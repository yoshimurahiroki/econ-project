# Design methods

The reference for steps 3 and 4 of the [economist's procedure](../../../runtime/ECONOMIST.md): how to build the model and how to choose the comparison, estimand and estimator. The order of work is the [design procedure](workflow.md); this file is looked up by section. Each section opens with when to use it, then numbered rules; follow the rules in order and write their results in the worksheet.

## Select the needed section

| The case has | Section | It returns |
| --- | --- | --- |
| Choices, constraints, strategic interaction, contracts, continuation | [Model construction](#model-construction) | feasible choices and the optimum, equilibrium, path or value |
| A proposition to prove or refute | [Propositions, proofs and counterexamples](#propositions-proofs-and-counterexamples) | the proof's determining step or a counterexample |
| Ordered discrete or nonsmooth choices, lattices, fixed points | [Ordered choices](#ordered-choices-and-constructive-representations) | monotone comparative statics or an equilibrium correspondence |
| Disclosure, information acquisition, ambiguity | [Information choices](#information-choices-and-belief-representations) | implementable beliefs and the choice they imply |
| A method or estimator to choose | [Choose the estimand and method](#choose-the-estimand-and-method) | the target and its estimator |
| Counts, zeros, shares or percentage effects | [Outcome scale](#outcome-scale-and-conditional-mean) | the model and the effect in the requested units |
| A causal parameter from an observed assignment process | [Design elements](#design-elements) | parameter, comparison, assumptions and inference unit |
| Variables to adopt for an analysis | [Economic variable adoption](#economic-variable-adoption) | the checked variable roles |
| Staggered adoption or event time | [Difference-in-differences](#difference-in-differences-and-event-studies) | cohort-time contrasts and their aggregation |
| Flexible adjustment or heterogeneous effects | [Orthogonal scores](#orthogonal-scores-and-heterogeneous-effects) | score, target population and decision contrast |
| Demand, conduct, entry, dynamics, equilibrium counterfactuals | [Structural estimation](#structural-estimation-and-counterfactuals) | identified primitives and re-solved choices |
| Random assignment | [Random assignment](#random-assignment-and-interventions) | assignment or receipt effects with matching inference |
| A threshold rule | [Regression discontinuity](#regression-discontinuity) | the local effect at the cutoff |
| An instrument or assigned decision-maker | [Instrumental variables](#instrumental-variables-and-assignment-leniency) | the complier effect with valid inference |
| Exposure from shares and shocks | [Shift-share](#shift-share-designs) | the exogeneity argument and effective units |
| Connected actors, interference | [Networks and spillovers](#networks-and-spillovers) | exposure mapping and direct or spillover effects |
| One treated unit and a donor pool | [Synthetic controls](#synthetic-controls-and-panel-counterfactuals) | the panel counterfactual |
| Standard errors, subgroups, sensitivity | [Inference](#inference-and-interpretation) | the covariance, distribution or conclusion-changing departure |
| A failed prediction, an inversion, a policy-induced response | [Connect choices and outcomes to the model](#connect-observed-choices-and-outcomes-to-the-model-and-interventions) | the repaired mapping or re-solved counterfactual |
| Deviations, multiple equilibria, observed budgets | [Restrictions and set-valued predictions](#construct-restrictions-and-set-valued-predictions) | valid inequalities and compatible sets |
| An unsettled target or a welfare aggregation | [Select the economic object](#select-the-economic-object), [quantities](#reuse-or-calculate-the-requested-quantities) | the parameter, counterfactual or common-unit comparison |

## Model construction

Start with the decision structure, primitives and requested object. Add the branches required by the model's information, strategic interaction, contracts or continuation choices. Use the solution and comparative-static branches for the object being derived.

1. **Choose the decision structure.** For a price-taking actor, write the feasible set and objective conditional on prices. When payoffs depend on others' choices, specify players, actions and the strategic solution concept. Derive contingent strategies from timing and information sets: a follower's strategy specifies actions after possible histories. Private types require conditional beliefs and type-dependent strategies. A designer choosing payments or rules needs the contract branch below; actions that change future opportunities need the dynamic branch.

2. **Type primitives and check compatible assumptions.** Define spaces and domains before objects on them: a commodity dimension and consumption set before preferences and endowments, or a type space before beliefs and strategies. Separate feasible actions from exogenous parameters. When introducing or combining assumptions leaves their joint feasibility unresolved, establish it by direct derivation or an admissible example. Use boundary examples when an illustration may import an additional restriction. Ordinal rankings suffice for ranking choices; use numerical utility with the representation and normalization needed for derivatives, risk or cardinal welfare operations. Establish the extra comparability assumptions before aggregating utility across people.

3. **Place shocks in information and time.** For each consequential shock, specify who observes it and when relative to choices. Under expected-utility or expected-payoff maximization, integrate payoffs over the shock distribution conditional on the actor's information. For a shock known to the actor but unobserved by the researcher, solve the actor's problem conditional on its realization, then integrate over it in the observation mapping. Derive observable probabilities or moments from this timing, attributing private information, choice error and measurement error each to its own term. Changing the observation time can change the optimization problem and the endogeneity of the resulting estimating equation.

4. **Close individual decisions with equilibrium conditions.** Separate each actor's optimization from consistency of choices, beliefs and aggregates. Add the market-clearing, resource, mobility, budget or strategic consistency conditions needed for the endogenous quantities. In an open-city closure, outside utility is fixed and population adjusts; in a closed-city closure, population is fixed and utility adjusts. A policy fixing a formerly endogenous boundary or quantity can replace its free-boundary condition: a binding development limit can generate a boundary rent above the outside land rent. Derive which condition changes before solving the new system. Establish whether the solution set is empty, single or multiple; use a justified selection rule or retain set-valued predictions when multiplicity matters.

5. **Establish optimizing actions.** For discrete actions, compare feasible payoffs directly. For a calculus solution, examine boundaries and active constraints; when using KKT, retain complementary slackness and check the constraint qualifications needed for necessary conditions. Use curvature, derivative signs or a direct comparison to establish global sufficiency. For maximization on [0,1], a differentiable objective can attain its maximum at 0 with f′(0) ≤ 0, at 1 with f′(1) ≥ 0, or at an interior stationary point; compare the feasible candidates. Establish existence, optimality and any uniqueness claim under their respective assumptions. When a numerical solution is requested, establish its convergence criterion, substitute the returned choices into the original constraints and optimality conditions, and compare their residuals with the required tolerance.

6. **Construct implementable contracts.** When actions or types are unobservable, condition allocations and transfers on contractible information. Write incentive compatibility against feasible deviations, individual rationality against the outside option, and transfer or resource restrictions separately. For a risk-neutral worker, let hidden effort cost e and raise success probability from 0 to p, with fixed pay w and success bonus b. Effort yields w + pb − e versus w from shirking, so IC gives pb ≥ e: the common fixed payment cancels. If p > 0, this gives b ≥ e/p; participation still compares w + pb − e with the outside option, while limited liability separately restricts payments. Check which constraints imply others, which bind, and how ties are resolved. Use a truthful-direct-mechanism reduction only under the information, commitment and equilibrium assumptions that support it.

7. **Construct a dynamic choice only when continuation matters.** Specify state s, control a, feasible actions A(s), transition s′ = T(s,a,ε′), flow payoff u, discount β, horizon and initial condition. Retain a state sufficient for payoff-relevant history. Under a valid stationary recursive representation, V(s) = max over a ∈ A(s) of {u(s,a) + β E[V(s′) | s,a]}; the policy g(s) selects actions while V(s) measures optimized continuation value. For a finite horizon, use time-indexed values and a terminal condition; for an infinite-horizon path, impose the appropriate transversality and admissibility conditions. Check the equivalence and regularity supporting the recursive or Euler characterization, and return the path, policy or value the question asks for.

8. **Reduce a system while preserving feasible choices and optimality.** When interaction operates through an aggregate, check whether payoffs and best responses can be represented using that aggregate. A reversible change of variables must preserve feasible domains and allow recovery of individual choices. Derive the aggregate consistency equation, recover individual choices from its solutions, and substitute those choices into the original individual optimality conditions. Where continuity, endpoint behavior and monotonicity establish existence or uniqueness, show that argument. Retain the disaggregated system when the proposed aggregate loses a relevant interaction or admits spurious solutions.

9. **Differentiate the requested object.** Define the chosen action, the equilibrium outcome and the optimized value each as its own object. For a smooth local equilibrium F(y,z) = 0 with nonsingular F_y, derive dy/dz = −F_y⁻¹F_z. For optimized value, apply an envelope result under its differentiability and constraint conditions, including direct effects through changing constraints. A unique optimizer alone does not establish value differentiability. Resolve changing active sets, thresholds, kinks or equilibrium selection before extending a local derivative across regimes; give the sign or ranking on the domain where its conditions hold.

10. **Recheck results after changing behavior or institutions.** Identify the changed primitive, preference domain, permitted deviation or information set and rewrite the affected solution conditions. Check the assumptions supporting any existence, uniqueness, incentive or comparative-static result before carrying it over. For example, allowing couples to rank pairs of jobs changes both preferences and blocking deviations in a matching model. Preserve the benchmark to locate the source of a changed result, and re-examine fixed conditions that adjust when scale or setting changes.

### Propositions, proofs and counterexamples

Use when a claim must be proved, refuted or repaired.

1. **Statement first.** Write the complete statement: each variable's domain, feasible set, information set and solution concept; quantifiers in their actual order; whether the claim covers every equilibrium, at least one, or the adopted selection. Keep existence of a feasible point, an optimizer, an equilibrium and a unique outcome apart.
2. **Determining step.** Find the step that turns the hypotheses into the conclusion and derive its lemmas from the primitives. Fixed points: the domain and the correspondence properties the theorem needs. Deviations: feasible deviations under the actor's information and timing, with induced continuation play. Optimization: boundary choices, complementary slackness and the global comparison. Each regularity condition (domination, integrability, compactness, differentiability, measurability) is stated where it is used; a cited theorem brings its exact hypotheses, and the model is mapped into them.
3. **Counterexamples.** Test a contested claim at its boundary, tie, binding constraint or equilibrium branch with explicit primitives, strategies or allocations; compute the hypotheses and the conclusion. One admissible violation refutes the claim; an affirmative claim needs a proof over the whole domain. Numerical cases settle only themselves.
4. **Repair.** Change the assumption or clause that breaks the implication, derive what the change does to the mechanism, and carry the new domain, selection and signs into every dependent proposition, comparative static and welfare statement.

### Ordered choices and constructive representations

- **Compare ordered choices through payoff differences.** For discrete, corner or nonsmooth choices, specify the choice and parameter orders and form ΔU(θ) = U(x_H,θ) − U(x_L,θ) for x_H > x_L. Single crossing preserves both weak and strict preference for the higher choice as θ rises. For vector choices, use quasi-supermodularity on a lattice and single crossing; supermodularity and increasing differences suffice. Order changing feasible sublattices by the strong set order: A ≥ B means a ∨ b ∈ A and a ∧ b ∈ B for every a ∈ A, b ∈ B. Compare the nonempty argmax sets in that order and their least/greatest elements when present; arbitrary selections through ties can fall. With an unresolved scalar state s, integrable single-crossing differences Δu(s) retain single crossing in their expectation under a monotone-likelihood-ratio shift, such as log-supermodular densities f(s;θ). First-order stochastic dominance suffices when Δu(s) is nondecreasing. For adoption paying s − c against zero, this stronger payoff shape permits the weaker distribution order.

- **Choose coordinates that preserve and expose the interaction.** For two substitutable choices, reversing one coordinate can turn their cross effect into complementarity; translate the resulting ordering back to the original choice. In larger systems, derive the signs after transformation. When the objective is f(x) + Σ_i g_i(x_i,y_i), independent local domains let maximization over y reduce it to f(x) + Σ_i max_y_i g_i(x_i,y_i). If f is supermodular, the reduced objective remains so because each added term depends on one x coordinate. Shared local constraints or cross-unit terms require a different reduction. Recover optimizing y_i from each reduced solution; use suprema and address attainment when maxima do not exist.

- **Construct the equilibrium correspondence.** Define each full best-response set B_i(x_−i), then B(x) = ∏_i B_i(x_−i). On a nonempty compact convex product strategy domain in finite-dimensional Euclidean space, continuous payoffs and quasi-concavity in own action give the nonempty compact convex values and upper hemicontinuity needed for a Kakutani fixed point. For opponent-dependent feasibility, derive these properties from the feasible correspondence. Recover simultaneous optimality from x ∈ B(x). Discrete actions sometimes admit a different convex representation: with ordered finite actions, compact interval private types, bounded atomless joint type density, finite payoff integrals and conditional-payoff single crossing whenever opponents use monotone strategies, represent monotone strategies by ordered cutoffs. Equal cutoffs allow skipped actions. Establish convex best responses and a closed graph in cutoff coordinates, then recover pure strategies and optimal boundary-type actions. Convex combinations of action levels require their own economic feasibility; a fixed point establishes existence, while uniqueness and iterative convergence need separate arguments.

### Information choices and belief representations

- **Construct disclosure through implementable beliefs.** When the intervention changes what receivers learn, specify state ω, prior μ₀, feasible signal kernels π(s|ω), receiver utility u and designer utility v. Under credible commitment to the known kernel, derive μ_s(ω) ∝ π(s|ω)μ₀(ω), receiver choices a(μ_s) ∈ argmax_a E_μ_s[u(a,ω)], and the designer's expected payoff, including tie behavior. Unrestricted experiments with a common prior permit choosing a distribution τ over full posteriors subject to E_τ[μ] = μ₀. For finite states and posterior support, recover π(s_μ|ω) = τ(μ)μ(ω)/μ₀(ω) on positive-prior states. With prior P(H)=1/4 and receiver threshold P(H|s)≥1/2, equal weights on posteriors 0 and 1/2 implement action at probability 1/2: the favorable signal occurs with probability 1 in H and 1/3 in L. Restricted experiments add feasibility conditions. Even with unrestricted experiments, preserving only the mean of posterior means generally does not ensure implementability. State-contingent messages chosen without commitment require a communication model supporting that behavior.

- **Make acquisition and remembered information endogenous when they affect choice.** Choose the feasible experiment menu and cost C(π) from the observation technology: paying for a specified test and choosing any signal kernel imply different attainable beliefs. Compare posterior decision value less cost and reoptimize acquisition when payoffs change. Shannon cost λI(ω;s) is one specification. For unrestricted experiments, finite actions and λ>0, its discrete-choice form P(i|ω) ∝ P(i)exp(u(i,ω)/λ) includes endogenous shares P(i) = E[P(i|ω)] and optimality inequalities for excluded alternatives; these shares can change with the prior or menu. When information persists, add the sufficient inherited belief to the physical state, update it after the chosen signal, and transition that belief into the next decision. A conditional-information cost prices new information given the history. Mean/variance compression requires a supporting family such as Gaussian beliefs; general learning may require the full posterior.

- **Select the state-probability aggregator from the preference comparison.** For known-probability lotteries, expected utility and utility curvature describe risk attitudes under the relevant representation axioms. For state-contingent acts, select a single subjective prior or ambiguity preferences; maxmin E_p[u] over p ∈ P requires its own preference restrictions. Select that representation from the actor's preferences over acts. In an urn with known red share 1/3 and unknown blue/green split, preferring red to blue but blue-or-green to red-or-green implies contradictory rankings of red and blue under any single additive prior and common increasing money utility. Utility curvature alone cannot generate those rankings. For sequential maxmin, specify the information partition and updating rule. To represent ex ante maxmin recursively across acts under the specified information structure, require rectangularity: admissible event probabilities and conditional priors can be recombined within P. With nonrectangular P, specify ex ante commitment or conditional reoptimization; rectangularizing P changes the preference model.

## Choose the estimand and method

Use when a new analysis needs its target and estimator. A settled specification is reused.

1. **Requested use.** The decision and its threshold; an action target adds its loss, welfare or profit comparison.
2. **Target.** Average, on the treated or conditional; level or relative; static or dynamic; with population, period, units and aggregation weights.
3. **Data structure.** Map the records to choices, markets, panels or repeated cross sections, with the information available before each choice; the observation unit, the assignment unit and the treatment history.
4. **Identifying restrictions.** Derive the conditional mean, moment, likelihood or equilibrium restriction that identifies the target; controls, instruments and fixed effects follow from it.
5. **Estimator and inference.** The estimator that implements that restriction ([implementation table](../../econ-data/references/implementation-engines.md)); covariance or resampling matched to the dependence and the actual cluster variable; pointwise or joint intervals as the claim requires.
6. **Distinct objects.** Linear projections, proportional means, count distributions, choice probabilities, IV complier effects, cohort-time and path effects, local cutoff effects, donor counterfactuals, orthogonal-score targets, network exposures, identified sets and structural equilibria answer different questions; the estimand names which.

Tooling: `research_design.py select` chooses among implementations from a contract (`research_causal.py select` calls it). The adopted analysis is `adopted_specification`; `design_contract` keeps population, comparison, units, weights and inference; `design="auto"` reads `conditions.assignment_mechanism` ([selection contract](causal-models/implementation.md#select-the-implementing-function)). Candidates listed under `eligibility.excluded_by` (mismatched target, history or dependence) are out before cost and precision are compared. Dynamic selection reads state and action domains, timing, transitions and constraints; an ambiguous `individual_dynamic_choice` is bound to the adopted `structural_model` or `model_contract_id`.

## Outcome scale and conditional mean

Use when the outcome is a count, has zeros, is a share, or the effect is wanted in percent.

| Outcome and question | Model | Effect |
| --- | --- | --- |
| Level change, additive mean | OLS (zeros admissible) | slope in outcome units; Δ/m × 100 percent of the reference mean m |
| Proportional change, nonnegative outcome (integer or not) | Poisson pseudo-likelihood (PPML), μ = exp(x′β) | 100[exp(β) − 1] percent for a binary regressor; β is the semi-elasticity |
| A specified count distribution, Var = μ + αμ² | negative binomial NB2 likelihood | as PPML; overdispersion alone does not select NB2 |
| Rate with exposure e | log link with offset log(e) | proportional effect on the rate |
| Share with a denominator | linear share, fractional response or binomial likelihood, by the observation process | percentage points |
| Individual growth rate | requires y0 > 0 | a different target from the change in means |

Rules:

1. A mean of individual rates and a ratio of population means use different weights; keep the chosen denominator.
2. Adding a constant before taking logs changes the target and makes it depend on units.
3. With interactions or heterogeneous slopes, average fitted counterfactual means over the target population.
4. Panel fixed effects in nonlinear models: state how individual effects enter (`MASS::glm.nb(y ~ x + factor(id))` estimates group intercepts; conditional NB imposes its own heterogeneity model); binary fixed effects use conditional likelihood, bias correction or a long panel.
5. Observations dropped for separation or absorbed effects are part of the fitted sample.
6. A separate zero or participation equation needs a behavioral or measurement process that produces it.

## Design elements

Use for any causal parameter from an observed assignment process.

1. **Comparison.** Treatment path or exposure mapping, potential outcomes, population, period and the target parameter.
2. **Units.** Source-observation, analysis, policy-assignment and inference units, each with its role.
3. **Variation.** The identifying variation, risk set, assignment and counterfactual, explained through institutions, timing and observed operations.
4. **Threats.** For each threat: the common cause, its timing, its effect on treatment or selection, its effect on the outcome. Controls come from the causal structure and measurement timing; state what variation each fixed-effect cell removes and what comparison remains.
5. **Diagnostics.** For each: the alternative path it targets, the outcome or proxy that path predicts, and the conditioning that keeps the intended variation. Rejection is read against the assumption the comparison tests.
6. **Name the object:** association, prediction, causal effect, causal mediation or model counterfactual.
7. Comparing decision-makers on the same case needs a setting with several judgments of that case; decision order or separate decisions show interaction among judges.

## Economic variable adoption

Use the existing assembly specification for the chain from the research question to actual analysis columns. Its top-level `question`, `population`, `observation_unit`, `economic_model`, `mechanism`, `estimand` and `identification` hold the adopted economic objects. Each accepts text or an object. In `economic_model`, connect actors, choices, constraints and information to the measured response. In `estimand`, define the contrast, target population, period and aggregation. Reuse the existing estimator specification in `analyses` as `{id, runner: "research" | "causal", specification: {...}}`; omit `data` and `data_record`, which the assembler supplies. Add an explicit per-analysis `sample` under the [assembly sample contract](../../econ-data/references/research-data.md#constructed-variables-and-analysis-samples) when the adopted target requires its own membership; a required common sample applies to every listed analysis.

`definitions` remains the single field dictionary. Each entry requires `unit`, `definition` and `version`. Optional metadata connects the economic object to its construction:

| Field | Adopted content |
| --- | --- |
| `role` | One role or a list from the [validated role vocabulary](../scripts/research_design.py). |
| `causal_role` | One role or a list from the [validated causal_role vocabulary](../scripts/research_design.py). |
| `source_fields`, `inputs` | Lists of original source fields and transformation input names. Inputs may include intermediate variables in the same construction. |
| `timing` | Measurement timing as text or an object. Checked adjustment timing is `pretreatment`, `baseline` or `time_invariant`, directly or in `relative_to_treatment`. Preserve the actual measurement window and information-availability date alongside that relation. |
| `rationale` | The economic path or identifying restriction that selects this variable. |
| `measurement` | Text or an object carrying the quantity, scale, numerator, denominator, exposure, price base, aggregation weights or treatment-path definition. |

Each bound analysis column requires a nonempty `source_fields` or `inputs` list. Outcomes, treatments, endogenous variables, instruments, regressors, adjustment variables, fixed effects, cohorts and running variables also require `timing` and `rationale`. An ID or auxiliary binding retains its origin and measurement definition. Definitions for unused or intermediate fields retain the optional metadata interface.

Choose the outcome from the model's observable prediction and estimand. Name the main outcome and list auxiliary measurements under it. A count, population rate, market share and mean conditional on participation use their specified populations and denominators. Bind nominal-to-real conversion to its price series and base period. Keep levels, logarithms, `log1p`, IHS, growth rates and percentage-point differences attached to their actual transformations. Record the response window and the resulting observation unit before execution.

Choose adjustment variables from the common causes, baseline outcomes and attributes, and pretreatment information that support the identifying comparison. Each actual `control`, `covariate` or effect-modifier adjustment requires `causal_role`, `timing` and `rationale`. A mediator, collider or posttreatment variable enters a conditioned comparison through an explicitly adopted `identification.adjustment_set` and `adjustment_rationale`; retain the resulting estimand and identifying conditions. Adjustments whose causal roles consist entirely of `fixed_effect`, `time_effect` or `trend` retain their adopted cell or time description. DML's nuisance learner receives the already adopted economic adjustment variables.

Treatment adoption follows the identifying variation:

| Design | Quantities and conditions retained in the specification |
| --- | --- |
| RCT | Assignment variable, assignment unit and probabilities; receipt and take-up; assignment effect or receipt estimand with its compliance conditions. `rct` binds its actual `options.treatment` to the `assignment` role. |
| IV | Endogenous treatment, excluded instrument, first stage, independence and exclusion; compliance population and monotonicity when the estimand uses those restrictions. |
| RDD | Running variable, cutoff, assignment rule and local comparison; treatment receipt and local compliance for fuzzy designs. |
| DID | First treatment or cohort, actual treatment history, never-treated or eligible not-yet-treated comparisons, anticipation, event-time reference and comparison periods. Reversals and changing doses retain their path and baseline-dose definition. |
| Continuous or multiple treatments | Dose units, treatment dimensions, the reference and changed paths, and the contrast identified by the selected official function. |
| Spillovers | Own and peers' treatment, observed network and its date, exposure mapping and interference set, with the direct or spillover contrast. |
| Structural model | The policy or primitive changed, behavioral response, equilibrium mapping and invariant primitives that define the counterfactual. |

Fix treatment dates and group membership through the adopted assignment and timing definitions. Use observed outcome values to estimate the specified contrast. Pass the resulting path to the existing method selector and the supported official runner.

`variable_design(spec)` checks the seven design objects, the existing definitions and each analysis's actual `outcome`, `outcome_pre`, `outcome_post`, treatment, regressor, covariate, endogenous, instrument, fixed-effect, cohort, running, time, weight and cluster bindings. An optional `identification.adjustment_set` must equal the actual adjustment columns in each listed analysis. It returns the design objects and `{id, runner, method, fields}` for each analysis, where `fields` maps actual input paths to column names. It raises `ValueError` for a mismatched or undefined role. The official runner owns estimator-option eligibility and execution; assembly owns the generated columns, final-column presence and sample. The input specification is preserved.

For an adopted DAG, `identification.dag` has exactly `edges` (directed node pairs), `treatment` and `outcome`; `identification.assumptions` states its causal assumptions and `adjustment_set` names the adopted columns. Its endpoints must match each listed analysis's actual treatment and outcome. The optional check detects cycles, endpoints or treatment descendants in that set, and open back-door paths under those arrows. It uses the supplied graph and adjustment set. Nodes representing unmeasured causes may appear in the edges; adjustment variables and endpoints must be defined columns. The returned result records the graph criterion and its adopted assumptions.

```sh
python3 skills/econ-design/scripts/research_design.py variables assembly.json --output variable-design.json
```

`assemble` invokes the same function when the seven design fields are supplied and saves its report in the existing construction record. The standalone command inspects that same contract. Existing assembly specifications without the design fields retain their construction interface.

## Difference-in-differences and event studies

Use for policies adopted at different times or in different places. Define adoption dates, reversals, intensity, anticipation and comparison eligibility before choosing an estimator, and state on which scale (levels or logs) untreated trends are parallel.

| Treatment pattern | Target | Estimator |
| --- | --- | --- |
| One treated cohort, one pre/post contrast | panel ATT under conditional parallel trends | outcome-regression, IPW or doubly robust two-period (`DRDID`); a common-date fixed-effects comparison when its weights match the target |
| Staggered, absorbing, binary | ATT(g, t) aggregated with the target's weights | `did::att_gt`, Sun–Abraham (`fixest::sunab`), imputation (`didimputation`, `did2s`); TWFE only after deriving its weights |
| Reversals or changing doses | effect of the observed path against the baseline path | `DIDmultiplegtDYN::did_multiplegt_dyn` (non-normalized vs normalized effects reported as such) |
| Fixed continuous dose | ATT(d) in outcome units; ACRT(d) per dose unit under strong parallel trends | `contdid::cont_did` ([continuous-DID contract](causal-models/continuous-did.md#fixed-dose-continuous-did)) |
| Several simultaneous interventions, two periods | additive first-difference coefficients | `multitreatment_did` |

Rules:

1. **Event studies:** reference period, window, eligible comparisons and the cohorts contributing at each horizon; a fixed population across horizons when the dynamic comparison requires it (`balance_e`, `same_switchers`).
2. **Covariates** by causal role and timing ([DID nuisance specifications](../../econ-data/references/implementation-calls.md#did-nuisance-specifications)); a pooled TWFE regression with the same variables does not reproduce the DR-DID ATT.
3. **Matching:** pre-treatment variables, measurement dates, common support, weights and the counterfactual-trend assumption; future-treated comparisons need an eligible pre-window.
4. **Pre-trends** are read for the same contrast and aggregation as the effect. A non-rejected test is that test's result; a claimed small pre-trend is judged against a stated magnitude and its interval. Departures from parallel trends: HonestDiD with the saved universal-reference coefficients, ordered periods and full covariance, under a stated relative-magnitude or smoothness restriction.
5. **Save** cohort-time comparisons, base periods, contributing cohorts, weights and populations at each horizon; label leads, anticipation periods, references and post-treatment ATT separately. Aggregates and their cross-horizon covariance come from the package's own aggregation (`aggregate.fixest`).
6. **Method comparisons** require the same treatment path, eligibility, switcher population, weights and estimand (`fixes::event_study` with an explicit estimator; `nonabsdid::nabs_event_study` with one engine and fixed horizons).

## Orthogonal scores and heterogeneous effects

Use when many controls need flexible adjustment or the effect varies across units.

1. Choose the target and the orthogonal score before the learners: `DoubleML` partially linear (coefficient), interactive (ATE or ATT), instrumental variants.
2. Cross-fit at the independent sampling or assignment unit, keep panel and cluster structure, tune inside training folds. Learners estimate nuisances; the design identifies.
3. `grf::causal_forest`: conditional average effects for binary unconfounded treatment; for continuous treatment the conditional covariance-to-variance slope. Cluster and unit weighting give different averages.
4. Heterogeneity claims rest on direct group contrasts, calibration or projection tests on evaluation data; a treatment-allocation rule is trained and evaluated on separate data, with value net of treatment and capacity costs.

## Structural estimation and counterfactuals

Use when the question needs behavior under conditions not observed: demand and conduct, entry, dynamic choice, general equilibrium, welfare.

1. **One specification.** Actors, objectives, feasible choices, information and timing, states and transitions, shocks, normalization, solution concept, parameters, observation process (likelihood or moments) and interventions, each mapped to its equation and code. The specification has a revision and travels into the fit, baseline, counterfactuals and every exhibit ([result lifecycle](../../econ-data/references/reproducible-workflow.md#carry-analysis-results-into-tables-figures-and-prose)); package options and convergence repairs do not change it.
2. **Identification.** For each free parameter: the variation or moment that moves it, the exclusion or restriction that permits the interpretation, the normalization separating it from payoff scale; fixed and calibrated values with their sources. Check local rank on the observed support; a full-rank Jacobian establishes the calculation, the economic restrictions establish the interpretation.
3. **Estimator by model:**

| Model and target | Identification and estimator construction |
| --- | --- |
| Random-coefficients demand and supply | Match market shares, outside market size, prices, characteristics, excluded demand/supply shifters and micro-data sampling weights to the parameter moments. Derive the demand-error orthogonality and pricing conditions before selecting the GMM weighting and covariance. A cost shifter excluded from utility identifies a different restriction from a rival characteristic whose exclusion depends on product placement. |
| Infinite-horizon discrete choice | Write choice-specific values and the Bellman operator with the actor's information and conditional transition law. NFXP solves that operator inside the likelihood; MPEC estimates parameters and value or policy objects subject to the same equilibrium equations. For CCP inversion, establish the shock distribution, choice support and normalization giving the value-difference mapping and carry first-stage CCP and transition estimation into inference. |
| Finite-horizon or discrete/continuous lifecycle choice | Specify terminal values, borrowing and participation constraints, consumption/savings timing, state support and observed histories. Select the existing representative-household growth solver for fixed-endpoint capital paths, HARK for consumption/saving policies, pylcm for individual states and employment/retirement regimes, and respy for identified finite-horizon discrete-choice parameters. Match backward induction or the consumer solver to the adopted constraints; retain solution, simulation and estimation as distinct operations through the [dynamic selection contract](dynamic-models/finite-horizon.md#official-finite-horizon-and-lifecycle-selection). |
| Dynamic competition and entry/exit | Specify simultaneous or sequential action timing, private shocks, rivals' policies and transition effects. For a BBL-style two-step estimator, estimate policies and transitions, forward-simulate discounted payoffs under the observed policy and feasible unilateral deviations, then use the resulting optimality inequalities. Solve a changed-policy equilibrium with all affected firms' best responses. |
| Auctions, search and bargaining | Specify allocation/payment or meeting rules, private/common information, participation and the relevant equilibrium. Match the observed bid, offer, duration or accepted outcome to its inversion, likelihood or moments, including reserve prices, selection and censoring. Recalculate the allocation, payments and search or bargaining policies under the intervention. |
| DSGE and aggregate policy shocks | Specify household and firm optimization, aggregate resource constraints, policy rules, shock processes, steady-state normalization and measurement equations. Match observed variables to model levels, growth rates and timing. Select linear/local perturbation or a nonlinear perfect-foresight transition from the requested shock and policy object, then solve the adopted equilibrium and evaluate its original residuals and state-transition stability. |
| Heterogeneous-agent general equilibrium | Define household asset/income states, borrowing constraints, transition risk, the cross-sectional distribution, market-clearing unknowns and aggregate targets. Solve individual policies and their distribution jointly with prices. Sequence-space impulse responses use the linearized household and market-clearing Jacobians at the adopted steady state; a finite nonlinear intervention re-solves the corresponding transition system. |
| Agent-based market or policy experiments | Define each actor's information, budget, feasible actions and behavioral policy, market matching/clearing, shock process and initial population. Map observed moments to calibrated or estimated primitives. Fix seeds and experiment assignments, retain actor histories and market/resource accounting, and compare outcomes under the same policy intervention and population weights. |


4. **Differentiated-product demand and pricing.** Markets, choice sets, outside shares and price endogeneity; excluded variation identifies price sensitivity and heterogeneity. Pricing: q(p) − Δ(p − mc) = 0, Δ_jk = −H_jk ∂q_k/∂p_j with ownership or conduct matrix H; recover markups and costs from estimated derivatives, then re-solve prices and quantities after the intervention (`PyBLP`). Holding baseline shares and derivatives fixed is a local approximation; a finite ownership or cost change is solved anew. Welfare across dates or markets needs the change in the outside option.
5. **Dynamic choice and games.** State, action, transitions (estimated from observed transitions), payoff normalization, discount factor, equilibrium selection; full-solution likelihood, CCP or simulation estimators; re-solve under the invariant primitives and the equilibrium rule ([dynamic models](dynamic-models.md)) and check the original Bellman, moment or equilibrium conditions. Macro contracts: [macro models](macro-models.md), [DSGE](dsge-models.md).
6. **Counterfactuals.** Define the changed primitive or institution, the invariant parameters, available choices, transition changes, market closure, initial population and equilibrium selection. Solve all affected prices, quantities, participation and policies together; transition paths start from the adopted initial distribution. Check residuals and profitable deviations in the original equations; with multiple equilibria keep the adopted selection or the admissible set and its action ranking.
7. **Welfare.** In stated monetary or utility units: consumer value or compensating variation, profits net of fixed and adjustment costs, public revenue, resource costs and external effects, for one population and horizon; transfers counted once; distributional weights kept. A log-sum formula uses its price coefficient and income-effect restriction.
8. **Investment and adjustment.** Specify the cost of changing each unit, the fixed cost of adjusting and irreversibility, and compare adjustment with waiting before fitting a smooth equation. Market-to-book equals the marginal value of capital only under the production, competition and adjustment-cost restrictions that make them equal; a financing mechanism needs variation in available finance separate from expected profitability.

## Random assignment and interventions

1. Assignment unit, mechanism, strata and probabilities; implementation, take-up, attrition and spillovers in the comparison.
2. Assignment effects and receipt effects are separate estimands; receipt effects rest on compliance assumptions.
3. Adjustment, weighting, randomization inference and clustering follow the assignment structure.
4. **Online and business experiments** (CAUSAL-02): persistent actor IDs, eligibility, outcome maturation, the metric's numerator and denominator, the profit comparison; the full assigned population for assignment effects; fixed-horizon or sequential stopping with matching inference; Bayesian adoption by posterior expected loss (STAT-07).
5. **Adaptive assignment:** record each pre-assignment probability and history; choose the objective (in-experiment profit, best-arm identification, later deployment) before the algorithm (INFO-02, CAUSAL-02, ADVCAUSAL-02).

## Regression discontinuity

1. Running variable, cutoff, assignment rule, compliance, support and the local parameter.
2. Continuity or local randomization, checked against manipulation, heaping, discreteness and other rules at the same cutoff (density test, covariate continuity).
3. Bandwidth, polynomial, kernel, bias correction and inference reported with the estimate (`rdrobust`); fuzzy designs divide the outcome jump by the treatment jump for the local compliers.
4. `rdplot` bins and polynomial coordinates are computed in the analysis and saved; binned-mean intervals and the robust effect interval are different objects.

## Instrumental variables and assignment leniency

1. Treatment, instrument, first stage and target population; the economic paths behind independence, exclusion and monotonicity.
2. Strength diagnostics matched to the model and the inference; weak first stage: weak-identification-robust inference (Anderson–Rubin).
3. **New policies:** with D = 1{U ≤ p} and MTE(u) = E[Y₁ − Y₀ | U = u], a shift p₀ → p₁ changes the mean by ∫ MTE(u) du over [p₀, p₁]; an instrument moving a different interval identifies a different weighted effect. When two effect schedules fit history and reverse the new ranking, obtain variation at the new margin.
4. **Judge or examiner leniency:** actual random assignment within cells, the leave-out unit from the assignment structure, estimation error in leniency, sorting and monotonicity.

## Shift-share designs

1. State whether exogeneity comes from shocks or from shares.
2. Share dates, shocks, concentration, exposure, leave-out construction and the effective assignment units.
3. Inspect the components with influential weights and their competing outcome paths.
4. Inference matched to shock dependence and exposure overlap (exposure-robust standard errors).

## Networks and spillovers

1. Relationship, measurement date, exposure mapping, own and peers' treatment, interference set.
2. Common shocks, network formation and peer selection separated from direct effects and spillovers.
3. Later treatment, migration, link changes and outcome recording traced through the exposure; inference matched to assignment and dependence.

## Synthetic controls and panel counterfactuals

1. Treated unit, donor pool, pre-treatment support and the counterfactual structure.
2. Fit, contamination, extrapolation and regularization examined; placebo and sensitivity exercises aimed at the identifying premise.
3. Inference matched to the assignment model and sampling framework.

## Inference and interpretation

1. Standard errors, clustering or randomization inference from the design's sampling and assignment variation; effective units, dependence and small-sample corrections stated.
2. Few clusters: wild cluster bootstrap (`fwildclusterboot::boottest`, `pyfixest` `wildboottest`) on the saved model with the exact null; CR2 tests with Satterthwaite degrees of freedom (`clubSandwich::coef_test`).
3. Pre-specified outcome families get multiple-testing adjustments; subgroup differences are tested directly.
4. Sensitivity: choose departures that represent the suspected confounder, find the departure that overturns the conclusion, and express it in outcome units over the evaluated period.

## Connect observed choices and outcomes to the model and interventions

- **Locate the source of a predictive failure.** Separate measurement of economic primitives, τ: X → C, from the mechanism, m: C → Y, so the prediction is m(τ(x)). Compare a repair to a proxy or primitive measurement with a change to the behavioral restriction it feeds. Examine whether competing mechanisms produce different observable predictions over the available support; if their distinguishing responses vanish there, seek variation where they separate. Compare the model with a benchmark using the same target, available information, evaluation population and loss; match training samples and parameter-selection procedures where their differences could explain the performance gap. When that benchmark predicts better, vary the model restriction suspected of causing the gap and compare performance under the same evaluation. When their performance is similar, test additional inputs on the held-out target if those inputs are available at prediction time and can change the requested prediction or action. Choose an extension for the new behavior it admits and the observed choices or outcomes that identify that behavior.

- **Separate imposed targets, inversion and identification.** Derive the requested target under the proposed functional form before estimating: Cobb–Douglas fixes the elasticity of substitution at 1, so estimating its coefficients cannot recover a different substitution elasticity. Choose a form that leaves the target free when the data can inform it. Define the forward solution y = G(a;θ) and the recovery of latent fundamentals a given y and θ as separate operations. Exact fit from that inversion can coexist with many values of θ; identify θ through additional restrictions or variation, or treat it as calibrated. Check predictions against outcomes or variation unused to force the fit, and identify which distributional or equilibrium-selection assumptions carry the identification.

- **Hold invariant fundamentals fixed and re-solve endogenous components.** For an intervention z → z′ in F(y;θ,z) = 0, justify which primitives θ remain invariant and solve the affected choices and equilibrium conditions at z′. If local productivity is A_n = A_n⁰ L_n^η, invariance of A_n⁰ permits A_n to change with employment L_n; freezing total A_n removes that feedback. Tie the affected behavioral margins to the identifying variation and specify the closure governing adjustment. Revisit the construction assumptions when the intervention changes the institution or behavior they describe.

## Construct restrictions and set-valued predictions

Use the branch matching the supplied choices, budgets or equilibrium observations and the requested target.

- **Turn feasible deviations into valid observable inequalities.** Write chosen minus deviating payoff Δπ; under expected-payoff best response, derive E[Δπ | J] ≥ 0 conditional on actor information J. Hold simultaneous opponents' actions fixed; include induced continuation choices in sequential deviations. For measurable payoff difference Δr and each nonnegative information-measurable weight h, derive the error restriction yielding E[hΔr(θ)] ≥ 0. Private choice-relevant shocks can remain selected: entry optimality (2d−1)(xβ+δd_other+ε) ≥ 0 does not allow deleting ε merely because E[ε]=0. For profit R(d)−d(θ+η), common feasible add/remove deviations and the relevant zero-mean error restrictions yield E[R(d+1)−R(d)] ≤ θ ≤ E[R(d)−R(d−1)]. Nonnegative instruments with E[η|x]=0 give weighted bounds, which can be intersected. At d=0 removal is infeasible; retain valid one-sided restrictions or derive a justified boundary correction. Trimming zero choices can invalidate the mean restriction. Adjacent deviations establish global optimality only with additional shape such as discrete concavity.

- **Eliminate selection through equilibrium-region probabilities.** Map latent payoff states into their permitted equilibrium outcomes. In a complete-information two-firm pure-entry model with strategic substitutes and zero-probability payoff ties, let q₁₀ be the probability that (1,0) is the unique equilibrium and q_S the probability that the equilibrium set is {(1,0),(0,1)}. Then observed p₁₀ = q₁₀ + λq_S with 0 ≤ λ ≤ 1 gives q₁₀ ≤ p₁₀ ≤ q₁₀+q_S. Combine these bounds with the other outcomes' probabilities and the maintained latent-state distribution. In larger games, impose one jointly feasible selection across outcomes; individual-outcome bounds alone can describe only an outer region. Realized mixed-strategy actions need the corresponding probabilistic mapping. A sharper region requires a substantive restriction on payoffs, shock distributions, support or selection; establish compatibility for every retained specification before claiming sharpness.

- **Carry the joint compatible set into the requested counterfactual.** For every jointly admissible primitive vector and permitted baseline/policy equilibrium selection, re-solve under the justified invariant primitives and map the result into T. Bound T over that joint set, preserving justified dependence across scenarios. Separate coefficient intervals generally contain combinations that the joint restrictions exclude. Historical selection need not survive a policy change, so even identified payoffs can imply multiple counterfactual outcomes. If all feasible T are positive, the sign is resolved. When the task asks for an action and rankings vary, specify its decision criterion: maximin maximizes worst-case welfare, whereas minimax regret minimizes the largest loss relative to the best action in each compatible state. Derive sampling inference from the corresponding moment restrictions and sampling design.

- **Use observed budgets to construct rationalizing preferences.** For error-free price/bundle observations (pᵗ,xᵗ) sharing stable preferences, construct the Afriat feasibility system u_s ≤ u_t + λ_t pᵗ·(xˢ−xᵗ), λ_t > 0, for every s,t. With standard positive prices and consumption budgets, feasibility characterizes locally nonsatiated utility rationalization and supplies a monotone concave continuous representation. Pooling different people imposes common preferences. For a new budget {x≥0:p·x≤m}, restrict candidates to p·x=m, then append each candidate choice and its inequalities; retain choices whose expanded system is feasible under the maintained environment. This derives a counterfactual set without selecting a parametric utility. Noisy observations require an explicit observation model, and feasible rationalization leaves multiple utilities available.

## Select the economic object

1. Descriptive question: the observed patterns and comparisons that answer it. Causal parameter: [design elements](#design-elements). Counterfactual or welfare needing behavior: [model construction](#model-construction). A reduced-form comparison is used when it suffices.
2. When several models fit the same choices, compare their predictions for the requested counterfactual or action; seek identification only where they disagree on the answer. Keep availability information when choice sets differ.
3. Transfer of a result: map the new case's choices, information, incentives and constraints onto the original relationship and derive the result under the new conditions.
4. Without full individual effects or distributions, identify the moments, bounds or group comparisons sufficient for the choice; rank options inside a restricted feasible set when only that set is identified.
5. A model for choosing an action identifies the causal response to the variable the decision-maker changes and keeps the information available at the choice.

## Reuse or calculate the requested quantities

1. Reuse summaries whose populations, periods and definitions match; compute missing ones through the data pipeline; coverage counts use the eligible population as denominator.
2. Mechanical exposure benchmarks: build the path from exposure durations and comparison outcomes, then read the remaining difference through the benchmark's assumptions.
3. Contribution in a nonlinear model: adding a component to the baseline and removing it from the joint scenario are different experiments; state which choices reoptimize.
4. Welfare: write the valuation equation in common units, count transmitted effects once, separate resource costs, transfers and weights; derive which behavioral terms vanish by optimization (sufficient statistics) and which remain through fiscal effects, externalities or distortions. A finite change z₀ → z₁ integrates the marginal effect along the path or re-solves the model; derivative × change is a local approximation.

## Deliver the selected result

Pass the mathematical object from design to execution and writing with its defining equations, the adopted symbols bound to role, indices, unit and normalization, and estimated, calibrated and imposed quantities marked:

| Requested result | Definitions and derivation carried to its consumer |
| --- | --- |
| A theoretical proposition or comparative static | State the claim on its parameter domain and feasible set, then retain the optimality or equilibrium relation and the sign, threshold or ordering that establishes it. Give existence, uniqueness and global-ranking claims their corresponding assumptions and derivation. |
| A dynamic policy, path or value | Identify the policy's action and state coordinates, the value's payoff unit, and the path's initial and terminal conditions. Carry discounting, decision timing and normalization. Define the population weights when aggregating state-specific values or histories. |
| A game equilibrium | Retain each player's contingent strategy, information set, feasible deviations and equilibrium selection. Connect the joint strategy to the resulting actions, payoffs and allocation. |
| A structural estimate and intervention | Match each estimated parameter to its observed choice or moment and each fixed or calibrated parameter to its source. Carry invariant primitives and the intervention into the separately solved prices, quantities, policies and profits. |
| A general-equilibrium comparison | Carry the household or firm policy, distribution and market-clearing prices from each scenario together. A transition comparison uses the adopted common initial distribution and each scenario's subsequent law of motion. |
| A welfare result | Define the valuation equation, reference population, horizon, discounting, resource and transfer accounting, and utility-to-money conversion. Identify whether the result averages values over the initial population or each scenario's stationary distribution. |


A decision is delivered as the objective compared across options and the choice it selects, with its parameter conditions.
