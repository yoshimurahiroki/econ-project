<a id="het-02"></a>

## HET-02　家計分布と不完全市場均衡

政策と所得遷移は状態のMarkov行列 \(P_g\) を定める。定常分布は \(\mu'=\mu'P_g\)、\(\sum_s\mu_s=1\) を満たす。連続政策をgridへ配分する際は隣接点への重みを使い、質量と資産の集計を保持する。

総資産 \(K^s(r)=\sum_{a,e}a\mu_r(a,e)\)、労働 \(L=\sum e\mu\) とする。競争企業の \(r=\alpha A(K/L)^{\alpha-1}-\delta\)、\(w=(1-\alpha)A(K/L)^\alpha\) と \(K=K^s(r)\) を連立する。

計算は価格を仮定し、家計政策、定常分布、総資産を解き、資本超過需要を根探索する。家計Euler残差、分布不変性、質量1、資本・財市場清算を元式で確認する。所得遷移はパネルから推定し、借入下限と選好は資産・消費・反応モーメントへ対応させる。HET-06には所与の政策から定常分布を求める小例、HET-04には家計・分布・市場清算を同時に評価する一資産モデルの実行契約がある。

人口を1とすると、企業の労働投入 $N$ と家計の効率労働 $L$ は同じ単位で清算する。QuantEconの [PythonのEGM例](https://github.com/QuantEcon/lecture-python.myst/blob/4d82fffbb1280f8f6980a45dbe518e677f5c9a39/lectures/aiyagari_egm.md) と [Juliaの政策反復例](https://github.com/QuantEcon/lecture-julia.myst/blob/18877b5dd22cba3530089a3a3f3de23f427b8656/lectures/multi_agent_models/aiyagari.md) の所得効率 $(.1,1)$ と対称な遷移では、定常人口が半数ずつなので $L=0.55$ である。企業に $N=1$ を渡し、家計に元の効率を使うと、資本市場が清算しても財市場に $Y-C-\delta K=w(N-L)=.45w$ が残る。家計の効率をそのまま使うなら企業に $N=.55$ を渡す。企業の労働を1に正規化するなら各家計の効率を $.55$ で割る。どちらも同じ単位で価格・家計政策・定常分布を解き、予算と財市場に戻して確かめる。

集計ショックが反復する経済では、集計Markov状態 \(z_t\) と家計の資産・所得分布 \(\mu_t(a,e)\) を集計状態として持つ。人口を1に正規化し、家計の次期資産政策を \(g_t(a,e)=g(a,e,z_t,\mu_t)\) とすると、
\[
K_t=\int a\,d\mu_t,\qquad
A_t=\int g_t(a,e)\,d\mu_t,\qquad K_{t+1}=A_t,\qquad
\mu_{t+1}=\mathcal T(\mu_t,g_t,z_t,z_{t+1})
\]
である。\(\mathcal T\) は資産政策と条件付き所得遷移 \(P(e'\mid e,z_t,z_{t+1})\) が作る分布遷移である。家計は \(c+a'=R_ta+W_te\)、借入下限と消費正値の下で効用を最大化し、集計状態の遷移 \(\Pi(z'\mid z)\)、所得遷移と次期分布を継続価値へ入れる。資産分布が貯蓄と次期価格を変え、その価格が現在の家計選択へ戻る。

HARK 0.17.2の[KrusellSmithEconomy](https://github.com/econ-ark/HARK/blob/0.17.2/HARK/ConsumptionSaving/ConsAggShockModel.py#L2915-L3039)では、集計状態別の生産性を \(Z_z\)、失業率を \(u_z\)、就業者一人の労働を \(\ell\) とし、労働投入を \(L_t=(1-u_{z_t})\ell\) で与える。前期末の総貯蓄を当期資本へ渡し、競争価格と当期集計資源を
\[
R_t=1+Z_{z_t}\alpha(K_t/L_t)^{\alpha-1}-\delta,\qquad
W_t=Z_{z_t}(1-\alpha)(K_t/L_t)^\alpha,\qquad
M_t=R_tK_t+W_tL_t
\]
とする。\(R_t\) は元本を含む収益率であり、所得効率 \(e\) は就業時に \(\ell\)、失業時に0となる。

Krusell–Smith法は、家計が将来の集計量を予測するために分布を少数の集計量へ縮約する。HARKの同実装は、正の集計資源と貯蓄について \(\log\widehat A_t=a_{z_t}+b_{z_t}\log M_t\) という状態別の予測則を用いる。所与の係数で家計政策を解き、集計状態・雇用・資産を模擬し、初期の除外期間後の \((M_t,A_t,z_t)\) から各状態で \(\log A_t\) を \(\log M_t\) にOLS回帰する。コードは記録上の `Aprev[t+1]` を `Mnow[t]` と組にしており、当期の期末貯蓄 \(A_t\) と期首資源 \(M_t\) が対応する。係数 \(\theta_z=(a_z,b_z)\) の更新は
\[
\theta_z^{\mathrm{new}}=d\theta_z^{\mathrm{old}}+(1-d)\theta_z^{\mathrm{OLS}},
\qquad d=\texttt{DampingFac},\quad 0\le d<1
\]
である。各状態で集計資源が変動する模擬標本を使い、予測則と家計政策を反復する。家計のEuler・借入境界、予算、分布質量、資産・財市場清算と、\(\log A_t-\log\widehat A_t\) の状態別残差を確認する。

集計状態と価格が一定の長期配分には、上の定常Aiyagari均衡を使う。反復する集計ショックに家計が将来の貯蓄・価格を予測して反応する課題には、分布遷移と予測則を同時に更新する方法を選ぶ。所与の集計経路に対する局所応答と、その経路を元の非線形条件で解き直す計算はHET-04へ接続する。

### 定常Aiyagari均衡の実行契約

`MC-aiyagari-stationary`は、所与のCRRA選好、所得Markov行列、有限資産格子と競争生産を、既存の`research_macro_extended.py run`へ渡す。指定は`model="aiyagari"`、校正値の出所、`parameters`、基準・変更後の生産性、資本探索区間と元式の許容残差である。各資本候補で[QuantEconの`DiscreteDP.solve(method="policy_iteration")`](https://github.com/QuantEcon/QuantEcon.py/blob/d30c9000a96d7ae1d434bdecb4aa63d285a18599/quantecon/markov/ddp.py)が家計を解き、その政策の唯一の再帰類から定常分布を得る。SciPyの`brentq`が資本市場を探索する。

各シナリオで消費・資産政策、価値、定常分布、資本、競争価格と集計量を保存する。家計Bellman式、選択政策の価値式、予算、分布不変性、総質量、所得周辺分布、資本市場と財市場を元の式で照合する。有限格子で生じる資本供給の跳びには、実際の資本・財市場残差に設定した許容値を適用する。`calibration.estimated_parameters=[]`は、入力された原始パラメータを校正値として保持する実行内容を表す。

定常厚生は各シナリオ固有の分布による\(W=\sum_{a,e}\mu(a,e)V(a,e)\)である。同じCRRA曲率\(\gamma\ne1\)の定常消費等価率は\((W_s/W_b)^{1/(1-\gamma)}-1\)、対数効用では\(\exp\{(1-\beta)(W_s-W_b)\}-1\)となる。初期分布固定の移行厚生はHET-05の定義で計算する。

