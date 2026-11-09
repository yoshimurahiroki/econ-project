"""Resolve stable operation/rule IDs from three authoritative registries.

The schema-1 reader is retained for old installations.
The schema-2 normalized view keeps maintenance consumers independent of storage.
"""
import json
import copy
import re
import ast
import html
import unicodedata
import posixpath
from collections import deque
from pathlib import Path


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate route key: {key}')
        result[key] = value
    return result


def expand_operation_registry(data):
    """Expand shared authoring fields into the existing schema-2 contract."""
    if 'storage_format' not in data:
        return data
    if data['storage_format'] != 'shared-operation-fields-v1':
        raise ValueError('Unsupported operation registry storage format')
    defaults = data.get('operation_defaults')
    sets = data.get('conditional_rule_sets')
    if (not isinstance(defaults, dict) or set(defaults) != {'input_contract', 'finish', 'result_contract'}
            or not isinstance(defaults['result_contract'], dict)
            or set(defaults['result_contract']) != {'role', 'kind', 'target'}
            or not isinstance(sets, dict)):
        raise ValueError('Invalid shared operation fields')
    for name, rows in sets.items():
        if (not isinstance(name, str) or not name or not isinstance(rows, list)
                or any(not isinstance(row, dict) or 'when' not in row or set(row) - {'when', 'uses_profile'}
                       or not isinstance(row['when'], str) or not row['when']
                       or 'uses_profile' in row and type(row['uses_profile']) is not bool for row in rows)):
            raise ValueError('Invalid shared conditional rules: ' + str(name))
    expanded = {k: copy.deepcopy(v) for k, v in data.items()
                if k not in ('storage_format', 'operation_defaults', 'conditional_rule_sets')}
    operations = []
    for source in data['operations']:
        op = copy.deepcopy(source)
        op.setdefault('input_contract', copy.deepcopy(defaults['input_contract']))
        op.setdefault('finish', defaults['finish'])
        result = op.pop('result_contract', {})
        if not isinstance(result, dict) or set(result) - {'role', 'kind', 'target', 'meaning'}:
            raise ValueError('Invalid compact result contract')
        op['result_contract'] = {**copy.deepcopy(defaults['result_contract']),
                                 'meaning': op['trigger'], **result}
        if 'conditional_rule_set' in op:
            name = op.pop('conditional_rule_set')
            if 'conditional_rules' in op or not isinstance(name, str) or name not in sets:
                raise ValueError('Invalid shared conditional rules: ' + str(name))
            op['conditional_rules'] = copy.deepcopy(sets[name])
        if 'conditional_rules' in op:
            if not isinstance(op['conditional_rules'], list):
                raise ValueError('Invalid conditional rules: ' + str(op.get('id')))
            edges = []
            for row in op['conditional_rules']:
                if not isinstance(row, dict):
                    raise ValueError('Invalid conditional rule: ' + str(op.get('id')))
                if 'conditional_rule_set' in row:
                    name = row['conditional_rule_set']
                    if set(row) != {'conditional_rule_set'} or not isinstance(name, str) or name not in sets:
                        raise ValueError('Invalid shared conditional rules: ' + str(name))
                    edges.extend(copy.deepcopy(sets[name]))
                elif (not isinstance(row.get('when'), str) or not row['when'] or set(row) - {'when', 'uses_profile'}
                      or 'uses_profile' in row and type(row['uses_profile']) is not bool):
                    raise ValueError('Invalid conditional rule: ' + str(op.get('id')))
                else:
                    edges.append(row)
            op['conditional_rules'] = edges
        # Keep the established public field order as well as its values.
        order = ('id', 'owner_skill', 'mode', 'trigger', 'input_contract', 'required_rules',
                 'conditional_rules', 'result_contract', 'finish', 'uses_profile',
                 'explicit_profile_allowed', 'default')
        operations.append({**{key: op[key] for key in order if key in op},
                           **{key: value for key, value in op.items() if key not in order}})
    expanded['operations'] = operations
    return expanded


def relative(value):
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value) or '\\' in value or Path(value).is_absolute() or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError(f'Unsafe route path: {value}')
    return value


def load_routes(root, layout='source'):
    base = Path(root) / ('registry' if layout == 'source' else '.agents/registry')
    if base.exists():
        routes = load_registry(root, layout)
    else:
        path = Path(root) / ('runtime/ROUTES.yaml' if layout == 'source' else '.agents/runtime/ROUTES.yaml')
        routes = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_object)
    if routes.get('schema_version') not in (1, 2):
        raise ValueError('Unsupported ROUTES schema_version')
    resources = routes['resources']
    if isinstance(resources, list):
        resources = {r['resource_id']: r for r in resources}
        routes['resources'] = resources
    aliases, deployments = set(), set()
    for rid, resource in resources.items():
        relative(resource['source_path'])
        deployed = relative(resource['deployment_path'])
        if deployed.casefold() in deployments:
            raise ValueError(f'Duplicate deployment path: {deployed}')
        deployments.add(deployed.casefold())
        name = relative(resource['export_alias'])
        if '/' in name or name.casefold() in aliases:
            raise ValueError(f'Duplicate or non-flat export alias: {name}')
        aliases.add(name.casefold())
    for operation in routes['operations']:
        required = operation['required_resources']
        conditional = [r['resource_id'] for r in operation.get('conditional_resources', [])]
        if set(required + conditional) - resources.keys():
            raise ValueError('Operation refers to an unknown resource')
    registry = condition_registry(routes)
    for cid, selection in registry.items():
        if set(selection) - resources.keys():
            raise ValueError(f'Unknown condition resource: {cid}')
        merge_selection({}, selection)
    for obj in [*routes['operations'], routes.get('placements', {})]:
        if set(obj.get('conditions', [])) - registry.keys():
            raise ValueError('Unknown condition ID in operation')
        if set(obj.get('resource_sections', {})) - resources.keys():
            raise ValueError('Unknown selected resource')
    return routes


def resource_path(root, resource, layout='source'):
    key = {'source': 'source_path', 'installed': 'deployment_path'}[layout]
    root = Path(root).resolve()
    path = root / relative(resource[key])
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root and p.is_relative_to(root)) or not path.resolve().is_relative_to(root):
        raise ValueError(f'Refuse symlink or escaping resource: {resource[key]}')
    return path


def merge_selection(target, additions):
    """Union declarative selections; an empty section list adds no body."""
    for rid, selection in additions.items():
        if not isinstance(selection, dict) or set(selection) - {'sections', 'whole_resource'}:
            raise ValueError(f'Invalid resource selection: {rid}')
        sections = selection.get('sections', [])
        if not isinstance(sections, list) or any(not isinstance(s, str) or not s for s in sections):
            raise ValueError(f'Invalid sections: {rid}')
        if selection.get('whole_resource'):
            target[rid] = {'whole_resource': True}
        elif sections and not target.get(rid, {}).get('whole_resource'):
            target[rid] = {'sections': list(dict.fromkeys(target.get(rid, {}).get('sections', []) + sections))}
    return target


def condition_registry(routes):
    if routes.get('schema_version') == 2:
        return routes['conditions']
    registry = dict(routes.get('conditions', {}))
    # Read legacy registries, rejecting conflicting duplicate definitions.
    for obj in [*routes['operations'], routes.get('placements', {}), *[a for a in routes.get('aliases', {}).values() if isinstance(a, dict)]]:
        for entry in obj.get('conditional_resources', []):
            rid, cid = entry['resource_id'], entry['when']
            selection = {k: entry[k] for k in ('sections', 'whole_resource') if k in entry}
            if not selection:
                selection = {'whole_resource': True}
            previous = registry.setdefault(cid, {}).get(rid)
            if previous is not None and previous != selection:
                raise ValueError(f'Conflicting condition definition: {cid}/{rid}')
            registry[cid][rid] = selection
    return registry


def resolve_operation(routes, selector, mode=None, *, user_profile=None, project_profile=None, conditions=()):
    requested = selector
    alias = routes.get('aliases', {}).get(selector)
    metadata = alias if isinstance(alias, dict) else {}
    if metadata.get('runtime_action'):
        action = metadata['runtime_action']
        result = {'skill_id': 'runtime', 'operation': action, 'mode': action, **metadata}
    else:
        if isinstance(alias, str):
            selector = alias
        elif metadata.get('operation_id'):
            selector = metadata['operation_id']
        elif metadata:
            selector = metadata.get('skill_id', metadata.get('operation', selector))
            if mode and metadata.get('mode') and mode != metadata['mode']:
                raise ValueError('Alias mode conflicts with explicit mode')
            mode = mode or metadata.get('mode')
        candidates = [r for r in routes['operations'] if selector in (r['skill_id'], r['operation'], r.get('id')) and (mode is None or r['mode'] == mode)]
        if not candidates:
            raise ValueError(f'Unknown operation or mode: {selector}:{mode}')
        if len(candidates) > 1:
            candidates = [r for r in candidates if r.get('default', False)]
            if len(candidates) != 1:
                raise ValueError(f'Specify --mode for {selector}')
        result = dict(candidates[0])
    selection = {}
    active_rules = []
    origins = {}
    if routes.get('schema_version') == 2:
        pending = list(result.get('required_rules', []))
        for cid in conditions:
            if cid not in routes.get('condition_definitions', {}):
                raise ValueError('Unknown condition: ' + cid)
            pending.extend(routes['condition_definitions'][cid].get('required_rules', []))
        active_rules, selection = required_closure(routes, pending, conditions, result.get('id', requested))
        origins = {rule_id: result.get('id', requested) for rule_id in active_rules}
    for obj in ([routes.get('placements', {}), result] if routes.get('schema_version') == 1 else []):
        ids = obj.get('required_resources', obj.get('common_resources', []))
        declared = obj.get('resource_sections', {})
        merge_selection(selection, {rid: declared.get(rid, {'whole_resource': True}) for rid in ids})
        merge_selection(selection, declared)
    registry = condition_registry(routes)
    unknown = set(conditions) - registry.keys()
    if unknown:
        raise ValueError('Unknown condition: ' + ', '.join(sorted(unknown)))
    for cid in conditions:
        merge_selection(selection, registry[cid])
    profile = user_profile or project_profile or 'default-micro'
    uses_profile = result.get('uses_writing_profile', result['skill_id'] == 'econ-writing')
    uses_profile = uses_profile or (bool(user_profile) and result.get('explicit_profile_allowed', False))
    uses_profile = uses_profile or any(
        edge.get('uses_profile', False) and edge.get('when') in conditions
        for edge in result.get('conditional_rules', [])
    )
    if uses_profile:
        selection.pop('default-micro', None)
    if uses_profile and profile == 'default-micro' and profile in routes['resources']:
        merge_selection(selection, {profile: {'whole_resource': True}})
    result.update(requested_selector=requested,
                  canonical_operation=result.get('id', result['skill_id'] + ':' + result['mode']),
                  owner_skill=result['skill_id'], default_input=metadata.get('default_input', result.get('default_input')),
                  requested_section=metadata.get('requested_section', metadata.get('section', result.get('section'))),
                  selected_profile=profile if uses_profile else None,
                  resource_sections=selection, active_rules=active_rules, required_rule_origins=origins,
                  required_outputs=result.get('required_outputs', []), required_actions=result.get('required_actions', []))
    return result






def select_reading_sections(routes, manifest, stage, role=None, reader_id=None, unresolved=()):
    """Select current reading within the unchanged adopted closure.

    This is navigation, not a new adoption or evidence of actual reading.
    Section IDs come from the same registry used to bind the run.
    """
    stages = routes.get('reading_stages', {})
    if stage not in stages:
        raise ValueError('Unknown reading stage: ' + str(stage))
    adopted = manifest.get('resource_sections', {})
    selected = {}
    for rid, ids in stages[stage].items():
        if rid in adopted:
            selected[rid] = list(ids)
    for rid, ids in routes.get('reading_roles', {}).get(role, {}).get(stage, {}).items():
        if rid in adopted:
            selected.setdefault(rid, []).extend(ids)
    # Entry exposes the complete adopted instruction closure before dependent
    # work. Later stages navigate that same closure and reuse covered ranges.
    if stage in ('entry', 'compose'):
        managed = set().union(*(set(value) for value in stages.values()))
        for rid, scope in adopted.items():
            if (stage == 'entry' or rid not in managed) and routes['resources'][rid]['source_path'].endswith('.md'):
                selected[rid] = (['all'] if scope.get('whole_resource') else
                    [sid for sid, loc in routes['sections'][rid].items()
                     if loc.get('heading') in scope.get('sections', [])])
        for rid in ('research', 'prose'):
            if rid in adopted:
                scope = adopted[rid]
                selected[rid] = (['all'] if scope.get('whole_resource') else
                    [sid for sid, loc in routes['sections'][rid].items()
                     if loc.get('heading') in scope.get('sections', [])])
    for item in unresolved:
        if isinstance(item, dict):
            for rule_id in item.get('rule_ids', []):
                rule = routes['rules'].get(rule_id)
                if rule and rule['resource_id'] in adopted:
                    selected.setdefault(rule['resource_id'], []).append(rule['section_id'])
    result = []
    for rid, ids in selected.items():
        scope = adopted[rid]
        for sid in dict.fromkeys(ids):
            locator = routes['sections'][rid].get(sid)
            if locator is None:
                raise ValueError('Unknown reading section: ' + rid + '/' + sid)
            if not scope.get('whole_resource') and locator.get('heading') not in scope.get('sections', []):
                continue
            result.append({'resource_id': rid, 'section_id': sid,
                'rule_ids': [key for key, row in routes['rules'].items()
                             if row['resource_id'] == rid and row['section_id'] == sid]})
    return result



def native_index(routes, *, links=False, operation=None):
    if operation is not None:
        selected = resolve_operation(routes, operation)
        lines = ['# ' + selected['canonical_operation'], '', selected['description'], '',
                 'Select the conditions actually present in the request. `read ' + selected['canonical_operation']
                 + ' --condition CONDITION` delivers their complete bodies and prerequisites.', '',
                 '| Condition | Direct required bodies | Optional examples |', '| --- | --- | --- |']
        for cid in dict.fromkeys(selected['conditions']):
            condition = routes['condition_definitions'][cid]
            bodies = []
            for rule_id in condition.get('required_rules', []):
                rule = routes['rules'][rule_id]
                locator = routes['sections'][rule['resource_id']][rule['section_id']]
                bodies.append(rule['resource_id'] + ': ' + locator.get('heading', 'complete body'))
            examples = ', '.join(condition.get('optional_examples', []))
            lines.append('| `' + cid + '` | ' + '; '.join(bodies) + ' | ' + examples + ' |')
        return '\n'.join(lines) + '\n'
    lines = ['# Economics operation index', '', 'Generated from registry/operations.json. Select the final operation, then read CORE, PROSE and its complete required rule bodies. Support continues the same task.', '']
    for op in routes['operations']:
        label = op['skill_id'] + ' / ' + op['mode']
        if links:
            path = posixpath.relpath(routes['resources'][op['owner_skill']]['source_path'], 'docs/ai')
            label = f'[{label}]({path})'
        lines.append(f"- {label}: {op.get('trigger', op['operation'])}")
    lines += ['', 'Compatibility names:', '']
    for alias, target in routes.get('aliases', {}).items():
        lines.append(f'- {alias}: ' + json.dumps(target, ensure_ascii=False, sort_keys=True))
    if links:
        lines += ['', '## Select the next reference', '',
                  'Choose the operation above, then the applicable field or method below. Read the selected body and its prerequisite rules completely. An index supplies locations; the linked body supplies the method.', '']
        for rid in ('design-methods', 'data-implementation', 'models-causal', 'models-markets',
                    'models-dynamic', 'models-macro-extended', 'models-dsge', 'models-numerics',
                    'econ-knowledge', 'research-execution', 'result-artifacts'):
            if rid in routes['resources']:
                path = posixpath.relpath(routes['resources'][rid]['source_path'], 'docs/ai')
                lines.append(f'- [{rid}]({path})')
        lines += ['', 'For local or extracted runtimes, go directly to a known `read OPERATION --condition CONDITION`. `index --operation OPERATION` lists its conditions and bodies; `index --resource RESOURCE_ID` lists a method hierarchy and prerequisites. Read pages through `next_offset` until null. `read RULE_ID` returns that rule with its prerequisites. Reuse complete same-version reads.', '']
    return '\n'.join(lines) + '\n'


def resource_index(routes, resource_id):
    """Locate independently selectable bodies from their canonical rule edges."""
    resource = routes['resources'].get(resource_id)
    if resource is None:
        raise ValueError('Unknown resource: ' + resource_id)
    rules = resource.get('reading_index') or [key for key, value in routes['rules'].items()
                                             if value['resource_id'] == resource_id]
    parent = posixpath.dirname(resource['source_path'])
    lines = ['| Complete body | Rule | Activation | Prerequisites |',
             '| --- | --- | --- | --- |']
    for key in rules:
        rule = routes['rules'][key]
        rid, sid = rule['resource_id'], rule['section_id']
        locator = routes['sections'][rid][sid]
        title = locator.get('heading', rid)
        path = posixpath.relpath(routes['resources'][rid]['source_path'], parent)
        if not locator.get('whole_resource'):
            path += '#' + heading_id(title)
        conditions = [cid for cid, value in routes['condition_definitions'].items()
                      if key in value.get('required_rules', [])]
        active = ', '.join('`' + cid + '`' for cid in conditions)
        dependencies = []
        for dep in rule['requires']:
            edge = routes['rules'][dep]
            source = routes['resources'][edge['resource_id']]['source_path']
            target = posixpath.relpath(source, parent)
            part = routes['sections'][edge['resource_id']][edge['section_id']]
            if not part.get('whole_resource'):
                target += '#' + heading_id(part['heading'])
            dependencies.append(f'[{dep}]({target})')
        required = ', '.join(dependencies)
        lines.append(f'| [{title}]({path}) | `{key}` | {active} | {required} |')
    return '\n'.join(lines) + '\n'


def extract_sections(text, selection, resource):
    if selection.get('whole_resource'):
        return text
    lines, headings = markdown_sections(text)
    included = set()
    if selection.get('sections') and lines and lines[0].strip() == '---':
        closing = next((i for i in range(1, len(lines)) if lines[i].strip() in ('---', '...')), None)
        if closing is not None:
            included.update(range(closing + 1))
    for section in selection.get('sections', []):
        matches = [h for h in headings if section in (h['title'], h['id'], '#' + h['id'])]
        if len(matches) != 1:
            raise ValueError(f'Missing or ambiguous section: {resource} / {section}')
        included.update(range(matches[0]['start'], matches[0]['end']))
    return ''.join(line for i, line in enumerate(lines) if i in included)


def read_selected(routes, root, selector, *, layout='source', mode=None, conditions=(),
                  user_profile=None, project_profile=None, offset=0, limit=16000):
    """Deliver exact selected bodies; pagination never marks them as read."""
    import hashlib
    if offset < 0 or limit < 1:
        raise ValueError('Reading offset must be nonnegative and limit positive')
    unknown = set(conditions) - routes['condition_definitions'].keys()
    if unknown:
        raise ValueError('Unknown condition: ' + ', '.join(sorted(unknown)))
    custom_profile = None
    if selector in routes['rules']:
        active, selection = required_closure(routes, [selector], conditions, selector)
    else:
        operation = resolve_operation(routes, selector, mode, conditions=conditions,
                                      user_profile=user_profile, project_profile=project_profile)
        active, selection = operation['active_rules'], operation['resource_sections']
        profile = operation.get('selected_profile')
        if profile and profile != 'default-micro':
            custom_profile = Path(profile)
            if not custom_profile.is_absolute():
                custom_profile = Path(root) / custom_profile
    bodies, sources = {}, []
    for rid, scope in selection.items():
        path = resource_path(root, routes['resources'][rid], layout)
        raw = path.read_bytes()
        bodies[rid] = raw.decode('utf-8')
        sources.append({'resource_id': rid, 'path': str(path),
                        'sha256': hashlib.sha256(raw).hexdigest(), 'selection': scope})
    validate_rule_bodies(routes, active, bodies.__getitem__, origin=selector)
    if custom_profile is not None:
        raw = custom_profile.read_bytes()
        bodies['selected-profile'] = raw.decode('utf-8')
        if not bodies['selected-profile'].strip():
            raise ValueError('Selected profile is empty: ' + str(custom_profile))
        sources.append({'resource_id': 'selected-profile', 'path': str(custom_profile),
                        'sha256': hashlib.sha256(raw).hexdigest(),
                        'selection': {'whole_resource': True}})
    text = '\n\n'.join('# Resource: ' + row['resource_id'] + '\n\n'
        + extract_sections(bodies[row['resource_id']], row['selection'], row['resource_id']).rstrip()
        for row in sources) + '\n'
    if offset > len(text):
        raise ValueError('Reading offset exceeds the selected body')
    end = min(offset + limit, len(text))
    return {'selector': selector, 'required_rules': active, 'sources': sources,
            'content_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'offset': offset, 'total_characters': len(text),
            'next_offset': end if end < len(text) else None,
            'text': text[offset:end]}


def _read_registry(root, path):
    source = resource_path(root, {'source_path': path}, 'source')
    obj = json.loads(source.read_text(encoding='utf-8'), object_pairs_hook=unique_object)
    if obj.get('schema_version') != 2:
        raise ValueError(f'Unsupported registry schema_version: {path}')
    return obj


def rule_selection(routes, rule_id, origin='registry'):
    """Translate a permanent ID through a separately editable source locator."""
    rule = routes['rules'].get(rule_id)
    if rule is None:
        raise ValueError(f'Missing required rule {rule_id}; operation {origin}')
    rid, sid = rule['resource_id'], rule['section_id']
    locator = routes['sections'].get(rid, {}).get(sid)
    if rid not in routes['resources'] or locator is None:
        raise ValueError(f'Missing required rule {rule_id} source section {rid}/{sid}; operation {origin}')
    return {rid: {'whole_resource': True} if locator.get('whole_resource') else {'sections': [locator['heading']]}}


def heading_id(text):
    text = re.sub(r'\s+#+\s*$', '', text).strip()
    return re.sub(r'[^\w\- ]', '', text.lower()).replace(' ', '-')


def inline_code_mask(text):
    """Mark matched backtick spans without changing their bytes or offsets."""
    mask = bytearray(len(text))
    position = 0
    while position < len(text):
        if text[position] != "`" or (position and text[position - 1] == "\\"):
            position += 1
            continue
        end = position
        while end < len(text) and text[end] == "`":
            end += 1
        length = end - position
        closing = end
        while closing < len(text):
            candidate = text.find("`", closing)
            if candidate < 0:
                break
            stop = candidate
            while stop < len(text) and text[stop] == "`":
                stop += 1
            if stop - candidate == length:
                mask[position:stop] = b"\x01" * (stop - position)
                position = stop
                break
            closing = stop
        else:
            candidate = -1
        if candidate < 0 or closing >= len(text):
            position = end
    return mask


def markdown_container_text(line, frame=None, with_frame=False):
    """Remove block container markers while retaining their textual contents."""
    if frame is not None:
        for kind, width in frame:
            if kind == 'quote':
                line = re.sub(r'^ {0,3}>[ \t]?', '', line, count=1)
            elif len(line) - len(line.lstrip(' \t')) >= width:
                line = line[width:]
        return line
    containers = []
    while True:
        quote = re.match(r'^ {0,3}>[ \t]?', line)
        listing = re.match(r'^ {0,3}(?:[-+*]|[0-9]{1,9}[.)])(?:[ \t]+|$)', line)
        marker = quote or listing
        if not marker:
            break
        containers.append(('quote' if quote else 'list', marker.end()))
        line = line[marker.end():]
    return (line, containers) if with_frame else line


def reference_definition_spans(text):
    """Locate block reference metadata, including continued destinations/titles.

    Return original character envelopes and raw labels; never enter fenced code.
    The display scanner receives this same implementation during generation.
    """
    lines = text.splitlines(keepends=True)
    offsets, total = [], 0
    for line in lines:
        offsets.append(total)
        total += len(line)
    def view(line):
        return markdown_container_text(line).rstrip('\r\n')
    def title(index, rest):
        if not rest or rest[0] not in '\"\'(':
            return None
        closer = ')' if rest[0] == '(' else rest[0]
        position = 1
        while index < len(lines):
            while position < len(rest):
                if rest[position] == '\\':
                    position += 2
                    continue
                if rest[position] == closer:
                    return index if not rest[position + 1:].strip() else None
                position += 1
            index += 1
            if index >= len(lines) or not view(lines[index]).strip():
                return None
            rest, position = view(lines[index]), 0
        return None
    found, index, fence, fence_frame = [], 0, None, []
    while index < len(lines):
        line, containers = markdown_container_text(lines[index], with_frame=True)
        if fence:
            line = markdown_container_text(lines[index], fence_frame)
        line = line.rstrip('\r\n')
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            if re.fullmatch(r' {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*', line):
                fence = None
            index += 1
            continue
        if marker:
            fence = marker.group(1)
            fence_frame = containers
            index += 1
            continue
        match = re.match(r'^ {0,3}\[((?:\\.|[^\]\\\r\n])+)\]:[ \t]*(.*)$', line)
        if not match:
            index += 1
            continue
        start, last, rest = index, index, match.group(2)
        if not rest and last + 1 < len(lines):
            last += 1
            rest = view(lines[last]).lstrip(' \t')
        destination = re.match(r'(?:<(?:\\.|[^<>])*?>|(?:\\.|[^\s<>\"\'])+)(.*)$', rest)
        if not destination:
            index += 1
            continue
        tail = destination.group(1).strip()
        if tail:
            end = title(last, tail)
            if end is None:
                index += 1
                continue
            last = end
        elif last + 1 < len(lines):
            continued = title(last + 1, view(lines[last + 1]).lstrip(' \t'))
            if continued is not None:
                last = continued
        found.append({'start': offsets[start], 'end': offsets[last] + len(lines[last]), 'label': match.group(1)})
        index = last + 1
    return found


def markdown_labels(text, mapping):
    """Keep link labels and their original coordinates, not link metadata.

    This bounded syntax recognizer never crosses a blank line. Undefined
    references remain literal text. Hidden definition lines retain their line
    endings so removing them cannot join separate paragraphs.
    """
    hidden, definitions = set(), set()
    paragraph_break = re.compile(r'\r?\n[ \t]*\r?\n')

    def reference(value):
        return ' '.join(html.unescape(re.sub(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\\\]\^_`{|}~])',
                                             r'\1', value)).split()).casefold()

    def closing(start, opener, closer):
        depth, index = 1, start + 1
        while index < len(text):
            if paragraph_break.match(text, index):
                return None
            char = text[index]
            if char == '\\':
                index += 2
                continue
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if not depth:
                    return index
            index += 1
        return None

    for definition in reference_definition_spans(text):
        definitions.add(reference(definition['label']))
        hidden.update(i for i in range(definition['start'], definition['end']) if text[i] not in '\r\n')

    index = 0
    while index < len(text):
        if index in hidden:
            index += 1
            continue
        if text[index] == '\\':
            index += 2
            continue
        if text[index] != '[':
            index += 1
            continue
        end = closing(index, '[', ']')
        if end is None:
            index += 1
            continue
        after, finish = end + 1, None
        if after < len(text) and text[after] == '(':
            # Parentheses in destinations may nest; quoted titles and angle
            # destinations may contain parentheses that are not delimiters.
            cursor, depth, quote, angle = after + 1, 1, None, False
            while cursor < len(text):
                char = text[cursor]
                if paragraph_break.match(text, cursor):
                    break
                if char == '\\':
                    cursor += 2
                    continue
                if quote:
                    if char == quote:
                        quote = None
                elif angle:
                    if char == '>':
                        angle = False
                elif char == '<':
                    angle = True
                elif char in '"\'' and text[cursor - 1].isspace():
                    quote = char
                elif char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                    if not depth:
                        finish = cursor + 1
                        break
                cursor += 1
        elif after < len(text) and text[after] == '[':
            reference_end = closing(after, '[', ']')
            if reference_end is not None:
                key = text[after + 1:reference_end] or text[index + 1:end]
                if reference(key) in definitions:
                    finish = reference_end + 1
        elif reference(text[index + 1:end]) in definitions:
            finish = after
        if finish is not None:
            hidden.add(index)
            hidden.update(range(end, finish))
        # Continue inside the label to recognize nested inline decoration.
        index += 1
    keep = [i for i in range(len(text)) if i not in hidden]
    return ''.join(text[i] for i in keep), [mapping[i] for i in keep]


def markdown_sections(text):
    """ATX and setext headings outside fences, with stable GitHub-style IDs."""
    lines = text.splitlines(keepends=True)
    headings, counts, fence, fence_frame = [], {}, None, []
    for index, line in enumerate(lines):
        fence_line, containers = markdown_container_text(line, with_frame=True)
        if fence:
            fence_line = markdown_container_text(line, fence_frame)
            if re.match(r'^ {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*$', fence_line):
                fence = None
            continue
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', fence_line)
        if marker:
            fence = marker.group(1)
            fence_frame = containers
            continue
        match = re.match(r'^ {0,3}(#{1,6})\s+(.+?)\s*$', line)
        if match:
            level, title, start = len(match.group(1)), re.sub(r'\s+#+$', '', match.group(2)), index
        elif index and re.match(r'^ {0,3}(=+|-+)\s*$', line) and lines[index - 1].strip() and not (index == 1 and lines[0].strip() == '---'):
            level, title, start = (1 if line.lstrip().startswith('=') else 2), lines[index - 1].strip(), index - 1
        else:
            continue
        slug = heading_id(title)
        count = counts.get(slug, 0); counts[slug] = count + 1
        headings.append({'title': title, 'id': slug + (f'-{count}' if count else ''), 'level': level, 'start': start})
    for i, heading in enumerate(headings):
        heading['end'] = next((h['start'] for h in headings[i + 1:] if h['level'] <= heading['level']), len(lines))
    return lines, headings


def validate_rule_bodies(routes, rule_ids, read_resource, origin='registry'):
    """Validate every required locator against the actual resource bytes.

    Whole-resource selects a range, not a waiver of dependent section bodies.
    Non-Markdown resources are checked in their own syntax, never as headings.
    """
    cache, verified = {}, set()
    for rule_id in rule_ids:
        rule_selection(routes, rule_id, origin)
        rule = routes['rules'][rule_id]
        rid, sid = rule['resource_id'], rule['section_id']
        path = routes['resources'][rid]['source_path']
        locator = routes['sections'][rid][sid]
        needed = locator.get('heading', sid)
        try:
            if (rid, sid) in verified:
                continue
            if rid not in cache:
                raw = read_resource(rid)
                text = raw.decode('utf-8') if isinstance(raw, bytes) else raw
                if not isinstance(text, str) or not text.strip():
                    raise ValueError('empty resource body')
                if any(ord(char) < 32 and char not in '\t\n\r\f' or ord(char) == 127 for char in text):
                    raise ValueError('unsupported control character in text resource')
                suffix = Path(path).suffix.lower()
                if suffix == '.py' and not ast.parse(text).body:
                    raise ValueError('empty Python body')
                if suffix == '.json' and not json.loads(text, object_pairs_hook=unique_object):
                    raise ValueError('empty JSON body')
                original = text
                if suffix == '.md':
                    text = re.sub(r'<!-- BEGIN GENERATED[^>]*-->.*?<!-- END GENERATED[^>]*-->', '', text, flags=re.S)
                    lines, headings = markdown_sections(text)
                else:
                    lines, headings = [], []
                cache[rid] = text, suffix, lines, headings, original
            text, suffix, lines, headings, original = cache[rid]
            if suffix != '.md':
                verified.add((rid, sid))
                continue
            if locator.get('whole_resource'):
                missing = [section['heading'] for section in routes['sections'][rid].values()
                           if not section.get('whole_resource') and
                           sum(section['heading'] in (h['title'], h['id'], '#' + h['id'])
                               for h in headings) != 1]
                if missing:
                    raise ValueError('whole resource lacks registered sections: ' + ', '.join(missing))
            if not locator.get('whole_resource'):
                matches = [h for h in headings if needed in (h['title'], h['id'], '#' + h['id'])]
                if len(matches) != 1:
                    raise ValueError('missing or ambiguous section')
                heading = matches[0]
                text = ''.join(lines[heading['start']:heading['end']])
            # Ignore headings, front matter, and comments as proof of a body.
            if text.startswith('---\n'):
                text = re.sub(r'\A---\n.*?\n(?:---|\.\.\.)\s*\n', '', text, count=1, flags=re.S)
            lines, headings = markdown_sections(text)
            skip = {h['start'] for h in headings}
            for h in headings:
                if h['start'] + 1 < len(lines) and re.match(r'^ {0,3}(=+|-+)\s*$', lines[h['start'] + 1]):
                    skip.add(h['start'] + 1)
            body = ''.join(line for i, line in enumerate(lines) if i not in skip)
            body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
            _, mapping = markdown_labels(body, [(i, i + 1) for i in range(len(body))])
            kept = {start for start, _ in mapping}
            shown = ''.join(char if index in kept or char in '\r\n' else ' '
                            for index, char in enumerate(body))
            structural = ''.join(markdown_container_text(line) for line in body.splitlines(keepends=True))
            structure_lines, structure_heads = markdown_sections(structural)
            heading_lines = {heading['start'] for heading in structure_heads}
            heading_lines.update(heading['start'] + 1 for heading in structure_heads
                if heading['start'] + 1 < len(structure_lines)
                and re.match(r'^ {0,3}(=+|-+)\s*$', structure_lines[heading['start'] + 1]))
            content, fence, fence_frame = [], None, []
            for index, (raw_line, shown_line) in enumerate(zip(body.splitlines(), shown.splitlines())):
                line, containers = markdown_container_text(raw_line, with_frame=True)
                if fence:
                    line = markdown_container_text(raw_line, fence_frame)
                marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
                if fence:
                    if re.fullmatch(r' {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*', line):
                        fence = None
                    else:
                        content.append(line)  # Nonempty code remains a real body.
                elif marker:
                    fence = marker.group(1)
                    fence_frame = containers
                elif index in heading_lines:
                    continue
                elif re.fullmatch(r' {0,3}(?:(?:\*[ \t]*){3,}|(?:_[ \t]*){3,}|(?:-[ \t]*){3,})', line):
                    continue
                else:
                    mask = inline_code_mask(raw_line)
                    for code in re.finditer(b'\x01+', mask):
                        segment = raw_line[code.start():code.end()]
                        width = len(segment) - len(segment.lstrip('`'))
                        content.append(segment[width:-width])
                    prose = html.unescape(re.sub(r'<[^>]*>', '', markdown_container_text(shown_line)))
                    prose = re.sub(r'[*_`~]', '', prose)
                    prose = re.sub(r'^\s*(?:[-+]|\d+[.)])(?:\s+\[[ xX]\])?\s*$', '', prose)
                    content.append(prose)
            if not any(not char.isspace() and unicodedata.category(char) not in {'Cc', 'Cf', 'Cs', 'Mn', 'Me'}
                       for char in ''.join(content)):
                raise ValueError('section has no non-generated body')
            verified.add((rid, sid))
        except (OSError, ValueError, SyntaxError, UnicodeError, KeyError) as error:
            raise ValueError(f'Missing required rule {rule_id}; required section {needed}; operation {origin}; source {path}: {error}') from error


def required_closure(routes, rule_ids, conditions=(), origin='registry'):
    """Close required edges and activated conditional edges, de-duplicating cycles."""
    active, selection, pending, seen = [], {}, deque(rule_ids), set()
    conditions = set(conditions)
    while pending:
        rule_id = pending.popleft()
        if rule_id in seen:
            continue
        merge_selection(selection, rule_selection(routes, rule_id, origin))
        seen.add(rule_id)
        active.append(rule_id)
        rule = routes['rules'][rule_id]
        pending.extend(rule.get('requires', []))
        for edge in rule.get('conditional_requires', []):
            if edge['when'] in conditions:
                pending.extend(edge['required_rules'])
    return active, selection


def load_registry(root, layout='source'):
    prefix = '' if layout == 'source' else '.agents/'
    names = ['registry/operations.json', 'registry/resources.json', 'registry/placements.json']
    op_data, resource_data, placement_data = [_read_registry(root, prefix + n) for n in names]
    op_data = expand_operation_registry(op_data)
    resources = {}
    if set(resource_data['resources']) != set(placement_data['resources']):
        raise ValueError('Resource and placement IDs differ')
    for rid, resource in resource_data['resources'].items():
        if resource.get('resource_id') != rid:
            raise ValueError('Resource key and resource_id differ: ' + rid)
        resources[rid] = {**resource, **placement_data['resources'][rid]}
        if resource.get('source_distribution_only'):
            resources[rid]['snapshot'] = 'source_distribution_only'
    routes = {'schema_version': 2, 'resources': resources,
              'rules': resource_data['rules'], 'sections': resource_data['sections'],
              'examples': resource_data.get('examples', {}),
              'aliases': op_data.get('aliases', {}), 'operations': [],
              'condition_definitions': op_data.get('conditions', {}),
              'reading_stages': resource_data.get('reading_stages', {}),
              'reading_roles': resource_data.get('reading_roles', {}),
              'conditions': {}, 'registry_source_paths': names,
              'placements': {k: v for k, v in placement_data.items() if k not in ('schema_version', 'resources')}}
    # Runtime consumers get joined pointer records.
    routes['placements']['policy_pointers'] = [
        {**resources[p['resource_id']], 'template_id': p['template_id']}
        for p in placement_data.get('policy_pointers', [])]
    for key, rule in routes['rules'].items():
        if key != rule.get('rule_id') or not isinstance(rule.get('requires'), list):
            raise ValueError('Invalid required rule: ' + key)
        rule_selection(routes, key)
    for stage, reading in routes['reading_stages'].items():
        if stage not in {'entry', 'contract', 'compose', 'review', 'finalize'} or not isinstance(reading, dict):
            raise ValueError('Invalid reading stage: ' + str(stage))
        for rid, ids in reading.items():
            if (rid not in resources or not isinstance(ids, list) or not ids
                    or any(not isinstance(sid, str) for sid in ids)
                    or len(ids) != len(set(ids)) or any(sid not in routes['sections'][rid] for sid in ids)):
                raise ValueError('Invalid reading sections: ' + str(rid))
    for role, stages in routes['reading_roles'].items():
        if role != 'author' or not isinstance(stages, dict):
            raise ValueError('Invalid reading role: ' + str(role))
        for stage, reading in stages.items():
            if stage not in routes['reading_stages'] or not isinstance(reading, dict):
                raise ValueError('Invalid role reading stage')
            for rid, ids in reading.items():
                if (rid not in resources or not isinstance(ids, list) or not ids
                        or any(not isinstance(sid, str) for sid in ids) or any(sid not in routes['sections'][rid] for sid in ids)):
                    raise ValueError('Invalid role reading sections')
    for cid, definition in routes['condition_definitions'].items():
        if definition.get('when') != cid:
            raise ValueError('Condition key and when differ: ' + cid)
        ids = definition.get('required_rules', [])
        example_ids = definition.get('optional_examples', [])
        if not ids and not example_ids:
            raise ValueError('Condition adds no body: ' + cid)
        _, selection = required_closure(routes, ids, [cid], 'condition ' + cid)
        for eid in example_ids:
            example = routes['examples'].get(eid)
            if not example:
                raise ValueError('Unknown optional example: ' + eid)
            rid, sid = example['resource_id'], example['section_id']
            locator = routes['sections'][rid][sid]
            merge_selection(selection, {rid: {'whole_resource': True} if locator.get('whole_resource') else {'sections': [locator['heading']]}})
        routes['conditions'][cid] = selection
    seen = set()
    for op in op_data['operations']:
        required_fields = {'id', 'owner_skill', 'mode', 'trigger', 'input_contract', 'required_rules', 'conditional_rules', 'result_contract', 'finish'}
        if required_fields - op.keys() or op['id'] in seen:
            raise ValueError('Invalid or duplicate operation: ' + str(op.get('id')))
        if any(type(op[key]) is not bool for key in ('uses_profile', 'explicit_profile_allowed') if key in op):
            raise ValueError('Invalid operation profile flag: ' + op['id'])
        seen.add(op['id'])
        _, selection = required_closure(routes, op['required_rules'], origin=op['id'])
        condition_ids = []
        for edge in op['conditional_rules']:
            cid = edge['when']
            if 'uses_profile' in edge and type(edge['uses_profile']) is not bool:
                raise ValueError('Invalid conditional profile flag: ' + op['id'])
            if cid not in routes['conditions']:
                raise ValueError('Unknown operation condition: ' + cid)
            condition_ids.append(cid)
        routes['operations'].append({**op, 'skill_id': op['owner_skill'], 'operation': op['mode'],
            'description': op['trigger'], 'uses_writing_profile': op.get('uses_profile', False),
            'required_resources': list(selection), 'resource_sections': selection,
            'conditions': condition_ids})
    for alias, definition in routes['aliases'].items():
        if definition.get('operation_id') and definition['operation_id'] not in seen:
            raise ValueError('Unknown alias target: ' + alias)
    # Validate unused dependency definitions too, after operation errors can name their owner.
    for key, rule in routes['rules'].items():
        for dep in rule['requires']:
            rule_selection(routes, dep, key)
    return routes




def generated_mode_block(routes, owner):
    lines = ['<!-- BEGIN GENERATED MODES -->', '## Registered operations', '',
             'Generated from registry/operations.json; the request determines the actual target and authority.', '']
    for op in routes['operations']:
        if op['owner_skill'] == owner:
            label = f"`{op['mode']}`"
            rule = routes['rules'].get(owner + '.' + op['mode'])
            if rule:
                locator = routes['sections'][rule['resource_id']][rule['section_id']]
                if locator.get('heading'):
                    entry = routes['resources'][owner]['source_path']
                    source = routes['resources'][rule['resource_id']]['source_path']
                    path = '' if source == entry else posixpath.relpath(source, posixpath.dirname(entry))
                    label = f"[{op['mode']}]({path}#{heading_id(locator['heading'])})"
            lines.append(f"- {label}: {op['trigger']}")
    return '\n'.join(lines + ['<!-- END GENERATED MODES -->'])


def entry_contract(routes, core, prose, index):
    """Render the registered entry body for a source, package or hook consumer."""
    template = routes['placements']['pointer_templates']['economics-task-entry']
    return template.split('\n\n', 1)[1].format(core=core, prose=prose, index=index).strip()


def replace_generated_section(text, title, block, marker):
    """Replace the one owned section, including an older unmarked version."""
    generated = r'<!-- BEGIN GENERATED ' + marker + r' -->.*?<!-- END GENERATED ' + marker + r' -->'
    if re.search(generated, text, re.S):
        return re.sub(generated, lambda _: block, text, flags=re.S)
    section = r'^## ' + re.escape(title) + r'\n.*?(?=^#{1,2} |\Z)'
    if re.search(section, text, re.M | re.S):
        return re.sub(section, lambda _: block + '\n\n', text, flags=re.M | re.S)
    return text.rstrip() + '\n\n' + block + '\n'


def optional_reference(resources, title):
    """Recover a registered resource and section from an optional-input heading."""
    matches = []
    for rid in resources:
        if title in (rid, heading_id(rid)):
            matches.append((rid, None))
        else:
            for prefix in dict.fromkeys((rid + '--', heading_id(rid) + '--')):
                if isinstance(title, str) and title.startswith(prefix) and title[len(prefix):]:
                    matches.append((rid, title[len(prefix):]))
                    break
    if len(matches) != 1:
        raise ValueError('Unregistered or ambiguous optional reference: ' + str(title))
    return matches[0]


def transform_entry_references(routes, resource_id, text):
    """Resolve canonical entry links through their registered resources."""
    from urllib.parse import urlsplit, unquote, urlunsplit
    from export_project import rewrite_markdown
    resources = routes['resources']
    entry = resources[resource_id]['source_path']
    parent = posixpath.dirname(entry)
    aliases = {resource['source_path']: rid for rid, resource in resources.items()}
    def destination(link):
        parts = urlsplit(link)
        if parts.scheme or parts.netloc or not parts.path:
            return link
        target = posixpath.normpath(posixpath.join(parent, unquote(parts.path)))
        if target not in aliases:
            raise ValueError('Unregistered entry reference: ' + resource_id + ': ' + link)
        return urlunsplit(('', '', posixpath.relpath(target, parent), parts.query, parts.fragment))
    return rewrite_markdown(text, destination)


def generate_entries(root, routes=None):
    """Regenerate human entries; never infer operation modes from handwritten prose."""
    import os
    import re
    root = Path(root)
    routes = load_routes(root) if routes is None else routes
    def write_changed(path, text, previous=None):
        raw = text.encode('utf-8')
        previous = path.read_bytes() if previous is None and path.is_file() else previous
        if raw != previous:
            path.write_bytes(raw)
    write_changed(root / 'docs/ai/compiled_ai_skills.md', native_index(routes, links=True))
    for rid, resource in routes['resources'].items():
        if resource.get('reading_index'):
            path = root / resource['source_path']
            body = path.read_text(encoding='utf-8')
            block = ('<!-- BEGIN GENERATED METHOD INDEX -->\n## Select a method\n\n'
                     + resource_index(routes, rid) + '<!-- END GENERATED METHOD INDEX -->')
            write_changed(path, replace_generated_section(body, 'Select a method', block, 'METHOD INDEX'))
    guide = ['# Registered resources', '', 'Generated from the resource and placement registries. Use this catalog only for requested distribution or maintenance.', '']
    guide += [f"- {rid}: {r['source_path']}" + (' (complete source distribution only)' if r.get('source_distribution_only') else '') for rid, r in routes['resources'].items()]
    write_changed(root / 'docs/ai/resources.md', '\n'.join(guide) + '\n')
    write_changed(root / 'docs/ai/project_instructions.txt', entry_contract(routes,
        '../../runtime/CORE.md', '../../runtime/PROSE.md', 'compiled_ai_skills.md') + '\n')
    for pointer in routes['placements']['policy_pointers']:
        path = root / pointer['source_path']
        template = routes['placements']['pointer_templates'][pointer['template_id']]
        body = template.format(
            core=os.path.relpath(root / 'runtime/CORE.md', path.parent),
            prose=os.path.relpath(root / 'runtime/PROSE.md', path.parent),
            operations=os.path.relpath(root / 'registry/operations.json', path.parent),
            index=os.path.relpath(root / 'docs/ai/compiled_ai_skills.md', path.parent))
        write_changed(path, body)
    for owner in sorted({o['owner_skill'] for o in routes['operations']}):
        path = root / routes['resources'][owner]['source_path']
        previous = path.read_bytes()
        body = previous.decode('utf-8')
        body = re.sub(r'\n*<!-- BEGIN GENERATED REVIEW PLANS -->.*?<!-- END GENERATED REVIEW PLANS -->', '', body, flags=re.S)
        entry_pattern = r'<!-- BEGIN GENERATED ENTRY -->.*?<!-- END GENERATED ENTRY -->'
        if re.search(entry_pattern, body, re.S):
            entry = ('<!-- BEGIN GENERATED ENTRY -->\n## Native entry contract\n\n' +
                entry_contract(routes, '../../runtime/CORE.md',
                    '../../runtime/PROSE.md', '../../docs/ai/compiled_ai_skills.md') +
                '\n<!-- END GENERATED ENTRY -->')
            body = re.sub(entry_pattern, lambda _: entry, body, flags=re.S)
        block = generated_mode_block(routes, owner)
        body = replace_generated_section(body, 'Registered operations', block, 'MODES')
        if owner == 'econ-review':
            body = re.sub(r'^Mode `assess`.*?\n\n', '', body, flags=re.M)
        body = transform_entry_references(routes, owner, body)
        write_changed(path, body, previous)
    modes = [op['mode'] for op in routes['operations'] if op['owner_skill'] == 'econ-writing']
    ui = 'interface:\n  display_name: "Economics Writing"\n  short_description: "Write, explain and revise natural academic prose"\n  default_prompt: "Use $econ-writing in ' + ', '.join(modes) + ' mode. Read CORE, PROSE and the selected mode; build the explanation before shortening and complete the integrated review."\npolicy:\n  allow_implicit_invocation: true\n'
    write_changed(root / 'skills/econ-writing/agents/openai.yaml', ui)
    return routes


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Select and resolve registered economics operations')
    parser.add_argument('--root', type=Path)
    parser.add_argument('--layout', choices=('source', 'installed'), default='source')
    commands = parser.add_subparsers(dest='command', required=True)
    index = commands.add_parser('index', help='show operations, operation conditions or a resource hierarchy')
    selection = index.add_mutually_exclusive_group()
    selection.add_argument('--resource')
    selection.add_argument('--operation')
    for command, help_text in [('resolve', 'show the selected contract and rule closure'),
                               ('read', 'read exact selected rule bodies and prerequisites')]:
        selected = commands.add_parser(command, help=help_text)
        selected.add_argument('operation')
        selected.add_argument('--mode')
        selected.add_argument('--condition', action='append', default=[])
        selected.add_argument('--user-profile')
        selected.add_argument('--project-profile')
        if command == 'read':
            selected.add_argument('--offset', type=int, default=0, help='Character offset returned by the preceding page')
            selected.add_argument('--limit', type=int, default=16000, help='Maximum body characters per page')
    args = parser.parse_args()
    script_root = Path(__file__).resolve().parent.parent
    root = args.root or (script_root if args.layout == 'source' else script_root.parent)
    routes = load_routes(root, args.layout)
    if args.command == 'index':
        print(resource_index(routes, args.resource) if args.resource else
              native_index(routes, operation=args.operation), end='')
    elif args.command == 'read':
        result = read_selected(routes, root, args.operation, layout=args.layout, mode=args.mode,
                               conditions=args.condition, user_profile=args.user_profile,
                               project_profile=args.project_profile, offset=args.offset, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = resolve_operation(routes, args.operation, args.mode,
                                   user_profile=args.user_profile, project_profile=args.project_profile,
                                   conditions=args.condition)
        print(json.dumps(result, ensure_ascii=False, indent=2))
