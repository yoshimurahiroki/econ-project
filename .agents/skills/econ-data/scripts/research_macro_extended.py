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
            'terminal': 'retirement is absorbing; the final alive period consumes all wealth; V_dead=0'}
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
                    values = frame[binding['column']].copy()
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
                terminal_saving = saving[alive['period'].to_numpy() == horizon-2]
                outcome['diagnostics'] = {'max_wealth_transition_residual': residual,
                    'minimum_savings': float(saving.min()), 'max_final_alive_savings': float(np.max(np.abs(terminal_saving)))}
                if residual > 1e-9 or saving.min() < -1e-9 or np.max(np.abs(terminal_saving)) > 1e-9:
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
    if model == 'lifecycle_choice':
        return lifecycle_run(spec, base_dir)
    if model == 'consumption_saving':
        return solve_hark(spec)
    if model == 'aiyagari':
        return solve_aiyagari(spec)
    if model != 'olg':
        raise ValueError('model must be olg, aiyagari, consumption_saving or lifecycle_choice')
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
        'sequence_space_jacobian': {'engine':'sequence_jacobian.simple.solve_jacobian', 'output_to_log_productivity':official_jacobian.tolist(), 'analytic_max_abs_error':official_error, 'difference_step':step, 'finite_difference_max_abs_error':sequence_error},
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
        result = solve(json.loads(raw),args.spec.resolve().parent)
        result['provenance']['spec_sha256'] = hashlib.sha256(raw).hexdigest()
        result['provenance']['producer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        atomic_write(args.output,result)
    except (ValueError,KeyError,TypeError,OSError,ArithmeticError) as exc:
        parser.exit(2,f'error: {exc}\n')


if __name__ == '__main__': main()
