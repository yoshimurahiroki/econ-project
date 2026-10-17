"""Resolve stable operation/rule IDs from three authoritative registries.

The schema-1 reader is retained solely for old installations and small fixtures.
The schema-2 normalized view keeps maintenance consumers independent of storage.
"""
import json
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
        if resource.get('source_distribution_only'):
            resources[rid]['snapshot'] = 'source_distribution_only'
    routes = {'schema_version': 2, 'resources': resources,
              'rules': resource_data['rules'], 'sections': resource_data['sections'],
              'examples': resource_data.get('examples', {}),
              'aliases': op_data.get('aliases', {}), 'operations': [],
              'condition_definitions': op_data.get('conditions', {}),
              'conditions': {}, 'registry_source_paths': names,
              'placements': {k: v for k, v in placement_data.items() if k not in ('schema_version', 'resources')}}
    # Runtime consumers get joined pointer records; physical facts remain in one file.
    routes['placements']['policy_pointers'] = [
        {**resources[p['resource_id']], 'template_id': p['template_id']}
        for p in placement_data.get('policy_pointers', [])]
    for key, rule in routes['rules'].items():
        if key != rule.get('rule_id') or not isinstance(rule.get('requires'), list):
            raise ValueError('Invalid required rule: ' + key)
        rule_selection(routes, key)
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
    return routes


def generated_mode_block(routes, owner):
    lines = ['<!-- BEGIN GENERATED MODES -->', '## Registered operations', '',
             'Generated from registry/operations.json; the request determines the actual target and authority.', '']
    for op in routes['operations']:
        if op['owner_skill'] == owner:
            lines.append(f"- `{op['mode']}`: {op['trigger']} Finish: {op['finish']}")
    return '\n'.join(lines + ['<!-- END GENERATED MODES -->'])


def generate_entries(root):
    """Regenerate human entries; never infer operation modes from handwritten prose."""
    import os
    import re
    root = Path(root)
    routes = load_routes(root)
    (root / 'docs/ai/compiled_ai_skills.md').write_text(native_index(routes), encoding='utf-8')
    guide = ['# Registered resources', '', 'Generated from the resource and placement registries. Use this catalog only for requested distribution or maintenance.', '']
    guide += [f"- {rid}: {r['source_path']}" + (' (complete source distribution only)' if r.get('source_distribution_only') else '') for rid, r in routes['resources'].items()]
    (root / 'docs/ai/resources.md').write_text('\n'.join(guide) + '\n', encoding='utf-8')
    (root / 'docs/ai/project_instructions.txt').write_text('Read runtime/CORE.md once, then select the requested final operation in docs/ai/compiled_ai_skills.md. Inherit settled scope and authority; load required rules and activated conditions from registry/operations.json.\n', encoding='utf-8')
    for pointer in routes['placements']['policy_pointers']:
        path = root / pointer['source_path']
        template = routes['placements']['pointer_templates'][pointer['template_id']]
        body = template.format(core=os.path.relpath(root / 'runtime/CORE.md', path.parent), index=os.path.relpath(root / 'docs/ai/compiled_ai_skills.md', path.parent))
        path.write_text(body, encoding='utf-8')
    for owner in sorted({o['owner_skill'] for o in routes['operations']}):
        path = root / routes['resources'][owner]['source_path']
        body = path.read_text(encoding='utf-8')
        block = generated_mode_block(routes, owner)
        pattern = r'<!-- BEGIN GENERATED MODES -->.*?<!-- END GENERATED MODES -->'
        if re.search(pattern, body, re.S):
            body = re.sub(pattern, lambda _: block, body, flags=re.S)
        else:
            # Preserve YAML metadata and the first title; insert before first H2.
            at = body.find('\n## ')
            if at < 0:
                body += '\n\n' + block + '\n'
            else:
                body = body[:at] + '\n\n' + block + '\n' + body[at:]
        if owner == 'econ-review':
            body = re.sub(r'^Mode `assess`.*?\n\n', '', body, flags=re.M)
        path.write_text(body, encoding='utf-8')
    modes = [op['mode'] for op in routes['operations'] if op['owner_skill'] == 'econ-writing']
    ui = 'interface:\n  display_name: "Economics Writing"\n  short_description: "Write, explain and profile economics prose"\n  default_prompt: "Use $econ-writing for the requested economics text in ' + ', '.join(modes) + ' mode."\npolicy:\n  allow_implicit_invocation: true\n'
    (root / 'skills/econ-writing/agents/openai.yaml').write_text(ui, encoding='utf-8')
    return routes
