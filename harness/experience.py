#!/usr/bin/env python3
"""Capture and propose reuse of a successful procedure in the existing task store."""
import argparse
import importlib.util
import json
from pathlib import Path
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
    return state.main(['--root', str(root), '--store', store, *args])


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
    required = {'expected_workdir', 'algorithm'}
    retained = {'failure_record', 'source_preservation', 'protected_paths', 'history_check',
                'restoration', 'package', 'readback', 'plugin'}
    require(isinstance(config, dict) and required <= set(config)
            and set(config) <= required | retained,
            'Native execution requires expected_workdir and algorithm evidence')
    def ref(name):
        return referenced_output(root, producer, ids, config[name], 'Native ' + name)
    outcome = checked_native(record)
    require(record['tool_name'] == 'exec_command' and record['operation'] == 'execute_command',
            'Native procedure requires an observed command execution')
    args = json.loads(record['call_args_text'])
    wanted = ref('expected_workdir')
    require(isinstance(wanted, str) and Path(wanted).is_absolute() and args.get('workdir') == wanted,
            'Native command workdir differs from requested stage')
    returned = terminal_return(record)
    algorithm = ref('algorithm')
    require(isinstance(algorithm, list) and algorithm
            and all(isinstance(step, str) and step.strip() for step in algorithm),
            'Owner-adopted reusable algorithm steps require evidence')
    evidence = {name: ref(name) for name in config if name in retained}
    if 'failure_record' in evidence:
        failure = evidence['failure_record']
        checked_native(failure)
        prior = terminal_return(failure)
        previous_args = json.loads(failure['call_args_text'])
        require(failure.get('tool_name') == 'exec_command' and failure.get('operation') == 'execute_command'
                and isinstance(previous_args.get('workdir'), str) and previous_args['workdir'] != wanted
                and args['cmd'].strip().splitlines()[-1] == previous_args['cmd'].strip().splitlines()[-1],
                'Working-directory repair evidence must show the same command in a different directory')
        evidence['failure_workdir'] = previous_args['workdir']
        evidence['failure_terminal_exit_code'] = prior['exit_code']
    for name in ('history_check', 'plugin'):
        if name in evidence:
            checked_native(evidence[name])
    execution = {'kind': 'native_operation', 'record': record, 'outcome': outcome,
                 'actual_workdir': wanted, 'terminal_exit_code': returned['exit_code']}
    if evidence:
        execution['supporting_evidence'] = evidence
    return execution, [{'instruction': step} for step in algorithm]


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
    else:
        result = prepare(root, args.store, args.target, args.procedure, json.loads(args.conditions.read_text()), args.task_id, args.bindings)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        sys.exit(1)
