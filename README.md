# econ-project

計量経済学、因果推論、構造推定、機械学習の分析環境と、経済学研究向けの AI 指示をまとめたテンプレートです。Python の statsmodels・pyfixest・PyTorch、R の fixest・ivreg・plm などを、Pixi と rv の lock ファイルで管理します。

共通ハーネスと研究スキルの正本は [econ-project-mini](https://github.com/yoshimurahiroki/econ-project-mini) です。このリポジトリは、より広い Python・R 分析環境と論文・スライドのビルド機能を持ちます。

## 使い始める

```sh
git clone https://github.com/yoshimurahiroki/econ-project.git
cd econ-project
```

AI の指示を使うには、このフォルダーをコーディングエージェントの作業場所にし、[AGENTS.md](AGENTS.md) と[操作一覧](docs/ai/compiled_ai_skills.md)を入口にします。

分析環境には Docker と VS Code の Dev Containers 拡張を用意し、このフォルダーをコンテナで開きます。Pixi の対象プラットフォームは `linux-64` です。[Dev Container 設定](.devcontainer/devcontainer.json)が Pixi、rv の R パッケージ、Jupyter カーネルを準備します。依存関係は [pyproject.toml](pyproject.toml)、[rproject.toml](rproject.toml)、[pixi.lock](pixi.lock)、[rv.lock](rv.lock) で管理します。

```sh
make help
make sync
make r-install
```

Notebook では登録済みの Python または R カーネルを選びます。データ用の `data/` は Docker volume に保存され、Git 管理から除外されています。

## 研究と執筆

| スキル | 担当する作業 |
|---|---|
| `econ-design` | 研究質問、モデル、識別・推定設計 |
| `econ-literature` | 文献調査、引用・制度の確認 |
| `econ-data` | データ取得・加工、計算、分析コード |
| `econ-writing` | 執筆、改稿、翻訳、論文の説明 |
| `econ-review` | 主張・成果物の評価と指定範囲の修正 |
| `project-work` | 案件参加・運営、専門作業の接続と成果統合 |

依頼には対象資料、成果物、変更を許す範囲を添えます。[操作一覧](docs/ai/compiled_ai_skills.md)からモードを選び、指定されたスキルと適用規則を読みます。文章・コード・成果物と実操作は [CORE](runtime/CORE.md) と [PROSE](runtime/PROSE.md) に沿って一体でレビューします。

条件付きの [econ-knowledge](skills/econ-knowledge/SKILL.md) は知識ライブラリ 2.3 の 250 ID を提供します。概念や JEL 分類から候補を探し、選択した項目とその前提を読みます。`project-work:contribute` と `project-work:manage` は、研究上の判断、作業、資源、成果を専門スキルと状態管理に接続します。

[研究実行ガイド](harness/research.md)は、因果推論、需要・供給、動学選択・ゲーム、市場設計、一般均衡、異質主体と数値計算の仕様・実行入口を示します。保存した結果から表・図・本文・スライドと再現パッケージを生成します。文献コーパスは複数の命題と原文位置を保持し、設計・計算・執筆・査読に渡します。

中長期の株式評価は [`econ-data:equity`](skills/econ-data/references/equity.md) と[経済モデル](skills/econ-data/references/equity-models.md)を使います。開示・IR・ニュース・産業データから需要、競争、投資、持続的 FCF、適正株価と意思決定を分析します。EDINET・e-Stat のキーは利用者自身の環境で管理します。

## 論文とスライド

[LaTeX 論文](tex/paper/ecta_template.tex)と [Beamer スライド](tex/slides/main.tex)を編集し、次のコマンドで PDF を作ります。

```sh
make build-paper
make build-slides
```

`PAPER=...`、`SLIDES=...` で原稿を指定できます。Quarto 原稿には `QMD=...` と `make quarto-html`、`make quarto-pdf`、`make quarto-reveal` を使います。

## 配布と状態管理

[公開正本のソース ZIP](https://github.com/yoshimurahiroki/econ-project-mini/archive/refs/heads/main.zip)から `python scripts/export_project.py --generate-entries` でスキルの配布物を生成できます。Plugin Creator への配布と更新は[配布手順](docs/ai/plugin-integration.md)に従います。Project に手動配置する場合は、出力先を新規に指定します。

```sh
python3 scripts/export_project.py --task econ-writing --mode compose --output /tmp/econ-writing-project-new
```

生成された `PROJECT_INSTRUCTIONS.txt` を指示欄へ貼り、残りのファイルを添付します。[統合・配布の説明](docs/ai/integration.md)は配置と同期の入口を示し、[同期記録](docs/ai/common-core.json)は共通ソースの版と管理対象を記録します。

[状態管理](harness/state.md)は、依頼、権限、成果物の版、依存関係と作業の再開を扱います。`.agents/state/` は Git 管理外です。

```sh
python3 harness/state.py --root . init
python3 harness/state.py --root . inspect
```

変更に対応する既存の Python 検査は次の入口から実行します。

```sh
python3 -m unittest discover -s harness -p 'test_*.py'
```
