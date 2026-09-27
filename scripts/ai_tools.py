#!/usr/bin/env python3
"""Check, measure and export a minimal research context using the standard library."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
ROOT = Path(__file__).resolve().parents[1]
STYLE = 'econ-assertive'
TRIGGER = 'Use `econ-assertive` by default'
LINK = re.compile('\\[[^\\]]*\\]\\(([^)\\s]+)\\)')

def safe(root: Path, name: str) -> Path:
    if not name or ':' in name or '\\' in name or PurePosixPath(name).is_absolute():
        raise ValueError('Unsafe path')
    if any((p in {'', '.', '..', '.git'} for p in name.split('/'))):
        raise ValueError('Unsafe path')
    result = root.resolve()
    for part in name.split('/'):
        result /= part
        if result.is_symlink():
            raise ValueError('Symlink path')
    return result

def read(root: Path, name: str) -> str:
    return safe(root, name).read_text(encoding='utf-8')

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def measure(text: str) -> dict:
    normalized = text.replace('\r\n', '\n')
    return {'utf8_bytes': len(text.encode()), 'characters_lf': len(normalized), 'characters_crlf': len(normalized.replace('\n', '\r\n'))}

def names(root: Path) -> list[str]:
    value = json.loads(read(root, 'docs/ai/skills.json'))
    items = value['skills']
    if value.get('schema') != 1 or not isinstance(items, list) or (not items):
        raise ValueError('Invalid registry')
    if any((not isinstance(n, str) or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', n) for n in items)):
        raise ValueError('Invalid skill name')
    if any((len(n) > 64 for n in items)):
        raise ValueError('Skill name exceeds 64 characters')
    if len(items) != len(set(items)) or STYLE not in items:
        raise ValueError('Duplicate skills or missing default style')
    return items

def metadata(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0] != '---':
        raise ValueError('Missing front matter')
    end = lines.index('---', 1)
    data = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(':')
        value = value.strip()
        if not sep or key not in {'name', 'description'} or key in data or (not value) or (': ' in value):
            raise ValueError('Invalid front matter')
        data[key] = value
    if set(data) != {'name', 'description'} or len(data['description']) > 160:
        raise ValueError('Invalid skill metadata')
    return data

def check(root: Path) -> list[str]:
    errors = []
    try:
        registry = names(root)
        policy = read(root, '.cursorrules')
        if STYLE not in policy or len(policy.encode()) > 3000:
            errors.append('Policy style trigger or size')
        project = read(root, 'docs/ai/project_instructions.txt')
        if 'ECON_ASSERTIVE.md' not in project or measure(project)['characters_crlf'] > 8000:
            errors.append('Project style trigger or size')
        style = read(root, f'.agents/skills/{STYLE}/SKILL.md')
        if any((token not in style for token in ['Stage 1:', 'Stage 2:', 'all three tests', 'DELETE', 'REWRITE', 'KEEP'])):
            errors.append('Two-stage content gate is incomplete')
        discovery_size = sum((len((n + metadata(read(root, f'.agents/skills/{n}/SKILL.md'))['description']).encode()) for n in registry))
        if discovery_size > 1800:
            errors.append('Discovery metadata exceeds 1800 bytes')
        actual = {p.parent.name for p in (root / '.agents/skills').glob('*/SKILL.md')}
        if actual != set(registry):
            errors.append('Skill file set differs')
        for name in registry:
            location = f'.agents/skills/{name}/SKILL.md'
            text = read(root, location)
            if metadata(text)['name'] != name or len(text.encode()) > 3000:
                errors.append(f'Skill metadata or size: {name}')
            if name != STYLE and TRIGGER not in text:
                errors.append(f'Default style trigger: {name}')
            for link in LINK.findall(text):
                if '://' not in link and (not link.startswith('#')):
                    if not safe(root / f'.agents/skills/{name}', link).is_file():
                        errors.append(f'Broken reference: {location}: {link}')
        for path in (root / '.agents/skills').rglob('*'):
            if path.is_symlink():
                errors.append('Symlink in skill tree')
        read(root, 'scripts/style_guard.py')
        for filename in ['AGENTS.md', 'CLAUDE.md', 'CODEX.md']:
            path = safe(root, filename)
            if path.exists() and '.cursorrules' not in path.read_text():
                errors.append(f'Policy pointer: {filename}')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return errors

def budget(root: Path, encoding: str | None=None) -> dict:
    registry = names(root)
    pointer = '# econ-project AI rules\n\nRead and follow `.cursorrules`; it is the single authoritative policy.\nDo not duplicate or extend its rules in this file.\n'
    discovery = '\n'.join((f"{n}: {metadata(read(root, f'.agents/skills/{n}/SKILL.md'))['description']} (.agents/skills/{n}/SKILL.md)" for n in registry)) + '\n'
    texts = {'policy': read(root, '.cursorrules'), 'discovery': discovery, 'default_style': read(root, f'.agents/skills/{STYLE}/SKILL.md')}
    texts['startup_basis'] = pointer + texts['policy'] + discovery
    texts['prose_startup_basis'] = texts['startup_basis'] + texts['default_style']
    result: dict = {key: measure(value) for key, value in texts.items()}
    if encoding:
        tokenizer = importlib.import_module('tiktoken').get_encoding(encoding)
        for key, text in texts.items():
            result[key]['tokens'] = len(tokenizer.encode(text, disallowed_special=()))
        result['encoding'] = encoding
    result['basis'] = 'One pointer, policy and serialized discovery; prose also loads the default style. Task/reference/platform/tool content is separate.'
    return result

def revision(root: Path) -> dict:
    if not (root / '.git').exists():
        return {'kind': 'file_layer', 'observed_commit': None}

    def git(*args: str) -> str:
        return subprocess.run(['git', '-C', str(root), *args], check=True, text=True, capture_output=True, timeout=15).stdout.strip()
    return {'kind': 'checkout', 'observed_commit': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'), 'dirty': bool(git('status', '--porcelain'))}

def export(root: Path, target: Path, profile: str, selection: list[str] | None=None) -> dict:
    errors = check(root)
    if errors:
        raise ValueError('; '.join(errors))
    if target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Export outside the source tree')
    if target.exists() or any((p.is_symlink() for p in [target.absolute(), *target.absolute().parents])):
        raise ValueError('Destination exists or traverses a symlink')
    registry = names(root)
    if profile not in {'bridge', 'standalone'}:
        raise ValueError('Invalid profile')
    mapping = {'.cursorrules': 'REPO_POLICY.md', 'scripts/style_guard.py': 'STYLE_GUARD.py'}
    if profile == 'bridge':
        if selection:
            raise ValueError('Bridge retains existing method owners')
        selected = [STYLE]
        mapping.update({'docs/ai/project_bridge.txt': 'BRIDGE_INSTRUCTIONS.txt', 'docs/ai/repo_context.md': 'REPO_CONTEXT.md', '.agents/skills/econ-workflow/references/descriptive-model.md': 'RESEARCH_WORKFLOW.md'})
    else:
        selected = registry.copy() if selection is None else selection.copy()
        if not selected or len(selected) != len(set(selected)) or set(selected) - set(registry):
            raise ValueError('Invalid selection')
        if STYLE not in selected:
            selected.append(STYLE)
        mapping['docs/ai/project_instructions.txt'] = 'PROJECT_INSTRUCTIONS.txt'
    for name in selected:
        prefix = name.upper().replace('-', '_')
        folder = f'.agents/skills/{name}'
        mapping[f'{folder}/SKILL.md'] = f'{prefix}.md'
        for ref in sorted(safe(root, f'{folder}/references').glob('*.md')):
            mapping[ref.relative_to(root).as_posix()] = f"{prefix}__{ref.stem.upper().replace('-', '_')}.md"
    if len(set(mapping.values())) != len(mapping):
        raise ValueError('Export name collision')
    contents = {}
    source_hashes = {}
    for source, output in mapping.items():
        data = safe(root, source).read_bytes()
        source_hashes[source] = sha(data)
        text = data.decode()
        for link in LINK.findall(text):
            path = str(PurePosixPath(source).parent / link)
            if path in mapping:
                text = text.replace(f']({link})', f']({mapping[path]})')
        if source.endswith('/econ-assertive/SKILL.md'):
            text = text.replace('python scripts/style_guard.py', 'python STYLE_GUARD.py')
        contents[output] = text.encode()
    if profile == 'standalone':
        lines = ['# Economics task index', '', 'Use ECON_ASSERTIVE.md by default with one matching task skill. Read references for actual dependencies.', '']
        for name in selected:
            source = f'.agents/skills/{name}/SKILL.md'
            lines.append(f"- [{name}]({mapping[source]}): {metadata(read(root, source))['description']}")
        contents['ECON_INDEX.md'] = ('\n'.join(lines) + '\n').encode()
    manifest = {'schema': 1, 'profile': profile, 'default_style': STYLE, 'skills': selected, 'source': revision(root), 'source_sha256': source_hashes, 'files': {n: sha(data) for n, data in sorted(contents.items())}}
    target.mkdir(parents=True)
    for name, data in contents.items():
        safe(target, name).write_bytes(data)
    (target / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    verify(target)
    return manifest

def verify(target: Path) -> dict:
    manifest = json.loads(read(target, 'MANIFEST.json'))
    files = manifest['files']
    if manifest.get('schema') != 1 or not isinstance(files, dict) or (not files):
        raise ValueError('Invalid manifest')
    for name, expected in files.items():
        if sha(safe(target, name).read_bytes()) != expected:
            raise ValueError(f'Hash mismatch: {name}')
        if name.endswith('.md'):
            for link in LINK.findall(read(target, name)):
                if '://' not in link and (not link.startswith('#')):
                    safe(target, link).read_bytes()
    actual = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
    if actual != set(files) | {'MANIFEST.json'}:
        raise ValueError('Export file set differs')
    return {'verified_files': len(files), 'profile': manifest['profile']}

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check')
    b = commands.add_parser('budget')
    b.add_argument('--encoding')
    e = commands.add_parser('export')
    e.add_argument('--output', type=Path, required=True)
    e.add_argument('--profile', choices=['bridge', 'standalone'], default='standalone')
    e.add_argument('--skills', nargs='+')
    v = commands.add_parser('verify')
    v.add_argument('--path', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'check':
        errors = check(args.root)
        print(json.dumps({'passed': not errors, 'errors': errors}, indent=2))
        return int(bool(errors))
    if args.command == 'budget':
        result = budget(args.root, args.encoding)
    elif args.command == 'export':
        result = export(args.root, args.output, args.profile, args.skills)
    else:
        result = verify(args.path)
    print(json.dumps(result, indent=2))
    return 0
if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, ImportError, subprocess.SubprocessError) as exc:
        print(f'Configuration error: {exc}', file=sys.stderr)
        raise SystemExit(2)
