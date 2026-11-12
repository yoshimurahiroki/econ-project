# Implementation notes

Select a worked example only for a concrete unresolved implementation choice.

## Select the operation-specific rules

1. **Output: selected operation; consumer: contract reader.** Carry the adopted economic question, specification and saved inputs into the row below matching the changed object. A new pipeline starts at A; an existing calculation starts at its first affected operation. Reuse completed inputs at matching versions.
2. **Output: executable contract; consumer: implementation.** Read the selected condition with `python scripts/route_registry.py read econ-data:execute --stage contract --condition CONDITION --format compact`, replacing `CONDITION` with the selected row's value. Follow its model-knowledge command. At calculation, read the same selection with `--stage compose`; combine conditions for objects that actually change.
3. **Output: saved operation result; consumer: next row or artifact.** Pass the row's named output with its producing specification, source version and result identity. Keep language transfers at shared-table or saved-result boundaries. Before: “Estimate each language's imported sample.” After: “Build the shared table once, pass its row IDs to the selected estimator, and save that fitted sample with the result.”

| Operation and selection | Input → output → consumer | Registered condition |
| --- | --- | --- |
| A. Acquire and construct shared data | Source release, coverage and dictionary → normalized tables with grain, keys, units, periods and source correspondence → B. Use SQL for relational construction and Arrow/Parquet for adopted transfers. | New pipeline: `data_pipeline_new`; source refresh: `data_acquisition_or_update`; shared-table transfer: `data_shared_table_handoff` |
| B. Transform and describe | Shared tables and adopted eligibility, variables and weights → analysis sample, Table 1 and saved distribution/group quantities → C–F or G. | `data_sample_change` for sample construction; `data_descriptive_statistics` for summaries |
| C. Estimate regression and causal quantities | Analysis sample, estimand, design and inference → official fit, covariance and population contrast → G. | `data_regression_implementation_selection` |
| D. Predict and estimate heterogeneity | Analysis sample, prediction-time information, target population and loss/score → fitted nuisance functions, held-out predictions or treatment-effect quantities with their inference → G or a decision in F. | Causal effects: `method_orthogonal_scores_and_heterogeneous_effects`, then the selected `method_causal_doubleml` or `method_causal_grf` native fit. Prediction uses the direct read below. |
| E. Estimate structural behavior and market outcomes | Choice/market data, economic equations, moments and identification → fitted parameters, equilibrium counterfactuals and welfare → G. | `data_market_implementation_selection`; dynamic estimators use `data_dynamic_implementation_selection` |
| F. Solve dynamics and numerical decisions | Adopted states, transitions, payoffs, constraints and numerical accuracy → policies, equilibria, simulations or action values with original-equation residuals → G. | `data_dynamic_implementation_selection`; a settled numerical method uses `data_numerical_or_simulation`. Select the adopted family with `method_bayesian_implementation_selection`, `method_forecast_inventory_implementation` or `method_marketing_customer_implementation`. |
| G. Save results and build artifacts | Native fits, full-precision quantities and scientific metadata → saved result, public claims and numerical uncertainty → figures, tables, prose and project decisions. Rebuild calculations for changed scientific inputs; redraw saved quantities for presentation changes. | `data_fit_result_handoff` |

Prediction reads `python scripts/route_registry.py read data-implementation.prediction --format compact`. The selected model contract and official API own each estimator. R supplies the adopted empirical/causal fit, Python the adopted structural/learning implementation and runner connection, and Julia the adopted fixed-effect or numerical implementation. Select the language from the required mathematical object and existing environment through [engine selection](implementation-engines.md#estimator-engine-and-algorithm-selection).

## Functions, types and failure boundaries

Inspect the canonical definition, relevant callers and actual package dispatch. Prefer an existing local or official-library operation to new parsing, estimation, validation or retry code. Keep direct control flow, explicit inputs/returns and cohesive logic. Avoid one-use wrappers, speculative configuration/service layers, fragmented files and dense conditionals; add an abstraction only for a necessary shared responsibility or substantive named calculation.

Return a scalar for one quantity and a simple named record for related outputs used together; keep transparent one-use expressions local. Name quantities by economic role and computational state. Expose result-changing choices as parameters and use shared types for real interfaces. Separate acquisition/writes from calculations where order or effects matter. Explain non-obvious economic or implementation choices in comments.

Validate external types, units, options, authority and persistence at their first boundary. Validate again only after a relevant transformation or at an independently exposed interface. Remove repeated coercions and checks of established invariants; preserve cleanup, transactions, concurrency and timeouts.

Repair the first incorrect state using the actual command, options, sample, versions and diagnostic. Catch errors only where the code can recover, add useful context or clean up; otherwise propagate them. Bound retries to documented recoverable failures. Defaults, fallbacks and compatibility branches need an actual supported case. Preserve authentication, authoritative-storage and invariant failures explicitly; empty results, synthetic values and stale estimates cannot replace a failed calculation.

Update producers, consumers and imports together. Remove superseded shapes, dead helpers and duplicate branches while preserving persisted user data and active public formats. [Named totals](implementation-examples.md#example-name-a-calculation-and-its-related-totals) illustrates a substantive shared calculation.

## Compare changed calculations

Trace the affected sample, weights, formula, inference or interface through the adopted definition, official call and saved-result consumers. Keep identification, inference, input validation and original-equation convergence inside the calculation. CORE owns the single integrated review; [reproducible execution](reproducible-workflow.md) owns requested source-data/reference reproduction.

## Prediction

Define target, prediction time and available information. Split future observations for future prediction or groups for new-group prediction; keep shared information together to prevent leakage. Fit preprocessing on training data. Evaluate the intended population/period with the adopted loss or decision objective, including requested probability calibration. Return the target, split and predictions/performance.

## Replication

Use [reproducible execution](reproducible-workflow.md) for exhibit tracing and discrepancy repair; apply journal requirements to requested submissions.

<!-- BEGIN GENERATED METHOD INDEX -->
## Select a method

| Complete body | Rule | Activation | Prerequisites |
| --- | --- | --- | --- |
| [Source to analysis](implementation-data.md#source-to-analysis) | `data-implementation.source-to-analysis` | `data_pipeline_new` |  |
| [Choose descriptive statistics from the question](implementation-descriptive.md#choose-descriptive-statistics-from-the-question) | `data-implementation.choose-descriptive-statistics-from-the-question` | `data_descriptive_statistics` |  |
| [Acquisition](implementation-data.md#acquisition) | `data-implementation.acquisition` | `data_pipeline_new`, `data_acquisition_or_update` |  |
| [Data contracts and joins](implementation-data.md#data-contracts-and-joins) | `data-implementation.data-contracts-and-joins` | `data_pipeline_new`, `data_join_time_or_reshape` | [data-implementation.2-establish-schema-measurement-and-grain](implementation-data.md#2-establish-schema-measurement-and-grain), [data-implementation.3-construct-the-shared-sample-and-account-for-exclusions](implementation-data.md#3-construct-the-shared-sample-and-account-for-exclusions) |
| [Estimator, engine and algorithm selection](implementation-engines.md#estimator-engine-and-algorithm-selection) | `data-implementation.estimator-engine-and-algorithm-selection` | `data_estimator_or_engine_change` | [design-methods.choose-the-estimand-and-method](../../econ-design/references/designs.md#choose-the-estimand-and-method) |
| [Regression and causal implementation candidates](implementation-engines.md#regression-and-causal-implementation-candidates) | `data-implementation.regression-and-causal-implementation-candidates` | `data_regression_implementation_selection` | [data-implementation.estimator-engine-and-algorithm-selection](implementation-engines.md#estimator-engine-and-algorithm-selection) |
| [Market model implementation candidates](implementation-engines.md#market-model-implementation-candidates) | `data-implementation.market-model-implementation-candidates` | `data_market_implementation_selection` | [data-implementation.estimator-engine-and-algorithm-selection](implementation-engines.md#estimator-engine-and-algorithm-selection) |
| [Dynamic and numerical implementation candidates](implementation-engines.md#dynamic-and-numerical-implementation-candidates) | `data-implementation.dynamic-and-numerical-implementation-candidates` | `data_dynamic_implementation_selection` | [data-implementation.estimator-engine-and-algorithm-selection](implementation-engines.md#estimator-engine-and-algorithm-selection) |
| [Fit results and execution handoff](implementation-calls.md#fit-results-and-execution-handoff) | `data-implementation.fit-results-and-execution-handoff` | `data_estimator_or_engine_change`, `data_fit_result_handoff` | [data-implementation.estimator-engine-and-algorithm-selection](implementation-engines.md#estimator-engine-and-algorithm-selection), [data-results.carry-analysis-results-into-tables-figures-and-prose](reproducible-workflow.md#carry-analysis-results-into-tables-figures-and-prose) |
| [Functions, types and failure boundaries](implementation.md#functions-types-and-failure-boundaries) | `data-implementation.functions-types-and-failure-boundaries` |  |  |
| [Compare changed calculations](implementation.md#compare-changed-calculations) | `data-implementation.compare-changed-calculations` |  |  |
| [Numerical methods](implementation-numerics.md#numerical-methods) | `data-implementation.numerical-methods` | `data_numerical_or_simulation` |  |
| [Power calculation inputs](implementation-numerics.md#power-calculation-inputs) | `data-implementation.power-calculation-inputs` | `data_power_or_simulation` | [econ-data.power-and-estimator-simulation](workflow.md#power-and-estimator-simulation) |
| [Measured performance and memory](implementation-numerics.md#measured-performance-and-memory) | `data-implementation.measured-performance-and-memory` | `data_measured_performance_or_memory` | [data-implementation.computation](implementation-numerics.md#computation), [data-implementation.estimator-engine-and-algorithm-selection](implementation-engines.md#estimator-engine-and-algorithm-selection) |
| [Worked data examples](implementation-examples.md#worked-data-examples) | `data-implementation.worked-data-examples` |  |  |
| [Bayesian project implementations](implementation-engines.md#bayesian-project-implementations) | `data-implementation.bayesian-project-implementations` | `method_bayesian_implementation_selection` | [data-implementation.official-project-scripts](implementation-calls.md#official-project-scripts) |
| [Marketing and customer implementations](implementation-engines.md#marketing-and-customer-implementations) | `data-implementation.marketing-and-customer-implementations` | `method_marketing_customer_implementation` | [data-implementation.official-project-scripts](implementation-calls.md#official-project-scripts) |
| [Forecast and inventory implementations](implementation-engines.md#forecast-and-inventory-implementations) | `data-implementation.forecast-and-inventory-implementations` | `method_forecast_inventory_implementation` | [data-implementation.official-project-scripts](implementation-calls.md#official-project-scripts) |
| [Operations and domain implementations](implementation-engines.md#operations-and-domain-implementations) | `data-implementation.operations-and-domain-implementations` | `method_operations_domain_implementation` | [data-implementation.official-project-scripts](implementation-calls.md#official-project-scripts) |
<!-- END GENERATED METHOD INDEX -->
