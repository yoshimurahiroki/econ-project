# Data execution operations

Select the applicable registered operation and section.

## Equity evaluation

Select the actual purpose: `equity_acquisition`, `equity_cash_flow`, `equity_fit`, `equity_dynamic`, `equity_valuation`, `equity_rates`, `equity_news_update` or `equity_investment_decision`. A full company evaluation combines acquisition, cash flow, the adopted model fit/dynamics, valuation and investment decision; reuse valid saved inputs and fits under CORE. For a model-specific derivation, use `index --operation econ-data:equity --family section-equity --query TEXT` and activate the matching section. Add rate transmission when it affects the selected case. Read every selected section completely before its dependent calculation.

Mode `equity` uses the [equity workflow](equity.md) and [valuation models](equity-models.md). Acquire real company/market observations, estimate the identified competition model, solve responses, forecast physical cash flows and market-implied performance, and compare attainable after-tax decisions. Complete the requested numerical stage. Public execution uses public data and the user's credentials; private connections and records remain user-owned.

## Procedure

### Execute structural estimation and equilibrium

Read the adopted [structural specification](../../econ-design/references/designs.md#structural-estimation-and-counterfactuals), selected engine and numerical procedure. Carry identification, state/action timing, transitions, normalization and equilibrium selection into the specialist interface. Estimate and solve baseline/intervention outcomes from the same fitted primitives; retain specification revision and scenario with prices, quantities, policies, profits and welfare. Existing demand/game calculations also use `equity.py fit` and `dynamic`.

### Map the object to the existing execution path

Locate the operation's entry, specification, source documentation and saved result. Select the relevant implementation or [result lifecycle](reproducible-workflow.md) procedure. For observed command/environment reuse, activate `operational_procedure_reuse` and match the [saved procedure](../../../harness/research.md#retain-and-reuse-an-observed-procedure) to actual inputs, failure and current authority.

Map the economic object to records, fields, keys and transformations. Preserve population, period, observation unit, units, denominator and observation-status treatment. If the intervention changes reporting/detection, use a source or stage responding differently to distinguish recording from the outcome. Evaluate a constructed classification/score against separate target information.

### Construct a requested data design

1. **Output: source-to-variable map; consumer: source-specific cleaning.** Inspect the original fields and adopted economic definitions. Specify population, observation unit, period, units, numerator/denominator, timing and observation statuses in the existing [assembly `definitions`](research-data.md#constructed-variables-and-analysis-samples). Retain amount due/paid, level/change and conditional/population targets in their adopted roles. Bind source version and inspected documentation through [definition references](../../../harness/state.md#retain-and-retrieve-adopted-definitions).
2. **Output: normalized shared tables and dictionary; consumer: analysis construction.** Clean each source through its existing `assemble` stage. Store reusable attributes at their determining grain, with complete primary keys in `grain`, foreign-key relationships in the declared joins, and source/version/units in `data-record.json`. Save one shared table per adopted grain through the [SQL and language handoff](research-data.md#shared-tables-across-sql-python-r-and-julia). Preserve the source population and observation statuses in these tables; apply analysis eligibility in step 3. Before: “Each estimator parses household and programme files.” After: “Build household, programme-month and household-month tables once; join their saved keys for each adopted analysis.”
3. **Output: analysis inputs and sample accounting; consumer: estimation and description.** Read the hashed shared tables, construct the adopted variables, weights and calendar histories, then build the shared sample once. Form pre-treatment groups from prior information and retain their membership. Use `analyses` for estimator columns and explicitly adopted analysis-specific samples. Pass the selected table, hashed `data_record`, definitions and retained row IDs to the existing runner; its saved result carries fitted membership and inference to artifacts.
4. **Output: affected generations; consumer: dependent calculations.** Add new source information at the shared table's existing producer, update its dictionary and bind the new table/record hashes in dependent stages. Rebuild the affected analysis and result descendants through the existing DAG; reuse matching results for display changes. Retain originals and inspected source passages in the private research record; distribute independently authored examples and public citations under the release procedure.

### Implement at the existing owner

Match the adopted parameter to an [official estimator/interface](implementation-engines.md#estimator-engine-and-algorithm-selection) and call it from the existing analysis entry. Carry sample, weights, fixed effects, covariance and post-estimation requirements into that call. An unsupported feature requires a matching implementation; custom estimation requires a demonstrated missing specialist feature.

Resolve an implementation choice governing many fits/exhibits before expanding them. Reuse valid fitted objects and keep each scenario's prices, shares, costs and policies together in its decision quantity. [Implementation rules](implementation.md#functions-types-and-failure-boundaries) own code structure; EXECUTION owns files and dependencies.

### Select a specialized research calculation

Use `index --operation econ-data:execute` only to resolve an unknown method condition. Select the individual `method_*` for a known calculation; `method_extended_*` loads a whole family only when that coverage is requested. The registry supplies complete equations, scientific restrictions and execution dependencies, replacing a second hand-maintained method table here.

Select `research_data_discovery` for data acquisition/analysis tables, `research_adaptive_experiments` for source-grounded proposals and `research_result_artifacts` for saved-statistic articles/slides. Use each family's pinned interpreter/requirements; respy, pylcm and Dolo retain separate compatible environments. Preserve existing Pixi, R and project infrastructure.

### Produce the result by dependency

Execute an adopted analysis DAG through the [research runner](../../../harness/research.md), binding actual sources, scripts, helpers, environment, specifications and consumed output IDs. `--parent` carries the governing task's request, choices, scope and holds. Declare Python/R/Julia and its package closure; use a named profile when execution paths differ.

The causal selector/runner supplies official DoubleML, GRF and randomizr interfaces. `research.py` retains OLS, IV, partial-linear orthogonal-score and two-period panel-DID execution with its declared requirements, fitted IDs, covariance and folds. Other selected scientific owners execute their adopted model.

Trace source→derived data→fit→exhibit. Reuse matching stages; changed inputs, mappings or definitions rebuild affected descendants. Tables, figures and numerical prose use the same selected saved quantities. Preserve stochastic seeds and actual dependency versions; reproduction packages use the exact current saved stages.

### Power and estimator simulation

For requested power/MDE/simulation, match DGP, assignment/dependence and test to the estimand. `research.py power` supports its two-arm Gaussian pooled-t individual/cluster design, noncentral-t power/MDE and seeded Monte Carlo diagnostics. DID, IV or structural power uses its own adopted DGP/estimator. Retain specification, code and runtime identities.

### Specification search and recovery

Freeze target, population, sample, evaluator, inference and discovery/validation/holdout roles. Run the finite declared grid, retain unsuccessful candidates/returns and execute the selected branch. Causal candidates retain their identifying restrictions and target parameter and use the adopted diagnostic comparison; predictive loss alone does not establish causal validity. `research.py evaluate` supports fixed-split OLS/Ridge with train-only preprocessing. Read [recovery](../../../harness/research.md#recover-interrupted-attempts) for killed-process reconciliation or observed repair reuse.

### Finite-horizon macro calculation

Use [the macro solver](../scripts/research_macro.py) for the representative-household growth model with explicit initial/terminal capital, productivity, tax paths, parameters and residual tolerance. It returns positive scenario paths/welfare and original Euler/resource/derivative checks. Other macro models use their selected package and observation map.

### Descriptive statistics

Choose population, analysis unit and summary from the economic question through [descriptive choices](implementation-descriptive.md#choose-descriptive-statistics-from-the-question). Use adopted available-case/model samples and record/entity weights. Save counts, denominators, weights, period and units. Define each rate/mean's denominator in its heading, axis or text; include observation-opportunity differences determining the comparison.

### Check the changed calculation

Apply [changed-calculation review](implementation.md#compare-changed-calculations) to affected keys, joins, sample, weights, formula or interface. Keep scientific inference and numerical convergence inside execution.

## Execution specification

Use the existing producer and official package interface. Carry population, timing, measurement, sample, weights, estimator and inference through its saved result and artifact consumer. [Implementation rules](implementation.md) own code structure; [engine selection](implementation-engines.md) owns estimator and runtime choices. Numerical, structural, dependency and recovery procedures apply only to their registered cases.

Read the selected model contract's equations, inputs and outputs through econ-knowledge. Resolve its registered engine and dependencies; a contract without an implementation supplies a mathematical interface for derivation or calculation through existing libraries.
