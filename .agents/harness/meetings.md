# 保存済み結果から研究ミーティング資料を編集する

ローカルの marimo 画面で研究成果物を選び、前回の決定・To Do と GitHub の進捗から資料を作る。資料は `meeting.json`、`content.md`、選択した `assets/` で完結する。HTML スライド、Markdown、既存 Beamer テンプレートによる PDF、Google Slides のネイティブ形式を使用する。

## 作成

```sh
python .agents/harness/state.py --root "$PROJECT" project-view CASE --role manage --view summary \
  --github github-snapshot.json --save meeting-summary.json
python .agents/harness/research.py gallery select --root "$PROJECT" \
  --registry analysis/gallery.json sample-table main-event-study \
  --output selected-results.json
python .agents/harness/research.py meeting create --root "$PROJECT" \
  --selection selected-results.json --project-view meeting-summary.json \
  --previous meetings/previous --output meetings/current \
  --title "研究ミーティング" --kind meeting --date 2026-11-05 \
  --issue-url https://github.com/OWNER/REPO/issues/123
```

`--previous` は初回には省略する。`--kind` は次のテンプレートから選ぶ。作成先には新しいディレクトリを指定する。CLI と marimo の選択肢は、同じ `.agents/tex/slides/meeting_templates.json` を読む。

| `--kind` | 内容 | HTML / PDF |
| --- | --- | --- |
| `brief` | 研究質問、データ・標本、分析仕様、保存結果、解釈、次の作業 | 文書 / Econometrica |
| `progress` | 前回判断、完了成果、現在の作業、結果、次の作業 | スライド / Beamer |
| `proposal` | 研究質問・推定対象、採用計画、記述統計、設計相談、判断 | スライド / Beamer |
| `results` | 研究質問、デザイン、標本、Table 1、主結果、イベントスタディ、追加結果、解釈、今回の判断、次の作業 | スライド / Beamer |
| `meeting` | 前回の決定とTo Do、今回の作業・結果・解釈・判断、次回To Do | スライド / Beamer |
| `model` | 主体・選択・目的・制約、情報と時間、記号、最適化、均衡、命題と導出、比較静学、数値解、反実仮想と厚生 | スライド / Beamer |
| `structural` | モデル、観測変動と識別、データ、尤度・モーメント、解法、構造パラメータ、適合度、反実仮想、厚生、感度 | スライド / Beamer |
| `appendix` | 記号、モデル、導出と証明、識別、データ構築、推定と推論、数値計算、追加結果 | 文書 / Econometrica |
| `manuscript` | Data、Empirical specification、Results、図表、Interpretation | 文書 / Econometrica |

テンプレートは既存の `.agents/tex/slides/meeting_templates.json` に置く。原稿の Data・仕様・Results は `project-view` に渡す `data_description`、`specification_description`、`results_summary` から初期化できる。本文は `content.md` で編集する。図表は選択した結果 ID と保存値を引き継ぐ。

理論・構造資料の本文は、同じ `project-view` の `section_content` に節 ID と採用済みの Markdown 本文を指定する。`model`、`information`、`optimality`、`equilibrium`、`propositions`、`identification`、`numerical` など、選んだテンプレートの節へ数式と説明を渡す。採用したモデル契約の主体・制約・情報・均衡条件から本文を作り、識別するパラメータと観測変動、最適化条件と数値解法、反実仮想で固定する構造を明示する。記号と定義は `notation`、命題と証明は `propositions` または付録の `derivation` に置く。本文の指定は既存の自動要約より優先され、選択していない節 ID は受け付けない。

```json
{
  "research_question": "企業結合は価格と消費者余剰をどう変えるか。",
  "section_content": {
    "model": "消費者は一つの製品か外部選択肢を選ぶ。企業は所有する製品の利潤を最大化する価格を同時に選ぶ。",
    "identification": "需要式から除外した費用シフターを価格の操作変数に使う。",
    "numerical": "保存済みの需要推定値と限界費用を固定し、所有構造変更後の価格一階条件を解く。"
  }
}
```

この例は `--kind structural` に渡す本文の形を示す。実際の資料には、採用した需要式、操作変数、費用構造、均衡選択と実行済み結果を指定する。`section_content` は文書入力であり、分析仕様や保存結果を書き換えない。

テンプレートの `artifact_role` が記述統計、主結果、イベントスタディ、追加結果の挿入位置を指定する。選択結果の `metadata.report_role` で `descriptive`、`main`、`event_study`、`additional` を明示できる。指定がない結果は保存済みの図表種類で配置する。主結果の要約本文は図表の前に保持する。`project-view` に対応する文章がない場合は、選択結果の発見・解釈・検討事項・採用判断を各セクションへ引き継ぐ。

構造資料は `parameters`、`model_fit`、`counterfactual`、`welfare`、理論資料は `notation`、`mechanism`、`comparative_statics` の保存済み `report_role` も配置する。選択したテンプレートに専用節がない図表は、そのテンプレートの既存の図表節へ置く。構造パラメータは推定・較正・固定の別と単位、適合度は観測モーメントとモデルモーメント、反実仮想はシナリオ別の価格・数量・利潤・厚生を保存値で表示する。異なる単位の数量はギャラリーの別パネルを使う。図表の `model_contract`、`scenario`、`parameter_definition`、パラメータの扱い、状態価値の定義、終端条件、ストック・フローの時点定義も資料へ引き継ぐ。

標準回帰表はギャラリーが保存値から組み立てた `presentation` を引き継ぐ。MarkdownとGoogle Slidesのネイティブ表は、同じ列グループ、係数行、括弧付き標準誤差行、モデル情報、表注を使用する。元の数値行と結果IDも資料に保持する。

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
python .agents/harness/research.py meeting render --root "$PROJECT" \
  --bundle meetings/current --output outputs/current-html --format html
```

`--format markdown` は Markdown、`--format pdf` は LuaLaTeX 出力を作る。文書は既存の `.agents/tex/paper/pandoc_template.latex` と Econometrica の class・設定を使い、スライドは既存の `.agents/tex/slides/pandoc_template.latex`、metropolis、早稲田色、日本語フォントを使う。HTML・PDFの出力先には完成ファイルと `render.json` を保存する。Markdownには本文が参照する画像も保存する。編集元の本文・構成・図表は元の資料bundleに保持し、中間のQuarto・TeX・スタイルファイルは描画時に再生成する。`render.json` の `latex_files` は生成に使った各版のハッシュを記録する。PDF用には保存済みPDF・PNG・JPEGを優先し、SVGだけを保存した図には `rsvg-convert` を使う。

図表注記は母集団、標本、重み、分母、基準期、区間種類、集計規則、処置履歴と推論単位を保存値から表示する。推論の数値は図表のセルに置き、注記は推論方法と設定を表示する。保存メタデータは区間端点、検定統計量、p値の全値を保持する。PDFには変数・結果別定義・生成元の識別子も入れる。生成元の SHA-256 は先頭12桁で表示し、完全な値を資料の保存メタデータに保持する。セクションの `caption` は最後の図表の注記に続けて表示し、発表者ノートは別に保持する。図の高さとテンプレートの注記サイズでスライド内に配置し、文書では短い表の見出し・全行・注記を同じページに置く。表の長い識別子はアンダースコアで改行する。PandocアダプターはQuartoの `include-in-header` を引き継ぎ、日本語文書のPDF設定も同じ経路で適用する。

Quarto は独立した作業ディレクトリで `engine: markdown` と `--no-execute` により本文・保存図表を描画する。図は `sections[].artifacts` で選び、本文は文章・数式・箇条書き・リンクに使う。保存済み図表のハッシュを照合し、新しい出力ディレクトリへ完成版を保存する。`render.json` は入力版、消費した図表・テンプレートのハッシュ、実行したコマンド、Quartoの版、出力ハッシュを保持する。

## GitHub のブラウザだけで編集する

1. 公開対象として選択した資料だけをリポジトリの `meetings/NAME/` に保存し、その `meeting.json` の `cloud_export` を `true` にする。初期値は `false`。`cloud_formats` に `["html", "pdf"]` のように出力形式を指定する。新規資料はHTML・PDFを選択する。原データや個票は資料に含めない。
2. GitHub 上で `content.md` の鉛筆ボタンを押して文章を変更する。`meeting.json` で順序・表示・配置を変える。複数ファイルは GitHub の Web editor（`.` キー）で同じコミットに保存できる。
3. `Render selected meeting materials` の Actions 実行を開く。ブラウザで原稿を保存すると、`cloud_formats` の各形式を描画する。`Run workflow` の `format: configured` は同じ指定を使い、`html`・`pdf`・`markdown` はその形式を選ぶ。Summary は完成した本文・表・図、Artifacts の `meeting-...` は完成資料を返す。HTMLは自己完結した `index.html` になる。`cloud_formats` を持たない既存資料はHTMLを使う。
4. 同じブラウザ操作で修正を保存する。変更された資料のジョブだけが再実行される。レンダラーや共通表示テンプレートの変更は対象資料の表示を更新する。

Actions の選択ジョブは資料の指定を読み、`cloud_export: true` の資料を選ぶ。描画ジョブは選択した資料ディレクトリと表示テンプレートを取得する。PDFではQuarto ActionsがTinyTeXを用意し、metropolis・日本語フォント・図表用パッケージを導入する。Issue の Related research に資料ディレクトリ、Actions 実行、Google Slides 編集先を結ぶ。

## Google Slides の独立した編集版

```sh
python .agents/harness/research.py meeting google-slides \
  --bundle meetings/current --output outputs/current-google-slides.json
```

このパケットは Google Slides API の `createSlide`、ネイティブのテキスト・表・図のリクエストを持つ。接続済み Google Drive / Slides で新規プレゼンテーション（`application/vnd.google-apps.presentation`）を作り、`requests` を `batchUpdate` に渡す。`images` のローカル PNG/JPEG は接続済みツールの画像アップロード引数で渡す。公開済み画像を使用する場合は `--asset-base-url` にその資料の HTTPS URL を指定できる。

発表者ノートは作成後の `slides[].slideProperties.notesPage.notesProperties.speakerNotesObjectId` を取得し、パケットの `speaker_notes` を対応するノート形状へ `insertText` する。作成先はユーザーの Drive の `ChatGPT` フォルダーを使用する。資料の文章・順序・図表配置は Google Slides の GUI で編集する。

```sh
python .agents/harness/research.py meeting link-edition --bundle meetings/current \
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
- [Quarto の図の寸法](https://quarto.org/docs/authoring/figures.html#figure-sizing)：PDFスライドの図の高さ。
- [EconAgentSkills の標準表](https://github.com/JonasWeinert/EconAgentSkills/blob/c1b8b1ef7ab59e6858fe3599a39d4732e5a76142/_skills/writing/latex-tables/examples/table_main_template.tex)：係数と括弧付き標準誤差、仕様行の配置。
- [econ-research-os の記号表](https://github.com/RyanPiao/econ-research-os/blob/0b206cd043f77d787932dcb149106bb648106033/skills/econ-write/templates/notation-table.md)と[Quarto章構成](https://github.com/RyanPiao/econ-research-os/blob/0b206cd043f77d787932dcb149106bb648106033/skills/econ-write/templates/chapter-template.qmd)：記号の定義、数式、実装、適用例の対応。ERSでは同じ既存の資料構成へ接続する。
