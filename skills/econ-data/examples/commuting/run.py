#!/usr/bin/env python3
"""Generate the fictional commuting economy and run its declared experiment."""
import argparse
import csv
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

FLAT = (Path(__file__).resolve().parent / "RESOURCES.json").is_file()
ROOT = Path(__file__).resolve().parent if FLAT else Path(__file__).resolve().parents[4]
SCRIPTS = ROOT if FLAT else ROOT / "skills/econ-data/scripts"
sys.path.insert(0, str(SCRIPTS))
import research_data


def reference(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save_table(path, rows):
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def equilibrium(households, market, subsidy, parameters):
    """Clear the finite labor market and retain original choice/accounting checks."""
    ordered = sorted(households, key=lambda h: (h["reservation"] + h["commute"], h["household_id"]))
    reservation = [h["reservation"] + h["commute"] - subsidy for h in ordered]
    n = len(ordered)
    output = [market["productivity"] * k - market["curvature"] * k * k / 2 for k in range(n + 1)]
    costs = [0.0]
    for value in reservation:
        costs.append(costs[-1] + value)
    employed = max(range(n + 1), key=lambda k: output[k] - costs[k])
    lower = max(reservation[employed - 1] if employed else -float("inf"),
                output[employed + 1] - output[employed] if employed < n else -float("inf"))
    upper = min(reservation[employed] if employed < n else float("inf"),
                output[employed] - output[employed - 1] if employed else float("inf"))
    wage = upper if employed == 0 else lower if employed == n else (lower + upper) / 2
    profit = output[employed] - wage * employed
    rows = []
    for rank, household in enumerate(ordered):
        job = int(rank < employed)
        benefit = wage + subsidy - household["commute"] - household["reservation"]
        fiscal = subsidy * job
        surplus = job * benefit
        welfare = (surplus + profit / n + parameters["external_benefit_per_job"] * job
                   - (1 + parameters["fiscal_excess_burden"]) * fiscal)
        rows.append({"household_id": household["household_id"], "employment": job,
                     "household_surplus": surplus, "firm_profit": profit / n,
                     "fiscal_spending": fiscal, "social_surplus": welfare,
                     "wage": wage})
    firm_deviation = max(output[k] - wage * k - profit for k in range(n + 1))
    household_deviation = max(max(0, wage - value) if k >= employed else max(0, value - wage)
                              for k, value in enumerate(reservation))
    resource_surplus = output[employed] - sum(h["reservation"] + h["commute"] for h in ordered[:employed])
    accounting_error = abs(sum(r["household_surplus"] + r["firm_profit"] - r["fiscal_spending"] for r in rows)
                           - resource_surplus)
    checks = {"firm_profitable_deviation": firm_deviation,
              "household_profitable_deviation": household_deviation,
              "accounting_residual": accounting_error, "supporting_wage_gap": max(0, lower - upper)}
    if max(checks.values()) > parameters["equilibrium_tolerance"]:
        raise ArithmeticError(f"Original equilibrium conditions: {checks}")
    return rows, checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    spec_path = Path(__file__).with_name("commuting-specification.json" if FLAT else "specification.json")
    spec = json.loads(spec_path.read_text())
    p = spec["parameters"]
    dimensions = {"mechanism": spec["mechanism"], "estimand": spec["estimand"],
                  "identifying_variation": spec["identification"], "population": spec["population"],
                  "measurement": "Employment and monetary outcomes over eight weeks; fixed household denominator"}
    formulation = {"specification": reference(spec_path), "judgment": {"owner": "example author", "formulation": {
        "initial": {"question": spec["internal"]["initial_question"],
                    "dimensions": {**dimensions, "estimand": "Finite-population employment assignment effects"}},
        "alternative": {"question": spec["question"], "dimensions": dimensions},
        "comparison": spec["internal"]["upstream_comparison"], "selected": "alternative",
        "rationale": spec["internal"]["decisive_calculation"]}}}
    research_data.write_json(destination / "formulation-contract.json", formulation)
    design_script = ROOT / "research_design.py" if FLAT else ROOT / "skills/econ-design/scripts/research_design.py"
    subprocess.run([sys.executable, str(design_script), "formulate", str(destination / "formulation-contract.json"),
                    "--root", str(ROOT), "--output", str(destination / "formulation.json")],
                   check=True, stdout=subprocess.DEVNULL)
    rng = random.Random(p["population_seed"])
    households, markets, potential, equilibrium_checks = [], [], {}, []
    for j in range(p["markets"]):
        market = {"market_id": f"M{j:02}", "productivity": rng.uniform(*p["market_productivity_uniform"]),
                  "curvature": p["firm_curvature"]}
        markets.append(market)
        residents = [{"household_id": f"H{j:02}{i:03}", "market_id": market["market_id"],
                      "reservation": rng.uniform(*p["reservation_value_uniform"]),
                      "commute": rng.uniform(*p["commuting_cost_uniform"])}
                     for i in range(p["households_per_market"])]
        households.extend(residents)
        for arm, subsidy in p["subsidies"].items():
            rows, checks = equilibrium(residents, market, subsidy, p)
            potential.setdefault(arm, []).extend(rows)
            equilibrium_checks.append({"market_id": market["market_id"], "arm": arm, **checks})
    households.sort(key=lambda h: h["household_id"])
    for rows in potential.values():
        rows.sort(key=lambda h: h["household_id"])
    monetary_unit = spec["unit"]
    meanings = {
        "household_id": ("identifier", "Household identity", "id"),
        "market_id": ("identifier", "Labor market and assignment cluster", "cluster"),
        "reservation": (monetary_unit, "Value of home production", "auxiliary"),
        "commute": (monetary_unit, "Employment commuting resource cost", "auxiliary"),
        "productivity": ("thousand JPY per worker over eight weeks", "Output intercept a", "auxiliary"),
        "curvature": ("thousand JPY per squared worker over eight weeks", "Output curvature b", "auxiliary"),
        "assignment": ("arm label", "Market-wide subsidy assignment", "assignment"),
        "employment": ("employed workers per household", "Employment indicator", "primary_outcome"),
        "household_surplus": (monetary_unit, "Employment utility relative to home production", "secondary_outcome"),
        "firm_profit": (monetary_unit, "Market profit divided by its fixed household count", "secondary_outcome"),
        "fiscal_spending": (monetary_unit, "Subsidy payment to an employed household", "secondary_outcome"),
        "social_surplus": (monetary_unit, "Government objective allocated across the fixed household population", "primary_outcome"),
        "wage": ("thousand JPY per employed worker over eight weeks", "Market-clearing wage", "secondary_outcome"),
        "high_cost_employment": ("employed workers per high-cost household", "Employment times pretreatment high-cost membership divided by its fixed population share", "secondary_outcome")}
    definitions = {name: {"unit": unit, "definition": meaning, "version": spec["specification_id"],
                          "role": role, "source_fields": [name],
                          "timing": "posttreatment" if role.endswith("outcome") else "pretreatment",
                          "rationale": meaning}
                   for name, (unit, meaning, role) in meanings.items()}
    definitions["assignment"]["timing"] = "assignment before employment"
    shared = {}
    for name, rows, key in (("households", households, "household_id"), ("markets", markets, "market_id")):
        source = destination / f"{name}-source.csv"
        save_table(source, rows)
        assembly = {"base": reference(source), "grain": [key],
                    "definitions": {k: definitions[k] for k in rows[0]}}
        research_data.write_json(destination / f"{name}-assembly.json", assembly)
        research_data.assemble(assembly, destination, destination / name)
        shared[name] = destination / name / "analysis.csv"

    arms = list(p["subsidies"])
    common = {"method": "rct_design", "id": "household_id", "outcome": "employment", "regressors": [],
              "endogenous": [], "instruments": [], "population": spec["population"], "period": spec["period"],
              "unit": meanings["employment"][0], "estimand": spec["estimand"],
              "identification": spec["identification"], "assignment": "market-level complete randomization",
              "inference": {"type": "official"},
              "options": {"operation": "assign", "treatment": "assignment", "seed": p["assignment_seed"],
                          "experimental_design": {"conditions": arms, "clusters": "market_id",
                                                  "m_each": [16, 16, 16], "interference": "within_cluster"}}}
    assignment_spec = {**common, "data": str(shared["households"])}
    research_data.write_json(destination / "assignment-spec.json", assignment_spec)
    causal = SCRIPTS / "research_causal.py"
    subprocess.run([sys.executable, str(causal), "run", str(destination / "assignment-spec.json"),
                    "--output", str(destination / "assignment.json")], check=True, stdout=subprocess.DEVNULL)
    assignment = json.loads((destination / "assignment.json").read_text())["diagnostics"]["assignment"]
    labels = dict(zip(assignment["ids"], assignment["condition"], strict=True))
    high_cost_share = sum(h["commute"] >= p["high_cost_threshold"] for h in households) / len(households)
    observed = []
    for i, household in enumerate(households):
        arm = labels[household["household_id"]]
        row = dict(potential[arm][i], assignment=arm)
        row["high_cost_employment"] = row["employment"] * (household["commute"] >= p["high_cost_threshold"]) / high_cost_share
        observed.append(row)
    save_table(destination / "observations-source.csv", observed)
    outcomes = [name for name, (_, _, role) in meanings.items() if role.endswith("outcome")]
    contrasts = [{"name": f"{b}-{a}", "weights": {arm: int(arm == b) - int(arm == a) for arm in arms}}
                 for a, b in ((arms[0], arms[1]), (arms[0], arms[2]), (arms[1], arms[2]))]
    analyses = [{"id": outcome, "runner": "causal", "specification": {
        **common, "outcome": outcome, "unit": meanings[outcome][0],
        "options": {**common["options"], "operation": "analyze", "contrasts": contrasts,
                    "assignment_result": str(destination / "assignment.json")}}} for outcome in outcomes]
    assembly = {key: spec[key] for key in ("question", "population", "observation_unit", "economic_model", "mechanism", "estimand", "identification")}
    assembly.update(base=reference(shared["households"]), joins=[
        {"table": reference(destination / "observations-source.csv"), "left": ["household_id"],
         "right": ["household_id"], "columns": [k for k in observed[0] if k != "household_id"],
         "cardinality": "one_to_one", "unmatched": "error"},
        {"table": reference(shared["markets"]), "left": ["market_id"], "right": ["market_id"],
         "columns": ["productivity", "curvature"], "cardinality": "many_to_one", "unmatched": "error"}],
        grain=["household_id"], definitions=definitions,
        sample={"id": "commuting-roster-v1", "row_id": "household_id", "filters": [],
                "complete_cases": outcomes, "require_common": True}, analyses=analyses)
    research_data.write_json(destination / "analysis-assembly.json", assembly)
    research_data.assemble(assembly, destination, destination / "analysis")
    results = {}
    for outcome in outcomes:
        result_path = destination / f"{outcome}-result.json"
        subprocess.run([sys.executable, str(causal), "run", str(destination / "analysis/analyses" / f"{outcome}.json"),
                        "--output", str(result_path)], check=True, stdout=subprocess.DEVNULL)
        results[outcome] = reference(result_path)
    welfare_result = json.loads((destination / "social_surplus-result.json").read_text())
    changes = {arms[0]: 0.0, **{arm: welfare_result["coefficients"][f"{arm}-{arms[0]}"] for arm in arms[1:]}}
    selected = max(arms, key=lambda arm: (changes[arm], -p["subsidies"][arm]))
    research_data.write_json(destination / "result-index.json", {
        "result_id": spec["specification_id"], "specification": reference(spec_path),
        "producer": reference(Path(__file__)), "python_version": sys.version,
        "formulation": reference(destination / "formulation.json"),
        "results": results, "selected_arm": selected, "estimated_surplus_changes": changes,
        "uncertainty": welfare_result["inference"],
        "internal": {"potential_outcomes": potential, "equilibrium_checks": equilibrium_checks,
                     "high_cost_population_share": high_cost_share, "decision": spec["internal"]["decision"]}})
    print(json.dumps({"result_id": spec["specification_id"], "output": str(destination), "selected_arm": selected}))


if __name__ == "__main__":
    main()
