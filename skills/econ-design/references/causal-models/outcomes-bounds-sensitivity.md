# Outcome models, decompositions, bounds, spillovers and sensitivity

Method cards for selection, censoring, duration, decomposition, bunching, distributional, partial-identification, network and spatial, sensitivity, mediation and specification-curve methods run by `python3 skills/econ-data/scripts/research_causal.py run SPEC.json --output RESULT.json`. The shared specification fields are in [specification and result](contract.md#specification-and-result); runner details are in [outcomes](outcomes.md), [basic](basic.md), [extensions](extensions.md), [contrasts](contrasts.md), [networks](networks.md) and [inference](inference.md). R methods take `inference={"type":"official"}` and native arguments through `options.args`; sensitivity methods accept a saved result in `data` with `input="saved_result"`. Each card gives when to use the method, how it differs from its neighbours, the estimand, the identifying conditions, the runner call and options (checked against the code), the native arguments that change the result and how they are set, the returns, the checks before reporting, documented pitfalls and sources.

## Which method

| Data, question and target | Method |
| --- | --- |
| Outcome observed only for a selected group, with an exclusion | `heckman`; without normality or exclusion, `lee_bounds` |
| Outcome censored at a known lower limit | `tobit` |
| Time to event with censoring: hazard ratio | `survival`; duration acceleration `survival_aft`; description `survival_km` |
| Mean gap between two groups: characteristics versus returns | `oaxaca` |
| Distribution or quantile gap between groups: composition | `dfl` |
| Aggregate rates over cells: rates versus shares | `kitagawa` |
| Which added controls move a coefficient | `gelbach` |
| Response to a kink or notch in a schedule | `bunching` |
| Effects on unconditional quantiles: population or treated | `qte`, `qtt` |
| Covariate effects on a conditional quantile | `quantile` |
| Share below a policy threshold by treatment | `distribution_effect` |
| Bounds from outcome support, monotone response or selection | `manski_bounds` |
| Bounds under differential attrition or observation | `lee_bounds` |
| Bounds with a binary instrument, treatment and outcome | `balke_pearl` |
| Spillovers in a randomized network: exposure contrasts | `network_exposure`; linear exposure `network_spillover` |
| Outcome feedback among neighbours | `spatial_lag` |
| Strength of an omitted confounder that would overturn a regression | `sensitivity_cinelli` (partial R²), `sensitivity_oster` (coefficient stability) |
| Strength of an omitted confounder for a ratio estimate | `sensitivity_evalue` |
| Share of an effect working through an observed channel | `mediation` |
| How the estimate varies over a declared set of specifications | `specification_curve` |

## Selection, censoring and duration

### `heckman`

**Use when.** The outcome is observed only for a selected group (wages only for workers, prices only for traded goods) and a variable shifts selection without entering the outcome; the target is the outcome equation for the whole population.

**Versus.** `tobit`: Models endogenous selection into outcome observation rather than fixed censoring of an observed outcome.

**Estimand.** Selection-corrected continuous-outcome regression parameters from a Heckman-type selection model.

**Identification.** A two-equation sample selection model uses a binary selection indicator. The outcome equation is observed only for the selected group in a tobit-2 model. Selection and outcome errors are jointly normal. At least one selection regressor is excluded from the outcome equation; without it, identification rests on the normal functional form alone.

**Run.** `method="heckman"` → `sampleSelection::selection` (1.2.16). `selection` is the 0/1 indicator and `selection_regressors` the selection equation; selection regressors absent from `regressors` are the exclusions (saved as `excluded_selection_regressors`). Requires `inference={"type":"official"}`.

**Options.** Required: `definitions`, `estimation_method`, `selection`, `selection_regressors`. Optional: `args`, `columns`, `confidence_level`, `seed`.

**Native arguments that change the result.** `selection` (Formula for the selection equation; default none; built from `selection` and `selection_regressors`); `outcome` (Formula for the outcome equation; default none; built from the outcome and `regressors`); `method` (Maximum likelihood or Heckman two-step estimation; default ml; top-level `estimation_method`: `ml` or `2step`); `type` (Tobit-2, tobit-5 or treatment-effects model type; default NULL; fixed by the runner at 2); `weights` (Prior weights supported for type-2 models; default NULL; fixed by the runner at none).

**Returns.** `coefficients`: Estimated selection and outcome model parameters; `vcov`: Coefficient variance–covariance matrix.

**Checks before reporting.** Name each excluded selection regressor with its economic reason and report its selection-equation coefficient. Report the error correlation ρ and the selection-correction term. Compare with `lee_bounds`, which needs neither normality nor an exclusion.

**Pitfalls.** Prior weights are currently supported only for type-2 models.

**Sources.** https://search.r-project.org/CRAN/refmans/sampleSelection/html/selection.html, https://doi.org/10.2307/1912352.

### `tobit`

**Use when.** The outcome piles up at a known lower limit that censors a latent continuous quantity (a detection limit, a reporting floor); the target is the latent-outcome coefficients.

**Versus.** `heckman`: Censoring is a known measurement limit; Heckman models whether the outcome is observed.

**Estimand.** Regression coefficients for an underlying Gaussian continuous outcome subject to left censoring.

**Identification.** The latent outcome is normal with constant variance given X. Censoring occurs at the known value `lower`.

**Run.** `method="tobit"` → `statsmodels; scipy` `statsmodels.base.model.GenericLikelihoodModel.fit (custom LeftCensoredNormal)` (statsmodels==0.14.6; scipy==1.17.0). Requires `inference={"type":"likelihood"}`, censored and uncensored observations, and no outcome below `lower`. The fit starts from OLS and uses BFGS with at most 2000 iterations.

**Options.** Required: `lower`. Optional: None.

**Native arguments that change the result.** `method` (Optimizer selected by the custom maximum-likelihood fit; default nm; fixed by the runner at bfgs); `start_params` (Initial parameter guess for likelihood optimization; default None; fixed by the runner: OLS coefficients and the log standard deviation).

**Returns.** `params`: Fitted latent-response regression and log-scale parameters; `bse`: Estimated standard errors from likelihood results.

**Checks before reporting.** Report the share of censored observations. Coefficients refer to the latent outcome; effects on the observed outcome or on the probability of a positive value are different quantities. When zeros are chosen corners rather than censored values, the latent-outcome reading needs that model; state which applies.

**Sources.** https://www.statsmodels.org/v0.14.6/dev/generated/statsmodels.base.model.GenericLikelihoodModel.fit.html.

### `survival`

**Use when.** Time to an event with right censoring (unemployment spells, firm survival, time to adoption) and the target is a hazard ratio.

**Versus.** `survival_aft`: Parameterizes proportional hazards rather than a parametric log-survival-time acceleration. `survival_km`: Models covariate-specific hazard ratios instead of an unadjusted nonparametric survival curve.

**Estimand.** Regression coefficients in a proportional hazards model estimated by partial likelihood.

**Identification.** Covariate hazard ratios are constant over event time under proportional hazards.

**Run.** `method="survival"` → `statsmodels` `statsmodels.duration.hazard_regression.PHReg` (0.14.6). Inference is `{"type":"official"}` (likelihood) or `{"type":"cluster","cluster":...}` (group sandwich). The fit uses Newton steps; strata without events and rows outside every risk set leave the fit and are saved in `excluded_engine_ids`.

**Options.** Required: `status`, `ties`. Optional: `confidence_level`, `definitions`, `effect_scale`, `entry`, `maxiter`, `offset`, `strata`, `tol`.

**Native arguments that change the result.** `status` (Indicator of observed failure rather than censoring; default None; top-level `status`); `entry` (Left truncation or delayed entry time; default None; top-level `entry`); `ties` (Handling of tied observed failures; default breslow; top-level `ties`); `strata` (Separate baseline hazards across strata; default None; top-level `strata`); `groups` (Cluster labels for robust covariance in fit(); default None; from `inference.cluster`).

**Returns.** `params`: Log hazard-ratio parameter estimates; `bse`: Estimated parameter standard errors; `baseline_cumulative_hazard`: Estimated baseline cumulative hazard by stratum.

**Checks before reporting.** Number of events per covariate. Proportional hazards: log-log survival curves by group or time-interacted covariates. Convergence and finite inference.

**Sources.** https://www.statsmodels.org/v0.14.6/generated/statsmodels.duration.hazard_regression.PHReg.html, https://www.statsmodels.org/v0.14.6/generated/statsmodels.duration.hazard_regression.PHReg.fit.html.

### `survival_aft`

**Use when.** Time-to-event outcome where effects are read as stretching or shrinking durations, and a parametric duration distribution is acceptable.

**Versus.** `survival`: Parametric log-duration coefficients replace Cox proportional-hazards coefficients. `survival_km`: Uses a specified parametric survival family and covariates instead of a nonparametric survivor estimate.

**Estimand.** Parameters of an accelerated failure-time model for log event durations, including log(sigma).

**Identification.** Survival times follow the selected Weibull, exponential, log-normal, or log-logistic parametric distribution.

**Run.** `method="survival_aft"` → `StatsPAI` `statspai.survival.models.survreg` (1.43.1). Inference is `official` or `cluster`.

**Options.** Required: `status`. Optional: `args`, `definitions`, `entry`, `group`, `weights`.

**Native arguments that change the result.** `dist` (Distribution of survival times; default weibull; via options.args); `robust` (Model-based, sandwich, or clustered standard errors; default nonrobust; via options.args); `cluster` (Cluster membership defining robust sandwich covariance; default None; from `inference.cluster`); `frailty` (Optional gamma multiplicative hazard heterogeneity; default None; via options.args).

**Returns.** `params`: Estimated log-time regression and log(sigma) coefficients; `diagnostics`: Log-likelihood of observed event durations; `model_info`: Distribution metadata and log-time likelihood.

**Checks before reporting.** Gamma frailty likelihood-ratio test: The variance-zero null is at the parameter boundary; source uses a halved p-value. Fit under at least two distributions and report how the coefficients change. Durations must be positive.

**Pitfalls.** The duration and log-duration likelihoods differ by the sum of log event times.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/survival/models.py.

### `survival_km`

**Use when.** Describe survival over time by group before modelling, with censoring, delayed entry or weights.

**Versus.** `survival`: Directly estimates S(t), without a Cox log-hazard coefficient. `survival_aft`: No Weibull or log-normal distribution is specified for event times.

**Estimand.** Kaplan–Meier nonparametric survival function S(t) at observed event times.

**Identification.** Censoring is independent for the interpretation of the Kaplan–Meier survival estimate.

**Run.** `method="survival_km"` → `StatsPAI` `statspai.survival.models.kaplan_meier` (1.43.1).

**Options.** Required: `status`. Optional: `args`, `definitions`, `entry`, `group`, `weights`.

**Native arguments that change the result.** `group` (Grouping column for distinct survivor curves; default None; top-level `group`); `weights` (Case weights, including inverse-probability weights; default None; top-level `weights`); `start` (Delayed-entry time column; default None; top-level `entry`); `conf_type` (Confidence-interval transformation; default log-log; via options.args); `se_method` (Greenwood, jackknife, or Xie–Liu variance; default None; via options.args).

**Returns.** `survival_table`: Time-specific survival, risk counts, standard errors, and confidence intervals; `median_survival`: Median time at which survival reaches one-half.

**Checks before reporting.** At-risk counts and event counts: Inspect time-specific n_risk and n_event entries in survival_table. Report the median survival with its interval, and the curve only where the number at risk is adequate.

**Pitfalls.** Plain confidence intervals must be truncated to [0,1]; log-log confidence intervals stay inside the probability interval.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/survival/models.py.

## Decompositions

### `oaxaca`

**Use when.** A mean gap between two groups (wages by gender, productivity by firm type) and the question is how much is accounted for by differences in characteristics versus differences in returns.

**Versus.** `dfl`: Decomposes a regression mean gap instead of a propensity-reweighted distributional statistic. `gelbach`: Explains an across-group outcome gap instead of an across-specification coefficient change.

**Estimand.** Group mean outcome gap decomposed into explained and unexplained components (twofold), or endowment, coefficient, and interaction components (threefold).

**Identification.** Linear group-specific regressions; the decomposition is accounting under the chosen reference coefficients, causal only under further assumptions.

**Run.** `method="oaxaca"` → `statsmodels.stats.oaxaca.OaxacaBlinder.two_fold`, `.three_fold` (0.14.6). Requires `group`, `group_order`, `decomposition` (`two_fold` or `three_fold`) and `bootstrap` with `n`, `conf` and `seed`; `inference={"type":"official"}` (row bootstrap). The runner sets `hasconst=True`.

**Options.** Required: `bootstrap`, `decomposition`, `group`, `group_order`. Optional: `definitions`, `submitted_weight`, `two_fold_type`.

**Native arguments that change the result.** `bifurcate` (Column separating observations into two groups; default none; top-level `group`, ordered by `group_order`); `two_fold_type` (Reference coefficient weighting for twofold decomposition; default pooled; top-level `two_fold_type` (pooled, nuemark, cotton, reimers or self_submitted with `submitted_weight`)); `std` (Whether to calculate bootstrap standard errors; default False; set by `bootstrap`); `n` (Bootstrap replications when std=True; default None; `bootstrap.n`); `conf` (Bootstrap confidence level; default None; `bootstrap.conf`).

**Returns.** `params`: Twofold explained, unexplained, and gap effects, or threefold endowments, coefficients, interaction, and gap; `std`: Bootstrap uncertainties when requested.

**Checks before reporting.** Constant-column specification: Check hasconst against the actual regressors; incorrect setting produces incorrect values. Report the reference coefficients; the unexplained part changes with `two_fold_type`. Detailed contributions of a categorical variable depend on the omitted category. The unexplained part is not a measure of discrimination without further assumptions.

**Pitfalls.** Setting hasconst incorrectly yields incorrect decomposition estimates.

**Sources.** https://raw.githubusercontent.com/statsmodels/statsmodels/v0.14.6/statsmodels/stats/oaxaca.py, https://doi.org/10.1016/S0169-7218(11)00407-2.

### `dfl`

**Use when.** A gap in the whole distribution or a quantile between two groups (wage inequality across periods) and the question is how much composition explains, by reweighting one group to the other's covariates.

**Versus.** `oaxaca`: Reweights distributions through propensity scores rather than group-specific linear coefficient projections. `kitagawa`: Uses propensity-reweighted covariate distributions instead of observed categorical cell-share arithmetic.

**Estimand.** Observed group-statistic gap split into counterfactual covariate-composition and outcome-structure components.

**Identification.** Both groups have overlapping covariate support for propensity-score reweighting.

**Run.** `method="dfl"` → `StatsPAI` `statspai.decomposition.dfl.dfl_decompose` (1.43.1).

**Options.** Required: `group`. Optional: `args`, `definitions`, `weights`.

**Native arguments that change the result.** `stat` (Distributional statistic to decompose; default mean; via options.args); `tau` (Quantile target when stat=quantile; default 0.5; via options.args); `reference` (Direction of counterfactual reweighting; default 0; via options.args); `weights` (Optional sampling weights; default None; top-level `weights`); `trim` (Propensity-score clipping threshold; default 0.001; via options.args); `inference` (Analytical, bootstrap, or no inference; default analytical; via options.args); `n_boot` (Bootstrap repetition count; default 299; via options.args).

**Returns.** `gap`: Unadjusted between-group statistic difference; `composition`: Change attributed to covariate-distribution composition; `structure`: Residual structural statistic difference.

**Checks before reporting.** Overlap after propensity weighting: Review the propensity clipping and feasible counterfactual support. Report the share of clipped propensities.

**Pitfalls.** reference=0 reverses counterfactual substitution semantics used by Machado–Mata and Melly methods.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/decomposition/dfl.py, https://doi.org/10.2307/2171954, https://doi.org/10.1016/S0169-7218(11)00407-2.

### `kitagawa`

**Use when.** Aggregate rates of two populations over categorical cells (mortality by age, unemployment by education) and the question is how much is due to cell rates versus cell shares.

**Versus.** `dfl`: Partitions aggregate rates using observed category shares and cell rates, without propensity-score reweighting. `oaxaca`: Decomposes category-specific rates and group composition rather than fitted regression coefficients.

**Estimand.** Aggregate rate gap = rate effect + composition effect + interaction.

**Identification.** An accounting identity; no behavioural assumption.

**Run.** `method="kitagawa"` → `StatsPAI` `statspai.decomposition.kitagawa.kitagawa_decompose` (1.43.1).

**Options.** Required: `by`, `group`. Optional: `args`, `definitions`, `weights`.

**Native arguments that change the result.** `by` (Category variables defining cells; default none; top-level `by`); `weights` (Cell population weights for pre-aggregated data; default None; top-level `weights`); `normalize` (Rate-effect reference population; default symmetric; via options.args).

**Returns.** `gap`: Overall aggregate rate difference; `rate_effect`: Contribution of category-specific rates; `composition_effect`: Contribution of population composition; `interaction`: Residual interaction term in exact decomposition.

**Checks before reporting.** Every adopted cell has both groups' rates; report the interaction term.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/decomposition/kitagawa.py.

### `gelbach`

**Use when.** A coefficient moves when controls are added, and the question is which added controls account for the move.

**Versus.** `oaxaca`: Decomposes change in a coefficient across nested regressions instead of an outcome-level gap between groups.

**Estimand.** Change in a chosen regression coefficient when controls enter, allocated to individual added regressors.

**Identification.** Base and augmented regressions refer to the same sample and a full-rank linear projection.

**Run.** `method="gelbach"` → `StatsPAI` `statspai.decomposition.oaxaca.gelbach` (1.43.1). `regressors` are the base regressors; `added_regressors` and `var_of_interest` are required; `fixed_effects` are absorbed in both regressions.

**Options.** Required: `added_regressors`, `var_of_interest`. Optional: `args`, `definitions`, `fixed_effects`, `weights`.

**Native arguments that change the result.** `base_x` (Regressors in the short specification; default none; the specification's `regressors`); `added_x` (Additional regressors in the full specification; default none; top-level `added_regressors`); `var_of_interest` (Original coefficient being decomposed; default None; top-level `var_of_interest`); `vce` (Robust or model-based covariance; default robust; via options.args); `absorb` (Fixed effects included in both regressions; default None; top-level `fixed_effects`); `cluster` (Cluster-robust standard errors; default None; from `inference.cluster`); `shapley` (Compute optional Shapley order-averaged contributions; default False; via options.args).

**Returns.** `decomposition`: Per-added-variable contributions to coefficient change; `total_change`: Sum of added-variable coefficient changes; `vcov`: Joint covariance of contributions.

**Checks before reporting.** Each contribution is conditional on the full set of added controls; unlike adding controls one at a time, it does not depend on order.

**Pitfalls.** Shapley decomposition requires up to 2^k subset regressions and is capped at 12 added variables.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/decomposition/oaxaca.py, https://doi.org/10.1086/683668.

## Bunching

### `bunching`

**Use when.** Agents respond to a kink or notch in a schedule (a tax bracket, a benefit threshold), so excess mass at the threshold measures the behavioural response and, with the rates, an elasticity.

**Estimand.** Observed excess mass at a kink or notch relative to a fitted smooth counterfactual density, with optional elasticity.

**Identification.** Without the kink the density is smooth around the threshold. Agents can adjust the running variable.

**Run.** `method="bunching"` → `bunching::bunchit` (0.8.6). Requires `seed` and `definitions.running_unit`; native kink, window, polynomial, exclusion, tax-rate and bootstrap arguments go in `args`. The saved result keeps bins, counts, counterfactual and bootstrap output.

**Options.** Required: `definitions`, `seed`. Optional: `args`, `columns`, `quantity`.

**Native arguments that change the result.** `zstar` (Location of the bunching point; default none; via options.args); `binwidth` (Width of histogram bins; default none; via options.args); `bins_l` (Number of bins to the left; default none; via options.args); `bins_r` (Number of bins to the right; default none; via options.args); `poly` (Counterfactual histogram polynomial order; default 9; via options.args); `bins_excl_l` (Left-side bunching exclusion bins; default 0; via options.args); `bins_excl_r` (Right-side bunching exclusion bins; default 0; via options.args); `n_boot` (Bootstrap resampling iterations; default 100; via options.args); `notch` (Whether policy schedule has a notch; default FALSE; via options.args); `correct` (Enforce integration constraint on counterfactual density; default TRUE; via options.args).

**Returns.** `b`: Standardized bunching estimate; `e`: Implied elasticity estimate; `cf`: Fitted counterfactual density.

**Checks before reporting.** Sensitivity of the excess mass to the bin width, the polynomial order and the excluded window. Excluded window set from the plotted density before estimation. Round-number heaping at the threshold is a competing explanation.

**Pitfalls.** Optimization frictions spread and shrink bunching, so the estimate understates the structural elasticity unless frictions are modelled.

**Sources.** https://search.r-project.org/CRAN/refmans/bunching/html/bunchit.html, https://doi.org/10.1146/annurev-economics-080315-015234, https://doi.org/10.1093/qje/qjr013.

## Distributional effects

### `qte`

**Use when.** Effects on quantiles of the outcome distribution in the whole population under selection on observables (does a programme raise the bottom of the earnings distribution).

**Versus.** `qtt`: Targets population potential outcome quantiles rather than treated-group distributions. `quantile`: Marginal potential-outcome quantile contrast instead of a conditional quantile regression slope.

**Estimand.** Q_{Y(1)}(τ) − Q_{Y(0)}(τ).

**Identification.** (Y(0), Y(1)) ⟂ D | X. Overlap: 0 < P(D = 1 | X) < 1.

**Run.** `method="qte"` → `qte::unc_qte` (2.0.0).

**Options.** Required: `seed`, `treatment`. Optional: `aggregation`, `args`, `columns`, `definitions`, `distribution_grid`.

**Native arguments that change the result.** `target` (Choose population QTE or QTT among treated units; default qte; fixed by the method (`qte` or `qtt`)); `xformla` (Conditioning covariates for propensity or outcome regression; default ~1; built from `regressors`); `probs` (Quantiles requested for treatment-effect curve; default seq(0.05,0.95,0.05); via options.args); `est_method` (IPW, outcome regression, or augmented IPW; default ipw; via options.args); `method` (Propensity-score link, logit or probit; default logit; via options.args); `weightsname` (Sampling weight column; default NULL; via options.args); `biters` (Empirical bootstrap iterations; default 100; via options.args); `cband` (Compute simultaneous quantile confidence bands; default TRUE; via options.args).

**Returns.** `qte`: Quantile-level effect estimates, QTT when target=qtt; `ate`: ATE or ATT matching target; `qte.se`: Quantile-specific bootstrap standard errors; `qte.lower`: Lower confidence limits; `qte.upper`: Upper confidence limits.

**Checks before reporting.** Quantile effects are differences of marginal quantiles, not effects on the units at those quantiles. Covariates enter only through `regressors`; with none, the result is the raw quantile difference. Use the simultaneous band (`cband`) for statements across quantiles.

**Pitfalls.** With xformla=~1, estimators return unadjusted sample quantile differences; covariate adjustment requires explicit xformla.

**Sources.** https://bcallaway11.github.io/qte/reference/unc_qte.html, https://doi.org/10.1111/j.1468-0262.2007.00738.x.

### `qtt`

**Use when.** Effects on quantiles of the outcome distribution among the treated under selection on observables.

**Versus.** `qte`: Targets treated-group potential outcome quantiles rather than population potential outcome quantiles. `quantile`: Marginal potential-outcome quantile contrast instead of a conditional quantile regression slope.

**Estimand.** Q_{Y(1)|D=1}(τ) − Q_{Y(0)|D=1}(τ).

**Identification.** (Y(0), Y(1)) ⟂ D | X. Overlap: P(D = 1 | X) < 1.

**Run.** `method="qtt"` → `qte::unc_qte` (2.0.0).

**Options.** Required: `seed`, `treatment`. Optional: `aggregation`, `args`, `columns`, `definitions`, `distribution_grid`.

**Native arguments that change the result.** `target` (Choose population QTE or QTT among treated units; default qte; fixed by the method (`qte` or `qtt`)); `xformla` (Conditioning covariates for propensity or outcome regression; default ~1; built from `regressors`); `probs` (Quantiles requested for treatment-effect curve; default seq(0.05,0.95,0.05); via options.args); `est_method` (IPW, outcome regression, or augmented IPW; default ipw; via options.args); `method` (Propensity-score link, logit or probit; default logit; via options.args); `weightsname` (Sampling weight column; default NULL; via options.args); `biters` (Empirical bootstrap iterations; default 100; via options.args); `cband` (Compute simultaneous quantile confidence bands; default TRUE; via options.args).

**Returns.** `qte`: Quantile-level effect estimates, QTT when target=qtt; `ate`: ATE or ATT matching target; `qte.se`: Quantile-specific bootstrap standard errors; `qte.lower`: Lower confidence limits; `qte.upper`: Upper confidence limits.

**Checks before reporting.** Quantile effects are differences of marginal quantiles, not effects on the units at those quantiles. Covariates enter only through `regressors`; with none, the result is the raw quantile difference. Use the simultaneous band (`cband`) for statements across quantiles.

**Pitfalls.** With xformla=~1, estimators return unadjusted sample quantile differences; covariate adjustment requires explicit xformla.

**Sources.** https://bcallaway11.github.io/qte/reference/unc_qte.html, https://doi.org/10.1111/j.1468-0262.2007.00738.x.

### `quantile`

**Use when.** How covariates shift a conditional quantile of the outcome (the conditional median wage), as a descriptive or structural regression.

**Versus.** `qte`: Conditional outcome quantile slope rather than a difference between potential-outcome marginal quantiles. `distribution_effect`: Conditional quantile of Y rather than a thresholded outcome CDF contrast.

**Estimand.** Linear covariate coefficients for the specified conditional quantile of Y at q.

**Run.** `method="quantile"` → `statsmodels` `statsmodels.regression.quantile_regression.QuantReg.fit` (0.14.6). Robust kernel covariance with the Epanechnikov kernel and Hall–Sheather bandwidth; at most 10000 iterations.

**Options.** Required: `quantile`. Optional: None.

**Native arguments that change the result.** `q` (Conditional outcome quantile; default 0.5; top-level `quantile`); `vcov` (Robust or iid covariance estimation; default robust; fixed by the runner at robust); `kernel` (Kernel for asymptotic covariance density; default epa; fixed by the runner at epa); `bandwidth` (Asymptotic covariance bandwidth selector; default hsheather; fixed by the runner at hsheather); `max_iter` (Maximum iterative weighted least-squares cycles; default 1000; fixed by the runner at 10000); `p_tol` (Coefficient-convergence tolerance; default 1e-6; package default).

**Returns.** `params`: Fitted conditional quantile coefficients; `q`: Quantile used for the fit; `iterations`: Iterations performed; `sparsity`: Estimated conditional sparsity; `bandwidth`: Bandwidth selected for standard error.

**Checks before reporting.** Quantile admissibility: q must be strictly between zero and one.

**Pitfalls.** A conditional quantile slope is not the effect on the unconditional quantile; for distributional treatment effects use `qte`.

**Sources.** https://www.statsmodels.org/v0.14.6/generated/statsmodels.regression.quantile_regression.QuantReg.html, https://www.statsmodels.org/v0.14.6/generated/statsmodels.regression.quantile_regression.QuantReg.fit.html.

### `distribution_effect`

**Use when.** The share of outcomes below a policy-relevant threshold (poverty line, minimum test score) by treatment status.

**Versus.** `quantile`: Estimates a CDF difference at a threshold rather than a conditional quantile coefficient. `qte`: Contrasts observed treated and untreated CDFs, not potential-outcome quantiles.

**Estimand.** E[1{Y ≤ c}|D=1] − E[1{Y ≤ c}|D=0] at a supplied threshold c.

**Run.** `method="distribution_effect"` → `statsmodels` `statsmodels.api.OLS.fit (outcome threshold indicator)` (0.14.6). `regressors` must be exactly `[treatment]`, coded 0/1. HC1 standard errors, or clustered with `inference.cluster`.

**Options.** Required: `threshold`, `treatment`. Optional: None.

**Native arguments that change the result.** `cov_type` (Covariance estimator; default nonrobust; fixed by the runner: HC1, or cluster with `inference.cluster`); `cov_kwds` (Cluster membership or additional covariance-estimator settings; default None; from `inference.cluster`).

**Returns.** `params`: OLS coefficients, including the threshold-indicator treatment difference; `bse`: Coefficient standard errors; `conf_int`: Confidence intervals for fitted coefficients.

**Checks before reporting.** The threshold is fixed from the decision before results. The contrast is causal only under the design's assignment.

**Sources.** https://www.statsmodels.org/v0.14.6/regression.html, https://www.statsmodels.org/v0.14.6/generated/statsmodels.regression.linear_model.OLS.fit.html.

## Partial identification

### `manski_bounds`

**Use when.** Without credible point identification: bounds on the average effect from the outcome's known support, tightened by monotone treatment response or selection.

**Versus.** `lee_bounds`: Bounds potential-outcome means using outcome support rather than monotone sample retention. `balke_pearl`: Does not require a binary instrument or binary outcomes.

**Estimand.** Bounds on ATE=E[Y(1)−Y(0)] from bounded outcomes, with optional MTR or MTS restrictions.

**Identification.** The outcome lies within known lower and upper support bounds.

**Run.** `method="manski_bounds"` → `StatsPAI` `statspai.bounds.lee_manski.manski_bounds` (1.43.1).

**Options.** Required: `assumption`, `n_bootstrap`, `seed`, `treatment`, `y_lower`, `y_upper`. Optional: `definitions`.

**Native arguments that change the result.** `y_lower` (Lower bound of outcome support; default None; top-level `y_lower`); `y_upper` (Upper bound of outcome support; default None; top-level `y_upper`); `assumption` (No restriction, monotone response, monotone selection, or both; default none; top-level `assumption`); `n_bootstrap` (Bootstrap replications for endpoint uncertainty; default 500; top-level `n_bootstrap`); `alpha` (One minus confidence level; default 0.05; from `inference.confidence_level`).

**Returns.** `model_info.lower_bound`: Lower endpoint of the estimated ATE identified set; `model_info.upper_bound`: Upper endpoint of the estimated ATE identified set; `ci`: Confidence interval expanding estimated bound endpoints.

**Checks before reporting.** Outcome support validity: y_lower must not exceed the observed minimum; y_upper must not fall below the observed maximum. Outcome support taken from the measurement, not from the sample extremes. Report the width of the identified set and which assumption narrows it.

**Pitfalls.** Unspecified outcome supports default to observed extrema rather than externally known population bounds. Joint MTS and MTR can imply an empty identified set when the observed treated-control mean difference is negative.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/bounds/lee_manski.py.

### `lee_bounds`

**Use when.** Treatment changes who is observed (attrition differs by arm, wages observed only for employed), and the target is the effect for units observed under both arms.

**Versus.** `manski_bounds`: Uses differential outcome retention and trimming instead of known outcome support. `heckman`: Partial-identification trimming instead of a parametric selection equation.

**Estimand.** Lower and upper ATE bounds under monotonic treatment-induced sample selection.

**Identification.** Treatment changes sample retention in a common monotone direction.

**Run.** `method="lee_bounds"` → `StatsPAI` `statspai.bounds.lee_manski.lee_bounds` (1.43.1). `monotonicity` is `increasing` or `decreasing`; the runner refuses it when observed retention by arm contradicts the declared direction.

**Options.** Required: `monotonicity`, `n_bootstrap`, `seed`, `selection`, `treatment`. Optional: `definitions`, `covariates`.

**Native arguments that change the result.** `selection` (Column indicating whether outcome is observed; default None; top-level `selection`); `covariates` (Discrete pretreatment cells used for tightened bounds; default None; top-level `covariates` (discrete cells)); `trimming` (Method of trimming excess retention; default quantile; fixed by the runner at exact); `se_method` (Bootstrap or analytic endpoint standard errors; default bootstrap; fixed by the runner at bootstrap); `n_bootstrap` (Bootstrap replication count; default 500; top-level `n_bootstrap`); `weights` (Optional sampling weights; default None; fixed by the runner: equal unit weights).

**Returns.** `model_info.lower_bound`: Lower bound of the effect for the always-observed; `model_info.upper_bound`: Upper bound of the effect for the always-observed; `model_info.trimming_fraction`: Share of the higher-retention arm trimmed; `ci`: Confidence interval for the partially identified effect.

**Checks before reporting.** Discrete outcome trimming: For binary or coarsely discrete outcomes choose trimming=exact. Report the trimming fraction and the observed shares by arm. State the monotonicity direction in `monotonicity` with its economic reason.

**Pitfalls.** Quantile trimming retains all tied outcomes, can undertrim discrete data, and may collapse the bounds.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/bounds/lee_manski.py, https://doi.org/10.1111/j.1467-937X.2009.00536.x.

### `balke_pearl`

**Use when.** Binary instrument, binary treatment and binary outcome with imperfect compliance, where the exclusion is credible but point identification of the average effect is not.

**Versus.** `manski_bounds`: Uses exogenous binary instrumental variation and binary outcomes, rather than known outcome support alone.

**Estimand.** ℓ_BP ≤ ATE ≤ u_BP from P(Y=y,D=d|Z=z).

**Identification.** Z ⊥ (Y(0), Y(1), D(0), D(1)).

**Run.** `method="balke_pearl"` → `StatsPAI` `statspai.bounds.balke_pearl.balke_pearl` (1.43.1). Requires `inference={"type":"none"}`; `monotonicity` is `none`, `increasing` or `decreasing`.

**Options.** Required: `instrument`, `monotonicity`, `treatment`. Optional: `definitions`.

**Native arguments that change the result.** `instrument` (Binary instrumental-variable column; default none; top-level `instrument`); `alpha` (Accepted but does not create confidence intervals; default 0.05; no effect).

**Returns.** `lower`: Lower endpoint without monotonicity; `upper`: Upper endpoint without monotonicity; `lower_monotone`: Lower endpoint under no-defier monotonicity; `upper_monotone`: Upper endpoint under no-defier monotonicity; `joint_probs`: Conditional joint outcome-treatment distributions by instrument.

**Checks before reporting.** Report the bounds with and without monotonicity (`monotonicity`). No sampling interval is computed; report the cell counts.

**Pitfalls.** The alpha argument is accepted for API symmetry but confidence intervals are not computed.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/bounds/balke_pearl.py, https://doi.org/10.1080/01621459.1997.10474074.

## Networks and space

### `network_exposure`

**Use when.** Randomized treatment with spillovers through a known network (classmates, neighbouring villages); the target is the contrast between exposure conditions defined by own and neighbours' treatment.

**Versus.** `network_spillover`: Design-based exposure-level comparisons instead of parametric OLS on neighbor treatment intensity. `spatial_lag`: Treats neighbors’ assignments as exposure rather than including a lagged outcome regressor.

**Estimand.** E[Y(h1)]−E[Y(h0)] among units eligible for both exposure levels.

**Identification.** Assignment follows the supplied Bernoulli or complete-randomization design. Exposure depends on own and neighbor treatment through the supplied mapping.

**Run.** `method="network_exposure"` → `StatsPAI` `statspai.interference.network_exposure.network_exposure` (1.43.1).

**Options.** Required: `adjacency`, `contrasts`, `eligible_population`, `estimator`, `mapping`, `min_prob`, `p_treat`, `treatment`. Optional: `definitions`, `thresholds`.

**Native arguments that change the result.** `mapping` (Four-cell or fraction-binned exposure categorization; default as4; top-level `mapping`); `p_treat` (Bernoulli treatment assignment probability; default None; top-level `p_treat`); `design` (Bernoulli versus complete randomization; default bernoulli; fixed by the runner at bernoulli); `estimator` (Hájek or Horvitz–Thompson estimator; default hajek; top-level `estimator`); `variance` (PSD-adjusted or ordinary dependency-graph HAC variance; default hac_psd; fixed by the runner at hac_psd); `contrasts` (Requested ordered exposure-category comparisons; default None; top-level `contrasts`); `min_prob` (Minimum eligible probability for each exposure category; default 0.0; top-level `min_prob`); `thresholds` (Cutoffs for fraction-of-treated-neighbors mapping; default (0.0, 0.5); top-level `thresholds`).

**Returns.** `estimates`: Exposure-level outcome means and their uncertainty; `contrasts`: Estimated outcome mean differences across exposures; `n_eligible`: Units with strictly positive probability for each exposure.

**Checks before reporting.** Exposure positivity: Exclude units whose exposure-category probability does not exceed min_prob. Exposure mapping fixed from the economics of the spillover before results. Report the number of eligible units for each contrast.

**Pitfalls.** Using the realized treatment share instead of the known Bernoulli design probability can change exposure weights. Unadjusted graph HAC variance can be anticonservative when the dependency graph has negative eigenvalues.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/interference/network_exposure.py, https://doi.org/10.1214/16-AOAS1005.

### `network_spillover`

**Use when.** A quick linear estimate of own and neighbour-treatment effects with a known network; design-based contrasts use `network_exposure`.

**Versus.** `network_exposure`: Models linear neighbor-treatment exposure rather than estimating randomization-weighted exposure contrasts. `spatial_lag`: Includes neighbors’ treatment WD rather than the simultaneous spatial outcome WY.

**Estimand.** OLS coefficient on W D in Y=α+βD+γWD+Xθ+ε for row-standardized W.

**Identification.** Random assignment of own treatment. The exposure is the row-standardized sum of neighbours' treatment.

**Run.** `method="network_spillover"` → `libpysal.weights.W`, `statsmodels.api.OLS.fit` (libpysal==4.15.1; statsmodels==0.14.6). `weights` names an edge CSV with `source,target,weight`, positive weights, no self-edges, and a neighbour for every unit; the runner row-standardizes it. Requires a complete sample.

**Options.** Required: `treatment`, `weights`. Optional: None.

**Native arguments that change the result.** `cov_type` (Selected coefficient covariance method; default nonrobust; fixed by the runner: HC1, or cluster with `inference.cluster`); `cov_kwds` (Cluster labels and covariance adjustment options; default None; from `inference.cluster`).

**Returns.** `params`: Coefficients on own treatment and weighted neighbor treatment; `bse`: Coefficient standard errors; `conf_int`: Confidence intervals for fitted coefficients.

**Checks before reporting.** Report the direct and spillover coefficients together. Errors of linked units are correlated; cluster at a level that contains most links.

**Sources.** https://www.statsmodels.org/v0.14.6/regression.html, https://pysal.org/libpysal/generated/libpysal.weights.W.html, https://www.statsmodels.org/v0.14.6/generated/statsmodels.regression.linear_model.OLS.fit.html.

### `spatial_lag`

**Use when.** Outcomes of a unit depend on neighbours' outcomes (house prices, local wages) and the parameter of interest is that feedback.

**Versus.** `network_spillover`: Endogenizes neighbors’ outcomes WY rather than including the neighbors’ treatment WD.

**Estimand.** β and ρ in y=ρWy+Xβ+ε estimated by spatial maximum likelihood.

**Identification.** Spatial outcome dependence is represented by a common scalar autoregressive coefficient and supplied weights W. The weights W are known and exogenous. Innovations are independent and Gaussian.

**Run.** `method="spatial_lag"` → `spreg; libpysal` `spreg.ML_Lag` (spreg==1.9.1; libpysal==4.15.1). Requires `inference={"type":"spatial_ml"}` and an edge CSV in `weights`; the runner fits by full maximum likelihood with the full covariance and simple impact multipliers.

**Options.** Required: `weights`. Optional: None.

**Native arguments that change the result.** `w` (Spatial weights matrix; default none; top-level `weights`); `method` (Maximum-likelihood log-determinant algorithm; default full; fixed by the runner at full); `slx_lags` (Number of spatial lags of explanatory variables; default 0; package default); `spat_impacts` (Method for computing spatial spillover multipliers; default simple; fixed by the runner at simple); `vm` (Whether to include full coefficient covariance matrix; default False; fixed by the runner at True); `spat_diag` (Whether to compute spatial diagnostics; default True; package default).

**Returns.** `betas`: Regressor and spatial autoregressive coefficient estimates; `rho`: Spatial outcome autoregressive coefficient; `logll`: Maximized log likelihood; `vm`: Full parameter covariance matrix when requested; `sp_multipliers`: Spatial impacts multipliers.

**Checks before reporting.** Interpret effects through the direct, indirect and total impacts, since β alone omits the feedback through ρ.

**Sources.** https://raw.githubusercontent.com/pysal/spreg/v1.9.1/spreg/ml_lag.py.

## Sensitivity, mediation and specification curves

### `sensitivity_cinelli`

**Use when.** How strong an omitted confounder would have to be, relative to an observed covariate, to overturn a regression estimate.

**Versus.** `sensitivity_oster`: Uses treatment and outcome partial R² instead of coefficient and R² movement across nested regressions. `sensitivity_evalue`: Measures confounding in partial R² instead of a risk-ratio association scale.

**Estimand.** Robustness value: minimum unobserved confounder partial-R² strength needed to overturn a coefficient conclusion.

**Identification.** The model is linear in the treatment and the confounder.

**Run.** `method="sensitivity_cinelli"` → `statspai.diagnostics.sensemakr.sensemakr`, `statspai.diagnostics.sensemakr._robustness_value` (1.43.1).

**Options.** Required: `term`. Optional: `benchmark`, `covariance`, `definitions`, `df_key`, `input`, `kd`, `ky`, `q`, `se_key`, `term`, `treatment`.

**Native arguments that change the result.** `benchmark` (Observed covariates used to calibrate unobserved confounding; default None; top-level option); `kd` (Treatment-confounder association multiplier relative to benchmark; default 1.0; top-level option); `ky` (Outcome-confounder multiplier relative to benchmark; default None (uses kd); top-level option); `alpha` (Test significance level for adjusted robustness; default 0.05; fixed by the runner).

**Returns.** `rv_q`: Robustness value to attenuate the coefficient; `rv_qa`: Robustness value for significance-adjusted conclusion; `partial_r2_yd`: Partial R² between treatment and outcome conditional on controls; `benchmark_table`: Sensitivity benchmarks based on observed covariates.

**Checks before reporting.** Benchmark against the strongest observed confounder (`benchmark`, `kd`, `ky`). Report the robustness value for the estimate and for significance.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/diagnostics/sensemakr.py, https://doi.org/10.1111/rssb.12348.

### `sensitivity_oster`

**Use when.** How much selection on unobservables, relative to observables, would drive the coefficient to zero, from coefficient and R² movements between short and long regressions.

**Versus.** `sensitivity_cinelli`: Uses short-long coefficient and R² stability rather than partial-R² confounder strength. `sensitivity_evalue`: Works on regression coefficients and R² instead of RR-scale association strength.

**Estimand.** Omitted-variable bias adjustment for β under proportional selection δ and assumed maximum model R².

**Identification.** Selection on unobservables is proportional to selection on observable controls at specified δ.

**Run.** `method="sensitivity_oster"` → `StatsPAI` `statspai.diagnostics.sensitivity.oster_bounds` (1.43.1).

**Options.** Required: `delta`, `r_max`. Optional: `absorb`, `absorb_controls`, `baseline_result`, `definitions`, `input`, `summary`, `term`, `treatment`.

**Native arguments that change the result.** `r_max` (Upper attainable R² assumed for fully controlled regression; default None (min(1.0,1.3×R²_long)); top-level option); `delta` (Ratio of unobservable to observable selection; default 1.0; top-level option); `absorb` (Optional absorbed fixed effects in underlying regressions; default None; top-level option); `cluster` (Optional cluster identifier for input data regressions; default None; fixed by the runner).

**Returns.** `beta_adjusted`: Estimated coefficient after omitted-variable adjustment; `delta_star`: Selection ratio at which the effect reaches zero; `identified_set`: Identified coefficient set under specified assumptions; `robust`: Robustness verdict derived from δ*.

**Checks before reporting.** Maximum model fit: r_max should exceed long-model R². Report δ for a zero coefficient and the bounds at the adopted r_max; r_max = 1.3 × R² of the long regression is the default. The controls added must be related to the unobservables of concern.

**Pitfalls.** r_max at or below the long-model R² is automatically raised with a warning.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/diagnostics/sensitivity.py, https://doi.org/10.1080/07350015.2016.1227711.

### `sensitivity_evalue`

**Use when.** Ratio-scale estimates (risk ratios, odds ratios, hazard ratios): the minimum confounder association with treatment and outcome that would explain away the estimate.

**Versus.** `sensitivity_cinelli`: Quantifies joint confounder associations on a risk-ratio scale instead of partial R². `sensitivity_oster`: Benchmarks confounder RR strength instead of short-long model coefficient changes.

**Estimand.** E-value = RR + sqrt(RR * (RR - 1)) (for RR >= 1; protective case uses 1/RR).

**Identification.** Bounds the bias from one unmeasured confounder on the risk-ratio scale.

**Run.** `method="sensitivity_evalue"` → `StatsPAI` `statspai.diagnostics.evalue.evalue` (1.43.1).

**Options.** Required: `coefficient_scale`, `measure`, `term`. Optional: `definitions`, `delta`, `input`, `rare`, `sd`, `true`.

**Native arguments that change the result.** `estimate` (Observed exposure-outcome association on selected measure scale; default none; fixed by the runner); `measure` (Ratio or difference scale of the supplied estimate; default RR; top-level option); `ci` (Confidence interval on the measure scale; default None; fixed by the runner); `se` (Standard error; on log scale for ratio measures; default None; fixed by the runner); `rare` (Optional rare-outcome convention for ratio conversions; default None; top-level option); `true` (Target association value to explain by confounding; default None; top-level option).

**Returns.** `evalue_estimate`: Confounder RR strength for the point association; `evalue_ci`: Confounder RR strength for the confidence limit closest to the null; `rr_estimate`: Association transformed to the RR scale; `rr_ci`: Confidence interval transformed to the RR scale.

**Checks before reporting.** Report the E-value for the estimate and for the interval limit closest to the null.

**Pitfalls.** For risk differences, the scalar conversion is approximate; the exact calculation requires evalue_rd with cell counts.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/diagnostics/evalue.py, https://doi.org/10.7326/M16-2607.

### `mediation`

**Use when.** The question is how much of a treatment effect works through an observed channel (training raises wages through skills).

**Estimand.** Total Effect = ACME + ADE; ACME is the indirect effect through the mediator.

**Identification.** Sequential ignorability: treatment is ignorable given covariates, and the mediator is ignorable given treatment and covariates.

**Run.** `method="mediation"` → `StatsPAI` `statspai.mediation.mediate.mediate` (1.43.1).

**Options.** Required: `mediator`, `treatment`. Optional: `args`, `definitions`, `weights`.

**Native arguments that change the result.** `covariates` (Pretreatment outcome and mediator-model controls; default None; the specification's `regressors`); `interaction` (Include treatment-by-mediator interaction in the outcome model; default False; via options.args); `inference` (Bootstrap, delta, or stacked estimating-equation variance; default bootstrap; via options.args); `n_boot` (Bootstrap resamples for effect uncertainty; default 1000; via options.args); `mediator_model` (Linear, logit or probit mediator specification; default linear; via options.args); `outcome_model` (Outcome specification for potential-outcome mediation; default linear; via options.args); `weights` (Optional observation weighting; default None; top-level `weights`).

**Returns.** `estimate`: Average natural indirect effect; `detail`: Natural indirect, natural direct, total and mediated-share estimates; `se`: Estimated standard error for indirect effect; `ci`: Confidence interval for indirect effect.

**Checks before reporting.** The mediator is measured after treatment and before the outcome. Sequential ignorability is untestable; report sensitivity of the indirect effect to mediator–outcome confounding.

**Pitfalls.** When treatment affects mediator-outcome confounders, the package recommends interventional mediation effects.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/mediation/mediate.py, https://doi.org/10.1037/a0020761.

### `specification_curve`

**Use when.** Several defensible specifications exist and the question is how the estimate varies over the whole declared set.

**Versus.** `sensitivity_oster`: Varies observed modeling choices rather than assuming a ratio of unobserved to observed selection.

**Estimand.** Distribution of a target regression coefficient across enumerated analytical specifications.

**Run.** `method="specification_curve"` → `statspai.robustness.spec_curve.spec_curve`, `statsmodels.stats.multitest.multipletests` (StatsPAI==1.43.1; statsmodels==0.14.6). `regressors` equals the union of the control sets; `family` is required; the saved p values are Holm-adjusted over the family, with Bonferroni simultaneous intervals.

**Options.** Required: `controls`, `family`, `se_types`, `treatment`. Optional: `cluster`, `definitions`, `fe`, `subsets`.

**Native arguments that change the result.** `controls` (Candidate control-variable sets; default None (uses [[]]); top-level option); `se_types` (Standard-error methods to enumerate; default None (uses nonrobust,hc1); top-level option); `subsets` (Named eligible analysis subsamples; default None (uses full sample); top-level option); `cluster_var` (Cluster identifier used by clustered specifications; default None; fixed by the runner); `fe` (Candidate sets of absorbed fixed effects; default None (uses [[]]); top-level option); `alpha` (Confidence interval and significance criterion; default 0.05; fixed by the runner).

**Returns.** `results_df`: One estimated coefficient, SE and p-value per specification; `median_estimate`: Median coefficient across specifications; `n_specs`: Number of fitted specifications; `share_significant`: Fraction of specifications meeting their significance criterion; `model_info.dropped_specs`: Specifications omitted due to linearly dependent regressors.

**Checks before reporting.** Specification completeness: Compare expected combinations with n_specs and inspect dropped_specs for failures. Every specification in the set is defensible before results; the set is fixed in advance. Report the share of specifications with each sign and the median estimate.

**Pitfalls.** Specifications with linearly dependent regressors are dropped and recorded in model_info.dropped_specs.

**Sources.** https://raw.githubusercontent.com/brycewang-stanford/StatsPAI/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/robustness/spec_curve.py, https://doi.org/10.1038/s41562-020-0912-z.

