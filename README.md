# econ-project — 計量経済学研究環境 / Econometrics Research Environment

このリポジトリは、計量経済学の実証研究のための統合開発環境です。Python、R、LaTeX、Quartoを組み合わせた再現可能な研究ワークフローを提供します。

This repository provides an integrated development environment for empirical research in econometrics. It offers a reproducible research workflow combining Python, R, LaTeX, and Quarto.

## 主な機能 / Features

- **計量経済学パッケージ / Econometric Packages**: 
  - Python: linearmodels, pyfixest, DoubleML, EconML, PyBLP, statsmodels, csdid, rdrobust など
  - R: tidyverse, data.table, fixest, その他R-essentials
- **データ分析 / Data Analysis**: pandas, polars, scikit-learn, PyTorch対応
- **可視化 / Visualization**: matplotlib, seaborn, plotnine（ggplot2スタイル）
- **文書作成 / Documentation**: 
  - LaTeX（日本語対応：LuaLaTeX + pBibTeX）
  - Quarto（HTML、PDF、Reveal.jsスライド）
- **開発ツール / Development Tools**: 
  - pre-commit、ruff、mypy、pytest
  - GitHub Actions（CI/CD、Notion連携）
- **Webスクレイピング / Web Scraping**: Scrapy、Playwright
- **時系列予測 / Time Series Forecasting**: nixtla、statsforecast

## セットアップ / Setup

### 推奨方法：Dev Container（VS Code + Docker）

再現可能な環境を簡単に構築できます：

1. VS CodeとDockerをインストール
2. このリポジトリをクローン
3. VS Codeで開き、"Reopen in Container"を選択

For a reproducible environment:

1. Install VS Code and Docker
2. Clone this repository
3. Open in VS Code and select "Reopen in Container"

### ローカルインストール / Local Installation

```bash
# Conda環境の作成
conda env create -f environment.yml
conda activate econ-env

# Poetryで依存関係をインストール
make install

# 開発環境のセットアップ（pre-commitフックを含む）
make setup-dev
```

## 使い方 / Usage

### Makefileコマンド / Makefile Commands

プロジェクトには便利なMakefileコマンドが用意されています：

```bash
make help          # 利用可能なコマンド一覧を表示
make install       # Poetryで依存関係をインストール
make setup-dev     # 開発環境をセットアップ（pre-commit含む）
make check         # コードチェック（ruff、mypy、pytest）
make format        # コードフォーマット
make test          # テスト実行（カバレッジ付き）
make build-paper   # LaTeX論文をビルド（tex/paper/）
make build-slides  # LaTeXスライドをビルド（tex/slides/）
make jupyter       # Jupyter Notebookを起動
make clean         # 一時ファイルを削除
```

### プロジェクト構成 / Project Structure

```
econ-project/
├── data/              # データファイル（.gitignoreで除外推奨）
├── Notebook/          # Jupyter Notebooks
├── scripts/           # Node.jsスクリプト（Notion連携など）
├── tex/
│   ├── paper/        # 論文用LaTeXファイル
│   └── slides/       # スライド用LaTeXファイル
├── pyproject.toml    # Python依存関係（Poetry）
├── environment.yml   # Conda環境定義
├── Makefile          # ビルド・テストコマンド
└── .devcontainer/    # Dev Container設定
```

### Python環境の使用例 / Python Usage Examples

#### 1. パネルデータ分析 / Panel Data Analysis

```python
import pandas as pd
from linearmodels import PanelOLS
from pyfixest.estimation import feols

# pyfixestで固定効果推定
df = pd.read_csv('data/panel_data.csv')
result = feols('y ~ x1 + x2 | firm + year', data=df, vcov='cluster')
print(result.summary())
```

#### 2. 因果推論 / Causal Inference

```python
from econml.dml import DML
from sklearn.ensemble import RandomForestRegressor

# Double Machine Learning
dml = DML(model_y=RandomForestRegressor(), model_t=RandomForestRegressor())
dml.fit(Y, T, X=X, W=W)
treatment_effects = dml.effect(X)
```

#### 3. RDデザイン / Regression Discontinuity

```python
import rdrobust

# RD推定
rd = rdrobust.rdrobust(y, x, c=0)
print(rd.summary())
```

### LaTeX文書のビルド / Building LaTeX Documents

#### 論文 / Paper

```bash
make build-paper
# 出力: tex/paper/ecta_template.pdf
```

論文テンプレートは日本語対応（LuaLaTeX + LuaTeX-ja）で、Econometrica形式をベースにしています。

The paper template supports Japanese (LuaLaTeX + LuaTeX-ja) and is based on the Econometrica format.

#### スライド / Slides

```bash
make build-slides
# 出力: tex/slides/main.pdf
```

Beamerのmetropolisテーマを使用したスライドテンプレートです。

Slides template using Beamer's metropolis theme.

### Quarto文書の作成 / Creating Quarto Documents

```bash
make quarto-html     # HTML出力
make quarto-pdf      # PDF出力
make quarto-reveal   # Reveal.jsスライド
```

Quartoは、コード・分析結果・説明文を統合した動的文書を作成できます。

Quarto enables you to create dynamic documents integrating code, results, and narrative.

## GitHub Actions連携 / GitHub Actions Integration

このプロジェクトには以下のワークフローが含まれています：

- **CI/CD** (`.github/workflows/ci.yml`): 自動テスト・リント
- **Notion連携** (`.github/workflows/notion-*.yml`): 
  - 文献データベースの同期
  - PDFのOCR処理
  - Paperpileからの文献インポート

These workflows are included:

- **CI/CD**: Automated testing and linting
- **Notion Integration**: Bibliography sync, PDF OCR, Paperpile import

## 主要パッケージ / Key Packages

### Python計量経済学 / Python Econometrics

- **linearmodels**: パネルデータ、IV推定
- **pyfixest**: 高速固定効果推定（Stata風構文）
- **DoubleML**: Double Machine Learning
- **EconML**: 機械学習ベース因果推論
- **PyBLP**: BLPモデル推定
- **statsmodels**: 統計モデル全般
- **csdid**: Callaway-Sant'Anna DID推定
- **rdrobust**: RDデザインのロバスト推定
- **scpi-pkg**: Synthetic Control

### データ処理 / Data Processing

- **pandas**: データフレーム操作
- **polars**: 高速データフレームライブラリ
- **scikit-learn**: 機械学習
- **PyTorch**: 深層学習

### 可視化 / Visualization

- **matplotlib**: 基本的なプロット
- **seaborn**: 統計的可視化
- **plotnine**: ggplot2スタイル（Pythonで）

## 開発ガイドライン / Development Guidelines

### コード品質 / Code Quality

- **ruff**: 高速なPythonリンター・フォーマッター
- **mypy**: 型チェック
- **pre-commit**: コミット前の自動チェック

```bash
make format  # コードを自動フォーマット
make check   # リント・型チェック・テスト実行
```

### テスト / Testing

```bash
make test    # テスト実行（カバレッジ付き）
```

## トラブルシューティング / Troubleshooting

### GPU利用の確認 / GPU Availability

```bash
make gpu
```

CUDA・PyTorchのGPU利用可能性を確認できます。

Check CUDA and PyTorch GPU availability.

### クリーンビルド / Clean Build

```bash
make clean       # 一時ファイル削除
make clean-all   # すべてのビルド成果物を削除
```
