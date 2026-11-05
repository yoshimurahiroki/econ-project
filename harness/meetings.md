# 保存済み結果から研究ミーティング資料を編集する

ローカルの marimo 画面で研究成果物を選び、前回の決定・To Do と GitHub の進捗から資料を作る。資料は `meeting.json`、`content.md`、選択した `assets/` で完結する。HTML スライド、Markdown、既存 Beamer テンプレートによる PDF、Google Slides のネイティブ形式を使用する。

## 作成

```sh
python harness/state.py --root "$PROJECT" project-view CASE --role manage --view summary \
  --github github-snapshot.json --save meeting-summary.json
python harness/research.py gallery select --root "$PROJECT" \
  --registry analysis/gallery.json sample-table main-event-study \
  --output selected-results.json
python harness/research.py meeting create --root "$PROJECT" \
  --selection selected-results.json --project-view meeting-summary.json \
  --previous meetings/previous --output meetings/current \
  --title "研究ミーティング" --kind meeting --date 2026-11-05 \
  --issue-url https://github.com/OWNER/REPO/issues/123
```

`--previous` は初回には省略する。`--kind` は次の６種類から選ぶ。作成先には新しいディレクトリを指定する。

| `--kind` | 内容 | HTML / PDF |
| --- | --- | --- |
| `brief` | 研究質問、データ・標本、分析仕様、保存結果、解釈、次の作業 | 文書 / Econometrica |
| `progress` | 前回判断、完了成果、現在の作業、結果、次の作業 | スライド / Beamer |
| `proposal` | 研究質問・推定対象、採用計画、記述統計、設計相談、判断 | スライド / Beamer |
| `results` | 主要結果、仕様比較、発見、解釈、次の作業 | スライド / Beamer |
| `meeting` | 前回の決定とTo Do、今回の作業・結果・解釈・判断、次回To Do | スライド / Beamer |
| `manuscript` | Data、Empirical specification、Results、図表、Interpretation | 文書 / Econometrica |

テンプレートは既存の `tex/slides/meeting_templates.json` に置く。原稿の Data・仕様・Results は `project-view` に渡す `data_description`、`specification_description`、`results_summary` から初期化できる。本文は `content.md` で編集する。図表は選択した結果 ID と保存値を引き継ぐ。

`project-view` は既存の `project-bind` に登録した GitHub Issues / Projects を読む。`--github` にはコネクタが取得したスナップショットを渡せる。資料内の `task_snapshot` は当該ミーティング時点の記録であり、現在の担当・期限・優先順位・進捗は GitHub で編集する。研究仕様と科学的結果は既存 ERS の正本に置く。

前回資料の `content.md` で編集した決定・To Do を引き継ぐ。該当本文が空欄なら `decisions` と `next_actions` を使う。今回の完了・進行中・次の作業、保存済みの発見・解釈・検討事項・採用判断を各セクションへ入れ、前回から新たに完了したタスクを選ぶ。各図表は結果 ID、標本、観測単位、比較群、期間、単位、推定・標準誤差・区間定義、生成元を引き継ぐ。図表の本文解釈は数値と分けて編集する。

## 原稿と構成

`content.md` の `<!-- section:ID -->` に続く文章が本文になる。`meeting.json` の `sections` が表示順、見出し、表示・非表示、配置、図表 ID、注記、発表者ノートを持つ。

| 編集対象 | 編集する項目 |
| --- | --- |
| 本文 | `content.md` の該当セクション |
| スライド順 | `sections` 配列の並べ替え |
| 見出し・表示 | `title`、`visible` |
| 図表の選択・順 | `artifacts` の ID 配列 |
| 配置 | `layout`: `stack`、`figure-left`、`figure-right`、`figures` |
| 注記・発表者ノート | `caption`、`speaker_notes` |
| 追加・削除 | 両ファイルに同じ ID を追加、または構成から削除 |

ローカルの marimo はこれらをフォームで編集する。既存保存版のハッシュを照合してから明示的な保存ボタンで反映する。科学的定義を変更する場合は既存の仕様更新・結果登録へ戻す。表示用の資料編集では推定プログラムを呼び出さない。

```sh
python harness/research.py meeting render --root "$PROJECT" \
  --bundle meetings/current --output outputs/current-html --format html
```

`--format markdown` は Markdown、`--format pdf` は LuaLaTeX 出力を作る。文書は既存の `tex/paper/pandoc_template.latex` と Econometrica の class・設定を使い、スライドは既存の `tex/slides/pandoc_template.latex`、metropolis、早稲田色、日本語フォントを使う。PDF用には保存済みPDF・PNG・JPEGを優先し、SVGだけを保存した図には `rsvg-convert` を使う。

PDFの図表注記には、母集団・変数・結果別定義・生成元の識別子も入れる。セクションの `caption` は最後の図表の注記に続けて表示し、発表者ノートは別に保持する。図の高さとテンプレートの注記サイズでスライド内に配置し、文書では短い表の全行と注記を同じページに置く。

Quarto は独立した作業ディレクトリで `engine: markdown` と `--no-execute` により本文・保存図表を描画する。図は `sections[].artifacts` で選び、本文は文章・数式・箇条書き・リンクに使う。保存済み図表のハッシュを照合し、新しい出力ディレクトリへ完成版を保存する。`render.json` は入力版、消費した図表・テンプレートのハッシュ、実行したコマンド、Quartoの版、出力ハッシュを保持する。

## GitHub のブラウザだけで編集する

1. 公開対象として選択した資料だけをリポジトリの `meetings/NAME/` に保存し、その `meeting.json` の `cloud_export` を `true` にする。初期値は `false`。`cloud_formats` に `["html", "pdf"]` のように出力形式を指定する。新規資料はHTML・PDFを選択する。原データや個票は資料に含めない。
2. GitHub 上で `content.md` の鉛筆ボタンを押して文章を変更する。`meeting.json` で順序・表示・配置を変える。複数ファイルは GitHub の Web editor（`.` キー）で同じコミットに保存できる。
3. `Render selected meeting materials` の Actions 実行を開く。ブラウザで原稿を保存すると、`cloud_formats` の各形式を描画する。`Run workflow` の `format: configured` は同じ指定を使い、`html`・`pdf`・`markdown` はその形式を選ぶ。Summary は完成した本文・表・図、Artifacts の `meeting-...` は完成資料を返す。HTMLは自己完結した `index.html` になる。`cloud_formats` を持たない既存資料はHTMLを使う。
4. 同じブラウザ操作で修正を保存する。変更された資料のジョブだけが再実行される。レンダラーや共通表示テンプレートの変更は対象資料の表示を更新する。

Actions の選択ジョブは資料の指定を読み、`cloud_export: true` の資料を選ぶ。描画ジョブは選択した資料ディレクトリと表示テンプレートを取得する。PDFではQuarto ActionsがTinyTeXを用意し、metropolis・日本語フォント・図表用パッケージを導入する。Issue の Related research に資料ディレクトリ、Actions 実行、Google Slides 編集先を結ぶ。

## Google Slides の独立した編集版

```sh
python harness/research.py meeting google-slides \
  --bundle meetings/current --output outputs/current-google-slides.json
```

このパケットは Google Slides API の `createSlide`、ネイティブのテキスト・表・図のリクエストを持つ。接続済み Google Drive / Slides で新規プレゼンテーション（`application/vnd.google-apps.presentation`）を作り、`requests` を `batchUpdate` に渡す。`images` のローカル PNG/JPEG は接続済みツールの画像アップロード引数で渡す。公開済み画像を使用する場合は `--asset-base-url` にその資料の HTTPS URL を指定できる。

発表者ノートは作成後の `slides[].slideProperties.notesPage.notesProperties.speakerNotesObjectId` を取得し、パケットの `speaker_notes` を対応するノート形状へ `insertText` する。作成先はユーザーの Drive の `ChatGPT` フォルダーを使用する。資料の文章・順序・図表配置は Google Slides の GUI で編集する。

```sh
python harness/research.py meeting link-edition --bundle meetings/current \
  --url https://docs.google.com/presentation/d/PRESENTATION_ID/edit \
  --expected-revision CURRENT_SOURCE_SHA256 --kind google-slides
```

返された編集 URL と生成元の版を `editions` に追記する。再生成では新しいプレゼンテーションを作り、編集済みプレゼンテーションの ID を書き込み先に使わない。GitHub 原稿と Google Slides 編集版をそれぞれ独立した版として保持する。

パケットの出力後、接続済みツールによる新規プレゼンテーションの作成、`batchUpdate`、発表者ノートの設定、返却された編集URLの登録までを実行する。パケットはその入力であり、`editions` は実作成された資料を指す。`--source-revision` はパケットに記録した元版を指定できる。`--expected-revision` には登録時点の現在版を渡す。

## 依存関係と保存範囲

分析・データ更新は既存の研究 DAG、図表の表示更新はギャラリー、会議資料の文章・構成更新はこのレンダラーが担当する。原データ・推定結果・表示用集計の生成元は分析時に保存する。通常の閲覧や資料編集は選択済みの保存結果を読む。再現パッケージは対応する成果物の作成・更新・再現実行を選択した際に既存 `research.py` の経路で作る。

## 公式仕様とテンプレート

- [Quarto の実行設定](https://quarto.org/docs/computations/execution-options.html)：`engine: markdown` による文書描画。
- [Quarto Beamer](https://quarto.org/docs/presentations/beamer.html)：見出しによるスライド分割、図表の段組、PDF表示設定。
- [Quarto の論文テンプレート](https://quarto.org/docs/journals/templates.html)：既存のPandocテンプレートとLaTeX出力。
- [Econometrica公式LaTeX配布案内](https://www.e-publications.org/ecta/support/)と[配布元](https://github.com/vtex-soft/texsupport.econometricsociety-ecta)：本プロジェクトのclass・設定・原稿テンプレートの出所。
- [Quarto Actions](https://github.com/quarto-dev/quarto-actions)：GitHub上のQuarto・TinyTeX設定。
- [Quarto の図の寸法](https://quarto.org/docs/authoring/figures.html#figure-sizing)と[LaTeX needspace](https://ctan.org/pkg/needspace)：PDFスライドの図の高さと文書の短表の改ページ。
