#!/usr/bin/env bash
# Optional full-repository context; selected instructions use export_project.py.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$#" -gt 1 ]; then
  echo "Usage: bash scripts/pack_context.sh [/absolute/path/to/fresh-context.txt]" >&2
  exit 2
fi
OUTPUT_FILE="$(realpath -m -- "${1:-${TMPDIR:-/tmp}/econ-context-$$.txt}")"
case "$OUTPUT_FILE" in
  "$PROJECT_ROOT"|"$PROJECT_ROOT"/*)
    echo "Choose an output file outside the repository." >&2
    exit 2 ;;
esac
if [ -e "$OUTPUT_FILE" ]; then
  echo "Choose a fresh output file." >&2
  exit 2
fi

cd "$PROJECT_ROOT"
mkdir -p "$(dirname "$OUTPUT_FILE")"
if command -v repomix >/dev/null 2>&1; then
  exec repomix --output "$OUTPUT_FILE"
elif command -v npx >/dev/null 2>&1; then
  exec npx --no-install repomix --output "$OUTPUT_FILE"
fi
echo "Install Repomix explicitly before packing repository context." >&2
exit 1
