#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
project_root="$PWD"

# Trust the workspace while preserving the user's existing trust entries.
if ! git config --global --get-all safe.directory | grep -Fx -- "$project_root" >/dev/null; then
  git config --global --add safe.directory "$project_root"
fi

# Initialize mounted-volume ownership once; later Make and kernel operations run as the user.
sudo mkdir -p .pixi data .resources /home/vscode/.cache/R /home/vscode/.cache/rattler /home/vscode/.cache/rv
sudo chown vscode:vscode /home/vscode/.cache .pixi data .resources /home/vscode/.cache/R /home/vscode/.cache/rattler /home/vscode/.cache/rv
sudo chmod u+rwX /home/vscode/.cache .pixi data .resources /home/vscode/.cache/R /home/vscode/.cache/rattler /home/vscode/.cache/rv

make sync

# Install project lifecycle hooks for Codex.
PATH="$PWD/.pixi/envs/default/bin:$PATH" bash scripts/setup_ide_mcp.sh --write --client codex --codex-hooks

if [ "${INSTALL_R_PACKAGES:-1}" = "1" ]; then
  make r-install
fi

# Register kernels after the requested R dependency installation succeeds.
bash .devcontainer/register-kernels.sh

if [ "${INSTALL_PLAYWRIGHT_BROWSERS:-0}" = "1" ]; then
  pixi run python -m playwright install --with-deps chromium
fi
