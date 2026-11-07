#!/usr/bin/env python3
"""Solve and simulate a stochastic RBC model: run SPEC --output FILE."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import warnings

import numpy as np
from numpy.polynomial.hermite import hermgauss
import scipy
from scipy.optimize import brentq
import statsmodels
from statsmodels.tsa.arima.model import ARIMA

from research_macro_extended import atomic_write, read_productivity


def solve(spec, base_dir=Path.cwd()):
    p = spec['parameters']
    alpha, beta, delta = (float(p[k]) for k in ('alpha', 'beta', 'delta'))
    if not (0 < alpha < 1 and 0 < beta < 1 and 0 < delta < 1):
        raise ValueError('alpha, beta and delta must lie strictly between zero and one')
    observed, observed_source = read_productivity(spec['observations'],base_dir)
    if observed.ndim != 1 or len(observed) < 20 or not np.isfinite(observed).all() or np.std(observed) <= 1e-10:
        raise ValueError('at least 20 finite varying log-productivity observations are required')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fitted = ARIMA(observed, order=(1, 0, 0), trend='n', enforce_stationarity=True).fit()
    if not fitted.mle_retvals.get('converged', False):
        raise ArithmeticError('ARIMA maximum likelihood did not converge')
    estimates = dict(zip(fitted.param_names, np.asarray(fitted.params, dtype=float)))
    rho, variance = estimates['ar.L1'], estimates['sigma2']
    if not (-1 < rho < 1 and variance > 0): raise ArithmeticError('invalid AR(1) estimate')
    sigma = float(np.sqrt(variance))
    covariance = np.asarray(fitted.cov_params(), dtype=float)
    if not np.isfinite(covariance).all(): raise ArithmeticError('non-finite parameter covariance')
    kbar = (alpha/(1/beta-1+delta))**(1/(1-alpha))
    ybar = kbar**alpha
    cbar = ybar-delta*kbar
    if cbar <= 0: raise ArithmeticError('nonpositive steady consumption')
    marginal_capital = alpha*ybar+(1-delta)*kbar
    eta = beta*alpha*kbar**(alpha-1)
    def consumption_capital(a): return (marginal_capital-kbar*a)/cbar
    def euler_root(a):
        A = consumption_capital(a)
        return A-(A-eta*(alpha-1))*a
    a = float(brentq(euler_root, 0., 1., xtol=1e-14))
    A = consumption_capital(a)
    b = ((ybar/cbar)*(1-rho)+eta*rho)/((A-eta*(alpha-1))+(kbar/cbar)*(1-rho))
    B = (ybar-kbar*b)/cbar
    capital_residual = A-(A-eta*(alpha-1))*a
    technology_residual = B*(1-rho)-(A-eta*(alpha-1))*b+eta*rho
    resource_k = cbar*A+kbar*a-marginal_capital
    resource_z = cbar*B+kbar*b-ybar
    if max(abs(capital_residual),abs(technology_residual),abs(resource_k),abs(resource_z)) > 1e-9:
        raise ArithmeticError('linear equilibrium coefficients fail original equations')
    if not (0 < a < 1): raise ArithmeticError('capital policy is not stable')
    horizon, paths, seed = (int(spec[k]) for k in ('horizon','simulation_paths','seed'))
    shock = float(spec['technology_shock'])
    if not (2 <= horizon <= 500 and 2 <= paths <= 10000 and np.isfinite(shock)):
        raise ValueError('invalid horizon, number of paths or shock')
    # Exact levels and budget evaluated at the first-order log-capital policy.
    def allocation(x, z):
        k = kbar*np.exp(x)
        next_x = a*x+b*z
        knext = kbar*np.exp(next_x)
        y = np.exp(z)*k**alpha
        c = y+(1-delta)*k-knext
        if not np.isfinite(c).all() or np.any(c <= 0): raise ValueError('policy yields nonpositive consumption')
        return next_x, k, knext, y, c
    value_constant = np.log(cbar)/(1-beta)
    value_k = A/(1-beta*a)
    value_z = (B+beta*value_k*b)/(1-beta*rho)
    def path(z):
        x = 0.
        rows = []
        welfare = 0.
        for t in range(horizon):
            next_x, k, knext, y, c = allocation(x,z[t])
            welfare += beta**t*np.log(c)
            rows.append({'period':t,'log_capital_deviation':float(x), 'log_productivity':float(z[t]),
                'capital':float(k),'next_capital':float(knext),'output':float(y),'consumption':float(c),
                'investment':float(knext-(1-delta)*k),
                'resource_residual':float(c+knext-y-(1-delta)*k)})
            x = next_x
        continuation = value_constant+value_k*x+value_z*z[horizon]
        welfare += beta**horizon*continuation
        return rows, float(welfare)
    z_irf = shock*rho**np.arange(horizon+1)
    irf_path, irf_welfare = path(z_irf)
    base_path, base_welfare = path(np.zeros(horizon+1))
    irf = [{key:row[key]-base[key] for key in ('capital','next_capital','output','consumption','investment')}
           for row,base in zip(irf_path,base_path)]
    rng = np.random.default_rng(seed)
    innovations = rng.normal(0,sigma,size=(paths,horizon))
    simulations = []
    z_samples = np.zeros((paths,horizon+1))
    welfare_samples = []
    for i in range(paths):
        for t in range(horizon): z_samples[i,t+1] = rho*z_samples[i,t]+innovations[i,t]
        rows, welfare = path(z_samples[i])
        simulations.append({'path':i,'innovations':innovations[i].tolist(),'periods':rows,'terminal_log_productivity':float(z_samples[i,-1]),'welfare':welfare})
        welfare_samples.append(welfare)
    forecast = [{'period':t,'sample_mean_log_productivity':float(np.mean(z_samples[:,t])),
        'sample_variance_log_productivity':float(np.var(z_samples[:,t],ddof=1)),
        'model_mean_log_productivity':0.,
        'model_variance_log_productivity':float(variance*sum(rho**(2*j) for j in range(t)))} for t in range(horizon+1)]
    for t in range(horizon):
        for key in ('capital','output','consumption','investment'):
            draws = np.asarray([trial['periods'][t][key] for trial in simulations])
            forecast[t]['sample_mean_'+key] = float(draws.mean())
            forecast[t]['sample_variance_'+key] = float(draws.var(ddof=1))
    nodes, weights = hermgauss(25)
    weights = weights/np.sqrt(np.pi)
    def euler_error(scale):
        x, z, sig = .03*scale, .04*scale, sigma*scale
        next_x, _, knext, _, c = allocation(x,z)
        next_z = rho*z+np.sqrt(2)*sig*nodes
        _, _, _, _, next_c = allocation(np.full_like(next_z,next_x),next_z)
        next_return = alpha*np.exp(next_z)*knext**(alpha-1)+1-delta
        return float(1/c-beta*np.dot(weights,next_return/next_c))
    scales = [1.,.5,.25,.125]
    residuals = [{'scale':scale,'conditional_euler_residual':euler_error(scale)} for scale in scales]
    max_resource = max(abs(row['resource_residual']) for trial in simulations for row in trial['periods'])
    stats = {'rho':{'value':float(rho),'unit':'AR(1) coefficient'},
        'innovation_std':{'value':sigma,'unit':'log productivity per period'},
        'steady_capital':{'value':float(kbar),'unit':'goods'},
        'capital_stable_root':{'value':a,'unit':'log capital elasticity'},
        'impact_output_change':{'value':irf[0]['output'],'unit':'goods per period'},
        'conditional_shock_welfare_change':{'value':irf_welfare-base_welfare,'unit':'discounted log consumption'},
        'mean_simulated_welfare':{'value':float(np.mean(welfare_samples)),'unit':'discounted log consumption'},
        'max_resource_residual':{'value':max_resource,'unit':'goods per period'}}
    return {'model':'stochastic log-utility RBC with first-order rational-expectations solution',
        'adopted':spec, 'scenario':'estimated AR(1), conditional technology shock, and seeded stochastic forecasts',
        'engine':'scipy.optimize.brentq; statsmodels.tsa.arima.model.ARIMA.fit; numpy Gauss-Hermite quadrature',
        'options':{'arima_order':[1,0,0], 'trend':'n','enforce_stationarity':True,'quadrature_nodes':25,'seed':seed},
        'observation':{'type':spec['observations']['type'],'source':spec['observations']['source'], 'input':observed_source,
            'equation':'z[t] = rho*z[t-1] + epsilon[t], epsilon ~ iid Normal(0,sigma^2)',
            'estimand':'conditional AR(1) persistence and innovation variance',
            'identification':'stationary AR(1), zero mean, Gaussian independent innovations and nonzero lagged variation',
            'parameter_names':fitted.param_names,'parameters':fitted.params.tolist(),
            'standard_errors':fitted.bse.tolist(),'covariance':covariance.tolist(),
            'log_likelihood':float(fitted.llf),'nobs':int(fitted.nobs),'converged':True,
            'warnings':[str(x.message) for x in caught]},
        'steady_state':{'capital':float(kbar),'consumption':float(cbar),'output':float(ybar),
            'euler_residual':float(1/cbar-beta*(alpha*kbar**(alpha-1)+1-delta)/cbar)},
        'policy':{'capital_state_coefficient':a,'capital_technology_coefficient':float(b),
            'consumption_state_coefficient':float(A),'consumption_technology_coefficient':float(B),
            'linear_euler_state_residual':float(capital_residual),'linear_euler_technology_residual':float(technology_residual),
            'linear_resource_state_residual':float(resource_k),'linear_resource_technology_residual':float(resource_z)},
        'nonlinear_euler_checks':{'method':'25-node Gauss-Hermite conditional expectation',
            'state_base':[.03,.04],'jointly_scaled_innovation_std':sigma,'residuals':residuals},
        'conditional_irf':{'shock':shock,'baseline':base_path,'scenario':irf_path,'differences':irf,
            'welfare_difference':irf_welfare-base_welfare},
        'forecast_moments':forecast, 'simulation':simulations,
        'welfare':{'method':'discounted exact log consumption under local policy plus first-order terminal value',
            'terminal_constant':float(value_constant),'terminal_capital_coefficient':float(value_k),
            'terminal_technology_coefficient':float(value_z),'baseline':base_welfare,
            'conditional_shock':irf_welfare,'mean_simulated':float(np.mean(welfare_samples))},
        'statistics':stats,'provenance':{'python':sys.version.split()[0],'numpy':np.__version__,
            'scipy':scipy.__version__,'statsmodels':statsmodels.__version__}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['run'])
    parser.add_argument('spec',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        raw = args.spec.read_bytes()
        result = solve(json.loads(raw),args.spec.resolve().parent)
        result['provenance']['spec_sha256'] = hashlib.sha256(raw).hexdigest()
        result['provenance']['producer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        atomic_write(args.output,result)
    except (ValueError,KeyError,TypeError,OSError,ArithmeticError) as exc:
        parser.exit(2,f'error: {exc}\n')


if __name__ == '__main__': main()
