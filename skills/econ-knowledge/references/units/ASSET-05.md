<a id="asset-05"></a>

## ASSET-05　ポートフォリオ、流動性、仲介

投資家は無リスク資産と \(J\) 個のリスク資産を選ぶ。超過収益平均を \(\mu\)、共分散を \(\Sigma\)、初期資産に対するリスク資産保有比率を \(w\)、リスク回避係数を \(\gamma>0\) とすると、目的は
\[
\max_w\ \mu'w-\frac{\gamma}{2}w'\Sigma w.
\]
\(\Sigma\) が正定値なら目的は厳密に凹であり、無制約の一階条件 \(\mu-\gamma\Sigma w=0\) の唯一解は \(w=\Sigma^{-1}\mu/\gamma\) となる。無リスク資産比率は \(1-\mathbf1'w\) である。空売り・借入・保有上限を \(Aw\le b\) と表せば、\(\lambda\ge0\)、\(\mu-\gamma\Sigma w-A'\lambda=0\)、\(Aw\le b\)、\(\lambda_i(A_iw-b_i)=0\) を同時に解く。これらのKKT条件は線形制約の下で最適解を特徴づける。取引費用、税、負債は目的と可行集合へ入れ、動学配分は富、所得、予測状態を状態変数として解く。

2資産の例では \(\mu=(.06,.04)'\)、\(\Sigma=\left[\begin{smallmatrix}.04&.01\\.01&.09\end{smallmatrix}\right]\)、\(\gamma=2\) とする。共分散行列の固有値は約(.038074,.091926)で、無制約の解は \(w=(5/7,1/7)\)、目的値は .024286 である。\(w_1\le.5,\ w_1,w_2\ge0,\ w_1+w_2\le1\) を課すと、解は \(w=(.5,1/6)\)、無リスク資産は1/3、目的値は .0225 となる。上限の乗数は \(1/60\)、他の乗数は0であり、勾配 \(\mu-2\Sigma w=(1/60,0)'\) と相補性を満たす。

収益モデルをベイズ推定して配分する場合、平均・共分散には同じ保有期間の事後予測収益を使う。条件付き平均を \(\mu_\theta\)、条件付き共分散を \(\Sigma_\theta\)、観測情報を \(\mathcal D\) とすれば、[STAT-07](https://github.com/yoshimurahiroki/econ-project-mini/blob/main/skills/econ-knowledge/references/chapters/02-probability-statistics.md#stat-07)の全分散から
\[
\mu_{pred}=E[\mu_\theta\mid\mathcal D],\qquad
\Sigma_{pred}=E[\Sigma_\theta\mid\mathcal D]+\operatorname{Cov}(\mu_\theta\mid\mathcal D)
\]
を得る。予測収益の平均分散を評価する投資家は、この二つを上の目的へ入れ、現在の情報で一つの実行可能な保有比率を選ぶ。状態別の平均分散目的を事後平均する目的では二次項は \(E[\Sigma_\theta\mid\mathcal D]\) となるため、採択する投資家の評価対象を先に定める。期待効用による配分では、同じ保有比率の収益を各予測標本で効用へ写して平均する。税・売買費用と保有制約はその同じ比率に適用する。

流動性は取引時の価格影響、bid–ask spread、探索待ち、資金制約をそれぞれの取引制度で定義する。仲介者の資産保有制約が拘束すると、その影価格が価格付けkernelへ入り、資産価格と仲介者純資産が同時に動く。取引記録、quote、注文、残高を制度の観測式へ結ぶ。

