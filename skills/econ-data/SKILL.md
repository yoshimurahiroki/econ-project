---
name: econ-data
description: Acquire, transform, estimate and reproduce economic data and results; implement and simplify research code through its existing owners and execution paths. Execute BLP, NFXP, MPEC, structural GMM, dynamic games and equilibrium counterfactuals. Evaluate Japanese and global equities with free financial data, sustainable cash flow, valuation and news updates.
---

# Research data

This skill carries step 5 of the [economist's procedure](../../runtime/ECONOMIST.md): run the design from the worksheet with the existing scripts.

0. **Procedure.** Empirical work follows the [empirical procedure](references/empirical.md): estimand, data audit, raw facts, design by decision rules, the specification ladder (`templates/estimate_ladder.py`), diagnostics and interpretation, each step filled in the worksheet.
1. **Data.** Clean, reshape, join, construct variables, describe and plot through the [data preparation procedure](references/data-preparation.md) (audit template `templates/data_audit.py`; P0 rules without exceptions); acquire through [research data](references/research-data.md).
   Rules without exceptions: everything runs in code and received files are never edited; the unit and key of every table are written first; imputation, deletion of outliers or records, winsorizing, value corrections, controls, aggregation rules, base years and weights come only from worksheet section 4 or [user] (imputation, outlier deletion, winsorizing and corrections only from [user] or the source's documentation), never from the data; every join declares its relationship and is checked for missing keys, matches and row counts; derived values are new columns; a failed check stops the dependent steps with status BLOCK and the question goes to the user.
2. **Estimation.** Run the selected method from the [implementation table](references/implementation-engines.md) with the matching script: `scripts/research_causal.py` (and `research_causal.R`, `research_rct.R`), `research_markets.py`, `research_dynamic.py`, `research_macro.py`, `research_macro_extended.py`, `research_dsge.py`, `research_numerics.py`. Specification fields and calls are in [implementation calls](references/implementation-calls.md); worked runs in [implementation examples](references/implementation-examples.md).
3. **Projects.** Multi-stage work runs through `python3 harness/research.py --root . research.json` ([research runner](../../harness/research.md)).
4. **Equity valuation.** The `equity` mode follows [equity](references/equity.md).
5. **Return.** Save results with their inputs, sample, units, estimator and inference; write the estimates and diagnostics into the worksheet for step 6.

The general procedure is in the [data workflow](references/workflow.md).

<!-- BEGIN GENERATED MODES -->
## Registered operations

- `execute`: Acquire, transform, join, calculate, estimate or change research data and code.
- `equity`: Evaluate Japanese, US and overseas equities from public filings, IR and market observations; estimate competition, compute sustainable cash flows, reverse valuation, after-tax investment decisions and news-driven changes.
<!-- END GENERATED MODES -->
