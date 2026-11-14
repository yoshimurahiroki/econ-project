#!/usr/bin/env python3
"""Build a local exemplar library from the user's papers, notes and slides and retrieve passages to imitate.

The library lives outside the repository (``$ERS_EXEMPLARS`` or the user data directory). Commands:

  add PATH...                      extract PDF/TXT/MD/TEX files (folders are searched) into the library
  list                             show the registered documents
  remove DOC_ID...                 delete documents
  find   --lang ja|en [--function F] [--kind prose|slide] [--query WORDS] [--limit N] [--max-chars N]
  outline --lang en [--function F] [--query WORDS] [--doc DOC_ID]
                                   first sentence of every paragraph in one section: the argument moves
  style  --lang ja [--function F] [--kind prose|slide] [--query WORDS]
                                   connectives, sentence endings and sentence lengths of matching passages

Functions: introduction, background, data, model, method, results, mechanism, robustness, conclusion.
"""
import argparse
import hashlib
import os
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

FUNCTIONS = {
    'introduction': ('introduction', 'motivation', 'はじめに', '序論', '問題意識', '序'),
    'background': ('background', 'institutional', 'institution', 'setting', 'context', '制度', '背景', '概要'),
    'data': ('data', 'sample', 'measurement', 'descriptive', 'データ', '標本', '資料', '記述統計'),
    'model': ('model', 'theory', 'theoretical', 'framework', 'equilibrium', 'モデル', '理論', '枠組み', '均衡'),
    'method': ('empirical strategy', 'identification', 'estimation', 'specification', 'econometric', 'research design',
               'methodology', '実証戦略', '推定方法', '識別', '分析方法', '推定式', '分析の枠組み'),
    'results': ('results', 'findings', 'estimates', 'main effects', 'evidence', '結果', '推定結果', '分析結果'),
    'mechanism': ('mechanism', 'channel', 'heterogeneity', 'interpretation', '経路', 'メカニズム', '異質性', '解釈'),
    'robustness': ('robustness', 'sensitivity', 'placebo', 'alternative', '頑健', '感度', 'プラセボ'),
    'conclusion': ('conclusion', 'concluding', 'discussion', 'summary', 'おわりに', '結論', 'まとめ', '結び', '終わりに'),
}
SKIP_HEADINGS = ('references', 'bibliography', 'appendix', 'acknowledg', '参考文献', '引用文献', '付録', '補論', '謝辞')
JA_END = '。．'
EN_END = '.?!'


def library_path(value=None):
    if value:
        return Path(value).expanduser()
    if os.environ.get('ERS_EXEMPLARS'):
        return Path(os.environ['ERS_EXEMPLARS']).expanduser()
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_DATA_HOME') or str(Path.home() / '.local' / 'share')
    return Path(base) / 'econ-exemplars' / 'library.sqlite'


def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript('''
        create table if not exists docs(id text primary key, name text, path text, lang text, kind text, units integer);
        create table if not exists units(doc text, seq integer, lang text, kind text, function text,
                                         section text, page integer, text text);
        create index if not exists units_filter on units(lang, kind, function);''')
    return db


def cjk_share(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum('぀' <= c <= 'ヿ' or '一' <= c <= '鿿' for c in letters) / len(letters)


def language(text):
    return 'ja' if cjk_share(text) > 0.2 else 'en'


def word_share(text):
    """Share of characters that belong to words; equations and tables score low."""
    if not text:
        return 0.0
    return sum(c.isalpha() or c.isspace() or c in '、。，．,.()（）' for c in text) / len(text)


def pages_of(path):
    if path.suffix.lower() == '.pdf':
        exe = shutil.which('pdftotext')
        if not exe:
            raise SystemExit('pdftotext is required: install poppler (pixi includes it).')
        raw = subprocess.run([exe, '-enc', 'UTF-8', str(path), '-'], capture_output=True, check=True).stdout
        pages = raw.decode('utf-8', 'replace').split('\f')
        info = subprocess.run([shutil.which('pdfinfo') or 'pdfinfo', str(path)], capture_output=True).stdout.decode('utf-8', 'replace')
        size = re.search(r'Page size:\s+([\d.]+) x ([\d.]+)', info)
        landscape = bool(size) and float(size.group(1)) > float(size.group(2))
        return pages, landscape
    return [path.read_text(encoding='utf-8', errors='replace')], False


def heading_function(line):
    text = re.sub(r'^\s*(?:[IVX]+\.|\d+(?:\.\d+)*\.?|第\s*\d+\s*[章節]|[A-Z]\.)\s*', '', line).strip().lower()
    if not text or len(text) > 60:
        return None
    if any(text.startswith(word) for word in SKIP_HEADINGS):
        return 'skip'
    for function, words in FUNCTIONS.items():
        if any(text.startswith(word) or (len(text) < 25 and word in text) for word in words):
            return function
    return None


def is_heading(line, lang):
    stripped = line.strip()
    if not stripped or len(stripped) > 70 or stripped[-1] in JA_END + EN_END + '、，,:;':
        return False
    numbered = re.match(r'^(?:[IVX]+\.|\d+(?:\.\d+)*\.?|第\s*\d+\s*[章節]|[A-Z]\.)\s+\S', stripped)
    return bool(numbered) or heading_function(stripped) is not None


def join(lines, lang):
    out = ''
    for line in lines:
        line = line.strip()
        if not out:
            out = line
        elif lang == 'ja' or cjk_share(out[-1:] + line[:1]) > 0:
            out += line
        elif out.endswith('-') and line[:1].islower():
            out = out[:-1] + line
        else:
            out += ' ' + line
    return re.sub(r'\s+', ' ', out).strip()


def prose_units(pages, lang):
    """Rebuild paragraphs across line, column and page breaks; a paragraph ends where a sentence ends on a short line
    or before a blank line."""
    units, function, section, block, start = [], None, '', [], 1
    ends = JA_END if lang == 'ja' else EN_END

    def flush(force=False):
        nonlocal block
        if block and (force or join(block, lang)[-1:] in ends + '」）)'):
            if function != 'skip':
                units.append([function, section, start, join(block, lang)])
            block = []
    for number, page in enumerate(pages, 1):
        lines = [x for x in page.split('\n') if not re.fullmatch(r'\s*(?:\d{1,4}|\d+\s*/\s*\d+|-\s*\d+\s*-)\s*', x)]
        widths = sorted(len(x.strip()) for x in lines if len(x.strip()) > 20)
        full = widths[len(widths) * 3 // 4] if widths else 60
        for line in lines:
            stripped = line.strip()
            if not stripped:
                flush()
                continue
            if is_heading(stripped, lang):
                flush(force=True)
                found = heading_function(stripped)
                if found:
                    function, section = found, stripped
                continue
            if not block:
                start = number
            block.append(stripped)
            if stripped[-1] in ends and len(stripped) < 0.8 * full:
                flush()
    flush(force=True)
    merged = []
    for unit in units:
        text = unit[3]
        continues = merged and (merged[-1][3][-1:] not in ends + '」）)' or (lang == 'en' and text[:1].islower()))
        if continues and merged[-1][0] == unit[0]:
            merged[-1][3] = join([merged[-1][3], text], lang)
        else:
            merged.append(unit)
    keep = []
    for function, section, page, text in merged:
        low = text.lower()
        if not (80 <= len(text) <= 2500) or word_share(text) < 0.8:
            continue
        if '@' in text or 'we thank' in low or ('university' in low and len(text) < 300):
            continue
        if lang == 'en' and text.count(' ') < 8:
            continue
        keep.append((function, section, page, text))
    return keep


def slide_units(pages, lang):
    units, function, section = [], None, ''
    for number, page in enumerate(pages, 1):
        lines = [x.strip() for x in page.split('\n') if x.strip()]
        if not lines:
            continue
        title = lines[0]
        found = heading_function(title)
        if found:
            function, section = found, title
        items = []
        for line in lines[1:]:
            if items and line == items[-1]:
                continue
            bullet = re.match(r'^[•・\-–▶■□◆○●]\s*', line)
            if items and not bullet and items[-1][-1:] not in JA_END + EN_END + ':：' and word_share(line) > 0.7:
                items[-1] = join([items[-1], line], lang)
            else:
                items.append(line[bullet.end():] if bullet else line)
        body = title + '\n' + '\n'.join('- ' + x for x in items if x != title and word_share(x) > 0.7 and len(x) > 1)
        if len(body) >= 40 and function != 'skip':
            units.append((function, section or title, number, body[:1500]))
    return units


def cmd_add(args, db):
    files = []
    for item in args.paths:
        path = Path(item).expanduser()
        if path.is_dir():
            files += sorted(p for p in path.rglob('*') if p.suffix.lower() in ('.pdf', '.txt', '.md', '.tex'))
        elif path.is_file():
            files.append(path)
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        if db.execute('select 1 from docs where id=?', (digest,)).fetchone():
            print(f'{digest}  already registered  {path.name}')
            continue
        try:
            pages, landscape = pages_of(path)
        except subprocess.CalledProcessError:
            print(f'skipped (unreadable)  {path.name}')
            continue
        lang = args.lang or language(' '.join(pages)[:20000])
        kind = args.kind or ('slide' if landscape else 'prose')
        units = slide_units(pages, lang) if kind == 'slide' else prose_units(pages, lang)
        db.executemany('insert into units values(?,?,?,?,?,?,?,?)',
                       [(digest, i, lang, kind, f, s, p, t) for i, (f, s, p, t) in enumerate(units)])
        db.execute('insert into docs values(?,?,?,?,?,?)', (digest, path.name, str(path.resolve()), lang, kind, len(units)))
        db.commit()
        print(f'{digest}  {lang} {kind:5} {len(units):4} units  {path.name}')


def cmd_list(args, db):
    for row in db.execute('select id, lang, kind, units, name from docs order by lang, kind, name'):
        print('{}  {} {:5} {:4} units  {}'.format(*row))


def cmd_remove(args, db):
    for doc in args.docs:
        db.execute('delete from units where doc=?', (doc,))
        db.execute('delete from docs where id=?', (doc,))
    db.commit()


def candidates(args, db):
    sql, params = 'select doc, seq, function, section, page, text from units where lang=?', [args.lang]
    if args.kind:
        sql += ' and kind=?'
        params.append(args.kind)
    if args.function:
        sql += ' and function=?'
        params.append(args.function)
    if getattr(args, 'doc', None):
        sql += ' and doc=?'
        params.append(args.doc)
    rows = db.execute(sql, params).fetchall()
    terms = [t for t in re.split(r'[\s,、，]+', args.query or '') if t]
    scored = []
    for row in rows:
        text = row[5].lower()
        score = sum(text.count(t.lower()) for t in terms) if terms else 0
        scored.append((-score, len(row[5]) > 1200, row[0], row[1], row))
    scored.sort()
    return [entry[-1] for entry in scored if not terms or entry[0] < 0] or [entry[-1] for entry in scored]


def names(db):
    return dict(db.execute('select id, name from docs'))


def cmd_find(args, db):
    rows, label, used, shown, total = candidates(args, db), names(db), set(), 0, 0
    for doc, seq, function, section, page, text in rows:
        if doc in used or shown >= args.limit or total + len(text) > args.max_chars:
            continue
        used.add(doc)
        shown += 1
        total += len(text)
        print(f'--- [{doc}:{seq}] {label.get(doc, doc)} p.{page} {function or "-"} | {section}\n{text}\n')
    print(f'({shown} passages, {total} characters)')


def cmd_outline(args, db):
    rows = candidates(args, db)
    if not rows:
        raise SystemExit('no matching passages')
    doc = args.doc or rows[0][0]
    function = args.function or rows[0][2]
    selected = db.execute('select seq, section, text from units where doc=? and function is ? order by seq',
                          (doc, function)).fetchall()
    ends = JA_END if args.lang == 'ja' else EN_END
    print(f'--- outline [{doc}] {names(db).get(doc, doc)} | {function}')
    total = 0
    for number, (seq, section, text) in enumerate(selected, 1):
        first = first_sentence(text, args.lang)[:240]
        total += len(first)
        print(f'{number}. {first}')
    print(f'({len(selected)} paragraphs, {total} characters)')


ABBREVIATIONS = re.compile(r'(?:\bet al|\be\.g|\bi\.e|\bcf|\bp|\bpp|\bFig|\bNo|\bVol|\bU\.S|\b[A-Z])\.$')


def first_sentence(text, lang):
    if lang == 'ja':
        return sentences(text)[0] if sentences(text) else text
    for match in re.finditer(r'[.?!](?=\s+[A-Z(“"]|$)', text):
        if not ABBREVIATIONS.search(text[:match.end()]):
            return text[:match.end()]
    return text


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[。．])', text) if len(s.strip()) > 4]


def cmd_style(args, db):
    rows = candidates(args, db)[:args.sample]
    opening, ending, lengths, comma = Counter(), Counter(), [], Counter()
    for *_, text in rows:
        comma['、。' if '、' in text else '，．' if '，' in text else '-'] += 1
        for sentence in sentences(re.sub(r'\n-\s*', '\n', text).replace('\n', '')):
            lengths.append(len(sentence))
            head = re.match(r'^([^、，]{1,8})[、，]', sentence)
            if head:
                opening[head.group(1)] += 1
            core = sentence.rstrip('。．')
            tail = re.search(r'(である|であった|となる|となった|といえる|と考えられる|とみられる|のである|ている|ていた|てい'
                             r'る|られる|される|する|した|ない|なる|ある|あった|だ|ます|ました|です|でした)$', core)
            ending[tail.group(1) if tail else core[-3:]] += 1
    if not lengths:
        raise SystemExit('no matching Japanese sentences')
    q = statistics.quantiles(lengths, n=4) if len(lengths) > 3 else [min(lengths), statistics.median(lengths), max(lengths)]
    print(f'--- style of {len(rows)} passages, {len(lengths)} sentences')
    print('punctuation: ' + ', '.join(f'{k} {v}' for k, v in comma.most_common()))
    print(f'sentence length (characters): quartiles {q[0]:.0f} / {q[1]:.0f} / {q[2]:.0f}; '
          f'short (<30) {sum(x < 30 for x in lengths) / len(lengths):.0%}, long (>70) {sum(x > 70 for x in lengths) / len(lengths):.0%}')
    print('openings: ' + '、'.join(f'{k}({v})' for k, v in opening.most_common(args.top)))
    print('endings: ' + '、'.join(f'{k}({v})' for k, v in ending.most_common(args.top)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--library', help='library file (default: $ERS_EXEMPLARS or the user data directory)')
    sub = parser.add_subparsers(dest='command', required=True)
    add = sub.add_parser('add')
    add.add_argument('paths', nargs='+')
    add.add_argument('--lang', choices=('ja', 'en'))
    add.add_argument('--kind', choices=('prose', 'slide'))
    sub.add_parser('list')
    remove = sub.add_parser('remove')
    remove.add_argument('docs', nargs='+')
    for name in ('find', 'outline', 'style'):
        p = sub.add_parser(name)
        p.add_argument('--lang', choices=('ja', 'en'), required=True)
        p.add_argument('--function', choices=tuple(FUNCTIONS))
        p.add_argument('--kind', choices=('prose', 'slide'))
        p.add_argument('--query')
        p.add_argument('--doc')
        p.add_argument('--limit', type=int, default=3)
        p.add_argument('--max-chars', type=int, default=2400)
        p.add_argument('--sample', type=int, default=40)
        p.add_argument('--top', type=int, default=15)
    args = parser.parse_args(argv)
    path = library_path(args.library)
    if args.command not in ('add',) and not path.exists():
        raise SystemExit(f'no exemplar library at {path}; register files with: exemplars.py add PATH')
    db = connect(path)
    {'add': cmd_add, 'list': cmd_list, 'remove': cmd_remove, 'find': cmd_find,
     'outline': cmd_outline, 'style': cmd_style}[args.command](args, db)


if __name__ == '__main__':
    main()
