<a id="contract-02"></a>

## CONTRACT-02 私的情報と選別

能力や費用のタイプ $\theta$ を代理人だけが知るとき、依頼人は報酬と配分の組 $(t(\theta),q(\theta))$ のメニューを提示する。効用が $U(\theta)=\theta q(\theta)-t(\theta)$ なら、各タイプが自分の組を選ぶ条件は $\theta q(\theta)-t(\theta)\ge\theta q(\hat\theta)-t(\hat\theta)$ である。上下二つのタイプの条件を足すと、高タイプに低タイプ以上の数量を割り当てる単調性が得られる。

連続タイプで誘因両立する配分の包絡条件は、ほとんど至る所で $U'(\theta)=q(\theta)$、したがって $U(\theta)=U(\underline\theta)+\int_{\underline\theta}^\theta q(s)ds$ である。正の密度 $f$、分布 $F$ のタイプに非負の数量を供給し費用を $C(q)$ とすると、期待利潤は下端の参加効用を除き、仮想価値 $\theta-(1-F(\theta))/f(\theta)$ に数量を掛けた値から費用を引いて最大化する形になる。仮想価値が単調なら各タイプの配分を最大化して契約に戻し、単調性を満たさない領域は配分を一括して調整する。例えば $\theta\sim U[0,1]$、$C(q)=q^2/2$、$q\ge0$ では仮想価値は $2\theta-1$、最適数量は $q(\theta)=\max(0,2\theta-1)$ である。最低タイプの効用を0にすると、$\theta>1/2$ では $U(\theta)=(\theta-1/2)^2$、支払は $t(\theta)=\theta^2-1/4$ となる。$\theta\le1/2$ は数量と支払が0であり、全タイプで数量が非減少である。

この一次元の式を使う判断条件は、タイプが配分への限界評価を一つの順序で表し、メニューへ拘束でき、タイプ別の外部機会が定義されることである。複数属性の私的情報、タイプに依存する留保効用、数量と品質の共同選択を観測したら、元の全申告間の誘因条件へ戻る。調査する語は「multidimensional screening incentive compatibility」「single crossing ironing participation constraints」であり、タイプ分布と選択肢・非購入の記録を用いてどの制約が効くか決める。econ-dataへ渡す有限タイプの計算では、各タイプの全報告先との効用差、参加条件、数量制約を元の効用で検査し、配分と情報レントを返す。

