#!/usr/bin/env python3
"""Template: a complexity ladder of nested economic models for one case, run from the simplest rung upward.
Copy this file to work/<topic>_model.py and replace the four marked blocks.

Each rung adds one feature to the rung below and reduces to it when that feature is switched off. The run
  (a) solves every rung over the parameter ranges, simplest first;
  (b) checks nesting: with the new feature off, the rung reproduces the rung below;
  (c) reports how far the decision changes from rung to rung and stops climbing once two consecutive rungs leave
      the decision unchanged or the time budget is spent.

Worked case: how strongly should a bonus depend on a measured KPI?
  Rung 0, single task (LEN): output e + noise, pay a + b*KPI, CARA risk aversion r, effort cost c*e^2/2.
  Rung 1, multitask: the firm also values a second task the KPI captures only partly (f2, g2); off when f2 = g2 = 0.
  Rung 2, relational cap: the bonus cannot exceed what the firm credibly pays, b <= cap; off when cap = inf.
  Decision: KPI bonus (b > 0) or flat pay (b = 0) when measuring the KPI costs K per worker.
"""
import itertools
import json
import sys
import time

import numpy as np

# 1. PARAMETERS: every parameter the decision depends on, with its range from the case, the knowledge library or
#    published estimates. Keep the grid small enough for each rung to finish within about a minute.
RANGES = {
    'r': [0.5, 1.0, 2.0],            # risk aversion (CARA coefficient)
    'c': [1.0],                      # effort cost scale
    'sigma2': [0.1, 0.5, 1.0, 2.0],  # KPI noise variance
    'f1': [1.0], 'g1': [1.0],        # value of and KPI loading on the measured task
    'f2': [1.0], 'g2': [0.0, 0.5],   # value of and KPI loading on the second task (rung 1)
    'cap': [0.3, 0.6],               # largest credible bonus rate (rung 2)
    'K': [0.05, 0.2],                # cost of measuring the KPI per worker
}
OFF = {'multitask': {'f2': 0.0, 'g2': 0.0}, 'relational_cap': {'cap': float('inf')}}  # feature switched off
BUDGET_SECONDS = 60


# 2. LADDER: one rung per model, simplest first. Each rung gives the surplus at bonus rate b after the worker's best
#    response, and its optimal b. A rung must reduce to the rung below under OFF[its feature].
def surplus(p, b):
    f, g = np.array([p['f1'], p.get('f2', 0.0)]), np.array([p['g1'], p.get('g2', 0.0)])
    e = b * g / p['c']                                      # worker's best response on each task
    return float(f @ e - p['c'] * e @ e / 2 - p['r'] * b ** 2 * p['sigma2'] / 2)


def rung_single_task(p):
    q = {**p, **OFF['multitask']}
    return 1 / (1 + q['r'] * q['c'] * q['sigma2']), q


def rung_multitask(p):
    f, g = np.array([p['f1'], p['f2']]), np.array([p['g1'], p['g2']])
    return float(f @ g) / (float(g @ g) + p['r'] * p['c'] * p['sigma2']), p


def rung_relational_cap(p):
    b, q = rung_multitask(p)
    return min(b, p['cap']), q


LADDER = [('single_task', rung_single_task, None),
          ('multitask', rung_multitask, 'multitask'),
          ('relational_cap', rung_relational_cap, 'relational_cap')]


# 3. CHECKS: the optimum matches a grid search on the rung's own surplus (within the cap), and the rung with its
#    feature off reproduces the rung below.
def optimum_verified(p, b_star, q, upper=2.0):
    grid = np.linspace(0, upper, 4001)
    best = grid[int(np.argmax([surplus(q, b) for b in grid]))]
    return bool(abs(best - b_star) < 1e-3)


def nesting_verified(level, p):
    if level == 0:
        return True
    name, rung, feature = LADDER[level]
    off = {**p, **OFF[feature]}
    return bool(abs(rung(off)[0] - LADDER[level - 1][1](off)[0]) < 1e-9)


# 4. DECISION: the action at each parameter point and the gain that decides it.
def decide(p, b_star, q):
    gain = surplus(q, b_star) - surplus(q, 0.0)
    return {'b': b_star, 'gain': gain, 'action': 'KPI bonus' if gain > p['K'] else 'flat pay'}


def main(out=None):
    keys = list(RANGES)
    points = [dict(zip(keys, v)) for v in itertools.product(*(RANGES[k] for k in keys))]
    report, previous, unchanged, start = [], None, 0, time.time()
    for level, (name, rung, feature) in enumerate(LADDER):
        t0, rows = time.time(), []
        for p in points:
            b_star, q = rung(p)
            upper = min(2.0, p['cap']) if feature == 'relational_cap' else 2.0
            rows.append({**decide(p, b_star, q), 'optimum_ok': optimum_verified(p, b_star, q, upper),
                         'nesting_ok': nesting_verified(level, p)})
        actions = [r['action'] for r in rows]
        changed = None if previous is None else sum(a != b for a, b in zip(actions, previous)) / len(points)
        report.append({'rung': name, 'adds': feature, 'b_range': [min(r['b'] for r in rows), max(r['b'] for r in rows)],
                       'share_bonus': sum(a == 'KPI bonus' for a in actions) / len(points),
                       'decisions_changed_vs_previous': changed,
                       'checks_ok': all(r['optimum_ok'] and r['nesting_ok'] for r in rows),
                       'seconds': round(time.time() - t0, 3)})
        unchanged = unchanged + 1 if changed == 0 else 0
        previous = actions
        if unchanged >= 2 or time.time() - start > BUDGET_SECONDS:
            break
    result = {'ladder': report, 'stopped_at': report[-1]['rung'],
              'switching_condition': 'pay the KPI bonus iff surplus(b*) - surplus(0) > K'}
    if out:
        open(out, 'w').write(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
