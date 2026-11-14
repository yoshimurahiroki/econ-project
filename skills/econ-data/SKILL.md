---
name: econ-data
description: Acquire, transform, estimate and reproduce economic data and results; implement and simplify research code through its existing owners and execution paths. Execute BLP, NFXP, MPEC, structural GMM, dynamic games and equilibrium counterfactuals. Evaluate Japanese and global equities with free financial data, sustainable cash flow, valuation and news updates.
---

# Research data

This skill carries step 5 of the [economist's procedure](../../runtime/ECONOMIST.md): run the design from the worksheet with the existing scripts.

1. **Data.** Acquire and build tables through [research data](references/research-data.md) and [source to analysis](references/implementation-data.md#source-to-analysis).
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
