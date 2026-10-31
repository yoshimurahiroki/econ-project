#!/usr/bin/env python3
"""Reproduce an observed airline demand case using free BTS/EIA data and PyBLP.

    python equity_airline_case.py --directory /path/to/user/work

The work directory receives original archives, aggregate data, model inputs,
the full estimate and a compact summary. Download size is approximately 1.4 GB.
The historical evaluation date is 2025-10-31; the downloaded historical series
may contain later revisions. This is a reconstruction, not an unrevised-vintage
backtest. A conditional four-carrier demand model does not identify total air
travel demand. Its estimated gross profits are not company-wide free cash flow.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import inspect
import json
from pathlib import Path
from urllib.request import urlopen
import zipfile

import numpy as np
import pandas as pd
import pyhdfe
from scipy.stats import t

import equity

PREPERIOD = "2022Q1"
BASELINE = "2025Q2"
AS_OF = "2025-10-31"
PERIODS = pd.period_range(PREPERIOD, BASELINE, freq="Q").astype(str).tolist()
CARRIERS = ["AA", "DL", "UA", "WN"]
EFFECTS = ["route_carrier", "market_ids", "carrier_period"]
FUEL_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DJFUELUSGULF"
PRODUCT_COLUMNS = ["market_ids", "product_ids", "firm_ids", "prices", "shares", "market_size",
                   "reference_price", "route", "route_carrier", "carrier_period", "period",
                   "demand_instruments0", "clustering_ids", "baseline_exposure", "fuel_lag", "nonstop"]


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                   default=equity.json_default, allow_nan=False) + "\n")
    temporary.replace(path)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def acquire(url, path):
    """Cache the original bytes atomically; hashes identify the retained vintage."""
    if not path.exists():
        temporary = path.with_suffix(path.suffix + ".part")
        with urlopen(url, timeout=120) as response, temporary.open("wb") as output:
            while block := response.read(4 * 1024 * 1024):
                output.write(block)
        temporary.replace(path)
    return {"url": url, "path": path.name, "sha256": digest(path), "bytes": path.stat().st_size}


def aggregation_contract():
    return {"version": 1, "carriers": CARRIERS,
            "filter_and_transformation_sha256": hashlib.sha256(inspect.getsource(aggregate).encode()).hexdigest()}


def aggregate(path, source):
    """Keep ticket-free, directional city-pair/carrier quarterly aggregates."""
    output, receipt = path.with_suffix(".csv"), path.with_suffix(".provenance.json")
    if output.exists() and receipt.exists():
        saved = json.loads(receipt.read_text())
        if (saved["sha256"] == source["sha256"] and saved.get("aggregation_contract") == aggregation_contract()
                and saved.get("aggregate_sha256") == digest(output) and
                len(pd.read_csv(output, usecols=["Year"])) == saved["aggregate_rows"]):
            return output
    columns = ["Year", "Quarter", "OriginCityMarketID", "DestCityMarketID", "OriginState", "DestState",
               "TkCarrier", "TkCarrierChange", "BulkFare", "Passengers", "MktFare", "MktMilesFlown",
               "NonStopMiles", "MktCoupons", "MktGeoType"]
    keys = ["Year", "Quarter", "OriginCityMarketID", "DestCityMarketID", "TkCarrier"]
    sums = ["Passengers", "fare_total", "miles_total", "distance_total", "nonstop_passengers"]
    pieces, source_rows, retained_rows = [], 0, 0
    with zipfile.ZipFile(path) as archive:
        name = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
        with archive.open(name) as stream:
            for data in pd.read_csv(stream, usecols=columns, chunksize=500_000):
                source_rows += len(data)
                use = ((data.BulkFare == 0) & (data.MktFare > 0) & (data.Passengers > 0)
                       & (data.MktGeoType == 2) & (data.TkCarrierChange == 0)
                       & ~data.OriginState.isin(["AK", "HI", "PR", "VI", "GU", "AS", "MP"])
                       & ~data.DestState.isin(["AK", "HI", "PR", "VI", "GU", "AS", "MP"])
                       & data.TkCarrier.isin(CARRIERS))
                data = data.loc[use].copy()
                retained_rows += len(data)
                data["fare_total"] = data.MktFare * data.Passengers
                data["miles_total"] = data.MktMilesFlown * data.Passengers
                data["distance_total"] = data.NonStopMiles * data.Passengers
                data["nonstop_passengers"] = (data.MktCoupons == 1) * data.Passengers
                pieces.append(data.groupby(keys, observed=True)[sums].sum())
    result = pd.concat(pieces).groupby(level=list(range(len(keys)))).sum().reset_index()
    for label, numerator in [("fare", "fare_total"), ("flown_miles", "miles_total"),
                             ("distance", "distance_total"), ("nonstop", "nonstop_passengers")]:
        result[label] = result[numerator] / result.Passengers
    temporary = output.with_suffix(".csv.part")
    result.to_csv(temporary, index=False)
    if len(pd.read_csv(temporary, usecols=["Year"])) != len(result):
        raise RuntimeError(f"Incomplete aggregate: {output.name}")
    temporary.replace(output)
    write_json(receipt, {**source, "source_rows": source_rows, "retained_rows": retained_rows,
                        "aggregate_rows": len(result), "sample_passengers": result.Passengers.sum(),
                        "csv": output.name, "aggregate_sha256": digest(output),
                        "aggregation_contract": aggregation_contract()})
    return output


def residualized(products, reference):
    ids = np.column_stack([pd.factorize(products[key])[0] for key in EFFECTS])
    absorb = pyhdfe.create(ids, drop_singletons=False)
    x = absorb.residualize((products.prices - products.reference_price).to_numpy()[:, None])[:, 0]
    z = absorb.residualize(products[["demand_instruments0"]].to_numpy())[:, 0]
    y = absorb.residualize(np.log(products.shares / products.market_ids.map(reference.shares))
                           .to_numpy()[:, None])[:, 0]
    return x, z, y


def diagnostics(products, reference):
    """Report common-shock uncertainty as well as the many-route statistics."""
    x, z, y = residualized(products, reference)
    zz, zx, zy = float(z @ z), float(z @ x), float(z @ y)
    if zz <= 0 or zx == 0:
        raise ValueError("The observed cost shifter does not identify a price response")
    pi, alpha = zx / zz, zy / zx
    result = {"inside_observations": len(products), "routes": products.route.nunique(),
              "quarters": sorted(products.period.unique()), "price_coefficient": alpha,
              "first_stage_coefficient": pi, "instrument_within_std": float(np.std(z)),
              "within_price_instrument_correlation": float(np.corrcoef(x, z)[0, 1]),
              "absorbed_fixed_effects": EFFECTS, "clusters": {}}
    for group in ["route", "period", "carrier_period"]:
        codes = pd.factorize(products[group])[0]
        count = len(np.unique(codes))
        correction = count / (count - 1)
        scores = np.bincount(codes, weights=z * (x - pi * z))
        pi_se = float(np.sqrt(correction * (scores @ scores) / zz**2))
        iv_scores = np.bincount(codes, weights=z * (y - alpha * x))
        alpha_se = float(np.sqrt(correction * (iv_scores @ iv_scores) / zx**2))
        result["clusters"][group] = {"count": count, "first_stage_F": (pi / pi_se)**2,
                                      "price_coefficient_se": alpha_se}
    # Invert the AR moment-regression test. This does not divide by a possibly
    # weak first stage to form a symmetric Wald interval for the price effect.
    codes = pd.factorize(products.period)[0]
    count = len(np.unique(codes))
    u = np.bincount(codes, weights=z * (y - zy / zz * z))
    v = np.bincount(codes, weights=z * (x - pi * z))
    critical = float(t.ppf(.975, count - 1)**2)
    factor = critical * count / (count - 1)
    coefficients = [zx*zx - factor*(v @ v), -2*zy*zx + 2*factor*(u @ v), zy*zy - factor*(u @ u)]
    roots = np.roots(coefficients)
    bounded = bool(coefficients[0] > 0 and np.isreal(roots).all())
    interval = sorted(float(value.real) for value in roots) if bounded else None
    result["anderson_rubin"] = {"confidence": .95, "common_shock_clusters": count,
        "reference_degrees_of_freedom": count - 1, "critical_F": critical,
        "quadratic_coefficients": coefficients, "bounded": bounded, "interval": interval,
        "inference": "Quarter-cluster AR-type inversion with a small-cluster t approximation; not an exact randomization test."}
    result["leave_one_quarter_out"] = []
    for quarter in sorted(products.period.unique()):
        xx, zz, yy = residualized(products.loc[products.period != quarter], reference)
        result["leave_one_quarter_out"].append({"excluded": quarter,
            "price_coefficient": float(zz @ yy / (zz @ xx)), "first_stage_coefficient": float(zz @ xx / (zz @ zz))})
    result["interpretation"] = ("Common fuel shocks occur in 13 quarters. The quarter-cluster first stage is weak, "
        "and the magnitude interval is wide. Treat point counterfactuals as conditional sensitivity calculations; "
        "the exclusion restriction is an economic assumption, not a consequence of the first-stage statistic.")
    return result


def prepare(directory):
    sources, files = [], []
    for period in PERIODS:
        year, quarter = period.split("Q")
        path = directory / f"db1b-market-{year}q{quarter}.zip"
        url = f"https://transtats.bts.gov/PREZIP/Origin_and_Destination_Survey_DB1BMarket_{year}_{quarter}.zip"
        source = acquire(url, path)
        sources.append({**source, "sample_rate": .1, "authority": "US DOT Bureau of Transportation Statistics"})
        files.append(aggregate(path, source))
    fuel_path = directory / "jetfuel.csv"
    sources.append({**acquire(FUEL_URL, fuel_path), "authority": "US EIA via Federal Reserve Bank of St Louis"})
    data = pd.concat([pd.read_csv(path) for path in files], ignore_index=True)
    data["route"] = data.OriginCityMarketID.astype(str) + "-" + data.DestCityMarketID.astype(str)
    data["period"] = data.Year.astype(str) + "Q" + data.Quarter.astype(str)
    data["route_carrier"] = data.route + "-" + data.TkCarrier
    data["carrier_period"] = data.TkCarrier + "-" + data.period
    total_coverage = data.groupby(["period", "TkCarrier"]).Passengers.sum()
    counts = data.groupby(["route", "period"]).TkCarrier.nunique().unstack()
    routes = counts[(counts == 4).all(axis=1)].index
    data = data.loc[data.route.isin(routes)].copy()
    exposure = data.loc[data.period == PREPERIOD].set_index("route_carrier").flown_miles / 1000
    data = data.loc[data.period != PREPERIOD].copy()
    data["baseline_exposure"] = data.route_carrier.map(exposure)
    data["market_ids"] = data.route + "-" + data.period
    data["firm_ids"], data["product_ids"] = data.TkCarrier, data.TkCarrier
    data["market_size"] = data.groupby("market_ids").Passengers.transform("sum") * 10
    data["shares"], data["prices"] = data.Passengers * 10 / data.market_size, data.fare
    reference = data.loc[data.firm_ids == "AA"].set_index("market_ids")
    data["reference_price"] = data.market_ids.map(reference.prices)
    fuel = pd.read_csv(fuel_path, parse_dates=["observation_date"])
    fuel["period"] = fuel.observation_date.dt.to_period("Q")
    quarter_fuel = fuel.groupby("period").DJFUELUSGULF.mean()
    data["fuel_lag"] = data.period.map(lambda p: float(quarter_fuel.loc[pd.Period(p, freq="Q") - 1]))
    relative_exposure = data.baseline_exposure - data.market_ids.map(reference.baseline_exposure)
    data["demand_instruments0"] = data.fuel_lag * relative_exposure
    data["clustering_ids"] = data.route
    products = data.loc[data.firm_ids != "AA", PRODUCT_COLUMNS].copy()
    reference = data.loc[data.firm_ids == "AA", PRODUCT_COLUMNS].copy()
    products.to_csv(directory / "airline-products.csv", index=False)
    reference.to_csv(directory / "airline-reference.csv", index=False)
    checks = diagnostics(products, reference.set_index("market_ids"))
    identification = {
        "market_definition": "Directional city-pair-quarter choice conditional on a paid AA/DL/UA/WN ticket; all four observed in every quarter from 2022Q1 to 2025Q2.",
        "market_size": "Observed four-carrier DB1B passengers times the official 10% sampling expansion. No assumed population or trip-frequency multiplier.",
        "reference": "AA normalizes utility during estimation and remains a strategic price setter in equilibrium.",
        "scope": "The four-carrier passenger pool is fixed in equilibrium. Total travel demand and substitution to other airlines are not identified.",
        "parameters": [{"name": "common price coefficient", "role": "price", "moments": ["demand_instruments0"],
            "variation": "Lagged quarterly EIA jet-fuel spot USD/gallon times 2022Q1 carrier-route flown miles/1000, relative to AA exposure.",
            "exclusion": "After carrier-route, route-quarter and carrier-quarter effects, fuel shocks times predetermined route exposure affect relative carrier utility only through fares. Fuel-induced service changes and exposure-specific demand shifts can violate this restriction.",
            "source": "BTS DB1B and EIA DJFUELUSGULF; cost-shift motivation: https://www.nber.org/papers/w20293 and https://cep.lse.ac.uk/pubs/download/dp1709.pdf"}],
        "limits": ["Fixed route set conditions on continuing four-carrier service.",
                   "A common nominal USD price coefficient is imposed over 2022Q2–2025Q2; heterogeneous preferences require additional identifying moments.",
                   "Reported fares exclude ancillary charges; average carrier products do not separate fare classes or flight frequency.",
                   "Current public historical archives can contain revisions after the historical evaluation date."],
        "diagnostics": checks}
    spec = {"model": "conditional_logit", "market": "US domestic four-carrier conditional choices, 2022Q2–2025Q2",
            "as_of": AS_OF, "currency": "USD", "price_unit": 1, "quantity_unit": "directional passenger",
            "products": str(directory / "airline-products.csv"), "reference_products": str(directory / "airline-reference.csv"),
            "demand": {"linear": "0 + I(prices-reference_price)",
                # Separate factors preserve identical effects while avoiding a
                # quadratic-size Patsy contrast matrix for route-quarter IDs.
                "absorb": "C(route):C(firm_ids) + C(route):C(period) + C(firm_ids):C(period)"},
            "solve": {"method": "1s", "se_type": "clustered", "W_type": "clustered"},
            "sources": sources, "identification": identification}
    write_json(directory / "airline-fit-input.json", spec)
    write_json(directory / "airline-identification-diagnostics.json", checks)
    coverage = [{"period": period, "firm": carrier, "all_retained_db1b_passengers": total * 10,
        "modeled_passengers": data.loc[(data.period == period) & (data.firm_ids == carrier), "Passengers"].sum() * 10}
        for (period, carrier), total in total_coverage.items() if period != PREPERIOD]
    write_json(directory / "coverage.json", coverage)
    return spec, checks, coverage


def support_tables(result, directory, checks):
    """Use the same market support for every coefficient in the AR interval."""
    products = pd.DataFrame(result["baseline"]["products"])
    products = products.loc[products.market_ids.str.endswith(BASELINE)].copy()
    actual = pd.read_csv(directory / "db1b-market-2025q2.csv")
    denominator = actual.groupby("TkCarrier").Passengers.sum() * 10
    actual["market_ids"] = actual.OriginCityMarketID.astype(str) + "-" + actual.DestCityMarketID.astype(str) + "-" + BASELINE
    actual = actual.rename(columns={"TkCarrier": "firm_ids"})
    products = products.merge(actual[["market_ids", "firm_ids", "flown_miles"]], on=["market_ids", "firm_ids"], validate="one_to_one")
    interval = checks["anderson_rubin"]["interval"]
    rules = [("point", "unit_cost")]
    if interval and interval[-1] < 0:
        products["ar_upper_unit_cost"] = products.price + 1 / (interval[-1] * (1 - products.share))
        rules.append(("ar_interval", "ar_upper_unit_cost"))
    rows = []
    for label, cost in rules:
        valid = products.groupby("market_ids")[cost].min().ge(0)
        selected = products.loc[products.market_ids.isin(valid[valid].index)]
        selected.to_csv(directory / f"airline-baseline-2025q2-{label}-valid.csv", index=False)
        for carrier, group in selected.groupby("firm_ids"):
            rows.append({"support": label, "firm": carrier, "market_count": len(group),
                         "quantity": group.quantity.sum(), "revenue_usd": group.revenue.sum(),
                         "point_gross_profit_usd": group.gross_profit.sum(),
                         "share_of_retained_carrier_db1b_passengers": group.quantity.sum() / denominator[carrier]})
    return {"baseline_period": BASELINE, "all_modeled_markets": products.market_ids.nunique(), "rows": rows,
        "support_rule": "Every carrier in a retained market has nonnegative inverse-FOC marginal cost. The interval support is fixed at the least price-elastic AR endpoint. Estimation uses the full sample; support restricts only the monetized counterfactual coverage.",
        "financial_bridge": "Use the corresponding quarter's change in gross profit only. If a financial fuel forecast already counts the direct cost effect, subtract that fixed-quantity direct effect before adding the strategic response. Do not multiply the covered market change into all company routes or four quarters."}


def fit_contract(spec):
    """Bind a saved estimate to data, economic specification and executed owners."""
    normalized = copy.deepcopy(spec)
    frames = []
    for field in ("products", "reference_products"):
        frame = equity.records(spec[field])
        frames.append(frame)
        serialized = frame.to_json(orient="split", double_precision=15).encode()
        normalized[field] = {"data_sha256": hashlib.sha256(serialized).hexdigest()}
    for source in normalized["sources"]:
        if "path" in source and "sha256" in source:
            source["path"] = {"data_sha256": source["sha256"]}
    serialized = json.dumps(normalized, sort_keys=True, separators=(",", ":"),
                            default=equity.json_default, allow_nan=False).encode()
    complete = pd.concat(frames, ignore_index=True).to_json(orient="split", double_precision=15).encode()
    owner = Path(equity.__file__)
    return {"version": 1, "normalized_spec_sha256": hashlib.sha256(serialized).hexdigest(),
            "data_sha256": hashlib.sha256(complete).hexdigest(),
            "calculation_sha256": {name: digest(owner.with_name(name)) for name in ("equity.py", "equity_io.py")}}


def run(directory, reuse_fit=False):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    spec, checks, coverage = prepare(directory)
    fit_path = directory / "airline-fit-result.json"
    contract = fit_contract(spec)
    if reuse_fit and fit_path.exists():
        result = json.loads(fit_path.read_text())
        if result.get("case_contract") != contract or result["input_sha256"] != contract["data_sha256"]:
            raise ValueError("Saved fit data, economic specification or calculation code changed; rerun without --reuse-fit")
    else:
        import pyblp
        pyblp.options.verbose = False
        result = equity.fit(spec)
        if contract != fit_contract(spec):
            raise RuntimeError("Case inputs or calculation code changed during estimation; rerun the case")
        result["case_contract"] = contract
        write_json(fit_path, result)
    support = support_tables(result, directory, checks)
    write_json(directory / "airline-cost-support-coverage.json", support)
    cost_support = {key: value for key, value in result["cost_support"].items() if key != "affected_products"}
    summary = {"case": "LUV and AA/DL/UA conditional carrier demand", "as_of": AS_OF,
        "baseline_period": BASELINE, "data_vintage": "Currently retrieved historical archives; later revisions possible",
        "engine": result["engine"], "engine_version": result["engine_version"],
        "model": result["model"], "observations_including_reference": result["observations"], "markets": result["markets"],
        "price_coefficient_usd_inverse": result["price_coefficient"], "standard_errors": result["standard_errors"],
        "pyblp_error_clustering": "route", "identification_diagnostics": checks,
        "solution_residuals": result["solution_residuals"], "cost_support": cost_support,
        "financial_coverage": support, "all_modeled_coverage": coverage,
        "input_sha256": result["input_sha256"], "case_contract": contract, "sources": spec["sources"],
        "economic_conditions": {key: value for key, value in spec["identification"].items() if key != "diagnostics"},
        "use": "Observed-data estimation and conditional sensitivity analysis. The wide price-response interval and limited common cost support do not establish a company-wide structural valuation."}
    write_json(directory / "airline-case-summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, help="User-owned directory for originals and generated results")
    parser.add_argument("--reuse-fit", action="store_true", help="Reuse an existing fit only when normalized input hashes match")
    arguments = parser.parse_args()
    summary = run(arguments.directory, arguments.reuse_fit)
    print(json.dumps({key: summary[key] for key in ["as_of", "model", "observations_including_reference", "markets",
                                                   "price_coefficient_usd_inverse"]}, indent=2))


if __name__ == "__main__":
    main()
