"""Resolve stable operation/rule IDs from three authoritative registries.

The schema-1 reader is retained for old installations.
The schema-2 normalized view keeps maintenance consumers independent of storage.
"""
import json
import re
import ast
import html
import unicodedata
from pathlib import Path


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate route key: {key}')
        result[key] = value
    return result


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
    uses_profile = result.get('uses_writing_profile', result['skill_id'] in ('econ-writing', 'econ-paper'))
    selection.pop('default-micro', None) if uses_profile else None
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


def review_definition(routes, plan):
    """Return the validated registry definition, never a caller-authored plan."""
    if plan not in routes['review_plans']:
        raise ValueError('Unknown review plan: ' + str(plan))
    return json.loads(json.dumps(routes['review_plans'][plan]))


def bounded_review_eligible(routes, operation, conditions=(), templates=(), plan='focused'):
    """Check registry eligibility, not the task's complete scope evidence.

    Loading supporting rules or examples does not itself change the operation.
    The harness separately verifies pinned inputs, text-only requirements and
    the absence of actions, investigation, quantitative changes and audit scope.
    """
    resolved = resolve_operation(routes, operation, conditions=conditions)
    definition = review_definition(routes, plan)
    for rid in templates:
        if rid not in routes['resources']:
            raise ValueError('Unknown template resource: ' + str(rid))
        if type(routes['resources'][rid].get('full_review_required', False)) is not bool:
            raise ValueError('template full_review_required must be bool: ' + rid)
    return (resolved['canonical_operation'] in definition['eligible_operations']
            and not any(routes['condition_definitions'][cid]['full_review_required']
                        for cid in conditions)
            and not any(routes['resources'][rid].get('full_review_required', False)
                        for rid in templates))


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
    # Specialized operation/profile/template bodies are read during production;
    # source/method sections remain those selected at begin.
    if stage == 'compose':
        managed = set().union(*(set(value) for value in stages.values()))
        for rid, scope in adopted.items():
            if rid not in managed and routes['resources'][rid]['source_path'].endswith('.md'):
                selected[rid] = (['all'] if scope.get('whole_resource') else
                    [sid for sid, loc in routes['sections'][rid].items()
                     if loc.get('heading') in scope.get('sections', [])])
        for rid in ('research', 'prose'):
            if rid in adopted:
                scope = adopted[rid]
                selected[rid] = (['all'] if scope.get('whole_resource') else
                    [sid for sid, loc in routes['sections'][rid].items()
                     if loc.get('heading') in scope.get('sections', [])])
    if stage == 'entry' and 'research' in adopted:
        selected['research'] = [sid for sid in ('turn-the-question-into-an-operation', 'select-a-feasible-action')
                                if sid in routes['sections']['research']]
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

def focused_review_eligible(routes, operation, conditions=(), templates=()):
    return bounded_review_eligible(routes, operation, conditions, templates)


def native_index(routes):
    lines = ['# Economics operation index', '', 'Generated from registry/operations.json. Read runtime/CORE.md once; select the final operation below. Support continues the same task.', '']
    for op in routes['operations']:
        lines.append(f"- {op['skill_id']} / {op['mode']}: {op.get('trigger', op['operation'])}")
    lines += ['', 'Compatibility names:', '']
    for alias, target in routes.get('aliases', {}).items():
        lines.append(f'- {alias}: ' + json.dumps(target, ensure_ascii=False, sort_keys=True))
    return '\n'.join(lines) + '\n'


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
    cache = {}
    for rule_id in rule_ids:
        rule_selection(routes, rule_id, origin)
        rule = routes['rules'][rule_id]
        rid, sid = rule['resource_id'], rule['section_id']
        path = routes['resources'][rid]['source_path']
        locator = routes['sections'][rid][sid]
        needed = locator.get('heading', sid)
        try:
            if rid not in cache:
                raw = read_resource(rid)
                cache[rid] = raw.decode('utf-8') if isinstance(raw, bytes) else raw
            text = cache[rid]
            if not isinstance(text, str) or not text.strip():
                raise ValueError('empty resource body')
            if any(ord(char) < 32 and char not in '\t\n\r\f' or ord(char) == 127 for char in text):
                raise ValueError('unsupported control character in text resource')
            suffix = Path(path).suffix.lower()
            if suffix == '.py':
                if not ast.parse(text).body:
                    raise ValueError('empty Python body')
                continue
            if suffix == '.json':
                if not json.loads(text, object_pairs_hook=unique_object):
                    raise ValueError('empty JSON body')
                continue
            if suffix != '.md':
                continue
            text = re.sub(r'<!-- BEGIN GENERATED[^>]*-->.*?<!-- END GENERATED[^>]*-->', '', text, flags=re.S)
            lines, headings = markdown_sections(text)
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
        except (OSError, ValueError, SyntaxError, UnicodeError, KeyError) as error:
            raise ValueError(f'Missing required rule {rule_id}; required section {needed}; operation {origin}; source {path}: {error}') from error


def required_closure(routes, rule_ids, conditions=(), origin='registry'):
    """Close required edges and activated conditional edges, de-duplicating cycles."""
    active, selection, pending = [], {}, list(rule_ids)
    while pending:
        rule_id = pending.pop(0)
        if rule_id in active:
            continue
        merge_selection(selection, rule_selection(routes, rule_id, origin))
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
    resources = {}
    if set(resource_data['resources']) != set(placement_data['resources']):
        raise ValueError('Resource and placement IDs differ')
    for rid, resource in resource_data['resources'].items():
        if resource.get('resource_id') != rid:
            raise ValueError('Resource key and resource_id differ: ' + rid)
        resources[rid] = {**resource, **placement_data['resources'][rid]}
        if 'full_review_required' in resource and type(resource['full_review_required']) is not bool:
            raise ValueError('resource full_review_required must be bool: ' + rid)
        if resource.get('source_distribution_only'):
            resources[rid]['snapshot'] = 'source_distribution_only'
    routes = {'schema_version': 2, 'resources': resources,
              'rules': resource_data['rules'], 'sections': resource_data['sections'],
              'examples': resource_data.get('examples', {}),
              'aliases': op_data.get('aliases', {}), 'operations': [],
              'condition_definitions': op_data.get('conditions', {}),
              'review_plans': op_data.get('review_plans', {}),
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
        if role not in {'author', 'requirements-coverage', 'quality-a', 'quality-b', 'compliance'} or not isinstance(stages, dict):
            raise ValueError('Invalid reading role: ' + str(role))
        for stage, reading in stages.items():
            if stage not in routes['reading_stages'] or not isinstance(reading, dict):
                raise ValueError('Invalid role reading stage')
            for rid, ids in reading.items():
                if (rid not in resources or not isinstance(ids, list) or not ids
                        or any(not isinstance(sid, str) for sid in ids) or any(sid not in routes['sections'][rid] for sid in ids)):
                    raise ValueError('Invalid role reading sections')
    for cid, definition in routes['condition_definitions'].items():
        if definition.get('when') != cid or type(definition.get('full_review_required')) is not bool:
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
        seen.add(op['id'])
        _, selection = required_closure(routes, op['required_rules'], origin=op['id'])
        condition_ids = []
        for edge in op['conditional_rules']:
            cid = edge['when']
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
    plans = routes['review_plans']
    if not isinstance(plans, dict) or not {'full', 'focused'} <= set(plans) or set(plans) - {'full', 'focused', 'direct', 'strict-reviewed'}:
        raise ValueError('Registry requires full and focused review plans')
    for name, plan in plans.items():
        if not isinstance(plan, dict) or set(plan) - {'roles', 'capabilities', 'checks', 'eligible_operations', 'review_kind', 'quality_roles'} or not {'roles', 'capabilities', 'checks', 'eligible_operations'} <= set(plan):
            raise ValueError('Invalid review plan: ' + name)
        for field in ('roles', 'capabilities', 'eligible_operations'):
            values = plan[field]
            if not isinstance(values, list) or (not values and field != 'capabilities') or any(not isinstance(v, str) or not v for v in values) or len(values) != len(set(values)):
                raise ValueError('Invalid review plan ' + field)
        if (set(plan['eligible_operations']) - seen or not isinstance(plan['checks'], dict)
                or set(plan['checks']) != set(plan['roles'])
                or plan.get('review_kind', 'independent') not in {'independent', 'self-check'}
                or plan.get('review_kind', 'independent') == 'independent' and (
                    not set(plan['roles']) <= set(plan['capabilities'])
                    or 'independent-requirements-coverage' not in plan['capabilities'])
                or plan.get('review_kind') == 'self-check' and (plan['capabilities'] or name != 'direct')):
            raise ValueError('Inconsistent review plan: ' + name)
        quality_roles = plan.get('quality_roles', [role for role in plan['roles'] if role.startswith('quality-')])
        if (not isinstance(quality_roles, list) or not quality_roles or any(not isinstance(x, str) for x in quality_roles) or len(set(quality_roles)) != len(quality_roles)
                or set(quality_roles) - set(plan['roles'])):
            raise ValueError('Invalid quality-role assignment: ' + name)
        for checks in plan['checks'].values():
            if not isinstance(checks, list) or not checks or any(not isinstance(v, str) or not v for v in checks) or len(checks) != len(set(checks)):
                raise ValueError('Invalid review checks: ' + name)
    return routes


def generated_review_block(routes):
    lines = ['<!-- BEGIN GENERATED REVIEW PLANS -->', '## Registered review plans', '',
             'Ordinary work completes through CORE’s integrated review and applicable verification. The plans below configure an explicitly requested native audit or certification; activate `formal_review_requested` for its instruction bodies.', '',
             '| Plan | Roles | Review kind | Certified publication |', '|---|---|---|---|']
    for name, plan in routes['review_plans'].items():
        lines.append('| ' + name + ' | ' + ', '.join(plan['roles']) + ' | ' + plan.get('review_kind', 'independent') + ' | ' + ('requires authenticated strict release gate' if name == 'strict-reviewed' else 'ineligible') + ' |')
    lines += ['', 'The selected formal plan retains its registered roles, checks and capabilities. Certified publication uses strict-reviewed, the 142-rule dictionary, 22 whole-candidate judgments, actual independent returns and the existing authenticated release predicate.', '<!-- END GENERATED REVIEW PLANS -->']
    return '\n'.join(lines)


def generated_mode_block(routes, owner):
    lines = ['<!-- BEGIN GENERATED MODES -->', '## Registered operations', '',
             'Generated from registry/operations.json; the request determines the actual target and authority.', '']
    for op in routes['operations']:
        if op['owner_skill'] == owner:
            lines.append(f"- `{op['mode']}`: {op['trigger']}")
    return '\n'.join(lines + ['<!-- END GENERATED MODES -->'])


NATIVE_ENTRY_CONTRACT = '''<!-- BEGIN GENERATED ENTRY -->
## Native entry contract

Read [CORE](references/bundle/runtime/CORE.md), [PROSE](references/bundle/runtime/PROSE.md), the [registered operation](references/bundle/registry/operations.json) and its required bodies. Reuse same-version reads. Preserve the request, adopted inputs and authority; reason through the determining choices, execute the result, complete the integrated review and verify changed behavior through the existing path. Apply [CONTROL](references/bundle/runtime/CONTROL.md) when selecting a requested formal review.
<!-- END GENERATED ENTRY -->'''


def replace_generated_section(text, title, block, marker):
    """Replace the one owned section, including an older unmarked version."""
    generated = r'<!-- BEGIN GENERATED ' + marker + r' -->.*?<!-- END GENERATED ' + marker + r' -->'
    if re.search(generated, text, re.S):
        return re.sub(generated, lambda _: block, text, flags=re.S)
    section = r'^## ' + re.escape(title) + r'\n.*?(?=^#{1,2} |\Z)'
    if re.search(section, text, re.M | re.S):
        return re.sub(section, lambda _: block + '\n\n', text, flags=re.M | re.S)
    return text.rstrip() + '\n\n' + block + '\n'


def transform_entry_references(routes, resource_id, text, layout='source'):
    """Resolve registered entry links for repository or self-contained plugin placement."""
    import posixpath
    from urllib.parse import urlsplit, unquote, urlunsplit
    from export_project import rewrite_markdown
    if layout not in ('source', 'plugin'):
        raise ValueError('Unknown entry placement: ' + layout)
    entry = routes['resources'][resource_id]['source_path']
    parent = posixpath.dirname(entry)
    aliases = {}
    for rid, resource in routes['resources'].items():
        source = resource['source_path']
        bundled = source[:-len('SKILL.md')] + 'REFERENCE.md' if re.fullmatch(r'skills/[^/]+/SKILL\.md', source) else source
        for alias in (source, posixpath.join(parent, 'references/bundle', source),
                      posixpath.join(parent, 'references/bundle', bundled)):
            aliases[alias] = (source, bundled)
    def destination(link):
        parts = urlsplit(link)
        if parts.scheme or parts.netloc or not parts.path:
            return link
        target = posixpath.normpath(posixpath.join(parent, unquote(parts.path)))
        if target not in aliases:
            raise ValueError('Unregistered entry reference: ' + resource_id + ': ' + link)
        source, bundled = aliases[target]
        path = posixpath.relpath(source, parent) if layout == 'source' else 'references/bundle/' + bundled
        return urlunsplit(('', '', path, parts.query, parts.fragment))
    text = rewrite_markdown(text, destination)
    if layout == 'source':
        text = text.replace('## Read packaged resources', '## Read repository resources')
        start = text.find('Use this skill package for bundled file reads.')
        if start >= 0:
            end = text.find('\n\n', start)
            text = text[:start] + 'Read registered resources relative to this repository entry. Inherit the current request, authority and progress; use only dependencies of the selected operation.' + text[end if end >= 0 else len(text):]
    return text


def generate_entries(root):
    """Regenerate human entries; never infer operation modes from handwritten prose."""
    import os
    import re
    root = Path(root)
    routes = load_routes(root)
    # One authored Markdown parser, embedded for the standalone text scanner.
    source = (root / 'scripts/route_registry.py').read_text(encoding='utf-8')
    names = {'markdown_container_text', 'reference_definition_spans', 'markdown_labels'}
    definitions = [node for node in ast.parse(source).body
                   if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in definitions} != names or len(definitions) != len(names):
        raise ValueError('Shared Markdown parser definitions must be present and unique')
    shared = '\n\n'.join(ast.get_source_segment(source, node) for node in definitions)
    scanner = root / 'harness/local_checks.py'
    scanner_text = scanner.read_text(encoding='utf-8')
    block = '# BEGIN GENERATED MARKDOWN PARSER\n' + shared + '\n# END GENERATED MARKDOWN PARSER'
    pattern = r'# BEGIN GENERATED MARKDOWN PARSER\n.*?# END GENERATED MARKDOWN PARSER'
    if re.search(pattern, scanner_text, re.S):
        scanner_text = re.sub(pattern, lambda _: block, scanner_text, flags=re.S)
    else:
        node = next(node for node in ast.parse(scanner_text).body
                    if isinstance(node, ast.FunctionDef) and node.name == 'markdown_labels')
        scanner_lines = scanner_text.splitlines(keepends=True)
        scanner_text = ''.join(scanner_lines[:node.lineno - 1]) + block + '\n' + ''.join(scanner_lines[node.end_lineno:])
    scanner.write_text(scanner_text, encoding='utf-8')
    review_block = generated_review_block(routes)
    for document in ('runtime/CORE.md', 'runtime/CONTROL.md', 'runtime/TEAM.md', 'runtime/EXECUTION.md', 'runtime/PROSE.md', 'README.md'):
        path = root / document
        body = path.read_text(encoding='utf-8')
        pattern = r'<!-- BEGIN GENERATED REVIEW PLANS -->.*?<!-- END GENERATED REVIEW PLANS -->'
        if document == 'runtime/CONTROL.md':
            body = replace_generated_section(body, 'Registered review plans', review_block, 'REVIEW PLANS')
        else:
            body = re.sub(r'\n*' + pattern, '', body, flags=re.S).rstrip() + '\n'
        path.write_text(body, encoding='utf-8')
    (root / 'docs/ai/compiled_ai_skills.md').write_text(native_index(routes), encoding='utf-8')
    guide = ['# Registered resources', '', 'Generated from the resource and placement registries. Use this catalog only for requested distribution or maintenance.', '']
    guide += [f"- {rid}: {r['source_path']}" + (' (complete source distribution only)' if r.get('source_distribution_only') else '') for rid, r in routes['resources'].items()]
    (root / 'docs/ai/resources.md').write_text('\n'.join(guide) + '\n', encoding='utf-8')
    (root / 'docs/ai/project_instructions.txt').write_text('Read runtime/CORE.md and runtime/PROSE.md, then select the requested final operation in docs/ai/compiled_ai_skills.md. Read its required rule bodies and activated conditions from registry/operations.json; reuse same-version reads. Complete the authorized work, its integrated review and applicable verification under CORE.\n', encoding='utf-8')
    for pointer in routes['placements']['policy_pointers']:
        path = root / pointer['source_path']
        template = routes['placements']['pointer_templates'][pointer['template_id']]
        body = template.format(
            core=os.path.relpath(root / 'runtime/CORE.md', path.parent),
            prose=os.path.relpath(root / 'runtime/PROSE.md', path.parent),
            operations=os.path.relpath(root / 'registry/operations.json', path.parent),
            index=os.path.relpath(root / 'docs/ai/compiled_ai_skills.md', path.parent))
        path.write_text(body, encoding='utf-8')
    for owner in sorted({o['owner_skill'] for o in routes['operations']}):
        path = root / routes['resources'][owner]['source_path']
        body = path.read_text(encoding='utf-8')
        body = re.sub(r'\n*<!-- BEGIN GENERATED REVIEW PLANS -->.*?<!-- END GENERATED REVIEW PLANS -->', '', body, flags=re.S)
        entry_pattern = r'<!-- BEGIN GENERATED ENTRY -->.*?<!-- END GENERATED ENTRY -->'
        if re.search(entry_pattern, body, re.S):
            body = re.sub(entry_pattern, lambda _: transform_entry_references(routes, owner, NATIVE_ENTRY_CONTRACT, 'source'), body, flags=re.S)
        block = generated_mode_block(routes, owner)
        body = replace_generated_section(body, 'Registered operations', block, 'MODES')
        if owner == 'econ-review':
            body = re.sub(r'^Mode `assess`.*?\n\n', '', body, flags=re.M)
        path.write_text(body, encoding='utf-8')
    modes = [op['mode'] for op in routes['operations'] if op['owner_skill'] == 'econ-writing']
    ui = 'interface:\n  display_name: "Economics Writing"\n  short_description: "Write, explain and revise natural academic prose"\n  default_prompt: "Use $econ-writing in ' + ', '.join(modes) + ' mode. Read CORE, PROSE and the selected mode; build the explanation before shortening and complete the integrated review."\npolicy:\n  allow_implicit_invocation: true\n'
    (root / 'skills/econ-writing/agents/openai.yaml').write_text(ui, encoding='utf-8')
    return routes
