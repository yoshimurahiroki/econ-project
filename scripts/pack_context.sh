#!/bin/bash
# Pack Context Script
# Wraps repomix (and gitingest as fallback) to generate a unified context file for LLMs.

set -e

OUTPUT_DIR="docs/issue"
OUTPUT_FILE="$OUTPUT_DIR/repo_context.txt"

mkdir -p "$OUTPUT_DIR"

echo "Packing repository context..."

if command -v repomix >/dev/null 2>&1 || npx --no-install repomix --version >/dev/null 2>&1; then
    echo "Using Repomix..."
    # repomix automatically respects repomix.config.json in the current directory
    npx repomix --output "$OUTPUT_FILE"
    echo "Context successfully packed to $OUTPUT_FILE using Repomix."
elif command -v gitingest >/dev/null 2>&1 || pixi run gitingest --version >/dev/null 2>&1; then
    echo "Repomix not found, falling back to Gitingest..."
    if command -v pixi >/dev/null 2>&1; then
        pixi run gitingest . -o "$OUTPUT_FILE"
    else
        gitingest . -o "$OUTPUT_FILE"
    fi
    echo "Context successfully packed to $OUTPUT_FILE using Gitingest."
else
    echo "Error: Neither repomix nor gitingest found."
    exit 1
fi
