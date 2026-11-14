# Implementation rules

How to write and change analysis code. The order of work is the [execution procedure](workflow.md); this file holds the code rules and the map from each operation to its detailed reference.

## Select the operation-specific rules

Find the row of the object that changes; a new pipeline starts at A, a change to an existing calculation at its first affected row. Read the linked section before writing code for that row.

| Operation | Input → output | Read |
| --- | --- | --- |
| A. Acquire and construct shared data | source release and dictionary → tables with grain, keys, units and periods | [source to analysis](implementation-data.md#source-to-analysis), [acquisition](implementation-data.md#acquisition), [data contracts and joins](implementation-data.md#data-contracts-and-joins) |
| B. Transform and describe | shared tables, eligibility, variables, weights → analysis sample and descriptive table | [descriptive choices](implementation-descriptive.md#choose-descriptive-statistics-from-the-question) |
| C. Regression and causal estimation | sample, estimand, design, inference → official fit and covariance | [empirical procedure](empirical.md), [regression and causal candidates](implementation-engines.md#regression-and-causal-implementation-candidates) |
| D. Prediction and heterogeneous effects | sample, prediction-time information, loss → held-out predictions or effect functions | [prediction](#prediction), [orthogonal scores](../../econ-design/references/causal-models/heterogeneity.md) |
| E. Structural behavior and markets | choice and market data, equations, moments → parameters, counterfactuals, welfare | [market candidates](implementation-engines.md#market-model-implementation-candidates), [structural implementation](implementation-structural.md) |
| F. Dynamics and numerical decisions | states, transitions, payoffs, accuracy → policies, equilibria, simulations with residuals | [dynamic and numerical candidates](implementation-engines.md#dynamic-and-numerical-implementation-candidates), [numerics](implementation-numerics.md) |
| G. Save results and build exhibits | fits and full-precision quantities → saved result → tables, figures, text | [fit results and hand-off](implementation-calls.md#fit-results-and-execution-handoff), [reproducible workflow](reproducible-workflow.md) |

Language follows the mathematical object and the existing environment: R for the adopted empirical and causal fits, Python for structural and learning implementations and the runners, Julia for the adopted fixed-effect or numerical implementations ([engine selection](implementation-engines.md#estimator-engine-and-algorithm-selection)). Transfers between languages happen at shared tables or saved results. Before: "Estimate each language's imported sample." After: "Build the shared table once, pass its row IDs to the selected estimator and save that fitted sample with the result."

## Functions, types and failure boundaries

Before writing code, read the existing definition, its callers and the package call it dispatches to. Then:

1. **Reuse.** Call an existing local function or official library for parsing, estimation, validation and retries; write new code only for a missing piece.
2. **Plain structure.** Direct control flow, explicit inputs and returns, one responsibility per function. No one-use wrappers, configuration layers or scattered files; a new abstraction serves a shared responsibility or a named economic calculation.
3. **Names and returns.** Name quantities by economic role and state (`employment_pre`, `att_hat`). Return a scalar for one quantity and a small named record for related outputs. Expose every choice that changes the result as a parameter.
4. **Boundaries.** Check types, units and options where external data enter, and again only after a transformation that can break them.
5. **Failures.** Repair the first wrong state using the actual command, sample, versions and diagnostic. Catch an error only to recover, add context or clean up; otherwise let it propagate. Empty results, synthetic values and stale estimates never stand in for a failed calculation.
6. **Change together.** Update producers, consumers and imports in the same change and delete superseded code, keeping user data and public formats. [Named totals](implementation-examples.md#example-name-a-calculation-and-its-related-totals) shows a shared calculation.
7. **Comments.** Explain non-obvious economic and implementation choices in the code.

## Compare changed calculations

Trace the affected sample, weights, formula, inference or interface through the definition, the official call and every consumer of the saved result. Record the old and new value of each affected quantity in the worksheet. Identification, inference, input checks and convergence of the original equations stay inside the calculation; requested reproduction of published results follows [reproducible execution](reproducible-workflow.md).

## Prediction

Define the target, the prediction time and the information available then. Split by future periods for forecasting and by groups for new-group prediction, keeping shared information on one side. Fit preprocessing on training data only. Evaluate on the intended population and period with the adopted loss or decision objective, including calibration when probabilities are used.

## Replication

Use [reproducible execution](reproducible-workflow.md) to trace exhibits to code and repair discrepancies.

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
| [Power calculation inputs](implementation-numerics.md#power-calculation-inputs) | `data-implementation.power-calculation-inputs` | `data_power_or_simulation` | [econ-data.power-and-estimator-simulation](workflow.md) |
| [Measured performance and memory](implementation-numerics.md#measured-performance-and-memory) | `data-implementation.measured-performance-and-memory` | `data_measured_performance_or_memory` | [data-implementation.computation](implementation-numerics.md#computation), [data-implementation.estimator-engine-and-algorithm-selection](implementation-engines.md#estimator-engine-and-algorithm-selection) |
| [Worked data examples](implementation-examples.md#worked-data-examples) | `data-implementation.worked-data-examples` |  |  |
| [Bayesian project implementations](implementation-engines.md#bayesian-project-implementations) | `data-implementation.bayesian-project-implementations` | `method_bayesian_implementation_selection` | [data-implementation.official-project-scripts](implementation-calls.md#official-project-scripts) |
| [Marketing and customer implementations](implementation-engines.md#marketing-and-customer-implementations) | `data-implementation.marketing-and-customer-implementations` | `method_marketing_customer_implementation` | [data-implementation.official-project-scripts](implementation-calls.md#official-project-scripts) |
| [Forecast and inventory implementations](implementation-engines.md#forecast-and-inventory-implementations) | `data-implementation.forecast-and-inventory-implementations` | `method_forecast_inventory_implementation` | [data-implementation.official-project-scripts](implementation-calls.md#official-project-scripts) |
| [Operations and domain implementations](implementation-engines.md#operations-and-domain-implementations) | `data-implementation.operations-and-domain-implementations` | `method_operations_domain_implementation` | [data-implementation.official-project-scripts](implementation-calls.md#official-project-scripts) |
<!-- END GENERATED METHOD INDEX -->
