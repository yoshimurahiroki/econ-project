# 保存済み結果の合成表示例

この例は表示操作用に作成した固定値を使う。標本構成表と、主仕様・別仕様を含むイベントスタディ図を保存する。数値は実証結果を表さない。データ取得・推定・再推論は実行しない。

プロジェクトルートで実行する。

```sh
python harness/research.py gallery register --root . \
  --registry examples/research-workspace/saved-results.json \
  --output examples/research-workspace/gallery.json
python harness/research.py gallery list --root . \
  --registry examples/research-workspace/gallery.json
python -m marimo run harness/research_gallery.py -- \
  --root . --registry examples/research-workspace/gallery.json
```

`gallery.json` は表示用行・設定・保存された来歴を持つ。`gallery-assets/` は登録コマンドが生成した SVG・PNG・HTML・Markdown 表を持つ。会議資料には `sample-composition` と `event-study` の ID を明示選択する。
