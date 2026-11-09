<a id="struct-04"></a>

## STRUCT-04　CCP、MPEC、逐次更新

有限状態 \(s\)、行動 \(a=0,\ldots,A\)、割引率 \(0<\beta<1\)、行動別遷移行列 \(P_a\) とflow \(u_a(s;\theta)\) を定める。選択前に観測する独立な極値ショックの尺度を \(\sigma>0\) とし、flowと価値を同じ尺度で測る。基準行動0の位置と効用尺度を正規化すると、選択別価値 \(v_a=u_a+\beta P_aV\) と条件付き選択確率は
\[
p_a(s)=\frac{e^{v_a(s)/\sigma}}{\sum_b e^{v_b(s)/\sigma}},\qquad v_a-v_0=\sigma\log(p_a/p_0).
\]
期待ショックのEuler定数分 \(\sigma\gamma\) を各期の全行動から差し引くと、期待価値は \(V=\sigma\log\sum_a e^{v_a/\sigma}\) となる。共通定数を残す場合は下の右辺に \(\sigma\gamma\) を加える。

第一段階で状態・行動ごとの選択頻度または条件付き確率モデルと遷移 \(P_a(s,s')\) を推定する。逆算する全行動の \(p_a(s)>0\)、遷移と選択の十分な支持を確認する。政策 \(p\) に対して \(P_p=\sum_a\operatorname{diag}(p_a)P_a\)、\(h(p)_s=-\sum_a p_a(s)\log p_a(s)\) とおけば、政策評価は
\[
V_p=(I-\beta P_p)^{-1}[\sum_a p_a u_a+\sigma h(p)].
\]
上式をlog oddsへ代入してflow係数を推定する。独立な個体単位で第一段階と第二段階を共に再推定するbootstrap、または第一段階の影響関数を含む分散を使う。遷移も推定する場合はその誤差も含める。

方法は利用可能な支持、解の条件と計算量で選ぶ。指定した尤度と状態遷移が妥当で、各候補の収縮固定点を十分な精度で解けるならNFXPを使う。状態・行動ごとの選択確率と遷移を安定して推定できるならCCP逆算が候補となる。観測が疎で0となる確率を任意の小数に置き換えても、必要な支持や識別は生じない。観測をまとめる・構造を変更する・別の推定法を使う場合は、その仮定と対象を明示する。MPECは同じ尤度と疎な均衡制約を同時に最適化できる場合に選び、実行可能性と局所解を複数初期値・元式残差で確認する。NPL・EPLは初期政策と逐次写像の局所収束、EPLのJacobian正則性を点検できる場合に選び、更新が小さいだけでなく元の均衡残差と尤度を検査する。

共通の研究対象を、同じ状態・行動履歴と選好・遷移の下での構造係数および政策後の選択率とする。NFXPは各候補で内側の価値固定点を解き、MPECは価値と係数を同時に選んで同じ固定点を制約するため、同一の尤度・支持・制約を使う比較ができる。CCPは各状態の第一段階確率と遷移を使って価値差を逆算し、第一段階誤差を推論へ伝える。NPLは推定と政策改善を反復し、EPLは前回の基準点で固定した残差Jacobianを使う。逐次法の利点は候補ごとの完全な内部解を繰り返さずに済む点にあり、局所更新の収束条件と元の均衡残差を検査する。方法を変更すると内側の計算、標準誤差、得られる局所候補が変わるため、共通標本上の尤度またはモーメントと政策後の行動・厚生を再評価する。

追加の調査では `dynamic discrete choice CCP first stage support transition inference`、`nested fixed point MPEC same likelihood constraints`、`dynamic game NPL EPL local convergence equilibrium selection` を使い、識別と第一段階を扱う方法論論文、各推定器の公式実装資料、標本の状態遷移記録を照合する。稀な状態の支持や遷移誤差が推定対象を変えるときは状態の集約と情報集合をecon-designで再指定し、econ-dataで同じ選択履歴に各候補法を適用する。推定標本と政策標本の到達可能な状態、元のBellman・確率残差、個体単位の再標本化を照合する。

NFXPは各 \(\theta\) でBellman固定点を解き \(\sum_{it}\log p_{a_{it}}(s_{it})\) を最大化する。MPECは同じ \(\theta,V,p\) と同じ尤度を選び、\(V-\sigma\log\sum_a\exp[(u_a+\beta P_aV)/\sigma]=0\) と同じ遷移・情報集合・支持・パラメータ制約・均衡選択を課す。両法の尤度と元のBellman残差を同じ許容誤差で比較する。

政策改善写像を \(\Psi(\theta,p)=\operatorname{softmax}[(u_a+\beta P_aV_p)/\sigma]_a\)、均衡残差を \(G(p,\theta)=p-\Psi(\theta,p)\) とする。NPLは \(p^k\) を固定して \(\theta^{k+1}=\arg\max_\theta\ell(\Psi(\theta,p^k))\)、次に \(p^{k+1}=\Psi(\theta^{k+1},p^k)\) とする。固定点での合成更新写像のJacobianのスペクトル半径が1未満なら局所収束する。EPLのNewton型政策近似は \(\widetilde p(\theta;p^k,\theta^k)=p^k-G_p(p^k,\theta^k)^{-1}G(p^k,\theta)\) とする。逆行列の評価点を前回の \((p^k,\theta^k)\) に固定し、この近似を尤度へ入れて \(\theta^{k+1}\) を最適化した後、\(p^{k+1}=\widetilde p(\theta^{k+1};p^k,\theta^k)\) とする。逐次線形制約（SLC）は基準点 \((p^k,\theta^k)\) の \(G+G_p\Delta p+G_\theta\Delta\theta=0\) を尤度最大化の制約として解き、基準点を更新する。逆行列は実際には線形系として解き、確率単体の独立座標を使う。既存の `research_dynamic` ゲーム実装は二行動ごとに独立なlog odds \(x=\log[p/(1-p)]\) を変数とし、残差 \(G_x=x-\operatorname{logit}\Psi(\theta,\operatorname{logistic}x)\) のJacobianを前回の \((x^k,\theta^k)\) に固定してEPLを更新する。確率座標のNewton更新とlog odds座標のNewton更新は同じ均衡根を表すが、座標変換が非線形なので途中の反復値が一般に一致するとは限らない。局所Newton更新でも \(G_p\) の正則性と初期値が必要で、各反復後に元の \(G\)、Bellman式、尤度、確率の和を再評価する。

同じ尤度を3方法で比べる二状態例を考える。状態 \(s\in\{L,H\}\)、行動 \(a\in\{0,1\}\)、\(\beta=.5\)、flow \(u(s,a)=1\{s=H\}+a(\theta+.4)\) とする。行動0の次期状態は \(L\)、行動1では \(H\) で、極値ショックの尺度は1である。状態別に行動0が10回、行動1が30回観測される。両行動の遷移は現在状態に依存せず、当期flowの差が1なので \(V(H)-V(L)=1\)。標本CCPは各状態で .75、逆算式は \(\log(.75/.25)=\theta+.4+.5\) となり、\(\hat\theta=\log3-.9=.198612289\) である。

全状態・行動に正の標本支持があり、この例の固定係数と遷移を使うと選択確率の未知係数への感応度は正である。実証標本では個体・市場の依存と第一段階推定を含めて分散を計算する。

