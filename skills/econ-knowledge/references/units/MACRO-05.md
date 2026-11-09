<a id="macro-05"></a>

## MACRO-05　RBCと動学一般均衡

合理的期待（rational expectations）は、各主体が情報集合 \(\mathcal I_t\) に基づいて使う条件付き期待を、同じモデルの最適行動と市場清算が生む遷移法則に一致させる条件である。予想する集計遷移を \(H\)、その下での個別最適政策を \(h_H\)、個別行動の集計から得る遷移を \(\Phi(H)\) とすると、均衡は \(H=\Phi(H)\) を満たす。家計は集計価格の法則を所与として選択し、その選択を集計した数量が市場を清算する。政策変更後は変更後の制度と行動から \(H\) を解き直す。この定義は[QuantEconの合理的期待均衡](https://github.com/QuantEcon/lecture-python.myst/blob/4d82fffbb1280f8f6980a45dbe518e677f5c9a39/lectures/rational_expectations.md#definition-of-rational-expectations-equilibrium)の予想法則と実現法則の固定点に対応する。

代表家計は \(E_0\sum_t\beta^t[u(c_t)-v(n_t)]\)、企業は \(Y_t=A_tK_t^\alpha N_t^{1-\alpha}\) とする。競争と完全市場の下で

\[
u'(c_t)=\beta E_t[u'(c_{t+1})(1-\delta+r_{t+1})],\quad
v'(n_t)=u'(c_t)w_t,
\]

\[
c_t+K_{t+1}=Y_t+(1-\delta)K_t,\quad
r_t=F_K,\quad w_t=F_N.
\]

技術を \(\log A_{t+1}-\log\bar A=\rho(\log A_t-\log\bar A)+\varepsilon_{t+1}\)、\(\bar A>0,|\rho|<1\) とする。無ショックの定常状態を計算し、線形摂動または大域的動学計画法で政策を求める。以下の検査では \(\bar A=.337962963\)、\(A_0=\bar A\)、全期 \(\varepsilon_t=0\) とし、生産性を一定に保つ。定常点の検査として $u(c)=\log c$、$v(n)=\chi n^2/2$、$\alpha=.36,\beta=.96,\delta=.08$、$K=N=1$ とする。$A=.337962963$、$\chi=.838478105$ なら $Y=.337962963,c=.257962963,r=.121666667,w=.216296296$ であり、資源・Euler・労働条件の残差はいずれも丸め前に0である。これは無ショックの決定論的定常点の検査であり、確率的定常分布を計算したものではない。ショックへの応答は動学系を解いて得る。観測方程式はモデルの水準・成長率・労働時間を統計系列へ対応させる。尤度には状態空間表現、SMMには変動・共分散・IRFのモーメントを使う。

実測との接続では、労働投入を一人当たり時間か総時間で固定し、人口と単位を観測側にも反映する。例えば \(y_t^{obs}=100(\log Y_t-\log Y_{t-1})+\epsilon_t^y\)、\(h_t^{obs}=\log N_t+\epsilon_t^h\) とし、測定誤差の分散と共分散を指定する。生産性の持続性と革新分散は残差やその自己共分散、資本分配率は要素支払、減耗は資本stockと投資の会計から情報を得る。選好や複数ショックを同時推定する際は、観測系列に対する尤度やモーメントの導関数が局所的に十分な階数を持つかを調べる。線形化の固有根と状態数で解の存在・一意性を確認し、求めた政策関数を非線形の家計Euler式、労働条件、資源制約に戻してショックと状態の格子上で残差を測る。

Blanchard–Kahn条件は、先決変数の初期値から有界な経路を一意に選べるかを判定する。定常点からの線形同次系を \(z_{t+1}=Az_t\)、\(z_t=(k_t',q_t')'\) とし、\(k_t\) は \(n_k\) 個の先決変数、\(q_t\) は当期に調整する変数とする。\(A\) の固有根は単位円上にないとする。絶対値が1未満の固有根に対応する一般化固有空間の直和を安定不変部分空間とする。その次元が \(n_k\) と一致し、その基底を \(Q_s=(Q_k',Q_q')'\) と分割した \(Q_k\) が正則なら、\(q_0=Q_qQ_k^{-1}k_0\) が有界経路を定める。これは不安定不変部分空間の係数を0にする条件を初期値へ解き戻した式である。一般化固有値問題では同じ先決・調整変数の区分を保ってQZ分解を使う。ショックの条件付き平均法則を加えた系でも、その法則と将来予想を同時に満たす政策係数を求める。[QuantEconの線形合理的期待モデル](https://github.com/QuantEcon/lecture-python.myst/blob/a1cd90c5ef6d6f05277318f47fe21eda60fa5e6b/lectures/re_with_feedback.md#another-perspective)は、固有空間から初期価格を選び、予想法則へ戻す計算を示している。

計算では、所与の集計遷移に対する個別Bellman方程式と、集計遷移を一致させる外側の固定点を別々に評価する。前者の収縮率は個別最適化の収束を定め、後者は \(\Phi(H)-H\) と市場清算残差で判定する。予測調査から別の信念更新則を推定する設計では、その更新則と情報の到着時点を状態へ組み込み、採択した予想の下で同じ最適化と清算条件を解く。

固定労働 $N_t=1$ の確率的モデルでは、家計の効用を $E_0\sum_t\beta^t\log c_t$、資源制約を $c_t+k_{t+1}=e^{z_t}k_t^\alpha+(1-\delta)k_t$、技術を $z_{t+1}=\rho z_t+\epsilon_{t+1}$ とする。$z$ は対数生産性の観測値である。

資本の対数偏差を $x_t=\log(k_t/k^*)$ とする。資源式を線形化して消費係数を資本係数で表し、条件付きEuler式の資本係数を安定根について解き、技術係数を続けて求める。

非線形の条件付きEuler残差は、将来ショックの分布についてGauss–Hermite積分で評価する。大域解には元の非線形条件を満たす政策を求める。

`MC-stochastic-rbc`はこの固定労働・対数効用・Cobb-Douglas生産・Gaussian AR(1)技術の実行契約である。既存の`research_dsge.py run`は観測された技術系列からAR(1)を推定し、校正済みの選好と技術係数で局所政策を解く。`structural_model="stochastic_rbc"`に`implementation="dolo"`を指定すると、同じ経済方程式を持つ採択済みYAMLの[公式Dolo時間反復](https://github.com/EconForge/dolo.py/blob/33f873eef42d9644b5a0705a63fb3a34de5c2825/src/dolo/algos/time_iteration.py)へ渡す。別の経済モデルのYAMLは`structural_model="dolo_yaml"`でその原始的要素と均衡条件を指定する。

Doloでは`yaml_import`でモデルを読み、`find_steady_state`と`residuals`で定常条件を照合し、`time_iteration(details=True)`の`dr`、`error_res`、`error_step`、`iterations`と`converged`を保存する。`converged`は更新幅または反復時の残差の終了条件を満たした状態である。最終政策を採択した格子と外生状態で評価し、同じ離散モデルを[公式`dolo.numeric.residuals.F`](https://github.com/EconForge/dolo.py/blob/33f873eef42d9644b5a0705a63fb3a34de5c2825/src/dolo/numeric/residuals.py)へ渡して最終政策の元Euler残差を保存する。内点の等式と、拘束点の境界・相補性をそれぞれモデルの条件で判定する。この外部入口は校正値を保持して政策関数を求める。

