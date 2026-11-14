## Official causal extensions

Use for the StatsPAI-based extensions: DiD and synthetic-control variants, mediation, heterogeneous effects, decomposition and duration. Each row gives the required options and the saved quantity.

### Causal extension contract

- The existing `run SPEC.json --output RESULT.json` command binds these methods through `_causal_extensions` and the pinned **StatsPAI 1.43.1**, [revision ddb3b45f2d3fc649ea794aa15f8989bb10f8e543](https://github.com/brycewang-stanford/StatsPAI/tree/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543).
- They use the common scientific specification, shared table reader and result lifecycle.
- `options.args` contains the selected function's native arguments; role columns belong in the flat options below.
- `inference={"type":"official","confidence_level":0.95}` selects native inference.
- Supported cluster paths use `{"type":"cluster","cluster":"column","confidence_level":0.95}`.
- The wrapper forwards the level as native `alpha=1-confidence_level`.

| Method | Required flat options | Official call and saved quantity |
| --- | --- | --- |
| `lp_did` | `entity`, `time`, `treatment` | `statspai.did.lp_did.lp_did`: event-time long-difference coefficients, horizon sample sizes, joint horizon covariance and native pooled pre/post regressions. |
| `bacon` | `entity`, `time`, `treatment` | `statspai.did.bacon.bacon_decomposition`: TWFE coefficient, weighted two-by-two contrasts, comparison classes, weight totals and the within/between decomposition with controls. |
| `scm_diagnostics` | `entity`, `time`, `treated`, `treatment_time` | `statspai.synth.scm.synth(method="classic")`: post-treatment average gap, trajectories, donor weights, requested in-space/time placebos and leave-one-donor paths. |
| `augmented_synthetic_control` | `entity`, `time`, `treated`, `treatment_time` | `statspai.synth.augsynth.augsynth`: ridge-augmented weights, counterfactual trajectory, average gap and native placebo inference. |
| `mediation` | `treatment`, `mediator` | `statspai.mediation.mediate.mediate`: native indirect/direct/total effects and proportion mediated. |
| `metalearner` | `treatment` | `statspai.metalearners.metalearners.metalearner`: selected S/T/X/R/DR CATE predictions and the separate native cross-fitted AIPW average. |
| `tmle` | `treatment` | `statspai.tmle.tmle.tmle`: selected targeted ATE/ATT/ATC, efficient influence function and native nuisance/targeting diagnostics. |
| `kitagawa` | `group`, `by` | `statspai.decomposition.kitagawa.kitagawa_decompose`: symmetric rate/composition decomposition and full cell contributions. |
| `dfl` | `group` | `statspai.decomposition.dfl.dfl_decompose`: distributional gap, composition and structure components, reweighting coefficients, counterfactual weights and requested quantile grid. |
| `gelbach` | `added_regressors`, `var_of_interest` | `statspai.decomposition.oaxaca.gelbach`: each added control's contribution to the short-minus-long coefficient change and the native joint covariance. |
| `survival_km` | `status` | `statspai.survival.models.kaplan_meier`: native product-limit survival curve, risk/event/censor counts, intervals and median survival. |
| `survival_aft` | `status` | `statspai.survival.models.survreg`: parametric log-duration coefficients, full covariance, likelihood/convergence diagnostics and exponentiated covariate time ratios. |
- `regressors` supplies controls or covariates, and the Gelbach base regressors.
- Kitagawa and KM use empty regressors.
- All twelve methods use empty `endogenous` and `instruments`.
- Optional `definitions` carries the adopted economic meaning.
- The complete-case sample includes every bound role, covariate, weight, fold and cluster column.
- IDs retain their original text.
- Native output, producer signature/source hash, package revision and effective arguments remain attached.
- A native horizon/donor/absorbed fit that does not export row membership sets `included_ids_available=false`; the result retains input IDs and native counts, coordinates and weights.

### DID and synthetic controls

- LP-DiD requires a balanced consecutive-integer panel with absorbing binary adoption.
- `args.horizons=[-3,5]` includes the normalized -1 reference and horizon zero.
- `clean_controls` chooses `not_yet_treated` or `never_treated`, and `time_fe` selects calendar effects.
- Controls carry their adopted pretreatment information set.
- StatsPAI 1.43.1's constructed horizon rows contain the entity identifier and omit a separately named cluster; this binding uses entity clustering.
- Negative-horizon coefficients, reference rows and nonnegative effects retain distinct roles.
- The coefficient at zero and each pooled regression retain their native target.

- Bacon takes the same balanced absorbing panel and `args.balance="error"`.
- Its `weights` column is positive and constant within entity.
- Group/contrast weights, already-treated control shares and covariate-adjusted within/between terms are saved directly.
- Its main quantity is a TWFE projection decomposition, and the result uses `inference.type="none"`.

- Classic SCM uses one treated unit and at least two eligible untreated donors.
- ASCM also accepts `treated` as a list with a common treatment date.
- Both require a complete balanced panel.
- Classic SCM forwards official `args.loo`, `placebo_time`, `placebo_cutoff`, `placebo_units`, `pre_periods`, `post_periods`, predictor-importance and optimizer settings.
- Native LOO removes donors with fitted weight at least 0.0005.
- The native fit reports its actual selected donor/time sample.
- `scm_trajectory` and `scm_gap` consume its saved coordinates.

- With official inference, classic SCM saves the actual placebo-rank p value and native interval method, including interval endpoints at infinity.
- ASCM saves the native placebo-ATT standard deviation, rank p value and normal-reference interval.
- `inference.type="none"` supplies `placebo=false`.
- `args.ridge_lambda`, `progfunc`, `scm` and `fixedeff` select the ASCM outcome model and weighting rule; native augmented weights can be negative.
- The existing `synthetic_control` method keeps its training/held-out-validation contrast and fitted-weight inference.

Sources: [LP-DiD implementation](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/did/lp_did.py), [Bacon implementation](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/did/bacon.py), [classic SCM](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/synth/scm.py), [native placebo/LOO reports](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/synth/_classic_report.py), and [ASCM](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/synth/augsynth.py).

### Mediation and heterogeneous treatment effects

- Mediation requires the adopted treatment/mediator sequential exchangeability, positivity, consistency and mediator/outcome models.
- Natural direct and indirect effects additionally require the adopted restriction on treatment-induced mediator-outcome confounding.
- Native `args.inference` is `bootstrap`, `robust` or `delta`; the delta path is the linear no-interaction model.
- `interaction`, `mediator_model`, `outcome_model`, `treat_values`, `n_boot`, `seed` and `pvalue_method` retain their official meanings.
- Optional `weights` binds sampling weights.
- The result saves potential-outcome means and their covariance when returned; the proportion-mediated row has its own unit.

- The meta-learner binding takes binary 0/1 treatment.
- `args.learner` selects `s`, `t`, `x`, `r` or `dr`.
- Native CATE predictions are saved by their actual estimation IDs.
- The aggregate estimate and SE come from the official cross-fitted AIPW score; the native CATE mean is a separate quantity.
- Native propensity clipping and its affected counts remain in diagnostics.
- `weights` and one declared cluster pass to the supported native average-effect calculation.

- For both meta-learners and TMLE, `options.fold` names an integer fold-label column.
- It is saved with row IDs and passed as native `fold_indices`.
- Clustered folds keep whole clusters together.
- `options.learners` reuses the existing learner constructor: meta-learners accept `outcome_model`, `propensity_model`, `cate_model`; TMLE accepts `outcome_model`, `propensity_model`, each as its supplied one-member Super Learner library.
- Each uses the existing `{"type":"linear","params":{}}` or classifier/regressor configuration.
- `seed` binds those declared learners; TMLE also binds native `random_state`.
- Native default meta-learner folds retain their declared fixed seed.

- TMLE `args.estimand` selects `ATE`, `ATT` or `ATC`.
- `n_folds` controls Super Learner's internal cross-validation.
- An explicit outer `fold` supplies out-of-fold initial nuisance fits; omission uses the native full-sample nuisance fits.
- `propensity_bounds`, `q_bound`, `fluctuation`, `se_method`, `n_boot`, weights and clustering preserve their native definitions.
- The saved influence function uses the retained input order, and the native output records targeting, nuisance ensemble weights and cross-fitting status.

Sources: [mediation](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/mediation/mediate.py), [meta-learners and their average score](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/metalearners/metalearners.py), and [TMLE](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/tmle/tmle.py).

### Decomposition and duration

- Kitagawa and DFL use groups 0 and 1, with the reported gap equal to group 0 minus group 1.
- Kitagawa requires both observed group rates in every adopted cell and `normalize="symmetric"`; the current native per-cell contributions use that symmetric formula.
- Without `weights`, each row is an individual; with `weights`, each row is one group-cell rate and its population count.
- The native aggregate gap, rate effect, composition effect and cell contributions retain their corresponding denominators.

- DFL `args.stat` selects the native mean, variance, standard deviation, quantile, IQR, Gini or log-variance.
- Preserve the statistic's unit in the common specification.
- `reference=0` reweights group 1 to group 0's covariate distribution; `reference=1` reverses that construction.
- `trim` clips the estimated propensity, and `stat_convention` selects the official weighted-statistic definition.
- `inference.type="none"` selects the descriptive decomposition; official inference selects `args.inference="bootstrap"`, with native `n_boot` and `seed`.
- Version 1.43.1's `analytical` argument returns no analytical variance, so the binding accepts the implemented none/bootstrap paths.
- Counterfactual weights keep their corresponding source-group IDs.
- Quantile-process rows retain their point-estimate role.

- Gelbach uses `regressors` as the short model, `added_regressors` as the additional controls and `var_of_interest` as a short-model term.
- Optional `fixed_effects` binds the same absorbed effects in both models.
- Native `args.vce` and declared clustering determine the stacked-regression covariance.
- Save the short/full coefficients, each native contribution, total change, total SE and full joint covariance.
- Absorbed singleton handling belongs to the native fit.

- KM `outcome` is duration and `status` is the event indicator.
- Optional `group`, `entry`, `weights` and clustering bind native groups, delayed entry, case weights and independent units.
- `args.conf_type` chooses `log-log`, `log` or `plain`; `se_method` chooses Greenwood, infinitesimal jackknife or Xie-Liu.
- Saved survival coordinates are rendered as a step function.
- AFT requires positive durations; `args.dist` chooses `weibull`, `exponential`, `lognormal` or `loglogistic`.
- `args.robust` and the declared cluster choose covariance; `frailty="gamma"` selects the native frailty likelihood.
- AFT coefficients, scale parameters and exponentiated covariate time ratios keep their distinct units.
- The existing PHReg survival and Oaxaca owners retain their original specifications.

Sources: [Kitagawa](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/decomposition/kitagawa.py), [DFL](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/decomposition/dfl.py), [Gelbach](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/decomposition/oaxaca.py), and [KM/AFT](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/survival/models.py).
