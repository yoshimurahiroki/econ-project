#!/usr/bin/env python3
"""Local text checks and exact snapshot writing using Python's standard library.

Text matches use NFKC/casefold views mapped to raw source coordinates. Snapshot writes
stage exact bytes before an atomic no-overwrite directory rename.
"""
import argparse
import ctypes
import errno
import codecs
import hashlib
import html
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import unicodedata

ROLES = ('quality-a', 'quality-b', 'compliance')
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

    def __init__(self, path, size, digest, stored=False):
        super().__init__()
        self.path, self.size, self.sha256 = Path(path).absolute(), size, digest
        self.stored, self.position = stored, 0

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


def content_record(data):
    digest = sha(data)
    return {'sha256': digest, 'size_bytes': len(data)} if isinstance(data, FileSnapshot) else digest


def record_hash(record):
    return record['sha256'] if isinstance(record, dict) else record


def store_file(data, directory):
    """Share one immutable content version across local run snapshots."""
    require(isinstance(data, FileSnapshot), 'fixed file required')
    directory = Path(directory).absolute()
    require(not any(p.is_symlink() for p in (directory, *directory.parents)), 'symlink object store prohibited')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = directory / data.sha256
    if not target.exists():
        fd, temporary = tempfile.mkstemp(prefix='.object-', dir=directory)
        try:
            with os.fdopen(fd, 'wb') as handle:
                write_content(handle, data)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o400)
            try:
                publish_file(temporary, target)
                sync_directory(directory)
            except FileExistsError:
                pass
        finally:
            if sys.platform == 'win32' and os.path.exists(temporary):
                os.chmod(temporary, 0o600)  # Remove our own temporary's read-only flag.
            Path(temporary).unlink(missing_ok=True)
    pinned = file_snapshot(target)
    require((pinned.sha256, pinned.size) == (data.sha256, data.size), 'stored object version mismatch')
    pinned.stored = True
    return pinned

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
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=_pairs,
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


# BEGIN GENERATED MARKDOWN PARSER
def markdown_container_text(line, frame=None, with_frame=False):
    """Remove block container markers while retaining their textual contents."""
    if frame is not None:
        for kind, width in frame:
            if kind == 'quote':
                line = re.sub(r'^ {0,3}>[ \t]?', '', line, count=1)
            elif len(line) - len(line.lstrip(' \t')) >= width:
                line = line[width:]
        return line
    containers = []
    while True:
        quote = re.match(r'^ {0,3}>[ \t]?', line)
        listing = re.match(r'^ {0,3}(?:[-+*]|[0-9]{1,9}[.)])(?:[ \t]+|$)', line)
        marker = quote or listing
        if not marker:
            break
        containers.append(('quote' if quote else 'list', marker.end()))
        line = line[marker.end():]
    return (line, containers) if with_frame else line

def reference_definition_spans(text):
    """Locate block reference metadata, including continued destinations/titles.

    Return original character envelopes and raw labels; never enter fenced code.
    The display scanner receives this same implementation during generation.
    """
    lines = text.splitlines(keepends=True)
    offsets, total = [], 0
    for line in lines:
        offsets.append(total)
        total += len(line)
    def view(line):
        return markdown_container_text(line).rstrip('\r\n')
    def title(index, rest):
        if not rest or rest[0] not in '\"\'(':
            return None
        closer = ')' if rest[0] == '(' else rest[0]
        position = 1
        while index < len(lines):
            while position < len(rest):
                if rest[position] == '\\':
                    position += 2
                    continue
                if rest[position] == closer:
                    return index if not rest[position + 1:].strip() else None
                position += 1
            index += 1
            if index >= len(lines) or not view(lines[index]).strip():
                return None
            rest, position = view(lines[index]), 0
        return None
    found, index, fence, fence_frame = [], 0, None, []
    while index < len(lines):
        line, containers = markdown_container_text(lines[index], with_frame=True)
        if fence:
            line = markdown_container_text(lines[index], fence_frame)
        line = line.rstrip('\r\n')
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            if re.fullmatch(r' {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*', line):
                fence = None
            index += 1
            continue
        if marker:
            fence = marker.group(1)
            fence_frame = containers
            index += 1
            continue
        match = re.match(r'^ {0,3}\[((?:\\.|[^\]\\\r\n])+)\]:[ \t]*(.*)$', line)
        if not match:
            index += 1
            continue
        start, last, rest = index, index, match.group(2)
        if not rest and last + 1 < len(lines):
            last += 1
            rest = view(lines[last]).lstrip(' \t')
        destination = re.match(r'(?:<(?:\\.|[^<>])*?>|(?:\\.|[^\s<>\"\'])+)(.*)$', rest)
        if not destination:
            index += 1
            continue
        tail = destination.group(1).strip()
        if tail:
            end = title(last, tail)
            if end is None:
                index += 1
                continue
            last = end
        elif last + 1 < len(lines):
            continued = title(last + 1, view(lines[last + 1]).lstrip(' \t'))
            if continued is not None:
                last = continued
        found.append({'start': offsets[start], 'end': offsets[last] + len(lines[last]), 'label': match.group(1)})
        index = last + 1
    return found

def markdown_labels(text, mapping):
    """Keep link labels and their original coordinates, not link metadata.

    This bounded syntax recognizer never crosses a blank line. Undefined
    references remain literal text. Hidden definition lines retain their line
    endings so removing them cannot join separate paragraphs.
    """
    hidden, definitions = set(), set()
    paragraph_break = re.compile(r'\r?\n[ \t]*\r?\n')

    def reference(value):
        return ' '.join(html.unescape(re.sub(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\\\]\^_`{|}~])',
                                             r'\1', value)).split()).casefold()

    def closing(start, opener, closer):
        depth, index = 1, start + 1
        while index < len(text):
            if paragraph_break.match(text, index):
                return None
            char = text[index]
            if char == '\\':
                index += 2
                continue
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if not depth:
                    return index
            index += 1
        return None

    for definition in reference_definition_spans(text):
        definitions.add(reference(definition['label']))
        hidden.update(i for i in range(definition['start'], definition['end']) if text[i] not in '\r\n')

    index = 0
    while index < len(text):
        if index in hidden:
            index += 1
            continue
        if text[index] == '\\':
            index += 2
            continue
        if text[index] != '[':
            index += 1
            continue
        end = closing(index, '[', ']')
        if end is None:
            index += 1
            continue
        after, finish = end + 1, None
        if after < len(text) and text[after] == '(':
            # Parentheses in destinations may nest; quoted titles and angle
            # destinations may contain parentheses that are not delimiters.
            cursor, depth, quote, angle = after + 1, 1, None, False
            while cursor < len(text):
                char = text[cursor]
                if paragraph_break.match(text, cursor):
                    break
                if char == '\\':
                    cursor += 2
                    continue
                if quote:
                    if char == quote:
                        quote = None
                elif angle:
                    if char == '>':
                        angle = False
                elif char == '<':
                    angle = True
                elif char in '"\'' and text[cursor - 1].isspace():
                    quote = char
                elif char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                    if not depth:
                        finish = cursor + 1
                        break
                cursor += 1
        elif after < len(text) and text[after] == '[':
            reference_end = closing(after, '[', ']')
            if reference_end is not None:
                key = text[after + 1:reference_end] or text[index + 1:end]
                if reference(key) in definitions:
                    finish = reference_end + 1
        elif reference(text[index + 1:end]) in definitions:
            finish = after
        if finish is not None:
            hidden.add(index)
            hidden.update(range(end, finish))
        # Continue inside the label to recognize nested inline decoration.
        index += 1
    keep = [i for i in range(len(text)) if i not in hidden]
    return ''.join(text[i] for i in keep), [mapping[i] for i in keep]
# END GENERATED MARKDOWN PARSER


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


def covers(container, contained):
    return bool(contained) and all(any(a <= c and d <= b for a, b in container)
                                   for c, d in contained)


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


def term_key(text):
    """Index spelling only: unify Latin intraword hyphens, never minus/ranges."""
    text = norm(text)
    chars = list(text)
    for index, character in enumerate(text):
        if character not in '-‐‑':
            continue
        left, right = index - 1, index + 1
        while left >= 0 and unicodedata.category(text[left]).startswith('M'):
            left -= 1
        while right < len(text) and unicodedata.category(text[right]).startswith('M'):
            right += 1
        if (left >= 0 and right < len(text)
                and 'LATIN' in unicodedata.name(text[left], '')
                and 'LATIN' in unicodedata.name(text[right], '')):
            chars[index] = '-'
    return ''.join(chars)


def occurrences(form, text_views, boundaries=True):
    normalized = term_key(form)
    pattern = re.escape(normalized)
    def continuation(character, edge):
        latin_edge = 'LATIN' in unicodedata.name(edge, '') or edge.isascii() and edge.isalnum()
        if latin_edge:
            return english_continuation(character)
        return bool(re.match(r'\w', character)) or unicodedata.category(character).startswith('M')
    found, seen = [], set()
    for text, mapping in text_views:
        # term_key is length-preserving on these already-normalized views.
        for match in re.finditer(pattern, term_key(text)):
            if boundaries and ((match.start() and continuation(text[match.start()-1], normalized[0]))
                               or (match.end() < len(text) and continuation(text[match.end()], normalized[-1]))):
                continue
            spans = character_spans(text, mapping, match.start(), match.end())
            occurrence = {'text': text[match.start():match.end()], 'start': spans[0][0], 'end': spans[-1][1],
                          'character_spans': spans}
            key = (occurrence['text'], occurrence['start'], occurrence['end'],
                   tuple(tuple(span) for span in spans))
            if key not in seen:
                seen.add(key)
                found.append(occurrence)
    return found



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


def structure_regions(data):
    """Retain raw coordinates while distinguishing link metadata from prose.

    Classification never changes the full-source dictionary scan. Code remains
    propositional input, including numbers in Markdown-looking code examples.
    The existing shared Markdown recognizer supplies link metadata boundaries.
    """
    raw = data.decode('utf-8')
    _, retained = markdown_labels(raw, [(i, i + 1) for i in range(len(raw))])
    visible = {left for left, _ in retained}
    kinds = ['visible_text' if i in visible else 'link_destination' for i in range(len(raw))]
    for record in reference_definition_spans(raw):
        for index in range(record['start'], record['end']):
            if raw[index] not in '\r\n':
                kinds[index] = 'identifier'
    # Fenced and inline code override link-looking syntax; its numeric results
    # still require their proposition/source correspondence.
    fenced, start = None, None
    offset = 0
    for line in raw.splitlines(keepends=True):
        marker = re.match(r'^[ \t]{0,3}(`{3,}|~{3,})', line)
        if fenced is None and marker:
            fenced, start = marker.group(1), offset
        elif fenced is not None and re.match(r'^[ \t]{0,3}' + re.escape(fenced[0]) +
                                             '{' + str(len(fenced)) + r',}[ \t]*(?:\r?\n)?$', line):
            kinds[start:offset + len(line)] = ['code'] * (offset + len(line) - start)
            fenced, start = None, None
        offset += len(line)
    if fenced is not None:
        kinds[start:] = ['code'] * (len(raw) - start)
    for match in re.finditer(r'(?<!`)(`+)(?!`)([^\r\n]*?)(?<!`)\1(?!`)', raw):
        kinds[match.start():match.end()] = ['code'] * (match.end() - match.start())
    # Markup itself is retained separately. Its numeric contents remain subject
    # to the quantity guard unless they are known link destinations/identifiers.
    for match in _VISIBLE_TOKEN.finditer(raw):
        for index in range(match.start(), match.end()):
            if kinds[index] == 'visible_text':
                kinds[index] = 'markup'
    regions, start = [], 0
    for end in range(1, len(raw) + 1):
        if end == len(raw) or kinds[end] != kinds[start]:
            regions.append({'kind': kinds[start], 'start': start, 'end': end,
                            'text': raw[start:end]})
            start = end
    return {'input_sha256': sha(data), 'regions': regions}


class TextInspection:
    """One check's shared views/searches, bound to exact text and transformer.

    This cache contains computed navigation only, never review judgments or
    release authority. It is discarded with the check and cannot survive a
    changed dependency by reusing a path alone.
    """
    def __init__(self):
        self._views, self._occurrences, self._regions, self._hashes = {}, {}, {}, {}
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

    def occurrences(self, form, path, data, boundaries=True):
        key = (*self.key(path, data), term_key(form), bool(boundaries))
        if key not in self._occurrences:
            self._occurrences[key] = occurrences(form, self.views(path, data), boundaries)
        return self._occurrences[key]

    def regions(self, path, data):
        key = self.key(path, data)
        if key not in self._regions:
            self._regions[key] = structure_regions(data)
        return self._regions[key]


def registered_terms(rule):
    terms, ids = rule.get('technical_terms', []), set()
    require(isinstance(terms, list), 'invalid technical terms')
    for term in terms:
        require(isinstance(term, dict) and set(term) ==
                {'term_id', 'forms', 'domain', 'definition_id', 'definition'},
                'invalid technical term registration')
        require(all(isinstance(term[k], str) and term[k].strip()
                    for k in ('term_id', 'domain', 'definition_id', 'definition'))
                and term['term_id'] not in ids, 'invalid technical term identity')
        ids.add(term['term_id'])
        require(isinstance(term['forms'], list)
                and term['forms'] and all(isinstance(f, str) and f.strip() for f in term['forms']),
                'invalid technical term forms or review flag')
    return terms


def quantity_modifier_spans(hit, views):
    """Classify the syntax after this exact 約 without deciding word identity.

    Numerals and half quantities are explicit quantity starts. 数/全 followed
    by a nonnumeric character remains word-formation evidence for the existing
    definition review. Character spans retain raw scanner coordinates.
    """
    def numeric(char):
        try:
            unicodedata.numeric(char)
            return True
        except (ValueError, TypeError):
            return False
    ambiguous = None
    for text, mapping in views:
        for match in re.finditer('約', text):
            if character_spans(text, mapping, *match.span()) != hit['character_spans']:
                continue
            index = match.end()
            while index < len(text) and text[index] in ' \t':
                index += 1
            if index >= len(text):
                continue
            end = index + 1
            first = text[index]
            kind = 'quantity'
            if first in '+-−.':
                if end >= len(text) or not numeric(text[end]):
                    continue
                end += 1
            elif numeric(first) or first == '半':
                pass
            elif first in '数全':
                if end < len(text) and numeric(text[end]):
                    end += 1
                else:
                    kind = 'word-formation'
            else:
                continue
            result = {'kind': kind, 'character_spans': character_spans(text, mapping, index, end)}
            if kind == 'quantity':
                return result
            ambiguous = result
    return ambiguous


def scan(artifacts, dictionary, inspection=None):
    require(isinstance(dictionary, dict) and dictionary.get('version') in ('1.0', '1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7') and isinstance(dictionary.get('rules'), list),
            'invalid dictionary')
    hits, ids = [], set()
    # Build views once, rather than once per dictionary rule.
    inspection = inspection or TextInspection()
    views = {path: inspection.views(path, data) for path, data in artifacts.items()}
    hashes = {path: sha(data) for path, data in artifacts.items()}
    alphabet = {char for path_views in views.values() for text, _ in path_views for char in text}
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
        terms = registered_terms(rule)
        for path, path_views in views.items():
            term_occurrences = [(term, occurrence) for term in terms for form in term['forms']
                                for occurrence in inspection.occurrences(form, path, artifacts[path])]
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
                    # Membership uses contributing characters, never a source envelope.
                    # An attribute/comment between term words remains separately scanned.
                    hit_spans = character_spans(text, mapping, match.start(), match.end())
                    technical_candidates, candidate_keys = [], set()
                    for term, occurrence in term_occurrences:
                        if not covers(occurrence['character_spans'], hit_spans):
                            continue
                        candidate = {**occurrence, 'term_id': term['term_id'],
                                     'definition_id': term['definition_id'],
                                     'domain': term['domain'], 'definition': term['definition'],
                                     'input_sha256': hashes[path]}
                        candidate_key = canonical(candidate)
                        if candidate_key not in candidate_keys:
                            candidate_keys.add(candidate_key)
                            technical_candidates.append(candidate)
                    hit = {'rule_id': rid, 'path': path, 'start': start,
                           'end': end, 'action': action, 'character_spans': hit_spans,
                           'input_sha256': hashes[path], 'view': view_name,
                           'offset_basis': 'raw-source-unicode',
                           'matched_text': text[match.start():match.end()],
                           'resolution': 'occurrence-review-required'}
                    if technical_candidates:
                        hit['technical_candidates'] = technical_candidates
                    hits.append(hit)
                    require(len(hits) <= 10000, 'too many dictionary hits')
    return hits

def recheck_inputs(expected):
    for path, expected_hash in expected.items():
        require(sha(file_snapshot(path)) == expected_hash, 'input changed during staging: ' + path)

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
            if isinstance(data, FileSnapshot) and data.stored and sys.platform != 'win32':
                try:
                    os.link(data.path, target, follow_symlinks=False)
                except OSError as error:
                    if error.errno != 18:
                        raise
                    with target.open('xb') as stream:
                        write_content(stream, data)
            else:
                with target.open('xb') as stream:
                    write_content(stream, data)
                    stream.flush()
                    os.fsync(stream.fileno())
            require(sha(file_snapshot(target)) == sha(data), 'output byte verification failed')
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
    parser.add_argument('--dictionary', required=True)
    parser.add_argument('--input')
    parser.add_argument('--require-clean', action='store_true')
    parser.add_argument('--surface', choices=SURFACES, default='final')
    args = parser.parse_args(argv)
    try:
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
                          'path': path.name, 'input_sha256': sha(data),
                          'surface': args.surface, 'text_sha256': sha(data),
                          'scan_complete': True, 'lexical_hits': hits,
                          'semantic_review': 'not-performed', 'release_authorized': False,
                          'dictionary_sha256': sha(dictionary_raw),
                          'coordinate_system': 'raw-source-characters',
                          'hits': hits}, ensure_ascii=False))
        return int(args.require_clean and bool(hits))
    except (GateError, OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
