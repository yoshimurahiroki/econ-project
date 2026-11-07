# 保存済みの経済研究結果と表図

このディレクトリは、11件の専門計算と1件の記述統計について、入力・実行結果・生成元・原稿・代表図表を保存する。`gallery.json` が表示用の正本である。数値行、定義、推論、元の結果を保持し、同じ結果を使う図表のメタデータを `shared_metadata` に共通化する。元の結果と完全一致する表示行は `rows_ref` で同じ JSON 内の保存結果を参照する。既存の読み込み関数が各項目の行とメタデータへ展開する。

## 計算の入力と実行結果

| 研究上の比較 | 採用した計算 | 結果 ID | 入力・結果 |
| --- | --- | --- | --- |
| 段階的導入後の成果と導入前診断 | 未処置群を対照とする DR-DID、群・時点別 ATT、動学集計、共同検定 | `specialist-did-r01` | [仕様](models/did-spec.json)・[結果](models/did-result.json) |
| 弱い操作変数による投資効果の推論 | 95% Anderson–Rubin 集合、第一段階・誘導形・2SLS | `specialist-weak-iv-r01` | [仕様](models/weak-iv-spec.json)・[結果](models/weak-iv-result.json) |
| 申請資格の閾値での成果の変化 | sharp RDD、バイアス補正後の局所効果と90%区間 | `specialist-rdd-r01` | [仕様](models/rdd-spec.json)・[結果](models/rdd-result.json) |
| 所有統合による価格と厚生の変化 | 120市場の需要・供給 GMM、推定限界費用を固定した価格均衡 | `specialist-blp-supply-r01` | [仕様](models/blp-supply-spec.json)・[結果](models/blp-supply-result.json) |
| 固定した異質性の下での製品シェア | 12市場のランダム係数需要、平均係数の推定と異質性係数の固定 | `specialist-blp-fixed-r01` | [仕様](models/blp-fixed-spec.json)・[結果](models/blp-fixed-result.json) |
| 嗜好別の損失と複数市場の厚生 | ランダム係数需要・供給、所有統合後の均衡、市場人口による集計 | `specialist-blp-random-r01` | [仕様](models/blp-random-merger.json)・[結果](models/blp-random-merger-result.json) |
| 更新費用の上昇と更新行動 | 5状態の動学的離散選択、NFXP・CCP、更新費用の反実仮想 | `specialist-ddc-r01` | [仕様](models/replacement-spec.json)・[結果](models/replacement-result.json) |
| 一時的な産出税と消費・資本の移行 | 20期の代表的家計、初期・終端資本を固定した均衡経路 | `specialist-growth-r01` | [仕様](models/growth-spec.json)・[結果](models/growth-result.json) |
| 生産性と定常均衡・資産分布 | 2所得状態・301資産点の Aiyagari、政策関数・分布・厚生 | `specialist-aiyagari-r01` | [仕様](models/aiyagari-spec.json)・[結果](models/aiyagari-result.json) |
| 同一標本による推定器の比較 | OLS・IV2SLS、保存された係数・標準誤差・モデル定義の共通表 | `specialist-common-ols-r01`・`specialist-common-iv2sls-r01` | [OLS仕様](models/common-ols-spec.json)・[IV仕様](models/common-iv2sls-spec.json)・[比較結果](materials/writing/common-regression-results.md) |

[sources.json](models/sources.json) が結果・仕様・データ・参照コードを対応させる。[historical-producers/](models/historical-producers/) は、保存結果を生成した旧版コードを保持する。各結果の実行時ハッシュと、登録時に採用した `expected_hashes` は、それぞれの記録に従う。元データ、採用仕様、数値計算の履歴は `models/` に残す。

[display-items.json](models/display-items.json) は、保存した項目 ID に対する見出し・列・表示設定だけを持つ。行と経済学的定義は `gallery.json` から読む。全市場の結果と詳細な診断は元の結果にも保持する。係数、標準誤差、p値、区間端点、政策関数、均衡値、厚生の丸めは表示時に行う。

## 代表原稿と査読対応

| 原稿 | 固有の論証 |
| --- | --- |
| [段階的導入と成果](materials/writing/causal-paper.md) | 群・時点別効果、動学集計、点別区間と導入前共同検定を、それぞれの推定・検証対象へ結ぶ。 |
| [一時的な産出税と移行経路](materials/writing/growth-paper.md) | 資源制約、Euler条件、初期・終端条件から、消費・資本の調整と家計厚生を説明する。 |
| [嗜好の異質性と企業統合](materials/writing/structural-heterogeneity-paper.md) | 需要の異質性、企業の最適反応、価格均衡、嗜好別余剰と市場人口による厚生集計を接続する。 |

[日英改稿・翻訳と読者別説明](materials/writing/revision-examples.md)は、同じ保存結果から研究者向けの論証、英語表現、非専門家向けの行動・誘因の説明を比較する。`profiles/default-micro/` の日英例文は、各文章機能の参照として維持する。

査読対応は原指摘、修正箇所、保存結果、評価、回答文を既存の `research_evidence.py review` で対応させる。因果研究の[回答文](materials/writing/causal-referee-response.md)と[契約](materials/writing/causal-referee-contract.json)は、集約効果・導入前診断・比較群への指摘を扱う。成長研究の[回答文](materials/writing/referee-response.md)と[契約](materials/writing/referee-contract.json)は、厚生関数・評価期間・政府吸収の説明を扱う。履歴記録内の旧版ハッシュと生成時の参照先は、その実行を表す。

## 保存結果を選び、必要な形式を生成する

`gallery-assets/` は、異なる計算を示す代表 SVG と共通回帰表の TeX を保持する。保存した全49項目は一覧・比較・選択・表示編集に使える。指定した項目だけを描画する。

```sh
python harness/research.py gallery list --root . \
  --registry examples/research-workspace/gallery.json
python harness/research.py gallery render --root . \
  --registry examples/research-workspace/gallery.json \
  --item specialist-common-ols-iv-table --format pdf --format tex
python harness/research.py gallery select --root . \
  --registry examples/research-workspace/gallery.json \
  specialist-did-r01-event-study specialist-did-r01-group_time \
  --output outputs/selected-results.json
```

`--format` の既定は PNG 一形式である。`--format svg`、`pdf`、`html`、`tex` は利用先に応じて指定する。登録だけを行う場合は `--no-render` を使う。

```sh
python harness/research.py gallery register --root . \
  --registry examples/research-workspace/gallery.json \
  --items examples/research-workspace/models/display-items.json \
  --output outputs/gallery.json --no-render
python -m marimo run harness/research_gallery.py -- \
  --root . --registry examples/research-workspace/gallery.json
```

新しい計算結果の登録は、その結果の仕様・入力・生成元を指定した `normalize` から始める。既存結果の表示変更は保存済み行を読む。

## 研究スライド

[スライド本文](materials/slides/content.md)、[構成・保存図表・発表者ノート](materials/slides/meeting.json)、[Beamer PDF](materials/slides-pdf/index.pdf)を保持する。図表を選んだ資料が独立して編集・描画できる経路を、この一組で示す。PNG はブラウザとネイティブ Google Slides、PDF 図は Beamer に使用する。

本文は `content.md`、順序・見出し・図表選択は `meeting.json` で編集する。次のコマンドは編集後の HTML を新しい出力先へ描画する。

```sh
python harness/research.py meeting render --root . \
  --bundle examples/research-workspace/materials/slides \
  --output outputs/slides-html --format html
```

`--format pdf` は既存の metropolis・LuaLaTeX・日本語フォントで PDF を生成する。完成ファイルと `render.json` を保存し、Markdown には本文が使用する画像も同梱する。Quarto・TeX の中間ファイルは本文・構成・テンプレートから再生成する。`render.json` は実際の入力版、図表とテンプレートのハッシュ、コマンド、出力ハッシュを保持する。

## 記述統計と配布範囲

`observations.csv`、`descriptive-spec.json`、`descriptive-result.json` は、12行の合成データと実行済み集計を対応させる。Table 1、群間比較、標本推移、時系列、ヒストグラム、密度、累積分布、箱ひげ図は同じ保存結果から選ぶ。変数ごとの利用可能標本、分母、群、期間、単位を表示へ引き継ぐ。

例の正本は `econ-project-mini` と同期先の `econ-project` に置く。インストールするスキルは実装・規則・テンプレートを配布し、この研究例を GitHub から参照する。
