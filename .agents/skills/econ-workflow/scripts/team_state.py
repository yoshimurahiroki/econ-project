#!/usr/bin/env python3
"""Local task state and evidence checks; no agent, API or credential access."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

STATES = {'queued', 'running', 'evaluating', 'completed', 'interrupted', 'failed'}
TOKEN_FIELDS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens')

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()

def relative(root, value, exists=True):
    path = Path(value)
    if path.is_absolute() or not value or '..' in path.parts:
        raise ValueError('Use a repository-relative path without parent traversal')
    target = root / path
    for parent in [target, *target.parents]:
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise ValueError('Symlink paths are not accepted for operational references')
    target.resolve().relative_to(root)
    if exists and not target.is_file():
        raise ValueError(f'Missing evidence file: {path.as_posix()}')
    return path.as_posix()

def snapshot(root, paths):
    return {relative(root, p): digest(root / p) for p in paths}

def changed(root, hashes):
    changes = []
    for path, expected in hashes.items():
        try:
            relative(root, path)
            if digest(root / path) != expected:
                changes.append(path)
        except (ValueError, OSError):
            changes.append(path)
    return changes

def revision(root):
    return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()

@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix('.lock')
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError('State is locked; inspect the active writer before removing a stale lock') from exc
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()

def save(path, state):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write('\n')
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)

def transition(task, status, next_action=None):
    task['history'].append({'status': task['status'], 'at': task['updated'],
                            'inputs': task['inputs'], 'outputs': task['outputs'],
                            'verification': task['verification'], 'next': task['next'],
                            'record_version': task.get('record_version'),
                            'input_contract': task.get('input_contract', 1)})
    task['status'], task['updated'] = status, now()
    if next_action is not None:
        task['next'] = next_action

def dependent_ids(tasks, stale):
    result = set(stale)
    while True:
        extra = {key for key, task in tasks.items() if set(task['after']) & result}
        if extra <= result:
            return result
        result |= extra

def completion_current(root, tasks, key):
    task = tasks[key]
    proof = task['verification']
    return (task['status'] == 'completed' and bool(task['outputs']) and proof is not None
            and proof['result'] == 'passed' and not changed(root, task['inputs'])
            and not changed(root, task['outputs']) and not changed(root, proof['evidence'])
            and all(completion_current(root, tasks, parent) for parent in task['after']))

def inspect(root, state, stale_seconds):
    findings, stale = [], set()
    for key, task in state['tasks'].items():
        paths = changed(root, task['inputs']) + changed(root, task['outputs'])
        verification = task['verification']
        if verification:
            paths += changed(root, verification['evidence'])
        if paths:
            stale.add(key)
            findings.append({'task': key, 'kind': 'changed-or-missing-evidence', 'paths': sorted(set(paths))})
        if task['status'] == 'completed' and (not task['outputs'] or not verification or verification['result'] != 'passed'):
            findings.append({'task': key, 'kind': 'completion-without-evidence'})
        if task['status'] == 'running':
            seconds = (datetime.now(timezone.utc) - datetime.fromisoformat(task['updated'])).total_seconds()
            if seconds >= stale_seconds:
                findings.append({'task': key, 'kind': 'progress-review-due', 'seconds': int(seconds)})
        if task['attempts'] >= state['limits']['max_attempts'] and task['status'] != 'completed':
            findings.append({'task': key, 'kind': 'attempt-limit'})
    for key in sorted(dependent_ids(state['tasks'], stale) - stale):
        findings.append({'task': key, 'kind': 'upstream-evidence-changed'})
    return findings, dependent_ids(state['tasks'], stale)

def report_usage(state):
    groups, problems, intervals = {}, [], []
    runs = [(key, run) for key, task in state['tasks'].items() for run in task['usage']]
    for task_id, run in runs:
        if run.get('usage_contract') != 2:
            problems.append({'hash': run['hash'], 'kind': 'legacy-counter-semantics-unclassified'})
            continue
        observations = run['observations']
        if not observations:
            problems.append({'hash': run['hash'], 'kind': 'completed-counter-unavailable'})
        for observation in observations:
            sid, epoch, sequence = observation['session_id'], run['epoch'], run['sequence']
            if not sid or epoch is None or sequence is None:
                problems.append({'hash': run['hash'], 'kind': 'unknown-session-epoch-or-order'})
                continue
            groups.setdefault((sid, epoch), []).append((sequence, observation['index'], observation['counter'], task_id, run['hash']))
    epoch_totals = []
    for (sid, epoch), observations in groups.items():
        positions = {}
        invalid = False
        for sequence, index, counter, task_id, fingerprint in observations:
            previous = positions.get((sequence, index))
            if previous and previous[0] != counter:
                problems.append({'session_id': sid, 'epoch': epoch, 'kind': 'conflicting-observation-position'})
                invalid = True
            else:
                positions[(sequence, index)] = (counter, task_id, fingerprint)
        ordered = sorted(positions.items())
        if not ordered or ordered[0][0] != (0, 0):
            problems.append({'session_id': sid, 'epoch': epoch, 'kind': 'initial-counter-baseline-unknown'})
            invalid = True
        prior = {field: 0 for field in TOKEN_FIELDS} if not invalid else {field: None for field in TOKEN_FIELDS}
        confirmed = prior
        for (sequence, index), (counter, task_id, fingerprint) in ordered:
            zero_or_default = all(counter.get(field) in (None, 0) for field in TOKEN_FIELDS)
            if not zero_or_default and any(counter.get(field) is not None and confirmed.get(field) is not None and counter[field] < confirmed[field] for field in TOKEN_FIELDS):
                problems.append({'session_id': sid, 'epoch': epoch, 'sequence': sequence, 'kind': 'counter-decreased-within-declared-epoch'})
                invalid = True
            delta = {field: counter[field] - prior[field] if not zero_or_default and counter.get(field) is not None and prior.get(field) is not None and counter[field] >= prior[field] else None for field in TOKEN_FIELDS}
            intervals.append({'session_id': sid, 'epoch': epoch, 'sequence': sequence, 'index': index,
                              'task': task_id, 'hash': fingerprint, 'counter_information': 'unknown-zero-or-default' if zero_or_default else 'reported-nonzero',
                              'increment_since_previous_observation': delta})
            prior = {field: None for field in TOKEN_FIELDS} if zero_or_default else counter
            if not zero_or_default:
                confirmed = counter
        if ordered and all(ordered[-1][1][0].get(field) in (None, 0) for field in TOKEN_FIELDS):
            problems.append({'session_id': sid, 'epoch': epoch, 'kind': 'final-zero-or-default-counter-unverified'})
        epoch_totals.append({field: None if invalid else prior.get(field) for field in TOKEN_FIELDS})
    totals = {field: (sum(row[field] for row in epoch_totals) if epoch_totals and not problems and all(row[field] is not None for row in epoch_totals) else None) for field in TOKEN_FIELDS}
    totals['elapsed_seconds'] = sum(run['elapsed_seconds'] for _, run in runs) if runs and all(run.get('elapsed_seconds') is not None for _, run in runs) else None
    totals['total_tokens'] = totals['input_tokens'] + totals['output_tokens'] if totals['input_tokens'] is not None and totals['output_tokens'] is not None else None
    return {'runs': len(runs), 'counter_epochs': len(groups), 'totals': totals, 'problems': problems,
            'intervals': intervals, 'attempts': sum(t['attempts'] for t in state['tasks'].values()),
            'human_corrections': sum(t['human_corrections'] for t in state['tasks'].values()),
            'meaning': 'CLI counters are cumulative within a declared session epoch. Sequence zero declares the captured epoch start. Import order does not set chronology. Cached input and reasoning output are included breakdowns; unknown is null. Interval increments cover the gap since the preceding recorded observation.'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument('--store', default='.agents/state/team.json')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    for name, default in [('max-active', 3), ('max-depth', 2), ('max-attempts', 3)]:
        init.add_argument('--' + name, type=int, default=default)
    add = sub.add_parser('add')
    add.add_argument('id')
    add.add_argument('--owner', required=True)
    add.add_argument('--record', required=True)
    add.add_argument('--input', action='append', default=[])
    add.add_argument('--scope', action='append', default=[])
    add.add_argument('--after', action='append', default=[])
    add.add_argument('--parent')
    add.add_argument('--next', required=True)
    add.add_argument('--independent-review', action='store_true')
    for command in ['start', 'requeue', 'output', 'verify', 'usage', 'transition']:
        cli = sub.add_parser(command)
        cli.add_argument('id')
        if command == 'output':
            cli.add_argument('path')
        elif command == 'requeue':
            inputs = cli.add_mutually_exclusive_group()
            inputs.add_argument('--input', action='append')
            inputs.add_argument('--no-inputs', action='store_true')
        elif command == 'verify':
            cli.add_argument('--evidence', required=True)
            cli.add_argument('--result', choices=['passed', 'failed'], required=True)
            cli.add_argument('--reviewer', required=True)
        elif command == 'usage':
            cli.add_argument('--jsonl', type=Path, required=True)
            cli.add_argument('--epoch', help='Explicit cumulative-counter epoch; retain it across resume')
            cli.add_argument('--sequence', type=int, help='Chronological observation ordinal; 0 declares the epoch start')
            cli.add_argument('--session-id', help='Verified session ID when the event stream has no thread.started')
            cli.add_argument('--elapsed-seconds', type=float)
            cli.add_argument('--human-corrections', type=int, default=0)
        elif command == 'transition':
            cli.add_argument('status', choices=sorted(STATES - {'queued', 'running'}))
            cli.add_argument('--next')
    view = sub.add_parser('inspect')
    view.add_argument('--stale-seconds', type=int, default=1800)
    view.add_argument('--invalidate', action='store_true')
    sub.add_parser('show')
    sub.add_parser('summary')
    args = parser.parse_args()
    root = args.root.resolve()
    relative(root, args.store, exists=False)
    if Path(args.store).parts[:2] != ('.agents', 'state'):
        raise ValueError('Operational store must stay in the local .agents/state directory')
    path = root / args.store
    mutate = args.command not in {'show', 'summary'} and not (args.command == 'inspect' and not args.invalidate)
    def execute():
        if args.command == 'init':
            if path.exists():
                raise ValueError('Store exists; resume it instead of initializing over existing state')
            limits = {k: getattr(args, k) for k in ['max_active', 'max_depth', 'max_attempts']}
            if min(limits.values()) < 1:
                raise ValueError('Limits must be positive')
            state = {'version': 1, 'created': now(), 'limits': limits, 'tasks': {}}
        else:
            state = json.loads(path.read_text(encoding='utf-8'))
            if state.get('version') != 1:
                raise ValueError('Unsupported store version')
        tasks = state['tasks']
        if args.command == 'add':
            if args.id in tasks or not args.id.strip():
                raise ValueError('Task ID must be new and nonempty')
            depth = 0
            parent = args.parent
            while parent:
                depth += 1
                parent = tasks[parent]['parent']
            if depth > state['limits']['max_depth']:
                raise ValueError('Delegation depth limit')
            if any(key not in tasks for key in args.after):
                raise ValueError('Unknown dependency')
            record = relative(root, args.record)
            scopes = [relative(root, p, exists=False) for p in args.scope]
            tasks[args.id] = {'owner': args.owner, 'record': record, 'revision': revision(root),
                'parent': args.parent, 'after': args.after, 'scope': scopes,
                'record_version': {'revision': revision(root), 'sha256': digest(root / record)},
                'input_contract': 2, 'input_paths': list(dict.fromkeys(args.input)),
                'inputs': snapshot(root, args.input), 'outputs': {},
                'status': 'queued', 'updated': now(), 'next': args.next,
                'attempts': 0, 'verification': None, 'history': [], 'usage': [],
                'independent_review': args.independent_review, 'human_corrections': 0}
        elif hasattr(args, 'id'):
            task = tasks[args.id]
            if args.command == 'start':
                if task['status'] != 'queued':
                    raise ValueError('Start requires queued state')
                if task['attempts'] >= state['limits']['max_attempts']:
                    raise ValueError('Attempt limit: revise the assignment before another run')
                if changed(root, task['inputs']):
                    raise ValueError('Inputs changed; inspect and requeue the affected task')
                if any(not completion_current(root, tasks, key) for key in task['after']):
                    raise ValueError('Dependency is incomplete or stale')
                active = [t for t in tasks.values() if t['status'] in {'running', 'evaluating'}]
                if len(active) >= state['limits']['max_active']:
                    raise ValueError('Active worker limit')
                for other in active:
                    if any(a == b or a.startswith(b + '/') or b.startswith(a + '/') for a in task['scope'] for b in other['scope']):
                        raise ValueError('Write scope overlaps an active task')
                task['attempts'] += 1
                transition(task, 'running')
            elif args.command == 'requeue':
                if task['status'] not in {'interrupted', 'failed'}:
                    raise ValueError('Requeue requires interrupted or failed state')
                if args.no_inputs:
                    input_paths = []
                elif args.input is not None:
                    input_paths = list(dict.fromkeys(args.input))
                elif task.get('input_contract') == 2:
                    input_paths = task['input_paths']
                else:
                    raise ValueError('Legacy inputs mixed record provenance with dependencies; requeue requires explicit --input paths or --no-inputs. Include the record with --input when it defines an actual dependency.')
                new_inputs = snapshot(root, input_paths)
                transition(task, 'queued')
                task['input_paths'], task['input_contract'] = input_paths, 2
                task['inputs'] = new_inputs
                task['outputs'], task['verification'] = {}, None
                task['revision'] = revision(root)
                task['record_version'] = {'revision': task['revision'], 'sha256': digest(root / task['record'])}
            elif args.command == 'output':
                if task['status'] not in {'running', 'evaluating'}:
                    raise ValueError('Output requires running or evaluating state')
                reference = relative(root, args.path)
                if not any(reference == scope or reference.startswith(scope + '/') for scope in task['scope']):
                    raise ValueError('Output is outside the assigned write scope')
                task['outputs'][reference] = digest(root / reference)
                task['updated'] = now()
            elif args.command == 'verify':
                if task['status'] != 'evaluating':
                    raise ValueError('Verification requires evaluating state')
                if task['independent_review'] and args.reviewer == task['owner']:
                    raise ValueError('Independent review requires a distinct reviewer identity')
                task['verification'] = {'result': args.result, 'reviewer': args.reviewer,
                                        'evidence': snapshot(root, [args.evidence]), 'at': now()}
            elif args.command == 'transition':
                allowed = {'running': {'evaluating', 'interrupted', 'failed'},
                           'evaluating': {'completed', 'interrupted', 'failed'},
                           'queued': {'interrupted', 'failed'}}
                if args.status not in allowed.get(task['status'], set()):
                    raise ValueError('Invalid transition')
                if args.status == 'completed' and (not task['outputs'] or not task['verification'] or task['verification']['result'] != 'passed' or changed(root, task['inputs']) or changed(root, task['outputs']) or changed(root, task['verification']['evidence']) or any(not completion_current(root, tasks, key) for key in task['after'])):
                    raise ValueError('Completion requires current outputs and passed evidence')
                if args.status in {'interrupted', 'failed'} and not args.next:
                    raise ValueError('Save the next authorized action for an unfinished task')
                transition(task, args.status, args.next)
            elif args.command == 'usage':
                if args.human_corrections < 0 or (args.elapsed_seconds is not None and args.elapsed_seconds < 0):
                    raise ValueError('Usage measures must be nonnegative')
                if args.sequence is not None and args.sequence < 0 or args.epoch is not None and not args.epoch.strip():
                    raise ValueError('Counter epoch must be nonempty and sequence nonnegative')
                run_hash = digest(args.jsonl)
                events = [json.loads(line) for line in args.jsonl.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
                observations, session_id = [], args.session_id
                for event in events:
                    if event.get('type') == 'thread.started':
                        event_id = event['thread_id']
                        if args.session_id and args.session_id != event_id:
                            raise ValueError('Declared session ID differs from the event stream')
                        session_id = event_id
                    if event.get('type') == 'turn.completed' and 'usage' in event:
                        counter = {field: event['usage'].get(field) for field in TOKEN_FIELDS}
                        if any(value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0) for value in counter.values()):
                            raise ValueError('Invalid token counter')
                        if counter['cached_input_tokens'] is not None and counter['input_tokens'] is not None and counter['cached_input_tokens'] > counter['input_tokens']:
                            raise ValueError('Cached input exceeds input counter')
                        if counter['reasoning_output_tokens'] is not None and counter['output_tokens'] is not None and counter['reasoning_output_tokens'] > counter['output_tokens']:
                            raise ValueError('Reasoning output exceeds output counter')
                        index = sum(row['session_id'] == session_id for row in observations)
                        observations.append({'session_id': session_id, 'index': index, 'counter': counter})
                identity = {'epoch': args.epoch, 'sequence': args.sequence, 'session_id': session_id, 'observations': observations}
                repeated = any(run.get('usage_contract') == 2 and {key: run[key] for key in identity} == identity and (observations or run['hash'] == run_hash) for t in tasks.values() for run in t['usage'])
                if not repeated:
                    task['usage'].append({'usage_contract': 2, 'hash': run_hash, **identity,
                        'elapsed_seconds': args.elapsed_seconds, 'imported': now()})
                    task['human_corrections'] += args.human_corrections
        if args.command == 'inspect':
            findings, stale = inspect(root, state, args.stale_seconds)
            if args.invalidate:
                for key in sorted(stale):
                    if tasks[key]['status'] in {'running', 'evaluating', 'completed'}:
                        transition(tasks[key], 'interrupted', 'Revalidate changed evidence and affected dependencies')
            output = {'findings': findings, 'affected_tasks': sorted(stale)}
        elif args.command == 'summary':
            output = report_usage(state)
        else:
            output = state if args.command == 'show' else {'command': args.command, 'tasks': len(tasks)}
        if mutate:
            save(path, state)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    if mutate:
        with locked(path):
            execute()
    else:
        execute()

if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
