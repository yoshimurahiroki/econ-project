#!/usr/bin/env bash
# Explicit local IDE selection; paths are relative to this project, never cwd.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI=""; WRITE=0
while (($#)); do
  case "$1" in
    --client)
      (($# >= 2)) || { echo '--client requires a value' >&2; exit 2; }
      [[ -z "$CLI" ]] || { echo 'Select one client' >&2; exit 2; }
      CLI="$2"; shift 2 ;;
    --write) [[ "$WRITE" == 0 ]] || exit 2; WRITE=1; shift ;;
    --help) echo 'Usage: setup_extensions.sh --client code|cursor|code-insiders|agy-ide|antigravity-ide [--write]'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
case "$CLI" in code|cursor|code-insiders|agy-ide|antigravity-ide) ;; *) echo 'Select a supported --client' >&2; exit 2;; esac
# Parse all required inputs before invoking an IDE command. Do not hide malformed JSON.
PARSED=$(python3 - "$ROOT/.devcontainer/devcontainer.json" "$CLI" <<'PY'
import json
from pathlib import Path
import sys
path = Path(sys.argv[1])
if path.exists():
    data = json.loads(path.read_text())
    key = 'antigravity' if sys.argv[2] in ('agy-ide', 'antigravity-ide') else 'vscode'
    extensions = data.get('customizations', {}).get(key, {}).get('extensions', [])
else:
    extensions = []
if not isinstance(extensions, list) or any(not isinstance(x, str) or not x or any(c.isspace() for c in x) or x.startswith('-') for x in extensions):
    raise ValueError('Invalid extension list')
if not extensions:
    extensions = ['ms-python.python', 'ms-python.debugpy', 'ms-toolsai.jupyter', 'charliermarsh.ruff', 'REditorSupport.r']
print('\n'.join(dict.fromkeys(extensions)))
PY
)
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
