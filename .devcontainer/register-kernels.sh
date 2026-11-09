#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
mode="${1:---all}"
if (( $# > 1 )) || [[ "$mode" != --all && "$mode" != --python && "$mode" != --r ]]; then
  echo 'Usage: register-kernels.sh [--all|--python|--r]' >&2
  exit 2
fi

if [ ! -x .pixi/envs/default/bin/python ]; then
  echo "Pixi Python environment is missing: .pixi/envs/default/bin/python" >&2
  echo "Run 'pixi install' before registering kernels." >&2
  exit 1
fi

export PATH="$PWD/.pixi/envs/default/bin:$PATH"
# User kernels share one Jupyter directory across checkouts. Bind each name to
# this environment so registering another project preserves its interpreter.
kernel_prefix="econ-$(printf '%s' "$PWD" | sha256sum | cut -c1-12)"
project_name="${PWD##*/}"
export ERS_R_KERNEL_NAME="$kernel_prefix-r"
export ERS_R_KERNEL_DISPLAY="R ($project_name)"

if [[ "$mode" != --r ]]; then
  .pixi/envs/default/bin/python -m ipykernel install \
    --user \
    --name "$kernel_prefix-python" \
    --display-name "Python ($project_name)"
fi

if [[ "$mode" != --python ]]; then
  if [ ! -x .pixi/envs/default/bin/Rscript ]; then
    echo "R kernel registration failed: Pixi Rscript is missing." >&2
    exit 1
  fi
  if ! command -v jupyter >/dev/null 2>&1; then
    echo "R kernel registration failed: Jupyter command is missing." >&2
    exit 1
  fi
  if ! .pixi/envs/default/bin/Rscript -e "IRkernel::installspec(name = Sys.getenv('ERS_R_KERNEL_NAME'), displayname = Sys.getenv('ERS_R_KERNEL_DISPLAY'), user = TRUE)"; then
    echo "R kernel registration failed." >&2
    exit 1
  fi
fi
