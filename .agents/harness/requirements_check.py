#!/usr/bin/env python3
"""Evaluate registered artifact, action, content, prohibition, and evidence requirements."""
import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

_FILE_RUNTIME = None
_FILE_RUNTIME_KEY = None

def _file_runtime():
    global _FILE_RUNTIME, _FILE_RUNTIME_KEY
    import importlib.util
    policy_path = Path(__file__).with_name('policy_assets.py')
    policy_spec = importlib.util.spec_from_file_location('requirements_policy_layout', policy_path)
    policy = importlib.util.module_from_spec(policy_spec)
    policy_spec.loader.exec_module(policy)
    root, manifest_bytes, manifest, _ = policy.discover_policy(__file__)
    if ((root / manifest['assets']['requirements_check']['path']).absolute() != Path(__file__).absolute()
            or (root / manifest['assets']['policy_assets']['path']).absolute() != policy_path.absolute()):
        raise ValueError('loaded requirements runtime differs from adopted policy layout')
    runtime_path = root / manifest['assets']['local_checks']['path']
    key = (str(root), policy.digest(manifest_bytes), str(runtime_path), manifest['assets']['local_checks']['sha256'])
    if _FILE_RUNTIME is not None and _FILE_RUNTIME_KEY == key:
        return _FILE_RUNTIME
    spec = importlib.util.spec_from_file_location('requirements_file_runtime', runtime_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _FILE_RUNTIME = module
    _FILE_RUNTIME_KEY = key
    return module


LIMITATION = ('Checks compare the explicit contract, final message bytes, artifact bytes, evaluator results and final action records. '
              'Retain the contract hash before candidate generation. The coverage reviewer maps the original '
              'request to the contract; the coordinator matches action records to actual tool returns and permissions.')
TYPES = {'text', 'json', 'pdf', 'zip', 'docx', 'pptx', 'xlsx', 'binary'}
MAX_ZIP_MEMBERS = 10000
MAX_ZIP_UNCOMPRESSED = 64 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
CONDITION_KINDS = {'content', 'prohibition', 'evidence'}
REVIEW_ROLES = {'quality-a', 'quality-b', 'compliance'}
REQUIREMENT_CLASSES = {'output', 'content', 'prohibition', 'action', 'authority', 'completion'}


class ReviewPending(ValueError):
    """A required review has not reached an evaluated passing result."""

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


def coverage_ledger_sha256(rows):
    """Bind the source-only extraction once, without its later contract links."""
    return digest(_canonical([{key: value for key, value in row.items()
                               if key != 'requirement_ids'} for row in rows]))


def _span_covered(text, start, end, spans):
    position = start
    for left, right in sorted(spans):
        left, right = max(start, left), min(end, right)
        if right <= left or right <= position:
            continue
        if text[position:left].strip():
            return False
        position = max(position, right)
    return not text[position:end].strip()


def validate_request_coverage(contract, request, rows, independent_extraction=None):
    """Check exact source positions and both mapping directions, never authenticity.

    The API has no candidate input. A trusted host separately establishes that the
    source-only ledger was actually extracted independently before candidate
    exposure and that a reviewer assessed its semantic obligation classification.
    A self-authored record can be structurally consistent without proving either.
    Legacy rows remain diagnostic input and return ``unreviewed``.
    """
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    require(isinstance(request, bytes), 'coverage request must contain exact UTF-8 bytes')
    request_text = request.decode('utf-8')
    requirements = {req['id']: req for req in validate_contract(contract, request)}
    sources = contract_sources(contract, request)
    explicit = 'sources' in contract
    positions = {sid: 0 for sid in sources}
    require(isinstance(rows, list) and rows, 'coverage_rows must be a nonempty array')
    classified = independent_extraction is not None
    seen, linked, obligation_rows, context_rows = set(), set(), {}, {}
    linked_ranges = {rid: [] for rid in requirements}
    for row in rows:
        require(isinstance(row, dict), 'coverage row must be an object')
        fields = {'id', 'start', 'end', 'source_quote', 'kind', 'requirement_ids'}
        if explicit:
            fields.add('source_id')
        sid = row.get('source_id')
        require(sid in sources, 'unknown coverage source_id')
        text, position = sources[sid], positions[sid]
        require(row.get('kind') in ('obligation', 'non-obligation'), 'invalid coverage row kind')
        if row['kind'] == 'non-obligation':
            fields.add('rationale')
        elif classified:
            fields.add('classifications')
        require(set(row) == fields, 'invalid coverage row fields')
        row_id = row['id']
        require(_string(row_id) and row_id not in seen, 'missing or duplicate coverage row ID')
        seen.add(row_id)
        start, end = row['start'], row['end']
        require(type(start) is int and type(end) is int and start == position
                and start < end <= len(text), 'gap, overlap, or invalid coverage source span: ' + row_id)
        require(isinstance(row['source_quote'], str) and row['source_quote'] == text[start:end],
                'coverage source quote mismatch: ' + row_id)
        ids = row['requirement_ids']
        require(isinstance(ids, list) and all(_string(item) for item in ids)
                and len(set(ids)) == len(ids) and set(ids) <= set(requirements),
                'unknown or duplicate linked requirement ID: ' + row_id)
        if row['kind'] == 'non-obligation':
            require(not ids and _string(row['rationale']),
                    'non-obligation requires rationale and no requirement IDs: ' + row_id)
            context_rows[row_id] = row
        else:
            require(ids, 'obligation requires linked contract requirements: ' + row_id)
            if classified:
                classes = row['classifications']
                require(isinstance(classes, list) and classes
                        and all(isinstance(value, str) for value in classes)
                        and len(classes) == len(set(classes)) and set(classes) <= REQUIREMENT_CLASSES,
                        'obligation requires distinct supported classifications: ' + row_id)
            covered = []
            for rid in ids:
                require(requirements[rid].get('source_id') == sid,
                        'linked requirement belongs to another source: ' + rid)
                spans = _source_spans(requirements[rid], text, sources if explicit else None)
                if classified:
                    require(len(spans) == 1,
                            'ambiguous requirement quote requires an explicit source_span: ' + rid)
                intersections = [(max(start, span['start']), min(end, span['end'])) for span in spans
                                 if span['start'] < end and start < span['end']]
                require(intersections, 'linked requirement source does not intersect obligation: ' + rid)
                covered.extend(intersections)
                linked_ranges[rid].extend(intersections)
            require(_span_covered(text, start, end, covered),
                    'obligation contains source text absent from linked contract requirements: ' + row_id)
            linked.update(ids)
            obligation_rows[row_id] = row
        positions[sid] = end
    require(all(positions[sid] == len(text) for sid, text in sources.items()),
            'coverage rows omit original or inherited source text')
    require(linked == set(requirements), 'coverage rows omit contract requirement IDs')
    for rid, req in requirements.items():
        text = sources[req.get('source_id')]
        spans = _source_spans(req, text, sources if explicit else None)
        require(any(_span_covered(text, span['start'], span['end'], linked_ranges[rid]) for span in spans),
                'linked requirement source is not covered by its obligation rows: ' + rid)
    result = {'schema_version': 1, 'status': 'unreviewed', 'request_sha256': digest(request),
              'source_ledger_sha256': coverage_ledger_sha256(rows),
              'provenance_authenticated': False, 'semantic_coverage_verified': False}
    if not classified:
        return result
    extraction = independent_extraction
    fields = {'schema_version', 'request_sha256', 'source_ledger_sha256', 'requirement_classes',
              'request_to_contract', 'contract_to_request', 'non_obligations', 'ambiguities'}
    require(isinstance(extraction, dict) and set(extraction) == fields
            and type(extraction['schema_version']) is int and extraction['schema_version'] == 1,
            'invalid independent extraction fields or schema')
    require(extraction['request_sha256'] == digest(request)
            and extraction['source_ledger_sha256'] == result['source_ledger_sha256'],
            'independent extraction source binding mismatch')
    require(isinstance(extraction['ambiguities'], list) and not extraction['ambiguities'],
            'ambiguous source classification must return for clarification')
    classes = extraction['requirement_classes']
    require(isinstance(classes, dict) and set(classes) == set(requirements)
            and all(isinstance(value, str) and value in REQUIREMENT_CLASSES for value in classes.values()),
            'independent extraction must classify every contract requirement')

    def mapping(values, key, links, expected, target):
        require(isinstance(values, list), 'coverage direction must be an array: ' + key)
        mapped = {}
        for value in values:
            require(isinstance(value, dict) and set(value) == {key, links}
                    and _string(value[key]) and value[key] not in mapped,
                    'invalid or duplicate coverage direction row: ' + key)
            refs = value[links]
            require(isinstance(refs, list) and refs and all(_string(ref) for ref in refs)
                    and len(set(refs)) == len(refs) and set(refs) <= target,
                    'invalid coverage direction links: ' + key)
            mapped[value[key]] = set(refs)
        require(set(mapped) == expected, 'coverage direction omits or invents a source or requirement: ' + key)
        return mapped

    forward = mapping(extraction['request_to_contract'], 'row_id', 'requirement_ids',
                      set(obligation_rows), set(requirements))
    reverse = mapping(extraction['contract_to_request'], 'requirement_id', 'row_ids',
                      set(requirements), set(obligation_rows))
    for row_id, row in obligation_rows.items():
        require(forward[row_id] == set(row['requirement_ids']),
                'original-to-contract comparison differs from source ledger links: ' + row_id)
        require(set(row['classifications']) == {classes[rid] for rid in forward[row_id]},
                'source and contract classifications differ: ' + row_id)
        require(all(row_id in reverse[rid] for rid in forward[row_id]),
                'missing reverse obligation mapping: ' + row_id)
    for rid, row_ids in reverse.items():
        require(row_ids == {row_id for row_id, ids in forward.items() if rid in ids},
                'contract-to-original comparison adds or omits an obligation: ' + rid)
    contexts = extraction['non_obligations']
    require(isinstance(contexts, list), 'non_obligations must be an explicit review array')
    reviewed_contexts = set()
    for row in contexts:
        require(isinstance(row, dict) and set(row) == {'row_id', 'decision'}
                and _string(row['row_id']) and row['row_id'] in context_rows
                and row['row_id'] not in reviewed_contexts and row['decision'] == 'non-obligation',
                'non-obligation must be independently resolved or returned as ambiguous')
        reviewed_contexts.add(row['row_id'])
    require(reviewed_contexts == set(context_rows), 'non-obligation classifications lack independent review')
    result.update(status='consistent', independent_extraction_sha256=digest(_canonical(extraction)),
                  requirement_classes=classes)
    return result


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
        'content': {'exact_sections', 'json_field', 'contains_literal', 'structured_review'},
        'prohibition': {'forbidden_literal', 'forbidden_operation', 'structured_review'},
        'evidence': {'evidence_refs', 'structured_review'},
    }
    if kind not in allowed[req['kind']]:
        raise ValueError('unsupported evaluator for condition kind: ' + rid)
    fields = {'exact_sections': {'level', 'count'}, 'json_field': {'pointer'},
              'contains_literal': {'value'}, 'forbidden_literal': {'value'},
              'evidence_refs': set(), 'forbidden_operation': {'operation'},
              'structured_review': {'role', 'check_id'}}[kind]
    optional = {'review_kind'} if kind == 'structured_review' else set()
    if not {'type'} | fields <= set(evaluator) or set(evaluator) - ({'type'} | fields | optional):
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
    elif kind == 'structured_review':
        if (not isinstance(evaluator['role'], str) or evaluator['role'] not in REVIEW_ROLES
                or not _string(evaluator['check_id'])):
            raise ValueError('structured review must name a role and check_id: ' + rid)
        review_kind = evaluator.get('review_kind', 'independent')
        if review_kind not in ('independent', 'self-check') or (review_kind == 'self-check' and evaluator['role'] != 'quality-a'):
            raise ValueError('self-check structured review requires quality-a; review_kind must be independent or self-check: ' + rid)
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
            (base, base | {'sources', 'request_source_id'})):
        raise ValueError('contract requires schema_version, request_sha256, requirements and optional paired sources/request_source_id')
    if type(contract['schema_version']) is not int or contract['schema_version'] not in (1, 2):
        raise ValueError('unsupported schema_version')
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
            # The v2 spelling without review_kind is the same independent
            # condition as its explicit spelling, while frozen bytes stay exact.
            if evaluator['type'] == 'structured_review':
                evaluator = {**evaluator, 'review_kind': evaluator.get('review_kind', 'independent')}
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
    return reqs

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


def _review(req, reviews, request_bytes, artifacts, contract_sha256, candidate_bytes,
            review_plan=None, author_id=None):
    evaluator = req['evaluator']
    kind = evaluator.get('review_kind', 'independent')
    if review_plan is not None:
        if (not isinstance(review_plan, dict) or evaluator['role'] not in review_plan.get('roles', [])
                or review_plan.get('review_kind', 'independent') != kind):
            raise ValueError('selected plan does not satisfy the structured review kind and role')
    if kind == 'self-check' and (review_plan is None or not _string(author_id)):
        raise ReviewPending('self-check requires the pinned plan and actual author identity')
    if reviews is None:
        raise ReviewPending('required structured review has not been supplied')
    if not isinstance(reviews, list):
        raise ValueError('reviews must be an array of structured original review records')
    matches = [r for r in reviews if isinstance(r, dict) and r.get('role') == evaluator['role']]
    if not matches:
        raise ReviewPending('required structured review role is missing: ' + evaluator['role'])
    if len(matches) != 1:
        raise ValueError('duplicate structured review role: ' + evaluator['role'])
    record = matches[0]
    if record.get('execution_status') != 'completed':
        raise ReviewPending('structured review is not completed')
    if record.get('review_kind') != kind:
        raise ReviewPending('structured review kind differs from the frozen requirement')
    for field in ('worker_id', 'return_ref', 'return_text'):
        if not _string(record.get(field)):
            raise ReviewPending('structured review lacks ' + field)
    if kind == 'independent':
        if not _string(record.get('launch_ref')):
            raise ReviewPending('structured review lacks launch_ref')
        if record['launch_ref'] == record['return_ref']:
            raise ValueError('independent review needs distinct launch and return references')
        if author_id is not None and record['worker_id'] == author_id:
            raise ValueError('independent review worker must differ from the author')
    elif record['worker_id'] != author_id or record.get('launch_ref'):
        raise ValueError('self-check must bind the actual author without a worker launch')
    if digest(record['return_text'].encode('utf-8')) != record.get('return_sha256'):
        raise ValueError('structured original review digest mismatch')
    body = _json(record['return_text'])
    if (not isinstance(body, dict) or type(body.get('schema_version')) is not int
            or body['schema_version'] not in ((2, 3) if evaluator['role'] in ('quality-a', 'quality-b') else (1,)) or body.get('role') != evaluator['role']):
        raise ValueError('review original must be a schema_version=1 object for the required role')
    for field in ('decision', 'findings', 'unassessed', 'errors', 'checks',
                  'dispositions', 'literal_dispositions', 'text_views_verified',
                  'action_results_verified', 'quality_reports_sha256'):
        if field in record and field not in body:
            raise ValueError('outer review field absent from original: ' + field)
    for key, value in body.items():
        if key in record and _canonical(record[key]) != _canonical(value):
            raise ValueError('review original and outer field disagree: ' + key)
    if 'normalized_return' in record and _canonical(record['normalized_return']) != _canonical(body):
        raise ValueError('normalized review differs from original')
    for field in ('findings', 'unassessed', 'errors'):
        if not isinstance(body.get(field), list):
            raise ValueError('structured original review lacks explicit ' + field + ' array')
        if body[field]:
            if field == 'unassessed':
                raise ReviewPending('structured review contains unassessed conditions')
            raise ValueError('structured review contains unresolved ' + field)
    if body.get('decision') != 'pass':
        raise ValueError('structured original review decision is not pass')
    checks = body.get('checks')
    if not isinstance(checks, dict) or checks.get(evaluator['check_id']) != 'passed':
        if isinstance(checks, dict) and checks.get(evaluator['check_id']) == 'failed':
            raise ValueError('required semantic check failed: ' + evaluator['check_id'])
        raise ReviewPending('required semantic check is not evaluated and passed: ' + evaluator['check_id'])
    if any(value != 'passed' for value in checks.values()):
        raise ReviewPending('structured review contains other nonpassing checks')
    entries = [{'path': path, 'sha256': digest(data)} for path, data in sorted(artifacts.items())]
    bindings = {'request_sha256': digest(request_bytes), 'contract_sha256': contract_sha256,
                'artifacts_sha256': digest(_canonical(entries))}
    if _target(req['target'])[0] == 'message':
        bindings['candidate_sha256'] = digest(candidate_bytes)
    for field, expected in bindings.items():
        if body.get(field) != expected:
            raise ValueError('structured review has stale or absent binding: ' + field)
    source = record.get('source_verification')
    if (not isinstance(source, dict) or set(source) != {'status', 'reference', 'verifier_id'}
            or source['status'] != ('self-check' if kind == 'self-check' else 'matched-to-runtime')
            or not _string(source['reference']) or not _string(source['verifier_id'])):
        raise ReviewPending('structured review lacks recorded source-matched original return')
    if kind == 'self-check' and (source['verifier_id'] != author_id
            or body.get('worker_id') != author_id or body.get('review_kind') != 'self-check'):
        raise ValueError('self-check original and verification must identify the actual author')
    return {'role': evaluator['role'], 'check_id': evaluator['check_id'],
            'review_kind': kind,
            'worker_id': record['worker_id'], 'return_ref': record['return_ref'],
            'return_sha256': record['return_sha256'], 'authenticated': False}


def _condition(req, artifacts, reviews, request_bytes, contract_sha256, candidate_bytes, checked,
               review_plan=None, author_id=None):
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
    elif kind == 'structured_review':
        checked['review'] = _review(req, reviews, request_bytes, artifacts, contract_sha256, candidate_bytes,
                                   review_plan=review_plan, author_id=author_id)
    checked['status'] = 'pass'
    return checked


def validate_requirements(contract, request_bytes, artifacts, events, reviews=None,
                          contract_sha256=None, candidate_bytes=None, review_plan=None, author_id=None):
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
                checked = _condition(req, artifacts, reviews, request_bytes, contract_sha256,
                                     candidate_bytes, evaluation, review_plan=review_plan, author_id=author_id)
                result['checked'].append(checked)
                evaluation = checked
            except ReviewPending as exc:
                evaluation['status'] = 'pending'
                evaluation['message'] = str(exc)
                fail('condition_pending', str(exc), rid)
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
                       expected_contract_sha256, reviews_path=None, final_message_path=None):
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
        if reviews_path is not None:
            import os
            def walk_error(error):
                raise error
            for directory, directories, names in os.walk(root, followlinks=False, onerror=walk_error):
                for name in directories + names:
                    if (Path(directory) / name).is_symlink():
                        raise ValueError('artifact tree contains a symlink')
                paths.update((Path(directory) / name).relative_to(root).as_posix() for name in names)
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
        reviews = _json(Path(reviews_path).read_bytes()) if reviews_path is not None else None
        candidate_bytes = None
        if final_message_path is not None:
            message_path = Path(final_message_path).absolute()
            if any(part.is_symlink() for part in (message_path, *message_path.parents)):
                raise ValueError('final message path contains a symlink')
            if not message_path.is_file():
                raise ValueError('final message must be a regular file')
            candidate_bytes = message_path.read_bytes()
        result = validate_requirements(contract, request, artifacts, events, reviews=reviews,
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
    check.add_argument('--reviews', help='JSON array of structured original review records')
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
                                    args.expected_contract_sha256, args.reviews, args.final_message)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output['status'] in {'valid', 'pass'} else 1

if __name__ == '__main__':
    sys.exit(main())
