<a id="info-06"></a>

## INFO-06 現在バイアス

時点 $t$ の主体が $u_t+\beta\sum_{k\ge1}\delta^k u_{t+k}$、$0<\beta\le1$、$0<\delta\le1$ を最大化し、和は有限とする。今期から将来への割引には $\beta\delta$ がかかり、将来の二つの隣接期の比較には $\delta$ がかかる。β<1 では、将来の行動が現在の行動に変わると、その時点の利得に対する将来利得の相対重みが β 倍となる。翌期に費用 $c$ を払い、その次の期に便益 $B$ を得る計画では、$\beta\delta B<c<\delta B$ なら今期は実行を選ぶが、翌期には中止を選ぶ。β=1 では指数割引となり、情報と制約が変わらなければ将来時点の再最適化は当初の計画と一致する。将来の再最適化を予見する主体は、拘束的な貯蓄や期限の設定も現在の選択に含める。

この準双曲割引（quasi-hyperbolic discounting）では、各時点の自己を当期の行動を選ぶ主体として扱う。[Laibson (1997), §II、式(1)、pp.449–451](https://laibson.scholars.harvard.edu/sites/g/files/omnuum5971/files/laibson/files/golden_eggs_and_hyperbolic_discounting.pdf) は、この自己間のゲームを部分ゲーム完全均衡で解く。将来自己の再最適化を予見する主体を sophisticated、将来自己が現在の計画を実行すると予測する主体を naive とする。コミットメントは将来の実行可能な行動集合を拘束する。

有限期間 $t=0,\ldots,T$ で、状態を $s$、行動集合を $A_t(s)$、遷移を $P_t(s'\mid s,a)$、終端利得を $W_T(s)=g(s)$ とする。各状態の行動集合は非空で、次の目的関数の最大値を持つものとする。将来自己の行動を予見する主体は、終端から逆向きに

\[
\pi_t(s)\in\arg\max_{a\in A_t(s)}
\left\{u_t(s,a)+\beta\delta E[W_{t+1}(s')\mid s,a]\right\},
\qquad
W_t(s)=u_t(s,\pi_t(s))+\delta E[W_{t+1}(s')\mid s,\pi_t(s)]
\]

を解く。$W_t$ は実現する方策列の指数割引価値であり、現在自己が行動を比較するときに将来価値へ $\beta$ を掛ける。定常の無限期間問題では $0<\delta<1$ と有界な当期効用の下で同じ二式を同時に満たす方策と価値を求め、固定方策の評価にはDYN-02を割引因子 $\delta$ で使う。$\beta=1$ では通常のBellman式になる。割引因子を毎期 $\beta\delta$ とすると二期先の重みは $\beta^2\delta^2$ となり、元の選好の $\beta\delta^2$ と異なる。[QuantEconの現在バイアス計算](https://python-advanced.quantecon.org/organizational_equilibrium.html#separating-the-state-from-the-actions) の `action_payoff` も、将来方策の指数割引評価と当期自己の評価を分ける。同教材の $\beta$ は本節の $\delta$、同教材の $\delta$ は本節の $\beta$ に対応する。

独自例として $\beta=1/2,\delta=9/10$ とし、時点1の実行 $e\in\{0,1\}$ が費用 $4e$ と時点2の便益 $6e$ を生む。時点0には費用 $2/5$ で実行を拘束する契約を購入できる。拘束がなければ時点1の実行価値は $-4+\beta\delta\,6=-1.3$ なので $e=0$ を選ぶ。拘束すると $e=1$ が実行され、$W_1=-4+\delta\,6=1.4$、時点0の契約価値は $-0.4+\beta\delta W_1=0.23$ となる。将来の中止を予見する主体は、契約なしの価値0と比較して購入する。naiveな主体は契約なしでも実行すると予測し、その計画価値 $\beta(-4\delta+6\delta^2)=0.63$ を契約価値0.23と比べて購入せず、時点1には実行を中止する。$\beta=1$ では拘束なしで実行し、時点0の価値は1.26、契約付きは0.86となる。

計画からの離脱を調べる際は、同じ支払・消費の時点を保ち、現在をまたぐ選択と二つの将来時点の選択を比べて $\beta$ と $\delta$ を識別する。再最適化を予見する主体と予見しない主体は、拘束契約の購入と期限前の行動に異なる予測を持つ。「present bias sophistication commitment demand」を調べ、流動性、実行費用、新しい情報を記録して計画変更の原因を比較する。econ-dataでは上の行動選択と価値評価を状態ごとに計算し、実現行動、拘束費用、各時点の自己の価値を同じ方策から求める。

