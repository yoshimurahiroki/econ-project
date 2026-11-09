#!/usr/bin/env python3
"""Preserve research task state, authority and actual operation results."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
import os
import re
import uuid
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlencode

if __name__ == '__main__':
    sys.dont_write_bytecode = True

_base = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('state_local_io', next(p for p in
    (_base / 'local_checks.py', _base / 'LOCAL_CHECKS.py') if p.is_file()))
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

STATES = {'queued', 'running', 'blocked', 'completed', 'failed'}
TOKEN_FIELDS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens')
_FILE_DIGESTS = {}

def now():
    return datetime.now(timezone.utc).isoformat()

def file_identity(path):
    info = Path(path).stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns

def digest(path):
    """Reuse unchanged file bytes within this process; detect concurrent changes."""
    path = Path(path).resolve(strict=True)
    before = file_identity(path)
    cached = _FILE_DIGESTS.get(path)
    if cached is not None and cached[0] == before:
        return cached[1]
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    if file_identity(path) != before:
        raise ValueError('File changed while reading: ' + str(path))
    result = value.hexdigest()
    _FILE_DIGESTS[path] = before, result
    return result

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

def save(path, state, *, indent=2):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(state, stream, ensure_ascii=False, indent=indent, sort_keys=True, allow_nan=False,
                      separators=(',', ':') if indent is None else None)
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
    if task.get('specification') is not None:
        value['specification'] = task['specification']
    if task.get('project_binding') is not None:
        value['project_binding'] = task['project_binding']
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
                or set(row) - {'decision_id', 'version', 'choice', 'reason', 'switch_condition', 'change_authority', 'references'}
                or row.get('change_authority', 'fixed') not in {'fixed', 'delegated'}
                or any(not isinstance(row[k], str) or not row[k].strip()
                       for k in ('decision_id', 'choice', 'reason', 'switch_condition'))
                or not (isinstance(row['version'], str) and row['version'].strip()
                        or type(row['version']) is int and row['version'] >= 0)
                or row['decision_id'] in seen):
            raise ValueError('Adopted decision requires a unique ID, version, choice, reason and switch condition')
        seen.add(row['decision_id'])
        if 'references' in row:
            if not isinstance(row['references'], list):
                raise ValueError('Decision references must be an array')
            argument = _project_argument()
            for reference in row['references']:
                argument.reference_contract(reference)
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
    if task.get('project_binding') is not None or task.get('project_history') or task.get('project_baseline'):
        try:
            _project_integrity(root, task)
        except (ValueError, OSError, KeyError, TypeError):
            changes.append('project-binding-or-source-changed')
    spec = task.get('specification')
    if spec and (changed(root, {spec['requirements']['path']: spec['requirements']['sha256'],
                               spec['request']['path']: spec['request']['sha256']})
                 or any(changed(root, row.get('source', {}).get('evidence', {}))
                        for row in task.get('specification_revisions', []))):
        changes.append('specification-or-evidence-changed')
    return changes


def transition(task, status, next_action=None, reason=None):
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
    if receipt.get('advanced_bindings') and any(changed(root, item['code_hashes']) for item in receipt['advanced_bindings']):
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


def completion_acceptance_id(request_sha256, owners):
    """Identify the complete declared scope; its digest alone grants no approval."""
    return content_hash({'request_sha256': request_sha256, 'owners': [
        {'operation_kind': owner['operation_kind'], 'context_id': context_id(owner)} for owner in owners]})

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
    return missing_required_results(task, lambda result: receipt_current(root, task, result), root=root)


def missing_required_results(task, action_current, *, root=None, final_message=None):
    """One output/action predicate for stored tasks and request-bound hook results."""
    missing, current_files = [], {}
    for requirement in task['required_outputs']:
        row = task['outputs'].get(requirement['target'], {})
        invalid = (row.get('role') != requirement['role'] or row.get('kind') != requirement['kind']
                or not row.get('version') or content_version(row) != row.get('version')
                or (row.get('kind') == 'message' and (not isinstance(row.get('value'), str) or not row['value'].strip())))
        if not invalid and requirement['kind'] == 'file':
            try:
                if root is None:
                    raise ValueError('current file verification requires its task root')
                value = gate.file_snapshot(root / relative(root, requirement['target']))
                invalid = value.sha256 != row['version']
                current_files[requirement['target']] = value
            except (OSError, ValueError):
                invalid = True
        if invalid:
            missing.append(requirement['role'])
    for requirement in task['required_actions']:
        if not any(all(result.get(k) == v for k, v in requirement.items()) and action_current(result)
                   for result in task.get('action_results', [])):
            missing.append(dict(requirement))
    if task.get('specification'):
        if root is None:
            missing.append('bound-specification-requires-current-root')
        else:
            try:
                specification, request = _spec_inputs(root, task)
                evaluator = _native().requirements
                requirements = evaluator.validate_contract(specification, request)
                artifacts, evidence = {}, {}
                for requirement in requirements:
                    if requirement['kind'] != 'artifact':
                        continue
                    path = requirement['path']
                    row = task['outputs'].get(path, {})
                    if row.get('kind') != 'file' or not row.get('version'):
                        continue
                    try:
                        data = current_files.get(path)
                        if data is None:
                            data = gate.file_snapshot(root / relative(root, path))
                        if data.sha256 == row['version']:
                            artifacts[path] = data
                    except (OSError, ValueError):
                        pass
                context = task.get('task_context') or {}
                source_pins = {row['path']: row['content_sha256']
                               for field in ('request_refs', 'active_instruction_refs')
                               for row in context.get(field, []) if row.get('path')}
                pins = {**{path: version for path, version in task.get('consumed_inputs', {}).items()
                           if path not in artifacts}, **source_pins, **task.get('read_dependencies', {})}
                for requirement in requirements:
                    for ref in requirement.get('evidence_refs', []):
                        path = ref['path']
                        if path in evidence:
                            continue
                        try:
                            data = artifacts.get(path)
                            if data is None:
                                data = gate.file_snapshot(root / relative(root, path))
                            expected = pins.get(path)
                            if expected is None or data.sha256 == expected:
                                evidence[path] = data
                        except (OSError, ValueError):
                            pass
                candidate = None
                if final_message is not None:
                    if not isinstance(final_message, str):
                        raise ValueError('final message must contain the actual text')
                    candidate = final_message.encode('utf-8')
                elif any(row.get('target') == 'message://final' for row in requirements):
                    messages = [task['outputs'].get(row['target'], {}) for row in task['required_outputs']
                                if row['kind'] == 'message']
                    if any(row['kind'] == 'message' and row['target'] == 'message://final'
                           for row in task['required_outputs']):
                        messages = [task['outputs'].get('message://final', {})]
                    values = {row['value'] for row in messages if row.get('kind') == 'message'
                              and isinstance(row.get('value'), str) and row.get('version')
                              and content_version(row) == row['version']}
                    if len(values) == 1:
                        candidate = next(iter(values)).encode('utf-8')
                actions = [{'operation': row['operation'], 'target': row['target_id'],
                            'status': 'success' if row.get('result') == 'passed' and action_current(row)
                            else 'unverified'} for row in task.get('action_results', [])]
                missing.extend(evaluator.missing_requirements(specification, request, artifacts, actions,
                               candidate_bytes=candidate, evidence=evidence))
            except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError) as exc:
                missing.append({'requirement_id': 'specification', 'message': str(exc)})
    return missing

def completion_current(root, tasks, key):
    task = tasks[key]
    return (task['status'] == 'completed' and constraints_current(root, tasks, task) and not missing_deliverables(root, task)
            and not input_changes(root, task) and not context_changes(root, task) and not output_changes(root, task)
            and not missing_checks(root, task) and consumed_current(root, tasks, task))

def _native():
    spec = importlib.util.spec_from_file_location('state_advanced_native', _base / 'native_check.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_specification(root, contract_path, request_path):
    contract_path, request_path = relative(root, contract_path), relative(root, request_path)
    contract_bytes, request_bytes = (root / contract_path).read_bytes(), (root / request_path).read_bytes()
    native = _native()
    value = gate.parse_json(contract_bytes)
    native.requirements.validate_contract(value, request_bytes)
    return {'requirements': {'path': contract_path, 'sha256': gate.sha(contract_bytes)},
            'request': {'path': request_path, 'sha256': gate.sha(request_bytes)}}


def bind_specification(root, task, contract_path, request_path, user_change=None):
    if task['status'] not in {'queued', 'blocked', 'failed'}:
        raise ValueError('Specification can be bound only to queued, blocked or failed tasks')
    new = load_specification(root, contract_path, request_path)
    old = task.get('specification')
    if old == new:
        return
    if old is not None and not user_change:
        raise ValueError('Replacing a specification requires user-change evidence')
    source = {'kind': 'initial-declaration'} if old is None else user_change_evidence(root, user_change, old, new, 'specification')
    revisions = task.setdefault('specification_revisions', [])
    if old is not None and not revisions:
        revisions.append({'specification': old, 'source': {'kind': 'previous-binding'}})
    revisions.append({'specification': new, 'source': source})
    task['specification'] = new
    task['check_receipts'], task['verification'] = {}, None


def _spec_inputs(root, task):
    spec = task['specification']
    contract = gate.regular_bytes(root / relative(root, spec['requirements']['path']))
    request = gate.regular_bytes(root / relative(root, spec['request']['path']))
    if gate.sha(contract) != spec['requirements']['sha256'] or gate.sha(request) != spec['request']['sha256']:
        raise ValueError('Specification or request bytes differ from the pinned binding')
    return gate.parse_json(contract), request


def _descendants(tasks, owner):
    return {key: task for key, task in tasks.items() if not task.get('repair_for') and
            (key == owner['task_id'] or any(a['task_id'] == owner['task_id'] for a in task_ancestors(tasks, task)))}


def _code_files(root, rows):
    files = {}
    for path in sorted({p for row in rows for p in row['code_paths']}):
        try:
            path = relative(root, path)
            files[path] = (root / path).read_bytes()
        except (ValueError, OSError):
            pass
    return files


def advanced_bindings(root, tasks, task, check):
    bindings = []
    for owner in tasks.values():
        if not owner.get('specification') or task['task_id'] not in _descendants(tasks, owner):
            continue
        value, _ = _spec_inputs(root, owner)
        selected = [row for row in value.get('traceability', []) if task['task_id'] in row['task_ids'] and check in row['check_ids']]
        if selected:
            code = _code_files(root, selected)
            paths = {p for row in selected for p in row['code_paths']}
            if set(code) != paths:
                raise ValueError('Mapped code must exist before importing its verification proof')
            commands = {row['check_commands'].get(check) for row in selected}
            if len(commands) != 1:
                raise ValueError('Mapped check has conflicting command pins')
            bindings.append({'owner': owner['task_id'], 'specification': owner['specification'],
                             'check_command': next(iter(commands)),
                             'code_hashes': {p: gate.sha(v) for p, v in code.items()}})
    return bindings


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
    """Expose completion and an explicitly selected independent certification."""
    task = tasks[key]
    completed = completion_current(root, tasks, key)
    if not task.get('independent_review'):
        return {'completed': completed}
    current = (constraints_current(root, tasks, task) and not missing_deliverables(root, task)
               and not input_changes(root, task) and not context_changes(root, task) and not output_changes(root, task)
               and consumed_current(root, tasks, task))
    receipts = [r for r in task['check_receipts'].values()
                if 'candidate' in r and receipt_current(root, task, r, allow_failed=True)
                and independent_receipt_current(root, task, r)]
    covered = set().union(*(set(task['outputs']) if r.get('output_ids') is None else set(r['output_ids'])
                            for r in receipts)) if receipts else set()
    missing = [check for check in task['required_checks']
               if not check_covered(root, task, check, independent=True)]
    reviewed = bool(current and receipts and not (set(task['outputs']) - covered) and not missing)
    return {'completed': completed, 'reviewed': reviewed,
            'review_source': 'worker-result-evidence' if reviewed else None,
            'missing_independent_checks': missing}


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
        task['required_checks'], task['check_receipts'] = [], {}
        task['authority'], task['holds'], task['next_action'] = task.get('authority', {}), task.get('holds', []), task['next']
        if task['status'] == 'evaluating':
            task['status'] = 'running'
        elif task['status'] in {'completed', 'interrupted'}:
            task['status'], task['blocked_reason'] = 'blocked', 'interrupted'
            task['next'] = task['next_action'] = 'Reconcile the requested outputs and actual operation returns with preserved research results'
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

def find_tasks(state, query, *, limit=5, offset=0, status=None, owner=None, parent=None):
    """Locate recorded evidence; current applicability remains a resume/show check."""
    terms = tuple(dict.fromkeys(query.casefold().split()))
    if not terms or limit < 1 or offset < 0:
        raise ValueError('Find requires a nonempty query, positive limit and nonnegative offset')
    if parent is not None and parent not in state['tasks']:
        raise ValueError(f'Unknown parent task ID: {parent}')

    def pointer(parts):
        return '/' + '/'.join(str(part).replace('~', '~0').replace('/', '~1') for part in parts)

    def texts(value, parts):
        if isinstance(value, str):
            yield parts, 'value', value
        elif isinstance(value, dict):
            for key, item in value.items():
                # Output/evidence paths can be dictionary keys, not string values.
                yield (*parts, key), 'key', key
                yield from texts(item, (*parts, key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from texts(item, (*parts, index))

    def excerpt(text):
        folded = text.casefold()
        at = min((folded.index(term) for term in terms if term in folded), default=0)
        # Case folding may expand a character; keep the excerpt around the actual match.
        if len(folded) != len(text):
            consumed = 0
            for index, char in enumerate(text):
                if consumed >= at:
                    at = index
                    break
                consumed += len(char.casefold())
        start = max(0, at - 60)
        end = min(len(text), start + 240)
        return {'excerpt': text[start:end], 'excerpt_truncated': start > 0 or end < len(text)}

    fields = ('task_id', 'owner', 'parent', 'status', 'next', 'record', 'scope', 'external_targets',
              'authority', 'holds', 'blocked_reason',
              'task_context', 'task_context_ref', 'inputs', 'read_dependencies', 'consumes',
              'outputs', 'required_outputs', 'required_actions', 'action_results', 'check_receipts',
              'verification', 'writing_state', 'history', 'context_revisions', 'contract_revisions')
    rows = []
    total = 0
    for key, task in sorted(state['tasks'].items()):
        if ((status is not None and task['status'] != status)
                or (owner is not None and task['owner'] != owner)
                or (parent is not None and task.get('parent') != parent)):
            continue
        seen, matches, additional, count = set(), [], [], 0
        for field in fields:
            for parts, location, text in texts(task.get(field), ('tasks', key, field)):
                found = {term for term in terms if term in text.casefold()}
                if not found:
                    continue
                count += 1
                if found - seen and len(matches) < 3:
                    matches.append({'pointer': pointer(parts), 'location': location, **excerpt(text)})
                elif len(additional) < 3:
                    additional.append({'pointer': pointer(parts), 'location': location, **excerpt(text)})
                seen.update(found)
        if len(seen) != len(terms):
            continue
        total += 1
        if not offset < total <= offset + limit:
            continue
        matches += additional[:3 - len(matches)]
        base = ('tasks', key)
        refs = {field: pointer((*base, field)) for field in
                ('record', 'task_context_ref', 'outputs', 'action_results') if task.get(field)}
        if task.get('task_context') is not None:
            refs.update({field: pointer((*base, 'task_context', field)) for field in
                         ('request_refs', 'active_instruction_refs', 'adopted_decisions')})
        rows.append({'task_id': key, 'recorded_status': task['status'], 'owner': task['owner'],
                     'parent': task.get('parent'), 'pointer': pointer(base), 'references': refs,
                     'matches': matches, 'match_count': count, 'matches_omitted': count - len(matches)})
    return {'query': query, 'view': 'recorded-locators', 'total': total, 'offset': offset, 'limit': limit,
            'next_offset': offset + len(rows) if offset + len(rows) < total else None, 'tasks': rows}

def usage_counter(value, aliases=None):
    if not isinstance(value, dict):
        raise ValueError('Usage counters must be an object')
    aliases = aliases or {field: field for field in TOKEN_FIELDS}
    result = {field: value.get(aliases[field]) for field in TOKEN_FIELDS}
    if any(v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 0) for v in result.values()):
        raise ValueError('Invalid token counter')
    for part, total in [('cached_input_tokens', 'input_tokens'), ('reasoning_output_tokens', 'output_tokens')]:
        if result[part] is not None and result[total] is not None and result[part] > result[total]:
            raise ValueError('Token detail exceeds its reported total')
    return result


def usage_operation(value):
    """Retain typed operational facts without treating them as authority or proof."""
    if value is None:
        return None
    names = {'tool', 'call_id', 'stage', 'phase', 'status', 'exit_code', 'process_id', 'call_sha256',
             'return_sha256', 'context_sha256', 'effects_sha256', 'input_sha256', 'operation_sha256', 'diagnostic_sha256',
             'edited_file_sha256', 'unresolved_check_sha256', 'launch_event_sha256', 'opportunity', 'delivered',
             'operation_kind', 'enabled', 'features', 'protected_capability_ids', 'authorization_message_id',
             'user_message_sha256'}
    if not isinstance(value, dict) or set(value) - names:
        raise ValueError('Invalid operation observation')
    result = {key: value.get(key) for key in sorted(names)}
    for key in ('tool', 'call_id', 'stage', 'authorization_message_id'):
        item = result[key]
        if item is not None and (not isinstance(item, str) or not item.strip() or len(item) > 256 or '\n' in item or '\r' in item):
            raise ValueError('Invalid operation identifier')
    if result['phase'] is not None and result['phase'] not in ('started', 'pending', 'terminal', 'unknown'):
        raise ValueError('Invalid operation phase')
    if result['status'] is not None and result['status'] not in ('success', 'failure', 'interrupted', 'pending', 'unknown'):
        raise ValueError('Invalid operation status')
    if result['exit_code'] is not None and (not isinstance(result['exit_code'], int) or isinstance(result['exit_code'], bool)):
        raise ValueError('Invalid operation exit code')
    process = result['process_id']
    if process is not None and (isinstance(process, bool) or not isinstance(process, (str, int))
                                or isinstance(process, str) and (not process.strip() or len(process) > 256 or '\n' in process or '\r' in process)):
        raise ValueError('Invalid operation process ID')
    for key in ('opportunity', 'delivered'):
        if result[key] is not None and not isinstance(result[key], bool):
            raise ValueError('Invalid operation evidence flag')
    if result['operation_kind'] is not None and result['operation_kind'] != 'optimization_settings':
        raise ValueError('Invalid operation kind')
    if result['enabled'] is not None and not isinstance(result['enabled'], bool):
        raise ValueError('Invalid optimization setting')
    features = result['features']
    if features is not None and (not isinstance(features, dict)
                                 or set(features) - {'experience', 'tools', 'loops', 'repo_map', 'display'}
                                 or any(flag is not None and not isinstance(flag, bool) for flag in features.values())):
        raise ValueError('Invalid optimization features')
    protected = result['protected_capability_ids']
    if protected is not None and (not isinstance(protected, list) or len(protected) > 1024
                                  or any(not isinstance(item, str) or not item.strip() or len(item) > 256
                                         or '\n' in item or '\r' in item for item in protected)):
        raise ValueError('Invalid protected capability IDs')
    if result['operation_kind'] != 'optimization_settings' and any(result[key] is not None for key in
            ('enabled', 'features', 'protected_capability_ids', 'authorization_message_id', 'user_message_sha256')):
        raise ValueError('Optimization settings require their declared operation kind')
    def valid_hash(item):
        return isinstance(item, str) and len(item) == 64 and all(c in '0123456789abcdef' for c in item)
    for key in ('call_sha256', 'return_sha256', 'context_sha256', 'effects_sha256', 'input_sha256', 'operation_sha256',
                'diagnostic_sha256', 'launch_event_sha256', 'user_message_sha256'):
        if result[key] is not None and not valid_hash(result[key]):
            raise ValueError('Invalid operation evidence hash')
    for key in ('edited_file_sha256', 'unresolved_check_sha256'):
        if result[key] is not None and (not isinstance(result[key], list) or len(result[key]) > 1024
                                        or not all(valid_hash(item) for item in result[key])):
            raise ValueError('Invalid operation evidence hashes')
    return result


def usage_v3_events(events, source, mode, epoch, sequence, session_id, fingerprint, source_ref):
    """Normalize declared usage observations; source files remain the evidence."""
    if not epoch or not epoch.strip() or sequence is None or sequence < 0:
        raise ValueError('Usage events require a nonempty epoch and nonnegative sequence')
    if source == 'codex-app-server' and mode != 'cumulative':
        raise ValueError('The app-server adapter uses cumulative total')
    aliases = dict(zip(TOKEN_FIELDS, ('inputTokens', 'cachedInputTokens', 'cacheWriteInputTokens',
                                      'outputTokens', 'reasoningOutputTokens')))
    rows = []
    for event in events:
        if not isinstance(event, dict):
            raise ValueError('Usage event must be an object')
        if source == 'codex-app-server':
            if event.get('method') != 'thread/tokenUsage/updated':
                continue
            params = event.get('params')
            if not isinstance(params, dict) or not isinstance(params.get('tokenUsage'), dict):
                raise ValueError('Invalid app-server usage notification')
            usage = params['tokenUsage']
            sid, turn, event_id = params.get('threadId'), params.get('turnId'), None
            if not isinstance(usage.get('last'), dict) or not isinstance(usage.get('total'), dict):
                raise ValueError('App-server usage needs last and total')
            counter, last = usage_counter(usage['total'], aliases), usage_counter(usage['last'], aliases)
            reported_total = {'total': usage['total'].get('totalTokens'), 'last': usage['last'].get('totalTokens')}
            metadata, resources, resource_scope, operation = {}, {}, 'unknown', None
            source_id = 'codex-app-server'
        else:
            if event.get('type') != 'usage.observed' and isinstance(event.get('usage_observation'), dict):
                event = event['usage_observation']
            if event.get('type') != 'usage.observed':
                continue
            sid, turn, event_id = event.get('session_id'), event.get('turn_id'), event.get('event_id')
            counter_data = event.get('counters')
            counter_data = {} if counter_data is None else counter_data
            counter, last = usage_counter(counter_data), None
            reported_total = {'total': counter_data.get('total_tokens')}
            metadata, resources = event.get('metadata', {}), event.get('resources', {})
            resource_scope = event.get('resource_scope', 'unknown')
            source_id = event.get('source_id')
            operation = usage_operation(event.get('operation'))
            if mode == 'observation' and (operation is None or any(value is not None for value in counter.values())
                                          or reported_total['total'] is not None):
                raise ValueError('Observation mode requires an operation and no token counters')
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError('Usage needs a source identity')
        if any(v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 0)
               for v in reported_total.values()):
            raise ValueError('Invalid reported total')
        if session_id and sid != session_id:
            raise ValueError('Declared session differs from usage event')
        if not isinstance(sid, str) or not sid.strip() or (turn is not None and (not isinstance(turn, str) or not turn.strip())):
            raise ValueError('Usage needs a session and valid optional turn')
        if source == 'codex-app-server' and turn is None:
            raise ValueError('App-server usage needs a turn ID')
        if event_id is not None and (not isinstance(event_id, str) or not event_id.strip()):
            raise ValueError('Invalid usage event ID')
        if not isinstance(metadata, dict) or set(metadata) - {'requested', 'observed'}:
            raise ValueError('Invalid usage metadata')
        clean_metadata = {}
        for kind, item in metadata.items():
            if not isinstance(item, dict) or set(item) - {'model', 'effort', 'agent'}:
                raise ValueError('Invalid model metadata')
            if any(v is not None and (not isinstance(v, str) or not v.strip()) for v in item.values()):
                raise ValueError('Invalid model metadata value')
            clean_metadata[kind] = item
        fields = {'tool_calls', 'retries', 'auxiliary_calls', 'failure_loops', 'human_corrections'}
        if not isinstance(resource_scope, str) or resource_scope not in {'event', 'unknown'}:
            raise ValueError('Invalid usage resource scope')
        if not isinstance(resources, dict) or set(resources) - (fields | {'duration_seconds'}):
            raise ValueError('Invalid usage resources')
        for key, value in resources.items():
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                    or isinstance(value, float) and not math.isfinite(value) or value < 0
                    or key in fields and not isinstance(value, int)):
                raise ValueError('Invalid usage resource value')
        identity = {'source': source, 'source_id': source_id, 'session_id': sid, 'epoch': epoch, 'mode': mode}
        if event_id:
            identity['event_id'] = event_id
        elif mode == 'cumulative':
            identity.update(turn_id=turn, counter=counter)
        else:
            # A source without event identity cannot support exactly-once delta accounting.
            identity.update(unidentified_source=fingerprint, index=len(rows))
        rows.append({'usage_contract': 3, 'identity': identity, 'sequence': sequence, 'index': len(rows),
                     'turn_id': turn, 'counter': counter, 'last': last, 'metadata': clean_metadata,
                     'reported_total': reported_total, 'resources': resources, 'resource_scope': resource_scope,
                     'operation': operation, 'hash': fingerprint,
                     'source_refs': [{'path': source_ref, 'sha256': fingerprint}],
                     'source_verification': 'imported-unverified', 'imported': now()})
    return rows


def usage_event_fingerprint(run):
    """Identify the same recorded event independently of an operator's epoch label."""
    identity = {key: value for key, value in run['identity'].items() if key not in ('epoch', 'mode')}
    if identity.get('event_id'):
        return content_hash({'identity': identity})
    fields = ('turn_id', 'counter', 'last')
    return content_hash({'identity': identity, 'event': {key: run.get(key) for key in fields}})


def report_usage_v3(runs, legacy_sessions):
    groups, problems, intervals = {}, [], []
    event_epochs = {}
    fingerprints = {}
    for _, run in runs:
        identity = run['identity']
        fingerprint = usage_event_fingerprint(run)
        fingerprints[id(run)] = fingerprint
        event_epochs.setdefault(fingerprint, set()).add((identity['session_id'], identity['epoch']))
    repeated = {key for key, epochs in event_epochs.items() if len(epochs) > 1}
    overlap = set().union(*(event_epochs[key] for key in repeated)) if repeated else set()
    for task_id, run in runs:
        identity = run['identity']
        if identity['mode'] == 'observation':
            continue
        key = (identity['session_id'], identity['epoch'])
        groups.setdefault(key, []).append((task_id, run))
    details = []
    for (sid, epoch), rows in groups.items():
        modes = {row['identity']['mode'] for _, row in rows}
        sources = {(row['identity']['source'], row['identity']['source_id']) for _, row in rows}
        issues = []
        if (sid, epoch) in overlap:
            issues.append('same-event-across-epochs')
        if (sid, epoch) in legacy_sessions or len(modes) != 1 or len(sources) != 1:
            issues.append('overlapping-or-unclassified-sources')
        if any(row['identity'].get('unidentified_source') for _, row in rows):
            issues.append('missing-event-identity')
        positions = [(row['sequence'], row['index']) for _, row in rows]
        if len(positions) != len(set(positions)) and modes == {'cumulative'}:
            issues.append('conflicting-observation-position')
        ordered = sorted(rows, key=lambda item: (item[1]['sequence'], item[1]['index']))
        if modes == {'cumulative'} and ordered and ordered[0][1]['sequence'] != 0:
            issues.append('initial-counter-baseline-unknown')
        if modes == {'cumulative'}:
            last_known = {field: None for field in TOKEN_FIELDS}
            previous = {field: 0 if ordered and ordered[0][1]['sequence'] == 0 else None for field in TOKEN_FIELDS}
            for _, row in ordered:
                increments = {}
                for field in TOKEN_FIELDS:
                    value = row['counter'][field]
                    if value is not None and last_known[field] is not None and value < last_known[field]:
                        issues.append('counter-decreased-within-declared-epoch')
                    increments[field] = (value - previous[field] if value is not None and previous[field] is not None
                                         and value >= previous[field] else None)
                    if value is not None:
                        last_known[field] = value
                    previous[field] = value
                intervals.append({'identity': row['identity'], 'sequence': row['sequence'], 'increment': increments})
            values = ordered[-1][1]['counter'] if ordered else {}
        elif modes == {'delta'}:
            intervals.extend({'identity': row['identity'], 'sequence': row['sequence'],
                              'increment': row['counter'] if row['identity'].get('event_id') else
                              {field: None for field in TOKEN_FIELDS}} for _, row in ordered)
            values = {field: sum(row['counter'][field] for _, row in ordered)
                      if all(row['counter'][field] is not None for _, row in ordered) else None
                      for field in TOKEN_FIELDS}
        else:
            values = {}
        issues = sorted(set(issues))
        problems.extend({'session_id': sid, 'epoch': epoch, 'kind': issue} for issue in issues)
        details.append({'session_id': sid, 'epoch': epoch, 'modes': sorted(modes),
                        'sources': [{'format': source, 'id': source_id} for source, source_id in sorted(sources)],
                        'totals': {field: None if issues else values.get(field) for field in TOKEN_FIELDS},
                        'observations': len(rows), 'problems': issues})
    problems.extend({'session_id': sid, 'epoch': epoch, 'kind': 'same-event-across-epochs'}
                    for sid, epoch in sorted(overlap - set(groups)))
    totals = {field: sum(group['totals'][field] for group in details)
              if details and all(group['totals'][field] is not None for group in details) else None
              for field in TOKEN_FIELDS}
    observations = [{'identity': run['identity'], 'sequence': run['sequence'], 'turn_id': run['turn_id'],
                     'counter': run['counter'], 'last': run['last'], 'metadata': run['metadata'],
                     'reported_total': run['reported_total'], 'resources': run['resources'], 'resource_scope': run['resource_scope'],
                     'source_verification': run['source_verification'], 'source_refs': run['source_refs'], 'operation': run.get('operation'),
                     'tasks': run.get('tasks', [task_id]), 'hash': run['hash']}
                    for task_id, run in runs]
    resource_fields = ('tool_calls', 'retries', 'auxiliary_calls', 'failure_loops', 'human_corrections', 'duration_seconds')
    subtotals = {}
    for field in resource_fields:
        reported = [run['resources'][field] for _, run in runs
                    if run['resource_scope'] == 'event' and run['resources'].get(field) is not None
                    and not run['identity'].get('unidentified_source')]
        duplicated = any(fingerprints[id(run)] in repeated and run['resource_scope'] == 'event'
                         and run['resources'].get(field) is not None for _, run in runs)
        subtotals[field] = {'recorded_event_subtotal': sum(reported) if reported and not duplicated else None,
                            'events_reporting': len(reported), 'events_recorded': len(runs)}
    return {'groups': details, 'totals': totals, 'problems': problems, 'observations': observations, 'intervals': intervals,
            'coverage': 'Recorded observations through the latest imported event; session completion is not inferred.',
            'resource_subtotals': subtotals}


def report_usage(state):
    groups, problems, intervals = {}, [], []
    runs = [(key, run) for key, task in state['tasks'].items() for run in task['usage']]
    v3_runs = [(task_id, run) for task_id, run in runs if run.get('usage_contract') == 3]
    v3_numeric = [(task_id, run) for task_id, run in v3_runs if run['identity']['mode'] != 'observation']
    runs = [(task_id, run) for task_id, run in runs if run.get('usage_contract') != 3]
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
    source_epochs = {}
    for (sid, epoch), observations in groups.items():
        for _, index, _, _, fingerprint in observations:
            source_epochs.setdefault((sid, fingerprint, index), set()).add(epoch)
    overlap = {(sid, epoch) for (sid, _, _), epochs in source_epochs.items() if len(epochs) > 1 for epoch in epochs}
    epoch_totals = []
    for (sid, epoch), observations in groups.items():
        positions = {}
        invalid = (sid, epoch) in overlap
        if invalid:
            problems.append({'session_id': sid, 'epoch': epoch, 'kind': 'same-source-across-epochs'})
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
    totals['elapsed_seconds'] = (sum(run['elapsed_seconds'] for _, run in runs)
                                 if runs and not overlap and all(run.get('elapsed_seconds') is not None for _, run in runs) else None)
    totals['total_tokens'] = totals['input_tokens'] + totals['output_tokens'] if totals['input_tokens'] is not None and totals['output_tokens'] is not None else None
    result = {'runs': len(runs), 'counter_epochs': len(groups), 'totals': totals, 'problems': problems,
            'intervals': intervals, 'attempts': sum(t['attempts'] for t in state['tasks'].values()),
            'human_corrections': (sum(t['human_corrections'] for t in state['tasks'].values()) if not overlap else None),
            'meaning': 'CLI counters accumulate within each declared session epoch. Sequence zero identifies the captured epoch start. The declared sequence sets chronology. Input includes cached input; output includes reasoning output. Unknown values are null. Each interval increment measures the change since the preceding recorded observation.'}
    if v3_runs:
        extended = report_usage_v3(v3_runs, set(groups))
        result['event_usage'] = extended
        result['runs'] += len(v3_numeric)
        result['operational_observations'] = len(v3_runs) - len(v3_numeric)
        result['counter_epochs'] += len(extended['groups'])
        result['problems'].extend(extended['problems'])
        if v3_numeric:
            for field in TOKEN_FIELDS:
                old, new = totals[field], extended['totals'][field]
                totals[field] = new if not runs else (old + new if old is not None and new is not None else None)
            totals['total_tokens'] = totals['input_tokens'] + totals['output_tokens'] if totals['input_tokens'] is not None and totals['output_tokens'] is not None else None
            totals['elapsed_seconds'] = None
            result['human_corrections'] = None
    return result

def prepare_hook_context(root, store, tasks, hook_path, task_id=None, release_hold=None, instruction_refs=()):
    """Save immutable copies of actual hook inputs; do not change a task or hold."""
    spec = importlib.util.spec_from_file_location('state_prepare_hooks', _base / 'codex_hooks.py')
    hooks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hooks)
    context_path = hooks.absolute(hook_path)
    context = hooks._read(context_path)
    if not isinstance(context, dict) or context.get('schema_version') != 2:
        raise ValueError('prepare-context requires the current version-2 host context')
    if hooks.absolute(context['cwd']) != root or hooks.absolute(context['plugin_root']) != _base.parent:
        raise ValueError('prepare-context root or plugin owner differs from the actual host context')
    directory = context_path.parent
    session = hooks.absolute(context['plugin_data']) / 'economics' / hooks.gate.sha(context['session_id'].encode())
    if hooks._read(session / 'active-task.json') != {'task_id': context['task_id']}:
        raise ValueError('prepare-context requires the active original task pointer')
    if hooks._lifecycle(directory) != 'active':
        raise ValueError('prepare-context requires an active ordinary task')
    spec = importlib.util.spec_from_file_location('state_prepare_policy', _base / 'policy_assets.py')
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    operation_binding = context.get('operation_binding') or {}
    selection = {'conditions': sorted(set(operation_binding.get('conditions', [])) | {'persistent_state_needed'})}
    if operation_binding:
        selection.update(operation=operation_binding['operation'], profile=operation_binding['profile'])
    owner, manifest_raw, manifest, _ = policy.discover_policy(policy.__file__, **selection)
    if (Path(owner) / manifest['assets']['policy_assets']['path']).absolute() != Path(policy.__file__).absolute():
        raise ValueError('prepare-context policy owner differs from the plugin root')
    request = hooks._effective_request(directory)
    hooks.load_context(context_path, request)
    binding = context.get('state_binding')
    if task_id is None:
        if binding is not None or release_hold is not None:
            raise ValueError('prepare-context requires the already bound task ID')
        previous = None
    else:
        if not isinstance(binding, dict) or binding.get('task_id') != task_id or hooks.absolute(binding.get('state_file')) != store or hooks.absolute(binding.get('state_root')) != root:
            raise ValueError('prepare-context task does not match the existing state binding')
        task = tasks[task_id]
        if context_changes(root, task) or not task.get('authority'):
            raise ValueError('saved task context or authority changed')
        previous = json.loads(json.dumps(task['task_context']))
        for field in ('request_refs', 'active_instruction_refs'):
            for ref in previous[field]:
                if field == 'active_instruction_refs' and not ref.get('path'):
                    raise ValueError('saved instruction source is unavailable')
                if ref.get('path') and digest(root / relative(root, ref['path'])) != ref['content_sha256']:
                    raise ValueError('saved task context source changed')
    prefix = '.agents/state/context-snapshots/'
    def immutable(data, suffix):
        name = prefix + hashlib.sha256(data).hexdigest() + suffix
        relative(root, name, exists=False)
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        relative(root, name, exists=False)
        fd, temporary = tempfile.mkstemp(prefix='.context-', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                gate.publish_file(Path(temporary), target)
            except FileExistsError:
                if gate.regular_bytes(target) != data:
                    raise ValueError('immutable context snapshot changed')
        finally:
            Path(temporary).unlink(missing_ok=True)
        return name
    request_path = immutable(request, '.request.txt')
    digest_request = hashlib.sha256(request).hexdigest()
    messages = [row for row in hooks._read(directory / 'task-messages.json', []) if row.get('kind') == 'amendment']
    latest = messages[-1] if messages else None
    packet = policy.instruction_context(owner, manifest=manifest, stage='entry', role='author')
    if previous is None:
        references = []
        for row in packet['reading_selection']:
            record = manifest['assets'][policy.resource_key(row['resource_id'])]
            raw = gate.regular_bytes(owner / record['path'])
            if hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('adopted instruction body changed')
            references.append({'rule_id': row['resource_id'], 'section': row['section_id'],
                'version': manifest['policy_id'] + ':' + packet['instruction_version'],
                'content_sha256': row['sha256'], 'path': immutable(raw, '.rule.txt')})
        value = {'request_refs': [{'source_id': 'actual:' + digest_request, 'version': 1,
                    'content_sha256': digest_request, 'path': request_path}],
                 'goal_and_constraints': request.decode('utf-8'), 'active_instruction_refs': references,
                 'adopted_decisions': []}
    else:
        value = previous
        old_sha = binding['effective_request_sha256']
        old_ref = next((row for row in previous['request_refs'] if row.get('content_sha256') == old_sha and row.get('path')), None)
        if old_ref is None:
            raise ValueError('bound previous effective request source is unavailable')
        old_request = gate.regular_bytes(root / relative(root, old_ref['path']))
        if hashlib.sha256(old_request).hexdigest() != old_sha or not request.startswith(old_request):
            raise ValueError('previous effective request is not the saved actual prefix')
        if digest_request != old_sha:
            if latest is None:
                raise ValueError('changed request lacks an actual user amendment')
            value['request_refs'].append({'source_id': 'actual:' + digest_request, 'version': 1,
                                          'content_sha256': digest_request, 'path': request_path})
            value['goal_and_constraints'] += request[len(old_request):].decode('utf-8')
        for row in packet['reading_selection']:
            current = next((ref for ref in value['active_instruction_refs']
                            if ref['rule_id'] == row['resource_id'] and ref['section'] == row['section_id']), None)
            version = manifest['policy_id'] + ':' + packet['instruction_version']
            if current is not None:
                if current['content_sha256'] != row['sha256'] or current['version'] != version:
                    raise ValueError('adopted entry instruction requires reconciliation')
                continue
            record = manifest['assets'][policy.resource_key(row['resource_id'])]
            raw = gate.regular_bytes(owner / record['path'])
            if hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('adopted instruction body changed')
            value['active_instruction_refs'].append({'rule_id': row['resource_id'], 'section': row['section_id'],
                'version': version, 'content_sha256': row['sha256'], 'path': immutable(raw, '.rule.txt')})
    assets = {key: gate.regular_bytes(owner / manifest['assets'][key]['path'])
              for key in (*policy.REGISTRY_KEYS.values(), 'route_registry')}
    resolver, routes = policy._routes(assets)
    for reference in instruction_refs:
        resource, separator, section = reference.rpartition('.')
        if not separator or resource not in routes['sections'] or section not in routes['sections'][resource]:
            raise ValueError('unknown registered instruction reference: ' + reference)
        key = policy.resource_key(resource)
        if key not in manifest['assets']:
            raise ValueError('instruction reference is not in the adopted manifest: ' + reference)
        adopted = manifest.get('resource_sections', {}).get(resource) if 'resource_sections' in manifest else None
        locator = routes['sections'][resource][section]
        if 'resource_sections' in manifest and not (adopted and (adopted.get('whole_resource')
                or locator.get('heading') in adopted.get('sections', []))):
            raise ValueError('instruction section is not adopted: ' + reference)
        record = manifest['assets'][key]
        raw = gate.regular_bytes(owner / record['path'])
        if hashlib.sha256(raw).hexdigest() != record['sha256']:
            raise ValueError('adopted instruction body changed: ' + reference)
        policy.section_ranges(routes, resource, raw.decode('utf-8'), resolver, {section})
        existing = next((row for row in value['active_instruction_refs']
                         if row['rule_id'] == resource and row['section'] == section), None)
        if existing is not None and (existing['content_sha256'] != record['sha256']
                or existing['version'] != manifest['policy_id'] + ':' + packet['instruction_version']):
            raise ValueError('adopted instruction reference requires reconciliation: ' + reference)
        if existing is None:
            value['active_instruction_refs'].append({'rule_id': resource, 'section': section,
                'version': manifest['policy_id'] + ':' + packet['instruction_version'],
                'content_sha256': record['sha256'], 'path': immutable(raw, '.rule.txt')})
    context_name = immutable(gate.canonical(value), '.context.json')
    output = {'task_context': context_name, 'request': request_path, 'request_sha256': digest_request,
              'policy_id': manifest['policy_id'], 'instruction_version': packet['instruction_version'],
              'policy_manifest_sha256': hashlib.sha256(manifest_raw).hexdigest(),
              'active_instruction_refs': value['active_instruction_refs'], 'reading_receipt': False,
              'instruction_sources': [{'resource_id': row['rule_id'], 'section': row['section'],
                  'source_path': manifest['assets'].get(policy.resource_key(row['rule_id']), {}).get('path'),
                  'snapshot_path': row.get('path'), 'sha256': row['content_sha256'], 'version': row['version']}
                  for row in value['active_instruction_refs']],
              'next': 'Read all applicable bodies; resolve the operation and any additional registered reading before dependent work.'}
    if previous is not None and digest_request != binding['effective_request_sha256']:
        change = {'source': 'user', 'message_id': latest['turn_id'], 'text': latest['text'],
                  'previous_context_sha256': content_hash(task['task_context']), 'replacement_context_sha256': content_hash(value)}
        output['user_change'] = immutable(gate.canonical(change), '.change.json')
    if release_hold is not None:
        if task_id is None or latest is None or release_hold not in task.get('holds', []):
            raise ValueError('release preparation requires an existing local hold and actual user amendment')
        release = {'source': 'user', 'message_id': latest['turn_id'], 'text': latest['text'],
                   'source_task_id': task_id, 'hold_id': release_hold}
        output['user_release'] = immutable(gate.canonical(release), '.release.json')
    return output


@lru_cache(maxsize=1)
def _project_argument():
    spec = importlib.util.spec_from_file_location('state_argument', _base / 'argument.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _project_references(root, tasks, task, graph, *, resolve=True, values=False, seen=()):
    """Join selected owner records without copying them into project state."""
    argument = _project_argument()
    effects = argument.REFERENCE_EFFECTS
    context = {row['decision_id']: row['choice'] for row in
               (task.get('task_context') or {}).get('adopted_decisions', [])}
    modules, loaded, rows, changes = {}, {}, [], {}
    def owner(name, path):
        if name not in modules:
            spec = importlib.util.spec_from_file_location('project_' + name, _base.parent / path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules[name] = module
        return modules[name]
    for node in graph['nodes']:
        refs = node.get('references', [])
        if not isinstance(refs, list):
            raise ValueError('Project references must be a list')
        for reference in refs:
            argument.reference_contract(reference)
            selectors = reference.get('when', {})
            if not resolve:
                continue
            row = {'node_id': node['node_id'], **reference, 'current_version': None}
            row['condition_state'] = ('inapplicable' if any(k in context and context[k] not in v for k, v in selectors.items())
                                      else 'unresolved' if any(k not in context for k in selectors) else 'satisfied')
            effect = effects[reference['relation']]
            row['action'] = 'reuse'
            if row['condition_state'] == 'unresolved' and effect != 'reference':
                row.update(action='authority', status='condition-required')
            elif row['condition_state'] == 'inapplicable' or effect == 'reference' and not values:
                row['status'] = 'not-required'
            else:
                try:
                    kind, ident, path = (reference[k] for k in ('kind', 'id', 'path'))
                    cache_key = content_hash({k: reference[k] for k in ('kind', 'id', 'path')} |
                                             {'keys': reference.get('keys'), 'context': context})
                    if cache_key not in loaded:
                        detail = {}
                        if kind == 'output':
                            producer = tasks[path]
                            if not output_current(root, tasks, path, ident):
                                raise ValueError('Referenced task output is not current')
                            version = producer['outputs'][ident]['version']
                            detail['producer_id'] = path
                            detail['definition_versions'] = producer['outputs'][ident].get('definition_versions', {})
                            if values:
                                detail['value'] = producer['outputs'][ident].get('value')
                                if isinstance(detail['value'], dict) and 'knowledge_output' in detail['value']:
                                    cache_name = ('task-knowledge', path, ident)
                                    if cache_name not in loaded:
                                        loaded[cache_name] = owner('knowledge', 'skills/econ-knowledge/scripts/knowledge.py').task_knowledge(
                                            producer, selected=[ident.removeprefix('knowledge:')])[1]
                                    source = loaded[cache_name][ident.removeprefix('knowledge:')]
                                    detail.update(value=source['value'], saved_reference=source['saved_reference'])
                        elif kind == 'decision':
                            key = (path, ident)
                            if key in seen:
                                raise ValueError('Cyclic adopted-decision reference: ' + path + '/' + ident)
                            producer = tasks[path]
                            if not context_current(root, producer):
                                raise ValueError('Referenced decision context revision changed')
                            decision = next((item for item in (producer.get('task_context') or {}).get('adopted_decisions', [])
                                             if item['decision_id'] == ident), None)
                            if decision is None:
                                raise ValueError('Unknown adopted decision: ' + ident)
                            version = content_hash(decision)
                            selected = {'nodes': [{'node_id': ident, 'references': decision.get('references', [])}]}
                            dependencies, _, actions = _project_references(root, tasks, producer, selected,
                                values=values, seen=(*seen, key))
                            detail = {'source_task_id': path, 'decision_version': decision['version'],
                                      'choice': decision['choice'], 'references': dependencies,
                                      'decision_review_required': bool(actions)}
                            if values:
                                detail['value'] = decision
                        elif kind == 'knowledge':
                            base = (_base.parent / 'skills/econ-knowledge/references' if path == '@package'
                                    else root / relative(root, path, exists=False))
                            reader_key = ('knowledge-reader', str(base))
                            if reader_key not in loaded:
                                loaded[reader_key] = owner('knowledge', 'skills/econ-knowledge/scripts/knowledge.py').Reader(base)
                            reader = loaded[reader_key]
                            plan = reader.plan([ident], context)
                            units = reader.units(plan['required_ids'])
                            unresolved = [e for e in plan['unresolved_conditions'] if e['type'] in
                                          {'prerequisite_to_understand', 'requires_to_apply', 'requires_assumption'}]
                            scientific = {'bodies': {u['id']: u['version']['body_sha256'] for u in units['units']},
                                'relations': [e for e in plan['eligible_relations'] if e['type'] in
                                              {'prerequisite_to_understand', 'requires_to_apply', 'requires_assumption'}],
                                'unresolved': unresolved, 'contracts': plan['contracts']}
                            version = content_hash(scientific)
                            detail = {'required_ids': plan['required_ids'], 'locators': plan['locators'],
                                      'unresolved_conditions': unresolved, 'read': reader.report()}
                            if values:
                                detail['value'] = units
                            if unresolved:
                                detail['input_required'] = True
                        else:
                            target = root / relative(root, path)
                            if kind == 'file':
                                version = digest(target)
                                detail['path'] = path
                            elif kind == 'literature':
                                selected = owner('search', 'skills/econ-literature/scripts/research_search.py').load_corpus_record(
                                    target, digest(target), proposition_ids=[ident])
                                version = selected['propositions'][0]['proposition_sha256']
                                detail['sources'] = selected['design_sources']
                            elif kind == 'claim':
                                evidence = owner('evidence', 'harness/research_evidence.py')
                                packet = evidence.review(gate.parse_json(target.read_bytes()), root, claim_ids=[ident])
                                version = packet['claim_fingerprints'][ident]
                                detail['claim_id'] = ident
                            else:
                                evidence = owner('evidence', 'harness/research_evidence.py')
                                value = evidence.read_json(target.read_bytes(), 'project JSON reference')
                                keys = reference.get('keys')
                                evidence.check_registered_inputs(value, root, keys)
                                identity = {'value': evidence.lookup(value, keys, 'project JSON reference')}
                                if value.get('schema') == 'research-artifact-registry-v1':
                                    if len(keys) > 1 and keys[0] in {'statistics', 'records'}:
                                        name = keys[1].split('.', 1)[0] if keys[0] == 'statistics' else keys[1]
                                        identity['references'] = value['records'][name]['references']
                                    else:
                                        identity['references'] = {k: v['references'] for k, v in value['records'].items()}
                                version = content_hash(identity)
                                detail['keys'] = keys
                                if values:
                                    detail['value'] = identity['value']
                        loaded[cache_key] = (version, detail)
                    version, detail = loaded[cache_key]
                    row.update(current_version=version, detail=detail,
                               status='current' if version == reference['version'] else 'changed')
                    if detail.get('input_required'):
                        row.update(action='authority', status='input-required')
                    elif detail.get('decision_review_required') and row['status'] == 'current':
                        row.update(action='review', status='decision-review-required')
                    elif row['status'] == 'changed':
                        row['action'] = effect
                    if effect == 'reference':
                        row['action'] = 'reuse'
                except (ValueError, KeyError, OSError, TypeError) as exc:
                    row.update(action='reuse' if effect == 'reference' else 'authority',
                               status='input-required', problem=str(exc))
            if row['action'] != 'reuse':
                changes.setdefault(node['node_id'], set()).add(row['action'])
            rows.append(row)
    return rows, context, changes


def decision_context(root, tasks, task_id, *, decision_ids=(), query='', history=False, values=False):
    """Select adopted knowledge from existing contexts and resolve its original owners."""
    task = tasks[task_id]
    terms = query.casefold().split()
    selected, found, contexts = [], set(), []
    for owner in [task, *task_ancestors(tasks, task)]:
        context = owner.get('task_context')
        if context is None:
            continue
        if owner.get('task_context_inherited_from') in tasks:
            continue
        contexts.append({'task_id': owner['task_id'], 'context_sha256': content_hash(context),
                         'request_refs': context['request_refs'],
                         'active_instruction_refs': context['active_instruction_refs'],
                         'goal_and_constraints': context['goal_and_constraints']})
        for decision in context['adopted_decisions']:
            ident = decision['decision_id']
            if decision_ids and ident not in decision_ids:
                continue
            body = json.dumps(decision, ensure_ascii=False).casefold()
            if not all(term in body for term in terms):
                continue
            found.add(ident)
            graph = {'nodes': [{'node_id': ident, 'references': decision.get('references', [])}]}
            refs, _, actions = _project_references(root, tasks, owner, graph, values=values,
                                                  seen=((owner['task_id'], ident),))
            row = {'task_id': owner['task_id'], 'decision': decision,
                   'version': content_hash(decision), 'references': refs,
                   'actions': sorted(actions.get(ident, [])),
                   'reference': {'kind': 'decision', 'id': ident, 'path': owner['task_id'],
                                 'version': content_hash(decision), 'relation': 'supports',
                                 'basis': decision['reason']}}
            if history:
                row['history'] = [{'context_revision': revision['revision'], 'at': revision['at'],
                                   'source': revision['source'], 'decision': previous}
                                  for revision in owner.get('context_revisions', [])
                                  for previous in (revision['context'] or {}).get('adopted_decisions', [])
                                  if previous['decision_id'] == ident]
            selected.append(row)
    if set(decision_ids) - found:
        raise ValueError('No selected adopted decision: ' + ', '.join(sorted(set(decision_ids) - found)))
    return {'task_id': task_id, 'contexts': contexts, 'decisions': selected,
            'next_action': task.get('next_action'), 'state_changed': False, 'analysis_executed': False}


def _project_number(value, name, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or positive and value == 0:
        raise ValueError('Project ' + name + ' must be a finite ' + ('positive' if positive else 'nonnegative') + ' number')
    return value


def _project_descendant(tasks, key, ancestor):
    seen = set()
    while key in tasks and key not in seen:
        if key == ancestor:
            return True
        seen.add(key)
        key = tasks[key].get('parent')
    return False


_GITHUB_FIELDS = {'status': 'Status', 'priority': 'Priority', 'due_date': 'Due date',
                  'classification': 'Classification', 'progress': 'Progress'}
_GITHUB_GROUPS = {'completed': ['Done', 'Completed'], 'active': ['In Progress', '進行中'],
                  'next': ['Todo', 'Not started', '未着手'], 'blocked': ['Blocked', '待機中']}


def _project_github_config(config):
    if (not isinstance(config, dict) or not isinstance(config.get('repository'), str)
            or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', config['repository'])
            or any(part in {'.', '..'} for part in config['repository'].split('/'))):
        raise ValueError('Project github.repository must be OWNER/REPO')
    for key in ('project_id', 'issue_template'):
        if key in config and (not isinstance(config[key], str) or not config[key].strip()):
            raise ValueError('Project github.' + key + ' must be nonempty')
    if 'project' in config:
        project = config['project']
        if (not isinstance(project, dict) or not isinstance(project.get('owner'), str)
                or not re.fullmatch(r'[A-Za-z0-9_.-]+', project['owner']) or project['owner'] in {'.', '..'}
                or type(project.get('number')) is not int or project['number'] < 1
                or project.get('owner_type', 'user') not in ('user', 'organization')):
            raise ValueError('GitHub project requires owner, positive number and user/organization owner_type')
    fields = config.get('fields', {})
    if (not isinstance(fields, dict) or set(fields) - set(_GITHUB_FIELDS)
            or any(not isinstance(value, str) or not value.strip() for value in fields.values())):
        raise ValueError('GitHub fields maps status, priority, due_date, classification and progress to Project field names')
    groups = config.get('status_groups', {})
    if (not isinstance(groups, dict) or set(groups) - {'completed', 'active', 'next', 'blocked'}
            or any(not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values)
                   for values in groups.values())):
        raise ValueError('GitHub status_groups maps completed, active, next and blocked to status names')
    names = [value.casefold() for values in {**_GITHUB_GROUPS, **groups}.values() for value in values]
    if len(names) != len(set(names)):
        raise ValueError('A GitHub status belongs to one summary group')


def _github_issue_identity(url):
    match = re.fullmatch(r'https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)', str(url))
    if not match or any(part in {'.', '..'} for part in match.group(1).split('/')):
        raise ValueError('Use a canonical GitHub issue URL')
    return match.group(1), int(match.group(2))


def _github_payload(value):
    """Unwrap connector returns while retaining the snapshot's acquisition identities."""
    while isinstance(value, dict):
        if value.get('isError'):
            raise ValueError('The GitHub connector returned an error')
        if 'structuredContent' in value:
            value = value['structuredContent']
        elif isinstance(value.get('content'), str):
            value = gate.parse_json(value['content'].encode('utf-8'))
        else:
            break
    if not isinstance(value, dict):
        raise ValueError('GitHub connector payload must contain a snapshot object')
    return value


def _github_snapshot_matches(config, snapshot):
    if snapshot.get('repository', '').casefold() != config['repository'].casefold():
        return False
    project = snapshot.get('project') or {}
    if config.get('project_id') and project.get('id') != config['project_id']:
        return False
    selector = config.get('project')
    if selector:
        owner_type = 'orgs' if selector.get('owner_type', 'user') == 'organization' else 'users'
        url = f"https://github.com/{owner_type}/{selector['owner']}/projects/{selector['number']}"
        return str(project.get('url', '')).casefold() == url.casefold()
    return project.get('id') == config.get('project_id')


def _github_cli(*arguments, payload=None):
    """Use the user's gh session for the selected API operation."""
    try:
        result = subprocess.run(['gh', *arguments], capture_output=True, text=True, timeout=60,
                                env={**os.environ, 'GH_HOST': 'github.com'},
                                input=json.dumps(payload, allow_nan=False) if payload is not None else None)
    except FileNotFoundError as exc:
        raise ValueError('GitHub operations require gh; reads also accept --github connector snapshots') from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError('GitHub operation timed out') from exc
    if result.returncode:
        raise ValueError('GitHub operation failed: ' + result.stderr.strip())
    value = gate.parse_json(result.stdout.encode('utf-8')) if result.stdout.strip() else None
    pages = value if isinstance(value, list) else [value]
    if any(isinstance(page, dict) and page.get('errors') for page in pages):
        raise ValueError('GitHub query returned errors: ' + json.dumps(value, ensure_ascii=False))
    return value


def _github_api(endpoint, *, query=None, project_id=None, paginate=False, method='GET', payload=None):
    command = ['api', '--hostname', 'github.com', endpoint]
    if query is None:
        command += ['--method', method, '-H', 'Accept: application/vnd.github+json',
                    '-H', 'X-GitHub-Api-Version: 2026-03-10']
        if payload is not None:
            command += ['--input', '-']
    else:
        command += ['--method', 'POST', '-f', 'query=' + query]
        if project_id is not None:
            command += ['-f', 'id=' + project_id]
    if paginate:
        command += ['--paginate', '--slurp']
    value = _github_cli(*command, payload=payload)
    if value is None and (query is not None or method == 'GET'):
        raise ValueError('GitHub read returned no JSON: ' + endpoint)
    if paginate and not isinstance(value, list):
        raise ValueError('GitHub pagination must return all response pages')
    return value


def _github_project_fetch(config, extra_fields=()):
    project_id = config.get('project_id')
    selector = config.get('project')
    if selector:
        owner_type = selector.get('owner_type', 'user')
        query = ('query { ' + owner_type + '(login: ' + json.dumps(selector['owner'])
                 + ') { projectV2(number: ' + str(selector['number']) + ') { id } } }')
        owner = _github_api('graphql', query=query).get('data', {}).get(owner_type)
        selected = owner.get('projectV2') if isinstance(owner, dict) else None
        if not isinstance(selected, dict) or not selected.get('id'):
            raise ValueError('GitHub did not return the selected owner and Project number')
        if project_id is not None and project_id != selected['id']:
            raise ValueError('GitHub project_id differs from the owner and number selector')
        project_id = selected['id']
    if project_id is None:
        return None
    fields = {**_GITHUB_FIELDS, **config.get('fields', {})}
    for index, name in enumerate(extra_fields):
        if name not in fields.values():
            fields['edit' + str(index)] = name
    value_fragment = ('... on ProjectV2ItemFieldSingleSelectValue { name } '
                      '... on ProjectV2ItemFieldTextValue { text } '
                      '... on ProjectV2ItemFieldDateValue { date } '
                      '... on ProjectV2ItemFieldNumberValue { number } '
                      '... on ProjectV2ItemFieldIterationValue { title }')
    selected = ' '.join(key + ': fieldValueByName(name: ' + json.dumps(name) + ') { ' + value_fragment + ' }'
                        for key, name in fields.items())
    queries = {
        'fields': 'nodes { ... on ProjectV2FieldCommon { id name dataType } '
                  '... on ProjectV2SingleSelectField { options { id name } } '
                  '... on ProjectV2IterationField { configuration { '
                  'iterations { id title startDate duration } completedIterations { id title startDate duration } } } }',
        'items': 'nodes { id isArchived content { ... on Issue { number repository { nameWithOwner } } } '
                 + selected + ' }'}
    project = {'id': project_id, 'fields': [], 'items': []}
    for connection, selection in queries.items():
        query = ('query($id: ID!, $endCursor: String) { node(id: $id) { ... on ProjectV2 { id title url '
                 + connection + '(first: 100, after: $endCursor) { pageInfo { hasNextPage endCursor } '
                 + selection + ' } } } }')
        for page in _github_api('graphql', query=query, project_id=project_id, paginate=True):
            node = page.get('data', {}).get('node')
            if not isinstance(node, dict) or node.get('id') != project_id or connection not in node:
                raise ValueError('GitHub Project was not returned: ' + project_id)
            project.update({key: node[key] for key in ('title', 'url')})
            for item in node[connection]['nodes']:
                if connection == 'fields':
                    project['fields'].append(item)
                elif (not item['isArchived'] and item.get('content')
                      and item['content'].get('repository', {}).get('nameWithOwner', '').casefold() == config['repository'].casefold()):
                    values = {fields[key]: next((value[k] for k in ('name', 'text', 'date', 'number', 'title') if k in value), None)
                              for key in fields if (value := item.get(key))}
                    project['items'].append({'id': item['id'], 'issue_number': item['content']['number'], 'fields': values})
    if not _github_snapshot_matches(config, {'repository': config['repository'], 'project': project}):
        raise ValueError('GitHub returned a different Project')
    return project


def _project_github_fetch(config, work):
    repository = config['repository']
    project = _github_project_fetch(config)
    numbers = {row['issue_number'] for row in work if 'issue_number' in row}
    numbers.update(item['issue_number'] for item in (project or {}).get('items', []))
    issues = []
    for number in sorted(numbers):
        endpoint = f'repos/{repository}/issues/{number}'
        issue = _github_api(endpoint)
        for relation in ('blocked_by', 'blocking'):
            pages = _github_api(endpoint + '/dependencies/' + relation + '?per_page=100', paginate=True)
            issue[relation] = [row for page in pages for row in page]
        issues.append(issue)
    return {'schema_version': 1, 'repository': repository, 'fetched_at': now(),
            'source': 'gh api', 'issues': issues, 'project': project}


def _github_form_fields(body):
    aliases = {'priority': {'priority', '優先順位'}, 'due_date': {'due date', '期限'},
               'classification': {'classification', '分類'}, 'progress': {'progress', '進捗'},
               'related_research': {'related research', '関連研究'}}
    sections = re.split(r'^###\s+(.+?)\s*$', body or '', flags=re.MULTILINE)
    result = {}
    for title, value in zip(sections[1::2], sections[2::2]):
        value = value.strip()
        if value and value not in {'_No response_', 'No response'}:
            for key, names in aliases.items():
                if title.casefold() in names:
                    result[key] = value
    return result


def _project_github(root, definition, snapshots):
    """Derive a view from a current API read or an explicitly supplied read snapshot."""
    config = definition['github']
    matches = [row for row in snapshots if _github_snapshot_matches(config, row)]
    if len(matches) > 1:
        raise ValueError('Multiple GitHub snapshots match the same repository and Project')
    data = matches[0] if matches else _project_github_fetch(config, definition['work'])
    if (type(data.get('schema_version')) is not int or data['schema_version'] != 1 or not isinstance(data.get('source'), str) or not data['source'].strip()
            or not isinstance(data.get('issues'), list)):
        raise ValueError('GitHub snapshot requires schema_version, source, fetched_at and issues')
    try:
        timestamp = datetime.fromisoformat(data['fetched_at'].replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            raise ValueError
    except (KeyError, AttributeError, ValueError) as exc:
        raise ValueError('GitHub fetched_at requires an ISO timestamp with timezone') from exc
    project = data.get('project')
    if project is not None and (not isinstance(project, dict) or not isinstance(project.get('items'), list)
                                or not isinstance(project.get('fields'), list)
                                or not isinstance(project.get('url'), str) or not project['url'].startswith('https://github.com/')):
        raise ValueError('GitHub Project snapshot requires id, url, fields and items')
    field_names = {**_GITHUB_FIELDS, **config.get('fields', {})}
    for field in (project or {}).get('fields', []):
        if (not isinstance(field, dict) or not isinstance(field.get('name'), str)
                or not isinstance(field.get('options', []), list)
                or any(not isinstance(option, dict) or not isinstance(option.get('name'), str) for option in field.get('options', []))):
            raise ValueError('Project fields require their names and single-select option names')
    items = {}
    for item in (project or {}).get('items', []):
        if not isinstance(item, dict):
            raise ValueError('Project items must be objects')
        number = item.get('issue_number')
        if (type(number) is not int or number < 1 or number in items or not isinstance(item.get('fields'), dict)
                or any(value is not None and type(value) not in {str, int, float} for value in item['fields'].values())):
            raise ValueError('Project items require distinct issue_number and fields')
        items[number] = item
    groups = {**_GITHUB_GROUPS, **config.get('status_groups', {})}
    groups = {key: {value.casefold() for value in values} for key, values in groups.items()}
    issues = []
    seen = set()
    for issue in data['issues']:
        if not isinstance(issue, dict):
            raise ValueError('GitHub Issues must be REST objects')
        number = issue.get('number')
        url = f"https://github.com/{config['repository']}/issues/{number}"
        if (type(number) is not int or number < 1 or number in seen or issue.get('pull_request')
                or not isinstance(issue.get('title'), str) or not issue['title'].strip()
                or not isinstance(issue.get('html_url'), str) or issue['html_url'].casefold() != url.casefold() or issue.get('state') not in {'open', 'closed'}
                or issue.get('body') is not None and not isinstance(issue['body'], str)
                or not isinstance(issue.get('assignees'), list)
                or any(not isinstance(row, dict) or not isinstance(row.get('login'), str) for row in issue['assignees'])):
            raise ValueError('GitHub snapshot requires distinct REST Issues from the bound repository')
        seen.add(number)
        dependencies = {}
        for relation in ('blocked_by', 'blocking'):
            if not isinstance(issue.get(relation), list):
                raise ValueError('GitHub Issue snapshot requires blocked_by and blocking arrays')
            dependencies[relation] = []
            for dependency in issue[relation]:
                if (not isinstance(dependency, dict) or dependency.get('state') not in {'open', 'closed'}
                        or not isinstance(dependency.get('html_url'), str)
                        or not re.fullmatch(r'https://github\.com/[^/]+/[^/]+/issues/[1-9][0-9]*', dependency['html_url'])):
                    raise ValueError('GitHub dependency requires its Issue html_url and state')
                dependencies[relation].append({'url': dependency['html_url'], 'number': dependency.get('number'),
                                               'title': dependency.get('title'), 'state': dependency['state']})
        values = _github_form_fields(issue.get('body'))
        fields = items.get(number, {}).get('fields', {})
        for key, name in field_names.items():
            if fields.get(name) is not None:
                values[key] = fields[name]
        status = values.get('status') or issue['state']
        status_name = str(status).casefold()
        progress = str(values.get('progress', '')).casefold()
        if issue['state'] == 'closed' or status_name in groups['completed']:
            bucket = 'completed'
        elif status_name in groups['blocked'] or progress in groups['blocked'] or any(row['state'] == 'open' for row in dependencies['blocked_by']):
            bucket = 'blocked'
        elif status_name in groups['active'] or progress in groups['active']:
            bucket = 'active'
        else:
            bucket = 'next'
        linked = [row for row in definition['work'] if row.get('issue_number') == number]
        artifacts = {kind: list(dict.fromkeys(value for row in linked for value in row.get('artifact_ids', {}).get(kind, [])))
                     for kind in ('results', 'figures', 'documents')}
        issues.append({'number': number, 'title': issue['title'], 'url': issue['html_url'],
                       'assignees': [row['login'] for row in issue['assignees']], 'state': issue['state'], 'status': status,
                       **{key: values.get(key) for key in ('priority', 'due_date', 'classification', 'progress')},
                       'updated_at': issue.get('updated_at'), 'closed_at': issue.get('closed_at'),
                       'bucket': bucket, 'dependencies': dependencies, 'project_item_id': items.get(number, {}).get('id'),
                       'execution_task_ids': [row['task_id'] for row in linked],
                       'links': {'issue': issue['html_url'], 'artifact_ids': artifacts,
                                 'related_research': values.get('related_research')}})
    needed = {row['issue_number'] for row in definition['work'] if 'issue_number' in row} | set(items)
    if needed - seen:
        raise ValueError('GitHub snapshot omits bound or Project Issues: ' + ', '.join(map(str, sorted(needed - seen))))
    issues = [row for row in issues if row['number'] in needed]
    options = next((row.get('options', []) for row in (project or {}).get('fields', [])
                    if row.get('name') == field_names['priority']), [])
    ranks = {row['name']: index for index, row in enumerate(options)}
    positions = {number: index for index, number in enumerate(items)}
    def priority_rank(issue):
        value = issue['priority']
        if value in ranks:
            return ranks[value]
        if type(value) in {int, float}:
            return value
        numbered = re.fullmatch(r'P([0-9]+)', str(value), flags=re.IGNORECASE)
        return int(numbered.group(1)) if numbered and not ranks else math.inf
    issues.sort(key=lambda row: (priority_rank(row), positions.get(row['number'], len(items)), row['number']))
    order = [key for issue in issues for key in issue['execution_task_ids']]
    order.extend(row['task_id'] for row in definition['work'] if row['task_id'] not in order)
    new_issue = f"https://github.com/{config['repository']}/issues/new"
    if config.get('issue_template'):
        new_issue += '?' + urlencode({'template': config['issue_template']})
    return {'repository': config['repository'], 'source': data['source'], 'fetched_at': data['fetched_at'],
            'snapshot_sha256': content_hash(data), 'tasks': issues, 'execution_priority': order,
            'project': project, 'management': {'issues_url': f"https://github.com/{config['repository']}/issues",
                'new_issue_url': new_issue, 'project_url': (project or {}).get('url'),
                'fields': (project or {}).get('fields', []), 'field_mapping': field_names,
                'rest_api': f"https://api.github.com/repos/{config['repository']}/issues",
                'graphql_api': 'https://api.github.com/graphql'}}


def _project_github_update(root, tasks, task_id, issue_url, changes, expected_updated_at=None):
    """Apply an explicit GitHub edit; adapted from PR #9 to the existing project contract."""
    task = tasks[task_id]
    if (not contract_current(root, task) or not constraints_current(root, tasks, task)
            or context_changes(root, task) or task.get('blocked_reason') in {'permission', 'user_hold'}):
        raise ValueError('Resolve the current project authority, holds and context before updating GitHub')
    definition, _, _ = _project_current(root, tasks, task_id)
    config = definition.get('github')
    if config is None:
        raise ValueError('Project has no GitHub binding')
    repository, number = _github_issue_identity(issue_url)
    if repository.casefold() != config['repository'].casefold():
        raise ValueError('Issue update is outside the bound repository')
    if issue_url not in task.get('external_targets', []):
        raise ValueError('Declare the exact Issue URL in the task external_targets before updating GitHub')
    permitted = {'title', 'body', 'state', 'state_reason', 'assignees', 'labels', 'milestone', 'fields', 'blocked_by'}
    if not isinstance(changes, dict) or not changes or set(changes) - permitted:
        raise ValueError('Use Issue fields, named Project fields, or blocked_by Issue URLs')
    fields = changes.get('fields', {})
    if not isinstance(fields, dict) or any(not isinstance(name, str) or not name.strip() for name in fields):
        raise ValueError('Project fields must map existing field names to values')
    patch = {key: value for key, value in changes.items() if key not in {'fields', 'blocked_by'}}
    if not patch and not fields and 'blocked_by' not in changes:
        raise ValueError('Supply an Issue, Project field or dependency change')
    for key, value in patch.items():
        if key == 'title' and (not isinstance(value, str) or not value.strip()):
            raise ValueError('Issue title must be nonempty text')
        if key == 'body' and value is not None and not isinstance(value, str):
            raise ValueError('Issue body must be text or null')
        if key == 'state' and value not in ('open', 'closed'):
            raise ValueError('Issue state must be open or closed')
        if key == 'state_reason' and (value not in ('completed', 'not_planned', 'reopened', None) or 'state' not in patch):
            raise ValueError('Issue state_reason requires a state change and its supported reason')
        if key in {'assignees', 'labels'} and (not isinstance(value, list)
                or any(not isinstance(item, str) or not item.strip() for item in value)):
            raise ValueError('Issue assignees and labels must be lists of names')
        if key == 'milestone' and value is not None and (type(value) is not int or value < 1):
            raise ValueError('Issue milestone must be its positive number or null')
    desired_dependencies = changes.get('blocked_by', [])
    if not isinstance(desired_dependencies, list):
        raise ValueError('blocked_by must be a list of canonical Issue URLs')
    dependency_refs = []
    for url in desired_dependencies:
        dep_repo, dep_number = _github_issue_identity(url)
        if dep_repo.casefold() == repository.casefold() and dep_number == number:
            raise ValueError('An Issue cannot depend on itself')
        dependency_refs.append((dep_repo, dep_number))
    project = _github_project_fetch(config, fields) if fields or config.get('project_id') or config.get('project') else None
    bound = {row['issue_number'] for row in definition['work'] if 'issue_number' in row}
    bound.update(row['issue_number'] for row in (project or {}).get('items', []))
    if number not in bound:
        raise ValueError('Select a work Issue or an Issue in the bound GitHub Project')
    targets = {issue_url}
    commands, expected_fields = [], {}
    if fields:
        if project is None:
            raise ValueError('Project field updates require a bound GitHub Project')
        targets.add(project['url'])
        if project['url'] not in task.get('external_targets', []):
            raise ValueError('Declare the exact Project URL in the task external_targets before editing its fields')
        item = next((row for row in project['items'] if row['issue_number'] == number), None)
        if item is None:
            raise ValueError('Selected Issue is not in the bound Project')
        for name, value in fields.items():
            matching = [row for row in project['fields'] if row['name'] == name]
            if len(matching) != 1:
                raise ValueError('Select one existing Project field: ' + name)
            field = matching[0]
            kind = field.get('dataType')
            if kind not in {'SINGLE_SELECT', 'ITERATION', 'DATE', 'NUMBER', 'TEXT'}:
                raise ValueError('Use Issue fields to update this built-in Project field: ' + name)
            command = ['project', 'item-edit', '--id', item['id'], '--project-id', project['id'], '--field-id', field['id']]
            expected_fields[name] = value
            if value is None:
                command.append('--clear')
            elif kind == 'SINGLE_SELECT':
                choices = [row for row in field['options'] if value in (row['id'], row['name'])]
                if len(choices) != 1:
                    raise ValueError('Select one existing Project option by name or ID: ' + name)
                command += ['--single-select-option-id', choices[0]['id']]
                expected_fields[name] = choices[0]['name']
            elif kind == 'ITERATION':
                configuration = field['configuration']
                choices = [row for row in [*configuration['iterations'], *configuration.get('completedIterations', [])]
                           if value in (row['id'], row['title'])]
                if len(choices) != 1:
                    raise ValueError('Select one existing Project iteration by title or ID: ' + name)
                command += ['--iteration-id', choices[0]['id']]
                expected_fields[name] = choices[0]['title']
            elif kind == 'DATE':
                if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
                    raise ValueError('Project date requires YYYY-MM-DD: ' + name)
                datetime.strptime(value, '%Y-%m-%d')
                command += ['--date', value]
            elif kind == 'NUMBER':
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError('Project number must be a finite JSON number: ' + name)
                command += ['--number', str(value)]
            else:
                if not isinstance(value, str):
                    raise ValueError('Project text must be a string: ' + name)
                command += ['--text', value]
            commands.append((name, [*command, '--format', 'json']))
    operation = {**task, 'operation_kind': 'external', 'external_targets': sorted(targets)}
    constraints = effective_constraints(tasks, operation, root)
    if constraints['holds'] or constraints['scope_errors']:
        raise ValueError('Resolve the existing external-operation hold or target scope before updating GitHub')
    if any(other['task_id'] != task_id and other['status'] == 'running'
           and targets.intersection(other.get('external_targets', [])) for other in tasks.values()):
        raise ValueError('GitHub target overlaps an active task')
    endpoint = f'repos/{repository}/issues/{number}'
    previous_dependencies, dependencies = {}, {}
    if 'blocked_by' in changes:
        previous_dependencies = {row['id']: row for page in _github_api(
            endpoint + '/dependencies/blocked_by?per_page=100', paginate=True) for row in page}
        for dep_repo, dep_number in dict.fromkeys(dependency_refs):
            dependency = _github_api(f'repos/{dep_repo}/issues/{dep_number}')
            if dependency.get('pull_request'):
                raise ValueError('An Issue dependency must identify an Issue')
            dependencies[dependency['id']] = dependency
    before = _github_api(endpoint)
    if before.get('pull_request') or str(before.get('html_url', '')).casefold() != issue_url.casefold():
        raise ValueError('GitHub did not return the exact target Issue')
    if expected_updated_at is not None and before.get('updated_at') != expected_updated_at:
        raise ValueError('Issue changed since it was read; retrieve its current values')
    responses = []
    try:
        if patch:
            responses.append({'operation': 'issue-update', 'target': issue_url,
                              'response': _github_api(endpoint, method='PATCH', payload=patch)})
        for name, command in commands:
            responses.append({'operation': 'project-field-update', 'target': project['url'], 'field': name,
                              'response': _github_cli(*command)})
        for dependency_id in sorted(dependencies.keys() - previous_dependencies.keys()):
            responses.append({'operation': 'dependency-add', 'target': issue_url, 'issue_id': dependency_id,
                'response': _github_api(endpoint + '/dependencies/blocked_by', method='POST', payload={'issue_id': dependency_id})})
        for dependency_id in sorted(previous_dependencies.keys() - dependencies.keys()):
            responses.append({'operation': 'dependency-remove', 'target': issue_url, 'issue_id': dependency_id,
                'response': _github_api(endpoint + '/dependencies/blocked_by/' + str(dependency_id), method='DELETE')})
        after = _github_api(endpoint)
        for key, expected in patch.items():
            actual = after.get(key)
            if key in {'assignees', 'labels'}:
                actual = sorted(row['login' if key == 'assignees' else 'name'] for row in actual or [])
                expected = sorted(expected)
            elif key == 'milestone':
                actual = actual.get('number') if actual else None
            if actual != expected:
                raise ValueError('GitHub readback differs from the requested Issue ' + key)
        if 'blocked_by' in changes:
            after['blocked_by'] = [row for page in _github_api(
                endpoint + '/dependencies/blocked_by?per_page=100', paginate=True) for row in page]
            if {row['id'] for row in after['blocked_by']} != set(dependencies):
                raise ValueError('GitHub dependency readback differs from the requested Issue list')
        updated_project = _github_project_fetch(config, fields) if fields else None
        if fields:
            item = next((row for row in updated_project['items'] if row['issue_number'] == number), None)
            if item is None or any(item['fields'].get(name) != value for name, value in expected_fields.items()):
                raise ValueError('GitHub Project field readback differs from the requested values')
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise ValueError(json.dumps({'operation': 'github-update', 'target': issue_url,
                                    'completed_responses': responses, 'error': str(exc)}, ensure_ascii=False)) from exc
    return {'operation': 'github-update', 'target': issue_url, 'responses': responses,
            'issue': after, 'project': updated_project, 'fetched_at': now()}


def _project_read(root, tasks, task_id, definition_path):
    definition_path = relative(root, definition_path)
    definition = gate.parse_json((root / definition_path).read_bytes())
    required = {'schema_version', 'argument', 'resources', 'work', 'data_date_hour',
                'time_unit', 'origin', 'target_finish_hour', 'approved_finish_hour', 'decision_rights'}
    if not isinstance(definition, dict) or not required <= set(definition) or type(definition['schema_version']) is not int or definition['schema_version'] != 1:
        raise ValueError('Project definition requires schema version 1 and the declared project fields')
    github = definition.get('github')
    if 'github' in definition:
        _project_github_config(github)
    if definition['time_unit'] != 'hours' or not isinstance(definition['origin'], str) or not definition['origin'].strip():
        raise ValueError('Project time unit must be hours and origin must be an explicit timezone ISO timestamp or relative label')
    origin = definition['origin']
    if not origin.startswith('relative:'):
        try:
            parsed = datetime.fromisoformat(origin.replace('Z', '+00:00'))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError
        except ValueError as exc:
            raise ValueError('Project origin needs an ISO timestamp with timezone or relative: label') from exc
    elif not origin[len('relative:'):].strip():
        raise ValueError('Project relative origin label is empty')
    for name in ('data_date_hour', 'target_finish_hour', 'approved_finish_hour'):
        _project_number(definition[name], name)
    if 'budget' in definition:
        _project_number(definition['budget'], 'budget')
    if 'currency' in definition and (not isinstance(definition['currency'], str) or not definition['currency'].strip()):
        raise ValueError('Project currency must be nonempty')
    if 'budget' in definition and 'currency' not in definition:
        raise ValueError('Project budget requires currency')
    argument = definition['argument']
    if not isinstance(argument, dict) or not {'path', 'sources_path'} <= set(argument):
        raise ValueError('Project argument requires path and sources_path')
    graph_path, sources_path = (relative(root, argument[k]) for k in ('path', 'sources_path'))
    graph = gate.parse_json((root / graph_path).read_bytes())
    sources = gate.parse_json((root / sources_path).read_bytes())
    module = _project_argument()
    try:
        result = module.validate_argument(graph, sources)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError('Invalid project argument: ' + str(exc)) from exc
    if not result['valid']:
        raise ValueError('Invalid project argument: ' + json.dumps(result['issues'], ensure_ascii=False))
    _project_references(root, tasks, tasks[task_id], graph, resolve=False)
    nodes = {row['node_id'] for row in graph['nodes']}
    resources = definition['resources']
    if not isinstance(resources, dict) or any(not isinstance(k, str) or not k.strip() for k in resources):
        raise ValueError('Project resources must map nonempty IDs to resource objects')
    for resource in resources.values():
        if not isinstance(resource, dict) or not {'capacity_units', 'hourly_cost'} <= set(resource):
            raise ValueError('Resource requires capacity_units and hourly_cost')
        _project_number(resource['capacity_units'], 'capacity_units', positive=True)
        _project_number(resource['hourly_cost'], 'hourly_cost')
    if any(resource['hourly_cost'] for resource in resources.values()) and 'currency' not in definition:
        raise ValueError('Nonzero hourly cost requires project currency')
    rights = definition['decision_rights']
    if not isinstance(rights, dict) or any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip() for k, v in rights.items()):
        raise ValueError('Project decision_rights must map names to actors')
    work = definition['work']
    if not isinstance(work, list) or not work:
        raise ValueError('Project work must be a nonempty list')
    ids = []
    for row in work:
        fields = {'task_id', 'node_ids', 'duration_hours', 'resources'}
        if not isinstance(row, dict) or not fields <= set(row):
            raise ValueError('Invalid project work fields')
        if 'issue_number' in row and (github is None or type(row['issue_number']) is not int or row['issue_number'] < 1):
            raise ValueError('Work issue_number requires a positive issue number and project github binding')
        if 'artifact_ids' in row:
            artifacts = row['artifact_ids']
            if (not isinstance(artifacts, dict) or set(artifacts) - {'results', 'figures', 'documents'}
                    or any(not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values)
                           or len(values) != len(set(values)) for values in artifacts.values())):
                raise ValueError('Work artifact_ids maps results, figures and documents to distinct IDs')
        if 'effect' in row and row['effect'] not in {'review', 'recalculate', 'regenerate', 'authority'}:
            raise ValueError('Invalid project work effect')
        key = row['task_id']
        if not isinstance(key, str) or not _project_descendant(tasks, key, task_id) or key == task_id or key in ids:
            raise ValueError('Project work must name distinct descendants of its project task')
        ids.append(key)
        if not isinstance(row['node_ids'], list) or not row['node_ids'] or any(not isinstance(n, str) or not n for n in row['node_ids']) or len(set(row['node_ids'])) != len(row['node_ids']) or set(row['node_ids']) - nodes:
            raise ValueError('Project work node_ids must identify distinct argument nodes')
        _project_number(row['duration_hours'], 'duration_hours', positive=True)
        _project_number(row.get('release_hour', 0), 'release_hour')
        _project_number(row.get('fixed_cost', 0), 'fixed_cost')
        if row.get('fixed_cost', 0) and 'currency' not in definition:
            raise ValueError('Fixed cost requires project currency')
        if not isinstance(row['resources'], dict) or set(row['resources']) - set(resources):
            raise ValueError('Project work uses unknown resources')
        for name, units in row['resources'].items():
            _project_number(units, 'resource units', positive=True)
            if units > resources[name]['capacity_units']:
                raise ValueError('Project work resource demand exceeds capacity: ' + name)
    if github is None or 'priority' in definition:
        priority = definition.get('priority')
        if not isinstance(priority, list) or any(not isinstance(v, str) for v in priority) or len(priority) != len(ids) or set(priority) != set(ids):
            raise ValueError('Project priority must contain every work task exactly once')
    if github is not None and not (github.get('project_id') or github.get('project')) and not any('issue_number' in row for row in work):
        raise ValueError('GitHub binding requires a Project selector or a work issue_number')
    binding = {'definition': {'path': definition_path, 'sha256': digest(root / definition_path)},
               'argument': {'path': graph_path, 'sha256': digest(root / graph_path)},
               'sources': {'path': sources_path, 'sha256': digest(root / sources_path)}}
    return definition, graph, binding


def _project_integrity(root, task):
    """Check saved binding, immutable source bytes and revision authority without task recursion."""
    saved = task.get('project_binding')
    history = task.get('project_history')
    if not isinstance(saved, dict) or set(saved) != {'definition', 'argument', 'sources'} or not isinstance(history, list) or not history:
        raise ValueError('Project binding or history is missing')
    if task.get('project_baseline') != history[0].get('binding') or history[-1].get('binding') != saved:
        raise ValueError('Project binding does not match its baseline or revision history')
    for ref in saved.values():
        try:
            path = relative(root, ref['path'])
            if digest(root / path) != ref['sha256']:
                raise ValueError('Project source drift: ' + path)
        except (OSError, KeyError) as exc:
            raise ValueError('Project source missing: ' + str(ref.get('path'))) from exc
    previous = None
    for revision in history:
        binding, source = revision['binding'], revision['source']
        if not isinstance(binding, dict) or set(binding) != {'definition', 'argument', 'sources'}:
            raise ValueError('Invalid project history binding')
        if previous is None:
            if source.get('kind') != 'initial-declaration':
                raise ValueError('Invalid project baseline source')
        else:
            message = source.get('message', {})
            if (source.get('kind') != 'user-change' or not isinstance(message, dict)
                    or message.get('source') != 'user' or not message.get('message_id') or not message.get('text')
                    or message.get('previous_project_sha256') != content_hash(previous)
                    or message.get('replacement_project_sha256') != content_hash(binding)
                    or not source.get('evidence')):
                raise ValueError('Project revision authority differs from its bindings')
        if changed(root, source.get('evidence', {})):
            raise ValueError('Project change authority evidence drift')
        for ref in binding.values():
            if changed(root, {ref['path']: ref['sha256']}):
                raise ValueError('Project historical source drift: ' + ref['path'])
        previous = binding
    return saved


def _project_current(root, tasks, task_id):
    if task_id not in tasks or not tasks[task_id].get('project_binding'):
        raise ValueError('Project task has no bound definition: ' + str(task_id))
    saved = _project_integrity(root, tasks[task_id])
    definition, graph, binding = _project_read(root, tasks, task_id, saved['definition']['path'])
    if binding != saved:
        raise ValueError('Project source binding changed')
    return definition, graph, binding


def _project_history(root, tasks, task_id):
    _project_current(root, tasks, task_id)
    return {'project_id': task_id, 'revisions': [
        {'revision': index + 1, 'project_sha256': content_hash(row['binding']), **row}
        for index, row in enumerate(tasks[task_id]['project_history'])]}


def _project_diff(root, tasks, task_id, from_revision=None, to_revision=None, definition_path=None):
    history = _project_history(root, tasks, task_id)['revisions']
    if definition_path is not None and to_revision is not None:
        raise ValueError('Select a proposed definition or a saved to-revision')
    before = from_revision if from_revision is not None else len(history) if definition_path else max(1, len(history) - 1)
    after = to_revision if to_revision is not None else len(history)
    if not 1 <= before <= len(history) or not 1 <= after <= len(history):
        raise ValueError('Project revision is outside the saved history')
    old = _project_read(root, tasks, task_id, history[before - 1]['binding']['definition']['path'])
    new = _project_read(root, tasks, task_id, definition_path or history[after - 1]['binding']['definition']['path'])
    changes = []
    def compare(left, right, path):
        if left == right:
            return
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                location = path + '/' + key.replace('~', '~0').replace('/', '~1')
                if key not in left:
                    changes.append({'path': location, 'operation': 'add', 'after': right[key]})
                elif key not in right:
                    changes.append({'path': location, 'operation': 'remove', 'before': left[key]})
                else:
                    compare(left[key], right[key], location)
        else:
            changes.append({'path': path, 'operation': 'replace', 'before': left, 'after': right})
    for kind in ('definition', 'argument', 'sources'):
        compare(gate.parse_json((root / old[2][kind]['path']).read_bytes()),
                gate.parse_json((root / new[2][kind]['path']).read_bytes()), '/' + kind)
    old_nodes = {row['node_id']: row for row in old[1]['nodes']}
    new_nodes = {row['node_id']: row for row in new[1]['nodes']}
    nodes = {key for key in set(old_nodes) | set(new_nodes) if old_nodes.get(key) != new_nodes.get(key)}
    old_edges = {content_hash(row): row for row in old[1]['dependencies']}
    new_edges = {content_hash(row): row for row in new[1]['dependencies']}
    nodes.update((old_edges.get(key) or new_edges[key])['to'] for key in set(old_edges) ^ set(new_edges))
    old_work = {row['task_id']: row for row in old[0]['work']}
    new_work = {row['task_id']: row for row in new[0]['work']}
    timing = set()
    for key in set(old_work) | set(new_work):
        left, right = old_work.get(key, {}), new_work.get(key, {})
        if left.get('node_ids') != right.get('node_ids'):
            nodes.update(left.get('node_ids', []))
            nodes.update(right.get('node_ids', []))
        if any(left.get(field) != right.get(field) for field in ('duration_hours', 'resources', 'release_hour', 'fixed_cost')):
            timing.add(key)
    resources = {key for key in set(old[0]['resources']) | set(new[0]['resources'])
                 if old[0]['resources'].get(key) != new[0]['resources'].get(key)}
    dates = any(old[0].get(key) != new[0].get(key) for key in
                ('origin', 'data_date_hour', 'target_finish_hour', 'approved_finish_hour', 'budget', 'currency'))
    dates |= ('github' not in old[0] or 'github' not in new[0]) and old[0].get('priority') != new[0].get('priority')
    impacts = [_project_impact(root, tasks, task_id, sorted(nodes & {row['node_id'] for row in current[1]['nodes']}),
                               resources=resources & set(current[0]['resources']),
                               work_tasks=timing & {row['task_id'] for row in current[0]['work']}, deadline=dates, current=current)
               for current in (old, new)]
    affected = {(row['task_id'], row['output_id']): row for impact in impacts for row in impact['affected_outputs']}
    impacted_tasks = sorted(set().union(*(set(impact['affected_task_ids']) for impact in impacts)))
    scheduled = sorted(set().union(*(set(impact['schedule_task_ids']) for impact in impacts)))
    impact = {'affected_task_ids': impacted_tasks, 'affected_outputs': list(affected.values()), 'schedule_task_ids': scheduled,
              'allocation_reassessment_required': bool(scheduled) or old[0]['decision_rights'] != new[0]['decision_rights'],
              'reusable_task_ids': sorted(set(new_work) - set(impacted_tasks)),
              'reusable_outputs': [row for row in impacts[1]['reusable_outputs'] if (row['task_id'], row['output_id']) not in affected]}
    if any('actions' in value for value in impacts):
        impact['actions'] = {action: sorted(set().union(*(set(value.get('actions', {}).get(action, [])) for value in impacts)))
                             for action in ('review', 'recalculate', 'regenerate', 'authority')}
    impact['affected_issues'] = _project_issue_links([old[0], new[0]], impacted_tasks)
    impact['schedule_issues'] = _project_issue_links([old[0], new[0]], scheduled)
    return {'project_id': task_id, 'from_revision': before, 'to_revision': None if definition_path else after,
            'proposed': definition_path is not None, 'from_binding': old[2], 'to_binding': new[2],
            'changes': changes, 'impact': impact}


def _project_issue_links(definitions, task_ids):
    links = {}
    for definition in definitions:
        if 'github' not in definition:
            continue
        for row in definition['work']:
            if row['task_id'] in task_ids and 'issue_number' in row:
                url = f"https://github.com/{definition['github']['repository']}/issues/{row['issue_number']}"
                links[(row['task_id'], url)] = {'task_id': row['task_id'], 'url': url}
    return list(links.values())


def project_context(root, tasks, task):
    """Restore each applicable bound project's exact sources, from root to this task."""
    result = []
    for owner in [*reversed(task_ancestors(tasks, task)), task]:
        if not owner.get('project_binding'):
            if owner.get('project_history') or owner.get('project_baseline'):
                raise ValueError('Project binding or history is missing')
            continue
        _, _, binding = _project_current(root, tasks, owner['task_id'])
        sources = {name: {**ref, 'text': (root / relative(root, ref['path'])).read_bytes().decode('utf-8')}
                   for name, ref in binding.items()}
        result.append({'task_id': owner['task_id'], 'binding': binding, 'sources': sources})
    return result


def _project_observations(root, tasks, task_id, definition, graph, binding):
    roles = {'project_judgment', 'project_acceptance', 'project_handover', 'project_outcome', 'project_actual',
             'project_finding', 'project_interpretation', 'project_open_decision'}
    result = []
    for key, task in tasks.items():
        if not _project_descendant(tasks, key, task_id):
            continue
        for output_id, row in task['outputs'].items():
            role = row.get('role')
            if role not in roles or row.get('kind') != 'object' or not output_current(root, tasks, key, output_id):
                continue
            value = row.get('value')
            if not isinstance(value, dict) or not all(isinstance(value.get(k), str) and value[k].strip() for k in ('actor', 'date', 'status')):
                continue
            refs = value.get('evidence')
            if not isinstance(refs, list) or not refs:
                continue
            try:
                if any(not isinstance(ref, dict) or set(ref) != {'path', 'sha256'} or digest(root / relative(root, ref['path'])) != ref['sha256'] for ref in refs):
                    continue
            except (OSError, ValueError, KeyError, TypeError):
                continue
            target = value.get('target')
            if not isinstance(target, dict):
                continue
            if set(target) == {'node_id', 'argument_sha256'}:
                if target['node_id'] not in {n['node_id'] for n in graph['nodes']} or target['argument_sha256'] != _project_argument().argument_sha256(graph):
                    continue
            elif set(target) == {'task_id', 'output_id', 'content_version'}:
                producer = target['task_id']
                oid = target['output_id']
                if producer not in tasks or not _project_descendant(tasks, producer, task_id) or oid == output_id and producer == key:
                    continue
                if oid not in tasks[producer]['outputs'] or tasks[producer]['outputs'][oid].get('version') != target['content_version'] or not output_current(root, tasks, producer, oid):
                    continue
            else:
                continue
            statuses = {'project_judgment': {'supported', 'refuted', 'proposed'},
                        'project_acceptance': {'proposed', 'accepted', 'rejected'},
                        'project_handover': {'proposed', 'handed_over', 'rejected'},
                        'project_outcome': {'proposed', 'observed'}, 'project_actual': {'proposed', 'actual'},
                        'project_finding': {'observed'}, 'project_interpretation': {'recorded', 'proposed'},
                        'project_open_decision': {'open', 'resolved'}}
            if value['status'] not in statuses[role]:
                continue
            if role in {'project_finding', 'project_interpretation', 'project_open_decision'}:
                if not isinstance(value.get('text'), str) or not value['text'].strip():
                    continue
                if role == 'project_open_decision' and (not isinstance(value.get('decision_id'), str) or not value['decision_id'].strip()):
                    continue
            if role in {'project_acceptance', 'project_handover'} and value['status'] in {'accepted', 'handed_over'}:
                if definition['decision_rights'].get(role.removeprefix('project_')) != value['actor']:
                    continue
            if role == 'project_outcome':
                if any(k not in value for k in ('observed_value', 'unit', 'target_value', 'comparator')) or not isinstance(value['unit'], str) or not value['unit'].strip() or not isinstance(value['comparator'], str) or not value['comparator'].strip():
                    continue
                if any(type(value[k]) not in (int, float) or not math.isfinite(value[k]) for k in ('observed_value', 'target_value')):
                    continue
            if role == 'project_actual':
                try:
                    _project_number(value['start_hour'], 'actual start')
                    _project_number(value['finish_hour'], 'actual finish')
                    if value['finish_hour'] < value['start_hour'] or 'task_id' not in target:
                        continue
                except (ValueError, KeyError):
                    continue
            result.append({'record_task_id': key, 'output_id': output_id, 'role': role, 'version': row['version'], 'value': value})
    return result


def _project_allocation(projects, observations):
    """Apply current economic judgments through the projects' existing decision rights."""
    bindings = {key: content_hash(binding) for key, _, _, binding in projects}
    baseline = [key for _, definition, _, _ in projects for key in definition['priority']]
    if any('github' in definition for _, definition, _, _ in projects):
        local = {project[0]: _project_allocation([project], observations) for project in projects if 'github' not in project[1]}
        priority = [task_id for key, definition, _, _ in projects
                    for task_id in (local[key]['priority'] if key in local else definition['priority'])]
        return {'status': 'decision-required' if any(row['status'] == 'decision-required' for row in local.values()) else 'github',
                'project_bindings': bindings, 'priority': priority,
                'records': [record for row in local.values() for record in row['records']]}
    rights = {key: definition['decision_rights'].get('allocation') for key, definition, _, _ in projects}
    candidates = {}
    for rows in observations.values():
        for row in rows:
            value = row['value']
            if row['role'] != 'project_judgment' or value['status'] != 'supported' or 'allocation' not in value:
                continue
            allocation = value['allocation']
            required = {'project_bindings', 'priority', 'rationale'}
            if (not isinstance(allocation, dict) or not required <= set(allocation)
                    or set(allocation) - required - {'switching_condition'}
                    or not isinstance(allocation['project_bindings'], dict)
                    or any(not isinstance(key, str) or not gate.hexhash(version)
                           for key, version in allocation['project_bindings'].items())):
                raise ValueError('Invalid allocation judgment fields')
            if (not isinstance(allocation.get('rationale'), str) or not allocation['rationale'].strip()
                    or 'switching_condition' in allocation and (not isinstance(allocation['switching_condition'], str)
                                                               or not allocation['switching_condition'].strip())):
                raise ValueError('Allocation requires its economic rationale and declared switching condition')
            if allocation.get('project_bindings') != bindings:
                continue  # A different or superseded portfolio is not authority for these inputs.
            priority = allocation.get('priority')
            if (not isinstance(priority, list) or any(not isinstance(key, str) for key in priority)
                    or len(priority) != len(baseline) or set(priority) != set(baseline)):
                raise ValueError('Allocation priority must contain every selected work task exactly once')
            authorized = {key for key, actor in rights.items() if actor == value['actor']}
            if not authorized:
                raise ValueError('Allocation judgment lacks project allocation authority')
            candidate = candidates.setdefault(content_hash(allocation), {
                **allocation, 'approved_projects': set(), 'records': []})
            candidate['approved_projects'].update(authorized)
            candidate['records'].append({key: row[key] for key in ('record_task_id', 'output_id', 'version')})
    adopted = [row for row in candidates.values() if row['approved_projects'] == set(bindings)]
    if len(adopted) > 1:
        raise ValueError('Conflicting current allocation judgments require their authorized decision')
    if adopted:
        return {'status': 'adopted', **{key: value for key, value in adopted[0].items() if key != 'approved_projects'}}
    return {'status': 'decision-required' if any(rights.values()) else 'baseline',
            'project_bindings': bindings, 'priority': baseline, 'records': []}


def _project_forecast(root, tasks, projects, priority=None, capacities=None, observations=None):
    proposed_priority = priority
    resources, work, priority, owner_project = {}, {}, [], {}
    observations = {} if observations is None else observations
    origin = projects[0][1]['origin']
    data_date = projects[0][1]['data_date_hour']
    currency = projects[0][1].get('currency')
    for project_id, definition, graph, binding in projects:
        if definition['origin'] != origin or definition['data_date_hour'] != data_date or definition.get('currency') != currency:
            raise ValueError('Shared projects require identical origin, data date and currency')
        for name, resource in definition['resources'].items():
            if name in resources and resources[name] != resource:
                raise ValueError('Conflicting shared project resource: ' + name)
            resources[name] = dict(resource)
        for row in definition['work']:
            if row['task_id'] in work:
                raise ValueError('Task appears in multiple projects: ' + row['task_id'])
            work[row['task_id']] = row
            owner_project[row['task_id']] = project_id
        priority.extend(definition['priority'])
        if project_id not in observations:
            observations[project_id] = _project_observations(root, tasks, project_id, definition, graph, binding)
    allocation = _project_allocation(projects, observations)
    priority = allocation['priority']
    if proposed_priority is not None or capacities is not None:
        if proposed_priority is not None:
            if (not isinstance(proposed_priority, list) or any(not isinstance(key, str) for key in proposed_priority)
                    or len(proposed_priority) != len(work) or set(proposed_priority) != set(work)):
                raise ValueError('Candidate priority must contain every selected work task exactly once')
            priority = proposed_priority
        if capacities is not None:
            if not isinstance(capacities, dict) or set(capacities) - set(resources):
                raise ValueError('Candidate capacity names an unknown resource')
            for name, units in capacities.items():
                _project_number(units, 'candidate capacity', positive=True)
                if any(row['resources'].get(name, 0) > units for row in work.values()):
                    raise ValueError('Candidate capacity is below a work resource demand')
                resources[name]['capacity_units'] = units
        allocation = {'status': 'proposal', 'priority': priority,
                      'project_bindings': allocation['project_bindings'], 'records': []}
    actual = {}
    for rows in observations.values():
        for observation in rows:
            value = observation['value']
            if observation['role'] == 'project_actual' and value['status'] == 'actual':
                key = value['target']['task_id']
                if key in actual:
                    raise ValueError('Multiple current actual records for task: ' + key)
                actual[key] = value
    execution_order = [key for key in priority if tasks[key]['status'] == 'running'] + [
        key for key in priority if tasks[key]['status'] != 'running']
    schedules, blocked, pending = {}, {}, set(work)
    intervals = {key: [] for key in resources}
    while pending:
        progressed = False
        for key in execution_order:
            if key not in pending:
                continue
            task = tasks[key]
            deps = list(dict.fromkeys(task['after'] + [r['producer_id'] for r in task.get('consumes', [])]))
            waiting = [dep for dep in deps if dep in pending]
            if waiting:
                continue
            unavailable = [dep for dep in deps if dep in blocked or dep not in work and not completion_current(root, tasks, dep)]
            if unavailable:
                blocked[key] = {'reason': 'dependency incomplete', 'dependencies': unavailable}
                pending.remove(key)
                progressed = True
                break
            if task['status'] in {'blocked', 'failed'} or effective_constraints(tasks, task, root)['holds']:
                blocked[key] = {'reason': 'task is ' + task['status'] + ' or held', 'dependencies': []}
                pending.remove(key)
                progressed = True
                break
            if task['status'] == 'completed' and not completion_current(root, tasks, key):
                blocked[key] = {'reason': 'completed task has stale results', 'dependencies': []}
                pending.remove(key)
                progressed = True
                break
            row = work[key]
            base = max([data_date, row.get('release_hour', 0)] + [schedules[d]['finish_hour'] for d in deps if d in schedules])
            predecessor = max((d for d in deps if d in schedules), key=lambda d: schedules[d]['precedence_finish_hour'], default=None)
            critical = max(data_date, row.get('release_hour', 0), schedules[predecessor]['precedence_finish_hour'] if predecessor else data_date)
            critical_path = (schedules[predecessor]['critical_path'] if predecessor and schedules[predecessor]['precedence_finish_hour'] >= max(data_date, row.get('release_hour', 0)) else []) + [key]
            done = completion_current(root, tasks, key)
            duration = 0 if done else row['duration_hours']
            start = base
            while duration:
                end = start + duration
                conflict_ends = []
                for name, units in row['resources'].items():
                    overlaps = [(a,b,u) for a,b,u in intervals[name] if a < end and b > start]
                    points = sorted({start, *(max(start,a) for a,b,u in overlaps), *(b for a,b,u in overlaps if start < b < end)})
                    for point in points:
                        active = [(b,u) for a,b,u in overlaps if a <= point < b]
                        if units + sum(u for b,u in active) > resources[name]['capacity_units'] + 1e-12:
                            conflict_ends.extend(b for b,u in active)
                            break
                if not conflict_ends:
                    break
                start = min(conflict_ends)
            finish = start + duration
            for name, units in row['resources'].items():
                if duration:
                    intervals[name].append((start, finish, units))
            cost = row.get('fixed_cost', 0) + row['duration_hours'] * sum(units * resources[name]['hourly_cost'] for name, units in row['resources'].items())
            schedules[key] = {'project_id': owner_project[key], 'start_hour': start, 'finish_hour': finish,
                              'precedence_start_hour': critical, 'precedence_finish_hour': critical + duration, 'critical_path': critical_path,
                              'resource_wait_hours': start - base, 'remaining_duration_hours': duration,
                              'planned_direct_cost': cost, 'remaining_direct_cost': 0 if done else cost,
                              'resource_units': row['resources'], 'owner': task['owner'],
                              'next_action': task['next_action'], 'actual': actual.get(key)}
            pending.remove(key)
            progressed = True
            break
        if not progressed:
            for key in sorted(pending):
                blocked[key] = {'reason': 'dependency cycle', 'dependencies': [d for d in tasks[key]['after'] if d in pending]}
            break
    summaries = {}
    for project_id, definition, _, _ in projects:
        ids = definition['priority']
        project_blocked = {key: blocked[key] for key in ids if key in blocked}
        complete = not project_blocked
        total_cost = sum(work[key].get('fixed_cost', 0) + work[key]['duration_hours'] * sum(units * resources[name]['hourly_cost'] for name, units in work[key]['resources'].items()) for key in ids)
        summaries[project_id] = {'target_finish_hour': definition['target_finish_hour'],
            'approved_finish_hour': definition['approved_finish_hour'],
            'forecast_finish_hour': max((schedules[key]['finish_hour'] for key in ids if key in schedules), default=data_date) if complete else None,
            'precedence_finish_hour': max((schedules[key]['precedence_finish_hour'] for key in ids if key in schedules), default=data_date) if complete else None,
            'critical_path': schedules[max(ids, key=lambda key: schedules[key]['precedence_finish_hour'])]['critical_path'] if complete and ids else None,
            'actual_finish_hour': max((actual[key]['finish_hour'] for key in ids), default=None) if all(key in actual and completion_current(root, tasks, key) for key in ids) else None,
            'planned_direct_cost': total_cost, 'currency': definition.get('currency'), 'budget': definition.get('budget'),
            'remaining_direct_cost': sum(schedules[key]['remaining_direct_cost'] for key in ids if key in schedules) if complete else None,
            'budget_difference': definition['budget'] - total_cost if 'budget' in definition else None, 'blocked': project_blocked}
        finish = summaries[project_id]['forecast_finish_hour']
        summaries[project_id]['target_delay_hours'] = max(0, finish - definition['target_finish_hour']) if finish is not None else None
        summaries[project_id]['approved_delay_hours'] = max(0, finish - definition['approved_finish_hour']) if finish is not None else None
    next_tasks = [key for key in priority if key in schedules and schedules[key]['start_hour'] <= data_date
                  and tasks[key]['status'] in {'queued', 'running'}
                  and all(completion_current(root, tasks, dependency) for dependency in
                          {*tasks[key]['after'], *(row['producer_id'] for row in tasks[key].get('consumes', []))})]
    if allocation['status'] == 'decision-required':
        next_tasks = []
    return {'time_unit': 'hours', 'origin': origin, 'data_date_hour': data_date, 'priority': priority,
            'resources': resources, 'allocation': allocation, 'execution_order': execution_order, 'next_tasks': next_tasks,
            'schedule': schedules, 'projects': summaries}


def _project_view(root, tasks, task_id, role, view, owner, others, priority=None, capacities=None, github=()):
    ids = [task_id] + others
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate selected project')
    projects = [(key, *_project_current(root, tasks, key)) for key in ids]
    snapshots = [_github_payload(gate.parse_json((root / relative(root, path)).read_bytes())) for path in github]
    if any(not isinstance(row, dict) or not isinstance(row.get('repository'), str)
           or row.get('project') is not None and not isinstance(row['project'], dict) for row in snapshots):
        raise ValueError('GitHub snapshots require a repository and a Project object or null')
    if any(not any(_github_snapshot_matches(definition['github'], row)
                   for _, definition, _, _ in projects if 'github' in definition) for row in snapshots):
        raise ValueError('GitHub snapshot does not match a selected project binding')
    external = {key: _project_github(root, definition, snapshots) for key, definition, _, _ in projects
                if 'github' in definition and view != 'story'}
    scheduled = [(key, {**definition, 'priority': external[key]['execution_priority']} if key in external else definition,
                  graph, binding) for key, definition, graph, binding in projects]
    human = {execution_id: row for data in external.values() for row in data['tasks'] for execution_id in row['execution_task_ids']}
    external_tasks = {row['task_id'] for key, definition, _, _ in projects if key in external for row in definition['work']}
    def selected_owner(key):
        return owner is None or (owner in human.get(key, {}).get('assignees', []) if key in external_tasks else tasks[key]['owner'] == owner)
    dependencies = {key: _project_impact(root, tasks, key, [], references=True, current=(definition, graph, binding))
                    for key, definition, graph, binding in projects if any(n.get('references') for n in graph['nodes'])}
    if (priority is not None or capacities is not None) and view != 'forecast':
        raise ValueError('Candidate priority and capacity apply to forecast')
    if others and view == 'story':
        raise ValueError('An argument story belongs to one project')
    observations = {key: _project_observations(root, tasks, key, definition, graph, binding)
                    for key, definition, graph, binding in projects}
    forecast = _project_forecast(root, tasks, scheduled, priority, capacities, observations) if view != 'story' else None
    if dependencies and forecast is not None:
        forecast['reference_impact'] = dependencies
        held = {tid for impact in dependencies.values() for tid in impact['actions']['authority']}
        forecast['next_tasks'] = [tid for tid in forecast['next_tasks'] if tid not in held]
    if view == 'forecast':
        forecast['role'] = role
        forecast['github'] = {key: {name: value for name, value in data.items() if name not in {'tasks', 'execution_priority', 'project'}}
                              for key, data in external.items()}
        for key, row in forecast['schedule'].items():
            if row['project_id'] in external:
                row['execution_owner'] = row.pop('owner')
                row['assignees'] = human.get(key, {}).get('assignees', [])
                row['issue_url'] = human.get(key, {}).get('url')
        if owner is not None:
            forecast['schedule'] = {key: value for key, value in forecast['schedule'].items() if selected_owner(key)}
            forecast['next_tasks'] = [key for key in forecast['next_tasks'] if selected_owner(key)]
        return forecast
    definition, graph, binding = projects[0][1:]
    obs = observations[task_id]
    decisions = (tasks[task_id].get('task_context') or {}).get('adopted_decisions', [])
    result = {'artifact_kind': 'project-view', 'generated_at': now(), 'project_id': task_id, 'role': role, 'view': view, 'binding': binding,
              'plan_revision': len(tasks[task_id]['project_history']),
              'argument_sha256': _project_argument().argument_sha256(graph),
              'central_question': graph['central_question'], 'central_answer': graph['central_answer'],
              'problem': graph.get('problem'), 'observations': obs,
              'outcome': [r for r in obs if r['role'] == 'project_outcome' and r['value']['status'] == 'observed'] or None,
              'target_finish_hour': definition['target_finish_hour'], 'approved_finish_hour': definition['approved_finish_hour']}
    result['findings'] = [row for row in obs if row['role'] == 'project_finding']
    result['interpretations'] = [row for row in obs if row['role'] == 'project_interpretation']
    result['open_decisions'] = [row for row in obs if row['role'] == 'project_open_decision' and row['value']['status'] == 'open'
                                and row['value']['decision_id'] not in {decision['decision_id'] for decision in decisions}]
    result['adopted_decisions'] = decisions
    result['plan'] = definition
    if task_id in external:
        data = external[task_id]
        result['github'] = {key: value for key, value in data.items() if key not in {'tasks', 'execution_priority', 'project'}}
        result['tasks'] = [row for row in data['tasks'] if owner is None or owner in row['assignees']]
        for row in result['tasks']:
            row['links']['plan'] = binding
            row['links']['outputs'] = [{'task_id': key, 'output_id': output_id, 'kind': output['kind'], 'version': output['version']}
                                      for key in row['execution_task_ids'] for output_id, output in tasks[key]['outputs'].items()]
        for group in ('completed', 'active', 'next', 'blocked'):
            result[group] = [row for row in result['tasks'] if row['bucket'] == group]
        result['completed'].sort(key=lambda row: row['closed_at'] or row['updated_at'] or '', reverse=True)
    if dependencies:
        result['reference_impact'] = dependencies
    if view == 'story':
        result.update(nodes=graph['nodes'], dependencies=graph['dependencies'], source_manifest=graph['source_manifest'])
    if view in {'summary', 'workplan'}:
        work = [{'task_id': row['task_id'], 'node_ids': row['node_ids'], 'owner': tasks[row['task_id']]['owner'],
                 'status': tasks[row['task_id']]['status'], 'current_completion': completion_current(root, tasks, row['task_id']),
                 'after': tasks[row['task_id']]['after'], 'next_action': tasks[row['task_id']]['next_action'],
                 'duration_hours': row['duration_hours'], 'resources': row['resources'],
                 'propositions': [node for node in graph['nodes'] if node['node_id'] in row['node_ids']],
                 'inputs': tasks[row['task_id']]['inputs'], 'consumes': tasks[row['task_id']].get('consumes', []),
                 'required_outputs': tasks[row['task_id']]['required_outputs'],
                 'required_actions': tasks[row['task_id']]['required_actions'],
                 'outputs': {key: {'kind': output['kind'], 'version': output['version']}
                             for key, output in tasks[row['task_id']]['outputs'].items()}}
                for row in definition['work'] if selected_owner(row['task_id'])]
        result['work'] = work
        result['allocation'] = forecast['allocation']
        result['next_tasks'] = [key for key in forecast['next_tasks'] if key in {row['task_id'] for row in work}]
        for row in work:
            if dependencies:
                row['dependency_actions'] = sorted({action for impact in dependencies.values()
                    for action, task_ids in impact['actions'].items() if row['task_id'] in task_ids})
                row['current_completion'] = row['current_completion'] and not row['dependency_actions']
            row['priority_rank'] = forecast['priority'].index(row['task_id']) + 1
            row['schedule'] = forecast['schedule'].get(row['task_id'])
            if task_id in external:
                row['execution'] = {key: row[key] for key in ('owner', 'status', 'after', 'next_action')}
                issue = human.get(row['task_id'], {})
                row.update({key: issue.get(key) for key in ('title', 'url', 'status', 'priority', 'due_date', 'classification', 'progress')})
                row['assignees'] = issue.get('assignees', [])
                row['owner'] = ', '.join(row['assignees']) or None
                row['dependencies'] = issue.get('dependencies')
                row['links'] = issue.get('links')
                if row['schedule']:
                    row['schedule']['execution_owner'] = row['schedule'].pop('owner')
                    row['schedule']['assignees'] = row['assignees']
        if task_id not in external:
            result['completed'] = [row for row in work if row['current_completion']]
            result['active'] = [row for row in work if row['status'] == 'running']
            result['next'] = [row for row in work if row['task_id'] in result['next_tasks'] and row['status'] == 'queued']
    if view == 'workplan':
        result['priority'] = [key for key in forecast['priority'] if any(row['task_id'] == key for row in work)]
        result['resources'] = forecast['resources']
    if role == 'manage':
        result['decision_rights'] = definition['decision_rights']
    return result


def _project_impact(root, tasks, task_id, nodes, resources=(), work_tasks=(), deadline=False, others=(), *, references=False, changes=None, current=None):
    definition, graph, binding = current if current is not None else _project_current(root, tasks, task_id)
    if not nodes and not resources and not work_tasks and not deadline and not references and not changes and current is None:
        raise ValueError('Project impact requires a node, resource, task or deadline change')
    ids = [task_id, *others]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate selected project')
    definitions = {task_id: definition}
    definitions.update({key: _project_current(root, tasks, key)[0] for key in others})
    work = {row['task_id']: row for item in definitions.values() for row in item['work']}
    known_resources = {key for item in definitions.values() for key in item['resources']}
    if set(resources) - known_resources or set(work_tasks) - set(work):
        raise ValueError('Project impact resource or task is outside the project')
    reference_rows, context, actions = _project_references(root, tasks, tasks[task_id], graph) if references else ([], {}, {})
    typed = references or changes is not None or any('effect' in d or 'when' in d for d in graph.get('dependencies', []))
    if typed:
        context = {row['decision_id']: row['choice'] for row in
                   (tasks[task_id].get('task_context') or {}).get('adopted_decisions', [])}
        for key, values in (changes or {}).items():
            actions.setdefault(key, set()).add(values)
        for key in nodes:
            actions.setdefault(key, {'review'})
        result = _project_argument().affected_nodes(graph, list(actions), context=context, changes=actions)
        result['references'] = reference_rows
    else:
        result = _project_argument().affected_nodes(graph, nodes)
    direct = {row['task_id'] for row in definition['work'] if set(row['node_ids']) & set(result['affected_node_ids'])}
    project_tasks = {key for key in tasks if any(_project_descendant(tasks, key, owner) for owner in ids)}
    affected = set(direct)
    productive = direct if not typed else {row['task_id'] for row in definition['work'] if any(
        set(result['node_actions'].get(n, [])) & {'recalculate', 'regenerate'} for n in row['node_ids'])}
    affected_outputs = {(key, oid) for key in productive for oid in tasks[key]['outputs']}
    changed = True
    while changed:
        changed = False
        for key in project_tasks:
            task = tasks[key]
            consumers = []
            for row in task.get('consumes', []):
                producer, oid = row['producer_id'], row['output_id']
                group = row.get('publication_group_id')
                grouped = group and any((producer, sibling) in affected_outputs and item.get('publication_group_id') == group
                                        for sibling, item in tasks[producer]['outputs'].items())
                if (producer, oid) in affected_outputs or grouped:
                    consumers.append(row)
            if key not in affected and ((not typed and set(task['after']) & affected) or consumers):
                affected.add(key)
                changed = True
            consumed_keys = {dependency_key(row) for row in consumers}
            for oid, output in task['outputs'].items():
                used = set(output.get('dependency_ids', task.get('dependency_versions') or {}))
                if (key, oid) not in affected_outputs and used & consumed_keys:
                    affected_outputs.add((key, oid))
                    changed = True
    schedule_tasks = ({row['task_id'] for row in definition['work']} if deadline else set()) | (affected & set(work)) | set(work_tasks)
    shared_resources = set(resources)
    while True:
        shared_resources.update(name for key in schedule_tasks for name in work[key]['resources'])
        expanded = schedule_tasks | {key for key, row in work.items() if shared_resources & set(row['resources'])
            or schedule_tasks & (set(tasks[key]['after']) | {item['producer_id'] for item in tasks[key].get('consumes', [])})}
        if expanded == schedule_tasks:
            break
        schedule_tasks = expanded
    outputs = [(key, oid, row) for key in project_tasks for oid, row in tasks[key]['outputs'].items()]
    classified = {}
    if typed:
        for action in ('review', 'recalculate', 'regenerate', 'authority'):
            classified[action] = sorted({row['task_id'] for row in definition['work']
                if any(action in result['node_actions'].get(n, []) for n in row['node_ids'])})
        # Actual output consumption is execution dependence, not an instruction
        # to rerun an estimate merely because its justification needs review.
        for key in affected - direct:
            action = work.get(key, {}).get('effect', 'authority')
            classified[action] = sorted(set(classified[action]) | {key})
    return {'binding': binding, **result, **({'actions': classified} if typed else {}), 'affected_task_ids': sorted(affected),
            'schedule_task_ids': sorted(schedule_tasks), 'allocation_reassessment_required': bool(schedule_tasks),
            'affected_issues': _project_issue_links(definitions.values(), affected),
            'schedule_issues': _project_issue_links(definitions.values(), schedule_tasks),
            'reusable_task_ids': sorted(set(work) - affected),
            'affected_outputs': [{'task_id': key, 'output_id': oid, 'version': row['version']} for key, oid, row in sorted(outputs) if (key, oid) in affected_outputs],
            'reusable_outputs': [{'task_id': key, 'output_id': oid, 'version': row['version']} for key, oid, row in sorted(outputs)
                                 if (key, oid) not in affected_outputs and (not typed or key not in direct - productive)
                                 and output_current(root, tasks, key, oid)]}


def parse_cli_args(argv=None, *, default_root=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=default_root or Path.cwd(), help='Project root; defaults to current working directory')
    parser.add_argument('--store', default='.agents/state/team.json')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    for name, default in [('max-active', None), ('max-depth', None), ('max-attempts', None)]:
        init.add_argument('--' + name, type=int, default=default)
    prepare = sub.add_parser('prepare-context')
    prepare.add_argument('--hook-context', required=True)
    prepare.add_argument('--task-id')
    prepare.add_argument('--release-hold')
    prepare.add_argument('--instruction-ref', action='append', default=[])
    add = sub.add_parser('add')
    add.add_argument('id')
    add.add_argument('--owner', required=True)
    add.add_argument('--record')
    add.add_argument('--requirements')
    add.add_argument('--request')
    add.add_argument('--task-context', help='Existing JSON context with request, instruction and adopted-decision versions')
    add.add_argument('--hook-context', help='Associate this task with the current host task context')
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
    for command in ['start', 'resume', 'set-context', 'bind-writing', 'release-hold', 'set-contract', 'action', 'requeue', 'output', 'verify', 'usage', 'transition', 'bind-specification']:
        cli = sub.add_parser(command)
        cli.add_argument('id')
        if command == 'bind-specification':
            cli.add_argument('--requirements', required=True)
            cli.add_argument('--request', required=True)
            cli.add_argument('--user-change')
        elif command == 'bind-writing':
            cli.add_argument('--paragraph-state', required=True, help='Saved ParagraphRun state; binds content and dependency versions')
        elif command == 'set-context':
            cli.add_argument('--task-context', required=True)
            cli.add_argument('--hook-context', help='Rebind this task to the current host request')
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
            cli.add_argument('--execution-result', help='Saved exact native command-result envelope')
            cli.add_argument('--check', required=True)
            cli.add_argument('--output', action='append')
            cli.add_argument('--input', action='append')
            cli.add_argument('--result', choices=['passed', 'failed'], help='Optional expected verdict for the supplied actual result')
            cli.add_argument('--reviewer', required=True)
        elif command == 'usage':
            cli.add_argument('--jsonl', type=Path, required=True)
            cli.add_argument('--source-format', choices=['legacy', 'codex-app-server', 'usage-event'], default='legacy')
            cli.add_argument('--counter-mode', choices=['cumulative', 'delta', 'observation'], help='Required for version-3 usage events')
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
    project_bind = sub.add_parser('project-bind')
    project_bind.add_argument('id')
    project_bind.add_argument('--definition', required=True)
    project_bind.add_argument('--user-change')
    project_history = sub.add_parser('project-history')
    project_history.add_argument('id')
    project_diff = sub.add_parser('project-diff')
    project_diff.add_argument('id')
    project_diff.add_argument('--from-revision', type=int)
    project_diff.add_argument('--to-revision', type=int)
    project_diff.add_argument('--definition', help='Compare a proposed immutable definition with the saved plan')
    project_view = sub.add_parser('project-view')
    project_view.add_argument('id')
    project_view.add_argument('--role', required=True, choices=['contribute', 'manage'])
    project_view.add_argument('--view', required=True, choices=['summary', 'story', 'workplan', 'forecast'])
    project_view.add_argument('--owner')
    project_view.add_argument('--project', action='append', default=[])
    project_view.add_argument('--priority', action='append', help='Candidate global order; repeat for every selected work task')
    project_view.add_argument('--capacity', help='Candidate resource capacities as a JSON object')
    project_view.add_argument('--github', action='append', default=[], metavar='SNAPSHOT', help='Current connector read snapshot; repeat for a portfolio')
    project_view.add_argument('--save', help='Save this derived view as project-relative JSON')
    project_update = sub.add_parser('project-update', help='Explicitly update a bound GitHub Issue or existing Project fields')
    project_update.add_argument('id')
    project_update.add_argument('--issue-url', required=True)
    project_update.add_argument('--changes', required=True, help='JSON object with Issue fields, fields, or blocked_by URLs')
    project_update.add_argument('--expected-updated-at', help='Reject a changed Issue timestamp before writing')
    project_impact = sub.add_parser('project-impact')
    project_impact.add_argument('id')
    project_impact.add_argument('--node', action='append', default=[])
    project_impact.add_argument('--resource', action='append', default=[])
    project_impact.add_argument('--task', action='append', default=[])
    project_impact.add_argument('--deadline', action='store_true')
    project_impact.add_argument('--project', action='append', default=[])
    project_impact.add_argument('--references', action='store_true', help='Compare selected owner references with their adopted versions')
    project_impact.add_argument('--change', action='append', default=[], metavar='NODE=ACTION', help='Classify an actual node change: review, recalculate, regenerate or authority')
    project_impact.add_argument('--definition', help='Calculate impact from a proposed versioned plan')
    project_impact.add_argument('--from-revision', type=int)
    project_impact.add_argument('--to-revision', type=int)
    view = sub.add_parser('inspect')
    view.add_argument('--stale-seconds', type=int, default=1800)
    view.add_argument('--invalidate', action='store_true')
    show = sub.add_parser('show')
    show.add_argument('task_id', nargs='?')
    context = sub.add_parser('context', help='Retrieve adopted decisions and their selected source/definition references')
    context.add_argument('task_id')
    context.add_argument('--decision', action='append', default=[], help='Select a decision ID; includes its existing governing ancestors')
    context.add_argument('--query', default='', help='Match every term in the selected decision records')
    context.add_argument('--history', action='store_true', help='Include existing context revisions of selected decisions')
    context.add_argument('--values', action='store_true', help='Read selected JSON, output and knowledge values from their existing owners')
    context.add_argument('--reference', action='append', default=[], help='Resolve an existing reference JSON and return its current version before adoption')
    find = sub.add_parser('find', help='Locate saved tasks, source references, results and failures before show/resume')
    find.add_argument('query', help='Case-insensitive literal terms; every whitespace-separated term must occur in the task')
    find.add_argument('--status', choices=sorted(STATES), help='Exact recorded status, not a current completion assessment')
    find.add_argument('--owner')
    find.add_argument('--parent', help='Exact immediate parent task ID')
    find.add_argument('--limit', type=int, default=5, help='Candidate page size; default 5')
    find.add_argument('--offset', type=int, default=0)
    find.add_argument('--snapshot', help='Prior find store_sha256; rejects pagination across a changed store')
    sub.add_parser('summary')
    return parser.parse_args(argv)


def cli_effect(args):
    """Classify the same parsed command used by execution, including saved views."""
    readonly = {'show', 'context', 'find', 'summary', 'prepare-context', 'project-view',
                'project-impact', 'project-history', 'project-diff', 'project-update'}
    store_write = args.command not in readonly and not (args.command == 'inspect' and not args.invalidate)
    files = [args.store] if store_write else []
    if args.command == 'project-view' and args.save:
        files.append(args.save)
    effect = ('write' if files or args.command in {'prepare-context', 'project-update'} else 'read')
    return effect, files, store_write


def main(argv=None):
    args = parse_cli_args(argv)
    root = args.root.resolve()
    relative(root, args.store, exists=False)
    if Path(args.store).parts[:2] != ('.agents', 'state'):
        raise ValueError('Operational store must stay in the local .agents/state directory')
    path = root / args.store
    _, _, mutate = cli_effect(args)
    refresh_state = mutate or args.command in {'inspect', 'show'}
    def execute():
        if args.command == 'init':
            if path.exists():
                raise ValueError('Store exists; resume its saved state')
            limits = {k: getattr(args, k) for k in ['max_active', 'max_depth', 'max_attempts']}
            if any(value is not None and value < 1 for value in limits.values()):
                raise ValueError('Limits must be positive')
            state = {'version': 5, 'created': now(), 'limits': limits, 'limit_sources': {k: 'explicit' if v is not None else 'unset' for k, v in limits.items()}, 'tasks': {}}
        else:
            source = path.read_bytes()
            state = json.loads(source.decode('utf-8'))
            migrate(state)
        tasks = state['tasks']
        if refresh_state:
            refresh_constraints(root, tasks)
        if args.command == 'prepare-context':
            output = prepare_hook_context(root, path, tasks, args.hook_context, args.task_id, args.release_hold,
                                          args.instruction_ref)
        elif args.command == 'add':
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
                'attempts': 0, 'verification': None, 'usage': [],
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
            if bool(args.requirements) != bool(args.request):
                raise ValueError('Supply both --requirements and --request')
            if args.requirements:
                bind_specification(root, tasks[args.id], args.requirements, args.request)
        elif args.command == 'project-bind':
            task = tasks[args.id]
            if not constraints_current(root, tasks, task) or context_changes(root, task):
                raise ValueError('Resolve current authority, holds and context before project binding')
            _, _, binding = _project_read(root, tasks, args.id, args.definition)
            previous = task.get('project_binding')
            if previous is not None:
                _project_current(root, tasks, args.id)
            if previous != binding:
                if task['status'] == 'running':
                    raise ValueError('Stop the active task before changing its project binding')
                if previous is None:
                    if args.user_change:
                        raise ValueError('Initial project binding does not replace a plan')
                    task['project_baseline'] = binding
                    source = {'kind': 'initial-declaration'}
                else:
                    if not args.user_change:
                        raise ValueError('Changed project binding requires user-change evidence')
                    source = user_change_evidence(root, args.user_change, previous, binding, 'project')
                task.setdefault('project_history', []).append({'binding': binding, 'source': source, 'at': now()})
                task['project_binding'] = binding
                task['check_receipts'], task['verification'] = {}, None
                if task['status'] == 'completed':
                    transition(task, 'blocked', 'Check the changed project binding against preserved outputs', 'interrupted')
            output = {'project_id': args.id, 'binding': binding}
        elif args.command == 'project-history':
            output = _project_history(root, tasks, args.id)
        elif args.command == 'project-diff':
            output = _project_diff(root, tasks, args.id, args.from_revision, args.to_revision, args.definition)
        elif args.command == 'project-view':
            capacities = gate.parse_json(args.capacity.encode('utf-8')) if args.capacity is not None else None
            if args.capacity is not None and not isinstance(capacities, dict):
                raise ValueError('Candidate capacities must be a JSON object')
            output = _project_view(root, tasks, args.id, args.role, args.view, args.owner, args.project,
                                   args.priority, capacities, args.github)
            if args.save:
                destination = relative(root, args.save, exists=False)
                sources = {ref['path'] for task in tasks.values() for revision in task.get('project_history', [])
                           for ref in revision['binding'].values()}
                if Path(destination).parts[:2] == ('.agents', 'state') or destination in sources or destination in args.github:
                    raise ValueError('Save a project view outside canonical sources and the task store')
                target = root / destination
                if target.exists():
                    previous = gate.parse_json(target.read_bytes())
                    if not isinstance(previous, dict) or previous.get('artifact_kind') != 'project-view':
                        raise ValueError('Project view save can replace an existing derived project-view only')
                output.update(artifact_kind='project-view', generated_at=now(), project_id=args.id, view=args.view)
                target.parent.mkdir(parents=True, exist_ok=True)
                save(target, output)
        elif args.command == 'project-update':
            output = _project_github_update(root, tasks, args.id, args.issue_url,
                                           gate.parse_json(args.changes.encode('utf-8')), args.expected_updated_at)
        elif args.command == 'project-impact':
            changes = {}
            for value in args.change:
                key, separator, action = value.partition('=')
                if not separator or not key or key in changes:
                    raise ValueError('Use distinct NODE=ACTION changes')
                changes[key] = action
            if args.definition is not None or args.from_revision is not None or args.to_revision is not None:
                if args.node or args.resource or args.task or args.deadline or args.project or args.references or args.change:
                    raise ValueError('Compare plan versions separately from explicit impact selectors')
                output = _project_diff(root, tasks, args.id, args.from_revision, args.to_revision, args.definition)
            else:
                output = _project_impact(root, tasks, args.id, args.node, args.resource, args.task, args.deadline, args.project,
                                         references=args.references, changes=changes if args.change else None)
        elif hasattr(args, 'id'):
            task = tasks[args.id]
            if args.command == 'bind-specification':
                bind_specification(root, task, args.requirements, args.request, args.user_change)
            elif args.command == 'bind-writing':
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
                    native._operation_results({'action_results_verified': [observed]}, [event], outcomes,
                                              authorized_inputs=task.get('external_targets', []))
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
                if args.worker_result and args.execution_result:
                    raise ValueError('Supply one worker result or execution result')
                result, review_kind, worker = args.result, None, None
                proof_error, execution_path = None, None
                evidence_paths = [args.evidence] if args.evidence else []
                if args.worker_result:
                    if args.output is not None or args.input is not None:
                        raise ValueError('Worker results must review the entire candidate; --input/--output selectors are only for execution evidence')
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
                    review_kind = 'worker-result'
                    evidence_paths.append(worker_path)
                elif args.execution_result:
                    execution_path = relative(root, args.execution_result)
                    evidence_paths.append(execution_path)
                    review_kind = 'execution-result'
                    execution_bytes = (root / execution_path).read_bytes()
                    bindings = advanced_bindings(root, tasks, task, args.check)
                    try:
                        observed = gate.parse_json(execution_bytes)
                        event = {k: observed[k] for k in ('event_id', 'operation', 'target', 'status')}
                        if event['operation'] != 'execute_command':
                            raise ValueError('Execution proof requires execute_command')
                        _native()._operation_results({'action_results_verified': [observed]}, [event],
                                                     authorized_inputs=task.get('external_targets', []))
                        if any(row['check_command'] is not None and row['check_command'] != event['target']
                               for row in bindings):
                            raise ValueError('Execution differs from the selected scientific command')
                        result = 'passed'
                    except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
                        result, proof_error = 'failed', str(exc)
                else:
                    raise ValueError('Verification requires an actual --worker-result or --execution-result')
                if args.result is not None and args.result != result:
                    raise ValueError('Expected verdict differs from the actual returned result')
                receipt = {'operation': args.check, 'result': result, 'reviewer': args.reviewer,
                    'review_kind': review_kind, 'evidence': snapshot(root, evidence_paths), 'at': now(),
                    'sequence': 1 + max((row.get('sequence', 0) for row in task['check_receipts'].values()), default=0),
                    'output_ids': args.output, 'input_ids': args.input, 'versions': versions(task, args.output, args.input),
                    'candidate': candidate(task)}
                if worker is not None:
                    receipt.update(worker_result_path=worker_path, worker_result=worker)
                if execution_path is not None:
                    receipt.update(execution_result_path=execution_path, execution_result_hex=execution_bytes.hex(), proof_error=proof_error)
                if worker is not None or execution_path is not None:
                    receipt['advanced_bindings'] = advanced_bindings(root, tasks, task, args.check)
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
                unmet = missing_deliverables(root, task) if status == 'completed' else []
                if status == 'completed' and (not constraints_current(root, tasks, task) or unmet or missing_checks(root, task) or not consumed_current(root, tasks, task) or input_changes(root, task) or context_changes(root, task) or output_changes(root, task)):
                    raise ValueError('Completion requires matching requested outputs/actions, current versions/check receipts and completed dependencies'
                                     + (': ' + json.dumps(unmet, ensure_ascii=False) if unmet else ''))
                if status == 'completed':
                    for owner in [*task_ancestors(tasks, task), task]:
                        if not owner.get('project_binding'):
                            continue
                        current = _project_current(root, tasks, owner['task_id'])
                        if any(n.get('references') for n in current[1]['nodes']):
                            impact = _project_impact(root, tasks, owner['task_id'], [], references=True, current=current)
                            if any(ids and (task is owner or task['task_id'] in ids) for ids in impact['actions'].values()):
                                raise ValueError('Completion requires resolving changed project references through their adopted authority')
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
                if args.source_format == 'legacy':
                    run_hash = digest(args.jsonl)
                    source_text = args.jsonl.read_text(encoding='utf-8-sig')
                else:
                    source_bytes = gate.regular_bytes(args.jsonl)
                    run_hash = hashlib.sha256(source_bytes).hexdigest()
                    source_text = source_bytes.decode('utf-8-sig')
                parse_event = json.loads if args.source_format == 'legacy' else lambda line: gate.parse_json(line.encode('utf-8'))
                events = [parse_event(line) for line in source_text.splitlines() if line.strip()]
                if args.source_format != 'legacy':
                    if args.counter_mode is None:
                        raise ValueError('Declare cumulative, delta or observation usage semantics')
                    if args.elapsed_seconds is not None or args.human_corrections:
                        raise ValueError('Version-3 measures belong to their source event')
                    rows = usage_v3_events(events, args.source_format, args.counter_mode, args.epoch,
                                           args.sequence, args.session_id, run_hash, str(args.jsonl))
                    if not rows:
                        raise ValueError('No usage observations in the declared source')
                    known = [run for other in tasks.values() for run in other['usage'] if run.get('usage_contract') == 3]
                    event_epochs = {}
                    for old in known:
                        event_epochs.setdefault(usage_event_fingerprint(old), set()).add(old['identity']['epoch'])
                    for row in rows:
                        fingerprint = usage_event_fingerprint(row)
                        if event_epochs.get(fingerprint, set()) - {row['identity']['epoch']}:
                            raise ValueError('Usage event already recorded in another epoch')
                        match = next((old for old in known if old['identity'] == row['identity']), None)
                        if match:
                            keys = ('counter', 'last', 'reported_total', 'metadata', 'resources', 'resource_scope', 'operation')
                            if any(match.get(k) != row.get(k) for k in keys):
                                raise ValueError('Conflicting usage event identity')
                            associations = match.setdefault('tasks', [])
                            if args.id not in associations:
                                associations.append(args.id)
                            for ref in row['source_refs']:
                                if ref not in match['source_refs']:
                                    match['source_refs'].append(ref)
                        else:
                            row['tasks'] = [args.id]
                            task['usage'].append(row)
                            known.append(row)
                            event_epochs.setdefault(fingerprint, set()).add(row['identity']['epoch'])
                    rows = None
                elif args.counter_mode is not None:
                    raise ValueError('Legacy importer retains its existing cumulative semantics')
                else:
                    rows = events
                observations, session_id = [], args.session_id
                for event in rows or []:
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
                if rows is not None:
                    identity = {'epoch': args.epoch, 'sequence': args.sequence, 'session_id': session_id, 'observations': observations}
                    positions = {(row['session_id'], row['index']) for row in observations if row['session_id']}
                    if args.epoch is not None and any(
                            run.get('usage_contract') == 2 and run.get('hash') == run_hash
                            and run.get('epoch') is not None and run['epoch'] != args.epoch
                            and positions & {(row['session_id'], row['index']) for row in run['observations']}
                            for other in tasks.values() for run in other['usage']):
                        raise ValueError('Usage source already recorded in another epoch')
                    repeated = any(run.get('usage_contract') == 2 and {key: run[key] for key in identity} == identity and (observations or run['hash'] == run_hash) for t in tasks.values() for run in t['usage'])
                    if not repeated:
                        task['usage'].append({'usage_contract': 2, 'hash': run_hash, **identity,
                            'elapsed_seconds': args.elapsed_seconds, 'imported': now()})
                        task['human_corrections'] += args.human_corrections
        if mutate and refresh_state:
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
        elif args.command == 'context':
            if args.task_id not in tasks:
                raise ValueError('Unknown task ID: ' + args.task_id)
            output = decision_context(root, tasks, args.task_id, decision_ids=args.decision,
                                      query=args.query, history=args.history, values=args.values)
            if args.reference:
                graph = {'nodes': [{'node_id': args.task_id, 'references': [gate.parse_json(value.encode('utf-8'))
                                                                         for value in args.reference]}]}
                output['selected_references'] = _project_references(root, tasks, tasks[args.task_id], graph,
                                                                   values=args.values)[0]
        elif args.command == 'find':
            source_sha256 = hashlib.sha256(source).hexdigest()
            if args.snapshot is not None and args.snapshot != source_sha256:
                raise ValueError('Store changed since the selected search page; repeat find from the first page')
            output = find_tasks(state, args.query, limit=args.limit, offset=args.offset,
                                status=args.status, owner=args.owner, parent=args.parent)
            output.update(store=args.store, store_sha256=source_sha256,
                          next_step='show the selected task ID, restore its original source bodies, then use existing resume/version checks')
        elif args.command == 'show':
            if args.task_id is not None and args.task_id not in tasks:
                raise ValueError(f'Unknown task ID: {args.task_id}')
            if args.task_id is not None:
                output = {**tasks[args.task_id], 'stages': stages(root, tasks, args.task_id),
                          'context_id': context_id(tasks[args.task_id])}
            else:
                output = {**state, 'tasks': {key: {**task, 'stages': stages(root, tasks, key),
                                                  'context_id': context_id(task)}
                                            for key, task in tasks.items()}}
        elif args.command in {'prepare-context', 'project-bind', 'project-view', 'project-impact', 'project-history', 'project-diff', 'project-update'}:
            pass
        else:
            output = {'command': args.command, 'tasks': len(tasks)}
        if mutate:
            save(path, state)
            if args.command in {'add', 'set-context'} and args.hook_context:
                spec = importlib.util.spec_from_file_location('state_codex_hooks', _base / 'codex_hooks.py')
                hooks = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(hooks)
                output['hook_binding'] = hooks.bind_state(args.hook_context, path, root, args.id)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    if mutate or args.command in {'prepare-context', 'project-update'}:
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
