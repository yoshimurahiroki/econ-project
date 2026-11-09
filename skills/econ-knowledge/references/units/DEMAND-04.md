<a id="demand-04"></a>

## DEMAND-04　連続需要と価格指標

支出関数から得た需要系は、加法整合性、価格と支出額に関する同時ゼロ次同次性、補償需要の対称性を満たす。AIDS型支出シェアは \(w_j=\alpha_j+\sum_k\gamma_{jk}\log p_k+\beta_j\log(m/P)\) と書き、\(\sum_j\alpha_j=1,\sum_j\gamma_{jk}=0,\sum_j\beta_j=0\)、\(\gamma_{jk}=\gamma_{kj}\) を課す。対称性により \(\sum_k\gamma_{jk}=0\) も成立し、すべての価格と支出額を同率で変えても支出シェアは変わらない。正確な価格指数は \(\log P=\alpha_0+\sum_k\alpha_k\log p_k+\tfrac12\sum_{k,l}\gamma_{kl}\log p_k\log p_l\) である。支出関数に対応するこの指数を使って推定し、近似指数を使う場合はその定義を推定式に含める。2財で $\alpha=(.5,.5)$、$\beta=(.2,-.2)$、$\gamma=\left[\begin{smallmatrix}.1&-.1\\-.1&.1\end{smallmatrix}\right]$、$\alpha_0=0$ とする。価格 $(1,1)$、支出1では $P=1$、シェア $(.5,.5)$ である。価格と支出をともに2倍にすると $P=2$、シェアは同じ $(.5,.5)$ で、シェアの同次性と和1を確認できる。

これらの線形制約に加え、評価する価格・支出の領域で支出シェアの非負性と支出関数の価格に関する凹性を確認する。$L=\log(m/P)$ とし、基準効用 $u=v(p,m)$ を固定したSlutsky行列を $S_{ij}=\partial h_i/\partial p_j$ とすれば、このAIDSの式から

$$S_{ij}=\frac{m}{p_ip_j}\left[\gamma_{ij}+\beta_i\beta_j L+w_iw_j-1\{i=j\}w_i\right]$$

を得る。MICRO-02の補償需要の性質に従い、この対称行列が半負定値となる領域で厚生計算に使う。

ゼロ消費には購入参加と条件付き数量の機構を置く。家計調査では世帯員、数量単位、単価と品質選択、支出測定をモデルへ対応させる。所得効果を含む厚生は支出関数を解いてCVを求める。

