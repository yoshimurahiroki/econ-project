#!/usr/bin/env python3
"""Shared numerical calculations and an independent synthetic case for research DAGs."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

import numpy as np
import scipy
from scipy import integrate, optimize, sparse
from scipy.sparse.linalg import spsolve
from scipy.special import expit
from scipy.stats import qmc


def state_price_bounds(payoffs, prices, claim, tolerance=1e-9):
    """Price a finite-state claim and check the original primal and hedge equations.

    Rows of payoffs are possible states and columns are freely traded assets.
    The bounds use nonnegative state prices; for an unspanned claim the prices
    compatible with strictly positive state prices form the open interval.
    Numerical classification and residual checks use the supplied tolerance.
    """
    X = np.asarray(payoffs, dtype=float)
    p = np.asarray(prices, dtype=float)
    h = np.asarray(claim, dtype=float)
    if (X.ndim != 2 or not all(X.shape) or p.shape != (X.shape[1],)
            or h.shape != (X.shape[0],) or not all(np.isfinite(a).all() for a in (X, p, h))
            or not np.isscalar(tolerance) or not np.isfinite(tolerance) or tolerance <= 0):
        raise ValueError('payoffs, prices, claim and positive tolerance must have compatible finite dimensions')
    positive_columns = np.flatnonzero(np.all(X > 0, axis=0))
    if not len(positive_columns):
        raise ValueError('a traded asset must have strictly positive payoff in every state')
    anchor = positive_columns[0]
    q_scale = p[anchor] / X[:, anchor].sum()
    if not np.isfinite(q_scale) or q_scale <= 0:
        raise ValueError('the market has no strictly positive state prices')
    price_scale = np.maximum(np.abs(p), np.max(np.abs(X), axis=0)*q_scale)
    price_scale = np.where(price_scale > 0, price_scale, 1.)
    claim_scale = float(np.max(np.abs(h))) or 1.
    A = X.T*q_scale/price_scale[:, None]
    b = p/price_scale
    if not np.isfinite(A).all() or not np.isfinite(b).all():
        raise ValueError('inputs exceed supported finite numerical scaling')
    n = len(h)
    options = {'primal_feasibility_tolerance': 1e-10, 'dual_feasibility_tolerance': 1e-10}
    positive = optimize.linprog(np.r_[np.zeros(n), -1.],
                                A_ub=np.c_[-np.eye(n), np.ones(n)], b_ub=np.zeros(n),
                                A_eq=np.c_[A, np.zeros(len(p))], b_eq=b,
                                bounds=(0, None), method='highs', options=options)
    if positive.status == 2:
        raise ValueError('the market has no strictly positive state prices')
    if not positive.success:
        raise ArithmeticError(f'state-price feasibility LP failed: {positive.message}')
    q_positive = positive.x[:n]*q_scale
    if (positive.x[-1] <= tolerance or np.min(q_positive) <= tolerance*q_scale
            or np.max(np.abs(X.T @ q_positive-p)/price_scale) > tolerance):
        raise ValueError('the market has no strictly positive state prices at the requested tolerance')

    fits = []
    for sign in (1., -1.):
        fit = optimize.linprog(sign*h/claim_scale, A_eq=A, b_eq=b,
                               bounds=(0, None), method='highs', options=options)
        if not fit.success:
            raise ArithmeticError(f'state-price bound LP failed: {fit.message}')
        q = fit.x*q_scale
        hedge = sign*fit.eqlin.marginals*claim_scale*q_scale/price_scale
        fits.append((q, hedge))
    (q_lower, subhedge), (q_upper, superhedge) = fits
    lower, upper = float(h @ q_lower), float(h @ q_upper)
    pricing_residual = float(max(np.max(np.abs(X.T @ q-p)) for q in (q_positive, q_lower, q_upper)))
    pricing_relative = max(np.max(np.abs(X.T @ q-p)/price_scale) for q in (q_positive, q_lower, q_upper))
    state_price_violation = float(max(0., -np.min(q_lower), -np.min(q_upper)))
    sub_violation = float(max(0., np.max(X @ subhedge-h)))
    super_violation = float(max(0., np.max(h-X @ superhedge)))
    lower_gap = float(abs(p @ subhedge-lower))
    upper_gap = float(abs(p @ superhedge-upper))
    hedge_scale = max(claim_scale, float(np.max(np.abs(X @ subhedge))),
                      float(np.max(np.abs(X @ superhedge))))
    value_scale = max(claim_scale*q_scale, abs(lower), abs(upper),
                      abs(float(p @ subhedge)), abs(float(p @ superhedge)))
    if (not np.isfinite([pricing_residual, state_price_violation, sub_violation, super_violation,
                         lower_gap, upper_gap, hedge_scale, value_scale]).all()
            or pricing_relative > tolerance or state_price_violation > tolerance*q_scale
            or max(sub_violation, super_violation) > tolerance*hedge_scale
            or max(lower_gap, upper_gap) > tolerance*value_scale
            or lower-upper > tolerance*value_scale):
        raise ArithmeticError('state-price or hedge solution fails the original constraints')

    portfolio = np.linalg.lstsq(X, h, rcond=None)[0]
    replication_residual = float(np.max(np.abs(X @ portfolio-h)))
    if not np.isfinite(portfolio).all() or not np.isfinite(replication_residual):
        raise ArithmeticError('replication calculation is not finite')
    replicated = replication_residual <= tolerance*claim_scale
    if replicated:
        value = float(p @ portfolio)
        if max(abs(value-lower), abs(value-upper)) > tolerance*value_scale:
            raise ArithmeticError('replication price disagrees with the state-price bounds')
        lower = upper = value
    return {'lower_bound': lower, 'upper_bound': upper, 'positive_state_prices': q_positive.tolist(),
            'subhedge': subhedge.tolist(), 'superhedge': superhedge.tolist(),
            'replicating_portfolio': portfolio.tolist() if replicated else None,
            'price_set': 'singleton' if replicated else 'open_interval',
            'pricing_residual': pricing_residual, 'state_price_violation': state_price_violation,
            'subhedge_violation': sub_violation, 'superhedge_violation': super_violation,
            'lower_duality_gap': lower_gap, 'upper_duality_gap': upper_gap,
            'replication_residual': replication_residual}


def multitask_incentives(b, m, rho, a, vq, vqly):
    """Solve the agent's two-task quadratic problem and return both payoffs."""
    values = np.asarray([b, m, rho, a, vq, vqly], dtype=float)
    if not np.isfinite(values).all() or b < 0 or m < 0 or a < 0 or abs(rho) >= 1:
        raise ValueError('b, m and a must be finite and nonnegative; abs(rho) must be below one')
    denominator = 1-rho*rho
    candidates = [((b-rho*m)/denominator, (m-rho*b)/denominator),
                  (b, 0.), (0., m), (0., 0.)]
    tolerance = 1e-10*max(1., b, m)
    for x, y in candidates:
        if not np.isfinite([x, y]).all() or x < -tolerance or y < -tolerance:
            continue
        x, y = max(x, 0.), max(y, 0.)
        gradient = (b-x-rho*y, m-y-rho*x)
        residual = max(abs(g) if z > 0 else max(g, 0.) for z, g in zip((x, y), gradient))
        if residual <= tolerance:
            agent = a+b*x+m*y-.5*(x*x+y*y+2*rho*x*y)
            principal = vq*x+vqly*y-a-b*x
            if not np.isfinite([agent, principal]).all():
                raise ValueError('inputs produce non-finite payoffs')
            return {'x': float(x), 'y': float(y), 'agent_payoff': float(agent),
                    'principal_payoff': float(principal), 'kkt_residual': float(residual)}
    raise ArithmeticError('no finite candidate satisfies the original KKT conditions')


def decision_rights(B, b, kP, kA, alpha, beta, holder):
    """Solve simultaneous information efforts for the selected decision-right holder."""
    if not np.isfinite([B, b, kP, kA, alpha, beta]).all() or min(B, b, kP, kA) <= 0:
        raise ValueError('benefits and cost coefficients must be positive and finite')
    if not 0 <= alpha <= 1 or not 0 <= beta <= 1 or holder not in ('principal', 'agent'):
        raise ValueError('alignment must lie in [0, 1] and holder must be principal or agent')
    p, q = B/kP, b/kA
    alignment = max(alpha, beta)
    if (not np.isfinite([p, q]).all() or min(p, q) <= 0 or
            (alignment > 0 and math.log(p)+math.log(q)+math.log(alignment) >= 0)):
        raise ValueError('the supported model requires kP*kA > B*b*max(alpha,beta)')
    c, d = (alpha, 1.) if holder == 'principal' else (1., beta)
    for p_state, a_state in itertools.product(('zero', 'interior', 'one'), repeat=2):
        rows = [[1., p*c] if p_state == 'interior' else [1., 0.],
                [q*d, 1.] if a_state == 'interior' else [0., 1.]]
        rhs = [p if p_state == 'interior' else float(p_state == 'one'),
               q if a_state == 'interior' else float(a_state == 'one')]
        try:
            E, e = np.linalg.solve(rows, rhs)
        except np.linalg.LinAlgError:
            continue
        if not np.isfinite([E, e]).all() or not (-1e-10 <= E <= 1+1e-10 and -1e-10 <= e <= 1+1e-10):
            continue
        E, e = float(np.clip(E, 0, 1)), float(np.clip(e, 0, 1))
        residual = max(abs(E-np.clip(p*(1-c*e), 0, 1)), abs(e-np.clip(q*(1-d*E), 0, 1)))
        if residual > 1e-10:
            continue
        if holder == 'principal':
            principal = B*(E+(1-E)*alpha*e)-kP*E*E/2
            agent = b*(beta*E+(1-E)*e)-kA*e*e/2
        else:
            principal = B*(alpha*e+(1-e)*E)-kP*E*E/2
            agent = b*(e+(1-e)*beta*E)-kA*e*e/2
        if not np.isfinite([principal, agent]).all():
            raise ValueError('inputs produce non-finite payoffs')
        return {'E': E, 'e': e, 'principal_payoff': float(principal),
                'agent_payoff': float(agent), 'best_response_residual': float(residual)}
    raise ArithmeticError('no finite active-set candidate satisfies the original best responses')


def queue_capacity(arrival_rate, service_rate):
    """Stationary M/M/1 system and queue means in the units of the input rates."""
    if not np.isfinite([arrival_rate, service_rate]).all() or not 0 <= arrival_rate < service_rate:
        raise ValueError('rates must be finite and satisfy 0 <= arrival_rate < service_rate')
    rho = arrival_rate/service_rate
    W = 1/(service_rate-arrival_rate)
    if not np.isfinite([rho, W, arrival_rate*W]).all():
        raise ValueError('rates produce non-finite queue statistics')
    return {'utilization': float(rho), 'W': float(W), 'L': float(arrival_rate*W),
            'Wq': float(rho*W), 'Lq': float(arrival_rate*rho*W)}


def moment_map(theta, x):
    """Mean binary-choice probability and its x-weighted mean, in that order."""
    p = expit(theta[0] + theta[1]*x)
    return np.array([p.mean(), (x*p).mean()])


def moment_jacobian(theta, x):
    p = expit(theta[0] + theta[1]*x)
    w = p*(1-p)
    return np.array([[w.mean(), (x*w).mean()], [(x*w).mean(), (x*x*w).mean()]])


def jax_moment_map(theta, x):
    """Differentiable binary-choice moments shared across CPU and GPU dispatch."""
    import jax
    import jax.numpy as jnp
    p = jax.nn.sigmoid(theta[0] + theta[1]*x)
    return jnp.array([jnp.mean(p), jnp.mean(x*p)])


def jax_moment_batch(parameters, x, backend):
    """Evaluate batched moments on an explicitly selected available device."""
    import jax
    jax.config.update('jax_enable_x64', True)
    if backend not in ('cpu', 'gpu'): raise ValueError('backend must be cpu or gpu')
    try:
        devices = jax.devices(backend)
    except RuntimeError as exc:
        raise ValueError(f'JAX {backend} backend is unavailable') from exc
    if not devices: raise ValueError(f'JAX {backend} backend is unavailable')
    func = jax.jit(jax.vmap(jax_moment_map, in_axes=(0, None)))
    return func(jax.device_put(parameters, devices[0]), jax.device_put(x, devices[0])).block_until_ready()


def finite_jacobian(function, theta, step=1e-5):
    theta = np.asarray(theta, dtype=float)
    return np.column_stack([(function(theta + np.eye(len(theta))[j]*step) -
                             function(theta - np.eye(len(theta))[j]*step))/(2*step)
                            for j in range(len(theta))])


def correlated_equilibrium(payoffs, weights=None, tolerance=1e-9):
    """Maximize weighted payoffs over finite correlated equilibria and check obedience."""
    u = np.asarray(payoffs, dtype=float)
    if u.ndim < 3 or u.shape[0] != u.ndim-1 or any(s < 1 for s in u.shape[1:]) or not np.isfinite(u).all():
        raise ValueError('payoffs must be a finite player-by-action-profile array')
    n = u.shape[0]
    w = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    if w.shape != (n,) or not np.isfinite(w).all() or not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('weights and positive tolerance must be finite')
    profiles = list(itertools.product(*(range(size) for size in u.shape[1:])))
    rows, labels = [], []
    for i, size in enumerate(u.shape[1:]):
        for recommendation in range(size):
            for deviation in range(size):
                if recommendation == deviation:
                    continue
                row = []
                for profile in profiles:
                    changed = list(profile); changed[i] = deviation
                    row.append(u[(i,)+profile]-u[(i,)+tuple(changed)] if profile[i] == recommendation else 0.)
                rows.append(row); labels.append((i, recommendation, deviation))
    matrix = np.asarray(rows, dtype=float).reshape((-1, len(profiles)))
    objective = np.array([sum(w[i]*u[(i,)+profile] for i in range(n)) for profile in profiles])
    fit = optimize.linprog(-objective, A_ub=-matrix if rows else None,
                           b_ub=np.zeros(len(rows)) if rows else None,
                           A_eq=np.ones((1, len(profiles))), b_eq=[1.], bounds=(0., None), method='highs')
    if not fit.success:
        raise RuntimeError(f'correlated equilibrium LP failed: {fit.message}')
    q = fit.x; slack = matrix @ q
    mass_error = abs(float(q.sum())-1.)
    minimum_probability = float(q.min())
    minimum_obedience = float(slack.min()) if len(slack) else 0.
    if mass_error > tolerance or minimum_probability < -tolerance or minimum_obedience < -tolerance:
        raise RuntimeError('LP solution fails the original probability or obedience constraints')
    return {'probabilities': q.reshape(u.shape[1:]).tolist(), 'weighted_payoff': float(objective @ q),
            'payoffs': [float(sum(q[k]*u[(i,)+p] for k, p in enumerate(profiles))) for i in range(n)],
            'mass_error': mass_error, 'minimum_probability': minimum_probability,
            'obedience': [{'player': i, 'recommendation': r, 'deviation': d, 'slack': float(v)}
                          for (i, r, d), v in zip(labels, slack)]}


def tu_shapley_core(values):
    """Exact Shapley allocation and coalition-core slacks; coalition index is a bit mask."""
    if not isinstance(values, (list, tuple)) or len(values) < 2 or len(values) & (len(values)-1):
        raise ValueError('values must contain 2**n entries in coalition bit-mask order')
    n = len(values).bit_length()-1
    if n > 16:
        raise ValueError('at most 16 players are supported')
    try:
        v = [Fraction(str(x)) for x in values]
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise ValueError('coalition values must be finite rational numbers') from exc
    if v[0] != 0:
        raise ValueError('the empty-coalition value must be zero')
    allocation = []
    for i in range(n):
        phi = Fraction(0)
        for mask in range(len(v)):
            if not mask & (1 << i):
                k = mask.bit_count()
                weight = Fraction(math.factorial(k)*math.factorial(n-k-1), math.factorial(n))
                phi += weight*(v[mask | (1 << i)]-v[mask])
        allocation.append(phi)
    slacks = [sum((allocation[i] for i in range(n) if mask & (1 << i)), Fraction(0))-v[mask]
              for mask in range(1, len(v))]
    efficiency = sum(allocation, Fraction(0))-v[-1]
    return {'allocation': [str(x) for x in allocation], 'efficiency_residual': str(efficiency),
            'core_slacks': [str(x) for x in slacks], 'in_core': all(x >= 0 for x in slacks)}


def clearing_payments(liabilities, outside_liabilities, external_assets, tolerance=1e-11, maxiter=100000):
    """Greatest pro-rata interbank payment vector, including outside creditors."""
    L = np.asarray(liabilities, dtype=float)
    outside = np.asarray(outside_liabilities, dtype=float)
    x = np.asarray(external_assets, dtype=float)
    if L.ndim != 2 or L.shape[0] != L.shape[1] or L.shape[0] == 0:
        raise ValueError('liabilities must be a nonempty square matrix')
    n = len(L)
    if outside.shape != (n,) or x.shape != (n,) or not all(np.isfinite(a).all() for a in (L, outside, x)):
        raise ValueError('creditor matrix, outside liabilities and assets must have compatible finite entries')
    if np.min(L) < 0 or np.min(outside) < 0 or np.min(x) < 0 or np.any(np.diag(L) != 0):
        raise ValueError('assets and liabilities must be nonnegative, and self-liabilities zero')
    if not np.isfinite(tolerance) or tolerance <= 0 or not isinstance(maxiter, int) or maxiter < 1:
        raise ValueError('tolerance and maximum iterations must be positive')
    nominal = L.sum(axis=1) + outside
    pi = np.divide(L, nominal[:, None], out=np.zeros_like(L), where=nominal[:, None] > 0)
    outside_share = np.divide(outside, nominal, out=np.zeros_like(outside), where=nominal > 0)
    p = nominal.copy()
    for iteration in range(1, maxiter+1):
        new_p = np.minimum(nominal, x + pi.T @ p)
        residual = float(np.max(np.abs(new_p - np.minimum(nominal, x + pi.T @ new_p))))
        p = new_p
        if residual <= tolerance:
            break
    else:
        raise RuntimeError('clearing iteration did not reach the original-equation tolerance')
    available = x + pi.T @ p
    equity = np.maximum(available - p, 0.)
    outside_payments = outside_share*p
    resource_error = float(outside_payments.sum() + equity.sum() - x.sum())
    if abs(resource_error) > n*tolerance*2:
        raise RuntimeError('clearing payments fail the aggregate resource identity')
    return {'payments': p.tolist(), 'nominal': nominal.tolist(), 'equity': equity.tolist(),
            'outside_payments': outside_payments.tolist(), 'iterations': iteration,
            'fixed_point_residual': residual, 'resource_residual': resource_error,
            'strict_outside_share': bool(np.all((nominal == 0) | (outside > 0)))}


def finite_policy_sir(initial, beta, gamma, schedule, infection_cost=1., control_cost=0., terminal_cost=0.,
                      rtol=1e-9, atol=1e-11, max_step=np.inf):
    """Integrate piecewise-constant contact controls and price infections and control."""
    y0 = np.asarray(initial, dtype=float)
    if y0.shape != (3,) or not np.isfinite(y0).all() or np.any(y0 < 0) or y0.sum() <= 0:
        raise ValueError('initial S, I and R must be finite, nonnegative and have positive total')
    if not np.isfinite([beta, gamma, infection_cost, control_cost, terminal_cost, rtol, atol]).all():
        raise ValueError('rates, costs and tolerances must be finite')
    if (min(beta, gamma, infection_cost, control_cost, terminal_cost) < 0
            or min(rtol, atol, max_step) <= 0 or not (np.isfinite(max_step) or np.isposinf(max_step))):
        raise ValueError('rates and costs must be nonnegative; tolerances and max_step must be positive')
    if not schedule:
        raise ValueError('schedule must contain at least one (end time, control) pair')
    N = float(y0.sum()); state = np.r_[y0, 0.]; times = [0.]; trajectory = [state.tolist()]
    t0 = 0.; total_control = 0.
    for end, control in schedule:
        end, control = float(end), float(control)
        if not np.isfinite([end, control]).all() or end <= t0 or not 0 <= control <= 1:
            raise ValueError('schedule end times must increase and control must lie in [0, 1]')
        def rhs(t, y):
            incidence = beta*(1-control)*y[0]*y[1]/N
            recovery = gamma*y[1]
            return [-incidence, incidence-recovery, recovery, incidence]
        sol = integrate.solve_ivp(rhs, (t0, end), state, rtol=rtol, atol=atol, max_step=max_step)
        if not sol.success:
            raise RuntimeError(f'SIR integration failed: {sol.message}')
        times.extend(sol.t[1:].tolist()); trajectory.extend(sol.y[:, 1:].T.tolist())
        state = sol.y[:, -1]; total_control += control_cost*control**2*(end-t0); t0 = end
    path = np.asarray(trajectory)
    mass_error = float(np.max(np.abs(path[:, :3].sum(axis=1)-N)))
    flow_error = float(np.max(np.abs(path[:, 0] + path[:, 3]-y0[0])))
    minimum = float(path[:, :3].min())
    acceptance = max(100*atol, 10*rtol*N)
    if mass_error > acceptance or flow_error > acceptance or minimum < -acceptance:
        raise RuntimeError('SIR path fails mass, infection-flow, or nonnegativity checks')
    infection_loss = infection_cost*float(state[3]); terminal_loss = terminal_cost*float(state[1])
    return {'times': times, 'path_S_I_R_cumulative': trajectory, 'new_infections': float(state[3]),
            'terminal_infected': float(state[1]), 'infection_loss': infection_loss,
            'control_loss': total_control, 'terminal_loss': terminal_loss,
            'total_loss': infection_loss + total_control + terminal_loss,
            'mass_residual': mass_error, 'infection_flow_residual': flow_error, 'minimum_state': minimum}


def optimize_moments(target, x, starts, bounds, maxiter=1000):
    """Multistart constrained least-squares on one fixed moment objective."""
    def objective(theta):
        difference = moment_map(theta, x)-target
        return float(difference @ difference)
    def gradient(theta):
        return 2*moment_jacobian(theta, x).T @ (moment_map(theta, x)-target)
    attempts = []
    for start in starts:
        fit = optimize.minimize(objective, start, jac=gradient, method='L-BFGS-B', bounds=bounds,
                                options={'maxiter': maxiter, 'ftol': 1e-15, 'gtol': 1e-10})
        attempts.append({'initial': list(map(float, start)), 'parameters': fit.x.tolist(),
                         'objective': float(fit.fun), 'gradient': gradient(fit.x).tolist(),
                         'iterations': int(fit.nit), 'success': bool(fit.success), 'message': str(fit.message)})
    successful = [a for a in attempts if a['success']]
    return {'attempts': attempts, 'best': min(successful, key=lambda a: a['objective']) if successful else None}


def birth_death_generator(n, birth, death):
    """Finite-state continuous-time reflecting birth/death generator."""
    if not isinstance(n, int) or n < 2 or not np.isfinite([birth, death]).all() or min(birth, death) < 0:
        raise ValueError('generator requires at least two states and finite nonnegative rates')
    upper = np.full(n-1, birth); lower = np.full(n-1, death)
    diagonal = -np.r_[birth, np.full(n-2, birth+death), death]
    return sparse.diags([lower, diagonal, upper], [-1, 0, 1], format='csr')


def _parallel_draw(item):
    seed, count = item
    rng = np.random.default_rng(seed)
    return float(np.exp(rng.random(count)).mean())


def compare_dynamic_algorithms(seed):
    """Compare existing NFXP, MPEC and SLC on the same game and observations."""
    import research_dynamic as dynamic
    import equity_io
    beta, profit, competition, cost = .8, 1., .4, .8
    states = [(0, 0), (0, 1), (1, 0), (1, 1)]
    names = ['00', '01', '10', '11']
    model = dynamic.discrete_game(beta, profit, competition, cost)
    data = dynamic.simulate_game(model['policies'], 100, 10, seed)
    profiles = []
    for i, state in enumerate(states):
        for j, action in enumerate(states):
            profiles.append({'state': names[i], 'actions': list(action),
                'payoffs': [action[k]*(profit-competition*action[1-k]) for k in range(2)],
                'payoff_features': {'entry_cost': [-action[k]*(1-state[k]) for k in range(2)]},
                'transitions': {names[j]: 1.}})
    observations = [{'market_id': int(row[0]), 'period': int(row[1]), 'state': names[row[2]],
        'actions': [int(row[3]), int(row[4])], 'next_state': names[states.index((row[3],row[4]))]}
        for row in data]
    spec = {'currency': 'synthetic units', 'amount_unit': 1, 'firms': ['A','B'], 'states': names,
        'profiles': profiles, 'observations': observations, 'discount_factor': beta, 'shock_scale': 1.,
        'flow_timing': 'current', 'action_timing': 'action determines next state',
        'shock_role': 'monetary_action_payoff', 'flow_definition': 'current profit less entry cost',
        'parameters': [{'name':'entry_cost','initial':.9,'bounds':[0.,2.]}],
        'identification': {'parameters': [{'name':'entry_cost','role':'payoff',
            'moments':['entry choices'],'variation':'active and inactive states'}]}}
    results = {}
    for method in ('nfxp','mpec'):
        start = time.perf_counter()
        fitted = equity_io.dynamic_game({**spec, 'estimation_method':method})
        results[method] = {'seconds':time.perf_counter()-start, 'result':fitted}
    start = time.perf_counter()
    fitted = dynamic.sequential_estimate(data,beta,profit,competition,[0.,2.],'slc')
    results['slc'] = {'seconds':time.perf_counter()-start, 'result':fitted}
    return {'specification':spec, 'generating_cost':cost,
            'sample_seed':seed, 'algorithm_results':results,
            'time_boundary':'one fit, original observed actions and fixed model; excludes data generation',
            'source_sha256':{name:hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                             for name,module in [('equity_io',equity_io),('research_dynamic',dynamic)]}}


def _local_checks():
    source = Path(__file__).resolve()
    candidates = [source.parent / 'local_checks.py', source.parent / 'LOCAL_CHECKS.py']
    candidates.extend(p / 'harness' / 'local_checks.py' for p in source.parents)
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise FileNotFoundError('local_checks.py required for atomic publication')
    module_spec = importlib.util.spec_from_file_location('numerics_local_checks', path)
    module = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(module)
    return module


def write_json(path, value):
    payload = json.dumps(value, indent=2, allow_nan=False)+'\n'
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.'+path.name+'.')
    try:
        with os.fdopen(fd, 'w') as out:
            out.write(payload)
        _local_checks().replace_path(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def run(spec):
    if set(spec) != {'seed', 'theta', 'grid_size', 'mc_replications', 'mc_sample_size', 'julia', 'jax_backend'}:
        raise ValueError('spec requires seed, theta, grid_size, mc_replications, mc_sample_size, julia, jax_backend')
    seed = int(spec['seed']); theta = np.asarray(spec['theta'], dtype=float)
    n = int(spec['grid_size']); reps = int(spec['mc_replications']); sample = int(spec['mc_sample_size'])
    if theta.shape != (2,) or not np.isfinite(theta).all() or not (-1.8 < theta[0] < 1.8 and .2 < theta[1] < 2.8):
        raise ValueError('theta must lie inside the surrogate region [-2,2] x [0,3]')
    if spec['jax_backend'] not in ('cpu', 'gpu'):
        raise ValueError('jax_backend must be cpu or gpu')
    if seed < 0 or n < 10 or reps < 2 or sample < 10 or not isinstance(spec['julia'], str):
        raise ValueError('invalid seed, grid, Monte Carlo dimensions or Julia executable')
    started = time.perf_counter(); rng = np.random.default_rng(seed)
    algorithms = compare_dynamic_algorithms(seed)
    x = np.linspace(-2, 2, n); target = moment_map(theta, x); jac = moment_jacobian(theta, x)
    svals = np.linalg.svd(jac, compute_uv=False); rank = int(np.linalg.matrix_rank(jac))
    fdjac = finite_jacobian(lambda t: moment_map(t, x), theta)
    starts = [[-1.5,.3], [1., 2.5], [0.,1.]]; bounds = [(-2.,2.), (0.,3.)]
    failed = optimize_moments(target, x, starts[:1], bounds, maxiter=1)
    t0 = time.perf_counter(); direct = optimize_moments(target, x, starts, bounds); direct_seconds = time.perf_counter()-t0
    if direct['best'] is None: raise ArithmeticError('multistart optimizer failed')
    t0 = time.perf_counter(); single = optimize_moments(target, x, [[0.,1.]], bounds); single_seconds = time.perf_counter()-t0
    if single['best'] is None: raise ArithmeticError('single-start optimizer failed')
    repaired = optimize_moments(target, x, [failed['attempts'][0]['parameters']], bounds)
    if repaired['best'] is None: raise ArithmeticError('optimization repair failed')

    # Frozen train, validation and holdout draws are generated before fitting.
    all_params = rng.uniform([-2.,0.], [2.,3.], size=(900,2))
    labels = np.array([moment_map(t, x) for t in all_params])
    from sklearn.neural_network import MLPRegressor
    import sklearn
    t0 = time.perf_counter()
    mlp = MLPRegressor(hidden_layer_sizes=(40,40), activation='tanh', solver='lbfgs',
                       alpha=1e-6, max_iter=1200, random_state=seed, tol=1e-10, max_fun=50000)
    mlp.fit(all_params[:600], labels[:600]); train_seconds = time.perf_counter()-t0
    errors = {}
    for name, sl in [('train',slice(0,600)),('validation',slice(600,750)),('holdout',slice(750,900))]:
        error = mlp.predict(all_params[sl])-labels[sl]
        errors[name] = {'rmse': float(np.sqrt(np.mean(error**2))), 'max_abs_error': float(np.max(np.abs(error))),
                        'parameter_indices': [sl.start, sl.stop]}
    t0 = time.perf_counter()
    surrogate_fit = optimize.minimize(lambda t: float(np.sum((mlp.predict(np.asarray(t)[None,:])[0]-target)**2)),
                                      [0.,1.], method='L-BFGS-B', bounds=bounds,
                                      options={'ftol':1e-15, 'gtol':1e-10, 'maxiter':1000})
    surrogate_seconds = time.perf_counter()-t0
    if not surrogate_fit.success: raise ArithmeticError('surrogate objective failed: '+str(surrogate_fit.message))
    t0 = time.perf_counter(); warm = optimize_moments(target, x, [surrogate_fit.x], bounds); warm_seconds = time.perf_counter()-t0
    if warm['best'] is None: raise ArithmeticError('warm-start original objective failed')
    surrogate_original_error = float(np.max(np.abs(moment_map(surrogate_fit.x,x)-target)))

    # Contractive scalar map, checked against its original fixed-point equation.
    mapping = lambda z: np.cos(z)*.8
    z = 0.; steps = 0
    while abs(z-mapping(z)) > 1e-11 and steps < 10000:
        z = float(mapping(z)); steps += 1
    accelerated = float(optimize.fixed_point(mapping, 0., xtol=1e-11, maxiter=1000, method='del2'))
    if abs(z-mapping(z)) > 1e-11 or abs(accelerated-mapping(accelerated)) > 1e-10:
        raise ArithmeticError('fixed-point residual exceeds tolerance')

    truth = float(np.e-1); deterministic, quadrature_error = integrate.quad(lambda u: np.exp(u), 0., 1., epsabs=1e-12)
    mc = float(np.exp(rng.random(1024)).mean())
    sobol = float(np.exp(qmc.Sobol(d=1, scramble=True, seed=seed).random_base2(10)).mean())
    seeds = [int(s.generate_state(1)[0]) for s in np.random.SeedSequence(seed).spawn(8)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        parallel = list(pool.map(_parallel_draw, [(s, 4096) for s in seeds]))
    serial = [_parallel_draw((s,4096)) for s in seeds]
    generator = birth_death_generator(1000, .7, .5)
    rhs = np.sin(np.arange(1000)/100)
    solution = spsolve(sparse.eye(1000, format='csr')-.9*generator, rhs)
    sparse_error = float(np.max(np.abs((sparse.eye(1000, format='csr')-.9*generator)@solution-rhs)))

    import jax
    import jaxlib
    jax.config.update('jax_enable_x64', True)
    import jax.numpy as jnp
    kernel = jax_moment_map
    jax_grid = jnp.asarray(x); jax_theta = jnp.asarray(theta)
    jac_jax = np.asarray(jax.jacfwd(kernel)(jax_theta, jax_grid))
    f_jax = lambda t: jnp.sum((kernel(t,jax_grid)-jnp.asarray(target))**2)
    h_jax = np.asarray(jax.hessian(f_jax)(jax_theta))
    h_fd = finite_jacobian(lambda t: 2*moment_jacobian(t,x).T@(moment_map(t,x)-target), theta, 1e-4)
    cpu = jax.devices('cpu')[0]
    batch = jax.device_put(all_params[:512], cpu); jax_grid = jax.device_put(x, cpu)
    fn = jax.jit(jax.vmap(kernel, in_axes=(0,None)))
    t0 = time.perf_counter(); compiled = np.asarray(fn(batch,jax_grid).block_until_ready()); compile_seconds = time.perf_counter()-t0
    t0 = time.perf_counter(); compiled = np.asarray(fn(batch,jax_grid).block_until_ready()); jax_seconds = time.perf_counter()-t0
    t0 = time.perf_counter(); reference = np.array([moment_map(t,x) for t in all_params[:512]]); numpy_seconds = time.perf_counter()-t0
    try:
        gpu_devices = jax.devices('gpu')
    except RuntimeError:
        gpu_devices = []
    gpu = {'available': bool(gpu_devices), 'devices': [str(d) for d in gpu_devices], 'executed': False}
    if gpu_devices:
        gpu_fn = jax.jit(jax.vmap(kernel, in_axes=(0,None)))
        gpu_output = np.asarray(gpu_fn(jax.device_put(all_params[:512],gpu_devices[0]),
                                       jax.device_put(x,gpu_devices[0])).block_until_ready())
        gpu.update({'executed':True, 'max_abs_error_vs_cpu':float(np.max(np.abs(gpu_output-compiled)))})

    if spec['jax_backend'] == 'gpu' and not gpu_devices:
        raise ValueError('requested JAX GPU backend is unavailable on this host')

    # Every replication generates a binary sample on the same identified grid.
    estimates=[]; statuses=[]; t0=time.perf_counter()
    mc_seeds = [int(s.generate_state(1)[0]) for s in np.random.SeedSequence(seed+1).spawn(reps)]
    probabilities = expit(theta[0]+theta[1]*x)
    for draw_seed in mc_seeds:
        rr=np.random.default_rng(draw_seed); idx=rr.integers(0,n,size=sample)
        xx=x[idx]; yy=rr.binomial(1, probabilities[idx]); observed=np.array([yy.mean(), (xx*yy).mean()])
        fit=optimize_moments(observed,xx,[[0.,1.]],bounds)
        statuses.append(fit['best'] is not None)
        if fit['best'] is not None: estimates.append(fit['best']['parameters'])
    monte_seconds=time.perf_counter()-t0
    if len(estimates) != reps: raise ArithmeticError('one or more Monte Carlo fits failed')
    estimates=np.asarray(estimates); bias=np.mean(estimates-theta,axis=0); rmse=np.sqrt(np.mean((estimates-theta)**2,axis=0))

    julia_script=Path(__file__).with_name('research_numerics.jl')
    t0=time.perf_counter()
    proc=subprocess.run([spec['julia'],'--startup-file=no',str(julia_script),'1000','.7','.5','.9'],
                        check=True,text=True,capture_output=True,timeout=90)
    julia_seconds=time.perf_counter()-t0
    lines=proc.stdout.strip().splitlines()
    if len(lines)!=3: raise ValueError('Julia numerical output malformed')
    julia_version=lines[0]; julia_metrics=np.array([float(v) for v in lines[1].split(',')]); julia_solution=np.array([float(v) for v in lines[2].split(',')])
    if len(julia_solution)!=len(solution) or len(julia_metrics)!=2: raise ValueError('Julia sparse output has wrong dimensions')
    comparison=float(np.max(np.abs(julia_solution-solution)))
    if (rank < 2 or np.max(np.abs(jac-fdjac)) > 1e-7 or np.max(np.abs(jac-jac_jax)) > 1e-8
            or np.max(np.abs(h_jax-h_fd)) > 1e-6 or sparse_error > 1e-9 or comparison > 1e-9
            or np.max(np.abs(moment_map(direct['best']['parameters'],x)-target)) > 1e-7
            or np.max(np.abs(moment_map(warm['best']['parameters'],x)-target)) > 1e-7):
        raise ArithmeticError('original equations, identification or derivative comparison failed tolerance')
    if serial != parallel: raise ArithmeticError('parallel draws changed their independent streams')

    stat = lambda value, unit: {'value':float(value),'unit':unit}
    alg = algorithms['algorithm_results']
    stats={'dynamic_nfxp_entry_cost':stat(alg['nfxp']['result']['estimation']['parameters']['entry_cost'],'utility'),
           'dynamic_mpec_entry_cost':stat(alg['mpec']['result']['estimation']['parameters']['entry_cost'],'utility'),
           'dynamic_slc_entry_cost':stat(alg['slc']['result']['entry_cost'],'utility'),
           'dynamic_slc_equilibrium_residual':stat(alg['slc']['result']['equilibrium_logit_residual'],'log odds'),
           'moment_jacobian_rank':stat(rank,'parameters'), 'moment_jacobian_smallest_singular_value':stat(svals[-1],'moment per parameter'),
           'moment_jacobian_analytic_fd_error':stat(np.max(np.abs(jac-fdjac)),'moment per parameter'),
           'moment_jacobian_jax_error':stat(np.max(np.abs(jac-jac_jax)),'moment per parameter'),
           'objective_hessian_jax_fd_error':stat(np.max(np.abs(h_jax-h_fd)),'objective per parameter squared'),
           'moment_fit_residual':stat(np.max(np.abs(moment_map(direct['best']['parameters'],x)-target)),'moment'),
           'fixed_point_residual':stat(abs(z-mapping(z)),'value'), 'accelerated_fixed_point_residual':stat(abs(accelerated-mapping(accelerated)),'value'),
           'quadrature_abs_error':stat(abs(deterministic-truth),'integral'), 'monte_carlo_integral_abs_error':stat(abs(mc-truth),'integral'),
           'sobol_integral_abs_error':stat(abs(sobol-truth),'integral'), 'sparse_linear_residual':stat(sparse_error,'value'),
           'jax_cpu_reference_error':stat(np.max(np.abs(compiled-reference)),'moment'),
           'julia_python_solution_error':stat(comparison,'value'), 'surrogate_holdout_rmse':stat(errors['holdout']['rmse'],'moment'),
           'surrogate_original_moment_error':stat(surrogate_original_error,'moment'),
           'warm_original_moment_error':stat(np.max(np.abs(moment_map(warm['best']['parameters'],x)-target)),'moment'),
           'monte_carlo_bias_intercept':stat(bias[0],'parameter'), 'monte_carlo_bias_slope':stat(bias[1],'parameter'),
           'monte_carlo_rmse_intercept':stat(rmse[0],'parameter'), 'monte_carlo_rmse_slope':stat(rmse[1],'parameter'),
           'monte_carlo_converged':stat(sum(statuses),'replications')}
    return {'model':'synthetic_binary_choice_moments', 'specification':spec, 'engine':'NumPy/SciPy/scikit-learn/JAX/Julia',
      'statistics':stats, 'fullresults':{
        'algorithm_comparison':algorithms,
        'identification':{'moment_order':['mean_probability','mean_x_probability'], 'parameter_order':['intercept','slope'],
                          'jacobian':jac.tolist(),'singular_values':svals.tolist(),'rank':rank,'rank_tolerance':float(svals[0]*max(jac.shape)*np.finfo(float).eps)},
        'derivatives':{'finite_difference_jacobian':fdjac.tolist(),'jax_jacobian':jac_jax.tolist(),'jax_hessian':h_jax.tolist(),'finite_difference_hessian':h_fd.tolist()},
        'optimization':{'direct':direct,'initial_iteration_limit':failed,'repair_same_objective':repaired,'direct_seconds_all_starts':direct_seconds, 'single_start':single, 'single_start_seconds':single_seconds},
        'surrogate':{'region':[[-2,2],[0,3]], 'split_seed':seed, 'split_indices':'train 0:600, validation 600:750, holdout 750:900',
                     'architecture':[2,40,40,2], 'training_seconds':train_seconds,'errors':errors,
                     'surrogate_fit':{'parameters':surrogate_fit.x.tolist(),'objective':float(surrogate_fit.fun),'success':bool(surrogate_fit.success), 'seconds':surrogate_seconds},
                     'original_fit_from_surrogate':warm,'warm_original_seconds':warm_seconds,
                     'timing_boundary':'direct single and multistart times are original fits; warm includes surrogate fit plus one original fit; training is separate'},
        'fixed_point':{'map':'0.8*cos(x)','plain_iterations':steps,'plain':z,'accelerated':accelerated,'acceleration':'scipy.optimize.fixed_point del2','tolerance':1e-11},
        'integration':{'integrand':'exp(u), u uniform on [0,1]','exact':truth,'quad':deterministic,'quad_error_estimate':quadrature_error,'monte_carlo':mc,'sobol_scrambled':sobol,'draws':1024,'parallel_draws':parallel,'parallel_matches_serial':serial==parallel,'parallel_seeds':seeds,'workers':4},
        'sparse':{'dimension':1000,'nnz_generator':int(generator.nnz),'generator_row_sum_max':float(np.max(np.abs(np.asarray(generator.sum(axis=1))))),'linear_residual':sparse_error},
        'jax':{'reference_backend':'cpu','requested_backend':spec['jax_backend'],'devices':[str(d) for d in jax.devices()],'dtype':str(jax_theta.dtype), 'compile_and_first_call_seconds':compile_seconds,'warm_call_seconds':jax_seconds,'numpy_reference_seconds':numpy_seconds,'batch':512,'gpu':gpu},
        'monte_carlo':{'replications':reps,'sample_size':sample,'independent_seeds':mc_seeds,'estimates':estimates.tolist(),'converged':statuses,'bias':bias.tolist(),'rmse':rmse.tolist(),'seconds':monte_seconds},
        'julia':{'executable':spec['julia'],'version':julia_version,'script':str(julia_script.resolve()),'script_sha256':hashlib.sha256(julia_script.read_bytes()).hexdigest(),'metrics':julia_metrics.tolist(),'python_solution_max_abs_error':comparison,'wall_seconds_including_startup':julia_seconds}},
      'provenance':{'python':sys.version.split()[0], 'numpy':np.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__,'jax':jax.__version__,'jaxlib':jaxlib.__version__,
                    'platform':platform.platform(),'cpu_count':os.cpu_count(),'cpu_affinity_count':len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count(),'seed':seed,'precision':'float64',
                    'elapsed_seconds':time.perf_counter()-started,'time_boundary':'run function including Julia startup, compilation, training and all fits',
                    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}


def case(output):
    output=output.absolute()
    if output.exists(): raise FileExistsError(output)
    spec={'seed':20261101,'theta':[-.4,1.2],'grid_size':201,'mc_replications':50,'mc_sample_size':1000,
          'julia':os.environ.get('ECON_JULIA','julia'),'jax_backend':'cpu'}
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='.numerics-') as tmp:
        stage=Path(tmp)/'stage'; stage.mkdir()
        write_json(stage/'numerics-spec.json',spec); write_json(stage/'numerics-result.json',run(spec))
        _local_checks().atomic_publish(stage,output)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    a=sub.add_parser('run'); a.add_argument('spec',type=Path); a.add_argument('--output','-o',required=True,type=Path)
    a=sub.add_parser('case'); a.add_argument('--output','-o',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        if args.command=='case': case(args.output)
        else:
            if args.spec.resolve()==args.output.resolve(): raise ValueError('output must differ from specification')
            raw=args.spec.read_bytes(); result=run(json.loads(raw)); result['provenance']['spec_sha256']=hashlib.sha256(raw).hexdigest()
            write_json(args.output,result)
    except (ValueError, TypeError, KeyError, OSError, ArithmeticError, subprocess.SubprocessError) as exc:
        parser.exit(2,'error: '+str(exc)+'\n')

if __name__=='__main__': main()
