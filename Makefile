# Explicit project operations.
.PHONY: help prepare-pixi sync install setup-dev setup-extensions register-kernels setup-r-kernel format lint test clean r-install r-plan build-paper build-slides quarto-html quarto-pdf quarto-reveal typecheck format-check lint-r format-r

PIXI ?= pixi
PIXI_RUN = $(PIXI) run
THREAD_ENV = OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
R_MAKEVARS_USER ?= $(CURDIR)/scripts/r-makevars
FILE ?=
TEST ?=
# Keep caller-supplied selectors as data, never as shell or Make source.
unexport FILE TEST
export QUALITY_FILE := $(value FILE)
export QUALITY_TEST := $(value TEST)
CHECK_FILE = test -n "$$QUALITY_FILE" && test -f "$$QUALITY_FILE" || { echo "Specify FILE=one-existing-file" >&2; exit 2; }; case "$$QUALITY_FILE" in /*) ;; *) QUALITY_FILE="./$$QUALITY_FILE";; esac
QMD ?=
PAPER ?= tex/paper/ecta_template.tex
SLIDES ?= tex/slides/main.tex

help:
	@echo "sync / r-install / r-plan: dependencies"
	@echo "build-paper PAPER=path / build-slides SLIDES=path / quarto-* QMD=path: documents"
	@echo "lint FILE=path / format FILE=path / typecheck FILE=path / format-check FILE=path"
	@echo "lint-r FILE=path / format-r FILE=path"
	@echo "Project export: python scripts/export_project.py --task econ-paper --output /tmp/econ-paper-new; profiles and all-method export: docs/ai/integration.md"

prepare-pixi:
	mkdir -p .pixi

sync: prepare-pixi
	$(PIXI) install
install: sync
setup-dev: sync
setup-extensions:
	bash scripts/setup_extensions.sh
register-kernels:
	bash .devcontainer/register-kernels.sh
setup-r-kernel: register-kernels

format:
	@$(CHECK_FILE); \
	$(PIXI_RUN) ruff format -- "$$QUALITY_FILE"
lint:
	@$(CHECK_FILE); \
	$(PIXI_RUN) ruff check -- "$$QUALITY_FILE"
typecheck:
	@$(CHECK_FILE); \
	$(PIXI_RUN) mypy -- "$$QUALITY_FILE"
format-check:
	@$(CHECK_FILE); \
	$(PIXI_RUN) ruff format --check -- "$$QUALITY_FILE"
lint-r:
	@$(CHECK_FILE); \
	$(PIXI_RUN) Rscript --vanilla -e 'f <- Sys.getenv("QUALITY_FILE"); invisible(parse(file = f)); x <- lintr::lint(f, linters = list(lintr::equals_na_linter(), lintr::seq_linter(), lintr::vector_logic_linter()), cache = FALSE); print(x); if (length(x)) quit(status = 1)'
format-r:
	@$(CHECK_FILE); \
	$(PIXI_RUN) Rscript --vanilla -e 'Sys.setenv(R_CACHE_ROOTPATH = tempdir()); f <- Sys.getenv("QUALITY_FILE"); x <- readLines(f, warn = FALSE, encoding = "UTF-8"); y <- as.character(styler::style_text(x, scope = "spaces")); if (anyNA(y) || (length(x) > 0L && length(y) == 0L)) stop("Formatter returned no valid source"); invisible(parse(text = y)); if (!identical(x, y)) writeLines(y, f, useBytes = TRUE)'
test:
	@test -n "$$QUALITY_TEST" || { echo "Specify TEST=path::node" >&2; exit 2; }; \
	$(THREAD_ENV) $(PIXI_RUN) pytest -q -p no:cacheprovider -- "$$QUALITY_TEST"

r-install: RV_ACTION = sync
r-plan: RV_ACTION = plan
r-install: prepare-pixi
r-install r-plan:
	$(PIXI_RUN) bash -lc ' \
		set -euo pipefail; \
		export PKG_CONFIG="$$CONDA_PREFIX/bin/pkg-config"; \
		export PKG_CONFIG_PATH="$$CONDA_PREFIX/lib/pkgconfig:$$CONDA_PREFIX/share/pkgconfig:$${PKG_CONFIG_PATH:-}"; \
		export LIBRARY_PATH="$$CONDA_PREFIX/lib:$${LIBRARY_PATH:-}"; \
		export LD_LIBRARY_PATH="$$CONDA_PREFIX/lib:$${LD_LIBRARY_PATH:-}"; \
		export R_MAKEVARS_USER="$(R_MAKEVARS_USER)"; \
		export RUSTUP_TOOLCHAIN="$${RUSTUP_TOOLCHAIN:-1.96.1}"; \
		export XML_CONFIG="$$CONDA_PREFIX/bin/xml2-config"; \
		export NANONEXT_LIBS=1; \
		unset NANONEXT_TLS CMAKE_PREFIX_PATH; \
		JAVA_BIN="$$(command -v java)"; \
		export JAVA_HOME="$$(dirname "$$(dirname "$$(readlink -f "$$JAVA_BIN")")")"; \
		export PATH="$$JAVA_HOME/bin:$$PATH"; \
		export LD_LIBRARY_PATH="$$JAVA_HOME/lib/server:$$JAVA_HOME/lib:$$LD_LIBRARY_PATH"; \
		if [ "$(RV_ACTION)" = sync ]; then \
			if pgrep -u "$$(id -u)" -x rv >/dev/null; then \
				echo "Another rv process is running." >&2; exit 1; \
			fi; \
			ln -sf libxml2.so.16 "$$CONDA_PREFIX/lib/libxml2.so" 2>/dev/null || true; \
			R CMD javareconf; \
		fi; \
		rv $(RV_ACTION) \
	'

build-paper:
	python3 scripts/build_latex.py -- '$(subst ','"'"',$(PAPER))'
build-slides:
	python3 scripts/build_latex.py -- '$(subst ','"'"',$(SLIDES))'
quarto-html:
	$(PIXI_RUN) quarto render "$(if $(strip $(QMD)),$(QMD),.)" --to html
quarto-pdf:
	$(PIXI_RUN) quarto render "$(if $(strip $(QMD)),$(QMD),.)" --to pdf
quarto-reveal:
	$(PIXI_RUN) quarto render "$(if $(strip $(QMD)),$(QMD),.)" --to revealjs

clean:
	rm -rf -- .coverage .mypy_cache .pytest_cache .ruff_cache _site _book .quarto
	find tex -type f \( -name '*.aux' -o -name '*.blg' -o -name '*.log' -o -name '*.out' -o -name '*.toc' -o -name '*.synctex.gz' -o -name '*.run.xml' -o -name '*.fdb_latexmk' -o -name '*.fls' \) -delete
