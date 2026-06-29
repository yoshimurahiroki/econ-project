# Minimal commands for the econ-project research environment.

.PHONY: help prepare-pixi sync install setup-dev setup-extensions register-kernels setup-r-kernel check format test clean \
	build-paper build-slides quarto-html quarto-pdf quarto-reveal \
	r-install r-plan

PIXI ?= pixi
PIXI_RUN = $(PIXI) run
THREAD_ENV = OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
R_MAKEVARS_USER ?= $(CURDIR)/scripts/r-makevars

help:
	@echo "Available commands:"
	@echo "  prepare-pixi   - Ensure Pixi and rv cache directories are writable"
	@echo "  sync           - Install Python dependencies with pixi"
	@echo "  setup-dev      - Sync dependencies and install pre-commit hooks"
	@echo "  setup-extensions - Install IDE extensions from devcontainer.json or fallback list"
	@echo "  register-kernels - Register Jupyter kernels for the Pixi Python/R environments"
	@echo "  setup-r-kernel - Install R packages, then register Python and R kernels"
	@echo "  format         - Format and autofix Python code"
	@echo "  test           - Validate AI surface and run pytest when tests exist"
	@echo "  check          - Run lint, format check, mypy, and tests"
	@echo "  clean          - Remove generated caches and build artifacts"
	@echo "  r-install      - Sync R dependencies with rv"
	@echo "  build-paper    - Build the LaTeX paper"
	@echo "  build-slides   - Build the LaTeX slides"
	@echo "  quarto-*       - Render Quarto outputs"


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
	$(PIXI_RUN) ruff format .
	$(PIXI_RUN) ruff check --fix .

test:
	PYTHONDONTWRITEBYTECODE=1 $(PIXI_RUN) python scripts/sync_rules.py
	@if find tests -name 'test_*.py' -o -name '*_test.py' 2>/dev/null | grep -q .; then \
		$(THREAD_ENV) $(PIXI_RUN) pytest -q; \
	else \
		echo "No pytest tests found; existing tests are reset."; \
	fi

check:
	$(PIXI_RUN) ruff check .
	$(PIXI_RUN) ruff format --check .
	$(PIXI_RUN) mypy scripts/sync_rules.py
	$(MAKE) test

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find tex -type f \( -name "*.aux" -o -name "*.bbl" -o -name "*.blg" -o -name "*.log" -o -name "*.out" -o -name "*.toc" -o -name "*.synctex.gz" -o -name "*.run.xml" -o -name "*.fdb_latexmk" -o -name "*.fls" \) -delete
	rm -rf .agent_state .coverage .mypy_cache .pytest_cache .ruff_cache _site _book .quarto

r-install: prepare-pixi
	$(PIXI_RUN) bash -lc ' \
		set -euo pipefail; \
		export PKG_CONFIG="$$CONDA_PREFIX/bin/pkg-config"; \
		export PKG_CONFIG_PATH="$$CONDA_PREFIX/lib/pkgconfig:$$CONDA_PREFIX/share/pkgconfig:$${PKG_CONFIG_PATH:-}"; \
		export LIBRARY_PATH="$$CONDA_PREFIX/lib:$${LIBRARY_PATH:-}"; \
		export LD_LIBRARY_PATH="$$CONDA_PREFIX/lib:$${LD_LIBRARY_PATH:-}"; \
		export R_MAKEVARS_USER="$(R_MAKEVARS_USER)"; \
		export XML_CONFIG="$$CONDA_PREFIX/bin/xml2-config"; \
		export NANONEXT_LIBS=1; \
		unset NANONEXT_TLS; \
		unset CMAKE_PREFIX_PATH; \
		JAVA_BIN="$$(command -v java)"; \
		export JAVA_HOME="$$(dirname "$$(dirname "$$(readlink -f "$$JAVA_BIN")")")"; \
		export PATH="$$JAVA_HOME/bin:$$PATH"; \
		export LD_LIBRARY_PATH="$$JAVA_HOME/lib/server:$$JAVA_HOME/lib:$$CONDA_PREFIX/lib:$${LD_LIBRARY_PATH:-}"; \
		ln -sf libxml2.so.16 "$$CONDA_PREFIX/lib/libxml2.so" 2>/dev/null || true; \
		echo "Checking pixi/conda-forge paths..."; \
		pkg-config --cflags librsvg-2.0; \
		pkg-config --libs librsvg-2.0; \
		pkg-config --modversion libxml-2.0; \
		test -f "$$CONDA_PREFIX/include/glpk.h"; \
		test -f "$$CONDA_PREFIX/lib/libglpk.so" || test -f "$$CONDA_PREFIX/lib/libglpk.a"; \
		test -f "$$CONDA_PREFIX/lib/liblzma.so" || test -f "$$CONDA_PREFIX/lib/liblzma.so.5"; \
		echo "Checking Java..."; \
		echo "JAVA_HOME=$$JAVA_HOME"; \
		java -version; \
		R CMD javareconf; \
		if pgrep -u "$$(id -u)" -x rv >/dev/null; then \
			echo "Another rv process is running; wait for it to finish before r-install." >&2; \
			exit 1; \
		fi; \
		find rv/library -type d -name "__rv__staging" -prune -exec rm -rf {} + 2>/dev/null || true; \
		rv sync \
	'

r-plan: prepare-pixi
	$(PIXI_RUN) bash -lc ' \
		set -euo pipefail; \
		export PKG_CONFIG="$$CONDA_PREFIX/bin/pkg-config"; \
		export PKG_CONFIG_PATH="$$CONDA_PREFIX/lib/pkgconfig:$$CONDA_PREFIX/share/pkgconfig:$${PKG_CONFIG_PATH:-}"; \
		export LIBRARY_PATH="$$CONDA_PREFIX/lib:$${LIBRARY_PATH:-}"; \
		export LD_LIBRARY_PATH="$$CONDA_PREFIX/lib:$${LD_LIBRARY_PATH:-}"; \
		export R_MAKEVARS_USER="$(R_MAKEVARS_USER)"; \
		export XML_CONFIG="$$CONDA_PREFIX/bin/xml2-config"; \
		export NANONEXT_LIBS=1; \
		unset NANONEXT_TLS; \
		unset CMAKE_PREFIX_PATH; \
		JAVA_BIN="$$(command -v java)"; \
		export JAVA_HOME="$$(dirname "$$(dirname "$$(readlink -f "$$JAVA_BIN")")")"; \
		export PATH="$$JAVA_HOME/bin:$$PATH"; \
		export LD_LIBRARY_PATH="$$JAVA_HOME/lib/server:$$JAVA_HOME/lib:$$CONDA_PREFIX/lib:$${LD_LIBRARY_PATH:-}"; \
		ln -sf libxml2.so.16 "$$CONDA_PREFIX/lib/libxml2.so" 2>/dev/null || true; \
		R CMD javareconf; \
		rv plan \
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
