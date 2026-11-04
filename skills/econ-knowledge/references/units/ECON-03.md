<a id="econ-03"></a>

## ECON-03　最尤、擬似尤度、非線形平均

独立観測の密度 \(f(Y_i|X_i;\theta)\) を指定し、\(\sum_i\log f_i(\theta)\) を最大化する。スコア \(s_i=\partial\log f_i/\partial\theta\) の平均が0となり、Hessianの負期待値 \(A\) とスコア共分散 \(B\) から分散 \(A^{-1}BA^{-1}/n\) を得る。正しい尤度では情報行列等式 \(A=B\) が成立する。

非負結果の平均を \(\mu_i=\exp(X_i'\beta)\) とすると、Poisson擬似尤度の一階条件は \(\sum_iX_i(Y_i-\mu_i)=0\) である。曝露 \(e_i>0\) 当たりの率なら \(\mu_i=e_i\exp(X_i'\beta)\) とし、\(\log e_i\) の係数を1に固定する。二値説明変数の変化は \(100(e^{\beta_k}-1)\%\) の条件付き平均変化となる。 条件付き平均 \(E[Y_i\mid X_i]=\mu_i\) が正しく指定され、識別と通常の正則条件が成り立てば、このスコアの母平均はゼロである。結果が整数値やPoisson分布である必要はないが、条件付き平均だけから個々の結果確率は決まらない。分散が平均に等しいと仮定しない場合は頑健分散を使い、完全分離などで有限の最大値が存在しない場合を確認する。

企業効果 \(\alpha_i\) と年効果 \(\lambda_t\) を含む平均を \(E[Y_{it}\mid D_{it},X_{it},\alpha_i,\lambda_t]=\exp(\tau D_{it}+X_{it}'\beta+\alpha_i+\lambda_t)\) とする。地域内の誤差依存を採用したモデルは、`fixest::fepois(sales ~ subsidy + x | firm + year, data = d, vcov = ~region)` で指定できる。`sales`は非負の売上、`subsidy`は処置、`x`は共変量、`firm + year`は吸収する効果、`region`はスコアを合算するクラスターである。正の曝露に対応する率モデルには `offset = ~log(exposure)` を加える。処置係数を因果効果に使う識別条件は、同じ共変量と効果に条件付けて定める。

[`fixest::fepois`の実装](https://github.com/lrberge/fixest/blob/cf9461331033e6f7276ad39d8203751690e619d4/R/estimation.R) はPoisson族の `feglm` を呼び、反復ごとに作業結果 \(z=\eta+(y-\mu)/\mu\) と作業重み \(\mu\) を作って固定効果付き加重最小二乗を解く。推定後は有限係数の存在、収束、共線性、除外された観測ID、固定効果の扱いと共分散設定を保存する。既存の [`research_causal.py`の`poisson`](https://github.com/yoshimurahiroki/econ-project-mini/blob/main/skills/econ-data/scripts/research_causal.py) は、切片と宣言した共変量で同じ指数平均スコアを推定し、非負連続結果とゼロを受け入れ、HC1または一方向クラスター共分散を返す。固定効果やoffsetを採用する計算は、[既存のエンジン選択](https://github.com/yoshimurahiroki/econ-project-mini/blob/main/skills/econ-data/references/implementation.md#estimator-engine-and-algorithm-selection)から対応する `fepois` 呼出しへ渡す。

例えば補助金がゼロを含む事業所売上の平均をどれだけ変えるかを問う。対象事業所について \(m(d,x)=E[Y\mid D=d,X=x]\) を推定し、同一の共変量分布で \(E_X[m(1,X)-m(0,X)]\) または \(E_X[m(1,X)]/E_X[m(0,X)]\) を計算する。因果的な反実仮想平均には、処置条件付き交換可能性、重なり、整合性を置く。指数平均を使うPPMLはゼロを含む原単位の観測から \(m\) を推定し、分散の形を固定しないサンドイッチ分散を使う。事業所間で共通の地域政策ショックがあるなら、その割当・依存に対応する地域単位でスコアを集計する。

正の売上だけのlog-OLSは \(E[\log Y\mid D,X,Y>0]\) を対象とし、ゼロを含む原単位の平均を求めるには参加確率と正値部分の再変換が要る。\(\log(1+Y)\) は売上の通貨単位を変えると変換値と係数も変わる。two-partモデルは \(P(Y>0\mid D,X)\) と \(E[Y\mid Y>0,D,X]\) の積として同じ条件付き平均を構成し、参加と正値の規模に別々の説明変数や関数形を使う。正値部分は正の観測で推定し、両部の対象人口・支持と推定誤差を平均差の推論へ反映する。NB2の尤度は非負整数の結果分布と \(\operatorname{Var}(Y\mid X)=\mu+\alpha\mu^2\) を指定し、件数分布や過分散を直接モデル化する。PPMLの平均条件は分散を平均へ固定せず、二つの選択は同じ平均対象と標本で比較する。

水準OLSもゼロを含む売上を使い、加法的な条件付き平均の下で同じ人口の平均差を構成する。PPMLは指数平均の比率変化を指定する。両方の推定結果から同じ共変量分布にわたる平均差と平均比を計算し、各モデルの平均関数、支持と予測値を比較する。OLSの回帰係数を対数リンクの割合係数として直接比較せず、それぞれの予測平均を共通の金額・人口へ戻す。

研究資料は「Poisson pseudo maximum likelihood」「zero outcomes」「two-part model」「retransformation」を手掛かりに、平均条件と推論を扱う方法論、ゼロの生成過程を測る応用研究、使用する推定関数の公式仕様を照合する。対象集団、曝露、割当単位と反実仮想をecon-designで固定し、econ-dataで採択した推定法と対応する分散を実行する。

切片だけの例で観測数が3、結果が \((0,1,2)\) なら、平均を \(\mu=e^\beta\) としたスコアは \(3-3\mu\) で、\(\hat\mu=1,\hat\beta=0\) となる。\(\hat\mu\) を代入した残差の和は0である。Poisson分散を正しく指定した場合の平均推定量のモデル分散は \(1/3\) だが、標本残差二乗の平均 \(2/3\) を使うサンドイッチ分散は \((2/3)/3=2/9\) となる。この小標本は計算方法の例であり、頑健分散が小さくなったこと自体は分布や平均モデルの正しさを証明しない。

二値結果のlogitは \(p_i=\Lambda(X_i'\beta)\)、\(\Lambda(v)=(1+e^{-v})^{-1}\) を使う。連続変数の限界効果は \(\beta_kp_i(1-p_i)\)、二値変数の効果は変数を1と0に置いた確率差である。多項logitの選択確率は、独立な第1種極値効用ショックから導く。負の二項NB2は \(\operatorname{Var}(Y|X)=\mu+\alpha\mu^2\) を指定する。

分位点回帰は \(\sum_i\rho_\tau(Y_i-X_i'b)\)、\(\rho_\tau(v)=v[\tau-1\{v<0\}]\) を最小化し、条件付き分位点を推定する。ゼロでの参加と参加後数量が異なる意思決定なら、その二つの条件付き分布を構成する。

