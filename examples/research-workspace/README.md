# 保存済みの経済研究結果と表図

記述統計の例は、表示操作用の固定値と12行の合成データから計算した集計を使う。標本構成表、主仕様・別仕様のイベントスタディ、Table 1、群間比較、標本の推移、時系列、ヒストグラム、密度、累積分布、箱ひげ図を保存する。

## 専門計算の保存結果

`models/` は、独立に指定した8つの合成経済について、実行済みの入力仕様・データ・結果を保存する。各ケースの研究質問、採用した計算、結果 ID は次のとおりである。既存の11項目に、これらの結果から31項目の表図を追加した。

| 研究質問 | 採用した対象と計算 | 結果 ID | 入力仕様・保存結果 |
| --- | --- | --- | --- |
| 段階的な導入後に成果はいつ変わるか。 | 未処置群を対照とする DR-DID、群・時点別 ATT と動学集計 | `specialist-did-r01` | [仕様](models/did-spec.json)・[結果](models/did-result.json) |
| 費用シフターを用いる投資効果の信頼集合はどの範囲を含むか。 | `ivDiag::AR_test` の95% Anderson–Rubin 集合、第一段階・誘導形・2SLS | `specialist-weak-iv-r01` | [仕様](models/weak-iv-spec.json)・[結果](models/weak-iv-result.json) |
| 申請資格の閾値で成果はどれだけ変わるか。 | `rdrobust::rdrobust` の sharp RDD、バイアス補正後の局所効果と90%区間 | `specialist-rdd-r01` | [仕様](models/rdd-spec.json)・[結果](models/rdd-result.json) |
| 企業0と1の合併が価格・シェア・厚生をどう変えるか。 | 120市場の需要・供給 GMM、推定限界費用を固定した所有統合 | `specialist-blp-supply-r01` | [仕様](models/blp-supply-spec.json)・[結果](models/blp-supply-result.json) |
| 異質性を固定した需要モデルは製品シェアをどう再現するか。 | 12市場のランダム係数需要、推定する平均係数と固定する異質性係数 | `specialist-blp-fixed-r01` | [仕様](models/blp-fixed-spec.json)・[結果](models/blp-fixed-result.json) |
| 更新費用の上昇が更新確率と状態価値をどう変えるか。 | 5状態の動学的離散選択、NFXP・CCP、更新費用を0.5効用単位増加 | `specialist-ddc-r01` | [仕様](models/replacement-spec.json)・[結果](models/replacement-result.json) |
| 一時的な産出税が消費・資本の経路と厚生をどう変えるか。 | 20期の代表的家計、初期・終端資本を固定し最初の10期に5%の税 | `specialist-growth-r01` | [仕様](models/growth-spec.json)・[結果](models/growth-result.json) |
| 生産性の上昇が定常均衡・貯蓄・資産分布・厚生をどう変えるか。 | 2所得状態・301資産点の Aiyagari、較正した経済で生産性1から1.05へ | `specialist-aiyagari-r01` | [仕様](models/aiyagari-spec.json)・[結果](models/aiyagari-result.json) |

[sources.json](models/sources.json) は結果・仕様・データ・参照コードの対応を持つ。[display-items.json](models/display-items.json) は保存済み行の表示設定を持つ。BLP の製品表示は市場0、厚生表示は市場0–2を選択する。全市場の行は registry と元の結果に保存している。係数、標準誤差、p値、区間端点、政策関数、均衡値、厚生は計算時の値を使い、桁数を表示時に設定する。

IV・RDD・更新モデル・Aiyagari の実行時コードは [historical-producers/](models/historical-producers/) に保存し、結果の producer hash と照合した。更新モデルは Git `53a633667c9fd1f2023b4660babf03b19ec025bd`、Aiyagari は Git `72019b6` のコードで計算された。DID・BLP・成長モデルの `expected_hashes` は、登録時に採用した参照コード・入力の SHA-256 を指定する。

Aiyagari の `asset_policy` と `distribution` は、表示用コピーの `columns` に `income_state` と `series` の列宣言を追加した。実行時の保存結果との相違は、この2つの表示ブロックの列宣言である。計算値、推論、較正値、診断、実行時コードの記録を保持している。

配布版の `gallery.json` は `source_result` 全体と表示行を同梱する。元入力と履歴コードは mini／project の同じ `examples/research-workspace/models/` を正本とし、registry の記録から URL とハッシュを参照する。保存行を使う `gallery register` → `gallery select` → `meeting create` → `meeting render` が、表図から研究資料までの表示経路である。

## 論文と研究スライド

同じ8つの結果 ID から、論文形式の資料と研究スライドを作成した。各ケースは研究質問、対象母集団、採用した推定・較正・固定パラメータ、推論、比較シナリオ、結果の経済的意味、数値解の診断を説明する。原結果へのリンクは保存コミット `f9093ba87cabce7bee1fdf3391656544617a8cb9` に固定している。

| 資料 | 完成出力 | 編集する本文・構成 | 選択結果 |
| --- | --- | --- | --- |
| 合成経済の推定と均衡比較 | [論文 PDF](materials/paper-pdf/index.pdf)・[HTML](materials/paper-html/index.html)：17ページ、16表図 | [本文](materials/paper/content.md)・[構成と結果定義](materials/paper/meeting.json) | [16表図](materials/selected-paper.json) |
| 合成経済の推定と均衡比較：研究スライド | [Beamer PDF](materials/slides-pdf/index.pdf)・[Quarto HTML](materials/slides-html/index.html)：10ページ、8図 | [本文](materials/slides/content.md)・[構成・発表者ノート](materials/slides/meeting.json) | [8図](materials/selected-slides.json) |

論文は既存の `manuscript`、スライドは `results` テンプレートを使う。論文は係数・均衡表と図を各ケースに配置し、スライドは主要な比較を図で示す。固定した異質性係数はランダム係数の Cholesky 因子として説明し、更新モデルの状態価値と Aiyagari の定常厚生は、それぞれ保存結果の効用・分布の定義に従う。

本文は `content.md`、順序・見出し・図表選択・発表者ノートは `meeting.json` で編集する。編集後は、プロジェクトルートから次の既存 CLI で新しい出力先へ描画する。

```sh
ERS_QUARTO=quarto
for ERS_MATERIAL in paper slides; do
  for ERS_FORMAT in html pdf; do
    python harness/research.py meeting render --root . \
      --bundle "examples/research-workspace/materials/$ERS_MATERIAL" \
      --output "outputs/specialist-${ERS_MATERIAL}-${ERS_FORMAT}" \
      --format "$ERS_FORMAT" --quarto "$ERS_QUARTO"
  done
done
```

保存した4出力は Quarto 1.11.9 で描画した。PDF は LuaLaTeX、既存の Econometrica／metropolis テンプレート、luatexja、Harano Aji フォントを使う。各出力の `render.json` は入力版、図表・テンプレートのハッシュ、実行コマンド、出力ハッシュを保存する。描画は `engine: markdown` と `--no-execute` で本文と保存図表を読み込む。

## 保存結果の登録と再描画

正本の入力から登録し直す場合は、既存の `normalize` と `prepare_gallery_items` を呼ぶ。表示用 Python 環境には `matplotlib` と日本語フォントを用意する。

```sh
python - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, 'harness')
import research_artifacts as artifacts

root = Path('.').resolve()
base = root / 'examples/research-workspace'
sources = artifacts.load(base / 'models/sources.json')
definitions = artifacts.load(base / 'models/display-items.json')
added = artifacts.normalize(root, sources)
added['items'] = artifacts.prepare_gallery_items(added, definitions)
source_commit = 'f9093ba87cabce7bee1fdf3391656544617a8cb9'
source_base = 'https://github.com/yoshimurahiroki/econ-project-mini/blob/' + source_commit + '/'
for record in added['records'].values():
    reference = record['references']['result']
    record['metadata'].update(source_url=source_base + reference['path'],
                              source_sha256=reference['sha256'], source_commit=source_commit)
for name in ('saved-results.json', 'gallery.json'):
    registry = artifacts.load(base / name)
    for field in ('records', 'statistics'):
        registry[field].update(added[field])
    if name == 'saved-results.json':
        registry['items'].update(added['items'])
    artifacts.state.save(base / name, registry)
PY
python harness/research.py gallery register --root . \
  --registry examples/research-workspace/gallery.json \
  --items examples/research-workspace/models/display-items.json \
  --output examples/research-workspace/gallery.json \
  --assets examples/research-workspace/gallery-assets
```

追加定義を渡すため、描画対象は専門計算の31項目になる。既存11項目の表示世代は保持する。

## 記述統計と表示操作

`observations.csv` と `descriptive-spec.json` が計算の入力である。`descriptive-result.json` は modelsummary 2.6.0／ggplot2 4.0.3 で生成した保存結果である。群 A の労働時間は観測値 0・2・4・6、平均 3、標準偏差 2.58198889747161、中央値 3、25%点 1.5、75%点 4.5、観測数 4 となる。変数別の利用可能標本を使うため、別の変数に欠損がある行の労働時間も集計に入る。

プロジェクトルートで実行する。

```sh
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
