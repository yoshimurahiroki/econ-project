#!/usr/bin/env python3
"""Solve a finite-horizon deterministic representative-household growth model.

Usage: research_macro.py solve SPEC.json -o RESULT.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import minimize


def _solve_path(model, alpha, beta, delta, initial, terminal, tol):
    if not isinstance(model, dict) or set(model) != {"productivity", "output_tax"}:
        raise ValueError("each scenario requires productivity and output_tax paths")
    z = np.asarray(model["productivity"], dtype=float)
    tax = np.asarray(model["output_tax"], dtype=float)
    if (z.ndim != 1 or len(z) < 2 or tax.shape != z.shape or not np.isfinite(z).all() or
            not np.isfinite(tax).all() or (z <= 0).any() or (tax < 0).any() or (tax >= 1).any()):
        raise ValueError("paths require at least two positive productivity values and tax rates in [0,1)")
    horizon = len(z)
    weights = beta ** np.arange(horizon)

    def quantities(internal):
        capital = np.r_[initial, internal, terminal]
        output = z * capital[:-1] ** alpha
        consumption = (1-tax) * output + (1-delta) * capital[:-1] - capital[1:]
        returns = (1-tax) * alpha * z * capital[:-1] ** (alpha-1) + 1-delta
        return capital, output, consumption, returns

    def objective(internal):
        _, _, consumption, _ = quantities(internal)
        return -float(np.dot(weights, np.log(np.maximum(consumption, 1e-12))))

    def gradient(internal):
        _, _, consumption, returns = quantities(internal)
        marginal = np.where(consumption > 1e-12, weights/np.maximum(consumption, 1e-12), 0)
        return marginal[:-1] - marginal[1:]*returns[1:]

    def constraint(internal):
        return quantities(internal)[2] - 1e-10

    def constraint_jac(internal):
        _, _, _, returns = quantities(internal)
        jac = np.zeros((horizon, horizon-1))
        jac[np.arange(horizon-1), np.arange(horizon-1)] = -1
        jac[np.arange(1,horizon), np.arange(horizon-1)] = returns[1:]
        return jac

    start = np.linspace(initial, terminal, horizon+1)[1:-1]
    opt = minimize(objective, start, method="SLSQP", jac=gradient, bounds=[(1e-10, None)]*(horizon-1),
                   constraints=[{"type": "ineq", "fun": constraint, "jac": constraint_jac}],
                   options={"ftol": min(1e-12, tol*1e-3), "maxiter": 5000})
    capital, output, consumption, returns = quantities(opt.x)
    if not opt.success or (consumption <= 0).any() or (capital <= 0).any():
        raise ArithmeticError(f"optimization failed: {opt.message}")
    euler = 1/consumption[:-1] - beta*returns[1:]/consumption[1:]
    resources = consumption + capital[1:] - ((1-tax)*output + (1-delta)*capital[:-1])
    numerical_gradient = np.empty_like(opt.x)
    numerical_constraint = np.empty((horizon, horizon-1))
    for j in range(horizon-1):
        step = 1e-5 * max(1, abs(opt.x[j]))
        change = np.zeros_like(opt.x)
        change[j] = step
        numerical_gradient[j] = (objective(opt.x + change) - objective(opt.x - change))/(2*step)
        numerical_constraint[:, j] = (constraint(opt.x + change) - constraint(opt.x - change))/(2*step)
    gradient_error = float(np.max(np.abs(numerical_gradient-gradient(opt.x))))
    jacobian_error = float(np.max(np.abs(numerical_constraint-constraint_jac(opt.x))))
    if (np.max(np.abs(euler)) > tol or np.max(np.abs(resources)) > tol or
            max(gradient_error, jacobian_error) > max(1e-6, 10*tol)):
        raise ArithmeticError("original equations or derivative checks exceed their numerical tolerances")
    steady = (alpha*z[0]*(1-tax[0])/(1/beta-1+delta))**(1/(1-alpha))
    return {"capital": capital.tolist(), "consumption": consumption.tolist(), "output": output.tolist(),
            "government_absorption": (tax*output).tolist(), "welfare": float(-objective(opt.x)),
            "steady_state_at_first_period_productivity_and_tax": float(steady),
            "euler_max_abs_error": float(np.max(np.abs(euler))),
            "resource_max_abs_error": float(np.max(np.abs(resources))),
            "objective_gradient_max_abs_error": gradient_error, "resource_jacobian_max_abs_error": jacobian_error,
            "derivative_tolerance": max(1e-6, 10*tol), "optimizer_iterations": int(opt.nit)}


def solve(spec):
    """Optimize log consumption subject to fixed initial and terminal capital."""
    allowed = {"alpha", "beta", "delta", "initial_capital", "terminal_capital", "baseline", "scenario",
               "population", "period", "unit", "sources", "tolerance"}
    if not isinstance(spec, dict) or set(spec) != allowed:
        raise ValueError(f"macro specification requires exactly: {', '.join(sorted(allowed))}")
    alpha, beta, delta = (float(spec[k]) for k in ("alpha", "beta", "delta"))
    initial, terminal, tol = (float(spec[k]) for k in ("initial_capital", "terminal_capital", "tolerance"))
    if (not np.isfinite([alpha, beta, delta, initial, terminal, tol]).all() or
            not (0 < alpha < 1 and 0 < beta < 1 and 0 <= delta <= 1 and initial > 0 and terminal > 0 and tol > 0)):
        raise ValueError("invalid preferences, technology, capital or tolerance")
    if any(not isinstance(spec[k], str) or not spec[k].strip() for k in ("population", "period", "unit")):
        raise ValueError("population, period and unit must be nonempty strings")
    if not isinstance(spec["sources"], list) or not spec["sources"] or any(
        not isinstance(x, dict) or not (x.get("url") or x.get("path") or x.get("description")) for x in spec["sources"]
    ):
        raise ValueError("sources must identify model inputs")
    if len(spec["baseline"]["productivity"]) != len(spec["scenario"]["productivity"]):
        raise ValueError("baseline and scenario must use the same horizon")
    baseline = _solve_path(spec["baseline"], alpha, beta, delta, initial, terminal, tol)
    scenario = _solve_path(spec["scenario"], alpha, beta, delta, initial, terminal, tol)
    path_rows, diagnostic_rows = [], []
    for name, allocation in (("baseline", baseline), ("scenario", scenario)):
        for quantity in ("capital", "consumption", "output", "government_absorption"):
            path_rows.extend({"scenario": name, "period": period, "quantity": quantity,
                              "value": value, "unit": spec["unit"]}
                             for period, value in enumerate(allocation[quantity]))
        diagnostic_rows.extend({"scenario": name, "diagnostic": diagnostic,
                                "value": allocation[diagnostic], "unit": unit}
                               for diagnostic, unit in (("euler_max_abs_error", "inverse consumption"),
                                                        ("resource_max_abs_error", spec["unit"]),
                                                        ("objective_gradient_max_abs_error", "utility per capital unit"),
                                                        ("resource_jacobian_max_abs_error", "resource per capital unit")))
    model_metadata = {"model_contract": "MC-ramsey-cf", "unit": "see row-specific unit", "population": spec["population"],
                      "period": spec["period"], "terminal_condition": "fixed terminal capital; no continuation utility"}
    displays = {
        "parameters": {"kind": "table", "title": "Preferences, technology and endpoints",
                       "columns": [{"key": key, "label": label, "unit": ""} for key, label in
                                   (("parameter", "Parameter"), ("value", "Specified value"), ("unit", "Unit"))],
                       "rows": [{"parameter": name, "value": spec[name], "unit": unit} for name, unit in
                                (("alpha", "capital elasticity"), ("beta", "discount factor"),
                                 ("delta", "depreciation rate"), ("initial_capital", spec["unit"]),
                                 ("terminal_capital", spec["unit"]))],
                       "metadata": {**model_metadata, "report_role": "parameters", "parameter_status": "specified"},
                       "display": {"plot_type": "table"}},
        "model_fit": {"kind": "table", "title": "Euler and resource diagnostics", "rows": diagnostic_rows,
                      "columns": [{"key": key, "label": label, "unit": ""} for key, label in
                                  (("scenario", "Scenario"), ("diagnostic", "Diagnostic"), ("value", "Value"), ("unit", "Unit"))],
                      "metadata": {**model_metadata, "report_role": "model_fit"}, "display": {"plot_type": "table"}},
        "allocation_paths": {"kind": "structural", "title": "Household growth paths", "rows": path_rows,
                             "columns": [{"key": key, "label": label, "unit": ""} for key, label in
                                         (("scenario", "Scenario"), ("period", "Period"), ("quantity", "Quantity"),
                                          ("value", "Value"), ("unit", "Unit"))],
                             "metadata": {**model_metadata, "report_role": "counterfactual",
                                          "time_definition": "Capital is the start-of-period stock, including the terminal endpoint; other quantities are period flows"},
                             "display": {"plot_type": "line", "x": "period", "y": "value", "series": "scenario", "facet": "quantity"}},
        "welfare": {"kind": "counterfactual", "title": "Discounted household welfare",
                    "columns": [{"key": key, "label": label, "unit": ""} for key, label in
                                (("scenario", "Scenario"), ("value", "Welfare"), ("unit", "Unit"))],
                    "rows": [{"scenario": name, "value": allocation["welfare"], "unit": "discounted log consumption"}
                             for name, allocation in (("baseline", baseline), ("scenario", scenario))],
                    "metadata": {**model_metadata, "report_role": "welfare", "unit": "discounted log consumption",
                                 "estimand": "Sum of beta^t log(c_t) over the stated horizon"},
                    "display": {"plot_type": "bar", "x": "scenario", "y": "value"}}}
    return {"model": "finite-horizon deterministic household growth", "engine": "scipy.optimize.minimize/SLSQP",
            "versions": {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__},
            "definition": {"population": spec["population"], "period": spec["period"], "unit": spec["unit"],
                           "sources": spec["sources"], "terminal_condition": "fixed terminal capital; no continuation utility",
                           "tax": "output tax funds government absorption and leaves household resources"},
            "baseline": baseline, "scenario": scenario, "welfare_change": scenario["welfare"] - baseline["welfare"],
            "statistics": {"welfare_change": {"value": scenario["welfare"]-baseline["welfare"], "unit": "discounted log consumption"}},
            "displays": displays}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["solve"])
    parser.add_argument("spec", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        raw = args.spec.read_bytes()
        result = solve(json.loads(raw))
        result["input"] = {"spec_path": str(args.spec.resolve()), "spec_sha256": hashlib.sha256(raw).hexdigest()}
        payload = json.dumps(result, indent=2, allow_nan=False) + "\n"
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent,
                                             prefix=f".{args.output.name}.", delete=False) as stream:
                temp = Path(stream.name)
                stream.write(payload)
            os.replace(temp, args.output)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
    except (ValueError, TypeError, KeyError, OSError, ArithmeticError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
