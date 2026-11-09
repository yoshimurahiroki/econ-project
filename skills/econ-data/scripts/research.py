#!/usr/bin/env python3
"""Estimate, evaluate or plan an adopted research calculation.

Usage: research.py estimate spec.json -o result.json
The analysis-table path is relative to the specification file; no source URL is fetched.
Covariance defaults to HC1. One-way clustering uses
``"covariance": {"type": "CR1", "cluster": "group_column"}``.
Unsupported specification fields are rejected.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import statsmodels
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_data


def _sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _names(spec, key, *, required=False):
    value = spec.get(key, [])
    if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value):
        raise ValueError(f"{key} must be a list of column names")
    if len(set(value)) != len(value) or (required and not value):
        raise ValueError(f"{key} must contain {'at least one distinct name' if required else 'distinct names'}")
    return value


def _ols_options(groups):
    if groups is None:
        return {"cov_type": "HC1"}
    return {"cov_type": "cluster", "cov_kwds": {"groups": groups, "use_correction": True,
                                                 "df_correction": True}, "use_t": True}


def estimate(spec, *, spec_path):
    """Fit the specified complete-case sample using the selected specialist engine."""
    if isinstance(spec, dict) and 'data_record' in spec:
        return research_data.execute_with_data_record(estimate, spec, spec_path)
    if not isinstance(spec, dict):
        raise TypeError("specification must be an object")
    accepted = {"method", "data", "id", "outcome", "population", "period", "unit", "sources",
                "exog", "endog", "instruments", "sample_columns", "constant", "filters",
                "require_versions", "question", "identification", "covariance"}
    unknown = set(spec) - accepted
    if unknown:
        raise ValueError(f"unsupported specification fields: {', '.join(sorted(unknown))}")
    covariance_spec = spec.get("covariance", {"type": "HC1"})
    if not isinstance(covariance_spec, dict) or covariance_spec.get("type") not in ("HC1", "CR1"):
        raise ValueError("covariance must specify type HC1 or CR1")
    cov_type = covariance_spec["type"]
    valid_cov_keys = {"type"} if cov_type == "HC1" else {"type", "cluster"}
    if set(covariance_spec) != valid_cov_keys:
        raise ValueError("HC1 accepts only type; CR1 requires only type and cluster")
    cluster_column = covariance_spec.get("cluster")
    if cov_type == "CR1" and (not isinstance(cluster_column, str) or not cluster_column.strip()):
        raise ValueError("CR1 cluster must name a column")
    method = spec.get("method")
    if method not in ("ols", "iv2sls"):
        raise ValueError("method must be ols or iv2sls")
    for field in ("data", "id", "outcome", "population", "period", "unit"):
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            raise ValueError(f"{field} must be a nonempty string")
    if not isinstance(spec.get("sources"), list) or not spec["sources"] or any(
        not isinstance(s, dict) or not (s.get("url") or s.get("path") or s.get("description")) for s in spec["sources"]
    ):
        raise ValueError("sources must contain source records with a URL, path, or description")
    exog = _names(spec, "exog")
    endog = _names(spec, "endog", required=method == "iv2sls")
    instruments = _names(spec, "instruments", required=method == "iv2sls")
    # sample_columns permits exactly the same complete-case sample across models.
    sample_columns = _names(spec, "sample_columns")
    design = exog + endog + instruments
    if len(set(design)) != len(design) or spec["outcome"] in design or spec["id"] in design + [spec["outcome"]]:
        raise ValueError("id, outcome, exog, endog and instruments must have distinct roles")
    if method == "ols" and (endog or instruments):
        raise ValueError("OLS regressors belong in exog; use sample_columns for common-sample exclusions")
    if method == "iv2sls" and len(instruments) < len(endog):
        raise ValueError("IV requires at least as many excluded instruments as endogenous regressors")
    if not isinstance(spec.get("constant", True), bool):
        raise TypeError("constant must be boolean")
    if spec.get("constant", True) and "const" in design:
        raise ValueError("const is reserved for the generated intercept")
    path = Path(spec["data"])
    if not path.is_absolute():
        path = spec_path.parent / path
    path = path.resolve()
    filters = spec.get("filters", [])
    if not isinstance(filters, list):
        raise TypeError("filters must be a list")
    for f in filters:
        if (not isinstance(f, dict) or set(f) != {"column", "op", "value"}
                or not isinstance(f["column"], str) or f["op"] not in ("eq", "ne", "lt", "le", "gt", "ge", "in")):
            raise ValueError("each filter needs column, op (eq/ne/lt/le/gt/ge/in), and value")
    # Model columns are numeric. Additional complete-case fields can be labels.
    columns = list(dict.fromkeys([spec["outcome"], *design]))
    required_columns = [spec["id"], *columns, *sample_columns]
    if cluster_column:
        required_columns.append(cluster_column)
    data = research_data.read_frame(path,
        columns=list(dict.fromkeys(required_columns + [f["column"] for f in filters])),
        string_columns=[spec["id"], *([cluster_column] if cluster_column else [])])
    if (data[spec["id"]].isna().any() or data[spec["id"]].duplicated().any()
            or data[spec["id"]].str.strip().eq("").any()):
        raise ValueError("id values must be nonmissing, nonempty and unique across the input")
    ids = data[spec["id"]]
    eligible = pd.Series(True, index=data.index)
    operators = {"eq": "eq", "ne": "ne", "lt": "lt", "le": "le", "gt": "gt", "ge": "ge"}
    for f in filters:
        s = data[f["column"]]
        if f["op"] == "in":
            if not isinstance(f["value"], list):
                raise ValueError("in filter value must be a list")
            matched = s.isin(f["value"])
        else:
            matched = getattr(s, operators[f["op"]])(f["value"])
        eligible &= matched.fillna(False) & s.notna()
    numeric = data[columns].apply(pd.to_numeric, errors="raise").astype(float)
    complete = pd.Series(np.isfinite(numeric.to_numpy(dtype=float)).all(axis=1), index=data.index)
    for column in set(sample_columns) - set(columns) - {cluster_column}:
        values = data[column]
        labels = values.astype("string").str.strip()
        present = values.notna() & labels.ne("").fillna(False)
        parsed = pd.to_numeric(values.where(present), errors="coerce")
        # Purely numeric fields must also be finite; categorical labels need
        # only be present. This does not encode them as model regressors.
        if parsed[present].notna().all():
            complete &= present & pd.Series(np.isfinite(parsed.to_numpy(dtype=float)), index=data.index)
        else:
            complete &= present
    cluster_complete = (data[cluster_column].notna() & data[cluster_column].str.strip().ne("")
                        if cluster_column else pd.Series(True, index=data.index))
    selected = eligible & complete & cluster_complete
    frame = numeric.loc[selected]
    if frame.empty:
        raise ValueError("no complete observations satisfy the sample rules")
    x = frame[exog].copy()
    if spec.get("constant", True):
        x.insert(0, "const", 1.0)
    regressors = pd.concat([x, frame[endog]], axis=1)
    if not regressors.shape[1]:
        raise ValueError("supply at least one regressor or an intercept")
    if len(frame) <= regressors.shape[1] or np.linalg.matrix_rank(regressors.to_numpy()) < regressors.shape[1]:
        raise ValueError("regressor matrix must have full column rank and residual degrees of freedom")
    cluster_info = None
    groups = None
    if cluster_column:
        labels = data.loc[selected, cluster_column]
        groups, levels = pd.factorize(labels, sort=False)
        group_count = len(levels)
        if group_count < 2:
            raise ValueError("clustered covariance requires at least two fitted clusters")
        cluster_info = {"column": cluster_column, "groups": group_count,
                        "assignments": [{"id": str(i), "cluster": str(g)}
                                        for i, g in zip(ids[selected], labels)]}
    versions = {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__,
                "scipy": scipy.__version__, "statsmodels": statsmodels.__version__}
    if method == "ols":
        fit = sm.OLS(frame[spec["outcome"]], x).fit(**_ols_options(groups))
        covariance = "CR1" if cluster_column else "HC1"
        inference = ({"reference": "Student t", "degrees_of_freedom": group_count - 1}
                     if cluster_column else {"reference": "normal", "degrees_of_freedom": None})
        diagnostics = None
    else:
        import linearmodels
        from linearmodels.iv import IV2SLS
        versions["linearmodels"] = linearmodels.__version__
        iv_options = ({"cov_type": "clustered", "clusters": groups, "debiased": True}
                      if cluster_column else {"cov_type": "robust", "debiased": True})
        fit = IV2SLS(frame[spec["outcome"]], x if len(x.columns) else None,
                     frame[endog], frame[instruments]).fit(**iv_options)
        covariance = "CR1" if cluster_column else "heteroskedastic robust, debiased"
        # linearmodels' debiased coefficient reference uses residual df even for clusters.
        inference = {"reference": "Student t", "degrees_of_freedom": int(fit.df_resid)}
        diagnostics = fit.first_stage.diagnostics.to_dict(orient="index")
        # The package reports robust first-stage Wald chi-square statistics.
        # Also report the finite-df F form from the identical HC1 first stage.
        first_x = pd.concat([x, frame[instruments]], axis=1)
        restrictions = np.zeros((len(instruments), len(first_x.columns)))
        restrictions[:, -len(instruments):] = np.eye(len(instruments))
        for name in endog:
            test = sm.OLS(frame[name], first_x).fit(**_ols_options(groups)).f_test(restrictions)
            diagnostics[name]["excluded_instrument_wald_f"] = {
                "statistic": float(test.fvalue), "pvalue": float(test.pvalue),
                "df_numerator": int(test.df_num), "df_denominator": int(test.df_denom),
                "covariance": cov_type}
    expected = spec.get("require_versions", {})
    if not isinstance(expected, dict) or any(versions.get(k) != v for k, v in expected.items()):
        raise ValueError(f"required engine versions do not match installed versions: {versions}")
    sensitivity = {}
    if method == 'ols':
        classical_cov = fit.normalized_cov_params * fit.scale
        sensitivity = {'residual_df':int(fit.df_resid), 'r_squared':float(fit.rsquared),
            'classical_standard_errors':dict(zip(fit.params.index, np.sqrt(np.diag(classical_cov)).tolist())),
            'outcome_variance':float(np.var(frame[spec['outcome']],ddof=1)),
            'sample_ids':ids[selected].tolist(), 'covariance_basis':'classical_ols',
            'terms':{term:{'estimate':float(fit.params[term]),
                'regressor_variance':float(np.var(x[term],ddof=1)),
                'residual_regressor_variance':float(1/fit.normalized_cov_params.loc[term,term]/(len(frame)-1))}
                for term in exog}}
    cov = fit.cov_params() if method == "ols" else fit.cov
    intervals = fit.conf_int(alpha=.05) if method == 'ols' else fit.conf_int(level=.95)
    inference.update(confidence_level=.95,
        confidence_intervals={str(term):[float(row.iloc[0]),float(row.iloc[1])]
                              for term,row in intervals.iterrows()},
        p_values=fit.pvalues.to_dict())
    return {
        "method": method, "engine": "statsmodels.OLS" if method == "ols" else "linearmodels.iv.IV2SLS",
        "versions": versions, "covariance_type": covariance, "inference": inference,
        "coefficients": fit.params.to_dict(), "covariance": cov.to_dict(orient="index"),
        "standard_errors": (fit.bse if method == "ols" else fit.std_errors).to_dict(),
        "first_stage": diagnostics, "diagnostics": {"ols_sensitivity":sensitivity} if sensitivity else {}, "observations": len(frame),
        "sample": {"id_column": spec["id"], "included_ids": ids[selected].tolist(),
                   "excluded_filter_ids": ids[~eligible].tolist(),
                   "excluded_incomplete_ids": ids[eligible & ~(complete & cluster_complete)].tolist(),
                   "excluded_missing_cluster_ids": ids[eligible & ~cluster_complete].tolist(),
                   "complete_case_columns": list(dict.fromkeys([*columns, *sample_columns,
                                                               *([cluster_column] if cluster_column else [])])),
                   "filters": filters, "cluster": cluster_info},
        "inputs": {"data_path": str(path), "data_sha256": _sha(path),
                   "spec_path": str(spec_path.resolve()), "spec_sha256": _sha(spec_path)},
        "definition": {k: spec[k] for k in ("outcome", "population", "period", "unit", "sources",
                                               "question", "identification") if k in spec},
        "design": {"exog": exog, "endog": endog, "instruments": instruments,
                   "constant": spec.get("constant", True)},
    }


def estimate_dml(spec, *, spec_path):
    """Estimate an adopted partially linear or two-period panel DID specification."""
    if isinstance(spec, dict) and 'data_record' in spec:
        return research_data.execute_with_data_record(estimate_dml, spec, spec_path)
    import research_causal
    from sklearn.model_selection import KFold, StratifiedKFold

    allowed = {"method", "data", "id", "outcome", "outcome_pre", "outcome_post", "treatment", "covariates",
               "sample_columns", "filters", "population", "period", "unit", "sources", "question",
               "identification", "dml", "learners", "require_versions"}
    if not isinstance(spec, dict) or set(spec) - allowed:
        raise ValueError("unsupported DoubleML specification fields")
    method = spec.get("method")
    if method not in ("dml_plr", "dml_did"):
        raise ValueError("method must be dml_plr or dml_did")
    for key in ("data", "id", "treatment", "population", "period", "unit"):
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    if not isinstance(spec.get("sources"), list) or not spec["sources"] or any(
        not isinstance(source, dict) or not (source.get("url") or source.get("path") or source.get("description"))
        for source in spec["sources"]
    ):
        raise ValueError("sources must identify input records")
    xcols = _names(spec, "covariates", required=True)
    sample_columns = _names(spec, "sample_columns")
    if method == "dml_plr":
        if "outcome_pre" in spec or "outcome_post" in spec or not isinstance(spec.get("outcome"), str) or not spec["outcome"]:
            raise ValueError("PLR requires one outcome and no panel outcome columns")
        outcomes = [spec["outcome"]]
    else:
        if "outcome" in spec or any(not isinstance(spec.get(k), str) or not spec[k] for k in ("outcome_pre", "outcome_post")):
            raise ValueError("panel DID requires distinct outcome_pre and outcome_post columns")
        outcomes = [spec["outcome_pre"], spec["outcome_post"]]
    roles = [spec["id"], spec["treatment"], *outcomes, *xcols]
    if len(set(roles)) != len(roles):
        raise ValueError("id, outcome, treatment and covariates must have distinct roles")
    dml = spec.get("dml")
    if not isinstance(dml, dict):
        raise TypeError("DML options must be an object")
    needed = {"folds", "seed", "score"} | ({"normalize"} if method == "dml_did" else set())
    if method == "dml_did" and dml.get("score") == "observational":
        needed.add("clipping_threshold")
    if set(dml) != needed:
        raise ValueError("DML options require folds, seed and score; DID requires normalization and observational DID requires clipping")
    if (isinstance(dml["folds"], bool) or not isinstance(dml["folds"], int) or dml["folds"] < 2 or
            isinstance(dml["seed"], bool) or not isinstance(dml["seed"], int) or dml["seed"] < 0):
        raise ValueError("folds must be at least two and seed must be nonnegative integers")
    if method == "dml_plr" and dml["score"] != "partialling out":
        raise ValueError("PLR supports only the explicit partialling out score")
    if method == "dml_did" and (dml["score"] not in ("observational", "experimental") or
            not isinstance(dml["normalize"], bool)):
        raise ValueError("DID requires observational or experimental score and boolean normalize")
    if method == "dml_did" and dml["score"] == "observational" and (
            isinstance(dml["clipping_threshold"], bool) or not isinstance(dml["clipping_threshold"], (float, int))
            or not 0 < dml["clipping_threshold"] < .5):
        raise ValueError("observational DID clipping must be in (0,0.5)")
    learners = spec.get("learners")
    keys = {"outcome", "treatment"} if method == "dml_plr" else ({"outcome", "propensity"} if dml["score"] == "observational" else {"outcome"})
    if not isinstance(learners, dict) or set(learners) != keys:
        raise ValueError(f"learners must specify exactly {', '.join(sorted(keys))}")
    def regression(config):
        if not isinstance(config, dict) or config.get("type") not in ("linear", "ridge"):
            raise ValueError("regression learner must be linear or ridge")
        if config["type"] == "linear" and set(config) == {"type"}:
            return {"type": "linear", "params": {"n_jobs": None}}
        if config["type"] == "ridge" and set(config) == {"type", "alpha"} and not isinstance(config["alpha"], bool) and isinstance(config["alpha"], (int, float)) and np.isfinite(config["alpha"]) and config["alpha"] > 0:
            return {"type": "ridge", "params": {"alpha": float(config["alpha"]), "random_state": None}}
        raise ValueError("linear takes no parameters; ridge requires finite positive alpha")
    learner_names = {"outcome": "ml_l", "treatment": "ml_m"} if method == "dml_plr" else {"outcome": "ml_g"}
    native_learners = {learner_names[name]: regression(learners[name]) for name in learner_names}
    if method == "dml_did" and dml["score"] == "observational":
        config = learners["propensity"]
        if not isinstance(config, dict) or set(config) != {"type", "C", "max_iter"} or config["type"] != "logistic" or isinstance(config["C"], bool) or not isinstance(config["C"], (int,float)) or not np.isfinite(config["C"]) or config["C"] <= 0 or isinstance(config["max_iter"], bool) or not isinstance(config["max_iter"], int) or config["max_iter"] < 1:
            raise ValueError("propensity requires logistic type, positive finite C and positive integer max_iter")
        learner_names["propensity"] = "ml_m"
        native_learners["ml_m"] = {"type": "logistic", "params": {"C": float(config["C"]),
            "max_iter": config["max_iter"], "solver": "lbfgs", "random_state": dml["seed"], "n_jobs": None}}
    path = Path(spec["data"])
    path = (path if path.is_absolute() else spec_path.parent / path).resolve()
    required = list(dict.fromkeys(roles + sample_columns))
    filters = spec.get("filters", [])
    if not isinstance(filters, list):
        raise TypeError("filters must be a list")
    operators = {"eq": "eq", "ne": "ne", "lt": "lt", "le": "le", "gt": "gt", "ge": "ge"}
    for f in filters:
        if (not isinstance(f, dict) or set(f) != {"column", "op", "value"} or
                not isinstance(f["column"], str) or f["op"] not in (*operators, "in")):
            raise ValueError("filter requires a column, supported op, and value")
    data = research_data.read_frame(path,
        columns=list(dict.fromkeys(required + [f["column"] for f in filters])),
        string_columns=[spec["id"]])
    ids = data[spec["id"]]
    if ids.isna().any() or ids.duplicated().any() or ids.str.strip().eq("").any():
        raise ValueError("id values must be nonmissing and unique across the input")
    eligible = pd.Series(True, index=data.index)
    for f in filters:
        series = data[f["column"]]
        if f["op"] == "in":
            if not isinstance(f["value"], list):
                raise ValueError("in filter value must be a list")
            matched = series.isin(f["value"])
        else:
            matched = getattr(series, operators[f["op"]])(f["value"])
        eligible &= matched.fillna(False) & series.notna()
    columns = outcomes + [spec["treatment"], *xcols]
    numeric = data[columns].apply(pd.to_numeric, errors="raise").astype(float)
    complete = pd.Series(np.isfinite(numeric.to_numpy(dtype=float)).all(axis=1), index=data.index)
    for column in set(sample_columns) - set(columns):
        values = data[column]
        present = values.notna() & values.astype("string").str.strip().ne("").fillna(False)
        parsed = pd.to_numeric(values.where(present), errors="coerce")
        complete &= (present & pd.Series(np.isfinite(parsed.to_numpy(dtype=float)), index=data.index)
                     if parsed[present].notna().all() else present)
    selected = eligible & complete
    frame = numeric.loc[selected].reset_index(drop=True)
    selected_ids = ids[selected].tolist()
    if len(frame) < dml["folds"]:
        raise ValueError("fitted sample must contain at least as many observations as folds")
    if method == "dml_did":
        if not set(frame[spec["treatment"]].unique()) == {0, 1}:
            raise ValueError("panel DID treatment must contain both 0 and 1")
        counts = frame[spec["treatment"]].value_counts()
        if counts.min() < dml["folds"]:
            raise ValueError("each DID treatment group must have at least one unit per fold")
        if "_did_change" in frame:
            raise ValueError("_did_change is reserved for panel outcome transformation")
        splitter = StratifiedKFold(n_splits=dml["folds"], shuffle=True, random_state=dml["seed"])
        splits = list(splitter.split(frame[xcols], frame[spec["treatment"]]))
    else:
        splits = list(KFold(n_splits=dml["folds"], shuffle=True, random_state=dml["seed"]).split(frame))
    fold_ids = [{"train_ids": [selected_ids[i] for i in train], "test_ids": [selected_ids[i] for i in test]}
                for train, test in splits]
    options = {"treatment": spec["treatment"], "score": dml["score"], "n_folds": dml["folds"],
               "n_rep": 1, "seed": dml["seed"], "learners": native_learners, "sample_splitting": [fold_ids]}
    if method == "dml_did":
        options.update(outcome_pre=outcomes[0], in_sample_normalization=dml["normalize"])
        if "clipping_threshold" in dml:
            options["clipping_threshold"] = dml["clipping_threshold"]
    frame[spec["id"]] = selected_ids
    estimator, intervals, folds, diagnostics, engine_versions = research_causal._doubleml(
        {"method": method, "id": spec["id"], "outcome": outcomes[-1], "regressors": xcols,
         "endogenous": [], "instruments": [], "options": options}, frame, [], len(data))
    coef, se = float(estimator.coef[0]), float(estimator.se[0])
    if not np.isfinite([coef, se]).all():
        raise ArithmeticError("DoubleML returned nonfinite coefficient or standard error")
    versions = {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__,
                "scipy": scipy.__version__, **engine_versions}
    expected = spec.get("require_versions", {})
    if not isinstance(expected, dict) or any(versions.get(k) != v for k, v in expected.items()):
        raise ValueError(f"required engine versions do not match installed versions: {versions}")
    return {"method": method, "engine": "DoubleMLPLR" if method == "dml_plr" else "DoubleMLDID",
            "versions": versions, "coefficients": {spec["treatment"]: coef}, "standard_errors": {spec["treatment"]: se},
            "covariance": {spec["treatment"]: {spec["treatment"]: se**2}},
            "inference": {"reference": "normal", "pvalue": float(estimator.pval[0]),
                          "confidence_interval_95": intervals.iloc[0].tolist()},
            "observations": len(frame), "sample": {"id_column": spec["id"], "included_ids": selected_ids,
                "excluded_filter_ids": ids[~eligible].tolist(), "excluded_incomplete_ids": ids[eligible & ~complete].tolist(),
                "complete_case_columns": list(dict.fromkeys(columns + sample_columns)), "filters": filters},
            "folds": folds[0], "options": {**dml, "repetitions": 1}, "learners": learners,
            "effective_learners": {name: diagnostics["effective_learners"][native]["params"]
                                   for name, native in learner_names.items()}, "diagnostics": diagnostics,
            "design": {"outcomes": outcomes, "treatment": spec["treatment"], "covariates": xcols,
                       "outcome_transformation": "post minus pre" if method == "dml_did" else "none"},
            "definition": {k: spec[k] for k in ("population", "period", "unit", "sources", "question", "identification") if k in spec},
            "inputs": {"data_path": str(path), "data_sha256": _sha(path), "spec_path": str(spec_path.resolve()),
                       "spec_sha256": _sha(spec_path)}}


def evaluate(spec, *, spec_path):
    """Evaluate one fixed prediction candidate on a frozen data partition."""
    from sklearn import __version__ as sklearn_version
    from sklearn.linear_model import LinearRegression, Ridge
    from sklearn.metrics import mean_squared_error
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    accepted = {"train_data", "evaluation_data", "id", "outcome", "features", "candidate", "partition",
                "identity", "protocol", "population", "period", "unit", "sources", "require_versions"}
    if not isinstance(spec, dict) or set(spec) - accepted:
        raise ValueError("unsupported prediction specification fields")
    for key in ("train_data", "evaluation_data", "id", "outcome", "population", "period", "unit"):
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    if not isinstance(spec.get("sources"), list) or not spec["sources"] or any(
        not isinstance(source, dict) or not (source.get("url") or source.get("path") or source.get("description"))
        for source in spec["sources"]
    ):
        raise ValueError("sources must identify the input data")
    features = _names(spec, "features", required=True)
    if spec["id"] == spec["outcome"] or spec["id"] in features or spec["outcome"] in features:
        raise ValueError("id, outcome and features must have distinct roles")
    candidate = spec.get("candidate")
    if not isinstance(candidate, dict) or candidate.get("method") not in ("ols", "ridge"):
        raise ValueError("candidate method must be ols or ridge")
    method = candidate["method"]
    if set(candidate) != ({"method"} if method == "ols" else {"method", "alpha"}):
        raise ValueError("OLS accepts only method; ridge requires method and alpha")
    if method == "ridge" and (isinstance(candidate["alpha"], bool) or not isinstance(candidate["alpha"], (int, float))
                              or not np.isfinite(candidate["alpha"]) or candidate["alpha"] <= 0):
        raise ValueError("ridge alpha must be finite and positive")
    partition = spec.get("partition")
    if partition not in ("validation", "holdout"):
        raise ValueError("partition must be validation or holdout")
    protocol = spec.get("protocol")
    if not isinstance(protocol, dict) or set(protocol) != {"seed", "train_sha256", "validation_sha256", "holdout_sha256"}:
        raise ValueError("protocol requires seed and train, validation and holdout SHA-256 hashes")
    if isinstance(protocol["seed"], bool) or not isinstance(protocol["seed"], int) or protocol["seed"] < 0:
        raise ValueError("protocol seed must be a nonnegative integer")
    for key in ("train_sha256", "validation_sha256", "holdout_sha256"):
        value = protocol[key]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"{key} must be a lowercase SHA-256 hash")
    if len({protocol[k] for k in ("train_sha256", "validation_sha256", "holdout_sha256")}) != 3:
        raise ValueError("training, validation and holdout data hashes must be distinct")
    identity = spec.get("identity")
    if not isinstance(identity, dict) or set(identity) != {"estimand", "evaluator", "sample"}:
        raise ValueError("identity requires estimand, evaluator and sample")
    if not isinstance(identity["estimand"], str) or not identity["estimand"].strip() or identity["evaluator"] != "mean_squared_error_v1":
        raise ValueError("identity requires an estimand and mean_squared_error_v1 evaluator")
    frozen = {"train_sha256": protocol["train_sha256"], "validation_sha256": protocol["validation_sha256"],
              "id": spec["id"], "outcome": spec["outcome"], "features": features}
    sample_hash = hashlib.sha256(json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if identity["sample"] != sample_hash:
        raise ValueError("sample identity does not match the frozen data and feature contract")
    def local_path(key):
        path = Path(spec[key])
        return (path if path.is_absolute() else spec_path.parent / path).resolve()
    train_path, evaluation_path = local_path("train_data"), local_path("evaluation_data")
    if _sha(train_path) != protocol["train_sha256"] or _sha(evaluation_path) != protocol[partition + "_sha256"]:
        raise ValueError("input data hashes do not match the frozen partition protocol")
    frames = []
    for path in (train_path, evaluation_path):
        frame = research_data.read_frame(path, columns=[spec["id"], spec["outcome"], *features],
                                         string_columns=[spec["id"]])
        ids = frame[spec["id"]]
        if ids.isna().any() or ids.duplicated().any() or ids.str.strip().eq("").any():
            raise ValueError("prediction IDs must be unique and nonmissing")
        numeric = frame[[spec["outcome"], *features]].apply(pd.to_numeric, errors="raise").astype(float)
        if len(frame) == 0 or not np.isfinite(numeric.to_numpy(dtype=float)).all():
            raise ValueError("prediction inputs must contain finite values and observations")
        frames.append((ids, numeric))
    (train_ids, train), (evaluation_ids, evaluation) = frames
    if set(train_ids) & set(evaluation_ids):
        raise ValueError("training and evaluation IDs must be disjoint")
    versions = {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__,
                "scipy": scipy.__version__, "scikit-learn": sklearn_version}
    expected = spec.get("require_versions", {})
    if not isinstance(expected, dict) or any(versions.get(k) != v for k, v in expected.items()):
        raise ValueError(f"required engine versions do not match installed versions: {versions}")
    estimator = LinearRegression() if method == "ols" else Ridge(alpha=float(candidate["alpha"]))
    pipeline = make_pipeline(StandardScaler(), estimator)
    pipeline.fit(train[features], train[spec["outcome"]])
    predicted = pipeline.predict(evaluation[features])
    loss = float(mean_squared_error(evaluation[spec["outcome"]], predicted))
    if not np.isfinite(loss) or not np.isfinite(predicted).all():
        raise ArithmeticError("evaluation produced nonfinite predictions or loss")
    scaler = pipeline.named_steps["standardscaler"]
    return {"identity": {**identity, "partition": partition}, "metrics": {"loss": loss},
            "loss_unit": f"squared {spec['unit']}", "candidate": candidate,
            "engine": "sklearn.pipeline.StandardScaler + " + type(estimator).__name__, "versions": versions,
            "training": {"ids": train_ids.tolist(), "observations": len(train), "sha256": protocol["train_sha256"]},
            "evaluation": {"ids": evaluation_ids.tolist(), "observations": len(evaluation),
                           "sha256": protocol[partition + "_sha256"],
                           "predictions": [{"id": str(i), "observed": float(y), "predicted": float(pred)}
                                           for i, y, pred in zip(evaluation_ids, evaluation[spec["outcome"]], predicted)]},
            "fitted_model": {"features": features, "coefficients_scaled": estimator.coef_.tolist(),
                             "intercept_scaled": float(estimator.intercept_), "scaler_mean": scaler.mean_.tolist(),
                             "scaler_scale": scaler.scale_.tolist(), "estimator_parameters": estimator.get_params(deep=False),
                             "scaler_parameters": scaler.get_params(deep=False)},
            "protocol": protocol, "inputs": {"spec_path": str(spec_path.resolve()), "spec_sha256": _sha(spec_path),
                                               "train_path": str(train_path), "evaluation_path": str(evaluation_path)},
            "definition": {k: spec[k] for k in ("population", "period", "unit", "sources", "outcome")}}


def power(spec, *, spec_path):
    """Plan a two-sided pooled t test and optionally simulate its assignment-unit DGP."""
    from scipy.optimize import brentq
    from scipy.stats import nct, t

    required = {'design', 'n_treatment', 'n_control', 'outcome_sd', 'effect',
                'alpha', 'target_power', 'seed', 'unit'}
    if (not isinstance(spec, dict) or not required <= set(spec)
            or set(spec) - required - {'cluster_size', 'icc', 'replications', 'dgp'}):
        raise ValueError('power requires its two-arm planning fields and supported options')
    design = spec['design']
    if design not in ('individual', 'cluster'):
        raise ValueError('design must be individual or cluster')
    if any(type(spec[key]) is not int or spec[key] < 2 for key in ('n_treatment', 'n_control')):
        raise ValueError('each arm needs at least two independent assignment units')
    if type(spec['seed']) is not int or spec['seed'] < 0:
        raise ValueError('seed must be a nonnegative integer')
    if not isinstance(spec['unit'], str) or not spec['unit'].strip():
        raise ValueError('unit must be a nonempty string')
    spec_bytes = spec_path.read_bytes()
    if json.loads(spec_bytes) != spec:
        raise ValueError('power specification must match its saved source bytes')
    for key in ('outcome_sd', 'effect', 'alpha', 'target_power'):
        if isinstance(spec[key], bool) or not isinstance(spec[key], (int, float)) or not np.isfinite(spec[key]):
            raise ValueError(f'{key} must be finite')
    if spec['outcome_sd'] <= 0 or not 0 < spec['alpha'] < 1 or not spec['alpha'] < spec['target_power'] < 1:
        raise ValueError('outcome_sd must be positive and alpha < target_power < 1')
    if design == 'cluster':
        if (type(spec.get('cluster_size')) is not int or spec['cluster_size'] < 1
                or isinstance(spec.get('icc'), bool) or not isinstance(spec.get('icc'), (int, float))
                or not np.isfinite(spec['icc']) or not 0 <= spec['icc'] <= 1):
            raise ValueError('cluster design requires positive integer cluster_size and icc in [0,1]')
        cluster_size, icc = spec['cluster_size'], float(spec['icc'])
    else:
        if 'cluster_size' in spec or 'icc' in spec:
            raise ValueError('individual design does not accept cluster options')
        cluster_size, icc = 1, 0.
    replications = spec.get('replications')
    if replications is not None and (type(replications) is not int or not 100 <= replications <= 100000):
        raise ValueError('replications must be an integer from 100 to 100000')
    dgp = spec.get('dgp', {})
    if not isinstance(dgp, dict) or set(dgp) - {'icc_true', 'group_shock_sd'}:
        raise ValueError('dgp accepts icc_true and group_shock_sd')
    if 'dgp' in spec and replications is None:
        raise ValueError('dgp sensitivity requires replications')
    if design == 'individual' and 'icc_true' in dgp:
        raise ValueError('icc_true is only defined for cluster design')
    for key in dgp:
        if isinstance(dgp[key], bool) or not isinstance(dgp[key], (int, float)) or not np.isfinite(dgp[key]):
            raise ValueError(f'{key} must be finite')
    true_icc = float(dgp.get('icc_true', icc))
    shock_sd = float(dgp.get('group_shock_sd', 0.))
    if not 0 <= true_icc <= 1 or shock_sd < 0:
        raise ValueError('icc_true must be in [0,1] and group_shock_sd nonnegative')

    nt, nc = spec['n_treatment'], spec['n_control']
    sd = float(spec['outcome_sd'])
    if sd > np.sqrt(np.finfo(float).max):
        raise ValueError('outcome_sd exceeds supported finite numerical precision')
    try:
        inverse_sizes = 1/nt + 1/nc
    except OverflowError as exc:
        raise ValueError('assignment-unit counts exceed supported numerical precision') from exc
    planned_variance = sd**2 * (icc + (1-icc)/cluster_size)
    true_variance = sd**2 * (true_icc + (1-true_icc)/cluster_size)
    se = np.sqrt(planned_variance*inverse_sizes)
    true_sd = np.sqrt(true_variance)
    df = nt + nc - 2
    critical = t.isf(spec['alpha']/2, df)
    if not np.isfinite([planned_variance, true_variance, se, true_sd, critical]).all() or min(se, true_sd) <= 0:
        raise ValueError('inputs exceed supported finite numerical precision')
    if not np.isfinite(float(spec['effect'])/se):
        raise ValueError('effect exceeds supported finite numerical precision')
    def probability(effect):
        noncentrality = effect/se
        return float(nct.sf(critical, df, noncentrality) + nct.cdf(-critical, df, noncentrality))
    analytic = probability(float(spec['effect']))
    upper = float(se)
    while probability(upper) < spec['target_power']:
        upper *= 2
        if not np.isfinite(upper):
            raise ArithmeticError('could not bracket the minimum detectable effect')
    mde = float(brentq(lambda effect: probability(effect)-spec['target_power'], 0., upper,
                       xtol=np.finfo(float).tiny, rtol=1e-12))
    if not np.isfinite([analytic, mde]).all():
        raise ArithmeticError('power calculation produced a nonfinite result')
    statistic = lambda value, unit: {'value': float(value), 'unit': unit}
    statistics = {'planned_standard_error': statistic(se, spec['unit']),
                  'analytic_power': statistic(analytic, 'probability'),
                  'minimum_detectable_effect': statistic(mde, spec['unit']),
                  'degrees_of_freedom': statistic(df, 'assignment units'),
                  'critical_t': statistic(critical, 't statistic')}
    simulation = None
    if replications is not None:
        null_rejections = alternative_rejections = covered = 0
        errors = np.empty(replications)
        for index, child in enumerate(np.random.SeedSequence(spec['seed']).spawn(replications)):
            rng = np.random.Generator(np.random.PCG64(child))
            treated = rng.normal(0., true_sd, nt)
            control = rng.normal(0., true_sd, nc)
            if shock_sd:
                treated += rng.normal(0., shock_sd)
                control += rng.normal(0., shock_sd)
            noise = float(treated.mean() - control.mean())
            pooled = ((nt-1)*treated.var(ddof=1) + (nc-1)*control.var(ddof=1))/df
            fit_se = np.sqrt(pooled*inverse_sizes)
            if not np.isfinite([noise, fit_se]).all() or fit_se <= 0:
                raise ArithmeticError('simulation produced an invalid pooled standard error')
            null_rejections += abs(noise/fit_se) > critical
            alternative_rejections += abs((noise + spec['effect'])/fit_se) > critical
            covered += abs(noise) <= critical*fit_se
            errors[index] = noise
        size, empirical_power, coverage = (count/replications for count in (null_rejections, alternative_rejections, covered))
        bias = float(errors.mean())
        rmse = float(np.sqrt(np.mean(errors**2)))
        probability_mcse = lambda value: float(np.sqrt(value*(1-value)/replications))
        bias_mcse = float(errors.std(ddof=1)/np.sqrt(replications))
        rmse_mcse = float((errors**2).std(ddof=1)/(2*rmse*np.sqrt(replications))) if rmse else 0.
        if not np.isfinite([bias, rmse, bias_mcse, rmse_mcse]).all():
            raise ArithmeticError('simulation produced nonfinite summary statistics')
        statistics.update({'simulation_size': statistic(size, 'probability'),
                           'simulation_power': statistic(empirical_power, 'probability'),
                           'simulation_coverage': statistic(coverage, 'probability'),
                           'simulation_bias': statistic(bias, spec['unit']),
                           'simulation_rmse': statistic(rmse, spec['unit'])})
        simulation = {'replications': replications,
                      'counts': {'null_rejections': int(null_rejections),
                                 'alternative_rejections': int(alternative_rejections), 'covered': int(covered)},
                      'mcse': {'size': probability_mcse(size), 'power': probability_mcse(empirical_power),
                               'coverage': probability_mcse(coverage), 'bias': bias_mcse, 'rmse': rmse_mcse},
                      'seed_protocol': {'seed': spec['seed'], 'generator': 'PCG64',
                          'streams': 'SeedSequence(seed).spawn(replications), one child per replication',
                          'coupling': 'null and alternative use the same assignment-unit innovations and arm shocks'},
                      'realized_dgp': {'icc_true': true_icc if design == 'cluster' else None,
                                       'group_shock_sd': shock_sd,
                                       'independent_assignment_unit_sd': float(true_sd),
                                       'assignment_unit_sd': float(np.hypot(true_sd, shock_sd)),
                                       'arm_shocks_independent': True}}
    return {'method': 'two_arm_pooled_t_power', 'engine': 'SciPy noncentral t and Brent root',
            'design': {'assignment_unit': design, 'n_treatment': nt, 'n_control': nc,
                       'cluster_size': cluster_size if design == 'cluster' else None,
                       'icc': icc if design == 'cluster' else None, 'outcome_sd': sd,
                       'assignment_unit_variance': float(planned_variance), 'effect': float(spec['effect']),
                       'alpha': float(spec['alpha']), 'target_power': float(spec['target_power']),
                       'assumptions': 'independent Gaussian assignment-unit outcomes with equal marginal variance',
                       'scope': 'two-arm difference in means; pooled two-sided t test'},
            'statistics': statistics, 'simulation': simulation,
            'versions': {'python': sys.version.split()[0], 'numpy': np.__version__, 'scipy': scipy.__version__},
            'inputs': {'spec_path': str(spec_path.resolve()), 'spec_sha256': hashlib.sha256(spec_bytes).hexdigest(),
                       'code_sha256': _sha(Path(__file__))}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["estimate", "evaluate", "power"])
    parser.add_argument("spec", type=Path)
    parser.add_argument("-o", "--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        protected = {args.spec.resolve()}
        if args.output.resolve() in protected:
            raise ValueError('output must differ from its specification')
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise TypeError("specification must be an object")
        for key in ('data', 'train_data', 'evaluation_data'):
            if isinstance(spec.get(key), str):
                protected.add((args.spec.parent / spec[key]).resolve())
        reference = spec.get('data_record')
        if isinstance(reference, dict) and isinstance(reference.get('path'), str):
            protected.add((args.spec.parent / reference['path']).resolve())
        if args.output.resolve() in protected:
            raise ValueError('output must differ from input data and construction records')
        operation = ((estimate_dml if spec.get("method") in ("dml_plr", "dml_did") else estimate)
                     if args.operation == "estimate" else evaluate if args.operation == "evaluate" else power)
        result = operation(spec, spec_path=args.spec)
        if 'data_construction' in result:
            construction = result['data_construction']
            record_path = Path(construction['record']['path'])
            protected.add((record_path.parent / construction['table']['path']).resolve())
            if args.output.resolve() in protected:
                raise ValueError('output must differ from the constructed analysis table')
        serialized = json.dumps(result, indent=2, allow_nan=False) + "\n"
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent,
                                             prefix=f".{args.output.name}.", delete=False) as temp:
                temp_path = Path(temp.name)
                temp.write(serialized)
            os.replace(temp_path, args.output)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
    except (TypeError, ValueError, KeyError, OSError, ArithmeticError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
