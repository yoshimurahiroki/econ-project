<a id="het-04"></a>

## HET-04　sequence-space Jacobian

集計量の応答を、状態別の政策反応と分布の移動に分解する。状態別の政策と遷移が問題の入力として与えられている場合は、DYN-01の分布更新とMATH-02の線形系を使い、下記の集計式からJacobianと均衡応答を求める。政策を原始的要素から求める場合は、採択した計算に対応する本文を追加する。

| 求める経済的対象 | 追加する知識 | `plan`の条件 |
| --- | --- | --- |
| 所得過程・選好・価格から家計の消費・貯蓄政策を解く | HET-01 | `household_policy=endogenous` |
| 家計政策・分布・生産から定常の資本・価格を清算する | HET-02 | `equilibrium_model=aiyagari` |
| 名目硬直性、金融則、財政と異質家計を閉じる | HET-03 | `equilibrium_model=one_asset_hank` |

`plan HET-04 --read` は共通の前提を取得する。例えば家計から求める一資産HANKでは `--context household_policy=endogenous --context equilibrium_model=one_asset_hank` を加える。条件は問題の入力と求める均衡から選ぶ。所与の家計反応を集計する計算では、その反応の定義、時点、初期分布を保持する。

期首状態を資産 \(a\) と所得 \(z\)、所得遷移を \(\Pi(z,z')\) とする。価格・所得経路 \((r_t,w_t,T_t)\) を予見する家計は、\(a'\ge\underline a\)、\(c>0\)、\(c+a'=(1+r_t)a+w_tz+T_t\) の下で
\[
V_t(a,z)=\max_{c,a'}\{u(c)+\beta\sum_{z'}\Pi(z,z')V_{t+1}(a',z')\}
\]
を解く。期 \(t\) に \(a'\) を選び、次期に \(z'\) が実現する。内点では \(u'(c_t)=\beta(1+r_{t+1})E_tu'(c_{t+1})\)。借入下限では \(u'(c_t)-\beta(1+r_{t+1})E_tu'(c_{t+1})\ge0\)、これと \(a'-\underline a\ge0\) の積が0となる。

終端価値を与え、\(T-1\) から後向きに政策 \(g_t(a,z)=a'\) と \(c_t\) を解く。資産grid \(a_m\le g_t\le a_{m+1}\) に対し \(\lambda=(g_t-a_m)/(a_{m+1}-a_m)\) とし、\((1-\lambda)\Pi(z,z')\) と \(\lambda\Pi(z,z')\) を隣接gridへの遷移確率にする。行和1の作用素 \(P_{g_t}\) は分布列を \(\mu_{t+1}=P_{g_t}'\mu_t\) と動かし、質量と政策資産の一次モーメントを保存する。\(Y_t=\sum_{a,z}\mu_t(a,z)y_t(a,z)\) で消費や資産を集計する。

定常状態近傍で \(J_{ts}^{Y,X}=\partial Y_t/\partial X_s\) とする。初期分布固定の一次変化は
\[
dY_t=\bar\mu' dy_t+\bar y' d\mu_t,\quad d\mu_{t+1}=\bar P_g' d\mu_t+(dP_{g_t})'\bar\mu.
\]
前者が状態別政策の直接効果、後者が分布構成効果である。各ショック時点の家計反応を後向きに作り、定常作用素の反復と期待値ベクトルを再利用して将来集計への寄与を組み立てる。sequence_jacobianの異質家計ブロックとJacobian組立はこの反復を共有する。一般均衡条件 \(H(U,Z)=0\) は内生経路 \(U\)、外生経路 \(Z\) に対し、\(H_U\) が正則なら \(H_UdU=-H_ZdZ\) を解く。

家計Euler/KKT、分布非負・質量1、市場清算、元の \(H\) を検査する。終端の定常条件と期間 \(T\) を延長し、関心期間の政策・集計が指定許容差内で一致するようにする。単発ショックの完全な非線形後向き・前向き再計算の中央差分を対応するJacobian列と比較する。有限な政策変更では価格経路と家計政策を元の非線形均衡で解き直す。

小さなショックの近傍応答にはSSJを選び、政策が借入制約への到達、価格設定や分布を大きく動かす場合は同じ初期分布と終端条件で非線形経路を解く。`sequence space Jacobian distribution household policy general equilibrium` と `heterogeneous agent nonlinear transition occasionally binding constraints` で家計Jacobianの計算法、借入境界と均衡条件を調べる。econ-dataはJacobian列を家計・分布の非線形中央差分と照合し、均衡解を元の市場清算式へ戻す。grid、所得状態と終端の変更が対象期間の応答または厚生を採択した許容差だけ変える場合、その精度を上げて再計算する。

`sequence_jacobian` の `hetblocks.hh_sim.hh_extended` は、所与の価格経路に対する家計ブロックを計算する。初期分布と終端の限界価値を指定し、家計の政策と分布を後向き・前向きに更新する。一般均衡では、価格経路を内生化して上記の $H$ を解く。

[現行の`sequence_jacobian.examples.hank.dag`](https://github.com/shade-econ/sequence-jacobian/blob/eb4ac4c3157357a4cacbea4b5a7a281f5b48cab9/src/sequence_jacobian/examples/hank.py)は10点の公開校正で定常状態を解き、`(hank_model_ss, ss, hank_model, unknowns, targets, exogenous)`を返す。別の資産格子や校正値を使う場合は、同じ公式ブロックから採択済みのモデルを構築する。定常モデルの`nkpc_ss`は\(w=Z/\mu\)を与え、移行モデルの`nkpc`は価格式の残差を返す。

`MC-hank-one-asset`の選択は、[公式`Block`の4操作](https://github.com/shade-econ/sequence-jacobian/blob/eb4ac4c3157357a4cacbea4b5a7a281f5b48cab9/src/sequence_jacobian/blocks/block.py)を分ける。`solve_steady_state(calibration,unknowns,targets)`は定常条件を解き、`solve_jacobian(ss,unknowns,targets,inputs,T=...)`は一般均衡Jacobianを返す。`solve_impulse_linear`と`solve_impulse_nonlinear`はショック名から配列への辞書を受け、線形・非線形の均衡経路を返す。移行の内生変数は`[w,Y,pi]`、目標は`[asset_mkt,goods_mkt,nkpc_res]`、外生入力は`rstar`と`Z`である。非線形操作は元の目標残差を各反復で判定する。実行結果には労働清算、家計予算、Euler条件、分布と終端条件も対応する経済量とともに保存する。

