find_project_root <- function(path = getwd()) {
  path <- normalizePath(path, mustWork = TRUE)
  repeat {
    if (file.exists(file.path(path, "rproject.toml"))) {
      return(path)
    }
    parent <- dirname(path)
    if (identical(parent, path)) {
      stop("Project marker rproject.toml is missing.", call. = FALSE)
    }
    path <- parent
  }
}

project_root <- find_project_root()
rv_library <- character(0)
if (nzchar(Sys.which("rv"))) {
  rv_library <- tryCatch(local({
    previous_directory <- setwd(project_root)
    on.exit(setwd(previous_directory))
    system2("rv", "library", stdout = TRUE)
  }), error = function(e) character(0), warning = function(w) character(0))
}

if (length(rv_library) == 1L && dir.exists(rv_library)) {
  .libPaths(unique(c(rv_library, .libPaths())))
}

pixi_prefix <- file.path(project_root, ".pixi", "envs", "default")
pixi_bin <- file.path(pixi_prefix, "bin")

if (dir.exists(pixi_bin)) {
  path <- strsplit(Sys.getenv("PATH"), .Platform$path.sep, fixed = TRUE)[[1]]
  if (!pixi_bin %in% path) {
    Sys.setenv(PATH = paste(c(pixi_bin, path), collapse = .Platform$path.sep))
  }
  Sys.setenv(QUARTO_PYTHON = file.path(pixi_bin, "python"))
  Sys.setenv(QUARTO_R = file.path(pixi_bin, "Rscript"))
  Sys.setenv(QUARTO_SHARE_PATH = file.path(pixi_prefix, "share", "quarto"))
  Sys.setenv(QUARTO_DENO = file.path(pixi_bin, "deno"))
  Sys.setenv(QUARTO_DENO_DOM = file.path(pixi_prefix, "lib", "deno_dom.so"))
  Sys.setenv(QUARTO_PANDOC = file.path(pixi_bin, "pandoc"))
  Sys.setenv(QUARTO_ESBUILD = file.path(pixi_bin, "esbuild"))
  Sys.setenv(QUARTO_TYPST = file.path(pixi_bin, "typst"))
  Sys.setenv(QUARTO_DART_SASS = file.path(pixi_bin, "sass"))
  Sys.setenv(QUARTO_CONDA_PREFIX = pixi_prefix)
}
