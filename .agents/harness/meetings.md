# 保存済み結果から研究ミーティング資料を編集する

ローカルの marimo 画面で研究成果物を選び、前回の決定・To Do と GitHub の進捗から資料を作る。資料は `meeting.json`、`content.md`、選択した `assets/` で完結する。HTML スライド、Markdown、既存 Beamer テンプレートによる PDF、Google Slides のネイティブ形式を使用する。

## 作成

```sh
python .agents/harness/state.py --root "$PROJECT" project-view CASE --view summary \
  --github github-snapshot.json --save meeting-summary.json
python .agents/harness/research.py gallery select --root "$PROJECT" \
  --registry analysis/gallery.json sample-table main-event-study \
  --output selected-results.json
python .agents/harness/research_meetings.py create --root "$PROJECT" \
  --selection selected-results.json --project-view meeting-summary.json \
  --previous meetings/previous --output meetings/current \
  --title "研究ミーティング" --kind meeting --date 2026-11-05 \
  --issue-url https://github.com/OWNER/REPO/issues/123
```

`--previous` は初回には省略する。`--kind` は `meeting`（研究ミーティング）、`progress`（進捗報告）、`proposal`（研究計画相談）、`results`（主要結果報告）を選ぶ。作成先には新しいディレクトリを指定する。既存の資料と Google Slides の編集版を保持する。

`project-view` は既存の `project-bind` に登録した GitHub Issues / Projects を読む。`--github` にはコネクタが取得したスナップショットを渡せる。資料内の `task_snapshot` は当該ミーティング時点の記録であり、現在の担当・期限・優先順位・進捗は GitHub で編集する。研究仕様と科学的結果は既存 ERS の正本に置く。

前回の `decisions` と `next_actions`、今回の完了・進行中・次の作業、保存済みの発見・解釈・検討事項・採用判断を各セクションへ入れる。前回から新たに完了したタスクを選ぶ。各図表は結果 ID、標本、観測単位、比較群、期間、単位、推定・標準誤差・区間定義、生成元を引き継ぐ。図表の本文解釈は数値と分けて編集する。

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
python .agents/harness/research_meetings.py render --root "$PROJECT" \
  --bundle meetings/current --output outputs/current-html --format html
```

`--format markdown` は Markdown、`--format pdf` は既存の Beamer / LuaLaTeX 出力を作る。Quarto は `--no-execute` と `execute.enabled: false` で動く。新しい出力ディレクトリに完成してから公開し、`render.json` に入力版・出力ハッシュ・実行したコマンドを残す。

## GitHub のブラウザだけで編集する

1. 公開対象として選択した資料だけをリポジトリの `meetings/NAME/` に保存し、その `meeting.json` の `cloud_export` を `true` にする。初期値は `false`。原データや個票は資料に含めない。
2. GitHub 上で `content.md` の鉛筆ボタンを押して文章を変更する。`meeting.json` で順序・表示・配置を変える。複数ファイルは GitHub の Web editor（`.` キー）で同じコミットに保存できる。
3. `Render selected meeting materials` の Actions 実行を開く。Summary に完成した資料の本文・表・図を表示する。Artifacts の `meeting-...` から自己完結した `index.html` を取得できる。
4. 同じブラウザ操作で修正を保存する。変更された資料のジョブだけが再実行される。レンダラーや共通表示テンプレートの変更は対象資料の表示を更新する。

Actions は資料と表示テンプレートだけを取得する。分析環境、データ、DVC、MLflow、推定スクリプトを取得・起動しない。GitHub Pages の設定やローカル PC / Docker への接続は不要。Issue の Related research に資料ディレクトリ、Actions 実行、Google Slides 編集先を結ぶ。

## Google Slides の独立した編集版

```sh
python .agents/harness/research_meetings.py google-slides \
  --bundle meetings/current --output outputs/current-google-slides.json
```

このパケットは Google Slides API の `createSlide`、ネイティブのテキスト・表・図のリクエストを持つ。接続済み Google Drive / Slides で新規プレゼンテーション（`application/vnd.google-apps.presentation`）を作り、`requests` を `batchUpdate` に渡す。`images` のローカル PNG/JPEG は接続済みツールの画像アップロード引数で渡す。公開済み画像を使用する場合は `--asset-base-url` にその資料の HTTPS URL を指定できる。

発表者ノートは作成後の `slides[].slideProperties.notesPage.notesProperties.speakerNotesObjectId` を取得し、パケットの `speaker_notes` を対応するノート形状へ `insertText` する。作成先はユーザーの Drive の `ChatGPT` フォルダーを使用する。資料の文章・順序・図表配置は Google Slides の GUI で編集する。

```sh
python .agents/harness/research_meetings.py link-edition --bundle meetings/current \
  --url https://docs.google.com/presentation/d/PRESENTATION_ID/edit \
  --expected-revision CURRENT_SOURCE_SHA256 --kind google-slides
```

返された編集 URL と生成元の版を `editions` に追記する。再生成では新しいプレゼンテーションを作り、編集済みプレゼンテーションの ID を書き込み先に使わない。GitHub 原稿と Google Slides 編集版をそれぞれ独立した版として保持する。

## 依存関係と保存範囲

分析・データ更新は既存の研究 DAG、図表の表示更新はギャラリー、会議資料の文章・構成更新はこのレンダラーが担当する。原データ・推定結果・表示用集計の生成元は分析時に保存する。通常の閲覧や資料編集は選択済みの保存結果を読む。再現パッケージは対応する成果物の作成・更新・再現実行を選択した際に既存 `research.py` の経路で作る。
