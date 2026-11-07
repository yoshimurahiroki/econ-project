# Generate artifacts from saved research results

The artifact operations extend `harness/research_evidence.py` and generate a manifest for the existing `harness/research.py` DAG. The research owner adopts the result sources, displayed quantities, units, words, equations, code spans and substantive judgments. The resulting registry retains each original result in full, including the covariance, inference reference, confidence-set structure and JSON nulls. Each input is identified by its project-relative path and SHA-256.

## Save displays at analysis or registration

The same `research-artifact-registry-v1` registry holds an `items` object keyed by stable display IDs. Save the rows needed by a table or plot when the analysis produces them. A saved source result can carry `display_items`, an array of the display records below, or `display:{kind,rows,metadata}` with nested saved blocks. Named additional blocks in `displays` retain separate pointwise/simultaneous or design-specific views. Normalization maps those blocks to the existing items; a source without display rows receives a named coefficient or statistic table. Register an existing saved registry to create its SVG, PNG, HTML, PDF and LaTeX displays:

```sh
python harness/research.py gallery register --root "$PROJECT" \
  --registry analysis/saved-results.json --output analysis/gallery.json
```

`--items analysis/display-items.json` selects an explicit array of display records supplied by the completed analysis. Normalization and registration read saved quantities. Neither operation estimates a model or derives p values, standard errors or interval endpoints. Save the requested inference with the official producing function before registration.

Each item contains `id`, `title`, `kind`, `result_ids`, `columns`, `rows`, `metadata`, `display`, `interpretation`, `status`, `links` and `files`. `columns` is an array of `{key,label,unit}`. Each row contains scalar saved cells and its `result_id`; JSON null remains a missing cell and numeric zero remains zero. `files` is an array of project-relative display paths. Basic kinds are `descriptive`, `sample_composition`, `distribution`, `time_series`, `group_comparison`, `coefficient`, `event_study`, `robustness`, `alternative_specification`, `table` and `figure`.

A producer's `display` or named `displays` block can supply the same `columns` and `display` objects. Registration retains their labels, units, selected axes, series, facets and formats; it fills automatic defaults only for omitted presentation choices. For a structural result, save parameter and moment tables as `kind:"table"` and scenario outcomes as `kind:"structural"`. Give a row its `scenario`, `quantity`, `value` and `unit`, then select `display:{plot_type:"bar",x:"scenario",y:"value",facet:"quantity"}` when the quantities have different units. Each panel prints its saved unit. The producer saves every requested aggregate, difference and welfare measure before registration. A confidence-set display keeps each parameter and result on its own row and each connected component on that parameter's row.

Save each descriptive summary at its analysis grain, with the relevant group, period or bin keys, usable counts, denominator, weights and measurement units. Preserve bin edges and interval closure for distributions, and the adopted convention for quantiles. Save coefficient and event-study estimates together with their already computed endpoints. The renderer selects and draws those cells.

`research_data.py describe` produces Table 1 (mean, SD, median, requested quantiles and usable counts), group balance, sample flow, trends and saved distribution coordinates through the [descriptive-result interface](../../econ-data/references/research-data.md#saved-descriptive-results). Distribution metadata names `distribution_type`: `histogram`, `density`, `ecdf` or `box`. Histograms save bin edges and counts; density and ECDF plots save coordinates; box plots save `ymin`, `lower`, `middle`, `upper`, `ymax` and outlier counts. Rendering does not recompute any of those quantities. An individual observation identity remains in the scientific result; display metadata keeps sample definitions, groups, periods and aggregate contributions.

Saved regression blocks use `kind:"regression"` with `term`, `estimate`, `se`, `ci_low`, `ci_high` and `p_value`. The comparison table uses existing result IDs as model columns and retains saved counts, clusters, fixed effects, controls, sample policy, period, weights, estimator and units. A common-sample comparison names that adopted sample; model-specific samples retain their separate definitions. Event-study rows retain `event_time`, role and saved interval endpoints, including null endpoints at a reference period. Existing `diagnostics.group_time.cells` also projects directly to ATT(g,t) and cohort event displays; each saved cell keeps its value, endpoints, calendar time, event time, base and role. Individual sample IDs and weights stay in the original result. The saved `interval_type` / `ci_kind`, `confidence_level` and `reference_event_time` / `reference_time` travel into the display. RDD, IV, heterogeneity, sensitivity and counterfactual blocks use their producer's saved coordinates and named estimates through the same interface.

The standard regression presentation places a coefficient and its parenthesized standard error on separate rows. `show_ci`, `show_p` and `show_stars` select saved inference for display. `model_column` and `outcome_column` identify saved model/outcome columns; `model_order`, `model_labels`, `term_order` and `term_labels` set their display. `column_groups:[{label,models}]` groups columns; `panels:[{label,terms}]` groups coefficient rows; `statistic_rows:[{field,label}]` selects saved model metadata. `preset:"paper"|"meeting"`, `digits`, `table_number` and `latex_label` control presentation. Comparison retains each model's saved `formats` and fallback `digits` regardless of selection order. Formats bind to the original saved column, including `se` / `standard_error` / `std.error`, `p_value` / `pvalue` / `p.value`, and `ci_low` / `lower` / `conf.low` with their corresponding upper endpoints. Model metadata uses that model's column formats. The same returned `presentation` accompanies selected raw rows into Markdown and native Google Slides tables, so their coefficient and inference cells stay aligned.

Specialized `plot_type` values are `att_gt`, `cohort_event`, `parallel_trends`, `rdd`, `iv_first_stage`, `iv_reduced_form`, `iv_confidence_set`, `scm`, `scm_gap`, `scm_placebo`, `binned_scatter`, `smd`, `structural` and `geo`, alongside existing coefficient, event-study and distribution displays. Save points, line coordinates and interval endpoints separately with `component` and series/side keys. ATT(g,t) rows retain cohort, calendar time and effect; geographic rows retain a serialized GeoJSON geometry and its saved value. The `x`, `y`, `lower`, `upper`, `component`, `cohort`, `time`, `value`, `geometry` and `facet` display fields select saved columns. The scientific metadata owns reference periods, treatment times, cutoffs and bandwidths; presentation edits cannot change those definitions.

The producing analysis supplies each specialized display's coordinates and defining metadata:

| Display | Saved inputs and application conditions |
| --- | --- |
| DID and event studies | Event time, estimate, saved endpoints and reference/pre-treatment/post-treatment role; calendar time and cohort for ATT(g,t), and a cohort series for cohort-event plots. Retain base period, treatment timing/history, comparison group, sample, anticipation and aggregation weights. Keep pointwise and simultaneous intervals in separate named blocks with their actual level and family. |
| RDD | Numeric running-variable coordinates (`running`, `x`, `bin_mid` or `mean_x`), binned outcomes and their saved endpoints, and separate left/right fitted-curve rows. Retain cutoff, bin edges, side, plotting bandwidth and estimation bandwidth under their saved definitions. A coefficient-only RDD summary has no running-variable axis and registers as a table. |
| IV | Save first-stage and reduced-form outcomes, stage/result identity, instruments, sample and any plotted points or fitted coordinates. A confidence-set display retains each connected component's `lower`, `upper`, `lower_unbounded`, `upper_unbounded` and `set_type`; finite endpoints, empty sets and the real line keep their saved meanings. |
| Synthetic control | Time and separately identified observed, synthetic, gap and placebo series, with treatment time, donor definition, fit period and sample. The gap display consumes a saved difference; it does not subtract series or fit donor weights during rendering. |
| Structural results | Named fitted, baseline and counterfactual scenarios, saved grid/path coordinates, equilibrium points and requested welfare quantities. Retain scenario assumptions, parameter definitions, population and units; use separate axes or facets for different measurement units. |
| Geography | A saved region/location ID, serialized GeoJSON geometry and the corresponding value. The producing analysis owns the geographic-ID mapping and boundary version; the renderer draws the saved mapping without joining another geographic dataset. |

Axis and series selection choose existing saved columns. Binning, curve estimation, effect aggregation, confidence-set inversion, donor fitting and equilibrium solution remain with the producing analysis.

### Draw the model's economic relationship

Use the adopted equations to select the relationship carrying the claim. Save its calculated coordinates through the existing result producer and display them with `kind:"structural"` and the existing line, scatter, area or structural plot. The manuscript and exhibit consume the same model, parameter values, scenario and units.

| Economic claim | Saved coordinates and display | Connection to the argument |
| --- | --- | --- |
| A constraint changes an optimal choice | Budget or feasible-set boundary, selected indifference curves and optimum points | Identify the changed price, income or constraint and the resulting substitution or allocation. |
| A market intervention changes equilibrium | Demand and supply curves, baseline and changed equilibrium points | Show the price and quantity responses under the saved market-clearing conditions. |
| Strategic incentives select an equilibrium | Best-response curves in the same action space and their intersections | Name each player's action and the fixed primitives behind the intersection. |
| An intervention changes surplus | Saved lower and upper boundaries over the applicable quantity range | Link the shaded region to the producer's separately saved welfare statistic and accounting convention. |
| A state changes along an adjustment path | State coordinates and their actual period or sequence column | Explain the transition equation and the ordering of responses. |
| A dynamic rule or distribution changes | Policy/value functions or distribution coordinates on the saved state grid | Name the state, decision or value unit, horizon, normalization and scenario. |

Set `component:"equilibrium"` for optimum or equilibrium points and `display.point_label` to their saved label column. A `component:"region"` row uses `display.lower` and `display.upper` as its two economic boundaries. The renderer shades their saved coordinates; the producing calculation supplies the area and welfare quantity. These boundaries carry the region's economic meaning. Save statistical intervals in their own component.

A phase path uses `component:"path"` and `display.path_order` naming its numeric period or sequence column. The renderer joins rows in that order, preserving a trajectory whose state coordinate reverses direction. Budget lines, demand, supply, best responses and policy functions use the existing coordinate order for their curves. Separate panels retain separate units. State-transition probabilities use the existing table or bar presentation with origin and destination labels.

For an explicitly named non-economist audience, label the actions, prices, quantities and equilibrium points in ordinary language, and explain the movement shown in the figure. For a research audience, carry the paper's adopted symbols and comparison directly into the axes, caption and discussion under PROSE's reader contract.

At registration, `metadata` joins the saved result IDs to `producers` and `result_definitions`. Retain the actual producing run and specification IDs, code/specification/result references and hashes, engine and environment, sample and population, observation and assignment units, comparison, period, variables, measurement units, estimand, weights and saved inference settings. DID definitions retain treatment history, anticipation, cohort composition, aggregation weights, comparison groups and base period. Record the SE method, inference unit, clustering, degrees of freedom, interval type and level in `inference`. Producers retain the executed official function, effective options and saved-result format version. A source's optional `metadata` object supplies run, environment and economic definitions to the normalizer; an item's metadata supplies its shared display definitions. The selected input's provenance remains in the registry; fitted individual IDs stay in the scientific result. `status` records adoption, and `links.tasks` / `links.documents` connect the result to existing work and manuscripts.

Structural solvers can store complete paths inside `scenario`. Keep those calculated arrays in `source_result`; captions use the adopted scenario definition or its saved ID, name and description. Supply additional intervention definitions through the source or display `metadata`. This preserves the complete numerical result and gives each exhibit its economic comparison.

Model-based results carry `model_contract`, `knowledge_ids`, `equations`, `notation`, `parameter_roles`, `assumptions`, `normalization`, `equilibrium_selection`, `welfare_definition` and `horizon` in the same saved definitions. The producer's adopted definitions or the artifact specification's source `metadata` supplies those fields. `parameter_roles` identifies each estimated, calibrated or fixed parameter and its source and unit. Read these selected definitions with their saved quantities to compose the Model, Results and Discussion; match notation and defining conditions across the equation, table, figure and manuscript. The selected item's `source_reference` binds this context to its existing registry version. Knowledge IDs locate their registered derivations; the adopted model and saved result govern the paper's actual claim.

## Browse compare and edit saved results

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

`research_evidence.py gallery` and `research_artifacts.py gallery` expose the same commands. `show ID` returns one selected display and its `revision` for an edit; `preview ID --output PATH` renders saved rows to HTML. `render --item ID` saves a complete SVG/PNG/HTML/PDF/LaTeX generation from the selected item's rows. `list` supports `--kind`, `--status` and seven definition filters: `--result-id`, `--sample`, `--comparison`, `--outcome`, `--specification`, `--period` and `--adoption`. `compare` keeps the selected records together, returns the saved regression comparison and reports definition differences. A specialist's saved rows without an applicable x/y pair render as a table with their original columns.

The Python interface `gallery_items(root, gallery_spec_path, query="")` returns display records with `files: list[str]`, `columns: list[{key,label,unit}]` and `rows: list[dict]`. Its rows and columns reflect the saved display selection, while the registry keeps the complete saved rows. Each record's `source_reference` names the existing registry JSON path, item key and content version for the existing DAG. Search, comparison, preview and reporting read that saved content. They do not reopen raw data, producer code, source specifications or execution environments. The resulting record list is the meeting module's explicit selection input; only selected display assets, rows and metadata travel into a meeting bundle. Comparison returns definition differences for every selected result, including multiple results within one item. It distinguishes aligned saved definitions, differing definitions and missing required definition fields; it does not change weights or aggregate effects to force agreement.

Pass `item_ids=[...]` to select exact displays in their requested order. CLI `select` and `compare` use that same path. Projection, table composition and manuscript handoff operate on those selected records; unselected displays remain stored for their own consumers.

Choose the main exhibits from the central claim and the identifying comparison or model change that establishes it. Use the existing argument's claim/evidence IDs and `exhibits.node_ids` to connect that inference to saved item IDs and their `source_reference`. Select the estimates, sample/comparison definitions, model parameters or fit quantities needed for that inference, then the counterfactual outcomes and welfare measure it establishes. Keep an exhibit in the main text when removing it breaks that explanation; put supporting specification variants, detailed parameter lists, derivations and additional diagnostics in the Appendix. A parameter or fit comparison that determines the central claim belongs beside that claim. Use a table for the exact model comparison and a figure for a distinct path, distribution or mechanism; retain one representation when both convey the same information. Results states the saved comparison and magnitudes; Discussion uses that result to explain the mechanism and its economic consequence under the same definitions.

For the bundled growth example, a claim about the adopted output-tax path's allocation and welfare consequences selects the saved paths and welfare for the main text, and the parameter list and numerical-equation diagnostics for the Appendix:

```sh
python harness/research.py gallery select --root "$PROJECT" \
  --registry examples/research-workspace/gallery.json \
  specialist-growth-r01-displays-allocation_paths specialist-growth-r01-displays-welfare
python harness/research.py gallery select --root "$PROJECT" \
  --registry examples/research-workspace/gallery.json \
  specialist-growth-r01-displays-parameters specialist-growth-r01-displays-model_fit
```

Each command returns its two items in that order with the original rows, `result_definitions` and source references. The welfare rows retain baseline/scenario values in discounted log consumption for one representative household over 20 model periods. Carry those definitions into the selected passage; the diagnostic rows retain their role as equation checks. Add `--output` at the project's existing manuscript input destination when saving the selection for its consumer.

The local marimo app uses the project's existing Python environment with pinned `marimo` and `matplotlib`. It offers all seven definition filters, multiple result selection, preview, comparison, table headings/columns/order/notes, plot type, saved specification and series selection, series order and labels, axes/scales/ranges, colors, legend, title and dimensions. Paper and presentation styles set the figure text size; Noto Sans CJK JP supplies Japanese glyphs. Changes preview reactively; the save buttons persist an explicit edit. The app separately edits interpretation, findings, issues, adoption decisions/status and task/document links. It exports the selected display records as JSON for meetings while preserving the existing project, history, GitHub and meeting screens. The [synthetic display example](https://github.com/yoshimurahiroki/econ-project-mini/tree/main/examples/research-workspace) exercises this saved-result path.

`edit_gallery_item(root, registry_path, item_id, changes, expected_revision=None)` distinguishes display changes (`title`, `display`), interpretation changes (`interpretation`, `findings`, `issues`, `adoption_decision`, `status`, `links`) and scientific changes (`rows`, `metadata`, units, result identity or other definitions). The UI and `edit --expected-revision HASH` command bind edits to the current item's `state.content_hash`. Display edits preserve saved scientific rows and produce a complete new display generation. Interpretation edits preserve display assets. A scientific change goes through the existing adopted-specification and result-registration path. A saved view never changes the selected sample, estimator, denominator, bins or inference.

The returned `changed_references` identifies the edited fields with existing JSON references: `keys:["items",ITEM_ID,"display"]`, `rows`, `metadata`, `interpretation` or `files`. Bind consumers to the fields they actually use through the existing argument/task dependency graph. A figure uses its rows, columns and display; interpretation uses its saved result definitions. A label edit regenerates the selected display consumers, an interpretation edit reopens its text consumers, and an authorized specification change updates the corresponding scientific result and its actual descendants. Keep unrelated result IDs reusable. The gallery adds no task store, registry or approval stage.

## Source basis for reuse and provenance

The [AEA Data and Code Availability Policy, February 2026](https://www.aeaweb.org/journals/data/data-code-policy), requires a program-to-output-to-exhibit map and reproduction instructions with software, hardware and running-time requirements. These fields belong to the producing result and reproduction package. The gallery retains their saved identities for result reuse. The policy's data-access and deposit provisions govern a separately authorized replication deposit.

The [AEA Data Editor's preparation guidance](https://aeadataeditor.github.io/aea-de-guidance/preparing-for-data-deposit) connects data provenance, computational requirements, programs and expected outputs. Its “No manual modifications” section requires figures, tables and numerical text to be generated from code. Saved numerical rows and persistent display settings give the local editor that executable correspondence.

[TIER Protocol 4.0's Output folder](https://www.projecttier.org/tier-protocol/protocol-4-0/root/output/) preserves generated tables, figures and other reported results, with separate data-appendix and analysis outputs. The gallery's kinds and source links retain that distinction in the existing registry.

[showyourwork's dependency configuration](https://show-your.work/en/latest/config/#dependencies) declares the files used by each script and reruns the consuming workflow section when those dependencies change. ERS applies that dependency principle through its existing DAG and selected JSON references. It reuses saved estimates when display settings change.

The marimo documentation defines [reactive controls](https://docs.marimo.io/guides/interactivity/), [selectable tables](https://docs.marimo.io/api/inputs/table/), [explicit run buttons](https://docs.marimo.io/api/inputs/run_button/), [application arguments](https://docs.marimo.io/api/cli_args/) and [HTML export](https://docs.marimo.io/guides/exporting/). The local app uses those native controls for browsing, editing and explicit saves. Source versions above were read on 2026-11-05.

The [modelsummary extension interface](https://modelsummary.com/vignettes/modelsummary_extension.html) accepts saved tidy/glance model quantities. The existing analysis engines extract quantities from their supported fitted objects. [ggfixest](https://grantmcdermott.com/ggfixest/) supplies coefficient and event-study displays for supported fixest objects; its post-estimation calculations belong to the producing analysis. The gallery consumes the chosen endpoints and reference period already saved by that producer. Its display-only exports follow the same saved-data separation as the official [ggplot2 saving interface](https://ggplot2.tidyverse.org/reference/ggsave.html).

The specialized layouts use the event-study and balance presentation examples in [EconAgentSkills](https://github.com/JonasWeinert/EconAgentSkills/tree/main/_skills/communication/econ-visualization), the event-study and RDD layouts in [SSCI-Plots](https://github.com/O0000-code/SSCI-Plots/blob/main/references/chart-types-causal-econ.md), and the model/series identities in [ggfixest's extraction code](https://github.com/grantmcdermott/ggfixest/blob/main/R/iplot_data.R). The existing renderer supplies their display operations. The producing RDD analysis saves [rdplot's `vars_bins`, `vars_poly`, cutoff and bandwidth](https://github.com/rdpackages/rdrobust/blob/main/R/rdrobust/R/rdplot.R). Bin intervals and fitted curves keep their separate roles. These source examples do not add estimator thresholds or analysis runs to gallery browsing.

## Default LaTeX family

New paper and slide exports use the supplied [Econometrica paper](../../../tex/paper/ecta_template.tex) and [metropolis slides](../../../tex/slides/main.tex). Their original author/title/body placeholders remain available for direct editing. Keep the paper's class, configuration and `ecta-fullname.bst` together. A citing direct document reads its project bibliography at `tex/bibliography.bib`; a missing requested bibliography remains a build error.

The existing artifact helper derives Pandoc adapters from those exact source templates:

```sh
python harness/research_artifacts.py generate-adapters --root "$PROJECT"
```

The project Quarto defaults and new artifact LaTeX/PDF stages consume those adapters. The shared LuaLaTeX helper handles the journal class's fontspec initialization, citation-aware BibTeX passes, backreferences and previous-PDF restoration on a failed build. Template, package and build-helper versions enter the affected stage inputs, so a layout change rebuilds the corresponding artifacts while preserving matching estimates and their scientific definitions. Keep explicitly adopted document formats with their existing projects.

## Run the reproducible example

Use a project containing the existing harness, causal and market scripts and an analysis Python with their installed dependencies. Pandoc, Quarto, LuaLaTeX and an SVG converter must be available. Source the project's usual environment before these commands; choose an output directory that does not already exist.

```sh
python harness/research_evidence.py artifacts example \
  --root "$PROJECT" --output "$PROJECT/outputs/artifact-example" \
  --python "$ANALYSIS_PYTHON" --pandoc "$PANDOC" --quarto "$QUARTO"
python harness/research.py --root "$PROJECT" outputs/artifact-example/manifest.json
```

The example draws a seeded IV sample, executes `research_causal.py` and `research_markets.py`, and writes the actual results, source specification, data, article and slide templates, artifact specification and executable DAG manifest. It connects the simulated IV result and the independent uniform-offer, full-recall search model. The search reservation threshold z solves c = (1−z)²/2 for 0 ≤ c ≤ 1/2. Its saved equation residual, code expression, baseline cost and reported threshold are checked together. The DAG returns the current generation path of every artifact; those files are not copied over previous generations.

## Adopt an artifact specification

The `example` writes a complete working JSON specification. Its `sources` list gives each distinct `id`, `result`, `code` and, where applicable, `specification` and `data`, all relative to the project root. A saved producer `spec_sha256`, `data_sha256`, `script_sha256` or `producer_sha256` must match the selected file. When a producer did not record a hash, provide the owner's SHA-256 in `expected_hashes` for each selected code, specification or data input. That adopted hash pins the selected input; it does not assert that an older result recorded its producing code hash. Preserve the actual source result and execution record when establishing that historical correspondence.

The normalizer registers every finite `{value,unit}` in `statistics`, names coefficients, standard errors, saved p values, saved interval limits and observation counts, and retains the complete source result. It preserves null entries in that source without converting them to zero. Generic saved intervals use `confidence_lower.TERM` and `confidence_upper.TERM`; explicitly saved 95% intervals retain `confidence_95_lower.TERM` and `confidence_95_upper.TERM`. Their level and inference definition remain attached to the saved result. For older coefficient results, supply `coefficient_units` mapping each parameter to its actual unit; no unit is inferred from a label. `quantities` can explicitly select additional finite source-result key paths and their adopted units. Stable keys are `<source-id>.<semantic-key>`.

Each `bindings` entry supplies a registry `key`, exact `unit`, numeric `format`, `display_unit` and human-readable `label`. Supported formats are `f`, `g`, `e`, or a precision such as `.3f`. A template statistic consists of two opening braces, `stat:name`, and two closing braces. The table and figure markers use the same brace pairs around `table` and `figure`. A value and its displayed unit are inserted together; their character spans generate the existing binder's number contract automatically. Repeated occurrences each receive their own binding. `figure` selects binding IDs sharing one unit.

Optional `definitions` bindings insert saved nonempty strings into both article and slide templates. A definition placeholder contains two opening braces, `definition:name`, and two closing braces. Each entry supplies a `key` array into the same registry. Select an adopted equation or comparison from `records.SOURCE.source_result`, or a selected item's economic definition from `items.ITEM.metadata.result_definitions.SOURCE`. For example, with the growth source registered under `specialist-growth-r01`:

```json
"definitions": {
  "period": {"key": ["items", "specialist-growth-r01-displays-welfare", "metadata", "result_definitions", "specialist-growth-r01", "period"]},
  "welfare_target": {"key": ["items", "specialist-growth-r01-displays-welfare", "metadata", "result_definitions", "specialist-growth-r01", "estimand"]}
}
```

The `period` placeholder inserts `20 model periods`; `welfare_target` inserts `Sum of beta^t log(c_t) over the stated horizon`. Use those saved definitions in the sentences defining the horizon and welfare objective. Select a string leaf for an equation, notation entry, parameter role, comparison or inference description; arrays, objects and numerical values retain their own saved types. Definition text is inserted literally in one pass, including its Unicode, equations and braces. Numerical occurrences keep their correct evidence spans after insertion. The [native research renderer](../../../harness/research.md) accepts the same definition placeholder in section stages, with `stage`, `output` and `key` identifying the consumed saved output. Both paths retain the existing result dependencies and artifact formats.

A `models` entry names the `source`, exact article `equation`, exact `code_quote`, source-result `residual_key`, tolerance and supported owner `judgment`. Optional `parameters` name an exact manuscript target and code quote, a specification key and its unit, and a registered result statistic. The generated model and parameter contracts bind the article, code and specification hashes, saved result identity, residual and selected quantity through the existing evidence binder. An owner confirms the substantive equation-to-code correspondence and economic interpretation; exact text matching establishes the selected passages.

For an adopted specification at `analysis/artifacts.json`, materialize and execute it with:

```sh
python harness/research_evidence.py artifacts materialize \
  --root "$PROJECT" --spec "$PROJECT/analysis/artifacts.json" \
  --output "$PROJECT/analysis/artifact-manifest.json" \
  --python "$ANALYSIS_PYTHON" --pandoc "$PANDOC" --quarto "$QUARTO"
python harness/research.py --root "$PROJECT" analysis/artifact-manifest.json
```

The generated stages normalize each selected result separately, merge their registry, render the table and SVG, generate article and slide sources, bind the manuscript and model, and export article HTML, LaTeX, PDF and Quarto HTML plus Beamer slide PDF. The article and slide sources are Quarto Markdown. Pandoc and Quarto execute as declared stages, and the Quarto output retains its executable version and hash. The PDF stages use a project-local LuaTeX cache; the runner records the selected environment and Pandoc executable identity.

Result, specification, data, code and template bytes enter the ordinary stage signatures. A changed result rebuilds its registry fragment and descendants; a figure consuming a different source remains reusable. A changed code or specification hash fails its old source binding until the owner adopts the changed input and its corresponding result. Binder verification rechecks the producing references of each selected registry quantity; an unrelated registry record is outside that selection. An older report fails when its selected result or code changes. Run the manifest again after an authorized update; the existing research runner retains prior generations and rebuilds affected stages. Update the article or slide text when a changed result changes the adopted argument.

## Claims, coverage and requested re-review

The same `research_evidence.py review CONTRACT --root PROJECT --output PACKET` selects registered claims and their original source passages. An anchor may name its evidential `role`, such as population, identification, assumption, result or counterevidence. A claim's `bindings` list refers to the existing `numbers`, `models` or `mappings` IDs; the packet supplies only those selected result values, producing inputs and code spans. `bind` checks their existing units, identities, formatted values, original equations and residuals. Multiple anchors and bindings establish their separate roles; the owner judges the resulting inference.

`claim_coverage` locates citation, quantitative, inference, causal and theoretical sentence candidates within `coverage.spans`, or the manuscript when no scope is selected. It returns exact Unicode character spans, detection signals and uncovered candidates. These heuristics do not establish truth or semantic completeness. Read the whole requested argument and register the material claims they miss. For selected coverage enforcement, set `coverage.claims` to true and retain a supported `coverage.claim_judgment` using the existing reviewer/decision/rationale judgment. A specific nonmaterial candidate can have its exact `target` and reasoned `judgment` in `coverage.claim_accounts`. Existing numerical coverage and source-bound numeric accounts remain in force. This is a manuscript-specific assessment, not a general detection exemption.

A requested review round adds a `review` object to the same contract. Its initial `criteria` are nonempty `{id,text}` rows. The owner's `assessment` has a `reviewer` and `findings`; each finding retains `id`, `claim_id`, `criterion_id`, `decision` (`supported`, `revision-required`, `unresolved` or `removed`), `rationale` and nonempty hash-pinned file `references`, with an optional exact `span`. Revised text has exact manuscript spans in `changes`. The resulting `reviewed` record means that the supplied evidence assessment covers its selected claims; its findings can still require repairs. It grants no certification or release authority.

Re-review points `review.previous` to the saved completed review's `{path,sha256}`. Initial criteria, adopted scientific identities and finding targets remain fixed. A changed criterion is rejected. Omitted initial findings are rejected when supplying the revised assessment. A removed finding requires the actual earlier claim to be absent from the new manuscript. The packet identifies `claims_to_reassess`, `reusable_claims` and removed claim IDs. Reused findings link their historical review through `reused_from`; current source/result context stays beside the current manuscript.

The manuscript's whole-file hash pins the delivered version. Each claim fingerprint instead binds its actual quoted claim, adopted identities, source editions/propositions and original locators, selected quantity and producing code/input identities. It excludes unrelated manuscript text and manuscript character offsets. A peripheral edit preserves those judgments; a changed selected claim, source edition or calculation input reopens its dependents. Register the selected fingerprint, decision and rationale as an existing state object output when continuation needs it, and let each writing or analysis task consume that output ID. Requeue the changed output through the existing state helper; preserve unrelated outputs and completed consumers.

Supply the author letter only through `review.author_response` together with `review.response_after`, a hash-pinned separately saved assessment of the current evidence. The command validates that assessment and its criteria before reading the letter, and returns `response-comparison-required` with unchanged evidence findings. Compare the letter's assertions with those findings. A new determining fact returns to the same evidence and assessment path; a response alone never silently changes the verdict. This selected file dependency controls the packet contents; it does not attest to unseen host inputs or create another reviewer Agent.

To generate a requested response from the completed revision, supply the current assessment with each finding's `changes` and `references`, then select `review.response_draft` through the same review entry point. It returns the original comment and passage, current revision, supporting evidence and response text. Use [econ-review's response contract](../../econ-review/SKILL.md#locate-and-repair-the-cause) for the language, finding selection and source correspondence.

Compose the finished response with the existing writing host after revising the actual manuscript and assessing its changed claims:

```sh
python harness/research_evidence.py review writing/current-contract.json \
  --root "$PROJECT" --output writing/current-review.json \
  --host writing/host-adapter.py --rules writing/rules.json \
  --request 'Compose the referee response from the assessed manuscript revision.' \
  --writing-mode compose --execution-kind single-agent-sequential \
  --author-id author --response-output writing/response.md
```

The host and rule files use the existing [paragraph callback interface](paragraph-workflow.md#command-entry-points). The task's operation is `econ-writing:compose`, `econ-writing:revise` or `econ-writing:translate`. Its payload carries the requested language, adopted scientific identities, selected original comments and passages, actual revised spans, assessment reasons, source text and saved quantities. The host returns `{"responses":{"FINDING_ID":"completed response text"}}` for exactly the selected findings. The same host observer binds that returned wording to its actual invocation. The response explains what the revision establishes, why its economic reasoning answers the comment, and where the revision appears. The packet retains the full evidence correspondence and execution; the Markdown letter contains the comments and completed responses. Ordinary direct writing uses the same composition procedure and saves its finished text in the requested destination.
