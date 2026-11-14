# Numerical calculation and computational resources

Use for numerical work: solvers, convergence on the original equations, derivatives, quadrature and simulation, and their tolerances.

Contents:

- [Computation](#computation)
- [Backend and algorithm changes](#backend-and-algorithm-changes)
- [Exact row compression](#exact-row-compression)
- [Resampling multiplicities](#resampling-multiplicities)
- [Parallel tasks and random streams](#parallel-tasks-and-random-streams)
- [Measured performance and memory](#measured-performance-and-memory)
- [Numerical methods](#numerical-methods)
- [Power calculation inputs](#power-calculation-inputs)

## Computation

Run relational joins, filters and aggregations in the existing query or vectorized engine; use iteration for a genuine sequential dependency or unsupported operation. Push selection, projection and valid aggregation toward the source before collection. A path such as `INSERT … SELECT` must specify sample selection, columns and options. Materialize the fields and rows the next operation needs. Use a whole-frame calculation when its peak working set fits the available budget; account for joins, sorting, design matrices, copies, conversion and writer buffers rather than stored file size alone. Choose chunking, streaming or an out-of-core engine when that budget would be exceeded, and preserve cross-chunk groups and sequential state. Carry the resulting object through the requested calculation or exhibit.

For file-based lazy work, start with a scan that permits pushdown. When a memory bound matters, inspect the plan for unsupported streaming operators, growing aggregation state and in-memory fallbacks; use a supported sink when collecting the final result would exceed the budget. Check partition schemas before combining them. Use distributed execution when the existing runner requires it or measured resource needs exceed a suitable single-machine path, accounting for transfer and coordination costs.

When a result combines heterogeneous weights, probabilities or nonlinear transformations, compute the defined object at its relevant unit before aggregating. Preserve the joint distribution needed by products and ratios.

## Backend and algorithm changes

Before switching a backend or representation, match the complete [estimator contract](implementation-engines.md#estimator-engine-and-algorithm-selection). Choose among eligible algorithms using the design's sparsity, fixed-effect structure, conditioning, precision and convergence requirements. When a backend adapts options, retain the effective algorithm, precision, device, stopping rule and consequential fallback in the existing run record. Compare those effective settings before attributing changed numerical results or runtime to the backend. A balanced-panel shortcut does not establish equivalence for an unbalanced panel.

## Exact row compression

When repeated design rows suggest compression, establish sufficient statistics for both the estimator and its requested inference before discarding rows. Preserve the identical sample, complete encoded design, weight domain, cluster identity and required moments. Coefficient equality alone does not establish covariance, degrees-of-freedom, prediction or resampling equality; a squared grouped score generally differs from a sum of squared individual scores. Do not discretize regressors to obtain compression without an authorized specification change. Label each step exact aggregation or approximate optimizer, and retain its convergence criterion.

## Resampling multiplicities

For resampling with replacement, preserve each sampled unit's multiplicity; set membership loses repeated draws. A cluster draw must carry its repetitions through joins and weighted moments, with draw-specific identities where the calculation requires separate copies. Uniform sampling of unequal compressed cells is not an individual-row bootstrap. Check the compressed operation against explicit replication of a small draw containing repeated and nonconsecutive identifiers.

## Parallel tasks and random streams

For parallel replications, fits or partitions, bound workers by their working memory as well as CPU availability and avoid nested worker/thread-pool oversubscription. Give tasks stable identities, reproducible independent random streams and the result ordering the consumer requires. Preserve each task's stream when workers, scheduling or retries change: a failed subset must recover its original streams rather than reseed a shortened task list. A deliberately new draw needs a new task identity. Use the existing library's supported stream mechanism and retain the generator and task-to-stream mapping with the run inputs. Surface failed tasks before combining results. For in-place updates, establish object ownership; copy deliberately when a caller still needs the original state.

## Measured performance and memory

Use this branch when measured runtime or memory identifies a problem on the requested path. Locate the bottleneck before adding native code or parallel workers. First remove redundant work, unnecessary transfers and unsuitable algorithms. Compare eligible alternatives on representative end-to-end work, including conversion, startup and peak memory. Use native code for a demonstrated hot operation that existing bulk primitives cannot handle adequately; retain a readable reference where feasible. Parallelize independent work only when its savings exceed scheduling and data-copy costs and its outputs have separate owners.

Use [Computation](#computation) for source-side selection and aggregation, working-set budgeting, scans, collection and streaming. Use [Estimator, engine and algorithm selection](implementation-engines.md#estimator-engine-and-algorithm-selection) when the proposed change affects the estimator, compression, resampling or parallel execution. Preserve the adopted calculation and rebuild only its affected dependencies.

## Numerical methods

For non-executed learning code with inputs stipulated by the problem, state that domain and implement the formula directly. Present the correspondence between the solution and the code without an execution-status preface, footnote or postscript. Keep input validation at the public calculation boundary.

Use finite enumeration to construct the requested distribution or finite example; reuse an analytic proof that establishes the requested general claim.

Implement a derived closed-form calculation with the project's existing libraries or the standard library; add a symbolic or numerical solver when the requested calculation requires it.

Define the target, parameters, seeds and convergence criterion. Compare the result with the original equations or an analytic special case. Compute the requested simulation summaries from the adopted draws and retain their generating settings with the result.

For linear estimation, inspect the matrix actually solved: applying least squares to cross-product normal equations does not undo their conditioning loss. Prefer a direct factorization of the original weighted design when conditioning threatens the required precision and its memory and runtime fit the resource budget; otherwise choose a feasible method that meets those requirements rather than changing the target. Preserve the adopted rank and dropped-term convention, and check the inference calculation: rank handling in the coefficient solve does not establish that a later covariance inverse is valid.

For iterative solves, verify the original score, residual or feasibility criterion directly; an iteration limit or a small stabilized step reports only its own status. With clipping, damping or regularization, substitute the returned candidate into the intended equations, compare residuals and constraint violations with the adopted tolerances, and retain the termination reason; a fallback that changes the target requires a specification decision under the economist's procedure: choose only within delegated scope and obtain missing authority before changing a fixed target.

For a relaxed numerical problem, check the candidate solution against the original constraints, including incentive constraints along induced continuation paths where applicable.

When forming a positive sum or ratio of exponentials, subtract the largest log term before exponentiating and restore or cancel that scale in the result; use expm1 and log1p for exp(x) − 1 and log(1 + z).

Evaluate composed objectives and residuals directly in a stable representation when separately materialized intermediate values overflow or underflow.

For an expensive structural solve, measure the objective's actual bottleneck and compare eligible methods on the same model, data, moments, initial conditions and accuracy target. Derive implicit derivatives from `F(y, theta)=0` through `dy/dtheta = -F_y^{-1} F_theta` when the selected root is locally differentiable and the Jacobian solve is valid; compare a directional derivative with the original objective at the adopted accuracy. For JAX, preserve float precision, PRNG keys, parameter transforms and the economic constraints, and include compilation, transfer and device synchronization in runtime comparisons. Compare GPU/batched and CPU outcomes at the same residual and simulation target before selecting the faster feasible route.

For a learned parameter-to-moment or equilibrium approximation, define its training parameter region, simulated design, targets and separate validation simulations in the existing analysis inputs. Compare its recovered parameters and policy quantities with exact solves on those validation cases. Evaluate the final candidate and each requested counterfactual through the original model equations, include simulation/training cost in the measured comparison, and use the exact solution for a case whose adopted residual or quantity target requires it. A neural approximation and an agent-generated implementation each retain their actual producing method and numerical result.

Reuse a solved numerical problem through the project's existing result or solution note: retain its model revision, observed failure, effective initial values, scaling, integration/grid, derivative and solver settings, returned residuals and the change that resolved it. Retrieve that note when the current model and failure mechanism match, apply its settings through the owning solver and verify the affected original equations. Keep binding rules and adopted research choices in their existing authoritative sources when recording reusable experience.

Example: log(exp(a) + exp(b)) = h + log1p(exp(l − h)), where h = max(a, b) and l = min(a, b).

## Power calculation inputs

For the existing `research.py power SPEC --output RESULT` interface, the specification names `design` (`individual` or `cluster`), integer treatment/control assignment-unit counts `n_treatment` and `n_control`, positive `outcome_sd`, the outcome-unit `effect` and `unit`, `alpha`, `target_power` and integer `seed`. Cluster designs also specify `cluster_size` and `icc`; the assignment unit is the cluster, and its mean variance is sigma-squared times `icc + (1-icc)/cluster_size`. The pooled two-sided t test has `n_treatment+n_control-2` degrees of freedom. Analytic power uses the noncentral t distribution, and MDE inverts that same test. Optional `replications` (100–100000) adds independently seeded Monte Carlo draws with bias, RMSE, null rejection, power, coverage and their simulation uncertainty. Optional `dgp` values `icc_true` and `group_shock_sd` let the adopted simulation expose violated working independence or ICC assumptions. Save the actual DGP and report this test's MDE next to the policy-relevant effect; a DID, IV, weak-instrument or structural simulation must execute its own estimator and inference under its own DGP.
