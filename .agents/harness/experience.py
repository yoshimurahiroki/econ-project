#!/usr/bin/env python3
"""Capture and propose reuse of a successful procedure in the existing task store."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

def _sibling(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native_check = _sibling('experience_native_check', 'native_check.py')
state = _sibling('experience_state', 'state.py')

OUTPUT = 'experience:procedure'
CONDITION_KEYS = ('model', 'engine', 'schema', 'method', 'failure_mechanism', 'package_versions', 'specification_sha256')
OPERATIONAL_KEYS = ('project', 'runtime', 'schema', 'failure_mechanism', 'package_versions', 'specification_sha256')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_store(root, store):
    name = state.relative(root, store)
    require(Path(name).parts[:2] == ('.agents', 'state'), 'Store must be under .agents/state')
    data = json.loads((root / name).read_text())
    state.migrate(data)
    return data


def call(root, store, *args):
    command = [sys.executable, str(Path(state.__file__).resolve()), '--root', str(root), '--store', store, *args]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout)


def output_data(root, task, output_id):
    row = task['outputs'][output_id]
    if row['kind'] == 'object':
        return row['value']
    if row['kind'] == 'file':
        return json.loads((root / state.relative(root, output_id)).read_text())
    raise ValueError('Typed condition evidence must be an object or JSON file output')


def select(value, path):
    require(isinstance(path, list) and all(isinstance(k, str) and k for k in path), 'Condition path must contain object keys')
    for key in path:
        require(isinstance(value, dict) and key in value, 'Condition path missing in producing evidence')
        value = value[key]
    return value


def validate_conditions(conditions):
    require(isinstance(conditions, dict) and set(conditions) in (set(CONDITION_KEYS), set(OPERATIONAL_KEYS)), 'All typed conditions are required')
    for key, value in conditions.items():
        if key == 'package_versions':
            require(isinstance(value, dict) and value and all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in value.items()), 'Package versions must map names to versions')
        else:
            require(isinstance(value, str) and value.strip(), 'Condition must contain text: ' + key)
    digest = conditions['specification_sha256']
    require(len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'Specification identity must be a SHA-256')


def referenced_output(root, producer, ids, ref, label):
    require(isinstance(ref, dict) and set(ref) == {'output_id', 'path'} and ref['output_id'] in producer['outputs'],
            label + ' must reference producing evidence')
    ids.add(ref['output_id'])
    return select(output_data(root, producer, ref['output_id']), ref['path'])


def checked_native(record):
    require(isinstance(record, dict), 'Native execution evidence must be an object')
    event = {key: record[key] for key in ('event_id', 'operation', 'target', 'status')}
    outcomes = []
    native_check._operation_results({'action_results_verified': [record]}, [event], outcomes)
    return outcomes[0]


def terminal_return(record):
    terminal = record.get('continuations', [])[-1] if record.get('continuations') else record
    returned = json.loads(terminal['return_text'])
    require(type(returned.get('exit_code')) is int and returned['exit_code'] == 0,
            'Native command requires an observed successful terminal exit')
    return returned


def native_execution(root, producer, ids, config, record):
    required = {'expected_workdir', 'failure_record', 'source_preservation', 'protected_paths', 'history_check',
                'restoration', 'package', 'readback', 'plugin', 'algorithm'}
    require(isinstance(config, dict) and set(config) == required,
            'Native execution requires workdir, historical source checks, package, readback, plugin and algorithm evidence')
    def ref(name):
        return referenced_output(root, producer, ids, config[name], 'Native ' + name)
    checked_native(record)
    require(record['tool_name'] == 'exec_command' and record['operation'] == 'execute_command',
            'Native generation requires an observed command execution')
    args = json.loads(record['call_args_text'])
    wanted = ref('expected_workdir')
    require(isinstance(wanted, str) and wanted and args.get('workdir') == wanted,
            'Native command workdir differs from requested stage')
    returned = terminal_return(record)
    failure, preservation, protected, history_check, restoration, package, readback, plugin, algorithm = (ref(k) for k in
        ('failure_record', 'source_preservation', 'protected_paths', 'history_check', 'restoration', 'package', 'readback', 'plugin', 'algorithm'))
    checked_native(failure)
    prior = terminal_return(failure)
    previous_args = json.loads(failure['call_args_text'])
    require(failure.get('tool_name') == 'exec_command' and failure.get('operation') == 'execute_command'
            and isinstance(previous_args.get('workdir'), str) and previous_args['workdir'] != wanted
            and args['cmd'].strip().splitlines()[-1] == previous_args['cmd'].strip().splitlines()[-1],
            'Failure evidence must show the same generation command in a different working directory')
    checked_native(history_check)
    history_return = terminal_return(history_check)
    require(json.loads(history_return['output']) == preservation, 'Historical Git evidence differs from its observed output')
    hashes = preservation.get('critical_source_sha256', {}) if isinstance(preservation, dict) else {}
    require(isinstance(preservation, dict) and preservation.get('direct_parent') is True and preservation.get('all_other_tracked_objects_equal') is True
            and preservation.get('tracked_paths_before') == preservation.get('tracked_paths_after')
            and type(preservation.get('tracked_paths_before')) is int and preservation['tracked_paths_before'] > 0
            and isinstance(preservation.get('changed_paths'), list) and isinstance(hashes, dict) and hashes
            and isinstance(protected, list) and protected and len(set(protected)) == len(protected)
            and all(isinstance(path, str) and path in hashes for path in protected)
            and not (set(hashes) & set(preservation['changed_paths']))
            and all(isinstance(v, str) and len(v) == 64 and all(c in '0123456789abcdef' for c in v) for v in hashes.values())
            and preservation.get('generation_rerun') is False and preservation.get('publication_rerun') is False,
            'Historical preservation requires matching protected Git objects')
    scope = restoration.get('observed_object_scope', {}) if isinstance(restoration, dict) else {}
    require(isinstance(restoration, dict) and native_check._source_matched(restoration.get('source_verification'))
            and restoration.get('captured_return_fields') == ['output']
            and restoration.get('return_projection', {}).get('field') == 'output'
            and 'clean' in restoration['return_projection'].get('value', '').lower()
            and scope.get('assertion_before_correct_generation') == 'git status --porcelain empty'
            and scope.get('historical_source_commit') == preservation.get('before_commit')
            and restoration.get('followed_by_native_record'),
            'Historical restoration requires its source-matched observed output')
    require(isinstance(package, dict) and isinstance(package.get('source_commit'), str) and package['source_commit']
            and isinstance(package.get('archive'), str) and package['archive']
            and isinstance(package.get('archive_sha256'), str) and len(package['archive_sha256']) == 64
            and all(c in '0123456789abcdef' for c in package['archive_sha256'])
            and type(package.get('file_count')) is int and package['file_count'] > 0,
            'Package evidence requires source commit, archive hash and count')
    require(package['source_commit'] == preservation.get('before_commit'), 'Package source differs from preserved historical commit')
    summary = readback.get('summary', {}) if isinstance(readback, dict) else {}
    require(summary.get('file_count') == package['file_count']
            and all(isinstance(summary.get(k), list) and not summary[k] for k in ('missing', 'extra', 'mismatches'))
            and type(summary.get('byte_identical')) is int and isinstance(summary.get('equivalent_json'), list)
            and summary['byte_identical'] + len(summary['equivalent_json']) == package['file_count']
            and isinstance(summary.get('release_id'), str) and summary['release_id'], 'Package readback does not match')
    plugin_outcome = checked_native(plugin)
    require(plugin_outcome.get('release_id') == summary['release_id'] and plugin_outcome.get('version') == summary.get('version')
            and json.loads(plugin['call_args_text']).get('archive') == package['archive'], 'Plugin release or archive does not match readback')
    require(isinstance(algorithm, list) and algorithm and all(isinstance(step, str) and step.strip()
            and wanted not in step and summary['version'] not in step for step in algorithm),
            'Owner-adopted reusable algorithm steps require evidence')
    return {'kind': 'native_operation', 'record': record, 'actual_workdir': wanted, 'terminal_exit_code': returned['exit_code'],
            'failure_record': failure, 'failure_workdir': previous_args['workdir'], 'failure_terminal_exit_code': prior['exit_code'],
            'source_preservation': preservation, 'protected_paths': protected,
            'source_commit': package['source_commit'], 'archive_sha256': package['archive_sha256'],
            'readback_summary': summary, 'plugin_outcome': plugin_outcome}, [{'instruction': step} for step in algorithm]


def task_check(root, tasks, producer, output_id, check, failure_id=None, failure_observation=None):
    """Recover a current verified producer and its optional earlier failure."""
    require(isinstance(check, str) and check in producer.get('required_checks', []), 'An adopted producer check is required')
    bindings = state.advanced_bindings(root, tasks, producer, check)
    require(bindings, 'Task check requires adopted command and code bindings')
    receipts = [row for row in producer.get('check_receipts', {}).values()
                if row.get('operation') == check and row.get('review_kind') == 'execution-result'
                and row.get('result') == 'passed' and (row.get('output_ids') is None or output_id in row['output_ids'])
                and state.receipt_current(root, producer, row)]
    require(receipts, 'Current verified execution receipt required')
    receipt = max(receipts, key=lambda row: row.get('sequence', 0))
    record = json.loads(bytes.fromhex(receipt['execution_result_hex']))
    run = state._execution_producer(root, tasks, producer, check, record, bindings)
    require(output_id in run['before']['versions']['outputs'], 'Check must bind the result output')
    result = {'kind': 'task_check', 'check_id': check, 'run': run, 'native_record': record}
    if failure_id is not None:
        runs = producer.get('check_runs', [])
        previous = [row for row in runs if row.get('run_id') == failure_id]
        require(len(previous) == 1 and runs.index(previous[0]) < runs.index(run), 'Failure must precede the successful run')
        failure = previous[0]
        unsigned = {k: v for k, v in failure.items() if k != 'producer_sha256'}
        require(failure.get('producer_sha256') == state.content_hash(unsigned)
                and failure.get('task_id') == producer['task_id'] and failure.get('check_id') == check
                and failure.get('store') == run['store'] and failure.get('command') == run['command']
                and isinstance(failure.get('before'), dict) and isinstance(failure.get('after'), dict)
                and type(failure.get('exit_code')) is int and failure.get('status') in ('passed', 'failed'),
                'Failure must retain its actual check producer and adopted command')
        require(isinstance(failure_observation, dict) and set(failure_observation) == {'run_id', 'reason', 'observed_output'}
                and failure_observation['run_id'] == failure_id
                and all(isinstance(failure_observation[k], str) and failure_observation[k].strip()
                        for k in ('reason', 'observed_output')), 'Failure requires a source-bound observation')
        observed = bytes.fromhex(failure['stdout_hex']).decode('utf-8', errors='replace') + bytes.fromhex(failure['stderr_hex']).decode('utf-8', errors='replace')
        require(failure_observation['observed_output'] in observed, 'Failure observation must appear in the actual run output')
        result.update(failure_run=failure, failure_observation=failure_observation)
    else:
        require(failure_observation is None, 'Failure observation requires a run ID')
    return result


def capture(root, store, task_id, parent, spec, metadata_input=None):
    data = read_store(root, store)
    tasks = data['tasks']
    require(parent in tasks, 'Existing parent task required')
    require(isinstance(spec, dict), 'Capture specification must be an object')
    metadata_path = metadata_sha = None
    if metadata_input is not None:
        if isinstance(metadata_input, dict):
            require(set(metadata_input) == {'path', 'sha256'}, 'Metadata binding needs a path and SHA-256')
            metadata_path = state.relative(root, metadata_input['path'])
            metadata_sha = metadata_input['sha256']
            require(isinstance(metadata_sha, str) and state.digest(root / metadata_path) == metadata_sha,
                    'Capture metadata bytes differ from the bound SHA-256')
            require(isinstance(json.loads((root / metadata_path).read_text()), dict), 'Capture metadata must be an object')
        else:
            metadata_path = state.relative(root, str(metadata_input))
            require(json.loads((root / metadata_path).read_text()) == spec, 'Capture metadata differs from the provided specification')
            metadata_sha = state.digest(root / metadata_path)
    producer_id = spec.get('producer_id')
    require(producer_id in tasks and state.completion_current(root, tasks, producer_id), 'Producing task must be completed and not stale')
    producer = tasks[producer_id]
    output_id, execution_id = spec.get('output_id'), spec.get('execution_output_id', 'research:execution')
    operational = spec.get('execution_kind', 'research') == 'task_check'
    require(output_id and output_id in producer['outputs'] and (operational or execution_id in producer['outputs']), 'Result and execution outputs required')
    conditions = spec.get('conditions')
    require(isinstance(conditions, dict) and set(conditions) == set(OPERATIONAL_KEYS if operational else CONDITION_KEYS), 'Typed condition evidence required')
    ids = {output_id} if operational else {output_id, execution_id}
    resolved = {}
    for key, ref in conditions.items():
        require(isinstance(ref, dict) and set(ref) == {'output_id', 'path'} and ref['output_id'] in producer['outputs'], 'Condition must reference producing evidence')
        ids.add(ref['output_id'])
        resolved[key] = select(output_data(root, producer, ref['output_id']), ref['path'])
    validate_conditions(resolved)
    tracked = set(producer.get('consumed_inputs', {}).values()) | set(producer.get('read_dependencies', {}).values())
    tracked.update(row['content_version'] for row in producer.get('consumes', []))
    require(resolved['specification_sha256'] in tracked, 'Specification hash must match a tracked producing input or consumed output')
    switch_refs = spec.get('permitted_switches', {})
    require(isinstance(switch_refs, dict), 'Permitted switch evidence must be an object')
    switches = {}
    for key, ref in switch_refs.items():
        require(isinstance(key, str) and key and isinstance(ref, dict) and set(ref) == {'output_id', 'path'} and ref['output_id'] in producer['outputs'], 'Switch must reference producing evidence')
        ids.add(ref['output_id'])
        value = select(output_data(root, producer, ref['output_id']), ref['path'])
        require(isinstance(value, str) and value.strip(), 'Switch evidence must contain text')
        switches[key] = value
    if operational:
        source_refs = list(conditions.values()) + [spec.get('steps')]
        if spec.get('failure_run_id') is not None:
            source_refs.append(spec.get('failure_observation'))
        require(all(isinstance(ref, dict) and ref.get('output_id') == output_id for ref in source_refs),
                'Operational facts and proposed steps must come from the checked result output')
        observation = referenced_output(root, producer, ids, spec['failure_observation'], 'Failure observation') if spec.get('failure_run_id') else None
        execution = task_check(root, tasks, producer, output_id, spec.get('check_id'), spec.get('failure_run_id'), observation)
        instructions = referenced_output(root, producer, ids, spec.get('steps'), 'Owner proposed steps')
        require(isinstance(instructions, list) and instructions and all(isinstance(step, str) and step.strip() for step in instructions), 'Owner proposed steps must contain text')
        steps = [{'instruction': step} for step in instructions]
        execution_id = None
    elif spec.get('execution_kind', 'research') == 'native_operation':
        execution = output_data(root, producer, execution_id)
        execution, steps = native_execution(root, producer, ids, spec.get('native_evidence'), execution)
    else:
        require(spec.get('execution_kind', 'research') == 'research', 'Unknown execution evidence kind')
        execution = output_data(root, producer, execution_id)
        require(isinstance(execution, dict) and type(execution.get('returncode')) is int and execution['returncode'] == 0 and isinstance(execution.get('argv'), list) and execution['argv'] and all(isinstance(x, str) and x for x in execution['argv']), 'Successful execution record with actual argv required')
        steps = [{'argv': execution['argv'], 'cwd': execution.get('cwd')}]
    for output in ids:
        require(state.output_current(root, tasks, producer_id, output), 'Producing output is stale: ' + output)
    refs = [{'producer_id': producer_id, 'output_id': key, **state.output_version(producer['outputs'][key])} for key in sorted(ids)]
    procedure = {'kind': 'successful_procedure', 'producer_id': producer_id, 'result_output_id': output_id,
                 'execution_output_id': execution_id, 'conditions': resolved, 'condition_evidence': conditions,
                 'consumes': refs, 'execution': execution, 'steps': steps,
                 'permitted_switches': switches, 'switch_evidence': switch_refs,
                 'capture_config_sha256': state.content_hash(spec), 'capture_metadata_input': metadata_path,
                 'capture_metadata_sha256': metadata_sha}
    args = ['add', task_id, '--owner', 'experience', '--parent', parent, '--operation-kind', 'answer',
            '--required-output', json.dumps({'role': 'procedure', 'kind': 'object', 'target': OUTPUT}),
            '--next', 'Record the current successful procedure']
    for module in (__file__, state.__file__, native_check.__file__, state.gate.__file__):
        try:
            relative = str(Path(module).resolve().relative_to(root))
        except ValueError:
            continue
        args += ['--read-dependency', relative]
    if metadata_path:
        args += ['--input', metadata_path]
    for ref in refs:
        args += ['--consumes', json.dumps(ref, ensure_ascii=False)]
    call(root, store, *args)
    if metadata_path:
        created = read_store(root, store)['tasks'][task_id]
        require(created['consumed_inputs'].get(metadata_path) == metadata_sha, 'Capture metadata changed while creating the task')
    call(root, store, 'start', task_id)
    call(root, store, 'output', task_id, OUTPUT, '--kind', 'object', '--value', json.dumps(procedure, ensure_ascii=False))
    call(root, store, 'transition', task_id, 'completed')
    return {'task_id': task_id, 'output_id': OUTPUT, 'procedure': procedure}


def find(root, store, conditions, allow_rebind=False):
    validate_conditions(conditions)
    data = read_store(root, store)
    found = state.find_tasks(data, OUTPUT, limit=max(1, len(data['tasks'])), status='completed')
    matches = []
    for row in found['tasks']:
        key = row['task_id']
        task = data['tasks'][key]
        output = task.get('outputs', {}).get(OUTPUT)
        if not output or not state.output_current(root, data['tasks'], key, OUTPUT):
            continue
        procedure = output.get('value', {})
        producer = data['tasks'].get(procedure.get('producer_id'), {})
        saved = procedure.get('conditions', {})
        if set(saved) != set(conditions):
            continue
        differences = {name for name in conditions if saved.get(name) != conditions[name]}
        permitted = set(procedure.get('permitted_switches', {}))
        eligible = not differences or (allow_rebind and differences == {'specification_sha256'}
                                       and 'condition:specification_sha256' in permitted
                                       and procedure.get('execution', {}).get('kind') == 'native_operation')
        if eligible and procedure.get('execution', {}).get('kind') == 'task_check':
            try:
                execution = procedure['execution']
                current = task_check(root, data['tasks'], producer, procedure['result_output_id'], execution['check_id'],
                                     execution.get('failure_run', {}).get('run_id'), execution.get('failure_observation'))
                eligible = current == execution and state.completion_current(root, data['tasks'], procedure['producer_id'])
            except (ValueError, KeyError, TypeError, OSError):
                eligible = False
        if producer.get('status') == 'completed' and procedure.get('kind') == 'successful_procedure' and eligible:
            matches.append({'task_id': key, 'output_id': OUTPUT, 'version': output['version'],
                            'changed_conditions': sorted(differences), 'procedure': procedure})
    return {'conditions': conditions, 'matches': matches}


def operational_candidates(root, store, conditions):
    """Describe current checked operational evidence without exposing its contents.

    Existing check receipts and native-operation captures do not bind an actual
    host session to their returns.  A task ID, run ID, or process session ID is
    not a substitute.  Accordingly these observations are candidates, never
    promoted facts, until that separate host evidence exists.
    """
    validate_conditions(conditions)
    matches = find(root, store, conditions)['matches']
    tasks = read_store(root, store)['tasks']
    candidates = []
    for match in matches:
        # Recheck against the same store snapshot used for usage evidence;
        # the procedure may have changed since find() read its snapshot.
        if (match['task_id'] not in tasks
                or tasks[match['task_id']].get('outputs', {}).get(OUTPUT, {}).get('version') != match['version']
                or not state.output_current(root, tasks, match['task_id'], OUTPUT)):
            continue
        execution = match['procedure'].get('execution', {})
        kind = execution.get('kind')
        if kind == 'task_check':
            previous = execution.get('failure_run')
            if not previous:
                continue
            # A failed check can also mean changed bindings while the process
            # itself exited successfully.  Text in stdout cannot establish a
            # separate semantic failure predicate.
            if type(previous.get('exit_code')) is not int or previous['exit_code'] == 0:
                classification = 'unverified_semantic_observation'
            else:
                classification = 'execution_failure'
        elif kind == 'native_operation':
            # native_execution validated the original target, preservation,
            # package and readback predicates when this procedure was captured.
            classification = 'semantic_defect'
        else:
            continue
        producer_id = match['procedure']['producer_id']
        if producer_id not in tasks or not state.completion_current(root, tasks, producer_id):
            continue
        producer = tasks[producer_id]
        recorded_events = 0
        # Usage rows are globally deduplicated and may be stored on another
        # associated task.  A declared import is not proof of a host event.
        for owner in tasks.values():
            for row in owner.get('usage', []):
                if (row.get('usage_contract') != 3 or producer_id not in row.get('tasks', [])
                        or row.get('source_verification') != 'imported-unverified'):
                    continue
                operation = row.get('operation')
                if not isinstance(operation, dict) or operation.get('context_sha256') != state.context_id(producer):
                    continue
                for ref in row.get('source_refs', []):
                    try:
                        path = Path(ref['path'])
                        if path.is_absolute():
                            path = path.relative_to(root)
                        path = state.relative(root, str(path))
                        if state.digest(root / path) == ref['sha256']:
                            recorded_events += 1
                            break
                    except (ValueError, OSError, TypeError, KeyError):
                        continue
        candidates.append({'procedure_id': match['task_id'], 'procedure_version': match['version'],
                           'classification': classification, 'host_session': None,
                           'session_provenance': 'unknown', 'unverified_current_events': recorded_events,
                           'promoted': False})
    return {'identity_sha256': state.content_hash(conditions), 'candidates': candidates,
            'confirmed_sessions': 0, 'known_opportunities': None, 'contributions': None,
            'telemetry_scope': 'current in-project source files only', 'presentation': [],
            'limitation': 'Host session to execution evidence is not established'}


_PYTEST_FACT = ('the bare pytest command was unavailable, and python -m pytest completed a run '
                'with at least one passing test.')
_UNITTEST_FACT = ('the bare unittest command was unavailable, and python -m unittest ran default test discovery.')


def _fact_text(family, conditions):
    versions = conditions['runtime']
    if family == 'pytest':
        versions += ' and pytest ' + conditions['package_versions']['pytest']
    return 'With ' + versions + ' and the recorded project inputs, ' + (_PYTEST_FACT if family == 'pytest' else _UNITTEST_FACT)


def _host_log_commands(root, path, expected_sha256):
    """Read one provided Codex log; do not retain its command/output contents."""
    source = state.gate.regular_bytes(path)
    require(hashlib.sha256(source).hexdigest() == expected_sha256, 'Host log bytes changed during assessment')
    headers, commands, calls, processes, message_hashes = [], [], {}, {}, set()
    turn = policy = None
    call_sequence = 0
    unrecognized_returns = unsupported_calls = 0
    for position, line in enumerate(source.decode('utf-8').splitlines()):
        if not line.strip():
            continue
        event = json.loads(line)
        require(isinstance(event, dict), 'Host log event must be an object')
        payload = event.get('payload')
        if not isinstance(payload, dict):
            continue
        if event.get('type') == 'session_meta':
            headers.append(payload)
        elif event.get('type') == 'turn_context':
            require(len(headers) == 1, 'Session header must precede turn context')
            turn = payload.get('turn_id')
            policy = (state.content_hash({'approval_policy': payload['approval_policy'],
                                         'sandbox_policy': payload['sandbox_policy']})
                      if isinstance(payload.get('approval_policy'), str) and payload['approval_policy'].strip()
                      and isinstance(payload.get('sandbox_policy'), dict)
                      and isinstance(payload['sandbox_policy'].get('type'), str)
                      and payload['sandbox_policy']['type'].strip() else None)
        elif event.get('type') == 'response_item' and payload.get('type') == 'function_call':
            require(len(headers) == 1, 'Session header must precede host calls')
            call_sequence += 1
            call_id = payload.get('call_id')
            require(isinstance(call_id, str) and call_id and call_id not in calls, 'Duplicate or missing host call ID')
            tool = payload.get('name')
            names = {'exec_command': 'exec_command', 'functions.exec_command': 'exec_command',
                     'write_stdin': 'write_stdin', 'functions.write_stdin': 'write_stdin'}
            tool = names.get(tool) if isinstance(tool, str) else None
            if tool is None:
                calls[call_id] = None
                continue
            arguments = payload.get('arguments')
            try:
                arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
            except json.JSONDecodeError:
                calls[call_id] = None
                unsupported_calls += 1
                continue
            if tool == 'write_stdin' and isinstance(arguments, dict):
                process = arguments.get('session_id')
                original = processes.get(process) if type(process) in (int, str) else None
                if (original is not None and set(arguments) <= {'session_id', 'chars', 'yield_time_ms', 'max_output_tokens'}
                        and arguments.get('chars', '') == '' and turn == original['turn'] and policy == original['policy']):
                    if call_sequence != original['last_sequence'] + 1:
                        original['interleaved'] = True
                    original['last_sequence'] = call_sequence
                    calls[call_id] = {'continuation': original, 'process': process, 'used': False}
                else:
                    calls[call_id] = None
                    unsupported_calls += 1
                continue
            if tool != 'exec_command':
                calls[call_id] = None
                continue
            if (not isinstance(arguments, dict) or not isinstance(arguments.get('cmd'), str)
                    or set(arguments) - {'cmd', 'workdir', 'yield_time_ms', 'max_output_tokens'}
                    or arguments.get('workdir') != str(root)):
                calls[call_id] = None
                unsupported_calls += 1
                continue
            calls[call_id] = {'command': arguments['cmd'], 'turn': turn, 'used': False,
                              'policy': policy, 'call_sequence': call_sequence, 'last_sequence': call_sequence,
                              'interleaved': False, 'call_position': position, 'chunks': []}
        elif event.get('type') == 'response_item' and payload.get('type') == 'function_call_output':
            call_id = payload.get('call_id')
            require(call_id in calls, 'Host return has no recorded call')
            call = calls[call_id]
            if call is None:
                continue
            require(not call['used'], 'Duplicate host return')
            call['used'] = True
            result = payload.get('output')
            try:
                result = json.loads(result) if isinstance(result, str) else result
            except json.JSONDecodeError:
                unrecognized_returns += 1
                continue
            if not isinstance(result, dict):
                unrecognized_returns += 1
                continue
            original = call.get('continuation', call)
            process = result.get('session_id')
            if 'continuation' in call and process is not None and process != call['process']:
                continue
            if type(result.get('exit_code')) is not int:
                if isinstance(result.get('output'), str):
                    original['chunks'].append(result['output'])
                if 'continuation' not in call and type(process) in (int, str) and process not in processes:
                    processes[process] = original
                elif 'continuation' not in call:
                    unrecognized_returns += 1
                continue  # A process/session launch is not a terminal result.
            if (original['interleaved'] or not isinstance(result.get('output'), str)
                    or 'continuation' not in call and process is not None):
                continue
            if 'continuation' in call:
                processes.pop(call['process'], None)
            output = ''.join(original['chunks']) + result['output']
            if len(output) > 1_000_000:
                continue
            timestamp = event.get('timestamp')
            try:
                parsed_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if isinstance(timestamp, str) else None
                timestamp = parsed_time.astimezone(timezone.utc).isoformat() if parsed_time and parsed_time.tzinfo else None
            except ValueError:
                timestamp = None
            commands.append({'command': original['command'], 'turn': original['turn'],
                             'policy': original['policy'], 'call_sequence': original['call_sequence'],
                             'completed_sequence': call_sequence, 'call_position': original['call_position'],
                             'return_position': position, 'exit': result['exit_code'], 'output': output,
                             'terminal_time': timestamp})
        elif (event.get('type') == 'response_item' and payload.get('type') == 'message'
              and payload.get('role') == 'developer' and isinstance(payload.get('content'), list)):
            for item in payload['content']:
                if isinstance(item, dict) and item.get('type') == 'input_text' and isinstance(item.get('text'), str):
                    # The hook appends the fact as a complete line after its
                    # mandatory reminder.  A substring is not a delivery.
                    for line in item['text'].split('\n'):
                        if line.endswith('\r'):
                            line = line[:-1]
                        message_hashes.add(hashlib.sha256(line.encode()).hexdigest())
    require(len(headers) == 1, 'One actual session header is required')
    header = headers[0]
    require(isinstance(header.get('id'), str) and header['id'] and header.get('cwd') == str(root)
            and isinstance(header.get('cli_version'), str) and header['cli_version'],
            'Host session requires its identity, project directory and CLI version')
    return (hashlib.sha256(header['id'].encode()).hexdigest(), header['cli_version'], commands, message_hashes,
            {'unrecognized_returns': unrecognized_returns, 'unsupported_calls': unsupported_calls,
             'unfinished_processes': len(processes)})


def assess_host_logs(root, store, target_id, conditions, log_paths, code_paths, current_log_path=None,
                     family='pytest', automatic=False, *, _tasks=None, _nonhistorical_inputs=(),
                     _current_session_sha256=None):
    """Assess one deliberately narrow repair from current, user-provided host logs.

    Source logs are evidence supplied by the user, not cryptographic host
    attestations. No commands from them are executed or copied into state.
    """
    tasks = _tasks if _tasks is not None else read_store(root, store)['tasks']
    require(target_id in tasks, 'Current target task required')
    target = tasks[target_id]
    settings = state.optimization_settings(target)
    if automatic and not (settings['enabled'] and settings['features']['experience']):
        return {'status': 'disabled', 'automatic_enabled': False, 'presentation': []}
    validate_conditions(conditions)
    require(set(conditions) == set(OPERATIONAL_KEYS), 'Operational conditions required')
    require(re.fullmatch(r'Python [0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*', conditions['runtime']) is not None,
            'Runtime must be an observed Python version')
    require(family in {'pytest', 'unittest'}, 'Unsupported deterministic test-runner family')
    if family == 'pytest':
        require(set(conditions['package_versions']) == {'pytest'}
                and re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?[A-Za-z0-9.+-]*', conditions['package_versions']['pytest']) is not None,
                'This adapter requires an observed pytest version')
    else:
        require(set(conditions['package_versions']) == {'python'}
                and conditions['runtime'] == 'Python ' + conditions['package_versions']['python'],
                'The unittest adapter requires the observed Python version')
    bare = family + ' -q'
    fixed_command = 'python -m ' + family + ' -q'
    fact = _fact_text(family, conditions)
    require(isinstance(log_paths, list) and log_paths and len(set(log_paths)) == len(log_paths), 'Distinct host logs required')
    require(isinstance(code_paths, list) and code_paths and len(set(code_paths)) == len(code_paths), 'Tracked code inputs required')
    require(current_log_path is None or current_log_path in log_paths, 'Current session log must be one of the tracked logs')
    constraints = state.effective_constraints(tasks, target, root)
    require(state.context_current(root, target) and not state.context_changes(root, target)
            and state.constraints_current(root, tasks, target) and not state.input_changes(root, target)
            and state.consumed_current(root, tasks, target)
            and not constraints['holds'] and not constraints['scope_errors'], 'Target context or authority is not current')
    tracked = {**target.get('read_dependencies', {}), **target.get('consumed_inputs', {})}
    for name in log_paths + code_paths:
        relative = state.relative(root, name)
        require(relative == name and name in tracked and state.digest(root / name) == tracked[name],
                'Each host log and code input must be tracked and current')
    # Include every tracked host log, so an explicit selection cannot hide a
    # known contradictory session in the same target's current inputs.
    discovered = set()
    for name in tracked:
        try:
            path = root / state.relative(root, name)
            with path.open(encoding='utf-8') as source:
                first = source.readline(65537)
            if len(first) <= 65536 and json.loads(first).get('type') == 'session_meta':
                discovered.add(name)
        except (ValueError, OSError, UnicodeError, AttributeError, TypeError):
            continue
    require(discovered <= set(log_paths), 'All current tracked host logs must be assessed')
    identities = []
    for name, digest in tracked.items():
        try:
            if state.digest(root / state.relative(root, name)) != digest:
                continue
            value = json.loads((root / name).read_text())
            if value == conditions or isinstance(value, dict) and value.get('identity') == conditions:
                identities.append(name)
        except (ValueError, OSError, UnicodeError, TypeError):
            continue
    require(identities, 'Exact operational identity must be a tracked current target input')
    specs = [name for name, digest in tracked.items() if digest == conditions['specification_sha256']
             and state.digest(root / state.relative(root, name)) == digest]
    require(specs, 'Current target specification input required')
    other_inputs = set(tracked) - set(log_paths) - set(identities) - set(specs) - set(_nonhistorical_inputs)
    require(other_inputs <= set(code_paths), 'Every other tracked input must have a version check')
    spec = sorted(specs)[0]
    paths = sorted(set([spec] + code_paths))
    require(all(re.fullmatch(r'[A-Za-z0-9_./-]+', name) for name in paths),
            'Input paths cannot be safely matched to a recorded checksum command')
    observed, cli_versions, policy_versions, current_messages = {}, set(), set(), set()
    unsupported_returns = unsupported_calls = unfinished_processes = 0
    confirmation_times = []
    untimed_confirmations = 0
    for log_path in log_paths:
        session, cli_version, commands, message_hashes, limitations = _host_log_commands(root, root / log_path, tracked[log_path])
        unsupported_returns += limitations['unrecognized_returns']
        unsupported_calls += limitations['unsupported_calls']
        unfinished_processes += limitations['unfinished_processes']
        if log_path == current_log_path:
            require(_current_session_sha256 is None or session == _current_session_sha256,
                    'Current host session differs from the provided log')
            current_messages = message_hashes
        require(session not in observed, 'Repeated logs cannot count as independent sessions')
        cli_versions.add(cli_version)
        def is_passed(row):
            if row['exit'] != 0:
                return False
            if family == 'pytest':
                return re.search(r'\b[1-9][0-9]* passed\b', row['output']) is not None
            return (re.search(r'\bRan [1-9][0-9]* tests?\b', row['output']) is not None
                    and re.search(r'(?m)^OK(?: \([^\n]*\))?\s*$', row['output']) is not None)
        def bound(rows, anchor, before, available=False):
            required = {'python --version': conditions['runtime']}
            if family == 'pytest':
                required['python -m pytest --version'] = 'pytest ' + conditions['package_versions']['pytest']
            for name in paths:
                required['sha256sum ' + name] = tracked[name] + '  ' + name
            required['command -v ' + family] = None
            count = len(required)
            block = rows[-count:] if before else rows[:count]
            if len(block) != count:
                return False
            def matches(row):
                if row['turn'] != anchor['turn'] or row['policy'] != anchor['policy'] or row['command'] not in required:
                    return False
                if required[row['command']] is None:
                    return ((row['exit'] == 0 and bool(row['output'].strip())) if available
                            else (row['exit'] == 1 and not row['output'].strip()))
                return row['exit'] == 0 and row['output'].strip() == required[row['command']]
            if not all(matches(row) for row in block):
                return False
            if {row['command'] for row in block} != set(required):
                return False
            sequence = block + [anchor] if before else [anchor] + block
            return all(later['call_sequence'] == earlier['completed_sequence'] + 1
                       and later['call_position'] > earlier['return_position']
                       for earlier, later in zip(sequence, sequence[1:]))
        opportunity, contribution, contradict = 0, 0, False
        for index, row in enumerate(commands):
            if row['command'] != bare:
                continue
            if not (row['turn'] and row['policy']):
                continue
            if (is_passed(row) and bound(commands[:index], row, True, available=True)
                    and bound(commands[index + 1:], row, False, available=True)):
                opportunity, contradict = opportunity + 1, True
                policy_versions.add(row['policy'])
            if (row['exit'] != 127 or not re.search(r'\b' + family + r': (?:command not found|コマンドが見つかりません)(?:\r?\n|$)', row['output'])
                    or index + 1 >= len(commands) or not bound(commands[:index], row, True)):
                continue
            fixed = commands[index + 1]
            if (fixed['command'] == fixed_command and fixed['turn'] == row['turn']
                    and fixed['policy'] == row['policy']
                    and fixed['call_sequence'] == row['completed_sequence'] + 1
                    and fixed['call_position'] > row['return_position']
                    and is_passed(fixed) and bound(commands[index + 2:], fixed, False)):
                opportunity += 1
                contribution += 1
                if fixed['terminal_time']:
                    confirmation_times.append(fixed['terminal_time'])
                else:
                    untimed_confirmations += 1
                policy_versions.add(row['policy'])
            elif bound(commands[index + 1:], row, False):
                opportunity += 1
                policy_versions.add(row['policy'])
        observed[session] = {'opportunity': opportunity, 'contribution': contribution, 'contradiction': contradict}
    require(not state.input_changes(root, target), 'Target input changed during assessment')
    require(len(cli_versions) == 1, 'Different host CLI versions require separate assessments')
    require(len(policy_versions) <= 1, 'Different host authority scopes require separate assessments')
    opportunities = sum(row['opportunity'] for row in observed.values())
    contributions = sum(row['contribution'] for row in observed.values())
    confirmed_sessions = sum(row['contribution'] > 0 for row in observed.values())
    contradictions = sum(row['contradiction'] for row in observed.values())
    incomplete = bool(unsupported_calls or unsupported_returns or unfinished_processes)
    eligible = (confirmed_sessions >= 3 and not contradictions and not incomplete
                and (opportunities < 4 or contributions / opportunities >= .4))
    version = state.content_hash({'identity': conditions, 'project_root': str(root),
                                  'authority': target.get('authority'), 'constraints': constraints,
                                  'code_versions': {name: tracked[name] for name in paths},
                                  'cli_version': next(iter(cli_versions)), 'host_policy': next(iter(policy_versions), None),
                                  'fact': family + '-module-v1', 'fact_sha256': hashlib.sha256(fact.encode()).hexdigest()})
    presented_fact = 'Verified operational fact (' + version + '): ' + fact
    delivery = hashlib.sha256(presented_fact.encode()).hexdigest()
    delivered = current_log_path is not None and delivery in current_messages
    if automatic:
        latest = (_tasks if _tasks is not None else read_store(root, store)['tasks']).get(target_id)
        require(latest is not None and state.context_id(latest) == state.context_id(target),
                'Target context changed during assessment')
        settings = state.optimization_settings(latest)
    enabled = settings['enabled'] and settings['features']['experience']
    selected = eligible and not delivered and (not automatic or enabled)
    return {'source_class': 'provided-host-log', 'host_authenticated': False, 'fact_version': version,
            'confirmed_sessions': confirmed_sessions, 'known_opportunities': opportunities,
            'contributions': contributions, 'contradictions': contradictions,
            'last_verified_at': max(confirmation_times) if confirmation_times and not untimed_confirmations else None,
            'unsupported_calls': unsupported_calls, 'unsupported_returns': unsupported_returns,
            'unfinished_processes': unfinished_processes,
            'status': 'invalidated' if contradictions else 'needs_reconciliation' if incomplete else 'eligible' if eligible else 'candidate',
            'automatic_enabled': enabled,
            'delivered_in_current_session': delivered if _current_session_sha256 is not None else None,
            'delivered_in_selected_log': delivered if current_log_path is not None else None,
            'presentation': [presented_fact] if selected else [],
            'evidence': [{'session_sha256': key, 'log_sha256': tracked[path]}
                         for (key, path) in zip(observed, log_paths)]}


def automatic_feedback(root, store, tasks, target_id, plan_ref, event):
    """Select applicable factual feedback for an actual pending host call."""
    try:
        target = tasks[target_id]
        settings = state.optimization_settings(target)
        if not (settings['enabled'] and settings['features']['experience']):
            return {'status': 'disabled', 'presentation': []}
        if (not isinstance(event, dict) or event.get('hook_event_name') != 'PreToolUse'
                or event.get('tool_name') not in ('exec_command', 'functions.exec_command')
                or not isinstance(event.get('tool_input'), dict)):
            return {'status': 'unrelated', 'presentation': []}
        pending = event['tool_input']
        if (set(pending) - {'cmd', 'workdir', 'yield_time_ms', 'max_output_tokens'}
                or pending.get('cmd') not in ('pytest -q', 'unittest -q')
                or pending.get('workdir') != str(root)):
            return {'status': 'unrelated', 'presentation': []}
        if plan_ref is None or plan_ref != settings.get('experience_plan'):
            return {'status': 'unavailable', 'reason': 'plan-not-configured', 'presentation': []}
        if (not isinstance(plan_ref, dict) or set(plan_ref) != {'path', 'sha256'}
                or not isinstance(plan_ref['path'], str) or Path(plan_ref['path']).parts[:2] != ('.agents', 'state')):
            return {'status': 'unavailable', 'reason': 'invalid-plan-reference', 'presentation': []}
        plan_path = state.relative(root, plan_ref['path'])
        plan_bytes = state.gate.regular_bytes(root / plan_path)
        if hashlib.sha256(plan_bytes).hexdigest() != plan_ref['sha256']:
            return {'status': 'stale-plan', 'reason': 'plan-content-changed', 'presentation': []}
        plan = state.gate.parse_json(plan_bytes)
        if (not isinstance(plan, dict) or not {'conditions', 'logs', 'code', 'family'} <= set(plan)
                or set(plan) - {'conditions', 'logs', 'code', 'family', 'current_log'}
                or plan['family'] not in ('pytest', 'unittest')
                or not isinstance(plan['conditions'], str) or not isinstance(plan['logs'], list)
                or any(not isinstance(path, str) or Path(path).parts[:2] != ('.agents', 'state') for path in plan['logs'])
                or not isinstance(plan['code'], list)):
            return {'status': 'unavailable', 'reason': 'invalid-plan', 'presentation': []}
        if pending['cmd'] != plan['family'] + ' -q':
            return {'status': 'unrelated', 'presentation': []}
        conditions_path = state.relative(root, plan['conditions'])
        tracked = {**target.get('read_dependencies', {}), **target.get('consumed_inputs', {})}
        if conditions_path not in tracked:
            return {'status': 'unavailable', 'reason': 'conditions-not-current', 'presentation': []}
        conditions_bytes = state.gate.regular_bytes(root / conditions_path)
        if hashlib.sha256(conditions_bytes).hexdigest() != tracked[conditions_path]:
            return {'status': 'unavailable', 'reason': 'conditions-not-current', 'presentation': []}
        conditions = state.gate.parse_json(conditions_bytes)
        if isinstance(conditions, dict) and isinstance(conditions.get('identity'), dict):
            conditions = conditions['identity']
        session = event.get('session_id')
        if plan.get('current_log') is not None and (not isinstance(session, str) or not session):
            return {'status': 'unavailable', 'reason': 'current-session-unknown', 'presentation': []}
        result = assess_host_logs(root, store, target_id, conditions, plan['logs'], plan['code'],
                                  plan.get('current_log'), plan['family'], True, _tasks=tasks,
                                  _nonhistorical_inputs=(plan_path,),
                                  _current_session_sha256=hashlib.sha256(session.encode()).hexdigest() if session else None)
        feedback = {key: result[key] for key in ('status', 'presentation', 'fact_version') if key in result}
        if result['status'] == 'needs_reconciliation':
            feedback['reason'] = 'unsupported-or-incomplete-source'
        return feedback
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        return {'status': 'unavailable', 'reason': 'assessment-rejected', 'error_type': type(exc).__name__,
                'presentation': []}


def record_host_assessment(root, store, target_id, conditions, log_paths, code_paths, current_log_path=None,
                           family='pytest', automatic=False):
    """Save an explicitly requested sanitized assessment through the shared writer."""
    result = assess_host_logs(root, store, target_id, conditions, log_paths, code_paths,
                              current_log_path, family, automatic)
    if 'fact_version' not in result:
        return {'task_id': target_id, 'output_id': None, 'assessment': result}
    output_id = 'experience:fact:' + result['fact_version']
    call(root, store, 'output', target_id, output_id, '--kind', 'object',
         '--value', json.dumps(result, ensure_ascii=False))
    return {'task_id': target_id, 'output_id': output_id, 'assessment': result}


def prepare(root, store, target_id, procedure_id, conditions, proposal_id=None, bindings_path=None):
    data = read_store(root, store)
    tasks = data['tasks']
    require(target_id in tasks, 'Target task is required')
    task = tasks[target_id]
    require(state.context_current(root, task) and not state.context_changes(root, task), 'Target context changed')
    constraints = state.effective_constraints(tasks, task, root)
    proposal_task = {'task_id': proposal_id or 'experience:pending', 'parent': target_id,
                     'operation_kind': 'answer', 'required_actions': [], 'required_outputs': [],
                     'scope': [], 'external_targets': [], 'holds': []}
    proposal_bounds = state.effective_constraints(tasks, proposal_task, root)
    require(not proposal_bounds['holds'] and not proposal_bounds['scope_errors'] and not constraints['scope_errors'],
            'Proposal has an applicable hold or target scope error')
    require(not task.get('parent') or task.get('effective_constraints_sha256') == state.content_hash(constraints),
            'Target constraints are not current')
    matches = find(root, store, conditions, allow_rebind=bindings_path is not None)['matches']
    match = next((m for m in matches if m['task_id'] == procedure_id), None)
    require(match is not None, 'No current procedure matches the typed conditions')
    bindings = {}
    binding_ref = None
    proposal_inputs = []
    proposal_consumes = []
    if set(conditions) == set(OPERATIONAL_KEYS):
        require(bindings_path is None, 'Operational conditions require an exact current target identity')
        def contains_identity(value):
            return value == conditions or (isinstance(value, dict) and value.get('identity') == conditions)
        current_files = []
        for path, digest in {**task.get('read_dependencies', {}), **task.get('consumed_inputs', {})}.items():
            try:
                if state.digest(root / path) == digest and contains_identity(json.loads((root / path).read_text())):
                    current_files.append(path)
            except (ValueError, OSError, UnicodeError):
                continue
        current_outputs = []
        for row in task.get('consumes', []):
            try:
                if state.consumed_ref_current(root, tasks, row) and contains_identity(output_data(root, tasks[row['producer_id']], row['output_id'])):
                    current_outputs.append(row)
            except (ValueError, KeyError, TypeError, OSError, UnicodeError):
                continue
        require(current_files or current_outputs, 'Operational conditions require a current target identity input or consumed output')
        tracked = {**task.get('read_dependencies', {}), **task.get('consumed_inputs', {})}
        spec_files = [path for path, digest in tracked.items() if digest == conditions['specification_sha256']
                      and state.digest(root / path) == digest]
        spec_outputs = [row for row in task.get('consumes', []) if row['content_version'] == conditions['specification_sha256']
                        and state.consumed_ref_current(root, tasks, row)]
        require(spec_files or spec_outputs, 'Operational specification must be a current target input or consumed output')
        if spec_files:
            proposal_inputs.append(sorted(spec_files)[0])
        else:
            proposal_consumes.append(spec_outputs[0])
        if current_files:
            proposal_inputs.append(sorted(current_files)[0])
        else:
            proposal_consumes.append(current_outputs[0])
    if bindings_path is not None:
        path = state.relative(root, bindings_path)
        tracked = {**task.get('read_dependencies', {}), **task.get('consumed_inputs', {})}
        require(path in tracked and state.digest(root / path) == tracked[path], 'Rebinding parameters must be a current target task input')
        proposal_inputs.append(path)
        bindings = json.loads((root / path).read_text())
        require(isinstance(bindings, dict) and isinstance(bindings.get('generation_authority'), str)
                and bindings['generation_authority'] and bindings['generation_authority'] == task.get('authority'),
                'Rebinding requires the target task generation authority')
        switches = match['procedure']['permitted_switches']
        values = {k: v for k, v in bindings.items() if k != 'generation_authority'}
        require(set(values) <= set(switches) and all(k in {'condition:specification_sha256', 'target:stage_path', 'target:release'} for k in values),
                'Rebinding is not declared by the producing evidence')
        require(all(isinstance(v, str) and v.strip() for v in values.values()), 'Rebinding values must contain text')
        for key in match['changed_conditions']:
            require(values.get('condition:' + key) == conditions[key], 'Changed condition requires a matching bound value')
        if match['changed_conditions']:
            wanted_spec = conditions['specification_sha256']
            current_files = [name for name, version in tracked.items() if version == wanted_spec and state.digest(root / name) == version]
            current_outputs = [row for row in task.get('consumes', []) if row['content_version'] == wanted_spec
                               and state.consumed_ref_current(root, tasks, row)]
            require(current_files or current_outputs, 'New specification must be a current target input or consumed output')
            if current_files:
                proposal_inputs.append(sorted(current_files)[0])
            else:
                proposal_consumes.append(current_outputs[0])
            require('target:stage_path' in values, 'Transferred native procedure requires a target stage path')
        if 'target:stage_path' in values:
            require(Path(values['target:stage_path']).is_absolute(), 'Stage path must be absolute')
        binding_ref = {'path': path, 'sha256': tracked[path]}
    procedure_output = tasks[procedure_id]['outputs'][OUTPUT]
    dependency = {'producer_id': procedure_id, 'output_id': OUTPUT, **state.output_version(procedure_output)}
    result = {'kind': 'adoption_proposal', 'target_task_id': target_id, 'target_context_id': state.context_id(task),
            'authority': task.get('authority', ''), 'scope': task.get('scope', []), 'constraints': constraints,
            'procedure_task_id': procedure_id, 'procedure_output_id': OUTPUT, 'procedure_version': match['version'],
            'procedure_dependency': dependency, 'producer_refs': match['procedure']['consumes'], 'conditions': conditions,
            'suggested_steps': match['procedure']['steps'], 'permitted_switches': match['procedure']['permitted_switches'],
            'binding_input': binding_ref, 'bindings': {k: v for k, v in bindings.items() if k != 'generation_authority'},
            'result_reuse': False,
            'required_execution_checks': (['Working directory equals the adopted stage path',
                                           'Canonical source remains unchanged'] if bindings else []),
            'adoption': 'Owner must use the existing context and specification path'}
    if proposal_id:
        name = 'experience:proposal'
        args = ['add', proposal_id, '--owner', 'experience', '--parent', target_id,
                '--operation-kind', 'answer', '--required-output', json.dumps({'role': 'proposal', 'kind': 'object', 'target': name}),
                '--consumes', json.dumps(dependency), '--next', 'Prepare the proposed procedure for owner adoption']
        for path in dict.fromkeys(proposal_inputs):
            args += ['--input', path]
        for consumed in proposal_consumes:
            args += ['--consumes', json.dumps(consumed)]
        call(root, store, *args)
        call(root, store, 'start', proposal_id)
        call(root, store, 'output', proposal_id, name, '--kind', 'object', '--value', json.dumps(result, ensure_ascii=False))
        call(root, store, 'transition', proposal_id, 'completed')
        result['proposal_task_id'] = proposal_id
        result['proposal_output_id'] = name
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--store', default='.agents/state/team.json')
    sub = parser.add_subparsers(dest='command', required=True)
    cap = sub.add_parser('capture')
    cap.add_argument('--task-id', required=True)
    cap.add_argument('--parent', required=True)
    cap.add_argument('--spec', type=Path, required=True)
    query = sub.add_parser('find')
    query.add_argument('--conditions', type=Path, required=True)
    query.add_argument('--allow-rebind', action='store_true')
    observed = sub.add_parser('operational-candidates')
    observed.add_argument('--conditions', type=Path, required=True)
    logs = sub.add_parser('assess-host-logs')
    logs.add_argument('--target', required=True)
    logs.add_argument('--conditions', type=Path, required=True)
    logs.add_argument('--log', action='append', required=True)
    logs.add_argument('--code', action='append', required=True)
    logs.add_argument('--current-log')
    logs.add_argument('--family', choices=('pytest', 'unittest'), default='pytest')
    logs.add_argument('--automatic', action='store_true', help='Apply the current operator experience switch')
    logs.add_argument('--record', action='store_true', help='Save a sanitized assessment on the running target task')
    proposal = sub.add_parser('prepare')
    proposal.add_argument('--conditions', type=Path, required=True)
    proposal.add_argument('--target', required=True)
    proposal.add_argument('--procedure', required=True)
    proposal.add_argument('--task-id', required=True)
    proposal.add_argument('--bindings', help='Target task tracked JSON input containing explicit new bindings')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == 'capture':
        try:
            metadata = str(args.spec.resolve().relative_to(root))
        except ValueError:
            metadata = None
        result = capture(root, args.store, args.task_id, args.parent, json.loads(args.spec.read_text()), metadata)
    elif args.command == 'find':
        result = find(root, args.store, json.loads(args.conditions.read_text()), args.allow_rebind)
    elif args.command == 'operational-candidates':
        result = operational_candidates(root, args.store, json.loads(args.conditions.read_text()))
    elif args.command == 'assess-host-logs':
        assess = record_host_assessment if args.record else assess_host_logs
        conditions = json.loads(args.conditions.read_text())
        if isinstance(conditions, dict) and isinstance(conditions.get('identity'), dict):
            conditions = conditions['identity']
        result = assess(root, args.store, args.target, conditions,
                        args.log, args.code, args.current_log, args.family, args.automatic)
    else:
        result = prepare(root, args.store, args.target, args.procedure, json.loads(args.conditions.read_text()), args.task_id, args.bindings)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        sys.exit(1)
