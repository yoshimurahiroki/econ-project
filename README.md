# econ-project

経済学研究のためのPython・R分析環境とEconomics Research Skills（ERS）をまとめたプロジェクト。計量経済学、因果推論、需要・構造推定、時系列、機械学習などの依存定義をPixi・rvのlockとともに管理し、Jupyter、Quarto、LaTeXで分析から論文・スライドまで作成する。

研究スキル・知識・共通ハーネスの正本は[econ-project-mini](https://github.com/yoshimurahiroki/econ-project-mini)である。このリポジトリは共有ソースを受け取り、広い科学計算環境、lock、コンテナ設定を保守する。研究ごとに必要なパッケージを導入する軽量な基盤から始める場合はminiを選ぶ。

## 環境を用意する

```sh
git clone https://github.com/yoshimurahiroki/econ-project.git
cd econ-project
```

DockerとVS CodeのDev Containers拡張を用意し、このフォルダーを「Reopen in Container」で開く。[コンテナ設定](.devcontainer/devcontainer.json)から[初期セットアップ](.devcontainer/setup-environment.sh)を実行し、Pixi環境、rvのRパッケージ、Python・RのJupyterカーネルを準備する。対象は`linux-64`、Pythonは3.12系、Rは4.5系。コンテナには文書作成用のTeX Liveと、Rパッケージのビルドに使うツールも含む。

環境の定義は[pyproject.toml](pyproject.toml)と[rproject.toml](rproject.toml)、解決した依存の固定版は[pixi.lock](pixi.lock)と[rv.lock](rv.lock)で管理する。初期セットアップではRの研究用パッケージも導入する。以降の更新やカーネル登録はリポジトリのルートで行う。

```sh
make help
make sync
make r-install
make register-kernels
```

Notebookでは`Python (フォルダー名)`または`R (フォルダー名)`を選ぶ。カーネルIDは作業場所ごとに分かれる。コンテナ内の作業場所は`/workspaces/<フォルダー名>`で、`data/`と`.pixi/`はDocker volumeに置く。個別ファイルの整形は`make format FILE=...`、Rは`make format-r FILE=...`を使う。

## 研究作業を依頼する

コーディングエージェントの作業場所をこのフォルダーにし、[AGENTS.md](AGENTS.md)と[操作一覧](docs/ai/compiled_ai_skills.md)を入口にする。問い、対象データ・資料、欲しい成果物、変更する範囲を伝え、担当Skillとモードを選ぶ。共通の判断・執筆規則は[CORE](runtime/CORE.md)と[PROSE](runtime/PROSE.md)にある。

| Skill | 担当する作業 |
| --- | --- |
| [econ-design](skills/econ-design/SKILL.md) | 研究質問、モデル、識別・推論設計、方法選択 |
| [econ-literature](skills/econ-literature/SKILL.md) | 文献調査、原文・引用・制度の確認 |
| [econ-data](skills/econ-data/SKILL.md) | データ取得・加工、推定・計算、研究コード、企業価値評価 |
| [econ-writing](skills/econ-writing/SKILL.md) | 執筆、改稿、翻訳、説明、論文・スライドへの変換 |
| [econ-review](skills/econ-review/SKILL.md) | 主張・計算・成果物の評価と指定範囲の修正 |
| [econ-knowledge](skills/econ-knowledge/SKILL.md) | 主担当が必要とする理論・モデル・判断条件の参照 |
| [project-work](skills/project-work/SKILL.md) | 要件・作業方針、実行プロンプト、案件への参加・運営 |

[知識ライブラリ](skills/econ-knowledge/references/domains.json)は35章・256ユニット・34モデル契約を持つ。日英の概念・同義語とJEL分類から候補を選び、適用するIDの定義・数式・前提を読む。モデル契約は入力、推定対象、均衡・意思決定、結果と実装を対応させる。

```sh
python3 skills/econ-knowledge/scripts/knowledge.py search --query "価格 在庫 ベイズ" --limit 6
python3 skills/econ-knowledge/scripts/knowledge.py plan FORECAST-01 --read
```

ベイズ統計・計量経済学では事前・事後予測、部分プーリング、計算診断、モデル比較と損失に応じた行動選択を扱う。企業の意思決定ではMMM・顧客価値、価格・商品・プラットフォーム、需要予測・在庫・容量、不動産・投資・信用・エネルギーを結ぶ。[中長期の企業・株式評価](skills/econ-data/references/equity.md)は、開示・産業データから競争、再投資、持続的FCF、逆DCFへ進む。

## 研究ごとの実装と環境を選ぶ

共通の分析環境に加え、採用したモデルは[公式実装の選択表](skills/econ-data/references/implementation-engines.md)から実行先を選ぶ。既存の因果推論、PyBLP、動学モデル、PyMC・ArviZの入口と、ベイズ・ビジネス分野の17の任意選択プロファイルを使える。各プロファイルの必要パッケージ・固定版・導入条件を研究ごとに選択する。

問い、推定対象、識別、標本・単位・期間と計算条件を含む選択仕様を`selection.json`に保存し、選択器へ渡す。

```sh
python3 skills/econ-design/scripts/research_design.py select selection.json \
  --root . --output outputs/selection.json
```

[公式project-script経路](skills/econ-data/references/implementation-calls.md#official-project-scripts)では、`options.stage`に研究プログラム、実データ・仕様、名前付き出力、実行するPython・R・Juliaを指定する。選択器は公式APIとパッケージ版をその段階へ結ぶ。Mesa・NetworkXを使う主体・ネットワークの研究も、採用した行動規則と初期状態を持つ研究プログラムを同じ経路で実行する。

各研究の環境は選択結果の`install_requirements`または既存の手法別requirements、R・Juliaのprojectとlockから復元する。実行するインタープリターを`argv`と`runtime.probe_argv`に対応させ、モデルソース・依存定義を入力へ含める。PythonからR・Juliaを呼ぶ段階は`runtime.companions`で言語環境を指定する。手法ごとに異なるpandas・PyMC・ArviZなどの版は別環境に置き、fullのPixi・rv環境と各研究の固定仕様を維持する。詳細は[実行環境の記録](harness/research.md#capture-the-selected-python-r-or-julia-environment)にある。

## 実行結果を保存し、再利用する

[研究実行ガイド](harness/research.md)に従い、データ取得、加工、推定・均衡計算、図表、本文の依存関係を研究manifest（JSON）へ定義する。採用済みのmanifestを`research.json`に保存した場合は、次の入口で実行する。

```sh
python3 harness/research.py --root . research.json
```

実行はデータ、採用仕様、コード、環境、上流結果を記録し、一致する完了済み段階を再利用する。変更した入力はその結果を使う段階へ伝える。各計算は、採用した識別・推論、元の均衡条件、ソルバーの終了と数値条件から結果を保存する。保存先と各段階の実行状況は返り値と[状態管理](harness/state.md)で確認できる。

[保存結果の登録](skills/econ-writing/references/result-artifacts.md)で数量、単位、定義と生成元を結び、同じ結果から表・図・本文を作る。自分の研究に登録したギャラリーと会議資料のパスを指定して表示する。

```sh
pixi run research-ui -- --root . \
  --registry path/to/research/gallery.json \
  --meeting path/to/research/meeting
```

marimoの画面から保存図表の検索・比較・表示編集を行う。[会議資料](harness/meetings.md)は図表と研究上の決定・作業記録を使い、[再現パッケージ](harness/research.md#package-and-reproduce-a-completed-research-result)は選択したデータ・コード・環境と完成結果をまとめる。

## 論文とスライドを作る

[LaTeX論文](tex/paper/ecta_template.tex)と[Beamerスライド](tex/slides/main.tex)を編集してPDFを作る。別の原稿は`PAPER=...`、`SLIDES=...`で指定する。

```sh
make build-paper
make build-slides
```

Quartoの[論文](tex/paper/quarto_template.qmd)・[スライド](tex/slides/quarto_template.qmd)には、原稿と出力形式を指定する。

```sh
make quarto-html QMD=tex/paper/quarto_template.qmd
make quarto-pdf QMD=tex/paper/quarto_template.qmd
pixi run quarto render tex/slides/quarto_template.qmd --to beamer
```

文書の入口は[Makefile](Makefile)、共通書式は[文書設定](docs/ai/integration.md#supplied-document-defaults)にある。生成したPDFは原稿と同じディレクトリへ置く。

## 共通ソースと利用者設定を管理する

共有の編集元はminiの`skills/`、`runtime/`、`registry/`、`harness/`と知識本文・カタログである。[共通同期](docs/ai/integration.md#common-core)で登録されたファイルを取り込み、[同期記録](docs/ai/common-core.json)に元の版と管理対象を残す。このリポジトリの依存定義、`pixi.lock`・`rv.lock`、コンテナ設定、研究データと成果物はそれぞれの所有元で保守する。

別プロジェクト向けの指示は、選択した操作・モードを書き出す。出力先に新しいディレクトリを指定する。

```sh
python3 scripts/export_project.py --task econ-writing --mode compose \
  --output /tmp/ers-writing-project-new
```

生成した`PROJECT_INSTRUCTIONS.txt`と参照ファイルをProjectへ配置する。エージェント用の配置は`--format deployed`、プラグインの配布は[統合・配布手順](docs/ai/plugin-integration.md)を使う。文体は[repo_context.md](docs/ai/repo_context.md)、IDE・モデル・接続は[設定ガイド](docs/ai/config-templates/README.md)から利用者ごとに設定する。

APIキー・認証情報、データ原本と評価履歴は利用者本人のSecret・非公開保存先に置く。`data/`、`outputs/`、`artifacts/`、`.agents/state/`などのGit管理範囲は[.gitignore](.gitignore)にある。
