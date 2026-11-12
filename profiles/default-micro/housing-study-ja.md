# 通勤アクセスと床供給の政策評価

Profile: `default-micro`. Research form: measurement, spatial equilibrium and welfare. Functions: abstract, introduction, measurement, model, counterfactuals and conclusion. Reader: economics researcher. Language: Japanese.

## Input card

Use the independently authored [housing specification](../../skills/econ-data/examples/housing/specification.json), ID `housing-transport-v1`, and its [executable example](../../skills/econ-data/examples/housing/run.py). The fictional city has three districts, 12,000 workers and separate floor owners. The saved `result-index.json` supplies `decision_quantities`; its bound native results supply district allocations. Monetary passages divide thousand JPY by 1,000 to display million JPY per representative operating year. The worker income equivalent uses baseline prices; owner income includes the annual policy charge.

Composition operation: open with access changing residence-workplace choices, connect those choices to wages and rents, then evaluate the policy through worker gains, owner income and annual resource costs. Give each measurement and model paragraph the economic function needed by the subsequent policy comparison.

## Abstract

通勤交通の整備は、働く場所と住む場所の組合せを変え、賃金と賃料を通じて便益を配分する。本研究は、3地区・労働者12,000人の架空都市で、中心部と郊外を結ぶ交通整備と、郊外の床供給を20%拡張する政策を評価する。交通整備による年間の純所得換算便益は1,768.830百万円となる。床供給の拡張を組み合わせると、労働者の所得換算便益は2,837.550百万円、政策費用を支払った所有者の所得変化は−285.665百万円となる。両者を合計した純便益2,551.884百万円に基づき、交通整備と床供給拡張の組合せを選ぶ。

## Introduction

中心部と郊外の移動時間が短くなると、労働者が評価する居住地と勤務地の組合せが変わる。労働者の移動は地区ごとの労働供給と住宅需要を動かし、企業の雇用と事業用床の利用も賃金と賃料に応じて調整される。この調整を通じて、交通整備の便益が労働者と床所有者に配分される。

本研究は、同じ12,000人が暮らす3地区の都市について、交通整備と床供給拡張の政策を比較する。都市の年間資源予算は1,500百万円である。政策の選択は、労働者の所得換算便益と所有者の純所得変化を合計して行う。交通アクセス、床供給、資源費用を同じ人口と期間で評価し、実行する政策を決める。

## Measurement and model

地区の居住者数と就業者数は、小地区と事業所の記録をそれぞれ集計して構築する。賃料は契約の年間収入総額を賃貸床面積の合計で割り、1平方メートルあたりの金額とする。地区の土地面積と9組の居住地・勤務地間の移動時間を結合することで、人口、価格、密度、交通を同じ地区単位で扱う。

労働者は、賃金、賃料、通勤時間と居住環境から居住地と勤務地を選ぶ。企業は労働と事業用床を使って財を生産し、その限界生産物と要素価格から雇用と床利用を決める。住宅用と事業用の床需要の合計が、各地区の床供給に一致する。就業者と居住者の密度は、生産性と居住環境を通じて次の立地選択へ作用する。

採用した弾力性と通勤費用の係数を用い、地区の居住者数、就業者数、賃料から基準均衡の賃金、生産性、居住環境と床供給を復元する。基準の平均年賃金は4百万円である。この基準均衡を引き継ぎ、中心部と郊外の移動時間を40分から20分へ短縮する政策と、郊外の床供給を20%拡張する組合せを計算する。

## Policy comparison

交通整備の年間費用は300百万円である。床供給を拡張する組合せでは、追加する66,640.067平方メートルの床サービスを含め、年間費用は833.121百万円となる。床所有者がこの費用を負担する。財の産出は、労働者の消費、政策費用支払い後の所有者の消費、政策に使う資源へ配分される。

交通整備による労働者の所得換算便益は1,704.463百万円となり、所有者の純所得は64.367百万円増加する。床供給の拡張を組み合わせると、労働者の便益は2,837.550百万円となる。所有者の賃料収入は547.455百万円増加し、政策費用支払い後の所得変化は−285.665百万円となる。同じ年と人口について合計した純便益は2,551.884百万円である。

交通と床供給の変化は、地区間の立地配分と、労働者・所有者間の所得配分を同時に動かす。労働者の便益を基準価格で所得へ換算し、所有者の純所得と合計することで、その調整を政策の判断基準へ結び付ける。

## Conclusion

年間の純所得換算便益に基づき、交通整備と床供給拡張の組合せを選ぶ。費用833.121百万円と純便益2,551.884百万円が、年間予算と便益の比較を与える。居住地・勤務地の選択、床市場の調整、費用負担を一つの計算へ接続することで、都市全体の政策判断が得られる。
