"""Quantity competition and finite-state investment games using NumPy/SciPy.

The caller supplies market definitions, source records and identifying moments.
Prices and quantities retain their declared units. Dynamic flows are monetary
payoffs at the current decision date; discounting starts with the next state.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from scipy.linalg import qr
from scipy.optimize import brentq, least_squares, minimize
from scipy.special import logsumexp


def _array(values, name, shape=None):
    result = np.asarray(values, dtype=float)
    if not np.isfinite(result).all() or (shape is not None and result.shape != shape):
        raise ValueError(f"{name}: supply finite numeric values with shape {shape}")
    return result


def conditional_logit(products, alpha, counterfactual=None):
    """Recover costs and solve all firms in a fixed-total conditional market."""
    if not np.isfinite(alpha) or alpha >= 0:
        raise ValueError("conditional logit requires a negative homogeneous price coefficient")
    prices = _array(products.prices, "conditional prices")
    shares = _array(products.shares, "conditional shares")
    costs = np.empty(len(products))
    intercepts = np.log(shares) - alpha * prices
    groups = products.groupby("market_ids", sort=False).indices
    for market, indices in groups.items():
        indices = np.asarray(indices)
        firms = products.iloc[indices].firm_ids.to_numpy()
        if len(set(firms)) < 2 or not np.isclose(shares[indices].sum(), 1, atol=1e-9, rtol=0):
            raise ValueError("each conditional market requires at least two owners and shares summing to one")
        ownership_share = np.asarray([shares[indices][firms == firm].sum() for firm in firms])
        costs[indices] = prices[indices] + 1 / (alpha * (1-ownership_share))
    output = {"baseline_costs": costs}
    if counterfactual is None:
        return output
    changed = products.copy()
    for name, values in counterfactual.get("product_changes", {}).items():
        if name != "firm_ids":
            raise ValueError("conditional product_changes supports ownership; use utility_shift for product utility changes")
        changed[name] = values
    new_costs = _array(counterfactual.get("costs", costs), "conditional counterfactual costs", (len(products),))
    shifts = np.broadcast_to(_array(counterfactual.get("utility_shift", 0), "conditional utility_shift"), (len(products),))
    new_prices, new_shares = prices.copy(), shares.copy()
    residuals = []
    tolerance = float(counterfactual.get("equilibrium_tolerance", 1e-8))
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("conditional equilibrium_tolerance must be finite and positive")
    for market, indices in groups.items():
        indices = np.asarray(indices)
        owner = changed.iloc[indices].firm_ids.to_numpy()
        firms = list(dict.fromkeys(owner))
        if len(firms) < 2:
            raise ValueError("a single owner has no finite price optimum in a market with fixed total demand")
        membership = np.asarray([[firm == company for firm in owner] for company in firms], dtype=float)
        utility = intercepts[indices] + shifts[indices]
        def choices(markups):
            candidate_prices = new_costs[indices] + membership.T @ markups / (-alpha)
            values = utility + alpha * candidate_prices
            candidate_shares = np.exp(values-logsumexp(values))
            return candidate_prices, candidate_shares
        def equations(markups):
            _, candidate_shares = choices(markups)
            return markups * (1-membership @ candidate_shares) - 1
        initial = 1 / (1-membership @ shares[indices])
        solution = least_squares(equations, initial, bounds=(0, np.inf),
                                 xtol=1e-12, ftol=1e-12, gtol=1e-12)
        error = float(np.max(np.abs(equations(solution.x))))
        if not solution.success or error > tolerance:
            raise ArithmeticError("conditional market prices must satisfy every owner's best response")
        new_prices[indices], new_shares[indices] = choices(solution.x)
        if (new_prices[indices] < 0).any():
            raise ValueError("conditional equilibrium requires nonnegative prices on its adopted support")
        residuals.append({"market_ids": market, "best_response_max_abs_error": error,
                          "evaluations": int(solution.nfev)})
    return {**output, "products": changed, "prices": new_prices, "shares": new_shares,
            "costs": new_costs, "equilibrium_residuals": residuals}


def cournot(spec):
    """Estimate inverse demand by 2SLS and solve convex-cost capacity games."""
    demand = spec["inverse_demand"]
    controls = list(demand.get("controls", []))
    labels = ["intercept", "quantity", *controls]
    if len(set(labels)) != len(labels):
        raise ValueError("inverse-demand control names must be unique")
    estimation = None
    if "observations" in spec:
        data = pd.read_csv(spec["observations"]) if isinstance(spec["observations"], str) else pd.DataFrame(spec["observations"])
        if data.duplicated("market_ids").any():
            raise ValueError("inverse demand requires one aggregate price/quantity observation per market")
        excluded = list(demand["instruments"])
        if not excluded or any(x in controls + ["quantity", "price"] for x in excluded):
            raise ValueError("supply excluded cost or supply instruments for aggregate quantity")
        y = _array(data["price"], "observed prices")
        x = _array(np.column_stack([np.ones(len(data)), data[["quantity", *controls]]]), "demand design")
        if (y < 0).any() or (x[:, 1] < 0).any():
            raise ValueError("observed market prices and quantities must be nonnegative")
        z = _array(np.column_stack([np.ones(len(data)), data[[*controls, *excluded]]]), "instruments")
        if len(data) <= x.shape[1] or np.linalg.matrix_rank(z) != z.shape[1]:
            raise ValueError("inverse demand requires positive residual degrees of freedom and full-rank instruments")
        # QR computes the instrument projection without forming normal equations.
        qz, _ = qr(z, mode="economic")
        projected_x, projected_y = qz.T @ x, qz.T @ y
        if np.linalg.matrix_rank(projected_x) != x.shape[1]:
            raise ValueError("the instrument projection must identify every inverse-demand coefficient")
        beta = np.linalg.lstsq(projected_x, projected_y, rcond=None)[0]
        residual = y - x @ beta
        estimation = {"method": "2SLS", "observations": len(data), "market_ids": data.market_ids.tolist(),
                      "instruments": ["intercept", *controls, *excluded],
                      "projected_design_rank": int(np.linalg.matrix_rank(projected_x)),
                      "residuals": residual.tolist(), "sample_moments": (z.T @ residual / len(data)).tolist()}
    else:
        beta = _array([demand["coefficients"][name] for name in labels], "inverse-demand coefficients")
    coefficients = dict(zip(labels, beta.tolist()))
    slope = -coefficients["quantity"]
    if slope <= 0:
        raise ValueError("Cournot demand must have a strictly negative quantity coefficient")
    price_unit = float(spec["price_unit"])
    if not np.isfinite(price_unit) or price_unit <= 0:
        raise ValueError("price_unit must be finite and positive")

    def solve(markets):
        if not markets:
            raise ValueError("supply at least one market for the Cournot equilibrium")
        firms_out, markets_out = [], []
        seen = set()
        for market in markets:
            market_id = market["market_ids"]
            if market_id in seen:
                raise ValueError("Cournot market identifiers must be unique")
            seen.add(market_id)
            intercept = coefficients["intercept"] + sum(coefficients[k] * float(market["controls"][k]) for k in controls)
            intercept += float(market.get("demand_shift", 0))
            firms = market["firms"]
            if not firms or len({f["firm_ids"] for f in firms}) != len(firms):
                raise ValueError("each market requires uniquely identified firms")
            costs = _array([f["unit_cost"] for f in firms], "unit costs")
            curvature = _array([f.get("cost_slope", 0) for f in firms], "cost slopes")
            capacity = _array([f["capacity"] for f in firms], "capacities")
            if (curvature < 0).any() or (capacity < 0).any():
                raise ValueError("cost slopes and capacities must be nonnegative")
            if not np.isfinite(intercept):
                raise ValueError("inverse-demand intercept must be finite")
            def quantities(total):
                return np.clip((intercept - costs - slope * total) / (slope + curvature), 0, capacity)
            maximum = float(capacity.sum())
            total = brentq(lambda q: float(quantities(q).sum() - q), 0, maximum, xtol=1e-12) if maximum else 0.0
            output = quantities(total)
            price = intercept - slope * total
            if price < 0:
                raise ValueError("the adopted linear-demand support must produce a nonnegative market price")
            gradient = price - costs - (slope + curvature) * output
            best = np.clip((intercept - costs - slope * (total - output)) / (2 * slope + curvature), 0, capacity)
            residual = float(np.max(np.abs(output - best)))
            tolerance = float(spec.get("equilibrium_tolerance", 1e-8))
            if not np.isfinite(tolerance) or tolerance <= 0:
                raise ValueError("equilibrium_tolerance must be finite and positive")
            if residual > tolerance or abs(output.sum() - total) > tolerance:
                raise ArithmeticError("Cournot quantities must satisfy all capacity-constrained best responses")
            for f, quantity, cost, curve, cap, grad in zip(firms, output, costs, curvature, capacity, gradient):
                revenue = price * quantity * price_unit
                variable_cost = (cost * quantity + .5 * curve * quantity ** 2) * price_unit
                firms_out.append({"market_ids": market_id, "firm_ids": f["firm_ids"],
                                  "quantity": float(quantity), "price": price * price_unit,
                                  "capacity": float(cap), "revenue": float(revenue),
                                  "variable_cost": float(variable_cost), "gross_profit": float(revenue - variable_cost),
                                  "marginal_cost": float((cost + curve * quantity) * price_unit),
                                  "capacity_shadow_price": float(max(grad, 0) * price_unit) if abs(quantity-cap) <= tolerance else 0.0})
            markets_out.append({"market_ids": market_id, "quantity": total, "price": price * price_unit,
                                "best_response_max_abs_error": residual})
        return {"currency": spec["currency"], "amount_unit": 1,
                "market_firms": firms_out, "markets": markets_out}
    result = {"model": "capacity_constrained_cournot", "engine": "numpy/scipy",
              "coefficients": coefficients, "parameter_origin": "estimated" if estimation else "supplied",
              "estimation": estimation, "baseline": solve(spec["markets"])}
    if "counterfactual" in spec:
        result["counterfactual"] = solve(spec["counterfactual"]["markets"])
    return result


def dynamic_game(spec):
    """Estimate action-cost parameters in a finite-state logit Markov game.

    The joint transition kernel is supplied per state/action profile or estimated
    from observed transitions. Firms have independent, mean-zero type-I extreme
    value action shocks with fixed monetary scales. Every firm's policy is
    re-solved inside the likelihood and each counterfactual.
    """
    firms, states = list(spec["firms"]), list(spec["states"])
    n, s_count = len(firms), len(states)
    if not n or not s_count or len(set(firms)) != n or len(set(states)) != s_count:
        raise ValueError("dynamic firms and states require unique nonempty identifiers")
    state_index = {state: i for i, state in enumerate(states)}
    discount = np.broadcast_to(_array(spec["discount_factor"], "discount_factor"), (n,))
    scale = np.broadcast_to(_array(spec["shock_scale"], "shock_scale"), (n,))
    if (discount < 0).any() or (discount >= 1).any() or (scale <= 0).any():
        raise ValueError("discount factors must lie in [0,1) and fixed monetary shock scales must be positive")
    if spec["flow_timing"] != "current":
        raise ValueError("dynamic payoffs must be valued at the current decision date")
    if not spec.get("flow_definition") or not spec.get("action_timing"):
        raise ValueError("define the payoff accounting and the action-to-state timing")
    if spec["shock_role"] not in {"monetary_action_payoff", "choice_only"}:
        raise ValueError("shock_role must be monetary_action_payoff or choice_only")
    parameters = list(spec.get("parameters", []))
    names = [p["name"] for p in parameters]
    if len(set(names)) != len(names):
        raise ValueError("dynamic payoff parameter names must be unique")
    if any(("initial" in p) == ("value" in p) for p in parameters):
        raise ValueError("each payoff parameter needs either an estimation initial value or a fixed value")
    estimated_positions = [i for i, p in enumerate(parameters) if "initial" in p]
    observations = spec.get("observations", [])
    if isinstance(observations, str):
        import json
        from pathlib import Path
        observations = json.loads(Path(observations).read_text(encoding="utf-8"))
    observed = []
    transition_counts = {}
    observation_keys = set()
    for row in observations:
        key = (row["market_id"], row["period"])
        if key in observation_keys:
            raise ValueError("dynamic observations require one joint-state/action record per market and period")
        observation_keys.add(key)
        state, next_state = state_index[row["state"]], state_index[row["next_state"]]
        actions = tuple(row["actions"])
        if len(actions) != n:
            raise ValueError("observed joint actions must follow the declared firm order")
        observed.append((state, actions))
        transition_counts.setdefault((state, actions), np.zeros(s_count))[next_state] += 1

    def prepare(profile_rows, validate_observed=True):
        profiles = [[] for _ in states]
        for row in profile_rows:
            s = state_index[row["state"]]
            actions = tuple(row["actions"])
            if len(actions) != n:
                raise ValueError("profile actions must follow the declared firm order")
            base = _array(row["payoffs"], "profile payoffs", (n,))
            feature_map = row.get("payoff_features", {})
            if set(feature_map) - set(names):
                raise ValueError("payoff features must name declared parameters")
            features = _array([feature_map.get(name, [0.] * n) for name in names], "payoff features").reshape(len(names), n)
            if "transitions" in row:
                if set(row["transitions"]) - set(states):
                    raise ValueError("transition destinations must be declared states")
                transition = _array([row["transitions"].get(st, 0) for st in states], "transition weights")
                count = None
            else:
                counts = transition_counts.get((s, actions))
                if counts is None:
                    raise ValueError(f"supply transitions for state {states[s]!r}, joint actions {actions!r}")
                count = int(counts.sum())
                transition = counts / count
            if (transition < 0).any() or abs(transition.sum() - 1) > 1e-10:
                raise ValueError("each transition row must be nonnegative and sum to one")
            profiles[s].append({"actions": actions, "base": base, "features": features,
                                "transition": transition, "transition_observations": count})
        actions_by_state, encoded = [], []
        for s, rows in enumerate(profiles):
            if not rows:
                raise ValueError(f"supply action profiles for state {states[s]!r}")
            available = [list(dict.fromkeys(row["actions"][i] for row in rows)) for i in range(n)]
            joint = [row["actions"] for row in rows]
            if len(joint) != len(set(joint)) or set(joint) != set(itertools.product(*available)):
                raise ValueError(f"state {states[s]!r} requires one profile for every feasible joint action")
            actions_by_state.append(available)
            encoded.append(np.array([[available[i].index(a) for i, a in enumerate(row["actions"])] for row in rows]))
        for state, acts in observed if validate_observed else []:
            if acts not in [row["actions"] for row in profiles[state]]:
                raise ValueError("observed actions must belong to the state's feasible joint action set")
        return profiles, actions_by_state, encoded

    tolerance = float(spec.get("equilibrium_tolerance", 1e-8))
    if not 0 < tolerance < 1:
        raise ValueError("equilibrium_tolerance must lie between zero and one")

    def equilibrium(theta, model, initial_logits=None):
        profiles, action_sets, encoded = model
        dimensions = [[len(x) for x in row] for row in action_sets]
        dimension = sum(sum(a - 1 for a in row) for row in dimensions)
        flows = [np.array([row["base"] + theta @ row["features"] for row in rows]) for rows in profiles]
        transitions = [np.array([row["transition"] for row in rows]) for rows in profiles]

        def evaluate(logits):
            policy, log_policy, cursor = [], [], 0
            for dims in dimensions:
                state_policy, state_logs = [], []
                for a in dims:
                    raw = np.r_[0., logits[cursor:cursor+a-1]]
                    logs = raw - logsumexp(raw)
                    state_policy.append(np.exp(logs)); state_logs.append(logs)
                    cursor += a - 1
                policy.append(state_policy); log_policy.append(state_logs)
            transition_policy = np.zeros((s_count, s_count))
            average_flows = np.zeros((s_count, n))
            for s, joint in enumerate(encoded):
                weight = np.prod(np.column_stack([policy[s][i][joint[:, i]] for i in range(n)]), axis=1)
                transition_policy[s] = weight @ transitions[s]
                average_flows[s] = weight @ flows[s]
            values = np.empty((s_count, n))
            cash_values = np.empty((s_count, n))
            for i in range(n):
                entropy = np.array([-policy[s][i] @ log_policy[s][i] for s in range(s_count)])
                values[:, i] = np.linalg.solve(np.eye(s_count) - discount[i]*transition_policy,
                                              average_flows[:, i] + scale[i]*entropy)
                cash_values[:, i] = values[:, i] if spec["shock_role"] == "monetary_action_payoff" else np.linalg.solve(
                    np.eye(s_count) - discount[i]*transition_policy, average_flows[:, i])
            scores, choice_values, bellman = [], [], []
            for s, joint in enumerate(encoded):
                state_values = []
                for i in range(n):
                    others = np.ones(len(joint))
                    for j in range(n):
                        if j != i:
                            others *= policy[s][j][joint[:, j]]
                    continuation = flows[s][:, i] + discount[i]*(transitions[s] @ values[:, i])
                    q = np.array([others[joint[:, i] == a] @ continuation[joint[:, i] == a]
                                  for a in range(dimensions[s][i])])
                    scores.extend((log_policy[s][i][1:] - log_policy[s][i][0] - (q[1:]-q[0])/scale[i]).tolist())
                    bellman.append(values[s, i] - scale[i]*logsumexp(q/scale[i]))
                    state_values.append(q)
                choice_values.append(state_values)
            return np.array(scores), values, cash_values, policy, log_policy, choice_values, np.array(bellman)

        supplied = initial_logits if initial_logits is not None else spec.get("initial_policy_logits", np.zeros(dimension))
        initial = _array(supplied, "initial_policy_logits", (dimension,))
        if dimension:
            solved = least_squares(lambda x: evaluate(x)[0], initial, xtol=tolerance*.01,
                                   ftol=tolerance*.01, gtol=tolerance*.01,
                                   max_nfev=int(spec.get("max_equilibrium_evaluations", 3000)))
            logits, evaluations = solved.x, int(solved.nfev)
        else:
            logits, evaluations = initial, 1
        residual, values, cash_values, policy, log_policy, choices, bellman = evaluate(logits)
        max_score = float(np.max(np.abs(residual))) if residual.size else 0.
        max_bellman = float(np.max(np.abs(bellman)))
        if max_score > tolerance or max_bellman > tolerance * max(1., float(np.max(scale))):
            raise ArithmeticError(f"dynamic equilibrium residuals: policy={max_score}, Bellman={max_bellman}")
        return {"values": values, "cash_values": cash_values, "policy": policy, "log_policy": log_policy,
                "choices": choices, "logits": logits, "evaluations": evaluations,
                "initial_logits": initial, "best_response_gain": float(max(0., -bellman.min())),
                "policy_max_abs_error": max_score, "bellman_max_abs_error": max_bellman}

    model = prepare(spec["profiles"])
    theta = _array([p.get("initial", p.get("value")) for p in parameters], "payoff parameters")
    estimation = None
    if estimated_positions:
        if not observed:
            raise ValueError("payoff estimation requires observed joint states, actions and transitions")
        parameter_contract = spec.get("identification", {}).get("parameters", []) if isinstance(spec.get("identification"), dict) else []
        estimated_names = [names[i] for i in estimated_positions]
        if not set(estimated_names).issubset({p.get("name") for p in parameter_contract}):
            raise ValueError("identify each estimated payoff parameter through its economic variation and action moments")
        observed_indices = [(s, [model[1][s][i].index(a) for i, a in enumerate(acts)]) for s, acts in observed]
        def full_parameters(candidate):
            full = theta.copy()
            full[estimated_positions] = candidate
            return full
        def objective(candidate):
            result = equilibrium(full_parameters(candidate), model)
            return -sum(result["log_policy"][s][i][a] for s, actions in observed_indices for i, a in enumerate(actions))
        estimated = minimize(objective, theta[estimated_positions], method="L-BFGS-B",
                             bounds=[parameters[i].get("bounds", [None, None]) for i in estimated_positions],
                             options={"ftol": 1e-12, "gtol": 1e-6, **spec.get("estimation_options", {})})
        if not estimated.success or not np.isfinite(estimated.fun):
            raise ArithmeticError(f"dynamic payoff estimation: {estimated.message}")
        theta = full_parameters(estimated.x)
        # Choice-response rank measures the estimated model on observed states.
        observed_states = sorted({s for s, _ in observed})
        def choice_vector(candidate):
            result = equilibrium(candidate, model)
            return np.concatenate([result["policy"][s][i][1:] for s in observed_states for i in range(n)])
        jacobian = []
        for k in estimated_positions:
            coefficient = theta[k]
            step = 1e-4 * max(1., abs(coefficient))
            plus, minus = theta.copy(), theta.copy()
            plus[k] += step; minus[k] -= step
            jacobian.append((choice_vector(plus)-choice_vector(minus))/(2*step))
        rank = int(np.linalg.matrix_rank(np.array(jacobian).T))
        if rank != len(estimated_positions):
            raise ValueError("observed-state action responses must identify every estimated payoff parameter")
        estimation = {"method": "nested_fixed_point_action_likelihood", "observations": len(observed),
                      "negative_log_likelihood": float(estimated.fun), "choice_response_rank": rank,
                      "parameters": {names[i]: float(theta[i]) for i in estimated_positions}}

    def report(result, prepared):
        policies = []
        for s, state in enumerate(states):
            for i, firm in enumerate(firms):
                for a, action in enumerate(prepared[1][s][i]):
                    policies.append({"state": state, "firm_ids": firm, "action": action,
                                     "choice_share": float(result["policy"][s][i][a]),
                                     "choice_value": float(result["choices"][s][i][a])})
        transition_rows = [{"state": states[s], "actions": list(row["actions"]),
                            "transitions": dict(zip(states, row["transition"].tolist())),
                            "observations": row["transition_observations"]}
                           for s, rows in enumerate(prepared[0]) for row in rows]
        return {"state_values": [{"state": state, "firm_ids": firm, "value": float(result["values"][s, i]),
                                  "cash_flow_value": float(result["cash_values"][s, i])}
                                 for s, state in enumerate(states) for i, firm in enumerate(firms)],
                "policies": policies, "transitions": transition_rows,
                "policy_max_abs_error": result["policy_max_abs_error"],
                "bellman_max_abs_error": result["bellman_max_abs_error"],
                "best_response_gain": result["best_response_gain"],
                "initial_policy_logits": result["initial_logits"].tolist(),
                "solution_policy_logits": result["logits"].tolist(),
                "equilibrium_evaluations": result["evaluations"]}

    baseline = equilibrium(theta, model)
    output = {"model": "finite_state_logit_markov_game", "engine": "numpy/scipy",
              "solution_concept": "Markov-perfect equilibrium with independent private additive action costs",
              "discount_factor": discount.tolist(), "shock_scale": scale.tolist(),
              "shock_role": spec["shock_role"],
              "flow_timing": spec["flow_timing"], "flow_definition": spec["flow_definition"],
              "action_timing": spec["action_timing"], "currency": spec["currency"],
              "amount_unit": spec["amount_unit"], "estimation": estimation,
              "parameters": [{"name": name, "value": float(coefficient)} for name, coefficient in zip(names, theta)],
              "equilibrium_selection": "root reached from the supplied initial policy logits",
              "baseline": report(baseline, model)}
    if "counterfactual" in spec:
        changed = prepare(spec["counterfactual"]["profiles"], validate_observed=False)
        cf = equilibrium(theta, changed, spec["counterfactual"].get("initial_policy_logits"))
        output["counterfactual"] = report(cf, changed)
        output["counterfactual"]["value_changes"] = [
            {"state": state, "firm_ids": firm, "choice_value_change": float(cf["values"][s, i]-baseline["values"][s, i]),
             "cash_flow_value_change": float(cf["cash_values"][s, i]-baseline["cash_values"][s, i])}
            for s, state in enumerate(states) for i, firm in enumerate(firms)]
    return output
