#!/usr/bin/env bash
set -euo pipefail

cd /workspaces/econ-project

sudo mkdir -p .pixi data /home/vscode/.cache/rattler /home/vscode/.cache/rv
sudo chown -R vscode:vscode .pixi data /home/vscode/.cache/rattler /home/vscode/.cache/rv
sudo chmod -R u+rwX .pixi data /home/vscode/.cache/rattler /home/vscode/.cache/rv

pixi install

mkdir -p .pixi/envs/default/bin/tools/x86_64/deno_dom
ln -sf ../../deno .pixi/envs/default/bin/tools/x86_64/deno
ln -sf ../../pandoc .pixi/envs/default/bin/tools/x86_64/pandoc
ln -sf ../../esbuild .pixi/envs/default/bin/tools/x86_64/esbuild
ln -sf ../../typst .pixi/envs/default/bin/tools/x86_64/typst
ln -sf ../../sass .pixi/envs/default/bin/tools/x86_64/sass
ln -sf ../../../../lib/deno_dom.so .pixi/envs/default/bin/tools/x86_64/deno_dom/libplugin.so

if ! grep -q "quarto-cli-real" .pixi/envs/default/bin/quarto; then
  mv .pixi/envs/default/bin/quarto .pixi/envs/default/bin/quarto-cli-real
fi

tee .pixi/envs/default/bin/quarto >/dev/null <<'EOF'
#!/usr/bin/env bash
cd /workspaces/econ-project
export PATH="/workspaces/econ-project/.pixi/envs/default/bin:$PATH"
export QUARTO_PYTHON="/workspaces/econ-project/.pixi/envs/default/bin/python"
export QUARTO_SHARE_PATH="/workspaces/econ-project/.pixi/envs/default/share/quarto"
export QUARTO_DENO="/workspaces/econ-project/.pixi/envs/default/bin/deno"
export QUARTO_DENO_DOM="/workspaces/econ-project/.pixi/envs/default/lib/deno_dom.so"
export QUARTO_PANDOC="/workspaces/econ-project/.pixi/envs/default/bin/pandoc"
export QUARTO_ESBUILD="/workspaces/econ-project/.pixi/envs/default/bin/esbuild"
export QUARTO_TYPST="/workspaces/econ-project/.pixi/envs/default/bin/typst"
export QUARTO_DART_SASS="/workspaces/econ-project/.pixi/envs/default/bin/sass"
export QUARTO_CONDA_PREFIX="/workspaces/econ-project/.pixi/envs/default"

if [ "${1:-}" = "render" ]; then
  has_format=0
  for arg in "$@"; do
    case "$arg" in
      --to|--to=*|-t|-t=*) has_format=1 ;;
    esac
  done

  if [ "$has_format" -eq 0 ]; then
    for arg in "$@"; do
      case "$arg" in
        *.qmd)
          if grep -Eq '^[[:space:]]*pdf:[[:space:]]*$|^[[:space:]]*format:[[:space:]]*pdf[[:space:]]*$' "$arg"; then
            exec /workspaces/econ-project/.pixi/envs/default/bin/quarto-cli-real "$@" --to pdf
          fi
          ;;
      esac
    done
  fi
fi

exec /workspaces/econ-project/.pixi/envs/default/bin/quarto-cli-real "$@"
EOF
chmod 0755 .pixi/envs/default/bin/quarto

sudo tee /usr/local/bin/quarto >/dev/null <<'EOF'
#!/usr/bin/env bash
exec /workspaces/econ-project/.pixi/envs/default/bin/quarto "$@"
EOF
sudo chmod 0755 /usr/local/bin/quarto

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

sed -i '/\/workspaces\/econ-project\/\.pixi\/envs\/default\/bin:\$PATH/d' ~/.bashrc
grep -q "usr/local/bin:.*\.pixi/envs/default/bin" ~/.bashrc || \
  echo "export PATH=/usr/local/bin:/workspaces/econ-project/.pixi/envs/default/bin:\$PATH" >> ~/.bashrc
