# Design operations

Select the required section from the [skill entry](../SKILL.md). Read that section and its mandatory dependencies completely before its operation.

## Procedure

### Identify the requested design work

When this design requires both an analytical result and source findings, or method applicability or selection remains unresolved, use [DECIDE](../../../runtime/DECIDE.md) for problem formulation, decision selection and independent source integration.

Select the requested output: a research question, derivation, empirical design or recommendation. For a research question, identify the behavior, incentive, information constraint, allocation or equilibrium it would explain; use econ-literature to compare that contribution with the closest papers. For an economic choice, apply [DECIDE's action-selection procedure](../../../runtime/DECIDE.md#select-a-feasible-action), expressing incremental benefits and resource costs for the same population, period and units and including existing uses of the same capacity. An assessment support call returns the requested technical judgment to econ-review.

When conflicting model results motivate a research question, express their choices and outcomes in a common model and vary the condition that can reverse the result. If aligned definitions resolve the difference, narrow the contribution accordingly. If an economic condition explains it, formulate the question around when that condition holds and select settings or measurements that distinguish its regimes.

For new research, retain the additional formulation comparison in the existing design artifact under DECIDE before carrying its selected question into implementation. The design producer checks that connection; reading its rule alone does not establish application.

When proposing a behavioral hypothesis, identify its driver, the quantity to measure independently, and the comparison where competing hypotheses predict different outcomes. Specify how cases differ in that driver while holding established determinants of the choice fixed, and how the measure would explain choices beyond established explanations.

Connect a diagnostic design to the condition preventing the requested outcome. Distinguish the observed shortfall, its candidate mechanism, the model margin an intervention changes and the resulting economic choice. Derive the comparison at that margin before specifying data collection or computation. Return its implication for the parent research claim or action, including displacement and participant responses that change the total objective. Keep established specifications attached to each delegated derivation or empirical comparison through [TEAM](../../../runtime/TEAM.md).

### For an empirical specification

Start with the [estimand-to-method sequence](designs.md#choose-the-estimand-and-method): requested use, target population and contrast, observation and assignment units, outcome scale, identifying variation, and inference. Resolve these choices before selecting a package. For an adopted specification, reuse those choices and start at the requested change. Use the count, DID, heterogeneous-effect or structural branch that matches the economic object.

Locate the unresolved link that can invalidate the requested conclusion: the measured outcome, the population or response margin identified, or the mapping from that effect to the proposed action. Resolve that link before downstream estimation variants and exhibits that depend on it. For a policy expansion, compare the people and choices moved by the new policy with those moved by the identifying variation. For a finite intervention, establish the response over its path. Return the decisive comparison and update only its affected calculations; retain the adopted specification and matching results.

Use [design elements](designs.md#design-elements) to define the parameter, comparison, assignment, controls and inference units. Translate the intervention into the information, feasible actions or payoffs it changes and the eligibility rule that includes actors. For staged implementation, locate the changed gate and retain eligible actors who do not proceed through it. Use timing gaps between information, contracting and implementation to find a comparison where one choice is fixed while another can respond. When explanations predict different responses, choose the population, timing or participation boundary where their predictions separate, then assess the explanations against that comparison.

When a proposed rule uses observed behavior to set eligibility, scores or prices, identify who can change that behavior after learning the rule. Compare fixed-input predictions with responses to the announced rule, including the cost of changing the input. Use the announcement-to-implementation interval and differences in the gain or cost of qualifying to distinguish anticipation from implementation effects; revise treatment timing, input assumptions or the policy comparison when those responses change the answer.

Use the [design-specific section selector](designs.md#select-the-needed-section) to match estimation and inference to the parameter, treatment path, heterogeneity, dependence and assignment units. Interpret each requested diagnostic through its null, precision and sampling design.

For implementation, pass the adopted estimator, sample, timing, weight meaning and inference requirements to [econ-data's engine selection](../../econ-data/references/implementation-engines.md#estimator-engine-and-algorithm-selection). Require the selected function to implement that parameter and the requested post-estimation comparison. A faster representation must preserve that contract; identify a proposed change in the economic specification and its affected comparisons as a design decision governed by [CORE](../../../runtime/CORE.md). An analysis request continues through the package call, saved estimates and requested economic comparison.

Bind the question, population, actors' choices and constraints, mechanism, estimand and identifying conditions to the existing assembly specification under [economic variable adoption](designs.md#economic-variable-adoption). Keep each field's measurement, timing, source inputs and economic role in its existing `definitions` entry. Put actual estimator inputs in `analyses`; the `variable_design` function checks their column roles before econ-data constructs the adopted sample. Preserve the identifying adjustment set when nuisance learners select predictive features. Carry the same definitions into saved estimates and Writing through the construction record.

### For a theoretical model

Choose the requested object: a payoff comparison, optimal choice, equilibrium, dynamic path or optimized value. Use the matching [model-construction operations](designs.md#model-construction). Retain structure whose omission changes that object, including waiting, nonparticipation, switching or actor composition. A baseline representing an existing institution preserves its objectives, rights and priority rules; a change to those features is a separate intervention to evaluate. A payoff comparison requires payoffs; deriving choices additionally requires a behavioral rule.

For interventions, include displacement into feasible alternative places, times or actions. If competitors or trading partners respond, include their outcomes where the requested aggregation requires them. When constructing an empirical counterfactual, reassess their eligibility as untreated comparisons. When connecting a model to observed data or interventions, use [observation mapping and interventions](designs.md#connect-observed-choices-and-outcomes-to-the-model-and-interventions) to map observed choices and outcomes to model parameters; use [restrictions and set-valued predictions](designs.md#construct-restrictions-and-set-valued-predictions) for deviations, multiple equilibria and compatible counterfactual sets.

### For behavioral responses and group comparisons

Distinguish a behavioral mechanism's total or fixed cost from its cost of an additional unit. Use the actor's decision rule and initial choice to derive the response to a cost change. Establish which choices cross the participation or supply threshold, or which feasible alternative becomes the chosen treatment. Express changes in net gains and changes in actions as separate economic objects.

An individual's monotone comparative static gives the direction of that actor's response. To compare group quantity changes, convert choices crossing the threshold into the comparison's quantity unit and apply population weights. When a change in the number participating can arise from entry or exit, compare those transitions and the quantities each contributes. Establish comparability of initial choice distributions, production opportunities and response margins at the affected thresholds. Choose the observation window from the response's adjustment and duration; a narrow window can precede implementation, while a long average can dilute a short-lived response.

### Establish feasibility

For a requested preregistration, grant design or data-management plan, carry the adopted question, estimand, identifying comparison, accessible sample, analysis and inference into that requested artifact through the existing specification and writing owner. Distinguish confirmatory choices from exploratory branches, fix the permitted changes and data-access/retention authority, and state the empirical failure or observation that would change the design. Use the existing source propositions and actual data documentation; record the chosen design in the current task before execution.

For an end-to-end research request, keep discovery, design and execution in the same adopted specification. Connect each candidate's closest literature answer, added economic mechanism, target contrast and identifying restrictions to documented source fields, observation grain, period, linkage keys and the variation that identifies that contrast. Use the [public discovery connector](../../econ-literature/scripts/research_sources.py) or the current connected sources to inspect those actual fields. Use the [design assessment](../scripts/research_design.py) to bind the closest-answer passages and the owner's contribution judgment to actual CSV grain, missingness, period, variation and linkage observations. Adopt the candidate order from its economic contribution and decisive comparison under DECIDE; execute the first feasible candidate's recorded next operation through the [research execution path](../../../harness/research.md). The host continues from a returned calculation to its economic interpretation, next determining comparison and final paper through the five existing owners.

Use [DECIDE's result interpretation](../../../runtime/DECIDE.md#interpret-a-consequential-result) after a consequential analytical result; the registry requires that body for this workflow. Keep specification-search estimand, population, inference, evaluator and partition roles fixed in the adopted protocol. A changed target or identifying restriction requires its authorized comparison and result identity.

For each proposed empirical design, map required measures and comparisons to documented fields and source records within the task's cost and access limits. For a theoretical or computational design, establish compatibility of assumptions and feasibility of the required derivation or solution within those limits. Preserve supplied candidate IDs and scope. Use econ-data for field or linkage analysis. Repair input or implementation defects within the authorized design; record missing fields or permissions needed for the next operation and continue independent work.

### Choose among research designs

When asked to select a design, compare feasible candidates on the requested economic object, assumptions needed to establish it, and data, computation, implementation and delay costs. For empirical designs, include identification and precision; for theoretical designs, compare the propositions and mechanisms their assumptions can establish. Evaluate numerical or statistical precision against a stated economic threshold or target contrast, deriving it from the task's objective when available. If that criterion is missing, request it when its value changes the design choice. Use [DECIDE](../../../runtime/DECIDE.md#select-a-feasible-action) to rank feasible designs, establish switch conditions and stop information gathering when it cannot change the action; return the selected design or its selecting conditions. Keep adoption decisions and project status in operational records; research artifacts state the economic comparison, assumptions and results.

## Specialized executable designs

Select the registered condition for the adopted calculation. The causal conditions below load the common input/result contract, the applicable extension contract and the named method section through existing rule dependencies. Select every condition used by the requested calculation. Read those complete sections and their required dependencies; reuse same-version bodies already read. `method_extended_causal` retains the complete [causal reference](causal-models.md) for family-wide work and existing callers. The method conditions are available to design, execution and review.

| Registered condition | Adopted calculation | Method section |
| --- | --- | --- |
| `method_causal_shift_share` | `shift_share_inference`: shock/share identification, AKM/AKM0/BHJ and Rotemberg weights | [Shift-share inference](causal-models/inference.md#shift-share-inference) |
| `method_causal_sensitivity` | `sensitivity_oster`, `sensitivity_cinelli`, `sensitivity_evalue` | [Saved-result sensitivity](causal-models/inference.md#sensitivity-from-saved-ols-quantities) |
| `method_causal_family_inference` | `romano_wolf`, `specification_curve`, `holm` | [Declared families and spatial covariance](causal-models/inference.md#declared-families-and-spatial-covariance) |
| `method_causal_spatial` | `spatial_conley` | [Declared families and spatial covariance](causal-models/inference.md#declared-families-and-spatial-covariance) |
| `method_causal_lp_did` | `lp_did` | [DID and synthetic controls](causal-models/extensions.md#did-and-synthetic-controls) |
| `method_causal_bacon` | `bacon` | [DID and synthetic controls](causal-models/extensions.md#did-and-synthetic-controls) |
| `method_causal_synthetic_controls` | `scm_diagnostics`, `augmented_synthetic_control` | [DID and synthetic controls](causal-models/extensions.md#did-and-synthetic-controls) |
| `method_causal_mediation` | `mediation` | [Mediation and heterogeneous treatment effects](causal-models/extensions.md#mediation-and-heterogeneous-treatment-effects) |
| `method_causal_ml` | `metalearner`, `tmle` | [Mediation and heterogeneous treatment effects](causal-models/extensions.md#mediation-and-heterogeneous-treatment-effects) |
| `method_causal_decomposition` | `kitagawa`, `dfl`, `gelbach` | [Decomposition and duration](causal-models/extensions.md#decomposition-and-duration) |
| `method_causal_survival` | `survival_km`, `survival_aft` | [Decomposition and duration](causal-models/extensions.md#decomposition-and-duration) |
| `method_causal_bayesian_model` | `bayesian_model` | [Bayesian project models](causal-models/native.md#bayesian-project-model-execution) |
| `method_causal_julia` | `fixed_effects_julia` | [Julia fixed effects and IV](causal-models/native.md#julia-fixed-effects-and-iv) |

For a known market, dynamic, macro, DSGE or numerical calculation, select its individual `method_market_*`, `method_dynamic_*`, `method_macro_*`, `method_dsge_*` or `method_numerical_*` condition from `index --operation econ-design:design`. Each condition closes its complete equations, observation map, scientific restrictions and execution prerequisites. Use the corresponding family-wide `method_extended_*` condition only for requested family coverage; an identified method needs no additional family-wide load. Agent simulation uses `method_agent_simulation`. Carry the same adopted objects into estimation, counterfactuals and prose.

Select `research_adaptive_experiments` for [source comparisons and adaptive experiments](adaptive-research.md). The proposal generator compares all five economic dimensions and actual data feasibility. The lead adopts the research target and authorized experiment axes in the existing governing context. The runner then generates new parameter candidates from completed results under the fixed evaluation and preserves the final held-out sample for the selected candidate.
