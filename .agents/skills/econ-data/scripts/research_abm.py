#!/usr/bin/env python3
"""Bounded-learning goods market: run SPEC --output FILE."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import scipy
from scipy.optimize import brentq


def simulate(model, seed):
    n, m, periods = (int(model[k]) for k in ('households', 'firms', 'periods'))
    if min(n, m, periods) < 1:
        raise ValueError('households, firms and periods must be positive')
    supply, endowment, value, price, speed, tax, bargaining = (float(model[k]) for k in
        ('firm_supply', 'household_cash', 'reservation_value', 'initial_price', 'learning_rate', 'sales_tax', 'bargaining_weight'))
    if not (supply > 0 and endowment > 0 and value > 0 and price > 0 and 0 <= speed <= 1 and 0 <= tax < 1 and 0 <= bargaining <= 1):
        raise ValueError('invalid market primitives')
    rng = np.random.default_rng(seed)
    cash = np.full(n, endowment)
    firm_cash = np.zeros(m)
    inventory = np.zeros(m)
    prices = np.full(m, price)
    initial_cash = float(cash.sum())
    total_production = total_consumption = 0.
    rows = []
    for t in range(periods):
        inventory += supply
        total_production += m * supply
        sales = np.zeros(m)
        revenues = np.zeros(m)
        bought = np.zeros(n)
        tax_revenue = 0.
        # Every household bargains once with each firm in a seeded order.
        for h in rng.permutation(n):
            for f in rng.permutation(m):
                bid = value / (1 + bought[h])
                ask = prices[f] * (1 + tax)
                if bid < ask or inventory[f] <= 0:
                    continue
                gross = (1-bargaining)*ask + bargaining*bid
                q = min(1., inventory[f], cash[h]/gross)
                if q <= 0:
                    continue
                cash[h] -= q*gross
                net = q*gross/(1+tax)
                firm_cash[f] += net
                revenues[f] += net
                tax_revenue += q*gross-net
                inventory[f] -= q
                sales[f] += q
                bought[h] += q
        # Firm owners are the same households; tax and profits are redistributed equally.
        distribution = float(firm_cash.sum()) + tax_revenue
        cash += distribution/n
        firm_cash[:] = 0
        total_consumption += float(bought.sum())
        cash_error = float(cash.sum()+firm_cash.sum()-initial_cash)
        goods_error = float(total_production-total_consumption-inventory.sum())
        rows.append({'period': t, 'consumption': float(bought.sum()), 'sales': sales.tolist(),
                     'inventory': inventory.tolist(), 'price': prices.tolist(), 'household_cash': cash.tolist(),
                     'household_consumption': bought.tolist(), 'revenues': revenues.tolist(),
                     'tax_revenue': tax_revenue, 'utility': float(np.log1p(bought).sum()),
                     'cash_residual': cash_error, 'goods_residual': goods_error})
        # A full stockout increases the ask; unsold inventory reduces it, with bounded changes.
        stockout = (inventory <= 1e-12).astype(float)
        prices *= np.exp(speed*(stockout-.5))
        prices = np.clip(prices, .05, value*2)
    return {'periods': rows, 'utility': sum(row['utility'] for row in rows),
            'total_consumption': total_consumption, 'final_prices': prices.tolist(),
            'max_cash_residual': max(abs(row['cash_residual']) for row in rows),
            'max_goods_residual': max(abs(row['goods_residual']) for row in rows)}


def run(spec):
    model = spec['model']
    seed = int(spec['seed'])
    candidates = spec['candidates']
    if not candidates or len({x['id'] for x in candidates}) != len(candidates):
        raise ValueError('candidates must have distinct IDs')
    results = []
    for candidate in candidates:
        changes = candidate.get('changes', {})
        if set(changes) - {'sales_tax', 'learning_rate'}:
            raise ValueError('only sales_tax and learning_rate may vary across the fixed protocol')
        results.append({'id': candidate['id'], 'changes': changes, 'simulation': simulate({**model, **changes}, seed)})
    winner = max(results, key=lambda x: (x['simulation']['utility'], x['id']))
    rate = float(winner['changes'].get('learning_rate', model['learning_rate']))
    next_rate = max(0., min(1., rate + float(spec['next_rate_step'])))
    # Static competitive reference: p clears n max(v/p - 1, 0) against m*s.
    n, m = int(model['households']), int(model['firms'])
    v, supply = float(model['reservation_value']), float(model['firm_supply'])
    pstar = brentq(lambda p: n*max(v/p-1, 0)-m*supply, 1e-9, v)
    stats = {f"{r['id']}_utility": {'value': r['simulation']['utility'], 'unit': 'sum of household log(1+consumption) over periods'} for r in results}
    stats.update({f"{r['id']}_consumption": {'value': r['simulation']['total_consumption'], 'unit': 'goods over periods'} for r in results})
    stats['competitive_reference_price'] = {'value': pstar, 'unit': 'currency per good'}
    return {'model': 'finite household-firm bargaining market', 'adopted': spec, 'scenario': 'fixed paired-seed candidate comparison',
            'engine': 'numpy and scipy.optimize.brentq', 'options': {'seed': seed},
            'observation': 'synthetic simulated transactions; no observed-data estimation',
            'simulation': results, 'selected_candidate': winner['id'],
            'next_candidate': {'id': 'next_rate', 'changes': {**winner['changes'], 'learning_rate': next_rate}},
            'equilibrium_reference': {'price': pstar, 'supply': m*supply,
                'demand_residual': n*max(v/pstar-1, 0)-m*supply,
                'definition': 'static divisible-goods price taking, no cash constraint, marginal utility v/(1+q)'},
            'statistics': stats, 'provenance': {'python': sys.version.split()[0], 'numpy': np.__version__, 'scipy': scipy.__version__, 'seed': seed}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['run'])
    parser.add_argument('spec', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        raw = args.spec.read_bytes()
        result = run(json.loads(raw))
        result['provenance']['spec_sha256'] = hashlib.sha256(raw).hexdigest()
        result['provenance']['producer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        from research_macro_extended import atomic_write
        atomic_write(args.output, result)
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError) as exc:
        parser.exit(2, f'error: {exc}\n')


if __name__ == '__main__': main()
