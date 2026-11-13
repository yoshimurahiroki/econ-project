#!/usr/bin/env python3
"""Load the plugin's canonical hook handler and preserve its host response."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True

event = sys.argv[1] if len(sys.argv) == 2 else 'Stop'
READ_TOOLS = {'read', 'read_file', 'read_text_file', 'read_multiple_files', 'list_directory',
              'directory_tree', 'search_files', 'get_file_info', 'view_image', 'grep', 'glob'}


def awaiting(value):
    """True when a record holds a pending restoration or a required child assignment."""
    if isinstance(value, dict):
        return (value.get('pending_restoration') is True or value.get('assignment_required') is True
                or any(awaiting(item) for item in value.values()))
    return isinstance(value, list) and any(awaiting(item) for item in value)


def pure_read(raw):
    """A native file read changes no task state; its callbacks are skipped unless instructions await restoration."""
    try:
        payload = json.loads(raw)
        tool, session = payload['tool_name'], payload['session_id']
        if (not isinstance(tool, str) or tool.startswith('mcp__')
                or tool.rsplit('__', 1)[-1].split('.')[-1].lower() not in READ_TOOLS):
            return False
        response = payload.get('tool_response')
        if event == 'PostToolUse' and isinstance(response, dict) and (
                response.get('error') or response.get('isError') or response.get('success') is False):
            return False
        data = Path(os.environ.get('PLUGIN_DATA') or Path.home() / '.local' / 'state' / 'economics-research-skills')
        folder = data / 'economics' / hashlib.sha256(session.encode('utf-8')).hexdigest()
        return folder.is_dir() and not any(awaiting(json.loads(p.read_text(encoding='utf-8')))
                                           for p in folder.rglob('reinjection.json'))
    except Exception:
        return False


if event in {'PreToolUse', 'PostToolUse'}:
    raw_input = sys.stdin.buffer.read()
    if pure_read(raw_input):
        print('{}')
        sys.exit(0)
    import io
    sys.stdin = io.TextIOWrapper(io.BytesIO(raw_input), encoding='utf-8')
try:
    if 'PLUGIN_DATA' not in os.environ:
        os.environ['PLUGIN_DATA'] = str(Path.home() / '.local' / 'state' / 'economics-research-skills')
    root = Path(os.environ['PLUGIN_ROOT'])
    if not root.is_absolute() or Path(__file__).resolve() != root.resolve() / 'hooks/check.py':
        raise ValueError('invalid plugin root')
    spec = importlib.util.spec_from_file_location('economics_codex_hooks', root / 'harness/codex_hooks.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
except Exception as exc:
    reason = ('Economics hook unavailable: ' + str(exc)).encode('utf-8')[:240].decode('utf-8', errors='ignore')
    result = ({'decision': 'block', 'reason': reason + '; state startup requires a working hook. Resubmit after repair.'}
              if event == 'UserPromptSubmit' else
              {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': reason}}
              if event in {'PreToolUse', 'PostToolUse', 'SubagentStart', 'SessionStart'}
              else {'systemMessage': reason})
    try:
        if event == 'UserPromptSubmit':
            raise ValueError('startup failure must remain visible')
        payload = json.load(sys.stdin)
        session, turn = payload.get('session_id'), payload.get('turn_id')
        data = Path(os.environ['PLUGIN_DATA'])
        if data.is_absolute() and isinstance(session, str) and session and isinstance(turn, str) and turn:
            sha = lambda value: hashlib.sha256(value.encode('utf-8')).hexdigest()
            directory = data / 'economics' / sha(session) / 'hook-notices' / sha(turn)
            directory.mkdir(parents=True, mode=0o700, exist_ok=True)
            for slot in range(2):
                try:
                    fd = os.open(directory / (sha(reason) + '-' + str(slot)),
                                 os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                except FileExistsError:
                    continue
                os.close(fd)
                break
            else:
                result = {}
    except Exception:
        pass
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)

sys.exit(module.main(event))
