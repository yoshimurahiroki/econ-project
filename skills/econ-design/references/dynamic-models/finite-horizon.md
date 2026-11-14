## Official finite-horizon and lifecycle selection

- The existing [selection entry](../../../econ-data/scripts/research_causal.py), `select DESIGN.json --output SELECTION.json`, selects the existing execution owner from `design="structural"` and the adopted model identity.
- Selection identifies its actual entry point and input/output contract.
- The owning runner constructs the official native objects, executes the adopted optimization, solution or simulation, and saves its numerical returns.
- Keep the adopted specification unchanged and retain proposed native-option changes in the returned selection.

Select the model from the actor's problem and requested quantity:

| Economic object | Selection and computational target |
| --- | --- |
| Representative household choosing consumption and capital over a fixed horizon | `finite_horizon_growth`: the existing `research_macro.py solve` optimizes log consumption under Cobb-Douglas production, output taxes and fixed initial/terminal capital. It returns optimal trajectories and scenario welfare. |
| Household consumption and savings under an exogenous income/return process | `consumption_saving`: official HARK consumer classes return age-specific consumption/value functions and simulated asset/income histories. Declare `conditions.income_process` as `perfect_foresight` or `idiosyncratic_shocks`. |
| Individual choices with several states, including assets, health or income | `lifecycle_choice`: official `lcm.Model` represents the adopted states, constraints, shocks and transitions. Its solution and simulation use fixed or previously estimated parameters. |
| Employment, retirement and other finite-lived regimes | `lifecycle_choice`: declare the regime graph, feasible transitions, terminal regimes and regime-specific choice problem in `lcm.Model`. |
| Finite-horizon discrete-choice structural estimation | `finite_horizon_choice`: official respy constructs the simulated-moment or likelihood criterion for the adopted optimizer and identified free parameters. |
| Policy or equilibrium counterfactual from an existing structural fit | Reuse the fitted parameters and native model object. respy uses `get_simulate_func` with its saved parameter vector and options. Lifecycle/HARK re-solve their own individual choices conditional on prices; the existing PyBLP, market, dynamic-game or macro owner solves its corresponding market-clearing or strategic equilibrium. |
- When `structural_model` is absent, `conditions.economic_object` accepts `representative_household_growth`, `household_consumption_saving`, `individual_dynamic_choice` and `employment_retirement_regimes`.
- Preserve an adopted `model_contract_id` or `structural_model` through estimation, policy simulation and welfare.
- For an unbound individual-choice model, its state/action domain and regime declaration select the implementing model: finite-horizon discrete choice uses respy, and the adopted lifecycle/regime declaration uses pylcm.
- A new requested output does not change the actor's states, choices, transitions or fitted model.
- The model contract retains `actors`, `objectives`, `states`, `choices`, `constraints`, `information`, `transitions`, `shocks`, `discount`, `horizon`, `terminal_conditions`, `observed_data`, `identified_parameters`, `computation_target`, `equilibrium` and `welfare` in `economic_model`.
- Missing primitives appear in `model_inputs_to_supply`, including when the supplied model object is empty.
- A calibrated solve records its parameter source and observation map; structural estimation additionally maps each free parameter to the observed variation, moments or likelihood and normalizations that identify it.

- `numerical.operation` distinguishes `solve`, `simulate`, `estimate` and `counterfactual`.
- The growth runner accepts solve/counterfactual, HARK and pylcm accept solve/simulate/counterfactual, and the respy estimation contract accepts estimate.
- For a saved respy model, retain `structural_model="finite_horizon_choice"` and select simulate/counterfactual with explicit fixed, calibrated or estimated `conditions.parameter_status`.
- `method_selection.computation` retains the requested operation, supported operations, parameter treatment and output objects; selection records `operations_executed=[]`.
- Use `numerical.solution_method` for a solver and `numerical.estimation_method` for estimation.
- The earlier lifecycle `estimation_method="backward_induction"` remains readable and must agree with `solution_method` when both are supplied.
- Record actual solution, simulation and optimization returns in the existing research result; constructing a criterion or selecting an interface supplies no fitted parameters.

| Economic model and target | Numerical method and official interface | Objective and returned quantities |
| --- | --- | --- |
| `finite_horizon_growth`, `policy_value` or `welfare` | `numerical.solution_method="slsqp"`; existing `research_macro.py solve` calls `scipy.optimize.minimize` | Fixed-endpoint capital/consumption paths, discounted log-consumption welfare and the original Euler/resource residuals. The result is a trajectory at those endpoints. |
| `consumption_saving`, `policy_value` or `welfare` | `numerical.solution_method="backward_induction"`; `HARK.ConsumptionSaving.ConsIndShockModel.PerfForesightConsumerType` or `IndShockConsumerType` | Policies and normalized values in `consumer.solution`; requested simulation histories in `consumer.history`. |
| `finite_horizon_choice`, `structural_parameter` | `numerical.estimation_method="smm"` (default); `respy.get_moment_errors_func` | Minimize `(m_data-m_sim(theta))' W (m_data-m_sim(theta))` through the returned `value`. The factory returns a parameter-only criterion. `return_scalar=false` retains the value, moment errors, simulated moments and comparison rows; `root_contributions` supplies a squared-residual representation for nonnegative diagonal `W`. |
| `finite_horizon_choice`, `structural_parameter` | `numerical.estimation_method="maximum_likelihood"`; `respy.get_log_like_func` | Maximize the mean log likelihood of the adopted observed histories. The factory returns a parameter-only likelihood function. `return_scalar=false` retains its value, contributions and comparison rows. |
| `finite_horizon_choice`, `policy_value` or `welfare`, with simulate/counterfactual | `numerical.solution_method="backward_induction"`; `respy.get_simulate_func` | Construct the native simulator from the saved specification, then call it at the supplied fixed or fitted parameter vector. Each call solves the same structural model and returns scenario outcomes. |
| `lifecycle_choice`, `policy_value` or `welfare` | `numerical.solution_method="backward_induction"` (default); `lcm.Model.solve` and `Model.simulate` | Hold fixed or previously estimated parameters, solve the declared regimes and simulate the adopted initial population. Aggregate saved scenario values/outcomes with the requested population weights and value units. |
- For [representative-household growth](../../../econ-data/scripts/research_macro.py), supply `alpha`, `beta`, `delta`, `initial_capital`, `terminal_capital`, `baseline` and `scenario` productivity/output-tax paths, `population`, `period`, `unit`, `sources` and `tolerance`.
- Both scenarios use the same horizon.
- The existing solver treats output-tax revenue as government absorption and terminal capital as fixed with zero continuation utility.
- Its saved result contains both allocations, their welfare difference and the original-equation residuals.
- It uses the supplied parameters directly.

- For HARK, set `cycles=1` and supply `T_cycle`, CRRA curvature, discounting, returns, survival and income-growth profiles, borrowing limits and initial asset/permanent-income distributions.
- `IndShockConsumerType` also needs the adopted permanent/transitory shock distributions, integration counts and asset grid.
- Selection proposes `vFuncBool=True` for that class because the requested output includes values; it preserves the original options and exposes the proposed change.
- `consumer.solve()` returns `None` and saves `T_cycle+1` solution objects in `consumer.solution`; each supplies `cFunc(mNrm)` and `vFunc(mNrm)`.
- These classes' terminal consumer spends cash on hand.
- For simulation, set `AgentCount`, `T_sim`, `seed` and `track_vars`, then call `initialize_sim()` and `simulate()`.
- Each tracked history has shape `(T_sim, AgentCount)`.
- Retain permanent-income normalization and the conversion used for level consumption or utility before aggregating welfare.
- The [existing macro runner](../macro-models/households.md#household-consumption-and-savings) accepts `model="consumption_saving"`, `income_process`, native `consumer_options`, `evaluation` and `calibration_source`.
- Optional `scenario.consumer_options` re-solves the changed primitives, and `simulation` supplies the native history settings.
- It saves evaluated policies, values, Euler gaps, borrowing complementarity, population-weighted statistics and gallery displays.

- For finite-horizon estimation, pass the official ordered `params` dataframe/series and `options`.
- Declare the horizon, terminal values, feasible states and choices, information timing, state transitions, utility/shock normalizations, free/fixed parameters and adopted bounds.
- Preserve the observed population, sample, units and weight meaning.
- The SMM factory also requires `calc_moments`, `replace_nans`, `empirical_moments`, the adopted `weighting_matrix` and `n_simulation_periods`.
- Match simulated moment labels and ordering to the empirical moments.
- Simulation length and `options.n_periods`, which sets the decision horizon, retain separate meanings.
- The likelihood factory requires the observed choice/wage `df` in the official estimation-data format.
- Retain `solution_seed`, `simulation_seed`, `estimation_seed`, integration/draw settings and the chosen optimizer.
- Parameter inference uses the adopted likelihood or moment procedure and independent sampling unit.

- The [pinned respy SMM implementation](https://github.com/OpenSourceEconomics/respy/blob/91e8a193fb7d5cf7212c15e50ae43f810bb9b1eb/respy/method_of_simulated_moments.py) returns `value=e.T @ W @ e` for moment errors `e`, and computes `root_contributions=e @ np.sqrt(W)` with an elementwise square root.
- Minimize `value` for the adopted general weighting matrix and retain `moment_errors`, `W` and the moment ordering for inference.
- Use `root_contributions` as a squared-residual representation when `W` is nonnegative and diagonal.
- For example, `e=(1,2)` and `W=[[2,1],[1,2]]` give `value=14` and a root-contribution squared sum of `15+8*sqrt(2)`.

- For a respy fitted-model simulation, declare `numerical.simulation_method`.
- `n_step_ahead_with_sampling` draws the initial population from the adopted distributions.
- `n_step_ahead_with_data` starts from the supplied initial states, using `Identifier`/`Period` indexing with zero-based consecutive IDs at Period 0.
- `one_step_ahead` evaluates each observed state; it supplies conditional one-period predictions.
- Both data methods require `df`.
- Individual counterfactual lifecycle welfare uses an n-step method so the model evolves its own changed state path.
- Supply the saved parameter dataframe/series and structural options explicitly, retaining their ordering, normalizations, initial population and scenario draws.

- The pinned [respy simulation implementation](https://github.com/OpenSourceEconomics/respy/blob/91e8a193fb7d5cf7212c15e50ae43f810bb9b1eb/respy/simulate.py) replaces an explicit `n_simulation_periods` with `options['n_periods']`.
- With `n_simulation_periods=None`, one-step simulation instead uses the largest observed Period plus one; n-step simulation uses the decision horizon.
- The selector proposes `None` and reports this effective horizon.
- Keep the adopted decision horizon intact and select displayed periods from saved results.
- The returned `Identifier`/`Period` dataframe contains states, `Choice`, `Wage`, `Discount_Rate`, `Present_Bias` and each choice's `Flow_Utility`, `Value_Function` and `Continuation_Value`.
- Welfare aggregates chosen flow utility under the adopted discounting, present-bias interpretation, terminal evaluation and population weights.
- A value function already includes continuation value.
- Recorded wages also contain measurement error, so their sum does not supply the utility aggregate.

- For lifecycle solution, construct the official `lcm.Model` with `regimes`, `regime_id_class`, `initial_nodes` and `edges`, plus exactly one of `ages` and `n_periods`.
- Supply the model's states, actions, `state_transitions`, utility functions, constraints, shocks, discounting, terminal regimes and regime-specific solver/grids.
- `fixed_params` and each call's `params` preserve the adopted normalizations and values; `conditions.parameter_status` accepts `fixed`, `calibrated` or `estimated`.
- `Model.solve(params=..., log_level=...)` returns `SolutionResult` with values, model/parameter identity and retained policy-replay artifacts.
- Pass that complete result to `Model.simulate(params=..., initial_conditions=..., solution=..., log_level=..., seed=...)`.
- Preserve initial-population order and the adopted `taste_shock_seed` or `shock_paths` across scenario comparisons.
- The simulation returns `SimulationResult`; `to_dataframe()` supplies its saved outcomes for project aggregation.

- Match each [pylcm solver](https://github.com/OpenSourceEconomics/pylcm/blob/0fb55673b0be4eb52d270b2585047faa38c4e930/src/lcm/solvers.py) to its economic declaration.
- `GridSearch` accepts the ordinary `Regime`.
- `EGM`, `DCEGM` and `NBEGM` use `ConsumptionSavingsRegime` with a `LiquidMargin` declaring `state`, `action`, `resources` and `post_decision_state`.
- `NEGM` and `NNBEGM` use `NestedConsumptionSavingsRegime`, adding an `OuterContinuousMargin` with `state`, `action`, `post_decision_state`, `no_adjustment` and the adopted `adjustment_cost`.
- These [margin roles](https://github.com/OpenSourceEconomics/pylcm/blob/0fb55673b0be4eb52d270b2585047faa38c4e930/src/lcm/consumption_savings_regime.py) bind the liquid state, consumption action, available resources, savings and outer durable or illiquid choice to the model's existing functions.
- The solver supplies numerical settings.
- Select EGM for one smooth continuous margin, DCEGM for discrete-continuous choices, NBEGM for declared nonconvex budget breakpoints, and the corresponding nested solver for an outer continuous margin.
- Preserve the declared constraints, grids, envelope method and complete solution artifacts used by simulation.

- Lifecycle policy values condition on the adopted exogenous paths.
- Welfare requires its population weights, scenario contrast and utility or monetary conversion.
- Market-clearing equilibrium has its own equation and execution owner; this selector rejects `target.kind="equilibrium"` for `lifecycle_choice`.
- Structural-parameter estimation uses the adopted estimation owner.
- A saved finite-horizon respy fit stays with that model for its subsequent simulation and welfare calculation.

Versioned official sources: [HARK 0.17.2 consumer classes](https://github.com/econ-ark/HARK/blob/269085077b84cb50feb49d0cd54bbf4da5fa3199/HARK/ConsumptionSaving/ConsIndShockModel.py), [respy 2.1.1 simulated moments](https://github.com/OpenSourceEconomics/respy/blob/91e8a193fb7d5cf7212c15e50ae43f810bb9b1eb/respy/method_of_simulated_moments.py), [respy mean log likelihood](https://github.com/OpenSourceEconomics/respy/blob/91e8a193fb7d5cf7212c15e50ae43f810bb9b1eb/respy/likelihood.py), [pylcm model construction, solution and simulation](https://github.com/OpenSourceEconomics/pylcm/blob/0fb55673b0be4eb52d270b2585047faa38c4e930/src/lcm/model.py), and [pylcm assets/health, work and retirement example](https://github.com/OpenSourceEconomics/pylcm/blob/0fb55673b0be4eb52d270b2585047faa38c4e930/src/lcm_examples/precautionary_savings_health.py).

- The existing knowledge planner accepts `MC-hark-consumption-saving`, `MC-respy-finite-choice`, `MC-lifecycle-regimes` and `MC-replacement-ddc` directly.
- Use `knowledge.py plan CONTRACT_ID --read` to obtain each model's selection, equations, identifying observations, numerical diagnostics and prerequisites.
- `DYN-02` compares the retirement regimes and continuous saving choices with a solved two-period switching threshold.
- `STRUCT-03` distinguishes respy's finite-horizon normal-shock integration from the stationary extreme-value replacement likelihood.
- `HET-01` maps exogenous-price consumption policies to HARK and the additional market-clearing calculation to `HET-02`.
- The contract's `availability` identifies the existing runner, numerical example or pinned external API; adopted parameters and actual execution remain in the research result.

## Execute and reuse a respy fit

- The existing `run` command dispatches `model="finite_horizon_choice"` to `respy_run`.
- Its `operation` is `estimate`, `simulate` or `counterfactual`.
- `params` is either `{"path":"params.csv"}` or a record array with `category`, `name` and `value`; additional native parameter columns are retained.
- Observations and parameter tables accept CSV, Parquet and Arrow IPC (`.arrow`, `.feather`, `.ipc`) through the shared `read_frame` helper.
- For Parquet or Arrow, install `pyarrow==17.0.0` in respy's selected Python 3.11 / NumPy 1.23 environment; the primary NumPy 2 environment retains its selected Arrow version.
- `options` is the official structural options dictionary.
- `adopted` retains the economic specification, identifying observations and normalizations.
- Table paths resolve against the specification directory.
- `data.path` names the observed native dataframe, with `Identifier` and `Period` columns; optional `data.columns` maps native names to actual table columns.
- Missing wage observations remain missing.

For estimation, supply:

```json
{
  "model": "finite_horizon_choice",
  "operation": "estimate",
  "params": {"path": "params.csv"},
  "options": {"n_periods": 5},
  "adopted": {"source": "adopted economic specification and revision"},
  "data": {"path": "observations.csv"},
  "estimation": {
    "method": "maximum_likelihood",
    "free_parameters": [["wage_fishing", "exp_fishing"]],
    "bounds": [[0.1, 0.5]],
    "optimizer": {"method": "L-BFGS-B", "options": {"ftol": 1e-11, "maxiter": 100}}
  },
  "inference": {"method": "retain_inputs", "independent_unit": "Identifier", "derivative_step": 0.00001}
}
```
- Complete `options` with the adopted native choice/state definitions, covariates, seeds and integration counts.
- The official defaults are materialized in the saved result.
- `free_parameters` fixes the optimization order and every other parameter stays fixed.
- `bounds` has the same order.
- Supported bounded SciPy methods are `L-BFGS-B`, `Powell`, `Nelder-Mead` and `SLSQP`; `optimizer.options` and optional `optimizer.tolerance` reach `scipy.optimize.minimize`.
- ML minimizes the negative native mean individual log likelihood.
- The saved criterion retains that native mean, individual contributions and comparison rows.
- Optimizer termination has its own field.

- For `estimation.method="smm"`, supply `moments.module`, a local Python file containing the adopted moment functions, and `moments.calc_moments`, their function name, ordered list of names or named dictionary.
- Apply the same functions to observed and simulated data.
- `moments.replace_nans` supplies a corresponding function name/list/dictionary or `null`.
- `moments.weighting_matrix` is the explicit symmetric positive-semidefinite matrix in `respy.get_flat_moments` order.
- Optional `moments.n_simulation_periods` reaches the native factory; the pinned simulator's effective horizon remains `options.n_periods`.

- The runner calls `respy.get_moment_errors_func(..., return_scalar=False)` and minimizes its `value`.
- It saves native moment errors, empirical and simulated moments, comparison rows, ordering and `W`.
- It compares the final returned value to the original `e.T @ W @ e`.
- It saves native `root_contributions` only for diagonal `W`.
- General symmetric `W`, including negative off-diagonal entries, uses the official scalar value.
- Optional distinct `moments.simulation_seeds` evaluate additional independent simulations at the fitted parameters, saving replicate moments, their standard deviation and the standard error of their mean.
- These draws do not change the criterion used for estimation.

- `fit` retains the native parameter dataframe, effective structural options, adopted specification, observed dataframe, exact source hashes, optimizer return and inference inputs.
- `inference.method="retain_inputs"` preserves the independent unit and observed sample mapping.
- With an explicit positive `derivative_step`, ML also retains individual scores and SMM retains the ordered moment-error Jacobian from central differences inside the adopted bounds.
- A statistical covariance is calculated by the adopted inference operation from these inputs; optimizer convergence and simulation dispersion retain separate roles.

- For saved-model simulation, supply `fit_path` pointing to the prior result JSON and `simulation.method`.
- The runner reconstructs the saved parameter dataframe and calls `respy.get_simulate_func` directly.
- Sampling starts from the native initial distributions.
- `n_step_ahead_with_data` uses the retained or explicitly supplied data and requires all observed initial states with consecutive zero-based IDs at Period 0.
- `one_step_ahead` retains its conditional prediction interpretation.
- `simulation.n_simulation_periods` accepts `null` or the saved decision horizon; select shorter displayed periods from the saved output.

- For a policy counterfactual, use `operation="counterfactual"` and `scenario.parameter_changes`, an array of `{category,name,value}` records for adopted `wage_` or `nonpec_` utility parameters.
- All other parameter coordinates, structural options, initial distributions, discounting, shocks and transitions remain fixed.
- Both scenarios call the native simulator with the saved seeds.
- The result saves complete native histories and scenario parameters, compares initial-state dataframes and base-draw SHA-256 values, and records the preserved parameter block and transition/shock definitions under `fullresults.counterfactual_invariants`.

- Optional `welfare` requires `discounting` and `population_weights`.
- `discounting="exponential"` aggregates each person's chosen native `Flow_Utility` with their discount factor over the complete horizon and requires native `Present_Bias=1`.
- `quasi_hyperbolic_initial_self` additionally applies the initial self's present-bias parameter to future flows.
- `population_weights` is `"equal"`, a vector in sorted Identifier order, or an object keyed by every Identifier.
- Weights normalize to one.
- The native finite-horizon terminal continuation value is zero.
- The result saves individual discounted utility, population weights, baseline/scenario welfare and their difference.
- It uses the realized chosen flow including reward shocks; wage measurement error and continuation value are not added to those flows.

- Top-level `computation`, `parameter_definition`, `normalization`, `equilibrium_selection`, `horizon`, `solver` and `welfare_definition` accompany the standard `statistics`, `displays` and `provenance`.
- Tables use saved parameter rows, criterion/welfare statistics and simulated period-choice shares.
- `fit_path` reuses parameters and performs no estimation.
- Each invocation gives the native state-space cache its own temporary location while preserving the structural options.
