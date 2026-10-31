#!/usr/bin/env python3
"""Estimate product markets and value equity from explicit, source-backed inputs.

Usage: equity.py {fit,dynamic,value,reverse,update} [input.json|-] [-o output.json]
Money fields share ``currency`` and ``amount_unit``; share counts use
``share_unit``. Market prices use ``price_unit`` currency units per product.
JSON inputs contain data and parameters, never Python expressions or pickles.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import pandas as pd
from scipy.optimize import brentq


def number(value, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name}: supply a numeric value")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError(f"{name}: supply a finite {'positive ' if positive else ''}value")
    return result


def records(value) -> pd.DataFrame:
    if isinstance(value, str):
        return pd.read_csv(value, dtype={k: str for k in ("market_ids", "product_ids", "firm_ids", "nesting_ids")})
    if isinstance(value, (list, dict)):
        return pd.DataFrame(value)
    raise ValueError("products and agents must be records, columns, or a local CSV path")


def provenance(spec: dict) -> list:
    sources = spec["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("sources must identify the input documents or an explicitly synthetic example")
    for source in sources:
        if source.get("kind") == "synthetic":
            if not source.get("description"):
                raise ValueError("synthetic sources require their construction description")
        elif not (source.get("url") or source.get("source_url") or source.get("path")):
            raise ValueError("each source requires its URL or local document path")
    return sources


def select_model(spec: dict, products: pd.DataFrame, agents: pd.DataFrame | None) -> tuple[dict, dict]:
    """Apply the adopted economic ranking after data and moment conditions."""
    candidates = spec.get("candidates")
    if not candidates:
        return spec, {"selected": "adopted_formulation"}
    requested = spec.get("model", "auto")
    instruments = [c for c in products if c.startswith("demand_instruments")]
    z = products[instruments].to_numpy(dtype=float)
    if not np.isfinite(z).all():
        raise ValueError("demand instruments must contain finite values")
    rank = int(np.linalg.matrix_rank(z))
    eligible, conditions = [], []
    for position, candidate in enumerate(candidates):
        requirements = candidate["requires"]
        product_fields = set(requirements.get("product_fields", []))
        agent_fields = set(requirements.get("agent_fields", []))
        data_fields = set(agents.columns) if agents is not None else set()
        demand = candidate["demand"]
        nonlinear = bool(demand.get("nonlinear"))
        solve = candidate.get("solve", spec.get("solve", {}))
        nested = "rho" in solve
        has_nodes = agents is not None and "weights" in agents and any(c.startswith("nodes") for c in agents)
        integration = candidate.get("integration", spec.get("integration"))
        engine_inputs = ((not nonlinear or ("sigma" in solve and (integration is not None or has_nodes)))
                         and (not nested or "nesting_ids" in products)
                         and (not candidate.get("agent_formula") or agents is not None))
        roles = ["price"] + (["heterogeneity"] if nonlinear else []) + (["nesting"] if nested else [])
        if candidate.get("supply"):
            roles.append("cost")
        if candidate.get("agent_formula"):
            roles.append("demographic")
        identification = candidate.get("identification")
        moment_conditions = _identification_conditions(identification, products, agents, roles)
        # Existing fixed linear specifications retain their adopted explanation.
        if not nonlinear and not nested and not candidate.get("supply") and isinstance(identification, str):
            moment_conditions = [] if identification.strip() else ["supply the economic identification argument"]
        satisfied = (engine_inputs and not moment_conditions and product_fields.issubset(products.columns)
                     and agent_fields.issubset(data_fields)
                     and rank >= int(requirements["instrument_rank"])
                     and products.market_ids.nunique() >= int(requirements.get("markets", 1))
                     and (requested == "auto" or requested == candidate["name"]))
        conditions.append({"name": candidate["name"], "input_conditions_satisfied": bool(satisfied),
                           "parameter_moment_conditions": moment_conditions})
        if satisfied:
            if not candidate.get("identification"):
                raise ValueError(f"{candidate['name']} requires its economic identification argument")
            priority = number(candidate.get("selection_priority", -position), "selection_priority")
            if "selection_priority" in candidate and not candidate.get("selection_reason"):
                raise ValueError("selection_priority requires the economic reason for the ranking")
            eligible.append(((priority, -position), candidate))
    if not eligible:
        raise ValueError("no candidate satisfies its market-data, parameter-moment and engine conditions")
    selected = max(eligible, key=lambda x: x[0])[1]
    chosen = {key: copy.deepcopy(value) for key, value in spec.items() if key != "candidates"}
    chosen.update({key: copy.deepcopy(value) for key, value in selected.items() if key not in {"name", "requires"}})
    return chosen, {"mode": requested, "selected": selected["name"], "excluded_instrument_rank": rank,
                    "criterion": selected.get("selection_reason", "first eligible specification in the adopted candidate order"),
                    "candidates": conditions}


def _identification_conditions(identification, products=None, agents=None, roles=()):
    if not isinstance(identification, dict) or not identification.get("parameters"):
        return ["supply parameter-specific moments, variation, exclusion and source records"]
    conditions, covered = [], set()
    available = set(products.columns) if products is not None else set()
    if agents is not None:
        available.update(agents.columns)
    for item in identification["parameters"]:
        label = item.get("name", "parameter")
        for field in ("name", "role", "moments", "variation", "exclusion", "source"):
            if not item.get(field):
                conditions.append(f"{label}: supply {field}")
        if not isinstance(item.get("moments"), list):
            conditions.append(f"{label}: moments must list the identifying fields or action comparisons")
        elif available and not set(item["moments"]).issubset(available):
            conditions.append(f"{label}: identifying moment fields are absent from the observations")
        covered.add(item.get("role"))
    conditions.extend(f"supply the {role} parameter's identifying moments" for role in roles if role not in covered)
    return conditions


def fit(spec: dict) -> dict:
    """Use PyBLP's estimator, derivatives and equilibrium solver directly."""
    sources = provenance(spec)
    if spec.get("model") == "cournot":
        from equity_io import cournot
        conditions = _identification_conditions(spec.get("identification"), roles=["demand"])
        if conditions:
            raise ValueError("; ".join(conditions))
        return {**cournot(spec), "market": spec["market"], "as_of": spec["as_of"],
                "currency": spec["currency"], "price_unit": spec["price_unit"],
                "quantity_unit": spec["quantity_unit"], "sources": sources,
                "identification": spec["identification"]}
    import pyblp
    products = records(spec["products"])
    required = {"market_ids", "product_ids", "firm_ids", "prices", "shares", "market_size"}
    absent = sorted(required - set(products.columns))
    if absent:
        raise ValueError(f"products requires {', '.join(absent)}")
    if products.duplicated(["market_ids", "product_ids"]).any():
        raise ValueError("market_ids and product_ids must identify one product observation")
    numeric = products[["prices", "shares", "market_size"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or (numeric <= 0).any():
        raise ValueError("prices, shares, and market_size must be finite and positive")
    markets = products.groupby("market_ids", sort=False)
    if (markets.shares.sum() >= 1).any() or (markets.market_size.nunique() != 1).any():
        raise ValueError("each market needs an outside share and a common market_size")
    if not any(c.startswith("demand_instruments") for c in products):
        raise ValueError("supply excluded demand_instruments0, ... for endogenous prices")
    agent_data = records(spec["agents"]) if "agents" in spec else None
    spec, selection = select_model(spec, products, agent_data)
    if not spec.get("identification"):
        raise ValueError("identification must describe market boundaries and instrument exclusion")
    currency = spec["currency"]
    price_unit = number(spec["price_unit"], "price_unit", positive=True)
    demand = spec["demand"]
    linear = demand["linear"]
    nonlinear = demand.get("nonlinear")
    supply = spec.get("supply")
    agent_formula = pyblp.Formulation(spec["agent_formula"]) if "agent_formula" in spec else None
    formulations = (
        pyblp.Formulation(linear, absorb=demand.get("absorb")),
        pyblp.Formulation(nonlinear) if nonlinear else None,
        pyblp.Formulation(supply["formula"], absorb=supply.get("absorb")) if supply else None,
    )
    integration = None
    if nonlinear:
        if "integration" in spec:
            config = spec["integration"]
            integration = pyblp.Integration(config["method"], int(config["size"]), config.get("options"))
        elif agent_data is None:
            raise ValueError("random coefficients require integration or agent nodes and weights")
    elif agent_data is not None or agent_formula is not None:
        raise ValueError("agent data requires a nonlinear demand formulation")
    nested = "rho" in spec.get("solve", {})
    if nonlinear or nested or supply:
        roles = ["price"] + (["heterogeneity"] if nonlinear else []) + (["nesting"] if nested else [])
        roles += ["cost"] if supply else []
        roles += ["demographic"] if agent_formula is not None else []
        conditions = _identification_conditions(spec["identification"], products, agent_data, roles)
        if conditions:
            raise ValueError("; ".join(conditions))
    if not nested and "nesting_ids" in products:
        products = products.drop(columns="nesting_ids")
    model = ("random_coefficients_" if nonlinear else "") + ("nested_logit" if nested else "logit")
    solve = dict(spec.get("solve", {}))
    # Estimator controls are passed through to the package; the chosen model is
    # never replaced by another estimator after an unsuccessful solve.
    solve.setdefault("method", "2s")
    solve["error_behavior"] = "raise"
    if nonlinear and "sigma" not in solve:
        raise ValueError("solve.sigma must specify the adopted nonlinear parameters")
    if nested and "rho" not in solve:
        raise ValueError("solve.rho must specify the adopted nesting parameters")
    if "optimization" in solve:
        config = solve.pop("optimization")
        solve["optimization"] = pyblp.Optimization(config["method"], config.get("options"))
    if "iteration" in solve:
        config = solve.pop("iteration")
        solve["iteration"] = pyblp.Iteration(config["method"], config.get("options"))
    problem = pyblp.Problem(
        formulations, products, agent_formula, agent_data, integration,
        rc_types=spec.get("rc_types"), costs_type=spec.get("costs_type", "linear"),
    )
    result = problem.solve(**solve)
    if not result.converged or not np.asarray(result.fp_converged).all():
        raise ArithmeticError("PyBLP did not satisfy its optimization or share-contraction criterion")
    gradient_norm = float(np.asarray(result.projected_gradient_norm).item()) if result.theta.size else 0.0
    gradient_tolerance = number(spec.get("gradient_tolerance", 1e-5), "gradient_tolerance", positive=True)
    share_error = float(np.max(np.abs(result.compute_shares().ravel() - products.shares.to_numpy())))
    share_tolerance = number(spec.get("share_tolerance", 1e-8), "share_tolerance", positive=True)
    if not math.isfinite(gradient_norm) or gradient_norm > gradient_tolerance or share_error > share_tolerance:
        raise ArithmeticError(f"estimation residuals exceed the supplied tolerances: gradient={gradient_norm}, shares={share_error}")
    costs = result.compute_costs()
    diagonal = result.extract_diagonals(result.compute_demand_jacobians())
    if not np.isfinite(costs).all() or (diagonal >= 0).any():
        raise ArithmeticError("the fitted model requires finite costs and downward own-price demand")
    outcome = _market_outcomes(products, products.prices, products.shares, costs, currency, price_unit)
    payload = {
        "model": model, "selection": selection, "engine": "pyblp", "engine_version": pyblp.__version__,
        "market": spec["market"], "as_of": spec["as_of"],
        "identification": spec["identification"], "currency": currency,
        "sources": sources,
        "price_unit": price_unit, "quantity_unit": spec["quantity_unit"],
        "observations": len(products), "markets": int(products.market_ids.nunique()),
        "coefficients": {"beta": result.beta, "sigma": result.sigma, "pi": result.pi,
                         "rho": result.rho, "gamma": result.gamma},
        "standard_errors": {"beta": result.beta_se, "sigma": result.sigma_se, "pi": result.pi_se,
                            "rho": result.rho_se, "gamma": result.gamma_se},
        "coefficient_labels": {"beta": result.beta_labels, "sigma": result.sigma_labels,
                               "pi": result.pi_labels, "rho": result.rho_labels, "gamma": result.gamma_labels},
        "objective": float(result.objective), "converged": True,
        "solution_residuals": {"projected_gradient_norm": gradient_norm, "gradient_tolerance": gradient_tolerance,
                               "share_max_abs_error": share_error, "share_tolerance": share_tolerance},
        "baseline": outcome,
    }
    if spec.get("model") == "conditional_logit":
        from equity_io import conditional_logit
        if nonlinear or nested or supply or "reference_price" not in linear:
            raise ValueError("conditional_logit uses homogeneous demand in prices-reference_price and no supply equation")
        reference = records(spec["reference_products"])
        if not required.issubset(reference.columns) or reference.market_ids.duplicated().any():
            raise ValueError("reference_products requires one complete reference product per market")
        lookup = reference.set_index("market_ids")
        if set(lookup.index) != set(products.market_ids) or not np.allclose(
                products.reference_price, products.market_ids.map(lookup.prices), atol=1e-10, rtol=0):
            raise ValueError("reference_price must equal the reference product price in the same market")
        if "year" in products:
            market_years = products.groupby("market_ids").year
            if market_years.nunique().max() != 1:
                raise ValueError("a conditional market must identify one observation year")
            years = reference.market_ids.map(market_years.first())
            if "year" in reference and not reference.year.equals(years):
                raise ValueError("reference products must use the same market year")
            reference["year"] = years
        complete = pd.concat([products, reference], ignore_index=True)
        if complete.duplicated(["market_ids", "product_ids"]).any() or (complete.shares <= 0).any():
            raise ValueError("reference and inside products must have distinct IDs and positive shares")
        if complete.groupby("market_ids").market_size.nunique().max() != 1:
            raise ValueError("conditional products and reference must share the observed market size")
        alpha = np.asarray(diagonal).ravel() / (products.shares.to_numpy() * (1-products.shares.to_numpy()))
        if not np.allclose(alpha, alpha[0], rtol=1e-8, atol=1e-12):
            raise ValueError("conditional_logit requires a common own-price coefficient")
        conditional = conditional_logit(complete, float(alpha[0]), spec.get("counterfactual"))
        payload.update(model="conditional_logit", price_coefficient=float(alpha[0]),
                       market_scope="fixed_total_choice_among_all_observed_products",
                       observations=len(complete), reference_products=reference.to_dict(orient="records"))
        payload["baseline"] = _market_outcomes(complete, complete.prices, complete.shares,
                                                conditional["baseline_costs"], currency, price_unit)
        negative = complete.loc[conditional["baseline_costs"] < 0, ["market_ids", "product_ids", "firm_ids"]]
        payload["cost_support"] = {"negative_marginal_cost_count": len(negative),
                                   "negative_marginal_cost_fraction": len(negative)/len(complete),
                                   "affected_products": negative.to_dict(orient="records"),
                                   "minimum_unit_cost": float(np.min(conditional["baseline_costs"]))*price_unit}
        if "counterfactual" in spec:
            payload["counterfactual"] = _market_outcomes(conditional["products"], conditional["prices"],
                conditional["shares"], conditional["costs"], currency, price_unit)
            payload["counterfactual"]["equilibrium_residuals"] = conditional["equilibrium_residuals"]
            payload["counterfactual"]["source"] = spec["counterfactual"].get("source", [])
    elif "counterfactual" in spec:
        cf = spec["counterfactual"]
        new_products = products.copy()
        for name, values in cf.get("product_changes", {}).items():
            if name in {"market_ids", "product_ids", "shares", "prices"}:
                raise ValueError(f"counterfactual product_changes cannot change {name}")
            new_products[name] = values
        new_costs = np.asarray(cf.get("costs", costs), dtype=float).reshape(-1, 1)
        if len(new_costs) != len(products) or not np.isfinite(new_costs).all():
            raise ValueError("counterfactual costs must give one finite cost per product")
        utility_shift = np.broadcast_to(np.asarray(cf.get("utility_shift", 0), dtype=float), (len(products),))
        # Recovered fixed effects enter xi so the same estimated utilities are
        # preserved when Simulation uses the unabsorbed design matrix.
        raw_x1 = pyblp.build_matrix(pyblp.Formulation(linear), products)
        xi = result.delta - raw_x1 @ result.beta + utility_shift[:, None]
        simulation = pyblp.Simulation(
            (pyblp.Formulation(linear), pyblp.Formulation(nonlinear) if nonlinear else None),
            new_products, beta=result.beta, sigma=result.sigma if nonlinear else None,
            pi=result.pi if agent_formula is not None else None,
            rho=result.rho if nested else None, xi=xi,
            agent_formulation=agent_formula, agent_data=agent_data,
            integration=integration, rc_types=spec.get("rc_types"),
        )
        changed = simulation.replace_endogenous(
            costs=new_costs, prices=products.prices.to_numpy()[:, None],
            iteration=pyblp.Iteration("simple", {"atol": 1e-12}), error_behavior="raise",
        )
        if not np.asarray(changed.fp_converged).all():
            raise ArithmeticError("counterfactual price equilibrium did not converge")
        payload["counterfactual"] = _market_outcomes(
            new_products, changed.product_data.prices, changed.product_data.shares,
            new_costs, currency, price_unit,
        )
        payload["counterfactual"]["profit_gradient_max_abs"] = float(
            max(np.max(np.abs(x)) for market in changed.profit_gradients.values() for x in market.values())
        )
        max_eigenvalue = float(max(np.max(x) for market in changed.profit_hessian_eigenvalues.values() for x in market.values()))
        tolerance = number(cf.get("equilibrium_tolerance", 1e-8), "equilibrium_tolerance", positive=True)
        if payload["counterfactual"]["profit_gradient_max_abs"] > tolerance or max_eigenvalue > tolerance:
            raise ArithmeticError("counterfactual prices must satisfy firm profit first- and second-order conditions")
        payload["counterfactual"]["profit_hessian_max_eigenvalue"] = max_eigenvalue
        payload["counterfactual"]["source"] = cf.get("source", [])
    payload["input_sha256"] = hashlib.sha256(
        (complete if spec.get("model") == "conditional_logit" else products).to_json(
            orient="split", double_precision=15).encode()
    ).hexdigest()
    return payload


def dynamic(spec: dict) -> dict:
    from equity_io import dynamic_game
    sources = provenance(spec)
    conditions = _identification_conditions(spec.get("identification"))
    if conditions:
        raise ValueError("; ".join(conditions))
    return {**dynamic_game(spec), "market": spec["market"], "as_of": spec["as_of"],
            "sources": sources, "identification": spec["identification"]}


def _market_outcomes(products, prices, shares, costs, currency, price_unit):
    columns = [c for c in ("market_ids", "product_ids", "firm_ids", "year") if c in products]
    output = products[columns].copy()
    output["price"] = np.asarray(prices).ravel() * price_unit
    output["unit_cost"] = np.asarray(costs).ravel() * price_unit
    output["share"] = np.asarray(shares).ravel()
    output["quantity"] = output.share.to_numpy() * products.market_size.to_numpy()
    output["revenue"] = output.price * output.quantity
    output["gross_profit"] = (output.price - output.unit_cost) * output.quantity
    keys = ["market_ids", "firm_ids"] + (["year"] if "year" in output else [])
    firms = output.groupby(keys, sort=False, as_index=False)[["quantity", "revenue", "gross_profit"]].sum()
    return {"currency": currency, "amount_unit": 1,
            "products": output.to_dict(orient="records"),
            "market_firms": firms.to_dict(orient="records")}


def _discount(rows, default_rate):
    factors, rates = [], []
    factor = 1.0
    for row in rows:
        rate = number(row.get("discount_rate", default_rate), "discount_rate")
        if rate <= -1:
            raise ValueError("discount_rate must exceed -1")
        factor /= 1 + rate
        factors.append(factor)
        rates.append(rate)
    return np.asarray(factors), rates


def _fcff(model):
    forecasts = list(model["forecasts"])
    advantage = model.get("competitive_advantage")
    if advantage:
        years = number(advantage["years"], "competitive_advantage.years")
        if years < 0 or years != int(years):
            raise ValueError("competitive_advantage.years must be a nonnegative integer")
        for year in range(int(years)):
            continuation = {**copy.deepcopy(advantage["forecast"]), "advantage_year": year + 1}
            if forecasts:
                continuation.pop("invested_capital_begin", None)
            forecasts.append(continuation)
    if not forecasts:
        raise ValueError("forecasts requires at least one annual period")
    rows = []
    capital = model.get("invested_capital_begin")
    for year, item in enumerate(forecasts, 1):
        row = dict(item)
        if "segments" in row:
            if "io" in row or "io_model" in row:
                raise ValueError("an annual forecast uses segments or one IO market aggregation")
            parts = []
            for segment in row["segments"]:
                part = dict(segment)
                provenance(part)
                if not part.get("name") or not part.get("quantity_unit"):
                    raise ValueError("physical segments require name and quantity_unit")
                scale = number(part["price_unit"], "segment.price_unit", positive=True) / model["amount_unit"]
                if "quantity" in part:
                    quantity = number(part["quantity"], "segment.quantity")
                else:
                    capacity = number(part["capacity"], "segment.capacity", positive=True)
                    utilization = number(part["utilization"], "segment.utilization")
                    if not 0 <= utilization <= 1:
                        raise ValueError("segment utilization must lie between zero and one")
                    quantity = capacity * utilization
                if "capacity" in part and quantity > number(part["capacity"], "segment.capacity", positive=True):
                    raise ValueError("segment quantity exceeds its productive capacity")
                price = number(part["price"], "segment.price")
                unit_cost = number(part["unit_variable_cost"], "segment.unit_variable_cost")
                slope = number(part.get("cost_slope", 0), "segment.cost_slope")
                if min(quantity, price, unit_cost, slope) < 0:
                    raise ValueError("segment quantity, price and variable-cost coefficients must be nonnegative")
                revenue = quantity * price * scale
                variable_cost = (unit_cost * quantity + .5 * slope * quantity**2) * scale
                part.update(quantity=quantity, revenue=revenue, variable_cost=variable_cost,
                            gross_profit=revenue-variable_cost)
                parts.append(part)
            if not parts or len({part["name"] for part in parts}) != len(parts):
                raise ValueError("physical segments require distinct business names")
            row["segments"] = parts
            for field in ("revenue", "gross_profit", "fixed_cash_cost", "depreciation", "change_working_capital"):
                row[field] = math.fsum(number(part[field], f"segment.{field}") for part in parts)
                if field not in {"revenue", "gross_profit"}:
                    row[field] += number(row.get(f"corporate_{field}", 0), f"corporate_{field}")
            corporate_fields = ("corporate_maintenance_capex", "corporate_growth_capex")
            corporate_split = any(field in row for field in corporate_fields)
            if corporate_split:
                corporate_investment = math.fsum(number(row[field], field) for field in corporate_fields)
                if "corporate_capex" in row and not math.isclose(
                        number(row["corporate_capex"], "corporate_capex"), corporate_investment,
                        rel_tol=1e-10, abs_tol=1e-10):
                    raise ValueError("corporate_capex must match its maintenance and growth components")
            else:
                corporate_investment = number(row.get("corporate_capex", 0), "corporate_capex")
            split = (all("maintenance_capex" in part and "growth_capex" in part for part in parts)
                     and (corporate_split or "corporate_capex" not in row))
            if split:
                for field in ("maintenance_capex", "growth_capex"):
                    row[field] = math.fsum(number(part[field], f"segment.{field}") for part in parts)
                    row[field] += number(row.get(f"corporate_{field}", 0), f"corporate_{field}")
            else:
                row.pop("maintenance_capex", None)
                row.pop("growth_capex", None)
                row["capex"] = corporate_investment
                for part in parts:
                    if "maintenance_capex" in part and "growth_capex" in part:
                        row["capex"] += number(part["maintenance_capex"], "maintenance_capex") + number(part["growth_capex"], "growth_capex")
                    else:
                        row["capex"] += number(part["capex"], "segment.capex")
                row["capex_split"] = "not_fully_identified"
        if "io_model" in row:
            link = row["io_model"]
            result = fit(link["spec"])
            outcome = link.get("outcome", "baseline")
            if outcome not in {"baseline", "counterfactual"}:
                raise ValueError("io_model.outcome must be baseline or counterfactual")
            unsupported = [p for p in result.get("cost_support", {}).get("affected_products", [])
                           if p["market_ids"] in link["market_ids"]]
            if unsupported and not link.get("negative_cost_interpretation"):
                raise ValueError("selected IO markets include negative recovered marginal costs; supply an economic interpretation or revise the identified model")
            row["io"] = {**result[outcome], "firm_id": link["firm_id"], "market_ids": link["market_ids"]}
            row["io_result"] = result
        if "io" in row:
            io = row["io"]
            if io["currency"] != model["currency"]:
                raise ValueError("IO profits and valuation must use the same currency")
            negative_costs = [p for p in io.get("products", []) if p["market_ids"] in io["market_ids"]
                              and number(p["unit_cost"], "io.product.unit_cost") < 0]
            interpretation = io.get("negative_cost_interpretation") or row.get("io_model", {}).get("negative_cost_interpretation")
            if negative_costs and not interpretation:
                raise ValueError("selected IO outcome includes negative marginal costs; supply an economic interpretation or revise the identified model")
            selected = [r for r in io["market_firms"] if r["firm_ids"] == io["firm_id"]
                        and r["market_ids"] in io["market_ids"]]
            if len({r["market_ids"] for r in selected}) != len(io["market_ids"]):
                raise ValueError("IO forecast requires one firm record for every selected market")
            if len(selected) != len(io["market_ids"]):
                raise ValueError("IO market-firm records must be unique")
            scale = number(io["amount_unit"], "io.amount_unit", positive=True) / model["amount_unit"]
            row["revenue"] = math.fsum(r["revenue"] for r in selected) * scale
            row["gross_profit"] = math.fsum(r["gross_profit"] for r in selected) * scale
        da = number(row["depreciation"], "depreciation")
        if "ebit" in row and "io" not in row and "segments" not in row:
            ebit = number(row["ebit"], "ebit")
        elif "gross_profit" in row:
            ebit = number(row["gross_profit"], "gross_profit") - number(row["fixed_cash_cost"], "fixed_cash_cost") - da
        else:
            ebit = number(row["revenue"], "revenue") * number(row["ebit_margin"], "ebit_margin")
        tax = number(row["tax_rate"], "tax_rate")
        if not 0 <= tax <= 1:
            raise ValueError("tax_rate must be between zero and one")
        cash_tax = number(row.get("cash_taxes", max(0, ebit) * tax), "cash_taxes")
        if "maintenance_capex" in row or "growth_capex" in row:
            maintenance = number(row["maintenance_capex"], "maintenance_capex")
            growth_capex = number(row["growth_capex"], "growth_capex")
            if min(maintenance, growth_capex) < 0:
                raise ValueError("maintenance and growth capital expenditure must be nonnegative")
            row["capex"] = maintenance + growth_capex
        capex = number(row["capex"], "capex")
        working = number(row["change_working_capital"], "change_working_capital")
        nopat = ebit - cash_tax
        row.update(period=year, ebit=ebit, nopat=nopat, reinvestment=capex - da + working,
                   fcff=nopat + da - capex - working)
        if "invested_capital_begin" in row or capital is not None:
            capital = number(row.get("invested_capital_begin", capital), "invested_capital_begin", positive=True)
            rate = number(row.get("discount_rate", model.get("discount_rate")), "discount_rate")
            closing_capital = capital + row["reinvestment"]
            row.update(invested_capital_begin=capital, invested_capital_end=closing_capital,
                       roic=nopat / capital, economic_profit=nopat - rate * capital)
            capital = closing_capital
        if "incremental_roic_lag" in model:
            lag = number(model["incremental_roic_lag"], "incremental_roic_lag")
            if lag < 0 or lag != int(lag):
                raise ValueError("incremental_roic_lag must be a nonnegative number of years")
            prior_nopat = rows[-1]["nopat"] if rows else model.get("prior_nopat")
            investment_period = year - int(lag)
            if prior_nopat is not None and investment_period >= 1:
                investment = row["reinvestment"] if lag == 0 else rows[investment_period-1]["reinvestment"]
                change = nopat - number(prior_nopat, "prior_nopat")
                row["incremental_return"] = {"nopat_change": change, "investment_period": investment_period,
                                             "net_reinvestment": investment,
                                             "incremental_roic": change / investment if investment != 0 else None}
        # Financing is displayed separately from operating FCFF. Financial assets
        # and their income are not both capitalized in the enterprise value.
        if "interest_expense" in row or "financial_income" in row:
            expense = number(row.get("interest_expense", 0), "interest_expense")
            income = number(row.get("financial_income", 0), "financial_income")
            row["net_income"] = nopat + (income - expense) * (1 - tax)
        rows.append(row)
    factors, rates = _discount(rows, model.get("discount_rate"))
    terminal = model["terminal"]
    growth = number(terminal["growth"], "terminal.growth")
    rate = number(terminal.get("discount_rate", rates[-1]), "terminal.discount_rate")
    if growth >= rate:
        raise ValueError("terminal growth must be below the terminal discount rate")
    if terminal.get("competitive"):
        if "fcff" in terminal or "nopat" in terminal:
            raise ValueError("competitive terminal NOPAT is computed from closing invested capital")
        terminal_capital = number(rows[-1]["invested_capital_end"], "terminal invested capital", positive=True)
        terminal_nopat = rate * terminal_capital
        terminal_reinvestment = growth * terminal_capital
        terminal_fcff = terminal_nopat - terminal_reinvestment
    elif "fcff" in terminal:
        terminal_fcff = number(terminal["fcff"], "terminal.fcff")
        terminal_reinvestment = None
    else:
        roic = number(terminal["roic"], "terminal.roic", positive=True)
        terminal_nopat = number(terminal.get("nopat", rows[-1]["nopat"] * (1 + growth)), "terminal.nopat")
        terminal_reinvestment = terminal_nopat * growth / roic
        terminal_fcff = terminal_nopat - terminal_reinvestment
    terminal_value = terminal_fcff / (rate - growth)
    for row, factor in zip(rows, factors):
        row["discount_factor"] = float(factor)
        row["present_value_fcff"] = row["fcff"] * factor
    operating_value = math.fsum(r["present_value_fcff"] for r in rows) + terminal_value * factors[-1]
    return {"basis": "enterprise", "value": operating_value, "forecasts": rows,
            "terminal_value": terminal_value, "terminal_fcff": terminal_fcff,
            "terminal_competitive": bool(terminal.get("competitive")),
            "terminal_reinvestment": terminal_reinvestment,
            "present_value_terminal": terminal_value * factors[-1]}


def _residual_income(model):
    opening = number(model["book_equity"], "book_equity", positive=True)
    book = opening
    forecasts = model["forecasts"]
    if not forecasts:
        raise ValueError("residual income requires annual earnings and net distributions")
    factors, rates = _discount(forecasts, model.get("cost_of_equity"))
    rows = []
    for year, (item, factor, rate) in enumerate(zip(forecasts, factors, rates), 1):
        earnings = number(item["comprehensive_income"], "comprehensive_income")
        distribution = number(item["net_distributions"], "net_distributions")
        residual = earnings - rate * book
        closing = book + earnings - distribution
        rows.append({"period": year, "book_equity_begin": book, "book_equity_end": closing,
                     "comprehensive_income": earnings, "net_distributions": distribution,
                     "residual_income": residual, "present_value_residual_income": residual * factor})
        book = closing
    terminal = model["terminal"]
    growth = number(terminal["growth"], "terminal.growth")
    rate = number(terminal.get("cost_of_equity", rates[-1]), "terminal.cost_of_equity")
    roe = number(terminal["roe"], "terminal.roe")
    if rate <= growth:
        raise ValueError("terminal growth must be below cost of equity")
    continuation = (roe - rate) * book / (rate - growth)
    result = opening + math.fsum(r["present_value_residual_income"] for r in rows) + continuation * factors[-1]
    return {"basis": "equity", "value": result, "forecasts": rows,
            "terminal_residual_income_value": continuation, "terminal_equity_value": book + continuation}


def _apv(model):
    """Value operating cash flows and financing effects under their own rates."""
    unlevered_rate = number(model["unlevered_cost_of_capital"], "unlevered_cost_of_capital")
    operating = copy.deepcopy(model)
    operating["discount_rate"] = unlevered_rate
    periods = list(operating["forecasts"])
    if operating.get("competitive_advantage"):
        periods.append(operating["competitive_advantage"]["forecast"])
    for row in periods:
        row["discount_rate"] = row.pop("unlevered_discount_rate", unlevered_rate)
    operating["terminal"]["discount_rate"] = operating["terminal"].get("unlevered_discount_rate", unlevered_rate)
    calculation = _fcff(operating)
    financing = model["financing"]
    if len(financing) != len(calculation["forecasts"]):
        raise ValueError("APV financing must match each operating forecast period")
    factors, _ = _discount(financing, None)
    rows = []
    for period, (row, factor) in enumerate(zip(financing, factors), 1):
        interest = number(row["interest_expense"], "financing.interest_expense")
        tax = number(row["tax_rate"], "financing.tax_rate")
        if not 0 <= tax <= 1:
            raise ValueError("financing.tax_rate must lie between zero and one")
        shield = number(row.get("tax_shield", interest * tax), "financing.tax_shield")
        cost = number(row.get("financing_cost", 0), "financing.financing_cost")
        rows.append({"period": period, "interest_expense": interest, "tax_shield": shield,
                     "financing_cost": cost, "discount_factor": float(factor),
                     "present_value": (shield-cost) * float(factor)})
    terminal = model["financing_terminal"]
    if "value" in terminal:
        terminal_financing = number(terminal["value"], "financing_terminal.value")
        if terminal_financing != 0:
            raise ValueError("use financing_terminal tax_shield/growth/discount_rate for continuing debt")
    else:
        growth = number(terminal["growth"], "financing_terminal.growth")
        rate = number(terminal["discount_rate"], "financing_terminal.discount_rate")
        if rate <= growth:
            raise ValueError("financing terminal growth must be below its discount rate")
        terminal_financing = number(terminal["tax_shield"], "financing_terminal.tax_shield") / (rate-growth)
    pv_financing = math.fsum(row["present_value"] for row in rows) + terminal_financing * factors[-1]
    unlevered_value = calculation["value"]
    return {**calculation, "value": unlevered_value + pv_financing,
            "unlevered_operating_value": unlevered_value, "unlevered_cost_of_capital": unlevered_rate,
            "financing": rows, "present_value_financing": pv_financing,
            "terminal_operating_value": calculation["terminal_value"],
            "terminal_financing_value": terminal_financing,
            "terminal_value": calculation["terminal_value"] + terminal_financing,
            "present_value_terminal": calculation["present_value_terminal"] + terminal_financing * factors[-1]}


def _dynamic_value(model):
    game = model["game"]
    if game["currency"] != model["currency"] or game["amount_unit"] != model["amount_unit"]:
        raise ValueError("dynamic game and equity valuation must share currency and amount units")
    if game["flow_definition"] != "unlevered_after_tax_cash_flow_excluding_financial_assets":
        raise ValueError("dynamic equity valuation requires unlevered after-tax cash flows excluding financial assets")
    result = dynamic(game)
    outcome = result[model.get("game_outcome", "baseline")]
    selected = [r for r in outcome["state_values"]
                if r["state"] == model["initial_state"] and r["firm_ids"] == model["target_firm"]]
    if len(selected) != 1:
        raise ValueError("select one existing dynamic state and target firm")
    return {"basis": "enterprise", "value": selected[0]["cash_flow_value"],
            "initial_state": model["initial_state"], "target_firm": model["target_firm"], "game": result}


def _dividends(model):
    forecasts = model["forecasts"]
    if not forecasts:
        raise ValueError("dividend valuation requires annual net distributions")
    factors, rates = _discount(forecasts, model.get("cost_of_equity"))
    payouts = [number(r["net_distributions"], "net_distributions") for r in forecasts]
    terminal = model["terminal"]
    growth = number(terminal["growth"], "terminal.growth")
    rate = number(terminal.get("cost_of_equity", rates[-1]), "terminal.cost_of_equity")
    if rate <= growth:
        raise ValueError("terminal growth must be below cost of equity")
    payout = number(terminal.get("net_distributions", payouts[-1] * (1 + growth)), "terminal.net_distributions")
    continuation = payout / (rate - growth)
    return {"basis": "equity", "value": math.fsum(p * d for p, d in zip(payouts, factors)) + continuation * factors[-1],
            "forecasts": forecasts, "terminal_equity_value": continuation}


def _nav(model):
    properties = []
    for item in model["assets"]:
        if "value" in item:
            gross = number(item["value"], "asset.value")
        else:
            gross = number(item["sustainable_noi"], "sustainable_noi") / number(item["cap_rate"], "cap_rate", positive=True)
        stake = number(item.get("ownership", 1), "ownership")
        if not 0 <= stake <= 1:
            raise ValueError("ownership must be between zero and one")
        net = (gross - number(item.get("disposal_cost", 0), "disposal_cost")
               - number(item.get("tax_on_gain", 0), "tax_on_gain")) * stake
        properties.append({"name": item["name"], "gross_value": gross, "net_value": net})
    liabilities = number(model["liabilities"], "liabilities")
    return {"basis": "equity", "value": math.fsum(p["net_value"] for p in properties) - liabilities,
            "assets": properties, "liabilities": liabilities}


def _method(model):
    methods = {"fcff": _fcff, "residual_income": _residual_income, "dividend": _dividends,
               "nav": _nav, "apv": _apv, "dynamic_game": _dynamic_value}
    method = model["method"]
    if method in methods:
        return methods[method](model)
    if method != "sotp":
        raise ValueError(f"unsupported valuation method: {method}")
    parts = []
    for component in model["components"]:
        component_model = {"currency": model["currency"], "amount_unit": model["amount_unit"], **component["model"]}
        if component_model["currency"] != model["currency"] or component_model["amount_unit"] != model["amount_unit"]:
            raise ValueError("SOTP components must use the parent currency and amount unit")
        result = _method(component_model)
        stake = number(component.get("ownership", 1), "ownership")
        if not 0 <= stake <= 1:
            raise ValueError("ownership must be between zero and one")
        # Every component uses the parent's currency and amount unit. Enterprise
        # components exclude debt; equity components already contain that bridge.
        parts.append({"name": component["name"], "ownership": stake, **result,
                      "attributable_value": result["value"] * stake})
    return {"basis": "component_sum", "value": math.fsum(p["attributable_value"] for p in parts), "components": parts}


def wacc(inputs: dict) -> dict:
    """Market-value weights and a currency-matched term structure."""
    equity = number(inputs["equity_market_value"], "equity_market_value", positive=True)
    debt = number(inputs["debt_market_value"], "debt_market_value")
    if debt < 0:
        raise ValueError("debt_market_value must be nonnegative")
    risk_free = number(inputs["risk_free_rate"], "risk_free_rate")
    cost_equity = risk_free + number(inputs["levered_beta"], "levered_beta") * number(inputs["equity_premium"], "equity_premium")
    cost_equity += number(inputs.get("country_premium", 0), "country_premium")
    cost_debt = risk_free + number(inputs["credit_spread"], "credit_spread")
    tax = number(inputs["tax_rate"], "tax_rate")
    if not 0 <= tax <= 1:
        raise ValueError("tax_rate must be between zero and one")
    return {"cost_of_equity": cost_equity, "cost_of_debt": cost_debt,
            "wacc": (cost_equity * equity + cost_debt * (1 - tax) * debt) / (equity + debt)}


def investment_return(holding: dict, price: float) -> dict:
    dividends = [number(x, "holding.distributions") for x in holding["distributions"]]
    years = len(dividends)
    if not years or any(x < 0 for x in dividends):
        raise ValueError("holding.distributions requires nonnegative annual per-share distributions")
    exit_price = number(holding["exit_price"], "holding.exit_price")
    if exit_price < 0 or math.fsum(dividends) + exit_price <= 0:
        raise ValueError("holding cash flows require positive total proceeds")
    flows = np.asarray(dividends, dtype=float)
    flows[-1] += exit_price
    # Solve in log(1+r), which represents every annual IRR above -100%.
    periods = np.arange(1, years + 1)
    positive = flows > 0
    def net_present(log_return):
        with np.errstate(over="ignore"):
            return float(np.sum(flows[positive] * np.exp(-log_return * periods[positive])) - price)
    root = brentq(net_present, -100, 100, xtol=1e-13)
    return {"years": years, "annualized_irr": math.expm1(root),
            "total_return": (math.fsum(dividends) + exit_price) / price - 1,
            "distributions": dividends, "exit_price": exit_price}


def investment_decision(terms: dict, valuation: dict) -> dict:
    """Compare attainable positions by after-tax cash flow opportunity cost."""
    holding = valuation["investment_return"]
    dividends, exit_price = holding["distributions"], holding["exit_price"]
    price = valuation["current_price"]
    owned = number(terms["held_shares"], "held_shares")
    budget = number(terms["cash_budget"], "cash_budget")
    maximum = number(terms["max_position_shares"], "max_position_shares")
    lot = number(terms["lot_size"], "lot_size", positive=True)
    basis = number(terms["tax_basis_per_share"], "tax_basis_per_share") if owned else 0.0
    if min(owned, budget, maximum, basis) < 0:
        raise ValueError("position shares, cash budget and tax basis must be nonnegative")
    taxes, fees, alternative = terms["taxes"], terms["fees"], terms["alternative"]
    div_tax, gain_tax, loss_credit = [number(taxes[k], k) for k in
                                      ("dividend_rate", "capital_gain_rate", "capital_loss_credit_rate")]
    if not (0 <= div_tax <= 1 and 0 <= loss_credit <= gain_tax <= 1):
        raise ValueError("tax rates must lie between zero and one; loss credit cannot exceed the gain rate")
    for key in ("deduct_selling_costs", "capitalize_buying_costs"):
        if not isinstance(taxes[key], bool):
            raise ValueError(f"taxes.{key} must be a boolean reflecting the adopted tax treatment")
    buy_rate, sell_rate, buy_fixed, sell_fixed = [number(fees[k], k) for k in
                                                ("buy_rate", "sell_rate", "buy_fixed", "sell_fixed")]
    if min(buy_rate, sell_rate, buy_fixed, sell_fixed) < 0:
        raise ValueError("transaction fees must be nonnegative")
    if alternative["currency"] != valuation["currency"]:
        raise ValueError("the alternative investment must use the stock cash-flow currency")
    rate = number(alternative["annual_after_tax_return"], "alternative.annual_after_tax_return")
    if rate <= -1 or not (alternative.get("source") or alternative.get("user_preference")):
        raise ValueError("the alternative return must exceed -100% and identify its source or user preference")
    dates = terms.get("cash_flow_dates")
    if dates is not None:
        if len(dates) != len(dividends):
            raise ValueError("cash_flow_dates must identify each annual distribution and final liquidation date")
        origin = date.fromisoformat(valuation["as_of"])
        periods = [(date.fromisoformat(day)-origin).days/365.25 for day in dates]
        if not periods or periods[0] <= 0 or any(b <= a for a, b in zip(periods, periods[1:])):
            raise ValueError("investor cash-flow dates must follow the valuation date in increasing order")
    else:
        periods = list(range(1, len(dividends) + 1))
    horizon = number(alternative["horizon_years"], "alternative.horizon_years", positive=True)
    if not math.isclose(horizon, periods[-1], abs_tol=1/365.25):
        raise ValueError("alternative and stock cash flows must share the same holding horizon")
    factors = [(1+rate)**(-period) for period in periods]
    def tax_on_gain(gain):
        return gain * (gain_tax if gain >= 0 else loss_credit)
    def position(shares):
        sold, bought = max(owned-shares, 0), max(shares-owned, 0)
        selling_cost = sold * price * sell_rate + (sell_fixed if sold else 0)
        buying_cost = bought * price * buy_rate + (buy_fixed if bought else 0)
        gain_now = sold * (price-basis) - (selling_cost if taxes["deduct_selling_costs"] else 0)
        immediate_tax = tax_on_gain(gain_now)
        liquid = budget + sold * price - selling_cost - immediate_tax - bought * price - buying_cost
        remaining_basis = min(owned, shares) * basis + bought * price
        if taxes["capitalize_buying_costs"]:
            remaining_basis += buying_cost
        exit_cost = shares * exit_price * sell_rate + (sell_fixed if shares else 0)
        gain_exit = shares * exit_price - remaining_basis - (exit_cost if taxes["deduct_selling_costs"] else 0)
        exit_tax = tax_on_gain(gain_exit)
        exit_net = shares * exit_price - exit_cost - exit_tax
        distributions = [shares * dividend * (1-div_tax) for dividend in dividends]
        flows = list(distributions)
        flows[-1] += exit_net
        present = liquid + math.fsum(flow * factor for flow, factor in zip(flows, factors))
        timeline = [{"period": 0, "date": valuation["as_of"], "cash_flow": liquid}]
        timeline.extend({"period": period, "date": dates[i] if dates else None, "cash_flow": flow}
                        for i, (period, flow) in enumerate(zip(periods, flows)))
        return {"target_shares": shares, "bought_shares": bought, "sold_shares": sold,
                "immediate_cash": liquid, "immediate_tax": immediate_tax,
                "immediate_transaction_cost": selling_cost+buying_cost,
                "taxable_gain_now": gain_now, "taxable_gain_exit": gain_exit,
                "exit_tax": exit_tax, "exit_transaction_cost": exit_cost, "exit_net_proceeds": exit_net,
                "after_tax_distributions": distributions, "cash_flows": timeline,
                "present_wealth": present, "terminal_wealth": present/factors[-1]}
    affordable = max(0, math.floor(max(0, budget-buy_fixed)/(price*(1+buy_rate))/lot)) * lot
    upper = min(maximum, owned+affordable)
    # Taxes and fixed fees make the objective piecewise linear. Its extrema
    # occur at position bounds or zero taxable gains; inspect adjacent lots.
    boundaries = sorted({0.0, min(owned, upper), upper})
    candidates = set(boundaries)
    for lower, higher in zip(boundaries, boundaries[1:]):
        if higher == lower:
            continue
        x, y = lower+(higher-lower)/3, lower+2*(higher-lower)/3
        first, second = position(x), position(y)
        for field in ("taxable_gain_now", "taxable_gain_exit"):
            slope = (second[field]-first[field])/(y-x)
            if slope:
                kink = x-first[field]/slope
                if lower < kink < higher:
                    candidates.add(kink)
    cash_segments = sorted(candidates)
    for lower, higher in zip(cash_segments, cash_segments[1:]):
        x, y = lower+(higher-lower)/3, lower+2*(higher-lower)/3
        first, second = position(x)["immediate_cash"], position(y)["immediate_cash"]
        slope = (second-first)/(y-x)
        if slope:
            boundary = x-first/slope
            if lower < boundary < higher:
                candidates.add(boundary)
    attainable = {0.0}
    for candidate in candidates:
        steps = (candidate-owned)/lot
        for step in (math.floor(steps), math.ceil(steps)):
            shares = owned + step * lot
            if 0 <= shares <= upper + 1e-9:
                attainable.add(min(shares, upper))
    if owned <= upper:
        attainable.add(owned)
    alternatives = [position(shares) for shares in sorted(attainable)]
    alternatives = [item for item in alternatives if item["immediate_cash"] >= -1e-8]
    if not alternatives:
        raise ValueError("no position satisfies the cash budget, position limit and transaction costs")
    liquidation = position(0)["present_wealth"]
    for item in alternatives:
        item["npv_over_liquidation_alternative"] = item["present_wealth"] - liquidation
    best = max(alternatives, key=lambda item: (item["present_wealth"], -abs(item["target_shares"]-owned)))
    target = best["target_shares"]
    action = "buy" if target > owned else "sell" if target < owned else "hold" if owned else "do_not_buy"
    return {"action": action, "target_shares": target, "currency": valuation["currency"],
            "amount_unit": 1, "share_unit": 1, "alternative": alternative,
            "criterion": "maximum_after_tax_present_wealth_within_supplied_budget_and_position_limit",
            "full_liquidation_present_wealth": liquidation, "alternatives": alternatives,
            "incremental_npv": best["npv_over_liquidation_alternative"],
            "dividend_reinvestment": "at_the_supplied_alternative_after_tax_return"}


def balance_bridge(balance: dict) -> dict:
    cash = number(balance["cash"], "cash")
    operating_cash = number(balance["operating_cash"], "operating_cash")
    if operating_cash < 0 or operating_cash > cash:
        raise ValueError("operating_cash must lie between zero and total cash")
    debt = number(balance["debt"], "debt")
    excess_cash = cash - operating_cash
    other_assets = number(balance.get("nonoperating_assets", 0), "nonoperating_assets")
    minority = number(balance.get("minority_interest", 0), "minority_interest")
    other_claims = number(balance.get("other_claims", 0), "other_claims")
    pensions = number(balance.get("pension_deficit", 0), "pension_deficit")
    leases = number(balance.get("lease_liabilities", 0), "lease_liabilities")
    net_financial = excess_cash + other_assets - debt - minority - other_claims - pensions - leases
    return {"excess_cash": excess_cash, "debt": debt, "net_cash": excess_cash - debt,
            "nonoperating_assets": other_assets, "minority_interest": minority,
            "other_claims": other_claims, "pension_deficit": pensions,
            "lease_liabilities": leases, "net_financial_assets": net_financial}


def value(spec: dict) -> dict:
    sources = provenance(spec)
    inputs = copy.deepcopy(spec)
    currency = spec["currency"]
    amount_unit = number(spec["amount_unit"], "amount_unit", positive=True)
    share_unit = number(spec["share_unit"], "share_unit", positive=True)
    shares = number(spec["diluted_shares"], "diluted_shares", positive=True)
    price = number(spec["current_price"], "current_price", positive=True)
    model = copy.deepcopy(spec)
    capital_cost = None
    if "capital_cost" in model and model["method"] not in {"apv", "dynamic_game"}:
        capital_cost = wacc(model["capital_cost"])
        key = "discount_rate" if model["method"] in {"fcff", "sotp"} else "cost_of_equity"
        model.setdefault(key, capital_cost["wacc" if key == "discount_rate" else "cost_of_equity"])
    calculation = _method(model)
    financial_bridge = 0.0
    bridge = None
    if calculation["basis"] in {"enterprise", "component_sum"}:
        bridge = balance_bridge(spec["balance"])
        financial_bridge = bridge["net_financial_assets"]
    equity = calculation["value"] + financial_bridge
    fair_price = equity * amount_unit / (shares * share_unit)
    output = {"inputs": inputs, "method": spec["method"], "currency": currency,
              "market": spec["market"], "as_of": spec["as_of"], "price_as_of": spec["price_as_of"],
              "sources": sources,
              "amount_unit": amount_unit, "share_unit": share_unit,
              "calculation": calculation, "balance_bridge": bridge,
              "equity_value": equity, "diluted_shares": shares,
              "fair_price": fair_price, "current_price": price,
              "price_gap": fair_price - price, "upside": fair_price / price - 1,
              "market_equity_value": price * shares * share_unit / amount_unit}
    if capital_cost is not None:
        output["capital_cost"] = capital_cost
    if "holding" in spec:
        holding = copy.deepcopy(spec["holding"])
        if "exit_price" not in holding:
            if holding["exit_basis"] != "model_terminal":
                raise ValueError("holding requires exit_price or exit_basis=model_terminal")
            if spec["method"] in {"nav", "sotp", "dynamic_game"}:
                raise ValueError("holding requires an explicit exit_price for NAV, SOTP and dynamic games")
            if len(holding["distributions"]) != len(calculation.get("forecasts", [])):
                raise ValueError("model_terminal holding horizon must equal the forecast horizon")
            if calculation["basis"] == "enterprise":
                terminal_financial = balance_bridge(holding["terminal_balance"])
                terminal_equity = calculation["terminal_value"] + terminal_financial["net_financial_assets"]
            else:
                terminal_equity = calculation["terminal_equity_value"]
            terminal_shares = number(holding["terminal_diluted_shares"], "terminal_diluted_shares", positive=True)
            holding["exit_price"] = terminal_equity * amount_unit / (terminal_shares * share_unit)
        output["investment_return"] = investment_return(holding, price)
    if "decision" in spec:
        if "investment_return" not in output:
            raise ValueError("investment decisions require holding distributions and an exit price or terminal value")
        output["decision"] = investment_decision(spec["decision"], output)
    return output


def _pointer(spec, path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("news changes require existing JSON Pointer paths, starting with /")
    keys = [x.replace("~1", "/").replace("~0", "~") for x in path[1:].split("/")]
    target = spec
    for key in keys[:-1]:
        target = target[int(key)] if isinstance(target, list) else target[key]
    key = int(keys[-1]) if isinstance(target, list) else keys[-1]
    if isinstance(key, int) and key < 0:
        raise ValueError("JSON Pointer list positions must be nonnegative")
    return target, key


def _change_input(spec, path, value):
    target, key = _pointer(spec, path)
    previous = copy.deepcopy(target[key])
    target[key] = copy.deepcopy(value)
    return previous


def reverse(spec: dict) -> dict:
    """Solve one market-implied primitive, keeping all other inputs fixed."""
    base = spec["base"]
    inputs = copy.deepcopy(base["inputs"] if "inputs" in base else base)
    inputs.pop("holding", None)
    inputs.pop("decision", None)
    parameter = spec["parameter"]
    path = parameter["path"]
    if path == "/current_price":
        raise ValueError("reverse valuation changes an economic primitive, holding the market price fixed")
    target, key = _pointer(inputs, path)
    adopted = number(target[key], path)
    market_price = number(spec.get("target_price", inputs["current_price"]), "target_price", positive=True)
    if not parameter.get("economic_quantity"):
        raise ValueError("reverse parameter requires the economic_quantity being inferred")
    evaluated = {}
    def calculate(candidate):
        if candidate not in evaluated:
            changed = copy.deepcopy(inputs)
            _change_input(changed, path, candidate)
            evaluated[candidate] = value(changed)
        return evaluated[candidate]["fair_price"] - market_price
    output = {"parameter": parameter, "adopted_value": adopted, "target_price": market_price,
              "currency": inputs["currency"], "condition": "all_other_primitives_fixed",
              "sources": provenance(inputs)}
    if parameter.get("kind", "continuous") == "integer":
        lower = number(parameter["lower"], "parameter.lower")
        upper = number(parameter["upper"], "parameter.upper")
        if lower != int(lower) or upper != int(upper) or upper < lower:
            raise ValueError("integer reverse bounds must be ordered integers")
        candidates = list(range(int(lower), int(upper) + 1))
        price_path = [{"value": n, "fair_price": calculate(n) + market_price} for n in candidates]
        feasible = [n for n in candidates if evaluated[n]["fair_price"] >= market_price]
        selected = min(feasible) if feasible else None
        return {**output, "criterion": "smallest_integer_in_range_with_value_at_least_market_price",
                "evaluations": price_path, "implied_value": selected,
                "valuation": evaluated[selected] if selected is not None else None}
    if parameter.get("kind", "continuous") != "continuous":
        raise ValueError("reverse kind must be continuous or integer")
    brackets = parameter.get("brackets") or [[parameter["lower"], parameter["upper"]]]
    roots = []
    for bracket in brackets:
        lower, upper = (number(x, "reverse bracket") for x in bracket)
        if not lower < upper:
            raise ValueError("each reverse bracket must have lower < upper")
        low_gap, high_gap = calculate(lower), calculate(upper)
        if low_gap == high_gap and calculate((lower+upper)/2) == low_gap:
            raise ValueError("endpoint and midpoint prices are identical; supply a bracket with informative price variation")
        if low_gap * high_gap > 0:
            raise ValueError(f"reverse bracket [{lower}, {upper}] does not bracket the target price; gaps {low_gap}, {high_gap}")
        candidates = [lower, upper] if low_gap == high_gap == 0 else [float(brentq(
            calculate, lower, upper, xtol=number(parameter.get("tolerance", 1e-9), "parameter.tolerance", positive=True)))]
        for root in candidates:
            roots.append({"bracket": [lower, upper], "implied_value": root,
                          "price_error": calculate(root), "valuation": evaluated[root]})
    return {**output, "roots": roots, "root_scope": "supplied_sign_change_brackets",
            "evaluations": len(evaluated)}


def update(spec: dict) -> dict:
    base = spec["base"]
    inputs = copy.deepcopy(base["inputs"] if "inputs" in base else base)
    original = value(inputs)
    def retain_parameters(model, calculation):
        # News changes primitives using the adopted structural estimates, also
        # when a dynamic business is one component of a multi-business company.
        if model["method"] == "dynamic_game":
            model["game"]["parameters"] = copy.deepcopy(calculation["game"]["parameters"])
        elif model["method"] == "sotp":
            for component, result in zip(model["components"], calculation["components"]):
                retain_parameters(component["model"], result)
    retain_parameters(inputs, original["calculation"])
    previous = original
    contributions = []
    applied = {source["event_id"] for source in inputs["sources"] if "event_id" in source}
    announcements = {}
    for source in inputs["sources"]:
        if "event_id" in source:
            announcements[source.get("announcement_id", source["event_id"])] = source
    for event in spec["events"]:
        if not event.get("source_url") or not event.get("published_at") or not event.get("mechanism"):
            raise ValueError("each event needs source_url, published_at, and its quantitative mechanism")
        if event["id"] in applied:
            raise ValueError(f"event {event['id']} is already included in this valuation")
        announcement = event.get("announcement_id", event["id"])
        revision = number(event.get("revision", 0), "event.revision")
        if not isinstance(announcement, str) or not announcement or revision < 0 or revision != int(revision):
            raise ValueError("each event requires a stable announcement_id and a nonnegative integer revision")
        preceding = announcements.get(announcement)
        if preceding is not None:
            if revision <= preceding.get("revision", 0):
                raise ValueError(f"announcement {announcement} revision {revision:g} is already included")
            if event.get("supersedes") != preceding["event_id"] or not preceding.get("input_changes"):
                raise ValueError("a revision must supersede the latest event and retain its saved input_changes")
            prior_index = next(i for i in range(len(inputs["sources"])-1, -1, -1)
                               if inputs["sources"][i].get("event_id") == preceding["event_id"])
            revised_paths = {change["path"] for change in preceding["input_changes"]}
            for later in inputs["sources"][prior_index+1:]:
                for change in later.get("input_changes", []):
                    path = change["path"]
                    if any(path == old or path.startswith(old + "/") or old.startswith(path + "/")
                           for old in revised_paths):
                        raise ValueError(f"later information wrote {path}; replay the revised event sequence from its original baseline")
            for change in preceding["input_changes"]:
                target, key = _pointer(inputs, change["path"])
                if target[key] != change["new"]:
                    raise ValueError(f"later information changed {change['path']}; replay the revised event sequence from its original baseline")
                _change_input(inputs, change["path"], change["old"])
        changes = []
        proposals = list(event.get("changes", []))
        if "rate_change" in event:
            rate = event["rate_change"]
            difference = number(rate["new"], "rate_change.new") - number(rate["old"], "rate_change.old")
            for channel in rate["channels"]:
                path = channel["path"]
                target, key = _pointer(inputs, path)
                base_value = number(target[key], path)
                loading = number(channel["loading"], "rate channel loading")
                if channel["response"] == "linear":
                    changed_value = base_value + loading * difference
                elif channel["response"] == "log":
                    changed_value = base_value * math.exp(loading * difference)
                else:
                    raise ValueError("rate response must be linear or log")
                proposals.append({"path": path, "value": changed_value, "channel": channel["role"],
                                  "loading": loading, "rate_difference": difference})
        if not proposals:
            raise ValueError("each event requires numeric changes or rate exposure channels")
        if len({p["path"] for p in proposals}) != len(proposals):
            raise ValueError("each event must update an input path once")
        if preceding and not {c["path"] for c in preceding["input_changes"]}.issubset(p["path"] for p in proposals):
            raise ValueError("a revision must supply the full replacement for all paths changed by the prior announcement")
        for change in proposals:
            old = _change_input(inputs, change["path"], change["value"])
            changes.append({"path": change["path"], "old": old, "new": change["value"],
                            **{key: change[key] for key in ("channel", "loading", "rate_difference") if key in change}})
        record = {"url": event["source_url"], "published_at": event["published_at"],
                  "event_id": event["id"], "announcement_id": announcement, "revision": int(revision),
                  "mechanism": event["mechanism"], "input_changes": changes}
        if preceding:
            record["supersedes"] = preceding["event_id"]
        inputs["sources"].append(record)
        announcements[announcement] = record
        if "as_of" in spec:
            inputs["as_of"] = spec["as_of"]
        applied.add(event["id"])
        current = value(inputs)
        contributions.append({"id": event["id"], "source_url": event["source_url"],
                              "announcement_id": announcement, "revision": int(revision),
                              "supersedes": preceding["event_id"] if preceding else None,
                              "published_at": event["published_at"], "mechanism": event["mechanism"],
                              "changes": changes, "equity_value_change": current["equity_value"] - previous["equity_value"],
                              "fair_price_change": current["fair_price"] - previous["fair_price"],
                              "fair_price_after": current["fair_price"]})
        previous = current
    return {"attribution": "sequential_in_supplied_event_order", "baseline": original,
            "updated": previous, "contributions": contributions,
            "equity_value_change": previous["equity_value"] - original["equity_value"],
            "fair_price_change": previous["fair_price"] - original["fair_price"]}


def json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"cannot encode {type(value).__name__}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("fit", "dynamic", "value", "reverse", "update"))
    parser.add_argument("input", nargs="?", default="-")
    parser.add_argument("-o", "--output")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            spec = json.load(sys.stdin)
        else:
            spec = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if args.operation == "fit" and spec.get("model") != "cournot":
            import pyblp
            pyblp.options.verbose = False
        with contextlib.redirect_stdout(sys.stderr):
            result = {"fit": fit, "dynamic": dynamic, "value": value, "reverse": reverse,
                      "update": update}[args.operation](spec)
        output = json.dumps(result, ensure_ascii=False, indent=2, default=json_default, allow_nan=False) + "\n"
        if args.output:
            destination = Path(args.output)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as file:
                    temporary = Path(file.name)
                    file.write(output)
                os.replace(temporary, destination)
                temporary = None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        else:
            print(output, end="")
        return 0
    except (KeyError, ValueError, TypeError, ArithmeticError, OSError) as exc:
        print(f"{args.operation}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
