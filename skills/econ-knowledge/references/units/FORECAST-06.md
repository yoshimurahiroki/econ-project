<a id="forecast-06"></a>

## FORECAST-06　ベイズ意思決定と情報価値

事後分布、期待効用による行動、追加標本の情報価値（EVSI）と完全情報価値（EVPI）の定義は[STAT-07](https://github.com/yoshimurahiroki/econ-project-mini/blob/main/skills/econ-knowledge/references/chapters/02-probability-statistics.md#stat-07)を使う。信号の生成と探索を伴う反復選択は[INFO-02](https://github.com/yoshimurahiroki/econ-project-mini/blob/main/skills/econ-knowledge/references/chapters/05-information-behavior.md#info-02)、事後積分は[ECON-09](https://github.com/yoshimurahiroki/econ-project-mini/blob/main/skills/econ-knowledge/references/chapters/10-econometrics.md#econ-09)へ接続する。調査・実験の対象、観測時点、変更できる行動と利益の発生時点を揃え、取得費用と待機中の利益差を同じ評価へ入れる。

FORECAST-01と同じ事象確率0.3、保護費用12通貨、無保護時の事象損失50通貨を使う。情報なしでは保護の期待費用12が無保護の15より小さい。完全情報があれば事象時だけ保護し、期待費用は $0.3\times12=3.6$、完全情報の価値は $12-3.6=8.4$ 通貨となる。

部分的なsignalの価値は、信号ごとに事後確率と最適行動を更新して求める。高状態と低状態の事前確率が各 .5、投資の貨幣利得が高状態10・低状態−6、投資しない利得が0とし、貨幣利得を線形に評価する。情報なしの投資期待利得は2である。状態を確率 .8 で正しく示す対称signalなら、高signal後の高状態確率は .8、低signal後は .2、それぞれの発生確率は .5である。高signalでは投資の条件付き期待利得6.8、低signalでは−2.8なので投資しない。情報後の期待価値は3.4、signalの総価値は1.4となる。費用が同じ貨幣単位で1.4未満なら購入する。signalの精度や事前確率を推定する時点と、費用を払って行動を変えられる期限を揃える。

情報を取得しても、すべての信号で現在と同じ行動が最適なら、同じ利得と行動集合の下で取得費用控除前の情報価値は0となる。売上予測を更新する調査でも、発注上限や設備の不可逆性が行動を固定する場合はこの判定を使う。行動を変えられる信号では、更新後に実行する発注・投資・治療の価値を信号確率で加重する。実験中にも配分を変更する場合はINFO-02の信念状態のBellman問題を使う。

