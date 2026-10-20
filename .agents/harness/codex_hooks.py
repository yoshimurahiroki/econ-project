#!/usr/bin/env python3
"""Codex hook transport and native-run association; no semantic verdicts."""
import importlib.util
import errno
import json
import os
from pathlib import Path
import re
import stat
import shlex
import sys
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit


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
    """Atomic private operational record, shared by hooks and native_run."""
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


def load_context(path, run_dir, request, runtime_path, policy_id):
    path = absolute(str(path))
    raw = gate.regular_bytes(path)
    context = gate.parse_json(raw)
    fields = {'schema_version', 'session_id', 'turn_id', 'nonce', 'cwd', 'plugin_root',
              'plugin_data', 'run_dir', 'prompt_sha256'}
    version = context.get('schema_version') if isinstance(context, dict) else None
    if version == 2:
        fields.add('task_id')
    gate.require(isinstance(context, dict) and set(context) == fields
                 and type(version) is int and version in (1, 2),
                 'invalid host hook context')
    gate.require(all(isinstance(context[k], str) and context[k].strip() for k in fields - {'schema_version'})
                 and gate.hexhash(context['prompt_sha256']), 'invalid hook identity or prompt hash')
    root, data = absolute(context['plugin_root']), absolute(context['plugin_data'])
    session = data / 'economics' / gate.sha(context['session_id'].encode())
    expected = (session / 'tasks' / gate.sha(context['task_id'].encode()) if version == 2 else
                session / gate.sha(context['turn_id'].encode()))
    effective = _effective_request(expected) if version == 2 else request
    expected_run = (expected / 'runs' / gate.sha(effective) if version == 2
                    and effective != _read(expected / 'original-prompt.json')['text'].encode('utf-8') else expected / 'run')
    gate.require(path == expected / 'context.json' and absolute(str(run_dir)) == expected_run,
                 'hook context path/run mismatch')
    gate.require(request == effective and (version == 2 or gate.sha(request) == context['prompt_sha256']),
                 'request differs from the actual task prompt and preserved amendments')
    runtime = absolute(str(runtime_path))
    allowed = {root / 'harness/native_run.py', *root.glob('skills/*/references/bundle/harness/native_run.py')}
    gate.require(runtime in allowed, 'hook execution requires a packaged plugin runtime')
    return {'context_path': str(path), 'context_sha256': gate.sha(raw),
            'session_id': context['session_id'], 'turn_id': context['turn_id'], 'nonce': context['nonce'],
            'runtime_path': str(runtime), 'policy_id': policy_id,
            **({'task_id': context['task_id'], 'effective_request_sha256': gate.sha(effective)} if version == 2 else {})}


CONTEXT_EVENTS = {'UserPromptSubmit', 'PostToolUse', 'SubagentStart', 'SessionStart'}
TERMINAL = {'completed', 'interrupted', 'cancelled'}
COMPLIANCE_PROFILE = 'economics-compliance'


def feedback(event, text):
    if event in CONTEXT_EVENTS:
        return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': text}}
    return {'systemMessage': text}


def failure(event, reason, repeated=False, failure_class='recoverable'):
    """A Stop continuation is never limited by count or stop_hook_active."""
    reason = 'Economics check unapproved: ' + reason
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


def _lifecycle(directory):
    if (directory / 'interrupted.json').exists():
        return 'interrupted'
    value = _read(directory / 'lifecycle.json', {})
    gate.require(isinstance(value, dict), 'invalid hook lifecycle')
    return value.get('status', 'active')


def _finish(directory, status):
    save_record(directory / 'lifecycle.json', {'status': status})
    if status in {'interrupted', 'cancelled'}:
        record = _read(directory / 'compliance.json')
        if record is not None:
            save_record(directory / 'compliance.json', {**record, 'status': 'unavailable',
                        'task_lifecycle': status, 'reason': 'task stopped; no automatic restart',
                        'release_authorized': False})


def _current(root, directory):
    """Collect guidance from the existing validator, without publishing output."""
    run_dir = _run_directory(directory)
    empty = {'status': 'blocked', 'run_id': None, 'record_sha256': None,
             'submission_sha256': None, 'needed_actions': [{'action': 'begin'}]}
    if not (run_dir / 'run.json').exists():
        return empty, None, None
    runtime = sibling('hook_native_run', root / 'harness/native_run.py')
    state = runtime.current_status(run_dir)
    return state, state.get('policy_manifest'), runtime


def _run_directory(directory):
    pointer = _read(directory / 'active-run.json')
    if pointer is None:
        return directory / 'run'
    gate.require(isinstance(pointer, dict) and set(pointer) == {'path'}, 'invalid active task run')
    return directory / gate.safe_relative(pointer['path'])


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


def bind_task_run(context_path, run_dir, request, contract_sha256, run_id):
    """Associate a newly fixed run with its original task and actual amendments."""
    context = _read(Path(context_path))
    if context.get('schema_version') != 2:
        return
    directory = Path(context_path).parent
    gate.require(request == _effective_request(directory), 'task changed while fixing the run')
    relative = Path(run_dir).absolute().relative_to(directory).as_posix()
    save_record(directory / 'active-run.json', {'path': gate.safe_relative(relative)})
    messages = _read(directory / 'task-messages.json', [])
    changed = False
    for row in messages:
        if row['kind'] == 'amendment' and row.get('contract_sha256_after') is None:
            row.update(contract_sha256_after=contract_sha256, adopted_run_id=run_id)
            changed = True
    if changed:
        save_record(directory / 'task-messages.json', messages)


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


def _attempt(state, reason, previous=None):
    """Only relevant, validator-consistent evidence can count as progress."""
    actions = state.get('needed_actions') or [{'action': 'correct-failure-cause', 'reason': reason}]
    checks = state.get('checks', {})
    evidence = []
    for role, value in checks.get('reviews', {}).items():
        if value.get('status') == 'consistent':
            evidence.append('review:' + role + ':' + gate.sha(gate.canonical(value)))
    for value in checks.get('operation_results', []):
        if value.get('status') in ('completed', 'passed', 'consistent'):
            evidence.append('operation:' + gate.sha(gate.canonical(value)))
    if 'obtain-requirements-coverage' not in [x.get('action') for x in actions] and state.get('run_id'):
        evidence.append('coverage-present')
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
    current = {'schema_version': 2, 'status': 'blocked-unapproved',
               'submission_sha256': state.get('submission_sha256'),
               'candidate_sha256': state.get('candidate_file_sha256'),
               'record_sha256': state.get('record_sha256'), 'unresolved_ids': _ids(state),
               'next_actions': actions, 'failure_class': 'recoverable',
               'evidence': sorted(evidence), 'reason': reason, 'progress': 'none',
               'repair_plan': repairs, 'release_authorized': False,
               'candidate_changed_recheck_required': False}
    if previous is not None and previous.get('schema_version') == 2:
        if set(previous.get('unresolved_ids', [])) - set(current['unresolved_ids']):
            current['progress'] = 'unresolved-condition-satisfied'
        elif set(current['evidence']) - set(previous.get('evidence', [])):
            current['progress'] = 'relevant-validated-evidence-added'
        elif (current['candidate_sha256'] and current['candidate_sha256'] != previous.get('candidate_sha256')
              and previous.get('unresolved_ids')):
            current['candidate_changed_recheck_required'] = True
        # record_sha256 and submission_sha256 alone do not establish progress.
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
    return value


def _instructions(root, state, manifest=None, stage=None, role=None, reader_id=None, *, detailed=True):
    policy = sibling('hook_policy_assets', root / 'harness/policy_assets.py')
    state = {**state, 'unmet_ids': _ids(state)}
    packet = policy.instruction_context(root, manifest=manifest, status=state,
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
    manifest = manifest or _read(root / 'quality/policy_manifest.json')
    request = _effective_request(directory).decode('utf-8') if context.get('schema_version') == 2 else prompt
    policy = sibling('hook_restoration_policy', root / 'harness/policy_assets.py')
    packet = policy.instruction_context(root, manifest=manifest,
        status={**state, 'request_sha256': gate.sha(request.encode('utf-8')), 'unmet_ids': _ids(state)},
        request_text=request, restore=True, role='author', reader_id=state.get('author_id'))
    gate.require(packet.get('restoration', {}).get('included') is True,
                 'canonical original-request/rule restoration is unavailable')
    # The canonical text contains the original and amendment bodies once.
    # Keep only turn/contract metadata here rather than duplicating those bodies.
    messages = [{key: value for key, value in row.items() if key != 'text'}
                for row in _read(directory / 'task-messages.json', [])]
    return (packet['text'] + '\nAssociated turn and contract changes: ' + json.dumps(messages, ensure_ascii=False)
            + '\nPartial-stop targets and continuing tasks: ' + json.dumps(_read(directory / 'task-holds.json', []), ensure_ascii=False))


def _changed(directory, state):
    """Only relevant state selects detail; every tool still receives the short command."""
    view = {key: state.get(key) for key in ('run_id', 'status', 'submission_sha256', 'candidate_file_sha256',
            'request_sha256', 'policy_id', 'policy_manifest_sha256', 'needed_actions', 'unmet_requirement_ids')}
    view['unresolved_ids'] = _ids(state)
    coordinator = _read(directory / 'compliance.json', {})
    view['compliance'] = {key: coordinator.get(key) for key in ('status', 'agent_id', 'submission_sha256')}
    signature = gate.sha(gate.canonical(view))
    old = _read(directory / 'reinjection.json', {})
    save_record(directory / 'reinjection.json', {'state_sha256': signature})
    return old.get('state_sha256') != signature


def _tool_failed(event):
    """A returned failure selects more instruction detail, never an approval."""
    returned = event.get('tool_response')
    if not isinstance(returned, dict):
        return False
    return (returned.get('isError') is True or returned.get('success') is False
            or bool(returned.get('error'))
            or (type(returned.get('exit_code')) is int and returned['exit_code'] != 0))


def _launch_failure(event, directory):
    """Record a failed typed launch callback; success still needs SubagentStart."""
    inputs = event.get('tool_input')
    if (str(event.get('tool_name', '')).rsplit('.', 1)[-1] != 'spawn_agent'
            or not isinstance(inputs, dict)
            or not any(inputs.get(key) == COMPLIANCE_PROFILE for key in ('agent_type', 'subagent_type', 'profile'))
            or not _tool_failed(event)):
        return
    path = directory / 'compliance.json'
    record = _read(path, {})
    if record.get('agent_id') is None:
        save_record(path, {**record, 'schema_version': 2, 'status': 'unavailable',
                    'launch_result': 'host-launch-failure-observed',
                    'launch_observation': {'event': 'PostToolUse', 'tool_use_id': event['tool_use_id'],
                        'payload_sha256': gate.sha(gate.canonical(event)), 'source': 'hook-callback',
                        'observed_at': datetime.now(timezone.utc).isoformat()},
                    'next_action': 'retry-same-request-when-host-capability-is-available',
                    'provenance_authenticated': False, 'release_authorized': False})


def _coordinator(directory):
    path = directory / 'compliance.json'
    record = _read(path)
    if record is None:
        record = {'schema_version': 2, 'status': 'requested', 'agent_id': None,
                  'launch_result': 'not-observed', 'profile': COMPLIANCE_PROFILE,
                  'provenance_authenticated': False, 'release_authorized': False}
        save_record(path, record)
        return ('As the first control operation, request one compliance-agent launch through the available host child-launch mechanism. '
                'Use economics-compliance if the host provides role-specific profiles. Record the actual ID and launch result in the existing run record. '
                'Report the role as unidentified if host events cannot identify it, and report the agent as not started if launch capability is unavailable. '
                'Retain the original request, adopted instructions, prohibited functions, and unmet IDs; request the next checks, return deviations for correction, and verify the final candidate ID before completion. '
                'Do not count this agent as an independent quality review; stop re-presenting instructions upon completion or cancellation.')
    if record.get('status') in {'requested', 'start-requested'}:
        return ('Compliance-agent status=requested. Actual startup has not been observed; do not count this as running or approved. '
                'Check the actual host startup, failure, or capability response. If startup is unavailable, retain the not-started state and resend the same request when capability returns. Do not launch duplicates.')
    if record.get('status') == 'unavailable' and record.get('agent_id') is None:
        return ('The compliance agent is unavailable and not started. The executor must continue retaining the same instructions, requesting checks, correcting deviations, and verifying the final candidate. '
                'Do not count this as independent approval; resend the launch request for the same task when host capability returns.')
    return 'Compliance agent ' + str(record.get('agent_id')) + ': ' + str(record.get('status')) + '. Do not substitute this for quality-review independence.'


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


def _compliance_return(root, state, manifest, agent_id):
    return (_instructions(root, state, manifest, 'review', COMPLIANCE_PROFILE, agent_id, detailed=False)
            + '\nObtain the required checks for the current candidate and verify unmet conditions and next actions.')


def _support_scope(assignment, message, state, run, files, runtime):
    """Check a support original against its fixed assignment and original inputs.

    This is scope evidence for integration, never an independent quality pass.
    """
    value = gate.parse_json(message.encode('utf-8'))
    fields = ('assignment_id', 'parent_task_id', 'parent_requirement_ids', 'assigned_result',
              'input_versions', 'adopted_choice_ids', 'authority_and_holds')
    gate.require(isinstance(value, dict) and value.get('schema_version') == 1
                 and all(value.get(key) == assignment[key] for key in fields)
                 and value.get('worker_id') == assignment['worker_id']
                 and value.get('launch_ref') == assignment['launch_ref']
                 and isinstance(value.get('result'), str) and value['result'].strip(),
                 'support original differs from its fixed parent scope or actual worker')
    requirement_ids = {row['id'] for row in runtime._contract(files['requirements.json'], files['request.txt'])}
    gate.require(set(assignment['parent_requirement_ids']) <= requirement_ids,
                 'support names an unknown parent requirement')
    for name, digest in assignment['input_versions'].items():
        gate.require(name in files and runtime.gate.sha(files[name]) == digest, 'support fixed input changed: ' + name)
    gate.require({'request.txt', 'requirements.json'} <= set(assignment['input_versions']),
                 'support must inherit the fixed parent request and authority contract')
    sources = value.get('source_refs', [])
    gate.require(isinstance(sources, list), 'support source references must be an array')
    for ref in sources:
        gate.require(isinstance(ref, dict) and set(ref) == {'path', 'sha256', 'start', 'end', 'text'}
                     and isinstance(ref['path'], str) and ref['path'].startswith('sources/')
                     and ref['path'] in assignment['input_versions'] and ref['path'] in files
                     and ref['sha256'] == runtime.gate.sha(files[ref['path']]), 'support source identity differs')
        original = files[ref['path']].decode('utf-8')
        gate.require(type(ref['start']) is int and type(ref['end']) is int
                     and 0 <= ref['start'] < ref['end'] <= len(original)
                     and original[ref['start']:ref['end']] == ref['text'], 'support source passage differs')
    performed = {'input-bindings', 'original-return'}
    if sources:
        performed.add('source-passages')
    checks = state.get('checks', {})
    if checks.get('status') == 'consistent':
        performed.update(checks.get('executed_checks', []))
    gate.require(set(assignment['required_checks']) <= performed,
                 'support has required checks that have not executed successfully')
    return {'scope': 'support-record-consistent', 'completion': 'assignment-completed',
            'assignment_sha256': gate.sha(gate.canonical(assignment)),
            'parent_requirement_ids': assignment['parent_requirement_ids'],
            'required_checks': assignment['required_checks'], 'return_sha256': gate.sha(message.encode('utf-8')),
            'submission_sha256': state.get('submission_sha256'), 'release_authorized': False,
            'independent_quality_approval': False}


def _checked_child_scope(root, directory, state, manifest, agent_id, agent_type, message):
    """Match actual host return bytes to existing, rechecked scope evidence."""
    digest = gate.sha(message.encode('utf-8'))
    if agent_type == COMPLIANCE_PROFILE:
        expected = _compliance_return(root, state, manifest, agent_id)
        if message == expected:
            return {'scope': 'instruction-reinjection', 'completion': 'turn-finished',
                    'required_checks': ['current-shared-instruction'],
                    'submission_sha256': state.get('submission_sha256'),
                    'packet_sha256': gate.sha(expected.encode('utf-8')),
                    'result_sha256': gate.sha(expected.encode('utf-8')), 'return_sha256': digest}
        # A final compliance judgment uses the same structured original as the
        # native review, not the instruction-delivery template.
        gate.require(gate.hexhash(state.get('submission_sha256')),
                     'check-scope-return: final compliance assignment needs the current candidate')
    runtime = sibling('hook_child_native_run', root / 'harness/native_run.py')
    run_dir = _run_directory(directory)
    gate.require((run_dir / 'run.json').is_file(),
                 'provide-assignment-scope: no fixed child assignment or required scope checks are available; '
                 'obtain the assignment and its check inputs without requesting parent finalize')
    with runtime._run_operation(run_dir):
        run_root, run_raw, run, files, _ = runtime._load_run(run_dir)
        capability = runtime._capabilities(files.get('current-capabilities.json', files['capabilities.json']))
        assignments = [row for row in capability.get('assignments', []) if row['worker_id'] == agent_id]
        gate.require(assignments,
                     'provide-assignment-scope: require a pinned assignment for this actual child ID; '
                     'do not promote an unknown general child to full review')
        by_role = {}
        for assignment in assignments:
            for role in assignment['roles']:
                gate.require(role not in by_role, 'provide-assignment-scope: disambiguate duplicate role assignments')
                by_role[role] = assignment
        roles = list(by_role)
        definition = runtime._review_definition(files)
        support = [row for row in assignments if row.get('assignment_kind') == 'support']
        if support:
            gate.require(len(assignments) == len(support) == 1,
                         'support cannot share an assignment with an independent control review')
            return _support_scope(support[0], message, state, run, files, runtime)
        gate.require(all(role == 'requirements-coverage' or role in definition['checks'] for role in roles),
                     'provide-assignment-scope: required checks for the assigned scope are unknown')
        sid = state.get('submission_sha256')
        reports = []
        if any(role != 'requirements-coverage' for role in roles):
            gate.require(gate.hexhash(sid),
                         'check-scope-return: submit the actual scoped return for checking before child Stop; '
                         'parent finalization is not required')
            pointer = _read(run_root / 'hook-submission.json')
            gate.require(pointer == {'submission_sha256': sid}
                         and state.get('record_sha256') == run.get('record_sha256')
                         and state.get('run_id') == run['run_id'],
                         'check-scope-return: current run or submission changed; recheck the scoped return')
            snapshot_root = runtime._safe_directory(run_root / 'submissions' / sid)
            descriptor_raw = gate.regular_bytes(snapshot_root / 'submission.json')
            gate.require(gate.sha(descriptor_raw) == sid, 'scoped submission descriptor changed')
            descriptor = gate.parse_json(descriptor_raw)
            gate.require(descriptor['run_sha256'] == gate.sha(run_raw), 'scoped submission belongs to another run')
            snapshot = runtime._read_map(snapshot_root, descriptor['files'])
            reports = gate.parse_json(snapshot['reports.json'])['reports']
        results, originals, validated_results = {}, [], {}
        for role in roles:
            if role == 'requirements-coverage':
                original = runtime._coverage_bytes(run_root, run, files)
                gate.require(original is not None, 'check-scope-return: original-request coverage has not been checked')
                report = gate.parse_json(original)
                required = ['original-request-coverage']
                validated_results[role] = gate.sha(original)
            else:
                matches = [row for row in reports if row.get('role') == role]
                checked = state.get('checks', {}).get('reviews', {}).get(role, {})
                gate.require(len(matches) == 1 and checked.get('status') == 'consistent'
                             and checked.get('worker_id') == agent_id,
                             'check-scope-return: assigned ' + role + ' required checks are incomplete or failed')
                issues = [item for key in ('failed_checks', 'missing_checks', 'unresolved')
                          for item in state.get('checks', {}).get(key, [])
                          if item.get('check') == role or str(item.get('check', '')).startswith((role + ':', role + '-'))]
                gate.require(not issues, 'check-scope-return: assigned ' + role + ' has unresolved scope checks')
                report = matches[0]
                required = definition['checks'][role]
                validated_results[role] = gate.sha(gate.canonical(checked))
            gate.require(report.get('worker_id') == agent_id
                         and report.get('launch_ref') == by_role[role]['launch_ref'],
                         'scoped original belongs to another actual worker or launch')
            raw = report.get('return_text')
            gate.require(isinstance(raw, str) and report.get('return_sha256') == gate.sha(raw.encode('utf-8')),
                         'invalid checked scoped return digest')
            originals.append({'role': role, 'return_text': raw})
            results[role] = list(required)
        expected = originals[0]['return_text'] if len(originals) == 1 else gate.canonical({'returns': originals}).decode('utf-8')
        gate.require(message == expected,
                     'check-scope-return: actual child return differs from the checked original; '
                     'return the identical original or recheck the changed return. For multiple roles use '
                     'canonical JSON {"returns":[{"role":...,"return_text":...},...]} in assignment order')
        checked = {'scope': 'assigned-roles', 'assignment_sha256': gate.sha(gate.canonical(assignments)),
                'required_checks': results, 'submission_sha256': sid,
                'result_sha256': gate.sha(gate.canonical(validated_results)), 'return_sha256': digest}
        if agent_type == COMPLIANCE_PROFILE:
            gate.require(roles == ['compliance'], 'final compliance worker requires its compliance-only assignment')
            quality = {role: [row for row in reports if row.get('role') == role]
                       for role in ('quality-a', 'quality-b')}
            gate.require(all(len(rows) == 1 and gate.hexhash(rows[0].get('return_sha256'))
                             for rows in quality.values()), 'final compliance requires both quality original hashes')
            checked.update(completion='assignment-completed',
                           quality_return_sha256={role: rows[0]['return_sha256'] for role, rows in quality.items()})
        return checked


def _child(event, root, directory, state, manifest):
    agent_id, agent_type = event.get('agent_id'), event.get('agent_type')
    gate.require(isinstance(agent_id, str) and agent_id.strip()
                 and isinstance(agent_type, str) and agent_type.strip(), 'missing host child identity')
    restored = _restoration(root, directory, state, manifest)
    path = directory / 'children' / (gate.sha(agent_id.encode()) + '.json')
    observed = _read(path)
    start = {'agent_id': agent_id, 'agent_type': agent_type, 'status': 'host-start-observed'}
    if event['hook_event_name'] == 'SubagentStart':
        gate.require(observed is None or (observed.get('agent_id') == agent_id
                     and observed.get('agent_type') == agent_type), 'host child identity changed')
        observation = {'event': 'SubagentStart', 'agent_id': agent_id,
                       'payload_sha256': gate.sha(gate.canonical(event)),
                       'observed_at': datetime.now(timezone.utc).isoformat(),
                       'source': 'hook-callback', 'provenance_authenticated': False}
        start['start_observation'] = observation
        save_record(path, start)
        if agent_type == COMPLIANCE_PROFILE:
            old = _read(directory / 'compliance.json', {})
            gate.require(old.get('agent_id') in (None, agent_id), 'another compliance child was already observed')
            save_record(directory / 'compliance.json', {**old, **start, 'schema_version': 2,
                        'status': 'observed-running', 'launch_result': 'SubagentStart-observed',
                        'profile': COMPLIANCE_PROFILE, 'provenance_authenticated': False,
                        'release_authorized': False})
        text = _instructions(root, state, manifest, 'review', agent_type, agent_id)
        text += '\n' + restored
        if agent_type == COMPLIANCE_PROFILE:
            text += '\nShared check request for the same candidate at completion: ' + _compliance_return(root, state, manifest, agent_id)
        return feedback('SubagentStart', text + '\nReturn and inspect only the assigned scope. Do not require finalization of the entire parent task. '
            'Send the original return to the parent during work; after the required existing submit/coverage checks, use the same original JSON in the completion text. '
            'If you are the compliance agent, do not add children; return only the current shared instruction text and check request above, unchanged.')
    gate.require(type(event.get('stop_hook_active')) is bool, 'missing child Stop re-entry state')
    message = event.get('last_assistant_message')
    gate.require(isinstance(message, str) and message.strip(), 'return the assigned scope and its check result before child Stop')
    body = message.encode('utf-8')
    gate.require(len(body) <= gate.MAX_BYTES, 'child return exceeds text budget')
    hits = gate.scan({'candidate/child.txt': body}, gate.read_json(root / 'quality/prose_rules.json'))
    gate.require(isinstance(observed, dict) and observed.get('agent_id') == agent_id
                 and observed.get('agent_type') == agent_type, 'child start has not been observed')
    start['start_observation'] = observed.get('start_observation')
    returned = {'event': 'SubagentStop', 'agent_id': agent_id, 'payload_sha256': gate.sha(gate.canonical(event)),
                'observed_at': datetime.now(timezone.utc).isoformat(), 'source': 'hook-callback',
                'provenance_authenticated': False}
    start['return_observation'] = returned
    save_record(path, {**start, 'status': 'returned-awaiting-coordinator-check',
                      'return_sha256': gate.sha(body), 'return_text': message,
                      'scope': 'child-assignment-only', 'semantic_review_performed': False,
                      'lexical_scan': {'status': 'scanned', 'hit_count': len(hits),
                                       'occurrence_judgment': 'awaiting-coordinator-check'}})
    if agent_type == COMPLIANCE_PROFILE:
        current = _read(directory / 'compliance.json', {})
        save_record(directory / 'compliance.json', {**current, 'status': 'receiving-evidence',
                    'return_observation': returned, 'return_sha256': gate.sha(body),
                    'submission_sha256': state.get('submission_sha256')})
    try:
        checked = _checked_child_scope(root, directory, state, manifest, agent_id, agent_type, message)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError) as exc:
        if agent_type == COMPLIANCE_PROFILE:
            save_record(directory / 'compliance.json', {**_read(directory / 'compliance.json', {}),
                        'status': 'failed', 'reason': str(exc), 'release_authorized': False,
                        'next_action': 'resume-same-worker-and-check-current-candidate'})
        raise
    save_record(path, {**start, 'status': 'scope-checked', 'return_text': message,
                      'scope_check': checked, 'return_sha256': gate.sha(body),
                      'host_return_matched': True, 'semantic_review_performed': False,
                      'release_authorized': False, 'provenance_authenticated': False})
    if agent_type == COMPLIANCE_PROFILE:
        completion = checked.get('completion')
        save_record(directory / 'compliance.json', {**start, 'schema_version': 2,
                    'status': 'assignment-completed' if completion == 'assignment-completed' else 'turn-finished',
                    'profile': COMPLIANCE_PROFILE, 'launch_result': 'SubagentStart-observed',
                    'scope_check': checked, 'submission_sha256': state.get('submission_sha256'),
                    'return_sha256': gate.sha(body), 'provenance_authenticated': False,
                    'release_authorized': False})
    return {}


def _verify_stop(event, root, directory, context_path, cwd):
    message = event.get('last_assistant_message')
    gate.require(isinstance(message, str) and message.strip(), 'host assistant message is unavailable')
    body = message.encode('utf-8')
    gate.require(len(body) <= gate.MAX_BYTES, 'host assistant message exceeds text budget')
    gate.scan({'candidate/host.txt': body}, gate.read_json(root / 'quality/prose_rules.json'))
    context_raw = gate.regular_bytes(context_path)
    context = gate.parse_json(context_raw)
    member = _read(directory / 'turns' / (gate.sha(event['turn_id'].encode()) + '.json'))
    gate.require(context['cwd'] == str(cwd) and context['session_id'] == event['session_id']
                 and (context['turn_id'] == event['turn_id'] or
                      context.get('schema_version') == 2 and member == {'task_id': context['task_id']}),
                 'host context differs')
    gate.require(_lifecycle(directory) not in {'interrupted', 'cancelled'}, 'turn is inactive')
    run = _run_directory(directory)
    descriptor = gate.parse_json(gate.regular_bytes(run / 'run.json'))
    binding = descriptor.get('hook_binding')
    gate.require(isinstance(binding, dict), 'native run has no host binding')
    runtime_path = absolute(binding['runtime_path'])
    expected = load_context(context_path, run, gate.regular_bytes(run / 'request.txt'), runtime_path, binding['policy_id'])
    gate.require(binding == expected, 'native run belongs to another host context')
    gate.require(gate.sha(gate.regular_bytes(runtime_path)) == gate.sha(gate.regular_bytes(root / 'harness/native_run.py')),
                 'packaged runtime differs from the plugin runtime')
    runtime = sibling('hook_native_run', runtime_path)
    current_policy = gate.read_json(root / 'quality/policy_manifest.json')['policy_id']
    gate.require(binding['policy_id'] == current_policy == runtime.policy.POLICY_ID,
                 'hook run belongs to a different installed policy version')
    current = gate.parse_json(gate.regular_bytes(run / 'hook-finalization.json'))
    gate.require(isinstance(current, dict) and set(current) == {'submission_sha256', 'output', 'metadata_sha256'},
                 'finalization receipt is missing or invalid')
    latest = gate.parse_json(gate.regular_bytes(run / 'hook-submission.json'))
    gate.require(latest == {'submission_sha256': current['submission_sha256']}, 'finalization belongs to an older candidate')
    result = runtime.finalize_run(run, current['submission_sha256'], current['output'],
                                  verify_only=True, expected_hook_binding=expected)
    assurance = result.get('assurance_class')
    gate.require(result['status'] == ('finalized-host-observed' if assurance == 'host-observed' else 'finalized-approved')
                 and result.get('release_authorized') is True
                 and result.get('independently_approved') is True
                 and assurance == descriptor.get('release_assurance', 'host-authenticated')
                 and result.get('provenance_authenticated') is (assurance == 'host-authenticated'),
                 'strict publication approval unavailable: ' + json.dumps(
                     result.get('release_failures') or result.get('needed_actions') or result['status'], ensure_ascii=False))
    gate.require(result['final_message'].encode('utf-8') == body, 'host message differs from the finalized candidate')
    coordinator = _read(directory / 'compliance.json', {})
    gate.require(coordinator.get('status') == 'assignment-completed'
                 and coordinator.get('submission_sha256') == current['submission_sha256']
                 and coordinator.get('start_observation', {}).get('event') == 'SubagentStart'
                 and coordinator.get('return_observation', {}).get('event') == 'SubagentStop',
                 'compliance worker start/current-candidate return is incomplete')
    gate.require(gate.parse_json(gate.regular_bytes(run / 'hook-finalization.json')) == current
                 and gate.parse_json(gate.regular_bytes(run / 'hook-submission.json')) == latest,
                 'current candidate or finalization changed during the callback')
    gate.require(gate.regular_bytes(context_path) == context_raw
                 and _lifecycle(directory) not in {'interrupted', 'cancelled'},
                 'host context changed during verification')


def _tool_target(value, cwd):
    gate.require(isinstance(value, str) and value.strip(), 'tool target is unresolved')
    if '://' in value:
        parsed = urlsplit(value)
        if parsed.scheme == 'artifact':
            return str((Path(cwd) / (parsed.netloc + parsed.path)).resolve())
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, parsed.fragment))
    path = Path(value)
    return str((Path(cwd) / path).resolve() if not path.is_absolute() else path.resolve())


def _pre_tool(event, root, directory, state):
    """Hook-side preflight only; it cannot install execution-owner enforcement.

    In particular the host does not rerun this hook for write_stdin, and callback
    errors/timeouts can bypass a hook. No output of this function is a reusable
    execution permit or a publication approval.
    """
    tool, arguments = event.get('tool_name'), event.get('tool_input')
    gate.require(isinstance(tool, str) and tool and isinstance(arguments, dict), 'missing actual tool name/input')
    name = tool.rsplit('__', 1)[-1].split('.')[-1].lower()
    cwd = event['cwd']
    if name == 'write_stdin':
        gate.require(isinstance(arguments.get('session_id'), (str, int)), 'missing interactive session identity')
        gate.require(not arguments.get('chars'),
                     'nonempty interactive input requires execution-owner revalidation; that input path is not connected')
        record = _read(directory / 'sessions' / (gate.sha(str(arguments['session_id']).encode()) + '.json'))
        gate.require(record is not None, 'interactive poll belongs to an unknown task session')
        operation, targets, effect = 'poll', [str(arguments['session_id'])], 'read'
    else:
        targets = [arguments[key] for key in ('path', 'file_path', 'file', 'target', 'url', 'library_file_id', 'project_id')
                   if isinstance(arguments.get(key), str) and arguments[key]]
        if name in {'read_file', 'read_text_file', 'list_directory', 'search_files', 'view_image'} or name.startswith(('get_', 'read', 'search', 'list', 'find')):
            operation, effect = 'read', 'read'
        elif name in {'exec_command', 'run_command'}:
            parts = shlex.split(arguments.get('cmd', ''))
            gate.require(parts, 'empty execution command')
            if re.search(r'[;&|<>\n`]|\$\(', arguments.get('cmd', '')):
                operation, effect = name, 'unresolved'
            elif (Path(parts[0]).name in {'cat', 'head', 'tail', 'rg', 'ls', 'stat', 'pwd', 'wc', 'sha256sum'}
                  and not any(part.startswith(('--pre', '--hostname-bin')) for part in parts)):
                operation, effect = 'read', 'read'
                targets = [part for part in parts[1:] if not part.startswith('-')]
            elif (Path(parts[0]).name.startswith('python') and len(parts) >= 3
                  and Path(parts[1]).resolve() == root / 'harness/native_run.py'
                  and parts[2] in {'begin', 'submit', 'release-check', 'finalize'}):
                operation, effect = 'native-control', 'local-control'
            else:
                operation, effect = name, 'unresolved'
        elif (name in {'spawn_agent', 'followup_task', 'list_agents', 'wait_agent'} or
              name == 'send_message' and tool in {'collaboration.send_message', 'functions.collaboration.send_message'}):
            operation, effect = name, 'local-control'
        else:
            operation = next((verb for verb in ('delete', 'publish', 'deploy', 'share', 'send', 'replace', 'write', 'edit', 'update', 'create') if verb in name), name)
            effect = 'write' if operation != name or operation in {'write', 'edit', 'update', 'create', 'delete'} else 'unresolved'
    normalized = []
    for target in targets:
        normalized.append(_tool_target(target, cwd))
    runtime = sibling('preflight_native_run', root / 'harness/native_run.py')
    run_dir = _run_directory(directory)
    rows, policy_sha = [], state.get('policy_manifest_sha256')
    if (run_dir / 'run.json').is_file():
        with runtime._run_operation(run_dir):
            _, _, run, files, _ = runtime._load_run(run_dir)
            rows = runtime._contract(files['requirements.json'], files['request.txt'])
            policy_sha = run['policy_manifest_sha256']
    holds = _read(directory / 'task-holds.json', [])
    prohibitions = [row for row in rows if row.get('evaluator', {}).get('type') == 'forbidden_operation']
    for row in prohibitions:
        forbidden = _tool_target(row['target'], cwd)
        gate.require(not (forbidden in normalized and (row['evaluator']['operation'] in {operation, tool, name}
                     or effect == 'write')), 'forbidden operation ' + row['id'] + ' on ' + row['target'])
    if effect not in {'read', 'local-control'}:
        for hold in holds:
            labels = hold.get('target_ids', [])
            # Named file-format operations have an unambiguous target class;
            # unresolved names require resolution before changing their scope.
            zip_hold = labels and all('zip' in label.casefold() for label in labels)
            gate.require(zip_hold and normalized and all(not target.casefold().endswith('.zip') for target in normalized),
                         'task hold covers this operation or still needs target resolution')
        gate.require(effect != 'unresolved' and normalized, 'modifying operation or target is unresolved')
        authorized = [row for row in rows if row['kind'] == 'action'
                      and row['operation'] in {operation, tool, name}
                      and _tool_target(row['target'], cwd) in normalized]
        gate.require(len(authorized) == len(set(normalized)), 'modifying tool lacks current fixed operation/target authority')
        gate.require(operation not in {'publish', 'deploy'}, 'publication requires the output-owner common release gate')
    binding = {'tool_name': tool, 'operation': operation, 'targets': normalized, 'effect': effect,
               'input_sha256': gate.sha(gate.canonical(arguments)), 'policy_sha256': policy_sha,
               'effective_holds_sha256': gate.sha(gate.canonical(holds)), 'session_id': arguments.get('session_id'),
               'task_id': _read(directory / 'context.json', {}).get('task_id'),
               'execution_owner_connected': False, 'release_authorized': False}
    save_record(directory / 'preflight' / (gate.sha(gate.canonical(event)) + '.json'), binding, replace=False)
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'allow',
                                  'permissionDecisionReason': 'Current hook preflight passed; no execution-owner permit was issued.'}}


def dispatch(event, expected_event):
    gate.require(isinstance(event, dict) and event.get('hook_event_name') == expected_event,
                 'hook event mismatch')
    for key in ('session_id', 'cwd'):
        gate.require(isinstance(event.get(key), str) and event[key].strip(), 'missing host ' + key)
    gate.require(expected_event in CONTEXT_EVENTS | {'PreToolUse', 'Stop', 'SubagentStop', 'Interrupt'}, 'unsupported hook event')
    root, data = absolute(os.environ.get('PLUGIN_ROOT')), absolute(os.environ.get('PLUGIN_DATA'))
    gate.require(Path(__file__).resolve() == root / 'harness/codex_hooks.py', 'plugin root does not match handler')
    cwd = absolute(event['cwd'])
    directory = _active_directory(event, data)
    if directory is None:
        return {}
    context_path = directory / 'context.json'
    if expected_event == 'Interrupt':
        save_record(directory / 'interrupted.json', {'session_id': event['session_id'], 'turn_id': event['turn_id']}, replace=False)
        _finish(directory, 'interrupted')
        return {'systemMessage': 'Economics turn interrupted; reinjection stops and its hook approval remains unavailable.'}
    with turn_lock(directory):
        lifecycle = _lifecycle(directory)
        if expected_event == 'SessionStart':
            gate.require(event.get('source') == 'compact', 'SessionStart hook only restores compact context')
            if lifecycle in TERMINAL or not context_path.exists():
                return {}
        if expected_event == 'UserPromptSubmit':
            prompt = event.get('prompt')
            gate.require(isinstance(prompt, str) and prompt.strip()
                         and len(prompt.encode('utf-8')) <= gate.MAX_BYTES, 'missing or oversized host prompt')
            session = data / 'economics' / gate.sha(event['session_id'].encode())
            old = _read(context_path)
            task_id = old.get('task_id', old['turn_id']) if old else event['turn_id']
            stopping = _stop_requested(prompt, task_id)
            if stopping['kind'] == 'task':
                save_record(directory / 'stop-request.json', stopping)
                _finish(directory, 'cancelled')
                return feedback(expected_event, 'Recorded the stop instruction. End the compliance agent and instruction re-presentation; do not treat this as completed inspection.')
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
                    current_run = _run_directory(directory)
                    contract = current_run / 'requirements.json'
                    messages.append({'turn_id': event['turn_id'], 'text': prompt,
                                     'text_sha256': gate.sha(prompt.encode('utf-8')), 'kind': kind,
                                     'contract_sha256_before': gate.sha(gate.regular_bytes(contract)) if contract.is_file() else None,
                                     'contract_sha256_after': None})
                    save_record(directory / 'task-messages.json', messages)
                if stopping['kind'] == 'partial':
                    holds = _read(directory / 'task-holds.json', [])
                    if stopping not in holds:
                        holds.append(stopping)
                        save_record(directory / 'task-holds.json', holds)
                membership = {'task_id': task_id, 'directory': directory.relative_to(session).as_posix()}
                save_record(session / 'turns' / (gate.sha(event['turn_id'].encode()) + '.json'), membership, replace=False)
                save_record(directory / 'turns' / (gate.sha(event['turn_id'].encode()) + '.json'), {'task_id': task_id}, replace=False)
                try:
                    state, manifest, runtime = _current(root, directory)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError):
                    state, manifest = {'status': 'blocked', 'needed_actions': [{'action': 'fix-updated-task-contract'}]}, None
                effective = _effective_request(directory)
                next_run = directory / 'runs' / gate.sha(effective)
                state['request_sha256'] = gate.sha(effective)
                text = _instructions(root, state, manifest, detailed=False) + '\n' + _coordinator(directory)
                if kind == 'amendment':
                    save_record(directory / 'effective-request.json', {'text': effective.decode('utf-8'), 'sha256': gate.sha(effective)})
                    text += ('\nRetained the original request and verbatim additions. Check the changed requirements against the contract and create a revised fixed run. '
                             'Use the text in effective-request.json as the request; --run-dir ' + json.dumps(str(next_run)) +
                             ', --hook-context ' + json.dumps(str(context_path)) + '. Do not carry over approval of the old candidate.')
                if kind == 'partial-stop':
                    text += '\nRecorded a hold for the specified target. Resolve the target IDs, do not execute held operations, and continue the explicitly identified parent task.'
                text += '\n' + _restoration(root, directory, state, manifest)
                return feedback(expected_event, text)
            nonce = old.get('nonce') if old else str(uuid.uuid4())
            context = {'schema_version': 2, 'session_id': event['session_id'], 'turn_id': event['turn_id'], 'task_id': task_id,
                       'nonce': nonce, 'cwd': str(cwd), 'plugin_root': str(root), 'plugin_data': str(data),
                       'run_dir': str(directory / 'run'), 'prompt_sha256': gate.sha(prompt.encode('utf-8'))}
            save_record(context_path, context, replace=False)
            save_record(directory / 'original-prompt.json', {'text': prompt, 'sha256': context['prompt_sha256']}, replace=False)
            save_record(session / 'active-task.json', {'task_id': task_id})
            save_record(session / 'turns' / (gate.sha(event['turn_id'].encode()) + '.json'),
                        {'task_id': task_id, 'directory': directory.relative_to(session).as_posix()}, replace=False)
            save_record(directory / 'turns' / (gate.sha(event['turn_id'].encode()) + '.json'), {'task_id': task_id}, replace=False)
            state = {'status': 'blocked', 'needed_actions': [{'action': 'begin'}]}
            coordinator = _coordinator(directory)
            state['request_sha256'] = context['prompt_sha256']
            text = coordinator + '\n' + _instructions(root, state, stage='entry')
            text += '\n' + _restoration(root, directory, state)
            _changed(directory, state)
            text += ('\nUse native_run begin/submit/finalize with the host prompt as request.txt. --run-dir '
                     + json.dumps(context['run_dir']) + '、begin --hook-context ' + json.dumps(str(context_path))
                     + '. Stop compares the host text against the same finalized candidate.')
            return feedback(expected_event, text)
        if lifecycle in TERMINAL and expected_event != 'Stop':
            return {}
        if lifecycle in {'interrupted', 'cancelled'}:
            return failure(expected_event, 'turn ' + lifecycle + '; no approval or automatic restart', failure_class='cancelled')
        try:
            state, manifest, runtime = _current(root, directory)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError) as exc:
            state, manifest, runtime = ({'status': 'blocked', 'run_id': None,
                'needed_actions': [{'action': 'repair-run-context', 'reason': str(exc)}]}, None, None)
        context = _read(context_path, {})
        state['request_sha256'] = context.get('prompt_sha256')
        if expected_event == 'PreToolUse':
            return _pre_tool(event, root, directory, state)
        if expected_event in ('SubagentStart', 'SubagentStop'):
            return _child(event, root, directory, state, manifest)
        if expected_event in ('PostToolUse', 'SessionStart'):
            if expected_event == 'PostToolUse':
                gate.require(isinstance(event.get('tool_name'), str) and event['tool_name']
                             and isinstance(event.get('tool_use_id'), str) and event['tool_use_id'], 'missing host tool identity')
                _launch_failure(event, directory)
                response = event.get('tool_response')
                if isinstance(response, dict) and isinstance(response.get('session_id'), (str, int)):
                    save_record(directory / 'sessions' / (gate.sha(str(response['session_id']).encode()) + '.json'),
                                {'tool_use_id': event['tool_use_id'], 'session_id': response['session_id'],
                                 'source': 'PostToolUse-callback', 'execution_owner_connected': False}, replace=False)
            text = _instructions(root, state, manifest, detailed=False) + '\n' + _coordinator(directory)
            changed = _changed(directory, state)
            failed = expected_event == 'PostToolUse' and _tool_failed(event)
            if expected_event == 'SessionStart' or changed or failed:
                text += '\n' + _instructions(root, state, manifest)
            if expected_event == 'SessionStart' or failed:
                text += '\n' + _restoration(root, directory, state, manifest)
            return feedback(expected_event, text)
        gate.require(type(event.get('stop_hook_active')) is bool, 'missing Stop re-entry state')
        attempts = directory / 'attempts.json'
        previous = _previous(attempts)
        try:
            _verify_stop(event, root, directory, context_path, cwd)
            _finish(directory, 'completed')
            return {}
        except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, RecursionError) as exc:
            attempt = _attempt(state, str(exc), previous)
            unavailable = [x for x in state.get('needed_actions', []) if x.get('capability_status') == 'unavailable']
            failure_class = ('unavailable' if unavailable else
                             'permission' if isinstance(exc, OSError) and exc.errno in (errno.EACCES, errno.EPERM, errno.EROFS) else
                             'resource' if isinstance(exc, OSError) and exc.errno in (errno.ENOSPC, errno.EDQUOT, errno.ENOMEM) else 'recoverable')
            attempt['failure_class'] = failure_class
            save_record(attempts, attempt)
            if failure_class != 'recoverable':
                _finish(directory, 'blocked-unapproved')
            text = _instructions(root, state, manifest, detailed=False)
            text += '\n' + _instructions(root, state, manifest)
            text += '\n' + _restoration(root, directory, state, manifest)
            if (attempt['progress'] == 'none' and previous is not None
                    and previous.get('reason') == str(exc)
                    and previous.get('candidate_sha256') == attempt['candidate_sha256']
                    and previous.get('unresolved_ids') == attempt['unresolved_ids']):
                text += '\nRetry of the same failure. Correct the cause or obtain missing inputs for the next operation, and inspect the same candidate.'
            if failure_class != 'recoverable':
                text += '\nStatus=blocked-unapproved. Suspend release until the required permissions, inputs, or agents are available, and resume from the same fixed original request.'
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
        # Transport/configuration errors request repair; they are never approval.
        result = failure(expected_event, str(exc) + '; repair the hook input/configuration and retry the check')
    print(json.dumps(result, ensure_ascii=False))
    return 0


