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

### 選択した推定器の環境

Pixi と rv はこのプロジェクトの基盤環境を管理します。各研究ランナーが使用する版は、`skills/econ-data/scripts/requirements-*.txt` と `requirements-causal-r.json` が定義します。`research_causal.py select` の選択結果から必要なファイルを特定し、その手法用の環境に復元します。たとえば拡張因果推論は次の Python 環境を使います。

```sh
python3.12 -m venv outputs/causal-env
outputs/causal-env/bin/python -m pip install -r skills/econ-data/scripts/requirements-causal.txt
```

因果推論の pandas 3 と、需要・動学モデルの pandas 2 は別の環境に置きます。R の分析も、選択した requirements の R・パッケージ版に一致する実行環境を指定します。既存 `rv.lock` の `did`・`DRDID` などと手法別の固定版は異なります。

研究 DAG の `runtime.executable` に使用する Python または Rscript を、`runtime.requirements` にその手法の既存 requirements ファイルを指定します。同じファイルをステージの `inputs` に含めます。Python から R を呼ぶ場合は `runtime.companions` に R の定義を置きます。[研究実行ガイド](harness/research.md)の環境照合が、パッケージ版・Git コミット・公式関数の引数を計算前に確認し、requirements の変更を保存結果の再利用条件に反映します。Pixi の NumPy は conda 側の定義で管理します。

## 研究と執筆

| スキル | 担当する作業 |
|---|---|
| `econ-design` | 研究質問、モデル、識別・推定設計 |
| `econ-literature` | 文献調査、引用・制度の確認 |
| `econ-data` | データ取得・加工、計算、分析コード |
| `econ-writing` | 執筆、改稿、翻訳、論文の説明 |
| `econ-review` | 主張・成果物の評価と指定範囲の修正 |
| `project-work` | 要件・方針整理、実行プロンプト作成・改善、案件参加・運営と成果統合 |

依頼には対象資料、成果物、変更を許す範囲を添えます。[操作一覧](docs/ai/compiled_ai_skills.md)からモードを選び、指定されたスキルと適用規則を読みます。文章・コード・成果物と実操作は [CORE](runtime/CORE.md) と [PROSE](runtime/PROSE.md) に沿って一体でレビューします。

条件付きの [econ-knowledge](skills/econ-knowledge/SKILL.md) は、[知識カタログ](skills/econ-knowledge/references/catalog.json)の概念・型付き関係・モデル契約を提供します。概念や JEL 分類から候補を探し、選択した項目とその前提を読みます。`project-work:contribute` と `project-work:manage` は、研究上の判断、作業、資源、成果を専門スキルと状態管理に接続します。

[研究実行ガイド](harness/research.md)は、因果推論、需要・供給、動学選択・ゲーム、市場設計、一般均衡、異質主体と数値計算の仕様・実行入口を示します。保存した結果から表・図・本文・スライドと再現パッケージを生成します。文献コーパスは複数の命題と原文位置を保持し、設計・計算・執筆・査読に渡します。

中長期の株式評価は [`econ-data:equity`](skills/econ-data/references/equity.md) と[経済モデル](skills/econ-data/references/equity-models.md)を使います。開示・IR・ニュース・産業データから需要、競争、投資、持続的 FCF、適正株価と意思決定を分析します。EDINET・e-Stat のキーは利用者自身の環境で管理します。

## 保存済み結果・研究計画・会議資料を編集する

```sh
pixi run research-ui -- --root . \
  --registry examples/research-workspace/gallery.json \
  --meeting meetings/workspace-demo
```

marimo の画面で、保存した記述統計表・図表を検索、比較、編集します。`--registry` に自分の結果ギャラリーを指定します。[結果ギャラリー](skills/econ-writing/references/result-artifacts.md)は保存済みの表示用行データと定義を読み、表示変更には既存の推定結果を使います。[公開用の合成表示例](examples/research-workspace/README.md)を同梱しています。

研究計画、採用仕様、発見・解釈・判断は既存 ERS の記録から編集します。`--project CASE` で登録済みの案件を開き、計画の版、比較、変更の影響を確認できます。担当、期限、依存、優先順位、進捗は [GitHub Issues / Projects](harness/state.md#project-work) で管理します。

[会議資料](harness/meetings.md)は、選択した保存済み図表、前回の決定・To Do、今回の進捗から作成します。画面で本文と構成を編集し、Markdown、Quarto HTML、Beamer PDF を生成します。GitHub のブラウザで資料を編集すると、Actions が保存済み資料を HTML に描画します。Google Slides にはネイティブの編集版を作成します。

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
