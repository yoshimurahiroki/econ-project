#!/usr/bin/env python3
"""Record local task state and compare saved check results. Do not launch agents, call APIs or access credentials."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

STATES = {'queued', 'running', 'blocked', 'completed', 'failed'}
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
        raise ValueError(f'Missing referenced file: {path.as_posix()}')
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
    try:
        return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

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

def transition(task, status, next_action=None, reason=None):
    task['history'].append(json.loads(json.dumps({k: task.get(k) for k in
        ('status', 'updated', 'consumed_inputs', 'read_dependencies', 'outputs', 'check_receipts', 'next', 'record_version', 'authority', 'holds', 'blocked_reason', 'consumes', 'compatibility_dependencies', 'dependency_versions')})))
    task['status'], task['updated'] = status, now()
    task.pop('blocked_reason', None)
    if status == 'blocked':
        task['blocked_reason'] = reason or 'interrupted'
    if next_action is not None:
        task['next'] = next_action
    task['next_action'] = task['next']

def in_scope(path, scopes):
    return any(path == scope or path.startswith(scope + '/') for scope in scopes)

def output_files(task):
    return {key: row['version'] for key, row in task['outputs'].items() if row['kind'] == 'file'}

def input_changes(root, task):
    # Only a declared in-place modification can replace its consumed source.
    replaced = output_files(task) if task['operation_kind'] == 'modify' else {}
    immutable = {k: v for k, v in task['consumed_inputs'].items() if k not in replaced}
    return sorted(set(changed(root, immutable) + changed(root, task['read_dependencies'])))

def versions(task, output_ids=None, input_ids=None, include_actions=True):
    inputs = {**task['consumed_inputs'], **task['read_dependencies']}
    outputs = task['outputs']
    if input_ids is not None:
        inputs = {k: inputs[k] for k in input_ids}
    if output_ids is not None:
        outputs = {k: outputs[k] for k in output_ids}
    result = {'dependencies': selected_dependencies(task, output_ids), 'inputs': inputs, 'outputs': {k: {'kind': v['kind'], 'version': v['version'], **({'definition_versions': v['definition_versions']} if v.get('definition_versions') else {}), **({'publication_group_id': v['publication_group_id']} if v.get('publication_group_id') else {})} for k, v in outputs.items()}}
    if include_actions and task.get('action_results'):
        result['actions'] = [{k: row[k] for k in ('target_kind', 'target_id', 'operation', 'result', 'evidence', 'at', 'target_version')} for row in task['action_results']]
    return result

def receipt_current(root, task, receipt):
    if receipt.get('receipt_kind') == 'action':
        target = receipt['target_id']
        if receipt['target_kind'] == 'file':
            try:
                relative(root, target, exists=False)
                current = digest(root / target) if (root / target).is_file() else None
                if (root / target).exists() and not (root / target).is_file():
                    return False
                if current != receipt.get('target_version'):
                    return False
            except (ValueError, OSError):
                return False
        elif task['outputs'].get(target, {}).get('version') != receipt.get('target_output_version'):
            return False
    if receipt.get('result') != 'passed' or changed(root, receipt.get('evidence', {})):
        return False
    try:
        captured = receipt['versions']
        replaced = output_files(task) if task['operation_kind'] == 'modify' else {}
        reads = {k: v for k, v in captured['inputs'].items() if k not in replaced or k in task['read_dependencies']}
        files = {k: v['version'] for k, v in captured['outputs'].items() if v['kind'] == 'file'}
        return not changed(root, reads) and not changed(root, files) and captured == versions(task, receipt.get('output_ids'), receipt.get('input_ids'), include_actions=receipt.get('receipt_kind') != 'action')
    except KeyError:
        return False

def missing_checks(root, task):
    return [key for key in task['required_checks'] if not receipt_current(root, task, task['check_receipts'].get(key, {}))]

def dependency_key(row):
    return json.dumps([row['producer_id'], row['output_id']], separators=(',', ':'))

def output_version(row):
    result = {'kind': row['kind'], 'content_version': row['version'],
              'definition_versions': row.get('definition_versions', {})}
    if row.get('publication_group_id'):
        result['publication_group_id'] = row['publication_group_id']
    return result

def selected_dependencies(task, output_ids=None):
    saved = task.get('dependency_versions')
    if saved is None or output_ids is None:
        return saved
    keys = set()
    for key in output_ids:
        row = task['outputs'][key]
        keys.update(row.get('dependency_ids', saved))
    return {k: v for k, v in saved.items() if k in keys}

def legacy_versions(task):
    result = versions(task)
    result['dependencies'] = task.get('legacy_dependency_versions', task.get('dependency_versions'))
    return result

def dependency_value(tasks, row):
    producer = tasks[row['producer_id']]
    output = producer['outputs'].get(row['output_id'])
    if output is None:
        # Action-only results have stable target IDs but a receipt content version.
        actions = [r for r in producer.get('action_results', []) if r['target_id'] == row['output_id'] and r['target_kind'] == row['kind']]
        if not actions:
            return None
        output = {'kind': row['kind'], 'version': hashlib.sha256(json.dumps(actions, sort_keys=True).encode()).hexdigest()}
    value = output_version(output)
    if row.get('publication_group_id'):
        group = row['publication_group_id']
        value['publication_group'] = {k: output_version(v) for k, v in producer['outputs'].items() if v.get('publication_group_id') == group}
    return value

def dependency_versions(tasks, task):
    result = {dependency_key(row): dependency_value(tasks, row) for row in task.get('consumes', [])}
    for producer in task.get('compatibility_dependencies', []):
        result['legacy:' + producer] = legacy_versions(tasks[producer])
    return result

def dependencies_changed(tasks, task):
    return task.get('dependency_versions') != dependency_versions(tasks, task)

def parse_consumes(values, tasks, task_id):
    result = []
    required = {'producer_id', 'output_id', 'kind', 'content_version', 'definition_versions'}
    for raw in values:
        row = json.loads(raw)
        if not isinstance(row, dict) or not required <= set(row) or set(row) - required - {'publication_group_id'}:
            raise ValueError('Consumes requires producer_id, output_id, kind, content_version, definition_versions; publication_group_id is optional')
        if any(not isinstance(row[k], str) or not row[k].strip() for k in required - {'definition_versions'}):
            raise ValueError('Consumed IDs, kind and content version must be nonempty strings')
        if row['producer_id'] not in tasks or row['producer_id'] == task_id or row['kind'] not in {'file', 'message', 'object'}:
            raise ValueError('Consumes requires an existing other producer and file/message/object kind')
        if not isinstance(row['definition_versions'], dict) or any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip() for k, v in row['definition_versions'].items()):
            raise ValueError('Definition versions must map nonempty IDs to nonempty versions')
        if 'publication_group_id' in row and (not isinstance(row['publication_group_id'], str) or not row['publication_group_id'].strip()):
            raise ValueError('Publication group ID must be nonempty')
        if dependency_key(row) in {dependency_key(v) for v in result}:
            raise ValueError('Duplicate consumed output')
        result.append(row)
    # Existing producer graph must not lead back to this task on requeue.
    def reaches(key, seen):
        if key == task_id:
            return True
        if key in seen:
            return False
        return any(reaches(r['producer_id'], seen | {key}) for r in tasks[key].get('consumes', []))
    if any(reaches(r['producer_id'], set()) for r in result):
        raise ValueError('Consumed-output dependency cycle')
    return result

def expected_dependencies(tasks, consumes):
    result = {}
    for row in consumes:
        value = {k: row[k] for k in ('kind', 'content_version', 'definition_versions')}
        if row.get('publication_group_id'):
            value['publication_group_id'] = row['publication_group_id']
            current = dependency_value(tasks, row)
            value['publication_group'] = current.get('publication_group', {}) if current else {}
        result[dependency_key(row)] = value
    return result

def output_current(root, tasks, producer_id, output_id, seen=None):
    seen = set() if seen is None else seen
    if (producer_id, output_id) in seen:
        return False
    seen = seen | {(producer_id, output_id)}
    task = tasks[producer_id]
    row = task['outputs'].get(output_id)
    if task.get('holds') or input_changes(root, task):
        return False
    if row is None:
        if not consumed_current(root, tasks, task, seen):
            return False
        actions = [r for r in task.get('action_results', []) if r['target_id'] == output_id]
        return bool(actions) and all(receipt_current(root, task, r) for r in actions)
    if task.get('holds') or input_changes(root, task):
        return False
    if row['kind'] == 'file' and changed(root, {output_id: row['version']}):
        return False
    selected = selected_dependencies(task, [output_id]) or {}
    current = dependency_versions(tasks, task)
    if any(current.get(k) != v for k, v in selected.items()):
        return False
    for consumed in task.get('consumes', []):
        if dependency_key(consumed) in selected and not consumed_ref_current(root, tasks, consumed, seen):
            return False
    for check in task['required_checks']:
        receipt = task['check_receipts'].get(check)
        if not receipt or (receipt.get('output_ids') is None or output_id in receipt['output_ids']) and not receipt_current(root, task, receipt):
            return False
    return True

def consumed_ref_current(root, tasks, row, seen=None):
    if not output_current(root, tasks, row['producer_id'], row['output_id'], seen):
        return False
    group = row.get('publication_group_id')
    return not group or all(output_current(root, tasks, row['producer_id'], key, seen)
                            for key, output in tasks[row['producer_id']]['outputs'].items()
                            if output.get('publication_group_id') == group)

def consumed_current(root, tasks, task, seen=None):
    return (not dependencies_changed(tasks, task)
            and all(consumed_ref_current(root, tasks, row, seen) for row in task.get('consumes', []))
            and all(completion_current(root, tasks, key) for key in task.get('compatibility_dependencies', [])))

def contract(root, outputs, actions):
    outputs, actions = [json.loads(v) for v in outputs], [json.loads(v) for v in actions]
    for rows, fields in [(outputs, ('role', 'kind', 'target')), (actions, ('target_kind', 'target_id', 'operation'))]:
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(fields) or any(not isinstance(row[f], str) or not row[f].strip() for f in fields):
                raise ValueError('Requirements need exactly these nonempty string fields: ' + ', '.join(fields))
    for row in outputs:
        if row['kind'] not in {'file', 'message', 'object'}:
            raise ValueError('Required output kind must be file, message or object')
        if row['kind'] == 'file':
            row['target'] = relative(root, row['target'], exists=False)
    for row in actions:
        if row['target_kind'] not in {'file', 'object'}:
            raise ValueError('Action target kind must be file or object')
        if row['target_kind'] == 'file':
            row['target_id'] = relative(root, row['target_id'], exists=False)
    if len({v['target'] for v in outputs}) != len(outputs):
        raise ValueError('Each required output needs a distinct target ID/path')
    if len({v['role'] for v in outputs}) != len(outputs) or len({tuple(v[f] for f in ('target_kind', 'target_id', 'operation')) for v in actions}) != len(actions):
        raise ValueError('Requirement roles and action tuples must be unique')
    if not outputs and not actions:
        raise ValueError('Declare at least one requested output or action')
    return outputs, actions

def missing_deliverables(root, task):
    if task.get('completion_contract') != 1:
        return ['explicit-completion-contract-required']
    missing = []
    for requirement in task['required_outputs']:
        row = task['outputs'].get(requirement['target'], {})
        if (row.get('role') != requirement['role'] or row.get('kind') != requirement['kind']
                or not row.get('version') or (row.get('kind') == 'message' and not row.get('value', '').strip())):
            missing.append(requirement['role'])
    for requirement in task['required_actions']:
        if not any(all(result.get(k) == v for k, v in requirement.items()) and receipt_current(root, task, result)
                   for result in task.get('action_results', [])):
            missing.append(dict(requirement))
    return missing

def completion_current(root, tasks, key):
    task = tasks[key]
    return (task['status'] == 'completed' and not task.get('holds') and not missing_deliverables(root, task)
            and not input_changes(root, task) and not changed(root, output_files(task))
            and not missing_checks(root, task) and consumed_current(root, tasks, task))

def migrate(state):
    if state.get('version') == 4:
        return
    if state.get('version') == 3:
        tasks = state['tasks']
        for task in tasks.values():
            task['legacy_dependency_versions'] = task.get('dependency_versions')
        for task in tasks.values():
            old = task.get('dependency_versions') or {}
            consumes, compatibility = [], []
            for producer in task['after']:
                captured = old.get(producer, {})
                matched = [(key, row) for key, row in captured.get('outputs', {}).items()
                           if row['kind'] == 'file' and task['consumed_inputs'].get(key) == row['version']
                           and sum(key in old.get(other, {}).get('outputs', {}) for other in task['after']) == 1]
                if matched:
                    for key, row in matched:
                        consumes.append({'producer_id': producer, 'output_id': key, 'kind': row['kind'],
                                         'content_version': row['version'], 'definition_versions': {}})
                else:
                    compatibility.append(producer)
            task['consumes'], task['compatibility_dependencies'] = consumes, compatibility
            saved = expected_dependencies(tasks, consumes)
            saved.update({'legacy:' + key: old.get(key) for key in compatibility})
            task['dependency_versions'] = saved
            # Re-key only identical dependency evidence. Preserve stale evidence as stale.
            receipts = list(task.get('check_receipts', {}).values()) + task.get('action_results', [])
            if task.get('verification'):
                receipts.append(task['verification'])
            for receipt in receipts:
                if receipt.get('versions', {}).get('dependencies') == old:
                    receipt['versions']['dependencies'] = json.loads(json.dumps(saved))
        state['version'] = 4
        return
    if state.get('version') == 2:
        for task in state['tasks'].values():
            # Old outputs record what happened, never what was requested.
            task['completion_contract'] = None
            task['required_outputs'], task['required_actions'] = [], []
            task['action_results'], task['external_targets'] = [], []
            if task.get('blocked_reason') in {'permission', 'user_hold'} and not task.get('holds'):
                # Give the pre-existing hold a stable address; do not release it.
                task['holds'] = ['legacy:' + task['blocked_reason']]
            if task['status'] == 'completed':
                transition(task, 'blocked', 'Declare requested outputs/actions with set-contract; reuse current results', 'interrupted')
        state['version'] = 3
        migrate(state)
        return
    if state.get('version') != 1:
        raise ValueError('Unsupported store version')
    for key, task in state['tasks'].items():
        task['task_id'], task['parent_id'] = key, task.get('parent')
        task['operation_kind'] = 'modify' if any(in_scope(p, task['scope']) for p in task['inputs']) else ('create' if task['scope'] else 'answer')
        task['write_scope'] = task['scope']
        task['consumed_inputs'] = dict(task['inputs'])
        task['read_dependencies'] = {p: v for p, v in task['inputs'].items() if task['operation_kind'] != 'modify' or not in_scope(p, task['scope'])}
        task['read_paths'] = []
        task['dependency_versions'] = None
        task['outputs'] = {p: {'kind': 'file', 'version': v} for p, v in task['outputs'].items()}
        task['required_checks'], task['check_receipts'] = ['legacy-verification'], {}
        task['authority'], task['holds'], task['next_action'] = task.get('authority', {}), task.get('holds', []), task['next']
        if task['status'] == 'evaluating':
            task['status'] = 'running'
        elif task['status'] in {'completed', 'interrupted'}:
            task['status'], task['blocked_reason'] = 'blocked', 'interrupted'
            task['next'] = task['next_action'] = 'Run missing legacy-verification check on preserved outputs; do not rerun unchanged computation'
    # A v1 store did not record whether a limit was explicitly selected.
    # Preserve it, label that uncertainty, and let the operator revise the budget.
    state['limit_sources'] = {key: 'legacy_unspecified' for key in state['limits']}
    state['version'] = 2
    migrate(state)

def inspect(root, state, stale_seconds):
    findings, stale = [], set()
    for key, task in state['tasks'].items():
        paths = input_changes(root, task) + changed(root, output_files(task))
        if paths:
            stale.add(key)
            findings.append({'task': key, 'kind': 'changed-or-missing-evidence', 'paths': sorted(set(paths))})
        if not consumed_current(root, state['tasks'], task):
            stale.add(key)
            findings.append({'task': key, 'kind': 'upstream-version-changed'})
        deliverables = missing_deliverables(root, task)
        if deliverables:
            findings.append({'task': key, 'kind': 'missing-required-deliverables', 'requirements': deliverables})
            if task['status'] == 'completed':
                stale.add(key)
        missing = missing_checks(root, task)
        if missing:
            findings.append({'task': key, 'kind': 'missing-current-checks', 'checks': missing})
            if task['status'] == 'completed':
                stale.add(key)
        if task['status'] == 'running':
            seconds = (datetime.now(timezone.utc) - datetime.fromisoformat(task['updated'])).total_seconds()
            if seconds >= stale_seconds:
                findings.append({'task': key, 'kind': 'progress-review-due', 'seconds': int(seconds)})
        limit = state['limits'].get('max_attempts')
        if limit and task['attempts'] >= limit and task['status'] != 'completed':
            findings.append({'task': key, 'kind': 'attempt-limit', 'next': 'Review the explicitly configured attempt budget'})
    return findings, stale

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
            'meaning': 'CLI counters accumulate within each declared session epoch. Sequence zero identifies the captured epoch start. The declared sequence sets chronology. Input includes cached input; output includes reasoning output. Unknown values are null. Each interval increment measures the change since the preceding recorded observation.'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='Project root; defaults to current working directory')
    parser.add_argument('--store', default='.agents/state/team.json')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    for name, default in [('max-active', None), ('max-depth', None), ('max-attempts', None)]:
        init.add_argument('--' + name, type=int, default=default)
    add = sub.add_parser('add')
    add.add_argument('id')
    add.add_argument('--owner', required=True)
    add.add_argument('--record')
    add.add_argument('--operation-kind', choices=['answer', 'modify', 'create', 'external'], default='create')
    add.add_argument('--read-dependency', action='append', default=[])
    add.add_argument('--required-check', action='append', default=[])
    add.add_argument('--required-output', action='append', default=[], help='JSON: role, kind, target')
    add.add_argument('--required-action', action='append', default=[], help='JSON: target_kind, target_id, operation')
    add.add_argument('--external-target', action='append', default=[], help='Exact external object ID; not a file path')
    add.add_argument('--authority', default='')
    add.add_argument('--hold', action='append', default=[])
    add.add_argument('--input', action='append', default=[])
    add.add_argument('--scope', action='append', default=[])
    add.add_argument('--after', action='append', default=[])
    add.add_argument('--consumes', action='append', default=[], help='JSON consumed-output version contract')
    add.add_argument('--parent')
    add.add_argument('--next', required=True)
    add.add_argument('--independent-review', action='store_true')
    for command in ['start', 'resume', 'release-hold', 'set-contract', 'action', 'requeue', 'output', 'verify', 'usage', 'transition']:
        cli = sub.add_parser(command)
        cli.add_argument('id')
        if command == 'set-contract':
            cli.add_argument('--required-output', action='append', default=[])
            cli.add_argument('--required-action', action='append', default=[])
            cli.add_argument('--external-target', action='append', default=[])
        elif command == 'action':
            cli.add_argument('--target-kind', choices=['file', 'object'], required=True)
            cli.add_argument('--target-id', required=True)
            cli.add_argument('--target-version', help='External object version from the saved result/readback when no object output is registered')
            cli.add_argument('--operation', required=True)
            cli.add_argument('--result', choices=['passed', 'failed'], required=True)
            cli.add_argument('--evidence', required=True, help='Local saved result/receipt file; does not perform the action')
        elif command == 'release-hold':
            cli.add_argument('--hold-id', required=True)
            cli.add_argument('--authority', required=True, help='Reference to the authority resolving the saved hold')
            cli.add_argument('--next', required=True)
        elif command == 'output':
            cli.add_argument('path', help='File path or exact message/object ID')
            cli.add_argument('--role', help='Matching required output role; unmatched outputs are supplementary')
            cli.add_argument('--kind', choices=['file', 'message', 'object'], default='file')
            cli.add_argument('--value', help='Message text or JSON object content')
            cli.add_argument('--definition-versions', default='{}', help='JSON definition ID to version mapping')
            cli.add_argument('--publication-group-id')
            cli.add_argument('--producer-id', help='Local producer label; defaults to task ID')
            cli.add_argument('--no-dependencies', action='store_true', help='This output consumes none of the task dependencies')
            cli.add_argument('--dependency', action='append', help='JSON [producer_id, output_id]; omitted means all consumed dependencies')
        elif command == 'requeue':
            cli.add_argument('--output', action='append', default=[], help='Discard only this output ID')
            cli.add_argument('--producer', action='append', default=[], help='Discard outputs carrying this local producer label')
            cli.add_argument('--consumes', action='append', help='Replace consumed-output contract; use --no-consumes to clear')
            cli.add_argument('--no-consumes', action='store_true')
            inputs = cli.add_mutually_exclusive_group()
            inputs.add_argument('--input', action='append')
            inputs.add_argument('--no-inputs', action='store_true')
        elif command == 'verify':
            cli.add_argument('--evidence')
            cli.add_argument('--check', default='legacy-verification')
            cli.add_argument('--output', action='append')
            cli.add_argument('--input', action='append')
            cli.add_argument('--result', choices=['passed', 'failed'], required=True)
            cli.add_argument('--reviewer', required=True)
        elif command == 'usage':
            cli.add_argument('--jsonl', type=Path, required=True)
            cli.add_argument('--epoch', help='Declare the cumulative-counter epoch and retain it when resuming')
            cli.add_argument('--sequence', type=int, help='Declare the chronological observation ordinal; 0 identifies the epoch start')
            cli.add_argument('--session-id', help='Supply the verified session ID when the event stream has no thread.started')
            cli.add_argument('--elapsed-seconds', type=float)
            cli.add_argument('--human-corrections', type=int, default=0)
        elif command == 'transition':
            cli.add_argument('status', choices=sorted((STATES - {'queued', 'running'}) | {'evaluating', 'interrupted'}))
            cli.add_argument('--next')
            cli.add_argument('--hold-id', help='Required for a permission or user hold')
            cli.add_argument('--reason', choices=['dependency', 'user_hold', 'interrupted', 'permission'])
    view = sub.add_parser('inspect')
    view.add_argument('--stale-seconds', type=int, default=1800)
    view.add_argument('--invalidate', action='store_true')
    show = sub.add_parser('show')
    show.add_argument('task_id', nargs='?')
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
                raise ValueError('Store exists; resume its saved state')
            limits = {k: getattr(args, k) for k in ['max_active', 'max_depth', 'max_attempts']}
            if any(value is not None and value < 1 for value in limits.values()):
                raise ValueError('Limits must be positive')
            state = {'version': 4, 'created': now(), 'limits': limits, 'limit_sources': {k: 'explicit' if v is not None else 'unset' for k, v in limits.items()}, 'tasks': {}}
        else:
            state = json.loads(path.read_text(encoding='utf-8'))
            migrate(state)
        tasks = state['tasks']
        if args.command == 'add':
            if args.id in tasks or not args.id.strip():
                raise ValueError('Task ID must be new and nonempty')
            depth = 0
            parent = args.parent
            while parent:
                depth += 1
                parent = tasks[parent]['parent']
            if state['limits'].get('max_depth') is not None and depth > state['limits']['max_depth']:
                raise ValueError('Delegation depth limit')
            if any(key not in tasks for key in args.after):
                raise ValueError('Unknown dependency')
            consumes = parse_consumes(args.consumes, tasks, args.id)
            required_outputs, required_actions = contract(root, args.required_output, args.required_action)
            if any(not v.strip() for v in args.external_target) or len(set(args.hold)) != len(args.hold) or any(not v.strip() for v in args.hold):
                raise ValueError('External targets and unique hold IDs must be nonempty')
            record = relative(root, args.record) if args.record else None
            scopes = [relative(root, p, exists=False) for p in args.scope]
            consumed = snapshot(root, args.input)
            reads = snapshot(root, args.read_dependency)
            reads.update({p: v for p, v in consumed.items() if args.operation_kind != 'modify' or not in_scope(p, scopes)})
            tasks[args.id] = {'task_id': args.id, 'owner': args.owner, 'record': record, 'revision': revision(root),
                'parent': args.parent, 'parent_id': args.parent, 'after': args.after, 'scope': scopes, 'write_scope': scopes,
                'operation_kind': args.operation_kind, 'read_paths': list(dict.fromkeys(args.read_dependency)), 'read_dependencies': reads,
                'consumed_inputs': consumed, 'required_checks': list(dict.fromkeys(args.required_check)), 'check_receipts': {},
                'authority': args.authority, 'holds': args.hold, 'next_action': args.next,
                'consumes': consumes, 'compatibility_dependencies': [], 'dependency_versions': expected_dependencies(tasks, consumes),
                'record_version': {'revision': revision(root), 'sha256': digest(root / record) if record else None},
                'input_contract': 2, 'input_paths': list(dict.fromkeys(args.input)),
                'inputs': consumed, 'outputs': {}, 'completion_contract': 1,
                'required_outputs': required_outputs, 'required_actions': required_actions,
                'action_results': [], 'external_targets': list(dict.fromkeys(args.external_target)),
                'status': 'queued', 'updated': now(), 'next': args.next,
                'attempts': 0, 'verification': None, 'history': [], 'usage': [],
                'independent_review': args.independent_review, 'human_corrections': 0}
        elif hasattr(args, 'id'):
            task = tasks[args.id]
            if args.command == 'set-contract':
                if task['status'] not in {'queued', 'blocked', 'failed'}:
                    raise ValueError('Set contract requires queued, blocked or failed state')
                outputs, actions = contract(root, args.required_output, args.required_action)
                if any(not v.strip() for v in args.external_target):
                    raise ValueError('External target IDs must be nonempty')
                task['required_outputs'], task['required_actions'] = outputs, actions
                task['completion_contract'] = 1
                task['external_targets'] = list(dict.fromkeys(args.external_target))
                task['action_results'] = []
                # Explicit requirements may map preserved legacy outputs without recomputation.
                for row in task['outputs'].values():
                    row.pop('role', None)
                for requirement in outputs:
                    row = task['outputs'].get(requirement['target'])
                    if row and row['kind'] == requirement['kind']:
                        row['role'] = requirement['role']
            elif args.command == 'release-hold':
                if task['status'] != 'blocked' or not args.authority.strip():
                    raise ValueError('Releasing a hold requires blocked state and an authority reference')
                if args.hold_id not in task['holds']:
                    raise ValueError('Unknown hold ID; release only a recorded hold')
                prior_reason = task.get('blocked_reason', 'interrupted')
                transition(task, 'blocked', args.next, prior_reason)
                task['holds'].remove(args.hold_id)
                task['authority'] = args.authority
                task.setdefault('hold_releases', []).append({'hold_id': args.hold_id, 'authority': args.authority, 'at': now()})
                if not task['holds']:
                    task['blocked_reason'] = 'interrupted'
            elif args.command in {'start', 'resume'}:
                if args.command == 'start' and task['status'] != 'queued':
                    raise ValueError('Start requires queued state')
                if args.command == 'resume' and task['status'] != 'blocked':
                    raise ValueError('Resume requires blocked state')
                if task['operation_kind'] == 'external' and not task.get('external_targets'):
                    raise ValueError('External operations require assigned external object IDs')
                if task['operation_kind'] in {'create', 'modify'} and not task['scope']:
                    raise ValueError('Writing operations require an assigned write scope')
                if task.get('holds') or task.get('blocked_reason') in {'permission', 'user_hold'}:
                    raise ValueError('Resolve the saved permission or user hold before resuming')
                limit = state['limits'].get('max_attempts')
                if args.command == 'start' and limit and task['attempts'] >= limit:
                    raise ValueError('Explicit attempt budget reached; review that budget before another run')
                if input_changes(root, task) or changed(root, output_files(task)):
                    raise ValueError('Inputs or outputs changed; inspect and requeue the affected task')
                if args.command == 'start' and any(tasks[key]['status'] != 'completed' for key in task['after']):
                    raise ValueError('Dependency is incomplete or stale')
                active = [t for t in tasks.values() if t['status'] == 'running']
                if state['limits'].get('max_active') is not None and len(active) >= state['limits']['max_active']:
                    raise ValueError('Active worker limit')
                for other in active:
                    if set(task.get('external_targets', [])) & set(other.get('external_targets', [])):
                        raise ValueError('External target overlaps an active task')
                    if any(a == b or a.startswith(b + '/') or b.startswith(a + '/') for a in task['scope'] for b in other['scope']):
                        raise ValueError('Write scope overlaps an active task')
                if not consumed_current(root, tasks, task):
                    raise ValueError('Dependency versions changed; requeue the affected operation')
                task['dependency_versions'] = dependency_versions(tasks, task)
                if args.command == 'start':
                    task['attempts'] += 1
                transition(task, 'running')
            elif args.command == 'requeue':
                if task['status'] not in {'blocked', 'failed'} and not (task['status'] == 'completed' and (args.output or args.producer or args.consumes is not None or args.no_consumes)):
                    raise ValueError('Requeue requires blocked/failed state, or an explicit output/producer/consumes selection for a completed task')
                if task.get('holds') or task.get('blocked_reason') in {'permission', 'user_hold'}:
                    raise ValueError('Resolve the saved permission or user hold before requeueing')
                if args.no_inputs:
                    input_paths = []
                elif args.input is not None:
                    input_paths = list(dict.fromkeys(args.input))
                elif task.get('input_contract') == 2:
                    input_paths = task['input_paths']
                else:
                    raise ValueError('Legacy inputs require explicit --input paths or --no-inputs')
                stale_inputs = input_changes(root, task)
                new_inputs = snapshot(root, input_paths)
                reads = snapshot(root, task['read_paths'])
                reads.update({p: v for p, v in new_inputs.items() if task['operation_kind'] != 'modify' or not in_scope(p, task['scope'])})
                transition(task, 'queued')
                task['input_paths'], task['input_contract'] = input_paths, 2
                task['inputs'] = task['consumed_inputs'] = new_inputs
                task['read_dependencies'] = reads
                if args.consumes is not None and args.no_consumes:
                    raise ValueError('Use --consumes or --no-consumes, not both')
                previous_dependencies = task.get('dependency_versions') or {}
                if args.consumes is not None or args.no_consumes:
                    task['consumes'] = parse_consumes(args.consumes or [], tasks, args.id)
                    task['compatibility_dependencies'] = []
                    new_dependencies = expected_dependencies(tasks, task['consumes'])
                else:
                    new_dependencies = dependency_versions(tasks, task)
                    for row in task.get('consumes', []):
                        value = new_dependencies[dependency_key(row)]
                        if value is None:
                            raise ValueError('Consumed output is missing; restore it or replace the consumes contract')
                        row['content_version'], row['definition_versions'] = value['content_version'], value['definition_versions']
                changed_dependencies = {k for k in set(previous_dependencies) | set(new_dependencies) if previous_dependencies.get(k) != new_dependencies.get(k)}
                selected = set(args.output)
                if selected - set(task['outputs']):
                    raise ValueError('Unknown selected output')
                producers = {row.get('producer_id', task['task_id']) for row in task['outputs'].values()}
                if set(args.producer) - producers:
                    raise ValueError('Unknown selected producer')
                selected.update(key for key, row in task['outputs'].items() if row.get('producer_id', task['task_id']) in args.producer)
                # Stale bytes/dependencies always lose their result registration, even with a narrower selector.
                selected.update(changed(root, output_files(task)))
                if stale_inputs:
                    selected.update(task['outputs'])
                selected.update(key for key, row in task['outputs'].items() if set(row.get('dependency_ids', previous_dependencies)) & changed_dependencies)
                task['outputs'] = {key: row for key, row in task['outputs'].items() if key not in selected}
                task['dependency_versions'] = new_dependencies
                task['action_results'] = [r for r in task['action_results'] if r['target_id'] not in selected and receipt_current(root, task, r)]
                task['check_receipts'] = {k: v for k, v in task['check_receipts'].items() if receipt_current(root, task, v)}
                if task['verification'] and not receipt_current(root, task, task['verification']):
                    task['verification'] = None
                task['revision'] = revision(root)
                task['record_version'] = {'revision': task['revision'], 'sha256': digest(root / task['record']) if task['record'] else None}
            elif args.command == 'output':
                if task['status'] != 'running':
                    raise ValueError('Output requires running state')
                if args.kind == 'file':
                    if task['operation_kind'] == 'answer':
                        raise ValueError('Answer operations return message or object outputs')
                    reference = relative(root, args.path)
                    if not in_scope(reference, task['scope']):
                        raise ValueError('Output is outside the assigned write scope')
                    row = {'kind': 'file', 'version': digest(root / reference)}
                else:
                    if not args.path.strip() or args.value is None:
                        raise ValueError('Message/object output requires a nonempty ID and --value')
                    reference = args.path
                    if task['operation_kind'] == 'external' and args.kind == 'object' and reference not in task['external_targets']:
                        raise ValueError('Object output is outside assigned external target IDs')
                    value = json.loads(args.value) if args.kind == 'object' else args.value
                    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')
                    row = {'kind': args.kind, 'version': hashlib.sha256(encoded).hexdigest(), 'value': value}
                matches = [r for r in task['required_outputs'] if r['target'] == reference and r['kind'] == args.kind]
                if args.role:
                    matches = [r for r in matches if r['role'] == args.role]
                    if not matches:
                        raise ValueError('Output role, kind and target must match a required output')
                if len(matches) > 1:
                    raise ValueError('Specify the required output role')
                if matches:
                    row['role'] = matches[0]['role']
                definitions = json.loads(args.definition_versions)
                if not isinstance(definitions, dict) or any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip() for k, v in definitions.items()):
                    raise ValueError('Definition versions must map nonempty IDs to nonempty versions')
                row['definition_versions'] = definitions
                row['producer_id'] = args.producer_id or task['task_id']
                if not row['producer_id'].strip() or args.publication_group_id is not None and not args.publication_group_id.strip():
                    raise ValueError('Producer and publication group IDs must be nonempty')
                if args.publication_group_id:
                    row['publication_group_id'] = args.publication_group_id
                if args.no_dependencies and args.dependency is not None:
                    raise ValueError('Use --dependency or --no-dependencies, not both')
                dependency_ids = [] if args.no_dependencies else list(task['dependency_versions']) if args.dependency is None else [json.dumps(json.loads(v), separators=(',', ':')) for v in args.dependency]
                if set(dependency_ids) - set(task['dependency_versions']):
                    raise ValueError('Output dependency must select a declared consumed output')
                row['dependency_ids'] = dependency_ids
                task['outputs'][reference] = row
                # Drop only receipts whose captured version selection changed.
                task['check_receipts'] = {k: v for k, v in task['check_receipts'].items() if receipt_current(root, task, v)}
                if task['verification'] and not receipt_current(root, task, task['verification']):
                    task['verification'] = None
                task['updated'] = now()
            elif args.command == 'action':
                if task['status'] != 'running':
                    raise ValueError('Action result requires running state')
                target = relative(root, args.target_id, exists=False) if args.target_kind == 'file' else args.target_id
                requirement = {'target_kind': args.target_kind, 'target_id': target, 'operation': args.operation}
                if requirement not in task['required_actions']:
                    raise ValueError('Action must match a requested target and operation')
                if args.target_kind == 'object' and target not in task['external_targets']:
                    raise ValueError('Action target is outside assigned external object IDs')
                if args.target_kind == 'file' and not in_scope(target, task['scope']):
                    raise ValueError('Action target is outside assigned file scope')
                if input_changes(root, task) or changed(root, output_files(task)):
                    raise ValueError('Action result requires unchanged inputs and current outputs')
                target_output = task['outputs'].get(target, {})
                if args.target_kind == 'file':
                    if (root / target).is_file():
                        target_version = digest(root / target)
                    elif not (root / target).exists() and args.operation in {'delete', 'remove', 'unlink'}:
                        target_version = None  # Explicit deletion tombstone.
                    else:
                        raise ValueError('File action requires the current file, or a missing target for a deletion operation')
                else:
                    if target_output and target_output['kind'] != 'object':
                        raise ValueError('External action target must reference an object output')
                    target_version = target_output.get('version') or args.target_version
                    if not target_version or not target_version.strip():
                        raise ValueError('External action needs a registered object output or explicit --target-version from its result')
                selected = [target] if target_output else []
                result = {**requirement, 'result': args.result, 'evidence': snapshot(root, [args.evidence]),
                          'target_version': target_version, 'target_output_version': target_output.get('version'),
                          'output_ids': selected, 'at': now(), 'receipt_kind': 'action',
                          'versions': versions(task, selected, include_actions=False)}
                task['action_results'] = [r for r in task['action_results'] if any(r[k] != v for k, v in requirement.items())] + [result]
            elif args.command == 'verify':
                if task['status'] != 'running':
                    raise ValueError('Verification requires running state; resume preserved outputs first')
                if task['independent_review'] and args.reviewer == task['owner']:
                    raise ValueError('Independent review requires a distinct reviewer identity')
                if not (task['outputs'] or task.get('action_results')) or input_changes(root, task) or changed(root, output_files(task)):
                    raise ValueError('Check requires registered results and unchanged external inputs')
                receipt = {'operation': args.check, 'result': args.result, 'reviewer': args.reviewer,
                    'evidence': snapshot(root, [args.evidence]) if args.evidence else {}, 'at': now(),
                    'output_ids': args.output, 'input_ids': args.input, 'versions': versions(task, args.output, args.input)}
                task['check_receipts'][args.check] = receipt
                task['verification'] = receipt
            elif args.command == 'transition':
                status = {'evaluating': 'running', 'interrupted': 'blocked'}.get(args.status, args.status)
                allowed = {'running': {'running', 'completed', 'blocked', 'failed'},
                           'queued': {'blocked', 'failed'}}
                if status not in allowed.get(task['status'], set()):
                    raise ValueError('Invalid transition')
                if status == 'completed' and (task.get('holds') or missing_deliverables(root, task) or missing_checks(root, task) or not consumed_current(root, tasks, task) or input_changes(root, task) or changed(root, output_files(task))):
                    raise ValueError('Completion requires matching requested outputs/actions, current versions/check receipts and completed dependencies')
                if status in {'blocked', 'failed'} and not args.next:
                    raise ValueError('Save the next authorized action for an unfinished task')
                if status == 'blocked' and args.reason in {'permission', 'user_hold'}:
                    if not args.hold_id or not args.hold_id.strip():
                        raise ValueError('Permission/user hold requires an explicit --hold-id')
                    if args.hold_id not in task['holds']:
                        task['holds'].append(args.hold_id)
                transition(task, status, args.next, args.reason)
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
                    if tasks[key]['status'] in {'running', 'completed'}:
                        transition(tasks[key], 'blocked', 'Inspect changed dependencies; preserve current outputs and rerun only affected operations', 'dependency')
            output = {'findings': findings, 'affected_tasks': sorted(stale)}
        elif args.command == 'summary':
            output = report_usage(state)
        elif args.command == 'show':
            if args.task_id is not None and args.task_id not in tasks:
                raise ValueError(f'Unknown task ID: {args.task_id}')
            output = tasks[args.task_id] if args.task_id is not None else state
        else:
            output = {'command': args.command, 'tasks': len(tasks)}
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
