<a id="stat-03"></a>

## STAT-03 大数の法則と中心極限定理

独立同分布の $X_i$ が有限平均 $\mu$ を持つとき、標本平均 $\bar X_n$ は $\mu$ に確率収束する。有限で正の分散 $\sigma^2$ も持つとき、$\sqrt n(\bar X_n-\mu)\Rightarrow N(0,\sigma^2)$ である。標本数が四倍になると標本平均の標準誤差は半分になる。観測が同じ集団や時点で依存する場合は、その依存を含む分散を用いる。

$g$ が $\mu$ で微分可能で $g'(\mu)\ne0$ なら、一次展開 $g(\bar X)-g(\mu)=g'(\mu)(\bar X-\mu)+o_p(n^{-1/2})$ により $\sqrt n[g(\bar X)-g(\mu)]\Rightarrow N(0,g'(\mu)^2\sigma^2)$ を得る。比率、弾力性、対数変換後の推定量の標準誤差は、多変量版の勾配と共分散行列から同様に計算する。

標本平均の分散を依存構造から求めると、$\operatorname{Var}(\bar X)=n^{-2}\sum_i\sum_j\operatorname{Cov}(X_i,X_j)$ である。独立同分布では対角項だけが残り $\sigma^2/n$ となる。同一集団内の共通ショックが正の共分散を作るとき、その項を含めた分散が平均の標本変動を表す。クラスターを独立な抽出単位として扱い、集団内の観測を合算したスコアの分散を用いると、同じ集団の共通ショックを反映できる。

定常系列 $X_t$ の平均を $\mu$、自己共分散を $\gamma(k)=\operatorname{Cov}(X_t,X_{t-k})$ とする。過去と $k$ 期以降の事象族を $\mathcal F_{-\infty}^t,\mathcal F_{t+k}^\infty$ とすると、strong mixing係数は $\alpha(k)=\sup_t\sup_{A\in\mathcal F_{-\infty}^t,B\in\mathcal F_{t+k}^\infty}|P(A\cap B)-P(A)P(B)|$ である。ある $\delta>0$ について $E|X_t|^{2+\delta}<\infty$、$\sum_{k=1}^\infty\alpha(k)^{\delta/(2+\delta)}<\infty$、長期分散 $\Omega=\gamma(0)+2\sum_{k\ge1}\gamma(k)>0$ が成り立つと、$\sqrt n(\bar X-\mu)\Rightarrow N(0,\Omega)$ である。依存が遠い時点間で減衰する条件により共分散和が有限となり、その和が平均の漸近分散を決める。

標本自己共分散を $\hat\gamma(k)=n^{-1}\sum_{t=k+1}^n(X_t-\bar X)(X_{t-k}-\bar X)$ とし、BartlettのHAC推定量を $\hat\Omega=\hat\gamma(0)+2\sum_{k=1}^{L}[1-k/(L+1)]\hat\gamma(k)$ とする。重みは非負の長期分散推定量を与える。帯域 $L$ を増やし、$L/n\to0$ として、採択するmixing・モーメント・帯域の条件の下で一致性を用いる。標準誤差は $\sqrt{\hat\Omega/n}$ である。標本平均のblock bootstrapでは、系列を循環させた連続 $\ell$ 観測のブロックを復元抽出し、連結して長さ $n$ に切る。例えば指数的に減衰するstrong mixing、有限 $(4+\delta)$ 次モーメント、$\ell=\lfloor n^{1/3}\rfloor$ の下で、中心化した標本平均の再標本分布を用いる。対象統計量と依存構造に合わせて再標本化の一致性条件を定める。

定常AR(1) $X_t=.5X_{t-1}+\epsilon_t$ のinnovation分散を $.75$ とすると、$\gamma(0)=1$、$\gamma(k)=.5^k$、$\Omega=1+2\sum_{k\ge1}.5^k=3$ である。$n$ 期平均の漸近分散は $3/n$ となり、独立系列の $1/n$ と比べて系列内の持続性を反映する。

例えば100人が各10人の独立な10集団に分かれ、個人の分散が1、同一集団内の異なる2人の相関が0.2なら、平均の分散は $[1+(10-1)0.2]/100=0.028$、標準誤差は約0.167である。全員独立と誤って扱った0.1より大きく、分散だけを同じにする独立標本数は約35.7人に相当する。一般の集団サイズや相関はこの簡単な式に収まらず、独立な集団の数が少ないと通常のクラスター漸近近似も不安定になる。平均の分散を正しく書くことと、依存下で中心極限定理が成立する条件を確認することは別の作業である。

$X_n\to X$ がほとんど確実に成り立ち、すべての $n$ で $|X_n|\le G$ がほとんど確実に成り立ち、$EG<\infty$ なら、優収束定理から $E|X_n-X|\to0$、従って $EX_n\to EX$ となる。確率空間上で可積分な $X_n$ が $X$ に確率収束するとき、$X$ が可積分で $X_n\to X$ が $L^1$ で成り立つための必要十分条件は一様可積分性 $\lim_{K\to\infty}\sup_n E[|X_n|\mathbf1_{\{|X_n|>K\}}]=0$ である。共通の可積分な上界はこの条件を満たす。例えば $U$ が $(0,1)$ の一様分布に従うとき、$X_n=2^n\mathbf1_{\{U<2^{-n}\}}$ はほとんど確実に0に収束するが、$EX_n=1$ である。どの $K$ にも $2^n>K$ となる $n$ があり、その裾の期待値は1のままである。

距離 $d$ のパラメータ空間で、確率過程 $g_n$ が $\theta_0$ で確率的同程度連続であるとは、各 $\epsilon>0$ について $\lim_{\delta\downarrow0}\limsup_{n\to\infty}P(\sup_{d(\theta,\theta_0)<\delta}|g_n(\theta)-g_n(\theta_0)|>\epsilon)=0$ となることをいう（上限は可測とする）。$|g_n(\hat\theta_n)-g_n(\theta_0)|>\epsilon$ の確率は $P(d(\hat\theta_n,\theta_0)\ge\delta)$ と上式の近傍内の確率の和以下である。$\hat\theta_n\to_p\theta_0$ なら、先に $n\to\infty$、次に $\delta\downarrow0$ とすると差は $o_p(1)$ となる。従って $g_n(\theta_0)\Rightarrow Z$ ならスルツキーの定理から $g_n(\hat\theta_n)\Rightarrow Z$ となる。各固定点での収束だけでは、移動する山を捉えられない。例えば $g_n(t)=Z+(1-n^2|t-2/n|)_+$ は各 $n$ で連続で、各固定 $t$ で $Z$ に収束するが、$t_n=2/n\to0$ では常に $Z+1$ である。

