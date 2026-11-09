# Implementation notes

Use [CORE](../../../runtime/CORE.md) for required reading, substantive reasoning, execution, integrated review and verification. Preserve fixed specifications and exercise delegated design authority. Ask for an essential user-held input or permission at the dependent action. Use [DECIDE](../../../runtime/DECIDE.md) for a method choice, [EXECUTION](../../../runtime/EXECUTION.md) for authorized operations, and the applicable [publication](../../../harness/publication.md) section for a requested publication operation.

Use the matching worked example and its input contract for [shared samples](implementation-examples.md#example-one-sample-for-counts-and-moments), [query-engine reduction](implementation-examples.md#example-reduce-in-the-query-engine-before-collecting), [repeated cluster draws](implementation-examples.md#example-preserve-repeated-cluster-draws), [decision-time information](implementation-examples.md#example-match-information-available-at-the-decision), [lookup-key diagnosis](implementation-examples.md#example-diagnose-join-multiplicity-before-attaching-values), or [named calculations and totals](implementation-examples.md#example-name-a-calculation-and-its-related-totals).

## Select the operation-specific rules

Select the changed object and activate the matching condition in the method index below. Combine conditions when several objects change; established inputs let a bounded operation begin at its affected stage. For a new pipeline, `data_pipeline_new` selects source construction, acquisition, joins and computation together. Read every selected body and its registered prerequisites completely, then carry its output into the existing result lifecycle.

Use [Functions, types and failure boundaries](#functions-types-and-failure-boundaries) for a changed data boundary, calculation interface or reusable implementation, and [Compare changed calculations](#compare-changed-calculations) for the affected numerical comparison. Select a worked example only for its concrete pending choice. `python scripts/route_registry.py read RULE_ID` returns the complete selected text and prerequisites; continue through `next_offset` until null.

## Functions, types and failure boundaries

Use [project-file ownership](../../../runtime/EXECUTION.md#project-file-ownership) to retrieve the owning definition, its complete current body and the relevant callers. Check the installed package's actual dispatch or wrapper when it determines which calculation runs. Search for a working local implementation and the standard-library or installed-package operation before writing parsing, formatting, validation, retry or data-shaping logic. Extend that owner and use supported package interfaces. Keep changes tied to the requested behavior and its consumers.

Implement the current requirement with direct control flow and explicit inputs and returns. Use clear `if` branches, descriptive names and intermediate values when they expose a calculation. Keep cohesive logic together. Avoid one-use wrappers, speculative configuration, service layers and fragmented files; dense expressions and nested conditionals also reduce readability. Match the project's conventions. Comments explain an economic or implementation decision whose reason the code does not show.

Name quantities by economic role and computational state: raw, within-transformed, solver-weighted or working response. Expose choices that alter the result as parameters. Use a shared type when its shape, units or option set defines a real interface. Isolate acquisition and writes from substantive calculations when their effects or execution order obscure the result.

Extract shared logic when real consumers implement the same rule and must change together. A substantive named calculation can also justify extraction when its units, denominator or independent use become clearer. Keep a transparent one-use expression local. Return one scalar for one quantity, or a simple named record for related outputs that travel together; the [named-totals example](implementation-examples.md#example-name-a-calculation-and-its-related-totals) shows this choice. Introduce an abstraction only when its necessary responsibility and concrete callers are established.

Validate external inputs at the boundary that first establishes their contract: source types and units, required configuration, supported public options, authentication, authorization, ownership and persistence. Parse documented representations once, then let internal calculations use the established contract. Validate again where a transformation changes the relevant property or an independently exposed entry point receives external input. Remove repeated null checks and coercions that reproduce an established invariant. Preserve required cleanup, transactions, concurrency controls, timeouts and boundary validation.

Trace a failed operation to the first incorrect state and repair that owner. For a recurring fit or pipeline failure, compare the effective options, sample, input revision and actual diagnostic under EXECUTION's recovery rule; change the component identified by that diagnosis while preserving the adopted specification. Catch an error where the code can perform the defined recovery, add actionable input context or clean up a resource; propagate it otherwise. Use bounded retries for documented recoverable failures. Add defaults, fallbacks or compatibility branches only for a current interface or task requirement with an identifiable trigger and outcome. Keep authentication, authoritative-storage and invariant failures explicit. Empty results, synthetic values and stale estimates cannot substitute for a failed requested calculation.

When a contract changes, update its producers, consumers and imports together. Remove superseded internal shapes, dead helpers and duplicate branches. Retain support required by persisted user data, active external consumers or a supported public format at the boundary that owns it. Do not preserve draft shapes through new aliases or rejection-only guards. Apply CORE's verification policy and retain each research requirement in its canonical owner.

## Compare changed calculations

Apply [CORE](../../../runtime/CORE.md#completion-and-reporting) to the integrated review and the actual requested operation. Read the adopted formula, official function, input contract, relevant callers and saved-result consumers. Resolve errors at the owner of the changed sample, weights, formula, inference or interface. Inspect the actual generated file, saved destination or external operation return when completing an authorized write.

Keep statistical inference, identification restrictions, input validation and the original-equation convergence criterion in the research execution itself. Preserve the returned estimator status, named quantities and adopted population. An expressly requested reproduction study uses its stated source data, specification and reference quantities through [reproducible execution](reproducible-workflow.md).

An implementation change uses the source, official API and the verification selected under CORE. A real research execution produces its requested scientific result. Rule and expression adherence remains with CORE and PROSE.


## Prediction

Define the target, prediction time and information available then. Choose a split representing the requested use: hold out future observations for future prediction, or hold out groups when predicting for new groups. Keep observations sharing information together when separation would leak information across that split. Fit preprocessing on training data. Evaluate the target level or change in the intended population and period using the requested loss or decision objective. Keep post-outcome information outside inputs; assess probability calibration when requested. Return predictions or performance with the target and split.

## Replication

Use [reproducible execution](reproducible-workflow.md) for exhibit tracing, comparison and discrepancy repair. Apply the journal's requirements to a requested submission.

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
