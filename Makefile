# Makefile for Econometrics Research Environment
.PHONY: help install setup-dev check format test clean build-paper build-slides jupyter \
	# r-install/r-check removed (no R) quarto-html quarto-pdf quarto-reveal gpu \
        clean-paper clean-slides clean-all pre-commit update stats notion-sync
 .PHONY: notion-install notion-sync notion-sync-db

help:
	@echo "Available commands:"
	@echo "  install        - Install dependencies with Poetry"
	@echo "  setup-dev      - Setup dev env (Poetry + pre-commit)"
	@echo "  check          - Run ruff + mypy + pytest"
	@echo "  format         - Format with ruff & fix lint"
	@echo "  test           - Run pytest with coverage"
	@echo "  build-paper    - Build LaTeX paper (lualatex + pbibtex)"
	@echo "  build-slides   - Build LaTeX slides"
	@echo "  quarto-html    - Render Quarto site/notebook to HTML"
	@echo "  quarto-pdf     - Render Quarto to PDF"
	@echo "  quarto-reveal  - Render Quarto slides (Reveal.js)"
	@echo "  r-install      - Install R deps from R/requirements.R (if exists)"
	@echo "  r-check        - Run basic R CMD check (quick)"
	@echo "  jupyter        - Start Jupyter Lab (127.0.0.1)"
	@echo "  gpu            - Print CUDA & PyTorch availability"
	@echo "  notion-sync    - Sync artifacts to Notion (official API, Node SDK)"
	@echo "  clean[-paper|-slides|-all] - Clean artifacts"
	@echo "  stats          - Project statistics"
	@echo "  update         - Poetry + conda env update"
	@echo "  drive-ocr      - Run Drive→OCR→Notion pipeline (Node)"

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
	poetry run pytest --verbose

format:
	poetry run ruff format .
	poetry run ruff check --fix .

test:
	poetry run pytest --verbose --cov=src --cov-report=term-missing

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.log" -delete
	find . -name "*.aux" -delete -o -name "*.bbl" -o -name "*.blg" -o -name "*.out" -o -name "*.toc" -o -name "*.synctex.gz" -delete
	rm -rf _site _book .quarto .pytest_cache .mypy_cache .ruff_cache

build-paper:
	cd tex/paper && \
	lualatex -shell-escape -interaction=nonstopmode ecta_template.tex && \
	pbibtex ecta_template && \
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
	poetry run jupyter lab --ip=127.0.0.1 --no-browser

gpu:
	@python - <<'PY'\nimport torch, sys\nprint('torch.cuda.is_available:', torch.cuda.is_available())\nprint('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')\nPY

pre-commit:
	poetry run pre-commit run --all-files

update:
	poetry update
	conda env update -f environment.yml

stats:
	@echo "=== Project Statistics ==="
	@echo "Python files: $(shell find src tests -name '*.py' 2>/dev/null | wc -l)"
	@echo "R files: $(shell find R notebooks/r -name '*.r' -o -name '*.R' 2>/dev/null | wc -l)"
	@echo "Jupyter notebooks: $(shell find notebooks -name '*.ipynb' 2>/dev/null | wc -l)"
	@echo "LaTeX files: $(shell find tex -name '*.tex' 2>/dev/null | wc -l)"

notion-install:
	@cd scripts && npm ci

notion-sync-db:
	@cd scripts && npm ci --silent
	@NOTION_TOKEN=$${NOTION_TOKEN} NOTION_DB_ID=$${NOTION_DB_ID} BIB_SOURCE=$${BIB_SOURCE:-data/papers/library.bib} node notion-sync-db.js

drive-ocr:
	@cd scripts && npm ci --silent
	@DRIVE_FOLDER_ID=$${DRIVE_FOLDER_ID} \
	GOOGLE_API_KEY=$${GOOGLE_API_KEY} \
	NOTION_TOKEN=$${NOTION_TOKEN} \
	NOTION_DB_ID=$${NOTION_DB_ID} \
	DEFAULT_TAGS=$${DEFAULT_TAGS} \
	CHUNK_SIZE=$${CHUNK_SIZE:-1000} \
	ENABLE_SQLITE=$${ENABLE_SQLITE:-false} \
	VECTOR_DB_PATH=$${VECTOR_DB_PATH:-vector.db} \
	TESS_LANG=$${TESS_LANG:-eng} \
	TESS_PSM=$${TESS_PSM:-1} \
	TESS_OEM=$${TESS_OEM:-1} \
	TESS_DPI=$${TESS_DPI:-300} \
	TESS_EXTRA_ARGS=$${TESS_EXTRA_ARGS} \
	ENABLE_EMBEDDINGS=$${ENABLE_EMBEDDINGS:-false} \
	EMBEDDING_MODEL=$${EMBEDDING_MODEL:-Xenova/all-MiniLM-L6-v2} \
# removed legacy drive OCR script
