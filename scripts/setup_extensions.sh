#!/usr/bin/env bash
set -euo pipefail

echo "Looking for IDE CLI tool..."

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
    echo "エラー: IDE CLI が見つかりません。"
    echo "agy-ide / antigravity-ide / code / cursor / code-insiders のいずれも利用できません。"
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
    echo "警告: devcontainer.json から拡張機能を取得できませんでした。ハードコードされたリストを使用します。"
    EXTENSIONS=(
        "ms-python.python"
        "ms-python.debugpy"
        "ms-toolsai.jupyter"
        "charliermarsh.ruff"
        "REditorSupport.r"
    )
fi

echo "合計 ${#EXTENSIONS[@]} 個の拡張機能をチェックします..."

echo "現在の拡張機能をチェックしています..."
INSTALLED=$("$CLI_CMD" --list-extensions 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)

for ext in "${EXTENSIONS[@]}"; do
    [ -z "$ext" ] && continue

    ext_lower=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

    if echo "$INSTALLED" | grep -Fxq "$ext_lower"; then
        echo "✅ 既済: $ext"
    else
        echo "⬇️  インストール: $ext"
        "$CLI_CMD" --install-extension "$ext" --force \
            || echo "⚠️  失敗: $ext のインストールに失敗しました"
    fi
done

echo "🎉 拡張機能のセットアップが完了しました。"