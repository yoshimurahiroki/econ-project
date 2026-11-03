<a id="forecast-04"></a>

## FORECAST-04　nowcastとnews

観測 \(y_t=C_tx_t+\nu_t\)、状態 \(x_t=Ax_{t-1}+\eta_t\) に異なる公表時点と頻度を入れる。TSのfilterで欠けた観測を飛ばして更新し、現時点の経済量を推定する。

旧情報 \(\mathcal I\) に新release \(z\) が加わると、線形Gaussian系の更新は

\[
E[Y|\mathcal I,z]-E[Y|\mathcal I]
=\operatorname{Cov}(Y,z|\mathcal I)
\operatorname{Var}(z|\mathcal I)^{-1}
[z-E[z|\mathcal I]]
\]

となる。角括弧がnewsであり、係数はそのreleaseが対象と共有する情報を数量化する。複数releaseをまとめて更新する場合はnews共分散行列の逆行列を使う。公表値の改定は旧版と新版の観測誤差・相関を含む測定過程に対応させ、旧情報と整合した改定の影響を計算する。具体的な一releaseのnewsと更新値の計算はFORECAST-07を使う。

公表時刻 $v$ の情報集合 $\mathcal I_v$ を、実際に利用可能な版と発表時刻で定義する。四半期の合計対象 $Y_q=\sum_{m\in q}y_m$ は月次状態とそのlagを含む観測行で表し、未公表成分は欠測としてfilterに渡す。予測対象、月次・四半期の単位、集計方法、公表順序と標本末端を固定して新旧の情報集合を作る。新releaseをまとめた $z$ と $S=\operatorname{Var}(z\mid\mathcal I_v)$ について $Sw=\operatorname{Cov}(z,Y\mid\mathcal I_v)$ を解き、更新を $w'[z-E(z\mid\mathcal I_v)]$ と計算する。$S$ が特異なときは同じ情報を重複する線形結合を特定し、独立な支持に対応する解を用いる。各releaseの寄与は同じ同時更新の $w_k\,news_k$ とし、その和と新旧予測差を照合する。

旧時点で $Y=x$、$x\sim N(2,1)$、$z_1=.6x+1.8+\nu_1$、$z_2=.2x+3.6+\nu_2$ とし、観測誤差は状態と独立、共分散は $\begin{pmatrix}.14&-.02\\-.02&.36\end{pmatrix}$ とする。旧予測は $(E[Y],E[z_1],E[z_2])=(2,3,4)$、$S=\begin{pmatrix}.5&.1\\.1&.4\end{pmatrix}$ である。新release $(4,3.5)$ のnews $(1,-.5)$、重み $(22/19,4/19)$ から、更新幅は $20/19$、新予測は $58/19$、更新後の状態分散は $5/19$ となる。推定係数を再推定した場合は、その変更による予測差も同じ新旧vintageで計算する。

`statsmodels` の `MLEModel.smooth` と `MLEResults.news` を使い、旧・新のfilter値、news、同時更新の重みと寄与合計を直接照合する。パラメータは新旧で固定する。

