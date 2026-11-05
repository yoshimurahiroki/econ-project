<a id="demand-01"></a>

## DEMAND-01　離散選択需要

消費者 \(i\) の製品 \(j\)、市場 \(t\) の効用を \(u_{ijt}=\delta_{jt}+\mu_{ijt}+\varepsilon_{ijt}\)、外部選択の平均効用を0とする。\(\delta_{jt}=x_{jt}'\beta-\alpha p_{jt}+\xi_{jt}\) であり、\(\varepsilon\) が独立極値なら

\[
s_{jt}=\int\frac{\exp(\delta_{jt}+\mu_{ijt})}
{1+\sum_k\exp(\delta_{kt}+\mu_{ikt})}\,dF(i).
\]

同質logitでは \(\log s_j-\log s_0=x_j'\beta-\alpha p_j+\xi_j\) を得る。価格は品質誤差 \(\xi\) と連動するため、費用シフターなど効用へ直接入らない変動を使う。市場規模は外部シェアを決め、その選択が弾力性と厚生へ影響する。同質選好で $\delta_1=\log2,\delta_2=0$、外部選択を0とすると、分母は4、各製品シェアは0.5と0.25、外部シェアは0.25である。シェアの和は1、$\log(s_1/s_0)=\log2$ の残差は0となる。推定を伴う異質選好の例はDEMAND-02を使う。

入れ子ロジット（nested logit）は製品を巣 $h$ に分け、巣内の選択を相関させる。外部財の効用を0、$\delta_j=x_j'\beta-\alpha p_j+\xi_j$、共通の巣内相関パラメータを $0\le\rho<1$ とする。$D_h=\sum_{j\in h}\exp[\delta_j/(1-\rho)]$ を求めると、巣内で製品 $j$ を選ぶ割合は $\exp[\delta_j/(1-\rho)]/D_h$、巣のシェアは $s_h=D_h^{1-\rho}/(1+\sum_gD_g^{1-\rho})$ である。両者の積が製品シェア $s_j$ となり、$\rho=0$ では通常のlogitに戻る。

同質選好では $\log(s_j/s_0)=x_j'\beta-\alpha p_j+\rho\log(s_j/s_h)+\xi_j$ を得る。価格と巣内シェアは品質誤差と相関するため、両方の係数を推定するには、品質誤差と直交し、統制後も両変数を独立に動かす操作変数が要る。すべての巣に製品が一つなら $\log(s_j/s_h)=0$ となり、$\rho$ は識別されない。[PyBLPの入れ子ロジット](https://pyblp.readthedocs.io/en/stable/_notebooks/tutorial/logit_nested.html) とecon-dataの既存例 `blp-nested-free` には、製品・市場ごとの巣を `nesting_ids` で渡す。需要推定の入力と価格均衡はDEMAND-02・03を使う。

一定の貨幣限界効用 $\alpha>0$ の下で、潜在消費者一人の余剰変化は $\log(1+\sum_gD_g^{1-\rho})/\alpha$ の政策前後差である。価格を固定し、効用0の3製品を二つと一つに分け、$\rho=.5,\alpha=1$ とする。3製品のシェアは $(.207107,.207107,.292893)$、外部シェアは $.292893$ である。二製品の巣から一つを除くと余剰変化は $\log3-\log(2+\sqrt2)=-.129335$ となる。価格も変わる政策では変更後の価格を解き、その効用で同じ差を求める。

random-coefficients logitは \(\mu_{ijt}=x_{jt}'\Sigma\nu_i\) のように嗜好を異質化し、近い製品への代替を表す。価格への異質性はその定義域と貨幣限界効用を指定する。

