<a id="demand-05"></a>

## DEMAND-05　生産関数と生産性

対数生産を \(y_{it}=\beta_0+\beta_kk_{it}+\beta_\ell\ell_{it}+\beta_m m_{it}+\omega_{it}+\varepsilon_{it}\) とする。企業が \(\omega\) を見て投入を選ぶため、投入と生産性が連動する。投入の時点、固定・可変区分、技術ショックと測定誤差を定義する。

企業が当期の \(\omega_{it}\) を見て中間投入 \(m_{it}\) を選び、\(m_{it}=m_t(k_{it},\omega_{it})\) が各 \(k,t\) で \(\omega\) に厳密に単調なら、観測支持上で \(\omega_{it}=h_t(k_{it},m_{it})\) と逆算する。投資をproxyとする場合も、その決定時点と単調な政策関数を同じように指定する。資本は当期の生産性innovationより前に決まり、労働は当期生産性を見て選ばれるとする。第一段階では \(E[\varepsilon_{it}\mid k_{it},\ell_{it},m_{it}]=0\) の下、
\[
\phi_t(k,\ell,m)=E[y_{it}\mid k,\ell,m]
=\beta_0+\beta_k k+\beta_\ell\ell+\beta_m m+h_t(k,m)
\]
を柔軟な関数として推定し、\(\hat\phi_{it}\) を得る。第一段階では \(\beta_m m\) と \(h_t(k,m)\) が同じ柔軟な関数に含まれるため、\(\beta_m\) をここから分離できない。労働がproxyと関数的に従属する場合は当期労働係数も分離しない。例えば第1段階の条件付き平均が $\phi=1+2k+3\ell+5m$ なら、$\beta_m=4,h=m$ と $\beta_m=2,h=3m$ はともに同じ $\phi$ を与え、どちらのproxy関数も $m$ に増加する。$k=\ell=1,m=2$ で両者とも16となるため、この段階だけで $\beta_m$ は分離できない。定数項と生産性の水準正規化は後段で揃える。

第二段階で候補 \(b=(b_k,b_\ell,b_m)\) に対し \(\hat\omega_{it}(b)=\hat\phi_{it}-\hat\beta_0(b)-b_kk_{it}-b_\ell\ell_{it}-b_m m_{it}\) とする。水準の正規化として \(\hat\beta_0(b)=n^{-1}\sum_{it}(\hat\phi_{it}-b_kk_{it}-b_\ell\ell_{it}-b_m m_{it})\) と置き、\(\hat\omega\) の標本平均を0にする。生産性遷移を \(\omega_{it}=g(\omega_{i,t-1};\alpha)+\nu_{it}\) とし、先決情報 \(\mathcal I_{i,t-1}\) に関する条件付き平均が \(E[\omega_{it}\mid\mathcal I_{i,t-1}]=g(\omega_{i,t-1};\alpha)\) に従うという条件付き平均の制約を置く。これにより、先決情報に含まれる操作変数はinnovationと直交する。例えば定数項と多項式の係数 \(\alpha\) を用いて、先決の \(Z_{it}\) に対する標本条件
\[
\hat g_n(b,\alpha)=\frac1n\sum_{i,t} Z_{it}
[\hat\omega_{it}(b)-g(\hat\omega_{i,t-1}(b);\alpha)]=0
\]
の二次形式 \(\hat g_n'W\hat g_n\) を最小化する。例えば当期資本と前期労働を使う場合は、それらが当期 \(\nu\) と直交する時点・情報条件を置く。候補 \((b,\alpha)\) の自由係数と同数以上の有効なモーメント、モーメントJacobianの列rank、入力・proxyの共通支持と逆写像の単調性を確認する。proxyと労働の関数従属性や弱い先決変動でrankが落ちる場合、追加の時点制約・観測変動が係数を識別する設計を選ぶ。複数初期値から目的と元のモーメントを確認し、企業単位bootstrapで第一段階と第二段階を共に再推定する。

需要推定の未観測品質 \(\xi\) は消費者の製品選択に入り、生産関数の \(\omega\) は企業が投入を選ぶ時点で把握する生産性である。需要の価格内生性には価格を動かして需要誤差に直交する変動が要り、生産性推定には資本・労働・材料の決定時点、proxyの逆写像とinnovationに直交する先決変動が要る。両方を求める場合は企業・製品・市場・年の鍵で数量、売上、価格、投入を結び、収入のみの標本では製品価格と需要の差を観測式へ加える。`production function proxy timing functional dependence` と `demand production physical productivity revenue prices` で投入選択の方法論論文、製品別数量・価格の統計仕様、企業の費用記録を調べる。価格や投入の時点が選んだ直交条件に反すれば、econ-designで操作変数と対象を変更し、econ-dataで第一段階と第二段階を再推定する。

売上生産性には価格と需要の差が入る。数量技術、物的生産性、売上生産性をそれぞれの観測式で定義する。複数製品や退出選択は、観測された企業・製品集合の選択機構へ含める。

