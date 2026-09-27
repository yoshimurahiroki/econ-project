#!/usr/bin/env python3
"""Detect rhetoric candidates in prose; the econ-assertive skill judges necessity."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
RULES = {'concession_en': '\\b(?:however|although|nevertheless|nonetheless|albeit)\\b', 'preface_en': '\\b(?:it (?:should|must) be noted|it is (?:important|worth) (?:noting|to note)|to be (?:clear|fair)|for the sake of (?:accuracy|completeness))\\b', 'retreat_en': '\\b(?:may|might|could)\\s+(?:possibly|potentially|perhaps|suggest)\\b|\\b(?:this does not imply|we do not claim|should be interpreted with caution|within this limited scope)\\b', 'concession_ja': 'ただし|但し|とはいえ|とは言え|あくまで|もっとも[、，,]|とはいっても', 'warning_ja': '念のため|厳密には|注意が必要|留意が必要|慎重に解釈|断定でき|言い切れない|とまでは言え|にすぎない', 'retreat_ja': '可能性(?:は|を)否定できない|必ずしも[^。！？\\n]{0,70}(?:とは限らない|わけではない)'}

def mask(match: re.Match[str]) -> str:
    return ''.join(('\n' if x == '\n' else ' ' for x in match.group()))

def prose_only(text: str, tex: bool=False, skip_quotes: bool=False) -> str:
    """Keep offsets while masking code and math; skip verified quotations on request."""
    result = []
    fence = ''
    for line in text.splitlines(keepends=True):
        marker = re.match('^\\s*(`{3,}|~{3,})', line)
        protected = bool(fence or marker or (skip_quotes and re.match('^\\s*>', line)))
        if marker:
            found = marker.group(1)
            if not fence:
                fence = found
            elif found[0] == fence[0] and len(found) >= len(fence):
                fence = ''
        result.append(''.join(('\n' if x == '\n' else ' ' for x in line)) if protected else line)
    value = ''.join(result)
    expressions = ['\\\\begin\\{(equation\\*?|align\\*?|gather\\*?|verbatim|lstlisting)\\}[\\s\\S]*?\\\\end\\{\\1\\}', '(?<!\\\\)\\$\\$[\\s\\S]*?(?<!\\\\)\\$\\$', '\\\\\\[[\\s\\S]*?\\\\\\]|\\\\\\([\\s\\S]*?\\\\\\)', '(?<!\\\\)\\$(?:\\\\.|[^$\\n])*?(?<!\\\\)\\$', '`+[^`\\n]*`+']
    if skip_quotes:
        expressions.extend(['"[^"\\n]+"|“[^”\\n]+”|「[^」\\n]+」|『[^』\\n]+』', '\\\\begin\\{(quote|quotation)\\}[\\s\\S]*?\\\\end\\{\\1\\}'])
    if tex:
        expressions.append('(?<!\\\\)%[^\\n]*')
    for expression in expressions:
        value = re.sub(expression, mask, value)
    return value

def scan(text: str, tex: bool=False, skip_quotes: bool=False) -> list[dict]:
    value = prose_only(text, tex, skip_quotes)
    result = []
    for name, pattern in RULES.items():
        for m in re.finditer(pattern, value, re.I):
            result.append({'rule': name, 'line': value.count('\n', 0, m.start()) + 1, 'column': m.start() - value.rfind('\n', 0, m.start()), 'phrase': text[m.start():m.end()]})
    return sorted(result, key=lambda x: (x['line'], x['column'], x['rule']))

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path)
    parser.add_argument('--skip-quotes', action='store_true', help='Skip quotations already verified against an original source')
    args = parser.parse_args(argv)
    rows = []
    for path in args.paths:
        if path.suffix.lower() not in {'.md', '.txt', '.qmd', '.tex'}:
            parser.error('Expected a prose source file')
        rows += [{'path': str(path), **row} for row in scan(path.read_text(encoding='utf-8'), path.suffix.lower() == '.tex', args.skip_quotes)]
    print(json.dumps({'findings': rows, 'semantic_review_required': True}, ensure_ascii=False, indent=2))
    return int(bool(rows))
if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f'Prose scan error: {exc}', file=sys.stderr)
        raise SystemExit(2)
