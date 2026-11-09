#!/usr/bin/env python3
"""Shared numerical calculations and finite economic model execution."""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import importlib.util
import inspect
import itertools
import json
import math
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import scipy
from scipy import integrate, optimize, sparse
from scipy.special import expit


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
    """Evaluate the supplied two-sided step with SciPy's second-order stencil."""
    from scipy.differentiate import jacobian
    result = jacobian(lambda points: np.apply_along_axis(function, 0, points),
                      np.asarray(theta, dtype=float), order=2, initial_step=step, maxiter=1)
    if not np.isfinite(result.df).all():
        raise ArithmeticError('finite Jacobian produced non-finite derivatives')
    return result.df


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
    # Every feasible payment is below the greatest clearing vector. A strictly
    # increasing objective therefore selects the same greatest fixed point.
    fit = optimize.linprog(-np.ones(n), A_ub=np.eye(n)-pi.T, b_ub=x,
                           bounds=list(zip(np.zeros(n), nominal)), method='highs',
                           options={'maxiter': maxiter, 'primal_feasibility_tolerance': 1e-10,
                                    'dual_feasibility_tolerance': 1e-10})
    if not fit.success:
        raise RuntimeError('clearing payment LP failed: '+fit.message)
    p = fit.x
    residual = float(np.max(np.abs(p-np.minimum(nominal, x+pi.T @ p))))
    if residual > tolerance or np.any(p < -tolerance) or np.any(p > nominal+tolerance):
        raise RuntimeError('clearing LP did not reach the original-equation tolerance')
    available = x + pi.T @ p
    equity = np.maximum(available - p, 0.)
    outside_payments = outside_share*p
    resource_error = float(outside_payments.sum() + equity.sum() - x.sum())
    if abs(resource_error) > n*tolerance*2:
        raise RuntimeError('clearing payments fail the aggregate resource identity')
    return {'payments': p.tolist(), 'nominal': nominal.tolist(), 'equity': equity.tolist(),
            'outside_payments': outside_payments.tolist(), 'iterations': int(fit.nit),
            'solver': {'method': 'scipy.optimize.linprog(method=highs)',
                       'success': bool(fit.success), 'message': fit.message},
            'fixed_point_residual': residual, 'resource_residual': resource_error,
            'strict_outside_share': bool(np.all((nominal == 0) | (outside > 0)))}


def finite_policy_sir(initial, beta, gamma, schedule, infection_cost=1., control_cost=0., terminal_cost=0.,
                      rtol=1e-9, atol=1e-11, max_step=None):
    """Integrate piecewise-constant contact controls and price infections and control."""
    max_step = np.inf if max_step is None else max_step
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
    if not isinstance(spec, dict) or set(spec) != {'model', 'inputs', 'unit'} or not isinstance(spec['inputs'], dict):
        raise ValueError('model run requires model, inputs object and unit')
    if not isinstance(spec['unit'], str) or not spec['unit'].strip():
        raise ValueError('unit must name the payoff, currency or queue time unit')
    model = spec['model']; unit = spec['unit']
    functions = {'correlated_equilibrium': correlated_equilibrium, 'tu_shapley_core': tu_shapley_core,
                 'interbank_clearing': clearing_payments, 'multitask_incentives': multitask_incentives,
                 'state_price_bounds': state_price_bounds, 'binary_logit': moment_map,
                 'finite_policy_sir': finite_policy_sir, 'queue_capacity': queue_capacity,
                 'decision_rights': decision_rights}
    if not isinstance(model, str) or model not in functions:
        raise ValueError('model must be one of ' + ', '.join(functions))
    function = functions[model]
    arguments = inspect.signature(function).bind(**spec['inputs'])
    arguments.apply_defaults()
    if model == 'binary_logit':
        theta = np.asarray(arguments.arguments['theta'], dtype=float)
        x = np.asarray(arguments.arguments['x'], dtype=float)
        if theta.shape != (2,) or x.ndim != 1 or not x.size or not np.isfinite(theta).all() or not np.isfinite(x).all():
            raise ValueError('binary_logit requires finite intercept/slope theta and a nonempty one-dimensional x')
        result = {'moment_map': moment_map(theta, x).tolist(),
                  'moment_jacobian': moment_jacobian(theta, x).tolist()}
    else:
        result = function(**arguments.arguments)
    stat = lambda value, measure: {'value': float(value), 'unit': measure}
    statistics = {}
    if model == 'correlated_equilibrium':
        contract, knowledge = 'MC-finite-correlated-equilibrium', 'GAME-07'
        engine = 'scipy.optimize.linprog(method=highs)'
        equations = ['sum_a q(a)=1; q(a)>=0',
            'sum_a_-i q(r,a_-i)*(u_i(r,a_-i)-u_i(d,a_-i))>=0 for each i,r,d',
            'max_q sum_a q(a)*sum_i weights_i*u_i(a)']
        statistics = {'weighted_payoff': stat(result['weighted_payoff'], unit),
            'mass_error': stat(result['mass_error'], 'probability'),
            'minimum_probability': stat(result['minimum_probability'], 'probability'),
            'minimum_obedience': stat(min((row['slack'] for row in result['obedience']), default=0.), unit)}
        statistics.update({f'payoff_player_{i}': stat(value, unit) for i, value in enumerate(result['payoffs'])})
        selection = 'maximize the supplied weighted payoff over conditional-obedience distributions'
    elif model == 'tu_shapley_core':
        contract, knowledge = 'MC-finite-tu-shapley-core', 'GAME-09'
        engine = 'fractions.Fraction'
        equations = ['phi_i=sum_S subset N\\{i} |S|!*(n-|S|-1)!/n!*(v(S union {i})-v(S))',
            'sum_i phi_i=v(N); core_slack(S)=sum_i in S phi_i-v(S)']
        statistics = {f'allocation_player_{i}': stat(Fraction(value), unit)
                      for i, value in enumerate(result['allocation'])}
        statistics['efficiency_residual'] = stat(Fraction(result['efficiency_residual']), unit)
        statistics['minimum_core_slack'] = stat(min(map(Fraction, result['core_slacks'])), unit)
        selection = 'Shapley allocation with every coalition evaluated for core membership'
    elif model == 'interbank_clearing':
        contract, knowledge = 'MC-interbank-clearing', 'FINANCE-08'
        engine = 'scipy.optimize.linprog(method=highs)'
        equations = ['nominal_i=outside_liabilities_i+sum_j liabilities_ij',
            'Pi_ij=liabilities_ij/nominal_i, with zero rows when nominal_i=0',
            'payments=min(nominal,external_assets+Pi.T@payments)',
            'sum(outside_payments)+sum(equity)=sum(external_assets)']
        for name in ('payments', 'nominal', 'outside_payments', 'equity'):
            statistics.update({f'{name}_bank_{i}': stat(value, unit) for i, value in enumerate(result[name])})
            statistics['total_'+name] = stat(sum(result[name]), unit)
        for name in ('fixed_point_residual', 'resource_residual'):
            statistics[name] = stat(result[name], unit)
        selection = 'greatest clearing fixed point selected by maximizing feasible equal-priority pro-rata payments'
    elif model == 'state_price_bounds':
        contract, knowledge = 'MC-state-price-bounds', 'ASSET-01'
        engine = 'scipy.optimize.linprog(method=highs)'
        equations = ['X.T@q=p; q>0',
            'L=min_{q>=0,X.T@q=p} h@q; U=max_{q>=0,X.T@q=p} h@q',
            'L=max_{X@theta<=h} p@theta; U=min_{X@theta>=h} p@theta',
            'price_set=(L,U) for unspanned h; price_set={p@theta} when X@theta=h']
        statistics = {name: stat(result[name], unit+' today') for name in
            ('lower_bound', 'upper_bound', 'pricing_residual', 'lower_duality_gap', 'upper_duality_gap')}
        statistics.update({name: stat(result[name], unit+' at payoff date') for name in
            ('subhedge_violation', 'superhedge_violation', 'replication_residual')})
        statistics['state_price_violation'] = stat(result['state_price_violation'], unit+' today per state payoff unit')
        selection = 'strictly positive state prices; open price interval for an unspanned claim and unique replication price for a spanned claim'
    elif model == 'multitask_incentives':
        contract, knowledge = 'MC-multitask-incentives', 'CONTRACT-07'
        engine = 'research_numerics.multitask_incentives'
        equations = ['max_x,y>=0 U_A=a+b*x+m*y-(x*x+y*y+2*rho*x*y)/2',
            'U_P=vq*x+vqly*y-a-b*x',
            'g=(b-x-rho*y,m-y-rho*x); g<=0; (x,y)*g=0']
        statistics = {name: stat(result[name], 'normalized effort') for name in ('x', 'y')}
        statistics.update({name: stat(result[name], unit) for name in ('principal_payoff', 'agent_payoff')})
        statistics['kkt_residual'] = stat(result['kkt_residual'], unit+' per normalized effort')
        selection = 'unique nonnegative agent best response at the supplied contract and strictly convex effort cost'
    elif model == 'binary_logit':
        contract, knowledge = 'MC-binary-logit', 'STRUCT-01'
        engine = 'research_numerics.moment_map + research_numerics.moment_jacobian'
        equations = ['p_i=expit(theta_0+theta_1*x_i)',
            'm(theta)=mean_i (p_i,x_i*p_i)',
            'G(theta)=mean_i p_i*(1-p_i)*[[1,x_i],[x_i,x_i*x_i]]']
        statistics = {'mean_choice_probability': stat(result['moment_map'][0], 'probability'),
            'covariate_choice_moment': stat(result['moment_map'][1], 'dimensionless covariate times probability')}
        for i, row in enumerate(result['moment_jacobian']):
            for j, value in enumerate(row):
                statistics[f'moment_{i}_derivative_theta_{j}'] = stat(value, 'moment per dimensionless parameter')
        selection = 'evaluate supplied intercept and slope at equally weighted covariates with unit logit scale and zero base-action utility'
    elif model == 'finite_policy_sir':
        contract, knowledge = 'MC-sir-finite-policy', 'HEALTH-08'
        engine = 'scipy.integrate.solve_ivp'
        equations = ['N=S_0+I_0+R_0; incidence=beta*(1-u)*S*I/N',
            'dS/dt=-incidence; dI/dt=incidence-gamma*I; dR/dt=gamma*I; dC/dt=incidence',
            'loss=infection_cost*C_T+integral control_cost*u(t)^2 dt+terminal_cost*I_T',
            'S+I+R=N; S+C=S_0']
        statistics = {name: stat(result[name], 'persons') for name in
            ('new_infections', 'terminal_infected', 'mass_residual', 'infection_flow_residual', 'minimum_state')}
        statistics.update({name: stat(result[name], unit) for name in
            ('infection_loss', 'control_loss', 'terminal_loss', 'total_loss')})
        selection = 'evaluate the supplied finite contact-reduction schedule and its terminal infected population'
    elif model == 'queue_capacity':
        contract, knowledge = 'MC-queue-capacity', 'MATH-09'
        engine = 'research_numerics.queue_capacity'
        equations = ['rho=lambda/mu<1; pi_n=(1-rho)*rho^n',
            'W=1/(mu-lambda); L=lambda*W; Wq=rho*W; Lq=lambda*Wq']
        statistics = {'utilization': stat(result['utilization'], 'ratio')}
        statistics.update({name: stat(result[name], unit) for name in ('W', 'Wq')})
        statistics.update({name: stat(result[name], 'events') for name in ('L', 'Lq')})
        selection = 'stationary first-come-first-served M/M/1 queue with independent Poisson arrivals and exponential service'
    else:
        contract, knowledge = 'MC-decision-rights', 'CONTRACT-08'
        engine = 'research_numerics.decision_rights'
        equations = (['E=clip(B*(1-alpha*e)/kP,0,1); e=clip(b*(1-E)/kA,0,1)',
            'U_P=B*(E+(1-E)*alpha*e)-kP*E^2/2; U_A=b*(beta*E+(1-E)*e)-kA*e^2/2']
            if arguments.arguments['holder'] == 'principal' else
            ['E=clip(B*(1-e)/kP,0,1); e=clip(b*(1-beta*E)/kA,0,1)',
            'U_P=B*(alpha*e+(1-e)*E)-kP*E^2/2; U_A=b*(e+(1-e)*beta*E)-kA*e^2/2'])
        equations.append('kP*kA>B*b*max(alpha,beta)')
        statistics = {name: stat(result[name], 'unit-interval information effort') for name in
            ('E', 'e', 'best_response_residual')}
        statistics.update({name: stat(result[name], unit) for name in ('principal_payoff', 'agent_payoff')})
        selection = 'unique simultaneous information-effort equilibrium at the supplied decision-right holder under contracting best responses'
    return {'result_format_version': 1, 'model': model, 'specification': spec,
        'effective_inputs': dict(arguments.arguments), 'engine': engine, 'unit': unit,
        'model_contract': contract, 'knowledge_ids': [knowledge], 'equations': equations,
        'equilibrium_selection': selection, 'statistics': statistics, 'fullresults': result,
        'provenance': {'python': sys.version.split()[0], 'numpy': np.__version__, 'scipy': scipy.__version__,
            'function': 'research_numerics.'+function.__name__,
            'precision': 'exact rational arithmetic' if model == 'tu_shapley_core' else 'float64',
            'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    a=sub.add_parser('run'); a.add_argument('spec',type=Path); a.add_argument('--output','-o',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        if args.spec.resolve()==args.output.resolve(): raise ValueError('output must differ from specification')
        raw=args.spec.read_bytes(); result=run(json.loads(raw)); result['provenance']['spec_sha256']=hashlib.sha256(raw).hexdigest()
        write_json(args.output,result)
    except (ValueError, TypeError, KeyError, OSError, ArithmeticError, RuntimeError) as exc:
        parser.exit(2,'error: '+str(exc)+'\n')

if __name__=='__main__': main()
