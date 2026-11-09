#!/usr/bin/env python3
"""Household consumption-saving and macro equilibria: run SPEC --output FILE."""
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
from scipy.special import gammaln, logsumexp
from importlib.metadata import version


def olg_sequence_block(K, Z, effective_a, labor, alpha, save, income_share):
    Y = Z*effective_a*K(-1)**alpha*labor**(1-alpha)
    clearing = K-save*income_share*Y
    return Y, clearing


def solve_hark(spec):
    """Solve the declared finite-life HARK consumer and save evaluated policies."""
    from HARK.ConsumptionSaving.ConsIndShockModel import PerfForesightConsumerType, IndShockConsumerType, calc_vp_next
    from HARK.distributions import expected
    classes = {'perfect_foresight': PerfForesightConsumerType, 'idiosyncratic_shocks': IndShockConsumerType}
    if spec['income_process'] not in classes:
        raise ValueError('income_process must be perfect_foresight or idiosyncratic_shocks')
    parameters = spec['consumer_options']
    required = {'cycles', 'T_cycle', 'CRRA', 'DiscFac', 'Rfree', 'LivPrb', 'PermGroFac', 'BoroCnstArt'}
    if not isinstance(parameters, dict) or required - parameters.keys():
        raise ValueError('consumer_options requires ' + ', '.join(sorted(required)))
    if parameters['cycles'] != 1 or type(parameters['T_cycle']) is not int or parameters['T_cycle'] < 1:
        raise ValueError('finite-life HARK execution requires cycles=1 and positive integer T_cycle')
    if not spec.get('calibration_source'):
        raise ValueError('calibration_source must identify the fixed or previously fitted parameters')
    evaluation = spec['evaluation']
    grid = np.asarray(evaluation['mNrm'], dtype=float)
    if grid.ndim != 1 or not grid.size or not np.isfinite(grid).all():
        raise ValueError('evaluation.mNrm requires a nonempty finite vector of normalized resources')
    periods = evaluation.get('periods', list(range(parameters['T_cycle']+1)))
    if (not isinstance(periods, list) or not periods or len(set(periods)) != len(periods) or
            any(type(t) is not int or not 0 <= t <= parameters['T_cycle'] for t in periods)):
        raise ValueError('evaluation.periods requires distinct ages from zero through T_cycle')
    weights = None
    if 'weights' in evaluation:
        weights = np.asarray(evaluation['weights'], dtype=float)
        if weights.shape != grid.shape or not np.isfinite(weights).all() or (weights < 0).any() or not np.isclose(weights.sum(), 1):
            raise ValueError('evaluation.weights must give nonnegative population masses summing to one on mNrm')
    simulation = spec.get('simulation')
    if simulation is not None:
        if not isinstance(simulation, dict) or set(simulation) != {'AgentCount', 'T_sim', 'seed', 'track_vars'}:
            raise ValueError('simulation requires AgentCount, T_sim, seed and track_vars')
        if any(type(simulation[k]) is not int or simulation[k] < 1 for k in ('AgentCount', 'T_sim')) or type(simulation['seed']) is not int:
            raise ValueError('simulation counts must be positive integers and seed must be an integer')
        if (not isinstance(simulation['track_vars'], list) or not simulation['track_vars'] or
                not all(isinstance(k, str) for k in simulation['track_vars']) or
                len(set(simulation['track_vars'])) != len(simulation['track_vars'])):
            raise ValueError('simulation.track_vars must name the histories to save')
        initial = {'kLogInitMean', 'kLogInitStd', 'pLogInitMean', 'pLogInitStd'}
        if initial - parameters.keys():
            raise ValueError('consumer_options must specify initial asset and permanent-income log distributions for simulation')
    scenarios = {'baseline': parameters}
    if 'scenario' in spec:
        scenario = spec['scenario']
        if not isinstance(scenario, dict) or set(scenario) != {'consumer_options'} or not isinstance(scenario['consumer_options'], dict):
            raise ValueError('scenario requires its consumer_options changes')
        changed = {**parameters, **scenario['consumer_options']}
        if any(changed[k] != parameters[k] for k in ('cycles', 'T_cycle', 'CRRA')):
            raise ValueError('scenario comparisons preserve the lifecycle horizon and CRRA utility normalization')
        scenarios['scenario'] = changed
    outcomes, statistics, policy_rows, value_rows = {}, {}, [], []
    units = {'cNrm': 'goods per unit permanent income', 'aNrm': 'goods per unit permanent income',
             'value': 'normalized expected discounted CRRA utility'}
    for name, options in scenarios.items():
        if spec['income_process'] == 'idiosyncratic_shocks' and options.get('vFuncBool') is not True:
            raise ValueError(f'{name}: IndShockConsumerType value output requires vFuncBool=true')
        native = dict(options)
        if simulation is not None:
            if set(simulation) & options.keys():
                raise ValueError(f'{name}: declare simulation settings in simulation')
            native.update({k: v for k, v in simulation.items() if k != 'track_vars'})
        consumer = classes[spec['income_process']](**native)
        consumer.solve()
        rows = []
        for t in periods:
            solution = consumer.solution[t]
            if (grid <= solution.mNrmMin).any():
                raise ValueError(f'{name} period {t}: evaluation.mNrm must exceed the solved resource minimum {solution.mNrmMin}')
            consumption = np.asarray(solution.cFunc(grid), dtype=float)
            value = np.asarray(solution.vFunc(grid), dtype=float)
            if consumption.shape != grid.shape or value.shape != grid.shape or not np.isfinite([consumption, value]).all() or (consumption <= 0).any():
                raise ArithmeticError(f'{name} period {t}: HARK must return positive consumption and finite values at each evaluation point')
            assets = grid-consumption
            if t < consumer.T_cycle:
                rfree, growth = consumer.Rfree[t], consumer.PermGroFac[t]
                next_value = consumer.solution[t+1].vPfunc
                if spec['income_process'] == 'idiosyncratic_shocks':
                    marginal_value = expected(calc_vp_next, consumer.IncShkDstn[t],
                        args=(assets, rfree, consumer.CRRA, growth, next_value))
                else:
                    marginal_value = next_value(rfree*assets/growth+1)
                euler_gap = 1-consumption**consumer.CRRA * consumer.DiscFac*consumer.LivPrb[t]*rfree*growth**(-consumer.CRRA)*marginal_value
            for i, m in enumerate(grid):
                row = {'period': t, 'mNrm': float(m), 'cNrm': float(consumption[i]),
                       'aNrm': float(assets[i]), 'value': float(value[i]),
                       'mNrmMin': float(solution.mNrmMin)}
                if t < consumer.T_cycle:
                    slack = float(assets[i]-solution.mNrmMin)
                    row.update(euler_gap=float(euler_gap[i]), borrowing_slack=slack,
                               complementarity=float(euler_gap[i]*slack))
                rows.append(row)
                for quantity, unit in units.items():
                    statistics[f'{name}.period_{t}.point_{i}.{quantity}'] = {'value': row[quantity], 'unit': unit}
                coordinate = {'scenario': name, 'period': t, 'mNrm': float(m), 'series': f'{name}: age {t}'}
                policy_rows.append({**coordinate, 'value': row['cNrm'], 'unit': units['cNrm']})
                value_rows.append({**coordinate, 'value': row['value'], 'unit': units['value']})
            if weights is not None:
                for quantity, values in (('cNrm', consumption), ('value', value)):
                    statistics[f'{name}.period_{t}.weighted_{quantity}'] = {'value': float(weights @ values), 'unit': units[quantity]}
        outcome = {'consumer_options': options,
            'effective_consumer_options': {key: value for key, value in consumer.parameters.items()
                if key != 'constructors' and key not in consumer.constructors},
            'policies': rows, 'solution_periods': len(consumer.solution)}
        if spec['income_process'] == 'idiosyncratic_shocks':
            outcome['aXtraGrid'] = consumer.aXtraGrid.tolist()
            outcome['income_distributions'] = []
            for t in range(consumer.T_cycle):
                distribution = consumer.IncShkDstn[t]
                outcome['income_distributions'].append({'period': t,
                    'PermShk': distribution.atoms[0].tolist(), 'TranShk': distribution.atoms[1].tolist(),
                    'probability': distribution.pmv.tolist()})
        if simulation is not None:
            outcome['initial_distributions'] = {key: {'atoms': getattr(consumer, key).atoms.tolist(),
                'probability': getattr(consumer, key).pmv.tolist()} for key in ('kNrmInitDstn', 'pLvlInitDstn')}
            consumer.track_vars = list(simulation['track_vars'])
            consumer.initialize_sim()
            consumer.simulate()
            outcome['history'] = {key: np.asarray(values).tolist() for key, values in consumer.history.items()}
        outcomes[name] = outcome
    if 'scenario' in outcomes and weights is not None:
        for t in periods:
            for quantity in ('cNrm', 'value'):
                key = f'period_{t}.weighted_{quantity}'
                statistics['change.'+key] = {'value': statistics['scenario.'+key]['value']-statistics['baseline.'+key]['value'],
                                            'unit': units[quantity]}
    metadata = {'model_contract': 'MC-hark-consumption-saving', 'parameter_source': spec['calibration_source'],
        'normalization': 'resources, consumption and assets divided by permanent income; HARK normalized CRRA value',
        'equilibrium': 'individual optimum at the supplied exogenous income and return processes',
        'euler_gap': '1-c^CRRA*DiscFac*LivPrb*Rfree*E[(PermGroFac*PermShk)^(-CRRA)*c_next^(-CRRA)]; zero at an interior optimum and nonnegative at a binding borrowing limit',
        'borrowing_slack': 'end-of-period normalized assets minus the solved borrowing minimum',
        'complementarity': 'euler_gap times borrowing_slack at each nonterminal evaluation point'}
    displays = {}
    for name, rows, title in (('consumption_policy', policy_rows, 'Consumption policy'), ('value_function', value_rows, 'Value function')):
        displays[name] = {'kind': 'structural', 'title': title, 'rows': rows,
            'columns': [{'key': key, 'label': key, 'unit': ''} for key in ('scenario', 'period', 'mNrm', 'series', 'value', 'unit')],
            'metadata': {**metadata, 'unit': rows[0]['unit'], 'report_role': 'counterfactual' if 'scenario' in outcomes else 'model_fit'},
            'display': {'plot_type': 'line', 'x': 'mNrm', 'y': 'value', 'series': 'series'}}
    return {'result_format_version': 1, 'model': 'consumption_saving', 'adopted': spec,
        'model_contract': 'MC-hark-consumption-saving', 'knowledge_ids': ['HET-01', 'DYN-03'],
        'engine': 'HARK.ConsumptionSaving.ConsIndShockModel.'+classes[spec['income_process']].__name__+'.solve',
        'calibration': {'source': spec['calibration_source'], 'estimated_parameters': []},
        'equations': ['m_t=c_t+a_t', 'm_next=Rfree*a_t/(PermGroFac*PermShk)+TranShk',
            'v_t(m)=max_c u(c)+DiscFac*LivPrb*E[(PermGroFac*PermShk)^(1-CRRA)*v_next(m_next)]',
            'c_terminal=m_terminal'], 'definitions': metadata, **outcomes,
        'statistics': statistics, 'displays': displays,
        'provenance': {'python': sys.version.split()[0], 'numpy': np.__version__, 'HARK': version('econ-ark')}}


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


def lifecycle_run(spec, base_dir=Path.cwd()):
    """Construct an official pylcm model, save its solution, and replay policies."""
    import jax
    jax.config.update('jax_enable_x64', True)
    import jax.numpy as jnp
    import pandas as pd
    from lcm import DiscreteGrid, Model
    from lcm.persistence import load_solution, save_solution

    package_version = version('pylcm')
    if package_version != '0.0.2.dev261+g0fb55673b':
        raise ValueError('lifecycle_choice requires the pylcm revision in requirements-lifecycle.txt')
    operation = spec['operation']
    if operation not in ('solve', 'simulate', 'counterfactual'):
        raise ValueError('lifecycle operation must be solve, simulate or counterfactual')
    if not spec.get('calibration_source'):
        raise ValueError('calibration_source must identify the supplied parameter values')
    parameter_status = spec.get('parameter_status', 'fixed')
    if parameter_status not in ('fixed', 'calibrated', 'estimated'):
        raise ValueError('parameter_status must be fixed, calibrated or estimated')
    if operation != 'solve' and 'saved_solution' not in spec:
        raise ValueError('simulate and counterfactual require saved_solution.path and sha256')
    if operation == 'solve' and 'saved_solution' in spec:
        raise ValueError('use operation=simulate to reuse a saved solution')
    if operation != 'counterfactual' and 'scenario' in spec:
        raise ValueError('scenario requires operation=counterfactual')

    def local_path(name):
        path = Path(name)
        return path if path.is_absolute() else Path(base_dir) / path

    def merge_parameters(base, changes):
        result = dict(base)
        for key, value in changes.items():
            result[key] = merge_parameters(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
        return result

    def construct(definition, parameters):
        if definition == 'iskhakov_et_al_2017':
            from lcm_examples import iskhakov_et_al_2017 as example
            if spec['solver'] not in ('grid_search', 'dcegm'):
                raise ValueError('the retirement example requires solver=grid_search or dcegm')
            required = {'discount_factor', 'disutility_of_work', 'interest_rate', 'wage'}
            if set(parameters) != required:
                raise ValueError('retirement parameters require discount_factor, disutility_of_work, interest_rate and wage')
            if type(spec['n_periods']) is not int or spec['n_periods'] < 3:
                raise ValueError('retirement n_periods must be an integer of at least three, including death')
            factory = example.get_dcegm_model if spec['solver'] == 'dcegm' else example.get_model
            model = factory(n_periods=spec['n_periods'])
            native_params = example.get_params(n_periods=spec['n_periods'], **parameters)
            source_path = Path(example.__file__)
            source = {'module': 'lcm_examples.iskhakov_et_al_2017', 'factory': factory.__name__,
                'sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
                'kwargs': {'n_periods': spec['n_periods']},
                'revision': '0fb55673b0be4eb52d270b2585047faa38c4e930'}
            settings = {'wealth_grid': np.asarray(example.WEALTH_GRID.to_jax()).tolist(),
                'consumption_grid': np.asarray(example.CONSUMPTION_GRID.to_jax()).tolist()}
            if spec['solver'] == 'dcegm':
                settings.update(savings_grid=np.asarray(example.SAVINGS_GRID.to_jax()).tolist(),
                    n_constrained_points=example.DCEGM_SOLVER.n_constrained_points,
                    envelope=type(example.DCEGM_SOLVER.envelope).__name__,
                    refined_grid_factor=example.DCEGM_SOLVER.refined_grid_factor)
        elif isinstance(definition, dict):
            source_path = local_path(definition['module']).resolve()
            digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
            if digest != definition['sha256']:
                raise ValueError('model_definition.module SHA-256 does not match the adopted source')
            name = 'ers_lifecycle_model_' + digest
            module_spec = importlib.util.spec_from_file_location(name, source_path)
            if module_spec is None or module_spec.loader is None:
                raise ValueError('model_definition.module must identify a Python source file')
            module = importlib.util.module_from_spec(module_spec)
            sys.modules[name] = module
            sys.path.insert(0, str(source_path.parent))
            try:
                module_spec.loader.exec_module(module)
            finally:
                sys.path.pop(0)
            model = getattr(module, definition['factory'])(**definition.get('kwargs', {}))
            if not isinstance(model, Model):
                raise TypeError('model_definition.factory must return lcm.Model')
            native_params = jax.tree.map(lambda value: jnp.asarray(value) if isinstance(value, list) else value,
                parameters, is_leaf=lambda value: isinstance(value, list))
            source = {**definition, 'module': str(source_path), 'sha256': digest}
            settings = {'source': source, 'regime_solvers': {
                name: repr(regime.solver) for name, regime in model.user_regimes.items()}}
        else:
            raise ValueError('model_definition requires iskhakov_et_al_2017 or a hash-pinned module/factory/kwargs object')
        return model, native_params, source, settings

    builtin = spec['model_definition'] == 'iskhakov_et_al_2017'
    if builtin:
        equations = {'utility': 'u(c,d)=log(c)-disutility_of_work*1[d=work]',
            'budget': 'a=wealth-consumption>=0; wealth_next=(1+interest_rate)*a+wage*1[d=work]',
            'bellman': 'V_t(wealth,regime)=max_(c,d) {u(c,d)+discount_factor*V_(t+1)(wealth_next,regime_next)}',
            'terminal': ('retirement is absorbing; final alive consumption is the largest feasible declared grid point; V_dead=0'
                         if spec['solver'] == 'grid_search' else
                         'retirement is absorbing; the final alive period consumes all wealth; V_dead=0')}
        definitions = {'equations': equations,
            'normalization': 'log consumption utility; additive work disutility; goods in the published model units',
            'equilibrium_selection': 'individual optimum at the supplied wage and interest rate; official solver tie rule',
            'welfare_definition': 'population-weighted initial decision value; separately report the weighted sum of discounted simulated utility',
            'shocks': 'deterministic income and death; no taste or state shock in this published model',
            'parameter_definition': {key: {'value': value, 'source': spec['calibration_source'], 'status': parameter_status,
                'unit': 'goods per model period' if key == 'wage' else 'utility' if key == 'disutility_of_work' else 'dimensionless'}
                for key, value in spec['parameters'].items()}}
        beta = float(spec['parameters']['discount_factor'])
        outcome_units = {'consumption': 'goods per model period', 'assets': 'goods after consumption',
            'employment': 'working share', 'income': 'goods per model period', 'utility': 'flow log utility'}
    else:
        definitions = dict(spec['definitions'])
        required = {'equations', 'normalization', 'equilibrium_selection', 'welfare_definition', 'parameter_definition'}
        if required - definitions.keys():
            raise ValueError('definitions requires ' + ', '.join(sorted(required)))
        beta = float(spec['welfare']['discount_factor'])
        if set(spec['outcomes']) != {'consumption', 'assets', 'employment', 'income', 'utility'}:
            raise ValueError('outcomes must bind consumption, assets, employment, income and utility to native columns and units')
        outcome_units = {key: binding['unit'] for key, binding in spec['outcomes'].items()}
    if not np.isfinite(beta) or not 0 < beta <= 1:
        raise ValueError('the welfare discount factor must lie in (0,1]')

    simulation = spec.get('simulation')
    if operation in ('simulate', 'counterfactual') and simulation is None:
        raise ValueError('simulation requires initial_conditions, weights, seed and taste_shock_seed')
    if operation == 'solve' and simulation is not None:
        raise ValueError('save the solve, then select operation=simulate for forward histories')
    if simulation is not None:
        initial = {name: jnp.asarray(values) for name, values in simulation['initial_conditions'].items()}
        weights = np.asarray(simulation['weights'], dtype=float)
        if (weights.ndim != 1 or not weights.size or not np.isfinite(weights).all() or
                (weights < 0).any() or abs(weights.sum()-1) > 1e-12 or
                any(values.ndim != 1 or len(values) != len(weights) for values in initial.values())):
            raise ValueError('initial_conditions requires equally sized vectors and weights requires nonnegative masses summing to one')
        if any(type(simulation[key]) is not int for key in ('seed', 'taste_shock_seed')):
            raise ValueError('simulation seed and taste_shock_seed must be integers')
        shock_paths = {key: jnp.asarray(values) for key, values in simulation.get('shock_paths', {}).items()}
    scenarios = {'baseline': {'parameters': spec['parameters'], 'model_definition': spec['model_definition']}}
    if operation == 'counterfactual':
        change = spec['scenario']
        scenarios['scenario'] = {'parameters': merge_parameters(spec['parameters'], change['parameters']),
            'model_definition': change.get('model_definition', spec['model_definition'])}
        if builtin and scenarios['scenario']['model_definition'] != spec['model_definition']:
            raise ValueError('the published retirement comparison retains its model_definition; declare a project factory for another model')
        if builtin and any(scenarios['scenario']['parameters'][key] != spec['parameters'][key]
                for key in ('discount_factor', 'disutility_of_work')):
            raise ValueError('retirement welfare comparisons retain discount_factor and disutility_of_work')

    results, statistics, value_rows, policy_rows, history_rows, welfare_rows = {}, {}, [], [], [], []
    executed, native_calls = [], []
    horizon = None
    for scenario_name, scenario_spec in scenarios.items():
        model, params, model_source, settings = construct(scenario_spec['model_definition'], scenario_spec['parameters'])
        if horizon is not None and model.n_periods != horizon:
            raise ValueError('counterfactuals must retain the adopted horizon')
        horizon = model.n_periods
        actions = []
        reuse = spec.get('saved_solution') if scenario_name == 'baseline' else spec['scenario'].get('saved_solution')
        if reuse is not None:
            solution_path = local_path(reuse['path'])
            if hashlib.sha256(solution_path.read_bytes()).hexdigest() != reuse['sha256']:
                raise ValueError('saved_solution SHA-256 does not match the adopted native archive')
            solution = load_solution(path=solution_path, verify_checksums=True)
            actions.append('load_solution')
            native_calls.append({'scenario': scenario_name, 'function': 'lcm.persistence.load_solution', 'path': str(solution_path)})
        else:
            solution_path = local_path(spec['solution_path'] if scenario_name == 'baseline' else spec['scenario']['solution_path'])
            if solution_path.exists():
                raise FileExistsError('solution_path already exists; reuse it through saved_solution or select a new output path')
            solution = model.solve(params=params, log_level='off', runtime_checks=True)
            save_solution(solution=solution, path=solution_path)
            actions.append('solve')
            native_calls.extend([{'scenario': scenario_name, 'function': 'lcm.Model.solve'},
                {'scenario': scenario_name, 'function': 'lcm.persistence.save_solution', 'path': str(solution_path)}])
        native_identity = solution.metadata
        value_functions = []
        for period, regimes in solution.values.items():
            for regime in regimes:
                array = solution.value_array(period=period, regime=regime)
                values = np.asarray(array)
                value_functions.append({'period': period, 'regime': regime, 'axes': list(array.dims),
                    'coordinates': {name: np.asarray(array.coords[name]).tolist() for name in array.dims},
                    'values': np.where(np.isfinite(values), values, None).tolist(),
                    'finite': np.isfinite(values).tolist()})
                # Infeasible states retain their native nonfinite values in the archive.
                # The JSON/reporting projection selects the finite solved states.
                frame = solution.value_frame(period=period, regime=regime)
                for row in frame.loc[np.isfinite(frame['V'])].to_dict('records'):
                    value_rows.append({'scenario': scenario_name, 'period': period, 'regime': regime,
                        **row, 'unit': 'expected discounted utility'})
        evaluations = []
        for query in spec.get('evaluation', []):
            policy = model.lookup_policy(params=params, solution=solution, period=query['period'],
                regime_name=query['regime'], states={name: jnp.asarray(values) for name, values in query['states'].items()})
            evaluation = {**query, 'value': np.asarray(policy.value).tolist(),
                'actions': None if policy.actions is None else {key: np.asarray(value).tolist() for key, value in policy.actions.items()},
                'conditional_actions': None if policy.conditional_actions is None else {
                    key: np.asarray(value).tolist() for key, value in policy.conditional_actions.items()},
                'choice_probabilities': None if policy.choice_probabilities is None else np.asarray(policy.choice_probabilities).tolist()}
            evaluation['action_categories'] = {key: {'codes': list(grid.codes), 'labels': list(grid.categories)}
                for key, grid in model.user_regimes[query['regime']].actions.items() if isinstance(grid, DiscreteGrid)}
            evaluations.append(evaluation)
            for index, value in enumerate(evaluation['value']):
                coordinate = {'scenario': scenario_name, 'period': query['period'], 'regime': query['regime'],
                    **{key: values[index] for key, values in query['states'].items()}}
                policy_rows.append({**coordinate, 'quantity': 'value', 'value': value, 'unit': 'expected discounted utility'})
                for key, values in (evaluation['actions'] or {}).items():
                    native_units = outcome_units if builtin else {
                        binding['column']: binding['unit'] for binding in spec['outcomes'].values()}
                    unit = query.get('action_units', {}).get(key, native_units.get(key))
                    if key in evaluation['action_categories']:
                        unit = 'category code'
                    if unit is None:
                        raise ValueError(f'evaluation.action_units requires the unit of action {key}')
                    policy_rows.append({**coordinate, 'quantity': key, 'value': values[index],
                        'unit': unit})
        saved_params = jax.tree.map(lambda value: np.asarray(value).tolist() if isinstance(value, (jax.Array, np.ndarray)) else value, params)
        outcome = {'parameters': scenario_spec['parameters'], 'native_parameters': saved_params, 'model_source': model_source,
            'numerical_settings': settings, 'operations_executed': actions,
            'solution': {'path': str(solution_path.resolve()), 'sha256': hashlib.sha256(solution_path.read_bytes()).hexdigest(),
                'model_fingerprint': native_identity.model_fingerprint, 'params_fingerprint': native_identity.params_fingerprint,
                'solver_types': dict(native_identity.solver_types), 'solution_schema_version': native_identity.solution_schema_version,
                'solver_api_version': native_identity.solver_api_version, 'reused': reuse is not None},
            'value_functions': value_functions, 'policy_evaluation': evaluations}
        if simulation is not None:
            native_simulation = model.simulate(params=params, initial_conditions=initial, solution=solution,
                log_level='off', runtime_checks=True, seed=simulation['seed'], taste_shock_seed=simulation['taste_shock_seed'],
                shock_paths=shock_paths or None)
            targets = ['utility', 'labor_income', 'is_working'] if builtin else [
                binding['column'] for binding in spec['outcomes'].values() if binding['column'] in native_simulation.available_targets]
            frame = native_simulation.to_dataframe(additional_targets=list(dict.fromkeys(targets)),
                use_categorical_codes=True, terminal_rows='all')
            reported = frame[['subject_id', 'period', 'regime_name', 'value']].copy()
            if 'age' in frame:
                reported['age'] = frame['age']
            if builtin:
                dead = frame['regime_name'] == 'dead'
                reported['consumption'] = frame['consumption'].where(~dead, 0.)
                reported['assets'] = (frame['wealth']-frame['consumption']).where(~dead, 0.)
                reported['employment'] = frame['is_working'].where(frame['regime_name'] == 'working_life', False).astype(float)
                reported['income'] = frame['labor_income'].where(frame['regime_name'] == 'working_life', 0.)
                reported['utility'] = frame['utility']
            else:
                for quantity, binding in spec['outcomes'].items():
                    values = (frame[binding['column']].copy() if binding['column'] in frame else
                              pd.Series(np.nan, index=frame.index))
                    for regime, value in binding.get('fill_by_regime', {}).items():
                        values = values.mask(values.isna() & (frame['regime_name'] == regime), value)
                    reported[quantity] = values.astype(float)
            if not np.isfinite(reported[list(outcome_units)].to_numpy(dtype=float)).all():
                raise ArithmeticError('each reported outcome must be finite in every simulated regime; bind its terminal or inactive value explicitly')
            ordered = reported.sort_values(['subject_id', 'period'])
            entry = ordered.groupby('subject_id', sort=True).first()
            if list(entry.index) != list(range(len(weights))):
                raise ArithmeticError('native simulation subject IDs must preserve the complete supplied population')
            first_period = reported['subject_id'].map(entry['period'])
            discounted_flow = reported['utility'] * beta ** (reported['period']-first_period)
            individual_utility = discounted_flow.groupby(reported['subject_id']).sum().reindex(entry.index).to_numpy()
            expected_welfare = float(weights @ entry['value'].to_numpy())
            realized_welfare = float(weights @ individual_utility)
            outcome.update(native_simulation=frame.astype(object).where(pd.notna(frame), None).to_dict('records'),
                histories=reported.to_dict('records'), randomness=dict(native_simulation.randomness),
                individual_discounted_utility=individual_utility.tolist(),
                welfare={'initial_value': expected_welfare, 'discounted_simulated_utility': realized_welfare})
            for quantity, value in outcome['welfare'].items():
                statistics[f'{scenario_name}.{quantity}'] = {'value': value, 'unit': 'discounted utility per initial person'}
                welfare_rows.append({'scenario': scenario_name, 'quantity': quantity, 'value': value,
                    'unit': 'discounted utility per initial person'})
            for period, rows in reported.groupby('period', sort=True):
                period_weights = weights[rows['subject_id'].to_numpy(dtype=int)]
                mass = float(period_weights.sum())
                if mass == 0:
                    continue
                for quantity, unit in outcome_units.items():
                    average = float(period_weights @ rows[quantity].to_numpy(dtype=float) / mass)
                    statistics[f'{scenario_name}.period_{period}.{quantity}'] = {'value': average, 'unit': unit}
                    history_rows.append({'scenario': scenario_name, 'period': int(period), 'quantity': quantity,
                        'value': average, 'population_mass': mass, 'unit': unit})
            if builtin:
                alive = frame.loc[frame['regime_name'] != 'dead'].copy()
                saving = alive['wealth'].to_numpy()-alive['consumption'].to_numpy()
                income = reported.loc[alive.index, 'income'].to_numpy()
                current = alive.set_index(['subject_id', 'period'])
                residuals = []
                for index, row in enumerate(alive.itertuples()):
                    following = (row.subject_id, row.period+1)
                    if following in current.index:
                        residuals.append(float(current.loc[following, 'wealth'] - ((1+scenario_spec['parameters']['interest_rate'])*saving[index]+income[index])))
                residual = max(map(abs, residuals), default=0.)
                final_alive = alive['period'].to_numpy() == horizon-2
                terminal_saving = saving[final_alive]
                terminal_consumption_error = float(np.max(np.abs(terminal_saving)))
                if spec['solver'] == 'grid_search':
                    grid = np.asarray(settings['consumption_grid'])
                    wealth = alive['wealth'].to_numpy()[final_alive]
                    indices = np.searchsorted(grid, wealth + 1e-12, side='right')-1
                    if np.any(indices < 0):
                        raise ArithmeticError('final resources are below the declared consumption grid')
                    chosen = alive['consumption'].to_numpy()[final_alive]
                    terminal_consumption_error = float(np.max(np.abs(chosen-grid[indices])))
                outcome['diagnostics'] = {'max_wealth_transition_residual': residual,
                    'minimum_savings': float(saving.min()), 'max_final_alive_savings': float(np.max(np.abs(terminal_saving))),
                    'max_terminal_consumption_optimality_residual': terminal_consumption_error}
                if residual > 1e-9 or saving.min() < -1e-9 or terminal_consumption_error > 1e-9:
                    raise ArithmeticError('the simulated retirement path violates its wealth transition, borrowing bound or terminal condition')
            actions.append('simulate')
            native_calls.append({'scenario': scenario_name, 'function': 'lcm.Model.simulate', 'solution': str(solution_path),
                'seed': simulation['seed'], 'taste_shock_seed': simulation['taste_shock_seed']})
        results[scenario_name] = outcome
        executed.extend(action for action in actions if action not in executed)
    if operation == 'counterfactual':
        for key, value in list(statistics.items()):
            if key.startswith('scenario.'):
                name = key[len('scenario.'):]
                statistics['change.'+name] = {'value': value['value']-statistics['baseline.'+name]['value'], 'unit': value['unit']}
        for name in ('initial_value', 'discounted_simulated_utility'):
            welfare_rows.append({'scenario': 'change', 'quantity': name, **statistics['change.'+name]})
    computation = {'requested_operation': operation, 'available_operations': ['solve', 'simulate', 'counterfactual'],
        'operations_executed': executed, 'native_calls': native_calls,
        'parameter_status': parameter_status,
        'parameter_operation': {
            'fixed': 'hold supplied fixed parameters; estimate no parameters',
            'calibrated': 'hold supplied calibrated parameters; estimate no parameters',
            'estimated': 'reuse supplied previously estimated parameters; estimate no parameters',
        }[parameter_status]}
    definitions.update(horizon={'n_periods': horizon, 'discount_factor': beta, 'time_unit': 'model period'},
        computation=computation, model_contract='MC-lifecycle-regimes')
    displays = {}
    for name, rows, title in (('value_functions', value_rows, 'Solved lifecycle values'),
            ('policies', policy_rows, 'Lifecycle policy evaluations'), ('histories', history_rows, 'Lifecycle population outcomes'),
            ('welfare', welfare_rows, 'Lifecycle welfare')):
        if rows:
            displays[name] = {'kind': 'table' if name != 'histories' else 'structural', 'title': title,
                'rows': rows, 'columns': [{'key': key, 'label': key, 'unit': ''} for key in dict.fromkeys(key for row in rows for key in row)],
                'metadata': {**definitions, 'report_role': 'counterfactual' if operation == 'counterfactual' else 'model_fit'},
                'display': {'plot_type': 'line', 'x': 'period', 'y': 'value', 'series': 'scenario', 'facet': 'quantity'}
                    if name == 'histories' else {'plot_type': 'table'}}
    return {'result_format_version': 1, 'model': 'lifecycle_choice', 'model_contract': 'MC-lifecycle-regimes',
        'knowledge_ids': ['DYN-02'], 'engine': 'lcm.Model.solve; lcm.persistence.load_solution; lcm.Model.simulate',
        'adopted': spec, 'calibration': {'source': spec['calibration_source'], 'estimated_parameters': []},
        **definitions, **results, 'simulation_inputs': simulation, 'statistics': statistics, 'displays': displays,
        'provenance': {'python': sys.version.split()[0], 'numpy': np.__version__, 'scipy': scipy.__version__,
            'pylcm': package_version, 'pylcm_revision': '0fb55673b0be4eb52d270b2585047faa38c4e930',
            'jax': jax.__version__, 'jaxlib': version('jaxlib'), 'backend': jax.default_backend(), 'jax_enable_x64': True}}


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


def solve(spec, base_dir=Path.cwd()):
    model = spec.get('model', 'olg')
    if model in ('qse_commuting', 'qse_open_city', 'qse_imperfect_mobility'):
        return solve_qse(spec, base_dir)
    if model == 'lifecycle_choice':
        return lifecycle_run(spec, base_dir)
    if model == 'consumption_saving':
        return solve_hark(spec)
    if model == 'aiyagari':
        return solve_aiyagari(spec)
    if model != 'olg':
        raise ValueError('model must be olg, aiyagari, consumption_saving, lifecycle_choice, qse_commuting, qse_open_city or qse_imperfect_mobility')
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
    fields = ('capital','next_capital','output','wage','rental_rate','government_absorption')
    irf = [{name: scenario_path[t][name]-baseline[t][name] for name in fields} for t in range(horizon)]
    maxres = max(abs(x['resource_residual']) for x in baseline+scenario_path)
    if maxres > 1e-8: raise ArithmeticError(f'resource residual {maxres}')
    wbase = float(shares@np.asarray(baseline[0]['cohort_welfare']))
    wscenario = float(shares@np.asarray(scenario_path[0]['cohort_welfare']))
    stats = {'sequence_jacobian_analytic_error': {'value':official_error,'unit':'goods per unit log productivity'},
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
        'sequence_space_jacobian': {'engine':'sequence_jacobian.simple.solve_jacobian', 'output_to_log_productivity':official_jacobian.tolist(), 'analytic_max_abs_error':official_error},
        'steady_state':{'baseline_capital':k0,'scenario_capital':parameters(scenario)[4], 'aggregate_productivity':aggregate_a,
            'firm_capital_shares':alloc.tolist()},
        'baseline':baseline,'simulation':scenario_path,'impulse_response':irf,'statistics':stats,
        'provenance':{'python':sys.version.split()[0],'numpy':np.__version__,'scipy':scipy.__version__, 'sequence_jacobian':version('sequence-jacobian')}}


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
        columns = [('scenario', 'Scenario'), ('asset', 'Current assets'), ('income_state', 'Income state'), ('income', 'Labor efficiency'), ('series', 'Series'), ('value', title), ('unit', 'Unit')] if curve else [('scenario', 'Scenario'), ('statistic', 'Statistic'), ('value', 'Value'), ('unit', 'Unit')]
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


def solve_qse(spec, base_dir=Path.cwd()):
    """Invert ARSW fundamentals and solve the declared city-mobility closure."""
    model = spec.get('model', 'qse_commuting')
    open_city = model == 'qse_open_city'
    imperfect_mobility = model == 'qse_imperfect_mobility'
    contracts = {'qse_commuting': 'MC-qse-commuting', 'qse_open_city': 'MC-qse-open-city',
                 'qse_imperfect_mobility': 'MC-qse-imperfect-mobility'}
    if model not in contracts:
        raise ValueError('solve_qse requires a supported QSE model')
    closure = {'qse_commuting': 'closed', 'qse_open_city': 'open',
               'qse_imperfect_mobility': 'imperfect_mobility'}[model]
    operation = spec['operation']
    if operation not in ('invert_baseline', 'counterfactual'):
        raise ValueError('qse_commuting operation must be invert_baseline or counterfactual')
    if (open_city or imperfect_mobility) and operation != 'counterfactual':
        raise ValueError(f'{model} requires counterfactual from a saved qse_commuting baseline')
    if spec.get('closure', closure) != closure:
        raise ValueError(f'{model} requires {closure} population closure')
    if not imperfect_mobility and 'migration' in spec:
        raise ValueError('migration inputs require model=qse_imperfect_mobility')
    equations = {'choice': 'phi_ij=exp(-epsilon*kappa*t_ij)*B_i^epsilon*q_i^(-(1-beta)*epsilon)*w_j^epsilon; pi_ij=phi_ij/sum(phi)',
        'population': 'R_i=N*sum_j pi_ij; L_j=N*sum_i pi_ij; I_i=N*sum_j pi_ij*w_j',
        'spillovers': 'A_i=a_i*(sum_j exp(-productivity_decay*t_ij)*L_j/area_j)^productivity_spillover; B_i=b_i*(sum_j exp(-amenity_decay*t_ij)*R_j/area_j)^amenity_spillover',
        'production': 'Y_i=A_i*L_i^alpha*S_i^(1-alpha); w_i=alpha*Y_i/L_i; q_i=(1-alpha)*Y_i/S_i',
        'floor': 'S_i=(1-alpha)*Y_i/q_i; H_i=(1-beta)*I_i/q_i; S_i+H_i=F_i; theta_i=S_i/F_i',
        'goods': 'sum_i Y_i=beta*sum_i I_i+sum_i q_i*F_i; profits_i=Y_i-w_i*L_i-q_i*S_i=0',
        'welfare': 'U=Gamma(1-1/epsilon)*(sum_ij phi_ij)^(1/epsilon); chi=U_s/U_b-1; EV_workers=chi*sum_j w_bj*L_bj; EV_owners=sum_i(q_si*F_si-q_bi*F_bi)',
        'local_value': 'U_i_fixed=Gamma(1-1/epsilon)*(sum_j phi_ij)^(1/epsilon), expected best workplace utility when residence is fixed at i'}
    migration_equation = 'log(U_s/U_b)=0; U_b is saved baseline expected utility; N_s is endogenous'
    open_welfare_equation = ('U=Gamma(1-1/epsilon)*(sum_ij phi_ij)^(1/epsilon)=U_b; '
        'chi=U_s/U_b-1; EV_baseline_workers=chi*sum_j w_bj*L_bj; '
        'population_change=N_s-N_b; EV_owners=sum_i(q_si*F_si-q_bi*F_bi)')
    imperfect_equations = {
        'migration': 'N=N_bar*U^zeta/(U^zeta+U_tilde); logit(N/N_bar)-logit(s_b)=zeta*log(U/U_b)',
        'migration_calibration': 'N_bar=N_b/s_b; U_tilde=U_b^zeta*(1-s_b)/s_b; s_b=baseline_urban_share',
        'regional_welfare': 'V=(U^zeta+U_tilde)^(1/zeta); log(V_s/V_b)=log((1-s_b)+s_b*(U_s/U_b)^zeta)/zeta',
        'welfare': 'city_chi=U_s/U_b-1; EV_city_opportunities=city_chi*sum_j w_bj*L_bj; '
                   'EV_owners=sum_i(q_si*F_si-q_bi*F_bi); regional_log_value_change=log(V_s/V_b)'}
    options = {'tolerance': 1e-9, 'max_iterations': 10000, **spec.get('solver', {})}
    if set(options) != {'tolerance', 'max_iterations'}:
        raise ValueError('solver accepts tolerance and max_iterations')
    tolerance, max_iterations = float(options['tolerance']), options['max_iterations']
    if (not np.isfinite(tolerance) or not 1e-12 <= tolerance < 1e-3 or
            type(max_iterations) is not int or max_iterations < 1):
        raise ValueError('require 1e-12 <= tolerance < 1e-3 and positive integer max_iterations')
    reused, executed = None, []
    if operation == 'counterfactual':
        if any(key in spec for key in ('baseline', 'parameters', 'calibration_source')):
            raise ValueError('counterfactual restores baseline and parameters from saved_solution')
        reuse = spec['saved_solution']
        path = Path(reuse['path'])
        if not path.is_absolute():
            path = base_dir / path
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != reuse['sha256']:
            raise ValueError('saved_solution SHA-256 does not match')
        saved = json.loads(raw)
        saved_model = saved.get('model')
        expected_equations = dict(equations)
        if saved_model == 'qse_open_city':
            expected_equations.update(migration=migration_equation, welfare=open_welfare_equation)
        elif saved_model == 'qse_imperfect_mobility':
            expected_equations.update(imperfect_equations)
        # The numerical contract survives unrelated changes in this multi-model file.
        # Versionless 0.68 results retain their verified producing implementation.
        compatible = saved.get('qse_numerical_contract_version') == 1
        if 'qse_numerical_contract_version' not in saved:
            compatible = saved.get('provenance', {}).get('producer_sha256') == (
                '103b6ed7349325aac7fdef778da8fdcacf87b7d20722eb9181152c0ff23778cc')
        if (saved_model not in contracts or saved.get('result_format_version') != 1 or
                saved.get('model_contract') != contracts.get(saved_model) or
                saved.get('equations') != expected_equations or not compatible):
            raise ValueError('saved_solution requires the compatible QSE numerical contract and original equations')
        baseline_input, parameters = saved['baseline_inputs'], saved['calibration']['parameters']
        calibration_source = saved['calibration']['source']
        reused = {'path': str(path.resolve()), 'sha256': reuse['sha256'],
                  'objects': ['primitives', 'baseline', 'inversion', 'calibration'],
                  'qse_numerical_contract_version': 1,
                  'producer_sha256': saved['provenance']['producer_sha256']}
        executed.append('load_baseline')
    else:
        if 'saved_solution' in spec or 'scenario' in spec:
            raise ValueError('invert_baseline takes baseline and parameters; run counterfactual from its saved result')
        baseline_input, parameters = spec['baseline'], spec['parameters']
        calibration_source = spec['calibration_source']
    parameter_names = {'alpha', 'beta', 'epsilon', 'kappa', 'productivity_spillover',
                       'productivity_decay', 'amenity_spillover', 'amenity_decay'}
    if set(parameters) != parameter_names:
        raise ValueError('parameters requires exactly ' + ', '.join(sorted(parameter_names)))
    p = {key: float(value) for key, value in parameters.items()}
    if (not all(np.isfinite(value) for value in p.values()) or not 0 < p['alpha'] < 1 or
            not 0 < p['beta'] < 1 or p['epsilon'] <= 1 or
            min(p['kappa'], p['productivity_decay'], p['amenity_decay']) < 0):
        raise ValueError('require alpha,beta in (0,1), epsilon>1, nonnegative decay and finite spillover elasticities')
    if not isinstance(calibration_source, str) or not calibration_source.strip():
        raise ValueError('calibration_source must identify the supplied parameters')
    ids = baseline_input['location_ids']
    if (not isinstance(ids, list) or not ids or
            any(not isinstance(key, str) or not key for key in ids) or len(set(ids)) != len(ids)):
        raise ValueError('location_ids requires distinct nonempty strings in matrix order')
    n = len(ids)

    def positive_vector(value, name, scalar=False):
        result = np.asarray(value, dtype=float)
        if scalar and result.ndim == 0:
            result = np.full(n, float(result))
        if result.shape != (n,) or not np.isfinite(result).all() or np.any(result <= 0):
            raise ValueError(name + ' requires one finite positive value per location')
        return result

    def time_matrix(value):
        result = np.asarray(value, dtype=float)
        if result.shape != (n, n) or not np.isfinite(result).all() or np.any(result < 0):
            raise ValueError('travel_time requires a finite nonnegative location-by-location matrix')
        return result

    observed_r = positive_vector(baseline_input['population'], 'baseline.population')
    observed_l = positive_vector(baseline_input['employment'], 'baseline.employment')
    area = positive_vector(baseline_input['land_area'], 'baseline.land_area')
    wage_numeraire = float(baseline_input['wage_numeraire'])
    if not np.isfinite(wage_numeraire) or wage_numeraire <= 0:
        raise ValueError('baseline.wage_numeraire requires the positive mean wage in the rent currency and period')
    observed_q = positive_vector(baseline_input['rent'], 'baseline.rent') / wage_numeraire
    travel = time_matrix(baseline_input['travel_time'])
    if not isinstance(baseline_input['source'], str) or not baseline_input['source'].strip():
        raise ValueError('baseline.source must identify the observations and their units')
    population = float(observed_r.sum())
    if not np.isclose(observed_l.sum(), population, rtol=1e-12, atol=0):
        raise ValueError('residential population and workplace employment must have equal totals')
    alpha, beta, epsilon = p['alpha'], p['beta'], p['epsilon']
    log_n, log_area = np.log(population), np.log(area)

    def evaluate(x, primitives, times, reservation_utility=None, migration=None):
        city_log_n = log_n
        city_state = x
        if reservation_utility is not None:
            city_log_n, city_state = x[-1], x[:-1]
        elif migration is not None:
            # A log-odds coordinate keeps both city and hinterland masses positive.
            city_log_n = migration['log_total_population']-np.logaddexp(0., -x[-1])
            city_state = x[:-1]
        log_w, log_q, log_l, log_r = np.split(city_state, 4)
        log_a = np.log(primitives['productivity']) + p['productivity_spillover'] * logsumexp(
            -p['productivity_decay'] * times + (log_l-log_area)[None, :], axis=1)
        log_b = np.log(primitives['amenity']) + p['amenity_spillover'] * logsumexp(
            -p['amenity_decay'] * times + (log_r-log_area)[None, :], axis=1)
        log_phi = epsilon * (log_b[:, None]-(1-beta)*log_q[:, None]+log_w[None, :]-p['kappa']*times)
        log_phi_sum = logsumexp(log_phi)
        log_pi = log_phi-log_phi_sum
        log_income = city_log_n+logsumexp(log_pi+log_w[None, :], axis=1)
        log_commercial = np.log((1-alpha)/alpha)+log_w+log_l-log_q
        log_residential = np.log(1-beta)+log_income-log_q
        log_f = np.log(primitives['floor_space'])
        # Firm cost minimization eliminates commercial floor demand; zero profit
        # and total floor clearing retain the original production and rent equations.
        residual = np.concatenate((
            log_l-city_log_n-logsumexp(log_pi, axis=0),
            log_r-city_log_n-logsumexp(log_pi, axis=1),
            log_w-np.log(alpha)-(log_a+(1-alpha)*(np.log(1-alpha)-log_q))/alpha,
            np.logaddexp(log_commercial, log_residential)-log_f))
        if reservation_utility is not None:
            log_utility = gammaln(1-1/epsilon)+log_phi_sum/epsilon
            residual = np.append(residual, log_utility-np.log(reservation_utility))
        elif migration is not None:
            log_utility = gammaln(1-1/epsilon)+log_phi_sum/epsilon
            residual = np.append(residual, x[-1]-migration['baseline_log_odds']-
                                 migration['zeta']*(log_utility-migration['baseline_log_utility']))
        return residual, (log_w, log_q, log_l, log_r, log_a, log_b, log_pi,
                          log_income, log_commercial, log_residential, log_phi, log_phi_sum, city_log_n)

    def equilibrium(primitives, times, initial, reservation_utility=None, migration=None):
        if reservation_utility is not None:
            initial = np.append(initial, log_n)
        elif migration is not None:
            initial = np.append(initial, migration['baseline_log_odds'])
        fit = least_squares(lambda x: evaluate(x, primitives, times, reservation_utility, migration)[0], initial,
                            method='trf', ftol=1e-13, xtol=1e-13, gtol=1e-13,
                            max_nfev=max_iterations)
        residual, values = evaluate(fit.x, primitives, times, reservation_utility, migration)
        if not fit.success or not np.isfinite(residual).all() or np.max(np.abs(residual)) > tolerance:
            raise ArithmeticError(f'QSE equilibrium failed: {fit.message}; max log residual={np.max(np.abs(residual))}')
        (log_w, log_q, log_l, log_r, log_a, log_b, log_pi, log_income,
         log_commercial, log_residential, log_phi, log_phi_sum, city_log_n) = values
        city_population = population if reservation_utility is None and migration is None else float(np.exp(city_log_n))
        w, q, labor, residents, a, b = (np.exp(v) for v in values[:6])
        probability, income = np.exp(log_pi), np.exp(log_income)
        commercial, residential = np.exp(log_commercial), np.exp(log_residential)
        floor = np.asarray(primitives['floor_space'])
        theta = commercial/floor
        output = a*labor**alpha*commercial**(1-alpha)
        wage_bill, property_income = w*labor, q*floor
        worker_consumption = beta*income
        profit = output-wage_bill-q*commercial
        labor_demand = (alpha*a/w)**(1/(1-alpha))*commercial
        utility = float(np.exp(gammaln(1-1/epsilon)+log_phi_sum/epsilon))
        local_utility = np.exp(gammaln(1-1/epsilon)+logsumexp(log_phi, axis=1)/epsilon)
        local = {'wage': w, 'rent': q, 'employment': labor, 'population': residents,
            'commercial_share': theta, 'commercial_floor': commercial, 'residential_floor': residential,
            'floor_space': floor, 'output': output, 'resident_income': income,
            'worker_consumption': worker_consumption, 'owner_income': property_income,
            'firm_profit': profit, 'productivity': a, 'amenity': b,
            'residence_fixed_expected_utility': local_utility,
            'net_exports': output-worker_consumption-property_income}
        diagnostics = {'labor_choice_max_relative_residual': float(np.max(np.abs(city_population*probability.sum(0)-labor)/labor)),
            'residence_choice_max_relative_residual': float(np.max(np.abs(city_population*probability.sum(1)-residents)/residents)),
            'labor_market_max_relative_residual': float(np.max(np.abs(labor_demand-labor)/labor)),
            'floor_market_max_relative_residual': float(np.max(np.abs(commercial+residential-floor)/floor)),
            'firm_profit_max_relative_residual': float(np.max(np.abs(profit)/output)),
            'population_relative_residual': float(abs(residents.sum()-city_population)/city_population),
            'employment_relative_residual': float(abs(labor.sum()-city_population)/city_population),
            'goods_market_relative_residual': float(abs(output.sum()-worker_consumption.sum()-property_income.sum())/output.sum()),
            'probability_mass_residual': float(abs(probability.sum()-1)),
            'max_log_equation_residual': float(np.max(np.abs(residual)))}
        if reservation_utility is not None:
            diagnostics['migration_utility_log_residual'] = float(abs(np.log(utility/reservation_utility)))
        elif migration is not None:
            target_log_odds = migration['baseline_log_odds']+migration['zeta']*(np.log(utility)-migration['baseline_log_utility'])
            target_log_n = migration['log_total_population']-np.logaddexp(0., -target_log_odds)
            diagnostics['migration_log_odds_residual'] = float(abs(residual[-1]))
            diagnostics['migration_population_relative_residual'] = float(abs(np.expm1(city_log_n-target_log_n)))
        if (not all(np.isfinite(v).all() for v in local.values()) or not np.isfinite(utility) or
                not np.all((theta > 0) & (theta < 1)) or max(diagnostics.values()) > 10*tolerance):
            raise ArithmeticError('QSE original equations, finite outcomes or mixed-use floor allocation failed')
        aggregate = {'population': float(residents.sum()), 'employment': float(labor.sum()),
            'output': float(output.sum()), 'wage_bill': float(wage_bill.sum()),
            'worker_consumption': float(worker_consumption.sum()), 'owner_income': float(property_income.sum()),
            'firm_profit': float(profit.sum()), 'expected_utility': utility,
            'mean_commute_time': float(np.sum(probability*times)),
            'goods_market_residual': float(output.sum()-worker_consumption.sum()-property_income.sum())}
        original = {'labor_market': labor_demand-labor, 'floor_market': commercial+residential-floor,
                    'firm_profit': profit, 'labor_choice': city_population*probability.sum(0)-labor,
                    'residence_choice': city_population*probability.sum(1)-residents}
        if reservation_utility is not None:
            original['migration_utility'] = np.array([utility-reservation_utility])
        elif migration is not None:
            original['migration_population'] = np.array([city_population-np.exp(target_log_n)])
        return {'local': {key: value.tolist() for key, value in local.items()}, 'aggregate': aggregate,
            'commuting_probability': probability.tolist(), 'commuting_flows': (city_population*probability).tolist(),
            'travel_time': times.tolist(), 'state_log': fit.x.tolist(), 'diagnostics': diagnostics,
            'original_residuals': {key: value.tolist() for key, value in original.items()},
            'solver': {'method': 'scipy.optimize.least_squares(trf)', 'success': bool(fit.success),
                       'message': fit.message, 'nfev': int(fit.nfev), 'cost': float(fit.cost),
                       'optimality': float(fit.optimality), 'residual_tolerance': tolerance,
                       **({'population_coordinate': 'logit(N/N_bar)'} if migration is not None else {})}}

    if operation == 'invert_baseline':
        log_rows, log_cols = np.log(observed_r/population), np.log(observed_l/population)
        log_kernel = -epsilon*p['kappa']*travel
        inversion_tolerance = min(tolerance, 1e-11)
        # Fix one destination multiplier to remove the origin/destination gauge.
        # Row multipliers follow analytically from the observed origin masses.
        def marginals(destination):
            log_v = np.r_[destination, 0.]
            log_u = log_rows-logsumexp(log_kernel+log_v[None, :], axis=1)
            log_pi = log_u[:, None]+log_kernel+log_v[None, :]
            return logsumexp(log_pi, axis=0)-log_cols
        if n > 1:
            balancing = least_squares(marginals, np.zeros(n-1), method='trf',
                                      ftol=1e-13, xtol=1e-13, gtol=1e-13,
                                      max_nfev=max_iterations)
            log_v = np.r_[balancing.x, 0.]
            iteration = int(balancing.nfev)
            if not balancing.success:
                raise ArithmeticError('QSE baseline balancing failed: '+balancing.message)
        else:
            log_v = np.zeros(1)
            iteration = 0
        log_u = log_rows-logsumexp(log_kernel+log_v[None, :], axis=1)
        log_pi = log_u[:, None]+log_kernel+log_v[None, :]
        gap = max(float(np.max(np.abs(logsumexp(log_pi, axis=1)-log_rows))),
                  float(np.max(np.abs(logsumexp(log_pi, axis=0)-log_cols))))
        if not np.isfinite(gap) or gap > inversion_tolerance:
            raise ArithmeticError(f'QSE baseline balancing failed: max log marginal residual={gap}')
        log_w = log_v/epsilon
        log_w -= logsumexp(log_w+log_cols)
        log_b = log_u/epsilon+(1-beta)*np.log(observed_q)
        log_b -= logsumexp(log_b+log_rows)
        log_income = log_n+logsumexp(log_pi+log_w[None, :], axis=1)
        log_commercial = np.log((1-alpha)/alpha)+log_w+np.log(observed_l)-np.log(observed_q)
        log_residential = np.log(1-beta)+log_income-np.log(observed_q)
        log_a = alpha*(log_w-np.log(alpha))+(1-alpha)*(np.log(observed_q)-np.log(1-alpha))
        fundamentals_a = log_a-p['productivity_spillover']*logsumexp(
            -p['productivity_decay']*travel+(np.log(observed_l)-log_area)[None, :], axis=1)
        fundamentals_b = log_b-p['amenity_spillover']*logsumexp(
            -p['amenity_decay']*travel+(np.log(observed_r)-log_area)[None, :], axis=1)
        primitives = {'productivity': np.exp(fundamentals_a).tolist(), 'amenity': np.exp(fundamentals_b).tolist(),
                      'floor_space': np.exp(np.logaddexp(log_commercial, log_residential)).tolist(),
                      'land_area': area.tolist(), 'population': population}
        initial = np.concatenate((log_w, np.log(observed_q), np.log(observed_l), np.log(observed_r)))
        baseline = equilibrium(primitives, travel, initial)
        reproduction = max(float(np.max(np.abs(np.asarray(baseline['local'][key])/observed-1)))
                           for key, observed in (('population', observed_r), ('employment', observed_l), ('rent', observed_q)))
        if reproduction > 10*tolerance:
            raise ArithmeticError(f'QSE baseline reproduction failed: max relative gap={reproduction}')
        inversion = {'method': 'scipy.optimize.least_squares(trf) log-coordinate marginals', 'iterations': iteration,
                     'max_log_marginal_residual': gap, 'max_observation_relative_gap': reproduction,
                     'tolerance': inversion_tolerance}
        executed.extend(['invert_baseline', 'solve_baseline'])
    else:
        primitives, baseline, inversion = saved['primitives'], saved['baseline'], saved['inversion']
        residual, baseline_values = evaluate(np.asarray(baseline['state_log']), primitives, travel)
        if not np.isfinite(residual).all() or np.max(np.abs(residual)) > tolerance:
            raise ValueError('saved baseline fails the requested original-equation tolerance')
        baseline_log_utility = gammaln(1-1/epsilon)+baseline_values[-2]/epsilon
        saved_utility = float(baseline['aggregate']['expected_utility'])
        if (not np.isfinite(saved_utility) or saved_utility <= 0 or
                abs(baseline_log_utility-np.log(saved_utility)) > tolerance):
            raise ValueError('saved baseline expected utility fails its original equation')

    migration, migration_inputs, mobility = None, None, None
    if imperfect_mobility:
        required_migration = {'zeta', 'baseline_urban_share', 'source'}
        previous_migration = saved.get('migration') if saved_model == model else None
        migration_inputs = spec.get('migration', previous_migration)
        if not isinstance(migration_inputs, dict) or set(migration_inputs) != required_migration:
            raise ValueError('migration requires zeta, baseline_urban_share and source')
        if previous_migration is not None and migration_inputs != previous_migration:
            raise ValueError('saved imperfect-mobility results retain their migration calibration')
        zeta, urban_share = (float(migration_inputs[key]) for key in ('zeta', 'baseline_urban_share'))
        if not np.isfinite(zeta) or zeta <= 0 or not np.isfinite(urban_share) or not 0 < urban_share < 1:
            raise ValueError('migration requires finite zeta>0 and baseline_urban_share in (0,1)')
        if not isinstance(migration_inputs['source'], str) or not migration_inputs['source'].strip():
            raise ValueError('migration.source must identify the shape calibration and baseline urbanization observation')
        migration_inputs = {**migration_inputs, 'zeta': zeta, 'baseline_urban_share': urban_share}
        migration = {'zeta': zeta, 'baseline_urban_share': urban_share,
            'baseline_log_odds': float(np.log(urban_share)-np.log1p(-urban_share)),
            'log_total_population': float(log_n-np.log(urban_share)),
            'baseline_log_utility': float(np.log(baseline['aggregate']['expected_utility']))}
        mobility = {'regional_population': float(np.exp(migration['log_total_population'])),
                    'outside_log_utility': migration['baseline_log_utility']-migration['baseline_log_odds']/zeta,
                    'scenarios': {}}
        if not np.isfinite(mobility['regional_population']) or not np.isfinite(mobility['outside_log_utility']):
            raise ValueError('migration calibration requires finite regional population and hinterland log opportunity value')
        if previous_migration is None:
            executed.append('calibrate_migration')
        else:
            reused['objects'].append('migration')
            executed.append('load_migration')

    scenarios = {'baseline': baseline}
    scenario_primitives = None
    if operation == 'counterfactual':
        change = spec['scenario']
        if set(change)-{'name', 'productivity_hat', 'amenity_hat', 'floor_space_hat', 'travel_time'}:
            raise ValueError('scenario accepts name, productivity_hat, amenity_hat, floor_space_hat and travel_time')
        scenario_primitives = {**primitives}
        for name in ('productivity', 'amenity', 'floor_space'):
            multiplier = positive_vector(change.get(name+'_hat', 1.), 'scenario.'+name+'_hat', scalar=True)
            scenario_primitives[name] = (np.asarray(primitives[name])*multiplier).tolist()
        times = time_matrix(change.get('travel_time', travel))
        reservation_utility = baseline['aggregate']['expected_utility'] if open_city else None
        scenarios['scenario'] = equilibrium(scenario_primitives, times, np.asarray(baseline['state_log']), reservation_utility, migration)
        executed.append('solve_counterfactual')

    if migration is not None:
        for name, result in scenarios.items():
            log_ratio = np.log(result['aggregate']['expected_utility'])-migration['baseline_log_utility']
            scaled_log_ratio = zeta*log_ratio
            if scaled_log_ratio <= 1:
                log_value_ratio = float(np.log1p(urban_share*np.expm1(scaled_log_ratio))/zeta)
            else:
                log_value_ratio = float(np.logaddexp(np.log1p(-urban_share), np.log(urban_share)+scaled_log_ratio)/zeta)
            city_mass = result['aggregate']['population']
            mobility['scenarios'][name] = {
                'urban_share': city_mass/mobility['regional_population'],
                'hinterland_population': mobility['regional_population']-city_mass,
                'regional_welfare_index_ratio': float(np.exp(log_value_ratio)),
                'regional_expected_log_utility_change': log_value_ratio}
        if any(not all(np.isfinite(value) for value in row.values()) or not 0 < row['urban_share'] < 1
               for row in mobility['scenarios'].values()):
            raise ArithmeticError('QSE migration requires finite regional outcomes and positive city and hinterland populations')

    if open_city:
        equations.update(migration=migration_equation, welfare=open_welfare_equation)
    elif imperfect_mobility:
        equations.update(imperfect_equations)
    normalization = ('Tradable-good price=1; baseline employment-weighted mean wage=1; observed rent divided by '
                     'baseline.wage_numeraire in the same currency and period; baseline population-weighted mean total amenity=1. '
                     'Counterfactual wages, rents and amenities retain the baseline units.')
    welfare_definition = ('N homogeneous workers draw iid Frechet(epsilon) residence-workplace tastes. U averages optimized utility before draws. '
        'Worker EV uniformly scales all baseline potential workplace wages by U_s/U_b at fixed baseline rents; its expected transfer is chi times '
        'the baseline wage bill, with baseline commuting probabilities as weights. Floor owners are outside the worker population, own all commercial '
        'and residential floors and consume their qF receipts in the numeraire good. Their linear-utility EV is the income change. '
        'The money-metric total gives unit weight to these two income equivalents. Competitive profits are zero. '
        'Travel is a utility cost; supplied floor changes are endowment changes with zero construction resource cost.')
    if open_city:
        welfare_definition = ('Workers move freely between the city and an outside option whose expected utility equals the saved baseline U_b. '
            'The scenario solves U_s=U_b with endogenous city population N_s. The original baseline workers retain this common expected utility. '
            'Their wage-proportional income equivalent scales all baseline potential workplace wages by U_s/U_b at fixed baseline rents; '
            'the transfer is (U_s/U_b-1) times the original baseline wage bill, for the original baseline worker population. '
            'Population change measures migration in workers; the utility ratio compares expected utility per worker before taste draws. '
            'Floor owners are outside the worker population, own all commercial and residential floors, and consume qF receipts in the numeraire good. '
            'Their linear-utility equivalent is the change in those receipts. Competitive profits are zero. '
            'Travel is a utility cost; supplied floor changes are endowment changes with zero construction resource cost.')
    elif imperfect_mobility:
        welfare_definition = ('A fixed regional population chooses city or hinterland before city residence-workplace tastes. '
            'The two location values are log(U) and log(U_tilde)/zeta with iid extreme-value shocks of scale 1/zeta. '
            'The expected optimized log value, with the common shock constant normalized to zero, is log(V). '
            'Regional welfare reports log(V_s/V_b) and V_s/V_b for that same regional population. '
            'City opportunity EV scales baseline city workplace wages by U_s/U_b at baseline rents, evaluated for the original '
            'baseline city population conditional on city residence. External floor-owner EV is the change in qF receipts. '
            'Regional log value, the conditional city income equivalent and owner income keep their respective units and populations. '
            'The hinterland opportunity value and regional population are fixed. Firms have zero profits, travel is a utility cost, '
            'and endowed floor changes have zero construction resource cost.')
    common = {'model_contract': contracts[model],
        'knowledge_ids': ['SPATIAL-02'], 'equations': equations,
        'normalization': normalization, 'welfare_definition': welfare_definition,
        'equilibrium_selection': ('Free migration at saved baseline expected utility; endogenous positive population; all locations mixed use; '
            'trust-region root starting at the recovered baseline.' if open_city else
            'Closed population; all locations mixed use; trust-region root starting at the recovered baseline.'),
        'population': (f'{population:g} baseline workers; endogenous city population; separate floor owners' if open_city else
            f'{population:g} workers and separate floor owners'), 'horizon': 'one common model period',
        'parameter_definition': {key: {'value': value, 'status': 'calibrated', 'source': calibration_source,
            'unit': 'inverse travel-time unit' if key in ('kappa', 'productivity_decay', 'amenity_decay') else 'dimensionless'}
            for key, value in p.items()}}
    if imperfect_mobility:
        common['equilibrium_selection'] = ('Fixed regional population and hinterland value; city population follows the calibrated '
            'utility log-odds equation; all locations mixed use; trust-region root starting at the recovered baseline.')
        common['population'] = f"{mobility['regional_population']:g} regional workers; {population:g} baseline city workers; separate floor owners"
        common['parameter_definition'].update({
            'migration.'+key: {'value': migration_inputs[key], 'status': 'calibrated',
                               'source': migration_inputs['source'], 'unit': 'dimensionless'}
            for key in ('zeta', 'baseline_urban_share')})
    flow_unit = 'baseline mean wages per period'
    local_units = {'wage': 'baseline mean wages per worker per period', 'rent': 'baseline mean wages per floor unit per period',
        'employment': 'workers', 'population': 'workers', 'commercial_share': 'fraction', 'commercial_floor': 'floor units',
        'residential_floor': 'floor units', 'floor_space': 'floor units', 'output': flow_unit, 'resident_income': flow_unit,
        'worker_consumption': flow_unit, 'owner_income': flow_unit, 'firm_profit': flow_unit, 'net_exports': flow_unit,
        'productivity': 'goods per labor^alpha floor^(1-alpha)', 'amenity': 'baseline amenity units',
        'residence_fixed_expected_utility': 'expected utility per worker at fixed residence'}
    aggregate_units = {key: flow_unit for key in baseline['aggregate']}
    aggregate_units.update(population='workers', employment='workers', expected_utility='expected utility per worker',
                           mean_commute_time='input travel-time units')
    statistics, local_rows, aggregate_rows, commute_rows, diagnostic_rows = {}, [], [], [], []
    for name, result in scenarios.items():
        for key, values in result['local'].items():
            for location, value in zip(ids, values):
                statistic = {'value': float(value), 'unit': local_units[key]}
                statistics[f'{name}.local.{location}.{key}'] = statistic
                local_rows.append({'scenario': name, 'location_id': location, 'quantity': key, **statistic})
        for key, value in result['aggregate'].items():
            statistic = {'value': float(value), 'unit': aggregate_units[key]}
            statistics[f'{name}.{key}'] = statistic
            aggregate_rows.append({'scenario': name, 'quantity': key, **statistic})
        for i, origin in enumerate(ids):
            for j, destination in enumerate(ids):
                commute_rows.append({'scenario': name, 'residence': origin, 'workplace': destination,
                    'probability': result['commuting_probability'][i][j], 'workers': result['commuting_flows'][i][j],
                    'travel_time': result['travel_time'][i][j]})
        for key, value in result['diagnostics'].items():
            statistic = {'value': value, 'unit': 'dimensionless residual'}
            statistics[f'{name}.{key}'] = statistic
            diagnostic_rows.append({'scenario': name, 'quantity': key, **statistic})
        if mobility is not None:
            mobility_units = {'urban_share': 'fraction of regional population', 'hinterland_population': 'workers',
                'regional_welfare_index_ratio': 'ratio of baseline regional welfare index',
                'regional_expected_log_utility_change': 'expected log utility per regional worker'}
            for key, value in mobility['scenarios'][name].items():
                statistic = {'value': value, 'unit': mobility_units[key]}
                statistics[f'{name}.{key}'] = statistic
                aggregate_rows.append({'scenario': name, 'quantity': key, **statistic})
    welfare = {}
    if operation == 'counterfactual':
        before, after = baseline['aggregate'], scenarios['scenario']['aggregate']
        fraction = after['expected_utility']/before['expected_utility']-1
        workers = fraction*before['wage_bill']
        owners = after['owner_income']-before['owner_income']
        welfare = {'worker_income_equivalent_fraction': {'value': fraction, 'unit': 'fraction of baseline potential wages'},
            'worker_income_equivalent': {'value': workers, 'unit': flow_unit},
            'owner_income_change': {'value': owners, 'unit': flow_unit},
            'firm_profit_change': {'value': after['firm_profit']-before['firm_profit'], 'unit': flow_unit}}
        if open_city or imperfect_mobility:
            welfare.update({
                'population_change': {'value': after['population']-before['population'], 'unit': 'workers'},
                'population_change_fraction': {
                    'value': after['population']/before['population']-1, 'unit': 'fraction of baseline city population'}})
            if open_city:
                welfare.update({
                    'worker_expected_utility_ratio': {'value': after['expected_utility']/before['expected_utility'],
                                                      'unit': 'ratio of baseline expected utility'},
                    'reservation_utility': {'value': before['expected_utility'], 'unit': 'expected utility per worker'}})
            else:
                for key in ('worker_income_equivalent_fraction', 'worker_income_equivalent'):
                    welfare['city_'+key] = welfare.pop(key)
                welfare['city_worker_expected_utility_ratio'] = {
                    'value': after['expected_utility']/before['expected_utility'], 'unit': 'ratio of baseline city expected utility'}
                for key in ('regional_welfare_index_ratio', 'regional_expected_log_utility_change'):
                    welfare[key] = dict(statistics['scenario.'+key])
        else:
            welfare['baseline_price_worker_and_external_owner_equivalent'] = {'value': workers+owners, 'unit': flow_unit}
        for key, value in list(statistics.items()):
            if key.startswith('scenario.'):
                suffix = key[len('scenario.'):]
                if 'baseline.'+suffix in statistics:
                    statistics['change.'+suffix] = {'value': value['value']-statistics['baseline.'+suffix]['value'], 'unit': value['unit']}
        statistics.update(welfare)
    displays = {}
    for name, rows in (('local_equilibrium', local_rows), ('aggregate_equilibrium', aggregate_rows),
                       ('commuting', commute_rows), ('diagnostics', diagnostic_rows),
                       ('welfare', [{'quantity': key, **value} for key, value in welfare.items()])):
        if rows:
            displays[name] = {'kind': 'table', 'title': name.replace('_', ' ').title(), 'rows': rows,
                'columns': [{'key': key, 'label': key.replace('_', ' ').title(), 'unit': ''} for key in rows[0]],
                'metadata': {**common, 'report_role': 'model_fit' if name == 'diagnostics' else 'counterfactual'},
                'display': {'plot_type': 'table'}}
    return {'result_format_version': 1, 'qse_numerical_contract_version': 1, 'model': model, 'closure': closure, **common,
        'engine': 'log-coordinate OD balancing; scipy.optimize.least_squares(trf)',
        'adopted': spec, 'baseline_inputs': baseline_input, 'options': options,
        'calibration': {'source': calibration_source, 'parameters': p, 'estimated_parameters': [],
                        'inverted_primitives': ['productivity', 'amenity', 'floor_space']},
        'primitives': primitives, 'scenario_primitives': scenario_primitives, 'inversion': inversion,
        **({'migration': migration_inputs, 'mobility': mobility} if imperfect_mobility else {}),
        **scenarios, 'welfare': welfare, 'statistics': statistics, 'displays': displays,
        'computation': {'requested_operation': operation, 'operations_executed': executed,
                        'reused_solution': reused, 'parameter_operation': (
                            'fixed calibrated elasticities and urban share; recover regional population and hinterland value; reuse baseline fundamentals'
                            if imperfect_mobility else 'fixed calibrated elasticities; invert latent fundamentals only in invert_baseline')},
        'provenance': {'python': sys.version.split()[0], 'numpy': np.__version__, 'scipy': scipy.__version__,
            'reference_implementation': 'https://github.com/Ahlfeldt/QSETRANSPORT-toolkit/tree/c3e212843bff81a9d69df75bb7e6aac022bea8c8/QUETRANSPORT-PythonOnly/src/python/functions',
            **({'migration_reference_implementation': 'https://github.com/Ahlfeldt/ABSJ2027-toolkit/blob/b5c8d32ccab117cb7b85f581cf29569c1eea893a/Python/functions/solver.py'}
               if imperfect_mobility else {})}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['run'])
    parser.add_argument('spec',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        if args.spec.resolve() == args.output.resolve():
            raise ValueError('output must differ from the specification path')
        raw = args.spec.read_bytes()
        specification = json.loads(raw)
        if not isinstance(specification, dict):
            raise TypeError('specification must be an object')
        base = args.spec.resolve().parent
        protected = {args.spec.resolve()}
        for key, field in (('observations', 'path'), ('saved_solution', 'path'), ('model_definition', 'module')):
            reference = specification.get(key)
            if isinstance(reference, dict) and isinstance(reference.get(field), str):
                protected.add((base / reference[field]).resolve())
        scenario = specification.get('scenario', {})
        for key, field in (('saved_solution', 'path'), ('model_definition', 'module')):
            reference = scenario.get(key) if isinstance(scenario, dict) else None
            if isinstance(reference, dict) and isinstance(reference.get(field), str):
                protected.add((base / reference[field]).resolve())
        outputs = [args.output.resolve()]
        for owner in (specification, scenario):
            if isinstance(owner, dict) and isinstance(owner.get('solution_path'), str):
                outputs.append((base / owner['solution_path']).resolve())
        if len(set(outputs)) != len(outputs) or set(outputs) & protected:
            raise ValueError('outputs must be distinct and differ from specification, observation and saved model inputs')
        result = solve(specification,args.spec.resolve().parent)
        result['provenance']['spec_sha256'] = hashlib.sha256(raw).hexdigest()
        result['provenance']['producer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        atomic_write(args.output,result)
    except (ValueError,KeyError,TypeError,OSError,ArithmeticError) as exc:
        parser.exit(2,f'error: {exc}\n')


if __name__ == '__main__': main()
