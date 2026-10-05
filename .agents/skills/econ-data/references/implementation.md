# Implementation notes

Use only the section needed for the task. Repository minimum-verification rules apply throughout.

## Acquisition
Use the official endpoint, required pagination, a timeout and appropriate rate handling. Keep credentials in environment variables. Preserve the source version and query needed to reproduce the data. Inspect relevant records before making coverage claims. Separate acquisition from transformations when that permits reuse.

## Computation
Use existing package APIs and dependency managers. Keep sample selection, column names and estimation options explicit. Check only the changed operation's consequential failure risk. Use projection, chunking or database execution when the actual data requires it.

## Prediction
Align the target, available information and split with the prediction setting. Fit preprocessing in training data. Evaluate the metric needed for the intended decision; inspect leakage or calibration when it determines validity.

## Numerical methods
Define the target, parameter choices, seeds and convergence criterion. Inspect numerical residuals or an analytic special case when needed to distinguish numerical error from the claimed result. Simulation studies report uncertainty from the simulation.

## Replication
Trace each requested exhibit to data, code and the execution command. Preserve access instructions, versions and seeds. Compare the requested reproduced values using the relevant tolerance. Check journal requirements for an actual submission task.
