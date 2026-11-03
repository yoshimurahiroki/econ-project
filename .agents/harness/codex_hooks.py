#!/usr/bin/env python3
"""Codex hook transport and native-run association; no semantic verdicts."""
import argparse
import importlib.util
import errno
import json
import os
from pathlib import Path
import re
import stat
import shlex
import shutil
import subprocess
import sys
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

if __name__ == '__main__':
    sys.dont_write_bytecode = True


def sibling(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = Path(__file__).resolve().parent
gate = sibling('hook_local_checks', next(path for path in
               (base / 'local_checks.py', base / 'LOCAL_CHECKS.py') if path.is_file()))


def absolute(value):
    gate.require(isinstance(value, str) and value.strip() and Path(value).is_absolute(),
                 'an absolute path is required')
    path = Path(value)
    gate.require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink path prohibited')
    return path


def save_record(path, value, replace=True):
    """Atomic private operational record."""
    path = absolute(str(path))
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    raw = gate.canonical(value)
    temporary = path.parent / ('.hook-' + str(uuid.uuid4()))
    try:
        with open(temporary, 'xb') as out:
            os.chmod(temporary, 0o600)
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        if replace:
            if path.exists():
                info = path.stat()
                gate.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'invalid operational record')
            gate.replace_path(temporary, path)
        else:
            try:
                gate.publish_file(temporary, path)
            except FileExistsError:
                gate.require(gate.regular_bytes(path) == raw, 'existing hook context differs')
        gate.sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def turn_lock(directory):
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    path = absolute(str(directory / 'event.lock'))
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        gate.require(stat.S_ISREG(os.fstat(fd).st_mode) and os.fstat(fd).st_nlink == 1,
                     'invalid hook lock')
        try:
            gate.lock_fd(fd)
        except BlockingIOError as exc:
            raise ValueError('another callback is checking this turn') from exc
        yield
    finally:
        os.close(fd)


def load_context(path, request):
    path = absolute(str(path))
    raw = gate.regular_bytes(path)
    context = gate.parse_json(raw)
    fields = {'schema_version', 'session_id', 'turn_id', 'nonce', 'cwd', 'plugin_root',
              'plugin_data', 'prompt_sha256'}
    if isinstance(context, dict) and 'run_dir' in context:
        fields.add('run_dir')  # Existing host contexts may retain the former run locator.
    version = context.get('schema_version') if isinstance(context, dict) else None
    if version == 2:
        fields.add('task_id')
        fields.update(key for key in ('formal_selected', 'state_binding', 'operation_binding', 'unbound_operations', 'completion_contract') if key in context)
    gate.require(isinstance(context, dict) and set(context) == fields
                 and type(version) is int and version in (1, 2),
                 'invalid host hook context')
    gate.require(all(isinstance(context[k], str) and context[k].strip()
                     for k in fields - {'schema_version', 'formal_selected', 'state_binding', 'operation_binding', 'unbound_operations', 'completion_contract'})
                 and gate.hexhash(context['prompt_sha256']), 'invalid hook identity or prompt hash')
    gate.require('formal_selected' not in context or type(context['formal_selected']) is bool,
                 'invalid formal-selection state')
    gate.require('state_binding' not in context or isinstance(context['state_binding'], dict),
                 'invalid task state binding')
    gate.require('operation_binding' not in context or isinstance(context['operation_binding'], dict),
                 'invalid operation binding')
    gate.require('unbound_operations' not in context or isinstance(context['unbound_operations'], list),
                 'invalid unbound operation observations')
    root, data = absolute(context['plugin_root']), absolute(context['plugin_data'])
    session = data / 'economics' / gate.sha(context['session_id'].encode())
    expected = (session / 'tasks' / gate.sha(context['task_id'].encode()) if version == 2 else
                session / gate.sha(context['turn_id'].encode()))
    effective = _effective_request(expected) if version == 2 else request
    gate.require(path == expected / 'context.json', 'hook context path mismatch')
    if version == 2:
        gate.require(_read(expected / 'original-prompt.json', {}).get('sha256') == context['prompt_sha256'],
                     'original request differs from the host context')
    gate.require(request == effective and (version == 2 or gate.sha(request) == context['prompt_sha256']),
                 'request differs from the actual task prompt and preserved amendments')
    return {'context_path': str(path), 'context_sha256': gate.sha(raw),
            'session_id': context['session_id'], 'turn_id': context['turn_id'], 'nonce': context['nonce'],
            **({'task_id': context['task_id'], 'effective_request_sha256': gate.sha(effective)} if version == 2 else {})}


CONTEXT_EVENTS = {'UserPromptSubmit', 'PostToolUse', 'SubagentStart', 'SessionStart'}
TERMINAL = {'completed', 'interrupted', 'cancelled'}


def feedback(event, text):
    if event in CONTEXT_EVENTS:
        return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': text}}
    return {'systemMessage': text}


def failure(event, reason, repeated=False, failure_class='recoverable'):
    """A Stop continuation is never limited by count or stop_hook_active."""
    reason = 'Economics task check: ' + reason
    if event in ('PreCompact', 'PostCompact', 'SessionStart'):
        return {'continue': False, 'stopReason': reason, 'systemMessage': reason}
    if event == 'PreToolUse':
        return {'hookSpecificOutput': {'hookEventName': event, 'permissionDecision': 'deny',
                                      'permissionDecisionReason': reason}}
    if event in ('Interrupt', 'SessionStart', 'SubagentStart', 'PostToolUse'):
        return feedback(event, reason)
    if failure_class in ('cancelled', 'permission', 'resource', 'unavailable'):
        return {'continue': False, 'stopReason': reason, 'systemMessage': reason}
    return {'decision': 'block', 'reason': reason}


def _read(path, default=None):
    return gate.parse_json(gate.regular_bytes(path)) if path.exists() else default


def _read_state_store(path):
    """Read the existing state store with the same safe file boundary as snapshots."""
    with gate._open_regular(path) as stream:
        before = os.fstat(stream.fileno())
        try:
            value = json.load(stream, object_pairs_hook=gate._pairs,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError('invalid state store JSON') from exc
        after = os.fstat(stream.fileno())
        current = os.stat(absolute(str(path)), follow_symlinks=False)
    gate.require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode)
                 == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode)
                 == (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns, current.st_mode),
                 'state store changed while reading')
    return value


def _lifecycle(directory):
    if (directory / 'interrupted.json').exists():
        return 'interrupted'
    value = _read(directory / 'lifecycle.json', {})
    gate.require(isinstance(value, dict), 'invalid hook lifecycle')
    return value.get('status', 'active')


def _finish(directory, status):
    save_record(directory / 'lifecycle.json', {'status': status})








def _effective_request(directory):
    original = _read(directory / 'original-prompt.json')
    gate.require(isinstance(original, dict) and isinstance(original.get('text'), str)
                 and original.get('sha256') == gate.sha(original['text'].encode('utf-8')),
                 'fixed original task request is missing or changed')
    text = original['text']
    for row in _read(directory / 'task-messages.json', []):
        if row['kind'] == 'amendment':
            text += '\n\n[User amendment ' + row['turn_id'] + ']\n' + row['text']
    return text.encode('utf-8')




def _resolve_operation_binding(root, operation, conditions, profile):
    policy = sibling('hook_operation_policy', root / 'harness/policy_assets.py')
    owner, _, catalog, assets = policy.discover_policy(
        policy.__file__, operation=operation, conditions=conditions, profile=profile)
    gate.require(Path(policy.__file__).absolute() == (root / 'harness/policy_assets.py').absolute(),
                 'hook policy module does not belong to this runtime')
    selected, contract = policy.select_manifest(catalog, assets, operation, conditions=conditions,
                                                 profile=profile, with_contract=True)
    return owner, selected, contract


def bind_operation(context_path, state_root, operation, conditions=(), profile=None, *,
                   required_outputs=(), required_actions=(), operation_kind=None, authority='', user_change=None, external_targets=()):
    """Adopt the explicitly selected operation and its exact source-bound closure."""
    path = absolute(str(context_path))
    with turn_lock(path.parent):
        context = _read(path)
        gate.require(isinstance(context, dict) and context.get('schema_version') == 2,
                     'operation binding requires a current task context')
        session = absolute(context['plugin_data']) / 'economics' / gate.sha(context['session_id'].encode())
        gate.require(path == session / 'tasks' / gate.sha(context['task_id'].encode()) / 'context.json'
                     and _read(session / 'active-task.json') == {'task_id': context['task_id']},
                     'operation binding is not the active host task context')
        gate.require(absolute(str(state_root)) == absolute(context['cwd']), 'operation root differs from the original task root')
        gate.require(_lifecycle(path.parent) == 'active', 'operation binding requires an active task')
        _effective_request(path.parent)
        root = absolute(context['plugin_root'])
        _, selected, contract = _resolve_operation_binding(root, operation, conditions, profile)
        binding = {'operation': selected['selection']['operation'],
                   'conditions': selected['selection']['conditions'], 'profile': profile,
                   'policy_id': selected['policy_id'], 'selection_sha256': gate.sha(gate.canonical(selected)),
                   'assets': selected['assets'], 'active_rules': selected['active_rules'],
                   'resource_sections': selected['resource_sections'], 'contract': contract}
        updated = {**context, 'operation_binding': binding}
        if required_outputs or required_actions or external_targets:
            gate.require(context.get('state_binding') is None,
                         'the bound state owner already owns the completion contract')
            module = sibling('hook_completion_state', root / 'harness/state.py')
            retained = context.get('completion_contract', {})
            outputs, actions = module.contract(state_root,
                list(required_outputs) if required_outputs else [json.dumps(row) for row in retained.get('required_outputs', [])],
                list(required_actions) if required_actions else [json.dumps(row) for row in retained.get('required_actions', [])])
            operation_kind = operation_kind or retained.get('operation_kind')
            authority = authority or retained.get('authority', '')
            if not any(row['kind'] == 'message' for row in outputs):
                outputs.append({'role': 'response', 'kind': 'message', 'target': 'response'})
            gate.require(operation_kind in {'answer', 'create', 'modify', 'external'}, 'declare the operation kind')
            gate.require(not actions or isinstance(authority, str) and authority.strip(),
                         'requested actions need their actual task authority')
            gate.require(not any(row['kind'] == 'file' for row in outputs) or actions,
                         'file outputs need their producing operation')
            gate.require(all(isinstance(target, str) and target.strip() for target in external_targets),
                         'external target authority must use exact nonempty identifiers')
            targets = sorted({row['target_id'] for row in actions if row['target_kind'] == 'object'} |
                             set(retained.get('external_targets', [])) | set(external_targets))
            record = context.get('completion_contract')
            if record is None:
                record = {'required_outputs': outputs, 'required_actions': actions, 'external_targets': targets}
                module.record_contract(record, {'kind': 'hook-request', 'request_sha256': gate.sha(_effective_request(path.parent))})
            else:
                record = gate.parse_json(gate.canonical(record))
                module.contract_change(state_root, record, outputs, actions, targets, user_change)
            record.update(operation_kind=operation_kind, authority=authority,
                          request_sha256=gate.sha(_effective_request(path.parent)))
            updated['completion_contract'] = record
        if context != updated:
            save_record(path, updated)
        return binding


def _operation_manifest(root, context):
    binding = context.get('operation_binding')
    if binding is None:
        return None
    gate.require(isinstance(binding, dict) and set(binding) ==
                 {'operation', 'conditions', 'profile', 'policy_id', 'selection_sha256',
                  'assets', 'active_rules', 'resource_sections', 'contract'},
                 'invalid operation binding')
    _, selected, contract = _resolve_operation_binding(root, binding['operation'], binding['conditions'], binding['profile'])
    gate.require(selected['policy_id'] == binding['policy_id']
                 and gate.sha(gate.canonical(selected)) == binding['selection_sha256']
                 and selected['assets'] == binding['assets'] and selected['active_rules'] == binding['active_rules']
                 and selected['resource_sections'] == binding['resource_sections'] and contract == binding['contract'],
                 'bound operation sources or closure changed; explicitly rebind the operation')
    return selected




def bind_state(context_path, state_file, state_root, task_id):
    path = absolute(str(context_path))
    context = _read(path)
    gate.require(isinstance(context, dict) and context.get('schema_version') == 2,
                 'state binding requires a current task context')
    directory = path.parent
    session = absolute(context['plugin_data']) / 'economics' / gate.sha(context['session_id'].encode())
    gate.require(path == session / 'tasks' / gate.sha(context['task_id'].encode()) / 'context.json',
                 'state binding is not the active host task context')
    root = absolute(str(state_root))
    gate.require(root == absolute(context['cwd']), 'state root differs from the original task root')
    store = absolute(str(state_file))
    gate.require(store.is_relative_to(root / '.agents/state'), 'task state is outside its existing store')
    state_module = sibling('hook_state_binding', Path(context['plugin_root']) / 'harness/state.py')
    data = _read_state_store(store)
    task = data['tasks'][task_id]
    task_context = task.get('task_context') or {}
    request_sha = gate.sha(_effective_request(directory))
    refs = task_context.get('request_refs', [])
    gate.require(any(row.get('content_sha256') == request_sha and row.get('path')
                     and state_module.digest(root / state_module.relative(root, row['path'])) == request_sha
                     for row in refs), 'state lacks the exact effective request source')
    gate.require(task_context.get('active_instruction_refs') and task.get('authority')
                 and not state_module.context_changes(root, task)
                 and not state_module.effective_constraints(data['tasks'], task, root)['scope_errors'],
                 'state authority, instructions or scope require reconciliation')
    gate.require(all(row.get('path') and state_module.digest(root / state_module.relative(root, row['path']))
                     == row.get('content_sha256') for row in task_context['active_instruction_refs']),
                 'state must retain every applicable instruction source and version')
    binding = {'state_file': str(store), 'state_root': str(root), 'task_id': task_id,
               'effective_request_sha256': request_sha}
    completion = context.get('completion_contract')
    if completion is not None:
        gate.require(all(row in task['required_outputs'] for row in completion['required_outputs'])
                     and all(row in task['required_actions'] for row in completion['required_actions'])
                     and set(completion['external_targets']) <= set(task.get('external_targets', [])),
                     'durable task must retain the original completion requirements and authority')
    previous = context.get('state_binding')
    gate.require(previous is None or all(previous.get(key) == binding[key]
                 for key in ('state_file', 'state_root', 'task_id')),
                 'bound task identity cannot be replaced by another state record')
    save_record(path, {**context, 'state_binding': binding})
    return binding


def _bound_state(directory, root):
    context = _read(directory / 'context.json', {})
    binding = context.get('state_binding')
    if binding is None:
        return None
    gate.require(isinstance(binding, dict) and set(binding) ==
                 {'state_file', 'state_root', 'task_id', 'effective_request_sha256'}, 'invalid task state binding')
    gate.require(binding['effective_request_sha256'] == gate.sha(_effective_request(directory)),
                 'task state must be rebound to the amended request')
    state_root, store = absolute(binding['state_root']), absolute(binding['state_file'])
    gate.require(state_root == absolute(context['cwd']), 'state root differs from the original task root')
    gate.require(store.is_relative_to(state_root / '.agents/state'), 'task state is outside its existing store')
    module = sibling('hook_bound_state', root / 'harness/state.py')
    data = _read_state_store(store)
    task = data['tasks'][binding['task_id']]
    messages = _read(directory / 'task-messages.json', [])
    original = _read(directory / 'original-prompt.json', {})
    actual = {(row.get('turn_id'), row.get('text')) for row in messages}
    actual.add((context.get('turn_id'), original.get('text')))
    for owner in [task, *module.task_ancestors(data['tasks'], task)]:
        for release in owner.get('hold_releases', []):
            message = release.get('message', {})
            gate.require(message.get('source') == 'user' and message.get('source_task_id') == owner['task_id']
                         and message.get('hold_id') == release.get('hold_id')
                         and (message.get('message_id'), message.get('text')) in actual
                         and isinstance(release.get('evidence'), dict) and release['evidence']
                         and not module.changed(state_root, release['evidence']),
                         'hold release does not match a saved actual user message and evidence')
    request_sha = binding['effective_request_sha256']
    gate.require(any(row.get('content_sha256') == request_sha and row.get('path')
                     and module.digest(state_root / module.relative(state_root, row['path'])) == request_sha
                     for row in (task.get('task_context') or {}).get('request_refs', [])),
                 'state no longer binds the effective request source')
    gate.require(task.get('authority') and not module.context_changes(state_root, task)
                 and not module.effective_constraints(data['tasks'], task, state_root)['scope_errors'],
                 'state authority, instructions or scope require reconciliation')
    refs = (task.get('task_context') or {}).get('active_instruction_refs', [])
    gate.require(refs and all(row.get('path') and module.digest(state_root / module.relative(state_root, row['path']))
                              == row.get('content_sha256') for row in refs),
                 'bound instruction sources or versions require reconciliation')
    return module, data, task, state_root


def _completion_task(directory, root):
    """Use the existing hook context, without creating a local state store."""
    context = _read(directory / 'context.json', {})
    contract = context.get('completion_contract')
    if contract is None:
        return None
    module = sibling('hook_completion_state', root / 'harness/state.py')
    gate.require(isinstance(contract, dict) and module.contract_current(Path(context['cwd']), contract)
                 and contract.get('request_sha256') == gate.sha(_effective_request(directory)),
                 'completion requirements or original request need reconciliation')
    outputs, actions = module.contract(Path(context['cwd']),
        [json.dumps(row) for row in contract['required_outputs']],
        [json.dumps(row) for row in contract['required_actions']])
    gate.require(outputs == contract['required_outputs'] and actions == contract['required_actions'],
                 'completion requirements are not normalized')
    scopes = sorted({row['target'] for row in outputs if row['kind'] == 'file'} |
                    {row['target_id'] for row in actions if row['target_kind'] == 'file'})
    task = {**contract, 'task_id': context['task_id'], 'parent': None, 'status': 'running',
            'write_scope': scopes, 'scope': scopes, 'holds': [], 'hold_releases': [], 'completion_contract': 1,
            'outputs': {}, 'action_results': [], 'consumed_inputs': {}, 'read_dependencies': {},
            'consumes': [], 'dependency_versions': {}, 'required_checks': [], 'check_receipts': {}}
    return module, {'tasks': {task['task_id']: task}}, task, Path(context['cwd'])


def _pending_task_holds(directory, bound):
    holds = _read(directory / 'task-holds.json', [])
    if bound is None:
        return holds
    module, data, task, state_root = bound
    messages = _read(directory / 'task-messages.json', [])
    remaining = []
    for hold in holds:
        labels = set(hold.get('target_ids', []))
        released = set()
        for release in task.get('hold_releases', []):
            message = release.get('message', {})
            evidence = release.get('evidence')
            if (not isinstance(evidence, dict) or not evidence or message.get('source') != 'user'
                    or message.get('source_task_id') != task['task_id']
                    or message.get('hold_id') != release.get('hold_id')
                    or not any(row.get('turn_id') == message.get('message_id') and row.get('text') == message.get('text')
                               for row in messages) or module.changed(state_root, evidence)):
                continue
            record = task.get('hold_records', {}).get(release.get('hold_id'), {})
            identifiers = {release.get('hold_id')} | {value.split(':', 1)[-1] for value in record.get('targets', [])}
            released.update(labels & identifiers)
        if not labels or released != labels:
            remaining.append(hold)
    return remaining




def _ids(state):
    result = set()
    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ('requirement_id', 'check_id', 'check') and isinstance(item, str):
                    result.add(item)
                elif isinstance(item, (dict, list)):
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    collect(state.get('needed_actions', []))
    result.update(x for x in state.get('unmet_requirement_ids', []) if isinstance(x, str))
    checks = state.get('checks', {})
    for key in ('failed_checks', 'missing_checks', 'unresolved'):
        collect(checks.get(key, []))
    requirements = checks.get('requirements', {})
    collect(requirements.get('unmet', []))
    collect([item for item in requirements.get('evaluations', []) if item.get('status') != 'pass'])
    return sorted(result)


def _ordinary_candidate(module, task, state_root, message):
    """Identify only required outputs using their current bytes or actual values."""
    candidates = []
    for requirement in task['required_outputs']:
        kind, target = requirement['kind'], requirement['target']
        identity = {'kind': kind, 'role': requirement['role'], 'target': target}
        if kind == 'file':
            path = state_root / module.relative(state_root, target, exists=False)
            if path.is_file():
                identity['content_sha256'] = module.digest(path)
            elif path.exists():
                raise ValueError('required output is not a regular file')
            else:
                identity['content_sha256'] = None
        elif kind == 'message':
            identity['content_sha256'] = gate.sha(message.encode('utf-8')) if isinstance(message, str) else None
        elif kind == 'object':
            row = task['outputs'].get(target, {})
            identity['content_sha256'] = module.content_version(row) if row.get('kind') == 'object' else None
        else:
            raise ValueError('unknown required output kind')
        candidates.append(identity)
    return gate.sha(gate.canonical(candidates)) if candidates else None


def _ordinary_attempt_state(root, directory, state, message):
    """Use the bound task store's existing unmet contracts for ordinary Stop guidance."""
    result = dict(state)
    try:
        bound = _bound_state(directory, root) or _completion_task(directory, root)
        if bound is None:
            return result
        module, data, task, state_root = bound
        result['candidate_file_sha256'] = _ordinary_candidate(module, task, state_root, message)
        actions = list(result.get('needed_actions', []))
        for item in module.missing_deliverables(state_root, task):
            if item in ('explicit-completion-contract-required', 'contract-revision-or-evidence-changed'):
                actions.append({'action': 'reconcile-task-contract', 'check_id': item})
            elif isinstance(item, str):
                actions.append({'action': 'satisfy-required-output', 'requirement_id': item})
            elif isinstance(item, dict):
                actions.append({'action': 'complete-required-action', **item})
        for check in module.missing_checks(state_root, task):
            actions.append({'action': 'complete-required-check', 'check_id': check})
        result['needed_actions'] = actions
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError):
        # The existing Stop guard and restoration path retain the reconciliation failure.
        pass
    return result


def _attempt_context(root, directory, state):
    """Identify governing inputs, without hashing the mutable task store or tool payloads."""
    try:
        request = gate.sha(_effective_request(directory))
        context = _read(directory / 'context.json', {})
        binding = context.get('completion_contract')
        if context.get('state_binding') is not None:
            bound = _bound_state(directory, root)
            module, data, task, _ = bound
            keys = ('task_id', 'authority', 'task_context', 'required_outputs', 'required_actions',
                    'required_checks', 'check_targets', 'scope', 'external_targets', 'holds',
                    'hold_records', 'specification')
            binding = [{key: owner.get(key) for key in keys}
                       for owner in [task, *module.task_ancestors(data['tasks'], task)]]
        return gate.sha(gate.canonical({'request': request, 'binding': binding,
            'policy_id': state.get('policy_id'),
            'policy_manifest_sha256': state.get('policy_manifest_sha256')}))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError):
        # An unverified governing context cannot establish a repeat.
        return None


def _unmet_action_ids(state):
    """Identify explicit unresolved action targets without saving their payloads."""
    keys = ('target_kind', 'target_id', 'operation')
    return sorted({gate.sha(gate.canonical({key: row[key] for key in keys}))
                   for row in state.get('needed_actions', []) if isinstance(row, dict)
                   and all(isinstance(row.get(key), str) and row[key] for key in keys)})


def _condition_identity(state, candidate, context):
    """Hash machine-readable condition and action keys, excluding free-form messages."""
    ids = _ids(state)
    fields = ('action', 'requirement_id', 'check_id', 'check', 'capability', 'role', 'id',
              'path', 'operation', 'target_kind', 'target_id', 'capability_status')
    actions = [{key: row[key] for key in fields if isinstance(row.get(key), str) and row[key]}
               for row in state.get('needed_actions', []) if isinstance(row, dict)]
    actions = [row for row in actions if row.get('action')]
    if context is None or not (ids or actions):
        return None
    encoded = sorted({gate.canonical(row).decode('utf-8') for row in actions})
    return gate.sha(gate.canonical({'context': context, 'candidate': candidate,
                                    'unresolved_ids': ids, 'actions': encoded}))


def _attempt(state, reason, previous=None, context_sha256=None):
    """Only relevant, validator-consistent evidence can count as progress."""
    actions = state.get('needed_actions') or [{'action': 'correct-failure-cause', 'reason': reason}]
    checks = state.get('checks', {})
    evidence = []
    for value in checks.get('operation_results', []):
        if value.get('status') in ('completed', 'passed', 'consistent'):
            evidence.append('operation:' + gate.sha(gate.canonical(value)))
    repairs = []
    for key in ('failed_checks', 'missing_checks', 'unresolved'):
        for row in checks.get(key, []):
            identity = row.get('requirement_id') or row.get('check_id') or row.get('check') or key
            matched = [action for action in actions if any(action.get(k) == identity for k in
                       ('requirement_id', 'check_id', 'check'))]
            repairs.append({'id': identity, 'cause': row.get('message') or row.get('reason') or key,
                            'next_actions': matched or [{'action': 'correct-failure-cause', 'check_id': identity,
                                'reason': row.get('message') or row.get('reason') or key}]})
    if not repairs:
        repairs = [{'id': identity, 'cause': reason, 'next_actions': actions}
                   for identity in _ids(state) or ['hook-stop']]
    current = {'schema_version': 2, 'status': 'blocked',
               'candidate_sha256': state.get('candidate_file_sha256'),
               'record_sha256': state.get('record_sha256'), 'unresolved_ids': _ids(state),
               'next_actions': actions, 'failure_class': 'recoverable',
               'evidence': sorted(evidence), 'reason': reason, 'progress': 'none',
               'repair_plan': repairs,
               'candidate_changed_recheck_required': False}
    current['context_sha256'] = context_sha256
    current['unresolved_action_ids'] = _unmet_action_ids(state)
    current['condition_sha256'] = _condition_identity(state, current['candidate_sha256'], context_sha256)
    current['condition_history'] = []
    current['repeated_unresolved_conditions'] = False
    if previous is not None and previous.get('schema_version') == 2:
        same_context = (context_sha256 is not None and previous.get('context_sha256') == context_sha256)
        if same_context:
            if (current['candidate_sha256'] != previous.get('candidate_sha256')
                    and (previous.get('unresolved_ids') or previous.get('condition_sha256'))):
                current['candidate_changed_recheck_required'] = True
            elif (set(previous.get('unresolved_ids', [])) - set(current['unresolved_ids'])
                  or set(previous.get('unresolved_action_ids', [])) - set(current['unresolved_action_ids'])):
                current['progress'] = 'unresolved-condition-satisfied'
            elif set(current['evidence']) - set(previous.get('evidence', [])):
                current['progress'] = 'relevant-validated-evidence-added'
            # A changed record or submission by itself does not establish progress.
            if current['progress'] == 'none' and not current['candidate_changed_recheck_required']:
                current['condition_history'] = list(previous.get('condition_history', []))
                identity = current['condition_sha256']
                current['repeated_unresolved_conditions'] = bool(identity and identity in current['condition_history'])
    identity = current['condition_sha256']
    if identity:
        history = [value for value in current['condition_history'] if value != identity]
        current['condition_history'] = (history + [identity])[-16:]
    return current


def _previous(path):
    value = _read(path)
    if value is None:
        return None
    gate.require(isinstance(value, dict), 'invalid hook attempt record')
    if set(value) == {'failures'}:
        gate.require(type(value['failures']) is int and value['failures'] >= 0, 'invalid legacy hook attempts')
        return None  # Read conversion; old counts have no stopping semantics.
    gate.require(value.get('schema_version') == 2, 'unsupported hook attempt schema')
    if 'condition_history' in value:
        history = value['condition_history']
        gate.require(isinstance(history, list) and len(history) <= 16
                     and all(gate.hexhash(item) for item in history), 'invalid hook condition history')
    for key in ('context_sha256', 'condition_sha256'):
        gate.require(value.get(key) is None or gate.hexhash(value[key]), 'invalid hook condition identity')
    if 'unresolved_action_ids' in value:
        gate.require(isinstance(value['unresolved_action_ids'], list)
                     and all(gate.hexhash(item) for item in value['unresolved_action_ids']),
                     'invalid hook unresolved action identities')
    return value


def _instructions(root, state, manifest=None, stage=None, role=None, reader_id=None, *, detailed=True):
    policy = sibling('hook_policy_assets', root / 'harness/policy_assets.py')
    owner, _, current, _ = policy.discover_policy(policy.__file__)
    gate.require(Path(policy.__file__).absolute() == (root / 'harness/policy_assets.py').absolute(),
                 'hook policy module does not belong to this runtime')
    gate.require(manifest is None or manifest['policy_id'] == current['policy_id'], 'adopted policy version changed')
    manifest = manifest or current
    state = {**state, 'unmet_ids': _ids(state)}
    packet = policy.instruction_context(owner, manifest=manifest, status=state,
                                        stage=stage, role=role, reader_id=reader_id)
    gate.require(isinstance(packet, dict) and isinstance(packet.get('text'), str)
                 and packet['text'].strip(), 'shared instruction context is unavailable')
    return packet['text'] if detailed else packet['short_text']


def _restoration(root, directory, state, manifest=None):
    """Restore fixed inputs, never a generated substitute for the host prompt."""
    context = _read(directory / 'context.json', {})
    original = _read(directory / 'original-prompt.json')
    if original is None and (directory / 'run/request.txt').is_file():
        original = {'text': gate.regular_bytes(directory / 'run/request.txt').decode('utf-8')}
    prompt = original.get('text') if isinstance(original, dict) else None
    gate.require(isinstance(prompt, str) and gate.sha(prompt.encode('utf-8')) == context.get('prompt_sha256'),
                 'restore-fixed-request: obtain the exact host original; do not reconstruct it from a candidate')
    request = _effective_request(directory).decode('utf-8') if context.get('schema_version') == 2 else prompt
    policy = sibling('hook_restoration_policy', root / 'harness/policy_assets.py')
    owner, _, current, _ = policy.discover_policy(policy.__file__)
    gate.require(Path(policy.__file__).absolute() == (root / 'harness/policy_assets.py').absolute(),
                 'hook policy module does not belong to this runtime')
    gate.require(manifest is None or manifest['policy_id'] == current['policy_id'], 'adopted policy version changed')
    selected = _operation_manifest(root, context)
    packet = policy.instruction_context(owner, manifest=manifest or selected or current,
        status={**state, 'request_sha256': gate.sha(request.encode('utf-8')), 'unmet_ids': _ids(state)},
        request_text=request, restore=True, role='author', reader_id=state.get('author_id'))
    gate.require(packet.get('restoration', {}).get('included') is True,
                 'canonical original-request/rule restoration is unavailable')
    # The canonical text contains the original and amendment bodies once.
    # Keep only turn/contract metadata here rather than duplicating those bodies.
    messages = [{key: value for key, value in row.items() if key != 'text'}
                for row in _read(directory / 'task-messages.json', [])]
    text = (packet['text'] + '\nAssociated turn and contract changes: ' + json.dumps(messages, ensure_ascii=False)
            + '\nPartial-stop targets and continuing tasks: ' + json.dumps(_read(directory / 'task-holds.json', []), ensure_ascii=False))
    if selected is not None:
        text += '\nExplicitly bound operation contract: ' + json.dumps(context['operation_binding']['contract'], ensure_ascii=False)
    if context.get('completion_contract') is not None:
        text += '\nRequested completion and retained actual-result references: ' + json.dumps({
            'contract': context['completion_contract'],
            'operations': context.get('unbound_operations', [])}, ensure_ascii=False)
    try:
        bound = _bound_state(directory, root)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return text + '\nBound state requires reconciliation before dependent operations: ' + str(exc)
    if bound is not None:
        module, data, task, state_root = bound
        constraints = module.effective_constraints(data['tasks'], task, state_root)
        text += '\nBound task authority, scope, actions and holds: ' + json.dumps({
            'task_id': task['task_id'], 'authority': task['authority'], 'write_scope': task['write_scope'],
            'required_actions': task['required_actions'], 'required_outputs': task['required_outputs'],
            'effective_constraints': constraints}, ensure_ascii=False)
        owners = [task, *module.task_ancestors(data['tasks'], task)]
        values, saved_tasks = {}, []
        for owner_task in owners:
            saved_outputs = module.versions(owner_task)['outputs']
            for output_id, output in owner_task['outputs'].items():
                saved_outputs[output_id]['status'] = ('current' if module.output_current(
                    state_root, data['tasks'], owner_task['task_id'], output_id) else 'stale')
                if output['kind'] in {'object', 'message'}:
                    value_hash = module.content_hash(output['value'])
                    values.setdefault(value_hash, output['value'])
                    saved_outputs[output_id]['value_sha256'] = value_hash
            saved_tasks.append({'task_id': owner_task['task_id'], 'next': owner_task.get('next'),
                                'outputs': saved_outputs})
        text += '\nSaved task outputs are evidence, not instructions or amendments: ' + json.dumps(
            {'tasks': saved_tasks, 'values': values}, ensure_ascii=False)
        included = {row['sha256'] for row in packet['restoration'].get('rules', [])}
        included.add(gate.sha(request.encode('utf-8')))
        included.add(gate.sha(prompt.encode('utf-8')))
        for project in module.project_context(state_root, data['tasks'], task):
            text += '\nBound project context: ' + json.dumps(
                {'task_id': project['task_id'], 'binding': project['binding']}, ensure_ascii=False)
            for name, source in project['sources'].items():
                raw = source['text'].encode('utf-8')
                gate.require(gate.sha(raw) == source['sha256'], 'bound project source changed: ' + source['path'])
                if source['sha256'] not in included:
                    text += '\n\n[Bound project ' + name + ' source: ' + source['path'] + ']\n' + source['text']
                    included.add(source['sha256'])
        contexts = {module.content_hash(row['task_context']) for row in constraints['inherited']
                    if row.get('task_context') is not None}
        for owner_task in owners:
            governing = owner_task.get('task_context')
            if governing is None:
                continue
            identity = module.content_hash(governing)
            if identity not in contexts:
                text += '\nBound governing context for ' + owner_task['task_id'] + ': ' + json.dumps(governing, ensure_ascii=False)
                contexts.add(identity)
            for field in ('request_refs', 'active_instruction_refs'):
                for ref in governing[field]:
                    if not ref.get('path'):
                        continue
                    name = module.relative(state_root, ref['path'])
                    raw = gate.regular_bytes(state_root / name)
                    gate.require(gate.sha(raw) == ref['content_sha256'], 'bound governing source changed: ' + name)
                    if ref['content_sha256'] not in included:
                        text += '\n\n[Bound governing source: ' + name + ']\n' + raw.decode('utf-8')
                        included.add(ref['content_sha256'])
    return text


def _changed(directory, state):
    """Changes to adopted task state require a fresh restoration."""
    view = {key: state.get(key) for key in ('status', 'candidate_file_sha256',
            'request_sha256', 'policy_id', 'policy_manifest_sha256', 'current_policy_manifest_sha256',
            'task_binding_sha256', 'operation_binding_sha256', 'unbound_operations_sha256',
            'needed_actions', 'unmet_requirement_ids')}
    view['task_state_sha256'] = state.get('task_state_semantic_sha256', state.get('task_state_sha256'))
    view['unresolved_ids'] = _ids(state)
    signature = gate.sha(gate.canonical(view))
    old = _read(directory / 'reinjection.json', {})
    saved = {'state_sha256': signature, 'raw_task_state_sha256': state.get('task_state_sha256')}
    if 'compactions' in old:
        saved['compactions'] = old['compactions']
    save_record(directory / 'reinjection.json', saved)
    return old.get('state_sha256') != signature


def _relevant_state_hash(data, task):
    """Keep task dependencies and descendants while excluding telemetry and unrelated tasks."""
    tasks = data['tasks']
    descendants, pending = set(), [task['task_id']]
    while pending:
        key = pending.pop()
        if key in descendants:
            continue
        gate.require(key in tasks, 'task dependency is missing')
        descendants.add(key)
        pending.extend(child for child, value in tasks.items() if value.get('parent') == key)
    selected, pending = set(), list(descendants)
    while pending:
        key = pending.pop()
        if key in selected:
            continue
        selected.add(key)
        if key not in tasks:
            continue
        row = tasks[key]
        if row.get('parent'):
            pending.append(row['parent'])
        pending.extend(value for value in row.get('after', []) if isinstance(value, str))
        pending.extend(item['producer_id'] for item in row.get('consumes', [])
                       if isinstance(item, dict) and isinstance(item.get('producer_id'), str))
    relevant = {key: ({field: value for field, value in tasks[key].items() if field != 'usage'}
                      if key in tasks else {'missing': True}) for key in sorted(selected)}
    return gate.sha(gate.canonical(relevant))


def _authorized_settings(directory, module, task):
    """Read only the operator's existing task configuration, never imported facts."""
    reader = getattr(module, 'optimization_settings', None)
    return reader(task) if callable(reader) else {}


def _feature_enabled(directory, module, task, name):
    settings = _authorized_settings(directory, module, task)
    features = settings.get('features') or {}
    return settings.get('enabled') is True and features.get(name) is True


def _experience_hint(root, directory, bound, event):
    """Return optional pending-tool feedback and an honest operational status."""
    if bound is None:
        return '', None
    module, data, task, state_root = bound
    try:
        settings = _authorized_settings(directory, module, task)
        if not (settings.get('enabled') is True and (settings.get('features') or {}).get('experience') is True):
            return '', None
        plan = settings.get('experience_plan')
        if plan is None:
            return '', {'status': 'no-plan', 'delivery': 'not-emitted'}
        binding = _read(directory / 'context.json')['state_binding']
        store = Path(binding['state_file']).relative_to(state_root).as_posix()
        experience = sibling('hook_experience', root / 'harness/experience.py')
        result = experience.automatic_feedback(state_root, store, data['tasks'], task['task_id'], plan, event)
        presentation = result.get('presentation') if isinstance(result, dict) else None
        status = result.get('status') if isinstance(result, dict) else None
        if (not isinstance(status, str) or not isinstance(presentation, list)
                or not all(isinstance(item, str) for item in presentation)):
            return '', {'status': 'invalid-feedback-result', 'delivery': 'not-emitted'}
        hint = '\n'.join(presentation)
        record = {'status': status, 'delivery': 'prepared-pending-host-delivery' if hint else 'not-emitted'}
        if gate.hexhash(result.get('fact_version')):
            record['fact_version'] = result['fact_version']
        return hint, record
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError) as exc:
        # Preserve the authority decision while recording the optional feature failure.
        return '', {'status': 'internal-error', 'error_type': type(exc).__name__, 'delivery': 'not-emitted'}


def _diagnostic_identity(response):
    """Hash a specific observed failure while preserving diagnostic numbers and locations."""
    if not isinstance(response, dict):
        return None
    text = response.get('output') or response.get('error') or response.get('stderr')
    if not isinstance(text, str):
        return None
    if not re.search(r'(?i)\berror\b|exception|failed|failure|\b\w+Error\b', text):
        return None
    lines = [line.strip() for line in text.splitlines()
             if re.search(r'(?i)(?:\d|\b(?:error|exception|failed|failure)\b|\b\w+Error\b)', line)]
    if not lines:
        return None
    text = '\n'.join(lines)
    text = re.sub(r'\b\d{4}-\d\d-\d\d[T ][0-9:.+-]+Z?\b', '<time>', text)
    text = re.sub(r'(?<!\w)/tmp/[^\s:]+', '<temporary>', text)
    return gate.sha(text.encode('utf-8'))


def _preflight_key(event):
    keys = ('session_id', 'turn_id', 'tool_use_id')
    if all(isinstance(event.get(key), str) and event[key] for key in keys):
        return gate.sha(gate.canonical({key: event[key] for key in keys}))
    return None


def _target_version(target, cwd):
    """Return a version only for an actual regular file inside the task root."""
    try:
        path, root = absolute(str(target)), absolute(str(cwd))
        path.relative_to(root)
        if not path.exists():
            return {'known': True, 'sha256': None}
        gate.require(path.is_file(), 'edit target is not a regular file')
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            gate.require(stat.S_ISREG(before.st_mode), 'nonregular edit target')
            import hashlib
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
            after = os.fstat(stream.fileno())
            current = os.stat(path, follow_symlinks=False)
            fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_mode')
            gate.require(all(getattr(before, key) == getattr(after, key) == getattr(current, key)
                             for key in fields), 'edit target changed while reading')
        return {'known': True, 'sha256': digest.hexdigest()}
    except (OSError, ValueError):
        return {'known': False, 'sha256': None}


def _saved_check_return(event, module, task, directory):
    """Match an actual terminal producer return to the existing check-run record."""
    response = event.get('tool_response')
    output = response.get('output') if isinstance(response, dict) else None
    if not isinstance(output, str):
        return None
    try:
        result = json.loads(output)
    except ValueError:
        return None
    if (not isinstance(result, dict) or result.get('command') != 'run-check'
            or result.get('task_id') != task.get('task_id')
            or str(event.get('tool_name', '')).rsplit('__', 1)[-1].split('.')[-1] != 'exec_command'):
        return None
    try:
        binding = _read(directory / 'context.json')['state_binding']
        root = Path(binding['state_root'])
        store = Path(binding['state_file']).relative_to(root).as_posix()
        args = event.get('tool_input') or {}
        native = {'call_args_text': json.dumps({'cmd': args.get('cmd'),
                    'workdir': args.get('workdir') or event.get('cwd')}),
                  'return_text': json.dumps(response)}
        if module._check_wrapper(root, store, task['task_id'], result.get('check_id'), native) != result:
            return None
    except (OSError, ValueError, TypeError, KeyError):
        return None
    for check in task.get('check_runs', []):
        if (check.get('run_id') != result.get('run_id') or check.get('check_id') != result.get('check_id')
                or check.get('producer_sha256') != result.get('producer_sha256')
                or check.get('status') != result.get('status')):
            continue
        body = {key: value for key, value in check.items() if key != 'producer_sha256'}
        if module.content_hash(body) != check['producer_sha256']:
            continue
        return check
    return None


def _observation(event, directory, module, task, prior=()):
    """Build a sanitized callback observation without inferring terminal success."""
    tool = str(event['tool_name']).rsplit('__', 1)[-1].split('.')[-1].lower()
    args = event.get('tool_input') if isinstance(event.get('tool_input'), dict) else {}
    response = event.get('tool_response')
    response = response if isinstance(response, dict) else {}
    process = args.get('session_id') if tool == 'write_stdin' else response.get('session_id')
    process_sha = gate.sha(str(process).encode()) if isinstance(process, (str, int)) else None
    exit_code = response.get('exit_code') if type(response.get('exit_code')) is int else None
    failed = _tool_failed(event)
    connector = event.get('tool_name') in {'mcp__codex_apps__github_update_ref',
                                           'mcp__codex_apps__plugin_creator_update_plugin'}
    if (exit_code is not None or failed or
            connector and isinstance(event.get('tool_response'), dict)):
        phase = 'terminal'
        outcome = 'failed' if failed else 'success'
    elif process_sha:
        phase, outcome = 'launch' if tool != 'write_stdin' else 'pending', 'unknown'
    elif response.get('isError') is False or response.get('success') is True:
        phase, outcome = 'terminal', 'success'
    else:
        phase, outcome = 'unknown', 'unknown'
    event_sha = gate.sha(event['tool_use_id'].encode('utf-8'))
    session_sha = gate.sha(event['session_id'].encode('utf-8'))
    turn_sha = gate.sha(event['turn_id'].encode('utf-8'))
    launch = next((row for row in reversed(prior) if process_sha and row.get('process_sha256') == process_sha
                   and row.get('phase') == 'launch' and row.get('host_session_sha256') == session_sha
                   and row.get('turn_sha256') == turn_sha), None)
    operation_args = {key: value for key, value in args.items()
                      if key not in {'yield_time_ms', 'max_output_tokens'}}
    operation_sha = (launch.get('operation_sha256') if launch and tool == 'write_stdin' else
                     gate.sha(gate.canonical({'tool': tool, 'input': operation_args})))
    context_sha = module.context_id(task)
    input_sha = gate.sha(gate.canonical({'consumed_inputs': task.get('consumed_inputs'),
        'read_dependencies': task.get('read_dependencies'), 'consumes': task.get('consumes'),
        'dependency_versions': task.get('dependency_versions'), 'specification': task.get('specification')}))
    before = _read(directory / 'preflight' / ((_preflight_key(event) or '') + '.json'), {})
    edits = []
    if outcome == 'success' and before.get('source') == 'PreToolUse':
        for target in before.get('edit_targets', []):
            after = _target_version(target['path'], event['cwd'])
            if target.get('version', {}).get('known') and after['known'] and target['version']['sha256'] != after['sha256']:
                edits.append(gate.sha(target['path'].encode('utf-8')))
    check = _saved_check_return(event, module, task, directory)
    if check is not None:
        phase, outcome = 'terminal', 'failed' if check.get('status') == 'failed' else 'success'
        try:
            stdout = bytes.fromhex(check['stdout_hex'])
            stderr = bytes.fromhex(check['stderr_hex'])
            gate.require(gate.sha(stdout) == check['stdout_sha256'] and gate.sha(stderr) == check['stderr_sha256'],
                         'saved check output changed')
            reason = check.get('failure_reason')
            diagnostic = {'output': ('Saved check failure: ' + reason + '\n' if reason else '')
                          + (stdout + b'\n' + stderr).decode('utf-8', errors='replace')}
        except (ValueError, TypeError, KeyError):
            diagnostic = {}
    else:
        diagnostic = response
    cause = _diagnostic_identity(diagnostic) if outcome == 'failed' else None
    try:
        root = Path(event['cwd'])
        checks = [{'kind': 'check', 'value': item} for item in module.missing_checks(root, task)]
        deliverables = [{'kind': 'deliverable', 'value': item} for item in module.missing_deliverables(root, task)]
        unresolved = sorted(gate.sha(gate.canonical(item)) for item in checks + deliverables)
    except (OSError, ValueError, TypeError, KeyError):
        unresolved = None
    preflight_path = directory / 'preflight' / (gate.sha(gate.canonical(event)) + '.json')
    source = None
    if preflight_path.is_file():
        source = {'path': str(preflight_path), 'sha256': gate.sha(gate.regular_bytes(preflight_path))}
    return {'schema_version': 1, 'source': 'PostToolUse', 'host_session_sha256': session_sha,
        'turn_sha256': turn_sha, 'event_sha256': event_sha, 'task_id': task['task_id'],
        'context_sha256': context_sha, 'input_sha256': input_sha, 'tool': tool,
        'process_sha256': process_sha, 'launch_event_sha256': launch.get('event_sha256') if launch else None,
        'phase': phase, 'outcome': outcome, 'terminal_exit': exit_code,
        'call_sha256': gate.sha(gate.canonical(args)), 'return_sha256': gate.sha(gate.canonical(event.get('tool_response'))),
        'producer_event_sha256': gate.sha(gate.canonical(event)), 'operation_sha256': operation_sha,
        'diagnostic_sha256': cause, 'edited_file_sha256': edits, 'unresolved_checks': unresolved,
        'check_source': ({'check_id': check['check_id'], 'run_id': check['run_id'],
                          'producer_sha256': check['producer_sha256']} if check else None),
        'source_preflight': source, 'source_evidence': None, 'provenance_authenticated': False,
        'observed_at': datetime.now(timezone.utc).isoformat()}


def _hook_usage_source(module, task, item, directory):
    """Match an imported fact to its saved hook-owned source and task binding."""
    identity, operation = item.get('identity') or {}, item.get('operation') or {}
    if item.get('usage_contract') != 3 or identity.get('source_id') != 'codex-hook-preflight':
        return None
    current = _read(directory / 'context.json', {})
    for ref in item.get('source_refs', []):
        try:
            source = absolute(ref['path'])
            raw = gate.regular_bytes(source)
            if gate.sha(raw) != ref['sha256'] or source.parent.name != 'preflight':
                continue
            task_dir = source.parent.parent
            context = _read(task_dir / 'context.json', {})
            session = context.get('session_id')
            binding = context.get('state_binding') or {}
            expected = (absolute(context['plugin_data']) / 'economics' / gate.sha(session.encode('utf-8'))
                        / 'tasks' / gate.sha(context['task_id'].encode('utf-8')))
            if (task_dir != expected or context.get('plugin_data') != current.get('plugin_data')
                    or binding.get('task_id') != task['task_id']
                    or binding.get('state_file') != (current.get('state_binding') or {}).get('state_file')
                    or gate.sha(session.encode('utf-8')) != identity.get('session_id')):
                continue
            preflight = gate.parse_json(raw)
            row = preflight.get('usage_observation') or {}
            if (row.get('session_id') != identity.get('session_id') or row.get('turn_id') != item.get('turn_id')
                    or row.get('event_id') != identity.get('event_id')
                    or module.usage_operation(row.get('operation')) != operation
                    or preflight.get('input_sha256') != operation.get('call_sha256')):
                continue
            return {'path': str(source), 'sha256': ref['sha256'], 'preflight': preflight,
                    'directory': task_dir}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            continue
    return None


def _prior_hook_observations(task, session_sha, turn_sha, directory, module):
    """Use only observations retained by the existing usage importer."""
    rows = []
    for item in task.get('usage', []):
        identity, operation = item.get('identity') or {}, item.get('operation') or {}
        if (item.get('usage_contract') != 3 or identity.get('source_id') != 'codex-hook-preflight'
                or identity.get('session_id') != session_sha or item.get('turn_id') != turn_sha):
            continue
        if _hook_usage_source(module, task, item, directory) is None:
            continue
        rows.append({'event_sha256': identity.get('event_id'), 'host_session_sha256': session_sha,
                     'turn_sha256': turn_sha, 'process_sha256': operation.get('process_id'),
                     'phase': 'launch' if operation.get('phase') == 'started' else operation.get('phase'),
                     'operation_sha256': operation.get('operation_sha256'), 'sequence': item.get('sequence', 0)})
    return sorted(rows, key=lambda row: row['sequence'])


def _hook_usage_row(event, directory, module, task):
    session = gate.sha(event['session_id'].encode('utf-8'))
    turn = gate.sha(event['turn_id'].encode('utf-8'))
    prior = _prior_hook_observations(task, session, turn, directory, module)
    observation = _observation(event, directory, module, task, prior)
    phase = {'launch': 'started', 'pending': 'pending', 'terminal': 'terminal'}.get(observation['phase'], 'unknown')
    status = {'success': 'success', 'failed': 'failure'}.get(observation['outcome'],
             'pending' if phase in {'started', 'pending'} else 'unknown')
    event_id = gate.sha(gate.canonical([session, turn, observation['event_sha256']]))
    checks = observation['unresolved_checks']
    operation = {'tool': observation['tool'] if len(observation['tool']) <= 256 else None,
        'call_id': observation['event_sha256'],
        'stage': ('check:' + gate.sha(observation['check_source']['check_id'].encode('utf-8'))
                  if observation['check_source'] else 'operation:' + observation['operation_sha256']), 'phase': phase, 'status': status,
        'exit_code': observation['terminal_exit'], 'process_id': observation['process_sha256'],
        'call_sha256': observation['call_sha256'], 'return_sha256': observation['return_sha256'],
        'context_sha256': observation['context_sha256'], 'input_sha256': observation['input_sha256'],
        'operation_sha256': observation['operation_sha256'], 'diagnostic_sha256': observation['diagnostic_sha256'],
        'edited_file_sha256': observation['edited_file_sha256'],
        'unresolved_check_sha256': checks,
        'launch_event_sha256': observation['launch_event_sha256'],
        'effects_sha256': gate.sha(gate.canonical(observation['edited_file_sha256'])) if observation['edited_file_sha256'] else None}
    return {'type': 'usage.observed', 'source_id': 'codex-hook-preflight', 'session_id': session,
            'turn_id': turn, 'event_id': event_id, 'operation': operation}


def _import_hook_observation(event, root, directory):
    """Import the already-written preflight record using the existing state owner."""
    source = directory / 'preflight' / (gate.sha(gate.canonical(event)) + '.json')
    preflight = _read(source, {})
    row = preflight.get('usage_observation')
    if not isinstance(row, dict):
        return None
    bound = _bound_state(directory, root)
    if bound is None:
        return None
    module, _, task, state_root = bound
    if not _feature_enabled(directory, module, task, 'loops'):
        return None
    for old in task.get('usage', []):
        if (old.get('identity') or {}).get('event_id') == row['event_id']:
            gate.require(old.get('operation') == module.usage_operation(row['operation']),
                         'conflicting callback identity requires reconciliation')
            return row, False
    prior = _prior_hook_observations(task, row['session_id'], row['turn_id'], directory, module)
    sequence = max((item['sequence'] for item in prior), default=-1) + 1
    binding = _read(directory / 'context.json')['state_binding']
    store = Path(binding['state_file']).relative_to(state_root).as_posix()
    epoch = 'hook-' + row['turn_id']
    command = [sys.executable, '-B', str(root / 'harness/state.py'), '--root', str(state_root),
               '--store', store, 'usage', task['task_id'], '--jsonl', str(source),
               '--source-format', 'usage-event', '--counter-mode', 'observation',
               '--epoch', epoch, '--sequence', str(sequence)]
    result = subprocess.run(command, cwd=state_root, capture_output=True, text=True)
    gate.require(result.returncode == 0, 'state observation importer failed: ' + result.stderr.strip()[:500])
    return row, True


def focus_saved_check(module, task, check_id, *, run_id=None, view='selected', offset=0, limit=100):
    """Project a saved run-check log while retaining its complete original in state."""
    gate.require(view in {'selected', 'stdout', 'stderr'} and type(offset) is int and offset >= 0
                 and type(limit) is int and 1 <= limit <= 500, 'invalid log view')
    matches = [row for row in task.get('check_runs', []) if row.get('check_id') == check_id
               and (run_id is None or row.get('run_id') == run_id)]
    gate.require(matches, 'saved check run is unavailable')
    record = matches[-1]
    body = {key: value for key, value in record.items() if key != 'producer_sha256'}
    gate.require(module.content_hash(body) == record.get('producer_sha256'), 'saved check record changed')
    lines = []
    for name in ('stdout', 'stderr'):
        try:
            raw = bytes.fromhex(record[name + '_hex'])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError('saved check stream is invalid') from exc
        gate.require(gate.sha(raw) == record.get(name + '_sha256'), 'saved check stream changed')
        for number, line in enumerate(raw.decode('utf-8', errors='replace').splitlines(), 1):
            if view == 'selected' and not re.search(r'(?i)\d|error|fail|exception|traceback|passed|warning', line):
                continue
            if view not in {'selected', name}:
                continue
            # A secret-like assignment is never copied into the compact display.
            safe = ('[redacted credential-bearing line]' if
                    re.search(r'(?i)\b(password|secret|api[_-]?key|access[_-]?token|authorization)\s*[:=]', line)
                    else line)
            lines.append({'stream': name, 'line': number, 'text': safe})
    if view == 'selected':
        def importance(item):
            text = item['text']
            return (0 if re.search(r'(?i)\berror\b|exception|failed|failure|\b\w+Error\b', text)
                    else 1 if 'traceback' in text.casefold() or re.search(r'\bfile\b.*\bline\b', text, re.I)
                    else 2)
        lines.sort(key=lambda item: (importance(item), item['stream'], item['line']))
    chosen = lines[offset:offset + limit]
    result = {'task_id': task['task_id'], 'check_id': check_id, 'run_id': record['run_id'],
            'status': record['status'], 'exit_code': record['exit_code'],
            'producer_sha256': record['producer_sha256'], 'stdout_sha256': record['stdout_sha256'],
            'stderr_sha256': record['stderr_sha256'], 'source': 'task.check_runs', 'view': view,
            'offset': offset, 'total_lines': len(lines), 'next_offset': offset + len(chosen) if offset + len(chosen) < len(lines) else None,
            'lines': chosen}
    if record.get('failure_reason'):
        result['failure_reason'] = record['failure_reason']
    return result


def focus_saved_research(module, task, *, view='selected', offset=0, limit=100):
    """Project the existing combined research log without modifying its saved output."""
    gate.require(view in {'selected', 'log'} and type(offset) is int and offset >= 0
                 and type(limit) is int and 1 <= limit <= 500, 'invalid log view')
    record = task.get('outputs', {}).get('research:execution') or {}
    gate.require(record.get('kind') == 'object' and module.content_version(record) == record.get('version'),
                 'saved research execution is unavailable or changed')
    value = record.get('value') or {}
    gate.require(isinstance(value.get('log'), str), 'saved research log is unavailable')
    lines = []
    for number, line in enumerate(value['log'].splitlines(), 1):
        if view == 'selected' and not re.search(r'(?i)\d|error|fail|exception|traceback|passed|warning', line):
            continue
        safe = ('[redacted credential-bearing line]' if
                re.search(r'(?i)\b(password|secret|api[_-]?key|access[_-]?token|authorization)\s*[:=]', line)
                else line)
        lines.append({'line': number, 'text': safe})
    if view == 'selected':
        lines.sort(key=lambda item: (0 if re.search(r'(?i)\berror\b|exception|failed|failure|\b\w+Error\b', item['text'])
                                    else 1 if re.search(r'(?i)traceback|\bfile\b.*\bline\b', item['text']) else 2,
                                    item['line']))
    chosen = lines[offset:offset + limit]
    return {'task_id': task['task_id'], 'source': 'task.outputs.research:execution',
            'content_version': record['version'], 'returncode': value.get('returncode'),
            'view': view, 'offset': offset, 'total_lines': len(lines),
            'next_offset': offset + len(chosen) if offset + len(chosen) < len(lines) else None, 'lines': chosen}


def evaluate_loop(events, completed_turn_lengths):
    """Compare one observed turn with completed-turn lengths; return an advisory candidate."""
    unique = {}
    for row in events:
        identity = row.get('identity') or {}
        event_id = identity.get('event_id')
        if event_id and event_id not in unique:
            unique[event_id] = row
    ordered = sorted(unique.values(), key=lambda row: (row.get('sequence', 0), row.get('index', 0)))
    boundary = 0
    for index in range(1, len(ordered)):
        previous, current = ordered[index - 1].get('operation') or {}, ordered[index].get('operation') or {}
        left, right = previous.get('unresolved_check_sha256'), current.get('unresolved_check_sha256')
        if (left is not None and right is not None and set(right) < set(left)
                and previous.get('context_sha256') == current.get('context_sha256')):
            boundary = index
    segment = ordered[boundary:]
    edits, failures, signatures = {}, [], {}
    for row in segment:
        operation = row.get('operation') or {}
        for target in operation.get('edited_file_sha256') or []:
            edits[target] = edits.get(target, 0) + 1
        if operation.get('phase') != 'terminal' or operation.get('status') != 'failure':
            continue
        failures.append(row)
        keys = ('stage', 'operation_sha256', 'context_sha256', 'input_sha256', 'diagnostic_sha256')
        signature = tuple(operation.get(key) for key in keys)
        if all(signature):
            signatures.setdefault(signature, []).append(row)
    repeated = sum(len(rows) - 1 for rows in signatures.values())
    fraction = repeated / len(failures) if failures else 0.0
    lengths = sorted(value for value in completed_turn_lengths if type(value) is int and value > 0)
    p90 = None
    if len(lengths) >= 5:
        point = .9 * (len(lengths) - 1)
        lower = int(point)
        p90 = lengths[lower] + (lengths[min(lower + 1, len(lengths) - 1)] - lengths[lower]) * (point - lower)
    churn = max(edits.values(), default=0)
    broad = len(edits) >= 3 and sum(edits.values()) >= 4
    candidate = (len(ordered) >= 20 and (churn >= 4 or broad) and len(failures) >= 6
                 and fraction >= .2 and p90 is not None and len(ordered) >= p90)
    repeats = [rows[-1] for rows in signatures.values() if len(rows) > 1]
    selected = max(repeats, key=lambda row: (row.get('sequence', 0), row.get('index', 0))) if repeats else None
    return {'completed_calls': len(ordered), 'post_progress_calls': len(segment),
            'max_edits_to_file': churn, 'distinct_edited_files': len(edits), 'failures': len(failures),
            'repeated_failures': repeated, 'repeated_fraction': fraction,
            'completed_baseline_turns': len(lengths), 'p90_calls': p90,
            'progress_boundary': boundary, 'candidate': candidate,
            'already_attempted': any((row.get('operation') or {}).get('opportunity') is True for row in segment),
            'selected_event_id': (selected.get('identity') or {}).get('event_id') if selected else None}


def _verified_loop_rows(module, task, directory, session=None, turn=None):
    result = []
    for row in task.get('usage', []):
        identity = row.get('identity') or {}
        if (identity.get('source_id') != 'codex-hook-preflight'
                or (session is not None and identity.get('session_id') != session)
                or (turn is not None and row.get('turn_id') != turn)):
            continue
        source = _hook_usage_source(module, task, row, directory)
        if source:
            result.append((row, source))
    return result


def _completed_turn_lengths(module, data, task, directory, state_root):
    """Use only completed tasks whose saved hook lifecycle identifies the final turn."""
    lengths = []
    for candidate in data['tasks'].values():
        if (candidate['task_id'] == task['task_id'] or candidate.get('status') != 'completed'
                or candidate.get('operation_kind') != task.get('operation_kind')):
            continue
        try:
            if not module.completion_current(state_root, data['tasks'], candidate['task_id']):
                continue
            rows = _verified_loop_rows(module, candidate, directory)
            groups = {}
            for row, source in rows:
                groups.setdefault((row['identity']['session_id'], row['turn_id'], str(source['directory'])), []).append(row)
            for (_, turn, folder), values in groups.items():
                folder = Path(folder)
                if _lifecycle(folder) != 'completed':
                    continue
                context = _read(folder / 'context.json', {})
                messages = _read(folder / 'task-messages.json', [])
                final_turn = messages[-1].get('turn_id') if messages else context.get('turn_id')
                if isinstance(final_turn, str) and gate.sha(final_turn.encode('utf-8')) == turn:
                    lengths.append(len({row['identity']['event_id'] for row in values}))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
            continue
    return lengths


def _pending_loop_advice(event, row, bound, directory):
    module, data, task, state_root = bound
    rows = [item for item, _ in _verified_loop_rows(module, task, directory, row['session_id'], row['turn_id'])]
    sequence = max((item.get('sequence', 0) for item in rows), default=-1) + 1
    proposed = {'identity': {'event_id': row['event_id']}, 'operation': row['operation'], 'sequence': sequence, 'index': 0}
    # The inexpensive conjunction must hold before scanning completed-turn evidence.
    quick = evaluate_loop(rows + [proposed], [1, 1, 1, 1, 1])
    if not quick['candidate'] or quick['already_attempted']:
        return None
    outcome = evaluate_loop(rows + [proposed], _completed_turn_lengths(module, data, task, directory, state_root))
    if (not outcome['candidate'] or outcome['already_attempted']
            or outcome['selected_event_id'] != row['event_id']):
        return None
    check = _saved_check_return(event, module, task, directory)
    if check is not None and check.get('status') == 'failed':
        row['operation']['opportunity'] = True
        return {'assessment': outcome, 'check_id': check['check_id'], 'run_id': check['run_id'],
                'producer_sha256': check['producer_sha256']}
    if row['operation'].get('diagnostic_sha256') is None:
        return None
    row['operation']['opportunity'] = True
    return {'assessment': outcome, 'callback_diagnostic_sha256': row['operation']['diagnostic_sha256']}


def _tool_failed(event):
    """A returned failure selects more instruction detail."""
    returned = event.get('tool_response')
    if not isinstance(returned, dict):
        return False
    tool = event.get('tool_name')
    if tool in {'mcp__codex_apps__github_update_ref', 'mcp__codex_apps__plugin_creator_update_plugin'}:
        native = sibling('hook_connector_outcome', next(path for path in
                         (base / 'native_check.py', base / 'NATIVE_CHECK.py') if path.is_file()))
        try:
            arguments = event.get('tool_input')
            operation, target = native._connector_call_target(tool, arguments)
            adapter = native._OPERATION_ADAPTERS[(tool, operation)][0]
            native._connector_operation(returned, arguments, operation, target, adapter)
        except (ValueError, TypeError, KeyError, RecursionError):
            return True
        return False
    return (returned.get('isError') is True or returned.get('success') is False
            or bool(returned.get('error'))
            or (type(returned.get('exit_code')) is int and returned['exit_code'] != 0))




def _coordinator(directory):
    return ('The result owner retains the original request, applicable rules, authority and holds, '
            'integrates actual returns, and completes the required result and verification.')


def _active_directory(event, data):
    session = data / 'economics' / gate.sha(event['session_id'].encode())
    turn = event.get('turn_id')
    if event['hook_event_name'] != 'SessionStart':
        gate.require(isinstance(turn, str) and turn.strip(), 'missing host turn_id')
        membership = _read(session / 'turns' / (gate.sha(turn.encode()) + '.json'))
        if membership is not None:
            gate.require(isinstance(membership, dict) and set(membership) == {'task_id', 'directory'}
                         and isinstance(membership['task_id'], str), 'invalid turn task membership')
            return session / gate.safe_relative(membership['directory'])
    pointer = session / 'active-task.json'
    active = _read(pointer)
    if active is not None:
        gate.require(isinstance(active, dict) and set(active) == {'task_id'}
                     and isinstance(active['task_id'], str) and active['task_id'], 'invalid active task pointer')
        current = session / 'tasks' / gate.sha(active['task_id'].encode())
        if event['hook_event_name'] == 'UserPromptSubmit':
            prompt = event.get('prompt', '')
            if (_new_task_requested(prompt) or
                    (_lifecycle(current) in TERMINAL and not _continuation_prompt(prompt)
                     and _stop_requested(prompt)['kind'] == 'none')):
                return session / 'tasks' / gate.sha(turn.encode())
        return current
    if event['hook_event_name'] != 'SessionStart':
        # Migrate an active v1 task without replacing its fixed request.
        if event['hook_event_name'] == 'UserPromptSubmit' and _new_task_requested(event.get('prompt', '')):
            return session / 'tasks' / gate.sha(turn.encode())
        previous = _read(session / 'active-turn.json')
        if previous is not None:
            old = session / gate.sha(previous['turn_id'].encode())
            if (old / 'context.json').is_file() and _lifecycle(old) not in TERMINAL:
                return old
        return session / 'tasks' / gate.sha(turn.encode())
    active = _read(session / 'active-turn.json')
    if active is None:
        return None
    gate.require(isinstance(active, dict) and set(active) == {'turn_id'}
                 and isinstance(active['turn_id'], str) and active['turn_id'], 'invalid active turn pointer')
    return session / gate.sha(active['turn_id'].encode())


def _new_task_requested(prompt):
    return bool(re.match(r'^\s*(?:新しい(?:独立した?)?(?:依頼|タスク)|別(?:の|件の)(?:依頼|タスク)|new\s+(?:independent\s+)?task)\s*[:：]', prompt, re.I))


def _continuation_prompt(prompt):
    text = unicodedata.normalize('NFKC', prompt).casefold().strip(' \t\r\n。.!?？')
    return bool(re.fullmatch(r'(?:まだ|進捗(?:は)?|状況(?:は)?|続けて(?:ください)?|継続して(?:ください)?|再開して(?:ください)?|continue|resume|status|any update|are you done)', text))


def _stop_requested(prompt, task_id=None):
    """Recognize current-work stop commands, excluding quoted/conditional uses.

    Hooks have no language-model intent API. This recognizes command syntax;
    Interrupt remains the host's authoritative cancellation event.
    """
    result = {'kind': 'none', 'target_ids': [], 'preserved_task_ids': [], 'source_span': None}
    text = unicodedata.normalize('NFKC', prompt).casefold()
    text = re.sub(r'```[\s\S]*?```|`[^`]*`|「[^」]*」|『[^』]*』|"[^"]*"', '', text)
    english_partial = re.match(r'^(?:please\s+)?(?:stop|cancel|abort|halt)\s+(.+?)(?:,\s*and|\s+and)\s+(?:continue|keep working on)\s+(.+)', text)
    if english_partial:
        return {'kind': 'partial', 'target_ids': [english_partial.group(1)],
                'preserved_task_ids': [task_id] if task_id else [],
                'source_span': {'start': 0, 'end': len(prompt), 'text': prompt}}
    # A named stopped operation and an explicitly continuing parent are distinct
    # scopes. Keep the actual wording pending target resolution; never promote it
    # to a cancellation of the preserved task.
    stop = re.search(r'(?P<target>[^。\n、,]+?)(?:を|は)(?:中止|停止|中断|キャンセル|終了)して', text)
    continuing = re.search(r'(?:続け|継続し|進め)|\b(?:continue|keep working)\b', text)
    if (stop and not re.search(r'(?:場合|たら|なら|もし|とき|後で)|\b(?:if|when|after|once)\b', text)
            and not re.search(r'(?:しては(?:いけない|ならない)|しない|しなく|せず|ないで)', text[stop.end()-2:])
            and (continuing or not re.fullmatch(r'(?:この|今の|現在の)?(?:全体|全部|すべて|全て|作業|タスク|依頼|研究|監査)', stop['target'].strip()))):
        return {'kind': 'partial', 'target_ids': [stop['target'].strip()],
                'preserved_task_ids': [task_id] if task_id else [],
                'source_span': {'start': 0, 'end': len(prompt), 'text': prompt}}
    def whole():
        return {'kind': 'task', 'target_ids': [task_id] if task_id else [],
                'preserved_task_ids': [], 'source_span': {'start': 0, 'end': len(prompt), 'text': prompt}}
    for clause in re.split(r'[。;；\n]|[.!?](?=\s|$)', text):
        clause = clause.strip()
        if not clause:
            continue
        if re.search(r'(?:停止|中止|終了|中断|キャンセル|取り消|取消|やめ|止め).{0,8}(?:しない|しなく|せず|ないで|ないこと)', clause):
            continue
        # Future/conditional stopping is not a request to cancel now.
        if re.search(r'(?:たら|なら|場合|とき|時に|後で|あとで)', clause):
            continue
        if re.search(r'(?:(?:今の|現在の|この)(?:作業|タスク|処理|依頼|調査|監査)|これ以上).{0,16}(?:続け|進め|継続し|実行し|再開し)(?:ないでください|なくて(?:いい|結構))', clause):
            return whole()
        ja_command = re.search(r'(?:停止|中止|終了|中断|キャンセル)(?:して(?:ください|下さい|くれ|ほしい|欲しい|いただきたい|頂きたい)?|し(?=[、,])|しなさい|せよ|しろ|する(?:よう|ことを)(?:お願い|要求|指示)|を?お願い(?:します|いたします))(?:\s*$|[、,]|から|して|します)', clause)
        ja_command = ja_command or re.search(r'(?:取り消して|取消して|やめて|止めて|やめ(?=[、,])|止め(?=[、,]))(?:ください|下さい|くれ|ほしい|欲しい)?(?:\s*$|[、,]|から)', clause)
        if ja_command:
            prefix = clause[:ja_command.start()]
            target = re.search(r'([^、,\s]+)(?:を|は|の)(?:一旦|いったん|今すぐ|すぐに|もう)?$', prefix)
            # Stop a named server/file operation as requested; do not cancel
            # the entire research task merely because that verb occurs.
            if target is None or re.search(r'(?:作業|タスク|課題|依頼|研究|調査|監査|処理|実行|開発|実装|検証|ワークフロー|この件|全部|すべて|全て|これ|それ)$', target.group(1)):
                return whole()
        if clause in {'停止', '中止', '終了', '中断', 'キャンセル', '/stop', '/cancel'}:
            return whole()
        # An imperative starts the clause; names such as "stop condition" do not.
        command = re.sub(r'^(?:and\s+|please\s+|now\s*[,，]\s*)+', '', clause)
        if re.match(r'^(?:do\s+not|don[’\']t)\s+(?:continue|proceed\s+with|keep\s+working\s+on|resume)\s+(?:(?:the\s+)?current|this)\s+(?:task|work|run)\b', command):
            return whole()
        if re.match(r'(?:do\s+not|don[’\']t|never|not)\s+', command):
            continue
        if re.search(r'\b(?:after|once|until|when|if|before)\b', command):
            continue
        if re.match(r'^(?:stop|cancel|abort|halt|terminate|end)(?:\s+(?:now|please))?\s*$', command):
            return whole()
        if re.match(r'^(?:stop|cancel|abort|halt|terminate|end)\s+(?:(?:all|the|this|current|ongoing|active|remaining|entire)\s+)*(?:work|task|run|operation|process|job|execution|research|audit|review|implementation|workflow|everything)\b', command):
            return whole()
        if re.match(r'^stop\s+(?:working|running|continuing|processing)\b', command):
            return whole()
    return result










def _pending_parent_returns(directory):
    record = _read(directory / 'pending-parent-returns.json', {'returns': []})
    gate.require(isinstance(record, dict) and set(record) == {'returns'}
                 and isinstance(record['returns'], list), 'invalid pending child returns')
    for row in record['returns']:
        gate.require(isinstance(row, dict) and isinstance(row.get('agent_id'), str)
                     and isinstance(row.get('agent_type'), str)
                     and gate.hexhash(row.get('return_sha256'))
                     and gate.hexhash(row.get('payload_sha256')),
                     'invalid pending child return')
    return record['returns']


def _queue_parent_return(directory, row):
    """Retain each observed return until a parent context callback presents it."""
    pending = _pending_parent_returns(directory)
    pending = [old for old in pending if old['payload_sha256'] != row['payload_sha256']]
    save_record(directory / 'pending-parent-returns.json', {'returns': pending + [row]})


def _parent_tool_callback(event, directory):
    """A callback explicitly identifying an observed child cannot consume its parent handoff."""
    agent_id = event.get('agent_id')
    return not (isinstance(agent_id, str) and agent_id
                and (directory / 'children' / (gate.sha(agent_id.encode()) + '.json')).is_file())


def _child_assignment(root, directory, agent_id):
    """Recover only an exact retained launch or complete fixed support assignment."""
    context = _read(directory / 'context.json', {})
    child = _read(directory / 'children' / (gate.sha(agent_id.encode()) + '.json'), {})
    launch = child.get('launch_observation') if isinstance(child, dict) else None
    if isinstance(launch, dict):
        observed = launch.get('event')
        if (isinstance(observed, dict) and launch.get('payload_sha256') == gate.sha(gate.canonical(observed))
                and _spawn_assignment(observed, agent_id)):
            return {'source': 'children/' + gate.sha(agent_id.encode()) + '.json#launch_observation',
                    'source_sha256': launch['payload_sha256'], 'observation': observed,
                    'provenance_authenticated': False}
    ref = child.get('assignment_reference') if isinstance(child, dict) else None
    if isinstance(ref, dict):
        bound = _bound_state(directory, root)
        if bound is not None:
            module, _, task, state_root = bound
            refs = (task.get('task_context') or {}).get('request_refs', [])
            valid = [item for item in refs if item.get('source_id') == ref.get('source_id')
                     and item.get('path') == ref.get('path') and item.get('content_sha256') == ref.get('sha256')]
            if len(valid) == 1:
                raw = gate.regular_bytes(state_root / module.relative(state_root, ref['path']))
                gate.require(gate.sha(raw) == ref['sha256'], 'child assignment source changed')
                return {'source': ref['path'], 'source_sha256': ref['sha256'], 'assignment': raw.decode('utf-8'),
                        'bound_task_id': task['task_id'], 'provenance_authenticated': False}
    matches = []
    for row in context.get('unbound_operations', []):
        if isinstance(row, dict) and _spawn_assignment(row, agent_id):
            matches.append(row)
    if len(matches) == 1:
        row = matches[0]
        return {'source': 'context.json#unbound_operations', 'source_sha256': gate.sha(gate.canonical(row)),
                'observation': row, 'provenance_authenticated': False}
    return None


def _spawn_assignment(event, agent_id=None):
    name = event.get('tool_name')
    inputs, response = event.get('tool_input'), event.get('tool_response')
    if isinstance(response, str):
        try:
            response = gate.parse_json(response.encode('utf-8'))
        except (ValueError, TypeError):
            return None
    if (name not in {'spawn_agent', 'collaboration.spawn_agent', 'functions.collaboration.spawn_agent'}
            or not isinstance(inputs, dict) or not isinstance(response, dict)
            or _tool_failed({'tool_response': response})):
        return None
    identity = response.get('agent_id')
    messages = [inputs[key] for key in ('message', 'prompt') if key in inputs]
    if (not isinstance(identity, str) or not identity.strip() or identity.strip() != identity
            or agent_id is not None and identity != agent_id or not messages
            or any(not isinstance(value, str) or not value.strip() for value in messages)
            or len(set(messages)) != 1):
        return None
    return identity


def _capture_child_launch(directory, event):
    agent_id = _spawn_assignment(event)
    if agent_id is None:
        return
    path = directory / 'children' / (gate.sha(agent_id.encode()) + '.json')
    existing = _read(path, {})
    gate.require(isinstance(existing, dict) and existing.get('agent_id', agent_id) == agent_id,
                 'child launch identity changed')
    gate.require(len(gate.canonical(event)) <= gate.MAX_BYTES, 'child launch observation exceeds the existing record limit')
    launch = {'event': event, 'payload_sha256': gate.sha(gate.canonical(event)), 'provenance_authenticated': False}
    gate.require(existing.get('launch_observation') in (None, launch), 'child launch assignment conflicts')
    if existing.get('launch_observation') is None:
        save_record(path, {**existing, 'agent_id': agent_id, 'launch_observation': launch})


def bind_child_assignment(context_path, state_root, agent_id, source_id, source_sha256):
    """Bind an existing named task-context source to an observed child identity."""
    path = absolute(str(context_path))
    with turn_lock(path.parent):
        context = _read(path)
        gate.require(isinstance(context, dict) and context.get('schema_version') == 2,
                     'child assignment binding requires a current task context')
        session = absolute(context['plugin_data']) / 'economics' / gate.sha(context['session_id'].encode())
        gate.require(path == session / 'tasks' / gate.sha(context['task_id'].encode()) / 'context.json'
                     and _read(session / 'active-task.json') == {'task_id': context['task_id']}
                     and _lifecycle(path.parent) == 'active', 'child assignment requires the active task')
        gate.require(absolute(str(state_root)) == absolute(context['cwd']), 'child assignment root differs from the task root')
        gate.require(isinstance(agent_id, str) and agent_id.strip() == agent_id and agent_id
                     and source_id == 'child-assignment:' + agent_id and gate.hexhash(source_sha256),
                     'child assignment requires its exact agent-specific source ID and hash')
        root = absolute(context['plugin_root'])
        bound = _bound_state(path.parent, root)
        gate.require(bound is not None, 'bind existing authorized task state before the child assignment')
        module, _, task, work = bound
        refs = (task.get('task_context') or {}).get('request_refs', [])
        matches = [row for row in refs if row.get('source_id') == source_id
                   and row.get('content_sha256') == source_sha256 and row.get('path')]
        gate.require(len(matches) == 1, 'exact child assignment source is absent from bound task context')
        relative = module.relative(work, matches[0]['path'])
        raw = gate.regular_bytes(work / relative)
        gate.require(gate.sha(raw) == source_sha256 and raw.decode('utf-8').strip(),
                     'child assignment source changed or is empty')
        child_path = path.parent / 'children' / (gate.sha(agent_id.encode()) + '.json')
        child = _read(child_path)
        gate.require(isinstance(child, dict) and child.get('agent_id') == agent_id,
                     'child identity has not been observed')
        reference = {'source_id': source_id, 'path': relative, 'sha256': source_sha256}
        if child.get('assignment_reference') != reference:
            save_record(child_path, {**child, 'assignment_reference': reference})
        return reference


def _child_recovery_tool(event, root):
    """Allow read and existing state/parent-recovery paths while assignment is missing."""
    tool, inputs = event.get('tool_name'), event.get('tool_input')
    if not isinstance(tool, str) or not isinstance(inputs, dict):
        return False
    name = tool.rsplit('__', 1)[-1].split('.')[-1].lower()
    if name in {'read', 'read_file', 'read_text_file', 'list_directory', 'search_files', 'view_image'}:
        return True
    if tool in {'collaboration.send_message', 'functions.collaboration.send_message'}:
        return True
    if name not in {'bash', 'exec_command', 'run_command'}:
        return False
    command = inputs.get('command') if name == 'bash' else inputs.get('cmd')
    if not isinstance(command, str) or re.search(r'[;&|<>\n`]|\$|[\r\x00]', command):
        return False
    parts = shlex.split(command)
    if not parts:
        return False
    if _trusted_read_program(parts[0]) and not any(part.startswith(('--pre', '--hostname-bin')) for part in parts):
        return True
    if parts[0] not in ('python', 'python3') or len(parts) < 3:
        return False
    index = 2 if parts[1] == '-B' and len(parts) > 3 else 1
    target = _tool_target(parts[index], event['cwd'])
    tail = parts[index+1:]
    offset = 0
    while offset < len(tail):
        item = tail[offset]
        if item in ('--root', '--store'):
            if offset + 1 >= len(tail):
                return False
            offset += 2
        elif any(item.startswith(option + '=') and item[len(option)+1:] for option in ('--root', '--store')):
            offset += 1
        else:
            break
    if offset >= len(tail):
        return False
    command, args = tail[offset], tail[offset+1:]
    if target == str((root / 'harness/codex_hooks.py').resolve()):
        return command == 'bind-child-assignment'
    if target != str((root / 'harness/state.py').resolve()):
        return False
    if command in ('show', 'find', 'summary'):
        return True
    if command != 'inspect':
        return False
    return (not args or len(args) == 2 and args[0] == '--stale-seconds' and args[1].isdigit()
            or len(args) == 1 and args[0].startswith('--stale-seconds=')
            and args[0].partition('=')[2].isdigit())


def _child(event, root, directory, state, manifest):
    agent_id, agent_type = event.get('agent_id'), event.get('agent_type')
    gate.require(isinstance(agent_id, str) and agent_id.strip()
                 and isinstance(agent_type, str) and agent_type.strip(), 'missing host child identity')
    path = directory / 'children' / (gate.sha(agent_id.encode()) + '.json')
    observed = _read(path)
    start = {'agent_id': agent_id, 'agent_type': agent_type, 'status': 'host-start-observed'}
    if event['hook_event_name'] == 'SubagentStart':
        restored = _restoration(root, directory, state, manifest)
        gate.require(observed is None or (observed.get('agent_id') == agent_id
                     and observed.get('agent_type') in (None, agent_type)), 'host child identity changed')
        start['start_observation'] = {'event': 'SubagentStart', 'agent_id': agent_id,
            'payload_sha256': gate.sha(gate.canonical(event)),
            'observed_at': datetime.now(timezone.utc).isoformat(), 'source': 'hook-callback'}
        for key in ('launch_observation', 'assignment_reference'):
            if isinstance(observed, dict) and key in observed:
                start[key] = observed[key]
        save_record(path, start)
        text = _instructions(root, state, manifest, 'review', agent_type, agent_id)
        return feedback('SubagentStart', text + '\n' + restored +
                        '\nComplete the assigned scope and return its actual result to the parent.')
    gate.require(type(event.get('stop_hook_active')) is bool, 'missing child Stop re-entry state')
    message = event.get('last_assistant_message')
    gate.require(isinstance(message, str) and message.strip(), 'return the assigned scope before child Stop')
    body = message.encode('utf-8')
    gate.require(len(body) <= gate.MAX_BYTES, 'child return exceeds text budget')
    gate.require(isinstance(observed, dict) and observed.get('agent_id') == agent_id
                 and observed.get('agent_type') == agent_type, 'child start has not been observed')
    start['start_observation'] = observed.get('start_observation')
    for key in ('launch_observation', 'assignment_reference'):
        if key in observed:
            start[key] = observed[key]
    returned = {'event': 'SubagentStop', 'agent_id': agent_id, 'payload_sha256': gate.sha(gate.canonical(event)),
                'observed_at': datetime.now(timezone.utc).isoformat(), 'source': 'hook-callback'}
    start['return_observation'] = returned
    return_sha = gate.sha(body)
    initial = {**start, 'status': 'returned-awaiting-coordinator-check',
               'return_sha256': return_sha, 'return_text': message, 'scope': 'child-assignment-only'}
    save_record(directory / 'children' / 'returns' / (returned['payload_sha256'] + '.json'),
                {'agent_id': agent_id, 'agent_type': agent_type, 'return_sha256': return_sha,
                 'return_text': message, 'payload_sha256': returned['payload_sha256']}, replace=False)
    save_record(path, initial)
    pending = {'agent_id': agent_id, 'agent_type': agent_type, 'return_sha256': return_sha,
               'payload_sha256': returned['payload_sha256'], 'status': initial['status'],
               'scope': 'child-assignment-only'}
    _queue_parent_return(directory, pending)
    try:
        _restoration(root, directory, state, manifest)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError) as exc:
        save_record(path, {**initial, 'status': 'restoration-check-failed', 'scope_error': str(exc)})
        _queue_parent_return(directory, {**pending, 'status': 'restoration-check-failed', 'scope_error': str(exc)})
        raise
    return {}




def _explicit_user_wait(directory):
    """Only use an explicit wait instruction in the saved actual user text."""
    texts = [_read(directory / 'original-prompt.json', {}).get('text', '')]
    texts += [row.get('text', '') for row in _read(directory / 'task-messages.json', [])
              if row.get('kind') == 'amendment']
    waiting = False
    for text in texts:
        text = re.sub(r'```[\s\S]*?```|`[^`]*`|「[^」]*」|『[^』]*』|"[^"]*"', '', text)
        for clause in re.split(r'[。.!?！？;；\n]', unicodedata.normalize('NFKC', text).casefold()):
            if re.search(r"\b(?:do not|don't|never)\s+wait\b|(?:待たない|待たず|待っては|待たなくて|待機しない)", clause):
                waiting = False
                continue
            if re.search(r'\b(?:unless|if)\b|(?:場合|なら|たら)', clause):
                continue
            if re.search(r'\bwait\s+(?:for|until)\s+(?:(?:my|the user[’\']?s|the next)\s+)+(?:next\s+)?(?:message|input|instruction|reply|response)\b', clause):
                waiting = True
            if re.search(r'(?:私の|ユーザーの)?次の(?:指示|入力|メッセージ|連絡|回答|返答)を待(?:つ|って|ち|機)', clause):
                waiting = True
            if re.search(r'(?:残りの指示を待(?:つ|って|ち|機)|(?:以後|その後|以降)(?:は)?指示待ち)', clause):
                waiting = True
    return waiting


def _ordinary_wait_leaf(module, data, task, state_root, directory, message):
    """Validate the completed phase while retaining the held parent contract."""
    tasks = data['tasks']
    constraints = module.effective_constraints(tasks, task, state_root)
    holds = constraints['holds']
    gate.require(_explicit_user_wait(directory) and task['status'] == 'blocked'
                 and task.get('blocked_reason') == 'user_hold' and task.get('holds')
                 and holds and all(row.get('targets') for row in holds),
                 'explicit user wait and a target-specific current user hold are required')
    labels = {row['hold_id'] for row in holds} | {target.split(':', 1)[-1]
              for row in holds for target in row['targets']}
    gate.require(all(row.get('target_ids') and set(row['target_ids']) <= labels
                     for row in _pending_task_holds(directory, (module, data, task, state_root))),
                 'unresolved user hold is not represented in the current state')
    gate.require(task.get('completion_contract') == 1 and module.contract_current(state_root, task)
                 and not constraints['scope_errors'] and not module.input_changes(state_root, task)
                 and not module.context_changes(state_root, task) and not module.output_changes(state_root, task)
                 and module.consumed_current(state_root, tasks, task), 'parent task versions or contract changed')
    def held(kind, target, operation=None):
        for row in holds:
            if operation is None and row['operations']:
                continue
            if operation is not None and row['operations'] and operation not in row['operations']:
                continue
            for item in row['targets']:
                if kind == 'file' and item.startswith('file:') and module.scopes_overlap(item[5:], target):
                    return True
                if kind == 'object' and item == 'object:' + target:
                    return True
        return False
    def output_held(row):
        return held(row['kind'], row['target']) or any(
            action['target_kind'] == row['kind'] and action['target_id'] == row['target']
            and held(action['target_kind'], action['target_id'], action['operation'])
            for action in task['required_actions'])
    required_outputs = [row for row in task['required_outputs'] if not output_held(row)]
    required_actions = [row for row in task['required_actions']
                        if not held(row['target_kind'], row['target_id'], row['operation'])]
    gate.require(len(required_outputs) < len(task['required_outputs'])
                 or len(required_actions) < len(task['required_actions']), 'hold covers no requested target')
    targets = {row['target'] for row in required_outputs} | {row['target_id'] for row in required_actions}
    gate.require(all(module.check_covered(state_root, task, check, targets=targets)
                     for check in task['required_checks']), 'parent phase checks are incomplete')
    candidates = [child for child in tasks.values() if child.get('parent') == task['task_id']
                  and not any(other.get('parent') == child['task_id'] for other in tasks.values())]
    descendants = [child for child in tasks.values() if any(
        ancestor['task_id'] == task['task_id'] for ancestor in module.task_ancestors(tasks, child))]
    for child in descendants:
        inherited = module.effective_constraints(tasks, child, state_root)
        gate.require(not inherited['scope_errors'], 'child authority or scope requires reconciliation')
        if not inherited['holds']:
            gate.require(module.completion_current(state_root, tasks, child['task_id']),
                         'nonheld descendant task is not current and complete')
    leaves = [child for child in candidates if module.completion_current(state_root, tasks, child['task_id'])]
    gate.require(leaves and all(any(row in leaf['required_outputs'] for leaf in leaves) for row in required_outputs)
                 and all(any(row in leaf['required_actions'] for leaf in leaves) for row in required_actions),
                 'nonheld outputs and actions require current completed leaf evidence')
    gate.require(any(any(row['kind'] == 'message' and leaf['outputs'].get(row['target'], {}).get('value') == message
                         for row in leaf['required_outputs']) for leaf in leaves),
                 'host message differs from the completed phase message output')
    return leaves


def _completion_callback(directory, root, event):
    context = _read(directory / 'context.json', {})
    if context.get('completion_contract') is None or context.get('state_binding'):
        return
    relative = 'preflight/' + gate.sha(gate.canonical(event)) + '.json'
    raw = gate.regular_bytes(directory / relative)
    binding = gate.parse_json(raw)
    if 'callback' not in binding:
        return
    reference = {'callback_path': relative, 'sha256': gate.sha(raw)}
    observed = context.get('unbound_operations', [])
    if reference not in observed:
        save_record(directory / 'context.json', {**context, 'unbound_operations': [*observed, reference]})


def _completion_observations(directory, context):
    observed = []
    for row in context.get('unbound_operations', []):
        if 'callback_path' not in row:
            observed.append(row)
            continue
        path = directory / gate.safe_relative(row['callback_path'])
        raw = gate.regular_bytes(path)
        gate.require(gate.sha(raw) == row['sha256'], 'saved operation callback changed')
        binding = gate.parse_json(raw)
        observed.append({**binding['callback'], 'preflight': binding,
                         'output_versions': binding.get('output_versions', {})})
    return observed


def _ordinary_action_result(directory, requirement, observed, state_root):
    """Derive outcomes from actual callbacks."""
    operation, target = requirement['operation'], requirement['target_id']
    rows = [row for row in observed if row.get('preflight', {}).get('operation') == operation
            and (str(state_root / target) if requirement['target_kind'] == 'file' else target)
            in row.get('preflight', {}).get('targets', [])]
    if requirement['target_kind'] == 'file':
        rows += [row for row in observed if [operation, str(state_root / target)]
                 in row.get('preflight', {}).get('resolved_effects', []) and row not in rows]
    if not rows:
        return None
    row = rows[-1]
    if _tool_failed(row):
        return None
    if requirement['target_kind'] == 'file':
        path = state_root / target
        if operation in {'delete', 'remove'}:
            if path.exists():
                return None
        elif not path.is_file() or row.get('output_versions', {}).get(target) != gate.sha(gate.regular_bytes(path)):
            return None
        return {**requirement, 'result': 'passed', 'callback': row}
    native = sibling('hook_completion_native', next(path for path in
                     (base / 'native_check.py', base / 'NATIVE_CHECK.py') if path.is_file()))
    tool = row['tool_name']
    name = tool.rsplit('__', 1)[-1].split('.')[-1].lower()
    args, returned = row['tool_input'], row['tool_response']
    try:
        if name in {'exec_command', 'run_command', 'bash'} and operation == 'execute_command':
            command = args.get('command') if name == 'bash' else args.get('cmd')
            gate.require(command == target, 'returned command differs from its requested target')
            outcome = native._operation_return(returned, operation, target, 'command')
            session = outcome.get('session_id')
            for follow in observed[observed.index(row) + 1:]:
                if (str(follow.get('tool_name', '')).rsplit('__', 1)[-1].split('.')[-1].lower() != 'write_stdin'
                        or follow.get('tool_input', {}).get('session_id') != session):
                    continue
                gate.require(outcome['status'] == 'running' and follow.get('preflight'),
                             'continuation needs its current operation authority')
                outcome = native._operation_return(follow['tool_response'], operation, target, 'command')
                gate.require(outcome.get('session_id', session) == session, 'continuation session changed')
        else:
            expected_operation, expected_target = native._connector_call_target(tool, args)
            gate.require((expected_operation, expected_target) == (operation, target), 'connector target changed')
            adapter = native._OPERATION_ADAPTERS[(tool, operation)][0]
            outcome = native._connector_operation(returned, args, operation, target, adapter)
        gate.require(outcome['status'] == 'success', 'required operation has not completed')
        return {**requirement, 'result': 'passed', 'callback': row, 'outcome': outcome}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def _verify_completion_contract(directory, root, message, observed):
    context = _read(directory / 'context.json', {})
    selected = _operation_manifest(root, context)
    gate.require(selected is not None, 'select the task operation before completing its result')
    bound = _completion_task(directory, root)
    if bound is None:
        conditions = set(selected['selection']['conditions'])
        gate.require(not observed and not conditions.intersection({
            'requested_artifact_files', 'file_output_or_format_rendering', 'data_code_change',
            'requested_distribution_configuration_or_installation', 'publication_requested'}),
            'declare the requested outputs and actions in the existing operation binding')
        return
    module, _, task, state_root = bound
    gate.require(all(row.get('preflight') for row in observed),
                 'observed operation needs its original authority and actual result evidence')
    for requirement in task['required_actions']:
        result = _ordinary_action_result(directory, requirement, observed, state_root)
        if result is not None:
            task['action_results'].append(result)
    for requirement in task['required_outputs']:
        kind, target = requirement['kind'], requirement['target']
        value = None
        if kind == 'message':
            value = message
            version = module.content_hash(value)
        elif kind == 'file':
            path = state_root / module.relative(state_root, target, exists=False)
            recorded = next((row.get('output_versions', {}).get(target) for row in reversed(observed)
                             if target in row.get('output_versions', {})), None)
            version = module.digest(path) if path.is_file() else None
            if not version or version != recorded:
                continue
        else:
            result = next((row for row in reversed(task['action_results']) if row['target_id'] == target), None)
            if result is None:
                continue
            value = result.get('outcome')
            version = module.content_hash(value)
        task['outputs'][target] = {'role': requirement['role'], 'kind': kind, 'version': version}
        if kind != 'file':
            task['outputs'][target]['value'] = value
    missing = module.missing_required_results(task, lambda result: result['result'] == 'passed')
    gate.require(not missing, 'required outputs or actual operations are incomplete: ' + json.dumps(missing))


def _verify_ordinary_stop(event, root, directory):
    message = event.get('last_assistant_message')
    gate.require(isinstance(message, str) and message.strip(), 'host assistant message is unavailable')
    if not event.get('agent_id'):
        gate.require(not _pending_parent_returns(directory), 'consume the returned child scope before parent completion')
        for path in sorted((directory / 'children').glob('*.json')):
            child = _read(path)
            gate.require(child.get('return_observation') and child.get('status') not in {
                'restoration-check-failed', 'scope-check-failed'}, 'child work has not returned its completed scope')
    observed = _completion_observations(directory, _read(directory / 'context.json', {}))
    bound = _bound_state(directory, root)
    if bound is None:
        gate.require(not _pending_task_holds(directory, None), 'unresolved task hold requires continuation')
        _verify_completion_contract(directory, root, message, observed)
        return 'completed'
    module, data, task, state_root = bound
    if module.completion_current(state_root, data['tasks'], task['task_id']):
        gate.require(all(module.completion_current(state_root, data['tasks'], ancestor['task_id'])
                         for ancestor in module.task_ancestors(data['tasks'], task)),
                     'bound leaf cannot complete an unfinished parent task')
        gate.require(not _pending_task_holds(directory, bound), 'unresolved task hold requires continuation')
        candidates = [task['outputs'].get(row['target'], {}) for row in task['required_outputs'] if row['kind'] == 'message']
        gate.require(any(row.get('value') == message for row in candidates),
                     'host message differs from the required recorded message output')
        receipt_tasks, outcome = [task], 'completed'
    else:
        receipt_tasks = [task, *_ordinary_wait_leaf(module, data, task, state_root, directory, message)]
        outcome = 'paused'
    for event in observed:
        matched = False
        for receipt in (receipt for owner in receipt_tasks for receipt in owner.get('action_results', [])
                        if module.receipt_current(state_root, owner, receipt)):
            for name in receipt.get('evidence', {}):
                try:
                    evidence = gate.parse_json(gate.regular_bytes(state_root / module.relative(state_root, name)))
                    matched = any(row.get('tool_call_ref') == event['tool_use_id']
                                  and row.get('tool_name') == event['tool_name']
                                  and json.loads(row.get('call_args_text', 'null')) == event['tool_input']
                                  and json.loads(row.get('return_text', 'null')) == event['tool_response']
                                  for row in [evidence, *evidence.get('continuations', [])])
                except (ValueError, OSError, TypeError):
                    matched = False
                if matched:
                    break
            if matched:
                break
        gate.require(matched, 'observed unbound operation lacks its exact returned-action evidence')
    return outcome


def _tool_target(value, cwd):
    gate.require(isinstance(value, str) and value.strip(), 'tool target is unresolved')
    if '://' in value:
        parsed = urlsplit(value)
        if parsed.scheme == 'artifact':
            return str((Path(cwd) / (parsed.netloc + parsed.path)).resolve())
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, parsed.fragment))
    path = Path(value)
    return str((Path(cwd) / path).resolve() if not path.is_absolute() else path.resolve())


def _recovery_packet(root):
    policy = sibling('hook_missing_context_policy', root / 'harness/policy_assets.py')
    owner, _, manifest, _ = policy.discover_policy(policy.__file__)
    packet = policy.instruction_context(owner, manifest=manifest, status={'status': 'blocked'}, restore=True)
    return (packet['text'] + '\nThe original task and its identity are unavailable in this session. '
            'Locate the actual inherited task context and recover its exact request, amendments, authority, holds, '
            'applicable rules and unfinished work before dependent changes or external actions. '
            'Do not treat a continuation request or a summary as the original task. '
            'An explicitly new independent task may start separately.')


def _patch_effects(command):
    gate.require(isinstance(command, str), 'missing patch command')
    lines = command.splitlines()
    gate.require(len(lines) >= 3 and lines[0] == '*** Begin Patch' and lines[-1] == '*** End Patch',
                 'patch boundaries are unresolved')
    effects = []
    for index, line in enumerate(lines[1:-1], 1):
        if line.startswith(('*** Add File: ', '*** Update File: ', '*** Delete File: ')):
            kind, target = line[4:].split(': ', 1)
            gate.require(target.strip() == target and target, 'patch target is unresolved')
            operation = {'Add File': 'create', 'Update File': 'update', 'Delete File': 'delete'}[kind]
            effects.append((operation, target))
        elif line.startswith('*** Move to: '):
            gate.require(index > 1 and lines[index - 1].startswith('*** Update File: ') and effects,
                         'patch move source is unresolved')
            target = line[len('*** Move to: '):]
            gate.require(target.strip() == target and target, 'patch move destination is unresolved')
            _, source = effects.pop()
            effects.extend((('delete', source), ('create', target)))
        elif line.startswith('*** '):
            gate.require(line == '*** End of File', 'unknown patch operation')
    gate.require(effects, 'patch contains no resolved operations')
    return effects


def _trusted_read_program(name):
    if name not in {'cat', 'head', 'tail', 'rg', 'ls', 'stat', 'pwd', 'wc', 'sha256sum'}:
        return False
    return _trusted_system_program(name)


def _trusted_system_program(name):
    found = shutil.which(name)
    if not found:
        return False
    path = Path(found).resolve()
    for part in (path, *path.parents):
        info = part.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            return False
    return True


def _observed_read_paths(event, task_root):
    """Return only literal paths named by a completed, successful read call."""
    raw_tool = event.get('tool_name')
    tool = str(raw_tool).rsplit('__', 1)[-1].split('.')[-1].lower()
    args, response = event.get('tool_input'), event.get('tool_response')
    if not isinstance(args, dict) or _tool_failed(event):
        return []
    if raw_tool in {'Read', 'read_file', 'read_text_file'}:
        if not (isinstance(response, str) or isinstance(response, dict) and
                (response.get('success') is True or response.get('isError') is False or
                 isinstance(response.get('content'), str) or isinstance(response.get('output'), str))):
            return []
        names = [args.get('file_path') if tool == 'read' else args.get('path')]
    elif raw_tool in {'Bash', 'exec_command', 'run_command', 'functions.exec_command'}:
        if not isinstance(response, dict) or type(response.get('exit_code')) is not int or response['exit_code'] != 0:
            return []
        command = args.get('command') if tool == 'bash' else args.get('cmd')
        if not isinstance(command, str) or re.search(r'[;&|<>\n`$\r\x00*?\[\]{}~#]', command):
            return []
        try:
            parts = shlex.split(command)
        except ValueError:
            return []
        if not parts or not (parts[0] == 'sed' and _trusted_system_program('sed') or
                             _trusted_read_program(parts[0])):
            return []
        if parts[0] == 'cat':
            names = [part for part in parts[1:] if part != '--']
            if any(part.startswith('-') for part in names):
                return []
        elif parts[0] == 'sed':
            if len(parts) < 4 or parts[1] != '-n' or not re.fullmatch(r'[0-9]+(?:,[0-9]+)?p', parts[2]):
                return []
            names = parts[3:]
            if any(part.startswith('-') for part in names):
                return []
        elif parts[0] == 'rg':
            tail = parts[1:]
            allowed = {'-n', '--line-number', '-i', '--ignore-case', '-F', '--fixed-strings', '--hidden'}
            while tail and tail[0] in allowed:
                tail = tail[1:]
            if tail and tail[0] == '--files':
                names = tail[1:]
            else:
                if tail and tail[0].startswith('-'):
                    return []
                names = tail[1:] if len(tail) > 1 else []
            if any(part.startswith('-') for part in names):
                return []
        else:
            return []
    else:
        return []
    workdir = args.get('workdir', event['cwd'])
    if not isinstance(workdir, str):
        return []
    workdir = Path(os.path.abspath(os.path.join(event['cwd'], workdir)))
    output = []
    for name in names:
        if not isinstance(name, str) or not name or name == '-':
            continue
        path = Path(os.path.abspath(workdir / name))
        if not path.is_relative_to(task_root):
            continue
        try:
            actual = path.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if actual.is_relative_to(task_root) and (actual.is_file() or actual.is_dir()):
            output.append((path, actual))
    return output


def _instruction_closure(root, observations):
    sources = {}
    for observation in observations:
        lexical = Path(observation['path'])
        try:
            actual = lexical.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if not actual.is_relative_to(root):
            continue
        scopes = [lexical if actual.is_dir() else lexical.parent,
                  actual if actual.is_dir() else actual.parent]
        for scope in scopes:
            while scope.is_relative_to(root):
                candidate = scope / 'AGENTS.md'
                try:
                    resolved = candidate.resolve(strict=True)
                    if resolved.is_relative_to(root) and resolved.is_file():
                        body = gate.regular_bytes(resolved)
                        key = (str(candidate), gate.sha(body))
                        if key not in sources:
                            sources[key] = {'path': str(candidate), 'resolved_path': str(resolved),
                                            'directory': str(scope), 'sha256': key[1],
                                            'body': body.decode('utf-8'), 'observed': []}
                        origin = {'path': observation['path'], 'tool_name': observation['tool_name'],
                                  'tool_use_id': observation['tool_use_id']}
                        if origin not in sources[key]['observed']:
                            sources[key]['observed'].append(origin)
                except FileNotFoundError:
                    pass
                if scope == root:
                    break
                scope = scope.parent
    return sorted(sources.values(), key=lambda row: (len(Path(row['directory']).relative_to(root).parts), row['directory']))


def _scoped_instructions(event, directory, context, *, restore=False, available=None):
    """Retain and restore the applicable AGENTS closure for observed read paths."""
    root = Path(context['cwd']).resolve(strict=True)
    record_path = directory / 'scoped-instructions.json'
    previous = _read(record_path, {'root': str(root), 'observations': [], 'instructions': [], 'pending': []})
    gate.require(previous.get('root') == str(root), 'scoped instruction root changed')
    observations = list(previous['observations'])
    if not restore:
        for lexical, actual in _observed_read_paths(event, root):
            item = {'path': str(lexical), 'resolved_path': str(actual), 'tool_name': event['tool_name'],
                    'tool_use_id': event['tool_use_id']}
            if not any(row['path'] == item['path'] and row['resolved_path'] == item['resolved_path']
                       for row in observations):
                observations.append(item)
    if not observations:
        return ''
    instructions = _instruction_closure(root, observations)
    current = {(row['path'], row['sha256']) for row in instructions}
    old = {(row['path'], row['sha256']) for row in previous['instructions']}
    restore = restore or previous.get('turn_id') != event.get('turn_id')
    changed = restore or current != old
    pending = set(previous['pending'])
    verified = set()
    if not restore:
        response = event.get('tool_response')
        content = response if isinstance(response, str) else (response.get('content', response.get('output')) if isinstance(response, dict) else None)
        if isinstance(content, str):
            digest = gate.sha(content.encode('utf-8'))
            for _, actual in _observed_read_paths(event, root):
                for row in instructions:
                    if row['resolved_path'] == str(actual) and row['sha256'] == digest:
                        verified.add(row['path'] + ':' + digest)
                        pending.discard(row['path'] + ':' + digest)
    pending &= {path + ':' + digest for path, digest in current}
    header = ('Applicable AGENTS.md instructions are ordered from ancestor to descendant; platform and user authority '
              'continue to govern. Within that authority, more specific instructions apply to their subtree. '
              'Re-evaluate affected work against changed instructions.\n')
    fresh = [row for row in instructions if restore or (row['path'], row['sha256']) not in old]
    rendered = ''.join('\n[Scoped instruction ' + row['path'] + ' sha256=' + row['sha256'] +
                       ' from ' + row['observed'][0]['tool_name'] + ' ' + row['observed'][0]['path'] + ']\n' + row['body']
                       for row in fresh)
    suffix = '\nThe applicable instruction closure changed; reconsider prior scoped judgments.' if current != old else ''
    if available is not None and len((header + rendered + suffix + '\n').encode('utf-8')) > available:
        pending.update({row['path'] + ':' + row['sha256'] for row in fresh} - verified)
        rendered = ('\nRead every pending AGENTS.md in the task-private closure record before dependent writes; '
                    'verify the recorded hashes against the actual files. Record: ' + str(record_path))
    updated = {'root': str(root), 'turn_id': event.get('turn_id'), 'observations': observations,
               'instructions': instructions, 'pending': sorted(pending)}
    if updated != previous:
        save_record(record_path, updated)
    if changed:
        return header + rendered + suffix
    return ''


def _scoped_available(root, event, base_text, policy):
    registration = gate.parse_json(gate.regular_bytes(root / 'hooks/hooks.json'))
    entries = registration['hooks'].get(event, [])
    handlers = [hook for entry in entries for hook in entry.get('hooks', [])
                if isinstance(hook.get('command'), str) and 'hooks/check.py' in hook['command']
                and hook['command'].rstrip().endswith(event)]
    limit = handlers[0].get('additionalContextLimit', 2500) if handlers else 2500
    gate.require(type(limit) is int and limit >= 0, 'invalid hook context limit')
    if limit == 0:
        return None
    priority = policy.PRIMARY_EXPRESSION_RULE + '\n' + policy.PRIMARY_JAPANESE_RULE + '\n'
    # Codex applies this configured threshold in approximate tokens: four UTF-8 bytes each.
    return max(0, 4 * limit - len((priority + base_text).encode('utf-8')))


def _pending_scoped_writes(directory, effect, targets):
    record = _read(directory / 'scoped-instructions.json', {})
    if effect not in {'write', 'unresolved'} or not record.get('observations'):
        return
    root = Path(record['root'])
    current = _instruction_closure(root, record['observations'])
    old_keys = {(row['path'], row['sha256']) for row in record['instructions']}
    new_keys = {(row['path'], row['sha256']) for row in current}
    pending = set(record.get('pending', []))
    changed_rows = [row for row in current + record['instructions']
                    if (row['path'], row['sha256']) in old_keys ^ new_keys]
    for row in record['instructions']:
        try:
            if (Path(row['path']).resolve(strict=True) != Path(row['resolved_path']) or
                    gate.sha(gate.regular_bytes(Path(row['resolved_path']))) != row['sha256']):
                pending.add(row['path'] + ':' + row['sha256'])
        except (OSError, ValueError):
            pending.add(row['path'] + ':' + row['sha256'])
    sources = changed_rows + [row for row in record['instructions'] if row['path'] + ':' + row['sha256'] in pending]
    if not sources:
        return
    if not targets or any(not str(target).startswith('/') for target in targets):
        raise ValueError('read the pending scoped AGENTS.md instructions before an unresolved write')
    for target in targets:
        path = Path(target)
        if any(path.is_relative_to(Path(row['directory'])) or
               path.is_relative_to(Path(row['directory']).resolve()) for row in sources):
            raise ValueError('read the pending scoped AGENTS.md instructions before a dependent write')


def _pre_tool(event, root, directory, state, bound_result=None):
    """Hook-side preflight only; it cannot install execution-owner enforcement.

    In particular the host does not rerun this hook for write_stdin, and callback
    errors/timeouts can bypass a hook. Its output is not a reusable execution permit.
    """
    if event.get('hook_event_name') == 'PostToolUse':
        observed_sha = gate.sha(gate.canonical(event))
        previous = _read(directory / 'preflight' / (observed_sha + '.json'))
        if previous is not None and previous.get('callback_sha256') == observed_sha:
            return {}  # The exact immutable returned event is not a new execution request.
    tool, arguments = event.get('tool_name'), event.get('tool_input')
    gate.require(isinstance(tool, str) and tool and isinstance(arguments, dict), 'missing actual tool name/input')
    name = tool.rsplit('__', 1)[-1].split('.')[-1].lower()
    cwd = event['cwd']
    effects = []
    command_action = None
    opaque_action = None
    input_bound = None
    read_operation = None
    if name == 'write_stdin':
        gate.require(isinstance(arguments.get('session_id'), (str, int)), 'missing interactive session identity')
        record = _read(directory / 'sessions' / (gate.sha(str(arguments['session_id']).encode()) + '.json'))
        gate.require(record is not None and not record.get('closed'),
                     'interactive session is unknown or already terminal')
        if arguments.get('chars'):
            input_bound = _bound_state(directory, root) or _completion_task(directory, root)
            gate.require(input_bound is not None and record.get('command'),
                         'interactive input requires its initiating operation and current task authority')
            module, data, task, state_root = input_bound
            native = sibling('hook_stdin_authority', root / 'harness/native_check.py')
            gate.require(task['status'] == 'running' and native.stdin_target(arguments) in task['external_targets']
                         and record['command'] in task['external_targets']
                         and any(row['operation'] == 'execute_command' and row['target_id'] == record['command']
                                 for row in task['required_actions'])
                         and not _pending_task_holds(directory, input_bound)
                         and not module.effective_constraints(data['tasks'], task, state_root)['holds'],
                         'interactive input lacks exact current session/input authority or has an unresolved hold')
        operation, targets, effect = ('write_stdin', [str(arguments['session_id'])], 'local-control') if arguments.get('chars') else (
                                     'poll', [str(arguments['session_id'])], 'read')
    else:
        targets = [arguments[key] for key in ('path', 'file_path', 'file', 'target', 'url', 'library_file_id', 'project_id')
                   if isinstance(arguments.get(key), str) and arguments[key]]
        if tool in {'Read', 'read_file', 'read_text_file', 'list_directory', 'search_files', 'view_image'}:
            operation, effect = 'read', 'read'
            read_operation = 'read_document'
        elif (tool.startswith(('web__', 'mcp__')) and
              tool in ((native := sibling('hook_acquisition_tools', root / 'harness/native_check.py')).WEB_READ_TOOLS |
                       native.LIBRARY_READ_TOOLS | native.CONNECTOR_READ_TOOLS)):
            operation, effect = 'read', 'read'
            read_operation = 'read_url' if tool in native.WEB_READ_TOOLS else 'read_document'
            for key in ('repository_full_name', 'repository_url', 'repository_name', 'org', 'ref',
                        'plugin_id', 'document_id', 'document_url', 'read_paths', 'repository_id'):
                value = arguments.get(key)
                values = value if isinstance(value, list) else [value]
                targets.extend(str(item) for item in values if isinstance(item, str) and item or type(item) is int)
            fields = (('open', 'click', 'find', 'screenshot') if tool in native.WEB_READ_TOOLS else
                      ('read',) if tool in native.LIBRARY_READ_TOOLS else ())
            for field in fields:
                calls = arguments.get(field, [])
                if not isinstance(calls, list):
                    continue
                for call in calls:
                    if not isinstance(call, dict) or not isinstance(call.get('ref_id'), str) or not call['ref_id']:
                        continue
                    targets.append(call['ref_id'])
                    if field == 'click' and type(call.get('id')) is int:
                        targets.append(call['ref_id'] + '#' + str(call['id']))
        elif name in {'bash', 'exec_command', 'run_command'}:
            command = arguments.get('command') if name == 'bash' else arguments.get('cmd')
            gate.require(isinstance(command, str), 'missing execution command')
            gate.require(not arguments.get('env'), 'execution environment override is unresolved')
            parts = shlex.split(command)
            gate.require(parts, 'empty execution command')
            if re.search(r'[;&|<>\n`]|\$|[\r\x00]', command):
                operation, effect, command_action = 'execute_command', 'write', command
            elif (_trusted_read_program(parts[0])
                  and not any(part.startswith(('--pre', '--hostname-bin')) for part in parts)):
                operation, effect = 'read', 'read'
                targets = [part for part in parts[1:] if not part.startswith('-')]
            elif (parts[0] in {'python', 'python3'} and len(parts) >= 3
                  and _tool_target(parts[2] if parts[1] == '-B' and len(parts) > 3 else parts[1], cwd)
                  == str((root / 'harness/state.py').resolve())):
                tail = parts[3:] if parts[1] == '-B' else parts[2:]
                specified = [tail[i + 1] for i, value in enumerate(tail[:-1]) if value == '--root']
                specified += [value.split('=', 1)[1] for value in tail if value.startswith('--root=')]
                context = _read(directory / 'context.json', {})
                task_root = str(absolute(context.get('cwd')).resolve())
                selected_root = _tool_target(specified[0], cwd) if specified else str(Path(cwd).resolve())
                gate.require(len(specified) <= 1 and selected_root == task_root,
                             'state bookkeeping root differs from the original task root')
                operation, effect = 'state-control', 'local-control'
            elif (parts[0] in {'python', 'python3'} and len(parts) >= 3
                  and _tool_target(parts[2] if parts[1] == '-B' and len(parts) > 3 else parts[1], cwd)
                  == str((root / 'harness/codex_hooks.py').resolve())):
                tail = parts[3:] if parts[1] == '-B' else parts[2:]
                context = _read(directory / 'context.json', {})
                roots = [tail[i+1] for i, value in enumerate(tail[:-1]) if value == '--root']
                contexts = [tail[i+1] for i, value in enumerate(tail[:-1]) if value == '--hook-context']
                gate.require(any(value in tail for value in ('bind-operation', 'bind-child-assignment'))
                             and len(roots) == 1 and len(contexts) == 1
                             and _tool_target(roots[0], cwd) == str(absolute(context['cwd']).resolve())
                             and _tool_target(contexts[0], cwd) == str((directory / 'context.json').resolve()),
                             'operation binding must target this task and its original root')
                operation, effect = 'state-control', 'local-control'
            else:
                operation, effect, command_action = 'execute_command', 'write', command
        elif tool in {'mcp__codex_apps__github_update_ref', 'mcp__codex_apps__plugin_creator_update_plugin'}:
            native = sibling('hook_connector_call', root / 'harness/native_check.py')
            operation, opaque_action = native._connector_call_target(tool, arguments)
            effect, targets = 'write', []
        elif name == 'apply_patch':
            effects = _patch_effects(arguments.get('command'))
            operation, effect = 'apply_patch', 'write'
            targets = [target for _, target in effects]
        elif tool in {'write_file', 'edit_file', 'create_file', 'delete_file', 'update_file'}:
            operation, effect = tool.split('_', 1)[0], 'write'
        elif (name in {'spawn_agent', 'followup_task', 'list_agents', 'wait_agent'} or
              name == 'send_message' and tool in {'collaboration.send_message', 'functions.collaboration.send_message'}):
            operation, effect = name, 'local-control'
        else:
            operation, effect = name, 'unresolved'
    normalized = []
    for target in targets:
        normalized.append(_tool_target(target, cwd))
    if opaque_action is not None:
        normalized = [opaque_action]
    resolved_effects = [(verb, _tool_target(target, cwd)) for verb, target in effects]
    if effect != 'read' and operation != 'state-control':
        _operation_manifest(root, _read(directory / 'context.json', {}))
    _pending_scoped_writes(directory, effect, normalized)
    rows, prohibitions, policy_sha = [], [], state.get('policy_manifest_sha256')
    bound = input_bound or (None if operation == 'state-control' else _bound_state(directory, root))
    if bound is None and operation != 'state-control':
        bound = _completion_task(directory, root)
    if bound is not None:
        state_module, data, task, state_root = bound
        ancestors = state_module.task_ancestors(data['tasks'], task) if task.get('parent') else []
        for owner in [task, *ancestors]:
            if owner.get('specification'):
                specification, request = state_module._spec_inputs(state_root, owner)
                requirements = state_module._native().requirements.validate_contract(specification, request)
                prohibitions.extend(row for row in requirements
                                    if row.get('evaluator', {}).get('type') == 'forbidden_operation')
        if effect != 'local-control':
            if effect == 'read' and task['status'] == 'blocked' and task.get('blocked_reason') == 'user_hold':
                if name in {'bash', 'exec_command', 'run_command'}:
                    gate.require(parts[0] in {'cat', 'head', 'tail', 'wc', 'sha256sum', 'stat', 'ls', 'pwd'}
                                 and all(not part.startswith('-') for part in parts[1:]),
                                 'held shell read scope is unresolved')
                else:
                    gate.require(tool in {'read_file', 'read_text_file', 'list_directory', 'view_image'}
                                 and set(arguments) <= {'path', 'file_path', 'file', 'target', 'offset', 'limit',
                                                       'start_line', 'end_line', 'detail'},
                                 'held read scope is unresolved')
                constraints = state_module.effective_constraints(data['tasks'], task, state_root)
                state_holds = constraints['holds']
                gate.require(state_holds and not constraints['scope_errors'], 'held read scope is unresolved')
                labels = {row['hold_id'] for row in state_holds} | {target.split(':', 1)[-1]
                          for row in state_holds for target in row['targets']}
                gate.require(all(row.get('target_ids') and set(row['target_ids']) <= labels
                                 for row in _pending_task_holds(directory, bound)),
                             'held read scope is unresolved')
                gate.require(normalized or (name in {'bash', 'exec_command', 'run_command'} and command == 'pwd'),
                             'held read target is unresolved')
                if not normalized:
                    gate.require(all(row['targets'] or (row['operations'] and not set(row['operations']) & {'read', tool, name})
                                     for row in state_holds), 'held read scope is unresolved')
                for target in normalized:
                    is_url = '://' in target
                    if is_url:
                        gate.require(target in task.get('external_targets', []), 'held read target is outside task scope')
                    else:
                        gate.require(Path(target).is_relative_to(state_root), 'held read target is outside task scope')
                    for hold in state_holds:
                        if hold['operations'] and not set(hold['operations']) & {'read', tool, name}:
                            continue
                        gate.require(hold['targets'], 'held read scope is unresolved')
                        for selected in hold['targets']:
                            if is_url:
                                blocked = selected == 'object:' + target
                            elif selected.startswith('file:'):
                                blocked = state_module.scopes_overlap(selected[5:], Path(target).relative_to(state_root).as_posix())
                            else:
                                blocked = False
                            gate.require(not blocked, 'task hold covers this read')
            else:
                gate.require(task['status'] == 'running', 'task state is not running')
        rows = [{'kind': 'action', 'operation': row['operation'], 'target':
                 str(state_root / row['target_id']) if row['target_kind'] == 'file' else row['target_id'],
                 'target_kind': row['target_kind']} for row in task['required_actions']]
    holds = _pending_task_holds(directory, bound)
    for row in prohibitions:
        forbidden = row['target'] if opaque_action is not None else _tool_target(row['target'], cwd)
        gate.require(not (forbidden in normalized and (row['evaluator']['operation'] in
                         {operation, read_operation, tool, name} or effect == 'write')),
                     'forbidden operation ' + row['id'] + ' on ' + row['target'])
    if effect not in {'read', 'local-control'}:
        if opaque_action is not None:
            gate.require(not holds, 'task hold requires reconciliation before an external operation')
            if bound is not None:
                gate.require(opaque_action in task.get('external_targets', []) and
                             any(row['operation'] == operation and row.get('target_kind') == 'object'
                                 and row['target'] == opaque_action for row in rows),
                             'external operation lacks its exact object authority')
                for hold in state_module.effective_constraints(data['tasks'], task, state_root)['holds']:
                    gate.require(not ((not hold['operations'] or operation in hold['operations']) and
                                      (not hold['targets'] or 'object:' + opaque_action in hold['targets'])),
                                 'task state hold covers this external operation')
            else:
                raise ValueError('external operation lacks its exact object authority')
        if command_action is not None:
            gate.require(bound is not None and not holds and not state_module.effective_constraints(data['tasks'], task, state_root)['holds'],
                         'command requires bound authority and no unresolved hold')
            gate.require(any(row['operation'] == 'execute_command' and row.get('target_kind') == 'object'
                             and row['target'] == command_action for row in rows)
                         and command_action in task.get('external_targets', []),
                         'exact command lacks current fixed operation/target authority')
            normalized = [command_action]
        for hold in holds:
            labels = hold.get('target_ids', [])
            # Named file-format operations have an unambiguous target class;
            # unresolved names require resolution before changing their scope.
            zip_hold = labels and all('zip' in label.casefold() for label in labels)
            gate.require(zip_hold and normalized and all(not target.casefold().endswith('.zip') for target in normalized),
                         'task hold covers this operation or still needs target resolution')
        gate.require(effect != 'unresolved' and normalized, 'modifying operation or target is unresolved')
        required = [] if command_action is not None or opaque_action is not None else resolved_effects or [(operation, target) for target in normalized]
        for verb, target in required:
            allowed_operations = {verb} if resolved_effects else {verb, tool, name}
            gate.require(any(row['kind'] == 'action' and row['operation'] in allowed_operations
                             and _tool_target(row['target'], cwd) == target for row in rows),
                         'modifying tool lacks current fixed operation/target authority')
            if bound is not None:
                try:
                    relative_target = Path(target).relative_to(state_root).as_posix()
                except ValueError as exc:
                    raise ValueError('target exceeds task write scope') from exc
                relative = state_module.relative(state_root, relative_target, exists=False)
                gate.require(state_module.in_scope(relative, task.get('write_scope', [])),
                             'target exceeds task write scope')
                for hold in state_module.effective_constraints(data['tasks'], task, state_root)['holds']:
                    matches_operation = not hold['operations'] or verb in hold['operations']
                    targets = hold['targets']
                    matches_target = not targets or any(item == 'file:' + relative for item in targets)
                    gate.require(not (matches_operation and matches_target), 'task state hold covers this operation')
    binding = {'tool_name': tool, 'operation': operation, 'targets': normalized, 'effect': effect,
               'resolved_effects': resolved_effects,
               'input_sha256': gate.sha(gate.canonical(arguments)), 'policy_sha256': policy_sha,
               'effective_holds_sha256': gate.sha(gate.canonical(holds)), 'session_id': arguments.get('session_id'),
               'task_id': _read(directory / 'context.json', {}).get('task_id'),
               'execution_owner_connected': False}
    observation_bound = bound
    if (observation_bound is None and event.get('hook_event_name') == 'PostToolUse'
            and _read(directory / 'context.json', {}).get('state_binding')):
        observation_bound = _bound_state(directory, root)
    enabled = (observation_bound is not None and _feature_enabled(directory, observation_bound[0],
                                                                    observation_bound[2], 'loops'))
    key = _preflight_key(event) if enabled and event.get('hook_event_name') == 'PreToolUse' else None
    if key:
        binding['source'] = 'PreToolUse'
        candidates = [target for _, target in resolved_effects] or normalized
        if effect == 'write' and command_action is None and opaque_action is None:
            binding['edit_targets'] = [{'path': target, 'version': _target_version(target, cwd)}
                                       for target in candidates if Path(target).is_absolute()]
    if enabled and event.get('hook_event_name') == 'PostToolUse':
        previous = _read(directory / 'preflight' / (gate.sha(gate.canonical(event)) + '.json'), {})
        if isinstance(previous.get('usage_observation'), dict):
            for field in ('usage_observation', 'usage_check_source', 'loop_advisory'):
                if field in previous:
                    binding[field] = previous[field]
        else:
            binding['usage_observation'] = _hook_usage_row(event, directory, observation_bound[0], observation_bound[2])
            check = _saved_check_return(event, observation_bound[0], observation_bound[2], directory)
            if check is not None:
                binding['usage_check_source'] = {'check_id': check['check_id'], 'run_id': check['run_id'],
                                                 'producer_sha256': check['producer_sha256']}
            advice = _pending_loop_advice(event, binding['usage_observation'], observation_bound, directory)
            if advice is not None:
                binding['loop_advisory'] = advice
    hint = ''
    if bound_result is not None:
        hint, experience_status = _experience_hint(root, directory, bound, event)
        if experience_status is not None:
            binding['experience_feedback'] = experience_status
    context = _read(directory / 'context.json', {})
    if event.get('hook_event_name') == 'PostToolUse':
        binding['callback_sha256'] = gate.sha(gate.canonical(event))
    if (event.get('hook_event_name') == 'PostToolUse' and context.get('completion_contract')
            and not context.get('state_binding') and (effect == 'write' or name == 'write_stdin')):
        binding['callback'] = {field: event.get(field) for field in
                               ('tool_name', 'tool_use_id', 'tool_input', 'tool_response')}
        binding['output_versions'] = {}
        if not _tool_failed(event):
            completion = _completion_task(directory, root)
            module, _, task, state_root = completion
            targets = {row['target'] for row in task['required_outputs'] if row['kind'] == 'file'}
            targets.update(row['target_id'] for row in task['required_actions'] if row['target_kind'] == 'file')
            for target in targets:
                output = state_root / module.relative(state_root, target, exists=False)
                if output.is_file():
                    binding['output_versions'][target] = module.digest(output)
    preflight_path = directory / 'preflight' / ((key or gate.sha(gate.canonical(event))) + '.json')
    existing = _read(preflight_path)
    if bound_result is not None and isinstance(existing, dict):
        old_core = {name: value for name, value in existing.items() if name != 'experience_feedback'}
        new_core = {name: value for name, value in binding.items() if name != 'experience_feedback'}
        if old_core == new_core and existing.get('experience_feedback') != binding.get('experience_feedback'):
            binding.pop('experience_feedback', None)
            if 'experience_feedback' in existing:
                binding['experience_feedback'] = existing['experience_feedback']
            hint = ''  # Preserve the immutable earlier callback record on a replay.
    save_record(preflight_path, binding, replace=False)
    if bound_result is not None:
        bound_result.append(hint)
    return {}


def dispatch(event, expected_event):
    gate.require(isinstance(event, dict) and event.get('hook_event_name') == expected_event,
                 'hook event mismatch')
    for key in ('session_id', 'cwd'):
        gate.require(isinstance(event.get(key), str) and event[key].strip(), 'missing host ' + key)
    gate.require(expected_event in CONTEXT_EVENTS | {'PreToolUse', 'Stop', 'SubagentStop', 'Interrupt',
                 'PreCompact', 'PostCompact'}, 'unsupported hook event')
    if expected_event in ('PreCompact', 'PostCompact'):
        gate.require(event.get('trigger') in ('manual', 'auto'), 'unknown compaction trigger')
    agent_id = event.get('agent_id')
    gate.require(agent_id is None or (isinstance(agent_id, str) and agent_id.strip() == agent_id and agent_id),
                 'invalid host child identity')
    compaction_key = 'root' if agent_id is None else 'agent:' + agent_id
    root, data = absolute(os.environ.get('PLUGIN_ROOT')), absolute(os.environ.get('PLUGIN_DATA'))
    gate.require(Path(__file__).resolve() == root / 'harness/codex_hooks.py', 'plugin root does not match handler')
    cwd = absolute(event['cwd'])
    directory = _active_directory(event, data)
    if directory is None:
        if expected_event == 'SessionStart':
            source = event.get('source')
            gate.require(source in {'startup', 'resume', 'clear', 'compact', 'fork'}, 'unknown SessionStart source')
            if source != 'startup':
                session = data / 'economics' / gate.sha(event['session_id'].encode())
                save_record(session / 'active-task.json', {'task_id': 'recovery-required:' + event['session_id']}, replace=False)
            return feedback(expected_event, _recovery_packet(root))
        return {}
    if expected_event in ('PreCompact', 'PostCompact') and not (directory / 'context.json').exists():
        session = data / 'economics' / gate.sha(event['session_id'].encode())
        gate.require(not (session / 'active-task.json').exists(), 'active task context is missing')
        return {}
    session = data / 'economics' / gate.sha(event['session_id'].encode())
    active = _read(session / 'active-task.json', {})
    recovering = str(active.get('task_id', '')).startswith('recovery-required:')
    new_task = expected_event == 'UserPromptSubmit' and _new_task_requested(event.get('prompt', ''))
    if recovering and not new_task:
        if expected_event in ('PreCompact', 'PostCompact'):
            return failure(expected_event, 'restore the original task before compaction')
        if expected_event == 'Interrupt':
            with turn_lock(directory):
                save_record(directory / 'interrupted.json', {'session_id': event['session_id'],
                                                              'turn_id': event['turn_id']}, replace=False)
                _finish(directory, 'interrupted')
            return {'systemMessage': 'Economics task interrupted; restoration and reinjection stop.'}
        if expected_event == 'UserPromptSubmit':
            stopping = _stop_requested(event.get('prompt', ''), active['task_id'])
            if stopping['kind'] == 'task':
                with turn_lock(directory):
                    save_record(directory / 'stop-request.json', stopping)
                    _finish(directory, 'cancelled')
                return feedback(expected_event, 'The task was stopped. Do not resume automatically or treat it as completed.')
        if _lifecycle(directory) in TERMINAL:
            if expected_event == 'PreToolUse':
                return failure('PreToolUse', 'the stopped task cannot resume automatically')
            if expected_event in {'Stop', 'SubagentStop'}:
                return failure(expected_event, 'the stopped task is not completed', failure_class='cancelled')
            if expected_event == 'UserPromptSubmit':
                return feedback(expected_event, 'The task was stopped. Do not resume automatically; a new independent task must be explicit.')
            return {}
        if expected_event == 'PreToolUse':
            tool, inputs = event.get('tool_name'), event.get('tool_input', {})
            name = str(tool).rsplit('__', 1)[-1].split('.')[-1].lower()
            command = inputs.get('command') if name == 'bash' else inputs.get('cmd')
            parts = shlex.split(command) if isinstance(command, str) else []
            if tool in {'read_file', 'read_text_file', 'list_directory', 'search_files', 'view_image'} or (parts and _trusted_read_program(parts[0])):
                return _pre_tool(event, root, directory, {})
            return failure('PreToolUse', 'restore the original task before changes or external actions')
        if expected_event in {'Stop', 'SubagentStop'}:
            return failure(expected_event, 'restore the original task and unresolved requirements before completion')
        return feedback(expected_event, _recovery_packet(root))
    context_path = directory / 'context.json'
    if expected_event == 'Interrupt':
        save_record(directory / 'interrupted.json', {'session_id': event['session_id'], 'turn_id': event['turn_id']}, replace=False)
        _finish(directory, 'interrupted')
        return {'systemMessage': 'Economics turn interrupted; restoration and reinjection stop.'}
    with turn_lock(directory):
        lifecycle = _lifecycle(directory)
        if expected_event == 'SessionStart':
            gate.require(event.get('source') in {'startup', 'resume', 'clear', 'compact', 'fork'}, 'unknown SessionStart source')
            if lifecycle in TERMINAL or not context_path.exists():
                return {}
        if expected_event == 'UserPromptSubmit':
            prompt = event.get('prompt')
            gate.require(isinstance(prompt, str) and prompt.strip()
                         and len(prompt.encode('utf-8')) <= gate.MAX_BYTES, 'missing or oversized host prompt')
            session = data / 'economics' / gate.sha(event['session_id'].encode())
            old = _read(context_path)
            if old is None:
                active = _read(session / 'active-task.json')
                gate.require(not active or directory.name != gate.sha(active['task_id'].encode()),
                             'active task context is missing; do not replace its governing state')
            task_id = old.get('task_id', old['turn_id']) if old else event['turn_id']
            stopping = _stop_requested(prompt, task_id)
            if stopping['kind'] == 'task':
                save_record(directory / 'stop-request.json', stopping)
                _finish(directory, 'cancelled')
                return feedback(expected_event, 'Recorded the stop instruction. Stop the task and preserve its existing state.')
            if lifecycle == 'paused':
                _finish(directory, 'active')
                lifecycle = 'active'
            if lifecycle in TERMINAL:
                return feedback(expected_event, 'This task has completed or stopped. Do not resume automatically. Handle an independent new request as a separate task.')
            if old is not None:
                kind = ('partial-stop' if stopping['kind'] == 'partial' else
                        'continuation' if _continuation_prompt(prompt) else 'amendment')
                if event['turn_id'] == old['turn_id']:
                    gate.require(prompt == _read(directory / 'original-prompt.json')['text'],
                                 'original host turn carries a different prompt')
                    kind = 'continuation'
                messages = _read(directory / 'task-messages.json', [])
                prior = next((row for row in messages if row['turn_id'] == event['turn_id']), None)
                if prior is not None:
                    gate.require(prior['text'] == prompt, 'same host turn carries a different task message')
                elif event['turn_id'] != old['turn_id']:
                    messages.append({'turn_id': event['turn_id'], 'text': prompt,
                                     'text_sha256': gate.sha(prompt.encode('utf-8')), 'kind': kind})
                    save_record(directory / 'task-messages.json', messages)
                if stopping['kind'] == 'partial':
                    holds = _read(directory / 'task-holds.json', [])
                    if stopping not in holds:
                        holds.append(stopping)
                        save_record(directory / 'task-holds.json', holds)
                membership = {'task_id': task_id, 'directory': directory.relative_to(session).as_posix()}
                save_record(session / 'turns' / (gate.sha(event['turn_id'].encode()) + '.json'), membership, replace=False)
                save_record(directory / 'turns' / (gate.sha(event['turn_id'].encode()) + '.json'), {'task_id': task_id}, replace=False)
                state, manifest = {'status': 'ordinary-active', 'needed_actions': []}, None
                effective = _effective_request(directory)
                state['request_sha256'] = gate.sha(effective)
                text = _coordinator(directory)
                if agent_id is not None or old.get('operation_binding') is not None:
                    text = _instructions(root, state, manifest, detailed=False) + '\n' + text
                if kind == 'amendment':
                    save_record(directory / 'effective-request.json', {'text': effective.decode('utf-8'), 'sha256': gate.sha(effective)})
                    text += '\nRetained the original request and verbatim additions. Reconcile the governing requirements and current state with the changed request.'
                if kind == 'partial-stop':
                    text += '\nRecorded a hold for the specified target. Resolve the target IDs, do not execute held operations, and continue the explicitly identified parent task.'
                text += '\n' + _restoration(root, directory, state, manifest)
                if event['turn_id'] != old['turn_id']:
                    policy = sibling('hook_scoped_policy_identity', root / 'harness/policy_assets.py')
                    available = _scoped_available(root, expected_event, text, policy)
                    scoped = _scoped_instructions(event, directory, old, restore=True, available=available)
                    if scoped:
                        text = scoped + '\n' + text
                return feedback(expected_event, text)
            nonce = old.get('nonce') if old else str(uuid.uuid4())
            context = {'schema_version': 2, 'session_id': event['session_id'], 'turn_id': event['turn_id'], 'task_id': task_id,
                       'nonce': nonce, 'cwd': str(cwd), 'plugin_root': str(root), 'plugin_data': str(data),
                       'prompt_sha256': gate.sha(prompt.encode('utf-8'))}
            save_record(context_path, context, replace=False)
            save_record(directory / 'original-prompt.json', {'text': prompt, 'sha256': context['prompt_sha256']}, replace=False)
            save_record(session / 'active-task.json', {'task_id': task_id})
            save_record(session / 'turns' / (gate.sha(event['turn_id'].encode()) + '.json'),
                        {'task_id': task_id, 'directory': directory.relative_to(session).as_posix()}, replace=False)
            save_record(directory / 'turns' / (gate.sha(event['turn_id'].encode()) + '.json'), {'task_id': task_id}, replace=False)
            state = {'status': 'ordinary-active', 'needed_actions': []}
            coordinator = _coordinator(directory)
            state['request_sha256'] = context['prompt_sha256']
            text = coordinator
            if agent_id is not None:
                text += '\n' + _instructions(root, state, stage='entry')
            text += '\n' + _restoration(root, directory, state)
            policy = sibling('hook_entry_policy_identity', root / 'harness/policy_assets.py')
            _, policy_raw, _, _ = policy.discover_policy(policy.__file__)
            state['current_policy_manifest_sha256'] = gate.sha(policy_raw)
            state['task_binding_sha256'] = gate.sha(gate.canonical(None))
            state['operation_binding_sha256'] = gate.sha(gate.canonical(None))
            state['task_state_sha256'] = None
            state['unbound_operations_sha256'] = gate.sha(gate.canonical([]))
            _changed(directory, state)
            text += ('\nApply the registered operation and all applicable instructions. '
                     'Bind existing task state through state.py for authorized writes and external operations. '
                     'After selecting a specialist operation, use codex_hooks.py --root ' + json.dumps(str(cwd)) +
                     ' bind-operation --hook-context ' + json.dumps(str(context_path)) +
                     ' --operation OPERATION with each applicable --condition and optional --profile.')
            return feedback(expected_event, text)
        if lifecycle in TERMINAL and expected_event != 'Stop':
            return {}
        if lifecycle in {'interrupted', 'cancelled'}:
            return failure(expected_event, 'turn ' + lifecycle + '; no automatic restart', failure_class='cancelled')
        state, manifest = {'status': 'ordinary-active', 'needed_actions': []}, None
        context = _read(context_path, {})
        state['request_sha256'] = context.get('prompt_sha256')
        if expected_event == 'SessionStart' and event.get('source') == 'compact':
            _bound_state(directory, root)
        if expected_event in ('PreCompact', 'PostCompact'):
            gate.require(context.get('session_id') == event['session_id'] and absolute(context['cwd']) == cwd,
                         'compaction task identity changed')
            original = _read(directory / 'original-prompt.json', {})
            gate.require(original.get('sha256') == context.get('prompt_sha256'), 'original task binding changed')
            _effective_request(directory)
            selected = _operation_manifest(root, context)
            if selected is None:
                policy = sibling('hook_compaction_policy', root / 'harness/policy_assets.py')
                _, _, current, _ = policy.discover_policy(policy.__file__)
                gate.require(manifest is None or manifest['policy_id'] == current['policy_id'],
                             'adopted policy version changed')
            _bound_state(directory, root)
            record = _read(directory / 'reinjection.json', {})
            gate.require(isinstance(record, dict), 'invalid reinjection state')
            compactions = record.setdefault('compactions', {})
            gate.require(isinstance(compactions, dict), 'invalid compaction state')
            pending = bool((compactions.get(compaction_key) or {}).get('pending_restoration'))
            compactions[compaction_key] = {'event': expected_event, 'trigger': event['trigger'],
                                           'session_id': event['session_id'], 'turn_id': event['turn_id'],
                                           'agent_id': agent_id, 'agent_type': event.get('agent_type'),
                                           'pending_restoration': expected_event == 'PostCompact' or pending}
            save_record(directory / 'reinjection.json', record)
            return {}
        record = _read(directory / 'reinjection.json', {})
        pending_compaction = (record.get('compactions') or {}).get(compaction_key) or {}
        if (agent_id is not None and pending_compaction.get('assignment_required') and
                expected_event in ('PreToolUse', 'Stop', 'SubagentStop')):
            if _child_assignment(root, directory, agent_id) is not None:
                pending_compaction['pending_restoration'] = True
            elif expected_event != 'PreToolUse' or not _child_recovery_tool(event, root):
                return failure(expected_event, 'recover the exact child assignment from the parent or an authorized bound source before dependent work')
        if (expected_event in ('PreToolUse', 'Stop', 'SubagentStop') and
                pending_compaction.get('pending_restoration')):
            text = _instructions(root, state, manifest, detailed=False) + '\n' + _coordinator(directory)
            text += '\n' + _restoration(root, directory, state, manifest)
            if agent_id is not None:
                assignment = _child_assignment(root, directory, agent_id)
                if assignment is None:
                    text += ('\nThe exact child launch assignment and returned agent link are missing. Request the parent '
                             'to resend the original assignment, or bind an existing authorized task-context source with '
                             'source ID child-assignment:' + agent_id + ' using bind-child-assignment and its exact SHA-256. '
                             'Read or recovery operations can continue; child-dependent changes and completion remain held.')
                else:
                    text += ('\n[Retained child assignment source; callback provenance is not authenticated]\n' +
                             json.dumps(assignment, ensure_ascii=False))
                pending_compaction['assignment_required'] = assignment is None
            if lifecycle == 'paused':
                text += '\nThe task is paused for the next actual user input. Preserve its holds.'
            if expected_event == 'PreToolUse':
                policy = sibling('hook_pending_compaction_policy', root / 'harness/policy_assets.py')
                available = _scoped_available(root, expected_event, text, policy)
                scoped = _scoped_instructions(event, directory, context, restore=True, available=available)
                if scoped:
                    text = scoped + '\n' + text
                result = failure(expected_event, 'read the restored task and applicable rules before retrying this tool')
                result['hookSpecificOutput']['additionalContext'] = text
            else:
                gate.require(type(event.get('stop_hook_active')) is bool, 'missing Stop re-entry state')
                result = failure(expected_event, 'read the restored task and applicable rules before completion\n' + text)
            pending_compaction['pending_restoration'] = False
            pending_compaction['delivery_event'] = expected_event
            save_record(directory / 'reinjection.json', record)
            return result
        if expected_event == 'PreToolUse':
            if lifecycle == 'paused':
                return failure('PreToolUse', 'the task is waiting for the next actual user input')
            bound_result = []
            result = _pre_tool(event, root, directory, state, bound_result=bound_result)
            specific = result.setdefault('hookSpecificOutput', {'hookEventName': expected_event})
            reminder = _instructions(root, state, manifest, detailed=False)
            hint = bound_result[0] if bound_result else ''
            specific['additionalContext'] = reminder + ('\n' + hint if hint else '')
            return result
        if expected_event in ('SubagentStart', 'SubagentStop'):
            return _child(event, root, directory, state, manifest)
        if expected_event in ('PostToolUse', 'SessionStart'):
            pending = []
            observation_error = None
            loop_observation = None
            if expected_event == 'PostToolUse':
                gate.require(isinstance(event.get('tool_name'), str) and event['tool_name']
                             and isinstance(event.get('tool_use_id'), str) and event['tool_use_id'], 'missing host tool identity')
                _capture_child_launch(directory, event)
                response = event.get('tool_response')
                if isinstance(response, dict) and isinstance(response.get('session_id'), (str, int)):
                    name = str(event['tool_name']).rsplit('__', 1)[-1].split('.')[-1].lower()
                    if name == 'write_stdin':
                        gate.require(str(event.get('tool_input', {}).get('session_id')) == str(response['session_id']),
                                     'interactive continuation returned a different session identity')
                    else:
                        session_path = directory / 'sessions' / (gate.sha(str(response['session_id']).encode()) + '.json')
                        existing_session = _read(session_path)
                        if existing_session is None:
                            inputs = event.get('tool_input', {})
                            save_record(session_path, {'tool_use_id': event['tool_use_id'], 'session_id': response['session_id'],
                                'command': inputs.get('cmd', inputs.get('command')),
                                'source': 'PostToolUse-callback', 'execution_owner_connected': False, 'closed': False}, replace=False)
                        else:
                            gate.require(existing_session['tool_use_id'] == event['tool_use_id'],
                                         'interactive session belongs to another initiating call')
                try:
                    _pre_tool(event, root, directory, state)
                except (OSError, ValueError, TypeError, KeyError, AttributeError):
                    current = _read(context_path)
                    observations = current.get('unbound_operations', [])
                    observation = {'tool_name': event['tool_name'], 'tool_use_id': event['tool_use_id'],
                                   'tool_input': event.get('tool_input'), 'tool_response': response}
                    if observation not in observations:
                        save_record(context_path, {**current, 'unbound_operations': observations + [observation]})
                else:
                    _completion_callback(directory, root, event)
                    try:
                        loop_observation = _import_hook_observation(event, root, directory)
                    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError) as exc:
                        observation_error = str(exc)
                if str(event['tool_name']).rsplit('__', 1)[-1].split('.')[-1].lower() == 'write_stdin':
                    session_id = event.get('tool_input', {}).get('session_id')
                    session_path = directory / 'sessions' / (gate.sha(str(session_id).encode()) + '.json')
                    session_record = _read(session_path)
                    gate.require(session_record is not None, 'continuation belongs to an unknown task session')
                    terminal = (isinstance(response, dict) and type(response.get('exit_code')) is int) or _tool_failed(event)
                    if terminal and not session_record.get('closed'):
                        save_record(session_path, {**session_record, 'closed': True,
                                                   'terminal_tool_use_id': event['tool_use_id']})
                if _parent_tool_callback(event, directory):
                    pending = _pending_parent_returns(directory)
                if lifecycle == 'paused' and not pending:
                    return {}
            policy = sibling('hook_event_policy_identity', root / 'harness/policy_assets.py')
            _, policy_raw, _, _ = policy.discover_policy(policy.__file__)
            state['current_policy_manifest_sha256'] = gate.sha(policy_raw)
            current_context = _read(context_path, {})
            state['task_binding_sha256'] = gate.sha(gate.canonical(current_context.get('state_binding')))
            state['operation_binding_sha256'] = gate.sha(gate.canonical(current_context.get('operation_binding')))
            if current_context.get('state_binding'):
                state['task_state_sha256'] = gate.sha(gate.file_snapshot(absolute(current_context['state_binding']['state_file'])))
                bound = _bound_state(directory, root)
                if bound is not None:
                    _, bound_data, bound_task, _ = bound
                    state['task_state_semantic_sha256'] = _relevant_state_hash(bound_data, bound_task)
            state['unbound_operations_sha256'] = gate.sha(gate.canonical([row for row in
                current_context.get('unbound_operations', []) if not row.get('callback_path')]))
            changed = _changed(directory, state)
            failed = expected_event == 'PostToolUse' and _tool_failed(event)
            needs_restoration = expected_event == 'SessionStart' or changed or failed or bool(pending)
            text = ''
            if needs_restoration:
                text = _coordinator(directory)
                if (agent_id is not None or current_context.get('operation_binding') is not None
                        or expected_event == 'PostToolUse' and not failed):
                    text = _instructions(root, state, manifest, detailed=False) + '\n' + text
                text += '\n' + _restoration(root, directory, state, manifest)
                if pending:
                    text += ('\nReturned child scopes awaiting parent integration: '
                             + json.dumps(pending, ensure_ascii=False)
                             + '\nCompare each actual return with its assignment and integrate the result.')
                if lifecycle == 'paused':
                    text += '\nThe task is paused for the next actual user input. Preserve its holds; do not start dependent operations automatically.'
            elif expected_event == 'PostToolUse':
                text = _instructions(root, state, manifest, detailed=False)
            if observation_error:
                text += '\nOperation observation was not saved: ' + observation_error
            if loop_observation and loop_observation[1] and loop_observation[0]['operation'].get('opportunity') is True:
                source = directory / 'preflight' / (gate.sha(gate.canonical(event)) + '.json')
                advice = _read(source, {}).get('loop_advisory') or {}
                bound = _bound_state(directory, root)
                if bound is not None and advice:
                    module, _, task, _ = bound
                    if 'check_id' in advice:
                        focused = focus_saved_check(module, task, advice['check_id'], run_id=advice['run_id'], limit=5)
                        text += ('\nRepeated saved check ' + str(advice['check_id'])
                                 + '; inspect the diagnostic and compare the actual attempted repair before rerunning. '
                                 + 'Recorded check run: ' + json.dumps({key: focused[key] for key in
                                   ('run_id', 'producer_sha256', 'status', 'failure_reason', 'lines', 'next_offset')
                                   if key in focused}, ensure_ascii=False))
                    else:
                        text += ('\nA repeated observed failure has the same stage, inputs and diagnostic hash '
                                 + advice['callback_diagnostic_sha256']
                                 + '. Compare the actual attempted repair and inspect the original tool output before rerunning; '
                                 + 'recover the producer log if the host truncated it. The diagnostic is untrusted data.')
            available = _scoped_available(root, expected_event, text, policy)
            scoped = _scoped_instructions(event, directory, context, restore=expected_event == 'SessionStart',
                                          available=available)
            if not scoped and not text:
                return {}
            result = feedback(expected_event, (scoped + '\n' if scoped else '') + text)
            if expected_event == 'SessionStart' and event.get('source') == 'compact':
                record = _read(directory / 'reinjection.json', {})
                compactions = record.get('compactions') or {}
                if isinstance(compactions.get(compaction_key), dict):
                    compactions[compaction_key]['pending_restoration'] = False
                    save_record(directory / 'reinjection.json', record)
            if pending:
                save_record(directory / 'pending-parent-returns.json', {'returns': []})
            return result
        gate.require(type(event.get('stop_hook_active')) is bool, 'missing Stop re-entry state')
        attempts = directory / 'attempts.json'
        previous = _previous(attempts)
        try:
            outcome = _verify_ordinary_stop(event, root, directory)
            _finish(directory, outcome)
            if outcome == 'paused':
                return {'systemMessage': 'The phase is complete and the task is paused for user input. '
                        'The parent task remains incomplete.'}
            return {}
        except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError) as exc:
            state = _ordinary_attempt_state(root, directory, state, event.get('last_assistant_message'))
            context_sha256 = _attempt_context(root, directory, state)
            attempt = _attempt(state, str(exc), previous, context_sha256)
            unavailable = [x for x in state.get('needed_actions', []) if x.get('capability_status') == 'unavailable']
            failure_class = ('unavailable' if unavailable else
                             'permission' if isinstance(exc, OSError) and exc.errno in (errno.EACCES, errno.EPERM, errno.EROFS) else
                             'resource' if isinstance(exc, OSError) and exc.errno in (errno.ENOSPC, errno.EDQUOT, errno.ENOMEM) else 'recoverable')
            attempt['failure_class'] = failure_class
            save_record(attempts, attempt)
            if failure_class != 'recoverable':
                _finish(directory, 'blocked')
            text = ''
            if agent_id is not None or context.get('operation_binding') is not None:
                text = _instructions(root, state, manifest, detailed=False)
                text += '\n' + _instructions(root, state, manifest) + '\n'
            text += _restoration(root, directory, state, manifest)
            if attempt['repeated_unresolved_conditions']:
                text += '\nRepeated unresolved conditions. Follow the current repair plan and recheck the candidate.'
            if attempt['candidate_changed_recheck_required']:
                text += '\nThe candidate changed; recheck the unresolved conditions against the current candidate.'
            if failure_class != 'recoverable':
                text += '\nThe task is blocked. Recover the required permissions, inputs, or agents and resume from the same fixed original request.'
            text += '\nUnmet IDs: ' + json.dumps(attempt['unresolved_ids'], ensure_ascii=False)
            text += '\nNext actions: ' + json.dumps(attempt['next_actions'], ensure_ascii=False)
            text += '\nCause-specific repairs: ' + json.dumps(attempt['repair_plan'], ensure_ascii=False)
            return failure('Stop', str(exc) + '\n' + text, failure_class=failure_class)


def main(expected_event):
    try:
        raw = sys.stdin.buffer.read(4 * gate.MAX_BYTES + 1)
        gate.require(len(raw) <= 4 * gate.MAX_BYTES, 'hook event exceeds input budget')
        result = dispatch(gate.parse_json(raw), expected_event)
    except Exception as exc:
        # Transport/configuration errors require repair before retry.
        result = failure(expected_event, str(exc) + '; repair the hook input/configuration and retry the check')
    print(json.dumps(result, ensure_ascii=False))
    return 0


def inspect_saved_state(argv=None):
    """Explicit read-only evaluation for hosts that do not deliver callbacks."""
    parser = argparse.ArgumentParser(description='Inspect retained hook observations or a saved check log')
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--store', default='.agents/state/team.json')
    sub = parser.add_subparsers(dest='command', required=True)
    loop = sub.add_parser('evaluate-loop')
    loop.add_argument('task_id')
    loop.add_argument('--hook-context', type=Path)
    loop.add_argument('--session-sha256')
    loop.add_argument('--turn-sha256')
    check = sub.add_parser('focus-check')
    check.add_argument('task_id')
    check.add_argument('--check', required=True)
    check.add_argument('--run-id')
    check.add_argument('--view', choices=['selected', 'stdout', 'stderr'], default='selected')
    check.add_argument('--offset', type=int, default=0)
    check.add_argument('--limit', type=int, default=100)
    research = sub.add_parser('focus-research')
    research.add_argument('task_id')
    research.add_argument('--view', choices=['selected', 'log'], default='selected')
    research.add_argument('--offset', type=int, default=0)
    research.add_argument('--limit', type=int, default=100)
    operation = sub.add_parser('bind-operation')
    operation.add_argument('--hook-context', required=True, type=Path)
    operation.add_argument('--operation', required=True)
    operation.add_argument('--condition', action='append', default=[])
    operation.add_argument('--profile')
    operation.add_argument('--required-output', action='append', default=[])
    operation.add_argument('--required-action', action='append', default=[])
    operation.add_argument('--operation-kind', choices=('answer', 'create', 'modify', 'external'))
    operation.add_argument('--authority', default='')
    operation.add_argument('--user-change')
    operation.add_argument('--external-target', action='append', default=[])
    child = sub.add_parser('bind-child-assignment')
    child.add_argument('--hook-context', required=True, type=Path)
    child.add_argument('--agent-id', required=True)
    child.add_argument('--source-id', required=True)
    child.add_argument('--source-sha256', required=True)
    args = parser.parse_args(argv)
    root = absolute(str(args.root))
    if args.command == 'bind-operation':
        print(json.dumps(bind_operation(args.hook_context, root, args.operation,
                                        conditions=args.condition, profile=args.profile, required_outputs=args.required_output,
                                        required_actions=args.required_action, operation_kind=args.operation_kind,
                                        authority=args.authority, user_change=args.user_change,
                                        external_targets=args.external_target), ensure_ascii=False, indent=2))
        return 0
    if args.command == 'bind-child-assignment':
        print(json.dumps(bind_child_assignment(args.hook_context, root, args.agent_id,
                                               args.source_id, args.source_sha256), ensure_ascii=False, indent=2))
        return 0
    module = sibling('inspect_state', base / 'state.py')
    store = root / module.relative(root, args.store)
    gate.require(Path(args.store).parts[:2] == ('.agents', 'state'), 'state store is outside its existing area')
    before = gate.sha(gate.file_snapshot(store))
    data = _read_state_store(store)
    gate.require(before == gate.sha(gate.file_snapshot(store)), 'state store changed during evaluation')
    task = data['tasks'][args.task_id]
    if args.command == 'focus-check':
        result = focus_saved_check(module, task, args.check, run_id=args.run_id, view=args.view,
                                   offset=args.offset, limit=args.limit)
        result['state_file'] = str(store)
        result['state_sha256'] = before
    elif args.command == 'focus-research':
        result = focus_saved_research(module, task, view=args.view, offset=args.offset, limit=args.limit)
        result['state_file'] = str(store)
        result['state_sha256'] = before
    else:
        recorded = [row for row in task.get('usage', []) if row.get('usage_contract') == 3
                    and (row.get('identity') or {}).get('source_id') == 'codex-hook-preflight']
        result = {'task_id': task['task_id'], 'state_sha256': before,
                  'recorded_observations': len(recorded), 'verified_hook_observations': 0,
                  'evaluation': None, 'source_verification': 'not-checked'}
        if args.hook_context is not None:
            context_path = absolute(str(args.hook_context))
            directory = context_path.parent
            context = _read(context_path, {})
            binding = context.get('state_binding') or {}
            gate.require(context_path.name == 'context.json' and binding.get('task_id') == task['task_id']
                         and binding.get('state_file') == str(store) and binding.get('state_root') == str(root),
                         'hook context does not match the requested state task')
            gate.require(gate.hexhash(args.session_sha256) and gate.hexhash(args.turn_sha256),
                         'actual session and turn hashes are required')
            verified = _verified_loop_rows(module, task, directory, args.session_sha256, args.turn_sha256)
            rows = [row for row, _ in verified]
            result['verified_hook_observations'] = len(rows)
            result['source_verification'] = 'saved hook preflight and task binding; host authentication not asserted'
            result['evaluation'] = evaluate_loop(rows, _completed_turn_lengths(module, data, task, directory, root))
        elif args.session_sha256 or args.turn_sha256:
            raise ValueError('a matching hook context is required to verify observations')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(inspect_saved_state())
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


