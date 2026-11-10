#!/usr/bin/env python3
"""Evaluate adopted source-bound requirements against current task results."""
import hashlib
import importlib.util
import io
import json
import math
import re
import zipfile
from pathlib import Path, PurePosixPath

TYPES = {'text', 'json', 'pdf', 'zip', 'docx', 'pptx', 'xlsx', 'binary'}
CONDITION_KINDS = {'content', 'prohibition', 'evidence'}
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_ZIP_MEMBERS = 10000
MAX_ZIP_UNCOMPRESSED = 64 * 1024 * 1024
def digest(data):
    if isinstance(data, io.BufferedIOBase):
        value, position = hashlib.sha256(), data.tell()
        data.seek(0)
        for chunk in iter(lambda: data.read(1024 * 1024), b''):
            value.update(chunk)
        data.seek(position)
        result = value.hexdigest()
        if getattr(data, 'snapshot_kind', None) == 'fixed-file-v1' and result != data.sha256:
            raise ValueError('pinned requirement target or evidence changed')
        return result
    return hashlib.sha256(data).hexdigest()

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


def _json(data):
    if len(data) > MAX_JSON_BYTES:
        raise ValueError('JSON input exceeds byte budget')
    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('nonfinite JSON number')
        return result
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(data.decode('utf-8'), object_pairs_hook=pairs,
                      parse_float=number,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('invalid JSON constant')))


def _check_type(data, file_type):
    if file_type == 'binary':
        return
    if file_type in {'text', 'json'}:
        data.decode('utf-8')
        if file_type == 'json':
            _json(data)
    elif file_type == 'pdf':
        if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-1024:]:
            raise ValueError('invalid PDF signature/trailer')
    else:
        with zipfile.ZipFile(io.BytesIO(data) if isinstance(data, bytes) else data) as archive:
            members = archive.infolist()
            if len(members) > MAX_ZIP_MEMBERS or sum(row.file_size for row in members) > MAX_ZIP_UNCOMPRESSED:
                raise ValueError('ZIP inspection budget exceeded')
            if archive.testzip() is not None:
                raise ValueError('corrupt ZIP member')
            required = {'docx': 'word/document.xml', 'pptx': 'ppt/presentation.xml',
                        'xlsx': 'xl/workbook.xml'}.get(file_type)
            if required and not {required, '[Content_Types].xml'} <= set(archive.namelist()):
                raise ValueError('missing Office package members')


def _sections(text, level):
    directory = Path(__file__).resolve().parent
    path = next((path for path in (directory.parent / 'scripts/route_registry.py',
                                  directory / 'TOOL_route_registry.py') if path.is_file()), None)
    if path is None:
        raise ValueError('registered Markdown section parser is unavailable')
    spec = importlib.util.spec_from_file_location('requirements_markdown_sections', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, headings = module.markdown_sections(text)
    return sum(heading['level'] == level for heading in headings)


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


def _evidence(refs, evidence):
    for ref in refs:
        path = ref['path']
        if path not in evidence:
            raise ValueError('required evidence file is unavailable: ' + path)
        data = evidence[path]
        if isinstance(data, bytes):
            nonempty = bool(data.strip())
        else:
            nonempty = False
            for chunk in data.chunks():
                nonempty |= bool(chunk.strip())
        if not nonempty:
            raise ValueError('required evidence file is empty: ' + path)
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
        digest(data)


def missing_requirements(contract, request_bytes, artifacts, actions, *, candidate_bytes=None, evidence=None):
    """Evaluate the bound contract against current outputs and verified actions.

    Artifact keys are registered relative output paths. Evidence has a separate
    namespace so a readable source cannot stand in for an unproduced output.
    Actions retain exact operation/target identities and source-verified status.
    """
    requirements = validate_contract(contract, request_bytes)
    evidence = artifacts if evidence is None else evidence
    missing = []
    for req in requirements:
        try:
            kind = req['kind']
            if kind == 'action':
                if not any(row['operation'] == req['operation'] and row['target'] == req['target']
                           and row['status'] == 'success' for row in actions):
                    raise ValueError('required action has no current successful returned operation')
                continue
            if kind == 'artifact':
                if req['path'] not in artifacts:
                    raise ValueError('required artifact is unavailable or unregistered: ' + req['path'])
                data = artifacts[req['path']]
                if req.get('nonempty', True) and (not data or
                        req['file_type'] in {'text', 'json'} and not data.strip()):
                    raise ValueError('required artifact is empty')
                _check_type(data, req['file_type'])
                for marker in req.get('reject_placeholders', []):
                    if marker.casefold() in data.decode('utf-8').casefold():
                        raise ValueError('forbidden placeholder marker: ' + marker)
                digest(data)
                continue
            evaluator = req['evaluator']
            _evidence(req['evidence_refs'], evidence)
            if evaluator['type'] == 'forbidden_operation':
                if any(row['operation'] == evaluator['operation'] and row['target'] == req['target']
                       for row in actions):
                    raise ValueError('recorded operation matches the declared prohibition')
                continue
            target_kind, path = _target(req['target'])
            data = candidate_bytes if target_kind == 'message' else artifacts.get(path)
            if data is None:
                raise ValueError('required condition target is unavailable: ' + req['target'])
            digest(data)
            check = evaluator['type']
            if check == 'exact_sections':
                count = _sections(data.decode('utf-8'), evaluator['level'])
                if count != evaluator['count']:
                    raise ValueError('expected %d level-%d sections; found %d' %
                                     (evaluator['count'], evaluator['level'], count))
            elif check == 'json_field':
                _json_field(data, evaluator['pointer'])
            elif check in {'contains_literal', 'forbidden_literal'}:
                contains = evaluator['value'] in data.decode('utf-8')
                if contains != (check == 'contains_literal'):
                    raise ValueError('required literal is missing' if check == 'contains_literal'
                                     else 'forbidden literal is present')
        except (ValueError, TypeError, UnicodeError, KeyError, AttributeError, OSError,
                zipfile.BadZipFile, RuntimeError, NotImplementedError, RecursionError) as exc:
            missing.append({'requirement_id': req['id'], 'message': str(exc)})
    return missing

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
            if valid and key == 'task_ids':
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
