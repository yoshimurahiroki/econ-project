# Data preparation, descriptive statistics and figures

From received files to clean tables, analysis variables, descriptive tables and figures. Estimation and identification are in the [empirical procedure](empirical.md). Work through P1 to P9 in order; every step runs in code, checks its output, and records the check in section 5 of the worksheet. Sources of the rules: World Bank DIME Analytics Data Handbook (chapters 3–7) and *Coding for Economists* (data and visualisation chapters).

## P0. Rules without exceptions

1. **Code only.** Files and cells are never edited by hand; received files are never overwritten.
2. **Four layers.** `data/raw/` (received files and `research_data.py acquire` snapshots, read-only) → `data/intermediate/` (types and structure fixed, meaning unchanged, one table per observation unit) → `data/analysis/` (analysis variables and sample) → `outputs/` (tables, figures, `outputs/qa/` checks). `research_data.py` writes each build to a new directory inside its layer (`data/analysis/<name>-<version>/`). Each layer is rebuilt from the one before by one command.
3. **Unit first.** Before any transformation, write what one row is and its key, for every table.
4. **Data never decide research choices.** Imputation, deletion of outliers or impossible values, winsorizing, value corrections, deletion of records, choice of controls, aggregation rules, base years and weights come only from the worksheet's section 4 or from the user ([user]), and are written before the variable's values are inspected. Imputation, outlier deletion, winsorizing and corrections additionally require [user] or the source's own documentation (codebook, provider's correction list). Without them the step stops with status BLOCK and the question goes to the user.
5. **Measured values stay.** Every derived value is a new column; the original column is kept.
6. **Every step is checked.** Run → check (assert, counts) → record → next step. A failed check stops the dependent steps.
7. **No invented results.** A check that did not run is NOT_RUN, never PASS. Without data, write the specification and the checking code; produce no statistics.
8. **Confidential data stay out.** Names, addresses, free text, exact locations and identifier crosswalks go to a restricted folder and never into outputs or logs.

| Status | When | Action |
| --- | --- | --- |
| PASS | the check meets the specification | next step |
| FLAG | values computable but need review (out-of-range, extreme) | keep the values, record count and keys, continue with non-destructive steps only |
| BLOCK | missing or duplicate keys, unexpected row growth, information lost in a type conversion, an unspecified research choice, a confidentiality risk | stop the step and its dependents, record it, ask the user |
| NOT_RUN | data or software unavailable | record as not run |

A BLOCK or NOT_RUN fills the worksheet as follows: section 5 lists the commands run, the failed check and its status; section 6 has `Decision: none (BLOCK at P<n>: <check>)`, `Switches when: the user decides <question>`, `Specification changes: none`; section 7 has `Deliverable and its path: BLOCK report to the user (status, open decision, rebuild command)`; the header has `Status: open` and `Next action: user decision on <question>`.

Order of authority when sources disagree: the user's specification and worksheet section 4 > questionnaire, official codebook and provider definitions > verified metadata > values in the data. A conflict with a higher source is BLOCK.

## P1. Inventory and audit of received files

1. List every file in `data/raw/` with size, format and SHA-256; record source, release or vintage, and access date ([research data](research-data.md) for acquisition).
2. Read with declared options: encoding, separator, decimal and thousands marks, header row, sheet. Identifiers, codes and postal or industry codes are read as strings (leading zeros kept); automatic type guessing is not trusted. Excel: the sheet is named, never "the first sheet".
3. Run the audit template on each table:

```sh
cp skills/econ-data/templates/data_audit.py work/<topic>_audit.py   # set READ, KEY, CODEBOOK, NUMERIC
python3 work/<topic>_audit.py data/raw/<file> outputs/qa/<name>_audit.json
```

It records shape, types, missing and zero counts, ranges and quantiles, codes outside the codebook, failed numeric conversions and key problems, and returns PASS, FLAG or BLOCK. A BLOCK stops P2 onward for that table.

## P2. Types and codes

| Meaning | Type | Rule |
| --- | --- | --- |
| identifiers, postal, industry and firm codes | string | never numeric; leading zeros kept |
| amounts, quantities, shares | numeric | unit, denominator and decimal mark known; any failed conversion is BLOCK |
| integers that can be missing | `Int64` | only when every value is integral |
| binary indicators | boolean or `Int64` | missing stays missing, never 0 or False |
| categories | categorical | every level and its order from the codebook; an unknown level is BLOCK |
| dates and periods | datetime or Period | input format, calendar, time zone and frequency declared; `01/02/2020` without a declared format is BLOCK |
| free text | string, restricted folder | never in outputs |

- Numeric parsing uses `strict_numeric` from the audit template: documented missing codes become missing, any other failure stops the run. `errors='coerce'` without counting failures is forbidden.
- Codes such as 99, -99, "Refused", "Don't know" become missing only when the column's codebook says so; the reason (refused, not applicable, not observed) is kept in a separate column.
- Zero and missing, non-response and not-applicable, zero sales and unreported sales stay distinct.
- Renaming keeps a one-to-one map from original to new names. Case, spacing and Unicode normalization are tried in a comparison column first and checked for collisions between distinct codes.

## P3. Keys and tidy tables

1. One column per variable, one row per observation, one table per observation unit; the key is unique and complete.
2. Duplicate keys: decide whether rows are different periods, versions, transactions or submissions (extend the key) or true duplicate ingestion (remove only when the submission ID or the provider establishes it). `drop_duplicates()` without that evidence is forbidden. In `assemble`, `duplicates` with policy `identical` removes only verified identical rows; policy `select` (keep the first or last version) requires the provider's version rule or [user].
3. Wide to long: one concept across years becomes `id, year, value`; repeated sub-units (children, transactions) become their own table. Long to wide only for display, after checking `(index, columns)` is unique; `pivot_table` with an aggregation function on duplicated cells is forbidden.
4. After every reshape compare row counts, key uniqueness and non-missing cell counts with the input; reverse the reshape and compare where possible.
5. Implicit missing rows (a unit–period absent from the table) are made explicit only against a documented frame of units and periods, flagged `observed=False`, and never filled with zero.

## P4. Quality checks and corrections

1. Check, in priority order (keys, treatment, outcome, sampling, weights, time; then main covariates; then the rest; every column gets type, missing, uniqueness and range checks):
   - completeness: expected units and periods against received ones, by wave, region and period;
   - logic: start ≤ end, components sum to totals, hierarchy consistency;
   - ranges: definitional domains (shares in [0,1], non-negative amounts);
   - distribution: quantiles, concentration at zero, heaping;
   - missingness by variable, group and period, with its reason.
2. Fixed thresholds: missing keys 0, duplicate keys 0, failed type conversions 0, unapproved deletions 0. No automatic rule deletes rows by missing share or extremeness; an extreme value is FLAG, investigated, never removed for being extreme.
3. A value is corrected only when a questionnaire, original record or provider correction establishes the true value. Corrections run from `data/corrections.csv` (`key, variable, old_value, new_value, evidence, date`); each correction asserts that `old_value` matches the current value.

## P5. Joins, appends and aggregation

1. Write each table's unit and key, then the relationship: `one_to_one`, `many_to_one` or `one_to_many`. An unplanned many-to-many is BLOCK.
2. Join through `checked_merge` from the audit template, or the `assemble` joins of `research_data.py`, which require the same declarations. Both check missing keys first (pandas matches missing keys to each other), validate the relationship, record matched, left-only and right-only counts, and stop on row growth in a left join.
3. The default is a left join from the population table. An inner join that drops units needs a [user] or section-4 decision; left-only and right-only keys are listed and classified (malformed key, missing partition, out of population).
4. Columns suffixed `_left`/`_right` are resolved by meaning; `combine_first` or keeping one side silently is forbidden.
5. Appends require the same definition, unit, currency and questionnaire version for same-named columns; a `source_file` or `wave` column is added; output rows equal the sum of input rows.
6. Aggregation: stocks take the end-of-period or stated-date value, flows the period sum, rates and prices the weighted mean under a stated weight. Sums use `min_count=1` so an all-missing group stays missing. The output key is checked unique, and totals are reconciled with their components.

## P6. Analysis variables

Each variable has a definition line in the `assemble` specification (`definitions`: unit, definition, version, source fields, role) before it is built. In `assemble`, these options require worksheet section 4 or [user]: `on_invalid: "missing"` (turns unparsable values into missing), `replace: true` (overwrites a column), `log1p` and `ihs` transformations, and every sample `filters` or `complete_cases` rule.

| Construction | Rule | Check |
| --- | --- | --- |
| indicator | 1 if true, 0 if false, missing if unknown | missing never becomes 0 |
| ratio, per capita | numerator / denominator | denominator > 0; both on the same population and period |
| log | ln(x) for x > 0 | x ≤ 0 is missing; log(x+1) only from section 4 or [user] |
| real values | nominal × CPI_base / CPI_t | same country, series, base year and timing |
| currency conversion | value × rate | rate direction, date and market or PPP basis recorded |
| standardization | (x − mean_ref) / sd_ref | reference population and period fixed and recorded |
| change, growth | x_t − x_{t−1}; 100(x_t / x_{t−1} − 1) | adjacent periods only (`adjacent_lag`); base zero is missing |
| interaction | D × X | timing, coding and missingness of both |
| winsorizing | at stated quantiles of a stated population | [user] only; original column kept, changed count recorded |

Panel rules: `(id, period)` unique; periods as `Period` at one frequency; fiscal and calendar years kept apart; lags only between adjacent periods; treatment start, event time and cohort from the design, never from outcomes; no future values in features or fills.

Variable selection: keep identifiers, time, design variables (assignment, outcome, treatment, weights, strata, clusters) and the pre-specified covariates from section 4. Post-treatment variables never enter as controls; the outcome never enters as a regressor; no control is chosen by its correlation, p value or missing share.

## P7. Descriptive tables

Run through `research_data.py describe` ([descriptive quantities](implementation-descriptive.md)) or the project's saved code; every table states its population, period, unit and N.

| Table | Content |
| --- | --- |
| A. Data overview | per source: rows, units, periods, first and last period, key duplicates, join match rate |
| B. Missingness and quality | per variable: N total, N valid, N missing, share missing, N zero, N negative, N flagged; by group and period |
| C. Numeric variables | N, mean, SD, min, p1, p5, p25, median, p75, p95, p99, max, with the unit |
| D. Categorical variables | count and share per level including missing; the denominator stated |
| E. By design group | N, mean and SD by treatment and control, baseline and each follow-up |
| F. Panel structure | units, periods, distribution of observed periods per unit, missing unit–periods, share balanced |

Rules: SD with divisor n − 1; a single-observation group has missing SD; group means use the group's non-missing values; weighted statistics only with a declared weight and its meaning, computed as `sum(w*x)/sum(w)` on valid pairs; unweighted N beside weighted statistics; survey standard errors only through the survey design. Self-checks before saving: valid + missing = total; category counts sum to the denominator; mean and quantiles lie within [min, max]; a 0/1 variable's mean equals its share of ones; group totals reconcile with the overall total.

## P8. Figures

| Purpose | Figure | Rule |
| --- | --- | --- |
| distribution of one variable | histogram | bins fixed; skewed variables on a log axis in a separate figure |
| distributions by group | box or violin plot | N per group shown; outliers shown |
| counts or shares of categories | horizontal bars from zero | denominator stated; order from the codebook or by frequency |
| one quantity over time | line | time ascending; unobserved periods not connected |
| two continuous variables | scatter (transparency or hexbin when dense) | N of complete pairs |
| group means or rates | points with intervals | interval from a design-valid calculation |
| composition | 100% stacked bars | same denominator across groups; missing as its own category |
| levels on different scales | separate panels | no dual vertical axes |

Before drawing: build the plotting table at its stated unit and count its N; check types and missingness of x, y, group, date and weight; never add points to an empty or tiny group (record the group as empty instead); log axes on positive values only, with excluded zeros and negatives counted. One colour, marker and order per group across all figures; no 3D, pie charts or ornament. Exploratory figures go to `outputs/figures/exploratory/` and carry N, unit, population and period in their title; final figures go to `outputs/figures/final/`, are generated from saved results through the [result artifacts](../../econ-writing/references/result-artifacts.md) producers, and follow the writing profile. After saving, check that each file exists, is not empty, and has labelled axes and legend.

## P9. Release gate and report

Release only when all hold:

- G0 raw hashes recorded and raw files unchanged;
- G1 every table's unit and key written; keys unique and complete;
- G2 every type change, recode and correction reproducible from the original values;
- G3 every reshape, join, append and aggregation reconciled (rows, matches, values);
- G4 every final column defined (meaning, unit, construction, missing treatment, role);
- G5 sample definitions and N agree across code, tables and figures;
- G6 one command rebuilds every output from raw files, with package versions and seeds recorded;
- G7 no confidential value in outputs or logs.

| Error | Forbidden shortcut | Required action |
| --- | --- | --- |
| duplicate keys | keep the first row | establish the unit, period or resubmission |
| row growth after a join | drop duplicates afterwards | fix keys and relationship; validate the join |
| unmatched keys | switch to an inner join | list and classify left-only and right-only keys |
| failed numeric or date parsing | `errors='coerce'` and continue | count failures, fix the parsing rule |
| impossible or extreme values | set to zero, delete or winsorize | FLAG, check the source, correct only with evidence |
| missing periods | copy the previous value | compare with the frame; mark unobserved |
| required variable missing | use a similarly named column | check codebook and provider; BLOCK until resolved |
| empty figure or tiny N | add placeholder points | report the empty group and its N; skip the figure |
| missing package or data | fabricate output | NOT_RUN with the missing dependency |

A fix reruns its step and every later step from the raw files. The checks, changes (corrections, recodes, constructed variables, excluded records with their rule) and inputs are saved in `outputs/qa/`. The report to the user gives only: the status (PASS, FLAG, BLOCK or NOT_RUN), the output paths, the open decisions with the question each needs, and the rebuild command.
