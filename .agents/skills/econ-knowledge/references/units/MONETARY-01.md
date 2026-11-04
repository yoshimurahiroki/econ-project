<a id="monetary-01"></a>

## MONETARY-01　New Keynesianの三式

家計Euler式を定常状態の周りで線形化し、価格調整企業の最適化を集計すると

\[
x_t=E_tx_{t+1}-\sigma^{-1}(i_t-E_t\pi_{t+1}-r_t^n),
\quad
\pi_t=\beta E_t\pi_{t+1}+\kappa x_t
\]

を得る。\(x\) は柔軟価格産出からのgap、\(r^n\) は自然実質金利、\(\pi\) はインフレ率である。Calvo価格調整では各期確率 \(1-\theta\) で価格を変更し、\(\kappa\) はその調整率と限界費用の産出反応から導く。

労働だけの線形生産、CRRA消費効用の曲率 $\sigma$、労働不効用 $N^{1+\varphi}/(1+\varphi)$、価格indexation0を置く。実質限界費用の対数gapは $\widehat{mc}=(\sigma+\varphi)x$ となる。価格を変更できる企業の将来限界費用への割引和と、変更しない企業を含む価格指数を合わせると、$\kappa=(1-\theta)(1-\beta\theta)(\sigma+\varphi)/\theta$ を得る。

政策則 \(i_t=\phi_\pi\pi_t+\phi_xx_t+\varepsilon_t^m\) とショック過程を加える。\(E_t\) はMACRO-05で定義した合理的期待であり、政策則を含む均衡の条件付き平均である。\(\beta\in(0,1),\sigma>0,\kappa>0,\phi_x=0\) の基本系では \(\phi_\pi>1\) がTaylor principleを満たす。同次系は \(E_tz_{t+1}=Az_t\)、\(z_t=(x_t,\pi_t)'\) と書け、
\[
A=\begin{pmatrix}
1+\phi_x/\sigma+\kappa/(\sigma\beta)&(\phi_\pi-1/\beta)/\sigma\\
-\kappa/\beta&1/\beta
\end{pmatrix}
\]
となる。この二変数は当期に調整するため、有界な同次解を一意にするには両固有根の絶対値が1を超える。例えば \((\beta,\sigma,\kappa,\phi_\pi,\phi_x)=(.99,1,.1,1.5,0)\) の固有根は \(1.05555556\pm.21775819i\)、絶対値はともに \(1.07778298\) である。先決状態を追加する拡張系では、MACRO-05の安定固有空間の次元と射影の階数を照合する。MONETARY-06は同じ三式から、一期間と持続する自然金利ショックへの反応を求める。

