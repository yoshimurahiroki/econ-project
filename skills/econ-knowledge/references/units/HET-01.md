<a id="het-01"></a>

## HET-01　不完全市場の貯蓄

資産 \(a\)、所得効率 \(e\)、借入下限 \(\underline a\) に対し

\[
V(a,e)=\max_{a'\ge\underline a}
\left\{u(we+(1+r)a-a')+
\beta\sum_{e'}P(e'|e)V(a',e')\right\}.
\]

消費正値と予算制約を可行集合へ入れる。内点Euler式は \(u'(c)=\beta(1+r)E[u'(c')]\)、借入境界では \(u'(c)\ge\beta(1+r)E[u'(c')]\) となる。所得リスクと曲率は将来消費の限界効用を通じて貯蓄を決める。対数効用による内点のEuler逆算はDYN-05、家計の予算・借入境界と集計を含む実行例はHET-04を参照する。

政策 \(a'=g(a,e)\) をVFI、PFI、EGMで求める。EGMは次期資産gridを固定し、Euler式を逆にして現在消費と現在cash-on-handを作り、借入拘束部分を継ぎ足す。grid外の遷移と上限は、資産分布が載る領域で評価する。

CRRAのEGMを実装する。各所得 \(e\) と次期資産格子 \(a'_j\) に対し、現在の政策候補から得た次期消費 \(c'(a'_j,e')\) を使い、\(c_j=[\beta(1+r)\sum_{e'}P(e'|e)c'(a'_j,e')^{-\gamma}]^{-1/\gamma}\)、\(a_j=[c_j+a'_j-we]/(1+r)\) を求める。\((a_j,a'_j)\) を現在の資産格子へ補間し、最小内生格子より下では \(a'=\underline a\)、予算から消費を作る。政策を反復し最大変化を許容差以下にした後、全状態の予算と正の消費、内点Euler残差、境界での符号と相補性積を検査する。非単調な内生格子が生じる非凸問題には候補の価値比較を備えた大域解法を選ぶ。

対数効用で \(\beta=.96,R=1+r=1.04,w e=w e'=1\)、次期に全資源を消費する終端を置く。\(a'=1\) なら \(c'=2.04\)、逆Eulerから \(c=2.043269\)、内生現在資産は \(a=1.964682\) である。予算 \(c+a'=Ra+1\) と \(1/c=\beta R/c'\) の残差は計算精度で0となる。この点は有限期間の終端に接続する内点の計算であり、定常政策には次期政策の反復が必要である。

恒久所得の変動を含む家計では、各期の期首資源、消費、期末資産を当期の恒久所得 \(p_t\) で割り、\(m_t=c_t+a_t\)、\(p_{t+1}=\Gamma\psi_{t+1}p_t\)、\(m_{t+1}=Ra_t/(\Gamma\psi_{t+1})+\theta_{t+1}\) とする。恒久所得shock \(\psi\) と一時所得shock \(\theta\) の同時分布を期待値に使う。CRRA係数 \(\gamma\)、生存確率 \(\ell\) の内点条件は \(c_t^{-\gamma}=\beta\ell R E[(\Gamma\psi_{t+1})^{-\gamma}c_{t+1}^{-\gamma}]\) であり、借入境界では左辺が右辺以上になる。各shockで次期資源を下限 \(\underline m_{t+1}\) 以上に保つ自然借入下限は \(a_t^N=\max_{\psi,\theta} (\Gamma\psi/R)(\underline m_{t+1}-\theta)\) で、人工的な制約 \(a_t^A\) を課す場合の下限は \(\max(a_t^N,a_t^A)\) である。EGMでは各期末資産から次期資源と期待限界効用を求めて消費を逆算し、拘束部分を接続する。

HARKの[公式ノートブック](https://github.com/econ-ark/HARK/blob/4c285e863cd1a60eb2a9c4ab335c7f86ea5aa767/examples/ConsIndShockModel/IndShockConsumerType.ipynb)は、`IndShockConsumerType(cycles=0, T_sim=120)` を構築し、`solve()` で無限期間の消費方策を求める。`aNrm`、`mNrm`、`cNrm`、`pLvl` を `track_vars` に指定し、`initialize_sim()` で初期状態と履歴を用意してから `simulate()` で家計の経路を作る。この固定版に保存された出力では、資源下限 `mNrmMin` は0、MPCの下限は .0445362734、上限は1である。正規化消費の横断面平均は `history["cNrm"]` を家計方向に平均して求め、水準消費は各家計の `pLvl` と `cNrm` の積を平均する。

数値解は元の条件へ戻して評価する。\(\zeta=1-c^\gamma\beta\ell R E[(\Gamma\psi)^{-\gamma}c'^{-\gamma}]\) と置き、内点で \(\zeta=0\)、借入境界で \(\zeta\ge0\)、相補性 \(\zeta(a-\underline a)=0\) を確認する。各期の予算は \(m-c-a\)、同一家計の次期資源は \(m'-Ra/(\Gamma\psi)-\theta\)、恒久所得は \(p'-\Gamma\psi p\) の残差で評価する。同版の[家計遷移コード](https://github.com/econ-ark/HARK/blob/4c285e863cd1a60eb2a9c4ab335c7f86ea5aa767/HARK/ConsumptionSaving/ConsIndShockModel.py)が記録する `PermShk` には \(\Gamma\) が含まれる。死亡・出生を含む模擬では、新生家計の遷移を初期化後の状態へ対応させる。格子点数、所得分布の離散化、資産領域を変え、対象とする資源での消費とこれらの残差を比較する。

