# 経済学研究フルスタック開発環境（WSL2 + Docker + VS Code Dev Containers）

無料で“最高の”Python / R / TeX 体験を得るための開発環境です。Windows 上の WSL2(Ubuntu) + Docker コンテナ + VS Code Dev Containers を前提に、以下をワンストップで提供します。

- Python: conda/mamba + Poetry 管理、型チェック(mypy)、Linter/Formatter(ruff)、pytest
- R: r-base + tidyverse、IRkernel（Jupyter から R 実行）、languageserver
- TeX: texlive-full（LuaLaTeX ベース）、VS Code LaTeX Workshop
- Jupyter: Python/R カーネル登録済み、127.0.0.1 バインドで安全
- Notion 連携: 公式 JS SDK（@notionhq/client）で成果物メモと文献DBの同期（CI連携可）
- Quarto: VS Code 拡張による編集体験（CLI は任意）

## 前提条件（Windows 無料ツール）
1. Windows 10/11 + WSL2（Ubuntu 22.04 推奨）
2. Docker Desktop（WSL2 連携を有効化）
3. Visual Studio Code + Dev Containers 拡張

## はじめかた（VS Code から）
1. 本リポジトリをクローン
2. VS Code で「Reopen in Container」を実行（.devcontainer が自動でビルド）
3. 初回セットアップ後、以下を実行
	 - 開発セットアップ（プリコミットなど）
		 - make setup-dev
	 - テスト/型/Lint の一括チェック
		 - make check

コンテナは `.devcontainer/Dockerfile` により以下を自動構築します。
- Miniforge(mamba) + conda 環境 `econ-env` を `environment.yml` から作成
- Poetry を導入、Python インタプリタは conda 環境を既定に設定
- Jupyter カーネル登録（Python econ-env, R IRkernel）
- VS Code 拡張（Python/R/LaTeX/Quarto など）を自動インストール

データディレクトリは Docker ボリューム `econ_data` として `/workspaces/econ-project/data` にマウントされ、ホストに依存せずに永続化されます。

## コマンド一覧（Makefile）
- 品質管理
	- make check      # ruff + mypy + pytest
	- make format     # ruff format & fix
	- make test       # pytest（カバレッジ付）
- Jupyter
	- make jupyter    # Jupyter Lab（127.0.0.1 バインド）
- LaTeX（LuaLaTeX + BibTeX）
	- make build-paper   # tex/paper/ecta_template.tex をビルド
	- make build-slides  # tex/slides/main.tex をビルド
	- make clean[-paper|-slides|-all]  # 生成物削除
- Notion（JS SDK）
	- make notion-install   # scripts の Node 依存インストール
	- make notion-sync      # 成果物状況（PDF等）を Notion ページに追記
	- make notion-sync-db   # Bib/CSL-JSON を Notion DB にアップサート

## パッケージ管理の原則
- システム/基盤（Python/R/Jupyter/TeX/Nodeなど）
	- conda/mamba（environment.yml）で一括管理・再現性確保
- Python プロジェクト依存（アプリ/ライブラリ）
	- Poetry（pyproject.toml）で厳密管理（dev 依存は group dev）
- R パッケージ
	- conda 経由で入るものは environment.yml に記載
	- 足りなければ R 内で install.packages() を使用（必要に応じて固定）
- Jupyter 内での `!pip install`/`install.packages()` は極力避け、定義ファイルに反映

## Notion 連携（無料・公式 SDK）
Node（scripts ディレクトリ限定）で公式 SDK を使用します。

1) 成果物ステータスのメモ追記
- スクリプト: scripts/notion-sync.js
- 使い方:
	- export NOTION_TOKEN=...  # Notion Integration のシークレット
	- export NOTION_PAGE_ID=...  # 追記先ページ（またはブロック）ID（URL末尾 32桁）
	- make notion-install
	- make notion-sync

2) 論文メタデータ（Paperpile エクスポート）→ Notion DB 同期
- スクリプト: scripts/notion-sync-db.js
- 入力: data/papers/library.bib（または CSL-JSON）
- Notion DB プロパティ例: Title, Authors, Year, Venue, Tags, DOI(url), URL(url), Abstract, Code(url), PDF(files), Updated(date)
- 照合順序: DOI → URL → Key（差分がある場合のみ更新）
- 使い方:
	- export NOTION_TOKEN=...
	- export NOTION_DB_ID=...
	- make notion-install
	- make notion-sync-db

3) CI 連携（GitHub Actions）
- .github/workflows/paperpile-to-notion.yml
- data/papers/*.bib|*.json|*.csljson の変更をトリガに DB 同期
- リポジトリ Secrets に NOTION_TOKEN / NOTION_DB_ID を設定

セキュリティ注意: `.env.example` を参照し、`.env` にシークレットを保存しないでください（.gitignore 済）。VS Code タスク/Make へ渡す場合は端末で `export` して実行してください。

## 開発体験のポイント（無料）
- VS Code 拡張（自動導入）
	- Python: Pylance, Black/Isort, Ruff, pytest、Mypy
	- R: R extension, R LSP, R Debugger、languageserver（postCreate で自動導入）
	- LaTeX: LaTeX Workshop, LaTeX Utilities
	- Quarto: Quarto 拡張（編集体験向上）
	- そのほか: YAML/TOML、dotenv、Makefile ツール等
- Jupyter: 127.0.0.1 バインドでローカルフォワード前提の安全運用
- TeX: texlive-full 同梱でローカル追加インストール不要

## トラブルシュート
- コンテナが重い/ビルドが長い: texlive-full は大型です。必要に応じて軽量化可。
- Jupyter に R カーネルが出ない: コンテナ再作成（IRkernel 登録は Dockerfile で実施）。
- Notion API 429（レート制限）: 再試行まで待機、バッチサイズ調整を検討。

## 付録：主要ファイル
- .devcontainer/Dockerfile: 基盤（Ubuntu + mamba + Poetry + TeX + R）
- environment.yml: conda 環境（Python/R/Jupyter/ツール）
- pyproject.toml: Poetry（Python 依存/ツール）
- Makefile: よく使うコマンド
- scripts/: Notion 連携ツール（Node 依存をここに隔離）
- notebooks/: 分析ノート（Python/R）
- tex/: 論文・スライド（LuaLaTeX）

---
この構成で、WSL2 上でも Docker コンテナ内で再現性と快適さを両立できます。必要になれば、Quarto CLI の追加、R パッケージの固定化、CIの拡張（テスト/静的解析/Notion 同期）もすぐ拡張可能です。
