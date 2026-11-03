#!/usr/bin/env bash
# Explicit local IDE selection; paths are relative to this project, never cwd.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI=""; WRITE=0; SYNC=0
while (($#)); do
  case "$1" in
    --client)
      (($# >= 2)) || { echo '--client requires a value' >&2; exit 2; }
      [[ -z "$CLI" ]] || { echo 'Select one client' >&2; exit 2; }
      CLI="$2"; shift 2 ;;
    --write) [[ "$WRITE" == 0 ]] || exit 2; WRITE=1; shift ;;
    --sync) [[ "$SYNC" == 0 ]] || exit 2; SYNC=1; shift ;;
    --help) echo 'Usage: setup_extensions.sh --sync | --client code|cursor|code-insiders|agy-ide|antigravity-ide [--write]'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
if [[ "$SYNC" == 1 ]]; then
  [[ -z "$CLI" && "$WRITE" == 0 ]] || { echo '--sync cannot be combined with --client or --write' >&2; exit 2; }
else
  case "$CLI" in code|cursor|code-insiders|agy-ide|antigravity-ide) ;; *) echo 'Select a supported --client' >&2; exit 2;; esac
fi
# The workspace recommendations are the single authoring source for both hosts.
PARSED=$(python3 - "$ROOT/.vscode/extensions.json" "$ROOT/.devcontainer/devcontainer.json" "$SYNC" <<'PYCODE'
import json
from pathlib import Path
import sys
source, target = map(Path, sys.argv[1:3])
extensions = json.loads(source.read_text())['recommendations']
if (not isinstance(extensions, list) or not extensions or
        any(not isinstance(x, str) or not x or any(c.isspace() for c in x) or x.startswith('-') for x in extensions) or
        len(set(extensions)) != len(extensions)):
    raise ValueError('Invalid extension list')
if sys.argv[3] == '1':
    data = json.loads(target.read_text())
    hosts = data.setdefault('customizations', {})
    for key in ('vscode', 'antigravity'):
        hosts.setdefault(key, {})['extensions'] = extensions
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print('\n'.join(extensions))
PYCODE
)
if [[ "$SYNC" == 1 ]]; then
  echo 'Updated devcontainer extensions from .vscode/extensions.json.'
  exit 0
fi
mapfile -t EXTENSIONS <<< "$PARSED"
if [[ "$WRITE" == 0 ]]; then
  printf 'Would ensure installed with %s:\n' "$CLI"
  printf '%s\n' "${EXTENSIONS[@]}"
  exit 0
fi
command -v "$CLI" >/dev/null || { echo "Missing IDE CLI: $CLI" >&2; exit 127; }
INSTALLED=$("$CLI" --list-extensions | tr '[:upper:]' '[:lower:]')
FAILED=()
for ext in "${EXTENSIONS[@]}"; do
  if grep -Fxiq -- "$ext" <<< "$INSTALLED"; then
    echo "Already installed: $ext"
  elif ! "$CLI" --install-extension "$ext" --force; then
    FAILED+=("$ext")
  fi
done
if ((${#FAILED[@]})); then
  printf 'Failed extension: %s\n' "${FAILED[@]}" >&2
  exit 1
fi
echo 'Selected extensions are installed.'
