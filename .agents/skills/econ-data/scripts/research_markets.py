#!/usr/bin/env python3
"""Execute explicitly specified structural market models and synthetic cases."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
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
    rank = {r:{p:i for i,p in enumerate(rp[r])} for r in rs}
    free = list(ps); next_choice = {p:0 for p in ps}; held = {}
    while free:
        p = free.pop(0); r = pp[p][next_choice[p]]; next_choice[p] += 1
        if r not in held: held[r] = p
        elif rank[r][p] < rank[r][held[r]]: free.append(held[r]); held[r] = p
        else: free.append(p)
    partner = {p:r for r,p in held.items()}
    blocking = [(p,r) for p in ps for r in rs if pp[p].index(r) < pp[p].index(partner[p]) and rank[r][p] < rank[r][held[r]]]
    if blocking: raise ArithmeticError('deferred acceptance produced a blocking pair')
    return {'matches': [{'proposer':p,'receiver':partner[p], 'proposer_value':pv[p][partner[p]], 'receiver_value':rv[partner[p]][p]} for p in ps],
            'total_welfare': sum(pv[p][partner[p]]+rv[partner[p]][p] for p in ps), 'blocking_pairs': len(blocking), 'proposals': sum(next_choice.values())}


def blp(s):
    """Estimate observed differentiated demand/supply and solve a new product market."""
    _keys(s, {'products','linear','nonlinear','supply','integration','solve','counterfactual','optimal_instruments','add_exogenous'})
    import pandas as pd
    import pyblp
    pyblp.options.verbose = False
    data = pd.DataFrame(s['products'])
    required = {'market_ids','product_ids','firm_ids','prices','shares'}
    if not required <= set(data) or data.duplicated(['market_ids','product_ids']).any():
        raise ValueError('products must identify markets, products, firms, prices and shares')
    if (data.prices <= 0).any() or (data.shares <= 0).any() or (data.groupby('market_ids').shares.sum() >= 1).any():
        raise ValueError('prices and shares must be positive with positive outside shares')
    if not any(c.startswith('demand_instruments') for c in data): raise ValueError('excluded demand instruments required')
    forms = (pyblp.Formulation(s['linear']), pyblp.Formulation(s['nonlinear']) if s['nonlinear'] else None,
             pyblp.Formulation(s['supply']) if s['supply'] else None)
    integration = None
    if s['nonlinear']:
        _keys(s['integration'], {'method','size','options'})
        integration = pyblp.Integration(s['integration']['method'], s['integration']['size'], s['integration']['options'])
    elif s['integration'] is not None: raise ValueError('integration requires nonlinear coefficients')
    if not isinstance(s['add_exogenous'], bool): raise ValueError('add_exogenous must be boolean')
    problem = pyblp.Problem(forms, data, integration=integration, add_exogenous=s['add_exogenous'])
    options = dict(s['solve'])
    for name in ('optimization','iteration'):
        if name in options:
            cfg = options[name]; _keys(cfg, {'method','options'})
            options[name] = (pyblp.Optimization if name == 'optimization' else pyblp.Iteration)(cfg['method'], cfg['options'])
    options['error_behavior'] = 'raise'
    result = problem.solve(**options)
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
    out = {'beta':arr(result.beta),'sigma':arr(result.sigma),'rho':arr(result.rho),'gamma':arr(result.gamma),
           'standard_errors': {'beta':arr(result.beta_se), 'sigma':arr(result.sigma_se), 'rho':arr(result.rho_se), 'gamma':arr(result.gamma_se)},
           'objective':float(result.objective),'gradient_norm':(float(result.projected_gradient_norm) if np.isfinite(result.projected_gradient_norm).all() else None),
           'share_max_abs_error':error,'elasticities':arr(result.compute_elasticities()),
           'diversion_ratios':arr(result.compute_diversion_ratios()),'markups':arr(result.compute_markups()),
           'marginal_costs':arr(costs),'consumer_surpluses':arr(consumer_surpluses),
           'shares':arr(fitted), 'product_profits':arr(result.compute_profits(costs=costs)), 'optimal_instruments':None}
    if not isinstance(s['optimal_instruments'], bool): raise ValueError('optimal_instruments must be boolean')
    market_ids = sorted(data.market_ids.unique().tolist())
    profits = np.asarray(result.compute_profits(costs=costs)).ravel()
    cs = np.asarray(consumer_surpluses).ravel()
    out['welfare'] = [{'market_ids':market, 'consumer_surplus':float(cs[i]),
                       'producer_surplus':float(profits[data.market_ids.to_numpy() == market].sum()),
                       'social_welfare':float(cs[i]+profits[data.market_ids.to_numpy() == market].sum())}
                      for i,market in enumerate(market_ids)]
    if s['optimal_instruments']:
        opt = result.compute_optimal_instruments(method='approximate')
        out['optimal_instruments']={'demand':arr(opt.demand_instruments),'supply':arr(opt.supply_instruments)}
    cf = s['counterfactual']
    if cf is not None:
        _keys(cf, {'keep_product_ids','firm_ids','costs','utility_shifts'}, {'entry_products','entry_xi'})
        mask = data.product_ids.isin(cf['keep_product_ids']).to_numpy()
        new = data.loc[mask].copy().reset_index(drop=True)
        entrants = pd.DataFrame(cf.get('entry_products', []))
        entry_xi = np.asarray(cf.get('entry_xi', []), dtype=float)
        if len(entry_xi) != len(entrants) or not np.isfinite(entry_xi).all(): raise ValueError('entry_xi must contain one finite structural utility shock per entrant')
        if len(entrants):
            if not required <= set(entrants) or not set(entrants.market_ids).issubset(set(data.market_ids)):
                raise ValueError('entry records require product fields and existing market IDs')
            new = pd.concat([new, entrants], ignore_index=True)
            if new.duplicated(['market_ids','product_ids']).any(): raise ValueError('counterfactual market/product identifiers must be unique')
        if len(new) != len(cf['firm_ids']) or len(new) != len(cf['costs']) or len(new) != len(cf['utility_shifts']) or not len(new):
            raise ValueError('counterfactual arrays must match retained product observations')
        new['firm_ids'] = cf['firm_ids']
        xi = np.r_[(result.delta - pyblp.build_matrix(forms[0], data) @ result.beta)[mask].ravel(), entry_xi][:,None] + np.asarray(cf['utility_shifts'])[:,None]
        agent_data = None
        if problem.K2:
            retained_agents = np.isin(problem.agents.market_ids.ravel(), new.market_ids.unique())
            agent_data = {name: problem.agents[name][retained_agents].copy() for name in ('market_ids', 'nodes', 'weights')}
        sim = pyblp.Simulation(forms[:2], new, beta=result.beta, sigma=result.sigma if s['nonlinear'] else None,
                               rho=result.rho if 'rho' in s['solve'] else None, xi=xi, agent_data=agent_data)
        check_surplus_utility(sim)
        change = sim.replace_endogenous(costs=np.asarray(cf['costs'])[:,None], prices=new.prices.to_numpy()[:,None],
                                        iteration=pyblp.Iteration('simple',{'atol':1e-12}), error_behavior='raise')
        if not np.asarray(change.fp_converged).all(): raise ArithmeticError('counterfactual equilibrium did not converge')
        grad=float(max(np.max(np.abs(x)) for market in change.profit_gradients.values() for x in market.values()))
        eigen=float(max(np.max(x) for market in change.profit_hessian_eigenvalues.values() for x in market.values()))
        if grad > 1e-8 or eigen > 1e-8: raise ArithmeticError('counterfactual profit FOC or SOC failed')
        pdout=change.product_data
        prices=np.asarray(pdout.prices).ravel(); shares=np.asarray(pdout.shares).ravel()
        costs2=np.asarray(cf['costs'])
        cf_consumer_surpluses = change.compute_consumer_surpluses()
        cf_cs = np.asarray(cf_consumer_surpluses).ravel()
        cf_profit = (prices-costs2)*shares
        cf_markets = sorted(new.market_ids.unique().tolist())
        cf_welfare = [{'market_ids':market, 'consumer_surplus':float(cf_cs[i]),
                       'producer_surplus':float(cf_profit[new.market_ids.to_numpy() == market].sum()),
                       'social_welfare':float(cf_cs[i]+cf_profit[new.market_ids.to_numpy() == market].sum())}
                      for i,market in enumerate(cf_markets)]
        out['counterfactual']={'welfare':cf_welfare, 'product_ids':new.product_ids.tolist(),'firm_ids':new.firm_ids.tolist(),
                               'prices':prices.tolist(),'shares':shares.tolist(),'marginal_costs':costs2.tolist(),
                               'product_profits':((prices-costs2)*shares).tolist(),
                               'consumer_surpluses':arr(cf_consumer_surpluses),
                               'profit_gradient_max_abs':grad,'profit_hessian_max_eigenvalue':eigen}
    return out


def solve(spec):
    _keys(spec, {'model','baseline','scenario','unit','sources'})
    model = spec['model']; methods = {'auction':auction, 'search':search, 'bargaining':bargain, 'platform':platform, 'matching':matching, 'equity':None, 'blp':blp, 'auction_fit':auction_fit}
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
        base, changed = blp(spec['baseline']), None
        key, indicator = 'objective', base['objective']
    else:
        if not isinstance(spec['scenario'], dict): raise ValueError('scenario must be a complete model specification')
        base, changed = methods[model](spec['baseline']), methods[model](spec['scenario'])
        key = ({'search':'expected_net_surplus', 'bargaining':'total_surplus', 'platform':'social_welfare', 'matching':'total_welfare', 'auction_fit':'support_upper_mle'}[model] if model != 'auction' else ('expected_revenue' if spec['baseline']['information'] == 'private' else 'bid_slope'))
        indicator = base[key]
    return {'model': model, 'engine': ('equity.fit' if model == 'equity' else 'pyblp' if model == 'blp' else 'numpy/scipy'),
            'adopted': {'unit':spec['unit'], 'sources':spec['sources']}, 'options': {'baseline':spec['baseline'], 'scenario':spec['scenario']},
            'statistics': {key:{'value':float(indicator),'unit':('dimensionless' if key in {'objective','gmm_objective','bid_slope'} else spec['unit'])}}, 'baseline':base, 'scenario':changed}


def _synthetic_bertrand(nested):
    """Generate prices from the stated single-product-firm Bertrand conditions."""
    from scipy.optimize import root
    rng = np.random.default_rng(20261101)
    products = []
    rho = .4 if nested else 0.
    alpha = -1.1
    for t in range(120):
        x = rng.normal(0, .7, 4); z = rng.uniform(-.7, .7, 4)
        xi = rng.normal(0, .025, 4); omega = rng.normal(0, .025, 4)
        cost = 1.3+.3*z+omega
        count = [1,2,3][t % 3]
        groups = np.array([0 if j < count else 1 for j in range(4)])
        def shares(prices):
            util = (1+.5*x+alpha*prices+xi)/(1-rho)
            e = np.exp(util)
            sums = np.array([e[groups == g].sum() for g in (0,1)])
            term = sums**(1-rho)
            within = e/sums[groups]
            return within*term[groups]/(1+term.sum()), within
        def conditions(prices):
            share, within = shares(prices)
            derivative = alpha/(1-rho)*share*(1-rho*within-(1-rho)*share)
            return prices-cost+share/derivative
        solution = root(conditions, cost+1.2, tol=1e-11)
        if np.max(np.abs(conditions(solution.x))) > 1e-9:
            raise ArithmeticError('synthetic Bertrand first-order equations failed')
        share, _ = shares(solution.x)
        for j in range(4):
            product = {'market_ids':str(t), 'product_ids':str(j), 'firm_ids':str(j),
                       'prices':float(solution.x[j]), 'shares':float(share[j]), 'x':float(x[j]), 'z':float(z[j]),
                       'demand_instruments0':float(z[j]), 'demand_instruments1':float(sum(groups == groups[j])),
                       'demand_instruments2':float(sum(z[groups == groups[j]])-z[j]),
                       'supply_instruments0':float(x[j]), 'supply_instruments1':float(sum(x[groups == groups[j]])-x[j])}
            if nested: product['nesting_ids'] = str(groups[j])
            products.append(product)
    return products


def cases():
    source = [{'kind':'synthetic','description':'Analytical distributions, preferences and parameters defined in market-models.md'}]
    def wrap(model,b,cf): return {'model':model,'baseline':b,'scenario':cf,'unit':'model units','sources':source}
    a = {'n':3,'format':'first','information':'private','reserve':0.,'bids':[.1,.3,.5]}
    common = {'n':3,'format':'first','information':'common','reserve':0.,'bids':[]}
    search0 = {'offers':3,'search_cost':.08,'outside_option':0.}
    bargaining0 = {'buyer_value':10.,'seller_cost':2.,'buyer_outside':1.,'seller_outside':1.,'buyer_weight':.4,'tax':0.}
    platform0 = {'intercepts':[4.,3.], 'cross_effects':[.3,.4], 'costs':[1.,1.]}
    match0 = {'proposers':['a','b','c'], 'receivers':['x','y','z'],
              'proposer_preferences':{'a':['x','y','z'],'b':['x','y','z'],'c':['y','z','x']},
              'receiver_preferences':{'x':['b','a','c'],'y':['a','c','b'],'z':['c','b','a']},
              'proposer_values':{'a':{'x':3,'y':2,'z':1},'b':{'x':3,'y':2,'z':1},'c':{'y':3,'z':2,'x':1}},
              'receiver_values':{'x':{'b':3,'a':2,'c':1},'y':{'a':3,'c':2,'b':1},'z':{'c':3,'b':2,'a':1}}}
    match1 = json.loads(json.dumps(match0)); match1['receiver_preferences']['x']=['a','b','c']; match1['receiver_values']['x']={'a':3,'b':2,'c':1}
    firms = [{'firm_ids':'A','unit_cost':20.,'capacity':100.},{'firm_ids':'B','unit_cost':20.,'capacity':100.}]
    market = {'market_ids':'synthetic','controls':{},'firms':firms}
    cournot = {'model':'cournot','market':'synthetic','as_of':'2026-11-01','currency':'units','price_unit':1.,'quantity_unit':'units',
               'sources':source, 'identification':{'parameters':[{'name':'inverse demand','role':'demand','moments':['calibration'],'variation':'supplied slope','exclusion':'calibrated model','source':'synthetic'}]},
               'inverse_demand':{'coefficients':{'intercept':100.,'quantity':-2.}},'markets':[market],
               'counterfactual':{'markets':[{**market,'firms':[{**firms[0],'capacity':5.},firms[1]]}]}}
    products = []
    for t in range(12):
        rows = []
        for j in range(3):
            x = math.sin(.7*t+1.2*j); z = math.cos(.8*t+1.7*j)
            price = 2.5+.3*x+.25*z+.1*math.sin(t+j)
            xi = .03*math.sin(t*1.3+j*.9)
            rows.append((x,z,price,1+.4*x-price+xi))
        den = 1+sum(math.exp(row[-1]) for row in rows)
        for j,(x,z,price,delta) in enumerate(rows):
            i = 3*t+j
            products.append({'market_ids':str(t),'product_ids':str(j),'firm_ids':str(j),
                             'prices':price,'shares':math.exp(delta)/den,'x':x,
                             'demand_instruments0':z,'demand_instruments1':math.sin(i*.47),
                             'demand_instruments2':math.cos(i*.31)})
    basic = {'products':products,'linear':'1 + prices + x','nonlinear':None,'supply':None,
             'integration':None,'solve':{'method':'1s'},'optimal_instruments':True,'add_exogenous':True,
             'counterfactual':{'keep_product_ids':['0','1'],'firm_ids':['merged']*24,
                               'costs':[1.]*24,'utility_shifts':[0.]*24}}
    endogenous = json.loads(json.dumps(basic)); endogenous['add_exogenous'] = False; endogenous['optimal_instruments'] = False; endogenous['counterfactual'] = None
    for product in endogenous['products']: product['demand_instruments3'] = 1.
    entry = json.loads(json.dumps(basic)); entry['optimal_instruments'] = False
    entrants = []
    for t in range(12):
        row = dict(products[3*t]); row.update(product_ids='entrant', firm_ids='entrant', prices=2.5, shares=.05, x=.2)
        entrants.append(row)
    entry['counterfactual'] = {'keep_product_ids':['0','1','2'], 'firm_ids':['incumbent']*36+['entrant']*12,
                               'costs':[1.]*48, 'utility_shifts':[0.]*48, 'entry_products':entrants,'entry_xi':[0.]*12}
    nested = json.loads(json.dumps(basic)); nested['optimal_instruments'] = False; nested['counterfactual'] = None
    for product in nested['products']: product['nesting_ids'] = 'nest' if product['product_ids'] != '2' else 'other'
    nested['solve'] = {'method':'1s','rho':.2,'rho_bounds':[[.2],[.2]]}
    random = json.loads(json.dumps(basic)); random['optimal_instruments'] = False; random['counterfactual'] = None
    random['nonlinear'] = '0 + prices'; random['integration'] = {'method':'product','size':5,'options':{}}
    random['solve'] = {'method':'1s','sigma':[[.2]], 'optimization':{'method':'l-bfgs-b','options':{'maxiter':100}}}
    supply = json.loads(json.dumps(basic)); supply['optimal_instruments'] = False; supply['counterfactual'] = None
    supply['supply'] = '1 + costx'
    for product in supply['products']:
        product['costx'] = product['demand_instruments0']; product['supply_instruments0'] = product['x']
    supply['solve'] = {'method':'1s','beta':[None,-1.,None], 'beta_bounds':[[None,-1.,None],[None,-1.,None]]}
    nested_free = json.loads(json.dumps(nested)); nested_free['products'] = _synthetic_bertrand(True)
    nested_free['solve'] = {'method':'1s','rho':.2,'rho_bounds':[[.01],[.9]],
                            'optimization':{'method':'l-bfgs-b','options':{'gtol':1e-8,'maxiter':500}}}
    supply_free = json.loads(json.dumps(supply)); supply_free['products'] = _synthetic_bertrand(False)
    supply_free['supply'] = '1 + z'
    supply_free['solve'] = {'method':'1s','beta':[None,-.9,None],
                            'optimization':{'method':'l-bfgs-b','options':{'gtol':1e-8,'maxiter':500}}}
    rng = np.random.default_rng(20261101)
    records = []
    for i in range(200):
        values = rng.uniform(0, 2.5, 3); bids = values*2/3; winner = int(np.argmax(bids))
        records.append({'auction_id':str(i), 'bids':[{'bidder_id':str(j),'amount':float(bids[j])} for j in range(3)],
                        'winner_id':str(winner), 'payment':float(bids[winner])})
    auction_records = {'n':3,'format':'first','records':records,'counterfactual_reserve':0.}
    return {'blp-nested-free':wrap('blp',nested_free,None), 'blp-supply-free':wrap('blp',supply_free,None),
            'auction-records':wrap('auction_fit',auction_records,{**auction_records,'counterfactual_reserve':1.25}),
            'blp-entry':wrap('blp',entry,None),'blp-logit':wrap('blp',basic,None),'blp-endogenous-characteristic':wrap('blp',endogenous,None),'blp-nested':wrap('blp',nested,None),
            'blp-random':wrap('blp',random,None),'blp-supply':wrap('blp',supply,None),
            'cournot':wrap('equity',cournot,None), 'auction-private':wrap('auction',a,{**a,'format':'second','reserve':.5,'bids':[]}),
            'auction-common':wrap('auction',common,{**common,'format':'second'}),
            'search':wrap('search',search0,{**search0,'search_cost':.02}),
            'bargaining':wrap('bargaining',bargaining0,{**bargaining0,'tax':2.}),
            'platform':wrap('platform',platform0,{**platform0,'cross_effects':[.1,.1]}),
            'matching':wrap('matching',match0,match1)}


def _write(path, data):
    payload = json.dumps(data, indent=2, allow_nan=False)+'\n'; path = Path(path)
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
    case = sub.add_parser('case'); case.add_argument('--output',type=Path,required=True)
    args = p.parse_args(argv)
    try:
        if args.operation == 'run':
            raw = args.spec.read_bytes(); result = solve(json.loads(raw)); result['provenance'] = {'spec_path':str(args.spec.resolve()), 'spec_sha256':hashlib.sha256(raw).hexdigest()}; _write(args.output,result)
        else:
            args.output.mkdir(parents=True, exist_ok=False)
            for name,spec in cases().items():
                path=args.output/(name+'.json'); _write(path,spec); result=solve(spec); result['provenance']={'spec_path':str(path.resolve()),'spec_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}; _write(args.output/(name+'-result.json'),result)
    except (ValueError, TypeError, KeyError, OSError, ArithmeticError) as exc: p.exit(2,f'error: {exc}\n')

if __name__ == '__main__': main()
