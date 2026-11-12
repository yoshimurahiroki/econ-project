#!/usr/bin/env python3
"""Estimate fictional equipment choices and compare renewal technologies."""
import argparse
import hashlib
import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

FLAT = (Path(__file__).resolve().parent / "RESOURCES.json").is_file()
ROOT = Path(__file__).resolve().parent if FLAT else Path(__file__).resolve().parents[4]
SCRIPTS = ROOT if FLAT else ROOT / "skills/econ-data/scripts"
sys.path.insert(0, str(SCRIPTS))
import research_data
import research_dynamic


def reference(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def bellman_derivatives(model, beta):
    """Differentiate the original Bellman equation in the order c, R."""
    probabilities = np.asarray(model["policy"])
    transition = np.asarray(model["transition"])
    states = len(probabilities)
    flow_gradient = np.zeros((2, states, 2))
    flow_gradient[0, :, 0] = -np.arange(states)
    flow_gradient[1, :, 1] = -1
    mixed = np.einsum("sa,ask->sk", probabilities, transition)
    right = np.einsum("sa,asj->sj", probabilities, flow_gradient)
    system = np.eye(states) - beta * mixed
    value_gradient = np.linalg.solve(system, right)
    choice_gradient = flow_gradient + beta * np.einsum("ask,kj->asj", transition, value_gradient)
    score = (choice_gradient - value_gradient[None, :, :]).transpose(1, 0, 2)
    return value_gradient, score, float(np.max(np.abs(system @ value_gradient - right)))


def cluster_covariance(frame, model, beta):
    """Combine conditional information and firm-level action scores."""
    value_gradient, scores, residual = bellman_derivatives(model, beta)
    states = frame["state"].to_numpy(dtype=int)
    actions = frame["action"].to_numpy(dtype=int)
    counts = np.bincount(states, minlength=len(model["policy"]))
    bread = np.einsum("s,sa,saj,sak->jk", counts, np.asarray(model["policy"]), scores, scores)
    ids, clusters = np.unique(frame["firm_id"].to_numpy(), return_inverse=True)
    contributions = scores[states, actions]
    firm_scores = np.zeros((len(ids), 2))
    np.add.at(firm_scores, clusters, contributions)
    factor = len(ids) / (len(ids) - 1)
    meat = factor * firm_scores.T @ firm_scores
    if np.linalg.matrix_rank(bread) != 2:
        raise ArithmeticError("Cost information requires two independent directions")
    inverse = np.linalg.solve(bread, np.eye(2))
    covariance = inverse @ meat @ inverse.T
    if not np.isfinite(covariance).all() or np.min(np.linalg.eigvalsh(covariance)) <= 0:
        raise ArithmeticError("Cost covariance must be finite and positive definite")
    diagnostics = {"conditional_information": bread.tolist(), "cluster_meat": meat.tolist(),
        "firm_ids": ids.tolist(), "firm_scores": firm_scores.tolist(), "clusters": len(ids),
        "finite_sample_factor": factor, "mean_score": contributions.mean(axis=0).tolist(),
        "information_eigenvalues": np.linalg.eigvalsh(bread).tolist(),
        "choice_score_singular_values": np.linalg.svd(scores.reshape(-1, 2), compute_uv=False).tolist(),
        "implicit_equation_residual": residual}
    return covariance, value_gradient, diagnostics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    destination = parser.parse_args().output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    spec_path = Path(__file__).with_name("equipment-specification.json" if FLAT else "specification.json")
    spec = json.loads(spec_path.read_text())
    simulation, estimation, economic = spec["simulation"], spec["estimation"], spec["economic_model"]
    beta, n = simulation["discount_factor"], simulation["states"]
    money = simulation["money_scale_thousand_jpy"]
    dimensions = {"mechanism": economic["mechanism"], "estimand": economic["objective"],
        "identifying_variation": economic["identification"], "population": spec["population"],
        "measurement": "Firm-quarter state, action and next state; initial states and monetary deployment costs"}
    formulation = {"specification": reference(spec_path), "judgment": {"owner": "example author", "formulation": {
        "initial": {"question": spec["internal"]["initial_question"],
                    "dimensions": {**dimensions, "estimand": "State-specific quarterly replacement probabilities"}},
        "alternative": {"question": spec["question"], "dimensions": dimensions},
        "comparison": spec["internal"]["upstream_comparison"], "selected": "alternative",
        "rationale": spec["internal"]["decisive_calculation"]}}}
    research_data.write_json(destination / "formulation-contract.json", formulation)
    design = ROOT / "research_design.py" if FLAT else ROOT / "skills/econ-design/scripts/research_design.py"
    subprocess.run([sys.executable, str(design), "formulate", str(destination / "formulation-contract.json"),
                    "--root", str(ROOT), "--output", str(destination / "formulation.json")],
                   check=True, stdout=subprocess.DEVNULL)

    truth = research_dynamic.replacement(beta, [simulation["maintenance_cost"], simulation["replacement_cost"]], n)
    rng = np.random.Generator(np.random.PCG64(simulation["seed"]))
    firms = pd.DataFrame({"firm_code": np.arange(simulation["firms"]),
                          "initial_wear": np.arange(simulation["firms"]) % n})
    observations = []
    for firm in firms.itertuples(index=False):
        state = int(firm.initial_wear)
        for quarter in range(1, simulation["quarters"] + 1):
            action = int(rng.random() < truth["policy"][state, 1])
            following = 0 if action else min(state + 1, n - 1)
            observations.append({"firm_code": int(firm.firm_code), "quarter_number": quarter,
                "wear": state, "renewal": action, "following_wear": following})
            state = following
    sources = {"firms": firms, "choices": pd.DataFrame(observations)}
    meanings = {
        "firm_id": ("identifier", "Independent firm owning one machine"),
        "initial_state": ("wear index", "Machine state before its first observed quarterly choice"),
        "record_id": ("identifier", "Unique firm-quarter observation"),
        "period": ("quarter index", "Quarter counted from zero"),
        "state": ("wear index", "Machine state observed before the current action"),
        "action": ("action code", "0 maintains; 1 replaces"),
        "next_state": ("wear index", "State resulting from the current action")}
    definitions = {key: {"unit": unit, "definition": meaning, "version": spec["specification_id"],
                          "timing": spec["period"]} for key, (unit, meaning) in meanings.items()}
    queries = {
        "firms": "SELECT CAST(firm_code AS BIGINT) AS firm_id, CAST(initial_wear AS BIGINT) AS initial_state FROM source ORDER BY firm_id",
        "choices": "SELECT CAST(firm_code AS BIGINT) AS firm_id, CAST(quarter_number AS BIGINT)-1 AS period, "
                   "firm_code || ':' || quarter_number AS record_id, CAST(wear AS BIGINT) AS state, "
                   "CAST(renewal AS BIGINT) AS action, CAST(following_wear AS BIGINT) AS next_state "
                   "FROM source ORDER BY firm_id, period"}
    shared, records = {}, {}
    for name, raw in sources.items():
        path = destination / f"{name}-source.csv"
        raw.to_csv(path, index=False)
        fields = ["firm_id", "initial_state"] if name == "firms" else ["firm_id", "period", "record_id", "state", "action", "next_state"]
        assembly = {"sql": {"tables": {"source": reference(path)}, "query": queries[name]},
            "grain": ["firm_id"] if name == "firms" else ["firm_id", "period"],
            "output_format": "parquet", "definitions": {key: definitions[key] for key in fields}}
        research_data.write_json(destination / f"{name}-assembly.json", assembly)
        research_data.assemble(assembly, destination, destination / name)
        shared[name] = destination / name / "analysis.parquet"
        records[name] = reference(destination / name / "data-record.json")
    analysis = {"base": reference(shared["choices"]), "grain": ["firm_id", "period"],
        "joins": [{"table": reference(shared["firms"]), "left": ["firm_id"], "right": ["firm_id"],
                   "columns": ["initial_state"], "cardinality": "many_to_one", "unmatched": "error"}],
        "definitions": definitions, "output_format": "parquet", "clusters": ["firm_id"],
        "weights": {"kind": "none"}, "observation_unit": "one firm-quarter choice",
        "panel": {"entity": "firm_id", "time": "period", "balanced": True},
        "sample": {"id": "equipment-firm-panel-v1", "row_id": "record_id", "filters": [],
                   "complete_cases": ["state", "action", "next_state"], "require_common": True}}
    research_data.write_json(destination / "panel-assembly.json", analysis)
    research_data.assemble(analysis, destination, destination / "panel")
    records["panel"] = reference(destination / "panel/data-record.json")
    frame = research_data.read_frame(destination / "panel/analysis.parquet")
    columns = {"id": "firm_id", "period": "period", "state": "state", "action": "action", "next_state": "next_state"}
    runner_spec = {"model": "replacement", "data_record": records["panel"], "data": {"columns": columns},
        "options": {"discount_factor": beta, "states": n, "initial_costs": estimation["starts"][0],
                    "finite_horizon": estimation["finite_comparison_quarters"], "replacement_cost_change": 0},
        "adopted": {"specification": reference(spec_path), "model_contract_id": spec["model_contract_id"]},
        "scenario": {"description": "Baseline cost for the saved official fit"}}
    runner = SCRIPTS / "research_dynamic.py"
    research_data.write_json(destination / "fit-spec.json", runner_spec)
    subprocess.run([sys.executable, str(runner), "run", str(destination / "fit-spec.json"),
                    "--output", str(destination / "fit-result.json")], check=True)
    fitted = json.loads((destination / "fit-result.json").read_text())
    results = fitted["fullresults"]
    baseline = results["baseline"]
    theta = np.asarray(results["nfxp"]["parameters"])
    data = frame[["firm_id", "period", "state", "action", "next_state"]].to_numpy(dtype=int)
    starts = [results["nfxp"], *[research_dynamic.fit_replacement(data, beta, n, start) for start in estimation["starts"][1:]]]
    likelihoods = [fit["negative_log_likelihood"] for fit in starts]
    if max(likelihoods) - min(likelihoods) > estimation["multistart_likelihood_tolerance"]:
        raise ArithmeticError("Starting values lead to different maximized likelihoods")
    covariance, base_gradient, diagnostics = cluster_covariance(frame, baseline, beta)
    if max(abs(value) for value in diagnostics["mean_score"]) > estimation["mean_score_tolerance"]:
        raise ArithmeticError("Original-model mean score exceeds the adopted tolerance")
    initial = research_data.read_frame(shared["firms"])["initial_state"].to_numpy(dtype=int)
    initial_weights = np.bincount(initial, minlength=n) / len(initial)
    critical = float(norm.ppf((1 + estimation["inference"]["level"]) / 2))
    rows, gradients, scenarios, probability_rows = [], [], {}, []
    for technology in spec["technologies"]:
        name, reduction = technology["name"], technology["replacement_cost_reduction"]
        if theta[1] <= reduction:
            raise ArithmeticError("Technology requires a positive fitted replacement cost")
        current = baseline if name == "baseline" else research_dynamic.replacement(beta, [theta[0], theta[1] - reduction], n)
        derivative, scores, residual = bellman_derivatives(current, beta)
        gain = float(money * initial_weights @ (np.asarray(current["value"]) - np.asarray(baseline["value"])))
        net = gain - technology["adoption_cost_thousand_jpy"]
        gradient = money * initial_weights @ (derivative - base_gradient)
        standard_error = float(np.sqrt(max(0, gradient @ covariance @ gradient)))
        rows.append({"scenario": name, "operating_value_gain": gain,
            "adoption_cost": technology["adoption_cost_thousand_jpy"], "net_present_gain": net,
            "std_error": standard_error, "ci_lower": net - critical * standard_error,
            "ci_upper": net + critical * standard_error,
            "initial_replacement_probability": float(initial_weights @ np.asarray(current["policy"])[:, 1]),
            "feasible": technology["adoption_cost_thousand_jpy"] <= spec["adoption_budget_thousand_jpy"]})
        gradients.append(gradient)
        scenarios[name] = {key: value.tolist() if isinstance(value, np.ndarray) else value for key, value in current.items()}
        scenarios[name]["implicit_derivative_residual"] = residual
        for state, probabilities in enumerate(current["policy"]):
            p = float(probabilities[1])
            p_gradient = p * scores[state, 1]
            se = float(np.sqrt(p_gradient @ covariance @ p_gradient))
            probability_rows.append({"scenario": name, "state": state, "probability": p, "std_error": se})
    gain_covariance = np.asarray(gradients) @ covariance @ np.asarray(gradients).T
    contrasts = []
    for j in range(1, len(rows)):
        for k in range(j):
            difference = rows[j]["net_present_gain"] - rows[k]["net_present_gain"]
            se = float(np.sqrt(max(0, gain_covariance[j, j] + gain_covariance[k, k] - 2 * gain_covariance[j, k])))
            contrasts.append({"scenario": rows[j]["scenario"], "comparator": rows[k]["scenario"],
                "net_gain_difference": difference, "std_error": se,
                "ci_lower": difference - critical * se, "ci_upper": difference + critical * se})
    selected = max((row for row in rows if row["feasible"]), key=lambda row: row["net_present_gain"])
    parameter_rows = [{"parameter": key, "estimate": float(value), "std_error": float(se),
                       "ci_lower": float(value - critical * se), "ci_upper": float(value + critical * se)}
                      for key, value, se in zip(estimation["parameter_order"], theta, np.sqrt(np.diag(covariance)), strict=True)]
    research_data.write_json(destination / "technology-results.json", scenarios)
    research_data.write_json(destination / "result-index.json", {
        "result_id": spec["specification_id"], "specification": reference(spec_path), "producer": reference(Path(__file__)),
        "formulation": reference(destination / "formulation.json"), "data_records": records,
        "results": {"fit": reference(destination / "fit-result.json"), "technologies": reference(destination / "technology-results.json")},
        "selected_action": selected["scenario"],
        "parameters": {"unit": "utility", "rows": parameter_rows, "covariance": covariance.tolist()},
        "replacement_probabilities": {"unit": "probability per quarter", "rows": probability_rows},
        "decision_quantities": {"unit": spec["unit"], "population": spec["population"], "period": spec["period"], "rows": rows},
        "public_claims": {"selected_action": selected["scenario"], "net_present_gain": selected["net_present_gain"]},
        "uncertainty": {"level": estimation["inference"]["level"], "reference": "standard normal",
            "unit": spec["unit"], "scenario_order": [row["scenario"] for row in rows],
            "net_gain_covariance": gain_covariance.tolist(), "pairwise_contrasts": contrasts},
        "internal": {"inference_specification": estimation["inference"], "inference_scope": spec["internal"]["inference_scope"],
            "accounting": spec["internal"]["accounting"], "diagnostics": diagnostics, "multistart_fits": starts,
            "initial_state_weights": initial_weights.tolist(), "net_gain_gradients": np.asarray(gradients).tolist(),
            "dynamic_runner": reference(runner), "environment": {"python": sys.version, "executable": sys.executable,
                "packages": {name: version(name) for name in ("ruspy", "numpy", "scipy", "pandas", "duckdb", "pyarrow")}}}})
    print(json.dumps({"result_id": spec["specification_id"], "selected_action": selected["scenario"], "output": str(destination)}))


if __name__ == "__main__":
    main()
