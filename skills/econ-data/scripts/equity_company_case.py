#!/usr/bin/env python3
"""Reconstruct LUV at 2025-10-31 from issuer filings and public market data.

Run equity_airline_case.py in the same --directory first. Generated source
documents, inputs and results stay in that directory. This is a conditional
operating-state valuation using revised historical BTS data, not a point-in-time
backtest or a forecast that management's initiative targets will be achieved.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
from lxml import html
from scipy.optimize import brentq, shgo

import equity
from equity_io import conditional_logit


ISSUER = "https://investors.southwest.com/sec-filings/all-sec-filings/content/"
SOURCES = {
    "fy2024": ("luv-fy2024-release.html", ISSUER + "0000092380-25-000007/er-12312024xerdoc.htm", "2025-01-30"),
    "q2": ("luv-q2-release.html", ISSUER + "0000092380-25-000131/er-6302025xerdoc.htm", "2025-07-23"),
    "q2_10q": ("luv-q2-10q.html", ISSUER + "0000092380-25-000134/luv-20250630.htm", "2025-07-24"),
    "q3": ("luv-q3-release.html", ISSUER + "0000092380-25-000138/er-9302025xerdoc.htm", "2025-10-22"),
    "q3_10q": ("luv-q3-10q.html", ISSUER + "0000092380-25-000140/luv-20250930.htm", "2025-10-23"),
    "price": ("luv-price-20251031.json", "https://query1.finance.yahoo.com/v8/finance/chart/LUV?period1=1761868800&period2=1762214400&interval=1d", "2025-10-31"),
    "treasury": ("luv-treasury-202510.html", "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value=202510&type=daily_treasury_yield_curve", "2025-10-31"),
    "beta": ("luv-airline-betas-jan2025.xls", "https://pages.stern.nyu.edu/~adamodar/pc/archives/betas24.xls", "2025-01-05"),
    "erp": ("luv-erp-jan2025.xlsx", "https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPJan25.xlsx", "2025-01"),
    "capitalized_interest_classification": ("luv-fas95.pdf", "https://storage.fasb.org/fas95.pdf", "1987-11"),
}
# Reviewed workbook observations; pinned bytes make the extraction auditable
# without adding an Excel engine to the numerical requirements.
WORKBOOK_CELLS = {
    "beta": {"sha256": "cd3f0356e71588d974bb2cb16f5398aec576992e3dfe49e959e54d77c329d636",
             "sheet": "Industry Averages", "row": "Air Transport",
             "column": "Unlevered beta corrected for cash", "value": .76},
    "erp": {"sha256": "d2191ce864715676a16ca4c0e12917005b4a0a6161e0a6482a280e03a02c6de8",
            "sheet": "Impl premium calculator", "cell": "C42",
            "row": "Implied Risk Premium in current level of Index =", "value": .04332785595907897},
}


def save(directory, name, content):
    (directory / name).write_text(json.dumps(content, ensure_ascii=False, indent=2,
                                            default=equity.json_default, allow_nan=False) + "\n")


def source_documents(directory):
    registry, documents = {}, {}
    for key, (filename, url, published) in SOURCES.items():
        path = directory / filename
        if not path.exists():
            request = Request(url, headers={"User-Agent": "EconomicsResearchCase/0.8 public-source-reproduction"})
            with urlopen(request, timeout=60) as response:
                data = response.read()
            path.write_bytes(data)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if key in WORKBOOK_CELLS and digest != WORKBOOK_CELLS[key]["sha256"]:
            raise ValueError(f"{filename}: archived workbook changed; review its cited cell before using it")
        registry[key] = {"url": url, "published_at": published, "file": filename,
                         "sha256": digest, "checked_at": datetime.now(timezone.utc).isoformat()}
        accession = re.search(r"/(\d{10}-\d{2}-\d{6})/", url)
        if accession:
            announcement = "SEC:92380:" + accession[1]
            registry[key].update(announcement_id=announcement, event_id=announcement+":initial-facts", revision=0)
        if filename.endswith(".html"):
            document = html.fromstring(data.decode("utf-8"))
            rows = [[" ".join(cell.text_content().split()) for cell in row.xpath("./td|./th")]
                    for row in document.xpath("//tr")]
            documents[key] = (document, rows)
    return registry, documents


def numeric_cells(row):
    values = []
    for cell in row[1:]:
        cleaned = cell.replace(",", "").replace(" ", "").replace("%", "")
        if re.fullmatch(r"\(?-?\d+(?:\.\d+)?\)?", cleaned):
            values.append(float(cleaned.replace("(", "-").replace(")", "")))
        elif cleaned in {"—", "–"}:
            values.append(0.0)
    return values


def extract_facts(directory, registry, documents):
    observations = []

    def row(source, label, *, prefix=False):
        matches = [(i, r) for i, r in enumerate(documents[source][1]) if r and
                   (r[0].startswith(label) if prefix else r[0] == label)]
        if not matches:
            raise ValueError(f"missing source row {source}: {label}")
        index, cells = matches[0]
        values = numeric_cells(cells)
        observations.append({"source": source, "html_row_zero_based": index,
                             "label": cells[0], "values": values})
        return values

    labels = {
        "revenue": "Total operating revenues",
        "nonfuel_expense": "Operating expenses, excluding Fuel and oil expense and special items",
        "unhedged_fuel_expense": "Fuel and oil expense, unhedged",
        "economic_fuel_expense": "Fuel and oil expense, excluding special items (economic)",
        "depreciation": "Depreciation and amortization",
        "rpm_million": "Revenue passenger miles (RPMs) (in millions)",
        "asm_million": "Available seat miles (ASMs) (in millions)",
        "gallons_million": "Fuel consumed, in gallons (millions)",
        "passengers_thousand": "Revenue passengers carried (000s)",
        "interest_expense": "Interest expense",
        "capitalized_interest": "Capitalized interest",
    }
    annual, snapshots = {}, {}
    for key, label in labels.items():
        values = row("fy2024", label, prefix=key in {"rpm_million", "asm_million"})
        annual[key] = values[2] if key == "unhedged_fuel_expense" else values[3]
    annual["revenue"] = row("fy2024", "Operating revenues, excluding special items")[3]
    annual["sale_leaseback_gain"] = -row("fy2024", "Gain on sale-leaseback transactions")[2]
    annual["capex"] = -row("fy2024", "Capital expenditures")[2]
    for quarter in ("q2", "q3"):
        data = {"period": "2025-06-30" if quarter == "q2" else "2025-09-30"}
        for key, label in labels.items():
            values = row(quarter, label, prefix=key in {"rpm_million", "asm_million"})
            current, prior = (values[2:4] if key == "unhedged_fuel_expense" else values[3:5])
            data[key] = annual[key] + current - prior
        gain = row(quarter, "Gain on sale-leaseback transactions")
        data["sale_leaseback_gain"] = annual["sale_leaseback_gain"] - gain[2] + gain[3]
        capex = row(quarter, "Capital expenditures")
        data["reported_ttm_capex"] = annual["capex"] - capex[2] + capex[3]
        data["cash"] = row(quarter, "Cash and cash equivalents")[0]
        data["short_term_investments"] = row(quarter, "Short-term investments")[0]
        data["cash_like"] = data["cash"] + data["short_term_investments"]
        data["debt"] = row(quarter, "Current maturities of long-term debt")[0] + row(quarter, "Long-term debt less current maturities")[0]
        data["book_equity"] = row(quarter, "Total stockholders' equity")[0]
        data["tax_rate"] = row(quarter, "Non-GAAP tax rate (B)")[0] / 100
        document = documents[quarter + "_10q"][0]
        text = " ".join(document.text_content().split())
        match = re.search(r"Number of shares of Common Stock outstanding.{0,120}:\s*([\d,]+)", text)
        if not match:
            raise ValueError(f"missing {quarter} cover share count")
        data["cover_shares_million"] = int(match[1].replace(",", "")) / 1e6
        data["rsu_dilution_proxy_million"] = row(quarter + "_10q", "Dilutive effect of restricted stock units")[0]
        data["diluted_shares_million"] = data["cover_shares_million"] + data["rsu_dilution_proxy_million"]
        data["capacity_plan_growth"] = .01 if quarter == "q2" else .015
        data["load_factor"] = data["rpm_million"] / data["asm_million"]
        data["effective_revenue_per_rpm"] = data["revenue"] / data["rpm_million"]
        data["cash_fuel_per_gallon"] = data["unhedged_fuel_expense"] / data["gallons_million"]
        data["gallons_per_asm"] = data["gallons_million"] / data["asm_million"]
        data["nonfuel_cash_per_asm"] = (data["nonfuel_expense"] - data["depreciation"] + data["sale_leaseback_gain"]) / data["asm_million"]
        data["book_operating_capital_proxy"] = data["book_equity"] + data["debt"] - data["cash_like"]
        snapshots[quarter] = data
    for quarter, phrase in (("q2", "capacity to be up roughly 1 percent"), ("q3", "capacity to be up roughly 1.5 percent")):
        text = " ".join(documents[quarter][0].text_content().split())
        if phrase not in text or "$2.5 billion to $3.0 billion" not in text:
            raise ValueError(f"review {quarter} capacity/capex guidance")
    q3_text = " ".join(documents["q3_10q"][0].text_content().split())
    if "550 million gallons" not in q3_text or "$92 million gain" not in q3_text:
        raise ValueError("review Q3 forward fuel volume and asset-sale adjustment")
    fuel_row = next(r for r in documents["q3"][1] if r and r[0].startswith("Fuel cost per gallon"))
    fuel_prices = [float(v) for v in re.findall(r"\$(\d+\.\d+)", " ".join(fuel_row))]
    q3_release = " ".join(documents["q3"][0].text_content().split())
    premium = float(re.search(r"premium expense of \$(\d+\.\d+) per gallon", q3_release)[1])
    if len(fuel_prices) != 2 or not re.search(r"Cash dividends,\s*\$\s*0\.18\s*per share", q3_text):
        raise ValueError("review Q4 fuel range and declared dividend")
    guidance = {"capex_usd_million": [2500, 3000], "q4_cash_fuel_price": [p-premium for p in fuel_prices],
                "q4_fuel_gallons_million": 550, "fuel_premium_already_expended_per_gallon": .07,
                "initiative_ebit_targets_usd_million": {"2025": 1800, "2026": 4300},
                "declared_quarterly_dividend_per_share": .18,
                "source_ids": ["q2", "q3", "q3_10q"]}
    price_data = json.loads((directory / SOURCES["price"][0]).read_text())["chart"]["result"][0]
    index = next(i for i, t in enumerate(price_data["timestamp"])
                 if datetime.fromtimestamp(t, timezone.utc).date().isoformat() == "2025-10-31")
    price = round(price_data["indicators"]["quote"][0]["close"][index], 2)
    treasury_rows = documents["treasury"][1]
    header = next(r for r in treasury_rows if r and r[0] == "Date" and "10 Yr" in r)
    rates = next(r for r in treasury_rows if r and r[0] == "10/31/2025")
    curve = {tenor: float(rates[header.index(tenor)])/100 for tenor in ("1 Yr", "2 Yr", "5 Yr", "10 Yr")}
    debt_rows = [r for r in documents["q3_10q"][1] if r and
                 re.match(r"(?:3\.00|7\.375|3\.45|5\.125|2\.625|1\.000)\s*%", r[0])]
    debt_values = [numeric_cells(r)[:3] for r in debt_rows]
    if len(debt_values) != 7:
        raise ValueError("review the seven disclosed debt fair-value rows")
    market_debt = sum(r[2] for r in debt_values) + snapshots["q3"]["debt"] - sum(r[1] for r in debt_values)
    bond_row = next(r for r in debt_rows if r[0].startswith("2.625"))
    bond = numeric_cells(bond_row)
    observations.append({"source": "q3_10q", "label": bond_row[0], "values": bond})
    years, face, bond_price = 5, bond[1], bond[2]
    bond_yield = brentq(lambda y: sum(face*.02625/(1+y)**t for t in range(1, years+1)) + face/(1+y)**years-bond_price, 0, .20)
    beta, erp, tax = WORKBOOK_CELLS["beta"]["value"], WORKBOOK_CELLS["erp"]["value"], snapshots["q3"]["tax_rate"]
    market_equity = price * snapshots["q3"]["cover_shares_million"]
    capital_cost = {"risk_free_rate": curve["10 Yr"], "equity_premium": erp,
                    "levered_beta": beta*(1+(1-tax)*market_debt/market_equity),
                    "equity_market_value": market_equity, "debt_market_value": market_debt,
                    "credit_spread": bond_yield-curve["5 Yr"], "tax_rate": tax}
    facts = {"financial_amount_unit": "USD million", "annual_2024": annual, "snapshots": snapshots,
             "guidance": guidance, "price": {"date": "2025-10-31", "unadjusted_close_usd": price},
             "treasury_curve": curve, "capital_cost_inputs": capital_cost,
             "capital_cost": equity.wacc(capital_cost), "reviewed_workbook_cells": WORKBOOK_CELLS,
             "credit_calibration": {"bond": "2.625% 2030", "face": face, "fair_value": bond_price,
                                    "yield": bond_yield, "annual_coupon_five_year_timing_approximation": True,
                                    "market_debt_proxy": market_debt},
             "observations": observations, "sources": registry}
    save(directory, "luv-input-facts.json", facts)
    return facts


def forecast_input(facts, quarter, capex=2750, *, fuel_news=False, io_correction=0):
    snapshot, source = facts["snapshots"][quarter], facts["sources"]
    capacity = facts["annual_2024"]["asm_million"] * (1+snapshot["capacity_plan_growth"])
    gallons = capacity * snapshot["gallons_per_asm"]
    cash_cost = capacity * snapshot["nonfuel_cash_per_asm"] + gallons*snapshot["cash_fuel_per_gallon"]
    sources = [source[key] for key in ("fy2024", quarter, quarter+"_10q", "price", "treasury", "beta", "erp", "capitalized_interest_classification")]
    segment = {"name": "Airline operating state", "quantity_unit": "million revenue passenger miles",
               "capacity": capacity, "utilization": snapshot["load_factor"],
               "price": snapshot["effective_revenue_per_rpm"], "price_unit": 1e6,
               "unit_variable_cost": 0, "fixed_cash_cost": cash_cost,
               "depreciation": snapshot["depreciation"], "capex": capex,
               "change_working_capital": 0, "sources": sources[:3]}
    first = {"segments": [copy.deepcopy(segment)], "tax_rate": snapshot["tax_rate"],
             "corporate_fixed_cash_cost": -io_correction}
    renewal = copy.deepcopy(first)
    renewal["segments"][0]["capex"] = snapshot["depreciation"]
    renewal["corporate_fixed_cash_cost"] = 0
    if fuel_news:
        price = sum(facts["guidance"]["q4_cash_fuel_price"])/2
        first["segments"][0]["fixed_cash_cost"] += facts["guidance"]["q4_fuel_gallons_million"] * (price-snapshot["cash_fuel_per_gallon"])
    result = {"method": "fcff", "company": "Southwest Airlines Co. (LUV)", "currency": "USD", "market": "US",
              "as_of": "2025-10-31", "price_as_of": "2025-10-31", "amount_unit": 1e6, "share_unit": 1e6,
              "diluted_shares": snapshot["diluted_shares_million"], "current_price": facts["price"]["unadjusted_close_usd"],
              "capital_cost": facts["capital_cost_inputs"], "discount_rate": facts["capital_cost"]["wacc"],
              "balance": {"cash": snapshot["cash_like"], "operating_cash": 0, "debt": snapshot["debt"], "lease_liabilities": 0},
              "invested_capital_begin": snapshot["book_operating_capital_proxy"], "incremental_roic_lag": 1,
              "forecasts": [first, renewal], "terminal": {"growth": 0, "roic": facts["capital_cost"]["wacc"]},
              "sources": sources,
              "assumptions": {
                  "scope": "Two annual operating-state periods calibrated to disclosed 2025 capacity; not a 2026 management forecast. Both Q2 and Q3 information states use the same October 31 market price and capital-cost proxy.",
                  "demand": "TTM load factor and total operating revenue per RPM held fixed; this effective revenue includes ancillary/other revenue.",
                  "cost": "Cash fuel and nonfuel expenses scale with scheduled ASM, not bookings at a fixed schedule. Capital spending is treated as operating investment; financing interest is excluded from operating FCFF.",
                  "fuel": "Use unhedged expense; previously paid hedge-premium amortization is excluded from future cash expense. Q4 guidance applies only to 550 million gallons in period one.",
                  "investment": "First-period capex is the disclosed total capital-spending midpoint, including expected aircraft sales; its maintenance/growth split is unidentified. Period two and zero-growth terminal renewal equal DA, an explicit proxy. The book-capital roll-forward does not separately identify disposal book values.",
                  "capitalized_interest": "Base condition sets operating cash investment numerically equal to the reported capital-spending guidance; this does not identify reported spending as excluding capitalized cash interest. FAS95 paragraph 17(c), footnote 7 includes capitalized paid interest in investing cash flows. A separate first-period 0/49m reclassification comparison uses TTM capitalized accrued interest as a proxy; these are conditions, not an identified interval for cash paid.",
                  "tax": "Reported rolling normalized effective tax rate is used as a cash-tax proxy; tax timing and prepaid-hedge tax shields are not separately identified.",
                  "capital_cost": "January 2025 US air-transport cash-corrected asset beta and ERP, October 31 Treasury curve, approximate disclosed 2030 bond yield; peer lease treatment may differ.",
                  "leases": "Operating rents remain in cash operating costs; no second deduction of operating lease liabilities. Finance leases remain in reported debt.",
                  "shares": "Cover-date common shares plus current-quarter 3m RSU dilution proxy; future buybacks absent, with already-paid buybacks reflected once in cash and shares.",
                  "liquidity": "Zero required operating cash is one boundary, not an estimate; all-cash-required boundary is also computed.",
                  "working_capital": "No incremental operating working capital in the stationary scenario; cash-flow sensitivity per additional USD100m is reported.",
                  "incremental_roic": "Change in NOPAT divided by lagged net investment is an accounting diagnostic; the reversal of temporary fuel savings is not a causal investment-return estimate.",
                  "io_fuel_exposure": "Default fixed schedule: fuel changes capacity cash cost, with zero ticket marginal-cost shock. A separate medium-run frequency-adjustment scenario uses average fuel intensity as a conditional marginal exposure.",
              }}
    return result


def structural_news(directory, facts):
    products = pd.read_csv(directory / "airline-baseline-2025q2-ar_interval-valid.csv")
    if "flown_miles" not in products:
        raise ValueError("rerun equity_airline_case.py to include actual 2025Q2 flown miles")
    airline = json.loads((directory / "airline-case-summary.json").read_text())
    lower, upper = sorted(airline["identification_diagnostics"]["anderson_rubin"]["interval"])
    alphas = [lower, airline["price_coefficient_usd_inverse"], upper]
    products = products.rename(columns={"price": "prices", "share": "shares"})
    products["market_size"] = products.quantity/products.shares
    snapshot = facts["snapshots"]["q3"]
    fuel_change = sum(facts["guidance"]["q4_cash_fuel_price"])/2-snapshot["cash_fuel_per_gallon"]
    cost_change = np.where(products.firm_ids == "WN", fuel_change*snapshot["gallons_million"]/snapshot["rpm_million"]*products.flown_miles, 0)
    least_elastic = conditional_logit(products, upper)["baseline_costs"]
    rejected = set(products.loc[(least_elastic < 0) | (least_elastic+cost_change < 0), "market_ids"])
    original_markets = products.market_ids.nunique()
    keep = ~products.market_ids.isin(rejected)
    products, cost_change = products.loc[keep].reset_index(drop=True), cost_change[keep]
    if products.empty:
        raise ValueError("no common nonnegative-cost support for the entire coefficient interval and fuel counterfactual")
    evaluated = {}
    def evaluate(alpha):
        alpha = float(alpha)
        if alpha in evaluated:
            return evaluated[alpha]
        costs = conditional_logit(products, alpha)["baseline_costs"]
        solved = conditional_logit(products, alpha, {"costs": costs+cost_change})
        if np.min(solved["costs"]) < 0:
            raise ValueError("counterfactual costs must remain nonnegative on the adopted support")
        mask = (products.firm_ids == "WN").to_numpy()
        quantities = solved["shares"]*products.market_size.to_numpy()
        baseline = np.sum((products.prices.to_numpy()[mask]-costs[mask])*products.quantity.to_numpy()[mask])
        changed = np.sum((solved["prices"][mask]-solved["costs"][mask])*quantities[mask])
        direct = -np.sum(cost_change[mask]*products.quantity.to_numpy()[mask])
        correction = changed-baseline-direct
        evaluated[alpha] = {"alpha_per_usd": alpha, "market_count": int(products.market_ids.nunique()),
                     "wn_passengers": float(products.loc[mask, "quantity"].sum()),
                     "wn_baseline_gross_profit_usd": float(baseline), "wn_counterfactual_gross_profit_usd": float(changed),
                     "direct_cost_saving_usd": float(direct), "gross_profit_change_usd": float(changed-baseline),
                     "strategic_correction_usd": float(correction), "corporate_fcff_correction_usd_million": float(correction/1e6*(1-snapshot["tax_rate"])),
                     "maximum_best_response_error": max(x["best_response_max_abs_error"] for x in solved["equilibrium_residuals"]),
                     "min_baseline_cost": float(min(costs)), "min_counterfactual_cost": float(min(solved["costs"])),
                     "maximum_competitor_price_change_usd": float(np.max(np.abs(solved["prices"][~mask]-products.prices.to_numpy()[~mask]))),
                     "wn_quantity_change": float(np.sum(quantities[mask]-products.quantity.to_numpy()[mask]))}
        return evaluated[alpha]
    rows = [evaluate(alpha) for alpha in alphas]
    extrema = {}
    for name, sign in (("minimum", 1), ("maximum", -1)):
        optimum = shgo(lambda x: sign*evaluate(-np.exp(float(x[0])))["strategic_correction_usd"],
                       [(np.log(-upper), np.log(-lower))], n=32, iters=2)
        if not optimum.success:
            raise ArithmeticError(f"coefficient-interval {name} search did not converge")
        extrema[name] = evaluate(-np.exp(float(optimum.x[0])))
    result = {"scope": "Conditional medium-run WN-specific fuel-cost update with rival marginal costs fixed; all four prices re-equilibrate. No aggregate travel-demand response.",
              "application": "One covered-quarter correction under observed 2025Q2 market composition only; no inverse-coverage extrapolation or annual multiplication. Q4 route composition is not identified.",
              "distance_calibration": "Observed corporate gallons/RPM times each 2025Q2 carrier-route flown distance. Interpreting this average as marginal ticket fuel exposure requires a medium-run condition: route capacity/frequency can scale with carried traffic. It is not an identified route fuel-production function or a fixed-schedule ticket marginal cost.",
              "double_count_control": "Add gross-profit change minus baseline-quantity direct cost saving; the company physical forecast already includes fuel savings.",
              "baseline_interval_valid_market_count": int(original_markets), "news_excluded_markets": sorted(rejected),
              "adopted_market_ids": sorted(products.market_ids.unique().tolist()), "fuel_price_change_per_gallon": fuel_change,
              "fixed_schedule": {"ticket_marginal_fuel_cost_change": 0, "equilibrium_price_and_quantity_change": 0,
                                 "direct_cash_saving_on_covered_routes_usd": rows[1]["direct_cost_saving_usd"],
                                 "additional_strategic_correction_usd": 0,
                                 "interpretation": "Fuel changes the cash cost of the already scheduled flights. The corporate physical forecast counts the saving; add no further IO profit."},
              "rows": rows, "numerically_searched_interval_extrema": extrema,
              "extremum_search": {"method": "SciPy SHGO over log(-alpha), 32 initial points, 2 iterations",
                                  "evaluated_coefficients": len(evaluated), "interpretation": "Numerical interval extrema; not an analytic global bound or an exact finite-sample confidence band."}}
    save(directory, "luv-structural-news.json", result)
    return result


def company_news(facts, old, updated):
    forecast_changes = [{"path": "/forecasts", "value": updated["forecasts"]},
                        {"path": "/assumptions", "value": updated["assumptions"]}]
    statements = [{"path": "/"+key, "value": updated[key]} for key in ("balance", "diluted_shares", "invested_capital_begin")]
    events = [
        {"id": "LUV-2025Q3-release", "announcement_id": "SEC:92380:0000092380-25-000138", "revision": 0,
         "source_url": SOURCES["q3"][1], "published_at": SOURCES["q3"][2],
         "mechanism": "Replace Q2 TTM physical observations by Q3 observations, increase disclosed capacity plan, and apply finite Q4 cash-fuel guidance under the supplied schedule/marginal-exposure condition.", "changes": forecast_changes},
        {"id": "LUV-2025Q3-10Q", "announcement_id": "SEC:92380:0000092380-25-000140", "revision": 0,
         "source_url": SOURCES["q3_10q"][1], "published_at": SOURCES["q3_10q"][2],
         "mechanism": "Replace cash, reported debt, book capital and cover-date shares/RSU dilution proxy once; repurchase cash is already included in the balance sheet.", "changes": statements},
    ]
    return {"base": old, "as_of": "2025-10-31", "events": events}


def investor_comparison(inputs, facts, *, owned):
    model = copy.deepcopy(inputs)
    result = equity.value(model)
    snapshot = facts["snapshots"]["q3"]
    dividend = facts["guidance"]["declared_quarterly_dividend_per_share"]*4
    cash = model["balance"]["cash"]
    cash_path = []
    # Operating investment and gross financing cash interest are separate
    # scenario inputs. The unobserved capitalized-cash component of reported
    # spending is addressed in the reclassification comparison below.
    interest = snapshot["interest_expense"]
    for row in result["calculation"]["forecasts"]:
        cash_interest = cash*facts["treasury_curve"]["1 Yr"]*(1-row["tax_rate"])
        cash += row["fcff"] - interest*(1-row["tax_rate"]) + cash_interest - dividend*model["diluted_shares"]
        cash_path.append(cash)
    if min(cash_path) < 0:
        raise ValueError("investor scenario requires financing beyond its supplied cash; specify that financing first")
    model["holding"] = {"distributions": [dividend, dividend], "exit_basis": "model_terminal",
                        "terminal_balance": {**model["balance"], "cash": cash},
                        "terminal_diluted_shares": model["diluted_shares"]}
    model["decision"] = {"held_shares": 100 if owned else 0, "tax_basis_per_share": model["current_price"],
                         "cash_budget": 0 if owned else 100*model["current_price"], "max_position_shares": 100, "lot_size": 1,
                         "taxes": {"dividend_rate": 0, "capital_gain_rate": 0, "capital_loss_credit_rate": 0,
                                   "deduct_selling_costs": False, "capitalize_buying_costs": False},
                         "fees": {"buy_rate": 0, "sell_rate": 0, "buy_fixed": 0, "sell_fixed": 0},
                         "alternative": {"currency": "USD", "horizon_years": 2,
                                         "annual_after_tax_return": facts["treasury_curve"]["2 Yr"],
                                         "source": {**facts["sources"]["treasury"], "assumption": "Tax-exempt illustrative account; 2-year Treasury par yield as constant opportunity-return proxy, coupons reinvested at that rate."}}}
    result = equity.value(model)
    result["investor_assumptions"] = {"identity": "Illustrative USD tax-exempt account, not the user's supplied tax/fee circumstances.",
                                      "horizon": "Two annual periods; exit market price equals model terminal equity in this convergence scenario.",
                                      "capital_allocation": "Constant debt/shares, no new buybacks; annualized declared dividend and cash interest are explicit continuation assumptions.",
                                      "cash_path_usd_million": cash_path,
                                      "annual_financing_interest_cash_proxy_usd_million": interest}
    return result


def run(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    registry, documents = source_documents(directory)
    facts = extract_facts(directory, registry, documents)
    io = structural_news(directory, facts)
    point = io["rows"][1]
    old = forecast_input(facts, "q2")
    updated = forecast_input(facts, "q3", fuel_news=True)
    updated["assumptions"]["io_fuel_exposure"] = "Default fixed schedule: fuel changes capacity cash cost, with zero ticket marginal-cost shock. A separate medium-run frequency-adjustment scenario uses average fuel intensity as a conditional marginal exposure."
    news_input = company_news(facts, old, updated)
    news = equity.update(news_input)
    current = equity.value(updated)
    if not np.isclose(news["updated"]["fair_price"], current["fair_price"], atol=1e-10):
        raise ArithmeticError("source-event bridge must reproduce the current valuation")
    updated = news["updated"]["inputs"]
    current = equity.value(updated)
    save(directory, "luv-value-input.json", updated)
    save(directory, "luv-value-result.json", current)
    save(directory, "luv-news-input.json", news_input)
    save(directory, "luv-news-result.json", news)
    medium = forecast_input(facts, "q3", fuel_news=True, io_correction=point["strategic_correction_usd"]/1e6)
    medium["assumptions"]["io_fuel_exposure"] = io["distance_calibration"]
    medium_news_input = company_news(facts, old, medium)
    save(directory, "luv-medium-run-news-input.json", medium_news_input)
    save(directory, "luv-medium-run-news-result.json", equity.update(medium_news_input))
    parameter = {"path": "/forecasts/1/segments/0/price", "economic_quantity": "Effective operating revenue per RPM from period two onward, with fixed observed load factor, scheduled capacity and cash costs.",
                 "lower": .10, "upper": .40}
    reverse_input = {"base": updated, "target_price": updated["current_price"], "parameter": parameter}
    reversed_value = equity.reverse(reverse_input)
    save(directory, "luv-reverse-input.json", reverse_input)
    save(directory, "luv-reverse-result.json", reversed_value)
    scenarios = []
    for capex in facts["guidance"]["capex_usd_million"]:
        for operating_cash in (0, facts["snapshots"]["q3"]["cash_like"]):
            scenario = forecast_input(facts, "q3", capex, fuel_news=True)
            scenario["balance"]["operating_cash"] = operating_cash
            result = equity.value(scenario)
            scenarios.append({"initial_capex_usd_million": capex, "required_operating_cash_usd_million": operating_cash,
                              "fair_price_usd": result["fair_price"], "equity_value_usd_million": result["equity_value"]})
    initiative = copy.deepcopy(updated)
    increment = facts["guidance"]["initiative_ebit_targets_usd_million"]["2026"]-facts["guidance"]["initiative_ebit_targets_usd_million"]["2025"]
    initiative["forecasts"][1]["segments"][0]["fixed_cash_cost"] -= increment
    initiative["assumptions"]["initiative"] = "The 2026-minus-2025 management initiative EBIT target difference is used as a conditional 2500m improvement benchmark from period two, persisting into the zero-growth perpetuity. Its amount already embedded in TTM earnings is not separately identified, so this is not a forecast bridge from TTM. Additional capital investment and incremental working capital are zero in this condition. No probability or assertion of achieved target; disclosures do not identify offsetting costs, investment needs or duration."
    initiative_result = equity.value(initiative)
    duration = copy.deepcopy(initiative)
    duration["forecasts"] = duration["forecasts"][:1]
    duration["competitive_advantage"] = {"years": 1, "forecast": copy.deepcopy(initiative["forecasts"][1])}
    duration["terminal"]["nopat"] = current["calculation"]["forecasts"][1]["nopat"]
    duration["assumptions"]["initiative"] = "The full incremental EBIT target lasts for n annual periods after the initial investment period, then terminal NOPAT returns to the stationary operating state. Capacity and book capital are unchanged, capex equals DA and additional working capital is zero during the initiative period."
    upper = 1
    if initiative_result["fair_price"] <= updated["current_price"]:
        raise ValueError("even perpetual full-initiative earnings cannot reach market price under these fixed inputs")
    while equity.value(duration)["fair_price"] < updated["current_price"]:
        upper *= 2
        duration["competitive_advantage"]["years"] = upper
    duration_input = {"base": duration, "target_price": updated["current_price"],
                      "parameter": {"path": "/competitive_advantage/years", "kind": "integer", "lower": 0, "upper": upper,
                                    "economic_quantity": "Number of annual periods of the disclosed full 2500m incremental EBIT target after the initial investment year; then operating profit returns to stationary levels."}}
    duration_result = equity.reverse(duration_input)
    save(directory, "luv-duration-reverse-input.json", duration_input)
    save(directory, "luv-duration-reverse-result.json", duration_result)
    investor = {"stationary_unowned": investor_comparison(updated, facts, owned=False),
                "stationary_owned": investor_comparison(updated, facts, owned=True),
                "full_initiative_unowned": investor_comparison(initiative, facts, owned=False)}
    save(directory, "luv-investor-results.json", investor)
    save(directory, "luv-initiative-scenario-input.json", initiative)
    reclassification = []
    for amount in (0, -facts["snapshots"]["q3"]["capitalized_interest"]):
        reclassified = copy.deepcopy(updated)
        reclassified["forecasts"][0]["segments"][0]["capex"] -= amount
        repriced = equity.value(reclassified)
        decision = investor_comparison(reclassified, facts, owned=False)
        revised_duration_input = copy.deepcopy(duration_input)
        revised_duration_input["base"]["forecasts"][0]["segments"][0]["capex"] -= amount
        reclassification.append({"first_period_capitalized_interest_cash_proxy_usd_million": amount,
                                 "first_period_operating_capex_usd_million": reclassified["forecasts"][0]["segments"][0]["capex"],
                                 "fair_price_usd": repriced["fair_price"],
                                 "minimum_initiative_years": equity.reverse(revised_duration_input)["implied_value"],
                                 "financing_interest_cash_proxy_usd_million": facts["snapshots"]["q3"]["interest_expense"],
                                 "npv_at_100_shares_over_treasury_usd": next(item["npv_over_liquidation_alternative"] for item in decision["decision"]["alternatives"] if item["target_shares"] == 100),
                                 "action_unowned": decision["decision"]["action"]})
    coefficient_values = []
    for label, row in [("lower_endpoint", io["rows"][0]), ("point", io["rows"][1]), ("upper_endpoint", io["rows"][2]),
                       *[("numerical_"+key, row) for key, row in io["numerically_searched_interval_extrema"].items()]]:
        spec = forecast_input(facts, "q3", fuel_news=True, io_correction=row["strategic_correction_usd"]/1e6)
        result = equity.value(spec)
        coefficient_values.append({"evaluation": label, "alpha": row["alpha_per_usd"], "fair_price_usd": result["fair_price"],
                                   "equity_value_usd_million": result["equity_value"],
                                   "action_unowned": investor_comparison(spec, facts, owned=False)["decision"]["action"]})
    # Sequential mechanism attribution is explicit about its chosen order.
    steps, prior = [], equity.value(old)
    physical = forecast_input(facts, "q3")
    for key in ("balance", "diluted_shares", "invested_capital_begin"):
        physical[key] = old[key]
    for name, spec in [("Q3 physical observations and capacity plan", physical),
                       ("Q3 cash/debt/capital/share-count observations", forecast_input(facts, "q3")),
                       ("Q4 fuel guidance, direct cash effect", forecast_input(facts, "q3", fuel_news=True)),
                       ("Fixed-schedule ticket marginal-cost response", updated)]:
        result = equity.value(spec)
        steps.append({"mechanism": name, "equity_value_change_usd_million": result["equity_value"]-prior["equity_value"],
                      "fair_price_change_usd": result["fair_price"]-prior["fair_price"]})
        prior = result
    root = reversed_value["roots"][0]
    reverse_result = root["valuation"]
    base_second = current["calculation"]["forecasts"][1]
    required_second = reverse_result["calculation"]["forecasts"][1]
    alternative_rate = facts["treasury_curve"]["2 Yr"]
    annual_dividend = .18*4
    breakeven_exit = updated["current_price"]*(1+alternative_rate)**2-annual_dividend*(1+alternative_rate)-annual_dividend
    summary = {"case": "LUV 2025-10-31 valuation from revised historical data", "point_in_time_backtest": False,
               "completion": {"primary_financial_extraction": True, "physical_forecast": True, "structural_counterfactual": True,
                              "source_event_valuation": True, "reverse_valuation": True, "investor_cash_flow_comparison": True,
                              "full_company_structural_forecast": False, "unconditional_investment_recommendation": False},
               "currency": "USD", "financial_amount_unit": 1e6, "market_price": updated["current_price"],
               "capital_cost": facts["capital_cost"], "reported_net_cash_usd_million": facts["snapshots"]["q3"]["cash_like"]-facts["snapshots"]["q3"]["debt"],
               "baseline_q2_information_fair_price": news["baseline"]["fair_price"],
               "updated_stationary_fair_price": current["fair_price"], "equity_value_usd_million": current["equity_value"],
               "news_equity_value_change_usd_million": news["equity_value_change"], "news_fair_price_change": news["fair_price_change"],
               "news_original_announcements": [{key: contribution[key] for key in
                                                  ("announcement_id", "source_url", "published_at", "revision", "equity_value_change", "fair_price_change")}
                                                 for contribution in news["contributions"]],
               "mechanism_order_attribution": steps,
               "forecasts": [{key: row.get(key) for key in ("period", "revenue", "ebit", "nopat", "depreciation", "capex", "fcff", "invested_capital_begin", "invested_capital_end", "roic", "economic_profit", "incremental_return")} for row in current["calculation"]["forecasts"]],
               "boundary_scenarios": scenarios, "full_management_increment_scenario_fair_price": initiative_result["fair_price"],
               "capitalized_interest_reclassification_conditions": reclassification,
               "reverse_requirements": {"required_effective_revenue_per_rpm": root["implied_value"],
                                        "current_effective_revenue_per_rpm": updated["forecasts"][1]["segments"][0]["price"],
                                        "required_second_period_ebit": required_second["ebit"],
                                        "incremental_ebit_required": required_second["ebit"]-base_second["ebit"],
                                        "required_ebit_margin": required_second["ebit"]/required_second["revenue"],
                                        "required_nopat_roic_on_book_capital": required_second["roic"],
                                        "fraction_of_disclosed_2500m_increment": (required_second["ebit"]-base_second["ebit"])/increment,
                                        "price_root_residual": root["price_error"]},
               "initiative_duration_reverse": {"minimum_years_after_initial_period": duration_result["implied_value"],
                                                "value_by_years": duration_result["evaluations"],
                                                "terminal_nopat_after_advantage_usd_million": duration["terminal"]["nopat"],
                                                "numerical_search_upper_years": upper,
                                                "search_condition": "Upper bound doubled until the target price is bracketed; it is not a modeled maximum life of competitive advantage.",
                                                "economic_condition": duration["assumptions"]["initiative"]},
               "io_interval_sensitivity": coefficient_values,
               "io_fixed_schedule": io["fixed_schedule"],
               "io_medium_run_condition": io["distance_calibration"],
               "io_support": {key: io[key] for key in ("baseline_interval_valid_market_count", "news_excluded_markets", "adopted_market_ids", "rows", "extremum_search")},
               "investor_decisions": {key: {"action": value["decision"]["action"], "target_shares": value["decision"]["target_shares"],
                                             "irr": value["investment_return"]["annualized_irr"], "exit_price": value["investment_return"]["exit_price"],
                                             "incremental_npv_usd": value["decision"]["incremental_npv"],
                                             "npv_at_100_shares_over_treasury_usd": next(item["npv_over_liquidation_alternative"] for item in value["decision"]["alternatives"] if item["target_shares"] == 100)} for key, value in investor.items()},
               "two_year_tax_exempt_break_even_exit_price": breakeven_exit,
               "additional_100m_first_period_working_capital_price_effect": -100/(1+updated["discount_rate"])/updated["diluted_shares"],
               "decision_conclusion": "The supplied stationary and full-initiative conditional scenarios imply different actions. The observed subset IO interval cannot establish the unobserved corporate improvement, maintenance investment or required operating cash. The output is a quantified decision threshold, not an identified unconditional buy/sell recommendation.",
               "initiative_condition": initiative["assumptions"]["initiative"],
               "assumptions": updated["assumptions"], "sources": registry,
               "computational_contract": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                          for name in ("equity.py", "equity_io.py", "equity_company_case.py")},
               "io_input_hashes": {name: hashlib.sha256((directory/name).read_bytes()).hexdigest()
                                   for name in ("airline-case-summary.json", "airline-baseline-2025q2-ar_interval-valid.csv")}}
    save(directory, "luv-case-summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.directory)
    print(json.dumps({key: result[key] for key in ("case", "market_price", "updated_stationary_fair_price", "news_fair_price_change", "reverse_requirements", "investor_decisions")}, ensure_ascii=False, indent=2))
