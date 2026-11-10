#!/usr/bin/env python3
"""Local checks and exact snapshot writing using Python's standard library.

Text matches use NFKC/casefold views mapped to raw source coordinates. Snapshot writes
stage exact bytes before an atomic no-overwrite directory rename.
"""
import argparse
import ctypes
import errno
import codecs
import hashlib
import html
import importlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import unicodedata


SURFACES = ('final', 'progress', 'status', 'error')
MAX_BYTES = 16 * 1024 * 1024
TEXT_SUFFIXES = {'.txt', '.md', '.tex', '.bib', '.csv', '.tsv', '.json', '.yaml', '.yml', '.rst', '.html', '.xml', '.py', '.r', '.jl', '.sql', '.sh', '.toml', '.js', '.ts', '.css', '.qmd', '.svg', '.ipynb', '.do', '.ado', '.m', '.c', '.cpp', '.h'}


class GateError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise GateError(message)


def lock_fd(fd):
    """One nonblocking OS-owned lock; closing the descriptor releases it."""
    if sys.platform == 'win32':
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise BlockingIOError(exc.errno, 'writer active') from exc
            raise
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _windows_move(source, target, replace=False):
    move = ctypes.WinDLL('kernel32', use_last_error=True).MoveFileExW
    move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong]
    move.restype = ctypes.c_int
    # No cross-volume copy fallback; retain atomic same-volume rename semantics.
    if not move(str(Path(source).absolute()), str(Path(target).absolute()), 8 | int(replace)):
        number = ctypes.get_last_error()
        if number in (80, 183):
            raise FileExistsError(errno.EEXIST, 'destination exists', str(target))
        raise ctypes.WinError(number)


def sync_directory(path):
    # Windows namespace writes below use MOVEFILE_WRITE_THROUGH, not a directory
    # fd (unsupported by the Windows CRT). File contents are fsynced first.
    if sys.platform != 'win32':
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def replace_path(source, target):
    if sys.platform == 'win32':
        _windows_move(source, target, replace=True)
    else:
        os.replace(source, target)


def publish_file(source, target):
    if sys.platform == 'win32':
        _windows_move(source, target)
    else:
        os.link(source, target, follow_symlinks=False)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')

def sha(data):
    if isinstance(data, FileSnapshot):
        for _ in data.chunks():
            pass
        return data.sha256
    return hashlib.sha256(data).hexdigest()

class FileSnapshot(io.BufferedIOBase):
    """Read-only, versioned file content with bounded text access."""
    snapshot_kind = 'fixed-file-v1'

    def __init__(self, path, size, digest):
        super().__init__()
        self.path, self.size, self.sha256 = Path(path).absolute(), size, digest
        self.position = 0

    def __len__(self):
        return self.size

    def readable(self):
        return True

    def writable(self):
        return False

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self._checkClosed()
        require(type(offset) is int and type(whence) is int, 'invalid snapshot seek')
        position = offset + (self.position if whence == 1 else self.size if whence == 2 else 0)
        require(type(offset) is int and whence in (0, 1, 2) and position >= 0, 'invalid snapshot seek')
        self.position = position
        return position

    def __getitem__(self, key):
        if isinstance(key, int):
            start = key if key >= 0 else self.size + key
            require(0 <= start < self.size, 'snapshot index outside file')
            return self[start:start + 1][0]
        require(isinstance(key, slice) and key.step in (None, 1), 'invalid snapshot slice')
        start, end, _ = key.indices(self.size)
        require(end - start <= MAX_BYTES, 'text or inspection range exceeds byte budget')
        with _open_regular(self.path) as handle:
            handle.seek(start)
            return handle.read(max(0, end - start))

    def read(self, size=-1):
        self._checkClosed()
        require(size is None or type(size) is int, 'invalid snapshot read size')
        size = max(0, self.size - self.position) if size is None or size < 0 else size
        data = self[self.position:self.position + size]
        self.position += len(data)
        return data

    def startswith(self, prefix):
        return self[:len(prefix)] == prefix

    def chunks(self):
        value, size = hashlib.sha256(), 0
        with _open_regular(self.path) as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                size += len(chunk)
                value.update(chunk)
                yield chunk
        require(size == self.size and value.hexdigest() == self.sha256,
                'pinned file changed: ' + str(self.path))

    def decode(self, encoding='utf-8', errors='strict'):
        require(self.size <= MAX_BYTES, 'text body exceeds byte budget')
        return b''.join(self.chunks()).decode(encoding, errors)

    def strip(self, *args):
        require(self.size <= MAX_BYTES, 'text body exceeds byte budget')
        return b''.join(self.chunks()).strip(*args)


class UTF8Text:
    """Character-coordinate access to a large fixed original with bounded slices."""
    def __init__(self, data):
        self.data, self.length = data, 0
        for text in self._chunks():
            self.length += len(text)

    def _chunks(self):
        decoder = codecs.getincrementaldecoder('utf-8')('strict')
        for raw in self.data.chunks():
            yield decoder.decode(raw)
        yield decoder.decode(b'', final=True)

    def __len__(self):
        return self.length

    def __getitem__(self, key):
        require(isinstance(key, slice) and key.step in (None, 1), 'text access requires a character range')
        start, end, _ = key.indices(self.length)
        parts, position, size = [], 0, 0
        for text in self._chunks():
            left, right = max(0, start - position), min(len(text), end - position)
            if right > left:
                part = text[left:right]
                size += len(part.encode('utf-8'))
                require(size <= MAX_BYTES, 'selected original text exceeds inspection byte budget')
                parts.append(part)
            position += len(text)
        return ''.join(parts)


def _open_regular(path):
    path = Path(path).absolute()
    for component in [path, *path.parents]:
        require(not component.is_symlink(), 'symlink prohibited: ' + str(component))
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise GateError('nonregular file: ' + str(path))
    return os.fdopen(fd, 'rb')


def file_snapshot(path):
    value, size = hashlib.sha256(), 0
    with _open_regular(path) as handle:
        before = os.fstat(handle.fileno())
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            size += len(chunk)
            value.update(chunk)
        after = os.fstat(handle.fileno())
    require((before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode) ==
            (after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode) and size == after.st_size,
            'file changed while fixing its version')
    return FileSnapshot(path, size, value.hexdigest())


def is_content(data):
    return isinstance(data, (bytes, FileSnapshot))


def write_content(handle, data):
    require(is_content(data), 'snapshot content must be bytes or a fixed file')
    if isinstance(data, FileSnapshot):
        for chunk in data.chunks():
            handle.write(chunk)
    else:
        handle.write(data)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result

def regular_bytes(path):
    path = Path(path).absolute()
    for component in [path, *path.parents]:
        require(not component.is_symlink(), 'symlink prohibited: ' + str(component))
    require(stat.S_ISREG(path.stat().st_mode), 'nonregular file: ' + str(path))
    require(path.stat().st_size <= MAX_BYTES, 'file too large')
    # O_NOFOLLOW additionally protects the last component on supported hosts.
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'nonregular file')
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, 'file too large')
    return data

def parse_json(data):
    def number(value):
        result = float(value)
        require(math.isfinite(result), 'nonfinite JSON')
        return result
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=_pairs,
                          parse_float=number,
                          parse_constant=lambda x: (_ for _ in ()).throw(GateError('nonfinite JSON')))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GateError('invalid UTF-8 JSON') from exc

def read_json(path):
    return parse_json(regular_bytes(path))

def hexhash(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None

def safe_relative(value):
    require(isinstance(value, str) and value and '\\' not in value and '\x00' not in value,
            'invalid relative artifact path')
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(p not in ('', '.', '..') for p in value.split('/')),
            'path escape or ambiguous path')
    require(':' not in value, 'platform-ambiguous path')
    return value

def norm(text):
    return unicodedata.normalize('NFKC', text).casefold()

# Conservative text extraction, not a browser or a complete Markdown renderer.
# Retain source scanning as well: markup, comments, code and quotations are not
# exemptions. Internal view spans are composed back to raw-source characters
# by text_views; no normalized offset is presented as a raw-source offset.
_VISIBLE_TOKEN = re.compile(
    r"<!--.*?-->|<![A-Za-z][^>]*>|<\?.*?\?>|"
    r"</?[A-Za-z][A-Za-z0-9:.-]*(?:\s+(?:[^\"'<>]|\"[^\"]*\"|'[^']*')*)?\s*/?>|"
    r"&(?:\#[xX][0-9a-fA-F]+;?|\#[0-9]+;?|[A-Za-z][A-Za-z0-9]+;)|"
    r"\\[!\"#$%&'()*+,\-./:;<=>?@\[\\\]\^_`{|}~]|[*_`~]+",
    re.DOTALL)


def invisible(character):
    # Format controls include ZWSP, ZWJ, ZWNJ, BOM, soft hyphen and bidi controls.
    # Variation selectors are also visually empty in isolation. This deliberately
    # errs toward extra review; language-sensitive shaping still needs a reviewer.
    code = ord(character)
    return (unicodedata.category(character) == 'Cf'
            or 0xFE00 <= code <= 0xFE0F or 0xE0100 <= code <= 0xE01EF
            or code == 0x034F)


def tex_arguments(text, mapping):
    """Project single braced control-word arguments without executing TeX.

    Preserve multi-argument commands and escaped delimiters. This is an extra
    detection view; original code and markup always remain separately scanned.
    """
    hidden = set()
    for command in re.finditer(r'(?<!\\)\\[A-Za-z@]+\*?(?=\{)', text):
        start = command.end()
        depth, cursor = 1, start + 1
        while cursor < len(text) and depth:
            if text[cursor] == '\\':
                cursor += 2
                continue
            if text[cursor] == '{':
                depth += 1
            elif text[cursor] == '}':
                depth -= 1
            cursor += 1
        if depth or text[cursor:cursor + 1] == '{':
            continue
        hidden.update(range(command.start(), start + 1))
        hidden.add(cursor - 1)
    keep = [index for index in range(len(text)) if index not in hidden]
    return ''.join(text[index] for index in keep), [mapping[index] for index in keep]


def visible_text(source):
    """Restore display characters and map them to the original source.

    Removes common inline markup, HTML tags/comments, and invisible controls;
    decodes semicolon-terminated HTML entities. Never executes HTML, CSS, scripts,
    TeX or Markdown. Retains all tag bodies, including script/style and code.
    """
    # Dictionary loading also executes this module from pinned source bytes.
    # Resolve the parser only when the display scan actually needs it.
    route_directory = Path(__file__).resolve().parent
    route_module = 'TOOL_route_registry' if (route_directory / 'TOOL_route_registry.py').is_file() else 'route_registry'
    if not (route_directory / (route_module + '.py')).is_file():
        route_directory = route_directory.parent / 'scripts'
    if str(route_directory) not in sys.path:
        sys.path.insert(0, str(route_directory))
    markdown_labels = importlib.import_module(route_module).markdown_labels

    chars, spans = [], []

    def emit(value, start, end):
        for character in value:
            if not invisible(character):
                chars.append(character)
                spans.append((start, end))

    # Strip controls before token recognition so controls within markup cannot
    # prevent recognizing that markup. Map every token back through this view.
    clean = ''.join(c for c in source if not invisible(c))
    clean_spans = [(i, i + 1) for i, c in enumerate(source) if not invisible(c)]

    clean, clean_spans = markdown_labels(clean, clean_spans)
    clean, clean_spans = tex_arguments(clean, clean_spans)

    def emit_clean(start, end):
        for i in range(start, end):
            emit(clean[i], *clean_spans[i])

    # Unpaired/intraword underscores are identifier constituents, not markup.
    emphasis = set()
    for match in re.finditer(r'(?<!\w)(_{1,2})(?=\S)(.+?)(?<=\S)\1(?!\w)', clean, re.S):
        width = len(match.group(1))
        emphasis.update(range(match.start(), match.start() + width))
        emphasis.update(range(match.end() - width, match.end()))
    cursor = 0
    for token in _VISIBLE_TOKEN.finditer(clean):
        emit_clean(cursor, token.start())
        value = token.group()
        begin, end = clean_spans[token.start()][0], clean_spans[token.end() - 1][1]
        if value.startswith('&'):
            emit(html.unescape(value), begin, end)
        elif re.match(r'</?(?:p|div|section|article|aside|header|footer|main|nav|ul|ol|dl|dt|dd|li|table|thead|tbody|tfoot|tr|td|th|h[1-6]|blockquote|pre|hr)(?=[\s/>])', value, re.I):
            emit('\n\n', begin, end)
        elif re.match(r'<br(?=[\s/>])', value, re.I):
            emit('\n', begin, end)
        elif value.startswith('\\'):
            emit(value[1:], *clean_spans[token.end() - 1])
        elif '_' in value:
            for index in range(token.start(), token.end()):
                if clean[index] == '_' and index not in emphasis:
                    emit_clean(index, index + 1)
        # Otherwise omit recognized markup, keeping its body via later tokens.
        cursor = token.end()
    emit_clean(cursor, len(clean))
    return ''.join(chars), spans


def whitespace_view(text, spans):
    """Fold layout whitespace without joining English words or sentences.

    A single wrapped line or horizontal spacing between Japanese characters may
    be omitted. Punctuation, blank lines, and non-layout separators remain. This
    is a detection approximation, not a claim that arbitrary sentences join.
    """
    def japanese(character):
        code = ord(character)
        return (0x3041 <= code <= 0x3096 or 0x30A1 <= code <= 0x30FA
                or 0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF
                or 0x20000 <= code <= 0x323AF or character in '々ー')

    chars, mapped = [], []
    cursor = 0
    for match in re.finditer(r'[ \t\r\n]+', text):
        chars.extend(text[cursor:match.start()])
        mapped.extend(spans[cursor:match.start()])
        run = match.group().replace('\r\n', '\n').replace('\r', '\n')
        # Preserve paragraph boundaries even for regexes using a literal space.
        if run.count('\n') >= 2:
            chars.extend(text[match.start():match.end()])
            mapped.extend(spans[match.start():match.end()])
        elif not (match.start() > 0 and match.end() < len(text)
                  and japanese(text[match.start() - 1]) and japanese(text[match.end()])):
            chars.append(' ')
            mapped.append((spans[match.start()][0], spans[match.end() - 1][1]))
        cursor = match.end()
    chars.extend(text[cursor:])
    mapped.extend(spans[cursor:])
    return ''.join(chars), mapped


def character_spans(text, mapping, start, end):
    """Exact source constituents; layout whitespace is not lexical content."""
    return [list(mapping[i] if mapping is not None else (i, i + 1))
            for i in range(start, end) if not text[i].isspace()]


def english_continuation(character):
    """One lexical boundary for English rules and Latin term candidates.

    Japanese adjacency delimits Latin tokens; identifier letters, numbers,
    underscores and combining marks do not split a token.
    """
    code = ord(character)
    japanese = (0x3041 <= code <= 0x3096 or 0x30A1 <= code <= 0x30FA
                or 0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF
                or 0x20000 <= code <= 0x323AF or character in '々ー')
    return not japanese and (bool(re.match(r'\w', character))
                             or unicodedata.category(character).startswith('M'))


def english_pattern(pattern, characters):
    """Bind regex word assertions to the shared lexical alphabet, not the Unicode word class.

    Only characters present in the scan views are needed beyond ASCII. No text
    is rewritten, so regex spans still address the original mapped view.
    """
    extra = ''.join(sorted(c for c in set(characters)
                           if not c.isascii() and english_continuation(c)))
    word = '[a-zA-Z0-9_' + re.escape(extra) + ']'
    boundary = '(?:(?<!{0})(?={0})|(?<={0})(?!{0}))'.format(word)
    # Preserve literal escapes and character classes (where \b is backspace).
    output, in_class = [], False
    for token in re.findall(r'\\.|[^\\]', pattern):
        if token == '[':
            in_class = True
        elif token == ']':
            in_class = False
        if not in_class and token == r'\b':
            output.append(boundary)
        elif not in_class and token == r'\w':
            output.append(word)
        else:
            output.append(token)
    return ''.join(output)


def normalized_source(raw):
    """Normalize Unicode clusters while retaining actual source constituents.

    Combining marks and Hangul composition can change preceding characters;
    each composed cluster therefore maps to its entire raw source span. Check
    whole-string equivalence and fail closed rather than fabricate coordinates.
    """
    groups = []
    start = 0
    for index, char in enumerate(raw):
        decomposition = unicodedata.normalize('NFKD', char)
        continuation = bool(decomposition and unicodedata.combining(decomposition[0]))
        # Hangul Jamo composition has canonical combining class zero.
        continuation = continuation or (decomposition and 0x1160 <= ord(decomposition[0]) <= 0x11FF)
        if index and not continuation:
            groups.append((start, index))
            start = index
    if raw:
        groups.append((start, len(raw)))
    chars, mapping = [], []
    for start, end in groups:
        value = norm(raw[start:end])
        chars.append(value)
        mapping.extend([(start, end)] * len(value))
    text = ''.join(chars)
    require(text == norm(raw), 'normalization source mapping could not be established')
    return text, mapping


def text_views(data):
    """Common normalized and display views in raw-source coordinates."""
    raw = data.decode('utf-8')
    source, source_spans = normalized_source(raw)
    visible, visible_spans = visible_text(raw)
    display, display_spans = normalized_source(visible)
    spans = [(visible_spans[start][0], visible_spans[end - 1][1])
             for start, end in display_spans]
    folded, folded_spans = whitespace_view(display, spans)
    return ((source, source_spans), (display, spans), (folded, folded_spans))


class TextInspection:
    """One check's shared views/searches, bound to exact text and transformer.

    This cache contains computed navigation only, never review judgments or
    release authority. It is discarded with the check and cannot survive a
    changed dependency by reusing a path alone.
    """
    def __init__(self):
        self._views, self._hashes = {}, {}
        self.transformer_sha256 = sha(regular_bytes(__file__))

    def key(self, path, data):
        identity = (path, id(data))
        if identity not in self._hashes:
            require(is_content(data), 'inspection requires fixed text bytes')
            self._hashes[identity] = (data, sha(data))
        return (path, self._hashes[identity][1], self.transformer_sha256)

    def views(self, path, data):
        key = self.key(path, data)
        if key not in self._views:
            self._views[key] = text_views(data)
        return self._views[key]

def expand_dictionary(dictionary):
    """Restore the legacy logical rule records from a recognized compact source."""
    require(isinstance(dictionary, dict), 'invalid dictionary')
    if 'format' not in dictionary:
        require('rule_defaults' not in dictionary and 'functional_check_defaults' not in dictionary,
                'dictionary defaults require a format')
        return dictionary
    extended = dictionary['format'] == 'shared-rule-and-functional-defaults-v1'
    require((dictionary['format'] == 'shared-rule-defaults-v1' or extended) and dictionary.get('version') == '1.8',
            'unsupported dictionary format')
    require(extended or 'functional_check_defaults' not in dictionary, 'unexpected functional defaults')
    defaults = dictionary.get('rule_defaults')
    require(isinstance(defaults, dict) and set(defaults) == {'instruction', 'action', 'explanation', 'repair'},
            'invalid dictionary defaults')
    require(defaults['instruction'] == 'Each rule inherits action, explanation, and repair from these defaults unless the rule explicitly supplies its own value for that field.',
            'invalid dictionary inheritance instruction')
    require(defaults['action'] in ('block', 'review') and all(isinstance(defaults[k], str) and defaults[k].strip()
            for k in ('explanation', 'repair')), 'invalid dictionary defaults')
    rules = dictionary.get('rules')
    require(isinstance(rules, list) and all(isinstance(row, dict) for row in rules), 'invalid dictionary rules')
    values = {key: defaults[key] for key in ('action', 'explanation', 'repair')}
    result = {key: value for key, value in dictionary.items()
              if key not in ('format', 'rule_defaults', 'functional_check_defaults')}
    result['rules'] = [{**values, **row} for row in rules]
    require(all(isinstance(row['explanation'], str) and row['explanation'].strip()
                and isinstance(row['repair'], str) and row['repair'].strip() for row in result['rules']),
            'invalid rule explanation or repair')
    if extended:
        functional = dictionary.get('functional_check_defaults')
        require(isinstance(functional, dict) and set(functional) == {'instruction', 'required_action'}
                and functional['instruction'] == 'Each functional check inherits required_action from these defaults unless it explicitly supplies its own value.'
                and isinstance(functional['required_action'], str) and functional['required_action'].strip(),
                'invalid functional check defaults')
        checks = dictionary.get('functional_checks')
        require(isinstance(checks, list) and all(isinstance(row, dict) for row in checks),
                'invalid functional checks')
        result['functional_checks'] = [{**row, 'required_action': row.get('required_action', functional['required_action'])}
                                       for row in checks]
        require(all(isinstance(row['required_action'], str) and row['required_action'].strip()
                    for row in result['functional_checks']), 'invalid functional check action')
    return result


def scan(artifacts, dictionary, inspection=None):
    dictionary = expand_dictionary(dictionary)
    require(isinstance(dictionary, dict) and dictionary.get('version') in ('1.0', '1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7', '1.8', '2.0') and isinstance(dictionary.get('rules'), list),
            'invalid dictionary')
    hits, ids = [], set()
    # Build views once, rather than once per dictionary rule.
    inspection = inspection or TextInspection()
    views = {path: inspection.views(path, data) for path, data in artifacts.items()}
    hashes = {path: sha(data) for path, data in artifacts.items()}
    # English boundary expansion needs only non-ASCII continuation characters.
    alphabet = {char for path_views in views.values() for text, _ in path_views for char in text}
    alphabet = {char for char in alphabet if not char.isascii() and english_continuation(char)}
    for rule in dictionary['rules']:
        require(isinstance(rule, dict), 'malformed dictionary rule')
        rid, pattern, action = rule.get('id'), rule.get('pattern'), rule.get('action')
        require(isinstance(rid, str) and rid and rid not in ids, 'invalid/duplicate rule id')
        ids.add(rid)
        require(isinstance(pattern, str) and pattern and len(pattern) <= 4096, 'invalid rule pattern')
        require(action in ('block', 'review'), 'invalid rule action')
        # Patterns themselves are regex source; NFKC/casefold applies to input.
        # Case-insensitive matching handles ordinary literal pattern casing.
        try:
            regex = re.compile(english_pattern(pattern, alphabet) if rid.startswith('en-') else pattern,
                               re.IGNORECASE)
        except re.error as exc:
            raise GateError('invalid dictionary regex: ' + rid) from exc
        for path, path_views in views.items():
            seen = set()
            for view_name, (text, mapping) in zip(('source', 'visible', 'whitespace'), path_views):
                for match in regex.finditer(text):
                    require(match.end() > match.start(), 'zero-width dictionary match')
                    start, end = match.start(), match.end()
                    if mapping is not None:
                        start, end = mapping[start][0], mapping[end - 1][1]
                    if (start, end) in seen:
                        continue
                    seen.add((start, end))
                    hit_spans = character_spans(text, mapping, match.start(), match.end())
                    hit = {'rule_id': rid, 'path': path, 'start': start,
                           'end': end, 'action': action, 'character_spans': hit_spans,
                           'input_sha256': hashes[path], 'view': view_name,
                           'offset_basis': 'raw-source-unicode',
                           'matched_text': text[match.start():match.end()],
                           'resolution': 'integrated-review'}
                    hits.append(hit)
                    require(len(hits) <= 10000, 'too many dictionary hits')
    return hits

def recheck_inputs(expected):
    for path, expected_hash in expected.items():
        require(file_snapshot(path).sha256 == expected_hash, 'input changed during staging: ' + path)

def atomic_publish(staging, output):
    """Install a staged local directory atomically without replacing its destination."""
    if sys.platform == 'win32':
        return _windows_move(staging, output)
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == 'darwin':
        rename = getattr(libc, 'renamex_np', None)
        require(rename is not None, 'atomic no-replace directory rename unavailable')
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(staging), os.fsencode(output), 4)  # RENAME_EXCL
    else:
        require(sys.platform.startswith('linux'), 'unsupported atomic publication platform')
        rename = getattr(libc, 'renameat2', None)
        require(rename is not None, 'atomic no-replace directory rename unavailable')
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(staging), -100, os.fsencode(output), 1)
    if result != 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number), str(output))

def release(artifacts, output, input_hashes=None, validate_inputs=None):
    """Write a fixed byte snapshot; recheck supplied input hashes after staging."""
    output = Path(output).absolute()
    require(not output.exists() and not output.is_symlink(), 'output already exists')
    parent = output.parent
    require(parent.is_dir(), 'output parent missing')
    for component in [parent, *parent.parents]:
        require(not component.is_symlink(), 'symlink output ancestor')
    staging = Path(tempfile.mkdtemp(prefix='.gate-', dir=parent))
    try:
        for path, data in artifacts.items():
            target = staging / safe_relative(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                write_content(stream, data)
                stream.flush()
                os.fsync(stream.fileno())
            expected_hash = data.sha256 if isinstance(data, FileSnapshot) else sha(data)
            require(file_snapshot(target).sha256 == expected_hash, 'output byte verification failed')
        if input_hashes is not None:
            recheck_inputs(input_hashes)
        if validate_inputs is not None:
            validate_inputs()
        atomic_publish(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('scan-text',))
    parser.add_argument('--dictionary')
    parser.add_argument('--input')
    parser.add_argument('--require-clean', action='store_true')
    parser.add_argument('--surface', choices=SURFACES, default='final')
    args = parser.parse_args(argv)
    try:
        require(args.dictionary, 'scan-text requires --dictionary')
        require(args.input, 'scan-text requires --input')
        path = Path(args.input)
        require(path.suffix.lower() in TEXT_SUFFIXES, 'scan-text requires a supported text suffix')
        data = regular_bytes(path)
        decoded = data.decode('utf-8')
        require(not any(ord(c) < 32 and c not in '\t\n\r\f' for c in decoded),
                'unsupported binary artifact')
        dictionary_raw = regular_bytes(args.dictionary)
        dictionary = parse_json(dictionary_raw)
        hits = scan({path.name: data}, dictionary)
        status = ('blocked' if hits else 'lexical-clean') if args.require_clean else 'scanned'
        print(json.dumps({'status': status,
                          'dictionary_version': dictionary['version'],
                          'scan_complete': True, 'hit_count': len(hits),
                          'semantic_review': 'not-performed',
                          'coordinate_system': 'raw-source-characters',
                          'hits': [{key: hit[key] for key in
                                    ('rule_id', 'start', 'end', 'character_spans')}
                                   for hit in hits]}, ensure_ascii=False))
        return int(args.require_clean and bool(hits))
    except (GateError, OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
