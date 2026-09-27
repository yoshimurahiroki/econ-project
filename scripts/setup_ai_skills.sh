#!/usr/bin/env bash
# Native research skills are bundled; external repositories are optional references.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python "$script_dir/sync_rules.py"
