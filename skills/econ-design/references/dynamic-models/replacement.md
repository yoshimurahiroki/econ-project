## Replacement

- An agent observes mileage state `s = 0,...,S-1` and independent unit-scale type-I extreme-value action shocks, then chooses maintenance `a=0` or replacement `a=1`.
- Maintenance costs `c s` and moves mileage to `min(s+1,S-1)`; replacement costs `R` and moves mileage to zero.
- The next state is known conditional on the action.
- Normalize Euler's constant to zero.
- For discount factor `0 < β < 1`, the inclusive value and choice probability satisfy

`V(s) = log Σ_a exp[u(s,a) + β Σ_s' P_a(s,s') V(s')]`,

`p(a|s) = exp[u(s,a) + β P_a(s,:) V - V(s)]`.

- The infinite-horizon calculation passes the original Bellman residual and its analytic Jacobian to official [`scipy.optimize.root(method="hybr")`](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.optimize.root.html), starting from zero values.
- Acceptance requires the original Bellman residual below `1e-12`; the returned solver status, message and function-evaluation count remain saved.
- The existing `iterations` field records those function evaluations.
- The finite-horizon calculation starts with zero terminal value and evaluates the specified backward recursion.
- Each stage records values and policies indexed by periods remaining.
- The saved residual checks the original recursion.
- Model values measure expected discounted utility, including the normalized taste shocks.
- A change in replacement cost produces a new value and policy from the changed primitives.

- The supplied panel provides action and state observations.
- The runner re-solves the baseline and changed replacement cost at the NFXP parameters fitted to the supplied panel.
- Nested fixed point calls the pinned official `ruspy` 2.0 criterion and maximizes its action likelihood over `(c,R)`, resolving the Bellman equation at each trial.
- The official engine applies one mileage increment after replacement.
- The equivalent official replacement-cost input is `R_official=R+β[V(1)-V(0)]`, which makes its continuation utility equal to this model’s reset-to-zero continuation.
- The supplied transition assigns probability one to the one-unit increment before the mileage cap.
- The output checks the official likelihood against the original model on the same observations.
- It treats the discount factor, shock scale and transition rule as fixed.
- Identification requires state variation and action responses that make the two cost derivatives linearly independent; the scale normalization fixes utility units.

- The [official ruspy criterion factory](https://github.com/OpenSourceEconomics/ruspy/blob/414e9f98e3b1cf19544b1ca3b1e544ac5751c1e9/ruspy/estimation/criterion_function.py) returns `(func_dict, transition_results)`.
- Its native dataframe has a subject/period MultiIndex and `state`, `decision` and `usage` columns.
- The factory estimates transition probabilities from `usage` and evaluates choices from period 1 onward; map those rows and the native replacement timing to the adopted sample and model.
- `options.estimation_method="mpec"` selects the implemented constrained optimization.
- The runner minimizes the official negative partial log likelihood in `[EV_0, ..., EV_(S-1), cost_parameters]`, subject to the returned `EV_new-EV=0` constraints, using the returned objective derivative and constraint Jacobian.
- It saves optimizer termination, transition estimates, variable order, original EV residuals and inference inputs from the [MPEC implementation](https://github.com/OpenSourceEconomics/ruspy/blob/414e9f98e3b1cf19544b1ca3b1e544ac5751c1e9/ruspy/estimation/mpec.py).

- The default reset-to-zero panel retains its existing columns, deterministic one-state maintenance increment, NFXP and CCP.
- For MPEC, `fit_replacement_mpec` uses `EV(s)=V(min(s+1,S-1))` and the equivalent native replacement cost above.
- The zero-state equation gives `V(0)=β EV(0)+log(1+exp(-R_official))`, hence `R=R_official-β(1-β)EV(0)+β log(1+exp(-R_official))`.
- `options.mpec.bounds` uses the original `[maintenance_cost, reset_replacement_cost]` order; the original replacement-cost bounds become constraints under this mapping.
- Optional `options.mpec.optimizer` supplies SLSQP options and `constraint_tolerance` sets the original EV residual criterion.
- The result reports the structural costs, native cost/EV variables, likelihood agreement with the original reset model, original Bellman residual and concentrated cost score separately.

- For an adopted native Rust panel, explicitly set `options.replacement_timing="reset_then_usage"`.
- Select this declared model through `structural_model="replacement"`; `MC-replacement-ddc` retains its reset-to-zero transition law.
- `data.columns` then maps `id`, `period`, `state`, `action` and `usage`; missing initial usage remains missing.
- The existing `run` command dispatches to `ruspy_native_run`.
- Supply `options.ruspy.model_specifications` with `discount_factor`, `num_states`, `maint_cost_func="linear"` and `cost_scale`, plus `initial_parameters` and `bounds` in native `[replacement_cost, maintenance_coefficient]` order.
- `options.ruspy.optimizer` selects `SLSQP` for MPEC or `L-BFGS-B` for NFXP, with its native SciPy options.
- Optional `alg_details` reaches `ruspy.calc_fixp`, and `constraint_tolerance` applies to the original EV/Bellman equations.
- This branch estimates the observed usage distribution and retains the official period-1-and-later likelihood sample.

- The native branch's maintenance cost per state is `maintenance_coefficient*cost_scale`.
- Its replacement cost is the native payoff cost before a new usage draw.
- Its `EV=P_usage V` and replacement continuation uses `EV(0)`.
- The result records those definitions and the original parameter order.
- `replacement_cost_change` modifies the native replacement payoff cost; the observed usage transition, discounting, initial population and shock normalization stay fixed.
- Official `calc_fixp` re-solves both scenarios, and official choice probabilities produce the saved likelihood comparison.
- The welfare statistic averages the initial-state inclusive value over the observed individuals.
- The default reset-to-zero branch keeps its distinct timing and transformation.

- The replacement result also saves gallery displays for parameters, model diagnostics, state-specific replacement probabilities and discounted values.
- Each row retains its estimator or policy scenario, state and utility/probability unit.
- Registration and meeting templates consume those saved rows without solving the Bellman equation again.

- The two-step CCP calculation estimates action probabilities from state-specific counts.
- Let `P̄ = Σ_a diag(p_a) P_a`, `H(s)=-Σ_a p_a(s) log p_a(s)` and `ū(s)=Σ_a p_a(s)u(s,a)`.
- Policy evaluation gives `V_p=(I-βP̄)^-1(ū+H)`.
- Hence the conditional log odds equal `u(s,1)-u(s,0)+β(P_1-P_0)V_p`.
- Because flows are linear in `(c,R)`, the implementation solves the resulting least-squares system and reports its rank and residual.
- This requires both actions observed in each state; it does not smooth empty cells.
- The supplied panel fixes the observed initial states, and the specification fixes the deterministic transition law.

## Persistent latent replacement type

- Each agent draws a permanent type before the observed panel.
- Type `k` has replacement cost `R_k` and share `ω_k`; maintenance cost, discount factor, transitions and shock scale are common and fixed.
- Its policy solves the replacement Bellman equation.
- A panel has type-conditional likelihood `L_ik=∏_t p_k(a_it|s_it)`, conditional on its observed initial state and transitions, and mixture likelihood `Σ_k ω_k L_ik`.
- Type costs must differ and panels must contain action and state variation that distinguishes them; ordering costs labels the two types.

- EM computes posterior type weights `τ_ik=ω_k L_ik/Σ_h ω_h L_ih`, updates each share to its sample mean, and maximizes the weighted panel log likelihood for each type's replacement cost with a new Bellman solution at every trial.
- The observed likelihood must increase at each iteration.
- The result saves the likelihood trace, starting values, input identity and final parameter change.
- Its counterfactual reports the initial-state value averaged across the fitted type shares, using fitted type costs before and after a replacement-cost change.
- The specification supplies the shared maintenance cost, starting replacement costs, initial type share and estimation bounds.

## Simulated moments for the replacement model

- Add `smm` to the replacement options to estimate the same observed table by simulated moments.
- Supply `seed`, at least two `replications`, two `initial_costs`, a two-by-two `bounds` array and optimizer `tolerance`.
- Each replication starts every observed ID in its observed initial state, follows its observed panel length, draws new action shocks and applies the same maintenance/replacement transition as the Bellman model.
- The same seeded draws are reused at every parameter trial; separate replications use independent draws.

- The ordered moment vector is the overall replacement frequency followed by the replacement frequency conditional on each mileage state.
- With observed moments `m` and the mean simulated moments `m̂(θ)`, the identity-weighted criterion is `(m̂(θ)-m)'(m̂(θ)-m)`.
- Bounded Powell optimization selects the two costs.
- Every observed state and every simulated replication must have positive state counts.
- The output reports observed and simulated moments, differences, the objective, bounds and optimizer tolerance, seed, replication count, starting states and panel lengths.
- Replication-to-replication variation supplies the Monte Carlo standard error of each simulated mean; it treats whole panels as the independent simulation replicates.

- For local identification, the code computes expected state masses from the exact controlled Markov transition under each trial policy, forms the corresponding population moment map, and reports its central-difference Jacobian, step sizes, singular values, numerical rank threshold and rank.
- The two cost columns must have rank two.
- `fit_id` binds the input source hash, discount factor, number of states, simulation options and producer hash.
- Baseline and changed policies are resolved at the SMM estimates and report their original Bellman residuals.
- The declared seed and fixed draws identify the simulation used by the estimator.
