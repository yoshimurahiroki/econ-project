## Household consumption and savings

- Set `model="consumption_saving"` and run `python skills/econ-data/scripts/research_macro_extended.py run SPEC.json --output RESULT.json`.
- The existing selector binds `MC-hark-consumption-saving` to this command.
- `income_process="perfect_foresight"` calls HARK's `PerfForesightConsumerType`; `"idiosyncratic_shocks"` calls `IndShockConsumerType`.
- Both classes solve the household's finite-life problem at the supplied income and return processes through their official `solve()` method.
- The [pinned HARK 0.17.2 implementation](https://github.com/econ-ark/HARK/blob/269085077b84cb50feb49d0cd54bbf4da5fa3199/HARK/ConsumptionSaving/ConsIndShockModel.py) owns the numerical solution.

- Supply `calibration_source` and `consumer_options` containing `cycles=1`, positive integer `T_cycle`, `CRRA`, `DiscFac`, and the native `Rfree`, `LivPrb`, `PermGroFac` profiles and `BoroCnstArt`.
- Include the adopted shock, integration and asset-grid parameters for `IndShockConsumerType`, with `vFuncBool=true`.
- These are fixed or previously estimated primitives.
- The runner preserves the supplied options and saves `effective_consumer_options`, including native defaults, with the actual package version.
- It also saves the constructed income-shock support and probabilities, `aXtraGrid` measured above the natural borrowing bound, and the initial asset/permanent-income distributions used by a requested simulation.

- `evaluation.mNrm` declares the normalized resource points; `evaluation.periods` selects ages from zero through `T_cycle`, defaulting to all solution ages.
- Each point must exceed that age's solved resource minimum.
- The output saves consumption `cNrm`, end-of-period assets `aNrm=mNrm-cNrm`, normalized value, and the resource minimum.
- At nonterminal ages it also saves the original Euler gap `1-c^CRRA*DiscFac*LivPrb*Rfree*E[(PermGroFac*PermShk)^(-CRRA)*c_next^(-CRRA)]`, the borrowing slack and their product.
- An interior optimum has zero Euler gap; a binding borrowing limit has a nonnegative gap and zero slack.
- The terminal household consumes all resources.

- Optional `evaluation.weights` gives nonnegative population masses summing to one on the resource points.
- The runner saves weighted consumption and value at each selected age.
- Optional `scenario.consumer_options` supplies changed native parameters and preserves the lifecycle horizon and CRRA normalization.
- Both scenarios use the same evaluation population, and the result saves their weighted differences.
- Consumption and assets are goods per unit of permanent income; values are normalized expected discounted CRRA utility.
- Market-clearing prices and monetary welfare use their adopted additional equations and execution owners.

- For histories, supply `simulation` with `AgentCount`, `T_sim`, integer `seed` and a list of distinct `track_vars`; declare `kLogInitMean`, `kLogInitStd`, `pLogInitMean` and `pLogInitStd` in `consumer_options`.
- The runner calls `initialize_sim()` and `simulate()` and saves the returned period-by-household histories.
- Policy and value displays, named statistics, equations, input and producer hashes enter the existing research artifact path.
- Saving figures or prose reuses these quantities.

## Lifecycle regimes, native solutions and forward histories

- Set `model="lifecycle_choice"` and run the same `research_macro_extended.py run SPEC.json --output RESULT.json` command.
- `lifecycle_run` constructs the declared official `lcm.Model`, calls its selected regime solvers, saves the complete native solution, and passes that solution to forward simulation.
- The [pylcm source revision `0fb55673b0be4eb52d270b2585047faa38c4e930`](https://github.com/OpenSourceEconomics/pylcm/tree/0fb55673b0be4eb52d270b2585047faa38c4e930) installs as `0.0.2.dev261+g0fb55673b`; the executed solution and solver API versions are both 3.
- Restore `requirements-lifecycle.txt` in Python 3.14.
- Its NumPy, JAX and pandas dependencies use their own environment.
- The HARK, OLG and Aiyagari paths keep their existing macro environment.

The specification's `operation` determines the computation:

| Operation | Inputs and executed result |
| --- | --- |
| `solve` | `model_definition`, `parameters`, `calibration_source`, and a new `solution_path`; construct the model, call `Model.solve`, and atomically save its values and solver-specific policy-replay artifacts through `lcm.persistence.save_solution`. |
| `simulate` | The same model and parameter declarations, `saved_solution:{path,sha256}`, and `simulation`; load the declared complete archive and call `Model.simulate(solution=...)`. |
| `counterfactual` | The saved baseline solution and the same simulation population and random inputs, plus `scenario.parameters` and `scenario.solution_path`; replay the baseline, solve the changed parameters, and simulate its own policies. `scenario.parameters` recursively overrides the corresponding baseline keys. An already solved scenario uses its own `scenario.saved_solution:{path,sha256}`. |
- `parameter_status` is `fixed`, `calibrated` or `estimated`, with `calibration_source` identifying the supplied values or producing estimate.
- These three operations keep supplied parameters fixed during each solve.
- The output's `computation` records the requested operation, actual `operations_executed`, scenario-specific native calls and `parameter_operation`.
- Each scenario's solution record retains its archive path and SHA-256, model and parameter fingerprints, native solver types, API versions and reuse status.
- Use a distinct `solution_path` for each new solve; reuse a completed archive through `saved_solution`.

### Declare the adopted model

- Supply `model_definition:{"module":"analysis/lifecycle_model.py","sha256":"SOURCE_SHA256","factory":"build_model","kwargs":{...}}`.
- Relative paths resolve against the specification directory.
- The runner verifies the source bytes and calls `build_model(**kwargs)`.
- The factory returns a native `lcm.Model` containing the adopted states, actions, utility, constraints, shocks, transition graph, terminal regimes, fixed parameters, grids and solver configuration.
- `parameters` supplies the native `params` mapping; numeric JSON arrays become native JAX arrays at that boundary.
- The source hash, constructor arguments, actual solver declarations and native fingerprints remain attached to the result.

- The [official solver contract](https://github.com/OpenSourceEconomics/pylcm/blob/0fb55673b0be4eb52d270b2585047faa38c4e930/src/lcm/solvers.py) chooses the numerical representation.
- Ordinary `Regime` uses `GridSearch`.
- `ConsumptionSavingsRegime` with a declared `LiquidMargin` supplies `EGM`, `DCEGM` or `NBEGM`; the nested declaration supplies `NEGM` or `NNBEGM`.
- The factory owns this choice and its settings.
- The runner invokes the resulting native solver directly.
- `DCEGM`'s `ExactEnvelope` uses pylcm's installed native payload and its matched JAX version.

- For a project model, provide `definitions` with `equations`, `normalization`, `equilibrium_selection`, `welfare_definition` and `parameter_definition`.
- Each parameter definition supplies its role, source and unit.
- `outcomes` binds exactly `consumption`, `assets`, `employment`, `income` and `utility` to native simulation columns using `{column,unit}`.
- `fill_by_regime:{regime:value}` supplies a declared inactive or terminal value where the native column is absent.
- For example, an employment function defined during working life can assign zero in retirement and death.
- Define whether the asset column is beginning-of-period wealth or end-of-period savings through its unit and equation.
- `welfare.discount_factor` defines the discount factor used to aggregate the reported flow utility.

- `simulation` requires `initial_conditions`, `weights`, integer `seed` and integer `taste_shock_seed`.
- The initial-condition vectors retain their original person order and include the native model's clock (`age` or `period`), `regime_id` and required states.
- Weights give nonnegative initial population masses summing to one.
- Optional `shock_paths` passes the adopted realized paths directly to the official simulation interface.
- Baseline and counterfactual receive the same initial vectors, weights, seeds and supplied paths.
- Native `SimulationResult.to_dataframe` provides the returned state, action, value and function columns; the output preserves those rows and their person/period coordinates.
- The official result's random-stream identity is saved with them.

- Optional `evaluation:[{period,regime,states:{state:[...]}}]` evaluates policies at adopted state points through `Model.lookup_policy`.
- Each result retains the state coordinates, actions, values, conditional continuous actions, discrete-choice probabilities and categorical action labels.
- `evaluation.action_units` supplies units for continuous actions outside the declared outcome columns.
- `value_functions` contains the solved state axes, coordinates, finite values and finite-value masks; the native archive preserves the complete values and replay artifacts.
- A loaded solution's canonical parameter and durable model identities are checked by native policy lookup and simulation before they are consumed.

- The runner saves initial-population-weighted decision value and the weighted sum of discounted realized utility as separate quantities.
- Discounting for a person's history starts at that person's entry period.
- Period means use the weight mass observed in that period and retain that denominator.
- Counterfactual differences subtract the corresponding baseline quantity.
- Native histories, policy evaluations, value arrays, named `statistics`, and `displays` all carry the same source/specification, model contract, parameter definitions, horizon and welfare units.
- Gallery rendering and Writing consume these saved quantities.

### Published retirement model

- `model_definition="iskhakov_et_al_2017"` selects the [official retirement model](https://github.com/OpenSourceEconomics/pylcm/blob/0fb55673b0be4eb52d270b2585047faa38c4e930/src/lcm_examples/iskhakov_et_al_2017.py).
- Set `solver="grid_search"` or `"dcegm"`, and supply `n_periods` including the final death period.
- The factory declares working life, absorbing retirement and death; initial age is 40 and model periods span ten years.
- The four supplied parameters are `discount_factor`, `disutility_of_work`, `interest_rate` and `wage`.
- The published analytical-solution parameterization uses six periods and values `(0.98,1,0,20)` in that order.

- The worker chooses consumption and work or retirement.
- Flow utility is `log(c)-disutility_of_work*1[work]`.
- Savings are `a=wealth-c>=0`, and next-period wealth is `(1+interest_rate)*a+wage*1[work]`.
- The continuous-action terminal optimum consumes all available wealth; death has value zero.
- GridSearch chooses the largest feasible point on its declared consumption grid in the final living period.
- This example has deterministic income and death.
- Its output records the official wealth, consumption and savings grids, DC-EGM envelope settings and state coordinates.
- The `assets` outcome is end-of-period savings.
- The runner evaluates the original wealth transition, the nonnegative savings constraint and the selected terminal optimum on every simulated person path.
- It retains terminal unspent wealth separately from the optimality residual, comparing GridSearch's final choice with its largest feasible grid point and DC-EGM's with available wealth.

For a baseline solve, the core input is:

```json
{"model":"lifecycle_choice","operation":"solve","model_definition":"iskhakov_et_al_2017","solver":"dcegm","n_periods":6,"parameters":{"discount_factor":0.98,"disutility_of_work":1.0,"interest_rate":0.0,"wage":20.0},"calibration_source":"Iskhakov et al. (2017), official pylcm analytical-solution parameterization","solution_path":"baseline.lcm","evaluation":[{"period":0,"regime":"working_life","states":{"wealth":[10,30,60,100,200]}}]}
```
- For forward simulation, select `operation="simulate"`, bind the returned archive as `saved_solution`, and supply `simulation.initial_conditions={wealth:[10,30,60,100,200],regime_id:[0,0,0,0,0],age:[40,40,40,40,40]}`, `weights=[0.2,0.2,0.2,0.2,0.2]`, and the adopted seeds.
- A wage counterfactual selects `operation="counterfactual"` with `scenario:{parameters:{wage:25},solution_path:"wage25.lcm"}` and the same baseline archive and simulation inputs.
- The utility normalization, discount factor and work disutility remain fixed in this published-model comparison.
