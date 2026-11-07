# 投資の内生性と生産の反応

## 研究課題と識別

生産性の高い企業ほど多く投資するとき、観測された投資と生産の関係は、投資が生産を変える効果と、生産性による企業間の違いを含む。本例は、同じ1,200企業のOLSとIVを比較し、この二つの変動が投資係数へどう現れるかを示す。

独自に生成した一時点の企業データを用いる。投資Iと生産Yは共通の基準からの乖離であり、生成式は

$$I=0.9z+0.4x+0.7u+v,\qquad Y=1.8I+0.5x+u+e$$

である。z、x、u、v、eは独立の標準正規変数であり、乱数シードは20261108である。xは観測された初期生産性、uは観測されない生産性である。uが投資と生産をともに増やすため、xを調整したOLSの投資係数は、この共通変動を含む。投資インセンティブzは投資を動かし、生産式の誤差u+eから独立である。この排除条件と共分散の非零条件の下で、zによるIVは、一定の生産反応1.8を識別する。

## Results

表1は同じ企業IDと観測値を用いた二つの推定結果を示す。OLSの投資係数は2.0898 生産単位／投資単位、IVの係数は1.8321 生産単位／投資単位である。それぞれの標準誤差は0.0249 生産単位／投資単位、0.0440 生産単位／投資単位となる。両列は初期生産性と定数項を含む。

| 項目 | OLS | IV |
| --- | ---: | ---: |
| Investment | 2.0898 | 1.8321 |
|  | (0.0249) | (0.0440) |
| Initial productivity | 0.3488 | 0.4602 |
|  | (0.0418) | (0.0459) |
| Constant | 0.0390 | 0.0672 |
|  | (0.0391) | (0.0409) |
| 観測数 | 1200 | 1200 |

表1　投資と生産の比較。括弧内は各公式推定器が保存した標準誤差。投資係数は投資1単位当たりの生産単位を表す。OLSはHC1共分散、IVは自由度補正を伴う不均一分散頑健共分散を用いる。標本は同じ1,200企業である。

投資インセンティブzを除外操作変数とする第一段階のWald統計量は635.6581であり、保存結果の参照分布は自由度1のカイ二乗分布である。この統計量は、初期生産性を調整した第一段階におけるzの係数が0という帰無仮説を検定する。zが生産誤差から独立であるという識別条件は、データ生成式の独立性と排除によって定まる。

## Discussion

観測されない生産性uが高い企業は、同じ初期生産性xでも投資と生産がともに多い。OLSはこの企業間の共変動を投資係数へ含めるため、生成式の一定の反応1.8より大きい係数を返す。IVはzが動かす投資変動を用い、保存結果では係数1.8321を得る。この比較は、同じ標本の下で、投資と生産の射影関係と、排除されたインセンティブによって識別する生産反応を結び付ける。

## English results paragraph

Using the same 1,200 producers and controlling for initial productivity, OLS gives an investment coefficient of 2.0898, with a standard error of 0.0249. IV uses the excluded investment incentive and gives 1.8321, with a standard error of 0.0440. Coefficients measure output units per investment unit. The common productivity shock raises both investment and output and therefore enters the OLS projection. Independence and exclusion of the incentive identify the constant structural response in the IV specification.

## Sources and execution

- [Original generated observations](../../models/common-regression-data.csv)
- [OLS specification](../../models/common-ols-spec.json) and [official statsmodels result](../../models/common-ols-result.json)
- [IV specification](../../models/common-iv2sls-spec.json) and [official linearmodels result](../../models/common-iv2sls-result.json)
- [Common regression table](../../gallery.json): `specialist-common-ols-iv-table`

- [Execution and coefficient comparison](execution.json): `common_regressions`
