#!/usr/bin/env python3
"""Economics task hooks for Codex and Claude Code: a short pointer at session start and on each prompt, and one
writing review before a turn with substantial prose ends."""
import json
import sys

sys.dont_write_bytecode = True

POINTER = ('Economics research entry: follow AGENTS.md and the economist\'s procedure (runtime/ECONOMIST.md), '
           'including for questions on bonuses, evaluation, teams, hiring, pricing or other everyday decisions. '
           'Every answer carries: the actors and their incentives; a small model with the condition that determines '
           'the choice (knowledge.py search first); its prediction or comparative static; the recommended decision '
           'with its switching condition. Without data, solve the model over parameter ranges. Text follows '
           'runtime/WRITING.md: argument from English originals, Japanese expression from Japanese exemplars '
           '(skills/econ-writing/scripts/exemplars.py find/style), direct claims, numerical uncertainty only.')
REVIEW = ('Before finishing, reread the answer once against runtime/WRITING.md: section 3 (direct claims, numerical '
          'uncertainty only, no hedges, disclaimers, limitations, ornament or negation contrasts) and, for Japanese, '
          'section 2 (connectives, endings, vocabulary and rhythm from the Japanese exemplars). Check that the answer '
          'carries the economist\'s four elements: actors and incentives, a model with the condition that determines '
          'the choice, its prediction or comparative static, and the decision with its switching condition. Add any '
          'missing element and revise any failing sentence; otherwise finish without comment.')
MIN_REVIEW_CHARS = 200


def last_message(payload):
    """Codex passes the final message; Claude Code passes the transcript path."""
    message = payload.get('last_assistant_message')
    if isinstance(message, str):
        return message
    path = payload.get('transcript_path')
    try:
        lines = open(path, encoding='utf-8').read().splitlines()
    except Exception:
        return ''
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        body = entry.get('message') if isinstance(entry.get('message'), dict) else entry
        if body.get('role') == 'assistant' or entry.get('type') == 'assistant':
            content = body.get('content')
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return ''.join(part.get('text', '') for part in content if isinstance(part, dict))
        if entry.get('type') == 'user' and not entry.get('toolUseResult'):
            return ''
    return ''


def main(event):
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    if event in ('SessionStart', 'UserPromptSubmit'):
        return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': POINTER}}
    if event == 'Stop':
        if payload.get('stop_hook_active') or len(last_message(payload)) < MIN_REVIEW_CHARS:
            return {}
        return {'decision': 'block', 'reason': REVIEW}
    return {}


if __name__ == '__main__':
    print(json.dumps(main(sys.argv[1] if len(sys.argv) > 1 else 'Stop'), ensure_ascii=False))
