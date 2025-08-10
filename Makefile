# Makefile for Econometrics Research Environment
# 便利なコマンドを定義

.PHONY: help install setup-dev check format test clean build-paper build-slides jupyter

# デフォルトターゲット
help:
	@echo "Available commands:"
	@echo "  install     - Install dependencies with Poetry"
	@echo "  setup-dev   - Setup development environment"
	@echo "  check       - Run all quality checks"
	@echo "  format      - Format code with ruff"
	@echo "  test        - Run tests with pytest"
	@echo "  clean       - Clean build artifacts"
	@echo "  build-paper - Build LaTeX paper"
	@echo "  build-slides - Build LaTeX slides"
	@echo "  jupyter     - Start Jupyter Lab"

# 依存関係インストール
install:
	poetry install --no-root

# 開発環境セットアップ
setup-dev:
	poetry install --no-root
	pre-commit install
	@echo "Development environment setup complete!"

# 品質チェック
check:
	poetry run ruff check .
	poetry run mypy .
	poetry run pytest --verbose

# コードフォーマット
format:
	poetry run ruff format .
	poetry run ruff check --fix .

# テスト実行
test:
	poetry run pytest --verbose --cov=src

# クリーンアップ
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.log" -delete
	find . -name "*.aux" -delete
	find . -name "*.bbl" -delete
	find . -name "*.blg" -delete
	find . -name "*.out" -delete
	find . -name "*.toc" -delete
	find . -name "*.synctex.gz" -delete

# LaTeX論文ビルド
build-paper:
	cd tex/paper && latexmk -lualatex -shell-escape -interaction=nonstopmode main.tex

# LaTeXスライドビルド  
build-slides:
	cd tex/slides && latexmk -lualatex -shell-escape -interaction=nonstopmode talk.tex

# Jupyter Lab起動
jupyter:
	poetry run jupyter lab --ip=0.0.0.0 --no-browser --allow-root

# 論文クリーンアップ
clean-paper:
	cd tex/paper && latexmk -C

# スライドクリーンアップ
clean-slides:
	cd tex/slides && latexmk -C

# 全てクリーンアップ
clean-all: clean clean-paper clean-slides

# プリコミットフックの実行
pre-commit:
	poetry run pre-commit run --all-files

# 依存関係の更新
update:
	poetry update
	conda env update -f environment.yml

# プロジェクト統計
stats:
	@echo "=== Project Statistics ==="
	@echo "Python files: $(shell find src tests -name '*.py' | wc -l)"
	@echo "R files: $(shell find R notebooks/r -name '*.r' -o -name '*.R' | wc -l)"  
	@echo "Jupyter notebooks: $(shell find notebooks -name '*.ipynb' | wc -l)"
	@echo "LaTeX files: $(shell find tex -name '*.tex' | wc -l)"
	@echo "Total lines of Python code:"
	@find src tests -name '*.py' -exec wc -l {} + | tail -1
