# 保存済みのモデル計算

`models/` は、既存の推定・均衡計算の入力、採用仕様、実行結果と生成元を保持する。`models/sources.json` が対応を定義する。数値結果を再計算せず、指定した結果を既存の成果物登録と描画に利用する。

`historical-producers/` は保存結果の生成時コードである。現在の実行は各専門ランナーの `run` と採用済み仕様を使う。

研究表・図・原稿・ミーティング資料の作成手順は [成果物管理](../../skills/econ-writing/references/result-artifacts.md) と [ミーティング資料](../../harness/meetings.md) に集約する。
