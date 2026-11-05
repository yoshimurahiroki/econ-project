#!/usr/bin/env python3
"""Execute explicitly specified empirical models with specialist estimators.

See econ-design/references/causal-models.md for the supported model contracts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import scipy
import statsmodels
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'harness'))
import state


R_METHODS = {
    'ols_r': ('stats', 'lm'),
    'fixest_ols': ('fixest', 'feols'),
    'fixest_ppml': ('fixest', 'fepois'),
    'drdid_panel': ('DRDID', 'drdid_panel'),
    'drdid_rc': ('DRDID', 'drdid_rc'),
    'did_multiplegt_dyn': ('DIDmultiplegtDYN', 'did_multiplegt_dyn'),
    'honest_did': ('HonestDiD', 'createSensitivityResults_relativeMagnitudes'),
    'wild_cluster_bootstrap': ('fwildclusterboot', 'boottest'),
    'club_sandwich': ('clubSandwich', 'coef_test'),
    'rdrobust_r': ('rdrobust', 'rdrobust'),
    'rddensity': ('rddensity', 'rddensity'),
    'rdpower': ('rdpower', 'rdpower'),
    'grf': ('grf', 'causal_forest'),
}


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_method(request):
    """Map an explicit estimand and design to its existing execution owner."""
    required = {'question','estimand','identification','design','outcome_scale','data_structure','treatment_pattern','dependence'}
    contract_fields = ('population','comparison_group','observation_unit','assignment_unit',
                       'unit','period','assignment','weights','inference')
    optional = {'adopted_method','adopted_specification','options','score','structural_model','implementation',*contract_fields}
    if not isinstance(request, dict) or not required <= request.keys() or set(request)-required-optional:
        raise ValueError(f'selection requires {sorted(required)} and accepts {sorted(optional)}')
    if any(not isinstance(request[k], str) or not request[k].strip() for k in required):
        raise ValueError('selection fields must be explicit nonempty strings')
    adopted_spec = request.get('adopted_specification', {})
    if not isinstance(adopted_spec, dict):
        raise ValueError('adopted_specification must be an existing specification object')
    if any(not isinstance(s.get('options', {}), dict) for s in (request, adopted_spec)):
        raise ValueError('selection and adopted specification options must be objects')
    adopted = request.get('adopted_method', adopted_spec.get('method', adopted_spec.get('model')))
    if adopted is not None and (not isinstance(adopted, str) or not adopted.strip()):
        raise ValueError('adopted_method must be a nonempty string')
    stored_method = adopted_spec.get('method', adopted_spec.get('model'))
    if stored_method and adopted and stored_method != adopted:
        raise ValueError('adopted_method must match adopted_specification')
    def scientific_contract(s):
        fields = {k:s[k] for k in contract_fields if k in s}
        o = s.get('options', {})
        if 'comparison_group' not in fields and 'control_group' in o:
            fields['comparison_group'] = o['control_group']
        if 'weights' not in fields:
            weights = {k:o[k] for k in ('weightsname','fix_weights') if k in o}
            for group in ('args','columns'):
                if not isinstance(o.get(group, {}), dict):
                    raise ValueError('native args and columns must be objects')
                selected = {k:v for k,v in o.get(group, {}).items() if k in ('weights','i.weights','sample.weights','weight')}
                if selected: weights[group] = selected
            if weights: fields['weights'] = weights
        return fields
    adopted_contract = scientific_contract(adopted_spec)
    proposed_contract = scientific_contract({**adopted_spec, **request})
    forward_options = request.get('options', adopted_spec.get('options', {}))
    design = request['design']; structure = request['data_structure']; pattern = request['treatment_pattern']
    owner = 'skills/econ-data/scripts/research_causal.py run'
    conditions = []
    method_quantity = request['estimand']
    if 'implementation' in request and design != 'heterogeneous_effect':
        raise ValueError('implementation selects grf or econml for heterogeneous_effect')
    if design == 'conditional_mean':
        if request['outcome_scale'] == 'level': method = 'fixest_ols'
        elif request['outcome_scale'] == 'proportional_nonnegative': method = 'fixest_ppml'
        else: raise ValueError('conditional_mean requires level or proportional_nonnegative outcome_scale')
        conditions = ['adopted conditional mean', 'fixed effects and weights from the target population', 'covariance matched to dependence']
    elif design == 'did':
        if pattern == 'absorbing_staggered': method = 'staggered_did'
        elif pattern in ('reversals','changing_dose','treatment_histories'): method = 'did_multiplegt_dyn'
        elif pattern == 'two_period':
            if structure == 'panel': method = 'drdid_panel'
            elif structure == 'repeated_cross_section': method = 'drdid_rc'
            else: raise ValueError('two-period DID requires panel or repeated_cross_section data_structure')
        else: raise ValueError('DID treatment_pattern must identify two_period, absorbing_staggered, reversals, changing_dose or treatment_histories')
        conditions = ['specified untreated-trend scale and comparison eligibility', 'adopted anticipation and reference period', 'cohort or switcher population and horizon weights', 'assignment-matched clustering and interval family']
    elif design == 'rdd':
        method = 'rdrobust_r'; conditions = ['cutoff and running-variable support', 'sharp, fuzzy or derivative target', 'adopted bandwidth, bias correction and dependence']
    elif design == 'density_at_cutoff':
        method = 'rddensity'; conditions = ['adopted cutoff', 'running-variable measurement and mass points']
    elif design == 'rd_power':
        method = 'rdpower'; conditions = ['adopted alternative effect, sample size and bandwidth', 'same RD estimator and dependence as the research design']
    elif design in ('iv','instrumental_variables'):
        method = 'iv_gmm'
        conditions = ['specified endogenous regressors and excluded instruments', 'instrument exclusion and rank identify the adopted moment coefficient', 'robust or adopted cluster covariance and the same moment weighting']
        method_quantity = 'linear IV moment coefficient estimated by two-step GMM'
    elif design == 'weak_instrument_inference':
        method = 'iv_ar'
        conditions = ['one endogenous regressor and the adopted excluded instruments', 'independent homoskedastic normal outcome errors with fixed instruments', 'adopted alpha and inversion of the Anderson-Rubin F test']
        method_quantity = 'Anderson-Rubin confidence set for the specified endogenous-regressor coefficient'
    elif design == 'synthetic_control':
        method = 'synthetic_control'
        conditions = ['one treated unit and at least two balanced eligible donors', 'adopted training, untreated validation and post-treatment periods', 'nonnegative donor weights summing to one and held-out gap inference']
        method_quantity = 'post-treatment treated-minus-synthetic gap relative to its held-out untreated validation mean'
    elif design == 'generalized_synth':
        method = 'generalized_synth'
        conditions = ['balanced panel with never-treated controls and one common absorbing adoption date', 'adopted factor rank and two-way interactive-effects specification', 'parametric bootstrap under the adopted error model']
        method_quantity = 'treated-block average and event-time effects relative to the interactive fixed-effects counterfactual'
    elif design == 'orthogonal_score':
        score = request.get('score')
        if score not in ('plr','did'): raise ValueError('this DoubleML owner supports score plr or did')
        method = 'dml_' + score; owner = 'skills/econ-data/scripts/research.py estimate'
        conditions = ['score identifies the stated target', 'folds preserve independent sampling units', 'nuisance fitting and tuning use training folds']
    elif design == 'heterogeneous_effect':
        implementation = request.get('implementation', 'grf')
        if implementation not in ('grf','econml'):
            raise ValueError('heterogeneous_effect implementation must be grf or econml')
        method = 'causal_forest' if implementation == 'econml' else 'grf'
        conditions = ['conditional exchangeability and overlap',
            'binary treatment with cross-fitted nuisance learners' if implementation == 'econml' else 'binary CATE or continuous covariance-to-variance target',
            'adopted effect covariates, independent sampling units and averaging population']
        method_quantity = 'conditional treatment effects and their adopted target-population aggregate'
    elif design == 'policy_learning':
        method = 'policy_tree'
        conditions = ['binary treatment and known assignment propensities', 'distinct training and evaluation samples', 'adopted effect covariates and the untreated-all baseline']
        method_quantity = 'held-out policy value gain relative to assigning treatment zero to every evaluation unit'
    elif design == 'parallel_trend_sensitivity':
        method = 'honest_did'; conditions = ['saved coefficients and joint covariance', 'ordered pre/post terms with universal reference', 'adopted restriction, magnitude grid and post-treatment contrast']
    elif design == 'wild_cluster_inference':
        method = 'wild_cluster_bootstrap'; conditions = ['saved supported linear-model fit', 'adopted null, clusters, bootstrap weights and repetitions']
    elif design == 'small_cluster_inference':
        method = 'club_sandwich'; conditions = ['saved supported model fit', 'adopted CR correction, coefficient contrast and degrees-of-freedom approximation']
    elif design == 'structural':
        model = request.get('structural_model')
        if model in ('blp','auction','auction_fit','search','bargaining','platform','matching'):
            method = model; owner = 'skills/econ-data/scripts/research_markets.py run'
        elif model in ('replacement','latent_replacement','discrete_entry','dynamic_adoption_blp','continuous_time_entry','capacity_product_game'):
            method = model; owner = 'skills/econ-data/scripts/research_dynamic.py run'
        elif model == 'dynamic_game':
            method = model; owner = 'skills/econ-data/scripts/equity.py dynamic'
        else:
            raise ValueError('structural_model must name a documented existing market, replacement, entry, adoption or dynamic-game model')
        conditions = ['adopted primitives, timing, moments and excluded variation', 'normalizations and equilibrium selection', 'counterfactual re-solves affected endogenous choices']
    else:
        raise ValueError('unsupported design; use the documented selection contracts')
    if method in R_METHODS:
        package, function = R_METHODS[method]; engine = f'{package}::{function}'
    else:
        engine = {'staggered_did':'did::att_gt + did::aggte','dml_plr':'doubleml.DoubleMLPLR',
                  'dml_did':'doubleml.did.DoubleMLDID','blp':'pyblp.Problem.solve',
                  'iv_gmm':'linearmodels.iv.IVGMM',
                  'iv_ar':'linearmodels.iv.IV2SLS + statsmodels.OLS + scipy.stats.f',
                  'synthetic_control':'pysyncon.Synth + statsmodels.OLS',
                  'generalized_synth':'gsynth::gsynth',
                  'causal_forest':'econml.dml.CausalForestDML',
                  'policy_tree':'econml.policy.DRPolicyTree + statsmodels.OLS',
                  'bargaining':'research_markets.bargain','dynamic_game':'equity_io.dynamic_game'}.get(method)
        if engine is None:
            engine = 'research_dynamic.observed_run' if owner.startswith('skills/econ-data/scripts/research_dynamic.py') else 'research_markets.'+method
    changes = []
    if adopted and adopted != method:
        changes.append({'field':'method','adopted':adopted,'selected':method})
    for key in ('estimand','identification'):
        if key in adopted_spec and adopted_spec[key] != request[key]:
            changes.append({'field':key,'adopted':adopted_spec[key],'selected':request[key]})
    for key in contract_fields:
        if key in adopted_contract and proposed_contract.get(key) != adopted_contract[key]:
            changes.append({'field':key,'adopted':adopted_contract[key],'selected':proposed_contract.get(key)})
    if 'options' in adopted_spec and forward_options != adopted_spec['options']:
        changes.append({'field':'options','adopted':adopted_spec['options'],'selected':forward_options})
    relation = {'adopted_estimand':adopted_spec.get('estimand'),
                'requested_estimand':request['estimand'],'selected_method_quantity':method_quantity}
    return {'status':'design_change' if changes else 'selected','question':request['question'],
        'estimand':request['estimand'],'identification':request['identification'],
        'method':method,'engine':engine,'entry_point':owner,'determining_conditions':conditions,
        'forward_options':forward_options,'design_contract':proposed_contract,
        'adopted_specification':adopted_spec,'estimand_relation':relation,
        'design_change':{'adopted_method':adopted,'selected_method':method,'changes':changes,'estimand_relation':relation} if changes else None,
        'requested_design':{k:request[k] for k in ('outcome_scale','data_structure','treatment_pattern','dependence')},
        'executed':False}


def _network(spec_path, filename, ids):
    from libpysal.weights import W
    wp=Path(filename); wp=(wp if wp.is_absolute() else spec_path.parent/wp).resolve()
    edge=pd.read_csv(wp,dtype={'source':'string','target':'string'})
    if set(edge.columns)!={'source','target','weight'} or edge.isna().any().any() or edge.duplicated(['source','target']).any(): raise ValueError('weights CSV needs distinct source,target,weight edges')
    edge['weight']=pd.to_numeric(edge['weight'],errors='raise')
    if not np.isfinite(edge['weight']).all() or (edge['weight']<=0).any() or (edge['source']==edge['target']).any(): raise ValueError('weights must be positive finite and exclude self-edges')
    if set(edge['source'])!=set(ids) or not set(edge['target'])<=set(ids): raise ValueError('each unit needs a neighbor and all endpoints must match input IDs')
    grouped=edge.groupby('source',sort=False)
    neighbors={i:grouped.get_group(i)['target'].astype(str).tolist() for i in ids}
    weights={i:grouped.get_group(i)['weight'].astype(float).tolist() for i in ids}
    w=W(neighbors,weights,id_order=ids,silence_warnings=True); w.transform='r'
    return w,wp


def _staggered_did(spec, data):
    """Call did with the adopted options and serialize its fitted objects."""
    import os
    import re
    import subprocess
    import tempfile

    opt = spec['options']
    entity, time, cohort = (opt[k] for k in ('entity', 'time', 'cohort'))
    names = [spec['outcome'], *spec['regressors'], entity, time, cohort]
    if (len(set(names)) != len(names) or
            spec['id'] in (entity, time, cohort) or
            any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', k) for k in names)):
        raise ValueError('DID requires distinct simple column names')
    if data.duplicated([entity, time]).any():
        raise ValueError('DID requires unique entity-time observations')
    grid = np.sort(data[time].unique())
    if (len(grid) < 2 or not np.equal(grid, np.floor(grid)).all() or
            not np.all(np.diff(grid) == 1) or
            not np.equal(data[cohort], np.floor(data[cohort])).all()):
        raise ValueError('DID requires consecutive integer period codes and integer treatment cohorts')
    panel = opt.get('panel', True)
    if panel and data.groupby(entity)[cohort].nunique().max() != 1:
        raise ValueError('DID panel cohorts must remain fixed within entity')
    if not panel and data[entity].duplicated().any():
        raise ValueError('repeated cross sections require a distinct entity ID for each observation')
    if opt['control_group'] not in ('nevertreated', 'notyettreated'):
        raise ValueError('DID control_group must be nevertreated or notyettreated')
    if opt['control_group'] == 'nevertreated' and not (data[cohort] == 0).any():
        raise ValueError('nevertreated DID requires a never-treated cohort coded zero')
    for key in ('panel', 'allow_unbalanced_panel', 'bstrap', 'cband', 'faster_mode'):
        if key in opt and not isinstance(opt[key], bool):
            raise ValueError(f'DID {key} must be boolean')
    for key, minimum in (('anticipation', 0), ('biters', 1), ('seed', 0)):
        if key in opt and (isinstance(opt[key], bool) or not isinstance(opt[key], int) or opt[key] < minimum):
            raise ValueError(f'DID {key} must be an integer >= {minimum}')
    if opt.get('base_period', 'varying') not in ('varying', 'universal'):
        raise ValueError('DID base_period must be varying or universal')
    if opt.get('est_method', 'dr') not in ('dr', 'ipw', 'reg'):
        raise ValueError('DID est_method must be dr, ipw or reg')
    clusters = opt.get('clustervars', [])
    if (not isinstance(clusters, list) or len(clusters) != len(set(clusters)) or
            any(not isinstance(k, str) or not k for k in clusters) or
            len(set(clusters) - {entity}) > 1):
        raise ValueError('DID clustervars accepts the entity and one additional cluster column')
    aggregate = opt.get('aggregation', {})
    aggregate_keys = {'type', 'balance_e', 'min_e', 'max_e', 'na.rm', 'bstrap', 'biters', 'cband', 'alp', 'clustervars'}
    if not isinstance(aggregate, dict) or set(aggregate) - aggregate_keys:
        raise ValueError('DID aggregation must contain documented aggte options')
    if aggregate.get('type', 'dynamic') not in ('simple', 'dynamic', 'group', 'calendar'):
        raise ValueError('DID aggregation type must be simple, dynamic, group or calendar')
    if 'clustervars' in aggregate and aggregate['clustervars'] != clusters:
        raise ValueError('aggte clustervars must match att_gt clustervars')
    if opt.get('cband', False) and not opt.get('bstrap', False):
        raise ValueError('DID simultaneous bands require bstrap=true')
    if aggregate.get('cband', opt.get('cband', False)) and not aggregate.get('bstrap', opt.get('bstrap', False)):
        raise ValueError('aggte simultaneous bands require bstrap=true')
    for key in ('alp',):
        for settings in (opt, aggregate):
            if key in settings and (isinstance(settings[key], bool) or not isinstance(settings[key], (int, float)) or not 0 < settings[key] < 1):
                raise ValueError('DID alp must lie strictly between zero and one')
    if 'weightsname' in opt:
        weights = data[opt['weightsname']]
        if (weights < 0).any() or weights.sum() <= 0:
            raise ValueError('DID sampling weights must be nonnegative with positive total')

    # JSON supplies named arguments; the R package owns preprocessing, fitting,
    # aggregation, bootstrap standard errors and simultaneous critical values.
    rcode = r'''
args <- commandArgs(trailingOnly=TRUE)
suppressPackageStartupMessages(library(did))
suppressPackageStartupMessages(library(jsonlite))
if (packageVersion('did') < '2.5.1') stop('did >= 2.5.1 is required')
s <- fromJSON(args[2], simplifyVector=TRUE); o <- s$options
classes <- setNames('character', s$id)
d <- read.csv(args[1], check.names=FALSE, colClasses=classes)
unit <- o$entity; tm <- o$time; gn <- o$cohort
original_unit <- as.character(d[[unit]])
d[[unit]] <- match(original_unit, unique(original_unit))
call_args <- list(yname=s$outcome, tname=tm, idname=unit, gname=gn,
  xformla=reformulate(if(length(s$regressors)) s$regressors else '1'), data=d,
  panel=TRUE, allow_unbalanced_panel=FALSE, anticipation=0L,
  bstrap=FALSE, cband=FALSE, est_method='dr', base_period='varying', cores=1L,
  control_group=o$control_group)
forward <- c('panel','allow_unbalanced_panel','anticipation','weightsname',
  'fix_weights','alp','bstrap','biters','clustervars','cband','est_method',
  'base_period','faster_mode')
for (k in intersect(names(o), forward)) call_args[k] <- o[k]
if (!is.null(o$seed)) set.seed(o$seed)
invisible(capture.output(a <- do.call(did::att_gt, call_args)))
agg_args <- list(MP=a, type='dynamic')
if (length(o$aggregation)) for(k in names(o$aggregation)) agg_args[k] <- o$aggregation[k]
invisible(capture.output(e <- do.call(did::aggte, agg_args)))
ap <- a$DIDparams; ep <- e$DIDparams
if (isTRUE(call_args$cband) && !isTRUE(ap$cband)) stop('did did not retain the requested group-time simultaneous band')
requested_band <- if(!is.null(o$aggregation$cband)) o$aggregation$cband else call_args$cband
if (isTRUE(requested_band) && e$type != 'simple' && !isTRUE(ep$cband)) stop('did did not retain the requested aggregate simultaneous band')
pd <- as.data.frame(ap$data)
if (!all(c(unit,tm) %in% names(pd))) stop('did did not retain the entity-time sample mapping')
row_index <- match(paste(pd[[unit]],pd[[tm]],sep=':'), paste(d[[unit]],d[[tm]],sep=':'))
if (anyNA(row_index)) stop('did sample mapping failed')
fitted <- d[row_index,,drop=FALSE]
if(!isTRUE(all.equal(pd[[s$outcome]], fitted[[s$outcome]],check.attributes=FALSE))) stop('did sample mapping changed outcomes')
official_weights <- if('.w' %in% names(pd)) pd$.w else pd$weights
if(length(official_weights) != nrow(fitted)) stop('did did not retain observation-level sampling weights')
grid <- sort(unique(fitted[[tm]]))

# Retain the official influence-function covariance separately from the selected
# bootstrap SE. Cluster sums follow the package's analytical covariance formula.
if_names <- switch(e$type, dynamic=c('dynamic.inf.func','dynamic.inf.func.e'),
  group=c('selective.inf.func','selective.inf.func.g'),
  calendar=c('calendar.inf.func','calendar.inf.func.t'), simple='simple.att')
influences <- do.call(cbind, e$inf.function[if_names])
analytic_cov <- function(x, params) {
  x <- as.matrix(x); n <- nrow(x)
  extra <- setdiff(params$clustervars, c(params$idname, unit, ''))
  if (length(extra)) {
    if (length(params$cluster_vector) != n) stop('did cluster vector does not match influence functions')
    x <- rowsum(x, params$cluster_vector, reorder=TRUE)
  }
  unname(crossprod(x) / n^2)
}
vv <- analytic_cov(influences, ep)
gv <- analytic_cov(a$inffunc, ap)

# These are the exact cohort mass inputs used by compute.aggte in did 2.5.1.
if (ap$panel) {
  if (isTRUE(ap$faster_mode) && !is.null(ap$time_invariant_data)) {
    population <- as.data.frame(ap$time_invariant_data)
  } else population <- pd[pd[[tm]] == min(grid),,drop=FALSE]
} else {
  population <- suppressWarnings(aggregate(pd, list(pd[[ap$idname]]), mean))
  population <- population[,-1L,drop=FALSE]
}
gpop <- population[[gn]]; gpop[is.infinite(gpop)] <- 0
wp <- if('.w' %in% names(population)) population$.w else population$weights
if (is.null(wp)) stop('did did not retain aggregation sampling weights')
mass <- vapply(a$group, function(g) sum(wp[gpop == g]), numeric(1))
cell_role <- function(g,t) {
  if (ap$base_period == 'universal' && t == max(grid[grid < g-ap$anticipation])) 'reference'
  else if (t >= g) 'post_treatment_att'
  else if (t >= g-ap$anticipation) 'anticipation'
  else 'pretreatment_diagnostic'
}
cells <- lapply(seq_along(a$att), function(j) {
  g <- a$group[j]; t <- a$t[j]
  base <- if(ap$base_period == 'universal' || t >= g) max(grid[grid < g-ap$anticipation]) else grid[match(t,grid)-1L]
  target <- fitted[[gn]] == g
  control <- fitted[[gn]] == 0
  if(ap$control_group == 'notyettreated') control <- control | (fitted[[gn]] > max(t,base)+ap$anticipation & fitted[[gn]] != g)
  take <- fitted[[tm]] %in% c(base,t) & (target | control)
  rows <- fitted[take,,drop=FALSE]
  raw_sampling <- if(is.null(o$weightsname)) rep(1,nrow(rows)) else rows[[o$weightsname]]
  sampling <- official_weights[take]
  weight_period <- if((ap$panel && !identical(o$fix_weights,'varying')) || isTRUE(o$fix_weights %in% c('first_period','base_period'))) {
    if(identical(o$fix_weights,'first_period')) min(grid)
    else if(identical(o$fix_weights,'base_period')) max(grid[grid < g-ap$anticipation])
    else min(base,t)
  } else NULL
  if (!is.null(weight_period)) {
    weight_rows <- fitted[fitted[[tm]] == weight_period,,drop=FALSE]
    weight_index <- match(rows[[unit]], weight_rows[[unit]])
    raw_sampling <- if(is.null(o$weightsname)) rep(1,nrow(rows)) else weight_rows[[o$weightsname]][weight_index]
    sampling <- official_weights[fitted[[tm]] == weight_period][weight_index]
    present <- rows[[unit]] %in% weight_rows[[unit]]
    rows <- rows[present,,drop=FALSE]; sampling <- sampling[present]; raw_sampling <- raw_sampling[present]
  }
  list(group=g,time=t,event_time=t-g,base_period=base,role=cell_role(g,t),
    estimate=a$att[j],se=a$se[j],critical_value=as.numeric(a$c),
    ci_low=a$att[j]-as.numeric(a$c)*a$se[j],ci_high=a$att[j]+as.numeric(a$c)*a$se[j],
    sample_ids=I(as.character(rows[[s$id]])),
    treated_ids=I(as.character(rows[[s$id]][rows[[gn]]==g])),
    control_ids=I(as.character(rows[[s$id]][rows[[gn]]!=g])),
    sampling_weights=I(sampling),raw_sampling_weights=I(raw_sampling),sampling_weight_period=weight_period)
})

components <- lapply(seq_along(e$egt), function(k) {
  z <- e$egt[k]
  keep <- switch(e$type, dynamic=(a$t-a$group == z), group=(a$group == z & a$t >= a$group), calendar=(a$t == z & a$group <= a$t))
  if (e$type == 'dynamic' && !is.null(e$balance_e)) keep <- keep & max(grid)-a$group >= e$balance_e
  if (e$type == 'group' && isTRUE(is.finite(agg_args$max_e))) keep <- keep & a$t <= a$group+agg_args$max_e
  keep <- which(keep & !is.na(a$att))
  weights <- mass[keep] / sum(mass[keep])
  ids <- unique(unlist(lapply(cells[keep], function(x) x$treated_ids), use.names=FALSE))
  list(index=z,cohorts=I(as.numeric(a$group[keep])),times=I(as.numeric(a$t[keep])),
    weights=I(weights),treated_sample_ids=I(ids),
    treated_units=length(unique(d[[unit]][match(ids,d[[s$id]])])),
    estimate=e$att.egt[k],se=e$se.egt[k],
    ci_low=e$att.egt[k]-e$crit.val.egt*e$se.egt[k],
    ci_high=e$att.egt[k]+e$crit.val.egt*e$se.egt[k])
})
settings <- function(params) {
  keys <- c('panel','allow_unbalanced_panel','control_group','anticipation','weightsname',
    'fix_weights','alp','bstrap','biters','clustervars','cband','est_method','base_period','faster_mode')
  params[intersect(keys,names(params))]
}
obj <- list(r_version=as.character(getRversion()), did_version=as.character(packageVersion('did')),
  drdid_version=as.character(packageVersion('DRDID')),
  runtime=list(library_paths=I(.libPaths()),working_directory=getwd(),profile_user=Sys.getenv('R_PROFILE_USER',unset=NA_character_)),
  signatures=list(att_gt=names(formals(did::att_gt)),aggte=names(formals(did::aggte))),
  att_gt_options=settings(ap),aggregate_options=c(settings(ep), list(type=e$type,balance_e=agg_args$balance_e,min_e=agg_args$min_e,max_e=agg_args$max_e,na.rm=isTRUE(agg_args$na.rm))),
  event_times=e$egt,coef=c(e$overall.att,e$att.egt),engine_se=c(e$overall.se,e$se.egt),
  critical_values=c(qnorm(1-ep$alp/2),rep(e$crit.val.egt,length(e$egt))),
  cov=vv,group_cov=gv,groups=a$group,times=a$t,att=a$att,group_se=a$se,n=a$n,
  fitted_ids=I(as.character(fitted[[s$id]])),components=components,cells=cells,
  pretreatment_test=list(statistic=a$W,p_value=a$Wpval),
  influence_unit_ids=I(rownames(a$inffunc)))
write_json(obj,args[3],auto_unbox=TRUE,digits=16,na='null',null='null')
'''
    with tempfile.TemporaryDirectory(prefix='causal-did-') as tmp:
        tmp = Path(tmp)
        data.to_csv(tmp / 'data.csv', index=False)
        (tmp / 'spec.json').write_text(json.dumps(spec), encoding='utf-8')
        proc = subprocess.run(['Rscript', '-', str(tmp / 'data.csv'),
                               str(tmp / 'spec.json'), str(tmp / 'result.json')],
                              input=rcode, text=True, capture_output=True, env=os.environ.copy())
        if proc.returncode:
            raise ArithmeticError('did engine failed: ' + proc.stderr[-4000:])
        result = json.loads((tmp / 'result.json').read_text(encoding='utf-8'))
    result['engine_messages'] = proc.stderr.strip()
    return result


def _official_r(spec, spec_path):
    """Execute a named official R interface in the existing result lifecycle."""
    import base64
    import os
    import subprocess
    import tempfile

    method = spec['method']; opt = spec['options']
    required = {
        'ols_r': set(), 'fixest_ols': set(), 'fixest_ppml': set(),
        'drdid_panel': {'entity','time','pre','post','treatment'},
        'drdid_rc': {'time','pre','post','treatment'},
        'did_multiplegt_dyn': {'entity','time','treatment'},
        'honest_did': {'pre_terms','post_terms','restriction'},
        'wild_cluster_bootstrap': set(), 'club_sandwich': set(),
        'rdrobust_r': {'running'}, 'rddensity': {'running'}, 'rdpower': {'running'}, 'grf': {'treatment'},
    }[method]
    optional = {'args','columns','seed'}
    if method in ('ols_r','fixest_ols','fixest_ppml'): optional.add('fixed_effects')
    if method == 'grf': optional.add('aggregation')
    if not required <= opt.keys() or set(opt)-required-optional:
        raise ValueError(f'{method} options require {sorted(required)} and accept {sorted(optional)}')
    if spec['inference'] != {'type':'official'}:
        raise ValueError('official R methods require inference={"type":"official"}; specify inference options in options.args')
    if not isinstance(opt.get('args', {}), dict) or not isinstance(opt.get('columns', {}), dict):
        raise ValueError('options.args and options.columns must be objects')
    if 'seed' in opt and (isinstance(opt['seed'], bool) or not isinstance(opt['seed'], int) or opt['seed'] < 0):
        raise ValueError('seed must be a nonnegative integer')
    path = Path(spec['data']); path = (path if path.is_absolute() else spec_path.parent/path).resolve()
    saved_input = method in ('honest_did','wild_cluster_bootstrap','club_sandwich')
    source = json.loads(path.read_text()) if saved_input else None
    if method in ('wild_cluster_bootstrap','club_sandwich'):
        native = source.get('native_fit', {})
        if native.get('format') != 'R-serialize-v3':
            raise ValueError('post-estimation requires a saved native fit from this runner')
        if hashlib.sha256(base64.b64decode(native['data'])).hexdigest() != native['sha256']:
            raise ValueError('saved native fit hash does not match')
    package, function = R_METHODS[method]
    if method == 'honest_did':
        if opt['restriction'] not in ('relative_magnitudes','smoothness'):
            raise ValueError('HonestDiD restriction must be relative_magnitudes or smoothness')
        if opt['restriction'] == 'smoothness': function = 'createSensitivityResults'
        terms = opt['pre_terms'] + opt['post_terms']
        if (not opt['pre_terms'] or not opt['post_terms'] or len(terms) != len(set(terms)) or
                any(t not in source['coefficients'] for t in terms)):
            raise ValueError('HonestDiD requires distinct saved pre_terms and post_terms in their adopted order')
        if source.get('method') == 'staggered_did' and source['options'].get('base_period','varying') != 'universal':
            raise ValueError('HonestDiD event studies require an adopted universal reference period')
    rcode = r'''
args <- commandArgs(trailingOnly=TRUE)
suppressPackageStartupMessages(library(jsonlite))
s <- fromJSON(args[1], simplifyVector=TRUE); o <- s$options; method <- s$method
pkg <- args[3]; fname <- args[4]
if(!requireNamespace(pkg,quietly=TRUE)) stop(paste('Install the selected official package:',pkg))
fun <- getExportedValue(pkg,fname)
formal_names <- names(formals(fun))
invoke <- function(f, a, additional=character()) {
  unknown <- setdiff(names(a),c(names(formals(f)),additional))
  if(length(unknown)) stop(paste('Unsupported official option:',paste(unknown,collapse=', ')))
  do.call(f,a)
}
if(!is.null(o$seed)) set.seed(o$seed)
postprocess <- method %in% c('honest_did','wild_cluster_bootstrap','club_sandwich')
if(postprocess) {
  source <- fromJSON(args[2],simplifyVector=FALSE)
  if(method != 'honest_did') {
    native <- unserialize(base64_dec(source$native_fit$data))
    fit_source <- native$fit; d <- native$data; ids <- native$ids
  }
} else {
  d <- read.csv(args[2],check.names=FALSE,colClasses=setNames('character',s$id))
  if(!s$id %in% names(d) || anyNA(d[[s$id]]) || anyDuplicated(d[[s$id]])) stop('Input IDs must be nonmissing and unique')
  ids <- as.character(d[[s$id]])
}
call_args <- o$args
if(is.null(call_args)) call_args <- list()
if(length(o$columns)) for(k in names(o$columns)) {
  if(k %in% names(call_args)) stop(paste('Argument appears in both args and columns:',k))
  cols <- o$columns[[k]]
  if(!all(cols %in% names(d))) stop(paste('Missing bound columns for',k))
  call_args[[k]] <- if(length(cols)==1L) d[[cols]] else as.matrix(d[,cols,drop=FALSE])
}
owned <- list(); diagnostics <- list(); estimates <- NULL; intervals <- NULL; covariance <- NULL; rows <- NULL
kind <- 'regression'
if(method %in% c('ols_r','fixest_ols','fixest_ppml')) {
  model_columns <- c(s$outcome,s$regressors,o$fixed_effects)
  if(!all(grepl('^[A-Za-z_][A-Za-z0-9_]*$',model_columns))) stop('Model columns must use simple names')
  rhs <- if(length(s$regressors)) paste(s$regressors,collapse='+') else '1'
  if(method=='ols_r') {
    if(length(o$fixed_effects)) rhs <- paste(rhs,paste0('factor(',o$fixed_effects,')',collapse='+'),sep='+')
    owned <- list(formula=as.formula(paste(s$outcome,'~',rhs)),data=d)
  } else {
    fml <- paste(s$outcome,'~',rhs)
    if(length(o$fixed_effects)) fml <- paste(fml,'|',paste(o$fixed_effects,collapse='+'))
    owned <- list(fml=as.formula(fml),data=d,data.save=TRUE)
    for(k in intersect(c('vcov','weights','offset','cluster','panel.id'),names(call_args))) {
      if(is.character(call_args[[k]]) && length(call_args[[k]])==1L && startsWith(call_args[[k]],'~')) call_args[[k]] <- as.formula(call_args[[k]])
    }
    if(is.list(call_args$ssc)) call_args$ssc <- invoke(fixest::ssc,call_args$ssc)
  }
} else if(method %in% c('drdid_panel','drdid_rc')) {
  if(!all(c(s$outcome,s$regressors,o$time,o$treatment) %in% names(d))) stop('Missing DRDID columns')
    if(length(unique(d[[o$time]]))!=2L || !all(sort(unique(d[[o$time]])) == c(o$pre,o$post)) || o$pre>=o$post) stop('DRDID requires exactly the adopted pre and post periods')
  if(!all(d[[o$treatment]] %in% c(0,1))) stop('DRDID treatment identifies the binary treated group in both periods')
  if(method=='drdid_panel') {
    if(anyDuplicated(d[,c(o$entity,o$time)])) stop('DRDID requires unique entity-time pairs')
    before <- d[d[[o$time]]==o$pre,,drop=FALSE]; after <- d[d[[o$time]]==o$post,,drop=FALSE]
    if(!setequal(before[[o$entity]],after[[o$entity]])) stop('DRDID panel requires both observations for every entity')
    after <- after[match(before[[o$entity]],after[[o$entity]]),,drop=FALSE]
    if(any(before[[o$treatment]] != after[[o$treatment]])) stop('DRDID treated-group membership must be fixed')
    if('i.weights' %in% names(o$columns)) call_args$i.weights <- before[[o$columns[['i.weights']]]]
    x <- model.matrix(reformulate(if(length(s$regressors)) s$regressors else '1'),before)
    owned <- list(y1=after[[s$outcome]],y0=before[[s$outcome]],D=before[[o$treatment]],covariates=x,inffunc=TRUE)
    diagnostics <- list(entity_ids=I(as.character(before[[o$entity]])),pre_ids=I(before[[s$id]]),post_ids=I(after[[s$id]]),covariate_period=o$pre)
  } else {
    x <- model.matrix(reformulate(if(length(s$regressors)) s$regressors else '1'),d)
    owned <- list(y=d[[s$outcome]],post=as.integer(d[[o$time]]==o$post),D=d[[o$treatment]],covariates=x,inffunc=TRUE)
    diagnostics <- list(covariate_period='observation period')
  }
} else if(method=='did_multiplegt_dyn') {
  owned <- list(df=d,outcome=s$outcome,group=o$entity,time=o$time,treatment=o$treatment,controls=s$regressors)
  if(is.null(call_args$graph_off)) call_args$graph_off <- TRUE
  if(is.null(call_args$save_sample)) call_args$save_sample <- TRUE
  kind <- 'event-study'
} else if(method=='honest_did') {
  terms <- c(o$pre_terms,o$post_terms)
  bhat <- vapply(terms,function(t) source$coefficients[[t]],numeric(1))
  sigma <- do.call(rbind,lapply(terms,function(t) vapply(terms,function(u) source$covariance[[t]][[u]],numeric(1))))
  owned <- list(betahat=bhat,sigma=sigma,numPrePeriods=length(o$pre_terms),numPostPeriods=length(o$post_terms))
  ids <- unlist(source$sample$included_ids); d <- NULL; kind <- 'sensitivity'
  diagnostics <- list(terms=terms,source_covariance_kind=source$covariance_kind)
} else if(method=='wild_cluster_bootstrap') {
  supported <- intersect(class(fit_source),c('fixest','lm','felm'))
  if(!length(supported)) stop('boottest requires a supported saved linear-model object')
  fun <- getS3method('boottest',supported[1],envir=asNamespace(pkg))
  formal_names <- names(formals(fun)); owned <- list(object=fit_source)
  if(is.list(call_args$ssc)) call_args$ssc <- invoke(getExportedValue(pkg,'boot_ssc'),call_args$ssc)
  kind <- 'sensitivity'
} else if(method=='club_sandwich') {
  owned <- list(obj=fit_source); kind <- 'sensitivity'
} else if(method=='rdrobust_r') {
  owned <- list(y=d[[s$outcome]],x=d[[o$running]]); kind <- 'rdd'
} else if(method=='rddensity') {
  owned <- list(X=d[[o$running]]); kind <- 'rdd'
} else if(method=='rdpower') {
  if(is.null(call_args$tau)) stop('rdpower requires the adopted alternative effect in args.tau')
  owned <- list(data=as.matrix(d[,c(s$outcome,o$running)])); kind <- 'sensitivity'
} else if(method=='grf') {
  owned <- list(X=as.matrix(d[,s$regressors,drop=FALSE]),Y=d[[s$outcome]],W=d[[o$treatment]])
  kind <- 'heterogeneity'
}
if(length(intersect(names(owned),names(call_args)))) stop(paste('options.args cannot replace owned model inputs:',paste(intersect(names(owned),names(call_args)),collapse=', ')))
all_args <- c(owned,call_args)
additional <- character()
if(method=='club_sandwich' && is.character(call_args$vcov)) {
  covariance_method <- NULL
  for(cls in class(fit_source)) {
    covariance_method <- getS3method('vcovCR',cls,optional=TRUE,envir=asNamespace(pkg))
    if(!is.null(covariance_method)) break
  }
  if(is.null(covariance_method)) stop('clubSandwich has no vcovCR method for this saved model class')
  additional <- names(formals(covariance_method))
}
invisible(capture.output(fit <- invoke(fun,all_args,additional)))
if(method %in% c('ols_r','fixest_ols','fixest_ppml')) {
  if(inherits(fit,'fixest_multi')) stop('This result contract requires one fitted model')
  table <- if(method=='ols_r') coef(summary(fit)) else fixest::coeftable(fit)
  intervals <- confint(fit); covariance <- vcov(fit)
  estimates <- data.frame(term=rownames(table),estimate=table[,1],se=table[,2],p_value=table[,4],ci_low=intervals[,1],ci_high=intervals[,2],row.names=NULL)
  used <- if(method=='ols_r') as.integer(rownames(model.frame(fit))) else fixest::obs(fit)
  ids <- ids[used]; d <- d[used,,drop=FALSE]
  diagnostics <- list(observations=nobs(fit),fixed_effects=o$fixed_effects)
  if(inherits(fit,'fixest')) diagnostics$n_clusters <- attr(fit$cov.scaled,'G')
} else if(method %in% c('drdid_panel','drdid_rc')) {
  estimates <- data.frame(term='ATT',estimate=fit$ATT,se=fit$se,p_value=2*pnorm(-abs(fit$ATT/fit$se)),ci_low=fit$lci,ci_high=fit$uci)
  covariance <- matrix(fit$se^2,1,1,dimnames=list('ATT','ATT'))
  diagnostics$influence_function <- fit$att.inf.func
  diagnostics$effective_options <- fit$argu
  diagnostics$observations <- length(all_args$D)
  diagnostics$sampling_weights <- if(is.null(all_args$i.weights)) rep(1,length(all_args$D)) else all_args$i.weights/mean(all_args$i.weights)
} else if(method=='grf') {
  aggregate_args <- if(is.null(o$aggregation)) list() else o$aggregation
  ate <- invoke(grf::average_treatment_effect,c(list(forest=fit),aggregate_args))
  predictions <- predict(fit,estimate.variance=TRUE)
  estimates <- data.frame(term='target_ate',estimate=ate[1],se=ate[2],p_value=2*pnorm(-abs(ate[1]/ate[2])),ci_low=ate[1]-qnorm(.975)*ate[2],ci_high=ate[1]+qnorm(.975)*ate[2])
  covariance <- matrix(ate[2]^2,1,1,dimnames=list('target_ate','target_ate'))
  diagnostics$cate <- data.frame(id=ids,estimate=predictions$predictions,variance=predictions$variance.estimates)
} else if(method=='honest_did') {
  rows <- as.data.frame(fit)
} else if(method=='did_multiplegt_dyn') {
  diagnostics$sample <- fit$save_sample
  diagnostics$normalized_weights <- fit$normalized_weights
  diagnostics$treatment_paths <- fit$design
  diagnostics$effects <- fit$results$Effects
  diagnostics$placebos <- fit$results$Placebos
  if(!is.null(fit$save_sample) && all(c(s$id,'_did_sample') %in% names(fit$save_sample))) ids <- as.character(fit$save_sample[[s$id]][!is.na(fit$save_sample[['_did_sample']])])
} else if(method=='rdrobust_r') {
  estimates <- data.frame(term='treatment_effect',estimate=fit$coef['Robust',1],se=fit$se['Robust',1],p_value=fit$pv['Robust',1],ci_low=fit$ci['Robust',1],ci_high=fit$ci['Robust',2])
  covariance <- matrix(fit$se['Robust',1]^2,1,1,dimnames=list('treatment_effect','treatment_effect'))
  cutoff <- if(is.null(call_args$c)) 0 else call_args$c
  local <- d[[o$running]] >= cutoff-fit$bws['h',1] & d[[o$running]] <= cutoff+fit$bws['h',2]
  diagnostics <- list(bandwidths=fit$bws,effective_counts=fit$N_h,local_ids=I(ids[local]))
} else if(method=='club_sandwich') {
  rows <- as.data.frame(fit)
} else if(method=='wild_cluster_bootstrap') {
  rows <- data.frame(term=paste(fit$param,collapse='+'),p_value=fit$p_val)
  if(length(fit$conf_int)==2) { rows$ci_low <- fit$conf_int[1]; rows$ci_high <- fit$conf_int[2] }
}
if(!is.null(estimates)) rows <- estimates
# Retain the native package result for subsequent official post-estimation.
native <- serialize(list(fit=fit,data=d,ids=ids),NULL,version=3)
clean <- function(x) {
  if(is.null(x) || is.atomic(x)) return(x)
  if(is.data.frame(x)) return(x)
  if(is.list(x)) {
    x <- unclass(x)
    x[intersect(names(x),c('plot','call','call.param','args','data','df','model','terms','formula','xlevels'))] <- NULL
    return(lapply(x,clean))
  }
  NULL
}
cleaned <- clean(fit)
if(is.null(rows)) rows <- data.frame(result=names(cleaned),value=vapply(cleaned,function(x) paste(capture.output(str(x,give.attr=FALSE,max.level=1)),collapse=' '),character(1)))
obj <- list(engine=paste0(pkg,'::',fname),versions=setNames(list(as.character(packageVersion(pkg))),pkg),
  R=as.character(getRversion()),signature=formal_names,official_result=cleaned,
  runtime=list(library_paths=I(.libPaths()),working_directory=getwd(),profile_user=Sys.getenv('R_PROFILE_USER',unset=NA_character_)),
  estimates=estimates,covariance=covariance,diagnostics=clean(diagnostics),
  sample=list(included_ids=I(as.character(ids))),display=list(kind=kind,rows=rows),
  native_fit=list(format='R-serialize-v3',data=base64_enc(native)))
obj$confidence_level <- if(method=='rdrobust_r' && !is.null(call_args$level)) call_args$level/100 else if(method=='wild_cluster_bootstrap' && !is.null(call_args$sign_level)) 1-call_args$sign_level else if(method=='honest_did' && !is.null(call_args$alpha)) 1-call_args$alpha else .95
write_json(obj,args[5],auto_unbox=TRUE,digits=16,na='null',null='null',dataframe='rows')
'''
    with tempfile.TemporaryDirectory(prefix='causal-official-r-') as tmp:
        tmp = Path(tmp); (tmp/'spec.json').write_text(json.dumps(spec),encoding='utf-8')
        proc = subprocess.run(['Rscript','-',str(tmp/'spec.json'),str(path),package,function,str(tmp/'result.json')],
                              input=rcode,text=True,capture_output=True,env=os.environ.copy())
        if proc.returncode: raise ArithmeticError(f'{package} engine failed: ' + proc.stderr[-4000:])
        result = json.loads((tmp/'result.json').read_text())
    result.update(method=method, options=opt, adopted={k:spec[k] for k in ('population','period','unit','estimand','identification','assignment','inference')},
        provenance={'data_path':str(path),'data_sha256':_hash(path),'spec_path':str(spec_path.resolve()),'spec_sha256':_hash(spec_path)})
    result['versions']['R'] = result.pop('R')
    result['native_fit']['sha256'] = hashlib.sha256(base64.b64decode(result['native_fit']['data'])).hexdigest()
    result['sample']['id_column'] = spec['id']
    if not result['diagnostics']: result['diagnostics'] = {}
    result['sample']['observations'] = result['diagnostics'].get('observations')
    display_sample = {'id_column':spec['id'],'included_rows':len(result['sample']['included_ids']),
                      'observations':result['sample']['observations']}
    result['display']['metadata'] = {'unit':spec['unit'],'population':spec['population'],'estimand':spec['estimand'],
        'sample':display_sample,'engine':result['engine'],'inference':spec['inference'],
        'n':result['sample']['observations'],'n_clusters':result['diagnostics'].get('n_clusters'),
        'fixed_effects':opt.get('fixed_effects',[]),'controls':spec['regressors'],
        'period':spec['period'],'weights':{k:v for k,v in {**opt.get('args',{}),**opt.get('columns',{})}.items() if k in ('weights','i.weights','sample.weights','weight')},
        'estimator':result['engine'],'sample_policy':'official estimator preprocessing with saved observation IDs',
        'specification':{'outcome':spec['outcome'],'regressors':spec['regressors'],'fixed_effects':opt.get('fixed_effects',[]),'options':opt},
        'confidence_level':result['confidence_level']}
    result['diagnostics']['engine_messages'] = proc.stderr.strip()
    result['statistics'] = {}
    if result['estimates']:
        estimates = result.pop('estimates')
        result['coefficients'] = {r['term']:r['estimate'] for r in estimates}
        result['standard_errors'] = {r['term']:r['se'] for r in estimates}
        result['inference'] = {'confidence_level':result['confidence_level'],'p_values':{r['term']:r['p_value'] for r in estimates},
            'confidence_intervals':{r['term']:[r['ci_low'],r['ci_high']] for r in estimates}}
        if result['confidence_level'] == .95:
            result['inference']['confidence_intervals_95'] = result['inference']['confidence_intervals']
        terms = list(result['coefficients']); matrix = np.atleast_2d(result['covariance'])
        result['covariance'] = {a:{b:float(matrix[i,j]) for j,b in enumerate(terms)} for i,a in enumerate(terms)}
        result['statistics'] = {f'coefficient.{r["term"]}':{'value':r['estimate'],'unit':spec['unit']} for r in estimates}
    return result

def run(spec, spec_path):
    allowed = {'method','data','id','outcome','regressors','endogenous','instruments',
               'population','period','unit','estimand','identification','assignment',
               'inference','options'}
    if not isinstance(spec, dict) or set(spec) != allowed:
        raise ValueError('specification must contain exactly the documented fields')
    method = spec['method']
    methods = {'gls','iv_gmm','iv_ar','panel_fe','quantile','poisson','logit','rct','rdd_sharp','rdd_fuzzy','hdfe','causal_forest','spatial_lag','rdd_localrand','shift_share','policy_tree','network_spillover','tobit','dynamic_panel','synthetic_control','staggered_did','generalized_synth','multitreatment_did','distribution_effect'} | set(R_METHODS)
    if method not in methods:
        raise ValueError('unsupported method')
    for key in ('data','id','outcome','population','period','unit','estimand','identification','assignment'):
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise ValueError(f'{key} must be a nonempty string')
    for key in ('regressors','endogenous','instruments'):
        v = spec[key]
        if not isinstance(v, list) or any(not isinstance(x,str) or not x for x in v) or len(set(v)) != len(v):
            raise ValueError(f'{key} must be a list of distinct column names')
    if method == 'shift_share':
        if len(spec['endogenous']) != 1 or spec['instruments']: raise ValueError('shift_share requires one endogenous regressor and no input instruments')
    elif method in ('iv_gmm','iv_ar'):
        if not spec['endogenous'] or len(spec['instruments']) < len(spec['endogenous']):
            raise ValueError('IV GMM requires endogenous regressors and at least as many instruments')
    elif spec['endogenous'] or spec['instruments']:
        raise ValueError('endogenous and instruments are reserved for IV methods')
    if method == 'iv_ar' and len(spec['endogenous']) != 1:
        raise ValueError('iv_ar requires one endogenous regressor')
    if not isinstance(spec['options'],dict):
        raise ValueError('options must be an object')
    if method in R_METHODS:
        return _official_r(spec, spec_path)
    opt = spec['options']
    required = {'gls': {'variance'}, 'iv_gmm': set(), 'iv_ar': {'alpha'}, 'panel_fe': {'entity','time','entity_effects','time_effects'},
                'quantile': {'quantile'}, 'poisson': set(), 'logit': set(), 'rct': {'treatment','permutations','seed'}, 'rdd_sharp': {'running','cutoff','bandwidth'}, 'rdd_fuzzy': {'running','cutoff','bandwidth','treatment'}, 'hdfe': {'fixed_effects'}, 'causal_forest': {'treatment','seed','trees','min_leaf'}, 'spatial_lag': {'weights'}, 'rdd_localrand': {'running','cutoff','bandwidth','permutations','seed'}, 'shift_share': {'shares','shocks'}, 'policy_tree': {'treatment','propensity','partition','seed'}, 'network_spillover': {'weights','treatment'}, 'tobit': {'lower'}, 'dynamic_panel': {'entity','time'}, 'synthetic_control': {'entity','time','treated','training_end','pre_end'}, 'staggered_did': {'entity','time','cohort','control_group'}, 'generalized_synth': {'entity','time','treatment','factors','bootstraps','seed'}, 'multitreatment_did': {'entity','time','pre','post','treatments'}, 'distribution_effect': {'treatment','threshold'}}[method]
    optional = ({'panel','allow_unbalanced_panel','anticipation','weightsname','fix_weights',
                 'alp','bstrap','biters','clustervars','cband','est_method','base_period',
                 'faster_mode','seed','aggregation'} if method == 'staggered_did' else set())
    if not required <= set(opt) or set(opt) - required - optional:
        raise ValueError(f'{method} options must contain exactly {sorted(required)}')
    inf = spec['inference']
    if not isinstance(inf,dict) or inf.get('type') not in ('robust','cluster','homoskedastic','randomization','rdrobust','forest','spatial_ml','policy','likelihood','dynamic_gmm','synthetic_holdout','did','gsynth'):
        raise ValueError('unsupported inference type; see causal-models.md')
    if set(inf) != ({'type','cluster'} if inf['type']=='cluster' else {'type'}):
        raise ValueError('cluster inference requires exactly type and cluster')
    if (method == 'generalized_synth') != (inf['type'] == 'gsynth'):
        raise ValueError('generalized_synth alone requires gsynth inference')
    if (method == 'staggered_did') != (inf['type'] == 'did'):
        raise ValueError('staggered_did alone requires did inference')
    if (method == 'synthetic_control') != (inf['type'] == 'synthetic_holdout'):
        raise ValueError('synthetic_control alone requires synthetic_holdout inference')
    if (method == 'dynamic_panel') != (inf['type'] == 'dynamic_gmm'):
        raise ValueError('dynamic_panel alone requires dynamic_gmm inference')
    if (method == 'tobit') != (inf['type'] == 'likelihood'):
        raise ValueError('tobit alone requires likelihood inference')
    if (method == 'policy_tree') != (inf['type'] == 'policy'):
        raise ValueError('policy_tree alone requires policy inference')
    if (method == 'spatial_lag') != (inf['type'] == 'spatial_ml'):
        raise ValueError('spatial_lag alone requires spatial_ml inference')
    if (method == 'causal_forest') != (inf['type'] == 'forest'):
        raise ValueError('causal_forest alone requires forest inference')
    if (method in ('rdd_sharp','rdd_fuzzy')) != (inf['type'] == 'rdrobust'):
        raise ValueError('RDD alone requires rdrobust inference')
    if (method in ('rct','rdd_localrand')) != (inf['type'] == 'randomization'):
        raise ValueError('rct alone requires randomization inference')
    if (method == 'iv_ar') != (inf['type'] == 'homoskedastic'):
        raise ValueError('iv_ar alone requires homoskedastic inference')
    if method == 'quantile' and inf['type'] != 'robust':
        raise ValueError('quantile currently supports its robust kernel covariance only')
    if method == 'panel_fe' and inf['type'] != 'cluster':
        raise ValueError('panel_fe requires entity clustering')
    if method == 'panel_fe' and inf['cluster'] != opt['entity']:
        raise ValueError('panel_fe cluster must equal entity')
    if method == 'hdfe' and (not isinstance(opt['fixed_effects'],list) or not opt['fixed_effects'] or len(set(opt['fixed_effects']))!=len(opt['fixed_effects'])): raise ValueError('hdfe requires distinct fixed effect columns')
    if method == 'shift_share' and (not isinstance(opt['shares'],list) or not isinstance(opt['shocks'],list) or len(opt['shares'])<2 or len(opt['shares'])!=len(opt['shocks']) or len(set(opt['shares']))!=len(opt['shares'])): raise ValueError('shift_share needs matching distinct share columns and shock values')
    if method == 'shift_share' and set(opt['shares']) & {spec['id'],spec['outcome'],*spec['endogenous']}: raise ValueError('shares must be distinct from ID, outcome and endogenous treatment')
    if method == 'multitreatment_did' and (not isinstance(opt['treatments'],list) or len(opt['treatments'])<2 or len(set(opt['treatments']))!=len(opt['treatments'])): raise ValueError('multiple-treatment DID needs at least two distinct treatment columns')
    extra = ([opt['entity'],opt['time'],*opt['treatments']] if method == 'multitreatment_did' else
             [opt['entity'],opt['time'],opt['treatment']] if method == 'generalized_synth' else
             [opt['entity'],opt['time'],opt['cohort']] if method == 'staggered_did' else
             [opt['entity'],opt['time']] if method in ('dynamic_panel','synthetic_control') else
             [opt['treatment']] if method == 'network_spillover' else
             [opt['treatment'],opt['propensity'],opt['partition']] if method == 'policy_tree' else
             opt['shares'] if method == 'shift_share' else
             [opt['treatment']] if method == 'causal_forest' else
             opt['fixed_effects'] if method == 'hdfe' else
             [opt['treatment']] if method == 'rdd_fuzzy' else
             [opt['variance']] if method == 'gls' else
             [opt['entity'],opt['time']] if method == 'panel_fe' else [])
    columns = [spec['id'],spec['outcome'],*spec['regressors'],*spec['endogenous'],*spec['instruments'],*extra]
    if method == 'staggered_did':
        if not isinstance(opt.get('clustervars', []), list):
            raise ValueError('DID clustervars must be a list of column names')
        columns.extend(opt.get('clustervars', []))
        if 'weightsname' in opt: columns.append(opt['weightsname'])
    if inf['type']=='cluster': columns += [inf['cluster']]
    if any(not isinstance(x,str) or not x for x in columns): raise ValueError('column names must be nonempty strings')
    roles = [spec['id'],spec['outcome'],*spec['regressors'],*spec['endogenous'],*spec['instruments']]
    if len(set(roles)) != len(roles) or 'const' in roles: raise ValueError('model column roles must be distinct; const is reserved')
    p = Path(spec['data']); p = (p if p.is_absolute() else spec_path.parent / p).resolve()
    df = pd.read_csv(p, dtype={spec['id']:'string'})
    input_rows = len(df)
    if not set(columns) <= set(df.columns): raise ValueError(f'missing columns: {sorted(set(columns)-set(df.columns))}')
    if df[spec['id']].isna().any() or df[spec['id']].str.strip().eq('').any() or df[spec['id']].duplicated().any():
        raise ValueError('IDs must be nonmissing and unique')
    numeric = [spec['outcome'],*spec['regressors'],*spec['endogenous'],*spec['instruments']]
    if method == 'network_spillover': numeric.append(opt['treatment'])
    if method == 'multitreatment_did': numeric.extend([opt['time'],*opt['treatments']])
    if method == 'generalized_synth': numeric.extend([opt['time'],opt['treatment']])
    if method == 'staggered_did': numeric.extend([opt['time'],opt['cohort']])
    if method == 'staggered_did' and 'weightsname' in opt: numeric.append(opt['weightsname'])
    if method == 'policy_tree': numeric.extend([opt['treatment'],opt['propensity']])
    if method == 'shift_share': numeric.extend(opt['shares'])
    if method == 'gls': numeric.append(opt['variance'])
    if method in ('rdd_fuzzy','causal_forest'): numeric.append(opt['treatment'])
    for c in numeric: df[c] = pd.to_numeric(df[c], errors='raise')
    selected = np.isfinite(df[numeric].to_numpy(dtype=float)).all(axis=1)
    for c in set(columns)-set(numeric): selected &= df[c].notna() & df[c].astype('string').str.strip().ne('').fillna(False)
    excluded = df.loc[~selected,spec['id']].astype(str).tolist()
    d = df.loc[selected].copy()
    outside=[]; training=[]; initial_lags=[]
    if method == 'rdd_localrand':
        running=opt['running']; cutoff=opt['cutoff']; bandwidth=opt['bandwidth']
        if spec['regressors'] != [running] or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) for v in (cutoff,bandwidth)) or bandwidth<=0: raise ValueError('local randomization requires a running variable, finite cutoff and positive fixed bandwidth')
        local=(d[running]>=cutoff-bandwidth)&(d[running]<=cutoff+bandwidth)
        outside=d.loc[~local,spec['id']].astype(str).tolist(); d=d.loc[local].copy()
    if len(d)<4: raise ValueError('at least four complete observations required')
    X = sm.add_constant(d[spec['regressors']],has_constant='add')
    if np.linalg.matrix_rank(X.to_numpy()) != X.shape[1] or len(d)<=X.shape[1]: raise ValueError('design must have full rank and residual degrees of freedom')
    groups = None
    if inf['type']=='cluster':
        groups = d[inf['cluster']]
        if groups.nunique()<2: raise ValueError('at least two clusters required')
    versions = {'python':sys.version.split()[0], 'numpy':np.__version__, 'pandas':pd.__version__, 'scipy':scipy.__version__, 'statsmodels':statsmodels.__version__}
    diagnostics = {}; fit_n=None; did_values=None; confidence_level=0.95
    if method == 'distribution_effect':
        treatment=opt['treatment']; threshold=opt['threshold']
        if spec['regressors']!=[treatment] or set(d[treatment].unique())!={0,1} or isinstance(threshold,bool) or not isinstance(threshold,(int,float)) or not np.isfinite(threshold): raise ValueError('distribution effect requires a binary treatment regressor and finite threshold')
        indicator=(d[spec['outcome']]<=threshold).astype(int); fit=sm.OLS(indicator,X).fit(**({'cov_type':'HC1'} if groups is None else {'cov_type':'cluster','cov_kwds':{'groups':groups,'use_correction':True},'use_t':True}))
        coef=fit.params; cov=fit.cov_params(); se=fit.bse; pv=fit.pvalues; ci=fit.conf_int(); reference='normal' if groups is None else 'Student t'; engine='statsmodels.OLS on threshold indicator'
        diagnostics={'threshold':float(threshold),'control_cdf':float(indicator[d[treatment]==0].mean()),'treated_cdf':float(indicator[d[treatment]==1].mean())}
    elif method == 'multitreatment_did':
        entity=opt['entity']; time=opt['time']; pre=opt['pre']; post=opt['post']; treatments=opt['treatments']
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) for v in (pre,post)) or pre>=post: raise ValueError('DID pre and post must be ordered finite numbers')
        if set(treatments) & {spec['id'],spec['outcome'],entity,time,*spec['regressors']} or entity in (spec['id'],spec['outcome'],time) or time in spec['regressors']: raise ValueError('DID columns must have distinct roles')
        if excluded or d.duplicated([entity,time]).any() or set(d[time].unique())!={pre,post} or not (d.groupby(entity)[time].nunique()==2).all(): raise ValueError('DID requires a complete unique balanced two-period panel')
        before=d.loc[d[time]==pre].set_index(entity).sort_index(); after=d.loc[d[time]==post].set_index(entity).sort_index()
        if not (before[treatments]==0).all().all(): raise ValueError('all treatment doses must be zero before treatment')
        if (after[treatments]<0).any().any() or not (after[treatments].sum(axis=1)==0).any(): raise ValueError('post doses must be nonnegative and include untreated units')
        XX=sm.add_constant(pd.concat([before[spec['regressors']],after[treatments]],axis=1),has_constant='add'); change=after[spec['outcome']]-before[spec['outcome']]
        if np.linalg.matrix_rank(XX.to_numpy())!=XX.shape[1]: raise ValueError('multiple-treatment DID design must have full rank')
        pair_groups=before[inf['cluster']] if groups is not None else None
        if pair_groups is not None and not (before[inf['cluster']]==after[inf['cluster']]).all(): raise ValueError('cluster assignment must remain fixed across periods')
        fit=sm.OLS(change,XX).fit(**({'cov_type':'HC1'} if pair_groups is None else {'cov_type':'cluster','cov_kwds':{'groups':pair_groups,'use_correction':True},'use_t':True}))
        coef=fit.params; cov=fit.cov_params(); se=fit.bse; pv=fit.pvalues; ci=fit.conf_int(); reference='normal' if pair_groups is None else 'Student t'; engine='statsmodels.OLS on within-unit changes'
        fit_n=len(before)
        diagnostics={'units':len(before),'treatments':treatments,'treatment_before':'zero for every unit','untreated_units':int((after[treatments].sum(axis=1)==0).sum()),'outcome_transformation':'post minus pre','controls':'pre-period values'}
    elif method == 'generalized_synth':
        import re, subprocess, tempfile, os
        from scipy.stats import norm
        entity=opt['entity']; time=opt['time']; treatment=opt['treatment']; rank=opt['factors']; boots=opt['bootstraps']; seed=opt['seed']; variables=[spec['outcome'],*spec['regressors'],entity,time,treatment]
        if any(not isinstance(k,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',k) for k in variables) or len(set(variables))!=len(variables): raise ValueError('generalized synthetic control requires distinct simple names')
        if any(isinstance(v,bool) or not isinstance(v,int) for v in (rank,boots,seed)) or rank<0 or boots<40 or seed<0: raise ValueError('factor count and seed must be nonnegative integers; bootstrap needs at least 40 repetitions')
        if excluded or d.duplicated([entity,time]).any() or set(d[treatment].unique())!={0,1}: raise ValueError('generalized synthetic control requires complete, unique panel and binary treatment')
        grid=np.sort(d[time].unique()); n_entities=d[entity].nunique()
        if len(grid)<8 or not np.equal(grid,np.floor(grid)).all() or not np.all(np.diff(grid)==1) or len(d)!=n_entities*len(grid) or not (d.groupby(entity)[time].nunique()==len(grid)).all(): raise ValueError('generalized synthetic control needs a balanced consecutive integer panel')
        paths=d.pivot(index=time,columns=entity,values=treatment).sort_index().to_numpy(); treated_paths=paths[:,paths.sum(axis=0)>0]; starts=[int(np.flatnonzero(t)[0]) for t in treated_paths.T]
        if not starts or len(starts)>=n_entities or len(set(starts))!=1 or starts[0]<5 or any(not np.array_equal(t,np.r_[np.zeros(starts[0]),np.ones(len(grid)-starts[0])]) for t in treated_paths.T): raise ValueError('generalized synthetic control requires one common absorbing treatment start and five pretreatment periods')
        if not os.environ.get('R_LIBS_USER'): raise ValueError('set R_LIBS_USER to the installed gsynth library')
        rcode="""
args<-commandArgs(trailingOnly=TRUE); suppressPackageStartupMessages(library(gsynth)); suppressPackageStartupMessages(library(jsonlite))
d<-read.csv(args[1],check.names=FALSE); outcome<-args[2]; unit<-args[3]; tm<-args[4]; treat<-args[5]; covars<-args[6]; rank<-as.integer(args[7]); boots<-as.integer(args[8]); seed<-as.integer(args[9]); d[[unit]]<-as.integer(as.factor(d[[unit]])); f<-as.formula(paste(outcome,'~',treat,if(nchar(covars)) paste('+',gsub(',', '+', covars)) else ''))
invisible(capture.output(z<-gsynth(f,data=d,index=c(unit,tm),force='two-way',r=rank,CV=FALSE,se=TRUE,nboots=boots,inference='parametric',parallel=FALSE,seed=seed)))
bb<-rbind(z$att.avg.boot,z$att.boot); vv<-cov(t(bb)); obj<-list(r_version=as.character(getRversion()),gsynth_version=as.character(packageVersion('gsynth')),events=as.numeric(rownames(z$est.att)),coef=c(z$att.avg,z$est.att[,'ATT']),engine_se=c(z$est.avg[1,'S.E.'],z$est.att[,'S.E.']),cov=unname(vv),rmse=z$rmse,iterations=z$niter,rank=z$r.cv,treated=z$Ntr,controls=z$Nco)
cat(toJSON(obj,auto_unbox=TRUE,digits=16,na='null',null='null'))
"""
        with tempfile.TemporaryDirectory(prefix='causal-gsynth-') as tmp:
            inp=Path(tmp)/'data.csv'; d.to_csv(inp,index=False); proc=subprocess.run(['Rscript','-',str(inp),spec['outcome'],entity,time,treatment,','.join(spec['regressors']),str(rank),str(boots),str(seed)],input=rcode,text=True,capture_output=True,env=os.environ.copy())
        if proc.returncode: raise ArithmeticError('gsynth engine failed: '+proc.stderr[-2000:])
        values=json.loads(proc.stdout); versions['R']=values['r_version']; versions['gsynth']=values['gsynth_version']; events=np.atleast_1d(values['events']); names=['overall']+[('event_m'+str(abs(int(x))) if x<0 else 'event_p'+str(int(x))) for x in events]; vals=np.atleast_1d(values['coef']); covariance=np.atleast_2d(values['cov']);
        if not np.isfinite(vals.astype(float)).all() or not np.isfinite(covariance.astype(float)).all(): raise ArithmeticError('gsynth returned nonfinite estimates')
        coef=pd.Series(vals,index=names,dtype=float); cov=pd.DataFrame(covariance,index=names,columns=names,dtype=float); se=pd.Series(np.sqrt(np.diag(cov)),index=names)
        if not np.allclose(se.to_numpy(),np.atleast_1d(values['engine_se']),rtol=1e-7,atol=1e-9): raise ArithmeticError('bootstrap covariance does not match gsynth standard errors')
        pv=pd.Series(2*norm.sf(np.abs(coef/se)),index=names); ci=pd.DataFrame({0:coef-norm.ppf(.975)*se,1:coef+norm.ppf(.975)*se}); reference='normal'; engine='R gsynth::gsynth'
        diagnostics={'factors':rank,'bootstraps':boots,'bootstrap':'parametric','seed':seed,'force':'two-way','cross_validation':False,'rmse':values['rmse'],'iterations':values['iterations'],'treated_units':int(values['treated']),'control_units':int(values['controls'])}
    elif method == 'staggered_did':
        from scipy.stats import norm
        did_values = _staggered_did(spec, d)
        values = did_values
        versions.update(R=values['r_version'], did=values['did_version'], DRDID=values['drdid_version'])
        effective = values['att_gt_options']; aggregation = values['aggregate_options']
        events = np.atleast_1d(values['event_times']) if values['event_times'] is not None else np.array([])
        prefix = {'dynamic':'event', 'group':'cohort', 'calendar':'time', 'simple':'overall'}[aggregation['type']]
        names = ['overall'] + [prefix + ('_m' + str(abs(int(x))) if x < 0 else '_p' + str(int(x))) for x in events]
        vals = np.atleast_1d(values['coef']).astype(float)
        errors = np.atleast_1d(values['engine_se']).astype(float)
        covariance = np.atleast_2d(values['cov']).astype(float)
        # A universal reference period is normalized by did and has no test.
        baseline = opt.get('base_period', 'varying') == 'universal'
        normalized = np.r_[False, (events == -opt.get('anticipation', 0)-1)] if aggregation['type'] == 'dynamic' and baseline else np.zeros(len(vals),dtype=bool)
        keep = ~normalized
        names = list(np.asarray(names)[keep]); vals = vals[keep]; errors = errors[keep]
        covariance = covariance[np.ix_(keep,keep)]
        coef = pd.Series(vals,index=names); se = pd.Series(errors,index=names)
        cov = pd.DataFrame(covariance,index=names,columns=names)
        critical = np.atleast_1d(values['critical_values']).astype(float)[keep]
        if not aggregation['bstrap'] and not np.allclose(se.to_numpy(),np.sqrt(np.diag(covariance)),rtol=1e-7,atol=1e-9):
            raise ArithmeticError('DID analytical covariance does not match official standard errors')
        pv = pd.Series(2*norm.sf(np.abs(coef/se)),index=names)
        ci = pd.DataFrame({0:coef-critical*se,1:coef+critical*se})
        confidence_level = 1-aggregation['alp']
        reference = 'normal pointwise tests with official multiplier-bootstrap standard errors' if aggregation['bstrap'] else 'normal'
        engine = 'R did::att_gt + did::aggte'; fit_n = int(values['n'])
        retained = set(values['fitted_ids'])
        removed = d.loc[~d[spec['id']].isin(retained),spec['id']].astype(str).tolist()
        outside = removed if not (d[opt['cohort']] == 0).any() else []
        d = d.loc[d[spec['id']].isin(retained)].copy()
        diagnostics = {'control_group':opt['control_group'],'score':effective['est_method'],
            'aggregation':aggregation['type'],'base_period':effective['base_period'],
            'group_time':{'group':values['groups'],'time':values['times'],'att':values['att'],
                          'standard_errors':values['group_se'],'covariance':values['group_cov'],
                          'cells':values['cells']},
            'units':fit_n,'bootstrap':effective['bstrap'],'anticipation':effective['anticipation'],
            'effective_options':{'att_gt':effective,'aggte':aggregation},
            'official_interfaces':values['signatures'],'aggregation_components':values['components'],
            'pretreatment_test':values['pretreatment_test'], 'excluded_engine_ids':removed,
            'engine_messages':values['engine_messages'],'runtime':values['runtime'],'seed':opt.get('seed')}
    elif method == 'synthetic_control':
        from importlib.metadata import version
        from pysyncon import Synth
        versions['pysyncon']=version('pysyncon')
        entity=opt['entity']; time=opt['time']; treated=str(opt['treated']); end=opt['training_end']; pre=opt['pre_end']
        if spec['regressors']!=[time] or entity in (spec['id'],spec['outcome'],time) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) for v in (end,pre)) or end>=pre: raise ValueError('synthetic control requires time regressor, distinct entity and ordered finite training_end and pre_end')
        if excluded or d.duplicated([entity,time]).any(): raise ValueError('synthetic control requires a complete unique unit-time panel')
        matrix=d.assign(**{entity:d[entity].astype(str)}).pivot(index=time,columns=entity,values=spec['outcome']).sort_index()
        if treated not in matrix.columns or matrix.shape[1]<3 or matrix.isna().any().any(): raise ValueError('synthetic control needs one treated unit and at least two balanced donors')
        tr=matrix.index<=end; validation=(matrix.index>end)&(matrix.index<=pre); post=matrix.index>pre
        if min(int(tr.sum()),int(validation.sum()),int(post.sum()))<4: raise ValueError('each synthetic control period partition needs at least four periods')
        donor_names=[x for x in matrix.columns if x!=treated]; controls=matrix[donor_names]; target=matrix[treated]
        model=Synth(); model.fit(X0=controls.loc[tr],X1=target.loc[tr],Z0=controls.loc[tr],Z1=target.loc[tr],custom_V=np.ones(int(tr.sum())))
        weights=np.asarray(model.W,dtype=float); gaps=target.to_numpy()-controls.to_numpy()@weights
        if not np.isfinite(weights).all() or weights.min() < -1e-7 or abs(weights.sum()-1)>1e-6: raise ArithmeticError('synthetic control optimizer produced invalid donor weights')
        held=validation|post; hold_gap=gaps[held]; post_indicator=np.asarray(post[held],dtype=float); XX=pd.DataFrame({'const':1.0,'post':post_indicator})
        fit=sm.OLS(hold_gap,XX).fit(cov_type='HC1'); fit_n=len(hold_gap); coef=fit.params; cov=fit.cov_params(); se=fit.bse; pv=fit.pvalues; ci=fit.conf_int(); reference='normal'; engine='pysyncon.Synth + statsmodels.OLS'
        training=d.loc[d[time]<=end,spec['id']].astype(str).tolist(); d=d.loc[d[time]>end].copy()
        diagnostics={'donor_weights':dict(zip(donor_names,[float(x) for x in weights])),'training_rmspe':float(np.sqrt(np.mean(gaps[tr]**2))),'validation_rmspe':float(np.sqrt(np.mean(gaps[validation]**2))),'period_gap':[{'time':float(t),'gap':float(g)} for t,g in zip(matrix.index,gaps)],'inference':'HC1 across held-out time gaps, conditional on training weights','training_periods':int(tr.sum()),'validation_periods':int(validation.sum()),'post_periods':int(post.sum())}
    elif method == 'dynamic_panel':
        import re, contextlib, io
        from importlib.metadata import version
        from pydynpd import regression
        from scipy.stats import norm
        versions['pydynpd']=version('pydynpd')
        entity=opt['entity']; time=opt['time']; model_names=[spec['outcome'],*spec['regressors'],entity,time]
        if not spec['regressors'] or any(not isinstance(k,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',k) for k in model_names) or len(set(model_names))!=len(model_names): raise ValueError('dynamic panel requires distinct simple variable names and exogenous regressors')
        if excluded or d.duplicated([entity,time]).any(): raise ValueError('dynamic panel requires complete data and unique entity-time pairs')
        times=pd.to_numeric(d[time],errors='raise').to_numpy(dtype=float)
        if not np.isfinite(times).all() or not np.equal(times,np.floor(times)).all(): raise ValueError('dynamic panel times must be finite integers')
        d[time]=times.astype(int); grid=np.sort(d[time].unique())
        if len(grid)<6 or not np.all(np.diff(grid)==1) or len(d)!=d[entity].nunique()*len(grid) or not (d.groupby(entity)[time].nunique()==len(grid)).all(): raise ValueError('dynamic panel requires a balanced consecutive panel with at least six periods')
        command=spec['outcome']+' L1.'+spec['outcome']+' '+' '.join(spec['regressors'])+' | gmm('+spec['outcome']+', 2:3) iv('+' '.join(spec['regressors'])+') | nolevel'
        with contextlib.redirect_stdout(io.StringIO()): result=regression.abond(command,d,[entity,time])
        if len(result.models)!=1: raise ArithmeticError('dynamic panel engine did not return exactly one model')
        fit=result.models[0]; table=fit.regression_table.set_index('variable'); names=table.index.tolist(); coef=table['coefficient']; se=table['std_err']; pv=table['p_value']; cov=pd.DataFrame(fit.step_results[-1].vcov,index=names,columns=names); ci=pd.DataFrame({0:coef-norm.ppf(.975)*se,1:coef+norm.ppf(.975)*se}); reference='normal'; engine='pydynpd.regression.abond'
        initial_lags=d.loc[d[time].isin(grid[:2]),spec['id']].astype(str).tolist(); d=d.loc[~d[time].isin(grid[:2])].copy()
        if int(fit.num_obs)!=len(d): raise ArithmeticError('dynamic panel engine sample differs from documented lag exclusions')
        diagnostics={'groups':int(fit.N),'instruments':int(fit.z_information.num_instr),'hansen':{'statistic':float(fit.hansen.test_value),'df':int(fit.hansen.df),'p_value':float(fit.hansen.p_value)},'serial_correlation':[{'lag':int(x.lag),'statistic':float(x.AR),'p_value':float(x.P_value)} for x in fit.AR_list],'command':command,'steps':2,'covariance':'Windmeijer corrected'}
    elif method == 'tobit':
        from statsmodels.base.model import GenericLikelihoodModel
        from scipy.special import log_ndtr
        from scipy.stats import norm
        lower=opt['lower']; y=d[spec['outcome']].to_numpy(); xx=X.to_numpy()
        if isinstance(lower,bool) or not isinstance(lower,(int,float)) or not np.isfinite(lower) or np.any(y<lower): raise ValueError('Tobit outcome must be at or above the finite censoring threshold')
        if not np.any(y==lower) or not np.any(y>lower): raise ValueError('Tobit needs censored and uncensored observations')
        class LeftCensoredNormal(GenericLikelihoodModel):
            def loglikeobs(self,params):
                sigma=np.exp(params[-1]); mu=self.exog@params[:-1]; z=(self.endog-mu)/sigma
                return np.where(self.endog==lower,log_ndtr((lower-mu)/sigma),norm.logpdf(z)-params[-1])
        start=np.r_[sm.OLS(y,xx).fit().params, np.log(np.std(y))]
        model=LeftCensoredNormal(y,xx,extra_params_names=['log_sigma']); fit=model.fit(start_params=start,method='bfgs',maxiter=2000,disp=False)
        if not fit.mle_retvals['converged']: raise ArithmeticError('Tobit optimizer did not converge')
        names=[*X.columns,'log_sigma']; coef=pd.Series(fit.params,index=names); se=pd.Series(fit.bse,index=names); cov=pd.DataFrame(fit.cov_params(),index=names,columns=names); pv=pd.Series(fit.pvalues,index=names); ci=pd.DataFrame(fit.conf_int(),index=names); reference='normal'; engine='statsmodels.GenericLikelihoodModel + scipy.special.log_ndtr'
        diagnostics={'censored_observations':int(np.sum(y==lower)),'log_likelihood':float(fit.llf),'sigma':float(np.exp(fit.params[-1])),'converged':True}
    elif method == 'network_spillover':
        from importlib.metadata import version
        versions['libpysal']=version('libpysal')
        if excluded: raise ValueError('network exposure requires a complete input sample')
        treatment=opt['treatment']
        if treatment in [spec['id'],spec['outcome'],*spec['regressors']] or set(d[treatment].unique())!={0,1}: raise ValueError('network treatment must be a distinct binary column')
        w,wp=_network(spec_path,opt['weights'],d[spec['id']].astype(str).tolist()); exposure=w.sparse @ d[treatment].to_numpy()
        XX=X.copy(); XX['treatment']=d[treatment].to_numpy(); XX['neighbor_exposure']=exposure
        if np.linalg.matrix_rank(XX)!=XX.shape[1]: raise ValueError('network exposure design must have full rank')
        fit=sm.OLS(d[spec['outcome']],XX).fit(**({'cov_type':'HC1'} if groups is None else {'cov_type':'cluster','cov_kwds':{'groups':groups,'use_correction':True},'use_t':True}))
        coef=fit.params; cov=fit.cov_params(); se=fit.bse; pv=fit.pvalues; ci=fit.conf_int(); reference='normal' if groups is None else 'Student t'; engine='libpysal.weights.W + statsmodels.OLS'
        diagnostics={'exposures':[{'id':str(i),'weighted_neighbor_treatment':float(x)} for i,x in zip(d[spec['id']],exposure)],'weights_path':str(wp),'weights_sha256':_hash(wp),'normalization':'row-standardized'}
    elif method == 'policy_tree':
        import econml
        from econml.policy import DRPolicyTree
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import LogisticRegression
        from importlib.metadata import version
        versions['econml']=econml.__version__; versions['scikit-learn']=version('scikit-learn')
        treatment=opt['treatment']; prop=opt['propensity']; partition=opt['partition']; seed=opt['seed']
        if isinstance(seed,bool) or not isinstance(seed,int) or seed<0 or not spec['regressors']: raise ValueError('policy requires nonnegative seed and effect covariates')
        if len({treatment,prop,partition,spec['id'],spec['outcome'],*spec['regressors']})!=5+len(spec['regressors']): raise ValueError('policy model roles must be distinct')
        if set(d[partition].unique()) != {'train','evaluation'} or set(d[treatment].unique()) != {0,1} or not ((d[prop]>0)&(d[prop]<1)).all(): raise ValueError('policy needs train/evaluation partitions, binary treatment and propensities in (0,1)')
        train=d[d[partition]=='train']; evaluation=d[d[partition]=='evaluation']
        if len(evaluation)<10 or len(train)<50 or train[treatment].value_counts().min()<20: raise ValueError('policy partitions need 50 training units, 20 per arm and 10 evaluation units')
        policy=DRPolicyTree(model_regression=RandomForestRegressor(n_estimators=50,min_samples_leaf=10,n_jobs=1,random_state=seed),model_propensity=LogisticRegression(max_iter=1000),max_depth=2,min_samples_leaf=20,cv=2,honest=True,random_state=seed)
        policy.fit(train[spec['outcome']].to_numpy(),train[treatment].to_numpy(),X=train[spec['regressors']].to_numpy())
        chosen=np.asarray(policy.predict(evaluation[spec['regressors']].to_numpy()),dtype=int).reshape(-1)
        if not set(np.unique(chosen))<= {0,1}: raise ArithmeticError('policy predicted invalid actions')
        t=evaluation[treatment].to_numpy(); y=evaluation[spec['outcome']].to_numpy(); prob=evaluation[prop].to_numpy(); score=y*((t==chosen)/np.where(t==1,prob,1-prob)-(t==0)/(1-prob))
        fit=sm.OLS(score,np.ones((len(score),1))).fit(cov_type='HC1'); name='policy_value_gain'; coef=pd.Series([float(fit.params[0])],index=[name]); se=pd.Series([float(fit.bse[0])],index=[name]); cov=pd.DataFrame([[float(fit.cov_params()[0,0])]],index=[name],columns=[name]); pv=pd.Series([float(fit.pvalues[0])],index=[name]); ci=pd.DataFrame([fit.conf_int()[0]],index=[name]); reference='normal'; engine='econml.policy.DRPolicyTree + statsmodels.OLS'
        training=train[spec['id']].astype(str).tolist(); d=evaluation.copy()
        diagnostics={'baseline':'assign treatment 0 to everyone','training_ids':training,'evaluation_policy':[{'id':str(i),'action':int(a)} for i,a in zip(evaluation[spec['id']],chosen)],'evaluation_score':'inverse probability weighted policy gain using known propensity','propensity_range':[float(prob.min()),float(prob.max())],'trained_treatment_fraction':float(chosen.mean())}
    elif method == 'shift_share':
        import linearmodels
        from linearmodels.iv import IV2SLS
        versions['linearmodels']=linearmodels.__version__
        shocks=opt['shocks']; shares=d[opt['shares']].to_numpy(dtype=float)
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) for v in shocks) or len(set(shocks))<2 or (shares<0).any() or not np.allclose(shares.sum(axis=1),1,atol=1e-8): raise ValueError('shares must be nonnegative, sum to one and pair with distinct finite shocks')
        instrument=pd.DataFrame({'shift_share':shares@np.asarray(shocks)},index=d.index)
        fit=IV2SLS(d[spec['outcome']],X,d[spec['endogenous']],instrument).fit(cov_type='clustered' if groups is not None else 'robust',debiased=True,**({'clusters':groups} if groups is not None else {}))
        coef=fit.params; cov=fit.cov; se=fit.std_errors; pv=fit.pvalues; ci=fit.conf_int(); reference='Student t'; engine='linearmodels.iv.IV2SLS'
        fs=fit.first_stage.diagnostics.iloc[0]; diagnostics={'instrument':'sum_k share_ik * shock_k','shock_count':len(shocks),'instrument_range':[float(instrument.min().iloc[0]),float(instrument.max().iloc[0])],'first_stage_partial_r_squared':float(fs['partial.rsquared']),'first_stage_statistic':float(fs['f.stat']),'first_stage_reference':str(fs['f.dist'])}
    elif method == 'spatial_lag':
        import spreg
        from libpysal.weights import W
        from importlib.metadata import version
        from scipy.stats import norm
        versions['spreg']=version('spreg'); versions['libpysal']=version('libpysal')
        if excluded: raise ValueError('spatial weights require a complete input sample')
        w,wp=_network(spec_path,opt['weights'],d[spec['id']].astype(str).tolist())
        fit=spreg.ML_Lag(d[spec['outcome']].to_numpy()[:,None],d[spec['regressors']].to_numpy(),w,method='full',vm=True,name_x=spec['regressors'],spat_impacts='simple')
        names=['const',*spec['regressors'],'spatial_lag']; coef=pd.Series(fit.betas.ravel(),index=names); se=pd.Series(fit.std_err,index=names); cov=pd.DataFrame(fit.vm,index=names,columns=names); pv=pd.Series([p for _,p in fit.z_stat],index=names); ci=pd.DataFrame({0:coef-1.959963984540054*se,1:coef+1.959963984540054*se}); reference='normal'; engine='spreg.ML_Lag'
        diagnostics={'rho':float(fit.rho),'log_likelihood':float(fit.logll),'weights_path':str(wp),'weights_sha256':_hash(wp),'normalization':'row-standardized','simple_multipliers':[float(x) for x in fit.sp_multipliers['simple']]}
    elif method == 'causal_forest':
        import econml
        from econml.dml import CausalForestDML
        from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
        from sklearn.model_selection import StratifiedKFold
        from importlib.metadata import version
        versions['econml']=econml.__version__; versions['scikit-learn']=version('scikit-learn')
        seed=opt['seed']; trees=opt['trees']; leaf=opt['min_leaf']; treatment=opt['treatment']
        if not spec['regressors'] or treatment in spec['regressors'] or treatment==spec['outcome'] or treatment==spec['id']: raise ValueError('forest requires distinct treatment and covariates')
        if any(isinstance(v,bool) or not isinstance(v,int) for v in (seed,trees,leaf)) or seed<0 or trees<40 or trees%4 or leaf<2: raise ValueError('forest seed, trees and leaf require nonnegative seed, trees >=40 divisible by 4, and leaf >=2')
        if set(d[treatment].unique()) != {0,1} or d[treatment].value_counts().min()<10: raise ValueError('forest requires at least 10 units in each binary treatment arm')
        splitter=StratifiedKFold(n_splits=2,shuffle=True,random_state=seed)
        model=CausalForestDML(discrete_treatment=True,model_y=RandomForestRegressor(n_estimators=50,min_samples_leaf=leaf,n_jobs=1,random_state=seed),model_t=RandomForestClassifier(n_estimators=50,min_samples_leaf=leaf,n_jobs=1,random_state=seed),n_estimators=trees,min_samples_leaf=leaf,n_jobs=1,random_state=seed,cv=splitter,honest=True,inference=True)
        features=d[spec['regressors']].to_numpy(); model.fit(d[spec['outcome']].to_numpy(),d[treatment].to_numpy(),X=features)
        aggregate=model.ate_inference(X=features); individual=model.effect_inference(X=features); lo,hi=aggregate.conf_int_mean(); ilo,ihi=individual.conf_int()
        name='sample_ate'; coef=pd.Series([float(aggregate.mean_point)],index=[name]); se=pd.Series([float(aggregate.stderr_mean)],index=[name]); cov=pd.DataFrame([[float(se.iloc[0]**2)]],index=[name],columns=[name]); pv=pd.Series([float(aggregate.pvalue())],index=[name]); ci=pd.DataFrame([[float(lo),float(hi)]],index=[name]); reference='normal'; engine='econml.dml.CausalForestDML'
        diagnostics={'cate':[{'id':str(i),'effect':float(v),'standard_error':float(e),'interval_95':[float(l),float(h)]} for i,v,e,l,h in zip(d[spec['id']],individual.point_estimate,individual.stderr,ilo,ihi)],'sample_ate_standard_error':'upper bound from econml population summary','folds':[{'train_ids':d[spec['id']].iloc[train].astype(str).tolist(),'test_ids':d[spec['id']].iloc[test].astype(str).tolist()} for train,test in splitter.split(features,d[treatment].to_numpy())],'honest':True,'nuisance_trees':50}
    elif method == 'hdfe':
        import re
        import pyfixest
        from importlib.metadata import version
        versions['pyfixest']=version('pyfixest')
        names=[spec['outcome'],*spec['regressors'],*opt['fixed_effects']] + ([inf['cluster']] if groups is not None else [])
        if not spec['regressors'] or any(not isinstance(k,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',k) for k in names): raise ValueError('hdfe requires simple column names and at least one regressor')
        formula=spec['outcome']+' ~ '+' + '.join(spec['regressors'])+' | '+' + '.join(opt['fixed_effects'])
        fit=pyfixest.feols(formula,d,vcov={'CRV1':inf['cluster']} if groups is not None else 'hetero',fixef_rm='none')
        coef=fit.coef(); se=fit.se(); pv=fit.pvalue(); ci=fit.confint(); cov=pd.DataFrame(fit._vcov,index=coef.index,columns=coef.index); reference='Student t'; engine='pyfixest.feols'
        if int(fit._N)!=len(d) or list(coef.index)!=spec['regressors']: raise ValueError('HDFE dropped observations or collinear regressors')
        diagnostics={'fixed_effects':opt['fixed_effects'],'levels':{k:int(d[k].nunique()) for k in opt['fixed_effects']},'singleton_policy':'retain','covariance': 'CRV1' if groups is not None else 'hetero'}
    elif method in ('rdd_sharp','rdd_fuzzy'):
        from rdrobust import rdrobust
        from importlib.metadata import version
        versions['rdrobust']=version('rdrobust')
        running=opt['running']; cutoff=opt['cutoff']; bandwidth=opt['bandwidth']
        if spec['regressors'] != [running]: raise ValueError('RDD regressors must contain only running variable')
        if isinstance(cutoff,bool) or not isinstance(cutoff,(int,float)) or not np.isfinite(cutoff): raise ValueError('cutoff must be finite')
        if bandwidth != 'mserd' and (isinstance(bandwidth,bool) or not isinstance(bandwidth,(int,float)) or not np.isfinite(bandwidth) or bandwidth<=0): raise ValueError('bandwidth must be mserd or positive finite number')
        fuzzy=d[opt['treatment']].to_numpy() if method=='rdd_fuzzy' else None
        if fuzzy is not None and set(np.unique(fuzzy)) != {0,1}: raise ValueError('fuzzy treatment must contain 0 and 1')
        fit=rdrobust(d[spec['outcome']].to_numpy(),d[running].to_numpy(),c=cutoff,fuzzy=fuzzy,p=1,q=2,kernel='tri',bwselect='mserd',h=None if bandwidth=='mserd' else bandwidth,vce='nn',all=True)
        name='treatment_effect'; coef=pd.Series([float(fit.coef.loc['Robust'].iloc[0])],index=[name]); se=pd.Series([float(fit.se.loc['Robust'].iloc[0])],index=[name]); cov=pd.DataFrame([[float(se.iloc[0]**2)]],index=[name],columns=[name]); pv=pd.Series([float(fit.pv.loc['Robust'].iloc[0])],index=[name]); ci=pd.DataFrame([fit.ci.loc['Robust'].to_numpy()],index=[name]); reference='normal'; engine='rdrobust.rdrobust'
        left=float(fit.bws.loc['h','left']); right=float(fit.bws.loc['h','right']); running_values=d[running].to_numpy(); local=(running_values >= cutoff-left) & (running_values <= cutoff+right)
        diagnostics={'bandwidths':{'left':left,'right':right},'bias_bandwidths':{'left':float(fit.bws.loc['b','left']),'right':float(fit.bws.loc['b','right'])},'effective_counts':[int(v) for v in fit.N_h],'local_ids':d.loc[local,spec['id']].astype(str).tolist(),'conventional_estimate':float(fit.coef.loc['Conventional'].iloc[0]),'conventional_se':float(fit.se.loc['Conventional'].iloc[0]),'polynomial_order':1,'bias_order':2,'kernel':'triangular','variance':'nearest neighbor'}
    elif method == 'rdd_localrand':
        from scipy.stats import permutation_test
        nperm=opt['permutations']; seed=opt['seed']
        if isinstance(nperm,bool) or not isinstance(nperm,int) or nperm<1000 or isinstance(seed,bool) or not isinstance(seed,int) or seed<0: raise ValueError('local randomization requires at least 1000 permutations and a nonnegative seed')
        assigned=(d[opt['running']]>=opt['cutoff']).astype(int); treated=d.loc[assigned==1,spec['outcome']].to_numpy(); control=d.loc[assigned==0,spec['outcome']].to_numpy()
        if min(len(treated),len(control))<2: raise ValueError('each local assignment arm requires at least two observations')
        test=permutation_test((treated,control),lambda a,b,axis: np.mean(a,axis=axis)-np.mean(b,axis=axis),n_resamples=nperm,alternative='two-sided',rng=np.random.default_rng(seed))
        rx=pd.DataFrame({'const':np.ones(len(d)),'assignment':assigned.to_numpy()},index=d.index); fit=sm.OLS(d[spec['outcome']],rx).fit(cov_type='HC1')
        coef=fit.params; cov=fit.cov_params(); se=fit.bse; pv=fit.pvalues; ci=fit.conf_int(); reference='normal'; engine='statsmodels.OLS + scipy.stats.permutation_test'
        diagnostics={'randomization_test':{'sharp_null':'zero individual treatment effects','assignment':'complete randomization within fixed window conditional on observed arm counts','p_value':float(test.pvalue),'statistic':float(test.statistic),'actual_permutations':int(len(test.null_distribution)),'treated':len(treated),'control':len(control)}}
    elif method == 'rct':
        from scipy.stats import permutation_test
        treatment=opt['treatment']; nperm=opt['permutations']; seed=opt['seed']
        if spec['regressors'] != [treatment]: raise ValueError('rct regressors must contain exactly treatment')
        if isinstance(nperm,bool) or not isinstance(nperm,int) or nperm<1000 or isinstance(seed,bool) or not isinstance(seed,int) or seed<0: raise ValueError('rct requires at least 1000 permutations and a nonnegative integer seed')
        if set(d[treatment].unique()) != {0,1}: raise ValueError('rct treatment must contain 0 and 1')
        treated=d.loc[d[treatment]==1,spec['outcome']].to_numpy(); control=d.loc[d[treatment]==0,spec['outcome']].to_numpy()
        if min(len(treated),len(control))<2: raise ValueError('each RCT arm needs at least two observations')
        test=permutation_test((treated,control),lambda a,b,axis: np.mean(a,axis=axis)-np.mean(b,axis=axis),n_resamples=nperm,alternative='two-sided',rng=np.random.default_rng(seed))
        fit=sm.OLS(d[spec['outcome']],X).fit(cov_type='HC1'); coef=fit.params; cov=fit.cov_params(); se=fit.bse; pv=fit.pvalues; ci=fit.conf_int(); reference='normal'
        engine='statsmodels.OLS + scipy.stats.permutation_test'; diagnostics={'randomization_test':{'sharp_null':'zero individual treatment effects','assignment':'complete randomization with observed arm counts','p_value':float(test.pvalue),'statistic':float(test.statistic),'actual_permutations':int(len(test.null_distribution)),'treated':len(treated),'control':len(control)}}
    elif method in ('gls','poisson','logit'):
        fitkw = {'cov_type':'HC1'} if groups is None else {'cov_type':'cluster','cov_kwds':{'groups':groups,'use_correction':True}, 'use_t':True}
        if method == 'gls':
            if (d[opt['variance']]<=0).any(): raise ValueError('GLS diagonal variances must be positive')
            fit = sm.GLS(d[spec['outcome']],X,sigma=d[opt['variance']].to_numpy()).fit(**fitkw)
            engine = 'statsmodels.GLS'; diagnostics['variance_range'] = [float(d[opt['variance']].min()),float(d[opt['variance']].max())]
        else:
            y=d[spec['outcome']]
            if method == 'poisson' and (y<0).any(): raise ValueError('Poisson conditional-mean outcome must be nonnegative')
            if method == 'logit' and set(y.unique()) != {0,1}: raise ValueError('logit outcome must contain 0 and 1')
            family=sm.families.Poisson() if method=='poisson' else sm.families.Binomial()
            fit=sm.GLM(y,X,family=family).fit(**fitkw)
            if not fit.converged: raise ArithmeticError('GLM failed to converge')
            engine = 'statsmodels.GLM.' + ('Poisson' if method=='poisson' else 'Binomial')
            diagnostics['converged']=bool(fit.converged)
        coef=fit.params; cov=fit.cov_params(); se=fit.bse; pv=fit.pvalues; ci=fit.conf_int(); reference='Student t' if groups is not None else 'normal'
    elif method=='quantile':
        q=opt['quantile']
        if isinstance(q,bool) or not isinstance(q,(int,float)) or not 0<q<1: raise ValueError('quantile must be in (0,1)')
        fit=sm.QuantReg(d[spec['outcome']],X).fit(q=q,vcov='robust',kernel='epa',bandwidth='hsheather',max_iter=10000)
        if fit.iterations>=10000: raise ArithmeticError('quantile fit reached iteration limit')
        engine='statsmodels.QuantReg'; coef=fit.params; cov=fit.cov_params(); se=fit.bse; pv=fit.pvalues; ci=fit.conf_int(); reference='Student t'; diagnostics={'iterations':int(fit.iterations),'bandwidth':float(fit.bandwidth),'sparsity':float(fit.sparsity)}
    elif method=='iv_ar':
        import linearmodels
        from linearmodels.iv import IV2SLS
        from scipy.stats import f as f_distribution
        versions['linearmodels']=linearmodels.__version__
        alpha=opt['alpha']
        if isinstance(alpha,bool) or not isinstance(alpha,(int,float)) or not 0<alpha<1: raise ValueError('alpha must be in (0,1)')
        y=d[spec['outcome']].to_numpy(); end=d[spec['endogenous'][0]].to_numpy(); Z=d[spec['instruments']].to_numpy()
        yr=sm.OLS(y,X).fit().resid.to_numpy(); dr=sm.OLS(end,X).fit().resid.to_numpy()
        zr=np.column_stack([sm.OLS(Z[:,j],X).fit().resid.to_numpy() for j in range(Z.shape[1])])
        q=zr.shape[1]; df=len(d)-X.shape[1]-q
        if df<=0 or np.linalg.matrix_rank(zr)!=q: raise ValueError('excluded instruments must have full residualized rank and positive residual degrees of freedom')
        py=sm.OLS(yr,zr).fit().fittedvalues; pd_=sm.OLS(dr,zr).fit().fittedvalues
        my=yr-py; md=dr-pd_; crit=float(f_distribution.ppf(1-alpha,q,df)); c=q*crit/df
        A=float(pd_@pd_-c*(md@md)); B=float(-2*(py@pd_-c*(my@md))); C=float(py@py-c*(my@my))
        scale=max(abs(A),abs(B),abs(C),1.0); eps=1e-12*scale
        if abs(A)<=eps:
            if abs(B)<=eps: intervals=[{'lower':None,'upper':None}] if C<=0 else []
            else:
                root=-C/B; intervals=[{'lower':None,'upper':root}] if B>0 else [{'lower':root,'upper':None}]
        else:
            disc=B*B-4*A*C
            if disc<0: intervals=[{'lower':None,'upper':None}] if A<0 else []
            else:
                roots=sorted([(-B-np.sqrt(disc))/(2*A),(-B+np.sqrt(disc))/(2*A)])
                intervals=[{'lower':roots[0],'upper':roots[1]}] if A>0 else [{'lower':None,'upper':roots[0]},{'lower':roots[1],'upper':None}]
        fit=IV2SLS(d[spec['outcome']],X,d[spec['endogenous']],d[spec['instruments']]).fit(cov_type='unadjusted',debiased=True)
        engine='linearmodels.iv.IV2SLS + statsmodels.OLS + scipy.stats.f'; coef=fit.params; cov=fit.cov; se=fit.std_errors; pv=fit.pvalues; ci=fit.conf_int(); reference='Student t'
        diagnostics={'anderson_rubin':{'confidence_level':1-alpha,'intervals':intervals,'null_endpoint':'unbounded','f_critical':crit,'numerator_df':q,'denominator_df':int(df),'quadratic':[A,B,C]}}
    elif method=='iv_gmm':
        import linearmodels
        from linearmodels.iv import IVGMM
        versions['linearmodels']=linearmodels.__version__
        fit=IVGMM(d[spec['outcome']],X,d[spec['endogenous']],d[spec['instruments']],weight_type='robust').fit(cov_type='clustered' if groups is not None else 'robust',debiased=True,**({'clusters':groups} if groups is not None else {}))
        engine='linearmodels.iv.IVGMM'; coef=fit.params; cov=fit.cov; se=fit.std_errors; pv=fit.pvalues; ci=fit.conf_int(); reference='Student t'; diagnostics={'iterations':int(fit.iterations),'j_statistic':float(fit.j_stat.stat) if np.isfinite(fit.j_stat.stat) else None,'j_degrees_of_freedom':int(fit.j_stat.df)}
    else:
        import linearmodels
        from linearmodels.panel import PanelOLS
        versions['linearmodels']=linearmodels.__version__
        if not all(isinstance(opt[k],bool) for k in ('entity_effects','time_effects')) or not (opt['entity_effects'] or opt['time_effects']): raise ValueError('at least one boolean fixed effect must be true')
        if d.duplicated([opt['entity'],opt['time']]).any(): raise ValueError('entity-time pairs must be unique')
        panel=d.set_index([opt['entity'],opt['time']]); xp=X.set_axis(panel.index)
        fit=PanelOLS(panel[spec['outcome']],xp,entity_effects=opt['entity_effects'],time_effects=opt['time_effects']).fit(cov_type='clustered',cluster_entity=True,debiased=True)
        engine='linearmodels.panel.PanelOLS'; coef=fit.params; cov=fit.cov; se=fit.std_errors; pv=fit.pvalues; ci=fit.conf_int(); reference='Student t'; diagnostics={'entities':int(d[opt['entity']].nunique()),'periods':int(d[opt['time']].nunique()),'residual_df':int(fit.df_resid)}
    arrays=[np.asarray(z,dtype=float) for z in (coef,cov,se,pv,ci)]
    if any(not np.isfinite(z).all() for z in arrays): raise ArithmeticError('estimator returned nonfinite inference')
    names=list(coef.index); vals=[float(v) for v in coef]; std=[float(v) for v in se]
    units={k:(spec['unit'] if k in ('const','treatment_effect','sample_ate','policy_value_gain','overall','post') or k.startswith(('event_','cohort_','time_')) else 'dimensionless' if k in ('spatial_lag','log_sigma','L1.'+spec['outcome']) else f"{spec['unit']} per one unit of {k}") for k in names}
    stats={f'coefficient.{k}':{'value':v,'unit':units[k]} for k,v in zip(names,vals)}
    stats.update({f'standard_error.{k}':{'value':v,'unit':units[k]} for k,v in zip(names,std)})
    stats.update({f'p_value.{k}':{'value':float(pv.loc[k]),'unit':'probability'} for k in names})
    level_label = format(100*confidence_level, '.8g')
    stats.update({f'confidence_{level_label}_lower.{k}':{'value':float(ci.loc[k].iloc[0]),'unit':units[k]} for k in names})
    stats.update({f'confidence_{level_label}_upper.{k}':{'value':float(ci.loc[k].iloc[1]),'unit':units[k]} for k in names})
    fit_n=len(d) if fit_n is None else fit_n
    stats['observations']={'value':int(fit_n),'unit':'fitted observations'}
    result = {'method':method,'engine':engine,'versions':versions,'options':opt,'adopted':{k:spec[k] for k in ('population','period','unit','estimand','identification','assignment','inference')},'sample':{'id_column':spec['id'],'included_ids':d[spec['id']].astype(str).tolist(),'excluded_incomplete_ids':excluded,'excluded_outside_window_ids':outside,'training_ids':training,'excluded_initial_lag_ids':initial_lags,'input_rows':int(input_rows),'observations':int(fit_n)},'coefficients':dict(zip(names,vals)),'standard_errors':dict(zip(names,std)),'covariance_kind':'upper bound on scalar variance' if method=='causal_forest' else 'estimator covariance','covariance':{a:{b:float(cov.loc[a,b]) for b in names} for a in names},'inference':{'reference':reference,'p_values':{k:float(pv.loc[k]) for k in names},'confidence_level':confidence_level,'confidence_intervals':{k:[float(x) for x in ci.loc[k]] for k in names}},'diagnostics':diagnostics,'statistics':stats,'provenance':{'data_path':str(p),'data_sha256':_hash(p),'spec_path':str(spec_path.resolve()),'spec_sha256':_hash(spec_path)}}
    if confidence_level == 0.95:
        result['inference']['confidence_intervals_95'] = result['inference']['confidence_intervals']
    if did_values is not None:
        aggregation = did_values['aggregate_options']
        result['covariance_kind'] = 'analytical covariance from official influence functions with adopted clustering'
        result['inference'].update(standard_error_method='multiplier bootstrap' if aggregation['bstrap'] else 'analytical',
            interval_type='simultaneous' if aggregation['cband'] and aggregation['type'] != 'simple' else 'pointwise',
            overall_interval_type='pointwise', critical_values=did_values['critical_values'])
        result['sample']['excluded_engine_ids'] = diagnostics['excluded_engine_ids']
        rows = []
        for component in did_values['components']:
            index = component['index']
            term = prefix + ('_m' + str(abs(int(index))) if index < 0 else '_p' + str(int(index)))
            role = ('reference' if aggregation['type'] == 'dynamic' and baseline and index == -opt.get('anticipation',0)-1
                    else 'post_treatment_att' if aggregation['type'] != 'dynamic' or index >= 0
                    else 'anticipation' if index >= -opt.get('anticipation',0) else 'pretreatment_diagnostic')
            row = {'term':term,'estimate':component['estimate'],'se':component['se'],
                   'ci_low':component['ci_low'],'ci_high':component['ci_high'],
                   'p_value':result['inference']['p_values'].get(term),
                   'n':component['treated_units'],'unit':spec['unit'],'role':role}
            row['event_time' if aggregation['type'] == 'dynamic' else 'group' if aggregation['type'] == 'group' else 'period'] = index
            rows.append(row)
        if not rows:
            rows = [{'term':'overall','estimate':result['coefficients']['overall'],
                     'se':result['standard_errors']['overall'],'ci_low':float(ci.loc['overall'].iloc[0]),
                     'ci_high':float(ci.loc['overall'].iloc[1]),'p_value':float(pv.loc['overall']),
                     'n':fit_n,'unit':spec['unit'],'role':'post_treatment_att'}]
        result['display'] = {'kind':'event-study' if aggregation['type'] == 'dynamic' else 'coefficient',
            'rows':rows,'metadata':{'aggregation':aggregation['type'],'confidence_level':confidence_level,
            'interval_type':result['inference']['interval_type'],
            'reference_event_time':-opt.get('anticipation',0)-1 if baseline else None,
            'cohort_contributions':[{k:v for k,v in component.items() if k != 'treated_sample_ids'} for component in did_values['components']],
            'unit':spec['unit'],'population':spec['population'],
            'sample':{k:v for k,v in result['sample'].items() if not isinstance(v,list)}}}
    return result


def case(output):
    """Generate original seeded data and execute every supported model."""
    output.mkdir(parents=True,exist_ok=False)
    rng=np.random.default_rng(10198)
    n=1200; x=rng.normal(size=n); z=rng.normal(size=n); z2=rng.normal(size=n)
    e=rng.normal(size=n); var=0.5+x*x; treatment=0.9*z+0.6*z2+0.7*e+rng.normal(size=n)
    frame=pd.DataFrame({'id':[f'r{i}' for i in range(n)],'x':x,'z':z,'z2':z2,'d':treatment,'variance':var,
        'y_gls':1+2*x+np.sqrt(var)*rng.normal(size=n),
        'y_iv':1+1.5*treatment+0.5*x+e,
        'y_quantile':1+2*x+rng.normal(size=n),
        'y_tobit':np.maximum(0,1+2*x+rng.normal(size=n)),
        'y_poisson':rng.poisson(np.exp(0.2+0.4*x)),
        'y_logit':rng.binomial(1,1/(1+np.exp(-(-0.3+0.8*x))))})
    frame['assigned']=rng.permutation(np.r_[np.zeros(n//2,dtype=int),np.ones(n-n//2,dtype=int)])
    frame['y_rct']=1+1.5*frame['assigned']+rng.normal(size=n)
    shares=rng.dirichlet([1,1,1,1],size=n); shocks=np.array([-1.5,-.5,.5,1.5]); shift=shares@shocks; shift_error=rng.normal(size=n); frame['shift_d']=1.5*shift+0.5*shift_error+rng.normal(scale=.5,size=n); frame['y_shift']=1+1.5*frame['shift_d']+.5*x+shift_error
    for j in range(4): frame[f'share{j}']=shares[:,j]
    frame['y_cate']=x+(1+x)*frame['assigned']+rng.normal(size=n)
    frame['y_dist']=frame['assigned']+rng.normal(size=n)
    frame['policy_d']=rng.binomial(1,0.5,n); frame['policy_p']=0.5; frame['partition']=np.where(np.arange(n)%2==0,'train','evaluation'); frame['y_policy']=1+x+1.5*x*frame['policy_d']+rng.normal(scale=.5,size=n)
    frame['running']=rng.uniform(-1,1,n); above=(frame['running']>=0); frame['received']=rng.binomial(1,0.15+0.7*above); frame['y_sharp']=1+frame['running']+2*above+rng.normal(scale=.5,size=n); frame['y_local']=1+2*above+rng.normal(scale=.5,size=n); frame['y_fuzzy']=1+frame['running']+2*frame['received']+rng.normal(scale=.5,size=n)
    frame.to_csv(output/'cross.csv',index=False)
    units=200; periods=6
    u=np.repeat(np.arange(units),periods); t=np.tile(np.arange(periods),units)
    px=rng.normal(size=len(u)); alpha=np.repeat(rng.normal(size=units),periods)
    panel=pd.DataFrame({'id':[f'p{i}' for i in range(len(u))],'entity':u,'time':t,'x':px,'y':2*px+alpha+0.3*t+rng.normal(size=len(u))})
    panel.to_csv(output/'panel.csv',index=False)
    nd=250; td=10; dx=rng.normal(size=(nd,td)); dy=np.zeros((nd,td)); da=rng.normal(size=nd)
    for j in range(1,td): dy[:,j]=.55*dy[:,j-1]+.7*dx[:,j]+da+rng.normal(size=nd)
    pd.DataFrame({'id':[f'd{i}' for i in range(nd*td)],'entity':np.repeat(np.arange(nd),td),'time':np.tile(np.arange(td),nd),'x':dx.ravel(),'y':dy.ravel()}).to_csv(output/'dynamic.csv',index=False)
    ns=160; spatial_x=rng.normal(size=ns); shock=rng.normal(size=ns); W=np.zeros((ns,ns)); idx=np.arange(ns); W[idx,(idx-1)%ns]=0.5; W[idx,(idx+1)%ns]=0.5
    spatial_y=np.linalg.solve(np.eye(ns)-.35*W,1+1.7*spatial_x+shock); nt=rng.binomial(1,.5,ns); network_y=1+.5*spatial_x+.8*nt+1.2*(W@nt)+rng.normal(scale=.5,size=ns); pd.DataFrame({'id':[f's{i}' for i in idx],'x':spatial_x,'y':spatial_y,'assigned':nt,'network_y':network_y}).to_csv(output/'spatial.csv',index=False)
    nsc=52; sc_t=np.arange(nsc); donor=rng.normal(size=(nsc,4))+0.02*sc_t[:,None]; true_weights=np.array([.1,.2,.3,.4]); sc_y=donor@true_weights+rng.normal(scale=.08,size=nsc)+2*(sc_t>=40)
    sc_rows=[{'id':f'c{t}_{u}','entity':f'u{u}','time':t,'y':float(sc_y[t] if u==0 else donor[t,u-1])} for t in sc_t for u in range(5)]; pd.DataFrame(sc_rows).to_csv(output/'synthetic.csv',index=False)
    nn=360; nt=7; cohort_values=np.resize(np.array([0,3,5]),nn); rng.shuffle(cohort_values); did_u=rng.normal(size=nn); did_x=rng.normal(size=nn*nt); did_entity=np.repeat(np.arange(nn),nt); did_time=np.tile(np.arange(1,nt+1),nn); did_g=np.repeat(cohort_values,nt); did_y=did_u[did_entity]+.3*did_time+.4*did_x+1.5*((did_g>0)&(did_time>=did_g))+rng.normal(size=nn*nt)
    pd.DataFrame({'id':[f'g{i}' for i in range(nn*nt)],'entity':did_entity,'time':did_time,'cohort':did_g,'x':did_x,'y':did_y}).to_csv(output/'staggered.csv',index=False)
    ng=70; tg=12; gunit=np.repeat(np.arange(ng),tg); gtime=np.tile(np.arange(1,tg+1),ng); gx=rng.normal(size=ng*tg); galpha=rng.normal(size=ng); gloading=rng.normal(size=ng); gd=((gunit<10)&(gtime>=9)).astype(int); gy=galpha[gunit]+.2*gtime+gloading[gunit]*np.sin(gtime/2)+.4*gx+1.4*gd+rng.normal(scale=.2,size=ng*tg)
    pd.DataFrame({'id':[f'h{i}' for i in range(ng*tg)],'entity':gunit,'time':gtime,'treated':gd,'x':gx,'y':gy}).to_csv(output/'gsynth.csv',index=False)
    nm=1200; mb=rng.normal(size=nm); mu=rng.normal(size=nm); md1=rng.binomial(1,.4,nm); md2=rng.binomial(1,.35,nm); dose=rng.binomial(2,.3,nm)*.5; my0=mu+.3*mb+rng.normal(size=nm); my1=mu+.3*mb+.5+1.2*md1+.6*md2+.7*dose+rng.normal(size=nm)
    mtrows=[{'id':f'm{i}_{t}','entity':i,'time':t,'x':mb[i],'d1':int(md1[i]) if t else 0,'d2':int(md2[i]) if t else 0,'dose':dose[i] if t else 0,'y':my1[i] if t else my0[i]} for i in range(nm) for t in range(2)]; pd.DataFrame(mtrows).to_csv(output/'multitreatment.csv',index=False)
    pd.DataFrame([{'source':f's{i}','target':f's{j}','weight':0.5} for i in idx for j in ((i-1)%ns,(i+1)%ns)]).to_csv(output/'weights.csv',index=False)
    common={'id':'id','regressors':['x'],'endogenous':[],'instruments':[],
      'population':'seeded simulated units','period':'simulated','unit':'outcome units',
      'estimand':'specified conditional model coefficient','identification':'exogeneity holds by construction',
      'assignment':'independent simulated units','inference':{'type':'robust'},'options':{}}
    specs={
      'distribution_effect':{'data':'cross.csv','outcome':'y_dist','regressors':['assigned'],'options':{'treatment':'assigned','threshold':0.0},'unit':'probability','estimand':'treatment minus control outcome CDF at zero','identification':'randomized treatment assignment','assignment':'complete randomization'},
      'multitreatment_did':{'data':'multitreatment.csv','outcome':'y','options':{'entity':'entity','time':'time','pre':0,'post':1,'treatments':['d1','d2','dose']},'estimand':'additive effects of two binary interventions and continuous dose','identification':'conditional parallel trends, no anticipation and additive linear treatment response','assignment':'independent simulated interventions'},
      'generalized_synth':{'data':'gsynth.csv','outcome':'y','options':{'entity':'entity','time':'time','treatment':'treated','factors':1,'bootstraps':50,'seed':42},'inference':{'type':'gsynth'},'estimand':'average and event-time treated effects','identification':'interactive fixed-effects counterfactual and untreated donor stability','assignment':'ten units adopt in period 9'},
      'staggered_did':{'data':'staggered.csv','outcome':'y','options':{'entity':'entity','time':'time','cohort':'cohort','control_group':'nevertreated'},'inference':{'type':'did'},'estimand':'group-time ATT and event-time average effects','identification':'conditional parallel trends, overlap and no anticipation','assignment':'staggered adoption with never-treated controls'},
      'synthetic_control':{'data':'synthetic.csv','outcome':'y','regressors':['time'],'options':{'entity':'entity','time':'time','treated':'u0','training_end':23,'pre_end':39},'inference':{'type':'synthetic_holdout'},'estimand':'post effect relative to validation-period gap','identification':'stable untreated mean gap and independent time errors conditional on training weights','assignment':'one treated unit, treatment begins after period 39'},
      'dynamic_panel':{'data':'dynamic.csv','outcome':'y','options':{'entity':'entity','time':'time'},'inference':{'type':'dynamic_gmm'},'estimand':'lagged outcome persistence and exogenous covariate slope','identification':'valid lagged levels and serially uncorrelated level disturbances','assignment':'independent simulated panel entities'},
      'tobit':{'data':'cross.csv','outcome':'y_tobit','options':{'lower':0.0},'inference':{'type':'likelihood'},'estimand':'latent outcome slope','identification':'normal homoskedastic errors and censoring at known threshold','assignment':'independent simulated observations'},
      'network_spillover':{'data':'spatial.csv','outcome':'network_y','options':{'weights':'weights.csv','treatment':'assigned'},'estimand':'direct and neighbor-exposure effects','identification':'random assignments, correct exposure mapping and conditionally independent errors','assignment':'independent Bernoulli treatment on known ring'},
      'policy_tree':{'data':'cross.csv','outcome':'y_policy','options':{'treatment':'policy_d','propensity':'policy_p','partition':'partition','seed':512},'inference':{'type':'policy'},'estimand':'holdout policy value minus treat-none policy','identification':'randomized treatment with known propensity and independent holdout','assignment':'independent Bernoulli treatment'},
      'shift_share':{'data':'cross.csv','outcome':'y_shift','endogenous':['shift_d'],'options':{'shares':['share0','share1','share2','share3'],'shocks':[-1.5,-0.5,0.5,1.5]},'estimand':'linear effect of shift-induced treatment','identification':'share-weighted shock exogeneity, relevance and independent unit errors conditional on fixed shocks','assignment':'independent units with fixed simulated shocks'},
      'rdd_localrand':{'data':'cross.csv','outcome':'y_local','regressors':['running'],'options':{'running':'running','cutoff':0.0,'bandwidth':0.15,'permutations':1999,'seed':202},'inference':{'type':'randomization'},'estimand':'local difference in assignment means','identification':'as-if complete randomization and no variation in potential outcome distribution inside the declared window','assignment':'cutoff assignment within fixed window'},
      'spatial_lag':{'data':'spatial.csv','outcome':'y','options':{'weights':'weights.csv'},'inference':{'type':'spatial_ml'},'estimand':'spatial autoregressive coefficient and direct covariate coefficient','identification':'known weights and exogenous covariates with iid Gaussian disturbances','assignment':'160 units on a ring'},
      'causal_forest':{'data':'cross.csv','outcome':'y_cate','regressors':['x'],'options':{'treatment':'assigned','seed':404,'trees':100,'min_leaf':10},'inference':{'type':'forest'},'estimand':'sample average treatment effect and conditional treatment effects','identification':'random treatment assignment and overlap','assignment':'complete randomization'},
      'hdfe':{'data':'panel.csv','outcome':'y','options':{'fixed_effects':['entity','time']},'inference':{'type':'cluster','cluster':'entity'},'assignment':'independent entities observed in six periods'},
      'rdd_sharp':{'data':'cross.csv','outcome':'y_sharp','regressors':['running'],'options':{'running':'running','cutoff':0.0,'bandwidth':'mserd'},'inference':{'type':'rdrobust'},'estimand':'outcome jump at cutoff','identification':'conditional potential outcomes continuous at cutoff','assignment':'sharp cutoff assignment'},
      'rdd_fuzzy':{'data':'cross.csv','outcome':'y_fuzzy','regressors':['running'],'options':{'running':'running','cutoff':0.0,'bandwidth':'mserd','treatment':'received'},'inference':{'type':'rdrobust'},'estimand':'local complier treatment effect','identification':'continuity, exclusion, monotonicity and nonzero treatment jump','assignment':'cutoff changes receipt probability'},
      'rct':{'data':'cross.csv','outcome':'y_rct','regressors':['assigned'],'options':{'treatment':'assigned','permutations':1999,'seed':123},'inference':{'type':'randomization'},'estimand':'average effect of assignment','identification':'complete randomization','assignment':'complete randomization of 600 treated among 1200 units'},
      'gls':{'data':'cross.csv','outcome':'y_gls','options':{'variance':'variance'}},
      'iv_ar':{'data':'cross.csv','outcome':'y_iv','endogenous':['d'],'instruments':['z','z2'], 'options':{'alpha':0.05}, 'inference':{'type':'homoskedastic'}, 'estimand':'effect of endogenous d', 'identification':'excluded z and z2 independent of homoskedastic normal outcome error'},
      'iv_gmm':{'data':'cross.csv','outcome':'y_iv','endogenous':['d'],'instruments':['z','z2'],
                'estimand':'effect of endogenous d','identification':'excluded z and z2 independent of outcome error'},
      'panel_fe':{'data':'panel.csv','outcome':'y','options':{'entity':'entity','time':'time','entity_effects':True,'time_effects':True},
                  'inference':{'type':'cluster','cluster':'entity'},'assignment':'independent entities observed in six periods'},
      'quantile':{'data':'cross.csv','outcome':'y_quantile','options':{'quantile':0.5},'estimand':'conditional median slope'},
      'poisson':{'data':'cross.csv','outcome':'y_poisson','unit':'log conditional mean','estimand':'log conditional mean slope'},
      'logit':{'data':'cross.csv','outcome':'y_logit','unit':'conditional log odds','estimand':'conditional log odds slope'}}
    targets={'distribution_effect':('assigned',-0.341344746,0.1),'multitreatment_did':('dose',0.7,0.25),'generalized_synth':('overall',1.4,0.3),'staggered_did':('event_p0',1.5,0.35),'synthetic_control':('post',2.0,0.2),'dynamic_panel':('L1.y',0.55,0.2),'tobit':('x',2.0,0.13),'network_spillover':('neighbor_exposure',1.2,0.45),'policy_tree':('policy_value_gain',0.6,0.3),'shift_share':('shift_d',1.5,0.13),'rdd_localrand':('assignment',2.0,0.35),'spatial_lag':('spatial_lag',0.35,0.22),'causal_forest':('sample_ate',1.0,0.3),'hdfe':('x',2.0,0.12),'rdd_sharp':('treatment_effect',2.0,0.4),'rdd_fuzzy':('treatment_effect',2.0,0.6),'rct':('assigned',1.5,0.2),'gls':('x',2.0,0.16),'iv_ar':('d',1.5,0.13),'iv_gmm':('d',1.5,0.13),'panel_fe':('x',2.0,0.12),
             'quantile':('x',2.0,0.13),'poisson':('x',0.4,0.1),'logit':('x',0.8,0.2)}
    checks={}
    for method,settings in specs.items():
        s={**common,**settings,'method':method}; sp=output/(method+'.json'); state.save(sp,s)
        result=run(s,sp); state.save(output/(method+'-result.json'),result)
        name,truth,tolerance=targets[method]; estimate=result['coefficients'][name]
        checks[method]={'parameter':name,'benchmark':truth,'benchmark_definition':'population optimal rule value gain under standard normal x' if method=='policy_tree' else 'generating parameter', 'estimate':estimate,'absolute_error':abs(estimate-truth),'tolerance':tolerance,'passed':abs(estimate-truth)<tolerance}
    state.save(output/'checks.json',checks)
    if not all(x['passed'] for x in checks.values()): raise ArithmeticError('seeded case failed its prespecified numerical comparison')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='operation',required=True)
    run_parser=sub.add_parser('run'); run_parser.add_argument('spec',type=Path); run_parser.add_argument('--output','-o',required=True,type=Path)
    select_parser=sub.add_parser('select'); select_parser.add_argument('spec',type=Path); select_parser.add_argument('--output','-o',required=True,type=Path)
    case_parser=sub.add_parser('case'); case_parser.add_argument('--output','-o',required=True,type=Path)
    a=parser.parse_args()
    try:
        if a.operation=='case': case(a.output)
        else:
            spec=json.loads(a.spec.read_text(encoding='utf-8'))
            result=select_method(spec) if a.operation=='select' else run(spec,a.spec)
            state.save(a.output,result)
    except (ValueError,TypeError,KeyError,OSError,ArithmeticError) as exc: parser.exit(2,f'error: {exc}\n')

if __name__=='__main__': main()
