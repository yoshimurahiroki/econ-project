# Implementation notes

Read the section for the requested operation.

## Acquisition

Use the official endpoint and implement its pagination, timeout and rate handling. Keep credentials in environment variables. Preserve the source version and query. Inspect source records to establish the requested coverage. Separate acquisition from transformation so saved inputs can be reused.

## Computation

Run bulk joins, filters, aggregations and transfers in the existing query or vectorized engine. A path such as `INSERT … SELECT` must specify sample selection, columns and options. Transfer the small result sets and selected fields consumed by the next operation. Use chunking or streaming for operations that require sequential access, including file hashing.

## Prediction

Match the target, available information and training/test split to the prediction setting. Fit preprocessing on training data. Evaluate the metric that defines performance for the requested prediction task. Match leakage and calibration checks to the validity question.

## Numerical methods

Define the target, parameters, seeds and convergence criterion. Use residuals or an analytic special case to resolve numerical error in the result. Report simulation uncertainty for simulation estimates.

## Replication

Trace each requested exhibit to its data, code and execution command. Preserve access instructions, versions and seeds. Compare reproduced values with the source using the tolerance for that quantity. Apply the journal's requirements to a requested submission.
