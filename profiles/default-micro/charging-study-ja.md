# 充電サービスの企業結合と余剰の配分

Profile: `default-micro`. Research form: structural demand, equilibrium and welfare. Functions: abstract, introduction, model, identification, results and conclusion. Reader: economics researcher. Language: Japanese.

## Input card

Use the independently authored [charging specification](../../skills/econ-data/examples/charging/specification.json), ID `charging-merger-v1`, and its [executable example](../../skills/econ-data/examples/charging/run.py). The fictional economy has 100 markets, three services per market and 100,000 potential 10-kWh charging occasions over one operating week. The saved `result-index.json` supplies `decision_quantities` and `uncertainty`. Monetary passages convert hundred JPY to million JPY by dividing by 10,000. Producer and total surplus include the real integration cost. Each 95% interval describes its named demand coefficient.

Composition operation: open with joint pricing and procurement, connect drivers' choices to the welfare comparison, then use the ownership and cost scenarios to explain the merger decision. Apply this progression and sentence rhythm to the current study's own model and results.

## Abstract

充電サービスの企業結合は、利用者が支払う価格と充電に使われる資源を変える。本研究は100市場からなる架空経済で需要を推定し、共同価格設定と、結合するサービスの限界費用を20%削減する統合を評価する。結合前の費用で共同価格を設定すると、1週間の総余剰は1.093百万円減少する。調達費用の削減と統合費用を加えた純余剰の増加は0.697百万円となる。消費者余剰の変化は−2.458百万円、生産者余剰の変化は3.155百万円である。総余剰に基づく判断は企業結合の承認を選ぶ。

## Introduction

充電事業者2社の結合により、両社の価格が共同で決められる。結合企業は、自社のサービス間で乗り換える利用者から得る利益を価格設定に織り込む。調達費用の削減は、利用者に充電を提供する費用を変える。企業結合の判断は、利用者の参加、サービス間の代替、充電に使われる資源を通じて定まる。

本研究は、各市場に3サービスを持つ100市場の架空経済を分析する。利用者はサービスまたは外部選択肢を選び、企業は価格を選ぶ。競争当局は、1週間に10万回の潜在的な充電機会について消費者余剰と生産者余剰を評価する。結合前、結合前の費用による共同価格設定、調達費用を削減する統合の順に比較し、所有と費用の変化が厚生に及ぼす作用を明らかにする。

## Model and identification

利用者の効用は、サービスの品質、製品固有の需要要因、支払う価格によって決まる。ロジット需要は、この効用を各サービスのシェアと外部選択肢の選択へ結び付ける。企業は、自社製品から得る利益を最大にする価格を選ぶ。共同所有の下では、結合する2サービス間の代替が同じ利益目標へ入る。

調達価格の変動は限界費用と均衡価格を動かす。この変動を用い、300の製品・市場観測から品質と定数項を含む需要式の価格係数を推定する。価格係数は100円あたり−0.824正規化効用単位、95%信頼区間は[−1.005, −0.643]である。品質係数は品質指数1単位あたり0.615正規化効用単位、95%信頼区間は[0.513, 0.717]である。

推定した需要と結合前の価格条件から限界費用を求める。次に、その費用による共同価格と、結合する2サービスの費用を20%削減した共同価格を解く。統合には0.200百万円の実物資源を使う。3つの比較は、同じ利用者、サービス品質、外部選択肢、営業週を共有する。

## Results and welfare

結合前の限界費用による共同価格設定では、消費者余剰が−3.454百万円、生産者余剰が2.361百万円変化する。総余剰の変化は−1.093百万円となる。所有の変化は、両サービス間の代替を通じて結合企業の価格設定の誘因を変える。

調達費用を削減する統合では、統合費用を含む総余剰が38.775百万円となる。結合前の総余剰は38.078百万円である。同じ週と人口で評価した純増加は0.697百万円となる。消費者余剰の変化は−2.458百万円、生産者余剰の変化は3.155百万円である。この余剰計算が、利用者と企業への配分を競争当局の判断基準へ結び付ける。

## Conclusion

総余剰に基づく判断は、調達費用を削減する企業結合の承認を選ぶ。共同価格設定と調達費用の削減が、利用者と企業の間の余剰配分を決める。同じ人口について両方の作用と統合費用を評価することで、判断を支える金額の比較が得られる。
