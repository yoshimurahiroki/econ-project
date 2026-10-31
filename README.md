# econ-project

計量経済・因果推論・機械学習の分析ライブラリと、Python・R、Jupyter、Quarto、LaTeX、経済学研究向けの AI 指示をまとめた研究環境のテンプレートです。Python 側には statsmodels・pyfixest・PyTorch など、R 側には fixest・ivreg・plm などの依存を定義しています。

[econ-project-mini](https://github.com/yoshimurahiroki/econ-project-mini) は、分析ライブラリを研究ごとに追加する基盤中心の構成です。このリポジトリは広い分析依存と `pixi.lock`／`rv.lock` を持ち、文書ビルドは Makefile の LuaLaTeX 手順を使います。

## 使い始める

```sh
git clone https://github.com/yoshimurahiroki/econ-project.git
cd econ-project
```

AI の指示を使うには、このフォルダーを コーディングエージェント の作業場所にし、[AGENTS.md](AGENTS.md) と[操作一覧](docs/ai/compiled_ai_skills.md)を入口にします。

分析環境を使う場合は、Docker と VS Code の Dev Containers 拡張を用意し、このフォルダーをコンテナで開きます。Pixi の対象プラットフォームは `linux-64` です。初回セットアップはネットワークからパッケージを取得します。

[Dev Container 設定](.devcontainer/devcontainer.json)から [setup-environment.sh](.devcontainer/setup-environment.sh) が実行され、Pixi 環境、rv による R パッケージ、Jupyter カーネルを準備します。コンテナ内の作業場所は `/workspaces/econ-project` です。以降のコマンドはリポジトリのルートで実行します。

```sh
make help
```

## 分析と依存を管理する

Python／Pixi の依存定義は [pyproject.toml](pyproject.toml)、R パッケージは [rproject.toml](rproject.toml) にあります。解決済みの依存は [pixi.lock](pixi.lock) と [rv.lock](rv.lock) に記録しています。依存を編集した後の更新には次の入口を使います。

```sh
make sync
make r-install
```

Notebook では、セットアップで登録された Python／R カーネルを選びます。データは `data/` に置きます。コンテナの `data/` は Docker volume に保存され、Git 管理から除外されています。生成物を含む除外設定は [.gitignore](.gitignore) にあります。

コードの検査は、lock を参照する専用の `quality` 環境で行います。

```sh
make setup-quality
make quality FILE=scripts/pack_context.sh
```

`make lint FILE=...` は Python の lint、`make typecheck FILE=...` は型検査、`make test TEST=...` は指定したテストを実行します。R の検査には lintr、整形には styler を導入し、`make lint-r FILE=...`／`make format-r FILE=...` を使います。適用する検査と必要な道具は[品質検査の説明](docs/quality-checks.md)を参照してください。

## 論文とスライドを作る

[LaTeX 論文](tex/paper/ecta_template.tex)と [Beamer スライド](tex/slides/main.tex)を編集し、次のコマンドで PDF を作ります。

```sh
make build-paper
make build-slides
```

`PAPER=...`、`SLIDES=...` で別の原稿を指定できます。Makefile は原稿のディレクトリで LuaLaTeX を実行し、参考文献の指定があれば pbibtex を挟んで PDF を作ります。

Quarto 原稿を追加した場合は、ファイルを `QMD=...` で指定し、`make quarto-html`、`make quarto-pdf`、`make quarto-reveal` を使います。書式と実行条件はその原稿の設定で指定します。

## AI に研究作業を依頼する

| スキル | 担当する作業 |
|---|---|
| `econ-design` | 研究質問、モデル、識別・推定設計 |
| `econ-literature` | 文献調査、引用・制度の確認 |
| `econ-data` | データ取得・加工、計算、分析コード |
| `econ-writing` | 執筆、改稿、翻訳、論文の説明 |
| `econ-review` | 主張・成果物の評価と指定範囲の修正 |

依頼には、対象資料、欲しい成果物、変更を許す範囲を添えます。Codex では `$econ-writing` などを指定し、改稿なら `revise`、翻訳なら `translate` のように[操作一覧](docs/ai/compiled_ai_skills.md)のモードを選びます。

共有指示の編集元は [skills/](skills/)、[runtime/](runtime/)、[registry/](registry/) にあり、コーディングエージェント 向けの配置は [.agents/](.agents/) です。書き方のプロファイルと Project に渡す追加資料は [repo_context.md](docs/ai/repo_context.md) で選びます。

ChatGPT では、自分用プラグインとして使う方法と、Project へ指示を手動配置する方法を選べます。

### Plugin Creator で自分用プラグインを作る

共通スキルの正本は[econ-project-mini](https://github.com/yoshimurahiroki/econ-project-mini)です。この公開配備先も、個人用サービスへの接続を含まず独立して利用できます。

[最新の完全ソース ZIP](https://github.com/yoshimurahiroki/econ-project-mini/archive/refs/heads/main.zip)を展開し、`python scripts/export_project.py --generate-entries`で5スキルの参照を生成します。生成した配布物をPlugin Creatorへ渡して自分用プラグインとして登録し、保存後の入口と参照本文を読み戻します。公開用manifestには認証付きアプリやMCPの固定接続がありません。既存プラグインを更新する場合は[配布手順](docs/ai/plugin-integration.md)に従います。

### Project に手動で配置する

プラグインを使えない環境では、Project へ指示ファイルを手動配置します。

文章作成用の ChatGPT Project パッケージは、Python 3.12 で書き出せます。まだ存在しない出力先を指定します。

```sh
python3 scripts/export_project.py --task econ-writing --mode compose --output /tmp/econ-writing-project-new
```

生成された `PROJECT_INSTRUCTIONS.txt` を Project の指示欄へ貼り、残りのファイルを添付します。条件付き参照、native 配置、他リポジトリへの同期は[統合・配布の説明](docs/ai/integration.md)にあります。

### 作業状態を保存する

作業を再開するために成果物の版・依存関係・停止条件を保存するときは、[ハーネスの状態管理](harness/state.md)を使います。

```sh
python3 harness/state.py --root . init
python3 harness/state.py --root . inspect
```

記録先は Git 管理外の `.agents/state/` です。分担と引継ぎの指示は [TEAM.md](runtime/TEAM.md)、成果物の配置や Git 操作は [publication.md](harness/publication.md) にあります。

## 中長期の株式評価

`econ-data:equity`で、日本株・米国株・海外株の公開開示・IR・ニュース・産業データを取得します。同梱の[専門リファレンス](skills/econ-data/references/equity-models.md)で観測と識別からモデルを選び、需要・競争均衡・投資から持続的FCF、ネットキャッシュ、適正株価を算定します。事業別の物量・費用・資本、逆DCF、税・取引費用・予算・代替投資による購入・保有・売却、新情報の価値寄与を計算します。

[実行手順](skills/econ-data/references/equity.md)に従い、Python依存は`skills/econ-data/scripts/requirements-equity.txt`から導入します。EDINET・e-Statの無料キーは利用者本人のSecretから`EDINET_API_KEY`・`ESTAT_APP_ID`へ渡します。未登録時に他者のキーやサービスへ接続する処理はありません。本人が管理するMCPを接続済みなら、その認証・保存先を利用できます。通常分析は専門資料の外部取得を必要とせず、個人の資料・認証・評価履歴は各利用者の非公開環境で管理します。売買需給分析には信用取引残高と裁定取引残高だけを使います。
