# Public data acquisition and research tables

Use for data acquisition and construction through the assembly specification: sources, constructed variables, analysis samples, shared tables across SQL, Python, R and Julia.

Contents:

- [Official series by provider](#official-series-by-provider)
- [Data scope](#data-scope)
- [Acquisition and catalogues](#acquisition-and-catalogues)
- [Data used in existing research](#data-used-in-existing-research)
- [Document tables](#document-tables)
- [Joining, panels and geographic data](#joining-panels-and-geographic-data)
- [Shared tables across SQL, Python, R and Julia](#shared-tables-across-sql-python-r-and-julia)
- [Constructed variables and analysis samples](#constructed-variables-and-analysis-samples)
- [Saved descriptive results](#saved-descriptive-results)


## Official series by provider

`python3 skills/econ-data/scripts/research_data.py acquire SPEC.json --output DIR` saves the original responses, `observations.csv` and `data-record.json` with source, definition and terms of use.

| Provider | `series` | Key | Coverage |
| --- | --- | --- | --- |
| `dbnomics` | `PROVIDER/DATASET/SERIES`, e.g. `IMF/IFS/A.JP.11____XDC` | none | ECB, OECD, IMF, BIS, Eurostat, ILO, World Bank, BOJ, ESRI, METI, JILPT and other providers through one interface |
| `estat` | ten-digit statsDataId; `filters` with e-Stat parameters (`cdArea`, `cdCat01`, `cdTime`) | `ESTAT_APP_ID` (free) | Japanese government statistics |
| `fred` | FRED series ID | none | US and international series on FRED |
| `worldbank` | indicator code with `countries` | none | World Development Indicators |
| `imf` | DataMapper indicator with `countries` | none | IMF DataMapper |
| `eurostat` | dataset code with `filters` | none | Eurostat |
| `census` | ACS variable or `POPESTIMATE` with `geography` | `CENSUS_API_KEY` optional | US Census |

Each dataset keeps its original responses, definition, vintage date and terms of use in its `data-record.json`; the terms of the original provider apply, including limits on redistribution and on use with AI systems. Record the dataset in the project context (`work/context.md`, Data holdings) so later tasks reuse it.

## Data scope

- `skills/econ-data/scripts/research_data.py` retrieves specified official observations, preserves the original response bytes and response hashes, and builds research tables from hashed source snapshots.
- It uses the existing `research_sources.py` connector for HTTP retrieval and World Bank definitions.
- The researcher chooses the observation unit, period, variables, data conditions and join keys before acquisition; `research_design.py assess` evaluates a declared question, period, population, grain, required fields, missingness, variation and linkage against the actual records and cited source spans.

- Each command writes a new output generation.
- Its output directory can contain pre-created empty subdirectories; existing files and symlinks stop execution before any output is written.
- After a failed operation, select a new directory so its retained source responses and inputs remain unchanged.

## Acquisition and catalogues

Run `python skills/econ-data/scripts/research_data.py acquire SPEC.json --output NEW_DIRECTORY`. A specification always provides `provider`, `unit` and `definition`. The supported provider-specific fields are:

- `fred`: `series`, `start` and `end`, with dates in `YYYY-MM-DD`. The source is FRED's public graph CSV. The returned monthly or daily observation dates are preserved.
- `worldbank`: `series`, `countries` (country codes), integer `start` and `end` years. The existing World Bank connector retrieves both observations and indicator documentation.
- `imf`: `series`, three-letter `countries`, `start` and `end` years. The public IMF DataMapper indicator endpoint provides the values.
- `eurostat`: `series` (dataset ID), `filters` (explicit dimension ID/value strings), `start` and `end`. The JSON-stat dimensions and each dimension's code are preserved. Select a sufficiently narrow set of dimensions for the intended grain.
- `census`: an integer `year` fixes the adopted release; an omitted `year` or `year:"latest"` explicitly requests the latest published release. For publicly downloadable Population Estimates, use `series:"POPESTIMATE"`, `unit:"persons"`, an ordered `start`/`end` observation period and `geography:"state:06"`, a comma-separated list of two-digit state FIPS codes, or `state:*`. Here `year` identifies the vintage, which can revise estimates for earlier observation years. The helper follows the official Population Estimates vintage, state and totals directory links to the published `NST-EST…-ALLDATA.csv`; the actual `POPESTIMATE` columns establish available years. For ACS five-year detailed tables, use an official variable ID as `series` and a supported `geography`. The official Census dataset catalogue selects the published ACS release, and the variable endpoint supplies its label and concept. Numeric suppression codes retain their original status alongside missing values. The ACS data endpoint can return a key-required HTML response; the retained response shows the actual access result.
- The result consists of `observations.csv` and `data-record.json`: provider, selected specification, units and definitions, terms URL, raw response path and SHA-256, missing counts, exact code hash and generated table hash.
- Raw-response paths are relative to their owning record and remain valid when the completed generation is published.
- Existing absolute references remain accepted.
- Each normalized row contains `entity`, `period`, `value`, `status`, `unit` and applicable dimensions.
- The declared unit is the researcher's adopted source unit; any conversion occurs explicitly in the assembly specification.
- A new output directory preserves earlier snapshots.

- Census records preserve the requested specification and the resolved release in `definition`: `selection` (`explicit` or `latest-published`), selected ACS `year` or Population Estimates `vintage`, the observation `period`, official metadata and source URLs, and the acquired definition.
- ACS records retain the official dataset metadata, five-year coverage and variable metadata.
- Population Estimates records retain the published vintage's coverage, actual available years and selected source columns; each value is a July 1 resident population estimate.
- `responses` retains the catalogue, directory, variable-definition and observation responses actually used, including retrieval time and content hashes.
- A new published year requires no code change; a pinned year selects its own release and fails when that release or the requested observation columns are absent.

When Census requires a user key for ACS observations, set `CENSUS_API_KEY` in the selected environment and include its name in the research stage's `inherit_env`; it is sent only to that observation endpoint, omitted from saved URLs and metadata, and never added to public catalogues or Population Estimates requests.

- `catalog SPEC.json --output NEW_DIRECTORY` searches bounded official metadata: IMF DataMapper indicators with `{"provider":"imf","query":"real GDP growth","limit":5}` or Census ACS variables with `{"provider":"census","year":"latest","query":"total population","limit":5}`.
- An integer Census `year` searches that pinned release; omitting it selects the latest published ACS five-year detailed tables.
- Terms, query, selected release, complete returned source bytes, SHA-256 and the matched official metadata are retained.
- World Bank indicator search uses `research_sources.py indicators`, and Eurostat dataset and dimension metadata are returned by a filtered acquisition.

## Data used in existing research

- `dataset-use SPEC.json --output NEW_DIRECTORY` searches a selected, hash-verified paper PDF for adopted dataset-name patterns.
- The specification supplies `source:{path,sha256,url}`, `paper`, `first_page`, `last_page` and `datasets:[{id,regex}]`.
- It invokes `pdftotext -layout` on the stated PDF pages; matches include page, matched text, normalized-page offsets, normalized-page SHA-256 and surrounding source text.
- A researcher reads the context to establish how the paper uses the named dataset and the required unit, population and period.
- The search expressions determine what this operation can find.

## Document tables

- `extract SPEC.json --root ROOT --output NEW_DIRECTORY` extracts a table from a local hash-verified original.
- For HTML, specify `format:"html"`, zero-based `table_index`, optional `row_regex`, `unit`, `definition` and optional numeric column names.
- The selected table needs a distinct header and rectangular rows.
- For PDF, specify `format:"pdf"`, one-based `page`, the exact selected `exact_line`, a `row_regex` with named groups, and optional `numeric` group names.
- The helper requires a unique exact-line/regex match in that page and calls `pdftotext -layout`; the output records the original hash, page, line number, extraction engine, matched fields, unit and definition.
- Row choice, page and capture expressions belong to the adopted source specification.

## Joining, panels and geographic data

- `assemble SPEC.json --root ROOT --output NEW_DIRECTORY` reads CSV, Parquet and Arrow IPC inputs through `{path,sha256}` references.
- CSV identifiers remain strings, preserving leading zeros.
- Typed inputs retain their column order, integer precision, timestamps, decimals and categorical labels.
- A join declares `table`, lists of `left` and `right` keys, output `columns`, `cardinality` (`one_to_one` or `many_to_one`) and `unmatched` (`error` or `keep`).
- Right keys must be unique and complete; one-to-one left keys must also be unique.
- Joins project the required right-table columns and preserve the left population.
- Declare `rename`, `numeric` and `scale` transformations where needed.
- Every resulting column requires its `unit`, `definition` and definition `version`; no implicit currency or population scaling is performed.

- `grain` is a list of fields whose complete values uniquely identify a row.
- Optional `panel` declares `entity`, `time` and whether balance is required; each entity–time key must be unique, and a balanced panel must contain the same times for every entity.
- Optional `geography` supplies a hash-verified GeoJSON FeatureCollection and `data_key`/`feature_key`.
- Keys must match; point positions must have finite WGS84 longitude and latitude; polygons require closed rings with at least four positions, and multipolygons require valid polygons.
- The output includes one canonical analysis table, selected `geography.geojson` and `data-record.json` with source hashes, definitions, panel summary and transformations.
- Polygon topology beyond ring closure is not evaluated.

## Shared tables across SQL, Python, R and Julia

- Assembly's `output_format` selects `csv` (the default), `parquet` or `arrow`.
- It writes only `analysis.csv`, `analysis.parquet` or `analysis.arrow` for that sample.
- Parquet uses Arrow schema metadata and Parquet 2.6 timestamp precision; Arrow uses Feather V2 / IPC file format.
- The selected format requires Python `pyarrow`; SQL additionally requires `duckdb`.
- Restore those dependencies in the declared research environment.
- Keep the canonical source references and generated `table.path` in the existing stage dependencies; format changes rebuild affected descendants through the same DAG.

- For direct CLI execution, restore only the dependencies selected by the operation in its adopted Python environment.
- CSV input and output use pandas from `requirements-research.txt`; Parquet or Arrow input/output adds `python -m pip install pyarrow==26.0.1`.
- SQL construction adds `python -m pip install pyarrow==26.0.1 duckdb==2.0.0`, including SQL over CSV.
- These are the same format/engine dependencies returned by the existing research selector.
- A stage retains that environment and the selected table format in its ordinary runtime and input bindings.

- `data-record.json.table` retains `path`, `sha256`, `rows` and ordered `fields`, and adds `format` and ordered `schema`.
- Generated table and geography paths are relative to their owning record.
- Generated analysis inputs reference their table and record relative to the analysis specification; these references survive publication of the completed generation.
- Each schema field records its name, pandas dtype and nullability; typed outputs also record the Arrow type, including timestamp unit/timezone and decimal precision/scale.
- Categorical columns retain labels, their dtype and ordered status in the record and native file metadata.
- The record retains `inputs`, `grain`, `sample`, definitions and transformations.
- Optional top-level `clusters:[COLUMN,...]` and `weights:{column,kind,...}` preserve their adopted meanings; `weights:{kind:"none"}` identifies equal observation weights.
- `observation_unit` retains the adopted research unit.
- Analysis-specific inference settings remain in each adopted analysis specification.

- Python consumers call `research_data.read_frame(path, columns=None, string_columns=None)`.
- `columns` projects fields in the requested order; `string_columns` names semantic identifiers that require text representation.
- `string_columns=True` provides the all-text view used by design assessment and preserves literal CSV status strings.
- Estimation uses explicit identifier lists and retains other native types.
- R consumers prepend `R_READ_TABLE` and call `ers_read_table(path, text_columns=character(), columns=NULL)`; `text_columns=TRUE` requests the all-text view and preserves literal CSV status strings.
- R uses `arrow::read_parquet` or `arrow::read_ipc_file` for typed inputs.
- Julia consumers prepend `JULIA_READ_TABLE` and call `ers_read_table(path; string_columns=String[], columns=nothing)`, using CSV.jl, Arrow.jl or Parquet2.jl with DataFrames.jl and Tables.jl.
- Every consumer reads the same saved path directly.
- Category encodings and model reference levels belong to the adopted estimator specification.

- R checks selected native timestamps by converting `POSIXct` back through official Arrow arrays with the original timestamp type and comparing physical integer values.
- Values that lose their declared precision stop at that conversion boundary; construct an explicitly defined string/integer clock in the existing assembly.
- Julia materializes selected native columns before converting semantic identifiers to text.
- Arrow microsecond/nanosecond timestamps retain their physical `Arrow.Timestamp` values, time unit and timezone.
- Parquet2's `DateTime` conversion cannot retain a declared submillisecond precision; the reader stops for those selected columns.
- Use the canonical Arrow table or an explicitly defined string/integer clock.
- An unselected timestamp column does not block either reader's projected read.

- For source-side selection and aggregation, replace `base` with `sql:{query,tables,joins}`.
- `tables` maps a SQL alias to each exact `{path,sha256}` input.
- Source field names must be distinct under case-insensitive SQL identifier matching; normalize ambiguous source headers in their earlier assembly.
- `query` is one SELECT over exactly those aliases; it owns the selected fields, casts, filters, joins, grouping, additive numerators/denominators, missing-value treatment and result order.
- CSV scans use VARCHAR columns, so numeric operations require explicit casts.
- Parquet and Arrow use lazy datasets; DuckDB pushes supported projections and predicates into their scans and executes joins and aggregation before collecting the result.
- Only the declared source paths are allowed, external access is disabled before the query, and extension installation is disabled.

- Each SQL join declares `{left_table,right_table,left:[KEY,...],right:[KEY,...],cardinality,unmatched}` using the same `one_to_one`/`many_to_one` and `error`/`keep` contracts.
- Optional `join_type:"LEFT"|"INNER"` fixes its exact executed type.
- DuckDB's parsed query must contain exactly the declared direct-column equality joins.
- `unmatched:"keep"` requires `LEFT JOIN`; `unmatched:"error"` accepts `LEFT JOIN` or `INNER JOIN` after establishing complete matching.
- Two source tables can use `USING`; a join chain uses qualified `ON` columns.
- Each lookup joins a distinct declared right source to a left source or preceding lookup chain.
- Normalize differing key types and construct derived join inputs in an earlier assembly.
- Complete keys, declared uniqueness and unmatched counts are checked on each join's actual left input and right source, including multiplicity introduced by earlier joins.
- All joined source aliases require declarations.
- The installed DuckDB `json` extension supplies the parsed query and is loaded explicitly.
- Use an explicit `ORDER BY` when row order determines an operation.
- The SQL transformation record retains the exact query, source aliases, hashes, source field types/counts, executed join types, join counts, returned fields/count and DuckDB version.
- These source-to-result counts describe SQL construction; the existing `sample` builder subsequently records analysis exclusions at the final grain.
- The normal definitions, transformations, grain, sample, panel and analysis binding contracts also apply to SQL output.

Official interfaces: [Arrow pandas conversion](https://arrow.apache.org/docs/python/pandas.html), [Parquet writer](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.write_table.html), [R Arrow readers](https://arrow.apache.org/docs/r/reference/read_parquet.html), [DuckDB Arrow scans](https://duckdb.org/docs/stable/guides/python/sql_on_arrow), [DuckDB Python API](https://duckdb.org/docs/stable/clients/python/reference), [DuckDB configuration](https://duckdb.org/docs/stable/configuration/overview), [Arrow.jl](https://arrow.apache.org/julia/stable/manual/), and [Parquet2.jl selective reading](https://expandingman.gitlab.io/Parquet2.jl/).

## Constructed variables and analysis samples

- The same `assemble` specification accepts an ordered `transformations` list and one `sample`.
- Execution order is hashed table loading or the declared SQL selection, declared joins, existing `rename`/`numeric`/`scale`, ordered transformations, grain validation, common-sample selection, then panel/geography validation and output.
- Normalize a source's join keys in its own assembly before attaching that source.
- Raw inputs are unchanged.
- An output name already present in the table requires `replace:true`.
- Numeric domain errors stop the operation; a declared `on_invalid:"missing"` retains the row with a missing generated value.
- Missing inputs propagate without clipping, imputation or sample relaxation.

- `definitions` remains the single variable dictionary.
- Each column requires nonempty `unit`, `definition` and `version`.
- Optional fields are `source_fields`, `role`, `causal_role`, `timing`, `rationale`, `measurement` and `inputs`, using the [variable-design contract](../../econ-design/references/designs.md).
- Define all transformation operands and outputs, including intermediate columns subsequently removed by aggregation or reshape.
- The saved record's `definitions` contains the final analysis columns; each executed transformation retains its input/output names, units, reference clock, source-field hashes, missing-output counts and actual before/after row counts.
- Grain changes are separate from sample attrition.

- The existing `measurement` object can retain the source document's ID, version, locator and content hash with the adopted construction.
- Keep the original document and inspected passage in the existing source catalog or acquired knowledge output.
- Bind that original and the selected `definitions[COLUMN]` value through the decision's [existing references](../../../harness/state.md#retain-and-retrieve-adopted-definitions).
- `assemble` carries the full definition into `data-record.json`; estimation, Gallery and Writing reuse it.
- Record the adoption rationale, alternatives and switching authority in `task_context.adopted_decisions`, and retrieve them with `state.py context`.
- A document update first changes the referenced source judgment; the adopted specification and its calculation change through their existing authority and dependency paths.

Every operation below uses `op` plus the listed fields. `input` and `output` name columns. Arithmetic operands can also be finite numeric constants. Operations do not execute expression strings.

| Operation | Adopted fields and calculation |
| --- | --- |
| `date` | `input`, `output`, explicit source `format`; optional `output_format` (default `%Y-%m-%d`) and `timezone`. Ambiguous/nonexistent local times fail. |
| `period` | `input`, `output`, `frequency`, such as `M`, `Q-DEC` or `Y-DEC`; emits the calendar period label. |
| `string` | `input`, `output`; explicit `strip`, `case` (`lower`, `upper`, `casefold`), Unicode normalization `unicode`, or code `width`/`pad` (default pad `0`). Records source labels merged by normalization. Blank strings remain missing before padding. |
| `category` | `input`, `output`, explicit `mapping` from string source labels; `unknown` is `error` (default), `missing` or `keep`. Alternatively use `breaks`, `labels`, `right` and `include_lowest` for declared numeric bins. |
| `indicator` | `input`, `output`, `values`; one for declared values, zero for other observed values, missing for missing input. |
| `arithmetic` | Ordered `inputs`, `output`, and `function`: `add`, `subtract`, `multiply`, `divide`, `min` or `max`. Missing operands propagate. |
| `ratio` | `numerator`, `denominator`, `output`, optional `scale` (default 1). Zero denominators follow `on_invalid`. |
| `log`, `log1p`, `exp`, `ihs` | `input`, `output`; natural log, log of one plus input, exponential, or inverse hyperbolic sine. Log domains are respectively positive and greater than -1. |
| `polynomial`, `interaction` | Polynomial uses `input`, `output`, nonnegative integer `power`; interaction multiplies declared `inputs` into `output`. |
| `standardize` | `input`, `output`, explicit `ddof` 0 or 1, optional grouping `by`, and `reference` filters. Computes mean and SD on the adopted reference observations and applies those values within group. Records actual reference counts, centers and scales; a zero SD follows `on_invalid`. |
| `index` | `inputs`, `weights`, `output`; weighted sum with `missing:"propagate"` by default. `missing:"available"` explicitly uses observed components; `normalize:true` divides by their corresponding weight sum. Component signs and scales are specified through preceding operations and weights. |
| `real` | `input`, positive `deflator`, explicit index `base` and `output`; computes nominal input times base divided by deflator. Define the currency, price base and conversion timing in the variable metadata. |
| `row_id` | `columns`, `output`; creates a unique JSON tuple string from complete declared keys. Original source IDs remain available. |
| `duplicates` | `keys`, `policy`. `error` rejects repeated keys; `identical` removes only fully identical source rows and rejects conflicts; `select` requires complete untied `order_by` columns and explicit `keep:"first"` or `"last"`. Adopt the source version rule before using selection. |
- Calendar operations declare `by:[entity_keys]`, `time` and a base `frequency`.
- Empty `by` declares one series.
- Complete entity-period keys must be unique; every horizon is a calendar distance.
- Use `periods` or `window` for multiples of the base frequency.
- A missing March cannot make February the one-period lag of April.

| Calendar operation | Adopted fields and calculation |
| --- | --- |
| `lag`, `lead` | `input`, `output`, positive `periods` (default 1); exact past/future calendar-key lookup. Absent target cells yield missing. |
| `diff`, `growth` | Same clock/horizon. Difference is current minus lag; growth is `(current / lag - 1) * scale`, with default `scale:1`. Zero bases follow `on_invalid`. |
| `rolling` | `input`, `output`, positive `window`, `stat` (`sum`, `mean`, `min`, `max`), `min_periods` (default window). The window includes the current period and preceding calendar periods. |
| `cumulative` | `input`, `output`, `stat`, optional `start`. Default start is each entity's first observed period, recorded in the reference clock. |
| `baseline` | `input`, `output`, exact baseline `period`, `mode`: `value`, `difference`, `ratio` or `index`. Index scale defaults to 100. A missing baseline remains missing. |
| `exposure` | `input`, optional multiplicative `weight`, `output`, optional calendar `window`; sums the adopted dose/exposure products over that window or cumulative observed history. |
- Rolling, cumulative and exposure operations default to `missing:"propagate"`: missing values and absent in-scope calendar cells produce missing totals.
- `missing:"available"` explicitly selects observed components; rolling additionally enforces `min_periods`.
- Such totals represent observed coverage.
- No omitted period becomes zero.

- `treatment` uses the same clock, `input`, explicit `active_values`, and an `outputs` mapping from requested quantities to column names: `active`, `first_treated`, `event_time`, `ever_observed`, `never_treated`, `not_yet_treated`, `cumulative`, `switch_on`, `switch_off` or `anticipation`.
- `anticipation` is a nonnegative period count.
- `history_start`/`history_end` can extend the required observed range; otherwise the saved bounds are each entity's first and last input periods.
- `never_treated` means all periods within these finite bounds are observed and untreated.
- It is missing for incomplete history.
- `not_yet_treated` includes completely observed untreated histories.
- An observed zero is retained as untreated.

- With default `history:"propagate"`, a missing period before first treatment makes `first_treated` and `event_time` missing.
- Treatment already active at the first observed period has no adoption date unless `initial_state:0` establishes the untreated prior state.
- Explicit `history:"observed"` defines the event clock at first observed active treatment and cumulative duration over observed periods.
- Switch indicators always compare adjacent calendar periods; missing predecessors remain missing.
- The saved record identifies the chosen event clock and history bounds.
- Assignment, receipt, dose and spillover measures use separate declared inputs and definitions.

- `aggregate` declares `by` and `metrics`, mapping output names to `{stat,...}`.
- Statistics are `rows`, `count`, `sum`, `mean`, `min`, `max`, `weighted_mean` or `rate`.
- Ordinary statistics use `input`; weighted means also use `weight`; rates use `numerator` and `denominator`.
- Weighted means and rates require distinct `numerator_output` and `denominator_output`, so their additive components remain in the output.
- Rate is total numerator divided by corresponding total exposure, with optional `scale`.
- Weights/exposure must be nonnegative; zero total exposure gives a missing rate.
- Default `missing:"propagate"` requires complete contributing fields.
- Explicit `missing:"complete"` uses complete value-weight or numerator-exposure pairs for both totals and records usable/source counts.
- `count` counts observed numeric or categorical input values.
- It treats the reader's markers (empty string, `.`, `NA`, `:`) and native nulls as missing; `rows` counts source rows.
- Output names must be distinct from all group keys and other outputs.

- For a single value, `wide_to_long` uses `id:[keys]`, `names_to`, `values_to`, and `columns:{source_column:dimension_label}`.
- `long_to_wide` uses `id`, `names_from`, `values_from`, and `columns:{dimension_label:output_column}`.
- To move values with their status, wide-to-long `columns` instead maps each dimension to paired names, for example `{"2020-01":{"sales":"sales_jan","status":"status_jan"},"2020-02":{"sales":"sales_feb","status":"status_feb"}}`; omit `values_to` and use `names_to:"month"`.
- The inverse uses `values_from:["sales","status"]` and `columns:{"2020-01":{"sales":"sales_jan","status":"status_jan"},...}`.
- Repeated wide cell keys fail.
- Widening requires every declared dimension for each identity; explicit missing/status rows preserve in-scope coverage.
- Neither direction drops missing values or invents observation combinations.

- The common sample is `sample:{id,row_id,filters,complete_cases,require_common}`.
- `id` is a definition identity; `row_id` names a complete unique final-table column.
- Filters run in declared order: `{column,values}` selects membership, or `{column,op,value}` uses `eq`, `ne`, `lt`, `le`, `gt`, `ge`; `in`/`not_in` use `values`, and `missing`/`nonmissing` need no value.
- An optional `reason` labels the condition.
- Missing values fail ordinary comparisons.
- `complete_cases:[columns]` adds explicit nonmissing conditions after these filters.
- All transformations run before selection, preserving the history needed by lags and treatment measures.

- `data-record.json.sample` saves `{id,row_id,row_ids,policy:"explicit",require_common,flow,exclusions}`.
- Sequential `flow` entries retain `step`, `rows_before`, `rows_after`, `newly_excluded_rows` and `cumulative_excluded_rows`.
- `exclusions` retains each condition's failing IDs on the original constructed population, allowing overlapping reasons.
- Those identities are saved once under their reasons; flow stores the corresponding counts.
- Sequential losses plus retained rows equal the constructed count.
- With no sample specification, assembly retains every row and saves grain-derived IDs with `row_id:null`; downstream shared-sample estimation requires an explicit source ID.

- To prepare existing-runner inputs, add the seven adopted research fields `question`, `population`, `observation_unit`, `economic_model`, `mechanism`, `estimand` and `identification`, plus `analyses:[{id,runner:"research"|"causal",specification:{...}}]`.
- Each specification is the existing runner input without `data` or `data_record`, and its `id` column equals `sample.row_id`.
- `research_design.variable_design` verifies roles, timing, adjustment and actual model columns.
- Assembly verifies that every bound column remains in the final table and saves the returned `variable_design`.
- No variable or causal design is selected automatically.
- The final record and canonical analysis table supply the common sample and definitions to the existing estimation, descriptive and saved-result consumers.
- `require_common:true` requires the official fitted ID set to equal the constructed set; other requested fits retain their additional exclusions through that same result contract.

- Assembly writes each declared input to `NEW_DIRECTORY/analyses/ID.json` after saving the final `data-record.json`.
- Run a `research` input with `research.py estimate` or a `causal` input with `research_causal.py run`.
- Each input contains the generated table path and `data_record:{path,sha256}`.
- The consumer verifies both the record and table hashes, the adopted analysis fields and shared row identity before calling the existing official estimator.
- Its result saves `variables` and `data_construction`, including construction sample flow and the correspondence with the official fitted sample.
- The record's specification owns the adopted design; `variable_design` retains its checked column bindings.

- For an adopted analysis-specific population or outcome support, add `sample:{id,filters,complete_cases,require_common}` to that entry in `analyses`.
- The existing sample builder selects from the completed assembly sample, after all variable and history construction.
- Each analysis sample has its own definition ID and retains the parent's `row_id`; an explicitly supplied `row_id` must match it.
- Assembly writes one `NEW_DIRECTORY/analyses/ID/analysis.EXT` in the parent's selected format and `data-record.json`, and binds `analyses/ID.json` to those files.
- The child record retains the original assembly specification, input hashes, variable definitions, transformations and grain, plus `parent_record:{path,sha256}`, `analysis_id`, the adopted `analysis_specification` and its actual sample flow.
- The parent reference retains assembly-level panel and geographic metadata.
- Estimation and description consume the selected record; its population comes from the adopted analysis specification when present.
- Saved results carry both construction membership and any additional official estimator exclusions.

- With assembly-level `sample.require_common:true`, every analysis uses the common record and per-analysis sample declarations are rejected.
- Put the joint eligibility and complete-case columns in that common sample.
- For a separately declared analysis sample, `require_common:true` requires its estimator and descriptive result to retain exactly that selected membership.
- Changes to a sample definition create a new assembly generation through the existing result dependencies.

## Saved descriptive results

- `describe SPEC.json --root ROOT --output NEW_DIRECTORY` calls `modelsummary::datasummary` and `ggplot2` from the adopted R environment.
- It saves `result.json` with display aggregates, definitions, actual row identities, source/specification/code hashes and package versions.
- The gallery reads those saved aggregates.
- It never opens the observation file or invokes this calculation.

- Description projects the columns needed by its variables, eligibility, groups, weights and sampling design.
- R reads the same hash-pinned canonical table directly; the handoff contains its path, selected row IDs and adopted options.
- Numeric observation rows are not serialized into an intermediate JSON or CSV.
- The input reference can be absolute or relative to `--root`, so a shared analysis table remains at its existing location.
- Survey inference retains all positive-weight design records and treats the selected sample as a domain.

- The specification names stable `result_id` and `specification`, a hash-pinned CSV, Parquet or Arrow IPC `data:{path,sha256}`, unique complete `row_id`, `population`, `denominator`, and `variables:[{name,unit,label?}]`.
- A variable can name a source `status` column with its adopted `observed_statuses`.
- Observed zero and missing or suppressed values retain their distinct counts.

- For a constructed sample, supply `data_record:{path,sha256}` and `variables:["COLUMN",...]`.
- The same binding resolves the hashed table, population, observation unit, row identity and variable units.
- An omitted `sample` uses the constructed sample ID with available-case description on that already selected table.
- Preserve the requested period, denominator, weights and quantile convention.
- `require_common:true` also compares the actual descriptive IDs with the construction IDs.
- The saved descriptive result carries the same `variables` and `data_construction` into the gallery and Writing.

- `sample` supplies `id` and `policy`: `available-case` uses each variable's observed values; `complete-case` requires all selected variables and positive usable weights; `fitted` selects the exact IDs in the hash-pinned `result:{path,sha256}` at `ids_key:[...]`.
- Optional `filters:[{column,values}]`, `period:{column,values,label}` and `group:{column,levels,missing:"include"|"exclude"}` implement the adopted eligibility.
- A fixed period can also be a string.
- Fitted membership must remain identical after all filters.
- The result saves sequential sample-flow counts, separately named newly and cumulatively excluded rows, and the retained row IDs.

- Use `weights:{kind:"none"}` for equal observation weights.
- Weighted specifications supply `kind` (`frequency`, `population`, `reliability`, `probability` or `analytic`), `column`, `normalization` (`none` or `sum_to_n`) and `variance` (`unbiased` or `ML`).
- Frequency weights retain integer counts; reliability and analytic weights normalize descriptive dispersion to the usable count; population and probability-weight dispersion use `ML`.
- Probability weights retain their scale and use the weighted ECDF quantile convention `i/n`.
- Weighted means use `stats::weighted.mean`; standard deviations and quantiles use the selected `Hmisc` conventions.
- Save quantile `probabilities` with an R `type` from 1 to 9 for unweighted data, or an Hmisc `method` (`quantile`, `(i-1)/(n-1)`, `i/(n+1)` or `i/n`) for weighted data.

- The primary saved table contains mean, standard deviation, median, requested quantiles, minimum, maximum, usable counts, missing/zero counts and weight sums for the whole selected sample and each declared group.
- `observation_unit` names the analysis grain; `entity` names a complete identity column for entity counts alongside observation counts.
- A period column also saves the full table by period in `display.by_year`.
- Group-period trends reuse those definitions.
- Source row IDs and variable-specific usable row IDs stay in the saved sample record.

- An explicit `balance` selects the contrast and inference, for example `{"control":"0","treated":"1","inference":{"method":"welch","confidence_level":0.95},"smd":{"denominator":"pooled_sd"},"plot_smd":true}`.
- `welch` calls `stats::t.test` for unweighted or integer-frequency samples.
- `estimatr` calls `estimatr::difference_in_means` for an unweighted design and accepts declared `clusters` and `blocks` columns.
- Probability weights select `survey` with `ids`, optional `strata`/`fpc` column lists and an explicit `nest` boolean; `ids:[]` specifies independent sampling.
- `analytic_wls` calls `stats::lm` with adopted inverse-variance weights.
- `none` saves descriptive contrasts only.
- The result records both unadjusted `mean_difference` and official estimator `difference`, saved SE, p-value, degrees of freedom and interval endpoints.
- SMD uses the unadjusted mean difference and the adopted `pooled_sd` or `control_sd`.
- The balance specification requires `observation_unit` and distinct named group levels.
- Existing specifications without `balance` retain their group-summary display and add no inference.

- Optional `distributions` maps variable names to any of four explicit specifications: `histogram:{breaks:[...],closed:"left"|"right"}`, `density:{bw:NUMBER|"nrd0",adjust:NUMBER,n:INTEGER}`, `ecdf:{}`, and `box:{coef:NUMBER}`.
- Official ggplot2 layer data supplies bin edges/counts, density coordinates, unweighted ECDF coordinates and box statistics.
- Weighted ECDF uses `Hmisc::wtd.Ecdf`; weighted box statistics use ggplot2's quantreg dependency.
- Only aggregate coordinates, five box statistics and outlier counts enter display rows.
- Bin closure, density settings, weight convention, groups, units and sample definitions remain in display metadata.
- Changing them requires regenerating the adopted descriptive result.

- The existing R initialization selects the project's library.
- A research stage's R companion supplies the exact interpreter and startup options used by `describe`; an explicit `--rscript` must match that interpreter.
- Standalone execution uses `Rscript --vanilla`, with `--rscript` selecting another executable.
- The result retains the invoked options and runtime/package versions.
- Python UI/render dependencies are pinned in `requirements-research.txt`.

Official interfaces: [datasummary](https://modelsummary.com/man/datasummary.html), [datasummary_balance](https://modelsummary.com/man/datasummary_balance.html), [ggplot2 layer data](https://ggplot2.tidyverse.org/reference/ggplot_build.html), [histograms](https://ggplot2.tidyverse.org/reference/geom_histogram.html), and [Hmisc weighted statistics](https://search.r-project.org/CRAN/refmans/Hmisc/html/wtd.stats.html).
