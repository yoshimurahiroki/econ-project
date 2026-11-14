# Execution procedure

Step 5 of the [economist's procedure](../../../runtime/ECONOMIST.md): turn the adopted design into saved results. Work through the steps in order; each ends with a block in section 5 of the worksheet `work/<topic>.md`. A result that is not saved to a file with its inputs does not exist for later steps, and numbers in any answer, table or slide come only from saved results.

Three rules hold throughout:

1. **Existing paths first.** Use the existing scripts, runners and official package calls. New code covers data preparation and case-specific models that no script covers.
2. **Print before trusting.** Every step prints counts, keys, ranges and diagnostics, and the worksheet records them.
3. **One source of numbers.** Tables, figures and text read the same saved result file.

## X1. Kind of execution

Pick the first row that matches.

| Work | Procedure | Entry |
| --- | --- | --- |
| Reduced-form estimation (DiD, RD, IV, RCT, panel) | [empirical procedure](empirical.md) | `templates/estimate_ladder.py`, `scripts/research_causal.py run` |
| Structural estimation and counterfactuals | X4 below and [structural implementation](implementation-structural.md) | `scripts/research_markets.py`, `research_dynamic.py`, `equity.py fit` |
| Model simulation without data | [modeling step by step](../../econ-design/references/modeling.md) | `econ-design/templates/simulate_model.py` |
| Macro and DSGE calculation | X4 below | `scripts/research_macro.py`, `research_macro_extended.py`, `research_dsge.py` |
| Data acquisition and construction only | X2, X3 | [research data](research-data.md) |
| Descriptive statistics | X3 and [descriptive choices](implementation-descriptive.md#choose-descriptive-statistics-from-the-question) | — |
| Power, minimum detectable effect, estimator simulation | X5 | `scripts/research.py power` |
| Equity valuation | [equity](equity.md), [valuation models](equity-models.md) | `scripts/equity.py` |
| Code change in an existing analysis | X6 and [implementation rules](implementation.md) | the existing entry |

```
Kind of execution:   <row>
Entry command:       <command>
```

## X2. Source to variables

Fill one line per variable before writing any cleaning code:

```
<variable>: source file and field, population, observation unit, period, unit, numerator / denominator,
            timing, treatment of missing / suppressed / censored values
```

Rules:

- Read the source documentation for each field; record its version and the passage that defines the field.
- Keep observed zeros apart from missing, suppressed and censored values; a suppressed amount never becomes zero.
- Keep amounts due and paid, levels and changes, conditional and population targets in their adopted roles.
- When the intervention changes reporting or detection, use a source or stage that responds differently, so recording and the outcome can be told apart.

## X3. Shared tables and the analysis sample

1. Clean each source once, through its `assemble` stage, into one table per grain (household, firm, household-month); keys are complete and unique, joins are declared, and `data-record.json` stores source, version and units ([shared tables](research-data.md#shared-tables-across-sql-python-r-and-julia)).
2. Build the analysis variables, weights and histories from the shared tables, then the analysis sample once, with groups formed from pre-treatment information.
3. Print and record the sample accounting:

```
Rows in source -> after each restriction (rule: count) -> analysis sample
Unique keys:            yes / duplicates and their treatment
Treated / control:      counts by period
```

Before: "Each estimator parses the household and programme files." After: "Build household, programme-month and household-month tables once and join their saved keys for each analysis."

## X4. Estimation and solution

1. Match the adopted parameter to the official call in the [implementation table](implementation-engines.md#estimator-engine-and-algorithm-selection); carry sample, weights, fixed effects and covariance into the call. A feature the package lacks is implemented only after confirming it is missing.
2. Structural work: estimate the primitives once, then solve baseline and intervention from the same fitted primitives; save prices, quantities, policies, profits and welfare for each scenario together.
3. Multi-stage projects run through `python3 harness/research.py --root . research.json`, which binds sources, scripts, environment and specifications and reuses stages whose inputs are unchanged ([research runner](../../../harness/research.md)).
4. Record in the worksheet:

```
Command:                <command and arguments>
Saved result:           <path>
Package and version:    <name version>
Convergence / residual: <value against tolerance>
Diagnostics:            <the diagnostics required by the design>
Seed:                   <seed>
```

## X5. Power and simulation

Match the data-generating process, assignment, dependence and test to the estimand. `research.py power` covers the two-arm Gaussian individual and cluster designs; other designs simulate their own data-generating process with the adopted estimator. Record the minimum detectable effect against the decision threshold.

## X6. Changing an existing calculation

1. Locate the entry, specification, source documentation and saved result of the calculation.
2. Trace the change through keys, joins, sample, weights, formula and interface to every consumer ([compare changed calculations](implementation.md#compare-changed-calculations)).
3. Rebuild the affected stages through the runner; display-only changes reuse the saved result.
4. Record the old and new value of every affected quantity.

## X7. Specification search

Freeze the target, population, sample, evaluator, inference and the discovery, validation and holdout roles before searching. Run the declared finite grid, keep the failed candidates and their returns, and execute the selected branch. Predictive loss alone does not select a causal specification; the identifying restriction and the diagnostic comparison do.

## Hand-off

Section 5 of the worksheet lists every command, saved file, version, convergence value and diagnostic. Step 6 reads the saved results against the predictions of section 3.
