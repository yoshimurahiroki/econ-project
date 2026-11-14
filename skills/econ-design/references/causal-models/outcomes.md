# Selection, duration, decomposition and bunching

Four estimators for outcomes that need their own model: outcomes observed only for a selected group, durations with censoring, mean gaps between two groups, and excess mass at a kink. Every method runs through `python3 skills/econ-data/scripts/research_causal.py run SPEC.json --output RESULT.json` with the shared fields of the [specification and result](contract.md#specification-and-result). Each card gives: when to use it, the identifying conditions, the run settings, the options, the saved output, the checks before reporting, and what the interface does not cover.

## Heckman sample selection

**Use when** the outcome is observed only for a selected group (wages of workers, prices of traded goods) and the target is the latent-outcome coefficient.

**Model and identification.** Selection S = 1{W′γ + u > 0}; outcome Y* = X′β + ε, observed when S = 1; (u, ε) jointly normal with Var(u) = 1, Var(ε) = σ², Cov(u, ε) = ρσ. At least one variable in W is excluded from X, and the worksheet states why it moves selection and not the outcome.

**Run.**

| Setting | Value |
| --- | --- |
| Selection | `design="sample_selection"`, target `structural_parameter` or `conditional_mean`; conditions `outcome_support="continuous"`, `joint_gaussian_errors=true`, `exclusion=true`, `iid=true` |
| Method | `method="heckman"`, `inference={"type":"official"}` |
| Dependence and weights | `dependence="independent"`, unweighted, pointwise inference |

**Options.**

| Option | Meaning |
| --- | --- |
| `selection` | binary 0/1 selection column |
| `selection_regressors` | selection covariates; those absent from `regressors` are the exclusion set and must be nonempty |
| `estimation_method` | `"2step"` or `"ml"` |
| `definitions` | the adopted conditions |
| `confidence_level` | default 0.95 |

`regressors` holds the outcome covariates; both equations get an intercept; `endogenous`, `instruments`, `args` and `columns` stay empty.

**Sample.** Keep the whole selection population in the table: selection indicator and selection regressors finite for every eligible row; outcome and outcome regressors finite where `selection=1`; outcomes of unselected rows stay missing. Apply sample restrictions before the call. Saved IDs: `sample.included_ids`, `selection_ids`, `observed_outcome_ids`, `unselected_ids`.

**Output.** All coefficients by equation, the inverse-Mills coefficient ρσ (two-step) with covariance corrected for the first stage, σ and ρ, the full covariance (`NA` kept as `null`), Student-t intervals with the native degrees of freedom, the native fit, and for ML the joint log-likelihood.

**Checks.** Optimizer return code 1, 2 or 8 (`maxLik::returnCode`), the number of iterations, a full-rank outcome regression, and the size and sign of ρ against the economic story of selection.

**Not covered.** Discrete outcomes, sampling weights, clustered inference.

**Source.** `sampleSelection` 1.2-16 ([selection](https://github.com/cran/sampleSelection/blob/5115e01a03d09a46ac1b92813c785c5799b4d654/R/selection.R), [two-step](https://github.com/cran/sampleSelection/blob/5115e01a03d09a46ac1b92813c785c5799b4d654/R/heckit2fit.R), [ML](https://github.com/cran/sampleSelection/blob/5115e01a03d09a46ac1b92813c785c5799b4d654/R/tobit2fit.R)) with dependencies `miscTools`, `systemfit`, `Formula`, `VGAM`, `mvtnorm`, `maxLik`.

## Duration and proportional hazards

**Use when** the outcome is a time to an event with right censoring (unemployment spells, firm survival, time to adoption) and the target is a hazard ratio.

**Model and identification.** h(t | X, stratum) = h₀,stratum(t) · exp(X′β + offset); proportional hazards and censoring or truncation independent of the event given X identify β as conditional log hazard ratios.

**Run.**

| Setting | Value |
| --- | --- |
| Selection | `design="survival"`, target `log_hazard_ratio` or `hazard_ratio` |
| Method | `method="survival"` (`statsmodels` `PHReg`) |
| Inference | `{"type":"official"}` (likelihood) or `{"type":"cluster","cluster":"<column>"}` (group sandwich) |

**Options.**

| Option | Meaning |
| --- | --- |
| `status` | 1 = event, 0 = right-censored |
| `ties` | `breslow` or `efron` |
| `entry`, `strata`, `offset` | optional columns; entry ≤ duration |
| `maxiter`, `tol` | Newton settings, default 100 and 1e-8 |
| `effect_scale` | `log_hazard` or `hazard_ratio` for the display |

`outcome` is the nonnegative duration; `regressors` are numeric, without an intercept; `definitions.duration_unit` names the time unit.

**Sample.** Strata without events and rows outside an event risk set leave the fit (`excluded_engine_ids`). With clustered inference every complete row must enter a risk set; restrict the sample first, or the runner stops.

**Output.** Coefficients and covariance on the log-hazard scale (both scales labelled), likelihood, score, event count, ties, and `displays.baseline_survival` with each stratum's baseline survival and cumulative hazard just before each event time.

**Checks.** Convergence, finite inference, the number of events per covariate, and the proportional-hazards assumption (log-log survival curves by group or time-interacted covariates).

**Not covered.** Observation weights, simultaneous intervals, time-varying covariates in counting-process form.

**Source.** [statsmodels 0.14.6 PHReg](https://github.com/statsmodels/statsmodels/blob/40e6a84d26ac74623c6b94b718f0987ef0351c53/statsmodels/duration/hazard_regression.py).

## Oaxaca–Blinder mean decomposition

**Use when** a mean gap between two groups (wages by gender, prices by region) is split into a part explained by characteristics and a part from different coefficients. The decomposition is descriptive; a causal reading needs its own design.

**Definitions.** Two-fold with reference coefficients β_ref: explained = (x̄₁ − x̄₂)β_ref; unexplained = x̄₁(β₁ − β_ref) + x̄₂(β_ref − β₂). Three-fold with group 2 as reference: endowments = (x̄₁ − x̄₂)β₂; coefficients = x̄₂(β₁ − β₂); interaction = (x̄₁ − x̄₂)(β₁ − β₂).

**Run.** `method="oaxaca"`, selection `design="oaxaca"` with target `mean_decomposition`, `inference={"type":"official"}` (row bootstrap).

**Options.**

| Option | Meaning |
| --- | --- |
| `group`, `group_order` | group column and the two labels as strings, first minus second (kept even when the first mean is smaller) |
| `decomposition` | `two_fold` or `three_fold` |
| `two_fold_type` | `pooled` (with group indicator), `nuemark` (pooled without it), `cotton` (sample shares), `reimers` (equal weights), `self_submitted` with `submitted_weight` |
| `bootstrap` | `{"n": ≥2, "conf": c, "seed": s}` |

**Output.** Gap, group means, coefficients and regressor means, each component, the sum residual, and bootstrap standard deviations computed over the central slice of sorted draws defined by `conf` (no confidence endpoints, no joint covariance, no standard error for the gap).

**Checks.** Full-rank design and positive residual degrees of freedom in each group; the components add up to the gap; the reference choice is written in the worksheet because it changes the split.

**Not covered.** Sampling weights, cluster resampling, a chosen interval level, nonlinear decompositions.

**Source.** [statsmodels 0.14.6 OaxacaBlinder](https://github.com/statsmodels/statsmodels/blob/40e6a84d26ac74623c6b94b718f0987ef0351c53/statsmodels/stats/oaxaca.py).

## Bunching at a kink

**Use when** a budget-set kink (tax bracket, benefit phase-out) produces excess mass in the distribution of the choice variable and the target is the excess mass or the implied elasticity.

**Identification.** A smooth counterfactual density fitted outside the excluded window gives the excess mass; the elasticity adds the tax rates on both sides and the package's behavioral mapping.

**Run.** `method="bunching"` through the official R runner (`bunching::bunchit`), selection target `bunching_mass` or `elasticity`, `inference={"type":"official"}` (residual bootstrap over binned counts).

**Options.**

| Option | Meaning |
| --- | --- |
| `seed` | nonnegative integer, passed to the native call |
| `definitions.running_unit` | unit of the running variable |
| `args.zstar`, `binwidth`, `bins_l`, `bins_r` | kink and binning window |
| `args.poly` | degree of the counterfactual polynomial |
| `args.t0`, `args.t1` | marginal tax rates below and above the kink |
| `args.n_boot` | bootstrap draws, default 100, at least 2 |
| `quantity` | `b` or `e` for the main display |

`outcome` is the unbinned variable; `regressors`, `endogenous` and `instruments` are empty. Exclusion bins, extra fixed effects, round-number controls and the integration correction pass through `args`.

**Output.** B (excess count), b (B over the mean counterfactual bin count in the excluded window), e (elasticity) and the marginal buncher, each with bootstrap draws and standard deviation (rounded to nine decimals by the package); `displays.bunching_density` with bin coordinates, observed and counterfactual counts. The sample is reported as binned counts (`included_ids_available=false`).

**Checks.** Sensitivity of b to the polynomial degree and the excluded window; round-number heaping near the kink; the counterfactual fit outside the window.

**Not covered.** Notches (`notch=true` is rejected), sampling weights, cluster resampling, confidence intervals.

**Source.** `bunching` 0.8.6 ([bunchit](https://github.com/cran/bunching/blob/8869c136e3b1d3075a117c4d422efa9cf5c2ef16/R/bunchit.R), [fit](https://github.com/cran/bunching/blob/8869c136e3b1d3075a117c4d422efa9cf5c2ef16/R/fit_bunching.R), [bootstrap](https://github.com/cran/bunching/blob/8869c136e3b1d3075a117c4d422efa9cf5c2ef16/R/do_bootstrap.R)).
