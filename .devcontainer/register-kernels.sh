#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

if [ ! -x .pixi/envs/default/bin/python ]; then
  echo "Pixi Python environment is missing: .pixi/envs/default/bin/python" >&2
  echo "Run 'pixi install' before registering kernels." >&2
  exit 1
fi

export PATH="$PWD/.pixi/envs/default/bin:$PATH"

.pixi/envs/default/bin/python -m ipykernel install \
  --user \
  --name econ-env \
  --display-name "Python (econ-env)"

if [ ! -x .pixi/envs/default/bin/Rscript ]; then
  echo "R kernel registration failed: Pixi Rscript is missing." >&2
  exit 1
fi

if ! command -v jupyter >/dev/null 2>&1; then
  echo "R kernel registration failed: Jupyter command is missing." >&2
  exit 1
fi

if ! .pixi/envs/default/bin/Rscript -e "stopifnot(requireNamespace('IRkernel', quietly = TRUE))"; then
  echo "R kernel registration failed: IRkernel is missing." >&2
  exit 1
fi

if ! .pixi/envs/default/bin/Rscript -e "IRkernel::installspec(name = 'ir', displayname = 'R (IRkernel)', user = TRUE)"; then
  echo "R kernel registration failed." >&2
  exit 1
fi
