#!/usr/bin/env python3
"""Build the fictional housing data and solve the transport policy comparison."""
import argparse
import hashlib
import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pandas as pd

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
    spec_path = Path(__file__).with_name("housing-specification.json" if FLAT else "specification.json")
    spec = json.loads(spec_path.read_text())
    model, measurement = spec["economic_model"], spec["measurement"]
    ids = measurement["location_ids"]
    dimensions = {"mechanism": model["mechanism_comparison"], "estimand": model["objective"],
                  "identifying_variation": model["identification"], "population": spec["population"],
                  "measurement": measurement["rent_aggregation"]}
    formulation = {"specification": reference(spec_path), "judgment": {"owner": "example author", "formulation": {
        "initial": {"question": spec["internal"]["initial_question"],
                    "dimensions": {**dimensions, "estimand": "Outer-district annual rent change"}},
        "alternative": {"question": spec["question"], "dimensions": dimensions},
        "comparison": spec["internal"]["upstream_comparison"], "selected": "alternative",
        "rationale": spec["internal"]["decisive_calculation"]}}}
    research_data.write_json(destination / "formulation-contract.json", formulation)
    design = ROOT / "research_design.py" if FLAT else ROOT / "skills/econ-design/scripts/research_design.py"
    subprocess.run([sys.executable, str(design), "formulate", str(destination / "formulation-contract.json"),
                    "--root", str(ROOT), "--output", str(destination / "formulation.json")],
                   check=True, stdout=subprocess.DEVNULL)

    raw = {}
    for name, field, quantity in (("residents", "subdistrict_residents", "residents"),
                                  ("jobs", "worksite_jobs", "jobs")):
        raw[name] = pd.DataFrame([{"location_id": location, "source_id": f"{location}-{k}", quantity: count}
            for location, counts in zip(ids, measurement[field], strict=True)
            for k, count in enumerate(counts)])
    raw["leases"] = pd.DataFrame([{"location_id": location, "source_id": f"{location}-{k}",
        "floor_m2": area, "annual_revenue_jpy": 1000 * rent * multiplier * area}
        for location, rent in zip(ids, measurement["annual_rent_thousand_jpy_per_m2"], strict=True)
        for k, (area, multiplier) in enumerate(zip(measurement["lease_floor_m2"], measurement["lease_rent_multipliers"], strict=True))])
    raw["land"] = pd.DataFrame([{"location_id": location, "land_m2": area}
        for location, area in zip(ids, measurement["land_area_m2"], strict=True)])
    raw["travel"] = pd.DataFrame([{"origin": origin, "destination": workplace, "seconds": seconds}
        for origin, times in zip(ids, measurement["travel_time_seconds"], strict=True)
        for workplace, seconds in zip(ids, times, strict=True)])
    construction = {
        "residents": ("SELECT location_id, sum(CAST(residents AS BIGINT)) AS population FROM source GROUP BY location_id", ["location_id"]),
        "jobs": ("SELECT location_id, sum(CAST(jobs AS BIGINT)) AS employment FROM source GROUP BY location_id", ["location_id"]),
        "leases": ("SELECT location_id, sum(CAST(annual_revenue_jpy AS DOUBLE))/sum(CAST(floor_m2 AS DOUBLE))/1000 AS rent FROM source GROUP BY location_id", ["location_id"]),
        "land": ("SELECT location_id, CAST(land_m2 AS DOUBLE)/1000000 AS land_area FROM source", ["location_id"]),
        "travel": ("SELECT origin, destination, CAST(seconds AS DOUBLE)/60 AS travel_time FROM source", ["origin", "destination"])}
    meanings = {
        "location_id": ("identifier", "District joining resident, employment, lease and land records"),
        "population": ("workers", "Resident workers summed across disjoint subdistricts"),
        "employment": ("workers", "Jobs summed across disjoint workplaces"),
        "rent": ("thousand JPY per square meter per year", "Annual lease revenue divided by leased floor area"),
        "land_area": ("square kilometers", "District land area"),
        "origin": ("identifier", "Residence district"), "destination": ("identifier", "Workplace district"),
        "travel_time": ("minutes", "Residence-to-workplace travel time")}
    definitions = {name: {"unit": unit, "definition": definition, "version": spec["specification_id"],
                           "timing": spec["period"]} for name, (unit, definition) in meanings.items()}
    shared, data_records = {}, {}
    for name, frame in raw.items():
        keys = ["origin", "destination"] if name == "travel" else ["location_id", "source_id"] if "source_id" in frame else ["location_id"]
        if frame[keys].isna().any().any() or frame.duplicated(keys).any():
            raise ValueError(f"Source keys: {name}")
        source = destination / f"{name}-source.csv"
        frame.to_csv(source, index=False)
        query, grain = construction[name]
        value_column = {"residents": "population", "jobs": "employment", "leases": "rent",
                        "land": "land_area", "travel": "travel_time"}[name]
        assembly = {"sql": {"tables": {"source": reference(source)}, "query": query},
                    "grain": grain, "definitions": {key: definitions[key] for key in [*grain, value_column]}}
        research_data.write_json(destination / f"{name}-assembly.json", assembly)
        research_data.assemble(assembly, destination, destination / name)
        shared[name] = destination / name / "analysis.csv"
        data_records[name] = reference(destination / name / "data-record.json")
    assembly = {"base": reference(shared["residents"]), "grain": ["location_id"],
        "definitions": {key: definitions[key] for key in ("location_id", "population", "employment", "rent", "land_area")},
        "joins": [{"table": reference(shared[name]), "left": ["location_id"], "right": ["location_id"],
                   "columns": [column], "cardinality": "one_to_one", "unmatched": "error"}
                  for name, column in (("jobs", "employment"), ("leases", "rent"), ("land", "land_area"))]}
    research_data.write_json(destination / "district-assembly.json", assembly)
    research_data.assemble(assembly, destination, destination / "districts")
    data_records["districts"] = reference(destination / "districts/data-record.json")
    districts = pd.read_csv(destination / "districts/analysis.csv", float_precision="round_trip").set_index("location_id").loc[ids]
    travel = pd.read_csv(shared["travel"], float_precision="round_trip")
    if set(travel.origin) != set(ids) or set(travel.destination) != set(ids) or len(travel) != len(ids) ** 2:
        raise ValueError("Travel table requires the complete declared origin-destination support")
    times = travel.pivot(index="origin", columns="destination", values="travel_time").loc[ids, ids].to_numpy()
    wage_scale = measurement["wage_numeraire_thousand_jpy_per_worker_year"]
    run_spec = {"model": "qse_commuting", "operation": "invert_baseline", "parameters": spec["calibration"],
        "calibration_source": spec["internal"]["calibration_source"], "solver": spec["solver"],
        "baseline": {"location_ids": ids, **{key: districts[key].tolist() for key in ("population", "employment", "rent", "land_area")},
            "travel_time": times.tolist(), "wage_numeraire": wage_scale,
            "source": f"Fictional {spec['specification_id']}; district and travel shared tables; annual rent in thousand JPY per square meter, land in square kilometers, travel in minutes"}}
    research_data.write_json(destination / "baseline-spec.json", run_spec)
    runner = SCRIPTS / "research_macro_extended.py"
    baseline_path = destination / "baseline-result.json"
    subprocess.run([sys.executable, str(runner), "run", str(destination / "baseline-spec.json"),
                    "--output", str(baseline_path)], check=True)
    baseline = json.loads(baseline_path.read_text())
    baseline_ref = reference(baseline_path)
    cases, results, decision_rows = {}, {}, []
    for policy in spec["policies"]:
        name = policy["name"]
        if name == "baseline":
            result, state = baseline, baseline["baseline"]
            workers = owner_change = 0.0
            results[name] = baseline_ref
        else:
            policy_times = times.copy()
            policy_times[ids.index("center"), ids.index("outer")] = policy["link_minutes"]
            policy_times[ids.index("outer"), ids.index("center")] = policy["link_minutes"]
            hats = [policy["outer_floor_hat"] if location == "outer" else 1 for location in ids]
            scenario_spec = {"model": "qse_commuting", "operation": "counterfactual", "saved_solution": baseline_ref,
                "solver": spec["solver"], "scenario": {"name": name, "travel_time": policy_times.tolist(), "floor_space_hat": hats}}
            input_path, output_path = destination / f"{name}-spec.json", destination / f"{name}-result.json"
            research_data.write_json(input_path, scenario_spec)
            subprocess.run([sys.executable, str(runner), "run", str(input_path), "--output", str(output_path)], check=True)
            result = json.loads(output_path.read_text())
            if result["baseline"] != baseline["baseline"] or result["computation"]["operations_executed"] != ["load_baseline", "solve_counterfactual"]:
                raise ArithmeticError("Counterfactual must reuse the exact saved original baseline")
            state = result["scenario"]
            workers = result["welfare"]["worker_income_equivalent"]["value"] * wage_scale
            owner_change = result["welfare"]["owner_income_change"]["value"] * wage_scale
            results[name] = reference(output_path)
        extra_floor = baseline["primitives"]["floor_space"][ids.index("outer")] * (policy["outer_floor_hat"] - 1)
        cost = policy["transport_cost_thousand_jpy"] + extra_floor * policy["added_floor_cost_thousand_jpy_per_m2"]
        owners_net = owner_change - cost
        owner_consumption = state["aggregate"]["owner_income"] * wage_scale - cost
        goods = state["aggregate"]["output"] * wage_scale
        goods_residual = goods - state["aggregate"]["worker_consumption"] * wage_scale - owner_consumption - cost
        if abs(goods_residual) / goods > 10 * spec["solver"]["tolerance"]:
            raise ArithmeticError("Goods must fund worker consumption, net owner consumption and policy resources")
        decision_rows.append({"scenario": name, "worker_income_equivalent": workers,
            "owner_income_change_gross": owner_change, "policy_resource_cost": cost,
            "owner_income_change_net": owners_net, "net_income_equivalent": workers + owners_net,
            "owner_consumption_net": owner_consumption, "additional_floor_m2": extra_floor,
            "mean_commute_minutes": state["aggregate"]["mean_commute_time"],
            "feasible": cost <= spec["policy_budget_thousand_jpy"] and owner_consumption >= 0})
        cases[name] = {"original_equations": state["diagnostics"], "original_residuals": state["original_residuals"],
                       "goods_resource_residual_thousand_jpy": goods_residual}
    selected = max((row for row in decision_rows if row["feasible"]), key=lambda row: row["net_income_equivalent"])
    research_data.write_json(destination / "result-index.json", {
        "result_id": spec["specification_id"], "specification": reference(spec_path), "producer": reference(Path(__file__)),
        "formulation": reference(destination / "formulation.json"), "data_records": data_records, "results": results,
        "selected_action": selected["scenario"], "decision_quantities": {"unit": spec["unit"],
            "population": spec["population"], "period": spec["period"], "rows": decision_rows},
        "public_claims": {"selected_action": selected["scenario"], "net_income_equivalent": selected["net_income_equivalent"]},
        "uncertainty": {}, "internal": {"checks": cases, "inference_scope": spec["internal"]["inference_scope"],
            "accounting": spec["internal"]["accounting"], "macro_runner": reference(runner),
            "environment": {"python": sys.version, "executable": sys.executable,
                "packages": {name: version(name) for name in ("pandas", "numpy", "scipy", "duckdb", "pyarrow")}},
            "baseline_inversion": baseline["inversion"], "normalization": baseline["normalization"]}})
    print(json.dumps({"result_id": spec["specification_id"], "selected_action": selected["scenario"], "output": str(destination)}))


if __name__ == "__main__":
    main()
