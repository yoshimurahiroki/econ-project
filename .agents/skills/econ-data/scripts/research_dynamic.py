#!/usr/bin/env python3
"""Solve and estimate specified finite-state dynamic choices and games.

Use ``run SPEC --output RESULT`` or ``case --output NEW_DIRECTORY``.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import scipy
from scipy.optimize import minimize, minimize_scalar, root
from scipy.special import expit, logsumexp, softmax
from scipy.sparse import csr_matrix, eye
from scipy.linalg import expm


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
    iterations = 0
    limit = horizon if horizon is not None else 20000
    for iterations in range(1, limit + 1):
        q = flow + beta * np.einsum('ask,k->as', p, v)
        new = logsumexp(q, axis=0)
        policy = np.exp(q - new)
        history.append((new.copy(), policy.copy()))
        error = np.max(np.abs(new - v))
        v = new
        if horizon is None and error < 1e-12:
            break
    if horizon is None and error >= 1e-12:
        raise ArithmeticError('replacement Bellman iteration failed')
    q_check = flow + beta * np.einsum('ask,k->as', p, v)
    if horizon is None:
        bellman = float(np.max(np.abs(v - logsumexp(q_check, axis=0))))
    else:
        previous = np.zeros(n)
        errors = []
        for stage_value, _ in history:
            rhs = logsumexp(flow + beta * np.einsum('ask,k->as', p, previous), axis=0)
            errors.append(float(np.max(np.abs(stage_value - rhs))))
            previous = stage_value
        bellman = max(errors)
    return {'value': v, 'policy': policy.T, 'transition': p, 'flow': flow,
            'iterations': iterations, 'bellman_residual': bellman,
            'finite_stages_remaining': [{'value': v0.tolist(), 'policy': p0.T.tolist()} for v0, p0 in history] if horizon else None}


def simulate_replacement(model, households, periods, seed):
    rng = np.random.default_rng(seed)
    data = []
    for individual in range(households):
        s = 0
        for t in range(periods):
            a = int(rng.random() < model['policy'][s, 1])
            sp = int(np.argmax(model['transition'][a, s]))
            data.append((individual, t, s, a, sp))
            s = sp
    return np.asarray(data, dtype=int)


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
    jacobian = np.empty((n+1, 2)); derivative_steps = []
    for j in range(2):
        step = 1e-5*max(1., abs(fit.x[j])); derivative_steps.append(step)
        change = np.zeros(2); change[j] = step
        jacobian[:, j] = (expected_moments(fit.x+change)-expected_moments(fit.x-change))/(2*step)
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
    generator = csr_matrix(q)
    uniform_rate = float(max(-q.diagonal()))
    trans = eye(4, format='csr') + generator / uniform_rate
    # Sum Poisson mixture for a one-unit interval.
    term = eye(4, format='csr'); total = term * math.exp(-uniform_rate)
    weight = math.exp(-uniform_rate)
    for k in range(1, 200):
        term = term @ trans
        weight *= uniform_rate / k
        total = total + weight * term
        if weight < 1e-16:
            break
    exact = expm(q)
    uerr = float(np.max(np.abs(total.toarray() - exact)))
    if uerr > 1e-10:
        raise ArithmeticError('uniformization does not agree with matrix exponential')
    policy_error = max(float(np.max(np.abs(policies[i] - expit(v[i, toggles[i]] - v[i] - costs[i])))) for i in range(2))
    return {'states': states, 'values': v.tolist(), 'toggle_probabilities': policies.tolist(),
            'selection': 'root solver initialized at zero values', 'policy_residual': policy_error,
            'generator': q.tolist(), 'one_unit_transition': total.toarray().tolist(),
            'uniformization_rate': uniform_rate, 'bellman_residual': resid,
            'generator_row_residual': float(np.max(np.abs(q.sum(axis=1)))), 'uniformization_error': uerr,
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
        step = 1e-5
        columns = []
        for index in range(len(x)):
            h = np.zeros_like(x); h[index] = step
            columns.append((residual(x+h, theta)-residual(x-h, theta))/(2*step))
        return np.column_stack(columns)
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


def simulate_game(policies, markets, periods, seed):
    rng = np.random.default_rng(seed); observations = []
    for market in range(markets):
        si = 0
        for period in range(periods):
            action = tuple(int(rng.random() < policies[i, si]) for i in range(2))
            observations.append((market, period, si, action[0], action[1]))
            si = _STATES.index(action)
    return np.asarray(observations, dtype=int)


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


def simulate_latent(beta, maintenance, costs, share, n, households, periods, seed):
    rng = np.random.default_rng(seed)
    models = [replacement(beta, [maintenance, cost], n) for cost in costs]
    types = (rng.random(households) >= share).astype(int)
    states = np.zeros((households, periods), dtype=int)
    actions = np.zeros((households, periods), dtype=int)
    for t in range(periods):
        probability = np.array([models[types[j]]['policy'][states[j, t], 1] for j in range(households)])
        actions[:, t] = (rng.random(households) < probability).astype(int)
        if t+1 < periods:
            states[:, t+1] = np.where(actions[:, t] == 1, 0, np.minimum(states[:, t]+1, n-1))
    return states, actions, types


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
    for iteration in range(20000):
        continuation = beta * value @ transition.T
        updated = np.logaddexp(utility, continuation)
        error = float(np.max(np.abs(updated-value)))
        value = updated
        if error < 1e-12:
            break
    else:
        raise ArithmeticError('dynamic adoption Bellman iteration failed')
    continuation = beta * value @ transition.T
    policy = expit(utility-continuation)
    residual = float(np.max(np.abs(value-np.logaddexp(utility, continuation))))
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
                 'ct_uniformization_error': {'value': baseline['uniformization_error'], 'unit': 'probability'},
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
    """Read declared CSV columns and bind analysis to exact source bytes."""
    if not isinstance(data_spec, dict) or set(data_spec) != {'path', 'columns'}:
        raise ValueError('data requires path and columns')
    mapping = data_spec['columns']
    if not isinstance(mapping, dict) or set(mapping) != set(fields) or len(set(mapping.values())) != len(fields):
        raise ValueError('data columns must map each required field to a unique CSV column')
    path = Path(data_spec['path'])
    if not path.is_absolute():
        path = base / path
    raw = path.read_bytes()
    from io import StringIO
    reader = csv.DictReader(StringIO(raw.decode('utf-8-sig'), newline=''))
    if reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('CSV headers must be present and unique')
    if any(name not in reader.fieldnames for name in mapping.values()):
        raise ValueError('declared CSV column missing')
    rows = []
    for row in reader:
        if None in row or any(row[mapping[field]] is None or not row[mapping[field]].strip() for field in fields):
            raise ValueError('CSV row has missing or extra fields')
        rows.append({field: row[mapping[field]].strip() for field in fields})
    if not rows:
        raise ValueError('observed data must be nonempty')
    return rows, {'path': str(path.resolve()), 'sha256': hashlib.sha256(raw).hexdigest(),
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


def simulate_opportunities(model, markets, periods, seed):
    rng = np.random.default_rng(seed); policies = np.asarray(model['toggle_probabilities']); rows = []
    for market in range(markets):
        state = 0
        for period in range(periods):
            firm = int(rng.integers(2)); action = int(rng.random() < policies[firm, state])
            pair = list(_STATES[state]); pair[firm] = (1-pair[firm]) if action else pair[firm]
            next_state = _STATES.index(tuple(pair)); rows.append((market, period, state, firm, action, next_state)); state = next_state
    return rows


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


def simulate_capacity(model, markets, periods, seed):
    rng = np.random.default_rng(seed); policy = np.asarray(model['policies']); rows = []
    for market in range(markets):
        state = 0
        for period in range(periods):
            action = [int(rng.choice(4, p=policy[i, state])) for i in range(2)]
            next_state = 4*action[0]+action[1]
            rows.append((market, period, state, action[0], action[1], next_state)); state = next_state
    return rows


def replacement_displays(result):
    """Expose saved replacement estimates, policy curves and value comparisons."""
    contract = {'model_contract': 'MC-replacement-ddc', 'unit': 'see row-specific unit'}
    parameter_rows = []
    for estimator in ('nfxp', 'ccp', 'smm'):
        if estimator not in result:
            continue
        for i, (parameter, unit) in enumerate((('maintenance_cost', 'utility per mileage state'),
                                               ('replacement_cost', 'utility'))):
            parameter_rows.append({'estimator': estimator, 'parameter': parameter,
                                   'value': result[estimator]['parameters'][i], 'unit': unit})
    diagnostic_rows = [
        {'diagnostic': 'nfxp_negative_log_likelihood', 'value': result['nfxp']['negative_log_likelihood'], 'unit': 'negative log likelihood'},
        {'diagnostic': 'official_likelihood_abs_difference', 'value': result['nfxp']['original_likelihood_abs_difference'], 'unit': 'log likelihood'},
        {'diagnostic': 'ccp_rank', 'value': result['ccp']['rank'], 'unit': 'rank'},
        {'diagnostic': 'ccp_inversion_max_residual', 'value': result['ccp']['inversion_max_residual'], 'unit': 'utility'},
    ]
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
                 'ct_uniformization_error': {'value': result['baseline']['uniformization_error'], 'unit': 'probability'}}
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
            estimate = fit_replacement(data, beta, n, start)
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
                      'nfxp': estimate, 'ccp': ccp}
            stats = {'replacement_bellman_residual': {'value': baseline['bellman_residual'], 'unit': 'utility'},
                     'replacement_cost_nfxp': {'value': estimate['parameters'][1], 'unit': 'utility'},
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
        output['engine'] = result['nfxp']['engine']+'; NumPy/SciPy CCP'
        output['displays'] = replacement_displays(result)
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


def case(output):
    checks = local_checks(); output = output.absolute()
    if output.exists():
        raise FileExistsError(output)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.dynamic-') as temp:
        stage = Path(temp) / 'stage'; stage.mkdir()
        def csv_file(name, fields, rows):
            with (stage/name).open('w', newline='', encoding='utf-8') as stream:
                writer = csv.writer(stream); writer.writerow(fields); writer.writerows(rows)
        def observed(name, mode, options, columns):
            spec = {'model': mode, 'adopted': {'source': 'seeded independent synthetic case'},
                    'scenario': {}, 'options': options,
                    'data': {'path': name+'-data.csv', 'columns': {field: field for field in columns}}}
            write_json(stage/(name+'-spec.json'), spec)
            result = observed_run(spec, stage)
            result['provenance']['data']['path'] = str(output/(name+'-data.csv'))
            result['provenance']['spec_sha256'] = hashlib.sha256((stage/(name+'-spec.json')).read_bytes()).hexdigest()
            write_json(stage/(name+'-result.json'), result)
        panel_cols = ['id', 'period', 'state', 'action', 'next_state']
        m = replacement(.9, [.25, 2.], 5)
        panel = simulate_replacement(m, 250, 40, 20020)
        csv_file('replacement-data.csv', panel_cols, panel.tolist())
        observed('replacement', 'replacement', {'discount_factor': .9, 'states': 5, 'initial_costs': [.2, 1.6],
                 'finite_horizon': 8, 'replacement_cost_change': .5, 'smm': {'seed': 20422, 'replications': 32,
                 'initial_costs': [.2, 1.6], 'bounds': [[.01,1.5],[.05,5.]], 'tolerance': .0002}}, panel_cols)
        states, actions, _ = simulate_latent(.9, .25, [1., 3.], .45, 5, 700, 30, 20022)
        rows = [(i, t, int(states[i,t]), int(actions[i,t]),
                 0 if actions[i,t] else min(int(states[i,t])+1,4)) for i in range(700) for t in range(30)]
        csv_file('latent_replacement-data.csv', panel_cols, rows)
        observed('latent_replacement', 'latent_replacement', {'discount_factor': .9, 'states': 5,
                 'maintenance_cost': .25, 'initial_costs': [1.2, 2.7], 'initial_type_one_share': .5,
                 'estimation_bounds': [.1, 5.], 'replacement_cost_change': .3}, panel_cols)
        model = discrete_game(.8, 1., .4, .8); panel = simulate_game(model['policies'], 1000, 50, 20021)
        game_cols = ['id','period','state','action_1','action_2','next_state']
        rows = [(int(row[0]), int(row[1]), int(row[2]), int(row[3]), int(row[4]), int(2*row[3]+row[4])) for row in panel]
        csv_file('discrete_entry-data.csv', game_cols, rows)
        observed('discrete_entry', 'discrete_entry', {'discount_factor': .8, 'active_profit': 1., 'competition': .4,
                 'estimation_bounds': [0., 2.], 'entry_cost_change': .3}, game_cols)
        transition = [[.7,.2,.1],[.15,.7,.15],[.1,.2,.7]]; price = [1.,1.5,2.]
        share = dynamic_adoption([.9,.35,-.2], price, [-.25,.25], [.5,.5], .85, transition)[0]
        counts = np.random.default_rng(20023).binomial(100000, share)
        adoption_cols = ['state','price','adoptions','cohort_size']
        csv_file('dynamic_adoption_blp-data.csv', adoption_cols, [(i, price[i], int(counts[i]), 100000) for i in range(3)])
        observed('dynamic_adoption_blp', 'dynamic_adoption_blp', {'discount_factor': .85, 'transition': transition,
                 'price_taste_types': [-.25,.25], 'type_weights': [.5,.5], 'price_change': .3}, adoption_cols)
        ct_cols = ['id','period','state','firm','action','next_state']
        ct_data = simulate_opportunities(ct_game(.1,.6,1.,.4,.8,.2), 250, 50, 20025)
        csv_file('continuous_time_entry-data.csv', ct_cols, ct_data)
        observed('continuous_time_entry', 'continuous_time_entry', {'discount_rate': .1, 'revision_rate': .6,
                 'active_profit': 1., 'competition': .4, 'exit_cost': .2, 'entry_cost_bounds': [.05, 1.5],
                 'entry_cost_change': .3}, ct_cols)
        cap_cols = ['id','period','state','action_1','action_2','next_state']
        cap_data = simulate_capacity(capacity_game(.7, [2.,1.6], .15, .4, .3), 200, 25, 20024)
        csv_file('capacity_product_game-data.csv', cap_cols, cap_data)
        observed('capacity_product_game', 'capacity_product_game', {'discount_factor': .7, 'product_margins': [2.,1.6],
                 'competition': .15, 'product_switching_cost': .3, 'investment_cost_bounds': [.05,1.],
                 'investment_cost_change': .2}, cap_cols)
        write_json(stage/'synthetic-design.json', {'replacement': {'costs': [.25,2.], 'seed': 20020},
                   'latent_replacement': {'costs': [1.,3.], 'type_one_share': .45, 'seed': 20022},
                   'discrete_entry': {'entry_cost': .8, 'seed': 20021},
                   'dynamic_adoption_blp': {'mean_utilities': [.9,.35,-.2], 'seed': 20023},
                   'continuous_time_entry': {'entry_cost': .8, 'seed': 20025},
                   'capacity_product_game': {'investment_cost': .4, 'seed': 20024}})
        checks.atomic_publish(stage, output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    solve = sub.add_parser('run'); solve.add_argument('spec', type=Path); solve.add_argument('--output', '-o', required=True, type=Path)
    demo = sub.add_parser('case'); demo.add_argument('--output', '-o', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'case':
            case(args.output)
        else:
            if args.spec.resolve() == args.output.resolve():
                raise ValueError('output must differ from the specification path')
            raw = args.spec.read_bytes(); specification = json.loads(raw)
            if isinstance(specification.get('data'), dict) and 'path' in specification['data']:
                input_path = Path(specification['data']['path'])
                if not input_path.is_absolute():
                    input_path = args.spec.resolve().parent / input_path
                if input_path.resolve() == args.output.resolve():
                    raise ValueError('output must differ from observed data path')
            result = observed_run(specification, args.spec.resolve().parent)
            result['provenance']['spec_sha256'] = hashlib.sha256(raw).hexdigest()
            write_json(args.output, result)
    except (ValueError, TypeError, KeyError, OSError, ArithmeticError) as exc:
        parser.exit(2, 'error: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
