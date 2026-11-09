# Explicit project operations.
.PHONY: help prepare-pixi sync setup-extensions register-kernels format clean r-install r-plan build-paper build-slides quarto-html quarto-pdf quarto-reveal format-r

PIXI ?= pixi
PIXI_RUN = $(PIXI) run
export R_BUILD_MAKEVARS := $(if $(filter undefined,$(origin R_MAKEVARS_USER)),$(CURDIR)/scripts/r-makevars,$(value R_MAKEVARS_USER))
unexport R_MAKEVARS_USER
FILE ?=
# Keep caller-supplied selectors as data, never as shell or Make source.
unexport FILE
export QUALITY_FILE := $(value FILE)
CHECK_FILE = test -n "$$QUALITY_FILE" && test -f "$$QUALITY_FILE" || { echo "Specify FILE=one-existing-file" >&2; exit 2; }; case "$$QUALITY_FILE" in /*) ;; *) QUALITY_FILE="./$$QUALITY_FILE";; esac
QMD ?=
export QUARTO_DOCUMENT := $(value QMD)
unexport QMD
QUARTO_INPUT = case "$$QUARTO_DOCUMENT" in /*|./*|../*) ;; *) QUARTO_DOCUMENT="./$$QUARTO_DOCUMENT" ;; esac
PAPER ?= tex/paper/ecta_template.tex
SLIDES ?= tex/slides/main.tex
export LATEX_PAPER := $(value PAPER)
export LATEX_SLIDES := $(value SLIDES)
unexport PAPER SLIDES
export TEXINPUTS := $(CURDIR)/tex/paper:$(TEXINPUTS)
export BSTINPUTS := $(CURDIR)/tex/paper:$(BSTINPUTS)

help:
	@echo "sync / r-install / r-plan: dependencies"
	@echo "build-paper PAPER=path / build-slides SLIDES=path / quarto-* QMD=path: documents"
	@echo "format FILE=path / format-r FILE=path"
	@echo "Project export: python scripts/export_project.py --task econ-writing --mode compose --output /tmp/econ-writing-new; selection and export: docs/ai/integration.md"

prepare-pixi:
	mkdir -p .pixi

sync: prepare-pixi
	$(PIXI) install
setup-extensions:
	bash scripts/setup_extensions.sh --sync
register-kernels:
	bash .devcontainer/register-kernels.sh

format:
	@$(CHECK_FILE); \
	$(PIXI_RUN) ruff format -- "$$QUALITY_FILE"
format-r:
	@$(CHECK_FILE); \
	$(PIXI_RUN) Rscript -e 'Sys.setenv(R_CACHE_ROOTPATH = tempdir()); f <- Sys.getenv("QUALITY_FILE"); x <- readLines(f, warn = FALSE, encoding = "UTF-8"); y <- as.character(styler::style_text(x, scope = "spaces")); if (anyNA(y) || (length(x) > 0L && length(y) == 0L)) stop("Formatter returned no valid source"); invisible(parse(text = y)); if (!identical(x, y)) writeLines(y, f, useBytes = TRUE)'
r-install: RV_ACTION = sync
r-plan: RV_ACTION = plan
r-install: prepare-pixi
r-install r-plan:
	$(PIXI_RUN) bash -c ' \
		set -euo pipefail; \
		export PKG_CONFIG="$$CONDA_PREFIX/bin/pkg-config"; \
		export PKG_CONFIG_PATH="$$CONDA_PREFIX/lib/pkgconfig:$$CONDA_PREFIX/share/pkgconfig:$${PKG_CONFIG_PATH:-}"; \
		export LIBRARY_PATH="$$CONDA_PREFIX/lib:$${LIBRARY_PATH:-}"; \
		export LD_LIBRARY_PATH="$$CONDA_PREFIX/lib:$${LD_LIBRARY_PATH:-}"; \
		export R_MAKEVARS_USER="$$R_BUILD_MAKEVARS"; \
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
			R CMD javareconf; \
		fi; \
		rv $(RV_ACTION) \
	'

build-paper:
	python3 scripts/build_latex.py -- "$$LATEX_PAPER"
build-slides:
	python3 scripts/build_latex.py -- "$$LATEX_SLIDES"
quarto-html:
	@QUARTO_DOCUMENT="$${QUARTO_DOCUMENT:-.}"; $(QUARTO_INPUT); $(PIXI_RUN) quarto render "$$QUARTO_DOCUMENT" --to html
quarto-pdf:
	@QUARTO_DOCUMENT="$${QUARTO_DOCUMENT:-.}"; $(QUARTO_INPUT); $(PIXI_RUN) quarto render "$$QUARTO_DOCUMENT" --to pdf
quarto-reveal:
	@QUARTO_DOCUMENT="$${QUARTO_DOCUMENT:-.}"; $(QUARTO_INPUT); $(PIXI_RUN) quarto render "$$QUARTO_DOCUMENT" --to revealjs

clean:
	rm -rf -- .mypy_cache .ruff_cache _site _book .quarto
	find tex -type f \( -name '*.aux' -o -name '*.blg' -o -name '*.log' -o -name '*.out' -o -name '*.toc' -o -name '*.synctex.gz' -o -name '*.run.xml' -o -name '*.fdb_latexmk' -o -name '*.fls' \) -delete
