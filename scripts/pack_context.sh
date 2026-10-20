#!/usr/bin/env bash
# Local-only scoped text pack. No network, external collectors, or npm execution.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 - "$ROOT" "$@" <<'PY'
import argparse
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
parser = argparse.ArgumentParser(description='Pack explicitly selected project text paths, excluding private runtime files.')
parser.add_argument('--output', required=True)
parser.add_argument('paths', nargs='+')
args = parser.parse_args(sys.argv[2:])
out = Path(args.output).expanduser().absolute()
try:
    if out.resolve().is_relative_to(root):
        raise ValueError('Output must be outside the project')
    if out.exists() or out.is_symlink():
        raise ValueError('Output must be a fresh file')
    denied_parts = {'.git', '.agents', '.codex', '.cursor', '.vscode', '.windsurf', '.gemini', '.claude', '.devcontainer', 'secrets', 'state', 'node_modules', '__pycache__', '.venv', 'venv', '.ssh', '.aws', '.azure', '.gcloud'}
    denied_names = {'credentials.json', 'token.json', 'tokens.json', 'id_rsa', 'id_ed25519', '.netrc', '.npmrc', '.pypirc', '.git-credentials'}
    def allowed(path):
        relative = path.relative_to(root)
        return not any(part.lower().startswith(('credentials.', 'credential.', 'tokens.', 'token.', 'secrets.')) for part in relative.parts) and not any(part in denied_parts or part.startswith('.env') for part in relative.parts) and path.name not in denied_names and path.suffix.lower() not in {'.pem', '.key', '.p12', '.pfx', '.sqlite', '.db'}
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
