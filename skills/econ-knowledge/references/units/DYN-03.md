<a id="dyn-03"></a>

## DYN-03 消費、Euler 方程式と終端条件

資産 $a_t$、所得 $y_t$、粗利子率 $R$ の家計が $E_0[\sum_{t\ge0}\beta^tu(c_t)]$ を最大化し、$a_{t+1}=Ra_t+y_t-c_t\ge\underline a$ を満たすとする。内点では消費一単位を現在から次期へ移す比較から $u'(c_t)=\beta R E_t[u'(c_{t+1})]$ を得る。借入制約が結合する場合は $u'(c_t)\ge\beta R E_t[u'(c_{t+1})]$ である。対数効用の具体的な内点Euler式と予算の検査はDYN-05の数値例を使う。

包絡線条件は $V_a(a,y)=R u'(c)$ で、資産一単位の価値はその期に消費できる資源の限界効用に等しい。遺産効用0、非負資産、利得有限の無限期間内点問題では、終端に消費可能な価値を残さない横断性条件 $\lim_{T\to\infty}E[\beta^T u'(c_T)a_{T+1}]=0$ を課す。初期資産、所得遷移、借入下限、効用と利子率を定めて方策を求める。

生産した資源を消費と次期への投資に分ける最適成長では、現在の資源を $y>0$、消費を $0<c<y$、次期資源を $y'=f(y-c)z$ とする。生産性 $z>0$ は独立同分布、$0<\beta<1$ とし、効用 $u$ は増加・厳密凹、生産関数 $f$ は増加・凹とする。以下の微分と期待値が存在し、価値が有限で最適消費が内点にある場合、Bellman式と包絡線条件は

\[
V(y)=\max_{0<c<y}\{u(c)+\beta E[V(f(y-c)z)]\},\qquad
V'(y)=u'(c^*(y))
\]

となる。消費から投資へ微小に移すとき、投資に対する次期資源の限界収益は $f'(y-c)z$ である。この限界収益と次期限界効用を用い、将来の消費方策 $\sigma$ に対する更新消費を

\[
u'(c)=\beta E\!\left[u'\{\sigma(f(y-c)z)\}f'(y-c)z\right]
\]

の根として求める。Coleman–Reffett作用素は、この根によって新しい方策 $K\sigma$ を定める。時間反復は $\sigma_{n+1}=K\sigma_n$ と更新する。正で増加する連続方策 $0<\sigma(y)<y$ の下では、左辺から右辺を引いた関数は $c$ について厳密に減少する。可行区間内の両端でその符号が正から負へ変われば、内点根は一意に定まる。

[QuantEconのPython時間反復](https://github.com/QuantEcon/lecture-python.myst/blob/4d82fffbb1280f8f6980a45dbe518e677f5c9a39/lectures/os_time_iter.md)では、`euler_diff` がこの差を計算し、`K` が各状態で `brentq` により求根する。[Julia版](https://github.com/QuantEcon/lecture-julia.myst/blob/18877b5dd22cba3530089a3a3f3de23f427b8656/lectures/dynamic_programming/coleman_policy_iter.md)の `K!` は同じ式を `find_zero` で解き、`K` は出力を確保してその処理を呼ぶ。どちらも将来方策を線形補間し、固定したショック標本で期待値を計算する。Pythonの `np.interp` は格子外に端点値を使い、Juliaの `LinearInterpolation(...,extrapolation_bc=Line())` は線形外挿する。DYN-04の条件に従い、比較する格子・積分・境界処理を揃える。

滑らかな連続選択で内点根が一意なら、この時間反復を選べる。借入・投資制約が等号で成立する境界では、Euler不等式と可行性を用いる。離散行動や非微分点を含む選択は、DYN-02のBellman右辺の最大化で比較する。Howard方策反復は固定方策の価値評価と行動改善を繰り返す。計算費用は同じ格子・積分と経済量の精度目標の下で、最大化、方策評価の線形系、Euler求根に要する時間を比べる。方策更新差と元のEuler残差に許容値を定め、求めた方策を資源式、Euler等式・不等式と横断条件へ戻して評価する。

例えば $u(c)=\log c,\ f(k)=\sqrt{k},\ z=1,\ \beta=4/5$ とする。$V(y)=A+B\log y$ をBellman式へ代入すると $B=1+\beta B/2=5/3$、$A=5\log(3/5)+(10/3)\log(2/5)$ となる。消費の一階条件 $1/c=(\beta B/2)/(y-c)$ と厳密凹性から、$c^*(y)=3y/5$、投資 $y-c^*(y)=2y/5$ を得る。$y=1$ では $c=3/5,\ y'=\sqrt{2/5},\ c'=3\sqrt{2/5}/5$ なので、

\[
\frac1c=\frac53
=\frac45\frac{1}{3\sqrt{2/5}/5}\frac{1}{2\sqrt{2/5}}.
\]

資源式とEuler式が成立し、割引した投資の限界価値 $\beta^t u'(c_t)(y_t-c_t)=(2/3)(4/5)^t$ は0へ収束する。資本を状態とするDYN-04の例とは $y=f(k)$ で対応する。

