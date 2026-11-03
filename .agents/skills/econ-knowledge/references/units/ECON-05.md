<a id="econ-05"></a>

## ECON-05　測定誤差、選択、打切り

構造式を \(Y=\alpha+\beta X^*+u\) とし、真の説明変数 \(X^*\) を \(X=X^*+v\) と観測する。\(v\) が \(X^*,u\) と独立で、さらに \(\operatorname{Cov}(X^*,u)=0\) なら、切片付き単回帰OLSの極限は \(\beta\operatorname{Var}(X^*)/[\operatorname{Var}(X^*)+\operatorname{Var}(v)]\) となる。独立な反復測定や妥当なIVから真の変動を回収する。

例えば真の傾きが2、真の説明変数の分散が4、独立な測定誤差の分散が1なら、誤差を含む説明変数によるOLSの極限は \(2\times4/(4+1)=1.6\) である。同じ真値を別の独立な誤差で測った \(X_2=X^*+v_2\) があり、\(v_2\) が最初の測定誤差と構造誤差にも無相関なら、\(\operatorname{Cov}(X_2,Y)=8\)、\(\operatorname{Cov}(X_2,X)=4\) なのでIV比は2を回復する。測定誤差の共通成分や真の説明変数と構造誤差の相関が残る場合は、この反復測定だけでは修正できない。

潜在結果 \(Y^*=X'\beta+\varepsilon\)、\(\varepsilon|X\sim N(0,\sigma^2)\)、観測 \(Y=\max(0,Y^*)\) を指定すると、Tobit尤度はゼロ観測の確率と正観測の密度を組み合わせる。観測選択 \(R=1\{Z'\gamma+\nu>0\}\) とし、両方の説明変数に条件付けた同時分布 \((\varepsilon,\nu)\mid X,Z\sim N(0,\Sigma)\) を置く。ここで \(\Sigma\) は \(X,Z\) に依存しない共分散行列で、\(\operatorname{Var}(\nu\mid X,Z)=1\)、\(\sigma_{\varepsilon\nu}=\operatorname{Cov}(\varepsilon,\nu\mid X,Z)\) とする。選択後の平均誤差は
\[
E[\varepsilon\mid X,Z,R=1]=\sigma_{\varepsilon\nu}\lambda(Z'\gamma),\qquad
\lambda(v)=\frac{\phi(v)}{\Phi(v)}
\]
である。観測を動かし結果に直接入らない変数が選択構造を分離する。

打切りでは閾値を越えた値の正確な大きさは見えなくても、その単位と閾値を越えた事実は観測する。切断では対象範囲外の単位自体が標本に入らず、観測される密度を標本入り確率で条件付ける。別の選択過程による欠測は、結果の既知の閾値による打切りと区別する。

調査の所得が上限を超えた事実だけ記録されるときは右打切りの尤度、上限以下の人だけが抽出されるときは標本入り確率で条件付けた切断尤度を選ぶ。就業者の賃金だけが観測される場合は就業選択と賃金の同時モデルを指定し、選択に作用する制度と結果に対する排除条件を調べる。所得が実際にゼロの人も観測される場合は参加と正値を組み合わせるECON-03のtwo-partモデルが候補になる。調査票、記録上限と対象外の扱いを確認し、「censoring truncation sample selection」「two part model observed zeros」「repeated measurements errors in variables」を検索する。

生存時間のハザードは \(h(t|X)=f(t|X)/S(t|X)\) である。比例ハザード \(h_0(t)e^{X'\beta}\) で、生存時間と右打切り時間が共変量条件付きで独立なら、リスク集合内の発生順序から部分尤度を得る。右打切り観測は生存確率で尤度へ入り、異なる終了事由は競合リスクとして定義する。

