# Econometrics Research Environment

経済学研究のためのフルスタック開発環境です。

## 🏗️ 環境構成

- **コンテナ**: rootless Docker + VS Code Dev Containers
- **Python**: conda/mamba + Poetry管理（pip禁止運用）
- **R**: tidyverse + IRkernel
- **LaTeX**: Econometrica対応 + 日本語ドラフト + BibTeX
- **開発ツール**: pre-commit, ruff, mypy, pytest

## 📁 プロジェクト構造

```
econ-project/
├── .devcontainer/          # Dev Container設定
├── .github/workflows/      # GitHub Actions CI
├── notebooks/
│   ├── python/            # Pythonノートブック
│   └── r/                 # Rノートブック
├── src/                   # Pythonソースコード
├── R/                     # Rスクリプト
├── tex/
│   ├── paper/             # 論文（Econometrica）
│   └── slides/            # プレゼンテーション（Beamer）
├── tests/                 # テストコード
├── pyproject.toml         # Poetry設定
├── environment.yml        # conda環境
└── .pre-commit-config.yaml
```

## 🚀 使用方法

### 1. 環境構築

```bash
# Dev Containerでの起動
# VS Code で "Reopen in Container" を選択

# 初回セットアップ
poetry install --no-root
pre-commit install
```

### 2. 開発ワークフロー

#### Python開発
```bash
# 依存関係の追加
poetry add package_name
poetry add --group dev dev_package_name

# 品質チェック
poetry run ruff check .
poetry run ruff format .
poetry run mypy .
poetry run pytest
```

#### R開発
```bash
# Rパッケージのインストール
R -e "install.packages('package_name')"

# カーネル確認
jupyter kernelspec list
```

#### LaTeX論文作成
```bash
# 論文コンパイル（日本語ドラフト）
cd tex/paper
latexmk -lualatex -shell-escape main.tex

# スライド作成
cd tex/slides  
latexmk -lualatex -shell-escape talk.tex
```

### 3. データ管理

データは `data/` ディレクトリに配置（Git追跡除外）
```bash
# データの配置
cp /path/to/your/data.csv data/
```

## 🔧 設定詳細

### Poetry依存関係管理
- **本番**: numpy, pandas, scipy, statsmodels, matplotlib, seaborn, scikit-learn
- **開発**: pytest, mypy, ruff, pre-commit

### Pre-commit Hooks
- ruff（linting & formatting）
- YAML/TOMLチェック
- 末尾空白削除
- 秘密鍵検出

### LaTeX設定
- **クラス**: ectaart（Econometrica）
- **エンジン**: LuaLaTeX（日本語対応）
- **BibTeX**: econometrica.bstスタイル

## 📊 サンプル

### Pythonサンプル
```python
import pandas as pd
import statsmodels.api as sm

# データ読み込み
df = pd.read_csv('data/sample.csv')

# 回帰分析
X = sm.add_constant(df[['education', 'experience']])
y = df['log_wage']
model = sm.OLS(y, X).fit()
print(model.summary())
```

### Rサンプル
```r
library(tidyverse)
library(broom)

# データ読み込み
df <- read_csv('data/sample.csv')

# 回帰分析
model <- lm(log_wage ~ education + experience, data = df)
summary(model)
```

## 🔍 品質管理

### コード品質
- **Linting**: ruff（高速・包括的）
- **Formatting**: ruff format（Black互換）
- **Type checking**: mypy strict mode
- **Testing**: pytest

### CI/CD
GitHub Actionsで自動実行：
- コード品質チェック
- テスト実行
- 型チェック

## 📚 参考資料

- [Poetry Documentation](https://python-poetry.org/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Econometrica LaTeX Style](https://www.econometricsociety.org/)
- [Dev Containers](https://containers.dev/)

## 🤝 貢献

1. Forkしてください
2. Feature branchを作成（`git checkout -b feature/AmazingFeature`）
3. Commitしてください（`git commit -m 'Add AmazingFeature'`）
4. Pushしてください（`git push origin feature/AmazingFeature`）
5. Pull Requestを開いてください

## 📄 ライセンス

このプロジェクトはMITライセンスの下で配布されています。詳細は `LICENSE` ファイルをご覧ください。

Econometrics research stack

- WSL2 + rootless Docker 上のコンテナ開発
- Python / R (mamba + Poetry 管理)
- Jupyter, LaTeX (ectaart + 日本語ドラフト), Beamer スライド
- pre-commit + ruff + mypy + pytest
