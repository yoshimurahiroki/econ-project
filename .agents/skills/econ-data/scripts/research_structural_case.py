#!/usr/bin/env python3
"""Run synthetic product-market and dynamic-choice examples.

Usage: research_structural_case.py --output NEW_DIRECTORY
Install the scientific dependencies in requirements-equity.txt first.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import equity
import numpy as np
import pandas as pd
import pyblp
import scipy


def local_checks():
    script = Path(__file__).resolve()
    candidates = [script.parent / "local_checks.py", script.parent / "LOCAL_CHECKS.py"]
    candidates.extend(root / "harness" / "local_checks.py" for root in script.parents)
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        raise FileNotFoundError("the installed local checks resource is required for atomic publication")
    spec = importlib.util.spec_from_file_location("structural_case_local_checks", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, default=equity.json_default, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run(stage):
    pyblp.options.verbose = False
    rng = np.random.default_rng(19020)
    count = 48
    market_ids = np.repeat(np.arange(1, 7), 8)
    quality = rng.normal(size=count)
    cost_shifter = rng.normal(size=count)
    demand_shock = rng.normal(scale=.1, size=count)
    prices = 2.4 + .45 * cost_shifter + .2 * quality + .2 * demand_shock
    utility = 1.2 - 1.2 * prices + .8 * quality + demand_shock
    exp_utility = np.exp(utility)
    shares = exp_utility / (1 + pd.Series(exp_utility).groupby(market_ids).transform('sum').to_numpy())
    products = pd.DataFrame({'market_ids': market_ids, 'product_ids': np.tile(np.arange(1, 9), 6),
                             'firm_ids': np.tile(np.repeat(np.arange(1, 5), 2), 6),
                             'prices': prices, 'shares': shares, 'market_size': 1,
                             'quality': quality, 'demand_instruments0': cost_shifter})
    products.to_csv(stage / "synthetic-products.csv", index=False)
    model = {
        "products": "synthetic-products.csv", "currency": "synthetic currency units",
        "market": "six independently generated markets with eight products each", "as_of": "2026-10-31",
        "price_unit": 1, "quantity_unit": "share per potential consumer",
        "sources": [{"kind": "synthetic", "description": "Seed 19020; independent standard normal quality and cost shifter; independent normal demand shock with standard deviation 0.1. Prices equal 2.4 + 0.45 cost shifter + 0.2 quality + 0.2 demand shock. Utility equals 1.2 - 1.2 prices + 0.8 quality + demand shock; logit shares include an outside option."}],
        "identification": "The generated cost shifter enters price and is independent of the generated demand shock conditional on quality.",
        "demand": {"linear": "1 + prices + quality"},
        "counterfactual": {"product_changes": {"firm_ids": products.firm_ids.where(products.firm_ids != 2, 1).tolist()},
                           "source": [{"kind": "synthetic", "description": "combine the ownership of synthetic firms 1 and 2"}]},
    }
    write_json(stage / "synthetic-market-spec.json", model)
    result = equity.fit({**model, "products": str(stage / "synthetic-products.csv")})
    write_json(stage / "synthetic-market-result.json", result)
    labels = result["coefficient_labels"]["beta"]
    betas = np.asarray(result["coefficients"]["beta"]).ravel()
    alpha = float(betas[labels.index("prices")])
    summary = {
        "source": "seeded synthetic data", "market_size": "1 per market; no population scaling",
        "coefficients": dict(zip(labels, betas)),
        "consumer_surplus_formula": "mean across markets of -log(outside share)/(-price coefficient), homogeneous logit, per potential consumer",
        "units": "synthetic currency units per product for price; synthetic currency units per potential consumer for profit and surplus",
        "estimation_residuals": result["solution_residuals"],
    }
    for scenario in ("baseline", "counterfactual"):
        rows = result[scenario]["products"]
        shares_by_market = defaultdict(float)
        for row in rows:
            shares_by_market[row["market_ids"]] += row["share"]
        markets = len(shares_by_market)
        summary[scenario] = {
            "mean_product_price": sum(row["price"] for row in rows) / len(rows),
            "mean_inside_share": sum(row["quantity"] for row in rows) / markets,
            "mean_gross_profit": sum(row["gross_profit"] for row in rows) / markets,
            "mean_consumer_surplus": sum(-math.log(1 - share) / -alpha for share in shares_by_market.values()) / markets,
        }
    for field in ("profit_gradient_max_abs", "profit_hessian_max_eigenvalue"):
        summary["counterfactual"][field] = result["counterfactual"][field]
    write_json(stage / "synthetic-market-summary.json", summary)

    profiles = [{"state": state, "actions": [action], "payoffs": [float(state == "high")],
                 "payoff_features": {"effect": [action], "fixed": [action]},
                 "transitions": {"high" if action else "low": 1}}
                for state in ("low", "high") for action in (0, 1)]
    observations = [{"market_id": state, "period": k, "state": state, "actions": [int(k < 30)],
                     "next_state": "high" if k < 30 else "low"}
                    for state in ("low", "high") for k in range(40)]
    changed = copy.deepcopy(profiles)
    for row in changed:
        row["payoffs"][0] += .7 * row["actions"][0]
    game = {
        "firms": ["A"], "states": ["low", "high"], "profiles": profiles, "observations": observations,
        "discount_factor": .5, "shock_scale": 1, "flow_timing": "current",
        "action_timing": "action affects current payoff", "shock_role": "choice_only",
        "flow_definition": "unlevered_after_tax_cash_flow_excluding_financial_assets",
        "parameters": [{"name": "effect", "initial": 0, "bounds": [-2, 2]}, {"name": "fixed", "value": .4}],
        "currency": "JPY", "amount_unit": 1, "market": "synthetic", "as_of": "2026-10-31",
        "sources": [{"kind": "synthetic", "description": "Two states, 30 actions and 10 waits each; deterministic transitions to high after action and low after wait."}],
        "identification": {"parameters": [{"name": "effect", "role": "payoff", "moments": ["action frequency"],
            "variation": "both actions observed", "exclusion": "fixed payoff and shock scale", "source": "synthetic observations"}]},
        "counterfactual": {"profiles": changed},
    }
    dynamic_results = {}
    for method in ("nfxp", "mpec"):
        spec = {**game, **({"estimation_method": "mpec"} if method == "mpec" else {})}
        write_json(stage / f"dynamic-{method}-spec.json", spec)
        dynamic_results[method] = equity.dynamic(spec)
        write_json(stage / f"dynamic-{method}-result.json", dynamic_results[method])
    mpec = dynamic_results["mpec"]
    def action_share(scenario):
        return next(row["choice_share"] for row in mpec[scenario]["policies"]
                    if row["state"] == "low" and row["action"] == 1)
    price_unit = "synthetic currency units per product"
    welfare_unit = "synthetic currency units per potential consumer"
    statistics = {
        "synthetic_market_price_coefficient": {"value": alpha, "unit": "utility per synthetic currency unit"},
        "synthetic_market_baseline_price": {"value": summary["baseline"]["mean_product_price"], "unit": price_unit},
        "synthetic_market_merger_price": {"value": summary["counterfactual"]["mean_product_price"], "unit": price_unit},
        "synthetic_market_baseline_surplus": {"value": summary["baseline"]["mean_consumer_surplus"], "unit": welfare_unit},
        "synthetic_market_merger_surplus": {"value": summary["counterfactual"]["mean_consumer_surplus"], "unit": welfare_unit},
        "synthetic_market_baseline_profit": {"value": summary["baseline"]["mean_gross_profit"], "unit": welfare_unit},
        "synthetic_market_merger_profit": {"value": summary["counterfactual"]["mean_gross_profit"], "unit": welfare_unit},
        "synthetic_market_merger_foc_residual": {"value": summary["counterfactual"]["profit_gradient_max_abs"], "unit": "share"},
        "dynamic_payoff_effect": {"value": mpec["estimation"]["parameters"]["effect"], "unit": "flow payoff units"},
        "dynamic_baseline_action_share": {"value": action_share("baseline"), "unit": "probability"},
        "dynamic_changed_action_share": {"value": action_share("counterfactual"), "unit": "probability"},
        "dynamic_bellman_residual": {"value": mpec["estimation"]["bellman_max_abs_error"], "unit": "value units"},
        "dynamic_policy_residual": {"value": mpec["estimation"]["policy_max_abs_error"], "unit": "probability"},
    }
    write_json(stage / "statistics.json", statistics)
    write_json(stage / "provenance.json", {
        "synthetic_source": {"seed": 19020, "description": model["sources"][0]["description"]},
        "generated_data_sha256": digest(stage / "synthetic-products.csv"),
        "spec_sha256": {name: digest(stage / name) for name in
                        ("synthetic-market-spec.json", "dynamic-nfxp-spec.json", "dynamic-mpec-spec.json")},
        "producer_sha256": digest(Path(__file__).resolve()),
        "engine_sha256": {name: digest(Path(equity.__file__).resolve().parent / name)
                          for name in ("equity.py", "equity_io.py")},
        "versions": {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__,
                     "scipy": scipy.__version__, "pyblp": pyblp.__version__},
        "dynamic_source": "synthetic finite-state action counts and transitions",
    })


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new output directory")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        parser.error(f"output already exists: {output}")
    if not output.parent.is_dir():
        parser.error(f"output parent must exist: {output.parent}")
    gate = local_checks()
    with tempfile.TemporaryDirectory(prefix=".structural-case-", dir=output.parent) as temp:
        stage = Path(temp)
        run(stage)
        try:
            gate.atomic_publish(stage, output)
        except FileExistsError:
            parser.error(f"output already exists: {output}")
    print(f"Saved structural examples to {output}")


if __name__ == "__main__":
    main()
