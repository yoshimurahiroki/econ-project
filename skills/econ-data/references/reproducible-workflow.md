# Reproducible execution

Use [CORE](../../../runtime/CORE.md) for required reading, reasoning, execution, integrated review and verification. Use [EXECUTION](../../../runtime/EXECUTION.md) for general files and delivery, [state](../../../harness/state.md) for persistent version-linked reuse and restart, and the applicable [publication](../../../harness/publication.md) section for a requested publication operation.

Use the existing contracts for [complete output replacement](../../../runtime/EXECUTION.md#complete-outputs-and-failure-propagation), [multi-file publication](../../../harness/publication.md#complete-generation-boundary), and [Git staging, moves and scoped commits](../../../harness/publication.md#working-files-git-and-delivery). Read the [affected-branch example](#example-recompute-the-affected-branch) when that implementation is needed.

## Locate the requested result

Map each requested table, figure or numerical claim to its saved inputs, sample, specification, producing code and execution command. Establish the producer by following its writes and consumers; a filename mentioned in prose or a script is only a reference. Preserve access instructions, dependency versions and seeds in the existing record. Apply econ-data's dependency rules to reuse unchanged objects and regenerate affected outputs.

## Entry point and dependencies

The [local research runner](../../../harness/research.md) implements this lifecycle through `state.py`: declare the adopted stages, actual files and named consumed outputs in one analysis manifest, then execute commands or numerical templates. Each successful stage selects a complete generation only after its outputs and current dependencies match. The same unchanged invocation reuses its completed stages. A changed source, helper, environment or adopted definition rebuilds its affected branch; failed stages preserve previous generations and block their current dependents. Connect rendering placeholders to the exact saved statistic and unit.

Use [EXECUTION's runner and environment rules](../../../runtime/EXECUTION.md#select-the-operation-and-working-area). Trace the numeric chain input → transformation → estimate → exhibit, attaching the adopted sample and estimator definitions at the stages that establish them.

Bind the selected Python, R or Julia interpreter and package closure through the [existing runtime contract](../../../harness/research.md#capture-the-selected-python-r-or-julia-environment). Put the actual interpreter in `argv` and `runtime.probe_argv`, and any interpreter invoked by that stage in `runtime.companions`. Use `runtime.packages` for the selected package versions and `runtime.files` for the adopted requirements, Pixi/rv locks or Julia Project/Manifest files; also declare those files as stage inputs. Use `runtime.requirements` when the complete named requirement file defines the selected environment.

Files referenced inside an analysis specification participate in that stage's input identity. The research runner resolves its existing entry points' data, construction records, canonical tables, model sources and saved-result references using the producer's path rules, including generated specifications from completed dependencies. Store generated table and analysis references relative to their containing record or specification so publishing the generation preserves them. Table formats and SQL execution select the corresponding reader and engine packages in the declared runtime. Declare external wrapper commands in the stage's `executables` list.

Track the inputs that determine output identity: data version, code and relevant helpers, adopted definitions, parameters, seeds and relevant environment settings. Reuse an output only when those dependencies match and its completion is established; timestamps or an existing filename alone may miss changed definitions or interrupted writes. Rebuild affected descendants and retain unaffected results. Use the current dependency record rather than creating another status store. When persistent task state is needed, map these used artifacts and definitions to `consumes` under [the state contract](../../../harness/state.md); `after` records start order only. Track the consumed output ID, content version and definition versions, not every output of its producer. An unused sibling output does not invalidate this result or its comparison records. A changed consumed definition invalidates affected results even when their displayed values match. Add a publication group only when the request requires joint publication.

When presentation changes would rerun costly estimation, save the model quantities and requested diagnostics under the lifecycle below. Use the existing result object and dependency system. Add persistent caching when avoided computation exceeds storage and dependency-management costs. Keep one producer for each result; update that producer and its consumers instead of adding a parallel pipeline or status store.

## Carry analysis results into tables, figures and prose

Apply this lifecycle when producing, managing or reusing analysis outputs. For a bounded explanation or prose revision, use the supplied table's sufficient estimates, definitions and adopted selection directly; obtain row identities or refit only for a requested calculation that requires them. Retrieve other calculation inputs only when the requested claim, comparison or new statistic requires them.

For reusable analysis, use the project's existing keys or records for a stable identity of the economic question or requested output, the adopted specification revision, and each execution attempt. A single calculation needs no new registry. A rerun changes the run identity; a specification change also changes the revision. Select the intended result explicitly under the publication rule below.

Attach the calculation's contract by reference to the saved result: source and derived-input versions, actual selected sample and exclusion rule, outcome and regressor definitions, and the estimator. For regression, include the formula or equivalent design, fixed effects, category encodings and reference levels, weight meaning and normalization, and requested inference settings such as clustering unit, small-sample adjustment or resampling scheme. Retain actual fitted-row identities or a reproducible sample artifact, not just the intended filter or observation count; estimation can remove further rows. Include units, population, period and denominator where they define the statistic. These fields are conditional: an unweighted descriptive total needs its inclusion rule and units, not invented fixed effects or a covariance estimator. Reuse the adopted specification and sample records rather than duplicating their text in every row.

Save reusable numeric quantities in a versioned structured result with named keys. Preserve precision for downstream calculations and round at rendering. Identify a coefficient by its variable, transformation, level or interaction and reference-category meaning. Give a contrast its own key and defining expression or weights over the named terms. Keep the ordered design-to-key mapping when a library's matrix order matters. A changed term meaning requires a changed definition; a display-label edit retains the key. Compute a point contrast from the named estimates and weights. For each requested post-estimation calculation, retain its required fitted object, complete covariance or resampling draws and the environment needed to load them.

For model-based results, carry the [design handoff's](../../econ-design/references/designs.md#deliver-the-selected-result) equation-to-quantity mapping in the existing adopted definitions. Use the model fields supported by [saved display metadata](../../econ-writing/references/result-artifacts.md#save-displays-at-analysis-or-registration) for contract and knowledge locators, equations, notation, parameter roles, assumptions, normalization, equilibrium selection, welfare definition and horizon. A parameter role includes its source and unit; a policy or value includes its state and time coordinates. Keep full calculated paths in `source_result` and place their adopted scenario definition in the display metadata. The artifact specification's `sources[].metadata` can attach these established definitions when registering a saved result.

Record fit status and each requested quantity's status in the existing result object. Mark a collinear term or reference level with its actual status; preserve an estimated zero as a numeric estimate. Determine fit completion from the estimator's adopted termination condition and the actual return. Apply the task's diagnostic-use rule to intermediate solver output. Release each downstream calculation when its named inputs are present and complete, and retain the recorded cause of an omitted quantity.

Make tables, figures and numerical prose consumers of the same selected numeric result and definitions. When several outputs reuse it, map each cell, point or sentence to its statistic key and specification in the existing build record. Display conversions, rounding, labels and layout belong to rendering. A changed outcome scale, contrast or denominator changes the calculation and its dependencies, including when requested through a figure edit. Keep technical provenance in result and operational records; research prose states the economic definition, mechanism and requested quantities under PROSE.

Use the existing `gallery select` operation to hand the chosen display rows, `metadata.result_definitions` and `source_reference` to writing. Match a sentence's quantity to its selected `result_id`, named row or statistic, unit and scenario; use the saved equation and parameter roles to explain the mechanism. Selection reads the registered content and preserves its source version. A requested calculation that changes a contrast, valuation or equilibrium returns to its producing analysis and updates the affected result and prose through the same dependencies. Revisions to wording, notation labels or exhibit layout consume the established quantities.

For reusable descriptive tables and plots, save the calculated summary at its declared grain with the relevant group, period or bin keys, statistic, usable count, denominator, weights, population, period and units that reproduce its definition. Retain bin edges and interval closure for binned data; retain the chosen quantile convention for quantiles. Reference the shared sample, weight definition and units instead of copying their definitions into every row. Let the table, plot and caption consume that summary. State a rate's or mean's denominator in the unit, axis, table heading or explanatory text that defines the quantity. Show differences in compared samples or observation opportunities and state common definitions once. Choose displayed information for the reader's understanding, comparison and judgment; saved counts and denominators need not all appear in every exhibit. Keep display order, labels, colors, output dimensions and format in the existing rendering specification. A label change reuses the summary; a changed denominator, group definition, binning or quantile convention regenerates the affected summaries and consumers. Keep missing cells distinguishable from observed zero cells in that shared object.

For a comparison, match named quantities and trace the changed source, sample, measure, specification and estimator. To isolate a requested component within scope, hold the other components fixed and compare the resulting named quantities. Give each common-sample or specification-specific result its own population and identity. Report the quantities that change and attribute each contribution to the comparison that establishes it.

Select the current result for each intended output through the project's existing specification-to-run mapping or manifest. Publish a complete result only when it matches that selection and the selection has not been superseded, using the [publication boundary](../../../runtime/EXECUTION.md#complete-outputs-and-failure-propagation). This keeps exploratory variants, failed retries and older attempts finishing late from replacing the adopted result. A prior complete result remains usable for outputs selecting its dependencies; outputs requesting revised dependencies wait for a matching result. See the [worked result lifecycle](#example-reuse-a-named-estimate-without-losing-its-definition) for a compact record and operation trace.

## Complete outputs and failure propagation

Use [publication contract](../../../runtime/EXECUTION.md#complete-outputs-and-failure-propagation) to expose a complete output generation; use [state](../../../harness/state.md) to resume a failed stage when persistent state is needed. Use its [working files and delivery rules](../../../harness/publication.md#working-files-git-and-delivery) for relocation, Git and packaging.

The runner drains command output into a bounded diagnostic in the existing execution result. SIGINT and SIGTERM stop the command's process group and later stages. A complete prepared result resumes publication; an interrupted unfinished calculation starts in a fresh generation on the next invocation. An observed terminal calculation failure uses the explicit repair-and-retry procedure in the runner contract.

Interpret empty results through the stage's contract and [sample-accounting rules](implementation-data.md#3-construct-the-shared-sample-and-account-for-exclusions). For a permitted zero-row result, publish the expected schema, count and input/rule identity. If estimation requires observations, stop that dependent stage and record the unavailable estimate in the internal execution record. A missing required file, a truncated file, or a header-only file where rows are required is incomplete even when the process exits successfully.

## Reproduce the requested path

Run the requested path through its actual entry point and inspect the requested outputs. Use the full pipeline for a requested clean reproduction or a result that requires the full dependency chain. Compare affected outputs with the specified reference using the adopted tolerance or one derived from rounding and numerical calculation. Reuse established checks of unchanged inputs. Trace a mismatch to its sample, source version, definition or calculation; repair the producing error, regenerate affected consumers and repeat their comparison. Keep the reproduced quantities and their source correspondence in the requested research output. This operation is selected by an explicit reproduction request; it is never an automatic development or distribution gate.

## Deliver the reproduced result

Deliver the requested result and comparison with the source under econ-data's output and reporting rules. Generate requested text and exhibits from the reproduced quantities and definitions.

## Worked project operations

Use these fictional examples for numeric-result reuse or incremental rebuilding. General publication and Git examples are linked above in EXECUTION.

### Example: reuse a named estimate without losing its definition

**Use when:** an adopted weekly-hours regression feeds a table, coefficient figure and one numerical sentence. The existing runner saves specification and sample records and publishes a selected run. The following is a fictional compact result record, not a mandatory schema. Its referenced specification defines `weekly_hours ~ training + age | site`, binary training participation, age in years, no weights, and site-clustered CR1 covariance with a t reference distribution and 23 degrees of freedom; it also records encoding and the fitted design. The sample record identifies the input snapshot, complete cases and any estimation exclusions, with fitted person IDs. The analysis concerns an association; this record alone does not establish a causal effect.

```yaml
record_version: 1
analysis: training_hours
specification: hours_s3
run: hours_s3_r02
inputs: derived_people_v7
sample: fitted_hours_s3_v7
fit_status: completed
sample_summary: {observations: 480, site_clusters: 24}
statistics:
  coefficient.training:
    status: estimated
    estimate: 1.25
    unit: hours_per_week
    standard_error: 0.50
    inference: {covariance: site_CR1, reference: t, degrees_of_freedom: 23}
  coefficient.age:
    status: estimated
    estimate: 0.00
    unit: hours_per_week_per_year
    standard_error: 0.02
    inference: {covariance: site_CR1, reference: t, degrees_of_freedom: 23}
```

**Operation trace:**

1. Complete the fit, retain its sample and design mapping, and extract estimates by semantic term key. Match the covariance calculation, cluster IDs, reference distribution and degrees of freedom to the adopted inference specification. Save the complete result under `hours_s3_r02`; the existing selection for the main output then points to that run. The version identifies the record format; the specification and run keys identify the research choices and execution separately.
2. The table and figure read `coefficient.training`, and the prose renderer uses its value and units. The sentence states, “Training participation is associated with 1.25 additional weekly hours.” All three use the same selected run. A label correction rebuilds the affected display while reusing the fit. Preserve the age coefficient's estimated zero and the producer's unrounded value.
3. A requested point contrast involving training and age uses a defined change in age and a named weighted combination of their estimates. Compute the contrast from the saved values. Retrieve the matching complete covariance or draws for any requested post-estimation calculation that consumes them; obtain missing inputs from the matching fit. Preserve the completed point contrast for its own consumers.
4. An authorized specification `hours_s4` adds a control with missing values. Save a new fitted-sample record and run. Compare fitted IDs as well as estimates. If the requested comparison needs to isolate the control's contribution and permits the calculation, fit `hours_s3` on the new common sample as a separately identified diagnostic. Distinguish its comparison with `hours_s4` from the change caused by restricting the original sample.
5. If the new control is collinear, record that term as `omitted` with reason `collinear` and no estimated value; do not print 0.00. If the run fails instead, retain a failed run status without publishing a replacement estimate. An output requesting `hours_s4` stays blocked; the completed `hours_s3_r02` remains usable only for outputs still selecting that specification. A delayed `hours_s3` attempt cannot replace a later adopted selection merely because it finishes last.

**Decision criterion:** reuse is established by matching definitions, inputs, sample and completion, then selecting the intended named quantity. Renderers consume estimates; they do not choose the preferred specification, reinterpret missing values, or reconstruct statistical inference from formatted tables.

### Example: recompute the affected branch

**Use when:** deciding whether an approved edit changes a saved quantity or only its display. This operation trace follows a small existing dependency graph.

The graph records these dependencies:

```text
input_file:     content of inputs/people.csv
sample_rule:    approved minimum age and missing-age exclusion rule
figure_labels: title and axis wording

records      <- input_file
sample       <- records, sample_rule
estimate     <- sample
table        <- estimate
figure       <- estimate, figure_labels
```

The input file is tracked by its contents. The existing runner also tracks producing code, called helpers and relevant environment settings; these remain unchanged in the three traces below. `sample_rule` and `figure_labels` are separate tracked configuration inputs. The `sample` object carries selected records and the adopted rule revision; the saved estimate carries that revision and the input fingerprint forward. A renderer reads those saved quantities.

**Expected operation trace:**

- Title correction: change only `figure_labels` from “Mean weekly hour” to “Mean weekly hours.” Rebuild the figure. Reuse `records`, `sample`, `estimate`, and `table`; their numerical provenance is unchanged.
- Approved sample revision: change minimum age from 18 to 21. In this fictional input, some retained people are aged 18–20 and their removal changes the mean. Rebuild `sample`, `estimate`, `table`, and `figure`. Reuse `records`, because the input bytes and import definition are unchanged. Update the sample revision attached to the estimate and exhibits.
- Source correction at the same CSV path: a changed content fingerprint invalidates `records`; reassess and rebuild the affected descendants. Reuse requires matching content and definition dependencies plus established completion.

**Decision criterion:** follow declared dependencies and changes in values or required provenance. A content-aware engine may skip later computations when an upstream recomputation yields an identical tracked value. Consequently, required definition/provenance revisions must themselves be tracked dependencies; a changed sample definition cannot silently inherit an old exhibit's provenance just because a mean happens to match. Confirm the actual run/skip record before reporting what rebuilt. A request for clean reproduction has a different scope from this incremental revision.

