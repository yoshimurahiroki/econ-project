#!/usr/bin/env python3
"""Macro equilibria: run SPEC --output FILE or case --model olg|aiyagari --output NEWDIR."""
import argparse
import csv
import io
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import scipy
from scipy.optimize import brentq, least_squares
from importlib.metadata import version


def olg_sequence_block(K, Z, effective_a, labor, alpha, save, income_share):
    Y = Z*effective_a*K(-1)**alpha*labor**(1-alpha)
    clearing = K-save*income_share*Y
    return Y, clearing


def hark_lifecycle(beta):
    # An independent two-period CRRA=2 example with a unit old-age endowment.
    from HARK.ConsumptionSaving.ConsIndShockModel import PerfForesightConsumerType
    gross_return = 1.04
    assets = 2.0
    consumer = PerfForesightConsumerType(cycles=1, T_cycle=1, CRRA=2., DiscFac=beta,
        Rfree=[gross_return], LivPrb=[1.], PermGroFac=[1.], BoroCnstArt=0.)
    consumer.solve()
    consumption = float(consumer.solution[0].cFunc(assets))
    analytic = (gross_return*assets+1)/(gross_return+np.sqrt(beta*gross_return))
    if abs(consumption-analytic) > 1e-8: raise ArithmeticError('HARK lifecycle Euler check failed')
    return {'engine':'HARK PerfForesightConsumerType.solve', 'CRRA':2., 'discount_factor':beta,
        'gross_return':gross_return,'young_resources':assets,'old_endowment':1.,
        'young_consumption':consumption,'saving':assets-consumption,
        'old_consumption':gross_return*(assets-consumption)+1.,
        'analytic_consumption':float(analytic),'analytic_abs_error':abs(consumption-analytic)}


def atomic_write(path, obj):
    payload = json.dumps(obj, indent=2, allow_nan=False) + '\n'
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix='.'+path.name+'.', delete=False) as stream:
            temp = Path(stream.name)
            stream.write(payload)
        os.replace(temp, path)
    finally:
        if temp is not None: temp.unlink(missing_ok=True)


def publish_case(output, spec, runner):
    output = output.resolve()
    if output.exists(): raise FileExistsError(f'output already exists: {output}')
    source = next((p/'harness/local_checks.py' for p in Path(__file__).resolve().parents if (p/'harness/local_checks.py').is_file()), None)
    if source is None: raise FileNotFoundError('harness/local_checks.py is required')
    module_spec = importlib.util.spec_from_file_location('macro_case_local_checks', source)
    gate = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(gate)
    with tempfile.TemporaryDirectory(prefix='.macro-case-', dir=output.parent) as temp:
        stage = Path(temp)
        atomic_write(stage/'spec.json', spec)
        result = runner(spec)
        result['provenance']['spec_sha256'] = hashlib.sha256((stage/'spec.json').read_bytes()).hexdigest()
        result['provenance']['producer_sha256'] = hashlib.sha256(Path(runner.__code__.co_filename).read_bytes()).hexdigest()
        atomic_write(stage/'result.json', result)
        gate.atomic_publish(stage, output)


def read_productivity(observations, base_dir):
    """Read the identified, equally spaced observed series from a hash-checked CSV."""
    path = Path(observations['path'])
    if not path.is_absolute(): path = Path(base_dir)/path
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != observations['sha256'].lower():
        raise ValueError('productivity CSV SHA-256 does not match the declared source')
    period_column = observations['period_column']
    value_column = observations['value_column']
    if not isinstance(period_column, str) or not isinstance(value_column, str) or period_column == value_column:
        raise ValueError('distinct period and value column IDs are required')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    if reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames) or not {period_column,value_column}.issubset(reader.fieldnames):
        raise ValueError('productivity CSV requires unique named period and value columns')
    periods, values = [], []
    for row in reader:
        if None in row: raise ValueError('productivity CSV contains rows with extra fields')
        periods.append(int(row[period_column]))
        values.append(float(row[value_column]))
    if not periods or any(b != a+1 for a,b in zip(periods, periods[1:])):
        raise ValueError('productivity periods must be consecutive ordered integers')
    values = np.asarray(values,dtype=float)
    if not np.isfinite(values).all(): raise ValueError('productivity values must be finite')
    return values, {'path':observations['path'], 'sha256':digest, 'period_column':period_column,
        'value_column':value_column, 'first_period':periods[0], 'last_period':periods[-1], 'rows':len(periods)}


def write_productivity_case(stage, values, source):
    path = stage/'observed-productivity.csv'
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['period','log_productivity'])
        writer.writerows((i,repr(float(x))) for i,x in enumerate(values))
    return {'type':'synthetic','source':source,'path':path.name,
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'period_column':'period','value_column':'log_productivity'}


def publish_observed_case(output, generator, runner):
    output = output.resolve()
    if output.exists(): raise FileExistsError(f'output already exists: {output}')
    source = next((p/'harness/local_checks.py' for p in Path(__file__).resolve().parents if (p/'harness/local_checks.py').is_file()), None)
    if source is None: raise FileNotFoundError('harness/local_checks.py is required')
    module_spec = importlib.util.spec_from_file_location('macro_observed_local_checks',source)
    gate = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(gate)
    with tempfile.TemporaryDirectory(prefix='.macro-observed-', dir=output.parent) as temp:
        stage = Path(temp)
        specification = generator(stage)
        atomic_write(stage/'spec.json', specification)
        result = runner(specification, stage)
        result['provenance']['spec_sha256'] = hashlib.sha256((stage/'spec.json').read_bytes()).hexdigest()
        result['provenance']['producer_sha256'] = hashlib.sha256(Path(runner.__code__.co_filename).read_bytes()).hexdigest()
        atomic_write(stage/'result.json', result)
        gate.atomic_publish(stage,output)


def solve(spec, base_dir=Path.cwd()):
    model = spec.get('model', 'olg')
    if model == 'aiyagari':
        return solve_aiyagari(spec)
    if model != 'olg':
        raise ValueError('model must be olg or aiyagari')
    p = spec['parameters']
    alpha, beta, delta = (float(p[k]) for k in ('alpha','beta','delta'))
    shares = np.asarray(p['household_weights'], dtype=float)
    efficiency = np.asarray(p['household_efficiency'], dtype=float)
    firm_shares = np.asarray(p['firm_labor_shares'], dtype=float)
    firm_a = np.asarray(p['firm_productivity'], dtype=float)
    if not (0 < alpha < 1 and 0 < beta < 1 and 0 <= delta < 1): raise ValueError('invalid preference or technology')
    if (len(shares)==0 or shares.shape != efficiency.shape or len(firm_shares)==0 or firm_shares.shape != firm_a.shape or
        not all(np.isfinite(x).all() for x in (shares,efficiency,firm_shares,firm_a)) or
        min(shares.min(),efficiency.min(),firm_shares.min(),firm_a.min()) <= 0 or
        abs(shares.sum()-1)>1e-10 or abs(firm_shares.sum()-1)>1e-10):
        raise ValueError('positive shares and productivity are required, with shares summing to one')
    labor = float(shares @ efficiency)
    # Heterogeneous firms rent capital competitively conditional on exogenous labor shares.
    scale = float(firm_shares @ firm_a**(1/(1-alpha)))
    aggregate_a = scale**(1-alpha)
    alloc = firm_shares*firm_a**(1/(1-alpha))/scale
    obs, observed_source = read_productivity(spec['observations'], base_dir)
    if len(obs)<4 or not np.isfinite(obs).all() or np.linalg.norm(obs[:-1]) < 1e-10:
        raise ValueError('at least four varying finite log-productivity observations required')
    fit = least_squares(lambda x: obs[1:]-x[0]*obs[:-1], x0=[.5], bounds=([-.99],[.99]), xtol=1e-12, ftol=1e-12, gtol=1e-12)
    rho = float(fit.x[0])
    if not fit.success: raise ArithmeticError(fit.message)
    jac_norm = float(np.linalg.norm(fit.jac))
    def parameters(s):
        markup, collateral, tax = (float(s[k]) for k in ('markup','collateral_income_limit','government_share'))
        if not (markup>=1 and 0 < collateral <= 1 and 0 <= tax < 1): raise ValueError('invalid scenario')
        save = min(beta/(1+beta), collateral)
        coefficient = (1-alpha)/markup + 1-1/markup - tax
        if coefficient <= 0: raise ValueError('government share exhausts young income')
        k = (save*coefficient*aggregate_a*labor**(1-alpha))**(1/(1-alpha))
        return markup, collateral, tax, save, k
    def transition(s, z, initial, initial_saving):
        markup, collateral, tax, save, _ = parameters(s)
        k = initial
        result = []
        previous_saving = initial_saving
        for t, shock in enumerate(z):
            a = aggregate_a*np.exp(shock)
            y = a*k**alpha*labor**(1-alpha)
            wage = (1-alpha)*y/(markup*labor)
            rent = alpha*y/(markup*k)
            dividend = (1-1/markup)*y
            gov = tax*y
            income = wage*efficiency+(dividend-gov)
            if np.min(income)<=0: raise ValueError('scenario generates nonpositive household income')
            saving = save*income
            cy = income-saving
            co = (1-delta+rent)*previous_saving
            knew = float(shares@saving)
            resources = float(shares@cy + shares@co + gov + knew - ((1-delta)*k+y))
            marginal = beta/saving-1/cy
            next_z = z[t+1] if t+1 < len(z) else z[t]*rho
            next_y = aggregate_a*np.exp(next_z)*knew**alpha*labor**(1-alpha)
            next_return = 1-delta+alpha*next_y/(markup*knew)
            result.append({'period':t,'capital':k,'next_capital':knew,'output':y,'wage':wage,'rental_rate':rent,
                'government_absorption':gov,'profits':dividend,'firm_capital':(alloc*k).tolist(),
                'young_income':income.tolist(),'young_consumption':cy.tolist(),'old_consumption':co.tolist(),
                'saving':saving.tolist(),'distribution_weights':shares.tolist(),'investment':knew-(1-delta)*k,
                'resource_residual':resources,'capital_market_residual':float(knew-shares@saving),
                'saving_constraint_slack':(collateral*income-saving).tolist(),
                'saving_constraint_multiplier':marginal.tolist(),
                'cohort_welfare':(np.log(cy)+beta*np.log(next_return*saving)).tolist()})
            previous_saving = saving
            k = knew
        return result
    base = spec['baseline']; scenario = spec['scenario']
    _,_,_,_, k0 = parameters(base)
    horizon = int(spec['horizon'])
    if horizon < 2: raise ValueError('horizon must be at least two')
    shock = float(spec['technology_shock'])
    z = [shock*rho**t for t in range(horizon)]
    base_markup, _, base_tax, base_save, _ = parameters(base)
    base_y = aggregate_a*k0**alpha*labor**(1-alpha)
    initial_saving = base_save*((1-alpha)*base_y/(base_markup*labor)*efficiency + (1-1/base_markup-base_tax)*base_y)
    baseline = transition(base, [0.]*horizon, k0, initial_saving)
    scenario_path = transition(scenario, z, k0, initial_saving)
    # Sequence-space Jacobian at the baseline steady state, dY_t / dz_s.
    # K_{t+1}=constant*exp(z_t)*K_t**alpha implies d log Y_t / dz_s=alpha**(t-s).
    sequence_jacobian = np.zeros((horizon, horizon))
    for t in range(horizon):
        for j in range(t+1):
            sequence_jacobian[t, j] = baseline[t]['output']*alpha**(t-j)
    base_markup, _, base_tax, base_save, _ = parameters(base)
    income_share = (1-alpha)/base_markup + 1-1/base_markup-base_tax
    from sequence_jacobian import simple
    sequence_block = simple(olg_sequence_block)
    sequence_ss = sequence_block.steady_state({'K':k0, 'Z':1., 'effective_a':aggregate_a,
        'labor':labor, 'alpha':alpha, 'save':base_save, 'income_share':income_share})
    official_jacobian = np.asarray(sequence_block.solve_jacobian(sequence_ss, unknowns=['K'],
        targets=['clearing'], inputs=['Z'], outputs=['Y'], T=horizon)['Y']['Z'])
    official_error = float(np.max(np.abs(official_jacobian-sequence_jacobian)))
    if official_error > 1e-7: raise ArithmeticError(f'official sequence Jacobian residual {official_error}')
    step = 1e-5
    numerical_jacobian = np.empty_like(sequence_jacobian)
    for j in range(horizon):
        perturb = np.zeros(horizon)
        perturb[j] = step
        plus = transition(base, perturb, k0, initial_saving)
        minus = transition(base, -perturb, k0, initial_saving)
        numerical_jacobian[:,j] = [(plus[t]['output']-minus[t]['output'])/(2*step) for t in range(horizon)]
    sequence_error = float(np.max(np.abs(sequence_jacobian-numerical_jacobian)))
    if sequence_error > 1e-7: raise ArithmeticError(f'sequence derivative residual {sequence_error}')
    fields = ('capital','next_capital','output','wage','rental_rate','government_absorption')
    irf = [{name: scenario_path[t][name]-baseline[t][name] for name in fields} for t in range(horizon)]
    maxres = max(abs(x['resource_residual']) for x in baseline+scenario_path)
    if maxres > 1e-8: raise ArithmeticError(f'resource residual {maxres}')
    wbase = float(shares@np.asarray(baseline[0]['cohort_welfare']))
    wscenario = float(shares@np.asarray(scenario_path[0]['cohort_welfare']))
    lifecycle = hark_lifecycle(beta)
    stats = {'hark_young_consumption': {'value':lifecycle['young_consumption'],'unit':'normalized goods per young household'},
        'sequence_jacobian_analytic_error': {'value':official_error,'unit':'goods per unit log productivity'},
        'estimated_technology_persistence': {'value':rho,'unit':'AR(1) coefficient'},
        'steady_capital': {'value':k0,'unit':'goods per young cohort'},
        'impact_output_change': {'value':irf[0]['output'],'unit':'goods per period'},
        'impact_cohort_welfare_change': {'value':wscenario-wbase,'unit':'weighted lifetime log utility'},
        'max_resource_residual': {'value':maxres,'unit':'goods per period'},
        'observation_jacobian_norm': {'value':jac_norm,'unit':'log productivity'}}
    return {'model':'two-period overlapping-generations general equilibrium with firm and household heterogeneity',
        'adopted':spec,'scenario':'baseline versus scenario and technology innovation',
        'engine':'closed-form household and firm choices; scipy.optimize.least_squares AR(1)',
        'options':{'optimizer':'least_squares','xtol':1e-12,'ftol':1e-12,'gtol':1e-12},
        'observation':{'type':spec['observations']['type'], 'source':spec['observations']['source'], 'input':observed_source, 'estimand':'conditional AR(1) persistence',
            'equation':'z[t] = rho*z[t-1] + innovation[t]', 'identification':'nonzero lagged productivity variation; innovation orthogonal to lag',
            'optimizer_success':bool(fit.success),'optimizer_cost':float(fit.cost),'jacobian_rank':int(np.linalg.matrix_rank(fit.jac)),
            'innovation_residuals':fit.fun.tolist()},
        'sequence_space_jacobian': {'engine':'sequence_jacobian.simple.solve_jacobian', 'output_to_log_productivity':official_jacobian.tolist(), 'analytic_max_abs_error':official_error, 'difference_step':step, 'finite_difference_max_abs_error':sequence_error},
        'hark_lifecycle_comparison':lifecycle,
        'steady_state':{'baseline_capital':k0,'scenario_capital':parameters(scenario)[4], 'aggregate_productivity':aggregate_a,
            'firm_capital_shares':alloc.tolist()},
        'baseline':baseline,'simulation':scenario_path,'impulse_response':irf,'statistics':stats,
        'provenance':{'python':sys.version.split()[0],'numpy':np.__version__,'scipy':scipy.__version__, 'sequence_jacobian':version('sequence-jacobian'), 'HARK':version('econ-ark')}}


def solve_aiyagari(spec):
    """Solve finite-grid household choices and their stationary capital market."""
    from quantecon import MarkovChain
    from quantecon.markov import DiscreteDP
    from scipy.sparse import csr_matrix

    p, options = spec['parameters'], spec['solver']
    alpha, beta, delta, crra = (float(p[key]) for key in ('alpha', 'beta', 'delta', 'crra'))
    if not (0 < alpha < 1 and 0 < beta < 1 and 0 <= delta < 1 and np.isfinite(crra) and crra > 0):
        raise ValueError('Aiyagari requires alpha and beta in (0,1), delta in [0,1), and positive finite crra')
    assets = np.asarray(p['asset_grid'], dtype=float)
    income = np.asarray(p['income_states'], dtype=float)
    transition = np.asarray(p['income_transition'], dtype=float)
    if (assets.ndim != 1 or len(assets) < 3 or not np.isfinite(assets).all() or
            np.any(np.diff(assets) <= 0) or assets[-1] <= 0):
        raise ValueError('asset_grid requires at least three finite increasing points and a positive maximum')
    if income.ndim != 1 or len(income) < 2 or not np.isfinite(income).all() or np.any(income <= 0):
        raise ValueError('income_states requires at least two positive finite labor efficiencies')
    if (transition.shape != (len(income), len(income)) or not np.isfinite(transition).all() or
            np.any(transition < 0) or np.max(np.abs(transition.sum(axis=1)-1)) > 1e-12):
        raise ValueError('income_transition must be a finite nonnegative row-stochastic matrix')
    income_chain = MarkovChain(transition)
    if not income_chain.is_irreducible:
        raise ValueError('income_transition must be irreducible')
    income_distribution = income_chain.stationary_distributions[0]
    labor = float(income_distribution @ income)
    bracket = np.asarray(options['capital_bracket'], dtype=float)
    if bracket.shape != (2,) or not np.isfinite(bracket).all() or not 0 < bracket[0] < bracket[1]:
        raise ValueError('capital_bracket requires two increasing positive finite values')
    tolerance_names = ('capital_tolerance', 'bellman_tolerance', 'distribution_tolerance', 'resource_tolerance')
    tolerances = {key: float(options[key]) for key in tolerance_names}
    if not all(np.isfinite(value) and value > 0 for value in tolerances.values()):
        raise ValueError('solver tolerances must be positive and finite')
    max_iterations = options['max_iterations']
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations < 2:
        raise ValueError('max_iterations must be an integer of at least two')
    if not isinstance(spec['calibration_source'], str) or not spec['calibration_source'].strip():
        raise ValueError('calibration_source must identify the supplied calibrated primitives')
    na, nz = len(assets), len(income)
    state_assets = np.repeat(assets, nz)
    state_income = np.tile(np.arange(nz), na)
    nstates = na*nz
    equations = {
        'utility': 'log(c)' if crra == 1 else 'c**(1-crra)/(1-crra)',
        'budget': 'c(a,z) + g(a,z) = w*z + (1+r)*a; c>0; g in asset_grid',
        'bellman': 'V(a,z) = max_a_prime {u(w*z+(1+r)*a-a_prime) + beta*sum_z_prime P[z,z_prime]*V(a_prime,z_prime)}',
        'distribution': 'mu(a_prime,z_prime) = sum_a,z mu(a,z)*1[g(a,z)=a_prime]*P[z,z_prime]',
        'firm': 'Y=A*K**alpha*L**(1-alpha); r=alpha*Y/K-delta; w=(1-alpha)*Y/L',
        'capital_market': 'K = sum_a,z mu(a,z)*a',
        'resource': 'Y = C + delta*K',
        'welfare': 'sum_a,z mu(a,z)*V(a,z), using each scenario stationary distribution',
    }

    def equilibrium(productivity):
        if not np.isfinite(productivity) or productivity <= 0:
            raise ValueError('scenario productivity must be positive and finite')
        evaluations = []

        def household(capital):
            output = productivity*capital**alpha*labor**(1-alpha)
            rate = alpha*output/capital-delta
            wage = (1-alpha)*output/labor
            consumption = wage*income[state_income, None] + (1+rate)*state_assets[:, None] - assets[None, :]
            feasible = consumption > 0
            if not feasible.any(axis=1).all():
                raise ValueError(f'positive consumption is infeasible in a household state at capital {capital}')
            state_indices, action_indices = np.nonzero(feasible)
            flow = np.full(consumption.shape, -np.inf)
            positive = consumption[feasible]
            flow[feasible] = np.log(positive) if crra == 1 else positive**(1-crra)/(1-crra)
            if not np.isfinite(flow[feasible]).all():
                raise ArithmeticError('household utility is nonfinite at the supplied calibration')
            rows = np.repeat(np.arange(len(state_indices)), nz)
            columns = (action_indices[:, None]*nz + np.arange(nz)).ravel()
            probabilities = transition[state_income[state_indices]].ravel()
            kernel = csr_matrix((probabilities, (rows, columns)), shape=(len(state_indices), nstates))
            problem = DiscreteDP(flow[feasible], kernel, beta, state_indices, action_indices)
            fitted = problem.solve(method='policy_iteration', max_iter=max_iterations)
            value, policy = fitted.v, fitted.sigma
            expected_value = value.reshape(na, nz) @ transition.T
            objective = flow + beta*expected_value[:, state_income].T
            bellman = float(np.max(np.abs(value-objective.max(axis=1))))
            chosen = objective[np.arange(nstates), policy]
            policy_residual = float(np.max(np.abs(value-chosen)))
            if not np.isfinite(value).all() or max(bellman, policy_residual) > tolerances['bellman_tolerance']:
                raise ArithmeticError(f'household Bellman residual {bellman}, policy residual {policy_residual}')
            stationary = fitted.mc.stationary_distributions
            if len(stationary) != 1:
                raise ArithmeticError(f'household policy induces {len(stationary)} recurrent classes; a unique stationary distribution is required')
            distribution = stationary[0]
            propagated = np.zeros(nstates)
            next_states = policy[:, None]*nz+np.arange(nz)
            np.add.at(propagated, next_states.ravel(), (distribution[:, None]*transition[state_income]).ravel())
            stationarity = float(np.max(np.abs(propagated-distribution)))
            mass = float(abs(distribution.sum()-1))
            income_residual = float(np.max(np.abs(distribution.reshape(na, nz).sum(axis=0)-income_distribution)))
            if (not np.isfinite(distribution).all() or distribution.min() < 0 or
                    max(stationarity, mass, income_residual) > tolerances['distribution_tolerance']):
                raise ArithmeticError(f'stationary distribution residual {stationarity}, mass residual {mass}, income marginal residual {income_residual}')
            chosen_consumption = consumption[np.arange(nstates), policy]
            capital_supply = float(distribution @ state_assets)
            aggregate_consumption = float(distribution @ chosen_consumption)
            aggregate_flow = float(distribution @ flow[np.arange(nstates), policy])
            welfare = float(distribution @ value)
            diagnostics = {'bellman_max_residual': bellman, 'policy_value_max_residual': policy_residual,
                'stationarity_max_residual': stationarity, 'mass_residual': mass,
                'income_marginal_max_residual': income_residual,
                'household_budget_max_residual': float(np.max(np.abs(chosen_consumption + assets[policy] -
                    wage*income[state_income] - (1+rate)*state_assets))),
                'capital_market_residual': float(capital-capital_supply),
                'resource_residual': float(output-aggregate_consumption-delta*capital),
                'minimum_consumption': float(chosen_consumption.min()),
                'upper_grid_mass': float(distribution.reshape(na, nz)[-1].sum()),
                'lower_grid_mass': float(distribution.reshape(na, nz)[0].sum()),
                'stationary_welfare_identity_residual': float(abs(welfare-aggregate_flow/(1-beta)))}
            result = {'productivity': productivity, 'capital': float(capital), 'capital_supply': capital_supply,
                'labor': labor, 'output': float(output), 'consumption': aggregate_consumption,
                'investment': float(delta*capital), 'interest_rate': float(rate), 'wage': float(wage),
                'policy_indices': policy.reshape(na, nz).tolist(), 'asset_policy': assets[policy].reshape(na, nz).tolist(),
                'consumption_policy': chosen_consumption.reshape(na, nz).tolist(),
                'value': value.reshape(na, nz).tolist(), 'distribution': distribution.reshape(na, nz).tolist(),
                'stationary_mean_value': welfare, 'stationary_mean_flow_utility': aggregate_flow,
                'diagnostics': diagnostics, 'policy_iterations': int(fitted.num_iter),
                'stationary_recurrent_classes': len(stationary)}
            evaluations.append({'capital': float(capital), 'capital_supply': capital_supply,
                                'capital_market_residual': diagnostics['capital_market_residual']})
            return result

        candidates = {}

        def clearing(capital):
            if capital not in candidates:
                candidates[capital] = household(capital)
            return candidates[capital]['diagnostics']['capital_market_residual']

        # The finite-grid supply curve has jumps; acceptance uses its actual market residual.
        endpoint_residuals = [clearing(float(capital)) for capital in bracket]
        if 0. in endpoint_residuals:
            root = float(bracket[endpoint_residuals.index(0.)])
            converged, termination, iterations = True, 'exact equilibrium at bracket endpoint', 0
        else:
            root, solved = brentq(clearing, *bracket, xtol=1e-12, rtol=1e-12,
                                  maxiter=max_iterations, full_output=True, disp=False)
            converged, termination, iterations = bool(solved.converged), solved.flag, int(solved.iterations)
        clearing(root)
        result = min(candidates.values(), key=lambda row: abs(row['diagnostics']['capital_market_residual']))
        diagnostic = result['diagnostics']
        if (not converged or abs(diagnostic['capital_market_residual']) > tolerances['capital_tolerance'] or
                abs(diagnostic['resource_residual']) > tolerances['resource_tolerance']):
            raise ArithmeticError(f'Aiyagari equilibrium failed: capital residual {diagnostic["capital_market_residual"]}, resource residual {diagnostic["resource_residual"]}, root termination {termination}')
        result['market_solver'] = {'method': 'scipy.optimize.brentq', 'converged': converged,
            'termination': termination, 'iterations': iterations, 'evaluations': evaluations,
            'returned_root': float(root), 'selected_capital': result['capital'], 'xtol': 1e-12, 'rtol': 1e-12}
        return result

    baseline = equilibrium(float(spec['baseline']['productivity']))
    scenario = equilibrium(float(spec['scenario']['productivity']))
    if crra == 1:
        equivalent = np.expm1((1-beta)*(scenario['stationary_mean_value']-baseline['stationary_mean_value']))
    else:
        equivalent = (scenario['stationary_mean_value']/baseline['stationary_mean_value'])**(1/(1-crra))-1
    equilibrium_rows, policy_rows, distribution_rows, welfare_rows, diagnostic_rows = [], [], [], [], []
    aggregate_units = {'capital': 'goods per household', 'capital_supply': 'goods per household',
        'output': 'goods per household per period', 'consumption': 'goods per household per period',
        'investment': 'goods per household per period', 'interest_rate': 'net return per period',
        'wage': 'goods per efficiency unit of labor'}
    for name, solution in (('baseline', baseline), ('scenario', scenario)):
        equilibrium_rows.extend({'scenario': name, 'statistic': key, 'value': solution[key], 'unit': unit}
                                for key, unit in aggregate_units.items())
        welfare_rows.append({'scenario': name, 'statistic': 'stationary_mean_value',
                             'value': solution['stationary_mean_value'], 'unit': 'expected discounted utility per household'})
        for key, value in solution['diagnostics'].items():
            unit = ('goods per household' if key == 'capital_market_residual' else
                    'goods per household per period' if key in ('resource_residual', 'minimum_consumption', 'household_budget_max_residual') else
                    'utility' if key in ('bellman_max_residual', 'policy_value_max_residual', 'stationary_welfare_identity_residual') else 'probability')
            diagnostic_rows.append({'scenario': name, 'statistic': key, 'value': value, 'unit': unit})
        for ia, asset in enumerate(assets):
            for iz, efficiency in enumerate(income):
                state = {'scenario': name, 'asset': float(asset), 'income_state': iz,
                         'income': float(efficiency), 'series': f'{name}: income {efficiency:g}'}
                policy_rows.append({**state, 'value': solution['asset_policy'][ia][iz], 'unit': 'goods per household'})
                distribution_rows.append({**state, 'value': solution['distribution'][ia][iz], 'unit': 'population probability'})
    welfare_rows.append({'scenario': 'scenario versus baseline', 'statistic': 'stationary_consumption_equivalent',
                         'value': float(equivalent), 'unit': 'fraction of baseline consumption'})
    common = {'model_contract': 'MC-aiyagari-stationary', 'population': 'Unit mass of infinitely lived households',
              'parameter_status': 'calibrated', 'asset_grid': assets.tolist(), 'income_states': income.tolist()}
    displays = {}
    for name, rows, title, curve in (
        ('equilibrium', equilibrium_rows, 'Stationary general equilibrium', False),
        ('asset_policy', policy_rows, 'Saving policy by asset and income state', True),
        ('distribution', distribution_rows, 'Stationary joint asset and income distribution', True),
        ('welfare', welfare_rows, 'Stationary expected lifetime welfare', False),
        ('diagnostics', diagnostic_rows, 'Original-equation and grid diagnostics', False)):
        columns = [('scenario', 'Scenario'), ('asset', 'Current assets'), ('income', 'Labor efficiency'), ('value', title), ('unit', 'Unit')] if curve else [('scenario', 'Scenario'), ('statistic', 'Statistic'), ('value', 'Value'), ('unit', 'Unit')]
        displays[name] = {'kind': 'structural' if curve else 'table', 'title': title, 'rows': rows,
            'columns': [{'key': key, 'label': label, 'unit': ''} for key, label in columns],
            'metadata': {**common, 'report_role': 'model_fit' if name == 'diagnostics' else 'counterfactual',
                         'unit': rows[0]['unit'] if curve else 'see row-specific unit'},
            'display': {'plot_type': 'line', 'x': 'asset', 'y': 'value', 'series': 'series'} if curve else {'plot_type': 'table'}}
    displays['welfare']['metadata'].update({'value_definition': equations['welfare'],
        'consumption_equivalent': 'Permanent uniform scaling of baseline consumption giving the scenario stationary expected utility; each economy uses its own stationary distribution'})
    statistics = {name+'_capital': {'value': result['capital'], 'unit': 'goods per household'}
                  for name, result in (('baseline', baseline), ('scenario', scenario))}
    statistics['stationary_consumption_equivalent'] = {'value': float(equivalent), 'unit': 'fraction of baseline consumption'}
    return {'model': 'aiyagari', 'adopted': spec, 'model_contract': 'MC-aiyagari-stationary',
        'engine': 'quantecon.markov.DiscreteDP.solve; MarkovChain.stationary_distributions; scipy.optimize.brentq',
        'calibration': {'source': spec['calibration_source'], 'parameters': p, 'estimated_parameters': []},
        'equations': equations, 'options': options, 'income_stationary_distribution': income_distribution.tolist(),
        'state_order': 'asset-major, income-minor; all policies and distributions have shape (assets,incomes)',
        'baseline': baseline, 'scenario': scenario, 'statistics': statistics, 'displays': displays,
        'provenance': {'python': sys.version.split()[0], 'numpy': np.__version__, 'scipy': scipy.__version__,
                       'quantecon': version('quantecon')}}


def aiyagari_example():
    return {'model': 'aiyagari', 'calibration_source': 'Synthetic stationary Aiyagari calibration',
        'parameters': {'alpha': .36, 'beta': .96, 'delta': .08, 'crra': 2.,
            'asset_grid': np.linspace(0., 30., 301).tolist(), 'income_states': [.5, 1.5],
            'income_transition': [[.9, .1], [.1, .9]]},
        'baseline': {'productivity': 1.}, 'scenario': {'productivity': 1.05},
        'solver': {'capital_bracket': [3., 15.], 'capital_tolerance': .005,
            'bellman_tolerance': 1e-9, 'distribution_tolerance': 1e-10,
            'resource_tolerance': .0005, 'max_iterations': 200}}


def example(stage):
    rng = np.random.default_rng(39020)
    obs = [.1]
    for _ in range(100): obs.append(.75*obs[-1]+rng.normal(scale=.03))
    return {'parameters':{'alpha':.36,'beta':.96,'delta':.08,'household_weights':[.5,.5],
        'household_efficiency':[.6,1.4],'firm_labor_shares':[.4,.6],'firm_productivity':[.8,1.2]},
        'observations':write_productivity_case(stage, obs, 'synthetic AR(1), seed 39020, rho .75, innovation sd .03'),
        'baseline':{'markup':1.,'collateral_income_limit':1.,'government_share':0.},
        'scenario':{'markup':1.2,'collateral_income_limit':.35,'government_share':.03},
        'horizon':20,'technology_shock':.05}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['run','case'])
    parser.add_argument('spec',nargs='?',type=Path)
    parser.add_argument('--model',choices=['olg','aiyagari'],help='model for the generated case (default: olg)')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation == 'run':
            if args.spec is None: raise ValueError('run requires a specification')
            if args.model is not None: raise ValueError('run selects its model from the specification')
            raw = args.spec.read_bytes()
            result = solve(json.loads(raw),args.spec.resolve().parent)
            result['provenance']['spec_sha256'] = hashlib.sha256(raw).hexdigest()
            result['provenance']['producer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            atomic_write(args.output,result)
        else:
            if args.spec is not None: raise ValueError('case takes no specification')
            if args.model == 'aiyagari':
                publish_case(args.output,aiyagari_example(),solve)
            else:
                publish_observed_case(args.output,example,solve)
    except (ValueError,KeyError,TypeError,OSError,ArithmeticError) as exc:
        parser.exit(2,f'error: {exc}\n')


if __name__ == '__main__': main()
