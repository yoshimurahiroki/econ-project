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

### HMC・NUTSと変分推論の選択

HMCは連続座標 $z$ の標的に運動量 $r\sim N(0,M)$ を加え、Hamiltonian $H(z,r)=-\log\pi_z(z\mid Y)+r'M^{-1}r/2$ に従う軌道を計算する。勾配を使うleapfrogの可逆・体積保存な近似と採択補正により、離れた候補へ移動する。NUTSは軌道を木として延長し、折り返し条件で経路長を選ぶ。warmupではstep sizeと質量行列を調整し、保存する事後drawはその後から取る。連続で微分可能な対数密度にこの計算を適用し、離散潜在状態は可能なら周辺化するか、その状態を扱う公式samplerを選ぶ。[StanのHMC・NUTS](https://mc-stan.org/docs/reference-manual/mcmc.html)の条件を、[既存のエンジン選択](https://github.com/yoshimurahiroki/econ-project-mini/blob/main/skills/econ-data/references/implementation-engines.md#estimator-engine-and-algorithm-selection)へ渡す。

階層モデルの $\theta_j\sim N(\mu,\tau^2)$ は、非中心化 $\theta_j=\mu+\tau z_j,\ z_j\sim N(0,1)$ で同じ分布を表せる。群内の情報が少ない場合は、$\tau$ と $\theta_j$ の強い依存を非中心化が解く。群内の尤度が強く各 $\theta_j$ を絞る場合は中心化も比較対象となる。尺度の標準化、共線性、事後の相関・曲率と識別方向を調べ、同じ事前・尤度を保つ座標変更を選ぶ。密度変換が必要な操作は上のJacobianを使う。異なる座標で同じ事後分布を計算する操作と、事前分布を変更する操作をそれぞれのモデル式へ反映する。

変分推論は分布族 $q_\lambda(\theta)$ を選び、$\operatorname{ELBO}(\lambda)=E_q[\log p(Y,\theta)-\log q_\lambda(\theta)]=\log m(Y)-D_{KL}(q_\lambda\|\pi(\theta\mid Y))$ を最大化する。mean-fieldは分布の独立な成分への分解、full-rank Gaussianは連続変数間の線形相関を表す。大きなモデルで多数の候補を比較する計算には、その分布族と計算費用を選択条件にする。ELBOの停止は選んだ族の最適化を表し、事後の裾、複数の峰、分位点や期待損失の近似精度は各対象で評価する。共役の解析値または同じモデルの診断を満たすMCMCに、係数だけでなく予測と選択行動を対応させる。公式手法の目的関数は[Stanの変分推論](https://mc-stan.org/docs/reference-manual/variational.html)で確認し、実行は既存の公式API経路を使う。

### 連鎖・幾何・意思決定量の診断

独立な初期値から原則4本以上を走らせ、rank-normalized split $\widehat R$ とfolded-split $\widehat R$ により、連鎖内・連鎖間の位置と尺度を比較する。[Stanの診断資料](https://mc-stan.org/learn-stan/diagnostics-warnings.html)の目安は $\widehat R<1.01$ である。bulk ESSは分布の中心を評価し、tail ESSは通常5%・95%分位点のESSの小さい方で裾を評価する。平均、利益差、損失確率、選ぶ価格・発注量ごとにMCSEを計算し、採択する金額・確率・数量の計算精度へ照合する。係数のESSが大きくても、非線形な利益や希少損失のESSはその関数で求める。信用区間の幅とMonte Carloによる区間端点の計算誤差もそれぞれの量で報告する。

divergenceは軌道の数値積分が事後の局所曲率を解像できなかった遷移を示す。warmup後の該当drawと群間尺度・相関・境界の位置を照合し、尺度変更、非中心化、尤度と事前の修正、step sizeの調整を、その原因に対応させる。最大tree depthへの到達は軌道計算の上限であり、ESS当たりの費用と連鎖診断で経路長の選択を評価する。エネルギーのE-BFMIは運動量更新が異なるエネルギー水準を探索する程度を測り、公式の目安0.3を下回る連鎖では裾と尺度を調べる。探索範囲を連鎖別の軌跡とrank plotで照合し、原因に対応する変更後に各診断と対象のMCSEを再計算する。

### 予測検査とモデル比較

事前予測は観測前の結果範囲、事後予測検査は推定後にモデルが再現する特徴を評価する。群別の売上分散、継続率、ゼロ、裾、系列相関など、採択した観測分布の含意をSTAT-07の生成過程から求める。予測の較正は、評価標本での予測分位点以下の頻度、予測区間の被覆、二値確率と実現率の対応を、同じ人口・期間で計算する。分布予測のlog scoreと、発注・広告・価格の経営損失をそれぞれ評価する。

条件付き尤度が観測単位 $i$ ごとに分解するモデルでは、LOOの対象は $\operatorname{elpd}_{LOO}=\sum_i\log\int p(y_i\mid\theta)\pi(\theta\mid y_{-i})d\theta$ である。各draw・観測単位の対数尤度を保存し、PSISで全標本の事後からleave-one-outの積分を近似する。出力はelpd、モデル間の同じ観測でのelpd差とその標準誤差、観測別Pareto $k$、Monte Carlo誤差である。[looの公式定義](https://mc-stan.org/loo/reference/loo.html)に従い、連鎖相関を含めた重要度計算の精度を評価する。[Pareto $k$ の判定](https://mc-stan.org/loo/reference/pareto-k-diagnostic.html)は事後draw数 $S$ に応じた $\min(1-1/\log_{10}S,0.7)$ を目安とし、基準を超える観測には当該leave-outの再推定、対応するmoment matching、またはK-foldを選ぶ。

leave-out単位は実際の利用と一致させる。同じ顧客の次回結果、未観測の新規顧客、新しい店舗の予測では、既存の群効果を使える情報が異なる。新規群の評価では評価用に群全体を取り置き、その群の潜在効果を母集団分布で積分する。将来時点の予測では過去のみで学習するrolling-originを使い、時点の前後をまたぐ通常のLOOから将来の情報を得る構成を外す。候補モデルは同じ対象・分割で比較し、予測分布を混合するstackingの重み、STAT-07のモデル事後確率、因果効果の識別をそれぞれの定義で扱う。事前の尺度や群構造を変更した場合は、同じ利益差と政策順位も再計算する。

**計算例。** 事後分布 $\theta\sim\operatorname{Beta}(A,B)$ をlogit座標で動かすと、対数標的は $A\log\theta+B\log(1-\theta)+\mathrm{const}$ である。対称提案 $z'=z+s\varepsilon$, $\varepsilon\sim N(0,1)$ にはこの対数標的差を使う。安定な評価は `log_theta = -logaddexp(0, -z)`、`log_one_minus_theta = -logaddexp(0, z)` で行う。戻したdrawの平均と分散を $A/(A+B)$、$AB/[(A+B)^2(A+B+1)]$ に照合する。$A=4,B=7$ なら平均 $4/11$、分散 $7/363$。Jacobianを省いたlogit標的を逆変換すると、元の密度を $\theta(1-\theta)$ で割るため、$A,B>1$ では $\operatorname{Beta}(A-1,B-1)$ となり、この例の平均は $1/3$ に変わる。$A\le1$ または $B\le1$ では省略後の標的の積分が発散する。

非線形・非Gaussian状態空間では粒子filterを使う。状態粒子を遷移で予測し、観測尤度でweightを更新し、正規化weightに従って再抽出する。毎期再抽出するbootstrap filterでは、各期の予測粒子に対する観測尤度の平均を掛け合わせて尤度を推定する。再抽出の頻度や提案分布を変える場合は、その手順に対応した逐次正規化と重要度比を用いる。粒子数を増やした尤度・予測の変化と、weightの集中を評価する。Kalman filterはTS-04の線形Gaussian系を解析的に更新する。

景気の潜在状態を当月までの情報で推定するとき、線形Gaussianの遷移と観測式ならKalman filterの平均・分散を使う。非線形や非Gaussianの同じ状態モデルでは粒子filterの重み付き分布を用い、粒子数と重みの集中による誤差を評価する。固定された構造パラメータの事後分布を求めるMCMCは、状態の逐次filterとは計算対象が異なる。両方が未知ならパラメータと状態を含む事後対象を定義して計算を組み合わせる。「nonlinear state space particle filter」「particle degeneracy」「Bayesian posterior MCMC effective sample size」を検索し、econ-designで対象と観測式を確定してecon-dataで適合する計算エンジンを選ぶ。

二状態の確認として目標確率を \(\pi(0)=1/4,\pi(1)=3/4\)、候補を必ず反対の状態とする。対称な候補のため採択確率は \(0\to1\) が1、\(1\to0\) が \(1/3\)。定常状態で両方向の流れはいずれも \(1/4\) で、詳細釣合いを満たす。両状態は相互に到達でき、状態1では確率 \(2/3\) で留まるので周期性もない。これは目標分布を不変にする仕組みの確認であり、有限回のdrawが十分混合したことの保証ではない。採択率が高いだけでも探索範囲や自己相関の問題は分からない。

粒子の正規化weightが \((0.2,0.8)\) なら、weightに基づく実効粒子数は \(1/(0.2^2+0.8^2)=25/17\simeq1.47\) で、粒子2個が均等に寄与する場合より小さい。低下時の再抽出は大きなweightに計算を集中させる一方、祖先の多様性を減らし、過去の状態の推定を不安定にし得る。全weightがゼロなら正規化できず、観測尤度や提案のsupportを点検する。再抽出は尤度の誤指定を修正しない。
