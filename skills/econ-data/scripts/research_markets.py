#!/usr/bin/env python3
"""Execute explicitly specified structural market models."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import pickle
import sys
import tempfile

import numpy as np
from scipy.integrate import quad
from scipy.optimize import minimize_scalar


def _num(x, name):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f"{name} must be finite and numeric")
    return float(x)


def _keys(obj, required, optional=()):
    if not isinstance(obj, dict) or not set(required) <= set(obj) or set(obj) - set(required) - set(optional):
        raise ValueError(f"required keys: {sorted(required)}; optional keys: {sorted(optional)}")


def auction(s):
    _keys(s, {'n', 'format', 'information', 'reserve', 'bids'})
    n = s['n']
    if isinstance(n, bool) or not isinstance(n, int) or n < 2:
        raise ValueError('n must be an integer of at least two')
    fmt, info, r = s['format'], s['information'], _num(s['reserve'], 'reserve')
    if fmt not in ('first', 'second') or info not in ('private', 'common') or not 0 <= r < 1:
        raise ValueError('invalid auction format, information or reserve')
    bids = np.asarray(s['bids'], dtype=float)
    if bids.ndim != 1 or not np.isfinite(bids).all() or np.any(bids < 0):
        raise ValueError('bids must be a finite nonnegative list')
    if info == 'common':
        if r != 0 or len(bids):
            raise ValueError('common-value case requires reserve zero and no bid-recovery data')
        # E[V | own x, highest rival x] = (n+2)x/(2n).
        k = (n+2)/(2*n)
        slope = k*(n-1)/n if fmt == 'first' else k
        def payoff(x, threshold):
            return quad(lambda t: ((x/n+t/2) - slope*threshold) * (n-1)*t**(n-2), 0, threshold)[0]
        x = .6
        opt = minimize_scalar(lambda t: -payoff(x, t), bounds=(0, 1), method='bounded', options={'xatol': 1e-12}) if fmt == 'first' else None
        # In a second-price auction the payment is the highest rival's bid.
        if fmt == 'second':
            def payoff2(t):
                return quad(lambda y: (x/n+y/2-slope*y)*(n-1)*y**(n-2), 0, t)[0]
            opt = minimize_scalar(lambda t: -payoff2(t), bounds=(0, 1), method='bounded', options={'xatol': 1e-12})
        return {'bid_slope': slope, 'bid_at_signal': slope*x, 'test_signal': x,
                'best_response_threshold': float(opt.x), 'best_response_error': abs(float(opt.x)-x),
                'marginal_winner_value_slope': k}
    # Independent private values U[0,1]; seller reserve is an allocation threshold.
    def bid(v):
        if fmt == 'second': return v
        return v - (v**n-r**n)/(n*v**(n-1)) if v > 0 else 0.
    def revenue(reserve):
        if fmt == 'first':
            return quad(lambda v: n*v**(n-1)*(v-(v**n-reserve**n)/(n*v**(n-1))), reserve, 1)[0]
        # Payment is reserve when exactly one value exceeds it, else second order statistic.
        return n*reserve**n*(1-reserve) + quad(lambda v: n*(n-1)*v**(n-2)*(1-v)*v, reserve, 1)[0]
    rev = revenue(r)
    welfare = n/(n+1)*(1-r**(n+1))
    best = minimize_scalar(lambda z: -revenue(z), bounds=(0, 1), method='bounded')
    recovered = []
    if len(bids):
        if r != 0:
            raise ValueError('bid inversion requires zero reserve')
        max_bid = 1. if fmt == 'second' else (n-1)/n
        if (bids > max_bid+1e-12).any(): raise ValueError('bids exceed equilibrium support')
        recovered = (bids if fmt == 'second' else bids*n/(n-1)).tolist()
    return {'bid_at_value_0_8': bid(.8) if .8 >= r else 0., 'recovered_values': recovered,
            'expected_revenue': rev, 'expected_total_surplus': welfare,
            'expected_bidder_surplus': welfare-rev, 'optimal_reserve': float(best.x),
            'optimal_revenue': float(revenue(best.x)), 'sale_probability': 1-r**n}


def auction_fit(s):
    """Recover iid uniform values from complete zero-reserve auction records."""
    _keys(s, {'n','format','records','counterfactual_reserve'})
    from scipy.stats import uniform
    n = s['n']; fmt = s['format']
    if isinstance(n, bool) or not isinstance(n, int) or n < 2 or fmt not in ('first','second'):
        raise ValueError('n >= 2 and first or second format required')
    if not isinstance(s['records'], list) or len(s['records']) < 2:
        raise ValueError('at least two complete auction records are required')
    observed, ids, allocations = [], set(), []
    for row in s['records']:
        _keys(row, {'auction_id','bids','winner_id','payment'})
        auction_id = row['auction_id']
        if not isinstance(auction_id, str) or not auction_id or auction_id in ids: raise ValueError('auction IDs must be distinct nonempty strings')
        ids.add(auction_id)
        if not isinstance(row['bids'], list) or len(row['bids']) != n: raise ValueError('each auction must contain exactly n bidder records')
        bidders, amounts = [], []
        for bid in row['bids']:
            _keys(bid, {'bidder_id','amount'})
            if not isinstance(bid['bidder_id'], str) or not bid['bidder_id']: raise ValueError('bidder IDs must be nonempty strings')
            bidders.append(bid['bidder_id']); amounts.append(_num(bid['amount'], 'bid amount'))
        if len(set(bidders)) != n or min(amounts) < 0: raise ValueError('bidders must be distinct and bids nonnegative')
        order = np.argsort(amounts)
        if amounts[order[-1]] == amounts[order[-2]]: raise ValueError('highest bid must be unique')
        winner = bidders[order[-1]]
        payment = _num(row['payment'], 'payment')
        implied = amounts[order[-1] if fmt == 'first' else order[-2]]
        if winner != row['winner_id'] or not math.isclose(payment, implied, rel_tol=1e-10, abs_tol=1e-10):
            raise ValueError('winner and payment must match the auction format and recorded bids')
        values = np.asarray(amounts) * (n/(n-1) if fmt == 'first' else 1.)
        observed.extend(values.tolist())
        allocations.append({'auction_id':auction_id,'winner_id':winner,'payment':payment,
                            'recovered_values':dict(zip(bidders, values.tolist()))})
    if max(observed) <= 0: raise ValueError('recovered values must contain a positive value')
    location, upper = uniform.fit(observed, floc=0.)
    if location != 0 or not math.isfinite(upper) or upper <= 0: raise ArithmeticError('uniform fit failed')
    reserve = _num(s['counterfactual_reserve'], 'counterfactual reserve')
    if not 0 <= reserve < upper: raise ValueError('counterfactual reserve must be below estimated support')
    normalized = auction({'n':n,'format':fmt,'information':'private','reserve':reserve/upper,'bids':[]})
    return {'observations':len(observed),'auction_count':len(allocations), 'support_upper_mle':float(upper),
            'support_upper_unbiased':float(upper*(len(observed)+1)/len(observed)),
            'valuation_location':0., 'recovered_auctions':allocations,
            'mean_observed_payment':float(np.mean([row['payment'] for row in allocations])),
            'counterfactual_reserve':reserve,'counterfactual_expected_revenue':upper*normalized['expected_revenue'],
            'counterfactual_expected_total_surplus':upper*normalized['expected_total_surplus'],
            'counterfactual_expected_bidder_surplus':upper*normalized['expected_bidder_surplus'],
            'optimal_reserve':upper*normalized['optimal_reserve'], 'optimal_revenue':upper*normalized['optimal_revenue']}


def search(s):
    _keys(s, {'offers', 'search_cost', 'outside_option'})
    n, c, outside = s['offers'], _num(s['search_cost'], 'search_cost'), _num(s['outside_option'], 'outside_option')
    if isinstance(n, bool) or not isinstance(n, int) or n < 1 or not 0 <= c <= .5 or not 0 <= outside <= 1:
        raise ValueError('offers must be positive, cost 0..0.5 and outside option 0..1')
    z = 1-math.sqrt(2*c)
    # With recall, P(final maximum <= t) is t**n below z and
    # z**n + (t-z)*sum(z**k, k=0..n-1) above z.
    if outside >= z:
        gross, count = outside, 0.
    else:
        count = sum(z**k for k in range(n))
        gross = (outside + z-outside - (z**(n+1)-outside**(n+1))/(n+1)
                 + (1-z**n)*(1-z)/2)
    return {'reservation_value': z, 'reservation_equation_error': abs((1-z)**2/2-c),
            'expected_net_surplus': gross-c*count, 'expected_searches': count,
            'expected_gross_surplus': gross}


def bargain(s):
    _keys(s, {'buyer_value', 'seller_cost', 'buyer_outside', 'seller_outside', 'buyer_weight', 'tax'})
    v, c, bo, so, w, tax = (_num(s[k], k) for k in ('buyer_value','seller_cost','buyer_outside','seller_outside','buyer_weight','tax'))
    if not 0 < w < 1 or tax < 0: raise ValueError('buyer_weight must be in (0,1); tax must be nonnegative')
    gain = v-c-tax-bo-so
    if gain <= 0:
        return {'trade': False, 'buyer_payoff': bo, 'seller_payoff': so, 'total_surplus': bo+so, 'tax_revenue': 0., 'nash_foc_error': 0.}
    buyer = bo+w*gain
    price = v-buyer
    seller = price-c-tax
    return {'trade': True, 'price': price, 'markup': price-c, 'buyer_payoff': buyer, 'seller_payoff': seller,
            'tax_revenue': tax, 'total_surplus': buyer+seller+tax,
            'nash_foc_error': abs(w/(buyer-bo)-(1-w)/(seller-so))}


def platform(s):
    _keys(s, {'intercepts', 'cross_effects', 'costs'})
    a = np.asarray(s['intercepts'], dtype=float); g = np.asarray(s['cross_effects'], dtype=float); c = np.asarray(s['costs'], dtype=float)
    if any(x.shape != (2,) or not np.isfinite(x).all() for x in (a,g,c)) or (g < 0).any() or g.sum() >= 2:
        raise ValueError('two finite intercepts, nonnegative cross effects summing to less than two, and two costs required')
    h = g.sum(); mat = np.array([[2.,-h],[-h,2.]])
    q = np.linalg.solve(mat, a-c)
    if (q <= 0).any(): raise ValueError('parameters must yield positive participation on both sides')
    p = a + g*q[::-1]-q
    profit = float((p-c)@q); surplus = (q*q/2).tolist()
    return {'participation': q.tolist(), 'prices': p.tolist(), 'profit': profit, 'consumer_surplus': surplus,
            'social_welfare': profit+sum(surplus), 'foc_max_abs_error': float(np.max(np.abs(mat@q-(a-c)))),
            'profit_hessian_max_eigenvalue': float(np.linalg.eigvalsh(-mat).max())}


def matching(s):
    from matching.games import StableMarriage
    _keys(s, {'proposers', 'receivers', 'proposer_preferences', 'receiver_preferences', 'proposer_values', 'receiver_values'})
    ps, rs = s['proposers'], s['receivers']; pp, rp = s['proposer_preferences'], s['receiver_preferences']
    pv, rv = s['proposer_values'], s['receiver_values']
    if not ps or len(set(ps)) != len(ps) or len(set(rs)) != len(rs) or len(ps) != len(rs): raise ValueError('two equally sized nonempty sets of unique IDs required')
    if set(pp) != set(ps) or set(rp) != set(rs) or set(pv) != set(ps) or set(rv) != set(rs): raise ValueError('preferences and values must cover all agents')
    for agents, others, prefs, vals in ((ps,rs,pp,pv),(rs,ps,rp,rv)):
        for i in agents:
            if len(prefs[i]) != len(others) or set(prefs[i]) != set(others) or set(vals[i]) != set(others): raise ValueError('each agent must rank and value all partners exactly once')
            values = [_num(vals[i][j], 'match value') for j in prefs[i]]
            if any(values[k] <= values[k+1] for k in range(len(values)-1)): raise ValueError('values must strictly agree with preferences')
    game = StableMarriage.create_from_dictionaries({p: pp[p] for p in ps}, {r: rp[r] for r in rs})
    solution = game.solve(optimal='suitor')
    game.check_validity()
    if not game.check_stability():
        raise ArithmeticError('stable matching produced a blocking pair')
    partner = {proposer.name: receiver.name for proposer, receiver in solution.items()}
    return {'matches': [{'proposer':p,'receiver':partner[p], 'proposer_value':pv[p][partner[p]], 'receiver_value':rv[partner[p]][p]} for p in ps],
            'total_welfare': sum(pv[p][partner[p]]+rv[partner[p]][p] for p in ps),
            'blocking_pairs': len(game.blocking_pairs),
            'proposals': sum(pp[p].index(partner[p])+1 for p in ps)}


def blp(s, *, fitted_result=None):
    """Estimate observed differentiated demand/supply and solve a new product market."""
    _keys(s, {'products','linear','nonlinear','supply','integration','solve','counterfactual','optimal_instruments','add_exogenous'},
          {'market_sizes', 'report_agent_surplus', 'agent_formulation', 'agent_data'})
    import pandas as pd
    import pyblp
    pyblp.options.verbose = False
    data = pd.DataFrame(s['products'])
    cf = s['counterfactual']
    if cf is not None:
        _keys(cf, {'keep_product_ids','firm_ids','costs','utility_shifts'}, {'entry_products','entry_xi'})
    entrants = pd.DataFrame(cf.get('entry_products', []) if cf is not None else [])
    if len(entrants) and cf['costs'] is None:
        raise ValueError('entry products require explicit counterfactual costs for every retained product and entrant')
    for name, products in (('products', data), ('entry_products', entrants)):
        ownership_columns = [c for c in products if isinstance(c, str) and
                             (c == 'ownership' or (c.startswith('ownership') and c[9:].isdigit()))]
        if ownership_columns:
            raise ValueError(f'{name} must use firm_ids for binary ownership; remove columns {ownership_columns}')
    required = {'market_ids','product_ids','firm_ids','prices','shares'}
    if not required <= set(data) or data.duplicated(['market_ids','product_ids']).any():
        raise ValueError('products must identify markets, products, firms, prices and shares')
    market_sizes = s.get('market_sizes')
    if market_sizes is not None:
        markets = {str(market) for market in data.market_ids.unique()}
        if not isinstance(market_sizes, dict) or set(market_sizes) != markets or len(markets) != data.market_ids.nunique():
            raise ValueError('market_sizes must identify every baseline market by its unique string ID')
        market_sizes = {market: _num(size, 'market size') for market, size in market_sizes.items()}
        if any(size <= 0 for size in market_sizes.values()):
            raise ValueError('market sizes must be positive potential-consumer counts')
    report_agents = s.get('report_agent_surplus', False)
    if not isinstance(report_agents, bool):
        raise ValueError('report_agent_surplus must be boolean')
    if (data.prices <= 0).any() or (data.shares <= 0).any() or (data.groupby('market_ids').shares.sum() >= 1).any():
        raise ValueError('prices and shares must be positive with positive outside shares')
    if not any(c.startswith('demand_instruments') for c in data): raise ValueError('excluded demand instruments required')
    forms = (pyblp.Formulation(s['linear']), pyblp.Formulation(s['nonlinear']) if s['nonlinear'] else None,
             pyblp.Formulation(s['supply']) if s['supply'] else None)
    agent_formulation = pyblp.Formulation(s['agent_formulation']) if s.get('agent_formulation') is not None else None
    agent_data = None
    if s.get('agent_data') is not None:
        if not isinstance(s['agent_data'], list) or not s['agent_data'] or not all(isinstance(row, dict) for row in s['agent_data']):
            raise ValueError('agent_data must be a nonempty array of individual records')
        agent_data = pd.DataFrame(s['agent_data'])
        if not {'market_ids', 'weights'} <= set(agent_data):
            raise ValueError('agent_data requires market_ids and weights for every individual')
        if s['integration'] is not None:
            raise ValueError('observed agent_data requires integration=null and explicit nodes and weights')
        availability = [name for name in agent_data if isinstance(name, str) and
                        (name == 'availability' or (name.startswith('availability') and name[12:].isdigit()))]
        if availability:
            raise ValueError('agent_data uses the common market choice set; agent-specific availability requires its own model contract')
        if agent_formulation is not None and agent_formulation._names - set(agent_data):
            raise ValueError('agent_data must supply each individual demographic variable as one scalar column')
        if 'agent_ids' in agent_data and agent_data.agent_ids.isna().any():
            raise ValueError('agent_ids must identify every supplied individual')
        weights = agent_data.weights.to_numpy(dtype=float)
        if not np.isfinite(weights).all() or (weights < 0).any():
            raise ValueError('observed agent weights must be finite nonnegative population masses')
        totals = agent_data.assign(weights=weights).groupby('market_ids', sort=False).weights.sum()
        if not np.allclose(totals.to_numpy(), 1., rtol=0, atol=1e-10):
            raise ValueError('observed agent weights must sum to one within each market')
    if agent_formulation is not None and agent_data is None:
        raise ValueError('agent_formulation requires observed agent_data')
    integration = None
    if s['nonlinear']:
        if s['integration'] is not None:
            _keys(s['integration'], {'method','size','options'})
            integration = pyblp.Integration(s['integration']['method'], s['integration']['size'], s['integration']['options'])
        elif agent_data is None:
            raise ValueError('nonlinear coefficients require integration or observed agent_data with nodes and weights')
    elif s['integration'] is not None or agent_data is not None or agent_formulation is not None:
        raise ValueError('integration and agent inputs require nonlinear coefficients')
    if not isinstance(s['add_exogenous'], bool): raise ValueError('add_exogenous must be boolean')
    if fitted_result is None:
        problem = pyblp.Problem(forms, data, agent_formulation=agent_formulation,
                               agent_data=agent_data, integration=integration, add_exogenous=s['add_exogenous'])
        if problem.agents.demographics.ndim != 2:
            raise ValueError('agent_data requires product-independent demographic columns')
        if problem.K2 and problem.agents.nodes.shape[1] != problem.K2:
            raise ValueError('agent_data requires one node column per nonlinear product characteristic, including fixed-zero sigma columns')
        options = dict(s['solve'])
        for name in ('optimization','iteration'):
            if name in options:
                cfg = options[name]; _keys(cfg, {'method','options'})
                options[name] = (pyblp.Optimization if name == 'optimization' else pyblp.Iteration)(cfg['method'], cfg['options'])
        options['error_behavior'] = 'raise'
        result = problem.solve(**options)
    else:
        if not isinstance(fitted_result, pyblp.ProblemResults):
            raise ValueError('saved fit must be an official PyBLP ProblemResults object')
        result, problem = fitted_result, fitted_result.problem
    if not result.converged or not np.asarray(result.fp_converged).all(): raise ArithmeticError('estimation or contraction did not converge')

    def check_surplus_utility(economy):
        # PyBLP's logsum uses the first product's price derivative for each agent.
        columns = [*economy._X1_formulations, *economy._X2_formulations]
        derivatives = [column.differentiate('prices') for column in columns]
        dx = np.column_stack([
            np.broadcast_to(np.asarray(column.evaluate_derivative('prices', economy.products)).ravel(), (economy.N,))
            for column in columns
        ])
        for market in economy.unique_market_ids:
            rows = np.flatnonzero(economy.products.market_ids.ravel() == market)
            agents = economy.agents[economy.agents.market_ids.ravel() == market]
            random_coefficients = result.sigma @ agents.nodes.T
            if economy.D:
                random_coefficients += result.pi @ agents.demographics.T
            coefficients = np.vstack((np.broadcast_to(result.beta, (economy.K1, len(agents))), random_coefficients))
            slopes = dx[rows, :economy.K1] @ result.beta + dx[rows, economy.K1:] @ random_coefficients
            if not np.isfinite(slopes).all() or not (slopes < 0).all():
                raise ValueError(f'consumer surplus requires finite negative price utility derivatives in market {market!r}')
            for coefficient in coefficients.T:
                slope = sum(float(value)*derivative for value, derivative in zip(coefficient, derivatives) if value != 0).simplify()
                if slope == 0:
                    raise ValueError(f'consumer surplus requires nonzero price utility derivatives in market {market!r}')
                if any(symbol.name == 'prices' for symbol in slope.free_symbols):
                    attributes = [symbol for symbol in slope.free_symbols if symbol.name != 'prices']
                    for row in rows:
                        fixed = {symbol: float(economy.products[symbol.name][row, 0]) for symbol in attributes}
                        if any(symbol.name == 'prices' for symbol in slope.subs(fixed).simplify().free_symbols):
                            raise ValueError(f'consumer surplus requires price-affine utility in market {market!r}')
            if not np.allclose(slopes, slopes[:1], rtol=1e-10, atol=0):
                raise ValueError(f'consumer surplus requires a common price derivative across products for each agent in market {market!r}')

    check_surplus_utility(problem)
    costs = result.compute_costs()
    fitted = result.compute_shares()
    error = float(np.max(np.abs(fitted.ravel()-data.shares.to_numpy())))
    if error > 1e-8: raise ArithmeticError('share inversion residual exceeds 1e-8')
    def arr(x):
        def clean(v):
            if isinstance(v, list): return [clean(i) for i in v]
            return None if isinstance(v, float) and not math.isfinite(v) else v
        return clean(np.asarray(x).tolist())
    consumer_surpluses = result.compute_consumer_surpluses()

    def agent_surpluses(economy, fitted):
        values = fitted.compute_consumer_surpluses(keep_all=True)
        rows = []
        for m, market in enumerate(economy.unique_market_ids):
            agents = economy.agents[economy.agents.market_ids.ravel() == market]
            deviations = agents.nodes @ result.sigma.T
            if economy.D:
                deviations += agents.demographics @ result.pi.T
            for i, agent in enumerate(agents):
                row = {'market': str(market), 'agent': i, 'weight': float(agent.weights[0]),
                       'consumer_surplus': float(values[m, i])}
                if agents.agent_ids.shape[1]:
                    row['agent_id'] = arr(agent.agent_ids[0])
                row.update({f'demographic_{label}': float(agent.demographics[d])
                            for d, label in enumerate(result.pi_labels)})
                row.update({f'taste_deviation_{label}': float(deviations[i, k])
                            for k, label in enumerate(result.sigma_labels)})
                rows.append(row)
        return rows

    out = {'beta':arr(result.beta),'sigma':arr(result.sigma),'pi':arr(result.pi),'rho':arr(result.rho),'gamma':arr(result.gamma),
           'parameter_labels': {name: [str(label) for label in getattr(result, name+'_labels')]
                                for name in ('beta', 'sigma', 'pi', 'rho', 'gamma')},
           'parameter_status': {name: np.where(
               np.equal(*getattr(result, name+'_bounds')), 'fixed', 'estimated').tolist()
               for name in ('beta', 'sigma', 'pi', 'rho', 'gamma')},
           'versions': {'pyblp': pyblp.__version__},
           'standard_errors': {name: arr(getattr(result, name+'_se')) for name in ('beta', 'sigma', 'pi', 'rho', 'gamma')},
           'objective':float(result.objective),'gradient_norm':(float(result.projected_gradient_norm) if np.isfinite(result.projected_gradient_norm).all() else None),
           'share_max_abs_error':error,'elasticities':arr(result.compute_elasticities()),
           'diversion_ratios':arr(result.compute_diversion_ratios()),'markups':arr(result.compute_markups()),
           'marginal_costs':arr(costs),'consumer_surpluses':arr(consumer_surpluses),
           'shares':arr(fitted), 'product_profits':arr(result.compute_profits(costs=costs)), 'optimal_instruments':None}
    if problem.K2:
        out['agent_population'] = {
            'market_ids': arr(problem.agents.market_ids.ravel()),
            'agent_ids': arr(problem.agents.agent_ids.ravel()),
            'nodes': arr(problem.agents.nodes), 'weights': arr(problem.agents.weights.ravel()),
            'demographic_labels': list(result.pi_labels), 'demographics': arr(problem.agents.demographics)}
    if not isinstance(s['optimal_instruments'], bool): raise ValueError('optimal_instruments must be boolean')
    market_ids = sorted(data.market_ids.unique().tolist())
    profits = np.asarray(out['product_profits']).ravel()
    cs = np.asarray(consumer_surpluses).ravel()
    out['welfare'] = [{'market_ids':market, 'consumer_surplus':float(cs[i]),
                       'producer_surplus':float(profits[data.market_ids.to_numpy() == market].sum()),
                       'social_welfare':float(cs[i]+profits[data.market_ids.to_numpy() == market].sum())}
                      for i,market in enumerate(market_ids)]
    if report_agents:
        out['agent_welfare'] = agent_surpluses(problem, result)
    if s['optimal_instruments']:
        opt = result.compute_optimal_instruments(method='approximate')
        out['optimal_instruments']={'demand':arr(opt.demand_instruments),'supply':arr(opt.supply_instruments)}
    if cf is not None:
        mask = data.product_ids.isin(cf['keep_product_ids']).to_numpy()
        new = data.loc[mask].copy().reset_index(drop=True)
        entry_xi = np.asarray(cf.get('entry_xi', []), dtype=float)
        if len(entry_xi) != len(entrants) or not np.isfinite(entry_xi).all(): raise ValueError('entry_xi must contain one finite structural utility shock per entrant')
        if len(entrants):
            if not required <= set(entrants) or not set(entrants.market_ids).issubset(set(data.market_ids)):
                raise ValueError('entry records require product fields and existing market IDs')
            new = pd.concat([new, entrants], ignore_index=True)
            if new.duplicated(['market_ids','product_ids']).any(): raise ValueError('counterfactual market/product identifiers must be unique')
        costs2 = costs.ravel()[mask].copy() if cf['costs'] is None else np.asarray(cf['costs'], dtype=float)
        if costs2.ndim != 1 or not np.isfinite(costs2).all():
            raise ValueError('counterfactual costs must be a finite vector or null for recovered incumbent costs')
        if len(new) != len(cf['firm_ids']) or len(new) != len(costs2) or len(new) != len(cf['utility_shifts']) or not len(new):
            raise ValueError('counterfactual arrays must match retained product observations')
        new['firm_ids'] = cf['firm_ids']
        xi = np.r_[(result.delta - pyblp.build_matrix(forms[0], data) @ result.beta)[mask].ravel(), entry_xi][:,None] + np.asarray(cf['utility_shifts'])[:,None]
        agent_data = None
        counterfactual_agent_formulation = None
        if problem.K2:
            retained_agents = np.isin(problem.agents.market_ids.ravel(), new.market_ids.unique())
            agent_data = {name: problem.agents[name][retained_agents].copy()
                          for name in ('market_ids', 'nodes', 'weights', 'agent_ids') if problem.agents[name].shape[1]}
            if problem.D:
                # Preserve the fitted demographic design when a market's exit removes categorical levels.
                names = [f'demographic_{d}' for d in range(problem.D)]
                demographics = problem.agents.demographics[retained_agents]
                agent_data.update({name: demographics[:, d] for d, name in enumerate(names)})
                counterfactual_agent_formulation = pyblp.Formulation('0 + ' + ' + '.join(names))
        sim = pyblp.Simulation(forms[:2], new, beta=result.beta, sigma=result.sigma if s['nonlinear'] else None,
                               pi=result.pi if problem.D else None, agent_formulation=counterfactual_agent_formulation,
                               rho=result.rho if 'rho' in s['solve'] else None, xi=xi, agent_data=agent_data)
        check_surplus_utility(sim)
        change = sim.replace_endogenous(costs=costs2[:,None], prices=new.prices.to_numpy()[:,None],
                                        iteration=pyblp.Iteration('simple',{'atol':1e-12}), error_behavior='raise')
        if not np.asarray(change.fp_converged).all(): raise ArithmeticError('counterfactual equilibrium did not converge')
        grad=float(max(np.max(np.abs(x)) for market in change.profit_gradients.values() for x in market.values()))
        eigen=float(max(np.max(x) for market in change.profit_hessian_eigenvalues.values() for x in market.values()))
        if grad > 1e-8 or eigen > 1e-8: raise ArithmeticError('counterfactual profit FOC or SOC failed')
        pdout=change.product_data
        prices=np.asarray(pdout.prices).ravel(); shares=np.asarray(pdout.shares).ravel()
        cf_consumer_surpluses = change.compute_consumer_surpluses()
        cf_cs = np.asarray(cf_consumer_surpluses).ravel()
        cf_profit = (prices-costs2)*shares
        cf_markets = sorted(new.market_ids.unique().tolist())
        cf_welfare = [{'market_ids':market, 'consumer_surplus':float(cf_cs[i]),
                       'producer_surplus':float(cf_profit[new.market_ids.to_numpy() == market].sum()),
                       'social_welfare':float(cf_cs[i]+cf_profit[new.market_ids.to_numpy() == market].sum())}
                      for i,market in enumerate(cf_markets)]
        out['counterfactual']={'welfare':cf_welfare, 'market_ids':new.market_ids.tolist(),
                               'product_ids':new.product_ids.tolist(),'firm_ids':new.firm_ids.tolist(),
                               'cost_source': ('recovered_baseline_marginal_costs' if cf['costs'] is None
                                               else 'specified_counterfactual_marginal_costs'),
                               'prices':prices.tolist(),'shares':shares.tolist(),'marginal_costs':costs2.tolist(),
                               'product_profits':((prices-costs2)*shares).tolist(),
                               'consumer_surpluses':arr(cf_consumer_surpluses),
                               'profit_gradient_max_abs':grad,'profit_hessian_max_eigenvalue':eigen}
        if problem.K2:
            out['counterfactual']['agent_population_rows'] = np.flatnonzero(retained_agents).tolist()
        if report_agents:
            counterfactual_agents = {(row['market'], row['agent']): row for row in agent_surpluses(sim, change)}
            remaining_markets = {str(market) for market in sim.unique_market_ids}
            out['counterfactual']['agent_welfare'] = [
                counterfactual_agents[(row['market'], row['agent'])] if row['market'] in remaining_markets
                else {**row, 'consumer_surplus': 0.}
                for row in out['agent_welfare']]
    if market_sizes is not None:
        quantities = ('consumer_surplus', 'producer_surplus', 'social_welfare')
        for fitted in (out, out.get('counterfactual')):
            if fitted is None:
                continue
            welfare = {str(row['market_ids']): row for row in fitted['welfare']}
            # A market with all inside products removed retains its population
            # at the normalized outside option, with zero inside profit and surplus.
            fitted['welfare_totals'] = [
                {'market': market, 'population': size,
                 **{key: size * welfare.get(market, {}).get(key, 0.) for key in quantities}}
                for market, size in market_sizes.items()]
            fitted['aggregate_welfare'] = {
                'population': sum(market_sizes.values()),
                **{key: sum(row[key] for row in fitted['welfare_totals']) for key in quantities}}
        if out.get('counterfactual') is not None:
            out['aggregate_welfare_change'] = {
                key: out['counterfactual']['aggregate_welfare'][key] - out['aggregate_welfare'][key]
                for key in quantities}
    if fitted_result is None:
        # PyBLP's native persistence uses pickle; keep the fit in the same atomic
        # JSON result as its adopted specification and public numerical outputs.
        native = pickle.dumps(result, protocol=5)
        out['native_fit'] = {'format': 'python-pickle-v5', 'package': 'pyblp',
            'version': pyblp.__version__, 'sha256': hashlib.sha256(native).hexdigest(),
            'fit_specification_sha256': blp_fit_identity(s),
            'data': base64.b64encode(native).decode('ascii')}
    return out


def blp_fit_identity(specification):
    """Bind the native fit to the data, model, integration and estimation inputs."""
    fitted = {key: value for key, value in specification.items()
              if key not in {'counterfactual', 'market_sizes', 'report_agent_surplus', 'optimal_instruments'}}
    return hashlib.sha256(json.dumps(fitted, sort_keys=True, allow_nan=False,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def blp_counterfactual(saved, scenario):
    """Reuse a project-generated native fit for a new economic intervention."""
    import pyblp
    if saved.get('model') != 'blp' or not isinstance(scenario, dict):
        raise ValueError('counterfactual requires a saved BLP result and a scenario object')
    native = saved.get('native_fit', {})
    baseline = saved['options']['baseline']
    if (native.get('format') != 'python-pickle-v5' or native.get('package') != 'pyblp'
            or native.get('version') != pyblp.__version__
            or native.get('fit_specification_sha256') != blp_fit_identity(baseline)):
        raise ValueError('saved native fit must match the adopted BLP specification and installed PyBLP version')
    raw = base64.b64decode(native['data'], validate=True)
    if hashlib.sha256(raw).hexdigest() != native.get('sha256'):
        raise ValueError('saved native fit content differs from its result binding')
    fitted = pickle.loads(raw)
    specification = {'model': 'blp', 'baseline': {**baseline, 'counterfactual': scenario},
        'scenario': None, 'unit': saved['adopted']['unit'], 'sources': saved['adopted']['sources']}
    result = solve(specification, fitted_result=fitted)
    result['fit_source'] = {key: native[key] for key in ('package', 'version', 'sha256', 'fit_specification_sha256')}
    return result


def blp_displays(result, specification, unit):
    """Project saved estimates and scenario quantities into the common gallery rows."""
    contract = {'model_contract': 'MC-pyblp-bertrand', 'unit': 'see row-specific unit'}
    parameter_rows = []
    for group in ('beta', 'sigma', 'pi', 'rho', 'gamma'):
        values = np.asarray(result[group])
        errors = np.asarray(result['standard_errors'][group], dtype=object)
        status = np.asarray(result['parameter_status'][group])
        labels = result['parameter_labels'][group]
        for index in np.ndindex(values.shape):
            if group == 'sigma' and index[1] > index[0]:
                continue
            if group == 'sigma':
                label = ', '.join(labels[i] for i in index)
            elif group == 'pi':
                label = result['parameter_labels']['sigma'][index[0]] + ', ' + labels[index[1]]
            else:
                label = labels[index[0]]
            parameter_rows.append({'parameter': f'{group}[{label}]', 'value': values[index].item(),
                                   'status': status[index].item(), 'std_error': errors[index],
                                   'unit': ('correlation' if group == 'rho' else
                                            'cost per regressor unit' if group == 'gamma' else
                                            'utility per product-characteristic and demographic unit' if group == 'pi' else
                                            'utility per regressor unit')})
    diagnostic_rows = [{'diagnostic': name, 'value': result[name], 'unit': unit_name}
                       for name, unit_name in (('objective', 'GMM criterion'),
                                               ('gradient_norm', 'criterion per parameter unit'),
                                               ('share_max_abs_error', 'market share'))
                       if result[name] is not None]
    counterfactual = result.get('counterfactual')
    if counterfactual is not None:
        diagnostic_rows.extend({'diagnostic': name, 'value': counterfactual[name], 'unit': unit_name}
                               for name, unit_name in (('profit_gradient_max_abs', 'profit per price unit'),
                                                       ('profit_hessian_max_eigenvalue', 'profit per squared price unit')))
    product_rows = []
    for i, product in enumerate(specification['products']):
        product_rows.append({'scenario': 'baseline', 'market': str(product['market_ids']),
                             'product': str(product['product_ids']), 'price': product['prices'],
                             'share': result['shares'][i][0], 'cost': result['marginal_costs'][i][0],
                             'profit': result['product_profits'][i][0]})
    if counterfactual is not None:
        for i, product in enumerate(counterfactual['product_ids']):
            product_rows.append({'scenario': 'counterfactual', 'market': str(counterfactual['market_ids'][i]),
                                 'product': str(product), 'price': counterfactual['prices'][i],
                                 'share': counterfactual['shares'][i], 'cost': counterfactual['marginal_costs'][i],
                                 'profit': counterfactual['product_profits'][i]})
    welfare_rows = []
    for scenario, fitted in (('baseline', result), ('counterfactual', counterfactual)):
        if fitted is None:
            continue
        for market in fitted['welfare']:
            for quantity in ('consumer_surplus', 'producer_surplus', 'social_welfare'):
                welfare_rows.append({'scenario': scenario, 'market': str(market['market_ids']),
                                     'quantity': quantity, 'value': market[quantity],
                                     'unit': unit+' per potential consumer'})
    displays = {
        'parameters': {'kind': 'table', 'title': 'Demand and supply parameters', 'rows': parameter_rows,
                       'columns': [{'key': key, 'label': label, 'unit': ''} for key, label in
                                   (('parameter', 'Parameter'), ('status', 'Status'), ('value', 'Value'), ('std_error', 'Standard error'), ('unit', 'Unit'))],
                       'metadata': {**contract, 'report_role': 'parameters',
                                    'inference': 'Official ProblemResults bounds identify fixed parameters; standard errors retain the official saved values'},
                       'display': {'plot_type': 'table', 'formats': {'value': '.4f', 'std_error': '.4f'}}},
        'model_fit': {'kind': 'table', 'title': 'Demand fit and equilibrium diagnostics', 'rows': diagnostic_rows,
                      'columns': [{'key': key, 'label': label, 'unit': ''} for key, label in
                                  (('diagnostic', 'Diagnostic'), ('value', 'Value'), ('unit', 'Unit'))],
                      'metadata': {**contract, 'report_role': 'model_fit'}, 'display': {'plot_type': 'table'}},
        'equilibrium_products': {'kind': 'counterfactual', 'title': 'Product equilibrium outcomes', 'rows': product_rows,
                                 'columns': [{'key': key, 'label': label, 'unit': units} for key, label, units in
                                             (('scenario', 'Scenario', ''), ('market', 'Market', ''), ('product', 'Product', ''),
                                              ('price', 'Price', unit), ('share', 'Market share', 'share'),
                                              ('cost', 'Marginal cost', unit), ('profit', 'Profit', unit+' per potential consumer'))],
                                 'metadata': {**contract, 'report_role': 'counterfactual', 'unit': 'see column-specific unit'}, 'display': {'plot_type': 'table'}},
        'welfare': {'kind': 'counterfactual', 'title': 'Market welfare', 'rows': welfare_rows,
                    'columns': [{'key': key, 'label': label, 'unit': ''} for key, label in
                                (('scenario', 'Scenario'), ('market', 'Market'), ('quantity', 'Quantity'), ('value', 'Value'), ('unit', 'Unit'))],
                    'metadata': {**contract, 'report_role': 'welfare', 'unit': unit+' per potential consumer',
                                 'population': 'Potential consumers within each market'},
                    'display': {'plot_type': 'bar', 'x': 'market', 'y': 'value', 'series': 'scenario', 'facet': 'quantity'}}}
    if 'aggregate_welfare' in result:
        rows = []
        for scenario, fitted in (('baseline', result), ('counterfactual', counterfactual)):
            if fitted is None:
                continue
            for row in [*fitted['welfare_totals'], {'market': 'All markets', **fitted['aggregate_welfare']}]:
                rows.extend({'scenario': scenario, 'market': row['market'], 'population': row['population'],
                             'quantity': key, 'value': row[key], 'unit': unit}
                            for key in ('consumer_surplus', 'producer_surplus', 'social_welfare'))
        displays['welfare_totals'] = {
            'kind': 'counterfactual', 'title': 'Population-weighted market welfare', 'rows': rows,
            'columns': [{'key': key, 'label': label, 'unit': ''} for key, label in
                        (('scenario', 'Scenario'), ('market', 'Market'), ('population', 'Potential consumers'),
                         ('quantity', 'Quantity'), ('value', 'Total'), ('unit', 'Unit'))],
            'metadata': {**contract, 'report_role': 'welfare', 'unit': unit,
                         'population': 'The same potential consumers in all baseline markets',
                         'weights': specification['market_sizes'],
                         'welfare_definition': 'Sum of market population times per-consumer surplus; social welfare equals consumer plus producer surplus'},
            'display': {'plot_type': 'table', 'formats': {'value': '.4f'}}}
    if 'agent_welfare' in result:
        rows = [{**row, 'scenario': scenario} for scenario, fitted in
                (('baseline', result), ('counterfactual', counterfactual)) if fitted is not None
                for row in fitted['agent_welfare']]
        taste_keys = [key for key in rows[0] if key.startswith('taste_deviation_')]
        demographic_keys = [key for key in rows[0] if key.startswith('demographic_')]
        agent_ids = [('agent_id', 'Observed agent ID', '')] if 'agent_id' in rows[0] else []
        displays['consumer_types'] = {
            'kind': 'counterfactual', 'title': 'Consumer surplus by agent', 'rows': rows,
            'columns': [{'key': key, 'label': label, 'unit': units} for key, label, units in
                        [('scenario', 'Scenario', ''), ('market', 'Market', ''), ('agent', 'Agent index', ''),
                         *agent_ids, ('weight', 'Integration weight', 'share'),
                         *[(key, key.removeprefix('demographic_'), 'as specified by agent_formulation') for key in demographic_keys],
                         *[(key, key.removeprefix('taste_deviation_')+' taste deviation', 'utility per characteristic unit') for key in taste_keys],
                         ('consumer_surplus', 'Consumer surplus', unit+' per consumer of this type')]],
            'metadata': {**contract, 'report_role': 'welfare', 'unit': unit+' per consumer of this type',
                         'population': 'The same saved agents within each market; demographic coordinates use the fitted agent formulation',
                         'weights': 'Saved integration weights; taste deviations equal Sigma nu + Pi d'},
            'display': {'plot_type': 'table', 'formats': {'consumer_surplus': '.4f', 'weight': '.4f'}}}
    return displays


def solve(spec, *, fitted_result=None):
    _keys(spec, {'model','baseline','scenario','unit','sources'})
    model = spec['model']; methods = {'auction':auction, 'search':search, 'bargaining':bargain, 'platform':platform, 'matching':matching, 'equity':None, 'blp':blp, 'auction_fit':auction_fit}
    if fitted_result is not None and model != 'blp':
        raise ValueError('native BLP reuse requires model=blp')
    if model not in methods or not isinstance(spec['unit'], str) or not spec['unit'] or not isinstance(spec['sources'], list) or not spec['sources']:
        raise ValueError('supply a supported model, unit and sources')
    if any(not isinstance(x, dict) or not (x.get('description') or x.get('path') or x.get('url')) for x in spec['sources']): raise ValueError('each source requires description, path or URL')
    if model == 'equity':
        import equity
        if spec['baseline'].get('model') != 'cournot':
            import pyblp
            pyblp.options.verbose = False
        # The adopted equity specification owns both baseline and counterfactual.
        if spec['scenario'] is not None: raise ValueError('equity scenario belongs in the adopted baseline specification')
        base = equity.fit(spec['baseline']); changed = None
        indicator = base.get('objective', base['baseline']['markets'][0]['best_response_max_abs_error'] if base.get('model') == 'capacity_constrained_cournot' else 0.)
        key = 'gmm_objective' if base.get('engine') == 'pyblp' else 'best_response_error'
    elif model == 'blp':
        if spec['scenario'] is not None: raise ValueError('BLP counterfactual belongs in baseline.counterfactual')
        base, changed = blp(spec['baseline'], fitted_result=fitted_result), None
        key, indicator = 'objective', base['objective']
    else:
        if not isinstance(spec['scenario'], dict): raise ValueError('scenario must be a complete model specification')
        base, changed = methods[model](spec['baseline']), methods[model](spec['scenario'])
        key = ({'search':'expected_net_surplus', 'bargaining':'total_surplus', 'platform':'social_welfare', 'matching':'total_welfare', 'auction_fit':'support_upper_mle'}[model] if model != 'auction' else ('expected_revenue' if spec['baseline']['information'] == 'private' else 'bid_slope'))
        indicator = base[key]
    statistic_unit = 'dimensionless' if key in {'objective', 'gmm_objective', 'bid_slope'} else spec['unit']
    if model == 'equity' and key == 'best_response_error':
        statistic_unit = spec['baseline']['quantity_unit']
    output = {'model': model, 'engine': ('equity.fit' if model == 'equity' else 'pyblp' if model == 'blp' else
                                      'matching.games.StableMarriage.solve' if model == 'matching' else 'numpy/scipy'),
            'adopted': {'unit':spec['unit'], 'sources':spec['sources']}, 'options': {'baseline':spec['baseline'], 'scenario':spec['scenario']},
            'statistics': {key:{'value':float(indicator),'unit':statistic_unit}}, 'baseline':base, 'scenario':changed}
    if model == 'blp':
        if 'native_fit' in base:
            output['native_fit'] = base.pop('native_fit')
        output['execution'] = {'estimation': 'executed' if fitted_result is None else 'reused',
            'counterfactual': 'executed' if spec['baseline']['counterfactual'] is not None else 'not_requested'}
        output['displays'] = blp_displays(base, spec['baseline'], spec['unit'])
        for scenario, fitted in (('baseline', base), ('counterfactual', base.get('counterfactual'))):
            if fitted is not None and 'aggregate_welfare' in fitted:
                output['statistics'].update({f'{scenario}_total_{key}': {'value': value, 'unit': spec['unit']}
                                             for key, value in fitted['aggregate_welfare'].items() if key != 'population'})
        output['statistics'].update({f'total_{key}_change': {'value': value, 'unit': spec['unit']}
                                     for key, value in base.get('aggregate_welfare_change', {}).items()})
    return output


def _write(path, data):
    encoding = {}
    if data.get('model') == 'equity':
        from equity import json_default
        encoding['default'] = json_default
    payload = json.dumps(data, indent=2, allow_nan=False, **encoding)+'\n'; path = Path(path)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix='.'+path.name+'.', delete=False) as stream:
            temp = Path(stream.name); stream.write(payload)
        os.replace(temp,path)
    finally:
        if temp is not None: temp.unlink(missing_ok=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='operation',required=True)
    run = sub.add_parser('run'); run.add_argument('spec',type=Path); run.add_argument('--output',type=Path,required=True)
    reuse = sub.add_parser('counterfactual'); reuse.add_argument('result',type=Path)
    reuse.add_argument('scenario',type=Path); reuse.add_argument('--output',type=Path,required=True)
    args = p.parse_args(argv)
    try:
        if args.operation == 'run':
            if args.spec.resolve() == args.output.resolve():
                raise ValueError('output must differ from the specification path')
            raw = args.spec.read_bytes()
            specification = json.loads(raw)
            if isinstance(specification, dict) and specification.get('model') == 'equity':
                from equity import data_input_paths
                if args.output.resolve() in data_input_paths(specification['baseline']):
                    raise ValueError('output must preserve the adopted equity model data')
            result = solve(specification)
            result['provenance'] = {'spec_path':str(args.spec.resolve()), 'spec_sha256':hashlib.sha256(raw).hexdigest()}
        else:
            if args.output.resolve() in {args.result.resolve(), args.scenario.resolve()}:
                raise ValueError('counterfactual output must preserve its saved fit and scenario inputs')
            raw, scenario = args.result.read_bytes(), args.scenario.read_bytes()
            result = blp_counterfactual(json.loads(raw), json.loads(scenario))
            result['fit_source'].update(path=str(args.result.resolve()), result_sha256=hashlib.sha256(raw).hexdigest())
            result['provenance'] = {'scenario_path':str(args.scenario.resolve()),
                'scenario_sha256':hashlib.sha256(scenario).hexdigest(),
                'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        _write(args.output,result)
    except (ValueError, TypeError, KeyError, OSError, ArithmeticError, pickle.UnpicklingError, EOFError) as exc:
        p.exit(2,f'error: {exc}\n')

if __name__ == '__main__': main()
