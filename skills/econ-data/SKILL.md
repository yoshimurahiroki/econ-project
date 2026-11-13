---
name: econ-data
description: Acquire, transform, estimate and reproduce economic data and results; implement and simplify research code through its existing owners and execution paths. Execute BLP, NFXP, MPEC, structural GMM, dynamic games and equilibrium counterfactuals. Evaluate Japanese and global equities with free financial data, sustainable cash flow, valuation and news updates.
---

# Research data

## Purpose and input

1. **Output: execution target; consumer: operation selection.** Recover the requested data operation or code change, adopted specification, source documentation and saved results.

## Select the operation

1. **Output: executable procedure; consumer: producer.** Select `execute` for data/calculations/code or `equity` for valuation. Read the registry-selected [workflow](references/workflow.md) and implementation sections. Resolve an unknown data/code operation with `python scripts/route_registry.py read data-implementation.select-the-operation-specific-rules`. Start a bounded change at its affected stage; a new pipeline uses [source to analysis](references/implementation-data.md#source-to-analysis).

## Deliver the data operation and its economic meaning

1. **Output: data/code/result; consumer: analysis or artifact.** Return actual inputs, producing operation, location and required verification. Carry population, period, units, denominator, fitted specification, effective engine and inference with quantities.
2. **Output: economic answer; consumer: user.** Use econ-writing:explain for a requested explanation; apply PROSE's selection and finish steps to the final result.

<!-- BEGIN GENERATED MODES -->
## Registered operations

- `execute`: Acquire, transform, join, calculate, estimate or change research data and code.
- `equity`: Evaluate Japanese, US and overseas equities from public filings, IR and market observations; estimate competition, compute sustainable cash flows, reverse valuation, after-tax investment decisions and news-driven changes.
<!-- END GENERATED MODES -->
