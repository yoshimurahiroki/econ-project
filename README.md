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

1. このリポジトリの[完全ソース ZIP](docs/ai/distributions/economics-workflow-v66-checked-20261017.zip)を取得します。スキル本文と参照ファイルを含む、プラグイン作成用の入力資料です。
2. Plugin Creator を利用できる ChatGPT の会話に ZIP を添付し、下の例のように作成を依頼します。Creator に manifest の追加、各スキル内で参照が完結する配布構成への変換、通常の読み取り機能による確認を依頼します。保存先は接続中のアカウントまたはワークスペースです。
3. 作成結果として返されたリンクから自分のプラグインを確認します。そのプラグインを使う会話で、たとえば「econ-writing の revise で、次の段落を日本語で改稿してください」と対象文章を渡します。

依頼例：

```text
添付の完全ソース ZIP から、私が使う非公開のスキル型 ChatGPT プラグインを Plugin Creator で作成・保存してください。
完全ソースを保持し、5スキルを公開するための plugin.json 等を追加してください。
各スキルの必須・条件付き参照を末端までたどり、共通 runtime・registry、他スキルの本文、profiles・harness・実装・例文を、そのスキル自身の references/bundle 配下で読める構成にしてください。相対リンクと registry の読み取り用パスも、そのスキル内で解決するように更新してください。規則の本文、論理 ID、モードは維持してください。
bundle に入れた他スキルの本文は REFERENCE.md 等に改名し、公開する SKILL.md は5つにしてください。元のソースパスとプラグイン内の読み取り用パスを区別してください。保守スクリプトを実行する場合は、完全ソースと対応する実行環境を使うことを明記してください。ソース更新時は bundle を再生成し、各コピーと参照先を再確認してください。
公開後、通常のスキル読み取り機能で5つの入口と各参照先を実際に読み、必須・条件付き参照の到達性を確認してください。管理用のファイル取得成功だけで完了としないでください。
作成結果のリンク、利用できる5スキル、読み取り確認結果を返してください。
```

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
