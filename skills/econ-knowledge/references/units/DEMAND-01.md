<a id="demand-01"></a>

## DEMAND-01　離散選択需要

消費者 \(i\) の製品 \(j\)、市場 \(t\) の効用を \(u_{ijt}=\delta_{jt}+\mu_{ijt}+\varepsilon_{ijt}\)、外部選択の平均効用を0とする。\(\delta_{jt}=x_{jt}'\beta-\alpha p_{jt}+\xi_{jt}\) であり、\(\varepsilon\) が独立極値なら

\[
s_{jt}=\int\frac{\exp(\delta_{jt}+\mu_{ijt})}
{1+\sum_k\exp(\delta_{kt}+\mu_{ikt})}\,dF(i).
\]

同質logitでは \(\log s_j-\log s_0=x_j'\beta-\alpha p_j+\xi_j\) を得る。価格は品質誤差 \(\xi\) と連動するため、費用シフターなど効用へ直接入らない変動を使う。市場規模は外部シェアを決め、その選択が弾力性と厚生へ影響する。同質選好で $\delta_1=\log2,\delta_2=0$、外部選択を0とすると、分母は4、各製品シェアは0.5と0.25、外部シェアは0.25である。シェアの和は1、$\log(s_1/s_0)=\log2$ の残差は0となる。推定を伴う異質選好の例はDEMAND-02を使う。

nested logitは同じ巣の選択相関を導入する。random-coefficients logitは \(\mu_{ijt}=x_{jt}'\Sigma\nu_i\) のように嗜好を異質化し、近い製品への代替を表す。価格への異質性はその定義域と貨幣限界効用を指定する。

