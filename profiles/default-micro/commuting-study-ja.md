# 通勤支援と雇用の配分

Profile: `default-micro`. Research form: calibrated economy and randomized policy evaluation. Functions: abstract, introduction, model, results and conclusion. Reader: economics researcher. Language: Japanese.

## Input card

Use the independently authored [commuting specification](../../skills/econ-data/examples/commuting/specification.json), ID `commuting-market-v1`, and its [executable example](../../skills/econ-data/examples/commuting/run.py). The completed example uses 48 markets, 4,800 households and three subsidy arms over eight weeks. Numerical passages consume the saved employment, wage, household-surplus, firm-profit, fiscal-spending and social-surplus results. Employment-rate displays multiply the saved workers-per-household contrast and interval endpoints by 100. Each 95% interval describes its named fixed contrast.

Composition operation: open with the policy choice, connect the subsidy to household participation and firms' hiring, then use the common population and monetary accounting to rank the policy arms. Apply the passage's sentence rhythm and argument order to the current study's own quantities.

## Abstract

通勤支援の給付額は、家計の就業と企業の採用を通じて政策の便益と費用を変える。本稿は48の労働市場からなる架空経済で支援額を無作為に割り当て、8週間の雇用と社会的余剰を評価する。4万円支援の雇用効果は9.19ポイント、95%信頼区間は[5.75, 12.63]ポイントである。家計余剰、企業利益、就業の社会的便益、財政費用を合計した1世帯あたりの余剰効果は1.68千円、95%信頼区間は[-4.44, 7.80]千円となる。三つの給付額を推定余剰で順位付けすると、4万円支援が選ばれる。

## Introduction

通勤費用への補助は、家計が就業から得る手取りを増やす。企業は増えた労働供給に応じて採用を拡大し、賃金が調整する。給付額の選択には、この家計と企業の反応を同じ政策比較に取り込む必要がある。

本稿は、家計の就業選択と企業の採用を結ぶ架空経済を構築し、0円、2万円、4万円の通勤支援を比較する。各市場に給付額を無作為に割り当て、雇用、家計余剰、企業利益、財政支出を同じ4,800世帯について測る。政策評価は8週間の社会的余剰を目的とし、各給付額が生む配分を共通の金額で評価する。

## Model and design

各家計は、賃金と給付の合計から通勤費用を引いた額を家事生産の価値と比較して就業を選ぶ。企業は、雇用の拡大とともに低下する限界生産物を賃金と比較して採用数を決める。市場賃金は家計の労働供給と企業の労働需要を一致させる。補助は家計の留保賃金を引き下げ、雇用と賃金を同時に変える。

各市場は100世帯で構成され、48市場のうち16市場ずつに三つの給付額を割り当てる。支援対象となる世帯の就業と市場賃金を8週間の同じ期間で評価する。推定対象は各給付額の割当効果であり、市場単位の割当確率を使って世帯平均の効果を推定する。

## Results

4万円支援は、0円の割当に対して雇用率を9.19ポイント高める。95%信頼区間は[5.75, 12.63]ポイントである。市場賃金の推定変化は労働者1人あたり-28.79千円となる。給付による労働供給の拡大と賃金調整が、企業の採用増加を支える。

この調整を通じて、家計と企業の双方に便益が生じる。4万円支援による家計余剰の推定増加は1世帯あたり5.61千円、標準誤差は1.14千円である。企業利益の推定増加は同じ世帯数で換算して14.88千円、標準誤差は2.81千円となる。財政支出の増加は1世帯あたり23.32千円である。

政策評価では、家計余剰と企業利益に就業の社会的便益を加え、給付と資金調達の費用を計上する。就業の社会的便益を1人10万円、財政支出の超過負担を0.2倍とする評価式から、4万円支援の推定余剰効果は1世帯あたり1.68千円となる。95%信頼区間は[-4.44, 7.80]千円である。この評価式と共通の対象世帯が、三つの給付額の順位を定める。

## Conclusion

本例の推定余剰に基づく選択は4万円支援である。政策の効果は、家計の就業拡大、賃金調整、企業の採用増加を通じて生じる。これらの反応を財政費用と合わせることで、支援額の選択を社会的余剰の比較へ結び付けた。
