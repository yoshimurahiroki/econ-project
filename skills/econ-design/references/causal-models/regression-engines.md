# Regression foundations and other engines

Method cards for the regression methods that other designs build on (GLS, logit, Poisson, negative binomial, OLS and fixed-effects regressions in R, Python and Julia, static and dynamic panels) and the Bayesian project-model engine, run by `python3 skills/econ-data/scripts/research_causal.py run SPEC.json --output RESULT.json`. The shared specification fields are in [specification and result](contract.md#specification-and-result); runner details are in [basic](basic.md), [R calls](r-calls.md) and [native](native.md). Python GLM-type methods take `inference={"type":"robust"}` (HC1) or `{"type":"cluster","cluster":...}`; R methods take `inference={"type":"official"}` and native arguments through `options.args`. Each card gives when to use the method, how it differs from its neighbours, the estimand, the identifying conditions, the runner call and options (checked against the code), the native arguments that change the result and how they are set, the returns, the checks before reporting, documented pitfalls and sources.

These methods estimate model parameters; a causal reading comes from the design chosen in [design methods](../designs.md), not from the estimator.

## Which method

| Outcome, structure and target | Method |
| --- | --- |
| Linear, known error variances | `gls` |
| Binary outcome, probability model | `logit` |
| Nonnegative outcome, multiplicative mean, no fixed effects | `poisson` |
| Nonnegative outcome with zeros and many fixed effects | `fixest_ppml` |
| Overdispersed counts where the distribution matters | `negative_binomial_r` |
| Linear, few fixed effects, saved fit for R post-estimation | `ols_r` |
| Linear, many fixed effects | `fixest_ols` (R); `hdfe` (Python); `fixed_effects_julia` (large data, IV) |
| Entity-time panel with entity or time effects | `panel_fe` |
| Panel with a lagged outcome, many units, few periods | `dynamic_panel` |
| Priors, hierarchical pooling, posterior predictions | `bayesian_model` |

## Linear and generalized linear models

### `gls`

**Use when.** Linear regression where the error variance of each observation is known (cell means with known sampling variances, aggregated data weighted by precision).

**Versus.** `ols_r`: Uses a supplied error covariance matrix instead of unweighted least squares.

**Estimand.** Linear regression coefficients estimated by generalized least squares with a supplied error covariance matrix.

**Identification.** The supplied variances are the true error variances up to scale; regressors are exogenous.

**Run.** `method="gls"` → `statsmodels` `statsmodels.api.GLS.fit` (0.14.6). `variance` names a column of positive diagonal variances; the runner passes it as `sigma`. HC1 standard errors, or clustered with `inference.cluster`.

**Options.** Required: `variance`. Optional: None.

**Native arguments that change the result.** `sigma` (Error covariance or observation-specific diagonal variances; default None; top-level `variance` (diagonal only)); `cov_type` (Estimator for the fitted parameter covariance; default nonrobust; fixed by the runner: HC1, or cluster with `inference.cluster`); `cov_kwds` (Options for covariance estimation, including cluster information; default None; from `inference.cluster`).

**Returns.** `params`: Fitted generalized least squares regression coefficients; `bse`: Standard errors of fitted coefficients; `cov_params`: Covariance matrix for parameter estimates.

**Checks before reporting.** The variances come from the data-generating process (sampling design), not from the residuals of the same fit.

**Pitfalls.** A vector supplied as sigma is interpreted as the diagonal of the error covariance matrix.

**Sources.** https://www.statsmodels.org/v0.14.6/generated/statsmodels.regression.linear_model.GLS.html, https://www.statsmodels.org/v0.14.6/generated/statsmodels.regression.linear_model.GLS.fit.html.

### `logit`

**Use when.** Binary outcome (employment, adoption, default) where the target is a probability model with a logit link; report average marginal effects for the decision.

**Versus.** `poisson`: Uses a binomial outcome family and logit link rather than a Poisson family and log link.

**Estimand.** Binomial generalized linear model coefficients with the logit link for the conditional response probability.

**Identification.** Exogenous regressors; the logit link describes the conditional probability.

**Run.** `method="logit"` → `statsmodels` `statsmodels.api.GLM.fit (family=statsmodels.api.families.Binomial)` (0.14.6). The outcome must contain 0 and 1; the fit must converge. HC1 standard errors, or clustered with `inference.cluster`.

**Options.** Required: None. Optional: None.

**Native arguments that change the result.** `family` (Specifies the binomial conditional outcome distribution; default Gaussian when omitted; fixed by the runner at Binomial); `link` (Maps conditional mean probability to the linear predictor; default logit; package default logit); `cov_type` (Estimator of the coefficient covariance; default nonrobust; fixed by the runner: HC1, or cluster with `inference.cluster`); `cov_kwds` (Options for robust or clustered coefficient covariance; default None; from `inference.cluster`).

**Returns.** `params`: Estimated generalized linear model coefficients; `converged`: Indicator of fitting convergence; `conf_int`: Coefficient confidence intervals.

**Checks before reporting.** Coefficients are log-odds; report average marginal effects on the probability, computed from the saved coefficients and data. Separation: a regressor that predicts the outcome perfectly gives unbounded coefficients.

**Pitfalls.** The default GLM family is Gaussian; the binomial family must be supplied explicitly.

**Sources.** https://www.statsmodels.org/v0.14.6/generated/statsmodels.genmod.families.family.Binomial.html, https://www.statsmodels.org/v0.14.6/generated/statsmodels.genmod.generalized_linear_model.GLM.html, https://www.statsmodels.org/v0.14.6/generated/statsmodels.genmod.generalized_linear_model.GLM.fit.html.

### `poisson`

**Use when.** Nonnegative outcomes with a multiplicative conditional mean (counts, trade flows, sales); consistent for the mean even when the variance differs from Poisson.

**Versus.** `logit`: Uses a Poisson mean and log link rather than a binomial probability and logit link. `negative_binomial_r`: Poisson family uses variance mu; negative binomial additionally estimates dispersion theta.

**Estimand.** Poisson generalized linear model coefficients linking the conditional mean to regressors through the log link.

**Identification.** The conditional mean is exp(Xβ); the Poisson variance need not hold when robust standard errors are used.

**Run.** `method="poisson"` → `statsmodels` `statsmodels.api.GLM.fit (family=statsmodels.api.families.Poisson)` (0.14.6). The outcome must be nonnegative; the fit must converge. HC1 standard errors, or clustered with `inference.cluster`. With fixed effects use `fixest_ppml`.

**Options.** Required: None. Optional: None.

**Native arguments that change the result.** `family` (Specifies Poisson conditional outcome distribution; default Gaussian when omitted; fixed by the runner at Poisson); `link` (Log transformation between conditional mean and linear predictor; default log; package default log); `cov_type` (Estimator of the coefficient covariance; default nonrobust; fixed by the runner: HC1, or cluster with `inference.cluster`).

**Returns.** `params`: Estimated mean-regression coefficients; `mu`: Fitted conditional mean of the response; `deviance`: Deviance of the estimated GLM.

**Checks before reporting.** Coefficients are semi-elasticities of the conditional mean.

**Pitfalls.** A Poisson family specifies a variance function equal to its mean. Log-linear OLS on log outcomes is inconsistent under heteroskedasticity and drops zeros; Poisson pseudo-maximum likelihood is the alternative.

**Sources.** https://www.statsmodels.org/v0.14.6/generated/statsmodels.genmod.families.family.Poisson.html, https://www.statsmodels.org/v0.14.6/generated/statsmodels.genmod.generalized_linear_model.GLM.html, https://www.statsmodels.org/v0.14.6/generated/statsmodels.genmod.generalized_linear_model.GLM.fit.html, https://doi.org/10.1162/rest.88.4.641.

### `negative_binomial_r`

**Use when.** Count outcomes where the full distribution matters (overdispersed counts, predicted probabilities of zero); for the conditional mean alone, `poisson` or `fixest_ppml` with robust errors is consistent under weaker conditions.

**Versus.** `poisson`: Estimates a negative-binomial dispersion parameter theta in addition to conditional-mean regression coefficients. `fixest_ppml`: Fits negative-binomial likelihood with estimated theta rather than fixed-effects Poisson mean estimation.

**Estimand.** Negative binomial generalized linear model coefficients and an additional estimated dispersion parameter theta.

**Identification.** The negative binomial distribution holds; consistency of β relies on it more than Poisson pseudo-maximum likelihood does.

**Run.** `method="negative_binomial_r"` → `MASS::glm.nb` (7.3-66). `fixed_effects` enter as factor terms in the formula; native arguments through `options.args`.

**Options.** Required: None. Optional: `args`, `columns`, `confidence_level`, `definitions`, `fixed_effects`, `seed`.

**Native arguments that change the result.** `formula` (Outcome model formula, including optional factor fixed effects constructed by the wrapper; default none; built from the outcome, `regressors` and `fixed_effects`); `weights` (Prior observation weights supplied to the GLM; default none; via options.args); `init.theta` (Initial dispersion value before alternating estimation; default moment estimator after preliminary Poisson GLM; via options.args); `link` (Link for conditional-mean regression; default log; via options.args); `control` (GLM fitting controls including alternating-iteration limit; default glm.control(...); via options.args).

**Returns.** `theta`: Maximum-likelihood estimate of the negative-binomial dispersion parameter; `SE.theta`: Approximate dispersion standard error from observed information; `twologlik`: Twice the fitted log likelihood.

**Checks before reporting.** Joint regression and dispersion convergence: Both regression coefficients and theta converge during alternating iterations. Report θ with its standard error. Compare β with `poisson`; a large gap points to misspecification of the distribution.

**Pitfalls.** glm.nb does not accept a family argument; offsets enter through offset() in a formula.

**Sources.** https://raw.githubusercontent.com/cran/MASS/7.3-66/man/glm.nb.Rd.

### `ols_r`

**Use when.** Linear regression in R when the saved fit is needed for R post-estimation (`club_sandwich`, `wild_cluster_bootstrap`, `marginaleffects`) and fixed effects are few.

**Versus.** `gls`: Uses ordinary or supplied-weight least squares rather than a full specified error covariance matrix. `fixest_ols`: Fits fixed effects as factor regressors rather than absorbing an arbitrary number of high-dimensional effects.

**Estimand.** Coefficients of a linear regression fitted by ordinary or weighted least squares.

**Run.** `method="ols_r"` → `stats::lm` (R 4.5.3). `fixed_effects` enter as factor terms; native arguments through `options.args`.

**Options.** Required: None. Optional: `args`, `columns`, `confidence_level`, `definitions`, `fixed_effects`, `seed`.

**Native arguments that change the result.** `formula` (Dependent variable, explanatory variables, and optional factor fixed effects; default none; built from the outcome, `regressors` and `fixed_effects`); `weights` (Optional observation weights for weighted least squares; default NULL; via options.args); `offset` (Known contribution to the regression linear predictor; default none; via options.args).

**Returns.** `coefficients`: Estimated linear regression coefficients; `residuals`: Observed-minus-fitted regression residuals; `fitted.values`: Fitted response values; `df.residual`: Residual degrees of freedom.

**Checks before reporting.** Many fixed-effect levels slow the fit; use `fixest_ols`.

**Pitfalls.** With weights, lm minimizes a weighted residual sum of squares rather than ordinary residual squares.

**Sources.** https://search.r-project.org/R/refmans/stats/html/lm.html.

## Fixed-effects regressions

### `fixest_ols`

**Use when.** Linear regression with many fixed effects (worker, firm, year) in R, including as the saved fit for wild bootstrap and CR2 tests.

**Versus.** `ols_r`: Absorbs high-dimensional fixed effects instead of including each level as an ordinary factor term. `fixest_ppml`: Minimizes least-squares loss rather than fitting a Poisson conditional mean with fixed effects.

**Estimand.** Ordinary least-squares regression coefficients estimated while absorbing any number of fixed effects.

**Identification.** Strict exogeneity of regressors given the fixed effects for the causal reading.

**Run.** `method="fixest_ols"` → `fixest::feols` (0.14.2). `fixed_effects` are absorbed after the pipe; `vcov`, `ssc` and other native arguments through `options.args`.

**Options.** Required: None. Optional: `args`, `columns`, `confidence_level`, `definitions`, `fixed_effects`, `seed`.

**Native arguments that change the result.** `fml` (Regression formula, with fixed effects after a pipe; default none; built from the outcome, `regressors` and `fixed_effects`); `weights` (Optional observation weights; default none; via options.args); `vcov` (Estimator for standard errors and covariance matrix; default none; via options.args); `ssc` (Small-sample correction for covariance estimation; default ssc(); via options.args); `fixef.rm` (Controls removal of fixed-effect groups yielding perfect fits; default perfect_fit; via options.args); `collin.tol` (Threshold for removing collinear regressors; default 1e-09; via options.args).

**Returns.** `coefficients`: Estimated slopes after accounting for fixed effects; `vcov`: Coefficient covariance matrix; `fixef_vars`: Names of fixed-effect variables; `collin.var`: Regressor names removed for collinearity.

**Checks before reporting.** Report observations and fixed-effect groups removed (`collin.var`, perfect-fit removal). Variation left after the fixed effects: a regressor with little within variation gives an imprecise estimate.

**Pitfalls.** Perfect-fit fixed-effect levels may be removed and collinear regressors excluded from the result.

**Sources.** https://lrberge.github.io/fixest/reference/feols.html.

### `fixest_ppml`

**Use when.** Nonnegative outcomes with zeros and many fixed effects (gravity equations with exporter-year, importer-year and pair effects).

**Versus.** `fixest_ols`: Uses Poisson GLM mean estimation rather than fixed-effects ordinary least squares. `poisson`: Absorbs high-dimensional categorical fixed effects within Poisson regression.

**Estimand.** Poisson generalized linear model conditional-mean coefficients with any number of absorbed fixed effects.

**Identification.** The conditional mean is exp(Xβ + fixed effects).

**Run.** `method="fixest_ppml"` → `fixest::fepois` (0.14.2). `fixed_effects` are absorbed; native arguments through `options.args`.

**Options.** Required: None. Optional: `args`, `columns`, `confidence_level`, `definitions`, `fixed_effects`, `seed`.

**Native arguments that change the result.** `fml` (Outcome, covariates, and fixed-effect formula terms; default none; built from the outcome, `regressors` and `fixed_effects`); `weights` (Observation weights in Poisson estimation; default none; via options.args); `offset` (Known additive contribution to log conditional mean; default none; via options.args); `vcov` (Covariance and standard-error estimator; default none; via options.args); `fixef.rm` (Removal policy for fixed-effect levels yielding perfect fits; default perfect_fit; via options.args); `glm.iter` (Maximum iterations for outer generalized-linear-model fitting; default 25; via options.args); `glm.tol` (Convergence tolerance for GLM fitting; default 1e-08; via options.args).

**Returns.** `coefficients`: Estimated Poisson log-mean regression slopes; `loglik`: Fitted model log likelihood; `deviance`: Fitted generalized linear model deviance.

**Checks before reporting.** GLM iteration convergence: Outer GLM fitting uses glm.iter and glm.tol convergence controls. Report observations dropped for separation or all-zero fixed-effect groups. Convergence within `glm.iter`.

**Pitfalls.** Some fixed-effect groups can be removed due to perfect predictions or separation.

**Sources.** https://lrberge.github.io/fixest/reference/feglm.html, https://doi.org/10.1162/rest.88.4.641, https://doi.org/10.1177/1536867X20909691.

### `hdfe`

**Use when.** Linear regression with several high-dimensional fixed effects in Python.

**Versus.** `fixest_ols`: Implements a compatible fixed-effects OLS specification in Python rather than R. `panel_fe`: Allows arbitrary fixed-effect factors in formula rather than entity/time effects in indexed panels.

**Estimand.** Coefficients of a linear regression estimated after absorbing high-dimensional fixed effects.

**Identification.** Strict exogeneity of regressors given the fixed effects for the causal reading.

**Run.** `method="hdfe"` → `pyfixest` `pyfixest.feols` (0.60.0). `fixed_effects` is required; `vcov` defaults to `hetero`, or CRV1 on `inference.cluster`, and accepts CRV3. Singletons are kept (`fixef_rm="none"`).

**Options.** Required: `fixed_effects`. Optional: `weights`, `weights_type`, `ssc`, `vcov`, `confidence_level`.

**Native arguments that change the result.** `fml` (Fixed-effects regression formula with a pipe before fixed-effect terms; default none; built from the outcome, `regressors` and `fixed_effects`); `vcov` (Heteroskedastic or cluster-robust coefficient covariance specification; default None; top-level `vcov`); `weights` (Name of optional weight variable; default None; top-level `weights`); `weights_type` (Analytic versus frequency observation weights; default aweights; top-level `weights_type`); `ssc` (Small-sample correction settings for covariance; default None; top-level `ssc` (k_adj, k_fixef, G_adj, G_df)); `fixef_rm` (Singleton fixed-effect observation removal policy; default singleton; fixed by the runner at none); `collin_tol` (Tolerance for regressor collinearity elimination; default 1e-09; package default).

**Returns.** `coef()`: Estimated slope coefficients; `se()`: Coefficient standard errors; `confint()`: Coefficient confidence intervals.

**Checks before reporting.** Variation left after the fixed effects. With few clusters, move to `fixest_ols` and the wild bootstrap.

**Pitfalls.** The library default removes singleton fixed-effect observations; passing fixef_rm="none" retains them. Frequency weights must be nonnegative integer multiplicities; analytic weights represent precision weights.

**Version notes.** 0.60.0 → 0.70.0: Default fixed-effect demeaning changed to LSMR with adaptive preconditioning. 0.60.0 → 0.70.0: Typed fitted-model results replace most private attributes, including fit._se.

**Sources.** https://raw.githubusercontent.com/py-econometrics/pyfixest/v0.60.0/pyfixest/estimation/api/feols.py, https://raw.githubusercontent.com/py-econometrics/pyfixest/v0.60.0/pyfixest/estimation/api/utils.py.

### `fixed_effects_julia`

**Use when.** Very large fixed-effects regressions or IV with fixed effects, where Julia's speed matters.

**Versus.** `fixest_ols`: Supports fixed-effects linear estimation through Julia with optional formula-embedded instrumental variables. `panel_fe`: Allows arbitrary fixed-effect variables and optional instrumented regressors rather than only entity/time panel effects.

**Estimand.** Linear regression or instrumental-variable slope coefficients with absorbed high-dimensional categorical fixed effects.

**Run.** `method="fixed_effects_julia"` → `FixedEffectModels.jl` `FixedEffectModels.reg` (2.2.0). `fixed_effects` is required; inference is `robust`, `cluster` (one or more columns) or `homoskedastic`; weights need `weights_type="analytic"`; `endogenous` and `instruments` give IV.

**Options.** Required: `fixed_effects`. Optional: `confidence_level`, `drop_singletons`, `julia`, `maxiter`, `native_output`, `tol`, `weights`, `weights_type`.

**Native arguments that change the result.** `formula` (Linear regression formula with fe() terms and optional endogenous-variable/instrument pairs; default none; built from the outcome, `regressors`, `fixed_effects`, `endogenous` and `instruments`); `weights` (Analytic weight variable named by a column symbol; default none; top-level `weights` with `weights_type="analytic"`); `covariance` (Covariance choice: simple, robust, or one-/multiway cluster; default Vcov.simple() when omitted; from `inference`); `save` (Store residuals, estimated fixed effects, or both; default none; set by the runner); `method` (Computational backend for absorption of fixed effects; default cpu; package default).

**Returns.** `coef`: Coefficient vector for fitted linear or IV model; `vcov`: Estimated coefficient covariance matrix; `r2`: Regression R-squared; `nobs`: Number of fitted observations.

**Checks before reporting.** With IV, report the first-stage F. Report singletons dropped (`drop_singletons`).

**Pitfalls.** Fixed-effect predictions require save=:fe or :all, while residual retrieval requires save=:residuals or :all.

**Sources.** https://raw.githubusercontent.com/FixedEffects/FixedEffectModels.jl/v2.2.0/README.md.

## Panels

### `panel_fe`

**Use when.** Entity-time panel with entity and/or time effects and entity-clustered inference, as the simplest within estimator.

**Versus.** `hdfe`: Restricts absorbed effects to entity/time panel structure rather than arbitrary categorical formula terms. `dynamic_panel`: Uses static fixed-effects regression rather than a lagged-outcome instrumental GMM estimator.

**Estimand.** One- or two-way fixed-effects regression slope coefficients on indexed entity-time panel data.

**Identification.** Strict exogeneity: regressors uncorrelated with past, present and future errors given the effects.

**Run.** `method="panel_fe"` → `linearmodels` `linearmodels.panel.PanelOLS.fit` (7.0). Requires `inference={"type":"cluster","cluster":<entity>}`; at least one of `entity_effects` and `time_effects` is true.

**Options.** Required: `entity`, `entity_effects`, `time`, `time_effects`. Optional: None.

**Native arguments that change the result.** `entity_effects` (Absorb entity-specific fixed effects; default False; top-level `entity_effects`); `time_effects` (Absorb time-specific fixed effects; default False; top-level `time_effects`); `weights` (Optional observation weights; default None; not used by the runner); `cov_type` (Covariance estimator; default unadjusted; fixed by the runner at clustered); `cluster_entity` (Cluster covariance by entity identifier; default False when unspecified; fixed by the runner at True); `debiased` (Degrees-of-freedom adjustment for covariance; default True; fixed by the runner at True).

**Returns.** `params`: Estimated fixed-effects slope coefficients; `cov`: Estimated covariance matrix for slope coefficients; `std_errors`: Coefficient standard errors.

**Checks before reporting.** Report entities, periods and residual degrees of freedom. A lagged outcome among the regressors violates strict exogeneity; use `dynamic_panel`.

**Pitfalls.** Regressors absorbed by fixed effects can make parameters unidentified.

**Version notes.** 7.0 → 7.1: Weight normalization for observations retained after singleton removal was corrected.

**Sources.** https://raw.githubusercontent.com/bashtage/linearmodels/v7.0/linearmodels/panel/model.py.

### `dynamic_panel`

**Use when.** The outcome depends on its own past (persistence of employment, capital, habits) in a panel with many units and few periods, where fixed effects with a lagged outcome are biased.

**Versus.** `panel_fe`: Instruments lagged dependent variables using difference/system GMM instead of static fixed-effects least squares.

**Estimand.** Dynamic panel GMM coefficients including lagged outcomes and exogenous covariates, using internal lag instruments.

**Identification.** The documented model distinguishes predetermined regressors from strictly exogenous regressors and individual fixed effects. No serial correlation in the idiosyncratic errors beyond what differencing creates. Lags two and three of the outcome are valid instruments for the differenced lag.

**Run.** `method="dynamic_panel"` → `pydynpd` `pydynpd.regression.abond` (0.2.2). Requires `inference={"type":"dynamic_gmm"}` and a balanced consecutive panel with at least six periods. The runner fits difference GMM with one outcome lag, instruments from lags two and three, and `regressors` as standard instruments; the first two periods are saved as initial lags. Instruments are not collapsed.

**Options.** Required: `entity`, `time`. Optional: None.

**Native arguments that change the result.** `command_str` (Model syntax specifying lagged dependent variables, GMM lag limits, standard instruments, and difference versus system GMM; default none; built by the runner); `gmm(y,2:3)` (GMM instrument lag window for lagged outcome; default none; fixed by the runner); `nolevel` (Selects difference GMM rather than system GMM; default none; fixed by the runner (difference GMM)).

**Returns.** `regression_table`: Coefficient estimates, standard errors and p-values; `hansen`: Hansen test of overidentifying restrictions; `AR_list`: Arellano–Bond residual serial correlation diagnostics.

**Checks before reporting.** Hansen overidentification test: Report the Hansen test statistic and p-value. Arellano–Bond serial correlation: Report AR(1) and AR(2) test statistics and p-values. AR(2) of the differenced errors not rejected. Hansen test neither rejecting nor near 1; a p value near 1 signals too many instruments. Report the instrument count against the number of groups.

**Pitfalls.** Instrument collapse is supported to limit instrument proliferation. Fixed effects with a lagged outcome are biased when periods are few.

**Sources.** https://pypi.org/project/pydynpd/, https://doi.org/10.2307/2297968, https://doi.org/10.1177/1536867X0900900106, https://doi.org/10.2307/1911408.

## Bayesian project models

### `bayesian_model`

**Use when.** A project model needs priors, hierarchical pooling or posterior predictions (small groups shrunk toward a common mean, structural parameters with prior information).

**Estimand.** The posterior distribution of the adopted variables (`var_names`) given the data and priors in the project's model file.

**Identification.** The likelihood and priors written in the model file; results are conditional on both.

**Run.** `method="bayesian_model"` → `pymc.sample`, `arviz.summary`, `causalpy.PyMCModel` (PyMC 6.4.0 / ArviZ 1.3.0; CausalPy 0.9.0 / PyMC 5.28.5 / ArviZ 0.23.4). Requires `inference={"type":"posterior"}`, optionally with `credible_level`. Required `builder`, `engine` (`pymc` or `causalpy`), `model_file`, `posterior_output`, `sampling` (`draws`, `tune`, `chains` ≥ 2, `random_seed`) and `var_names`; optional `diagnostics` thresholds, prior and posterior predictive settings. `engine="pymc"` uses PyMC 6 with ArviZ 1; `causalpy` uses its PyMC 5 environment.

**Options.** Required: `builder`, `engine`, `model_file`, `posterior_output`, `sampling`, `var_names`. Optional: `definitions`, `diagnostics`, `model_dependencies`, `observation_coord`, `posterior_predictive`, `prior_predictive`.

**Native arguments that change the result.** `draws` (Number of posterior samples per chain after tuning; default 1000; `sampling.draws`); `tune` (Sampler adaptation iterations, discarded by default; default 1000; `sampling.tune`); `chains` (Independent Markov chains for posterior sampling; default None; `sampling.chains` (at least 2)); `random_seed` (Seed for randomized sampling steps; default None; `sampling.random_seed`); `var_names` (Posterior variables to summarize; default None; top-level `var_names`); `ci_prob` (Posterior credible-interval probability for summary; default rcParams[stats.ci_prob]; from `inference.credible_level`).

**Returns.** `posterior`: Posterior simulated draws in the fitted model container; `mean`: Posterior mean for each selected parameter; `ci`: Posterior credible interval; `r_hat`: Rank-normalized split-R-hat convergence diagnostic; `ess_bulk`: Bulk effective sample size.

**Checks before reporting.** R-hat across chains: Report the rank-normalized split-R-hat for each selected parameter. Effective sample sizes: Report bulk and tail effective sample size for each parameter. Set `diagnostics.r_hat_max`, `ess_bulk_min`, `ess_tail_min` and `divergences_max` before sampling, from the recommendations of Vehtari et al. (2021). Prior predictive check: simulated outcomes cover plausible values. Report how the posterior moves under a wider prior.

**Pitfalls.** Tuning samples are excluded from returned posterior draws by default.

**Sources.** https://www.pymc.io/projects/docs/en/stable/api/generated/pymc.sample.html, https://python.arviz.org/projects/stats/en/v1.3.0/_modules/arviz_stats/summary.html, https://doi.org/10.1214/20-BA1221.

