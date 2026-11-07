# 公開経済学実装とERSの対応

本資料は、公開実装の関数・API・Skill本文を、ERSの既存所有箇所、採用した変更、実行結果に対応させる。固定リンクは比較に用いた版を指す。採用した変更は正本の既存ランナー、知識catalog、Writing、binderへ実装した。

## 推定対象から公式推定器へ

| 比較元と実読箇所 | 計算を決める仕組み | ERSの既存経路と今回の採用 |
| --- | --- | --- |
| [DoubleML IRM](https://github.com/DoubleML/doubleml-for-py/blob/a3493c3b7a444b6ddd730ad05c2c0e6c67ac19c3/doubleml/irm/irm.py)、[PLIV](https://github.com/DoubleML/doubleml-for-py/blob/a3493c3b7a444b6ddd730ad05c2c0e6c67ac19c3/doubleml/plm/pliv.py)、[IIVM](https://github.com/DoubleML/doubleml-for-py/blob/a3493c3b7a444b6ddd730ad05c2c0e6c67ac19c3/doubleml/irm/iivm.py) | IRMのATE/ATTE、PLIVのpartialling-out/IV-type、IIVMのLATEは、それぞれのscore、nuisance、cross-fittingから係数と推論を計算する。 | `research_causal.py`の選択情報で止まっていた入口を、公式classの構築・`fit()`・保存へ接続した。標本ID、fold、score成分、nuisance予測、推論設定と公式の係数・SE・p値・区間を同じ結果に保存する。指定cluster foldsはラベルと行の対応を入口で確認する。 |
| [StatsPAI `dml/irm.py`](https://github.com/brycewang-stanford/StatsPAI/blob/0c04f715d7463ef2d7048dcda9e656d992c2c59a/src/statspai/dml/irm.py) | nuisance学習後にscoreと分散をパッケージ内で計算する。`sample_weight`の適用箇所が推定対象を決める。 | ERSはDoubleMLの公式scoreと推論を利用する。学習時の重みとターゲット集計の重みを採用仕様に対応させ、実際に渡した設定を保存する。 |
| [did `compute.aggte.R`](https://github.com/bcallaway11/did/blob/9ead26b9d37c7f2bc202bebc4f5e8220ab7e8c13/R/compute.aggte.R) | cohort質量と集計対象がATTの重みを定め、推定された重みの影響関数も分散へ入る。 | 既存の`att_gt`→`aggte`を保持した。dynamic/group/calendar等の対象、窓、重み、区間族と標本を保存する既存経路を使う。Writingでは集計対象と推論を結果定義から引き継ぐ。 |
| [PyFixest `_result_accessor_mixin.py`](https://github.com/py-econometrics/pyfixest/blob/2fb86f30a65f4ad9fa70b1e69bc8da6d0bbcd5db/pyfixest/estimation/models/_result_accessor_mixin.py) | `tidy()`と`confint()`が係数名に対応する公式の推定値・推論を返す。 | 既存HDFEランナーと推論保存を保持した。本文には観測・割付・分析・推論の単位と、採用したcovariance・参照分布を渡す。 |
| [GRF `average_treatment_effect.R`](https://github.com/grf-labs/grf/blob/5bee99b51471f76cb2d63acbc8a9b0ffec408ba0/r-package/grf/R/average_treatment_effect.R) | target sampleに対応したdoubly robust scoreを集計し、clusterごとの寄与から推論を得る。 | 既存の公式aggregateとpolicy経路を保持した。CATEの個体別予測、母集団平均、政策価値をそれぞれの計算定義で保存・説明する。 |

DoubleMLの実行版は[0.11.4の固定commit](https://github.com/DoubleML/doubleml-for-py/tree/96e32c9517812a8b8875dd74956704d7998f6510)である。IIVMの`normalize_ipw=True`にはinstrument propensityの正規化に処置を使う問題があり、公式修正は[commit e31e61e](https://github.com/DoubleML/doubleml-for-py/commit/e31e61efe8864c160c04488d91f1306e1e25c129)にある。ERSは該当版でその指定を拒否し、採用仕様を保ったまま修正版の使用を要求する。実行したLATE仕様は`normalize_ipw=False`である。

実装先：[causal runner](../../skills/econ-data/scripts/research_causal.py)、[causal model reference](../../skills/econ-design/references/causal-models.md)、[実装指針](../../skills/econ-data/references/implementation.md)。

GRFのselectorから実行仕様へ移る際に、標本重み・cluster列・区間水準が落ちる欠陥を修正した。`weights`と`inference.cluster`を公式`causal_forest`の`sample.weights`・`clusters`へ結び、指定水準を`average_treatment_effect`の推定値・SEから作る区間へ渡す。実際の重み、対象ID、cluster数、native fit、集計対象と推論を同じ結果へ保存する。[GRF 2.6.1の公式関数](https://github.com/grf-labs/grf/blob/5bee99b51471f76cb2d63acbc8a9b0ffec408ba0/r-package/grf/R/causal_forest.R)に対応する依存pinも追加した。

## モデル、動学、均衡と厚生

| 比較元と実読箇所 | 経済的対象と公式出力 | ERSで採用した実装 |
| --- | --- | --- |
| [HARK `AgentType.solve`](https://github.com/econ-ark/HARK/blob/4c285e863cd1a60eb2a9c4ab335c7f86ea5aa767/HARK/core.py)、[消費貯蓄モデル](https://github.com/econ-ark/HARK/blob/4c285e863cd1a60eb2a9c4ab335c7f86ea5aa767/HARK/ConsumptionSaving/ConsIndShockModel.py) | 消費者の効用、所得過程、価格、借入制約を受け、年齢・状態ごとの`cFunc`・`vFunc`を返す。 | 外部handoffで止まるselectorを既存macro runnerへ接続した。固定二期間例の自動実行を撤去し、採用されたconsumer class・parameters・評価gridから公式`solve()`を実行する。政策、価値、正規化、状態・年齢・scenario、指定したsimulationを保存する。実行版は[HARK 0.17.2](https://github.com/econ-ark/HARK/tree/269085077b84cb50feb49d0cd54bbf4da5fa3199)。 |
| [QuantEcon `DiscreteDP.solve`](https://github.com/QuantEcon/QuantEcon.py/blob/d30c9000a96d7ae1d434bdecb4aa63d285a18599/quantecon/markov/ddp.py) | 報酬、遷移、割引から価値、政策添字、政策下のMarkov連鎖を返す。有限期間では終端価値が必要になる。 | 既存Aiyagari経路で公式の動学計画を使う。状態座標・行動値・政策・価値を既存結果へ保存する構造を保持した。 |
| [dcegm `backward_induction.py`](https://github.com/OpenSourceEconomics/dcegm/blob/6914875e57f4fe3a6de50c2f3ddb9e56cba7f93c/src/dcegm/backward_induction.py) | 終端、状態間の依存、内生grid、上包絡線から離散・連続選択の価値と政策を計算する。 | ERSの`lifecycle_choice`はpylcmの`Model.solve`・`Model.simulate`への仕様引継ぎを返す。状態、期間、離散・連続選択のタイミングをこの既存入口に対応させ、今回の固定モデル契約ではHARKの実行接続を採用した。 |
| [respy `get_solve_func`・`solve`](https://github.com/OpenSourceEconomics/respy/blob/91e8a193fb7d5cf7212c15e50ae43f810bb9b1eb/respy/solve.py) | 採用状態空間、報酬、遷移、ショックから後ろ向きに期待価値を求める。 | `finite_horizon_choice`はrespyの公式criterion・simulation入口と必要引数を返す。既存の仕様引継ぎを保持し、ERS内の動学runnerから固定模擬panel・case生成を削除した。 |
| [PyBLP `Problem.solve`](https://github.com/jeffgortmaker/pyblp/blob/16536807004b16c24fb40b931531b45b33884e00/pyblp/economies/problem.py)、[`ProblemResults.to_pickle`](https://github.com/jeffgortmaker/pyblp/blob/16536807004b16c24fb40b931531b45b33884e00/pyblp/results/problem_results.py) | 需要・供給のmoment、instrument、重み、最適化から構造parametersと推論を得る。native fitは積分点・重み・推定パラメータを保持し、変更後の所有・費用で均衡を解く。 | 0.61.0では別の反実仮想を実行するたびに`Problem.solve`を呼んでいた。既存market runnerの結果JSONに公式fitを保存し、`counterfactual`入口から再利用する経路を加えた。入力の版とfitのhashを対応させ、同じパラメータ・消費者分布から価格・数量・利益・余剰・共通displayを返す。 |

### 既存モデル契約の実行接続

| 契約 | 選択から既存計算へ渡す入力 | 保存する経済量 |
| --- | --- | --- |
| Binary Logit | 採用したパラメータ、説明変数、観測量 | 選択確率、moment、解析Jacobian |
| Cournot競争 | 逆需要、費用、企業、均衡条件 | 数量、価格、利潤、最適反応残差 |
| 有限期間SIR | 初期状態、感染・回復、介入、期間、損失の定義 | 状態経路、累積損失、介入シナリオ |
| 待ち行列・容量 | 到着率、サービス率、時間単位 | 稼働率、滞在時間、待ち時間、系内人数、待ち人数 |
| 意思決定権配分 | 主体の利得、努力費用、権限配分 | 均衡努力、成功確率、各主体の利得 |

既存のcatalogから生成した契約に実行bindingを付け、`select_method`が必要入力と実行仕様を返す。計算本体は既存の`research_numerics.py`と`equity.py`を使う。理論参照の契約は式、成立条件、前提知識をそのまま利用する。

実装先：[knowledge catalog](../../skills/econ-knowledge/references/catalog.json)、[numerical runner](../../skills/econ-data/scripts/research_numerics.py)、[equity runner](../../skills/econ-data/scripts/equity.py)、[macro runner](../../skills/econ-data/scripts/research_macro_extended.py)、[dynamic runner](../../skills/econ-data/scripts/research_dynamic.py)。

## 問題定式化、識別、理論とWriting

| 比較元と実読範囲 | 比較から採用した手順 | ERSの改修箇所 |
| --- | --- | --- |
| [Auto-Empirical-Research-Skills](https://github.com/brycewang-stanford/Auto-Empirical-Research-Skills/blob/bfa0a6e5a843babbf45a1ef1663fd5dc4f07c0ba/skills/00.1-Full-empirical-analysis-skill_Python/SKILL.md)：実行方針、Typical agent execution、Step 8.5 | 保存数値・図表・出典から原稿を組み立てる。ERSでは既存registryの結果IDと統計キーをそのまま使う。 | `research_evidence.py`は先付けのsupported判定を外し、実際の出典・数値・採用仕様を`bound`として保存する。 |
| [AER-Skills identification](https://github.com/brycewang-stanford/AER-Skills/blob/85eae99fe5935c79c209f597a56c88899082a090/skills/aer-identification/SKILL.md)、[paper body](https://github.com/brycewang-stanford/AER-Skills/blob/85eae99fe5935c79c209f597a56c88899082a090/skills/aer-paper-body/SKILL.md) | estimand→識別式→仮定→推定と推論→経済的な大きさの順で論証する。 | `paper-workflow.md`と`result-artifacts.md`に、母集団、単位、比較、実際の標本・重み・covariance・参照分布を受け渡す操作を実装した。 |
| [mimaowang/econ-writing-skills](https://github.com/mimaowang/econ-writing-skills/blob/0229db42e1eb068cb3ef7e74de601abf426dcbb4/skills/write-economics-introduction/SKILL.md) | 完成本文からquestion・answer・credibilityを取り出し、その研究と近い文献に貢献を対応させる。 | 既存`composition_context`を使い、保存された主張と結果から章節を構成する。通常段落は執筆後、一度の本文統合へ進む。 |
| [h-lu/theoretical-economics-paper-writing](https://github.com/h-lu/theoretical-economics-paper-writing/blob/261332bd79dd0ee93287062b74e6c0b7021b3746/SKILL.md)、[research loop](https://github.com/h-lu/theoretical-economics-paper-writing/blob/261332bd79dd0ee93287062b74e6c0b7021b3746/references/research-loop.md) | 定義域・量化順序を固定し、決定的な補題、全仮説を満たす反例、成立条件、証明、均衡・厚生への含意を解く。 | `designs.md`、econ-review、Writingの既存ownerへ接続した。反例が破る命題と変更権限を特定し、採用した命題・証明を本文へ反映する。 |

通常の論証reviewは、該当命題、誤りを生む関係、具体的修正を返す。固定check網羅、スコア関数、段落ごとの合格連鎖を撤去した。明示選択された独立認証は実worker・出典・返却記録を使う既存経路で実行する。binderは対象を一度読み、同じ解析済み結果を使う。全文coverage走査は明示選択時に行う。

実装先：[designs](../../skills/econ-design/references/designs.md)、[Writing](../../skills/econ-writing/SKILL.md)、[paper workflow](../../skills/econ-writing/references/paper-workflow.md)、[argument](../../harness/argument.py)、[paragraph](../../harness/paragraph.py)、[binder](../../harness/research_evidence.py)、[review](../../skills/econ-review/SKILL.md)。

## 結果の再利用、表図と研究開発

| 比較元と実読箇所 | 計算・成果物の依存 | ERSで採用・維持した経路 |
| --- | --- | --- |
| [econ-project-templates analysis](https://github.com/OpenSourceEconomics/econ-project-templates/blob/8dcd9d0cb9fc928c6ddd87b72ce1b7901acd2831/src/template_project/analysis/task_analysis_template.py)、[final](https://github.com/OpenSourceEconomics/econ-project-templates/blob/8dcd9d0cb9fc928c6ddd87b72ce1b7901acd2831/src/template_project/final/task_final_template.py)、[documents](https://github.com/OpenSourceEconomics/econ-project-templates/blob/8dcd9d0cb9fc928c6ddd87b72ce1b7901acd2831/documents/task_documents.py) | 保存fit→予測→表図→論文を明示した依存で更新する。 | 既存研究DAGと保存結果の共通engineを維持した。模擬研究workspace・gallery・case generatorとその起動元を撤去した。文言や図の表示変更は保存結果を再利用する。 |
| [modelsummary `get_estimates`](https://github.com/vincentarelbundock/modelsummary/blob/847bece31af20d6f4b1bccd44321aec94e7b6da4/R/get_estimates.R)、[modelsummary_list](https://github.com/vincentarelbundock/modelsummary/blob/847bece31af20d6f4b1bccd44321aec94e7b6da4/R/modelsummary_list.R)、[did methods](https://github.com/vincentarelbundock/modelsummary/blob/847bece31af20d6f4b1bccd44321aec94e7b6da4/R/methods_did.R) | 保存tidy/glance、term、group、公式推論を使って表を作る。 | 共通statistics/displayと既存の表・図・本文生成を維持した。新規DoubleML・モデル結果を同じ形式へ接続した。 |
| 追加比較：[EconAgentSkills clustered inference](https://github.com/JonasWeinert/EconAgentSkills/blob/c1b8b1ef7ab59e6858fe3599a39d4732e5a76142/_skills/analysis/python-panel-data/examples/clustered_inference.py)、[event study](https://github.com/JonasWeinert/EconAgentSkills/blob/c1b8b1ef7ab59e6858fe3599a39d4732e5a76142/_skills/analysis/python-panel-data/examples/event_study_sun_abraham.py)、[tables](https://github.com/JonasWeinert/EconAgentSkills/blob/c1b8b1ef7ab59e6858fe3599a39d4732e5a76142/_skills/writing/latex-tables/examples/make_tables_modelsummary.R)、[sample construction](https://github.com/JonasWeinert/EconAgentSkills/blob/c1b8b1ef7ab59e6858fe3599a39d4732e5a76142/_skills/data/working-with-data/examples/sample_construction_logging.py) | 実証の標本構築、推論、表出力を個別の専門skillへ接続する。 | 既存の標本ID、公式DID集計、保存推論を使う。経験的cluster数基準、event係数の単純平均、表出力時の再fitは採用対象から外した。 |

ハーネスでは正本のregistryと既存export producerを所有元とし、entries、skill内bundle、`.agents`を生成する。要件の再読込、生成物の反復全走査、テスト専用CI・Makefile起動、テストログからの成功率採点、ホスト設定を変えないcapability評価を撤去した。実行・権限・保存・配布に必要な境界処理と、実際の結果を読む通常経路を維持した。

追加比較として[pytaskの実行判定](https://github.com/pytask-dev/pytask/blob/938532dd58d3fa0630b823edc1fb50f769d9208a/src/_pytask/execute.py)と[skip処理](https://github.com/pytask-dev/pytask/blob/938532dd58d3fa0630b823edc1fb50f769d9208a/src/_pytask/skipping.py)を読んだ。各タスクの入力・生成物・sourceの変更を判定し、保存状態が一致する計算を再利用する。ERSの`harness/research.py`も消費結果の版、実行仕様、runtimeと完了状態から既存計算を再利用する。この所有箇所を維持し、`codex_hooks.py`に残っていた復元判定用の状態hash保存・関連タスク走査・到達不能なPostToolUse分岐を削除した。SessionStartは元の依頼・適用規則・権限を復元し、通常readの反復callbackは追加本文を返さない。実依頼を入力したresume・compact経路で復元とcompaction状態の更新を確認した。

## 追加専門手法の採否

StatsPAIの[同一固定版](https://github.com/brycewang-stanford/StatsPAI/tree/0c04f715d7463ef2d7048dcda9e656d992c2c59a)で、以下の計算本体を読んだ。

| 実読ファイル | 計算対象と採否を決める条件 | 今回の実装判断 |
| --- | --- | --- |
| `src/statspai/bunching/bunching.py` | notchとkinkの行動反応・反実仮想密度・弾性の写像が必要。実装のnotch弾性は正規化した超過質量を使う。 | 対象税制・弾性の採用定義を要求する既存designに残した。汎用runnerの追加対象から外した。 |
| `src/statspai/survival/models.py` | risk set、censoring、ties、start/stopが推定対象を決める。 | 期間データ・打切り定義を伴う研究仕様から公式survival実装を選ぶ。現在の契約群への一括追加対象から外した。 |
| `src/statspai/decomposition/oaxaca.py` | 参照係数、群のgap、共変量平均の扱いが分解と分散を決める。 | 既存のCDF・quantile分布機能を維持した。Oaxacaはその採用分解を持つ課題で選択する。 |
| `src/statspai/policy_learning/targeting.py` | CATE順序と人数予算による割当てを生成する。政策価値の推論には評価用標本とscoreが必要になる。 | 既存policy tree、GRF、独立評価標本による政策評価を使う。 |

## 実行した結果

DoubleMLの公開401(k)データ9915世帯を、固定標本・foldで公式推定器へ渡した。IRM ATE、IRM ATTE、PLIV、IIVMの係数・SE・p値・95%区間は、別に構築した公式classの出力と一致した。最大差は0だった。保存したIRM ATE 6633.56453594259米ドル、SE 1143.2181645928124米ドルを、再推定せず既存registry・selection・本文render・binderへ渡した。本文は処置`e401`、結果`net_tfa`、1991年調査・1990年参照変数、採用された交換可能性とcross-fittingを説明する。binderの実返却は`bound`だった。

五つのモデルはselectorが返した仕様を既存CLIへ渡し、数値と共通JSON保存を確認した。Binary Logitの解析Jacobian、Cournotの線形需要均衡、SIRの感染流入ゼロの解析経路、M/M/1の時間・人数関係、意思決定権配分の均衡式と比較した。HARKの完全予見二期間モデルは公式`solve()`から政策・価値・scenario・simulationを保存し、CRRA解析式との最大差は7.77×10⁻¹⁶だった。

Writingの段落host経路は実装と保存形式を更新した。実行記録は、公開データから得た推定結果の登録・選択・本文render・binderについて保存した。数値比較は各計算の正しさと接続を、binderは指定箇所の出典・数値・仕様の対応を確認する。

401(k)の保存結果を追跡すると、表示用の`inference: {type: official}`が実行済みの推論全体を上書きしていた。`research_artifacts.py`の登録・表示選択で、同じ区間族・水準の公式推論を保持するよう修正した。再登録した9915世帯の結果は、registry・selection・Writingの結果定義・表示定義へnormal参照、公式score分散、点別95%区間、反復間集約を渡した。数値・表示行・母集団・標本・米ドル単位・期間は元の保存結果と一致し、既存2段落原稿のbinderは`bound`を返した。推定を実行せず、対応する保存済み端点を持たない水準・区間族への表示変更を拒否した。

PyBLP 1.3.0の[Nevo製品データ](https://github.com/jeffgortmaker/pyblp/blob/16536807004b16c24fb40b931531b45b33884e00/pyblp/data/nevo_products.csv)2256観測・94市場でfit保存と再利用を実行した。線形効用は`1 + prices + sugar + mushy`、random coefficientは定数項に固定標準偏差0.2、Monte Carlo積分は15点・seed 726、GMMは一段階とした。企業1と2の合併を、回収した限界費用を保持して計算した。再利用中の`Problem.solve`呼出しは0回で、価格・シェア・利潤・消費者余剰は保存fitの公式result methodsによる別計算と最大1.39×10⁻¹⁶の差だった。利潤勾配の最大絶対値は8.96×10⁻¹⁴で、元の推定結果、パラメータ、積分typeの基準余剰・重みを保持した。

GRFの接続は[AER CASchoolsの公開観測](https://github.com/vincentarelbundock/Rdatasets/blob/cc03c29690889dbe83089f5206e2422db8c3f71f/csv/AER/CASchools.csv)420学校区・45 countyで確認した。処置を生徒数／教員数が20未満の239地区と定義し、生徒数重み、county cluster、treated集計、seed 72608、400 trees、点別90%区間を指定した。R 4.5.3・GRF 2.6.1の公式関数を別に構築した計算と、既存CLIのselect→runが返した推定値・SE・p値・区間端点の最大差は0だった。対象行、正規化重み、cluster数、保存fitと表示定義も一致した。
