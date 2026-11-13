#!/usr/bin/env python3
"""Solve and estimate specified finite-state dynamic choices and games.

Use ``run SPEC --output RESULT`` with the adopted inputs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import scipy
from scipy.optimize import minimize, minimize_scalar, root
from scipy.special import expit, logsumexp, softmax
from scipy.linalg import expm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_data
from research_numerics import finite_jacobian


def official_package(name, version, revision):
    """Bind the producing installed distribution to its adopted source revision."""
    import importlib.metadata
    import subprocess
    from urllib.parse import unquote, urlparse
    distribution = importlib.metadata.distribution(name)
    direct = distribution.read_text('direct_url.json')
    source = json.loads(direct) if direct else {}
    actual = source.get('vcs_info', {}).get('commit_id')
    if source.get('url', '').startswith('file:'):
        directory = Path(unquote(urlparse(source['url']).path))
        check = subprocess.run(['git', '-C', str(directory), 'rev-parse', 'HEAD'],
                               capture_output=True, text=True)
        actual = check.stdout.strip() if check.returncode == 0 else None
    if distribution.version != version or actual != revision:
        raise ValueError(f'{name} {version} at official revision {revision} is required')
    return {'package': name, 'version': distribution.version, 'source_revision': actual,
            'direct_url': source}


def native_json(value):
    """Retain native coordinates and missing observations in the common JSON result."""
    import pandas as pd
    if isinstance(value, pd.DataFrame):
        return {'kind': 'dataframe', 'index_names': list(value.index.names),
                'index': native_json(value.index.tolist()), 'columns': native_json(value.columns.tolist()),
                'data': native_json(value.to_numpy().tolist())}
    if isinstance(value, pd.Series):
        return {'kind': 'series', 'index_names': list(value.index.names),
                'index': native_json(value.index.tolist()), 'name': native_json(value.name),
                'data': native_json(value.tolist())}
    if isinstance(value, dict):
        return {str(k): native_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [native_json(v) for v in value]
    if isinstance(value, np.generic):
        return native_json(value.item())
    if isinstance(value, Path):
        return str(value)
    if value is None or value is pd.NA or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, float) and not np.isfinite(value):
        raise ArithmeticError('native result contains an infinite value')
    return value


def restore_frame(value):
    import pandas as pd
    names = value['index_names']
    index = (pd.MultiIndex.from_tuples([tuple(x) for x in value['index']], names=names)
             if len(names) > 1 else pd.Index(value['index'], name=names[0]))
    return pd.DataFrame(value['data'], index=index, columns=value['columns'])


def source_file(value, base):
    path = Path(value)
    path = path if path.is_absolute() else base / path
    path = path.resolve()
    with path.open('rb') as stream:
        sha256 = hashlib.file_digest(stream, 'sha256').hexdigest()
    return path, {'path': str(path), 'sha256': sha256}


def respy_data(data_spec, base):
    import pandas as pd
    path, source = source_file(data_spec['path'], base)
    frame = research_data.read_frame(path)
    # The pinned respy label encoder replaces strings with integer codes.
    # Materialize extension strings at that native boundary without changing labels.
    for column in frame.select_dtypes(include='string').columns:
        frame[column] = frame[column].astype(object)
    if data_spec.get('columns'):
        frame = frame.rename(columns={v: k for k, v in data_spec['columns'].items()})
    frame = frame.set_index(['Identifier', 'Period']).sort_index()
    if frame.empty or not frame.index.is_unique:
        raise ValueError('respy observations require unique Identifier/Period keys')
    keys = frame.index.to_frame(index=False).to_numpy(dtype=float)
    if not np.isfinite(keys).all() or not np.equal(keys, np.floor(keys)).all() or (keys < 0).any():
        raise ValueError('Identifier and Period must be nonnegative integers')
    source.update(rows=len(frame), columns=list(frame.columns), index_names=list(frame.index.names))
    return frame, source


def respy_callbacks(config, base, observed):
    """Load the adopted moment definitions; preserve their native nesting and labels."""
    path, source = source_file(config['module'], base)
    module_spec = importlib.util.spec_from_file_location('adopted_respy_moments', path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    def resolve(value):
        if value is None:
            return None
        if isinstance(value, list):
            return [resolve(x) for x in value]
        if isinstance(value, dict):
            return {k: resolve(v) for k, v in value.items()}
        function = getattr(module, value)
        if not callable(function):
            raise TypeError('moment definitions must be callable')
        return function
    def apply(functions):
        if isinstance(functions, list):
            return [apply(x) for x in functions]
        if isinstance(functions, dict):
            return {k: apply(v) for k, v in functions.items()}
        return functions(observed.copy())
    calculate = resolve(config['calc_moments'])
    return calculate, resolve(config.get('replace_nans')), apply(calculate), source


def respy_welfare(frame, config, method, horizon):
    """Aggregate chosen native flow utilities for the adopted initial population."""
    if method == 'one_step_ahead':
        raise ValueError('lifecycle welfare requires n-step simulation')
    discounting = config['discounting']
    if discounting not in ('exponential', 'quasi_hyperbolic_initial_self'):
        raise ValueError('welfare.discounting must name exponential or quasi_hyperbolic_initial_self')
    rows = []
    for identifier, panel in frame.groupby(level='Identifier', sort=True):
        periods = panel.index.get_level_values('Period').to_numpy()
        if not np.array_equal(periods, np.arange(horizon)):
            raise ValueError('welfare requires the complete simulated decision horizon')
        delta = panel['Discount_Rate'].to_numpy(dtype=float)
        present_bias = panel['Present_Bias'].to_numpy(dtype=float)
        if not np.equal(delta, delta[0]).all() or not np.equal(present_bias, present_bias[0]).all():
            raise ValueError('welfare requires the declared constant individual discount parameters')
        if discounting == 'exponential' and present_bias[0] != 1:
            raise ValueError('present-biased choices require an explicit welfare discounting definition')
        columns = {c[len('Flow_Utility_'):].lower(): c for c in panel.columns if c.startswith('Flow_Utility_')}
        flows = np.array([row[columns[str(row['Choice']).lower()]] for _, row in panel.iterrows()], dtype=float)
        factors = delta[0] ** periods
        if discounting == 'quasi_hyperbolic_initial_self':
            factors[periods > 0] *= present_bias[0]
        rows.append({'identifier': int(identifier), 'discounted_utility': float(factors @ flows)})
    weights = config['population_weights']
    if weights == 'equal':
        weights = np.ones(len(rows)) / len(rows)
    elif isinstance(weights, dict):
        if set(weights) != {str(r['identifier']) for r in rows}:
            raise ValueError('welfare weights must match every simulated identifier')
        weights = np.array([weights[str(r['identifier'])] for r in rows], dtype=float)
    else:
        weights = np.asarray(weights, dtype=float)
    if weights.shape != (len(rows),) or not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError('invalid welfare population weights')
    weights = weights / weights.sum()
    for row, weight in zip(rows, weights):
        row['population_weight'] = float(weight)
    if config.get('terminal_value', 0) != 0:
        raise ValueError('respy finite-horizon welfare uses its zero terminal continuation value')
    return {'value': float(weights @ [r['discounted_utility'] for r in rows]),
            'unit': config.get('unit', 'utility'), 'individuals': rows,
            'definition': 'Population-weighted sum of chosen Flow_Utility over the full decision horizon',
            'discounting': discounting, 'terminal_value': 0, 'horizon': horizon}


def respy_run(spec, base):
    """Estimate and reuse the adopted finite-horizon model through official respy."""
    import pandas as pd
    import respy
    from respy.config import DEFAULT_OPTIONS
    from respy.pre_processing.model_processing import process_params_and_options
    from respy.shared import create_state_space_columns, rename_labels_from_internal
    identity = official_package('respy', '2.1.1', '91e8a193fb7d5cf7212c15e50ae43f810bb9b1eb')
    operation = spec['operation']
    if operation not in ('estimate', 'simulate', 'counterfactual'):
        raise ValueError('respy operation must be estimate, simulate or counterfactual')
    sources = {}
    if 'fit_path' in spec:
        if operation == 'estimate':
            raise ValueError('fit_path reuses a fit; a new estimate requires explicit params and options')
        path, sources['fit'] = source_file(spec['fit_path'], base)
        saved = json.loads(path.read_text())
        if saved.get('model') != 'finite_horizon_choice':
            raise ValueError('fit_path must identify a finite_horizon_choice result')
        fit = copy.deepcopy(saved['fit'])
        params = restore_frame(fit['params'])
        options = copy.deepcopy(fit['options'])
        adopted = copy.deepcopy(fit['adopted'])
        for key, expected in (('options', options), ('adopted', adopted)):
            if key in spec and spec[key] != expected:
                raise ValueError(f'{key} must preserve the saved fit')
        if 'params' in spec:
            raise ValueError('fit_path already supplies the saved parameters')
        observed = restore_frame(fit['observed_data']) if fit.get('observed_data') else None
        sources = {**fit.get('sources', {}), **sources}
    else:
        parameter_input = spec['params']
        if isinstance(parameter_input, dict) and 'path' in parameter_input:
            path, sources['params'] = source_file(parameter_input['path'], base)
            params = research_data.read_frame(path).set_index(['category', 'name'])
        else:
            params = pd.DataFrame(parameter_input).set_index(['category', 'name'])
        options = {**copy.deepcopy(DEFAULT_OPTIONS), **copy.deepcopy(spec['options'])}
        adopted = copy.deepcopy(spec['adopted'])
        observed = None
        fit = {'parameter_status': spec.get('parameter_status', 'fixed'), 'adopted': adopted}
    if not params.index.is_unique or 'value' not in params or not np.isfinite(params['value'].to_numpy(dtype=float)).all():
        raise ValueError('respy parameters require unique category/name and finite values')
    if 'data' in spec:
        observed, sources['data'] = respy_data(spec['data'], base)
    if operation == 'estimate' and observed is None:
        raise ValueError('respy estimation requires adopted observed data')
    if operation == 'estimate' and spec.get('inference', {}).get('method', 'retain_inputs') != 'retain_inputs':
        raise ValueError('this operation retains inference inputs; select the adopted covariance through its inference owner')
    horizon = int(options['n_periods'])
    if horizon < 1:
        raise ValueError('n_periods must be positive')
    # Each invocation owns its native disk cache. It is an execution location, not a primitive.
    with tempfile.TemporaryDirectory(prefix='ers-respy-') as cache:
        native_options = copy.deepcopy(options)
        native_options['cache_path'] = cache
        statistics, parameter_rows, diagnostics = {}, [], []
        free = [tuple(x) for x in fit.get('free_parameters', [])]
        if operation == 'estimate':
            estimation = spec['estimation']
            method = estimation['method']
            free = [tuple(x) for x in estimation['free_parameters']]
            if not free or len(free) != len(set(free)) or any(x not in params.index for x in free):
                raise ValueError('free_parameters must identify distinct adopted parameter coordinates')
            bounds = estimation['bounds']
            if len(bounds) != len(free) or any(len(x) != 2 for x in bounds):
                raise ValueError('bounds must match free_parameters')
            initial = params.loc[free, 'value'].to_numpy(dtype=float)
            for x, (lo, hi) in zip(initial, bounds):
                if (lo is not None and x < lo) or (hi is not None and x > hi) or (lo is not None and hi is not None and lo >= hi):
                    raise ValueError('initial parameters must lie in adopted bounds')
            optimizer = estimation['optimizer']
            if optimizer['method'] not in ('L-BFGS-B', 'Powell', 'Nelder-Mead', 'SLSQP'):
                raise ValueError('select a supported bounded scipy optimizer')
            def parameter_frame(values):
                candidate = params.copy(deep=True)
                candidate.loc[free, 'value'] = values
                return candidate
            sign = -1. if method == 'maximum_likelihood' else 1.
            if method == 'maximum_likelihood':
                criterion = respy.get_log_like_func(params, native_options, observed, return_scalar=False)
                criterion_definition = 'Mean individual log likelihood; the optimizer minimizes its negative'
                empirical = weighting = None
            elif method == 'smm':
                moments = spec['moments']
                calculate, replace, empirical, sources['moments'] = respy_callbacks(moments, base, observed)
                flat = respy.get_flat_moments(empirical)
                weighting = np.asarray(moments['weighting_matrix'], dtype=float)
                if (weighting.shape != (len(flat), len(flat)) or not np.isfinite(weighting).all()
                        or not np.allclose(weighting, weighting.T, rtol=0, atol=1e-12)
                        or np.linalg.eigvalsh(weighting).min() < -1e-12):
                    raise ValueError('SMM weighting matrix must be symmetric positive semidefinite in moment order')
                if not flat.index.is_unique or not np.isfinite(flat.to_numpy()).all():
                    raise ValueError('empirical moments must have unique labels and finite values')
                criterion = respy.get_moment_errors_func(params, native_options, calculate, replace,
                    empirical, weighting_matrix=weighting,
                    n_simulation_periods=moments.get('n_simulation_periods'), return_scalar=False)
                criterion_definition = 'e.T @ W @ e, with e = empirical moments - simulated moments'
            else:
                raise ValueError('estimation.method must be maximum_likelihood or smm')
            def evaluate(values):
                # The native root output takes an elementwise square root of W. Only value
                # defines the general-W objective; roots are retained solely for diagonal W.
                with np.errstate(invalid='ignore'):
                    result = criterion(parameter_frame(values))
                if not np.isfinite(result['value']):
                    raise ArithmeticError('official respy criterion is nonfinite')
                return result
            optimization = minimize(lambda x: sign * float(evaluate(x)['value']), initial,
                bounds=bounds, method=optimizer['method'], options=optimizer.get('options', {}),
                tol=optimizer.get('tolerance'))
            if not optimization.success:
                raise ArithmeticError('respy optimization: ' + str(optimization.message))
            final = evaluate(optimization.x)
            params.loc[free, 'value'] = optimization.x
            raw_criterion = {k: v for k, v in final.items() if k != 'root_contributions'}
            if method == 'smm' and np.array_equal(weighting, np.diag(np.diag(weighting))):
                raw_criterion['root_contributions'] = final['root_contributions']
            inferential = {'independent_unit': spec.get('inference', {}).get('independent_unit', 'Identifier'),
                'procedure': copy.deepcopy(spec.get('inference', {'method': 'retain_inputs'})),
                'sample_ids': observed.index.get_level_values('Identifier').unique().tolist(),
                'sample_keys': observed.index.tolist(), 'free_parameter_order': free,
                'draw_settings': {k: options[k] for k in options if 'seed' in k or 'draws' in k}}
            if method == 'maximum_likelihood':
                inferential['individual_log_likelihood_contributions'] = final['contributions']
                statistics['respy_mean_log_likelihood'] = {'value': float(final['value']), 'unit': 'mean log likelihood'}
            else:
                errors = final['moment_errors']
                if list(errors.index) != list(flat.index) or not np.isfinite(errors.to_numpy()).all():
                    raise ArithmeticError('official moment order or finiteness differs from adopted moments')
                difference = abs(float(errors.to_numpy() @ weighting @ errors.to_numpy()) - float(final['value']))
                if difference > max(1e-10, abs(float(final['value'])) * 1e-12):
                    raise ArithmeticError('official SMM value differs from the adopted weighted criterion')
                inferential.update(moment_order=flat.index.tolist(), weighting_matrix=weighting,
                                   empirical_moments=empirical, moment_errors=errors)
                statistics['respy_smm_criterion'] = {'value': float(final['value']), 'unit': 'weighted squared moment error'}
            derivative_step = spec.get('inference', {}).get('derivative_step')
            if derivative_step is not None:
                step = np.broadcast_to(np.asarray(derivative_step, dtype=float), optimization.x.shape)
                if not np.isfinite(step).all() or (step <= 0).any():
                    raise ValueError('inference derivative steps must be positive')
                columns = []
                target = 'contributions' if method == 'maximum_likelihood' else 'moment_errors'
                for j, h in enumerate(step):
                    plus, minus = optimization.x.copy(), optimization.x.copy()
                    plus[j] += h; minus[j] -= h
                    lo, hi = bounds[j]
                    if (lo is not None and minus[j] < lo) or (hi is not None and plus[j] > hi):
                        raise ValueError('central inference differences must remain inside the adopted bounds')
                    columns.append((np.asarray(evaluate(plus)[target]) - np.asarray(evaluate(minus)[target])) / (2*h))
                inferential['derivative_step'] = step
                inferential['individual_score' if method == 'maximum_likelihood' else 'moment_error_jacobian'] = np.column_stack(columns)
            simulation_error = {'component': 'simulated_likelihood' if method == 'maximum_likelihood' else 'simulated_moments',
                'criterion_seed': options['estimation_seed'] if method == 'maximum_likelihood' else options['simulation_seed'],
                'solution_seed': options['solution_seed'], 'independent_replications': 1}
            if method == 'smm' and spec['moments'].get('simulation_seeds'):
                seeds = spec['moments']['simulation_seeds']
                if len(set(seeds)) != len(seeds) or len(seeds) < 2:
                    raise ValueError('simulation_seeds requires at least two distinct seeds')
                replicas = []
                for seed in seeds:
                    repeated_options = {**native_options, 'simulation_seed': int(seed)}
                    repeated = respy.get_moment_errors_func(params, repeated_options, calculate, replace,
                        empirical, weighting_matrix=weighting, n_simulation_periods=spec['moments'].get('n_simulation_periods'),
                        return_scalar=False)
                    with np.errstate(invalid='ignore'):
                        value = repeated(params)
                    replicas.append(respy.get_flat_moments(value['simulated_moments']).reindex(flat.index).to_numpy())
                replica_values = np.asarray(replicas)
                if not np.isfinite(replica_values).all():
                    raise ArithmeticError('simulation replication contains nonfinite moments')
                simulation_error.update(seeds=seeds, independent_replications=len(seeds),
                    moment_order=flat.index.tolist(), replicated_simulated_moments=replica_values,
                    standard_deviation=replica_values.std(axis=0, ddof=1),
                    mean_standard_error=replica_values.std(axis=0, ddof=1)/np.sqrt(len(seeds)))
            fit.update(parameter_status='estimated', estimation_method=method, free_parameters=free,
                bounds=bounds, criterion_definition=criterion_definition, criterion=raw_criterion,
                optimization={'method': optimizer['method'], 'options': optimizer.get('options', {}),
                    'tolerance': optimizer.get('tolerance'), 'initial_parameters': initial,
                    'parameters': optimization.x, 'objective': float(optimization.fun),
                    'success': bool(optimization.success), 'status': int(optimization.status),
                    'message': str(optimization.message), 'iterations': int(optimization.nit),
                    'evaluations': int(optimization.nfev)},
                inferential_information=inferential, simulation_error=simulation_error)
        fit.update(params=native_json(params), options=options, adopted=adopted,
                   observed_data=native_json(observed) if observed is not None else None, sources=sources,
                   official_source=identity)
        simulations, policy_rows = {}, []
        invariants = {}
        simulation_config = spec.get('simulation')
        if operation in ('simulate', 'counterfactual') and simulation_config is None:
            raise ValueError('simulation.method is required')
        if simulation_config is not None:
            method = simulation_config['method']
            if method not in ('n_step_ahead_with_sampling', 'n_step_ahead_with_data', 'one_step_ahead'):
                raise ValueError('unsupported native simulation method')
            if method != 'n_step_ahead_with_sampling' and observed is None:
                raise ValueError('the selected simulation method requires data')
            requested_periods = simulation_config.get('n_simulation_periods')
            if requested_periods is not None and requested_periods != horizon:
                raise ValueError('the pinned respy simulator uses n_periods; retain that horizon and select display periods afterward')
            native_parameters, _ = process_params_and_options(params, native_options)
            state_columns = [rename_labels_from_internal(x) for x in create_state_space_columns(native_parameters)]
            if method == 'n_step_ahead_with_data':
                initial = observed.loc[observed.index.get_level_values('Period') == 0]
                ids = initial.index.get_level_values('Identifier').to_numpy()
                if not np.array_equal(ids, np.arange(len(initial))) or len(initial) != observed.index.get_level_values('Identifier').nunique():
                    raise ValueError('n-step data simulation requires consecutive zero-based IDs at Period 0')
                required = [c for c in state_columns if c not in ('Identifier', 'Period', 'Type')]
                if any(c not in initial for c in required) or initial[required].isna().any().any():
                    raise ValueError('n-step data simulation requires all adopted initial observed states')
            scenarios = [('baseline', params)]
            if operation == 'counterfactual':
                changed = params.copy(deep=True)
                changes = spec['scenario']['parameter_changes']
                if not changes:
                    raise ValueError('counterfactual requires adopted utility parameter changes')
                for change in changes:
                    coordinate = (change['category'], change['name'])
                    if coordinate not in params.index or not coordinate[0].startswith(('wage_', 'nonpec_')):
                        raise ValueError('counterfactual parameter changes must name wage/nonpec utility parameters')
                    if not np.isfinite(change['value']):
                        raise ValueError('counterfactual parameter values must be finite')
                    changed.loc[coordinate, 'value'] = change['value']
                scenarios.append(('scenario', changed))
            for scenario_name, scenario_params in scenarios:
                simulator = respy.get_simulate_func(scenario_params, native_options, method=method,
                    df=observed, n_simulation_periods=requested_periods)
                frame = simulator(scenario_params)
                statistics['respy_'+scenario_name+'_simulation_rows'] = {'value': len(frame), 'unit': 'person periods'}
                statistics['respy_'+scenario_name+'_simulation_individuals'] = {
                    'value': int(frame.index.get_level_values('Identifier').nunique()), 'unit': 'individuals'}
                for (period, choice), share in frame.groupby(level='Period')['Choice'].value_counts(normalize=True).items():
                    policy_rows.append({'scenario': scenario_name, 'period': int(period), 'choice': str(choice),
                                        'value': float(share), 'unit': 'simulated choice share'})
                initial_frame = frame.loc[frame.index.get_level_values('Period') == 0,
                    [c for c in state_columns if c in frame]]
                simulation = {'data': native_json(frame), 'params': native_json(scenario_params),
                    'method': method, 'requested_n_simulation_periods': requested_periods,
                    'effective_n_simulation_periods': int(frame.index.get_level_values('Period').max()+1),
                    'individuals': int(frame.index.get_level_values('Identifier').nunique()),
                    'initial_states': native_json(initial_frame),
                    'base_draws_sha256': {key: hashlib.sha256(simulator.keywords[key].tobytes()).hexdigest()
                                         for key in ('base_draws_sim', 'base_draws_wage')}}
                if spec.get('welfare'):
                    simulation['welfare'] = respy_welfare(frame, spec['welfare'], method, horizon)
                    statistics['respy_'+scenario_name+'_welfare'] = {
                        'value': simulation['welfare']['value'], 'unit': simulation['welfare']['unit']}
                simulations[scenario_name] = simulation
            if operation == 'counterfactual':
                for key in ('initial_states', 'base_draws_sha256'):
                    if simulations['baseline'][key] != simulations['scenario'][key]:
                        raise ArithmeticError('counterfactual must preserve the initial population and scenario draws')
                invariants = {'initial_states_equal': True, 'simulation_base_draws_equal': True,
                    'structural_options_equal': True,
                    'unchanged_parameters': native_json(params.loc[
                        [x for x in params.index if x[0].startswith(('wage_', 'nonpec_')) is False]]),
                    'transition_definition': adopted.get('transitions', 'Native respy options and state-transition parameters'),
                    'shock_definition': adopted.get('shocks', 'Native shock parameters and fixed seeded normal base draws')}
                if spec.get('welfare'):
                    statistics['respy_welfare_change'] = {
                        'value': simulations['scenario']['welfare']['value'] - simulations['baseline']['welfare']['value'],
                        'unit': simulations['baseline']['welfare']['unit']}
        for coordinate, row in params.iterrows():
            role = 'estimated' if coordinate in free else fit['parameter_status'] if not free else 'fixed'
            parameter_rows.append({'category': coordinate[0], 'parameter': coordinate[1],
                                   'value': float(row['value']), 'role': role})
        for key, value in statistics.items():
            diagnostics.append({'quantity': key, **value})
        displays = {
            'parameters': {'kind': 'table', 'title': 'Finite-horizon structural parameters', 'rows': parameter_rows,
                'columns': [{'key': x, 'label': x.replace('_', ' ').title(), 'unit': ''}
                            for x in ('category', 'parameter', 'value', 'role')],
                'metadata': {'model_contract': 'MC-respy-finite-choice', 'report_role': 'parameters'},
                'display': {'plot_type': 'table'}},
            'model_fit': {'kind': 'table', 'title': 'Criterion and scenario welfare', 'rows': diagnostics,
                'columns': [{'key': x, 'label': x.title(), 'unit': ''} for x in ('quantity', 'value', 'unit')],
                'metadata': {'model_contract': 'MC-respy-finite-choice', 'report_role': 'model_fit'},
                'display': {'plot_type': 'table'}}}
        if policy_rows:
            displays['choice_shares'] = {'kind': 'structural', 'title': 'Simulated choices by period', 'rows': policy_rows,
                'columns': [{'key': x, 'label': x.title(), 'unit': ''} for x in ('scenario', 'period', 'choice', 'value', 'unit')],
                'metadata': {'model_contract': 'MC-respy-finite-choice', 'report_role': 'counterfactual',
                             'unit': 'simulated choice share'}, 'display': {'plot_type': 'table'}}
        executed = ['solve', operation]
        if simulations and 'simulate' not in executed:
            executed.insert(1, 'simulate')
        return native_json({'model': 'finite_horizon_choice', 'operation': operation, 'adopted': adopted,
            'scenario': spec.get('scenario', {}), 'options': options,
            'computation': {'requested_operation': operation, 'operations_executed': executed,
                'parameter_operation': 'estimate' if operation == 'estimate' else 'reuse_'+fit['parameter_status']},
            'parameter_definition': {'coordinates': ['category', 'name'], 'free_parameters': free,
                'structural_parameters': 'Native utility, transition, shock and discount parameter dataframe',
                'optimization': 'Numerical minimization return; structural parameters retain native coordinates',
                'inference': 'Saved likelihood contributions or ordered moments and W; optional derivatives',
                'simulation_error': 'Independent-seed moment dispersion at the saved parameter vector'},
            'normalization': adopted.get('normalization', adopted.get('normalizations', 'Native params and options')),
            'equilibrium_selection': 'Individual finite-horizon backward induction at the adopted exogenous primitives',
            'welfare_definition': spec.get('welfare', adopted.get('welfare', {})),
            'horizon': horizon, 'solver': 'respy backward induction with adopted simulation integration',
            'engine': 'respy', 'fit': fit, 'fullresults': {'simulations': simulations,
                                                       'counterfactual_invariants': invariants},
            'statistics': statistics, 'displays': displays,
            'provenance': {'official_source': identity, 'sources': sources, 'python': sys.version.split()[0],
                'numpy': np.__version__, 'pandas': pd.__version__, 'scipy': scipy.__version__,
                'official_functions': (['get_log_like_func' if fit.get('estimation_method') == 'maximum_likelihood'
                    else 'get_moment_errors_func'] if operation == 'estimate' else [])
                    + (['get_simulate_func'] if simulations else []),
                'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}})


def _transition(n):
    p = np.zeros((2, n, n))
    for s in range(n):
        p[0, s, min(s + 1, n - 1)] = 1
        p[1, s, 0] = 1
    return p


def replacement(beta, costs, n, horizon=None):
    """EV1 shocks with Euler's constant normalized to zero; actions keep/replace."""
    p = _transition(n)
    flow = np.vstack((-costs[0] * np.arange(n), -costs[1] * np.ones(n)))
    v = np.zeros(n)
    history = []
    if horizon is None:
        def equation(value):
            q = flow + beta * np.einsum('ask,k->as', p, value)
            return value-logsumexp(q, axis=0)
        def derivative(value):
            q = flow + beta * np.einsum('ask,k->as', p, value)
            probabilities = softmax(q, axis=0)
            return np.eye(n)-beta*np.einsum('as,ask->sk', probabilities, p)
        solution = root(equation, v, jac=derivative, method='hybr',
                        options={'xtol': 1e-12, 'maxfev': 20000})
        v = solution.x
        bellman = float(np.max(np.abs(equation(v))))
        if not np.isfinite(v).all() or bellman >= 1e-12:
            raise ArithmeticError('replacement Bellman solve failed: '+str(solution.message))
        policy = softmax(flow+beta*np.einsum('ask,k->as', p, v), axis=0)
        iterations = int(solution.nfev)
        solver = {'method': 'scipy.optimize.root(hybr)', 'success': bool(solution.success),
                  'message': str(solution.message), 'nfev': int(solution.nfev),
                  'acceptance': 'original Bellman residual below 1e-12'}
    else:
        for iterations in range(1, horizon+1):
            q = flow + beta * np.einsum('ask,k->as', p, v)
            new = logsumexp(q, axis=0)
            policy = np.exp(q-new)
            history.append((new.copy(), policy.copy()))
            v = new
        previous = np.zeros(n)
        errors = []
        for stage_value, _ in history:
            rhs = logsumexp(flow+beta*np.einsum('ask,k->as', p, previous), axis=0)
            errors.append(float(np.max(np.abs(stage_value-rhs))))
            previous = stage_value
        bellman = max(errors)
        solver = {'method': 'finite-horizon backward recursion', 'periods': horizon}
    return {'value': v, 'policy': policy.T, 'transition': p, 'flow': flow,
            'iterations': iterations, 'bellman_residual': bellman,
            'solver': solver,
            'finite_stages_remaining': [{'value': v0.tolist(), 'policy': p0.T.tolist()} for v0, p0 in history] if horizon else None}


def fit_replacement(data, beta, n, start):
    """Fit the reset-to-zero model through the pinned official ruspy criterion."""
    import importlib.metadata
    import pandas as pd
    from ruspy.estimation.criterion_function import get_criterion_function
    distribution = importlib.metadata.distribution('ruspy')
    if distribution.version != '2.0':
        raise ValueError('official ruspy version 2.0 is required')
    from urllib.parse import unquote, urlparse
    import subprocess
    direct = distribution.read_text('direct_url.json')
    source = json.loads(direct) if direct else {}
    revision = source.get('vcs_info', {}).get('commit_id')
    location = source.get('url', '')
    if location.startswith('file:'):
        directory = Path(unquote(urlparse(location).path))
        check = subprocess.run(['git', '-C', str(directory), 'rev-parse', 'HEAD'], capture_output=True, text=True)
        revision = check.stdout.strip() if check.returncode == 0 else None
    if revision != '414e9f98e3b1cf19544b1ca3b1e544ac5751c1e9':
        raise ValueError('official ruspy source must match the pinned Git revision')
    frame = pd.DataFrame({'id': data[:, 0], 'period': data[:, 1]+1, 'state': data[:, 2],
                          'decision': data[:, 3], 'usage': np.ones(len(data), dtype=int)})
    frame = frame.set_index(['id', 'period']).sort_index()
    init = {'method': 'NFXP', 'model_specifications': {'discount_factor': beta, 'num_states': n,
                                                       'maint_cost_func': 'linear', 'cost_scale': 1.}}
    # Known usage is one unit before truncation. The next state after replacement is zero;
    # its equivalent ruspy replacement cost accounts for ruspy's additional usage step.
    with np.errstate(divide='ignore', invalid='ignore'):
        functions, transition = get_criterion_function(init, frame)
    if not np.array_equal(transition['x'], [0., 1.]):
        raise ArithmeticError('official transition differs from the declared deterministic increment')
    def official_parameters(costs):
        value = replacement(beta, costs, n)['value']
        return np.array([costs[1]+beta*(value[1]-value[0]), costs[0]])
    def objective(costs):
        return float(functions['criterion_function'](official_parameters(costs)))
    fit = minimize(objective, start, method='L-BFGS-B', bounds=[(.001, 4), (.001, 10)],
                   options={'ftol': 1e-12, 'gtol': 1e-6, 'maxiter': 400})
    if not fit.success:
        raise ArithmeticError('replacement likelihood: '+str(fit.message))
    model = replacement(beta, fit.x, n)
    independent = -float(np.log(np.clip(model['policy'][data[:, 2], data[:, 3]], 1e-300, 1)).sum())
    difference = abs(independent-float(fit.fun))
    if difference > max(1e-8, len(data)*1e-10):
        raise ArithmeticError('official criterion disagrees with original reset-model likelihood')
    return {'parameters': fit.x.tolist(), 'negative_log_likelihood': float(fit.fun),
            'iterations': int(fit.nit), 'success': bool(fit.success),
            'engine': 'ruspy.estimation.criterion_function.get_criterion_function/NFXP',
            'ruspy_version': distribution.version, 'ruspy_source_revision': revision,
            'ruspy_direct_url': distribution.read_text('direct_url.json'),
            'official_parameters': official_parameters(fit.x).tolist(),
            'original_likelihood_abs_difference': difference}


def fit_replacement_mpec(data, beta, n, start, config):
    """Fit the same reset model with official ruspy MPEC variables and constraints."""
    import pandas as pd
    from ruspy.estimation.criterion_function import get_criterion_function
    identity = official_package('ruspy', '2.0', '414e9f98e3b1cf19544b1ca3b1e544ac5751c1e9')
    frame = pd.DataFrame({'id': data[:, 0], 'period': data[:, 1]+1,
                         'state': data[:, 2], 'decision': data[:, 3],
                         'usage': np.ones(len(data), dtype=int)}).set_index(['id', 'period']).sort_index()
    init = {'method': 'MPEC', 'model_specifications': {'discount_factor': beta, 'num_states': n,
                                                    'maint_cost_func': 'linear', 'cost_scale': 1.}}
    with np.errstate(divide='ignore', invalid='ignore'):
        functions, transitions = get_criterion_function(init, frame)
    if not np.array_equal(transitions['x'], [0., 1.]):
        raise ArithmeticError('official transition differs from the adopted deterministic increment')
    # EV(s)=V(min(s+1,S-1)). At zero, V(0)=beta*EV(0)+log(1+exp(-R_official)).
    # Hence R=R_official-beta*(EV(0)-V(0)); this preserves reset-to-zero utility.
    def reset_cost(x):
        return x[n] - beta*(1-beta)*x[0] + beta*np.logaddexp(0., -x[n])
    def reset_cost_gradient(x):
        out = np.zeros(n+2)
        out[0] = -beta*(1-beta)
        out[n] = 1-beta*expit(-x[n])
        return out
    bounds = config.get('bounds', [[.001, 4.], [.001, 10.]])
    bounds = np.asarray(bounds, dtype=float)
    if (bounds.shape != (2, 2) or not np.isfinite(bounds).all()
            or (bounds[:, 0] >= bounds[:, 1]).any() or (bounds[:, 0] <= 0).any()
            or (np.asarray(start) < bounds[:, 0]).any() or (np.asarray(start) > bounds[:, 1]).any()):
        raise ValueError('MPEC requires positive [maintenance, reset replacement] bounds containing initial costs')
    initial_value = replacement(beta, start, n)['value']
    initial = np.r_[initial_value[np.minimum(np.arange(n)+1, n-1)],
                    start[1]+beta*(initial_value[1]-initial_value[0]), start[0]]
    constraints = [
        {'type': 'eq', 'fun': functions['constraint'], 'jac': functions['constraint_derivative']},
        {'type': 'ineq', 'fun': lambda x: reset_cost(x)-bounds[1, 0], 'jac': reset_cost_gradient},
        {'type': 'ineq', 'fun': lambda x: bounds[1, 1]-reset_cost(x),
         'jac': lambda x: -reset_cost_gradient(x)}]
    optimizer = config.get('optimizer', {'method': 'SLSQP', 'options': {'ftol': 1e-10, 'maxiter': 400}})
    if optimizer['method'] != 'SLSQP':
        raise ValueError('official replacement MPEC uses the adopted SLSQP constrained optimizer')
    fit = minimize(functions['criterion_function'], initial, jac=functions['criterion_derivative'],
        method='SLSQP', bounds=[(None, None)]*(n+1)+[tuple(bounds[0])], constraints=constraints,
        options=optimizer.get('options', {}), tol=optimizer.get('tolerance'))
    if not fit.success:
        raise ArithmeticError('official replacement MPEC: '+str(fit.message))
    residuals = np.asarray(functions['constraint'](fit.x))
    tolerance = float(config.get('constraint_tolerance', 1e-8))
    if tolerance <= 0 or not np.isfinite(tolerance) or np.max(np.abs(residuals)) > tolerance:
        raise ArithmeticError('official MPEC EV residual exceeds adopted tolerance')
    parameters = np.array([fit.x[-1], reset_cost(fit.x)])
    if (parameters < bounds[:, 0]-tolerance).any() or (parameters > bounds[:, 1]+tolerance).any():
        raise ArithmeticError('MPEC structural parameters violate adopted bounds')
    model = replacement(beta, parameters, n)
    independent = -float(np.log(model['policy'][data[:, 2], data[:, 3]]).sum())
    difference = abs(independent-float(fit.fun))
    if difference > max(1e-7, len(data)*tolerance*10):
        raise ArithmeticError('official MPEC likelihood differs from the original reset model')
    gradient = np.asarray(functions['criterion_derivative'](fit.x))
    jacobian = np.asarray(functions['constraint_derivative'](fit.x))
    native_sensitivity = -np.linalg.solve(jacobian[:, :n], jacobian[:, n:])
    concentrated_score = gradient[n:] + native_sensitivity.T @ gradient[:n]
    return {'parameters': parameters.tolist(), 'negative_log_likelihood': float(fit.fun),
        'success': bool(fit.success), 'iterations': int(fit.nit), 'optimizer_status': int(fit.status),
        'optimizer_message': str(fit.message), 'optimizer': optimizer, 'bounds': bounds.tolist(),
        'engine': 'ruspy.estimation.criterion_function.get_criterion_function/MPEC',
        'ruspy_version': identity['version'], 'ruspy_source_revision': identity['source_revision'],
        'official_parameters': fit.x[n:].tolist(), 'official_expected_values': fit.x[:n].tolist(),
        'official_variable_order': [f'EV_{s}' for s in range(n)]+['replacement_cost_official', 'maintenance_cost'],
        'structural_parameter_order': ['maintenance_cost', 'replacement_cost_reset_to_zero'],
        'parameter_transformation': 'R=R_official-beta*(1-beta)*EV_0+beta*log(1+exp(-R_official))',
        'official_ev_residuals': residuals.tolist(), 'official_ev_max_residual': float(np.max(np.abs(residuals))),
        'original_bellman_residual': model['bellman_residual'],
        'original_likelihood_abs_difference': difference,
        'official_original_ev_max_difference': float(np.max(np.abs(fit.x[:n]-model['value'][np.minimum(np.arange(n)+1, n-1)]))),
        'transition_estimates': transitions['x'].tolist(), 'transition_counts': transitions['trans_count'].tolist(),
        'inferential_information': {'criterion_gradient': gradient.tolist(), 'ev_constraint_jacobian': jacobian.tolist(),
            'concentrated_native_cost_score': concentrated_score.tolist(),
            'observation_keys': data[:, :2].tolist(), 'independent_unit': 'id'},
        'constraint_tolerance': tolerance}


def ruspy_native_run(spec, base):
    """Estimate the explicitly adopted reset-then-usage model on its native panel."""
    import pandas as pd
    from ruspy.estimation.criterion_function import get_criterion_function
    from ruspy.estimation.estimation_transitions import create_transition_matrix
    from ruspy.model_code.cost_functions import calc_obs_costs, lin_cost
    from ruspy.model_code.fix_point_alg import calc_fixp
    from ruspy.model_code.choice_probabilities import choice_prob_gumbel
    identity = official_package('ruspy', '2.0', '414e9f98e3b1cf19544b1ca3b1e544ac5751c1e9')
    options = spec['options']; native = options['ruspy']; data_spec = spec['data']
    mapping = data_spec['columns']
    if set(mapping) != {'id', 'period', 'state', 'action', 'usage'} or len(set(mapping.values())) != 5:
        raise ValueError('reset_then_usage requires unique id, period, state, action and usage columns')
    path, source = source_file(data_spec['path'], base)
    frame = research_data.read_frame(path, columns=list(mapping.values())).rename(columns={v: k for k, v in mapping.items()})
    frame = frame[list(mapping)].rename(columns={'action': 'decision'}).set_index(['id', 'period']).sort_index()
    if frame.empty or not frame.index.is_unique:
        raise ValueError('native replacement panel requires unique id/period keys')
    index_values = frame.index.to_frame(index=False).to_numpy(dtype=float)
    if not np.isfinite(index_values).all() or (index_values < 0).any() or not np.equal(index_values, np.floor(index_values)).all():
        raise ValueError('native replacement panel keys must be nonnegative integers')
    model = copy.deepcopy(native['model_specifications'])
    if model['maint_cost_func'] != 'linear':
        raise ValueError('the replacement contract uses the native linear maintenance-cost function')
    beta = float(model['discount_factor']); n = int(model['num_states']); scale = float(model['cost_scale'])
    if not 0 < beta < 1 or n < 3 or not np.isfinite(scale) or scale <= 0:
        raise ValueError('invalid native replacement state count, discount or cost scale')
    for key in ('state', 'decision'):
        values = pd.to_numeric(frame[key], errors='raise').to_numpy(dtype=float)
        if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
            raise ValueError('native states and decisions must be finite integers')
        frame[key] = values.astype(int)
    if ((frame.state < 0) | (frame.state >= n)).any() or not frame.decision.isin([0, 1]).all():
        raise ValueError('native observations must lie in the adopted state/action support')
    usage = pd.to_numeric(frame.usage, errors='raise').to_numpy(dtype=float)
    observed_usage = usage[~np.isnan(usage)]
    if not len(observed_usage) or not np.isfinite(observed_usage).all() or (observed_usage < 0).any() or not np.equal(observed_usage, np.floor(observed_usage)).all():
        raise ValueError('observed native usage must be nonnegative integers')
    frame['usage'] = usage
    sample = frame.loc[(slice(None), slice(1, None)), :]
    if sample.empty:
        raise ValueError('official choice likelihood requires observations at period 1 or later')
    method = options.get('estimation_method', 'nfxp')
    if method not in ('mpec', 'nfxp'):
        raise ValueError('native replacement estimation_method must be nfxp or mpec')
    init = {'method': method.upper(), 'model_specifications': model, 'alg_details': native.get('alg_details', {})}
    functions, transitions = get_criterion_function(init, frame)
    transition = create_transition_matrix(n, np.asarray(transitions['x']))
    start = np.asarray(native['initial_parameters'], dtype=float)
    bounds = native['bounds']
    if start.shape != (2,) or not np.isfinite(start).all() or len(bounds) != 2:
        raise ValueError('native initial_parameters and bounds use [replacement_cost, maintenance_coefficient]')
    for value, pair in zip(start, bounds):
        if len(pair) != 2 or (pair[0] is not None and value < pair[0]) or (pair[1] is not None and value > pair[1]):
            raise ValueError('native initial parameters must satisfy their adopted bounds')
    optimizer = native['optimizer']
    if optimizer['method'] != ('SLSQP' if method == 'mpec' else 'L-BFGS-B'):
        raise ValueError('native MPEC uses SLSQP and native NFXP uses L-BFGS-B')
    tolerance = float(native.get('constraint_tolerance', 1e-8))
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('constraint_tolerance must be positive')
    initial_ev = calc_fixp(transition, calc_obs_costs(n, lin_cost, start, scale), beta,
                           **native.get('alg_details', {}))[0]
    if method == 'mpec':
        initial = np.r_[initial_ev, start]
        constraints = [{'type': 'eq', 'fun': functions['constraint'], 'jac': functions['constraint_derivative']}]
        optimization_bounds = [(None, None)]*n + bounds
    else:
        initial, constraints, optimization_bounds = start, (), bounds
    optimization = minimize(functions['criterion_function'], initial, jac=functions['criterion_derivative'],
        method=optimizer['method'], bounds=optimization_bounds, constraints=constraints,
        options=optimizer.get('options', {}), tol=optimizer.get('tolerance'))
    if not optimization.success:
        raise ArithmeticError('official native '+method.upper()+': '+str(optimization.message))
    parameters = optimization.x[n:] if method == 'mpec' else optimization.x
    ev_residuals = functions['constraint'](optimization.x) if method == 'mpec' else None
    if ev_residuals is not None and np.max(np.abs(ev_residuals)) > tolerance:
        raise ArithmeticError('official native MPEC violates its original EV constraints')
    initial_states = frame.groupby(level='id', sort=True).head(1)['state'].to_numpy(dtype=int)
    def solution(cost_parameters):
        costs = calc_obs_costs(n, lin_cost, cost_parameters, scale)
        ev, contractions, newton_steps = calc_fixp(transition, costs, beta, **native.get('alg_details', {}))
        policy = choice_prob_gumbel(ev, costs, beta)
        flows = np.column_stack((-costs[:, 0], np.repeat(-costs[0, 1], n)))
        action_transition = np.stack((transition, np.repeat(transition[[0]], n, axis=0)))
        values = logsumexp(flows + beta*np.column_stack((ev, np.repeat(ev[0], n))), axis=1)
        original_rhs = logsumexp(flows + beta*np.einsum('ask,k->sa', action_transition, values), axis=1)
        residual = float(np.max(np.abs(values-original_rhs)))
        if residual > tolerance:
            raise ArithmeticError('native replacement solution violates the original Bellman equation')
        return {'value': values.tolist(), 'policy': policy.tolist(), 'expected_value': ev.tolist(),
            'transition': action_transition.tolist(), 'flow': flows.tolist(),
            'bellman_residual': residual, 'ev_residual': float(np.max(np.abs(transition @ values-ev))),
            'contractions': int(contractions), 'newton_steps': int(newton_steps),
            'initial_population_value': float(values[initial_states].mean()),
            'parameters_native': cost_parameters.tolist()}
    baseline = solution(parameters)
    scenario_parameters = parameters.copy()
    change = float(options['replacement_cost_change'])
    if not np.isfinite(change):
        raise ValueError('replacement cost change must be finite')
    scenario_parameters[0] += change
    scenario = solution(scenario_parameters)
    probabilities = np.asarray(baseline['policy'])[sample.state.to_numpy(), sample.decision.to_numpy()]
    original_likelihood = -float(np.log(probabilities).sum())
    difference = abs(original_likelihood-float(optimization.fun))
    if difference > max(1e-7, len(sample)*tolerance*10):
        raise ArithmeticError('official native criterion differs from the original observation likelihood')
    inferential = {'independent_unit': 'id', 'observation_keys': sample.index.tolist(),
        'criterion_gradient': functions['criterion_derivative'](optimization.x),
        'transition_counts': transitions['trans_count'], 'choice_log_likelihood_contributions': np.log(probabilities)}
    if method == 'mpec':
        jacobian = np.asarray(functions['constraint_derivative'](optimization.x))
        gradient = np.asarray(inferential['criterion_gradient'])
        sensitivity = -np.linalg.solve(jacobian[:, :n], jacobian[:, n:])
        inferential.update(ev_constraint_jacobian=jacobian,
                          concentrated_native_cost_score=gradient[n:]+sensitivity.T@gradient[:n])
    estimate = {'parameters': [float(parameters[1]*scale), float(parameters[0])],
        'structural_parameter_order': ['maintenance_cost_per_state', 'replacement_cost_reset_then_usage'],
        'official_parameters': parameters.tolist(), 'official_parameter_order': ['replacement_cost', 'maintenance_coefficient'],
        'official_expected_values': optimization.x[:n].tolist() if method == 'mpec' else baseline['expected_value'],
        'official_variable_order': [f'EV_{s}' for s in range(n)]+['replacement_cost', 'maintenance_coefficient']
                                 if method == 'mpec' else ['replacement_cost', 'maintenance_coefficient'],
        'negative_log_likelihood': float(optimization.fun), 'original_likelihood_abs_difference': difference,
        'success': bool(optimization.success), 'iterations': int(optimization.nit), 'evaluations': int(optimization.nfev),
        'optimizer_status': int(optimization.status), 'optimizer_message': str(optimization.message),
        'optimizer': optimizer, 'bounds': bounds, 'initial_parameters': start.tolist(),
        'engine': 'ruspy.estimation.criterion_function.get_criterion_function/'+method.upper(),
        'official_ev_residuals': ev_residuals,
        'official_ev_max_residual': float(np.max(np.abs(ev_residuals))) if ev_residuals is not None else baseline['ev_residual'],
        'transition_estimates': transitions['x'], 'transition_counts': transitions['trans_count'],
        'transition_negative_log_likelihood': float(transitions['fun']), 'inferential_information': inferential,
        'ruspy_version': identity['version'], 'ruspy_source_revision': identity['source_revision']}
    results = {method: estimate, 'baseline': baseline, 'scenario': scenario}
    source.update(rows=len(frame), choice_rows=len(sample), columns=mapping,
                  choice_sample_keys=sample.index.tolist(), initial_states=initial_states.tolist())
    return native_json({'model': 'replacement', 'adopted': spec.get('adopted', {}), 'scenario': spec.get('scenario', {}),
        'options': options, 'transition': 'Reset mileage to zero, then draw observed-usage transition; cap at last state',
        'engine': estimate['engine'], 'fullresults': results, 'displays': replacement_displays(results),
        'statistics': {'replacement_cost_'+method: {'value': float(parameters[0]), 'unit': 'utility'},
            'maintenance_cost_per_state_'+method: {'value': float(parameters[1]*scale), 'unit': 'utility per mileage state'},
            'replacement_bellman_residual': {'value': baseline['bellman_residual'], 'unit': 'utility'},
            'replacement_baseline_value': {'value': baseline['initial_population_value'], 'unit': 'utility'},
            'replacement_scenario_value': {'value': scenario['initial_population_value'], 'unit': 'utility'},
            'replacement_value_change': {'value': scenario['initial_population_value']-baseline['initial_population_value'], 'unit': 'utility'}},
        'computation': {'requested_operation': 'estimate', 'operations_executed': ['estimate', 'solve', 'counterfactual'],
                        'parameter_operation': 'estimate', 'estimation_method': method},
        'parameter_definition': {'structural_order': estimate['structural_parameter_order'],
            'native_cost_order': estimate['official_parameter_order'], 'maintenance_cost_scale': scale,
            'native_expected_values': 'EV=P_usage V; replacement continuation uses EV(0)',
            'replacement_cost': 'Native replacement payoff cost before the common usage draw',
            'optimization_variables': estimate['official_variable_order']},
        'normalization': 'Unit-scale EV1 action shocks; Euler constant normalized to zero',
        'equilibrium_selection': 'Unique discounted single-agent Bellman fixed point',
        'welfare_definition': {'quantity': 'Mean initial-state inclusive value across observed individuals',
                               'initial_states': initial_states.tolist(), 'population_weights': 'equal',
                               'unit': 'utility', 'includes': 'Unit-scale normalized EV1 action shocks'},
        'horizon': 'infinite', 'solver': 'Official ruspy '+method.upper()+' and calc_fixp',
        'provenance': {'data': source, 'official_source': identity, 'python': sys.version.split()[0],
            'numpy': np.__version__, 'pandas': pd.__version__, 'scipy': scipy.__version__,
            'official_functions': ['get_criterion_function', 'calc_fixp', 'choice_prob_gumbel'],
            'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}})


def fit_replacement_smm(data, beta, n, config, source_sha256):
    """Fit replacement costs by matching simulated full-panel action histories."""
    required = {'seed', 'replications', 'initial_costs', 'bounds', 'tolerance'}
    if not isinstance(config, dict) or set(config) != required:
        raise ValueError('smm requires seed, replications, initial_costs, bounds and tolerance')
    replications = int(config['replications']); seed = int(config['seed'])
    initial = np.asarray(config['initial_costs'], dtype=float)
    bounds = np.asarray(config['bounds'], dtype=float); tolerance = float(config['tolerance'])
    if (replications < 2 or initial.shape != (2,) or bounds.shape != (2, 2) or
            not np.isfinite([*initial, *bounds.ravel(), tolerance]).all() or tolerance <= 0 or
            (bounds[:, 0] <= 0).any() or (bounds[:, 0] >= bounds[:, 1]).any() or
            (initial < bounds[:, 0]).any() or (initial > bounds[:, 1]).any()):
        raise ValueError('invalid SMM starting costs, bounds, repetitions or tolerance')
    identifiers = np.unique(data[:, 0])
    groups = [data[data[:, 0] == identifier] for identifier in identifiers]
    starts = np.array([group[0, 2] for group in groups]); lengths = np.array([len(group) for group in groups])
    observed_counts = np.bincount(data[:, 2], minlength=n)
    if np.any(observed_counts == 0):
        raise ValueError('SMM moments require observations in every state')
    observed_actions = np.bincount(data[:, 2], weights=data[:, 3], minlength=n)
    observed = np.r_[np.mean(data[:, 3]), observed_actions/observed_counts]
    horizon = int(max(lengths)); households = len(groups)
    draws = np.random.default_rng(seed).random((replications, households, horizon))
    replicate = np.broadcast_to(np.arange(replications)[:, None], (replications, households))
    def simulated_moments(costs):
        policy = replacement(beta, costs, n)['policy'][:, 1]
        state = np.broadcast_to(starts, (replications, households)).copy()
        counts = np.zeros((replications, n)); actions = np.zeros((replications, n))
        for t in range(horizon):
            active = np.broadcast_to(t < lengths, state.shape)
            action = draws[:, :, t] < policy[state]
            index = (replicate*n+state)[active]
            counts += np.bincount(index, minlength=replications*n).reshape(replications, n)
            actions += np.bincount(index, weights=action[active], minlength=replications*n).reshape(replications, n)
            state = np.where(active, np.where(action, 0, np.minimum(state+1, n-1)), state)
        if np.any(counts == 0):
            raise ValueError('SMM simulation must visit each state in each replication')
        return np.column_stack((actions.sum(axis=1)/counts.sum(axis=1), actions/counts))
    def objective(costs):
        try:
            error = simulated_moments(costs).mean(axis=0)-observed
        except ValueError as error:
            if str(error) == 'SMM simulation must visit each state in each replication':
                return 1e6
            raise
        return float(error @ error)
    fit = minimize(objective, initial, method='Powell', bounds=bounds.tolist(),
                   options={'xtol': tolerance, 'ftol': tolerance*tolerance, 'maxiter': 300})
    if not fit.success or not np.isfinite(fit.fun):
        raise ArithmeticError('simulation moment optimization failed: '+str(fit.message))
    simulated = simulated_moments(fit.x)
    # The rank calculation uses the exact expected Markov moment map, not finite-difference
    # derivatives of the discontinuous simulated sample criterion.
    def expected_moments(costs):
        model = replacement(beta, costs, n); policy = model['policy']; transition = model['transition']
        distribution = np.eye(n)[starts]; counts = np.zeros(n); action_counts = np.zeros(n)
        mixed = np.einsum('sa,ask->sk', policy, transition)
        for t in range(horizon):
            mass = distribution[lengths > t].sum(axis=0)
            counts += mass; action_counts += mass*policy[:, 1]
            distribution = distribution@mixed
        return np.r_[action_counts.sum()/counts.sum(), action_counts/counts]
    derivative_steps = (1e-5*np.maximum(1., np.abs(fit.x))).tolist()
    jacobian = finite_jacobian(expected_moments, fit.x, np.asarray(derivative_steps))
    singular = np.linalg.svd(jacobian, compute_uv=False)
    rank_tolerance = float(max(jacobian.shape)*singular[0]*np.finfo(float).eps)
    rank = int(np.sum(singular > rank_tolerance))
    if rank < 2:
        raise ArithmeticError('SMM costs are not locally identified by the declared moments')
    fit_id = hashlib.sha256(json.dumps({'source_sha256': source_sha256, 'beta': beta, 'states': n,
                                       'config': config, 'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                                      sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'fit_id': fit_id, 'parameters': fit.x.tolist(), 'moment_order': ['replacement_rate']+
            [f'replacement_given_state_{s}' for s in range(n)], 'observed_moments': observed.tolist(),
            'simulated_moments': simulated.mean(axis=0).tolist(),
            'moment_residuals': (simulated.mean(axis=0)-observed).tolist(),
            'simulation_standard_errors': (simulated.std(axis=0, ddof=1)/np.sqrt(replications)).tolist(),
            'criterion': float(fit.fun), 'weighting': 'identity', 'expected_moment_jacobian': jacobian.tolist(),
            'expected_moment_jacobian_rank': rank, 'expected_moment_jacobian_singular_values': singular.tolist(),
            'jacobian_central_difference_steps': derivative_steps, 'jacobian_rank_tolerance': rank_tolerance,
            'seed': seed, 'replications': replications,
            'initial_states': starts.tolist(), 'panel_lengths': lengths.tolist(), 'bounds': bounds.tolist(),
            'optimizer': 'scipy.optimize.minimize/Powell', 'optimizer_tolerance': tolerance,
            'optimizer_iterations': int(fit.nit), 'optimizer_evaluations': int(fit.nfev),
            'optimizer_success': bool(fit.success)}


def ccp_fit(data, beta, n):
    counts = np.zeros((n, 2))
    np.add.at(counts, (data[:, 2], data[:, 3]), 1)
    if np.any(counts == 0):
        raise ValueError('CCP inversion requires both observed actions in each state')
    prob = counts / counts.sum(axis=1, keepdims=True)
    entropy = -(prob * np.log(prob)).sum(axis=1)
    p = _transition(n)
    mixed = np.einsum('sa,ask->sk', prob, p)
    inverse = np.linalg.inv(np.eye(n) - beta * mixed)
    direct_difference = np.column_stack((np.arange(n), -np.ones(n)))
    # Flow u(s,keep)=-c*s; u(s,replace)=-R.
    flow_by_coefficient = np.column_stack((-prob[:, 0] * np.arange(n), -prob[:, 1]))
    value_coefficient = inverse @ flow_by_coefficient
    value_entropy = inverse @ entropy
    diff = p[1] - p[0]
    design = direct_difference + beta * diff @ value_coefficient
    outcome = np.log(prob[:, 1] / prob[:, 0]) - beta * diff @ value_entropy
    params, _, rank, _ = np.linalg.lstsq(design, outcome, rcond=None)
    if rank < 2:
        raise ArithmeticError('CCP parameters not identified by observed state variation')
    return {'parameters': params.tolist(), 'sample_probabilities': prob.tolist(), 'counts': counts.tolist(),
            'rank': int(rank), 'inversion_max_residual': float(np.max(np.abs(outcome - design @ params)))}


def ct_game(rho, rate, profit, competition, entry_cost, exit_cost):
    """Two symmetric players; independent EV1 shocks at Poisson revision opportunities."""
    states = [(0, 0), (0, 1), (1, 0), (1, 1)]
    toggles = np.array([[states.index(tuple(1-x if j == i else x for j, x in enumerate(s)))
                         for s in states] for i in range(2)])
    flows = np.array([[s[i] * (profit - competition * s[1-i]) for s in states] for i in range(2)])
    costs = np.array([[exit_cost if s[i] else entry_cost for s in states] for i in range(2)])
    def bellman(flat):
        v = flat.reshape(2, 4)
        result = np.empty((2, 4))
        for i in range(2):
            j = 1-i
            own_diff = v[i, toggles[i]] - v[i] - costs[i]
            rival_diff = v[j, toggles[j]] - v[j] - costs[j]
            result[i] = flows[i] + rate * np.logaddexp(0, own_diff) + rate * expit(rival_diff) * (v[i, toggles[j]] - v[i]) - rho * v[i]
        return result.ravel()
    solution = root(bellman, np.zeros(8), tol=1e-11)
    resid = float(np.max(np.abs(bellman(solution.x))))
    if not solution.success or resid > 1e-8:
        raise ArithmeticError('continuous-time game did not solve: ' + str(solution.message))
    v = solution.x.reshape(2, 4)
    policies = np.array([expit(v[i, toggles[i]]-v[i]-costs[i]) for i in range(2)])
    q = np.zeros((4, 4))
    for i in range(2):
        for s in range(4):
            q[s, toggles[i, s]] += rate * policies[i, s]
    q[np.diag_indices(4)] = -q.sum(axis=1)
    transition = expm(q)
    transition_error = max(float(np.max(np.abs(transition.sum(axis=1)-1))),
                           max(0., -float(transition.min())))
    if transition_error > 1e-10:
        raise ArithmeticError('matrix exponential fails transition probability constraints')
    policy_error = max(float(np.max(np.abs(policies[i] - expit(v[i, toggles[i]] - v[i] - costs[i])))) for i in range(2))
    return {'states': states, 'values': v.tolist(), 'toggle_probabilities': policies.tolist(),
            'selection': 'root solver initialized at zero values', 'policy_residual': policy_error,
            'generator': q.tolist(), 'one_unit_transition': transition.tolist(),
            'transition_engine': 'scipy.linalg.expm', 'bellman_residual': resid,
            'generator_row_residual': float(np.max(np.abs(q.sum(axis=1)))),
            'transition_probability_residual': transition_error,
            'initial_empty_total_value': float(v[:, 0].sum())}



_STATES = [(0, 0), (0, 1), (1, 0), (1, 1)]


def discrete_policy_value(policies, beta, profit, competition, entry_cost):
    """Ex-ante values for arbitrary independent mixed stationary Markov policies."""
    p = np.asarray(policies)
    transition = np.zeros((4, 4)); payoff = np.zeros((2, 4))
    for sidx, state in enumerate(_STATES):
        for nextidx, action in enumerate(_STATES):
            prob = np.prod([p[i, sidx] if action[i] else 1-p[i, sidx] for i in range(2)])
            transition[sidx, nextidx] = prob
            for i in range(2):
                payoff[i, sidx] += prob * (action[i] * (profit - competition*action[1-i])
                                           - entry_cost * action[i] * (1-state[i]))
        for i in range(2):
            q = p[i, sidx]
            payoff[i, sidx] -= q*np.log(q) + (1-q)*np.log1p(-q)
    value = np.array([np.linalg.solve(np.eye(4)-beta*transition, payoff[i]) for i in range(2)])
    return value, transition


def game_response(logits, beta, profit, competition, entry_cost):
    policies = expit(logits.reshape(2, 4))
    values, transition = discrete_policy_value(policies, beta, profit, competition, entry_cost)
    response = np.empty((2, 4))
    for i in range(2):
        j = 1-i
        for si, state in enumerate(_STATES):
            q = []
            for ai in (0, 1):
                total = 0.
                for aj in (0, 1):
                    action = (ai, aj) if i == 0 else (aj, ai)
                    prob = policies[j, si] if aj else 1-policies[j, si]
                    total += prob * (ai*(profit-competition*aj) - entry_cost*ai*(1-state[i])
                                     + beta*values[i, _STATES.index(action)])
                q.append(total)
            response[i, si] = q[1]-q[0]
    return response, policies, values, transition


def discrete_game(beta, profit, competition, entry_cost):
    def response(x):
        return game_response(x, beta, profit, competition, entry_cost)
    solution = root(lambda x: (x.reshape(2, 4)-response(x)[0]).ravel(), np.zeros(8), tol=1e-10)
    logits, policies, values, transition = response(solution.x)
    error = float(np.max(np.abs(policies-expit(logits))))
    if not solution.success or error > 1e-8:
        raise ArithmeticError('discrete game failed to solve: ' + str(solution.message))
    return {'states': _STATES, 'policies': policies, 'values': values, 'transition': transition,
            'policy_residual': error, 'selection': 'root solver initialized at zero logits'}


def sequential_estimate(data, beta, profit, competition, bounds, method):
    """Sequential pseudo-likelihood, Newton EPL, or affine SLC estimator."""
    counts = np.zeros((2, 4, 2))
    for row in data:
        for i in range(2):
            counts[i, row[2], row[3+i]] += 1
    if np.any(counts == 0):
        raise ValueError('sequential estimation requires both actions in every firm-state')
    probability = counts[:, :, 1] / counts.sum(axis=2)
    x = np.log(probability / (1-probability)).ravel()
    theta = sum(bounds) / 2
    def response(x, theta):
        return game_response(x, beta, profit, competition, theta)[0].ravel()
    def residual(x, theta):
        return x-response(x, theta)
    def jacobian(x, theta):
        return finite_jacobian(lambda value: residual(value, theta), x, 1e-5)
    def objective(x):
        x = x.reshape(2, 4)
        return float(np.sum(counts[:, :, 0]*np.logaddexp(0, x) + counts[:, :, 1]*np.logaddexp(0, -x)))
    trace = []
    for iteration in range(100):
        if method == 'npl':
            def mapping(candidate):
                return response(x, candidate)
        elif method == 'epl':
            j = jacobian(x, theta)
            def mapping(candidate):
                return x - np.linalg.solve(j, residual(x, candidate))
        elif method == 'slc':
            j = jacobian(x, theta)
            step = 1e-5
            partial = (residual(x, theta+step)-residual(x, theta-step))/(2*step)
            correction = np.linalg.solve(j, -residual(x, theta))
            tangent = np.linalg.solve(j, -partial)
            def mapping(candidate):
                return x + correction + tangent*(candidate-theta)
        else:
            raise ValueError('unknown sequential estimation method')
        fitted = minimize_scalar(lambda candidate: objective(mapping(candidate)), bounds=tuple(bounds),
                                 method='bounded', options={'xatol': 1e-10})
        if not fitted.success:
            raise ArithmeticError('sequential parameter optimization failed')
        next_theta = float(fitted.x)
        next_x = mapping(next_theta)
        theta_change = abs(next_theta-theta)
        equation_error = float(np.max(np.abs(residual(next_x, next_theta))))
        trace.append({'entry_cost': next_theta, 'equilibrium_logit_residual': equation_error,
                      'parameter_change': theta_change})
        x, theta = next_x, next_theta
        if theta_change < 1e-7 and equation_error < 1e-7:
            break
    else:
        raise ArithmeticError(f'{method} sequential estimation did not converge')
    j = jacobian(x, theta); step = 1e-5
    partial = (residual(x, theta+step)-residual(x, theta-step))/(2*step)
    sensitivity = np.linalg.solve(j, -partial)
    gradient = ((counts.sum(axis=2)*expit(x.reshape(2, 4))-counts[:, :, 1]).ravel())
    constrained_score = float(gradient @ sensitivity / len(data))
    pseudo_score = float(gradient @ (-partial) / len(data))
    return {'method': method, 'entry_cost': theta, 'negative_log_likelihood': objective(x),
            'equilibrium_logit_residual': equation_error, 'constrained_score_per_observation': constrained_score,
            'pseudo_score_per_observation': pseudo_score, 'equilibrium_jacobian_condition': float(np.linalg.cond(j)),
            'iterations': iteration+1, 'trace': trace, 'policies': expit(x.reshape(2, 4)).tolist()}


def bbl_estimate(data, beta, profit, competition, bounds):
    counts = np.zeros((2, 4, 2))
    for row in data:
        for i in range(2):
            counts[i, row[2], row[3+i]] += 1
    if np.any(counts == 0):
        raise ValueError('game CCP estimation requires both actions for each firm-state')
    policy = counts[:, :, 1] / counts.sum(axis=2)
    # Each deviation perturbs one player's stationary policy in every state.
    deviations = []
    for i in range(2):
        for shift in (-.3, -.1, .1, .3):
            alternative = policy.copy()
            alternative[i] = expit(np.log(policy[i]/(1-policy[i])) + shift)
            deviations.append((i, alternative))
    def gains(cost):
        base, _ = discrete_policy_value(policy, beta, profit, competition, cost)
        return np.concatenate([base[i] - discrete_policy_value(alt, beta, profit, competition, cost)[0][i]
                               for i, alt in deviations])
    def criterion(cost):
        g = gains(cost)
        return float(np.minimum(g, 0) @ np.minimum(g, 0))
    fit = minimize_scalar(criterion, bounds=tuple(bounds), method='bounded', options={'xatol': 1e-10})
    if not fit.success:
        raise ArithmeticError('deviation-inequality estimation failed')
    intercept = gains(0.); slope = gains(1.) - intercept
    lower, upper = map(float, bounds)
    for a, b in zip(intercept, slope):
        if b > 1e-12:
            lower = max(lower, float(-a/b))
        elif b < -1e-12:
            upper = min(upper, float(-a/b))
        elif a < 0:
            lower = upper + 1
    identified_set = [lower, upper] if lower <= upper else None
    selected = (lower+upper)/2 if identified_set else float(fit.x)
    return {'entry_cost': selected, 'sample_inequality_set': identified_set,
            'criterion': criterion(selected), 'sample_probabilities': policy.tolist(),
            'counts': counts.tolist(), 'deviation_gains': gains(selected).tolist(),
            'deviation_log_odds_shifts': [-.3, -.1, .1, .3],
            'known_primitives': {'discount_factor': beta, 'active_profit': profit, 'competition': competition},
            'estimator': 'squared negative Markov-policy deviation gains'}


def latent_em(states, actions, beta, maintenance, n, initial_costs, initial_share, bounds):
    def panel_log_likelihood(cost):
        model = replacement(beta, [maintenance, cost], n)
        return np.log(model['policy'][states, actions]).sum(axis=1)
    costs = np.asarray(initial_costs, dtype=float); share = float(initial_share)
    history = []
    for iteration in range(250):
        loglik = np.column_stack([panel_log_likelihood(cost) for cost in costs])
        joint = loglik + np.log([share, 1-share])
        total = logsumexp(joint, axis=1)
        responsibilities = np.exp(joint-total[:, None])
        value = float(total.sum())
        if history and value < history[-1] - 1e-7:
            raise ArithmeticError('EM observed likelihood decreased')
        history.append(value)
        next_share = float(responsibilities[:, 0].mean())
        next_costs = []
        for k in range(2):
            fitted = minimize_scalar(lambda cost: -float(responsibilities[:, k] @ panel_log_likelihood(cost)),
                                     bounds=tuple(bounds), method='bounded', options={'xatol': 1e-7})
            if not fitted.success:
                raise ArithmeticError('latent-type M step failed')
            next_costs.append(float(fitted.x))
        next_costs = np.asarray(next_costs)
        if next_costs[0] > next_costs[1]:
            next_costs = next_costs[::-1]; next_share = 1-next_share
        change = max(float(np.max(np.abs(next_costs-costs))), abs(next_share-share))
        costs, share = next_costs, next_share
        if change < 1e-6:
            break
    else:
        raise ArithmeticError('latent-type EM did not converge')
    final_joint = np.column_stack([panel_log_likelihood(cost) for cost in costs]) + np.log([share, 1-share])
    final_likelihood = float(logsumexp(final_joint, axis=1).sum())
    if final_likelihood < history[-1] - 1e-7:
        raise ArithmeticError('final EM likelihood decreased')
    return {'replacement_costs': costs.tolist(), 'type_one_share': share,
            'negative_log_likelihood': -final_likelihood, 'likelihood_trace': history + [final_likelihood],
            'iterations': iteration+1, 'final_parameter_change': change}


def dynamic_adoption(delta, price, shock_types, weights, beta, transition):
    """Dynamic durable-good adoption for a fixed distribution of permanent price tastes."""
    delta = np.asarray(delta); price = np.asarray(price); shock_types = np.asarray(shock_types)
    weights = np.asarray(weights); transition = np.asarray(transition)
    value = np.zeros((len(weights), len(delta)))
    utility = delta[None, :] + shock_types[:, None] * price[None, :]
    def equation(flat):
        candidate = flat.reshape(value.shape)
        return (candidate-np.logaddexp(utility, beta*candidate@transition.T)).ravel()
    solution = root(equation, value.ravel(), method='hybr',
                    options={'xtol': 1e-12, 'maxfev': 20000})
    value = solution.x.reshape(value.shape)
    continuation = beta * value @ transition.T
    policy = expit(utility-continuation)
    residual = float(np.max(np.abs(value-np.logaddexp(utility, continuation))))
    if not np.isfinite(value).all() or residual >= 1e-12:
        raise ArithmeticError('dynamic adoption Bellman solve failed: '+str(solution.message))
    return weights @ policy, value, policy, residual



def capacity_game(beta, demand, competition, investment_cost, switching_cost):
    """Two-player finite Markov game with exit and three capacity-product choices."""
    states = list(itertools.product(range(4), repeat=2))
    capacity = np.array([0, 1, 2, 1]); product = np.array([0, 1, 1, 2])
    margin = np.array([0, demand[0], demand[0], demand[1]])
    flow = np.empty((2, 16, 16))
    for i in range(2):
        for si, state in enumerate(states):
            for ai, actions in enumerate(states):
                own, rival = actions[i], actions[1-i]
                overlap = 1. if product[own] == product[rival] else .3
                flow[i, si, ai] = (capacity[own] * (margin[own]-competition*capacity[rival]*overlap)
                    - investment_cost*max(capacity[own]-capacity[state[i]], 0)
                    - switching_cost*int(capacity[own] > 0 and capacity[state[i]] > 0
                                         and product[own] != product[state[i]]))
    def evaluate(x):
        logits = np.concatenate((np.zeros((2, 16, 1)), x.reshape(2, 16, 3)), axis=2)
        policy = softmax(logits, axis=2)
        joint = (policy[0, :, :, None]*policy[1, :, None, :]).reshape(16, 16)
        entropy = logsumexp(logits, axis=2)-np.sum(policy*logits, axis=2)
        reward = np.einsum('sa,isa->is', joint, flow)+entropy
        value = np.linalg.solve(np.eye(16)-beta*joint, reward.T).T
        q = np.zeros((2, 16, 4))
        for i in range(2):
            for si in range(16):
                for ai in range(4):
                    for aj in range(4):
                        next_state = (ai, aj) if i == 0 else (aj, ai)
                        j = states.index(next_state)
                        q[i, si, ai] += policy[1-i, si, aj]*(flow[i, si, j]+beta*value[i, j])
        return (q[:, :, 1:]-q[:, :, :1]).ravel(), policy, value, joint, reward
    solution = root(lambda x: x-evaluate(x)[0], np.zeros(96), tol=1e-9)
    response, policy, value, transition, reward = evaluate(solution.x)
    policy_residual = float(np.max(np.abs(solution.x-response)))
    bellman_residual = float(np.max(np.abs(value-reward-beta*value@transition.T)))
    if not solution.success or max(policy_residual, bellman_residual) > 1e-7:
        raise ArithmeticError('capacity-product equilibrium did not converge')
    return {'states': states, 'action_capacity': capacity.tolist(), 'action_product': product.tolist(),
            'policies': policy.tolist(), 'values': value.tolist(), 'transition': transition.tolist(),
            'policy_logit_residual': policy_residual, 'bellman_residual': bellman_residual,
            'selection': 'root solver initialized at zero logits', 'initial_empty_total_value': float(value[:, 0].sum())}

def run_calibrated(spec):
    mode = spec['model']; options = spec['options']
    if mode == 'continuous_time_entry':
        args = [float(options[k]) for k in ('discount_rate', 'revision_rate', 'active_profit', 'competition', 'entry_cost', 'exit_cost')]
        change = float(options['entry_cost_change'])
        if (not np.isfinite([*args, change]).all() or args[0] <= 0 or args[1] <= 0
                or args[-1] < 0 or args[-2] < 0 or args[-2]+change < 0):
            raise ValueError('invalid continuous-time rates or switching costs')
        baseline = ct_game(*args)
        changed = args.copy(); changed[4] += change
        scenario = ct_game(*changed)
        stats = {'ct_bellman_residual': {'value': baseline['bellman_residual'], 'unit': 'utility per time unit'},
                 'ct_transition_probability_residual': {'value': baseline['transition_probability_residual'], 'unit': 'probability'},
                 'ct_baseline_value': {'value': baseline['initial_empty_total_value'], 'unit': 'utility'},
                 'ct_scenario_value': {'value': scenario['initial_empty_total_value'], 'unit': 'utility'}}
    elif mode == 'capacity_product_game':
        beta = float(options['discount_factor']); demand = np.asarray(options['product_margins'], dtype=float)
        competition = float(options['competition']); cost = float(options['investment_cost'])
        switching = float(options['product_switching_cost']); change = float(options['investment_cost_change'])
        if (demand.shape != (2,) or not np.isfinite([beta, *demand, competition, cost, switching, change]).all()
                or not 0 < beta < 1 or min(competition, cost, switching, cost+change) < 0):
            raise ValueError('invalid capacity-product parameters')
        baseline = capacity_game(beta, demand, competition, cost, switching)
        scenario = capacity_game(beta, demand, competition, cost+change, switching)
        stats = {'capacity_policy_residual': {'value': baseline['policy_logit_residual'], 'unit': 'log odds'},
                 'capacity_bellman_residual': {'value': baseline['bellman_residual'], 'unit': 'utility'},
                 'capacity_baseline_value': {'value': baseline['initial_empty_total_value'], 'unit': 'utility'},
                 'capacity_scenario_value': {'value': scenario['initial_empty_total_value'], 'unit': 'utility'}}
    else:
        raise ValueError('unsupported dynamic model')
    return {'model': mode, 'adopted': spec.get('adopted', {}), 'scenario': spec.get('scenario', {}),
            'options': options, 'transition': 'endogenous action-specific transition', 'engine': 'NumPy/SciPy',
            'statistics': stats, 'fullresults': {'baseline': baseline, 'scenario': scenario},
            'provenance': {'python': sys.version.split()[0], 'numpy': np.__version__, 'scipy': scipy.__version__,
                           'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}


def read_observations(data_spec, base, fields):
    """Read declared analysis-table columns and bind them to source bytes."""
    if not isinstance(data_spec, dict) or set(data_spec) != {'path', 'columns'}:
        raise ValueError('data requires path and columns')
    mapping = data_spec['columns']
    if not isinstance(mapping, dict) or set(mapping) != set(fields) or len(set(mapping.values())) != len(fields):
        raise ValueError('data columns must map each required field to a unique table column')
    path = Path(data_spec['path'])
    if not path.is_absolute():
        path = base / path
    frame = research_data.read_frame(path, columns=list(mapping.values()), string_columns=list(mapping.values()))
    if frame.empty or frame.isna().any().any():
        raise ValueError('observed data must contain complete declared fields')
    frame = frame.rename(columns={value: key for key, value in mapping.items()})
    for column in frame:
        frame[column] = frame[column].str.strip()
        if frame[column].eq('').any():
            raise ValueError('observed fields must be nonempty')
    rows = frame.to_dict(orient='records')
    with path.open('rb') as stream:
        sha256 = hashlib.file_digest(stream, 'sha256').hexdigest()
    return rows, {'path': str(path.resolve()), 'sha256': sha256,
                  'rows': len(rows), 'columns': mapping}


def integer_field(row, field):
    try:
        value = int(row[field])
    except (ValueError, TypeError):
        raise ValueError(f'{field} must be an integer') from None
    return value


def panel_data(data_spec, base, states, game=False):
    fields = ('id', 'period', 'state', 'action_1', 'action_2', 'next_state') if game else ('id', 'period', 'state', 'action', 'next_state')
    rows, provenance = read_observations(data_spec, base, fields)
    result = []
    for row in rows:
        identifier = row['id']; period = integer_field(row, 'period'); state = integer_field(row, 'state')
        next_state = integer_field(row, 'next_state')
        actions = [integer_field(row, f'action_{i}') for i in (1, 2)] if game else [integer_field(row, 'action')]
        if period < 0 or not 0 <= state < states or not 0 <= next_state < states or any(a not in (0, 1) for a in actions):
            raise ValueError('panel period, state or action outside the specified support')
        implied = 2*actions[0]+actions[1] if game else (0 if actions[0] else min(state+1, states-1))
        if next_state != implied:
            raise ValueError('observed next state violates the declared action-specific transition')
        result.append((identifier, period, state, *actions, next_state))
    result.sort(key=lambda x: (x[0], x[1]))
    seen = set(); previous = {}
    for row in result:
        key = (row[0], row[1])
        if key in seen:
            raise ValueError('panel id-period keys must be unique')
        seen.add(key)
        if row[0] in previous:
            old = previous[row[0]]
            if row[1] != old[1] + 1 or row[2] != old[-1]:
                raise ValueError('panel must have consecutive periods and consistent state transitions')
        previous[row[0]] = row
    identifiers = sorted({row[0] for row in result})
    provenance['fitted_ids_sha256'] = hashlib.sha256(json.dumps(identifiers, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    provenance['fitted_ids'] = identifiers
    index = {key: n for n, key in enumerate(identifiers)}
    return np.asarray([(index[row[0]], *row[1:]) for row in result], dtype=int), provenance


def adoption_data(data_spec, base):
    rows, provenance = read_observations(data_spec, base, ('state', 'price', 'adoptions', 'cohort_size'))
    output = []
    for row in rows:
        state = integer_field(row, 'state'); count = integer_field(row, 'adoptions'); size = integer_field(row, 'cohort_size')
        price = float(row['price'])
        if state < 0 or not np.isfinite(price) or price < 0 or size <= 0 or not 0 < count < size:
            raise ValueError('adoption states, prices and counts must be valid and shares interior')
        output.append((state, price, count, size))
    output.sort()
    if [row[0] for row in output] != list(range(len(output))):
        raise ValueError('adoption states must be unique and numbered consecutively from zero')
    ids = [str(row[0]) for row in output]
    provenance['fitted_ids'] = ids
    provenance['fitted_ids_sha256'] = hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()
    return np.asarray(output, dtype=float), provenance


def fit_observed_adoption(rows, transition, beta, heterogeneity, weights, price_change):
    price = rows[:, 1]; observed = rows[:, 2]/rows[:, 3]
    transition = np.asarray(transition, dtype=float); heterogeneity = np.asarray(heterogeneity, dtype=float)
    weights = np.asarray(weights, dtype=float); size = len(price)
    if (size < 3 or transition.shape != (size, size) or heterogeneity.shape != weights.shape or len(weights) < 1
            or not all(np.isfinite(a).all() for a in (price, transition, heterogeneity, weights))
            or not 0 < beta < 1 or (transition < 0).any() or not np.allclose(transition.sum(axis=1), 1)
            or (weights <= 0).any() or not np.isclose(weights.sum(), 1) or not np.isfinite(price_change)):
        raise ValueError('invalid dynamic adoption transition or type weights')
    def predicted(delta, prices=price):
        return dynamic_adoption(delta, prices, heterogeneity, weights, beta, transition)
    inversion = root(lambda delta: predicted(delta)[0]-observed, np.zeros(size), tol=1e-10)
    inversion_error = float(np.max(np.abs(predicted(inversion.x)[0]-observed)))
    if not inversion.success or inversion_error > 1e-9:
        raise ArithmeticError('dynamic share inversion did not converge')
    design = np.column_stack((np.ones(size), price))
    coefficients, _, rank, _ = np.linalg.lstsq(design, inversion.x, rcond=None)
    if rank != 2:
        raise ArithmeticError('dynamic price slope is not identified by price variation')
    fitted = predicted(design@coefficients)
    scenario_price = price+price_change
    if (scenario_price < 0).any():
        raise ValueError('changed prices must be nonnegative')
    changed_delta = coefficients[0]+coefficients[1]*scenario_price
    changed = dynamic_adoption(changed_delta, scenario_price, heterogeneity, weights, beta, transition)
    return {'observed_shares': observed.tolist(), 'observed_counts': rows[:, 2].astype(int).tolist(),
            'cohort_sizes': rows[:, 3].astype(int).tolist(), 'prices': price.tolist(),
            'mean_utility': inversion.x.tolist(), 'linear_coefficients': coefficients.tolist(),
            'linear_residuals': (inversion.x-design@coefficients).tolist(), 'linear_design_rank': int(rank),
            'inversion_residual': inversion_error,
            'baseline': {'shares': fitted[0].tolist(), 'values': fitted[1].tolist(), 'policy': fitted[2].tolist(),
                         'bellman_residual': fitted[3]},
            'scenario': {'prices': scenario_price.tolist(), 'shares': changed[0].tolist(), 'values': changed[1].tolist(),
                         'policy': changed[2].tolist(), 'bellman_residual': changed[3]},
            'baseline_initial_consumer_value': float(weights @ fitted[1][:, 0]),
            'scenario_initial_consumer_value': float(weights @ changed[1][:, 0])}


def opportunity_panel(data_spec, base):
    fields = ('id', 'period', 'state', 'firm', 'action', 'next_state')
    rows, provenance = read_observations(data_spec, base, fields)
    values = []
    for row in rows:
        identifier = row['id']; period = integer_field(row, 'period'); state = integer_field(row, 'state')
        firm = integer_field(row, 'firm'); action = integer_field(row, 'action'); next_state = integer_field(row, 'next_state')
        if period < 0 or not 0 <= state < 4 or firm not in (0, 1) or action not in (0, 1) or not 0 <= next_state < 4:
            raise ValueError('invalid continuous-time opportunity record')
        pair = list(_STATES[state]); pair[firm] = (1-pair[firm]) if action else pair[firm]
        if next_state != _STATES.index(tuple(pair)):
            raise ValueError('opportunity next state violates the observed action')
        values.append((identifier, period, state, firm, action, next_state))
    values.sort(key=lambda row: (row[0], row[1])); previous = {}; seen = set()
    for row in values:
        key = (row[0], row[1])
        if key in seen:
            raise ValueError('opportunity id-period keys must be unique')
        seen.add(key)
        if row[0] in previous:
            prior = previous[row[0]]
            if row[1] != prior[1]+1 or row[2] != prior[-1]:
                raise ValueError('opportunity records must have consecutive periods and consistent states')
        previous[row[0]] = row
    identifiers = sorted(previous)
    provenance['fitted_ids'] = identifiers
    provenance['fitted_ids_sha256'] = hashlib.sha256(json.dumps(identifiers, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    index = {name: i for i, name in enumerate(identifiers)}
    return np.asarray([(index[row[0]], *row[1:]) for row in values], dtype=int), provenance


def estimate_ct_entry(data, rho, rate, profit, competition, exit_cost, bounds, change):
    if (len(bounds) != 2 or not np.isfinite([rho, rate, profit, competition, exit_cost, *bounds, change]).all()
            or rho <= 0 or rate <= 0 or exit_cost < 0 or not 0 <= bounds[0] < bounds[1]):
        raise ValueError('invalid continuous-time estimation parameters')
    counts = np.zeros((2, 4, 2))
    np.add.at(counts, (data[:, 3], data[:, 2], data[:, 4]), 1)
    def game(cost):
        return ct_game(rho, rate, profit, competition, cost, exit_cost)
    def objective(cost):
        p = np.asarray(game(cost)['toggle_probabilities'])
        return float(-np.sum(counts[:, :, 1]*np.log(p)+counts[:, :, 0]*np.log1p(-p)))
    fit = minimize_scalar(objective, bounds=tuple(bounds), method='bounded', options={'xatol': 1e-8})
    if not fit.success or not np.isfinite(fit.fun):
        raise ArithmeticError('continuous-time choice likelihood did not converge')
    cost = float(fit.x)
    if cost+change < 0:
        raise ValueError('scenario entry cost must be nonnegative')
    step = 1e-4*max(1., abs(cost)); plus = np.asarray(game(cost+step)['toggle_probabilities'])
    minus = np.asarray(game(cost-step)['toggle_probabilities']); p = np.asarray(game(cost)['toggle_probabilities'])
    derivative = (plus-minus)/(2*step)
    information = float(np.sum(counts.sum(axis=2)*derivative**2/(p*(1-p))))
    if information <= 1e-10:
        raise ArithmeticError('entry cost lacks local choice-probability identification')
    score = float((objective(cost+step)-objective(cost-step))/(2*step)/len(data))
    return {'estimate': {'entry_cost': cost, 'negative_log_likelihood': float(fit.fun), 'observations': len(data),
                         'choice_information': information, 'choice_response_rank': 1, 'likelihood_score_per_observation': score,
                         'jacobian_step': step, 'bounds': bounds, 'counts': counts.tolist(), 'iterations': int(fit.nfev)},
            'baseline': game(cost), 'scenario': game(cost+change)}


def capacity_panel(data_spec, base):
    fields = ('id', 'period', 'state', 'action_1', 'action_2', 'next_state')
    rows, provenance = read_observations(data_spec, base, fields)
    values = []
    for row in rows:
        identifier = row['id']; period = integer_field(row, 'period'); state = integer_field(row, 'state')
        action_1 = integer_field(row, 'action_1'); action_2 = integer_field(row, 'action_2')
        next_state = integer_field(row, 'next_state')
        if period < 0 or not 0 <= state < 16 or action_1 not in range(4) or action_2 not in range(4):
            raise ValueError('invalid capacity-product panel record')
        if next_state != 4*action_1+action_2:
            raise ValueError('capacity-product next state violates the joint actions')
        values.append((identifier, period, state, action_1, action_2, next_state))
    values.sort(key=lambda row: (row[0], row[1])); previous = {}; seen = set()
    for row in values:
        key = (row[0], row[1])
        if key in seen:
            raise ValueError('capacity-product id-period keys must be unique')
        seen.add(key)
        if row[0] in previous:
            prior = previous[row[0]]
            if row[1] != prior[1]+1 or row[2] != prior[-1]:
                raise ValueError('capacity-product panel requires consecutive periods and consistent states')
        previous[row[0]] = row
    identifiers = sorted(previous)
    provenance['fitted_ids'] = identifiers
    provenance['fitted_ids_sha256'] = hashlib.sha256(json.dumps(identifiers, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    index = {name: i for i, name in enumerate(identifiers)}
    return np.asarray([(index[row[0]], *row[1:]) for row in values], dtype=int), provenance


def estimate_capacity_game(data, beta, demand, competition, switching, bounds, change):
    demand = np.asarray(demand, dtype=float)
    if (demand.shape != (2,) or len(bounds) != 2 or not np.isfinite([beta, *demand, competition, switching, *bounds, change]).all()
            or not 0 < beta < 1 or competition < 0 or switching < 0 or not 0 <= bounds[0] < bounds[1]):
        raise ValueError('invalid capacity-product estimation parameters')
    counts = np.zeros((2, 16, 4))
    for i in range(2):
        np.add.at(counts[i], (data[:, 2], data[:, 3+i]), 1)
    def game(cost):
        return capacity_game(beta, demand, competition, cost, switching)
    def objective(cost):
        p = np.asarray(game(cost)['policies'])
        return -float(np.sum(counts*np.log(p)))
    fit = minimize_scalar(objective, bounds=tuple(bounds), method='bounded', options={'xatol': 1e-7})
    if not fit.success or not np.isfinite(fit.fun):
        raise ArithmeticError('capacity-product choice likelihood did not converge')
    cost = float(fit.x)
    if cost+change < 0:
        raise ValueError('scenario investment cost must be nonnegative')
    baseline = game(cost); p = np.asarray(baseline['policies']); step = 1e-4*max(1., abs(cost))
    derivative = (np.asarray(game(cost+step)['policies'])-np.asarray(game(cost-step)['policies']))/(2*step)
    information = float(np.sum(counts.sum(axis=2)[:, :, None]*derivative**2/p))
    if information <= 1e-10:
        raise ArithmeticError('investment cost lacks local choice-probability identification')
    score = float((objective(cost+step)-objective(cost-step))/(2*step)/len(data))
    return {'estimate': {'investment_cost': cost, 'negative_log_likelihood': float(fit.fun), 'observations': len(data),
                         'choice_information': information, 'choice_response_rank': 1, 'likelihood_score_per_observation': score,
                         'jacobian_step': step, 'bounds': bounds, 'counts': counts.tolist(), 'iterations': int(fit.nfev)},
            'baseline': baseline, 'scenario': game(cost+change)}


def replacement_displays(result):
    """Expose saved replacement estimates, policy curves and value comparisons."""
    contract = {'model_contract': 'MC-replacement-ddc', 'unit': 'see row-specific unit'}
    parameter_rows = []
    for estimator in ('nfxp', 'mpec', 'ccp', 'smm'):
        if estimator not in result:
            continue
        for i, (parameter, unit) in enumerate((('maintenance_cost', 'utility per mileage state'),
                                               ('replacement_cost', 'utility'))):
            parameter_rows.append({'estimator': estimator, 'parameter': parameter,
                                   'value': result[estimator]['parameters'][i], 'unit': unit})
    selected = 'mpec' if 'mpec' in result else 'nfxp'
    diagnostic_rows = [
        {'diagnostic': selected+'_negative_log_likelihood', 'value': result[selected]['negative_log_likelihood'], 'unit': 'negative log likelihood'},
        {'diagnostic': 'official_likelihood_abs_difference', 'value': result[selected]['original_likelihood_abs_difference'], 'unit': 'log likelihood'},
    ]
    if 'ccp' in result:
        diagnostic_rows.extend([
            {'diagnostic': 'ccp_rank', 'value': result['ccp']['rank'], 'unit': 'rank'},
            {'diagnostic': 'ccp_inversion_max_residual', 'value': result['ccp']['inversion_max_residual'], 'unit': 'utility'}])
    policy_rows, value_rows = [], []
    for scenario in ('baseline', 'scenario'):
        solution = result[scenario]
        diagnostic_rows.append({'diagnostic': scenario+'_bellman_residual',
                                'value': solution['bellman_residual'], 'unit': 'utility'})
        for state, (policy, value) in enumerate(zip(solution['policy'], solution['value'])):
            policy_rows.append({'scenario': scenario, 'state': state, 'value': policy[1], 'unit': 'replacement probability'})
            value_rows.append({'scenario': scenario, 'state': state, 'value': value, 'unit': 'discounted utility'})
    return {
        'parameters': {'kind': 'table', 'title': 'Replacement costs by estimator', 'rows': parameter_rows,
                       'columns': [{'key': key, 'label': label, 'unit': ''} for key, label in
                                   (('estimator', 'Estimator'), ('parameter', 'Parameter'), ('value', 'Estimate'), ('unit', 'Unit'))],
                       'metadata': {**contract, 'report_role': 'parameters'},
                       'display': {'plot_type': 'table', 'formats': {'value': '.4f'}}},
        'model_fit': {'kind': 'table', 'title': 'Choice fit and Bellman diagnostics', 'rows': diagnostic_rows,
                      'columns': [{'key': key, 'label': label, 'unit': ''} for key, label in
                                  (('diagnostic', 'Diagnostic'), ('value', 'Value'), ('unit', 'Unit'))],
                      'metadata': {**contract, 'report_role': 'model_fit'}, 'display': {'plot_type': 'table'}},
        'replacement_policy': {'kind': 'structural', 'title': 'Replacement policy by mileage state', 'rows': policy_rows,
                               'columns': [{'key': key, 'label': label, 'unit': unit} for key, label, unit in
                                           (('scenario', 'Scenario', ''), ('state', 'Mileage state', 'state'),
                                            ('value', 'Replacement probability', 'probability'), ('unit', 'Unit', ''))],
                               'metadata': {**contract, 'report_role': 'counterfactual', 'unit': 'replacement probability',
                                            'estimand': 'Optimal replacement probability conditional on mileage state'},
                               'display': {'plot_type': 'line', 'x': 'state', 'y': 'value', 'series': 'scenario'}},
        'state_values': {'kind': 'counterfactual', 'title': 'Expected discounted value by mileage state', 'rows': value_rows,
                         'columns': [{'key': key, 'label': label, 'unit': unit} for key, label, unit in
                                     (('scenario', 'Scenario', ''), ('state', 'Mileage state', 'state'),
                                      ('value', 'Expected discounted value', 'utility'), ('unit', 'Unit', ''))],
                         'metadata': {**contract, 'report_role': 'counterfactual', 'unit': 'discounted utility',
                                      'population': 'Initial state-specific agents; no cross-state population aggregation',
                                      'value_definition': 'Inclusive expected discounted utility under unit-scale EV1 shocks with Euler constant normalized to zero'},
                         'display': {'plot_type': 'line', 'x': 'state', 'y': 'value', 'series': 'scenario'}}}


def observed_run(spec, base):
    if 'data_record' in spec:
        data_spec = spec.get('data', {})
        if not isinstance(data_spec, dict):
            raise ValueError('dynamic data requires a path and its column mapping')
        reference = {key: value for key, value in spec.items() if key != 'data'}
        if 'path' in data_spec:
            reference['data'] = data_spec['path']
        clean, record, construction = research_data.bind_data_record(reference, base)
        clean['data'] = {**data_spec, 'path': clean['data']}
        result = observed_run(clean, base)
        provenance = result['provenance']
        source = provenance.get('data', provenance.get('sources', {}).get('data'))
        if source is None or source['sha256'] != record['table']['sha256']:
            raise ValueError('Dynamic result source differs from the constructed table')
        row_id = record['sample']['row_id']
        if result['model'] == 'finite_horizon_choice':
            observed = result['fit']['observed_data']
            result['sample'] = {'row_id': row_id, 'included_ids_available': False,
                'input_key_columns': observed['index_names'], 'input_sample_keys': observed['index'],
                'input_observations': source['rows']}
        else:
            identities = research_data.read_frame(source['path'], columns=[row_id],
                                                   string_columns=[row_id])[row_id]
            if identities.isna().any():
                raise ValueError('Constructed row identities must be complete')
            included = identities.tolist()
            if result['model'] == 'replacement' and result['options'].get('replacement_timing') == 'reset_then_usage':
                mapping = source['columns']
                keys = research_data.read_frame(source['path'], columns=[mapping['id'], mapping['period']])
                rows_by_key = dict(zip(keys.itertuples(index=False, name=None), included))
                choice_keys = [tuple(key) for key in source['choice_sample_keys']]
                if len(rows_by_key) != len(included) or any(key not in rows_by_key for key in choice_keys):
                    raise ValueError('Native choice keys differ from the constructed row identities')
                included = [rows_by_key[key] for key in choice_keys]
            result['sample'] = {'row_id': row_id, 'included_ids': included, 'observations': len(included)}
        return research_data.attach_data_record(result, record, construction)
    if spec['model'] == 'finite_horizon_choice':
        return respy_run(spec, base)
    if spec['model'] == 'replacement' and spec['options'].get('replacement_timing', 'reset_to_zero') not in ('reset_to_zero', 'reset_then_usage'):
        raise ValueError('replacement_timing must be reset_to_zero or reset_then_usage')
    if spec['model'] == 'replacement' and spec['options'].get('replacement_timing') == 'reset_then_usage':
        return ruspy_native_run(spec, base)
    mode = spec['model']; options = spec['options']
    if mode == 'capacity_product_game' and 'data' in spec:
        data, source = capacity_panel(spec['data'], base)
        result = estimate_capacity_game(data, float(options['discount_factor']), options['product_margins'],
                    float(options['competition']), float(options['product_switching_cost']),
                    options['investment_cost_bounds'], float(options['investment_cost_change']))
        stats = {'capacity_investment_cost': {'value': result['estimate']['investment_cost'], 'unit': 'utility'},
                 'capacity_policy_residual': {'value': result['baseline']['policy_logit_residual'], 'unit': 'log odds'},
                 'capacity_bellman_residual': {'value': result['baseline']['bellman_residual'], 'unit': 'utility'}}
        return {'model': mode, 'adopted': spec.get('adopted', {}), 'scenario': spec.get('scenario', {}),
                'options': options, 'transition': 'deterministic joint-action product and capacity state',
                'engine': 'NumPy/SciPy', 'statistics': stats, 'fullresults': result,
                'provenance': {'data': source, 'python': sys.version.split()[0], 'numpy': np.__version__,
                               'scipy': scipy.__version__, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    if mode == 'continuous_time_entry' and 'data' in spec:
        data, source = opportunity_panel(spec['data'], base)
        args = [float(options[k]) for k in ('discount_rate', 'revision_rate', 'active_profit', 'competition', 'exit_cost')]
        result = estimate_ct_entry(data, *args, options['entry_cost_bounds'], float(options['entry_cost_change']))
        stats = {'ct_entry_cost': {'value': result['estimate']['entry_cost'], 'unit': 'utility'},
                 'ct_bellman_residual': {'value': result['baseline']['bellman_residual'], 'unit': 'utility per time unit'},
                 'ct_transition_probability_residual': {'value': result['baseline']['transition_probability_residual'], 'unit': 'probability'}}
        return {'model': mode, 'adopted': spec.get('adopted', {}), 'scenario': spec.get('scenario', {}),
                'options': options, 'transition': 'independent Poisson firm opportunities', 'engine': 'NumPy/SciPy',
                'statistics': stats, 'fullresults': result,
                'provenance': {'data': source, 'python': sys.version.split()[0], 'numpy': np.__version__,
                               'scipy': scipy.__version__, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    if mode not in ('replacement', 'latent_replacement', 'discrete_entry', 'dynamic_adoption_blp'):
        if 'data' in spec:
            raise ValueError('calibrated model does not accept observed data')
        return run_calibrated(spec)
    beta = float(options['discount_factor'])
    if not 0 < beta < 1:
        raise ValueError('discount factor must be in (0,1)')
    if mode in ('replacement', 'latent_replacement'):
        n = int(options['states'])
        if n < 3:
            raise ValueError('replacement requires at least three states')
        data, source = panel_data(spec['data'], base, n)
        change = float(options['replacement_cost_change'])
        if not np.isfinite(change):
            raise ValueError('replacement cost change must be finite')
        if mode == 'replacement':
            start = np.asarray(options['initial_costs'], dtype=float)
            horizon = int(options['finite_horizon'])
            if start.shape != (2,) or not np.isfinite(start).all() or (start <= 0).any() or horizon < 1:
                raise ValueError('positive initial costs and finite horizon required')
            method = options.get('estimation_method', 'nfxp')
            if method not in ('nfxp', 'mpec'):
                raise ValueError('replacement estimation_method must be nfxp or mpec')
            estimate = (fit_replacement_mpec(data, beta, n, start, options.get('mpec', {}))
                        if method == 'mpec' else fit_replacement(data, beta, n, start))
            ccp = ccp_fit(data, beta, n)
            costs = np.asarray(estimate['parameters'])
            if costs[1]+change <= 0:
                raise ValueError('counterfactual replacement cost must be positive')
            baseline = replacement(beta, costs, n)
            scenario = replacement(beta, [costs[0], costs[1]+change], n)
            finite = replacement(beta, costs, n, horizon)
            def clean(m):
                return {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in m.items()}
            result = {'baseline': clean(baseline), 'scenario': clean(scenario), 'finite_horizon': clean(finite),
                      method: estimate, 'ccp': ccp}
            stats = {'replacement_bellman_residual': {'value': baseline['bellman_residual'], 'unit': 'utility'},
                     'replacement_cost_'+method: {'value': estimate['parameters'][1], 'unit': 'utility'},
                     'replacement_cost_ccp': {'value': ccp['parameters'][1], 'unit': 'utility'}}
            if 'smm' in options:
                smm = fit_replacement_smm(data, beta, n, options['smm'], source['sha256'])
                smm_costs = smm['parameters']
                if smm_costs[1]+change <= 0:
                    raise ValueError('SMM counterfactual replacement cost must be positive')
                result['smm'] = smm
                result['smm_baseline'] = clean(replacement(beta, smm_costs, n))
                result['smm_scenario'] = clean(replacement(beta, [smm_costs[0], smm_costs[1]+change], n))
                stats['replacement_cost_smm'] = {'value': smm_costs[1], 'unit': 'utility'}
        else:
            maintenance = float(options['maintenance_cost']); initial = np.asarray(options['initial_costs'], dtype=float)
            bounds = options['estimation_bounds']; initial_share = float(options['initial_type_one_share'])
            if (initial.shape != (2,) or len(bounds) != 2 or
                    not np.isfinite([maintenance, *initial, *bounds, initial_share]).all() or maintenance <= 0
                    or bounds[0] <= 0 or not bounds[0] <= initial[0] < initial[1] <= bounds[1]
                    or not 0 < initial_share < 1):
                raise ValueError('invalid latent-type starting parameters or bounds')
            ids, counts = np.unique(data[:, 0], return_counts=True)
            if len(set(counts)) != 1 or not all(np.array_equal(data[data[:, 0] == i, 1], data[data[:, 0] == ids[0], 1]) for i in ids):
                raise ValueError('latent model requires a balanced panel with common period indices')
            states = np.stack([data[data[:, 0] == i, 2] for i in ids]); actions = np.stack([data[data[:, 0] == i, 3] for i in ids])
            fit = latent_em(states, actions, beta, maintenance, n, initial, initial_share, bounds)
            costs = np.asarray(fit['replacement_costs'])
            if np.any(costs+change <= 0):
                raise ValueError('counterfactual type costs must be positive')
            weights = np.array([fit['type_one_share'], 1-fit['type_one_share']])
            values = [replacement(beta, [maintenance, cost], n)['value'][0] for cost in costs]
            changed = [replacement(beta, [maintenance, cost+change], n)['value'][0] for cost in costs]
            result = {'estimate': fit, 'baseline_initial_value': float(weights @ values),
                      'scenario_initial_value': float(weights @ changed)}
            stats = {'latent_type_one_cost': {'value': costs[0], 'unit': 'utility'},
                     'latent_type_two_cost': {'value': costs[1], 'unit': 'utility'},
                     'latent_type_one_share': {'value': fit['type_one_share'], 'unit': 'probability'}}
    elif mode == 'discrete_entry':
        data, source = panel_data(spec['data'], base, 4, game=True)
        profit = float(options['active_profit']); competition = float(options['competition'])
        bounds = options['estimation_bounds']; change = float(options['entry_cost_change'])
        if (len(bounds) != 2 or not np.isfinite([profit, competition, *bounds, change]).all()
                or not 0 <= bounds[0] < bounds[1]):
            raise ValueError('invalid game parameter bounds')
        estimate = bbl_estimate(data, beta, profit, competition, bounds)
        sequential = {method: sequential_estimate(data, beta, profit, competition, bounds, method) for method in ('npl','epl','slc')}
        cost = sequential['epl']['entry_cost']
        if cost+change < 0:
            raise ValueError('counterfactual entry cost must be nonnegative')
        baseline = discrete_game(beta, profit, competition, cost)
        changed = discrete_game(beta, profit, competition, cost+change)
        def clean(m):
            return {k: v.tolist() if isinstance(v, np.ndarray) else v for k,v in m.items()}
        result = {'baseline': clean(baseline), 'scenario': clean(changed), 'bbl': estimate, 'sequential': sequential}
        stats = {'game_entry_cost_epl': {'value': cost, 'unit': 'utility'},
                 'game_policy_residual': {'value': baseline['policy_residual'], 'unit': 'probability'}}
    else:
        data, source = adoption_data(spec['data'], base)
        result = fit_observed_adoption(data, options['transition'], beta, options['price_taste_types'],
                                       options['type_weights'], float(options['price_change']))
        stats = {'dynamic_blp_price_coefficient': {'value': result['linear_coefficients'][1], 'unit': 'utility per price unit'},
                 'dynamic_blp_share_inversion_residual': {'value': result['inversion_residual'], 'unit': 'probability'}}
    output = {'model': mode, 'adopted': spec.get('adopted', {}), 'scenario': spec.get('scenario', {}), 'options': options,
            'transition': 'declared in specification', 'engine': 'NumPy/SciPy', 'statistics': stats, 'fullresults': result,
            'provenance': {'data': source, 'python': sys.version.split()[0], 'numpy': np.__version__,
                           'scipy': scipy.__version__, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    if mode == 'replacement':
        method = options.get('estimation_method', 'nfxp')
        output['engine'] = result[method]['engine']+'; NumPy/SciPy CCP'
        output['displays'] = replacement_displays(result)
        output.update(computation={'requested_operation': 'estimate',
            'operations_executed': ['estimate', 'solve', 'counterfactual'], 'parameter_operation': 'estimate',
            'estimation_method': method},
            parameter_definition={'structural_order': ['maintenance_cost', 'replacement_cost_reset_to_zero'],
                'native_ruspy_order': ['replacement_cost_official', 'maintenance_cost'],
                'native_expected_values': 'EV(s)=V(min(s+1,S-1)) under the same reset-to-zero structural value',
                'replacement_cost_mapping': 'R_official=R+beta*(V(1)-V(0))',
                'mpec_variables': 'EV and official costs are optimization variables; reported costs use the structural order'},
            normalization='Unit-scale EV1 action shocks; Euler constant normalized to zero',
            equilibrium_selection='Unique discounted single-agent Bellman fixed point',
            welfare_definition='State-specific expected discounted utility including normalized action shocks',
            horizon={'baseline': 'infinite', 'finite_comparison': int(options['finite_horizon'])},
            solver='Official ruspy '+method.upper()+'; scipy.optimize.root for original reset Bellman equations')
    return output


def local_checks():
    source = Path(__file__).resolve()
    candidates = [source.parent / 'local_checks.py', source.parent / 'LOCAL_CHECKS.py']
    candidates.extend(p / 'harness' / 'local_checks.py' for p in source.parents)
    checks_path = next((p for p in candidates if p.is_file()), None)
    if checks_path is None:
        raise FileNotFoundError('local_checks.py required for atomic publication')
    module_spec = importlib.util.spec_from_file_location('dynamic_local_checks', checks_path)
    checks = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(checks)
    return checks


def write_json(path, value):
    payload = json.dumps(value, indent=2, allow_nan=False) + '\n'
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name + '.')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(payload)
        local_checks().replace_path(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    solve = sub.add_parser('run'); solve.add_argument('spec', type=Path); solve.add_argument('--output', '-o', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.spec.resolve() == args.output.resolve():
            raise ValueError('output must differ from the specification path')
        raw = args.spec.read_bytes(); specification = json.loads(raw)
        if not isinstance(specification, dict):
            raise TypeError('specification must be an object')
        protected = {args.spec.resolve()}
        for key, field in (('params', 'path'), ('moments', 'module'), ('data_record', 'path')):
            reference = specification.get(key)
            if isinstance(reference, dict) and isinstance(reference.get(field), str):
                protected.add((args.spec.resolve().parent / reference[field]).resolve())
        if isinstance(specification.get('fit_path'), str):
            protected.add((args.spec.resolve().parent / specification['fit_path']).resolve())
        if args.output.resolve() in protected:
            raise ValueError('output must differ from parameter, moment, fit and construction inputs')
        if isinstance(specification.get('data'), dict) and 'path' in specification['data']:
            input_path = Path(specification['data']['path'])
            if not input_path.is_absolute():
                input_path = args.spec.resolve().parent / input_path
            if input_path.resolve() == args.output.resolve():
                raise ValueError('output must differ from observed data path')
        result = observed_run(specification, args.spec.resolve().parent)
        if 'data_construction' in result:
            construction = result['data_construction']
            record_path = Path(construction['record']['path'])
            table_path = Path(construction['table']['path'])
            if not table_path.is_absolute():
                table_path = record_path.parent / table_path
            if args.output.resolve() in {record_path.resolve(), table_path.resolve()}:
                raise ValueError('output must differ from the construction record and observed data paths')
        result['provenance']['spec_sha256'] = hashlib.sha256(raw).hexdigest()
        write_json(args.output, result)
    except (ValueError, TypeError, KeyError, OSError, ArithmeticError) as exc:
        parser.exit(2, 'error: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
