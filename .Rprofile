rv_library <- "/workspaces/econ-project/rv/library/4.5/x86_64/jammy"
pixi_bin <- "/workspaces/econ-project/.pixi/envs/default/bin"

if (dir.exists(rv_library) && !rv_library %in% .libPaths()) {
  .libPaths(c(rv_library, .libPaths()))
}

if (dir.exists(pixi_bin)) {
  path <- strsplit(Sys.getenv("PATH"), .Platform$path.sep, fixed = TRUE)[[1]]
  if (!pixi_bin %in% path) {
    Sys.setenv(PATH = paste(c(pixi_bin, path), collapse = .Platform$path.sep))
  }
  Sys.setenv(QUARTO_PYTHON = file.path(pixi_bin, "python"))
  Sys.setenv(QUARTO_SHARE_PATH = "/workspaces/econ-project/.pixi/envs/default/share/quarto")
  Sys.setenv(QUARTO_DENO = file.path(pixi_bin, "deno"))
  Sys.setenv(QUARTO_DENO_DOM = "/workspaces/econ-project/.pixi/envs/default/lib/deno_dom.so")
  Sys.setenv(QUARTO_PANDOC = file.path(pixi_bin, "pandoc"))
  Sys.setenv(QUARTO_ESBUILD = file.path(pixi_bin, "esbuild"))
  Sys.setenv(QUARTO_TYPST = file.path(pixi_bin, "typst"))
  Sys.setenv(QUARTO_DART_SASS = file.path(pixi_bin, "sass"))
  Sys.setenv(QUARTO_CONDA_PREFIX = "/workspaces/econ-project/.pixi/envs/default")
}
