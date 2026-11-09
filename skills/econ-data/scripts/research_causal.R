
args <- commandArgs(trailingOnly=TRUE)
suppressPackageStartupMessages(library(jsonlite))
s <- fromJSON(args[1], simplifyVector=TRUE); o <- s$options; method <- s$method
# JSON empty arrays are lists in jsonlite; native column selectors require vectors.
for(field in c('regressors','endogenous','instruments')) s[[field]] <- as.character(unlist(s[[field]],use.names=FALSE))
pkg <- args[3]; fname <- args[4]
if(!requireNamespace(pkg,quietly=TRUE)) stop(paste('Install the selected official package:',pkg))
uses_polars <- method=='did_multiplegt_dyn' || (method=='nonabs_did' && identical(o$estimator,'DCDH'))
if(uses_polars) suppressPackageStartupMessages(library(polars))
qte_method <- method %in% c('qte','qtt','quantile_did','changes_in_changes')
grf_method <- method %in% c('grf','grf_instrumental','grf_multi_arm','grf_survival')
if(qte_method && packageVersion('qte') < '2.0.0') stop('These distributional-effect interfaces require qte >= 2.0.0')
if(method=='iv_ar_robust' && packageVersion('ivDiag') < '1.0.8') stop('iv_ar_robust requires ivDiag >= 1.0.8 for whole-line confidence-set inversion')
fun <- getExportedValue(pkg,fname)
formal_names <- names(formals(fun))
invoke <- function(f, a, additional=character(), call_name=NULL) {
  unknown <- setdiff(names(a),c(names(formals(f)),additional))
  if(length(unknown)) stop(paste('Unsupported official option:',paste(unknown,collapse=', ')))
  if(is.null(call_name)) do.call(f,a) else do.call(call_name,a,envir=asNamespace(pkg))
}
if(!is.null(o$seed)) set.seed(o$seed)
if(method=='wild_cluster_bootstrap' && !is.null(o$seed)) dqrng::dqset.seed(o$seed)
postprocess <- method %in% c('honest_did','wild_cluster_bootstrap','club_sandwich','marginaleffects')
if(postprocess) {
  source <- fromJSON(args[2],simplifyVector=FALSE)
  if(method != 'honest_did') {
    model_engine <- if(is.null(source$source_model$engine)) source$engine else source$source_model$engine
    if(!is.null(model_engine) && grepl('^[A-Za-z][A-Za-z0-9.]*::',model_engine)) {
      model_package <- sub('::.*$','',model_engine)
      if(!requireNamespace(model_package,quietly=TRUE)) stop(paste('Install the saved model package:',model_package))
    }
    native <- unserialize(base64_dec(source$native_fit$data))
    fit_source <- native$fit; d <- native$data; ids <- native$ids
    if(method=='marginaleffects') {
      model_data <- d; model_ids <- ids
      fit_source <- marginaleffects::set_modeldata(fit_source,model_data)
      if(nzchar(args[6])) {
        d <- ers_read_table(args[6],text_columns=o$evaluation_id)
        if(!o$evaluation_id %in% names(d) || anyNA(d[[o$evaluation_id]]) ||
           any(!nzchar(trimws(as.character(d[[o$evaluation_id]])))) || anyDuplicated(d[[o$evaluation_id]]))
          stop('Evaluation IDs must be nonmissing, nonempty and unique')
        ids <- as.character(d[[o$evaluation_id]])
        for(column in intersect(names(d),names(model_data))) if(is.factor(model_data[[column]])) {
          if(any(!is.na(d[[column]]) & !d[[column]] %in% levels(model_data[[column]])))
            stop(paste('Evaluation factor has levels absent from the saved model:',column))
          d[[column]] <- factor(d[[column]],levels=levels(model_data[[column]]),ordered=is.ordered(model_data[[column]]))
        }
      }
    }
  }
} else {
  text_columns <- s$id
  if(grf_method) text_columns <- unique(c(text_columns,unlist(o$columns$clusters,use.names=FALSE)))
  if(method=='grf_multi_arm') text_columns <- unique(c(text_columns,o$treatment))
  columns <- switch(method,
    rddensity=c(s$id,o$running),
    rdrobust_r=c(s$id,s$outcome,o$running),
    rdpower=c(s$id,s$outcome,o$running),
    bunching=c(s$id,s$outcome),
    continuous_did=c(s$id,s$outcome,o$entity,o$time,o$cohort,o$dose),
    drdid_panel=c(s$id,s$outcome,s$regressors,o$entity,o$time,o$treatment),
    drdid_rc=c(s$id,s$outcome,s$regressors,o$time,o$treatment),
    NULL)
  if(grf_method && method!='grf') columns <- c(s$id,s$outcome,s$regressors,o$treatment,o$instrument,o$status)
  if(!is.null(columns)) columns <- unique(c(columns,unlist(o$columns,use.names=FALSE)))
  # Saved regression models retain the full data for later grouping and covariance calls.
  d <- ers_read_table(args[2],text_columns=text_columns,columns=columns)
  if(!s$id %in% names(d) || anyNA(d[[s$id]]) ||
     any(!nzchar(trimws(as.character(d[[s$id]])))) || anyDuplicated(d[[s$id]]))
    stop('Input IDs must be nonmissing, nonempty and unique')
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
if(method=='heckman') {
  if(as.character(packageVersion('sampleSelection'))!='1.2.16')
    stop('This Heckman binding requires sampleSelection 1.2-16')
  selection_columns <- c(o$selection,o$selection_regressors)
  outcome_columns <- c(s$outcome,s$regressors)
  model_columns <- unique(c(selection_columns,outcome_columns))
  if(!all(model_columns %in% names(d)) || !all(grepl('^[A-Za-z_][A-Za-z0-9_]*$',model_columns)))
    stop('Heckman equations require existing columns with simple names')
  if(any(!nzchar(trimws(ids)))) stop('Heckman IDs must be nonempty')
  selected <- d[[o$selection]]
  if(!is.numeric(selected) || any(!is.na(selected) & !selected %in% c(0,1)))
    stop('Heckman selection must be numeric zero or one')
  if(!is.numeric(d[[s$outcome]])) stop('Heckman requires a numeric continuous outcome')
  d[[s$outcome]][which(selected==0)] <- NA_real_
  selection_complete <- complete.cases(d[,selection_columns,drop=FALSE])
  outcome_complete <- complete.cases(d[,outcome_columns,drop=FALSE])
  for(column in selection_columns) if(is.numeric(d[[column]]))
    selection_complete <- selection_complete & is.finite(d[[column]])
  for(column in outcome_columns) if(is.numeric(d[[column]]))
    outcome_complete <- outcome_complete & is.finite(d[[column]])
  keep <- selection_complete & (selected==0 | outcome_complete)
  diagnostics$input_rows <- nrow(d); diagnostics$input_ids <- I(ids)
  diagnostics$excluded_incomplete_ids <- I(ids[!keep])
  d <- d[keep,,drop=FALSE]; ids <- ids[keep]; rownames(d) <- ids
  if(!setequal(unique(d[[o$selection]]),c(0,1))) stop('Heckman estimation requires selected and unselected observations')
  selection_formula <- reformulate(o$selection_regressors,response=o$selection)
  outcome_formula <- reformulate(if(length(s$regressors)) s$regressors else '1',response=s$outcome)
  owned <- list(selection=selection_formula,outcome=outcome_formula,data=d,
    method=o$estimation_method,type=2L,weights=NULL,maxMethod='Newton-Raphson')
  if(o$estimation_method=='ml') owned <- c(owned,list(ys=TRUE,xs=TRUE,yo=TRUE,xo=TRUE,mfs=TRUE,mfo=TRUE))
  display_metadata$selection_equation <- paste(deparse(selection_formula),collapse=' ')
  display_metadata$outcome_equation <- paste(deparse(outcome_formula),collapse=' ')
  display_metadata$excluded_selection_regressors <- I(setdiff(o$selection_regressors,s$regressors))
  display_metadata$estimation_method <- o$estimation_method
  display_metadata$reference_distribution <- 'Student t with sampleSelection native residual degrees of freedom'
  display_metadata$inference_procedure <- 'sampleSelection iid covariance; native Student-t p values and Student-t Wald intervals'
  display_metadata$conditions <- o$definitions$conditions
  display_metadata$outcome_observation_rule <- paste0(o$selection,' = 1')
} else if(method=='continuous_did') {
  if(as.character(packageVersion('contdid'))!='0.1.2' || as.character(packageVersion('ptetools'))!='1.0.1')
    stop('This continuous-DID binding requires the adopted contdid 0.1.2 and ptetools 1.0.1 interfaces')
  defaults <- list(treatment_type='continuous',dose_est_method='parametric',control_group='notyettreated',
    base_period='varying',anticipation=0,allow_unbalanced_panel=FALSE,bstrap=TRUE,cband=FALSE,
    boot_type='multiplier',alp=.05,biters=1000L,degree=3L,num_knots=0L,cl=1L)
  for(k in names(defaults)) if(is.null(call_args[[k]])) call_args[[k]] <- defaults[[k]]
  if(!is.null(call_args$panel) && !identical(call_args$panel,TRUE)) stop('contdid 0.1.2 requires panel observations')
  call_args$panel <- NULL
  if(!is.null(call_args$xformula) && (!is.character(call_args$xformula) ||
     length(call_args$xformula)!=1L || gsub(' ','',call_args$xformula,fixed=TRUE)!='~1'))
    stop('contdid 0.1.2 supports xformula=~1 only')
  call_args$xformula <- as.formula('~1')
  if(!identical(call_args$treatment_type,'continuous') || !identical(call_args$allow_unbalanced_panel,FALSE))
    stop('contdid 0.1.2 requires continuous treatment and a balanced panel')
  if(!is.null(call_args$est_method) || !is.null(call_args$weightsname))
    stop('contdid 0.1.2 does not execute covariate adjustment or the requested sampling weights')
  if(!identical(call_args$control_group,'notyettreated') || !identical(call_args$base_period,'varying') ||
     !identical(call_args$bstrap,TRUE) || length(call_args$anticipation)!=1L || call_args$anticipation!=0)
    stop('contdid 0.1.2 executes notyettreated controls, varying base periods, zero anticipation and bootstrap inference')
  if(!is.null(call_args$clustervars) && !identical(as.character(call_args$clustervars),o$entity))
    stop('contdid 0.1.2 does not forward external clustervars; inference uses independent panel entities')
  if(!identical(call_args$boot_type,'multiplier'))
    stop('This contdid 0.1.2 binding preserves the official multiplier inference path')
  if(!is.logical(call_args$cband) || length(call_args$cband)!=1L || is.na(call_args$cband)) stop('cband must be boolean')
  if(!is.numeric(call_args$alp) || length(call_args$alp)!=1L || !is.finite(call_args$alp) || call_args$alp<=0 || call_args$alp>=1)
    stop('alp must be between zero and one')
  for(k in c('biters','degree','num_knots','cl')) {
    z <- call_args[[k]]; minimum <- switch(k,biters=2L,degree=1L,num_knots=0L,cl=1L)
    if(!is.numeric(z) || length(z)!=1L || !is.finite(z) || z<minimum || z!=floor(z))
      stop(paste(k,'must be an integer of at least',minimum))
  }
  if(!call_args$dose_est_method %in% c('parametric','cck')) stop('dose_est_method must be parametric or cck')
  if(!is.null(call_args$dvals) && (!is.numeric(call_args$dvals) || length(call_args$dvals)<2L ||
     any(!is.finite(call_args$dvals)) || any(call_args$dvals<=0) || is.unsorted(call_args$dvals,strictly=TRUE)))
    stop('dvals must contain at least two increasing distinct positive doses')
  model_columns <- c(s$outcome,o$entity,o$time,o$cohort,o$dose)
  if(!all(model_columns %in% names(d))) stop('Missing continuous-DID outcome, entity, time, cohort or dose column')
  if(!nrow(d) || any(!complete.cases(d[,model_columns,drop=FALSE])) || any(!nzchar(trimws(ids))) ||
     any(!nzchar(trimws(as.character(d[[o$entity]])))))
    stop('continuous DID requires the adopted complete panel and nonempty row/entity IDs; no rows are discarded')
  for(k in c(s$outcome,o$time,o$cohort,o$dose)) if(!is.numeric(d[[k]]) || any(!is.finite(d[[k]])))
    stop(paste('Continuous-DID column must be finite and numeric:',k))
  if(anyDuplicated(d[,c(o$entity,o$time)])) stop('continuous DID requires unique entity-time pairs')
  times <- sort(unique(d[[o$time]]))
  if(length(times)<2L || any(times<=0 | times!=floor(times))) stop('contdid time codes must be positive integers with at least two periods')
  panels <- split(seq_len(nrow(d)),d[[o$entity]])
  if(any(vapply(panels,length,integer(1))!=length(times))) stop('contdid requires every entity in every adopted period')
  if(any(vapply(panels,function(i) length(unique(d[[o$dose]][i]))!=1L,logical(1))))
    stop('Fixed dose must be constant within every entity, including all pretreatment periods')
  if(any(vapply(panels,function(i) length(unique(d[[o$cohort]][i]))!=1L,logical(1))))
    stop('First-treatment cohort must be constant within every entity')
  cohorts <- sort(unique(d[[o$cohort]]))
  if(!0 %in% cohorts || length(cohorts)<2L || any(!cohorts %in% c(0,times[-1L])))
    stop('contdid/ptetools requires never-treated cohort zero and observed treatment cohorts with a pretreatment period')
  if(any(d[[o$dose]][d[[o$cohort]]==0]!=0) || any(d[[o$dose]][d[[o$cohort]]!=0]<=0))
    stop('The adopted dose must be zero for never-treated entities and positive for every treated entity')
  if(length(unique(d[[o$dose]][d[[o$cohort]]!=0]))<2L) stop('Continuous-dose estimation requires distinct positive treated doses')
  if('.ers_contdid_row_id' %in% names(d)) stop('.ers_contdid_row_id is reserved for continuous-DID sample correspondence')
  if(call_args$dose_est_method=='cck') {
    if(as.character(packageVersion('npiv'))!='0.1.3') stop('The CCK binding requires the adopted npiv 0.1.3 interface')
    if(length(times)!=2L || length(cohorts)!=2L || call_args$aggregation!='dose')
      stop('contdid CCK requires two periods, common treatment timing and dose aggregation')
    if(!isTRUE(call_args$cband) || call_args$alp!=.05 || call_args$degree!=3L || call_args$num_knots!=0L || !is.null(call_args$dvals))
      stop('contdid 0.1.2 CCK uses native observed-dose evaluation, adaptive cubic splines and 95% uniform bands; use cband=true, alp=.05, degree=3, num_knots=0 and omit dvals')
  }
  d$.ers_contdid_row_id <- ids
  owned <- list(yname=s$outcome,dname=o$dose,gname=o$cohort,tname=o$time,idname=o$entity,data=d)
  confidence_level <- 1-call_args$alp
  kind <- if(call_args$aggregation=='dose') 'dose-response' else 'event-study'
  diagnostics$input_rows <- length(ids)
  diagnostics$entity_ids <- I(as.character(unique(d[[o$entity]])))
  diagnostics$n_entities <- length(panels)
  diagnostics$n_clusters <- length(panels)
  diagnostics$entity_doses <- d[!duplicated(d[[o$entity]]),c(o$entity,o$cohort,o$dose),drop=FALSE]
  diagnostics$time_periods <- I(times)
  display_metadata$target_parameter <- call_args$target_parameter
  display_metadata$aggregation <- call_args$aggregation
  display_metadata$dose_est_method <- call_args$dose_est_method
  display_metadata$primary_quantity <- if(is.null(o$quantity)) 'curve' else o$quantity
  display_metadata$interval_type <- if(isTRUE(call_args$cband)) 'simultaneous' else 'pointwise'
  display_metadata$inference_unit <- o$entity
  display_metadata$control_group <- 'notyettreated'
  display_metadata$base_period <- 'varying'
  display_metadata$anticipation <- 0
  display_metadata$dose <- o$dose
  display_metadata$dose_unit <- o$definitions$dose_unit
  display_metadata$outcome_unit <- o$definitions$outcome_unit
  display_metadata$reference_distribution <- 'standard_normal for pointwise intervals; native bootstrap critical value for uniform bands'
  display_metadata$inference_procedure <- if(call_args$dose_est_method=='cck') 'official npiv asymptotic SE and adaptive uniform bands; native overall-effect inference' else 'official contdid/ptetools entity multiplier bootstrap'
} else if(method=='bunching') {
  if(any(!nzchar(trimws(ids)))) stop('Bunching IDs must be nonempty')
  if(!s$outcome %in% names(d) || !is.numeric(d[[s$outcome]])) stop('Bunching requires a numeric unbinned outcome column')
  keep <- is.finite(d[[s$outcome]])
  diagnostics$input_rows <- nrow(d); diagnostics$excluded_incomplete_ids <- I(ids[!keep])
  d <- d[keep,,drop=FALSE]; ids <- ids[keep]
  if(!length(ids)) stop('No finite unbinned observations')
  owned <- list(z_vector=d[[s$outcome]])
  call_args$seed <- o$seed
  if(is.null(call_args$n_boot)) call_args$n_boot <- 100L
  if(is.null(call_args$notch)) call_args$notch <- FALSE
  confidence_level <- NULL
  kind <- 'coefficient'
  display_metadata$interval_type <- 'none'
  display_metadata$inference_procedure <- 'official residual bootstrap of binned-frequency residuals'
  display_metadata$bootstrap_repetitions <- call_args$n_boot
  display_metadata$normalization <- 'B divided by mean counterfactual bin count over the excluded bunching region'
  display_metadata$primary_quantity <- if(is.null(o$quantity)) 'b' else o$quantity
  display_metadata$running_unit <- o$definitions$running_unit
} else if(method=='marginaleffects') {
  if(packageVersion('marginaleffects') <= '1.0.0') {
    if(any(call_args$comparison %in% c('expdydx','expdydxavg','expdydxavgwts')))
      stop('These exponentiated-outcome derivative comparisons require the official marginaleffects correction 870f15a0f79525cedebc6b73ee2446851f8bc66d; the installed version divides the estimate and its standard error by exp(eps)')
  }
  if(packageVersion('marginaleffects') < '1.0.0.10005' &&
     o[["function"]] %in% c('predictions','avg_predictions') &&
     any(call_args$by %in% c('Predicted','SE','CI_low','CI_high')))
    stop('Prediction grouping by Predicted, SE, CI_low or CI_high requires marginaleffects 1.0.0.10005 with official correction 9ac42288138c25966ab901f64c60c859bc23e664')
  needs_padding <- any(vapply(d,function(x) is.factor(x) && any(!levels(x) %in% as.character(x)),logical(1)))
  if(needs_padding && packageVersion('marginaleffects') < '1.0.0.10004')
    stop('Factor-level padding requires marginaleffects 1.0.0.10004 or later with unique negative row IDs, correction 701d7d8670e678d2d196e0975cf5342a6bd6987d')
  if(is.null(call_args$conf_level)) call_args$conf_level <- .95
  if(is.character(call_args$vcov) && length(call_args$vcov)==1L && startsWith(call_args$vcov,'~'))
    call_args$vcov <- as.formula(call_args$vcov)
  if(is.null(call_args$wts)) call_args$wts <- FALSE
  owned <- list(model=fit_source,newdata=d)
  confidence_level <- call_args$conf_level
  kind <- if(startsWith(o[["function"]],'avg_') && !grepl('predictions',o[["function"]])) 'coefficient' else 'table'
  diagnostics$estimation_ids <- I(as.character(model_ids))
  diagnostics$evaluation_ids <- I(as.character(ids))
  diagnostics$estimation_observations <- length(model_ids)
  diagnostics$evaluation_observations <- length(ids)
  diagnostics$model_class <- I(class(fit_source))
  diagnostics$estimation_weights <- stats::weights(fit_source)
  display_metadata$evaluation_population <- s$population
  display_metadata$averaging <- if(startsWith(o[["function"]],'avg_')) 'average' else if(!is.null(call_args$by) && !identical(call_args$by,FALSE)) 'within by groups' else 'individual'
  display_metadata$weight_scope <- 'wts weights only the averaging of unit-level post-estimation quantities'
  display_metadata$quantity <- o[["function"]]
  display_metadata$scale <- call_args$type
  display_metadata$inference_procedure <- if(identical(call_args$vcov,FALSE)) 'none' else 'official marginaleffects delta method'
  display_metadata$interval_type <- if(identical(call_args$vcov,FALSE)) 'none' else 'pointwise'
  display_metadata$covariance <- if(is.null(call_args$vcov)) 'saved model covariance' else if(inherits(call_args$vcov,'formula'))
    paste(deparse(call_args$vcov),collapse=' ') else call_args$vcov
  if(inherits(call_args$vcov,'formula')) display_metadata$cluster_columns <- I(all.vars(call_args$vcov))
} else if(qte_method) {
  cross_section <- method %in% c('qte','qtt')
  model_columns <- unique(as.character(unlist(c(s$outcome,s$regressors,if(cross_section) o$treatment else c(o$entity,o$time,o$cohort),call_args$weightsname),use.names=FALSE)))
  if(!all(model_columns %in% names(d))) stop('Missing adopted distributional-effect columns')
  keep <- complete.cases(d[,model_columns,drop=FALSE])
  diagnostics$input_rows <- nrow(d); diagnostics$excluded_missing_ids <- I(ids[!keep])
  d <- d[keep,,drop=FALSE]; ids <- ids[keep]
  if(!length(ids)) stop('The distributional-effect sample has no complete observations')
  if(!is.numeric(d[[s$outcome]]) || any(!is.finite(d[[s$outcome]]))) stop('Distributional effects require finite numerical outcomes')
  if(!is.null(call_args$weightsname)) {
    w <- d[[call_args$weightsname]]
    if(!is.numeric(w) || any(!is.finite(w)) || any(w<=0)) stop('Sampling weights must be finite and positive')
    if(cross_section && packageVersion('qte') <= '2.0.0')
      stop('qte <= 2.0.0 resamples data without resampling its weight vector; weighted inference requires an official implementation preserving observation-weight correspondence')
    diagnostics$sampling_weights <- I(w)
  }
  if(is.null(call_args$probs)) call_args$probs <- seq(.05,.95,.05)
  if(!is.numeric(call_args$probs) || any(!is.finite(call_args$probs)) || any(call_args$probs<=0 | call_args$probs>=1) ||
     is.unsorted(call_args$probs,strictly=TRUE)) stop('probs must be increasing distinct quantiles between zero and one')
  if(is.null(call_args$alp)) call_args$alp <- .05
  if(!is.numeric(call_args$alp) || length(call_args$alp)!=1L || !is.finite(call_args$alp) || call_args$alp<=0 || call_args$alp>=1) stop('alp must be between zero and one')
  if(is.null(call_args$biters)) call_args$biters <- 100L
  if(!is.numeric(call_args$biters) || length(call_args$biters)!=1L || call_args$biters<2 || call_args$biters!=as.integer(call_args$biters)) stop('biters must be an integer of at least two')
  if(is.null(call_args$cl)) call_args$cl <- 1L
  xform <- reformulate(if(length(s$regressors)) s$regressors else '1')
  if(cross_section) {
    if(!setequal(unique(d[[o$treatment]]),c(0,1))) stop('QTE/QTT treatment must contain both zero and one')
    if(isTRUE(call_args$cband)) stop('unc_qte 2.0.0 returns pointwise intervals; cband=TRUE does not supply uniform endpoints')
    call_args$cband <- FALSE
    owned <- list(yname=s$outcome,dname=o$treatment,data=d,xformla=xform,target=method)
    display_metadata$target_population <- if(method=='qte') 'all sampled units' else 'treated sampled units'
  } else {
    if('.ers_qte_row_id' %in% names(d)) stop('.ers_qte_row_id is reserved for qte sample correspondence')
    if(!is.null(call_args$weightsname) && packageVersion('ptetools') <= '1.0.2')
      stop('ptetools <= 1.0.2 does not preserve weightsname in the QTT bootstrap; weighted inference requires an official implementation preserving that argument')
    d$.ers_qte_row_id <- ids
    if(is.null(call_args$panel)) call_args$panel <- TRUE
    if(!is.logical(call_args$panel) || length(call_args$panel)!=1L) stop('panel must be boolean')
    if(isTRUE(call_args$panel) && anyDuplicated(d[,c(o$entity,o$time)])) stop('Distributional DID requires unique entity-time observations')
    if(!0 %in% d[[o$cohort]]) stop('qte 2.0.0 panel setup requires a never-treated cohort coded zero')
    if(is.null(call_args$cband)) call_args$cband <- FALSE
    owned <- list(yname=s$outcome,gname=o$cohort,tname=o$time,idname=o$entity,data=d,xformula=xform,gt_type='qtt')
    display_metadata$target_population <- 'treated cohort-period distributions under the selected official aggregation'
  }
  confidence_level <- 1-call_args$alp
  kind <- 'qte'
  display_metadata$interval_type <- if(isTRUE(call_args$cband)) 'simultaneous over quantiles within each curve' else 'pointwise'
  display_metadata$aggregation <- if(is.null(o$aggregation)) 'overall' else o$aggregation
  display_metadata$aggregation_method <- if(cross_section) 'marginal potential-outcome quantile difference' else 'mix potential-outcome distributions before taking quantile differences'
  display_metadata$quantile_convention <- 'official qte/ptetools marginal-distribution quantile extraction'
  display_metadata$inference_unit <- if(cross_section || !isTRUE(call_args$panel)) s$id else o$entity
  display_metadata$inference_procedure <- 'official empirical bootstrap'
} else if(method %in% c('ols_r','fixest_ols','fixest_ppml','negative_binomial_r','sunab')) {
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
  owned <- list(data=d,outcome=s$outcome,treatment=o$treatment,unit=o$entity,time=o$time,method=o$estimator,
    controls=if(length(s$regressors)) s$regressors else NULL)
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
  owned <- list(df=d,outcome=s$outcome,group=o$entity,time=o$time,treatment=o$treatment,
    controls=if(length(s$regressors)) s$regressors else NULL)
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
} else if(grf_method) {
  if(any(!nzchar(trimws(ids)))) stop('GRF IDs must be nonempty')
  if(is.character(call_args$clusters)) call_args$clusters <- factor(call_args$clusters)
  owned <- list(X=as.matrix(d[,s$regressors,drop=FALSE]),Y=d[[s$outcome]],W=d[[o$treatment]])
  grf_quantity <- if(is.null(o$quantity)) 'average' else o$quantity
  aggregate_args <- utils::modifyList(list(target.sample='all',method='AIPW'),if(is.null(o$aggregation)) list() else o$aggregation)
  aggregate_args$target.sample <- match.arg(aggregate_args$target.sample,c('all','treated','control','overlap'))
  aggregate_args$method <- match.arg(aggregate_args$method,c('AIPW','TMLE'))
  if(method!='grf' && (aggregate_args$target.sample!='all' || aggregate_args$method!='AIPW'))
    stop('This GRF forest aggregates with method=AIPW and target.sample=all')
  if(method=='grf_instrumental') {
    owned$Z <- d[[o$instrument]]
    binary_instrument <- all(owned$Z %in% c(0,1)) && length(unique(owned$Z))==2L
    if(grf_quantity=='average' && !binary_instrument)
      stop('Native average_treatment_effect for instrumental forests requires a binary 0/1 instrument; conditional predictions retain the native numeric-instrument target')
    if(o$definitions$iv_estimand=='conditional_late' &&
       (!binary_instrument || !all(owned$W %in% c(0,1)) || length(unique(owned$W))!=2L))
      stop('The conditional complier LATE contract requires binary 0/1 treatment and instrument')
  }
  if(method=='grf_multi_arm') {
    arms <- unlist(o$arms,use.names=FALSE)
    if(anyNA(owned$W) || !setequal(unique(owned$W),arms))
      stop('Every declared GRF arm must occur, and all treatment labels must belong to arms')
    owned$W <- factor(owned$W,levels=arms)
    if(!is.null(call_args$W.hat)) {
      if(is.matrix(call_args$W.hat)) {
        if(ncol(call_args$W.hat)!=length(arms)) stop('W.hat columns must follow the complete declared arm order')
        colnames(call_args$W.hat) <- arms
      }
      if(any(!is.finite(call_args$W.hat)) || any(call_args$W.hat<=0 | call_args$W.hat>=1) ||
         (is.matrix(call_args$W.hat) && any(abs(rowSums(call_args$W.hat)-1)>1e-8)) ||
         (!is.matrix(call_args$W.hat) && abs(sum(call_args$W.hat)-1)>1e-8))
        stop('Supplied multi-arm W.hat must give positive arm probabilities summing to one')
    }
  }
  if(method=='grf_survival') owned$D <- d[[o$status]]
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
if(method=='heckman') additional <- c(names(formals(sampleSelection::selection)),'maxMethod')
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
invisible(capture.output(fit <- invoke(fun,all_args,additional,
  if(method=='wild_cluster_bootstrap') paste0('boottest.',supported[1]) else NULL)))
if(method=='heckman') {
  optimization <- if(o$estimation_method=='2step') fit$probit else fit
  code <- maxLik::returnCode(optimization)
  diagnostics$convergence <- list(algorithm='Newton-Raphson',stage=if(o$estimation_method=='2step') 'selection probit' else 'joint likelihood',
    code=code,message=maxLik::returnMessage(optimization),iterations=maxLik::nIter(optimization),converged=code %in% c(1L,2L,8L))
  if(!diagnostics$convergence$converged) stop(paste('Heckman native optimizer did not converge:',diagnostics$convergence$message))
  selection_ids <- if(o$estimation_method=='2step') rownames(optimization$x) else rownames(fit$xs)
  outcome_ids <- if(o$estimation_method=='2step') rownames(model.frame(fit$lm)) else selection_ids[fit$ys==1]
  if(length(selection_ids)!=fit$param$nObs || anyDuplicated(selection_ids) || !all(selection_ids %in% ids) ||
     length(outcome_ids)!=fit$param$N1 || anyDuplicated(outcome_ids) || !all(outcome_ids %in% selection_ids))
    stop('Heckman native observation identities do not match its returned sample counts')
  diagnostics$excluded_engine_ids <- I(setdiff(ids,selection_ids))
  d <- d[match(selection_ids,ids),,drop=FALSE]; ids <- as.character(selection_ids)
  if(!setequal(outcome_ids,ids[d[[o$selection]]==1])) stop('Heckman outcome IDs do not match the selected observations')
  diagnostics$selection_ids <- I(ids); diagnostics$observed_outcome_ids <- I(as.character(outcome_ids))
  diagnostics$unselected_ids <- I(setdiff(ids,outcome_ids))
  diagnostics$observations <- fit$param$nObs
  diagnostics$observed_outcomes <- fit$param$N1; diagnostics$unselected_observations <- fit$param$N0
  diagnostics$residual_df <- fit$param$df
  if(!is.finite(fit$param$df) || fit$param$df<=0) stop('Heckman coefficient inference requires positive native residual degrees of freedom')
  summary_fit <- summary(fit)
  full <- coef(summary_fit,part='full')
  full_covariance <- vcov(fit,part='full')
  outcome_index <- fit$param$index$outcome
  tab <- full[outcome_index,,drop=FALSE]
  covariance <- full_covariance[outcome_index,outcome_index,drop=FALSE]
  if(any(!is.finite(tab)) || any(!is.finite(covariance))) stop('Heckman returned nonfinite outcome coefficients or covariance')
  critical <- qt((1+confidence_level)/2,df=fit$param$df)
  estimates <- data.frame(term=rownames(tab),estimate=tab[,1],se=tab[,2],p_value=tab[,4],
    ci_low=tab[,1]-critical*tab[,2],ci_high=tab[,1]+critical*tab[,2],row.names=NULL,
    role=ifelse(rownames(tab)=='invMillsRatio','selection_correction','outcome_coefficient'))
  full_terms <- paste0('error.',rownames(full))
  full_terms[fit$param$index$betaS] <- paste0('selection.',rownames(full)[fit$param$index$betaS])
  full_terms[fit$param$index$betaO] <- paste0('outcome.',rownames(full)[fit$param$index$betaO])
  diagnostics$full_parameters <- data.frame(term=full_terms,estimate=full[,1],se=full[,2],statistic=full[,3],p_value=full[,4],row.names=NULL)
  diagnostics$full_covariance <- list(parameter_names_ref='diagnostics.full_parameters[].term',values=unname(full_covariance))
  diagnostics$native_parameter_index <- fit$param$index
  diagnostics$effective_options <- list(estimation_method=fit$method,type=fit$tobitType,
    maxMethod='Newton-Raphson',weights='none',selection=display_metadata$selection_equation,outcome=display_metadata$outcome_equation)
  if(o$estimation_method=='ml') diagnostics$log_likelihood <- as.numeric(logLik(fit)) else {
    diagnostics$selection_log_likelihood <- as.numeric(logLik(fit$probit))
    diagnostics$outcome_rank <- fit$lm$rank
  }
  display_metadata$residual_df <- fit$param$df; display_metadata$critical_value <- critical
  display_metadata$selection_observations <- fit$param$nObs
  display_metadata$observed_outcomes <- fit$param$N1; display_metadata$unselected_observations <- fit$param$N0
  display_metadata$covariance_scope <- 'official outcome equation; includes the Mills coefficient for two-step estimation'
} else if(method=='continuous_did') {
  dose_aggregation <- call_args$aggregation=='dose'
  if((dose_aggregation && !inherits(fit,'dose_obj')) || (!dose_aggregation && !inherits(fit,'pte_results')))
    stop('The adopted continuous-DID aggregation returned an unsupported native class')
  ptep <- if(dose_aggregation) fit$pte_params else fit$ptep
  fitted_ids <- as.character(ptep$data$.ers_contdid_row_id)
  if(length(fitted_ids)!=length(ids) || anyDuplicated(fitted_ids) || !setequal(fitted_ids,ids))
    stop('contdid changed the adopted panel sample; retain the input specification and reconcile its native preprocessing')
  d <- d[match(fitted_ids,ids),,drop=FALSE]; ids <- fitted_ids
  diagnostics$observations <- length(ids)
  diagnostics$excluded_engine_ids <- I(character())
  diagnostics$effective_options <- ptep[setdiff(names(ptep),c('data','call'))]
  diagnostics$bootstrap_repetitions <- list(curve=if(call_args$dose_est_method=='cck') 999L else ptep$biters,
    overall=ptep$biters,group_time=as.numeric(formals(getFromNamespace('mboot2','ptetools'))$biters))
  diagnostics$aggregation_definition <- 'Within each cohort average its post-treatment periods; weight cohorts by their share among ever-treated entities'
  display_metadata$bootstrap_repetitions <- diagnostics$bootstrap_repetitions
  display_metadata$band_family <- if(dose_aggregation) 'each ATT(d) or ACRT(d) curve across its saved dose coordinates' else 'the selected ATT or ACRT curve across its saved event times'
  display_metadata$aggregation_definition <- diagnostics$aggregation_definition
  display_metadata$sample_policy <- 'complete balanced input panel; native row IDs checked against the unchanged adopted sample'
  display_metadata$dose_timing <- 'fixed entity dose in every period, including pretreatment; zero dose for never-treated entities'
  display_metadata$dose_time_invariant <- TRUE
  display_metadata$dose_support <- list(treated_range=range(d[[o$dose]][d[[o$cohort]]!=0]),
    by_cohort=lapply(split(d[[o$dose]][d[[o$cohort]]!=0],d[[o$cohort]][d[[o$cohort]]!=0]),range))
  gt_index <- expand.grid(t=ptep$tlist,group=ptep$glist)
  diagnostics$aggregation_weights <- getFromNamespace('overall_weights','ptetools')(
    list(group=gt_index$group,t=gt_index$t,ptep=ptep))
  display_metadata$aggregation_weights <- diagnostics$aggregation_weights
  z <- qnorm(1-ptep$alp/2)
  units <- c(ATT=o$definitions$outcome_unit,ACRT=if(call_args$target_parameter=='slope') s$unit else
    paste(o$definitions$outcome_unit,'per',o$definitions$dose_unit))
  main_target <- if(call_args$target_parameter=='level') 'ATT' else 'ACRT'
  display_metadata$unit <- units[[main_target]]
  cont_rows <- function(terms,estimate,se,critical,unit,curve=TRUE) {
    if(length(terms)!=length(estimate) || length(se)!=length(estimate) || length(critical)!=1L ||
       any(!is.finite(c(estimate,se,critical))) || any(se<0) || critical<=0)
      stop('Official continuous-DID estimates, standard errors or critical values do not match their coordinates')
    out <- data.frame(term=terms,estimate=as.numeric(estimate),se=as.numeric(se),
      ci_low=as.numeric(estimate-critical*se),ci_high=as.numeric(estimate+critical*se),
      pointwise_ci_low=as.numeric(estimate-z*se),pointwise_ci_high=as.numeric(estimate+z*se),
      critical_value=as.numeric(critical),pointwise_critical_value=z,unit=unit)
    if(curve && isTRUE(ptep$cband)) {
      out$uniform_ci_low <- out$ci_low; out$uniform_ci_high <- out$ci_high
    }
    out
  }
  if(dose_aggregation) {
    if(!length(fit$dose) || any(!is.finite(fit$dose))) stop('Official continuous-DID dose coordinates are missing')
    for(target in c('ATT','ACRT')) {
      stem <- paste0(tolower(target),'.d')
      curve <- cont_rows(paste0(target,'.dose.',seq_along(fit$dose)),fit[[stem]],fit[[paste0(stem,'_se')]],
        fit[[paste0(stem,'_crit.val')]],units[[target]])
      curve$dose <- as.numeric(fit$dose); curve$component <- target
      curve$identification_condition <- if(target=='ATT') 'PT-MP' else 'SPT-MP'
      extra_displays[[paste0('dose_',tolower(target))]] <- list(kind='dose-response',rows=curve,
        display=list(plot_type='line',x='dose',y='estimate'),metadata=list(unit=units[[target]],
          target_parameter=if(target=='ATT') 'level' else 'slope',estimand=paste0(target,'(d)'),
          primary_quantity='curve',interval_type=if(isTRUE(ptep$cband)) 'simultaneous' else 'pointwise',
          band_family=paste0(target,'(d) across its saved dose coordinates'),
          critical_value=as.numeric(fit[[paste0(stem,'_crit.val')]])))
    }
    overall <- rbind(cont_rows('overall_ATT',fit$overall_att,fit$overall_att_se,z,units[['ATT']],FALSE),
      cont_rows('overall_ACRT',fit$overall_acrt,fit$overall_acrt_se,z,units[['ACRT']],FALSE))
    overall$component <- c('ATT','ACRT')
    overall$identification_condition <- c('PT-MP','SPT-MP')
    overall$aggregation <- 'cohort-weighted post-treatment average'
    estimates <- extra_displays[[paste0('dose_',tolower(main_target))]]$rows
    display_metadata$critical_value <- as.numeric(fit[[paste0(tolower(main_target),'.d_crit.val')]])
    diagnostics$evaluation_grid <- if(call_args$dose_est_method=='cck') 'native sorted observed treated doses; npiv X.grid selects the basis' else 'native pte_params.dvals'
    if(call_args$dose_est_method=='cck') diagnostics$cck_settings <- list(npiv_alpha=.05,npiv_boot_num=999L,
      J_x_degree=3L,K_w_degree=3L,knots='quantiles',evaluation='observed treated doses',
      curve_standard_errors='npiv asy.se and deriv.asy.se for the centered outcome')
  } else {
    event <- fit$event_study
    estimates <- cont_rows(paste0(main_target,'.event.',event$egt),event$att.egt,event$se.egt,event$crit.val.egt,units[[main_target]])
    estimates$event_time <- as.numeric(event$egt)
    estimates$role <- ifelse(event$egt<0,'pre_diagnostic',tolower(main_target))
    estimates$component <- main_target
    extra_displays$event_study <- list(kind='event-study',rows=estimates,
      metadata=list(critical_value=as.numeric(event$crit.val.egt),aggregation='eventstudy',
        primary_quantity='curve',interval_type=if(isTRUE(ptep$cband)) 'simultaneous' else 'pointwise',
        band_family='the selected ATT or ACRT curve across its saved event times',
        aggregation_definition='At each event time weight the eligible cohorts by their ever-treated cohort shares'))
    overall <- rbind(cont_rows(paste0('overall_',main_target),fit$overall_att$overall.att,fit$overall_att$overall.se,z,units[[main_target]],FALSE),
      cont_rows(paste0('event_average_',main_target),event$overall.att,event$overall.se,z,units[[main_target]],FALSE))
    overall$component <- main_target
    overall$aggregation <- c('cohort-weighted post-treatment average','equal-weight average across nonnegative event times')
    diagnostics$group_time <- fit$att_gt[c('group','t','att','se','crit_val','n','W','Wpval')]
    diagnostics$aggregation_weights <- getFromNamespace('overall_weights','ptetools')(fit$att_gt)
    display_metadata$aggregation_weights <- diagnostics$aggregation_weights
    display_metadata$critical_value <- as.numeric(event$crit.val.egt)
    display_metadata$event_time_definition <- 'native event_study.egt; negative times are varying-base pretreatment diagnostics'
    display_metadata$aggregation_definition <- extra_displays$event_study$metadata$aggregation_definition
  }
  extra_displays$overall_effects <- list(kind='table',rows=overall,metadata=list(
    interval_type='pointwise',band_family='each scalar aggregate',critical_value=z,
    estimand='Official overall effects with their distinct population and period aggregations'))
  if(identical(o$quantity,'overall')) {
    estimates <- overall[overall$term==paste0('overall_',main_target),,drop=FALSE]
    kind <- 'coefficient'; display_metadata$interval_type <- 'pointwise'; display_metadata$critical_value <- z
    display_metadata$band_family <- 'the selected scalar overall effect'
    display_metadata$aggregation_definition <- diagnostics$aggregation_definition
  }
} else if(method=='bunching') {
  terms <- c('B','b','e','marginal_buncher')
  estimates <- data.frame(term=terms,estimate=as.numeric(unlist(fit[terms])),
    se=as.numeric(unlist(fit[paste0(terms,'_sd')])),
    unit=c('observations','bin multiples','elasticity',o$definitions$running_unit))
  if(any(!is.finite(estimates$estimate)) || any(!is.finite(estimates$se))) stop('bunchit returned nonfinite estimates or bootstrap standard deviations')
  diagnostics$input_ids <- I(as.character(ids))
  diagnostics$observations <- sum(fit$data$freq_orig)
  diagnostics$bin_count <- nrow(fit$data)
  diagnostics$sample_mapping <- 'Official bunchit exports binned counts and no fitted raw-row identifiers'
  diagnostics$binned_data <- fit$data
  diagnostics$counterfactual_counts <- I(fit$cf)
  diagnostics$bootstrap_draws <- fit[paste0(terms,'_vector')]
  diagnostics$rounding_digits <- 9L
  density_rows <- rbind(data.frame(x=fit$data$bin,estimate=fit$data$freq_orig,component='observed'),
    data.frame(x=fit$data$bin,estimate=fit$cf,component='counterfactual'))
  extra_displays$bunching_density <- list(kind='distribution',rows=density_rows,
    display=list(plot_type='line',x='x',y='estimate',series='component'),
    metadata=list(unit='observations per bin',outcome_unit=o$definitions$running_unit,cutoff=call_args$zstar,
      binwidth=call_args$binwidth,estimand='Observed bin counts and fitted counterfactual counts',
      interval_type='none',confidence_level=NULL))
  extra_displays$bunching_summary <- list(kind='table',rows=estimates,
    metadata=list(estimand='Official excess mass, normalized mass, elasticity and marginal buncher',interval_type='none',confidence_level=NULL))
  ids <- character()
} else if(method=='marginaleffects') {
  tab <- as.data.frame(fit)
  if(!nrow(tab) || !'estimate' %in% names(tab) || any(!is.finite(tab$estimate))) stop('Official post-estimation returned no finite requested quantities')
  evaluation_data <- as.data.frame(marginaleffects::components(fit,'newdata'))
  padding <- if('rowid' %in% names(evaluation_data)) evaluation_data$rowid < 0 else rep(FALSE,nrow(evaluation_data))
  diagnostics$padding_row_ids <- I(evaluation_data$rowid[padding])
  evaluation_data <- evaluation_data[!padding,,drop=FALSE]
  evaluation_weights <- evaluation_data[['marginaleffects_wts_internal']]
  if(is.null(evaluation_weights)) evaluation_weights <- rep(1,nrow(evaluation_data))
  if(length(evaluation_weights)!=nrow(evaluation_data)) stop('Official evaluation weights do not match the processed evaluation rows')
  evaluation_row <- if('rowidcf' %in% names(evaluation_data)) evaluation_data$rowidcf else evaluation_data$rowid
  evaluation_row_ids <- as.character(ids[evaluation_row])
  effective_by <- marginaleffects::components(fit,'by')
  by_columns <- if(is.character(effective_by)) intersect(effective_by,names(evaluation_data)) else character()
  weight_groups <- data.frame(evaluation_rows=nrow(evaluation_data),weight_sum=sum(evaluation_weights))
  if(length(by_columns)) {
    groups <- unique(evaluation_data[,by_columns,drop=FALSE])
    weight_groups <- do.call(rbind,lapply(seq_len(nrow(groups)),function(j) {
      use <- rep(TRUE,nrow(evaluation_data))
      for(k in by_columns) use <- use & if(is.na(groups[j,k])) is.na(evaluation_data[[k]]) else
        !is.na(evaluation_data[[k]]) & evaluation_data[[k]]==groups[j,k]
      cbind(groups[j,,drop=FALSE],evaluation_rows=sum(use),weight_sum=sum(evaluation_weights[use]))
    }))
  }
  estimates <- tab
  names(estimates)[names(estimates)=='std.error'] <- 'se'
  names(estimates)[names(estimates)=='p.value'] <- 'p_value'
  names(estimates)[names(estimates)=='conf.low'] <- 'ci_low'
  names(estimates)[names(estimates)=='conf.high'] <- 'ci_high'
  if('term' %in% names(estimates)) estimates$variable <- estimates$term
  estimates$term <- paste0(o[["function"]],'.',seq_len(nrow(estimates)))
  if('rowid' %in% names(estimates)) {
    estimates$observation_id <- evaluation_row_ids[match(estimates$rowid,evaluation_data$rowid)]
  }
  estimates$unit <- s$unit
  diagnostics$observations <- length(ids)
  diagnostics$evaluation_data <- evaluation_data
  diagnostics$evaluation_row_ids <- I(evaluation_row_ids)
  diagnostics$processed_evaluation_rows <- nrow(evaluation_data)
  diagnostics$evaluation_weights <- I(as.numeric(evaluation_weights))
  diagnostics$evaluation_weight_sum <- sum(diagnostics$evaluation_weights)
  diagnostics$evaluation_weight_groups <- weight_groups
  display_metadata$averaging <- if(length(by_columns)) 'within by groups' else if(startsWith(o[["function"]],'avg_')) 'average' else 'individual'
  display_metadata$averaging_weights <- list(argument=call_args$wts,sum=diagnostics$evaluation_weight_sum,
    by=effective_by,groups=weight_groups)
  display_metadata$reference_df <- if(is.null(call_args$df)) 'Inf' else call_args$df
} else if(qte_method) {
  if(method %in% c('qte','qtt')) {
    estimates <- data.frame(term=paste0('q',fit$probs),quantile=fit$probs,estimate=fit$qte,
      se=fit$qte.se,ci_low=fit$qte.lower,ci_high=fit$qte.upper,unit=s$unit)
    F0 <- fit$F.treated.t.cf; F1 <- fit$F.treated.t
    display_metadata$distribution_representation <- 'native unc_qte ECDF of potential-outcome quantiles on the requested probs grid'
    diagnostics$average_effect <- list(estimate=fit$ate,se=fit$ate.se,ci_low=fit$ate.lower,ci_high=fit$ate.upper,
      target=if(method=='qte') 'ATE' else 'ATT',unit=s$unit)
  } else {
    tab <- fit[[display_metadata$aggregation]]
    if(is.null(tab) || !nrow(tab)) stop('The selected official QTT aggregation returned no estimates')
    band <- if(isTRUE(call_args$cband)) 'ub' else 'pw'
    estimates <- data.frame(term=paste0('q',tab$probs),quantile=tab$probs,estimate=tab$qtt,se=tab$se,
      ci_low=tab[[paste0('lower_',band)]],ci_high=tab[[paste0('upper_',band)]],unit=s$unit)
    if('e' %in% names(tab)) { estimates$event_time <- tab$e; estimates$component <- paste0('event_',tab$e) }
    if('group' %in% names(tab)) { estimates$cohort <- tab$group; estimates$component <- paste0('cohort_',tab$group) }
    if('component' %in% names(estimates)) estimates$term <- paste(estimates$component,estimates$term,sep='.')
    F0 <- fit$F0_overall; F1 <- fit$F1_overall
    diagnostics$excluded_engine_ids <- I(setdiff(ids,fit$ptep$data$.ers_qte_row_id))
    ids <- as.character(fit$ptep$data$.ers_qte_row_id)
    d <- d[match(ids,d$.ers_qte_row_id),,drop=FALSE]
    diagnostics$aggregation_parameters <- fit$ptep[c('groups','time.periods','original_groups','original_time.periods','probs','panel','weightsname','control_group','anticipation')]
    display_metadata$distribution_representation <- 'official aggregate F0/F1 from ptetools::qtt_pte_aggregations'
  }
  if(any(!is.finite(as.matrix(estimates[,c('estimate','se','ci_low','ci_high')])))) stop('Official quantile inference returned nonfinite values')
  diagnostics$observations <- length(ids)
  grid <- o$distribution_grid
  if(is.null(grid)) grid <- sort(unique(c(knots(F0),knots(F1))))
  distribution_rows <- rbind(data.frame(x=grid,estimate=F0(grid),component='counterfactual_untreated',unit='probability'),
    data.frame(x=grid,estimate=F1(grid),component='treated',unit='probability'))
  distribution_name <- if(cross_section) 'quantile_grid_distribution' else 'counterfactual_distribution'
  extra_displays[[distribution_name]] <- list(kind='distribution',rows=distribution_rows,
    display=list(plot_type='ecdf',x='x',y='estimate',series='component'),metadata=list(
      unit='probability',outcome_unit=s$unit,distribution_type='ecdf',aggregation='overall',
      estimand=if(cross_section) 'ECDFs of the official potential-outcome quantile-grid values' else
        'Marginal treated and counterfactual untreated outcome CDFs for the overall target population',
      distribution_representation=display_metadata$distribution_representation,interval_type='none',
      confidence_level=NULL,outcome=s$outcome))
} else if(method %in% c('ols_r','fixest_ols','fixest_ppml','negative_binomial_r','sunab','did2s')) {
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
} else if(grf_method) {
  predictions <- predict(fit,estimate.variance=TRUE)
  critical_value <- qnorm((1+confidence_level)/2)
  binary_treatment <- is.numeric(fit$W.orig) && all(fit$W.orig %in% c(0,1))
  outcome_unit <- if(method=='grf_survival' && fit$target=='survival.probability' && binary_treatment) 'probability difference' else s$unit
  if(method=='grf_multi_arm') {
    conditional_rows <- do.call(rbind,lapply(seq_len(length(levels(fit$W.orig))-1L),function(j)
      data.frame(id=ids,contrast=dimnames(predictions$predictions)[[2]][j],
        estimate=predictions$predictions[,j,1],variance=predictions$variance.estimates[,j],stringsAsFactors=FALSE)))
  } else {
    conditional_rows <- data.frame(id=ids,estimate=predictions$predictions,variance=predictions$variance.estimates)
  }
  if(any(!is.finite(conditional_rows$estimate)) || any(!is.finite(conditional_rows$variance)) || any(conditional_rows$variance<0))
    stop('GRF returned nonfinite conditional effects or invalid pointwise variances')
  conditional_rows$se <- sqrt(conditional_rows$variance)
  conditional_rows$ci_low <- conditional_rows$estimate-critical_value*conditional_rows$se
  conditional_rows$ci_high <- conditional_rows$estimate+critical_value*conditional_rows$se
  conditional_rows$unit <- outcome_unit
  if(method=='grf') diagnostics$cate <- conditional_rows else diagnostics$conditional_effects <- conditional_rows
  diagnostics$observations <- nrow(fit$X.orig)
  diagnostics$n_clusters <- if(length(fit$clusters)) length(unique(fit$clusters)) else NULL
  observation_weights <- getFromNamespace('observation_weights','grf')(fit)
  if(grf_quantity=='average') {
    ate <- invoke(grf::average_treatment_effect,c(list(forest=fit),aggregate_args))
    if(method=='grf_multi_arm') {
      estimates <- data.frame(term=ate$contrast,contrast=ate$contrast,estimate=ate$estimate,se=ate$std.err)
    } else {
      term <- switch(method,grf='target_ate',grf_instrumental=if(o$definitions$iv_estimand=='conditional_late') 'target_aclate' else 'target_average_iv_ratio',
        grf_survival=if(fit$target=='RMST') 'target_rmst' else 'target_survival_probability')
      estimates <- data.frame(term=term,estimate=unname(ate[1]),se=unname(ate[2]))
    }
    estimates$p_value <- 2*pnorm(-abs(estimates$estimate/estimates$se))
    estimates$ci_low <- estimates$estimate-critical_value*estimates$se
    estimates$ci_high <- estimates$estimate+critical_value*estimates$se
    estimates$unit <- outcome_unit
    if(nrow(estimates)==1L) covariance <- matrix(estimates$se^2,1,1,dimnames=list(estimates$term,estimates$term))
    aggregate_rows <- getFromNamespace('validate_subset','grf')(fit,aggregate_args$subset)
    target_rows <- switch(aggregate_args$target.sample,
      treated=aggregate_rows[fit$W.orig[aggregate_rows]==1],
      control=aggregate_rows[fit$W.orig[aggregate_rows]==0],aggregate_rows)
    diagnostics$aggregation <- list(arguments=aggregate_args,subset_ids=I(ids[aggregate_rows]),
      target_ids=I(ids[target_rows]),observation_weights=I(observation_weights),
      weights_ids_ref='sample.included_ids',weights_definition='normalized observation weights before target.sample and score-specific weighting')
    display_metadata$aggregation <- aggregate_args
    display_metadata$aggregation_target <- aggregate_args$target.sample
    display_metadata$inference_function <- 'grf::average_treatment_effect'
  } else {
    estimates <- conditional_rows
    estimates$term <- paste0('conditional_effect[',seq_len(nrow(estimates)),']')
    estimates$p_value <- 2*pnorm(-abs(estimates$estimate/estimates$se))
    display_metadata$inference_function <- paste0('grf::predict.',fname)
  }
  if(any(!is.finite(estimates$estimate)) || any(!is.finite(estimates$se)) || any(estimates$se<0))
    stop('GRF returned nonfinite requested estimates or invalid standard errors')
  effect_target <- switch(method,
    grf=if(binary_treatment) 'E[Y(1)-Y(0) | X=x]' else 'Cov[Y,W | X=x] / Var[W | X=x]',
    grf_instrumental='Cov[Y,Z | X=x] / Cov[W,Z | X=x]',
    grf_multi_arm='E[Y(arm)-Y(reference) | X=x]',
    grf_survival=if(fit$target=='RMST') {
      if(binary_treatment) 'E[min(T(1),horizon)-min(T(0),horizon) | X=x]' else 'Cov[min(T,horizon),W | X=x] / Var[W | X=x]'
    } else if(binary_treatment) 'P[T(1)>horizon | X=x]-P[T(0)>horizon | X=x]' else 'Cov[1{T>horizon},W | X=x] / Var[W | X=x]')
  inference_unit <- if(!is.null(o$definitions$inference_unit)) o$definitions$inference_unit else if(!is.null(o$columns$clusters)) o$columns$clusters else if(length(fit$clusters)) 'native cluster partition' else s$id
  heterogeneity <- list(forest=fname,quantity=grf_quantity,conditional_target=effect_target,
    target=if(grf_quantity=='conditional') effect_target else if(method=='grf_instrumental') {
      if(o$definitions$iv_estimand=='conditional_late') 'E_X[tau(X)] over the declared covariate population (ACLATE)' else 'Average conditional IV covariance ratio over the declared covariate population'
    } else if(method=='grf') switch(aggregate_args$target.sample,
      all=if(binary_treatment) 'ATE over the declared population' else 'Average conditional covariance-to-variance slope',
      treated='ATT over treated units',control='ATC over control units',
      overlap=if(binary_treatment) 'Overlap-weighted average effect' else 'Conditional variance-weighted average slope from the residualized linear projection') else 'Average of the conditional target over the declared population',
    treatment=list(column=o$treatment,type=if(method=='grf_multi_arm') 'multi_arm' else if(binary_treatment) 'binary' else 'continuous',
      arms=if(method=='grf_multi_arm') I(levels(fit$W.orig)) else NULL,
      reference_arm=if(method=='grf_multi_arm') levels(fit$W.orig)[1] else if(binary_treatment) 0 else NULL,
      contrasts=if(method=='grf_multi_arm') I(dimnames(predictions$predictions)[[2]]) else NULL),
    outcome=s$outcome,population=s$population,period=s$period,unit=outcome_unit,
    inference=list(unit=inference_unit,cluster_columns=o$columns$clusters,n_clusters=diagnostics$n_clusters,
      confidence_level=confidence_level,interval_family='pointwise',reference_distribution='standard_normal'),
    prediction=list(sample='out-of-bag training observations',ids_ref='sample.included_ids',
      rows_ref=if(method=='grf') 'diagnostics.cate' else 'diagnostics.conditional_effects',
      variance='official pointwise prediction variance',joint_covariance_available=FALSE),
    aggregation=if(grf_quantity=='average') list(arguments=aggregate_args,
      subset_ids_ref='diagnostics.aggregation.subset_ids',target_ids_ref='diagnostics.aggregation.target_ids',
      inference_function='grf::average_treatment_effect',joint_covariance_available=!is.null(covariance)) else NULL,
    weights=list(sample_weights_column=o$columns$sample.weights,equalize_cluster_weights=fit$equalize.cluster.weights,
      normalization='native observation_weights normalized over the fitted observations; target-specific score weights applied by average_treatment_effect',
      observation_weights=I(observation_weights),ids_ref='sample.included_ids'),
    identification=s$identification,conditions=o$definitions$conditions)
  if(method=='grf_instrumental') heterogeneity$instrumental <- list(instrument=o$instrument,
    estimand=o$definitions$iv_estimand,compliance_population=o$definitions$compliance_population,
    aggregation_population='Covariate population weighted by native observation weights; the conditional IV target is averaged over X',
    compliance_score=aggregate_args$compliance.score,
    score_weights_source=if(!is.null(aggregate_args$debiasing.weights)) 'supplied debiasing.weights' else if(!is.null(aggregate_args$compliance.score)) 'supplied compliance.score' else 'native compliance forest in grf::get_scores',
    identifying_conditions='Instrument relevance, exclusion and conditional exogeneity; binary conditional LATE additionally requires monotonicity')
  if(method=='grf_survival') heterogeneity$survival <- list(outcome=s$outcome,status=o$status,
    event_coding=list(censored=0,event=1),target=fit$target,horizon=fit$horizon,time_unit=o$definitions$time_unit,
    censoring=o$definitions$censoring,identifying_conditions='Conditional treatment exchangeability and overlap; independent right censoring given X and W with follow-up support through the adopted horizon',
    failure_times=call_args$failure.times)
  diagnostics$effective_options <- list(equalize.cluster.weights=fit$equalize.cluster.weights,
    seed=fit$seed,num.threads=fit$num.threads,tunable.params=fit$tunable.params)
  display_metadata$heterogeneity <- heterogeneity
  display_metadata$unit <- outcome_unit
  display_metadata$inference_unit <- inference_unit
  display_metadata$cluster_columns <- o$columns$clusters
  display_metadata$equalize_cluster_weights <- fit$equalize.cluster.weights
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
  if(!is.null(fit$save_sample) && all(c(s$id,'did_sample') %in% names(fit$save_sample))) ids <- as.character(fit$save_sample[[s$id]][!is.na(fit$save_sample[['did_sample']])])
  parts <- if(!is.null(fit$results)) list(overall=fit) else fit[startsWith(names(fit),'by_level_')]
  if(!length(parts)) stop('The official treatment-path result contains no saved effect groups')
  tables <- lapply(names(parts),function(group_name) {
    part <- parts[[group_name]]
    effect <- as.data.frame(part$results$Effects,check.names=FALSE)
    names(effect) <- make.names(names(effect),unique=TRUE)
    if(!all(c('Estimate','SE','LB.CI','UB.CI') %in% names(effect))) stop('Unsupported DIDmultiplegtDYN effect-table interface')
    out <- data.frame(term=paste0(group_name,':Effect_',seq_len(nrow(effect))),
      estimate=effect$Estimate,se=effect$SE,ci_low=effect$LB.CI,ci_high=effect$UB.CI,
      event_time=seq_len(nrow(effect))-1L,role='att',group=group_name)
    if('Switchers' %in% names(effect)) out$population_count <- effect$Switchers
    placebo <- as.data.frame(part$results$Placebos,check.names=FALSE)
    names(placebo) <- make.names(names(placebo),unique=TRUE)
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
if(method=='bunching') native_record$ids <- diagnostics$input_ids
if(method=='marginaleffects') native_record <- list(fit=fit_source,data=model_data,ids=model_ids)
if(method=='iv_ar_robust') native_record$stages <- stage_fit
native <- serialize(native_record,NULL,version=3)
if(method=='continuous_did' && !is.null(o$plot)) {
  saved_fit <- unserialize(native)$fit
  official_plot <- contdid::ggcont_did(saved_fit,type=tolower(main_target))
  x_label <- if(dose_aggregation) paste0('Dose [',o$definitions$dose_unit,']') else 'Event time'
  y_label <- paste0(main_target,if(dose_aggregation) '(d)' else '(e)',' [',units[[main_target]],']')
  official_plot <- official_plot + ggplot2::labs(x=x_label,y=y_label)
  official_plot <- official_plot + ggplot2::scale_x_continuous(name=x_label) + ggplot2::scale_y_continuous(name=y_label)
  ggplot2::ggsave(filename=args[7],plot=official_plot,
    width=if(is.null(o$plot$width)) 7 else o$plot$width,
    height=if(is.null(o$plot$height)) 4.5 else o$plot$height,
    dpi=if(is.null(o$plot$dpi)) 160 else o$plot$dpi,units='in')
}
clean <- function(x) {
  if(is.null(x)) return(x)
  if(is.atomic(x)) return(if(is.numeric(x) && is.object(x) && !inherits(x,c('Date','POSIXt','difftime'))) unclass(x) else x)
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
if(grf_method) obj$heterogeneity <- heterogeneity
if(method=='nonabs_did') obj$versions[[underlying[[1]]]] <- as.character(packageVersion(underlying[[1]]))
if(uses_polars) obj$versions$polars <- as.character(packageVersion('polars'))
if(method=='wild_cluster_bootstrap') obj$versions$dqrng <- as.character(packageVersion('dqrng'))
if(method=='iv_ar_robust') obj$versions$lfe <- as.character(packageVersion('lfe'))
if(method=='heckman') {
  for(dependency in c('miscTools','systemfit','Formula','VGAM','mvtnorm','maxLik'))
    obj$versions[[dependency]] <- as.character(packageVersion(dependency))
  obj$effective_options$bindings <- list(selection=display_metadata$selection_equation,outcome=display_metadata$outcome_equation,
    estimation_method=o$estimation_method,type=2L,maxMethod='Newton-Raphson',weights='none')
  obj$diagnostics$selection_signature <- names(formals(sampleSelection::selection))
}
table_path <- if(postprocess) {
  if(method=='marginaleffects') args[6] else ''
} else args[2]
if(tolower(tools::file_ext(table_path)) %in% c('parquet','arrow','feather','ipc'))
  obj$versions$arrow <- as.character(packageVersion('arrow'))
if(method=='bunching') for(dependency in c('BB','dplyr','tidyr','ggplot2')) obj$versions[[dependency]] <- as.character(packageVersion(dependency))
if(qte_method) obj$versions$ptetools <- as.character(packageVersion('ptetools'))
if(method=='continuous_did') {
  for(dependency in c('ptetools','npiv','BMisc','splines2','sandwich','ggplot2','checkmate','MASS','Matrix'))
    obj$versions[[dependency]] <- as.character(packageVersion(dependency))
  obj$effective_options$args$xformula <- '~1'
  obj$effective_options$bindings <- list(yname=s$outcome,dname=o$dose,gname=o$cohort,tname=o$time,idname=o$entity)
  obj$effective_options$inference <- list(bstrap=TRUE,boot_type='multiplier',
    independent_unit=o$entity,bootstrap_repetitions=diagnostics$bootstrap_repetitions)
}
obj$confidence_level <- if(method=='rdrobust_r' && !is.null(call_args$level)) call_args$level/100 else if(method=='wild_cluster_bootstrap' && !is.null(call_args$sign_level)) 1-call_args$sign_level else if(method=='honest_did' && !is.null(call_args$alpha)) 1-call_args$alpha else confidence_level
if(method=='bunching') obj['confidence_level'] <- list(NULL)
write_json(obj,args[5],auto_unbox=TRUE,digits=16,na='null',null='null',dataframe='rows')
