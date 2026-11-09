#!/usr/bin/env python3
"""Execute explicitly specified empirical models with specialist estimators.

See econ-design/references/causal-models.md for the supported model contracts.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FLAT_EXPORT = (Path(__file__).resolve().parent / 'RESOURCES.json').is_file()
ROOT = Path(__file__).resolve().parent if FLAT_EXPORT else Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT if FLAT_EXPORT else ROOT / 'harness'))
sys.path.insert(0, str(ROOT if FLAT_EXPORT else ROOT / 'skills/econ-design/scripts'))
from research_design import (R_METHODS, GRF_METHODS, QTE_METHODS, MARGINAL_FUNCTIONS, RUN_FIELDS,
    DML_METHODS, DML_TREATMENT_METHODS, INFERENCE_METHODS, CAUSAL_EXTENSIONS, select_method)


def _hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _fixed_effects_julia(spec, spec_path):
    """Call FixedEffectModels on the canonical table and retain its native fit."""
    import numpy as np
    import research_data
    import os
    import subprocess
    import tempfile

    opt = spec['options']
    allowed = {'fixed_effects','weights','weights_type','tol','maxiter','drop_singletons',
               'confidence_level','native_output','julia'}
    if set(opt)-allowed or not isinstance(opt.get('fixed_effects'),list):
        raise ValueError('fixed_effects_julia requires fixed_effects and its documented native options')
    julia = opt.get('julia')
    if 'julia' in opt and (not isinstance(julia, str) or not julia):
        raise ValueError('options.julia must name the Julia executable')
    julia_argv = research_data.companion_command('julia', julia, default_options=('--startup-file=no',))
    if opt.get('weights') is not None and opt.get('weights_type') != 'analytic':
        raise ValueError('FixedEffectModels weights require the adopted analytic-weight convention')
    inf = spec['inference']
    if not isinstance(inf,dict) or inf.get('type') not in ('robust','cluster','homoskedastic'):
        raise ValueError('fixed_effects_julia supports robust, cluster or homoskedastic covariance')
    clusters = inf.get('clusters', [inf['cluster']] if 'cluster' in inf else [])
    if (set(inf)-{'type','cluster','clusters'} or ('cluster' in inf and 'clusters' in inf)
            or not isinstance(clusters,list) or len(set(clusters)) != len(clusters)
            or (inf['type']=='cluster') != bool(clusters)):
        raise ValueError('cluster inference must bind its distinct cluster columns')
    columns = [spec['id'],spec['outcome'],*spec['regressors'],*spec['endogenous'],
               *spec['instruments'],*opt['fixed_effects'],*clusters]
    if opt.get('weights'): columns.append(opt['weights'])
    if any(not isinstance(column,str) or not column for column in columns):
        raise ValueError('model roles must bind named columns')
    if len(set(opt['fixed_effects'])) != len(opt['fixed_effects']):
        raise ValueError('fixed effects must name distinct columns')
    level = opt.get('confidence_level',.95)
    tol, maxiter = opt.get('tol',1e-6), opt.get('maxiter',10000)
    if (isinstance(level,bool) or not isinstance(level,(float,int)) or not 0 < level < 1
            or isinstance(tol,bool) or not isinstance(tol,(float,int)) or not np.isfinite(tol) or tol <= 0
            or isinstance(maxiter,bool) or not isinstance(maxiter,int) or maxiter < 1
            or not isinstance(opt.get('drop_singletons',True),bool)):
        raise ValueError('confidence level, demeaning tolerance, iteration limit and singleton rule must be valid')
    path = Path(spec['data']); path = (path if path.is_absolute() else spec_path.parent/path).resolve()
    native_path = opt.get('native_output')
    if native_path is not None:
        if not isinstance(native_path,str) or not native_path:
            raise ValueError('native_output must name the Julia fitted-object destination')
        native_path = Path(native_path)
        native_path = (native_path if native_path.is_absolute() else spec_path.parent/native_path).resolve()
        if native_path == path or native_path == spec_path.resolve():
            raise ValueError('native_output must have its own destination')
    jcode = research_data.JULIA_READ_TABLE + r'''
using FixedEffectModels, StatsModels, JSON3, Serialization, Base64
function ers_run_fixed_effects()
s = JSON3.read(read(ARGS[1],String), Dict{String,Any}); o=s["options"]; inf=s["inference"]
clusters = get(inf,"clusters",haskey(inf,"cluster") ? [inf["cluster"]] : String[])
cols = unique(vcat([s["id"],s["outcome"]],s["regressors"],s["endogenous"],s["instruments"],o["fixed_effects"],clusters,
    haskey(o,"weights") ? [o["weights"]] : String[]))
d = ers_read_table(ARGS[2]; string_columns=[s["id"]], columns=cols)
ids = d[!,Symbol(s["id"])]
any(ismissing,ids) && error("Input IDs must be complete")
ids = string.(ids)
(length(unique(ids)) != length(ids) || any(isempty,strip.(ids))) && error("Input IDs must be unique and nonempty")
for column in vcat([s["outcome"]],s["regressors"],s["endogenous"],s["instruments"])
    all(x -> ismissing(x) || x isa Real && isfinite(x), d[!,Symbol(column)]) || error("Model columns require finite numeric observations")
end
rhs = term(1)
for column in s["regressors"]; rhs = rhs + term(Symbol(column)); end
for column in o["fixed_effects"]; rhs = rhs + fe(Symbol(column)); end
if !isempty(s["endogenous"])
    endog = reduce(+,term.(Symbol.(s["endogenous"])))
    instruments = reduce(+,term.(Symbol.(s["instruments"])))
    rhs = rhs + (endog ~ instruments)
end
formula = term(Symbol(s["outcome"])) ~ rhs
covariance = inf["type"]=="cluster" ? Vcov.cluster(Symbol.(clusters)...) :
    inf["type"]=="robust" ? Vcov.robust() : Vcov.simple()
weights = haskey(o,"weights") ? Symbol(o["weights"]) : nothing
if weights !== nothing
    all(x -> ismissing(x) || x isa Real && isfinite(x) && x > 0,d[!,weights]) || error("Analytic weights must be finite and positive")
end
fit = reg(d,formula,covariance; weights=weights,save=:all,method=:cpu,double_precision=true,
    tol=get(o,"tol",1e-6),maxiter=get(o,"maxiter",10000),drop_singletons=get(o,"drop_singletons",true),progress_bar=false)
fit.converged || error("Fixed-effect demeaning did not converge")
dof_residual(fit)>0 || error("Inference requires positive residual degrees of freedom")
keep = isfinite.(stderror(fit)); terms=string.(coefnames(fit)[keep]); b=coef(fit)[keep]; v=vcov(fit)[keep,keep]
all(isfinite,b) && all(isfinite,v) || error("Official coefficients and covariance must be finite")
ci=confint(fit;level=get(o,"confidence_level",.95))[keep,:]; pv=coeftable(fit).cols[4][keep]
native = Dict("fit"=>fit,"ids"=>ids[fit.esample],"data_path"=>ARGS[2])
serialize(ARGS[4],native)
result=Dict("coefficients"=>Dict(terms .=> b),"standard_errors"=>Dict(terms .=> stderror(fit)[keep]),
    "p_values"=>Dict(terms .=> pv),"confidence_intervals"=>Dict(terms[i]=>vec(ci[i,:]) for i in eachindex(terms)),
    "covariance"=>Dict(terms[i]=>Dict(terms[j]=>v[i,j] for j in eachindex(terms)) for i in eachindex(terms)),
    "versions"=>Dict("Julia"=>string(VERSION),"FixedEffectModels"=>string(Base.pkgversion(FixedEffectModels))),
    "sample"=>Dict("input_rows"=>nrow(d),"nobs"=>nobs(fit),"included_ids"=>ids[fit.esample],"excluded_ids"=>ids[.!fit.esample]),
    "diagnostics"=>Dict("converged"=>fit.converged,"iterations"=>fit.iterations,"dof_residual"=>dof_residual(fit),
        "r_squared"=>r2(fit),"dropped_terms"=>string.(coefnames(fit)[.!keep]),"nclusters"=>fit.nclusters,
        "Kleibergen_Paap_F"=>isfinite(fit.F_kp) ? fit.F_kp : nothing),
    "effective_options"=>Dict("formula"=>string(formula),"covariance"=>string(typeof(covariance)),
        "precision"=>"Float64","device"=>"cpu","threads"=>Threads.nthreads(),"active_project"=>Base.active_project(),"tol"=>get(o,"tol",1e-6),
        "drop_singletons"=>get(o,"drop_singletons",true)))
open(ARGS[3],"w") do io; JSON3.write(io,result); end
end
ers_run_fixed_effects()
'''
    with tempfile.TemporaryDirectory(prefix='causal-julia-') as tmp:
        tmp = Path(tmp); spec_file = tmp/'spec.json'; result_file = tmp/'result.json'; native_file = tmp/'fit.jls'
        spec_file.write_text(json.dumps(spec),encoding='utf-8')
        proc = subprocess.run([*julia_argv,'-',str(spec_file),str(path),
            str(result_file),str(native_file)],input=jcode,text=True,env=os.environ.copy())
        if proc.returncode:
            raise ArithmeticError(f'FixedEffectModels engine failed with return code {proc.returncode}')
        result = json.loads(result_file.read_text()); native = native_file.read_bytes()
    result['effective_options']['julia_argv'] = julia_argv
    import base64
    native_result = {'format':'Julia-Serialization','sha256':hashlib.sha256(native).hexdigest(),
        'data_path':str(path),'data_sha256':_hash(path),'runtime_version':result['versions']['Julia']}
    if native_path is not None:
        research_data.sources.atomic_write(native_path,native)
        native_result['path'] = str(native_path)
    else:
        native_result['data'] = base64.b64encode(native).decode('ascii')
    result.update(result_format_version=1,method='fixed_effects_julia',engine='FixedEffectModels.reg',
        options=opt,native_fit=native_result,confidence_level=level,
        adopted={key:spec[key] for key in ('population','period','unit','estimand','identification','assignment','inference')},
        provenance={'data_path':str(path),'data_sha256':_hash(path),'spec_path':str(spec_path.resolve()),
            'spec_sha256':_hash(spec_path),'producer_path':str(Path(__file__).resolve()),'producer_sha256':_hash(Path(__file__))})
    result['statistics'] = {f'coefficient.{term}':{'value':value,'unit':spec['unit']} for term,value in result['coefficients'].items()}
    result['statistics']['nobs'] = {'value':result['sample']['nobs'],'unit':'observations'}
    result['display'] = {'kind':'estimation','rows':[{'term':term,'estimate':value,
        'se':result['standard_errors'][term],'p_value':result['p_values'][term],
        'ci_low':result['confidence_intervals'][term][0],'ci_high':result['confidence_intervals'][term][1],
        'unit':spec['unit']} for term,value in result['coefficients'].items()]}
    return result


def _network(spec_path, filename, ids):
    import numpy as np
    import pandas as pd
    import research_data
    from libpysal.weights import W
    wp=Path(filename); wp=(wp if wp.is_absolute() else spec_path.parent/wp).resolve()
    edge=research_data.read_frame(wp, string_columns=['source','target'])
    if set(edge.columns)!={'source','target','weight'} or edge.isna().any().any() or edge.duplicated(['source','target']).any(): raise ValueError('weights CSV needs distinct source,target,weight edges')
    edge['weight']=pd.to_numeric(edge['weight'],errors='raise')
    if not np.isfinite(edge['weight']).all() or (edge['weight']<=0).any() or (edge['source']==edge['target']).any(): raise ValueError('weights must be positive finite and exclude self-edges')
    if set(edge['source'])!=set(ids) or not set(edge['target'])<=set(ids): raise ValueError('each unit needs a neighbor and all endpoints must match input IDs')
    grouped=edge.groupby('source',sort=False)
    neighbors={i:grouped.get_group(i)['target'].astype(str).tolist() for i in ids}
    weights={i:grouped.get_group(i)['weight'].astype(float).tolist() for i in ids}
    w=W(neighbors,weights,id_order=ids,silence_warnings=True); w.transform='r'
    return w,wp


def _staggered_did(spec, data, data_path):
    """Call did with the adopted options and serialize its fitted objects."""
    import numpy as np
    import research_data
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
    rcode = research_data.R_READ_TABLE + r'''
args <- commandArgs(trailingOnly=TRUE)
suppressPackageStartupMessages(library(did))
suppressPackageStartupMessages(library(jsonlite))
did_version <- packageVersion('did')
if (did_version < '2.5.1') stop('did >= 2.5.1 is required')
updated_aggregation_rules <- did_version >= '2.5.1.906'
s <- fromJSON(args[2], simplifyVector=TRUE); o <- s$options
agg_args <- list(type='dynamic')
if (length(o$aggregation)) for(k in names(o$aggregation)) agg_args[k] <- o$aggregation[k]
if (!updated_aggregation_rules && agg_args$type == 'group' && isTRUE(agg_args$min_e > 0))
  stop('Positive group min_e requires did >= 2.5.1.906; this did version does not apply that aggregation window')
classes <- setNames('character', s$id)
d <- ers_read_table(args[1], text_columns=s$id)
if(!is.null(s$input_ids)) d <- d[as.character(d[[s$id]]) %in% s$input_ids,,drop=FALSE]
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
a <- do.call(did::att_gt, call_args)
agg_args$MP <- a
e <- do.call(did::aggte, agg_args)
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
  else if (t >= g) 'att'
  else if (t >= g-ap$anticipation) 'anticipation'
  else 'pre_diagnostic'
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

component_support <- !is.na(a$att)
balance_rule <- NULL
if (e$type == 'dynamic' && !is.null(e$balance_e) && updated_aggregation_rules) {
  # Match compute.aggte: balance on the original cell support before trimming
  # the displayed window, retaining only cohorts with every required ATT.
  event_time <- a$t-a$group
  eligible <- max(a$t)-a$group >= e$balance_e
  eligible_groups <- unique(a$group[eligible])
  required_events <- unique(event_time[eligible & event_time >= 0 & event_time <= e$balance_e])
  complete <- vapply(eligible_groups, function(g) {
    length(required_events) > 0L && all(required_events %in% event_time[a$group == g & component_support])
  }, logical(1))
  component_support <- component_support & a$group %in% eligible_groups[complete]
  balance_rule <- 'common_nonmissing_event_support'
} else if (e$type == 'dynamic' && !is.null(e$balance_e)) {
  # did 2.5.1 balances by calendar reach after removing missing ATT cells.
  component_support <- component_support & max(a$t[component_support])-a$group >= e$balance_e
  balance_rule <- 'calendar_reach_after_na_removal'
}
components <- lapply(seq_along(e$egt), function(k) {
  z <- e$egt[k]
  keep <- switch(e$type, dynamic=(a$t-a$group == z), group=(a$group == z & a$t >= a$group), calendar=(a$t == z & a$group <= a$t))
  if (e$type == 'group' && updated_aggregation_rules && isTRUE(is.finite(agg_args$min_e))) keep <- keep & a$t >= a$group+agg_args$min_e
  if (e$type == 'group' && isTRUE(is.finite(agg_args$max_e))) keep <- keep & a$t <= a$group+agg_args$max_e
  keep <- which(keep & component_support)
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
aggregation_conditions <- list(group_min_e_supported=updated_aggregation_rules,
  group_event_time_min=if(e$type == 'group') {
    if(updated_aggregation_rules && !is.null(agg_args$min_e)) max(0,agg_args$min_e) else 0
  } else NULL, balance_e_rule=balance_rule)
obj <- list(r_version=as.character(getRversion()), did_version=as.character(did_version),
  drdid_version=as.character(packageVersion('DRDID')),
  runtime=list(library_paths=I(.libPaths()),working_directory=getwd(),profile_user=Sys.getenv('R_PROFILE_USER',unset=NA_character_)),
  signatures=list(att_gt=names(formals(did::att_gt)),aggte=names(formals(did::aggte))),
  att_gt_options=settings(ap),aggregate_options=c(settings(ep), list(type=e$type,balance_e=agg_args$balance_e,min_e=agg_args$min_e,max_e=agg_args$max_e,na.rm=isTRUE(agg_args$na.rm),effective_conditions=aggregation_conditions)),
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
        (tmp / 'spec.json').write_text(json.dumps({**spec,'input_ids':data[spec['id']].astype(str).tolist()}), encoding='utf-8')
        proc = subprocess.run([*research_data.companion_command('r'), '-', str(data_path),
                               str(tmp / 'spec.json'), str(tmp / 'result.json')],
                              input=rcode, text=True, env=os.environ.copy())
        if proc.returncode:
            raise ArithmeticError(f'did engine failed with return code {proc.returncode}')
        result = json.loads((tmp / 'result.json').read_text(encoding='utf-8'))
    return result


def _rct_design(spec, spec_path):
    """Call the official RCT owner and retain its assignment/analysis identities."""
    import research_data
    import base64
    import subprocess
    import tempfile

    path = (spec_path.parent / spec['data']).resolve()
    assignment_path = spec['options'].get('assignment_result')
    if assignment_path is not None:
        assignment_path = (spec_path.parent / assignment_path).resolve()
        source = json.loads(assignment_path.read_text(encoding='utf-8'))
        if source.get('method') != 'rct_design' or source.get('options', {}).get('operation') != 'assign':
            raise ValueError('assignment_result must name a saved rct_design assign result')
        if any(source['options'].get(key) != spec['options'].get(key)
               for key in ('experimental_design','seed','treatment')):
            raise ValueError('Analysis must retain the saved assignment design, treatment column and seed')
    helper = Path(__file__).with_name('research_rct.R')
    producing_paths = [path, spec_path.resolve(), Path(__file__).resolve(), helper]
    if assignment_path is not None:
        producing_paths.append(assignment_path)
    producing_hashes = {p:_hash(p) for p in producing_paths}
    with tempfile.TemporaryDirectory(prefix='causal-rct-') as temporary:
        staged = Path(temporary)
        (staged/'spec.json').write_text(json.dumps(spec), encoding='utf-8')
        process = subprocess.run([*research_data.companion_command('r'), '-', str(staged/'spec.json'), str(path),
            str(staged/'result.json'), str(assignment_path) if assignment_path is not None else ''],
            input=research_data.R_READ_TABLE + helper.read_text(encoding='utf-8'), text=True)
        if process.returncode:
            raise ArithmeticError(f'RCT official R engine failed with return code {process.returncode}')
        result = json.loads((staged/'result.json').read_text(encoding='utf-8'))
    if any(_hash(p) != digest for p, digest in producing_hashes.items()):
        raise ArithmeticError('RCT inputs or producing code changed during execution; retain one complete input revision')
    result['provenance'] = {'data_path':str(path), 'data_sha256':_hash(path),
        'spec_path':str(spec_path.resolve()), 'spec_sha256':_hash(spec_path),
        'producer_path':str(Path(__file__).resolve()), 'producer_sha256':_hash(Path(__file__).resolve()),
        'helper_path':str(helper), 'helper_sha256':_hash(helper)}
    if assignment_path is not None:
        result['provenance'].update(assignment_path=str(assignment_path), assignment_sha256=_hash(assignment_path))
    result['native_fit']['sha256'] = hashlib.sha256(base64.b64decode(result['native_fit']['data'])).hexdigest()
    result['producer'] = {'entry_point':'research_causal.py run', 'function':result['engine'],
        'signature':result['signature'], 'versions':result['versions']}
    result['statistics'] = {}
    if 'estimates' in result:
        rows = result.pop('estimates')
        result['coefficients'] = {r['term']:r['estimate'] for r in rows}
        result['standard_errors'] = {r['term']:r['se'] for r in rows}
        result['inference'] = {'confidence_level':result['display']['metadata']['confidence_level'],
            'interval_type':'pointwise', 'source':result['engine'],
            'se_type':result['adopted']['experimental_design']['se_type'],
            'reference_distribution':result['adopted']['experimental_design']['reference_distribution'],
            'p_values':{r['term']:r['p_value'] for r in rows},
            'confidence_intervals':{r['term']:[r['ci_low'],r['ci_high']] for r in rows},
            'degrees_of_freedom':{r['term']:r['df'] for r in rows}}
        ri = result['diagnostics'].get('randomization_inference')
        if ri is not None:
            result['inference']['randomization'] = {k:v for k,v in ri.items()
                if k not in ('statistics','permutation_probabilities')}
        terms = result.pop('covariance_terms')
        covariance = result.pop('covariance', None)
        result['inference']['covariance_available'] = covariance is not None
        if covariance is not None:
            result['covariance'] = {a:{b:covariance[i][j] for j,b in enumerate(terms)} for i,a in enumerate(terms)}
        if result['adopted']['experimental_design'].get('design') == 'balanced':
            result['standard_errors'] = {}
            result['inference'].update(interval_type='none',confidence_intervals={},degrees_of_freedom={},
                p_value_target='declared sharp null',independent_draw_unit='complete declared assignment vector')
        for row in rows:
            for field, label in (('estimate','coefficient'),('se','standard_error'),
                    ('ci_low','confidence_lower'),('ci_high','confidence_upper'),('p_value','p_value')):
                if row[field] is not None:
                    result['statistics'][f'{label}.{row["term"]}'] = {'value':row[field],
                        'unit':'probability' if field == 'p_value' else spec['unit']}
    elif spec['options']['operation'] == 'diagnose':
        for row in result['display']['rows']:
            for field in ('power','coverage','bias','rmse'):
                if row[field] is not None:
                    result['statistics'][f'{field}.{row["term"]}.{row["effect"]}'] = {
                        'value':row[field], 'unit':'probability' if field in ('power','coverage') else spec['unit']}
    else:
        result['statistics']['assigned_units'] = {'value':result['adopted']['experimental_design']['assignment_units'], 'unit':'assignment units'}
    return result



def _official_r(spec, spec_path):
    """Execute a named official R interface in the existing result lifecycle."""
    import numpy as np
    import research_data
    import base64
    import os
    import subprocess
    import tempfile

    method = spec['method']; opt = spec['options']
    grf_method = method in GRF_METHODS
    required = {
        'ols_r': set(), 'fixest_ols': set(), 'fixest_ppml': set(), 'negative_binomial_r': set(),
        'heckman': {'selection','selection_regressors','estimation_method','definitions'},
        'sunab': {'entity','time','cohort'},
        'did2s': {'treatment','first_stage','second_stage','cluster_var'},
        'did_imputation': {'entity','time','cohort'},
        'fixes_event_study': {'entity','time','cohort','estimator'},
        'nonabs_did': {'entity','time','treatment','estimator'},
        'synthdid': {'entity','time','treatment','variance'},
        'drdid_panel': {'entity','time','pre','post','treatment'},
        'drdid_rc': {'time','pre','post','treatment'},
        'did_multiplegt_dyn': {'entity','time','treatment'},
        'honest_did': {'pre_terms','post_terms','restriction'},
        'wild_cluster_bootstrap': set(), 'club_sandwich': set(),
        'rdrobust_r': {'running'}, 'rddensity': {'running'}, 'rdpower': {'running'}, 'grf': {'treatment'},
        'grf_instrumental': {'treatment','instrument','definitions'},
        'grf_multi_arm': {'treatment','arms'},
        'grf_survival': {'treatment','status','definitions'},
        'iv_ar_robust': set(),
        'qte': {'treatment','seed'}, 'qtt': {'treatment','seed'},
        'quantile_did': {'entity','time','cohort','seed'},
        'changes_in_changes': {'entity','time','cohort','seed'},
        'marginaleffects': {'function'},
        'bunching': {'seed','definitions'},
        'continuous_did': {'entity','time','cohort','dose','seed','definitions'},
    }[method]
    optional = {'args','columns','seed','definitions'}
    if method in ('ols_r','fixest_ols','fixest_ppml','negative_binomial_r','sunab','fixes_event_study','iv_ar_robust'): optional.add('fixed_effects')
    if method in ('ols_r','fixest_ols','fixest_ppml','negative_binomial_r','heckman'): optional.add('confidence_level')
    if method == 'sunab': optional |= {'sunab','aggregation','never_treated','confidence_level'}
    if method == 'did2s': optional |= {'event_variable','reference_event_time','confidence_level'}
    if method == 'fixes_event_study': optional |= {'never_treated'}
    if method == 'synthdid': optional |= {'confidence_level'}
    if grf_method: optional |= {'aggregation','confidence_level','quantity'}
    if method == 'rdrobust_r': optional.add('plot')
    if method in QTE_METHODS: optional |= {'distribution_grid','aggregation'}
    if method == 'marginaleffects': optional |= {'evaluation_data','evaluation_id'}
    if method == 'bunching': optional.add('quantity')
    if method == 'continuous_did': optional |= {'quantity','plot'}
    if not required <= opt.keys() or set(opt)-required-optional:
        raise ValueError(f'{method} options require {sorted(required)} and accept {sorted(optional)}')
    if spec['inference'] != {'type':'official'}:
        raise ValueError('official R methods require inference={"type":"official"}; specify inference options in options.args')
    if not isinstance(opt.get('args', {}), dict) or not isinstance(opt.get('columns', {}), dict):
        raise ValueError('options.args and options.columns must be objects')
    if not isinstance(opt.get('definitions', {}), dict):
        raise ValueError('options.definitions must contain the adopted comparison and inference definitions')
    if grf_method:
        if not spec['regressors']:
            raise ValueError('GRF requires the adopted effect covariates in regressors')
        if opt.get('quantity','average') not in ('average','conditional'):
            raise ValueError('GRF quantity must be average or conditional')
        if 'aggregation' in opt and not isinstance(opt['aggregation'],dict):
            raise ValueError('GRF aggregation must contain native average_treatment_effect arguments')
        if opt.get('quantity') == 'conditional' and opt.get('aggregation'):
            raise ValueError('Conditional predictions use their own pointwise inference; aggregation belongs to quantity=average')
        roles = [spec['id'],spec['outcome'],opt['treatment']]
        roles += [opt['instrument']] if method == 'grf_instrumental' else [opt['status']] if method == 'grf_survival' else []
        if (any(not isinstance(column,str) or not column for column in roles)
                or len(set(roles)) != len(roles) or set(roles) & set(spec['regressors'])):
            raise ValueError('GRF ID, outcome, treatment, instrument/status and covariate roles must be distinct')
        definitions = opt.get('definitions',{})
        if method == 'grf_instrumental':
            if definitions.get('iv_estimand') not in ('conditional_late','conditional_iv_ratio'):
                raise ValueError('GRF instrumental definitions.iv_estimand must be conditional_late or conditional_iv_ratio')
            if definitions['iv_estimand'] == 'conditional_late' and not (
                    isinstance(definitions.get('compliance_population'),str) and definitions['compliance_population'].strip()):
                raise ValueError('Conditional LATE requires the adopted definitions.compliance_population')
        if method == 'grf_multi_arm':
            arms = opt['arms']
            if (not isinstance(arms,list) or len(arms)<2
                    or any(not isinstance(arm,str) or not arm for arm in arms) or len(set(arms))!=len(arms)):
                raise ValueError('GRF arms must be distinct ordered strings, with the reference arm first')
        if method == 'grf_survival':
            native = opt.get('args',{})
            horizon = native.get('horizon')
            if native.get('target') not in ('RMST','survival.probability'):
                raise ValueError('GRF survival requires args.target=RMST or survival.probability')
            if isinstance(horizon,bool) or not isinstance(horizon,(int,float)) or not np.isfinite(horizon) or horizon<=0:
                raise ValueError('GRF survival args.horizon must be a positive finite follow-up time')
            if any(not isinstance(definitions.get(key),str) or not definitions[key].strip()
                   for key in ('time_unit','censoring')):
                raise ValueError('GRF survival requires definitions.time_unit and definitions.censoring')
    if method == 'heckman':
        roles = [spec['id'],spec['outcome'],opt['selection']]
        selection_regressors = opt['selection_regressors']
        if (any(not isinstance(column,str) or not column for column in roles)
                or len(set(roles)) != len(roles)):
            raise ValueError('Heckman ID, outcome and selection columns must be distinct')
        if (not isinstance(selection_regressors,list) or not selection_regressors
                or any(not isinstance(column,str) or not column for column in selection_regressors)
                or len(set(selection_regressors)) != len(selection_regressors)):
            raise ValueError('selection_regressors must name distinct observed selection covariates')
        if set(roles) & set(selection_regressors+spec['regressors']):
            raise ValueError('Heckman covariates must be distinct from ID, outcome and selection columns')
        if not set(selection_regressors)-set(spec['regressors']):
            raise ValueError('Heckman selection requires a covariate excluded from the outcome equation')
        conditions = opt['definitions'].get('conditions',{})
        if (not isinstance(conditions,dict) or conditions.get('outcome_support') != 'continuous'
                or any(conditions.get(key) is not True for key in ('joint_gaussian_errors','exclusion','iid'))):
            raise ValueError('Heckman definitions.conditions requires continuous outcome_support and true joint_gaussian_errors, exclusion and iid')
        if opt['estimation_method'] not in ('2step','ml') or opt.get('args') or opt.get('columns'):
            raise ValueError('Heckman uses estimation_method=2step/ml and its named unweighted iid inputs')
    if method == 'continuous_did':
        if spec['regressors'] or opt.get('columns'):
            raise ValueError('contdid 0.1.2 requires an unconditional fixed-dose design; bind entity, time, cohort and dose by name')
        for key in ('entity','time','cohort','dose'):
            if not isinstance(opt[key],str) or not opt[key].strip():
                raise ValueError(f'continuous_did options.{key} must name its analysis column')
        if len({spec['outcome'],opt['entity'],opt['time'],opt['cohort'],opt['dose']}) != 5:
            raise ValueError('continuous DID outcome, entity, time, cohort and fixed dose must have distinct columns')
        for key in ('outcome_unit','dose_unit'):
            if not isinstance(opt['definitions'].get(key),str) or not opt['definitions'][key].strip():
                raise ValueError(f'continuous_did definitions.{key} must name its measurement unit')
        if opt['definitions'].get('parallel_trends_type') not in ('standard','strong'):
            raise ValueError('continuous_did definitions.parallel_trends_type must be standard or strong')
        native_args = opt.get('args',{})
        if native_args.get('target_parameter') not in ('level','slope') or native_args.get('aggregation') not in ('dose','eventstudy'):
            raise ValueError('continuous_did requires explicit args.target_parameter=level/slope and args.aggregation=dose/eventstudy')
        if native_args['target_parameter'] == 'slope' and opt['definitions']['parallel_trends_type'] != 'strong':
            raise ValueError('The local ACRT target requires the adopted strong parallel-trends restriction SPT-MP')
        if native_args['aggregation'] == 'dose' and opt['definitions'].get('dose_aggregation') != 'fixed_cohort_weights':
            raise ValueError('continuous_did dose aggregation requires the adopted fixed_cohort_weights definition')
        if opt.get('quantity','curve') not in ('curve','overall'):
            raise ValueError('continuous_did quantity must be curve or overall')
        if 'plot' in opt:
            plot = opt['plot']
            if not isinstance(plot,dict) or not isinstance(plot.get('path'),str) or not plot['path'].strip() or set(plot)-{'path','width','height','dpi'}:
                raise ValueError('continuous_did plot requires path and accepts width, height in inches and dpi')
            if Path(plot['path']).suffix.lower() not in ('.pdf','.png','.svg'):
                raise ValueError('continuous_did official plot path must end in .pdf, .png or .svg')
            for key in ('width','height','dpi'):
                if key in plot and (isinstance(plot[key],bool) or not isinstance(plot[key],(int,float)) or not np.isfinite(plot[key]) or plot[key]<=0):
                    raise ValueError(f'continuous_did plot.{key} must be positive and finite')
    if method == 'bunching':
        native_required = {'zstar','binwidth','bins_l','bins_r','poly','t0','t1'}
        if not native_required <= opt.get('args',{}).keys():
            raise ValueError('bunching args require '+', '.join(sorted(native_required)))
        if spec['regressors'] or opt.get('columns'):
            raise ValueError('bunchit uses the unbinned outcome vector; covariate and weight bindings require their own estimator')
        if not isinstance(opt['definitions'].get('running_unit'),str) or not opt['definitions']['running_unit'].strip():
            raise ValueError('bunching definitions.running_unit must name the unbinned variable unit')
        if opt.get('quantity','b') not in ('b','e'):
            raise ValueError('bunching quantity must be b (normalized mass) or e (elasticity)')
        if opt['args'].get('notch',False) is not False:
            raise ValueError('bunching 0.8.6 runner adopts the kink contract; its notch bootstrap omits notch/alpha in marginal_buncher')
        n_boot = opt['args'].get('n_boot',100)
        if isinstance(n_boot,bool) or not isinstance(n_boot,int) or n_boot<2:
            raise ValueError('bunching residual-bootstrap inference requires n_boot >= 2')
        if 'seed' in opt['args'] and opt['args']['seed']!=opt['seed']:
            raise ValueError('bunchit native seed must match options.seed')
    if method == 'marginaleffects':
        if opt['function'] not in MARGINAL_FUNCTIONS:
            raise ValueError('marginaleffects function must be a supported slopes, predictions or comparisons function')
        if ('evaluation_data' in opt) != ('evaluation_id' in opt):
            raise ValueError('evaluation_data and evaluation_id must be supplied together')
        if any(key in opt.get('args',{}) for key in ('model','newdata')):
            raise ValueError('saved model and evaluation data are bound by the post-estimation specification')
    if method in QTE_METHODS:
        if opt.get('columns'):
            raise ValueError('qte binds sampling weights by options.args.weightsname; options.columns must be empty')
        if opt.get('aggregation','overall') not in ('overall','dynamic','group'):
            raise ValueError('qte aggregation must be overall, dynamic or group')
        if method in ('qte','qtt') and opt.get('aggregation','overall') != 'overall':
            raise ValueError('cross-sectional QTE/QTT has an overall target population')
        grid = opt.get('distribution_grid')
        if grid is not None and (not isinstance(grid,list) or not grid
                or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not np.isfinite(x) for x in grid)
                or grid != sorted(set(grid))):
            raise ValueError('distribution_grid must contain increasing distinct finite outcome values')
    if method == 'iv_ar_robust':
        if opt.get('columns'):
            raise ValueError('ivDiag takes column names in options.args.cl and options.args.weights')
        if opt.get('args', {}).get('CI', True) is not True:
            raise ValueError('iv_ar_robust requires CI=true to save the Anderson-Rubin confidence set')
    if method == 'rdrobust_r' and 'plot' in opt:
        plot_options = {'p','nbins','binselect','scale','kernel','h','covs_eval','covs_drop',
                        'ginv.tol','support','masspoints','ci'}
        if not isinstance(opt['plot'],dict) or set(opt['plot'])-plot_options:
            raise ValueError('options.plot must be an object of rdplot options: ' + ', '.join(sorted(plot_options)))
    if method == 'fixes_event_study' and opt['estimator'] not in ('cs','sa','bjs','twm','flex','twfe'):
        raise ValueError('fixes estimator must be cs, sa, bjs, twm, flex or twfe')
    if method == 'fixes_event_study' and opt['estimator'] == 'cs':
        if spec['regressors'] or any(k in opt.get('args',{}) or k in opt.get('columns',{}) for k in ('weights','cluster')):
            raise ValueError('the inspected fixes CS implementation uses unadjusted unit-level comparisons; covariates, sampling weights or higher-level clusters use did::att_gt')
    if method == 'fixes_event_study' and opt['estimator'] == 'sa':
        if spec['regressors'] or 'weights' in opt.get('args',{}) or 'weights' in opt.get('columns',{}):
            raise ValueError('the inspected fixes SA implementation does not pass covariates or sampling weights to its interaction fit; use the sunab formula term in fixest::feols for that specification')
    if method == 'fixes_event_study' and opt['estimator'] in ('bjs','twm','flex'):
        if 'weights' in opt.get('args',{}) or 'weights' in opt.get('columns',{}):
            raise ValueError(f"the inspected fixes {opt['estimator'].upper()} implementation does not pass sampling weights to its fit")
    if method == 'nonabs_did' and opt['estimator'] not in ('DCDH','PanelMatch','IFE','FE','MC'):
        raise ValueError('nonabsdid estimator must be DCDH, PanelMatch, IFE, FE or MC')
    if method == 'sunab' and opt.get('aggregation','period') not in ('period','cohort','att'):
        raise ValueError('sunab aggregation must be period, cohort or att')
    if 'seed' in opt and (isinstance(opt['seed'], bool) or not isinstance(opt['seed'], int) or opt['seed'] < 0):
        raise ValueError('seed must be a nonnegative integer')
    path = Path(spec['data']); path = (path if path.is_absolute() else spec_path.parent/path).resolve()
    saved_input = method in ('honest_did','wild_cluster_bootstrap','club_sandwich','marginaleffects')
    source = None
    if saved_input:
        from research_evidence import read_json
        source = read_json(path.read_bytes(), f'saved causal result {path}')
    if method in ('wild_cluster_bootstrap','club_sandwich','marginaleffects'):
        native = source.get('native_fit', {})
        if native.get('format') != 'R-serialize-v3':
            raise ValueError('post-estimation requires the saved R-serialize-v3 fit, data and ids bundle')
        if hashlib.sha256(base64.b64decode(native['data'])).hexdigest() != native['sha256']:
            raise ValueError('saved native fit hash does not match')
    package, function = R_METHODS[method]
    evaluation_path = None
    if method == 'marginaleffects':
        function = opt['function']
        if 'evaluation_data' in opt:
            evaluation_path = Path(opt['evaluation_data'])
            evaluation_path = (evaluation_path if evaluation_path.is_absolute() else spec_path.parent/evaluation_path).resolve()
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
        covariance = source.get('covariance', {})
        if any(t not in covariance or any(u not in covariance[t] or covariance[t][u] is None for u in terms) for t in terms):
            raise ValueError('HonestDiD requires the saved full joint covariance for every ordered pre/post term')
    helper = Path(__file__).with_suffix('.R')
    helper_bytes = helper.read_bytes()
    helper_sha256 = hashlib.sha256(helper_bytes).hexdigest()
    rcode = research_data.R_READ_TABLE + helper_bytes.decode('utf-8')
    official_plot_path = None
    official_plot_bytes = None
    if method == 'continuous_did' and 'plot' in opt:
        official_plot_path = Path(opt['plot']['path'])
        official_plot_path = (official_plot_path if official_plot_path.is_absolute() else spec_path.parent/official_plot_path).resolve()
    with tempfile.TemporaryDirectory(prefix='causal-official-r-') as tmp:
        tmp = Path(tmp); (tmp/'spec.json').write_text(json.dumps(spec),encoding='utf-8')
        r_input = path
        if saved_input:
            r_input = tmp/'source.json'
            r_input.write_text(json.dumps(source),encoding='utf-8')
        plot_stage = tmp/('official_plot'+official_plot_path.suffix.lower()) if official_plot_path is not None else None
        proc = subprocess.run([*research_data.companion_command('r'),'-',str(tmp/'spec.json'),str(r_input),package,function,str(tmp/'result.json'),
                               str(evaluation_path) if evaluation_path is not None else '',str(plot_stage) if plot_stage is not None else ''],
                              input=rcode,text=True,env=os.environ.copy())
        if proc.returncode: raise ArithmeticError(f'{package} engine failed with return code {proc.returncode}')
        result = json.loads((tmp/'result.json').read_text())
        if plot_stage is not None: official_plot_bytes = plot_stage.read_bytes()
    result.update(result_format_version=1, method=method, options=opt, adopted={k:spec[k] for k in ('population','period','unit','estimand','identification','assignment','inference')},
        provenance={'data_path':str(path),'data_sha256':_hash(path),'spec_path':str(spec_path.resolve()),'spec_sha256':_hash(spec_path),
                    'producer_path':str(Path(__file__).resolve()),'producer_sha256':_hash(Path(__file__).resolve()),
                    'helper_path':str(helper),'helper_sha256':helper_sha256,
                    'table_reader_prelude_sha256':hashlib.sha256(research_data.R_READ_TABLE.encode('utf-8')).hexdigest()})
    result['producer'] = {'entry_point':'research_causal.py run','function':result['engine'],
                          'signature':result['signature'],'versions':result['versions']}
    if method in QTE_METHODS:
        result['display']['display'] = {'plot_type':'line','x':'quantile','y':'estimate'}
        if any('component' in row for row in result['display']['rows']):
            result['display']['display']['series'] = 'component'
    if method == 'continuous_did' and opt.get('quantity','curve') == 'curve' and opt['args']['aggregation'] == 'dose':
        result['display']['display'] = {'plot_type':'line','x':'dose','y':'estimate'}
    result['versions']['R'] = result.pop('R')
    if method == 'marginaleffects':
        result['source_model'] = source.get('source_model') or {'engine':source.get('engine'),'versions':source.get('versions'),
            'native_fit_sha256':source['native_fit']['sha256'],'sample':source.get('sample'),
            'adopted':source.get('adopted')}
        if evaluation_path is not None:
            result['provenance'].update(evaluation_data_path=str(evaluation_path),evaluation_data_sha256=_hash(evaluation_path))
        saved_rows = result['display']['rows']
        effective_by = result['display']['metadata']['averaging_weights'].get('by')
        by_columns = [effective_by] if isinstance(effective_by,str) else (
            effective_by if isinstance(effective_by,list) and all(isinstance(column,str) for column in effective_by) else [])
        if any('by' in row for row in saved_rows): by_columns = [*by_columns,'by']
        by_columns = sorted(set(by_columns)-{'term','variable','contrast','group'})
        display_options = {}
        term_labels = {}
        for row in saved_rows:
            if 'variable' in row:
                by_labels = [f'{column}={json.dumps(row[column],ensure_ascii=False)}' for column in by_columns if column in row]
                term_labels[row['term']] = str(row['variable']) + (' ['+', '.join(by_labels)+']' if by_labels else '')
        if term_labels: display_options['term_labels'] = term_labels
        if any('contrast' in row for row in saved_rows): display_options['facet'] = 'contrast'
        if any('group' in row for row in saved_rows): display_options['series'] = 'group'
        if opt['function'].startswith('avg_') and all('variable' in row for row in saved_rows):
            display_options['term_column'] = 'variable'
            panel_columns = sorted({'contrast','group',*by_columns})
            for row in saved_rows:
                panel = {column:row[column] for column in panel_columns if column in row}
                if panel: row['panel'] = json.dumps(panel,ensure_ascii=False,sort_keys=True)
        if display_options: result['display']['display'] = display_options
    result['native_fit']['sha256'] = hashlib.sha256(base64.b64decode(result['native_fit']['data'])).hexdigest()
    result['sample']['id_column'] = opt.get('evaluation_id',spec['id'])
    if not result['diagnostics']: result['diagnostics'] = {}
    result['sample']['observations'] = result['diagnostics'].get('observations')
    ids_available = 'sample_mapping' not in result['diagnostics']
    result['sample']['included_ids_available'] = ids_available
    if result['diagnostics'].get('input_ids'):
        result['sample']['input_ids'] = result['diagnostics']['input_ids']
    display_sample = {'id_column':result['sample']['id_column'],'included_rows':len(result['sample']['included_ids']) if ids_available else None,
                      'observations':result['sample']['observations']}
    native_metadata = result['display'].get('metadata') or {}
    definitions = opt.get('definitions', {})
    fixed_effects = result['effective_options'].get('fixed_effects') or opt.get('fixed_effects',[])
    result['display']['metadata'] = {**definitions,'unit':spec['unit'],'population':spec['population'],'estimand':spec['estimand'],
        'sample':display_sample,'engine':result['engine'],'inference':spec['inference'],
        'n':result['sample']['observations'],'n_clusters':result['diagnostics'].get('n_clusters'),
        'fixed_effects':fixed_effects,'controls':spec['regressors'],
        'period':spec['period'],'weights':{k:v for k,v in {**opt.get('args',{}),**opt.get('columns',{})}.items() if k in ('weights','i.weights','sample.weights','weight','weightsname','wts')},
        'estimator':result['engine'],'sample_policy':'official estimator preprocessing with saved observation IDs',
        'specification':{'outcome':spec['outcome'],'regressors':spec['regressors'],'fixed_effects':fixed_effects,'options':opt},
        'producer':result['producer'],'effective_options':result['effective_options'],
        'treatment':opt.get('treatment',definitions.get('treatment')),
        'cohort':opt.get('cohort',definitions.get('cohort')),
        'observation_unit':definitions.get('observation_unit',opt.get('entity')),
        'inference_unit':definitions.get('inference_unit',opt.get('cluster_var',opt.get('args',{}).get('cluster'))),
        'control_group':opt.get('args',{}).get('control_group',definitions.get('control_group')),
        'result_format_version':1,'interval_type':'pointwise','confidence_level':result['confidence_level'],**native_metadata}
    if not ids_available:
        result['display']['metadata']['sample_policy'] = result['diagnostics']['sample_mapping']
    for block in (result.get('displays') or {}).values():
        block['metadata'] = {**result['display']['metadata'],**block.get('metadata',{})}
    result['statistics'] = {}
    if method == 'iv_ar_robust':
        ar = result['diagnostics']['anderson_rubin']
        result['inference'] = {'confidence_level':ar['confidence_level'],
            'confidence_sets':{spec['endogenous'][0]:ar['intervals']},
            'set_type':ar['set_type'],'null_test':ar['null_test'],
            'interval_type':'Anderson-Rubin test inversion','source':result['engine']}
        result['sample']['input_rows'] = result['diagnostics']['input_rows']
        result['sample']['excluded_missing_ids'] = result['diagnostics']['excluded_missing_ids']
        for name, display in result['displays'].items():
            for row in display['rows']:
                result['statistics'][f'{name}.coefficient.{row["term"]}'] = {
                    'value':row['estimate'],'unit':display['metadata']['unit']}
    if method == 'heckman':
        diagnostics = result['diagnostics']
        result['sample'].update({key:diagnostics[key] for key in (
            'input_rows','input_ids','selection_ids','observed_outcome_ids','unselected_ids',
            'excluded_incomplete_ids','excluded_engine_ids','observed_outcomes','unselected_observations')})
    if result['estimates']:
        estimates = result.pop('estimates')
        if any(r.get('estimate') is None or not np.isfinite(r['estimate']) for r in estimates):
            raise ArithmeticError(f'{result["engine"]} returned a nonfinite requested estimate')
        result['coefficients'] = {r['term']:r['estimate'] for r in estimates}
        result['standard_errors'] = {r['term']:r['se'] for r in estimates if r.get('se') is not None}
        result['inference'] = {'confidence_level':result['confidence_level'],
            'p_values':{r['term']:r['p_value'] for r in estimates if r.get('p_value') is not None},
            'confidence_intervals':{r['term']:[r['ci_low'],r['ci_high']] for r in estimates if r.get('ci_low') is not None and r.get('ci_high') is not None},
            'interval_type':result['display']['metadata']['interval_type'],'source':result['engine']}
        if method == 'marginaleffects':
            result['inference'].update(procedure=native_metadata['inference_procedure'],
                reference_df=native_metadata['reference_df'],covariance=native_metadata['covariance'],
                cluster_columns=native_metadata.get('cluster_columns'))
        elif method == 'heckman':
            result['inference'].update(type='official',reference='Student t',
                degrees_of_freedom=result['diagnostics']['residual_df'],covariance='native iid',
                procedure=native_metadata['inference_procedure'],
                estimation_method=opt['estimation_method'])
        elif method in QTE_METHODS:
            result['inference'].update(procedure=native_metadata['inference_procedure'],
                inference_unit=native_metadata['inference_unit'],
                bootstrap_repetitions=result['effective_options']['args']['biters'])
        elif method == 'continuous_did':
            result['inference'].update(procedure=native_metadata['inference_procedure'],
                inference_unit=opt['entity'],seed=opt['seed'],
                bootstrap_repetitions=result['diagnostics']['bootstrap_repetitions'],
                band_family=native_metadata['band_family'],
                critical_values={r['term']:r['critical_value'] for r in estimates},
                pointwise_confidence_intervals={r['term']:[r['pointwise_ci_low'],r['pointwise_ci_high']] for r in estimates},
                uniform_confidence_bands={r['term']:[r['uniform_ci_low'],r['uniform_ci_high']] for r in estimates if 'uniform_ci_low' in r})
        if result['confidence_level'] == .95 and result['inference']['confidence_intervals']:
            result['inference']['confidence_intervals_95'] = result['inference']['confidence_intervals']
        if result['covariance'] is not None:
            terms = result.pop('covariance_terms') or list(result['coefficients'])
            if isinstance(terms,str): terms = [terms]
            matrix = np.atleast_2d(result['covariance'])
            if matrix.shape != (len(terms),len(terms)):
                raise ArithmeticError('Official covariance dimensions do not match the saved term ordering')
            result['covariance'] = {a:{b:float(matrix[i,j]) if matrix[i,j] is not None else None for j,b in enumerate(terms)} for i,a in enumerate(terms)}
        else:
            result.pop('covariance'); result.pop('covariance_terms',None)
        result['inference']['covariance_available'] = 'covariance' in result
        result['statistics'] = {f'coefficient.{r["term"]}':{'value':r['estimate'],'unit':spec['unit']} for r in estimates}
    if grf_method:
        result['inference'].update(reference_distribution='standard_normal',
            procedure=native_metadata['inference_function'],
            inference_unit=native_metadata['inference_unit'])
        result['statistics'] = {f'coefficient.{row["term"]}':{'value':row['estimate'],'unit':row['unit']}
            for row in result['display']['rows']}
    if method == 'bunching':
        rows = result['display']['rows']
        quantity = opt.get('quantity','b')
        result['display']['rows'] = [row for row in rows if row['term']==quantity]
        result['display']['metadata']['unit'] = result['display']['rows'][0]['unit']
        result['statistics'] = {f'quantity.{row["term"]}':{'value':row['estimate'],'unit':row['unit']} for row in rows}
        result['statistics'].update({f'standard_error.{row["term"]}':{'value':row['se'],'unit':row['unit']} for row in rows})
        result['inference'].update(procedure=native_metadata['inference_procedure'],
            bootstrap_repetitions=opt.get('args',{}).get('n_boot',100),seed=opt['seed'])
        result['sample']['input_rows'] = result['diagnostics']['input_rows']
        result['sample']['excluded_incomplete_ids'] = result['diagnostics']['excluded_incomplete_ids']
    if method == 'continuous_did':
        for display in [result['display'], *result['displays'].values()]:
            if display['kind'] in ('dose-response','event-study'):
                display.setdefault('display', {})['note_fields'] = [
                    'estimand','interval_type','confidence_level','control_group','base_period']
        result['statistics'] = {f'coefficient.{row["term"]}':{'value':row['estimate'],'unit':row['unit']}
            for row in result['display']['rows']}
        result['sample'].update(input_rows=result['diagnostics']['input_rows'],
            entity_column=opt['entity'],time_column=opt['time'],cohort_column=opt['cohort'],dose_column=opt['dose'],
            entities=result['diagnostics']['n_entities'],excluded_engine_ids=result['diagnostics']['excluded_engine_ids'])
        for name, display in result['displays'].items():
            for row in display['rows']:
                for field, quantity in (('estimate','coefficient'),('se','standard_error'),('ci_low','confidence_lower'),
                        ('ci_high','confidence_upper'),('pointwise_ci_low','pointwise_confidence_lower'),
                        ('pointwise_ci_high','pointwise_confidence_upper'),('uniform_ci_low','uniform_confidence_lower'),
                        ('uniform_ci_high','uniform_confidence_upper'),('critical_value','critical_value')):
                    if field in row:
                        result['statistics'][f'{name}.{quantity}.{row["term"]}'] = {
                            'value':row[field],'unit':'dimensionless' if field=='critical_value' else row['unit']}
        if official_plot_path is not None:
            plot_record = {'path':str(official_plot_path),'sha256':hashlib.sha256(official_plot_bytes).hexdigest(),
                'function':'contdid::ggcont_did','target':opt['args']['target_parameter'],
                'aggregation':opt['args']['aggregation'],'format':official_plot_path.suffix.lower()[1:],
                'native_fit_sha256':result['native_fit']['sha256']}
            result['official_plot'] = plot_record
            result['display']['metadata']['official_plot'] = plot_record
            official_plot_path.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=official_plot_path.parent,prefix='.contdid-plot-',delete=False) as staged:
                staged.write(official_plot_bytes)
                staged_path = Path(staged.name)
            try:
                os.replace(staged_path,official_plot_path)
            finally:
                staged_path.unlink(missing_ok=True)
    return result


def _nuisance_learners(configs, seed):
    """Construct the shared declared sklearn nuisance learners."""
    from sklearn.ensemble import (RandomForestRegressor, RandomForestClassifier,
                                  HistGradientBoostingRegressor, HistGradientBoostingClassifier)
    from sklearn.linear_model import LinearRegression, Ridge, Lasso, LogisticRegression
    classes = {'linear':LinearRegression,'ridge':Ridge,'lasso':Lasso,'logistic':LogisticRegression,
        'random_forest_regressor':RandomForestRegressor,'random_forest_classifier':RandomForestClassifier,
        'hist_gradient_boosting_regressor':HistGradientBoostingRegressor,
        'hist_gradient_boosting_classifier':HistGradientBoostingClassifier}
    learners = {}
    effective_learners = {}
    for name, config in configs.items():
        if (not isinstance(config,dict) or not {'type'} <= config.keys() or set(config)-{'type','params'}
                or config['type'] not in classes or not isinstance(config.get('params',{}),dict)):
            raise ValueError('each nuisance learner requires a supported type and optional native params')
        cls = classes[config['type']]
        params = deepcopy(config.get('params',{}))
        signature = inspect.signature(cls)
        if 'random_state' in signature.parameters:
            params.setdefault('random_state', seed)
        if 'n_jobs' in signature.parameters:
            params.setdefault('n_jobs', 1)
        signature.bind(**params)
        learners[name] = cls(**params)
        effective_learners[name] = {'class':cls.__module__+'.'+cls.__name__,
            'params':learners[name].get_params(deep=False)}
    return learners, effective_learners


def _doubleml(spec, data, cluster_columns, input_rows):
    """Fit the declared official score and retain its sample and native coordinates."""
    import numpy as np
    import warnings
    import doubleml
    import sklearn
    from sklearn.base import is_classifier
    from sklearn.exceptions import ConvergenceWarning

    opt = spec['options']
    method = spec['method']
    if not isinstance(opt.get('definitions',{}),dict):
        raise ValueError('DoubleML definitions must be an object')
    if method == 'dml_iivm' and opt.get('normalize_ipw') and doubleml.__version__ == '0.11.4':
        raise ValueError('DoubleML 0.11.4 normalizes IIVM instrument propensities with treatment d; '
            'normalize_ipw=True requires the official correction e31e61efe8864c160c04488d91f1306e1e25c129 '
            '(normalization with instrument z). Install an official release containing that correction.')
    if method == 'dml_ssm' and opt.get('normalize_ipw') and doubleml.__version__ == '0.11.4':
        raise ValueError('DoubleML 0.11.4 scales normalized SSM corrections by treatment-arm shares; '
            'normalize_ipw=True requires the official mean-one correction '
            '7d2225b6756f4329ce7fe47a3002f48eb3b30dff. '
            'Install an official release containing that correction.')
    treatment = opt['treatment'] if method in DML_TREATMENT_METHODS else spec['endogenous'][0]
    distributional = method in ('dml_qte','dml_pq','dml_cvar')
    nonignorable = method == 'dml_ssm' and opt['score'] == 'nonignorable'
    if cluster_columns and (distributional or nonignorable):
        raise ValueError('DoubleML quantile/tail models and nonignorable SSM use native nested row splits; '
            'these specifications require independent observations')
    n_rep = opt.get('n_rep', 1)
    for name, value, lower in (('n_folds',opt['n_folds'],2),('n_rep',n_rep,1),('seed',opt['seed'],0)):
        if isinstance(value,bool) or not isinstance(value,int) or value < lower:
            raise ValueError(f'DoubleML {name} must be an integer >= {lower}')
    level = opt.get('confidence_level', .95)
    joint = opt.get('joint', False)
    if isinstance(level,bool) or not isinstance(level,(int,float)) or not 0 < level < 1:
        raise ValueError('DoubleML confidence_level must be between zero and one')
    if not isinstance(joint,bool):
        raise ValueError('DoubleML joint must be boolean')
    bootstrap = opt.get('bootstrap')
    if bootstrap is not None and (not isinstance(bootstrap,dict) or set(bootstrap) != {'method','n_rep_boot'}
            or bootstrap['method'] not in ('normal','Bayes','wild')
            or isinstance(bootstrap['n_rep_boot'],bool) or not isinstance(bootstrap['n_rep_boot'],int)
            or bootstrap['n_rep_boot'] < 1):
        raise ValueError('bootstrap requires method normal/Bayes/wild and positive integer n_rep_boot')
    if joint and bootstrap is None:
        raise ValueError('joint DoubleML intervals require options.bootstrap')
    if cluster_columns and bootstrap is not None:
        raise ValueError('the official DoubleML multiplier bootstrap requires independent observations')
    if not spec['regressors']:
        raise ValueError('DoubleML requires named covariate columns')
    if method not in ('dml_plr','dml_pliv','dml_apo') and set(data[treatment].unique()) != {0,1}:
        raise ValueError(f'{method} requires one treatment containing both 0 and 1')
    if (method == 'dml_iivm' or method == 'dml_qte' and opt['score'] == 'LPQ') and set(data[spec['instruments'][0]].unique()) != {0,1}:
        raise ValueError('IIVM and local QTE require one instrument containing both 0 and 1')
    valid_scores = {'dml_plr':{'partialling out','IV-type'},
        'dml_did':{'observational','experimental'},'dml_irm':{'ATE','ATTE'},
        'dml_pliv':{'partialling out','IV-type'},'dml_iivm':{'LATE'},
        'dml_ssm':{'missing-at-random','nonignorable'},'dml_qte':{'PQ','LPQ','CVaR'},
        'dml_pq':{'PQ'},'dml_cvar':{'CVaR'},'dml_apo':{'APO'}}
    if opt['score'] not in valid_scores[method]:
        raise ValueError(f'{method} score must be one of {sorted(valid_scores[method])}')
    if method == 'dml_ssm' and set(data[opt['selection']].unique()) != {0,1}:
        raise ValueError('SSM selection must contain both 0 and 1')
    if method in ('dml_pq','dml_cvar','dml_apo'):
        treatment_level = opt['treatment_level']
        if (isinstance(treatment_level,bool) or not isinstance(treatment_level,(int,float))
                or not np.isfinite(treatment_level) or treatment_level not in set(data[treatment])):
            raise ValueError('treatment_level must be an observed finite numeric treatment value')
        if method != 'dml_apo' and (not isinstance(treatment_level,int) or treatment_level not in (0,1)):
            raise ValueError('PQ and CVaR treatment_level must be integer 0 or 1')
        if method == 'dml_apo' and data[treatment].nunique() < 2:
            raise ValueError('APO requires observations at the selected treatment level and another level')
    if distributional:
        quantiles = opt['quantiles'] if method == 'dml_qte' else [opt['quantile']]
        if (not isinstance(quantiles,list) or not quantiles
                or any(isinstance(q,bool) or not isinstance(q,(int,float)) or not 0 < q < 1 for q in quantiles)
                or any(left >= right for left,right in zip(quantiles,quantiles[1:]))):
            raise ValueError('quantiles must be a strictly increasing nonempty list in (0,1); quantile must be in (0,1)')
    if method in ('dml_plr','dml_pliv'):
        learner_names = {'ml_l','ml_m'} | ({'ml_r'} if method == 'dml_pliv' else set())
        if opt['score'] == 'IV-type':
            learner_names.add('ml_g')
    elif method == 'dml_did':
        learner_names = {'ml_g'} | ({'ml_m'} if opt['score'] == 'observational' else set())
    else:
        learner_names = {'ml_g','ml_m'} | {'dml_iivm':{'ml_r'},'dml_ssm':{'ml_pi'}}.get(method,set())
    if not isinstance(opt['learners'],dict) or set(opt['learners']) != learner_names:
        raise ValueError(f'{method} learners must contain exactly {sorted(learner_names)}')
    learners, effective_learners = _nuisance_learners(opt['learners'], opt['seed'])
    if nonignorable and is_classifier(learners['ml_g']):
        raise ValueError('nonignorable SSM requires a regression ml_g; its native outcome step uses predict')
    constructor_options = {key:deepcopy(opt[key]) for key in
        ('score','normalize_ipw','trimming_rule','trimming_threshold','subgroups',
         'in_sample_normalization','clipping_threshold','quantile','quantiles','treatment_level') if key in opt}
    if method in ('dml_pq','dml_cvar'):
        constructor_options['treatment'] = constructor_options.pop('treatment_level')
    if method == 'dml_did' and 'clipping_threshold' in opt:
        threshold = opt['clipping_threshold']
        if isinstance(threshold,bool) or not isinstance(threshold,(int,float)) or not 0 < threshold < .5:
            raise ValueError('DID clipping_threshold must be between zero and one half')
    if 'ps_processor_config' in opt:
        from doubleml.utils import PSProcessorConfig
        constructor_options['ps_processor_config'] = PSProcessorConfig(**opt['ps_processor_config'])
    if 'weights' in opt:
        if method not in ('dml_irm','dml_apo') or opt['score'] not in ('ATE','APO'):
            raise ValueError('DoubleML constructor weights require IRM ATE or APO')
        weights = opt['weights']
        if isinstance(weights,str):
            constructor_options['weights'] = data[weights].to_numpy(dtype=float)
        else:
            arrays = weights if isinstance(weights,dict) else {'weights':weights}
            if set(arrays) not in ({'weights'},{'weights','weights_bar'}):
                raise ValueError('DoubleML weights use weights and optional weights_bar')
            converted = {}
            for key, values in arrays.items():
                values = np.asarray(values,dtype=float)
                expected = (input_rows,n_rep) if key=='weights_bar' else (input_rows,)
                if values.shape != expected or not np.isfinite(values).all():
                    raise ValueError(f'{key} must be finite with input-row shape {expected}')
                converted[key] = values[data.index.to_numpy()]
            constructor_options['weights'] = converted if 'weights_bar' in converted else converted['weights']
    frame = data.reset_index(drop=True)
    data_class = doubleml.DoubleMLData
    if method == 'dml_did':
        from doubleml.did import DoubleMLDID
        frame[spec['outcome']] = frame[spec['outcome']] - frame[opt['outcome_pre']]
        data_class = doubleml.DoubleMLDIDData
        cls = DoubleMLDID
    else:
        cls = getattr(doubleml, DML_METHODS[method])
    data_options = {'y_col':spec['outcome'],'d_cols':treatment,'x_cols':spec['regressors'],
        'z_cols':spec['instruments'] or None,'cluster_cols':cluster_columns or None}
    if method == 'dml_ssm':
        data_class = doubleml.DoubleMLSSMData
        data_options['s_col'] = opt['selection']
        # The native data backend requires finite Y; S=0 masks this value in every outcome score.
        frame.loc[frame[opt['selection']].eq(0),spec['outcome']] = 0.0
    backend = data_class(frame, **data_options)
    fit = cls(backend, **learners, n_folds=opt['n_folds'], n_rep=n_rep,
        draw_sample_splitting=False, **constructor_options)
    ids = frame[spec['id']].astype(str).tolist()
    positions = {value:i for i,value in enumerate(ids)}
    random_state = np.random.get_state()
    try:
        np.random.seed(opt['seed'])
        specified = opt.get('sample_splitting')
        if specified is None:
            fit.draw_sample_splitting()
            if method == 'dml_qte':
                fit.set_sample_splitting(fit.smpls)
        else:
            if not isinstance(specified,list) or len(specified) != n_rep:
                raise ValueError('sample_splitting must contain one fold list per repetition')
            splits = []
            cluster_splits = []
            for repetition in specified:
                if not isinstance(repetition,list) or len(repetition) != opt['n_folds']**max(1,len(cluster_columns)):
                    raise ValueError('sample_splitting fold count must match n_folds and cluster dimensions')
                row_splits = []
                row_cluster_splits = []
                for fold in repetition:
                    keys = {'train_ids','test_ids'} | ({'train_clusters','test_clusters'} if cluster_columns else set())
                    if not isinstance(fold,dict) or set(fold) != keys:
                        raise ValueError(f'each sample fold requires {sorted(keys)}')
                    for key in ('train_ids','test_ids'):
                        if not isinstance(fold[key],list) or any(value not in positions for value in fold[key]):
                            raise ValueError(f'{key} must name complete-case observation IDs')
                    row_splits.append(tuple(np.array([positions[value] for value in fold[key]],dtype=int)
                        for key in ('train_ids','test_ids')))
                    if cluster_columns:
                        for key in ('train_clusters','test_clusters'):
                            if not isinstance(fold[key],dict) or set(fold[key]) != set(cluster_columns):
                                raise ValueError(f'{key} must map each cluster column to its labels')
                        for col in cluster_columns:
                            train_labels, test_labels = fold['train_clusters'][col], fold['test_clusters'][col]
                            if not isinstance(train_labels,list) or not isinstance(test_labels,list):
                                raise ValueError('cluster labels must be lists')
                            if (len(set(train_labels)) != len(train_labels) or len(set(test_labels)) != len(test_labels)
                                    or set(train_labels) & set(test_labels)
                                    or set(train_labels) | set(test_labels) != set(frame[col])):
                                raise ValueError(f'each fold must partition the complete {col} cluster labels')
                        for j,key in enumerate(('train_clusters','test_clusters')):
                            membership = np.ones(len(frame),dtype=bool)
                            for col in cluster_columns:
                                membership &= frame[col].isin(fold[key][col]).to_numpy()
                            if not np.array_equal(np.sort(row_splits[-1][j]), np.flatnonzero(membership)):
                                raise ValueError('sample fold IDs must equal the intersection of their declared cluster sets')
                        row_cluster_splits.append(tuple([np.asarray(fold[key][col]) for col in cluster_columns]
                            for key in ('train_clusters','test_clusters')))
                splits.append(row_splits)
                cluster_splits.append(row_cluster_splits)
            fit.set_sample_splitting(splits, cluster_splits if cluster_columns else None)
        with warnings.catch_warnings():
            warnings.simplefilter('error', ConvergenceWarning)
            fit_options = {'n_jobs_cv':1,'store_predictions':True}
            if method == 'dml_qte': fit_options['n_jobs_models'] = 1
            fit.fit(**fit_options)
        if bootstrap is not None:
            fit.bootstrap(**bootstrap)
        intervals = fit.confint(joint=joint, level=float(level))
    except ConvergenceWarning as exc:
        raise ArithmeticError(f'DoubleML nuisance fit did not converge: {exc}') from exc
    finally:
        np.random.set_state(random_state)
    folds = []
    for rep, repetition in enumerate(fit.smpls):
        saved = []
        for fold_no, (train,test) in enumerate(repetition):
            fold = {'train_ids':[ids[i] for i in train], 'test_ids':[ids[i] for i in test]}
            if cluster_columns:
                native = fit.smpls_cluster[rep][fold_no]
                fold.update({key:{col:np.asarray(values).tolist() for col,values in zip(cluster_columns,native[j])}
                    for j,key in enumerate(('train_clusters','test_clusters'))})
            saved.append(fold)
        folds.append(saved)
    diagnostics = {'score':fit.score,'n_folds':fit.n_folds,'n_rep':fit.n_rep,
        'folds_per_cluster':opt['n_folds'] if cluster_columns else None,
        'cluster_columns':cluster_columns,'cluster_counts':{col:int(frame[col].nunique()) for col in cluster_columns},
        'effective_learners':effective_learners,'all_coef':fit.all_coef.tolist(),'all_se':fit.all_se.tolist(),
        'array_order':{'nuisance_predictions':['included_id','repetition','treatment'],
            'score_elements':['included_id','repetition','treatment'],'all_coef':['treatment','repetition']},
        'official_interface':{'data_constructor':str(inspect.signature(data_class)),
            'constructor':str(inspect.signature(cls)),'fit':str(inspect.signature(fit.fit)),
            'confint':str(inspect.signature(fit.confint))}}
    if method == 'dml_qte':
        diagnostics['potential_outcomes'] = [
            {'quantile':float(quantile),'treatment_level':level,'model':type(model).__name__,
             'coef':float(model.coef[0]),'se':float(model.se[0]),
             'all_coef':model.all_coef.tolist(),'all_se':model.all_se.tolist(),
             'nuisance_predictions':{key:values.tolist() for key,values in model.predictions.items()},
             'score_elements':{key:values.tolist() for key,values in model.psi_elements.items()}}
            for level,models in ((0,fit.modellist_0),(1,fit.modellist_1))
            for quantile,model in zip(fit.quantiles,models)]
        diagnostics['scaled_scores'] = fit.framework.scaled_psi.tolist()
        diagnostics['variance_scaling_factors'] = fit.framework.var_scaling_factors.tolist()
        diagnostics['array_order'] = {'all_coef':['quantile','repetition'],
            'scaled_scores':['included_id','quantile','repetition'],
            'potential_outcome_nuisance_predictions':['included_id','repetition','single_treatment'],
            'potential_outcome_score_elements':['included_id','repetition','single_treatment'],
            'potential_outcome_all_coef':['single_treatment','repetition']}
    else:
        diagnostics['nuisance_predictions'] = {key:values.tolist() for key,values in fit.predictions.items()}
        diagnostics['score_elements'] = {key:values.tolist() for key,values in fit.psi_elements.items()}
    if distributional or nonignorable:
        from sklearn.model_selection import StratifiedKFold, train_test_split
        strata = frame[treatment].to_numpy()
        stratification = [treatment]
        if nonignorable or opt['score'] == 'LPQ':
            other = opt['selection'] if nonignorable else spec['instruments'][0]
            strata = strata + 2 * frame[other].to_numpy()
            stratification.append(other)
        nested_folds = []
        for repetition in fit.smpls:
            nested_repetition = []
            for train,_ in repetition:
                first,second = train_test_split(train,test_size=.5,random_state=42,stratify=strata[train])
                nested = {'preliminary_train_ids':[ids[i] for i in first],
                    'nuisance_train_ids':[ids[i] for i in second]}
                if distributional:
                    nested['preliminary_propensity_folds'] = [
                        {'train_ids':[ids[first[i]] for i in inner_train],
                         'test_ids':[ids[first[i]] for i in inner_test]}
                        for inner_train,inner_test in StratifiedKFold(n_splits=fit.n_folds).split(first,strata[first])]
                nested_repetition.append(nested)
            nested_folds.append(nested_repetition)
        diagnostics['nested_sample_splitting'] = {'seed':42,'training_fraction':.5,
            'stratification_columns':stratification,'folds':nested_folds,
            'identity_source':'native deterministic train_test_split and preliminary StratifiedKFold rules'}
    if hasattr(fit,'weights'):
        diagnostics['score_weights'] = {key:value.tolist() for key,value in fit.weights.items()}
    if hasattr(fit,'normalize_ipw'):
        diagnostics['normalize_ipw'] = fit.normalize_ipw
        diagnostics['propensity_score_processing'] = vars(fit.ps_processor_config)
    if method == 'dml_iivm':
        diagnostics['subgroups'] = fit.subgroups
    if method == 'dml_did':
        diagnostics.update(in_sample_normalization=fit.in_sample_normalization,
            clipping_threshold=fit.clipping_threshold, outcome_change=frame[spec['outcome']].tolist())
    if method == 'dml_ssm':
        diagnostics['selection'] = {'column':opt['selection'],
            'observed_outcomes':int(frame[opt['selection']].sum()),
            'unobserved_outcomes':int(frame[opt['selection']].eq(0).sum()),
            'native_masked_outcome_value':0.0,
            'selection_propensity_processing':'native untrimmed ml_pi predictions'}
    if bootstrap is not None:
        diagnostics['bootstrap'] = {**bootstrap,'t_statistics':fit.boot_t_stat.tolist()}
    return fit, intervals, folds, diagnostics, {'doubleml':doubleml.__version__,'scikit-learn':sklearn.__version__}



def _survival_or_oaxaca(spec, spec_path):
    """Call the native duration/decomposition estimator on its declared sample."""
    import numpy as np
    import pandas as pd
    import scipy
    import statsmodels
    import statsmodels.api as sm
    import research_data
    method = spec['method']; opt = spec['options']; inf = spec['inference']
    required = {'status','ties'} if method == 'survival' else {'group','group_order','decomposition','bootstrap'}
    optional = ({'entry','strata','offset','confidence_level','effect_scale','maxiter','tol','definitions'}
        if method == 'survival' else {'two_fold_type','submitted_weight','definitions'})
    if not required <= opt.keys() or set(opt)-required-optional:
        raise ValueError(f'{method} options require {sorted(required)} and accept {sorted(optional)}')
    if not isinstance(opt.get('definitions',{}),dict):
        raise ValueError('options.definitions must contain adopted scientific definitions')
    if inf != {'type':'official'} and not (method == 'survival' and isinstance(inf,dict)
            and set(inf)=={'type','cluster'} and inf['type']=='cluster' and isinstance(inf['cluster'],str)):
        raise ValueError('survival accepts official or one-way cluster inference; Oaxaca uses its official row bootstrap')
    roles = [spec['id'],spec['outcome'],*spec['regressors']]
    if len(set(roles)) != len(roles) or 'const' in roles or not spec['regressors']:
        raise ValueError('ID, outcome and nonempty regressor roles must be distinct; const is reserved')
    extra = ([opt[k] for k in ('status','entry','strata','offset') if k in opt]
        if method == 'survival' else [opt['group']])
    if set(extra) & set(roles) or len(set(extra)) != len(extra):
        raise ValueError('duration/status/strata/offset or decomposition group must have distinct column roles')
    columns = list(dict.fromkeys([*roles,*extra,*([inf['cluster']] if inf['type']=='cluster' else [])]))
    if any(not isinstance(c,str) or not c for c in columns):
        raise ValueError('column bindings must be nonempty strings')
    path = Path(spec['data']); path = (path if path.is_absolute() else spec_path.parent/path).resolve()
    text_columns = {spec['id']:'string'}
    if method == 'oaxaca': text_columns[opt['group']] = 'string'
    data = research_data.read_frame(path, columns=columns, string_columns=text_columns)
    if not set(columns) <= set(data):
        raise ValueError(f'missing columns: {sorted(set(columns)-set(data))}')
    if data[spec['id']].isna().any() or data[spec['id']].str.strip().eq('').any() or data[spec['id']].duplicated().any():
        raise ValueError('IDs must be nonmissing and unique')
    numeric = [spec['outcome'],*spec['regressors']]
    if method == 'survival': numeric += [opt[k] for k in ('status','entry','offset') if k in opt]
    for column in numeric: data[column] = pd.to_numeric(data[column],errors='raise')
    keep = np.isfinite(data[numeric].to_numpy(dtype=float)).all(axis=1)
    for column in set(columns)-set(numeric):
        keep &= data[column].notna() & data[column].astype('string').str.strip().ne('').fillna(False)
    d = data.loc[keep].copy()
    sample = {'id_column':spec['id'],'input_rows':len(data),'complete_case_columns':columns,
        'excluded_incomplete_ids':data.loc[~keep,spec['id']].astype(str).tolist(),
        'complete_case_ids':d[spec['id']].astype(str).tolist(),'included_ids_available':True}
    if len(d) <= len(spec['regressors'])+2:
        raise ValueError('the complete sample must have positive residual degrees of freedom')
    versions = {'python':sys.version.split()[0],'numpy':np.__version__,'pandas':pd.__version__,
        'scipy':scipy.__version__,'statsmodels':statsmodels.__version__}
    result = {'result_format_version':1,'method':method,'options':deepcopy(opt),'versions':versions,
        'adopted':{k:spec[k] for k in ('population','period','unit','estimand','identification','assignment','inference')},
        'sample':sample,'statistics':{},'diagnostics':{},
        'provenance':{'data_path':str(path),'data_sha256':_hash(path),'spec_path':str(spec_path.resolve()),
            'spec_sha256':_hash(spec_path),'producer_path':str(Path(__file__).resolve()),
            'producer_sha256':_hash(Path(__file__).resolve())}}
    metadata = {**opt.get('definitions',{}),'population':spec['population'],'period':spec['period'],
        'estimand':spec['estimand'],'unit':spec['unit'],'controls':spec['regressors'],
        'outcome':spec['outcome'],'weights':'equal observation weights','result_format_version':1}
    if method == 'survival':
        import warnings
        from statsmodels.duration.hazard_regression import PHReg
        from statsmodels.tools.sm_exceptions import ConvergenceWarning
        if opt['ties'] not in ('breslow','efron'):
            raise ValueError('survival ties must be breslow or efron')
        if not set(d[opt['status']].unique()) <= {0,1} or not d[opt['status']].eq(1).any():
            raise ValueError('survival status must be zero/one with at least one event')
        if (d[spec['outcome']]<0).any():
            raise ValueError('survival duration must be nonnegative')
        if 'entry' in opt and ((d[opt['entry']]<0) | (d[opt['entry']]>d[spec['outcome']])).any():
            raise ValueError('entry must be nonnegative and no later than the recorded duration')
        level = opt.get('confidence_level',.95)
        if isinstance(level,bool) or not isinstance(level,(float,int)) or not 0<level<1:
            raise ValueError('confidence_level must be between zero and one')
        scale = opt.get('effect_scale','log_hazard')
        if scale not in ('log_hazard','hazard_ratio'):
            raise ValueError('effect_scale must be log_hazard or hazard_ratio')
        maxiter = opt.get('maxiter',100); tolerance = opt.get('tol',1e-8)
        if isinstance(maxiter,bool) or not isinstance(maxiter,int) or maxiter<1 or isinstance(tolerance,bool) or not isinstance(tolerance,(float,int)) or not np.isfinite(tolerance) or tolerance<=0:
            raise ValueError('maxiter must be a positive integer and tol a positive finite number')
        x = d[spec['regressors']].to_numpy(dtype=float)
        if np.linalg.matrix_rank(np.column_stack([np.ones(len(x)),x])) != x.shape[1]+1:
            raise ValueError('PHReg regressors must have full rank without an intercept')
        native_args = {k:d[opt[k]].to_numpy() for k in ('status','entry','strata','offset') if k in opt}
        model = PHReg(d[spec['outcome']].to_numpy(),x,ties=opt['ties'],missing='raise',**native_args)
        used = np.sort(np.concatenate(model.surv.stratum_rows)) if model.surv.stratum_rows else np.array([],dtype=int)
        if not len(used): raise ValueError('no observations enter an event risk set')
        groups = d[inf['cluster']].to_numpy() if inf['type']=='cluster' else None
        if groups is not None:
            if len(np.unique(groups))<2: raise ValueError('cluster inference requires at least two clusters')
            if len(used)!=len(d):
                raise ValueError('PHReg group sandwich requires every supplied complete observation in an event risk set; adopt that sample explicitly before clustered fitting')
        with warnings.catch_warnings():
            warnings.simplefilter('error',ConvergenceWarning)
            fit = model.fit(groups=groups,method='newton',maxiter=maxiter,tol=tolerance,disp=False)
        estimates = np.asarray(fit.params); se = np.asarray(fit.bse); covariance = np.asarray(fit.cov_params())
        ci = np.asarray(fit.conf_int(alpha=1-level)); pvalues = np.asarray(fit.pvalues)
        if not all(np.isfinite(v).all() for v in (estimates,se,covariance,ci,pvalues)):
            raise ArithmeticError('PHReg returned nonfinite coefficient inference')
        names = spec['regressors']; used_ids = d.iloc[used][spec['id']].astype(str).tolist()
        sample.update(included_ids=used_ids,observations=len(used),
            excluded_engine_ids=d.loc[~d[spec['id']].isin(used_ids),spec['id']].astype(str).tolist())
        engine = 'statsmodels.duration.hazard_regression.PHReg'
        result.update(engine=engine,coefficients=dict(zip(names,estimates.tolist())),
            standard_errors=dict(zip(names,se.tolist())),coefficient_scale='log hazard ratio',
            covariance={a:{b:float(covariance[i,j]) for j,b in enumerate(names)} for i,a in enumerate(names)},
            inference={'type':inf['type'],'cluster':inf.get('cluster'),'reference':'standard normal',
                'confidence_level':level,'interval_type':'pointwise','covariance_available':True,
                'p_values':dict(zip(names,pvalues.tolist())),
                'confidence_intervals':dict(zip(names,ci.tolist()))})
        baseline = []
        for label,triplet in zip(model.surv.stratum_names,model.baseline_cumulative_hazard(estimates)):
            baseline.extend({'stratum':str(label),'time':float(t),'cumulative_hazard':float(h),
                'estimate':float(s)} for t,h,s in zip(*triplet))
        result['diagnostics'] = {'event_count':int(d.iloc[used][opt['status']].sum()),
            'strata':list(map(str,model.surv.stratum_names)),'partial_log_likelihood':float(model.loglike(estimates)),
            'score':model.score(estimates).tolist(),'score_max_abs':float(np.max(np.abs(model.score(estimates)))),
            'cluster_count':len(np.unique(groups)) if groups is not None else None,
            'risk_set_entry':'entry <= event time <= duration','ties':opt['ties']}
        result['effective_options'] = {'constructor':{'ties':opt['ties'],'missing':'raise'},
            'columns':{k:opt[k] for k in ('status','entry','strata','offset') if k in opt},
            'fit':{'groups':inf.get('cluster'),'method':'newton','maxiter':maxiter,'tol':tolerance},
            'effect_scale':scale}
        rows = []
        for i,name in enumerate(names):
            log_unit = f'log hazard ratio per one unit of {name}'
            result['statistics']['coefficient.'+name] = {'value':float(estimates[i]),'unit':log_unit}
            result['statistics']['hazard_ratio.'+name] = {'value':float(np.exp(estimates[i])),'unit':'hazard ratio'}
            rows.append({'term':name,'estimate':float(np.exp(estimates[i]) if scale=='hazard_ratio' else estimates[i]),
                'se':float(se[i]) if scale=='log_hazard' else None,'p_value':float(pvalues[i]),
                'ci_low':float(np.exp(ci[i,0]) if scale=='hazard_ratio' else ci[i,0]),
                'ci_high':float(np.exp(ci[i,1]) if scale=='hazard_ratio' else ci[i,1]),
                'unit':'hazard ratio' if scale=='hazard_ratio' else log_unit})
        metadata.update(interval_type='pointwise',confidence_level=level,effect_scale=scale,
            inference_unit=inf.get('cluster',spec['id']),ties=opt['ties'])
        result['displays'] = {'baseline_survival':{'kind':'line','rows':baseline,
            'display':{'plot_type':'step','x':'time','y':'estimate','series':'stratum'},
            'metadata':{**metadata,'unit':'probability','time_unit':opt.get('definitions',{}).get('duration_unit',spec['outcome']),
                'estimand':'Native PHReg baseline survival immediately before each observed event time',
                'interval_type':'none','confidence_level':None,'reference_covariates':'zero linear predictor'}}}
        signatures = {'constructor':str(inspect.signature(PHReg)),'fit':str(inspect.signature(PHReg.fit))}
    else:
        from statsmodels.stats.oaxaca import OaxacaBlinder
        labels = opt['group_order']; decomposition = opt['decomposition']; boot = opt['bootstrap']
        if not isinstance(labels,list) or len(labels)!=2 or any(not isinstance(v,str) or not v for v in labels) or labels[0]==labels[1]:
            raise ValueError('group_order must contain two distinct string labels: first minus second')
        if set(d[opt['group']].unique())!=set(labels):
            raise ValueError('group_order must match exactly the two observed group labels')
        if decomposition not in ('two_fold','three_fold'):
            raise ValueError('decomposition must be two_fold or three_fold')
        if not isinstance(boot,dict) or set(boot)!={'n','conf','seed'}:
            raise ValueError('bootstrap requires exactly n, conf and seed')
        n = boot['n']; conf = boot['conf']; seed = boot['seed']
        if isinstance(n,bool) or not isinstance(n,int) or n<2 or isinstance(seed,bool) or not isinstance(seed,int) or seed<0:
            raise ValueError('bootstrap n must be at least two and seed a nonnegative integer')
        if isinstance(conf,bool) or not isinstance(conf,(float,int)) or not .5<conf<=1 or int(n*conf)-int(n*(1-conf))<2:
            raise ValueError('bootstrap conf must retain at least two ordered draws and lie in (.5,1]')
        code = d[opt['group']].map({labels[0]:0,labels[1]:1}).to_numpy()
        x = sm.add_constant(d[spec['regressors']],has_constant='add').to_numpy(dtype=float)
        for g in (0,1):
            if (code==g).sum()<=x.shape[1] or np.linalg.matrix_rank(x[code==g])!=x.shape[1]:
                raise ValueError('each Oaxaca group must have a full-rank design and positive residual degrees of freedom')
        model = OaxacaBlinder(d[spec['outcome']].to_numpy(),np.column_stack([code,x]),0,
            hasconst=True,swap=False,cov_type='nonrobust')
        args = {'std':True,'n':n,'conf':conf}
        if decomposition == 'two_fold':
            reference = opt.get('two_fold_type')
            if reference not in ('pooled','nuemark','cotton','reimers','self_submitted'):
                raise ValueError('two_fold requires native two_fold_type: pooled, nuemark, cotton, reimers or self_submitted')
            args['two_fold_type'] = reference
            if reference == 'self_submitted':
                w = opt.get('submitted_weight')
                if isinstance(w,bool) or not isinstance(w,(float,int)) or not 0<=w<=1:
                    raise ValueError('submitted_weight must be the first-group coefficient weight in [0,1]')
                args['submitted_weight'] = w
            elif 'submitted_weight' in opt:
                raise ValueError('submitted_weight belongs to self_submitted two-fold decomposition')
        elif 'two_fold_type' in opt or 'submitted_weight' in opt:
            raise ValueError('three-fold decomposition uses the second-group coefficient reference')
        random_state = np.random.get_state()
        try:
            np.random.seed(seed)
            fit = getattr(model,decomposition)(**args)
        finally:
            np.random.set_state(random_state)
        names = ['unexplained','explained','gap'] if decomposition=='two_fold' else ['endowments','coefficients','interaction','gap']
        estimates = np.asarray(fit.params,dtype=float); se = np.asarray(fit.std,dtype=float)
        if not np.isfinite(estimates).all() or not np.isfinite(se).all():
            raise ArithmeticError('OaxacaBlinder returned nonfinite decomposition or bootstrap standard deviations')
        engine = 'statsmodels.stats.oaxaca.OaxacaBlinder'
        sample.update(included_ids=d[spec['id']].astype(str).tolist(),observations=len(d),excluded_engine_ids=[])
        sample['groups'] = {label:{'observations':int((code==i).sum()),
            'included_ids':d.loc[code==i,spec['id']].astype(str).tolist()} for i,label in enumerate(labels)}
        result.update(engine=engine,coefficients=dict(zip(names,estimates.tolist())),
            standard_errors=dict(zip(names[:-1],se.tolist())),
            inference={'type':'official','procedure':'native row-bootstrap standard deviations',
                'bootstrap_repetitions':n,'seed':seed,'bootstrap_conf':conf,
                'retained_order_slice':[int(n*(1-conf)),int(n*conf)],'std_ddof':0,
                'interval_type':'none','confidence_level':None,'covariance_available':False})
        result['effective_options'] = {'constructor':{'hasconst':True,'swap':False,'cov_type':'nonrobust'},
            'group_order':labels,'decomposition':decomposition,'args':args,'seed':seed}
        result['diagnostics'] = {'group_order':labels,'gap_definition':'mean(first)-mean(second)',
            'group_means':{label:float(d.loc[code==i,spec['outcome']].mean()) for i,label in enumerate(labels)},
            'design_terms':['const',*spec['regressors']],
            'group_coefficients':{labels[0]:model._f_model.params.tolist(),labels[1]:model._s_model.params.tolist()},
            'group_regressor_means':{labels[0]:model.exog_f_mean.tolist(),labels[1]:model.exog_s_mean.tolist()},
            'reference_coefficients':model.t_params.tolist() if decomposition=='two_fold' else model._s_model.params.tolist(),
            'decomposition_sum_residual':float(estimates[:-1].sum()-estimates[-1])}
        definitions = ({'unexplained':'xbar_first*(beta_first-beta_ref)+xbar_second*(beta_ref-beta_second)',
            'explained':'(xbar_first-xbar_second)*beta_ref'} if decomposition=='two_fold' else
            {'endowments':'(xbar_first-xbar_second)*beta_second',
             'coefficients':'xbar_second*(beta_first-beta_second)',
             'interaction':'(xbar_first-xbar_second)*(beta_first-beta_second)'})
        metadata.update(group_order=labels,decomposition=decomposition,component_definitions=definitions,
            interval_type='none',confidence_level=None,inference_unit=spec['id'])
        rows = [{'term':name,'estimate':float(estimates[i]),'se':float(se[i]) if i<len(se) else None,
            'unit':spec['unit'],'role':'observed_gap' if name=='gap' else 'decomposition'} for i,name in enumerate(names)]
        result['statistics'] = {f'component.{name}':{'value':float(value),'unit':spec['unit']} for name,value in zip(names,estimates)}
        signatures = {'constructor':str(inspect.signature(OaxacaBlinder)),decomposition:str(inspect.signature(getattr(OaxacaBlinder,decomposition)))}
    result['producer'] = {'entry_point':'research_causal.py run','function':engine,'signature':signatures,'versions':versions}
    metadata.update(engine=engine,sample={'observations':sample['observations'],'included_ids_ref':'sample.included_ids'},
        producer=result['producer'],effective_options=result['effective_options'])
    result['display'] = {'kind':'coefficient','rows':rows,'metadata':metadata}
    result['statistics']['observations'] = {'value':sample['observations'],'unit':'fitted observations'}
    return result


STATSPAI_METHODS = {'network_exposure', 'manski_bounds', 'lee_bounds', 'balke_pearl'}


def _statspai(spec, spec_path):
    """Save official exposure contrasts and identified sets on the adopted sample."""
    import numpy as np
    import pandas as pd
    import scipy
    import research_data
    import warnings
    from importlib import import_module
    from importlib.metadata import distribution

    method = spec['method']; opt = spec['options']; inf = spec['inference']
    required = {
        'network_exposure': {'treatment','adjacency','mapping','p_treat','estimator',
            'contrasts','min_prob','eligible_population'},
        'manski_bounds': {'treatment','y_lower','y_upper','assumption','n_bootstrap','seed'},
        'lee_bounds': {'treatment','selection','monotonicity','n_bootstrap','seed'},
        'balke_pearl': {'treatment','instrument','monotonicity'},
    }[method]
    optional = {'definitions'} | ({'thresholds'} if method == 'network_exposure' else
        {'covariates'} if method == 'lee_bounds' else set())
    if not required <= opt.keys() or set(opt)-required-optional:
        raise ValueError(f'{method} options require {sorted(required)} and accept {sorted(optional)}')
    if spec['regressors'] or spec['endogenous'] or spec['instruments']:
        raise ValueError(f'{method} binds its treatment, instrument and discrete cells in options')
    if not isinstance(opt.get('definitions',{}),dict):
        raise ValueError('options.definitions must contain adopted scientific definitions')
    if method == 'balke_pearl':
        if inf != {'type':'none'}:
            raise ValueError('balke_pearl returns identified-set endpoints with inference.type=none')
        level = None
    else:
        if not isinstance(inf,dict) or set(inf) != {'type','confidence_level'} or inf['type'] != 'official':
            raise ValueError(f'{method} requires official inference and an explicit confidence_level')
        level = inf['confidence_level']
        if isinstance(level,bool) or not isinstance(level,(float,int)) or not 0 < level < 1:
            raise ValueError('confidence_level must be between zero and one')
    if method in ('manski_bounds','lee_bounds'):
        for name, minimum in (('n_bootstrap',2),('seed',0)):
            if isinstance(opt[name],bool) or not isinstance(opt[name],int) or opt[name] < minimum:
                raise ValueError(f'{name} must be an integer at least {minimum}')
    covariates = opt.get('covariates',[])
    if not isinstance(covariates,list) or any(not isinstance(c,str) or not c for c in covariates):
        raise ValueError('covariates must name the adopted discrete pretreatment cells')
    roles = [spec['id'],spec['outcome'],opt['treatment'],*covariates]
    if method == 'lee_bounds': roles.append(opt['selection'])
    if method == 'balke_pearl': roles.append(opt['instrument'])
    if any(not isinstance(c,str) or not c for c in roles) or len(set(roles)) != len(roles):
        raise ValueError('ID, outcome, treatment, selection, instrument and cell columns must be distinct')
    path = Path(spec['data']); path = (path if path.is_absolute() else spec_path.parent/path).resolve()
    data = research_data.read_frame(path, columns=roles, string_columns=[spec['id'],*covariates])
    if len(data) < 2 or data[spec['id']].isna().any() or data[spec['id']].str.strip().eq('').any() or data[spec['id']].duplicated().any():
        raise ValueError('the adopted sample needs at least two distinct nonempty IDs')
    for column in [c for c in roles if c not in [spec['id'],*covariates]]:
        data[column] = pd.to_numeric(data[column],errors='raise')
    binary = [opt['treatment']]
    if method == 'lee_bounds': binary.append(opt['selection'])
    if method == 'balke_pearl': binary.append(opt['instrument'])
    for column in binary:
        if not data[column].isin([0,1]).all():
            raise ValueError(f'{column} must contain observed zero/one values')
    for column in covariates:
        if data[column].isna().any() or data[column].str.strip().eq('').any():
            raise ValueError('discrete pretreatment cells must be observed on the adopted sample')
    selected = data[opt['selection']].eq(1) if method == 'lee_bounds' else pd.Series(True,index=data.index)
    if not np.isfinite(data.loc[selected,spec['outcome']].to_numpy(dtype=float)).all():
        raise ValueError('outcomes must be finite on every observed row of the adopted sample')
    ids = data[spec['id']].astype(str).tolist()
    dist = distribution('StatsPAI')
    versions = {'python':sys.version.split()[0],'numpy':np.__version__,
        'pandas':pd.__version__,'scipy':scipy.__version__,'StatsPAI':dist.version}
    result = {'result_format_version':1,'method':method,'options':deepcopy(opt),'versions':versions,
        'adopted':{k:spec[k] for k in ('population','period','unit','estimand','identification','assignment','inference')},
        'sample':{'id_column':spec['id'],'input_rows':len(data),'input_ids':ids,
            'included_ids':ids,'included_ids_available':True,'observations':len(data),
            'excluded_incomplete_ids':[]},'statistics':{},'diagnostics':{},
        'provenance':{'data_path':str(path),'data_sha256':_hash(path),'spec_path':str(spec_path.resolve()),
            'spec_sha256':_hash(spec_path),'producer_path':str(Path(__file__).resolve()),
            'producer_sha256':_hash(Path(__file__).resolve())}}
    metadata = {**opt.get('definitions',{}),'population':spec['population'],'period':spec['period'],
        'estimand':spec['estimand'],'unit':spec['unit'],'outcome':spec['outcome'],
        'treatment':opt['treatment'],'identification':spec['identification'],
        'assignment':spec['assignment'],'weights':'equal population-unit weights',
        'result_format_version':1}
    args = {'alpha':1-level} if level is not None else {}
    if method == 'network_exposure':
        module = import_module('statspai.interference.network_exposure')
        function = module.network_exposure
        if opt['mapping'] not in ('as4','fraction') or opt['estimator'] not in ('hajek','ht'):
            raise ValueError('network_exposure requires a built-in mapping and hajek or ht')
        if opt['eligible_population'] != 'all_exposures_above_min_prob':
            raise ValueError('network target population is all_exposures_above_min_prob')
        for name, closed in (('p_treat',False),('min_prob',True)):
            v = opt[name]
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) or not (0 <= v < 1 if closed else 0 < v < 1):
                raise ValueError(f'{name} must lie in {"[0,1)" if closed else "(0,1)"}')
        pairs = opt['contrasts']
        if (not isinstance(pairs,list) or not pairs or any(not isinstance(p,list) or len(p)!=2
                or any(not isinstance(h,str) or not h for h in p) or p[0]==p[1] for p in pairs)
                or len({tuple(p) for p in pairs}) != len(pairs)):
            raise ValueError('contrasts must contain distinct ordered pairs of exposure levels')
        thresholds = opt.get('thresholds')
        if opt['mapping'] == 'fraction':
            if (not isinstance(thresholds,list) or not thresholds or any(isinstance(t,bool)
                    or not isinstance(t,(int,float)) or not np.isfinite(t) or not 0<=t<=1 for t in thresholds)
                    or any(a>=b for a,b in zip(thresholds,thresholds[1:]))):
                raise ValueError('fraction mapping needs increasing thresholds in [0,1]')
            args['thresholds'] = tuple(thresholds)
        elif thresholds is not None:
            raise ValueError('thresholds belong to the fraction mapping')
        adjacency_path = Path(opt['adjacency'])
        adjacency_path = (adjacency_path if adjacency_path.is_absolute() else spec_path.parent/adjacency_path).resolve()
        edges = research_data.read_frame(adjacency_path, string_columns=['source','target'])
        if (set(edges) != {'source','target'} or edges.isna().any().any()
                or edges.duplicated(['source','target']).any() or edges['source'].eq(edges['target']).any()
                or not set(edges['source']) <= set(ids) or not set(edges['target']) <= set(ids)):
            raise ValueError('adjacency CSV needs distinct non-self source,target edges among the input IDs')
        positions = {identity:i for i,identity in enumerate(ids)}
        adjacency = np.zeros((len(data),len(data)),dtype=np.int8)
        adjacency[edges['source'].map(positions).to_numpy(dtype=int),
            edges['target'].map(positions).to_numpy(dtype=int)] = 1
        degree = adjacency.sum(axis=1)
        treatment = data[opt['treatment']].to_numpy(dtype=int)
        if opt['mapping'] == 'as4':
            probabilities, levels = module._as4_probabilities(degree,opt['p_treat'])
            exposures = module._as4_mapping(treatment,adjacency)
        else:
            probabilities, levels = module._fraction_probabilities(degree,opt['p_treat'],tuple(thresholds))
            exposures = module._fraction_mapping(treatment,adjacency,tuple(thresholds))
        probability_matrix = np.column_stack([probabilities[h] for h in levels])
        eligible = (probability_matrix > opt['min_prob']).all(axis=1)
        args.update(mapping=opt['mapping'],p_treat=opt['p_treat'],design='bernoulli',
            estimator=opt['estimator'],variance='hac_psd',contrasts=[tuple(p) for p in pairs],min_prob=opt['min_prob'])
        with warnings.catch_warnings(record=True) as returned_warnings:
            warnings.simplefilter('always')
            native = function(data[spec['outcome']].to_numpy(dtype=float),treatment,adjacency,**args)
        if native.n_eligible != int(eligible.sum()) or len(native.contrasts) != len(pairs):
            raise ValueError('each requested contrast needs realized observations in both eligible exposure cells')
        if not np.isfinite(native.contrasts[['estimate','se','ci_lo','ci_hi']].to_numpy(dtype=float)).all():
            raise ArithmeticError('official network contrasts returned nonfinite estimates or inference')
        clean_contrasts = native.contrasts.astype(object).where(pd.notna(native.contrasts),None).to_dict('records')
        rows = [{'term':r['contrast'],'estimate':r['estimate'],'se':r['se'],
            'lower':r['ci_lo'],'upper':r['ci_hi'],'unit':spec['unit'],'role':'exposure_contrast'} for r in clean_contrasts]
        result.update(coefficients={r['contrast']:r['estimate'] for r in clean_contrasts},
            standard_errors={r['contrast']:r['se'] for r in clean_contrasts},
            inference={'type':'official','reference':'normal','variance':'hac_psd','design':'bernoulli',
                'confidence_level':level,'interval_type':'pointwise exposure contrast',
                'confidence_intervals':{r['contrast']:[r['ci_lo'],r['ci_hi']] for r in clean_contrasts},
                'p_values':{r['contrast']:r['pvalue'] for r in clean_contrasts},'covariance_available':False})
        result['sample'].update(included_ids=data.loc[eligible,spec['id']].astype(str).tolist(),
            excluded_ineligible_ids=data.loc[~eligible,spec['id']].astype(str).tolist(),
            observations=native.n_eligible,eligible_population=opt['eligible_population'])
        result['diagnostics'] = {**native.detail,'exposure_levels':levels,
            'exposure_probabilities':{'values':probability_matrix.tolist(),'ids_ref':'sample.input_ids','levels':levels},
            'realized_exposures':exposures.tolist(),
            'exposure_estimates':native.estimates.astype(object).where(pd.notna(native.estimates),None).to_dict('records'),
            'adjacency_path':str(adjacency_path),'adjacency_sha256':_hash(adjacency_path),
            'edge_direction':'source outcome exposed to target treatment'}
        metadata.update(inference=result['inference'],confidence_level=level,interval_type='pointwise exposure contrast',
            mapping=opt['mapping'],estimator=opt['estimator'],p_treat=opt['p_treat'],
            min_prob=opt['min_prob'],eligible_population=opt['eligible_population'])
        for row in rows:
            for prefix, field in [('coefficient','estimate'),('standard_error','se'),
                    (f'confidence_{100*level:g}_lower','lower'),(f'confidence_{100*level:g}_upper','upper')]:
                result['statistics'][f'{prefix}.{row["term"]}'] = {'value':row[field],'unit':spec['unit']}
        display_kind = 'coefficient'
    else:
        module = import_module('statspai.bounds.balke_pearl' if method == 'balke_pearl' else 'statspai.bounds.lee_manski')
        function = getattr(module,method)
        args.update(y=spec['outcome'],treat=opt['treatment'])
        if method == 'manski_bounds':
            support = [opt['y_lower'],opt['y_upper']]
            if (any(isinstance(x,bool) or not isinstance(x,(int,float)) or not np.isfinite(x) for x in support)
                    or support[0] >= support[1] or not data[spec['outcome']].between(*support).all()):
                raise ValueError('Manski bounds require finite adopted population support containing all observed outcomes')
            if opt['assumption'] not in ('none','mtr','mts','mts_mtr'):
                raise ValueError('Manski assumption must be none, mtr, mts or mts_mtr')
            args.update(y_lower=support[0],y_upper=support[1],assumption=opt['assumption'])
        elif method == 'lee_bounds':
            if opt['monotonicity'] not in ('increasing','decreasing'):
                raise ValueError('Lee bounds require an adopted increasing or decreasing selection monotonicity')
            direction = 1 if opt['monotonicity'] == 'increasing' else -1
            groups = [(None,data)] if not covariates else data.groupby(covariates,observed=True,sort=False)
            for _, cell in groups:
                rates = cell.groupby(opt['treatment'])[opt['selection']].mean()
                if set(rates.index) != {0,1} or (rates<=0).any():
                    raise ValueError('each adopted Lee cell needs both treatment arms and positive retention')
                if direction*(rates[1]-rates[0]) < 0:
                    raise ValueError('observed cell retention conflicts with the adopted selection monotonicity direction')
            args.update(selection=opt['selection'],covariates=covariates or None,se_method='bootstrap',trimming='exact')
            result['sample'].update(observed_outcome_ids=data.loc[selected,spec['id']].astype(str).tolist(),
                unobserved_outcome_ids=data.loc[~selected,spec['id']].astype(str).tolist(),
                observed_outcomes=int(selected.sum()),target_population='always-observed principal stratum')
        else:
            if not data[spec['outcome']].isin([0,1]).all() or set(data[opt['instrument']].unique()) != {0,1}:
                raise ValueError('Balke-Pearl requires binary outcomes and both instrument arms')
            if opt['monotonicity'] not in ('none','increasing','decreasing'):
                raise ValueError('Balke-Pearl monotonicity must be none, increasing or decreasing')
            args.update(instrument=opt['instrument'])
        if method in ('manski_bounds','lee_bounds'):
            args.update(n_bootstrap=opt['n_bootstrap'],random_state=opt['seed'])
        with warnings.catch_warnings(record=True) as returned_warnings:
            warnings.simplefilter('always')
            native = function(data,**args)
        if method == 'balke_pearl':
            if opt['monotonicity'] == 'none':
                lower, upper = native.lower,native.upper
            else:
                z_hi = 1 if opt['monotonicity'] == 'increasing' else 0
                if native.detail['z_hi'] != z_hi:
                    raise ValueError('the official first-stage direction conflicts with the adopted instrument monotonicity')
                lower, upper = native.lower_monotone,native.upper_monotone
            result['diagnostics'] = {**native.detail,'joint_probabilities':
                native.joint_probs.rename_axis('cell').reset_index().to_dict('records')}
            result['inference'] = {'type':'none','confidence_level':None,'interval_type':'none'}
            restrictions = {'monotonicity':opt['monotonicity'],'outcome_support':[0,1],
                'instrument':opt['instrument'],'instrument_exogeneity':spec['identification']}
        else:
            model_info = dict(native.model_info)
            if isinstance(model_info.get('cells'),pd.DataFrame):
                model_info['cells'] = model_info['cells'].to_dict('records')
            lower, upper = model_info['lower_bound'],model_info['upper_bound']
            if not np.isfinite([lower,upper,*native.ci]).all():
                raise ArithmeticError('the official bounds or their requested inference are nonfinite')
            target = 'parameter' if method == 'lee_bounds' else 'identified_set'
            procedure = ('Imbens-Manski critical value with native row-bootstrap endpoint standard errors'
                if method == 'lee_bounds' else 'two-sided normal endpoint expansion with native row-bootstrap standard errors')
            result['confidence_region'] = {'lower':float(native.ci[0]),'upper':float(native.ci[1]),
                'target':target,'level':level,'procedure':procedure}
            result['inference'] = {'type':'official','confidence_level':level,'target':target,
                'procedure':procedure,'resampling_unit':spec['id'],'n_bootstrap':opt['n_bootstrap'],'seed':opt['seed']}
            result['diagnostics'] = model_info
            restrictions = ({'outcome_support':support,'assumption':opt['assumption']} if method == 'manski_bounds' else
                {'selection_monotonicity':opt['monotonicity'],'selection':opt['selection'],
                 'target_population':'always-observed principal stratum','covariates':covariates,'trimming':'exact'})
        if not np.isfinite([lower,upper]).all():
            raise ArithmeticError('the official identified-set endpoints are nonfinite')
        result['identified_set'] = {'lower':float(lower),'upper':float(upper),'target':spec['estimand'],
            'population':spec['population'],'unit':spec['unit'],'restrictions':restrictions,
            'set_type':'empty' if lower>upper else 'point' if lower==upper else 'interval'}
        region = result.get('confidence_region',{})
        rows = [{'term':spec['estimand'],'lower':float(lower),'upper':float(upper),
            'confidence_lower':region.get('lower'),'confidence_upper':region.get('upper'),
            'confidence_target':region.get('target'),'confidence_level':level,
            'set_type':result['identified_set']['set_type'],'unit':spec['unit']}]
        result['statistics'].update({'bounds.lower':{'value':float(lower),'unit':spec['unit']},
            'bounds.upper':{'value':float(upper),'unit':spec['unit']}})
        if region:
            for side in ('lower','upper'):
                result['statistics'][f'confidence_region.{side}'] = {'value':region[side],'unit':spec['unit']}
        metadata.update(identified_set=result['identified_set'],inference=result['inference'],
            confidence_level=level,confidence_target=region.get('target'),interval_type=region.get('procedure','none'))
        display_kind = 'identified_set'
    engine = 'statspai.'+method
    source_path = Path(module.__file__).resolve()
    result['diagnostics']['native_warnings'] = [str(w.message) for w in returned_warnings]
    result['effective_options'] = args
    result['engine'] = engine
    result['producer'] = {'entry_point':'research_causal.py run','function':engine,
        'signature':str(inspect.signature(function)),'versions':versions,
        'source_path':str(source_path),'source_sha256':_hash(source_path),
        'distribution_source':json.loads(dist.read_text('direct_url.json') or 'null')}
    metadata.update(engine=engine,producer=result['producer'],effective_options=result['effective_options'],
        sample={'observations':result['sample']['observations'],'included_ids_ref':'sample.included_ids'})
    result['display'] = {'kind':display_kind,'rows':rows,'metadata':metadata}
    result['statistics']['observations'] = {'value':result['sample']['observations'],
        'unit':'eligible population units' if method == 'network_exposure' else 'input population units'}
    return result


def _inference_extensions(spec, spec_path):
    """Execute official inference and sensitivity functions on declared data or saved quantities."""
    import numpy as np
    import pandas as pd
    import scipy
    import statsmodels
    import statsmodels.api as sm
    import research_data
    import warnings
    from importlib import import_module
    from importlib.metadata import distribution
    from research_evidence import read_json, lookup
    from statsmodels.stats.multitest import multipletests

    method = spec['method']; opt = spec['options']; inf = spec['inference']
    required = set(INFERENCE_METHODS[method]['required_options'])
    if method == 'sensitivity_cinelli' and opt.get('input','data') == 'data':
        required = {'treatment'}
    optional = {'definitions'} | {
        'shift_share_inference': {'weights','cluster'},
        'sensitivity_oster': {'input','treatment','summary','absorb','absorb_controls','baseline_result','term'},
        'sensitivity_cinelli': {'input','treatment','benchmark','kd','ky','term','df_key','se_key','covariance','q'},
        'sensitivity_evalue': {'input','rare','sd','delta','true'},
        'romano_wolf': {'cluster'},
        'specification_curve': {'fe','subsets','cluster'},
        'holm': set(),
        'spatial_conley': {'time','lag_cutoff','time_kernel','panel_unit','lag_cutoff_cross'},
    }[method]
    if not required <= opt.keys() or set(opt)-required-optional:
        raise ValueError(f'{method} options require {sorted(required)} and accept {sorted(optional)}')
    if not isinstance(opt.get('definitions',{}),dict):
        raise ValueError('definitions must contain adopted scientific definitions')
    if not isinstance(inf,dict) or inf.get('type') != 'official' or set(inf)-{'type','confidence_level','alpha'}:
        raise ValueError('inference requires type=official and confidence_level or alpha')
    level = inf.get('confidence_level',1-inf.get('alpha',.05))
    if isinstance(level,bool) or not isinstance(level,(float,int)) or not 0 < level < 1:
        raise ValueError('confidence_level must lie between zero and one')
    alpha = 1-level
    if 'alpha' in inf and (isinstance(inf['alpha'],bool) or not np.isclose(alpha,inf['alpha'])):
        raise ValueError('alpha and confidence_level must agree')
    input_kind = opt.get('input','saved_result' if method in ('sensitivity_evalue','holm') else 'data')
    if input_kind not in ('data','saved_result'):
        raise ValueError('input must be data or saved_result')
    saved = input_kind == 'saved_result'
    if method in ('sensitivity_evalue','holm') and not saved:
        raise ValueError(f'{method} consumes saved_result inputs')
    if method not in ('sensitivity_oster','sensitivity_cinelli','sensitivity_evalue','holm') and saved:
        raise ValueError(f'{method} consumes analysis data')
    if method == 'shift_share_inference':
        if len(spec['endogenous']) != 1 or spec['instruments']:
            raise ValueError('shift_share_inference requires one endogenous column and no input instruments')
        if opt['identification_basis'] not in ('shocks','shares'):
            raise ValueError('identification_basis must be shocks or shares')
        if any(not isinstance(opt['definitions'].get(k),str) or not opt['definitions'][k].strip()
                for k in ('baseline_period','share_population','identifying_variation')):
            raise ValueError('shift-share definitions require baseline_period, share_population and identifying_variation')
        if opt['identification_basis'] == 'shocks' and opt['definitions'].get('shock_dependence') != 'independent':
            raise ValueError('AKM/BHJ requires definitions.shock_dependence=independent for the supplied shock units')
    elif spec['endogenous'] or spec['instruments']:
        raise ValueError('these inference extensions require empty endogenous and instruments')
    family = opt.get('family')
    if family is not None:
        if (not isinstance(family,dict) or not isinstance(family.get('name'),str) or not family['name'].strip()
                or family.get('status') not in ('prespecified','exploratory','post_selection')):
            raise ValueError('family requires name and status=prespecified, exploratory or post_selection')
    path = Path(spec['data']); path = (path if path.is_absolute() else spec_path.parent/path).resolve()
    dist = None
    versions = {'python':sys.version.split()[0],'numpy':np.__version__,'pandas':pd.__version__,
        'scipy':scipy.__version__,'statsmodels':statsmodels.__version__}
    if method != 'holm':
        from statspai.core.results import _to_jsonable
        dist = distribution('StatsPAI'); versions['StatsPAI'] = dist.version
    result = {'result_format_version':1,'method':method,'options':deepcopy(opt),'versions':versions,
        'adopted':{k:spec[k] for k in ('population','period','unit','estimand','identification','assignment','inference')},
        'statistics':{},'diagnostics':{},'inference':{'type':'official','confidence_level':level},
        'provenance':{'data_path':str(path),'data_sha256':_hash(path),'spec_path':str(spec_path.resolve()),
            'spec_sha256':_hash(spec_path),'producer_path':str(Path(__file__).resolve()),
            'producer_sha256':_hash(Path(__file__).resolve())}}
    metadata = {**opt.get('definitions',{}),**result['adopted'],'result_format_version':1}
    functions = []; rows = []; extra_displays = {}; args = {}; source = None
    if saved:
        source = read_json(path.read_bytes(),f'saved inference result {path}')
        if not isinstance(source,dict):
            raise ValueError('saved inference input must be a result object')
        result['sample'] = deepcopy(source.get('sample',{}))
        result['source_result'] = {'path':str(path),'sha256':_hash(path),'method':source.get('method'),
            'engine':source.get('engine'),'adopted':source.get('adopted',source.get('definition'))}
        if method != 'holm' and not result['sample'].get('included_ids'):
            raise ValueError('saved sensitivity requires the fitted sample identities')
    else:
        controls = spec['regressors']
        treatment = spec['endogenous'][0] if method == 'shift_share_inference' else opt.get('treatment')
        if method in ('sensitivity_oster','sensitivity_cinelli') and not treatment:
            raise ValueError('data sensitivity requires treatment')
        role_columns = [spec['id'],spec['outcome'],*controls]
        if treatment: role_columns.append(treatment)
        text_columns = [spec['id']]
        if opt.get('cluster'): role_columns.append(opt['cluster']); text_columns.append(opt['cluster'])
        if method == 'shift_share_inference':
            shares = opt['shares']; shocks = opt['shocks']
            if (not isinstance(shares,list) or len(shares)<2 or len(set(shares))!=len(shares)
                    or not isinstance(shocks,list) or len(shares)!=len(shocks)
                    or not np.isfinite(np.asarray(shocks,dtype=float)).all()):
                raise ValueError('shares and finite shocks must have matching ordered entries')
            role_columns += shares
            if opt.get('weights'): role_columns.append(opt['weights'])
        elif method == 'romano_wolf':
            outcomes = opt['outcomes']
            if not isinstance(outcomes,list) or len(outcomes)<2 or len(set(outcomes))!=len(outcomes) or spec['outcome'] not in outcomes:
                raise ValueError('outcomes must declare a distinct multiple-outcome family containing outcome')
            if set(outcomes)&{treatment,*controls}:
                raise ValueError('outcome-family columns must be distinct from treatment and controls')
            role_columns += outcomes
            if (isinstance(opt['n_boot'],bool) or not isinstance(opt['n_boot'],int) or opt['n_boot']<2
                    or isinstance(opt['seed'],bool) or not isinstance(opt['seed'],int) or opt['seed']<0):
                raise ValueError('n_boot must be at least two and seed a nonnegative integer')
        elif method == 'specification_curve':
            control_sets = opt['controls']; fe_sets = opt.get('fe',[[]]); subsets = opt.get('subsets',{'Full sample':None})
            for name,sets in (('controls',control_sets),('fe',fe_sets)):
                if (not isinstance(sets,list) or not sets or any(not isinstance(s,list) or len(set(s))!=len(s)
                        or any(not isinstance(c,str) or not c for c in s) for s in sets)):
                    raise ValueError(f'{name} must contain explicit lists of distinct column names')
            if not isinstance(subsets,dict) or not subsets or any(v is not None and not isinstance(v,str) for v in subsets.values()):
                raise ValueError('subsets maps labels to zero/one inclusion columns or null for the full sample')
            se_types = opt['se_types']
            if (not isinstance(se_types,list) or not se_types or len(set(se_types))!=len(se_types)
                    or set(se_types)-{'nonrobust','hc1','cluster'} or ('cluster' in se_types) != bool(opt.get('cluster'))):
                raise ValueError('se_types must explicitly list nonrobust, hc1 or cluster with its cluster column')
            union_controls = list(dict.fromkeys(c for s in control_sets for c in s))
            if set(controls) != set(union_controls):
                raise ValueError('regressors must equal the union of the declared control sets')
            role_columns += [c for s in fe_sets for c in s]+[c for c in subsets.values() if c]
            text_columns += [c for s in fe_sets for c in s]
        elif method == 'sensitivity_oster':
            for name in ('absorb','absorb_controls'):
                values = opt.get(name,[])
                if not isinstance(values,list) or any(not isinstance(c,str) or not c for c in values):
                    raise ValueError(f'{name} must list existing fixed-effect columns')
                role_columns += values; text_columns += values
        elif method == 'spatial_conley':
            role_columns += [opt['lat'],opt['lon']]
            if ('time' in opt) != ('panel_unit' in opt) or ('time' in opt) != ('lag_cutoff' in opt):
                raise ValueError('spatial-temporal Conley requires time, panel_unit and lag_cutoff together')
            if 'time' in opt: role_columns += [opt['time'],opt.get('panel_unit')]; text_columns.append(opt.get('panel_unit'))
        if any(not isinstance(c,str) or not c for c in role_columns):
            raise ValueError('all input bindings must name columns')
        if spec['id'] in role_columns[1:] or spec['outcome'] in controls or treatment in controls:
            raise ValueError('ID, outcome, treatment and control roles must be distinct')
        role_columns = list(dict.fromkeys(role_columns)); text_columns = list(dict.fromkeys(text_columns))
        data = research_data.read_frame(path,columns=role_columns,string_columns=text_columns)
        if (len(data)<2 or data[spec['id']].isna().any() or data[spec['id']].str.strip().eq('').any()
                or data[spec['id']].duplicated().any()):
            raise ValueError('analysis data require distinct nonempty row IDs')
        for c in set(role_columns)-set(text_columns):
            data[c] = pd.to_numeric(data[c],errors='raise')
            if np.isinf(data[c].to_numpy(dtype=float)).any(): raise ValueError(f'{c} contains infinite values')
        all_ids = data[spec['id']].tolist()
        # The multiple-outcome and specification owners select their own declared samples.
        if method in ('romano_wolf','specification_curve'):
            d = data.copy(); excluded = []
        else:
            complete = data.notna().all(axis=1)
            excluded = data.loc[~complete,spec['id']].tolist(); d = data.loc[complete].copy()
            if len(d)<2: raise ValueError('the declared complete-case sample has fewer than two observations')
        d = d.reset_index(drop=True)
        result['sample'] = {'id_column':spec['id'],'input_rows':len(data),'input_ids':all_ids,
            'included_ids':d[spec['id']].tolist(),'included_ids_available':True,
            'excluded_incomplete_ids':excluded,'observations':len(d)}

    with warnings.catch_warnings(record=True) as returned_warnings:
        warnings.simplefilter('always')
        if method == 'shift_share_inference':
            module = import_module('statspai.bartik.adao_correction')
            bartik = import_module('statspai.bartik.shift_share').bartik
            functions = [bartik]
            share_frame = d[opt['shares']]; shock_series = pd.Series(opt['shocks'],index=opt['shares'],dtype=float)
            if (share_frame.to_numpy()<0).any() or not np.allclose(share_frame.sum(axis=1),1,atol=1e-8,rtol=0):
                raise ValueError('this shift-share contract requires nonnegative shares summing to one')
            args = {'y':spec['outcome'],'x':treatment,'controls':controls,'cluster':opt.get('cluster'),
                'alpha':alpha,'weights':opt.get('weights'),'identification_basis':opt['identification_basis']}
            decomposition = bartik(d,y=spec['outcome'],endog=treatment,shares=share_frame,shocks=shock_series,
                covariates=controls,leave_one_out=False,weights=opt.get('weights'),alpha=alpha)
            if opt['identification_basis']=='shocks':
                functions.append(module.ssaggregate)
                native = module.ssaggregate(d,shares=share_frame,shocks=shock_series,
                    **{k:v for k,v in args.items() if k!='identification_basis'})
                ci = native.conf_int(alpha=alpha).loc[treatment]
                result['diagnostics'] = _to_jsonable(native.diagnostics)
                shock_data = native.data_info['shock_data']
                result['diagnostics']['shock_data'] = _to_jsonable(shock_data.to_dict('records'))
                label = f'{100*level:g}%'; kind = native.model_info['akm0_ci_type']
                lo = native.diagnostics[f'CI lower (AKM0, {label})']; hi = native.diagnostics[f'CI upper (AKM0, {label})']
                if kind == 'bounded': intervals = [{'lower':float(lo),'upper':float(hi)}]
                elif kind == 'union': intervals = [{'lower':None,'upper':float(hi)},{'lower':float(lo),'upper':None}]
                elif kind == 'real_line': intervals = [{'lower':None,'upper':None}]
                elif kind == 'empty': intervals = []
                else: raise ValueError(f'unsupported native AKM0 set kind: {kind}')
                result['inference'].update(procedure='AKM',reference='normal',covariance_available=False,
                    akm0_confidence_set={'set_type':kind,'confidence_level':level,'intervals':intervals})
                extra_displays['akm0'] = {'kind':'iv_confidence_set','rows':[{'term':treatment,**v,
                    'lower_unbounded':v['lower'] is None,'upper_unbounded':v['upper'] is None,'set_type':kind} for v in intervals],
                    'metadata':{'interval_type':'AKM0 null-imposed confidence set','confidence_level':level}}
                if not intervals: extra_displays['akm0']['rows'] = [{'term':treatment,'set_type':'empty'}]
                extra_displays['bhj'] = {'kind':'coefficient','rows':[{'term':treatment,
                    'estimate':float(native.diagnostics['beta (BHJ shock-level)']),
                    'se':float(native.diagnostics['SE (BHJ shock-level, HC0)']),'unit':spec['unit']}],
                    'metadata':{'interval_type':'none','confidence_level':None,'procedure':'BHJ shock-level IV; native HC0 SE'}}
            elif opt.get('cluster'):
                import linearmodels
                from linearmodels.iv import IV2SLS
                functions += [IV2SLS,IV2SLS.fit]; versions['linearmodels'] = linearmodels.__version__
                native = IV2SLS(d[spec['outcome']],sm.add_constant(d[controls],has_constant='add'),d[[treatment]],
                    pd.DataFrame({'shift_share':share_frame.to_numpy()@shock_series.to_numpy()},index=d.index),
                    weights=d[opt['weights']] if opt.get('weights') else None).fit(
                        cov_type='clustered',clusters=d[opt['cluster']],debiased=True)
                ci = native.conf_int(level=level).loc[treatment]
                result['covariance'] = {treatment:{treatment:float(native.cov.loc[treatment,treatment])}}
                result['diagnostics'] = {'first_stage':_to_jsonable(native.first_stage.diagnostics.to_dict('index')),
                    'native_coefficients':native.params.to_dict(),'native_covariance':native.cov.to_dict('index')}
                result['inference'].update(procedure='location-clustered 2SLS',reference='Student t',
                    degrees_of_freedom=int(native.df_resid),cluster=opt['cluster'],
                    cluster_count=int(d[opt['cluster']].nunique()),covariance_available=True)
            else:
                native = decomposition; ci = native.conf_int(alpha=alpha).loc[treatment]
                result['diagnostics'] = _to_jsonable(native.diagnostics)
                result['inference'].update(procedure='location HC1 2SLS',reference='Student t',
                    degrees_of_freedom=int(native.data_info['df_resid']),covariance_available=False)
            rows = [{'term':treatment,'estimate':float(native.params[treatment]),'se':float(native.std_errors[treatment]),
                'p_value':float(native.pvalues[treatment]),'ci_low':float(ci.iloc[0]),'ci_high':float(ci.iloc[1]),'unit':spec['unit']}]
            weights = d[opt['weights']].to_numpy(dtype=float) if opt.get('weights') else np.ones(len(d))
            exposures = (share_frame.to_numpy()*weights[:,None]).sum(axis=0)/weights.sum()
            result['diagnostics']['rotemberg_weights'] = _to_jsonable(decomposition.model_info['rotemberg_weights'].to_dict('records'))
            result['diagnostics'].update(shock_count=len(exposures),shock_exposure_weights=dict(zip(opt['shares'],exposures.tolist())),
                effective_shock_count=float(1/np.square(exposures).sum()),
                location_share_concentration=[{'id':i,'hhi':float(h)} for i,h in
                    zip(d[spec['id']],np.square(share_frame.to_numpy()).sum(axis=1))])
            result['inference'].update(identification_basis=opt['identification_basis'],
                shock_inference_selected=opt['identification_basis']=='shocks')
            args = {'identification_basis':opt['identification_basis'],'shares':opt['shares'],'shocks':opt['shocks'],
                'bartik':{'y':spec['outcome'],'endog':treatment,'covariates':controls,'leave_one_out':False,
                    'weights':opt.get('weights'),'robust':'hc1','alpha':alpha},
                'selected_inference':{**result['inference'],'weights':opt.get('weights'),'cluster':opt.get('cluster')}}
            extra_displays['rotemberg_weights'] = {'kind':'coefficient','rows':[{'term':str(v['industry']),
                'estimate':v['weight'],'unit':'Rotemberg weight','shock':v['shock'],'beta':v['beta']}
                for v in result['diagnostics']['rotemberg_weights']],
                'metadata':{'interval_type':'none','confidence_level':None,'unit':'Rotemberg weight'}}
        elif method == 'sensitivity_oster':
            function = import_module('statspai.diagnostics.sensitivity').oster_bounds; functions = [function]
            args = {'r_max':opt['r_max'],'delta':opt['delta'],'alpha':alpha}
            if saved:
                if 'baseline_result' in opt:
                    if 'term' not in opt or 'summary' in opt:
                        raise ValueError('baseline_result requires term and uses the saved OLS sensitivity moments')
                    baseline_path = Path(opt['baseline_result'])
                    baseline_path = (baseline_path if baseline_path.is_absolute() else spec_path.parent/baseline_path).resolve()
                    baseline = read_json(baseline_path.read_bytes(),'saved baseline OLS result')
                    full = lookup(source,['diagnostics','ols_sensitivity'],'full OLS sensitivity')
                    short = lookup(baseline,['diagnostics','ols_sensitivity'],'baseline OLS sensitivity')
                    if (source.get('engine')!='statsmodels.OLS' or baseline.get('engine')!='statsmodels.OLS'
                            or source['sample']['included_ids']!=baseline['sample']['included_ids']
                            or source['inputs']['data_sha256']!=baseline['inputs']['data_sha256']
                            or source.get('definition',{}).get('outcome')!=baseline.get('definition',{}).get('outcome')
                            or not source.get('design',{}).get('constant') or not baseline.get('design',{}).get('constant')
                            or not set(baseline['design']['exog'])<=set(source['design']['exog'])):
                        raise ValueError('Oster requires nested intercept OLS models on the same outcome, source and ordered sample')
                    term = opt['term']
                    summary = {'beta_short':short['terms'][term]['estimate'],'r2_short':short['r_squared'],
                        'beta_long':full['terms'][term]['estimate'],'r2_long':full['r_squared'],
                        'sigma_yy':full['outcome_variance'],'sigma_xx':short['terms'][term]['residual_regressor_variance'],
                        't_x':full['terms'][term]['residual_regressor_variance']}
                    result['source_result']['baseline'] = {'path':str(baseline_path),'sha256':_hash(baseline_path)}
                elif 'summary' in opt:
                    keys = {'beta_short','r2_short','beta_long','r2_long','sigma_yy','sigma_xx','t_x'}
                    if not isinstance(opt['summary'],dict) or set(opt['summary']) != keys:
                        raise ValueError('summary must bind beta_short, r2_short, beta_long, r2_long, sigma_yy, sigma_xx and t_x')
                    summary = {k:lookup(source,v,f'Oster {k}') for k,v in opt['summary'].items()}
                else:
                    moments = lookup(source,['diagnostics','oster_inputs'],'saved Oster inputs')
                    summary = {new:moments[old] for new,old in {'beta_short':'beta_o','r2_short':'r_o',
                        'beta_long':'beta_t','r2_long':'r_t','sigma_yy':'sigma_yy','sigma_xx':'sigma_xx','t_x':'t_x'}.items()}
                if not np.isfinite(list(summary.values())).all(): raise ValueError('saved Oster inputs must be finite')
                args.update({k:summary[k] for k in ('beta_short','r2_short','beta_long','r2_long')},
                    moments={k:summary[k] for k in ('sigma_yy','sigma_xx','t_x')})
                native = function(**args)
            else:
                args.update(y=spec['outcome'],treat=treatment,controls=controls,
                    absorb=opt.get('absorb'),absorb_controls=opt.get('absorb_controls'))
                native = function(data=d,**args)
            if isinstance(opt['r_max'],(int,float)) and not np.isclose(native['r_max'],opt['r_max']):
                raise ValueError('r_max must exceed the fitted long-model R-squared and be at most one')
            if not np.isfinite([native['beta_adjusted'],*native['identified_set']]).all():
                raise ArithmeticError('the official Oster coefficient or identified-set endpoints are nonfinite')
            result['diagnostics'] = {k:_to_jsonable(v) for k,v in native.items() if k not in ('interpretation','robust')}
            result['diagnostics']['oster_inputs'] = native['inputs']
            result['diagnostics']['delta_star_status'] = 'unbounded' if np.isinf(native['delta_star']) else 'finite'
            for name,unit in (('beta_adjusted',spec['unit']),('delta_star','relative selection'),('r_max','R-squared')):
                rows.append({'term':name,'estimate':_to_jsonable(native[name]),'unit':unit})
            result['identified_set'] = {'lower':float(native['identified_set'][0]),'upper':float(native['identified_set'][1]),
                'target':'coefficient under the declared proportional-selection range','unit':spec['unit']}
            result['inference'].update(procedure='Oster exact coefficient-stability calculation',interval_type='identified set')
        elif method == 'sensitivity_cinelli':
            module = import_module('statspai.diagnostics.sensemakr')
            if saved:
                if 'term' not in opt:
                    raise ValueError('saved Cinelli sensitivity requires term')
                term = opt['term']; classical = source.get('diagnostics',{}).get('ols_sensitivity')
                if classical:
                    if classical.get('covariance_basis')!='classical_ols' or classical['sample_ids']!=source['sample']['included_ids']:
                        raise ValueError('classical OLS moments must match the saved fitted sample')
                    se_key = opt.get('se_key',['diagnostics','ols_sensitivity','classical_standard_errors',term])
                    df_key = opt.get('df_key',['diagnostics','ols_sensitivity','residual_df'])
                else:
                    if (not {'df_key','covariance'} <= opt.keys() or opt['covariance']!='classical_ols'
                            or source.get('covariance_type') not in (None,'nonrobust','homoskedastic','classical')):
                        raise ValueError('saved Cinelli sensitivity requires classical OLS SEs and residual df')
                    se_key = opt.get('se_key',['standard_errors',term]); df_key = opt['df_key']
                estimate = float(source['coefficients'][term]); se = float(lookup(source,se_key,'classical OLS standard error'))
                dof = lookup(source,df_key,'OLS residual degrees of freedom'); q = opt.get('q',1.)
                if (not np.isfinite([estimate,se,dof,q]).all() or se<=0 or dof<=1 or int(dof)!=dof or q<0):
                    raise ValueError('Cinelli inputs require finite estimate, positive SE, integer residual df above one and nonnegative q')
                if dist.version != '1.43.1': raise ValueError('saved Cinelli sensitivity requires the pinned StatsPAI 1.43.1 helper')
                function = module._robustness_value; functions = [function]
                t_value = estimate/se
                native = {'beta_treat':estimate,'se_treat':se,'t_treat':t_value,'df_resid':int(dof),
                    'partial_r2_yd':t_value*t_value/(t_value*t_value+dof),
                    'rv_q':function(t_value,int(dof),q=q,alpha=1.),
                    'rv_qa':function(t_value,int(dof),q=q,alpha=alpha)}
                args = {'t_statistic':t_value,'dof':int(dof),'q':q,'alpha':alpha,'covariance':'classical_ols',
                    'se_key':se_key,'df_key':df_key}
            else:
                if 'q' in opt and opt['q'] != 1: raise ValueError('native data sensemakr uses q=1')
                function = module.sensemakr; functions = [function]
                args = {'y':spec['outcome'],'treat':treatment,'controls':controls,'alpha':alpha,
                    **{k:opt[k] for k in ('benchmark','kd','ky') if k in opt}}
                native = function(d,**args)
                result['diagnostics']['benchmark_table'] = _to_jsonable(native['benchmark_table'].to_dict('records'))
            result['diagnostics'].update({k:_to_jsonable(v) for k,v in native.items()
                if k not in ('interpretation','robustness','benchmark_table')})
            rows = [{'term':k,'estimate':float(native[k]),'unit':'partial R-squared'} for k in ('partial_r2_yd','rv_q','rv_qa')]
            result['inference'].update(procedure='Cinelli-Hazlett partial R-squared',covariance='classical OLS')
        elif method == 'sensitivity_evalue':
            function = import_module('statspai.diagnostics.evalue').evalue; functions = [function]
            term = opt['term']; estimate = float(source['coefficients'][term]); scale = opt['coefficient_scale']
            if scale not in ('identity','log'): raise ValueError('coefficient_scale must be identity or log')
            if scale=='log' and opt['measure'] not in ('RR','OR','HR'):
                raise ValueError('log coefficient_scale requires RR, OR or HR')
            source_inference = source.get('inference',{})
            ci = source_inference.get('confidence_intervals',source_inference.get('confidence_intervals_95',{})).get(term)
            if ci is not None:
                source_level = source_inference.get('confidence_level',.95 if 'confidence_intervals_95' in source_inference else None)
                if source_level is None or not np.isclose(level,source_level):
                    raise ValueError('the saved confidence interval must use the requested level')
            args = {'estimate':float(np.exp(estimate)) if scale=='log' else estimate,'measure':opt['measure'],'alpha':alpha,
                **{k:opt[k] for k in ('rare','sd','delta','true') if k in opt}}
            if opt['measure']=='OLS' and 'sd' not in args:
                args['sd'] = float(np.sqrt(lookup(source,['diagnostics','ols_sensitivity','outcome_variance'],'saved outcome variance')))
            if ci is not None: args['ci'] = np.exp(ci).tolist() if scale=='log' else ci
            elif term in source.get('standard_errors',{}):
                if scale=='identity' and opt['measure'] in ('RR','OR','HR'):
                    raise ValueError('a ratio-scale saved coefficient requires its saved confidence interval')
                args['se'] = source['standard_errors'][term]
            native = function(**args)
            result['diagnostics'] = {k:_to_jsonable(v) for k,v in native.items() if k!='interpretation'}
            rows = [{'term':k,'estimate':native[k],'unit':'risk-ratio strength'} for k in ('evalue_estimate','evalue_ci') if native[k] is not None]
            result['inference'].update(procedure='E-value',source_term=term,source_scale=scale)
        elif method == 'romano_wolf':
            function = import_module('statspai.mht.romano_wolf').romano_wolf; functions = [function]
            args = {'y':opt['outcomes'],'x':opt['treatment'],'controls':controls,'cluster':opt.get('cluster'),
                'n_boot':opt['n_boot'],'seed':opt['seed'],'alpha':alpha}
            native = function(d,**args)
            table = native.table
            result['diagnostics']['outcome_table'] = _to_jsonable(table.to_dict('records'))
            base = [opt['treatment'],*controls,*([opt['cluster']] if opt.get('cluster') else [])]
            members = {y:d.loc[d[[*base,y]].notna().all(axis=1),spec['id']].tolist() for y in opt['outcomes']}
            result['sample'].update(included_ids_available=False,observations=None,by_outcome=members)
            result['sample'].pop('included_ids')
            rows = [{'term':str(v['outcome']),'estimate':float(v['coef']),'se':float(v['se']),
                'p_value':float(v['p_rw']),'p_raw':float(v['p_value']),'p_holm':float(v['p_holm']),
                'n':int(v['n_obs']),'unit':opt.get('definitions',{}).get('outcome_units',{}).get(v['outcome'],spec['unit'])}
                for v in table.to_dict('records')]
            result['inference'].update(procedure='Romano-Wolf stepdown',family=family,family_size=len(opt['outcomes']),
                resampling_unit=opt.get('cluster',spec['id']),n_boot=opt['n_boot'],seed=opt['seed'],selection_adjusted=False)
        elif method == 'specification_curve':
            function = import_module('statspai.robustness.spec_curve').spec_curve; functions = [function,multipletests]
            masks = {}
            for label,column in subsets.items():
                if column is not None and not d[column].isin([0,1]).all():
                    raise ValueError('subset columns must contain observed zero/one values')
                masks[label] = None if column is None else d[column].eq(1)
            family_size = len(control_sets)*len(fe_sets)*len(se_types)*len(subsets)
            control_labels = {', '.join(v) if v else '(none)':v for v in control_sets}
            fe_labels = {', '.join(v) if v else '(none)':v for v in fe_sets}
            if len(control_labels)!=len(control_sets) or len(fe_labels)!=len(fe_sets):
                raise ValueError('control and fixed-effect sets must have distinct native specification labels')
            args = {'y':spec['outcome'],'x':opt['treatment'],'controls':control_sets,'se_types':se_types,
                'cluster_var':opt.get('cluster'),'fe':fe_sets,'alpha':alpha/family_size}
            native = function(d,subsets=masks,**args)
            if native.n_specs != family_size:
                raise ArithmeticError(f'the declared family has {family_size} specifications; the official function estimated {native.n_specs}')
            table = native.results_df.copy()
            table['p_holm'] = multipletests(table['pvalue'].to_numpy(),alpha=alpha,method='holm')[1]
            result['diagnostics']['specification_table'] = _to_jsonable(table.to_dict('records'))
            result['diagnostics']['native_model_info'] = _to_jsonable(native.model_info)
            result['diagnostics']['median_estimate'] = float(native.median_estimate)
            result['sample'].update(included_ids_available=False,observations=None)
            result['sample'].pop('included_ids')
            result['sample']['by_specification'] = {}
            for v in table.to_dict('records'):
                term = 'spec_'+str(int(v['spec_id']))
                chosen_controls = control_labels[v['controls']]
                chosen_fe = fe_labels[v['fe']]
                needed = [spec['outcome'],opt['treatment'],*chosen_controls,*chosen_fe]
                if v['se_type']=='cluster': needed.append(opt['cluster'])
                eligible = d[needed].notna().all(axis=1)
                if masks[v['subset']] is not None: eligible &= masks[v['subset']]
                ids = d.loc[eligible,spec['id']].tolist()
                sample = {'eligible_ids':ids,'observations':int(v['nobs']),'included_ids_available':not chosen_fe}
                if not chosen_fe: sample['included_ids'] = ids
                result['sample']['by_specification'][term] = sample
                rows.append({'term':term,'estimate':float(v['estimate']),'se':float(v['se']),
                    'p_raw':float(v['pvalue']),'p_value':float(v['p_holm']),
                    'ci_low':float(v['ci_lower']),'ci_high':float(v['ci_upper']),'n':int(v['nobs']),
                    'controls':v['controls'],'fixed_effects':v['fe'],'subset':v['subset'],'se_type':v['se_type'],'unit':spec['unit']})
            result['inference'].update(procedure='Holm adjusted p-values and Bonferroni simultaneous intervals',
                interval_type='simultaneous',family=family,family_size=family_size,
                native_interval_alpha=alpha/family_size,selection_adjusted=False)
        elif method == 'holm':
            bindings = opt['p_values']
            if not isinstance(bindings,dict) or not bindings: raise ValueError('p_values must map hypothesis names to saved JSON key paths')
            names = list(bindings); raw = np.asarray([lookup(source,bindings[k],f'p value {k}') for k in names],dtype=float)
            if not np.isfinite(raw).all() or ((raw<0)|(raw>1)).any(): raise ValueError('saved p values must lie in [0,1]')
            rejected,adjusted,_,_ = multipletests(raw,alpha=alpha,method='holm'); functions = [multipletests]
            args = {'alpha':alpha,'method':'holm','hypotheses':names}
            rows = [{'term':k,'estimate':float(adjusted[i]),'p_raw':float(raw[i]),'p_value':float(adjusted[i]),
                'reject':bool(rejected[i]),'unit':'probability'} for i,k in enumerate(names)]
            result['inference'].update(procedure='Holm stepdown',family=family,family_size=len(names),selection_adjusted=False)
        else:
            regress = import_module('statspai.regression.ols').regress
            function = import_module('statspai.inference.conley').conley; functions = [regress,function]
            if not controls: raise ValueError('spatial_conley requires at least one regressor')
            if any(not c.isidentifier() for c in [spec['outcome'],*controls]):
                raise ValueError('Conley formula columns must be valid identifiers')
            formula = spec['outcome']+' ~ '+' + '.join(controls)
            fitted = regress(formula,data=d,robust='nonrobust',collinear='raise',missing='raise')
            args = {'lat':opt['lat'],'lon':opt['lon'],'dist_cutoff':opt['dist_cutoff'],
                'kernel':opt['kernel'],'distance':opt['distance'],'alpha':alpha,
                **{k:opt[k] for k in ('time','lag_cutoff','time_kernel','lag_cutoff_cross') if k in opt}}
            if 'panel_unit' in opt: args['unit'] = opt['panel_unit']
            native = function(fitted,d,**args); ci = native.conf_int(alpha=alpha)
            covariance = native.cov_params()
            if not np.isfinite(covariance.to_numpy()).all(): raise ArithmeticError('Conley covariance is nonfinite')
            result['covariance'] = covariance.to_dict('index')
            result['diagnostics'] = _to_jsonable(native.diagnostics)
            result['diagnostics']['native_model_info'] = _to_jsonable(native.model_info)
            result['diagnostics']['formula'] = formula
            result['diagnostics']['residual_df'] = int(native.data_info['df_resid'])
            result['inference'].update(procedure='Conley HAC',reference=native.data_info.get('inference','t'))
            rows = [{'term':str(k),'estimate':float(v),'se':float(native.std_errors[k]),'p_value':float(native.pvalues[k]),
                'ci_low':float(ci.loc[k].iloc[0]),'ci_high':float(ci.loc[k].iloc[1]),'unit':spec['unit']}
                for k,v in native.params.items()]

    if not rows: raise ArithmeticError('the official calculation returned no requested quantities')
    result['diagnostics']['native_warnings'] = [str(w.message) for w in returned_warnings]
    if method == 'romano_wolf' and any('bootstrap draws' in str(w.message) and 'discarded' in str(w.message) for w in returned_warnings):
        raise ArithmeticError('the official Romano-Wolf calculation discarded unidentified bootstrap draws')
    for row in rows:
        for key in ('estimate','se','p_value','ci_low','ci_high'):
            value = row.get(key)
            if value is not None and not np.isfinite(value): raise ArithmeticError(f'nonfinite {key} for {row["term"]}')
        for field,prefix in (('estimate','estimate'),('se','standard_error'),('p_value','p_value'),('p_raw','p_raw'),
                ('ci_low','confidence_lower'),('ci_high','confidence_upper')):
            if field in row:
                result['statistics'][prefix+'.'+row['term']] = {'value':row[field],
                    'unit':'probability' if field.startswith('p_') else row['unit']}
    if method in ('shift_share_inference','spatial_conley'):
        result['coefficients'] = {r['term']:r['estimate'] for r in rows}
        result['standard_errors'] = {r['term']:r['se'] for r in rows}
        result['inference']['confidence_intervals'] = {r['term']:[r['ci_low'],r['ci_high']] for r in rows}
        result['inference']['p_values'] = {r['term']:r['p_value'] for r in rows}
    if family is not None: metadata['family'] = family
    producers = []
    for function in functions:
        code_path = Path(inspect.getfile(inspect.unwrap(function))).resolve()
        producers.append({'function':function.__module__+'.'+function.__name__,
            'signature':str(inspect.signature(function)),'source_path':str(code_path),'source_sha256':_hash(code_path)})
    result['engine'] = '; '.join(p['function'] for p in producers)
    result['producer'] = {'entry_point':'research_causal.py run','functions':producers,'versions':versions,
        'distribution_source':json.loads(dist.read_text('direct_url.json') or 'null') if dist is not None else None}
    result['effective_options'] = args if method=='holm' else _to_jsonable(args)
    metadata.update(engine=result['engine'],producer=result['producer'],inference=result['inference'],
        confidence_level=level,interval_type=result['inference'].get('interval_type','pointwise'))
    result['display'] = {'kind':'coefficient','rows':rows,'metadata':metadata}
    if extra_displays:
        result['displays'] = {k:{**v,'metadata':{**metadata,'estimand':k,**v.get('metadata',{})}} for k,v in extra_displays.items()}
    return result


def _causal_extensions(spec, spec_path):
    """Bind adopted empirical objects to the pinned official implementations."""
    import numpy as np
    import pandas as pd
    import scipy
    import research_data
    from importlib import import_module
    from importlib.metadata import distribution
    import warnings

    method, opt, inf = spec['method'], spec['options'], spec['inference']
    if method=='bayesian_model':
        return _bayesian_model(spec,spec_path)
    contract = CAUSAL_EXTENSIONS[method]
    required = set(contract['required_options'])
    optional = {'args','definitions','weights'}
    optional |= {'fold','learners','seed'} if method in ('metalearner','tmle') else set()
    optional |= {'group','entry'} if method == 'survival_km' else set()
    optional |= {'fixed_effects'} if method == 'gelbach' else set()
    if not required <= opt.keys() or set(opt)-required-optional:
        raise ValueError(f'{method} requires {sorted(required)} and accepts {sorted(optional)}')
    args = deepcopy(opt.get('args',{}))
    definitions = opt.get('definitions',{})
    if not isinstance(args,dict) or not isinstance(definitions,dict):
        raise ValueError('args and definitions must be objects')
    if (not isinstance(inf,dict) or inf.get('type') not in ('official','none','cluster')
            or set(inf)-{'type','confidence_level','cluster'}):
        raise ValueError('extension inference requires official, none or cluster with confidence_level and one cluster column')
    level = inf.get('confidence_level',0.95)
    if isinstance(level,bool) or not isinstance(level,(float,int)) or not 0 < level < 1:
        raise ValueError('confidence_level must be between zero and one')
    cluster = inf.get('cluster')
    if (inf['type']=='cluster') != (cluster is not None):
        raise ValueError('cluster inference requires its actual cluster column')
    clustered = {'lp_did','metalearner','tmle','gelbach','survival_km','survival_aft'}
    if cluster is not None and method not in clustered:
        raise ValueError(f'{method} has no cluster binding in this execution contract')
    weighted = {'bacon','mediation','metalearner','tmle','kitagawa','dfl','survival_km'}
    if 'weights' in opt and method not in weighted:
        raise ValueError(f'{method} has no observation-weight argument')
    if spec['endogenous'] or spec['instruments']:
        raise ValueError('causal extensions bind their scientific roles through options')
    if method in ('kitagawa','survival_km') and spec['regressors']:
        raise ValueError(f'{method} uses its declared cells/groups and no regression covariates')

    role_keys = {
        'lp_did':['entity','time','treatment'], 'bacon':['entity','time','treatment'],
        'scm_diagnostics':['entity','time'], 'augmented_synthetic_control':['entity','time'],
        'mediation':['treatment','mediator'], 'metalearner':['treatment'], 'tmle':['treatment'],
        'kitagawa':['group'], 'dfl':['group'], 'gelbach':[],
        'survival_km':['status','group','entry'], 'survival_aft':['status'],
    }[method]
    columns = [spec['id'],spec['outcome'],*spec['regressors']]
    columns.extend(opt[k] for k in role_keys if k in opt)
    cells = opt['by'] if method=='kitagawa' else []
    cells = [cells] if isinstance(cells,str) else cells
    added = opt.get('added_regressors',[])
    fixed = opt.get('fixed_effects',[])
    for label, values in [('by',cells),('added_regressors',added),('fixed_effects',fixed)]:
        if not isinstance(values,list) or any(not isinstance(v,str) or not v for v in values):
            raise ValueError(f'{label} must name a column or list of columns')
    columns.extend([*cells,*added,*fixed])
    for column in (opt.get('weights'),opt.get('fold'),cluster):
        if column is not None: columns.append(column)
    if any(not isinstance(c,str) or not c for c in columns):
        raise ValueError('each role must name a nonempty analysis column')
    if spec['id'] in columns[1:]:
        raise ValueError('the row ID must have a separate role from model columns')
    columns = list(dict.fromkeys(columns))
    strings = [spec['id'],*fixed,*cells]
    if 'entity' in opt: strings.append(opt['entity'])
    if method=='survival_km' and 'group' in opt: strings.append(opt['group'])
    if cluster is not None: strings.append(cluster)
    path = Path(spec['data'])
    path = (path if path.is_absolute() else spec_path.parent/path).resolve()
    data = research_data.read_frame(path,columns=columns,string_columns=list(dict.fromkeys(strings)))
    if data[spec['id']].isna().any() or data[spec['id']].str.strip().eq('').any() or data[spec['id']].duplicated().any():
        raise ValueError('the input needs distinct nonempty row IDs')
    for column in set(columns)-set(strings):
        data[column] = pd.to_numeric(data[column],errors='raise')
    keep = data[columns].notna().all(axis=1)
    frame = data.loc[keep].copy().reset_index(drop=True)
    if len(frame)<2 or not np.isfinite(frame[list(set(columns)-set(strings))].to_numpy(dtype=float)).all():
        raise ValueError('the complete-case sample needs at least two rows and finite numeric inputs')
    ids = frame[spec['id']].astype(str).tolist()
    if 'weights' in opt:
        w = frame[opt['weights']]
        if (w<0).any() or w.sum()<=0 or (method!='survival_km' and (w<=0).any()):
            raise ValueError('analysis weights must have positive total and the native supported positive domain')
    if 'entity' in opt:
        entity, time = opt['entity'], opt['time']
        if frame.duplicated([entity,time]).any():
            raise ValueError('panel entity-time pairs must be unique')
        periods = np.sort(frame[time].unique())
        if not frame.groupby(entity)[time].nunique().eq(len(periods)).all():
            raise ValueError('these panel extensions require a complete balanced analysis panel')
    if method in ('lp_did','bacon'):
        treatment = opt['treatment']
        if set(frame[treatment].unique())!={0,1}:
            raise ValueError('DID treatment must contain both zero and one')
        ordered = frame.sort_values([entity,time])
        if ordered.groupby(entity)[treatment].diff().dropna().lt(0).any():
            raise ValueError('these DID extensions require absorbing treatment')
        if method=='lp_did':
            if not np.equal(periods,np.floor(periods)).all() or not np.all(np.diff(periods)==1):
                raise ValueError('LP-DiD requires consecutive integer periods')
            if cluster not in (None,entity):
                raise ValueError('StatsPAI 1.43.1 LP-DiD horizon rows retain entity clustering only')
            horizons = args.get('horizons',[-3,5])
            if (not isinstance(horizons,(list,tuple)) or len(horizons)!=2
                    or any(isinstance(h,bool) or not isinstance(h,int) for h in horizons)
                    or not horizons[0]<=-1 or horizons[1]<0):
                raise ValueError('LP-DiD horizons must contain the -1 reference and horizon zero')
        if method=='bacon' and args.get('balance','error')!='error':
            raise ValueError('the Bacon binding preserves the complete balanced input with balance=error')
    if method in ('metalearner','tmle') and set(frame[opt['treatment']].unique())!={0,1}:
        raise ValueError('this treatment-effect binding requires binary treatment coded zero and one')
    if method in ('kitagawa','dfl') and set(frame[opt['group']].unique())!={0,1}:
        raise ValueError('decomposition group must contain zero and one, with gap group 0 minus group 1')
    if method=='kitagawa':
        if not cells or args.get('normalize','symmetric')!='symmetric':
            raise ValueError('Kitagawa requires cells and symmetric contributions')
        if not set(map(tuple,frame.loc[frame[opt['group']].eq(0),cells].to_numpy())) == set(map(tuple,frame.loc[frame[opt['group']].eq(1),cells].to_numpy())):
            raise ValueError('Kitagawa requires both observed group rates in every adopted cell')
        if 'weights' in opt and frame.duplicated([opt['group'],*cells]).any():
            raise ValueError('weighted Kitagawa takes one rate and population count per group-cell')
    if method=='gelbach':
        if not added or opt['var_of_interest'] not in spec['regressors'] or set(added)&set(spec['regressors']):
            raise ValueError('Gelbach requires distinct added controls and a base variable of interest')
    if method in ('survival_km','survival_aft'):
        if not frame[opt['status']].isin([0,1]).all() or not frame[opt['status']].eq(1).any():
            raise ValueError('survival status must be binary with observed events')
        if (frame[spec['outcome']]<0).any() or method=='survival_aft' and (frame[spec['outcome']]<=0).any():
            raise ValueError('KM durations must be nonnegative and AFT durations positive')

    module = import_module(contract['module'])
    function = getattr(module,contract['function'])
    owned = {'data':frame}
    if method in ('lp_did','bacon'):
        owned.update(y=spec['outcome'],time=opt['time'])
        if method=='lp_did': owned.update(unit=entity,treatment=opt['treatment'],controls=spec['regressors'],cluster=entity)
        else: owned.update(id=entity,treat=opt['treatment'],covariates=spec['regressors'])
    elif method in ('scm_diagnostics','augmented_synthetic_control'):
        treated = opt['treated']
        treated = [str(x) for x in treated] if isinstance(treated,list) else str(treated)
        treated_ids = treated if isinstance(treated,list) else [treated]
        if not set(treated_ids)<=set(frame[entity]) or frame[entity].nunique()-len(treated_ids)<2:
            raise ValueError('synthetic control requires observed treated units and at least two donors')
        if method=='scm_diagnostics' and len(treated_ids)!=1:
            raise ValueError('classic SCM takes one treated unit')
        owned.update(outcome=spec['outcome'],unit=entity,time=opt['time'],treated_unit=treated,
            treatment_time=opt['treatment_time'],covariates=spec['regressors'])
        if method=='scm_diagnostics': owned.update(method='classic',missing='raise')
    elif method in ('mediation','metalearner','tmle'):
        owned.update(y=spec['outcome'],treat=opt['treatment'],covariates=spec['regressors'])
        if method=='mediation': owned['mediator']=opt['mediator']
    elif method=='kitagawa':
        owned.update(rate=spec['outcome'],group=opt['group'],by=cells)
    elif method=='dfl':
        owned.update(y=spec['outcome'],group=opt['group'],x=spec['regressors'])
        args.setdefault('inference','none' if inf['type']=='none' else 'bootstrap')
        if args['inference'] not in ('none','bootstrap'):
            raise ValueError('DFL 1.43.1 supplies descriptive output or its native bootstrap')
    elif method=='gelbach':
        owned.update(y=spec['outcome'],base_x=spec['regressors'],added_x=added,var_of_interest=opt['var_of_interest'])
        if fixed: owned['absorb']=fixed
    else:
        owned.update(duration=spec['outcome'],event=opt['status'])
        if method=='survival_km':
            if 'group' in opt: owned['group']=opt['group']
            if 'entry' in opt: owned['start']=opt['entry']
        else: owned['x']=spec['regressors']
    if method!='kitagawa': owned['alpha']=1-level
    if 'weights' in opt: owned['weights']=opt['weights']
    if cluster is not None: owned['cluster']=cluster
    reserved = set(owned) | {'data','alpha','design','formula','fold_indices','Q','g1W',
        'cluster','weights','absorb','outcome_model','propensity_model','cate_model',
        'outcome_library','propensity_library'}
    if set(args)&reserved:
        raise ValueError(f'native args duplicate owned scientific inputs: {sorted(set(args)&reserved)}')
    effective_learners = {}
    if method in ('metalearner','tmle'):
        if method=='metalearner' and 'seed' in opt and 'learners' not in opt:
            raise ValueError('metalearner seed binds declared learners; supply learners or use the native fixed defaults')
        if 'fold' in opt:
            fold_values = frame[opt['fold']].to_numpy(dtype=float)
            if not np.equal(fold_values,np.floor(fold_values)).all():
                raise ValueError('fold labels must be integers')
            owned['fold_indices']=fold_values.astype(int)
        if 'learners' in opt:
            seed = opt.get('seed',42)
            if isinstance(seed,bool) or not isinstance(seed,int) or seed<0:
                raise ValueError('learner seed must be a nonnegative integer')
            learner_map, effective_learners = _nuisance_learners(opt['learners'],seed)
            allowed = {'outcome_model','propensity_model','cate_model'} if method=='metalearner' else {'outcome_model','propensity_model'}
            if not set(learner_map)<=allowed:
                raise ValueError(f'learners accepts {sorted(allowed)}')
            if method=='metalearner': owned.update(learner_map)
            else:
                for key,value in learner_map.items():
                    owned[key.replace('_model','_library')]=[value]
        if method=='tmle' and 'seed' in opt:
            if 'random_state' in args and args['random_state']!=opt['seed']:
                raise ValueError('TMLE seed and native random_state must agree')
            args['random_state']=opt['seed']
    if inf['type']=='none' and method not in ('kitagawa','bacon','dfl','scm_diagnostics','augmented_synthetic_control'):
        raise ValueError(f'{method} returns its native inference; select official or cluster')
    if method in ('scm_diagnostics','augmented_synthetic_control'):
        if 'placebo' in args and args['placebo']!=(inf['type']!='none'):
            raise ValueError('placebo option must agree with the selected inference')
        args['placebo']=inf['type']!='none'
    if method=='dfl' and (args['inference']=='none')!=(inf['type']=='none'):
        raise ValueError('DFL inference and the common inference contract must agree')
    signature = inspect.signature(function)
    if not any(p.kind==inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()):
        unknown = set(args)-set(signature.parameters)
        if unknown: raise ValueError(f'unsupported {contract["engine"]} arguments: {sorted(unknown)}')
    arguments = {**owned,**args}
    with warnings.catch_warnings(record=True) as native_warnings:
        warnings.simplefilter('always')
        native = function(**arguments)

    def plain(value):
        if isinstance(value,pd.DataFrame):
            return {'columns':plain(value.columns.tolist()),'index':plain(value.index.tolist()),'data':plain(value.to_numpy().tolist())}
        if isinstance(value,pd.Series):
            return {'index':plain(value.index.tolist()),'data':plain(value.tolist())}
        if isinstance(value,np.ndarray): return plain(value.tolist())
        if isinstance(value,np.generic): return plain(value.item())
        if isinstance(value,dict): return {str(k):plain(v) for k,v in value.items() if not str(k).startswith('_')}
        if isinstance(value,(list,tuple)): return [plain(v) for v in value]
        if isinstance(value,(pd.Timestamp,np.datetime64)): return str(value)
        if isinstance(value,float) and not np.isfinite(value): return None
        if value is None or isinstance(value,(str,bool,int,float)): return value
        raise TypeError(f'unsupported native result value {type(value).__name__}')

    dist = distribution('StatsPAI')
    source = Path(inspect.getsourcefile(inspect.unwrap(function))).resolve()
    versions = {'python':sys.version.split()[0],'numpy':np.__version__,'pandas':pd.__version__,
        'scipy':scipy.__version__,'StatsPAI':dist.version}
    inference = {'type':inf['type'],'confidence_level':level,'procedure':contract['inference'],
        'cluster':cluster,'covariance_available':False,'interval_type':'native pointwise'}
    result = {'result_format_version':1,'method':method,'engine':contract['engine'],
        'options':deepcopy(opt),'versions':versions,
        'adopted':{k:deepcopy(spec[k]) for k in ('population','period','unit','estimand','identification','assignment','inference')},
        'sample':{'id_column':spec['id'],'input_rows':len(data),'input_ids':data[spec['id']].astype(str).tolist(),
            'included_ids':ids,'included_ids_available':True,'observations':len(frame),
            'excluded_incomplete_ids':data.loc[~keep,spec['id']].astype(str).tolist()},
        'inference':inference,'statistics':{},'diagnostics':{'native_warnings':[str(w.message) for w in native_warnings]},
        'effective_options':plain({k:v for k,v in arguments.items() if k!='data' and k not in ('outcome_model','propensity_model','cate_model','outcome_library','propensity_library')}),
        'producer':{'entry_point':'research_causal.py run','function':contract['engine'],'signature':str(signature),
            'versions':versions,'source_path':str(source),'source_sha256':_hash(source),
            'distribution_source':json.loads(dist.read_text('direct_url.json') or 'null')},
        'provenance':{'data_path':str(path),'data_sha256':_hash(path),'spec_path':str(spec_path.resolve()),
            'spec_sha256':_hash(spec_path),'producer_path':str(Path(__file__).resolve()),'producer_sha256':_hash(Path(__file__).resolve())}}
    if effective_learners:
        result['effective_options']['learners']=plain(effective_learners)
    metadata = {**definitions,'population':spec['population'],'period':spec['period'],'unit':spec['unit'],
        'estimand':spec['estimand'],'outcome':spec['outcome'],'identification':spec['identification'],
        'assignment':spec['assignment'],'inference':inference,'engine':contract['engine'],
        'confidence_level':level,'result_format_version':1}
    rows, displays, covariance = [], {}, None
    native_info = getattr(native,'model_info',{})
    if native_info:
        result['diagnostics']['native']=plain(native_info)
        if native_info.get('converged') is False:
            raise ArithmeticError(f'{contract["engine"]} did not converge')

    def row(term, estimate, se=None, lower=None, upper=None, pvalue=None, unit=None, **extra):
        if estimate is None or not np.isfinite(float(estimate)):
            raise ArithmeticError(f'{method} returned a nonfinite primary estimate for {term}')
        return {'term':str(term),'estimate':float(estimate),'se':plain(se),'lower':plain(lower),'upper':plain(upper),
            'ci_low':plain(lower),'ci_high':plain(upper),
            'p_value':plain(pvalue),'unit':unit or spec['unit'],
            'lower_unbounded':bool(lower is not None and np.isneginf(lower)),
            'upper_unbounded':bool(upper is not None and np.isposinf(upper)),**extra}

    if method=='bacon':
        result['native_result']=plain(dict(native))
        table=native['decomposition']
        rows=[row(f'comparison_{i}',r['estimate'],weight=float(r['weight']),
            comparison_class=r['comparison_class'],comparison_type=r['type']) for i,r in table.iterrows()]
        result['statistics']['twfe.coefficient']={'value':float(native['beta_twfe']),'unit':spec['unit']}
        result['statistics']['decomposition.weighted_sum']={'value':float(native['weighted_sum']),'unit':spec['unit']}
        inference.update(type='none',confidence_level=None,interval_type='none')
    elif method=='kitagawa':
        result['native_result']=plain(native.to_dict())
        rows=[row(k,getattr(native,k)) for k in ('gap','rate_effect','composition_effect','interaction')]
        displays['decomposition_cells']={'kind':'table','rows':plain(native.per_cell.to_dict('records')),'metadata':metadata}
        inference.update(type='none',confidence_level=None,interval_type='none')
    elif method=='dfl':
        result['native_result']=plain(native.to_dict())
        if inf['type']!='none' and (native.se is None or native.ci is None):
            raise ArithmeticError('DFL did not return its requested bootstrap inference')
        for term in ('gap','composition','structure'):
            interval=(native.ci or {}).get(term,(None,None))
            rows.append(row(term,getattr(native,term),(native.se or {}).get(term),*interval))
        if native.quantile_grid is not None:
            displays['decomposition_quantiles']={'kind':'table','rows':plain(native.quantile_grid.to_dict('records')),
                'metadata':{**metadata,'interval_type':'none','estimand':'Native point decomposition over the declared quantile grid'}}
        result['diagnostics']['counterfactual_weight_ids']=frame.loc[frame[opt['group']].eq(1 if args.get('reference',0)==0 else 0),spec['id']].tolist()
    elif method=='gelbach':
        result['native_result']=plain(native.to_dict())
        rows=[row(r['variable'],r['delta'],r['se'],pvalue=r['pvalue']) for r in native.decomposition.to_dict('records')]
        covariance=native.vcov.to_numpy(dtype=float)
        result['diagnostics'].update(base_coefficient=float(native.base_coef),full_coefficient=float(native.full_coef),
            total_change=float(native.total_change),total_standard_error=float(native.total_se))
        if fixed:
            result['sample'].update(included_ids_available=False,included_ids=[],observations=None,
                membership='native absorbed projection; fitted IDs are not exported')
    elif method=='survival_km':
        table=native.survival_table
        result['native_result']={'survival_table':plain(table),'median_survival':plain(native.median_survival)}
        rows=[row(f'survival_{i}',r['survival'],r['std_err'],r['ci_lower'],r['ci_upper'],
            unit='probability',time=r['time'],component=str(r.get('group','all')),
            n_risk=r['n_risk'],n_event=r['n_event'],n_censor=r['n_censor']) for i,r in table.iterrows()]
        metadata.update(unit='probability',time_unit=definitions.get('duration_unit',spec['unit']))
    elif method=='survival_aft':
        interval=native.conf_int(alpha=1-level)
        result['native_result']={'parameters':plain(native.params),'standard_errors':plain(native.std_errors),
            'intervals':plain(interval),'model_info':plain(native.model_info),'data_info':plain(native.data_info),
            'diagnostics':plain(native.diagnostics)}
        covariance=native.cov_params().to_numpy(dtype=float)
        rows=[row(term,value,native.std_errors[term],*interval.loc[term].tolist(),pvalue=native.pvalues[term],
            unit='dimensionless log scale' if term.startswith('log(') else spec['unit'])
            for term,value in native.params.items()]
        displays['time_ratios']={'kind':'coefficient','rows':[
            {'term':r['term'],'estimate':float(np.exp(r['estimate'])),'lower':float(np.exp(r['lower'])),
             'upper':float(np.exp(r['upper'])),'ci_low':float(np.exp(r['lower'])),
             'ci_high':float(np.exp(r['upper'])),'unit':'time ratio'} for r in rows if r['term'] in spec['regressors']],
            'metadata':{**metadata,'unit':'time ratio','estimand':'Multiplicative duration change exp(beta)'}}
    else:
        result['native_result']={**plain(native.to_dict(detail='minimal')),
            'detail':plain(native.detail),'model_info':plain(native_info)}
        if method=='lp_did':
            es=native_info['event_study']
            for item in es.to_dict('records'):
                h=int(item['relative_time'])
                rows.append(row(f'event_{h}',item['att'],item['se'],item['ci_lower'],item['ci_upper'],item['pvalue'],
                    event_time=h,role='reference' if h==-1 else 'pre_diagnostic' if h<0 else 'att',
                    observations=int(item['n_obs'])))
            vc=native_info['event_study_vcov']
            result['diagnostics']['event_covariance']=plain(vc)
            if vc is not None:
                result['covariance']={f'event_{int(a)}':{f'event_{int(b)}':float(vc.loc[a,b]) for b in vc.columns} for a in vc.index}
                inference['covariance_available']=True
            result['sample'].update(included_ids=[],included_ids_available=False,observations=None,
                membership='native horizon-specific samples; counts are attached to event rows')
        elif method=='mediation':
            rows=[row(r['effect'],r['estimate'],r['se'],r['ci_lower'],r['ci_upper'],r['pvalue'],
                unit='proportion' if 'prop' in str(r['effect']).lower() else spec['unit'])
                for r in native.detail.to_dict('records') if np.isfinite(r['estimate'])]
        else:
            rows=[row(native.estimand,native.estimate,native.se,*native.ci,pvalue=native.pvalue)]
        if method in ('scm_diagnostics','augmented_synthetic_control'):
            gap=native_info['gap_table']
            trajectory=[]
            for r in gap.to_dict('records'):
                for component,column in [('actual','treated'),('synthetic','synthetic')]:
                    trajectory.append({'time':r['time'],'estimate':r[column],'component':component,'unit':spec['unit']})
            displays['scm_trajectory']={'kind':'scm','rows':plain(trajectory),
                'metadata':{**metadata,'donor_weights':plain(native_info['weights']),'treatment_time':opt['treatment_time']}}
            displays['scm_gap']={'kind':'scm_gap','rows':[
                {'time':r['time'],'estimate':r['gap'],'unit':spec['unit']} for r in gap.to_dict('records')],
                'metadata':metadata}
            for key in ('placebo_table','placebo_effects','placebo_time','loo'):
                if key in native_info: result['diagnostics'][key]=plain(native_info[key])
            result['sample'].update(included_ids=[],included_ids_available=False,observations=None,
                panel_rows=len(frame),membership='native donor and time selections in saved trajectories/weights')
            inference['native_interval_method']=native_info.get('ci_method','placebo_sd_normal')
        if method=='metalearner':
            estimation_rows=np.asarray(native_info['estimation_rows'],dtype=int)
            fitted_ids=frame.iloc[estimation_rows][spec['id']].tolist()
            result['sample'].update(included_ids=fitted_ids,observations=int(native.n_obs))
            displays['cate']={'kind':'coefficient','rows':[
                {'term':identity,'estimate':float(cate),'unit':spec['unit'],'role':'fitted_cate'}
                for identity,cate in zip(fitted_ids,native_info['cate'])],
                'metadata':{**metadata,'estimand':'Learner-specific conditional treatment effect','interval_type':'none'}}
        if method in ('metalearner','tmle') and 'fold' in opt:
            result['diagnostics']['fold_assignment']={'ids':ids,'folds':owned['fold_indices'].tolist()}
        if method in ('mediation','metalearner','tmle') and int(native.n_obs)!=len(frame):
            raise ArithmeticError('native fitted row count differs from the explicit complete-case sample')
    result['coefficients']={r['term']:r['estimate'] for r in rows}
    result['standard_errors']={r['term']:r['se'] for r in rows if r.get('se') is not None}
    inference['confidence_intervals']={r['term']:[r['lower'],r['upper']] for r in rows if r.get('lower') is not None or r.get('lower_unbounded')}
    inference['p_values']={r['term']:r['p_value'] for r in rows if r.get('p_value') is not None}
    if covariance is not None:
        result['covariance']={a['term']:{b['term']:float(covariance[i,j]) for j,b in enumerate(rows)} for i,a in enumerate(rows)}
        inference['covariance_available']=True
    for r in rows:
        for prefix,field in [('coefficient','estimate'),('standard_error','se'),
                (f'confidence_{100*level:g}_lower','lower'),(f'confidence_{100*level:g}_upper','upper')]:
            if r.get(field) is not None: result['statistics'][f'{prefix}.{r["term"]}']={'value':r[field],'unit':r['unit']}
    kind='event_study' if method=='lp_did' else 'line' if method=='survival_km' else 'coefficient'
    metadata.update(inference=inference,sample={'observations':result['sample']['observations'],
        'included_ids_available':result['sample']['included_ids_available'],'input_ids_ref':'sample.input_ids'})
    result['display']={'kind':kind,'rows':rows,'metadata':metadata}
    if method=='survival_km':
        result['display']['display']={'plot_type':'step','x':'time','y':'estimate','series':'component'}
    if displays: result['displays']=displays
    return plain(result)


def _bayesian_model(spec, spec_path):
    """Execute an adopted project model and retain its native posterior file."""
    import numpy as np
    import pandas as pd
    import research_data
    import os
    import tempfile
    import warnings
    from importlib.metadata import version
    import pymc as pm
    import arviz as az
    import xarray as xr
    import h5netcdf
    import h5py

    opt, inf = spec['options'], spec['inference']
    required=set(CAUSAL_EXTENSIONS['bayesian_model']['required_options'])
    optional={'definitions','prior_predictive','posterior_predictive','diagnostics','model_dependencies','observation_coord'}
    if not required<=opt.keys() or set(opt)-required-optional:
        raise ValueError(f'bayesian_model requires {sorted(required)} and accepts {sorted(optional)}')
    if opt['engine'] not in ('pymc','causalpy'):
        raise ValueError('Bayesian engine must be pymc or causalpy')
    inference_data = opt['engine']=='causalpy'
    pymc_major, arviz_major = version('pymc').split('.')[0], version('arviz').split('.')[0]
    if inference_data and (pymc_major!='5' or arviz_major!='0'):
        raise ValueError('CausalPy 0.9 uses PyMC 5 and ArviZ 0 InferenceData; use the selected CausalPy package environment')
    if not inference_data and (pymc_major!='6' or arviz_major!='1'):
        raise ValueError('engine=pymc uses the selected PyMC 6 and ArviZ 1 DataTree environment')
    if not isinstance(inf,dict) or set(inf)-{'type','credible_level'} or inf.get('type')!='posterior':
        raise ValueError('Bayesian inference is posterior with an optional credible_level')
    level=inf.get('credible_level',0.95)
    if isinstance(level,bool) or not isinstance(level,(int,float)) or not 0<level<1:
        raise ValueError('credible_level must lie between zero and one')
    variables=opt['var_names']
    if not isinstance(variables,list) or not variables or any(not isinstance(v,str) or not v for v in variables):
        raise ValueError('var_names must name the adopted posterior variables')
    sampling=deepcopy(opt['sampling'])
    if not isinstance(sampling,dict) or not {'draws','tune','chains','random_seed'}<=sampling.keys():
        raise ValueError('sampling must declare draws, tune, chains and random_seed')
    for key,minimum in [('draws',4),('tune',0),('chains',2),('random_seed',0)]:
        if isinstance(sampling[key],bool) or not isinstance(sampling[key],int) or sampling[key]<minimum:
            raise ValueError(f'sampling.{key} must be an integer at least {minimum}')
    if 'model' in sampling or sampling.get('return_inferencedata') is False:
        raise ValueError('the builder supplies the model and sampling returns its native posterior container')
    if opt['engine']=='pymc': sampling.setdefault('progressbar',False)
    diagnostics=opt.get('diagnostics',{})
    if not isinstance(diagnostics,dict) or set(diagnostics)-{'r_hat_max','ess_bulk_min','ess_tail_min','divergences_max'}:
        raise ValueError('diagnostics accepts adopted R-hat, bulk/tail ESS and divergence thresholds')
    for key,value in diagnostics.items():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or value<0:
            raise ValueError(f'diagnostics.{key} must be a finite nonnegative threshold')
    definitions=opt.get('definitions',{})
    if not isinstance(definitions,dict) or not isinstance(definitions.get('parameter_units',{}),dict):
        raise ValueError('definitions and its parameter_units must be objects')
    paths={}
    for key,value in [('data',spec['data']),('model_file',opt['model_file']),('posterior_output',opt['posterior_output'])]:
        if not isinstance(value,str) or not value: raise ValueError(f'{key} must name a path')
        p=Path(value); paths[key]=(p if p.is_absolute() else spec_path.parent/p).resolve()
    if paths['posterior_output'] in (paths['data'],paths['model_file'],spec_path.resolve()):
        raise ValueError('posterior_output must be separate from the adopted inputs')
    if paths['posterior_output'].suffix.lower() not in ('.nc','.netcdf'):
        raise ValueError('posterior_output must be a native NetCDF path')
    dependency_paths=opt.get('model_dependencies',[])
    if not isinstance(dependency_paths,list) or any(not isinstance(p,str) or not p for p in dependency_paths):
        raise ValueError('model_dependencies must list the actual model helper/input paths')
    dependencies=[]
    for name in dependency_paths:
        p=Path(name); p=(p if p.is_absolute() else spec_path.parent/p).resolve()
        if p == paths['posterior_output']:
            raise ValueError('posterior_output must be separate from model dependencies')
        dependencies.append({'path':str(p),'sha256':_hash(p)})
    data=research_data.read_frame(paths['data'],string_columns=[spec['id']])
    if data[spec['id']].isna().any() or data[spec['id']].str.strip().eq('').any() or data[spec['id']].duplicated().any():
        raise ValueError('Bayesian input needs distinct nonempty row IDs')
    input_ids = data[spec['id']].astype(str).tolist()
    if not isinstance(opt['builder'],str) or not opt['builder'].isidentifier():
        raise ValueError('builder must name the adopted model function')
    loader=importlib.util.spec_from_file_location('ers_bayesian_model_'+_hash(paths['model_file'])[:16],paths['model_file'])
    if loader is None or loader.loader is None: raise ValueError('model_file must be an importable Python source file')
    module=importlib.util.module_from_spec(loader)
    sys.modules[loader.name]=module
    model_directory=str(paths['model_file'].parent)
    sys.path.insert(0,model_directory)
    steps=[]

    def retain_groups(target, generated, names):
        # Predictive calls retain the fitted observed_data and constant_data.
        if inference_data:
            selected={name:generated[name] for name in names if name in generated.groups()}
            target.extend(az.InferenceData(**selected),join='right')
        else:
            for name in names:
                if name in generated.children: target[name]=generated[name].copy()

    with warnings.catch_warnings(record=True) as returned_warnings:
        warnings.simplefilter('always')
        try:
            loader.loader.exec_module(module)
            builder=getattr(module,opt['builder'])
            inspect.signature(builder).bind(data=data,specification=spec)
            native=builder(data=data,specification=deepcopy(spec))
        finally:
            sys.path.remove(model_directory)
        if opt['engine']=='pymc':
            if not isinstance(native,pm.Model): raise TypeError('the PyMC builder must return its adopted pm.Model')
            model=native
            prior=None
            if 'prior_predictive' in opt:
                prior_args=deepcopy(opt['prior_predictive'])
                if not isinstance(prior_args,dict) or 'model' in prior_args or prior_args.get('return_inferencedata') is False:
                    raise ValueError('prior_predictive contains native keyword arguments with the builder model')
                prior_args.setdefault('random_seed',sampling['random_seed'])
                prior=pm.sample_prior_predictive(model=model,**prior_args)
                steps.append({'function':'pymc.sample_prior_predictive','arguments':prior_args})
            idata=pm.sample(model=model,**sampling)
            steps.append({'function':'pymc.sample','arguments':sampling})
            if prior is not None:
                retain_groups(idata,prior,('prior','prior_predictive'))
        else:
            from causalpy.experiments.base import BaseExperiment
            from causalpy.pymc_models import PyMCModel
            experiment=isinstance(native,BaseExperiment)
            model=native.model if experiment else native
            if not isinstance(model,PyMCModel):
                raise TypeError('the CausalPy builder must return its fitted PyMCModel or Bayesian BaseExperiment')
            actual_sampling=model.sample_kwargs
            for key,value in sampling.items():
                if actual_sampling.get(key)!=value:
                    raise ValueError(f'CausalPy builder did not bind adopted sampling.{key}')
            idata=model.idata
            if not isinstance(idata,az.InferenceData) or 'posterior' not in idata.groups():
                raise TypeError('the CausalPy builder must return its fitted native InferenceData posterior')
            steps.append({'function':type(native).__module__+'.'+type(native).__name__,
                'operation':'constructor fit' if experiment else 'fit','sampling':deepcopy(actual_sampling)})
            if 'prior_predictive' in opt:
                prior_args=deepcopy(opt['prior_predictive'])
                if not isinstance(prior_args,dict) or 'model' in prior_args or prior_args.get('return_inferencedata') is False:
                    raise ValueError('prior_predictive contains native keyword arguments with the fitted CausalPy model')
                prior_args.setdefault('random_seed',sampling['random_seed'])
                prior=pm.sample_prior_predictive(model=model,**prior_args)
                retain_groups(idata,prior,('prior','prior_predictive'))
                steps.append({'function':'pymc.sample_prior_predictive','arguments':prior_args,'model_state':'fitted CausalPy model'})
        native_type=az.InferenceData if inference_data else xr.DataTree
        if not isinstance(idata,native_type):
            raise TypeError('the selected Bayesian engine must return its native '+native_type.__name__)
        groups=idata.groups() if inference_data else list(idata.children)
        if 'posterior' not in groups:
            raise ValueError('the fitted Bayesian result must contain its posterior group')
        if 'posterior_predictive' in opt:
            predictive_args=deepcopy(opt['posterior_predictive'])
            if not isinstance(predictive_args,dict) or {'trace','model','extend_inferencedata'}&predictive_args.keys() or predictive_args.get('return_inferencedata') is False:
                raise ValueError('posterior_predictive contains native keyword arguments for the saved posterior and builder model')
            predictive_args.setdefault('random_seed',sampling['random_seed'])
            predictive_args.setdefault('progressbar',False)
            predictive=pm.sample_posterior_predictive(idata,model=model,extend_inferencedata=False,**predictive_args)
            retain_groups(idata,predictive,('posterior_predictive','predictions','predictions_constant_data'))
            steps.append({'function':'pymc.sample_posterior_predictive','arguments':predictive_args})
        missing=set(variables)-set(idata['posterior'].data_vars)
        if missing: raise ValueError(f'posterior variables absent from the fitted model: {sorted(missing)}')
        summary_args={'var_names':variables,'group':'posterior','kind':'all','round_to':'none','skipna':False}
        if inference_data:
            summary_args['hdi_prob']=level
            lower_column=f'hdi_{100*(1-level)/2:g}%'; upper_column=f'hdi_{100*(1-(1-level)/2):g}%'
        else:
            summary_args.update(ci_prob=level,ci_kind='hdi')
            lower_column=f'hdi{int(level*100)}_lb'; upper_column=f'hdi{int(level*100)}_ub'
        summary=az.summary(idata,**summary_args)
    if not np.isfinite(summary[['mean','sd',lower_column,upper_column]].to_numpy(dtype=float)).all():
        raise ArithmeticError('the selected posterior summary contains nonfinite estimates')
    divergence_count=(int(idata['sample_stats']['diverging'].sum().item())
        if 'sample_stats' in groups and 'diverging' in idata['sample_stats'] else None)
    measures={'divergences_max':divergence_count}
    for key,column in [('r_hat_max','r_hat'),('ess_bulk_min','ess_bulk'),('ess_tail_min','ess_tail')]:
        values=summary[column].to_numpy(dtype=float)
        # An adopted threshold applies to every selected posterior quantity.
        # Pandas reductions would silently omit a quantity with an undefined diagnostic.
        measures[key]=(float(values.max() if key.endswith('_max') else values.min())
            if np.isfinite(values).all() else None)
    criteria={}
    for key,threshold in diagnostics.items():
        observed=measures[key]
        passed=observed is not None and np.isfinite(observed) and (observed<=threshold if key.endswith('_max') else observed>=threshold)
        criteria[key]={'observed':observed if observed is not None and np.isfinite(observed) else None,
            'threshold':threshold,'passed':bool(passed)}
    ids=input_ids
    fitted_ids = None
    if 'observation_coord' in opt:
        coordinate = opt['observation_coord']
        if ('observed_data' not in groups or coordinate not in idata['observed_data'].coords
                or not any(coordinate in value.dims for value in idata['observed_data'].data_vars.values())):
            raise ValueError('observation_coord must index the native observed outcome data')
        fitted_ids = [str(value) for value in idata['observed_data'].coords[coordinate].values]
        if len(fitted_ids)!=len(set(fitted_ids)) or not set(fitted_ids)<=set(ids):
            raise ValueError('native observed-data coordinates must identify unique rows of the canonical input')
    rows=[]; statistics={}
    for label,values in summary.iterrows():
        term=str(label)
        unit=definitions.get('parameter_units',{}).get(term,spec['unit'])
        rows.append({'term':term,'estimate':float(values['mean']),'posterior_sd':float(values['sd']),
            'ci_low':float(values[lower_column]),'ci_high':float(values[upper_column]),
            'unit':unit,'role':'posterior'})
        for key,column in [('posterior_mean','mean'),('posterior_sd','sd'),('hdi_lower',lower_column),('hdi_upper',upper_column)]:
            statistics[f'{key}.{term}']={'value':float(values[column]),'unit':unit}
    output=paths['posterior_output']; output.parent.mkdir(parents=True,exist_ok=True)
    handle=tempfile.NamedTemporaryFile(prefix='.'+output.name+'.',suffix='.nc',dir=output.parent,delete=False)
    temporary=Path(handle.name); handle.close()
    rejected_posterior = None
    try:
        idata.to_netcdf(temporary,engine='h5netcdf')
        if any(not criterion['passed'] for criterion in criteria.values()):
            rejected_posterior = temporary
            raise ArithmeticError('Adopted posterior diagnostics failed: '+json.dumps(criteria)+
                '; rejected native posterior retained at '+str(rejected_posterior))
        os.replace(temporary,output)
    finally:
        if rejected_posterior is None:
            temporary.unlink(missing_ok=True)
    package_names=['pymc','arviz','arviz-stats','xarray','h5netcdf','h5py','numpy','pandas','scipy','pytensor']
    if inference_data: package_names.extend(['causalpy','pymc-extras','preliz','better-optimize','scikit-learn'])
    versions={name:version(name) for name in package_names}
    versions['python']=sys.version.split()[0]
    native_groups=idata.groups() if inference_data else list(idata.groups)
    native_file={'format':('arviz.InferenceData' if inference_data else 'xarray.DataTree')+' NetCDF',
        'path':str(output),'sha256':_hash(output),'groups':native_groups,
        'dimensions':{group:dict(idata[group].sizes) for group in native_groups}}
    summary_values=summary.replace([np.inf,-np.inf],np.nan)
    posterior_summary=summary_values.astype(object).where(pd.notna(summary_values),None).reset_index(names='term').to_dict('records')
    metadata={**definitions,'population':spec['population'],'period':spec['period'],'unit':spec['unit'],
        'estimand':spec['estimand'],'identification':spec['identification'],'assignment':spec['assignment'],
        'interval_type':'posterior HDI','credible_level':level,'engine':opt['engine'],'native_posterior':native_file}
    return {'result_format_version':1,'method':'bayesian_model','engine':opt['engine'],
        'options':deepcopy(opt),'versions':versions,
        'adopted':{k:deepcopy(spec[k]) for k in ('population','period','unit','estimand','identification','assignment','inference')},
        'sample':{'id_column':spec['id'],'input_rows':len(ids),'input_ids':ids,
            'included_ids_available':fitted_ids is not None,'included_ids':fitted_ids or [],
            'observations':len(fitted_ids) if fitted_ids is not None else None,
            'membership':'native observed_data coordinate '+opt['observation_coord'] if fitted_ids is not None else
                'The project model owns the observation mapping; native observed_data and coordinates are retained in NetCDF.'},
        'posterior':{'summary':posterior_summary,'native_file':native_file},
        'inference':{'type':'posterior','credible_level':level,'interval_type':'HDI',
            'posterior_intervals':{r['term']:[r['ci_low'],r['ci_high']] for r in rows}},
        'statistics':statistics,'display':{'kind':'coefficient','rows':rows,'metadata':metadata},
        'diagnostics':{'sampler_summary':posterior_summary,'divergences':divergence_count,
            'criteria':criteria,'criteria_passed':all(c['passed'] for c in criteria.values()) if criteria else None,
            'native_warnings':[str(w.message) for w in returned_warnings]},
        'effective_options':{'sampling':sampling,'summary':summary_args,'executed_steps':steps},
        'producer':{'entry_point':'research_causal.py run','builder':opt['builder'],
            'builder_signature':str(inspect.signature(builder)),'sample_signature':str(inspect.signature(pm.sample)),
            'summary_signature':str(inspect.signature(az.summary)),'versions':versions},
        'provenance':{'data_path':str(paths['data']),'data_sha256':_hash(paths['data']),
            'spec_path':str(spec_path.resolve()),'spec_sha256':_hash(spec_path),
            'model_path':str(paths['model_file']),'model_sha256':_hash(paths['model_file']),'model_dependencies':dependencies,
            'producer_path':str(Path(__file__).resolve()),'producer_sha256':_hash(Path(__file__).resolve())}}


def _policy_assignment(rewards, weights, costs, baseline, constraints):
    """Choose actions from predicted rewards and resources, before reading evaluation outcomes."""
    import numpy as np
    if not constraints:
        return rewards.argmax(axis=1), {'method':'argmax of econml.policy.PolicyTree.predict_value'}
    from scipy.optimize import milp, Bounds, LinearConstraint
    from scipy.sparse import csr_matrix, kron, eye, vstack
    n, k = rewards.shape
    allowed = {'budget','max_treated','max_treated_fraction','arm_capacities'}
    if not isinstance(constraints,dict) or set(constraints)-allowed:
        raise ValueError('policy constraints accept budget, max_treated, max_treated_fraction and arm_capacities')
    if {'max_treated','max_treated_fraction'} <= constraints.keys():
        raise ValueError('choose max_treated or max_treated_fraction')
    matrices = [kron(eye(n,format='csr'), np.ones((1,k)), format='csr')]
    lower = [np.ones(n)]; upper = [np.ones(n)]; limits = {}
    if 'budget' in constraints:
        budget = constraints['budget']
        if isinstance(budget,bool) or not isinstance(budget,(int,float)) or not np.isfinite(budget) or budget < 0:
            raise ValueError('policy budget must be finite and nonnegative')
        matrices.append(csr_matrix(np.tile(costs,n).reshape(1,-1)))
        lower.append([-np.inf]); upper.append([budget]); limits['budget'] = budget
    if 'max_treated_fraction' in constraints:
        fraction = constraints['max_treated_fraction']
        if isinstance(fraction,bool) or not isinstance(fraction,(int,float)) or not 0 <= fraction <= 1:
            raise ValueError('max_treated_fraction must lie in [0,1]')
        limits['max_treated'] = int(np.floor(n*fraction))
    elif 'max_treated' in constraints:
        count = constraints['max_treated']
        if isinstance(count,bool) or not isinstance(count,int) or count < 0:
            raise ValueError('max_treated must be a nonnegative integer')
        limits['max_treated'] = count
    if 'max_treated' in limits:
        matrices.append(csr_matrix(np.tile(np.arange(k)!=baseline,n).reshape(1,-1)))
        lower.append([-np.inf]); upper.append([limits['max_treated']])
    if 'arm_capacities' in constraints:
        caps = constraints['arm_capacities']
        if not isinstance(caps,list) or len(caps)!=k or any(isinstance(v,bool) or not isinstance(v,int) or v<0 for v in caps):
            raise ValueError('arm_capacities must contain one nonnegative integer per declared arm')
        matrices.append(kron(np.ones((1,n)),eye(k,format='csr'),format='csr'))
        lower.append(np.full(k,-np.inf)); upper.append(caps); limits['arm_capacities'] = caps
    matrix = vstack(matrices,format='csr'); lo = np.concatenate(lower); hi = np.concatenate(upper)
    solved = milp(-(weights[:,None]*rewards).ravel(), integrality=np.ones(n*k),
        bounds=Bounds(0,1), constraints=LinearConstraint(matrix,lo,hi), options={'mip_rel_gap':0.0})
    if not solved.success:
        raise ArithmeticError('policy allocation failed: '+solved.message)
    chosen = solved.x.reshape(n,k).argmax(axis=1)
    assigned = np.eye(k)[chosen].ravel()
    residual = max(float(np.max(lo-matrix@assigned)),float(np.max(matrix@assigned-hi)),0.0)
    if residual > 1e-7 or not np.allclose(solved.x,assigned,rtol=0,atol=1e-6):
        raise ArithmeticError('policy allocation violates its original integer/resource constraints')
    return chosen, {'method':'scipy.optimize.milp','limits':limits,'maximum_constraint_violation':residual,
        'objective':float(np.sum(weights*rewards[np.arange(n),chosen])),
        'mip_gap':float(solved.mip_gap),'message':solved.message}


def _policy_tree(spec, spec_path):
    """Cross-fitted multi-arm rewards, frozen policy selection and independent value evaluation."""
    import numpy as np
    import pandas as pd
    import scipy
    import statsmodels
    import statsmodels.api as sm
    import research_data
    import econml
    import sklearn
    import statspai
    import warnings
    from econml.policy import PolicyTree
    from sklearn.base import clone, is_classifier, is_regressor
    from sklearn.model_selection import StratifiedKFold, StratifiedGroupKFold
    from sklearn.exceptions import ConvergenceWarning
    from scipy.stats import norm, t as student_t
    from statsmodels.stats.sandwich_covariance import S_white_simple
    from statspai.policy_learning.ope import doubly_robust, ips
    from statspai.policy_learning import ope as ope_module

    opt = spec['options']; config = opt['policy']; inf = spec['inference']
    required = {'treatment','partition','seed','policy'}
    if not required <= opt.keys() or set(opt)-required-{'weights'}:
        raise ValueError('extended policy options require treatment, partition, seed, policy; weights is optional')
    required_policy = {'arms','baseline','value_method','propensity','evaluation_target'}
    optional_policy = {'n_folds','learners','tree','costs','objective','constraints'}
    if not isinstance(config,dict) or not required_policy <= config.keys() or set(config)-required_policy-optional_policy:
        raise ValueError('policy requires arms, baseline, value_method, propensity and evaluation_target')
    arms = config['arms']
    if (not isinstance(arms,list) or len(arms)<2 or any(not isinstance(a,str) or not a.strip() for a in arms)
            or len(set(arms))!=len(arms) or config['baseline'] not in arms):
        raise ValueError('policy arms must be distinct nonempty string labels including baseline')
    k = len(arms); baseline = arms.index(config['baseline']); seed = opt['seed']; folds = config.get('n_folds',2)
    for name,value,minimum in (('seed',seed,0),('n_folds',folds,2)):
        if isinstance(value,bool) or not isinstance(value,int) or value<minimum:
            raise ValueError(f'policy {name} must be an integer >= {minimum}')
    if config['value_method'] not in ('ipw','aipw') or config['evaluation_target'] not in ('population','fixed_batch'):
        raise ValueError('policy value_method is ipw/aipw; evaluation_target is population/fixed_batch')
    if (not isinstance(inf,dict) or inf.get('type')!='policy'
            or set(inf)-{'type','cluster','confidence_level'}):
        raise ValueError('policy inference requires type=policy and optional cluster/confidence_level')
    cluster = inf.get('cluster'); level = inf.get('confidence_level',.95)
    if isinstance(level,bool) or not isinstance(level,(int,float)) or not 0<level<1:
        raise ValueError('policy confidence_level must lie between zero and one')
    propensity = config['propensity']
    if not isinstance(propensity,dict) or propensity.get('source') not in ('known','estimated'):
        raise ValueError('policy propensity.source must be known or estimated')
    known = propensity['source']=='known'
    if not known and config['value_method']=='ipw':
        raise ValueError('estimated-propensity policy inference requires AIPW; this IPW route uses known probabilities')
    if set(propensity)-({'source','columns','assignment_unit','mechanism'} if known else {'source'}):
        raise ValueError('known propensity accepts columns, assignment_unit and mechanism; estimated accepts source only')
    propensity_columns = propensity.get('columns',[])
    if known and (not isinstance(propensity_columns,list) or len(propensity_columns)!=k
            or len(set(propensity_columns))!=k):
        raise ValueError('known policy propensity needs one distinct column per arm, in arms order')
    constraints = config.get('constraints',{})
    if not isinstance(constraints,dict): raise ValueError('policy constraints must be an object')
    fixed_batch = config['evaluation_target']=='fixed_batch'
    if constraints and not fixed_batch:
        raise ValueError('exact policy constraints require evaluation_target=fixed_batch')
    if fixed_batch and (not known or propensity.get('mechanism')!='independent_multinomial'
            or propensity.get('assignment_unit')!=('cluster' if cluster else 'individual')):
        raise ValueError('fixed_batch requires known independent multinomial assignment at the declared individual/cluster unit')
    objective = config.get('objective','net_benefit')
    if objective not in ('outcome','net_benefit'):
        raise ValueError('policy objective must be outcome or net_benefit')
    cost_config = config.get('costs',{'amounts':[0.0]*k,'unit':spec['unit'],'benefit_per_outcome':1.0})
    if not isinstance(cost_config,dict) or set(cost_config)!={'amounts','unit','benefit_per_outcome'}:
        raise ValueError('policy costs requires amounts, unit and benefit_per_outcome')
    amounts = cost_config['amounts']; multiplier = cost_config['benefit_per_outcome']
    if (not isinstance(amounts,list) or len(amounts)!=k
            or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) or v<0 for v in amounts)
            or not isinstance(cost_config['unit'],str) or not cost_config['unit'].strip()
            or isinstance(multiplier,bool) or not isinstance(multiplier,(int,float)) or not np.isfinite(multiplier) or multiplier<=0):
        raise ValueError('policy costs need finite nonnegative arm amounts, a unit and positive benefit_per_outcome')
    costs = np.asarray(amounts,dtype=float)
    treatment = opt['treatment']; partition = opt['partition']; weight_col = opt.get('weights')
    columns = [spec['id'],spec['outcome'],treatment,partition,*spec['regressors'],*propensity_columns]
    if weight_col is not None: columns.append(weight_col)
    if cluster is not None: columns.append(cluster)
    if (not spec['regressors'] or any(not isinstance(c,str) or not c for c in columns)
            or len(set(columns))!=len(columns)):
        raise ValueError('policy requires distinct outcome, treatment, partition, covariate, propensity, weight and cluster columns')
    path = Path(spec['data']); path = (path if path.is_absolute() else spec_path.parent/path).resolve()
    data = research_data.read_frame(path, columns=columns, string_columns=[spec['id'],treatment,partition,*([cluster] if cluster else [])])
    if not set(columns)<=set(data.columns) or data[columns].isna().any().any():
        raise ValueError('policy input must contain complete declared columns; construct the adopted sample before learning')
    if data[spec['id']].duplicated().any() or data[spec['id']].str.strip().eq('').any():
        raise ValueError('policy IDs must be unique and nonempty')
    numeric = [spec['outcome'],*spec['regressors'],*propensity_columns,*([weight_col] if weight_col else [])]
    for col in numeric: data[col] = pd.to_numeric(data[col],errors='raise')
    if not np.isfinite(data[numeric].to_numpy(dtype=float)).all():
        raise ValueError('policy numeric inputs must be finite')
    if set(data[partition])!={'train','evaluation'} or set(data[treatment])!=set(arms):
        raise ValueError('policy data must contain train/evaluation partitions and precisely the declared arms')
    train = data.loc[data[partition]=='train'].reset_index(drop=True)
    evaluation = data.loc[data[partition]=='evaluation'].reset_index(drop=True)
    if len(evaluation)<2 or train[treatment].nunique()!=k or train[treatment].value_counts().min()<folds:
        raise ValueError('policy needs two evaluation observations and at least n_folds training observations per arm')
    weights = np.ones(len(data)) if weight_col is None else data[weight_col].to_numpy(dtype=float)
    if (weights<=0).any(): raise ValueError('policy target weights must be positive')
    tw = weights[data[partition].eq('train')]; ew = weights[data[partition].eq('evaluation')]
    if cluster:
        if set(train[cluster]) & set(evaluation[cluster]):
            raise ValueError('policy training and evaluation clusters must be disjoint')
        if train[cluster].nunique()<folds or evaluation[cluster].nunique()<2:
            raise ValueError('policy needs n_folds training clusters and at least two evaluation clusters')
    probabilities = data[propensity_columns].to_numpy(dtype=float) if known else None
    if known and ((probabilities<=0).any() or (probabilities>=1).any()
            or not np.allclose(probabilities.sum(axis=1),1,rtol=0,atol=1e-10)):
        raise ValueError('known policy probabilities must be in (0,1) and sum to one in every row')
    if fixed_batch and cluster:
        if (data.groupby(cluster)[treatment].nunique()!=1).any() or any(
                (data.groupby(cluster)[column].nunique()!=1).any() for column in propensity_columns):
            raise ValueError('fixed_batch cluster assignment requires one realized arm and probability vector per cluster')
    features = train[spec['regressors']].to_numpy(); evaluation_features = evaluation[spec['regressors']].to_numpy()
    arm_index = {arm:i for i,arm in enumerate(arms)}
    train_arm = train[treatment].map(arm_index).to_numpy(dtype=int)
    train_y = train[spec['outcome']].to_numpy(dtype=float)
    default_learners = {'ml_g':{'type':'random_forest_regressor','params':{'n_estimators':100,'min_samples_leaf':5}}}
    if not known: default_learners['ml_m'] = {'type':'logistic','params':{'max_iter':1000}}
    learner_config = config.get('learners',default_learners)
    if not isinstance(learner_config,dict) or set(learner_config)!=set(default_learners):
        raise ValueError('policy learners requires ml_g and, for estimated propensity, ml_m')
    learners,effective_learners = _nuisance_learners(learner_config,seed)
    if not is_regressor(learners['ml_g']) or not known and not is_classifier(learners['ml_m']):
        raise ValueError('policy ml_g must be a regressor and ml_m a probability classifier')

    def nuisance_prediction(fit_rows, predict_features):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',ConvergenceWarning)
                means = np.column_stack([clone(learners['ml_g']).fit(features[fit_rows][train_arm[fit_rows]==a],
                    train_y[fit_rows][train_arm[fit_rows]==a],sample_weight=tw[fit_rows][train_arm[fit_rows]==a]).predict(predict_features)
                    for a in range(k)])
                probs = None
                if not known:
                    model = clone(learners['ml_m']).fit(features[fit_rows],train_arm[fit_rows],sample_weight=tw[fit_rows])
                    probs = model.predict_proba(predict_features)[:,np.argsort(model.classes_)]
        except ConvergenceWarning as exc:
            raise ArithmeticError('policy nuisance model did not converge: '+str(exc)) from exc
        return means,probs

    splitter = (StratifiedGroupKFold if cluster else StratifiedKFold)(n_splits=folds,shuffle=True,random_state=seed)
    split = splitter.split(features,train_arm,train[cluster] if cluster else None)
    train_means = np.empty((len(train),k)); train_probs = probabilities[data[partition].eq('train')].copy() if known else np.empty_like(train_means)
    fold_records = []
    for fit_rows,score_rows in split:
        if set(train_arm[fit_rows])!=set(range(k)):
            raise ValueError('each policy nuisance training fold must contain every arm')
        means,probs = nuisance_prediction(fit_rows,features[score_rows])
        train_means[score_rows] = means
        if not known: train_probs[score_rows] = probs
        fold_records.append({'train_ids':train.iloc[fit_rows][spec['id']].tolist(),'score_ids':train.iloc[score_rows][spec['id']].tolist()})
    evaluation_means,evaluation_probs = nuisance_prediction(np.arange(len(train)),evaluation_features)
    if known: evaluation_probs = probabilities[data[partition].eq('evaluation')]
    if any(not np.isfinite(a).all() for a in (train_means,train_probs,evaluation_means,evaluation_probs)) or any(
            (a<=0).any() or (a>=1).any() for a in (train_probs,evaluation_probs)):
        raise ArithmeticError('policy nuisance predictions require finite means and positive probabilities without clipping')
    rewards = train_means.copy()
    rewards[np.arange(len(train)),train_arm] += (train_y-train_means[np.arange(len(train)),train_arm])/train_probs[np.arange(len(train)),train_arm]
    tree_options = {'max_depth':2,'min_samples_leaf':10,'honest':False,**config.get('tree',{})}
    if set(tree_options)-{'max_depth','min_samples_leaf','min_samples_split','min_balancedness_tol','honest'}:
        raise ValueError('policy tree accepts depth, leaf/split sizes, balancedness and honesty')
    tree_rewards = multiplier*rewards-costs if objective=='net_benefit' else rewards
    tree = PolicyTree(random_state=seed,**tree_options).fit(features,tree_rewards,sample_weight=tw)
    predictions = tree.predict_value(evaluation_features)
    chosen,allocation = _policy_assignment(predictions,ew,costs,baseline,constraints)
    # Only this evaluation stage consumes held-out treatments and outcomes.
    n = len(evaluation); observed = evaluation[treatment].map(arm_index).to_numpy(dtype=int)
    observed_y = evaluation[spec['outcome']].to_numpy(dtype=float); index = np.arange(n)
    q = evaluation_means if config['value_method']=='aipw' else np.zeros_like(evaluation_means)
    corrections = np.zeros_like(q)
    corrections[index,observed] = (observed_y-q[index,observed])/evaluation_probs[index,observed]
    arm_scores = q+corrections
    if not np.isfinite(arm_scores).all():
        raise ArithmeticError('policy evaluation scores are nonfinite at the supplied propensities')
    values = arm_scores[index,chosen]; base_values = arm_scores[:,baseline]
    scores = {'policy_value':values,'baseline_value':base_values,'policy_value_gain':values-base_values,
        'policy_cost':costs[chosen],'baseline_cost':np.full(n,costs[baseline]),
        'policy_net_benefit':multiplier*values-costs[chosen],
        'baseline_net_benefit':multiplier*base_values-costs[baseline],
        'policy_net_gain':multiplier*(values-base_values)-(costs[chosen]-costs[baseline])}
    innovation = {'policy_value':corrections[index,chosen],'baseline_value':corrections[:,baseline]}
    innovation['policy_value_gain'] = innovation['policy_value']-innovation['baseline_value']
    innovation.update(policy_cost=np.zeros(n),baseline_cost=np.zeros(n),
        policy_net_benefit=multiplier*innovation['policy_value'],baseline_net_benefit=multiplier*innovation['baseline_value'],
        policy_net_gain=multiplier*innovation['policy_value_gain'])
    for a,arm in enumerate(arms):
        scores['arm_value.'+arm] = arm_scores[:,a]; innovation['arm_value.'+arm] = corrections[:,a]
        scores['assignment_rate.'+arm] = (chosen==a).astype(float); innovation['assignment_rate.'+arm] = np.zeros(n)
    names = list(scores); matrix = np.column_stack(list(scores.values()))
    estimates = np.average(matrix,axis=0,weights=ew)
    influence = np.column_stack([innovation[name] for name in names]) if fixed_batch else matrix-estimates
    influence *= ew[:,None]/ew.sum()
    group_count = int(evaluation[cluster].nunique()) if cluster else n
    if cluster: influence = pd.DataFrame(influence).groupby(evaluation[cluster].to_numpy(),sort=False).sum().to_numpy()
    covariance = S_white_simple(influence)*(1.0 if fixed_batch else group_count/(group_count-1))
    if not np.isfinite(covariance).all():
        raise ArithmeticError('policy score covariance is nonfinite')
    reference = 'normal' if fixed_batch or not cluster else 'Student t'
    critical = norm.ppf((1+level)/2) if reference=='normal' else student_t.ppf((1+level)/2,group_count-1)
    rows = []; coefficients = {}; standard_errors = {}; intervals = {}; p_values = {}; statistics = {}
    native_values = {}
    for j,name in enumerate(names):
        estimate = float(estimates[j]); se = float(np.sqrt(max(covariance[j,j],0)))
        ci = [estimate-critical*se,estimate+critical*se]
        if not fixed_batch:
            kwargs = {'cov_type':'cluster','cov_kwds':{'groups':evaluation[cluster],'use_correction':True},'use_t':True} if cluster else {'cov_type':'HC1'}
            fitted = sm.WLS(matrix[:,j],np.ones((n,1)),weights=ew).fit(**kwargs)
            estimate = float(fitted.params[0]); se = float(fitted.bse[0]); ci = fitted.conf_int(alpha=1-level)[0].tolist()
            if not cluster and weight_col is None and (name in ('policy_value','baseline_value') or name.startswith('arm_value.')):
                action = chosen if name=='policy_value' else np.full(n,baseline if name=='baseline_value' else arms.index(name.split('.',1)[1]))
                target = np.eye(k)[action]
                args = {'pi_behavior':evaluation_probs[index,observed],'clip':np.inf,'alpha':1-level}
                official = (doubly_robust(evaluation_features,observed,observed_y,target,q_hat=q,n_actions=k,**args)
                    if config['value_method']=='aipw' else ips(evaluation_features,observed,observed_y,target,**args))
                estimate,se,ci = float(official.value),float(official.se),list(official.ci)
                native_values[name] = {'function':official.method,'value':estimate,'se':se,'interval':ci}
        unit = ('probability' if name.startswith('assignment_rate.') else cost_config['unit']
            if name in ('policy_cost','baseline_cost','policy_net_benefit','baseline_net_benefit','policy_net_gain') else spec['unit'])
        pvalue = float(2*(norm.sf(abs(estimate/se)) if reference=='normal' else student_t.sf(abs(estimate/se),group_count-1))) if se>0 else None
        coefficients[name] = estimate; standard_errors[name] = se; intervals[name] = ci; p_values[name] = pvalue
        rows.append({'term':name,'estimate':estimate,'se':se,'ci_low':ci[0],'ci_high':ci[1],'p_value':pvalue,'n':n,'unit':unit})
        for stat,value in (('coefficient',estimate),('standard_error',se),('confidence_lower',ci[0]),('confidence_upper',ci[1])):
            statistics[stat+'.'+name] = {'value':value,'unit':unit}
    rule = tree.tree_
    policy_definition = {**deepcopy(config),'arms':arms,'training_partition':'train','evaluation_partition':'evaluation',
        'n_folds':folds,'tree':tree_options,'learners':learner_config,'objective':objective,'costs':cost_config,
        'learning_score':'cross-fitted arm AIPW rewards','nuisance_fit_population':'training partition only',
        'evaluation_nuisance_fit':'all training rows; no evaluation outcomes or assignments',
        'fold_unit':cluster or spec['id'],'allocation':allocation['method'],
        'resource_population':'unweighted evaluation-row counts and total costs',
        'value_population':'fixed evaluation cohort conditional on covariates, training fit and actions' if fixed_batch else 'holdout target population conditional on the trained tree'}
    inference = {'reference':reference,'confidence_level':level,'interval_type':'pointwise',
        'procedure':'conservative conditional randomization residual second moment' if fixed_batch else 'independent holdout weighted mean with HC1/cluster covariance',
        'independent_units':group_count,'cluster':cluster,'degrees_of_freedom':group_count-1 if reference=='Student t' else None,
        'conditional_on':['training fit','evaluation covariates','allocated actions'] if fixed_batch else ['training fit'],
        'covariance_target':'upper bound on conditional assignment variance' if fixed_batch else 'target-population mean covariance',
        'finite_sample_adjustment':1.0 if fixed_batch else group_count/(group_count-1),
        'variance_formula':'sum_g u_g u_g.T; u_g=sum_i_in_g normalized_weight_i * IPW_residual_correction_i' if fixed_batch else 'G/(G-1) sum_g centered_weighted_score_g centered_weighted_score_g.T',
        'confidence_intervals':intervals,'p_values':p_values}
    versions = {'python':sys.version.split()[0],'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,
        'statsmodels':statsmodels.__version__,'econml':econml.__version__,'scikit-learn':sklearn.__version__,'statspai':statspai.__version__}
    engine = 'econml.policy.PolicyTree + '+('scipy.optimize.milp + ' if constraints else '')+(
        'statsmodels.stats.sandwich_covariance.S_white_simple' if fixed_batch else 'statsmodels.WLS')
    if native_values: engine += ' + statspai.policy_learning.ope'
    adopted = {key:deepcopy(spec[key]) for key in ('population','period','unit','estimand','identification','assignment')}
    adopted.update(policy=policy_definition,weights={'column':weight_col,'meaning':'positive pretreatment target-population weights','normalization':'sum to one within the evaluation population'},inference=deepcopy(inf))
    metadata = {**adopted,'engine':engine,'inference':inference,'result_format_version':1}
    leaf_ids = tree.apply(evaluation_features)
    assignment_rows = [{'id':str(row_id),'action':arms[a],'tree_action':arms[int(predictions[i].argmax())],
        'leaf':int(leaf_ids[i]),'weight':float(ew[i]),'cost':float(costs[a]),
        'expected_outcome':float(evaluation_means[i,a]),'expected_benefit':float(multiplier*evaluation_means[i,a]),
        'expected_effect':float(evaluation_means[i,a]-evaluation_means[i,baseline]),
        'expected_net_benefit':float(multiplier*evaluation_means[i,a]-costs[a]),
        'selection_prediction':float(predictions[i,a])} for i,(row_id,a) in enumerate(zip(evaluation[spec['id']],chosen))]
    group_outcomes = (predictions+costs)/multiplier if objective=='net_benefit' else predictions
    group_rows = [{'leaf':int(leaf_ids[i]),'arm':arm,'expected_outcome':float(group_outcomes[i,a]),
        'expected_effect':float(group_outcomes[i,a]-group_outcomes[i,baseline]),
        'expected_net_benefit':float(multiplier*group_outcomes[i,a]-costs[a]),
        'tree_action':arms[int(predictions[i].argmax())]} for i in np.unique(leaf_ids,return_index=True)[1] for a,arm in enumerate(arms)]
    forecast_columns = [{'key':key,'label':key.replace('_',' ').title(),'unit':unit} for key,unit in (
        ('expected_outcome',spec['unit']),('expected_effect',spec['unit']),
        ('expected_benefit',cost_config['unit']),('expected_net_benefit',cost_config['unit']),('cost',cost_config['unit']))]
    return {'method':'policy_tree','result_format_version':1,'engine':engine,'versions':versions,'options':opt,'adopted':adopted,
        'sample':{'id_column':spec['id'],'input_rows':len(data),'observations':n,'included_ids':evaluation[spec['id']].tolist(),
            'training_ids':train[spec['id']].tolist(),'excluded_incomplete_ids':[],'complete_case_columns':columns},
        'coefficients':coefficients,'standard_errors':standard_errors,
        'covariance_kind':inference['covariance_target'],
        'covariance':{a:{b:float(covariance[i,j]) for j,b in enumerate(names)} for i,a in enumerate(names)},
        'inference':inference,'statistics':statistics,'display':{'kind':'table','rows':rows,'metadata':metadata,
            'columns':[{'key':key,'label':label,'unit':unit} for key,label,unit in (
                ('term','Quantity',''),('estimate','Estimate',''),('se','Standard error',''),
                ('ci_low','Lower',''),('ci_high','Upper',''),('p_value','p value','probability'),
                ('n','Observations','observations'),('unit','Unit',''))],
            'display':{'column_order':['term','estimate','se','ci_low','ci_high','unit']}},
        'displays':{'policy_assignments':{'kind':'table','rows':assignment_rows,
            'columns':[{'key':key,'label':key.replace('_',' ').title(),'unit':''} for key in ('id','action','tree_action','leaf','weight')]+forecast_columns+
                [{'key':'selection_prediction','label':'Selection prediction',
                  'unit':cost_config['unit'] if objective=='net_benefit' else spec['unit']}],
            'metadata':{**metadata,'unit':cost_config['unit'],
                'estimand':'Frozen assignments, resources and training-model conditional predictions','interval_type':'none','inference':{'type':'none'}}},
            'policy_groups':{'kind':'table','rows':group_rows,
                'columns':[{'key':key,'label':key.replace('_',' ').title(),'unit':''} for key in ('leaf','arm','tree_action')]
                    +[column for column in forecast_columns if column['key'] in ('expected_outcome','expected_effect','expected_net_benefit')],
                'metadata':{**metadata,'estimand':'Native tree leaf predictions by arm; effects relative to the declared baseline',
                    'interval_type':'none','inference':{'type':'none'}}}},
        'diagnostics':{'folds':fold_records,'learners':effective_learners,'allocation':allocation,'native_values':native_values,
            'tree':{'children_left':rule.children_left.tolist(),'children_right':rule.children_right.tolist(),
                'feature':rule.feature.tolist(),'threshold':rule.threshold.tolist(),'value':rule.value.tolist(),
                'feature_names':spec['regressors'],'arm_names':arms},
            'training_reward_matrix':rewards.tolist(),'training_nuisance_predictions':train_means.tolist(),
            'training_propensities':train_probs.tolist(),'evaluation_nuisance_predictions':evaluation_means.tolist(),
            'evaluation_effect_predictions':(evaluation_means-evaluation_means[:,[baseline]]).tolist(),
            'evaluation_policy_predictions':predictions.tolist(),
            'evaluation_propensities':evaluation_probs.tolist(),'evaluation_scores':{name:values.tolist() for name,values in scores.items()},
            'evaluation_assignment_corrections':{name:values.tolist() for name,values in innovation.items()},
            'assignment_counts':{arm:int((chosen==a).sum()) for a,arm in enumerate(arms)},
            'total_cost':float(costs[chosen].sum()),'weighted_expected_benefit':float(np.average(multiplier*evaluation_means[index,chosen],weights=ew)),
            'weighted_expected_net_gain':float(np.average(multiplier*(evaluation_means[index,chosen]-evaluation_means[:,baseline])-(costs[chosen]-costs[baseline]),weights=ew)),
            'training_weight_sum':float(tw.sum()),'evaluation_weight_sum':float(ew.sum()),
            'cluster_labels':evaluation[cluster].tolist() if cluster else None,
            'official_api':{function.__qualname__:str(inspect.signature(function)) for function in (PolicyTree,PolicyTree.fit,doubly_robust,ips,S_white_simple)}},
        'provenance':{'data_path':str(path),'data_sha256':_hash(path),'spec_path':str(spec_path.resolve()),'spec_sha256':_hash(spec_path),
            'ope_source_sha256':_hash(Path(ope_module.__file__))}}


def run(spec, spec_path):
    import research_data
    if isinstance(spec, dict) and 'data_record' in spec:
        return research_data.execute_with_data_record(run, spec, spec_path)
    if not isinstance(spec, dict) or set(spec) != RUN_FIELDS:
        raise ValueError('specification must contain exactly the documented fields')
    method = spec['method']
    methods = {'fixed_effects_julia','survival','oaxaca','gls','iv_gmm','iv_ar','panel_fe','quantile','poisson','logit','rct','rdd_sharp','rdd_fuzzy','hdfe','causal_forest','spatial_lag','rdd_localrand','shift_share','policy_tree','network_spillover','tobit','dynamic_panel','synthetic_control','staggered_did','generalized_synth','multitreatment_did','distribution_effect'} | set(R_METHODS) | set(DML_METHODS) | STATSPAI_METHODS | set(INFERENCE_METHODS) | set(CAUSAL_EXTENSIONS)
    if method not in methods:
        raise ValueError('unsupported method')
    for key in ('data','id','outcome','population','period','unit','estimand','identification','assignment'):
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise ValueError(f'{key} must be a nonempty string')
    for key in ('regressors','endogenous','instruments'):
        v = spec[key]
        if not isinstance(v, list) or any(not isinstance(x,str) or not x for x in v) or len(set(v)) != len(v):
            raise ValueError(f'{key} must be a list of distinct column names')
    if method in ('dml_pliv','dml_iivm'):
        if len(spec['endogenous']) != 1 or not spec['instruments'] or (method=='dml_iivm' and len(spec['instruments'])!=1):
            raise ValueError('PLIV requires one endogenous treatment and instruments; IIVM requires exactly one instrument')
    elif method in ('dml_ssm','dml_qte'):
        if spec['endogenous']:
            raise ValueError('SSM and QTE bind treatment through options.treatment')
    elif method in ('shift_share','shift_share_inference'):
        if len(spec['endogenous']) != 1 or spec['instruments']: raise ValueError('shift_share requires one endogenous regressor and no input instruments')
    elif method in ('iv_gmm','iv_ar','iv_ar_robust') or method == 'fixed_effects_julia' and (spec['endogenous'] or spec['instruments']):
        if not spec['endogenous'] or len(spec['instruments']) < len(spec['endogenous']):
            raise ValueError('IV GMM requires endogenous regressors and at least as many instruments')
    elif spec['endogenous'] or spec['instruments']:
        raise ValueError('endogenous and instruments are reserved for IV methods')
    if method in ('iv_ar','iv_ar_robust') and len(spec['endogenous']) != 1:
        raise ValueError('Anderson-Rubin methods require one endogenous regressor')
    if not isinstance(spec['options'],dict):
        raise ValueError('options must be an object')
    if method in INFERENCE_METHODS:
        return _inference_extensions(spec,spec_path)
    if method in CAUSAL_EXTENSIONS:
        return _causal_extensions(spec,spec_path)
    if method == 'fixed_effects_julia':
        return _fixed_effects_julia(spec,spec_path)
    if method == 'policy_tree' and 'policy' in spec['options']:
        return _policy_tree(spec, spec_path)
    if method in STATSPAI_METHODS:
        return _statspai(spec, spec_path)
    if method == 'rct_design':
        return _rct_design(spec, spec_path)
    if method in R_METHODS:
        return _official_r(spec, spec_path)
    if method in ('survival','oaxaca'):
        return _survival_or_oaxaca(spec, spec_path)
    import numpy as np
    import pandas as pd
    import scipy
    import statsmodels
    import statsmodels.api as sm
    opt = spec['options']
    required = ({'score','n_folds','seed','learners'} | ({'treatment'} if method in DML_TREATMENT_METHODS else set())
        | {'dml_did':{'outcome_pre'},'dml_ssm':{'selection'},'dml_qte':{'quantiles'},
           'dml_pq':{'quantile','treatment_level'},'dml_cvar':{'quantile','treatment_level'},
           'dml_apo':{'treatment_level'}}.get(method,set()) if method in DML_METHODS else
        {'gls': {'variance'}, 'iv_gmm': set(), 'iv_ar': {'alpha'}, 'panel_fe': {'entity','time','entity_effects','time_effects'},
                'quantile': {'quantile'}, 'poisson': set(), 'logit': set(), 'rct': {'treatment','permutations','seed'}, 'rdd_sharp': {'running','cutoff','bandwidth'}, 'rdd_fuzzy': {'running','cutoff','bandwidth','treatment'}, 'hdfe': {'fixed_effects'}, 'causal_forest': {'treatment','seed','trees','min_leaf'}, 'spatial_lag': {'weights'}, 'rdd_localrand': {'running','cutoff','bandwidth','permutations','seed'}, 'shift_share': {'shares','shocks'}, 'policy_tree': {'treatment','propensity','partition','seed'}, 'network_spillover': {'weights','treatment'}, 'tobit': {'lower'}, 'dynamic_panel': {'entity','time'}, 'synthetic_control': {'entity','time','treated','training_end','pre_end'}, 'staggered_did': {'entity','time','cohort','control_group'}, 'generalized_synth': {'entity','time','treatment','factors','bootstraps','seed'}, 'multitreatment_did': {'entity','time','pre','post','treatments'}, 'distribution_effect': {'treatment','threshold'}}[method])
    optional = ({'panel','allow_unbalanced_panel','anticipation','weightsname','fix_weights',
                 'alp','bstrap','biters','clustervars','cband','est_method','base_period',
                 'faster_mode','seed','aggregation'} if method == 'staggered_did' else set())
    if method == 'hdfe':
        optional = {'weights','weights_type','ssc','vcov','confidence_level'}
    if method in DML_METHODS:
        optional = {'n_rep','confidence_level','joint','bootstrap','sample_splitting','definitions'}
        if method not in ('dml_plr','dml_pliv','dml_did'):
            optional |= {'normalize_ipw','trimming_rule','trimming_threshold','ps_processor_config'}
        optional |= {'weights'} if method in ('dml_irm','dml_apo') else {'subgroups'} if method=='dml_iivm' else set()
        if method == 'dml_did':
            optional |= {'in_sample_normalization','clipping_threshold'}
    if not required <= set(opt) or set(opt) - required - optional:
        raise ValueError(f'{method} options must contain exactly {sorted(required)}')
    if method == 'dml_ssm':
        if (opt['score'] == 'nonignorable') != bool(spec['instruments']):
            raise ValueError('SSM nonignorable requires selection instruments; missing-at-random requires instruments=[]')
    if method == 'dml_qte':
        if (opt['score'] == 'LPQ' and len(spec['instruments']) != 1
                or opt['score'] != 'LPQ' and spec['instruments']):
            raise ValueError('QTE LPQ requires exactly one binary instrument; PQ and CVaR require instruments=[]')
    inf = spec['inference']
    if not isinstance(inf,dict) or inf.get('type') not in ('official','robust','cluster','homoskedastic','randomization','rdrobust','forest','spatial_ml','policy','likelihood','dynamic_gmm','synthetic_holdout','did','gsynth'):
        raise ValueError('unsupported inference type; see causal-models.md')
    dml_clusters = []
    if method in DML_METHODS:
        if inf['type'] == 'cluster':
            if set(inf) not in ({'type','cluster'},{'type','clusters'}):
                raise ValueError('DoubleML cluster inference requires cluster or clusters')
            dml_clusters = inf.get('clusters',[inf.get('cluster')])
            if (not isinstance(dml_clusters,list) or not 1 <= len(dml_clusters) <= 2
                    or any(not isinstance(col,str) or not col for col in dml_clusters)
                    or len(set(dml_clusters)) != len(dml_clusters)):
                raise ValueError('DoubleML requires one or two distinct cluster columns')
        elif inf != {'type':'official'}:
            raise ValueError('DoubleML uses official orthogonal-score inference or declared clustering')
    elif inf['type'] == 'official':
        raise ValueError('official inference is reserved for official estimator calls')
    elif set(inf) != ({'type','cluster'} if inf['type']=='cluster' else {'type'}):
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
             [opt['treatment'],opt['outcome_pre']] if method == 'dml_did' else
             [opt['treatment'],opt['selection']] if method == 'dml_ssm' else
             [opt['treatment']] if method in DML_TREATMENT_METHODS or method == 'causal_forest' else
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
    if method == 'hdfe' and opt.get('weights') is not None:
        columns.append(opt['weights'])
    if method in ('dml_irm','dml_apo') and isinstance(opt.get('weights'),str):
        columns.append(opt['weights'])
    if method in DML_METHODS:
        columns += dml_clusters
    elif inf['type']=='cluster': columns += [inf['cluster']]
    if any(not isinstance(x,str) or not x for x in columns): raise ValueError('column names must be nonempty strings')
    roles = [spec['id'],spec['outcome'],*spec['regressors'],*spec['endogenous'],*spec['instruments']]
    if method in DML_TREATMENT_METHODS: roles.append(opt['treatment'])
    if method == 'dml_did': roles.append(opt['outcome_pre'])
    if method == 'dml_ssm': roles.append(opt['selection'])
    if method in DML_METHODS and set(dml_clusters) & set(roles[1:]):
        raise ValueError('DoubleML cluster columns must be distinct from model columns')
    if len(set(roles)) != len(roles) or 'const' in roles: raise ValueError('model column roles must be distinct; const is reserved')
    p = Path(spec['data']); p = (p if p.is_absolute() else spec_path.parent / p).resolve()
    df = research_data.read_frame(p, columns=list(dict.fromkeys(columns)), string_columns=[spec['id']])
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
    if method == 'hdfe' and opt.get('weights') is not None: numeric.append(opt['weights'])
    if method == 'policy_tree': numeric.extend([opt['treatment'],opt['propensity']])
    if method == 'shift_share': numeric.extend(opt['shares'])
    if method == 'gls': numeric.append(opt['variance'])
    if method in DML_TREATMENT_METHODS or method in ('rdd_fuzzy','causal_forest'): numeric.append(opt['treatment'])
    if method == 'dml_did': numeric.append(opt['outcome_pre'])
    if method == 'dml_ssm': numeric.append(opt['selection'])
    if method in ('dml_irm','dml_apo') and isinstance(opt.get('weights'),str): numeric.append(opt['weights'])
    for c in numeric: df[c] = pd.to_numeric(df[c], errors='raise').astype(float)
    complete_columns = [c for c in numeric if method != 'dml_ssm' or c != spec['outcome']]
    selected = np.isfinite(df[complete_columns].to_numpy(dtype=float)).all(axis=1)
    if method == 'dml_ssm':
        selected &= df[opt['selection']].eq(0) | np.isfinite(df[spec['outcome']].to_numpy())
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
    X = None if method in DML_METHODS else sm.add_constant(d[spec['regressors']],has_constant='add')
    if X is not None and (np.linalg.matrix_rank(X.to_numpy()) != X.shape[1] or len(d)<=X.shape[1]): raise ValueError('design must have full rank and residual degrees of freedom')
    groups = None
    if inf['type']=='cluster' and method not in DML_METHODS:
        groups = d[inf['cluster']]
        if groups.nunique()<2: raise ValueError('at least two clusters required')
    versions = {'python':sys.version.split()[0], 'numpy':np.__version__, 'pandas':pd.__version__, 'scipy':scipy.__version__, 'statsmodels':statsmodels.__version__}
    diagnostics = {}; fit_n=None; did_values=None; confidence_level=0.95
    if method in DML_METHODS:
        fit, ci, dml_folds, diagnostics, dml_versions = _doubleml(spec, d, dml_clusters, input_rows)
        versions.update(dml_versions)
        term = opt['treatment'] if method in DML_TREATMENT_METHODS else spec['endogenous'][0]
        terms = [f'{term}.quantile_{float(q)}' for q in fit.quantiles] if method == 'dml_qte' else [term]
        coef = pd.Series(fit.coef,index=terms); se = pd.Series(fit.se,index=terms)
        pv = pd.Series(fit.pval,index=terms); ci = ci.set_axis(terms,axis=0)
        cov = pd.DataFrame(np.nan,index=terms,columns=terms)
        for name,value in se.items(): cov.loc[name,name] = float(value**2)
        reference = 'normal'; engine = ('doubleml.did.' if method == 'dml_did' else 'doubleml.')+DML_METHODS[method]
        confidence_level = opt.get('confidence_level',.95)
    elif method == 'distribution_effect':
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
        rcode=research_data.R_READ_TABLE+"""
args<-commandArgs(trailingOnly=TRUE); suppressPackageStartupMessages(library(gsynth)); suppressPackageStartupMessages(library(jsonlite))
outcome<-args[2]; unit<-args[3]; tm<-args[4]; treat<-args[5]; covars<-strsplit(args[6],',',fixed=TRUE)[[1]]; rank<-as.integer(args[7]); boots<-as.integer(args[8]); seed<-as.integer(args[9])
d<-ers_read_table(args[1],columns=unique(c(outcome,unit,tm,treat,covars))); d[[unit]]<-as.integer(as.factor(d[[unit]])); f<-reformulate(c(treat,covars),response=outcome)
z<-gsynth(f,data=d,index=c(unit,tm),force='two-way',r=rank,CV=FALSE,se=TRUE,nboots=boots,inference='parametric',parallel=FALSE,seed=seed)
bb<-rbind(z$att.avg.boot,z$att.boot); vv<-cov(t(bb)); obj<-list(r_version=as.character(getRversion()),gsynth_version=as.character(packageVersion('gsynth')),events=as.numeric(rownames(z$est.att)),coef=c(z$att.avg,z$est.att[,'ATT']),engine_se=c(z$est.avg[1,'S.E.'],z$est.att[,'S.E.']),cov=unname(vv),rmse=z$rmse,iterations=z$niter,rank=z$r.cv,treated=z$Ntr,controls=z$Nco)
write_json(obj,args[10],auto_unbox=TRUE,digits=16,na='null',null='null')
"""
        with tempfile.TemporaryDirectory(prefix='causal-gsynth-') as tmp:
            result_file = Path(tmp)/'result.json'
            proc=subprocess.run([*research_data.companion_command('r'),'-',str(p),spec['outcome'],entity,time,treatment,','.join(spec['regressors']),str(rank),str(boots),str(seed),str(result_file)],input=rcode,text=True,env=os.environ.copy())
            if proc.returncode: raise ArithmeticError(f'gsynth engine failed with return code {proc.returncode}')
            values = json.loads(result_file.read_text(encoding='utf-8'))
        versions['R']=values['r_version']; versions['gsynth']=values['gsynth_version']; events=np.atleast_1d(values['events']); names=['overall']+[('event_m'+str(abs(int(x))) if x<0 else 'event_p'+str(int(x))) for x in events]; vals=np.atleast_1d(values['coef']); covariance=np.atleast_2d(values['cov']);
        if not np.isfinite(vals.astype(float)).all() or not np.isfinite(covariance.astype(float)).all(): raise ArithmeticError('gsynth returned nonfinite estimates')
        coef=pd.Series(vals,index=names,dtype=float); cov=pd.DataFrame(covariance,index=names,columns=names,dtype=float); se=pd.Series(np.sqrt(np.diag(cov)),index=names)
        if not np.allclose(se.to_numpy(),np.atleast_1d(values['engine_se']),rtol=1e-7,atol=1e-9): raise ArithmeticError('bootstrap covariance does not match gsynth standard errors')
        pv=pd.Series(2*norm.sf(np.abs(coef/se)),index=names); ci=pd.DataFrame({0:coef-norm.ppf(.975)*se,1:coef+norm.ppf(.975)*se}); reference='normal'; engine='R gsynth::gsynth'
        diagnostics={'factors':rank,'bootstraps':boots,'bootstrap':'parametric','seed':seed,'force':'two-way','cross_validation':False,'rmse':values['rmse'],'iterations':values['iterations'],'treated_units':int(values['treated']),'control_units':int(values['controls'])}
    elif method == 'staggered_did':
        from scipy.stats import norm
        did_values = _staggered_did(spec, d, p)
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
            'runtime':values['runtime'],'seed':opt.get('seed')}
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
        weights=np.asarray(model.W,dtype=float); synthetic=controls.to_numpy()@weights; gaps=target.to_numpy()-synthetic
        if not np.isfinite(weights).all() or weights.min() < -1e-7 or abs(weights.sum()-1)>1e-6: raise ArithmeticError('synthetic control optimizer produced invalid donor weights')
        held=validation|post; hold_gap=gaps[held]; post_indicator=np.asarray(post[held],dtype=float); XX=pd.DataFrame({'const':1.0,'post':post_indicator})
        fit=sm.OLS(hold_gap,XX).fit(cov_type='HC1'); fit_n=len(hold_gap); coef=fit.params; cov=fit.cov_params(); se=fit.bse; pv=fit.pvalues; ci=fit.conf_int(); reference='normal'; engine='pysyncon.Synth + statsmodels.OLS'
        training=d.loc[d[time]<=end,spec['id']].astype(str).tolist(); d=d.loc[d[time]>end].copy()
        diagnostics={'donor_weights':dict(zip(donor_names,[float(x) for x in weights])),'training_rmspe':float(np.sqrt(np.mean(gaps[tr]**2))),'validation_rmspe':float(np.sqrt(np.mean(gaps[validation]**2))),'period_gap':[{'time':float(t),'gap':float(g)} for t,g in zip(matrix.index,gaps)],'inference':'HC1 across held-out time gaps, conditional on training weights','training_periods':int(tr.sum()),'validation_periods':int(validation.sum()),'post_periods':int(post.sum())}
    elif method == 'dynamic_panel':
        import re
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
        result=regression.abond(command,d,[entity,time])
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
        confidence_level = opt.get('confidence_level', .95)
        if (isinstance(confidence_level, bool) or not isinstance(confidence_level, (int, float)) or
                not 0 < confidence_level < 1):
            raise ValueError('HDFE confidence_level must be between zero and one')
        weights_column = opt.get('weights')
        weights_type = opt.get('weights_type', 'aweights')
        if weights_type not in ('aweights', 'fweights'):
            raise ValueError('HDFE weights_type must be aweights or fweights')
        weights = d[weights_column].to_numpy(dtype=float) if weights_column is not None else np.ones(len(d))
        if np.any(weights <= 0) or (weights_type == 'fweights' and np.any(weights != np.floor(weights))):
            raise ValueError('HDFE weights must be positive; fweights must be integer frequencies')
        ssc_options = opt.get('ssc', {})
        if not isinstance(ssc_options, dict) or set(ssc_options)-{'k_adj','k_fixef','G_adj','G_df'}:
            raise ValueError('HDFE ssc accepts k_adj, k_fixef, G_adj and G_df')
        small_sample = pyfixest.ssc(**ssc_options)
        covariance = opt.get('vcov', {'CRV1': inf['cluster']} if groups is not None else 'hetero')
        if groups is None:
            if covariance not in ('hetero', 'HC1'):
                raise ValueError('HDFE robust inference requires vcov hetero or HC1')
        elif (not isinstance(covariance, dict) or len(covariance) != 1 or
              next(iter(covariance)) not in ('CRV1','CRV3') or next(iter(covariance.values())) != inf['cluster']):
            raise ValueError('HDFE cluster vcov must bind CRV1 or CRV3 to inference.cluster')
        formula=spec['outcome']+' ~ '+' + '.join(spec['regressors'])+' | '+' + '.join(opt['fixed_effects'])
        fit=pyfixest.feols(formula,d,vcov=covariance,weights=weights_column,weights_type=weights_type,
                           ssc=small_sample,fixef_rm='none')
        coef=fit.coef(); se=fit.se(); pv=fit.pvalue(); ci=fit.confint(alpha=1-confidence_level)
        cov=pd.DataFrame(fit._vcov,index=coef.index,columns=coef.index); reference='Student t'; engine='pyfixest.feols'
        fitted_ids = fit._data[spec['id']].astype(str).tolist()
        if (int(fit._N_rows) != len(d) or fitted_ids != d[spec['id']].astype(str).tolist() or
                list(coef.index) != spec['regressors']):
            raise ValueError('HDFE dropped observations or collinear regressors')
        fitted_weights = np.asarray(fit._weights, dtype=float).reshape(-1)
        if not np.array_equal(fitted_weights, weights):
            raise ArithmeticError('HDFE fitted weights differ from the declared complete-case weights')
        fit_n = int(fit._N_rows)
        diagnostics={'fixed_effects':opt['fixed_effects'],'levels':{k:int(d[k].nunique()) for k in opt['fixed_effects']},
            'singleton_policy':'retain','covariance':covariance,'degrees_of_freedom':float(fit._df_t),
            'effective_observations':float(fit._N),
            'weights':{'column':weights_column,'type':fit._weights_type,'values':fitted_weights.tolist(),
                       'total':float(fitted_weights.sum()),'row_order':'sample.included_ids'},
            'effective_options':{'weights':weights_column,'weights_type':fit._weights_type,'ssc':fit._ssc_dict,
                                 'vcov':covariance,'confidence_level':confidence_level,'fixef_rm':'none'}}
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
    arrays=[np.asarray(z,dtype=float) for z in ((coef,se,pv,ci) if method=='dml_qte' else (coef,cov,se,pv,ci))]
    if any(not np.isfinite(z).all() for z in arrays): raise ArithmeticError('estimator returned nonfinite inference')
    names=list(coef.index); vals=[float(v) for v in coef]; std=[float(v) for v in se]
    units={k:(spec['unit'] if k in ('const','treatment_effect','sample_ate','policy_value_gain','overall','post') or k.startswith(('event_','cohort_','time_')) else 'dimensionless' if k in ('spatial_lag','log_sigma','L1.'+spec['outcome']) else f"{spec['unit']} per one unit of {k}") for k in names}
    if method == 'distribution_effect':
        units = {key:'probability' for key in names}
    if method in DML_METHODS:
        units = {key:spec['unit'] for key in names}
    stats={f'coefficient.{k}':{'value':v,'unit':units[k]} for k,v in zip(names,vals)}
    stats.update({f'standard_error.{k}':{'value':v,'unit':units[k]} for k,v in zip(names,std)})
    stats.update({f'p_value.{k}':{'value':float(pv.loc[k]),'unit':'probability'} for k in names})
    level_label = format(100*confidence_level, '.8g')
    stats.update({f'confidence_{level_label}_lower.{k}':{'value':float(ci.loc[k].iloc[0]),'unit':units[k]} for k in names})
    stats.update({f'confidence_{level_label}_upper.{k}':{'value':float(ci.loc[k].iloc[1]),'unit':units[k]} for k in names})
    fit_n=len(d) if fit_n is None else fit_n
    stats['observations']={'value':int(fit_n),'unit':'fitted observations'}
    result = {'method':method,'engine':engine,'versions':versions,'options':opt,'adopted':{k:spec[k] for k in ('population','period','unit','estimand','identification','assignment','inference')},'sample':{'id_column':spec['id'],'included_ids':d[spec['id']].astype(str).tolist(),'excluded_incomplete_ids':excluded,'excluded_outside_window_ids':outside,'training_ids':training,'excluded_initial_lag_ids':initial_lags,'input_rows':int(input_rows),'observations':int(fit_n)},'coefficients':dict(zip(names,vals)),'standard_errors':dict(zip(names,std)),'covariance_kind':'upper bound on scalar variance' if method=='causal_forest' else 'estimator covariance','covariance':{a:{b:None if method=='dml_qte' and a!=b else float(cov.loc[a,b]) for b in names} for a in names},'inference':{'reference':reference,'p_values':{k:float(pv.loc[k]) for k in names},'confidence_level':confidence_level,'confidence_intervals':{k:[float(x) for x in ci.loc[k]] for k in names}},'diagnostics':diagnostics,'statistics':stats,'provenance':{'data_path':str(p),'data_sha256':_hash(p),'spec_path':str(spec_path.resolve()),'spec_sha256':_hash(spec_path)}}
    if confidence_level == 0.95:
        result['inference']['confidence_intervals_95'] = result['inference']['confidence_intervals']
    if method == 'distribution_effect':
        result.update(unit='probability', outcome=spec['outcome'], outcome_unit=spec['unit'],
                      threshold=float(threshold), threshold_unit=spec['unit'],
                      effect_scale='probability', coefficient_units=units,
                      covariance_unit='probability squared')
        result['inference'].update(unit='probability', interval_type='pointwise',
            standard_error_method='HC1' if groups is None else 'cluster with finite-sample correction')
        metadata = {key:result[key] for key in ('outcome','outcome_unit','threshold','threshold_unit')}
        metadata.update(estimand=spec['estimand'], population=spec['population'], period=spec['period'],
            treatment=treatment, assignment=spec['assignment'], confidence_level=confidence_level,
            interval_type='pointwise', producer={'function':engine,'versions':versions})
        for scale, factor, unit in (('probability', 1.0, 'probability'),
                                    ('percentage_point', 100.0, 'percentage points')):
            row = {'term':treatment, 'estimate':float(coef[treatment])*factor,
                   'se':float(se[treatment])*factor, 'p_value':float(pv[treatment]),
                   'ci_low':float(ci.loc[treatment].iloc[0])*factor,
                   'ci_high':float(ci.loc[treatment].iloc[1])*factor,
                   'n':int(fit_n), 'unit':unit}
            display_inference = {**result['inference'], 'unit':unit,
                'p_values':{treatment:row['p_value']},
                'confidence_intervals':{treatment:[row['ci_low'],row['ci_high']]}}
            if confidence_level == 0.95:
                display_inference['confidence_intervals_95'] = display_inference['confidence_intervals']
            block = {'kind':'coefficient', 'rows':[row],
                'columns':[{'key':key,'label':label,'unit':column_unit} for key,label,column_unit in (
                    ('term','Treatment',''), ('estimate','CDF difference',unit), ('se','Standard error',unit),
                    ('ci_low','Interval lower endpoint',unit), ('ci_high','Interval upper endpoint',unit),
                    ('p_value','p value','probability'), ('n','Observations','observations'), ('unit','Unit',''))],
                'metadata':{**metadata,'unit':unit,'effect_scale':scale,'scale_factor':factor,
                            'inference':display_inference}}
            if scale == 'probability':
                result['display'] = block
            else:
                result['displays'] = {'percentage_points':block}
                for key, column in (('coefficient_pp','estimate'), ('standard_error_pp','se'),
                                    (f'confidence_{level_label}_lower_pp','ci_low'),
                                    (f'confidence_{level_label}_upper_pp','ci_high')):
                    stats[f'{key}.{treatment}'] = {'value':row[column],'unit':unit}
    if method in DML_METHODS:
        result['folds'] = dml_folds
        result['sample']['complete_case_columns'] = list(dict.fromkeys(columns))
        result['design'] = {'outcome':spec['outcome'],'treatment':term,'covariates':spec['regressors'],
            'instruments':spec['instruments'],'score':opt['score'],'cluster_columns':dml_clusters}
        if method == 'dml_did':
            result['design'].update(outcome_pre=opt['outcome_pre'],outcome_transformation='post minus pre')
        if method == 'dml_ssm':
            observed = d[opt['selection']].eq(1)
            result['sample'].update(selection_ids=d[spec['id']].astype(str).tolist(),
                observed_outcome_ids=d.loc[observed,spec['id']].astype(str).tolist(),
                unselected_ids=d.loc[~observed,spec['id']].astype(str).tolist(),
                outcome_observation_rule=f"finite {spec['outcome']} required when {opt['selection']}=1")
            result['sample']['complete_case_columns'].remove(spec['outcome'])
            result['design']['selection'] = opt['selection']
        for key in ('treatment_level','quantile','quantiles'):
            if key in opt: result['design'][key] = opt[key]
        result['inference'].update(procedure='official cross-fitted orthogonal-score inference',
            interval_type='joint multiplier bootstrap' if opt.get('joint') else 'pointwise',
            standard_error_method='official clustered score variance' if dml_clusters else 'official score variance',
            repetitions=fit.n_rep, coefficient_aggregation='median over sample-splitting repetitions',
            interval_aggregation='official median of repetition-specific endpoints')
        targets = {
            'dml_plr':('partial_linear_slope','E[(D-m(X))*(Y-D*theta-g(X))]=0' if opt['score']=='IV-type'
                else 'E[(D-m(X))*(Y-l(X)-theta*(D-m(X)))]=0'),
            'dml_pliv':('partial_linear_iv_slope','E[(Z-m(X))*(Y-D*theta-g(X))]=0' if opt['score']=='IV-type'
                else 'E[(Z-m(X))*(Y-l(X)-theta*(D-r(X)))]=0'),
            'dml_did':('att','E[Y_post(1)-Y_post(0) | D=1]'),
            'dml_irm':('att','E[Y(1)-Y(0) | D=1]') if opt['score']=='ATTE' else ('ate','E[Y(1)-Y(0)]'),
            'dml_iivm':('late','E[Y(1)-Y(0) | complier]'),
            'dml_ssm':('ate','E[Y(1)-Y(0)]'),
            'dml_pq':('potential_quantile','Q_Y(d)(tau)'),
            'dml_cvar':('tail_mean','C_tau(d)=Q_Y(d)(tau)+E[(Y(d)-Q_Y(d)(tau))_+]/(1-tau)'),
            'dml_apo':('potential_mean','E[Y(d)]'),
        }
        if method == 'dml_qte':
            target_kind,target_expression = {'PQ':('qte','Q_Y(1)(tau)-Q_Y(0)(tau)'),
                'LPQ':('local_qte','Q_Y(1)|complier(tau)-Q_Y(0)|complier(tau)'),
                'CVaR':('tail_effect','C_tau(1)-C_tau(0)')}[opt['score']]
        else:
            target_kind,target_expression = targets[method]
        score_definition = {'model':DML_METHODS[method],'score':opt['score'],
            'target':{'kind':target_kind,'expression':target_expression,'adopted_estimand':spec['estimand']},
            'population':spec['population'],'period':spec['period'],'unit':spec['unit'],
            'treatment_column':term,'sample_ref':'sample','inference_ref':'inference',
            'weights':{'source':'options.weights' if 'weights' in opt else 'native unweighted target score',
                'normalization':'constructor weights are passed without rescaling',
                'score_weights_ref':'diagnostics.score_weights' if 'score_weights' in diagnostics else None,
                'normalize_ipw':diagnostics.get('normalize_ipw')},
            'sample_splitting':{'role':'nuisance learners train outside each scoring fold',
                'source':'adopted observation-ID folds' if 'sample_splitting' in opt else 'native seeded folds',
                'independent_unit_columns':dml_clusters or [spec['id']],
                'n_folds':opt['n_folds'],'n_rep':fit.n_rep,'seed':opt['seed'],'folds_ref':'folds'}}
        if method not in ('dml_plr','dml_pliv'):
            score_definition['treatment_levels'] = sorted(d[term].unique().tolist())
        if 'treatment_level' in opt:
            score_definition['treatment_level'] = opt['treatment_level']
        if method in ('dml_qte','dml_pq','dml_cvar'):
            score_definition['quantiles'] = list(map(float,opt['quantiles'] if method=='dml_qte' else [opt['quantile']]))
        if opt['score'] == 'CVaR':
            score_definition['tail'] = {'direction':'upper',
                'probabilities':[1-q for q in score_definition['quantiles']],
                'functional':'C_tau(d)=q_tau(d)+E[(Y(d)-q_tau(d))_+]/(1-tau)'}
        if 'nested_sample_splitting' in diagnostics:
            score_definition['sample_splitting'].update(
                nested_folds_ref='diagnostics.nested_sample_splitting',
                nested_role='preliminary selection propensity' if method=='dml_ssm'
                    else 'preliminary potential quantile and threshold-dependent nuisance training')
        if method == 'dml_ssm':
            score_definition['selection'] = {'column':opt['selection'],'mechanism':opt['score'],
                'excluded_instruments':spec['instruments'],
                'population':'all retained selection-sample observations',
                'conditions':['treatment exchangeability given X','treatment and selection positivity'] +
                    (['outcome-selection exchangeability given D,X'] if opt['score']=='missing-at-random' else
                     ['selection-instrument relevance and outcome exclusion',
                      'scalar threshold selection and conditional latent-rank independence',
                      'treatment overlap given X and selection propensity','conditional effect homogeneity'])}
        if 'weights' in opt:
            score_definition['weights']['score_equation'] = (
                '-w/mean(w)*theta+w*g_d+w_bar*1{D=d}*(Y-g_d)/p_d' if method=='dml_apo' else
                '-w/mean(w)*theta+w*(g_1-g_0)+w_bar*(D*(Y-g_1)/p-(1-D)*(Y-g_0)/(1-p))')
            score_definition['target']['expression'] = (
                'E['+score_definition['weights']['score_equation'].replace('mean(w)','E[w]')+']=0')
        result['orthogonal_score'] = score_definition
        if method == 'dml_qte':
            result['covariance_kind'] = 'official marginal variances; cross-quantile covariance is not exported'
        rows = [{'term':name,'estimate':float(coef[name]),'se':float(se[name]),
            'p_value':float(pv[name]),'ci_low':float(ci.loc[name].iloc[0]),'ci_high':float(ci.loc[name].iloc[1]),
            'n':int(fit_n),'unit':spec['unit'],'target':target_kind} for name in names]
        if method in ('dml_qte','dml_pq','dml_cvar'):
            for row,quantile in zip(rows,score_definition['quantiles']): row['quantile'] = quantile
        if 'treatment_level' in opt:
            for row in rows: row['treatment_level'] = opt['treatment_level']
        result['display'] = {'kind':'qte' if method=='dml_qte' and opt['score']!='CVaR' else
                'line' if method=='dml_qte' else 'coefficient','rows':rows,
            'metadata':{**opt.get('definitions',{}),'estimand':spec['estimand'],'population':spec['population'],
                'period':spec['period'],'unit':spec['unit'],'score':opt['score'],'engine':engine,
                'confidence_level':confidence_level,'interval_type':result['inference']['interval_type'],
                'inference':spec['inference'],'orthogonal_score':score_definition,
                'producer':{'function':engine,'versions':versions}}}
        if method == 'dml_qte':
            result['display']['display'] = {'plot_type':'line','x':'quantile','y':'estimate'}
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
                    else 'att' if aggregation['type'] != 'dynamic' or index >= 0
                    else 'anticipation' if index >= -opt.get('anticipation',0) else 'pre_diagnostic')
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
                     'n':fit_n,'unit':spec['unit'],'role':'att'}]
        result['display'] = {'kind':'event-study' if aggregation['type'] == 'dynamic' else 'coefficient',
            'rows':rows,'metadata':{'aggregation':aggregation['type'],'confidence_level':confidence_level,
            'interval_type':result['inference']['interval_type'],
            'reference_event_time':-opt.get('anticipation',0)-1 if baseline else None,
            'cohort_contributions':[{k:v for k,v in component.items() if k != 'treated_sample_ids'} for component in did_values['components']],
            'unit':spec['unit'],'population':spec['population'],
            'sample':{k:v for k,v in result['sample'].items() if not isinstance(v,list)}}}
    result['result_format_version'] = 1
    if method == 'synthetic_control':
        treatment_time = float(matrix.index[post][0])
        metadata = {'population':spec['population'],'period':spec['period'],'unit':spec['unit'],
            'treatment':treated,'control_group':donor_names,'treatment_time':treatment_time,
            'training_end':end,'validation_end':pre,'weights':diagnostics['donor_weights'],
            'observation_unit':entity,'time_variable':time,'engine':engine,
            'effect_estimand':spec['estimand'],'inference':spec['inference'],
            'producer':{'function':engine,'versions':versions},
            'interval_type':'none','result_format_version':1}
        series_rows = [{'time':float(t),'estimate':float(value),'component':component}
            for component, values in (('actual',target.to_numpy()),('synthetic',synthetic))
            for t,value in zip(matrix.index,values)]
        result['display'] = {'kind':'scm','rows':series_rows,
            'metadata':{**metadata,'estimand':'Treated outcome and its fitted synthetic-control trajectory'}}
        result['displays'] = {'scm_gap':{'kind':'scm_gap',
            'rows':[{'time':float(t),'estimate':float(gap)} for t,gap in zip(matrix.index,gaps)],
            'metadata':{**metadata,'estimand':'Treated-minus-synthetic outcome gap'}}}
    if method == 'iv_ar':
        ar = diagnostics['anderson_rubin']
        ar_rows = [{'term':spec['endogenous'][0],**interval,
                    'lower_unbounded':interval['lower'] is None,
                    'upper_unbounded':interval['upper'] is None,
                    'set_type':'interval'} for interval in ar['intervals']]
        if not ar_rows:
            ar_rows = [{'term':spec['endogenous'][0],'set_type':'empty'}]
        result['display'] = {'kind':'iv_confidence_set','rows':ar_rows,
            'metadata':{'estimand':spec['estimand'],'population':spec['population'],
                'unit':spec['unit'],'confidence_level':ar['confidence_level'],
                'interval_type':'Anderson-Rubin test inversion','inference':spec['inference'],
                'engine':engine,'assignment':spec['assignment']}}
    return result



def main():
    import state
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='operation',required=True)
    run_parser=sub.add_parser('run'); run_parser.add_argument('spec',type=Path); run_parser.add_argument('--output','-o',required=True,type=Path)
    select_parser=sub.add_parser('select'); select_parser.add_argument('spec',type=Path); select_parser.add_argument('--output','-o',required=True,type=Path)
    a=parser.parse_args()
    try:
        spec=json.loads(a.spec.read_text(encoding='utf-8'))
        protected = {a.spec.resolve()}
        if a.operation == 'run' and isinstance(spec, dict):
            if isinstance(spec.get('data'), str):
                protected.add((a.spec.parent / spec['data']).resolve())
            if isinstance(spec.get('data_record'),dict) and isinstance(spec['data_record'].get('path'),str):
                record_path = (a.spec.parent/spec['data_record']['path']).resolve()
                protected.add(record_path)
                table = json.loads(record_path.read_text(encoding='utf-8'))['table']
                protected.add((record_path.parent/table['path']).resolve())
            options = spec.get('options', {})
            if isinstance(options,dict):
                for key in ('baseline_result','model_file'):
                    if isinstance(options.get(key),str): protected.add((a.spec.parent/options[key]).resolve())
                for key in ('native_output','posterior_output'):
                    if isinstance(options.get(key),str) and (a.spec.parent/options[key]).resolve() in protected | {a.output.resolve()}:
                        raise ValueError('Native model/posterior, common JSON and source inputs must have separate destinations')
            if spec.get('method') == 'rct_design' and isinstance(options, dict):
                assignment_path = options.get('assignment_result')
                if isinstance(assignment_path, str):
                    protected.add((a.spec.parent / assignment_path).resolve())
        if a.output.resolve() in protected:
            raise ValueError('Output must use a separate path from the specification, input data and saved assignment')
        result=select_method(spec,spec_path=a.spec) if a.operation=='select' else run(spec,a.spec)
        state.save(a.output,result)
    except (ValueError,TypeError,KeyError,OSError,ArithmeticError) as exc: parser.exit(2,f'error: {exc}\n')

if __name__=='__main__': main()
