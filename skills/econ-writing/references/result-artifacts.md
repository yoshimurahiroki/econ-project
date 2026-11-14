# Generate artifacts from saved research results

Use to turn saved results into tables, figures, numerical text and slides: registration, display specifications, inference blocks, model-based displays and claim coverage.

Contents:

- [Artifact scope](#artifact-scope)
- [Save displays at analysis or registration](#save-displays-at-analysis-or-registration)
- [Browse compare and edit saved results](#browse-compare-and-edit-saved-results)
- [Source basis for reuse and provenance](#source-basis-for-reuse-and-provenance)
- [Default LaTeX family](#default-latex-family)
- [Adopt an artifact specification](#adopt-an-artifact-specification)
- [Claims, coverage and requested re-review](#claims-coverage-and-requested-re-review)
- [Interface: Save displays at analysis or registration](#interface-save-displays-at-analysis-or-registration)
- [Interface: Browse compare and edit saved results](#interface-browse-compare-and-edit-saved-results)
- [Interface: Default LaTeX family](#interface-default-latex-family)
- [Interface: Adopt an artifact specification](#interface-adopt-an-artifact-specification)
- [Interface: Claims, coverage and requested re-review](#interface-claims-coverage-and-requested-re-review)

## Artifact scope

Apply [WRITING](../../../runtime/WRITING.md) to every prose and visual choice. Existing technical interfaces and scientific results below remain in force.

For an analytical result used in a consequential economic claim, complete the economist's procedure's result interpretation at its existing research owner. Bind the saved report with `sources[].metadata.result_interpretation={"path":...,"sha256":...}` in this artifact specification. Registration checks its exact result and specification hashes, retains the judgment reference with the existing producer and carries it into Gallery links. An interpretation for different result bytes is rejected. Display edits retain numerical rows and existing prose; internal judgment fields remain internal. Reuse a matching adopted interpretation without another review cycle.

The artifact operations extend `harness/research_evidence.py` and generate a manifest for the existing `harness/research.py` DAG. The research owner adopts the result sources, displayed quantities, units, words, equations and code spans. The resulting registry retains each original result in full, including the covariance, inference reference, confidence-set structure and JSON nulls. Each input is identified by its project-relative path and SHA-256. Binding establishes these exact correspondences and returns `status:"bound"`. An actual substantive judgment can accompany a binding or be developed through the selected review; it is preserved with its supporting evidence.

## Save displays at analysis or registration

1. **Routed result → display metadata.** Save supported claims in `metadata.public_claims`; retain assumptions, restrictions, missingness, failures and notes in `metadata.internal`. Keep the complete scientific result and existing diagnostic fields at their original owner. Each public claim names its quantity with the population, period and units that define it and carries its numerical uncertainty; apply [WRITING](../../../runtime/WRITING.md) to its expression.
2. **Saved uncertainty → renderer.** `metadata.uncertainty` selects numerical cells by zero-based `row`, `columns`, `kind`, quantity `label` and `unit`. Use `se` or `p_value` with one column; p values use the dimensionless unit `"1"`. Use `confidence_interval` or `credible_interval` with two ordered endpoint columns and the saved fractional `level`. Example: `{"kind":"confidence_interval","row":0,"columns":["ci_low","ci_high"],"label":"Employment","unit":"pp","level":0.95}` renders `Employment: 95% CI [-1, 5] pp` from those saved cells. The renderer preserves signs and zeros and applies the saved column formats. Existing numerical rows and confidence-set displays retain their source definitions, including nulls, disconnected components and unbounded sets.
3. **Selected display → public artifact.** Gallery resolves those fields into `public_text` for HTML, Markdown, LaTeX, plots and meeting consumers. Selection retains scientific metadata and internal records for writing; public renderers use the explicit projection. Register metadata changes through the existing result-registration path and regenerate affected assets. Review titles, labels and claims against WRITING and the selected population, period, unit and result. Bind each claim and label to a read corresponding original and the saved cells, with only the necessary target-specific adjustments.

Public claims bind the complete saved display. A row-filtered selection emits its selected numerical uncertainty and retains the original claims internally; adopt a claim for the new selection through result registration. Gallery's returned `public_text` is the resolved read-only projection consumed by meeting formats. Edit the original registered item and select it again to update that projection.

The same `research-artifact-registry-v1` registry holds an `items` object keyed by stable display IDs. Save the rows needed by a table or plot when the analysis produces them. A saved source result can carry `display_items`, an array of the display records below, or `display:{kind,rows,metadata}` with nested saved blocks. Named additional blocks in `displays` retain separate pointwise/simultaneous or design-specific views. Normalization maps those blocks to the existing items; a source without display rows receives a named coefficient or statistic table. Register an existing saved registry to create one PNG per selected display, usable in previews and native Google Slides:



`--items analysis/display-items.json` selects an explicit array of display records supplied by the completed analysis. An existing item's `id` with display or metadata overrides reuses its saved rows and columns. Use `--no-render` to register the rows and settings with an empty asset list. Use repeated `--format` arguments to generate the required SVG, PNG, HTML, PDF or LaTeX files. Normalization and registration read saved quantities. Save the requested inference with the official producing function before registration.

Keep one canonical registry for a research result and its displays. `save_registry` stores common display definitions and producer information in `shared_metadata`; each item retains its `metadata_ref` and its distinct fields. Identical producer containers, including resolved options, use `source_fields` to reference their keys inside the same record's complete `source_result`. `load`, `gallery_registry` and the evidence reader restore the same public record and item values from those saved references. They preserve the original numerical results and require no source-data or estimator execution. Save display overrides and regenerate the formats used by the selected manuscript or meeting. Skill packages contain the reusable implementation and rules; each research project retains its own inputs and completed results.

Each item contains `id`, `title`, `kind`, `result_ids`, `columns`, `rows`, `metadata`, `display`, `interpretation`, `status`, `links` and `files`. `columns` is an array of `{key,label,unit}`. Each row contains scalar saved cells and its `result_id`; JSON null remains a missing cell and numeric zero remains zero. `files` is an array of project-relative display paths. Basic kinds are `descriptive`, `sample_composition`, `distribution`, `time_series`, `group_comparison`, `coefficient`, `event_study`, `robustness`, `alternative_specification`, `table` and `figure`.

A producer's `display` or named `displays` block can supply the same `columns` and `display` objects. Registration retains their labels, units, selected axes, series, facets and formats; for omitted presentation choices, select settings from the corresponding read original and save them rather than relying on unsourced defaults. For a structural result, save parameter and moment tables as `kind:"table"` and scenario outcomes as `kind:"structural"`. Give a row its `scenario`, `quantity`, `value` and `unit`. The interface accepts `display:{plot_type:"bar",x:"scenario",y:"value",facet:"quantity"}`; select a presentation only when it corresponds to a read original and preserves the saved scientific definitions and distinct units. Each panel prints its saved unit. The producer saves every requested aggregate, difference and welfare measure before registration. A confidence-set display keeps each parameter and result on its own row and each connected component on that parameter's row.

Save each descriptive summary at its analysis grain, with the relevant group, period or bin keys, usable counts, denominator, weights and measurement units. Preserve bin edges and interval closure for distributions, and the adopted convention for quantiles. Save coefficient and event-study estimates together with their already computed endpoints. The renderer selects and draws those cells.

`research_data.py describe` produces Table 1 (mean, SD, median, requested quantiles and usable counts), group balance, sample flow, trends and saved distribution coordinates through the [descriptive-result interface](../../econ-data/references/research-data.md#saved-descriptive-results). Distribution metadata names `distribution_type`: `histogram`, `density`, `ecdf` or `box`. Histograms save bin edges and counts; density and ECDF plots save coordinates; box plots save `ymin`, `lower`, `middle`, `upper`, `ymax` and outlier counts. Rendering reads those quantities as saved. An individual observation identity remains in the scientific result; display metadata keeps sample definitions, groups, periods and aggregate contributions.

Save a quantile-effect curve as `kind:"qte"` with numeric `quantile`, `estimate` and its computed `ci_low` / `ci_high` endpoints. Registration maps it to the existing line figure, whose renderer places the quantile on the horizontal axis and the outcome unit on the vertical axis. Select this presentation only when it corresponds to a read eligible original and preserves the saved definitions. A counterfactual CDF uses `kind:"distribution"`, `metadata.distribution_type:"ecdf"`, its outcome unit in `metadata.outcome_unit`, and a named `display.series` for each potential-outcome distribution. Preserve the producing estimand, target population, aggregation and pointwise or simultaneous inference.

Save a continuous-DID dose curve as `kind:"dose-response"` with `dose`, `estimate`, `se` and the official `ci_low` / `ci_high`. The existing line figure can use the saved dose unit horizontally and the target's unit vertically: outcome units for ATT(d), outcome units per dose unit for ACRT(d). Select this presentation only when it corresponds to a read eligible original and preserves the saved definitions. Event-time aggregates use the existing `event_study` display. Carry `target_parameter`, `dose_support`, `dose_est_method`, `dose_time_invariant`, `parallel_trends_type`, `dose_aggregation` and the adopted `dose_cohort_independence` with the cohort, comparison, population, period and inference definitions. Select the saved pointwise or simultaneous block and its actual critical value. The producing `contdid::ggcont_did()` output and serialized fit remain attached to the same result. Writing consumes the selected target, coordinates and definitions through `composition_context`.

For `distribution_effect`, select the saved probability display or `displays.percentage_points`. The latter contains the CDF contrast, standard error and interval endpoints multiplied by 100. The saved `threshold` and `threshold_unit` define the original outcome cutoff, while `unit`, `effect_scale` and `scale_factor` define the selected effect display. These fields and the display's scaled inference pass to gallery selection and Writing. Bind percentage-point prose to the saved `_pp` statistics; a probability value converts through the saved `_pp` statistic.

Saved regression blocks use `kind:"regression"` with `term`, `estimate`, `se`, `ci_low`, `ci_high` and `p_value`. The comparison table uses existing result IDs as model columns and retains saved counts, clusters, fixed effects, controls, sample policy, period, weights, estimator and units. A common-sample comparison names that adopted sample; model-specific samples retain their separate definitions. Event-study rows retain `event_time`, role and saved interval endpoints, including null endpoints at a reference period. Existing `diagnostics.group_time.cells` also projects directly to ATT(g,t) and cohort event displays; each saved cell keeps its value, endpoints, calendar time, event time, base and role. Individual sample IDs and weights stay in the original result. The saved `interval_type` / `ci_kind`, `confidence_level` and `reference_event_time` / `reference_time` travel into the display. RDD, IV, heterogeneity, sensitivity and counterfactual blocks use their producer's saved coordinates and named estimates through the same interface.

The renderer can place a coefficient and its labeled numerical standard error on separate rows. Select the presentation from a corresponding read original while retaining the saved numerical inference and scientific definitions. `show_se`, `show_ci` and `show_p` select saved numerical inference under WRITING. Apply WRITING to reported inference. Keep annotation and note fields in the saved metadata; presentations omit them. Existing `show_stars` fields remain readable for saved-specification compatibility; rendering omits significance stars and their legend. `model_column` and `outcome_column` identify saved model/outcome columns; `model_order`, `model_labels`, `term_order` and `term_labels` set their display. An optional `term_column` selects the saved semantic term column for table alignment; its values define `term_order` and table labels while the original `term` and statistic keys remain intact. Tables preserve the saved `panel`, or combine the selected `facet` with subgroup, group and period. For marginal effects, the producer saves the original variable and a panel identifying its contrast, response group and `by` values. Coefficient plots use the original `term` positions and their `term_labels`. `column_groups:[{label,models}]` groups columns; `panels:[{label,terms}]` groups coefficient rows; `statistic_rows:[{field,label}]` selects saved model metadata. `preset:"paper"|"meeting"`, `digits`, `table_number` and `latex_label` control presentation. Comparison retains each model's saved `formats` and fallback `digits` regardless of selection order. Formats bind to the original saved column, including `se` / `standard_error` / `std.error`, `p_value` / `pvalue` / `p.value`, and `ci_low` / `lower` / `conf.low` with their corresponding upper endpoints. Model metadata uses that model's column formats. The same returned `presentation` accompanies selected raw rows into Markdown and native Google Slides tables, so their coefficient and inference cells stay aligned.

Specialized `plot_type` values are `att_gt`, `cohort_event`, `parallel_trends`, `rdd`, `iv_first_stage`, `iv_reduced_form`, `iv_confidence_set`, `scm`, `scm_gap`, `scm_placebo`, `binned_scatter`, `smd`, `structural` and `geo`, alongside existing coefficient, event-study and distribution displays. Save points, line coordinates and interval endpoints separately with `component` and series/side keys. ATT(g,t) rows retain cohort, calendar time and effect; geographic rows retain a serialized GeoJSON geometry and its saved value. The `x`, `y`, `lower`, `upper`, `component`, `cohort`, `time`, `value`, `geometry` and `facet` display fields select saved columns. The scientific metadata owns reference periods, treatment times, cutoffs and bandwidths; those definitions stay fixed under presentation edits.

The producing analysis supplies each specialized display's coordinates and defining metadata:

| Display | Saved inputs and application conditions |
| --- | --- |
| DID and event studies | Event time, estimate, saved endpoints and reference/pre-treatment/post-treatment role; calendar time and cohort for ATT(g,t), and a cohort series for cohort-event plots. Retain base period, treatment timing/history, comparison group, sample, anticipation and aggregation weights. Keep pointwise and simultaneous intervals in separate named blocks with their actual level and family. |
| RDD | Numeric running-variable coordinates (`running`, `x`, `bin_mid` or `mean_x`), binned outcomes and their saved endpoints, and separate left/right fitted-curve rows. Retain cutoff, bin edges, side, plotting bandwidth and estimation bandwidth under their saved definitions. A coefficient-only RDD summary has no running-variable axis and registers as a table. |
| IV | Save first-stage and reduced-form outcomes, stage/result identity, instruments, sample and any plotted points or fitted coordinates. A confidence-set display retains each connected component's `lower`, `upper`, `lower_unbounded`, `upper_unbounded` and `set_type`; finite endpoints, empty sets and the real line keep their saved meanings. |
| Synthetic control | Time and separately identified observed, synthetic, gap and placebo series, with treatment time, donor definition, fit period and sample. The gap display consumes a saved difference; the producing analysis subtracts the series and fits the donor weights. |
| Structural results | Named fitted, baseline and counterfactual scenarios, saved grid/path coordinates, equilibrium points and requested welfare quantities. Retain scenario assumptions, parameter definitions, population and units; use separate axes or facets for different measurement units. |
| Geography | A saved region/location ID, serialized GeoJSON geometry and the corresponding value. The producing analysis owns the geographic-ID mapping and boundary version; the renderer draws the saved mapping without joining another geographic dataset. |

Axis and series selection choose existing saved columns. Binning, curve estimation, effect aggregation, confidence-set inversion, donor fitting and equilibrium solution remain with the producing analysis.

For presentation figures, inspect axis and legend text at the rendered slide size. Set `font_size` and the figure dimensions together to carry the 28 pt slide baseline into the exhibit. The existing `legend_location:"above"` option places series labels above the plotting area in up to three columns; select placement and wrapping by reference to the read original while keeping the saved exhibit visible.

### Draw the model's economic relationship

Use the adopted equations to select the relationship carrying the claim. Save its calculated coordinates through the existing result producer and display them with `kind:"structural"` and the existing line, scatter, area or structural plot. The manuscript and exhibit consume the same model, parameter values, scenario and units.

Select the economic relationship, coordinates, exhibit form and connection to the argument by mapping each choice to a read corresponding source and to the adopted equations and saved results. Preserve the source-to-output correspondence in the existing record.

Set `component:"equilibrium"` for optimum or equilibrium points and `display.point_label` to their saved label column. A `component:"region"` row uses `display.lower` and `display.upper` as its two economic boundaries. The renderer shades their saved coordinates; the producing calculation supplies the area and welfare quantity. These boundaries carry the region's economic meaning. Save statistical intervals in their own component.

A phase path uses `component:"path"` and `display.path_order` naming its numeric period or sequence column. The renderer joins rows in that order, preserving a trajectory whose state coordinate reverses direction. Budget lines, demand, supply, best responses and policy functions use the existing coordinate order for their curves. Separate panels retain separate units. The existing table and bar presentations support state-transition probabilities with origin and destination labels. Choose the presentation and labels from an exemplar of the same kind of display, keeping the saved probabilities and their definitions.

Labels, axes, captions and discussion follow [WRITING](../../../runtime/WRITING.md) and the paper's symbols, comparison and audience; the scientific definitions stay attached to the saved result.

At registration, `metadata` joins the saved result IDs to `producers` and `result_definitions`. Retain the actual producing run and specification IDs, code/specification/result references and hashes, engine and environment, sample and population, observation, assignment, analysis and inference units, treatment recipient, delivery actor, comparison, period, variables, measurement units, estimand, weights and saved inference settings. Use `observation_unit`, `assignment_unit`, `analysis_unit`, `inference_unit`, `treatment_recipient` and `delivery_actor` for those adopted roles. These fields pass through result comparison and `composition_context` to Writing. DID definitions retain treatment history, anticipation, cohort composition, aggregation weights, comparison groups and base period. Record the SE method, inference unit, clustering, degrees of freedom, interval type and level in `inference`. Producers retain the executed official function, effective options and saved-result format version. A source's optional `metadata` object supplies run, environment and economic definitions to the normalizer; an item's metadata supplies its shared display definitions. The selected input's provenance remains in the registry; fitted individual IDs stay in the scientific result. `status` records adoption, and `links.tasks` / `links.documents` connect the result to existing work and manuscripts.

An assembled analysis carries `variables` and `data_construction` from its hash-bound `data-record.json`. The selected definitions retain economic roles, original fields, timing, formulas, units, denominator, grain and common-sample accounting. Executed variable construction, computation, orthogonal-score, heterogeneity, policy and experimental-design definitions take precedence over source and display metadata. Use those saved definitions with the corresponding coefficient or contrast when explaining levels, rates, logs, growth, real amounts and treatment exposure. The fitted sample remains the official estimator's returned sample. Gallery selection and Writing consume the saved result without reopening source tables.

Carry the executed result's `inference` through registration, display selection and writing. A declaration such as `type:"official"` supplements that saved procedure, reference distribution and interval definition. For the same interval family and level, executed fields take precedence over declared fields. Select a separately saved display block for another family or level; existing endpoints keep their labels under a metadata override. Each selected block retains its own interval definition and rows.

Structural solvers can store complete paths inside `scenario`. Keep those calculated arrays in `source_result`; captions take their wording, under WRITING, from a corresponding read original and use the adopted scenario definition or its saved ID, name and description. Supply additional intervention definitions through the source or display `metadata`. This preserves the complete numerical result and gives each exhibit its economic comparison.

Model-based results carry `model_contract`, `knowledge_ids`, `equations`, `notation`, `parameter_roles`, `assumptions`, `normalization`, `equilibrium_selection`, `welfare_definition` and `horizon` in the same saved definitions. The producer's adopted definitions or the artifact specification's source `metadata` supplies those fields. `parameter_roles` identifies each estimated, calibrated or fixed parameter and its source and unit. Read these selected definitions with their saved quantities to compose the Model, Results and Discussion; match notation and defining conditions across the equation, table, figure and manuscript. The selected item's `source_reference` binds this context to its existing registry version. Knowledge IDs locate their registered derivations; the adopted model and saved result govern the paper's actual claim.

The executed result's `computation` travels through that same definition projection into tables, figures and `composition_context`. It records the performed estimation, solution, Jacobian or simulation operation, parameter treatment and numerical target. Its actual producer values take precedence over display metadata. Use these saved operations with `parameter_roles` and `welfare_definition`, borrowing the explanation from corresponding read originals with minimal target-specific adjustment, to explain the calculated object and reuse the same solution or fitted parameters in a subsequent passage.

Orthogonal-score results carry `orthogonal_score`: the executed score model, potential-outcome or contrast target, treatment levels, quantiles or tail definition, selection mechanism and sample-splitting roles. Forest results carry `heterogeneity`: treatment contrasts, instrument and compliance population, survival horizon and censoring conditions, aggregation and weights. Registration preserves these executed definitions in comparison and `composition_context`; they stay fixed under presentation metadata. The complete saved result retains fitted IDs, folds and native fits.

Policy results carry the adopted `policy` definition: treatment arms, baseline rule, value target, score, training and evaluation roles, costs and allocation constraints. Experimental results carry `experimental_design`: assignment mechanism, arms, probabilities, randomization unit, estimator, contrasts and diagnostic design. Keep observation IDs, fold membership, assignment vectors and score arrays in the complete source result. Gallery comparison compares these definitions, and Writing selects the corresponding saved values, costs, assignment rates, effects, power and interval endpoints through the same registry. A changed policy target or assignment design receives its own producing result.

When a manuscript inference uses a saved diagnostic, covariance block, model condition or evaluation definition outside the named statistics, select its exact JSON path with `research_results.evidence_paths` in the existing [writing brief](paragraph-workflow.md#command-entry-points). For example, `{"specialist-did-r01": [["diagnostics", "pretreatment_test"]]}` selects the original joint-test result. `composition_context` returns that value with its registry path, exact source-result keys and content hash alongside the same result's definitions and quantities. Select the additional saved paths needed to establish the null, tested contrasts, interval family or evaluation population. The writer uses the official method and adopted design to explain their inferential relation through [paper guidance](paper-workflow.md#w3-compose-section-by-section). The existing result record retains unselected diagnostics and observation-level arrays.

Read the [interface](result-artifacts.md#interface-save-displays-at-analysis-or-registration) for the exact input forms.

## Browse compare and edit saved results



`research_evidence.py gallery` and `research_artifacts.py gallery` expose the same commands. `show ID` returns one selected display and its `revision` for an edit; `preview ID --output PATH` renders saved rows to HTML. `render --item ID` saves a PNG generation from the selected item's rows; for a paper export, select `--format svg`, `--format pdf` or `--format tex` as needed. `list` supports `--kind`, `--status` and seven definition filters: `--result-id`, `--sample`, `--comparison`, `--outcome`, `--specification`, `--period` and `--adoption`. `compare` keeps the selected records together, returns the saved regression comparison and reports definition differences. A specialist's saved rows without an applicable x/y pair render as a table with their original columns.

The Python interface `gallery_items(root, gallery_spec_path, query="")` returns display records with `files: list[str]`, `columns: list[{key,label,unit}]` and `rows: list[dict]`. Its rows and columns reflect the saved display selection, while the registry keeps the complete saved rows. Each record's `source_reference` names the existing registry JSON path, item key and content version for the existing DAG. Search, comparison, preview and reporting read that saved content. They read saved results; raw data, producer code, source specifications and execution environments stay as recorded. The resulting record list is the meeting module's explicit selection input; only selected display assets, rows and metadata travel into a meeting bundle. Comparison returns definition differences for every selected result, including multiple results within one item. It classifies definitions as aligned, differing or missing required fields, and reports effects with the weights and aggregation as saved.

Pass `item_ids=[...]` to select exact displays in their requested order. CLI `select` and `compare` use that same path. Projection, table composition and manuscript handoff operate on those selected records; unselected displays remain stored for their own consumers.

Select and arrange main and supporting exhibits, tables, figures, Results and Discussion by mapping each content, argument and visual choice to corresponding read source passages and exhibits. Use the existing argument's claim/evidence IDs and `exhibits.node_ids` to connect that inference to saved item IDs and their `source_reference`. Preserve the selected estimates, sample/comparison definitions, model parameters, fit quantities, counterfactual outcomes and welfare measures as saved; keep the task's own conditions and conclusions. Record every source correspondence and necessary target-specific adjustment.

The local marimo app uses the project's existing Python environment with pinned `marimo` and `matplotlib`. It offers all seven definition filters, multiple result selection, preview, comparison, table headings/columns/order/notes, plot type, saved specification and series selection, series order and labels, axes/scales/ranges, colors, legend, title and dimensions. Paper and presentation styles set the figure text size; Noto Sans CJK JP supplies Japanese glyphs. Changes preview reactively; the save buttons persist an explicit edit. The app separately edits interpretation, findings, issues, adoption decisions/status and task/document links. It exports the selected display records as JSON for meetings while preserving the existing project, history, GitHub and meeting screens.

`edit_gallery_item(root, registry_path, item_id, changes, expected_revision=None)` classifies changes as display (`title`, `display`), interpretation (`interpretation`, `findings`, `issues`, `adoption_decision`, `status`, `links`) or scientific (`rows`, `metadata`, units, result identity or other definitions). The UI and `edit --expected-revision HASH` command bind edits to the current item's `state.content_hash`. Display edits preserve saved scientific rows and produce a complete new display generation. Interpretation edits preserve display assets. A scientific change goes through the existing adopted-specification and result-registration path. A saved view keeps the selected sample, estimator, denominator, bins and inference.

The returned `changed_references` identifies the edited fields with existing JSON references: `keys:["items",ITEM_ID,"display"]`, `rows`, `metadata`, `interpretation` or `files`. Bind consumers to the fields they actually use through the existing argument/task dependency graph. A figure uses its rows, columns and display; interpretation uses its saved result definitions. A label edit regenerates the selected display consumers, an interpretation edit reopens its text consumers, and an authorized specification change updates the corresponding scientific result and its actual descendants. Keep unrelated result IDs reusable. The gallery adds no task store, registry or approval stage.

### Find code, data, results and documents

Use the same Gallery entry to search the project's existing task outputs, consumed files, saved DAG generations, result registries and selected meeting bundles:



Repeat `--registry` or `--meeting` for additional existing owners. `--id`, `--kind`, `--question`, `--result-id`, `--sample`, `--comparison`, `--outcome`, `--specification`, `--period`, `--adoption` and `--status` narrow the recorded metadata. Search terms all match within the same artifact. The Python interface is `artifact_catalog(root, registry_paths=(), store=..., query=..., filters=..., task_ids=(), include_history=False, meeting_paths=())`. The workspace's **成果物を探す** tab uses this interface; the existing result tab continues to select saved exhibits for manuscripts and meetings.

Each returned item names its stable ID, path, format, producer role, recorded content version, run/task and exact source references. Scientific definitions and their versions remain beside their producing result; task dependencies, decisions and document links point to their existing owners. Identical file-path/content-version pairs share one search row with all recorded producers and consumers. A query reads only the selected state, registries and meeting records. It reads only the saved display registry and its displays. `file_present` reports file presence; the version is the producer's recorded hash. Use the selected owner's existing `show`, `select` or `resume` operation before consuming its values.

For each saved pipeline, profile, parent and stage, the default view selects its latest completed task record. `--history` also includes retained generations and earlier task-output snapshots. `latest_recorded` identifies that selection; an exhibit's saved adoption status identifies its scientific use. A search result preserves the original version even when the file has subsequently changed. A saved search selection is a view of these source records; the source owners retain updates and history.

Keep code at its module, source data at its project data path, derived data with its assembly specification and data record, calculations in their saved DAG generation, figures with their Gallery assets, writing at its manuscript source, and meetings in their bundle. Register newly produced code, data and documents through the existing task `output` operation; the research runner already registers its outputs and dependencies. Register figures through Gallery and select their saved records for the meeting or writing consumer. Update all producing and consuming references together for an authorized move. File discovery and layout changes reuse the saved scientific quantities.

Read the [interface](result-artifacts.md#interface-browse-compare-and-edit-saved-results) for the exact input forms.

## Source basis for reuse and provenance

The [AEA Data and Code Availability Policy, February 2026](https://www.aeaweb.org/journals/data/data-code-policy), requires a program-to-output-to-exhibit map and reproduction instructions with software, hardware and running-time requirements. These fields belong to the producing result and reproduction package. The gallery retains their saved identities for result reuse. The policy's data-access and deposit provisions govern a separately authorized replication deposit.

The [AEA Data Editor's preparation guidance](https://aeadataeditor.github.io/aea-de-guidance/preparing-for-data-deposit) connects data provenance, computational requirements, programs and expected outputs. Its “No manual modifications” section requires figures, tables and numerical text to be generated from code. Saved numerical rows and persistent display settings give the local editor that executable correspondence.

[TIER Protocol 4.0's Output folder](https://www.projecttier.org/tier-protocol/protocol-4-0/root/output/) preserves generated tables, figures and other reported results, with separate data-appendix and analysis outputs. The gallery's kinds and source links retain that distinction in the existing registry.

[showyourwork's dependency configuration](https://show-your.work/en/latest/config/#dependencies) declares the files used by each script and reruns the consuming workflow section when those dependencies change. ERS applies that dependency principle through its existing DAG and selected JSON references. It reuses saved estimates when display settings change.

The marimo documentation defines [reactive controls](https://docs.marimo.io/guides/interactivity/), [selectable tables](https://docs.marimo.io/api/inputs/table/), [explicit run buttons](https://docs.marimo.io/api/inputs/run_button/), [application arguments](https://docs.marimo.io/api/cli_args/) and [HTML export](https://docs.marimo.io/guides/exporting/). The local app uses those native controls for browsing, editing and explicit saves. Source versions above were read on 2026-11-05.

The [modelsummary extension interface](https://modelsummary.com/vignettes/modelsummary_extension.html) accepts saved tidy/glance model quantities. The existing analysis engines extract quantities from their supported fitted objects. [ggfixest](https://grantmcdermott.com/ggfixest/) supplies coefficient and event-study displays for supported fixest objects; its post-estimation calculations belong to the producing analysis. The gallery consumes the chosen endpoints and reference period already saved by that producer. Its display-only exports follow the same saved-data separation as the official [ggplot2 saving interface](https://ggplot2.tidyverse.org/reference/ggsave.html).

The renderer supports specialized layouts informed by the event-study and balance presentation examples in [EconAgentSkills](https://github.com/JonasWeinert/EconAgentSkills/tree/main/_skills/communication/econ-visualization), the event-study and RDD layouts in [SSCI-Plots](https://github.com/O0000-code/SSCI-Plots/blob/main/references/chart-types-causal-econ.md), and the model/series identities in [ggfixest's extraction code](https://github.com/grantmcdermott/ggfixest/blob/main/R/iplot_data.R). Select each actual layout and its visual elements by correspondence to a read eligible original in the source categories specified above; record the correspondence and necessary adjustments. The existing renderer supplies the display operations. The producing RDD analysis saves [rdplot's `vars_bins`, `vars_poly`, cutoff and bandwidth](https://github.com/rdpackages/rdrobust/blob/main/R/rdrobust/R/rdplot.R). Bin intervals and fitted curves keep their separate roles. Gallery browsing uses the saved displays as they are.

## Default LaTeX family

New paper and slide exports use the supplied [Econometrica paper](../../../tex/paper/ecta_template.tex) and [metropolis slides](../../../tex/slides/main.tex). The generator replaces each `%% BEGIN NAME` … `%% END NAME` region of the two templates (title, authors, support, abstract, keywords, body, bibliography) and keeps the preamble, so `python harness/research_artifacts.py generate-adapters --root .` rebuilds both adapters after a template edit; inspect corresponding real source pages and slides for all content and visual choices. Keep the paper's class, configuration and `ecta-fullname.bst` together. A citing direct document reads its project bibliography at `tex/bibliography.bib`; a missing requested bibliography remains a build error.

The existing artifact helper derives Pandoc adapters from those exact source templates:



The project Quarto defaults and new artifact LaTeX/PDF stages consume those adapters. The shared LuaLaTeX helper handles the journal class's fontspec initialization, citation-aware BibTeX passes, backreferences and previous-PDF restoration on a failed build. Template, package and build-helper versions enter the affected stage inputs, so a layout change rebuilds the corresponding artifacts while preserving matching estimates and their scientific definitions. Keep explicitly adopted document formats with their existing projects.

Read the [interface](result-artifacts.md#interface-default-latex-family) for the exact input forms.

## Adopt an artifact specification

Use the project's completed result files and existing authored article and slide sources. The artifact specification's `sources` list gives each distinct `id`, `result`, `code` and, where applicable, `specification` and `data`, all relative to the project root. A saved producer `spec_sha256`, `data_sha256`, `script_sha256` or `producer_sha256` must match the selected file. When a producer left a hash unrecorded, provide the owner's SHA-256 in `expected_hashes` for each selected code, specification or data input. That adopted hash pins the selected input. Preserve the actual source result and execution record when establishing that historical correspondence.

The normalizer registers every finite `{value,unit}` in `statistics`, names coefficients, standard errors, saved p values, saved interval limits and observation counts, and retains the complete source result. It preserves null entries in that source without converting them to zero. Generic saved intervals use `confidence_lower.TERM` and `confidence_upper.TERM`; explicitly saved 95% intervals retain `confidence_95_lower.TERM` and `confidence_95_upper.TERM`. Their level and inference definition remain attached to the saved result. For older coefficient results, supply `coefficient_units` mapping each parameter to its actual unit; no unit is inferred from a label. `quantities` can explicitly select additional finite source-result key paths and their adopted units. Stable keys are `<source-id>.<semantic-key>`.

The key paths in `sources[].quantities` and `research_results.evidence_paths` use nonempty strings for object keys and zero-based nonnegative integers for array positions. A `describe` mean can be selected by `["display","rows",0,"mean"]`; match that saved row's variable, group, period and unit before assigning its semantic statistic name. The saved result hash binds the array order. Boolean, negative and out-of-range indices are rejected. Registration and Writing retrieve the stored value without recomputing it.

Each `bindings` entry supplies a registry `key`, exact `unit`, numeric `format`, `display_unit` and human-readable `label`. Supported formats are `f`, `g`, `e`, or a precision such as `.3f`. A template statistic consists of two opening braces, `stat:name`, and two closing braces. The table and figure markers use the same brace pairs around `table` and `figure`. A value and its displayed unit are inserted together. The saved render trace links each occurrence to its statistic and source; rendering consumes those saved values directly. `figure` selects binding IDs sharing one unit.

Optional `definitions` bindings insert saved nonempty strings into both article and slide templates. A definition placeholder contains two opening braces, `definition:name`, and two closing braces. Each entry supplies a `key` array into the same registry. Select an adopted equation or comparison from `records.SOURCE.source_result`, or a selected item's economic definition from `items.ITEM.metadata.result_definitions.SOURCE`. Select a string leaf for an equation, notation entry, parameter role, comparison or inference description; arrays, objects and numerical values retain their own saved types. Definition text is inserted literally in one pass, including its Unicode, equations and braces. Numerical occurrences keep their correct evidence spans after insertion. The [native research renderer](../../../harness/research.md) accepts the same definition placeholder in section stages, with `stage`, `output` and `key` identifying the consumed saved output. Both paths retain the existing result dependencies and artifact formats.

A `models` entry names the `source`, exact article `equation`, exact `code_quote`, source-result `residual_key` and tolerance. Optional `parameters` name an exact manuscript target and code quote, a specification key and its unit, and a registered result statistic. Normalization retains these adopted mappings in the source record’s `metadata.model_mappings`, alongside the saved quantities and input references. Article and slide rendering consume the selected results without an independent audit stage. An optional `judgment` retains the owner's actual assessment of the equation-to-code correspondence and economic interpretation. Exact text matching establishes the selected passages.

For an adopted specification at `analysis/artifacts.json`, materialize and execute it with:



The generated stages normalize each selected result separately, merge their registry, render the table and SVG, generate article and slide sources with their saved-statistic traces, and export article HTML, LaTeX, PDF and Quarto HTML plus Beamer slide PDF. The article and slide sources are Quarto Markdown. Pandoc and Quarto execute as declared stages, and the Quarto output retains its executable version and hash. The PDF stages use a project-local LuaTeX cache. Wrapper stages declare their external commands in `executables`: Pandoc for LaTeX, Pandoc/LuaLaTeX/`pbibtex` for PDF, and Quarto for Quarto HTML. The runner resolves these commands in each stage environment and includes their executable hashes in reuse signatures.

Result, specification, data, code and template bytes enter the ordinary stage signatures. LaTeX wrapper stages include their consumed artifact specification, source template and Python helpers. Materialization validates both authored templates; article and slide rendering validate only their selected template. Normalization, registry merging, tables and figures consume the specification without reading manuscript bodies. A changed result rebuilds its registry fragment and descendants; a figure consuming a different source remains reusable. A changed code or specification hash fails its old source binding until the owner adopts the changed input and its corresponding result. The normalizer reads each selected saved result and producing file once per operation and retains the selected quantities with that pinned content. Run the manifest again after an authorized update; the existing research runner retains prior generations and rebuilds affected stages. When a changed result changes the adopted argument, search and read corresponding originals and update article or slide text by borrowing, imitation and minimal adjustment, recording the correspondence.

Read the [interface](result-artifacts.md#interface-adopt-an-artifact-specification) for the exact input forms.

## Claims, coverage and requested re-review

The same `research_evidence.py review CONTRACT --root PROJECT --output PACKET` selects registered claims and their original source passages. An anchor may name its evidential `role`, such as population, identification, assumption, result or counterevidence. A claim's `bindings` list refers to the existing `numbers`, `models` or `mappings` IDs; the packet supplies only those selected result values, producing inputs and code spans. `bind` checks their existing units, identities, formatted values, original equations and residuals. Multiple anchors and bindings establish their separate roles; the owner judges the resulting inference.

Select `coverage.claims:true` when the request requires automated claim-coverage inspection. `claim_coverage` then locates citation, quantitative, inference, causal and theoretical sentence candidates within `coverage.spans`, or the manuscript when no scope is selected. It returns exact Unicode character spans, detection signals and uncovered candidates. The substantive review judges the actual argument and the material claims outside those lexical signals. Selected coverage enforcement retains a supported `coverage.claim_judgment` using the existing reviewer/decision/rationale judgment. A specific nonmaterial candidate can have its exact `target` and reasoned `judgment` in `coverage.claim_accounts`. Numerical coverage scans only the explicitly selected `coverage.spans`; ordinary binding resolves its declared source and statistic references directly.

A requested review round adds a `review` object to the same contract. Its initial `criteria` are nonempty `{id,text}` rows. The owner's `assessment` has a `reviewer` and `findings`; each finding retains `id`, `claim_id`, `criterion_id`, `decision` (`supported`, `revision-required`, `unresolved` or `removed`), `rationale` and nonempty hash-pinned file `references`, with an optional exact `span`. Revised text has exact manuscript spans in `changes`. The resulting `reviewed` record means that the supplied evidence assessment covers its selected claims; its findings can still require repairs. It grants no certification or release authority.

Re-review points `review.previous` to the saved completed review's `{path,sha256}`. Initial criteria, adopted scientific identities and finding targets remain fixed. A changed criterion is rejected. Omitted initial findings are rejected when supplying the revised assessment. A removed finding requires the actual earlier claim to be absent from the new manuscript. The packet identifies `claims_to_reassess`, `reusable_claims` and removed claim IDs. Reused findings link their historical review through `reused_from`; current source/result context stays beside the current manuscript.

The manuscript's whole-file hash pins the delivered version. Each claim fingerprint instead binds its actual quoted claim, adopted identities, source editions/propositions and original locators, selected quantity and producing code/input identities. It excludes unrelated manuscript text and manuscript character offsets. A peripheral edit preserves those judgments; a changed selected claim, source edition or calculation input reopens its dependents. Register the selected fingerprint, decision and rationale as an existing state object output when continuation needs it, and let each writing or analysis task consume that output ID. Requeue the changed output through the existing state helper; preserve unrelated outputs and completed consumers.

Supply the author letter only through `review.author_response` together with `review.response_after`, a hash-pinned separately saved assessment of the current evidence. The command validates that assessment and its criteria before reading the letter, and returns `response-comparison-required` with unchanged evidence findings. Compare the letter's assertions with those findings. A new determining fact returns to the same evidence and assessment path and changes the verdict there. This selected file dependency controls the packet contents and runs in the existing reviewer Agent.

To generate a requested response from the completed revision, supply the current assessment with each finding's `changes` and `references`, then select `review.response_draft` through the same review entry point. It returns the original comment and passage, current revision, supporting evidence and response text. Use [econ-review's response contract](../../econ-review/references/review.md) for the language, finding selection and source correspondence.

Compose the finished response with the existing writing host after revising the actual manuscript and assessing its changed claims:



The host and rule files use the existing [paragraph callback interface](paragraph-workflow.md#command-entry-points). The task's operation is `econ-writing:compose`, `econ-writing:revise` or `econ-writing:translate`. Its payload carries the requested language, adopted scientific identities, selected original comments and passages, actual revised spans, assessment reasons, source text and saved quantities. The host returns `{"responses":{"FINDING_ID":"completed response text"}}` for exactly the selected findings. The same host observer binds that returned wording to its actual invocation. Borrow the response’s content selection, structure and wording from corresponding read originals and adjust only as necessary to explain the assessed revision, reasoning and location. The packet retains the full evidence correspondence and execution; the Markdown letter contains the comments and completed responses. Ordinary direct writing uses the same source-first borrowing, imitation, minimal adjustment and correspondence procedure and saves its finished text in the requested destination.

Read the [interface](result-artifacts.md#interface-claims-coverage-and-requested-re-review) for the exact input forms.

## Interface: Save displays at analysis or registration

```sh
python harness/research.py gallery register --root "$PROJECT" \
  --registry analysis/saved-results.json --output analysis/gallery.json
```

## Interface: Browse compare and edit saved results

```sh
python harness/research.py gallery list --root "$PROJECT" \
  --registry analysis/gallery.json --query "employment"
python harness/research.py gallery compare --root "$PROJECT" \
  --registry analysis/gallery.json main-event-study alternative-event-study
python harness/research.py gallery select --root "$PROJECT" \
  --registry analysis/gallery.json main-event-study sample-table \
  --output meetings/selected-results.json
python -m marimo run harness/research_gallery.py -- \
  --root "$PROJECT" --registry analysis/gallery.json
python harness/research.py gallery ui --root "$PROJECT" \
  --registry analysis/gallery.json --headless --port 2718
```

```sh
python harness/research.py gallery search --root "$PROJECT" \
  --registry analysis/gallery.json --meeting meetings/current --query "employment"
python harness/research.py gallery search --root "$PROJECT" --kind code
python harness/research.py gallery search --root "$PROJECT" \
  --store .agents/state/team.json --task RESEARCH_TASK --history
```

## Interface: Default LaTeX family

```sh
python harness/research_artifacts.py generate-adapters --root "$PROJECT"
```

## Interface: Adopt an artifact specification

```sh
python harness/research_evidence.py artifacts materialize \
  --root "$PROJECT" --spec "$PROJECT/analysis/artifacts.json" \
  --output "$PROJECT/analysis/artifact-manifest.json" \
  --python "$ANALYSIS_PYTHON" --pandoc "$PANDOC" --quarto "$QUARTO"
python harness/research.py --root "$PROJECT" analysis/artifact-manifest.json
```

## Interface: Claims, coverage and requested re-review

```sh
python harness/research_evidence.py review writing/current-contract.json \
  --root "$PROJECT" --output writing/current-review.json \
  --host writing/host-adapter.py --rules writing/rules.json \
  --request 'Compose the referee response from the assessed manuscript revision.' \
  --writing-mode compose --execution-kind single-agent-sequential \
  --author-id author --response-output writing/response.md
```
