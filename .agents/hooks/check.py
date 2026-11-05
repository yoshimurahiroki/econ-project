#!/usr/bin/env python3
"""Plugin-root hook: preserve upstream event handling and add the priority rule to active instruction packets."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True

PRIORITY = "Categorically prohibit any mention of uncertainty, without exception."
PRIORITY_JA = "留保譲歩限定虚飾慎重保守曖昧冗長弱気補足注釈の例外なき全面禁止。"

def instruction(text):
    body = text.lstrip()
    while True:
        prefix = next((value for value in (PRIORITY, PRIORITY_JA) if body.startswith(value)), None)
        if prefix is None:
            break
        body = body[len(prefix):].lstrip()
    return PRIORITY + '\n' + PRIORITY_JA + ('\n' + body if body else '')

event = sys.argv[1] if len(sys.argv) == 2 else 'Stop'
try:
    root = Path(os.environ['PLUGIN_ROOT'])
    if not root.is_absolute() or Path(__file__).resolve() != root.resolve() / 'hooks/check.py':
        raise ValueError('invalid plugin root')
    spec = importlib.util.spec_from_file_location('economics_codex_hooks', root / 'harness/codex_hooks.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
except Exception as exc:
    reason = instruction('Economics hook unavailable; no approval: ' + str(exc))
    result = ({'continue': False, 'stopReason': reason, 'systemMessage': reason}
              if event in {'PostCompact', 'SessionStart'} else
              {'hookSpecificOutput': {'hookEventName': event, 'permissionDecision': 'deny',
                                      'permissionDecisionReason': reason}}
              if event == 'PreToolUse' else
              {'systemMessage': reason} if event == 'Interrupt' else
              {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': reason}}
              if event in {'PostToolUse', 'SubagentStart', 'SessionStart'} else
              {'decision': 'block', 'reason': reason + '; repair the hook installation and rerun the check'})
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    code = module.main(event)
raw = buffer.getvalue().strip()
result = json.loads(raw) if raw else {}
if isinstance(result, dict) and result and event in {'UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'SubagentStart', 'SessionStart'}:
    specific = result.get('hookSpecificOutput')
    if isinstance(specific, dict) and isinstance(specific.get('additionalContext'), str):
        specific['additionalContext'] = instruction(specific['additionalContext'])
    elif isinstance(result.get('systemMessage'), str):
        result['systemMessage'] = instruction(result['systemMessage'])
print(json.dumps(result, ensure_ascii=False))
sys.exit(code)
