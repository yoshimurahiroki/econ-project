#!/usr/bin/env bash
set -euo pipefail

cd /workspaces/econ-project

sudo mkdir -p .pixi data /home/vscode/.cache/rattler /home/vscode/.cache/rv
sudo chown -R vscode:vscode .pixi data /home/vscode/.cache/rattler /home/vscode/.cache/rv
sudo chmod -R u+rwX .pixi data /home/vscode/.cache/rattler /home/vscode/.cache/rv

pixi install

# Register the Python kernel immediately after Pixi succeeds so it is available
# even if the much larger R package sync fails later.
bash .devcontainer/register-kernels.sh

if [ "${INSTALL_R_PACKAGES:-1}" = "1" ]; then
  if make r-install; then
    bash .devcontainer/register-kernels.sh
  else
    echo "R package installation failed; Python kernel remains registered." >&2
  fi
fi

if [ "${INSTALL_PLAYWRIGHT_BROWSERS:-0}" = "1" ]; then
  pixi run playwright install --with-deps chromium
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  pixi run bash -lc "pre-commit install"
fi

bash scripts/setup_ai_skills.sh > /tmp/setup_ai_skills.log 2>&1 || true
bash scripts/setup_ide_mcp.sh > /tmp/setup_ide_mcp.log 2>&1 || true
pixi run python scripts/sync_rules.py > /tmp/sync_rules.log 2>&1 || true

grep -q "\.pixi/envs/default/bin" ~/.bashrc || \
  echo "export PATH=/workspaces/econ-project/.pixi/envs/default/bin:\$PATH" >> ~/.bashrc
