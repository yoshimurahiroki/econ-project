#!/usr/bin/env bash
set -euo pipefail

CLI_CMD=""

# Antigravity IDE を最優先
for cmd in agy-ide antigravity-ide code cursor code-insiders; do
    if command -v "$cmd" >/dev/null 2>&1; then
        if "$cmd" --help 2>&1 | grep -q -- "--install-extension"; then
            CLI_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$CLI_CMD" ]; then
    echo "IDE CLIが未検出です。agy-ide / antigravity-ide / code / cursor / code-insidersをPATHに追加してください。"
    exit 127
fi

echo "使用するCLI: $CLI_CMD"

EXTENSIONS=()

if command -v jq >/dev/null 2>&1 && [ -f ".devcontainer/devcontainer.json" ]; then
    echo "devcontainer.json から拡張機能リストを抽出しています..."

    PARSED=$(
        jq -r '
          if (.customizations.antigravity.extensions | type == "array") then
            .customizations.antigravity.extensions[]
          elif (.customizations.vscode.extensions | type == "array") then
            .customizations.vscode.extensions[]
          else
            empty
          end
        ' .devcontainer/devcontainer.json 2>/dev/null || true
    )

    if [ -n "$PARSED" ]; then
        mapfile -t EXTENSIONS <<< "$PARSED"
    fi
fi

if [ "${#EXTENSIONS[@]}" -eq 0 ] || [ -z "${EXTENSIONS[0]:-}" ]; then
    echo "既定の拡張機能リストを使用します。"
    EXTENSIONS=(
        "ms-python.python"
        "ms-python.debugpy"
        "ms-toolsai.jupyter"
        "charliermarsh.ruff"
        "REditorSupport.r"
    )
fi

echo "導入済みの拡張機能を取得します。"
INSTALLED=$("$CLI_CMD" --list-extensions 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)

for ext in "${EXTENSIONS[@]}"; do
    [ -z "$ext" ] && continue

    ext_lower=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

    if echo "$INSTALLED" | grep -Fxq "$ext_lower"; then
        echo "導入済み: $ext"
    else
        echo "インストール: $ext"
        "$CLI_CMD" --install-extension "$ext" --force \
            || echo "インストール失敗: $ext"
    fi
done

echo "拡張機能のセットアップ処理を終了しました。"