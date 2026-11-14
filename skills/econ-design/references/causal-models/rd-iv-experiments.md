# Regression discontinuity, instrumental variables, experiments and inference

Method cards for the regression-discontinuity, instrumental-variable, experimental, shift-share and inference methods run by `python3 skills/econ-data/scripts/research_causal.py run SPEC.json --output RESULT.json`. The shared specification fields are in [specification and result](contract.md#specification-and-result); R methods take `inference={"type":"official"}` and pass native arguments through `options.args`. Methods that adjust a saved result take its JSON in `data`. Each card gives when to use the method, how it differs from its neighbours, the estimand, the identifying conditions, the runner call and options (checked against the code), the native arguments that change the result, the returns, the checks before reporting, documented pitfalls and sources.

## Which method

| Source of variation and target | Method |
| --- | --- |
| Treatment switches on at a score threshold; effect at the threshold | `rdd_sharp`; `rdrobust_r` for covariates, clusters, mass points, kinks or plots |
| A threshold changes the probability of treatment; complier effect at the threshold | `rdd_fuzzy`; `rdrobust_r` with `fuzzy` for the same extensions |
| Few observations near the threshold or a discrete score | `rdd_localrand` |
| Sorting of units across the threshold (always run before an RD estimate) | `rddensity` |
| Power of an RD design at the decision-relevant effect | `rdpower` |
| Overidentified linear IV with heteroskedastic or clustered errors | `iv_gmm` |
| One endogenous regressor, possibly weak instruments | `iv_ar_robust` (reported interval); `iv_ar` under homoskedasticity |
| Two-arm unit-level randomization | `rct` |
| Blocked, clustered, multiarm or factorial experiment; assignment and power | `rct_design` |
| Shift-share exposure (industry shocks × local shares) | `shift_share` (first rung); `shift_share_inference` (reported inference) |
| Few or unbalanced clusters | `wild_cluster_bootstrap` and `club_sandwich`, reported together |
| Errors correlated by distance | `spatial_conley` |
| Several outcomes testing one hypothesis | `romano_wolf`; `holm` for p values from separate saved results |

Inference rules that apply to every card: cluster at the level of assignment; with few or unbalanced clusters report the wild cluster bootstrap and the CR2 test next to the clustered standard error; with weak-identification risk report the Anderson–Rubin set; with an outcome family report adjusted p values.

## Regression discontinuity

### `rdd_sharp`

**Use when.** Treatment switches on for everyone at a known score threshold (a test-score cutoff for a scholarship, an age threshold for a pension rule, a firm-size threshold for a regulation); the target is the effect for units at the threshold. Use `rdrobust_r` when covariates, clustered scores, mass points or a kink are needed; use `rdd_localrand` when few units lie near the threshold.

**Versus.** `rdd_fuzzy`: Treatment assignment is deterministic; fuzzy RD rescales by the uptake discontinuity. `rdd_localrand`: Uses local-polynomial continuity identification rather than local complete-randomization inference.

**Estimand.** τ = lim_{x↓c} E[Y | X = x] − lim_{x↑c} E[Y | X = x], the average effect for units with score X = c.

**Identification.** Conditional potential-outcome functions are continuous at the cutoff. No precise manipulation of the score around c. Predetermined covariates are continuous at c.

**Run.** `method="rdd_sharp"` → `rdrobust` `rdrobust.rdrobust` (2.1.1). The saved estimate, standard error and interval are the robust bias-corrected `Robust` row; `diagnostics` keep the conventional estimate, h and b on each side, and the effective counts.

**Options.** Required: `bandwidth`, `cutoff`, `running`. Optional: None.

**Native arguments that change the result.** `c` (Running-variable cutoff; default 0; top-level `cutoff`); `fuzzy` (Observed treatment uptake vector for fuzzy RD; default NULL; none for the sharp design); `p` (Local-polynomial order; default 1; fixed by the runner at 1); `q` (Bias-estimation polynomial order; default p+1; fixed by the runner at 2); `h` (Cutoff estimation bandwidths, selected automatically if omitted; default NULL; top-level `bandwidth`: "mserd" or a positive number); `kernel` (Kernel weighting observations around the cutoff; default tri; fixed by the runner at tri); `bwselect` (Data-driven bandwidth selection rule; default mserd; fixed by the runner at mserd); `vce` (Variance estimator: nearest-neighbor or other supported choice; default nn; fixed by the runner at nn).

**Returns.** `coef`: Conventional, bias-corrected, and robust point estimates; `se`: Standard errors for the reported estimators; `pv`: Inference p-values; `ci`: Confidence intervals; `bws`: Chosen estimation and bias-correction bandwidths; `N_h`: Effective observations within bandwidth by cutoff side.

**Checks before reporting.** Local effective sample sizes: Report N_h alongside side-specific bandwidths. Density test at c with `rddensity` before reading the estimate; a rejection at 5% sends the design back to step E4. Covariate continuity: rerun with each predetermined covariate as the outcome; a jump at c is a failed check. Report the robust bias-corrected estimate and interval with h and b on each side. Bandwidth sensitivity at half and double h; the estimate should stay inside the headline interval. Placebo cutoffs away from c, on each side separately.

**Pitfalls.** Conventional local-polynomial confidence intervals can have substantial smoothing bias; robust bias correction addresses this. The estimate is local to c; effects away from the threshold need a model. Global high-order polynomials in the score give misleading estimates; the runner uses local linear fits.

**Sources.** https://cran.r-project.org/web/packages/rdrobust/refman/rdrobust.html, https://www.annualreviews.org/content/journals/10.1146/annurev-economics-051520-021409, https://doi.org/10.3982/ECTA11757, https://doi.org/10.1080/07350015.2017.1366909.

### `rdd_fuzzy`

**Use when.** Crossing the threshold changes the probability of treatment without fixing it (a programme offered above a score with partial take-up, a class-size rule partly followed); the target is the effect for compliers at the threshold.

**Versus.** `rdd_sharp`: Normalizes outcome discontinuity by the treatment uptake jump. `rdd_localrand`: Uses local-polynomial continuity identification rather than local complete-randomization inference.

**Estimand.** τ_F = [lim_{x↓c} E[Y | X = x] − lim_{x↑c} E[Y | X = x]] / [lim_{x↓c} E[D | X = x] − lim_{x↑c} E[D | X = x]], a local average effect for compliers at c.

**Identification.** Conditional potential-outcome functions are continuous at the cutoff. Treatment probability changes discontinuously at the cutoff. Monotonicity: crossing the threshold moves no unit out of treatment. Exclusion: the threshold affects the outcome only through treatment.

**Run.** `method="rdd_fuzzy"` → `rdrobust` `rdrobust.rdrobust` (2.1.1). `treatment` must be coded 0/1. The saved estimate is the `Robust` row, as in `rdd_sharp`.

**Options.** Required: `bandwidth`, `cutoff`, `running`, `treatment`. Optional: None.

**Native arguments that change the result.** `c` (Running-variable cutoff; default 0; top-level `cutoff`); `fuzzy` (Observed treatment uptake vector for fuzzy RD; default NULL; top-level `treatment`); `p` (Local-polynomial order; default 1; fixed by the runner at 1); `q` (Bias-estimation polynomial order; default p+1; fixed by the runner at 2); `h` (Cutoff estimation bandwidths, selected automatically if omitted; default NULL; top-level `bandwidth`: "mserd" or a positive number); `kernel` (Kernel weighting observations around the cutoff; default tri; fixed by the runner at tri); `bwselect` (Data-driven bandwidth selection rule; default mserd; fixed by the runner at mserd); `vce` (Variance estimator: nearest-neighbor or other supported choice; default nn; fixed by the runner at nn).

**Returns.** `coef`: Conventional, bias-corrected, and robust point estimates; `se`: Standard errors for the reported estimators; `pv`: Inference p-values; `ci`: Confidence intervals; `bws`: Chosen estimation and bias-correction bandwidths; `N_h`: Effective observations within bandwidth by cutoff side.

**Checks before reporting.** Local effective sample sizes: Report N_h alongside side-specific bandwidths. First stage: estimate the jump in treatment at c with `rdd_sharp` on D; a small or imprecise jump is a weak-identification risk. Density and covariate-continuity checks as in `rdd_sharp`. Report h, b and the effective counts on each side.

**Pitfalls.** Conventional local-polynomial confidence intervals can have substantial smoothing bias; robust bias correction addresses this. The effect is for compliers at c; it differs from the effect for always-takers or for units far from the threshold.

**Sources.** https://cran.r-project.org/web/packages/rdrobust/refman/rdrobust.html, https://www.annualreviews.org/content/journals/10.1146/annurev-economics-051520-021409, https://doi.org/10.3982/ECTA11757.

### `rdd_localrand`

**Use when.** Few observations near the threshold or a discrete score, where local-polynomial extrapolation is unreliable, and a narrow window around c can be treated as randomly assigned.

**Versus.** `rdd_sharp`: Uses a fixed-window randomization mechanism and permutation tests instead of local-polynomial extrapolation. `rct`: Assignment derives from cutoff position within a selected window, not a study-wide randomization.

**Estimand.** Difference in mean outcomes between the two sides of c inside the window [c − w, c + w]; the permutation test is for the sharp null of zero effect for every unit in the window.

**Identification.** Treatment assignment behaves as complete randomization inside the chosen window. Inside the window the outcome does not depend on the score itself, or the dependence is modelled.

**Run.** `method="rdd_localrand"` → `scipy.stats.permutation_test`, `statsmodels.OLS.fit` (scipy 1.17.0; statsmodels 0.14.6). The window is [cutoff − bandwidth, cutoff + bandwidth]; units outside it are saved as excluded. The saved coefficient is the HC1 regression difference in means; the permutation p value is in `diagnostics.randomization_test`.

**Options.** Required: `bandwidth`, `cutoff`, `permutations`, `running`, `seed`. Optional: None.

**Native arguments that change the result.** `n_resamples` (Monte Carlo reassignments for permutation-test p-value; default 9999; top-level `permutations`, at least 1000); `permutation_type` (Randomly permute observations between independent samples; default independent; fixed by the runner at independent); `alternative` (Upper, lower, or two-sided randomization test; default two-sided; fixed by the runner at two-sided); `rng` (Random generator controlling Monte Carlo draws; default None; top-level `seed`); `cov_type` (Regression covariance estimator; default nonrobust; fixed by the runner at HC1).

**Returns.** `statistic`: Observed difference-in-means test statistic; `pvalue`: Permutation-test p-value; `null_distribution`: Simulated or enumerated null randomization distribution; `params`: OLS intercept and cutoff assignment coefficient.

**Checks before reporting.** Complete randomization plausibility: Assess score-window assignment mechanism prior to interpreting randomization inference. Choose the window from covariate balance in nested windows around c, before looking at outcomes. Balance of predetermined covariates inside the adopted window. Report the window, the arm counts and the actual number of permutations. Sensitivity to the next smaller and larger windows.

**Pitfalls.** Permutation-test validity depends on the declared exchangeability/randomization mechanism.

**Sources.** https://doi.org/10.1515/jci-2013-0010, https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.stats.permutation_test.html, https://www.statsmodels.org/v0.14.6/generated/statsmodels.regression.linear_model.OLS.fit.html.

### `rdrobust_r`

**Use when.** Regression discontinuity that needs what the Python runner fixes: covariates, clustered scores, mass points in a discrete score, a kink design (`deriv=1`), other polynomial orders or kernels, or a binned `rdplot`.

**Versus.** `rdd_sharp`: R implementation also exposes fuzzy and kink variants through function parameters. `rddensity`: Estimates a cutoff outcome effect, whereas rddensity tests the running-variable density itself.

**Estimand.** Discontinuity in the conditional outcome regression at cutoff; fuzzy designs rescale by treatment discontinuity.

**Identification.** Outcome regression limits identify potential outcomes on either cutoff side. No precise manipulation of the score around c.

**Run.** `method="rdrobust_r"` → `rdrobust::rdrobust` (4.1.1). The saved estimate is the `Robust` row. `plot={}` also calls `rdrobust::rdplot` and saves its bins.

**Options.** Required: `running`. Optional: `args`, `columns`, `definitions`, `plot`, `seed`.

**Native arguments that change the result.** `c` (Treatment assignment cutoff; default 0; via options.args); `fuzzy` (Treatment variable for fuzzy RD; default NULL; via options.args); `p` (Order of local-polynomial point estimator; default 1; via options.args); `q` (Order of bias estimator; default p+1; via options.args); `h` (Estimation bandwidths; default NULL; via options.args); `kernel` (Kernel used in weighting; default tri; via options.args); `vce` (Variance estimation scheme; default nn; via options.args); `masspoints` (Handling of repeated running-variable values; default adjust; via options.args).

**Returns.** `coef`: Conventional, bias-corrected and robust point estimates; `se`: Associated standard errors; `ci`: Confidence interval matrix; `bws`: Estimation and bias bandwidths.

**Checks before reporting.** Mass points in running variable: Use supported masspoints adjustments and effective observations when discrete scores are present. Mass points: with repeated score values, report the number of distinct values on each side and keep `masspoints="adjust"`. Report the robust bias-corrected estimate and interval with h and b on each side and the effective counts. Density test with `rddensity` and covariate continuity, as in `rdd_sharp`. With clustered scores, set `cluster` and report the cluster count.

**Pitfalls.** Repeated running-variable values affect the bandwidth-selection and standard-error procedures.

**Sources.** https://cran.r-project.org/web/packages/rdrobust/refman/rdrobust.html, https://www.annualreviews.org/content/journals/10.1146/annurev-economics-051520-021409.

### `rddensity`

**Use when.** Before any RD estimate: test whether units sort across the threshold, for example bunching of the score just above a cutoff that pays.

**Versus.** `rdrobust_r`: Tests density continuity of the score instead of estimating discontinuity in outcomes. `rdpower`: Tests an observed assignment-score distribution rather than evaluating power for a treatment-effect alternative.

**Estimand.** Density jump f(c+) - f(c-) of the running variable at assignment cutoff.

**Identification.** Continuity of running-variable density under the no-precise-manipulation null.

**Run.** `method="rddensity"` → `rddensity::rddensity` (3.0).

**Options.** Required: `running`. Optional: `args`, `columns`, `definitions`, `seed`.

**Native arguments that change the result.** `c` (Discontinuity cutoff; default 0; via options.args); `p` (Local-polynomial density estimator order; default 2; via options.args); `q` (Bias-correction polynomial order; zero requests automatic selection; default 0; via options.args); `h` (Bandwidths below and above cutoff; default automatic; via options.args); `kernel` (Kernel for local density estimation; default triangular; via options.args); `massPoints` (Account for repeated running-variable observations; default TRUE; via options.args).

**Returns.** `test`: Asymptotic and jackknife density-discontinuity test results; `hat`: Local-polynomial density estimates on each cutoff side; `bino`: Local binomial test results when requested.

**Checks before reporting.** Density manipulation test: Compare density discontinuity test p-value with adopted significance level. Report the p value of the density test with the effective counts on each side; a rejection at 5% sends the design back to step E4. A non-rejection with few observations near c is weak evidence; report the counts with it.

**Pitfalls.** Repeated running-variable values require attention to mass-point and unique-value bandwidth options.

**Sources.** https://cran.r-project.org/web/packages/rddensity/refman/rddensity.html.

### `rdpower`

**Use when.** Before collecting data or committing to an RD design: power to detect the effect size that would change the decision.

**Versus.** `rdrobust_r`: Computes power at a declared alternative rather than estimating a treatment effect from observed outcomes. `rddensity`: Evaluates rejection probability for RD effects rather than running-variable density jumps.

**Estimand.** Power to reject the zero-effect null under a specified RD alternative effect tau.

**Identification.** Specified alternative tau, significance level and variance/bandwidth inputs define a power calculation.

**Run.** `method="rdpower"` → `rdpower::rdpower` (3.0).

**Options.** Required: `running`. Optional: `args`, `columns`, `definitions`, `seed`.

**Native arguments that change the result.** `tau` (Alternative treatment-effect magnitude; default NULL (half untreated-group outcome SD); via options.args; required by the runner); `alpha` (Significance level for the test; default 0.05; via options.args); `samph` (Alternative bandwidth or effective sample-size input; default NULL; via options.args); `fuzzy` (Treatment uptake values in fuzzy RD; default NULL; via options.args); `kernel` (Kernel used for RD power calculations; default triangular; via options.args).

**Returns.** `power.rbc`: Power of robust bias-corrected RD inference; `power.conv`: Power of conventional RD inference; `se.rbc`: Robust bias-corrected standard-error input or estimate.

**Checks before reporting.** Set `tau` to the decision threshold of step E1 and report power at that value. Power below 0.8 at the decision threshold means the design cannot settle the decision; report it before estimating.

**Pitfalls.** Power varies with the specified alternative effect and bandwidth configuration.

**Sources.** https://cran.r-project.org/web/packages/rdpower/refman/rdpower.html.

## Instrumental variables

### `iv_gmm`

**Use when.** Overidentified linear IV (more excluded instruments than endogenous regressors) with heteroskedastic or clustered errors, where efficient weighting and the J test add information over 2SLS.

**Versus.** `iv_ar`: Fits GMM point estimates and a J overidentification statistic; iv_ar inverts the Anderson–Rubin test. `shift_share`: Uses supplied excluded instruments, rather than constructing a Bartik exposure-weighted instrument.

**Estimand.** β in Y = Xβ + u with E[Z_i u_i(β)] = 0, estimated by two-step efficient GMM.

**Identification.** Instruments satisfy moment orthogonality with the structural regression disturbance. Relevance: the excluded instruments move the endogenous regressors conditional on the exogenous regressors.

**Run.** `method="iv_gmm"` → `linearmodels` `linearmodels.iv.IVGMM.fit` (7.0). Clustering comes from `inference.cluster`; the saved diagnostics hold the J statistic, its degrees of freedom and the iteration count.

**Options.** Required: None. Optional: None.

**Native arguments that change the result.** `weight_type` (GMM weighting matrix specification; default robust; fixed by the runner at robust); `cov_type` (Postestimation covariance choice; default robust; fixed by the runner: clustered when the inference has a cluster, robust otherwise); `debiased` (Degrees-of-freedom covariance adjustment; default False; fixed by the runner at True); `clusters` (Cluster groups when covariance is clustered; default None; from `inference.cluster`); `iter_limit` (Maximum GMM iterations; default 2; package default); `tol` (GMM convergence tolerance; default 0.0001; package default).

**Returns.** `params`: GMM coefficient vector; `std_errors`: Estimated coefficient standard errors; `j_stat`: Overidentifying moment restrictions test; `iterations`: Completed iterations of GMM weighting.

**Checks before reporting.** Overidentifying restrictions: Report J statistic and reference degrees of freedom when overidentified. First-stage strength for each endogenous regressor (effective F); with weak-identification risk, report the `iv_ar_robust` set next to the estimate. J test with its degrees of freedom; a rejection says the instruments disagree, not which one is invalid. Compare with the 2SLS estimate; a large gap with many instruments points to finite-sample bias.

**Pitfalls.** J test is uninformative when the model is exactly identified.

**Sources.** https://bashtage.github.io/linearmodels/iv/iv/linearmodels.iv.model.IVGMM.html, https://bashtage.github.io/linearmodels/iv/iv/linearmodels.iv.model.IVGMM.fit.html, https://bashtage.github.io/linearmodels/iv/iv/linearmodels.iv.results.IVGMMResults.html.

### `iv_ar`

**Use when.** One endogenous regressor, homoskedastic errors plausible, and instruments possibly weak: an interval valid whatever the first-stage strength. With heteroskedastic or clustered errors use `iv_ar_robust`.

**Versus.** `iv_ar_robust`: Uses a homoskedastic F reference; iv_ar_robust supports heteroskedastic and cluster-robust AR inversion. `iv_gmm`: Inverts IV test statistics to provide weak-identification-robust confidence sets.

**Estimand.** Set of IV coefficients beta whose Anderson–Rubin F test does not reject the null at significance alpha.

**Identification.** Excluded instruments are exogenous under the null and homoskedastic F reference holds.

**Run.** `method="iv_ar"` → `IV2SLS.fit`, `OLS.fit`, `scipy.stats.f.ppf` (linearmodels 7.0; statsmodels 0.14.6; scipy 1.17.0). The Anderson–Rubin set is computed exactly from a quadratic in β, not on a grid; `diagnostics.anderson_rubin.intervals` holds one interval, two rays, the whole line or nothing. The point estimate is IV2SLS with unadjusted covariance. Requires exactly one endogenous column and `inference.type="homoskedastic"`.

**Options.** Required: `alpha`. Optional: None.

**Native arguments that change the result.** `cov_type` (IV2SLS covariance type; default robust; fixed by the runner at unadjusted); `debiased` (Use degrees-of-freedom adjustment in IV2SLS; default False; fixed by the runner at True); `q` (Excluded-instrument count used as AR numerator degrees of freedom; default number of instruments; number of excluded instruments, set by the data); `alpha` (Significance level used to invert AR test; default 0.05; top-level `alpha`).

**Returns.** `params`: 2SLS estimated regression coefficients; `confidence_set`: Inverted AR set: bounded interval, rays, real line, or empty set.

**Checks before reporting.** Inverted AR confidence set: Retain unbounded or empty sets rather than truncating to a finite interval. Report the set exactly as returned, including rays or the whole line. An unbounded set means the instruments do not identify β at that level; the interval is the finding.

**Pitfalls.** Weak instruments may yield unbounded, disconnected, or empty confidence sets.

**Sources.** https://doi.org/10.1257/jep.20251464, https://bashtage.github.io/linearmodels/iv/iv/linearmodels.iv.model.IV2SLS.html.

### `iv_ar_robust`

**Use when.** The reported interval for applied linear IV with one endogenous regressor whenever identification may be weak: heteroskedastic or clustered errors, fixed effects and weights are supported.

**Versus.** `iv_ar`: Uses heteroskedastic or clustered inference rather than the homoskedastic F inversion in iv_ar.

**Estimand.** Anderson–Rubin confidence set obtained by inverting robust tests across candidate treatment coefficients.

**Identification.** Excluded instruments satisfy IV exclusion and exogeneity conditions.

**Run.** `method="iv_ar_robust"` → `ivDiag::AR_test` (1.0.8). The runner also calls `ivDiag::ivDiag` without bootstrap and saves the first-stage statistics in `stages`.

**Options.** Required: None. Optional: `args`, `columns`, `definitions`, `fixed_effects`, `seed`.

**Native arguments that change the result.** `FE` (Fixed-effect covariates to absorb; default NULL; top-level `fixed_effects`); `cl` (Optional grouping for clustered variance estimates; default NULL; via options.args); `weights` (Observation weights; default NULL; via options.args); `CI` (Return confidence set by inversion; default TRUE; set to TRUE by the runner); `alpha` (Test significance level; default 0.05; via options.args; runner default 0.05); `prec` (Rounding precision for reported results; default 4; via options.args; runner default 12).

**Returns.** `Fstat`: Anderson–Rubin test statistic; `ci`: Computed Anderson–Rubin confidence set; `ci.print`: Formatted confidence-set representation; `bounded`: Whether AR confidence set is bounded.

**Checks before reporting.** Robust Anderson–Rubin inference: Report confidence-set topology, including infinite endpoints. Report the effective first-stage F from the saved stages. For a 5% t-test on the 2SLS estimate to be valid the first-stage F must exceed 104.7; below it, report the AR set as the interval.

**Pitfalls.** AR confidence sets may be unbounded under weak identification.

**Sources.** https://www.rdocumentation.org/packages/ivDiag/versions/1.0.8/topics/AR_test, https://doi.org/10.1257/aer.20211063, https://doi.org/10.1257/jep.20251464.

## Experiments

### `rct`

**Use when.** Two-arm complete randomization at the unit level, no strata or clusters; the target is the average effect of assignment (intention to treat). Blocked, clustered, multiarm or factorial experiments go to `rct_design`.

**Versus.** `rdd_localrand`: Analyzes two-arm random assignment across the full sample rather than within a running-score cutoff window. `rct_design`: Does not implement blocked, clustered, factorial, or multiarm design declarations.

**Estimand.** Observed mean outcome difference between two randomized assignment arms.

**Identification.** Independent treatment assignment follows the declared complete-randomization allocation.

**Run.** `method="rct"` → `scipy.stats.permutation_test`, `statsmodels.OLS.fit` (scipy 1.17.0; statsmodels 0.14.6). `regressors` must be exactly `[treatment]`, coded 0/1. The saved coefficient is the HC1 regression difference in means; the permutation p value for the sharp null is in `diagnostics.randomization_test`.

**Options.** Required: `permutations`, `seed`, `treatment`. Optional: None.

**Native arguments that change the result.** `n_resamples` (Number of random reassignments; default 9999; top-level `permutations`, at least 1000); `permutation_type` (Permutation design for two independent groups; default independent; fixed by the runner at independent); `alternative` (One- or two-sided alternative; default two-sided; fixed by the runner at two-sided); `rng` (Randomization pseudorandom generator; default None; top-level `seed`); `cov_type` (OLS covariance specification; default nonrobust; fixed by the runner at HC1).

**Returns.** `statistic`: Observed test statistic on randomized arms; `pvalue`: Assignment permutation p-value; `null_distribution`: Randomization-based reference statistics; `params`: OLS arm-difference coefficient and constant.

**Checks before reporting.** Permutations and two-sided rejection: Compare randomization p-value with the adopted significance level. Balance table of predetermined covariates by arm. Attrition by arm; differential attrition calls for `lee_bounds`. With partial take-up the estimate is the intention-to-treat effect; the effect of treatment uses IV with assignment as the instrument.

**Pitfalls.** When the permutation count is below the possible distinct reallocations, p-values use randomized Monte Carlo approximation.

**Sources.** https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.stats.permutation_test.html, https://www.statsmodels.org/v0.14.6/generated/statsmodels.regression.linear_model.OLS.fit.html.

### `rct_design`

**Use when.** Designing or analysing an experiment with blocks, clusters, several arms, factorial cells or unequal assignment probabilities: assignment, simulated diagnosis and design-based analysis from one declaration.

**Versus.** `rct`: Supports declared multiarm, blocked and clustered assignments and design-based weighting.

**Estimand.** Randomized assignment effects estimated as differences in means, regression-adjusted contrasts, or Horvitz–Thompson contrasts.

**Identification.** Known treatment assignment probabilities follow the declared randomization mechanism.

**Run.** `method="rct_design"` → `randomizr::declare_ra`, `randomizr::conduct_ra`, `estimatr::difference_in_means`, `estimatr::lm_robust`, `estimatr::horvitz_thompson` (randomizr 2.0.1.9000; estimatr 2.1.0). `operation` is `assign`, `analyze` or `diagnose`; the declaration and its options are in [RCT design, assignment and diagnosis](randomization.md#rct-design-assignment-and-diagnosis).

**Options.** Required: `experimental_design`, `operation`, `seed`, `treatment`. Optional: `weights`, `estimator`, `contrasts`, `ri`, `simulation`, `receipt`, `confidence_level`, `definitions`, `assignment_result`.

**Native arguments that change the result.** `ra_type` (Choice of random assignment mechanism; default NULL; `experimental_design.ra_type`); `prob` (Marginal treatment assignment probability where applicable; default NULL; `experimental_design`); `blocks` (Blocking variable used to randomize within groups; default NULL; `experimental_design`); `clusters` (Cluster variable randomized jointly; default NULL; `experimental_design`); `weights` (Unit importance weights for robust regression or estimator; default NULL; top-level `weights`); `se_type` (Variance-estimator selection in design-based difference in means; default default; `estimator`).

**Returns.** `Z`: Assigned experimental arm from randomizr::conduct_ra; `estimate`: Design-based treatment-effect point estimate; `std.error`: Estimated uncertainty of treatment contrast.

**Checks before reporting.** Assignment probabilities: The declaration supports assignment-probability extraction for each unit. Assignment probabilities by unit from the declaration; analysis weights match them. Analysis clusters at the unit of assignment. Diagnosis before fielding: power and bias at the decision threshold of step E1.

**Pitfalls.** Horvitz–Thompson variance calculations depend on the specified randomization declaration.

**Sources.** https://cran.r-project.org/web/packages/estimatr/refman/estimatr.html, https://cran.r-project.org/web/packages/randomizr/refman/randomizr.html.

## Shift-share designs

### `shift_share`

**Use when.** A first rung for a shift-share design: 2SLS with the instrument Σ_k s_ik g_k built from fixed shares and supplied shocks. Its inference is location-robust only; the reported inference comes from `shift_share_inference`.

**Versus.** `shift_share_inference`: Constructs only the exposure-weighted instrument and standard robust/clustered 2SLS inference. `iv_gmm`: Builds an excluded instrument from observed shock-share exposure, then estimates 2SLS.

**Estimand.** Linear IV coefficient using the exposure-weighted shock instrument sum_k s_ik g_k.

**Identification.** Shock-based identification follows from quasi-random sector shocks. Share-based identification requires exogeneity of location-sector exposure shares.

**Run.** `method="shift_share"` → `linearmodels` `linearmodels.iv.IV2SLS.fit` (7.0). Shares must be nonnegative and sum to one in every row; each share column pairs with one shock value. Clustering comes from `inference.cluster`.

**Options.** Required: `shares`, `shocks`. Optional: None.

**Native arguments that change the result.** `dependent` (Structural outcome vector; default none; the specification's `outcome`); `endog` (Endogenous treatment variable; default none; the specification's `endogenous`); `instruments` (Excluded instrument matrix; here generated from shares and shocks; default none; built by the runner from `shares` and `shocks`); `cov_type` (Covariance choice; default robust; fixed by the runner: clustered when the inference has a cluster, robust otherwise); `debiased` (Covariance degrees-of-freedom correction; default False; fixed by the runner at True).

**Returns.** `params`: IV structural coefficient estimates; `std_errors`: IV coefficient standard errors; `first_stage`: First-stage statistics for instrument relevance.

**Checks before reporting.** First-stage instrument strength: Inspect first-stage partial R-squared and test statistic. First-stage partial R² and statistic from `diagnostics`. Move to `shift_share_inference` for the reported interval.

**Pitfalls.** Common sector shocks create cross-unit dependence that conventional location-level standard errors can miss.

**Sources.** https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/bartik/shift_share.py, https://doi.org/10.1093/restud/rdab030, https://doi.org/10.1257/aer.20181047, https://bashtage.github.io/linearmodels/iv/iv/linearmodels.iv.model.IV2SLS.html.

### `shift_share_inference`

**Use when.** Reported inference for shift-share designs (industry trade shocks × local industry shares, national inflows by origin × local origin shares). Fix the identification basis first: `shocks` when many as-good-as-random shocks identify the effect (Borusyak, Hull and Jaravel; AKM and AKM0 inference); `shares` when exogenous baseline shares identify it (Goldsmith-Pinkham, Sorkin and Swift; location-clustered 2SLS with Rotemberg weights).

**Versus.** `shift_share`: Supports explicit shocks-based AKM inference and shares-based location robust/clustered 2SLS.

**Estimand.** 2SLS shift-share effect with AKM exposure-robust covariance and AKM0 confidence sets when identification_basis=shocks.

**Identification.** For shock-based identification, sector shocks are exogenous conditional on exposure and control variables. Shares basis: baseline shares are exogenous to the outcome changes, conditional on controls. Shocks basis: many shocks, none with a large exposure weight.

**Run.** `method="shift_share_inference"` → `statspai.bartik.shift_share.bartik`, `statspai.bartik.adao_correction.ssaggregate`, `linearmodels.iv.IV2SLS.fit` (StatsPAI git:ddb3b45f2d3fc649ea794aa15f8989bb10f8e543; linearmodels 7.0). Requires one endogenous column, no input instruments, and `definitions` with `baseline_period`, `share_population` and `identifying_variation`. The shocks basis also requires `definitions.shock_dependence="independent"`. Shocks basis saves the AKM estimate, the AKM0 set and its type (bounded, union, real line or empty) and the shock-level BHJ estimate; shares basis saves location-clustered (with `cluster`) or HC1 2SLS.

**Options.** Required: `definitions`, `identification_basis`, `shares`, `shocks`. Optional: `cluster`, `definitions`, `weights`.

**Native arguments that change the result.** `shares` (Sector exposure share matrix; default none; top-level `shares`); `shocks` (Sector-level shock vector aligned with shares; default None; top-level `shocks`); `controls` (Included exogenous controls; default None; the specification's `regressors`); `cluster` (Grouping variable for shock-level inference; default None; top-level `cluster`); `weights` (Location observation weights; default None; top-level `weights`); `alpha` (Confidence-set test size; default 0.05; from the specification's confidence level); `leave_one_out` (Whether Bartik shock exposure uses leave-one-out adjustment; default None; fixed by the runner at False).

**Returns.** `params`: Shift-share IV point estimate; `std_errors`: AKM-adjusted standard errors when shock-based inference selected; `akm0_ci_type`: Topology of null-imposed AKM0 confidence set; `shock_data`: Sector-level aggregated estimating data; `rotemberg_weights`: Rotemberg weight decomposition from Bartik implementation.

**Checks before reporting.** Exposure and shock concentration: Inspect shock-level aggregates and Rotemberg contribution weights. Shocks basis: report `effective_shock_count` (inverse sum of squared exposure weights); a small count means a few shocks drive the estimate. Shares basis: report the industries with the largest Rotemberg weights and check balance of baseline characteristics on those shares. Pre-period placebo: regress pre-period outcome changes on the instrument. Report the AKM0 set type with its endpoints, including unbounded sets.

**Pitfalls.** Location-robust covariance can understate uncertainty when sector shocks are shared across locations.

**Sources.** https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/bartik/adao_correction.py, https://doi.org/10.1093/restud/rdab030, https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/bartik/shift_share.py, https://doi.org/10.1093/qje/qjz025.

## Inference: clusters, space and multiple outcomes

### `wild_cluster_bootstrap`

**Use when.** Few clusters, few treated clusters or very unequal cluster sizes, where cluster-robust t tests over-reject: a test and interval for one coefficient of a saved linear model (`fixest_ols`, `ols_r`).

**Versus.** `club_sandwich`: Bootstraps clustered coefficient tests; club_sandwich instead applies cluster-robust sandwich covariance with small-sample tests.

**Estimand.** Bootstrap distribution of a null-imposed regression coefficient test, with p-value and inverted confidence interval.

**Identification.** Specified clusters determine the dependence-preserving bootstrap resampling structure.

**Run.** `method="wild_cluster_bootstrap"` → `fwildclusterboot::boottest` (0.14.3). `data` is the saved result JSON of the fitted model. `seed` also seeds `dqrng`.

**Options.** Required: None. Optional: `args`, `columns`, `definitions`, `seed`.

**Native arguments that change the result.** `param` (Coefficient or linear restriction being tested; default none; via options.args); `B` (Bootstrap replications; required argument; default none; via options.args); `clustid` (Cluster identifiers used in bootstrap; default NULL; via options.args); `type` (Wild-bootstrap weight distribution; default rademacher; via options.args); `impose_null` (Impose the tested null during resampling; default TRUE; via options.args); `bootcluster` (Cluster dimension resampled when multiple cluster variables occur; default max; via options.args).

**Returns.** `p_val`: Wild-bootstrap p-value for test restriction; `conf_int`: Inverted wild-bootstrap confidence interval.

**Checks before reporting.** Number of distinct bootstrap sign patterns: For few clusters, compare B with available Rademacher assignments. Report the number of clusters and of treated clusters. With Rademacher weights there are only 2^G sign patterns; with about 12 clusters or fewer, use Webb weights (`type="webb"`). Keep the null imposed (`impose_null=TRUE`). Report the bootstrap p value and interval next to the clustered standard error, and the `club_sandwich` test.

**Pitfalls.** Small numbers of clusters limit possible Rademacher resampling patterns.

**Sources.** https://s3alfisc.github.io/fwildclusterboot/reference/boottest.fixest.html, https://doi.org/10.1177/1536867X19830877.

### `club_sandwich`

**Use when.** Few or unbalanced clusters: bias-reduced CR2 variance with Satterthwaite degrees of freedom for coefficient tests on a saved model; report next to the wild cluster bootstrap.

**Versus.** `wild_cluster_bootstrap`: Uses sandwich covariance and Satterthwaite degrees of freedom, not wild-cluster resampling.

**Estimand.** Regression coefficient tests using cluster-robust variance estimates and finite-sample reference distributions.

**Identification.** Cluster membership indexes within-cluster correlation for covariance estimation.

**Run.** `method="club_sandwich"` → `clubSandwich::coef_test` (0.7.0). `data` is the saved result JSON; `columns.cluster` binds the saved sample's cluster column; `args.vcov` names the estimator ("CR2").

**Options.** Required: None. Optional: `args`, `columns`, `definitions`, `seed`.

**Native arguments that change the result.** `vcov` (CR variance matrix or variance type used for tests; required argument; default none; via options.args); `test` (Choice of reference test and degrees-of-freedom approximation; default Satterthwaite; via options.args); `coefs` (Coefficient subset; default All; via options.args); `null_constants` (Hypothesized parameter values; default 0; via options.args); `alternative` (One- or two-sided coefficient test; default two-sided; via options.args).

**Returns.** `beta`: Regression coefficient estimate; `SE`: Cluster-robust standard error; `df_Satt`: Satterthwaite approximate degrees of freedom; `p_Satt`: Satterthwaite-reference p-value.

**Checks before reporting.** Small-sample degrees of freedom: Report parameter-specific Satterthwaite degrees of freedom. Report the Satterthwaite degrees of freedom for each tested coefficient. Degrees of freedom below about 4 mean the test is unreliable even with CR2; say so with the result.

**Pitfalls.** Residual degrees of freedom can differ substantially from the parameter-specific small-sample cluster approximation.

**Sources.** https://cran.r-project.org/web/packages/clubSandwich/refman/clubSandwich.html, https://doi.org/10.1080/07350015.2016.1247004.

### `spatial_conley`

**Use when.** Units are places (counties, grid cells, plants with coordinates) and shocks spread across neighbours, so errors correlate by distance rather than within administrative clusters.

**Versus.** `club_sandwich`: Uses a spatial-distance kernel rather than a discrete cluster membership covariance.

**Estimand.** V = (X'X)^(-1) Omega (X'X)^(-1), where Omega weights residual cross-products by spatial proximity.

**Identification.** Covariance is accumulated over spatial dependence within the selected distance cutoff.

**Run.** `method="spatial_conley"` → `statspai.regression.ols.regress`, `statspai.inference.conley.conley` (git:ddb3b45f2d3fc649ea794aa15f8989bb10f8e543). Coordinates are in degrees and `dist_cutoff` in kilometres. A panel needs `time`, `panel_unit` and `lag_cutoff` together.

**Options.** Required: `dist_cutoff`, `distance`, `kernel`, `lat`, `lon`. Optional: `definitions`, `lag_cutoff`, `lag_cutoff_cross`, `panel_unit`, `time`, `time_kernel`.

**Native arguments that change the result.** `dist_cutoff` (Distance beyond which spatial covariance is zero, in kilometers; default none; top-level option); `kernel` (Spatial distance weighting function; default uniform; top-level option); `distance` (Great-circle or alternative distance calculation; default haversine; top-level option); `lag_cutoff` (Maximum temporal dependence lag if time information is supplied; default None; top-level option); `lag_cutoff_cross` (Cross-unit temporal covariance lag; default None; top-level option); `time_kernel` (Time-distance covariance kernel; default bartlett; top-level option).

**Returns.** `params`: Estimated OLS regression coefficients; `std_errors`: Conley HAC coefficient standard errors; `pvalues`: Coefficient p-values under HAC inference; `cov_params`: Full estimated spatial-HAC covariance matrix; `diagnostics`: Spatial covariance calculation diagnostics.

**Checks before reporting.** Distance cutoff and kernel: Report the adopted distance cutoff and weighting kernel. Fix the headline cutoff from the spatial reach of the shock before results. Report standard errors over a grid of cutoffs around the headline value. In a panel, set a temporal cutoff; spatial-only covariance ignores serial correlation.

**Pitfalls.** Spatial-only inference omits noncontemporaneous temporal correlation unless a temporal cutoff is provided.

**Sources.** https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/inference/conley.py.

### `romano_wolf`

**Use when.** Several outcomes test one hypothesis (a set of labour-market outcomes of one programme, components of a wellbeing index); family-wise error control that uses the correlation among outcomes, so less conservative than `holm`.

**Versus.** `holm`: Uses joint bootstrap dependence in stepdown adjustment; Holm uses ordered marginal p-values.

**Estimand.** Stepdown family-wise-error-adjusted p-values for a jointly resampled family of coefficient tests.

**Identification.** Bootstrap resampling reflects dependence among the tested statistics.

**Run.** `method="romano_wolf"` → `StatsPAI` `statspai.mht.romano_wolf.romano_wolf` (git:ddb3b45f2d3fc649ea794aa15f8989bb10f8e543). Numeric `regressors` are common controls; `family` must be declared with `status="prespecified"` for confirmatory claims.

**Options.** Required: `family`, `n_boot`, `outcomes`, `seed`, `treatment`. Optional: `cluster`, `definitions`.

**Native arguments that change the result.** `n_boot` (Number of joint bootstrap draws; default 1000; top-level `n_boot`); `cluster` (Optional resampling-cluster column; default None; top-level `cluster`); `seed` (Random seed for bootstrap draws; default None; top-level `seed`); `alpha` (Nominal family-wise significance level; default 0.05; from the specification's confidence level).

**Returns.** `p_rw`: Romano–Wolf adjusted p-values; `p_value`: Unadjusted p-values; `p_holm`: Holm stepdown adjusted p-values; `coef`: Outcome-specific treatment coefficients; `se`: Outcome-specific coefficient standard errors.

**Checks before reporting.** Completed joint bootstrap draws: Check whether any draws were discarded for unidentified coefficients. The family and the primary outcome are named before results. `n_boot` of at least 1000 for reported p values. A warning about discarded bootstrap draws is reported with the count.

**Pitfalls.** Bootstrap draws producing unidentified coefficients are discarded.

**Sources.** https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/mht/romano_wolf.py.

### `holm`

**Use when.** Adjust p values already saved from separate estimates (different samples or models) when no joint resampling is available.

**Versus.** `romano_wolf`: Applies Holm correction without resampling the joint distribution of test statistics.

**Estimand.** Holm stepdown family-wise-error-adjusted p-values and associated null-rejection indicators.

**Identification.** Each supplied marginal p-value is valid for its individual null hypothesis.

**Run.** `method="holm"` → `statsmodels` `statsmodels.stats.multitest.multipletests` (0.14.6). `data` is a saved result JSON; `p_values` maps hypothesis names to JSON key paths.

**Options.** Required: `family`, `p_values`. Optional: `definitions`.

**Native arguments that change the result.** `alpha` (Family-wise test significance level; default 0.05; from the specification's confidence level); `method` (Correction method; default hs; fixed by the runner at holm; the package default hs is Holm–Šidák); `is_sorted` (Input p-values already sorted ascending; default False; fixed by the runner at False).

**Returns.** `reject`: Corrected multiple-test rejection decisions; `pvals_corrected`: Holm-adjusted p-values; `alphacBonf`: Bonferroni-corrected family significance threshold.

**Checks before reporting.** Family-wise rejection: Compare each Holm-adjusted p-value with alpha. The family is named before results and every test of it is in `p_values`.

**Pitfalls.** Correction applies to the supplied p-value family; omitted tests do not enter multiplicity adjustment.

**Sources.** https://www.statsmodels.org/v0.14.6/generated/statsmodels.stats.multitest.multipletests.html, https://doi.org/10.1111/j.2517-6161.1979.tb01084.x.

