# Decision proposals and pre-analysis plans

Two deliverables that commit someone to an action before the outcome is known: a decision proposal for a firm, and a pre-analysis plan for an estimate. Both are written from the worksheet `work/<topic>.md` after its sections 1 to 6 are filled; the headings below are the order of the document, and each part names the worksheet lines it draws on. Expression follows [WRITING](../../../runtime/WRITING.md); Japanese wording comes from the user's Japanese exemplars, never from these English headings.

## A. Decision proposal

A proposal to management (pricing, pay and evaluation, hiring, organization, investment, a pilot). The reader decides; the document gives the recommended action, why it beats the alternatives, what it costs, and what observation would reverse it.

### A1. Fill the worksheet first

| Worksheet line | What it must hold for a proposal |
| --- | --- |
| 1. Decision maker, Decision, Stake | the person who signs, the action on the table, the money, people or time at stake |
| 1. Facts and magnitudes | baseline numbers of the business (revenue, headcount, turnover, conversion) with source tags |
| 2. Question | the choice among concrete options under one objective |
| 3. Model, Prediction | the incentive or market model behind each option and what it predicts |
| 4–5 | estimates from data, or the solved model over parameter ranges (without data) |
| 6. Decision, Switches when, Measure first | the recommended option, the switching value, the quantity whose measurement would change the decision most |
| 6. Objections and answers | the strongest alternative explanation and how the recommendation handles it |
| 6. Actions (owner, date) | who does what by when |

### A2. Order of the document

1. **Recommendation.** The action, its expected effect with a range and unit, its cost, and the condition under which another option wins. One paragraph or one slide.
2. **Decision and stake.** Who decides, by when, and the magnitude at stake.
3. **Options compared.** A table of the feasible options under the same objective, population, period and units: expected effect (range), cost, time to effect, and the value of the key unknown at which each option wins. Dominated options are listed with the reason they drop out.
4. **Economic reasoning.** The actors and their incentives, the model with the condition that determines the choice, and the prediction that separates the options.
5. **Evidence.** Estimates with intervals, or simulated outcomes over the parameter ranges, each with its source (saved result, literature, company data).
6. **Implementation.** Steps with owner, date and resources; the order follows dependencies.
7. **Measurement.** How the effect will be verified after the decision: a randomized pilot or staggered rollout where feasible, the comparison group, the primary indicator, and the threshold that triggers a change. An indicator used for pay or evaluation is checked for the distortions of multitask incentives ([knowledge: CONTRACT-07]).
8. **Switching conditions.** The observations that would reverse the recommendation, each with its threshold.

### A3. Expression

- Risks and uncertainties enter only as switching conditions (part 8) and as ranges (parts 1, 3, 5); there is no separate risk or limitation section.
- Every number comes from the worksheet and its saved results; ranges carry their source.
- Slides follow the same order: one slide per part, the recommendation first, the options table on one slide.
- Templates: `tex/slides/main.tex` for slides; a document through `tex/paper/quarto_template.qmd`, a meeting material through `tex/slides/meeting_template.qmd`, or the format the user names.

## B. Pre-analysis plan

A plan that fixes the sample, specification, outcomes, inference and decision rule before the outcome data are seen (an experiment, a rollout, an evaluation of a policy change). Its content is a set of conditions: under rule 3 of [WRITING](../../../runtime/WRITING.md) each enters the text as a proposition of the plan ("The primary outcome is …", "Standard errors are clustered at …").

### B1. Fill the worksheet first

Sections 1 to 4 as usual. Before outcome data exist, sections 5 and 6 hold the planned analysis:

- **5. Execution:** the planned specification run on simulated or placebo data with the planned code (the `estimate_ladder.py` simulation, `rct_design` with `operation="diagnose"`, or `rdpower`), with the saved result file. This checks that the code runs and gives the precision the plan relies on.
- **6. Decision:** the decision rule by estimate range ("adopt when the lower bound of the interval at the user's level exceeds the threshold"). **Switches when:** the threshold. **Specification changes:** none (plan stage).

### B2. Order of the document

1. **Question and hypotheses.** The question (worksheet section 2) and the hypotheses as the predictions of the competing mechanisms (section 3), each with the sign or pattern that would support it.
2. **Design.** Assignment or source of variation, the comparison group and the estimand (section 4); standard identifying conditions are named by the design, and only case-specific threats are written out; the method card for the chosen method ([which method](../../econ-design/references/causal-models.md#which-method)).
3. **Population and sample.** Eligibility, unit, period, sample size, exclusion rules written before the data, and the handling of attrition.
4. **Outcomes.** The primary outcome with its definition and unit; secondary outcomes as a declared family.
5. **Specification.** The headline specification and the ladder rungs ([empirical procedure](../../econ-data/references/empirical.md), steps E4 and E5), with covariates and fixed effects listed.
6. **Inference.** Cluster level, the few-cluster rule, the multiple-testing family and procedure, and the interval reported.
7. **Precision.** The significance level and target power chosen by the user, and the minimum detectable effect from the simulation of section 5, compared with the decision threshold.
8. **Heterogeneity.** The subgroups declared in advance, each with the mechanism that predicts it.
9. **Decision rule.** The action taken for each range of the primary estimate.
10. **Deviations.** Changes after data arrive follow the classes of [step E6b](../../econ-data/references/empirical.md#step-e6b-specification-changes-after-the-first-result) and are reported with their number and reason.

### B3. Values the user sets

The significance level, target power, decision threshold and the family of outcomes are the user's or the decision maker's choices. Write them with the tag [user]; when the user has not given them, ask once and mark the fields open in the worksheet.
