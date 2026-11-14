# Numerical methods for structural research

Use for finite economic models solved by `research_numerics.py run` (equilibria, Shapley and core, clearing, multitask incentives, queues, decision rights) and their model contracts.

Contents:

- [Finite economic model execution](#finite-economic-model-execution)
- [Moment identification and estimation](#moment-identification-and-estimation)
- [Derivatives, devices and sparse systems](#derivatives-devices-and-sparse-systems)
- [Entry point](#entry-point)
- The existing numerical entry point `skills/econ-data/scripts/research_numerics.py` executes finite economic models.
- Its reusable functions also evaluate binary-choice moments, analytic and automatic derivatives, constrained moment estimates and finite-state sparse generators.
- A research stage declares the adopted specification, producing code, selected environment and saved result as dependencies.

## Finite economic model execution

- The same `run SPEC.json --output RESULT.json` command accepts `{ "model": MODEL, "inputs": INPUTS, "unit": UNIT }`.
- `inputs` uses the owning function's argument names.
- `unit` names the common payoff or currency unit; for `queue_capacity` it names the time unit used in both rates.
- Binary-logit covariates and parameters are dimensionless.
- Probabilities and normalized effort retain their own units.
- The command saves the supplied specification, effective arguments including defaults, named scalar `statistics`, complete `fullresults`, equation strings, model-contract and knowledge IDs, source/specification hashes and actual Python/NumPy/SciPy versions.

| Model and knowledge contract | Required inputs | Optional inputs | Calculated object and residuals |
| --- | --- | --- | --- |
| `correlated_equilibrium`, `MC-finite-correlated-equilibrium` / GAME-07 | `payoffs`: finite player-first array, followed by one action axis per player | `weights`: one finite dimensionless welfare weight per player, default all ones; `tolerance=1e-9` | `scipy.optimize.linprog(method="highs")` maximizes the weighted expected payoff. Returns joint recommendation probabilities, each player's expected payoff and every conditional recommendation/deviation slack; verifies probability mass and nonnegativity. |
| `tu_shapley_core`, `MC-finite-tu-shapley-core` / GAME-09 | `values`: exactly `2**n` rational coalition values in bit-mask order, empty coalition zero, at most 16 players | None | `fractions.Fraction` gives exact Shapley allocations, efficiency residual and each nonempty coalition's core slack. `in_core` records membership of that allocation. `fullresults` preserves rational strings; `statistics` supplies numeric values for rendering. |
| `interbank_clearing`, `MC-interbank-clearing` / FINANCE-08 | `liabilities`: debtor rows and creditor columns with zero diagonal; `outside_liabilities`; `external_assets`; all nonnegative in the same currency and clearing period | `tolerance=1e-11`; `maxiter=100000` for the LP solver | The official SciPy HiGHS linear program maximizes total payments subject to `0<=p<=nominal` and `(I-Pi.T)@p<=external_assets`, selecting the greatest pro-rata clearing fixed point. Returns payments, outside-creditor recoveries, equity, the official solver status and iteration count, original fixed-point residual and the resource residual `sum(outside_payments)+sum(equity)-sum(external_assets)`. |
| `multitask_incentives`, `MC-multitask-incentives` / CONTRACT-07 | `b`, `m`, `rho`, `a`, `vq`, `vqly`: quantity reward, private quality benefit, cost interaction, salary and the principal's two marginal values | None | Solves the agent's nonnegative quantity/quality effort at the supplied contract. Own-effort quadratic cost coefficients are normalized to one; `abs(rho)<1`, and `a,b,m>=0`. Returns both efforts, both payoffs and the original KKT residual. |
| `state_price_bounds`, `MC-state-price-bounds` / ASSET-01 | `payoffs`: possible states by freely traded assets; `prices`: current asset prices; `claim`: payoff in those states | `tolerance=1e-9` | Linear programs find strictly positive state prices and the claim-price bounds over their nonnegative closure. Returns subhedge, superhedge, replication portfolio when spanned, and original pricing, hedge and duality residuals. A positive-payoff traded asset bounds the state-price set. An unspanned claim has the open price interval; a spanned claim has its unique replication price. |
| `binary_logit`, `MC-binary-logit` / STRUCT-01 | `theta`: finite intercept and slope; `x`: nonempty finite covariate vector | None | Calls the existing `moment_map` and `moment_jacobian` at the supplied coefficients. Returns the equally weighted mean choice probability, covariate-choice moment and their analytic derivatives. Fix the logit shock scale at one and the base-action utility at zero. |
| `finite_policy_sir`, `MC-sir-finite-policy` / HEALTH-08 | `initial`: susceptible, infected and recovered persons; `beta`, `gamma`: daily transmission and recovery rates; `schedule`: increasing `(end day, contact reduction)` pairs | `infection_cost=1`, `control_cost=0`, `terminal_cost=0`, `rtol=1e-9`, `atol=1e-11`, `max_step=null` for the solver's unbounded maximum step | Calls `finite_policy_sir` to integrate the specified contact path. Saves the full SIR and cumulative-infection path, infection/control/terminal losses, their sum, population conservation and infection-flow residuals. The finite horizon and terminal valuation define the policy comparison. |
| `queue_capacity`, `MC-queue-capacity` / MATH-09 | `arrival_rate`, `service_rate`: events per declared time unit, with `0 <= arrival_rate < service_rate` | None | Returns stationary M/M/1 utilization, mean system time `W`, mean queue time `Wq`, mean system occupancy `L` and mean queue occupancy `Lq`. Use a single server, independent Poisson arrivals, exponential service and first-come-first-served order. |
| `decision_rights`, `MC-decision-rights` / CONTRACT-08 | `B`, `b`, `kP`, `kA`: positive values and quadratic cost coefficients; `alpha`, `beta`: alignment in `[0,1]`; `holder`: `principal` or `agent` | None | Calls the existing active-set equilibrium calculation for simultaneous information efforts. `kP*kA > B*b*max(alpha,beta)` gives contracting best responses and a unique equilibrium. Saves efforts, both net payoffs and the original best-response residual. |
- Use `research_causal.py select` with `design="structural"` and the model's `model_contract_id` or `structural_model`.
- Put the complete three-field run object in `adopted_specification`.
- The supported `target.kind` values are `equilibrium` or `welfare` for correlated equilibrium, `allocation` for Shapley/core, `equilibrium` for clearing, and `policy_value` for multitask incentives.
- `numerical.solution_method` selects respectively `linear_program`, `exact_enumeration`, `greatest_fixed_point` or `kkt`; `numerical.operation="solve"` is the calculation.
- The selector obtains required arguments from the existing callable, returns missing `inputs.NAME` fields explicitly, and supplies the existing owner's executable specification and command.
- Compare adopted policy scenarios by solving each supplied input object and aggregating its saved payoffs under the stated welfare definition.

- For binary logit, select `target.kind="conditional_mean"` and `numerical.solution_method="analytic_moments"`.
- For finite SIR use `policy_value` or `welfare` with `solve_ivp`; for the stationary queue use `equilibrium` or `policy_value` with `closed_form`; for decision rights use `equilibrium`, `policy_value` or `welfare` with `active_set`.
- Each uses `numerical.operation="solve"` and preserves the supplied parameters.
- Interpretation follows the saved quantities: logit moments average over the supplied covariates, SIR losses cover the declared horizon, queue waiting costs require the adopted cost per unit time, and delegation comparisons use each holder's separately solved efforts and payoffs.

- State-price selection uses `target.kind="price_bounds"`, `numerical.solution_method="linear_program"` and `numerical.operation="solve"`.
- The same model follows from `conditions.economic_object="finite_state_claim"`.
- Its conditions `free_trading` and `all_states_possible` describe unrestricted portfolio holdings and the supplied possible states.
- Save the `price_set` classification with the bounds: strictly positive state prices exclude both endpoints for an unspanned claim.
- The saved bound statistics use currency today; hedge and replication residuals use currency at the payoff date.

For example, this two-bank specification has nominal debts `(10,6)` and clearing equations `p1=1+p2/2`, `p2=2+3*p1/5`. The LP and the greatest-fixed-point equations give clearing payments `(20/7,26/7)`, and outside-creditor recoveries sum to the three units of external assets.

```json
{"model":"interbank_clearing","inputs":{"liabilities":[[0,6],[3,0]],"outside_liabilities":[4,3],"external_assets":[1,2]},"unit":"currency units"}
```

## Moment identification and estimation

- For parameter vector θ and fixed covariates xᵢ, `moment_map(theta, x)` defines pᵢ(θ) = 1/(1 + exp(−θ₀ − θ₁xᵢ)) and m(θ) = n⁻¹ Σᵢ (pᵢ, xᵢpᵢ)ᵀ.
- Parameter order is intercept then slope; moment order is mean probability then x-weighted mean probability.
- `moment_jacobian` returns n⁻¹ Σᵢ pᵢ(1−pᵢ) (1, xᵢ)ᵀ(1, xᵢ).
- Full column rank establishes local identification at the evaluated parameter.

- `optimize_moments(target, x, starts, bounds, maxiter)` minimizes ‖m(θ) − m_target‖² with L-BFGS-B and analytic gradient 2Jᵀ(m−m_target).
- Supply the adopted parameter bounds, starting values and observed target moments.
- The function retains each start, termination, gradient and objective and selects the smallest converged objective.
- Save these returns through the existing research result.
- Requested sampling inference uses the adopted independent observation or resampling unit in the producing analysis.

## Derivatives, devices and sparse systems

- `finite_jacobian(function, theta, step)` adapts the supplied callable to official [`scipy.differentiate.jacobian`](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.differentiate.jacobian.html), with `order=2`, the supplied `initial_step` and one stencil evaluation.
- It retains the existing central-difference step and output shape; the replacement and sequential-game estimators share this adapter.
- Choose the step and comparison tolerance from that function's scale and precision when a changed derivative requires verification under the economist's procedure.

- `jax_moment_map` supplies the differentiable binary-choice moments.
- `jax_moment_batch(parameters, x, backend)` applies the same kernel with 64-bit arithmetic, vectorization and JIT on the selected `cpu` or `gpu` device.
- It returns the synchronized native array.
- Record the device and effective precision in the producing analysis.
- A requested GPU execution requires an available GPU device.

- `birth_death_generator(n, birth, death)` returns a sparse reflecting generator.
- Its off-diagonal rates are Qᵢ,ᵢ₊₁=birth and Qᵢ,ᵢ₋₁=death; each diagonal is minus its outgoing rates.
- Use the adopted reward vector and discounting in the project's SciPy sparse or Julia linear solve.
- The model's original Bellman or resolvent equation determines the saved residual.

Dynamic estimation uses the existing [dynamic model runner](dynamic-models.md) and its adopted data, likelihood, moments and equilibrium selection. Numerical algorithm comparisons run only for a requested choice that changes the research result.

## Entry point

```sh
python skills/econ-data/scripts/research_numerics.py run /path/to/model-spec.json --output /path/to/result.json
```
- `run` atomically saves the selected model result with the specification hash.
- Install the selected dependencies from `requirements-numerics.txt` in the existing research environment.
- Import a named numerical function directly from the existing analysis stage when the adopted calculation requires it.
