# Explicit project operations; no automatic verification chain.
.PHONY: help prepare-pixi sync install setup-dev setup-extensions register-kernels setup-r-kernel format lint test clean r-install r-plan build-paper build-slides quarto-html quarto-pdf quarto-reveal

PIXI ?= pixi
PIXI_RUN = $(PIXI) run
THREAD_ENV = OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
R_MAKEVARS_USER ?= $(CURDIR)/scripts/r-makevars
FILE ?=
TEST ?=

help:
	@echo "sync / r-install / r-plan: dependencies"
	@echo "build-paper / build-slides / quarto-*: documents"
	@echo "test TEST=path::node / lint FILE=path / format FILE=path: explicit targets"
	@echo "Project export: python scripts/export_project.py --output /tmp/econ-project"

prepare-pixi:
	sudo mkdir -p .pixi /home/vscode/.cache /home/vscode/.cache/R /home/vscode/.cache/rattler /home/vscode/.cache/rv
	sudo chown vscode:vscode /home/vscode/.cache
	sudo chown -R vscode:vscode .pixi /home/vscode/.cache/R /home/vscode/.cache/rattler /home/vscode/.cache/rv
	sudo chmod u+rwx /home/vscode/.cache
	sudo chmod -R u+rwX .pixi /home/vscode/.cache/R /home/vscode/.cache/rattler /home/vscode/.cache/rv

sync: prepare-pixi
	$(PIXI) install
install: sync
setup-dev: sync
	$(PIXI_RUN) pre-commit install
setup-extensions:
	bash scripts/setup_extensions.sh
register-kernels: sync
	bash .devcontainer/register-kernels.sh
setup-r-kernel: sync r-install
	bash .devcontainer/register-kernels.sh

format:
	@test -n "$(FILE)" || { echo "Specify FILE=path" >&2; exit 2; }
	$(PIXI_RUN) ruff format -- "$(FILE)"
lint:
	@test -n "$(FILE)" || { echo "Specify FILE=path" >&2; exit 2; }
	$(PIXI_RUN) ruff check -- "$(FILE)"
test:
	@test -n "$(TEST)" || { echo "Specify TEST=path::node" >&2; exit 2; }
	$(THREAD_ENV) $(PIXI_RUN) pytest -q -p no:cacheprovider -- "$(TEST)"

r-install: RV_ACTION = sync
r-plan: RV_ACTION = plan
r-install r-plan: prepare-pixi
	$(PIXI_RUN) bash -lc ' \
		set -euo pipefail; \
		export PKG_CONFIG="$$CONDA_PREFIX/bin/pkg-config"; \
		export PKG_CONFIG_PATH="$$CONDA_PREFIX/lib/pkgconfig:$$CONDA_PREFIX/share/pkgconfig:$${PKG_CONFIG_PATH:-}"; \
		export LIBRARY_PATH="$$CONDA_PREFIX/lib:$${LIBRARY_PATH:-}"; \
		export LD_LIBRARY_PATH="$$CONDA_PREFIX/lib:$${LD_LIBRARY_PATH:-}"; \
		export R_MAKEVARS_USER="$(R_MAKEVARS_USER)"; \
		export XML_CONFIG="$$CONDA_PREFIX/bin/xml2-config"; \
		export NANONEXT_LIBS=1; \
		unset NANONEXT_TLS CMAKE_PREFIX_PATH; \
		JAVA_BIN="$$(command -v java)"; \
		export JAVA_HOME="$$(dirname "$$(dirname "$$(readlink -f "$$JAVA_BIN")")")"; \
		export PATH="$$JAVA_HOME/bin:$$PATH"; \
		export LD_LIBRARY_PATH="$$JAVA_HOME/lib/server:$$JAVA_HOME/lib:$$LD_LIBRARY_PATH"; \
		ln -sf libxml2.so.16 "$$CONDA_PREFIX/lib/libxml2.so" 2>/dev/null || true; \
		R CMD javareconf; \
		if [ "$(RV_ACTION)" = sync ] && pgrep -u "$$(id -u)" -x rv >/dev/null; then \
			echo "Another rv process is running." >&2; exit 1; \
		fi; \
		rv $(RV_ACTION) \
	'

build-paper:
	cd tex/paper && \
	lualatex -shell-escape -interaction=nonstopmode ecta_template.tex && \
	pbibtex ecta_template || true && \
	lualatex -shell-escape -interaction=nonstopmode ecta_template.tex && \
	lualatex -shell-escape -interaction=nonstopmode ecta_template.tex
build-slides:
	cd tex/slides && \
	lualatex -shell-escape -interaction=nonstopmode main.tex && \
	pbibtex main || true && \
	lualatex -shell-escape -interaction=nonstopmode main.tex && \
	lualatex -shell-escape -interaction=nonstopmode main.tex
quarto-html:
	$(PIXI_RUN) quarto render . --to html
quarto-pdf:
	$(PIXI_RUN) quarto render . --to pdf
quarto-reveal:
	$(PIXI_RUN) quarto render . --to revealjs

clean:
	rm -rf -- .coverage .mypy_cache .pytest_cache .ruff_cache _site _book .quarto
	find tex -type f \( -name '*.aux' -o -name '*.blg' -o -name '*.log' -o -name '*.out' -o -name '*.toc' -o -name '*.synctex.gz' -o -name '*.run.xml' -o -name '*.fdb_latexmk' -o -name '*.fls' \) -delete
