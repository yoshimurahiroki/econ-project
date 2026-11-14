# Machine learning, heterogeneous effects and policy

Method cards for orthogonal-score (DoubleML), generalized-random-forest, meta-learner, TMLE, policy-learning and post-estimation methods run by `python3 skills/econ-data/scripts/research_causal.py run SPEC.json --output RESULT.json`. The shared specification fields are in [specification and result](contract.md#specification-and-result); runner details are in [heterogeneity](heterogeneity.md), [policy](policy.md) and [extensions](extensions.md). Each card gives when to use the method, how it differs from its neighbours, the estimand, the identifying conditions, the runner call and options (checked against the code), the native arguments that change the result and how they are set, the returns, the checks before reporting, documented pitfalls and sources.

Rules shared by every DoubleML card (`dml_*`):

- `inference` is `{"type":"official"}` or `{"type":"cluster","cluster":...}` (one or two cluster columns). Quantile and tail models and the nonignorable selection score refuse clustering, and the multiplier `bootstrap` requires independent observations.
- `regressors` lists the pre-treatment covariates and must not be empty. `learners` maps each nuisance name (`ml_l`, `ml_m`, `ml_g`, `ml_r`, `ml_pi`, as the card lists) to `{"type": ..., "params": {...}}` with type `linear`, `ridge`, `lasso`, `logistic`, `random_forest_regressor`, `random_forest_classifier`, `hist_gradient_boosting_regressor` or `hist_gradient_boosting_classifier`; `seed` sets their `random_state`.
- Fix the score and target before choosing learners. Folds follow the unit of independent sampling or assignment: with cluster inference DoubleML splits by cluster. Learner hyperparameters are set inside the training folds (native `params`).
- `n_folds` is at least 2; `joint=true` needs `bootstrap={"method":"normal"|"Bayes"|"wild","n_rep_boot":...}`.
- `dml_plr` and `dml_pliv` take the treatment from `endogenous`; the other models take it from `options.treatment` and need it coded 0/1, except `dml_apo`.

GRF cards (`grf*`) take `inference={"type":"official"}`, native arguments through `options.args`, and column bindings through `options.columns`.

## Which method

| Treatment, target and data | Method |
| --- | --- |
| One slope of a continuous or binary treatment, many controls | `dml_plr` |
| Binary treatment, average effect or effect on the treated, many controls | `dml_irm` |
| Mean outcome at one level of a multivalued treatment | `dml_apo` |
| Binary instrument and binary take-up; complier effect | `dml_iivm` |
| Continuous instrument, partially linear structural slope | `dml_pliv` |
| Two periods, parallel trends conditional on many covariates | `dml_did` |
| Effects on quantiles of the outcome distribution | `dml_qte`; one arm's quantile `dml_pq`; upper-tail mean `dml_cvar` |
| Outcomes observed only for a selected group | `dml_ssm` |
| How the effect varies with covariates; binary or continuous treatment | `grf` (R, full options); `causal_forest` (Python, fixed settings) |
| Heterogeneous effects with an instrument | `grf_instrumental` |
| Several arms; which works better for whom | `grf_multi_arm` |
| Censored time-to-event outcome | `grf_survival` |
| CATE from a chosen learner family, AIPW average | `metalearner` |
| Targeted average effect with bounded estimates | `tmle` |
| A treatment rule and its held-out gain, binary treatment | `policy_tree` |
| Rules over several arms, with costs or constraints, and their value | `policy_learning` |
| Slopes, predictions or contrasts on the outcome scale from a fitted model | `marginaleffects` |

## Orthogonal scores (DoubleML)

### `dml_plr`

**Use when.** Effect of a continuous or binary policy variable (training hours, a tax rate, a subsidy amount) with many controls, under selection on observables, when one slope is the target: the high-dimensional version of regression with controls.

**Versus.** `dml_irm`: Restricts the conditional outcome to a constant additive coefficient on D. `dml_pliv`: Uses conditional exogeneity E(ζ|D,X)=0 rather than an excluded instrument Z.

**Estimand.** Y = D θ₀ + g₀(X) + ζ; D = m₀(X) + V.

**Identification.** E(ζ|D,X) = 0. E(V|X) = 0.

**Run.** `method="dml_plr"` → `DoubleML` `doubleml.DoubleMLPLR` (0.11.4).

**Options.** Required: `learners`, `n_folds`, `score`, `seed`. Optional: `bootstrap`, `confidence_level`, `definitions`, `joint`, `n_rep`, `sample_splitting`.

**Native arguments that change the result.** `n_folds` (Number of cross-fitting folds; default 5; top-level `n_folds` (at least 2)); `n_rep` (Repeated sample splittings; default 1; top-level `n_rep`); `score` (Orthogonal score construction: partialling out or IV-type; default partialling out; top-level `score`: `partialling out` or `IV-type` (the latter adds `learners.ml_g`)); `ml_l` (Estimator of E[Y|X]; default none; `learners.ml_l`); `ml_m` (Estimator of E[D|X]; default none; `learners.ml_m`); `ml_g` (Outcome learner required for IV-type scoring; default None; `learners.ml_g`).

**Returns.** `coef`: Orthogonal-score treatment parameter estimates; `se`: Standard errors for the target estimates; `pval`: P-values for target parameter estimates; `confint()`: Confidence interval estimates at the requested level.

**Checks before reporting.** Nuisance fit: compare out-of-fold loss of at least two learner types from the saved predictions; an estimate that moves with the learner is reported with both. With `n_rep` above 1, report the spread of the estimate across sample splits. Covariates in `regressors` are measured before treatment.

**Pitfalls.** With heterogeneous effects θ is a weighted average with weights proportional to the conditional variance of treatment, not the average effect; for a binary treatment and the average effect use `dml_irm`.

**Sources.** https://docs.doubleml.org/stable/api/generated/doubleml.plm.DoubleMLPLR.html, https://doi.org/10.1111/ectj.12097.

### `dml_irm`

**Use when.** Binary treatment (a programme, a policy adoption) with many covariates and effects that may differ across units; the target is the average effect (`ATE`) or the effect on the treated (`ATTE`).

**Versus.** `dml_plr`: Allows fully heterogeneous treatment effects instead of a constant D coefficient. `dml_apo`: ATE subtracts two potential outcome means; APO targets a specified potential outcome level.

**Estimand.** θ₀ = E[g₀(1,X) − g₀(0,X)].

**Identification.** E(U|X,D) = 0. E(V|X) = 0. Overlap: 0 < P(D = 1 | X) < 1.

**Run.** `method="dml_irm"` → `DoubleML` `doubleml.DoubleMLIRM` (0.11.4).

**Options.** Required: `learners`, `n_folds`, `score`, `seed`, `treatment`. Optional: `bootstrap`, `confidence_level`, `definitions`, `joint`, `n_rep`, `normalize_ipw`, `ps_processor_config`, `sample_splitting`, `trimming_rule`, `trimming_threshold`, `weights`.

**Native arguments that change the result.** `n_folds` (Number of cross-fitting folds; default 5; top-level `n_folds` (at least 2)); `n_rep` (Repeated sample splittings; default 1; top-level `n_rep`); `score` (ATE or ATTE target score; default ATE; top-level `score`: `ATE` or `ATTE`); `ml_g` (Outcome regression learner E[Y|D,X]; default none; `learners.ml_g`); `ml_m` (Propensity score classifier E[D|X]; default none; `learners.ml_m`); `weights` (Optional score weights for ATE; default None; top-level `weights` (ATE score only)); `normalize_ipw` (Normalize inverse propensity weights; default False; top-level `normalize_ipw`); `trimming_threshold` (Propensity-score truncation threshold; deprecated; default 0.01; top-level; deprecated in favour of `ps_processor_config`).

**Returns.** `coef`: Orthogonal-score treatment parameter estimates; `se`: Standard errors for the target estimates; `pval`: P-values for target parameter estimates; `confint()`: Confidence interval estimates at the requested level.

**Checks before reporting.** Overlap: report the range of the saved out-of-fold propensities (`diagnostics.nuisance_predictions`); many values near 0 or 1 mean the estimate rests on few units, and trimming to [0.1, 0.9] is run as a labelled sensitivity. Nuisance fit: compare out-of-fold loss of at least two learner types from the saved predictions; an estimate that moves with the learner is reported with both. With `n_rep` above 1, report the spread of the estimate across sample splits.

**Pitfalls.** The trimming_rule and trimming_threshold arguments are deprecated; ps_processor_config replaces them.

**Sources.** https://docs.doubleml.org/stable/api/generated/doubleml.irm.DoubleMLIRM.html, https://doi.org/10.1111/ectj.12097, https://doi.org/10.1093/biomet/asn055.

### `dml_apo`

**Use when.** Multivalued treatment (dose levels, programme intensities); the target is the mean outcome at one level, run once per level to compare levels.

**Versus.** `dml_irm`: Targets one potential outcome mean rather than ATE or ATTE contrast.

**Estimand.** E[Y(d)] at treatment level d.

**Identification.** Outcome regression depends on treatment and observed X under the interactive regression model. Conditional exchangeability and overlap at the selected treatment level.

**Run.** `method="dml_apo"` → `DoubleML` `doubleml.DoubleMLAPO` (0.11.4). `treatment_level` must be an observed numeric level with at least five observations and another level present.

**Options.** Required: `learners`, `n_folds`, `score`, `seed`, `treatment`, `treatment_level`. Optional: `bootstrap`, `confidence_level`, `definitions`, `joint`, `n_rep`, `normalize_ipw`, `ps_processor_config`, `sample_splitting`, `trimming_rule`, `trimming_threshold`, `weights`.

**Native arguments that change the result.** `n_folds` (Number of cross-fitting folds; default 5; top-level `n_folds` (at least 2)); `n_rep` (Repeated sample splittings; default 1; top-level `n_rep`); `treatment_level` (Observed treatment value defining the potential outcome; default none; top-level `treatment_level`); `ml_g` (Learner for conditional outcome regression; default none; `learners.ml_g`); `ml_m` (Learner for treatment propensity; default none; `learners.ml_m`); `weights` (Optional weighting scheme; default None; top-level `weights`); `normalize_ipw` (Normalize inverse propensity weights; default False; top-level `normalize_ipw`).

**Returns.** `coef`: Orthogonal-score treatment parameter estimates; `se`: Standard errors for the target estimates; `pval`: P-values for target parameter estimates; `confint()`: Confidence interval estimates at the requested level.

**Checks before reporting.** Overlap: report the range of the saved out-of-fold propensities (`diagnostics.nuisance_predictions`); many values near 0 or 1 mean the estimate rests on few units, and trimming to [0.1, 0.9] is run as a labelled sensitivity. Nuisance fit: compare out-of-fold loss of at least two learner types from the saved predictions; an estimate that moves with the learner is reported with both.

**Sources.** https://docs.doubleml.org/stable/api/generated/doubleml.irm.DoubleMLAPO.html, https://doi.org/10.1111/ectj.12097.

### `dml_iivm`

**Use when.** A binary instrument (a lottery offer, a randomized encouragement) moves a binary take-up, with covariates; the target is the local average effect for compliers.

**Versus.** `dml_irm`: Targets a Wald-ratio local effect under binary instrumental variation, not population ATE. `dml_pliv`: Uses binary instrument and treatment with nonlinear conditional response functions.

**Estimand.** θ₀ = {E[g₀(1,X)] − E[g₀(0,X)]}/{E[r₀(1,X)] − E[r₀(0,X)]}.

**Identification.** E(ν|Z,X) = 0; E(U|Z,X) = 0; E(V|X) = 0. Conditional instrument propensity is bounded between ε and 1−ε. Monotonicity: the instrument moves no unit out of treatment.

**Run.** `method="dml_iivm"` → `DoubleML` `doubleml.DoubleMLIIVM` (0.11.4). Requires one endogenous treatment and exactly one 0/1 instrument. `normalize_ipw=true` is refused on DoubleML 0.11.4 (a documented normalization error).

**Options.** Required: `learners`, `n_folds`, `score`, `seed`. Optional: `bootstrap`, `confidence_level`, `definitions`, `joint`, `n_rep`, `normalize_ipw`, `ps_processor_config`, `sample_splitting`, `subgroups`, `trimming_rule`, `trimming_threshold`.

**Native arguments that change the result.** `n_folds` (Number of cross-fitting folds; default 5; top-level `n_folds` (at least 2)); `n_rep` (Repeated sample splittings; default 1; top-level `n_rep`); `ml_g` (Learner for E[Y|Z,X]; default none; `learners.ml_g`); `ml_m` (Learner for E[Z|X]; default none; `learners.ml_m`); `ml_r` (Learner for E[D|Z,X]; default none; `learners.ml_r`); `subgroups` (Restrictions concerning always-takers and never-takers; default None; top-level `subgroups`); `normalize_ipw` (Normalize inverse propensity weights; default False; top-level; refused as true on 0.11.4); `trimming_threshold` (Propensity-score truncation threshold; deprecated; default 0.01; top-level; deprecated in favour of `ps_processor_config`).

**Returns.** `coef`: Orthogonal-score treatment parameter estimates; `se`: Standard errors for the target estimates; `pval`: P-values for target parameter estimates; `confint()`: Confidence interval estimates at the requested level; `robust_confset()`: Confidence set robust to weak instruments.

**Checks before reporting.** First stage: the estimated difference in take-up between instrument arms; a small difference is a weak-identification risk, with `robust_confset()` reported. Nuisance fit: compare out-of-fold loss of at least two learner types from the saved predictions; an estimate that moves with the learner is reported with both. With `n_rep` above 1, report the spread of the estimate across sample splits.

**Pitfalls.** Trimming arguments are deprecated in favor of ps_processor_config.

**Sources.** https://docs.doubleml.org/stable/api/generated/doubleml.irm.DoubleMLIIVM.html, https://doi.org/10.1111/ectj.12097.

### `dml_pliv`

**Use when.** An excluded instrument that may be continuous or multivalued, many controls, and one structural slope as the target.

**Versus.** `dml_plr`: Relies on E(ζ|Z,X)=0 with excluded Z instead of E(ζ|D,X)=0. `dml_iivm`: Partially linear effect coefficient allows instruments beyond binary encouragement.

**Estimand.** Y − D θ₀ = g₀(X) + ζ; Z = m₀(X) + V.

**Identification.** E(ζ|Z,X) = 0. E(V|X) = 0.

**Run.** `method="dml_pliv"` → `DoubleML` `doubleml.DoubleMLPLIV` (0.11.4). Requires one endogenous treatment and at least one instrument.

**Options.** Required: `learners`, `n_folds`, `score`, `seed`. Optional: `bootstrap`, `confidence_level`, `definitions`, `joint`, `n_rep`, `sample_splitting`.

**Native arguments that change the result.** `n_folds` (Number of cross-fitting folds; default 5; top-level `n_folds` (at least 2)); `n_rep` (Repeated sample splittings; default 1; top-level `n_rep`); `ml_l` (Learner for E[Y|X]; default none; `learners.ml_l`); `ml_m` (Learner for E[Z|X]; default none; `learners.ml_m`); `ml_r` (Learner for E[D|X]; default none; `learners.ml_r`); `score` (Partialling-out or IV-type orthogonal score; default partialling out; top-level `score`: `partialling out` or `IV-type`); `ml_g` (Outcome regression learner for IV-type score; default None; `learners.ml_g`).

**Returns.** `coef`: Orthogonal-score treatment parameter estimates; `se`: Standard errors for the target estimates; `pval`: P-values for target parameter estimates; `confint()`: Confidence interval estimates at the requested level.

**Checks before reporting.** First-stage strength of the residualized instrument. Nuisance fit: compare out-of-fold loss of at least two learner types from the saved predictions; an estimate that moves with the learner is reported with both. With `n_rep` above 1, report the spread of the estimate across sample splits.

**Sources.** https://docs.doubleml.org/stable/api/generated/doubleml.plm.DoubleMLPLIV.html, https://doi.org/10.1111/ectj.12097.

### `dml_did`

**Use when.** Two periods, treated and comparison groups, parallel trends plausible only conditional on many covariates; the target is the effect on the treated in the post period.

**Versus.** `dml_irm`: Two-period changes identify the treated-group post-period effect rather than an outcome-level ATE.

**Estimand.** E[Y_post(1) − Y_post(0) | D=1].

**Identification.** No anticipation. Parallel trends conditional on pre-treatment covariates. Overlap: P(D = 1 | X) < 1. The `experimental` score adds independence of treatment and covariates.

**Run.** `method="dml_did"` → `DoubleML` `doubleml.did.DoubleMLDID` (0.11.4). One row per unit, with the post outcome as `outcome` and the pre outcome in `outcome_pre`; the runner passes their difference.

**Options.** Required: `learners`, `n_folds`, `outcome_pre`, `score`, `seed`, `treatment`. Optional: `bootstrap`, `clipping_threshold`, `confidence_level`, `definitions`, `in_sample_normalization`, `joint`, `n_rep`, `sample_splitting`.

**Native arguments that change the result.** `n_folds` (Number of cross-fitting folds; default 5; top-level `n_folds` (at least 2)); `n_rep` (Repeated sample splittings; default 1; top-level `n_rep`); `score` (Observational or experimental DID orthogonal score; default observational; top-level `score`: `observational` or `experimental`); `ml_g` (Learner for E[Y₁−Y₀|D=d,X]; default none; `learners.ml_g`); `ml_m` (Treatment propensity learner under observational score; default None; `learners.ml_m`); `in_sample_normalization` (Normalize treatment propensity weighting in sample; default True; top-level; runner keeps true); `clipping_threshold` (Propensity clipping threshold; default 0.01; top-level; runner default 0.01).

**Returns.** `coef`: Orthogonal-score treatment parameter estimates; `se`: Standard errors for the target estimates; `pval`: P-values for target parameter estimates; `confint()`: Confidence interval estimates at the requested level.

**Checks before reporting.** Covariates in `regressors` are measured before treatment. Overlap: report the range of the saved out-of-fold propensities (`diagnostics.nuisance_predictions`); many values near 0 or 1 mean the estimate rests on few units, and trimming to [0.1, 0.9] is run as a labelled sensitivity. Nuisance fit: compare out-of-fold loss of at least two learner types from the saved predictions; an estimate that moves with the learner is reported with both.

**Sources.** https://docs.doubleml.org/stable/api/generated/doubleml.did.DoubleMLDID.html, https://doi.org/10.1111/ectj.12097.

### `dml_qte`

**Use when.** The target is the effect on quantiles of the outcome distribution (lower and upper wages, test-score tails) under selection on observables; `LPQ` with a binary instrument gives complier quantile effects.

**Versus.** `dml_pq`: Subtracts potential outcome quantiles between treatment states. `dml_cvar`: Targets quantile differences rather than conditional value at risk.

**Estimand.** Q_τ(Y(1)) − Q_τ(Y(0)).

**Identification.** `PQ`: conditional exchangeability and overlap. `LPQ`: binary-instrument independence, exclusion, monotonicity and overlap.

**Run.** `method="dml_qte"` → `DoubleML` `doubleml.DoubleMLQTE` (0.11.4). Clustered inference is refused for quantile models. `quantiles` is a strictly increasing list in (0, 1).

**Options.** Required: `learners`, `n_folds`, `quantiles`, `score`, `seed`, `treatment`. Optional: `bootstrap`, `confidence_level`, `definitions`, `joint`, `n_rep`, `normalize_ipw`, `ps_processor_config`, `sample_splitting`, `trimming_rule`, `trimming_threshold`.

**Native arguments that change the result.** `n_folds` (Number of cross-fitting folds; default 5; top-level `n_folds` (at least 2)); `n_rep` (Repeated sample splittings; default 1; top-level `n_rep`); `quantiles` (Quantile levels to estimate; default 0.5; top-level `quantiles`); `score` (Potential-quantile, local-potential-quantile, or CVaR scoring; default PQ; top-level `score`: `PQ`, `LPQ` or `CVaR`); `normalize_ipw` (Normalize inverse propensity weights; default True; top-level `normalize_ipw`); `kde` (Kernel density estimator for score derivative; default None; package default); `trimming_threshold` (Propensity-score threshold; deprecated; default 0.01; top-level; deprecated in favour of `ps_processor_config`).

**Returns.** `coef`: Orthogonal-score treatment parameter estimates; `se`: Standard errors for the target estimates; `pval`: P-values for target parameter estimates; `confint()`: Confidence interval estimates at the requested level.

**Checks before reporting.** Quantile effects are differences of marginal quantiles, not effects on the units at those quantiles. Overlap: report the range of the saved out-of-fold propensities (`diagnostics.nuisance_predictions`); many values near 0 or 1 mean the estimate rests on few units, and trimming to [0.1, 0.9] is run as a labelled sensitivity. Pointwise intervals across quantiles are not simultaneous; a joint statement needs `joint=true` with `bootstrap`.

**Pitfalls.** Trimming parameters are deprecated in favor of ps_processor_config.

**Sources.** https://docs.doubleml.org/stable/api/generated/doubleml.irm.DoubleMLQTE.html, https://doi.org/10.1111/ectj.12097.

### `dml_pq`

**Use when.** The level of one quantile of the potential-outcome distribution in one arm, as an input to a distributional comparison.

**Versus.** `dml_qte`: Estimates an arm-specific potential quantile rather than the cross-arm quantile difference. `dml_cvar`: Quantile level instead of the corresponding conditional tail mean.

**Estimand.** Q_τ(Y(d)) for treatment d∈{0,1}.

**Identification.** Conditional exchangeability and overlap.

**Run.** `method="dml_pq"` → `DoubleML` `doubleml.DoubleMLPQ` (0.11.4).

**Options.** Required: `learners`, `n_folds`, `quantile`, `score`, `seed`, `treatment`, `treatment_level`. Optional: `bootstrap`, `confidence_level`, `definitions`, `joint`, `n_rep`, `normalize_ipw`, `ps_processor_config`, `sample_splitting`, `trimming_rule`, `trimming_threshold`.

**Native arguments that change the result.** `n_folds` (Number of cross-fitting folds; default 5; top-level `n_folds` (at least 2)); `n_rep` (Repeated sample splittings; default 1; top-level `n_rep`); `treatment` (Potential outcome treatment level, zero or one; default 1; top-level `treatment_level` (0 or 1)); `quantile` (Potential outcome quantile level; default 0.5; top-level `quantile`); `normalize_ipw` (Normalize inverse propensity weights; default True; top-level `normalize_ipw`); `kde` (Kernel density estimator for score derivative; default None; package default); `trimming_threshold` (Propensity-score threshold; deprecated; default 0.01; top-level; deprecated in favour of `ps_processor_config`).

**Returns.** `coef`: Orthogonal-score treatment parameter estimates; `se`: Standard errors for the target estimates; `pval`: P-values for target parameter estimates; `confint()`: Confidence interval estimates at the requested level.

**Checks before reporting.** Overlap: report the range of the saved out-of-fold propensities (`diagnostics.nuisance_predictions`); many values near 0 or 1 mean the estimate rests on few units, and trimming to [0.1, 0.9] is run as a labelled sensitivity.

**Sources.** https://docs.doubleml.org/stable/api/generated/doubleml.irm.DoubleMLPQ.html, https://doi.org/10.1111/ectj.12097.

### `dml_cvar`

**Use when.** The mean outcome above the τ quantile in one arm (an upper-tail mean, such as spending among the heaviest users).

**Versus.** `dml_pq`: Estimates potential-outcome CVaR rather than the potential-outcome quantile itself.

**Estimand.** C_τ(d) = q_τ(d) + E[(Y(d) − q_τ(d))_+]/(1 − τ), the upper-tail potential-outcome mean.

**Identification.** Conditional exchangeability and overlap.

**Run.** `method="dml_cvar"` → `DoubleML` `doubleml.DoubleMLCVAR` (0.11.4).

**Options.** Required: `learners`, `n_folds`, `quantile`, `score`, `seed`, `treatment`, `treatment_level`. Optional: `bootstrap`, `confidence_level`, `definitions`, `joint`, `n_rep`, `normalize_ipw`, `ps_processor_config`, `sample_splitting`, `trimming_rule`, `trimming_threshold`.

**Native arguments that change the result.** `n_folds` (Number of cross-fitting folds; default 5; top-level `n_folds` (at least 2)); `n_rep` (Repeated sample splittings; default 1; top-level `n_rep`); `treatment` (Selected potential outcome treatment state; default 1; top-level `treatment_level` (0 or 1)); `quantile` (Tail quantile level; default 0.5; top-level `quantile`); `normalize_ipw` (Normalize inverse propensity weights; default True; top-level `normalize_ipw`); `trimming_threshold` (Propensity-score threshold; deprecated; default 0.01; top-level; deprecated in favour of `ps_processor_config`).

**Returns.** `coef`: Orthogonal-score treatment parameter estimates; `se`: Standard errors for the target estimates; `pval`: P-values for target parameter estimates; `confint()`: Confidence interval estimates at the requested level.

**Checks before reporting.** Overlap: report the range of the saved out-of-fold propensities (`diagnostics.nuisance_predictions`); many values near 0 or 1 mean the estimate rests on few units, and trimming to [0.1, 0.9] is run as a labelled sensitivity.

**Sources.** https://docs.doubleml.org/stable/api/generated/doubleml.irm.DoubleMLCVAR.html, https://doi.org/10.1111/ectj.12097.

### `dml_ssm`

**Use when.** Outcomes are observed only for a selected group (wages only for the employed, survey attrition); `missing-at-random` when selection depends on observed D and X, `nonignorable` with an excluded selection instrument.

**Versus.** `dml_irm`: Models outcome attrition with an additional selection probability nuisance model.

**Estimand.** E[Y(1) − Y(0)].

**Identification.** Selection mechanism uses missing-at-random or nonignorable selection score specifications. `missing-at-random`: outcome and selection independent given D and X. `nonignorable`: an excluded instrument shifts selection without affecting the outcome.

**Run.** `method="dml_ssm"` → `DoubleML` `doubleml.DoubleMLSSM` (0.11.4). `selection` is a 0/1 column. `normalize_ipw=true` is refused on DoubleML 0.11.4; the nonignorable score refuses clustered inference and needs a regression `ml_g`.

**Options.** Required: `learners`, `n_folds`, `score`, `seed`, `selection`, `treatment`. Optional: `bootstrap`, `confidence_level`, `definitions`, `joint`, `n_rep`, `normalize_ipw`, `ps_processor_config`, `sample_splitting`, `trimming_rule`, `trimming_threshold`.

**Native arguments that change the result.** `n_folds` (Number of cross-fitting folds; default 5; top-level `n_folds` (at least 2)); `n_rep` (Repeated sample splittings; default 1; top-level `n_rep`); `score` (Missing-at-random or nonignorable selection score; default missing-at-random; top-level `score`); `ml_g` (Learner for E[Y|S,D,X]; default none; `learners.ml_g`); `ml_m` (Learner for P(D=1|X); default none; `learners.ml_m`); `ml_pi` (Learner for P(S=1|D,X); default none; `learners.ml_pi`); `normalize_ipw` (Normalize inverse propensity weights; default False; top-level; refused as true on 0.11.4); `trimming_threshold` (Propensity-score threshold; deprecated; default 0.01; top-level; deprecated in favour of `ps_processor_config`).

**Returns.** `coef`: Orthogonal-score treatment parameter estimates; `se`: Standard errors for the target estimates; `pval`: P-values for target parameter estimates; `confint()`: Confidence interval estimates at the requested level.

**Checks before reporting.** Selection overlap: range of the saved selection probabilities. Overlap: report the range of the saved out-of-fold propensities (`diagnostics.nuisance_predictions`); many values near 0 or 1 mean the estimate rests on few units, and trimming to [0.1, 0.9] is run as a labelled sensitivity. Nuisance fit: compare out-of-fold loss of at least two learner types from the saved predictions; an estimate that moves with the learner is reported with both.

**Sources.** https://docs.doubleml.org/stable/api/generated/doubleml.irm.DoubleMLSSM.html, https://doi.org/10.1111/ectj.12097.

## Generalized random forests

### `grf`

**Use when.** Binary or continuous treatment, many covariates, and the question is how the effect varies across units (by firm size, worker age), with the average or the effect on a subpopulation as the aggregate.

**Versus.** `grf_instrumental`: Uses conditional unconfoundedness instead of instrument Z. `grf_multi_arm`: Binary or continuous treatment rather than factor-valued multiple treatment arms. `causal_forest`: R generalized random forest rather than EconML DML-residualized CausalForestDML.

**Estimand.** τ(x) = E[Y(1) − Y(0) | X=x].

**Identification.** Binary W is unconfounded conditional on X for a causal treatment effect interpretation. Overlap in treatment given X.

**Run.** `method="grf"` → `grf::causal_forest`, `grf::predict.causal_forest`, `grf::average_treatment_effect` (2.6.1). `quantity="average"` (default) saves the aggregate and its standard error; `quantity="conditional"` saves out-of-bag τ(x) with pointwise intervals. `aggregation` sets `target.sample` and `method`.

**Options.** Required: `treatment`. Optional: `aggregation`, `args`, `columns`, `confidence_level`, `definitions`, `quantity`, `seed`.

**Native arguments that change the result.** `num.trees` (Number of trees in fitted forest; default 2000; via options.args); `sample.weights` (Observation-level training weights; default NULL; via options.args); `clusters` (Cluster membership for forest splitting and inference; default NULL; via options.args); `equalize.cluster.weights` (Weight sampled clusters equally; default FALSE; via options.args); `honesty` (Use disjoint samples for splitting and leaf estimation; default TRUE; via options.args); `min.node.size` (Minimum approximate node size; default 5; via options.args); `ci.group.size` (Number of trees grouped for variance estimation; default 2; via options.args); `tune.parameters` (Optional data-driven parameter tuning; default none; via options.args); `W.hat` (Supplied estimated treatment propensities; default NULL; via options.args); `target.sample` (Sample population for aggregate effect; default all; `aggregation.target.sample`); `method` (AIPW or TMLE for aggregate effect; default AIPW; `aggregation.method`).

**Returns.** `predictions`: Estimated conditional treatment effects from predict(); `variance.estimates`: Estimated prediction variances when estimate.variance=TRUE; `estimate`: Doubly robust aggregate treatment effect; `std.err`: Standard error for aggregated treatment effect.

**Checks before reporting.** Forest excess error: Additional trees may be needed if excess.error is not negligible. Overlap: range of the forest's propensity estimates. Pointwise intervals of τ(x) are not simultaneous; claims about who gains more rest on a comparison of groups fixed before results.

**Pitfalls.** Confidence interval estimation generally requires more trees than point prediction. Training weights must be independent of potential outcomes conditional on X.

**Sources.** https://grf-labs.github.io/grf/reference/causal_forest.html, https://grf-labs.github.io/grf/reference/average_treatment_effect.html, https://grf-labs.github.io/grf/reference/predict.causal_forest.html, https://doi.org/10.1214/18-AOS1709.

### `grf_instrumental`

**Use when.** An instrument and a treatment with effects that may vary across units; the target is the conditional IV effect, or the complier effect with binary treatment and instrument.

**Versus.** `grf`: Instrumental forest estimates conditional IV ratio; when Z=W it equals causal forest.

**Estimand.** τ(x) = Cov[Y,Z | X=x] / Cov[W,Z | X=x].

**Identification.** Relevance, exclusion and conditional instrument exogeneity. Monotonicity for the complier reading.

**Run.** `method="grf_instrumental"` → `grf::instrumental_forest`, `grf::predict.instrumental_forest`, `grf::average_treatment_effect` (2.6.1). `definitions.iv_estimand` is `conditional_late` (binary 0/1 treatment and instrument, with `definitions.compliance_population`) or `conditional_iv_ratio`. The average aggregate requires a binary instrument and uses AIPW over all units.

**Options.** Required: `definitions`, `instrument`, `treatment`. Optional: `aggregation`, `args`, `columns`, `confidence_level`, `quantity`, `seed`.

**Native arguments that change the result.** `num.trees` (Number of trees in fitted forest; default 2000; via options.args); `sample.weights` (Observation-level training weights; default NULL; via options.args); `clusters` (Cluster membership for forest splitting and inference; default NULL; via options.args); `equalize.cluster.weights` (Weight sampled clusters equally; default FALSE; via options.args); `honesty` (Use disjoint samples for splitting and leaf estimation; default TRUE; via options.args); `min.node.size` (Minimum approximate node size; default 5; via options.args); `ci.group.size` (Number of trees grouped for variance estimation; default 2; via options.args); `Z` (Instrumental variable vector; default none; top-level `instrument`); `Z.hat` (Supplied instrument conditional-mean estimates; default NULL; via options.args); `reduced.form.weight` (Weight on reduced-form objective in splitting; default 0; via options.args); `tune.parameters` (Optional parameter tuning; default none; via options.args).

**Returns.** `predictions`: Estimated conditional treatment effects from predict(); `variance.estimates`: Estimated prediction variances when estimate.variance=TRUE; `estimate`: Aggregate conditional IV effect estimate.

**Checks before reporting.** Strength of the instrument within covariate groups; a small conditional covariance makes τ(x) imprecise. Pointwise intervals of τ(x) are not simultaneous; claims about who gains more rest on a comparison of groups fixed before results.

**Pitfalls.** A small conditional covariance Cov[W,Z|X=x] weakens identification of the local IV ratio.

**Sources.** https://grf-labs.github.io/grf/reference/instrumental_forest.html, https://doi.org/10.1214/18-AOS1709.

### `grf_multi_arm`

**Use when.** Several treatment arms (alternative programme designs, price levels) and the question is which arm works better for whom, relative to a reference arm.

**Versus.** `grf`: Produces arm-k effects relative to factor baseline arm 1 instead of one binary contrast. `grf_survival`: Targets contemporaneous outcomes across factor levels, not horizon-specific survival contrasts.

**Estimand.** τ_k(x) = E[Y(k) − Y(1) | X=x].

**Identification.** Treatment W is unconfounded conditional on X.

**Run.** `method="grf_multi_arm"` → `grf::multi_arm_causal_forest`, `grf::predict.multi_arm_causal_forest`, `grf::average_treatment_effect` (2.6.1). `arms` lists distinct labels in order; the first is the reference. Every arm occurs in the fitted sample. The average aggregate uses AIPW over all units.

**Options.** Required: `arms`, `treatment`. Optional: `aggregation`, `args`, `columns`, `confidence_level`, `definitions`, `quantity`, `seed`.

**Native arguments that change the result.** `num.trees` (Number of trees in fitted forest; default 2000; via options.args); `sample.weights` (Observation-level training weights; default NULL; via options.args); `clusters` (Cluster membership for forest splitting and inference; default NULL; via options.args); `equalize.cluster.weights` (Weight sampled clusters equally; default FALSE; via options.args); `honesty` (Use disjoint samples for splitting and leaf estimation; default TRUE; via options.args); `min.node.size` (Minimum approximate node size; default 5; via options.args); `ci.group.size` (Number of trees grouped for variance estimation; default 2; via options.args); `W` (Treatment factor with baseline defined by first level; default none; top-level `treatment` with `arms` order); `W.hat` (Treatment propensity matrix; default NULL; via options.args).

**Returns.** `predictions`: Estimated conditional treatment effects from predict(); `variance.estimates`: Estimated prediction variances when estimate.variance=TRUE.

**Checks before reporting.** Treatment factor baseline: First factor level determines reference arm. Overlap for every arm. Report effects for every non-reference arm. Pointwise intervals of τ(x) are not simultaneous; claims about who gains more rest on a comparison of groups fixed before results.

**Pitfalls.** Multiple outcomes must be on the same scale.

**Sources.** https://grf-labs.github.io/grf/reference/multi_arm_causal_forest.html, https://doi.org/10.1214/18-AOS1709.

### `grf_survival`

**Use when.** Time-to-event outcomes with right censoring (time to re-employment, firm exit); the target is the effect on restricted mean time to a horizon or on survival at that horizon.

**Versus.** `grf`: Estimates restricted survival-time or survival-probability treatment contrasts rather than outcomes without censoring. `grf_multi_arm`: Targets two treatment conditions with time-to-event censoring rather than multi-arm outcomes.

**Estimand.** τ(x) = E[min(T(1),horizon) − min(T(0),horizon) | X=x].

**Identification.** Conditional exchangeability and overlap. Censoring independent of event times given treatment and covariates. Follow-up reaches the horizon.

**Run.** `method="grf_survival"` → `grf::causal_survival_forest`, `grf::predict.causal_survival_forest`, `grf::average_treatment_effect` (2.6.1). `status` is 1 for an observed event and 0 for censoring; `args.target` and `args.horizon` are required, with `definitions.time_unit` and `definitions.censoring`.

**Options.** Required: `definitions`, `status`, `treatment`. Optional: `aggregation`, `args`, `columns`, `confidence_level`, `quantity`, `seed`.

**Native arguments that change the result.** `num.trees` (Number of trees in fitted forest; default 2000; via options.args); `sample.weights` (Observation-level training weights; default NULL; via options.args); `clusters` (Cluster membership for forest splitting and inference; default NULL; via options.args); `equalize.cluster.weights` (Weight sampled clusters equally; default FALSE; via options.args); `honesty` (Use disjoint samples for splitting and leaf estimation; default TRUE; via options.args); `min.node.size` (Minimum approximate node size; default 5; via options.args); `ci.group.size` (Number of trees grouped for variance estimation; default 2; via options.args); `D` (Event indicator: zero censored, one observed failure; default none; top-level `status`); `target` (Restricted mean survival time or survival probability difference; default RMST; via options.args; required); `horizon` (Required horizon defining the treatment-effect estimand; default NULL; via options.args; required); `failure.times` (Selected survival-time grid; default NULL; via options.args).

**Returns.** `predictions`: Estimated conditional treatment effects from predict(); `variance.estimates`: Estimated prediction variances when estimate.variance=TRUE.

**Checks before reporting.** The horizon lies inside the follow-up of both arms; report the share censored before it. Overlap: range of the forest's propensity estimates. Pointwise intervals of τ(x) are not simultaneous; claims about who gains more rest on a comparison of groups fixed before results.

**Pitfalls.** Sample weights are not used during survival splitting.

**Sources.** https://grf-labs.github.io/grf/reference/causal_survival_forest.html, https://doi.org/10.1214/18-AOS1709.

### `causal_forest`

**Use when.** A quick Python estimate of heterogeneous effects of a binary treatment with fixed settings; for clusters, weights, tuning or other targets use `grf`.

**Versus.** `grf`: DML-cross-fitted nuisance residualization with EconML forest, instead of grf::causal_forest.

**Estimand.** E[(Y − E[Y|X,W] − ⟨θ(x),T−E[T|X,W]⟩ − β(x))(T;1) | X=x] = 0.

**Identification.** Conditional exchangeability and overlap.

**Run.** `method="causal_forest"` → `econml.dml.CausalForestDML.fit`, `.effect_inference`, `.ate_inference` (0.17.0). `trees` is at least 40 and divisible by 4, `min_leaf` at least 2, and each arm has at least 10 units. Requires `inference={"type":"forest"}`. The saved aggregate variance is an upper bound.

**Options.** Required: `min_leaf`, `seed`, `treatment`, `trees`. Optional: None.

**Native arguments that change the result.** `discrete_treatment` (Declare treatment categorical; default False; fixed by the runner at True); `cv` (First-stage cross-fitting scheme; default 2; fixed by the runner: stratified two-fold); `n_estimators` (Forest tree count; default 100; top-level `trees`); `min_samples_leaf` (Minimum examples at each leaf; default 5; top-level `min_leaf`); `honest` (Split and estimation samples separated within each tree; default True; fixed by the runner); `inference` (Enable confidence interval inference; default True; fixed by the runner); `model_t` (Treatment nuisance prediction model; default auto; fixed by the runner: random-forest classifier, 50 trees); `model_y` (Outcome nuisance prediction model; default auto; fixed by the runner: random-forest regressor, 50 trees).

**Returns.** `effect_inference()`: Conditional treatment-effect estimates with uncertainty intervals; `ate_inference()`: Average treatment effect on supplied X with uncertainty; `stderr_mean`: Estimated standard error of population-average mean effect.

**Checks before reporting.** Overlap: at least 10 units per arm is the runner's floor, not evidence of overlap. Individual CATE intervals are pointwise.

**Sources.** https://www.pywhy.org/EconML/_autosummary/econml.dml.CausalForestDML.html, https://doi.org/10.1080/01621459.2017.1319839.

## Meta-learners and targeted estimation

### `metalearner`

**Use when.** Conditional effects of a binary treatment from a chosen learner family (S, T, X, R or DR), with the average effect from AIPW pseudo-outcomes; useful to compare CATE fits across learners.

**Versus.** `tmle`: Meta-learners produce learner-specific CATE predictions; ATE uses AIPW pseudo-outcomes. `causal_forest`: Uses selectable S/T/X/R/DR meta-learners instead of forest moment-solving.

**Estimand.** φ_i = μ̂₁(X_i) − μ̂₀(X_i) + D_i(Y_i−μ̂₁(X_i))/ê(X_i) − (1−D_i)(Y_i−μ̂₀(X_i))/(1−ê(X_i)); ÂTE=mean_i φ_i.

**Identification.** Conditional exchangeability and overlap.

**Run.** `method="metalearner"` → `StatsPAI` `statspai.metalearners.metalearners.metalearner` (git:ddb3b45f2d3fc649ea794aa15f8989bb10f8e543). Inference is `official` or `cluster`; `learners` maps `outcome_model`, `propensity_model` and `cate_model`, and `fold` binds fixed fold labels.

**Options.** Required: `treatment`. Optional: `args`, `definitions`, `fold`, `learners`, `seed`, `weights`.

**Native arguments that change the result.** `learner` (Meta-learner family: S/T/X/R/DR; default dr; via options.args); `n_folds` (Cross-fitting fold count; default 5; via options.args; replaced by top-level `fold` labels); `outcome_model` (Prediction model for outcomes; default None; `learners.outcome_model`); `propensity_model` (Treatment propensity learner; default None; `learners.propensity_model`); `cate_model` (CATE prediction learner; default None; `learners.cate_model`); `weights` (Optional observation weighting; default None; top-level `weights`); `cluster` (Optional clustered inference index; default None; from `inference.cluster`).

**Returns.** `estimate`: AIPW treatment effect point estimate; `se`: Standard error for ATE; `ci`: Confidence interval; `model_info`: Learner-specific CATE predictions and nuisance metadata.

**Checks before reporting.** Propensity clipping frequency: Warning when more than 5% of scores are clipped. Report the propensity clipping warning and its share. The reported interval is for the AIPW average effect; CATE summaries carry no interval.

**Pitfalls.** The AIPW standard error does not quantify uncertainty of the learner-specific cate_mean. n_bootstrap is deprecated and ignored as of StatsPAI v1.11.4.

**Sources.** https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/metalearners/metalearners.py, https://doi.org/10.1111/ectj.12097.

### `tmle`

**Use when.** Binary treatment and the average effect (or ATT, ATC, risk ratio) with a targeted, bounded estimator; useful when outcomes are bounded or rates.

**Versus.** `metalearner`: Targets an updated outcome regression using a fluctuation submodel instead of meta-learner CATE prediction.

**Estimand.** ATE = E[Q*(1,W) − Q*(0,W)].

**Identification.** TMLE is doubly robust: consistent if either outcome nuisance Q or propensity nuisance g is correctly specified. Conditional exchangeability and overlap.

**Run.** `method="tmle"` → `StatsPAI` `statspai.tmle.tmle.tmle` (git:ddb3b45f2d3fc649ea794aa15f8989bb10f8e543). Inference is `official` or `cluster`; `learners` maps `outcome_model` and `propensity_model` to the libraries; `seed` sets `random_state`.

**Options.** Required: `treatment`. Optional: `args`, `definitions`, `fold`, `learners`, `seed`, `weights`.

**Native arguments that change the result.** `estimand` (Target quantity, including ATE/ATT/ATC and risk measures; default ATE; via options.args); `n_folds` (Cross-fitting fold count; default 5; via options.args); `propensity_bounds` (Allowed range for estimated propensity; default (0.025, 0.975); via options.args); `outcome_library` (Outcome prediction model library; default None; `learners.outcome_model`); `propensity_library` (Propensity prediction model library; default None; `learners.propensity_model`); `se_method` (Influence-function or bootstrap standard error calculation; default influence; via options.args); `n_boot` (Bootstrap iterations when bootstrap SE selected; default 200; via options.args); `cluster` (Optional clustered inference index; default None; from `inference.cluster`).

**Returns.** `estimate`: TMLE parameter estimate; `se`: Influence-function or bootstrap standard error; `ci`: Confidence interval; `model_info`: Nuisance models and targeting metadata.

**Checks before reporting.** Propensity clipping fraction: Warning when propensity truncation affects more than 5% of observations. Report the share of propensities truncated at the bounds; above 5% the estimate depends on the bounds. Overlap: report the range of the saved out-of-fold propensities; many values near 0 or 1 mean the estimate rests on few units, and trimming to [0.1, 0.9] is run as a labelled sensitivity.

**Pitfalls.** Extreme estimated propensities are truncated to propensity_bounds.

**Sources.** https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/tmle/tmle.py, https://doi.org/10.1093/biomet/asn055.

## Treatment rules

### `policy_tree`

**Use when.** Choose a simple treatment rule (who gets the programme) from covariates and evaluate its gain on held-out data, with a binary treatment and known assignment probabilities.

**Versus.** `policy_learning`: PolicyTree selects an assignment rule, whereas off-policy estimators evaluate a supplied rule.

**Estimand.** 1/n ∑_i ∑_j a_j(X_i) * y_ij.

**Identification.** Known assignment probabilities (`propensity`) and overlap in the training data.

**Run.** `method="policy_tree"` → `econml.policy.PolicyTree.fit`, `econml.policy.DRPolicyTree.fit`, `statspai.policy_learning.ope.doubly_robust`, `ips` (econml 0.17.0; StatsPAI git:ddb3b45f2d3fc649ea794aa15f8989bb10f8e543). Requires `inference={"type":"policy"}`. The four-option form learns a depth-2 `DRPolicyTree` on the training partition and evaluates the inverse-probability-weighted gain over treating no one on the evaluation partition. Adding `options.policy` switches to `policy_learning`.

**Options.** Required: `partition`, `propensity`, `seed`, `treatment`. Optional: None.

**Native arguments that change the result.** `max_depth` (Maximum number of split levels; default None; fixed by the runner at 2); `min_samples_leaf` (Minimum leaf sample count; default 5; fixed by the runner at 20); `min_samples_split` (Minimum observations for an internal split; default 10; package default); `honest` (Use disjoint samples for splitting and reward estimation; default True; fixed by the runner at True); `min_balancedness_tol` (Balancedness tolerance of policy splits; default 0.45; package default).

**Returns.** `predict()`: Selected treatment arm per covariate row; `predict_value()`: Predicted value of selected treatment arm; `value`: Off-policy evaluation estimate via auxiliary StatsPAI estimators.

**Checks before reporting.** Gain is evaluated only on the evaluation partition. Report the treated share under the rule and the propensity range.

**Sources.** https://www.pywhy.org/EconML/_autosummary/econml.policy.PolicyTree.html, https://doi.org/10.3982/ECTA15732.

### `policy_learning`

**Use when.** Several arms, costs or constraints, and the question is which rule maximizes welfare (outcome or net benefit) and what its value is, with known or estimated propensities.

**Versus.** `policy_tree`: Evaluates a supplied policy on logged data rather than optimizing a new assignment tree.

**Estimand.** V = mean_i[∑_a π_e(a|X_i)Q(X_i,a) + w_i(R_i−Q(X_i,A_i))].

**Identification.** Known or consistently estimated assignment probabilities, with overlap for every arm.

**Run.** `method="policy_tree"` → `statspai.policy_learning.ope.doubly_robust`, `statspai.policy_learning.ope.ips` (git:ddb3b45f2d3fc649ea794aa15f8989bb10f8e543). Add `options.policy` (arms, baseline, `value_method` ipw or aipw, propensity, evaluation target) and `inference={"type":"policy"}`; see [multi-arm policy learning](policy.md#multi-arm-policy-learning-and-evaluation). Tree defaults: depth 2, minimum leaf 10, honest false, set in `policy.tree`.

**Options.** Required: `partition`, `policy`, `seed`, `treatment`. Optional: `weights`.

**Native arguments that change the result.** `pi_target` (Evaluation policy assigning action probabilities; default none; the learned rule on the evaluation partition); `pi_behavior` (Logged behavior action probabilities; default None; `policy.propensity` (known columns or estimated)); `q_hat` (Supplied potential reward regression; default None; fitted on the training partition); `clip` (Maximum importance weight; default 50.0; set by the runner); `n_folds` (Cross-fitting folds for reward model; default 1; set by the runner); `alpha` (Confidence interval test size; default 0.05; from `inference.confidence_level`).

**Returns.** `value`: Estimated target-policy reward; `se`: Estimated standard error of policy value; `ci`: Policy value confidence interval; `diagnostics`: Importance-weight diagnostics.

**Checks before reporting.** Importance-weight effective sample size: Read diagnostics['ess']; no threshold is specified. Fallback to uniform propensities: Review diagnostics['propensity_fallback'] after behavior-model failure. Estimated propensities require `value_method="aipw"`. A fallback to uniform propensities is a failed check.

**Pitfalls.** Behavior-model failure can cause propensity fallback to uniform 1/K with a ConvergenceWarning.

**Sources.** https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/policy_learning/ope.py, https://doi.org/10.3982/ECTA15732.

## Post-estimation quantities

### `marginaleffects`

**Use when.** Translate a fitted model into quantities on the outcome scale (average slopes, predicted differences between scenarios, elasticities) for the decision of section 6.

**Versus.** `dml_plr`: Reports post-estimation functions of a fitted model rather than an orthogonal-score treatment coefficient.

**Estimand.** ∂E[Y|X=x]/∂x_j; average slopes aggregate these model-based derivatives over newdata.

**Identification.** A causal reading inherits the identification of the fitted model.

**Run.** `method="marginaleffects"` → `marginaleffects::slopes`, `avg_slopes`, `predictions`, `avg_predictions`, `comparisons`, `avg_comparisons` (1.0.0.10005). `data` is the saved fit; `function` names the call; `evaluation_data` and `evaluation_id` supply the grid.

**Options.** Required: `function`. Optional: `args`, `columns`, `definitions`, `evaluation_data`, `evaluation_id`, `seed`.

**Native arguments that change the result.** `newdata` (Predictor grid or observations at which to evaluate fitted effects; default NULL; top-level `evaluation_data`); `variables` (Focal regressors for slopes and contrasts; default NULL; via options.args); `type` (Model-specific response scale to predict; default NULL; via options.args); `slope` (Derivative or elasticity functional for slopes; default dydx; via options.args); `by` (Grouping or aggregation for slopes; default FALSE (slopes); TRUE (avg_slopes); via options.args); `vcov` (Coefficient covariance matrix or estimator for uncertainty; default TRUE; via options.args); `wts` (Weighting for aggregation; default FALSE; via options.args); `conf_level` (Confidence level; default 0.95; via options.args).

**Returns.** `estimate`: Model-based prediction, contrast, or slope estimate; `std.error`: Delta-method standard error when requested; `conf.low`: Lower confidence limit; `conf.high`: Upper confidence limit.

**Checks before reporting.** State the evaluation grid and the scale (`type`). Averages over the sample and effects at the mean differ in nonlinear models; report which one.

**Pitfalls.** Slopes for categorical or binary variables automatically use prediction comparisons. If newdata=NULL, retrieving model data from the environment may yield unexpected values after model-data changes.

**Sources.** https://marginaleffects.com/man/r/slopes.html.

