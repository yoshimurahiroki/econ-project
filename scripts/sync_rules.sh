#!/bin/bash
# Wrapper to run the rule synchronization python script
# Usage: bash scripts/sync_rules.sh

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
python "$SCRIPT_DIR/sync_rules.py"
