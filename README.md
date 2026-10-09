# econ-project

Python・R・Quarto・LaTeXを使う経済学研究のテンプレートである。fullは計量・機械学習・データ処理の広い環境を備える。必要な分析パッケージから始める研究には [mini](https://github.com/yoshimurahiroki/econ-project-mini) を使う。

## 研究を始める

GitHubの「Use this template」で研究用のリポジトリを作り、VS CodeのDev Containerで開く。依存環境は初回のcontainer作成時に導入される。研究課題と受け入れた判断は [docs/issue](docs/issue/README.md) の既存形式で記録する。原データと加工データは `data/` に置き、コードと定義から必要な表・図・文書を生成する。

[.cursorrules](.cursorrules) が共通方針、[研究skills](docs/ai/compiled_ai_skills.md) が作業方法を定める。作業では保存済みの入力と成果物を再利用し、変更が影響する入口を実行する。

## 環境と保存領域

各研究の `data/` と `.pixi/` は `econ_data_${devcontainerId}`、`econ_pixi_env_${devcontainerId}` に保存する。[Dev Container識別子](https://github.com/devcontainers/spec/blob/main/docs/specs/devcontainer-id-variable.md) は再作成後も安定し、同じDocker host上の独立した研究を分離する。ダウンロードcache `econ_pixi_cache` は共有する。setupは保存領域のrootを設定する。

fullの保存済みR依存関係はRust 1.96.1でビルドする。DockerfileとMakeの既定版を揃え、明示した `RUSTUP_TOOLCHAIN` は保持する。R依存関係やkernelの導入に失敗するとsetupを停止する。既存containerで必要な版が未導入なら、`rustup toolchain install 1.96.1 --profile minimal` の後に `make r-install` を実行する。利用者の自動導入設定は保持する。

既存containerを再作成する前に、`docker inspect CONTAINER --format '{{json .Mounts}}'` で現在のvolume名を確認する。継続利用する場合は `.devcontainer/devcontainer.json` の該当 `source=` をその名前に固定する。従来の既定名なら次の2行を使う。

```json
"type=volume,source=econ_data,target=/workspaces/econ-project/data",
"type=volume,source=econ_pixi_env,target=/workspaces/econ-project/.pixi"
```

内部パスとcache mountを維持したまま再作成する。この設定は既存volumeをその場所で再利用する。

| 操作 | 用途 |
| --- | --- |
| `make sync` | Pixi依存環境を更新 |
| `make r-install` / `make r-plan` | rv依存環境を更新／変更計画を表示 |
| `make register-kernels` / `make setup-r-kernel` | 導入済みPixi環境のPython・R kernelを登録 |
| `pixi add PACKAGE` / `rv add PACKAGE` | 研究で使う依存パッケージを追加 |
| `pixi run python scripts/NAME.py` | 既存環境で研究コードを実行 |

## 文書と作業入口

| 入口 | 出力 |
| --- | --- |
| `make build-paper [PAPER=path.tex]` | sourceと同じ場所のPDF。既定は `tex/paper/ecta_template.pdf` |
| `make build-slides [SLIDES=path.tex]` | sourceと同じ場所のPDF。既定は `tex/slides/main.pdf` |
| `make quarto-html QMD=path.qmd` | 指定QMDのHTML |
| `make quarto-pdf QMD=path.qmd` | 指定QMDのPDF |
| `make quarto-reveal QMD=path.qmd` | 指定QMDのReveal.js |

Quartoの `QMD` を省略するとプロジェクト全体をrenderする。出力先と既定formatは文書・project設定に従う。LaTeXの既定文書には研究の文献ファイル `tex/bibliography.bib` を用意する。LaTeXのエラーはbuildを停止し、`.aux` に文献指定がある場合に実行するBibTeXの失敗も伝播する。

具体的な変更リスクを確認する入口は `make test TEST=path::node`、`make lint FILE=path`、`make format FILE=path` である。対象は明示したファイル・testに限る。commit hookはprivate key検出を行う。

## Gitと共通機能の管理

Gitの作者名・メールは利用者自身のGit設定を使う。コンテナの実行ユーザー `vscode` はcommit作者とは別の設定である。

共通ファイルを複数の研究へ配布する場合は [汎用同期の手順](docs/ai/integration.md#common-core) を使う。同期元・同期先・管理path・期待HEADを指定し、差分を確認してから `--apply` を実行する。各研究の独自変更は前回採用版との比較で保護する。通常の起動時には同期しない。

## ProjectとIDEの接続

[Project連携](docs/ai/integration.md) に既存Projectのbridge、全方式・選択方式のstandalone、task別exportと共通指示の同期入口がある。研究固有の選択は[project context](docs/ai/repo_context.md)に置く。同期元と同期先は利用者が指定する。上流テンプレートの保守では、[econ-project-mini](https://github.com/yoshimurahiroki/econ-project-mini)で共通指示を編集する。

```sh
python scripts/export_project.py --profile bridge --output /tmp/econ-bridge
python scripts/export_project.py --profile standalone --output /tmp/econ-all-new
python scripts/export_project.py --profile standalone --task econ-paper \
  --references .agents/skills/econ-workflow/references/descriptive-model.md \
  --output /tmp/econ-paper-new
```

exportは選択した指示とsource revisionを新しい外部folderへ保存する。全文contextが必要な作業では `bash scripts/pack_context.sh /tmp/econ-context.txt` を使う。導入済みRepomixがGitのignoreと既存configに従って出力する。出力先を省略すると一時folderへ新しいファイルを作る。

配布用の設定定義は [config templates](docs/ai/config-templates/README.md) にある。認証済みのruntime設定はローカルに生成し、Git管理から分離する。MCPは必要なserverの実行ファイルと環境変数を用意してから `bash scripts/setup_ide_mcp.sh --write` で設定する。[IDEを同じ環境から起動する](https://prod.cursor.com/help/customization/mcp)。API keyとdatabase接続情報はserver起動時に環境から渡す。Google Driveの資格情報は `secrets/credentials.json` に置く。Codexには環境変数名のallowlistを生成する。生成器は管理対象のMCP blockを更新し、モデル、役割、許可設定、手管理のMCP接続を保持する。JSON設定はMCP欄以外の利用者設定を保持する。
