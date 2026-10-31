#!/usr/bin/env python3
"""Record local task state and compare saved check results."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

_base = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('state_local_io', next(p for p in
    (_base / 'local_checks.py', _base / 'LOCAL_CHECKS.py') if p.is_file()))
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

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

def content_hash(value):
    """One encoding for registering and rechecking saved message/object bodies."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()

def content_version(row):
    if row['kind'] in {'message', 'object'}:
        return content_hash(row['value']) if 'value' in row else None
    return row['version']

def output_changes(root, task):
    changes = changed(root, output_files(task))
    for key, row in task['outputs'].items():
        if row['kind'] in {'message', 'object'} and (content_version(row) != row.get('version')
                or row['kind'] == 'message' and not isinstance(row.get('value'), str)):
            changes.append(key)
    return sorted(set(changes))

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
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        try:
            gate.lock_fd(fd)
        except BlockingIOError as exc:
            raise ValueError(f'State writer active for {path}; retry this update after that writer exits') from exc
        yield
    finally:
        # Keep one stable lock inode. Closing releases ownership even after a
        # failed operation; process termination releases the descriptor in the OS.
        os.close(fd)

def save(path, state):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        gate.replace_path(temporary, path)
        gate.sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def context_id(task):
    """Hash governing content, excluding scheduling and continuation display."""
    value = {key: task.get(key) for key in
             ('authority', 'required_outputs', 'required_actions', 'required_checks',
              'check_targets', 'scope', 'external_targets', 'task_context', 'writing_state')}
    value['holds'] = sorted(task.get('holds', []))
    if task.get('parent'):
        value['inherited_constraints_sha256'] = task.get('effective_constraints_sha256')
    value['record_sha256'] = task.get('record_version', {}).get('sha256')
    return content_hash(value)


def bind_paragraph_state(root, task, path):
    """Bind one actual resumable paragraph state without granting final release."""
    path = relative(root, path)
    module_path = _base / 'paragraph.py'
    spec = importlib.util.spec_from_file_location('state_paragraph_engine', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = module.ParagraphRun.load(root / path)
    value = run.state
    reference = {'path': path, 'sha256': digest(root / path), 'run_id': value['run_id'],
                 'request_sha256': value['request_sha256'], 'rules_sha256': value['rules_sha256'],
                 'blueprint_sha256': value['blueprint']['sha256'],
                 'paragraphs': {pid: {'status': row['status'], 'spec_sha256': row['spec_sha256'],
                                      'text_sha256': row['text_sha256']}
                                for pid, row in value['paragraphs'].items()}}
    if task.get('writing_state') != reference:
        task['writing_state'] = reference
        task['check_receipts'], task['verification'] = {}, None
        if task['status'] == 'completed':
            transition(task, 'blocked', 'Check the changed paragraph state and affected outputs', 'interrupted')
    return reference


def load_task_context(root, path):
    """Read the existing context record; refs stay in the project namespace."""
    path = relative(root, path)
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate task_context key: ' + key)
            value[key] = item
        return value
    value = json.loads((root / path).read_text(encoding='utf-8'), object_pairs_hook=pairs,
                       parse_constant=lambda item: (_ for _ in ()).throw(ValueError('Nonfinite task_context value')))
    if (not isinstance(value, dict) or set(value) !=
            {'request_refs', 'goal_and_constraints', 'active_instruction_refs', 'adopted_decisions'}
            or not isinstance(value['goal_and_constraints'], str) or not value['goal_and_constraints'].strip()):
        raise ValueError('task_context requires request_refs, goal_and_constraints, active_instruction_refs and adopted_decisions')
    for field, identity, extra in [('request_refs', 'source_id', set()),
                                    ('active_instruction_refs', 'rule_id', {'section'})]:
        rows, seen = value[field], set()
        if not isinstance(rows, list):
            raise ValueError('task_context references must be arrays')
        for row in rows:
            required = {identity, 'version', 'content_sha256'} | extra
            if (not isinstance(row, dict) or not required <= set(row) or set(row) - required - {'path'}
                    or any(not isinstance(row[key], str) or not row[key].strip() for key in {identity} | extra)
                    or not (isinstance(row['version'], str) and row['version'].strip()
                            or type(row['version']) is int and row['version'] >= 0)
                    or not isinstance(row['content_sha256'], str)
                    or len(row['content_sha256']) != 64 or any(c not in '0123456789abcdef' for c in row['content_sha256'])):
                raise ValueError('Invalid task_context reference')
            key = (row[identity], row.get('section'))
            if key in seen:
                raise ValueError('Duplicate task_context reference')
            seen.add(key)
            if 'path' in row:
                name = relative(root, row['path'])
                if digest(root / name) != row['content_sha256']:
                    raise ValueError('task_context reference content changed: ' + name)
    rows, seen = value['adopted_decisions'], set()
    if not isinstance(rows, list):
        raise ValueError('adopted_decisions must be an array')
    for row in rows:
        if (not isinstance(row, dict) or not {'decision_id', 'version', 'choice', 'reason', 'switch_condition'} <= set(row)
                or set(row) - {'decision_id', 'version', 'choice', 'reason', 'switch_condition', 'change_authority'}
                or row.get('change_authority', 'fixed') not in {'fixed', 'delegated'}
                or any(not isinstance(row[k], str) or not row[k].strip()
                       for k in ('decision_id', 'choice', 'reason', 'switch_condition'))
                or not (isinstance(row['version'], str) and row['version'].strip()
                        or type(row['version']) is int and row['version'] >= 0)
                or row['decision_id'] in seen):
            raise ValueError('Adopted decision requires a unique ID, version, choice, reason and switch condition')
        seen.add(row['decision_id'])
    return value, {'path': path, 'sha256': content_hash(value)}


def record_context(task, source):
    revisions = task.setdefault('context_revisions', [])
    value = json.loads(json.dumps(task.get('task_context')))
    revisions.append({'revision': len(revisions) + 1, 'context': value,
                      'sha256': content_hash(value), 'source': source, 'at': now()})


def context_current(root, task):
    revisions = task.get('context_revisions', [])
    if not revisions:
        return True  # Existing stores and inherited contexts retain their source bindings.
    try:
        return (revisions[-1]['context'] == task.get('task_context')
                and all(row['revision'] == index + 1 and row['sha256'] == content_hash(row['context'])
                        and not changed(root, row['source'].get('evidence', {}))
                        for index, row in enumerate(revisions)))
    except (KeyError, TypeError, ValueError, OSError):
        return False


def context_change(root, task, value, user_change, decision_updates):
    """Preserve binding instructions; revise delegated choices on recorded evidence."""
    if not context_current(root, task):
        raise ValueError('Saved context revision/evidence changed; reconcile the original records')
    previous = task.get('task_context')
    if previous == value:
        return False
    source = {'kind': 'additive-context'}
    protected_change = previous is not None and previous['goal_and_constraints'] != value['goal_and_constraints']
    if previous is not None:
        for field in ('request_refs', 'active_instruction_refs'):
            old = [{k: v for k, v in row.items() if k != 'path'} for row in previous[field]]
            new = [{k: v for k, v in row.items() if k != 'path'} for row in value[field]]
            protected_change |= any(row not in new for row in old)
        decisions = {row['decision_id']: row for row in value['adopted_decisions']}
        replaced = [row for row in previous['adopted_decisions'] if decisions.get(row['decision_id']) != row]
        protected_change |= any(row['decision_id'] not in decisions
                                or row.get('change_authority', 'fixed') != 'delegated'
                                or decisions[row['decision_id']].get('change_authority', 'fixed') != 'delegated'
                                or decisions[row['decision_id']]['switch_condition'] != row['switch_condition']
                                for row in replaced)
    else:
        replaced, decisions = [], {}
    if protected_change and not user_change:
        raise ValueError('Removing or replacing binding context requires --user-change evidence of the user instruction')
    if user_change:
        source = user_change_evidence(root, user_change, previous, value, 'context')
    elif replaced:
        updates = [gate.parse_json(text.encode('utf-8')) for text in decision_updates]
        expected = {row['decision_id'] for row in replaced}
        if (len(updates) != len(expected) or any(not isinstance(row, dict)
                or set(row) != {'decision_id', 'reason', 'evidence'}
                or not isinstance(row['reason'], str) or not row['reason'].strip()
                or not isinstance(row['evidence'], list) or not row['evidence']
                for row in updates) or {row['decision_id'] for row in updates} != expected):
            raise ValueError('Each revised delegated decision needs --decision-update with its ID, reason and evidence paths')
        for row in replaced:
            if decisions[row['decision_id']]['version'] == row['version']:
                raise ValueError('A revised decision requires a new version')
        source = {'kind': 'delegated-decision', 'updates': updates,
                  'evidence': snapshot(root, [path for row in updates for path in row['evidence']])}
    elif decision_updates:
        raise ValueError('Decision-update evidence must match a revised delegated decision')
    if not task.get('context_revisions'):
        record_context(task, {'kind': 'legacy-retained' if previous is not None else 'initial-declaration'})
    task['task_context'] = value
    record_context(task, source)
    return True


def context_changes(root, task):
    """Compare recorded content, never a Git label or task progress timestamp."""
    changes = []
    if not context_current(root, task):
        changes.append('context-revision-or-evidence-changed')
    record = task.get('record')
    if record:
        try:
            path = relative(root, record)
            if digest(root / path) != task.get('record_version', {}).get('sha256'):
                changes.append('record:' + path)
        except (ValueError, OSError):
            changes.append('record:' + record)
    ref = task.get('task_context_ref')
    if ref:
        try:
            value, current = load_task_context(root, ref['path'])
            if current != ref or value != task.get('task_context'):
                changes.append('task_context:' + ref['path'])
        except (ValueError, OSError, KeyError, TypeError):
            changes.append('task_context:' + str(ref.get('path')))
    writing = task.get('writing_state')
    if writing:
        try:
            path = relative(root, writing['path'])
            if digest(root / path) != writing['sha256']:
                changes.append('writing_state:' + path)
        except (ValueError, OSError, KeyError, TypeError):
            changes.append('writing_state:' + str(writing.get('path')))
    return changes


def transition(task, status, next_action=None, reason=None):
    task['history'].append(json.loads(json.dumps({k: task.get(k) for k in
        ('status', 'updated', 'consumed_inputs', 'read_dependencies', 'outputs', 'check_receipts', 'next', 'record_version', 'authority', 'holds', 'blocked_reason', 'consumes', 'compatibility_dependencies', 'dependency_versions', 'task_context', 'task_context_ref')})))
    task['status'], task['updated'] = status, now()
    task.pop('blocked_reason', None)
    if status == 'blocked':
        task['blocked_reason'] = reason or 'interrupted'
    if next_action is not None:
        task['next'] = next_action
    task['next_action'] = task['next']

def in_scope(path, scopes):
    return any(scope == '.' or path == scope or path.startswith(scope + '/') for scope in scopes)

def scopes_overlap(left, right):
    return left == '.' or right == '.' or left == right or left.startswith(right + '/') or right.startswith(left + '/')


def task_ancestors(tasks, task):
    result, seen = [], {task['task_id']}
    parent = task.get('parent')
    while parent:
        if parent in seen or parent not in tasks:
            raise ValueError('Unknown or cyclic parent task')
        seen.add(parent)
        result.append(tasks[parent])
        parent = tasks[parent].get('parent')
    return result


def hold_applies(row, task):
    operations = {task['operation_kind']} | {r['operation'] for r in task.get('required_actions', [])}
    if row.get('operations') and not operations.intersection(row['operations']):
        return False
    targets = row.get('targets', [])
    if not targets:
        return True
    files = list(task.get('scope', [])) + [r['target'] for r in task.get('required_outputs', []) if r['kind'] == 'file']
    files += [r['target_id'] for r in task.get('required_actions', []) if r['target_kind'] == 'file']
    objects = set(task.get('external_targets', []))
    return any((target.startswith('file:') and any(scopes_overlap(target[5:], path) for path in files))
               or (target.startswith('object:') and target[7:] in objects) for target in targets)


def effective_constraints(tasks, task, root=None):
    """Derive inherited bounds from their setters, never a child's omissions."""
    ancestors = task_ancestors(tasks, task)
    holds, errors, inherited = [], [], []
    for owner in [task, *ancestors]:
        for hold_id in owner.get('holds', []):
            row = owner.get('hold_records', {}).get(hold_id, {})
            row = {'hold_id': hold_id, 'source_task_id': owner['task_id'],
                   'source_requirement_ids': row.get('source_requirement_ids', []),
                   'operations': row.get('operations', []), 'targets': row.get('targets', [])}
            if owner is task or hold_applies(row, task):
                holds.append(row)
        if owner is task:
            continue
        if root is not None and context_changes(root, owner):
            errors.append({'source_task_id': owner['task_id'], 'kind': 'governing-content-changed'})
        if any(not in_scope(path, owner.get('scope', [])) for path in task.get('scope', [])):
            errors.append({'source_task_id': owner['task_id'], 'kind': 'write-scope'})
        if set(task.get('external_targets', [])) - set(owner.get('external_targets', [])):
            errors.append({'source_task_id': owner['task_id'], 'kind': 'external-target'})
        inherited.append({'source_task_id': owner['task_id'], 'authority': owner.get('authority', ''),
                          'task_context': owner.get('task_context'),
                          'record_sha256': owner.get('record_version', {}).get('sha256')})
    return {'inherited': inherited, 'holds': holds, 'scope_errors': errors}


def constraints_current(root, tasks, task):
    value = effective_constraints(tasks, task, root)
    return (not value['holds'] and not value['scope_errors']
            and (not task.get('parent') or task.get('effective_constraints_sha256') == content_hash(value)))


def refresh_constraints(root, tasks):
    """Invalidate affected assessments while retaining every saved output."""
    for task in sorted(tasks.values(), key=lambda row: len(task_ancestors(tasks, row))):
        inherited_from = task.get('task_context_inherited_from')
        if inherited_from:
            parent = tasks[inherited_from]
            for key in ('task_context', 'task_context_ref'):
                if key in parent:
                    task[key] = json.loads(json.dumps(parent[key]))
                else:
                    task.pop(key, None)
        value = effective_constraints(tasks, task, root)
        previous, current = task.get('effective_constraints_sha256'), content_hash(value)
        changed = previous != current and (previous is not None or task.get('parent') and
                  (task['status'] in {'running', 'completed'} or task.get('check_receipts')))
        task['effective_constraints_sha256'] = current
        task['effective_holds'] = value['holds']
        task['inherited_authority'] = value['inherited']
        task['constraint_errors'] = value['scope_errors']
        if changed:
            task['check_receipts'], task['verification'] = {}, None
            if task['status'] in {'running', 'completed'}:
                transition(task, 'blocked', 'Reconcile changed parent constraints; preserve outputs and obtain affected checks',
                           'permission' if value['holds'] or value['scope_errors'] else 'dependency')
                task['constraint_blocked'] = True
            elif task['status'] == 'blocked' and task.get('constraint_blocked') and not value['holds'] and not value['scope_errors']:
                task['blocked_reason'] = 'dependency'


def record_hold(root, task, hold_id, operations=(), targets=()):
    normalized = []
    for target in targets:
        if target.startswith('file:'):
            normalized.append('file:' + relative(root, target[5:], exists=False))
        elif target.startswith('object:') and target[7:].strip():
            normalized.append(target)
        else:
            raise ValueError('Hold targets require file:relative/path or object:exact-id')
    if any(not value.strip() for value in operations):
        raise ValueError('Hold operations must be nonempty')
    task.setdefault('hold_records', {})[hold_id] = {
        'hold_id': hold_id, 'source_task_id': task['task_id'],
        'source_requirement_ids': sorted(requested_targets(task)),
        'operations': sorted(set(operations)), 'targets': sorted(set(normalized))}


def hold_release_evidence(root, task, hold_id, reference):
    if not reference:
        raise ValueError('Releasing a hold requires --user-release with the saved user instruction')
    path = relative(root, reference)
    message = json.loads((root / path).read_text(encoding='utf-8'))
    if (not isinstance(message, dict) or message.get('source') != 'user'
            or any(not isinstance(message.get(k), str) or not message[k].strip() for k in ('message_id', 'text'))
            or message.get('source_task_id') != task['task_id'] or message.get('hold_id') != hold_id):
        raise ValueError('Hold release requires the user message ID/text and matching source_task_id/hold_id')
    return {'evidence': snapshot(root, [path]), 'message': message}

def output_files(task):
    return {key: row['version'] for key, row in task['outputs'].items() if row['kind'] == 'file'}

DELETE_OPERATIONS = {'delete', 'remove', 'unlink'}

def deletion_targets(root, task, pending=None):
    """Requested, evidenced tombstones replace only their pinned input version."""
    deleted = set()
    for row in [*task.get('action_results', []), *([pending] if pending else [])]:
        requirement = {key: row.get(key) for key in ('target_kind', 'target_id', 'operation')}
        target = row.get('target_id')
        if (row.get('receipt_kind') != 'action' or row.get('result') != 'passed'
                or requirement not in task['required_actions']
                or row.get('target_kind') != 'file' or row.get('operation') not in DELETE_OPERATIONS
                or row.get('target_version') is not None
                or row.get('input_version') != task['consumed_inputs'].get(target)
                or changed(root, row.get('evidence', {}))):
            continue
        try:
            relative(root, target, exists=False)
            if not (root / target).exists() and not (root / target).is_symlink():
                deleted.add(target)
        except (OSError, ValueError, TypeError):
            continue
    return deleted

def input_changes(root, task, pending=None):
    # Only a declared in-place modification can replace its consumed source.
    replaced = output_files(task) if task['operation_kind'] == 'modify' else {}
    replaced = set(replaced) | deletion_targets(root, task, pending)
    immutable = {k: v for k, v in task['consumed_inputs'].items() if k not in replaced}
    return sorted(set(changed(root, immutable) + changed(root, task['read_dependencies'])))

def versions(task, output_ids=None, input_ids=None, include_actions=True):
    inputs = {**task['consumed_inputs'], **task['read_dependencies']}
    outputs = task['outputs']
    if input_ids is not None:
        inputs = {k: inputs[k] for k in input_ids}
    if output_ids is not None:
        outputs = {k: outputs[k] for k in output_ids}
    result = {'dependencies': selected_dependencies(task, output_ids), 'inputs': inputs, 'outputs': {k: {'kind': v['kind'], 'version': content_version(v), **({'definition_versions': v['definition_versions']} if v.get('definition_versions') else {}), **({'publication_group_id': v['publication_group_id']} if v.get('publication_group_id') else {})} for k, v in outputs.items()}}
    if include_actions and task.get('action_results'):
        result['actions'] = [{k: row[k] for k in ('target_kind', 'target_id', 'operation', 'result', 'evidence', 'at', 'target_version', *(['input_version'] if 'input_version' in row else []))} for row in task['action_results']]
    result['context_id'] = context_id(task)
    return result

def receipt_current(root, task, receipt, allow_failed=False):
    if context_changes(root, task):
        return False
    if receipt.get('review_kind') == 'worker-result' and not worker_receipt_current(root, task, receipt):
        return False
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
    if receipt.get('result') not in ({'passed', 'failed'} if allow_failed else {'passed'}) or changed(root, receipt.get('evidence', {})):
        return False
    try:
        captured = receipt['versions']
        replaced = set(output_files(task) if task['operation_kind'] == 'modify' else {}) | deletion_targets(root, task)
        reads = {k: v for k, v in captured['inputs'].items() if k not in replaced or k in task['read_dependencies']}
        files = {k: v['version'] for k, v in captured['outputs'].items() if v['kind'] == 'file'}
        return not changed(root, reads) and not changed(root, files) and captured == versions(task, receipt.get('output_ids'), receipt.get('input_ids'), include_actions=receipt.get('receipt_kind') != 'action')
    except KeyError:
        return False

def requested_targets(task):
    return {row['target'] for row in task['required_outputs']} | {row['target_id'] for row in task['required_actions']}

def normalize_checks(values, task):
    names, targets = [], {}
    for value in values:
        row = json.loads(value) if value.lstrip().startswith('{') else {'id': value, 'targets': None}
        if (not isinstance(row, dict) or set(row) != {'id', 'targets'}
                or not isinstance(row['id'], str) or not row['id'].strip()
                or row['targets'] is not None and (not isinstance(row['targets'], list) or not row['targets']
                    or any(not isinstance(v, str) or not v.strip() for v in row['targets'])
                    or len(set(row['targets'])) != len(row['targets'])
                    or set(row['targets']) - requested_targets(task))):
            raise ValueError('Required check needs an ID and requested target IDs')
        name = row['id']
        if name in targets and targets[name] != row['targets']:
            raise ValueError('Conflicting required check targets')
        if name not in targets:
            names.append(name)
            targets[name] = row['targets']
    return names, targets

def check_covered(root, task, check, targets=None, independent=None, receipts=None):
    """Union current receipts per check; output coverage never crosses checks."""
    selected = task.get('check_targets', {}).get(check)
    required = requested_targets(task) if selected is None else set(selected)
    if required - requested_targets(task):
        return False
    if targets is not None:
        required &= set(targets)
    if not required:
        return True
    latest = {}
    independent = task.get('independent_review', False) if independent is None else independent
    for receipt in task['check_receipts'].values() if receipts is None else receipts:
        if receipt.get('operation') != check or not receipt_current(root, task, receipt, allow_failed=True):
            continue
        if independent and not independent_receipt_current(root, task, receipt):
            continue
        covered = ((set(task['outputs']) | {r['target_id'] for r in task.get('action_results', [])})
                   if receipt.get('output_ids') is None else set(receipt['output_ids']))
        order = (receipt.get('sequence', 0), receipt.get('at', ''))
        for target in required & covered:
            if target not in latest or order >= latest[target][0]:
                latest[target] = (order, receipt)
    return all(target in latest and latest[target][1].get('result') == 'passed' for target in required)

def missing_checks(root, task):
    return [check for check in task['required_checks'] if not check_covered(root, task, check)]

def dependency_key(row):
    return json.dumps([row['producer_id'], row['output_id']], separators=(',', ':'))

def output_version(row):
    result = {'kind': row['kind'], 'content_version': content_version(row),
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
        value = {'kind': row['kind'], 'content_version': hashlib.sha256(json.dumps(actions, sort_keys=True).encode()).hexdigest(),
                 'definition_versions': {}}
    else:
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
    if not constraints_current(root, tasks, task) or input_changes(root, task) or context_changes(root, task):
        return False
    if row is None:
        if not consumed_current(root, tasks, task, seen):
            return False
        actions = [r for r in task.get('action_results', []) if r['target_id'] == output_id]
        return bool(actions) and all(receipt_current(root, task, r) for r in actions)
    if not constraints_current(root, tasks, task) or input_changes(root, task) or context_changes(root, task):
        return False
    if row['kind'] == 'file' and changed(root, {output_id: row['version']}):
        return False
    if row['kind'] in {'message', 'object'} and content_version(row) != row.get('version'):
        return False
    selected = selected_dependencies(task, [output_id]) or {}
    current = dependency_versions(tasks, task)
    if any(current.get(k) != v for k, v in selected.items()):
        return False
    for consumed in task.get('consumes', []):
        if dependency_key(consumed) in selected and not consumed_ref_current(root, tasks, consumed, seen):
            return False
    for check in task['required_checks']:
        if not check_covered(root, task, check, [output_id]):
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

def contract_snapshot(task):
    keys = ('required_outputs', 'required_actions', 'external_targets')
    if 'check_targets' in task:
        keys += ('required_checks', 'check_targets')
    return json.loads(json.dumps({key: task.get(key, []) for key in keys}))

def record_contract(task, source):
    revisions = task.setdefault('contract_revisions', [])
    snapshot = contract_snapshot(task)
    revisions.append({'revision': len(revisions) + 1, 'at': now(), 'contract': snapshot,
                      'sha256': content_hash(snapshot), 'source': source})

def contract_current(root, task):
    revisions = task.get('contract_revisions', [])
    if not revisions:
        return True  # Legacy stores predate revision history.
    try:
        return (revisions[-1]['contract'] == contract_snapshot(task)
                and all(row['revision'] == index + 1 and row['sha256'] == content_hash(row['contract'])
                        and not changed(root, row['source'].get('evidence', {}))
                        for index, row in enumerate(revisions)))
    except (KeyError, TypeError, ValueError, OSError):
        return False

def contract_change(root, task, outputs, actions, external_targets, user_change, checks=None):
    """Require version-bound user-change evidence before removing any obligation.

    The coordinator must compare its quotation and reference with the actual user
    message. Local JSON is retained evidence, not an authority authenticator.
    """
    if not contract_current(root, task):
        raise ValueError('Saved contract revision/evidence changed; reconcile the original records before changing requirements')
    previous = contract_snapshot(task)
    replacement = {'required_outputs': outputs, 'required_actions': actions,
                   'external_targets': external_targets}
    if 'check_targets' in task or checks is not None:
        provisional = {**task, **replacement}
        if checks is None:
            available = requested_targets(provisional)
            mapping = {name: (None if task.get('check_targets', {}).get(name) is None else
                             [target for target in task['check_targets'][name] if target in available])
                       for name in task['required_checks']}
            names = [name for name in task['required_checks'] if mapping[name] is None or mapping[name]]
            mapping = {name: mapping[name] for name in names}
        else:
            names, mapping = normalize_checks(checks, provisional)
        replacement.update(required_checks=names, check_targets=mapping)
    removed = any(row not in replacement[key] for key in ('required_outputs', 'required_actions', 'external_targets')
                  for row in previous[key])
    for check in task.get('required_checks', []):
        old_targets = task.get('check_targets', {}).get(check)
        old_targets = requested_targets(task) if old_targets is None else set(old_targets)
        new_targets = replacement.get('check_targets', {}).get(check)
        new_targets = requested_targets({**task, **replacement}) if new_targets is None else set(new_targets)
        removed |= check not in replacement.get('required_checks', task.get('required_checks', [])) or bool(old_targets - new_targets)
    source = {'kind': 'additive-change'}
    if removed and not user_change:
        raise ValueError('Removing or replacing requirements requires --user-change evidence of the user instruction')
    if user_change:
        source = user_change_evidence(root, user_change, previous, replacement, 'contract')
    if previous == replacement:
        return False
    if not task.get('contract_revisions'):
        record_contract(task, {'kind': 'legacy-retained'})
    task.update(replacement)
    record_contract(task, source)
    return True


def user_change_evidence(root, reference, previous, replacement, kind):
    reference = relative(root, reference)
    evidence = gate.parse_json((root / reference).read_bytes())
    if (not isinstance(evidence, dict) or evidence.get('source') != 'user'
            or any(not isinstance(evidence.get(key), str) or not evidence[key].strip()
                   for key in ('message_id', 'text'))
            or evidence.get('previous_' + kind + '_sha256') != content_hash(previous)
            or evidence.get('replacement_' + kind + '_sha256') != content_hash(replacement)):
        raise ValueError('User-change evidence needs the user message ID/text and matching previous/replacement ' + kind + ' hashes')
    return {'kind': 'user-change', 'evidence': snapshot(root, [reference]), 'message': evidence}

def missing_deliverables(root, task):
    if task.get('completion_contract') != 1:
        return ['explicit-completion-contract-required']
    if not contract_current(root, task):
        return ['contract-revision-or-evidence-changed']
    missing = []
    for requirement in task['required_outputs']:
        row = task['outputs'].get(requirement['target'], {})
        if (row.get('role') != requirement['role'] or row.get('kind') != requirement['kind']
                or not row.get('version') or content_version(row) != row.get('version')
                or (row.get('kind') == 'message' and (not isinstance(row.get('value'), str) or not row['value'].strip()))):
            missing.append(requirement['role'])
    for requirement in task['required_actions']:
        if not any(all(result.get(k) == v for k, v in requirement.items()) and receipt_current(root, task, result)
                   for result in task.get('action_results', [])):
            missing.append(dict(requirement))
    return missing

def completion_current(root, tasks, key):
    task = tasks[key]
    return (task['status'] == 'completed' and constraints_current(root, tasks, task) and not missing_deliverables(root, task)
            and not input_changes(root, task) and not context_changes(root, task) and not output_changes(root, task)
            and not missing_checks(root, task) and consumed_current(root, tasks, task))

def candidate(task):
    """Bind reviews to content, definitions, dependencies and the requested contract."""
    return json.loads(json.dumps({'versions': versions(task), 'task_id': task['task_id'],
        'owner': task['owner'], 'required_outputs': task['required_outputs'],
        'required_actions': task['required_actions'], 'required_checks': task['required_checks'],
        'context_id': context_id(task),
        **({'check_targets': task['check_targets']} if 'check_targets' in task else {})}))

def validate_worker_result(task, record):
    """Normalize the original worker return and validate its local evidence."""
    if not isinstance(record, dict):
        raise ValueError('Worker result must be a JSON object')
    strings = ('role', 'worker_id', 'launch_ref', 'return_ref', 'return_text', 'return_sha256')
    if any(not isinstance(record.get(key), str) or not record[key].strip() for key in strings):
        raise ValueError('Worker result requires role, worker ID, launch/return references and returned text/hash')
    if record['worker_id'] == task['owner'] or record['launch_ref'] == record['return_ref']:
        raise ValueError('Worker evidence must identify another worker and separate launch/return results')
    if record.get('execution_status') != 'completed':
        raise ValueError('Worker result must have a completed terminal execution status')
    if record['return_sha256'] != hashlib.sha256(record['return_text'].encode('utf-8')).hexdigest():
        raise ValueError('Worker returned text does not match its hash')
    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate key in structured worker return: ' + key)
            value[key] = item
        return value
    def reject_constant(value):
        raise ValueError('Nonfinite value in structured worker return: ' + value)
    try:
        original = json.loads(record['return_text'], object_pairs_hook=unique_pairs,
                              parse_constant=reject_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('Unstructured or malformed worker return cannot establish approval') from exc
    if not isinstance(original, dict):
        raise ValueError('Unstructured worker return cannot establish approval')
    if type(original.get('schema_version')) is not int or original['schema_version'] != 1:
        raise ValueError('Structured worker return requires schema_version 1')
    required = {'role', 'candidate_sha256', 'decision', 'findings', 'unassessed', 'errors', 'checks'}
    if not required <= set(original):
        raise ValueError('Structured worker return lacks decision, findings, checks or candidate binding')
    transport = {'worker_id', 'launch_ref', 'return_ref', 'execution_status',
                 'source_verification', 'return_text', 'return_sha256'}
    if {'return_text', 'return_sha256', 'normalized_return'} & set(original):
        raise ValueError('Structured worker return cannot include transport text/hash or normalized_return')
    if any(key in transport and key not in record for key in original):
        raise ValueError('Worker transport metadata must be supplied in the evidence envelope')
    for key, value in record.items():
        if key not in transport or key in original:
            if (key not in original or
                    json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) !=
                    json.dumps(original[key], sort_keys=True, ensure_ascii=False, allow_nan=False)):
                raise ValueError('Worker envelope differs from structured original: ' + key)
    record = {**{key: value for key, value in record.items() if key in transport}, **original,
              'normalized_return': original}
    if record.get('candidate_sha256') != content_hash(candidate(task)):
        raise ValueError('Worker result does not match the current candidate')
    if record.get('decision') not in {'pass', 'fail'}:
        raise ValueError('Worker result decision must be pass or fail')
    if any(not isinstance(record.get(key), list) for key in ('findings', 'unassessed', 'errors')):
        raise ValueError('Worker result requires findings, unassessed and errors arrays')
    if record['decision'] == 'pass' and any(record[key] for key in ('findings', 'unassessed', 'errors')):
        raise ValueError('Passing worker results cannot contain unresolved findings or gaps')
    checks = record.get('checks')
    if (not isinstance(checks, dict) or not checks or any(
            not isinstance(key, str) or not key.strip() or not isinstance(value, str) or not value.strip()
            for key, value in checks.items())):
        raise ValueError('Structured worker return requires named check statuses')
    if record['decision'] == 'pass' and (checks.get(record['role']) != 'passed'
                                       or any(value != 'passed' for value in checks.values())):
        raise ValueError('Passing worker result requires its named check and all reported checks passed')
    source = record.get('source_verification', {})
    if (not isinstance(source, dict) or source.get('status') not in {'matched-to-runtime', 'not-verified'}
            or source.get('status') == 'matched-to-runtime' and any(
                not isinstance(source.get(key), str) or not source[key].strip() for key in ('reference', 'verifier_id'))):
        raise ValueError('Worker result requires explicit runtime-source verification status and matching evidence')
    return record

def worker_receipt_current(root, task, receipt):
    try:
        if receipt.get('output_ids') is not None or receipt.get('input_ids') is not None:
            return False
        path = relative(root, receipt['worker_result_path'])
        record = json.loads((root / path).read_text(encoding='utf-8'))
        record = validate_worker_result(task, record)
        return (receipt.get('worker_result') == record
                and receipt.get('evidence', {}).get(path) == digest(root / path)
                and receipt.get('reviewer') == record['worker_id']
                and receipt.get('operation') == record['role']
                and receipt.get('result') == {'pass': 'passed', 'fail': 'failed'}[record['decision']])
    except (KeyError, TypeError, ValueError, OSError, RecursionError):
        return False

def worker_conflict(left, right):
    return (left['worker_id'] == right.get('worker_id')
            or bool({left['launch_ref'], left['return_ref']} & {right.get('launch_ref'), right.get('return_ref')}))

def independent_receipt_current(root, task, receipt):
    if receipt.get('review_kind') != 'worker-result' or not worker_receipt_current(root, task, receipt):
        return False
    record = receipt['worker_result']
    if record['source_verification']['status'] != 'matched-to-runtime':
        return False
    # Recheck on reads as well as registration; editing the store cannot make
    # one worker or one returned result count as distinct independent roles.
    for key, other in task['check_receipts'].items():
        if other == receipt or other.get('review_kind') != 'worker-result':
            continue
        other_record = other.get('worker_result', {})
        if worker_conflict(record, other_record):
            return False
    return True

def stages(root, tasks, key):
    """Derived stages never change scheduling/completion/dependency semantics."""
    task = tasks[key]
    current = (constraints_current(root, tasks, task) and not missing_deliverables(root, task)
               and not input_changes(root, task) and not context_changes(root, task) and not output_changes(root, task)
               and consumed_current(root, tasks, task))
    receipts = list(task['check_receipts'].values())
    valid = [r for r in receipts if 'candidate' in r and receipt_current(root, task, r, allow_failed=True)]
    independent = [r for r in valid if independent_receipt_current(root, task, r)]
    self_checks = [r for r in valid if r not in independent]
    def covers(receipts):
        covered = set().union(*(set(task['outputs']) if r.get('output_ids') is None else set(r['output_ids']) for r in receipts)) if receipts else set()
        return bool(receipts) and not (set(task['outputs']) - covered) and all(check_covered(root, task, check, independent=False, receipts=receipts)
                                     for check in task['required_checks'])
    reviewed = bool(current and covers(independent))
    return {'completed': completion_current(root, tasks, key), 'reviewed': reviewed,
            'self_checked': bool(current and covers(self_checks)),
            'review_source': 'worker-result-evidence' if reviewed else None,
            'missing_independent_checks': [check for check in task['required_checks']
                                          if not check_covered(root, task, check, independent=True)]}


def migrate(state):
    if state.get('version') in {4, 5}:
        # Retired publication records have no role in local review or completion.
        obsolete = ('gate_review', 'gate_release', 'released', 'publication_id',
                    'publication_kind', 'stages')
        for task in state['tasks'].values():
            for record in [task, *task.get('history', [])]:
                for field in obsolete:
                    record.pop(field, None)
        state['version'] = 5
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
        migrate(state)
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
        if not constraints_current(root, state['tasks'], task):
            stale.add(key)
            findings.append({'task': key, 'kind': 'effective-parent-constraints',
                             'holds': task.get('effective_holds', []), 'scope_errors': task.get('constraint_errors', [])})
        paths = input_changes(root, task) + output_changes(root, task) + context_changes(root, task)
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
    add.add_argument('--task-context', help='Existing JSON context with request, instruction and adopted-decision versions')
    add.add_argument('--operation-kind', choices=['answer', 'modify', 'create', 'external'], default='create')
    add.add_argument('--read-dependency', action='append', default=[])
    add.add_argument('--required-check', action='append', default=[])
    add.add_argument('--required-output', action='append', default=[], help='JSON: role, kind, target')
    add.add_argument('--required-action', action='append', default=[], help='JSON: target_kind, target_id, operation')
    add.add_argument('--external-target', action='append', default=[], help='Exact external object ID; not a file path')
    add.add_argument('--authority', default='')
    add.add_argument('--hold', action='append', default=[])
    add.add_argument('--hold-operation', action='append', default=[])
    add.add_argument('--hold-target', action='append', default=[])
    add.add_argument('--input', action='append', default=[])
    add.add_argument('--scope', action='append', default=[])
    add.add_argument('--after', action='append', default=[])
    add.add_argument('--consumes', action='append', default=[], help='JSON consumed-output version contract')
    add.add_argument('--parent')
    add.add_argument('--next', required=True)
    add.add_argument('--independent-review', action='store_true')
    for command in ['start', 'resume', 'set-context', 'bind-writing', 'release-hold', 'set-contract', 'action', 'requeue', 'output', 'verify', 'usage', 'transition']:
        cli = sub.add_parser(command)
        cli.add_argument('id')
        if command == 'bind-writing':
            cli.add_argument('--paragraph-state', required=True, help='Saved ParagraphRun state; binds content and dependency versions')
        elif command == 'set-context':
            cli.add_argument('--task-context', required=True)
            cli.add_argument('--user-change', help='Existing user instruction and old/new context hashes authorizing a binding change')
            cli.add_argument('--decision-update', action='append', default=[], help='JSON: decision_id, reason, evidence paths for a revised delegated choice')
        elif command in {'start', 'resume'}:
            cli.add_argument('--task-context', help='Current context to compare with the saved governing version')
        elif command == 'set-contract':
            cli.add_argument('--required-output', action='append', default=[])
            cli.add_argument('--required-action', action='append', default=[])
            cli.add_argument('--external-target', action='append', default=[])
            cli.add_argument('--required-check', action='append', help='Replacement check IDs or explicit target records; omitted preserves checks on retained targets')
            cli.add_argument('--user-change', help='Saved user message with old/new contract hashes authorizing removed or replaced requirements')
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
            cli.add_argument('--user-release', help='Saved user instruction with source_task_id and hold_id')
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
            cli.add_argument('--worker-result', help='Saved candidate-bound terminal worker result and runtime-source match record')
            cli.add_argument('--check', default='legacy-verification')
            cli.add_argument('--output', action='append')
            cli.add_argument('--input', action='append')
            cli.add_argument('--result', choices=['passed', 'failed'], help='Required for self-checks; worker results derive this from their returned decision')
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
            cli.add_argument('--hold-operation', action='append', default=[])
            cli.add_argument('--hold-target', action='append', default=[])
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
            state = {'version': 5, 'created': now(), 'limits': limits, 'limit_sources': {k: 'explicit' if v is not None else 'unset' for k, v in limits.items()}, 'tasks': {}}
        else:
            state = json.loads(path.read_text(encoding='utf-8'))
            migrate(state)
        tasks = state['tasks']
        refresh_constraints(root, tasks)
        if args.command == 'add':
            if args.id in tasks or not args.id.strip():
                raise ValueError('Task ID must be new and nonempty')
            depth = 0
            parent = args.parent
            while parent:
                depth += 1
                parent = tasks[parent]['parent']
            if (args.hold_operation or args.hold_target) and not args.hold:
                raise ValueError('Hold selectors require at least one hold ID')
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
            if args.task_context:
                tasks[args.id]['task_context'], tasks[args.id]['task_context_ref'] = load_task_context(root, args.task_context)
                record_context(tasks[args.id], {'kind': 'initial-declaration'})
            elif args.parent and tasks[args.parent].get('task_context') is not None:
                tasks[args.id]['task_context_inherited_from'] = args.parent
                for key in ('task_context', 'task_context_ref'):
                    if key in tasks[args.parent]:
                        tasks[args.id][key] = json.loads(json.dumps(tasks[args.parent][key]))
            if args.parent and not args.authority:
                tasks[args.id]['authority'] = tasks[args.parent].get('authority', '')
            if effective_constraints(tasks, tasks[args.id])['scope_errors']:
                raise ValueError('Child scope or external targets exceed ancestor authority')
            for hold_id in args.hold:
                record_hold(root, tasks[args.id], hold_id, args.hold_operation, args.hold_target)
            tasks[args.id]['required_checks'], tasks[args.id]['check_targets'] = normalize_checks(args.required_check, tasks[args.id])
            record_contract(tasks[args.id], {'kind': 'initial-declaration'})
        elif hasattr(args, 'id'):
            task = tasks[args.id]
            if args.command == 'bind-writing':
                bind_paragraph_state(root, task, args.paragraph_state)
            elif args.command == 'set-context':
                if task['status'] == 'running':
                    raise ValueError('Stop the active task before changing its governing context')
                value, reference = load_task_context(root, args.task_context)
                before = context_id(task)
                transition(task, task['status'], task['next'], task.get('blocked_reason'))
                context_change(root, task, value, args.user_change, args.decision_update)
                task['task_context_ref'] = reference
                task.pop('task_context_inherited_from', None)
                if context_id(task) != before:
                    task['check_receipts'], task['verification'] = {}, None
                    if task['status'] == 'completed':
                        transition(task, 'blocked', 'Recheck changed context against preserved outputs; reuse unchanged computations', 'interrupted')
            elif args.command == 'set-contract':
                if task['status'] not in {'queued', 'blocked', 'failed'}:
                    raise ValueError('Set contract requires queued, blocked or failed state')
                outputs, actions = contract(root, args.required_output, args.required_action)
                if any(not v.strip() for v in args.external_target):
                    raise ValueError('External target IDs must be nonempty')
                contract_change(root, task, outputs, actions, list(dict.fromkeys(args.external_target)), args.user_change, args.required_check)
                task['completion_contract'] = 1
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
                    raise ValueError('Unknown local hold ID; an inherited hold must be released at its source task')
                evidence = hold_release_evidence(root, task, args.hold_id, args.user_release)
                prior_reason = task.get('blocked_reason', 'interrupted')
                transition(task, 'blocked', args.next, prior_reason)
                task['holds'].remove(args.hold_id)
                task.setdefault('hold_releases', []).append({'hold_id': args.hold_id, 'source_task_id': task['task_id'],
                                                             'authority': args.authority, 'at': now(), **evidence})
                if not task['holds']:
                    task['blocked_reason'] = 'interrupted'
            elif args.command in {'start', 'resume'}:
                if args.task_context:
                    value, reference = load_task_context(root, args.task_context)
                    proposed = {**task, 'task_context': value}
                    if context_id(proposed) != context_id(task):
                        raise ValueError('Current task_context differs; register the authorized change with set-context')
                    task['task_context'], task['task_context_ref'] = value, reference
                if context_changes(root, task):
                    raise ValueError('Governing context or record content changed; preserve outputs and reconcile its version before resuming')
                if args.command == 'start' and task['status'] != 'queued':
                    raise ValueError('Start requires queued state')
                if args.command == 'resume' and task['status'] != 'blocked':
                    raise ValueError('Resume requires blocked state')
                if task['operation_kind'] == 'external' and not task.get('external_targets'):
                    raise ValueError('External operations require assigned external object IDs')
                if task['operation_kind'] in {'create', 'modify'} and not task['scope']:
                    raise ValueError('Writing operations require an assigned write scope')
                if not constraints_current(root, tasks, task) or task.get('blocked_reason') in {'permission', 'user_hold'}:
                    raise ValueError('Resolve the saved permission or user hold before resuming')
                limit = state['limits'].get('max_attempts')
                if args.command == 'start' and limit and task['attempts'] >= limit:
                    raise ValueError('Explicit attempt budget reached; review that budget before another run')
                if input_changes(root, task) or output_changes(root, task):
                    raise ValueError('Inputs or outputs changed; inspect and requeue the affected task')
                if args.command == 'start' and any(tasks[key]['status'] != 'completed' for key in task['after']):
                    raise ValueError('Dependency is incomplete or stale')
                active = [t for t in tasks.values() if t['status'] == 'running']
                if state['limits'].get('max_active') is not None and len(active) >= state['limits']['max_active']:
                    raise ValueError('Active worker limit')
                for other in active:
                    if set(task.get('external_targets', [])) & set(other.get('external_targets', [])):
                        raise ValueError('External target overlaps an active task')
                    if any(scopes_overlap(a, b) for a in task['scope'] for b in other['scope']):
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
                if not constraints_current(root, tasks, task) or task.get('blocked_reason') in {'permission', 'user_hold'}:
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
                selected.update(output_changes(root, task))
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
                    row = {'kind': args.kind, 'version': content_hash(value), 'value': value}
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
                target_output = task['outputs'].get(target, {})
                if args.target_kind == 'file':
                    if (root / target).is_file():
                        target_version = digest(root / target)
                    elif not (root / target).exists() and args.operation in DELETE_OPERATIONS:
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
                outcome = None
                if args.target_kind == 'object' and args.result == 'passed':
                    # Reuse the native return adapters: a caller's verdict and an
                    # existing log file do not establish a completed remote action.
                    evidence_path = relative(root, args.evidence)
                    observed = gate.parse_json((root / evidence_path).read_bytes())
                    if not isinstance(observed, dict):
                        raise ValueError('External action evidence must contain its returned tool record')
                    spec = importlib.util.spec_from_file_location('state_operation_results', _base / 'native_check.py')
                    native = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(native)
                    event = {'event_id': observed.get('event_id'), 'operation': args.operation,
                             'target': target, 'status': 'success'}
                    outcomes = []
                    native._operation_results({'action_results_verified': [observed]}, [event], outcomes)
                    outcome = outcomes[0]
                    returned_version = outcome.get('commit_sha') or outcome.get('release_id')
                    if args.target_version and returned_version and args.target_version != returned_version:
                        raise ValueError('External target version differs from the returned commit or release')
                result = {**requirement, 'result': args.result, 'evidence': snapshot(root, [args.evidence]),
                          'target_version': target_version, 'target_output_version': target_output.get('version'),
                          'input_version': task['consumed_inputs'].get(target),
                          'output_ids': selected, 'at': now(), 'receipt_kind': 'action',
                          'versions': versions(task, selected, include_actions=False)}
                if outcome is not None:
                    result['operation_outcome'] = outcome
                if input_changes(root, task, result) or output_changes(root, task):
                    raise ValueError('Action result requires unchanged inputs and current outputs')
                task['action_results'] = [r for r in task['action_results'] if any(r[k] != v for k, v in requirement.items())] + [result]
            elif args.command == 'verify':
                if task['status'] != 'running':
                    raise ValueError('Verification requires running state; resume preserved outputs first')
                if not args.reviewer.strip():
                    raise ValueError('Reviewer must be nonempty')
                if task['independent_review'] and not args.worker_result:
                    raise ValueError('Independent review requires --worker-result evidence, not a caller-supplied name/verdict')
                if not (task['outputs'] or task.get('action_results')) or input_changes(root, task) or context_changes(root, task) or output_changes(root, task):
                    raise ValueError('Check requires registered results and unchanged external inputs')
                for selected, allowed in [(args.output, task['outputs']), (args.input, {**task['consumed_inputs'], **task['read_dependencies']})]:
                    if selected is not None and (len(set(selected)) != len(selected) or set(selected) - set(allowed)):
                        raise ValueError('Check selectors must name distinct registered inputs or outputs')
                args.output = sorted(args.output) if args.output is not None else None
                args.input = sorted(args.input) if args.input is not None else None
                result, review_kind, worker = args.result, 'self-check', None
                evidence_paths = [args.evidence] if args.evidence else []
                if args.worker_result:
                    if args.output is not None or args.input is not None:
                        raise ValueError('Worker results must review the entire candidate; --input/--output selectors are only for self-checks')
                    worker_path = relative(root, args.worker_result)
                    worker = json.loads((root / worker_path).read_text(encoding='utf-8'))
                    worker = validate_worker_result(task, worker)
                    if worker['worker_id'] != args.reviewer or worker['role'] != args.check:
                        raise ValueError('Worker result role and identity must match the registered check')
                    if task['independent_review'] and worker['source_verification']['status'] != 'matched-to-runtime':
                        raise ValueError('Independent review requires evidence matched to actual runtime launch/return results')
                    for key, other in task['check_receipts'].items():
                        if key != args.check and other.get('review_kind') == 'worker-result' and worker_conflict(worker, other.get('worker_result', {})):
                            raise ValueError('Independent checks require distinct worker IDs, launches and returned results')
                    result = {'pass': 'passed', 'fail': 'failed'}[worker['decision']]
                    if args.result is not None and args.result != result:
                        raise ValueError('Caller verdict conflicts with the returned worker decision')
                    review_kind = 'worker-result'
                    evidence_paths.append(worker_path)
                elif result is None:
                    raise ValueError('Self-checks require an explicit --result')
                receipt = {'operation': args.check, 'result': result, 'reviewer': args.reviewer,
                    'review_kind': review_kind, 'evidence': snapshot(root, evidence_paths), 'at': now(),
                    'sequence': 1 + max((row.get('sequence', 0) for row in task['check_receipts'].values()), default=0),
                    'output_ids': args.output, 'input_ids': args.input, 'versions': versions(task, args.output, args.input),
                    'candidate': candidate(task)}
                if worker is not None:
                    receipt.update(worker_result_path=worker_path, worker_result=worker)
                key = next((key for key, old in task['check_receipts'].items()
                            if old.get('operation') == args.check
                            and old.get('output_ids') == args.output and old.get('input_ids') == args.input), None)
                if key is None:
                    key, ordinal = args.check, 1
                    while key in task['check_receipts']:
                        key, ordinal = args.check + ':' + str(ordinal), ordinal + 1
                task['check_receipts'][key] = receipt
                task['verification'] = receipt
            elif args.command == 'transition':
                status = {'evaluating': 'running', 'interrupted': 'blocked'}.get(args.status, args.status)
                allowed = {'running': {'running', 'completed', 'blocked', 'failed'},
                           'queued': {'blocked', 'failed'}, 'blocked': {'blocked', 'failed'}}
                if status not in allowed.get(task['status'], set()):
                    raise ValueError('Invalid transition')
                if status == 'completed' and (not constraints_current(root, tasks, task) or missing_deliverables(root, task) or missing_checks(root, task) or not consumed_current(root, tasks, task) or input_changes(root, task) or context_changes(root, task) or output_changes(root, task)):
                    raise ValueError('Completion requires matching requested outputs/actions, current versions/check receipts and completed dependencies')
                if status in {'blocked', 'failed'} and not args.next:
                    raise ValueError('Save the next authorized action for an unfinished task')
                if status == 'blocked' and args.reason in {'permission', 'user_hold'}:
                    if not args.hold_id or not args.hold_id.strip():
                        raise ValueError('Permission/user hold requires an explicit --hold-id')
                    if args.hold_id not in task['holds']:
                        task['holds'].append(args.hold_id)
                        record_hold(root, task, args.hold_id, args.hold_operation, args.hold_target)
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
        refresh_constraints(root, tasks)
        if args.command == 'inspect':
            findings, stale = inspect(root, state, args.stale_seconds)
            if args.invalidate:
                for key in sorted(stale):
                    if tasks[key]['status'] in {'running', 'completed'}:
                        transition(tasks[key], 'blocked', 'Inspect changed dependencies; preserve current outputs and rerun only affected operations', 'dependency')
            output = {'findings': findings, 'affected_tasks': sorted(stale),
                      'stages': {key: stages(root, tasks, key) for key in tasks}}
        elif args.command == 'summary':
            output = report_usage(state)
        elif args.command == 'show':
            if args.task_id is not None and args.task_id not in tasks:
                raise ValueError(f'Unknown task ID: {args.task_id}')
            output = json.loads(json.dumps(tasks[args.task_id] if args.task_id is not None else state))
            if args.task_id is not None:
                output['stages'] = stages(root, tasks, args.task_id)
                output['context_id'] = context_id(tasks[args.task_id])
            else:
                for key in tasks:
                    output['tasks'][key]['stages'] = stages(root, tasks, key)
                    output['tasks'][key]['context_id'] = context_id(tasks[key])
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
