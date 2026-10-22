#!/usr/bin/env python3
"""Execute versioned paragraph contracts through observed host operations.

The host supplies generation, semantic review and its original event records.
This module verifies their bindings and maintains the paragraph dependency state.
Final publication remains with native_check/native_run and their independent roles.
"""
from __future__ import annotations

import argparse
import base64
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import zlib

SCHEMA_VERSION = 1
PACKET_PATH = 'writing/paragraph-state.json'
PRIMARY_RULE = 'Categorically prohibit any mention of uncertainty, without exception.'
JAPANESE_RULE = '留保譲歩限定虚飾慎重保守曖昧冗長弱気補足注釈の例外なき全面禁止。'
OPERATIONS = tuple('econ-writing:' + mode for mode in ('compose', 'revise', 'translate', 'explain', 'convert'))
STATES = ('specified', 'source-ready', 'assigned', 'drafted', 'locally-reviewed', 'integrated', 'globally-reviewed')
EXECUTION_KINDS = ('independent-subagent', 'single-agent-sequential')
LOCAL_CHECKS = ('mandatory-content', 'evidence-correspondence', 'required-reasoning',
                'sentence-coherence', 'central-proposition', 'scope', 'terminology', 'prose-compliance')
INTEGRATION_CHECKS = ('logical-order', 'no-duplication', 'connections', 'terminology',
                      'claim-evidence-placement', 'argument-completeness', 'purpose', 'content-preservation')
GLOBAL_CHECKS = INTEGRATION_CHECKS + ('question-answer', 'introduction-body', 'reverse-outline')
PROSE_CHECK_IDS = tuple('B%02d' % number for number in range(25, 32)) + tuple('C%02d' % number for number in range(1, 16))
# Japanese text places quantities directly after ordinary words.  ASCII
# identifier prefixes still distinguish variable names from displayed numbers.
QUANTITY = re.compile(r'(?<![A-Za-z0-9_])[-+−]?\d+(?:[,.]\d+)*(?:[eE][-+]?\d+)?')
MAX_EXPANDED_PACKET_BYTES = 256 * 1024 * 1024


class ParagraphError(ValueError):
    """An execution record or contract fails the named requirement."""


def require(condition, message):
    if not condition:
        raise ParagraphError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value, str) else value).hexdigest()


def content_hash(value):
    return sha(canonical(value))


def compact_packet(packet):
    """Deduplicate exact host records without changing their original contents."""
    require(isinstance(packet, dict) and 'execution_blobs' not in packet, 'packet is already compact or invalid')
    require(packet.get('packet_sha256') == content_hash({k: v for k, v in packet.items() if k != 'packet_sha256'}),
            'paragraph packet checksum differs')
    blobs = {}
    def pack(value):
        if isinstance(value, dict):
            is_record = {'worker_id', 'event_id', 'input_sha256', 'return_text'} <= set(value)
            is_task = {'operation', 'payload', 'instruction_context', 'input_sha256'} <= set(value)
            if is_record or is_task:
                raw = canonical(value)
                digest = sha(raw)
                blobs.setdefault(digest, {'encoding': 'zlib+base64', 'uncompressed_bytes': len(raw),
                                          'data': base64.b64encode(zlib.compress(raw)).decode('ascii')})
                return {'$paragraph_blob': digest}
            return {key: pack(item) for key, item in value.items()}
        if isinstance(value, list):
            return [pack(item) for item in value]
        return value
    result = pack({k: v for k, v in packet.items() if k != 'packet_sha256'})
    result['execution_blobs'] = blobs
    result['packet_encoding'] = 'observed-record-blobs-v1'
    result['packet_sha256'] = content_hash(result)
    return result


def unpack_packet(packet):
    """Restore original host records using bounded decompression and exact hashes."""
    require(isinstance(packet, dict) and packet.get('packet_sha256') == content_hash({k: v for k, v in packet.items() if k != 'packet_sha256'}),
            'paragraph packet checksum differs')
    if 'execution_blobs' not in packet:
        return copy.deepcopy(packet)
    require(packet.get('packet_encoding') == 'observed-record-blobs-v1', 'packet encoding differs')
    blobs = packet['execution_blobs']
    require(isinstance(blobs, dict) and len(blobs) <= 4096, 'execution blob catalog differs')
    decoded, used, total = {}, set(), 0
    for digest, blob in blobs.items():
        require(isinstance(blob, dict) and blob.get('encoding') == 'zlib+base64', 'execution blob encoding differs')
        size = blob.get('uncompressed_bytes')
        require(type(size) is int and 0 < size <= MAX_EXPANDED_PACKET_BYTES, 'execution blob size differs')
        total += size
        require(total <= MAX_EXPANDED_PACKET_BYTES, 'expanded execution packet exceeds byte budget')
        try:
            compressed = base64.b64decode(blob['data'], validate=True)
            stream = zlib.decompressobj()
            raw = stream.decompress(compressed, size + 1)
            require(stream.eof and not stream.unconsumed_tail and not stream.unused_data and len(raw) == size,
                    'execution blob expansion size differs')
            require(sha(raw) == digest, 'execution blob original hash differs')
            decoded[digest] = json.loads(raw)
        except (ValueError, TypeError, zlib.error) as exc:
            raise ParagraphError('execution blob cannot restore its original JSON') from exc
    expanded_total = 0
    def expand(value):
        nonlocal expanded_total
        if isinstance(value, dict):
            if set(value) == {'$paragraph_blob'}:
                digest = value['$paragraph_blob']
                require(digest in decoded, 'execution blob reference is absent')
                used.add(digest)
                expanded_total += blobs[digest]['uncompressed_bytes']
                require(expanded_total <= MAX_EXPANDED_PACKET_BYTES, 'expanded execution references exceed byte budget')
                return copy.deepcopy(decoded[digest])
            return {key: expand(item) for key, item in value.items()}
        if isinstance(value, list):
            return [expand(item) for item in value]
        return copy.deepcopy(value)
    result = expand({k: v for k, v in packet.items() if k not in ('execution_blobs', 'packet_encoding', 'packet_sha256')})
    require(used == set(blobs), 'execution blob catalog contains unused records')
    result['packet_sha256'] = content_hash(result)
    return result


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _fields(value, names, context):
    require(isinstance(value, dict), context + ' must be an object')
    require(set(names) <= set(value), context + ' missing fields: ' + ', '.join(sorted(set(names) - set(value))))


def _texts(value, names, context):
    _fields(value, names, context)
    for key in names:
        require(_text(value[key]), context + '.' + key + ' must contain text')


def _span(value, text, context):
    _fields(value, ('start', 'end', 'quote'), context)
    a, b = value['start'], value['end']
    require(type(a) is int and type(b) is int and 0 <= a < b <= len(text), context + ' invalid character span')
    require(value['quote'] == text[a:b], context + ' quote differs from original bytes')
    return text[a:b]


def normalize_sources(sources):
    require(isinstance(sources, dict) and sources, 'sources must be a nonempty mapping')
    result = copy.deepcopy(sources)
    for key, source in result.items():
        require(_text(key), 'source id must contain text')
        _texts(source, ('text',), 'source ' + key)
        digest = sha(source['text'])
        require(source.get('sha256', digest) == digest, 'source hash differs: ' + key)
        source['sha256'] = digest
    return result


def validate_rules(rules):
    _fields(rules, ('policy_id', 'texts', 'dictionary', 'profile'), 'rules')
    require(_text(rules['policy_id']), 'policy id missing')
    _texts(rules['texts'], ('CORE', 'PROSE', 'econ-writing', 'prose-guide'), 'rule bodies')
    dictionary = rules['dictionary']
    require(isinstance(dictionary, dict) and isinstance(dictionary.get('rules'), list), 'dictionary missing')
    ids = [row.get('id') for row in dictionary['rules']]
    require(len(ids) == len(set(ids)) == 142, 'all 142 dictionary rules are required')
    require(isinstance(rules['profile'], (dict, str)) and bool(rules['profile']), 'writing profile missing')
    return content_hash(rules)


def instruction_packet(request, rules, *, paragraph_id=None, event='task-start', unmet=()):
    validate_rules(rules)
    return {
        'event': event, 'text': PRIMARY_RULE + '\n' + JAPANESE_RULE,
        'short_text': PRIMARY_RULE + '\n' + JAPANESE_RULE,
        'original_request': request, 'request_sha256': sha(request), 'policy_id': rules['policy_id'],
        'rules_sha256': content_hash(rules), 'paragraph_id': paragraph_id,
        'unmet': list(unmet), 'next_action': 'Complete the assigned contract and obtain the required current-version review.',
        'rule_texts': copy.deepcopy(rules['texts']), 'dictionary': copy.deepcopy(rules['dictionary']),
        'profile': copy.deepcopy(rules['profile']), 'required_counts': {'dictionary_rules': 142, 'whole_candidate_judgments': 22},
    }


def _task(operation, payload, instructions):
    task = {'operation': operation, 'payload': copy.deepcopy(payload), 'instruction_context': copy.deepcopy(instructions)}
    task['input_sha256'] = content_hash(task)
    return task


def observed_return(task, returned, observe, *, execution_kind, author_id=None):
    """Compare exact returns with the caller's host-owned event lookup."""
    require(execution_kind in EXECUTION_KINDS, 'invalid execution kind')
    require(task.get('input_sha256') == content_hash({k: v for k, v in task.items() if k != 'input_sha256'}),
            'host assignment checksum differs')
    require(callable(observe), 'host event observer is required')
    _texts(returned, ('worker_id', 'event_id', 'input_sha256', 'return_text'), 'host return')
    require(returned['input_sha256'] == task['input_sha256'], 'return belongs to another assignment')
    original = returned['return_text']
    event = observe(returned['event_id'])
    _fields(event, ('worker_id', 'input_sha256', 'return_sha256', 'status', 'execution_kind'), 'host observation')
    require(event['status'] == 'completed', 'host return has no completed event')
    require(event['worker_id'] == returned['worker_id'] and event['input_sha256'] == task['input_sha256'], 'host actor or assignment differs')
    require(event['return_sha256'] == sha(original), 'host original return differs')
    require(event['execution_kind'] == execution_kind, 'execution kind differs from host event')
    if execution_kind == 'independent-subagent':
        _texts(returned, ('launch_ref',), 'subagent return')
        require(event.get('launch_ref') == returned['launch_ref'], 'launch reference differs from host event')
        launch = observe(returned['launch_ref'])
        require(isinstance(launch, dict) and launch.get('worker_id') == returned['worker_id'], 'subagent launch actor differs')
        require(launch.get('input_sha256') == task['input_sha256'], 'subagent launch assignment differs')
        require(launch.get('status') in ('running', 'completed') and launch.get('execution_kind') == execution_kind, 'subagent launch not observed')
        require(author_id is None or returned['worker_id'] != author_id, 'author cannot be recorded as an independent subagent')
    else:
        _texts(returned, ('turn_ref',), 'sequential return')
        require(event.get('turn_ref') == returned['turn_ref'], 'sequential turn reference differs')
    try:
        value = json.loads(original)
    except (ValueError, TypeError) as exc:
        raise ParagraphError('host return must contain an original JSON object') from exc
    require(isinstance(value, dict), 'host return must contain an object')
    record = {key: copy.deepcopy(returned[key]) for key in returned}
    record.update({'return_sha256': sha(original), 'execution_kind': execution_kind,
                   'host_observation': copy.deepcopy(event), 'input': copy.deepcopy(task)})
    if execution_kind == 'independent-subagent':
        record['launch_observation'] = copy.deepcopy(launch)
    return value, record


def invoke_host(host, task, observe, *, execution_kind='independent-subagent', author_id=None):
    require(callable(host), 'host executor must be callable')
    return observed_return(task, host(copy.deepcopy(task)), observe, execution_kind=execution_kind, author_id=author_id)


def _argument_io():
    parent = Path(__file__).resolve().parent
    file = next((parent / name for name in ('argument.py', 'ARGUMENT.py') if (parent / name).is_file()), None)
    require(file is not None, 'argument engine missing')
    spec = importlib.util.spec_from_file_location('paragraph_argument_engine', file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _ArgumentHost:
    """Adapt a paragraph callback to the same observed argument host protocol."""

    def __init__(self, host, observe, execution_kind, author_id=None):
        self.host, self.observe = host, observe
        self.execution_kind, self.author_id = execution_kind, author_id

    def __call__(self, task):
        _, record = invoke_host(self.host, task, self.observe, execution_kind=self.execution_kind,
                                author_id=self.author_id)
        return record


def _record_parts(record):
    task = record.get('task', record.get('input'))
    event = record.get('observation', record.get('host_observation'))
    require(isinstance(task, dict) and isinstance(event, dict), 'execution task or observation missing')
    require('task' not in record or 'input' not in record or record['task'] == record['input'], 'execution task aliases differ')
    require('observation' not in record or 'host_observation' not in record or record['observation'] == record['host_observation'],
            'execution observation aliases differ')
    require(task.get('input_sha256') == content_hash({k: v for k, v in task.items() if k != 'input_sha256'}),
            'execution task checksum differs')
    return task, event


def _record_observer(record):
    _, event = _record_parts(record)
    events = {record['event_id']: event}
    if record.get('execution_kind') == 'independent-subagent':
        events[record['launch_ref']] = record.get('launch_observation')
    return lambda event_id: copy.deepcopy(events.get(event_id))


def validate_execution_record(record, *, execution_kind=None, author_id=None, observe=None):
    """Recheck original execution bytes; an observer also verifies live host records."""
    task, _ = _record_parts(record)
    require(record.get('return_sha256') == sha(record.get('return_text', '')), 'execution original return hash differs')
    kind = execution_kind or record.get('execution_kind')
    value, _ = observed_return(task, record, observe or _record_observer(record),
                               execution_kind=kind, author_id=author_id)
    return value


class _RecordedArgumentHost:
    """Replay one original for validation; this performs no new semantic work."""

    def __init__(self, record, execution_kind, author_id=None, observe=None):
        validate_execution_record(record, execution_kind=execution_kind, author_id=author_id, observe=observe)
        self.record = record
        self.observe = observe or _record_observer(record)

    def __call__(self, task):
        original_task, _ = _record_parts(self.record)
        require(task == original_task, 'argument execution input differs from current adopted content')
        return copy.deepcopy(self.record)


def validate_blueprint(blueprint, sources=None):
    _texts(blueprint, ('version', 'purpose', 'reader', 'central_question', 'central_answer', 'contribution'), 'blueprint')
    _fields(blueprint, ('schema_version', 'completion_conditions', 'argument_structure', 'sections',
                        'paragraphs', 'definitions', 'quantities', 'conditions', 'writing_rules', 'prohibited_rules'), 'blueprint')
    require(blueprint['schema_version'] == SCHEMA_VERSION, 'blueprint schema version differs')
    require(isinstance(blueprint['paragraphs'], list) and blueprint['paragraphs'], 'blueprint paragraphs missing')
    require(isinstance(blueprint['sections'], list) and blueprint['sections'], 'blueprint sections missing')
    sections, ids = set(), set()
    for section in blueprint['sections']:
        _texts(section, ('section_id', 'role', 'claim'), 'section')
        require(section['section_id'] not in sections, 'duplicate section id')
        sections.add(section['section_id'])
    for paragraph in blueprint['paragraphs']:
        _texts(paragraph, ('paragraph_id', 'section_id', 'central_proposition', 'role'), 'blueprint paragraph')
        _fields(paragraph, ('depends_on', 'source_ids', 'scope'), 'blueprint paragraph')
        pid = paragraph['paragraph_id']
        require(pid not in ids and paragraph['section_id'] in sections, 'paragraph id or section differs')
        require(isinstance(paragraph['depends_on'], list) and isinstance(paragraph['source_ids'], list), 'paragraph dependencies must be lists')
        ids.add(pid)
    deps = {p['paragraph_id']: p['depends_on'] for p in blueprint['paragraphs']}
    _layers(deps)
    graph = blueprint['argument_structure']
    checked = _argument_io().validate_argument(graph, sources)
    require(checked['valid'], 'blueprint argument is invalid: ' + '; '.join(r['message'] for r in checked['issues']))
    require(graph['central_question'] == blueprint['central_question'] and graph['central_answer'] == blueprint['central_answer'],
            'blueprint central question or answer differs from argument')
    owners = {}
    for node in graph['nodes']:
        require(node['section_id'] in sections, 'argument node section is absent from blueprint')
        for pid in node['paragraph_ids']:
            require(pid in ids and pid not in owners, 'argument paragraph ownership differs or repeats')
            owners[pid] = node
    require(set(owners) == ids, 'argument does not own every blueprint paragraph')
    for paragraph in blueprint['paragraphs']:
        node = owners[paragraph['paragraph_id']]
        require(node['claim'] == paragraph['central_proposition'] and node['section_id'] == paragraph['section_id'],
                'blueprint paragraph differs from its argument node')
    return content_hash({k: v for k, v in blueprint.items() if k != 'sha256'})


def _layers(dependencies):
    ids = set(dependencies)
    require(all(set(values) <= ids for values in dependencies.values()), 'dependency target absent')
    pending, done, layers = set(ids), set(), []
    while pending:
        ready = sorted(key for key in pending if set(dependencies[key]) <= done)
        require(bool(ready), 'paragraph dependency cycle')
        layers.append(ready)
        done.update(ready)
        pending.difference_update(ready)
    return layers


def seal_blueprint(blueprint, sources=None):
    value = copy.deepcopy(blueprint)
    value['sha256'] = validate_blueprint(value, sources)
    return value


def validate_specification(spec, blueprint, sources=None):
    _texts(spec, ('paragraph_id', 'section_id', 'blueprint_version'), 'paragraph specification')
    require(spec['blueprint_version'] == blueprint['version'], 'specification blueprint version differs')
    bp = next((p for p in blueprint['paragraphs'] if p['paragraph_id'] == spec['paragraph_id']), None)
    require(bp is not None and bp['section_id'] == spec['section_id'], 'paragraph is absent from blueprint')
    for field, keys in {
        'role': ('purpose', 'contribution_to_global_argument'),
        'central_proposition': ('claim', 'logical_status'),
        'logical_structure': ('opening', 'development', 'mechanism', 'implication'),
        'relationships': ('preceding_paragraph', 'inherited_information', 'following_paragraph', 'information_to_pass_forward'),
        'terminology': ('adopted_definitions', 'fixed_quantities', 'required_terms'),
        'scope': ('included', 'excluded', 'content_change_authority'),
        'writing': ('language', 'profile', 'paragraph_rules', 'prohibited_functions', 'instruction_packet', 'source_references'),
        'completion': ('mandatory_claims', 'evidence_correspondence', 'logical_coherence', 'prose_compliance', 'local_review'),
    }.items():
        require(field in spec, 'specification missing field: ' + field)
        _fields(spec[field], keys, field)
    _texts(spec['role'], ('purpose', 'contribution_to_global_argument'), 'role')
    _texts(spec['central_proposition'], ('claim', 'logical_status'), 'central proposition')
    require(spec['central_proposition']['claim'] == bp['central_proposition'], 'specification central proposition differs from blueprint')
    require(isinstance(spec.get('required_content'), list) and spec['required_content'], 'required content missing')
    ids = set()
    for row in spec['required_content']:
        _texts(row, ('proposition_id', 'exact_content', 'source_id', 'evidence_type', 'required_reasoning'), 'required content')
        require(row['proposition_id'] not in ids, 'duplicate proposition in paragraph specification')
        ids.add(row['proposition_id'])
        require('source_location' in row and isinstance(row['source_location'], dict), 'exact source location missing')
        if sources is not None:
            require(row['source_id'] in sources, 'required source missing: ' + row['source_id'])
            _span(row['source_location'], sources[row['source_id']]['text'], 'required source')
    require(isinstance(spec['completion']['mandatory_claims'], list) and set(spec['completion']['mandatory_claims']) == ids,
            'mandatory claims differ from required content')
    _fields(spec, ('argument_node_id', 'parent_proposition', 'local_question', 'supporting_propositions',
                   'inference_form', 'proposition_order', 'logical_completion'), 'paragraph argument')
    require(spec['inference_form'] in ('atomic', 'deductive', 'inductive'), 'invalid paragraph inference form')
    require(_text(spec['local_question']) and _text(spec['argument_node_id']), 'paragraph argument identity missing')
    graph = blueprint['argument_structure']
    argument = _argument_io()
    node = next((n for n in graph['nodes'] if n['node_id'] == spec['argument_node_id']), None)
    require(node is not None and spec['paragraph_id'] in node['paragraph_ids'], 'specification argument ownership differs')
    expected_argument = argument.paragraph_argument(graph, spec['argument_node_id'])
    require(all(spec.get(key) == value for key, value in expected_argument.items()),
            'paragraph argument fields differ from adopted graph')
    require(isinstance(spec['proposition_order'], list) and
            len(spec['proposition_order']) == len(ids) and set(spec['proposition_order']) == ids,
            'paragraph proposition order differs from mandatory content')
    source_ids = spec['writing']['source_references']
    require(isinstance(source_ids, list) and all(_text(sid) for sid in source_ids),
            'paragraph source references must be source IDs')
    if sources is not None:
        require(set(source_ids) | set(bp['source_ids']) <= set(sources),
                'paragraph references an absent source')
        checked = argument.validate_argument(graph, sources)
        require(checked['valid'], 'paragraph argument source bindings differ')
    require(PRIMARY_RULE in str(spec['writing']['instruction_packet']) and JAPANESE_RULE in str(spec['writing']['instruction_packet']),
            'canonical instruction literals missing from paragraph contract')
    return content_hash(spec)


def generate_blueprint(brief, sources, rules, host, observe, *, execution_kind='independent-subagent', author_id=None):
    sources = normalize_sources(sources)
    _texts(brief, ('original_request', 'authority', 'purpose', 'reader'), 'writing brief')
    task = _task('writing:architect', {'brief': brief, 'sources': sources}, instruction_packet(brief['original_request'], rules))
    result, record = invoke_host(host, task, observe, execution_kind=execution_kind, author_id=author_id)
    require(isinstance(result.get('blueprint'), dict), 'architect did not return a blueprint')
    return {'blueprint': seal_blueprint(result['blueprint'], sources), 'execution': record}


def generate_specifications(blueprint, sources, rules, host, observe, *, request, authority,
                            execution_kind='independent-subagent', author_id=None):
    sources = normalize_sources(sources)
    blueprint = seal_blueprint(blueprint, sources)
    task = _task('writing:specify', {'blueprint': blueprint, 'sources': sources, 'original_request': request,
                                   'authority': authority}, instruction_packet(request, rules))
    result, record = invoke_host(host, task, observe, execution_kind=execution_kind, author_id=author_id)
    specs = result.get('specifications')
    require(isinstance(specs, list), 'designer did not return specifications')
    ids = [p['paragraph_id'] for p in blueprint['paragraphs']]
    require([p.get('paragraph_id') for p in specs] == ids, 'designer specification order or coverage differs')
    for spec in specs:
        validate_specification(spec, blueprint, sources)
    return {'specifications': specs, 'execution': record, 'blueprint_sha256': blueprint['sha256']}


def _local_io():
    parent = Path(__file__).resolve().parent
    file = next((parent / name for name in ('local_checks.py', 'LOCAL_CHECKS.py') if (parent / name).is_file()), None)
    require(file is not None, 'local dictionary checker missing')
    spec = importlib.util.spec_from_file_location('paragraph_local_checks', file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scan_paragraph(text, dictionary):
    require(len(dictionary.get('rules', [])) == 142, 'all 142 dictionary rules are required')
    return _local_io().scan({'paragraph.txt': text.encode('utf-8')}, dictionary)


def _check_rows(rows, required, text, context):
    require(isinstance(rows, list), context + ' checks missing')
    ids = [row.get('check_id') for row in rows if isinstance(row, dict)]
    require(set(ids) == set(required) and len(ids) == len(required), context + ' check coverage differs')
    for row in rows:
        _texts(row, ('assessment',), context + ' check')
        require(row.get('verdict') in ('pass', 'fail'), context + ' check verdict missing')
        require(isinstance(row.get('spans'), list) and row['spans'], context + ' inspected text spans missing')
        for span in row['spans']:
            _span(span, text, context + ' check')
    return all(row['verdict'] == 'pass' for row in rows)


def validate_local_review(review, spec, text, sources, hits):
    """Validate concrete paragraph assessments; preserve their original meaning decisions."""
    _fields(review, ('paragraph_id', 'text_sha256', 'spec_sha256', 'checks', 'claim_evidence',
                      'reasoning', 'quantity_evidence', 'occurrence_judgments', 'findings'), 'local review')
    require(review['paragraph_id'] == spec['paragraph_id'], 'local review paragraph differs')
    require(review['text_sha256'] == sha(text) and review['spec_sha256'] == content_hash(spec), 'local review is stale')
    passed = _check_rows(review['checks'], LOCAL_CHECKS, text, 'paragraph')
    require(isinstance(review['findings'], list), 'local review findings missing')
    for finding in review['findings']:
        _texts(finding, ('check_id', 'problem', 'repair'), 'local finding')
        require(finding['check_id'] in LOCAL_CHECKS, 'local finding check id differs')
        _span(finding['span'], text, 'local finding')
    expected = {r['proposition_id']: r for r in spec['required_content']}
    mapped = {}
    for row in review['claim_evidence']:
        _texts(row, ('proposition_id', 'assessment', 'source_id', 'source_sha256'), 'claim evidence')
        pid = row['proposition_id']
        require(pid in expected and pid not in mapped, 'claim evidence id differs or repeats')
        _span(row['target'], text, 'claim target')
        sid = row['source_id']
        require(sid == expected[pid]['source_id'] and sid in sources, 'claim source differs from contract')
        require(row['source_sha256'] == sources[sid]['sha256'], 'claim source hash differs')
        _span(row['source'], sources[sid]['text'], 'claim source')
        require(row['source'] == expected[pid]['source_location'], 'claim source location differs from contract')
        mapped[pid] = row
    missing_claims = set(expected) - set(mapped)
    require(not missing_claims or (not passed and set(review.get('missing_claims', [])) == missing_claims),
            'mandatory claim has no text and source correspondence')
    reasoning = review['reasoning']
    require(isinstance(reasoning, list), 'reasoning correspondence missing')
    reasoning_ids = {r.get('proposition_id') for r in reasoning}
    require(reasoning_ids <= set(expected) and len(reasoning_ids) == len(reasoning), 'required reasoning coverage repeats or differs')
    require(reasoning_ids == set(expected) or (not passed and set(review.get('missing_reasoning', [])) == set(expected) - reasoning_ids),
            'required reasoning coverage differs')
    for row in reasoning:
        _texts(row, ('assessment',), 'reasoning')
        require(row.get('required_reasoning') == expected[row['proposition_id']]['required_reasoning'], 'reasoning contract differs')
        _span(row['target'], text, 'reasoning target')
    quantities = review['quantity_evidence']
    require(isinstance(quantities, list), 'quantity evidence missing')
    expected_quantities = {(m.start(), m.end()) for m in QUANTITY.finditer(text)}
    quantity_targets = set()
    for row in quantities:
        _texts(row, ('source_id', 'source_sha256', 'assessment'), 'quantity evidence')
        target = _span(row['target'], text, 'quantity target')
        location = (row['target']['start'], row['target']['end'])
        require(location in expected_quantities and location not in quantity_targets, 'quantity coverage repeats or splits a token')
        sid = row['source_id']
        require(sid in sources and row['source_sha256'] == sources[sid]['sha256'], 'quantity source differs')
        admitted = {r['source_id'] for r in spec['required_content']} | set(spec['writing']['source_references'])
        require(sid in admitted, 'quantity source is outside the paragraph contract')
        source_quantity = _span(row['source'], sources[sid]['text'], 'quantity source')
        require(target == source_quantity, 'quantity spelling differs from the adopted calculation or source')
        require(any(m.start() == row['source']['start'] and m.end() == row['source']['end'] for m in QUANTITY.finditer(sources[sid]['text'])),
                'quantity source span splits another number')
        quantity_targets.add(location)
    require(quantity_targets == expected_quantities, 'paragraph quantity lacks source correspondence')
    dispositions = review['occurrence_judgments']
    require(isinstance(dispositions, list), 'occurrence judgments missing')
    hit_keys = {(h['rule_id'], h['start'], h['end']) for h in hits}
    found = set()
    for row in dispositions:
        _texts(row, ('rule_id', 'function', 'meaning', 'syntax', 'proposition'), 'occurrence judgment')
        key = (row['rule_id'], row.get('start'), row.get('end'))
        require(key in hit_keys and key not in found, 'occurrence judgment differs or repeats')
        require(row.get('verdict') in ('violation', 'non-prohibited'), 'occurrence verdict missing')
        require(row.get('text_sha256') == sha(text), 'occurrence judgment text differs')
        found.add(key)
        passed &= row['verdict'] == 'non-prohibited'
    require(found == hit_keys, 'dictionary hit lacks occurrence judgment')
    return {'passed': passed and not review['findings'], 'semantic_review_performed': True,
            'dictionary_rules': 142, 'lexical_hits': len(hits), 'release_authorized': False}


class ParagraphRun:
    """Mutable run state with immutable contract and review generations."""

    def __init__(self, state):
        self.state = state
        self._lock = threading.RLock()
        self._checkpoint_path = None

    @classmethod
    def create(cls, *, run_id, request, authority, author_id, operation, blueprint, specifications,
               sources, rules, execution_kind='independent-subagent', original_paragraphs=None,
               editable_ids=None, design_records=()):
        require(operation in OPERATIONS, 'operation requires a registered writing route')
        require(execution_kind in EXECUTION_KINDS, 'execution kind missing')
        require(all(_text(x) for x in (run_id, request, authority, author_id)), 'run identity or authority missing')
        sources = normalize_sources(sources)
        blueprint = seal_blueprint(blueprint, sources)
        validate_rules(rules)
        ids = [p['paragraph_id'] for p in blueprint['paragraphs']]
        require([s.get('paragraph_id') for s in specifications] == ids, 'specification order or coverage differs')
        original = copy.deepcopy(original_paragraphs or {})
        require(set(original) <= set(ids) and all(_text(v) for v in original.values()), 'original paragraph map differs')
        editable = set(ids if editable_ids is None else editable_ids)
        require(editable <= set(ids), 'edit scope contains another paragraph')
        if operation == 'econ-writing:revise':
            require(set(original) == set(ids), 'revision requires every original paragraph')
        if operation in ('econ-writing:translate', 'econ-writing:convert'):
            require(set(original) == set(ids), 'translation and conversion require every original paragraph')
        claimed = set()
        records = {}
        for spec in specifications:
            validate_specification(spec, blueprint, sources)
            props = set(spec['completion']['mandatory_claims'])
            require(not props & claimed, 'proposition assigned to multiple paragraph owners')
            claimed.update(props)
            pid = spec['paragraph_id']
            records[pid] = {'paragraph_id': pid, 'status': 'specified', 'spec': copy.deepcopy(spec),
                            'spec_sha256': content_hash(spec), 'text': original.get(pid),
                            'text_sha256': sha(original[pid]) if pid in original else None,
                            'writer': None, 'assignment': None, 'review': None, 'history': [],
                            'instruction_delivery': [], 'generation': 0, 'repair_count': 0}
        state = {'schema_version': SCHEMA_VERSION, 'run_id': run_id, 'request': request, 'request_sha256': sha(request),
                 'authority': authority, 'author_id': author_id, 'operation': operation, 'blueprint': blueprint,
                 'sources': sources, 'rules': copy.deepcopy(rules), 'rules_sha256': content_hash(rules),
                 'execution_kind': execution_kind, 'original_paragraphs': original, 'editable_ids': sorted(editable),
                 'paragraphs': records, 'design_records': copy.deepcopy(list(design_records)), 'sections': {},
                 'argument_review': None,
                 'manuscript': None, 'global_review': None, 'events': [], 'lifecycle': 'active',
                 'publication_status': 'blocked-unapproved', 'release_authorized': False}
        run = cls(state)
        for pid in ids:
            run.source_ready(pid)
            if pid in original and (operation == 'econ-writing:revise' and pid not in editable):
                records[pid]['status'] = 'drafted'
                records[pid]['writer'] = {'execution_kind': 'preserved-original', 'worker_id': author_id,
                                         'original_sha256': sha(original[pid])}
        return run

    def _active(self):
        require(self.state['lifecycle'] == 'active', 'paragraph run is not active')

    def _event(self, kind, ids, **details):
        row = {'sequence': len(self.state['events']) + 1, 'kind': kind, 'paragraph_ids': list(ids), **details}
        self.state['events'].append(row)
        if self._checkpoint_path is not None:
            self.save(self._checkpoint_path)
        return row

    def _bp(self, pid):
        return next(p for p in self.state['blueprint']['paragraphs'] if p['paragraph_id'] == pid)

    def review_argument(self, host, observe):
        self._active()
        argument = _argument_io()
        structural = argument.validate_argument(self.state['blueprint']['argument_structure'], self.state['sources'])
        require(structural['valid'], 'argument semantic review failed: repair current structural source bindings first')
        adapter = _ArgumentHost(host, observe, self.state['execution_kind'], self.state['author_id'])
        result = argument.review_argument(self.state['blueprint']['argument_structure'], self.state['sources'], adapter,
            instructions=instruction_packet(self.state['request'], self.state['rules'], event='argument-review'))
        self.state['argument_review'] = result
        self._event('argument-reviewed' if result['valid'] else 'argument-review-failed', self.state['paragraphs'],
                    event_id=result['record']['event_id'])
        return copy.deepcopy(result)

    def _argument_review_current(self):
        result = self.state.get('argument_review')
        return (isinstance(result, dict) and result.get('valid') is True and
                result.get('argument_sha256') == _argument_io().argument_sha256(self.state['blueprint']['argument_structure']))

    def _binding(self, pid):
        row = self.state['paragraphs'][pid]
        source_ids = self._source_ids(pid)
        return {'paragraph_id': pid, 'spec_sha256': row['spec_sha256'],
                'blueprint_sha256': self.state['blueprint']['sha256'], 'rules_sha256': self.state['rules_sha256'],
                'request_sha256': self.state['request_sha256'],
                'sources': {key: self.state['sources'][key]['sha256'] for key in sorted(source_ids)},
                'dependencies': {key: self.state['paragraphs'][key]['text_sha256'] for key in self._bp(pid)['depends_on']}}

    def _source_ids(self, pid):
        """Collect every source consumed by the paragraph's current contract."""
        row = self.state['paragraphs'][pid]
        return ({item['source_id'] for item in row['spec']['required_content']} |
                set(row['spec']['writing']['source_references']) | set(self._bp(pid)['source_ids']))

    def source_ready(self, pid):
        self._active()
        row = self.state['paragraphs'][pid]
        validate_specification(row['spec'], self.state['blueprint'], self.state['sources'])
        if row['status'] == 'specified':
            row['status'] = 'source-ready'
            self._event('source-ready', [pid], spec_sha256=row['spec_sha256'])

    def tasks(self):
        self._active()
        result = []
        for bp in self.state['blueprint']['paragraphs']:
            pid, row = bp['paragraph_id'], self.state['paragraphs'][bp['paragraph_id']]
            if row['status'] != 'source-ready' or pid not in self.state['editable_ids']:
                continue
            if not all(self.state['paragraphs'][dep]['text'] and
                       self.state['paragraphs'][dep]['status'] in
                       ('drafted', 'locally-reviewed', 'integrated', 'globally-reviewed')
                       for dep in bp['depends_on']):
                continue
            packet = instruction_packet(self.state['request'], self.state['rules'], paragraph_id=pid, event='worker-start')
            payload = {'run_id': self.state['run_id'], 'original_request': self.state['request'], 'authority': self.state['authority'],
                       'operation': self.state['operation'], 'blueprint': self.state['blueprint'], 'specification': row['spec'],
                       'sources': {sid: self.state['sources'][sid] for sid in self._binding(pid)['sources']},
                       'neighbors': {neighbor: self.state['paragraphs'][neighbor]['text'] for neighbor in
                                     (row['spec']['relationships']['preceding_paragraph'], row['spec']['relationships']['following_paragraph'])
                                     if neighbor in self.state['paragraphs']},
                       'binding': self._binding(pid), 'original_text': self.state['original_paragraphs'].get(pid),
                       'required_return': {'paragraph_id': pid, 'text': 'Complete paragraph text', 'binding': self._binding(pid)}}
            result.append(_task('writing:paragraph', payload, packet))
        return result

    def assign(self, task):
        self._active()
        require(self._argument_review_current(), 'current argument semantic review is required before assignment')
        pid = task['payload']['specification']['paragraph_id']
        row = self.state['paragraphs'][pid]
        require(row['status'] == 'source-ready', 'paragraph is not ready for assignment')
        require(task in self.tasks(), 'assignment differs from current contract')
        row['assignment'] = copy.deepcopy(task)
        row['status'] = 'assigned'
        row['instruction_delivery'].append({'state': 'sent', 'instruction_sha256': content_hash(task['instruction_context']),
                                            'input_sha256': task['input_sha256']})
        self._event('assigned', [pid], input_sha256=task['input_sha256'])

    def accept_draft(self, pid, returned, observe):
        self._active()
        row = self.state['paragraphs'][pid]
        require(row['status'] == 'assigned' and row['assignment'], 'paragraph has no active assignment')
        task = row['assignment']
        require(task['payload']['binding'] == self._binding(pid), 'assignment dependencies changed')
        value, record = observed_return(task, returned, observe, execution_kind=self.state['execution_kind'], author_id=self.state['author_id'])
        require(value.get('paragraph_id') == pid and value.get('binding') == self._binding(pid), 'draft contract differs')
        require(_text(value.get('text')), 'writer returned no paragraph text')
        require(pid in self.state['editable_ids'], 'writer changed a retained paragraph')
        row.update({'text': value['text'], 'text_sha256': sha(value['text']), 'writer': record,
                    'status': 'drafted', 'review': None, 'generation': row['generation'] + 1})
        row['instruction_delivery'].append({'state': 'received', 'input_sha256': task['input_sha256'], 'event_id': record['event_id']})
        if value.get('read_instruction_sha256') == content_hash(task['instruction_context']):
            row['instruction_delivery'].append({'state': 'read', 'instruction_sha256': value['read_instruction_sha256'], 'event_id': record['event_id']})
        self._event('drafted', [pid], text_sha256=row['text_sha256'], event_id=record['event_id'])
        return copy.deepcopy(row)

    def write(self, host, observe, *, max_workers=1):
        self._active()
        if not self._argument_review_current():
            require(self.review_argument(host, observe)['valid'], 'argument semantic review failed')
        if any(row['status'] == 'assigned' for row in self.state['paragraphs'].values()):
            self.recover_assignments(host, observe)
        require(not any(row['status'] == 'assigned' for row in self.state['paragraphs'].values()),
                'host assignments are still running; restore their original returns before continuation')
        require(type(max_workers) is int and max_workers > 0, 'writer capacity must be positive')
        capacity = max_workers if self.state['execution_kind'] == 'independent-subagent' else 1
        produced = []
        while True:
            tasks = self.tasks()
            if not tasks:
                break
            for task in tasks:
                self.assign(task)
            def execute(task):
                return task['payload']['specification']['paragraph_id'], host(copy.deepcopy(task))
            with ThreadPoolExecutor(max_workers=capacity) as pool:
                futures = [pool.submit(execute, task) for task in tasks]
                failures = []
                for task, future in zip(tasks, futures):
                    pid = task['payload']['specification']['paragraph_id']
                    returned = None
                    try:
                        _, returned = future.result()
                        self.accept_draft(pid, returned, observe)
                        produced.append(pid)
                    except Exception as exc:
                        # A transport exception can occur after the worker starts.
                        # Retain that exact assignment until host recovery records
                        # its terminal result; only a matching terminal return may
                        # release it for another generation.
                        terminal = None
                        if isinstance(returned, dict) and _text(returned.get('event_id')):
                            try:
                                event = observe(returned['event_id'])
                                if (isinstance(event, dict) and event.get('status') == 'completed' and
                                        event.get('input_sha256') == task['input_sha256'] and
                                        event.get('worker_id') == returned.get('worker_id') and
                                        isinstance(returned.get('return_text'), str) and
                                        event.get('return_sha256') == sha(returned['return_text'])):
                                    terminal = event
                            except Exception:
                                # The preserved assignment is recovered by its input hash.
                                pass
                        if terminal is not None:
                            row = self.state['paragraphs'][pid]
                            row['history'].append({'kind': 'writer-invalid-return',
                                                   'assignment': copy.deepcopy(task),
                                                   'returned': copy.deepcopy(returned),
                                                   'host_observation': copy.deepcopy(terminal),
                                                   'error': str(exc)})
                            row['status'], row['assignment'] = 'source-ready', None
                        self._event('writer-failed' if terminal is not None else 'writer-recovery-required',
                                    [pid], error=str(exc), input_sha256=task['input_sha256'])
                        failures.append(exc)
                if failures:
                    raise ParagraphError('writer failed: ' + str(failures[0]))
        return produced

    def recover_assignments(self, host, observe):
        """Recover each pending original from the adapter's persisted host registry."""
        recover = getattr(host, 'recover', None)
        require(callable(recover), 'pending assignments require host.recover(task) or accept_draft with the original return')
        result = {'recovered': [], 'running': [], 'failed': []}
        for pid, row in self.state['paragraphs'].items():
            if row['status'] != 'assigned':
                continue
            task = row['assignment']
            receipt = recover(copy.deepcopy(task))
            _texts(receipt, ('event_id', 'status'), 'assignment recovery receipt')
            event = observe(receipt['event_id'])
            require(isinstance(event, dict) and event.get('input_sha256') == task['input_sha256'] and
                    event.get('status') == receipt['status'], 'recovery receipt differs from host event')
            if receipt['status'] == 'completed':
                returned = receipt.get('returned')
                require(isinstance(returned, dict) and returned.get('event_id') == receipt['event_id'], 'recovery original return missing')
                self.accept_draft(pid, returned, observe)
                result['recovered'].append(pid)
            elif receipt['status'] == 'failed':
                row['status'], row['assignment'] = 'source-ready', None
                self._event('writer-failed', [pid], event_id=receipt['event_id'], recovery=True)
                result['failed'].append(pid)
            else:
                require(receipt['status'] == 'running', 'recovery host status differs')
                result['running'].append(pid)
        return result

    def review(self, pid, host, observe):
        self._active()
        row = self.state['paragraphs'][pid]
        require(row['status'] in ('drafted', 'locally-reviewed') and row['text'], 'paragraph has no current draft')
        hits = scan_paragraph(row['text'], self.state['rules']['dictionary'])
        binding = self._binding(pid)
        task = _task('writing:paragraph-review', {'paragraph_id': pid, 'text': row['text'], 'text_sha256': row['text_sha256'],
                     'specification': row['spec'], 'sources': self.state['sources'], 'binding': binding,
                     'required_checks': list(LOCAL_CHECKS), 'lexical_hits': hits,
                     'original_text': self.state['original_paragraphs'].get(pid)},
                     instruction_packet(self.state['request'], self.state['rules'], paragraph_id=pid))
        value, record = invoke_host(host, task, observe, execution_kind=self.state['execution_kind'])
        if self.state['execution_kind'] == 'independent-subagent':
            require(record['worker_id'] != row['writer']['worker_id'], 'local independent reviewer is the paragraph writer')
        require(value.get('binding') == binding, 'local review input bindings differ')
        try:
            result = validate_local_review(value, row['spec'], row['text'], self.state['sources'], hits)
        except ParagraphError as exc:
            result = {'passed': False, 'structural_errors': [str(exc)], 'semantic_review_performed': True,
                      'dictionary_rules': 142, 'lexical_hits': len(hits), 'release_authorized': False}
        row['review'] = {'record': record, 'result': result, 'binding': binding, 'text_sha256': row['text_sha256']}
        row['status'] = 'locally-reviewed' if result['passed'] else 'drafted'
        row['instruction_delivery'].append({'state': 'checked', 'passed': result['passed'], 'event_id': record['event_id']})
        self._event('locally-reviewed' if result['passed'] else 'local-review-failed', [pid], event_id=record['event_id'])
        return copy.deepcopy(row['review'])

    def repair(self, pid, host, observe):
        row = self.state['paragraphs'][pid]
        require(row['review'] and not row['review']['result']['passed'], 'paragraph has no failed review to repair')
        require(pid in self.state['editable_ids'], 'repair is outside authorized paragraph scope')
        findings = json.loads(row['review']['record']['return_text']).get('findings', [])
        findings += [{'check_id': 'evidence-correspondence', 'problem': error, 'repair': error}
                     for error in row['review']['result'].get('structural_errors', [])]
        self.invalidate('text-regeneration', [pid], reason='Repair the recorded paragraph findings.')
        row['status'] = 'source-ready'
        task = next(task for task in self.tasks() if task['payload']['specification']['paragraph_id'] == pid)
        task['payload']['repair_findings'] = findings
        task['payload']['prior_text'] = row['text']
        task['input_sha256'] = content_hash({key: value for key, value in task.items() if key != 'input_sha256'})
        row['assignment'] = task
        row['status'] = 'assigned'
        self.accept_draft(pid, host(copy.deepcopy(task)), observe)
        row['repair_count'] += 1
        return self.review(pid, host, observe)

    def _integration(self, ids, host, observe, *, section_id=None):
        self._active()
        require(all(self.state['paragraphs'][pid]['status'] in ('locally-reviewed', 'integrated') for pid in ids), 'integration requires locally reviewed paragraphs')
        texts = {pid: self.state['paragraphs'][pid]['text'] for pid in ids}
        hashes = {pid: sha(text) for pid, text in texts.items()}
        operation = 'writing:section-integrate' if section_id is not None else 'writing:manuscript-integrate'
        outline_record, outline, argument_comparison = None, None, None
        if section_id is None:
            if not self._argument_review_current():
                require(self.review_argument(host, observe)['valid'], 'argument semantic review failed')
            argument = _argument_io()
            adapter = _ArgumentHost(host, observe, self.state['execution_kind'], self.state['author_id'])
            manuscript_rows = [{'paragraph_id': pid, 'section_id': self._bp(pid)['section_id'], 'text': texts[pid]} for pid in ids]
            outline = argument.reverse_outline(manuscript_rows, adapter,
                instructions=instruction_packet(self.state['request'], self.state['rules'], event='reverse-outline'))
            outline_record = outline['record']
            argument_comparison = argument.compare_outline(self.state['blueprint']['argument_structure'], outline,
                self.state['sources'], adapter,
                instructions=instruction_packet(self.state['request'], self.state['rules'], event='argument-compare'))
            if not argument_comparison['valid']:
                result = {'status': 'failed', 'paragraph_ids': ids, 'paragraph_hashes': hashes,
                          'reverse_outline': outline, 'outline_execution': outline_record,
                          'argument_comparison': argument_comparison, 'findings': argument_comparison['findings']}
                self._event('argument-comparison-failed', ids, event_id=argument_comparison['record']['event_id'])
                self.state['manuscript'] = None
                return result
        task = _task(operation, {'blueprint': self.state['blueprint'], 'paragraphs': texts,
                     'specifications': {pid: self.state['paragraphs'][pid]['spec'] for pid in ids},
                     'sources': self.state['sources'], 'paragraph_hashes': hashes,
                     'section_id': section_id, 'reverse_outline': outline if section_id is None else None,
                     'argument_comparison': argument_comparison,
                     'required_checks': list(INTEGRATION_CHECKS if section_id is not None else GLOBAL_CHECKS)},
                     instruction_packet(self.state['request'], self.state['rules']))
        value, record = invoke_host(host, task, observe, execution_kind=self.state['execution_kind'])
        require(value.get('paragraph_hashes') == hashes, 'integration input changed')
        require(isinstance(value.get('paragraphs'), dict) and set(value['paragraphs']) == set(ids), 'integration changed paragraph coverage')
        changed = [pid for pid in ids if value['paragraphs'][pid] != texts[pid]]
        if changed:
            require(set(changed) <= set(self.state['editable_ids']), 'integration changed retained text')
            for pid in changed:
                require(_text(value['paragraphs'][pid]), 'integration removed a paragraph')
            self.invalidate('integration-edit', changed, reason='Integrator changed paragraph text.')
            for pid in changed:
                row = self.state['paragraphs'][pid]
                row.update({'text': value['paragraphs'][pid], 'text_sha256': sha(value['paragraphs'][pid]),
                            'status': 'drafted', 'writer': record, 'generation': row['generation'] + 1})
            return {'status': 'recheck-required', 'changed_paragraph_ids': changed, 'execution': record}
        manuscript = '\n\n'.join(texts[pid] for pid in ids)
        require(value.get('text') == manuscript, 'integration text does not match its paragraph map')
        passed = _check_rows(value.get('checks'), INTEGRATION_CHECKS if section_id is not None else GLOBAL_CHECKS, manuscript, 'integration')
        require(isinstance(value.get('findings'), list), 'integration findings missing')
        result = {'status': 'integrated' if passed and not value['findings'] else 'failed',
                  'text': manuscript, 'sha256': sha(manuscript), 'paragraph_ids': ids, 'paragraph_hashes': hashes,
                  'execution': record, 'findings': value['findings']}
        if result['status'] == 'integrated':
            for pid in ids:
                self.state['paragraphs'][pid]['status'] = 'integrated'
            if section_id is not None:
                self.state['sections'][section_id] = result
            else:
                comparison = value.get('outline_comparison')
                require(isinstance(comparison, list) and [r.get('paragraph_id') for r in comparison] == ids, 'outline comparison coverage differs')
                for item in comparison:
                    _texts(item, ('assessment',), 'outline comparison')
                    pid = item['paragraph_id']
                    require(item.get('spec_sha256') == self.state['paragraphs'][pid]['spec_sha256'], 'outline comparison specification differs')
                    require(item.get('outline_sha256') == content_hash(outline), 'outline comparison source differs')
                    require(item.get('verdict') == 'pass', 'outline comparison failed')
                result['reverse_outline'] = outline
                result['outline_execution'] = outline_record
                result['outline_comparison'] = comparison
                result['argument_comparison'] = argument_comparison
                self.state['manuscript'] = result
        self._event(result['status'], ids, event_id=record['event_id'], section_id=section_id)
        return copy.deepcopy(result)

    def integrate_section(self, section_id, host, observe):
        ids = [p['paragraph_id'] for p in self.state['blueprint']['paragraphs'] if p['section_id'] == section_id]
        require(ids, 'section is absent')
        return self._integration(ids, host, observe, section_id=section_id)

    def integrate_manuscript(self, host, observe):
        sections = {p['section_id'] for p in self.state['blueprint']['paragraphs']}
        require(sections <= set(self.state['sections']), 'section integration missing')
        ids = [p['paragraph_id'] for p in self.state['blueprint']['paragraphs']]
        return self._integration(ids, host, observe)

    def invalidate(self, kind, paragraph_ids, *, reason):
        self._active()
        require(kind in ('text-regeneration', 'integration-edit', 'specification-change', 'source-change', 'rules-change', 'dependency-change', 'argument-change'), 'invalidation kind differs')
        affected = set(paragraph_ids)
        require(affected <= set(self.state['paragraphs']), 'invalidation paragraph absent')
        while True:
            expanded = affected | {p['paragraph_id'] for p in self.state['blueprint']['paragraphs'] if set(p['depends_on']) & affected}
            if expanded == affected:
                break
            affected = expanded
        for pid in affected:
            row = self.state['paragraphs'][pid]
            row['history'].append({'kind': kind, 'reason': reason, 'text': row['text'], 'text_sha256': row['text_sha256'],
                                   'spec_sha256': row['spec_sha256'], 'writer': row['writer'], 'review': row['review']})
            row['review'] = None
            row['assignment'] = None
            row['status'] = 'drafted' if row['text'] else 'specified'
        for key in list(self.state['sections']):
            if affected & set(self.state['sections'][key]['paragraph_ids']):
                del self.state['sections'][key]
        self.state['manuscript'] = None
        self.state['global_review'] = None
        if kind in ('specification-change', 'source-change', 'rules-change', 'dependency-change', 'argument-change'):
            self.state['argument_review'] = None
        self.state['publication_status'] = 'blocked-unapproved'
        self.state['release_authorized'] = False
        self._event('invalidated', sorted(affected), change_kind=kind, reason=reason)
        return sorted(affected)

    def update_sources(self, sources):
        sources = normalize_sources(sources)
        require(set(sources) == set(self.state['sources']), 'source-set changes require revised specifications')
        changed = {key for key in sources if sources[key]['sha256'] != self.state['sources'][key]['sha256']}
        affected = [pid for pid in self.state['paragraphs'] if changed & self._source_ids(pid)]
        invalidated = self.invalidate('source-change', affected, reason='Source bytes changed.') if affected else []
        self.state['sources'] = sources
        if changed:
            # Argument and integration assignments consume the complete source
            # catalog.  Their original inputs change even when only another
            # paragraph owns the updated passage.  Local reviews retain their
            # narrower binding and remain reusable when it is unchanged.
            self.state['argument_review'] = None
            self.state['sections'] = {}
            self.state['manuscript'] = None
            self.state['global_review'] = None
            self.state['publication_status'] = 'blocked-unapproved'
            self.state['release_authorized'] = False
            for pid, row in self.state['paragraphs'].items():
                if pid not in invalidated and row['status'] in ('integrated', 'globally-reviewed'):
                    row['status'] = 'locally-reviewed'
        for pid in invalidated:
            row = self.state['paragraphs'][pid]
            try:
                validate_specification(row['spec'], self.state['blueprint'], sources)
            except ParagraphError:
                row['status'] = 'specified'
        self._event('sources-updated', invalidated, sources={key: value['sha256'] for key, value in sources.items()})
        return invalidated

    def update_rules(self, rules):
        validate_rules(rules)
        if content_hash(rules) == self.state['rules_sha256']:
            return []
        ids = self.invalidate('rules-change', self.state['paragraphs'], reason='Adopted rule bytes changed.')
        self.state['rules'] = copy.deepcopy(rules)
        self.state['rules_sha256'] = content_hash(rules)
        self._event('rules-updated', ids, rules_sha256=self.state['rules_sha256'])
        return ids

    def update_specification(self, spec):
        validate_specification(spec, self.state['blueprint'], self.state['sources'])
        pid = spec['paragraph_id']
        require(pid in self.state['editable_ids'], 'specification change outside authorized paragraph scope')
        claimed_elsewhere = {claim for key, row in self.state['paragraphs'].items() if key != pid
                             for claim in row['spec']['completion']['mandatory_claims']}
        require(not set(spec['completion']['mandatory_claims']) & claimed_elsewhere,
                'proposition assigned to multiple paragraph owners')
        if content_hash(spec) == self.state['paragraphs'][pid]['spec_sha256']:
            return []
        ids = self.invalidate('specification-change', [pid], reason='Paragraph contract changed.')
        self.state['paragraphs'][pid].update({'spec': copy.deepcopy(spec), 'spec_sha256': content_hash(spec), 'status': 'source-ready'})
        self._event('specification-updated', ids, spec_sha256=content_hash(spec))
        return ids

    def change_dependencies(self, pid, depends_on):
        require(pid in self.state['editable_ids'], 'dependency change outside authorized paragraph scope')
        blueprint = copy.deepcopy(self.state['blueprint'])
        target = next(p for p in blueprint['paragraphs'] if p['paragraph_id'] == pid)
        target['depends_on'] = list(depends_on)
        blueprint = seal_blueprint(blueprint)
        if blueprint['sha256'] == self.state['blueprint']['sha256']:
            return []
        # A new global blueprint binds every local assessment to its revised graph.
        affected = self.invalidate('dependency-change', self.state['paragraphs'], reason='Blueprint dependency graph changed.')
        self.state['blueprint'] = blueprint
        self._event('dependencies-updated', affected, blueprint_sha256=blueprint['sha256'])
        return affected

    def update_dependencies(self, pid, depends_on):
        """Apply the documented dependency update while preserving the old entry point."""
        return self.change_dependencies(pid, depends_on)

    def update_blueprint(self, blueprint, specifications):
        """Adopt a revised argument and contracts while retaining all manuscript bytes."""
        self._active()
        blueprint = seal_blueprint(blueprint, self.state['sources'])
        ids = [p['paragraph_id'] for p in blueprint['paragraphs']]
        require(ids == list(self.state['paragraphs']) and [s.get('paragraph_id') for s in specifications] == ids,
                'blueprint update must retain the authorized paragraph set and order')
        claimed = set()
        for spec in specifications:
            validate_specification(spec, blueprint, self.state['sources'])
            props = set(spec['completion']['mandatory_claims'])
            require(not props & claimed, 'proposition assigned to multiple paragraph owners')
            claimed.update(props)
            if spec['paragraph_id'] not in self.state['editable_ids']:
                old = self.state['paragraphs'][spec['paragraph_id']]['spec']
                for field in ('central_proposition', 'required_content', 'scope'):
                    require(spec[field] == old[field], 'blueprint change alters retained paragraph content')
        if blueprint == self.state['blueprint'] and all(s == self.state['paragraphs'][s['paragraph_id']]['spec'] for s in specifications):
            return []
        affected = self.invalidate('argument-change', ids, reason='Adopted argument and blueprint changed.')
        self.state['blueprint'] = blueprint
        for spec in specifications:
            row = self.state['paragraphs'][spec['paragraph_id']]
            row.update(spec=copy.deepcopy(spec), spec_sha256=content_hash(spec))
            if not row['text']:
                row['status'] = 'source-ready'
        self._event('blueprint-updated', affected, blueprint_sha256=blueprint['sha256'])
        return affected

    def packet(self, *, target='message://final', text=None, compact=None):
        require(self.state['manuscript'] is not None, 'global integration missing')
        manuscript = self.state['manuscript']['text']
        require(text is None or text == manuscript, 'candidate differs from integrated manuscript')
        result = copy.deepcopy(self.state)
        result['target'] = target
        result['candidate_sha256'] = sha(manuscript)
        result['publication_status'] = 'awaiting-independent-final-review'
        result['release_authorized'] = False
        result['packet_sha256'] = content_hash(result)
        if compact is True or (compact is None and len(canonical(result)) > 8 * 1024 * 1024):
            return compact_packet(result)
        return result

    def record_global_review(self, receipt, observe):
        """Record a native final-review event; this function does not publish."""
        require(self.state['manuscript'] is not None, 'global integration missing')
        _texts(receipt, ('event_id', 'candidate_sha256', 'return_sha256'), 'native review receipt')
        require(receipt['candidate_sha256'] == self.state['manuscript']['sha256'], 'native review candidate differs')
        event = observe(receipt['event_id'])
        require(isinstance(event, dict) and event.get('status') == 'completed', 'native review event incomplete')
        require(event.get('return_sha256') == receipt['return_sha256'] and event.get('candidate_sha256') == receipt['candidate_sha256'], 'native review receipt differs')
        require(event.get('review_plan') == 'strict-reviewed' and set(event.get('roles', [])) == {'quality-a', 'quality-b', 'compliance'}, 'native independent review roles differ')
        require(event.get('decision') == 'passed', 'native review did not pass')
        self.state['global_review'] = copy.deepcopy(event)
        for row in self.state['paragraphs'].values():
            row['status'] = 'globally-reviewed'
        self._event('globally-reviewed', self.state['paragraphs'], event_id=receipt['event_id'])

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        require(not path.is_symlink(), 'state path is a symlink')
        value = {'sha256': content_hash(self.state), 'state': self.state}
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name, mode='wb', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
            temporary = None
            self._checkpoint_path = path
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls, path):
        path = Path(path)
        require(path.is_file() and not path.is_symlink(), 'state file missing or symlink')
        value = json.loads(path.read_text(encoding='utf-8'))
        require(isinstance(value, dict) and value.get('sha256') == content_hash(value.get('state')), 'state checksum differs')
        state = value['state']
        require(state.get('schema_version') == SCHEMA_VERSION, 'state schema differs')
        require(state['request_sha256'] == sha(state['request']), 'restored original request differs')
        require(state['rules_sha256'] == validate_rules(state['rules']), 'restored rules differ')
        require(state['blueprint']['sha256'] == validate_blueprint(state['blueprint']), 'restored blueprint differs')
        normalize_sources(state['sources'])
        for pid, row in state['paragraphs'].items():
            require(row['status'] in STATES and row['spec_sha256'] == content_hash(row['spec']), 'restored specification differs')
            validate_specification(row['spec'], state['blueprint'])
            require(row['text_sha256'] == (sha(row['text']) if row['text'] else None), 'restored paragraph text differs')
            if row.get('writer') and row['writer'].get('execution_kind') != 'preserved-original':
                validate_execution_record(row['writer'], execution_kind=state['execution_kind'], author_id=state['author_id'])
            if row.get('review'):
                validate_execution_record(row['review']['record'], execution_kind=state['execution_kind'])
        run = cls(state)
        run._checkpoint_path = path
        run._event('resumed', state['paragraphs'], instruction_context=instruction_packet(state['request'], state['rules'], event='task-resume'))
        return run


def validate_packet(packet, candidate_text=None, text_artifacts=None, *, observe=None):
    """Return artifact-bound diagnostics consumed by the native whole-candidate gate."""
    issues = []
    submitted_packet = packet
    try:
        require(isinstance(packet, dict), 'paragraph packet must be an object')
        digest = content_hash({k: v for k, v in packet.items() if k != 'packet_sha256'})
        require(packet.get('packet_sha256') == digest, 'paragraph packet checksum differs')
        packet = unpack_packet(packet)
        require(packet.get('operation') in OPERATIONS, 'paragraph packet operation differs')
        require(packet.get('release_authorized') is False, 'paragraph packet cannot authorize publication')
        require(packet['request_sha256'] == sha(packet['request']), 'packet original request differs')
        require(packet['rules_sha256'] == validate_rules(packet['rules']), 'packet rules differ')
        blueprint = packet['blueprint']
        sources = normalize_sources(packet['sources'])
        require(blueprint['sha256'] == validate_blueprint(blueprint, sources), 'packet blueprint differs')
        ids = [p['paragraph_id'] for p in blueprint['paragraphs']]
        require(set(ids) == set(packet['paragraphs']), 'packet paragraph coverage differs')
        execution_kind = packet['execution_kind']
        argument = _argument_io()
        argument_record = packet['argument_review']['record']
        argument_review = argument.review_argument(blueprint['argument_structure'], sources,
            _RecordedArgumentHost(argument_record, execution_kind, packet['author_id'], observe),
            instructions=instruction_packet(packet['request'], packet['rules'], event='argument-review'))
        require(argument_review['valid'] and argument_review['argument_sha256'] == packet['argument_review']['argument_sha256'],
                'adopted argument review failed or differs')
        run = ParagraphRun(copy.deepcopy(packet))
        claimed = set()
        for pid in ids:
            row = packet['paragraphs'][pid]
            require(row['status'] in ('integrated', 'globally-reviewed'), 'paragraph integration incomplete: ' + pid)
            require(row['spec_sha256'] == validate_specification(row['spec'], blueprint, sources), 'paragraph specification differs')
            claims = set(row['spec']['completion']['mandatory_claims'])
            require(not claimed & claims, 'proposition assigned to multiple paragraph owners')
            claimed.update(claims)
            require(row['text_sha256'] == sha(row['text']), 'paragraph text differs')
            writer = row['writer']
            if writer.get('execution_kind') == 'preserved-original':
                require(pid not in packet['editable_ids'] and row['text'] == packet['original_paragraphs'][pid] and
                        writer.get('original_sha256') == sha(row['text']), 'preserved original writer record differs')
            else:
                original_draft = validate_execution_record(writer, execution_kind=execution_kind,
                                                           author_id=packet['author_id'], observe=observe)
                writer_task, _ = _record_parts(writer)
                if writer_task['operation'] == 'writing:paragraph':
                    require(original_draft.get('paragraph_id') == pid and original_draft.get('text') == row['text'],
                            'paragraph draft differs from writer original return')
                else:
                    require(writer_task['operation'] in ('writing:section-integrate', 'writing:manuscript-integrate') and
                            original_draft.get('paragraphs', {}).get(pid) == row['text'],
                            'paragraph edit differs from integrator original return')
            require(row['review'] and row['review']['binding'] == run._binding(pid), 'paragraph review binding differs')
            review = row['review']['record']
            original_review = validate_execution_record(review, execution_kind=execution_kind, observe=observe)
            review_task, _ = _record_parts(review)
            payload = review_task['payload']
            require(review_task['operation'] == 'writing:paragraph-review' and payload.get('text') == row['text'] and
                    payload.get('specification') == row['spec'] and payload.get('binding') == run._binding(pid),
                    'local review assignment differs from current paragraph')
            require(review_task['instruction_context'] == instruction_packet(packet['request'], packet['rules'], paragraph_id=pid),
                    'local reviewer did not receive the adopted instructions')
            require(all(payload['sources'].get(sid) == sources[sid] for sid in run._binding(pid)['sources']),
                    'local review source assignment differs')
            if execution_kind == 'independent-subagent':
                require(review['worker_id'] != writer['worker_id'], 'local independent reviewer is the paragraph writer')
            require(original_review.get('binding') == run._binding(pid), 'local original review binding differs')
            result = validate_local_review(original_review, row['spec'], row['text'], sources,
                                           scan_paragraph(row['text'], packet['rules']['dictionary']))
            require(result['passed'], 'paragraph local review failed: ' + pid)
            if pid not in packet['editable_ids']:
                require(row['text'] == packet['original_paragraphs'][pid], 'retained paragraph changed')
        manuscript = '\n\n'.join(packet['paragraphs'][pid]['text'] for pid in ids)
        require(packet['manuscript']['text'] == manuscript and packet['manuscript']['sha256'] == sha(manuscript), 'manuscript differs from paragraph assembly')
        require(packet['candidate_sha256'] == sha(manuscript), 'packet candidate binding differs')
        expected_sections = {p['section_id'] for p in blueprint['paragraphs']}
        require(set(packet['sections']) == expected_sections, 'section integration coverage differs')
        for section_id, integration in list(packet['sections'].items()) + [(None, packet['manuscript'])]:
            section_ids = [p['paragraph_id'] for p in blueprint['paragraphs'] if section_id is None or p['section_id'] == section_id]
            section_texts = {pid: packet['paragraphs'][pid]['text'] for pid in section_ids}
            section_hashes = {pid: sha(text) for pid, text in section_texts.items()}
            section_text = '\n\n'.join(section_texts.values())
            record = integration['execution']
            original = validate_execution_record(record, execution_kind=execution_kind, observe=observe)
            integration_task, _ = _record_parts(record)
            expected_payload = {'blueprint': blueprint, 'paragraphs': section_texts,
                'specifications': {pid: packet['paragraphs'][pid]['spec'] for pid in section_ids},
                'sources': sources, 'paragraph_hashes': section_hashes, 'section_id': section_id,
                'reverse_outline': packet['manuscript']['reverse_outline'] if section_id is None else None,
                'argument_comparison': packet['manuscript']['argument_comparison'] if section_id is None else None,
                'required_checks': list(GLOBAL_CHECKS if section_id is None else INTEGRATION_CHECKS)}
            expected_task = _task('writing:manuscript-integrate' if section_id is None else 'writing:section-integrate',
                                  expected_payload, instruction_packet(packet['request'], packet['rules']))
            require(integration_task == expected_task,
                    'integration assignment differs from current blueprint or text')
            require(original.get('paragraphs') == section_texts and original.get('paragraph_hashes') == section_hashes,
                    'integration original paragraph mapping differs')
            require(original.get('text') == section_text and integration.get('text') == section_text, 'integration original text differs')
            require(_check_rows(original.get('checks'), INTEGRATION_CHECKS if section_id is not None else GLOBAL_CHECKS,
                                section_text, 'integration') and original.get('findings') == [], 'integration review failed')
        outline_record = packet['manuscript']['outline_execution']
        manuscript_rows = [{'paragraph_id': pid, 'section_id': run._bp(pid)['section_id'],
                            'text': packet['paragraphs'][pid]['text']} for pid in ids]
        outline = argument.reverse_outline(manuscript_rows,
            _RecordedArgumentHost(outline_record, execution_kind, packet['author_id'], observe),
            instructions=instruction_packet(packet['request'], packet['rules'], event='reverse-outline'))
        require(outline == packet['manuscript']['reverse_outline'], 'outline differs from original return')
        comparison_record = packet['manuscript']['argument_comparison']['record']
        comparison = argument.compare_outline(blueprint['argument_structure'], outline, sources,
            _RecordedArgumentHost(comparison_record, execution_kind, packet['author_id'], observe),
            instructions=instruction_packet(packet['request'], packet['rules'], event='argument-compare'))
        require(comparison['valid'] and comparison == packet['manuscript']['argument_comparison'],
                'reverse argument comparison differs or failed')
        final_original = validate_execution_record(packet['manuscript']['execution'], execution_kind=execution_kind, observe=observe)
        comparison_rows = final_original.get('outline_comparison')
        require(isinstance(comparison_rows, list) and [r.get('paragraph_id') for r in comparison_rows] == ids,
                'outline paragraph comparison coverage differs')
        for row in comparison_rows:
            require(_text(row.get('assessment')) and row.get('verdict') == 'pass' and
                    row.get('spec_sha256') == packet['paragraphs'][row['paragraph_id']]['spec_sha256'] and
                    row.get('outline_sha256') == content_hash(outline), 'outline paragraph comparison differs or failed')
        target = packet['target']
        if target == 'message://final':
            target_text = candidate_text
        else:
            require(target.startswith('artifact://'), 'paragraph target is invalid')
            target_text = (text_artifacts or {}).get(target[len('artifact://'):])
        if isinstance(target_text, bytes):
            target_text = target_text.decode('utf-8')
        require(isinstance(target_text, str) and target_text == manuscript, 'candidate target differs from integrated text')
    except (ParagraphError, ValueError, KeyError, TypeError, AttributeError, ImportError) as exc:
        issues.append(str(exc))
    return {'valid': not issues, 'issues': issues, 'paragraph_count': len(packet.get('paragraphs', {})) if isinstance(packet, dict) else 0,
            'bundle_sha256': content_hash(submitted_packet), 'release_authorized': False,
            'execution_assurance': 'host-observed' if observe is not None else 'stored-record-consistent',
            'required_final_roles': ['quality-a', 'quality-b', 'compliance'], 'required_final_prose_checks': list(PROSE_CHECK_IDS)}


def load_host_adapter(path):
    """Load an explicitly selected adapter implementing callback and observation."""
    path = Path(path).resolve()
    require(path.is_file(), 'host adapter file is absent')
    spec = importlib.util.spec_from_file_location('paragraph_host_adapter', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = getattr(module, 'create_host', None)
    host = factory() if callable(factory) else getattr(module, 'host', None)
    observer = getattr(host, 'observe', None) or getattr(module, 'observe', None)
    require(callable(host) and callable(observer), 'adapter must expose a callable host and observe(event_id)')
    return host, observer


def execute_operation(run, operation, host, observe, *, paragraph_id=None, section_id=None, max_workers=1, repair_limit=0):
    """Run an authorized stage through the supplied actual host adapter."""
    require(type(repair_limit) is int and repair_limit >= 0, 'repair limit must be nonnegative')
    if operation == 'argument-review':
        return run.review_argument(host, observe)
    if operation == 'write':
        return {'written_paragraph_ids': run.write(host, observe, max_workers=max_workers)}
    if operation == 'repair':
        require(paragraph_id in run.state['paragraphs'], 'repair requires a paragraph id')
        return run.repair(paragraph_id, host, observe)
    if operation == 'section-integrate':
        return run.integrate_section(section_id, host, observe)
    if operation == 'manuscript-integrate':
        return run.integrate_manuscript(host, observe)
    require(operation in ('review', 'full'), 'paragraph execution operation differs')
    if operation == 'full':
        run.write(host, observe, max_workers=max_workers)
    ids = [paragraph_id] if paragraph_id is not None else list(run.state['paragraphs'])
    require(set(ids) <= set(run.state['paragraphs']), 'review paragraph absent')
    reviews = {}
    for pid in ids:
        row = run.state['paragraphs'][pid]
        if row.get('review') and row['review']['result']['passed'] and row['review']['binding'] == run._binding(pid):
            review = copy.deepcopy(row['review'])
        else:
            review = run.review(pid, host, observe)
        for _ in range(repair_limit):
            if review['result']['passed']:
                break
            review = run.repair(pid, host, observe)
        reviews[pid] = review
    result = {'status': 'locally-reviewed' if all(row['result']['passed'] for row in reviews.values()) else 'failed',
              'reviews': reviews}
    if operation == 'review' or result['status'] == 'failed':
        return result
    for section in run.state['blueprint']['sections']:
        sid = section['section_id']
        if sid not in run.state['sections']:
            integration = run.integrate_section(sid, host, observe)
            if integration['status'] != 'integrated':
                return integration
    return run.state['manuscript'] or run.integrate_manuscript(host, observe)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check-packet')
    check.add_argument('--packet', type=Path, required=True)
    check.add_argument('--candidate', type=Path, required=True)
    tasks = sub.add_parser('tasks')
    tasks.add_argument('--state', type=Path, required=True)
    tasks.add_argument('--output', type=Path, required=True)
    resume = sub.add_parser('resume')
    resume.add_argument('--state', type=Path, required=True)
    create = sub.add_parser('create')
    create.add_argument('--input', type=Path, required=True, help='JSON keyword arguments for ParagraphRun.create')
    create.add_argument('--state', type=Path, required=True)
    design = sub.add_parser('design')
    for key in ('brief', 'sources', 'rules', 'host', 'output'):
        design.add_argument('--' + key, type=Path, required=True)
    design.add_argument('--author-id', required=True)
    design.add_argument('--execution-kind', choices=EXECUTION_KINDS, default='independent-subagent')
    execute = sub.add_parser('execute')
    execute.add_argument('--state', type=Path, required=True)
    execute.add_argument('--host', type=Path, required=True)
    execute.add_argument('--operation', choices=('argument-review', 'write', 'review', 'repair', 'section-integrate', 'manuscript-integrate', 'full'), required=True)
    execute.add_argument('--paragraph-id')
    execute.add_argument('--section-id')
    execute.add_argument('--max-workers', type=int, default=1)
    execute.add_argument('--repair-limit', type=int, default=0)
    execute.add_argument('--output', type=Path)
    update = sub.add_parser('update')
    update.add_argument('--state', type=Path, required=True)
    update.add_argument('--kind', choices=('sources', 'rules', 'specification', 'blueprint', 'dependencies'), required=True)
    update.add_argument('--input', type=Path, required=True)
    packet = sub.add_parser('packet')
    packet.add_argument('--state', type=Path, required=True)
    packet.add_argument('--target', default='message://final')
    packet.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'check-packet':
        result = validate_packet(json.loads(args.packet.read_text()), args.candidate.read_text())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['valid'] else 1
    if args.command == 'design':
        host, observe = load_host_adapter(args.host)
        brief, sources, rules = [json.loads(path.read_text(encoding='utf-8')) for path in (args.brief, args.sources, args.rules)]
        blueprint = generate_blueprint(brief, sources, rules, host, observe,
                                      execution_kind=args.execution_kind, author_id=args.author_id)
        specifications = generate_specifications(blueprint['blueprint'], sources, rules, host, observe,
                            request=brief['original_request'], authority=brief['authority'],
                            execution_kind=args.execution_kind, author_id=args.author_id)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical({'blueprint': blueprint['blueprint'], 'specifications': specifications['specifications'],
                                          'design_records': [blueprint['execution'], specifications['execution']]}))
        print(json.dumps({'status': 'specified', 'output': str(args.output)}))
        return 0
    if args.command == 'create':
        run = ParagraphRun.create(**json.loads(args.input.read_text(encoding='utf-8')))
        run.save(args.state)
        print(json.dumps({'run_id': run.state['run_id'], 'state': str(args.state)}))
        return 0
    run = ParagraphRun.load(args.state)
    if args.command == 'tasks':
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical(run.tasks()))
        print(json.dumps({'task_count': len(run.tasks()), 'output': str(args.output)}))
    elif args.command == 'resume':
        run.save(args.state)
        print(json.dumps({'run_id': run.state['run_id'], 'paragraphs': {k: v['status'] for k, v in run.state['paragraphs'].items()},
                          'instruction_context': instruction_packet(run.state['request'], run.state['rules'], event='task-resume')}, ensure_ascii=False))
    elif args.command == 'execute':
        host, observe = load_host_adapter(args.host)
        try:
            result = execute_operation(run, args.operation, host, observe, paragraph_id=args.paragraph_id,
                                       section_id=args.section_id, max_workers=args.max_workers, repair_limit=args.repair_limit)
        finally:
            run.save(args.state)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(canonical(result))
        status = result.get('status', 'completed')
        print(json.dumps({'operation': args.operation, 'status': status, 'state': str(args.state),
                          'release_authorized': False}, ensure_ascii=False))
        return 1 if status in ('failed', 'recheck-required') or result.get('valid') is False else 0
    elif args.command == 'update':
        value = json.loads(args.input.read_text(encoding='utf-8'))
        methods = {'sources': run.update_sources, 'rules': run.update_rules, 'specification': run.update_specification}
        if args.kind == 'blueprint':
            affected = run.update_blueprint(value['blueprint'], value['specifications'])
        elif args.kind == 'dependencies':
            affected = run.update_dependencies(value['paragraph_id'], value['depends_on'])
        else:
            affected = methods[args.kind](value)
        run.save(args.state)
        print(json.dumps({'affected_paragraph_ids': affected, 'state': str(args.state)}))
    elif args.command == 'packet':
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result = run.packet(target=args.target, compact=True)
        args.output.write_bytes(canonical(result))
        print(json.dumps({'packet': str(args.output), 'candidate_sha256': result['candidate_sha256'], 'release_authorized': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

