# 企業統合による価格調整と市場厚生

## Abstract

本稿は、独自に生成された120市場の需要・供給推定結果を用い、二企業の統合が価格、シェア、厚生に与える影響を示す。推定した需要と限界費用を保持し、製品0と1の所有を統合して全企業の価格を解き直す。市場0では、製品0の価格が2.1413から2.2161へ上昇し、そのシェアは0.0732から0.0681へ低下する。潜在消費者1人当たりの消費者余剰は0.5500から0.5388へ、総余剰は1.0220から1.0154へ低下する。価格設定における自社製品間の代替の内部化が、この配分と厚生を結び付ける。

## Introduction

競合する製品が同じ企業の所有となると、一方の製品の値上げによって他方へ移る需要が、その企業の利潤に入る。本稿は、この所有関係の変更が、再調整された価格と消費者の選択を通じて市場厚生にどう現れるかを調べる。構造推定に基づく市場0の比較では、製品0と1の統合によって価格が上昇し、消費者余剰と総余剰が低下する。

需要側では、製品価格と特性xが消費者の選択を規定する。供給側では、費用シフターzと推定された需要反応が限界費用の回収を規律する。価格の効用係数は−1.1247であり、費用シフターの係数は0.3050である。需要・供給モーメントと価格設定条件を用いて、観測された価格とシェアをモデルのパラメータへ対応させる。

この計算例では、所有関係を変更し、各製品の推定限界費用と効用の定義を保持する。全企業の価格設定条件を解き直すことで、統合企業と競合企業の反応を同じ均衡へ統合する。得られたシェアと利潤を用いて、潜在消費者1人当たりの消費者余剰、生産者余剰、その和としての総余剰を比較する。

## Model and estimation

採用した需要モデルは、平均効用を価格と製品特性xで表す同質的logitである。外部選択肢の効用を基準化し、価格係数は需要モーメントから推定する。供給の費用式には定数とzを含める。zを需要の操作変数、xを供給の操作変数として用いる採用済みの排除条件が、価格と費用の識別を支える。PyBLPによる需要・供給の同時GMM推定結果を用いる。

企業fは所有する製品集合$\mathcal J_f$の利潤を最大化する。製品jの価格設定条件は、潜在消費者当たりのシェア$s_j(p)$を用いて次のように書ける。

$$s_j(p)+\sum_{k\in\mathcal J_f}(p_k-c_k)\frac{\partial s_k(p)}{\partial p_j}=0.$$

統合後には、製品0と1が同じ集合に入る。この所有変更を全市場へ適用し、推定した限界費用で価格を解き直している。以下では市場0の製品別配分と厚生を示す。

## Results

市場0で製品0の価格は2.1413から2.2161へ、製品1の価格は2.1127から2.1834へ上昇する。対応するシェアは、それぞれ0.0732から0.0681、0.0771から0.0721へ変化する。競合する製品2と3も価格を調整し、製品2は2.3698から2.3718へ、製品3は2.2467から2.2487へ上昇する。表1は、これらの価格とシェアを、それぞれの限界費用、利潤と対応させる。

表1　市場0の製品別均衡。価格と限界費用の単位は人工データの通貨単位、利潤は潜在消費者1人当たり。

| シナリオ | 市場 | 製品 | 価格 (synthetic currency units) | シェア (share) | 限界費用 (synthetic currency units) | 利潤 (synthetic currency units per potential consumer) |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 0 | 0 | 2.1413 | 0.0732 | 1.1819 | 0.0702 |
| baseline | 0 | 1 | 2.1127 | 0.0771 | 1.1492 | 0.0743 |
| baseline | 0 | 2 | 2.3698 | 0.1543 | 1.3184 | 0.1622 |
| baseline | 0 | 3 | 2.2467 | 0.1567 | 1.1923 | 0.1652 |
| counterfactual | 0 | 0 | 2.2161 | 0.0681 | 1.1819 | 0.0704 |
| counterfactual | 0 | 1 | 2.1834 | 0.0721 | 1.1492 | 0.0746 |
| counterfactual | 0 | 2 | 2.3718 | 0.1559 | 1.3184 | 0.1642 |
| counterfactual | 0 | 3 | 2.2487 | 0.1583 | 1.1923 | 0.1673 |


市場0の潜在消費者1人当たりの消費者余剰は0.5500から0.5388へ低下し、生産者余剰は0.4720から0.4765へ上昇する。総余剰は1.0220から1.0154へ低下する。消費者余剰と生産者余剰は、同じ市場、外部選択肢、通貨単位で計算されている。

## Discussion

統合企業は、製品0の値上げによって製品1へ移る需要と、製品1の値上げによって製品0へ移る需要を利潤に含める。価格設定条件に加わる交差価格反応が、値上げの誘因を生む。消費者は製品間と外部選択肢の間で選択を調整し、競合企業もその需要に応じて価格を変える。表1の価格、シェア、利潤は、この同時の調整を表している。

厚生比較では、統合後の価格とシェアから各主体の余剰を計算する。市場0では生産者余剰が増加し、消費者余剰が減少する。両者を同じ潜在消費者単位で合計した総余剰も低下する。各製品の費用を固定したこの所有変更の効果は、価格設定と消費者の代替を通じて生じる。

## Conclusion

推定した需要・供給を固定して製品0と1の所有を統合すると、市場0では価格が上昇し、消費者余剰と総余剰が低下する。潜在消費者1人当たりの総余剰は1.0220から1.0154へ変化する。統合企業が製品間の代替を内部化する価格設定と、それに応じた競合企業・消費者の調整が、この厚生変化を生む。

## English abstract

We use estimates of demand and supply from 120 independently generated markets to study a merger of firms owning products 0 and 1. We retain fitted marginal costs and re-solve every firm's pricing conditions under the new ownership structure. In market 0, the price of product 0 rises from 2.1413 to 2.2161 and its share falls from 0.0732 to 0.0681. Consumer surplus per potential consumer falls from 0.5500 to 0.5388, and total surplus falls from 1.0220 to 1.0154. The ownership change alters pricing incentives by internalizing substitution between the merging firms' products; the resulting equilibrium links these incentives to market welfare.

## Sources

- [Adopted specification](../../models/blp-supply-spec.json)
- [Executed result](../../models/blp-supply-result.json)
- [Producing pricing and welfare calculations](../../models/historical-producers/research_markets-registration.py)
