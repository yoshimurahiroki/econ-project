# 保存済み結果の合成表示例

この例は、表示操作用の固定値と12行の合成データから計算した記述統計を使う。標本構成表、主仕様・別仕様のイベントスタディ、Table 1、群間比較、標本の推移、時系列、ヒストグラム、密度、累積分布、箱ひげ図を保存する。

`observations.csv` と `descriptive-spec.json` が計算の入力である。`descriptive-result.json` は modelsummary 2.6.0／ggplot2 4.0.3 で生成した保存結果である。群 A の労働時間は観測値 0・2・4・6、平均 3、標準偏差 2.58198889747161、中央値 3、25%点 1.5、75%点 4.5、観測数 4 となる。変数別の利用可能標本を使うため、別の変数に欠損がある行の労働時間も集計に入る。

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

`gallery.json` は既存の `registry.items` に表示行・設定・来歴を保存する。`gallery-assets/` は SVG・PNG・HTML・PDF・LaTeX を持つ。画面で選択・比較・表示編集・解釈編集を行い、選択した項目を会議資料へ渡す。

```sh
python harness/research.py gallery select --root . \
  --registry examples/research-workspace/gallery.json \
  descriptive-demo-r01-table1 descriptive-demo-r01-distributions-hours-box event-study \
  --output outputs/selected-results.json
```

記述統計を同じ仕様から再生成するコマンドは次のとおりである。プロジェクトの R 初期化と採用ライブラリを使う。ギャラリーの閲覧・編集は保存済み集計を読む。

```sh
python skills/econ-data/scripts/research_data.py describe \
  examples/research-workspace/descriptive-spec.json --root . \
  --output outputs/descriptive-example
```
