#!/usr/bin/env python3
"""Solve the adopted RBC, one-asset HANK or Dolo model: run SPEC --output FILE."""
import argparse
from copy import deepcopy
import hashlib
from importlib.metadata import version
import inspect
import json
from pathlib import Path
import sys
import tempfile
import warnings

import numpy as np
from numpy.polynomial.hermite import hermgauss
import scipy
from scipy.optimize import brentq
import statsmodels
from statsmodels.tsa.arima.model import ARIMA

from research_macro_extended import atomic_write, read_productivity


SSJ_REVISION = 'eb4ac4c3157357a4cacbea4b5a7a281f5b48cab9'
DOLO_REVISION = '33f873eef42d9644b5a0705a63fb3a34de5c2825'
HANK_UNKNOWNS = ['w', 'Y', 'pi']
HANK_TARGETS = ['asset_mkt', 'goods_mkt', 'nkpc_res']
HANK_OUTPUTS = ['w', 'Y', 'pi', 'r', 'A', 'C', 'N', 'NE', 'L', 'Div', 'Tax',
                'asset_mkt', 'goods_mkt', 'labor_mkt', 'nkpc_res']
HANK_UNITS = {'w': 'goods per efficiency unit of labor', 'Y': 'goods per household per period',
              'pi': 'inflation rate per period', 'r': 'real interest rate per period',
              'rstar': 'policy interest rate per period', 'A': 'assets per household',
              'B': 'government debt per household', 'amax': 'assets per household',
              'C': 'goods per household per period', 'N': 'hours per household',
              'NE': 'efficiency units of labor per household', 'L': 'efficiency units of labor per household',
              'Div': 'goods per household per period', 'Tax': 'goods per household per period',
              'asset_mkt': 'assets per household', 'goods_mkt': 'goods per household per period',
              'labor_mkt': 'efficiency units of labor per household', 'nkpc_res': 'inflation-equation residual',
              'nA': 'asset grid points', 'nS': 'income states'}


def package_source_hashes(package, files):
    root = Path(package.__file__).parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}


def numeric_json(value):
    """Preserve native numerical coordinates in the existing JSON result."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: numeric_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [numeric_json(item) for item in value]
    return value


def read_saved_solution(reference, base_dir):
    path = (base_dir / reference['path']).resolve()
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != reference['sha256']:
        raise ValueError('saved_solution.sha256 does not match the selected result')
    return json.loads(raw), {'path': str(path), 'sha256': digest}


def structural_display(rows, metadata, plot=None):
    return {'kind': 'structural', 'rows': rows,
            'columns': [{'key': key, 'label': key, 'unit': ''}
                        for key in (list(rows[0]) if rows else [])],
            'metadata': metadata, 'display': plot or {'plot_type': 'table'}}


def hank_models():
    """Compose the official blocks without executing dag()'s fixed calibration."""
    from sequence_jacobian import create_model
    from sequence_jacobian.examples import hank
    household = hank.hh.add_hetinputs([hank.transfers, hank.wages, hank.make_grids])
    household = household.add_hetoutputs([hank.labor_supply])
    common = [household, hank.firm, hank.monetary, hank.fiscal, hank.mkt_clearing]
    return (create_model(common + [hank.nkpc_ss], name='One-Asset HANK SS'),
            create_model(common + [hank.nkpc], name='One-Asset HANK'), household)


def hank_household_quantities(ss, household, impulse=None, stationary=None):
    """Evaluate the official policies and transition operators, including values."""
    from scipy.sparse.linalg import LinearOperator, gmres
    h = ss.internals['hh']
    beta, eis, frisch, vphi = (ss[key] for key in ('beta', 'eis', 'frisch', 'vphi'))
    if not (0 < beta < 1 and eis > 0 and frisch > 0 and vphi > 0):
        raise ValueError('solved beta, eis, frisch and vphi must define discounted concave utility')
    power = 1 - 1 / eis

    def felicity(c, n):
        if np.any(c <= 0) or np.any(n < 0):
            raise ArithmeticError('HANK policies require positive consumption and nonnegative labor')
        consumption = np.log(c) if power == 0 else c ** power / power
        labor = vphi * n ** (1 + 1 / frisch) / (1 + 1 / frisch)
        return consumption, labor

    exogenous = household.make_exog_law_of_motion(h)
    endogenous = household.make_endog_law_of_motion(h)
    shape, size = h['c'].shape, h['c'].size
    consumption_utility, labor_cost = felicity(h['c'], h['n'])
    flow = consumption_utility - labor_cost
    operator = LinearOperator((size, size), matvec=lambda v:
        (v.reshape(shape) - beta * endogenous.expectation(
            exogenous.expectation(v.reshape(shape)))).ravel(), dtype=float)
    if stationary is None:
        component_values = []
        for component in (consumption_utility, labor_cost):
            solution, info = gmres(operator, component.ravel(), rtol=1e-12, atol=1e-12,
                                   restart=min(size, 200), maxiter=1000)
            if info != 0 or np.max(np.abs(operator @ solution - component.ravel())) > 1e-9:
                raise ArithmeticError('stationary HANK policy-value equation did not meet 1e-9')
            component_values.append(solution.reshape(shape))
        value = component_values[0] - component_values[1]
        baseline_consumption_value = float(np.sum(h['D'] * component_values[0]))
        baseline_labor_cost = float(np.sum(h['D'] * component_values[1]))
    else:
        value = np.asarray(stationary['stationary_value'])
        baseline_consumption_value = stationary['stationary_consumption_utility']
        baseline_labor_cost = stationary['stationary_labor_disutility']
    value_residual = operator @ value.ravel() - flow.ravel()
    steady_welfare = float(np.sum(h['D'] * value))
    result = {'stationary_value': value, 'stationary_welfare': steady_welfare,
              'stationary_value_residual': value_residual.reshape(shape),
              'stationary_consumption_utility': baseline_consumption_value,
              'stationary_labor_disutility': baseline_labor_cost}
    if impulse is None:
        paths = {key: h[key][None, ...] for key in ('c', 'n', 'a', 'D')}
        levels = {key: np.asarray([ss[key]]) for key in ('r', 'w', 'Div', 'Tax')}
    else:
        paths = {key: impulse.internals['hh'][key] + h[key] for key in ('c', 'n', 'a', 'D')}
        levels = {key: impulse[key] + ss[key] for key in ('r', 'w', 'Div', 'Tax')}
    count = len(paths['c'])
    budget, euler, labor_foc, propagation, mass = [], [], [], [], []
    values = np.empty_like(paths['c'])
    utility = np.empty(count)
    next_value = value
    terminal_distribution = None
    for t in reversed(range(count)):
        c, n, a, distribution = (paths[key][t] for key in ('c', 'n', 'a', 'D'))
        endog_t = household.make_endog_law_of_motion({**h, 'a': a})
        wage = levels['w'][t] * h['e_grid'][:, None]
        transfers = (levels['Div'][t] - levels['Tax'][t]) * h['e_grid'][:, None]
        transfers /= np.sum(h['pi_e'] * h['e_grid'])
        budget.append(c + a - (1 + levels['r'][t]) * h['a_grid'][None, :] - wage * n - transfers)
        next_c = paths['c'][t + 1] if t + 1 < count else h['c']
        next_r = levels['r'][t + 1] if t + 1 < count else ss['r']
        euler.append(c ** (-1 / eis) - beta * (1 + next_r) *
                     endog_t.expectation(exogenous.expectation(next_c ** (-1 / eis))))
        labor_foc.append(vphi * n ** (1 / frisch) - wage * c ** (-1 / eis))
        next_distribution = exogenous.forward(endog_t.forward(distribution))
        if t == count - 1:
            terminal_distribution = next_distribution
        elif impulse is not None:
            propagation.append(next_distribution - paths['D'][t + 1])
        if impulse is None:
            propagation.append(next_distribution - distribution)
        mass.append(float(distribution.sum() - 1))
        uc, un = felicity(c, n)
        utility[t] = np.sum(distribution * (uc - un))
        values[t] = uc - un + beta * endog_t.expectation(exogenous.expectation(next_value))
        next_value = values[t]
    euler = np.asarray(euler[::-1])
    borrowing_slack = paths['a'] - h['a_grid'][0]
    interior = borrowing_slack > 1e-9
    kkt = np.where(interior, euler, np.minimum(euler, 0))
    result['household'] = paths
    result['diagnostics'] = {
        'budget_residual': np.asarray(budget[::-1]),
        'euler_gap': euler, 'borrowing_slack': borrowing_slack,
        'euler_complementarity_residual': kkt,
        'labor_first_order_residual': np.asarray(labor_foc[::-1]),
        'distribution_residual': np.asarray(propagation), 'mass_residual': np.asarray(mass[::-1]),
        'max_budget_residual': float(np.max(np.abs(budget))),
        'max_euler_complementarity_residual': float(np.max(np.abs(kkt))),
        'max_labor_first_order_residual': float(np.max(np.abs(labor_foc))),
        'max_distribution_residual': float(np.max(np.abs(propagation))) if propagation else 0.,
        'max_mass_residual': float(np.max(np.abs(mass))),
        'minimum_consumption': float(paths['c'].min()),
        'minimum_borrowing_slack': float(borrowing_slack.min()),
        'upper_grid_excess': float(max(0., np.max(paths['a'] - h['a_grid'][-1])))}
    if impulse is not None:
        finite_value = float(np.dot(beta ** np.arange(count), utility))
        terminal_value = float(beta ** count * np.sum(terminal_distribution * value))
        welfare = finite_value + terminal_value
        if power == 0:
            equivalent = np.expm1((1 - beta) * (welfare - steady_welfare))
        else:
            ratio = (welfare + baseline_labor_cost) / baseline_consumption_value
            if ratio <= 0:
                raise ArithmeticError('scenario utility lies outside the common consumption-equivalent domain')
            equivalent = ratio ** (1 / power) - 1
        result.update(values=values, period_utility=utility, finite_utility=finite_value,
                      terminal_utility=terminal_value, terminal_distribution=terminal_distribution,
                      welfare=welfare, welfare_change=welfare - steady_welfare,
                      consumption_equivalent=float(equivalent),
                      initial_value_welfare=float(np.sum(h['D'] * values[0])))
        if abs(result['initial_value_welfare'] - welfare) > 1e-9:
            raise ArithmeticError('HANK backward values and forward-distribution welfare disagree')
    return result


def solve_hank(spec, base_dir):
    from research_dynamic import official_package
    identity = official_package('sequence-jacobian', '1.0.0', SSJ_REVISION)
    import sequence_jacobian
    from sequence_jacobian import SteadyStateDict, JacobianDict
    from sequence_jacobian.classes.sparse_jacobians import make_matrix
    operation = spec.get('operation', 'solve_steady_state')
    operations = ('solve_steady_state', 'solve_jacobian', 'solve_impulse_linear', 'solve_impulse_nonlinear')
    if operation not in operations:
        raise ValueError('HANK operation must be one of ' + ', '.join(operations))
    if spec.get('solver_options') and operation != 'solve_impulse_nonlinear':
        raise ValueError('solver_options configures the native nonlinear impulse solver')
    transition = spec.get('transition', {'unknowns': HANK_UNKNOWNS, 'targets': HANK_TARGETS})
    if transition != {'unknowns': HANK_UNKNOWNS, 'targets': HANK_TARGETS}:
        raise ValueError('the adopted HANK closure requires w,Y,pi and asset_mkt,goods_mkt,nkpc_res')
    steady_model, model, household = hank_models()
    executed, reused, saved, reference = [], [], None, None
    source = 'https://github.com/shade-econ/sequence-jacobian/blob/' + SSJ_REVISION + '/src/sequence_jacobian/examples/hank.py'
    source_hashes = package_source_hashes(sequence_jacobian,
        ['examples/hank.py', 'hetblocks/hh_labor.py', 'blocks/block.py', 'blocks/het_block.py'])
    if 'saved_solution' in spec:
        saved, reference = read_saved_solution(spec['saved_solution'], base_dir)
        if saved.get('model_contract') != 'MC-hank-one-asset' or saved['native_solution']['format'] != 'sequence-jacobian-steady-state-v1':
            raise ValueError('saved_solution must contain a solved one-asset HANK model')
        if saved['provenance']['sequence_jacobian'] != version('sequence-jacobian'):
            raise ValueError('saved HANK solution and execution package versions differ')
        if saved['provenance']['source_hashes'] != source_hashes:
            raise ValueError('saved HANK solution and installed native source revisions differ')
        definition = saved['solution_definition']
        for key in ('parameters', 'steady_state', 'calibration_source'):
            if key in spec and spec[key] != definition[key]:
                raise ValueError(f'{key} changes the saved steady-state definition; solve the changed calibration first')
        native = saved['native_solution']
        top = {key: np.asarray(val) if isinstance(val, list) else val for key, val in native['toplevel'].items()}
        internal = {block: {key: np.asarray(val) for key, val in data.items()}
                    for block, data in native['internals'].items()}
        ss = SteadyStateDict(top, internal)
        reused.append('SteadyStateDict: parameters, household policies and stationary distribution')
    else:
        if not spec.get('calibration_source'):
            raise ValueError('calibration_source must identify the adopted HANK primitives and targets')
        parameters = spec['parameters']
        required = {'rstar', 'eis', 'frisch', 'B', 'mu', 'rho_s', 'sigma_s', 'kappa', 'phi', 'Y', 'Z', 'pi', 'nS', 'amax', 'nA'}
        if required - parameters.keys():
            raise ValueError('missing HANK parameters: ' + ', '.join(sorted(required - parameters.keys())))
        if not all(np.isfinite(value) for value in parameters.values()):
            raise ValueError('HANK parameters must be finite scalars')
        if any(type(parameters[key]) is not int or parameters[key] < 2 for key in ('nS', 'nA')):
            raise ValueError('nS and nA must be integers of at least two')
        if not (parameters['amax'] > 0 and parameters['B'] > 0 and parameters['mu'] > 1 and
                parameters['kappa'] > 0 and parameters['Y'] > 0 and parameters['Z'] > 0):
            raise ValueError('HANK asset supply, productivity, output and price-setting parameters are invalid')
        steady = spec['steady_state']
        if set(steady['unknowns']) != {'beta', 'vphi'} or set(steady['targets']) != {'asset_mkt', 'NE'}:
            raise ValueError('steady_state requires beta/vphi unknowns and asset_mkt/NE targets')
        options = dict(steady.get('options', {}))
        valid_options = set(steady_model.solve_steady_state_options) | set(household.steady_state_options)
        if set(options) - valid_options:
            raise ValueError('unsupported HANK steady-state option: ' + ', '.join(sorted(set(options) - valid_options)))
        options['solver'] = steady.get('solver', 'broyden_custom')
        cali = steady_model.solve_steady_state(parameters, steady['unknowns'], steady['targets'], **options)
        executed.append('Block.solve_steady_state')
        ss = model.steady_state(cali, **options)
        executed.append('Block.steady_state')
        definition = {key: deepcopy(spec[key]) for key in ('parameters', 'steady_state', 'calibration_source')}
    diagnostics = {key: float(ss[key]) for key in HANK_TARGETS + ['labor_mkt']}
    tolerance = float(spec.get('equilibrium_tolerance', 1e-7))
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('equilibrium_tolerance must be finite and positive')
    if max(abs(value) for value in diagnostics.values()) > tolerance:
        raise ArithmeticError('original HANK steady-state market or price residual exceeds equilibrium_tolerance')
    quantities = saved['welfare']['baseline'] if saved else hank_household_quantities(ss, household)
    if saved:
        reused.append('stationary household values and diagnostics')
    metadata = {
        'model_contract': 'MC-hank-one-asset', 'knowledge_ids': ['HET-03', 'HET-04', 'HET-05'],
        'normalization': 'Unit household mass; mean skill one; asset lower bound zero; consumption and output in goods per household per period.',
        'equilibrium_selection': 'Official one-asset HANK blocks; beta and vphi solve adopted stationary targets from supplied starting values; transitions start from that stationary distribution and end at its stationary policy.',
        'welfare_definition': 'u(c,n)=log(c)-vphi*n^(1+1/frisch)/(1+1/frisch) for eis=1; otherwise c^(1-1/eis)/(1-1/eis) minus the same labor term. Sum discounted expected utility under the common initial stationary distribution, plus beta^T times its terminal distribution-weighted stationary-policy value. Consumption equivalent scales baseline consumption permanently while holding baseline labor fixed.',
        'parameter_definition': definition,
        'parameter_roles': {key: {'role': 'calibrated to stationary targets' if key in ('beta', 'vphi') else 'supplied calibration',
                                 'value': float(ss[key]), 'source': definition['calibration_source'],
                                 'unit': HANK_UNITS.get(key, 'dimensionless model primitive')}
                            for key in set(definition['parameters']) | {'beta', 'vphi'}},
        'equations': {
            'household_budget': 'c_t+a_next=(1+r_t)*a+w_t*e*n_t+T_t(e)',
            'euler': 'c_t^(-1/eis)>=beta*(1+r_next)*E[c_next^(-1/eis)] with equality above the borrowing limit',
            'labor': 'vphi*n_t^(1/frisch)=w_t*e*c_t^(-1/eis)',
            'distribution': 'D_next=Pi-forward(lottery(a_policy)-forward(D))',
            'firm': 'L=Y/Z; Div=Y-w*L-mu/(mu-1)/(2*kappa)*log(1+pi)^2*Y',
            'monetary': 'r_t=(1+rstar_(t-1)+phi*pi_(t-1))/(1+pi_t)-1',
            'fiscal': 'Tax=r*B; T(e)=(Div-Tax)*e/E[e]',
            'pricing': 'nkpc_res=kappa*(w/Z-1/mu)+(Y_next/Y)*log(1+pi_next)/(1+r_next)-log(1+pi)',
            'clearing': 'asset_mkt=A-B; labor_mkt=NE-L; goods_mkt=Y-C-mu/(mu-1)/(2*kappa)*log(1+pi)^2*Y'}}
    result = {**metadata, 'model': 'hank_one_asset', 'adopted': deepcopy(spec),
              'solution_definition': definition, 'engine': 'sequence_jacobian.examples.hank official blocks',
              'steady_state': dict(ss.toplevel), 'steady_state_diagnostics': diagnostics,
              'native_solution': {'format': 'sequence-jacobian-steady-state-v1', 'toplevel': dict(ss.toplevel),
                                  'internals': ss.internals}, 'welfare': {'baseline': quantities},
              'statistics': {key: {'value': float(ss[key]), 'unit': HANK_UNITS.get(key, 'dimensionless model primitive')}
                             for key in ('beta', 'vphi', 'A', 'C', 'NE', 'w', 'Y')},
              'provenance': {'python': sys.version.split()[0], 'numpy': np.__version__, 'scipy': scipy.__version__,
                             'sequence_jacobian': version('sequence-jacobian'), 'numba': version('numba'),
                             'upstream_revision': identity['source_revision'], 'official_package': identity,
                             'model_source': source, 'source_hashes': source_hashes,
                             'official_api': {name: str(inspect.signature(getattr(model, name))) for name in operations},
                             'saved_solution': reference},
              'options': {'steady_state': steady_model.get_options({}, definition['steady_state'].get('options', {}), 'solve_steady_state'),
                          'household_steady_state': household.get_options({}, definition['steady_state'].get('options', {}), 'steady_state'),
                          'transition': model.get_options({}, {'verbose': False, **spec.get('solver_options', {})}, operation) if operation != 'solve_steady_state' else {}}}
    result['options']['steady_state']['solver'] = definition['steady_state'].get('solver', 'broyden_custom')
    result['statistics']['baseline.welfare'] = {'value': quantities['stationary_welfare'], 'unit': 'discounted utility per household'}
    result['statistics'].update({'baseline.' + key: {'value': value, 'unit': HANK_UNITS[key]}
                                 for key, value in diagnostics.items()})
    equilibrium_rows = [{'scenario': 'baseline', 'quantity': key, 'value': float(ss[key]), 'unit': HANK_UNITS[key]}
                        for key in HANK_OUTPUTS]
    welfare_rows = [{'scenario': 'baseline', 'quantity': 'welfare', 'value': quantities['stationary_welfare'], 'unit': 'discounted utility per household'}]
    path_rows = []
    if operation != 'solve_steady_state':
        horizon = spec['horizon']
        if type(horizon) is not int or horizon < 2:
            raise ValueError('horizon must be an integer of at least two')
        result['horizon'] = horizon
        outputs = list(dict.fromkeys(HANK_OUTPUTS + spec.get('outputs', [])))
        if set(outputs) - (set(model.outputs) | set(HANK_UNKNOWNS) | {'rstar', 'Z'}):
            raise ValueError('outputs must name native HANK outputs or the rstar/Z shocks')
        cache_key = {'horizon': horizon, 'outputs': outputs, 'inputs': ['rstar', 'Z'], 'revision': SSJ_REVISION}
        cache = saved.get('jacobian_cache') if saved else None
        if cache and cache['definition'] == cache_key:
            partial = {name: JacobianDict({o: {i: np.asarray(matrix) for i, matrix in row.items()}
                                           for o, row in item['matrices'].items()}, name=name, T=horizon)
                       for name, item in cache['partial'].items()}
            reused.append('partial JacobianDict blocks')
        else:
            partial = model.partial_jacobians(ss, ['rstar', 'Z'] + HANK_UNKNOWNS, outputs, T=horizon)
            executed.append('Block.partial_jacobians')
        result['jacobian_cache'] = {'definition': cache_key, 'partial': {
            name: {'matrices': {o: {i: make_matrix(matrix, horizon) for i, matrix in row.items()}
                               for o, row in jac.nesteddict.items()}}
            for name, jac in partial.items()}}
        if operation == 'solve_jacobian':
            inputs = spec.get('inputs', ['rstar', 'Z'])
            if not inputs or set(inputs) - {'rstar', 'Z'}:
                raise ValueError('HANK Jacobian inputs must select rstar and/or Z')
            jac = model.solve_jacobian(ss, HANK_UNKNOWNS, HANK_TARGETS, inputs, outputs=outputs,
                                       T=horizon, Js=partial)
            result['jacobian'] = {'outputs': list(jac.outputs), 'inputs': list(jac.inputs),
                                  'matrices': {o: {i: make_matrix(matrix, horizon) for i, matrix in row.items()}
                                               for o, row in jac.nesteddict.items()},
                                  'coordinates': 'row=output period; column=shock period; level derivatives'}
            executed.append('Block.solve_jacobian')
        else:
            scenarios = {'baseline_shock': spec['shocks']}
            if 'scenario' in spec:
                if spec['scenario'].get('name', 'counterfactual') == 'baseline_shock':
                    raise ValueError('scenario.name must distinguish the counterfactual from baseline_shock')
                scenarios[spec['scenario'].get('name', 'counterfactual')] = spec['scenario']['shocks']
            result['impulses'] = {}
            for name, raw_shocks in scenarios.items():
                shocks = {key: np.asarray(values, dtype=float) for key, values in raw_shocks.items()}
                if not shocks or set(shocks) - {'rstar', 'Z'} or any(
                        values.shape != (horizon,) or not np.isfinite(values).all() for values in shocks.values()):
                    raise ValueError('shocks require finite rstar/Z level-deviation arrays of length horizon')
                if operation == 'solve_impulse_linear':
                    impulse = model.solve_impulse_linear(ss, HANK_UNKNOWNS, HANK_TARGETS, shocks,
                                                         outputs=outputs, Js=partial)
                else:
                    options = {'verbose': False, **spec.get('solver_options', {})}
                    if set(options) - set(model.solve_impulse_nonlinear_options):
                        raise ValueError('solver_options must use the native nonlinear tol, maxit and verbose names')
                    impulse = model.solve_impulse_nonlinear(ss, HANK_UNKNOWNS, HANK_TARGETS, shocks,
                        outputs=outputs, internals={'hh': ['a', 'c', 'n', 'D', 'Va']}, Js=partial, **options)
                executed.append('Block.' + operation)
                residuals = {key: impulse[key] for key in HANK_TARGETS + ['labor_mkt']}
                if any(not np.isfinite(values).all() for values in impulse.values()) or max(np.max(np.abs(values)) for values in residuals.values()) > tolerance:
                    raise ArithmeticError('HANK transition residual exceeds equilibrium_tolerance')
                levels = {key: values + ss[key] for key, values in impulse.items()}
                result['impulses'][name] = {'shocks': shocks, 'deviations': dict(impulse.toplevel),
                                           'levels': levels, 'residuals': residuals,
                                           'household_deviations': impulse.internals}
                if operation == 'solve_impulse_nonlinear':
                    welfare = hank_household_quantities(ss, household, impulse, stationary=quantities)
                    result['welfare'][name] = welfare
                    for key, unit in [('welfare', 'discounted utility per household'),
                                      ('welfare_change', 'discounted utility per household'),
                                      ('consumption_equivalent', 'fraction of baseline consumption')]:
                        result['statistics'][name + '.' + key] = {'value': welfare[key], 'unit': unit}
                        welfare_rows.append({'scenario': name, 'quantity': key, 'value': welfare[key], 'unit': unit})
                for key, values in impulse.items():
                    result['statistics'][name + '.impact.' + key] = {'value': float(values[0]), 'unit': HANK_UNITS.get(key, 'model units') + ' change'}
                    path_rows.extend({'scenario': name, 'period': t, 'quantity': key, 'value': float(value),
                                      'unit': HANK_UNITS.get(key, 'model units') + ' change'} for t, value in enumerate(values))
    result['computation'] = {'requested_operation': operation, 'operations_executed': executed,
        'parameter_operation': 'reuse saved calibration' if saved else 'calibrate beta and vphi to the declared stationary targets',
        'reused_objects': reused, 'estimated_parameters': [],
        'computed_quantities': ['stationary equilibrium', 'household policies and distribution', 'stationary policy values'] +
            (['general-equilibrium Jacobian'] if operation == 'solve_jacobian' else
             ['linear equilibrium impulses'] if operation == 'solve_impulse_linear' else
             ['nonlinear equilibrium paths', 'transition values', 'common consumption equivalent'] if operation == 'solve_impulse_nonlinear' else [])}
    metadata['computation'] = result['computation']
    metadata['horizon'] = result.get('horizon', 'stationary infinite horizon')
    result['displays'] = {'equilibrium': structural_display(equilibrium_rows, metadata),
                          'welfare': structural_display(welfare_rows, metadata)}
    h = ss.internals['hh']
    for key, native_key, unit in [('consumption_policy', 'c', 'goods per household'),
                                   ('asset_policy', 'a', 'goods per household'),
                                   ('distribution', 'D', 'population probability')]:
        rows = [{'scenario': 'baseline', 'income_state': i, 'efficiency': float(e), 'asset': float(a),
                 'quantity': native_key, 'value': float(h[native_key][i, j]), 'unit': unit}
                for i, e in enumerate(h['e_grid']) for j, a in enumerate(h['a_grid'])]
        result['displays'][key] = structural_display(rows, metadata,
            {'plot_type': 'line', 'x': 'asset', 'y': 'value', 'series': 'income_state'})
    if path_rows:
        result['displays']['impulses'] = structural_display(path_rows, metadata,
            {'plot_type': 'line', 'x': 'period', 'y': 'value', 'series': 'scenario', 'facet': 'quantity'})
    return numeric_json(result)


def solve_dolo(spec, base_dir):
    """Solve or reuse an adopted native YAML model with official Dolo methods."""
    from research_dynamic import official_package
    identity = official_package('dolo', '0.4.9.20', DOLO_REVISION)
    import dolo
    from dolo.compiler.model_import import yaml_import
    from dolo.compiler.misc import CalibrationDict
    from dolo.algos.steady_state import find_steady_state, residuals
    from dolo.algos.time_iteration import time_iteration
    from dolo.numeric.discretized_model import DiscretizedModel
    from dolo.numeric.residuals import F
    source_hashes = package_source_hashes(dolo, ['compiler/model_import.py', 'compiler/model.py',
        'algos/steady_state.py', 'algos/time_iteration.py', 'numeric/residuals.py', 'numeric/decision_rule.py'])
    operation = spec.get('operation', 'time_iteration')
    if operation not in ('time_iteration', 'reuse_solution'):
        raise ValueError('Dolo operation must be time_iteration or reuse_solution')
    saved, reference = None, None
    if 'saved_solution' in spec:
        saved, reference = read_saved_solution(spec['saved_solution'], base_dir)
        if saved.get('native_solution', {}).get('format') != 'dolo-decision-rule-v1':
            raise ValueError('saved_solution must contain a Dolo decision rule')
        if saved['provenance']['dolo'] != version('dolo'):
            raise ValueError('saved Dolo rule and execution package versions differ')
        if saved['provenance']['source_hashes'] != source_hashes:
            raise ValueError('saved Dolo rule and installed native source revisions differ')
    if operation == 'reuse_solution' and saved is None:
        raise ValueError('reuse_solution requires saved_solution')
    if 'yaml_model' in spec:
        source = dict(spec['yaml_model'])
        path = (base_dir / source['path']).resolve()
        raw_yaml = path.read_bytes()
        if hashlib.sha256(raw_yaml).hexdigest() != source['sha256']:
            raise ValueError('yaml_model.sha256 does not match the adopted YAML')
        if not source.get('source'):
            raise ValueError('yaml_model.source must identify the adopted model equations')
        yaml_text = raw_yaml.decode('utf-8')
    elif saved:
        source = saved['yaml_model']['source']
        yaml_text = saved['yaml_model']['text']
    else:
        raise ValueError('yaml_model with path, sha256 and source is required')
    calibration_source = spec.get('calibration_source', saved['calibration_source'] if saved else None)
    if not calibration_source:
        raise ValueError('calibration_source must identify the adopted Dolo calibration')
    overrides = spec.get('calibration', saved['solution_definition']['calibration'] if saved else {})
    discretization = spec.get('discretization', saved['solution_definition']['discretization'] if saved else {})
    solver = {'engine': 'vectorized', 'interpolation': 'cubic', 'tol_eps': 1e-8, 'tol_eta': 1e-9,
              'maxit': 500, 'inner': {'tol': 1e-10}, 'ignore_constraints': False, 'verbose': False}
    if saved:
        solver.update(saved['solver'])
    solver.update(spec.get('solver', {}))
    allowed = {'engine', 'backend', 'interpolation', 'tol_eps', 'tol_eta', 'maxit', 'inner',
               'accelerate', 'ignore_constraints', 'verbose'}
    if set(solver) - allowed:
        raise ValueError('unsupported Dolo solver option: ' + ', '.join(sorted(set(solver) - allowed)))
    if solver['interpolation'] not in ('linear', 'cubic'):
        raise ValueError('Dolo interpolation must be linear or cubic')
    if any(not np.isfinite(solver[key]) or solver[key] <= 0 for key in ('tol_eps', 'tol_eta')):
        raise ValueError('Dolo convergence tolerances must be finite and positive')
    validation = {'steady_state_tolerance': 1e-8, 'arbitrage_tolerance': 1e-7, 'bound_tolerance': 1e-8,
                  **spec.get('validation', {})}
    if set(validation) - {'steady_state_tolerance', 'arbitrage_tolerance', 'bound_tolerance'}:
        raise ValueError('validation must name steady_state_tolerance, arbitrage_tolerance or bound_tolerance')
    if any(not np.isfinite(value) or value <= 0 for value in validation.values()):
        raise ValueError('Dolo validation tolerances must be finite and positive')
    definition = {'yaml_sha256': hashlib.sha256(yaml_text.encode('utf-8')).hexdigest(),
                  'calibration': overrides, 'discretization': discretization,
                  'interpolation': solver['interpolation'], 'ignore_constraints': solver['ignore_constraints']}
    if saved and definition != saved['solution_definition']:
        raise ValueError('saved Dolo solution requires the same YAML, calibration, grid, process and interpolation')
    # Import the exact retained bytes, including when the original input moved.
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', encoding='utf-8') as stream:
        stream.write(yaml_text)
        stream.flush()
        model = yaml_import(stream.name, check=True)
    executed = ['yaml_import']
    if overrides:
        if set(overrides) - model.calibration.flat.keys():
            raise ValueError('calibration overrides must name native model symbols')
        model = model.recalibrate(**overrides)
        executed.append('Model.recalibrate')
    if operation == 'reuse_solution':
        steady = CalibrationDict(model.symbols, {key: np.asarray(value) for key, value in saved['steady_state']['grouped'].items()})
    else:
        steady = find_steady_state(model)
        executed.append('find_steady_state')
    steady_residuals = residuals(model, steady)
    executed.append('residuals')
    steady_error = max(float(np.max(np.abs(value))) for value in steady_residuals.values())
    if not np.isfinite(steady_error) or steady_error > validation['steady_state_tolerance']:
        raise ArithmeticError('Dolo original steady-state residual exceeds steady_state_tolerance')
    dmodel = DiscretizedModel(model, **discretization)
    dr0 = None
    if saved:
        if not np.array_equal(dmodel.endo_nodes, np.asarray(saved['native_solution']['state_grid'])):
            raise ValueError('saved Dolo state coordinates differ from the reconstructed native grid')
        dr0 = dmodel.decision_rule(np.asarray(saved['native_solution']['values']), interp_method=solver['interpolation'])
    if operation == 'reuse_solution':
        decision_rule = dr0
        convergence = saved['convergence']
    else:
        fitted = time_iteration(dmodel, dr0=dr0, details=True, **solver)
        executed.append('time_iteration')
        decision_rule = fitted.dr
        convergence = {'iterations': int(fitted.iterations), 'converged': bool(fitted.converged),
                       'error_res': float(fitted.error_res), 'error_step': float(fitted.error_step),
                       'criterion': 'error_res < tol_eps OR error_step < tol_eta; error_res precedes the final policy update',
                       'complementarities': bool(fitted.complementarities)}
        if not fitted.converged:
            raise ArithmeticError('Dolo time_iteration did not meet its native convergence criterion')
    controls = dmodel.initial_guess()
    regimes = []
    for regime, exogenous, states in dmodel.regimes():
        controls[regime] = decision_rule(regime, states)
        regimes.append({'index': regime, 'exogenous': exogenous})
    final = F(dmodel, controls, decision_rule, engine=solver['engine'], backend=solver.get('backend'),
              interp_method=solver['interpolation'])
    executed.append('F(final_decision_rule)')
    original = np.asarray(final.data if hasattr(final, 'grid') else final)
    original = original.reshape(controls.shape)
    if not np.isfinite(original).all() or not np.isfinite(controls.data).all():
        raise ArithmeticError('Dolo returned nonfinite policies or original arbitrage residuals')
    lower, upper = dmodel.lower_bounds(), dmodel.upper_bounds()
    if lower is None or upper is None or solver['ignore_constraints']:
        lo, hi = np.full(controls.shape, -np.inf), np.full(controls.shape, np.inf)
    else:
        lo, hi = lower.data, upper.data
    tol_bound = validation['bound_tolerance']
    at_lower, at_upper = controls.data <= lo + tol_bound, controls.data >= hi - tol_bound
    interior = ~(at_lower | at_upper)
    kkt = np.where(interior, original, np.where(at_lower, np.minimum(original, 0.), np.maximum(original, 0.)))
    kkt = np.where(at_lower & at_upper, 0., kkt)
    violation = np.maximum(np.maximum(lo - controls.data, controls.data - hi), 0.)
    kkt_error, bound_error = float(np.max(np.abs(kkt))), float(np.max(violation))
    if kkt_error > validation['arbitrage_tolerance'] or bound_error > tol_bound:
        raise ArithmeticError('Dolo final decision rule fails original arbitrage/complementarity or bound tolerance')
    units = spec.get('units', saved.get('units', {}) if saved else {})
    from dolo.numeric.residuals import _resolve_engine
    residual_engine = _resolve_engine(dmodel, solver['engine'], solver.get('backend'))
    iteration_engine = residual_engine if dmodel.n_regimes == 1 else 'vectorized'
    metadata = {'equations': model.equations, 'notation': dict(model.symbols),
        'parameter_definition': {'source': calibration_source, 'calibration': model.calibration.flat},
        'parameter_roles': {name: {'role': 'supplied calibration', 'value': float(model.calibration[name]),
                                  'source': calibration_source, 'unit': units.get(name, 'model units')}
                            for name in model.symbols['parameters']},
        'normalization': spec.get('normalization', saved.get('normalization') if saved else 'The retained native YAML defines levels, units, preference scale and state/control timing.'),
        'equilibrium_selection': 'Native YAML calibration initializes the steady-state root; time iteration starts from its controls or the hash-bound saved decision rule on the declared grid and process.',
        'horizon': 'stationary infinite-horizon decision rule',
        'computation': {'requested_operation': operation, 'operations_executed': executed,
                        'parameter_operation': 'reuse adopted calibration; estimate no parameters',
                        'computed_quantities': ['steady-state calibration', 'original transition and arbitrage residuals',
                                                'decision rule on state/regime coordinates', 'final-policy complementarity residuals'],
                        'reused_objects': ['saved steady state and decision rule'] if operation == 'reuse_solution' else
                                          ['saved initial decision rule'] if saved else []}}
    state_names, control_names = model.symbols['states'], model.symbols['controls']
    rows = []
    for regime in range(dmodel.n_regimes):
        for index, state in enumerate(dmodel.endo_nodes):
            for j, control in enumerate(control_names):
                rows.append({'regime': regime, 'grid_index': index,
                             **{name: float(state[k]) for k, name in enumerate(state_names)},
                             'quantity': control, 'value': float(controls.data[regime, index, j]),
                             'unit': units.get(control, 'model units')})
    statistics = {name: {'value': value, 'unit': 'residual'} for name, value in
                  [('max_steady_state_residual', steady_error), ('max_original_arbitrage_residual', float(np.max(np.abs(original)))),
                   ('max_complementarity_residual', kkt_error), ('max_bound_violation', bound_error)]}
    statistics.update({'steady_state.' + key: {'value': float(value), 'unit': units.get(key, 'model units')}
                       for key, value in steady.flat.items()})
    process = [{'regime': regime, 'node': dmodel.dprocess.node(regime),
                'integration_nodes': [dmodel.dprocess.inode(regime, j) for j in range(dmodel.dprocess.n_inodes(regime))],
                'weights': [dmodel.dprocess.iweight(regime, j) for j in range(dmodel.dprocess.n_inodes(regime))]}
               for regime in range(dmodel.n_regimes)]
    result = {**metadata, 'model': 'dolo_yaml', 'model_name': model.name, 'adopted': deepcopy(spec), 'units': units,
              'yaml_model': {'source': source, 'text': yaml_text}, 'calibration_source': calibration_source,
              'solution_definition': definition, 'solver': solver, 'validation': validation,
              'engine': 'dolo.yaml_import; find_steady_state; residuals; time_iteration; numeric.residuals.F',
              'effective_engines': {'time_iteration': iteration_engine, 'final_residual': residual_engine},
              'steady_state': {'flat': steady.flat, 'grouped': steady.grouped, 'residuals': steady_residuals},
              'convergence': convergence,
              'native_solution': {'format': 'dolo-decision-rule-v1', 'state_names': state_names, 'control_names': control_names,
                                  'state_grid': dmodel.endo_nodes, 'regimes': regimes, 'process': process,
                                  'interpolation': solver['interpolation'], 'values': controls.data,
                                  'coefficients': decision_rule.coefficients},
              'diagnostics': {'original_arbitrage_residuals': original, 'complementarity_residuals': kkt,
                              'lower_bounds': np.where(np.isfinite(lo), lo, None),
                              'upper_bounds': np.where(np.isfinite(hi), hi, None),
                              'unbounded_endpoint': {'lower_null': '-infinity', 'upper_null': '+infinity'},
                              'interior': interior, 'bound_violation': violation,
                              'complementarity_convention': 'F=0 inside bounds, F>=0 at lower bound, F<=0 at upper bound'},
              'statistics': statistics, 'displays': {'decision_rule': structural_display(rows, metadata)},
              'provenance': {'python': sys.version.split()[0], 'numpy': np.__version__, 'scipy': scipy.__version__,
                             'dolo': version('dolo'), 'numba': version('numba'), 'quantecon': version('quantecon'),
                             'interpolation': version('interpolation'), 'jax': version('jax'),
                             'upstream_revision': identity['source_revision'], 'official_package': identity,
                             'source_hashes': source_hashes, 'saved_solution': reference,
                             'official_api': {function.__name__: str(inspect.signature(function))
                                              for function in (yaml_import, find_steady_state, residuals, time_iteration, F)}}}
    return numeric_json(result)


def solve(spec, base_dir=Path.cwd()):
    if spec.get('model') == 'hank_one_asset':
        return solve_hank(spec, base_dir)
    if spec.get('model') == 'dolo_yaml' or spec.get('options', {}).get('algorithm') == 'dolo_time_iteration':
        return solve_dolo(spec, base_dir)
    p = spec['parameters']
    alpha, beta, delta = (float(p[k]) for k in ('alpha', 'beta', 'delta'))
    if not (0 < alpha < 1 and 0 < beta < 1 and 0 < delta < 1):
        raise ValueError('alpha, beta and delta must lie strictly between zero and one')
    observed, observed_source = read_productivity(spec['observations'],base_dir)
    if observed.ndim != 1 or len(observed) < 20 or not np.isfinite(observed).all() or np.std(observed) <= 1e-10:
        raise ValueError('at least 20 finite varying log-productivity observations are required')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fitted = ARIMA(observed, order=(1, 0, 0), trend='n', enforce_stationarity=True).fit()
    if not fitted.mle_retvals.get('converged', False):
        raise ArithmeticError('ARIMA maximum likelihood did not converge')
    estimates = dict(zip(fitted.param_names, np.asarray(fitted.params, dtype=float)))
    rho, variance = estimates['ar.L1'], estimates['sigma2']
    if not (-1 < rho < 1 and variance > 0): raise ArithmeticError('invalid AR(1) estimate')
    sigma = float(np.sqrt(variance))
    covariance = np.asarray(fitted.cov_params(), dtype=float)
    if not np.isfinite(covariance).all(): raise ArithmeticError('non-finite parameter covariance')
    kbar = (alpha/(1/beta-1+delta))**(1/(1-alpha))
    ybar = kbar**alpha
    cbar = ybar-delta*kbar
    if cbar <= 0: raise ArithmeticError('nonpositive steady consumption')
    marginal_capital = alpha*ybar+(1-delta)*kbar
    eta = beta*alpha*kbar**(alpha-1)
    def consumption_capital(a): return (marginal_capital-kbar*a)/cbar
    def euler_root(a):
        A = consumption_capital(a)
        return A-(A-eta*(alpha-1))*a
    a = float(brentq(euler_root, 0., 1., xtol=1e-14))
    A = consumption_capital(a)
    b = ((ybar/cbar)*(1-rho)+eta*rho)/((A-eta*(alpha-1))+(kbar/cbar)*(1-rho))
    B = (ybar-kbar*b)/cbar
    capital_residual = A-(A-eta*(alpha-1))*a
    technology_residual = B*(1-rho)-(A-eta*(alpha-1))*b+eta*rho
    resource_k = cbar*A+kbar*a-marginal_capital
    resource_z = cbar*B+kbar*b-ybar
    if max(abs(capital_residual),abs(technology_residual),abs(resource_k),abs(resource_z)) > 1e-9:
        raise ArithmeticError('linear equilibrium coefficients fail original equations')
    if not (0 < a < 1): raise ArithmeticError('capital policy is not stable')
    horizon, paths, seed = (int(spec[k]) for k in ('horizon','simulation_paths','seed'))
    shock = float(spec['technology_shock'])
    if not (2 <= horizon <= 500 and 2 <= paths <= 10000 and np.isfinite(shock)):
        raise ValueError('invalid horizon, number of paths or shock')
    # Exact levels and budget evaluated at the first-order log-capital policy.
    def allocation(x, z):
        k = kbar*np.exp(x)
        next_x = a*x+b*z
        knext = kbar*np.exp(next_x)
        y = np.exp(z)*k**alpha
        c = y+(1-delta)*k-knext
        if not np.isfinite(c).all() or np.any(c <= 0): raise ValueError('policy yields nonpositive consumption')
        return next_x, k, knext, y, c
    value_constant = np.log(cbar)/(1-beta)
    value_k = A/(1-beta*a)
    value_z = (B+beta*value_k*b)/(1-beta*rho)
    def path(z):
        x = 0.
        rows = []
        welfare = 0.
        for t in range(horizon):
            next_x, k, knext, y, c = allocation(x,z[t])
            welfare += beta**t*np.log(c)
            rows.append({'period':t,'log_capital_deviation':float(x), 'log_productivity':float(z[t]),
                'capital':float(k),'next_capital':float(knext),'output':float(y),'consumption':float(c),
                'investment':float(knext-(1-delta)*k),
                'resource_residual':float(c+knext-y-(1-delta)*k)})
            x = next_x
        continuation = value_constant+value_k*x+value_z*z[horizon]
        welfare += beta**horizon*continuation
        return rows, float(welfare)
    z_irf = shock*rho**np.arange(horizon+1)
    irf_path, irf_welfare = path(z_irf)
    base_path, base_welfare = path(np.zeros(horizon+1))
    irf = [{key:row[key]-base[key] for key in ('capital','next_capital','output','consumption','investment')}
           for row,base in zip(irf_path,base_path)]
    rng = np.random.default_rng(seed)
    innovations = rng.normal(0,sigma,size=(paths,horizon))
    simulations = []
    z_samples = np.zeros((paths,horizon+1))
    welfare_samples = []
    for i in range(paths):
        for t in range(horizon): z_samples[i,t+1] = rho*z_samples[i,t]+innovations[i,t]
        rows, welfare = path(z_samples[i])
        simulations.append({'path':i,'innovations':innovations[i].tolist(),'periods':rows,'terminal_log_productivity':float(z_samples[i,-1]),'welfare':welfare})
        welfare_samples.append(welfare)
    forecast = [{'period':t,'sample_mean_log_productivity':float(np.mean(z_samples[:,t])),
        'sample_variance_log_productivity':float(np.var(z_samples[:,t],ddof=1)),
        'model_mean_log_productivity':0.,
        'model_variance_log_productivity':float(variance*sum(rho**(2*j) for j in range(t)))} for t in range(horizon+1)]
    for t in range(horizon):
        for key in ('capital','output','consumption','investment'):
            draws = np.asarray([trial['periods'][t][key] for trial in simulations])
            forecast[t]['sample_mean_'+key] = float(draws.mean())
            forecast[t]['sample_variance_'+key] = float(draws.var(ddof=1))
    nodes, weights = hermgauss(25)
    weights = weights/np.sqrt(np.pi)
    def euler_error(scale):
        x, z, sig = .03*scale, .04*scale, sigma*scale
        next_x, _, knext, _, c = allocation(x,z)
        next_z = rho*z+np.sqrt(2)*sig*nodes
        _, _, _, _, next_c = allocation(np.full_like(next_z,next_x),next_z)
        next_return = alpha*np.exp(next_z)*knext**(alpha-1)+1-delta
        return float(1/c-beta*np.dot(weights,next_return/next_c))
    scales = [1.,.5,.25,.125]
    residuals = [{'scale':scale,'conditional_euler_residual':euler_error(scale)} for scale in scales]
    max_resource = max(abs(row['resource_residual']) for trial in simulations for row in trial['periods'])
    stats = {'rho':{'value':float(rho),'unit':'AR(1) coefficient'},
        'innovation_std':{'value':sigma,'unit':'log productivity per period'},
        'steady_capital':{'value':float(kbar),'unit':'goods'},
        'capital_stable_root':{'value':a,'unit':'log capital elasticity'},
        'impact_output_change':{'value':irf[0]['output'],'unit':'goods per period'},
        'conditional_shock_welfare_change':{'value':irf_welfare-base_welfare,'unit':'discounted log consumption'},
        'mean_simulated_welfare':{'value':float(np.mean(welfare_samples)),'unit':'discounted log consumption'},
        'max_resource_residual':{'value':max_resource,'unit':'goods per period'}}
    return {'model':'stochastic log-utility RBC with first-order rational-expectations solution',
        'adopted':spec, 'scenario':'estimated AR(1), conditional technology shock, and seeded stochastic forecasts',
        'engine':'scipy.optimize.brentq; statsmodels.tsa.arima.model.ARIMA.fit; numpy Gauss-Hermite quadrature',
        'options':{'arima_order':[1,0,0], 'trend':'n','enforce_stationarity':True,'quadrature_nodes':25,'seed':seed},
        'observation':{'type':spec['observations']['type'],'source':spec['observations']['source'], 'input':observed_source,
            'equation':'z[t] = rho*z[t-1] + epsilon[t], epsilon ~ iid Normal(0,sigma^2)',
            'estimand':'conditional AR(1) persistence and innovation variance',
            'identification':'stationary AR(1), zero mean, Gaussian independent innovations and nonzero lagged variation',
            'parameter_names':fitted.param_names,'parameters':fitted.params.tolist(),
            'standard_errors':fitted.bse.tolist(),'covariance':covariance.tolist(),
            'log_likelihood':float(fitted.llf),'nobs':int(fitted.nobs),'converged':True,
            'warnings':[str(x.message) for x in caught]},
        'steady_state':{'capital':float(kbar),'consumption':float(cbar),'output':float(ybar),
            'euler_residual':float(1/cbar-beta*(alpha*kbar**(alpha-1)+1-delta)/cbar)},
        'policy':{'capital_state_coefficient':a,'capital_technology_coefficient':float(b),
            'consumption_state_coefficient':float(A),'consumption_technology_coefficient':float(B),
            'linear_euler_state_residual':float(capital_residual),'linear_euler_technology_residual':float(technology_residual),
            'linear_resource_state_residual':float(resource_k),'linear_resource_technology_residual':float(resource_z)},
        'nonlinear_euler_checks':{'method':'25-node Gauss-Hermite conditional expectation',
            'state_base':[.03,.04],'jointly_scaled_innovation_std':sigma,'residuals':residuals},
        'conditional_irf':{'shock':shock,'baseline':base_path,'scenario':irf_path,'differences':irf,
            'welfare_difference':irf_welfare-base_welfare},
        'forecast_moments':forecast, 'simulation':simulations,
        'welfare':{'method':'discounted exact log consumption under local policy plus first-order terminal value',
            'terminal_constant':float(value_constant),'terminal_capital_coefficient':float(value_k),
            'terminal_technology_coefficient':float(value_z),'baseline':base_welfare,
            'conditional_shock':irf_welfare,'mean_simulated':float(np.mean(welfare_samples))},
        'statistics':stats,'provenance':{'python':sys.version.split()[0],'numpy':np.__version__,
            'scipy':scipy.__version__,'statsmodels':statsmodels.__version__}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['run'])
    parser.add_argument('spec',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        raw = args.spec.read_bytes()
        specification = json.loads(raw)
        if not isinstance(specification, dict):
            raise TypeError('specification must be an object')
        protected = {args.spec.resolve()}
        for key in ('observations', 'saved_solution', 'yaml_model'):
            reference = specification.get(key)
            if isinstance(reference, dict) and isinstance(reference.get('path'), str):
                protected.add((args.spec.parent / reference['path']).resolve())
        if args.output.resolve() in protected:
            raise ValueError('output must differ from the specification, observations and saved model inputs')
        result = solve(specification,args.spec.resolve().parent)
        result['provenance']['spec_sha256'] = hashlib.sha256(raw).hexdigest()
        result['provenance']['producer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        atomic_write(args.output,result)
    except (ValueError,KeyError,TypeError,OSError,ArithmeticError) as exc:
        parser.exit(2,f'error: {exc}\n')


if __name__ == '__main__': main()
