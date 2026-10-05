# Design-specific decisions

Read the section for the requested design. Select diagnostics for a concrete identifying question; this reference is not an execution checklist.

## Common design record

Define the unit, treatment path or exposure mapping, potential outcomes, population, period, and target parameter. State the actual identifying variation and risk set. Explain the treatment assignment or counterfactual comparison through institutions, timing, and observed operations. Identify the maintained assumptions, diagnostic evidence, estimator, aggregation weights, and inference unit.

Explain a causal threat through its common cause, timing, effect on treatment or selection, and effect on the outcome. Select controls through the causal structure and measurement timing. Explain the variation removed by each fixed-effect cell and the comparison remaining after conditioning. Predetermined measurement supplies temporal ordering; assignment exogeneity receives its own evidence.

Map each diagnostic to the assumption it examines. Report its actual statistic and uncertainty when these determine the interpretation. State an assumption as an assumption and diagnostic evidence as evidence. Separate conditional association, prediction, causal treatment effect, causal mediation, and model counterfactual through the parameter and its supporting design.

## Difference-in-differences and event studies

Record adoption dates, treatment reversals or intensity, cohorts, outcomes, and comparison eligibility at each date. State the target group-time effects and their aggregation. Explain the counterfactual trend, anticipation window, interference, composition changes, common support, and concurrent interventions relevant to that comparison.

Choose the estimator for the treatment path and effect heterogeneity. Inspect which cohort-time contrasts and weights supply the estimate. Interpret a two-way fixed-effect coefficient through those contrasts. For event studies, specify the reference period, event window, cohort composition, comparison groups, and interval type. Distinguish simultaneous and pointwise uncertainty.

For matching, specify the pre-treatment variables, their measurement dates, common support, matching weights, and subsequent counterfactual-trend assumption. For future-treated comparisons, record the eligible pre-treatment window and assumptions about event timing. Map age, birth cohort, calendar time, and event time explicitly.

Use pre-treatment dynamics to diagnose the stated comparison. A precision or equivalence claim gives its economic tolerance and corresponding interval or test. A conventional pre-trend test receives its actual inferential meaning. Select concurrent-policy and placebo checks through a specific alternative causal path.

## Random assignment and interventions

Identify the unit and mechanism of assignment, stratification, probabilities, implementation, take-up, attrition, and spillovers. Distinguish assignment effects and treatment-receipt effects. Use treatment-receipt estimands with their compliance assumptions. Give covariate adjustment, weighting, randomization inference, and cluster inference the design's assignment structure.

## Regression discontinuity

Specify the running variable, cutoff, assignment rule, compliance, support, and local parameter. Explain continuity or local-randomization assumptions, manipulation, heaping, discretization, and other rules at the cutoff. Record bandwidth selection, polynomial order, kernel, bias correction, and uncertainty. For a fuzzy design, connect the outcome jump and treatment jump to the local compliance parameter.

## Instrumental variables and assignment leniency

Specify treatment, instrument, first stage, independence, exclusion, monotonicity, and the target population. Explain the economic paths supporting the restrictions. Evaluate strength with diagnostics suited to the model and inference. Use weak-instrument-robust inference when the analysis requires it.

For judge, examiner, or officer leniency, verify actual assignment and within-cell variation. Construct the instrument with the appropriate leave-out unit. Address instrument-estimation error, examiner sample sizes, treatment dimensions, case sorting, and monotonicity. Map the parameter to the compliance population and institutional margin.

## Shift-share designs

Identify whether shocks or shares supply the exogeneity argument. Record share dates, shock construction, concentration, exposure, leave-out construction, common components, and the effective assignment units. Match inference to shock dependence and exposure overlap. Explain the estimand under the chosen exogeneity argument.

## Networks and spillovers

Define the relationship, its measurement date, the exposure mapping, own treatment, peers' treatment, and the relevant interference set. Separate common shocks, network formation, endogenous peer selection, direct effects, and spillover effects through the design. Trace assignment from an initial event to downstream exposure. Account for later treatment, migration, endogenous link changes, and outcome recording. Select the inference unit for the assignment and dependence structure.

## Synthetic controls and panel counterfactuals

Define the treated unit, donor eligibility, pre-treatment support, fit, contamination, extrapolation, regularization, and counterfactual structure. Match placebo and sensitivity exercises to the identifying premise. Explain uncertainty using the assignment model, sampling framework, or formal inferential procedure actually employed.

## Inference and interpretation

Use the design's sampling and assignment variation to select standard errors, clustering, randomization inference, or another justified procedure. Record the number of effective assignment units, dependence structure, and small-sample corrections when consequential. Preserve prespecified outcome families and multiple-testing adjustments. Interpret subgroup differences with their direct contrast.

Report the supported parameter and its numerical uncertainty. A design repair states the revised comparison, the changed estimand, and the evidence supporting it. A requested audit covers all design-relevant conditions; a paper explanation selects the main interpretation-changing conditions.
