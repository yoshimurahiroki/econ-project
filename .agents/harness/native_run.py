#!/usr/bin/env python3
"""Begin a pinned research run, check submitted snapshots, and finalize exact bytes."""
import argparse
import os
import stat
from contextlib import contextmanager
from functools import wraps
import importlib.util
import json
from pathlib import Path
import sys
import uuid


def _sibling(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native = _sibling('run_native_check', Path(__file__).with_name('native_check.py'))
policy = _sibling('run_policy_assets', Path(__file__).with_name('policy_assets.py'))
gate = native.gate
hooks = _sibling('run_codex_hooks', Path(__file__).with_name('codex_hooks.py'))
LOADED_SOURCE_HASHES = {key: gate.sha(gate.regular_bytes(filename)) for key, filename in {
    'native_run': __file__, 'policy_assets': policy.__file__, 'native_check': native.__file__,
    'codex_hooks': hooks.__file__,
    'requirements_check': native.requirements.__file__, 'local_checks': gate.__file__}.items()}
EMPTY_REPORTS = {'schema_version': 1, 'reports': [], 'unresolved_flags': []}
REQUIRED_CAPABILITIES = tuple(native.REVIEW_PLANS['strict-reviewed']['capabilities'])


@contextmanager
def _run_operation(run_dir):
    """Serialize task context, submission and publication with an OS-owned lock."""
    requested = Path(run_dir).absolute()
    gate.require(not any(path.is_symlink() for path in (requested, *requested.parents)),
                 'symlink run directory prohibited')
    root = requested.resolve()
    root.parent.mkdir(parents=True, exist_ok=True)
    lock = root.parent / ('.econ-run-lock-' + gate.sha(str(root).encode('utf-8')))
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        gate.require(stat.S_ISREG(os.fstat(fd).st_mode), 'run lock must be a regular file')
        try:
            gate.lock_fd(fd)
        except BlockingIOError as exc:
            raise ValueError('another operation is active in this run; reload its current context and retry') from exc
        yield
    finally:
        os.close(fd)


def _serialize_run(function):
    @wraps(function)
    def invoke(*args, **kwargs):
        root = args[0] if args else kwargs['run_dir']
        with _run_operation(root):
            return function(*args, **kwargs)
    return invoke


def _contract(raw, request):
    contract = gate.parse_json(raw)
    gate.require(isinstance(contract, dict) and type(contract.get('schema_version')) is int
                 and contract['schema_version'] == 2,
                 'research-full requires contract schema_version 2; '
                 'use requirements_check.py for v1 diagnosis and migrate to v2 before begin')
    return native.requirements.validate_contract(contract, request)


def _capabilities(raw):
    capability = gate.parse_json(raw)
    gate.require(isinstance(capability, dict) and {'available', 'unavailable'} <= set(capability)
                 and set(capability) <= {'available', 'unavailable', 'assignments'}
                 and all(isinstance(capability[key], list)
                         and all(native._text(x) for x in capability[key])
                         and len(capability[key]) == len(set(capability[key])) for key in ('available', 'unavailable'))
                 and not set(capability['available']) & set(capability['unavailable']),
                 'capabilities must list unique, disjoint available and unavailable names')
    assignments = capability.get('assignments', [])
    roles = {'author', 'requirements-coverage'} | {role for plan in native.REVIEW_PLANS.values() for role in plan['roles']}
    gate.require(isinstance(assignments, list), 'assignments must be an array')
    for row in assignments:
        support_fields = {'assignment_id', 'parent_task_id', 'parent_requirement_ids', 'assigned_result',
                          'input_versions', 'adopted_choice_ids', 'authority_and_holds', 'required_checks'}
        kind = row.get('assignment_kind', 'control-review') if isinstance(row, dict) else None
        gate.require(kind in {'control-review', 'support'}, 'unknown assignment kind')
        gate.require(isinstance(row, dict) and {'worker_id', 'roles', 'launch_ref', 'source_verification'} <= set(row)
                     and set(row) <= {'worker_id', 'roles', 'launch_ref', 'source_verification',
                                     'purpose', 'inputs_seen_before_assignment', 'original_request_provided',
                                     'assignment_kind', *support_fields}
                     and native._text(row['worker_id']) and native._text(row['launch_ref'])
                     and isinstance(row['roles'], list) and row['roles']
                     and all(native._text(role) for role in row['roles'])
                     and len(set(row['roles'])) == len(row['roles'])
                     and (not set(row['roles']) - roles if kind == 'control-review' else not set(row['roles']) & roles)
                     and native._source_matched(row['source_verification']), 'assignment requires its actual runtime launch binding')
        if kind == 'support':
            gate.require(support_fields <= set(row)
                         and all(native._text(row[key]) for key in ('assignment_id', 'parent_task_id', 'assigned_result'))
                         and all(isinstance(row[key], list) and all(native._text(value) for value in row[key])
                                 and len(row[key]) == len(set(row[key]))
                                 for key in ('parent_requirement_ids', 'adopted_choice_ids', 'required_checks'))
                         and row['parent_requirement_ids'] and row['required_checks']
                         and isinstance(row['input_versions'], dict) and row['input_versions']
                         and all(native._text(key) and gate.hexhash(value) for key, value in row['input_versions'].items())
                         and isinstance(row['authority_and_holds'], dict)
                         and {'authority', 'holds'} <= set(row['authority_and_holds'])
                         and isinstance(row['authority_and_holds']['holds'], list),
                         'support requires its parent requirements, fixed inputs, authority/holds and scope checks')
        if 'purpose' in row:
            gate.require(native._text(row['purpose'])
                         and isinstance(row.get('inputs_seen_before_assignment'), list)
                         and all(native._text(value) for value in row['inputs_seen_before_assignment'])
                         and row.get('original_request_provided') in
                             {'before-assessment', 'after-reconstruction', 'withheld'},
                         'assignment purpose requires actual prior inputs and original request timing')
            if row['purpose'] == 'artifact-only-comprehension':
                gate.require('author' not in row['roles']
                             and not {'request', 'candidate', 'authoring-history'} & set(row['inputs_seen_before_assignment'])
                             and row['original_request_provided'] in {'after-reconstruction', 'withheld'},
                             'artifact-only comprehension requires a previously unexposed context')
    return capability


def _resource_reads(raw, files):
    payload = gate.parse_json(raw)
    gate.require(isinstance(payload, dict) and set(payload) == {'schema_version', 'reads'}
                 and type(payload['schema_version']) is int and payload['schema_version'] == 1
                 and isinstance(payload['reads'], list) and 0 < len(payload['reads']) <= 1000,
                 'invalid resource read cache')
    manifest = gate.parse_json(files['policy-manifest.json'])
    _, _, assets = _policy(**manifest['selection'])
    resolver, routes = policy._routes(assets)
    for row in payload['reads']:
        gate.require(isinstance(row, dict) and {'reader_id', 'resource_id', 'sha256', 'sections'} <= set(row)
                     and set(row) <= {'reader_id', 'resource_id', 'sha256', 'sections', 'partial_sections'}
                     and native._text(row['reader_id']) and isinstance(row['resource_id'], str)
                     and row['resource_id'] in manifest['resource_sections'], 'read resource is not adopted')
        rid = row['resource_id']; key = policy.resource_key(rid)
        selection = manifest['resource_sections'][rid]
        gate.require(key in manifest['assets'] and row['sha256'] == manifest['assets'][key]['sha256'],
                     'read hash or selected sections differ')
        sections = row['sections']; parts = row.get('partial_sections', [])
        gate.require(isinstance(sections, list) and isinstance(parts, list) and (sections or parts)
                     and all(isinstance(sid, str) for sid in sections)
                     and len(sections) == len(set(sections)), 'invalid recorded reading sections')
        for part in parts:
            gate.require(isinstance(part, dict) and set(part) == {'section_id', 'start', 'end'}
                         and isinstance(part['section_id'], str), 'invalid partial reading range')
        aliases = {loc.get('heading', sid): sid for sid, loc in routes['sections'][rid].items()}
        requested = {aliases.get(sid, sid) for sid in sections}
        requested.update(part['section_id'] for part in parts)
        requested.update(['all'] if selection.get('whole_resource') else
                         [aliases[heading] for heading in selection.get('sections', [])])
        ranges = policy.section_ranges(routes, rid, assets[key].decode('utf-8'), resolver, requested)
        allowed = [(0, len(assets[key].decode('utf-8')))] if selection.get('whole_resource') else [
            ranges[aliases[heading]] for heading in selection.get('sections', [])]
        def inside(sid, left=None, right=None):
            gate.require(isinstance(sid, str) and sid in ranges, 'unregistered reading section')
            start, end = ranges[sid]
            left, right = (start, end) if left is None else (left, right)
            gate.require(type(left) is int and type(right) is int and start <= left < right <= end
                         and any(a <= left < right <= b for a, b in allowed),
                         'read range is outside the adopted section')
        row['sections'] = [aliases.get(sid, sid) for sid in sections]
        for sid in row['sections']:
            inside(sid)
        for part in parts:
            gate.require(isinstance(part, dict) and set(part) == {'section_id', 'start', 'end'},
                         'invalid partial reading range')
            inside(part['section_id'], part['start'], part['end'])
    return payload['reads']


def _apply_run_records(root, raw, run, files):
    """Append-only context changes preserve the fixed request and policy bytes."""
    run['current_author_id'] = run['author_id']
    run['record_sha256'], run['record_number'] = gate.sha(raw), 0
    run['_record_files'] = {}
    run['resource_reads'] = []
    directory = root / 'records'
    if not directory.exists() and not directory.is_symlink():
        return
    _safe_directory(directory)
    committed = [path for path in sorted(directory.iterdir()) if not path.name.startswith('.gate-')]
    for ordinal, path in enumerate(committed, 1):
        gate.require(path.name == f'{ordinal:08d}', 'run record sequence is incomplete')
        _safe_directory(path)
        record_raw, payload = gate.regular_bytes(path / 'record.json'), gate.regular_bytes(path / 'payload.json')
        record = gate.parse_json(record_raw)
        gate.require(isinstance(record, dict) and set(record) ==
                     {'schema_version', 'kind', 'previous_sha256', 'payload_sha256', 'author_id'}
                     and type(record['schema_version']) is int and record['schema_version'] == 1
                     and record['previous_sha256'] == run['record_sha256']
                     and record['payload_sha256'] == gate.sha(payload), 'run context record differs from its predecessor or payload')
        if record['kind'] == 'capabilities':
            capability = _capabilities(payload)
            if record['author_id'] != run['current_author_id']:
                gate.require(any(row['worker_id'] == record['author_id'] and 'author' in row['roles']
                                 for row in capability.get('assignments', [])), 'author replacement requires its actual assignment')
            files['current-capabilities.json'] = payload
            run['current_author_id'] = record['author_id']
        elif record['kind'] == 'coverage':
            gate.require(record['author_id'] == run['current_author_id'], 'coverage context author mismatch')
            _coverage(payload, run, files)
            files['current-coverage.json'] = payload
            run['_coverage_path'] = str(path / 'payload.json')
        elif record['kind'] == 'resource-reads':
            gate.require(record['author_id'] == run['current_author_id'], 'read cache context author mismatch')
            for row in _resource_reads(payload, files):
                previous = next((old for old in run['resource_reads'] if all(old[k] == row[k]
                                 for k in ('reader_id', 'resource_id', 'sha256'))), None)
                if previous is None:
                    run['resource_reads'].append(row)
                else:
                    previous['sections'] = sorted(set(previous['sections']) | set(row['sections']))
                    parts = previous.get('partial_sections', []) + row.get('partial_sections', [])
                    if parts:
                        previous['partial_sections'] = list({gate.canonical(part): part for part in parts}.values())
        else:
            raise ValueError('unknown run context record kind')
        run['record_sha256'], run['record_number'] = gate.sha(record_raw), ordinal
        run['_record_files'].update({str(path / 'record.json'): gate.sha(record_raw),
                                     str(path / 'payload.json'): gate.sha(payload)})


def _append_run_record(root, run, kind, payload, expected, author_id=None):
    gate.require(expected == run['record_sha256'], 'run context changed or expected record SHA-256 missing')
    record = {'schema_version': 1, 'kind': kind, 'previous_sha256': expected,
              'payload_sha256': gate.sha(payload), 'author_id': author_id or run['current_author_id']}
    records = root / 'records'
    records.mkdir(exist_ok=True)
    _safe_directory(records)
    gate.release({'record.json': gate.canonical(record), 'payload.json': payload},
                 records / f"{run['record_number'] + 1:08d}")


def _author(run):
    return run.get('current_author_id', run['author_id'])


def _review_plan(files):
    return gate.parse_json(files.get('review-plan.json', b'{"schema_version":1,"plan":"strict-reviewed"}'))['plan']


def _required_reviews(rows):
    return [row['evaluator'] for row in rows
            if row.get('evaluator', {}).get('type') == 'structured_review']


def _plan_satisfies_requirements(plan, rows):
    definition = native.REVIEW_PLANS[plan]
    return all(item['role'] in definition['roles']
               and item.get('review_kind', 'independent') == definition.get('review_kind', 'independent')
               for item in _required_reviews(rows))


def _bounded_rows(rows):
    return all(row['kind'] in ('artifact', 'content', 'prohibition', 'evidence')
               and (row['kind'] != 'artifact' or row['file_type'] == 'text') for row in rows)


def _independent_requested(rows, manifest):
    return ('independent_review_requested_or_needed' in manifest['selection']['conditions']
            or any(item.get('review_kind', 'independent') == 'independent'
                   for item in _required_reviews(rows)))


def _validate_review_plan(raw, files, manifest, assets):
    selection = gate.parse_json(raw)
    resolver, routes = policy._routes(assets)
    gate.require(routes['review_plans'] == native.REVIEW_PLANS,
                 'executing review plans differ from pinned registry')
    gate.require(isinstance(selection, dict) and type(selection.get('schema_version')) is int
                 and selection['schema_version'] == 1, 'invalid review-plan schema')
    rows = _contract(files['requirements.json'], files['request.txt'])
    if selection.get('plan') in ('strict-reviewed', 'full'):
        gate.require(set(selection) == {'schema_version', 'plan'}, 'invalid full review-plan fields')
        gate.require(_plan_satisfies_requirements(selection['plan'], rows),
                     'full plan does not satisfy the contract-required review kind and role')
        return
    plan = selection.get('plan')
    gate.require(plan in ('focused', 'direct') and set(selection) ==
                 {'schema_version', 'plan', 'scope', 'request_evidence'}, 'invalid bounded review-plan fields')
    resolver, routes = policy._routes(assets)
    adopted = manifest['selection']
    gate.require(resolver.bounded_review_eligible(routes, adopted['operation'],
                 adopted['conditions'], adopted['templates'], plan), 'operation requires full review plan')
    scope = selection['scope']
    fields = {'external_actions', 'source_investigation', 'quantitative_changes',
              'independent_review_requested'}
    gate.require(isinstance(scope, dict) and set(scope) == fields
                 and all(type(value) is bool for value in scope.values())
                 and all(scope[field] is False for field in fields - {'independent_review_requested'}),
                 'bounded review requires no external actions, source investigation or quantitative changes')
    independent = _independent_requested(rows, manifest)
    gate.require(not independent or scope['independent_review_requested'],
                 'scope must retain the contract-required independent review')
    gate.require(plan != 'direct' or not scope['independent_review_requested'],
                 'direct cannot satisfy an independent review request')
    request = files['request.txt'].decode('utf-8')
    evidence = selection['request_evidence']
    gate.require(isinstance(evidence, list) and evidence, 'review-plan requires original request evidence')
    for row in evidence:
        gate.require(isinstance(row, dict) and set(row) == {'start', 'end', 'quote'}
                     and type(row['start']) is int and type(row['end']) is int
                     and 0 <= row['start'] < row['end'] <= len(request)
                     and row['quote'] == request[row['start']:row['end']], 'invalid review-plan request evidence')
    if adopted['operation'] in ('econ-writing:revise', 'econ-writing:translate'):
        gate.require(any(path.startswith('sources/') for path in files),
                     'revision or translation requires pinned original text sources')
    gate.require(_bounded_rows(rows),
                 'focused review permits only text artifact/content/prohibition/evidence requirements')
    gate.require(_plan_satisfies_requirements(plan, rows),
                 'bounded plan lacks the contract-required review kind and role')


def _default_review_plan(files, manifest, assets):
    # Draft plans require an explicit selection and never confer release rights.
    return {'schema_version': 1, 'plan': 'strict-reviewed'}


def _review_definition(files):
    # _validate_review_plan has compared these loaded definitions with pinned registry bytes.
    return gate.parse_json(gate.canonical(native.REVIEW_PLANS[_review_plan(files)]))


def _capability_statuses(files):
    capability = _capabilities(files.get('current-capabilities.json', files['capabilities.json']))
    return {name: ('available' if name in capability['available'] else
                   'unavailable' if name in capability['unavailable'] else 'unknown')
            for name in _review_definition(files)['capabilities']}


def _policy(**selection):
    root, raw, manifest, assets = policy.discover_policy(__file__, **selection)
    loaded = {'native_run': __file__, 'policy_assets': policy.__file__, 'codex_hooks': hooks.__file__,
              'native_check': native.__file__, 'requirements_check': native.requirements.__file__,
              'local_checks': gate.__file__}
    for key, filename in loaded.items():
        gate.require(gate.sha(gate.regular_bytes(filename)) == manifest['assets'][key]['sha256']
                     and LOADED_SOURCE_HASHES[key] == manifest['assets'][key]['sha256'],
                     'executing checker differs from policy asset: ' + key)
    return raw, manifest, assets


def _safe_directory(path):
    path = Path(path).absolute()
    gate.require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink directory prohibited')
    gate.require(path.is_dir(), 'directory missing: ' + str(path))
    return path


def _read_map(root, entries):
    gate.require(isinstance(entries, dict), 'snapshot file hashes must be an object')
    files = {}
    for path, sha in entries.items():
        gate.safe_relative(path)
        if isinstance(sha, dict):
            gate.require(set(sha) == {'sha256', 'size_bytes'} and gate.hexhash(sha['sha256'])
                         and type(sha['size_bytes']) is int and sha['size_bytes'] >= 0,
                         'invalid fixed file descriptor')
            data = gate.file_snapshot(root / path)
            gate.require(len(data) == sha['size_bytes'], 'pinned file size changed: ' + path)
        else:
            gate.require(gate.hexhash(sha), 'invalid snapshot file digest')
            data = gate.regular_bytes(root / path)
        gate.require(gate.sha(data) == gate.record_hash(sha), 'pinned bytes changed: ' + path)
        files[path] = data
    return files


def _load_run(run_dir):
    root = _safe_directory(run_dir)
    raw = gate.regular_bytes(root / 'run.json')
    run = gate.parse_json(raw)
    required_fields = {'schema_version', 'run_id', 'mode', 'author_id', 'policy_id', 'policy_manifest_sha256', 'files'}
    gate.require(isinstance(run, dict) and required_fields <= set(run)
                 and set(run) <= required_fields | {'hook_binding', 'release_assurance', 'release_adapter'},
                 'invalid fixed run record')
    gate.require(run.get('release_assurance', 'host-authenticated') in {'host-authenticated', 'host-observed'},
                 'invalid fixed release assurance')
    _adapter_binding(run.get('release_adapter'))
    gate.require(type(run['schema_version']) is int and run['schema_version'] == 2
                 and run['mode'] in ('strict', 'provisional') and native._text(run['author_id']),
                 'invalid run mode, schema, or executor')
    gate.require(isinstance(run['run_id'], str), 'run_id must be a canonical UUIDv4')
    run_id = uuid.UUID(run['run_id'])
    gate.require(run_id.version == 4 and str(run_id) == run['run_id'],
                 'run_id must be a canonical UUIDv4')
    files = _read_map(root, run['files'])
    required = {'request.txt', 'requirements.json', 'dictionary.json', 'policy-manifest.json', 'capabilities.json', 'review-plan.json'}
    if run['mode'] == 'provisional':
        required.add('provisional-selection.json')
    gate.require(required <= set(files) and all(path in required or path.startswith('sources/') for path in files),
                 'fixed run inputs are incomplete')
    _contract(files['requirements.json'], files['request.txt'])
    _capabilities(files['capabilities.json'])
    saved_manifest = gate.parse_json(files['policy-manifest.json'])
    gate.require(isinstance(saved_manifest, dict) and isinstance(saved_manifest.get('selection'), dict),
                 'saved run requires an explicit operation policy selection; begin a new run')
    _, catalog, assets = _policy(**saved_manifest['selection'])
    manifest = policy.select_manifest(catalog, assets, **saved_manifest['selection'])
    manifest_raw = policy.canonical(manifest)
    gate.require(run['policy_id'] == manifest['policy_id']
                 and gate.sha(manifest_raw) == run['policy_manifest_sha256']
                 and files['policy-manifest.json'] == manifest_raw
                 and files['dictionary.json'] == assets['dictionary'],
                 'adopted policy changed; begin a new run and obtain new reviews')
    if 'hook_binding' in run:
        gate.require(run['hook_binding'] == hooks.load_context(
            run['hook_binding']['context_path'], root, files['request.txt'], __file__, run['policy_id']),
            'fixed hook binding changed')
    _validate_review_plan(files['review-plan.json'], files, manifest, assets)
    if run['mode'] == 'provisional':
        _selection(files['provisional-selection.json'])
    _apply_run_records(root, raw, run, files)
    return root, raw, run, files, manifest


def _selection(raw):
    selected = gate.parse_json(raw)
    gate.require(isinstance(selected, dict)
                 and set(selected) == {'mode', 'user_message_ref', 'user_text'}
                 and selected['mode'] == 'provisional'
                 and all(native._text(selected[key]) for key in ('user_message_ref', 'user_text')),
                 'provisional requires an explicit recorded user selection')
    return selected


def _coverage_rows(rows, files, independent_extraction=None):
    """Validate one shared source ledger; host provenance is a separate gate."""
    _contract(files['requirements.json'], files['request.txt'])
    contract = gate.parse_json(files['requirements.json'])
    gate.require(isinstance(contract, dict) and type(contract.get('schema_version')) is int
                 and contract['schema_version'] == 2, 'research runs require contract schema_version 2')
    return native.requirements.validate_request_coverage(
        contract, files['request.txt'], rows, independent_extraction)


def _coverage(raw, run, files):
    report = gate.parse_json(raw)
    gate.require(isinstance(report, dict), 'coverage return must be an object')
    body_text = report.get('return_text')
    gate.require(native._text(body_text) and report.get('return_sha256') == gate.sha(body_text.encode()),
                 'coverage return text digest mismatch')
    body = gate.parse_json(body_text.encode())
    gate.require(isinstance(body, dict), 'coverage original return must be an object')
    schema_version = body.get('schema_version')
    gate.require(type(schema_version) is int and schema_version in (2, 3),
                 'unsupported requirements-coverage schema')
    expected = {'schema_version': schema_version, 'role': 'requirements-coverage', 'decision': 'pass',
                'run_id': run['run_id'],
                'request_sha256': gate.sha(files['request.txt']),
                'contract_sha256': gate.sha(files['requirements.json']),
                'policy_manifest_sha256': run['policy_manifest_sha256'],
                'findings': [], 'unassessed': [], 'errors': [], 'coverage_rows': body.get('coverage_rows')}
    if schema_version == 3:
        expected['independent_extraction'] = body.get('independent_extraction')
        gate.require(isinstance(expected['independent_extraction'], dict),
                     'schema 3 requires the independent extraction ledger comparison')
    if _review_plan(files) in ('focused', 'direct'):
        expected.update(review_plan_sha256=gate.sha(files['review-plan.json']), scope_assessment='eligible')
    kind = _review_definition(files).get('review_kind', 'independent')
    if kind == 'self-check':
        expected.update(worker_id=_author(run), review_kind='self-check')
    gate.require(body == expected and type(body.get('schema_version')) is int,
                 'coverage must pass original-request and contract checks with exact pinned bindings')
    _coverage_rows(body['coverage_rows'], files, body.get('independent_extraction') if schema_version == 3 else None)
    for field, value in body.items():
        gate.require(field not in report or gate.canonical(report[field]) == gate.canonical(value), 'contradictory coverage mirror: ' + field)
    gate.require(report.get('role') == 'requirements-coverage', 'coverage role mismatch')
    native._review_identity(report, body, kind, _author(run))
    return body


def _coverage_bytes(root, run, files):
    path = root / 'coverage' / 'report.json'
    raw = files.get('current-coverage.json')
    if raw is None and not path.exists():
        return None
    raw = gate.regular_bytes(path) if raw is None else raw
    report = gate.parse_json(raw)
    kind = _review_definition(files).get('review_kind', 'independent')
    if report.get('worker_id') == _author(run) and kind == 'independent' or report.get('worker_id') != _author(run) and kind == 'self-check':
        return None
    _coverage(raw, run, files)
    return raw


def _required_artifact_actions(files, check):
    if check is None:
        return []
    fulfillment = check.get('requirements', {})
    passed = {row.get('requirement_id') for row in fulfillment.get('checked', []) if 'path' in row}
    failures = {row.get('requirement_id'): row for row in fulfillment.get('unmet', [])}
    return [{'action': 'produce-required-artifact', 'requirement_id': row['id'], 'path': row['path'],
             'reason': failures.get(row['id'], {}).get('message', 'required artifact has not passed validation')}
            for row in _contract(files['requirements.json'], files['request.txt'])
            if row['kind'] == 'artifact' and row['id'] not in passed]


def _ordered_actions(needed):
    priorities = {'update-capabilities-in-current-run': 0, 'obtain-requirements-coverage': 1,
                  'produce-required-artifact': 2, 'correct-and-resubmit': 3, 'resolve-and-resubmit': 3,
                  'rewrite-or-delete-prohibited-text': 3, 'complete-required-check': 4, 'submit': 5, 'finalize': 6}
    unique = {}
    for item in needed:
        row = dict(item)
        row['rule_ids'] = (['control.original-request-and-contract'] if row.get('action') == 'obtain-requirements-coverage'
            else ['control.finalization-and-delivery'] if row.get('action') == 'finalize'
            else ['control.full-candidate-prose-records', 'control.original-returns-and-correction']
                if row.get('action') == 'rewrite-or-delete-prohibited-text'
            else ['control.run-and-capability-contract'] if row.get('capability')
            else ['control.original-returns-and-correction'])
        key = tuple(str(row.get(k, '')) for k in ('action', 'requirement_id', 'path', 'role', 'check_id', 'check', 'capability', 'id', 'message', 'reason'))
        if key not in unique:
            unique[key] = row
    # Missing artifact has a concrete repair; avoid generic duplicate requirement errors.
    artifacts = {row.get('requirement_id') for row in unique.values() if row.get('action') == 'produce-required-artifact'}
    result = [row for row in unique.values() if not (row.get('requirement_id') in artifacts
              and row.get('action') in {'correct-and-resubmit', 'resolve-and-resubmit'})]
    return sorted(result, key=lambda row: priorities.get(row.get('action'), 4))


def _with_instructions(result, manifest, stage=None, *, request_text=None, restore=False):
    if result.get('status') in {'ready', 'provisional-ready'} and result.get('submission_sha256'):
        if not any(row.get('action') == 'finalize' for row in result.get('needed_actions', [])):
            result.setdefault('needed_actions', []).append({'action': 'finalize',
                'submission_sha256': result['submission_sha256']})
    result['needed_actions'] = _ordered_actions(result.get('needed_actions', []))
    result['instruction_context'] = policy.instruction_context(
        manifest=manifest, status=result, stage=stage, role='author', reader_id=result.get('author_id'),
        request_text=request_text, restore=restore)
    return result


def _status(run, files, check=None, coverage=None):
    capabilities = _capability_statuses(files)
    fulfilled = set()
    if coverage is not None:
        fulfilled.add('independent-requirements-coverage')
    if check is not None:
        fulfilled.update(role for role, value in check.get('reviews', {}).items() if value.get('status') == 'consistent')
    needed = [{'action': 'update-capabilities-in-current-run', 'capability': name,
               'capability_status': status,
               'role': 'requirements-coverage' if name == 'independent-requirements-coverage' else name,
               'reason': ('required capability is pinned unavailable' if status == 'unavailable' else
                          'required capability is not declared available in the pinned record')}
              for name, status in capabilities.items() if status != 'available' and name not in fulfilled]
    if coverage is None:
        needed.append({'action': 'obtain-requirements-coverage',
                       'role': 'requirements-coverage',
                       'reason': _review_definition(files).get('review_kind', 'independent') + ' original-request-to-contract return missing'})
    if check is not None:
        for item in check.get('missing_checks', []):
            needed.append({'action': 'complete-required-check', **item})
        for item in check.get('failed_checks', []):
            needed.append({'action': 'correct-and-resubmit', **item})
        for item in check.get('unresolved', []):
            needed.append({'action': 'resolve-and-resubmit', **item})
    consistent = (all(value == 'available' or name in fulfilled for name, value in capabilities.items())
                  and check is not None and check['status'] == 'consistent' and coverage is not None)
    status = ('ready' if consistent else 'blocked') if run['mode'] == 'strict' else 'quarantined-unapproved'
    if status == 'ready' and _review_plan(files) != 'strict-reviewed':
        status = 'draft-ready'
        needed.append({'action': 'begin-strict-reviewed-run',
                       'reason': 'the selected plan is draft-only and has no publication qualification'})
    artifact_actions = _required_artifact_actions(files, check)
    if artifact_actions:
        status = 'blocked'
        needed.extend(artifact_actions)
    if check is not None:
        prose = check.get('prose_scan', {})
        if (prose.get('status') != 'scanned' or prose.get('unresolved_hits')
                or any(item.get('check') == 'artifact-text-view' for item in check.get('missing_checks', []))):
            status = 'blocked'
            needed.append({'action': 'rewrite-or-delete-prohibited-text',
                           'reason': 'complete the prose scan and resolve every non-source match'})
    record_status = status
    if status == 'ready' and not callable(_release_verifier()):
        status = 'blocked-unapproved'
        configured = run.get('release_adapter') is not None
        needed.append({'action': 'verify-release-through-configured-host' if configured else 'connect-host-release-verifier',
                       'check': 'host-provenance', 'reason':
                       'record checks are consistent; invoke the fixed host output route for current verification' if configured else
                       'record checks are consistent; the local host event/output adapter is not connected'})
    result = {'status': status, 'run_id': run['run_id'], 'mode': run['mode'], 'policy_id': run['policy_id'],
            'request_sha256': gate.sha(files['request.txt']),
            'policy_manifest_sha256': run['policy_manifest_sha256'],
            'review_plan': _review_plan(files), 'required_capabilities': list(capabilities), 'capability_statuses': capabilities,
            'fulfilled_capabilities': sorted(set(capabilities) & fulfilled),
            'author_id': _author(run), 'record_sha256': run.get('record_sha256'),
            'resource_reads': run.get('resource_reads', []),
            'unmet_requirement_ids': ([row['id'] for row in _contract(files['requirements.json'], files['request.txt'])]
                if check is None else sorted({row['requirement_id'] for row in
                    check.get('requirements', {}).get('unmet', []) if 'requirement_id' in row})),
            'needed_actions': needed, 'worker_launches': 0, 'independently_approved': False,
            'release_authorized': False, 'provenance_authenticated': False}
    result['record_status'] = record_status
    result['adopted_assurance_class'] = run.get('release_assurance', 'host-authenticated')
    result['release_adapter'] = run.get('release_adapter')
    result['host_adapter_status'] = ('connected-for-current-verification' if callable(_release_verifier()) else
        'configured-awaiting-host-verification' if run.get('release_adapter') else 'not-connected')
    if check is not None and 'surface_check' in check:
        result['surface_check'] = check['surface_check']
    return result


@_serialize_run
def begin_run(run_dir, request=None, requirements=None, author_id=None, mode=None,
              provisional_selection=None, capabilities=None, coverage_review=None,
              operation=None, conditions=None, profile=None, templates=None, sources=None, review_plan=None,
              expected_record_sha256=None, resource_reads=None, hook_context=None, release_assurance=None, release_adapter=None):
    """Create fixed inputs, or resume only to supply the pre-candidate coverage return."""
    root = Path(run_dir).absolute()
    gate.require(resource_reads is None or root.exists(), 'record resource reads in an existing fixed run')
    if root.exists():
        root, run_raw, run, files, manifest = _load_run(root)
        gate.require(all(value is None for value in
                         (request, requirements, mode, provisional_selection,
                          operation, conditions, profile, templates, sources, review_plan, release_assurance, release_adapter)),
                     'existing request, contract, policy selection and mode remain fixed')
        if hook_context is not None:
            gate.require(run.get('hook_binding') == hooks.load_context(
                hook_context, root, files['request.txt'], __file__, run['policy_id']), 'resumed hook binding differs')
        gate.require(author_id is None or capabilities is not None, 'author replacement requires its assignment record')
        if capabilities is not None:
            capability_raw = gate.regular_bytes(capabilities)
            capability = _capabilities(capability_raw)
            next_author = _author(run) if author_id is None else author_id
            gate.require(native._text(next_author), 'actual replacement author required')
            if next_author != _author(run):
                gate.require(any(row['worker_id'] == next_author and 'author' in row['roles']
                                 for row in capability.get('assignments', [])), 'replacement author lacks its actual assignment')
            previous = files.get('current-capabilities.json', files['capabilities.json'])
            if gate.canonical(capability) != gate.canonical(_capabilities(previous)) or next_author != _author(run):
                _append_run_record(root, run, 'capabilities', capability_raw, expected_record_sha256, next_author)
                root, run_raw, run, files, manifest = _load_run(root)
                expected_record_sha256 = run['record_sha256']
    else:
        gate.require(request is not None and requirements is not None and native._text(author_id),
                     'new run requires request, requirements, and author-id')
        gate.require(native._text(operation), 'new run requires an explicit registered operation')
        mode = 'strict' if mode is None else mode
        gate.require(mode in ('strict', 'provisional'), 'unsupported mode')
        _, catalog, assets = _policy(operation=operation, conditions=conditions or (),
                                      profile=profile, templates=templates or ())
        manifest = policy.select_manifest(catalog, assets, operation, conditions=conditions or (),
                                          profile=profile, templates=templates or ())
        manifest_raw = policy.canonical(manifest)
        request_raw, contract_raw = gate.regular_bytes(request), gate.regular_bytes(requirements)
        gate.require(request_raw.strip(), 'request must be nonempty')
        _contract(contract_raw, request_raw)
        capability_raw = gate.regular_bytes(capabilities) if capabilities else gate.canonical({'available': [], 'unavailable': []})
        _capabilities(capability_raw)
        files = {'request.txt': request_raw, 'requirements.json': contract_raw,
                 'dictionary.json': assets['dictionary'], 'policy-manifest.json': manifest_raw,
                 'capabilities.json': capability_raw}
        if sources is not None:
            source_files = native._collect_artifacts(sources)
            for path, data in source_files.items():
                # Preserve raw calculation inputs; text evidence is checked when referenced.
                gate.require(path != 'request' and not path.startswith(('candidate/', 'artifacts/', 'evidence/', 'views/')),
                             'original sources cannot use request, generated-output or submission-evidence namespaces')
                files['sources/' + path] = gate.store_file(data, root.parent / '.econ-objects')
        files['review-plan.json'] = (gate.regular_bytes(review_plan) if review_plan else
                                     gate.canonical(_default_review_plan(files, manifest, assets)))
        active_conditions = set(conditions or ())
        if _review_plan(files) != 'direct':
            active_conditions.add('delegation_active')
        if any(row['kind'] == 'artifact' for row in _contract(contract_raw, request_raw)):
            active_conditions.add('requested_artifact_files')
        if active_conditions != set(conditions or ()):
            _, catalog, assets = _policy(operation=operation, conditions=sorted(active_conditions),
                                          profile=profile, templates=templates or ())
            manifest = policy.select_manifest(catalog, assets, operation, conditions=sorted(active_conditions),
                                              profile=profile, templates=templates or ())
            manifest_raw = policy.canonical(manifest)
            files['policy-manifest.json'] = manifest_raw
        _validate_review_plan(files['review-plan.json'], files, manifest, assets)
        if mode == 'provisional':
            gate.require(provisional_selection is not None, 'provisional requires a recorded user selection')
            selection_raw = gate.regular_bytes(provisional_selection)
            _selection(selection_raw)
            files['provisional-selection.json'] = selection_raw
        else:
            gate.require(provisional_selection is None, 'strict run cannot carry a provisional selection')
        release_assurance = release_assurance or 'host-authenticated'
        gate.require(release_assurance in {'host-authenticated', 'host-observed'}, 'unknown release assurance class')
        run = {'schema_version': 2, 'run_id': str(uuid.uuid4()), 'mode': mode, 'author_id': author_id,
               'release_assurance': release_assurance,
               'policy_id': manifest['policy_id'], 'policy_manifest_sha256': gate.sha(manifest_raw),
               'files': {path: gate.content_record(data) for path, data in files.items()}}
        if release_adapter is not None:
            run['release_adapter'] = _adapter_binding(release_adapter)
        if hook_context is not None:
            run['hook_binding'] = hooks.load_context(hook_context, root, request_raw, __file__, run['policy_id'])
        run_raw = gate.canonical(run)
        gate.release({**files, 'run.json': run_raw}, root)
        if hook_context is not None:
            hooks.bind_task_run(hook_context, root, request_raw, gate.sha(contract_raw), run['run_id'])
        _apply_run_records(root, run_raw, run, files)
    if coverage_review is not None:
        review_raw = gate.regular_bytes(coverage_review)
        _coverage(review_raw, run, files)
        coverage_path = root / 'coverage'
        if coverage_path.exists():
            previous = files.get('current-coverage.json')
            previous = gate.regular_bytes(coverage_path / 'report.json') if previous is None else previous
            if previous != review_raw:
                _append_run_record(root, run, 'coverage', review_raw, expected_record_sha256)
                root, run_raw, run, files, manifest = _load_run(root)
        else:
            gate.require(not (root / 'submissions').exists(), 'coverage must be fixed before the first candidate submission')
            gate.release({'report.json': review_raw}, coverage_path)
    if resource_reads is not None:
        reads_raw = gate.regular_bytes(resource_reads)
        _resource_reads(reads_raw, files)
        _append_run_record(root, run, 'resource-reads', reads_raw, expected_record_sha256)
        root, run_raw, run, files, manifest = _load_run(root)
    coverage = _coverage_bytes(root, run, files)
    result = _status(run, files, coverage=coverage)
    if coverage is not None and all(value == 'available' or name in result['fulfilled_capabilities'] for name, value in result['capability_statuses'].items()):
        result['status'] = 'requirements-fixed'
    result.update(run_sha256=gate.sha(run_raw), review_plan_sha256=gate.sha(files['review-plan.json']),
                  request_sha256=gate.sha(files['request.txt']),
                  contract_sha256=gate.sha(files['requirements.json']),
                  policy_manifest_sha256=run['policy_manifest_sha256'],
                  reported_capabilities=gate.parse_json(files.get('current-capabilities.json', files['capabilities.json'])),
                  profile=manifest['profile'])
    return _with_instructions(result, manifest, request_text=files['request.txt'].decode('utf-8'), restore=True)


def _check(run, files, candidate_name, candidate_bytes, artifacts, events, reports, views, coverage, evidence=None, view_files=None, *, surface='final'):
    gate.require(run['mode'] != 'strict' or coverage is not None,
                 'strict candidate checks require pre-candidate coverage')
    evidence = {} if evidence is None else evidence
    if evidence:
        gate.require('manifest.json' in evidence, 'additional evidence requires manifest.json')
        manifest = gate.parse_json(evidence['manifest.json'])
        gate.require(isinstance(manifest, dict) and set(manifest) ==
                     {'schema_version', 'run_id', 'evidence_sources'}
                     and type(manifest['schema_version']) is int and manifest['schema_version'] == 1
                     and manifest['run_id'] == run['run_id'], 'evidence manifest differs from this run')
    candidate_reports = gate.parse_json(reports)
    if coverage is not None and isinstance(candidate_reports, dict):
        preflight = gate.parse_json(coverage)
        coverage_refs = tuple(preflight.get(field) for field in ('launch_ref', 'return_ref') if native._text(preflight.get(field)))
        records = candidate_reports.get('reports')
        if isinstance(records, list):
            for report in records:
                if isinstance(report, dict):
                    for field in ('launch_ref', 'return_ref'):
                        gate.require(report.get(field) not in coverage_refs,
                                     'candidate ' + str(report.get('role')) + ' ' + field
                                     + ' reuses a pre-candidate coverage event reference')
    return native.check_native(candidate_name, candidate_bytes, files['request.txt'],
                               files['requirements.json'], artifacts, events, files['dictionary.json'],
                               _author(run), gate.sha(files['request.txt']),
                               gate.sha(files['requirements.json']), gate.sha(candidate_bytes),
                               candidate_reports, gate.parse_json(views), run_id=run['run_id'],
                               review_plan=_review_plan(files),
                               review_definition=_review_definition(files),
                               view_files=view_files, surface=surface,
                               sources={**{path[len('sources/'):]: data for path, data in files.items()
                                           if path.startswith('sources/')},
                                        **{'evidence/' + path: data for path, data in evidence.items()}})


def _check_dependency_sha256(run, files, name, body, artifacts, events, reports, views, coverage,
                             evidence=None, view_files=None, *, surface='final'):
    """Only values consumed by _check; delivery/read-cache state is not a dependency."""
    fixed = {key: gate.sha(data) for key, data in files.items()
             if key in {'request.txt', 'requirements.json', 'dictionary.json', 'review-plan.json'}
             or key.startswith('sources/')}
    return gate.sha(gate.canonical({'schema_version': 1, 'surface': surface,
        'run_id': run['run_id'], 'mode': run['mode'], 'author_id': _author(run),
        'policy_manifest_sha256': run['policy_manifest_sha256'], 'checker_sources': LOADED_SOURCE_HASHES,
        'fixed': fixed, 'candidate_name': name, 'candidate_sha256': gate.sha(body),
        'artifacts': {key: gate.sha(value) for key, value in sorted(artifacts.items())},
        'events_sha256': gate.sha(events), 'reports_sha256': gate.sha(reports),
        'views_sha256': gate.sha(views), 'coverage_sha256': gate.sha(coverage) if coverage is not None else None,
        'evidence': {key: gate.sha(value) for key, value in sorted((evidence or {}).items())},
        'view_files': {key: gate.sha(value) for key, value in sorted((view_files or {}).items())}}))


def _state_binding(state_file, state_task, state_root, snapshot, source_paths=None, retained=None,
                   verified_inputs=None, policy_selection=None):
    if state_file is None and state_task is None:
        gate.require(state_root is None, 'state-root requires state-file and state-task')
        return None
    gate.require(state_file is not None and native._text(state_task), 'state-file and state-task must be supplied together')
    gate.require(isinstance(policy_selection, dict), 'state binding requires the adopted policy selection')
    policy_root, _, manifest, _ = policy.discover_policy(__file__, **policy_selection)
    gate.require('state' in manifest['assets'],
                 'state use requires requested_local_state_helper_operation at begin; begin a new run with that condition')
    state = _sibling('run_state', policy_root / manifest['assets']['state']['path'])
    root = _safe_directory(state_root or Path.cwd())
    store = Path(state_file).absolute()
    state_raw = gate.regular_bytes(store)
    data = gate.parse_json(state_raw)
    validated_hashes = {}
    def validated_digest(path):
        path = Path(path).absolute()
        digest = gate.sha(gate.file_snapshot(path))
        key = str(path)
        gate.require(key not in validated_hashes or validated_hashes[key] == digest,
                     'state input changed during validation: ' + key)
        validated_hashes[key] = digest
        return digest
    state.digest = validated_digest
    tasks = data['tasks']
    task = tasks[state_task]
    context_file = (root / state.relative(root, task['task_context_ref']['path'])
                    if task.get('task_context_ref') else None)
    if context_file is not None:
        validated_digest(context_file)
    gate.require(not task.get('holds') and not state.input_changes(root, task)
                 and not state.context_changes(root, task)
                 and not state.output_changes(root, task) and state.consumed_current(root, tasks, task)
                 and state.contract_current(root, task)
                 and all(state.receipt_current(root, task, row) for row in task.get('action_results', [])),
                 'registered state inputs, outputs, dependencies, or holds require attention')
    if context_file is not None:
        validated_digest(context_file)
    gate.require(task['outputs'], 'state task needs registered outputs')
    mappings = []
    for output_id, row in sorted(task['outputs'].items()):
        if retained is not None:
            matching = [item['native_path'] for item in retained['outputs'] if item['output_id'] == output_id]
        elif row['kind'] == 'file':
            actual = (root / state.relative(root, output_id)).absolute()
            matching = [path for path, source in source_paths.items() if Path(source).absolute() == actual]
            artifact_matches = [path for path in matching if path.startswith('artifacts/')]
            if len(artifact_matches) == 1:
                matching = artifact_matches
        elif row['kind'] == 'message' and isinstance(row.get('value'), str):
            matching = [path for path, raw in snapshot.items()
                        if path.startswith('candidate/') and raw == row['value'].encode('utf-8')]
        else:
            raise ValueError('state output has no supported exact snapshot correspondence: ' + output_id)
        gate.require(len(matching) == 1 and matching[0] in snapshot,
                     'state output needs one exact candidate/artifact correspondence: ' + output_id)
        path = matching[0]
        if row['kind'] == 'file':
            state.relative(root, output_id)
            gate.require(gate.sha(gate.file_snapshot(root / output_id)) == gate.sha(snapshot[path])
                         and row['version'] == gate.sha(snapshot[path]), 'state file version differs from snapshot')
        elif row['kind'] == 'message':
            gate.require(row['value'].encode('utf-8') == snapshot[path]
                         and row['version'] == state.content_version(row), 'state message differs from snapshot')
        else:
            raise ValueError('unsupported registered output kind: ' + str(row['kind']))
        mappings.append({'output_id': output_id, 'kind': row['kind'], 'state_output_version': row['version'],
                         'native_path': path, 'native_file_sha256': gate.sha(snapshot[path])})
    candidate_paths = [path for path in snapshot if path.startswith('candidate/')]
    gate.require(len(candidate_paths) == 1, 'exactly one native candidate required')
    result = {'state_file': str(store), 'state_root': str(root), 'task_id': state_task,
              'state_candidate_sha256': state.content_hash(state.candidate(task)),
              'native_candidate_file_sha256': gate.sha(snapshot[candidate_paths[0]]), 'outputs': mappings}
    gate.require(retained is None or result == retained, 'registered state candidate or output mapping changed')
    if verified_inputs is not None:
        verified_inputs.update(validated_hashes)
    return result


@_serialize_run
def submit_run(run_dir, candidate, artifacts, events, reports=None, text_views=None,
               state_file=None, state_task=None, state_root=None, evidence=None, views=None, surface='final'):
    root, run_raw, run, files, manifest = _load_run(run_dir)
    coverage = _coverage_bytes(root, run, files)
    if run['mode'] == 'strict' and coverage is None:
        prerequisites = _status(run, files, coverage=coverage)
        return _with_instructions(prerequisites, manifest, request_text=files['request.txt'].decode('utf-8'), restore=True)
    name, candidate_raw = Path(candidate).name, gate.regular_bytes(candidate)
    gate.safe_relative(name)
    artifact_bytes = native._collect_artifacts(artifacts)
    event_raw = gate.regular_bytes(events)
    report_raw = gate.regular_bytes(reports) if reports else gate.canonical(EMPTY_REPORTS)
    view_raw = gate.regular_bytes(text_views) if text_views else b'{}'
    evidence_bytes = native._collect_artifacts(evidence) if evidence is not None else {}
    internal_views = native._collect_artifacts(views) if views is not None else {}
    check = _check(run, files, name, candidate_raw, artifact_bytes, event_raw, report_raw, view_raw, coverage, evidence_bytes, internal_views, surface=surface)
    snapshot = {'candidate/' + name: candidate_raw, 'events.json': event_raw,
                'reports.json': report_raw, 'text-views.json': view_raw, 'checks.json': gate.canonical(check),
                **{'artifacts/' + path: data for path, data in artifact_bytes.items()},
                **{'views/' + path: data for path, data in internal_views.items()},
                **{'evidence/' + path: data for path, data in evidence_bytes.items()}}
    sources = {'candidate/' + name: Path(candidate).absolute(),
               **{'artifacts/' + path: Path(artifacts).absolute() / path for path in artifact_bytes}}
    state_binding = _state_binding(state_file, state_task, state_root, snapshot, sources,
                                   policy_selection=manifest['selection'])
    descriptor = {'schema_version': 1, 'run_sha256': gate.sha(run_raw), 'candidate_name': name,
                  'state_binding': state_binding,
                  'coverage_sha256': gate.sha(coverage) if coverage is not None else None,
                  'files': {path: gate.content_record(data) for path, data in sorted(snapshot.items())}}
    descriptor['check_dependencies_sha256'] = _check_dependency_sha256(
        run, files, name, candidate_raw, artifact_bytes, event_raw, report_raw, view_raw, coverage, evidence_bytes, internal_views, surface=surface)
    if surface != 'final':
        descriptor['surface'] = surface
    descriptor_raw = gate.canonical(descriptor)
    sid = gate.sha(descriptor_raw)
    submissions = root / 'submissions'
    submissions.mkdir(exist_ok=True)
    _safe_directory(submissions)
    target = submissions / sid
    payload = {**snapshot, 'submission.json': descriptor_raw}
    if target.exists():
        gate.require(all(gate.sha(gate.file_snapshot(target / path)) == gate.sha(data) for path, data in payload.items()),
                     'existing content-addressed submission differs')
    else:
        gate.release(payload, target)
    if 'hook_binding' in run:
        hooks.save_record(root / 'hook-submission.json', {'submission_sha256': sid})
    result = _status(run, files, check, coverage)
    result.update(submission_sha256=sid, candidate_file_sha256=gate.sha(candidate_raw),
                  state_binding=state_binding, checks=check)
    return _with_instructions(result, manifest, request_text=files['request.txt'].decode('utf-8'), restore=True)


@_serialize_run
def current_status(run_dir, submission_sha256=None, *, restore_instructions=False):
    root, raw, run, files, manifest = _load_run(run_dir)
    coverage = _coverage_bytes(root, run, files)
    sid = submission_sha256
    if sid is None and (root / 'hook-submission.json').is_file():
        pointer = gate.parse_json(gate.regular_bytes(root / 'hook-submission.json'))
        gate.require(isinstance(pointer, dict) and set(pointer) == {'submission_sha256'}, 'invalid submission pointer')
        sid = pointer['submission_sha256']
    if sid is None:
        state = _status(run, files, coverage=coverage)
        state['needed_actions'].append({'action': 'submit'})
        if coverage is not None and all(value == 'available' or name in state['fulfilled_capabilities']
                for name, value in state['capability_statuses'].items()):
            state['status'] = 'requirements-fixed'
    else:
        gate.require(gate.hexhash(sid), 'invalid submission hash')
        directory = _safe_directory(root / 'submissions' / sid)
        descriptor_raw = gate.regular_bytes(directory / 'submission.json')
        gate.require(gate.sha(descriptor_raw) == sid, 'submission descriptor changed')
        descriptor = gate.parse_json(descriptor_raw)
        gate.require(descriptor['run_sha256'] == gate.sha(raw), 'submission belongs to another run')
        gate.require(descriptor['coverage_sha256'] == (gate.sha(coverage) if coverage is not None else None),
                     'pre-candidate coverage changed after submission; resubmit the current candidate')
        snapshot = _read_map(directory, descriptor['files'])
        binding = descriptor.get('state_binding')
        if binding is not None:
            _state_binding(binding['state_file'], binding['task_id'], binding['state_root'], snapshot,
                           retained=binding, policy_selection=manifest['selection'])
        name = gate.safe_relative(descriptor['candidate_name'])
        gate.require('/' not in name, 'candidate must have a basename')
        body = snapshot['candidate/' + name]
        artifacts = {key[10:]: value for key, value in snapshot.items() if key.startswith('artifacts/')}
        evidence = {key[9:]: value for key, value in snapshot.items() if key.startswith('evidence/')}
        view_files = {key[6:]: value for key, value in snapshot.items() if key.startswith('views/')}
        surface = descriptor.get('surface', 'final')
        dependencies = _check_dependency_sha256(run, files, name, body, artifacts,
            snapshot['events.json'], snapshot['reports.json'], snapshot['text-views.json'], coverage,
            evidence, view_files, surface=surface)
        reused = descriptor.get('check_dependencies_sha256') == dependencies
        cache = None
        if not reused:
            try:
                cached = gate.parse_json(gate.regular_bytes(root / 'current-checks.json'))
                if (isinstance(cached, dict) and cached.get('schema_version') == 1
                        and cached.get('dependencies_sha256') == dependencies
                        and isinstance(cached.get('checks'), dict)
                        and cached.get('checks_sha256') == gate.sha(gate.canonical(cached['checks']))):
                    cache = cached['checks']
            except (OSError, ValueError, TypeError):
                pass  # A disposable cache miss reruns the actual checker.
        if reused:
            check = gate.parse_json(snapshot['checks.json'])
        elif cache is not None:
            check, reused = cache, True
        else:
            check = _check(run, files, name, body, artifacts,
                snapshot['events.json'], snapshot['reports.json'], snapshot['text-views.json'], coverage,
                evidence, view_files, surface=surface)
            hooks.save_record(root / 'current-checks.json', {'schema_version': 1,
                'dependencies_sha256': dependencies, 'checks_sha256': gate.sha(gate.canonical(check)), 'checks': check})
        state = _status(run, files, check, coverage)
        state.update(submission_sha256=sid, candidate_file_sha256=gate.sha(body), checks=check,
                     check_reused=reused, check_dependencies_sha256=dependencies)
    state['policy_manifest'] = manifest
    return _with_instructions(state, manifest,
        request_text=files['request.txt'].decode('utf-8') if restore_instructions else None,
        restore=restore_instructions)


def _release_context(run, files, check, coverage, submission_sha256, artifacts, reports, status):
    # All values derive from verified saved bytes. None is an authentication flag.
    envelope = gate.parse_json(reports)
    return {'mode': run['mode'], 'status': status, 'review_plan': _review_plan(files),
            'adopted_assurance_class': run.get('release_assurance', 'host-authenticated'),
            'release_adapter': run.get('release_adapter'),
            'surface': check.get('surface_check', {}).get('surface', 'final'),
            'author_id': _author(run), 'run_id': run['run_id'], 'policy_id': run['policy_id'],
            'request_sha256': gate.sha(files['request.txt']),
            'contract_sha256': gate.sha(files['requirements.json']),
            'policy_manifest_sha256': run['policy_manifest_sha256'],
            'candidate_sha256': check.get('bindings', {}).get('candidate_sha256'),
            **{field: check.get('bindings', {}).get(field) for field in
               ('events_sha256', 'dictionary_sha256', 'artifacts_sha256', 'text_views_sha256', 'sources_sha256')},
            'submission_sha256': submission_sha256,
            'coverage_sha256': gate.sha(coverage) if coverage is not None else None,
            'dictionary_rule_count': len(gate.parse_json(files['dictionary.json'])['rules']),
            'capability_statuses': _capability_statuses(files),
            'artifact_hashes': [{'path': path, 'sha256': gate.sha(data), 'size_bytes': len(data)}
                                for path, data in sorted(artifacts.items())],
            'coverage_review': gate.parse_json(coverage) if coverage is not None else {},
            'review_records': envelope.get('reports', [])}


def _adapter_binding(value):
    if value is None:
        return None
    fields = {'adapter_id', 'version', 'connection', 'output_channel'}
    gate.require(isinstance(value, dict) and set(value) == fields
                 and all(native._text(value[key]) for key in fields), 'invalid release adapter binding')
    return dict(value)


def _release_verifier():
    """Reserved host-owned integration; no authenticated adapter is installed.

    Future integration requires an explicit implementation using independently
    retrieved host events. There is no public setter or caller-supplied adapter.
    """
    return None


def _release_summary(check):
    # Originals and claim quotations remain internal; they can contain the
    # complete unapproved candidate even when final_message is absent.
    return {'status': check.get('status'),
            'recorded_checks_complete': check.get('recorded_checks_complete', False),
            'executed_checks': check.get('executed_checks', []),
            **{key: [{'check': row.get('check')} for row in check.get(key, [])]
               for key in ('failed_checks', 'missing_checks', 'unresolved')}}


def verify_release(run_dir, submission_sha256):
    """Read-only publication eligibility; no candidate body, output or receipt."""
    return finalize_run(run_dir, submission_sha256, check_only=True)


def verify_surface_release(run_dir, submission_sha256):
    """Release only a reviewed outgoing surface; retain the parent task state."""
    return finalize_run(run_dir, submission_sha256, check_only=True, _surface_only=True)


@_serialize_run
def finalize_run(run_dir, submission_sha256, output=None, verify_only=False, expected_hook_binding=None,
                 *, check_only=False, _surface_only=False):
    gate.require(not _surface_only or (check_only and output is None and not verify_only),
                 'surface verification cannot write final outputs')
    root, run_raw, run, files, manifest = _load_run(run_dir)
    gate.require(gate.hexhash(submission_sha256), 'submission SHA-256 required')
    if 'hook_binding' in run:
        gate.require(gate.parse_json(gate.regular_bytes(root / 'hook-submission.json'))
                     == {'submission_sha256': submission_sha256}, 'a newer candidate was submitted')
    if verify_only:
        gate.require(run['mode'] == 'strict' and run.get('hook_binding') == expected_hook_binding
                     and expected_hook_binding is not None, 'verification requires the current strict host binding')
    coverage = _coverage_bytes(root, run, files)
    if run['mode'] == 'strict' and coverage is None:
        prerequisites = _status(run, files, coverage=coverage)
        prerequisites.update(status='blocked-unapproved')
        return _with_instructions(prerequisites, manifest, request_text=files['request.txt'].decode('utf-8'), restore=True)
    snapshot_root = _safe_directory(root / 'submissions' / submission_sha256)
    descriptor_raw = gate.regular_bytes(snapshot_root / 'submission.json')
    gate.require(gate.sha(descriptor_raw) == submission_sha256, 'submission descriptor changed')
    descriptor = gate.parse_json(descriptor_raw)
    descriptor_fields = {'schema_version', 'run_sha256', 'candidate_name', 'coverage_sha256', 'state_binding', 'files'}
    gate.require(descriptor_fields <= set(descriptor) and set(descriptor) <= descriptor_fields | {'check_dependencies_sha256', 'surface'}
                 and type(descriptor['schema_version']) is int and descriptor['schema_version'] == 1
                 and descriptor['run_sha256'] == gate.sha(run_raw), 'submission does not match fixed run')
    snapshot = _read_map(snapshot_root, descriptor['files'])
    name = gate.safe_relative(descriptor['candidate_name'])
    gate.require('/' not in name, 'candidate must have a basename')
    expected = {'candidate/' + name, 'events.json', 'reports.json', 'text-views.json', 'checks.json'}
    gate.require(expected <= set(snapshot) and all(path in expected or path.startswith(('artifacts/', 'evidence/', 'views/')) for path in snapshot),
                 'invalid submission file set')
    coverage = _coverage_bytes(root, run, files)
    gate.require(descriptor['coverage_sha256'] == (gate.sha(coverage) if coverage is not None else None),
                 'pre-candidate coverage changed after submission')
    artifacts = {path[len('artifacts/'):]: data for path, data in snapshot.items() if path.startswith('artifacts/')}
    binding = descriptor['state_binding']
    if binding is not None:
        _state_binding(binding['state_file'], binding['task_id'], binding['state_root'], snapshot, retained=binding,
                       policy_selection=manifest['selection'])
    surface = descriptor.get('surface', 'final')
    gate.require((surface in native.SURFACES and surface != 'final') if _surface_only else surface == 'final',
                 'requested release route does not match the saved surface')
    check = _check(run, files, name, snapshot['candidate/' + name], artifacts,
                   snapshot['events.json'], snapshot['reports.json'], snapshot['text-views.json'], coverage,
                   {path[len('evidence/'):]: data for path, data in snapshot.items() if path.startswith('evidence/')},
                   {path[len('views/'):]: data for path, data in snapshot.items() if path.startswith('views/')},
                   surface=surface)
    gate.require(snapshot['checks.json'] == gate.canonical(check), 'mechanical result changed on the pinned snapshot')
    result = _status(run, files, check, coverage)
    result.update(submission_sha256=submission_sha256, candidate_file_sha256=gate.sha(snapshot['candidate/' + name]),
                  state_binding=binding, checks=check)
    release_context = _release_context(run, files, check, coverage, submission_sha256, artifacts,
                                       snapshot['reports.json'], result['status'])
    host_verifier = _release_verifier()
    try:
        predicate = native.assert_surface_release_predicates if _surface_only else native.assert_release_predicates
        approval = predicate(release_context, check, host_verifier=host_verifier)
    except native.ReleaseBlocked as exc:
        result.update(status='blocked-unapproved', release_failures=exc.failures,
                      quarantine=str(snapshot_root), release_authorized=False, checks=_release_summary(check))
        result['needed_actions'].extend(exc.failures)
        return _with_instructions(result, manifest, request_text=files['request.txt'].decode('utf-8'), restore=True)
    if check_only:
        _, fresh_raw, fresh_run, fresh_files, _ = _load_run(root)
        gate.require(fresh_raw == run_raw, 'fixed run changed during release verification')
        fresh_coverage = _coverage_bytes(root, fresh_run, fresh_files)
        gate.require((gate.sha(fresh_coverage) if fresh_coverage is not None else None)
                     == descriptor['coverage_sha256'], 'coverage changed during release verification')
        gate.require(gate.regular_bytes(snapshot_root / 'submission.json') == descriptor_raw,
                     'submission changed during release verification')
        _read_map(snapshot_root, descriptor['files'])
        if binding is not None:
            _state_binding(binding['state_file'], binding['task_id'], binding['state_root'], snapshot,
                           retained=binding, policy_selection=manifest['selection'])
        result.update(status='surface-release-authorized' if _surface_only else 'release-authorized',
                      checks=_release_summary(check), **approval)
        if _surface_only:
            result.update(surface=surface, surface_message=snapshot['candidate/' + name].decode('utf-8'),
                          parent_unmet=check['surface_check']['parent_unmet'])
        return _with_instructions(result, manifest, request_text=files['request.txt'].decode('utf-8'), restore=True)
    gate.require(output is not None, 'publication output directory is required')
    # Recheck saved bytes and adopted assets before writing the in-memory snapshot.
    _load_run(root)
    gate.require(gate.regular_bytes(snapshot_root / 'submission.json') == descriptor_raw, 'submission changed during finalization')
    _read_map(snapshot_root, descriptor['files'])
    state_input_hashes = {}
    if binding is not None:
        _state_binding(binding['state_file'], binding['task_id'], binding['state_root'], snapshot,
                       retained=binding, verified_inputs=state_input_hashes, policy_selection=manifest['selection'])
    classification = ('finalized-host-observed' if approval.get('assurance_class') == 'host-observed'
                      else 'finalized-approved')
    metadata = {'schema_version': 1, 'run_id': run['run_id'], 'classification': classification,
                'output': str(Path(output).absolute()),
                'mode': run['mode'], 'review_plan': _review_plan(files), 'policy_id': run['policy_id'],
                'policy_manifest_sha256': run['policy_manifest_sha256'],
                'request_sha256': release_context['request_sha256'],
                'contract_sha256': release_context['contract_sha256'],
                'coverage_sha256': release_context['coverage_sha256'],
                'artifact_hashes': release_context['artifact_hashes'],
                'submission_sha256': submission_sha256,
                'state_binding': binding,
                'candidate_file_sha256': result['candidate_file_sha256'],
                **approval, 'capability_statuses': result['capability_statuses'],
                'required_checks_status': check['status'], 'needed_actions': result['needed_actions']}
    contract_rows = _contract(files['requirements.json'], files['request.txt'])
    selected = {row['path'] for row in contract_rows if row['kind'] == 'artifact'}
    output_bytes = {path: artifacts[path] for path in selected}
    deliverables = [{'path': path, 'sha256': gate.sha(data), 'size_bytes': len(data)}
                    for path, data in sorted(output_bytes.items())]
    metadata['deliverables'] = deliverables
    if 'hook_binding' in run:
        metadata.update(hook_binding=run['hook_binding'])
    input_hashes = {str(root / 'run.json'): gate.sha(run_raw),
                    str(snapshot_root / 'submission.json'): submission_sha256,
                    **{str(root / path): gate.record_hash(sha) for path, sha in run['files'].items()},
                    **{str(snapshot_root / path): gate.record_hash(sha) for path, sha in descriptor['files'].items()}}
    if coverage is not None:
        input_hashes[run.get('_coverage_path', str(root / 'coverage/report.json'))] = descriptor['coverage_sha256']
    input_hashes.update(run.get('_record_files', {}))
    policy_root, policy_raw, current_manifest, current_assets = policy.discover_policy(__file__, **manifest['selection'])
    gate.require(policy.select_manifest(current_manifest, current_assets, **manifest['selection']) == manifest,
                 'adopted policy changed before staging; begin a new run and obtain new reviews')
    input_hashes.update({str(policy_root / item['path']): item['sha256']
                         for item in manifest['assets'].values()})
    if binding is not None:
        input_hashes.update(state_input_hashes)
        input_hashes.update({str(Path(binding['state_root']) / row['output_id']): row['native_file_sha256']
                             for row in binding['outputs'] if row['kind'] == 'file'})
    def revalidate():
        _, fresh_raw, fresh_run, fresh_files, _ = _load_run(root)
        gate.require(fresh_raw == run_raw, 'fixed run changed during staging')
        fresh_coverage = _coverage_bytes(root, fresh_run, fresh_files)
        gate.require((gate.sha(fresh_coverage) if fresh_coverage is not None else None) == descriptor['coverage_sha256'],
                     'coverage changed during staging')
        fresh_check = _check(fresh_run, fresh_files, name, snapshot['candidate/' + name], artifacts,
                            snapshot['events.json'], snapshot['reports.json'], snapshot['text-views.json'], fresh_coverage,
                            {path[len('evidence/'):]: data for path, data in snapshot.items() if path.startswith('evidence/')},
                            {path[len('views/'):]: data for path, data in snapshot.items() if path.startswith('views/')})
        gate.require(gate.canonical(fresh_check) == snapshot['checks.json'], 'current inputs change the completed checks')
        refreshed_approval = native.assert_release_predicates(
            _release_context(fresh_run, fresh_files, fresh_check, fresh_coverage,
                             submission_sha256, artifacts, snapshot['reports.json'],
                             _status(fresh_run, fresh_files, fresh_check, fresh_coverage)['status']),
            fresh_check, host_verifier=host_verifier)
        gate.require(refreshed_approval == approval,
                     'host approval changed during staging; obtain approval for the current snapshot')
        if binding is not None:
            try:
                _state_binding(binding['state_file'], binding['task_id'], binding['state_root'], snapshot,
                               retained=binding, policy_selection=manifest['selection'])
            except (ValueError, OSError) as exc:
                raise ValueError('state input changed during staging: ' + str(exc)) from exc
    def verify_outputs():
        current = native._collect_artifacts(output)
        extra, missing = set(current) - set(output_bytes), set(output_bytes) - set(current)
        gate.require(not extra and not missing,
                     'finalized attachment set differs: extra=' + repr(sorted(extra)) + '; missing=' + repr(sorted(missing)))
        for path, data in output_bytes.items():
            gate.require(gate.content_record(current[path]) == gate.content_record(data),
                         'finalized attachment size or SHA-256 differs: ' + path)
    if verify_only:
        checked_record = {**metadata, 'classification': 'checked-record-consistent'}
        record_path = root / 'finalizations' / gate.sha(gate.canonical(checked_record))
        gate.require(gate.regular_bytes(record_path / 'published.json') == gate.canonical(metadata),
                     'successful finalization evidence is missing')
        receipt = {'submission_sha256': submission_sha256, 'output': metadata['output'],
                   'metadata_sha256': gate.sha(gate.canonical(metadata))}
        gate.require(gate.parse_json(gate.regular_bytes(root / 'hook-finalization.json')) == receipt,
                     'finalization receipt differs')
        verify_outputs()
        gate.recheck_inputs(input_hashes)
        revalidate()
        verify_outputs()
    else:
        records = root / 'finalizations'
        records.mkdir(exist_ok=True)
        _safe_directory(records)
        checked_record = {**metadata, 'classification': 'checked-record-consistent'}
        record_bytes = gate.canonical(checked_record)
        record_path = records / gate.sha(record_bytes)
        retained = record_path.exists()
        output_exists = Path(output).exists() or Path(output).is_symlink()
        if retained:
            gate.require(gate.regular_bytes(record_path / 'native-result.json') == record_bytes,
                         'retained finalization check differs')
        else:
            gate.require(not output_exists,
                         'existing output has no matching prior finalization record: ' + str(output))
            gate.release({'native-result.json': record_bytes}, record_path)
        if output_exists:
            # Only the exact output fixed before publication is recoverable.
            # Never adopt an unrelated pre-existing directory, even with equal bytes.
            verify_outputs()
            gate.recheck_inputs(input_hashes)
            revalidate()
            verify_outputs()
        else:
            gate.release(output_bytes, output, input_hashes=input_hashes, validate_inputs=revalidate)
        hooks.save_record(record_path / 'published.json', metadata, replace=False)
        if 'hook_binding' in run:
            receipt = {
                'submission_sha256': submission_sha256, 'output': metadata['output'],
                'metadata_sha256': gate.sha(gate.canonical(metadata))}
            receipt_path = root / 'hook-finalization.json'
            previous = gate.parse_json(gate.regular_bytes(receipt_path)) if receipt_path.exists() else None
            if previous is not None and previous.get('submission_sha256') == submission_sha256:
                gate.require(previous == receipt, 'existing receipt conflicts with this finalization')
            if previous != receipt:
                hooks.save_record(receipt_path, receipt)
    result.update(**approval)
    result.update(status=classification, output=str(Path(output).absolute()), deliverables=deliverables,
                  final_message=snapshot['candidate/' + name].decode('utf-8'))
    return _with_instructions(result, manifest, request_text=files['request.txt'].decode('utf-8'), restore=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    begin = subs.add_parser('begin')
    begin.add_argument('--run-dir', required=True)
    for field in ('request', 'requirements', 'author-id', 'provisional-selection', 'capabilities',
                  'coverage-review', 'operation', 'profile', 'sources', 'review-plan', 'resource-reads', 'hook-context'):
        begin.add_argument('--' + field)
    begin.add_argument('--expected-record-sha256', help='Current context record returned by begin, for append-only capability or coverage updates')
    begin.add_argument('--condition', dest='conditions', action='append')
    begin.add_argument('--template', dest='templates', action='append')
    begin.add_argument('--mode', choices=('strict', 'provisional'))
    begin.add_argument('--release-assurance', choices=('host-authenticated', 'host-observed'))
    submit = subs.add_parser('submit')
    for field in ('run-dir', 'candidate', 'artifacts', 'events'):
        submit.add_argument('--' + field, required=True)
    for field in ('reports', 'text-views', 'state-file', 'state-task', 'state-root', 'evidence', 'views'):
        submit.add_argument('--' + field)
    submit.add_argument('--surface', choices=('final', 'progress', 'status', 'error'), default='final')
    finalize = subs.add_parser('finalize')
    for field in ('run-dir', 'submission-sha256', 'output'):
        finalize.add_argument('--' + field, required=True)
    verify = subs.add_parser('release-check')
    verify.add_argument('--run-dir', required=True)
    verify.add_argument('--submission-sha256', required=True)
    status = subs.add_parser('status')
    status.add_argument('--run-dir', required=True)
    status.add_argument('--submission-sha256')
    status.add_argument('--restore-instructions', action='store_true')
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        result = {'begin': begin_run, 'submit': submit_run, 'finalize': finalize_run,
                  'release-check': verify_release, 'status': current_status}[command](**args)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        result = {'status': 'blocked', 'error': str(exc), 'worker_launches': 0, 'release_authorized': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['status'] in {'blocked', 'blocked-unapproved', 'quarantined-unapproved'} else 0


if __name__ == '__main__':
    sys.exit(main())
