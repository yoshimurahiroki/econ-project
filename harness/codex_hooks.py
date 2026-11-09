#!/usr/bin/env python3
"""Task callbacks, current instructions and attributable operation results."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import shlex
import shutil
import sys
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

_INVOCATION_POLICY = {}

if __name__ == '__main__':
    sys.dont_write_bytecode = True


@lru_cache(maxsize=None)
def sibling(path):
    """Share each sibling within one callback; dispatch starts a fresh snapshot."""
    spec = importlib.util.spec_from_file_location('hook_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = Path(__file__).resolve().parent
gate = sibling(next(path for path in
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
    if path.exists():
        info = path.stat()
        gate.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'invalid operational record')
        if info.st_size == len(raw) <= gate.MAX_BYTES and gate.regular_bytes(path) == raw:
            return
        gate.require(replace, 'existing hook context differs')
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
        fields.update(key for key in ('formal_selected', 'state_binding', 'operation_binding', 'unbound_operations', 'completion_contract', 'reading_stage') if key in context)
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
    if event in CONTEXT_EVENTS or event == 'PreToolUse':
        return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': text}}
    return {'systemMessage': text}


def failure(event, reason, repeated=False, failure_class='recoverable'):
    """A Stop continuation is never limited by count or stop_hook_active."""
    reason = 'Economics task check: ' + reason
    if event in ('PostCompact', 'SessionStart'):
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


def _read_state_store(path, *, with_digest=False):
    """Read the existing state store with the same safe file boundary as snapshots."""
    with gate._open_regular(path) as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read()
        try:
            value = json.loads(raw, object_pairs_hook=gate._pairs,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError('invalid state store JSON') from exc
        after = os.fstat(stream.fileno())
        current = os.stat(absolute(str(path)), follow_symlinks=False)
    gate.require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode)
                 == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode)
                 == (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns, current.st_mode),
                 'state store changed while reading')
    return (value, gate.sha(raw)) if with_digest else value


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
    policy = sibling(root / 'harness/policy_assets.py')
    owner, _, selected, _, contract = policy.discover_policy(
        policy.__file__, operation=operation, conditions=conditions, profile=profile, with_contract=True)
    gate.require(Path(policy.__file__).absolute() == (root / 'harness/policy_assets.py').absolute(),
                 'hook policy module does not belong to this runtime')
    return owner, selected, contract


def bind_operation(context_path, state_root, operation, conditions=(), profile=None, *,
                   required_outputs=(), required_actions=(), operation_kind=None, authority='', user_change=None, external_targets=(), stage=None):
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
        # An explicit rebind adopts the runtime executing this command, including
        # after a release moves its canonical files. Task authority stays intact.
        policy = sibling(base / 'policy_assets.py')
        root = policy.discover_policy(policy.__file__, load_assets=False)[0]
        previous = context.get('operation_binding') or {}
        if stage is not None and operation == previous.get('operation'):
            conditions = conditions or previous['conditions']
            profile = previous['profile'] if profile is None else profile
        _, selected, contract = _resolve_operation_binding(root, operation, conditions, profile)
        if stage is not None:
            routes = sibling(root / 'scripts/route_registry.py').load_routes(root)
            gate.require(stage in routes.get('reading_stages', {}), 'unknown reading stage')
        binding = {'operation': selected['selection']['operation'],
                   'conditions': selected['selection']['conditions'], 'profile': profile,
                   'policy_id': selected['policy_id'], 'selection_sha256': gate.sha(gate.canonical(selected)),
                   'assets': selected['assets'], 'active_rules': selected['active_rules'],
                   'resource_sections': selected['resource_sections'], 'contract': contract}
        updated = {**context, 'plugin_root': str(root), 'operation_binding': binding}
        if stage is not None:
            updated['reading_stage'] = stage
        elif binding != context.get('operation_binding'):
            updated.pop('reading_stage', None)
        if context.get('state_binding') is None:
            module = sibling(root / 'harness/state.py')
            retained = context.get('completion_contract', {})
            output_args = list(required_outputs) if required_outputs else [json.dumps(row) for row in retained.get('required_outputs', [])]
            action_args = list(required_actions) if required_actions else [json.dumps(row) for row in retained.get('required_actions', [])]
            outputs, actions = module.contract(state_root, output_args, action_args)
            operation_kind = operation_kind or retained.get('operation_kind')
            authority = authority or retained.get('authority', '')
            if not any(row['kind'] == 'message' for row in outputs):
                outputs.append({'role': 'response', 'kind': 'message', 'target': 'response'})
            gate.require(operation_kind in {'answer', 'create', 'modify', 'external'}, 'declare the operation kind')
            gate.require(operation_kind != 'answer' or not actions and all(row['kind'] == 'message' for row in outputs),
                         'answer-only contracts cannot authorize modifications, artifacts or external actions')
            gate.require(operation_kind == 'answer' or actions,
                         'verifiable deliverables require their complete producing actions and exact targets')
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
        else:
            gate.require(not (required_outputs or required_actions or external_targets or operation_kind or authority or user_change),
                         'the bound state owner already owns the completion contract')
            bound = _bound_state(path.parent, root)
            gate.require(bound is not None and bound[2].get('completion_contract') == 1,
                         'bound state needs the original complete output/action contract')
        if context != updated:
            save_record(path, updated)
        return binding


def _operation_manifest(root, context, directory=None):
    binding = context.get('operation_binding')
    if binding is None:
        return None
    gate.require(isinstance(binding, dict) and set(binding) ==
                 {'operation', 'conditions', 'profile', 'policy_id', 'selection_sha256',
                  'assets', 'active_rules', 'resource_sections', 'contract'},
                 'invalid operation binding')
    policy, _, _, catalog, verification = _policy_snapshot(root, directory, context)
    selection = {'selection': {'operation': binding['operation'], 'conditions': binding['conditions'],
                               'profile': binding['contract']['selected_profile'], 'templates': []},
                 'active_rules': binding['active_rules'], 'resource_sections': binding['resource_sections']}
    selected = {**catalog, **selection}
    gate.require(policy.digest(policy.canonical(selection)) == verification.get('selection_sha256')
                 and policy.digest(policy.canonical(binding['contract'])) == verification.get('contract_sha256')
                 and selected['policy_id'] == binding['policy_id']
                 and gate.sha(gate.canonical(selected)) == binding['selection_sha256']
                 and selected['assets'] == binding['assets'] and selected['active_rules'] == binding['active_rules']
                 and selected['resource_sections'] == binding['resource_sections'],
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
    gate.require(_read(session / 'active-task.json') == {'task_id': context['task_id']}
                 and _lifecycle(directory) == 'active', 'state binding requires the active original task')
    root = absolute(str(state_root))
    gate.require(root == absolute(context['cwd']), 'state root differs from the original task root')
    store = absolute(str(state_file))
    gate.require(store.is_relative_to(root / '.agents/state'), 'task state is outside its existing store')
    state_module = sibling(Path(context['plugin_root']) / 'harness/state.py')
    data = _read_state_store(store)
    task = data['tasks'][task_id]
    gate.require(task.get('completion_contract') == 1, 'state binding requires the complete original output/action contract')
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
    if previous != binding:
        save_record(path, {**context, 'state_binding': binding})
        retained = _read(directory / 'reinjection.json', {})
        save_record(directory / 'reinjection.json', {**retained, 'instruction_policy_sha256': None})
    return binding


def _bound_state(directory, root, *, check_sources=True):
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
    module = sibling(root / 'harness/state.py')
    data = _read_state_store(store)
    task = data['tasks'][binding['task_id']]
    messages = _read(directory / 'task-messages.json', [])
    original = _read(directory / 'original-prompt.json', {})
    actual = {(row.get('turn_id'), row.get('text')) for row in messages if row.get('kind') != 'contract-acceptance'}
    actual.add((context.get('turn_id'), original.get('text')))
    for owner in [task, *module.task_ancestors(data['tasks'], task)]:
        for release in owner.get('hold_releases', []):
            message = release.get('message', {})
            gate.require(message.get('source') == 'user' and message.get('source_task_id') == owner['task_id']
                         and message.get('hold_id') == release.get('hold_id')
                         and (message.get('message_id'), message.get('text')) in actual
                         and isinstance(release.get('evidence'), dict) and release['evidence']
                         and (not check_sources or not module.changed(state_root, release['evidence'])),
                         'hold release does not match a saved actual user message and evidence')
    request_sha = binding['effective_request_sha256']
    gate.require(any(row.get('content_sha256') == request_sha and row.get('path')
                     and (not check_sources or module.digest(state_root / module.relative(state_root, row['path'])) == request_sha)
                     for row in (task.get('task_context') or {}).get('request_refs', [])),
                 'state no longer binds the effective request source')
    gate.require(task.get('authority') and (not check_sources or not module.context_changes(state_root, task))
                 and not module.effective_constraints(data['tasks'], task, state_root if check_sources else None)['scope_errors'],
                 'state authority, instructions or scope require reconciliation')
    refs = (task.get('task_context') or {}).get('active_instruction_refs', [])
    gate.require(refs and (not check_sources or all(row.get('path') and module.digest(state_root / module.relative(state_root, row['path']))
                              == row.get('content_sha256') for row in refs)),
                 'bound instruction sources or versions require reconciliation')
    return module, data, task, state_root


def _completion_task(directory, root, *, check_sources=True):
    """Use the existing hook context, without creating a local state store."""
    context = _read(directory / 'context.json', {})
    contract = context.get('completion_contract')
    if contract is None:
        return None
    module = sibling(root / 'harness/state.py')
    gate.require(isinstance(contract, dict) and (not check_sources or module.contract_current(Path(context['cwd']), contract))
                 and contract.get('request_sha256') == gate.sha(_effective_request(directory)),
                 'completion requirements or original request need reconciliation')
    outputs, actions = contract['required_outputs'], contract['required_actions']
    if check_sources:
        normalized = module.contract(Path(context['cwd']),
            [json.dumps(row) for row in outputs], [json.dumps(row) for row in actions])
        gate.require(normalized == (outputs, actions), 'completion requirements are not normalized')
    scopes = sorted({row['target'] for row in outputs if row['kind'] == 'file'} |
                    {row['target_id'] for row in actions if row['target_kind'] == 'file'})
    task = {**contract, 'task_id': context['task_id'], 'parent': None, 'status': 'running',
            'write_scope': scopes, 'scope': scopes, 'holds': [], 'hold_releases': [], 'completion_contract': 1,
            'outputs': {}, 'action_results': [], 'consumed_inputs': {}, 'read_dependencies': {},
            'consumes': [], 'dependency_versions': {}, 'required_checks': [], 'check_receipts': {}}
    return module, {'tasks': {task['task_id']: task}}, task, Path(context['cwd'])


def _pending_task_holds(directory, bound, *, check_sources=True):
    holds = _read(directory / 'task-holds.json', [])
    if bound is None:
        return holds
    module, data, task, state_root = bound
    messages = [row for row in _read(directory / 'task-messages.json', []) if row.get('kind') != 'contract-acceptance']
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
                               for row in messages) or (check_sources and module.changed(state_root, evidence))):
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


def _policy_snapshot(root, directory=None, context=None, conditions=()):
    context = context if context is not None else _read(directory / 'context.json', {}) if directory else {}
    if directory is None and context.get('task_id') and context.get('plugin_data'):
        directory = (absolute(context['plugin_data']) / 'economics' / gate.sha(context['session_id'].encode()) /
                     'tasks' / gate.sha(context['task_id'].encode()))
    binding = context.get('operation_binding') or {}
    active_conditions = sorted(set(binding.get('conditions', [])) | set(conditions))
    selection = ({'operation': binding['operation'], 'conditions': active_conditions,
                  'profile': binding['profile']} if binding else {'conditions': active_conditions})
    key = (str(root), str(directory), gate.sha(gate.canonical(selection)))
    if key in _INVOCATION_POLICY:
        return _INVOCATION_POLICY[key]
    policy = sibling(root / 'harness/policy_assets.py')
    record = _read(directory / 'reinjection.json', {}) if directory else {}
    retained = record.get('policy_verification', {})
    verification = dict(retained) if isinstance(retained, dict) else {}
    owner, raw, current, _ = policy.discover_policy(policy.__file__, verification=verification,
                                                  load_assets=False, **selection)
    if directory and retained != verification:
        record['policy_verification'] = verification
        save_record(directory / 'reinjection.json', record)
    result = (policy, owner, raw, current, verification)
    _INVOCATION_POLICY[key] = result
    return result


def _restoration(root, directory, state, manifest=None, conditions=(), *, restore=True, instruction_event=None):
    """Restore fixed inputs, never a generated substitute for the host prompt."""
    context = _read(directory / 'context.json', {})
    original = _read(directory / 'original-prompt.json')
    if original is None and (directory / 'run/request.txt').is_file():
        original = {'text': gate.regular_bytes(directory / 'run/request.txt').decode('utf-8')}
    prompt = original.get('text') if isinstance(original, dict) else None
    gate.require(isinstance(prompt, str) and gate.sha(prompt.encode('utf-8')) == context.get('prompt_sha256'),
                 'restore-fixed-request: obtain the exact host original; do not reconstruct it from a candidate')
    request = _effective_request(directory).decode('utf-8') if context.get('schema_version') == 2 else prompt
    selected = _operation_manifest(root, context, directory)
    policy, owner, policy_raw, current, _ = _policy_snapshot(root, directory, context, conditions)
    gate.require(Path(policy.__file__).absolute() == (root / 'harness/policy_assets.py').absolute(),
                 'hook policy module does not belong to this runtime')
    gate.require(manifest is None or manifest['policy_id'] == current['policy_id'], 'adopted policy version changed')
    retained = _read(directory / 'reinjection.json', {})
    context_lost = restore
    retained_bodies = (() if context_lost or retained.get('instruction_body_root') != str(owner)
                       else retained.get('instruction_read_bodies', ()))
    binding_sha = gate.sha(gate.canonical(context.get('operation_binding')))
    restore = (restore or retained.get('instruction_policy_sha256') != gate.sha(policy_raw)
               or retained.get('instruction_binding_sha256') != binding_sha
               or retained.get('instruction_stage') != context.get('reading_stage'))
    source_versions = {str(owner / row['path']): row['sha256']
                       for row in current['assets'].values()}
    request_sha = gate.sha(request.encode('utf-8'))
    restore_request = context_lost or retained.get('instruction_request_sha256') != request_sha
    if not context.get('state_binding') and not context.get('completion_contract'):
        state = {**state, 'needed_actions': [*state.get('needed_actions', []),
                 {'requirement_id': 'task-completion-contract', 'action': 'bind the original complete deliverables and authority before changes or completion'}]}
    packet = policy.instruction_context(owner, manifest=current,
        status={**state, 'lifecycle': _lifecycle(directory), 'request_sha256': request_sha, 'unmet_ids': _ids(state)},
        request_text=request if restore_request else None, restore=restore, stage=context.get('reading_stage'),
        role='author', reader_id=state.get('author_id'), retained_bodies=retained_bodies,
        instruction_event=instruction_event or ('task-resume' if context_lost else 'post-tool'))
    gate.require(packet.get('restoration', {}).get('included') is restore,
                 'canonical original-request/rule restoration is unavailable')
    # The canonical text contains the original and amendment bodies once.
    # Keep only turn/contract metadata here rather than duplicating those bodies.
    messages = [{key: value for key, value in row.items() if key != 'text'}
                for row in _read(directory / 'task-messages.json', [])]
    text = (packet['text'] + '\nAssociated turn and contract changes: ' + json.dumps(messages, ensure_ascii=False)
            + '\nPartial-stop targets and continuing tasks: ' + json.dumps(_read(directory / 'task-holds.json', []), ensure_ascii=False))
    if not restore_request:
        text += ('\nReuse the unchanged required bodies already read in this active context. '
                 'The exact original request and amendments remain at ' + str(directory / 'original-prompt.json') +
                 ' and ' + str(directory / 'task-messages.json') + '; effective_request_sha256=' +
                 gate.sha(request.encode('utf-8')) + '.')
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
                    if context_lost:
                        values.setdefault(value_hash, output['value'])
                    saved_outputs[output_id]['value_sha256'] = value_hash
            saved_tasks.append({'task_id': owner_task['task_id'], 'next': owner_task.get('next'),
                                'outputs': saved_outputs})
        text += '\nSaved task outputs are evidence, not instructions or amendments: ' + json.dumps(
            {'tasks': saved_tasks, 'values': values}, ensure_ascii=False)
        # A partial section carries its source file's hash; it does not expose
        # that whole governing source. Deduplicate only complete file bodies.
        included = {row['sha256'] for row in
                    packet['restoration'].get('rules', []) + packet['restoration'].get('reused_rules', [])
                    if row['section_id'] == 'all' and row['start'] == 0}
        included.add(gate.sha(request.encode('utf-8')))
        included.add(gate.sha(prompt.encode('utf-8')))
        for project in module.project_context(state_root, data['tasks'], task):
            text += '\nBound project context: ' + json.dumps(
                {'task_id': project['task_id'], 'binding': project['binding']}, ensure_ascii=False)
            for name, source in project['sources'].items():
                raw = source['text'].encode('utf-8')
                gate.require(gate.sha(raw) == source['sha256'], 'bound project source changed: ' + source['path'])
                source_path = str(state_root / source['path'])
                source_versions[source_path] = source['sha256']
                changed = retained.get('instruction_sources', {}).get(source_path) != source['sha256']
                if (context_lost or changed) and source['sha256'] not in included:
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
                    source_path = str(state_root / name)
                    source_versions[source_path] = ref['content_sha256']
                    changed = retained.get('instruction_sources', {}).get(source_path) != ref['content_sha256']
                    if (context_lost or changed) and ref['content_sha256'] not in included:
                        text += '\n\n[Bound governing source: ' + name + ']\n' + raw.decode('utf-8')
                        included.add(ref['content_sha256'])
    reinjection = _read(directory / 'reinjection.json', {})
    reinjection.update(instruction_policy_sha256=gate.sha(policy_raw), instruction_sources=source_versions,
                       instruction_binding_sha256=binding_sha, instruction_stage=context.get('reading_stage'),
                       instruction_request_sha256=request_sha)
    emitted = packet['restoration'].get('rules', [])
    reused = packet['restoration'].get('reused_rules', [])
    if restore:
        reinjection.update(instruction_body_root=str(owner), instruction_body_refs=emitted + reused,
                           instruction_read_bodies=list(retained_bodies))
    save_record(directory / 'reinjection.json', reinjection)
    return text


def _retain_exposed_rule_bodies(directory, event):
    """Reuse only complete pinned bodies actually present in native tool output.

    This extends the existing reinjection snapshot; it proves text exposure,
    never semantic reading, task acceptance or authority. Child contexts do not
    inherit their parent's exposed text.
    """
    if event.get('agent_id') or _tool_failed(event):
        return
    record = _read(directory / 'reinjection.json', {})
    refs = record.get('instruction_body_refs', [])
    if not refs or not record.get('instruction_body_root'):
        return
    retained = list(record.get('instruction_read_bodies', []))
    def identity(row):
        return tuple(row[key] for key in ('path', 'sha256', 'start', 'end'))
    seen = {identity(row) for row in retained}
    pending = [row for row in refs if identity(row) not in seen]
    if not pending:
        return
    texts = []
    def collect(value, depth=0):
        if depth > 6:
            return
        if isinstance(value, str):
            texts.append(value)
            if value.lstrip().startswith(('{', '[')):
                try:
                    collect(json.loads(value), depth + 1)
                except (ValueError, RecursionError):
                    pass
        elif isinstance(value, dict):
            for key in ('output', 'content', 'text', 'result', 'structuredContent'):
                if key in value:
                    collect(value[key], depth + 1)
        elif isinstance(value, list):
            for item in value:
                collect(item, depth + 1)
    collect(event.get('tool_response'))
    source_root = Path(record['instruction_body_root'])
    sources = {}
    for row in pending:
        path = source_root / row['path']
        if row['path'] not in sources:
            try:
                raw = gate.regular_bytes(path)
                sources[row['path']] = gate.sha(raw), raw.decode('utf-8')
            except (OSError, UnicodeError):
                sources[row['path']] = None
        if sources[row['path']] is None:
            continue
        digest, source = sources[row['path']]
        if digest != row['sha256']:
            continue
        body = source[row['start']:row['end']]
        if body and any(body in text for text in texts):
            retained.append(row)
            seen.add(identity(row))
    if retained != record.get('instruction_read_bodies', []):
        save_record(directory / 'reinjection.json', {**record, 'instruction_read_bodies': retained})


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


def _tool_failed(event):
    """A returned failure selects more instruction detail."""
    returned = event.get('tool_response')
    if not isinstance(returned, dict):
        return False
    tool = event.get('tool_name')
    if isinstance(tool, str) and tool.startswith(('mcp__codex_apps__github_', 'mcp__codex_apps__plugin_creator_')):
        native = sibling(next(path for path in
                         (base / 'native_check.py', base / 'NATIVE_CHECK.py') if path.is_file()))
        if tool not in native.CONNECTOR_WRITE_TOOLS:
            return (returned.get('isError') is True or returned.get('success') is False
                    or bool(returned.get('error')))
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


def _continuation_prompt(prompt, *, action_only=False):
    text = unicodedata.normalize('NFKC', prompt).casefold().strip(' \t\r\n。.!?？')
    action = r'(?:続けて(?:ください)?|継続して(?:ください)?|再開して(?:ください)?|(?:please\s+)?(?:continue|resume)(?:\s+(?:the current task|this task|the task|working))?)'
    return bool(re.fullmatch(action, text) or not action_only and
                re.fullmatch(r'(?:まだ|進捗(?:は)?|状況(?:は)?|status|any update|are you done)', text))


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
    identities = [response[key] for key in ('agent_id', 'task_name') if key in response]
    if (not identities or any(not isinstance(value, str) or not value.strip()
                              or value.strip() != value for value in identities)):
        return None
    identity = identities[0]
    messages = [inputs[key] for key in ('message', 'prompt') if key in inputs]
    if (agent_id is not None and identity != agent_id or not messages
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


def _child_recovery_tool(event, root, directory):
    """Allow read and existing state/parent-recovery paths while assignment is missing."""
    tool, inputs = event.get('tool_name'), event.get('tool_input')
    if not isinstance(tool, str) or not isinstance(inputs, dict):
        return False
    if _tool_effect(event, root, directory, enforce_authority=False)[4] == 'read':
        return True
    name = tool.rsplit('__', 1)[-1].split('.')[-1].lower()
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
        restored = _restoration(root, directory, state, manifest, conditions=('delegation_active',),
                                instruction_event='worker-start')
        assignment = _child_assignment(root, directory, agent_id)
        restored += ('\nThe original request above supplies parent constraints. Execute only the host-assigned child scope; '
                     'do not replace the research design, downgrade its method or close the parent through this return.')
        if assignment is not None:
            restored += '\n[Retained exact child assignment]\n' + json.dumps(assignment, ensure_ascii=False)
        else:
            restored += '\nKeep the original host launch assignment; recover it from the parent before dependent work if unavailable.'
        gate.require(observed is None or (observed.get('agent_id') == agent_id
                     and observed.get('agent_type') in (None, agent_type)), 'host child identity changed')
        start['start_observation'] = {'event': 'SubagentStart', 'agent_id': agent_id,
            'payload_sha256': gate.sha(gate.canonical(event)),
            'observed_at': datetime.now(timezone.utc).isoformat(), 'source': 'hook-callback'}
        for key in ('launch_observation', 'assignment_reference'):
            if isinstance(observed, dict) and key in observed:
                start[key] = observed[key]
        save_record(path, start)
        return feedback('SubagentStart', restored +
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
    save_record(path, initial)
    pending = {'agent_id': agent_id, 'agent_type': agent_type, 'return_sha256': return_sha,
               'payload_sha256': returned['payload_sha256'], 'status': initial['status'],
               'scope': 'child-assignment-only'}
    _queue_parent_return(directory, pending)
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


def _recorded_check_covered(module, task, check, targets=None):
    """Compare the selected check's executed receipts with its saved target versions."""
    required = module.requested_targets(task)
    selected = task.get('check_targets', {}).get(check)
    if selected is not None:
        if set(selected) - required:
            return False
        required = set(selected)
    if targets is not None:
        required &= set(targets)
    latest = {}
    for receipt in task.get('check_receipts', {}).values():
        if receipt.get('operation') != check:
            continue
        if receipt.get('versions') != module.versions(task, receipt.get('output_ids'), receipt.get('input_ids')):
            continue
        if task.get('independent_review') and receipt.get('review_kind') != 'worker-result':
            continue
        covered = (set(task['outputs']) | {row['target_id'] for row in task.get('action_results', [])}
                   if receipt.get('output_ids') is None else set(receipt['output_ids']))
        order = (receipt.get('sequence', 0), receipt.get('at', ''))
        for target in required & covered:
            if target not in latest or order >= latest[target][0]:
                latest[target] = (order, receipt)
    return all(target in latest and latest[target][1].get('result') == 'passed' for target in required)


def _recorded_completion(module, tasks, task, state_root, final_message=None):
    if task['status'] != 'completed':
        return False
    constraints = module.effective_constraints(tasks, task)
    missing = module.missing_required_results(task, lambda row: module.receipt_current(state_root, task, row),
        root=state_root, final_message=final_message)
    if final_message is not None:
        gate.require(not missing, 'bound requirements are unmet: ' + json.dumps(missing, ensure_ascii=False))
    return (task.get('completion_contract') == 1
            and not constraints['holds'] and not constraints['scope_errors']
            and not module.dependencies_changed(tasks, task)
            and not missing
            and all(_recorded_check_covered(module, task, check) for check in task['required_checks']))


def _ordinary_wait_leaf(module, data, task, state_root, directory, message):
    """Validate the completed phase while retaining the held parent contract."""
    tasks = data['tasks']
    constraints = module.effective_constraints(tasks, task)
    holds = constraints['holds']
    gate.require(_explicit_user_wait(directory) and task['status'] == 'blocked'
                 and task.get('blocked_reason') == 'user_hold' and task.get('holds')
                 and holds and all(row.get('targets') for row in holds),
                 'explicit user wait and a target-specific current user hold are required')
    labels = {row['hold_id'] for row in holds} | {target.split(':', 1)[-1]
              for row in holds for target in row['targets']}
    gate.require(all(row.get('target_ids') and set(row['target_ids']) <= labels
                     for row in _pending_task_holds(directory, (module, data, task, state_root), check_sources=False)),
                 'unresolved user hold is not represented in the current state')
    gate.require(task.get('completion_contract') == 1 and not constraints['scope_errors'],
                 'parent task contract or scope requires reconciliation')
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
    gate.require(all(_recorded_check_covered(module, task, check, targets=targets)
                     for check in task['required_checks']), 'parent phase checks are incomplete')
    candidates = [child for child in tasks.values() if child.get('parent') == task['task_id']
                  and not any(other.get('parent') == child['task_id'] for other in tasks.values())]
    descendants = [child for child in tasks.values() if any(
        ancestor['task_id'] == task['task_id'] for ancestor in module.task_ancestors(tasks, child))]
    for child in descendants:
        inherited = module.effective_constraints(tasks, child)
        gate.require(not inherited['scope_errors'], 'child authority or scope requires reconciliation')
        if not inherited['holds']:
            gate.require(_recorded_completion(module, tasks, child, state_root),
                         'nonheld descendant task is not current and complete')
    leaves = [child for child in candidates if _recorded_completion(module, tasks, child, state_root)]
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
    if not (directory / relative).is_file():
        return
    raw = gate.regular_bytes(directory / relative)
    binding = gate.parse_json(raw)
    if 'callback' not in binding:
        return
    if binding.get('authorization', {}).get('task_control'):
        contract = context['completion_contract']
        requested_files = {row['target'] for row in contract['required_outputs'] if row['kind'] == 'file'}
        effects = {Path(target).relative_to(context['cwd']).as_posix() for _, target in binding.get('resolved_effects', [])}
        requested_action = any(row['operation'] == binding['operation'] and row['target_id'] in binding['targets']
                               for row in contract['required_actions'])
        if not requested_action and not requested_files.intersection(effects):
            return  # Incidental bookkeeping cannot replace the original deliverables.
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
        if binding.get('effect') != 'read':
            call = binding.get('callback', {})
            approval = _read(directory / 'preflight' / ('authorized-' + gate.sha(str(call.get('tool_use_id')).encode()) + '.json'))
            gate.require(approval is not None and binding.get('authorization') == approval,
                         'saved modifying result lacks its actual matching preflight authority')
        producer = _read(directory / 'preflight' / ('authorized-' + gate.sha(str(binding.get('production_call_id')).encode()) + '.json'), {})
        before = producer.get('output_versions_before', {}) if producer.get('task_id') == context.get('task_id') else {}
        versions = {target: version for target, version in binding.get('output_versions', {}).items()
                    if target in before and version != before[target]}
        observed.append({**binding['callback'], 'preflight': binding,
                         'output_versions': versions})
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
        if target not in row.get('output_versions', {}):
            return None
        latest = next((item.get('output_versions', {}).get(target) for item in reversed(observed)
                       if target in item.get('output_versions', {})), None)
        if operation in {'delete', 'remove'}:
            if (target not in row.get('preflight', {}).get('deleted_targets', []) or latest is not None
                    or (state_root / target).exists() or (state_root / target).is_symlink()):
                return None
        elif not latest or row.get('output_versions', {}).get(target) != latest:
            return None
        else:
            try:
                if gate.file_snapshot(state_root / target).sha256 != latest:
                    return None
            except (OSError, ValueError):
                return None
        return {**requirement, 'result': 'passed', 'callback': row}
    native = sibling(next(path for path in
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
        elif target.startswith('agent-call://'):
            gate.require(target == 'agent-call://' + gate.sha(gate.canonical({'tool_name': tool, 'tool_input': args}))
                         and operation == name and returned, 'delegation call differs from its fixed authorized input')
            identity = _spawn_assignment(row) if name == 'spawn_agent' else args.get('target', args.get('agent_id'))
            gate.require(isinstance(identity, str) and identity, 'delegation result lacks its actual agent identity')
            if name in {'spawn_agent', 'followup_task'}:
                child = _read(directory / 'children' / (gate.sha(identity.encode()) + '.json'), {})
                gate.require(child.get('return_observation') and child.get('return_text'), 'delegated scope has not returned')
            outcome = {'status': 'success', 'operation': operation, 'target': target, 'agent_id': identity}
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
    bound = _completion_task(directory, root, check_sources=False)
    if bound is None:
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
            version = next((row.get('output_versions', {}).get(target) for row in reversed(observed)
                            if target in row.get('output_versions', {})), None)
            if not version:
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
    missing = module.missing_required_results(task, lambda result: result['result'] == 'passed',
                                             root=state_root, final_message=message)
    gate.require(not missing, 'required outputs or actual operations are incomplete: ' + json.dumps(missing))


def _require_original_requirements_acceptance(directory, module, owners):
    """Only an actual user message can confirm that the declared scope is complete."""
    identity = module.completion_acceptance_id(gate.sha(_effective_request(directory)), owners)
    command = 'ERS accept-completion-contract ' + identity
    messages = _read(directory / 'task-messages.json', [])
    gate.require(any(row.get('kind') == 'contract-acceptance' and row.get('text', '').strip() == command
                     for row in messages),
                 'original request requirements have not been independently confirmed; '
                 'executor declarations cannot establish completeness. After reviewing the complete original request '
                 'and this contract, the user may submit exactly: ' + command)


def _verify_ordinary_stop(event, root, directory):
    message = event.get('last_assistant_message')
    gate.require(isinstance(message, str) and message.strip(), 'host assistant message is unavailable')
    if not event.get('agent_id'):
        gate.require(not _pending_parent_returns(directory), 'consume the returned child scope before parent completion')
        for path in sorted((directory / 'children').glob('*.json')):
            child = _read(path)
            gate.require(child.get('return_observation') and child.get('status') not in {
                'restoration-check-failed', 'scope-check-failed'}, 'child work has not returned its completed scope')
    gate.require(_read(directory / 'reinjection.json', {}).get('instruction_policy_sha256', True) is not None,
                 'a governing source changed; rebind its adopted instructions before completion')
    observed = _completion_observations(directory, _read(directory / 'context.json', {}))
    bound = _bound_state(directory, root)
    if bound is None:
        gate.require(not _pending_task_holds(directory, None), 'unresolved task hold requires continuation')
        gate.require(_completion_task(directory, root) is not None,
                     'bind the original complete deliverables before completion; use an answer-only contract for a conversational response')
        _verify_completion_contract(directory, root, message, observed)
        module, _, task, _ = _completion_task(directory, root)
        _require_original_requirements_acceptance(directory, module, [task])
        return 'completed'
    module, data, task, state_root = bound
    if _recorded_completion(module, data['tasks'], task, state_root, message):
        gate.require(all(_recorded_completion(module, data['tasks'], ancestor, state_root, message)
                         for ancestor in module.task_ancestors(data['tasks'], task)),
                     'bound leaf cannot complete an unfinished parent task')
        gate.require(not _pending_task_holds(directory, bound, check_sources=False), 'unresolved task hold requires continuation')
        candidates = [task['outputs'].get(row['target'], {}) for row in task['required_outputs'] if row['kind'] == 'message']
        gate.require(any(row.get('value') == message for row in candidates),
                     'host message differs from the required recorded message output')
        _require_original_requirements_acceptance(directory, module,
            [task, *module.task_ancestors(data['tasks'], task)])
        receipt_tasks, outcome = [task], 'completed'
    else:
        receipt_tasks = [task, *_ordinary_wait_leaf(module, data, task, state_root, directory, message)]
        outcome = 'paused'
    for event in observed:
        matched = False
        for receipt in (receipt for owner in receipt_tasks for receipt in owner.get('action_results', [])
                        if receipt.get('result') == 'passed'):
            for name in receipt.get('evidence', {}):
                try:
                    raw = gate.regular_bytes(state_root / module.relative(state_root, name))
                    if gate.sha(raw) != receipt['evidence'][name]:
                        continue
                    evidence = gate.parse_json(raw)
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
    policy = sibling(root / 'harness/policy_assets.py')
    owner, _, manifest, _ = policy.discover_policy(policy.__file__, conditions=('resumption_active',))
    packet = policy.instruction_context(owner, manifest=manifest, status={'status': 'blocked'}, restore=True,
                                        instruction_event='task-resume')
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


def _trusted_python(name):
    found = shutil.which(name)
    return bool(found and Path(found).resolve() == Path(sys.executable).resolve()
                or name in {'python', 'python3'} and _trusted_system_program(name))


def _simple_command(command):
    """Recognize one literal invocation without interpreting quoted JSON as shell code."""
    quote, escaped = None, False
    for char in command:
        if char == '\x00':
            return False
        if escaped:
            escaped = False
            continue
        if quote == "'":
            if char == "'":
                quote = None
            continue
        if char == '\\':
            escaped = True
        elif char == '"':
            quote = None if quote == '"' else '"'
        elif char == "'" and quote is None:
            quote = "'"
        elif char in '$`' or quote is None and char in ';&|<>\n\r#':
            return False
    return quote is None and not escaped


def _observed_read_paths(event, task_root):
    """Return only literal paths named by a completed, successful read call."""
    raw_tool = event.get('tool_name')
    tool = str(raw_tool).rsplit('__', 1)[-1].split('.')[-1].lower()
    args, response = event.get('tool_input'), event.get('tool_response')
    if not isinstance(args, dict) or _tool_failed(event):
        return []
    if tool in {'read', 'read_file', 'read_text_file'}:
        if not (isinstance(response, str) or isinstance(response, dict) and
                (response.get('success') is True or response.get('isError') is False or
                 isinstance(response.get('content'), str) or isinstance(response.get('output'), str))):
            return []
        names = [args.get('file_path') if tool == 'read' else args.get('path')]
    elif tool in {'bash', 'exec_command', 'run_command'}:
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


def _instruction_closure(root, observations, retained=()):
    sources = {}
    available = {row['path']: row for row in retained}
    for observation in observations:
        lexical = Path(observation['path'])
        try:
            actual = lexical.resolve()
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
                    name = str(candidate)
                    if name not in available:
                        available[name] = None
                        resolved = candidate.resolve(strict=True)
                        if resolved.is_relative_to(root) and resolved.is_file():
                            body = gate.regular_bytes(resolved)
                            available[name] = {'path': name, 'resolved_path': str(resolved),
                                               'directory': str(scope), 'sha256': gate.sha(body),
                                               'body': body.decode('utf-8'), 'observed': []}
                    source = available[name]
                    if source is not None:
                        key = (source['path'], source['sha256'])
                        if key not in sources:
                            sources[key] = {**source, 'observed': list(source['observed'])}
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


def _scoped_instructions(event, directory, context, *, restore=False, refresh=False, available=None,
                         changed_paths=(), write_targets=(), read_paths=None):
    """Retain and restore the applicable AGENTS closure for observed read paths."""
    root = Path(context['cwd']).resolve(strict=True)
    record_path = directory / 'scoped-instructions.json'
    previous = _read(record_path, {'root': str(root), 'observations': [], 'instructions': []})
    gate.require(previous.get('root') == str(root), 'scoped instruction root changed')
    observations = list(previous['observations'])
    additions = []
    observed = []
    if not restore:
        observed = _observed_read_paths(event, root) if read_paths is None else list(read_paths)
    observed.extend((Path(target), Path(target).resolve()) for target in write_targets
                    if Path(target).is_absolute() and Path(target).is_relative_to(root))
    if not restore:
        for lexical, actual in observed:
            item = {'path': str(lexical), 'resolved_path': str(actual), 'tool_name': event['tool_name'],
                    'tool_use_id': event.get('tool_use_id', 'PreToolUse')}
            if not any(row['path'] == item['path'] and row['resolved_path'] == item['resolved_path']
                       for row in observations):
                observations.append(item)
                additions.append(item)
            elif lexical.name == 'AGENTS.md':
                additions.append(item)
    changed_sources = [row for row in previous['instructions']
                       if row['path'] in changed_paths or row['resolved_path'] in changed_paths]
    for row in changed_sources:
        additions.extend(row['observed'])
    changed_scopes = [Path(path).parent for path in changed_paths
                      if Path(path).name == 'AGENTS.md' and Path(path).is_relative_to(root)]
    additions.extend(row for row in observations if any(
        Path(row[field]).is_relative_to(scope)
        for scope in changed_scopes for field in ('path', 'resolved_path')))
    if not observations and not additions:
        return ''
    if restore or refresh:
        instructions = _instruction_closure(root, observations)
    else:
        instructions_by_path = {row['path']: row for row in previous['instructions'] if row not in changed_sources}
        if additions:
            reread = {str(path) for pair in observed for path in pair if path.name == 'AGENTS.md'}
            retained = [row for row in instructions_by_path.values()
                        if row['path'] not in reread and row['resolved_path'] not in reread]
            instructions_by_path.update({row['path']: row for row in _instruction_closure(root, additions, retained)})
        instructions = sorted(instructions_by_path.values(), key=lambda row: (
            len(Path(row['directory']).relative_to(root).parts), row['directory']))
    current = {(row['path'], row['sha256']) for row in instructions}
    old = {(row['path'], row['sha256']) for row in previous['instructions']}
    changed = restore or current != old
    header = ('Applicable AGENTS.md instructions are ordered from ancestor to descendant; platform and user authority '
              'continue to govern. Within that authority, more specific instructions apply to their subtree. '
              'Re-evaluate affected work against changed instructions.\n')
    fresh = [row for row in instructions if restore or (row['path'], row['sha256']) not in old]
    rendered = ''.join('\n[Scoped instruction ' + row['path'] + ' sha256=' + row['sha256'] +
                       ' from ' + row['observed'][0]['tool_name'] + ' ' + row['observed'][0]['path'] + ']\n' + row['body']
                       for row in fresh)
    suffix = '\nThe applicable instruction closure changed; reconsider prior scoped judgments.' if current != old else ''
    if available is not None and len((header + rendered + suffix + '\n').encode('utf-8')) > available:
        rendered = ('\nRead the complete applicable AGENTS.md bodies before dependent work. '
                    'Their paths and full text are retained in ' + str(record_path))
    updated = {'root': str(root), 'turn_id': event.get('turn_id'), 'observations': observations,
               'instructions': instructions}
    if updated != previous:
        save_record(record_path, updated)
    if changed:
        return header + rendered + suffix
    return ''


def _context_budget(root, event):
    registration = gate.parse_json(gate.regular_bytes(root / 'hooks/hooks.json'))
    entries = registration['hooks'].get(event, [])
    handlers = [hook for entry in entries for hook in entry.get('hooks', [])
                if isinstance(hook.get('command'), str) and 'hooks/check.py' in hook['command']
                and hook['command'].rstrip().endswith(event)]
    limit = handlers[0].get('additionalContextLimit', 2500) if handlers else 2500
    gate.require(type(limit) is int and limit >= 0, 'invalid hook context limit')
    # A byte budget is conservative for token limits across languages.
    return limit


def _scoped_available(root, event, base_text, policy):
    budget = _context_budget(root, event)
    if budget == 0:
        return None
    priority = policy.primary_instruction('') + '\n'
    return max(0, budget - len((priority + base_text).encode('utf-8')))


def _tool_effect(event, root, directory, *, enforce_authority=True):
    """Classify the actual tool call; authority belongs to its preflight."""
    tool, arguments = event.get('tool_name'), event.get('tool_input')
    if isinstance(tool, str) and tool.rsplit('__', 1)[-1].split('.')[-1].lower() == 'apply_patch' and isinstance(arguments, str):
        arguments = {'command': arguments}
    elif tool == 'functions.exec' and isinstance(arguments, str):
        arguments = {'code': arguments}
    gate.require(isinstance(tool, str) and tool and isinstance(arguments, dict), 'missing actual tool name/input')
    name = tool.rsplit('__', 1)[-1].split('.')[-1].lower()
    cwd = event['cwd']
    effects = []
    command_action = None
    opaque_action = None
    input_bound = None
    state_args = None
    if name == 'write_stdin':
        gate.require(isinstance(arguments.get('session_id'), (str, int)), 'missing interactive session identity')
        if arguments.get('chars') and enforce_authority:
            input_bound = _bound_state(directory, root) or _completion_task(directory, root)
            gate.require(input_bound is not None, 'interactive input requires the original task completion contract')
            record = _read(directory / 'sessions' / (gate.sha(str(arguments['session_id']).encode()) + '.json'))
            gate.require(record is not None and not record.get('closed'),
                         'interactive session is unknown or already terminal')
            gate.require(_read(directory / 'reinjection.json', {}).get('instruction_policy_sha256', True) is not None,
                         'a governing source changed; rebind its adopted instructions before interactive input')
            gate.require(record.get('command'),
                         'interactive input requires its initiating operation and current task authority')
            module, data, task, state_root = input_bound
            native = sibling(root / 'harness/native_check.py')
            gate.require(task['status'] == 'running' and native.stdin_target(arguments) in task['external_targets']
                         and record['command'] in task['external_targets']
                         and any(row['operation'] == 'execute_command' and row['target_id'] == record['command']
                                 for row in task['required_actions'])
                         and not _pending_task_holds(directory, input_bound)
                         and not module.effective_constraints(data['tasks'], task)['holds'],
                         'interactive input lacks exact current session/input authority or has an unresolved hold')
        if arguments.get('chars'):
            record = _read(directory / 'sessions' / (gate.sha(str(arguments['session_id']).encode()) + '.json'), {})
            command_action = record.get('command')
        operation, targets, effect = ('write_stdin', [str(arguments['session_id'])], 'write') if arguments.get('chars') else (
                                     'poll', [str(arguments['session_id'])], 'read')
    else:
        targets = [arguments[key] for key in ('path', 'file_path', 'file', 'target', 'url', 'library_file_id', 'project_id')
                   if isinstance(arguments.get(key), str) and arguments[key]]
        if tool in {'skills__list', 'skills__read'} or not tool.startswith('mcp__') and name in {
                    'read', 'read_file', 'read_text_file', 'read_multiple_files', 'list_directory',
                    'directory_tree', 'search_files', 'get_file_info', 'view_image'}:
            operation, effect = 'read', 'read'
        elif (tool.startswith(('web__', 'mcp__')) and
              tool in ((native := sibling(root / 'harness/native_check.py')).WEB_READ_TOOLS |
                       native.LIBRARY_READ_TOOLS | native.CONNECTOR_READ_TOOLS)):
            operation, effect = 'read', 'read'
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
            if enforce_authority:
                gate.require(not arguments.get('env'), 'execution environment override is unresolved')
                shell = arguments.get('shell')
                gate.require(shell is None or isinstance(shell, str) and Path(shell).name in {'bash', 'sh', 'zsh'}
                             and _trusted_system_program(shell), 'execution shell override is unresolved')
            command_cwd = _tool_target(arguments.get('workdir', cwd), cwd)
            parts = shlex.split(command)
            gate.require(parts, 'empty execution command')
            if not _simple_command(command):
                operation, effect, command_action = 'execute_command', 'write', command
            elif ((_trusted_read_program(parts[0])
                   and not any(part.startswith(('--pre', '--hostname-bin')) for part in parts))
                  or (parts[0] == 'sed' and _trusted_system_program('sed') and len(parts) >= 4
                      and parts[1] == '-n' and re.fullmatch(r'[0-9]+(?:,[0-9]+)?p', parts[2])
                      and all(not part.startswith('-') for part in parts[3:]))):
                operation, effect = 'read', 'read'
                targets = [part for part in parts[1:] if not part.startswith('-')]
            elif (_trusted_python(parts[0]) and len(parts) >= 3
                  and _tool_target(parts[2] if parts[1] == '-B' and len(parts) > 3 else parts[1], command_cwd)
                  == str((root / 'harness/state.py').resolve())):
                tail = parts[3:] if parts[1] == '-B' else parts[2:]
                module = sibling(root / 'harness/state.py')
                if '--help' in tail or '-h' in tail:
                    operation, effect = 'read', 'read'
                else:
                    try:
                        parsed = module.parse_cli_args(tail, default_root=Path(command_cwd))
                    except SystemExit as exc:
                        raise ValueError('state command arguments are unresolved') from exc
                    effect, files, _ = module.cli_effect(parsed)
                    state_args = parsed
                    operation = 'read' if effect == 'read' else 'execute_command'
                    if effect == 'write':
                        task_root = absolute(_read(directory / 'context.json', {})['cwd'])
                        gate.require(_tool_target(str(parsed.root), command_cwd) == str(task_root),
                                     'state bookkeeping root differs from the original task root')
                        command_action = command
                        for name_ in files:
                            target = task_root / module.relative(task_root, name_, exists=False)
                            effects.append(('update' if target.exists() else 'create', str(target)))
            elif (_trusted_python(parts[0]) and len(parts) >= 3
                  and _tool_target(parts[2] if parts[1] == '-B' and len(parts) > 3 else parts[1], command_cwd)
                  == str((root / 'harness/codex_hooks.py').resolve())):
                tail = parts[3:] if parts[1] == '-B' else parts[2:]
                if '--help' in tail or '-h' in tail:
                    operation, effect = 'read', 'read'
                    parsed = None
                else:
                    try:
                        parsed = parse_control_args(tail)
                    except SystemExit as exc:
                        raise ValueError('hook control arguments are unresolved') from exc
                    operation, effect = ('read', 'read') if parsed.command == 'focus-research' else ('state-control', 'local-control')
                if enforce_authority and effect == 'local-control':
                    context = _read(directory / 'context.json', {})
                    gate.require(parsed.command in {'bind-operation', 'bind-child-assignment'}
                                 and not event.get('agent_id')
                                 and _tool_target(str(parsed.root), command_cwd) == str(absolute(context['cwd']).resolve())
                                 and _tool_target(str(parsed.hook_context), command_cwd) == str((directory / 'context.json').resolve()),
                                 'operation binding must target this task and its original root')
            else:
                operation, effect, command_action = 'execute_command', 'write', command
        elif tool.startswith('mcp__') and tool in native.CONNECTOR_WRITE_TOOLS:
            native = sibling(root / 'harness/native_check.py')
            operation, opaque_action = native._connector_call_target(tool, arguments)
            effect, targets = 'write', []
        elif name == 'apply_patch':
            effects = _patch_effects(arguments.get('command', arguments.get('patch', arguments.get('input'))))
            operation, effect = 'apply_patch', 'write'
            targets = [target for _, target in effects]
        elif name in {'write', 'edit', 'multiedit', 'write_file', 'edit_file', 'create_file', 'delete_file', 'update_file'}:
            operation, effect = name.split('_', 1)[0], 'write'
        elif name in {'list_agents', 'wait_agent', 'wait'} and not arguments.get('terminate'):
            operation, effect = name, 'read'
        elif name in {'spawn_agent', 'followup_task', 'interrupt_agent', 'close_agent', 'send_message'}:
            opaque_action = 'agent-call://' + gate.sha(gate.canonical({'tool_name': tool, 'tool_input': arguments}))
            operation, effect = name, 'write'
        else:
            operation, effect = name, 'unresolved'
    normalized = []
    for target in targets:
        normalized.append(_tool_target(target, cwd))
    if opaque_action is not None:
        normalized = [opaque_action]
    resolved_effects = [(verb, _tool_target(target, cwd)) for verb, target in effects]
    return tool, arguments, name, operation, effect, normalized, resolved_effects, command_action, opaque_action, input_bound, state_args


def _authorize_call(event, directory, module, task, effects, *, task_control=False):
    gate.require(isinstance(event.get('tool_use_id'), str) and event['tool_use_id'], 'modifying call needs its host tool identity')
    approval = {'task_id': _read(directory / 'context.json')['task_id'],
                'request_sha256': gate.sha(_effective_request(directory)),
                'tool_name': event['tool_name'], 'tool_use_id': event['tool_use_id'],
                'input_sha256': gate.sha(gate.canonical(event['tool_input'])),
                'resolved_effects': effects,
                'task_control': task_control,
                'contract_sha256': module.content_hash(module.contract_snapshot(task))}
    work = Path(_read(directory / 'context.json')['cwd'])
    files = {row['target'] for row in task['required_outputs'] if row['kind'] == 'file'}
    files.update(row['target_id'] for row in task['required_actions'] if row['target_kind'] == 'file')
    approval['output_versions_before'] = {name: gate.file_snapshot(work / name).sha256
                                         if (work / name).is_file() else None for name in sorted(files)}
    save_record(directory / 'preflight' / ('authorized-' + gate.sha(event['tool_use_id'].encode()) + '.json'), approval, replace=False)


def _state_control_preflight(args, root, directory, event):
    """Validate bounded reconciliation at its existing state owner, including holds."""
    if args is None or args.command not in {'init', 'add', 'prepare-context', 'set-context', 'set-contract', 'release-hold', 'start', 'resume', 'requeue'}:
        return None
    context = _read(directory / 'context.json')
    binding = context.get('state_binding')
    gate.require(not event.get('agent_id'), 'only the parent reconciles the bound task state')
    module = sibling(root / 'harness/state.py')
    work = absolute(context['cwd'])
    store = work / module.relative(work, args.store, exists=False)
    gate.require(store.is_relative_to(work / '.agents/state'), 'state control target exceeds the existing metadata area')
    if binding is None:
        if args.command not in {'init', 'add', 'prepare-context'}:
            return None
        bound = _completion_task(directory, root)
        gate.require(bound is not None and bound[2].get('authority') and bound[2]['operation_kind'] != 'answer'
                     and not _pending_task_holds(directory, bound)
                     and _read(directory / 'reinjection.json', {}).get('instruction_policy_sha256', True) is not None,
                     'state bootstrap requires the original complete task contract and authority without unresolved holds')
        task = bound[2]
        if args.command == 'add':
            gate.require(args.hook_context and _tool_target(args.hook_context, str(work)) == str(directory / 'context.json')
                         and args.authority.strip() and args.task_context, 'state creation must bind this actual host task and authority')
            outputs, actions = module.contract(work, args.required_output, args.required_action)
            gate.require(outputs == task['required_outputs'] and actions == task['required_actions']
                         and set(task['external_targets']) == set(args.external_target),
                         'state creation must preserve every original output/action and external target')
            scopes = [module.relative(work, value, exists=False) for value in args.scope]
            gate.require(all(module.in_scope(value, task['write_scope'] + ['.agents/state']) for value in scopes),
                         'state creation exceeds the original write scope')
            value, _ = module.load_task_context(work, args.task_context)
            request_sha = gate.sha(_effective_request(directory))
            gate.require(any(row.get('content_sha256') == request_sha and row.get('path')
                             and module.digest(work / module.relative(work, row['path'])) == request_sha
                             for row in value['request_refs']), 'state creation lost the actual complete request')
        elif args.command == 'prepare-context':
            gate.require(_tool_target(args.hook_context, str(work)) == str(directory / 'context.json')
                         and args.task_id is None and args.release_hold is None,
                         'initial context preparation must target this actual host task')
        return module, task
    if args.command in {'init', 'add'}:
        return None  # Additional records require their explicit normal command/file authority.
    task_id = getattr(args, 'id', getattr(args, 'task_id', None))
    gate.require(str(store) == binding['state_file'] and str(work) == binding['state_root']
                 and task_id == binding['task_id'], 'state reconciliation must target the bound task and store')
    if getattr(args, 'hook_context', None):
        gate.require(_tool_target(str(args.hook_context), str(work)) == str(directory / 'context.json'),
                     'state reconciliation hook context differs from this task')
    data = _read_state_store(store)
    task = data['tasks'][task_id]
    gate.require(task.get('authority') and task.get('completion_contract') == 1 and module.contract_current(work, task)
                 and not module.effective_constraints(data['tasks'], task)['scope_errors'],
                 'state reconciliation lacks original authority, requirements or scope')
    refs = (task.get('task_context') or {}).get('request_refs', [])
    sources = [gate.regular_bytes(work / module.relative(work, row['path'])) for row in refs
               if row.get('content_sha256') == binding['effective_request_sha256'] and row.get('path')]
    gate.require(sources and any(gate.sha(raw) == binding['effective_request_sha256'] and _effective_request(directory).startswith(raw)
                                for raw in sources), 'reconciliation lost the actual original request')
    messages = [(row['turn_id'], row['text']) for row in _read(directory / 'task-messages.json', [])
                if row.get('kind') != 'contract-acceptance']
    messages.append((context['turn_id'], _read(directory / 'original-prompt.json')['text']))
    for reference in (getattr(args, 'user_change', None), getattr(args, 'user_release', None)):
        if reference:
            message = gate.parse_json(gate.regular_bytes(work / module.relative(work, reference)))
            gate.require(message.get('source') == 'user' and (message.get('message_id'), message.get('text')) in messages,
                         'state authority must match an actual saved user message')
    proposed = gate.parse_json(gate.canonical(task))
    if args.command == 'set-context':
        value, _ = module.load_task_context(work, args.task_context)
        module.context_change(work, proposed, value, args.user_change, args.decision_update)
    elif args.command == 'set-contract':
        outputs, actions = module.contract(work, args.required_output, args.required_action)
        module.contract_change(work, proposed, outputs, actions, args.external_target, args.user_change, args.required_check)
        gate.require(not module.effective_constraints({**data['tasks'], task_id: proposed}, proposed)['scope_errors'],
                     'replacement contract exceeds ancestor authority')
    elif args.command == 'release-hold':
        gate.require(args.user_release, 'hold release needs its actual user instruction')
        module.hold_release_evidence(work, task, args.hold_id, args.user_release)
    elif args.command in {'start', 'resume', 'requeue'}:
        bound = _bound_state(directory, root)
        gate.require(not _pending_task_holds(directory, bound) and not module.effective_constraints(data['tasks'], task)['holds'],
                     'restarting task state cannot bypass an unresolved hold')
    return module, task


def _pre_tool(event, root, directory, state):
    """Check only the authority and targets of a modifying operation."""
    tool, arguments, name, operation, effect, normalized, resolved_effects, command_action, opaque_action, input_bound, state_args = (
        _tool_effect(event, root, directory))
    if effect in {'read', 'local-control'}:
        return {}
    control = _state_control_preflight(state_args, root, directory, event)
    if control is not None:
        gate.require(_tool_target(arguments.get('workdir', event['cwd']), event['cwd']) == _read(directory / 'context.json')['cwd'],
                     'state control working directory differs from the original task root')
        _authorize_call(event, directory, *control, resolved_effects, task_control=True)
        return {}
    gate.require(_read(directory / 'reinjection.json', {}).get('instruction_policy_sha256', True) is not None,
                 'a governing source changed; rebind its adopted instructions before dependent changes')
    cwd = event['cwd']
    rows, prohibitions = [], []
    bound = input_bound or _bound_state(directory, root)
    if bound is None:
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
        gate.require(task['status'] == 'running', 'task state is not running')
        rows = [{'kind': 'action', 'operation': row['operation'], 'target':
                 str(state_root / row['target_id']) if row['target_kind'] == 'file' else row['target_id'],
                 'target_kind': row['target_kind']} for row in task['required_actions']]
    holds = _pending_task_holds(directory, bound, check_sources=False)
    scoped = _scoped_instructions(event, directory, _read(directory / 'context.json'),
                                  write_targets=normalized if command_action is None and opaque_action is None else ())
    if bound is None:
        raise ValueError('bind the original task authority, complete outputs/actions and exact targets before a modifying or unresolved operation')
    if event.get('agent_id'):
        gate.require(_read(directory / 'context.json').get('state_binding') is not None,
                     'child changes require their scoped task in the existing state owner')
        children = [row for row in data['tasks'].values() if row.get('owner') == event['agent_id']
                    and any(parent['task_id'] == task['task_id'] for parent in state_module.task_ancestors(data['tasks'], row))]
        gate.require(len(children) == 1, 'resolve the exact host child identity to its existing bounded task')
        task = children[0]
        gate.require(task.get('authority') and task.get('completion_contract') == 1 and task['status'] == 'running'
                     and not state_module.context_changes(state_root, task), 'child authority or completion contract needs reconciliation')
        rows = [{'kind': 'action', 'operation': row['operation'], 'target':
                 str(state_root / row['target_id']) if row['target_kind'] == 'file' else row['target_id'],
                 'target_kind': row['target_kind']} for row in task['required_actions']]
        if task.get('specification'):
            specification, request = state_module._spec_inputs(state_root, task)
            prohibitions.extend(row for row in state_module._native().requirements.validate_contract(specification, request)
                                if row.get('evaluator', {}).get('type') == 'forbidden_operation')
    if name in {'bash', 'exec_command', 'run_command'}:
        gate.require(_tool_target(arguments.get('workdir', cwd), cwd) == str(state_root),
                     'modifying command working directory differs from the authorized task root')
    for row in prohibitions:
        forbidden = row['target'] if opaque_action is not None else _tool_target(row['target'], cwd)
        gate.require(not (forbidden in normalized and (row['evaluator']['operation'] in
                         {operation, tool, name} or effect == 'write')),
                     'forbidden operation ' + row['id'] + ' on ' + row['target'])
    constraints = state_module.effective_constraints(data['tasks'], task)
    gate.require(not constraints['scope_errors'], 'task scope exceeds its governing authority')
    if opaque_action is not None:
        gate.require(not holds, 'task hold requires reconciliation before an external operation')
        gate.require(opaque_action in task.get('external_targets', []) and
                     any(row['operation'] == operation and row.get('target_kind') == 'object'
                         and row['target'] == opaque_action for row in rows),
                     'external operation lacks its exact object authority')
        for hold in constraints['holds']:
            gate.require(not ((not hold['operations'] or operation in hold['operations']) and
                              (not hold['targets'] or 'object:' + opaque_action in hold['targets'])),
                         'task state hold covers this external operation')
    if command_action is not None:
        gate.require(not holds and not constraints['holds'],
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
    required = resolved_effects or ([] if command_action is not None or opaque_action is not None else [(operation, target) for target in normalized])
    for verb, target in required:
        allowed_operations = {verb} if resolved_effects else {verb, tool, name}
        gate.require(command_action is not None or any(row['kind'] == 'action' and row['operation'] in allowed_operations
                         and _tool_target(row['target'], cwd) == target for row in rows),
                     'modifying tool lacks current fixed operation/target authority')
        try:
            relative_target = Path(target).relative_to(state_root).as_posix()
        except ValueError as exc:
            raise ValueError('target exceeds task write scope') from exc
        relative = state_module.relative(state_root, relative_target, exists=False)
        gate.require(state_module.in_scope(relative, task.get('write_scope', [])),
                     'target exceeds task write scope')
        for hold in constraints['holds']:
            matches_operation = not hold['operations'] or verb in hold['operations']
            targets = hold['targets']
            matches_target = not targets or any(item == 'file:' + relative for item in targets)
            gate.require(not (matches_operation and matches_target), 'task state hold covers this operation')
    _authorize_call(event, directory, state_module, task, resolved_effects)
    return feedback('PreToolUse', scoped) if scoped else {}


def _post_tool(event, root, directory):
    """Keep the actual execution result needed by the existing completion contract."""
    context = _read(directory / 'context.json', {})
    tool, arguments, name, operation, effect, targets, resolved_effects, command_action, opaque_action, _, _ = (
        _tool_effect(event, root, directory, enforce_authority=False))
    if effect not in {'write', 'unresolved'} and name != 'write_stdin':
        return operation, []
    if effect != 'read':
        approval = _read(directory / 'preflight' / ('authorized-' + gate.sha(str(event.get('tool_use_id')).encode()) + '.json'))
        gate.require(isinstance(approval, dict) and approval['task_id'] == context.get('task_id')
                     and approval['tool_name'] == tool and approval['tool_use_id'] == event.get('tool_use_id')
                     and approval['input_sha256'] == gate.sha(gate.canonical(event['tool_input'])),
                     'operation result has no matching authorized preflight for this task and input')
        resolved_effects = approval['resolved_effects']
    if command_action is not None:
        targets = [command_action]
    affected = {target for _, target in resolved_effects} or set(targets)
    changed_paths = ({target for target in affected if Path(target).is_absolute()}
                     if command_action is None and opaque_action is None and name != 'write_stdin' else set())
    observed_sha = gate.sha(gate.canonical(event))
    path = directory / 'preflight' / (observed_sha + '.json')
    existing = _read(path)
    if existing is not None:
        _completion_callback(directory, root, event)
        return operation, existing.get('changed_paths', sorted(changed_paths))
    binding = {'tool_name': tool, 'operation': operation, 'targets': targets, 'effect': effect,
               'resolved_effects': resolved_effects, 'input_sha256': gate.sha(gate.canonical(arguments)),
               'session_id': arguments.get('session_id'), 'task_id': context.get('task_id'),
               'execution_owner_connected': False, 'callback_sha256': observed_sha,
               'callback': {field: event.get(field) for field in
                            ('tool_name', 'tool_use_id', 'tool_input', 'tool_response')}}
    if effect != 'read':
        binding['authorization'] = approval
    if context.get('completion_contract') and not context.get('state_binding'):
        binding['output_versions'] = {}
        binding['deleted_targets'] = []
        contract = context['completion_contract']
        state_root = Path(context['cwd'])
        producer = approval if effect != 'read' else {}
        if name == 'write_stdin':
            session = _read(directory / 'sessions' / (gate.sha(str(arguments['session_id']).encode()) + '.json'), {})
            origin = _read(directory / 'preflight' / ('authorized-' + gate.sha(str(session.get('tool_use_id')).encode()) + '.json'), {})
            producer = origin if not session.get('closed') and origin.get('task_id') == context.get('task_id') else {}
        before = producer.get('output_versions_before', {})
        binding['production_call_id'] = producer.get('tool_use_id')
        required = {row['target'] for row in contract['required_outputs'] if row['kind'] == 'file'}
        required.update(row['target_id'] for row in contract['required_actions'] if row['target_kind'] == 'file')
        failed = _tool_failed(event)
        for target in sorted(required):
            output = state_root / target
            if target in before and (command_action is not None or name == 'write_stdin' or str(output) in affected):
                version = gate.file_snapshot(output).sha256 if output.is_file() else None
                if version == before[target]:
                    continue
                changed_paths.add(str(output))
                binding['output_versions'][target] = version if not failed else None
                if before[target] is not None and version is None and not failed:
                    binding['deleted_targets'].append(target)
        binding['changed_paths'] = sorted(changed_paths)
        save_record(path, binding, replace=False)
        _completion_callback(directory, root, event)
    retained = _read(directory / 'reinjection.json', {})
    sources = retained.get('instruction_sources', {})
    for target in changed_paths & sources.keys():
        output = Path(target)
        if not output.is_file() or gate.file_snapshot(output).sha256 != sources[target]:
            save_record(directory / 'reinjection.json', {**retained, 'instruction_policy_sha256': None})
            break
    return operation, sorted(changed_paths)


def dispatch(event, expected_event):
    _INVOCATION_POLICY.clear()
    sibling.cache_clear()
    gate.require(isinstance(event, dict) and event.get('hook_event_name') == expected_event,
                 'hook event mismatch')
    for key in ('session_id', 'cwd'):
        gate.require(isinstance(event.get(key), str) and event[key].strip(), 'missing host ' + key)
    gate.require(expected_event in CONTEXT_EVENTS | {'PreToolUse', 'Stop', 'SubagentStop', 'Interrupt',
                 'PostCompact'}, 'unsupported hook event')
    if expected_event == 'PostCompact':
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
        if expected_event == 'PreToolUse':
            if _tool_effect(event, root, data, enforce_authority=False)[4] == 'read':
                return {}
            return failure(expected_event, 'restore the original task and bind its authority before changes')
        if expected_event in {'Stop', 'SubagentStop'}:
            return failure(expected_event, 'original task and completion requirements are unavailable')
        return {}
    if expected_event == 'PostCompact' and not (directory / 'context.json').exists():
        session = data / 'economics' / gate.sha(event['session_id'].encode())
        gate.require(not (session / 'active-task.json').exists(), 'active task context is missing')
        return {}
    session = data / 'economics' / gate.sha(event['session_id'].encode())
    active = _read(session / 'active-task.json', {})
    recovering = str(active.get('task_id', '')).startswith('recovery-required:')
    new_task = expected_event == 'UserPromptSubmit' and _new_task_requested(event.get('prompt', ''))
    if recovering and not new_task:
        if expected_event == 'PostCompact':
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
            if _tool_effect(event, root, directory, enforce_authority=False)[4] == 'read':
                return {}
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
            resume_action = _continuation_prompt(prompt, action_only=True)
            resuming_interruption = lifecycle == 'interrupted' and resume_action
            if (lifecycle == 'paused' and (resume_action or not _continuation_prompt(prompt))) or resuming_interruption:
                _finish(directory, 'active')
                if resuming_interruption:
                    (directory / 'interrupted.json').unlink()
                lifecycle = 'active'
            if lifecycle in TERMINAL:
                return feedback(expected_event, 'This task has completed or stopped. Do not resume automatically. Handle an independent new request as a separate task.')
            if old is not None:
                kind = ('contract-acceptance' if re.fullmatch(r'ERS accept-completion-contract [a-f0-9]{64}', prompt.strip()) else
                        'partial-stop' if stopping['kind'] == 'partial' else
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
                if kind == 'amendment':
                    save_record(directory / 'effective-request.json', {'text': effective.decode('utf-8'), 'sha256': gate.sha(effective)})
                    text += '\nRetained the original request and verbatim additions. Reconcile the governing requirements and current state with the changed request.'
                if kind == 'partial-stop':
                    text += '\nRecorded a hold for the specified target. Resolve the target IDs, do not execute held operations, and continue the explicitly identified parent task.'
                text += '\n' + _restoration(root, directory, state, manifest, restore=resuming_interruption,
                                            instruction_event='task-resume' if resuming_interruption else 'post-tool')
                if event['turn_id'] != old['turn_id']:
                    policy = sibling(root / 'harness/policy_assets.py')
                    available = _scoped_available(root, expected_event, text, policy)
                    scoped = _scoped_instructions(event, directory, old, refresh=True, available=available)
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
            text += '\n' + _restoration(root, directory, state, instruction_event='task-start')
            text += ('\nRead the selected operation and applicable bodies. Before changes or completion, bind all original '
                     'outputs/actions, exact targets and authority; an answer-only contract needs no durable task store. '
                     'Use codex_hooks.py --root ' + json.dumps(str(cwd)) +
                     ' bind-operation --hook-context ' + json.dumps(str(context_path)) +
                     ' --operation OPERATION --operation-kind KIND with the requested --required-output, --required-action '
                     'and --authority, applicable --condition and optional --profile. Use state.py only for durable continuation.')
            return feedback(expected_event, text)
        if lifecycle in {'interrupted', 'cancelled'}:
            return failure(expected_event, 'turn ' + lifecycle + '; no automatic restart', failure_class='cancelled')
        if lifecycle in TERMINAL and expected_event not in {'Stop', 'SubagentStop'}:
            if expected_event == 'PreToolUse' and _tool_effect(event, root, directory, enforce_authority=False)[4] != 'read':
                return failure(expected_event, 'the completed task grants no authority for further changes')
            return {}
        state, manifest = {'status': 'ordinary-active', 'needed_actions': []}, None
        context = _read(context_path, {})
        state['request_sha256'] = context.get('prompt_sha256')
        if expected_event == 'PostCompact':
            gate.require(context.get('session_id') == event['session_id'] and absolute(context['cwd']) == cwd,
                         'compaction task identity changed')
            record = _read(directory / 'reinjection.json', {})
            gate.require(isinstance(record, dict), 'invalid reinjection state')
            compactions = record.setdefault('compactions', {})
            gate.require(isinstance(compactions, dict), 'invalid compaction state')
            compactions[compaction_key] = {'event': expected_event, 'trigger': event['trigger'],
                                           'session_id': event['session_id'], 'turn_id': event['turn_id'],
                                           'agent_id': agent_id, 'agent_type': event.get('agent_type'),
                                           'pending_restoration': True}
            save_record(directory / 'reinjection.json', record)
            return {}
        record = _read(directory / 'reinjection.json', {})
        pending_compaction = (record.get('compactions') or {}).get(compaction_key) or {}
        if (agent_id is not None and pending_compaction.get('assignment_required') and
                expected_event in ('PreToolUse', 'Stop', 'SubagentStop')):
            if _child_assignment(root, directory, agent_id) is not None:
                pending_compaction['pending_restoration'] = True
            elif expected_event != 'PreToolUse' or not _child_recovery_tool(event, root, directory):
                return failure(expected_event, 'recover the exact child assignment from the parent or an authorized bound source before dependent work')
        if (expected_event in ('PreToolUse', 'Stop', 'SubagentStop') and
                pending_compaction.get('pending_restoration')):
            text = _coordinator(directory)
            conditions = ('resumption_active', 'delegation_active') if agent_id else ('resumption_active',)
            text += '\n' + _restoration(root, directory, state, manifest, conditions=conditions,
                                        instruction_event='compaction')
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
                policy = sibling(root / 'harness/policy_assets.py')
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
            latest = _read(directory / 'reinjection.json', {})
            latest['compactions'] = record['compactions']
            save_record(directory / 'reinjection.json', latest)
            return result
        if expected_event == 'PreToolUse':
            if lifecycle == 'paused':
                return failure('PreToolUse', 'the task is waiting for the next actual user input')
            return _pre_tool(event, root, directory, state)
        if expected_event in ('SubagentStart', 'SubagentStop'):
            return _child(event, root, directory, state, manifest)
        if expected_event in ('PostToolUse', 'SessionStart'):
            if expected_event == 'PostToolUse':
                pending = []
                gate.require(isinstance(event.get('tool_name'), str) and event['tool_name']
                             and isinstance(event.get('tool_use_id'), str) and event['tool_use_id'], 'missing host tool identity')
                response = event.get('tool_response')
                operation, changed_paths = _post_tool(event, root, directory)
                _capture_child_launch(directory, event)
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
                text = ''
                current_context = _read(context_path, {})
                retained = _read(directory / 'reinjection.json', {})
                if _tool_failed(event):
                    text = _restoration(root, directory, state, manifest, restore=False,
                                        instruction_event='check-failure')
                    text += '\nThe failed operation remains incomplete. Repair its actual cause and affected dependents before claiming completion.'
                elif (operation == 'state-control'
                        and (retained.get('instruction_binding_sha256') != gate.sha(gate.canonical(current_context.get('operation_binding')))
                             or retained.get('instruction_stage') != current_context.get('reading_stage')
                             or retained.get('instruction_policy_sha256') is None)):
                    text = _restoration(root, directory, state, manifest, restore=False)
                elif retained.get('instruction_policy_sha256', True) is None:
                    text = 'A governing source changed. Rebind its adopted instructions before dependent changes or completion.'
                if pending:
                    text += ('\nReturned child scopes awaiting parent integration: '
                            + json.dumps(pending, ensure_ascii=False)
                            + '\nCompare each actual return with its assignment and integrate the result.')
                    save_record(directory / 'pending-parent-returns.json', {'returns': []})
                _retain_exposed_rule_bodies(directory, event)
                scoped = ''
                affected_instructions = any(Path(path).name == 'AGENTS.md' for path in changed_paths)
                read_paths = _observed_read_paths(event, Path(context['cwd']))
                if affected_instructions or read_paths:
                    policy = sibling(root / 'harness/policy_assets.py')
                    scoped = _scoped_instructions(event, directory, context, changed_paths=changed_paths,
                        available=_scoped_available(root, expected_event, text, policy), read_paths=read_paths)
                return feedback(expected_event, (scoped + '\n' if scoped else '') + text) if scoped or text else {}
            # PostToolUse has returned; SessionStart restores the governing text.
            conditions = ('resumption_active',) if event.get('source') != 'startup' else ()
            policy, _, _, _, _ = _policy_snapshot(root, directory, conditions=conditions)
            text = _coordinator(directory)
            text += '\n' + _restoration(root, directory, state, manifest, conditions=conditions,
                                        instruction_event='compaction' if event.get('source') == 'compact' else 'task-resume')
            if lifecycle == 'paused':
                text += '\nThe task is paused for the next actual user input. Preserve its holds; do not start dependent operations automatically.'
            available = _scoped_available(root, expected_event, text, policy)
            scoped = _scoped_instructions(event, directory, context, restore=True, available=available)
            result = feedback(expected_event, (scoped + '\n' if scoped else '') + text)
            if event.get('source') == 'compact':
                record = _read(directory / 'reinjection.json', {})
                compactions = record.get('compactions') or {}
                if isinstance(compactions.get(compaction_key), dict):
                    compactions[compaction_key]['pending_restoration'] = False
                    save_record(directory / 'reinjection.json', record)
            return result
        gate.require(type(event.get('stop_hook_active')) is bool, 'missing Stop re-entry state')
        try:
            outcome = _verify_ordinary_stop(event, root, directory)
            _finish(directory, outcome)
            if outcome == 'paused':
                return {'systemMessage': 'The phase is complete and the task is paused for user input. '
                        'The parent task remains incomplete.'}
            return {}
        except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError) as exc:
            try:
                restored = _restoration(root, directory, state, manifest, restore=False,
                                        instruction_event='check-failure')
            except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError) as restore_error:
                return failure('Stop', str(exc) + '; restore required instructions: ' + str(restore_error))
            return failure('Stop', str(exc) + '\n' + restored)


def main(expected_event):
    try:
        raw = sys.stdin.buffer.read(4 * gate.MAX_BYTES + 1)
        gate.require(len(raw) <= 4 * gate.MAX_BYTES, 'hook event exceeds input budget')
        event = gate.parse_json(raw)
        result = dispatch(event, expected_event)
        output = result.get('hookSpecificOutput', {})
        fields = [(output, 'additionalContext'), (output, 'permissionDecisionReason'),
                  (result, 'reason'), (result, 'systemMessage'), (result, 'stopReason')]
        for container, key in fields:
            text = container.get(key)
            if not text:
                continue
            root = absolute(os.environ.get('PLUGIN_ROOT'))
            limit = _context_budget(root, expected_event)
            # Keep the exact packet available instead of allowing host truncation.
            if limit and len(text.encode('utf-8')) > limit:
                data = absolute(os.environ.get('PLUGIN_DATA'))
                directory = _active_directory(event, data)
                if directory is None:
                    directory = data / 'economics' / gate.sha(event['session_id'].encode())
                digest = gate.sha(text.encode('utf-8'))
                packet = directory / 'instruction-context' / (digest + '.json')
                save_record(packet, {'text': text, 'content_sha256': digest}, replace=False)
                container[key] = (
                    'Read the complete saved instruction packet before dependent work: ' + str(packet) +
                    '. content_sha256=' + digest +
                    '. Its UTF-8 JSON text field contains the exact request, adopted rules and current context. '
                    'Read that field in bounded character pages through its end and reuse complete same-version reads. '
                    'This locator is not a reading receipt; a host-truncated preview cannot restore required instructions.')
    except Exception as exc:
        # Transport/configuration errors require repair before retry.
        result = failure(expected_event, str(exc) + '; repair the hook input/configuration and retry the check')
    print(json.dumps(result, ensure_ascii=False))
    return 0


def parse_control_args(argv=None):
    parser = argparse.ArgumentParser(description='Bind task instructions or read an existing research execution log')
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--store', default='.agents/state/team.json')
    sub = parser.add_subparsers(dest='command', required=True)
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
    operation.add_argument('--stage', help='Registered reading stage within the adopted operation closure')
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
    return parser.parse_args(argv)


def inspect_saved_state(argv=None):
    """Read an existing research log or bind the current operation and instructions."""
    args = parse_control_args(argv)
    root = absolute(str(args.root))
    if args.command == 'bind-operation':
        print(json.dumps(bind_operation(args.hook_context, root, args.operation,
                                        conditions=args.condition, profile=args.profile, required_outputs=args.required_output,
                                        required_actions=args.required_action, operation_kind=args.operation_kind,
                                        authority=args.authority, user_change=args.user_change,
                                        external_targets=args.external_target, stage=args.stage), ensure_ascii=False, indent=2))
        return 0
    if args.command == 'bind-child-assignment':
        print(json.dumps(bind_child_assignment(args.hook_context, root, args.agent_id,
                                               args.source_id, args.source_sha256), ensure_ascii=False, indent=2))
        return 0
    module = sibling(base / 'state.py')
    store = root / module.relative(root, args.store)
    gate.require(Path(args.store).parts[:2] == ('.agents', 'state'), 'state store is outside its existing area')
    data, source_sha256 = _read_state_store(store, with_digest=True)
    task = data['tasks'][args.task_id]
    result = focus_saved_research(module, task, view=args.view, offset=args.offset, limit=args.limit)
    result['state_file'] = str(store)
    result['state_sha256'] = source_sha256
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(inspect_saved_state())
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


