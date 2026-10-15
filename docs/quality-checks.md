# 変更対象の品質検査

AI がコードを作成・変更したら、変更言語・入出力境界・意味のある処理から次の検査を選び、指摘の妥当性を確認して修正し、同じ対象を再検査する。利用者が毎回 checker を選ぶ必要はない。完了報告には実行コマンド、対象、結果、未検証事項を含める。仕様が未確定なら型や lint の都合で研究上の判断を決めない。

## 最初の準備と実行場所

`make setup-quality` は `pixi.lock` の独立した `quality` 環境を導入し、既存 pre-commit hook を登録する。研究用の巨大な default 環境や R package 群は導入しない。通常はこの準備を AI が行う。起動環境の Pixi を使い、依存追加・更新も manifest と lock に記録する。検査に必要なツールがないことを「検査成功」と扱わない。

- 作業中: `make quality FILE=path`。複数ファイルは `pixi run --locked -e quality pre-commit run --files path1 path2`。未追跡の新規ファイルにも実行する。
- commit: `make quality-staged` またはインストール済み commit hook が staged ファイルを検査する。pre-commit は未 stage の差分を一時退避する。自動 fix はしない。
- PR: CI は実際の PR HEAD を checkout し、base との merge-base からの変更ファイルに同じ hook を実行する。hook・manifest・lock・Make・CI を変えた場合は代表 Python/Shell ファイルも確認する。
- `make quality-changed BASE=ref` は ref と HEAD の committed 差分だけを扱う。分岐後に base が進んだ場合は `BASE=$(git merge-base ref HEAD)` を指定する。作業中差分と未追跡ファイルは上の `--files` を使う。

保存時自動修正、全ツリー一括整形、重い分析は起動しない。文書だけの変更ではコード checker は発火しない。秘密鍵検出は既存どおり各変更ファイルに発火する。

## 発火条件と失敗の扱い

| 変更・検出対象 | 入口と対象 | commit / CI | 扱い |
| --- | --- | --- | --- |
| Python の構文、未定義名、無効な比較・制御構文など | 変更 `.py` / `.pyi` に Ruff `E9,F63,F7,F82` | 自動 | 必須。exit 1 は修正・再検査 |
| Python の追加・変更した入出力境界、再利用関数の引数・戻り値の不整合 | `make typecheck FILE=path.py`。初期対象は `scripts/export_project.py` の既存 annotated `export()` と `main()`、追加した `sha256()` と `flat_filename()` | 初期対象ファイルの変更時に自動 | 必須。新しい境界を段階的に注釈し、確認できたファイルを hook の対象へ追加 |
| Shell の未定義変数、無効な test、構文など | 変更 shell を ShellCheck 0.11.0 `--severity=warning` | 自動 | warning / error は必須。info は参考として AI が必要時に全診断を読む |
| `.Rprofile`、R の構文、`x == NA`、空配列に対する `1:length(x)`、条件式の vector logic | `make lint-r FILE=path` | 自動 hook には含めず、R 変更時に AI が必須実行 | parse と選択した lintr 診断を失敗にする。code は実行せず静的に検査 |
| Python の import 順・表記等 | 変更 Python に `make lint FILE=path`、`make format-check FILE=path` | 自動 gate には含めない | 参考。exit 1 を記録して変更箇所との関連を判断。既存全件の整形や warning 隠蔽に進まない |
| 変更した処理の契約・研究条件 | `make test TEST=path::node`、または既存の小さな fixture・assertion | CI は変更対象の repository helper tests だけ自動。研究条件は AI が選択 | 対象処理の条件違反は必須失敗 |

Ruff の必須規則は `--select` で固定し、既存の通常 lint の `I/TID/UP` より優先する。mypy は全 strict 化せず、未注釈の関数内部を保証しない。`ignore_missing_imports` や `follow_imports=skip` で推移 import の問題を一括隠蔽しない。変更境界に必要な stub・型情報を個別に確認し、環境不足とコード誤りを区別する。

ShellCheck の info には正しい single quote に対する SC2016 などもあるため gate は warning 以上に限定した。引用や変数展開を変更した場合は `pixi run --locked -e quality shellcheck path.sh` も読み、SC2086 の分割・glob 展開等を個別判断する。黙って除外・抑制を増やさない。

単位、キー、一意性、結合の行数・多重度、欠損とゼロ、標本、分母は型・lint だけでは保証できない。変更した結合には小さな重複キー fixture、集計にはゼロ・欠損・空標本と分母の確認など、該当する既存 test を使う。標本選択、処置分類、推定方法を検査導入の都合で変更しない。

## check と fix

`quality`、`typecheck`、`lint`、`lint-r`、`format-check` と commit / CI はソースを変更しない。`make format FILE=path.py` と `make format-r FILE=path.R` だけが指定ファイルを整形する。整形が必要な変更範囲でのみ使い、差分を確認して check を再実行する。R は `styler::style_text(scope="spaces")` とし、token 変更を避ける。`.Rprofile` は `style_file()` の対象拡張子ではないため、指定した一ファイルを `style_text()` で整形する。styler の cache はこの R プロセスの一時領域に置き、home の書き込み権限や利用者の永続設定に依存させない。Ruff `--unsafe-fixes` や意味を変える自動 fix はこの入口に含めない。

## 導入する場合・しない場合

この repo の実コードは Python / Shell と `.Rprofile` である。R 変更時はまず `pixi run Rscript --vanilla -e 'stopifnot(requireNamespace("lintr", quietly=TRUE))'` で実環境を確認する。full の `r-languageserver` が lintr / styler を依存として要求し、`pixi.lock` と `rv.lock` の両方に lintr 3.3.0-1 / styler 1.11.0 が含まれる。未導入と決めつけて CRAN に重複 install しない。default 環境が未準備なら通常の `make sync` を使う。`make r-install` は研究用 R 依存の更新が必要な場合だけで、lint のためだけに実行しない。

新たな R 分析を採用して頻繁に変更する時点で、必要な R tool を直接依存として記録し、小さな R 専用環境と変更 R hook / CI を追加する。現状の `.Rprofile` だけのために PR ごとに研究環境を導入しない。R に変更がなければ R 実行環境の追加導入は不要。

Black / Flake8 / isort / Pylint / ty は現時点で品質入口から呼ばれていない。Black は `causalml 0.16.0` の実依存 (`black>=26.1.0`) でもあり、Jupyter formatter の利用余地もあるので削除しない。重複 checker を同時実行しない。既存の `[dependency-groups].dev` には Pixi と非互換の古い制約（Black、isort、mypy 等）がある。default 運用は Pixi であり、今回の quality は独立環境を正規経路とする。研究環境全体の依存整理は別途利用箇所を確認してから行う。

shfmt は継続的な shell 整形需要が出た場合、Runic / JET は Julia、TypeScript compiler は TypeScript の実コードを採用した場合だけ検討する。JS / Biome と独立 SQL / SQLFluff は現 tree に対象がないので導入しない。埋込み SQL のためだけに抽出基盤を作らない。

## 採用版の資料

quality は Ruff 0.15.20、mypy 2.1.0、ShellCheck 0.11.0、pre-commit 4.6.0、pytest 9.1.1 を lock する。更新時はこの版と新しい版の挙動を比較する。

- [Ruff 0.15.20: defaults と CLI 選択](https://github.com/astral-sh/ruff/blob/0.15.20/README.md)
- [mypy 2.1.0: 既存コードへの段階適用](https://github.com/python/mypy/blob/v2.1.0/docs/source/existing_code.rst)
- [ShellCheck 0.11.0 release](https://github.com/koalaman/shellcheck/releases/tag/v0.11.0)
- [lintr 3.3.0-1: NA 比較](https://github.com/r-lib/lintr/blob/v3.3.0-1/R/equals_na_linter.R)、[空系列](https://github.com/r-lib/lintr/blob/v3.3.0-1/R/seq_linter.R)
- [styler 1.11.0: scope と AST 検証](https://styler.r-lib.org/reference/style_file.html)
- [Pixi の独立環境](https://pixi.prefix.dev/latest/workspace/multi_environment/)、[pre-commit の対象選択](https://pre-commit.com/#usage)
