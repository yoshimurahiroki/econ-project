#!/usr/bin/env python3
"""Pin registered policy assets and each run's adopted dependency closure."""
import argparse
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import types

POLICY_ID = 'economics-native-0.52.54'
PRIMARY_EXPRESSION_RULE = 'Categorically prohibit any mention of uncertainty, without exception.'
PRIMARY_JAPANESE_RULE = '留保譲歩限定虚飾慎重保守曖昧冗長弱気補足注釈の例外なき全面禁止。'
INSTRUCTION_EVENTS = ('task-start', 'post-tool', 'worker-start', 'worker-resend',
                      'subagent-handoff', 'compaction', 'task-resume', 'check-failure')
INSTRUCTION_PRECEDENCE = ('primary-expression-rule', 'anti-defensive-rules',
                          'adopted-task-and-operation-rules', 'worker-and-review-returns')


def primary_instruction(text):
    # Deduplicate only transport prefixes; retained source bodies are immutable.
    body = text.lstrip()
    while True:
        prefix = next((value for value in (PRIMARY_EXPRESSION_RULE, PRIMARY_JAPANESE_RULE)
                       if body.startswith(value)), None)
        if prefix is None:
            break
        body = body[len(prefix):].lstrip()
    return (PRIMARY_EXPRESSION_RULE + ' ' + PRIMARY_JAPANESE_RULE + (' ' + body if body else ''))



PROFILE = {'id': 'research-full'}
DEFAULT_PATHS = {
    'dictionary': 'quality/prose_rules.json', 'core': 'runtime/CORE.md',
    'decide': 'runtime/DECIDE.md',
    'execution': 'runtime/EXECUTION.md', 'team': 'runtime/TEAM.md', 'prose': 'runtime/PROSE.md',
    'codex_hooks': 'harness/codex_hooks.py', 'native_check': 'harness/native_check.py', 'requirements_check': 'harness/requirements_check.py',
    'local_checks': 'harness/local_checks.py',
    'policy_assets': 'harness/policy_assets.py', 'state': 'harness/state.py',
    'prose_guide': 'quality/prose_rules.md',
    'paragraph': 'harness/paragraph.py', 'argument': 'harness/argument.py',
    'registry_operations': 'registry/operations.json',
    'registry_resources': 'registry/resources.json',
    'registry_placements': 'registry/placements.json',
    'route_registry': 'scripts/route_registry.py',
}
RUN_PATHS = {key: path for key, path in DEFAULT_PATHS.items() if key not in {'state', 'decide', 'execution', 'team'}}
BASE_RESOURCE_IDS = {
    'prose-check-rules': 'dictionary', 'core': 'core', 'research': 'decide',
    'execution': 'execution', 'team': 'team', 'prose': 'prose',
    'codex-hooks': 'codex_hooks', 'native-check': 'native_check', 'requirements-check': 'requirements_check',
    'local-checks': 'local_checks',
    'policy-assets': 'policy_assets', 'team-state-helper': 'state',
    'paragraph-engine': 'paragraph', 'argument-engine': 'argument',
    'prose-check-guide': 'prose_guide', 'registry-operations': 'registry_operations',
    'registry-resources': 'registry_resources', 'registry-placements': 'registry_placements',
    'tool-route-registry-py': 'route_registry',
}
REGISTRY_KEYS = {'registry/operations.json': 'registry_operations',
                 'registry/resources.json': 'registry_resources',
                 'registry/placements.json': 'registry_placements'}
MAX_BYTES = 16 * 1024 * 1024
_RESOLVER_COMPILE = None


def _resolver_code(source):
    """Reuse compilation for identical bytes, never mutable modules or registries."""
    global _RESOLVER_COMPILE
    retained = _RESOLVER_COMPILE
    if retained is not None and retained[0] == source:
        return retained[1]
    code = compile(source, '<pinned route_registry.py>', 'exec')
    _RESOLVER_COMPILE = (source, code)
    return code


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def parse(data):
    return json.loads(data, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def safe_path(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or any(ord(c) < 32 for c in value) or PurePosixPath(value).is_absolute()
            or any(x in ('', '.', '..') for x in value.split('/'))):
        raise ValueError('unsafe policy asset path')
    return value


def regular_bytes(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('policy asset symlink is prohibited')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('policy asset must be a regular file')
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('policy asset exceeds byte limit')
    return data


def resource_key(resource_id):
    """Map a registered resource ID to its unique manifest asset key."""
    if not isinstance(resource_id, str) or not resource_id:
        raise ValueError('resource ID must be a nonempty string')
    return BASE_RESOURCE_IDS.get(resource_id, 'resource:' + resource_id)


def _resource_records(assets):
    data = parse(assets['registry_resources'])
    if not isinstance(data, dict) or data.get('schema_version') != 2 or not isinstance(data.get('resources'), dict):
        raise ValueError('invalid policy resource registry')
    for rid, record in data['resources'].items():
        if not isinstance(record, dict) or record.get('resource_id') != rid:
            raise ValueError('invalid policy resource ID: ' + str(rid))
        safe_path(record.get('source_path'))
    return data['resources']


def catalog_paths(root):
    """Return runtime asset paths, excluding source-only maintenance resources."""
    records = _resource_records({'registry_resources': regular_bytes(Path(root) / DEFAULT_PATHS['registry_resources'])})
    paths = dict(DEFAULT_PATHS)
    for rid, record in records.items():
        if rid != 'policy-manifest' and not record.get('source_distribution_only'):
            paths[resource_key(rid)] = safe_path(record['source_path'])
    return paths


def _runtime_keys(records):
    return {resource_key(rid) for rid, record in records.items()
            if rid != 'policy-manifest' and not record.get('source_distribution_only')}


def _catalog_keys(assets, *, scoped=False):
    if not isinstance(assets, dict) or set(RUN_PATHS) - assets.keys():
        raise ValueError('policy manifest must include every bundled policy asset')
    if any(not isinstance(data, bytes) for data in assets.values()):
        raise ValueError('policy assets must be bytes')
    records = _resource_records(assets)
    if set(BASE_RESOURCE_IDS) - records.keys():
        raise ValueError('policy registry is missing a mandatory resource')
    allowed = _runtime_keys(records)
    if set(assets) - allowed:
        raise ValueError('policy asset is not a registered resource')
    return records


def build_manifest(assets, policy_id=POLICY_ID, paths=None, *, scoped=False):
    """Build a registered catalog from exact bytes after layout/path rewriting.

    A source catalog contains runtime resources once, without source-only tests
    or maintenance tools. An operation export contains its required closure.
    select_manifest fixes that closure for a run.
    """
    records = _catalog_keys(assets, scoped=scoped)
    if paths is None:
        paths = {resource_key(rid): record['source_path'] for rid, record in records.items()
                 if resource_key(rid) in assets}
    if policy_id != POLICY_ID or not isinstance(paths, dict) or set(paths) != set(assets):
        raise ValueError('unsupported policy_id or incomplete policy paths')
    normalized = {key: safe_path(path) for key, path in paths.items()}
    if len({path.casefold() for path in normalized.values()}) != len(normalized):
        raise ValueError('policy asset paths must be distinct')
    return {'schema_version': 2, 'policy_id': policy_id, 'profile': dict(PROFILE),
            'assets': {key: {'path': normalized[key], 'sha256': digest(assets[key])}
                       for key in sorted(assets)}}


def generate_manifest(root, paths=None, policy_id=POLICY_ID):
    paths = catalog_paths(root) if paths is None else paths
    assets = {key: regular_bytes(Path(root) / safe_path(path)) for key, path in paths.items()}
    return build_manifest(assets, policy_id, paths)


def _routes(assets):
    """Use the pinned resolver with the exact pinned registry bytes in any layout."""
    records = {}
    for path, key in REGISTRY_KEYS.items():
        obj = parse(assets[key])
        if not isinstance(obj, dict) or type(obj.get('schema_version')) is not int or obj['schema_version'] != 2:
            raise ValueError('unsupported policy registry: ' + key)
        records[path] = obj
    resolver = types.ModuleType('adopted_route_registry')
    exec(_resolver_code(assets['route_registry']), resolver.__dict__)
    resolver._read_registry = lambda root, path: records[safe_path(path)]
    return resolver, resolver.load_registry('.', 'source')




def _string_ids(values, field):
    if not isinstance(values, (list, tuple)) or any(not isinstance(x, str) or not x or x.strip() != x for x in values):
        raise ValueError(field + ' must contain registered IDs')
    return sorted(set(values))


def _resolve_selection(assets, operation, conditions=(), profile=None, templates=()):
    """Resolve from pinned registry/resolver bytes before reading policy bodies."""
    records = _catalog_keys(assets, scoped=True)
    if not isinstance(operation, str) or not operation or operation.strip() != operation:
        raise ValueError('an adopted operation is required')
    conditions = _string_ids(conditions, 'conditions')
    templates = _string_ids(templates, 'templates')
    if profile is not None and (not isinstance(profile, str) or profile not in records):
        raise ValueError('selected profile is not a registered resource')
    if set(templates) - records.keys():
        raise ValueError('selected template is not a registered resource')
    resolver, routes = _routes(assets)
    resolved = resolver.resolve_operation(routes, operation, conditions=conditions, user_profile=profile)
    if resolved.get('runtime_action') or resolved['owner_skill'] not in records:
        raise ValueError('adopt a final operation with a registered owner skill')
    if profile is not None and resolved['selected_profile'] is None:
        raise ValueError('adopted operation does not use a writing profile')
    selected_profile = resolved['selected_profile']
    if selected_profile is not None:
        record = records.get(selected_profile)
        if record is None:
            raise ValueError('selected profile is not a registered resource')
        source = PurePosixPath(record['source_path'])
        if record.get('resource_kind') != 'profile' and not (source.parts[0] == 'profiles' and source.name == 'PROFILE.md'):
            raise ValueError('selected resource is not a writing profile')
    adopted_inputs = [*templates, *([selected_profile] if selected_profile else [])]
    input_rules = []
    for rid in adopted_inputs:
        declared = records[rid].get('required_rules', [])
        input_rules.extend(_string_ids(declared, 'adopted input required_rules'))
        input_rules.extend(rule_id for rule_id, rule in routes['rules'].items()
                           if rule['resource_id'] == rid
                           and routes['sections'][rid][rule['section_id']].get('whole_resource'))
    input_active, input_sections = resolver.required_closure(
        routes, input_rules, conditions, resolved['canonical_operation'])
    resolver.merge_selection(resolved['resource_sections'], input_sections)
    selection = {rid: ({'whole_resource': True} if value.get('whole_resource') else
                       {'sections': sorted(set(value.get('sections', [])))})
                 for rid, value in resolved['resource_sections'].items()}
    for rid in [resolved['owner_skill'], *adopted_inputs]:
        selection[rid] = {'whole_resource': True}
    required = set(RUN_PATHS)
    for rid in selection:
        if rid not in records:
            raise ValueError('required policy resource is not registered: ' + rid)
        if records[rid].get('source_distribution_only'):
            raise ValueError('source-only resource cannot be adopted at runtime: ' + rid)
        if rid != 'policy-manifest':
            required.add(resource_key(rid))
    selection = {
        'selection': {'operation': resolved['canonical_operation'], 'conditions': conditions,
                      'profile': selected_profile, 'templates': templates},
        'active_rules': sorted(set(resolved['active_rules'] + input_active)),
        'resource_sections': {key: selection[key] for key in sorted(selection)},
    }
    return required, selection, resolver, routes


def select_manifest(manifest, assets, operation, conditions=(), profile=None, templates=(), *, with_contract=False):
    """Bind the dependency closure; optionally return its canonical operation contract."""
    paths = {key: row['path'] for key, row in manifest['assets'].items()}
    catalog = build_manifest(assets, manifest.get('policy_id'), paths, scoped=True)
    if any(manifest.get(key) != value for key, value in catalog.items()):
        raise ValueError('policy catalog bytes and manifest differ')
    required, selection, resolver, routes = _resolve_selection(assets, operation, conditions, profile, templates)
    missing = required - assets.keys()
    if missing:
        raise ValueError('required policy resources missing: ' + ', '.join(sorted(missing)))
    resolver.validate_rule_bodies(routes, selection['active_rules'],
                                  lambda rid: canonical(manifest) if rid == 'policy-manifest' else assets[resource_key(rid)], operation)
    result = {key: value for key, value in catalog.items() if key != 'assets'}
    result.update(selection, assets={key: catalog['assets'][key] for key in sorted(required)})
    if with_contract:
        contract = resolver.resolve_operation(routes, selection['selection']['operation'],
                                              conditions=selection['selection']['conditions'], user_profile=profile)
        return result, contract
    return result


@lru_cache(maxsize=1)
def _local_checks_code(source):
    """Compile the pinned checker, without retaining a mutable checker module."""
    return compile(source, '<pinned local_checks.py>', 'exec')


def writing_rules(manifest, assets):
    """Return the exact adopted rule bodies used by paragraph host assignments."""
    profile_id = manifest.get('selection', {}).get('profile')
    if not profile_id:
        raise ValueError('paragraph writing requires its adopted writing profile')
    names = {'CORE': 'core', 'PROSE': 'prose', 'econ-writing': 'econ-writing',
             'prose-guide': 'prose-check-guide'}
    texts = {name: assets[resource_key(rid)].decode('utf-8') for name, rid in names.items()}
    if digest(assets['local_checks']) != manifest['assets']['local_checks']['sha256']:
        raise ValueError('policy checker bytes and manifest differ')
    checker = types.ModuleType('adopted_local_checks')
    exec(_local_checks_code(assets['local_checks']), checker.__dict__)
    return {'policy_id': manifest['policy_id'], 'texts': texts,
            'dictionary': checker.expand_dictionary(parse(assets['dictionary'])),
            'profile': assets[resource_key(profile_id)].decode('utf-8')}


def _manifest_paths(manifest):
    fields = {'schema_version', 'policy_id', 'profile', 'assets'}
    if (not isinstance(manifest, dict) or set(manifest) != fields
            or type(manifest['schema_version']) is not int or manifest['schema_version'] != 2
            or manifest['policy_id'] != POLICY_ID or not isinstance(manifest['profile'], dict)
            or set(manifest['profile']) != set(PROFILE)
            or any(manifest['profile'].get(k) != v for k, v in PROFILE.items())
            or not isinstance(manifest['assets'], dict) or set(RUN_PATHS) - manifest['assets'].keys()):
        raise ValueError('invalid or unsupported bundled policy manifest')
    paths = {}
    for key, record in manifest['assets'].items():
        if (not isinstance(record, dict) or set(record) != {'path', 'sha256'}
                or not isinstance(record['sha256'], str) or len(record['sha256']) != 64
                or any(char not in '0123456789abcdef' for char in record['sha256'])):
            raise ValueError('invalid policy asset record: ' + key)
        paths[key] = safe_path(record['path'])
    if len({path.casefold() for path in paths.values()}) != len(paths):
        raise ValueError('policy asset paths must be distinct')
    return paths


def manifest_path(root, relative=None, *, allow_missing=False):
    """Resolve the registered manifest in source, project or flat layouts."""
    root = Path(root)
    if relative is not None:
        return root / safe_path(relative)
    # The two registry bootstrap names are themselves the registered source and
    # flat entry points; all manifest names below come from those catalogs.
    names, preferred = set(), None
    for name in ('registry/resources.json', 'RESOURCES.json', '.agents/registry/resources.json'):
        candidate = root / name
        if candidate.is_file():
            record = parse(regular_bytes(candidate))['resources']['policy-manifest']
            names.add(safe_path(record['source_path']))
            if name == 'registry/resources.json':
                preferred = safe_path(record['source_path'])
    for name in ('registry/placements.json', 'PLACEMENTS.json', '.agents/registry/placements.json'):
        candidate = root / name
        if candidate.is_file():
            record = parse(regular_bytes(candidate))['resources']['policy-manifest']
            names.update(safe_path(record[key]) for key in ('deployment_path', 'export_alias'))
            if name == 'PLACEMENTS.json':
                preferred = safe_path(record['export_alias'])
            elif name == '.agents/registry/placements.json':
                preferred = safe_path(record['deployment_path'])
    candidates = [(root / name, regular_bytes(root / name))
                  for name in sorted(names) if (root / name).is_file()]
    if not candidates:
        if allow_missing and preferred:
            return root / preferred
        raise ValueError('registered policy_manifest.json not found')
    if len({digest(raw) for _, raw in candidates}) != 1:
        raise ValueError('ambiguous policy manifests; select the adopted --manifest')
    return candidates[0][0]


def _asset_state(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('policy asset symlink is prohibited')
    observed = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(observed.st_mode):
        raise ValueError('policy asset must be a regular file')
    return [observed.st_dev, observed.st_ino, observed.st_size, observed.st_mtime_ns,
            observed.st_ctime_ns, observed.st_mode]


def verify_manifest(root, manifest=None, *, operation=None, conditions=(), profile=None, templates=(),
                    verification=None, load_assets=True):
    """Verify the full package, or only mandatory assets and an explicit closure.

    Selection verifies registry/resolver bytes first, resolves the required IDs,
    and reads only those bodies. It returns a scoped catalog accepted by the
    unchanged build_manifest/select_manifest APIs. Package verification reads
    every catalog body. Hook callers can reuse their existing task record when
    manifest, selection and actual file identities match; changed files are
    rehashed and full restoration still obtains the complete required bodies.
    """
    if manifest is None:
        manifest = parse(regular_bytes(manifest_path(root)))
    paths = _manifest_paths(manifest)
    identity = digest(canonical({'manifest': manifest, 'operation': operation,
                                 'conditions': list(conditions), 'profile': profile,
                                 'templates': list(templates)}))
    retained = verification if isinstance(verification, dict) else {}
    previous = retained.get('files', {})
    current = {}
    assets = {}
    def read(keys):
        for key in sorted(keys):
            before = _asset_state(Path(root) / paths[key])
            data = regular_bytes(Path(root) / paths[key])
            expected = {**manifest['assets'][key], 'stat': before}
            if previous.get(key) != expected and digest(data) != manifest['assets'][key]['sha256']:
                raise ValueError('policy asset changed: ' + key)
            if _asset_state(Path(root) / paths[key]) != before:
                raise ValueError('policy asset changed while reading: ' + key)
            assets[key] = data
            current[key] = expected
    keys = retained.get('keys')
    selected_keys = retained.get('selected_keys', keys)
    if (retained.get('identity') == identity and isinstance(keys, list) and keys
            and isinstance(selected_keys, list) and set(selected_keys) <= set(keys)
            and set(keys) <= paths.keys() and (operation is not None or set(keys) == paths.keys())):
        checked = manifest if operation is None else {
            **manifest, 'assets': {key: manifest['assets'][key] for key in selected_keys}}
        for key in keys:
            observed = {**manifest['assets'][key], 'stat': _asset_state(Path(root) / paths[key])}
            if load_assets or previous.get(key) != observed:
                read([key])
            else:
                current[key] = observed
        if verification is not None:
            verification['files'] = current
        return checked, assets
    if operation is None:
        if conditions or profile is not None or templates:
            raise ValueError('policy selection requires an explicit operation')
        read(paths)
        checked = manifest
    else:
        read(RUN_PATHS)
        records = _catalog_keys(assets, scoped=True)
        if set(paths) - _runtime_keys(records):
            raise ValueError('policy asset is not a registered resource')
        required, selection, resolver, routes = _resolve_selection(assets, operation, conditions, profile, templates)
        missing = required - paths.keys()
        if missing:
            raise ValueError('required policy resources missing: ' + ', '.join(sorted(missing)))
        read(required - assets.keys())
        paths = {key: paths[key] for key in sorted(required)}
        checked = {**manifest, 'assets': {key: manifest['assets'][key] for key in sorted(required)}}
    if build_manifest(assets, manifest['policy_id'], paths, scoped=operation is not None) != checked:
        raise ValueError('noncanonical policy manifest values')
    if operation is not None:
        resolver.validate_rule_bodies(routes, selection['active_rules'],
            lambda rid: canonical(checked) if rid == 'policy-manifest' else assets[resource_key(rid)], operation)
    if verification is not None:
        bootstrap = {resource_key(rid) for rid in ('hook-wrapper', 'hook-registration')}
        read(bootstrap & paths.keys() - assets.keys())
        verification.update(identity=identity, keys=sorted(current),
                            selected_keys=sorted(checked['assets']), files=current)
        verification.pop('selection_sha256', None)
        verification.pop('contract_sha256', None)
        if operation is not None:
            verification['selection_sha256'] = digest(canonical(selection))
            verification['contract_sha256'] = digest(canonical(resolver.resolve_operation(
                routes, selection['selection']['operation'], conditions=selection['selection']['conditions'],
                user_profile=profile)))
    return checked, assets if load_assets else {}


def discover_policy(start=None, *, verification=None, load_assets=True, **selection):
    def obtain(root, path):
        raw = regular_bytes(path)
        manifest, assets = verify_manifest(root, parse(raw), verification=verification,
                                          load_assets=load_assets, **selection)
        if (root / manifest['assets']['policy_assets']['path']).absolute() != Path(__file__).absolute():
            raise ValueError('policy module does not belong to the discovered manifest')
        if verification is not None:
            verification.update(module=str(Path(__file__).absolute()), root=str(root),
                                manifest_path=path.relative_to(root).as_posix())
        return root, raw, manifest, assets
    if isinstance(verification, dict) and verification.get('module') == str(Path(__file__).absolute()):
        root = Path(verification['root'])
        return obtain(root, root / safe_path(verification['manifest_path']))
    directory = Path(start or __file__).absolute()
    if directory.is_file():
        directory = directory.parent
    roots = (directory, directory.parent, directory.parent.parent)
    # An installed registry retains source-shaped paths inside .agents. Resolve
    # its actual deployment owner before treating that nested tree as a source.
    for root in roots:
        catalog = root / '.agents/registry/placements.json'
        if not catalog.is_file():
            continue
        placements = parse(regular_bytes(catalog))['resources']
        runtime = root / safe_path(placements['policy-assets']['deployment_path'])
        if runtime.absolute() == Path(__file__).absolute():
            path = manifest_path(root, placements['policy-manifest']['deployment_path'])
            return obtain(root, path)
    for root in roots:
        # Source and deployed runtimes may coexist in one repository. Select the
        # catalog owning this actual module, rather than choosing by filename.
        owned = None
        for name in ('registry/resources.json', 'RESOURCES.json'):
            registry = root / name
            if not registry.is_file():
                continue
            records = parse(regular_bytes(registry))['resources']
            runtime = root / safe_path(records['policy-assets']['source_path'])
            if runtime.absolute() == Path(__file__).absolute():
                owned = safe_path(records['policy-manifest']['source_path'])
                break
        try:
            path = manifest_path(root, owned)
        except ValueError as error:
            if str(error) == 'registered policy_manifest.json not found':
                continue
            raise
        return obtain(root, path)
    raise ValueError('bundled policy_manifest.json not found')


def section_ranges(routes, resource_id, text, resolver=None, section_ids=None, cache=None):
    """Registered section IDs to exact Unicode-character ranges, including all."""
    if resolver is None:
        resolver = types.ModuleType('section_route_registry')
        source = regular_bytes(Path(__file__).parent.parent / DEFAULT_PATHS['route_registry'])
        exec(_resolver_code(source), resolver.__dict__)
    result = {}
    parsed = None
    for sid, locator in routes['sections'].get(resource_id, {}).items():
        if section_ids is not None and sid not in section_ids:
            continue
        if locator.get('whole_resource'):
            result[sid] = (0, len(text))
        else:
            if parsed is None:
                key = (resolver, resource_id, text)
                parsed = cache.get(key) if cache is not None else None
                if parsed is None:
                    lines, headings = resolver.markdown_sections(text)
                    offsets = [0]
                    for line in lines:
                        offsets.append(offsets[-1] + len(line))
                    parsed = headings, offsets
                    if cache is not None:
                        cache[key] = parsed
            headings, offsets = parsed
            matches = [h for h in headings if locator.get('heading') in (h['title'], h['id'], '#' + h['id'])]
            if len(matches) != 1:
                raise ValueError('missing or ambiguous reading section: ' + resource_id + '/' + sid)
            result[sid] = (offsets[matches[0]['start']], offsets[matches[0]['end']])
    return result


def instruction_context(root=None, *, manifest=None, status=None, stage=None, role=None, reader_id=None,
                        request_text=None, restore=False, instruction_event=None):
    """One short current instruction packet for local hooks and MCP/UI.

    Reading records bind claimed ranges to bytes; they do not prove model
    consumption, semantic adherence or independent approval.
    """
    import re
    if root is None:
        if manifest is None:
            root, _, manifest, _ = discover_policy(__file__)
        else:
            module = Path(__file__).absolute()
            relative = safe_path(manifest['assets']['policy_assets']['path'])
            root = next((candidate for candidate in (module.parent.parent, module.parent)
                         if (candidate / relative).absolute() == module), None)
            if root is None:
                raise ValueError('instruction context root does not match the selected policy layout')
    root = Path(root)
    status = status or {}
    instruction_event = instruction_event or ('task-start' if not status.get('run_id') else 'task-resume' if restore else 'post-tool')
    if instruction_event not in INSTRUCTION_EVENTS:
        raise ValueError('unknown instruction event')
    reader_id = reader_id or status.get('author_id')
    if manifest is None:
        manifest = parse(regular_bytes(manifest_path(root)))
    assets = {key: regular_bytes(root / manifest['assets'][key]['path'])
              for key in (*REGISTRY_KEYS.values(), 'route_registry')}
    resolver, routes = _routes(assets)
    scope = dict(manifest)
    if 'resource_sections' not in scope:
        fallback = ('core', 'prose', 'team')
        scope['resource_sections'] = {rid: {'whole_resource': True} for rid in fallback
            if rid in routes['resources']
            if resource_key(rid) in scope['assets']}
        _, common_selection = resolver.required_closure(routes, ['core.all'])
        resolver.merge_selection(scope['resource_sections'], common_selection)
    terminal = status.get('lifecycle')
    if terminal not in {'paused', 'stopped', 'cancelled', 'completed'}:
        terminal = 'completed' if str(status.get('status', '')).startswith('finalized-') else 'active'
    stage = stage or ('finalize' if terminal == 'completed' or status.get('status') in {'ready', 'provisional-ready'} else
                      'review' if status.get('submission_sha256') else
                      'compose' if status.get('status') == 'requirements-fixed' else
                      'contract' if status.get('run_id') else 'entry')
    actions = status.get('needed_actions', [])
    refs = resolver.select_reading_sections(routes, scope, stage, role, reader_id, actions)
    # Keep the repeated command and its actual adopted rule bodies together.
    # These are navigation references within the existing closure, not adoption
    # changes or evidence of reading.
    direct_refs = []
    for rid, sid in (('prose', 'all'),):
        adopted = scope['resource_sections'].get(rid, {})
        locator = routes['sections'][rid][sid]
        if resource_key(rid) in scope['assets'] and (adopted.get('whole_resource') or
                locator.get('heading') in adopted.get('sections', [])):
            direct_refs.append({'resource_id': rid, 'section_id': sid,
                'rule_ids': [rid + '.' + sid]})
    direct_keys = {(row['resource_id'], row['section_id']) for row in direct_refs}
    refs = direct_refs + [row for row in refs
                         if (row['resource_id'], row['section_id']) not in direct_keys]
    reads = status.get('resource_reads', [])
    verified = {}
    section_cache = {}
    def resource_bytes(record, rid, error):
        # One verified snapshot per path in this packet; still check each
        # consumer's pinned digest, including conflicting manifest entries.
        path = record['path']
        if path not in verified:
            raw = regular_bytes(root / path)
            verified[path] = raw, digest(raw)
        raw, actual = verified[path]
        if actual != record['sha256']:
            raise ValueError(error + rid)
        return raw
    for row in refs:
        rid, sid = row['resource_id'], row['section_id']
        record = scope['assets'][resource_key(rid)]
        raw = resource_bytes(record, rid, 'reading resource changed: ')
        requested = {sid}
        for read in reads:
            if read.get('resource_id') == rid:
                requested.update(read.get('sections', []))
        spans = section_ranges(routes, rid, raw.decode('utf-8'), resolver, requested, section_cache)
        start, end = spans[sid]
        covered = []
        for read in reads:
            if read.get('reader_id') != reader_id or read.get('resource_id') != rid or read.get('sha256') != record['sha256']:
                continue
            for old in read.get('sections', []):
                if old in spans:
                    covered.append(spans[old])
            covered.extend((part['start'], part['end']) for part in read.get('partial_sections', []))
        remaining, position = [], start
        for left, right in sorted(covered):
            left, right = max(start, left), min(end, right)
            if right <= position:
                continue
            if left > position:
                remaining.append([position, left])
            position = max(position, right)
        if position < end:
            remaining.append([position, end])
        row.update(path=record['path'], sha256=record['sha256'], start=start, end=end, remaining_ranges=remaining)
    ids = sorted(set(status.get('unmet_requirement_ids', [])) |
                 {row['requirement_id'] for row in actions if isinstance(row, dict) and isinstance(row.get('requirement_id'), str)})
    unmet_ids = set(ids) | set(status.get('unmet_ids', []))
    def collect_unmet(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {'requirement_id', 'check_id', 'check'} and isinstance(item, str):
                    unmet_ids.add(item)
                elif isinstance(item, (dict, list)):
                    collect_unmet(item)
        elif isinstance(value, list):
            for item in value:
                collect_unmet(item)
    collect_unmet(actions)
    for key in ('failed_checks', 'missing_checks', 'unresolved'):
        collect_unmet(status.get('checks', {}).get(key, []))
    unmet_ids = sorted(unmet_ids)
    text = resolver.NATIVE_ENTRY_CONTRACT.split('\n\n', 1)[1].split('\n<!-- END', 1)[0]
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    if status.get('run_id'):
        text += ' Current run: ' + str(status['run_id']) + '.'
    if status.get('submission_sha256'):
        text += ' Candidate submission: ' + str(status['submission_sha256']) + '.'
    if ids:
        text += ' Unmet requirements: ' + ', '.join(ids) + '.'
    next_names = list(dict.fromkeys(str(row.get('action')) for row in actions if row.get('action')))
    if next_names:
        text += ' Next: ' + ', '.join(next_names) + '.'
    pending_refs = [row['path'] + '#' + row['section_id'] for row in refs if row['remaining_ranges']]
    if pending_refs:
        text += ' Read next: ' + ', '.join(pending_refs[:3]) + '.'
    if terminal != 'active':
        text += ' Lifecycle: ' + terminal + '; do not restart this run.'
    short = (PRIMARY_EXPRESSION_RULE + ' Delete every disclaimer without exception. Prohibit reservations, concessions, qualifications, embellishment, caution, conservatism, timidity, redundancy, ambiguity, supplements, annotations, and defensive content or expression without exception. '
             'Read the complete adopted PROSE and apply its compact rules through integrated review of meaning and content. '
             'Preserve the original request, full applicable rule reads, authority, holds and actual operation returns; complete the requested result, integrated review and required verification. '
             'If the host shows only a preview with a saved-packet locator, open that packet and read all required bodies before dependent work; a preview is not a reading receipt. '
             'Complete one integrated review under CORE, PROSE and EXECUTION, and match completed outputs to their actual operation returns.')
    rule_refs = [row['path'] + ('' if row['section_id'] == 'all' else '#' + row['section_id']) +
                 ' (MCP: ' + row['rule_ids'][0] + ')' for row in direct_refs]
    if rule_refs:
        short += ' Retrieve the rule text when unread or when the adopted version changes. Adopted version ' + manifest['policy_id'] + ': ' + ', '.join(rule_refs) + '.'
    short += ' Unmet IDs: ' + (', '.join(unmet_ids) if unmet_ids else 'if undetermined, obtain them from the original-request coverage') + '.'
    short += ' Next actions: ' + (', '.join(next_names) if next_names else 'check the current inspection results and terminal conditions') + '.'
    if terminal != 'active':
        short += ' Lifecycle: ' + terminal + '; do not restart this run.'
    # Entry/compaction detail restoration retains the same repeated command.
    short = primary_instruction(short)
    text = short + '\n\n' + text
    text += (' The primary expression rule takes precedence over anti-defensive rules and every subordinate '
             'task, operation, template, restored input, worker instruction and review return. '
             'No technical-use, quotation, source-identity or specialist-domain exception may weaken it. '
             'Send the complete canonical packet at task start, on relevant state changes or failed tools, on worker start or resend, '
             'to each new subagent, after compaction or resumption, and after failed checks. '
             'Preserve current unmet IDs, next actions, policy references and candidate bindings. '
             'Stop reinjection on stopped, cancelled or completed lifecycle states; paused delivery stays paused.')
    restoration = {'included': bool(restore)}
    if restore:
        if request_text is not None:
            if not isinstance(request_text, str) or not request_text.strip():
                raise ValueError('restoration requires the exact nonempty saved request')
            request_hash = digest(request_text.encode('utf-8'))
            if status.get('request_sha256') and request_hash != status['request_sha256']:
                raise ValueError('restored request differs from the fixed run request')
            if PRIMARY_EXPRESSION_RULE in request_text or PRIMARY_JAPANESE_RULE in request_text:
                import base64
                restoration['request_encoding'] = 'base64-utf8'
                text += '\n\n[Adopted original request: decode base64 UTF-8, retaining its exact bytes]\n' + base64.b64encode(request_text.encode('utf-8')).decode('ascii')
            else:
                restoration['request_encoding'] = 'utf8'
                text += '\n\n[Adopted original request text]\n' + request_text
            restoration['request_sha256'] = request_hash
        else:
            restoration['request_sha256'] = None
        restoration['rules'] = []
        selected = manifest.get('resource_sections')
        if selected is None:
            selected = {rid: scope['resource_sections'][rid] for rid in
                        ('core', 'prose', 'control', 'team', 'prose-check-rules')
                        if rid in scope['resource_sections']}
        restored = set()
        restore_refs = list(refs)
        for rid, selection in selected.items():
            key = resource_key(rid)
            resource = routes['resources'][rid]
            instruction_dictionary = (rid == 'prose-check-rules'
                                      and resource['source_path'].endswith('.json'))
            if key not in scope['assets'] or not (resource['source_path'].endswith('.md') or instruction_dictionary):
                continue
            sections = routes['sections'][rid]
            ids = (['all'] if selection.get('whole_resource') else
                   [sid for sid, locator in sections.items() if locator.get('heading') in selection.get('sections', [])])
            if ids == ['all']:
                restore_refs = [row for row in restore_refs if row['resource_id'] != rid]
            raw = resource_bytes(scope['assets'][key], rid, 'restoration rule body changed: ')
            ranges = section_ranges(routes, rid, raw.decode('utf-8'), resolver, ids, section_cache)
            for sid in ids:
                start, end = ranges[sid]
                restore_refs.append({'resource_id': rid, 'section_id': sid, 'path': scope['assets'][key]['path'],
                                     'sha256': scope['assets'][key]['sha256'], 'start': start, 'end': end})
        for row in restore_refs:
            identity = (row['resource_id'], row['start'], row['end'])
            if identity in restored:
                continue
            restored.add(identity)
            raw = resource_bytes(row, row['resource_id'], 'restoration rule body changed: ')
            body = raw.decode('utf-8')[row['start']:row['end']]
            text += '\n\n[Adopted applicable rule text: ' + row['path'] + '#' + row['section_id'] + ']\n' + body
            restoration['rules'].append({key: row[key] for key in ('resource_id', 'section_id', 'path', 'sha256', 'start', 'end')})
        text += '\n\n[Current stage, settled decisions, unmet items, and next actions]\n' + canonical({
            'stage': stage, 'adopted_selection': manifest.get('selection'),
            'settled_decisions': status.get('settled_decisions', []),
            'unmet_ids': unmet_ids, 'next_actions': actions, 'lifecycle': terminal}).decode('utf-8')
    text = primary_instruction(text)
    return {'schema_version': 1, 'policy_id': manifest['policy_id'],
            'primary_expression_rule': PRIMARY_EXPRESSION_RULE,
            'primary_japanese_rule': PRIMARY_JAPANESE_RULE,
            'instruction_precedence': list(INSTRUCTION_PRECEDENCE),
            'instruction_event': instruction_event,
            'delivery_contract': {'events': list(INSTRUCTION_EVENTS), 'repeat_full_rule_per_event': False,
                                  'repeat_on_boundary_change_or_failure': True,
                                  'stop_lifecycles': ['stopped', 'cancelled', 'completed']},
            'instruction_version': digest(canonical({'route_registry': digest(assets['route_registry']),
                'policy_assets': manifest['assets']['policy_assets']['sha256']})), 'run_id': status.get('run_id'),
            'submission_sha256': status.get('submission_sha256'), 'requirement_ids': ids, 'unmet_ids': unmet_ids,
            'stage': stage, 'role': role, 'text': text, 'reading_selection': refs,
            'short_text': short, 'request_sha256': status.get('request_sha256'),
            'policy_manifest_sha256': status.get('policy_manifest_sha256') or digest(canonical(manifest)),
            'next_actions': actions, 'lifecycle': terminal, 'reading_receipt': False,
            'restoration': restoration}


def _cli_layout(root, target, paths):
    """Select the asset root whose registered layout owns the chosen catalog."""
    root, target = Path(root).absolute(), Path(target).absolute()
    candidates = [root]
    for parent in target.parent.parents:
        if parent == root:
            break
        if parent.is_relative_to(root):
            candidates.append(parent)
    candidates.sort(key=lambda candidate: len(candidate.parts), reverse=True)
    modes = (('source_path', 'registry/resources.json', 'registry/placements.json'),
             ('deployment_path', '.agents/registry/resources.json', '.agents/registry/placements.json'),
             ('export_alias', 'RESOURCES.json', 'PLACEMENTS.json'))
    registered_target, eligible, standard_pairs = False, set(), set()
    for base in candidates:
        for field, resources_name, placements_name in modes:
            if paths is not None and (paths.get('registry_resources'), paths.get('registry_placements')) != (resources_name, placements_name):
                continue
            resource_file, placement_file = base / resources_name, base / placements_name
            if not resource_file.is_file() or not placement_file.is_file():
                continue
            resources = parse(regular_bytes(resource_file))['resources']
            placements = parse(regular_bytes(placement_file))['resources']
            owns_target = any(
                base / safe_path((resources if kind == 'source_path' else placements)['policy-manifest'][kind]) == target
                for kind, _, _ in modes)
            registered_target |= owns_target
            if owns_target:
                eligible.add(base)
            for kind, _, _ in modes:
                catalog = resources if kind == 'source_path' else placements
                standard_pairs.add(tuple(safe_path(catalog[rid][kind])
                                         for rid in ('registry-resources', 'registry-placements')))
            def location(rid):
                return safe_path((resources if field == 'source_path' else placements)[rid][field])
            if base / location('policy-manifest') != target:
                continue
            expected = {'registry_resources': location('registry-resources'),
                        'registry_placements': location('registry-placements')}
            if paths is not None and any(paths.get(key) != value for key, value in expected.items()):
                continue
            if paths is None:
                mapped = {resource_key(rid): location(rid) for rid, row in resources.items()
                          if rid != 'policy-manifest' and not row.get('source_distribution_only')}
                if not all((base / p).is_file() for p in mapped.values()):
                    continue
            else:
                mapped = None
            # Prefer the package-relative layout when a new standalone export
            # also admits the same bytes from the enclosing project root.
            return base, mapped
    if paths is not None:
        # Custom maps can relocate the bootstrap registries themselves.
        for base in candidates:
            resource_file = base / safe_path(paths['registry_resources'])
            placement_file = base / safe_path(paths['registry_placements'])
            if not resource_file.is_file() or not placement_file.is_file():
                continue
            resources = parse(regular_bytes(resource_file))['resources']
            placements = parse(regular_bytes(placement_file))['resources']
            for kind, _, _ in modes:
                catalog = resources if kind == 'source_path' else placements
                standard_pairs.add(tuple(safe_path(catalog[rid][kind])
                                         for rid in ('registry-resources', 'registry-placements')))
                if base / safe_path(catalog['policy-manifest'][kind]) == target:
                    eligible.add(base)
                    registered_target = True
    if paths is not None and (paths.get('registry_resources'), paths.get('registry_placements')) not in standard_pairs:
        # A caller may map registered assets to custom paths. Resolve such a
        # map only when its declared files fit exactly one registered owner.
        custom = [base for base in eligible if all((base / safe_path(p)).is_file() for p in paths.values())]
        if len(custom) == 1:
            return custom[0], None
        if len(custom) > 1:
            raise ValueError('custom policy paths match more than one registered asset root')
    if registered_target:
        raise ValueError('selected manifest does not match an available registered asset layout')
    # Explicit custom --paths remain relative to the supplied project root.
    return root, None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('generate', 'verify'))
    parser.add_argument('--root', required=True)
    parser.add_argument('--manifest', help='explicit adopted manifest; default resolves the registered layout')
    parser.add_argument('--paths', help='JSON registered logical-id to layout-relative asset path map')
    args = parser.parse_args(argv)
    target = manifest_path(args.root, args.manifest, allow_missing=args.command == 'generate')
    paths = parse(regular_bytes(args.paths)) if args.paths else None
    existing = parse(regular_bytes(target)) if args.command == 'verify' or target.is_file() else None
    existing_paths = _manifest_paths(existing) if existing is not None else None
    if args.command == 'verify' and paths is not None and paths != existing_paths:
        raise ValueError('--paths must match the selected manifest when verifying')
    declared = paths if paths is not None else existing_paths
    root, registered_paths = _cli_layout(args.root, target, declared)
    if args.command == 'generate':
        if paths is None:
            paths = existing_paths if existing is not None else registered_paths
        manifest = generate_manifest(root, paths)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(canonical(manifest) + b'\n')
        print(digest(regular_bytes(target)))
    else:
        verify_manifest(root, existing)
        print('policy assets match')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
