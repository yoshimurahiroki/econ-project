<a id="asset-04"></a>

## ASSET-04　複製、オプション、連続時間

二項株価で上昇倍率 \(u\)、下落倍率 \(d\)、無リスクgross rate \(R\)、\(d<R<u\) とする。価格付け確率は \(p^Q=(R-d)/(u-d)\)、請求権価格は \(R^{-1}[p^QX_u+(1-p^Q)X_d]\) である。株式と債券の複製から導く。ASSET-06に株価と行使価格を指定した実際の複製計算を示す。

連続時間で \(dS=\mu Sdt+\sigma SdW\)、一定金利 \(r\)、配当0、連続売買、\(\sigma>0\) の下では、複製価格は
\(\partial_tV+rS\partial_SV+\frac12\sigma^2S^2\partial_{SS}V-rV=0\)
を満たす。残存期間 \(T>0\) の欧州callは
\(C=S\Phi(d_1)-Ke^{-rT}\Phi(d_2)\)、
\(d_1=[\log(S/K)+(r+\sigma^2/2)T]/(\sigma\sqrt T)\)、\(d_2=d_1-\sigma\sqrt T\) となる。

早期行使は継続価値と行使価値の最大を後向きに取る最適停止である。信用商品ではdefault時点と回収を支払に入れる。零回収で、価格付け測度の下で強度 \(\lambda^Q\) が金利・強度の経路に条件付けたCox生存確率を定める場合、債券は \(E^Q[\exp(-\int(r+\lambda^Q)dt)]\) で価格付けする。

