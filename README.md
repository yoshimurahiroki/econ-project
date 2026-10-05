# econ-project

Python・R・Quarto・LaTeXを使う経済学研究のテンプレートである。fullは計量・機械学習・データ処理の広い環境を備える。必要な分析パッケージから始める研究には [mini](https://github.com/yoshimurahiroki/econ-project-mini) を使う。

## 研究を始める

GitHubの「Use this template」で研究用のリポジトリを作り、VS CodeのDev Containerで開く。依存環境は初回のcontainer作成時に導入される。研究課題と受け入れた判断は [docs/issue](docs/issue/README.md) の既存形式で記録する。原データと加工データは `data/` に置き、コードと定義から必要な表・図・文書を生成する。

[.cursorrules](.cursorrules) が共通方針、[研究skills](docs/ai/compiled_ai_skills.md) が作業方法を定める。作業では保存済みの入力と成果物を再利用し、変更が影響する入口を実行する。

## 環境と保存領域

各研究の `data/` と `.pixi/` は `econ_data_${devcontainerId}`、`econ_pixi_env_${devcontainerId}` に保存する。[Dev Container識別子](https://github.com/devcontainers/spec/blob/main/docs/specs/devcontainer-id-variable.md) は再作成後も安定し、同じDocker host上の独立した研究を分離する。ダウンロードcache `econ_pixi_cache` は共有する。setupは保存領域のrootを設定する。

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

## ProjectとIDEの接続

[Project連携](docs/ai/integration.md) に既存Projectのbridgeとstandalone exportの使い方がある。

```sh
python scripts/export_project.py --profile bridge --output /tmp/econ-bridge
```

exportは選択した指示とsource revisionを新しい外部folderへ保存する。全文contextが必要な作業では `bash scripts/pack_context.sh /tmp/econ-context.txt` を使う。導入済みRepomixがGitのignoreと既存configに従って出力する。出力先を省略すると一時folderへ新しいファイルを作り、次回の入力への自己混入を避ける。

MCPは必要なserverの実行ファイルと環境変数を用意してから `bash scripts/setup_ide_mcp.sh --write` で設定する。[IDEを同じ環境から起動する](https://prod.cursor.com/help/customization/mcp)。接続資格情報は設定へ書き込まず、server起動時に環境から渡す。Codexには [変数名のallowlist](https://learn.chatgpt.com/docs/config-file/config-reference) を生成する。
