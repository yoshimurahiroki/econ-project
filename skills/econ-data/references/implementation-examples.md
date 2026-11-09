# Worked data operations

Select the required section through the [implementation index](implementation.md#select-the-operation-specific-rules). Read its complete body and registered prerequisites before applying it.

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
