# Implementation notes

Use [CORE](../../../runtime/CORE.md) for required reading, substantive reasoning, execution, integrated review and verification. Preserve fixed specifications and exercise delegated design authority. Ask for an essential user-held input or permission at the dependent action. Use [DECIDE](../../../runtime/DECIDE.md) for a method choice, [EXECUTION](../../../runtime/EXECUTION.md) for authorized operations, and the applicable [publication](../../../harness/publication.md) section for a requested publication operation.

Use the matching worked example and its input contract for [shared samples](implementation.md#example-one-sample-for-counts-and-moments), [query-engine reduction](implementation.md#example-reduce-in-the-query-engine-before-collecting), [repeated cluster draws](implementation.md#example-preserve-repeated-cluster-draws), [decision-time information](implementation.md#example-match-information-available-at-the-decision), [lookup-key diagnosis](implementation.md#example-diagnose-join-multiplicity-before-attaching-values), or [named calculations and totals](implementation.md#example-name-a-calculation-and-its-related-totals).

## Select the operation-specific rules

Select sections from the objects actually changed. Combine matching branches when an operation changes several objects; established inputs let a bounded operation begin at its affected stage. Read a linked worked example when its concrete operation is needed.

- **New analysis pipeline:** [Source to analysis](implementation.md#source-to-analysis), [Acquisition](implementation.md#acquisition), [Data contracts and joins](implementation.md#data-contracts-and-joins), and [Computation](implementation.md#computation) cover acquisition through analysis.
- **Acquisition or refresh:** [Acquisition](implementation.md#acquisition) and [1. Establish the received source and revision](implementation.md#1-establish-the-received-source-and-revision) establish the delivery and input revision.
- **Variables or observation unit:** [2. Establish schema, measurement and grain](implementation.md#2-establish-schema-measurement-and-grain) defines fields, measurement and row units.
- **Sample:** [3. Construct the shared sample and account for exclusions](implementation.md#3-construct-the-shared-sample-and-account-for-exclusions) and [4. Prepare the estimation input](implementation.md#4-prepare-the-estimation-input) cover eligibility, exclusions and the actual estimation sample.
- **Joins, timing or reshape:** [Data contracts and joins](implementation.md#data-contracts-and-joins) covers keys, join multiplicity and correspondence.
- **Aggregation or descriptive statistics:** [Choose descriptive statistics from the question](implementation.md#choose-descriptive-statistics-from-the-question) selects summaries for the requested economic quantity.
- **Estimator or computation engine:** [Estimator, engine and algorithm selection](implementation.md#estimator-engine-and-algorithm-selection) matches the estimator contract and implementation.
- **Numerical calculation or simulation:** [Numerical methods](implementation.md#numerical-methods) covers the calculation, convergence and reproducible simulation design.
- **Measured speed or memory problem:** [Measured performance and memory](implementation.md#measured-performance-and-memory) selects changes to complexity, reading and aggregation from the observed bottleneck.

Use [Functions, types and failure boundaries](implementation.md#functions-types-and-failure-boundaries) when the selected operation changes a data boundary, calculation interface or reusable implementation. Use [Compare changed calculations](implementation.md#compare-changed-calculations) for the affected numerical comparison and the [result lifecycle](reproducible-workflow.md#carry-analysis-results-into-tables-figures-and-prose) when saving or consuming analysis results. These dependencies follow the changed object; they do not expand a bounded operation into a new pipeline.

## Source to analysis

Use the stages below for an end-to-end task, saving outputs in the project's existing data objects, metadata and work record. For a bounded task, start with the affected stage's established inputs and stop after the requested consumers. Under an execution hold, return the proposed mapping and identify the unperformed sample, join or calculation comparisons in the handoff governed by [TEAM](../../../runtime/TEAM.md).

### 1. Establish the received source and revision

Input: the supplied files or authorized acquisition request, source documentation and the requested population and period. Identify the exact release or vintage and receipt/query details under [Acquisition](implementation.md#acquisition); distinguish a frozen reproduction from a refresh. Compare a revised delivery with the prior input's coverage, fields and measurement definitions before reusing its transformations.

Output: an identified source snapshot with its coverage and revision recorded. Continue when the required partitions and documented coverage are present and the requested vintage is established. Repair an incomplete delivery through the authorized acquisition path. Preserve a fixed vintage. When vintage selection is delegated, compare releases against the requested information set and choose under CORE; obtain available source documentation before deciding. Ask only when changing a fixed vintage or a user-specific choice requires authority or input not already supplied. A later revision is not automatically the correct input. A change confined to supplied values under the same contract still invalidates affected downstream results. If a required source cannot be obtained, identify the missing input and continue only independent branches.

### 2. Establish schema, measurement and grain

Input: the identified source and adopted measure definitions. Compare field names, types, categories, units and row grain with the expected contract, including across partitions. A documented rename or representation change can be mapped in the source-to-derived producer; an unknown field meaning, changed population or changed measurement requires source clarification or a design decision before the dependent transformation. Retain the original fields and revision so the mapping is inspectable. Apply the existing [identifier, join and timing rules](implementation.md#data-contracts-and-joins) where those operations enter.

Separate an observed zero from unavailable, suppressed and censored observations using source status fields or documented codes. Preserve the status when creating a numeric analysis field; a suppressed amount or an unobserved record cannot become zero through parsing, filling or aggregation. Use the adopted treatment of each status. When a missing treatment changes the requested calculation, resolve it from authorized documentation or applicable adopted settings; choose within delegated design scope under CORE. Ask only for a user-specific input or permission needed to change a fixed treatment.

For unit conversions, record the source and target units, conversion factor or series, and applicable dates and price base. Apply conversions at the unit where the factor is defined before aggregating when factors vary. For aggregation, define the resulting row unit, numerator, denominator and weight meaning together: a population rate uses the included numerator total divided by its corresponding exposure total, not an unweighted mean of subunit rates. Establish which units contribute to both totals and preserve missing coverage; an unknown component does not prove a complete total. A zero denominator yields an undefined rate under the stated contract, not a zero rate.

Output: the requested schema or measurement mapping with field definitions, source correspondence and intended grain; produce mapped derived records only when transformation is in scope. A documentation-only schema task finishes with that mapping and its unresolved field meanings. When a calculation follows, continue when its required fields have known meanings and the mapping preserves its population and quantities. Repair parsing, conversion or grain errors at their producer. Preserve fixed measurement and aggregation definitions. Select a needed definition within delegated design scope under CORE and carry it into dependent calculations; a convenient substitute is not a reason to change the economic object. Ask for authorization only when the change exceeds that scope.

### 3. Construct the shared sample and account for exclusions

Input: the mapped records and adopted eligibility, missingness and timing rules. Implement those rules once in the shared sample builder or relation used by counts, moments and model consumers. For a variable-specific descriptive question, derive its available-case subset from that eligibility definition; use the model's joint sample when describing model observations or comparing quantities on a stipulated common sample. Keep original row identities, inclusion status and applicable exclusion reasons. Count starting units and retained units at the same grain; when aggregation changes that grain, report the source-to-output counts separately rather than label the difference as sample attrition.

Distinguish two exclusion summaries. Overlapping reason counts describe every applicable reason on the starting population and can count a unit more than once. Sequential counts use an explicit rule order and count only newly excluded units among those remaining; these counts plus the retained count must equal the starting count. Keep the full reason flags even when assigning a first exclusion reason. Report a weighted population or exposure loss separately when row counts do not describe the relevant denominator. The [shared-sample example](implementation.md#example-one-sample-for-counts-and-moments) shows how counts and moments consume one definition.

If selection uses the outcome or a post-treatment variable, identify that dependence and its effect on the target population. Use [empirical design](../../econ-design/SKILL.md#for-an-empirical-specification) to resolve an unadopted restriction within delegated design scope under CORE; if it changes a fixed specification, obtain the missing authority. Do not describe it as neutral cleaning or silently substitute a pre-treatment rule. When already adopted, retain the rule and make its conditioning explicit in the analysis handoff.

Output: the shared sample, retained identities and exclusion accounting under one rule version. Continue when membership implements the adopted rules and the counts reconcile. If a required subset is unexpectedly empty, trace the first stage where it disappears through source coverage, parsing, matching and filtering. Repair an implementation defect; if the adopted rules genuinely produce no observations, identify that finding and resolve the design decision within delegated scope under CORE, or ask for the missing authority to change fixed rules for an estimate requiring that subset. Do not relax filters to manufacture observations. A deliberately empty descriptive cell may be reported as empty, with undefined means or rates left undefined.

### 4. Prepare the estimation input

Input: the shared sample and adopted estimator, outcome, regressors, transformations, weights and inference units. Build the model columns and encodings from that sample using [estimator, engine and algorithm selection](implementation.md#estimator-engine-and-algorithm-selection). Carry row identities and column definitions with the analysis object. Account for additional losses caused by lags, transformations, missing model fields or estimator-specific omissions; reconcile the fitted sample with the shared sample rather than accepting undocumented library deletion. For a requested common-sample comparison, use the adopted common sample across specifications; report intentionally different samples separately.

Output: an estimation-ready object with its actual sample, design columns, weight meaning and inference identifiers, or an exact unsupported requirement. Continue when the implemented estimator and its usable comparison satisfy the adopted specification. Repair encoding or mapping errors within that specification. If no valid treatment comparison, variation or required inference units remain, return the specific feasibility problem to econ-design instead of switching models or covariance rules. Descriptive-only tasks can pass their shared sample and defined summaries directly to the next stage without constructing a model matrix.

### 5. Hand off the analysis and its dependencies

Input: the prepared analysis object and the authorized requested calculation. Perform the calculation and [compare changed calculations](implementation.md#compare-changed-calculations), then pass saved quantities and the [result contract](reproducible-workflow.md#carry-analysis-results-into-tables-figures-and-prose) to the requested exhibit or to econ-writing:explain for interpretation. Include the exclusion summary and any difference between the shared and fitted samples.

Output: the requested analysis result or prepared input, its generating path, interpretation conditions and missing dependencies. Continue to dependent exhibits when their inputs match the completed calculation; repair a failed calculation before publishing its descendants. For later source, sample or specification changes, resume at the first affected stage and rebuild affected descendants, reusing unrelated matching results.

### Example: distinguish overlapping reasons from sequential attrition

Fictional operation: six shops have unique IDs A–F at one survey wave. The adopted order is eligibility, observed outcome, then observed regressor. A is eligible with observed outcome zero and an observed regressor; B is ineligible with both fields missing; C is eligible with both fields missing; D is eligible with an observed outcome and missing regressor; E and F are eligible with both fields observed. No values are suppressed or censored. Apply the stipulated complete-case rule.

On all six shops, overlapping reason counts are ineligible `1` (B), missing outcome `2` (B, C), and missing regressor `3` (B, C, D). Their sum of `6` is not the excluded population. Sequentially, eligibility excludes `1` and leaves `5`; observed outcome excludes `1` more and leaves `4`; observed regressor excludes `1` more and leaves `3`. Thus `6 = 1 + 1 + 1 + 3`; the excluded union is B, C, D, and retained IDs are A, E, F. A's zero remains observed. Reversing the rule order changes first-reason counts but not retained IDs under these conjunctive rules. Keep both the reason flags and the stated order so the summaries answer their distinct questions.

## Choose descriptive statistics from the question

Start with the population and period the question concerns, the unit receiving equal or weighted representation, and the quantity to summarize. Reuse adopted definitions; resolve a missing choice when it changes the economic object. Save the selected summaries with their sample definition, units, grouping keys and denominators for downstream tables and plots.

- **What is observed?** On the eligible population, count usable observations, observed zeros, missing values and suppressed values separately; retain censoring information where present. Zero is a subset of observed values, not a separate exclusion. Save variable-specific usable counts for available-case summaries and display them where differences in support affect the comparison. Do not discard an observed outcome merely because an unrelated regressor is missing. For a model-sample description, use the actual fitted sample, including estimator omissions. A shared denominator must be deliberate rather than the accidental result of a library dropping rows.
- **Whose typical experience?** A record-level mean in a panel weights entities with more usable periods more heavily. For the average entity's period-average outcome, first form each entity's average over the defined period support, then average entities with the adopted entity weights. For the average period's population outcome, aggregate within period first. State how incomplete period coverage enters; neither equal entity weights nor an unbalanced record mean repairs missing periods. Distinguish the number of records, entities and periods where each matters.
- **How much, how often, or how large on average?** Use a sum for the amount across included units, retaining coverage so an observed subtotal is not described as a complete population total. Use total events divided by corresponding total exposure for an exposure rate, with the eligible numerator and denominator formed on the same support. Use an arithmetic mean for an equally represented analysis unit, or `sum(w*y) / sum(w)` on the same usable value–weight pairs for the adopted weighted mean. Establish whether weights represent frequency, population expansion, exposure or another adopted role; a normalized weighted mean is not an expanded population total. Account for missing or unusable weights and require a defined, nonzero denominator.
- **Where is the distribution concentrated?** Use a median or selected quantiles for a typical rank or tail question; use a mean when the question concerns expected amounts or additive totals. Select spread or tail summaries when those features matter rather than assuming the mean describes them. Record quantile probabilities, interpolation or order-statistic convention, and any weighting convention; match these across engines. A median of subgroup medians is not generally the pooled median. Do not silently drop genuine extremes or replace a mean with a median to make the result look stable.
- **Which group supplies the denominator?** For within-group rates or shares, divide by that group's eligible exposure or count; for a group's share of the population total, divide by the corresponding across-group total. Identify missing group labels and groups with no usable values. A zero count of observed events with positive exposure can give a zero rate; an empty group or zero exposure cannot. Keep counts, denominators and group definitions alongside comparisons so composition changes remain visible.
- **Which measure of dispersion?** Standard deviation uses variation among the defined units, the chosen variance divisor and the weight convention. Calculate each requested statistic using its adopted sampling, clustering or survey design. A descriptive-dispersion request uses the selected descriptive measure.
- **Conditional on what?** Label a summary among participants, employed people, positive outcomes or another selected group with that condition. To describe the whole target population, use its unconditional observations or combine conditional quantities with the relevant group shares under the adopted definition. An adjusted model prediction at fixed covariates differs from a prediction averaged over a stated covariate distribution; neither is automatically the raw observed mean. Keep the conditioning set or averaging population with the saved result.

### Example: choose available cases and the represented unit

Fictional operation trace: five eligible shop–month records cover shops A–D in a two-month window. A has observed sales `0` and `18`; B has one observed value `6`; C has one missing value; D has one suppressed value. Sales use the same toy currency and price base. A's second record has a missing regressor; the other four records have that regressor observed. Unrecorded shop–months are outside this supplied coverage, not observed zeros. The stipulated descriptive question uses available observed sales; the stipulated model uses complete cases on sales and the regressor.

The eligible records number `5`: sales are observed on `3`, missing on `1` and suppressed on `1`; the observed-zero count is `1` within the `3`. The observed subtotal is `0 + 18 + 6 = 24`, and the record-weighted mean is `24 / 3 = 8`. Sorted observed values are `0, 6, 18`, so the middle-observation median is `6`. For an equally weighted average of the two shops' available-period means, A contributes `(0 + 18) / 2 = 9` and B contributes `6 / 1 = 6`, giving `(9 + 6) / 2 = 7.5`; this is not a balanced two-month population mean. The model sample retains A's first record and B's record, so its descriptive mean is `(0 + 6) / 2 = 3`. These results answer different questions; none turns the observed subtotal into sales for all four shops.

## Acquisition

Use the official endpoint and implement its pagination, timeout and rate handling. Keep credentials outside source files and outputs, using the project's secret mechanism or environment variables. Preserve the source version, acquisition date, query and input identity, using a checksum when needed to distinguish the acquired bytes. Inspect source records to establish coverage and completion, then save the acquired inputs for reuse subject to their access terms. Make refresh explicit; keep a frozen-input reproduction separate from a new acquisition. File existence alone does not establish completeness or freshness. Separate acquisition from transformation.

## Data contracts and joins

Before combining or transforming sources, identify each stage's observation unit, key, quantity units, eligible population and output grain. Keep reusable attributes and their grain-specific transformations in a keyed table at the grain that determines them, such as state-year policy in a state-year table, then join them into analysis rows as needed. Preserve received raw files and generate lower-level copies from that keyed producer. Use the [shared-sample rules](implementation.md#3-construct-the-shared-sample-and-account-for-exclusions) for counts, sums and denominators, including database null-skipping aggregates, and the [measurement rules](implementation.md#2-establish-schema-measurement-and-grain) for observed zero, missing, suppressed and censored values. Label intentionally different variable-specific descriptive samples.

Choose a join from the intended population and relationship: check uniqueness on the side expected to be unique, declare one-to-one, many-to-one or intentional many-to-many matching, and inspect unmatched records and row multiplication against that relationship. Resolve duplicate keys by their economic meaning rather than retaining an arbitrary row. Use explicit source lists when an uncontrolled directory scan could admit stale or unrelated files.

When keys repeat, inspect the repeated records before choosing a remedy. If they are duplicate ingestion of the same source record, remove the repeated ingestion in the source-to-derived transformation while retaining its provenance. If they are distinct periods, versions or subunits, complete the key, apply the adopted version rule, or aggregate to the required grain with the defined weights and denominator. Conflicting values at the same intended key require source reconciliation; neither `first` nor an arbitrary average resolves the conflict. An intentional many-to-many relationship needs a defined resulting unit and allocation rule where amounts would otherwise be counted repeatedly. Compare multiplicity by key, as in the [join diagnostic](implementation.md#example-diagnose-join-multiplicity-before-attaching-values), rather than relying on total row count: losses and expansions can offset.

When rows do not match, distinguish a malformed identifier or missing source partition from genuine absence under the adopted population. Repair the former at its producer; retain the latter with explicit missingness when the target population includes it. Restrict to matched rows only when the adopted design defines that intersection, and carry the excluded identifiers and counts into the sample record. A missing lookup is not a zero outcome. If completeness is required for the next calculation, stop that dependent calculation with the affected keys instead of quietly dropping them. Investigate right-only keys when the source is meant to cover the same population; extra historical or out-of-scope records alone need not block a valid left-population calculation.

When reading identifiers or categories, choose representation from their meaning before parsing. Keep codes such as `001` as strings when leading zeros distinguish or define valid identifiers; a numeric round trip cannot recover lost width without a source-defined format. Normalize spaces, case or padding only under the source's identity rules, then check whether normalization merged distinct keys. For categorical regressors, preserve labels, level-to-code mapping, reference level and missing-value treatment with the fitted design. Do not independently recode train/prediction or cross-language data and assume equal integer codes denote equal categories. Handle an unseen level under the adopted prediction rule; never silently assign it the reference category. Numeric category codes do not imply a cardinal scale or ordered spacing.

For date alignment, distinguish information available at a decision from an event's response window and a fiscal-period lag. Select backward or forward matching, tolerance and tie treatment from that clock; preserve time zones, release times and trading-session boundaries when they determine availability. A date without a release time cannot establish after-close availability. Construct calendar or fiscal lags from their period keys when gaps make row shifts ambiguous. Check boundary dates and overlapping event windows where they change the sample.

For a wide/long reshape, define the identifier and within-record dimension keys, and map each value together with its status and units. Preserve the intended cell support: dropping missing-valued cells changes sample accounting, while expanding every combination can invent out-of-scope records. Use the documented observation universe to distinguish an unobserved in-scope cell from a structural non-observation. Resolve repeated cell keys under the existing duplicate/grain rules before widening; a pivot's aggregation option changes the calculation. Check the resulting keys and value/status mapping against the intended cells, as in the [reshape example](implementation.md#example-reshape-values-with-their-observation-status).

### Example: reshape values with their observation status

**Use when:** a sparse shop–month table feeds a wide exhibit and a long analysis input. Sales use the same toy currency and price base. The adopted coverage record puts A in scope for January–March and B in scope for February–March. A missing value in a delivered row means the amount was not reported; an absent in-scope row means no record was delivered. The requested analysis input retains all in-scope shop–months for sample accounting.

A's delivered records are January sales `0`, February sales explicitly missing, and March sales `6`. B has only a March record, with sales `10`. B–February is in scope but absent; B–January is outside coverage.

**Operation trace:** establish keys `A–Jan, A–Feb, A–Mar, B–Feb, B–Mar` from coverage, then attach the four delivered records. Retain source presence and value status: A–February has a delivered record with an unknown amount; B–February has no delivered record. Both amounts remain missing. A rectangular exhibit may display B–January as outside coverage. On returning paired value/status fields to long form, recover the five in-scope keys: three observed amounts, one delivered missing amount, and one absent record. The observed zero belongs to the three observed amounts.

**Decision criterion:** dropping every missing numeric value leaves three rows and erases the two in-scope nonresponse states. Treating every display cell as an observation produces six rows and adds an out-of-scope combination. Preserve the five requested keys and their paired values/statuses; keep both missing amounts missing. Compare semantic shop–month keys rather than column position or row count alone. A subsequent complete-case analysis may select the three observed cells under its adopted rule; perform that selection explicitly after reshaping.

## Computation

Run relational joins, filters and aggregations in the existing query or vectorized engine; use iteration for a genuine sequential dependency or unsupported operation. Push selection, projection and valid aggregation toward the source before collection. A path such as `INSERT … SELECT` must specify sample selection, columns and options. Materialize the fields and rows the next operation needs. Use a whole-frame calculation when its peak working set fits the available budget; account for joins, sorting, design matrices, copies, conversion and writer buffers rather than stored file size alone. Choose chunking, streaming or an out-of-core engine when that budget would be exceeded, and preserve cross-chunk groups and sequential state. Carry the resulting object through the requested calculation or exhibit.

For file-based lazy work, start with a scan that permits pushdown. When a memory bound matters, inspect the plan for unsupported streaming operators, growing aggregation state and in-memory fallbacks; use a supported sink when collecting the final result would exceed the budget. Check partition schemas before combining them. Use distributed execution when the existing runner requires it or measured resource needs exceed a suitable single-machine path, accounting for transfer and coordination costs.

When a result combines heterogeneous weights, probabilities or nonlinear transformations, compute the defined object at its relevant unit before aggregating. Preserve the joint distribution needed by products and ratios.

### Estimator, engine and algorithm selection

Take the adopted target, identifying assumptions, outcome scale and sample from [the estimand-to-method sequence](../../econ-design/references/designs.md#choose-the-estimand-and-method). Select the specialist function that estimates that object with the required fixed effects, instruments, treatment history, weights and inference. Read its current official interface and method reference; inspect source when the interface leaves a consequential behavior unresolved. Confirm the installed version and signature before coding the call. A package name, an estimator label or a similarly named option does not establish that the requested combination is implemented.

Use the following branches to find the eligible implementation. The listed functions are candidates tied to economic objects, not defaults that override the design.

| Required object | Specialist implementations to inspect | Choices that must match the actual call |
| --- | --- | --- |
| Linear projection, additive fixed effects, linear IV | R `fixest::feols`; Python `pyfixest.feols`; Julia `FixedEffectModels.reg` | Within variation, endogenous regressors and excluded instruments, absorbed effects, singleton/rank handling, weight type, covariance and small-sample convention. |
| Exponential conditional mean with nonnegative outcomes | R `fixest::fepois`; Python `pyfixest.fepois`; Stata `ppmlhdfe` | Exposure or offset, fixed effects, separation and omitted observations, convergence, supported weights and cluster covariance. Zeros alone do not require a different model. |
| A specified negative-binomial likelihood | R `MASS::glm.nb`; Python `statsmodels` negative binomial | NB1/NB2 or other adopted variance law, estimated dispersion versus a fixed GLM dispersion parameter, link, exposure and treatment of individual heterogeneity. Adding group indicators is an unconditional likelihood specification. |
| Two-period ATT under conditional parallel trends | R `DRDID`: the corresponding panel or repeated-cross-section OR, IPW or DR function | Sampling structure, chosen score, covariates and constant, normalized sampling weights, overlap/trimming, nuisance estimation and valid influence-function or resampling inference. |
| Group-time ATT with staggered absorbing adoption | R `did::att_gt` and `aggte` | Cohort coding, comparison group, anticipation, panel versus repeated cross section, unbalanced-panel handling, covariate timing, weights, clusters and aggregation population. |
| Effects of changing treatment paths or doses | R/Stata `did_multiplegt_dyn` | Baseline treatment, switcher/control eligibility, observed paths and horizons, normalized versus non-normalized effects, restrictions for continuous treatment and cluster inference. |
| Local discontinuity or fuzzy-RD effect | R/Python/Stata `rdrobust` | Cutoff, sharp/fuzzy/kink design, bandwidth, polynomial order, kernel, bias correction, mass points and dependence. Extract the point estimate and interval belonging to the adopted inferential procedure. |
| Linear IV or specified moment restrictions | R `ivreg` or `gmm`, or the matching FE-IV branch above | Instrument-to-regressor mapping, moment conditions, weighting matrix and dependence. Conventional 2SLS output does not supply weak-instrument-robust inference automatically. |
| A treated trajectory or treated-block average | R `Synth` or `synthdid` | Donor eligibility, pre-treatment fit, treatment timing, target aggregation and suitable inference. The documented `synthdid` matrix interface requires a common treatment block. |
| An orthogonal-score treatment parameter | R/Python `DoubleML` | PLR, IRM, PLIV or IIVM model and score; ATE versus ATT/LATE where supported; learners, sample splitting, independent units and supported clustering. |
| Conditional treatment effects or their target-population aggregate | R `grf::causal_forest` | Binary versus continuous treatment target, overlap, honesty, nuisance fits, cluster/sample weights, averaging population and separate policy evaluation. |
| Differentiated-product demand, supply and equilibrium counterfactuals | Python `pyblp.Problem.solve` and documented result methods | Market/product definitions, shares and outside option, demand/supply instruments, integration, GMM weighting, cost specification, ownership and counterfactual equilibrium. |
| A dynamic structural parameter or policy value | The model's official replication implementation with established optimization, integration and linear-algebra libraries | States, actions, transition law, normalizations, discounting, equilibrium selection, likelihood or moments, solution residuals and simulation accuracy. |

Rank eligible implementations by agreement with the theoretical estimator, support for the complete specification, method paper and author implementation or replication evidence, maintained source, numerical behavior, and the existing language/data environment. Compare runtime and memory only where they can change feasibility or completion cost. The CRAN Econometrics Task View helps locate candidates; adoption requires the actual interface and estimator reference. Inspect the selected implementation's current license, dependencies and release metadata. Install only what the chosen analysis needs. Use an already available authorized Stata runtime when appropriate; do not obtain a paid engine to avoid an available suitable implementation.

Call the selected package directly from the existing analysis entry point. For example, an adopted level model with unit and year effects and state-clustered inference can use `fit <- fixest::feols(y ~ treatment + x | id + year, data = d, vcov = ~state)` after constructing its specified sample. An adopted exponential conditional-mean model can use the corresponding `fepois` call; changing that function changes the model and requires the corresponding design choice. Keep the fitted object and its sample mapping for the requested contrasts rather than reconstructing coefficients, covariance or marginal effects independently.

Match nuisance specifications as carefully as the final regression. `DRDID::drdid_panel` uses one supplied covariate matrix in both propensity and outcome nuisance models, expects a supplied intercept, and exposes a control-group trimming threshold. A requirement for different nuisance covariate sets needs an implementation that supports the chosen score and its inference. `did::att_gt` uses different covariate timing in its balanced-panel and unbalanced/repeated-cross-section paths; select the path deliberately and use the adopted group-time aggregation. Ordinary individual-level standard errors do not become clustered by supplying a cluster column elsewhere in the data. Use a documented procedure that carries the independent sampling unit into the chosen score or resampling calculation.

Resolve an unsupported option by selecting another implementation that satisfies the same adopted target and inference. If none does, identify the specific missing feature and compare a minimal extension using existing fits, influence functions or solvers with a design change under the authority already granted. A fixed specification remains fixed until the required change is authorized. Failed fitting, unavailable covariance or unsupported prediction cannot become an empty result, a stale estimate or a different estimator reported as success.

Execute the fit, extract named estimates and the requested economic contrast using the package's documented post-estimation methods. Use an established contrast implementation such as `marginaleffects` when it supports the fitted model and required covariance. Save the actual sample, effective options, package version, convergence result, estimates and needed inference in the existing [result lifecycle](reproducible-workflow.md#carry-analysis-results-into-tables-figures-and-prose). Produce the requested table, figure or action comparison from those saved quantities. A completed package survey, successful import or optimizer return establishes only its own stage.

For a counterfactual, check which supplied inputs each result method changes and which defaults reuse baseline values. In `PyBLP`, `compute_approximate_prices` fixes baseline shares and price derivatives; `compute_prices` solves equilibrium prices. Under adopted constant marginal costs, recover baseline `costs = result.compute_costs()`, obtain `prices = result.compute_prices(firm_ids=new_firms, costs=costs)`, then `shares = result.compute_shares(prices=prices)` and `profits = result.compute_profits(prices=prices, shares=shares, costs=costs)`. Supplying only new prices to `compute_profits` retains old shares. Multiply population-normalized profits by the corresponding market size and include the specified fixed and transaction costs in the action comparison. A model with quantity-dependent costs or changed choice sets uses the corresponding simulation and updated cost calculation. Reuse the valid demand fit when only the intervention changes.

Before switching a backend or representation, match the complete estimator contract above. Choose among eligible algorithms using the design's sparsity, fixed-effect structure, conditioning, precision and convergence requirements. When a backend adapts options, retain the effective algorithm, precision, device, stopping rule and consequential fallback in the existing run record. Compare those effective settings before attributing changed numerical results or runtime to the backend. A balanced-panel shortcut does not establish equivalence for an unbalanced panel.

When repeated design rows suggest compression, establish sufficient statistics for both the estimator and its requested inference before discarding rows. Preserve the identical sample, complete encoded design, weight domain, cluster identity and required moments. Coefficient equality alone does not establish covariance, degrees-of-freedom, prediction or resampling equality; a squared grouped score generally differs from a sum of squared individual scores. Do not discretize regressors to obtain compression without an authorized specification change. Distinguish exact aggregation from an approximate optimizer and retain its convergence criterion.

For resampling with replacement, preserve each sampled unit's multiplicity; set membership loses repeated draws. A cluster draw must carry its repetitions through joins and weighted moments, with draw-specific identities where the calculation requires separate copies. Uniform sampling of unequal compressed cells is not an individual-row bootstrap. Check the compressed operation against explicit replication of a small draw containing repeated and nonconsecutive identifiers.

Keep frequency, analytic, probability and iterative working weights distinct. Compute weighted means or losses with their defined weight total and normalization; do not replace that total with row count. Retain the fitted row identities, exclusions, column order and encoding needed by post-estimation rather than reconstructing a different sample from raw data.

For parallel replications, fits or partitions, bound workers by their working memory as well as CPU availability and avoid nested worker/thread-pool oversubscription. Give tasks stable identities, reproducible independent random streams and the result ordering the consumer requires. Preserve each task's stream when workers, scheduling or retries change: a failed subset must recover its original streams rather than reseed a shortened task list. A deliberately new draw needs a new task identity. Use the existing library's supported stream mechanism and retain the generator and task-to-stream mapping with the run inputs. Surface failed tasks before combining results. For in-place updates, establish object ownership; copy deliberately when a caller still needs the original state.

### Functions, types and failure boundaries

Locate the function, module and callers that own the required behavior. Search for an existing implementation and the standard-library or installed-package operation before writing parsing, formatting, validation, retry or data-shaping logic. Extend that owner and use supported package interfaces. Keep changes tied to the requested behavior and its consumers.

Implement the current requirement with direct control flow and explicit inputs and returns. Use clear `if` branches, descriptive names and intermediate values when they expose a calculation. Keep cohesive logic together. Avoid one-use wrappers, speculative configuration, service layers and fragmented files; dense expressions and nested conditionals also reduce readability. Match the project's conventions. Comments explain an economic or implementation decision whose reason the code does not show.

Name quantities by economic role and computational state: raw, within-transformed, solver-weighted or working response. Expose choices that alter the result as parameters. Use a shared type when its shape, units or option set defines a real interface. Isolate acquisition and writes from substantive calculations when their effects or execution order obscure the result.

Extract shared logic when real consumers implement the same rule and must change together. A substantive named calculation can also justify extraction when its units, denominator or independent use become clearer. Keep a transparent one-use expression local. Return one scalar for one quantity, or a simple named record for related outputs that travel together; the [named-totals example](implementation.md#example-name-a-calculation-and-its-related-totals) shows this choice. Introduce an abstraction only when its necessary responsibility and concrete callers are established.

Validate external inputs at the boundary that first establishes their contract: source types and units, required configuration, supported public options, authentication, authorization, ownership and persistence. Parse documented representations once, then let internal calculations use the established contract. Validate again where a transformation changes the relevant property or an independently exposed entry point receives external input. Remove repeated null checks and coercions that reproduce an established invariant. Preserve required cleanup, transactions, concurrency controls, timeouts and boundary validation.

Trace a failed operation to the first incorrect state and repair that owner. Catch an error where the code can perform the defined recovery, add actionable input context or clean up a resource; propagate it otherwise. Use bounded retries for documented recoverable failures. Add defaults, fallbacks or compatibility branches only for a current interface or task requirement with an identifiable trigger and outcome. Keep authentication, authoritative-storage and invariant failures explicit. Empty results, synthetic values and stale estimates cannot substitute for a failed requested calculation.

When a contract changes, update its producers, consumers, imports, fixtures and affected tests together. Remove superseded internal shapes, dead helpers and duplicate branches. Retain support required by persisted user data, active external consumers or a supported public format at the boundary that owns it. Do not preserve draft shapes through new aliases or rejection-only guards. Remove obsolete tests and task-created probes with the implementation they served; retain each required behavior in its canonical owner.

## Measured performance and memory

Use this branch when measured runtime or memory identifies a problem on the requested path. Locate the bottleneck before adding native code or parallel workers. First remove redundant work, unnecessary transfers and unsuitable algorithms. Compare eligible alternatives on representative end-to-end work, including conversion, startup and peak memory. Use native code for a demonstrated hot operation that existing bulk primitives cannot handle adequately; retain a readable reference where feasible. Parallelize independent work only when its savings exceed scheduling and data-copy costs and its outputs have separate owners.

Use [Computation](implementation.md#computation) for source-side selection and aggregation, working-set budgeting, scans, collection and streaming. Use [Estimator, engine and algorithm selection](implementation.md#estimator-engine-and-algorithm-selection) when the proposed change affects the estimator, compression, resampling or parallel execution. Preserve the adopted calculation and rebuild only its affected dependencies.

## Compare changed calculations

Use [CORE](../../../runtime/CORE.md#completion-and-reporting) and [Compare changed outputs](../../../runtime/EXECUTION.md#compare-changed-outputs) to select the smallest sufficient verification for the affected behavior. Reuse existing coverage and direct execution evidence. Inspect the real entry point and resulting persisted state when the change affects wiring, routing, serialization or writes. For calculations, use the numerical and sample comparisons below.

Use a derived identity or analytic case, explicit raw-row calculation, or specified reference implementation under the adopted specification. Match sample IDs, keys, encodings and coefficient names exactly. Define separate tolerances for estimates and inference quantities from their numerical or simulation error. Finiteness, symmetry, a successful exit and agreement with the old version do not alone establish that the calculation implements the defined estimator and inference. For a port or engine change, establish matching sample construction and missingness before comparing named estimates and inference.

Derive expected results from the adopted formula, observable contract or independent calculation. Avoid tests that copy implementation tables, assert private call order or pin incidental wording. Use a focused controlled case for a material race, retry or partial-write condition that the normal path does not exercise. Reuse fixtures and place durable coverage in the existing suite at the layer that owns the behavior. Keep multiple layers only when each demonstrates a distinct failure mechanism.

Retain a new test when it protects an important behavior absent from existing coverage and recurring detection justifies its maintenance. Merge a useful task-created probe into the canonical test; remove diagnostic-only residue. For authorized suite consolidation, preserve each unique contract assertion in a named surviving test and remove its obsolete test-only wrappers. Test count, coverage percentage and file count are never generation or deletion quotas.

When a check fails, compare its expectation with the adopted contract and identify the responsible implementation, test or environment. Repair that source and repeat the affected check. Preserve required outputs and independent numerical expectations. Regeneration and reporting follow EXECUTION; an additional audit report or test runner requires its own necessary function.

## Prediction

Define the target, prediction time and information available then. Choose a split representing the requested use: hold out future observations for future prediction, or hold out groups when predicting for new groups. Keep observations sharing information together when separation would leak information across that split. Fit preprocessing on training data. Evaluate the target level or change in the intended population and period using the requested loss or decision objective. Keep post-outcome information outside inputs; assess probability calibration when requested. Return predictions or performance with the target and split.

## Numerical methods

For non-executed learning code with inputs stipulated by the problem, state that domain and implement the formula directly. Present the correspondence between the solution and the code without an execution-status preface, footnote or postscript. Add runtime input validation or a test harness only when requested.

Use finite enumeration to construct the requested distribution or finite example; reuse an analytic proof that establishes the requested general claim.

Implement a derived closed-form calculation with the project's existing libraries or the standard library; add a symbolic or numerical solver when the requested calculation requires it.

Define the target, parameters, seeds and convergence criterion. Compare the result with the original equations or an analytic special case. Compute the requested simulation summaries from the adopted draws and retain their generating settings with the result.

For linear estimation, inspect the matrix actually solved: applying least squares to cross-product normal equations does not undo their conditioning loss. Prefer a direct factorization of the original weighted design when conditioning threatens the required precision and its memory and runtime fit the resource budget; otherwise choose a feasible method that meets those requirements rather than changing the target. Preserve the adopted rank and dropped-term convention, and check the inference calculation: rank handling in the coefficient solve does not establish that a later covariance inverse is valid.

For iterative solves, distinguish an iteration limit or a small stabilized step from satisfaction of the original score, residual or feasibility criterion. With clipping, damping or regularization, substitute the returned candidate into the intended equations, compare residuals and constraint violations with the adopted tolerances, and retain the termination reason; a fallback that changes the target requires a specification decision under CORE: choose only within delegated scope and obtain missing authority before changing a fixed target.

For a relaxed numerical problem, check the candidate solution against the original constraints, including incentive constraints along induced continuation paths where applicable.

When forming a positive sum or ratio of exponentials, subtract the largest log term before exponentiating and restore or cancel that scale in the result; use expm1 and log1p for exp(x) − 1 and log(1 + z).

Evaluate composed objectives and residuals directly in a stable representation when separately materialized intermediate values overflow or underflow.

Example: log(exp(a) + exp(b)) = h + log1p(exp(l − h)), where h = max(a, b) and l = min(a, b).

## Replication

Use [reproducible execution](reproducible-workflow.md) for exhibit tracing, comparison and discrepancy repair. Apply the journal's requirements to a requested submission.

## Worked data examples

Read the matching complete example when its sample, join, collection or resampling decision needs a concrete model. All records, paths, dates and values below are fictional; use the current task’s adopted inputs and definitions.

### Example: one sample for counts and moments

Use when the adopted analysis requires complete observations on both outcome and regressor. Fictional contract: one row per shop in one survey wave; `shop_id` is unique and nonmissing; `y` is weekly sales in toy currency units, `x` is opening hours. `eligible` is a nonmissing Boolean. Numeric values are finite or SQL `NULL`; zero is observed, and `NULL` means missing. Apply the adopted complete-case deletion rule. Dialect: DuckDB SQL.

```sql
WITH raw(shop_id, eligible, y, x) AS (
    VALUES ('S1', TRUE, 0, 2), ('S2', TRUE, 6, 4),
           ('S3', TRUE, NULL, 8), ('S4', TRUE, 10, NULL),
           ('S5', FALSE, 12, 6)
), analysis_sample AS (
    SELECT shop_id, y, x
    FROM raw
    WHERE eligible AND y IS NOT NULL AND x IS NOT NULL
)
SELECT COUNT(*) AS n, SUM(y) AS total_y,
       AVG(y) AS mean_y, AVG(x) AS mean_x
FROM analysis_sample;
```

Expected: retained IDs `S1, S2`; one summary row `(n=2, total_y=6, mean_y=3, mean_x=3)`. Both means use the same two observations. A model consumer should take `shop_id, y, x` from this same sample definition, retaining row identities rather than independently dropping missing values. A CTE lasts for this query; use the project's shared sample-building function or named relation when separate consumers need it.

Change the choice when the adopted design requires imputation, a different eligible population, additional model fields, or special treatment of suppression/censoring. Duplicate keys require resolving the observation grain, not an arbitrary deduplication.

### Example: reduce in the query engine before collecting

Use when the next exhibit needs only monthly summaries. Fictional input `toy_shop_months.parquet` has unique `(shop_id, year, month)` keys; `year` and `month` are nonmissing integers, with month in 1–12. Other fields follow the previous contract. For the worked case it contains exactly the previous five rows, all in January 2042. Dialect: DuckDB SQL.

```sql
SELECT month, COUNT(*) AS n, SUM(y) AS total_y, AVG(y) AS mean_y
FROM read_parquet('toy_shop_months.parquet')
WHERE year = 2042
  AND eligible AND y IS NOT NULL AND x IS NOT NULL
GROUP BY month
ORDER BY month;
```

Expected: `(month=1, n=2, total_y=6, mean_y=3)`. Collect this result for the monthly exhibit, at most 12 rows under the contract, instead of collecting the shop-level file first. Filtering and required-column selection can be pushed into the Parquet reader; aggregation stays in DuckDB before the result crosses into the caller. This bounds result size, not the engine's entire working set. Before an authorized production run, inspect `EXPLAIN` for scan columns and filters if pushdown is material to the memory or runtime decision.

Change the choice when the next operation needs shop-level records, a join changes the grain, or grouping cardinality grows beyond the collection budget. Months with no eligible observations are absent; add an explicit calendar join if the exhibit requires all months, without automatically turning an undefined mean into zero.

### Example: preserve repeated cluster draws

Use when checking additive moments for a cluster bootstrap draw with replacement. Fictional contract: `raw` has one row per nonmissing unique `obs_id`; every row belongs to one nonmissing cluster and has finite observed `y`. `draw_id` identifies each sampled cluster copy. The supplied draw selects `C7` twice and `C91` once. Dialect: DuckDB SQL.

```sql
WITH raw(obs_id, cluster_id, y) AS (
    VALUES (1, 'C7', 2), (2, 'C7', 4), (3, 'C91', 9)
), draws(draw_id, cluster_id) AS (
    VALUES (1, 'C7'), (2, 'C91'), (3, 'C7')
), multiplicity AS (
    SELECT cluster_id, COUNT(*) AS copies
    FROM draws GROUP BY cluster_id
), moments AS (
    SELECT cluster_id, COUNT(*) AS n, SUM(y) AS total_y
    FROM raw GROUP BY cluster_id
)
SELECT 'compressed' AS method,
       SUM(m.copies * s.n) AS n,
       SUM(m.copies * s.total_y) AS total_y
FROM multiplicity AS m JOIN moments AS s USING (cluster_id)
UNION ALL
SELECT 'explicit_copies', COUNT(*), SUM(r.y)
FROM draws AS d JOIN raw AS r USING (cluster_id);
```

Expected: both result rows have `n=5` and `total_y=21`: twice the two `C7` observations plus the one `C91` observation gives `2×2+1=5` and `2×(2+4)+9=21`. Filtering with set membership would instead give `n=3, total_y=15`, losing the repeated draw.

Change the representation when fitting requires covariate-specific moments or nonadditive statistics. Preserve the full required design and sufficient moments; these two totals alone do not establish estimator or covariance equivalence. If the downstream calculation distinguishes sampled cluster copies, retain `draw_id` as the new cluster identity and `(draw_id, obs_id)` as the copied-row key rather than merging all copies under the original cluster label.

### Example: match information available at the decision

Use when each decision needs the latest signal already available to that decision-maker. Fictional contract: unique nonmissing `decision_id`; nonmissing firm and timestamps; unique `(firm_id, released_at)` releases with finite signal values. Times below are invented UTC-normalized timestamps stored consistently as `TIMESTAMP`. `released_at` means actual availability, with no additional delivery lag. An equal-time release is usable; there are no tied releases per firm. Dialect: DuckDB SQL.

```sql
WITH decisions(decision_id, firm_id, decision_at) AS (
    VALUES (1, 'Fable', TIMESTAMP '2042-06-03 10:00:00'),
           (2, 'Fable', TIMESTAMP '2042-06-03 12:00:00')
), releases(firm_id, released_at, signal) AS (
    VALUES ('Fable', TIMESTAMP '2042-06-03 09:00:00', 5),
           ('Fable', TIMESTAMP '2042-06-03 11:00:00', 8)
)
SELECT d.decision_id, r.released_at, r.signal
FROM decisions AS d
ASOF LEFT JOIN releases AS r
  ON d.firm_id = r.firm_id AND d.decision_at >= r.released_at
ORDER BY d.decision_id;
```

Expected: decision 1 matches the 09:00 release and signal `5`; decision 2 matches the 11:00 release and signal `8`. A decision before the first release remains present with unmatched fields `NULL`. Change `>=` to `>` if simultaneous releases are excluded; resolve source/version ties and delivery delays before matching, and impose an age limit if stale signals are inadmissible.

A next-session event-response window requires a separate trading-calendar mapping: choose the first eligible session after the event under the study's intraday/after-close rule. That forward session search answers a different question from this backward information-availability match; a calendar date alone cannot settle the release's session.

### Example: diagnose join multiplicity before attaching values

Use when a lookup should attach at most one district to each establishment. Fictional contract: `establishments` contains unique nonmissing string IDs; the lookup's IDs and district labels are nonmissing. Labels are categorical, and leading zeros belong to the source identifier format. The diagnostic deliberately includes an exact duplicate, a conflicting assignment, a missing match and a valid match. Dialect: DuckDB SQL.

```sql
WITH establishments(establishment_id) AS (
    VALUES ('001'), ('002'), ('003'), ('004')
), district_lookup(establishment_id, district) AS (
    VALUES ('001', 'North'), ('001', 'North'),
           ('002', 'East'), ('002', 'West'), ('004', 'South')
)
SELECT e.establishment_id,
       COUNT(d.establishment_id) AS matching_rows,
       COUNT(DISTINCT d.district) AS distinct_districts
FROM establishments AS e
LEFT JOIN district_lookup AS d
  ON e.establishment_id = d.establishment_id
GROUP BY e.establishment_id
ORDER BY e.establishment_id;
```

Expected `(establishment_id, matching_rows, distinct_districts)`: `('001', 2, 1)`, `('002', 2, 2)`, `('003', 0, 0)`, `('004', 1, 1)`. Count the right-side nonmissing key, not `COUNT(*)`, because the unmatched left row still appears once. An uncorrected attachment would produce six rows for four establishments.

For `001`, establish that repeated ingestion caused the identical lookup rows before removing a duplicate; identical displayed values alone would not prove duplication in a richer source. For `002`, reconcile the conflicting district or introduce the omitted period/subunit key if that explains it. For `003`, repair a missing source record when one should exist, or retain an unknown district if the design allows it. `004` can attach directly. Once the lookup relationship is resolved, the left-population attachment should retain exactly these four IDs and one row per ID; all four need known districts only if the downstream calculation requires that coverage. If establishments genuinely span districts, change to the adopted establishment–district grain and allocation rule instead of forcing this many-to-one contract.

### Example: name a calculation and its related totals

Use when several program comparisons share the same adopted benefit calculation and the exhibit needs its components as well as the net total. Fictional contract: incremental benefit is a constant amount per participating household; `households` is a nonnegative integer, and benefit and resource cost are finite nonnegative amounts in the same currency and price year. All totals fit the chosen floating-point representation. Cost is already the program's total incremental real resource cost, not cost per household. The calculation has no discounting, spillovers or distributional weights. These are stipulated inputs here; in an executed pipeline they would be established at the data boundary. Language: Python.

```python
from typing import NamedTuple

class ProgramTotals(NamedTuple):
    total_benefit: float
    total_resource_cost: float
    net_benefit: float

def program_totals(
    *, benefit_per_household: float, households: int,
    total_resource_cost: float,
) -> ProgramTotals:
    total_benefit = benefit_per_household * households
    return ProgramTotals(
        total_benefit=total_benefit,
        total_resource_cost=total_resource_cost,
        net_benefit=total_benefit - total_resource_cost,
    )

program_a = program_totals(
    benefit_per_household=12.0, households=100,
    total_resource_cost=900.0,
)
program_b = program_totals(
    benefit_per_household=8.0, households=200,
    total_resource_cost=1200.0,
)
```

Expected: program A has total benefit `1200.0`, resource cost `900.0` and net benefit `300.0`; program B has `1600.0`, `1200.0` and `400.0`. An exhibit can read `program_b.net_benefit` alongside its named components without relying on tuple positions. The function makes the shared population-total calculation explicit, and keyword-only inputs distinguish a per-household benefit from a total cost. The record groups the outputs; its annotations do not enforce units or valid inputs at runtime.

Change the formula when household benefits differ, timing requires discounting, or the adopted objective uses distributional weights; passing a convenient unweighted mean would not establish the required total. For a single local expression whose sole consumer needs net benefit, the multiplication and subtraction can remain inline without introducing this record.
