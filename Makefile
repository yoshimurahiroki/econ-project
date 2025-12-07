# Makefile for Econometrics Research Environment
.PHONY: help install setup-dev check format test clean \
        build-paper build-slides quarto-html quarto-pdf quarto-reveal \
	r-install r-check jupyter gpu pre-commit update stats \
        clean-paper clean-slides clean-all


THREAD_ENV = OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1

help:
	@echo "Available commands:"
	@echo "  install        - Install dev dependencies with Poetry"
	@echo "  setup-dev      - Setup dev env (Poetry + pre-commit)"
	@echo "  check          - Run ruff + mypy + pytest"
	@echo "  format         - Format with ruff & fix lint"
	@echo "  test           - Run pytest with coverage"
	@echo "  build-paper    - Build LaTeX paper (lualatex + pbibtex)"
	@echo "  build-slides   - Build LaTeX slides (lualatex)"
	@echo "  quarto-html    - Render Quarto project to HTML"
	@echo "  quarto-pdf     - Render Quarto project to PDF"
	@echo "  quarto-reveal  - Render Quarto slides (Reveal.js)"
	@echo "  r-install      - Install R deps from R/requirements.R (if exists)"
	@echo "  r-check        - Run basic R CMD check (quick)"
	@echo "  jupyter        - Start Jupyter *Notebook* if installed (Lab not used)"
	@echo "  gpu            - Print CUDA & PyTorch availability"
	@echo "  clean[-paper|-slides|-all] - Clean artifacts"
	@echo "  stats          - Project statistics"
	@echo "  update         - Poetry + conda env update"
install:
	poetry install --no-root

setup-dev:
	poetry install --no-root
	pre-commit install
	@echo "Development environment setup complete!"

check:
	poetry run ruff check .
	poetry run ruff format --check .
	poetry run mypy .
	$(THREAD_ENV) poetry run pytest -q

format:
	poetry run ruff format .
	poetry run ruff check --fix .

test:
	$(THREAD_ENV) poetry run pytest --verbose --cov=src --cov-report=term-missing

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.log" -delete
	# TeX artifacts
	find . -type f \( -name "*.aux" -o -name "*.bbl" -o -name "*.blg" -o -name "*.out" -o -name "*.toc" -o -name "*.synctex.gz" -o -name "*.run.xml" -o -name "*.fdb_latexmk" -o -name "*.fls" \) -delete
	rm -rf _site _book .quarto .pytest_cache .mypy_cache .ruff_cache

clean-paper:
	rm -f tex/paper/*.aux tex/paper/*.bbl tex/paper/*.blg tex/paper/*.log tex/paper/*.out tex/paper/*.toc tex/paper/*.synctex.gz tex/paper/*.run.xml tex/paper/*.fdb_latexmk tex/paper/*.fls

clean-slides:
	rm -f tex/slides/*.aux tex/slides/*.bbl tex/slides/*.blg tex/slides/*.log tex/slides/*.out tex/slides/*.toc tex/slides/*.synctex.gz tex/slides/*.run.xml tex/slides/*.fdb_latexmk tex/slides/*.fls

clean-all: clean clean-paper clean-slides

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
	quarto render . --to html

quarto-pdf:
	quarto render . --to pdf

quarto-reveal:
	quarto render . --to revealjs

r-install:
	@[ -f R/requirements.R ] && Rscript R/requirements.R || echo "No R/requirements.R"

r-check:
	R -q -e "sessionInfo(); if (requireNamespace('devtools', quietly=TRUE)) devtools::check(document=FALSE, error_on='warning') else message('Install devtools to run full checks')"

jupyter:
	@if command -v jupyter >/dev/null 2>&1; then \
		jupyter notebook --ip=127.0.0.1 --no-browser ; \
	else \
		echo "No Jupyter server installed. Use VS Code's Notebook (ipykernel only)." ; \
	fi

gpu:
	@$(THREAD_ENV) python - <<- 'PY'
	import sys
	try:
	    import torch
	    print("torch.cuda.is_available:", torch.cuda.is_available())
	    print("device:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")
	except Exception as e:
	    print("PyTorch not installed or error:", e)
	PY

pre-commit:
	poetry run pre-commit run --all-files


update:
	@. /home/vscode/miniforge3/etc/profile.d/conda.sh && conda activate econ-env && \
	if command -v mamba >/dev/null 2>&1; then mamba env update -f environment.yml --prune; else conda env update -f environment.yml --prune; fi
	poetry update

stats:
	@echo "=== Project Statistics ==="
	@echo "Python files: $$(find src tests -name '*.py' 2>/dev/null | wc -l)"
	@echo "R files: $$(find R notebooks/r -name '*.r' -o -name '*.R' 2>/dev/null | wc -l)"
	@echo "Jupyter notebooks: $$(find notebooks -name '*.ipynb' 2>/dev/null | wc -l)"
	@echo "LaTeX files: $$(find tex -name '*.tex' 2>/dev/null | wc -l)"
