#!/usr/bin/env python3
"""Overlapping generations macro model: run SPEC --output FILE or case --output NEWDIR."""
import argparse
import csv
import io
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import scipy
from scipy.optimize import least_squares
from importlib.metadata import version


def olg_sequence_block(K, Z, effective_a, labor, alpha, save, income_share):
    Y = Z*effective_a*K(-1)**alpha*labor**(1-alpha)
    clearing = K-save*income_share*Y
    return Y, clearing


def hark_lifecycle(beta):
    # An independent two-period CRRA=2 example with a unit old-age endowment.
    from HARK.ConsumptionSaving.ConsIndShockModel import PerfForesightConsumerType
    gross_return = 1.04
    assets = 2.0
    consumer = PerfForesightConsumerType(cycles=1, T_cycle=1, CRRA=2., DiscFac=beta,
        Rfree=[gross_return], LivPrb=[1.], PermGroFac=[1.], BoroCnstArt=0.)
    consumer.solve()
    consumption = float(consumer.solution[0].cFunc(assets))
    analytic = (gross_return*assets+1)/(gross_return+np.sqrt(beta*gross_return))
    if abs(consumption-analytic) > 1e-8: raise ArithmeticError('HARK lifecycle Euler check failed')
    return {'engine':'HARK PerfForesightConsumerType.solve', 'CRRA':2., 'discount_factor':beta,
        'gross_return':gross_return,'young_resources':assets,'old_endowment':1.,
        'young_consumption':consumption,'saving':assets-consumption,
        'old_consumption':gross_return*(assets-consumption)+1.,
        'analytic_consumption':float(analytic),'analytic_abs_error':abs(consumption-analytic)}


def atomic_write(path, obj):
    payload = json.dumps(obj, indent=2, allow_nan=False) + '\n'
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix='.'+path.name+'.', delete=False) as stream:
            temp = Path(stream.name)
            stream.write(payload)
        os.replace(temp, path)
    finally:
        if temp is not None: temp.unlink(missing_ok=True)


def publish_case(output, spec, runner):
    output = output.resolve()
    if output.exists(): raise FileExistsError(f'output already exists: {output}')
    source = next((p/'harness/local_checks.py' for p in Path(__file__).resolve().parents if (p/'harness/local_checks.py').is_file()), None)
    if source is None: raise FileNotFoundError('harness/local_checks.py is required')
    module_spec = importlib.util.spec_from_file_location('macro_case_local_checks', source)
    gate = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(gate)
    with tempfile.TemporaryDirectory(prefix='.macro-case-', dir=output.parent) as temp:
        stage = Path(temp)
        atomic_write(stage/'spec.json', spec)
        result = runner(spec)
        result['provenance']['spec_sha256'] = hashlib.sha256((stage/'spec.json').read_bytes()).hexdigest()
        result['provenance']['producer_sha256'] = hashlib.sha256(Path(runner.__code__.co_filename).read_bytes()).hexdigest()
        atomic_write(stage/'result.json', result)
        gate.atomic_publish(stage, output)


def read_productivity(observations, base_dir):
    """Read the identified, equally spaced observed series from a hash-checked CSV."""
    path = Path(observations['path'])
    if not path.is_absolute(): path = Path(base_dir)/path
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != observations['sha256'].lower():
        raise ValueError('productivity CSV SHA-256 does not match the declared source')
    period_column = observations['period_column']
    value_column = observations['value_column']
    if not isinstance(period_column, str) or not isinstance(value_column, str) or period_column == value_column:
        raise ValueError('distinct period and value column IDs are required')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    if reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames) or not {period_column,value_column}.issubset(reader.fieldnames):
        raise ValueError('productivity CSV requires unique named period and value columns')
    periods, values = [], []
    for row in reader:
        if None in row: raise ValueError('productivity CSV contains rows with extra fields')
        periods.append(int(row[period_column]))
        values.append(float(row[value_column]))
    if not periods or any(b != a+1 for a,b in zip(periods, periods[1:])):
        raise ValueError('productivity periods must be consecutive ordered integers')
    values = np.asarray(values,dtype=float)
    if not np.isfinite(values).all(): raise ValueError('productivity values must be finite')
    return values, {'path':observations['path'], 'sha256':digest, 'period_column':period_column,
        'value_column':value_column, 'first_period':periods[0], 'last_period':periods[-1], 'rows':len(periods)}


def write_productivity_case(stage, values, source):
    path = stage/'observed-productivity.csv'
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['period','log_productivity'])
        writer.writerows((i,repr(float(x))) for i,x in enumerate(values))
    return {'type':'synthetic','source':source,'path':path.name,
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'period_column':'period','value_column':'log_productivity'}


def publish_observed_case(output, generator, runner):
    output = output.resolve()
    if output.exists(): raise FileExistsError(f'output already exists: {output}')
    source = next((p/'harness/local_checks.py' for p in Path(__file__).resolve().parents if (p/'harness/local_checks.py').is_file()), None)
    if source is None: raise FileNotFoundError('harness/local_checks.py is required')
    module_spec = importlib.util.spec_from_file_location('macro_observed_local_checks',source)
    gate = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(gate)
    with tempfile.TemporaryDirectory(prefix='.macro-observed-', dir=output.parent) as temp:
        stage = Path(temp)
        specification = generator(stage)
        atomic_write(stage/'spec.json', specification)
        result = runner(specification, stage)
        result['provenance']['spec_sha256'] = hashlib.sha256((stage/'spec.json').read_bytes()).hexdigest()
        result['provenance']['producer_sha256'] = hashlib.sha256(Path(runner.__code__.co_filename).read_bytes()).hexdigest()
        atomic_write(stage/'result.json', result)
        gate.atomic_publish(stage,output)


def solve(spec, base_dir=Path.cwd()):
    p = spec['parameters']
    alpha, beta, delta = (float(p[k]) for k in ('alpha','beta','delta'))
    shares = np.asarray(p['household_weights'], dtype=float)
    efficiency = np.asarray(p['household_efficiency'], dtype=float)
    firm_shares = np.asarray(p['firm_labor_shares'], dtype=float)
    firm_a = np.asarray(p['firm_productivity'], dtype=float)
    if not (0 < alpha < 1 and 0 < beta < 1 and 0 <= delta < 1): raise ValueError('invalid preference or technology')
    if (len(shares)==0 or shares.shape != efficiency.shape or len(firm_shares)==0 or firm_shares.shape != firm_a.shape or
        not all(np.isfinite(x).all() for x in (shares,efficiency,firm_shares,firm_a)) or
        min(shares.min(),efficiency.min(),firm_shares.min(),firm_a.min()) <= 0 or
        abs(shares.sum()-1)>1e-10 or abs(firm_shares.sum()-1)>1e-10):
        raise ValueError('positive shares and productivity are required, with shares summing to one')
    labor = float(shares @ efficiency)
    # Heterogeneous firms rent capital competitively conditional on exogenous labor shares.
    scale = float(firm_shares @ firm_a**(1/(1-alpha)))
    aggregate_a = scale**(1-alpha)
    alloc = firm_shares*firm_a**(1/(1-alpha))/scale
    obs, observed_source = read_productivity(spec['observations'], base_dir)
    if len(obs)<4 or not np.isfinite(obs).all() or np.linalg.norm(obs[:-1]) < 1e-10:
        raise ValueError('at least four varying finite log-productivity observations required')
    fit = least_squares(lambda x: obs[1:]-x[0]*obs[:-1], x0=[.5], bounds=([-.99],[.99]), xtol=1e-12, ftol=1e-12, gtol=1e-12)
    rho = float(fit.x[0])
    if not fit.success: raise ArithmeticError(fit.message)
    jac_norm = float(np.linalg.norm(fit.jac))
    def parameters(s):
        markup, collateral, tax = (float(s[k]) for k in ('markup','collateral_income_limit','government_share'))
        if not (markup>=1 and 0 < collateral <= 1 and 0 <= tax < 1): raise ValueError('invalid scenario')
        save = min(beta/(1+beta), collateral)
        coefficient = (1-alpha)/markup + 1-1/markup - tax
        if coefficient <= 0: raise ValueError('government share exhausts young income')
        k = (save*coefficient*aggregate_a*labor**(1-alpha))**(1/(1-alpha))
        return markup, collateral, tax, save, k
    def transition(s, z, initial, initial_saving):
        markup, collateral, tax, save, _ = parameters(s)
        k = initial
        result = []
        previous_saving = initial_saving
        for t, shock in enumerate(z):
            a = aggregate_a*np.exp(shock)
            y = a*k**alpha*labor**(1-alpha)
            wage = (1-alpha)*y/(markup*labor)
            rent = alpha*y/(markup*k)
            dividend = (1-1/markup)*y
            gov = tax*y
            income = wage*efficiency+(dividend-gov)
            if np.min(income)<=0: raise ValueError('scenario generates nonpositive household income')
            saving = save*income
            cy = income-saving
            co = (1-delta+rent)*previous_saving
            knew = float(shares@saving)
            resources = float(shares@cy + shares@co + gov + knew - ((1-delta)*k+y))
            marginal = beta/saving-1/cy
            next_z = z[t+1] if t+1 < len(z) else z[t]*rho
            next_y = aggregate_a*np.exp(next_z)*knew**alpha*labor**(1-alpha)
            next_return = 1-delta+alpha*next_y/(markup*knew)
            result.append({'period':t,'capital':k,'next_capital':knew,'output':y,'wage':wage,'rental_rate':rent,
                'government_absorption':gov,'profits':dividend,'firm_capital':(alloc*k).tolist(),
                'young_income':income.tolist(),'young_consumption':cy.tolist(),'old_consumption':co.tolist(),
                'saving':saving.tolist(),'distribution_weights':shares.tolist(),'investment':knew-(1-delta)*k,
                'resource_residual':resources,'capital_market_residual':float(knew-shares@saving),
                'saving_constraint_slack':(collateral*income-saving).tolist(),
                'saving_constraint_multiplier':marginal.tolist(),
                'cohort_welfare':(np.log(cy)+beta*np.log(next_return*saving)).tolist()})
            previous_saving = saving
            k = knew
        return result
    base = spec['baseline']; scenario = spec['scenario']
    _,_,_,_, k0 = parameters(base)
    horizon = int(spec['horizon'])
    if horizon < 2: raise ValueError('horizon must be at least two')
    shock = float(spec['technology_shock'])
    z = [shock*rho**t for t in range(horizon)]
    base_markup, _, base_tax, base_save, _ = parameters(base)
    base_y = aggregate_a*k0**alpha*labor**(1-alpha)
    initial_saving = base_save*((1-alpha)*base_y/(base_markup*labor)*efficiency + (1-1/base_markup-base_tax)*base_y)
    baseline = transition(base, [0.]*horizon, k0, initial_saving)
    scenario_path = transition(scenario, z, k0, initial_saving)
    # Sequence-space Jacobian at the baseline steady state, dY_t / dz_s.
    # K_{t+1}=constant*exp(z_t)*K_t**alpha implies d log Y_t / dz_s=alpha**(t-s).
    sequence_jacobian = np.zeros((horizon, horizon))
    for t in range(horizon):
        for j in range(t+1):
            sequence_jacobian[t, j] = baseline[t]['output']*alpha**(t-j)
    base_markup, _, base_tax, base_save, _ = parameters(base)
    income_share = (1-alpha)/base_markup + 1-1/base_markup-base_tax
    from sequence_jacobian import simple
    sequence_block = simple(olg_sequence_block)
    sequence_ss = sequence_block.steady_state({'K':k0, 'Z':1., 'effective_a':aggregate_a,
        'labor':labor, 'alpha':alpha, 'save':base_save, 'income_share':income_share})
    official_jacobian = np.asarray(sequence_block.solve_jacobian(sequence_ss, unknowns=['K'],
        targets=['clearing'], inputs=['Z'], outputs=['Y'], T=horizon)['Y']['Z'])
    official_error = float(np.max(np.abs(official_jacobian-sequence_jacobian)))
    if official_error > 1e-7: raise ArithmeticError(f'official sequence Jacobian residual {official_error}')
    step = 1e-5
    numerical_jacobian = np.empty_like(sequence_jacobian)
    for j in range(horizon):
        perturb = np.zeros(horizon)
        perturb[j] = step
        plus = transition(base, perturb, k0, initial_saving)
        minus = transition(base, -perturb, k0, initial_saving)
        numerical_jacobian[:,j] = [(plus[t]['output']-minus[t]['output'])/(2*step) for t in range(horizon)]
    sequence_error = float(np.max(np.abs(sequence_jacobian-numerical_jacobian)))
    if sequence_error > 1e-7: raise ArithmeticError(f'sequence derivative residual {sequence_error}')
    fields = ('capital','next_capital','output','wage','rental_rate','government_absorption')
    irf = [{name: scenario_path[t][name]-baseline[t][name] for name in fields} for t in range(horizon)]
    maxres = max(abs(x['resource_residual']) for x in baseline+scenario_path)
    if maxres > 1e-8: raise ArithmeticError(f'resource residual {maxres}')
    wbase = float(shares@np.asarray(baseline[0]['cohort_welfare']))
    wscenario = float(shares@np.asarray(scenario_path[0]['cohort_welfare']))
    lifecycle = hark_lifecycle(beta)
    stats = {'hark_young_consumption': {'value':lifecycle['young_consumption'],'unit':'normalized goods per young household'},
        'sequence_jacobian_analytic_error': {'value':official_error,'unit':'goods per unit log productivity'},
        'estimated_technology_persistence': {'value':rho,'unit':'AR(1) coefficient'},
        'steady_capital': {'value':k0,'unit':'goods per young cohort'},
        'impact_output_change': {'value':irf[0]['output'],'unit':'goods per period'},
        'impact_cohort_welfare_change': {'value':wscenario-wbase,'unit':'weighted lifetime log utility'},
        'max_resource_residual': {'value':maxres,'unit':'goods per period'},
        'observation_jacobian_norm': {'value':jac_norm,'unit':'log productivity'}}
    return {'model':'two-period overlapping-generations general equilibrium with firm and household heterogeneity',
        'adopted':spec,'scenario':'baseline versus scenario and technology innovation',
        'engine':'closed-form household and firm choices; scipy.optimize.least_squares AR(1)',
        'options':{'optimizer':'least_squares','xtol':1e-12,'ftol':1e-12,'gtol':1e-12},
        'observation':{'type':spec['observations']['type'], 'source':spec['observations']['source'], 'input':observed_source, 'estimand':'conditional AR(1) persistence',
            'equation':'z[t] = rho*z[t-1] + innovation[t]', 'identification':'nonzero lagged productivity variation; innovation orthogonal to lag',
            'optimizer_success':bool(fit.success),'optimizer_cost':float(fit.cost),'jacobian_rank':int(np.linalg.matrix_rank(fit.jac)),
            'innovation_residuals':fit.fun.tolist()},
        'sequence_space_jacobian': {'engine':'sequence_jacobian.simple.solve_jacobian', 'output_to_log_productivity':official_jacobian.tolist(), 'analytic_max_abs_error':official_error, 'difference_step':step, 'finite_difference_max_abs_error':sequence_error},
        'hark_lifecycle_comparison':lifecycle,
        'steady_state':{'baseline_capital':k0,'scenario_capital':parameters(scenario)[4], 'aggregate_productivity':aggregate_a,
            'firm_capital_shares':alloc.tolist()},
        'baseline':baseline,'simulation':scenario_path,'impulse_response':irf,'statistics':stats,
        'provenance':{'python':sys.version.split()[0],'numpy':np.__version__,'scipy':scipy.__version__, 'sequence_jacobian':version('sequence-jacobian'), 'HARK':version('econ-ark')}}


def example(stage):
    rng = np.random.default_rng(39020)
    obs = [.1]
    for _ in range(100): obs.append(.75*obs[-1]+rng.normal(scale=.03))
    return {'parameters':{'alpha':.36,'beta':.96,'delta':.08,'household_weights':[.5,.5],
        'household_efficiency':[.6,1.4],'firm_labor_shares':[.4,.6],'firm_productivity':[.8,1.2]},
        'observations':write_productivity_case(stage, obs, 'synthetic AR(1), seed 39020, rho .75, innovation sd .03'),
        'baseline':{'markup':1.,'collateral_income_limit':1.,'government_share':0.},
        'scenario':{'markup':1.2,'collateral_income_limit':.35,'government_share':.03},
        'horizon':20,'technology_shock':.05}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['run','case'])
    parser.add_argument('spec',nargs='?',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation == 'run':
            if args.spec is None: raise ValueError('run requires a specification')
            raw = args.spec.read_bytes()
            result = solve(json.loads(raw),args.spec.resolve().parent)
            result['provenance']['spec_sha256'] = hashlib.sha256(raw).hexdigest()
            result['provenance']['producer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            atomic_write(args.output,result)
        else:
            if args.spec is not None: raise ValueError('case takes no specification')
            publish_observed_case(args.output,example,solve)
    except (ValueError,KeyError,TypeError,OSError,ArithmeticError) as exc:
        parser.exit(2,f'error: {exc}\n')


if __name__ == '__main__': main()
