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
import numpy as np
import pandas as pd
import scipy
import statsmodels
import statsmodels.api as sm

FLAT_EXPORT = (Path(__file__).resolve().parent / 'RESOURCES.json').is_file()
ROOT = Path(__file__).resolve().parent if FLAT_EXPORT else Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT if FLAT_EXPORT else ROOT / 'harness'))
import state


R_METHODS = {
    'ols_r': ('stats', 'lm'),
    'fixest_ols': ('fixest', 'feols'),
    'fixest_ppml': ('fixest', 'fepois'),
    'negative_binomial_r': ('MASS', 'glm.nb'),
    'sunab': ('fixest', 'feols'),
    'did2s': ('did2s', 'did2s'),
    'did_imputation': ('didimputation', 'did_imputation'),
    'fixes_event_study': ('fixes', 'event_study'),
    'nonabs_did': ('nonabsdid', 'nabs_event_study'),
    'synthdid': ('synthdid', 'synthdid_estimate'),
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
    'iv_ar_robust': ('ivDiag', 'AR_test'),
}

RUN_FIELDS = {'method','data','id','outcome','regressors','endogenous','instruments',
              'population','period','unit','estimand','identification','assignment','inference','options'}
DML_METHODS = {'dml_irm':'DoubleMLIRM', 'dml_pliv':'DoubleMLPLIV', 'dml_iivm':'DoubleMLIIVM'}


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_method(request):
    """Select an estimator from economic objects and structured design conditions.

    Narrative identification is retained as evidence, never parsed as a package
    request. Existing flat specifications remain readable at this boundary.
    """
    required = {'question','estimand','identification','design','outcome_scale','data_structure','treatment_pattern','dependence'}
    contract_fields = ('population','comparison_group','observation_unit','assignment_unit','inference_unit',
                       'unit','period','assignment','weights','inference',
                       'economic_model','target','conditions','comparison','numerical','model_contract_id')
    optional = {'adopted_method','adopted_specification','options','score','structural_model','implementation',
                'data','id','outcome','regressors','endogenous','instruments',*contract_fields}
    if not isinstance(request, dict) or not required <= request.keys() or set(request)-required-optional:
        raise ValueError(f'selection requires {sorted(required)} and accepts {sorted(optional)}')
    if any(not isinstance(request[k], str) or not request[k].strip() for k in required):
        raise ValueError('selection fields must be explicit nonempty strings')
    adopted_spec = request.get('adopted_specification', {})
    if not isinstance(adopted_spec, dict):
        raise ValueError('adopted_specification must be an existing specification object')
    resources = json.loads((ROOT / ('RESOURCES.json' if FLAT_EXPORT else 'registry/resources.json')).read_text())['resources']
    placements = json.loads((ROOT / ('PLACEMENTS.json' if FLAT_EXPORT else 'registry/placements.json')).read_text())['resources']
    layout_path = 'export_alias' if FLAT_EXPORT else 'deployment_path' if ROOT.name == '.agents' else 'source_path'
    model_contract = None
    knowledge_plan = None
    contract_binding = None
    contract_id = request.get('model_contract_id', adopted_spec.get('model_contract_id'))
    if contract_id is not None:
        if not isinstance(contract_id, str) or not contract_id.startswith('MC-'):
            raise ValueError('model_contract_id must name a canonical MC- contract')
        rid = 'knowledge-retrieval'
        knowledge_relative = resources[rid]['source_path'] if layout_path == 'source_path' else placements[rid][layout_path]
        knowledge_path = (ROOT.parent if ROOT.name == '.agents' else ROOT) / knowledge_relative
        module_spec = importlib.util.spec_from_file_location('selected_model_knowledge', knowledge_path)
        knowledge = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(knowledge)
        reader = knowledge.Reader(knowledge.BASE)
        model_contract = reader.contract(contract_id)
        knowledge_plan = reader.plan([contract_id])
        knowledge_plan.pop('contracts')
        contract_binding = model_contract.get('selection_binding')
    for key in ('economic_model','target','conditions','comparison','numerical'):
        if not isinstance(request.get(key, adopted_spec.get(key,{})), dict):
            raise ValueError(f'{key} must be a structured object')
    facts = request.get('conditions', adopted_spec.get('conditions',{}))
    target = request.get('target', adopted_spec.get('target',{}))
    economic_model = request.get('economic_model', adopted_spec.get('economic_model',{}))
    comparison = request.get('comparison', adopted_spec.get('comparison',{}))
    numerical = request.get('numerical', adopted_spec.get('numerical',{}))
    for key in ('randomized','weak_instruments','homoskedastic_normal_errors',
                'conditional_exchangeability','overlap','parallel_trends',
                'exclusion','monotonicity','continuity','common_treatment_block',
                'equilibrium_counterfactual','independent_units','no_interference',
                'aggregate_shocks','stationary_equilibrium','nominal_rigidity',
                'complete_information','transferable_utility','coalition_externalities',
                'free_trading','all_states_possible'):
        if key in facts and not isinstance(facts[key], bool):
            raise ValueError(f'conditions.{key} must be boolean')
    target_kind = target.get('kind')
    allowed_targets = {'ate','att','itt','late','cate','policy_value','linear_projection',
        'conditional_mean','count_distribution','group_time_att','event_time_att',
        'treatment_path_effect','dose_response','local_effect','confidence_set',
        'treated_trajectory','treated_block_att','structural_parameter','equilibrium',
        'welfare','allocation','price_bounds','sensitivity','density_discontinuity','power'}
    if target_kind is not None and target_kind not in allowed_targets:
        raise ValueError(f'target.kind must be one of {sorted(allowed_targets)}')
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
        definitions = o.get('definitions', {})
        if not isinstance(definitions, dict):
            raise ValueError('options.definitions must be an object')
        for key in contract_fields:
            if key not in fields and key in definitions:
                fields[key] = definitions[key]
        for key in ('population','weights'):
            if key not in fields and key in s.get('target',{}):
                fields[key] = s['target'][key]
        for group in ('args','columns'):
            if not isinstance(o.get(group, {}), dict):
                raise ValueError('native args and columns must be objects')
        if 'comparison_group' not in fields and 'control_group' in o:
            fields['comparison_group'] = o['control_group']
        if 'weights' not in fields:
            weights = {k:o[k] for k in ('weightsname','fix_weights','weights','weights_type') if k in o}
            for group in ('args','columns'):
                selected = {k:v for k,v in o.get(group, {}).items() if k in ('weights','i.weights','sample.weights','weight')}
                if selected: weights[group] = selected
            if weights: fields['weights'] = weights
        return fields
    adopted_contract = scientific_contract(adopted_spec)
    proposed_contract = scientific_contract({**adopted_spec, **request})
    for key in ('population','weights'):
        if key not in request and key in request.get('target',{}):
            proposed_contract[key] = request['target'][key]
    forward_options = request.get('options', adopted_spec.get('options', {}))
    requested_inference = proposed_contract.get('inference', {})
    if not isinstance(requested_inference, dict):
        raise ValueError('inference must be a structured object')
    level = comparison.get('confidence_level', requested_inference.get('confidence_level'))
    requested_alpha = requested_inference.get('alpha')
    for key, value in (('confidence_level', level), ('alpha', requested_alpha)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < 1):
            raise ValueError(f'inference {key} must lie strictly between zero and one')
    if level is not None and requested_alpha is not None and abs(level + requested_alpha - 1) > 1e-12:
        raise ValueError('confidence_level and inference.alpha must agree')
    if level is None and requested_alpha is not None:
        level = 1 - requested_alpha
    interval_type = comparison.get('interval_type', comparison.get('ci_kind',
        requested_inference.get('interval_type', requested_inference.get('ci_kind'))))
    cluster_columns = requested_inference.get('clusters', requested_inference.get('cluster'))
    if isinstance(cluster_columns, str):
        cluster_columns = [cluster_columns]
    if cluster_columns is not None and (not isinstance(cluster_columns, list) or not cluster_columns or
            any(not isinstance(column, str) or not column.strip() for column in cluster_columns) or
            len(set(cluster_columns)) != len(cluster_columns)):
        raise ValueError('inference.cluster/clusters must name distinct analysis columns')
    design = request['design']; structure = request['data_structure']; pattern = request['treatment_pattern']
    mechanism = facts.get('assignment_mechanism')
    if design == 'auto':
        mechanisms = {'randomized':'rct','parallel_trends':'did','threshold':'rdd',
            'instrument':'iv','selection_on_observables':'orthogonal_score',
            'conditional_mean':'conditional_mean','donor_panel':'synthetic_control',
            'structural_equilibrium':'structural'}
        if mechanism not in mechanisms:
            raise ValueError('design=auto requires conditions.assignment_mechanism: ' + ', '.join(mechanisms))
        design = mechanisms[mechanism]
        if mechanism in ('randomized','selection_on_observables'):
            if target_kind == 'cate': design = 'heterogeneous_effect'
            if target_kind == 'policy_value': design = 'policy_learning'
    if mechanism == 'selection_on_observables':
        if facts.get('conditional_exchangeability') is False or facts.get('overlap') is False:
            raise ValueError('selection on observables requires conditional exchangeability and overlap in the target population')
    for name, value in (('data_structure',structure),('treatment_pattern',pattern),
                        ('outcome_scale',request['outcome_scale'])):
        if name in facts and facts[name] != value:
            raise ValueError(f'conditions.{name} must match the explicit {name}')
    if model_contract is not None:
        if contract_binding is None:
            return {'result_format_version':1, 'status':'implementation_required',
                'question':request['question'], 'estimand':request['estimand'],
                'identification':request['identification'], 'method':None, 'engine':None, 'entry_point':None,
                'design_contract':proposed_contract, 'adopted_specification':adopted_spec,
                'method_selection':{'model_contract':model_contract, 'knowledge_plan':knowledge_plan,
                    'compatibility':{'status':model_contract['selection_status'],
                        'reason':'This contract has no binding to the existing method selector.',
                        'selected_method':None},
                    'official_implementation':{'execution_mode':'none', 'execution_specification':None}},
                'executed':False}
        if design != contract_binding['design']:
            raise ValueError(f'{contract_id} requires design={contract_binding["design"]}; received {design}')
    owner = 'skills/econ-data/scripts/research_causal.py run'
    conditions = []
    required_inputs = []
    alternatives = []
    required_native_options = {}
    external_implementation = None
    native_function = None
    computation = None
    numerical_kernel = None
    respy_simulation = False
    method_quantity = request['estimand']
    score = facts.get('score', request.get('score'))
    if 'score' in facts and 'score' in request and facts['score'] != request['score']:
        raise ValueError('conditions.score must match score')
    if design in ('rct','randomized'):
        if facts.get('randomized') is False:
            raise ValueError('RCT requires randomized assignment')
        method = 'rct'
        method_quantity = 'E[Y(1)-Y(0)] for the randomized assignment population'
        if target_kind == 'late':
            method = 'iv_gmm'
            method_quantity = 'complier effect under assignment exclusion, relevance and monotonicity'
        elif target_kind not in (None,'ate','itt'):
            raise ValueError('RCT assignment comparison targets ate or itt; receipt late requires the IV branch')
        conditions = ['recorded randomization probabilities and assignment units',
            'consistency and the adopted interference mapping',
            'complete randomization at the observed arm counts for the sharp-null permutation test']
        required_inputs = ['treatment assignment column','outcome','assignment unit','randomization scheme']
        if method == 'iv_gmm':
            conditions = ['random assignment of the instrument','assignment exclusion','nonzero receipt first stage','monotonic receipt response']
            required_inputs += ['actual treatment receipt','assignment as excluded instrument']
        elif request['dependence'] in ('cluster','clustered'):
            method = 'fixest_ols'
            conditions = ['randomized cluster assignment','assignment-level covariance','assignment contrast with the adopted cluster/population weights']
            required_inputs.append('cluster column bound to official vcov')
        alternatives = [
            {'method':'fixest_ols','difference':'covariate-adjusted assignment contrast',
             'estimand':'average assignment effect under the adopted regression adjustment and population weights',
             'conditions':['random assignment','prespecified adjustment implementing the target contrast'],
             'data_fit':{'required':['assignment, outcome and pretreatment adjustment variables']},
             'inference':{'procedure':'official linear-model covariance at the independent assignment unit'}},
            {'method':'iv_gmm','difference':'assignment instruments actual treatment receipt',
             'estimand':'receipt LATE for assignment compliers under binary assignment and receipt',
             'conditions':['assignment exclusion','instrument independence','monotonic receipt response','nonzero first stage'],
             'data_fit':{'required':['assignment instrument, actual receipt, outcome and exogenous controls']},
             'inference':{'procedure':'robust or clustered GMM covariance; weak-IV inference requires test inversion'}}]
    elif design == 'conditional_mean':
        if target_kind == 'count_distribution' or facts.get('conditional_distribution') == 'nb2':
            if facts.get('conditional_distribution') != 'nb2':
                raise ValueError('count-distribution selection requires conditions.conditional_distribution=nb2')
            method = 'negative_binomial_r'
            method_quantity = 'NB2 likelihood coefficient with E[Y|X]=exp(X beta) and Var(Y|X)=mu+alpha*mu^2'
        elif request['outcome_scale'] == 'level':
            method = 'hdfe' if request.get('implementation') == 'pyfixest' else 'fixest_ols'
            method_quantity = 'weighted additive conditional-mean or linear-projection coefficient in outcome units'
        elif request['outcome_scale'] == 'proportional_nonnegative': method = 'fixest_ppml'
        else: raise ValueError('conditional_mean requires level or proportional_nonnegative outcome_scale')
        conditions = ['adopted conditional mean', 'fixed effects and weights from the target population', 'covariance matched to dependence']
        if method == 'fixest_ppml':
            method_quantity = 'log-mean coefficient beta in E[Y|X,FE]=exp(X beta+FE+offset)'
        required_inputs = ['outcome scale and support','regressors and fixed effects','sampling or analytic weights','exposure/offset when a rate is targeted']
        alternatives = [
            {'method':'fixest_ols','difference':'additive outcome-unit contrast',
             'estimand':'weighted linear projection or additive conditional-mean coefficient',
             'conditions':['specified projection population or additive conditional mean','full-rank residual variation'],
             'data_fit':{'required':['numeric outcomes, regressors, fixed effects and adopted weights'], 'outcome_scales':['level']},
             'inference':{'procedure':'adopted fixest covariance and small-sample convention'}},
            {'method':'fixest_ppml','difference':'exponential conditional mean with observed zeros retained',
             'estimand':'beta in E[Y|X,FE]=exp(X beta+FE+offset)',
             'conditions':['exponential conditional mean','exogenous regressors','identified nonseparated coefficients'],
             'data_fit':{'required':['nonnegative outcomes and positive exposure for a log offset'], 'outcome_scales':['proportional_nonnegative']},
             'inference':{'procedure':'heteroskedastic or cluster covariance for the PPML score'}},
            {'method':'negative_binomial_r','difference':'NB2 count likelihood jointly estimates dispersion',
             'estimand':'log-mean coefficients and alpha in Var(Y|X)=mu+alpha*mu^2',
             'conditions':['adopted NB2 conditional distribution','specified unconditional group heterogeneity'],
             'data_fit':{'required':['nonnegative integer counts and an identified likelihood design'], 'conditional_distribution':'nb2'},
             'inference':{'procedure':'MASS likelihood coefficient covariance and official dispersion standard error'}}]
    elif design == 'did':
        if facts.get('parallel_trends') is False:
            raise ValueError('DID requires the adopted parallel-trend restriction; use saved-event-study sensitivity for a bounded departure')
        estimator = facts.get('estimator', 'group_time')
        if pattern == 'absorbing_staggered':
            candidates = {'group_time':'staggered_did','cohort_interaction':'sunab',
                'imputation':'did_imputation','two_stage':'did2s','fixes':'fixes_event_study'}
            if estimator not in candidates:
                raise ValueError('absorbing DID estimator must be group_time, cohort_interaction, imputation, two_stage or fixes')
            method = candidates[estimator]
            if method == 'fixes_event_study':
                required_inputs.append('explicit fixes estimator and its supported nuisance/weight/cluster contract')
            method_quantity = 'ATT(g,t)=E[Y_t(g)-Y_t(0)|G=g], aggregated over the adopted cohorts and event times'
        elif pattern in ('reversals','changing_dose','treatment_histories','continuous'):
            if target_kind == 'dose_response' and facts.get('effect_normalization') != 'per_unit_dose':
                raise ValueError('dose_response requires the adopted per_unit_dose normalization and dose-response restrictions')
            method = 'nonabs_did' if estimator == 'nonabsdid' else 'did_multiplegt_dyn'
            if estimator not in ('group_time','switcher','nonabsdid'):
                raise ValueError('changing treatment histories require switcher or nonabsdid estimator conditions')
            method_quantity = ('weighted current and lagged per-unit dose effects' if facts.get('effect_normalization') == 'per_unit_dose'
                else 'switcher effect of the realized treatment path relative to maintaining the baseline dose')
            normalized = facts.get('effect_normalization') == 'per_unit_dose'
            if method == 'nonabs_did' and normalized:
                required_native_options['estimator'] = 'DCDH'
            if method == 'did_multiplegt_dyn' or normalized or forward_options.get('estimator') == 'DCDH':
                required_native_options['args.normalized'] = normalized
        elif pattern == 'two_period':
            if structure == 'panel': method = 'drdid_panel'
            elif structure == 'repeated_cross_section': method = 'drdid_rc'
            else: raise ValueError('two-period DID requires panel or repeated_cross_section data_structure')
            if score not in (None,'dr','doubly_robust'):
                raise ValueError('the two-period runner implements the doubly robust score; preserve an adopted OR/IPW score in its official implementation')
            method_quantity = 'E[Y_post(1)-Y_post(0)|D=1] under conditional parallel trends'
            if (request['dependence'] in ('cluster','clustered') or interval_type == 'simultaneous' or
                    (level is not None and abs(level - .95) > 1e-12)):
                method = 'staggered_did'
        else: raise ValueError('DID treatment_pattern must identify two_period, absorbing_staggered, reversals, changing_dose or treatment_histories')
        conditions = ['specified untreated-trend scale and comparison eligibility', 'adopted anticipation and reference period', 'cohort or switcher population and horizon weights', 'assignment-matched clustering and interval family']
        required_inputs = ['entity and time','cohort or complete treatment history','eligible control population',
            'anticipation periods','outcome and pretreatment covariates','event window and base period',
            'aggregation weights and population at each horizon']
        if pattern == 'two_period' and method == 'staggered_did':
            required_inputs.append('common adoption cohort and native inference settings for the adopted two-period score')
        alternatives = [
            {'method':'drdid_panel','difference':'one treated-group pre/post contrast using paired outcomes',
             'estimand':'two-period ATT with treated-population sampling weights',
             'conditions':['conditional parallel trends','no anticipation','overlap','correct propensity or untreated-outcome nuisance model'],
             'data_fit':{'required':['paired pre/post outcomes and pretreatment covariates'], 'data_structures':['panel'], 'treatment_patterns':['two_period'], 'dependence':['independent','iid','heteroskedastic','robust']},
             'inference':{'procedure':'official DRDID influence-function or bootstrap inference for independent sampled units'}},
            {'method':'drdid_rc','difference':'period-specific outcomes from stationary repeated cross sections',
             'estimand':'two-period ATT for the stable treated population',
             'conditions':['conditional parallel trends','no anticipation','overlap','stationary sampling composition','adopted doubly robust nuisance conditions'],
             'data_fit':{'required':['pre/post cross sections, treatment-group membership and period covariates'], 'data_structures':['repeated_cross_section'], 'treatment_patterns':['two_period'], 'dependence':['independent','iid','heteroskedastic','robust']},
             'inference':{'procedure':'official repeated-cross-section influence-function or bootstrap inference'}},
            {'method':'staggered_did','difference':'group-time comparisons and target-specific aggregation',
             'estimand':'ATT(g,t), aggregated using the adopted cohort/event/calendar weights',
             'conditions':['conditional parallel trends against eligible never-treated or not-yet-treated units','no anticipation beyond the adopted window','comparison overlap'],
             'data_fit':{'required':['cohort, time, unit and comparison eligibility'], 'data_structures':['panel','repeated_cross_section'], 'treatment_patterns':['absorbing_staggered','two_period']},
             'inference':{'procedure':'official influence functions or multiplier bootstrap with adopted clustering and simultaneous family'}},
            {'method':'sunab','difference':'cohort-interacted regression with designated reference cohorts',
             'estimand':'cohort-event ATT combined with the fitted sample cohort shares',
             'conditions':['parallel untreated trends for the designated reference cohorts','absorbing adoption','adopted anticipation and covariate restriction'],
             'data_fit':{'required':['cohort-period interactions, reference cohorts, fixed effects and horizon support'], 'data_structures':['panel'], 'treatment_patterns':['absorbing_staggered','two_period']},
             'inference':{'procedure':'fixest fitted covariance and covariance-aware cohort aggregation'}},
            {'method':'did_imputation','difference':'fit the untreated outcome model before imputing treated outcomes',
             'estimand':'weighted average of treated-minus-imputed outcomes at the adopted horizons',
             'conditions':['specified untreated conditional mean','no anticipation','untreated observations identify each imputed component'],
             'data_fit':{'required':['unit-period panel and untreated support for the first-stage design'], 'data_structures':['panel'], 'treatment_patterns':['absorbing_staggered','two_period']},
             'inference':{'procedure':'official imputation standard errors at the adopted cluster level; pretrend regression has a separate target'}},
            {'method':'did2s','difference':'untreated-sample residualization followed by the adopted treatment regression',
             'estimand':'second-stage treatment coefficients under the adopted residualization and weighting',
             'conditions':['specified untreated outcome model','no anticipation','identified first-stage fixed effects and covariates'],
             'data_fit':{'required':['unit-period panel, treatment status and explicit first/second-stage formulas'], 'data_structures':['panel'], 'treatment_patterns':['absorbing_staggered','two_period']},
             'inference':{'procedure':'official clustered variance correction for first-stage estimation'}},
            {'method':'did_multiplegt_dyn','difference':'switcher comparisons preserve the observed treatment history',
             'estimand':'effect of the realized path relative to its baseline dose, or normalized weighted current/lagged dose effects',
             'conditions':['baseline-dose-specific parallel trends','no anticipation','eligible not-yet-switching comparisons','adopted continuous-dose trend restriction'],
             'data_fit':{'required':['complete group treatment histories, shared baseline-dose support and horizon-specific switchers'], 'data_structures':['panel'], 'treatment_patterns':['absorbing_staggered','two_period','reversals','changing_dose','treatment_histories','continuous']},
             'inference':{'procedure':'official horizon-specific covariance or bootstrap with the adopted cluster and switcher population'}}]
        anticipation = facts.get('anticipation', forward_options.get('anticipation',0))
        if isinstance(anticipation,bool) or not isinstance(anticipation,int) or anticipation < 0:
            raise ValueError('anticipation must be a nonnegative number of periods')
        if anticipation and method in ('sunab','did_imputation','did2s'):
            required_inputs.append('explicit announcement/exposure coding implementing the adopted anticipation window')
        if pattern in ('continuous','changing_dose'):
            conditions.append('baseline-dose-specific trends and the adopted restriction across continuous baseline doses')
    elif design == 'rdd':
        if facts.get('continuity') is False:
            raise ValueError('local-polynomial RD requires the adopted continuity restrictions; a local-randomization design needs its own assignment conditions')
        method = 'rdrobust_r'; conditions = ['cutoff and running-variable support', 'sharp, fuzzy or derivative target', 'adopted bandwidth, bias correction and dependence']
        fuzzy = facts.get('discontinuity', 'sharp') == 'fuzzy'
        if facts.get('discontinuity','sharp') not in ('sharp','fuzzy'):
            raise ValueError('conditions.discontinuity must be sharp or fuzzy')
        method_quantity = ('local complier effect: outcome discontinuity divided by treatment-receipt discontinuity' if fuzzy
            else 'lim E[Y|X=c+] - lim E[Y|X=c-] at the assignment cutoff')
        if fuzzy: conditions += ['nonzero treatment jump','exclusion and local monotonicity']
        if fuzzy and 'fuzzy' in forward_options.get('columns', {}):
            required_native_options['columns.fuzzy'] = forward_options['columns']['fuzzy']
        required_inputs = ['running variable','cutoff','outcome','bandwidth and polynomial orders','treatment receipt for fuzzy RD']
        alternatives = [{'method':'rdd_localrand','difference':'assignment-based comparison within a fixed window',
            'estimand':'average assignment contrast in the adopted local-randomization window',
            'conditions':['complete randomization conditional on arm counts within the window','consistency and the adopted interference mapping'],
            'data_fit':{'required':['prespecified window, binary assignment and outcome observations']},
            'inference':{'procedure':'sharp-null permutation test and separate HC1 average-contrast interval'}}]
    elif design == 'density_at_cutoff':
        method = 'rddensity'; conditions = ['adopted cutoff', 'running-variable measurement and mass points']
    elif design == 'rd_power':
        method = 'rdpower'; conditions = ['adopted alternative effect, sample size and bandwidth', 'same RD estimator and dependence as the research design']
    elif design in ('iv','instrumental_variables'):
        method = 'iv_ar' if facts.get('weak_instruments') or target_kind == 'confidence_set' else 'iv_gmm'
        conditions = ['specified endogenous regressors and excluded instruments', 'instrument exclusion and rank identify the adopted moment coefficient', 'robust or adopted cluster covariance and the same moment weighting']
        method_quantity = 'linear IV moment coefficient estimated by two-step GMM'
        if method == 'iv_ar':
            if facts.get('homoskedastic_normal_errors') is not True or request['dependence'] in ('cluster','clustered','heteroskedastic','robust'):
                method = 'iv_ar_robust'
            conditions = ['one endogenous regressor','instrument exclusion',
                'independent homoskedastic normal errors with fixed instruments' if method=='iv_ar' else 'independent observations or the adopted independent clusters',
                'inversion of the adopted Anderson-Rubin test']
            method_quantity = 'Anderson-Rubin confidence set for the endogenous-regressor coefficient'
        required_inputs = ['endogenous regressors','excluded instruments','exogenous controls','moment weighting','independent inference unit']
        alternatives = [
            {'method':'iv_gmm','difference':'point estimation and conventional GMM covariance',
             'estimand':'coefficient identified by the adopted linear IV moments',
             'conditions':['instrument exclusion and exogeneity','rank condition for conventional inference'],
             'data_fit':{'required':['endogenous regressors, excluded instruments and exogenous controls']},
             'inference':{'procedure':'two-step robust or cluster GMM covariance'}},
            {'method':'iv_ar','difference':'exact F-test inversion under the adopted disturbance model',
             'estimand':'Anderson-Rubin confidence set for one endogenous-regressor coefficient',
             'conditions':['valid excluded instruments','independent homoskedastic normal errors and fixed instruments'],
             'data_fit':{'required':['one endogenous regressor, excluded instruments and exogenous controls'], 'dependence':['independent','iid','homoskedastic']},
             'inference':{'procedure':'analytic F inversion retaining disconnected, empty and unbounded sets'}},
            {'method':'iv_ar_robust','difference':'robust or clustered Anderson-Rubin test inversion',
             'estimand':'Anderson-Rubin confidence set for one endogenous-regressor coefficient',
             'conditions':['valid excluded instruments','independent observations or independent clusters'],
             'data_fit':{'required':['one endogenous regressor, instruments, controls and any adopted cluster/weight columns']},
             'inference':{'procedure':'official ivDiag::AR_test confidence-set inversion'}}]
    elif design == 'weak_instrument_inference':
        method = ('iv_ar' if facts.get('homoskedastic_normal_errors') is True and request['dependence'] not in ('cluster','clustered','heteroskedastic','robust') else 'iv_ar_robust')
        conditions = ['one endogenous regressor and the adopted excluded instruments',
            'independent homoskedastic normal errors with fixed instruments' if method=='iv_ar' else 'independent observations or the adopted independent clusters',
            'adopted alpha and inversion of the Anderson-Rubin test']
        method_quantity = 'Anderson-Rubin confidence set for the specified endogenous-regressor coefficient'
    elif design == 'synthetic_control':
        method = 'synthdid' if facts.get('counterfactual_model') == 'synthetic_did' or target_kind == 'treated_block_att' else 'synthetic_control'
        if facts.get('counterfactual_model') == 'interactive_fixed_effects': method = 'generalized_synth'
        conditions = ['one treated unit and at least two balanced eligible donors', 'adopted training, untreated validation and post-treatment periods', 'nonnegative donor weights summing to one and held-out gap inference']
        method_quantity = 'post-treatment treated-minus-synthetic gap relative to its held-out untreated validation mean'
        if method == 'synthdid':
            if facts.get('common_treatment_block') is False:
                raise ValueError('synthdid requires a common treated block')
            method_quantity = 'average treatment effect over the common treated unit-time block'
            conditions = ['balanced outcome panel with a common treatment block','eligible untreated donor units','unit and time weights selected by synthdid','adopted bootstrap, jackknife or placebo inference']
        elif method == 'generalized_synth':
            method_quantity = 'treated-block average relative to the interactive fixed-effects counterfactual'
            conditions = ['stable factor counterfactual','identified factor rank and untreated support','adopted gsynth bootstrap']
        required_inputs = ['treated units','eligible donors','pre/post periods','balanced outcome panel','target aggregation and inference method']
        alternatives = [
            {'method':'synthetic_control','difference':'convex donor combination learned on pretreatment outcomes',
             'estimand':'post-treatment gap relative to its held-out untreated validation mean',
             'conditions':['eligible untreated donors','stable expected untreated gaps','independent held-out time errors for the implemented covariance'],
             'data_fit':{'required':['one treated unit, balanced donors and distinct training/validation/post periods'], 'data_structures':['panel']},
             'inference':{'procedure':'HC1 covariance across held-out time gaps conditional on trained donor weights'}},
            {'method':'synthdid','difference':'joint unit and time weighting for a common treatment block',
             'estimand':'average effect over the adopted treated unit-time block',
             'conditions':['common treatment block','eligible untreated donor panel','identified weighted counterfactual'],
             'data_fit':{'required':['balanced unit-period outcomes and common treatment timing'], 'data_structures':['panel']},
             'inference':{'procedure':'official bootstrap, jackknife or placebo variance chosen for the adopted assignment model'}},
            {'method':'generalized_synth','difference':'interactive fixed-effects untreated counterfactual',
             'estimand':'treated-block average and event-time effects relative to the fitted factor counterfactual',
             'conditions':['stable factor structure','identified rank and untreated support','adopted error model'],
             'data_fit':{'required':['balanced panel, never-treated units and at least five pretreatment periods'], 'data_structures':['panel']},
             'inference':{'procedure':'seeded official parametric bootstrap'}}]
    elif design == 'generalized_synth':
        method = 'generalized_synth'
        conditions = ['balanced panel with never-treated controls and one common absorbing adoption date', 'adopted factor rank and two-way interactive-effects specification', 'parametric bootstrap under the adopted error model']
        method_quantity = 'treated-block average and event-time effects relative to the interactive fixed-effects counterfactual'
    elif design == 'orthogonal_score':
        if score is None:
            score = 'irm' if target_kind in ('ate','att') else 'iivm' if target_kind=='late' else 'plr'
        if score in ('plr','irm') and facts.get('conditional_exchangeability') is False:
            raise ValueError('an unconfounded-treatment score requires conditional exchangeability; use the identified instrument score for endogeneity')
        if score=='irm' and facts.get('overlap') is False:
            raise ValueError('the interactive-regression ATE/ATT score requires overlap in its target population')
        if score not in ('plr','did','irm','pliv','iivm'):
            raise ValueError('score must be plr, did, irm, pliv or iivm')
        method = 'dml_' + score; owner = 'skills/econ-data/scripts/research.py estimate'
        conditions = ['score identifies the stated target', 'folds preserve independent sampling units', 'nuisance fitting and tuning use training folds']
        method_quantity = {'plr':'partially linear structural slope with residual-treatment weighting',
            'did':'two-period ATT under the adopted DoubleML DID score',
            'irm':'E[Y(1)-Y(0)|D=1]' if target_kind=='att' else 'E[Y(1)-Y(0)]',
            'pliv':'partially linear instrumental-variable moment coefficient',
            'iivm':'local average treatment effect among instrument compliers'}[score]
        if score == 'plr' and (target_kind in ('att','late','cate','policy_value') or
                (target_kind == 'ate' and facts.get('effect_heterogeneity') != 'constant')):
            raise ValueError('PLR targets its partially linear slope; choose a score identifying the requested target')
        required_inputs = ['mathematical score','outcome/treatment/covariates','fold assignment at independent units','nuisance learner and training-only tuning']
        if score in ('irm','pliv','iivm'):
            owner = 'skills/econ-data/scripts/research_causal.py run'
            selected_score = (('ATTE' if target_kind=='att' else 'ATE') if score=='irm'
                else 'LATE' if score=='iivm' else forward_options.get('score','partialling out'))
            if score == 'pliv' and selected_score not in ('partialling out','IV-type'):
                raise ValueError('DoubleMLPLIV score must be partialling out or IV-type')
            required_native_options['score'] = selected_score
            if score == 'irm' and target_kind == 'att' and forward_options.get('weights') is not None:
                raise ValueError('DoubleMLIRM weights implements a weighted ATE and is incompatible with score=ATTE')
        if score in ('pliv','iivm'):
            conditions += ['valid excluded instruments and the specified instrument score']
            required_inputs += ['instrument columns and instrument/treatment support']
        alternatives = [
            {'method':'dml_irm','difference':'interactive-regression score for the specified treatment population',
             'estimand':'ATE or ATT selected by the official ATE/ATTE score',
             'conditions':['conditional exchangeability','overlap','orthogonal-score nuisance rate conditions'],
             'data_fit':{'required':['binary treatment, outcome, covariates and independent scoring folds']},
             'inference':{'procedure':'official cross-fitted score inference with the adopted independent units'}},
            {'method':'dml_iivm','difference':'instrument score identifies the complier population',
             'estimand':'LATE for binary-instrument compliers',
             'conditions':['instrument independence and exclusion','monotonicity','nonzero first stage','instrument overlap'],
             'data_fit':{'required':['binary treatment and instrument, outcome, covariates and independent scoring folds']},
             'inference':{'procedure':'official cross-fitted instrumental score inference; weak-IV sets require their own procedure'}}]
    elif design == 'heterogeneous_effect':
        implementation = request.get('implementation', 'grf')
        if implementation not in ('grf','econml'):
            raise ValueError('heterogeneous_effect implementation must be grf or econml')
        method = 'causal_forest' if implementation == 'econml' else 'grf'
        conditions = ['conditional exchangeability and overlap',
            'binary treatment with cross-fitted nuisance learners' if implementation == 'econml' else 'binary CATE or continuous covariance-to-variance target',
            'adopted effect covariates, independent sampling units and averaging population']
        method_quantity = 'conditional treatment effects and their adopted target-population aggregate'
        required_inputs = ['effect covariates','treatment support','outcome','overlap population','honesty and independent sampling folds','target aggregation weights']
        if facts.get('conditional_exchangeability') is False or facts.get('overlap') is False:
            raise ValueError('the selected forest requires conditional exchangeability and overlap')
        alternatives = [
            {'method':'dml_plr','difference':'partially linear slope weighted by residual treatment variation',
             'estimand':'partially linear coefficient; ATE under the explicit constant-effect restriction',
             'conditions':['partially linear conditional mean','exogenous residual treatment','cross-fitted nuisance rate conditions'],
             'data_fit':{'required':['outcome, treatment, covariates and independent scoring folds']},
             'inference':{'procedure':'official DoubleMLPLR orthogonal-score covariance'}},
            {'method':'policy_tree','difference':'learn an assignment rule and evaluate its held-out gain',
             'estimand':'policy value relative to assigning treatment zero to the evaluation population',
             'conditions':['known propensities','conditional exchangeability and overlap','independent policy training and evaluation'],
             'data_fit':{'required':['binary treatment, propensities and explicit train/evaluation partitions']},
             'inference':{'procedure':'HC1 holdout-value covariance conditional on the trained policy'}}]
    elif design == 'policy_learning':
        if facts.get('conditional_exchangeability') is False or facts.get('overlap') is False:
            raise ValueError('policy evaluation requires conditional exchangeability and overlap in its evaluation population')
        method = 'policy_tree'
        conditions = ['binary treatment and known assignment propensities', 'distinct training and evaluation samples', 'adopted effect covariates and the untreated-all baseline']
        method_quantity = 'held-out policy value gain relative to assigning treatment zero to every evaluation unit'
        required_inputs = ['known assignment propensities','separate training/evaluation partitions','effect covariates','treatment cost and capacity in the adopted objective']
        alternatives = [{'method':'grf','difference':'conditional effects preceding a separate allocation decision',
            'estimand':'binary-treatment CATE or the continuous-treatment covariance-to-variance slope',
            'conditions':['conditional exchangeability and overlap','honest estimation and the adopted nuisance restrictions'],
            'data_fit':{'required':['outcome, treatment, effect covariates and target-population weights']},
            'inference':{'procedure':'official forest prediction variance and target-population aggregation'}}]
    elif design == 'parallel_trend_sensitivity':
        method = 'honest_did'; conditions = ['saved coefficients and joint covariance', 'ordered pre/post terms with universal reference', 'adopted restriction, magnitude grid and post-treatment contrast']
    elif design == 'wild_cluster_inference':
        method = 'wild_cluster_bootstrap'; conditions = ['saved supported linear-model fit', 'adopted null, clusters, bootstrap weights and repetitions']
    elif design == 'small_cluster_inference':
        method = 'club_sandwich'; conditions = ['saved supported model fit', 'adopted CR correction, coefficient contrast and degrees-of-freedom approximation']
    elif design == 'structural':
        requested_operation = numerical.get('operation', adopted_spec.get('operation'))
        model = request.get('structural_model')
        if not model and adopted == 'finite_horizon_choice' and requested_operation in ('simulate','counterfactual'):
            model = adopted
        condition_model = {'differentiated_products':'blp','replacement':'replacement','dynamic_game':'dynamic_game',
            'quantity_competition':'cournot'}.get(facts.get('market_structure'))
        economic_object_model = {'representative_household_growth':'finite_horizon_growth',
                'household_consumption_saving':'consumption_saving',
                'stationary_incomplete_markets':'aiyagari', 'one_asset_hank':'hank_one_asset',
                'stochastic_representative_growth':'stochastic_rbc',
                'finite_complete_information_game':'correlated_equilibrium',
                'transferable_utility_game':'tu_shapley_core',
                'interbank_liabilities':'interbank_clearing',
                'quantity_quality_effort':'multitask_incentives',
                'finite_state_claim':'state_price_bounds',
                'capacity_constrained_quantity_competition':'cournot',
                'binary_logit_moments':'binary_logit','finite_policy_sir':'finite_policy_sir',
                'queue_capacity':'queue_capacity','decision_rights':'decision_rights',
                'employment_retirement_regimes':'lifecycle_choice'}.get(facts.get('economic_object'))
        if facts.get('economic_object') == 'individual_dynamic_choice':
            # The adopted state/action domain governs estimation and welfare
            # simulation through the same model.
            economic_object_model = (model or
                (contract_binding['structural_model'] if contract_binding else None) or adopted)
            if economic_object_model not in ('finite_horizon_choice', 'lifecycle_choice', 'consumption_saving'):
                raise ValueError('individual_dynamic_choice requires the adopted structural_model or model_contract_id for its state/action domain')
        if condition_model and economic_object_model and condition_model != economic_object_model:
            raise ValueError('market_structure and economic_object identify different structural models')
        condition_model = condition_model or economic_object_model
        if model and condition_model and model != condition_model:
            raise ValueError('structural_model and declared economic conditions identify different models')
        if contract_binding:
            bound_model = contract_binding['structural_model']
            if any(value is not None and value != bound_model for value in (model, condition_model)):
                raise ValueError(f'{contract_id} binds structural_model={bound_model}; declared economic model differs')
            model = bound_model
        elif not model:
            model = condition_model
        if model in ('blp','auction','auction_fit','search','bargaining','platform','matching'):
            method = model; owner = 'skills/econ-data/scripts/research_markets.py run'
        elif model in ('replacement','latent_replacement','discrete_entry','dynamic_adoption_blp','continuous_time_entry','capacity_product_game'):
            method = model; owner = 'skills/econ-data/scripts/research_dynamic.py run'
        elif model == 'dynamic_game':
            method = model; owner = 'skills/econ-data/scripts/equity.py dynamic'
        elif model == 'cournot':
            method = model; owner = 'skills/econ-data/scripts/equity.py fit'
        elif model == 'finite_horizon_growth':
            method = model; owner = 'skills/econ-data/scripts/research_macro.py solve'
        elif model == 'aiyagari':
            method = model; owner = 'skills/econ-data/scripts/research_macro_extended.py run'
        elif model == 'stochastic_rbc':
            method = model; owner = 'skills/econ-data/scripts/research_dsge.py run'
        elif model in ('correlated_equilibrium','tu_shapley_core','interbank_clearing','multitask_incentives','state_price_bounds',
                       'binary_logit','finite_policy_sir','queue_capacity','decision_rights'):
            method = model; owner = 'skills/econ-data/scripts/research_numerics.py run'
            numerical_kernel = {'interbank_clearing':'clearing_payments','binary_logit':'moment_map'}.get(model,model)
        elif model in ('finite_horizon_choice','lifecycle_choice','consumption_saving','hank_one_asset','dolo_yaml'):
            method = model
        else:
            raise ValueError('structural_model must name a documented market, dynamic, macro, finite-game, clearing, multitask, state-price or declared Dolo model')
        conditions = ['adopted primitives, timing, moments and excluded variation', 'normalizations and equilibrium selection', 'counterfactual re-solves affected endogenous choices']
        method_quantity = ('identified utility/cost parameters and scenario-specific equilibrium prices, choices and welfare' if model == 'blp'
            else 'identified payoff/transition parameters and the re-solved policy or equilibrium under the adopted intervention')
        respy_simulation = model == 'finite_horizon_choice' and requested_operation in ('simulate','counterfactual')
        ssj_operations = ('solve_steady_state','solve_jacobian','solve_impulse_linear','solve_impulse_nonlinear')
        ssj_operation = (requested_operation or 'solve_steady_state') if model == 'hank_one_asset' else None
        if ssj_operation is not None and ssj_operation not in ssj_operations:
            raise ValueError(f'hank_one_asset requires numerical.operation in {ssj_operations}')
        algorithms = {'blp':('gmm',), 'replacement':('nfxp','ccp','smm','mpec'),
            'latent_replacement':('em',),'discrete_entry':('moment_inequalities','npl','epl','slc'),
            'dynamic_adoption_blp':('share_inversion',),'continuous_time_entry':('nfxp',),
            'capacity_product_game':('nfxp',),'dynamic_game':('nfxp','mpec'),
            'auction_fit':('maximum_likelihood',),'auction':('equilibrium',),
            'search':('equilibrium',),'bargaining':('equilibrium',),
            'platform':('equilibrium',),'matching':('deferred_acceptance',),
            'finite_horizon_choice':('backward_induction',) if respy_simulation else ('smm','maximum_likelihood'),
            'lifecycle_choice':('backward_induction',),
            'finite_horizon_growth':('slsqp',),'consumption_saving':('backward_induction',),
            'aiyagari':('policy_iteration_brentq',),'hank_one_asset':(ssj_operation,),
            'stochastic_rbc':('time_iteration','linearized_euler') if request.get('implementation') == 'dolo' else ('linearized_euler','time_iteration'),
            'dolo_yaml':('time_iteration',), 'correlated_equilibrium':('linear_program',),
            'tu_shapley_core':('exact_enumeration',), 'interbank_clearing':('greatest_fixed_point',),
            'multitask_incentives':('kkt',), 'state_price_bounds':('linear_program',),
            'binary_logit':('analytic_moments',),'finite_policy_sir':('solve_ivp',),
            'queue_capacity':('closed_form',),'decision_rights':('active_set',),'cournot':('equilibrium',)}
        solution_model = model in ('finite_horizon_growth','consumption_saving','lifecycle_choice',
            'aiyagari','hank_one_asset','stochastic_rbc','dolo_yaml','cournot') or respy_simulation or numerical_kernel is not None
        numerical_key = 'solution_method' if solution_model else 'estimation_method'
        default_algorithm = (adopted_spec.get('estimation', {}).get('method', algorithms[model][0])
            if model == 'finite_horizon_choice' and not respy_simulation else algorithms[model][0])
        if model == 'replacement':
            default_algorithm = adopted_spec.get('options', {}).get('estimation_method', default_algorithm)
        if model == 'stochastic_rbc' and adopted_spec.get('options', {}).get('algorithm') == 'dolo_time_iteration':
            default_algorithm = 'time_iteration'
        algorithm = numerical.get(numerical_key, numerical.get('estimation_method', default_algorithm))
        if solution_model and 'solution_method' in numerical and 'estimation_method' in numerical and numerical['solution_method'] != numerical['estimation_method']:
            raise ValueError('numerical.solution_method and the legacy estimation_method must agree')
        if algorithm not in algorithms[model]:
            raise ValueError(f'{model} implements numerical.{numerical_key} in {algorithms[model]}')
        required_native_options['solution_component' if solution_model else 'estimation_component'] = algorithm
        if solution_model or model == 'finite_horizon_choice':
            if numerical_kernel is not None:
                available_operations = ['solve']
            elif model == 'hank_one_asset':
                available_operations = list(ssj_operations)
            elif respy_simulation:
                available_operations = ['simulate','counterfactual']
            elif model == 'dolo_yaml' or model == 'stochastic_rbc' and algorithm == 'time_iteration':
                available_operations = ['time_iteration','reuse_solution']
            elif model in ('finite_horizon_growth','aiyagari','stochastic_rbc','cournot'):
                available_operations = ['solve','counterfactual']
            else:
                available_operations = ['solve','simulate','counterfactual'] if solution_model else ['estimate']
            operation = requested_operation or ssj_operation or (
                'time_iteration' if model == 'dolo_yaml' or model == 'stochastic_rbc' and algorithm == 'time_iteration'
                else 'solve' if solution_model else 'estimate')
            if operation not in available_operations:
                raise ValueError(f'{model} supports numerical.operation in {available_operations}')
            if solution_model and facts.get('parameter_status') not in (None,'fixed','calibrated','estimated'):
                raise ValueError(f'{model} requires fixed, calibrated or previously estimated parameters')
            computation = {'requested_operation':operation,'available_operations':available_operations,
                'numerical_method':algorithm,'operations_executed':[],
                'parameter_operation':'reuse fixed, calibrated or previously estimated values' if solution_model else 'estimate identified free parameters',
                'identification_target':target or {'expression':request['estimand']},
                'observation_map':economic_model.get('observed_data'),
                'identified_parameters':economic_model.get('identified_parameters')}
        if model == 'dynamic_game':
            required_native_options['estimation_method'] = algorithm
        if model == 'replacement' and algorithm == 'smm':
            required_native_options['options.smm'] = 'adopted seed, replications, initial_costs, bounds and tolerance'
        if model == 'replacement' and algorithm == 'mpec':
            owner = 'skills/econ-data/scripts/research_dynamic.py run'
            required_native_options = {'estimation_method':'mpec'}
            native_function = 'ruspy.estimation.criterion_function.get_criterion_function'
        if contract_id == 'MC-replacement-ddc' and forward_options.get('replacement_timing', 'reset_to_zero') != 'reset_to_zero':
            raise ValueError('MC-replacement-ddc fixes reset-to-zero transitions; select the explicitly adopted native replacement model without that contract')
        required_inputs = ['actors/objectives/feasible actions/information and timing','states and transition law',
            'shock distribution and payoff normalization','moments or likelihood and excluded variation',
            'parameter order and fixed/calibrated values','equilibrium selection','intervention and welfare aggregation']
        if numerical_kernel is not None:
            if forward_options:
                raise ValueError('numerical model arguments belong in adopted_specification.inputs')
            rid = 'research-numerics'
            numerical_relative = resources[rid]['source_path'] if layout_path == 'source_path' else placements[rid][layout_path]
            numerical_path = (ROOT.parent if ROOT.name == '.agents' else ROOT) / numerical_relative
            numerical_spec = importlib.util.spec_from_file_location('selected_numerical_model', numerical_path)
            numerical_module = importlib.util.module_from_spec(numerical_spec)
            numerical_spec.loader.exec_module(numerical_module)
            numerical_signature = inspect.signature(getattr(numerical_module, numerical_kernel))
            required_inputs = ['inputs.'+name for name, parameter in numerical_signature.parameters.items()
                               if parameter.default is inspect.Parameter.empty] + ['unit']
            required_native_options = {}
            if model == 'correlated_equilibrium':
                if facts.get('recommendation_timing') not in (None,'private_before_action'):
                    raise ValueError('correlated equilibrium requires private recommendations before actions')
                if facts.get('complete_information') is False:
                    raise ValueError('correlated equilibrium requires complete-information payoffs')
                method_quantity = 'joint action probabilities maximizing the supplied weighted expected payoff subject to every conditional deviation inequality'
                conditions = ['finite complete-information game with one action axis per player',
                    'each player observes only its own recommendation before choosing',
                    'supplied weights define the common-unit payoff objective and equilibrium selection']
            elif model == 'tu_shapley_core':
                if facts.get('transferable_utility') is False or facts.get('coalition_externalities') is True:
                    raise ValueError('Shapley/core requires transferable coalition values with fixed outside terms')
                method_quantity = 'exact Shapley allocation and every coalition slack for that allocation'
                conditions = ['finite transferable-utility game with empty-coalition value zero',
                    'coalition values in bit-mask order with fixed outside transaction terms',
                    'core membership evaluates the returned Shapley allocation']
            elif model == 'interbank_clearing':
                if facts.get('repayment_priority') not in (None,'equal_pro_rata'):
                    raise ValueError('interbank clearing requires equal-priority pro-rata repayment')
                if facts.get('bankruptcy_costs') not in (None,False,0):
                    raise ValueError('interbank clearing implements zero bankruptcy resource costs')
                method_quantity = 'greatest clearing payments, outside-creditor recoveries and residual bank equity'
                conditions = ['nonnegative debtor-row liabilities, zero self-liabilities and nonnegative external assets',
                    'one simultaneous clearing period with equal-priority pro-rata repayment and limited liability',
                    'greatest fixed point selected by iteration from nominal payments',
                    'outside payments plus equity equal external assets at the adopted residual tolerance']
            elif model == 'state_price_bounds':
                if facts.get('free_trading') is False or facts.get('all_states_possible') is False:
                    raise ValueError('state-price bounds require freely traded assets and every supplied state to be possible')
                method_quantity = 'no-arbitrage claim-price bounds, endpoint inclusion and the subhedge, superhedge or replicating portfolio'
                conditions = ['finite possible states and freely traded assets with unrestricted portfolio holdings',
                    'at least one traded asset pays strictly positively in every state',
                    'existing asset prices admit strictly positive state prices',
                    'an unspanned claim has an open price interval; a replicated claim has its unique replication price']
            elif model == 'binary_logit':
                method_quantity = 'mean logit probability and regressor-weighted probability, with their parameter Jacobian'
                conditions = ['supplied intercept and slope held fixed','finite observed covariate support',
                    'logistic response probability and its analytic derivatives']
            elif model == 'finite_policy_sir':
                method_quantity = 'SIR state trajectory and integrated loss under the supplied finite policy schedule'
                conditions = ['nonnegative susceptible, infected and recovered initial states',
                    'fixed transmission and recovery rates and finite dated controls',
                    'population conservation and the supplied infection, control and terminal loss weights']
            elif model == 'queue_capacity':
                method_quantity = 'stationary M/M/1 utilization, mean system/queue length and mean system/queue waiting time'
                conditions = ['Poisson arrivals and exponential single-server service',
                    'nonnegative arrival rate and positive service rate with arrival rate below service rate']
            elif model == 'decision_rights':
                method_quantity = 'principal and agent information effort and payoffs under the specified authority holder'
                conditions = ['supplied project payoffs, effort costs and preference alignment',
                    'principal or agent holds formal authority','efforts satisfy the original best-response bounds']
            else:
                method_quantity = 'quantity and quality effort and both principal and agent payoffs at the supplied contract'
                conditions = ['fixed nonnegative salary, quantity reward and private quality benefit',
                    'nonnegative efforts and quadratic cost with absolute interaction coefficient below one',
                    'agent best response satisfies both original KKT conditions',
                    'principal values quantity and quality at the supplied coefficients']
            computation.update(parameter_operation='hold supplied model inputs fixed; estimate no parameters',
                solution_object=method_quantity,
                outputs=[row['name'] for row in model_contract['outputs']] if model_contract else [method_quantity])
        elif model == 'cournot':
            required_native_options = {}
            method_quantity = 'capacity-constrained firm quantities, market prices and profits under baseline and changed market inputs'
            conditions = ['decreasing linear inverse demand and convex variable costs',
                'nonnegative quantities within firm capacities','Nash best responses at the adopted equilibrium tolerance',
                'supplied demand coefficients or excluded cost instruments identifying aggregate quantity']
            required_inputs = ['sources','identification','market','as_of','currency','price_unit','quantity_unit',
                'inverse_demand','markets']
            computation.update(solution_object=method_quantity,
                parameter_operation='estimate inverse demand by 2SLS when observations are supplied; otherwise reuse supplied coefficients',
                outputs=['baseline and counterfactual market and firm quantities, prices, costs, profits and capacity shadow prices'])
        elif model == 'finite_horizon_growth':
            method_quantity = 'optimal finite-horizon capital and consumption paths and discounted log-consumption welfare conditional on initial and terminal capital'
            conditions = ['representative household, log utility and Cobb-Douglas production',
                'positive consumption and capital; fixed initial and terminal capital with no continuation utility',
                'deterministic productivity and output-tax paths; tax revenue finances government absorption',
                'fixed or previously estimated alpha, beta and delta; original Euler/resource residuals within tolerance']
            required_inputs = ['alpha, beta, delta, initial_capital and terminal_capital',
                'baseline and scenario, each with equal-horizon productivity and output_tax paths',
                'population, period, unit, sources and tolerance']
            computation['outputs'] = ['baseline and scenario capital, consumption, output and government_absorption paths',
                'discounted log-consumption welfare and scenario-minus-baseline welfare_change',
                'original Euler/resource residuals and analytic-derivative comparisons']
            computation['solution_object'] = 'optimal trajectories at the supplied endpoints; a feedback policy function requires the corresponding state-space model'
        elif model == 'aiyagari':
            if facts.get('aggregate_shocks') is True or facts.get('stationary_equilibrium') is False:
                raise ValueError('aiyagari selects stationary equilibria with a fixed aggregate productivity in each scenario')
            method_quantity = 'scenario-specific stationary capital, competitive prices, household policies, invariant distributions and stationary population welfare'
            conditions = ['unit mass of infinitely lived households; CRRA utility and inelastic Markov labor efficiency',
                'finite increasing asset grid, positive consumption and irreducible income transition',
                'competitive Cobb-Douglas production with labor aggregated from the same income distribution',
                'one recurrent class in each evaluated household-policy transition',
                'Bellman, distribution, capital and resource residuals meet the adopted tolerances']
            required_inputs = ['model=aiyagari and calibration_source',
                'parameters: alpha, beta, delta, crra, asset_grid, income_states, income_transition',
                'baseline.productivity and scenario.productivity',
                'solver: capital_bracket, capital_tolerance, bellman_tolerance, distribution_tolerance, resource_tolerance, max_iterations']
            computation.update(parameter_operation='hold the supplied calibrated primitives; estimate no parameters',
                solution_object='two stationary equilibria, each with its own household policy and invariant distribution',
                outputs=['baseline/scenario capital, output, consumption, investment, net interest rate and wage',
                    'asset and consumption policies, value and stationary distribution by asset/income state',
                    'stationary mean value and stationary consumption equivalent',
                    'original Bellman, household-budget, distribution, capital and resource diagnostics'])
            required_native_options = {}
        elif model == 'hank_one_asset':
            if facts.get('nominal_rigidity') is False:
                raise ValueError('hank_one_asset requires the declared nominal-price and general-equilibrium conditions')
            if target_kind == 'welfare' and ssj_operation in ('solve_jacobian','solve_impulse_linear'):
                raise ValueError('HANK transition welfare requires solve_impulse_nonlinear with the saved household policies and distribution')
            function = 'sequence_jacobian.blocks.block.Block.' + ssj_operation
            owner = 'skills/econ-data/scripts/research_dsge.py run'
            method_quantity = ('calibrated one-asset HANK steady state satisfying the adopted targets' if ssj_operation == 'solve_steady_state'
                else 'one-asset HANK general-equilibrium Jacobian' if ssj_operation == 'solve_jacobian'
                else 'linear one-asset HANK equilibrium impulse paths' if ssj_operation == 'solve_impulse_linear'
                else 'nonlinear one-asset HANK equilibrium transition paths')
            conditions = ['the HET-03 household, monetary, fiscal and Rotemberg-price equations with common units and timing',
                'adopted income process, asset grid, borrowing limit and distribution weights',
                'steady-state calibration targets and transition unknowns/targets kept distinct',
                'fixed initial distribution and terminal steady state over the requested horizon',
                'original household, distribution, asset, labor, goods and pricing residuals retained']
            required_inputs = ['declared model blocks and calibration; constructing the model preserves the adopted equations',
                'steady-state model unknown initial values/brackets and target values, or the saved matching SteadyStateDict',
                'transition unknowns [w,Y,pi] and targets [asset_mkt,goods_mkt,nkpc_res]',
                'inputs: shock names for solve_jacobian, or adopted rstar/Z shock arrays for impulse operations',
                'horizon, requested outputs, original residuals and household internals needed by the target']
            native_function = function
            computation['parameter_operation'] = ('calibrate the declared steady-state unknowns to the adopted targets' if ssj_operation == 'solve_steady_state'
                else 'reuse the matching steady-state parameters, policy and distribution')
            required_native_options = {}
        elif model in ('stochastic_rbc','dolo_yaml'):
            if model == 'stochastic_rbc':
                restrictions = {'utility':'log','production':'cobb_douglas',
                    'labor_supply':'fixed_unit','productivity_process':'stationary_gaussian_ar1'}
                for field, expected in restrictions.items():
                    if field in facts and facts[field] != expected:
                        raise ValueError(f'stochastic_rbc requires conditions.{field}={expected}')
            dolo_entry = model == 'dolo_yaml' or algorithm == 'time_iteration'
            if request.get('implementation') == 'dolo' and not dolo_entry:
                raise ValueError('implementation=dolo requires numerical.solution_method=time_iteration')
            conditions = (['infinite-lived household with log utility, fixed unit labor and Cobb-Douglas production',
                'stationary zero-mean Gaussian AR(1) log productivity and calibrated alpha, beta and delta',
                'positive consumption, adopted capital timing and original Euler/resource equations']
                if model == 'stochastic_rbc' else ['declared YAML state, control, shock and parameter coordinates implement the adopted economic model',
                    'transition and arbitrage equations, shock timing, constraints and normalization match the requested equilibrium'])
            if dolo_entry:
                function = ('dolo.compiler.model_import.yaml_import + dolo.algos.steady_state.find_steady_state + '
                    'dolo.algos.steady_state.residuals + dolo.algos.time_iteration.time_iteration + dolo.numeric.residuals.F')
                owner = 'skills/econ-data/scripts/research_dsge.py run'
                method_quantity = 'decision rule for the adopted dynamic model, with steady-state equations and original final-policy arbitrage residuals'
                required_inputs = ['native Dolo YAML filename with the adopted equations, calibration, state/control/shock timing and bounds',
                    'same DiscretizedModel, grids and shock-process discretization throughout solution and residual evaluation',
                    'adopted interpolation, backend, initial decision rule and convergence tolerances',
                    'final decision rule evaluated on the same grid/regimes for original residuals.F']
                required_native_options = {}
                native_function = function
                computation.update(parameter_operation='reuse the adopted calibration; estimate no parameters',
                    solution_object='dynamic decision rule of the explicitly supplied model')
            else:
                method_quantity = 'AR(1) productivity estimates, local RBC policy, conditional impulse responses, stochastic allocations and finite-horizon welfare with terminal continuation'
                required_inputs = ['parameters.alpha, beta and delta',
                    'observations: type, source, path, sha256, period_column, value_column',
                    'horizon, simulation_paths, seed and technology_shock']
                required_native_options = {}
                computation.update(parameter_operation='estimate AR(1) persistence and innovation variance; hold preferences and technology coefficients fixed',
                    solution_object='local first-order capital policy with exact resource accounting',
                    outputs=['AR(1) estimates and covariance','linearized Euler/resource coefficients and residuals',
                        'conditional impulse responses, stochastic paths and forecast moments','finite-horizon welfare with terminal continuation'])
        elif model == 'consumption_saving':
            income_process = facts.get('income_process', adopted_spec.get('income_process'))
            classes = {'perfect_foresight':'PerfForesightConsumerType','idiosyncratic_shocks':'IndShockConsumerType'}
            if income_process not in classes:
                raise ValueError('consumption_saving requires conditions.income_process=perfect_foresight or idiosyncratic_shocks')
            function = 'HARK.ConsumptionSaving.ConsIndShockModel.' + classes[income_process]
            owner = 'skills/econ-data/scripts/research_macro_extended.py run'
            method_quantity = 'age-specific consumption policies, normalized value functions and simulated asset/income paths at adopted parameters'
            conditions = ['finite lifecycle with cycles=1 and T_cycle periods plus the terminal solution',
                'CRRA utility, adopted discounting, survival, income growth, returns and borrowing constraints',
                'terminal consumption equals cash on hand in these consumer classes',
                'initial population and income/shock timing match the adopted model',
                'prices are exogenous; welfare uses declared value units, population weights and scenario contrast']
            required_inputs = ['income_process','consumer_options with cycles, T_cycle, CRRA, DiscFac, Rfree, LivPrb, PermGroFac and BoroCnstArt',
                'evaluation.mNrm with adopted periods and optional population weights','calibration_source',
                'simulation for requested histories; scenario.consumer_options for a requested counterfactual']
            if income_process == 'idiosyncratic_shocks':
                required_inputs += ['PermShkStd, TranShkStd, shock distributions, integration counts and asset grid']
            required_native_options = {'consumer_options.cycles':1}
            if income_process == 'idiosyncratic_shocks':
                required_native_options['consumer_options.vFuncBool'] = True
            computation.update(solution_object=method_quantity,
                outputs=['solve() stores T_cycle+1 ConsumerSolution objects in consumer.solution',
                    'solution[t].cFunc(mNrm) and vFunc(mNrm), with permanent-income normalization',
                    'simulate() stores each track_vars history as a (T_sim, AgentCount) array',
                    'scenario-specific values and outcomes aggregated with the adopted population weights'])
        elif respy_simulation:
            simulation_method = numerical.get('simulation_method', adopted_spec.get('simulation', {}).get('method'))
            if simulation_method not in ('n_step_ahead_with_sampling','n_step_ahead_with_data','one_step_ahead'):
                raise ValueError('respy simulation requires numerical.simulation_method=n_step_ahead_with_sampling, n_step_ahead_with_data or one_step_ahead')
            if facts.get('parameter_status') not in ('fixed','calibrated','estimated'):
                raise ValueError('respy simulation requires explicit fixed, calibrated or estimated parameter_status')
            owner = 'skills/econ-data/scripts/research_dynamic.py run'
            method_quantity = ('scenario contrast of adopted discounted chosen-flow utility for the same initial population' if target_kind == 'welfare'
                else 'scenario-specific choices, rewards and state paths from the same respy structural primitives')
            if simulation_method == 'one_step_ahead':
                if target_kind == 'welfare':
                    raise ValueError('respy lifecycle welfare requires an n-step simulation of the counterfactual state path')
                method_quantity = 'one-period choices and rewards conditional on each observed state under the adopted respy scenario'
            conditions = ['reuse the fitted respy parameter ordering, normalizations, model options and invariant primitives',
                'declare sampled initial conditions, fixed observed initial states or observed one-step states',
                'hold the adopted population, scenario draws, choice ordering and horizon comparison fixed',
                'aggregate chosen flow utility with adopted discounting, present-bias interpretation and terminal evaluation']
            required_inputs = ['params: fixed or saved estimated parameter dataframe/series with provenance',
                'options: the same structural model, decision horizon, initial distributions, solution/simulation seeds and draws',
                'numerical.simulation_method and the adopted scenario changes',
                'target population, identifiers, weights, value units and welfare aggregation']
            if simulation_method != 'n_step_ahead_with_sampling':
                required_inputs += ['df with Identifier/Period MultiIndex and the adopted state columns; initial-data simulation uses zero-based consecutive IDs at Period=0']
            required_native_options = {}
            native_function = 'respy.get_simulate_func'
            computation['outputs'] = ['saved ordered parameters and native model options',
                'Identifier/Period-indexed simulated choices, states and rewards',
                'adopted discounted chosen-flow utility and scenario contrasts']
        elif model == 'finite_horizon_choice':
            smm = algorithm == 'smm'
            function = 'respy.get_moment_errors_func' if smm else 'respy.get_log_like_func'
            owner = 'skills/econ-data/scripts/research_dynamic.py run'
            method_quantity = ('structural parameters minimizing the adopted weighted finite-horizon simulated-moment distance' if smm
                else 'structural parameters maximizing the mean log likelihood of the adopted finite-horizon observed histories')
            conditions = ['finite decision horizon, adopted terminal values and feasible state/action support',
                'payoff and shock normalizations, information timing and transition law',
                'parameter-to-moment identification' if smm else 'identified choice/wage likelihood on the adopted observed sample',
                'fixed solution and simulation draws across parameter evaluations']
            required_inputs = ['params: ordered parameter dataframe/series with free and fixed parameters, normalizations and adopted bounds',
                'options: horizon, state/choice definitions, covariates, transitions, integration and simulation settings',
                'observed population, sample selection, measurement units and target weights',
                'solution, simulation and estimation seeds and draw counts',
                'adopted optimizer and structural-parameter inference at the independent sampling unit']
            required_inputs += (['calc_moments and ordered empirical_moments with matching labels',
                'replace_nans rule, weighting_matrix and n_simulation_periods'] if smm
                else ['df: observed choice/wage histories in the official estimation-data format'])
            required_native_options = {}
            native_function = function
            computation['outputs'] = ['fitted ordered structural parameters and optimizer return',
                'official weighted moment criterion and moment errors' if smm else 'official mean log likelihood and contributions',
                'adopted parameter-inference inputs and simulation design']
        elif model == 'lifecycle_choice':
            owner = 'skills/econ-data/scripts/research_macro_extended.py run'
            method_quantity = ('target-population aggregation of lifecycle values under the adopted welfare weights and utility or monetary conversion' if target_kind == 'welfare'
                else 'lifecycle policies, values and simulated outcomes at the adopted fixed or previously estimated parameters')
            conditions = ['fixed or previously estimated structural parameters and adopted utility/shock normalizations',
                'finite horizon and terminal regimes with feasible states, actions, constraints and transition laws',
                'declared information, perceived/realized regime transitions and initial-population distribution',
                'policy scenarios hold the adopted exogenous paths fixed and re-solve affected household choices',
                'welfare aggregation uses the adopted population weights and value units']
            required_inputs = ['lcm.Model: regimes, regime_id_class, initial_nodes and edges',
                'exactly one of ages and n_periods; states, actions, state_transitions, utility functions, constraints and shocks',
                'fixed_params and params matching get_params_template(), including discounting and normalizations',
                'regime-specific official solver, grids, integration and numerical precision',
                'initial_conditions, seed and adopted taste_shock_seed or shock_paths for scenario comparisons',
                'policy intervention, exogenous price paths, target population, weights and welfare aggregation/conversion']
            required_native_options = {}
            native_function = 'lcm.Model.solve + lcm.Model.simulate'
        alternatives = [
            {'method':'nfxp','difference':'solve the Bellman/equilibrium system within each parameter evaluation',
             'estimand':'parameters of the adopted dynamic likelihood and equilibrium selection',
             'conditions':['specified payoff/shock/transition law','identified likelihood and normalization'],
             'data_fit':{'required':['observed states, actions and transitions in the model support']},
             'inference':{'procedure':'adopted likelihood curvature or refitted sampling procedure'}},
            {'method':'mpec','difference':'jointly optimize parameters and values or policies under equilibrium constraints',
             'estimand':'the same structural likelihood parameters under the imposed equilibrium equations',
             'conditions':['the adopted likelihood and normalization','original Bellman or equilibrium constraints'],
             'data_fit':{'required':['the same state/action observations and an identified constrained system']},
             'inference':{'procedure':'structural parameter inference accounting for equilibrium constraints'}},
            {'method':'ccp','difference':'use first-stage choice probabilities and transition estimates',
             'estimand':'payoff parameters identified by the adopted CCP inversion and second-stage criterion',
             'conditions':['shock distribution giving the CCP inversion','choice support and transition identification'],
             'data_fit':{'required':['supported conditional choices and transitions for each evaluated state']},
             'inference':{'procedure':'sampling procedure carrying first-stage CCP and transition estimation'}},
            {'method':'smm','difference':'match observed and simulated moments under fixed simulation draws',
             'estimand':'structural parameters identified by the adopted moment vector and weighting matrix',
             'conditions':['parameter-to-moment identification','adopted initial-state and transition law'],
             'data_fit':{'required':['ordered empirical moments and observed histories in the adopted support']},
             'inference':{'procedure':'adopted moment covariance with the specified simulation contribution'}},
            {'method':'gmm','difference':'match economically identified moments using the adopted weighting matrix',
             'estimand':'parameters satisfying the adopted population moment restrictions',
             'conditions':['moment exclusion and rank','adopted integration and normalization'],
             'data_fit':{'required':['moment observations, instruments and adopted population weights']},
             'inference':{'procedure':'moment covariance matched to the independent market or sampling unit'}},
            {'method':'maximum_likelihood','difference':'maximize the mean log likelihood of the observed finite-horizon histories',
             'estimand':'structural parameters identified by the adopted choice/wage likelihood',
             'conditions':['identified likelihood and utility/shock normalizations','adopted information, state support and transition law'],
             'data_fit':{'required':['observed choice/wage histories and their adopted sampling population']},
             'inference':{'procedure':'adopted likelihood curvature or refitted sampling procedure with the recorded integration draws'}}]
        alternatives = [candidate for candidate in alternatives
                        if candidate['method'] in algorithms[model] and candidate['method'] != algorithm]
    else:
        raise ValueError('unsupported design; use the documented selection contracts')
    if method == 'iv_ar_robust':
        required_inputs = ['data','Y: outcome column','D: one endogenous treatment column',
            'Z: excluded instrument columns','controls: exogenous control columns',
            'FE: adopted fixed effects','cl: adopted cluster columns','weights: adopted weight column','alpha']
        alpha = requested_alpha
        if level is not None:
            if isinstance(level,bool) or not isinstance(level,(int,float)) or not 0<level<1:
                raise ValueError('comparison.confidence_level must be between zero and one')
            if alpha is not None and abs(alpha-(1-level))>1e-12:
                raise ValueError('inference.alpha and comparison.confidence_level must agree')
            alpha = 1-level
        if alpha is None: alpha = forward_options.get('args',{}).get('alpha',.05)
        if isinstance(alpha,bool) or not isinstance(alpha,(int,float)) or not 0<alpha<1:
            raise ValueError('the selected AR alpha must be between zero and one')
        native_alpha = forward_options.get('args',{}).get('alpha')
        if native_alpha is not None and abs(native_alpha-alpha)>1e-12:
            raise ValueError('options.args.alpha must agree with the selected inference level')
        required_native_options = {'args.CI':True,'args.alpha':alpha}
    if method == 'fixes_event_study' and target_kind == 'att':
        method = 'fixes_att'; owner = 'external official R entry: fixes::att'
        required_native_options = {'aggregation':'simple','estimator':'adopted cs or bjs'}
        external_implementation = {'language':'R','function':'fixes::att','version':'1.0.0',
            'source':'https://github.com/yo5uke/fixes/blob/0a1e1cbba31bd344b7599273f973f9c850247c92/R/att.R',
            'inputs':['formula','data','time','timing with never-treated coded NA','unit','estimator','aggregation','comparison and anticipation'],
            'outputs':['aggregate estimates','standard errors','confidence intervals','aggregation/sample attributes'],
            'execution':'invoke the official aggregate function in project analysis; the event-study runner retains dynamic effects'}
    compatible = {
        'rct':{'ate','itt'},'fixest_ols':{'linear_projection','conditional_mean','ate','itt'},
        'hdfe':{'linear_projection','conditional_mean'},'fixest_ppml':{'conditional_mean'},
        'negative_binomial_r':{'count_distribution','conditional_mean'},
        'staggered_did':{'att','group_time_att','event_time_att'},
        'drdid_panel':{'att'},'drdid_rc':{'att'},'sunab':{'att','event_time_att'},
        'did2s':{'att','event_time_att'},'did_imputation':{'att','event_time_att'},
        'fixes_event_study':{'event_time_att'},'fixes_att':{'att'},
        'did_multiplegt_dyn':{'treatment_path_effect','dose_response'},
        'nonabs_did':{'treatment_path_effect','dose_response'},
        'rdrobust_r':{'local_effect','late'} if facts.get('discontinuity')=='fuzzy' else {'local_effect'},
        'rdd_localrand':{'local_effect','ate','itt'},'rddensity':{'density_discontinuity'},'rdpower':{'power'},
        'iv_gmm':{'structural_parameter','late'},'iv_ar':{'confidence_set','structural_parameter','late'},'iv_ar_robust':{'confidence_set','structural_parameter','late'},
        'synthetic_control':{'treated_trajectory'},'synthdid':{'treated_block_att','att'},
        'generalized_synth':{'treated_trajectory','treated_block_att','att','event_time_att'},
        'dml_plr':{'linear_projection','conditional_mean','structural_parameter','ate'},'dml_did':{'att'},
        'dml_irm':{'ate','att'},'dml_pliv':{'structural_parameter'},'dml_iivm':{'late'},
        'grf':{'cate','ate','att'},'causal_forest':{'cate','ate'},'policy_tree':{'policy_value'},
        'honest_did':{'sensitivity','confidence_set'},
        'finite_horizon_choice':{'policy_value','welfare'} if respy_simulation else {'structural_parameter'},'lifecycle_choice':{'policy_value','welfare'},
        'finite_horizon_growth':{'policy_value','welfare'},'consumption_saving':{'policy_value','welfare'},
        'aiyagari':{'equilibrium','welfare'}, 'hank_one_asset':{'equilibrium','welfare'},
        'stochastic_rbc':{'equilibrium'} if native_function else {'equilibrium','welfare','structural_parameter'},
        'dolo_yaml':{'equilibrium'},
        'correlated_equilibrium':{'equilibrium','welfare'}, 'tu_shapley_core':{'allocation'},
        'interbank_clearing':{'equilibrium'}, 'multitask_incentives':{'policy_value'},
        'state_price_bounds':{'price_bounds'},
        'binary_logit':{'conditional_mean'},'finite_policy_sir':{'policy_value','welfare'},
        'queue_capacity':{'equilibrium','policy_value'},'decision_rights':{'equilibrium','policy_value','welfare'},
        'cournot':{'equilibrium','welfare'},
        'smm':{'structural_parameter'},'maximum_likelihood':{'structural_parameter'}}
    accepted_targets = compatible.get(method, {'structural_parameter','equilibrium','welfare'} if design=='structural' else None)
    if target_kind is not None and accepted_targets is not None and target_kind not in accepted_targets:
        raise ValueError(f'{method} implements target.kind in {sorted(accepted_targets)}; received {target_kind}')
    if design=='conditional_mean' and method=='fixest_ols' and target_kind in ('ate','itt'):
        raise ValueError('causal ATE/ITT selection requires the assignment branch and its identifying conditions')
    if method in ('iv_gmm','iv_ar','iv_ar_robust','dml_pliv','dml_iivm') and facts.get('exclusion') is False:
        raise ValueError('the selected IV moment and its test inversion require instrument exclusion')
    if method=='rdrobust_r' and facts.get('discontinuity')=='fuzzy':
        if facts.get('exclusion') is False or facts.get('monotonicity') is False:
            raise ValueError('the fuzzy RD complier effect requires exclusion and local monotonicity')
    if target_kind=='late':
        if facts.get('exclusion') is False or facts.get('monotonicity') is False:
            raise ValueError('LATE requires exclusion and monotonicity for the adopted instrument/receipt comparison')
        conditions += ['binary assignment/receipt compliance population','exclusion and monotonicity','nonzero first-stage receipt response']
    if target_kind=='att' and method=='sunab': required_native_options['aggregation'] = 'att'
    if method in DML_METHODS:
        if level is not None:
            required_native_options['confidence_level'] = level
        if interval_type is not None:
            if interval_type not in ('pointwise','simultaneous','joint'):
                raise ValueError('DoubleML intervals must be pointwise or simultaneous')
            required_native_options['joint'] = interval_type in ('simultaneous','joint')
    if target_kind=='event_time_att' and method=='sunab': required_native_options['aggregation'] = 'period'
    if method=='grf' and target_kind in ('ate','att'):
        required_native_options['aggregation.target.sample'] = 'treated' if target_kind=='att' else 'all'
    if method == 'grf':
        if interval_type not in (None, 'pointwise'):
            raise ValueError('the GRF runner saves pointwise normal intervals from the official aggregate estimate and standard error')
        if level is not None:
            required_native_options['confidence_level'] = level
        if cluster_columns is not None:
            if len(cluster_columns) != 1:
                raise ValueError('grf.clusters requires one adopted independent cluster partition')
            required_native_options['columns.clusters'] = cluster_columns[0]
        selected_weight = proposed_contract.get('weights')
        if isinstance(selected_weight, str):
            required_native_options['columns.sample.weights'] = selected_weight
    if method == 'staggered_did':
        if structure not in ('panel','repeated_cross_section'):
            raise ValueError('group-time DID requires panel or repeated_cross_section data_structure')
        required_native_options['panel'] = structure == 'panel'
        if target_kind in ('att','event_time_att'):
            required_native_options['aggregation.type'] = 'simple' if target_kind == 'att' else 'dynamic'
        if cluster_columns is not None:
            if len(set(cluster_columns) - {forward_options.get('entity')}) > 1:
                raise ValueError('did clustering accepts the entity column and one additional cluster column')
            required_native_options['clustervars'] = cluster_columns
            required_native_options['aggregation.clustervars'] = cluster_columns
        if level is not None:
            required_native_options['alp'] = 1 - level
            required_native_options['aggregation.alp'] = 1 - level
        if interval_type is not None:
            if interval_type not in ('pointwise', 'simultaneous'):
                raise ValueError('did interval_type must be pointwise or simultaneous')
            required_native_options['cband'] = interval_type == 'simultaneous'
            required_native_options['aggregation.cband'] = interval_type == 'simultaneous'
            if interval_type == 'simultaneous':
                required_native_options['bstrap'] = True
                required_native_options['aggregation.bstrap'] = True
        for field in ('anticipation', 'base_period'):
            if field in facts:
                required_native_options[field] = facts[field]
        if proposed_contract.get('comparison_group') in ('nevertreated', 'notyettreated'):
            required_native_options['control_group'] = proposed_contract['comparison_group']
    if method == 'iv_ar':
        required_native_options['alpha'] = 1 - level if level is not None else forward_options.get('alpha', .05)
    if method == 'iv_ar_robust' and cluster_columns is not None:
        required_native_options['args.cl'] = cluster_columns
    if method == 'rdrobust_r':
        if interval_type not in (None, 'pointwise'):
            raise ValueError('rdrobust supplies pointwise robust bias-corrected intervals for the adopted cutoff target')
        if level is not None:
            required_native_options['args.level'] = 100 * level
        if cluster_columns is not None:
            if len(cluster_columns) != 1:
                raise ValueError('rdrobust.cluster requires one adopted independent cluster partition')
            required_native_options['columns.cluster'] = cluster_columns[0]
    if method in ('fixest_ols', 'fixest_ppml', 'sunab') and cluster_columns is not None:
        quoted_columns = ['`' + name.replace('\\', '\\\\').replace('`', '\\`') + '`' for name in cluster_columns]
        required_native_options['args.vcov'] = '~' + '+'.join(quoted_columns)
    if method == 'hdfe':
        if interval_type not in (None, 'pointwise'):
            raise ValueError('the HDFE runner implements pointwise official confint intervals')
        if level is not None:
            required_native_options['confidence_level'] = level
        if cluster_columns is not None:
            if len(cluster_columns) != 1:
                raise ValueError('the HDFE runner requires one declared independent cluster column')
            native_vcov = forward_options.get('vcov', {})
            adjustment = 'CRV3' if isinstance(native_vcov, dict) and 'CRV3' in native_vcov else 'CRV1'
            required_native_options['vcov'] = {adjustment:cluster_columns[0]}
        selected_weight = proposed_contract.get('weights')
        if isinstance(selected_weight, str):
            required_native_options['weights'] = selected_weight
        elif selected_weight is not None and not forward_options.get('weights'):
            raise ValueError('HDFE weights require the actual column in options.weights or a string weights binding')
    if method in ('ols_r', 'fixest_ols', 'fixest_ppml', 'negative_binomial_r', 'sunab', 'did2s'):
        if interval_type not in (None, 'pointwise'):
            raise ValueError('the selected fitted-model confint interface supplies pointwise intervals')
        if level is not None:
            required_native_options['confidence_level'] = level
    # Keep the supplied options intact and expose target-implied changes as a
    # reviewable proposal. Selection never amends or executes the adopted fit.
    selected_options = deepcopy(forward_options)
    if method == 'consumption_saving':
        if 'consumer_options' in selected_options:
            if set(selected_options) != {'consumer_options'}:
                raise ValueError('HARK selection options must contain the native consumer_options object')
        else:
            selected_options = {'consumer_options':deepcopy(forward_options or adopted_spec.get('consumer_options',{}))}
        if not isinstance(selected_options['consumer_options'],dict):
            raise ValueError('consumer_options must be an object of native HARK arguments')
    option_changes = []
    if method == 'grf':
        for argument in ('clusters', 'sample.weights'):
            if 'columns.' + argument in required_native_options and argument in selected_options.get('args', {}):
                previous = selected_options['args'].pop(argument)
                option_changes.append({'field':'options.args.' + argument,'supplied':previous,'selected':None})
    if method in ('fixest_ols', 'fixest_ppml', 'sunab') and cluster_columns is not None:
        # fixest accepts one covariance specification. The vcov formula binds
        # the adopted clusters without also passing its legacy cluster option.
        for container in ('args', 'columns'):
            if 'cluster' in selected_options.get(container, {}):
                previous = selected_options[container].pop('cluster')
                option_changes.append({'field':f'options.{container}.cluster','supplied':previous,'selected':None})
    if method in ('ols_r','fixest_ols','fixest_ppml','negative_binomial_r','sunab','did2s','grf','staggered_did','did_multiplegt_dyn','nonabs_did','iv_ar','iv_ar_robust','rdrobust_r','hdfe','dml_irm','dml_pliv','dml_iivm','finite_horizon_choice','consumption_saving','stochastic_rbc','dolo_yaml','replacement'):
        for field, value in required_native_options.items():
            cursor = selected_options
            path = field.split('.', 1)
            if len(path) == 2:
                if not isinstance(cursor.get(path[0], {}), dict):
                    raise ValueError(f'options.{path[0]} must be an object')
                cursor = cursor.setdefault(path[0], {})
            key = path[-1]
            defaults = {'panel':True,'aggregation.type':'dynamic','aggregation':'period',
                        'aggregation.target.sample':'all','args.normalized':False,
                        'args.CI':True,'args.alpha':.05,'args.level':95,'alpha':.05,'confidence_level':.95,
                        'alp':.05,'aggregation.alp':forward_options.get('alp',.05),
                        'cband':False,'aggregation.cband':forward_options.get('cband',False),
                        'bstrap':False,'aggregation.bstrap':forward_options.get('bstrap',False),
                        'score':'ATE' if method == 'dml_irm' else 'LATE' if method == 'dml_iivm' else 'partialling out',
                        'return_scalar':True,'vFuncBool':False,'details':True,
                        'vcov':{'CRV1':cluster_columns[0]} if method == 'hdfe' and cluster_columns else 'hetero'}
            supplied = cursor.get(key, defaults.get(field))
            if supplied != value:
                option_changes.append({'field':('' if method=='consumption_saving' else 'options.')+field,
                    'supplied':supplied,'selected':value})
            cursor[key] = value
    unbound_inputs = []
    if method == 'grf':
        has_weights = (selected_options.get('columns', {}).get('sample.weights') is not None or
            selected_options.get('args', {}).get('sample.weights') is not None)
        if proposed_contract.get('weights') is not None and not has_weights:
            unbound_inputs.append('weights: analysis column, options.columns.sample.weights or options.args.sample.weights')
        if has_weights and selected_options.get('args', {}).get('equalize.cluster.weights') is True:
            raise ValueError('GRF sample.weights requires equalize.cluster.weights=false')
    if method in DML_METHODS:
        for field in ('n_folds','seed','learners'):
            if field not in selected_options:
                unbound_inputs.append('options.'+field)
        if method == 'dml_irm' and not selected_options.get('treatment'):
            unbound_inputs.append('options.treatment: binary treatment column')
        if selected_options.get('joint') and not selected_options.get('bootstrap'):
            unbound_inputs.append('options.bootstrap: method and n_rep_boot for joint intervals')
    if request['dependence'] in ('cluster', 'clustered'):
        if method in DML_METHODS and not cluster_columns:
            unbound_inputs.append('inference.cluster/clusters: independent cluster columns')
        elif method == 'hdfe' and not cluster_columns:
            unbound_inputs.append('inference.cluster: one independent cluster column')
        elif method == 'staggered_did' and not selected_options.get('clustervars'):
            unbound_inputs.append('inference.cluster/clusters or options.clustervars')
        elif method == 'iv_ar_robust' and not selected_options.get('args', {}).get('cl'):
            unbound_inputs.append('inference.cluster/clusters or options.args.cl')
        elif method == 'rdrobust_r' and not (selected_options.get('columns', {}).get('cluster') or
                selected_options.get('args', {}).get('cluster') is not None):
            unbound_inputs.append('inference.cluster or options.columns.cluster')
        elif method == 'grf' and not (selected_options.get('columns', {}).get('clusters') or
                selected_options.get('args', {}).get('clusters') is not None):
            unbound_inputs.append('inference.cluster, options.columns.clusters or options.args.clusters')
        elif method in ('fixest_ols', 'fixest_ppml', 'sunab') and cluster_columns is None:
            native = selected_options.get('args', {})
            vcov = native.get('vcov')
            if not (native.get('cluster') or selected_options.get('columns', {}).get('cluster') or
                    isinstance(vcov, str) and '~' in vcov):
                unbound_inputs.append('inference.cluster/clusters or an explicit native cluster binding')
    if method == 'rdrobust_r' and facts.get('discontinuity') == 'fuzzy' and not (
            selected_options.get('columns', {}).get('fuzzy') or selected_options.get('args', {}).get('fuzzy') is not None):
        unbound_inputs.append('options.columns.fuzzy: actual treatment-receipt column')
    if external_implementation:
        engine = external_implementation['function']
    elif native_function:
        engine = native_function
    elif method == 'consumption_saving':
        engine = function
    elif method in R_METHODS:
        package, function = R_METHODS[method]; engine = f'{package}::{function}'
    else:
        engine = {'staggered_did':'did::att_gt + did::aggte','dml_plr':'doubleml.DoubleMLPLR',
                  'dml_did':'doubleml.did.DoubleMLDID','blp':'pyblp.Problem.solve',
                  'dml_irm':'doubleml.DoubleMLIRM','dml_pliv':'doubleml.DoubleMLPLIV','dml_iivm':'doubleml.DoubleMLIIVM',
                  'iv_gmm':'linearmodels.iv.IVGMM',
                  'iv_ar_robust':'ivDiag::AR_test',
                  'fixes_att':'fixes::att',
                  'iv_ar':'linearmodels.iv.IV2SLS + statsmodels.OLS + scipy.stats.f',
                  'synthetic_control':'pysyncon.Synth + statsmodels.OLS',
                  'generalized_synth':'gsynth::gsynth',
                  'causal_forest':'econml.dml.CausalForestDML',
                  'policy_tree':'econml.policy.DRPolicyTree + statsmodels.OLS',
                  'rct':'scipy.stats.permutation_test + statsmodels.OLS',
                  'hdfe':'pyfixest.feols',
                  'finite_horizon_growth':'scipy.optimize.minimize/SLSQP',
                  'aiyagari':'quantecon.markov.DiscreteDP.solve + scipy.optimize.brentq',
                  'stochastic_rbc':'statsmodels.tsa.arima.model.ARIMA + research_dsge.solve',
                  'correlated_equilibrium':'research_numerics.correlated_equilibrium + scipy.optimize.linprog',
                  'tu_shapley_core':'research_numerics.tu_shapley_core',
                  'interbank_clearing':'research_numerics.clearing_payments',
                  'multitask_incentives':'research_numerics.multitask_incentives',
                  'state_price_bounds':'research_numerics.state_price_bounds + scipy.optimize.linprog',
                  'binary_logit':'research_numerics.moment_map + research_numerics.moment_jacobian',
                  'finite_policy_sir':'research_numerics.finite_policy_sir + scipy.integrate.solve_ivp',
                  'queue_capacity':'research_numerics.queue_capacity','decision_rights':'research_numerics.decision_rights',
                  'cournot':'equity_io.cournot',
                  'bargaining':'research_markets.bargain','dynamic_game':'equity_io.dynamic_game'}.get(method)
        if engine is None:
            engine = 'research_dynamic.observed_run' if owner.startswith('skills/econ-data/scripts/research_dynamic.py') else 'research_markets.'+method
    changes = []
    if adopted and adopted != method:
        changes.append({'field':'method','adopted':adopted,'selected':method})
    for key in ('estimand','identification','data','id','outcome','regressors','endogenous','instruments'):
        if key == 'identification' and method == 'cournot' and isinstance(adopted_spec.get(key),dict):
            # The equity owner consumes its structured identification object;
            # the selector's required prose describes that unchanged object.
            continue
        if key in adopted_spec and key in request and adopted_spec[key] != request[key]:
            changes.append({'field':key,'adopted':adopted_spec[key],'selected':request[key]})
    for key in contract_fields:
        if key in adopted_contract and proposed_contract.get(key) != adopted_contract[key]:
            changes.append({'field':key,'adopted':adopted_contract[key],'selected':proposed_contract.get(key)})
    if method == 'consumption_saving' and adopted_spec:
        if selected_options['consumer_options'] != adopted_spec.get('consumer_options',{}):
            changes.append({'field':'consumer_options','adopted':adopted_spec.get('consumer_options',{}),
                'selected':selected_options['consumer_options']})
        if 'income_process' in adopted_spec and adopted_spec['income_process'] != income_process:
            changes.append({'field':'income_process','adopted':adopted_spec['income_process'],'selected':income_process})
    elif adopted_spec and (forward_options != adopted_spec.get('options', {}) or option_changes):
        changes.append({'field':'options','adopted':adopted_spec.get('options', {}),'selected':selected_options})
    relation = {'adopted_estimand':adopted_spec.get('estimand'),
                'requested_estimand':request['estimand'],'selected_method_quantity':method_quantity}
    if 'target' in adopted_spec and target and adopted_spec['target'] != target:
        relation['target_change'] = {'adopted':adopted_spec['target'],'selected':target}
    inherited_inference = proposed_contract.get('inference', {})
    if not isinstance(inherited_inference, dict):
        inherited_inference = {}
    inference_contract = {'dependence':request['dependence'],
        'unit':proposed_contract.get('inference_unit',proposed_contract.get('assignment_unit',proposed_contract.get('observation_unit'))),
        'assignment_unit':proposed_contract.get('assignment_unit'),
        'specification':proposed_contract.get('inference'),
        'interval_type':comparison.get('interval_type',comparison.get('ci_kind',
            inherited_inference.get('interval_type',inherited_inference.get('ci_kind','pointwise')))),
        'confidence_level':level,
        'family':comparison.get('inference_family',comparison.get('family',
            inherited_inference.get('inference_family',inherited_inference.get('family')))),
        'official_output_required':True}
    if method == 'iv_ar_robust':
        inference_contract['confidence_level'] = 1-alpha
    elif method == 'finite_horizon_choice' and not respy_simulation:
        inference_contract['procedure'] = ('adopted moment covariance with simulation contribution' if algorithm == 'smm'
            else 'adopted likelihood curvature or refitted sampling procedure')
        inference_contract['parameter_operation'] = 'estimate structural parameters'
    elif method in ('lifecycle_choice','consumption_saving','finite_horizon_growth','aiyagari','hank_one_asset','stochastic_rbc','dolo_yaml','cournot') or respy_simulation or numerical_kernel is not None:
        inference_contract['procedure'] = ('original Euler/resource residuals at the adopted deterministic numerical tolerance' if method == 'finite_horizon_growth'
            else 'adopted simulation precision and parameter-draw propagation when requested')
        inference_contract['parameter_operation'] = 'hold fixed or previously estimated parameters'
        inference_contract['interval_type'] = comparison.get('interval_type',comparison.get('ci_kind',
            inherited_inference.get('interval_type',inherited_inference.get('ci_kind'))))
        inference_contract['official_output_required'] = False
        if numerical_kernel is not None:
            inference_contract['procedure'] = 'original feasibility, obedience, allocation, clearing or KKT residuals'
            inference_contract['parameter_operation'] = computation['parameter_operation']
            if method == 'state_price_bounds':
                inference_contract['procedure'] = 'original state-price equations, hedge inequalities, primal-dual gaps and replication residual'
            elif method == 'binary_logit':
                inference_contract['procedure'] = 'analytic model quantities and derivatives at the supplied fixed parameters'
            elif method == 'queue_capacity':
                inference_contract['procedure'] = 'stationary M/M/1 utilization, system and queue identities at the supplied rates'
            elif method == 'finite_policy_sir':
                inference_contract['procedure'] = 'population conservation and the adopted integration tolerance'
        if method == 'cournot':
            inference_contract['procedure'] = 'firm best-response residuals and capacity complementarity at the adopted equilibrium tolerance'
            inference_contract['parameter_operation'] = computation['parameter_operation']
        if method in ('aiyagari','hank_one_asset','stochastic_rbc','dolo_yaml'):
            inference_contract['procedure'] = 'original economic-equation residuals and the adopted grid, horizon and integration comparisons'
            inference_contract['parameter_operation'] = computation['parameter_operation']
        if method == 'stochastic_rbc' and native_function is None:
            inference_contract['procedure'] = 'Gaussian AR(1) maximum-likelihood covariance and original RBC equation residuals'
            inference_contract['official_output_required'] = True
    if request['dependence'] in ('cluster', 'clustered'):
        cluster_count = facts.get('cluster_count')
        treated_cluster_count = facts.get('treated_cluster_count')
        for name, count, minimum in (('cluster_count', cluster_count, 2),
                ('treated_cluster_count', treated_cluster_count, 0)):
            if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < minimum):
                raise ValueError(f'conditions.{name} must be an integer >= {minimum}')
        if cluster_count is not None and treated_cluster_count is not None and treated_cluster_count > cluster_count:
            raise ValueError('treated_cluster_count cannot exceed cluster_count')
        inference_contract['cluster_design'] = {
            'columns':cluster_columns, 'independent_unit':inference_contract['unit'],
            'declared_cluster_count':cluster_count, 'declared_treated_cluster_count':treated_cluster_count,
            'common_shocks':facts.get('common_shocks'), 'counts_basis':'declared design; confirm on the fitted sample',
            'required_conditions':['independence across the specified clusters',
                'assignment and common shocks represented by the adopted clustering',
                'cluster size, leverage and treated/control cluster support for the chosen reference distribution']}
        inference_contract['comparisons'] = []
        for candidate, supported, model_class, native, source in (
            ('wild_cluster_bootstrap', method in ('ols_r','fixest_ols','sunab','did2s'),
             'saved lm or linear fixest fit', {'conf_int':True},
             'https://s3alfisc.github.io/fwildclusterboot/reference/boottest.fixest.html'),
            ('club_sandwich', method == 'ols_r', 'saved lm fit with vcovCR.lm support',
             {'vcov':'CR2','test':'Satterthwaite'},
             'https://jepusto.github.io/clubSandwich/reference/coef_test.html')):
            package, function = R_METHODS[candidate]
            inference_contract['comparisons'].append({
                'method':candidate,'function':f'{package}::{function}',
                'entry_point':'skills/econ-data/scripts/research_causal.py run',
                'model_contract':model_class,'compatible_saved_fit':supported,
                'excluded_by':[] if supported else ['the selected result does not provide this supported native linear-model fit'],
                'native_options':native,'source':source,
                'required_inputs':['saved fit and exact analysis-sample cluster vector','coefficient contrast and null',
                    'adopted cluster reference model and bootstrap weights/repetitions when used'],
                'adoption_status':'comparison_preserving_current_inference','executed':False})
    candidate_comparisons = []
    for candidate in alternatives:
        if candidate['method'] == method:
            continue
        fit = candidate['data_fit']
        dimensions = {'data_structures':('data_structure',structure),
                      'treatment_patterns':('treatment_pattern',pattern),
                      'outcome_scales':('outcome_scale',request['outcome_scale']),
                      'dependence':('dependence',request['dependence'])}
        fit['declared'] = {name:value for name,value in dimensions.values()}
        fit['matches_declared_dimensions'] = {
            name:value in fit[allowed] for allowed,(name,value) in dimensions.items() if allowed in fit}
        if 'conditional_distribution' in fit:
            fit['matches_declared_dimensions']['conditional_distribution'] = (
                facts['conditional_distribution'] == fit['conditional_distribution'] if 'conditional_distribution' in facts else None)
        fit['basis'] = 'declared specification'
        fit['data_inspected'] = False
        candidate_targets = compatible.get(candidate['method'])
        candidate['target_comparison'] = {'requested':target or {'expression':request['estimand']},
            'candidate_estimand':candidate['estimand'],
            'supported_kinds':sorted(candidate_targets) if candidate_targets is not None else None,
            'matches_requested_kind':target_kind in candidate_targets if target_kind and candidate_targets is not None else None}
        if candidate['method'] == 'dml_plr' and target_kind == 'ate':
            candidate['target_comparison']['matches_requested_kind'] = (
                facts['effect_heterogeneity'] == 'constant' if 'effect_heterogeneity' in facts else None)
        exclusions = [f'{dimension}={fit["declared"].get(dimension, facts.get(dimension))}'
            for dimension, matches in fit['matches_declared_dimensions'].items() if matches is False]
        if candidate['target_comparison']['matches_requested_kind'] is False:
            exclusions.append(f'target.kind={target_kind} is outside the candidate estimand')
        if candidate['method'] == 'iv_ar' and facts.get('homoskedastic_normal_errors') is False:
            exclusions.append('exact F inversion requires explicit independent homoskedastic normal errors')
        if candidate['method'] == 'synthdid' and facts.get('common_treatment_block') is False:
            exclusions.append('the observed treatment histories do not form a common treated block')
        candidate['eligibility'] = {'status':'incompatible' if exclusions else 'requires_identifying_conditions',
            'excluded_by':exclusions, 'conditions_to_establish':candidate['conditions']}
        candidate['inference']['adopted_dependence'] = request['dependence']
        candidate['inference']['adopted_unit'] = inference_contract['unit']
        candidate['adopted_specification_changes'] = {
            'method':{'adopted':adopted,'candidate':candidate['method'],
                      'change_required':adopted is not None and adopted != candidate['method']},
            'estimand':{'adopted':adopted_spec.get('estimand'),'candidate':candidate['estimand']},
            'identification':{'adopted':adopted_spec.get('identification'),'candidate_conditions':candidate['conditions']},
            'sample_weights_aggregation':{'adopted':{k:adopted_contract[k] for k in ('population','comparison_group','weights','comparison') if k in adopted_contract},
                                          'candidate_requirements':fit['required']},
            'inference':{'adopted':adopted_contract.get('inference'),'candidate_procedure':candidate['inference']['procedure']}}
        if design == 'structural':
            candidate['adopted_specification_changes']['method'] = {
                'adopted':adopted,'candidate':model,'change_required':adopted is not None and adopted != model}
            candidate['adopted_specification_changes']['numerical.estimation_method'] = {
                'adopted':adopted_contract.get('numerical',{}).get('estimation_method'),
                'selected':algorithm,'candidate':candidate['method']}
        candidate_comparisons.append(candidate)
    economic_fields = ('actors','objectives','choices','constraints','information','interactions','equilibrium','welfare')
    if computation is not None and numerical_kernel is None:
        economic_fields = ('actors','objectives','states','choices','constraints','information',
            'transitions','shocks','discount','horizon','terminal_conditions','observed_data',
            'identified_parameters','computation_target','equilibrium','welfare')
        if external_implementation:
            computation['outputs'] = external_implementation['outputs']
    if not required_inputs:
        required_inputs = ['adopted target/population/period','model-specific columns or saved fitted object','matching inference unit and contrast']
    selection = {'selected_method':method,'estimand':method_quantity,'target':target,
        'economic_model':economic_model,'structured_conditions':facts,
        'required_inputs':required_inputs,'assumptions':conditions,'inference':inference_contract,
        'official_implementation':{'function':engine,'entry_point':owner,'options':selected_options,
            'required_options':required_native_options,'execution_mode':'external_official_entry' if external_implementation else 'existing_runner',
            'unbound_inputs':unbound_inputs,
            'external_contract':external_implementation},
        'option_changes':option_changes,
        'reason':{'target':method_quantity,'design':design,'assignment_mechanism':mechanism,
            'data_structure':structure,'treatment_pattern':pattern,'outcome_scale':request['outcome_scale']},
        'alternatives':candidate_comparisons,
        'economic_chain':{'decision':economic_model,'target':target or {'expression':request['estimand']},
            'population_and_observations':proposed_contract,'identification':{'statement':request['identification'],'conditions':facts,'comparison':comparison},
            'estimator':{'method':method,'weights':proposed_contract.get('weights'),'numerical':numerical,'inference':inference_contract},
            'implementation':{'function':engine,'options':selected_options}},
        'model_inputs_to_supply':[k for k in economic_fields if (economic_model or computation is not None) and k not in economic_model],
        'adoption_status':'proposal_retaining_adopted_specification' if changes else 'selected_for_requested_target'}
    if computation is not None:
        selection['computation'] = computation
    if model_contract is not None:
        selection['model_contract'] = model_contract
        selection['knowledge_plan'] = knowledge_plan
        selection['compatibility'] = {'status':'compatible_declared_specification',
            'basis':'existing selector restrictions on the declared model, target, conditions and numerical method',
            'selected_method':method, 'structural_model':model,
            'supported_targets':sorted(accepted_targets), 'requested_target':target_kind,
            'numerical_method':algorithm, 'conditions_to_establish':conditions,
            'data_inspected':False, 'executed':False}
    implementation = selection['official_implementation']
    # Reuse the registered dependency owners; requirements remain their sole
    # version authority and can be passed to the research harness runtime.
    dependency_path = owner.split(' ', 1)[0]
    resource = next((r for rid, r in resources.items() if dependency_path in
        (r['source_path'], placements[rid]['deployment_path'], placements[rid]['export_alias'])), None)
    is_causal_runner = owner == 'skills/econ-data/scripts/research_causal.py run'
    if model_contract is not None:
        if external_implementation:
            called_functions = set(engine.split(' + '))
            matched_bindings = [entry for entry in model_contract['implementation']
                if entry.get('module') and entry['module']+'.'+entry['symbol'] in called_functions]
            matched_functions = {entry['module']+'.'+entry['symbol'] for entry in matched_bindings}
            if matched_functions != called_functions:
                raise ValueError(f'{contract_id} does not bind the selected official functions: {engine}')
        else:
            matched_bindings = [entry for entry in model_contract['implementation']
                if resource and entry.get('resource_id') == resource['resource_id']
                and entry.get('command') == owner.split(' ',1)[1]]
            if not matched_bindings:
                raise ValueError(f'{contract_id} does not bind the selected execution owner: {owner}')
        implementation['model_contract_id'] = contract_id
        implementation['contract_bindings'] = matched_bindings
    if resource and not external_implementation:
        resource_id = resource['resource_id']
        script_path = resource['source_path'] if layout_path == 'source_path' else placements[resource_id][layout_path]
        owner = script_path + ' ' + owner.split(' ', 1)[1]
        implementation['entry_point'] = owner
    for candidate in inference_contract.get('comparisons', []):
        causal_path = resources['research-causal']['source_path'] if layout_path == 'source_path' else placements['research-causal'][layout_path]
        candidate['entry_point'] = causal_path + ' run'
    implementation['dependencies'] = []
    if resource:
        dependency_ids = resource.get('required_resources', [])
        if method == 'finite_horizon_choice':
            dependency_ids = ['research-respy-dependencies']
        elif method == 'lifecycle_choice':
            dependency_ids = ['research-lifecycle-dependencies']
        elif method == 'dolo_yaml' or method == 'stochastic_rbc' and native_function:
            dependency_ids = ['research-dolo-dependencies']
        elif method in ('hank_one_asset','stochastic_rbc','aiyagari','consumption_saving'):
            dependency_ids = ['research-macro-dependencies']
        for resource_id in dependency_ids:
            dependency = resources[resource_id]
            path = dependency['source_path']
            if Path(path).name.startswith('requirements-'):
                if path.endswith('-r.json') and method not in R_METHODS and method not in ('staggered_did','generalized_synth'):
                    continue
                implementation['dependencies'].append({'resource_id':resource_id,
                    'path':path if layout_path == 'source_path' else placements[resource_id][layout_path]})
    if is_causal_runner and external_implementation is None:
        inputs = {**adopted_spec, **request}
        execution_spec = {key:deepcopy(inputs[key]) for key in RUN_FIELDS if key in inputs}
        execution_spec.update(method=method, options=deepcopy(selected_options))
        if method in DML_METHODS:
            execution_spec['inference'] = ({'type':'cluster','clusters':cluster_columns} if cluster_columns
                else {'type':'official'})
            for field in ('endogenous','instruments'):
                if method == 'dml_irm':
                    execution_spec.setdefault(field, [])
                elif not execution_spec.get(field):
                    unbound_inputs.append(field+': adopted treatment/instrument columns')
        elif method in R_METHODS:
            execution_spec['inference'] = {'type':'official'}
        elif method == 'staggered_did':
            execution_spec['inference'] = {'type':'did'}
        elif method == 'iv_ar':
            execution_spec['inference'] = {'type':'homoskedastic'}
        elif method == 'hdfe':
            if cluster_columns:
                execution_spec['inference'] = {'type':'cluster','cluster':cluster_columns[0]}
            else:
                execution_spec['inference'] = {'type':'cluster' if request['dependence'] in ('cluster','clustered') else 'robust'}
        missing_fields = sorted(RUN_FIELDS - execution_spec.keys())
        implementation['execution_specification'] = {
            'status':'inputs_required' if missing_fields or unbound_inputs else 'specified',
            'specification':execution_spec, 'missing_fields':missing_fields,
            'unbound_inputs':unbound_inputs, 'adoption_required':bool(changes),
            'command':['python',*owner.split(' '),'SPEC.json','--output','RESULT.json']}
    elif resource and external_implementation is None and (resource['resource_id'] in (
            'research-macro', 'research-markets', 'research-dynamic', 'research-macro-extended', 'research-dsge', 'research-numerics')
            or resource['resource_id'] == 'equity-calculator' and method == 'cournot'):
        # Project a matching adopted specification into its existing owner's
        # public input. Numerical validation stays in that owner.
        resource_id = resource['resource_id']
        if resource_id == 'research-numerics':
            owner_fields = required_fields = {'model','inputs','unit'}
        elif resource_id == 'equity-calculator' and method == 'cournot':
            required_fields = {'model','sources','identification','market','as_of','currency','price_unit','quantity_unit',
                'inverse_demand','markets'}
            owner_fields = required_fields | {'observations','counterfactual','equilibrium_tolerance'}
        elif resource_id == 'research-macro':
            owner_fields = {'alpha','beta','delta','initial_capital','terminal_capital','baseline','scenario',
                'population','period','unit','sources','tolerance'}
            required_fields = owner_fields
        elif resource_id == 'research-macro-extended' and method == 'aiyagari':
            owner_fields = required_fields = {'model','calibration_source','parameters','baseline','scenario','solver'}
        elif resource_id == 'research-macro-extended' and method == 'consumption_saving':
            required_fields = {'model','income_process','consumer_options','evaluation','calibration_source'}
            owner_fields = required_fields | {'scenario','simulation'}
        elif resource_id == 'research-macro-extended' and method == 'lifecycle_choice':
            required_fields = {'model','operation','model_definition','parameters','calibration_source'}
            owner_fields = required_fields | {'n_periods','solver','solution_path','saved_solution',
                'simulation','scenario','outcomes','welfare','evaluation','definitions','parameter_status'}
            if computation['requested_operation'] in ('simulate','counterfactual'):
                required_fields |= {'saved_solution','simulation'}
            else:
                required_fields.add('solution_path')
            if computation['requested_operation'] == 'counterfactual':
                required_fields.add('scenario')
        elif resource_id == 'research-dynamic' and method == 'finite_horizon_choice':
            required_fields = {'model', 'operation'}
            owner_fields = required_fields | {'params', 'options', 'adopted', 'data', 'estimation',
                'moments', 'fit_path', 'simulation', 'scenario', 'welfare', 'inference', 'parameter_status'}
            if 'fit_path' not in adopted_spec:
                required_fields |= {'params', 'options', 'adopted'}
            if not respy_simulation:
                required_fields |= {'data', 'estimation'}
                if algorithm == 'smm':
                    required_fields.add('moments')
            elif computation['requested_operation'] == 'counterfactual':
                required_fields.add('scenario')
        elif resource_id == 'research-dsge' and method == 'hank_one_asset':
            required_fields = {'model','operation'}
            owner_fields = required_fields | {'calibration_source','parameters','steady_state','saved_solution',
                'transition','horizon','inputs','shocks','outputs','solver_options','scenario','equilibrium_tolerance'}
            if 'saved_solution' not in adopted_spec:
                required_fields |= {'calibration_source','parameters','steady_state'}
            if computation['requested_operation'] != 'solve_steady_state':
                required_fields.add('horizon')
                required_fields.add('inputs' if ssj_operation == 'solve_jacobian' else 'shocks')
        elif resource_id == 'research-dsge' and native_function:
            required_fields = {'model','operation'}
            owner_fields = required_fields | {'yaml_model','calibration_source','calibration','discretization',
                'solver','validation','saved_solution','options','units','normalization'}
            if 'saved_solution' not in adopted_spec:
                required_fields |= {'yaml_model','calibration_source'}
            if computation['requested_operation'] == 'reuse_solution':
                required_fields.add('saved_solution')
        elif resource_id == 'research-dsge':
            owner_fields = required_fields = {'parameters','observations','horizon','simulation_paths','seed','technology_shock'}
        elif resource_id == 'research-markets':
            owner_fields = required_fields = {'model','baseline','scenario','unit','sources'}
        else:
            required_fields = {'model','options'}
            owner_fields = required_fields | {'data','adopted','scenario'}
            if method in ('replacement','latent_replacement','discrete_entry','dynamic_adoption_blp'):
                required_fields = required_fields | {'data'}
        execution_spec = {key:deepcopy(adopted_spec[key]) for key in owner_fields if key in adopted_spec}
        if resource_id != 'research-macro' and (resource_id != 'research-dsge' or native_function):
            execution_spec['model'] = model
        if method in ('lifecycle_choice','hank_one_asset','dolo_yaml') or method == 'stochastic_rbc' and native_function:
            execution_spec['operation'] = computation['requested_operation']
        if method == 'stochastic_rbc' and native_function:
            execution_spec.setdefault('options', {})['algorithm'] = 'dolo_time_iteration'
        if method == 'lifecycle_choice' and 'parameter_status' in facts:
            if execution_spec.get('parameter_status', facts['parameter_status']) != facts['parameter_status']:
                raise ValueError('lifecycle parameter_status must agree with the adopted specification')
            execution_spec['parameter_status'] = facts['parameter_status']
        if method == 'consumption_saving':
            execution_spec['income_process'] = income_process
            execution_spec['consumer_options'] = deepcopy(selected_options['consumer_options'])
            if computation['requested_operation'] == 'simulate' and 'simulation' not in execution_spec:
                unbound_inputs.append('simulation: adopted AgentCount, T_sim, seed and track_vars')
            if computation['requested_operation'] == 'counterfactual' and 'scenario' not in execution_spec:
                unbound_inputs.append('scenario.consumer_options: adopted changed parameters')
        if method == 'finite_horizon_choice':
            execution_spec['operation'] = computation['requested_operation']
            if respy_simulation:
                execution_spec.setdefault('simulation', {})['method'] = simulation_method
                execution_spec['parameter_status'] = facts['parameter_status']
            else:
                execution_spec.setdefault('estimation', {})['method'] = algorithm
        if resource_id == 'research-dynamic' and method != 'finite_horizon_choice' and 'options' in adopted_spec:
            execution_spec['options'] = deepcopy(selected_options)
            if method == 'replacement' and algorithm == 'smm' and 'smm' not in execution_spec['options']:
                unbound_inputs.append('options.smm: adopted seed, replications, initial_costs, bounds and tolerance')
        missing_fields = sorted(required_fields - execution_spec.keys())
        if method == 'consumption_saving':
            missing_fields.extend('consumer_options.'+key for key in
                ('T_cycle','CRRA','DiscFac','Rfree','LivPrb','PermGroFac','BoroCnstArt')
                if key not in execution_spec['consumer_options'])
            if isinstance(execution_spec.get('evaluation'),dict) and 'mNrm' not in execution_spec['evaluation']:
                missing_fields.append('evaluation.mNrm')
        if resource_id == 'research-numerics' and 'inputs' in execution_spec:
            if not isinstance(execution_spec['inputs'], dict):
                raise ValueError('adopted_specification.inputs must be an object')
            numerical_signature.bind_partial(**execution_spec['inputs'])
            missing_fields.extend('inputs.'+name for name, parameter in numerical_signature.parameters.items()
                if parameter.default is inspect.Parameter.empty and name not in execution_spec['inputs'])
        implementation['execution_specification'] = {
            'status':'inputs_required' if missing_fields or unbound_inputs else 'specified',
            'specification':execution_spec, 'missing_fields':missing_fields,
            'unbound_inputs':unbound_inputs, 'adoption_required':bool(changes),
            'schema_owner':{'resource_id':resource_id, 'entry_point':implementation['entry_point']},
            'validation':'The selected owner validates numerical inputs when its command executes.',
            'command':['python',*owner.split(' '),'SPEC.json','--output','RESULT.json']}
        if method == 'replacement':
            replacement_options = execution_spec.get('options', {})
            implementation['execution_components'] = [replacement_options.get('estimation_method', 'nfxp'),
                'baseline and scenario policy solution']
            if replacement_options.get('replacement_timing', 'reset_to_zero') == 'reset_to_zero':
                implementation['execution_components'] += ['ccp','finite-horizon solution']
            if 'smm' in execution_spec.get('options', {}):
                implementation['execution_components'].append('smm')
    return {'result_format_version':1,'status':'design_change' if changes else 'selected','question':request['question'],
        'estimand':request['estimand'],'identification':request['identification'],
        'method':method,'engine':engine,'entry_point':owner,'determining_conditions':conditions,
        'forward_options':forward_options,'design_contract':proposed_contract,
        'adopted_specification':adopted_spec,'estimand_relation':relation,
        'design_change':{'adopted_method':adopted,'selected_method':method,'changes':changes,'estimand_relation':relation} if changes else None,
        'requested_design':{k:request[k] for k in ('outcome_scale','data_structure','treatment_pattern','dependence')},
        'method_selection':selection,'executed':False}


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
did_version <- packageVersion('did')
if (did_version < '2.5.1') stop('did >= 2.5.1 is required')
updated_aggregation_rules <- did_version >= '2.5.1.906'
s <- fromJSON(args[2], simplifyVector=TRUE); o <- s$options
agg_args <- list(type='dynamic')
if (length(o$aggregation)) for(k in names(o$aggregation)) agg_args[k] <- o$aggregation[k]
if (!updated_aggregation_rules && agg_args$type == 'group' && isTRUE(agg_args$min_e > 0))
  stop('Positive group min_e requires did >= 2.5.1.906; this did version does not apply that aggregation window')
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
agg_args$MP <- a
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
        'ols_r': set(), 'fixest_ols': set(), 'fixest_ppml': set(), 'negative_binomial_r': set(),
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
        'iv_ar_robust': set(),
    }[method]
    optional = {'args','columns','seed','definitions'}
    if method in ('ols_r','fixest_ols','fixest_ppml','negative_binomial_r','sunab','fixes_event_study','iv_ar_robust'): optional.add('fixed_effects')
    if method in ('ols_r','fixest_ols','fixest_ppml','negative_binomial_r'): optional.add('confidence_level')
    if method == 'sunab': optional |= {'sunab','aggregation','never_treated','confidence_level'}
    if method == 'did2s': optional |= {'event_variable','reference_event_time','confidence_level'}
    if method == 'fixes_event_study': optional |= {'never_treated'}
    if method == 'synthdid': optional |= {'confidence_level'}
    if method == 'grf': optional |= {'aggregation','confidence_level'}
    if method == 'rdrobust_r': optional.add('plot')
    if not required <= opt.keys() or set(opt)-required-optional:
        raise ValueError(f'{method} options require {sorted(required)} and accept {sorted(optional)}')
    if spec['inference'] != {'type':'official'}:
        raise ValueError('official R methods require inference={"type":"official"}; specify inference options in options.args')
    if not isinstance(opt.get('args', {}), dict) or not isinstance(opt.get('columns', {}), dict):
        raise ValueError('options.args and options.columns must be objects')
    if not isinstance(opt.get('definitions', {}), dict):
        raise ValueError('options.definitions must contain the adopted comparison and inference definitions')
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
        covariance = source.get('covariance', {})
        if any(t not in covariance or any(u not in covariance[t] or covariance[t][u] is None for u in terms) for t in terms):
            raise ValueError('HonestDiD requires the saved full joint covariance for every ordered pre/post term')
    rcode = r'''
args <- commandArgs(trailingOnly=TRUE)
suppressPackageStartupMessages(library(jsonlite))
s <- fromJSON(args[1], simplifyVector=TRUE); o <- s$options; method <- s$method
pkg <- args[3]; fname <- args[4]
if(!requireNamespace(pkg,quietly=TRUE)) stop(paste('Install the selected official package:',pkg))
if(method=='iv_ar_robust' && packageVersion('ivDiag') < '1.0.8') stop('iv_ar_robust requires ivDiag >= 1.0.8 for whole-line confidence-set inversion')
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
covariance_terms <- NULL; display_metadata <- list(); extra_displays <- list(); plot_options <- NULL
confidence_level <- if(is.null(o$confidence_level)) .95 else o$confidence_level
if(!is.numeric(confidence_level) || length(confidence_level)!=1L || confidence_level<=0 || confidence_level>=1) stop('confidence_level must be between zero and one')
kind <- 'regression'
if(method %in% c('ols_r','fixest_ols','fixest_ppml','negative_binomial_r','sunab')) {
  model_columns <- c(s$outcome,s$regressors,o$fixed_effects)
  if(!all(grepl('^[A-Za-z_][A-Za-z0-9_]*$',model_columns))) stop('Model columns must use simple names')
  rhs <- if(length(s$regressors)) paste(s$regressors,collapse='+') else '1'
  if(method %in% c('ols_r','negative_binomial_r')) {
    if(length(o$fixed_effects)) rhs <- paste(rhs,paste0('factor(',o$fixed_effects,')',collapse='+'),sep='+')
    owned <- list(formula=as.formula(paste(s$outcome,'~',rhs)),data=d)
  } else {
    if(method=='sunab') {
      if(!all(c(o$entity,o$time,o$cohort) %in% names(d))) stop('Missing Sun-Abraham panel columns')
      if(anyDuplicated(d[,c(o$entity,o$time)])) stop('Sun-Abraham requires unique entity-time pairs')
      sa <- if(is.null(o$sunab)) list() else o$sunab
      unknown <- setdiff(names(sa),setdiff(names(formals(getFromNamespace('sunab','fixest'))),c('cohort','period')))
      if(length(unknown)) stop(paste('Unsupported sunab option:',paste(unknown,collapse=', ')))
      if(isTRUE(sa$no_agg)) stop('Use the saved cohort coefficients for no_agg; this branch reports an adopted aggregate')
      if(isTRUE(sa$att) && !identical(o$aggregation,'att')) stop('sunab att=TRUE requires aggregation=att')
      never <- if(is.null(o$never_treated)) 0 else o$never_treated
      d[[o$cohort]][d[[o$cohort]]==never] <- max(d[[o$time]],na.rm=TRUE)+1
      sa_call <- as.call(c(list(as.name('sunab'),as.name(o$cohort),as.name(o$time)),sa))
      rhs <- paste(paste(deparse(sa_call,width.cutoff=500),collapse=''),rhs,sep='+')
      if(is.null(o$fixed_effects)) o$fixed_effects <- c(o$entity,o$time)
      diagnostics$cohort_coding <- list(input_never_treated=never,engine_never_treated=max(d[[o$time]],na.rm=TRUE)+1)
      display_metadata$reference_event_time <- if(is.null(sa$ref.p)) -1 else sa$ref.p
      display_metadata$reference_cohort <- sa$ref.c
      display_metadata$aggregation <- if(is.null(o$aggregation)) 'period' else o$aggregation
      kind <- 'event-study'
    }
    fml <- paste(s$outcome,'~',rhs)
    if(length(o$fixed_effects)) fml <- paste(fml,'|',paste(o$fixed_effects,collapse='+'))
    owned <- list(fml=as.formula(fml,env=asNamespace('fixest')),data=d,data.save=TRUE)
    for(k in intersect(c('vcov','weights','offset','cluster','panel.id'),names(call_args))) {
      if(is.character(call_args[[k]]) && length(call_args[[k]])==1L && startsWith(call_args[[k]],'~')) call_args[[k]] <- as.formula(call_args[[k]])
    }
    if(is.list(call_args$ssc)) call_args$ssc <- invoke(fixest::ssc,call_args$ssc)
  }
} else if(method=='did2s') {
  owned <- list(data=d,yname=s$outcome,treatment=o$treatment,
    first_stage=as.formula(o$first_stage),second_stage=as.formula(o$second_stage),cluster_var=o$cluster_var)
  if(isTRUE(call_args$return_bootstrap)) stop('Native bootstrap draws are retained by the package; return_bootstrap must be FALSE for the fixest result contract')
  display_metadata$reference_event_time <- o$reference_event_time
  display_metadata$event_variable <- o$event_variable
  display_metadata$inference_unit <- o$cluster_var
  kind <- if(is.null(o$event_variable)) 'regression' else 'event-study'
} else if(method=='did_imputation') {
  owned <- list(data=d,yname=s$outcome,gname=o$cohort,tname=o$time,idname=o$entity)
  if(!is.null(call_args$first_stage)) call_args$first_stage <- as.formula(call_args$first_stage)
  if(length(s$regressors) && is.null(call_args$first_stage)) owned$first_stage <- as.formula(paste('~',paste(s$regressors,collapse='+'),'|',o$entity,'+',o$time))
  display_metadata$base_period <- 'untreated outcome model; pretrend regression uses omitted pretreatment event times'
  display_metadata$inference_unit <- if(is.null(call_args$cluster_var)) o$entity else call_args$cluster_var
  kind <- 'event-study'
} else if(method=='fixes_event_study') {
  never <- if(is.null(o$never_treated)) 0 else o$never_treated
  d[[o$cohort]][!is.na(d[[o$cohort]]) & d[[o$cohort]]==never] <- NA
  diagnostics$cohort_coding <- list(input_never_treated=never,engine_never_treated='NA')
  fe <- if(is.null(o$fixed_effects)) c(o$entity,o$time) else o$fixed_effects
  o$fixed_effects <- fe
  rhs <- if(length(s$regressors)) paste(s$regressors,collapse='+') else '1'
  fml <- paste(s$outcome,'~',rhs)
  if(length(fe)) fml <- paste(fml,'|',paste(fe,collapse='+'))
  owned <- list(formula=as.formula(fml),data=d,time=o$time,timing=o$cohort,unit=o$entity,estimator=o$estimator)
  if(!is.null(call_args$cluster) && startsWith(call_args$cluster,'~')) call_args$cluster <- as.formula(call_args$cluster)
  if(is.null(call_args$conf_level)) call_args$conf_level <- confidence_level
  if(length(call_args$conf_level)!=1L) stop('Save one adopted confidence level per result')
  kind <- 'event-study'
} else if(method=='nonabs_did') {
  owned <- list(data=d,outcome=s$outcome,treatment=o$treatment,unit=o$entity,time=o$time,method=o$estimator,controls=s$regressors)
  if(is.null(call_args$conf.level)) call_args$conf.level <- confidence_level
  if(o$estimator=='DCDH') {
    if(isTRUE(call_args$graph_off)) stop('nonabsdid DCDH extraction requires the official plot data')
    if(is.null(call_args$ci_level)) call_args$ci_level <- 100*call_args$conf.level
    if(call_args$ci_level != 100*call_args$conf.level) stop('DCDH ci_level must match conf.level')
  }
  kind <- 'event-study'
} else if(method=='synthdid') {
  if(length(s$regressors)) stop('The long-panel synthdid contract supplies outcomes; its X tensor requires the direct official matrix interface')
  setup <- synthdid::panel.matrices(d,unit=o$entity,time=o$time,outcome=s$outcome,treatment=o$treatment)
  owned <- list(Y=setup$Y,N0=setup$N0,T0=setup$T0)
  diagnostics$panel <- list(units=rownames(setup$Y),periods=colnames(setup$Y),control_units=rownames(setup$Y)[seq_len(setup$N0)],pre_periods=colnames(setup$Y)[seq_len(setup$T0)])
  display_metadata$treatment_time <- colnames(setup$Y)[setup$T0+1L]
  display_metadata$aggregation <- 'uniform treated unit-time block'
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
  if(is.character(call_args$clusters)) call_args$clusters <- factor(call_args$clusters)
  owned <- list(X=as.matrix(d[,s$regressors,drop=FALSE]),Y=d[[s$outcome]],W=d[[o$treatment]])
  kind <- 'heterogeneity'
} else if(method=='iv_ar_robust') {
  model_columns <- unique(c(s$outcome,s$endogenous,s$instruments,s$regressors,o$fixed_effects,call_args$cl,call_args$weights))
  if(!all(model_columns %in% names(d))) stop('Missing adopted IV outcome, treatment, instrument, control, effect, cluster or weight columns')
  if(length(intersect(c(s$outcome,s$endogenous),c(s$instruments,s$regressors)))) stop('IV outcome and endogenous treatment must be distinct from instruments and controls')
  if(length(intersect(s$instruments,s$regressors))) stop('Excluded instruments must be distinct from exogenous controls')
  keep <- complete.cases(d[,model_columns,drop=FALSE])
  diagnostics$excluded_missing_ids <- I(ids[!keep])
  diagnostics$input_rows <- length(ids)
  d <- d[keep,,drop=FALSE]; ids <- ids[keep]
  if(!nrow(d)) stop('The adopted IV sample contains no complete observations')
  owned <- list(data=d,Y=s$outcome,D=s$endogenous[[1]],Z=s$instruments,controls=s$regressors,FE=o$fixed_effects)
  if(is.null(call_args$CI)) call_args$CI <- TRUE
  if(is.null(call_args$alpha)) call_args$alpha <- .05
  if(is.null(call_args$prec)) call_args$prec <- 12L
  if(!is.numeric(call_args$alpha) || length(call_args$alpha)!=1L || !is.finite(call_args$alpha) || call_args$alpha<=0 || call_args$alpha>=1) stop('AR alpha must be between zero and one')
  confidence_level <- 1-call_args$alpha
  kind <- 'iv_confidence_set'
  display_metadata$interval_type <- 'Anderson-Rubin test inversion'
  display_metadata$inference_unit <- if(is.null(call_args$cl)) s$id else call_args$cl
  display_metadata$covariance <- if(is.null(call_args$cl)) 'heteroskedastic robust' else 'cluster robust'
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
if(method=='nonabs_did') {
  underlying <- switch(o$estimator,DCDH=list('DIDmultiplegtDYN','did_multiplegt_dyn'),PanelMatch=list('PanelMatch','PanelMatch'),list('fect','fect'))
  if(!requireNamespace(underlying[[1]],quietly=TRUE)) stop(paste('Install selected nonabsdid engine:',underlying[[1]]))
  additional <- names(formals(getExportedValue(underlying[[1]],underlying[[2]])))
}
invisible(capture.output(fit <- invoke(fun,all_args,additional)))
if(method %in% c('ols_r','fixest_ols','fixest_ppml','negative_binomial_r','sunab','did2s')) {
  if(inherits(fit,'fixest_multi')) stop('This result contract requires one fitted model')
  if(method=='sunab') {
    diagnostics$cohort_coefficients <- coef(fit,agg=FALSE)
    diagnostics$cohort_covariance <- vcov(fit)
    diagnostics$cohort_covariance_terms <- rownames(vcov(fit))
    fit <- summary(fit,agg=if(is.null(o$aggregation)) 'period' else o$aggregation)
  }
  table <- if(method %in% c('ols_r','negative_binomial_r')) coef(summary(fit)) else fixest::coeftable(fit)
  intervals <- confint(fit,level=confidence_level)
  if(method!='sunab') covariance <- vcov(fit)
  estimates <- data.frame(term=rownames(table),estimate=table[,1],se=table[,2],p_value=table[,4],ci_low=intervals[,1],ci_high=intervals[,2],row.names=NULL)
  used <- if(method %in% c('ols_r','negative_binomial_r')) as.integer(rownames(model.frame(fit))) else fixest::obs(fit)
  if(method=='did2s' && length(used)!=nrow(d)) stop('did2s changed the sample; supply the adopted complete estimation sample and rerun')
  ids <- ids[used]; d <- d[used,,drop=FALSE]
  diagnostics$observations <- nobs(fit); diagnostics$fixed_effects <- o$fixed_effects
  if(inherits(fit,'fixest')) diagnostics$n_clusters <- attr(fit$cov.scaled,'G')
  if(method=='negative_binomial_r') diagnostics$dispersion <- list(theta=fit$theta,theta_se=fit$SE.theta,variance='mu + mu^2/theta')
  if(method %in% c('sunab','did2s') && kind=='event-study') {
    event_terms <- if(method=='sunab') startsWith(estimates$term,paste0(o$time,'::')) else startsWith(estimates$term,paste0(o$event_variable,'::'))
    estimates$event_time <- suppressWarnings(as.numeric(sub('.*::','',estimates$term)))
    estimates$role <- ifelse(!event_terms,'adjustment',ifelse(estimates$event_time<0,'pre_diagnostic','att'))
  }
} else if(method=='did_imputation') {
  estimates <- data.frame(term=as.character(fit$term),estimate=fit$estimate,se=fit$std.error,
    ci_low=fit$conf.low,ci_high=fit$conf.high,event_time=suppressWarnings(as.numeric(fit$term)))
  estimates$role <- ifelse(is.na(estimates$event_time),'att',ifelse(estimates$event_time<0,'pre_diagnostic','att'))
  if(all(is.na(estimates$event_time))) kind <- 'regression'
  diagnostics$sample_mapping <- 'official did_imputation returns an aggregate table; fitted row identities are not exported'
  diagnostics$input_ids <- ids; ids <- character()
  diagnostics$observations <- NULL
} else if(method=='fixes_event_study') {
  confidence_level <- call_args$conf_level
  suffix <- sprintf('%.0f',100*confidence_level)
  estimates <- data.frame(term=as.character(fit$term),estimate=fit$estimate,se=fit$std.error,
    event_time=fit$relative_time,ci_low=fit[[paste0('conf_low_',suffix)]],ci_high=fit[[paste0('conf_high_',suffix)]])
  if('p.value' %in% names(fit)) estimates$p_value <- fit$p.value
  estimates$role <- ifelse(fit$is_baseline,'reference',ifelse(fit$relative_time<0,'pre_diagnostic','att'))
  covariance <- attr(fit,'es_vcov')
  if(!is.null(covariance)) covariance_terms <- rownames(covariance)
  diagnostics$official_attributes <- attributes(fit)[setdiff(names(attributes(fit)),c('class','row.names','names','call'))]
  diagnostics$observations <- attr(fit,'N')
  diagnostics$sample_mapping <- 'fixes aggregate result exports sample counts and estimator metadata; row identities are retained in native fit when supplied'
  diagnostics$input_ids <- ids; ids <- character()
  display_metadata$reference_event_time <- attr(fit,'baseline')
  display_metadata$aggregation <- list(estimator=o$estimator,control_group=attr(fit,'cs_control_group'))
  if(all(c('conf_low_sim','conf_high_sim') %in% names(fit))) {
    simultaneous <- estimates
    simultaneous$ci_low <- fit$conf_low_sim; simultaneous$ci_high <- fit$conf_high_sim
    extra_displays$simultaneous <- list(kind='event-study',rows=simultaneous,metadata=list(interval_type='simultaneous',confidence_level=1-attr(fit,'boot_alpha')))
  }
} else if(method=='nonabs_did') {
  tab <- fit$tidy
  estimates <- data.frame(term=as.character(tab$time),estimate=tab$estimate,se=tab$std.error,
    event_time=tab$time,ci_low=tab$conf.low,ci_high=tab$conf.high)
  estimates$role <- ifelse(tab$time<0,'pre_diagnostic','att')
  if(o$estimator=='DCDH') estimates$role[tab$time == -1] <- 'reference'
  confidence_level <- call_args$conf.level
  diagnostics$observations <- NULL
  diagnostics$sample_mapping <- 'native nonabsdid fit retains its engine sample; aggregate tibble does not export row identities'
  diagnostics$input_ids <- ids; ids <- character()
  display_metadata$reference_event_time <- if(o$estimator=='DCDH') -1 else NULL
  display_metadata$aggregation <- list(engine=o$estimator,method='native estimator aggregation')
  display_metadata$event_time_convention <- if(o$estimator=='DCDH') 'native DIDmultiplegtDYN Time minus one' else 'native engine event time'
  if(o$estimator=='DCDH') {
    diagnostics$official_covariance <- fit$fit$coef$vcov
    if(is.null(call_args$bootstrap) && !is.null(fit$fit$coef$vcov)) {
      covariance <- fit$fit$coef$vcov
      native_terms <- rownames(covariance)
      covariance_terms <- vapply(native_terms,function(x) {
        if(startsWith(x,'Effect_')) as.character(as.integer(sub('Effect_','',x))-1L)
        else if(startsWith(x,'Placebo_')) as.character(-as.integer(sub('Placebo_','',x))-1L)
        else stop('Unsupported native DCDH covariance term')
      },character(1))
    }
  }
} else if(method=='synthdid') {
  variance_fun <- getS3method('vcov','synthdid_estimate',envir=asNamespace('synthdid'))
  covariance <- invoke(variance_fun,c(list(object=fit),o$variance))
  dimnames(covariance) <- list('ATT','ATT')
  estimates <- data.frame(term='ATT',estimate=as.numeric(fit),se=sqrt(covariance[1,1]))
  diagnostics$weights <- attr(fit,'weights'); diagnostics$effective_options <- attr(fit,'opts')
  diagnostics$effect_curve <- synthdid::synthdid_effect_curve(fit)
  diagnostics$observations <- nrow(d)
  diagnostics$inference_function <- 'synthdid::vcov.synthdid_estimate'
  display_metadata$interval_type <- 'variance_only'
} else if(method %in% c('drdid_panel','drdid_rc')) {
  estimates <- data.frame(term='ATT',estimate=fit$ATT,se=fit$se,p_value=2*pnorm(-abs(fit$ATT/fit$se)),ci_low=fit$lci,ci_high=fit$uci)
  covariance <- matrix(fit$se^2,1,1,dimnames=list('ATT','ATT'))
  diagnostics$influence_function <- fit$att.inf.func
  diagnostics$effective_options <- fit$argu
  diagnostics$observations <- length(all_args$D)
  diagnostics$sampling_weights <- if(is.null(all_args$i.weights)) rep(1,length(all_args$D)) else all_args$i.weights/mean(all_args$i.weights)
} else if(method=='grf') {
  aggregate_args <- utils::modifyList(list(target.sample='all',method='AIPW'),if(is.null(o$aggregation)) list() else o$aggregation)
  aggregate_args$target.sample <- match.arg(aggregate_args$target.sample,c('all','treated','control','overlap'))
  aggregate_args$method <- match.arg(aggregate_args$method,c('AIPW','TMLE'))
  ate <- invoke(grf::average_treatment_effect,c(list(forest=fit),aggregate_args))
  predictions <- predict(fit,estimate.variance=TRUE)
  critical_value <- qnorm((1+confidence_level)/2)
  estimates <- data.frame(term='target_ate',estimate=ate[1],se=ate[2],p_value=2*pnorm(-abs(ate[1]/ate[2])),ci_low=ate[1]-critical_value*ate[2],ci_high=ate[1]+critical_value*ate[2])
  covariance <- matrix(ate[2]^2,1,1,dimnames=list('target_ate','target_ate'))
  diagnostics$cate <- data.frame(id=ids,estimate=predictions$predictions,variance=predictions$variance.estimates)
  aggregate_rows <- getFromNamespace('validate_subset','grf')(fit,aggregate_args$subset)
  target_rows <- switch(aggregate_args$target.sample,
    treated=aggregate_rows[fit$W.orig[aggregate_rows]==1],
    control=aggregate_rows[fit$W.orig[aggregate_rows]==0],aggregate_rows)
  diagnostics$observations <- nrow(fit$X.orig)
  diagnostics$n_clusters <- if(length(fit$clusters)) length(unique(fit$clusters)) else NULL
  diagnostics$aggregation <- list(arguments=aggregate_args,subset_ids=I(ids[aggregate_rows]),
    target_ids=I(ids[target_rows]),observation_weights=I(getFromNamespace('observation_weights','grf')(fit)),
    weights_ids_ref='sample.included_ids',weights_definition='normalized observation weights before target.sample and score-specific weighting')
  diagnostics$effective_options <- list(equalize.cluster.weights=fit$equalize.cluster.weights,
    seed=fit$seed,num.threads=fit$num.threads,tunable.params=fit$tunable.params)
  display_metadata$aggregation <- aggregate_args
  display_metadata$aggregation_target <- aggregate_args$target.sample
  display_metadata$inference_unit <- if(!is.null(o$definitions$inference_unit)) o$definitions$inference_unit else if(!is.null(o$columns$clusters)) o$columns$clusters else if(length(fit$clusters)) 'native cluster partition' else s$id
  display_metadata$cluster_columns <- o$columns$clusters
  display_metadata$equalize_cluster_weights <- fit$equalize.cluster.weights
  display_metadata$inference_function <- 'grf::average_treatment_effect'
  display_metadata$reference_distribution <- 'standard_normal'
  display_metadata$critical_value <- critical_value
} else if(method=='honest_did') {
  rows <- as.data.frame(fit)
} else if(method=='did_multiplegt_dyn') {
  diagnostics$sample <- fit$save_sample
  diagnostics$normalized_weights <- fit$normalized_weights
  diagnostics$treatment_paths <- fit$design
  diagnostics$effects <- fit$results$Effects
  diagnostics$placebos <- fit$results$Placebos
  if(!is.null(fit$save_sample) && all(c(s$id,'_did_sample') %in% names(fit$save_sample))) ids <- as.character(fit$save_sample[[s$id]][!is.na(fit$save_sample[['_did_sample']])])
  parts <- if(!is.null(fit$results)) list(overall=fit) else fit[startsWith(names(fit),'by_level_')]
  if(!length(parts)) stop('The official treatment-path result contains no saved effect groups')
  tables <- lapply(names(parts),function(group_name) {
    part <- parts[[group_name]]
    effect <- as.data.frame(part$results$Effects,check.names=FALSE)
    if(!all(c('Estimate','SE','LB.CI','UB.CI') %in% names(effect))) stop('Unsupported DIDmultiplegtDYN effect-table interface')
    out <- data.frame(term=paste0(group_name,':Effect_',seq_len(nrow(effect))),
      estimate=effect$Estimate,se=effect$SE,ci_low=effect$LB.CI,ci_high=effect$UB.CI,
      event_time=seq_len(nrow(effect))-1L,role='att',group=group_name)
    if('Switchers' %in% names(effect)) out$population_count <- effect$Switchers
    placebo <- as.data.frame(part$results$Placebos,check.names=FALSE)
    if(nrow(placebo)) {
      pre <- data.frame(term=paste0(group_name,':Placebo_',seq_len(nrow(placebo))),
        estimate=placebo$Estimate,se=placebo$SE,ci_low=placebo$LB.CI,ci_high=placebo$UB.CI,
        event_time=-seq_len(nrow(placebo))-1L,role='pre_diagnostic',group=group_name)
      if('population_count' %in% names(out)) pre$population_count <- placebo$Switchers
      out <- rbind(pre,out)
    }
    out
  })
  estimates <- do.call(rbind,tables)
  if(length(parts)==1L && is.null(call_args$bootstrap)) {
    covariance <- parts[[1]]$coef$vcov
    covariance_terms <- paste0(names(parts)[1],':',rownames(covariance))
  }
  diagnostics$official_covariance <- lapply(parts,function(x) x$coef$vcov)
  diagnostics$covariance_kind <- 'official analytical covariance; bootstrap standard errors retained in effect tables'
  diagnostics$observations <- length(ids)
  confidence_level <- if(is.null(call_args$ci_level)) .95 else call_args$ci_level/100
  display_metadata$reference_event_time <- -1
  display_metadata$event_time_convention <- 'native horizon minus one; first treatment change is event time zero'
  display_metadata$aggregation <- list(normalized=isTRUE(call_args$normalized),same_switchers=isTRUE(call_args$same_switchers),
    same_switchers_pl=isTRUE(call_args$same_switchers_pl),only_never_switchers=isTRUE(call_args$only_never_switchers))
} else if(method=='rdrobust_r') {
  estimates <- data.frame(term='treatment_effect',estimate=fit$coef['Robust',1],se=fit$se['Robust',1],p_value=fit$pv['Robust',1],ci_low=fit$ci['Robust',1],ci_high=fit$ci['Robust',2])
  covariance <- matrix(fit$se['Robust',1]^2,1,1,dimnames=list('treatment_effect','treatment_effect'))
  cutoff <- if(is.null(call_args$c)) 0 else call_args$c
  local <- d[[o$running]] >= cutoff-fit$bws['h',1] & d[[o$running]] <= cutoff+fit$bws['h',2]
  diagnostics <- list(bandwidths=fit$bws,effective_counts=fit$N_h,observations=sum(fit$N),side_counts=fit$N,
    bandwidth_input_ids=I(ids[which(local)]),input_ids=I(ids),input_rows=length(ids),
    sample_mapping='official rdrobust reports post-preprocessing side counts; fitted row identities are not exported')
  if('plot' %in% names(o)) {
    plot_fun <- getExportedValue('rdrobust','rdplot')
    shared <- intersect(names(call_args),c('weights','covs','subset'))
    plot_args <- c(list(y=d[[s$outcome]],x=d[[o$running]],c=cutoff,hide=TRUE),call_args[shared],o$plot)
    invisible(capture.output(plot_fit <- invoke(plot_fun,plot_args)))
    bins <- plot_fit$vars_bins; poly <- plot_fit$vars_poly
    # rdplot returns the left grid followed by the equally sized right grid.
    # Each grid includes the cutoff, so assigning side from x alone loses a curve endpoint.
    nside <- nrow(poly)%/%2L
    if(nrow(poly)%%2L || nside<2L || any(poly$rdplot_x[seq_len(nside)]>plot_fit$c) ||
       any(poly$rdplot_x[nside+seq_len(nside)]<plot_fit$c) ||
       poly$rdplot_x[nside]!=plot_fit$c || poly$rdplot_x[nside+1L]!=plot_fit$c)
      stop('rdplot polynomial output does not preserve the official left/right grid contract')
    bin_rows <- data.frame(component='points',side=ifelse(bins$rdplot_mean_x<plot_fit$c,'left','right'),
      x=bins$rdplot_mean_bin,estimate=bins$rdplot_mean_y,mean_x=bins$rdplot_mean_x,
      bin_low=bins$rdplot_min_bin,bin_high=bins$rdplot_max_bin,n=bins$rdplot_N,
      se=bins$rdplot_se_y,ci_low=bins$rdplot_ci_l,ci_high=bins$rdplot_ci_r)
    line_rows <- data.frame(component='line',side=rep(c('left','right'),each=nside),
      x=poly$rdplot_x,estimate=poly$rdplot_y,mean_x=NA_real_,bin_low=NA_real_,bin_high=NA_real_,
      n=NA_integer_,se=NA_real_,ci_low=NA_real_,ci_high=NA_real_)
    plot_options <- list(args=o$plot,inherited_args=call_args[shared],
      columns=o$columns[intersect(names(o$columns),shared)],c=cutoff,hide=TRUE,
      returned=plot_fit[c('p','c','h','N','N_h','J','binselect','kernel','scale')])
    extra_displays$rdd <- list(kind='rdd',rows=rbind(bin_rows,line_rows),metadata=list(
      estimand='Binned outcome means and left/right polynomial conditional means',effect_estimand=s$estimand,
      running_variable=o$running,cutoff=plot_fit$c,bandwidth=I(plot_fit$h),
      estimation_bandwidth=fit$bws,polynomial_order=plot_fit$p,kernel=plot_fit$kernel,
      binselect=plot_fit$binselect,bin_counts=I(plot_fit$J),side_counts=I(plot_fit$N),
      effective_side_counts=I(plot_fit$N_h),interval_type='pointwise',interval_target='binned means',
      confidence_level=if(is.null(o$plot$ci)) .95 else o$plot$ci/100,
      polynomial_interval_available=FALSE,side_definition='source order: left grid followed by right grid; both include cutoff',
      sample=list(input_rows=length(ids),observations=sum(plot_fit$N),included_ids_available=FALSE),
      sample_policy='official rdplot preprocessing with returned side counts',
      producer=list(`function`='rdrobust::rdplot',version=as.character(packageVersion('rdrobust')),
        signature=names(formals(plot_fun)),function_defaults=lapply(formals(plot_fun),function(x) paste(deparse(x),collapse=' '))),
      effective_options=plot_options))
  }
  ids <- character()
} else if(method=='club_sandwich') {
  rows <- as.data.frame(fit)
} else if(method=='wild_cluster_bootstrap') {
  rows <- data.frame(term=paste(fit$param,collapse='+'),p_value=fit$p_val)
  if(length(fit$conf_int)==2) { rows$ci_low <- fit$conf_int[1]; rows$ci_high <- fit$conf_int[2] }
} else if(method=='iv_ar_robust') {
  stage_args <- c(all_args[intersect(names(all_args),c('data','Y','D','Z','controls','FE','cl','weights','prec'))],
    list(bootstrap=FALSE,run.AR=FALSE,parallel=FALSE))
  stage_fit <- invoke(ivDiag::ivDiag,stage_args)
  if(stage_fit$N != length(ids)) stop('Official IV stages changed the complete-case sample')
  ends <- fit$ci
  empty <- length(ends)==1L && is.na(ends)
  if(empty) {
    rows <- data.frame(term=s$endogenous[[1]],set_type='empty')
    intervals <- list(); set_type <- 'empty'
  } else {
    if(!length(ends) || length(ends)%%2L || anyNA(ends)) stop('Unsupported official AR confidence-set endpoint structure')
    lower <- ends[seq.int(1L,length(ends),by=2L)]
    upper <- ends[seq.int(2L,length(ends),by=2L)]
    rows <- data.frame(term=s$endogenous[[1]],lower=ifelse(is.finite(lower),lower,NA_real_),upper=ifelse(is.finite(upper),upper,NA_real_),
      lower_unbounded=is.infinite(lower),upper_unbounded=is.infinite(upper),set_type='interval')
    intervals <- lapply(seq_along(lower),function(j) list(lower=if(is.finite(lower[j])) lower[j] else NULL,
      upper=if(is.finite(upper[j])) upper[j] else NULL))
    set_type <- if(length(ends)>2L) 'disconnected' else if(all(is.infinite(ends))) 'real_line' else if(any(is.infinite(ends))) 'unbounded' else 'bounded'
  }
  diagnostics$anderson_rubin <- list(confidence_level=confidence_level,intervals=intervals,set_type=set_type,
    null_endpoint='unbounded',null_test=as.list(fit$Fstat),printed_set=fit$ci.print,bounded=fit$bounded)
  diagnostics$observations <- stage_fit$N
  diagnostics$n_clusters <- stage_fit$N_cl
  diagnostics$cluster_columns <- call_args$cl
  diagnostics$cluster_counts <- setNames(lapply(call_args$cl,function(column) length(unique(d[[column]]))),call_args$cl)
  diagnostics$stages <- stage_fit
  diagnostics$first_stage_tests <- as.list(stage_fit$F_stat)
  diagnostics$stage_function <- 'ivDiag::ivDiag'
  diagnostics$stage_arguments <- stage_args[setdiff(names(stage_args),'data')]
  for(stage in c('first_stage','reduced_form','2sls')) {
    tab <- switch(stage,first_stage=stage_fit$est_fs,reduced_form=stage_fit$est_rf,`2sls`=stage_fit$est_2sls)
    names_interval <- if(stage=='2sls') c('CI 2.5%','CI 97.5%') else c('CI.2.5%','CI.97.5%')
    stage_rows <- data.frame(term=if(stage=='2sls') s$endogenous[[1]] else rownames(tab),estimate=tab[,'Coef'],
      se=tab[,'SE'],p_value=tab[,'p.value'],ci_low=tab[,names_interval[1]],ci_high=tab[,names_interval[2]],stage=stage)
    stage_unit <- switch(stage,first_stage=o$definitions$first_stage_unit,reduced_form=o$definitions$reduced_form_unit,`2sls`=s$unit)
    if(is.null(stage_unit)) stage_unit <- paste(if(stage=='first_stage') s$endogenous[[1]] else s$outcome,'per instrument unit')
    extra_displays[[paste0('iv_',stage)]] <- list(kind=switch(stage,first_stage='iv_first_stage',reduced_form='iv_reduced_form',`2sls`='regression'),
      rows=stage_rows,metadata=list(stage=stage,unit=stage_unit,confidence_level=.95,interval_type='conventional Wald',
        estimand=switch(stage,first_stage=paste('First-stage linear-projection coefficients for',s$endogenous[[1]]),
          reduced_form=paste('Reduced-form linear-projection coefficients for',s$outcome),`2sls`=paste('2SLS coefficient on',s$endogenous[[1]])),
        interval_constant=1.96,instruments=I(s$instruments),outcome=if(stage=='first_stage') s$endogenous[[1]] else s$outcome,
        estimator=if(stage=='2sls') '2SLS' else 'OLS',engine='ivDiag::ivDiag',
        producer=list(`function`='ivDiag::ivDiag',version=as.character(packageVersion('ivDiag')),signature=names(formals(ivDiag::ivDiag))),
        effective_options=diagnostics$stage_arguments,
        sample=list(observations=stage_fit$N,included_ids_ref='sample.included_ids'),
        inference_unit=display_metadata$inference_unit,covariance=display_metadata$covariance))
  }
}
if(!is.null(estimates)) rows <- estimates
# Retain the native package result for subsequent official post-estimation.
native_record <- list(fit=fit,data=d,ids=ids)
if(method=='iv_ar_robust') native_record$stages <- stage_fit
native <- serialize(native_record,NULL,version=3)
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
  function_defaults=lapply(formals(fun),function(x) paste(deparse(x),collapse=' ')),
  effective_options=list(args=clean(call_args),columns=o$columns,returned=clean(diagnostics$effective_options),
    formula=if(!is.null(all_args$fml)) paste(deparse(all_args$fml),collapse=' ') else if(!is.null(all_args$formula)) paste(deparse(all_args$formula),collapse=' ') else NULL,
    fixed_effects=o$fixed_effects,aggregation=display_metadata$aggregation,cohort_coding=diagnostics$cohort_coding,plot=plot_options),
  runtime=list(library_paths=I(.libPaths()),working_directory=getwd(),profile_user=Sys.getenv('R_PROFILE_USER',unset=NA_character_)),
  estimates=estimates,covariance=covariance,covariance_terms=if(is.null(covariance_terms)) rownames(covariance) else covariance_terms,diagnostics=clean(diagnostics),
  sample=list(included_ids=I(as.character(ids))),display=list(kind=kind,rows=rows,metadata=display_metadata),displays=extra_displays,
  native_fit=list(format='R-serialize-v3',data=base64_enc(native)))
if(method=='iv_ar_robust') obj$versions$lfe <- as.character(packageVersion('lfe'))
obj$confidence_level <- if(method=='rdrobust_r' && !is.null(call_args$level)) call_args$level/100 else if(method=='wild_cluster_bootstrap' && !is.null(call_args$sign_level)) 1-call_args$sign_level else if(method=='honest_did' && !is.null(call_args$alpha)) 1-call_args$alpha else confidence_level
write_json(obj,args[5],auto_unbox=TRUE,digits=16,na='null',null='null',dataframe='rows')
'''
    with tempfile.TemporaryDirectory(prefix='causal-official-r-') as tmp:
        tmp = Path(tmp); (tmp/'spec.json').write_text(json.dumps(spec),encoding='utf-8')
        proc = subprocess.run(['Rscript','-',str(tmp/'spec.json'),str(path),package,function,str(tmp/'result.json')],
                              input=rcode,text=True,capture_output=True,env=os.environ.copy())
        if proc.returncode: raise ArithmeticError(f'{package} engine failed: ' + proc.stderr[-4000:])
        result = json.loads((tmp/'result.json').read_text())
    result.update(result_format_version=1, method=method, options=opt, adopted={k:spec[k] for k in ('population','period','unit','estimand','identification','assignment','inference')},
        provenance={'data_path':str(path),'data_sha256':_hash(path),'spec_path':str(spec_path.resolve()),'spec_sha256':_hash(spec_path),
                    'producer_path':str(Path(__file__).resolve()),'producer_sha256':_hash(Path(__file__).resolve())})
    result['producer'] = {'entry_point':'research_causal.py run','function':result['engine'],
                          'signature':result['signature'],'versions':result['versions']}
    result['versions']['R'] = result.pop('R')
    result['native_fit']['sha256'] = hashlib.sha256(base64.b64decode(result['native_fit']['data'])).hexdigest()
    result['sample']['id_column'] = spec['id']
    if not result['diagnostics']: result['diagnostics'] = {}
    result['sample']['observations'] = result['diagnostics'].get('observations')
    ids_available = 'sample_mapping' not in result['diagnostics']
    result['sample']['included_ids_available'] = ids_available
    if result['diagnostics'].get('input_ids'):
        result['sample']['input_ids'] = result['diagnostics']['input_ids']
    display_sample = {'id_column':spec['id'],'included_rows':len(result['sample']['included_ids']) if ids_available else None,
                      'observations':result['sample']['observations']}
    native_metadata = result['display'].get('metadata') or {}
    definitions = opt.get('definitions', {})
    fixed_effects = result['effective_options'].get('fixed_effects') or opt.get('fixed_effects',[])
    result['display']['metadata'] = {**definitions,'unit':spec['unit'],'population':spec['population'],'estimand':spec['estimand'],
        'sample':display_sample,'engine':result['engine'],'inference':spec['inference'],
        'n':result['sample']['observations'],'n_clusters':result['diagnostics'].get('n_clusters'),
        'fixed_effects':fixed_effects,'controls':spec['regressors'],
        'period':spec['period'],'weights':{k:v for k,v in {**opt.get('args',{}),**opt.get('columns',{})}.items() if k in ('weights','i.weights','sample.weights','weight')},
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
    result['diagnostics']['engine_messages'] = proc.stderr.strip()
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
    return result

def _doubleml(spec, data, cluster_columns, input_rows):
    """Fit the declared official score on the common complete-case sample."""
    import warnings
    import doubleml
    import sklearn
    from sklearn.ensemble import (RandomForestRegressor, RandomForestClassifier,
                                  HistGradientBoostingRegressor, HistGradientBoostingClassifier)
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LinearRegression, Ridge, Lasso, LogisticRegression

    opt = spec['options']
    method = spec['method']
    if not isinstance(opt.get('definitions',{}),dict):
        raise ValueError('DoubleML definitions must be an object')
    if method == 'dml_iivm' and opt.get('normalize_ipw') and doubleml.__version__ == '0.11.4':
        raise ValueError('DoubleML 0.11.4 normalizes IIVM instrument propensities with treatment d; '
            'normalize_ipw=True requires the official correction e31e61efe8864c160c04488d91f1306e1e25c129 '
            '(normalization with instrument z). Install an official release containing that correction.')
    treatment = opt['treatment'] if method == 'dml_irm' else spec['endogenous'][0]
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
    if method in ('dml_irm','dml_iivm') and set(data[treatment].unique()) != {0,1}:
        raise ValueError('IRM and IIVM require one treatment containing both 0 and 1')
    if method == 'dml_iivm' and set(data[spec['instruments'][0]].unique()) != {0,1}:
        raise ValueError('IIVM requires one instrument containing both 0 and 1')
    valid_scores = {'dml_irm':{'ATE','ATTE'},'dml_pliv':{'partialling out','IV-type'},'dml_iivm':{'LATE'}}
    if opt['score'] not in valid_scores[method]:
        raise ValueError(f'{method} score must be one of {sorted(valid_scores[method])}')
    learner_names = ({'ml_l','ml_m','ml_r'} | ({'ml_g'} if opt['score']=='IV-type' else set())
        if method == 'dml_pliv' else {'ml_g','ml_m'} | ({'ml_r'} if method == 'dml_iivm' else set()))
    if not isinstance(opt['learners'],dict) or set(opt['learners']) != learner_names:
        raise ValueError(f'{method} learners must contain exactly {sorted(learner_names)}')
    classes = {'linear':LinearRegression,'ridge':Ridge,'lasso':Lasso,'logistic':LogisticRegression,
        'random_forest_regressor':RandomForestRegressor,'random_forest_classifier':RandomForestClassifier,
        'hist_gradient_boosting_regressor':HistGradientBoostingRegressor,
        'hist_gradient_boosting_classifier':HistGradientBoostingClassifier}
    learners = {}
    effective_learners = {}
    for name, config in opt['learners'].items():
        if (not isinstance(config,dict) or not {'type'} <= config.keys() or set(config)-{'type','params'}
                or config['type'] not in classes or not isinstance(config.get('params',{}),dict)):
            raise ValueError('each nuisance learner requires a supported type and optional native params')
        cls = classes[config['type']]
        params = deepcopy(config.get('params',{}))
        signature = inspect.signature(cls)
        if 'random_state' in signature.parameters:
            params.setdefault('random_state', opt['seed'])
        if 'n_jobs' in signature.parameters:
            params.setdefault('n_jobs', 1)
        signature.bind(**params)
        learners[name] = cls(**params)
        effective_learners[name] = {'class':cls.__module__+'.'+cls.__name__,
            'params':learners[name].get_params(deep=False)}
    constructor_options = {key:deepcopy(opt[key]) for key in
        ('score','normalize_ipw','trimming_rule','trimming_threshold','subgroups') if key in opt}
    if 'ps_processor_config' in opt:
        from doubleml.utils import PSProcessorConfig
        constructor_options['ps_processor_config'] = PSProcessorConfig(**opt['ps_processor_config'])
    if 'weights' in opt:
        if opt['score'] != 'ATE':
            raise ValueError('DoubleMLIRM constructor weights require score=ATE')
        weights = opt['weights']
        if isinstance(weights,str):
            constructor_options['weights'] = data[weights].to_numpy(dtype=float)
        else:
            arrays = weights if isinstance(weights,dict) else {'weights':weights}
            if set(arrays) not in ({'weights'},{'weights','weights_bar'}):
                raise ValueError('IRM weights use weights and optional weights_bar')
            converted = {}
            for key, values in arrays.items():
                values = np.asarray(values,dtype=float)
                expected = (input_rows,n_rep) if key=='weights_bar' else (input_rows,)
                if values.shape != expected or not np.isfinite(values).all():
                    raise ValueError(f'{key} must be finite with input-row shape {expected}')
                converted[key] = values[data.index.to_numpy()]
            constructor_options['weights'] = converted if isinstance(weights,dict) else converted['weights']
    frame = data.reset_index(drop=True)
    backend = doubleml.DoubleMLData(frame, y_col=spec['outcome'], d_cols=treatment,
        x_cols=spec['regressors'], z_cols=spec['instruments'] or None, cluster_cols=cluster_columns or None)
    cls = getattr(doubleml, DML_METHODS[method])
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
            fit.fit(n_jobs_cv=1, store_predictions=True)
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
        'nuisance_predictions':{key:values.tolist() for key,values in fit.predictions.items()},
        'score_elements':{key:values.tolist() for key,values in fit.psi_elements.items()},
        'array_order':{'nuisance_predictions':['included_id','repetition','treatment'],
            'score_elements':['included_id','repetition','treatment'],'all_coef':['treatment','repetition']},
        'official_interface':{'constructor':str(inspect.signature(cls)),'fit':str(inspect.signature(fit.fit)),
            'confint':str(inspect.signature(fit.confint))}}
    if hasattr(fit,'weights'):
        diagnostics['score_weights'] = {key:value.tolist() for key,value in fit.weights.items()}
    if method in ('dml_irm','dml_iivm'):
        diagnostics['normalize_ipw'] = fit.normalize_ipw
        diagnostics['propensity_score_processing'] = vars(fit.ps_processor_config)
    if method == 'dml_iivm':
        diagnostics['subgroups'] = fit.subgroups
    if bootstrap is not None:
        diagnostics['bootstrap'] = {**bootstrap,'t_statistics':fit.boot_t_stat.tolist()}
    return fit, intervals, folds, diagnostics, {'doubleml':doubleml.__version__,'scikit-learn':sklearn.__version__}


def run(spec, spec_path):
    if not isinstance(spec, dict) or set(spec) != RUN_FIELDS:
        raise ValueError('specification must contain exactly the documented fields')
    method = spec['method']
    methods = {'gls','iv_gmm','iv_ar','panel_fe','quantile','poisson','logit','rct','rdd_sharp','rdd_fuzzy','hdfe','causal_forest','spatial_lag','rdd_localrand','shift_share','policy_tree','network_spillover','tobit','dynamic_panel','synthetic_control','staggered_did','generalized_synth','multitreatment_did','distribution_effect'} | set(R_METHODS) | set(DML_METHODS)
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
    elif method == 'shift_share':
        if len(spec['endogenous']) != 1 or spec['instruments']: raise ValueError('shift_share requires one endogenous regressor and no input instruments')
    elif method in ('iv_gmm','iv_ar','iv_ar_robust'):
        if not spec['endogenous'] or len(spec['instruments']) < len(spec['endogenous']):
            raise ValueError('IV GMM requires endogenous regressors and at least as many instruments')
    elif spec['endogenous'] or spec['instruments']:
        raise ValueError('endogenous and instruments are reserved for IV methods')
    if method in ('iv_ar','iv_ar_robust') and len(spec['endogenous']) != 1:
        raise ValueError('Anderson-Rubin methods require one endogenous regressor')
    if not isinstance(spec['options'],dict):
        raise ValueError('options must be an object')
    if method in R_METHODS:
        return _official_r(spec, spec_path)
    opt = spec['options']
    required = ({'score','n_folds','seed','learners'} | ({'treatment'} if method=='dml_irm' else set()) if method in DML_METHODS else
        {'gls': {'variance'}, 'iv_gmm': set(), 'iv_ar': {'alpha'}, 'panel_fe': {'entity','time','entity_effects','time_effects'},
                'quantile': {'quantile'}, 'poisson': set(), 'logit': set(), 'rct': {'treatment','permutations','seed'}, 'rdd_sharp': {'running','cutoff','bandwidth'}, 'rdd_fuzzy': {'running','cutoff','bandwidth','treatment'}, 'hdfe': {'fixed_effects'}, 'causal_forest': {'treatment','seed','trees','min_leaf'}, 'spatial_lag': {'weights'}, 'rdd_localrand': {'running','cutoff','bandwidth','permutations','seed'}, 'shift_share': {'shares','shocks'}, 'policy_tree': {'treatment','propensity','partition','seed'}, 'network_spillover': {'weights','treatment'}, 'tobit': {'lower'}, 'dynamic_panel': {'entity','time'}, 'synthetic_control': {'entity','time','treated','training_end','pre_end'}, 'staggered_did': {'entity','time','cohort','control_group'}, 'generalized_synth': {'entity','time','treatment','factors','bootstraps','seed'}, 'multitreatment_did': {'entity','time','pre','post','treatments'}, 'distribution_effect': {'treatment','threshold'}}[method])
    optional = ({'panel','allow_unbalanced_panel','anticipation','weightsname','fix_weights',
                 'alp','bstrap','biters','clustervars','cband','est_method','base_period',
                 'faster_mode','seed','aggregation'} if method == 'staggered_did' else set())
    if method == 'hdfe':
        optional = {'weights','weights_type','ssc','vcov','confidence_level'}
    if method in DML_METHODS:
        optional = {'n_rep','confidence_level','joint','bootstrap','sample_splitting','definitions'}
        if method in ('dml_irm','dml_iivm'):
            optional |= {'normalize_ipw','trimming_rule','trimming_threshold','ps_processor_config'}
        optional |= {'weights'} if method=='dml_irm' else {'subgroups'} if method=='dml_iivm' else set()
    if not required <= set(opt) or set(opt) - required - optional:
        raise ValueError(f'{method} options must contain exactly {sorted(required)}')
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
             [opt['treatment']] if method in ('causal_forest','dml_irm') else
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
    if method == 'dml_irm' and isinstance(opt.get('weights'),str):
        columns.append(opt['weights'])
    if method in DML_METHODS:
        columns += dml_clusters
    elif inf['type']=='cluster': columns += [inf['cluster']]
    if any(not isinstance(x,str) or not x for x in columns): raise ValueError('column names must be nonempty strings')
    roles = [spec['id'],spec['outcome'],*spec['regressors'],*spec['endogenous'],*spec['instruments']]
    if method == 'dml_irm': roles.append(opt['treatment'])
    if method in DML_METHODS and set(dml_clusters) & set(roles[1:]):
        raise ValueError('DoubleML cluster columns must be distinct from model columns')
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
    if method == 'hdfe' and opt.get('weights') is not None: numeric.append(opt['weights'])
    if method == 'policy_tree': numeric.extend([opt['treatment'],opt['propensity']])
    if method == 'shift_share': numeric.extend(opt['shares'])
    if method == 'gls': numeric.append(opt['variance'])
    if method in ('rdd_fuzzy','causal_forest','dml_irm'): numeric.append(opt['treatment'])
    if method == 'dml_irm' and isinstance(opt.get('weights'),str): numeric.append(opt['weights'])
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
        term = opt['treatment'] if method=='dml_irm' else spec['endogenous'][0]
        coef = pd.Series(fit.coef,index=[term]); se = pd.Series(fit.se,index=[term])
        pv = pd.Series(fit.pval,index=[term]); cov = pd.DataFrame([[float(fit.se[0]**2)]],index=[term],columns=[term])
        reference = 'normal'; engine = 'doubleml.'+DML_METHODS[method]
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
        weights=np.asarray(model.W,dtype=float); synthetic=controls.to_numpy()@weights; gaps=target.to_numpy()-synthetic
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
    arrays=[np.asarray(z,dtype=float) for z in (coef,cov,se,pv,ci)]
    if any(not np.isfinite(z).all() for z in arrays): raise ArithmeticError('estimator returned nonfinite inference')
    names=list(coef.index); vals=[float(v) for v in coef]; std=[float(v) for v in se]
    units={k:(spec['unit'] if k in ('const','treatment_effect','sample_ate','policy_value_gain','overall','post') or k.startswith(('event_','cohort_','time_')) else 'dimensionless' if k in ('spatial_lag','log_sigma','L1.'+spec['outcome']) else f"{spec['unit']} per one unit of {k}") for k in names}
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
    result = {'method':method,'engine':engine,'versions':versions,'options':opt,'adopted':{k:spec[k] for k in ('population','period','unit','estimand','identification','assignment','inference')},'sample':{'id_column':spec['id'],'included_ids':d[spec['id']].astype(str).tolist(),'excluded_incomplete_ids':excluded,'excluded_outside_window_ids':outside,'training_ids':training,'excluded_initial_lag_ids':initial_lags,'input_rows':int(input_rows),'observations':int(fit_n)},'coefficients':dict(zip(names,vals)),'standard_errors':dict(zip(names,std)),'covariance_kind':'upper bound on scalar variance' if method=='causal_forest' else 'estimator covariance','covariance':{a:{b:float(cov.loc[a,b]) for b in names} for a in names},'inference':{'reference':reference,'p_values':{k:float(pv.loc[k]) for k in names},'confidence_level':confidence_level,'confidence_intervals':{k:[float(x) for x in ci.loc[k]] for k in names}},'diagnostics':diagnostics,'statistics':stats,'provenance':{'data_path':str(p),'data_sha256':_hash(p),'spec_path':str(spec_path.resolve()),'spec_sha256':_hash(spec_path)}}
    if confidence_level == 0.95:
        result['inference']['confidence_intervals_95'] = result['inference']['confidence_intervals']
    if method in DML_METHODS:
        result['folds'] = dml_folds
        result['sample']['complete_case_columns'] = list(dict.fromkeys(columns))
        result['design'] = {'outcome':spec['outcome'],'treatment':term,'covariates':spec['regressors'],
            'instruments':spec['instruments'],'score':opt['score'],'cluster_columns':dml_clusters}
        result['inference'].update(procedure='official cross-fitted orthogonal-score inference',
            interval_type='joint multiplier bootstrap' if opt.get('joint') else 'pointwise',
            standard_error_method='official clustered score variance' if dml_clusters else 'official score variance',
            repetitions=fit.n_rep, coefficient_aggregation='median over sample-splitting repetitions')
        result['display'] = {'kind':'coefficient','rows':[{'term':term,'estimate':vals[0],'se':std[0],
            'p_value':float(pv.iloc[0]),'ci_low':float(ci.iloc[0,0]),'ci_high':float(ci.iloc[0,1]),
            'n':int(fit_n),'unit':spec['unit']}],
            'metadata':{**opt.get('definitions',{}),'estimand':spec['estimand'],'population':spec['population'],
                'period':spec['period'],'unit':spec['unit'],'score':opt['score'],'engine':engine,
                'confidence_level':confidence_level,'interval_type':result['inference']['interval_type'],
                'inference':spec['inference'],'producer':{'function':engine,'versions':versions}}}
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
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='operation',required=True)
    run_parser=sub.add_parser('run'); run_parser.add_argument('spec',type=Path); run_parser.add_argument('--output','-o',required=True,type=Path)
    select_parser=sub.add_parser('select'); select_parser.add_argument('spec',type=Path); select_parser.add_argument('--output','-o',required=True,type=Path)
    a=parser.parse_args()
    try:
        spec=json.loads(a.spec.read_text(encoding='utf-8'))
        result=select_method(spec) if a.operation=='select' else run(spec,a.spec)
        state.save(a.output,result)
    except (ValueError,TypeError,KeyError,OSError,ArithmeticError) as exc: parser.exit(2,f'error: {exc}\n')

if __name__=='__main__': main()
