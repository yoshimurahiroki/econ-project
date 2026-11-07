#!/usr/bin/env python3
"""Match actual operation returns and requirements to their exact saved inputs."""


import importlib.util


import re


from pathlib import Path


def _sibling(name, *filenames):
    """Load only shipped siblings, including the flat Project export alias."""
    for filename in filenames:
        path = Path(__file__).resolve().with_name(filename)
        if path.is_file():
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise ImportError('Missing sibling dependency: ' + ', '.join(filenames))


gate = _sibling('native_local_checks', 'local_checks.py', 'LOCAL_CHECKS.py')


requirements = _sibling('native_requirements_check', 'requirements_check.py')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _source_matched(source):
    return (isinstance(source, dict) and set(source) == {'status', 'reference', 'verifier_id'}
            and source.get('status') == 'matched-to-runtime'
            and _text(source.get('reference')) and _text(source.get('verifier_id')))


_OPERATION_ADAPTERS = {
    ('mcp__codex_apps__github_update_ref', 'github.update_ref'): ('github-ref', ('repository_full_name', 'branch_name')),
    ('mcp__codex_apps__plugin_creator_update_plugin', 'plugin_creator.update_plugin'): ('plugin-update', ('plugin_id',)),
    ('send_email', 'send_email'): ('json', ('target', 'to')),
    ('publish', 'publish'): ('json', ('target', 'document_id')),
    ('execute_command', 'execute_command'): ('command', ('cmd',)),
    ('exec_command', 'execute_command'): ('command', ('cmd',)),
    ('write_stdin', 'execute_command'): ('command', ('session_id',)),
    ('mcp__codex_apps__library_create_library_file',
     'save_file'): ('library', ('file',)),
    ('mcp__codex_apps__library_replace_library_file',
     'save_file'): ('library-replace', ('file',)),
    ('mcp__codex_apps__library_finalize_uploads',
     'save_file'): ('library', ('uploads',)),
}


def _connector_payloads(value, depth=0):
    """Read both structured and textual MCP copies; accept no error branch."""
    gate.require(depth <= 8 and isinstance(value, dict), 'invalid connector result envelope')
    gate.require(value.get('isError', False) is False and not value.get('error') and not value.get('errors'),
                 'connector operation returned an error')
    if 'structuredContent' in value or 'content' in value:
        gate.require(set(value) <= {'structuredContent', 'content', 'isError', 'meta', '_meta'},
                     'unsupported connector envelope fields')
        payloads = []
        if 'structuredContent' in value:
            payloads.extend(_connector_payloads(value['structuredContent'], depth + 1))
        for block in value.get('content', []):
            gate.require(isinstance(block, dict) and block.get('type') == 'text'
                         and isinstance(block.get('text'), str), 'unsupported connector content')
            if block['text'] == 'Action completed.':
                continue
            payloads.extend(_connector_payloads(gate.parse_json(block['text'].encode('utf-8')), depth + 1))
        gate.require(payloads, 'connector result has no structured outcome')
        return payloads
    if set(value) == {'result'}:
        return _connector_payloads(value['result'], depth + 1)
    return [value]


def _connector_operation(value, args, operation, target, adapter):
    outcomes = []
    for result in _connector_payloads(value):
        if adapter == 'github-ref':
            gate.require(result == {'success': True}, 'GitHub ref update did not return success')
            outcomes.append({'status': 'success', 'operation': operation, 'target': target,
                             'commit_sha': args['sha']})
        else:
            allowed = {'current_release_id', 'description', 'discoverability', 'latest_release_id',
                       'name', 'plugin_id', 'plugin_url', 'release_id', 'scope', 'status', 'version', 'workspace_id'}
            gate.require(set(result) <= allowed and result.get('plugin_id') == args['plugin_id']
                         and result.get('status') == 'updated' and _text(result.get('release_id'))
                         and result['release_id'] == result.get('latest_release_id')
                         and result['release_id'] != args['expected_release_id']
                         and _text(result.get('plugin_url')) and _text(result.get('version')),
                         'plugin update outcome differs from its guarded target or release')
            outcomes.append({'status': 'success', 'operation': operation, 'target': target,
                             'release_id': result['release_id'], 'version': result['version']})
    gate.require(all(row == outcomes[0] for row in outcomes), 'connector result branches contradict each other')
    return outcomes[0]


def _operation_target(value, fields):
    supplied = [value[key] for key in fields if key in value]
    gate.require(supplied and all(_text(item) for item in supplied)
                 and all(item == supplied[0] for item in supplied),
                 'operation target is absent, unsupported or contradictory')
    return supplied[0]


def _operation_return(value, operation, target, adapter, depth=0):
    """Parse every registered result branch; reject uninterpreted containers."""
    gate.require(depth <= 8 and isinstance(value, dict),
                 'unsupported operation return: expected a JSON object')
    gate.require('isError' not in value or value['isError'] is False,
                 'operation return reports an error or invalid isError')
    gate.require(not value.get('error') and not value.get('errors'),
                 'operation return contains errors')
    if 'status' in value:
        gate.require(value['status'] in (('success', 'completed', 'running', 'pending')
                                        if adapter == 'command' else
                                        ('success', 'succeeded') if adapter in ('library', 'library-replace') else ('success',)),
                     'operation return is failed or has an unsupported status')
    session = None
    running = adapter == 'command' and value.get('status') in ('running', 'pending')
    for key in ('session_id', 'sessionId'):
        if value.get(key) is not None:
            gate.require(adapter == 'command' and
                         (type(value[key]) is int or _text(value[key])),
                         'unsupported operation session identifier')
            gate.require(session is None or session == value[key], 'contradictory operation sessions')
            session = value[key]
            running = True
    if 'operation' in value:
        expected_operation = ('replace_library_file' if adapter == 'library-replace' else
                              'create_library_file' if adapter == 'library' else operation)
        gate.require(value['operation'] == expected_operation, 'returned operation differs from call')
    for key in ('target', 'target_id'):
        if key in value:
            gate.require(value[key] == target, 'returned target differs from call')
    if 'cmd' in value:
        gate.require(adapter == 'command' and value['cmd'] == target, 'returned command differs from call')
    # Closed result vocabulary prevents an unparsed outcome/data/response branch
    # (including one containing an error) from being ignored beside success.
    allowed = {'status', 'operation', 'target', 'target_id', 'isError', 'error', 'errors',
               'result', 'structuredContent', 'content', 'metadata', 'message', 'id'}
    if adapter == 'command':
        allowed |= {'exit_code', 'output', 'cmd', 'session_id', 'sessionId',
                    'wall_time_seconds', 'chunk_id', 'original_token_count'}
    if adapter in ('library', 'library-replace'):
        allowed |= {'library_file_id', 'file_id', 'file_name', 'path', 'version',
                    'version_id', 'current_version_number', 'mime_type', 'size_bytes',
                    'file_size_bytes', 'xattrs', 'results', 'workspace_path',
                    'restored_from_version_number', 'directory_id', 'library_artifact_type',
                    'external_connectors_accessed'}
    gate.require(set(value) <= allowed, 'unsupported operation return fields')
    for key, item in value.items():
        if key not in ('result', 'structuredContent', 'content', 'metadata', 'errors', 'xattrs', 'results'):
            gate.require(not isinstance(item, (dict, list)), 'unsupported operation outcome container')
    returned_targets = [value[key] for key in ('target', 'target_id') if key in value]
    if 'metadata' in value:
        metadata = value['metadata']
        gate.require(isinstance(metadata, dict) and metadata
                     and set(metadata) <= {'operation', 'target', 'target_id', 'id'},
                     'unsupported operation return metadata')
        for key, item in metadata.items():
            gate.require(_text(item), 'unsupported operation return metadata value')
            if key == 'operation':
                gate.require(item == operation, 'metadata operation differs from call')
            if key in ('target', 'target_id'):
                gate.require(item == target, 'metadata target differs from call')
                returned_targets.append(item)
    identifiers = []
    file_ids = []
    versions = []
    if adapter in ('library', 'library-replace'):
        for key in ('current_version_number', 'file_size_bytes'):
            if key in value:
                gate.require(type(value[key]) is int and value[key] >= 0,
                             'invalid saved file version or size')
        if 'current_version_number' in value:
            versions.append(value['current_version_number'])
        if value.get('restored_from_version_number') is not None:
            gate.require(type(value['restored_from_version_number']) is int
                         and value['restored_from_version_number'] >= 0,
                         'invalid restored file version')
        if 'external_connectors_accessed' in value:
            gate.require(type(value['external_connectors_accessed']) is bool,
                         'invalid saved file connector indicator')
        if 'workspace_path' in value:
            gate.require(value['workspace_path'] == target, 'saved file source differs from call')
        if 'xattrs' in value:
            gate.require(isinstance(value['xattrs'], list) and all(
                isinstance(item, dict) and set(item) == {'name', 'value'}
                and _text(item['name']) and isinstance(item['value'], str)
                for item in value['xattrs']), 'unsupported saved file attributes')
        if 'file_id' in value:
            gate.require(_text(value['file_id']), 'invalid saved file identifier')
            file_ids.append(value['file_id'])
        if 'library_file_id' in value:
            gate.require(_text(value['library_file_id']), 'saved file lacks Library identifier')
            identifiers.append(value['library_file_id'])
    nested = [value[key] for key in ('result', 'structuredContent') if key in value]
    if 'results' in value:
        gate.require(adapter in ('library', 'library-replace') and isinstance(value['results'], list)
                     and len(value['results']) == 1, 'saved result must match one requested file')
        nested.extend(value['results'])
    if 'content' in value:
        content = value['content']
        gate.require(isinstance(content, list) and content, 'unsupported empty/non-array return content')
        for block in content:
            gate.require(isinstance(block, dict) and set(block) == {'type', 'text'}
                         and block.get('type') == 'text' and _text(block.get('text')),
                         'unsupported operation return content block')
            # The real Library transport supplies this fixed human-readable
            # acknowledgement beside its authoritative structured result.
            # Other text must still parse and agree; it cannot hide an error.
            if not (adapter in ('library', 'library-replace') and 'structuredContent' in value
                    and block['text'] == 'Action completed.'):
                nested.append(gate.parse_json(block['text'].encode('utf-8')))
    if 'exit_code' in value:
        gate.require(adapter == 'command' and ((running and value['exit_code'] is None)
                     or (type(value['exit_code']) is int and value['exit_code'] == 0)),
                     'command did not terminate successfully')
    if nested:
        for item in nested:
            outcome = _operation_return(item, operation, target, adapter, depth + 1)
            running = running or outcome['status'] == 'running'
            if outcome.get('session_id') is not None:
                gate.require(session is None or session == outcome['session_id'],
                             'nested operation session differs')
                session = outcome['session_id']
            if 'current_version_number' in outcome:
                versions.append(outcome['current_version_number'])
            if outcome.get('file_id'):
                file_ids.append(outcome['file_id'])
            if outcome.get('library_file_id'):
                identifiers.append(outcome['library_file_id'])
    elif adapter == 'command':
        gate.require(running or (type(value.get('exit_code')) is int and value['exit_code'] == 0),
                     'command completion requires terminal exit_code zero')
    elif adapter in ('library', 'library-replace'):
        gate.require(identifiers, 'saved result lacks created Library file identifier')
    else:
        gate.require(value.get('status') == 'success' and returned_targets,
                     'operation completion lacks explicit success and returned target metadata')
    result = {'operation': operation, 'target': target,
              'status': 'running' if running else 'success'}
    if session is not None:
        result['session_id'] = session
    if adapter in ('library', 'library-replace'):
        gate.require(identifiers and len(set(identifiers)) == 1,
                     'saved result contains contradictory Library file identifiers')
        result['library_file_id'] = identifiers[0]
        gate.require(len(set(file_ids)) <= 1, 'saved result contains contradictory file identifiers')
        if file_ids:
            result['file_id'] = file_ids[0]
        gate.require(len(set(versions)) <= 1, 'saved result contains contradictory versions')
        if versions:
            result['current_version_number'] = versions[0]
    return result


def _connector_call_target(tool_name, args):
    """Validate the existing guarded connector calls without fabricating a return."""
    gate.require(isinstance(args, dict), 'operation call arguments must be an object')
    if tool_name == 'mcp__codex_apps__github_update_ref':
        gate.require(set(args) <= {'repository_full_name', 'branch_name', 'sha', 'expected_sha', 'force'}
                     and all(_text(args.get(key)) for key in ('repository_full_name', 'branch_name', 'sha'))
                     and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args['repository_full_name'])
                     and re.fullmatch(r'[a-f0-9]{40}', args['sha'])
                     and _text(args.get('expected_sha'))
                     and re.fullmatch(r'[a-f0-9]{40}', args.get('expected_sha', ''))
                     and args.get('force', False) is False,
                     'GitHub ref update requires an exact target and expected head without force')
        gate.require(not args['branch_name'].startswith('refs/') and '..' not in args['branch_name']
                     and not any(c.isspace() for c in args['branch_name']), 'invalid GitHub branch name')
        return 'github.update_ref', args['repository_full_name'] + ':refs/heads/' + args['branch_name']
    gate.require(tool_name == 'mcp__codex_apps__plugin_creator_update_plugin', 'unknown connector call')
    gate.require(set(args) <= {'archive', 'delete_paths', 'expected_release_id', 'plugin_id'}
                 and all(_text(args.get(key)) for key in ('archive', 'expected_release_id', 'plugin_id'))
                 and args['archive'].startswith('/'), 'plugin update requires its exact guarded archive call')
    deletes = args.get('delete_paths')
    gate.require(deletes is None or (isinstance(deletes, list) and all(_text(value) for value in deletes)),
                 'plugin delete paths must be an array of exact paths')
    for value in deletes or []:
        gate.require(gate.safe_relative(value) == value and not any(char in value for char in '*?[]'),
                     'plugin delete path must be an exact plugin-relative file')
    return 'plugin_creator.update_plugin', args['plugin_id']


def stdin_target(args):
    """Identify an exact nonempty interactive input for its process session."""
    gate.require(isinstance(args, dict) and type(args.get('session_id')) is int
                 and isinstance(args.get('chars'), str) and bool(args['chars']),
                 'interactive input needs an integer session and nonempty text')
    return 'stdin://' + str(args['session_id']) + '/' + gate.sha(args['chars'].encode('utf-8'))


def _operation_results(report, events, outcomes=None, *, authorized_inputs=()):
    """Bind registered operation return schemas to exact supplied call bytes."""
    gate.require(isinstance(authorized_inputs, (list, tuple, set, frozenset))
                 and all(isinstance(value, str) for value in authorized_inputs),
                 'interactive input authority must contain exact target identities')
    records = report.get('action_results_verified', [])
    gate.require(isinstance(records, list), 'action_results_verified must be an array')
    expected = {event['event_id']: event for event in events}
    seen = set()
    for record in records:
        gate.require(isinstance(record, dict), 'action result must be an object')
        event_id = record.get('event_id')
        gate.require(isinstance(event_id, str) and event_id in expected and event_id not in seen,
                     'unknown or duplicate verified action result')
        event = expected[event_id]
        gate.require(all(record.get(field) == event[field] for field in ('operation', 'target', 'status'))
                     and record.get('status') == 'success', 'verified action differs from final event')
        gate.require(all(_text(record.get(field)) for field in
                         ('tool_call_ref', 'tool_return_ref', 'tool_name', 'call_args_text', 'return_text')),
                     'action result lacks actual tool name, call arguments, references or return text')
        gate.require(record['tool_call_ref'] != record['tool_return_ref'],
                     'tool call and return references must be distinct')
        gate.require(record.get('return_sha256') == gate.sha(record['return_text'].encode('utf-8')),
                     'action returned text digest mismatch')
        gate.require(record.get('call_args_sha256') == gate.sha(record['call_args_text'].encode('utf-8')),
                     'action call arguments digest mismatch')
        gate.require(_source_matched(record.get('source_verification')),
                     'action source not recorded as matched to actual tool result')
        key = (record['tool_name'], event['operation'])
        gate.require(key in _OPERATION_ADAPTERS, 'unregistered tool/operation return adapter')
        adapter, fields = _OPERATION_ADAPTERS[key]
        args = gate.parse_json(record['call_args_text'].encode('utf-8'))
        gate.require(isinstance(args, dict), 'operation call arguments must be an object')
        if 'operation' in args:
            gate.require(args['operation'] == event['operation'], 'call operation differs from final event')
        gate.require(record['tool_name'] != 'write_stdin',
                     'command continuation requires its initiating exec_command')
        if adapter in ('github-ref', 'plugin-update'):
            operation, target = _connector_call_target(record['tool_name'], args)
            gate.require(operation == event['operation'], 'call operation differs from final event')
        elif adapter in ('library', 'library-replace'):
            if fields == ('file',):
                allowed_args = ({'file', 'library_file_id', 'expected_current_version', 'directory_id', 'version_reason'}
                                if adapter == 'library-replace' else
                                {'file', 'files', 'directory_id', 'library_artifact_type'})
                gate.require(set(args) <= allowed_args, 'unsupported Library save call fields')
                if adapter == 'library-replace':
                    gate.require(_text(args.get('library_file_id')), 'replacement lacks Library target ID')
                    if args.get('expected_current_version') is not None:
                        gate.require(type(args['expected_current_version']) is int
                                     and args['expected_current_version'] >= 0,
                                     'invalid expected replacement version')
                gate.require(('file' in args) != ('files' in args),
                             'save call requires exactly one file input')
                files = [args['file']] if 'file' in args else args['files']
                gate.require(isinstance(files, list) and len(files) == 1
                             and _text(files[0]) and files[0].startswith('/'),
                             'save action must identify one absolute local file')
                target = files[0]
            else:
                gate.require(set(args) == {'uploads'}, 'unsupported Library finalize call fields')
                uploads = args.get('uploads')
                gate.require(isinstance(uploads, list) and len(uploads) == 1
                             and isinstance(uploads[0], dict),
                             'save action must identify one finalized upload')
                upload = uploads[0]
                gate.require(set(upload) <= {'directory_id', 'expected_current_version', 'file_id',
                             'file_name', 'file_size_bytes', 'library_artifact_type', 'library_file_id',
                             'method', 'mime_type', 'pdf_c2pa_upload', 'purpose', 'required_headers',
                             'shared_library_upload', 'store_in_library', 'upload_session_id',
                             'upload_url', 'version_reason', 'workspace_path'},
                             'unsupported finalized upload fields')
                gate.require(upload.get('purpose') == 'create_library_file'
                             and upload.get('store_in_library') is True
                             and all(_text(upload.get(key)) for key in
                                     ('upload_session_id', 'file_id', 'file_name'))
                             and bool(upload.get('workspace_path')) != bool(upload.get('upload_url')),
                             'invalid finalized upload source or purpose')
                target = upload.get('workspace_path') or upload['file_name']
        else:
            target = _operation_target(args, fields)
        gate.require(target == event['target'], 'call target differs from final event')
        returned_value = gate.parse_json(record['return_text'].encode('utf-8'))
        outcome = (_connector_operation(returned_value, args, event['operation'], target, adapter)
                   if adapter in ('github-ref', 'plugin-update') else
                   _operation_return(returned_value, event['operation'], target, adapter))
        if adapter in ('library', 'library-replace') and fields == ('uploads',):
            gate.require(outcome.get('file_id') == upload['file_id'],
                         'finalized file identifier differs from prepared upload')
        if adapter == 'library-replace':
            gate.require(outcome.get('library_file_id') == args['library_file_id'],
                         'replacement returned a different Library target ID')
            if args.get('expected_current_version') is not None:
                gate.require(outcome.get('current_version_number') == args['expected_current_version'] + 1,
                             'replacement did not return the next expected version')
        continuations = record.get('continuations', [])
        gate.require(isinstance(continuations, list), 'operation continuations must be an array')
        references = {record['tool_call_ref'], record['tool_return_ref']}
        for step in continuations:
            gate.require(adapter == 'command' and record['tool_name'] == 'exec_command'
                         and outcome['status'] == 'running'
                         and type(outcome.get('session_id')) is int,
                         'continuation lacks an active command session')
            gate.require(isinstance(step, dict) and step.get('tool_name') == 'write_stdin'
                         and all(step.get(key) == event[key] for key in ('event_id', 'operation', 'target')),
                         'continuation belongs to a different operation or target')
            gate.require(all(_text(step.get(key)) for key in
                         ('tool_call_ref', 'tool_return_ref', 'call_args_text', 'return_text')),
                         'continuation lacks tool references or exact bytes')
            gate.require(step['tool_call_ref'] != step['tool_return_ref']
                         and not references.intersection((step['tool_call_ref'], step['tool_return_ref'])),
                         'continuation reuses call/return references')
            references.update((step['tool_call_ref'], step['tool_return_ref']))
            gate.require(_source_matched(step.get('source_verification')),
                         'continuation is not matched to actual tool result')
            gate.require(all(step.get(key + '_sha256') == gate.sha(step[key + '_text'].encode('utf-8'))
                             for key in ('call_args', 'return')), 'continuation bytes digest mismatch')
            follow_args = gate.parse_json(step['call_args_text'].encode('utf-8'))
            gate.require(isinstance(follow_args, dict)
                         and set(follow_args) <= {'session_id', 'chars', 'max_output_tokens', 'yield_time_ms'}
                         and type(follow_args.get('session_id')) is int
                         and follow_args['session_id'] == outcome['session_id']
                         and isinstance(follow_args.get('chars', ''), str),
                         'continuation session or input differs from the running command')
            if follow_args.get('chars', ''):
                gate.require(stdin_target(follow_args) in authorized_inputs,
                             'interactive input lacks exact current task authority')
            session = outcome['session_id']
            outcome = _operation_return(gate.parse_json(step['return_text'].encode('utf-8')),
                                        event['operation'], target, adapter)
            gate.require(outcome.get('session_id', session) == session,
                         'continuation return belongs to a different session')
        if outcomes is not None:
            outcomes.append({'event_id': event_id, 'tool_name': record['tool_name'],
                             **{key: value for key, value in outcome.items() if key != 'session_id'}})
        gate.require(outcome['status'] == 'success',
                     'operation remains running; claimed completion is unmet')
        seen.add(event_id)
    gate.require(seen == set(expected), 'required actions lack source-matched returned tool results')
    return seen


def reconcile_requirements(contract, request_bytes, artifacts, events, *, tasks=None,
                           context=None, code_files=None, candidate_bytes=None,
                           contract_sha256=None, action_results=None):
    """Reconcile explicit requirements with current bytes and native operation returns."""
    analysis = requirements.analyze_requirements(contract, request_bytes, tasks=tasks,
                                                  context=context, code_files=code_files)
    fulfillment = requirements.validate_requirements(
        contract, request_bytes, artifacts, events,
        contract_sha256=contract_sha256, candidate_bytes=candidate_bytes)
    findings = list(analysis['findings']) + list(fulfillment['unmet'])
    outcomes = []
    if any(row['code'] == 'invalid_input' for row in fulfillment['unmet']):
        return {'status': 'fail', 'findings': findings, 'analysis': analysis,
                'fulfillment': fulfillment, 'operation_outcomes': outcomes}
    try:
        if not isinstance(events, list) or not isinstance(action_results if action_results is not None else [], list):
            raise ValueError('events and action_results must be arrays')
        records = action_results if action_results is not None else []
        known_event_ids = {e.get('event_id') for e in events if isinstance(e, dict)}
        if any(not isinstance(r, dict) or r.get('event_id') not in known_event_ids for r in records):
            raise ValueError('action result references an unknown event')
        for req in contract['requirements']:
            if req['kind'] != 'action':
                continue
            matched = [e for e in events if isinstance(e, dict) and e.get('requirement_id') == req['id']]
            if len(matched) != 1:
                findings.append({'code': 'native_action_unverified', 'requirement_id': req['id'],
                                 'message': 'required action needs exactly one matching event and verified native return'})
                continue
            event = matched[0]
            matching_records = [r for r in records if r.get('event_id') == event.get('event_id')]
            try:
                authorized = ()
                if analysis['status'] == 'pass' and isinstance(tasks, dict):
                    mappings = [row for row in analysis['mappings'] if row['requirement_id'] == req['id']]
                    if len(mappings) == 1:
                        action = {'target_kind': 'object', 'target_id': req['target'], 'operation': req['operation']}
                        owners = [tasks[tid] for tid in mappings[0]['task_ids']
                                  if tid in tasks and action in tasks[tid].get('required_actions', [])]
                        if len(owners) == 1 and isinstance(owners[0].get('external_targets'), list):
                            authorized = owners[0]['external_targets']
                _operation_results({'action_results_verified': matching_records}, [event], outcomes=outcomes,
                                   authorized_inputs=authorized)
            except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
                findings.append({'code': 'native_action_unverified', 'requirement_id': req['id'],
                                 'event_id': event.get('event_id'), 'message': str(exc)})
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        findings.append({'code': 'invalid_input', 'requirement_id': None, 'message': str(exc)})
    return {'status': 'fail' if findings else 'pass', 'findings': findings,
            'analysis': analysis, 'fulfillment': fulfillment, 'operation_outcomes': outcomes}


WEB_READ_TOOLS = {'web__run', 'mcp__codex_apps__search_service_web_run'}


LIBRARY_READ_TOOLS = {'mcp__codex_apps__library_read'}


CONNECTOR_READ_TOOLS = {
    'mcp__codex_apps__github_get_repo', 'mcp__codex_apps__github_fetch_file',
    'mcp__codex_apps__github_search', 'mcp__codex_apps__plugin_creator_get_plugin_files',
    'mcp__codex_apps__plugin_creator_get_plugin_metadata', 'mcp__codex_apps__app_equity_sources',
    'mcp__codex_apps__google_drive_get_document',
}
