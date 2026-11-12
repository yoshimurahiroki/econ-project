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
