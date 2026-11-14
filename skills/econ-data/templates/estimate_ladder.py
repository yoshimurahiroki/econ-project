#!/usr/bin/env python3
"""Template: a specification ladder for one estimand, run from the simplest comparison upward.
Copy to work/<topic>_estimate.py, replace the three marked blocks and run:
    python3 work/<topic>_estimate.py [DATA.csv] [OUT.json]
Without DATA.csv it simulates a staggered-adoption panel whose effect grows with exposure, so the ladder shows the
two-way fixed effects estimate drifting away from the heterogeneity-robust estimates.

Each rung changes one thing (comparison, fixed effects, controls, estimator). The report gives each rung's
estimate, standard error, 95% interval and cluster count, flags the inference rules that apply, and states whether
the estimate moved outside the previous rung's interval.
"""
import json
import sys
import time

import numpy as np
import pandas as pd
import pyfixest as pf

# 1. DATA AND ROLES: unit id, time, outcome, first treated period (0 = never treated), cluster, controls.
ROLES = {'unit': 'unit', 'time': 'year', 'outcome': 'y', 'cohort': 'first_treat', 'cluster': 'unit',
         'controls': ['x']}


def simulate(seed=0, units=300, years=range(2000, 2012)):
    rng = np.random.default_rng(seed)
    cohorts = rng.choice([0, 2004, 2006, 2008], size=units, p=[.4, .2, .2, .2])
    rows = []
    for i, g in enumerate(cohorts):
        alpha = rng.normal()
        for t in years:
            exposure = t - g + 1 if g and t >= g else 0
            effect = 0.5 * exposure                      # effect grows with exposure: TWFE is biased here
            x = rng.normal()
            rows.append({'unit': i, 'year': t, 'first_treat': int(g), 'x': x,
                         'y': alpha + 0.1 * (t - 2000) + 0.3 * x + effect + rng.normal()})
    data = pd.DataFrame(rows)
    data['treat'] = ((data.first_treat > 0) & (data.year >= data.first_treat)).astype(int)
    treated = data[data.treat == 1]
    return data, float((0.5 * (treated.year - treated.first_treat + 1)).mean())


# 2. LADDER: one rung per change, simplest first. Each returns (estimate, standard error).
def coef(fit, name='treat'):
    return float(fit.coef()[name]), float(fit.se()[name])


def rung_raw_difference(d, r):
    fit = pf.feols(f"{r['outcome']} ~ treat", data=d, vcov={'CRV1': r['cluster']})
    return coef(fit)


def rung_twfe(d, r):
    fit = pf.feols(f"{r['outcome']} ~ treat | {r['unit']} + {r['time']}", data=d, vcov={'CRV1': r['cluster']})
    return coef(fit)


def rung_twfe_controls(d, r):
    controls = ' + '.join(r['controls'])
    fit = pf.feols(f"{r['outcome']} ~ treat + {controls} | {r['unit']} + {r['time']}", data=d,
                   vcov={'CRV1': r['cluster']})
    return coef(fit)


def rung_imputation(d, r):
    fit = pf.did2s(d, yname=r['outcome'], first_stage=f"~ 0 | {r['unit']} + {r['time']}", second_stage='~ treat',
                   treatment='treat', cluster=r['cluster'])
    return coef(fit)


def pretrends(d, r):
    """Imputation event study: leads (periods before adoption) should be zero under parallel trends."""
    e = d.copy()
    e['rel'] = np.where(e[r['cohort']] > 0, e[r['time']] - e[r['cohort']], -1).astype(int)  # never treated: reference
    fit = pf.did2s(e, yname=r['outcome'], first_stage=f"~ 0 | {r['unit']} + {r['time']}",
                   second_stage='~ i(rel, ref=-1)', treatment='treat', cluster=r['cluster'])
    table = fit.tidy()
    lead_rows = [i for i in table.index if str(i).startswith('rel::') and int(str(i).split('::')[1]) < -1]
    leads = table.loc[lead_rows]
    return {'leads': len(leads), 'significant_at_5pct': int((leads['Pr(>|t|)'] < 0.05).sum()),
            'largest_abs_lead': round(float(leads['Estimate'].abs().max()), 4) if len(leads) else None}


LADDER = [('raw difference', rung_raw_difference),
          ('two-way fixed effects', rung_twfe),
          ('+ pre-determined controls', rung_twfe_controls),
          ('imputation (did2s)', rung_imputation)]


# 3. INFERENCE RULES that apply to this design and sample.
def flags(d, r):
    clusters = d[r['cluster']].nunique()
    treated_clusters = d.loc[d.treat == 1, r['cluster']].nunique()
    out = []
    if clusters < 40 or treated_clusters < 10:
        out.append(f'{clusters} clusters ({treated_clusters} treated): use the wild cluster bootstrap')
    if d[r['cohort']].replace(0, np.nan).nunique() > 1:
        out.append('staggered adoption: report the heterogeneity-robust rungs as the estimate; TWFE is rung 1 only')
    return clusters, out


def main(path=None, out=None):
    if path:
        data, truth = pd.read_csv(path), None
        data['treat'] = ((data[ROLES['cohort']] > 0) & (data[ROLES['time']] >= data[ROLES['cohort']])).astype(int)
    else:
        data, truth = simulate()
    clusters, notes = flags(data, ROLES)
    report, previous = [], None
    for name, rung in LADDER:
        t0 = time.time()
        estimate, se = rung(data, ROLES)
        low, high = estimate - 1.96 * se, estimate + 1.96 * se
        moved = None if previous is None else not (previous[0] <= estimate <= previous[1])
        report.append({'rung': name, 'estimate': round(estimate, 4), 'se': round(se, 4),
                       'ci95': [round(low, 4), round(high, 4)], 'moved_outside_previous_ci': moved,
                       'seconds': round(time.time() - t0, 2)})
        previous = (low, high)
    try:
        diagnostics = {'pretrends': pretrends(data, ROLES)}
    except Exception as exc:                     # report, then repair the roles or the cohort coding
        diagnostics = {'pretrends': 'failed: ' + str(exc)[:200]}
    result = {'n': len(data), 'clusters': clusters, 'flags': notes, 'ladder': report, 'diagnostics': diagnostics,
              'true_att_simulated': truth}
    if out:
        open(out, 'w').write(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None, sys.argv[2] if len(sys.argv) > 2 else None)
