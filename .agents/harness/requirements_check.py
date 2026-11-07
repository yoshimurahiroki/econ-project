#!/usr/bin/env python3
"""Evaluate registered artifact, action, content, prohibition, and evidence requirements."""
import argparse
import hashlib
import io
import json
import math
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

_FILE_RUNTIME = None

def _file_runtime():
    global _FILE_RUNTIME
    if _FILE_RUNTIME is not None:
        return _FILE_RUNTIME
    import importlib.util
    for filename in ('local_checks.py', 'LOCAL_CHECKS.py'):
        path = Path(__file__).resolve().with_name(filename)
        if path.is_file():
            spec = importlib.util.spec_from_file_location('requirements_file_runtime', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _FILE_RUNTIME = module
            return module
    raise ImportError('Missing sibling dependency: local_checks.py or LOCAL_CHECKS.py')


LIMITATION = ('Checks compare the explicit contract, final message bytes, artifact bytes, evaluator results and final action records. '
              'Retain the contract hash and match action records to actual tool returns and permissions.')
TYPES = {'text', 'json', 'pdf', 'zip', 'docx', 'pptx', 'xlsx', 'binary'}
MAX_ZIP_MEMBERS = 10000
MAX_ZIP_UNCOMPRESSED = 64 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
CONDITION_KINDS = {'content', 'prohibition', 'evidence'}
def digest(data):
    if isinstance(data, io.BufferedIOBase):
        value, position = hashlib.sha256(), data.tell()
        data.seek(0)
        for chunk in iter(lambda: data.read(1024 * 1024), b''):
            value.update(chunk)
        data.seek(position)
        return value.hexdigest()
    return hashlib.sha256(data).hexdigest()

def _content(data):
    return isinstance(data, bytes) or (isinstance(data, io.BufferedIOBase)
        and getattr(data, 'snapshot_kind', None) == 'fixed-file-v1'
        and data.readable() and not data.writable() and data.seekable())

def _object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('duplicate JSON key: ' + key)
        obj[key] = value
    return obj

def _json(data):
    # Native collection supplies verified fixed-file snapshots, not raw bytes.
    # Their decode method checks the retained version while reading all bytes;
    # do not pass a file object to json.loads or bypass that version check.
    if _content(data) and not isinstance(data, bytes):
        if len(data) > MAX_JSON_BYTES:
            raise ValueError('JSON input exceeds byte budget')
        data = data.decode('utf-8')
    if isinstance(data, bytes):
        if len(data) > MAX_JSON_BYTES:
            raise ValueError('JSON input exceeds byte budget')
        data = data.decode('utf-8')
    if isinstance(data, str) and len(data.encode('utf-8')) > MAX_JSON_BYTES:
        raise ValueError('JSON input exceeds byte budget')
    return json.loads(data, object_pairs_hook=_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('invalid JSON constant')))

def _string(value):
    return isinstance(value, str) and bool(value.strip())

def _safe_path(value):
    if (not _string(value) or '\\' in value or ':' in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        return False
    p = PurePosixPath(value)
    return not p.is_absolute() and all(x not in ('', '.', '..') for x in value.split('/'))

def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def _target(value):
    """Resolve the exact target syntax without URL decoding or path normalization."""
    if value == 'message://final':
        return 'message', None
    if not isinstance(value, str):
        raise ValueError('condition target must be a string')
    if value.startswith('artifact://'):
        path = value[len('artifact://'):]
        if not _safe_path(path) or any(char in path for char in '%?#'):
            raise ValueError('invalid canonical artifact target: ' + value)
        return 'artifact', path
    if not _safe_path(value) or any(char in value for char in '%?#'):
        raise ValueError('invalid condition target: ' + value)
    return 'artifact', value


def contract_sources(contract, request):
    """Resolve immutable inherited instructions; the current request stays exact."""
    if 'sources' not in contract:
        return {None: request.decode('utf-8')}
    if contract.get('schema_version') != 2 or not _string(contract.get('request_source_id')):
        raise ValueError('sources require v2 and an explicit request_source_id')
    rows, sources = contract['sources'], {}
    if not isinstance(rows, list) or not rows:
        raise ValueError('sources must be a nonempty array')
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'source_id', 'version', 'content_sha256', 'content'}:
            raise ValueError('source requires source_id, version, content_sha256 and exact content')
        sid, version, content = row['source_id'], row['version'], row['content']
        if (not _string(sid) or sid in sources or not isinstance(content, str)
                or not (_string(version) or type(version) is int and version >= 0)
                or row['content_sha256'] != digest(content.encode('utf-8'))):
            raise ValueError('invalid source identity, version or content digest')
        sources[sid] = content
    sid = contract['request_source_id']
    if sid not in sources or sources[sid].encode('utf-8') != request:
        raise ValueError('request_source_id must identify the exact current request bytes')
    return sources


def _source_spans(req, request_text, sources=None):
    """Use Unicode source coordinates, with an explicit ID for inherited text."""
    source_id = req.get('source_id')
    if sources is not None:
        if source_id not in sources:
            raise ValueError('unresolved or missing requirement source_id: ' + str(req.get('id')))
        request_text = sources[source_id]
    elif source_id is not None:
        raise ValueError('source_id requires registered sources')
    quote = req.get('source_text')
    if not _string(quote) or quote not in request_text:
        raise ValueError('unresolved user-text reference: ' + str(req.get('id')))
    binding = {'source_id': source_id} if source_id is not None else {}
    if 'source_span' in req:
        span = req['source_span']
        if (not isinstance(span, dict) or set(span) != {'start', 'end'}
                or type(span['start']) is not int or type(span['end']) is not int
                or not 0 <= span['start'] < span['end'] <= len(request_text)
                or request_text[span['start']:span['end']] != quote):
            raise ValueError('source_span must match source_text in source characters: ' + req['id'])
        return [{**span, **binding}]
    spans, start = [], 0
    while True:
        start = request_text.find(quote, start)
        if start < 0:
            return spans
        spans.append({'start': start, 'end': start + len(quote), **binding})
        start += 1


def requirement_spans(contract, request):
    sources = contract_sources(contract, request)
    return {req['id']: _source_spans(req, request.decode('utf-8'), sources if 'sources' in contract else None)
            for req in contract['requirements']}


def _pointer_tokens(pointer):
    if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')):
        raise ValueError('JSON pointer must be empty or begin with /')
    if re.search(r'~(?![01])', pointer):
        raise ValueError('invalid JSON pointer escape')
    return [part.replace('~1', '/').replace('~0', '~') for part in pointer.split('/')[1:]]


def _validate_condition(req, rid, base):
    if set(req) != base | {'target', 'evaluator', 'evidence_refs', 'status'}:
        raise ValueError('invalid condition fields: ' + rid)
    if not isinstance(req.get('evaluator'), dict):
        raise ValueError('condition evaluator must be an object: ' + rid)
    if req['evaluator'].get('type') == 'forbidden_operation':
        if not _string(req['target']):
            raise ValueError('operation prohibition requires an exact target: ' + rid)
    else:
        _target(req['target'])
    if req['status'] != 'pending':
        raise ValueError('frozen condition status must be pending: ' + rid)
    evaluator = req['evaluator']
    if not isinstance(evaluator, dict) or not _string(evaluator.get('type')):
        raise ValueError('condition evaluator must name a supported type: ' + rid)
    kind = evaluator['type']
    allowed = {
        'content': {'exact_sections', 'json_field', 'contains_literal'},
        'prohibition': {'forbidden_literal', 'forbidden_operation'},
        'evidence': {'evidence_refs'},
    }
    if kind not in allowed[req['kind']]:
        raise ValueError('unsupported evaluator for condition kind: ' + rid)
    fields = {'exact_sections': {'level', 'count'}, 'json_field': {'pointer'},
              'contains_literal': {'value'}, 'forbidden_literal': {'value'},
              'evidence_refs': set(), 'forbidden_operation': {'operation'}}[kind]
    if set(evaluator) != {'type'} | fields:
        raise ValueError('invalid evaluator fields: ' + rid)
    if kind == 'exact_sections':
        if (type(evaluator['level']) is not int or not 1 <= evaluator['level'] <= 6
                or type(evaluator['count']) is not int or evaluator['count'] < 0):
            raise ValueError('section level must be 1..6 and count a nonnegative integer: ' + rid)
    elif kind == 'json_field':
        _pointer_tokens(evaluator['pointer'])
    elif kind in {'contains_literal', 'forbidden_literal'}:
        if not _string(evaluator['value']):
            raise ValueError('literal must be a nonempty string: ' + rid)
    elif kind == 'forbidden_operation':
        if not _string(evaluator['operation']):
            raise ValueError('operation prohibition requires an exact operation: ' + rid)
    refs = req['evidence_refs']
    if not isinstance(refs, list) or (req['kind'] == 'evidence' and not refs):
        raise ValueError('evidence_refs must be an array, nonempty for evidence requirements: ' + rid)
    seen = set()
    for ref in refs:
        if (not isinstance(ref, dict) or set(ref) not in ({'path'}, {'path', 'id'})
                or not _safe_path(ref.get('path')) or ('id' in ref and not _string(ref['id']))):
            raise ValueError('invalid evidence file/id reference: ' + rid)
        identity = (ref['path'], ref.get('id'))
        if identity in seen:
            raise ValueError('duplicate evidence reference: ' + rid)
        seen.add(identity)


def validate_contract(contract, request):
    base = {'schema_version', 'request_sha256', 'requirements'}
    if (not isinstance(contract, dict) or set(contract) not in
            (base, base | {'sources', 'request_source_id'}, base | {'traceability'},
             base | {'sources', 'request_source_id', 'traceability'})):
        raise ValueError('contract requires schema_version, request_sha256, requirements and optional paired sources/request_source_id')
    if type(contract['schema_version']) is not int or contract['schema_version'] not in (1, 2):
        raise ValueError('unsupported schema_version')
    if 'traceability' in contract and contract['schema_version'] != 2:
        raise ValueError('traceability requires schema_version 2')
    if contract['request_sha256'] != digest(request):
        raise ValueError('request digest mismatch')
    request_text = request.decode('utf-8')
    sources = contract_sources(contract, request) if 'sources' in contract else None
    reqs = contract['requirements']
    if not isinstance(reqs, list) or not reqs:
        raise ValueError('requirements must be a nonempty array')
    ids, paths, actions, conditions = set(), set(), set(), set()
    for req in reqs:
        if not isinstance(req, dict):
            raise ValueError('requirement must be an object')
        rid = req.get('id')
        if not _string(rid) or rid in ids:
            raise ValueError('missing or duplicate requirement id')
        ids.add(rid)
        _source_spans(req, request_text, sources)
        base = {'id', 'source_text', 'kind'}
        if sources is not None:
            base.add('source_id')
        if 'source_span' in req:
            base.add('source_span')
        if req.get('kind') == 'artifact':
            allowed = base | {'path', 'file_type', 'nonempty', 'reject_placeholders'}
            if set(req) - allowed or not {'path', 'file_type'} <= set(req):
                raise ValueError('invalid artifact fields: ' + rid)
            path = req['path']
            if not _safe_path(path) or path in paths:
                raise ValueError('unsafe or duplicate artifact path: ' + rid)
            paths.add(path)
            if req['file_type'] not in TYPES:
                raise ValueError('unsupported artifact type: ' + rid)
            if type(req.get('nonempty', True)) is not bool:
                raise ValueError('nonempty must be boolean: ' + rid)
            placeholders = req.get('reject_placeholders', [])
            if not isinstance(placeholders, list) or any(not _string(x) for x in placeholders):
                raise ValueError('reject_placeholders must be text strings: ' + rid)
            if placeholders and req['file_type'] not in {'text', 'json'}:
                raise ValueError('placeholder matching supported only for text/json: ' + rid)
        elif req.get('kind') == 'action':
            if set(req) != base | {'operation', 'target'} or not all(_string(req.get(x)) for x in ('operation', 'target')):
                raise ValueError('invalid action fields: ' + rid)
            identity = (req['operation'], req['target'])
            if identity in actions:
                raise ValueError('duplicate required action: ' + rid)
            actions.add(identity)
        elif contract['schema_version'] == 2 and isinstance(req.get('kind'), str) and req['kind'] in CONDITION_KINDS:
            _validate_condition(req, rid, base)
            evaluator = req['evaluator']
            identity = _canonical({'kind': req['kind'], 'target': req['target'] if req['evaluator']['type'] == 'forbidden_operation' else _target(req['target']),
                                   'evaluator': evaluator,
                                   'evidence_refs': sorted(req['evidence_refs'], key=_canonical)})
            if identity in conditions:
                raise ValueError('duplicate condition target/evaluator: ' + rid)
            conditions.add(identity)
        else:
            raise ValueError('unresolved requirement kind: ' + rid)
    # Output conditions must govern an explicitly declared deliverable. Merely
    # supplying a file for a condition does not add it to the publication set.
    # Auxiliary evidence_refs and operation targets are separate namespaces.
    for req in reqs:
        if (req['kind'] in CONDITION_KINDS
                and req['evaluator']['type'] != 'forbidden_operation'):
            target_kind, target_path = _target(req['target'])
            if target_kind == 'artifact' and target_path not in paths:
                raise ValueError('condition target requires a declared artifact: ' + req['id'])
    if 'traceability' in contract:
        findings = _traceability_shape(contract['traceability'], ids)
        if findings:
            raise ValueError(findings[0]['message'])
    return reqs

def _traceability_shape(rows, requirement_ids):
    findings = []
    def fail(code, message, rid=None):
        findings.append({'code': code, 'requirement_id': rid, 'message': message})
    if not isinstance(rows, list):
        fail('invalid_traceability', 'traceability must be an array')
        return findings
    seen = set()
    fields = {'requirement_id', 'task_ids', 'code_paths', 'check_ids',
              'decision_refs', 'depends_on', 'constraints', 'check_commands'}
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            fail('invalid_mapping', 'mapping must contain exactly the required traceability fields')
            continue
        rid = row['requirement_id']
        if not _string(rid) or rid not in requirement_ids or rid in seen:
            fail('invalid_mapping_id', 'mapping requirement_id must identify one distinct requirement', rid if isinstance(rid, str) else None)
        else:
            seen.add(rid)
        for key in ('task_ids', 'code_paths', 'check_ids', 'depends_on'):
            values = row[key]
            valid = (isinstance(values, list) and all(_string(x) for x in values)
                     and len(values) == len(set(values)))
            if valid and key in ('task_ids', 'check_ids'):
                valid = bool(values)
            if valid and key == 'code_paths':
                valid = all(_safe_path(x) for x in values)
            if valid and key == 'depends_on':
                valid = all(x in requirement_ids and x != rid for x in values)
            if not valid:
                fail('invalid_' + key, key + ' must contain valid distinct references', rid)
        commands = row['check_commands']
        if (not isinstance(commands, dict) or any(not _string(k) or not _string(v) for k, v in commands.items())
                or not isinstance(row['check_ids'], list) or any(k not in row['check_ids'] for k in commands)):
            fail('invalid_check_commands', 'check_commands must map selected check IDs to nonempty exact commands', rid)
        refs = row['decision_refs']
        if not isinstance(refs, list):
            fail('invalid_decision_refs', 'decision_refs must be an array', rid)
        else:
            ids = set()
            for ref in refs:
                if (not isinstance(ref, dict) or set(ref) != {'decision_id', 'version', 'choice'}
                        or not _string(ref.get('decision_id')) or ref.get('decision_id') in ids
                        or not _string(ref.get('choice'))
                        or not (_string(ref.get('version')) or type(ref.get('version')) is int and ref['version'] >= 0)):
                    fail('invalid_decision_refs', 'decision_refs must contain distinct decision_id/version/choice pins', rid)
                else:
                    ids.add(ref['decision_id'])
        constraints = row['constraints']
        if (not isinstance(constraints, dict) or any(not _string(k) or
                not (v is None or type(v) in (str, bool, int) or type(v) is float and math.isfinite(v))
                for k, v in constraints.items())):
            fail('invalid_constraints', 'constraints must map nonempty keys to finite JSON scalars', rid)
    for rid in sorted(requirement_ids - seen):
        fail('mapping_missing', 'requirement has no traceability mapping', rid)
    return findings


def analyze_requirements(contract, request_bytes, *, tasks=None, context=None, code_files=None):
    """Compare explicit traceability inputs without inferring intent or authority."""
    result = {'status': 'fail', 'findings': [], 'mappings': [], 'code_hashes': {}}
    findings = result['findings']
    def fail(code, message, rid=None, **identity):
        findings.append({'code': code, 'requirement_id': rid, 'message': message, **identity})
    try:
        if not isinstance(contract, dict):
            raise ValueError('contract must be an object')
        # Validate the existing contract separately so shape errors can all be returned.
        base = {k: v for k, v in contract.items() if k != 'traceability'}
        reqs = validate_contract(base, request_bytes)
        if 'traceability' not in contract:
            result['status'] = 'not-selected'
            return result
        if contract['schema_version'] != 2:
            raise ValueError('traceability requires schema_version 2')
        ids = {r['id'] for r in reqs}
        shape = _traceability_shape(contract['traceability'], ids)
        findings.extend(shape)
        all_rows = contract['traceability']
        rows = ([row for row in all_rows if not any(
                    f['code'] != 'mapping_missing' for f in _traceability_shape([row], ids))]
                if isinstance(all_rows, list) else [])
        result['mappings'] = rows
        if tasks is not None and (not isinstance(tasks, dict) or any(not _string(k) or not isinstance(v, dict) for k, v in tasks.items())):
            raise ValueError('tasks must map task IDs to task objects')
        if context is not None and (not isinstance(context, dict) or not isinstance(context.get('adopted_decisions'), list)
                                    or any(not isinstance(d, dict) or not _string(d.get('decision_id')) for d in context['adopted_decisions'])
                                    or len({d['decision_id'] for d in context['adopted_decisions']}) != len(context['adopted_decisions'])):
            raise ValueError('context must contain distinct adopted_decisions')
        decisions = {d['decision_id']: d for d in context['adopted_decisions']} if context is not None else {}
        if code_files is not None and (not isinstance(code_files, dict) or any(not _safe_path(k) or not isinstance(v, bytes) for k, v in code_files.items())):
            raise ValueError('code_files must map safe paths to bytes')
        if code_files is not None:
            result['code_hashes'] = {path: digest(data) for path, data in sorted(code_files.items())}
        constraints, graph, command_pins = {}, {}, {}
        for row in rows:
            rid = row['requirement_id']
            graph[rid] = row['depends_on']
            for task_id in row['task_ids']:
                for check in row['check_ids']:
                    key, command = (task_id, check), row['check_commands'].get(check)
                    if key in command_pins and command_pins[key][1] != command:
                        fail('check_command_conflict', 'mapped task/check has conflicting execution or semantic proof pins', rid,
                             task_id=task_id, check_id=check, other_requirement_id=command_pins[key][0])
                    else:
                        command_pins[key] = (rid, command)
            if tasks is not None:
                for task_id in row['task_ids']:
                    if task_id not in tasks:
                        fail('missing_task', 'mapped task does not exist', rid, task_id=task_id)
                for check in row['check_ids']:
                    if not any(check in tasks[t].get('required_checks', []) for t in row['task_ids'] if t in tasks and isinstance(tasks[t].get('required_checks', []), list)):
                        fail('missing_check', 'check is not declared by a mapped task', rid, check_id=check)
            if code_files is not None:
                for path in row['code_paths']:
                    if path not in code_files:
                        fail('missing_code_file', 'mapped implementation file is missing', rid, code_path=path)
            if context is not None:
                for pin in row['decision_refs']:
                    actual = decisions.get(pin['decision_id'])
                    if actual is None or any(actual.get(k) != pin[k] or type(actual.get(k)) is not type(pin[k]) for k in ('version', 'choice')):
                        fail('decision_mismatch', 'adopted decision differs from mapping pin', rid, decision_id=pin['decision_id'])
            for key, value in row['constraints'].items():
                if key in constraints and _canonical(value) != _canonical(constraints[key][1]):
                    fail('constraint_conflict', 'explicit constraint differs across requirements', rid, constraint=key, other_requirement_id=constraints[key][0])
                else:
                    constraints[key] = (rid, value)
        def reaches(start, current, visited):
            for nxt in graph.get(current, []):
                if nxt == start:
                    return True
                if nxt not in visited:
                    visited.add(nxt)
                    if reaches(start, nxt, visited):
                        return True
            return False
        for rid in graph:
            if reaches(rid, rid, {rid}):
                fail('dependency_cycle', 'requirement participates in a dependency cycle', rid)
        for required in reqs:
            for prohibited in reqs:
                ev, ban = required.get('evaluator', {}), prohibited.get('evaluator', {})
                if (ev.get('type') == 'contains_literal' and ban.get('type') == 'forbidden_literal'
                        and _target(required['target']) == _target(prohibited['target']) and ban['value'] in ev['value']):
                    fail('literal_conflict', 'required literal contains forbidden literal on the same target', required['id'], other_requirement_id=prohibited['id'])
                if (required['kind'] == 'action' and ban.get('type') == 'forbidden_operation'
                        and required['operation'] == ban['operation'] and required['target'] == prohibited['target']):
                    fail('operation_conflict', 'required action matches a forbidden operation', required['id'], other_requirement_id=prohibited['id'])
    except (ValueError, TypeError, UnicodeError, KeyError, AttributeError, RecursionError) as exc:
        fail('invalid_input', str(exc))
    result['status'] = 'fail' if findings else 'pass'
    return result


def _check_type(data, file_type):
    if file_type == 'binary':
        return
    if file_type in {'text', 'json'}:
        decoded = data.decode('utf-8')
        if file_type == 'json':
            _json(decoded)
    elif file_type == 'pdf':
        if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-1024:]:
            raise ValueError('invalid PDF signature/trailer')
    else:
        with zipfile.ZipFile(io.BytesIO(data) if isinstance(data, bytes) else data) as archive:
            members = archive.infolist()
            if len(members) > MAX_ZIP_MEMBERS or sum(x.file_size for x in members) > MAX_ZIP_UNCOMPRESSED:
                raise ValueError('ZIP inspection budget exceeded')
            if archive.testzip() is not None:
                raise ValueError('corrupt ZIP member')
            required = {'docx': 'word/document.xml', 'pptx': 'ppt/presentation.xml',
                        'xlsx': 'xl/workbook.xml'}.get(file_type)
            if required and not {required, '[Content_Types].xml'} <= set(archive.namelist()):
                raise ValueError('missing Office package members')

def _sections(text, level):
    """Count ATX headings at the registered level, excluding fenced code."""
    count, fence_char, fence_length = 0, None, 0
    heading = re.compile(r'^[ ]{0,3}' + '#' * level + r'(?:[ \t]|$)')
    for line in text.splitlines():
        if fence_char is not None:
            if re.fullmatch(r'[ ]{0,3}' + re.escape(fence_char) +
                            '{' + str(fence_length) + r',}[ \t]*', line):
                fence_char, fence_length = None, 0
            continue
        fence = re.match(r'^[ ]{0,3}(`{3,}|~{3,})(.*)$', line)
        if fence and not (fence[1][0] == '`' and '`' in fence[2]):
            fence_char, fence_length = fence[1][0], len(fence[1])
            continue
        if heading.match(line):
            count += 1
    return count


def _json_field(data, pointer):
    current = _json(data)
    for token in _pointer_tokens(pointer):
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and re.fullmatch(r'0|[1-9][0-9]*', token):
            index = int(token)
            if index >= len(current):
                raise ValueError('required JSON field is missing: ' + pointer)
            current = current[index]
        else:
            raise ValueError('required JSON field is missing: ' + pointer)


def _nonempty_evidence(data):
    if isinstance(data, bytes):
        return bool(data.strip())
    # Evidence without a JSON record ID may be binary and larger than the text
    # budget. Consume every chunk even after finding content so the snapshot's
    # final size/digest verification cannot be skipped.
    nonempty = False
    for chunk in data.chunks():
        if chunk.strip():
            nonempty = True
    return nonempty


def _evidence(refs, artifacts):
    resolved = []
    for ref in refs:
        path = ref['path']
        if path not in artifacts or not _nonempty_evidence(artifacts[path]):
            raise ValueError('required evidence file is missing or empty: ' + path)
        data = artifacts[path]
        if 'id' in ref:
            ledger = _json(data)
            if not isinstance(ledger, dict) or not isinstance(ledger.get('records'), list):
                raise ValueError('evidence ID lookup requires a JSON records array: ' + path)
            seen = set()
            for row in ledger['records']:
                if not isinstance(row, dict) or not _string(row.get('id')) or row['id'] in seen:
                    raise ValueError('evidence records need unique nonempty IDs: ' + path)
                seen.add(row['id'])
            if ref['id'] not in seen:
                raise ValueError('required evidence ID is missing: ' + ref['id'])
        resolved.append({**ref, 'sha256': digest(data)})
    return resolved


def _condition(req, artifacts, candidate_bytes, checked):
    target_kind, path = _target(req['target'])
    if target_kind == 'message':
        if candidate_bytes is None:
            raise ValueError('required final message bytes are missing: message://final')
        data = candidate_bytes
    else:
        if path not in artifacts:
            raise ValueError('required condition target is missing: ' + req['target'])
        data = artifacts[path]
    checked['sha256'] = digest(data)
    checked['evidence'] = _evidence(req['evidence_refs'], artifacts)
    evaluator = req['evaluator']
    kind = evaluator['type']
    if kind == 'exact_sections':
        count = _sections(data.decode('utf-8'), evaluator['level'])
        checked['observed_count'] = count
        if count != evaluator['count']:
            raise ValueError('expected %d level-%d ATX sections; found %d' %
                             (evaluator['count'], evaluator['level'], count))
    elif kind == 'json_field':
        _json_field(data, evaluator['pointer'])
    elif kind in {'contains_literal', 'forbidden_literal'}:
        contains = evaluator['value'] in data.decode('utf-8')
        if contains != (kind == 'contains_literal'):
            raise ValueError('required literal is missing' if kind == 'contains_literal'
                             else 'forbidden literal is present')
    checked['status'] = 'pass'
    return checked


def validate_requirements(contract, request_bytes, artifacts, events, contract_sha256=None, candidate_bytes=None):
    """Pure host integration: artifact mapping is exact relative path -> bytes.

    candidate_bytes is the separate exact UTF-8 message://final input. The host
    must independently bind this contract to its trusted frozen manifest,
    reject filesystem aliases while collecting bytes, and pass execution records.
    Failure is returned as status='fail' with structured unmet entries, not raised.
    """
    result = {'status': 'fail', 'unmet': [], 'checked': [], 'evaluations': [], 'source_spans': {},
              'limitations': LIMITATION}
    def fail(code, message, rid=None):
        item = {'code': code, 'message': message}
        if rid is not None:
            item['requirement_id'] = rid
        result['unmet'].append(item)
    try:
        reqs = validate_contract(contract, request_bytes)
        result['source_spans'] = requirement_spans(contract, request_bytes)
        if contract_sha256 is None:
            contract_sha256 = digest(_canonical(contract))
        if not isinstance(contract_sha256, str) or not re.fullmatch('[0-9a-f]{64}', contract_sha256):
            raise ValueError('contract_sha256 must be a lowercase SHA-256 digest')
        if not isinstance(artifacts, dict) or any(not _safe_path(k) or not _content(v) for k, v in artifacts.items()):
            raise ValueError('artifacts must map exact safe paths to bytes')
        if candidate_bytes is not None:
            if not isinstance(candidate_bytes, bytes):
                raise ValueError('candidate_bytes must contain exact final message bytes')
            candidate_bytes.decode('utf-8')
        if not isinstance(events, list):
            raise ValueError('events must be an array')
        event_ids, by_requirement = set(), {}
        action_ids = {r['id'] for r in reqs if r['kind'] == 'action'}
        prohibited_ids = {r['id'] for r in reqs if r.get('evaluator', {}).get('type') == 'forbidden_operation'}
        for event in events:
            if not isinstance(event, dict) or not all(_string(event.get(k)) for k in ('event_id', 'requirement_id', 'operation', 'target', 'status')):
                raise ValueError('event lacks event_id, requirement_id, operation, target, or status')
            if event['event_id'] in event_ids or (event['requirement_id'] in action_ids and event['requirement_id'] in by_requirement):
                raise ValueError('duplicate event id or requirement event')
            if event['requirement_id'] not in action_ids | prohibited_ids:
                raise ValueError('unresolved event requirement_id')
            event_ids.add(event['event_id'])
            if event['requirement_id'] in action_ids:
                by_requirement[event['requirement_id']] = event
    except (ValueError, TypeError, UnicodeError, AttributeError) as exc:
        fail('invalid_input', str(exc))
        return result
    for req in reqs:
        rid = req['id']
        if req.get('evaluator', {}).get('type') == 'forbidden_operation':
            matches = [event['event_id'] for event in events
                       if event['operation'] == req['evaluator']['operation'] and event['target'] == req['target']]
            evaluation = {'requirement_id': rid, 'status': 'fail' if matches else 'pass',
                          'target': req['target'], 'evaluator': 'forbidden_operation',
                          'event_ids': matches, 'source_spans': result['source_spans'][rid]}
            try:
                evaluation['evidence'] = _evidence(req['evidence_refs'], artifacts)
            except (ValueError, TypeError, UnicodeError) as exc:
                evaluation.update(status='fail', message=str(exc))
                fail('condition_unmet', str(exc), rid)
            result['evaluations'].append(evaluation)
            if matches:
                fail('prohibited_operation', 'Recorded operation matches a preserved prohibition', rid)
            elif evaluation['status'] == 'pass':
                result['checked'].append(evaluation)
            continue
        if req['kind'] in CONDITION_KINDS:
            target_kind, target_path = _target(req['target'])
            evaluation = {'requirement_id': rid, 'status': 'fail', 'target': req['target'],
                          'target_uri': 'message://final' if target_kind == 'message' else 'artifact://' + target_path,
                          'evaluator': req['evaluator']['type'],
                          'source_spans': result['source_spans'][rid]}
            try:
                checked = _condition(req, artifacts, candidate_bytes, evaluation)
                result['checked'].append(checked)
                evaluation = checked
            except (ValueError, TypeError, UnicodeError, KeyError, RecursionError) as exc:
                evaluation['message'] = str(exc)
                fail('condition_unmet', str(exc), rid)
            result['evaluations'].append(evaluation)
            continue
        if req['kind'] == 'action':
            event = by_requirement.get(rid)
            if event is None:
                fail('missing_action_event', 'No event recorded for required action', rid)
            elif event['operation'] != req['operation'] or event['target'] != req['target']:
                fail('action_mismatch', 'Operation or target differs from contract', rid)
            elif event['status'] != 'success':
                fail('action_unsuccessful', 'Required action status is not success', rid)
            else:
                result['checked'].append({'requirement_id': rid, 'event_id': event['event_id'],
                                          'source_spans': result['source_spans'][rid]})
            continue
        try:
            if req['path'] not in artifacts:
                raise ValueError('required artifact is missing: ' + req['path'])
            data = artifacts[req['path']]
            if req.get('nonempty', True) and (not data or (req['file_type'] in {'text', 'json'} and not data.strip())):
                raise ValueError('required artifact is empty')
            _check_type(data, req['file_type'])
            for marker in req.get('reject_placeholders', []):
                if marker.casefold() in data.decode('utf-8').casefold():
                    raise ValueError('forbidden placeholder marker: ' + marker)
            result['checked'].append({'requirement_id': rid, 'path': req['path'], 'sha256': digest(data),
                                      'source_spans': result['source_spans'][rid]})
        except (ValueError, UnicodeError, zipfile.BadZipFile, RuntimeError, OSError, NotImplementedError) as exc:
            fail('artifact_invalid', str(exc), rid)
    if not result['unmet']:
        result['status'] = 'pass'
    return result


def check_requirements(requirements_path, artifacts_dir, events_path, request_path,
                       expected_contract_sha256, final_message_path=None):
    """Filesystem adapter. All paths and an externally pinned hash are required."""
    try:
        raw = Path(requirements_path).read_bytes()
        if not isinstance(expected_contract_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_contract_sha256):
            raise ValueError('externally pinned expected contract SHA-256 is required')
        if digest(raw) != expected_contract_sha256:
            raise ValueError('contract digest mismatch')
        contract = _json(raw)
        request = Path(request_path).read_bytes()
        reqs = validate_contract(contract, request)
        source_root = Path(artifacts_dir).absolute()
        if any(part.is_symlink() for part in (source_root, *source_root.parents)):
            raise ValueError("artifacts root contains a symlink")
        root = source_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError('artifacts root must be a directory')
        artifacts = {}
        paths = set()
        for req in reqs:
            if req['kind'] == 'artifact':
                paths.add(req['path'])
            elif req['kind'] in CONDITION_KINDS:
                if req['evaluator']['type'] != 'forbidden_operation':
                    target_kind, target_path = _target(req['target'])
                    if target_kind == 'artifact':
                        paths.add(target_path)
                paths.update(ref['path'] for ref in req['evidence_refs'])
        for path in sorted(paths):
            cursor = root
            for component in PurePosixPath(path).parts:
                cursor /= component
                if cursor.is_symlink():
                    raise ValueError('artifact path contains a symlink')
            if not cursor.exists():
                continue
            resolved = cursor.resolve(strict=True)
            if not resolved.is_relative_to(root) or not resolved.is_file():
                raise ValueError('artifact is not a regular file inside root')
            artifacts[path] = _file_runtime().file_snapshot(resolved)
        events = _json(Path(events_path).read_bytes())
        candidate_bytes = None
        if final_message_path is not None:
            message_path = Path(final_message_path).absolute()
            if any(part.is_symlink() for part in (message_path, *message_path.parents)):
                raise ValueError('final message path contains a symlink')
            if not message_path.is_file():
                raise ValueError('final message must be a regular file')
            candidate_bytes = message_path.read_bytes()
        result = validate_requirements(contract, request, artifacts, events,
                                       contract_sha256=digest(raw), candidate_bytes=candidate_bytes)
        result['contract_sha256'] = digest(raw)
        return result
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        return {'status': 'fail', 'unmet': [{'code': 'invalid_input', 'message': str(exc)}],
                'checked': [], 'limitations': LIMITATION}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    freeze = sub.add_parser('freeze-requirements', help='Validate and pin a contract BEFORE creating the candidate')
    freeze.add_argument('--requirements', required=True)
    freeze.add_argument('--request', required=True)
    check = sub.add_parser('check-requirements')
    for name in ('requirements', 'artifacts', 'events', 'request', 'expected-contract-sha256'):
        check.add_argument('--' + name, required=True)
    check.add_argument('--final-message', help='File containing exact UTF-8 message://final bytes')
    args = parser.parse_args(argv)
    if args.command == 'freeze-requirements':
        try:
            raw = Path(args.requirements).read_bytes()
            request = Path(args.request).read_bytes()
            contract = _json(raw)
            reqs = validate_contract(contract, request)
            output = {'status': 'valid', 'contract_sha256': digest(raw), 'limitations': LIMITATION,
                      'source_spans': requirement_spans(contract, request)}
        except (OSError, ValueError, TypeError, UnicodeError) as exc:
            output = {'status': 'fail', 'unmet': [{'code': 'invalid_input', 'message': str(exc)}]}
    else:
        output = check_requirements(args.requirements, args.artifacts, args.events, args.request,
                                    args.expected_contract_sha256, args.final_message)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output['status'] in {'valid', 'pass'} else 1

if __name__ == '__main__':
    sys.exit(main())
