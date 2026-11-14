#!/usr/bin/env python3
"""Economics task hooks for Codex and Claude Code.

SessionStart / UserPromptSubmit: state the procedure and record the start of the turn.
PreToolUse: an edit inside the project and outside work/ waits until this turn's worksheet has its situation,
question and model.
Stop: the turn ends only when this turn's worksheet has all seven sections, knowledge unit IDs, a decision and its
switching condition, and the answer has been reread against WRITING once.
SubagentStop: a worker rereads its return against the procedure once.
"""
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

POINTER = ('Economics research entry: follow AGENTS.md. Every request, without exception (code, data, writing, '
           'formatting, everyday questions), runs the economist\'s procedure (runtime/ECONOMIST.md): set the deep, '
           'consequential problem first. Copy runtime/WORKSHEET.md to work/<topic>.md and fill it: sections 1-3 '
           '(situation, question, model with knowledge unit IDs, each decision tagged with its source) before '
           'editing any project file; all seven sections, the decision, its switching condition, the number of '
           'specification changes and the Status/Next action header before the turn ends; the hooks check this. '
           'Read runtime/context/ for the country and work/context.md for the project before deciding. '
           'Models are built from standard models and existing knowledge (knowledge.py search), fitted to the case '
           'and solved as a complexity ladder (skills/econ-design/references/modeling.md); empirical work follows '
           'skills/econ-data/references/empirical.md. Text follows runtime/WRITING.md.')
REVIEW = ('Before finishing, reread the answer once against runtime/WRITING.md: section 3 (direct claims, numerical '
          'uncertainty only, no hedges, disclaimers, limitations, ornament or negation contrasts, and no '
          'assumptions, conditions, threats, diagnostics or justifications of the design, and no definitions or '
          'explanations of standard concepts, methods, estimators or software) and, for Japanese, '
          'section 2 (connectives, endings, vocabulary and rhythm from the Japanese exemplars). Check that the answer '
          'contains the requested deliverable and nothing the worksheet holds for internal use (the procedure, '
          'assumptions, checks, objections). Delete anything else and revise any failing sentence; otherwise finish without '
          'comment.')
REFEREE = ('Before the writing check, review the answer once as a referee would, using '
           'skills/econ-review/references/review.md (R2 and the R3 checks that apply): is the question consequential '
           'and does it beat its upstream alternative; does the comparison identify the estimand; is the magnitude '
           'plausible against the baseline and prior estimates; what is the strongest alternative mechanism that fits '
           'the same result, and the main threat to identification. Write these objections and their answers (evidence, '
           'a check, or a switching condition) in the worksheet line "Objections and answers:", run any check that '
           'an objection requires, and change the claims or the decision where an objection holds. Objections and '
           'answers stay in the worksheet and add no sentences to the answer; otherwise finish without comment.')
WORKER_REVIEW = ('Before returning, check the return against runtime/ECONOMIST.md: it states the economic object it '
                 'serves, the model or method used with knowledge unit IDs, the actual commands run and saved files, '
                 'and the result the parent needs. Add what is missing; otherwise return without comment.')
SECTIONS = ['1. Situation and stakes', '2. Question', '3. Model', '4. Estimand and identification',
            '5. Execution', '6. Interpretation and decision', '7. Expression']
SOURCE_TAG = re.compile(r'\[(?:user|context|knowledge|literature|data|assumption)\b')
KNOWLEDGE_ID = re.compile(r'\b(?:MC-[A-Za-z0-9-]+|[A-Z]{2,}(?:-[A-Z]+)?-\d{2})\b')
EDIT_TOOLS = {'Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'apply_patch', 'edit', 'write'}
MAX_STOP_BLOCKS = 3
MIN_FILLED = 15


def state_path(session):
    base = Path(os.environ.get('PLUGIN_DATA') or os.environ.get('CLAUDE_PLUGIN_DATA')
                or Path.home() / '.local' / 'state' / 'econ-harness')
    return base / (hashlib.sha256(str(session).encode('utf-8')).hexdigest()[:32] + '.json')


def load_state(session):
    try:
        return json.loads(state_path(session).read_text(encoding='utf-8'))
    except Exception:
        return {'start': 0.0, 'blocks': 0, 'refereed': False, 'reviewed': False}


def save_state(session, state):
    try:
        path = state_path(session)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding='utf-8')
    except Exception:
        pass


def template_lines():
    try:
        text = (Path(__file__).resolve().parent.parent / 'runtime' / 'WORKSHEET.md').read_text(encoding='utf-8')
    except Exception:
        return set()
    return {line.strip() for line in text.splitlines() if line.strip()}


def sections(text):
    found, current = {}, None
    for line in text.splitlines():
        match = re.match(r'^##\s+(\d)\.', line)
        if match:
            index = int(match.group(1)) - 1
            current = SECTIONS[index] if 0 <= index < len(SECTIONS) else None
            if current:
                found[current] = []
            continue
        if line.startswith('#'):
            current = None
        elif current:
            found[current].append(line)
    return found


def filled(lines, template):
    """Characters written beyond the template text and empty labels."""
    total = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped in template:
            continue
        label = re.match(r'^[^:：]{1,60}[:：]\s*(.*)$', stripped)
        value = label.group(1) if label else stripped
        total += len(re.sub(r'\(IDs from knowledge\.py[^)]*\)', '', value).strip(' -–'))
    return total


def label_value(lines, label):
    for line in lines:
        match = re.match(r'^\s*' + re.escape(label) + r'\s*[:：]\s*(.*)$', line)
        if match:
            return match.group(1).strip()
    return ''


def worksheet_problems(cwd, start, upto):
    """Problems with the most recently written worksheet of this turn, checked through section `upto`."""
    work = Path(cwd) / 'work'
    candidates = sorted((p for p in work.glob('*.md') if p.stat().st_mtime >= start - 1),
                        key=lambda p: p.stat().st_mtime, reverse=True) if work.is_dir() else []
    if not candidates:
        return None, ['no worksheet in work/ was written in this turn: copy runtime/WORKSHEET.md to '
                      'work/<topic>.md (or update the existing one for this topic) and fill it']
    path = candidates[0]
    found, template, problems = sections(path.read_text(encoding='utf-8', errors='replace')), template_lines(), []
    for name in SECTIONS[:upto]:
        if name not in found:
            problems.append(f'section "## {name}" is missing')
        elif filled(found[name], template) < MIN_FILLED:
            problems.append(f'section "## {name}" is not filled')
    if '3. Model' in found and not KNOWLEDGE_ID.search('\n'.join(found['3. Model'])):
        problems.append('section 3 names no knowledge unit ID: run knowledge.py search and read the matching units')
    if upto >= 3:
        tagged = '\n'.join(sum((found.get(n, []) for n in SECTIONS[1:upto if upto < 4 else 4]), []))
        if not SOURCE_TAG.search(tagged):
            problems.append('decisions in sections 2-4 carry no source tag such as [user], [knowledge: ID], '
                            '[literature: ...], [data: ...] or [assumption]')
    if upto >= 6 and '6. Interpretation and decision' in found:
        for label in ('Decision', 'Switches when', 'Specification changes'):
            if not label_value(found['6. Interpretation and decision'], label) or \
                    label_value(found['6. Interpretation and decision'], label).startswith('(number after'):
                problems.append(f'section 6 has no "{label}:" entry')
    if upto >= 7:
        header = path.read_text(encoding='utf-8', errors='replace').split('\n## 1.')[0].splitlines()
        status = label_value(header, 'Status').lower()
        if status not in ('open', 'closed'):
            problems.append('the header has no "Status: open" or "Status: closed" line')
        elif status == 'open' and not label_value(header, 'Next action'):
            problems.append('the worksheet is open and its header has no "Next action:"')
    return path, problems


def open_worksheets(cwd):
    """Open worksheets and their next actions, read at session start so work resumes where it stopped."""
    work = Path(cwd) / 'work'
    out = []
    for path in sorted(work.glob('*.md'), key=lambda p: p.stat().st_mtime, reverse=True)[:5] if work.is_dir() else []:
        header = path.read_text(encoding='utf-8', errors='replace').split('\n## 1.')[0].splitlines()
        if label_value(header, 'Status').lower() == 'open':
            out.append(f'{path.name}: step {label_value(header, "Current step") or "?"}; next: '
                       f'{label_value(header, "Next action") or "(not set)"}')
    return out


def edit_targets(payload):
    tool_input = payload.get('tool_input') or {}
    paths = [tool_input.get(key) for key in ('file_path', 'path', 'notebook_path') if tool_input.get(key)]
    patch = tool_input.get('patch') or tool_input.get('input') or tool_input.get('command') or ''
    if isinstance(patch, str):
        paths += [p.strip() for p in re.findall(r'^\*\*\* (?:Add|Update|Delete) File:\s*(.+)$', patch, re.M)]
    return [p for p in paths if isinstance(p, str)]


def gated(path, cwd):
    """Edits inside the project and outside work/ are gated; scratch and temporary files are not."""
    root = Path(cwd).resolve()
    target = (Path(path) if Path(path).is_absolute() else root / path).resolve()
    return root in target.parents and (root / 'work') not in target.parents


def main(event):
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    session = payload.get('session_id') or 'default'
    cwd = payload.get('cwd') or os.getcwd()
    if event in ('SessionStart', 'UserPromptSubmit'):
        if event == 'UserPromptSubmit':
            save_state(session, {'start': time.time(), 'blocks': 0, 'refereed': False, 'reviewed': False})
        context = POINTER
        if event == 'SessionStart':
            pending = open_worksheets(cwd)
            if pending:
                context += ' Open worksheets (resume from their next action): ' + ' | '.join(pending)
        return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': context}}
    state = load_state(session)
    if event == 'PreToolUse':
        if str(payload.get('tool_name', '')).rsplit('__', 1)[-1] not in EDIT_TOOLS:
            return {}
        targets = [p for p in edit_targets(payload) if gated(p, cwd)]
        if not targets:
            return {}
        _, problems = worksheet_problems(cwd, state.get('start', 0.0), 3)
        if not problems:
            return {}
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                       'permissionDecisionReason': 'Fill sections 1-3 of this turn\'s worksheet '
                                       'before editing ' + ', '.join(targets[:3]) + ': ' + '; '.join(problems) + '.'}}
    if event == 'SubagentStop':
        return {} if payload.get('stop_hook_active') else {'decision': 'block', 'reason': WORKER_REVIEW}
    if event == 'Stop':
        path, problems = worksheet_problems(cwd, state.get('start', 0.0), 7)
        if problems and state.get('blocks', 0) < MAX_STOP_BLOCKS:
            state['blocks'] = state.get('blocks', 0) + 1
            save_state(session, state)
            where = f' ({path.name})' if path else ''
            return {'decision': 'block', 'reason': 'Complete the worksheet' + where + ' before finishing: '
                    + '; '.join(problems) + '. Then align the answer with it.'}
        if problems:
            return {'systemMessage': 'Economics worksheet incomplete after ' + str(MAX_STOP_BLOCKS)
                    + ' requests: ' + '; '.join(problems)}
        if not state.get('refereed'):
            state['refereed'] = True
            save_state(session, state)
            return {'decision': 'block', 'reason': REFEREE}
        if not state.get('reviewed'):
            state['reviewed'] = True
            save_state(session, state)
            return {'decision': 'block', 'reason': REVIEW}
        return {}
    return {}


if __name__ == '__main__':
    print(json.dumps(main(sys.argv[1] if len(sys.argv) > 1 else 'Stop'), ensure_ascii=False))
