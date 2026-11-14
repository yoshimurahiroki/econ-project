## Specification and result

- Use `python skills/econ-data/scripts/research_causal.py run SPEC.json --output RESULT.json`.
- The shared specification binds `method`, canonical `data` or hashed `data_record`, unique nonempty `id`, `outcome`, `regressors`, `endogenous`, `instruments`, population/period/unit, estimand, identification, assignment, inference and method-specific `options`.
- Relative paths resolve against the specification.
- CSV, Parquet and Arrow IPC share the existing projected reader; preserve textual IDs and the selected method's observation rule, including unobserved outcomes for selection models.

- Use the selected method's body and selector-produced execution specification for its columns, inference type and options.
- The exact shared fields are owned by `research_design.RUN_FIELDS`, common/method option validation by `research_causal.run`, staggered-DID forwarding by `_staggered_did`, and DoubleML inputs by `_doubleml`.
- The [core method reference](basic.md#core-causal-and-empirical-methods) owns HDFE/IV/RDD and their parameter meanings; the selected extension body owns its specialized interface.
- The common contract does not enumerate every method's parameters.
- Column lists contain distinct nonempty names and roles; numeric analysis columns are converted at the estimator boundary while IDs remain text.
- Complete-case selection includes adopted weights and effect/cluster keys; selection models retain their unobserved rows under their own score.
- Python matrix estimators require numeric analysis columns; native R functions own factor encoding.
- Regression includes an intercept unless fixed effects or differencing absorb it.
- Preserve the adopted coefficient scale.
- Execution validates the actual input/interface before fitting.

- Results retain engine versions, named estimates/covariance/inference, fitted/excluded IDs, row/sample counts, diagnostics, definitions, input hashes and semantic `statistics` with units.
- Method contracts own their native quantities and row mapping; shared atomic publication owns saving.
- The existing `research.py estimate` retains its persisted OLS/2SLS/PLR/two-period-DID formats; new DoubleML selections use the causal runner.
