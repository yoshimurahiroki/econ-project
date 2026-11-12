# 設備更新と技術導入の投資価値

Profile: `default-micro`. Research form: dynamic discrete choice and investment. Functions: abstract, introduction, data, model, estimation, counterfactuals and conclusion. Reader: economics researcher. Language: Japanese.

## Input card

Use the independently authored [equipment specification](../../skills/econ-data/examples/equipment/specification.json), ID `equipment-renewal-v1`, and its [executable example](../../skills/econ-data/examples/equipment/run.py). The fictional panel follows 480 firms, each with one machine, for 32 quarters. The saved `result-index.json` owns cost estimates, replacement probabilities, net present gains and their joint covariance. Monetary gains use thousand JPY per machine at adoption and the same initial population, with 80 machines in each wear state. The common technology maximizes the population's mean net present gain.

1. **Output: opening paragraph; consumer: model exposition.** Connect the recurring choice to the investment that changes its future payoffs. Before: “設備更新モデルを推定する。” After: “更新技術の導入は、将来の設備交換費用を引き下げる。その投資価値は、費用の節約と、その後の維持・交換の選択から決まる。”
2. **Output: decision paragraph; consumer: conclusion.** Put adoption costs and discounted gains on the same monetary basis, then state the selected technology with its saved interval. Before: “高度技術は交換を増やす。” After: “高度技術の純現在価値は設備1台あたり213.434千円、95%信頼区間は［205.718, 221.150］千円となる。”

## Abstract

更新技術の導入は、将来の設備交換費用と維持・交換の時期を変える。本研究は、480社を32四半期にわたり観測する架空のパネルを用いて、技術導入の投資価値を評価する。動学的選択モデルにより、設備の摩耗、維持費用、交換費用を各四半期の行動へ結び付ける。高度技術による期待操業価値の現在価値増分は、設備1台あたり513.434千円となる。導入費用300千円を差し引いた純現在価値は213.434千円、95%信頼区間は［205.718, 221.150］千円である。初期の設備集団の平均純現在価値に基づき、高度技術を選ぶ。

## Introduction

摩耗した設備を交換すると、その稼働状態が回復し、当期に交換費用が発生する。維持を選ぶと、その後の四半期にも維持費用を支払う。交換費用を引き下げる技術は、今期に交換する費用と、将来に交換機会を持つ設備の継続価値をともに変える。この行動と価値の変化が、技術導入への支払額を評価する基礎となる。

本研究は、初期状態の構成を共通にした480台について、3種類の恒久的な更新技術を比較する。標準技術と高度技術の導入費用は1台あたり120千円と300千円であり、その後の交換1回あたりの費用を40千円と80千円引き下げる。各社の導入予算は350千円である。操業価値の現在価値増分から導入費用を差し引き、初期の設備集団の平均が最大となる共通技術を選ぶ。

各四半期の維持・交換の選択を使って、その行動を決める費用を推定する。次に、各技術を導入した後の操業問題を解き、同じ初期摩耗状態で価値を比較する。この手順により、観測された交換行動を恒久的な技術導入の判断へつなげる。

## Data and model

パネルには15,360件の企業・四半期観測が含まれる。各記録は、設備の摩耗状態、企業の行動、次の摩耗状態を持つ。摩耗は0から5までの6状態で表す。維持すると摩耗が1段階進んで上限の5に達し、交換すると状態0へ戻る。初期の各状態には80台を配置する。

摩耗状態$s$で維持する利得は$-cs$、交換する利得は$-R+d_k$である。$d_k$は技術$k$による交換費用の削減額を表し、利得1単位を100千円とする。企業は行動ごとの利得ショックを観測し、当期の利得と割引した継続価値の合計が最大となる行動を選ぶ。四半期の割引因子を$\beta=0.95$とすると、ショックを観測する前の価値は次式を満たす。

$$
V_k(s)=\log\left[\exp\{-cs+\beta V_k(\min(s+1,5))\}+\exp\{-R+d_k+\beta V_k(0)\}\right].
$$

摩耗が進むほど、維持の費用が交換に対して上昇する。採用したモデルでは、摩耗状態ごとの四半期行動の変動が2つの費用パラメータを識別する。同じパネルから費用を推定し、各技術の価値関数へ引き継ぐ。

## Estimates and investment comparison

維持費用の係数は摩耗1段階あたり0.3448利得単位、標準誤差は0.0098となる。交換費用の推定値は2.7919利得単位、標準誤差は0.0564である。推論には企業単位のクラスタリングを用い、同じ企業の四半期行動の依存を反映する。基準技術での交換確率は、状態0の0.1049から状態5の0.6653へ上昇する。対応する標準誤差は0.0036と0.0094である。

各技術の価値関数の増分を初期の設備集団で平均し、金額へ換算して導入費用を差し引く。標準技術の操業価値増分は244.719千円、導入費用は120千円となる。設備1台あたりの純現在価値は124.719千円、95%信頼区間は［121.234, 128.204］千円である。高度技術の操業価値増分は513.434千円、導入費用は300千円となる。純現在価値は213.434千円、95%信頼区間は［205.718, 221.150］千円である。

高度技術の純現在価値は、標準技術を1台あたり88.715千円上回り、差の95%信頼区間は［84.434, 92.996］千円となる。この比較には、同じ推定費用から得られる両技術の価値の共分散を用いる。将来の交換費用の節約と維持・交換行動の変化が、追加の導入費用に対する投資価値を決める。

## Conclusion

初期の設備集団の平均純現在価値に基づき、高度技術を選ぶ。設備1台あたりの導入費用300千円と純現在価値213.434千円が、この投資判断を支える。各四半期の選択を継続価値へ結び付けることで、設備の交換行動から恒久的な技術導入の判断が得られる。
