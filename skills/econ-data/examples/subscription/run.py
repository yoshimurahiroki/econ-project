#!/usr/bin/env python3
"""Learn support allocations and evaluate quarterly subscription contribution."""
import argparse
import hashlib
import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.stats import norm
from sklearn.metrics import mean_squared_error

FLAT = (Path(__file__).resolve().parent / "RESOURCES.json").is_file()
ROOT = Path(__file__).resolve().parent if FLAT else Path(__file__).resolve().parents[4]
SCRIPTS = ROOT if FLAT else ROOT / "skills/econ-data/scripts"
sys.path.insert(0, str(SCRIPTS))
import research_data


def reference(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    destination = parser.parse_args().output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    spec_path = Path(__file__).with_name("subscription-specification.json" if FLAT else "specification.json")
    spec = json.loads(spec_path.read_text())
    simulation, learning, economic = spec["simulation"], spec["learning"], spec["economic_model"]
    n, training = simulation["customers"], simulation["training_customers"]
    margin, cost = simulation["renewal_contribution"], simulation["contact_cost"]
    dimensions = {"mechanism": economic["mechanism"], "estimand": economic["firm_objective"],
        "identifying_variation": economic["identification"], "population": spec["population"],
        "measurement": "Pretreatment disengagement and support need, randomized contact and quarterly renewal"}
    formulation = {"specification": reference(spec_path), "judgment": {"owner": "example author", "formulation": {
        "initial": {"question": spec["internal"]["initial_question"],
                    "dimensions": {**dimensions, "estimand": "Quarterly cancellation probability under the existing service"}},
        "alternative": {"question": spec["question"], "dimensions": dimensions},
        "comparison": spec["internal"]["upstream_comparison"], "selected": "alternative",
        "rationale": spec["internal"]["decisive_calculation"]}}}
    research_data.write_json(destination / "formulation-contract.json", formulation)
    design = ROOT / "research_design.py" if FLAT else ROOT / "skills/econ-design/scripts/research_design.py"
    subprocess.run([sys.executable, str(design), "formulate", str(destination / "formulation-contract.json"),
                    "--root", str(ROOT), "--output", str(destination / "formulation.json")],
                   check=True, stdout=subprocess.DEVNULL)

    rng = np.random.Generator(np.random.PCG64(simulation["population_seed"]))
    disengagement = rng.uniform(size=n)
    need = rng.binomial(1, simulation["support_need_probability"], n)
    uniform_shock = rng.uniform(size=n)
    utility = simulation["utility_intercept"] + simulation["disengagement_slope"] * disengagement
    probabilities = expit(utility[:, None] + np.array([0, 1])[None, :] *
                          (simulation["support_increment"] + simulation["need_increment"] * need[:, None]))
    potential_outcomes = (uniform_shock[:, None] <= probabilities).astype(int)
    assignment = np.random.Generator(np.random.PCG64(simulation["assignment_seed"])).binomial(
        1, simulation["assignment_probability"], n)
    ids = np.array([f"C{i:05d}" for i in range(n)])
    sources = {
        "customers": pd.DataFrame({"customer_code": ids, "prior_disengagement": disengagement,
            "prior_support_need": need, "sample_role": np.where(np.arange(n) < training, "train", "evaluation")}),
        "renewals": pd.DataFrame({"customer_code": ids, "support_assignment": np.array(["control", "support"])[assignment],
            "renewed": potential_outcomes[np.arange(n), assignment],
            "control_probability": 1 - simulation["assignment_probability"],
            "support_probability": simulation["assignment_probability"]})}
    meanings = {
        "customer_id": ("identifier", "Unique subscription customer"),
        "disengagement": ("index on [0,1]", "Recorded disengagement before the support assignment"),
        "support_need": ("indicator", "Onboarding need reported before the support assignment"),
        "partition": ("sample role", "Fixed training or evaluation assignment by customer roster"),
        "action": ("assignment label", "Randomized control or support assignment"),
        "renewal": ("indicator", "Customer renews the subscription for the quarter"),
        "p_control": ("probability", "Known individual probability of control assignment"),
        "p_support": ("probability", "Known individual probability of support assignment")}
    definitions = {key: {"unit": unit, "definition": meaning, "version": spec["specification_id"]}
                   for key, (unit, meaning) in meanings.items()}
    queries = {
        "customers": "SELECT customer_code AS customer_id, CAST(prior_disengagement AS DOUBLE) AS disengagement, "
                     "CAST(prior_support_need AS BIGINT) AS support_need, sample_role AS partition FROM source ORDER BY customer_id",
        "renewals": "SELECT customer_code AS customer_id, support_assignment AS action, CAST(renewed AS BIGINT) AS renewal, "
                    "CAST(control_probability AS DOUBLE) AS p_control, CAST(support_probability AS DOUBLE) AS p_support "
                    "FROM source ORDER BY customer_id"}
    fields = {"customers": ["customer_id", "disengagement", "support_need", "partition"],
              "renewals": ["customer_id", "action", "renewal", "p_control", "p_support"]}
    records = {}
    for name, raw in sources.items():
        source = destination / f"{name}-source.csv"
        raw.to_csv(source, index=False)
        assembly = {"sql": {"tables": {"source": reference(source)}, "query": queries[name]},
            "grain": ["customer_id"], "output_format": "parquet",
            "definitions": {key: definitions[key] for key in fields[name]}}
        research_data.write_json(destination / f"{name}-assembly.json", assembly)
        research_data.assemble(assembly, destination, destination / name)
        records[name] = reference(destination / name / "data-record.json")
    assembly = {"base": reference(destination / "customers/analysis.parquet"), "grain": ["customer_id"],
        "joins": [{"table": reference(destination / "renewals/analysis.parquet"),
            "left": ["customer_id"], "right": ["customer_id"], "columns": fields["renewals"][1:],
            "cardinality": "one_to_one", "unmatched": "error"}],
        "definitions": definitions, "output_format": "parquet", "weights": {"kind": "none"},
        "observation_unit": spec["observation_unit"],
        "sample": {"id": "subscription-training-and-evaluation-v1", "row_id": "customer_id", "filters": [],
                   "complete_cases": list(definitions), "require_common": False}}
    research_data.write_json(destination / "analysis-assembly.json", assembly)
    research_data.assemble(assembly, destination, destination / "analysis")
    records["analysis"] = reference(destination / "analysis/data-record.json")
    runner_spec = {"method": "policy_tree", "data_record": records["analysis"],
        "data": str(destination / "analysis/analysis.parquet"), "id": "customer_id", "outcome": "renewal",
        "regressors": learning["regressors"], "endogenous": [], "instruments": [],
        "population": "The fixed evaluation cohort of 4,000 fictional subscribers", "period": spec["period"],
        "unit": "renewals per evaluation customer", "estimand": spec["inference"]["target"],
        "identification": economic["identification"], "assignment": "Independent Bernoulli customer-level support assignment",
        "inference": {"type": "policy", "confidence_level": spec["inference"]["confidence_level"]},
        "options": {"treatment": "action", "partition": "partition", "seed": simulation["learning_seed"], "policy": {
            "arms": ["control", "support"], "baseline": "control", "value_method": "aipw",
            "evaluation_target": "fixed_batch", "propensity": {"source": "known", "columns": ["p_control", "p_support"],
                "mechanism": "independent_multinomial", "assignment_unit": "individual"},
            "n_folds": learning["n_folds"], "learners": {"ml_g": learning["outcome_learner"]},
            "tree": learning["policy_tree"], "objective": "net_benefit",
            "costs": {"amounts": [0, cost], "unit": spec["unit"], "benefit_per_outcome": margin},
            "constraints": {"budget": simulation["contact_budget"], "max_treated": simulation["maximum_contacts"]}}}}
    runner = SCRIPTS / "research_causal.py"
    research_data.write_json(destination / "policy-spec.json", runner_spec)
    subprocess.run([sys.executable, str(runner), "run", str(destination / "policy-spec.json"),
                    "--output", str(destination / "policy-result.json")], check=True)
    fitted = json.loads((destination / "policy-result.json").read_text())
    diagnostics = fitted["diagnostics"]
    evaluation_ids = np.asarray(fitted["sample"]["included_ids"])
    means = np.asarray(diagnostics["evaluation_nuisance_predictions"])
    count = len(evaluation_ids)
    selected_index = np.arange(count)
    capacity = min(simulation["maximum_contacts"], int(simulation["contact_budget"] // cost), count)
    risk = np.zeros(count, dtype=int)
    risk[np.lexsort((evaluation_ids, means[:, 0]))[:capacity]] = 1
    actions = {"baseline": np.zeros(count, dtype=int), "risk": risk,
        "policy": np.array([int(row["action"] == "support") for row in fitted["displays"]["policy_assignments"]["rows"]])}
    expected = {name: float(np.mean(margin * means[selected_index, action] - cost * action))
                for name, action in actions.items()}
    selected = max(actions, key=lambda name: (expected[name], -int(actions[name].sum()), -list(actions).index(name)))
    research_data.write_json(destination / "allocation.json", {"selected_action": selected,
        "customer_ids": evaluation_ids.tolist(), "assignments": {name: action.tolist() for name, action in actions.items()},
        "training_fitted_net_contribution": expected, "selection": learning["selection"],
        "input_result": reference(destination / "policy-result.json")})

    frame = research_data.read_frame(destination / "analysis/analysis.parquet").set_index("customer_id")
    evaluation = frame.loc[evaluation_ids]
    observed = evaluation["action"].eq("support").to_numpy(dtype=int)
    renewal = evaluation["renewal"].to_numpy(dtype=float)
    propensity = evaluation[["p_control", "p_support"]].to_numpy(dtype=float)
    corrections = np.zeros_like(means)
    corrections[selected_index, observed] = (renewal - means[selected_index, observed]) / propensity[selected_index, observed]
    scores = means + corrections
    value_scores = np.column_stack([margin * scores[selected_index, action] - cost * action for action in actions.values()])
    innovations = np.column_stack([margin * corrections[selected_index, action] / count for action in actions.values()])
    covariance = innovations.T @ innovations
    estimates = value_scores.mean(axis=0)
    critical = norm.ppf((1 + spec["inference"]["confidence_level"]) / 2)
    rows, contrasts = [], []
    for j, (name, action) in enumerate(actions.items()):
        se = float(np.sqrt(covariance[j, j]))
        rows.append({"scenario": name, "contacts": int(action.sum()), "total_contact_cost": float(cost * action.sum()),
            "renewal_rate": float(scores[selected_index, action].mean()), "net_contribution": float(estimates[j]),
            "std_error": se, "ci_lower": float(estimates[j] - critical * se), "ci_upper": float(estimates[j] + critical * se),
            "training_fitted_net_contribution": expected[name]})
        for k in range(j):
            difference = float(estimates[j] - estimates[k])
            se_difference = float(np.sqrt(max(0, covariance[j, j] + covariance[k, k] - 2 * covariance[j, k])))
            contrasts.append({"scenario": name, "comparator": list(actions)[k], "net_gain_difference": difference,
                "std_error": se_difference, "ci_lower": difference - critical * se_difference,
                "ci_upper": difference + critical * se_difference})
    group_rows, group_corrections = [], []
    for group in [0, 1]:
        included = evaluation["support_need"].to_numpy() == group
        weights = included / included.sum()
        effect = float(100 * weights @ (scores[:, 1] - scores[:, 0]))
        innovation = 100 * weights * (corrections[:, 1] - corrections[:, 0])
        group_corrections.append(innovation)
        se = float(np.linalg.norm(innovation))
        group_rows.append({"support_need": group, "customers": int(included.sum()), "renewal_effect": effect,
            "std_error": se, "ci_lower": effect - critical * se, "ci_upper": effect + critical * se})
    group_covariance = np.asarray(group_corrections) @ np.asarray(group_corrections).T
    group_difference = group_rows[1]["renewal_effect"] - group_rows[0]["renewal_effect"]
    group_se = float(np.sqrt(np.array([-1, 1]) @ group_covariance @ np.array([-1, 1])))
    controls = observed == 0
    bins = np.minimum((means[:, 0] * 5).astype(int), 4)
    calibration = []
    for bin_id in range(5):
        included = controls & (bins == bin_id)
        if included.any():
            calibration.append({"lower": bin_id / 5, "upper": (bin_id + 1) / 5, "customers": int(included.sum()),
                "predicted_renewal": float(means[included, 0].mean()), "observed_renewal": float(renewal[included].mean())})
    prediction = {"target": "Control-service renewal in the evaluation cohort", "observed_customers": int(controls.sum()),
        "brier_loss": float(mean_squared_error(renewal[controls], means[controls, 0])),
        "unit": "squared probability", "calibration": calibration,
        "calibration_bin_closure": "[lower, upper); the final bin includes upper=1",
        "calibration_field_units": {"lower": "probability", "upper": "probability", "customers": "customers",
            "predicted_renewal": "probability", "observed_renewal": "renewals per observed control customer"}}
    truth = {"customer_ids": ids.tolist(), "renewal_probabilities": probabilities.tolist(),
        "potential_outcomes": potential_outcomes.tolist(), "uniform_utility_shocks": uniform_shock.tolist()}
    research_data.write_json(destination / "simulation-primitives.json", truth)
    selected_row = rows[list(actions).index(selected)]
    research_data.write_json(destination / "result-index.json", {
        "result_id": spec["specification_id"], "specification": reference(spec_path), "producer": reference(Path(__file__)),
        "formulation": reference(destination / "formulation.json"), "data_records": records,
        "results": {"fit": reference(destination / "policy-result.json"), "allocation": reference(destination / "allocation.json")},
        "selected_action": selected, "prediction": prediction,
        "heterogeneity": {"unit": "percentage points of quarterly renewal", "rows": group_rows,
            "covariance": group_covariance.tolist(), "need_group_difference": {"estimate": group_difference,
                "std_error": group_se, "ci_lower": group_difference - critical * group_se,
                "ci_upper": group_difference + critical * group_se}},
        "decision_quantities": {"unit": spec["unit"], "population": runner_spec["population"], "period": spec["period"], "rows": rows,
            "field_units": {"contacts": "customers", "total_contact_cost": "thousand JPY for the evaluation cohort",
                "renewal_rate": "renewals per evaluation customer", "net_contribution": spec["unit"],
                "std_error": spec["unit"], "ci_lower": spec["unit"], "ci_upper": spec["unit"],
                "training_fitted_net_contribution": spec["unit"]}},
        "public_claims": {"selected_action": selected, "net_contribution": selected_row["net_contribution"],
            "contacts": selected_row["contacts"]},
        "uncertainty": {"level": spec["inference"]["confidence_level"], "reference": "standard normal", "unit": spec["unit"],
            "scenario_order": list(actions), "net_contribution_covariance": covariance.tolist(), "pairwise_contrasts": contrasts},
        "internal": {"inference_specification": spec["inference"], "conditions": spec["internal"]["conditions"],
            "simulation": reference(destination / "simulation-primitives.json"), "causal_runner": reference(runner),
            "selection_inputs": "Training-fitted means, frozen tree assignments, evaluation IDs and pretreatment covariates",
            "normalized_assignment_corrections": innovations.tolist(), "group_assignment_corrections": np.asarray(group_corrections).tolist(),
            "environment": {"python": sys.version, "executable": sys.executable,
                "packages": {name: version(name) for name in ("econml", "statspai", "scikit-learn", "numpy", "scipy", "statsmodels", "pandas", "duckdb", "pyarrow")}}}})
    print(json.dumps({"result_id": spec["specification_id"], "selected_action": selected, "output": str(destination)}))


if __name__ == "__main__":
    main()
