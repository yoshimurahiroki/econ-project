---
name: econ-data
description: Acquire, transform, estimate and reproduce economic data and results; implement and simplify research code through its existing owners and execution paths. Execute BLP, NFXP, MPEC, structural GMM, dynamic games and equilibrium counterfactuals. Evaluate Japanese and global equities with free financial data, sustainable cash flow, valuation and news updates.
---

# Research data

## Purpose and input

[Task boundaries and completion](../../runtime/CORE.md) and [operation selection](../../docs/ai/compiled_ai_skills.md) govern this specialist. Read their applicable bodies and the selected sections below before implementation. Use [PROSE](../../runtime/PROSE.md) when explaining the result.

Input: Requested data operation, canonical specification, input documentation and saved results.

## Select the operation

Select `execute` or `equity` directly under CORE; use the [operation index](../../docs/ai/compiled_ai_skills.md) only when selection is unresolved. Use this table to select only the applicable workflow sections and registered method conditions. Read each selected body and its required premises through the end. The table locates the instructions; execution uses their complete text. Reuse complete same-version reads and saved results with matching consumed inputs.

Use the selected units' knowledge plan to retrieve their shared model contracts. Match the contract's inputs, outputs and equation bodies to the adopted calculation. Resolve a registered execution binding through this skill's engine and dependencies. For a mathematical contract whose `implementation` list is empty, derive or evaluate the stated equations through the existing implementation selector; a closed-form example uses the existing libraries or standard library. Retain the actual specification, producing calculation, returned quantities and requested verification in the result.

Select the rules from the object actually changed under [operation-specific rules](references/implementation.md#select-the-operation-specific-rules): a new analysis pipeline; acquisition or refresh; variables or observation unit; sample; joins, timing or reshape; aggregation or descriptive statistics; estimator or engine; numerical calculation or simulation; or a measured speed or memory problem. A new pipeline follows [source to analysis](references/implementation-data.md#source-to-analysis). A bounded operation starts at the affected stage with established inputs and updates its requested consumers. Use [CORE](../../runtime/CORE.md) to preserve fixed specifications, select delegated design choices and identify only user-specific inputs or permissions that need asking; carry selected definitions into their dependent calculations.

| Requested operation | Complete workflow | Activation |
| --- | --- | --- |
| Change research code or an existing implementation | [Existing owner](references/workflow.md#implement-at-the-existing-owner) | `data_code_change` |
| Acquire, map or transform research records | [Execution path](references/workflow.md#map-the-object-to-the-existing-execution-path) | The selected `data_*` operation |
| Construct measures, variables or a shared sample | [Data design](references/workflow.md#construct-a-requested-data-design) | `data_pipeline_new` or `data_schema_measurement_or_grain` |
| Estimate a structural model and solve interventions | [Structural execution](references/workflow.md#execute-structural-estimation-and-equilibrium) | `method_structural_estimation_and_counterfactuals` |
| Select a causal, market, dynamic, macro or numerical calculation | [Calculation selector](references/workflow.md#select-a-specialized-research-calculation) | The selected `method_*` condition |
| Execute or resume an adopted analysis DAG | [Dependency execution](references/workflow.md#produce-the-result-by-dependency) | `research_pipeline_requested` |
| Calculate power or simulate an estimator | [Power and simulation](references/workflow.md#power-and-estimator-simulation) | `data_power_or_simulation` |
| Search specifications or recover a failed run | [Search and recovery](references/workflow.md#specification-search-and-recovery) | `data_specification_search` or `operational_procedure_reuse` |
| Solve the finite-horizon growth model | [Macro calculation](references/workflow.md#finite-horizon-macro-calculation) | `data_macro_calculation` |
| Produce descriptive statistics | [Descriptive choices](references/workflow.md#descriptive-statistics) | `data_descriptive_statistics` |
| Change a calculation or its consumed inputs | [Changed calculation](references/workflow.md#check-the-changed-calculation) | The affected calculation |
| Evaluate an equity | [Equity evaluation](references/workflow.md#equity-evaluation) | `equity` mode |

Carry the selected specification through the existing engine, saved result and artifact consumer named by that workflow. Preserve its population, timing, measurement, estimator and inference. Select the whole workflow only when the requested work needs all of its branches.

## Deliver the data operation and its economic meaning

Return the requested data, code change or numerical result with its generating inputs and saved output location when one exists. Define a numerical result by its measurement, population, period and applicable denominator. Use econ-writing:explain for the economic explanation. Code explanations and comments state the calculation and the reasons for substantive implementation choices. Report actual operation results under CORE and EXECUTION.

For a delegated calculation, return the named quantity or requested artifact with its source and specification versions, population and units, effective engine and inference, actual operation return and output location. Match those identities to each consumer and update affected descendants through the existing dependency path. Follow [TEAM](../../runtime/TEAM.md) for return and resumption.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `execute`: Acquire, transform, join, calculate, estimate or change research data and code.
- `equity`: Evaluate Japanese, US and overseas equities from public filings, IR and market observations; estimate competition, compute sustainable cash flows, reverse valuation, after-tax investment decisions and news-driven changes.
<!-- END GENERATED MODES -->
