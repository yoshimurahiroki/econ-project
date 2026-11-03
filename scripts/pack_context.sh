#!/usr/bin/env bash
# Local-only scoped text pack. No network, external collectors, or npm execution.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 - "$ROOT" "$@" <<'PY'
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
parser = argparse.ArgumentParser(description='Pack explicitly selected project text paths, excluding private runtime files.')
parser.add_argument('--output')
parser.add_argument('--map', action='store_true', help='Return a scoped structural lookup as JSON')
parser.add_argument('--root', help='Project root for map mode; defaults to the helper project')
parser.add_argument('--query', help='Exact identifier to locate in map mode')
parser.add_argument('--known-owner', help='Skip mapping when the implementation location is already known')
parser.add_argument('--limit', type=int, default=80, help='Maximum returned map locations (1..200)')
parser.add_argument('paths', nargs='+')
args = parser.parse_args(sys.argv[2:])
if args.root:
    if not args.map:
        parser.error('--root requires --map')
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        parser.error('--root must identify a project directory')
try:
    if args.map:
        if args.output or not args.query or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', args.query) or not 1 <= args.limit <= 200:
            raise ValueError('Map requires an identifier query, a limit in 1..200, and no output file')
    elif not args.output or args.query or args.known_owner or args.limit != 80:
        raise ValueError('Packing requires an output; map options require --map')
    denied_parts = {'.git', '.agents', '.codex', '.cursor', '.vscode', '.windsurf', '.gemini', '.claude', '.devcontainer', 'secrets', 'state', 'node_modules', '__pycache__', '.venv', 'venv', '.ssh', '.aws', '.azure', '.gcloud'}
    denied_names = {'mcp.json', '.mcp.json', 'credentials.json', 'token.json', 'tokens.json', 'id_rsa', 'id_ed25519', '.netrc', '.npmrc', '.pypirc', '.git-credentials'}
    def allowed(path):
        relative = path.relative_to(root)
        return not any(part.lower().startswith(('credentials.', 'credential.', 'tokens.', 'token.', 'secrets.')) for part in relative.parts) and not any(part in denied_parts or part.startswith('.env') for part in relative.parts) and path.name not in denied_names and path.suffix.lower() not in {'.pem', '.key', '.p12', '.pfx', '.sqlite', '.db'}
    if args.map:
        if args.known_owner:
            print(json.dumps({'status': 'known-owner', 'owner': args.known_owner, 'locations': [], 'truncated': False}))
            sys.exit(0)
        scopes = []
        for name in args.paths:
            candidate = root / name
            if (not candidate.exists() or not candidate.resolve().is_relative_to(root)
                    or any(p.is_symlink() for p in (candidate, *candidate.parents) if p != root.parent)
                    or not allowed(candidate) or not allowed(candidate.resolve())):
                raise ValueError('Invalid or excluded scoped input: ' + name)
            scopes.append(candidate.relative_to(root))
        command = ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', *map(str, scopes)]
        result = subprocess.run(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode:
            raise ValueError('Map requires a Git working tree')
        paths = sorted({root / name for name in result.stdout.decode('utf-8').split('\0') if name})
        eligible = [p for p in paths if p.suffix.lower() in {'.py', '.r', '.jl', '.ts', '.tsx'}
                    and p.is_file() and allowed(p) and p.resolve().is_relative_to(root)
                    and allowed(p.resolve()) and not any(q.is_symlink() for q in (p, *p.parents) if q != root.parent)]
        locations, versions, issues = [], {}, []
        max_files, max_bytes = 400, 256 * 1024
        for path in eligible[:max_files]:
            rel = str(path.relative_to(root))
            if path.stat().st_size > max_bytes:
                issues.append({'path': rel, 'reason': 'oversize-or-binary'})
                continue
            data = path.read_bytes()
            if len(data) > max_bytes or b'\0' in data:
                issues.append({'path': rel, 'reason': 'oversize-or-binary'})
                continue
            try:
                source = data.decode('utf-8')
            except UnicodeDecodeError:
                issues.append({'path': rel, 'reason': 'non-utf8'})
                continue
            version = hashlib.sha256(data).hexdigest()
            versions[path] = version
            test = path.name.startswith('test_') or path.name.endswith(('_test.py', '.test.ts', '.test.tsx', '.spec.ts', '.spec.tsx')) or 'tests' in path.parts
            found = set()
            if path.suffix.lower() == '.py':
                try:
                    tree = ast.parse(source, filename=rel)
                except SyntaxError:
                    issues.append({'path': rel, 'reason': 'invalid-python'})
                    continue
                for node in ast.walk(tree):
                    kind = None
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == args.query:
                        kind = 'definition'
                    elif isinstance(node, (ast.Import, ast.ImportFrom)) and any(a.name.split('.')[-1] == args.query or a.asname == args.query for a in node.names):
                        kind = 'import'
                    elif isinstance(node, ast.Call) and ((isinstance(node.func, ast.Name) and node.func.id == args.query) or (isinstance(node.func, ast.Attribute) and node.func.attr == args.query)):
                        kind = 'test-call' if test else 'call'
                    if kind:
                        found.add((node.lineno, kind, 'ast'))
            else:
                identifier = re.escape(args.query)
                for number, line in enumerate(source.splitlines(), 1):
                    if not re.search(r'(?<![\w])' + identifier + r'(?![\w])', line):
                        continue
                    kind = ('definition' if re.search(r'(?:\b(?:function|class|def|const|let|var)\s+' + identifier + r'\b|\b' + identifier + r'\s*(?:<-|=)\s*function\s*\()', line)
                            else 'import' if re.search(r'\b(?:import|using|from|require|source|library)\b', line)
                            else 'test-reference' if test else 'reference')
                    found.add((number, kind, 'lexical'))
            locations.extend({'path': rel, 'line': line, 'kind': kind, 'method': method, 'sha256': version}
                             for line, kind, method in sorted(found))
        for path, version in versions.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != version:
                raise ValueError('File changed while mapping: ' + str(path.relative_to(root)))
        print(json.dumps({'status': 'ok', 'query': args.query, 'locations': locations[:args.limit],
                          'files_scanned': min(len(eligible), max_files), 'issues': issues,
                          'truncated': bool(issues) or len(locations) > args.limit or len(eligible) > max_files}, ensure_ascii=False))
        sys.exit(0)
    out = Path(args.output).expanduser().absolute()
    if out.resolve().is_relative_to(root):
        raise ValueError('Output must be outside the project')
    if out.exists() or out.is_symlink():
        raise ValueError('Output must be a fresh file')
    files = set()
    for name in args.paths:
        candidate = root / name
        if not candidate.exists() or candidate.is_symlink() or not candidate.resolve().is_relative_to(root):
            raise ValueError('Invalid scoped input: ' + name)
        if not allowed(candidate) or not allowed(candidate.resolve()):
            raise ValueError('Excluded scoped input: ' + name)
        for path in ([candidate] if candidate.is_file() else candidate.rglob('*')):
            if path.is_file() and not path.is_symlink() and allowed(path) and path.resolve().is_relative_to(root) and allowed(path.resolve()):
                files.add(path)
    if not files:
        raise ValueError('No eligible scoped files')
    chunks = []
    for path in sorted(files):
        data = path.read_bytes()
        if b'\0' in data:
            raise ValueError('Binary scoped input: ' + str(path.relative_to(root)))
        chunks.append('## ' + str(path.relative_to(root)) + '\n\n' + data.decode('utf-8') + '\n')
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as handle:
        handle.write('\n'.join(chunks))
    print(f'Packed {len(files)} explicitly scoped files into {out}')
except (OSError, ValueError, UnicodeError) as error:
    print(str(error), file=sys.stderr)
    sys.exit(1)
PY
