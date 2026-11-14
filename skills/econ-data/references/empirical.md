# Empirical analysis, step by step

Use this for steps 4 to 6 of the [economist's procedure](../../../runtime/ECONOMIST.md) whenever data are involved. Each step ends with a filled block in the worksheet `work/<topic>.md`; the next step starts only when the block is filled. Run every estimate through code and save it; numbers in the answer come from the saved output.

## Step E1. Estimand

```
Estimand:            average effect of <treatment> on <outcome> for <population>, <period>, in <units>
Model link:          which parameter or prediction of section 3 it measures
Competing predictions and the estimate that separates them:
Decision threshold:  the effect size at which the decision in section 1 changes
```

## Step E2. Data audit

Load the data and print, before any regression:

```
Unit / time / keys:         unique on (unit, time)? duplicates dropped how?
Coverage:                   units, periods, balanced panel?
Treatment:                  coding, timing (one date or staggered), share treated, switches off?
Outcome:                    distribution, zeros, outliers, units, transformations
Missing values:             per variable and by treatment status
Sample rule:                written before seeing estimates; post-treatment variables excluded from the rule
```

## Step E3. Raw facts

Plot or tabulate before modelling: outcome means by group and period (raw trends around adoption), the first stage in raw form for IV, the outcome against the running variable for RD. Write two lines on what the raw pattern already says about the competing predictions.

## Step E4. Design and method: decision rules

Choose by the source of variation; the first matching row decides.

| Variation | Design | Estimator (rung order in the ladder) | Required diagnostics |
| --- | --- | --- | --- |
| Random assignment | experiment | difference in means → with strata fixed effects → with pre-registered covariates | balance table, attrition by arm |
| One adoption date, treated and control groups | 2×2 difference-in-differences | raw difference → two-way fixed effects → + pre-determined controls | event-study leads |
| Adoption dates differ across units (staggered), absorbing | staggered difference-in-differences | two-way fixed effects as rung 1 only → imputation (`pf.did2s`) or `did::att_gt` | leads, cohort-specific effects, HonestDiD sensitivity |
| Treatment switches on and off, or doses differ | treatment paths | `DIDmultiplegtDYN`, `contdid` (R) | placebo switches |
| Eligibility by a threshold of a score | regression discontinuity | `rdd_sharp` or `rdd_fuzzy` (robust bias-corrected local linear, MSE-optimal bandwidth) → half and double bandwidth; `rdd_localrand` when few units lie near the threshold | density test (`rddensity`), covariate continuity, h and b on each side |
| An excluded instrument | instrumental variables | reduced form → first stage → 2SLS (`pf.feols("y ~ 1 | fe | d ~ z")`) | robust (effective) first-stage F; with weak-identification risk the Anderson–Rubin set (`iv_ar_robust`) is the reported interval, since F = 10 is a heuristic, not a validity condition |
| Few treated aggregate units | synthetic control | `synthetic_control` or `scm_diagnostics` (one treated unit), `synthdid` (a treated block) | treated unit and donor pool fixed and saved before estimation; pre-period fit; in-space and in-time placebos; for `synthdid` the variance method and replications; no joint band without a returned covariance |
| Exposure built from shares and shocks | shift-share | `shift_share` → `shift_share_inference` with the identification basis (shocks or shares) fixed first; [shift-share design](../../econ-design/references/designs.md#shift-share-designs) | shocks: AKM inference and effective shock count; shares: Rotemberg weights and balance |
| Only selection on observables | conditional independence | regression → `dml_irm` (binary) or `dml_plr` with cross-fitting → `grf` for heterogeneity | overlap of propensity scores (trimming to [0.1, 0.9] as a sensitivity), learner sensitivity |

Inference rules, applied to every row:

1. Cluster at the level at which treatment is assigned.
2. Few clusters, few treated clusters or very unequal cluster sizes: report the wild cluster bootstrap (`wild_cluster_bootstrap`) and the CR2 test with Satterthwaite degrees of freedom (`club_sandwich`) next to the clustered standard error, with the counts of clusters and treated clusters.
3. Several outcomes testing one hypothesis: name the primary outcome in advance and report family-wise adjusted p values for the family (`romano_wolf`; `holm` for p values from separate saved results).
4. Leads in an event study are evidence on parallel trends; when they are non-zero, report the sensitivity bounds (HonestDiD) next to the estimate.

Method cards with options, checks and pitfalls: [DiD and synthetic control](../../econ-design/references/causal-models/did.md), [RD, IV, experiments and inference](../../econ-design/references/causal-models/rd-iv-experiments.md), [ML, heterogeneity and policy](../../econ-design/references/causal-models/ml-heterogeneity.md), [outcomes, bounds and sensitivity](../../econ-design/references/causal-models/outcomes-bounds-sensitivity.md), [regression foundations and engines](../../econ-design/references/causal-models/regression-engines.md). The full list of package calls is the [implementation table](implementation-engines.md).

## Step E5. Specification ladder

Copy the template, set the roles and the rungs for the chosen design, and run it:

```sh
cp skills/econ-data/templates/estimate_ladder.py work/<topic>_estimate.py
python3 work/<topic>_estimate.py data/<file>.csv work/<topic>_estimate.json
```

Each rung changes one thing: the comparison, the fixed effects, the controls, the estimator, the sample definition. The report gives each rung's estimate, standard error, 95% interval and cluster count, flags the inference rules that apply, and marks the rungs whose estimate leaves the previous interval. The rung that matches the design in step E4 is the headline estimate; the other rungs show what each choice does to it. Without a data file the template runs a simulated staggered panel: the two-way fixed effects rung gives 1.11, the imputation rung 1.68, against a true average effect of 1.83.

Stop adding rungs when a further change keeps the estimate inside the headline interval and leaves the decision unchanged. A rung that moves the estimate across the decision threshold is reported with its reason.

## Step E6. Diagnostics

Fill the diagnostics of the chosen row of step E4 with numbers: leads and their joint test, balance, density test, first-stage F, overlap, pre-period fit. A failed diagnostic sends the work back to step E4 for another design or a narrower population.

## Step E6b. Specification changes after the first result

The first specification, fixed in step E4 before seeing results, is the baseline and stays in the report. When an estimate or diagnostic looks wrong, find the cause first and route it by class:

| Class | Examples | Action |
| --- | --- | --- |
| 1. Implementation or data error | wrong transformation, misaligned sample, mislabelled series, coding slip | fix and rerun automatically; record the fix |
| 2. Pre-specified statistical rule | lag length by the stated criterion, the documented default for a failed diagnostic | apply and rerun automatically; record the rule |
| 3. Economically motivated change | different controls, sample period, outcome definition, identification, clustering, anything that would move results toward expected signs | never automatic: propose it with the failed check and its economic reason; run it as a labelled sensitivity next to the baseline |
| 4. Unexpected but clean result | sign or size against the prior with no error found | report and interpret; it may be the finding |

Rules:

1. Classes 1 and 2 share a budget of five automatic reruns; after that, present every attempt and ask the user.
2. A specification is never chosen by its results. "Try X until it is significant" is replaced by a pre-specified design.
3. The report states the number of specification changes after the first result (zero included) and what each changed, from worksheet section 6 (`Specification changes:`). With class 3 changes, the reported intervals carry that search: the baseline is reported first.
4. Named anomalies are flagged before results are delivered: estimates outside the plausible range of the literature, wrong-signed first stages, weak instruments, failed pre-trends, explosive dynamics, implausible magnitudes against the baseline mean.

## Step E7. Interpretation

```
Headline estimate:     <value> (SE <value>), 95% interval [<low>, <high>], <units>, <population>, <period>
Magnitude:             relative to the baseline mean, per unit of treatment, elasticity, cost per outcome
Specification changes: number after the first result, each with its class (E6b) and reason
Against predictions:   which mechanism of section 3 the estimate supports and which it rejects
Decision:              the action it selects at the threshold of step E1
Switches when:         the effect size or cost at which the decision changes
```

Copy these lines into section 6 of the worksheet.
