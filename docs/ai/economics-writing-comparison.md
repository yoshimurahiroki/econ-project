# 経済学Writing・研究実装21件の比較とERSへの反映

比較日：2026年11月7日。

指定された19件と既存の追加比較2件を、ERSの論証構築、モデル・推定結果の受渡し、図表生成、改稿・翻訳・査読対応と照合した。2026年11月7日に21件すべての公開リポジトリへ `git ls-remote https://github.com/<owner>/<repository>.git HEAD` を実行し、全件で終了コード0を得た。取得したHEADは以下の固定SHAとすべて一致し、公開原典の変更は0件だった。指定19件にはjuliaErrorとshuangchenfinanceを含み、追加2件はzbsayginとviplee110である。各項目の固定コミット、実読箇所、比較判断を再利用した。

## 今回完成したWritingの接続

公開実装との実質差分は、保存された数量・根拠・修正箇所を既存の執筆処理へ渡し、経済的な答えを持つ原稿と回答文を完成させる接続にある。以下は0.58.0の既存機能を起点に選んだ改修である。原典の本文位置と固定SHAは各比較項目に記載した。

| 解決する作業と利用条件 | 公開実装の根拠 | ERSの既存機能と改修箇所 | 今回の状態 |
| --- | --- | --- | --- |
| 保存結果から最初の章節・段落を設計する。入力は採用した研究質問、結果ID、定義、表図、出典。 | [juliaError](#20-juliaerrorecon-topjournal-writing-skill)の結果から構成への接続と論証・執筆課題、[JonasWeinert](#3-jonasweinerteconagentskills)のResults・Reproducibility Discipline。 | [paragraph.py](../../harness/paragraph.py)の `generate_blueprint`・`generate_specifications` は完成段落の `composition_context` を再利用する。保存結果を読む入口から同じ執筆入力へ、選択した数量、定義、図表、出典を渡す。論証の依存関係は [argument.py](../../harness/argument.py) が担う。 | `b8bab737`に保存。既存design入口から執筆・改稿・保存・完成段落の再利用まで実行し、担当3テストが成功した。 |
| 数量から経済的な主張を組み立てる。入力は結果の主体・母集団・期間・単位・比較基準・識別条件と、採用したモデルの定義。 | [changxiangxu](#10-changxiangxuecon-research-skills)のResults_Manager Task A・E、[did](#16-bcallaway11did)の集計対象とイベント窓、[modelsummary](#18-vincentarelbundockmodelsummary)の保存された項・群・推論。 | [paper-workflow](../../skills/econ-writing/references/paper-workflow.md#establish-the-argument-from-the-research)と [paragraph-workflow](../../skills/econ-writing/references/paragraph-workflow.md)で、保存数量が示す行動・配分・均衡・厚生の関係を段落の主張へ結ぶ。[result-artifacts](../../skills/econ-writing/references/result-artifacts.md)から同じ結果定義を渡す。 | `4806b74d`にWriting手順を保存。DIDの時間的応答、成長モデルの資源配分、所有統合の価格調整と厚生を完成原稿へ反映した。 |
| Introductionと結論を、本文が支持する答えと先行研究の実際の知見から構成する。 | [mimaowang](#2-mimaowangecon-writing-skills)のIntroductionとMixed Papers、[juliaError](#20-juliaerrorecon-topjournal-writing-skill)の中心結果と本文位置の対応。 | [paper-workflow](../../skills/econ-writing/references/paper-workflow.md#introduction)で引用先の知見と本研究の支持結果を結ぶ。`composition_context` にある中心質問・答え・貢献を、Title・Abstract・Introduction・Conclusionで共有する。 | 研究7類型の推論を既存手順へ統合。3原稿のTitle・Abstract・Introduction・Results・Discussion・Conclusionを同じ結果から構成し、主要数値と対象・期間・単位を照合した。 |
| 修正済み本文から査読回答を完成させる。入力は解決済みの指摘、現行assessment、旧本文、実際の修正箇所、根拠と計算結果。 | [hanlulongの査読実装](#6-hanlulongecon-paper-review-skill)のrevision-cycle・review-actions-handoff、[shuangchenfinance](#21-shuangchenfinanceresearch-skills)のREFEREE RESPONSE・REWRITE。 | [research_evidence.py](../../harness/research_evidence.py)の `response_draft` が既存のWriting hostへ `econ-writing:compose`・`revise`・`translate` を渡す。各findingに採用理由と修正本文・位置を付し、返った完成回答を出力する。 | `45419eb8`に保存し、既存4テストが成功。成長モデルの実際の修正本文から完成回答を書き、既存review CLIの `--response-output` で保存した。 |

完成した[因果実証原稿](../../examples/research-workspace/materials/writing/causal-paper.md)、[成長モデル原稿](../../examples/research-workspace/materials/writing/growth-paper.md)、[構造推定原稿](../../examples/research-workspace/materials/writing/structural-paper.md)は、既存の保存結果を用いた独自の計算例である。[日英改稿・翻訳と読者別説明](../../examples/research-workspace/materials/writing/revision-examples.md)、[査読回答](../../examples/research-workspace/materials/writing/referee-response.md)、[実行結果](../../examples/research-workspace/materials/writing/execution.json)も保存した。文章はnative会話で構成し、数量・表図・査読対応の受渡しを既存コードで実行した。

## 0.58.0で保存済みの実行接続

| 完了した接続 | 登録済み入口と入力 | 生成される内容 |
| --- | --- | --- |
| 完成本文から章節を設計 | `paragraph.py design --reuse-state … --reuse-paragraph …` に既存の段落IDと現在の執筆依頼を渡す | 完成した主張、根拠、数量、採用図表、前提依存を `writing:architect` と `writing:specify` へ渡す。Title・Abstract・Introduction・Conclusionは同じ中心的な答えから構成する。 |
| 数量と定義を本文へ渡す | `research.py` の既存 `render` に `statistics` と `definitions` を指定する | 保存された値・単位と、比較群・期間・数式などの文字列を同じ節へ挿入する。節の編集は既存DAGの対応する出力を更新する。 |
| 論文・スライドへ同じ定義を渡す | `research_evidence.py artifacts materialize` の既存仕様に `definitions` を指定する | 選択した結果・図表の定義をarticle/slidesへ挿入し、数値・単位の実際の文字位置を既存binderへ渡す。 |
| 査読回答の材料をそろえる | `research_evidence.py review` に現行assessmentと `review.response_draft` を渡す | 当初の指摘、旧本文、修正済み本文、根拠、選択計算と採用理由を同じ返却結果にまとめる。完成回答への執筆接続は上表に記載した。 |

各経路は既存の状態、結果ID、図表、公式計算結果を再利用する。論文本文の出力例には、保存済みDiD結果と20期の成長モデル結果を使用した。主図の選択例では、成長モデルの配分経路・厚生を主本文へ、パラメータと方程式の診断を付録へ接続した。読者、言語、研究類型、節の機能は既存7モードの共通処理と現在の執筆依頼が定める。

## 反映した変更と既存の所有箇所

| 対象 | 保持した既存機能 | 今回反映した内容 |
| --- | --- | --- |
| 論文全体・章節・段落 | [paper-workflow](../../skills/econ-writing/references/paper-workflow.md)の章節別手順、[paragraph-workflow](../../skills/econ-writing/references/paragraph-workflow.md)、[argument.py](../../harness/argument.py)・[paragraph.py](../../harness/paragraph.py)の依存管理 | 研究類型ごとの貢献、混合研究の推論、選択から配分・厚生への接続、圧縮後の主張と本文の対応を具体化した。 |
| 読者・言語・著者の表現 | [econ-writing](../../skills/econ-writing/SKILL.md)の7モード、[PROSE](../../runtime/PROSE.md)の意味判断、[既存プロファイル](../../profiles/default-micro/PROFILE.md) | 大学院コアの知識を前提とする説明と、明示された非専門家向けの説明への切替をPROSEに集約した。既存例に、元の経済的対象・数式・引用を保つ日英改稿と読者別説明を追加した。 |
| モデル・手法・保存結果 | [モデル契約](../../skills/econ-knowledge/references/model-contracts.json)、[研究設計](../../skills/econ-design/references/designs.md)、[公式実装の選択](../../skills/econ-data/references/implementation.md)、[結果ライフサイクル](../../skills/econ-data/references/reproducible-workflow.md) | 式と名前付き数量、記号と役割・添字・単位を対応づけた。公式ライブラリの政策添字、正規化価値、集計ATT、反実仮想の戻り値を、意味を保って保存する手順を追加した。 |
| 表・理論図・本文 | [research_artifacts.py](../../harness/research_artifacts.py)、[result-artifacts](../../skills/econ-writing/references/result-artifacts.md)、既存の表・図・論文生成経路 | 選択した表示項目に絞る処理、二つの境界による領域表示、保存順序による経路表示、均衡点のラベルを実装した。保存済みモデル定義を選択結果とともに文章へ渡す。 |
| 改稿・翻訳・査読 | [econ-review](../../skills/econ-review/SKILL.md)、[research_evidence.py](../../harness/research_evidence.py)の主張・出典・数値対応 | 元文と改稿文の主体、数量、群、期間、条件、引用を照合する手順を追加した。査読コメントの前提を本文・式・図表へ戻し、実際の修正箇所から回答を書く。 |

研究課題から必要な知識・モデル契約を選び、econ-designが定めた経済的対象をecon-dataの公式実装へ渡す。保存結果には数式、パラメータの役割、正規化、均衡選択、厚生の定義、期間が残る。econ-writingは選択した結果IDと同じ定義を使って、図表、Model、Results、Discussionを構成する。文章・表示の変更はその保存結果を再利用する。

## Writing・改稿・査読の専門実装

### 1. hanlulong/econ-writing-skill

固定版：`f2bf7a22c5e3b37921a5e6c73bd1fb380a5e00e8`。実読：[README](https://github.com/hanlulong/econ-writing-skill/blob/f2bf7a22c5e3b37921a5e6c73bd1fb380a5e00e8/README.md)、[skills/econ-write/SKILL.md](https://github.com/hanlulong/econ-writing-skill/blob/f2bf7a22c5e3b37921a5e6c73bd1fb380a5e00e8/skills/econ-write/SKILL.md)のCore Principles、Abstract、Introduction、Model、Propositions and Proofs、Assumptions、Equations in Text、Testable Predictions。

**利用条件と実装。** 論文の導入、理論モデル、命題・証明の執筆に用いる。Modelの手順は経済環境、原始的要素、均衡、命題を並べ、直観を誘因・制約に結び付ける。Introductionは段落群を指定し、Abstractは150語の上限と非専門家向けの説明を指定する。

**ERSとの対応と判断。** [章節ガイド](../../skills/econ-writing/references/paper-workflow.md)は、研究の推論と投稿先の規定から構成・長さを選ぶ既存手順を保持する。今回、命題を決める制約、利得差、最適反応、市場清算を説明する操作をTheory節へ加えた。[PROSE](../../runtime/PROSE.md#select-the-profile)で読者の切替条件を一元化し、理論の説明を[保存済みモデル図](../../skills/econ-writing/references/result-artifacts.md#draw-the-models-economic-relationship)へ接続した。

### 2. mimaowang/econ-writing-skills

固定版：`0229db42e1eb068cb3ef7e74de601abf426dcbb4`。実読：[README](https://github.com/mimaowang/econ-writing-skills/blob/0229db42e1eb068cb3ef7e74de601abf426dcbb4/README.md)、[IntroductionのSKILL.md](https://github.com/mimaowang/econ-writing-skills/blob/0229db42e1eb068cb3ef7e74de601abf426dcbb4/skills/write-economics-introduction/SKILL.md)、[paper-type-patterns.md](https://github.com/mimaowang/econ-writing-skills/blob/0229db42e1eb068cb3ef7e74de601abf426dcbb4/skills/write-economics-introduction/references/paper-type-patterns.md)。

**利用条件と実装。** 本文を持つ論文のIntroduction作成・再構成に用いる。現在の研究の成果は本文、先行研究の成果は引用先に対応づけ、中心となる主張の種類から情報量と順序を選ぶ。Mixed Papersでは、記述、因果推定、構造推定、反実仮想、理論の結果を結ぶ関係を説明する。

**ERSとの対応と判断。** 主張と根拠の対応は既存の[evidence binder](../../harness/research_evidence.py)、論証依存は[argument.py](../../harness/argument.py)が担う。今回、[paper-workflow](../../skills/econ-writing/references/paper-workflow.md#establish-the-argument-from-the-research)に研究類型ごとの知見の増分と、推定された反応、パラメータ、均衡、厚生計算をつなぐ手順を追加した。段落数と長さは、その研究の説明に必要な関係から決める。

### 3. JonasWeinert/EconAgentSkills

固定版：`c1b8b1ef7ab59e6858fe3599a39d4732e5a76142`。実読：[README](https://github.com/JonasWeinert/EconAgentSkills/blob/c1b8b1ef7ab59e6858fe3599a39d4732e5a76142/README.md)、[_skills/writing/academic-paper-writer/SKILL.md](https://github.com/JonasWeinert/EconAgentSkills/blob/c1b8b1ef7ab59e6858fe3599a39d4732e5a76142/_skills/writing/academic-paper-writer/SKILL.md)、[reference.md](https://github.com/JonasWeinert/EconAgentSkills/blob/c1b8b1ef7ab59e6858fe3599a39d4732e5a76142/_skills/writing/academic-paper-writer/reference.md)。

**利用条件と実装。** 実証論文の識別説明、結果記述、図表、査読回答に用いる。Cross-Skill Routingで表・図・記号の担当へ接続し、ResultsとReproducibility Disciplineは生成した数値マクロを本文で利用する。参照本文には5段落のIntroduction、5文のAbstract、識別・結果・査読回答の構成例がある。

**ERSとの対応と判断。** 既存の[結果ライフサイクル](../../skills/econ-data/references/reproducible-workflow.md#carry-analysis-results-into-tables-figures-and-prose)は、数量キー、単位、推論、生成元を表・図・本文に共有する。[研究DAG](../../harness/research.py)による更新も保持した。今回のモデル定義の受渡しにより、同じ結果IDから式、記号、パラメータの役割、正規化、均衡選択、厚生の定義を読める。識別の選択はecon-design、計算はecon-dataが担当する。

### 4. AlessandroCaforio/Academic-Writing

固定版：`4de944ca1605d86e301c6fdbc6cdce485f5a2227`。実読：[README](https://github.com/AlessandroCaforio/Academic-Writing/blob/4de944ca1605d86e301c6fdbc6cdce485f5a2227/README.md)、[.claude/skills/write-introduction/SKILL.md](https://github.com/AlessandroCaforio/Academic-Writing/blob/4de944ca1605d86e301c6fdbc6cdce485f5a2227/.claude/skills/write-introduction/SKILL.md)。

**利用条件と実装。** 特定の修士論文のIntroduction作成・改稿に用いる。Research段階で既存章と文献根拠を読み、Build Argumentative Structureで段落構成を作り、Style Matchingで既存章の文章に合わせる。章構成、語り口、分量、参照先はその論文の仕様として指定されている。

**ERSとの対応と判断。** 既存の[paragraph-workflow](../../skills/econ-writing/references/paragraph-workflow.md)は、論文全体、段落、節、全体統合を同じ執筆作業で扱う。今回、各段落で追加する観測・定義・導出と、それを次の主張が使う関係を明示した。[プロファイル](../../profiles/default-micro/PROFILE.md)による著者の語彙・記号・有効な表現の保持と、依頼に応じた既存の段落状態を継続する。

### 5. Silas1929/econ-writing

固定版：`ba636f282fc80b12dbed623752b76c1513cd73ea`。実読：[README](https://github.com/Silas1929/econ-writing/blob/ba636f282fc80b12dbed623752b76c1513cd73ea/README.md)、[SKILL.md](https://github.com/Silas1929/econ-writing/blob/ba636f282fc80b12dbed623752b76c1513cd73ea/SKILL.md)、[references/paragraph-composition.md](https://github.com/Silas1929/econ-writing/blob/ba636f282fc80b12dbed623752b76c1513cd73ea/references/paragraph-composition.md)。

**利用条件と実装。** 与えられた文章の改稿、Introduction作成、段落の役割の整理に用いる。Core PrinciplesとPolish Human-Written Textは著者の専門語彙を保ち、paragraph-compositionは段落を節の目的に結び付け、本文で成立する発見を早い位置に置く。

**ERSとの対応と判断。** [econ-writingのRevise](../../skills/econ-writing/SKILL.md#revise)、[Introductionの手順](../../skills/econ-writing/references/paper-workflow.md#introduction)、既存プロファイルを保持した。[英語短例](../../profiles/default-micro/short-examples-en.md)と[日本語短例](../../profiles/default-micro/short-examples-ja.md)に、著者の用語、集計式、引用の係り先が改稿後も対応する独自例を追加した。文章は制度、定義、結果の関係から構成する。

### 6. hanlulong/econ-paper-review-skill

固定版：`de9e5491c7214ba3fde5e5c7e858ea0361371410`。実読：[README](https://github.com/hanlulong/econ-paper-review-skill/blob/de9e5491c7214ba3fde5e5c7e858ea0361371410/README.md)、[econ-review/SKILL.md](https://github.com/hanlulong/econ-paper-review-skill/blob/de9e5491c7214ba3fde5e5c7e858ea0361371410/econ-review/SKILL.md)、[revision-cycle.md](https://github.com/hanlulong/econ-paper-review-skill/blob/de9e5491c7214ba3fde5e5c7e858ea0361371410/econ-review/references/revision-cycle.md)、[review-actions-handoff.md](https://github.com/hanlulong/econ-paper-review-skill/blob/de9e5491c7214ba3fde5e5c7e858ea0361371410/econ-review/references/review-actions-handoff.md)。

**利用条件と実装。** 査読コメント、実装回答、改稿済み原稿の対応を調べる作業に用いる。Reconstruct before critiqueは指摘の前提を原稿へ戻し、revision-cycleのImplementation-agent handoffとNext-round intakeは、報告された変更を実際の箇所と前回の指摘に対応づける。

**ERSとの対応と判断。** [econ-review](../../skills/econ-review/SKILL.md#locate-and-repair-the-cause)に、コメントの質問、事実上の前提、求める変更を回復し、本文・付録・式・図表で判断する手順を追加した。回答は実際に読んだ修正箇所から書く。既存の[reviewとresponse_afterの対応](../../skills/econ-writing/references/result-artifacts.md#claims-coverage-and-requested-re-review)、finding ID、論証依存、COREの統合レビューを維持する。

### 7. h-lu/theoretical-economics-paper-writing

固定版：`261332bd79dd0ee93287062b74e6c0b7021b3746`。実読：[README](https://github.com/h-lu/theoretical-economics-paper-writing/blob/261332bd79dd0ee93287062b74e6c0b7021b3746/README.md)、[SKILL.md](https://github.com/h-lu/theoretical-economics-paper-writing/blob/261332bd79dd0ee93287062b74e6c0b7021b3746/SKILL.md)、[references/published-theory-practice.md](https://github.com/h-lu/theoretical-economics-paper-writing/blob/261332bd79dd0ee93287062b74e6c0b7021b3746/references/published-theory-practice.md)。

**利用条件と実装。** 理論の改稿、命題、比較静学、貢献の説明に用いる。Present the model、State results、Revise for an economist-readerは、タイミング、情報、均衡選択、量化、内生反応を形式的主張に対応づける。published-theory-practiceは、具体的な編集判断に必要な前後の文章を読む手順を持つ。

**ERSとの対応と判断。** [Theory, model and proof](../../skills/econ-writing/references/paper-workflow.md#theory-model-and-proof)と[econ-review](../../skills/econ-review/SKILL.md)で、説明文を数式の定義域、量化、不等号、均衡反応に照合する。独自のCournot例では、両社共通の限界費用の変更について双方の最適反応を微分し、定義・証明・図の説明・査読回答が同じ比較静学を表すようにした。

### 8. linkingoscar/econ-management-paper-polish

固定版：`e163b67b2feea7411b0f1763c06cfa2118878a00`。実読：[README](https://github.com/linkingoscar/econ-management-paper-polish/blob/e163b67b2feea7411b0f1763c06cfa2118878a00/README.md)、[SKILL.md](https://github.com/linkingoscar/econ-management-paper-polish/blob/e163b67b2feea7411b0f1763c06cfa2118878a00/SKILL.md)、[revision-matrix.md](https://github.com/linkingoscar/econ-management-paper-polish/blob/e163b67b2feea7411b0f1763c06cfa2118878a00/references/revision-matrix.md)、[v3-writing-contract.md](https://github.com/linkingoscar/econ-management-paper-polish/blob/e163b67b2feea7411b0f1763c06cfa2118878a00/references/v3-writing-contract.md)。

**利用条件と実装。** 同じ言語での改稿、翻訳、査読回答に用いる。Start with the writing taskとPreserve the researchは数量、ラベル、著者の用語を保つ。v3-writing-contractは翻訳時の表現変更を扱い、revision-matrixは実際の操作、根拠、原稿箇所を対応づける。

**ERSとの対応と判断。** [Revise・Translate](../../skills/econ-writing/SKILL.md#revise)とPROSEの意味判断を維持し、[econ-review](../../skills/econ-review/SKILL.md#locate-and-repair-the-cause)で、同じ数が指す主体・群・期間・比較・出典を原文と照合する手順を追加した。日英の独自例は、1.3 MWの対比、同じ時刻で集計する式、架空の実施規則への引用を一緒に保持する。

### 9. Thlookingatyou/AI-Agent-Economics-Paper-Writing-Workflow

固定版：`a96c14a3d77b218424671d65aca0e8df4a236b1f`。実読：[README](https://github.com/Thlookingatyou/AI-Agent-Economics-Paper-Writing-Workflow/blob/a96c14a3d77b218424671d65aca0e8df4a236b1f/README.md)、[manuscript-review/SKILL.md](https://github.com/Thlookingatyou/AI-Agent-Economics-Paper-Writing-Workflow/blob/a96c14a3d77b218424671d65aca0e8df4a236b1f/.agents/skills/manuscript-review/SKILL.md)、[docs/manuscript-review.md](https://github.com/Thlookingatyou/AI-Agent-Economics-Paper-Writing-Workflow/blob/a96c14a3d77b218424671d65aca0e8df4a236b1f/docs/manuscript-review.md)、[edits.md](https://github.com/Thlookingatyou/AI-Agent-Economics-Paper-Writing-Workflow/blob/a96c14a3d77b218424671d65aca0e8df4a236b1f/templates/paper/review/edits.md)、[result-memo.md](https://github.com/Thlookingatyou/AI-Agent-Economics-Paper-Writing-Workflow/blob/a96c14a3d77b218424671d65aca0e8df4a236b1f/templates/paper/review/result-memo.md)。

**利用条件と実装。** 文法、用語、内容、構造の修正と、その統合に用いる。manuscript-reviewは正本の原稿と編集モードを定め、主張を実際の出典・実行・推論へ対応づける。edits.mdは特定箇所の原文と置換文を並べる。

**ERSとの対応と判断。** [Preserve adopted content](../../skills/econ-writing/SKILL.md#preserve-adopted-content)、[econ-reviewの版比較](../../skills/econ-review/SKILL.md#compare-versions-or-decisions-when-requested)、既存の証拠・段落依存を維持した。今回の既存短例には入力文、改稿文、訳文を置き、与えられた文章からどの経済的関係を保存したか読めるようにした。権限と版は既存のタスク・結果記録で扱う。

## 知識・モデル・手法と保存結果の専門実装

### 10. changxiangxu/econ-research-skills

固定版：`834f70c2d2a77942dc60a8f00e4b21c1ff861e69`。実読：[README](https://github.com/changxiangxu/econ-research-skills/blob/834f70c2d2a77942dc60a8f00e4b21c1ff861e69/README.md)、[Results_Manager/SKILL.md](https://github.com/changxiangxu/econ-research-skills/blob/834f70c2d2a77942dc60a8f00e4b21c1ff861e69/skills/Results_Manager/SKILL.md)のTask A・E、[Theoretical_Framework/SKILL.md](https://github.com/changxiangxu/econ-research-skills/blob/834f70c2d2a77942dc60a8f00e4b21c1ff861e69/skills/Theoretical_Framework/SKILL.md)のTask A・C、[02_callaway_santanna.R](https://github.com/changxiangxu/econ-research-skills/blob/834f70c2d2a77942dc60a8f00e4b21c1ff861e69/code_library/did_r/02_callaway_santanna.R)。

**利用条件と実装。** 回帰結果の解釈、理論と検証可能な仮説の接続、DiDの集計に用いる。Results_Managerは係数、SE、N、固定効果を経済量と表・列に対応づける。Theoretical_Frameworkは主体と機序から導出・仮定を組み立てる。R例は`att_gt`と、dynamic・simple・group・calendarの`aggte`を実行する。

**ERSとの対応と判断。** [designs](../../skills/econ-design/references/designs.md)、[implementation](../../skills/econ-data/references/implementation.md)、[結果ライフサイクル](../../skills/econ-data/references/reproducible-workflow.md)の責任分担と、入力・仕様・結果ID・公式推論の対応を保持した。今回、文章へ渡す数学的対象を、動学、ゲーム、一般均衡、厚生の出力まで具体化した。

### 11. zbsaygin/econ-skills

固定版：`d2daa952269eca9874f36ad8288e7f3495aef019`。実読：[README](https://github.com/zbsaygin/econ-skills/blob/d2daa952269eca9874f36ad8288e7f3495aef019/README.md)、[notation-clean/references/notation-rules.md](https://github.com/zbsaygin/econ-skills/blob/d2daa952269eca9874f36ad8288e7f3495aef019/notation-clean/references/notation-rules.md)の第3–9節。

**利用条件と実装。** 本文、証明、付録の記号を整える作業に用いる。合成記号の経済的意味、装飾、添字、関数、個別量と集計量を整理し、記号の使用回数や文字種の規則も持つ。

**ERSとの対応と判断。** [paper-workflow](../../skills/econ-writing/references/paper-workflow.md#design-the-papers-argument)の採用済み記号と、保存された`notation`を継続する。[designsの受渡し](../../skills/econ-design/references/designs.md#deliver-the-selected-result)に、記号の経済的役割、添字、単位、正規化を結び付ける手順を追加した。個別量から集計量への式は、その研究の採用定義で決まる。

### 12. econ-ark/HARK

固定版：`4c285e863cd1a60eb2a9c4ab335c7f86ea5aa767`。実読：[READMEのUsage](https://github.com/econ-ark/HARK/blob/4c285e863cd1a60eb2a9c4ab335c7f86ea5aa767/README.md)、[HARK/ConsumptionSaving/ConsIndShockModel.py](https://github.com/econ-ark/HARK/blob/4c285e863cd1a60eb2a9c4ab335c7f86ea5aa767/HARK/ConsumptionSaving/ConsIndShockModel.py)の`ConsumerSolution`と`solve_one_period_ConsIndShock`の引数・出力定義。

**利用条件と実装。** 所得、借入制約、価格を定めた家計の消費貯蓄問題に用いる。`cFunc`は正規化市場資源から消費、`vFunc`は同じ状態から期首価値を返す。`mNrmMin`は定義域の下限、`vFuncBool`は価値関数の計算指定であり、解は`consumer.solution`に保存される。

**ERSとの対応と判断。** [モデル契約](../../skills/econ-knowledge/references/model-contracts.json)の`MC-hark-consumption-saving`、HET-01・DYN-03、[research_causal.py](../../skills/econ-data/scripts/research_causal.py)の`select_method`にある`consumption_saving`入口を保持した。採用契約のHARK 0.17.2と既存の実行条件を使う。今回、[公式戻り値の受渡し](../../skills/econ-data/references/implementation.md#estimator-engine-and-algorithm-selection)に、評価済み政策・価値の状態グリッド、年齢、恒常所得による正規化、シナリオを保存する操作を追加した。

### 13. QuantEcon/QuantEcon.py

固定版：`d30c9000a96d7ae1d434bdecb4aa63d285a18599`。実読：[README](https://github.com/QuantEcon/QuantEcon.py/blob/d30c9000a96d7ae1d434bdecb4aa63d285a18599/README.md)、[quantecon/markov/ddp.py](https://github.com/QuantEcon/QuantEcon.py/blob/d30c9000a96d7ae1d434bdecb4aa63d285a18599/quantecon/markov/ddp.py)の`DiscreteDP.solve`、`DPSolveResult`、`sigma_values`、`backward_induction`。

**利用条件と実装。** 有限状態・行動、報酬、遷移、割引率を定めた動学計画に用いる。定常問題の`solve`は価値`v`、政策添字`sigma`、制御されたMarkov連鎖`mc`を返す。`sigma_values`は行動座標を使って添字を行動値へ戻す。有限期間の`backward_induction(ddp, T, v_term)`は、指定された終端価値の下で期間別の価値と政策添字を返す。

**ERSとの対応と判断。** [designs](../../skills/econ-design/references/designs.md#deliver-the-selected-result)と既存の公式API選択・数値計算を維持した。[implementation](../../skills/econ-data/references/implementation.md#estimator-engine-and-algorithm-selection)に、定常・有限期間の入口と戻り値を明記し、政策添字と経済的な行動単位の両方を保存する手順を追加した。論文は状態、報酬、割引、期間を伴う政策・価値を説明する。

### 14. jeffgortmaker/pyblp

固定版：`16536807004b16c24fb40b931531b45b33884e00`。実読：[README.rst](https://github.com/jeffgortmaker/pyblp/blob/16536807004b16c24fb40b931531b45b33884e00/README.rst)、[pyblp/results/economy_results.py](https://github.com/jeffgortmaker/pyblp/blob/16536807004b16c24fb40b931531b45b33884e00/pyblp/results/economy_results.py)の`compute_prices`、`compute_profits`、`compute_consumer_surpluses`の引数、数量定義、実装。

**利用条件と実装。** 推定した需要・供給プリミティブから、所有・費用変更後の価格、数量、利益、余剰を比較する。`compute_prices`は変更後の均衡価格を解く。`compute_profits`の既定シェアは元のシェアであり、返す粗利益は人口で正規化した`(p-c)s`である。消費者余剰の計算は採用した価格微分・所得効果の条件に従う。

**ERSとの対応と判断。** [implementation](../../skills/econ-data/references/implementation.md)の費用、価格、シェア、利益を同じシナリオで計算する順序と、[research_markets.py](../../skills/econ-data/scripts/research_markets.py)のパラメータ・SE・均衡・厚生保存を保持した。今回、戻り値の対応表に同一シナリオ、市場人口、金額への換算を記載した。本文の反実仮想比較は、その定義を保存結果から引き継ぐ。

### 15. py-econometrics/pyfixest

固定版：`2fb86f30a65f4ad9fa70b1e69bc8da6d0bbcd5db`。実読：[READMEのFeatures・Quickstart](https://github.com/py-econometrics/pyfixest/blob/2fb86f30a65f4ad9fa70b1e69bc8da6d0bbcd5db/README.md)、[feols.py](https://github.com/py-econometrics/pyfixest/blob/2fb86f30a65f4ad9fa70b1e69bc8da6d0bbcd5db/pyfixest/estimation/api/feols.py)の関数引数・`store_data`・`lean`・戻り値、[_result_accessor_mixin.py](https://github.com/py-econometrics/pyfixest/blob/2fb86f30a65f4ad9fa70b1e69bc8da6d0bbcd5db/pyfixest/estimation/models/_result_accessor_mixin.py)の`tidy`本文と`confint`の引数・対象。

**利用条件と実装。** 採用した固定効果、重み、共分散、標本による線形推定に用いる。`tidy`は係数名に対応する推定値、SE、t値、p値、区間を返す。`confint`は選択係数と推論方式を受け取る。`store_data`と`lean`は、後続操作に必要なデータ・推定配列の保持を決める。

**ERSとの対応と判断。** [research_causal.py](../../skills/econ-data/scripts/research_causal.py)の`hdfe`と既存の推論保存を維持した。[implementation](../../skills/econ-data/references/implementation.md#estimator-engine-and-algorithm-selection)に、係数名と経済的な項、区間の水準と係数集合、後続操作に必要なデータの対応を追加した。採用済み環境で実際の関数引数を確認し、保存結果の同じ項を表・図・本文で利用する。

### 16. bcallaway11/did

固定版：`9ead26b9d37c7f2bc202bebc4f5e8220ab7e8c13`。実読：[README](https://github.com/bcallaway11/did/blob/9ead26b9d37c7f2bc202bebc4f5e8220ab7e8c13/README.md)、[R/aggte.R](https://github.com/bcallaway11/did/blob/9ead26b9d37c7f2bc202bebc4f5e8220ab7e8c13/R/aggte.R)、[R/AGGTEobj.R](https://github.com/bcallaway11/did/blob/9ead26b9d37c7f2bc202bebc4f5e8220ab7e8c13/R/AGGTEobj.R)のオブジェクトとsummaryの区間構成。

**利用条件と実装。** 採用したコホート、比較群、平行トレンド、先取り、標本と集計対象に基づくATTに用いる。`aggte`はsimple・dynamic・group・calendarを選び、`balance_e`とイベント窓を受け取る。`AGGTEobj`は`overall.att`、`att.egt`、`egt`、SE、選択した区間族の臨界値、影響関数、`DIDparams`を保持する。

**ERSとの対応と判断。** [research_causal.py](../../skills/econ-data/scripts/research_causal.py)の`_staggered_did`は、実際の`att_gt`・`aggte`設定、区間、コホート寄与、標本IDを保存する。この実行経路を保持し、[implementation](../../skills/econ-data/references/implementation.md#estimator-engine-and-algorithm-selection)に集計種類、イベント窓、バランス化、重みと数量の対応を追加した。総括ATTと各イベント時点の効果は、それぞれの対象定義を伴って文章化する。

## 成果物生成と追加の専門比較

### 17. OpenSourceEconomics/econ-project-templates

固定版：`8dcd9d0cb9fc928c6ddd87b72ce1b7901acd2831`。実読：[README](https://github.com/OpenSourceEconomics/econ-project-templates/blob/8dcd9d0cb9fc928c6ddd87b72ce1b7901acd2831/README.md)、[documents/task_documents.py](https://github.com/OpenSourceEconomics/econ-project-templates/blob/8dcd9d0cb9fc928c6ddd87b72ce1b7901acd2831/documents/task_documents.py)、[src/template_project/final/task_final_template.py](https://github.com/OpenSourceEconomics/econ-project-templates/blob/8dcd9d0cb9fc928c6ddd87b72ce1b7901acd2831/src/template_project/final/task_final_template.py)。

**利用条件と実装。** 保存した分析結果から図表、論文、発表資料を作る研究プロジェクトに用いる。`task_compile_paper`と`task_compile_presentation`は本文、文献、保存図表への依存を宣言する。`task_plot_results_by_age`は保存データ・予測から図を作り、`task_create_results_table`は保存した推定結果からMarkdown表を作る。

**ERSとの対応と判断。** 既存の[研究DAG](../../harness/research.py)、[論文テンプレート](../../tex/paper/ecta_template.tex)、[Beamer](../../tex/slides/main.tex)、Quartoの生成経路を保持した。[research_artifacts.py](../../harness/research_artifacts.py)に、選択結果のモデル定義と、保存済み領域・経路・均衡点を表示する処理を追加した。[paper-workflow](../../skills/econ-writing/references/paper-workflow.md#theory-model-and-proof)は、図と本文が同じ経済的関係を示すように選択する。

### 18. vincentarelbundock/modelsummary

固定版：`847bece31af20d6f4b1bccd44321aec94e7b6da4`。実読：[README](https://github.com/vincentarelbundock/modelsummary/blob/847bece31af20d6f4b1bccd44321aec94e7b6da4/README.md)、[R/modelsummary_list.R](https://github.com/vincentarelbundock/modelsummary/blob/847bece31af20d6f4b1bccd44321aec94e7b6da4/R/modelsummary_list.R)、[R/get_estimates.R](https://github.com/vincentarelbundock/modelsummary/blob/847bece31af20d6f4b1bccd44321aec94e7b6da4/R/get_estimates.R)。

**利用条件と実装。** 複数モデルの係数、推論、適合統計を共通の表で示す際に用いる。`modelsummary_list`は保存された`tidy`・`glance`表を受け取る。`get_estimates`は項と群の対応、公式推論から得た推定値を扱う。

**ERSとの対応と判断。** [result-artifacts](../../skills/econ-writing/references/result-artifacts.md#save-displays-at-analysis-or-registration)の係数、SE、区間、N、固定効果、クラスタの共通フィールド、回帰表パネル、モデルごとの表示形式を保持した。科学的な計算と推論は[econ-data](../../skills/econ-data/SKILL.md)が担い、表示は選択した保存済み結果を使う。今回の選択処理とモデル定義の追加は、この既存の表生成にも同じ結果の意味を渡す。

### 19. viplee110/economics-paper-reviewer

固定版：`a4b55ffe8f47ac85423aed15f4027a66c438b7ad`。今回の追加探索で発見。実読：[README](https://github.com/viplee110/economics-paper-reviewer/blob/a4b55ffe8f47ac85423aed15f4027a66c438b7ad/README.md)、[SKILL.md](https://github.com/viplee110/economics-paper-reviewer/blob/a4b55ffe8f47ac85423aed15f4027a66c438b7ad/SKILL.md)、[theory_review.md](https://github.com/viplee110/economics-paper-reviewer/blob/a4b55ffe8f47ac85423aed15f4027a66c438b7ad/references/theory_review.md)、[structural_review.md](https://github.com/viplee110/economics-paper-reviewer/blob/a4b55ffe8f47ac85423aed15f4027a66c438b7ad/references/structural_review.md)、[evidence_grounding.md](https://github.com/viplee110/economics-paper-reviewer/blob/a4b55ffe8f47ac85423aed15f4027a66c438b7ad/references/evidence_grounding.md)。

**利用条件と実装。** 理論・構造研究の中心命題と根拠を評価する際に用いる。理論では原始的要素から結果への関係、構造研究ではモデルと観測、パラメータとモーメントの対応を調べる。evidence_groundingはその判断を研究の根拠に結び付ける。

**ERSとの対応と判断。** 既存の[econ-review](../../skills/econ-review/SKILL.md)と[evidence binder](../../harness/research_evidence.py)を継続する。今回追加した保存モデル定義により、WritingとReviewが同じ式、条件、パラメータの役割を使う。[CORE](../../runtime/CORE.md#completion-and-reporting)の統合レビューと[TEAM](../../runtime/TEAM.md)の既存役割で、採用した研究と実際の成果物を評価する。

### 20. juliaError/econ-TopJournal-writing-Skill

固定版：`1dd28fd41d24ae2565b424bd7a1d3edb8d910c3f`。実読：[README](https://github.com/juliaError/econ-TopJournal-writing-Skill/blob/1dd28fd41d24ae2565b424bd7a1d3edb8d910c3f/README.md)、[WritingのSKILL.md](https://github.com/juliaError/econ-TopJournal-writing-Skill/blob/1dd28fd41d24ae2565b424bd7a1d3edb8d910c3f/skills/econ-writing-workflow/SKILL.md)、[結果から構成への接続](https://github.com/juliaError/econ-TopJournal-writing-Skill/blob/1dd28fd41d24ae2565b424bd7a1d3edb8d910c3f/skills/econ-writing-workflow/references/full-paper-drafting/02_from_results_to_outline.md)、[論証と執筆課題](https://github.com/juliaError/econ-TopJournal-writing-Skill/blob/1dd28fd41d24ae2565b424bd7a1d3edb8d910c3f/skills/econ-writing-workflow/references/outlines/01_argument_and_writing_task_outlines.md)。

**利用条件と実装。** 結果を持つ論文の構成と改稿に用いる。表図の経済的対象・役割・標本・仕様を研究質問へ結び、中心結果を運ぶ表図を主本文へ配置する。各主張には説明を完成させる本文位置を与え、冒頭と結論ではその主張が果たす機能に合わせて再利用する。

**ERSとの対応と判断。** [argument.py](../../harness/argument.py)と[paragraph.py](../../harness/paragraph.py)に、指定した完成段落から支持する主張・前提依存・採用図表を選ぶ `composition_context` を追加した。既存の `design` 入口が同じ中央質問・答え・貢献と保存結果の参照を章節設計へ渡す。[result-artifacts](../../skills/econ-writing/references/result-artifacts.md#browse-compare-and-edit-saved-results)では、中心的な推論に必要な表図を選び、ResultsとDiscussionへ接続する操作を具体化した。

### 21. shuangchenfinance/research-skills

固定版：`615de14afdbdf4b5789734959633a32420764f40`。実読：[README](https://github.com/shuangchenfinance/research-skills/blob/615de14afdbdf4b5789734959633a32420764f40/README.md)、[econ-referee/SKILL.md](https://github.com/shuangchenfinance/research-skills/blob/615de14afdbdf4b5789734959633a32420764f40/skills/econ-referee/SKILL.md)、[specialized-tasks.mdのREFEREE RESPONSE](https://github.com/shuangchenfinance/research-skills/blob/615de14afdbdf4b5789734959633a32420764f40/skills/econ-write/specialized-tasks.md)、[econ-write/SKILL.mdのREWRITE](https://github.com/shuangchenfinance/research-skills/blob/615de14afdbdf4b5789734959633a32420764f40/skills/econ-write/SKILL.md)、[econ-writing-plus/SKILL.mdのECONOMIC SIGNIFICANCE](https://github.com/shuangchenfinance/research-skills/blob/615de14afdbdf4b5789734959633a32420764f40/skills/econ-writing-plus/SKILL.md)。

**利用条件と実装。** 実証論文の査読、改稿、経済的な大きさの説明に用いる。各指摘へ本文・表図の根拠を付し、回答では変更内容、その掲載箇所、変更の理由を対応させる。改稿は著者の経済的な意味を保持する。

**ERSとの対応と判断。** [research_evidence.py](../../harness/research_evidence.py)の既存 `review` と `response_draft` は、固定した指摘・基準、保存された旧本文、現行の修正箇所、根拠ファイルと計算結果を対応させる。今回の `45419eb8` は、現行の `rationale` を根拠説明として、修正本文・位置・出典とともに既存のWriting hostへ渡す。compose・revise・translateがfindingごとの完成回答を返し、回答欄へ出力する。周辺追記で段落位置が移った場合も、同じ主張の判断を再利用して現行箇所を引用する。

## 論文資料から具体化したWriting判断

### 定義・形式文・説明文の対応

William Thomson（1999）, “The Young Person's Guide to Writing Economic Theory,” *Journal of Economic Literature* 37(1), 157–183。[DOI: 10.1257/jel.37.1.157](https://doi.org/10.1257/jel.37.1.157)。実読箇所は第2節General Principlesの158–159頁と、第4節Definitionsの162–165頁。

この読解を、定義の順序、形式文と説明文の対応、改稿・翻訳後の経済的対象の保持に用いた。具体的な実装は[理論節](../../skills/econ-writing/references/paper-workflow.md#theory-model-and-proof)、[改稿の意味対応](../../skills/econ-review/SKILL.md#locate-and-repair-the-cause)、独自のCournot・生産日程の作例に置いた。式の定義域、量化、不等号、集計順序と、その式を使う文章を対応づける。

### 結果から次の推論への接続

Raj Chetty, John N. Friedman, Nathaniel Hilger, Emmanuel Saez, Diane Whitmore Schanzenbach and Danny Yagan（2011）, “How Does Your Kindergarten Classroom Affect Your Earnings? Evidence from Project STAR,” *Quarterly Journal of Economics* 126(4), 1593–1660。[DOI: 10.1093/qje/qjr041](https://doi.org/10.1093/qje/qjr041)。実読箇所はAbstract・Introductionの1593–1598頁、IV.A Class Sizeの式(1)・Table V・Figure IIを含む1619–1621頁、VI Fade-out, Reemergence, and Noncognitive SkillsのFigure VIの構成を含む1649–1651頁、VII Conclusion冒頭の1655–1656頁。

この読解を、割当て、結果変数、母集団、期間が次の推論を定める段落構成に用いた。[段落ガイド](../../skills/econ-writing/references/paragraph-workflow.md)と[章節ガイド](../../skills/econ-writing/references/paper-workflow.md)に接続し、独自の食品加工団地の[英語](../../profiles/default-micro/extended-introduction-en.md)・[日本語](../../profiles/default-micro/extended-introduction-ja.md)のResultsとDiscussionを追加した。同じ保存数量を使い、ピークMW、日次エネルギー、料金、実施、引渡し、生産量をそれぞれの定義に結び付ける。個別実施と一括実施の比較から、同意の仕組みが電力需要を変える経路を説明する。

## 0.60.0の実行経路と保存結果の完成

PR #16の保存済み比較・実行結果を引き継ぎ、次の3箇所を既存の所有実装で完成させた。

- **無裁定価格境界。** [状態価格の接続](https://github.com/yoshimurahiroki/econ-project-mini/commit/03574b4bd7d3d842b49875f974e6027c2f7feba9)は、既存ASSET-01／MC-state-price-boundsと数値関数を、モデル選択、実行仕様、保存結果へ接続する。3状態の独立計算で未複製請求権の価格集合(0,1)、複製請求権の価格2、正の状態価格、価格式、ヘッジ、時点別単位を確認した。選択CLIが返すコマンドをそのまま実行する検算1件が成功した。
- **同じ保存結果の再利用。** [生成元情報の共有化](https://github.com/yoshimurahiroki/econ-project-mini/commit/7666f8143fc4e32fb495a4b48a01efd6685a1778)は、完全一致する生成元のoptions等をsource_result内へのsource_fields参照にまとめる。12件の計算記録と49表示の全公開値・content hashを保持し、gallery.jsonを4,299,997から3,660,204 bytesへ縮小した。既存テスト3件と一覧・選択・比較・編集・PNG/SVG描画、原稿入力、研究資料への引渡しが成功した。
- **査読から実改稿・回答への対応。** [削除claimの指摘保持](https://github.com/yoshimurahiroki/econ-project-mini/commit/115b63fb34d748a6ed9cc266af4a4061e001b9e2)は、再審査時に初回指摘の全IDを保持する。明示的な削除判断を回答作成へ渡し、判断の再利用と原文復帰時の再審査を実CLIで確認した。回帰2件が成功し、元原稿・保存結果・前回reviewのバイトを保持した。

具体例は437 files／54,688,284 bytesから97 files／15,193,290 bytesへ整理した。source_distribution_onlyの例を正本に保持し、旧.agentsギャラリーと各skill bundleの複製を配布対象から外す。七つのWritingモード、採用済み研究仕様、推定結果、既存プラグインのID・接続・設定を継続する。

