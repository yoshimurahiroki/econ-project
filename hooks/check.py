#!/usr/bin/env python3
"""Load the plugin's canonical hook handler and preserve its host response."""
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True

event = sys.argv[1] if len(sys.argv) == 2 else 'Stop'
try:
    root = Path(os.environ['PLUGIN_ROOT'])
    if not root.is_absolute() or Path(__file__).resolve() != root.resolve() / 'hooks/check.py':
        raise ValueError('invalid plugin root')
    spec = importlib.util.spec_from_file_location('economics_codex_hooks', root / 'harness/codex_hooks.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
except Exception as exc:
    reason = 'Economics hook unavailable: ' + str(exc)
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

sys.exit(module.main(event))
