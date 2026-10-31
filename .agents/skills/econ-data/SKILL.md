---
name: econ-data
description: Acquire, transform, estimate and reproduce economic data and results; implement and simplify research code through its existing owners and execution paths. Evaluate Japanese and global equities with free financial data, structural IO models, sustainable cash flow, valuation and news updates.
---

# Research data

## Purpose and input

[Task boundaries and completion](../../runtime/CORE.md) and [operation ownership](../../registry/operations.json) govern this specialist. Read their applicable bodies and the selected sections below before implementation. Use [PROSE](../../runtime/PROSE.md) when explaining the result.

Input: Requested data operation, canonical specification, input documentation and saved results.

## Equity evaluation

Use mode `equity` for stock selection, intrinsic value, structural competition, financial forecasting and updates from IR or news. Read the [equity workflow](references/equity.md) and its self-contained [model and valuation reference](references/equity-models.md), then execute the linked source-processing and numerical tools. Acquire company and market observations, estimate the identified model, solve competitors' responses, compute physical cash-flow forecasts and market-implied performance, and compare attainable investment decisions after taxes and costs. A stage without its requested real-company numerical result remains unfinished. Public execution uses public data and the current user's own credentials; private connections and saved records belong to that user. Keep the five existing specialist owners: econ-literature acquires evidence, econ-design selects the identified model, econ-data executes the calculation, econ-writing explains the result, and econ-review performs requested assessment.

## Procedure

Select the rules from the object actually changed under [operation-specific rules](references/implementation.md#select-the-operation-specific-rules): a new analysis pipeline; acquisition or refresh; variables or observation unit; sample; joins, timing or reshape; aggregation or descriptive statistics; estimator or engine; numerical calculation or simulation; or a measured speed or memory problem. A new pipeline follows [source to analysis](references/implementation.md#source-to-analysis). A bounded operation starts at the affected stage with established inputs and updates its requested consumers. Use [CORE](../../runtime/CORE.md) to preserve fixed specifications, select delegated design choices and identify only user-specific inputs or permissions that need asking; carry selected definitions into their dependent calculations.

### Map the object to the existing execution path

Use [EXECUTION](../../runtime/EXECUTION.md) to locate project instructions, establish file ownership and producing commands, and preserve source inputs when changing project files. Trace the requested behavior through its callers, implementation and consumers before selecting the change.

Locate the existing entry point, specification, input documentation and saved results for the requested operation. Use [implementation notes](references/implementation.md) for acquisition, data contracts, computation, prediction or numerical methods, [numerical dependencies and replication](references/reproducible-workflow.md) for saved analysis results, and [EXECUTION](../../runtime/EXECUTION.md) for general file operations and [publication](../../harness/publication.md) when that operation is requested. Read only the branches needed for that operation.

Carry the parent question and the decision this calculation informs through its inputs, implementation and returned result. A delegated calculation inherits the governing request, fixed definitions and authorized scope through [TEAM](../../runtime/TEAM.md). On resumption, recover those sources and the saved results before choosing the next operation. Return the computed quantity with the definitions and unresolved dependency its consumer needs; completing an intermediate table leaves the parent's remaining deliverables active.

Map the requested economic object to records, fields, keys and transformations. When the intervention changes reporting, detection or recording, compare the recorded outcome with a source or stage that responds differently to that process. When a result constructs a classification or score, evaluate its target relationship with separate information. Preserve the source version, population, period, observation unit, quantity unit, denominator and adopted observation-status treatment. Choose joins that produce the intended population.

### Construct a requested data design

Inspect the source fields that define the proposed measures. Map sample eligibility, measurement support, scale, case mix, behavior and heterogeneity to their roles in the design. Define each requested metric's population, numerator, denominator, timing, aggregation and missingness treatment. Map the measured quantity to the outcome or resource use that ranks the proposed actions. Preserve each field's definition of amount due, amount paid, level, increment, conditional mean or population total; trace composition changes through the relevant counts or weights. Construct pre-treatment groups from pre-treatment information and fix membership across the comparison period.

### Implement at the existing owner

For estimation, read [the estimator and package selection branch](references/implementation.md#estimator-engine-and-algorithm-selection), match the adopted parameter to an official function and its supported options, and call that function directly from the existing analysis entry point. Confirm the installed interface before executing it. Carry the selected sample, weights, fixed effects, covariance and requested post-estimation output into the actual call; resolve an unsupported requirement through a matching implementation. Reimplement an estimator only after identifying the required feature absent from the available specialist implementations.

Use the [implementation decisions](references/implementation.md#functions-types-and-failure-boundaries) for readable control flow, reuse, abstraction, file placement and error handling. Prefer the existing function or module and supported standard-library or package operations. Implement the complete requested behavior with the fewest necessary responsibilities. Keep each rule at one owner and update its consumers together. Remove superseded branches, wrappers and files within the authorized change. Preserve functional requirements and required boundary validation, authentication and persistence behavior.

### Produce the result by dependency

For descriptive statistics, start with the economic question and choose the population, analysis unit and summary under [descriptive choices](references/implementation.md#choose-descriptive-statistics-from-the-question). Apply the adopted available-case or model sample and record or entity weights. Save the counts, denominators, weights, population, period and units that reproduce each summary. State a rate's or mean's denominator in its unit, axis, heading or defining text. Include sample and observation-opportunity differences that determine the comparison and state shared definitions once. Compute and display the summaries that answer the question.

Trace the requested result through its source, derived data, analysis object and exhibit. Reuse completed saved objects with matching dependencies; when an input, mapping, population or specification changes, recompute affected descendants. Generate tables, figures and numerical prose from the same selected quantities under the [result lifecycle](references/reproducible-workflow.md#carry-analysis-results-into-tables-figures-and-prose). Keep dependency versions and stochastic seeds in the existing records.

Keep adopted sample rules and classifications in the canonical specification. Identify a proposed specification change and the sample membership, quantities and consumers it affects; apply [CORE](../../runtime/CORE.md) to authority. Keep unresolved choices and project status in operational records.

### Check the changed calculation

Complete CORE's integrated review of the changed behavior, ownership, duplication, abstractions, branches, names and file layout. Then use its check-selection rule and [changed calculations](references/implementation.md#compare-changed-calculations) to verify the affected keys, joins, sample, weights, formula or interface. Exercise the real entry point for routing, persistence or distribution changes. Repair failures at their producing source and verify the repaired behavior. Reuse existing tests and fixtures; place necessary new coverage in the owning suite.

### Deliver the data operation and its economic meaning

Return the requested data, code change or numerical result with its generating inputs and saved output location when one exists. Define a numerical result by its measurement, population, period and applicable denominator. Use econ-writing:explain for the economic explanation. Code explanations and comments state the calculation and the reasons for substantive implementation choices. Report actual operation results under CORE and EXECUTION.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `execute`: Acquire, transform, join, calculate, estimate or change research data and code.
- `equity`: Evaluate Japanese, US and overseas equities from public filings, IR and market observations; estimate competition, compute sustainable cash flows, reverse valuation, after-tax investment decisions and news-driven changes.
<!-- END GENERATED MODES -->
