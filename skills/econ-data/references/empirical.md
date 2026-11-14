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
| Eligibility by a threshold of a score | regression discontinuity | `rdrobust` local linear, data-driven bandwidth → half and double bandwidth | density test (`rddensity`), covariate continuity |
| An excluded instrument | instrumental variables | reduced form → first stage → 2SLS (`pf.feols("y ~ 1 | fe | d ~ z")`) | effective first-stage F; below 10, Anderson–Rubin interval |
| Few treated aggregate units | synthetic control | `synthdid`, `Synth` | pre-period fit, placebo units |
| Exposure built from shares and shocks | shift-share | [shift-share design](../../econ-design/references/designs.md#shift-share-designs) | exposure-robust standard errors |
| Only selection on observables | conditional independence | regression → `DoubleML` with cross-fitting | overlap of propensity scores |

Inference rules, applied to every row:

1. Cluster at the level at which treatment is assigned.
2. Fewer than about 40 clusters, or fewer than about 10 treated clusters: wild cluster bootstrap (`fwildclusterboot` in R; `pyfixest` `wildboottest`) and report the cluster counts.
3. Several outcomes testing one hypothesis: name the primary outcome in advance and report family-wise adjusted p values (`pf.rwolf`, `pf.wyoung`) for the family.
4. Leads in an event study are evidence on parallel trends; when they are non-zero, report the sensitivity bounds (HonestDiD) next to the estimate.

The full list of package calls is the [implementation table](implementation-engines.md).

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

## Step E7. Interpretation

```
Headline estimate:     <value> (SE <value>), 95% interval [<low>, <high>], <units>, <population>, <period>
Magnitude:             relative to the baseline mean, per unit of treatment, elasticity, cost per outcome
Against predictions:   which mechanism of section 3 the estimate supports and which it rejects
Decision:              the action it selects at the threshold of step E1
Switches when:         the effect size or cost at which the decision changes
```

Copy these lines into section 6 of the worksheet.
