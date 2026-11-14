#!/usr/bin/env python3
"""Template: build candidate economic models for a case, solve them over parameter ranges and find where the
decision switches. Copy this file to work/<topic>_model.py and replace the four marked blocks.

Worked case: how strongly should a bonus depend on a measured KPI?
  Candidate A (single task, LEN): output y = e + noise, pay w = a + b*y, CARA risk aversion r, effort cost c*e^2/2.
  Candidate B (multitask, distorted measure): two tasks e1, e2; the firm values f1*e1 + f2*e2, the KPI measures
    g1*e1 + g2*e2 + noise; pay w = a + b*KPI; cost c*(e1^2 + e2^2)/2.
  Decision: pay a KPI bonus (b > 0) or flat pay (b = 0) when measuring the KPI costs K per worker.
"""
import itertools
import json
import sys
import time

import numpy as np

# 1. PARAMETERS: every parameter the decision depends on, with the range taken from the case, the knowledge
#    library or published estimates. Keep the grid small enough to finish in under a minute.
RANGES = {
    'r': [0.5, 1.0, 2.0],          # risk aversion (CARA coefficient)
    'c': [1.0],                    # effort cost scale
    'sigma2': [0.1, 0.5, 1.0, 2.0],  # KPI noise variance
    'f1': [1.0], 'f2': [1.0],      # value of the two tasks to the firm
    'g1': [1.0], 'g2': [0.0, 0.5, 1.0],  # how the KPI loads on each task (g2 = 0: KPI ignores task 2)
    'K': [0.05, 0.2],              # cost of measuring the KPI per worker
}


# 2. CANDIDATE MODELS: for each model, the total surplus at contract b (value minus effort cost minus risk
#    premium, after the agent's best response) and the closed-form or numerical optimum.
def surplus_single_task(p, b):
    """LEN: the agent chooses e = b/c."""
    e = b / p['c']
    return e - p['c'] * e ** 2 / 2 - p['r'] * b ** 2 * p['sigma2'] / 2


def optimum_single_task(p):
    return 1 / (1 + p['r'] * p['c'] * p['sigma2'])


def surplus_multitask(p, b):
    """Distorted measure: the agent chooses e_i = b g_i / c."""
    f, g = np.array([p['f1'], p['f2']]), np.array([p['g1'], p['g2']])
    e = b * g / p['c']
    return float(f @ e - p['c'] * e @ e / 2 - p['r'] * b ** 2 * p['sigma2'] / 2)


def optimum_multitask(p):
    f, g = np.array([p['f1'], p['f2']]), np.array([p['g1'], p['g2']])
    return float(f @ g) / (float(g @ g) + p['r'] * p['c'] * p['sigma2'])


MODELS = {'single_task': (surplus_single_task, optimum_single_task),
          'multitask': (surplus_multitask, optimum_multitask)}


# 3. CHECK: the closed-form optimum must match a grid search over the model's own surplus.
def verified(surplus, p, b_star):
    grid = np.linspace(0, 2, 4001)
    best = grid[int(np.argmax([surplus(p, b) for b in grid]))]
    return bool(abs(best - b_star) < 1e-3)


# 4. DECISION: the action the model recommends and the quantity that decides it.
def decide(p, surplus, b_star):
    gain = surplus(p, b_star) - surplus(p, 0.0)
    return {'b': b_star, 'gain': gain, 'action': 'KPI bonus' if gain > p['K'] else 'flat pay'}


def main(out=None):
    start, rows = time.time(), []
    keys = list(RANGES)
    for values in itertools.product(*(RANGES[k] for k in keys)):
        p = dict(zip(keys, values))
        for name, (surplus, optimum) in MODELS.items():
            b_star = optimum(p)
            rows.append({**p, 'model': name, **decide(p, surplus, b_star), 'verified': verified(surplus, p, b_star)})
    elapsed = time.time() - start
    # Switching condition: the measurement cost at which the action flips equals the surplus gain.
    summary = {}
    for name in MODELS:
        part = [r for r in rows if r['model'] == name]
        summary[name] = {'b_range': [min(r['b'] for r in part), max(r['b'] for r in part)],
                         'share_bonus': sum(r['action'] == 'KPI bonus' for r in part) / len(part),
                         'all_verified': all(r['verified'] for r in part)}
    result = {'rows': rows, 'summary': summary, 'seconds': round(elapsed, 3),
              'switching_condition': 'pay the KPI bonus iff (f.g)^2 / (2 c (|g|^2 + r c sigma2)) > K'}
    text = json.dumps(result, indent=1)
    (open(out, 'w').write(text) if out else None)
    print(json.dumps({'summary': summary, 'seconds': result['seconds'],
                      'switching_condition': result['switching_condition']}, indent=1))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
