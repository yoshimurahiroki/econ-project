# Implementation checks

## Acquisition
Verify endpoints and authentication. Use environment variables for secrets, timeouts, bounded retries, pagination and rate limits. Record query, date, version, schema and source checksums when needed. Separate downloads from transforms. Inspect records before asserting coverage.

## Computation
Use existing rv and Pixi conventions. Check indexes, factor baselines, weights, clustering and units. Choose package APIs from the identified design and current official documentation. Use column projection, chunking or database execution when data size warrants it. Preserve locks during deliberate dependency changes.

## Prediction
Record target, prediction time, labels and information available then. Split at the person, cluster or time level required by deployment. Fit preprocessing within training folds. Check leakage, imbalance, calibration, benchmarks and decision loss. Intervention effects require intervention evidence.

## Numerical methods
Specify the data-generating process, target truth, parameter grid, replications, seeds and convergence criteria. Report Monte Carlo uncertainty for simulation summaries. Check analytic special cases and numerical residuals. Separate numerical error from sampling uncertainty.

## Replication
Map each exhibit to inputs, entry point and command. Record software versions, seeds, path configuration, access instructions and expected outputs. Run from a clean process. Compare reproduced values with their sources using documented tolerances. Preserve data-use conditions. Verify journal requirements when the submission task invokes them.
