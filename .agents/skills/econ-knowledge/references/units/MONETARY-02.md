<a id="monetary-02"></a>

## MONETARY-02　政策目的と下限

二次近似の目的を \(E_0\sum_t\beta^t(\pi_t^2+\lambda x_t^2)\) とする。裁量政策は各時点のPhillips曲線制約の下で当期と予想を扱い、commitmentは将来政策への約束を制約系に含める。価格分散や労働供給の歪みから \(\lambda\) と目的の定義を導く。

名目金利下限 \(i_t\ge\underline i\) がある完全予見の有限期間 \(t=0,\ldots,T-1\) では、終端 \(x_T=\pi_T=0\) とし、cost-push shock \(u_t\) を含む制約を
\[
f_t=x_t-x_{t+1}+\sigma^{-1}(i_t-\pi_{t+1}-r_t^n)=0,\quad
g_t=\pi_t-\beta\pi_{t+1}-\kappa x_t-u_t=0
\]
とする。commitmentの経路は \(\sum_{t=0}^{T-1}\beta^t(\pi_t^2+\lambda x_t^2)\) をこの全期間の制約と下限の下で最小化する。乗数を \(\alpha_t,\eta_t\)、下限の乗数を \(\zeta_t\ge0\) とし、初期に継承された約束がない場合は \(\alpha_{-1}=\eta_{-1}=0\) とする。ラグランジュ関数を目的に \(\sum_t(\alpha_tf_t+\eta_tg_t-\zeta_t(i_t-\underline i))\) を加えたものとすると、一階条件と相補性は
\[
\begin{aligned}
2\beta^t\lambda x_t+\alpha_t-\alpha_{t-1}-\kappa\eta_t&=0,\\
2\beta^t\pi_t+\eta_t-\sigma^{-1}\alpha_{t-1}-\beta\eta_{t-1}&=0,\\
\sigma^{-1}\alpha_t-\zeta_t&=0,\\
i_t-\underline i\ge0,\quad\zeta_t\ge0,\quad\zeta_t(i_t-\underline i)&=0.
\end{aligned}
\]
\(\sigma>0,\ \beta\in(0,1),\ \lambda\ge0\) とし、価格式と終端が与えられた凸問題として解く。将来の約束を継承する場合は初期の過去乗数をその約束に合わせる。過去の乗数が現在の一階条件に入るのは、現在のインフレと産出が以前の期待制約に含まれていたためである。裁量では各時点に再最適化する条件と継続価値を別に定める。両者の比較では同じ実際の初期状態とショックを使い、過去の約束を引き継ぐかも明示する。

例えば1期間、$\sigma=\kappa=\lambda=1$、$r_0^n=-1$、$u_0=0$、下限0、終端 $x_1=\pi_1=0$ とする。最適解は $i_0=0,x_0=\pi_0=-1$、損失2である。乗数 $\alpha_0=4,\eta_0=2,\zeta_0=4$ は上記の需要・価格式、一階条件、相補性をすべて残差0で満たす。これは指定された有限期間のcommitment問題の解であり、長い期間の終端感度とは別に検査する。

計算では下限が拘束する期間集合を仮定し、その期間は \(i_t=\underline i\)、他の期間は \(\zeta_t=0\) と置いて線形系を解く。解の金利と乗数の符号を確認し、違反する期間を入れ替えて更新する。全期間の \(f_t,g_t\)、一階条件、下限、相補性積を元式で検査し、終端を延長して初期の対象期間が許容差内で一致することを確認する。

中央銀行が将来政策への約束を維持する制度なら全期間を一度に選ぶcommitmentのKKTを使い、各期に再最適化する制度なら継続価値と予想を持つ裁量政策を解く。金利下限の期間、発表時点と将来約束の継承が政策経路を変える。`optimal monetary policy commitment discretion effective lower bound` で政策目的と価格設定のハンドブック、中央銀行の政策則・発表記録を照合し、econ-designが目的と約束を選ぶ。econ-dataでactive setを更新し、終端期間を伸ばして対象期間の経路と各制約を比較する。

所与のTaylor則を評価する場合は、その最適政策の一階条件に代えて \(i_t^{rule}=\phi_\pi\pi_t+\phi_xx_t+\varepsilon_t^m\) と \(i_t=\max(\underline i,i_t^{rule})\) を使う。後者は \(i_t-\underline i\ge0\)、\(i_t-i_t^{rule}\ge0\)、両者の積0と等価で、同じ価格式と需要式に連立する。予想される将来金利を現在需要へ入れ、政策発表と実施の時点を情報集合へ置く。

