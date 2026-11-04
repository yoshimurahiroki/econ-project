---
name: econ-data
description: Acquire, transform, estimate and reproduce economic data and results; implement and simplify research code through its existing owners and execution paths. Execute BLP, NFXP, MPEC, structural GMM, dynamic games and equilibrium counterfactuals. Evaluate Japanese and global equities with free financial data, sustainable cash flow, valuation and news updates.
---

# Research data

## Purpose and input

[Task boundaries and completion](../../runtime/CORE.md) and [operation selection](../../docs/ai/compiled_ai_skills.md) govern this specialist. Read their applicable bodies and the selected sections below before implementation. Use [PROSE](../../runtime/PROSE.md) when explaining the result.

Input: Requested data operation, canonical specification, input documentation and saved results.

## Equity evaluation

Use mode `equity` for stock selection, intrinsic value, structural competition, financial forecasting and updates from IR or news. Read the [equity workflow](references/equity.md) and its self-contained [model and valuation reference](references/equity-models.md), then execute the linked source-processing and numerical tools. Acquire company and market observations, estimate the identified model, solve competitors' responses, compute physical cash-flow forecasts and market-implied performance, and compare attainable investment decisions after taxes and costs. A stage without its requested real-company numerical result remains unfinished. Public execution uses public data and the current user's own credentials; private connections and saved records belong to that user. Keep the five existing specialist owners: econ-literature acquires evidence, econ-design selects the identified model, econ-data executes the calculation, econ-writing explains the result, and econ-review performs requested assessment.

Before acquisition, implementation or calculation, apply [CORE task entry](../../runtime/CORE.md#task-entry). Read the applicable data, estimator, numerical or equity reference and its required dependencies in full; retrieve knowledge IDs and their true prerequisites only when the calculation needs them. An engine name, summary, heading or knowledge lookup does not replace these bodies, the adopted specification or this specialist's execution responsibility.

## Procedure

When the pending operation needs a library definition, derivation, model condition or worked example, activate [econ-knowledge](../econ-knowledge/SKILL.md) and select the needed IDs and required prerequisites. Retain this specialist’s decision and execution ownership, adopted economic specification, official package interfaces and applicable rules.

Use the selected units' knowledge plan to retrieve their shared model contracts. Match the contract's inputs, outputs and equation bodies to the adopted calculation before choosing its execution binding. Resolve the binding through this skill's registered engine and dependencies, then retain the actual specification and returned quantities in the producing result.


### Execute structural estimation and equilibrium

Read the adopted [structural specification](../econ-design/references/designs.md#structural-estimation-and-counterfactuals) and use [engine selection](references/implementation.md#estimator-engine-and-algorithm-selection) and [numerical methods](references/implementation.md#numerical-methods) for its actual model. Carry parameter-to-moment identification, state/action timing, transitions, normalization and equilibrium selection into the installed specialist interface. Estimate, solve the baseline and changed equilibrium, and produce the requested prices, quantities, policies, profits and welfare from the same fitted primitives. Preserve the specification revision and scenario in the existing result objects. The existing demand and finite-state game implementations also serve research calculations through their documented `fit` and `dynamic` entry points.

The [structural research case](scripts/research_structural_case.py) executes independently specified synthetic demand, ownership and dynamic comparisons through these same numerical owners. It emits complete specifications, source and engine hashes, full fitted/scenario results and named statistic/unit bindings for the common research renderer.

Select the rules from the object actually changed under [operation-specific rules](references/implementation.md#select-the-operation-specific-rules): a new analysis pipeline; acquisition or refresh; variables or observation unit; sample; joins, timing or reshape; aggregation or descriptive statistics; estimator or engine; numerical calculation or simulation; or a measured speed or memory problem. A new pipeline follows [source to analysis](references/implementation.md#source-to-analysis). A bounded operation starts at the affected stage with established inputs and updates its requested consumers. Use [CORE](../../runtime/CORE.md) to preserve fixed specifications, select delegated design choices and identify only user-specific inputs or permissions that need asking; carry selected definitions into their dependent calculations.

### Map the object to the existing execution path

For requested reuse of an observed project command or environment repair, select `operational_procedure_reuse` and use the [existing experience helper](../../harness/research.md#retain-and-reuse-an-observed-procedure). Match the actual producing run, applicability and current target authority before adopting its proposed steps.

For a measured repeated-reading, failed-command or execution-log problem, use the existing [optional task controls](../../harness/state.md#optional-execution-controls-and-observed-usage), version-bound operational facts and focused saved-log views. Compare the complete requested result and optimization overhead on the same inputs. Keep unmeasured features disabled. Use the [context packer's](../../scripts/pack_context.sh) optional symbol map when a structural lookup improves the pending operation; an exact known owner goes directly to its current source. Preserve the complete mandatory instructions, adopted estimand, numerical conditions and required verification through these paths.

Use [EXECUTION](../../runtime/EXECUTION.md) to locate project instructions, establish file ownership and producing commands, and preserve source inputs when changing project files. Trace the requested behavior through its callers, implementation and consumers before selecting the change.

Locate the existing entry point, specification, input documentation and saved results for the requested operation. Use [implementation notes](references/implementation.md) for acquisition, data contracts, computation, prediction or numerical methods, [numerical dependencies and replication](references/reproducible-workflow.md) for saved analysis results, and [EXECUTION](../../runtime/EXECUTION.md) for general file operations and [publication](../../harness/publication.md) when that operation is requested. Read only the branches needed for that operation.

Carry the parent question and the decision this calculation informs through its inputs, implementation and returned result. A delegated calculation inherits the governing request, fixed definitions and authorized scope through [TEAM](../../runtime/TEAM.md). On resumption, recover those sources and the saved results before choosing the next operation. Return the computed quantity with the definitions and unresolved dependency its consumer needs; completing an intermediate table leaves the parent's remaining deliverables active.

Map the requested economic object to records, fields, keys and transformations. When the intervention changes reporting, detection or recording, compare the recorded outcome with a source or stage that responds differently to that process. When a result constructs a classification or score, evaluate its target relationship with separate information. Preserve the source version, population, period, observation unit, quantity unit, denominator and adopted observation-status treatment. Choose joins that produce the intended population.

### Construct a requested data design

Inspect the source fields that define the proposed measures. Map sample eligibility, measurement support, scale, case mix, behavior and heterogeneity to their roles in the design. Define each requested metric's population, numerator, denominator, timing, aggregation and missingness treatment. Map the measured quantity to the outcome or resource use that ranks the proposed actions. Preserve each field's definition of amount due, amount paid, level, increment, conditional mean or population total; trace composition changes through the relevant counts or weights. Construct pre-treatment groups from pre-treatment information and fix membership across the comparison period.

### Implement at the existing owner

For estimation, read [the estimator and package selection branch](references/implementation.md#estimator-engine-and-algorithm-selection), match the adopted parameter to an official function and its supported options, and call that function directly from the existing analysis entry point. Confirm the installed interface before executing it. Carry the selected sample, weights, fixed effects, covariance and requested post-estimation output into the actual call; resolve an unsupported requirement through a matching implementation. Reimplement an estimator only after identifying the required feature absent from the available specialist implementations.

When an unresolved implementation choice governs many later fits or exhibits, execute its determining operation first: recover the requested contrast with its sample and population weights, or solve the changed equilibrium with its corresponding outcomes. Use an existing valid fitted object where available. Carry scenario-specific prices, shares, costs and policy assignments together into the decision quantity. Repair an unsupported call or mismatched object at its producer before expanding the dependent run.

Use the [implementation decisions](references/implementation.md#functions-types-and-failure-boundaries) for readable control flow, reuse, abstraction, file placement and error handling. Prefer the existing function or module and supported standard-library or package operations. Implement the complete requested behavior with the fewest necessary responsibilities. Keep each rule at one owner and update its consumers together. Remove superseded branches, wrappers and files within the authorized change. Preserve functional requirements and required boundary validation, authentication and persistence behavior.

### Select a specialized research calculation

Select the matching registered condition and read its model reference before running its specification. Each interface accepts the declared scientific inputs, invokes its calculation engine, and saves fitted quantities, adopted definitions, numerical checks and named statistics for the same research DAG.

| Calculation | Registered condition | Model and execution contract |
| --- | --- | --- |
| Causal and empirical models | `method_extended_causal` | [Causal models](../econ-design/references/causal-models.md): fixed effects, IV and weak-IV sets, staggered DR-DID, RDD, synthetic controls, dynamic panels, causal forests, policy evaluation, network/spatial designs and limited outcomes. |
| Demand, supply and market design | `method_extended_markets` | [Market models](../econ-design/references/market-models.md): joint PyBLP estimation, endogenous prices/characteristics, equilibrium interventions, auctions, search, bargaining, platforms and matching. |
| Dynamic choices and games | `method_extended_dynamic` | [Dynamic models](../econ-design/references/dynamic-models.md): observed panels, stationary and finite choices, CCP, simulation moments, game inequalities, sequential estimators, continuous time, hidden types and dynamic demand. |
| Macro and heterogeneous agents | `method_extended_macro` | [General equilibrium](../econ-design/references/macro-models.md) and [stochastic equilibrium](../econ-design/references/dsge-models.md): observed productivity, equilibrium paths, lifecycle policies, Sequence-Space Jacobians and policy welfare. |
| Agent simulations | `method_agent_simulation` | [Agent models](../econ-design/references/agent-models.md): trade, learning, conservation, fixed interventions and result-dependent next experiments. |
| Numerical kernels | `method_extended_numerics` | [Numerical methods](../econ-design/references/numerical-models.md): derivatives, sparse Python/Julia systems, constrained fits, JAX devices, original-equation surrogate verification and Monte Carlo comparisons. |

Use `research_data_discovery` for [official data acquisition and declared analysis tables](references/research-data.md). Use `research_adaptive_experiments` for [source-backed candidate proposals and result-dependent experiments](../econ-design/references/adaptive-research.md). Their commands consume the existing state, files and stage receipts. Select `research_result_artifacts` to [register saved statistics and generate articles and slides](../econ-writing/references/result-artifacts.md). Restore only the selected family's pinned requirements in a compatible Python 3.12 scientific environment; the causal family uses its own pandas 3 environment. Preserve the project's existing infrastructure, Pixi and R environments.

### Produce the result by dependency

For an adopted local analysis DAG, execute the [research runner](../../harness/research.md) with its explicit sources, scripts, helpers, environment, specification files and consumed output IDs. Bind an existing governing task with `--parent` so its original request, decisions, scope and holds govern every stage. Its immutable generations and existing state receipts identify completed calculations, selective rebuilding and the files consumed by tables, figures and prose. Declare the actual Python/R runtime and selected package closure for environment-aware reuse, and choose a named development/formal profile when the adopted execution paths differ. Build the requested reproduction package from the exact current saved stages through the same guide. Use the [estimation interface](scripts/research.py) for supported OLS, IV, partial linear orthogonal scores and two-period panel DID specifications; it calls the official specialist engines and preserves fitted IDs, named estimates, covariance, actual fold assignments and inference. Restore its [declared numerical dependencies](scripts/requirements-research.txt). Use the existing `equity.py fit` and `dynamic` interfaces for their adopted structural models and call another selected specialist directly when its economic object requires it. The [executed research case](scripts/research_case.py) creates an independently specified Python/R simulation and measures selective rebuilding from generated inputs through estimates to the paper.

For a requested power, minimum-detectable-effect or estimator simulation, match the DGP, assignment unit and dependence to the adopted estimand and test. `research.py power` implements the documented two-arm Gaussian pooled-t individual/cluster design, its noncentral-t power and MDE, and seeded Monte Carlo bias, RMSE, rejection, coverage and simulation uncertainty. Preserve the specification, code and runtime identities. Use another adopted estimator/DGP for DID, IV or structural power; the two-arm calculation does not justify their inference. Compare a valid case with the consequential violated restriction when assessing a method.

For specification search, freeze the target, population, sample, evaluator, inference and discovery/validation/holdout partitions in the adopted protocol. Expand its finite parameter grid through the same runner, compare the declared metrics and execute the selected next branch. Use `research.py evaluate` for fixed-split OLS or Ridge prediction with train-only preprocessing. Choose a causal specification through its identifying restrictions and target parameter, and apply its adopted diagnostic comparison. Preserve unsuccessful candidates and their actual returns. Read [recovery and procedure reuse](../../harness/research.md#recover-interrupted-attempts) before reconciling a killed process or reusing an observed repair; the current task retains its authority and fixed scientific choices.

For the finite-horizon representative-household growth model, use [the macro solver](scripts/research_macro.py) with explicit initial and terminal capital, productivity, output-tax paths, calibrated parameters and residual tolerance. It solves positive consumption and capital choices, returns scenario-specific paths and welfare, and checks the original Euler/resource equations and analytic derivatives. Select the specialist package and observation map for another adopted macro model through the existing engine-selection procedure.

For descriptive statistics, start with the economic question and choose the population, analysis unit and summary under [descriptive choices](references/implementation.md#choose-descriptive-statistics-from-the-question). Apply the adopted available-case or model sample and record or entity weights. Save the counts, denominators, weights, population, period and units that reproduce each summary. State a rate's or mean's denominator in its unit, axis, heading or defining text. Include sample and observation-opportunity differences that determine the comparison and state shared definitions once. Compute and display the summaries that answer the question.

Trace the requested result through its source, derived data, analysis object and exhibit. Reuse completed saved objects with matching dependencies; when an input, mapping, population or specification changes, recompute affected descendants. Generate tables, figures and numerical prose from the same selected quantities under the [result lifecycle](references/reproducible-workflow.md#carry-analysis-results-into-tables-figures-and-prose). Keep dependency versions and stochastic seeds in the existing records.

Keep adopted sample rules and classifications in the canonical specification. Identify a proposed specification change and the sample membership, quantities and consumers it affects; apply [CORE](../../runtime/CORE.md) to authority. Keep unresolved choices and project status in operational records.

### Check the changed calculation

For requested specification consistency or implementation completion reconciliation, select `specification_reconciliation_requested` and use [Analyze and Converge](../../harness/state.md#analyze-and-converge). Bind the adopted requirement IDs to the existing tasks, implementation files, decisions and executable checks. Repair each reported gap at its producer and reconcile the current outputs and actual execution returns before completing the task.

Complete CORE's integrated review of the changed behavior, ownership, duplication, abstractions, branches, names and file layout. Then use its check-selection rule and [changed calculations](references/implementation.md#compare-changed-calculations) to verify the affected keys, joins, sample, weights, formula or interface. Exercise the real entry point for routing, persistence or distribution changes. Repair failures at their producing source and verify the repaired behavior. Reuse existing tests and fixtures; place necessary new coverage in the owning suite.

### Deliver the data operation and its economic meaning

Return the requested data, code change or numerical result with its generating inputs and saved output location when one exists. Define a numerical result by its measurement, population, period and applicable denominator. Use econ-writing:explain for the economic explanation. Code explanations and comments state the calculation and the reasons for substantive implementation choices. Report actual operation results under CORE and EXECUTION.

For a delegated calculation, return the named quantity or requested artifact with its source and specification versions, population and units, effective engine and inference where used, actual operation return and output location needed by the owner. Match those identities to each consumer before reuse and update affected descendants through the existing dependency path. After interruption, handoff or loss of context, restore the original request, authority, fixed specification, completed results and mandatory rule bodies that are unread, changed or no longer available in the active context through [TEAM's resumption contract](../../runtime/TEAM.md#resumption); reuse same-version reads and valid results. Continue the authorized calculation and requested consumers through their actual completion conditions.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `execute`: Acquire, transform, join, calculate, estimate or change research data and code.
- `equity`: Evaluate Japanese, US and overseas equities from public filings, IR and market observations; estimate competition, compute sustainable cash flows, reverse valuation, after-tax investment decisions and news-driven changes.
<!-- END GENERATED MODES -->
