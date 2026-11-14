# Difference-in-differences and synthetic control

Method cards for the difference-in-differences, event-study and synthetic-control methods run by `python3 skills/econ-data/scripts/research_causal.py run SPEC.json --output RESULT.json`. The shared specification fields are in [specification and result](contract.md#specification-and-result); R methods take `inference={"type":"official"}` and pass native arguments through `options.args`. Each card gives when to use the method, how it differs from its neighbours, the estimand, the identifying conditions, the runner call and options (checked against the code), the native arguments that change the result, the returns, the checks before reporting, documented pitfalls and sources.

## Which method

| Treatment pattern and target | Method |
| --- | --- |
| Two periods, one treated group, panel; ATT with covariates | `drdid_panel` |
| Two periods, one treated group, repeated cross sections | `drdid_rc` |
| Two periods, several treatments switched on together | `multitreatment_did` |
| Staggered, absorbing, binary; cohort-time ATT(g,t) and aggregations | `staggered_did` (headline); `did_imputation` or `did2s` (imputation-based); `sunab` (fixest regression) |
| Several of these estimators side by side on one event-time axis | `fixes_event_study` |
| Horizon-specific effects with clean controls only | `lp_did` |
| Where an inherited TWFE coefficient comes from | `bacon` (diagnostic, not a headline estimate) |
| Treatment switches on and off, or is non-binary | `did_multiplegt_dyn`; `nonabs_did` to compare estimators |
| Fixed continuous dose per unit | `continuous_did` |
| Effects on quantiles or the whole distribution | `quantile_did` (parallel trends in quantiles); `changes_in_changes` (monotone outcome model) |
| Sensitivity of an event study to violations of parallel trends | `honest_did` |
| One treated unit, donor pool, long pre-period | `synthetic_control`; `scm_diagnostics` for fit and placebo checks |
| A treated block adopting at one date, many controls | `synthdid` |
| Several treated units, different dates, factor structure | `generalized_synth` |

## Two-period and multiple-treatment designs

### `drdid_panel`

**Use when.** Two periods, a panel of the same units, one treated group; the target is the ATT under conditional parallel trends with covariates.

**Versus.** `drdid_rc`: Uses matched pre/post unit outcomes.

**Estimand.** Average treatment effect on the treated (ATT) from a locally efficient doubly robust DiD estimator.

**Identification.** Conditional parallel trends for the untreated potential outcome. Overlap in treatment propensity for covariate values.

**Run.** `method="drdid_panel"` → `DRDID::drdid_panel` (1.4.0).

**Options.** Required: `entity`, `post`, `pre`, `time`, `treatment`. Optional: `args`, `columns`, `definitions`, `seed`.

**Native arguments that change the result.** `covariates` (Pre-period matrix entering propensity-score and outcome models; default none; via options.args); `i.weights` (Normalized observation weights; default NULL; via options.args); `boot` (Bootstrap standard errors; default FALSE; via options.args); `boot.type` (Weighted or multiplier bootstrap; default weighted; via options.args); `nboot` (Number of bootstrap replications when enabled; default NULL; via options.args); `trim.level` (Propensity-score overlap trimming cutoff; default 0.995; via options.args).

**Returns.** `ATT`: Average treatment effect on treated units; `se`: Estimated standard error; `att.inf.func`: Influence function when inffunc=TRUE.

**Pitfalls.** Group indicators require 1 for treated and 0 for comparison units.

**Sources.** https://cran.r-project.org/web/packages/DRDID/refman/DRDID.html, https://cran.r-project.org/web/packages/DRDID/news/news.html.

### `drdid_rc`

**Use when.** Two periods observed as repeated cross sections with one treated group; the target is the ATT under conditional parallel trends with covariates.

**Versus.** `drdid_panel`: Uses independent pre/post cross-section observations.

**Estimand.** Average treatment effect on the treated (ATT) from a locally efficient doubly robust DiD estimator.

**Identification.** Conditional parallel trends for the untreated potential outcome. Overlap in treatment propensity for covariate values.

**Run.** `method="drdid_rc"` → `DRDID::drdid_rc` (1.4.0).

**Options.** Required: `post`, `pre`, `time`, `treatment`. Optional: `args`, `columns`, `definitions`, `seed`.

**Native arguments that change the result.** `covariates` (Covariate matrix entering propensity-score and outcome regressions; default none; via options.args); `i.weights` (Normalized observation weights; default NULL; via options.args); `boot` (Bootstrap standard errors; default FALSE; via options.args); `boot.type` (Weighted or multiplier bootstrap; default weighted; via options.args); `nboot` (Number of bootstrap replications when enabled; default NULL; via options.args); `trim.level` (Propensity-score overlap trimming cutoff; default 0.995; via options.args).

**Returns.** `ATT`: Average treatment effect on treated units; `se`: Estimated standard error; `att.inf.func`: Influence function when inffunc=TRUE.

**Pitfalls.** Group indicators require 1 for treated and 0 for comparison units.

**Sources.** https://cran.r-project.org/web/packages/DRDID/refman/DRDID.html, https://cran.r-project.org/web/packages/DRDID/news/news.html.

### `multitreatment_did`

**Use when.** Two periods and several treatments switched on between them; the target is each treatment's coefficient in the first-difference regression with pre-period controls.

**Estimand.** Coefficients of the treatment vector in the regression of post-minus-pre outcomes on the treatments and pre-period controls.

**Identification.** Conditional parallel trends for each treatment, joint support of the treatment combinations, and additive effects.

**Run.** `method="multitreatment_did"` → `statsmodels` `OLS.fit` (0.14.6). The runner differences the outcome, requires every treatment to be zero before, and uses pre-period controls.

**Options.** Required: `entity`, `post`, `pre`, `time`, `treatments`. Optional: None.

**Native arguments that change the result.** `endog` (Dependent response vector for OLS; default none; built by the runner (post minus pre outcome)); `exog` (Regression design matrix, including treatment doses and controls; default none; built by the runner (treatments and pre-period controls)).

**Returns.** `params`: OLS coefficient estimates; `bse`: Standard errors of estimated regression coefficients.

**Sources.** https://www.statsmodels.org/v0.14.6/generated/statsmodels.regression.linear_model.OLS.html.

## Staggered adoption

### `staggered_did`

**Use when.** Binary treatment adopted at different dates and never reversed; the target is the cohort-time ATT(g,t) and its event-time, cohort or overall aggregation.

**Versus.** `sunab`: Uses group-time ATT(g,t) identification and selectable never- or not-yet-treated comparisons. `continuous_did`: Treatment is indexed by adoption cohort; contdid additionally indexes treatment effects by dose.

**Estimand.** Group-time average treatment effects ATT(g,t), aggregated by cohort, calendar period, event time, or overall.

**Identification.** Conditional parallel trends in untreated potential outcomes for treated cohorts and comparison groups. No treatment anticipation beyond the specified anticipation period.

**Run.** `method="staggered_did"` → `did::att_gt; aggte` (2.5.1).

**Options.** Required: `cohort`, `control_group`, `entity`, `time`. Optional: `aggregation`, `allow_unbalanced_panel`, `alp`, `anticipation`, `base_period`, `biters`, `bstrap`, `cband`, `clustervars`, `est_method`, `faster_mode`, `fix_weights`, `panel`, `seed`, `weightsname`.

**Native arguments that change the result.** `control_group` (Comparison cohort: never-treated or not-yet-treated; default nevertreated; top-level option); `est_method` (First-step estimator: doubly robust, inverse-probability weighting, or regression; default dr; top-level option); `base_period` (Base period for pre-treatment ATT(g,t); default varying; top-level option); `anticipation` (Number of periods before onset with possible anticipation; default 0; top-level option); `type` (ATT(g,t) aggregation: simple, dynamic, group, or calendar; default group; fixed by the runner); `clustervars` (One or two variables defining clustered inference; default NULL; top-level option); `bstrap` (Use multiplier bootstrap for inference; default TRUE; top-level option).

**Returns.** `att`: Estimated ATT(g,t) by cohort and period; `overall.att`: Overall aggregated average treatment effect; `egt`: Relative treatment times for dynamic aggregation.

**Checks before reporting.** Pre-treatment conditional parallel-trends test: Pre-treatment test p-value from att_gt. State the comparison group (never-treated or not-yet-treated) and the base period. Use base_period="universal" when the event-study coefficients feed honest_did.

**Pitfalls.** TWFE estimators can use already-treated cohorts as comparisons with heterogeneous effects.

**Sources.** https://cran.r-universe.dev/did/doc/manual.html.

### `sunab`

**Use when.** Staggered absorbing adoption with unit and time fixed effects already in the specification; the target is cohort-weighted event-time effects from one fixest regression.

**Versus.** `staggered_did`: Creates Sun-Abraham cohort-by-event-time interactions; did computes ATT(g,t) using configurable comparison groups.

**Estimand.** Interaction-weighted cohort-relative-period treatment effects, aggregated to event-time average treatment effects.

**Identification.** Cohorts selected as references are untreated comparison cohorts.

**Run.** `method="sunab"` → `fixest::feols; sunab` (0.14.2).

**Options.** Required: `cohort`, `entity`, `time`. Optional: `aggregation`, `args`, `columns`, `confidence_level`, `definitions`, `fixed_effects`, `never_treated`, `seed`, `sunab`.

**Native arguments that change the result.** `ref.c` (Reference cohorts excluded from interaction dummies; default NULL; via options.args); `ref.p` (Reference relative periods; default -1; via options.args); `bin.rel` (Bin relative periods into specified categories; default none; via options.args); `att` (Aggregate effects into an ATT instead of event-study coefficients; default FALSE; via options.args); `no_agg` (Retain cohort-by-period interaction coefficients without aggregation; default FALSE; via options.args).

**Returns.** `coef`: Cohort-period or aggregated event-time coefficients in the fitted feols object.

**Pitfalls.** Always-treated cohorts are excluded; cohort coding must distinguish never-treated and always-treated units. At least two reference periods are required.

**Sources.** https://lrberge.github.io/fixest/reference/sunab.html.

### `did_imputation`

**Use when.** Staggered adoption where the untreated outcome model is fitted on untreated observations and imputed for treated cells; the target is a weighted average of treated-cell effects.

**Versus.** `did2s`: Imputes untreated potential outcomes before averaging treated residuals; did2s fits second-stage treatment-effect regressions.

**Estimand.** Weighted average treatment effects for treated observations using imputed untreated potential outcomes.

**Identification.** The untreated-outcome model fitted on untreated observations identifies treated units’ untreated potential outcomes.

**Run.** `method="did_imputation"` → `didimputation::did_imputation` (0.6.0).

**Options.** Required: `cohort`, `entity`, `time`. Optional: `args`, `columns`, `definitions`, `seed`.

**Native arguments that change the result.** `first_stage` (Untreated-outcome regression specification; default NULL; via options.args); `wname` (Variable for observation estimation weights; default NULL; via options.args); `wtr` (Variables defining treatment-effect weights; default NULL; via options.args); `horizon` (Relative times over which to report treatment effects; default NULL; via options.args); `cluster_var` (Cluster variable for standard errors; default NULL; via options.args); `leaveout` (Leave-out variance correction; default FALSE; via options.args).

**Returns.** `term`: Relative-time or aggregate treatment effect label; `estimate`: Imputation-based treatment effect estimate; `std.error`: Standard error of estimated treatment effect.

**Checks before reporting.** Separate pre-trend regression: pretrends is a test-only option and leaves primary estimates unchanged.

**Sources.** https://kylebutts.r-universe.dev/didimputation/doc/manual.html.

### `did2s`

**Use when.** Staggered adoption where untreated observations identify unit and time effects; the target is the treated-observation average or event-time effects, with the two-stage variance correction.

**Versus.** `did_imputation`: Second-stage treatment regressors use first-stage residualized outcomes; did_imputation imputes untreated potential outcomes for treated cells.

**Estimand.** Treatment or event-time coefficients from a two-stage regression residualizing outcomes with untreated observations.

**Identification.** Untreated observations identify the first-stage fixed-effects and covariate model.

**Run.** `method="did2s"` → `did2s::did2s` (1.3.0).

**Options.** Required: `cluster_var`, `first_stage`, `second_stage`, `treatment`. Optional: `args`, `columns`, `confidence_level`, `definitions`, `event_variable`, `reference_event_time`, `seed`.

**Native arguments that change the result.** `first_stage` (Fixed effects and covariates fitted on untreated observations; default none; top-level option); `second_stage` (Treatment or event-time regression specification; default none; top-level option); `weights` (Optional estimation weights; default NULL; via options.args); `bootstrap` (Use bootstrap covariance instead of analytic correction; default FALSE; via options.args); `n_bootstraps` (Number of bootstrap replications; default 250; via options.args); `vcov_method` (Analytic covariance computation backend; default sparse; via options.args).

**Returns.** `fixest`: A fixest model containing treatment coefficients with two-stage-adjusted standard errors.

**Pitfalls.** First-stage estimation must exclude treated observations.

**Sources.** https://kylebutts.r-universe.dev/did2s/doc/manual.html.

### `fixes_event_study`

**Use when.** Event studies where several estimators (TWFE, CS, SA, BJS, TWM, FLEX) are compared on one interface with the same timing and reference period.

**Versus.** `sunab`: Estimator can select SA or five other methods, rather than always constructing Sun-Abraham interactions.

**Estimand.** Dynamic event-time treatment effects from a selected TWFE or staggered-adoption estimator.

**Identification.** Comparison cohorts and anticipation are specified for supported staggered-adoption estimators.

**Run.** `method="fixes_event_study"` → `fixes::event_study` (1.0.0).

**Options.** Required: `cohort`, `entity`, `estimator`, `time`. Optional: `args`, `columns`, `definitions`, `fixed_effects`, `never_treated`, `seed`.

**Native arguments that change the result.** `estimator` (Event-study estimator: twfe, cs, sa, bjs, twm, or flex; default twfe; top-level option); `control_group` (Untreated comparison: never-treated or not-yet-treated; default nevertreated; via options.args); `baseline` (Omitted reference relative period; default -1; via options.args); `cluster` (Cluster specification for covariance; default NULL; via options.args); `weights` (Optional estimation weights; default NULL; via options.args); `boot_reps` (Number of bootstrap replications if bootstrap is enabled; default 999; via options.args).

**Returns.** `estimate`: Estimated treatment effect by relative period; `std.error`: Estimated standard error by relative period; `relative_time`: Event time relative to first treatment.

**Pitfalls.** With irregular calendar spacing, interval and time_transform affect event-time calculation.

**Sources.** https://yo5uke.com/fixes/reference/event_study.html.

### `lp_did`

**Use when.** Staggered adoption where each horizon uses only clean controls; the target is the horizon-specific effect from local projections.

**Versus.** `bacon`: Employs horizon-specific clean controls, whereas Bacon decomposes TWFE coefficients into 2x2 comparison contributions.

**Estimand.** Horizon-specific local-projection difference-in-differences treatment effects based on clean treated-control comparisons.

**Identification.** Clean controls must remain untreated over the horizon of each comparison.

**Run.** `method="lp_did"` → `StatsPAI` `statspai.did.lp_did.lp_did` (git:ddb3b45f2d3fc649ea794aa15f8989bb10f8e543).

**Options.** Required: `entity`, `time`, `treatment`. Optional: `args`, `definitions`, `weights`.

**Pitfalls.** The StatsPAI LP-DiD implementation is described as not verified against the published paper.

**Sources.** https://www.nber.org/papers/w31184, https://github.com/brycewang-stanford/StatsPAI/blob/main/docs/guides/choosing_did_estimator.md.

### `bacon`

**Use when.** A two-way fixed effects DiD coefficient is reported or inherited and the question is which 2x2 comparisons and weights produce it.

**Versus.** `staggered_did`: Decomposes a TWFE coefficient rather than directly estimating cohort-time ATT(g,t).

**Estimand.** TWFE difference-in-differences coefficient as a weighted average of all two-group, two-period DID estimates.

**Identification.** Causal interpretation of TWFE DD requires parallel trends and treatment effects constant over time.

**Run.** `method="bacon"` → `StatsPAI` `statspai.did.bacon.bacon_decomposition` (git:ddb3b45f2d3fc649ea794aa15f8989bb10f8e543).

**Options.** Required: `entity`, `time`, `treatment`. Optional: `args`, `definitions`, `weights`.

**Returns.** `beta_twfe`: TWFE coefficient reconstructed from the decomposition; `decomposition`: Component 2x2 comparisons with weights and estimated effects.

**Checks before reporting.** Decomposition weight shares: Inspect weights for already-treated-versus-later-treated comparisons.

**Pitfalls.** Some 2x2 terms use already-treated cohorts as controls.

**Sources.** https://doi.org/10.1016/j.jeconom.2021.03.014, https://brycewang-stanford.github.io/StatsPAI/guides/mixtape_castle_replication/.

## Switching and continuous treatments

### `did_multiplegt_dyn`

**Use when.** Treatment that is non-binary or switches on and off; the target is the effect of the first treatment change at each horizon among switchers.

**Versus.** `nonabs_did`: Direct DCDH estimator for first-switch designs; nonabs_did also wraps PanelMatch and fect estimators. `staggered_did`: Allows nonbinary and nonabsorbing treatments, not only staggered absorbing adoption.

**Estimand.** Horizon-specific intertemporal average treatment effects of a first treatment change, among switchers.

**Identification.** Parallel trends for untreated potential outcomes within the relevant treatment-history comparison groups.

**Run.** `method="did_multiplegt_dyn"` → `DIDmultiplegtDYN::did_multiplegt_dyn` (2.4.0).

**Options.** Required: `entity`, `time`, `treatment`. Optional: `args`, `columns`, `definitions`, `seed`.

**Native arguments that change the result.** `effects` (Number of post-switch horizons estimated; default 1; via options.args); `placebo` (Number of pre-switch placebo estimates; default 0; via options.args); `normalized` (Normalize effects by treatment-dose changes; default FALSE; via options.args); `controls` (Time-varying control variables; default NULL; via options.args); `only_never_switchers` (Restrict controls to never-switchers; default FALSE; via options.args); `cluster` (Cluster variable; default NULL; via options.args); `same_switchers` (Use same switcher sample at all horizons; default FALSE; via options.args).

**Checks before reporting.** Pre-switch placebo tests: Placebo event-time estimates should be compared with zero under identifying assumptions.

**Sources.** https://cran.r-project.org/web/packages/DIDmultiplegtDYN/refman/DIDmultiplegtDYN.html.

### `nonabs_did`

**Use when.** Binary treatment that switches on and off; one estimator at a time (DCDH, PanelMatch, IFE, FE, MC) on a common event-time axis.

**Versus.** `did_multiplegt_dyn`: Dispatches among several distinct estimators; did_multiplegt_dyn uses the DCDH event-study estimator.

**Estimand.** Event-time estimates from a selected DCDH, PanelMatch, or fect estimator, harmonized to one relative-time scale.

**Identification.** Underlying identification assumptions depend on the selected DCDH, PanelMatch, or fect estimator.

**Run.** `method="nonabs_did"` → `nonabsdid::nabs_event_study` (0.4.1.9000).

**Options.** Required: `entity`, `estimator`, `time`, `treatment`. Optional: `args`, `columns`, `definitions`, `seed`.

**Native arguments that change the result.** `method` (Choose DCDH, PanelMatch, IFE, FE, or MC estimation; default DCDH; via options.args); `lags` (Number of periods after treatment transition; default 6; via options.args); `leads` (Number of periods before treatment transition; default 8; via options.args); `controls` (Optional covariates passed to compatible underlying estimators; default NULL; via options.args); `cluster` (Variable for clustered standard errors; default unit; via options.args).

**Returns.** `time`: Unified relative event time; `estimate`: Underlying estimator treatment-effect estimate; `std.error`: Estimated standard error.

**Pitfalls.** Different underlying methods have differing estimands, comparisons, and cohort coverage. Upstream estimator output structures may change; the project advises pinning versions.

**Sources.** https://takuma1102.r-universe.dev/nonabsdid/doc/manual.html, https://takuma1102.github.io/nonabsdid/.

### `continuous_did`

**Use when.** Each unit has a fixed treatment dose, adoption common or staggered; the target is the dose response ATT(d) or the marginal response ACRT(d).

**Versus.** `staggered_did`: Estimates dose-response ATT(d) or causal-response ACRT(d); staggered_did identifies cohort-time ATT(g,t).

**Estimand.** Dose-specific ATT(d) or average causal response ACRT(d), selected by target_parameter.

**Identification.** ATT(d) requires parallel trends in untreated outcomes; ACRT(d) additionally requires strong parallel trends across doses (Callaway, Goodman-Bacon and Sant'Anna).

**Run.** `method="continuous_did"` → `contdid::cont_did` (0.1.2).

**Options.** Required: `cohort`, `definitions`, `dose`, `entity`, `seed`, `time`. Optional: `args`, `columns`, `plot`, `quantity`.

**Native arguments that change the result.** `target_parameter` (Dose-response level or causal-response slope; default level; via options.args); `aggregation` (Dose or event-study aggregation; the none option is not implemented; default dose; via options.args); `dose_est_method` (Parametric B-spline or CCK nonparametric estimation; default parametric; via options.args); `degree` (Polynomial degree for dose-response splines; default 3; via options.args); `num_knots` (Number of dose spline knots; default 0; via options.args); `control_group` (Not-yet-, never-, or eventually-treated comparisons; default notyettreated; via options.args); `biters` (Multiplier bootstrap repetitions; default 1000; via options.args).

**Pitfalls.** The dose variable must be constant over time within each unit, even before adoption. The aggregation=none mode and treatment_type=discrete are currently unsupported.

**Sources.** https://cran.r-project.org/web/packages/contdid/refman/contdid.html, https://arxiv.org/abs/2107.02637.

## Distributional effects

### `quantile_did`

**Use when.** Staggered or two-period adoption and the target is the effect on quantiles of the treated group's outcome distribution.

**Versus.** `changes_in_changes`: Uses Quantile Difference-in-Differences identifying strategy for counterfactual outcome distributions.

**Estimand.** Quantile treatment effect on the treated, QTT(τ), and the group-time ATT.

**Identification.** Parallel trends in the untreated outcome quantiles at each rank, no anticipation, and stable comparison populations.

**Run.** `method="quantile_did"` → `qte::qdid` (2.0.0).

**Options.** Required: `cohort`, `entity`, `seed`, `time`. Optional: `aggregation`, `args`, `columns`, `definitions`, `distribution_grid`.

**Native arguments that change the result.** `gt_type` (Group-time average ATT or quantile QTT curve; default att; via options.args); `control_group` (Not-yet-treated or never-treated comparison cohorts; default notyettreated; via options.args); `panel` (Use panel rather than repeated-cross-section estimator; default TRUE; via options.args); `probs` (QTT quantile grid; the NULL default resolves internally to seq(0.05,0.95,0.05); default NULL; via options.args); `biters` (Bootstrap replications for inference; default 100; via options.args); `cband` (Uniform band rather than pointwise inference; default TRUE; via options.args); `weightsname` (Sampling weight column; default NULL; via options.args).

**Returns.** `pte_qtt`: Overall, group-specific, and dynamic QTT curves with bootstrap standard errors; `pte_results`: Group-time ATT estimates when gt_type="att".

**Sources.** https://cran.r-project.org/web/packages/qte/refman/qte.html.

### `changes_in_changes`

**Use when.** Staggered or two-period adoption, a continuous outcome, and the target is the treated group's counterfactual distribution under a monotone outcome model.

**Versus.** `quantile_did`: Uses Change in Changes identifying strategy for counterfactual outcome distributions.

**Estimand.** Quantile treatment effect on the treated, QTT(τ), from the changes-in-changes counterfactual distribution.

**Identification.** Untreated outcome strictly increasing in a scalar unobservable whose distribution is time-invariant within each group, with support conditions (Athey and Imbens 2006).

**Run.** `method="changes_in_changes"` → `qte::cic` (2.0.0).

**Options.** Required: `cohort`, `entity`, `seed`, `time`. Optional: `aggregation`, `args`, `columns`, `definitions`, `distribution_grid`.

**Native arguments that change the result.** `gt_type` (Group-time average ATT or quantile QTT curve; default att; via options.args); `control_group` (Not-yet-treated or never-treated comparison cohorts; default notyettreated; via options.args); `panel` (Use panel rather than repeated-cross-section estimator; default TRUE; via options.args); `probs` (QTT quantile grid; the NULL default resolves internally to seq(0.05,0.95,0.05); default NULL; via options.args); `biters` (Bootstrap replications for inference; default 100; via options.args); `cband` (Uniform band rather than pointwise inference; default TRUE; via options.args); `weightsname` (Sampling weight column; default NULL; via options.args).

**Returns.** `pte_qtt`: Overall, group-specific, and dynamic QTT curves with bootstrap standard errors; `pte_results`: Group-time ATT estimates when gt_type="att".

**Sources.** https://cran.r-project.org/web/packages/qte/refman/qte.html, https://doi.org/10.1111/j.1468-0262.2006.00668.x.

## Sensitivity to parallel trends

### `honest_did`

**Use when.** An event study is estimated and the conclusion must be checked against bounded violations of parallel trends.

**Versus.** `staggered_did`: Constructs sensitivity confidence sets from existing event-study coefficients rather than estimating ATT(g,t) from panel observations.

**Estimand.** Scalar target theta = l_vec'tau with robust confidence sets under Delta^RM(Mbar) or Delta^SDRM(Mbar) restrictions.

**Identification.** Post-treatment parallel-trends violations are constrained relative to pre-treatment differences by the chosen Delta set.

**Run.** `method="honest_did"` → `HonestDiD::createSensitivityResults_relativeMagnitudes` (0.2.8). Input is the saved event-study coefficients with their full covariance; from staggered_did they require base_period="universal".

**Options.** Required: `post_terms`, `pre_terms`, `restriction`. Optional: `args`, `columns`, `definitions`, `seed`.

**Native arguments that change the result.** `bound` (Use deviations from parallel or linear trends; default deviation from parallel trends; via options.args); `method` (Robust interval construction method; default C-LF; via options.args); `Mbarvec` (Sensitivity bounds to evaluate; default NULL; via options.args); `l_vec` (Linear combination of post-treatment effects defining target parameter; default first basis vector; via options.args); `monotonicityDirection` (Optional monotonicity restriction on deviations; default NULL; via options.args); `biasDirection` (Optional sign restriction on deviations; default NULL; via options.args); `alpha` (Significance level for robust confidence sets; default 0.05; via options.args).

**Returns.** `lb`: Lower bound of robust confidence interval; `ub`: Upper bound of robust confidence interval; `M`: Corresponding sensitivity magnitude.

**Checks before reporting.** Sensitivity breakdown over Mbar: Evaluate when robust intervals include the null value.

**Pitfalls.** Linear-trend-deviation bounds require more than one pre-treatment period.

**Sources.** https://cran.r-project.org/web/packages/HonestDiD/refman/HonestDiD.html.

## Synthetic control

### `synthetic_control`

**Use when.** One treated unit, a donor pool and a long pre-period; the target is the post-treatment gap between the treated unit and its synthetic control.

**Versus.** `generalized_synth`: Uses donor-weighted synthetic control for a single treated unit, not interactive fixed effects for several treated units.

**Estimand.** Treated-minus-synthetic-control outcome gap using a convex combination of untreated donor units.

**Identification.** A weighted combination of untreated donors approximates treated-unit preintervention predictors and outcomes.

**Run.** `method="synthetic_control"` → `pysyncon; statsmodels` `Synth.fit; OLS.fit` (pysyncon=1.7.0; statsmodels=0.14.6). The runner splits the pre-period into training (up to training_end) and validation (up to pre_end) for the predictor weights.

**Options.** Required: `entity`, `pre_end`, `time`, `training_end`, `treated`. Optional: None.

**Native arguments that change the result.** `X0` (Donor-unit pre-intervention predictor matrix; default none; built by the runner from the panel); `X1` (Treated-unit pre-intervention predictor vector; default none; built by the runner from the panel); `Z0` (Donor-unit pre-intervention outcomes; default none; built by the runner from the panel); `Z1` (Treated-unit pre-intervention outcomes; default none; built by the runner from the panel); `custom_V` (User-specified predictor importance matrix; default None; fixed by the runner (data-driven V)).

**Checks before reporting.** Pre-intervention donor fit: Compare preintervention treated outcomes with the synthetic control. Treated unit and donor pool fixed before estimation, with each excluded donor and its reason saved in `definitions`. Inference comes from placebos run with `scm_diagnostics` (in-space and in-time), not from the OLS standard error.

**Sources.** https://sdfordham.github.io/pysyncon/synth.html.

### `scm_diagnostics`

**Use when.** A single treated unit and the question is whether the synthetic control fit and placebo distribution support the estimated gap.

**Versus.** `synthetic_control`: Uses StatsPAI classic synthetic control and native placebo diagnostics; synthetic_control fits pysyncon donor weights.

**Estimand.** Post-treatment treated-minus-synthetic-control gap for a single treated unit.

**Identification.** Classic synthetic control requires a credible donor-weighted pre-treatment match.

**Run.** `method="scm_diagnostics"` → `StatsPAI` `statspai.synth.scm.synth` (git:ddb3b45f2d3fc649ea794aa15f8989bb10f8e543).

**Options.** Required: `entity`, `time`, `treated`, `treatment_time`. Optional: `args`, `definitions`, `weights`.

**Native arguments that change the result.** `method` (Select classic synthetic control; default classic; via options.args); `treatment_time` (Intervention onset separating pre- and post-treatment observations; default none; top-level option); `covariates` (Optional outcome-predictor covariate list; default none; via options.args).

**Checks before reporting.** Pre-treatment RMSPE: Poor fit flagged when pre-treatment RMSPE exceeds post-treatment effect. Placebo inference: Placebo p-value >= 0.1 triggers AssumptionWarning even with visible gap. Treated unit and donor pool fixed before estimation, with each excluded donor and its reason saved in `definitions`. In-space placebos (`args.placebo_units`) and an in-time placebo (`args.placebo_time`, a false treatment date inside the pre-period) are both reported, with leave-one-out donors (`args.loo`). Save the donor weights and the pre-treatment fit statistics. This runner has no conformal procedure.

**Pitfalls.** Classic SCM is listed for one treated unit, few pre-periods, and good donor fit.

**Sources.** https://brycewang-stanford.github.io/StatsPAI/guides/synth/.

### `synthdid`

**Use when.** A block of treated units adopting at one date, a balanced panel, and many control units and pre-periods; the target is the average effect over the treated block.

**Versus.** `generalized_synth`: Requires simultaneous adoption in treated block; generalized_synth accommodates multiple treatment-onset dates. `synthetic_control`: Combines control-unit and pre-period time weights rather than donor-unit weights alone.

**Estimand.** Average treatment effect over the treated unit-by-post-period block using synthetic difference-in-differences.

**Identification.** Untreated outcomes follow a model in which unit and time weights balance pre-treatment trends (Arkhangelsky et al. 2021).

**Run.** `method="synthdid"` → `synthdid::panel.matrices; synthdid_estimate` (0.0.9).

**Options.** Required: `entity`, `time`, `treatment`, `variance`. Optional: `args`, `columns`, `confidence_level`, `definitions`, `seed`.

**Native arguments that change the result.** `N0` (Count of control units in panel matrix; default none; via options.args); `T0` (Number of pre-treatment periods; default none; via options.args); `X` (Time-varying covariate array; default empty array; via options.args); `eta.omega` (Regularization scale for unit weights; default (Ntr*Tpost)^(1/4); via options.args); `eta.lambda` (Regularization scale for time weights; default 1e-6; via options.args); `weights` (Optionally pre-specified donor-unit and pre-treatment time weights; default list(omega=NULL,lambda=NULL); via options.args).

**Returns.** `estimate`: Average treatment effect estimate over treated block; `weights`: Unit and time weights attached as estimate attributes; `setup`: Panel matrix and treatment-block structure attached as attributes.

**Checks before reporting.** Pre-treatment fit of the weighted controls. Treated unit and donor pool fixed before estimation, with each excluded donor and its reason saved in `definitions`. Set the variance in `options.variance` (`method` placebo, bootstrap or jackknife, and `replications`) and report both; placebo variance needs more control units than treated units. The saved effect curve has no covariance across periods, so no joint band is built over it.

**Pitfalls.** panel.matrices requires a balanced panel and simultaneous treatment adoption.

**Sources.** https://synth-inference.github.io/synthdid/reference/synthdid_estimate.html, https://synth-inference.github.io/synthdid/reference/panel.matrices.html, https://doi.org/10.1257/aer.20190159.

### `generalized_synth`

**Use when.** Several treated units with different adoption dates and untreated outcomes driven by a few common factors; the target is the ATT from interactive-fixed-effects imputation.

**Versus.** `synthdid`: Allows heterogeneous treatment dates; synthdid panel.matrices requires simultaneous adoption for treated units. `synthetic_control`: Imputes controls using interactive fixed effects rather than a single treated unit’s donor weights.

**Estimand.** Average treatment effect on treated units from observed outcomes minus interactive-fixed-effects counterfactual predictions.

**Identification.** Untreated potential outcomes follow a linear interactive-fixed-effects model.

**Run.** `method="generalized_synth"` → `gsynth::gsynth` (1.4.0). The runner calls gsynth with force="two-way", CV=FALSE, r=options.factors, se=TRUE, inference="parametric" and nboots=options.bootstraps.

**Options.** Required: `bootstraps`, `entity`, `factors`, `seed`, `time`, `treatment`. Optional: None.

**Native arguments that change the result.** `r` (Number or candidate range of interactive factors; default 0; set by options.factors); `CV` (Select factor rank using cross-validation; default TRUE; fixed by the runner at FALSE); `force` (Choice of unit, time, or two-way fixed effects; default unit; fixed by the runner at two-way); `criterion` (Factor-rank selection criterion; default mspe; fixed by the runner); `nboots` (Bootstrap replications when se=TRUE; default 200; set by options.bootstraps); `inference` (Parametric or nonparametric bootstrap; default NULL; fixed by the runner at parametric); `min.T0` (Minimum untreated periods required for treated unit inclusion; default 5; fixed by the runner).

**Returns.** `att.avg`: Overall average treatment effect on treated units; `att`: Estimated treated-group effects by time; `Y.ct`: Estimated untreated counterfactual outcomes for treated units; `r.cv`: Selected or supplied number of factors.

**Checks before reporting.** Pre-treatment fit of the imputed counterfactual for treated units at the chosen number of factors. Sensitivity of the ATT to the number of factors (rerun with factors one lower and one higher). Treated unit and donor pool fixed before estimation, with each excluded donor and its reason saved in `definitions`.

**Pitfalls.** Units with fewer than min.T0 pre-treatment observations are automatically removed.

**Sources.** https://cran.r-project.org/web/packages/gsynth/refman/gsynth.html.

