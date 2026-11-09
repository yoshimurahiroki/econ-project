<a id="spatial-02"></a>

## SPATIAL-02 居住、通勤と住宅清算

個人が居住地 $i$ と勤務地 $j$ を選び、合成財と住宅面積のCobb–Douglas効用、住宅支出比率 $0<\beta<1$、賃金所得 $w_j$、住宅amenity $A_i$、通勤の効用費用 $\tau_{ij}$ を置く。最適住宅面積は $h_{ij}=\beta w_j/R_i$、間接効用の確定部分は定数を除き $V_{ij}=A_i+\log w_j-\beta\log R_i-\tau_{ij}$ となる。独立な極値型の選択ショックを仮定すると、居住・勤務地の選択確率は $P_{ij}=\exp(V_{ij})/\sum_{k,l}\exp(V_{kl})$ である。通勤費 $\tau_{ij}$ が下がると、その組の選択確率が高くなり、代替組の確率が変わる。

人口 $N$ の住宅面積需要 $N\sum_jP_{ij}\beta w_j/R_i$ を面積供給 $H_i(R_i)$ に等置し、各勤務地の労働需要と $N\sum_iP_{ij}$ を一致させる。賃金、地代、通勤者数を同時に更新して清算させる。住宅在庫、地代、勤務地別賃金、居住地・勤務地の流れと交通時間を結び、交通改善などの外生的変化を用いて移動費用と選好を推定する。政策後は家賃と賃金の応答を含む効用のログサムを再計算する。地域の未観測amenityが賃金・家賃と共変する場合、地域間の観測相関だけでは選好を識別できない。地域別労働需要を動かし未観測amenityの変化と直交する変動を用い、除外条件と支配的な産業ショックへの曝露を調べる。住宅需要の反応は、一人当たり面積の変化と居住者数の変化を合わせて計算する。

政策対象地区の家賃や賃金だけでは、他地区へ波及する価格変化の集計を捉えられない。例えば対象地区の10人の一人当たり間接効用が0.1低下し、他地区の90人がそれぞれ0.002上昇すると、住民全体の変化は $10(-0.1)+90(0.002)=-0.82$ である。各地域の人口が異なるため、一人当たりの波及が小さくても総和は無視できない。この例は同じ尺度で測った住民効用の合計であり、金銭的な社会便益に換算するときは限界効用と住宅所有者の受取額も加味する。

一人一戸の居住枠を数える仕様では、地区の選択便益を $V_i=A_i-\alpha\log R_i$、居住枠需要を $N_i=N\exp(V_i)/\sum_k\exp(V_k)$、供給を $H_i=K_iR_i^{\varepsilon_i}$ とする。供給を増やす政策はまず供給曲線を右に動かし、家賃低下によってその地域への居住を増やす。周辺地域でも人口と家賃が変わるため、すべての地域で $N_i=H_i$ を満たす家賃の組を解く。外部からの人口流入を認める開放都市なら、都市全体の人口も外部選択肢の価値に一致するまで調整する。

住宅供給の反実仮想を二地区で計算する。人口100人は各1単位の労働を供給し、生産 $F(L)=100L$ の競争企業が全員を雇うため賃金は100である。各人の住宅支出比率を $\beta=.25$、地区の確定的amenityを同一とし、地区固有ショックを独立な単位尺度極値分布とする。地区の住宅面積は政策前 $(H_1,H_2)=(100,100)$、政策後 $(400,100)$ とし、追加住宅面積は費用0で外生的に供給される。各地区の家賃 $R_i$ は $N_i(.25\cdot100/R_i)=H_i$、人口は $N_i=100R_i^{-.25}/\sum_jR_j^{-.25}$ を満たす。

基準均衡は人口 $(50,50)$、家賃 $(12.5,12.5)$、政策後は人口 $(56.887407,43.112593)$、家賃 $(3.555463,10.778148)$ となる。両地区で住宅需要と供給の差は $1.5\times10^{-14}$ 以下、人口は100に等しい。選択前の期待効用の差は $\Delta V=\log\sum_i\exp(\log100-.25\log R_i^1)-\log\sum_i\exp(\log100-.25\log R_i^0)=0.185260$ である。政策前価格で同じ効用を得る所得変化は一人当たり $100(e^{\Delta V}-1)=20.353113$ で、100人の等価変分は2035.311298である。住宅所有者は居住者とは別の家主であり、賃料収入をすべて合成財に支出する。各均衡で労働者の合成財消費は一人75、家主の賃料収入と消費は2500となり、合計消費 $100\cdot75+2500=10000$ は企業の生産 $100\cdot100$ に等しい。家主所得差は0である。所得等価額は各人が家賃を所与に受け取る額で評価する。移動費や建設費が発生する政策ではそれらを資源費用として追加し、当該費用と家主・住民の受取額を同じ人口と期間で集計する。

### Closed-city ARSW model and executable inversion

`MC-qse-commuting` specifies the ARSW (2015) mixed-use closed-city economy. In this subsection, \(\beta_g\) is the **goods expenditure share** and corresponds to the runner's `parameters.beta`; residential expenditure has share \(1-\beta_g\). Let \(N\) be the fixed worker population, \(t_{ij}\) travel time from residence \(i\) to workplace \(j\), \(q_i\) the common commercial/residential floor rent, and \(w_j\) the wage. Workers have iid Fréchet tastes with shape \(\epsilon>1\). Define
\[
\phi_{ij}=e^{-\epsilon\kappa t_{ij}}B_i^\epsilon q_i^{-(1-\beta_g)\epsilon}w_j^\epsilon,
\quad \pi_{ij}=\frac{\phi_{ij}}{\sum_{k,l}\phi_{kl}},\quad
R_i=N\sum_j\pi_{ij},\quad L_j=N\sum_i\pi_{ij},\quad I_i=N\sum_j\pi_{ij}w_j.
\]
The homogeneous traded good has price one. Firms produce \(Y_i=A_iL_i^\alpha S_i^{1-\alpha}\) using labor and commercial floors. Competitive factor prices satisfy \(w_i=\alpha Y_i/L_i\) and \(q_i=(1-\alpha)Y_i/S_i\). Residential demand is \(H_i=(1-\beta_g)I_i/q_i\), and floor clearing requires \(S_i+H_i=F_i\). All locations have positive residential and workplace populations, and their commercial shares \(S_i/F_i\) lie in \((0,1)\).

Productivity and amenities respond to the distributions through
\[
A_i=a_i\left[\sum_j e^{-\delta t_{ij}}L_j/\mathrm{area}_j\right]^\lambda,
\qquad
B_i=b_i\left[\sum_j e^{-\rho t_{ij}}R_j/\mathrm{area}_j\right]^\eta.
\]
The fixed primitive vectors are \(a,b,F,\mathrm{area}\); \(\alpha,\beta_g,\epsilon,\kappa,\lambda,\delta,\eta,\rho\) are supplied calibrated parameters. Population, rents, production and both density indices adjust in a policy equilibrium. A supplied travel-time matrix determines the commuting and spillover kernels.

Given positive observed \(R,L,q,\mathrm{area}\), equal population and employment totals, and finite nonnegative travel times, log-coordinate origin-destination balancing matches \(e^{-\epsilon\kappa t}\) to the residence and workplace shares. Its destination multipliers recover relative \(w^\epsilon\); origin multipliers and \(q\) recover relative \(B^\epsilon\). The baseline employment-weighted mean wage and population-weighted mean total amenity each equal one. Observed rents are divided by `baseline.wage_numeraire`, the mean wage in the same currency and period. Firm prices imply \(A_i=(w_i/\alpha)^\alpha(q_i/(1-\alpha))^{1-\alpha}\). Floor demands recover \(F\); division by the baseline density indices recovers \(a,b\). This inversion holds the supplied elasticities fixed. Policy calculations retain these baseline units.

The existing `research_macro_extended.py` runs `model="qse_commuting"` with `operation="invert_baseline"` or `"counterfactual"`. A counterfactual consumes `saved_solution:{path,sha256}` and positive `productivity_hat`, `amenity_hat`, `floor_space_hat` or a replacement `travel_time` matrix. It restores the saved primitives and complete baseline equilibrium. SciPy trust-region least squares solves the log-coordinate labor choice, residence choice, zero-profit and floor-clearing equations. The returned quantities are substituted into the original market, population, probability and resource conditions. The [macro reference](https://github.com/yoshimurahiroki/econ-project-mini/blob/main/skills/econ-design/references/macro-models/spatial.md#closed-city-commuting-and-floor-space-equilibrium) specifies the complete input and saved-result interface.

Expected optimized worker utility is \(U=\Gamma(1-1/\epsilon)(\sum_{ij}\phi_{ij})^{1/\epsilon}\). The same \(N\) workers are evaluated before their tastes are drawn. Set \(\chi=U_s/U_b-1\). Raising every potential baseline wage by \(\chi\), at baseline rents, gives the scenario expected utility. The expected income equivalent is
\[
EV_W=\chi N\sum_{ij}\pi^b_{ij}w^b_j
=\chi\sum_j w^b_jL^b_j.
\]
Separate external floor owners receive all \(q_iF_i\) and consume the numeraire good; their linear-utility equivalent is \(EV_O=\sum_i(q_i^sF_i^s-q_i^bF_i^b)\). The saved baseline-price income equivalent sums \(EV_W+EV_O\) with unit weights. Firms earn zero profit. Each equilibrium satisfies \(\sum_iY_i=\beta_g\sum_iI_i+\sum_iq_iF_i\). Travel is a utility cost, and floor hats change endowed space with zero construction resource cost. The result retains the worker utility ratio, worker income equivalent, owner income change and firm-profit change as named quantities. Local outcomes, commuting flows and aggregate accounting feed the existing statistics and gallery interfaces.

The official calculation sources are [QSETRANSPORT's baseline inversion](https://github.com/Ahlfeldt/QSETRANSPORT-toolkit/blob/c3e212843bff81a9d69df75bb7e6aac022bea8c8/QUETRANSPORT-PythonOnly/src/python/functions/inversion/baseline.py) and its [closed-city damped equilibrium calculation](https://github.com/Ahlfeldt/QSETRANSPORT-toolkit/blob/c3e212843bff81a9d69df75bb7e6aac022bea8c8/QUETRANSPORT-PythonOnly/src/python/functions/equilibrium/model.py). The [independent Julia implementation](https://github.com/SebKrantz/Quantitative-Spatial-Economics/blob/4e673a3c7d7470a137bdfc34d9c1325178ab0568/AhlfeldtReddingSturmWolf-ECMA-2015/ahlfeldt_redding_sturm_wolf_density_model.jl) states the same commuting, production and density equations. The supplied travel-time intervention enters those kernels directly.

### Open-city commuting equilibrium with free migration

`MC-qse-open-city` uses the same production, floor clearing, commuting probabilities, density spillovers and calibrated primitives. Workers choose city residence before their location-pair tastes are drawn and can attain the fixed reservation expected utility outside the city. The saved original baseline determines that reservation utility, \(\bar U=U_b\). City population \(N_s>0\) adjusts jointly with wages, rents and the residence and employment distributions. Its additional equilibrium condition is
\[
\log\left[\frac{\Gamma(1-1/\epsilon)(\sum_{ij}\phi^s_{ij})^{1/\epsilon}}{\bar U}\right]=0.
\]
The solver adds \(\log N_s\) to the unknowns and this migration condition to the original labor, residence, production and floor equations. A transport improvement or a change in amenities, productivity or endowed floors changes the city population and its internal allocation. The same homogeneous traded good and external floor owners retain the goods accounting above.

Select `model="qse_open_city"`, `operation="counterfactual"` and a hash-bound `saved_solution` from the QSE runner. The existing `solve_qse` restores the original baseline and reevaluates its economic equations before solving the policy. `scenario` and `solver` retain the closed-city input definitions. The result preserves `qse_numerical_contract_version`, the actual producing code and original saved-source identity. The versioned economic equations govern reuse across file changes.

Free migration fixes expected worker utility at \(U_s=U_b\). The income equivalent for the original baseline population, \((U_s/U_b-1)\sum_j w^b_jL^b_j\), is zero at equilibrium. The result separately saves city population change, its ratio, the expected-utility ratio and external floor-owner income change \(\sum_i(q_i^sF_i^s-q_i^bF_i^b)\). Each saved quantity carries its population and units. The official comparison uses [QSETRANSPORT `solve_closure("open", ..., reservation_utility=U_b)`](https://github.com/Ahlfeldt/QSETRANSPORT-toolkit/blob/c3e212843bff81a9d69df75bb7e6aac022bea8c8/QUETRANSPORT-PythonOnly/src/python/functions/equilibrium/model.py) at the same primitives, travel times and reservation utility.

### City-hinterland migration with a finite utility elasticity

`MC-qse-imperfect-mobility` keeps the ARSW within-city equations and adds a fixed regional population choosing between city and hinterland. Let the observed baseline urban share be \(s_b\in(0,1)\), the saved city population be \(N_b\), and its expected city opportunity value be \(U_b\). With calibrated shape \(\zeta>0\), set
\[
\bar N=N_b/s_b,\qquad \widetilde U=U_b^\zeta(1-s_b)/s_b.
\]
City and hinterland log opportunity values have independent extreme-value shocks with scale \(1/\zeta\). Workers choose the city before drawing its residence-workplace tastes. The resulting population condition is
\[
N=\bar N\frac{U^\zeta}{U^\zeta+\widetilde U},\qquad
\operatorname{logit}(N/\bar N)-\operatorname{logit}(s_b)=\zeta\log(U/U_b).
\]
The elasticity of city population to city utility is \(\zeta(1-N/\bar N)\). Policies change both population and city utility. Every candidate population enters commuting flows, employment and residential density spillovers, floor clearing and goods accounting. The regional population and hinterland opportunity value remain fixed. This adopts the migration primitive from [ABSJ2027 `solver`](https://github.com/Ahlfeldt/ABSJ2027-toolkit/blob/b5c8d32ccab117cb7b85f581cf29569c1eea893a/Python/functions/solver.py) and its [urban-share inversion](https://github.com/Ahlfeldt/ABSJ2027-toolkit/blob/b5c8d32ccab117cb7b85f581cf29569c1eea893a/Python/functions/find_utilde.py), by Ahlfeldt, Baum-Snow and Jedwab, *The Skyscraper Revolution: Global Economic Development and Land Savings*. The city retains the preceding ARSW production, mixed-use floor supply and commuting specification.

The regional welfare index is \(V=(U^\zeta+\widetilde U)^{1/\zeta}\). Under the common outer-shock constant normalization, \(\log V\) is expected optimized log opportunity value per regional worker. The comparison for the same regional population is
\[
\log(V_s/V_b)=\frac{1}{\zeta}\log\left[(1-s_b)+s_b(U_s/U_b)^\zeta\right].
\]
The saved regional ratio and log-value change retain those utility units. The conditional city income equivalent \((U_s/U_b-1)\sum_jw_j^bL_j^b\) evaluates city opportunities for the original baseline city population at baseline rents. The external floor-owner income difference retains its existing monetary definition. The result saves these three objects with their population and unit definitions, together with city migration and hinterland population.

Select `model="qse_imperfect_mobility"`, `operation="counterfactual"`, a hash-bound QSE `saved_solution`, and `migration={zeta,baseline_urban_share,source}`. The existing `research_macro_extended.py run` and `solve_qse` restore the baseline and calibrated ARSW primitives. One population log-odds coordinate and the migration equation extend the same trust-region equilibrium solve. Original population-supply and log-odds residuals accompany all existing market residuals. A saved result retains the migration calibration for subsequent policies; it supplies the same original baseline and complete named welfare, statistics and display objects. The [macro execution contract](https://github.com/yoshimurahiroki/econ-project-mini/blob/main/skills/econ-design/references/macro-models/spatial.md#city-and-hinterland-with-imperfect-mobility) defines the input, numerical coordinates and saved outputs.

