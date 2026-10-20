# 機能別の短い例：日本語

Profile: default-micro. All settings, research designs, quantities and source sentences below are original fictional examples. Apply [profile principles](PROFILE.md#principles); read the function needed for the current passage.

## 結論と比較

Example ID: default-micro.ja.conclusion.

**Input:**
1年間の純便益を最大にするサービスを一つ選ぶ。送迎サービスの便益は8万4,000ポンド、費用は6万ポンド。自転車サービスの純便益は1万9,000ポンド。両案とも予算6万5,000ポンドに収まり、同時には実施できない。

**Ideal output:**
送迎サービスを採用する。1年間の便益8万4,000ポンドから費用6万ポンドを引いた純便益は2万4,000ポンドで、自転車サービスの1万9,000ポンドを5,000ポンド上回る。両案とも予算6万5,000ポンドに収まり、一つだけを実施できる。

**Generalizable operation:**
State the choice once at the beginning and compare the quantities used for the objective over a common period and in common units. State the net-benefit difference that determines the choice.

### 情報取得費用と効用の単位

等確率の二状態で、Aの金額は(64, 64)、Bは(144, 4)、効用は金額の平方根とする。完全情報の金銭費用は4。

情報を取得する。即時行動はAで、期待効用は8である。情報取得後は第一状態でB、第二状態でAを選び、金銭費用を引いた期待効用は(√140 + √60)/2 ≈ 9.789063となる。効用を10u + 5に変えると即時行動は85、情報取得は約102.890631で、選択は同じになる。金額を100倍の表示単位に変える場合は費用も400とし、効用を√(金額/100)とする。効用単位で別に定義した加法費用は、効用と同じ尺度で差し引く。

## 制度と機序

Example ID: default-micro.ja.mechanism.

**Input:**
協同組合は共同の製粉機に午前と午後の予約枠を設けた。午後に自家用車が空く農家は、その車で穀物を運び、運搬の外注費を省ける。次の文を、その仕組みが伝わる説明へ改稿する。「これは単なる予約制度の変更ではなく、農家の運搬方法にも影響する改革である。」

**Ideal output:**
午後に自家用車が空く農家は、製粉機の午後の利用を申し込み、その車で穀物を運べる。利用時間を車の空き時間に合わせることで、その荷物の運搬を外注する費用を省ける。

**Generalizable operation:**
Remove the “単なる変更ではなく” contrast that does no work in the conclusion and connect the farmer's reservation, available vehicle and transport cost.

## 数量と関係

Example ID: default-micro.ja.quantities.

**Input:**
2024年の修理店160店舗の観察データを説明する。有資格者の比率が20パーセントポイント高い店舗では、従業員1人時あたりの売上が平均12ユーロ高い。店舗間の相関を報告する。

**Ideal output:**
2024年に調べた160の修理店では、有資格者の比率が20パーセントポイント高い店舗ほど、従業員1人時あたりの売上が平均12ユーロ高かった。

**Generalizable operation:**
Put the observed relationship, population, period, comparison width and outcome unit in one sentence. State quantities directly.

## 改稿と翻訳

Example ID: default-micro.ja.translation.

**Input:**
次の契約規則を自然な日本語に訳す。Each tenant may renew the lease for one year if rent is paid in full and the building retains its occupancy permit. 家賃全額の支払いと使用許可の有効性は同時に必要な条件であり、規則は更新の許可を定める。

**Ideal output:**
各借主は、家賃を全額支払い、建物の使用許可が有効である場合に、賃貸借を1年間更新できる。

**Generalizable operation:**
Build the sentence in the target language.

## Abstract

Example ID: default-micro.ja.abstract.

**Input:**
アルダーベイ市の800世帯を無作為に二群へ分け、住宅調査の調査票に返信用の切手付き封筒を同封する効果を調べた。回答率は同封群64％、非同封群51％。この研究のAbstractを書く。

**Ideal output:**
返信用の切手付き封筒を同封すると、住宅調査の回答率が13パーセントポイント上がった。回答率は同封した群で64％、同封しなかった群で51％だった。アルダーベイ市の800世帯を無作為に二群へ分け、一群には調査票とともに返信用の切手付き封筒を送付して、この効果を推定した。

**Generalizable operation:**
Put the main result in the first sentence, followed by the 64 percent versus 51 percent comparison, population and assignment. Express the difference as 13 percentage points and make the Abstract self-contained.

## Introduction冒頭

Example ID: default-micro.ja.introduction.

**Input:**
同じ住宅調査のIntroduction冒頭を書く。返信用の封筒がない場合、世帯は調査票を返送する郵送料を負担する。封筒の同封で郵送料の支払いが不要になる。800世帯への無作為割当てによる回答率の差は13パーセントポイントだった。

**Ideal output:**
返信用の切手付き封筒を同封すると、住宅調査の回答率が13パーセントポイント上がった。封筒の同封によって、世帯は調査票を返送する郵送料を支払う必要がなくなる。本研究は、アルダーベイ市の800世帯への無作為割当てを使い、この変更が回答率に与える効果を推定した。

**Generalizable operation:**
Connect the main result to the institution changing households' costs and the comparison measuring its effect. Explain the return process in the Introduction instead of repeating the Abstract's group-specific response rates.

## 割当てと比較

Example ID: default-micro.ja.assignment.

**Input:**
職業訓練の定員を超える応募があり、受講機会を抽選で割り当てた。当選者と落選者のその後の有給就業を比較する研究設計を説明する。

**Ideal output:**
受講機会の抽選で当選した応募者と落選した応募者のその後の有給就業を比較し、職業訓練を受ける機会を得ることが就業に与える影響を推定する。

**Generalizable operation:**
Use the assignment mechanism and outcome comparison to explain the design. Include a regression specification when it determines the estimate's meaning or is needed for the requested explanation of the method.
