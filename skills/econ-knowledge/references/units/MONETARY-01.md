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

政策則 \(i_t=\phi_\pi\pi_t+\phi_xx_t+\varepsilon_t^m\) とショック過程を加える。正の標準パラメータ、\(\phi_x=0\) の基本系では \(\phi_\pi>1\) がTaylor principleを満たす。一般の拡張系は、先決状態数と安定固有根数を照合して局所解を選ぶ。この三式に一期間の自然金利ショックを入れた計算はMONETARY-06に示す。

