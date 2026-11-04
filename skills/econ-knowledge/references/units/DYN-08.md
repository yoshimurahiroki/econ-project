<a id="dyn-08"></a>

## DYN-08 確率ゲームと Markov 完全均衡

主体 $i$ の価値を $V_i(s)$、行動を $a_i$ とすると、Markov 完全均衡の方策 $\pi_i(s)$ は各状態で $\pi_i(s)\in\arg\max_{a_i}\{r_i(s,a_i,\pi_{-i}(s))+\beta E[V_i(s')\mid s,a_i,\pi_{-i}(s)]\}$ を満たす。価値関数はこの方策による当期利得と次期価値の和に等しい。

計算では初期方策を置き、各主体の価値を方策の下で評価する。相手の方策を固定した最適反応を各状態で求め、方策と価値を更新する。最後に各状態での一回の逸脱利得と遷移確率、値の再帰式を計算し、候補が均衡条件を満たすか調べる。参入退出、能力投資、在庫競争の政策比較では、変更後の均衡方策と状態分布をともに更新する。

参入退出の均衡推定では、企業の選択前に観測する状態、私的shock、競合の情報と同時性、参入費用の支払、当期行動後の遷移を決める。企業ごとの最適反応が同じ状態で複数の政策を許すとき、初期条件と選択規則を使った経路と、選択を固定しない均衡結果の集合を比較する。`dynamic oligopoly entry exit Markov perfect equilibrium identification` と `dynamic games equilibrium selection moment inequalities` を用いて原著・レビュー、参入退出と候補企業の記録を探す。econ-designで観測状態と逸脱集合を定め、econ-dataで各候補の一回逸脱、価値再帰と政策後の状態分布を求める。競合相手の政策と遷移を推定した誤差は市場単位の推論に入れる。

混合方策では、状態 \(s\) の他社行動分布を所与とした一回逸脱 \(a_i\) の利得を、当期報酬と次期状態の継続価値の期待和として求める。候補方策の価値はその候補が作る遷移行列で評価し、正の確率を置く行動が最大価値を達成することを検査する。全状態・全行動の最大逸脱利得を \(\varepsilon\) とすれば、一回逸脱の最適反応Bellman残差は \(\varepsilon\) 以下であり、割引 \(\beta\) の下で全期間の最適反応価値と候補価値の差は \(\varepsilon/(1-\beta)\) 以下となる。相互最適反応の単純反復は循環することがあるため、異なる初期方策から候補を求め、各候補の逸脱条件と採択した均衡選択を確認する。STRUCT-05の反復参入例は、当期行動が次期状態に影響しない特殊例で、各社の逸脱条件と複数均衡を具体的に計算する。

線形二次動学ゲームでは、2主体が各期に共通状態 $x_t\in\mathbb R^n$ を観測して行動 $u_{it}\in\mathbb R^{k_i}$ を同時に選び、状態が $x_{t+1}=Ax_t+B_1u_{1t}+B_2u_{2t}$ に従う。主体 $i$ は $0<\beta<1$ の下で割引費用和を最小化する。$j\ne i$ とし、当期費用を

\[
\ell_i(x,u_i,u_j)
=x^\top R_ix+u_i^\top Q_iu_i+u_j^\top S_iu_j
+2x^\top W_iu_i+2u_j^\top M_iu_i
\]

とする。費用行列 $R_i,Q_i,S_i$ は対称とする。状態、自己と相手の調整量、それらの相互作用を各行列に対応させる。相手の方策 $u_j=-F_jx$ を固定すると、$\Lambda_i=A-B_jF_j$、$\Pi_i=R_i+F_j^\top S_iF_j$、$\Gamma_i=W_i^\top-M_i^\top F_j$ により、遷移は $\Lambda_ix+B_iu_i$、費用は $x^\top\Pi_ix+u_i^\top Q_iu_i+2u_i^\top\Gamma_ix$ となる。

対称な $P_i$ を用いて定常費用価値を $V_i(x)=x^\top P_ix$ と置き、$H_i=Q_i+\beta B_i^\top P_iB_i$ が正定値となるとき、自己行動の一階条件と価値の再帰から

\[
H_iF_i=\beta B_i^\top P_i\Lambda_i+\Gamma_i,\qquad
P_i=\Pi_i+\beta\Lambda_i^\top P_i\Lambda_i-F_i^\top H_iF_i
\]

を得る。方策は $u_i=-F_ix$ である。$C_{ij}=\beta B_i^\top P_iB_j+M_i^\top$、$b_i=\beta B_i^\top P_iA+W_i^\top$ と置くと、両主体の第1式は

\[
\begin{pmatrix}H_1&C_{12}\\C_{21}&H_2\end{pmatrix}
\begin{pmatrix}F_1\\F_2\end{pmatrix}
=\begin{pmatrix}b_1\\b_2\end{pmatrix}
\]

となる。各 $H_i$ が正定値で、このブロック行列が正則なら、次期の価値係数を所与とした両方策の一意解を得る。有限期間では $H_i,C_{ij},b_i$ を次期の価値係数から作り、当期の方策と価値係数を終端から後退計算する。期間を延ばした係数が収束し、その極限が元のRiccati式、相互最適反応と割引終端条件を満たすとき、その極限を定常解として採用する。

[QuantEcon.pyのnnash](https://github.com/QuantEcon/QuantEcon.py/blob/d30c9000a96d7ae1d434bdecb4aa63d285a18599/quantecon/_lqnash.py)と[QuantEcon.jlのnnash](https://github.com/QuantEcon/QuantEcon.jl/blob/df801457aae1f280698d663e68f1a6ac8423360e/src/lqnash.jl)は、終端価値0に対応する $P_1=P_2=0$ から連立方策と価値係数を更新し、`F1,F2,P1,P2` を返す。Pythonは `nnash(..., beta=beta)`、Juliaは `nnash(...; beta=beta)` に元の $A,B_1,B_2$ と費用行列を渡す。両実装が内部で遷移行列を $\sqrt\beta$ 倍して割引を取り込む。停止判定には方策係数の更新差を使う。状態経路には元の閉ループ行列 $A-B_1F_1-B_2F_2$ を使う。費用和が有限となる方策について、元のRiccati残差、相手を固定した最適反応、価値の再帰と割引終端値を評価する。行動上限、非負数量、離散参入を持つモデルは、その可行集合を含む最適反応計算へ接続する。

例えば状態偏差と両主体の調整行動を実数とし、$x_{t+1}=x_t+u_{1t}+u_{2t}$、$\ell_i=(13/16)x^2+u_i^2$、$\beta=1/2$ とする。候補方策 $u_1=u_2=-x/4$、費用価値 $V_1(x)=V_2(x)=x^2$ を代入する。相手が $-x/4$ を選ぶと、当期費用と継続価値の和は

\[
\frac{13}{16}x^2+u_i^2+\frac12\left(\frac34x+u_i\right)^2
=x^2+\frac32\left(u_i+\frac14x\right)^2
\]

となる。全状態で唯一の最適反応は $u_i=-x/4$、最小費用は $x^2$ となる。候補方策は互いに最適反応で、各費用価値は価値の再帰を満たす。閉ループは $x_{t+1}=x_t/2$、割引終端価値は $(1/8)^t x_0^2$ で0へ収束する。公式関数に対応する行列は $A=B_1=B_2=1,\ R_1=R_2=13/16,\ Q_1=Q_2=1,\ S_i=W_i=M_i=0$ であり、参照解は $F_1=F_2=1/4,\ P_1=P_2=1$ となる。この解の連立行列は対角成分 $3/2$、非対角成分 $1/2$ で、行列式は2となる。入力では各係数を1×1行列として与える。

