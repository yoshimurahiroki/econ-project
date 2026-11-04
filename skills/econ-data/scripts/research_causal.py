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


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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

def run(spec, spec_path):
    allowed = {'method','data','id','outcome','regressors','endogenous','instruments',
               'population','period','unit','estimand','identification','assignment',
               'inference','options'}
    if not isinstance(spec, dict) or set(spec) != allowed:
        raise ValueError('specification must contain exactly the documented fields')
    method = spec['method']
    methods = {'gls','iv_gmm','iv_ar','panel_fe','quantile','poisson','logit','rct','rdd_sharp','rdd_fuzzy','hdfe','causal_forest','spatial_lag','rdd_localrand','shift_share','policy_tree','network_spillover','tobit','dynamic_panel','synthetic_control','staggered_did','generalized_synth','multitreatment_did','distribution_effect'}
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
    opt = spec['options']
    required = {'gls': {'variance'}, 'iv_gmm': set(), 'iv_ar': {'alpha'}, 'panel_fe': {'entity','time','entity_effects','time_effects'},
                'quantile': {'quantile'}, 'poisson': set(), 'logit': set(), 'rct': {'treatment','permutations','seed'}, 'rdd_sharp': {'running','cutoff','bandwidth'}, 'rdd_fuzzy': {'running','cutoff','bandwidth','treatment'}, 'hdfe': {'fixed_effects'}, 'causal_forest': {'treatment','seed','trees','min_leaf'}, 'spatial_lag': {'weights'}, 'rdd_localrand': {'running','cutoff','bandwidth','permutations','seed'}, 'shift_share': {'shares','shocks'}, 'policy_tree': {'treatment','propensity','partition','seed'}, 'network_spillover': {'weights','treatment'}, 'tobit': {'lower'}, 'dynamic_panel': {'entity','time'}, 'synthetic_control': {'entity','time','treated','training_end','pre_end'}, 'staggered_did': {'entity','time','cohort','control_group'}, 'generalized_synth': {'entity','time','treatment','factors','bootstraps','seed'}, 'multitreatment_did': {'entity','time','pre','post','treatments'}, 'distribution_effect': {'treatment','threshold'}}[method]
    if set(opt) != required:
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
    diagnostics = {}; fit_n=None
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
        import re, subprocess, tempfile, os
        entity=opt['entity']; time=opt['time']; cohort=opt['cohort']; control=opt['control_group']
        variables=[spec['outcome'],*spec['regressors'],entity,time,cohort]
        if control not in ('nevertreated','notyettreated') or any(not isinstance(k,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',k) for k in variables) or len(set(variables))!=len(variables): raise ValueError('DID requires distinct simple column names and valid control group')
        if excluded or d.duplicated([entity,time]).any() or d.groupby(entity)[cohort].nunique().max()!=1: raise ValueError('DID needs complete unique entity-time observations and fixed cohort')
        grid=np.sort(d[time].unique()); groups=d[cohort].unique(); n_entities=d[entity].nunique()
        if len(grid)<4 or not np.equal(grid,np.floor(grid)).all() or not np.equal(groups,np.floor(groups)).all() or not np.all(np.diff(grid)==1) or len(d)!=n_entities*len(grid) or not (d.groupby(entity)[time].nunique()==len(grid)).all(): raise ValueError('DID needs a balanced consecutive integer-time panel')
        if not np.any(groups>0) or any(g not in grid[1:] for g in groups if g!=0): raise ValueError('DID needs valid post-baseline treatment cohorts')
        if control == 'nevertreated' and 0 not in groups:
            raise ValueError('nevertreated DID requires a never-treated cohort coded zero')
        if 0 not in groups:
            if len(groups)<2:
                raise ValueError('notyettreated DID requires at least two treatment cohorts when no never-treated cohort exists')
            # No untreated comparison remains from the last adoption period onward.
            comparison_window = d[time] < max(groups)
            outside = d.loc[~comparison_window,spec['id']].astype(str).tolist()
            d = d.loc[comparison_window].copy()
        if not os.environ.get('R_LIBS_USER'): raise ValueError('set R_LIBS_USER to the installed did library')
        rcode="""
args <- commandArgs(trailingOnly=TRUE)
suppressPackageStartupMessages(library(did)); suppressPackageStartupMessages(library(jsonlite))
d <- read.csv(args[1],check.names=FALSE); y <- args[2]; unit <- args[3]; tm <- args[4]; cohort <- args[5]; control <- args[6]; covars <- args[7]
d[[unit]] <- as.integer(as.factor(d[[unit]])); form <- if(nchar(covars)) as.formula(paste('~',gsub(',', '+', covars))) else ~1
invisible(capture.output(a <- att_gt(yname=y,tname=tm,idname=unit,gname=cohort,xformla=form,data=d,control_group=control,panel=TRUE,allow_unbalanced_panel=FALSE,anticipation=0,bstrap=FALSE,cband=FALSE,est_method='dr',base_period='varying',cores=1)))
invisible(capture.output(e <- aggte(a,type='dynamic',bstrap=FALSE,cband=FALSE)))
influences <- cbind(e$inf.function$dynamic.inf.func, e$inf.function$dynamic.inf.func.e); vv <- crossprod(influences)/(a$n^2)
gv <- crossprod(as.matrix(a$inffunc))/(a$n^2)
obj <- list(r_version=as.character(getRversion()),did_version=as.character(packageVersion('did')),event_times=e$egt,coef=c(e$overall.att,e$att.egt),engine_se=c(e$overall.se,e$se.egt),cov=unname(vv),groups=a$group,times=a$t,att=a$att,group_cov=unname(gv),group_se=a$se,n=a$n)
cat(toJSON(obj,auto_unbox=TRUE,digits=16,na='null',null='null'))
"""
        with tempfile.TemporaryDirectory(prefix='causal-did-') as tmp:
            inp=Path(tmp)/'data.csv'; d.to_csv(inp,index=False)
            proc=subprocess.run(['Rscript','-',str(inp),spec['outcome'],entity,time,cohort,control,','.join(spec['regressors'])],input=rcode,text=True,capture_output=True,env=os.environ.copy())
        if proc.returncode: raise ArithmeticError('did engine failed: '+proc.stderr[-2000:])
        values=json.loads(proc.stdout); versions['R']=values['r_version']; versions['did']=values['did_version']
        events=np.atleast_1d(values['event_times']); names=['overall']+[('event_m'+str(abs(int(x))) if x<0 else 'event_p'+str(int(x))) for x in events]; vals=np.atleast_1d(values['coef']); covariance=np.atleast_2d(values['cov']);
        if not np.isfinite(vals.astype(float)).all() or not np.isfinite(covariance.astype(float)).all(): raise ArithmeticError('DID returned nonfinite estimates')
        coef=pd.Series(vals,index=names,dtype=float); cov=pd.DataFrame(covariance,index=names,columns=names,dtype=float); se=pd.Series(np.sqrt(np.diag(cov)),index=names); from scipy.stats import norm
        if not np.allclose(se.to_numpy(),np.atleast_1d(values['engine_se']),rtol=1e-7,atol=1e-9) or not np.allclose(np.sqrt(np.diag(np.atleast_2d(values['group_cov']))),np.atleast_1d(values['group_se']),rtol=1e-7,atol=1e-9): raise ArithmeticError('DID influence-function covariance does not match engine standard errors')
        pv=pd.Series(2*norm.sf(np.abs(coef/se)),index=names); ci=pd.DataFrame({0:coef-norm.ppf(.975)*se,1:coef+norm.ppf(.975)*se}); reference='normal'; engine='R did::att_gt + did::aggte'
        fit_n=n_entities
        diagnostics={'control_group':control,'score':'doubly robust','aggregation':'dynamic event time over available cohorts at each event time','base_period':'varying','group_time':{'group':values['groups'],'time':values['times'],'att':values['att'],'standard_errors':values['group_se'],'covariance':values['group_cov']},'units':int(values['n']),'bootstrap':False,'anticipation':0}
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
            if method == 'poisson' and ((y<0).any() or (y != np.floor(y)).any()): raise ValueError('Poisson outcome must be a nonnegative integer')
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
    units={k:(spec['unit'] if k in ('const','treatment_effect','sample_ate','policy_value_gain','overall','post') or k.startswith('event_') else 'dimensionless' if k in ('spatial_lag','log_sigma','L1.'+spec['outcome']) else f"{spec['unit']} per one unit of {k}") for k in names}
    stats={f'coefficient.{k}':{'value':v,'unit':units[k]} for k,v in zip(names,vals)}
    stats.update({f'standard_error.{k}':{'value':v,'unit':units[k]} for k,v in zip(names,std)})
    stats.update({f'p_value.{k}':{'value':float(pv.loc[k]),'unit':'probability'} for k in names})
    stats.update({f'confidence_95_lower.{k}':{'value':float(ci.loc[k].iloc[0]),'unit':units[k]} for k in names})
    stats.update({f'confidence_95_upper.{k}':{'value':float(ci.loc[k].iloc[1]),'unit':units[k]} for k in names})
    fit_n=len(d) if fit_n is None else fit_n
    stats['observations']={'value':int(fit_n),'unit':'fitted observations'}
    return {'method':method,'engine':engine,'versions':versions,'options':opt,'adopted':{k:spec[k] for k in ('population','period','unit','estimand','identification','assignment','inference')},'sample':{'id_column':spec['id'],'included_ids':d[spec['id']].astype(str).tolist(),'excluded_incomplete_ids':excluded,'excluded_outside_window_ids':outside,'training_ids':training,'excluded_initial_lag_ids':initial_lags,'input_rows':int(input_rows),'observations':int(fit_n)},'coefficients':dict(zip(names,vals)),'standard_errors':dict(zip(names,std)),'covariance_kind':'upper bound on scalar variance' if method=='causal_forest' else 'estimator covariance','covariance':{a:{b:float(cov.loc[a,b]) for b in names} for a in names},'inference':{'reference':reference,'p_values':{k:float(pv.loc[k]) for k in names},'confidence_intervals_95':{k:[float(x) for x in ci.loc[k]] for k in names}},'diagnostics':diagnostics,'statistics':stats,'provenance':{'data_path':str(p),'data_sha256':_hash(p),'spec_path':str(spec_path.resolve()),'spec_sha256':_hash(spec_path)}}


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
    case_parser=sub.add_parser('case'); case_parser.add_argument('--output','-o',required=True,type=Path)
    a=parser.parse_args()
    try:
        if a.operation=='case': case(a.output)
        else:
            spec=json.loads(a.spec.read_text(encoding='utf-8'))
            result=run(spec,a.spec)
            state.save(a.output,result)
    except (ValueError,TypeError,KeyError,OSError,ArithmeticError) as exc: parser.exit(2,f'error: {exc}\n')

if __name__=='__main__': main()
