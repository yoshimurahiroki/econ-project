<a id="econ-09"></a>

## ECON-09　ベイズ計算と粒子

事後密度の比例式 \(\pi(\theta|Y)\propto L(Y|\theta)\pi(\theta)\) を計算対象にする。比例式を確率分布として用いるには、尤度と事前密度の積の積分が有限かつ正でなければならない。Metropolis–Hastingsは候補 \(\theta'\sim q(\theta'|\theta)\) を
\[
\min\left\{1,\frac{L(Y|\theta')\pi(\theta')q(\theta|\theta')}
{L(Y|\theta)\pi(\theta)q(\theta'|\theta)}\right\}
\]
で採択し、残りで現在値に留まる。Gibbsは各成分の完全条件付き分布から順に抽出する。Hamiltonian法は対数事後の勾配と補助運動量で候補を作り、数値積分誤差を採択確率へ反映する。

**密度変換と不変分布。** 制約付きパラメータを一対一の微分可能な変換 $\theta=T(z)$ で表すと、$z$ の密度は $\pi_z(z\mid Y)=\pi_\theta(T(z)\mid Y)|\det DT(z)|$ となる。これは任意の領域 $A$ について $\int_{T(A)}\pi_\theta(\theta\mid Y)d\theta=\int_A\pi_z(z\mid Y)dz$ と確率を保存する変数変換である。対数密度に $\log|\det DT(z)|$ を加え、提案密度も実際に連鎖を動かす座標で評価する。正の尺度なら $\theta=e^z$ で対数Jacobianは $z$、確率なら $\theta=(1+e^{-z})^{-1}$ で $\log\theta+\log(1-\theta)$ となる。

正規化した標的密度を $p$、上の受容確率を $\alpha(z,z')$ と書くと、異なる点の確率流は
\[
p(z)q(z'\mid z)\alpha(z,z')=\min\{p(z)q(z'\mid z),p(z')q(z\mid z')\}
=p(z')q(z\mid z')\alpha(z',z).
\]
棄却時の自己遷移を加えた遷移核は詳細釣合いを満たし、両辺を積分すると $p$ が不変分布となる。標的について既約・非周期かつHarris再帰的な連鎖では、標本平均は可積分な標的モーメントへ収束する。正規化定数は密度比で消える。対称なランダムウォーク提案では提案密度比も消える。

**反復と誤差評価。** 初期値を標的のsupport内に置き、毎回、候補 $z'$ と独立な $U\sim U(0,1)$ を生成する。$\log U<\min(0,\log p(z')-\log p(z)+\log q(z\mid z')-\log q(z'\mid z))$ なら更新し、棄却時は現在値を次のdrawとして保存する。提案尺度の調整期間と保存期間を分け、保存期間では指定した遷移核を固定する。別々の乱数系列と離れた初期値で複数連鎖を実行し、各連鎖の平均、分散、受容率、自己相関、実効標本数を比較する。

保存した $N$ 個の $h(\theta_t)$ の平均を $\bar h$、定常自己共分散を $\gamma_k$ とする。Markov連鎖CLTと有限な長期分散の下で $\operatorname{Var}(\bar h)$ の主要項は $[\gamma_0+2\sum_{k\ge1}\gamma_k]/N$。batch meansでは $N=ab$ 個を長さ $b$ の連続した $a$ 組に分け、組平均 $\bar h_j$ を使って
\[
\widehat{\operatorname{MCSE}}^2(\bar h)=\frac{1}{a(a-1)}\sum_{j=1}^a(\bar h_j-\bar h)^2,
\qquad N_{\rm eff}=\frac{\widehat\gamma_0}{\widehat{\operatorname{MCSE}}^2(\bar h)}
\]
を計算する。一致性には連鎖の混合・モーメント条件と $a,b\to\infty$ が必要である。評価するモーメントごとにbatchを作り、連鎖ごとの結果とbatch長を増やした結果を照合する。等長で独立な $C$ 本の平均をまとめると、そのMonte Carlo分散推定値は各連鎖の分散推定値の和を $C^2$ で割ったものになる。事後分散はパラメータ分布の広がり、MCSEは有限回の反復で計算した平均の誤差を測る。事後予測では各drawから同じ観測過程を通じて将来観測を生成する。

**計算例。** 事後分布 $\theta\sim\operatorname{Beta}(A,B)$ をlogit座標で動かすと、対数標的は $A\log\theta+B\log(1-\theta)+\mathrm{const}$ である。対称提案 $z'=z+s\varepsilon$, $\varepsilon\sim N(0,1)$ にはこの対数標的差を使う。安定な評価は `log_theta = -logaddexp(0, -z)`、`log_one_minus_theta = -logaddexp(0, z)` で行う。戻したdrawの平均と分散を $A/(A+B)$、$AB/[(A+B)^2(A+B+1)]$ に照合する。$A=4,B=7$ なら平均 $4/11$、分散 $7/363$。Jacobianを省いたlogit標的を逆変換すると、元の密度を $\theta(1-\theta)$ で割るため、$A,B>1$ では $\operatorname{Beta}(A-1,B-1)$ となり、この例の平均は $1/3$ に変わる。$A\le1$ または $B\le1$ では省略後の標的の積分が発散する。

非線形・非Gaussian状態空間では粒子filterを使う。状態粒子を遷移で予測し、観測尤度でweightを更新し、正規化weightに従って再抽出する。毎期再抽出するbootstrap filterでは、各期の予測粒子に対する観測尤度の平均を掛け合わせて尤度を推定する。再抽出の頻度や提案分布を変える場合は、その手順に対応した逐次正規化と重要度比を用いる。粒子数を増やした尤度・予測の変化と、weightの集中を評価する。Kalman filterはTS-04の線形Gaussian系を解析的に更新する。

景気の潜在状態を当月までの情報で推定するとき、線形Gaussianの遷移と観測式ならKalman filterの平均・分散を使う。非線形や非Gaussianの同じ状態モデルでは粒子filterの重み付き分布を用い、粒子数と重みの集中による誤差を評価する。固定された構造パラメータの事後分布を求めるMCMCは、状態の逐次filterとは計算対象が異なる。両方が未知ならパラメータと状態を含む事後対象を定義して計算を組み合わせる。「nonlinear state space particle filter」「particle degeneracy」「Bayesian posterior MCMC effective sample size」を検索し、econ-designで対象と観測式を確定してecon-dataで適合する計算エンジンを選ぶ。

二状態の確認として目標確率を \(\pi(0)=1/4,\pi(1)=3/4\)、候補を必ず反対の状態とする。対称な候補のため採択確率は \(0\to1\) が1、\(1\to0\) が \(1/3\)。定常状態で両方向の流れはいずれも \(1/4\) で、詳細釣合いを満たす。両状態は相互に到達でき、状態1では確率 \(2/3\) で留まるので周期性もない。これは目標分布を不変にする仕組みの確認であり、有限回のdrawが十分混合したことの保証ではない。採択率が高いだけでも探索範囲や自己相関の問題は分からない。

粒子の正規化weightが \((0.2,0.8)\) なら、weightに基づく実効粒子数は \(1/(0.2^2+0.8^2)=25/17\simeq1.47\) で、粒子2個が均等に寄与する場合より小さい。低下時の再抽出は大きなweightに計算を集中させる一方、祖先の多様性を減らし、過去の状態の推定を不安定にし得る。全weightがゼロなら正規化できず、観測尤度や提案のsupportを点検する。再抽出は尤度の誤指定を修正しない。
