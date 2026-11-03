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
bin_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
prefix="$(dirname -- "$bin_dir")"
export PATH="$bin_dir:$PATH"
export QUARTO_PYTHON="$bin_dir/python"
export QUARTO_SHARE_PATH="$prefix/share/quarto"
export QUARTO_DENO="$bin_dir/deno"
export QUARTO_DENO_DOM="$prefix/lib/deno_dom.so"
export QUARTO_PANDOC="$bin_dir/pandoc"
export QUARTO_ESBUILD="$bin_dir/esbuild"
export QUARTO_TYPST="$bin_dir/typst"
export QUARTO_DART_SASS="$bin_dir/sass"
export QUARTO_CONDA_PREFIX="$prefix"

project_root="$PWD"
while [ "$project_root" != "/" ] && [ ! -f "$project_root/tex/paper/fonts.latex" ]; do
  project_root="$(dirname "$project_root")"
done
if [ -f "$project_root/tex/paper/fonts.latex" ]; then
  export TEXINPUTS="$project_root/tex/paper:${TEXINPUTS:-}"
  export BSTINPUTS="$project_root/tex/paper:${BSTINPUTS:-}"
fi

exec "$bin_dir/quarto-cli-real" "$@"
EOF
chmod 0755 .pixi/envs/default/bin/quarto

if [ "${INSTALL_R_PACKAGES:-1}" = "1" ]; then
  make r-install
fi

# Register kernels after the requested R dependency installation succeeds.
bash .devcontainer/register-kernels.sh

if [ "${INSTALL_PLAYWRIGHT_BROWSERS:-0}" = "1" ]; then
  pixi run playwright install --with-deps chromium
fi

# Record this workspace's Pixi bin once for interactive shells.
printf -v pixi_bin_quoted '%q' "$project_root/.pixi/envs/default/bin"
path_line="export PATH=$pixi_bin_quoted:\$PATH"
grep -Fxq -- "$path_line" ~/.bashrc || printf '%s\n' "$path_line" >> ~/.bashrc
sed -i '/^export LANG=ja_JP\.UTF-8$/d; /^export LC_ALL=ja_JP\.UTF-8$/d' ~/.bashrc
printf '%s\n' 'export LANG=ja_JP.UTF-8' 'export LC_ALL=ja_JP.UTF-8' >> ~/.bashrc
