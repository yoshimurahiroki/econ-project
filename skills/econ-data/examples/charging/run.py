#!/usr/bin/env python3
"""Generate the fictional charging economy and compare its merger scenarios."""
import argparse
import base64
import hashlib
import json
import pickle
import subprocess
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd
import pyblp

FLAT = (Path(__file__).resolve().parent / "RESOURCES.json").is_file()
ROOT = Path(__file__).resolve().parent if FLAT else Path(__file__).resolve().parents[4]
SCRIPTS = ROOT if FLAT else ROOT / "skills/econ-data/scripts"
sys.path.insert(0, str(SCRIPTS))
import research_data


def reference(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def original_equations(data, delta, alpha, prices, shares, costs, firms, populations):
    """Evaluate the adopted logit shares, price conditions and monetary totals."""
    share_error, gradient_error = 0.0, 0.0
    consumer, producer = 0.0, 0.0
    for market, population in populations.items():
        rows = np.flatnonzero(data.market_ids.to_numpy() == int(market))
        utility = delta[rows] - alpha * (prices[rows] - data.prices.to_numpy()[rows])
        scale = max(0.0, float(utility.max()))
        exponentials = np.exp(utility - scale)
        denominator = np.exp(-scale) + exponentials.sum()
        predicted = exponentials / denominator
        derivative = -alpha * (np.diag(predicted) - np.outer(predicted, predicted))
        ownership = firms[rows, None] == firms[None, rows]
        margins = prices[rows] - costs[rows]
        gradients = predicted + (ownership * derivative).T @ margins
        share_error = max(share_error, float(np.max(np.abs(predicted - shares[rows]))))
        gradient_error = max(gradient_error, float(np.max(np.abs(gradients))))
        consumer += population * (scale + np.log(denominator)) / alpha
        producer += population * float(margins @ predicted)
    return {"share_residual": share_error, "profit_gradient": gradient_error,
            "consumer_surplus": consumer, "producer_surplus": producer,
            "social_welfare": consumer + producer}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    spec_path = Path(__file__).with_name("charging-specification.json" if FLAT else "specification.json")
    spec = json.loads(spec_path.read_text())
    p, model = spec["parameters"], spec["economic_model"]
    dimensions = {"mechanism": model["mechanism_comparison"], "estimand": model["objective"],
                  "identifying_variation": model["identification"], "population": spec["population"],
                  "measurement": "Prices per10kWh and monetary surplus over one operating week"}
    formulation = {"specification": reference(spec_path), "judgment": {"owner": "example author", "formulation": {
        "initial": {"question": spec["internal"]["initial_question"],
                    "dimensions": {**dimensions, "estimand": "Equilibrium charging price changes"}},
        "alternative": {"question": spec["question"], "dimensions": dimensions},
        "comparison": spec["internal"]["upstream_comparison"], "selected": "alternative",
        "rationale": spec["internal"]["decisive_calculation"]}}}
    research_data.write_json(destination / "formulation-contract.json", formulation)
    design = ROOT / "research_design.py" if FLAT else ROOT / "skills/econ-design/scripts/research_design.py"
    subprocess.run([sys.executable, str(design), "formulate", str(destination / "formulation-contract.json"),
                    "--root", str(ROOT), "--output", str(destination / "formulation.json")],
                   check=True, stdout=subprocess.DEVNULL)

    rng = np.random.default_rng(p["seed"])
    n = p["markets"] * p["products_per_market"]
    data = pd.DataFrame({"market_ids": np.repeat(np.arange(p["markets"]), p["products_per_market"]),
                         "product_ids": np.tile(np.arange(p["products_per_market"]), p["markets"])})
    data["firm_ids"] = data.product_ids
    data["clustering_ids"] = data.market_ids
    data["quality"] = rng.uniform(*p["quality_uniform"], n)
    data["demand_instruments0"] = rng.uniform(*p["procurement_shifter_uniform"], n)
    xi = np.repeat(rng.normal(0, p["market_demand_shock_sd"], p["markets"]), p["products_per_market"])
    xi += rng.normal(0, p["product_demand_shock_sd"], n)
    costs = (p["cost_intercept"] + p["cost_shifter_coefficient"] * data.demand_instruments0.to_numpy()
             + p["cost_quality_coefficient"] * data.quality.to_numpy() + rng.uniform(*p["cost_shock_uniform"], n))
    pyblp.options.verbose = False
    simulation = pyblp.Simulation(pyblp.Formulation(spec["estimation"]["linear"]), data,
        beta=[p["beta"]["intercept"], p["beta"]["prices"], p["beta"]["quality"]], xi=xi, seed=p["seed"])
    generated = simulation.replace_endogenous(costs=costs)
    data["prices"] = generated.product_data.prices.ravel()
    data["shares"] = generated.product_data.shares.ravel()
    data["row_id"] = [f"M{m:03}-P{j}" for m, j in zip(data.market_ids, data.product_ids)]
    markets = pd.DataFrame({"market_ids": np.arange(p["markets"]), "market_size": p["occasions_per_market"]})
    meanings = {
        "market_ids": ("identifier", "Independent geographic market", "cluster"),
        "product_ids": ("identifier", "Charging service within a market", "identifier"),
        "firm_ids": ("identifier", "Price-setting owner", "auxiliary"),
        "clustering_ids": ("identifier", "Independent market inference unit", "cluster"),
        "quality": ("quality index", "Observed service quality entering utility", "regressor"),
        "demand_instruments0": ("procurement-price index", "Excluded cost shifter", "instrument"),
        "prices": ("hundred JPY per10kWh", "Equilibrium service price", "endogenous"),
        "shares": ("share of potential charging occasions", "Observed choice probability", "primary_outcome"),
        "row_id": ("identifier", "Product-market row identity", "identifier"),
        "market_size": ("potential10kWh charging occasions", "Fixed market population", "auxiliary")}
    definitions = {name: {"unit": unit, "definition": meaning, "version": spec["specification_id"],
                          "role": role, "source_fields": [name], "timing": spec["period"], "rationale": meaning}
                   for name, (unit, meaning, role) in meanings.items()}
    shared = {}
    for name, table, keys in (("products", data, ["market_ids", "product_ids"]),
                              ("markets", markets, ["market_ids"])):
        source = destination / f"{name}-source.csv"
        table.to_csv(source, index=False)
        assembly = {"base": reference(source), "grain": keys,
                    "definitions": {key: definitions[key] for key in table.columns}}
        research_data.write_json(destination / f"{name}-assembly.json", assembly)
        research_data.assemble(assembly, destination, destination / name)
        shared[name] = destination / name / "analysis.csv"
    assembly = {"base": reference(shared["products"]), "grain": ["market_ids", "product_ids"],
        "definitions": definitions, "joins": [{"table": reference(shared["markets"]),
            "left": ["market_ids"], "right": ["market_ids"], "columns": ["market_size"],
            "cardinality": "many_to_one", "unmatched": "error"}],
        "sample": {"id": "charging-market-sample-v1", "row_id": "row_id", "filters": [],
                   "complete_cases": ["prices", "shares", "quality", "demand_instruments0"], "require_common": True}}
    research_data.write_json(destination / "analysis-assembly.json", assembly)
    research_data.assemble(assembly, destination, destination / "analysis")
    analysis = pd.read_csv(destination / "analysis/analysis.csv", float_precision="round_trip")
    columns = [key for key in data.columns if key != "row_id"]
    populations = {str(int(row.market_ids)): int(row.market_size) for row in markets.itertuples()}
    baseline = {"products": analysis[columns].to_dict("records"), "linear": spec["estimation"]["linear"],
        "nonlinear": None, "supply": None, "integration": None,
        "solve": {key: spec["estimation"][key] for key in ("method", "W_type", "se_type")},
        "counterfactual": None, "optimal_instruments": False, "add_exogenous": True, "market_sizes": populations}
    run_spec = {"model": "blp", "baseline": baseline, "scenario": None, "unit": spec["unit"],
        "sources": [{"description": "Fictional charging economy", **reference(spec_path)},
                    {"description": "Shared analysis table", **reference(destination / "analysis/analysis.csv")},
                    {"description": "Shared data record", **reference(destination / "analysis/data-record.json")} ]}
    research_data.write_json(destination / "run-spec.json", run_spec)
    runner = SCRIPTS / "research_markets.py"
    fit_path = destination / "fit.json"
    subprocess.run([sys.executable, str(runner), "run", str(destination / "run-spec.json"),
                    "--output", str(fit_path)], check=True)
    fit = json.loads(fit_path.read_text())
    native = pickle.loads(base64.b64decode(fit["native_fit"]["data"]))
    beta = dict(zip(native.beta_labels, native.beta.ravel(), strict=True))
    fitted_costs = np.asarray(fit["baseline"]["marginal_costs"]).ravel()
    cases = {"baseline": fit["baseline"]}
    results = {"baseline": reference(fit_path)}
    ownership = {"baseline": analysis.firm_ids.to_numpy()}
    scenario_costs = {"baseline": fitted_costs}
    for name, reduction in (("ownership-only", 0.0), ("integrated", p["merged_cost_reduction"])):
        merged = analysis.firm_ids.isin(p["merged_firms"]).to_numpy()
        ownership[name] = np.where(merged, p["merged_firms"][0], analysis.firm_ids)
        scenario_costs[name] = fitted_costs * np.where(merged, 1 - reduction, 1)
        scenario = {"keep_product_ids": list(range(p["products_per_market"])),
                    "firm_ids": ownership[name].tolist(), "costs": scenario_costs[name].tolist(),
                    "utility_shifts": np.zeros(n).tolist()}
        research_data.write_json(destination / f"{name}-scenario.json", scenario)
        result_path = destination / f"{name}.json"
        subprocess.run([sys.executable, str(runner), "counterfactual", str(fit_path),
                        str(destination / f"{name}-scenario.json"), "--output", str(result_path)], check=True)
        cases[name] = json.loads(result_path.read_text())["baseline"]["counterfactual"]
        results[name] = reference(result_path)
    checks, totals = {}, {}
    for name, result in cases.items():
        prices = analysis.prices.to_numpy() if name == "baseline" else np.asarray(result["prices"]).ravel()
        shares = np.asarray(result["shares"]).ravel()
        checked = original_equations(analysis, native.delta.ravel(), -beta["prices"], prices, shares,
                                     scenario_costs[name], ownership[name], populations)
        totals[name] = result["aggregate_welfare"]
        checked["accounting_residual"] = max(abs(checked[key] - totals[name][key])
            for key in ("consumer_surplus", "producer_surplus", "social_welfare"))
        if max(checked[key] for key in ("share_residual", "profit_gradient", "accounting_residual")) > p["equation_tolerance"]:
            raise ArithmeticError(f"Original charging equations: {name}: {checked}")
        checks[name] = checked
    integration_cost = sum(populations.values()) * p["integration_cost_per_potential_occasion"]
    decision_totals = {name: {"consumer_surplus": values["consumer_surplus"],
        "producer_surplus": values["producer_surplus"] - (integration_cost if name == "integrated" else 0),
        "social_welfare": values["social_welfare"] - (integration_cost if name == "integrated" else 0)}
        for name, values in totals.items()}
    decision_changes = {name: {key: value - decision_totals["baseline"][key] for key, value in values.items()}
                        for name, values in decision_totals.items()}
    net_gain = decision_changes["integrated"]["social_welfare"]
    critical = NormalDist().inv_cdf((1 + spec["estimation"]["confidence_level"]) / 2)
    coefficient_units = {"1": "normalized utility", "prices": "normalized utility per hundred JPY",
                         "quality": "normalized utility per quality-index unit"}
    intervals = {str(label): {"estimate": float(value), "standard_error": float(se),
        "lower": float(value - critical * se), "upper": float(value + critical * se), "unit": coefficient_units[str(label)]}
        for label, value, se in zip(native.beta_labels, native.beta.ravel(), native.beta_se.ravel(), strict=True)}
    research_data.write_json(destination / "result-index.json", {
        "result_id": spec["specification_id"], "specification": reference(spec_path),
        "producer": reference(Path(__file__)), "formulation": reference(destination / "formulation.json"),
        "data_record": reference(destination / "analysis/data-record.json"), "results": results,
        "selected_action": "approve" if net_gain > 0 else "baseline",
        "net_social_surplus_change": net_gain, "unit": spec["unit"],
        "decision_quantities": {"unit": spec["unit"], "population": sum(populations.values()),
                                "scenario_totals": decision_totals, "changes_from_baseline": decision_changes},
        "uncertainty": {"confidence_level": spec["estimation"]["confidence_level"],
                        "family": spec["estimation"]["interval_family"], "coefficients": intervals},
        "internal": {"original_equations": checks, "true_xi": xi.tolist(), "true_costs": costs.tolist(),
                     "integration_cost": integration_cost, "scenario_totals": totals,
                     "inference_scope": spec["internal"]["inference_scope"], "python": sys.version,
                     "pyblp": pyblp.__version__, "market_runner": reference(runner)}})
    print(json.dumps({"result_id": spec["specification_id"], "output": str(destination)}))


if __name__ == "__main__":
    main()
