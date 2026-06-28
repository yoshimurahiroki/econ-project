#!/usr/bin/env bash
set -euo pipefail

cd /workspaces/econ-project


sudo mkdir -p .pixi /home/vscode/.cache /home/vscode/.cache/R /home/vscode/.cache/rattler /home/vscode/.cache/rv
sudo chown vscode:vscode /home/vscode/.cache
sudo chown -R vscode:vscode .pixi /home/vscode/.cache/R /home/vscode/.cache/rattler /home/vscode/.cache/rv
sudo chmod u+rwx /home/vscode/.cache
sudo chmod -R u+rwX .pixi /home/vscode/.cache/R /home/vscode/.cache/rattler /home/vscode/.cache/rv

if [ ! -x .pixi/envs/default/bin/python ]; then
  echo "Pixi Python environment is missing: .pixi/envs/default/bin/python" >&2
  echo "Run 'pixi install' before registering kernels." >&2
  exit 1
fi

export PATH="/workspaces/econ-project/.pixi/envs/default/bin:$PATH"

.pixi/envs/default/bin/python -m ipykernel install \
  --user \
  --name econ-env \
  --display-name "Python (econ-env)"

if [ ! -x .pixi/envs/default/bin/Rscript ]; then
  echo "Pixi R environment is not available yet; skipped R kernel registration." >&2
  exit 0
fi

if ! command -v jupyter >/dev/null 2>&1; then
  echo "Jupyter command is not available yet; skipped R kernel registration." >&2
  exit 0
fi

if ! .pixi/envs/default/bin/Rscript -e "stopifnot(requireNamespace('IRkernel', quietly = TRUE))"; then
  echo "IRkernel is not available yet; skipped R kernel registration." >&2
  exit 0
fi

if ! .pixi/envs/default/bin/Rscript -e "IRkernel::installspec(name = 'ir', displayname = 'R (IRkernel)', user = TRUE)"; then
  echo "R kernel registration failed; Python kernel remains registered." >&2
  exit 0
fi
