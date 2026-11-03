# Numerical methods for structural research

The existing numerical entry point `.agents/skills/econ-data/scripts/research_numerics.py` provides reusable moment, derivative, constrained optimization and sparse generator functions alongside a reproducible synthetic case. A research DAG invokes the entry point as a stage, declares its specification, script, imported `.agents/skills/econ-data/scripts/research_dynamic.py` and `.agents/skills/econ-data/scripts/equity_io.py`, Julia script, selected environment and result as dependencies, and consumes named entries from `statistics`. The result includes the complete input, engine versions, source digests, seed, hardware, precision, timing boundaries, matrices and diagnostics. The optional Julia stage uses standard-library `SparseArrays` and `LinearAlgebra`; set `JULIA_DEPOT_PATH` to the selected Julia environment before running.

## Moment identification and estimation

For parameter vector θ and fixed covariates xᵢ, the example defines pᵢ(θ) = 1/(1 + exp(−θ₀ − θ₁xᵢ)) and m(θ) = n⁻¹ Σᵢ (pᵢ, xᵢpᵢ)ᵀ. The column order is intercept then slope, and row order is mean probability then x-weighted mean probability. Its Jacobian is n⁻¹ Σᵢ pᵢ(1−pᵢ) (1, xᵢ)ᵀ(1, xᵢ). Full column rank establishes local identification at the evaluated point. Singular values and the rank threshold are saved with the matrix; local rank alone does not establish global identification.

The estimator minimizes ‖m(θ) − m_target‖² subject to θ₀ ∈ [−2,2] and θ₁ ∈ [0,3]. `optimize_moments(target, x, starts, bounds, maxiter)` applies L-BFGS-B with the analytic gradient 2Jᵀ(m−m_target), records each start and termination, and selects the smallest converged objective. The case first runs with a one-iteration limit and then resumes its returned parameter under the same objective and bounds. It compares analytic and central finite-difference Jacobians (step 10⁻⁵), JAX automatic Jacobians, and JAX Hessians against central differences of the analytic gradient (step 10⁻⁴). Original moments and derivatives are checked to 10⁻⁷ and 10⁻⁶ respectively.

## Dynamic estimators

The comparison generates 100 ten-period markets from the same symmetric two-firm, four-state game, with state s = (s₁,s₂), action a = (a₁,a₂), next state a and current firm-i flow aᵢ(1−0.4aⱼ)−c aᵢ(1−sᵢ). Independent type-I extreme-value payoff shocks have unit scale, discount factor is 0.8, and the generating entry cost is 0.8. Both actions are observed at every firm-state in the case. NFXP and MPEC call the existing `equity_io.dynamic_game` entry; SLC calls `research_dynamic.sequential_estimate`. NFXP solves the policy equilibrium inside the same observed action likelihood. MPEC maximizes that likelihood jointly over c and policy log odds subject to equilibrium equations. SLC solves successive linearized equilibrium constraints and records its final original equilibrium residual and constrained score. The comparisons use the same observations, bounds, payoff definition and equilibrium initialization. Runtime records include the full fit and exclude sample construction. NFXP/MPEC/SLC estimates, likelihoods and residuals must be inspected together; algorithm-specific termination criteria remain explicit.

## Fixed points, integration, sparse calculation and devices

The fixed-point example solves z = 0.8 cos(z). This map is a contraction because |−0.8 sin(z)| ≤ 0.8. Plain iteration stops on the original residual 10⁻¹¹. `scipy.optimize.fixed_point` with `method="del2"` supplies accelerated iteration, followed by substitution into the original equation. For integral comparisons, the common target is ∫₀¹ exp(u) du = e−1: adaptive quadrature, 1,024 independent uniform draws, and 1,024 scrambled Sobol draws each return an estimate and absolute error. Independent parallel draws use `SeedSequence.spawn`; the saved streams and ordering make the serial/parallel identity test reproducible.

The sparse generator Q has n states, upward rate b and downward rate d, with reflecting boundaries. Off-diagonal Qᵢ,ᵢ₊₁=b and Qᵢ,ᵢ₋₁=d where those neighbors exist; Qᵢᵢ is minus the sum of the outgoing rates. Python and Julia solve the identical sparse system (I−0.9Q)v=r, rᵢ=sin(i/100), i=0,…,999. The output records row sums, linear residuals, maximum Python–Julia solution difference, Julia executable, version, script digest and wall time including startup. This finite system can be reused with different sparse matrices and right-hand sides; dimensions and rates are inputs to the generator.

JAX executes the moment kernel with 64-bit arithmetic, vectorized across parameter draws and JIT-compiled. CPU timing distinguishes compilation plus first call from a synchronized warm call and NumPy reference loop. The backend setting accepts `cpu` or `gpu`; a GPU request requires an observed JAX GPU device and runs the same vectorized kernel there, with CPU-reference error reported. The result records actual GPU devices and whether a GPU call executed. An unavailable GPU request returns an error rather than reporting a GPU result. Transfer and compilation are excluded from warm-call timing; the NumPy time includes its Python loop.

## Surrogate and Monte Carlo

The neural surrogate approximates the original two-moment mapping over the frozen parameter region [−2,2] × [0,3]. A seeded uniform design is split before fitting into 600 training, 150 validation and 150 holdout rows. A 2–40–40–2 tanh MLP is fit on training rows only. The saved result reports RMSE and maximum error on all three partitions. A bounded optimization of the surrogate provides a starting parameter; the final estimate then minimizes the original moment objective. Both the surrogate candidate's original-moment error and the final original-moment error are saved. Record the separate training time, surrogate fit, original warm-start fit, original single-start fit and original multistart fit. Compare times under these explicit boundaries; training amortization depends on the number of future fits.

For Monte Carlo evaluation, each replication independently samples covariate indices from the fixed grid and then binary outcomes from pᵢ(θ). Each estimate solves the same bounded moment problem. Save every seed, fit and convergence indicator, together with mean error (bias), root mean squared error, replication count, sample size and elapsed time. Its finite-sample summaries describe the stipulated model and design.

## Entry point

A JSON specification contains exactly `seed` (nonnegative integer), `theta` (two finite values with −1.8 < θ₀ < 1.8 and 0.2 < θ₁ < 2.8), `grid_size` (integer at least 10), `mc_replications` (integer at least 2), `mc_sample_size` (integer at least 10), `julia` (executable path), and `jax_backend` (`cpu` or `gpu`). The grid spans [−2,2]. For a reproducible case or a DAG stage:

```sh
ECON_JULIA=/path/to/julia python .agents/skills/econ-data/scripts/research_numerics.py case --output /new/case-directory
python .agents/skills/econ-data/scripts/research_numerics.py run /path/to/numerics-spec.json --output /path/to/result.json
```

`case` publishes the specification and result together to a new directory. `run` atomically publishes a result and records the specification hash. Install the pinned packages in `.agents/skills/econ-data/scripts/requirements-numerics.txt` in the selected research environment, along with the existing dynamic-game modules. Julia must be available at the path in the specification. The GPU backend additionally requires a compatible JAX device installation.
