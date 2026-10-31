"""Financial identities, news attribution, and the public PyBLP execution path."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).parents[1] / "skills/econ-data/scripts/equity.py"
sys.path.insert(0, str(SCRIPT.parent))
try:
    import numpy as np
    SPEC = importlib.util.spec_from_file_location("equity", SCRIPT)
    equity = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(equity)
except ModuleNotFoundError:
    equity = None


def business():
    # An artificial company: steady NOPAT 100, no growth and no net investment.
    return {
        "method": "fcff", "currency": "JPY", "market": "JP", "as_of": "2026-10-31",
        "sources": [{"kind": "synthetic", "description": "Steady NOPAT 100 and explicit balance-sheet claims"}],
        "price_as_of": "2026-10-30", "amount_unit": 1_000_000,
        "share_unit": 1_000_000, "diluted_shares": 10, "current_price": 80,
        "discount_rate": .1,
        "balance": {"cash": 150, "operating_cash": 50, "debt": 30,
                    "nonoperating_assets": 20, "minority_interest": 10,
                    "lease_liabilities": 5, "pension_deficit": 5},
        "forecasts": [{"ebit": 125, "tax_rate": .2, "depreciation": 20,
                       "capex": 20, "change_working_capital": 0}],
        "terminal": {"growth": 0, "roic": .15},
        "holding": {"distributions": [8], "exit_price": 88},
    }


@unittest.skipIf(equity is None, "install requirements-equity.txt for the valuation execution contract")
class EquityTests(unittest.TestCase):
    def test_steady_value_bridge_units_and_holding(self):
        result = equity.value(business())
        self.assertAlmostEqual(result["calculation"]["value"], 1000)
        self.assertAlmostEqual(result["equity_value"], 1070)
        self.assertAlmostEqual(result["fair_price"], 107)
        self.assertAlmostEqual(result["investment_return"]["annualized_irr"], .2)
        changed_units = business()
        changed_units["share_unit"] = 1
        changed_units["diluted_shares"] = 10_000_000
        self.assertAlmostEqual(equity.value(changed_units)["fair_price"], 107)
        terminal = business()
        terminal["holding"] = {"distributions": [10], "exit_basis": "model_terminal",
                               "terminal_balance": terminal["balance"], "terminal_diluted_shares": 10}
        self.assertAlmostEqual(equity.value(terminal)["investment_return"]["exit_price"], 107)

    def test_reinvestment_and_clean_surplus(self):
        spec = business()
        spec["terminal"] = {"growth": .03, "roic": .15}
        result = equity.value(spec)["calculation"]
        self.assertAlmostEqual(result["terminal_reinvestment"], 20.6)
        self.assertAlmostEqual(result["terminal_fcff"], 82.4)
        bank = {**business(), "method": "residual_income", "book_equity": 1000,
                "cost_of_equity": .1,
                "forecasts": [{"comprehensive_income": 100, "net_distributions": 100}],
                "terminal": {"growth": 0, "roe": .1}}
        # ROE equals the required equity return, so market value equals book.
        self.assertAlmostEqual(equity.value(bank)["equity_value"], 1000)

    def test_news_changes_telescope_through_real_cli(self):
        event = {"id": "earnings", "source_url": "https://example.org/artificial-earnings",
                 "published_at": "2026-10-31T00:00:00Z", "mechanism": "人工例：利益見通しを更新",
                 "changes": [{"path": "/forecasts/0/ebit", "value": 150}]}
        rate = {"id": "rate", "source_url": "https://example.org/artificial-rate",
                "published_at": "2026-10-31T01:00:00Z", "mechanism": "人工例：資本費用を更新",
                "changes": [{"path": "/discount_rate", "value": .12}]}
        completed = subprocess.run([sys.executable, str(SCRIPT), "update"],
                                   input=json.dumps({"base": business(), "events": [event, rate]}),
                                   text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertAlmostEqual(sum(x["fair_price_change"] for x in result["contributions"]),
                               result["fair_price_change"])
        self.assertAlmostEqual(result["updated"]["calculation"]["value"], 1000)
        interest = {**rate, "announcement_id": "official-rate", "revision": 0, "changes": [],
                    "rate_change": {"old": .1, "new": .12, "channels": [
                        {"path": "/discount_rate", "role": "opportunity_cost", "response": "linear", "loading": 1}]}}
        corrected = json.loads(json.dumps(interest))
        corrected.update(id="rate-correction", revision=1, supersedes=interest["id"])
        corrected["rate_change"]["new"] = .11
        updated = equity.update({"base": business(), "events": [interest, corrected]})
        self.assertAlmostEqual(updated["updated"]["inputs"]["discount_rate"], .11)
        duplicate = {**interest, "id": "rate-republication"}
        with self.assertRaisesRegex(ValueError, "already included"):
            equity.update({"base": updated["updated"], "events": [duplicate]})
        later = {**rate, "id": "later-rate-outlook", "announcement_id": "other-outlook"}
        with self.assertRaisesRegex(ValueError, "replay"):
            equity.update({"base": business(), "events": [interest, later, corrected]})

    def test_auto_selects_the_candidate_with_complete_identifying_inputs(self):
        import pandas as pd
        data = pd.DataFrame({"market_ids": [1, 1, 2, 2], "prices": [1, 2, 2, 4],
                             "shares": [.1, .2, .2, .1], "demand_instruments0": [1, 0, 2, 0]})
        candidates = [
            {"name": "heterogeneous", "demand": {"linear": "1+prices", "nonlinear": "0+prices"},
             "solve": {"sigma": [[1]]}, "integration": {"method": "product", "size": 5},
             "identification": "人工例の追加モーメント", "requires": {"agent_fields": ["income"], "instrument_rank": 1}},
            {"name": "aggregate", "demand": {"linear": "1+prices"},
             "identification": "人工例の除外操作変数", "requires": {"instrument_rank": 1}},
        ]
        _, selection = equity.select_model({"candidates": candidates}, data, None)
        self.assertEqual(selection["selected"], "aggregate")
        _, selection = equity.select_model({"candidates": candidates}, data, pd.DataFrame({"income": [1]}))
        self.assertEqual(selection["selected"], "aggregate")
        candidates[0]["identification"] = {"parameters": [
            {"name": name, "role": role, "moments": ["demand_instruments0"],
             "variation": "synthetic market shifts", "exclusion": "zero structural error",
             "source": "synthetic selection fixture"}
            for name, role in [("price", "price"), ("price dispersion", "heterogeneity")]]}
        _, selection = equity.select_model({"candidates": candidates}, data, pd.DataFrame({"income": [1]}))
        self.assertEqual(selection["selected"], "heterogeneous")

    def test_physical_forecasts_capital_and_market_implied_primitives(self):
        model = business()
        model.update(invested_capital_begin=1000, prior_nopat=300, incremental_roic_lag=0)
        segment = {"name": "synthetic plant", "capacity": 200, "utilization": .5,
                   "quantity_unit": "unit", "price": 10, "unit_variable_cost": 4,
                   "price_unit": 1_000_000, "fixed_cash_cost": 100, "depreciation": 20,
                   "maintenance_capex": 20, "growth_capex": 30, "change_working_capital": 10,
                   "sources": model["sources"]}
        model["forecasts"] = [{"segments": [segment], "ebit": 999, "capex": 999, "tax_rate": .25}]
        row = equity.value(model)["calculation"]["forecasts"][0]
        self.assertEqual(row["revenue"], 1000)
        self.assertEqual(row["ebit"], 480)
        self.assertEqual(row["fcff"], 320)
        self.assertEqual(row["invested_capital_end"], 1040)
        self.assertEqual(row["economic_profit"], 260)
        self.assertEqual(row["incremental_return"]["incremental_roic"], 1.5)
        total_only = json.loads(json.dumps(model))
        total_segment = total_only["forecasts"][0]["segments"][0]
        total_segment["capex"] = total_segment.pop("maintenance_capex") + total_segment.pop("growth_capex")
        total_only["forecasts"][0].update(corporate_maintenance_capex=3, corporate_growth_capex=4)
        mixed = equity.value(total_only)["calculation"]["forecasts"][0]
        self.assertEqual(mixed["capex"], 57)
        self.assertEqual(mixed["fcff"], 313)
        self.assertEqual(mixed["capex_split"], "not_fully_identified")
        total_only = json.loads(json.dumps(model))
        total_only["forecasts"][0]["corporate_capex"] = 7
        mixed = equity.value(total_only)["calculation"]["forecasts"][0]
        self.assertEqual(mixed["capex"], 57)
        self.assertEqual(mixed["fcff"], 313)
        self.assertEqual(mixed["capex_split"], "not_fully_identified")
        for path, expected, lower, upper in [
                ("/forecasts/0/segments/0/price", 12, 8, 14),
                ("/forecasts/0/revenue", 1200, 800, 1400),
                ("/forecasts/0/ebit_margin", .15, .08, .2),
                ("/terminal/roic", .2, .1, .3)]:
            inputs = model if "segments" in path else business()
            inputs = json.loads(json.dumps(inputs))
            if "segments" not in path:
                inputs["forecasts"][0].pop("ebit")
                inputs["forecasts"][0].update(revenue=1000, ebit_margin=.125)
                inputs["terminal"]["growth"] = .03
            target = json.loads(json.dumps(inputs))
            equity._change_input(target, path, expected)
            request = {"base": inputs, "target_price": equity.value(target)["fair_price"],
                       "parameter": {"path": path, "lower": lower, "upper": upper,
                                     "economic_quantity": "synthetic market-implied primitive"}}
            if "segments" in path:
                completed = subprocess.run([sys.executable, str(SCRIPT), "reverse"],
                    input=json.dumps(request), text=True, capture_output=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                solved = json.loads(completed.stdout)["roots"][0]
            else:
                solved = equity.reverse(request)["roots"][0]
            self.assertAlmostEqual(solved["implied_value"], expected, places=7)
            self.assertAlmostEqual(solved["price_error"], 0, places=7)
        duration = business()
        duration.update(invested_capital_begin=1000)
        duration["forecasts"][0]["ebit"] = 250
        duration["competitive_advantage"] = {"years": 0, "forecast": duration["forecasts"][0]}
        duration["terminal"] = {"growth": .02, "competitive": True}
        target = json.loads(json.dumps(duration))
        target["competitive_advantage"]["years"] = 3
        expected = 1000 + sum(100/1.1**t for t in range(1, 5))
        self.assertAlmostEqual(equity.value(target)["calculation"]["value"], expected)
        solved = equity.reverse({"base": duration, "target_price": equity.value(target)["fair_price"],
                                 "parameter": {"path": "/competitive_advantage/years", "kind": "integer",
                                               "lower": 0, "upper": 6, "economic_quantity": "excess-profit duration"}})
        self.assertEqual(solved["implied_value"], 3)

    def test_investor_taxes_fees_budget_and_tax_deferral(self):
        model = business()
        model["current_price"] = 100
        model["holding"] = {"distributions": [10], "exit_price": 120}
        model["decision"] = {"held_shares": 2, "tax_basis_per_share": 50, "cash_budget": 200,
            "lot_size": 1, "max_position_shares": 4,
            "taxes": {"dividend_rate": .2, "capital_gain_rate": .2, "capital_loss_credit_rate": 0,
                      "deduct_selling_costs": True, "capitalize_buying_costs": True},
            "fees": {"buy_rate": 0, "sell_rate": 0, "buy_fixed": 2, "sell_fixed": 2},
            "alternative": {"currency": "JPY", "horizon_years": 1, "annual_after_tax_return": .1,
                            "user_preference": "synthetic opportunity return"}}
        decision = equity.value(model)["decision"]
        self.assertEqual(decision["action"], "buy")
        self.assertEqual(decision["target_shares"], 3)
        self.assertAlmostEqual(decision["full_liquidation_present_wealth"], 378.4)
        self.assertAlmostEqual(decision["incremental_npv"], 98 + 350.8/1.1 - 378.4)
        model["holding"] = {"distributions": [0], "exit_price": 104.5}
        terms = model["decision"]
        terms.update(held_shares=1, tax_basis_per_share=0, cash_budget=100, max_position_shares=1)
        terms["fees"].update(buy_fixed=0, sell_fixed=0)
        terms["alternative"]["annual_after_tax_return"] = .04
        self.assertEqual(equity.value(model)["decision"]["action"], "hold")
        terms["held_shares"] = 0
        self.assertEqual(equity.value(model)["decision"]["action"], "do_not_buy")
        terms["held_shares"] = 1
        model["holding"]["exit_price"] = 80
        self.assertEqual(equity.value(model)["decision"]["action"], "sell")

    def test_pyblp_recovers_demand_and_resolves_multi_product_ownership(self):
        try:
            import pyblp
        except ImportError:
            self.skipTest("install requirements-equity.txt for the structural execution contract")
        pyblp.options.verbose = False
        products = []
        for market in range(10):
            prices = np.array([1.0, 1.2, 1.4]) + .01 * market * np.array([1, 2, 3])
            quality = np.array([.3, .6, .9]) + .02 * (market % 3)
            utility = 1 + 2 * quality - 3 * prices
            shares = np.exp(utility) / (1 + np.exp(utility).sum())
            for product in range(3):
                products.append({"market_ids": market, "product_ids": product,
                                 "firm_ids": product, "prices": prices[product], "quality": quality[product],
                                 "shares": shares[product], "market_size": 1000,
                                 "demand_instruments0": prices[product] + .1 * quality[product]})
        spec = {"products": products, "currency": "JPY", "market": "artificial",
                "as_of": "2026-10-31", "price_unit": 1, "quantity_unit": "unit",
                "sources": [{"kind": "synthetic", "description": "Utility 1 + 2*quality - 3*price with zero structural errors"}],
                "identification": "人工例：効用誤差ゼロ、価格と除外操作変数の対応を指定",
                "demand": {"linear": "1 + prices + quality"},
                "counterfactual": {"costs": [.5] * len(products),
                                   "product_changes": {"firm_ids": [0, 0, 2] * 10}, "utility_shift": .1}}
        with contextlib.redirect_stdout(io.StringIO()):
            result = equity.fit(spec)
        np.testing.assert_allclose(np.ravel(result["coefficients"]["beta"]), [1, -3, 2], atol=1e-7)
        cf = result["counterfactual"]["products"]
        # Multi-product Bertrand first-order condition for product 0:
        # s0 + sum_{j in same firm} (pj-cj) * dsj/dp0 = 0.
        for start in range(0, len(cf), 3):
            a, b, _ = cf[start:start + 3]
            score = a["share"] - 3 * (a["price"] - .5) * a["share"] * (1 - a["share"])
            score += 3 * (b["price"] - .5) * b["share"] * a["share"]
            self.assertAlmostEqual(score, 0, places=9)
            self.assertAlmostEqual(a["gross_profit"], (a["price"] - .5) * a["quantity"])


@unittest.skipUnless(importlib.util.find_spec("edinet_tools"),
                     "install requirements-equity.txt for the filing execution contract")
class EquitySourceTests(unittest.TestCase):
    def test_xbrl_cli_preserves_segments_units_periods_and_filing(self):
        from tempfile import TemporaryDirectory

        # Artificial standard XBRL: consolidated revenue and one segment use
        # different contexts; decimals describes precision, not a multiplier.
        instance = b'''<?xml version="1.0"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance"
 xmlns:us-gaap="http://fasb.org/us-gaap/2025"
 xmlns:firm="http://example.org/2025" xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi">
 <context id="total"><entity><identifier scheme="http://www.sec.gov/CIK">0000123456</identifier></entity>
  <period><startDate>2025-01-01</startDate><endDate>2025-12-31</endDate></period></context>
 <context id="segment"><entity><identifier scheme="http://www.sec.gov/CIK">0000123456</identifier>
  <segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">firm:JapanMember</xbrldi:explicitMember></segment></entity>
  <period><startDate>2025-01-01</startDate><endDate>2025-12-31</endDate></period></context>
 <unit id="usd"><measure>iso4217:USD</measure></unit>
 <us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax contextRef="total" unitRef="usd" decimals="-6">900000000</us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax>
 <us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax contextRef="segment" unitRef="usd" decimals="-6">250000000</us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax>
</xbrl>'''
        source_script = SCRIPT.with_name("equity_sources.py")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "instance.xml").write_bytes(instance)
            (root / "filing.json").write_text(json.dumps({
                "accessionNumber": "0000123456-26-000001", "filingDate": "2026-02-01", "form": "10-K"}))
            completed = subprocess.run([
                sys.executable, str(source_script), "xbrl", str(root / "instance.xml"),
                "--url", "https://example.org/firm-20251231_htm.xml",
                "--metadata", str(root / "filing.json")], text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["entity_ids"], ["0000123456"])
        total, segment = result["records"]
        self.assertEqual(total["dimensions"], {})
        self.assertEqual(segment["dimensions"], {"us-gaap:StatementBusinessSegmentsAxis": "firm:JapanMember"})
        self.assertEqual(segment["value"], 250000000)
        self.assertEqual(segment["unit"], "USD")
        self.assertEqual(segment["start"], "2025-01-01")
        self.assertEqual(segment["end"], "2025-12-31")
        self.assertEqual(segment["accession"], "0000123456-26-000001")
        self.assertEqual(segment["filed"], "2026-02-01")
        spec = importlib.util.spec_from_file_location("equity_sources", source_script)
        sources = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sources)
        where = {"concept": segment["concept"], "unit": "USD", "end": "2025-12-31"}
        with self.assertRaisesRegex(ValueError, "distinct accounting facts"):
            sources.select_facts(result, {"revenue": {"where": where}})
        selected = sources.select_facts(result, {"segment_revenue": {
            "where": {**where, "dimensions": segment["dimensions"]},
            "multiplier": .000001, "model_unit": "USD million"}})
        self.assertEqual(selected["segment_revenue"]["value"], 250)


class CredentialSourceTests(unittest.TestCase):
    @staticmethod
    def load_sources():
        spec = importlib.util.spec_from_file_location("equity_sources", SCRIPT.with_name("equity_sources.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_own_credentials_required_and_errors_do_not_expose_keys(self):
        from unittest.mock import patch
        from urllib.error import HTTPError

        sources = self.load_sources()
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "EDINET_API_KEY.*free registration"):
                sources.edinet_list("2025-10-31")
            with self.assertRaisesRegex(ValueError, "ESTAT_APP_ID.*free registration"):
                sources.estat(stats_data_id="example")
        secret = "test-only-key+with/slash"
        error = HTTPError("https://api.e-stat.go.jp/?appId=" + secret, 403, secret, {}, None)
        with patch.dict("os.environ", {"ESTAT_APP_ID": secret}), \
             patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "HTTP 403") as raised:
                sources.estat(stats_data_id="example")
            self.assertNotIn(secret, str(raised.exception))
            self.assertNotIn("appId", str(raised.exception))
        with patch.dict("os.environ", {"EDINET_API_KEY": secret}):
            with self.assertRaisesRegex(RuntimeError, "HTTP 403") as raised:
                sources._edinet_request(lambda **kwargs: (_ for _ in ()).throw(error))
            self.assertNotIn(secret, str(raised.exception))

    def test_estat_pages_preserve_units_suppression_and_redact_echoed_key(self):
        import io
        from decimal import Decimal
        from unittest.mock import patch
        from urllib.parse import parse_qs, urlsplit

        sources = self.load_sources()
        secret = "test-only-estat-key"
        pages = [
            {"GET_STATS_DATA": {"RESULT": {"STATUS": 0}, "PARAMETER": {"APP_ID": secret},
                "STATISTICAL_DATA": {"TABLE_INF": {"@id": "example"}, "CLASS_INF": {"test": "labels"},
                    "RESULT_INF": {"NEXT_KEY": 2}, "DATA_INF": {"VALUE":
                        [{"$": "1,234.50", "@unit": "百万円", "@time": "2025000000"}]}}}},
            {"GET_STATS_DATA": {"RESULT": {"STATUS": 0},
                "STATISTICAL_DATA": {"RESULT_INF": {}, "DATA_INF": {"VALUE":
                    {"$": "***", "@unit": "百万円", "@time": "2024000000"}}}}},
        ]
        seen = []
        def fetch(url, **kwargs):
            seen.append(parse_qs(urlsplit(url).query))
            return io.BytesIO(json.dumps(pages[len(seen) - 1]).encode())
        with patch.dict("os.environ", {"ESTAT_APP_ID": secret}), \
             patch("urllib.request.urlopen", side_effect=fetch), patch("time.sleep"):
            result = sources.estat(stats_data_id="example", parameters={"limit": "1"})
        self.assertEqual(seen[1]["startPosition"], ["2"])
        self.assertEqual(seen[0]["appId"], [secret])
        self.assertEqual(result["records"][0]["value"], Decimal("1234.50"))
        self.assertEqual(result["records"][0]["unit"], "百万円")
        self.assertEqual(result["records"][1]["value"], "***")
        self.assertEqual(result["table"], {"@id": "example"})
        self.assertEqual(len(result["acquisition"]), 2)
        self.assertNotIn(secret, json.dumps(result, default=str))
        self.assertTrue(all("appId" not in page["source_url"] for page in result["acquisition"]))

    @unittest.skipUnless(importlib.util.find_spec("pyhdfe"), "install requirements-equity.txt for the case cache contract")
    def test_case_cache_detects_same_row_count_edits_spec_and_code_changes(self):
        import csv
        import zipfile
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        import equity_airline_case as case

        row = {"Year": 2025, "Quarter": 2, "OriginCityMarketID": 100, "DestCityMarketID": 200,
               "OriginState": "NY", "DestState": "CA", "TkCarrier": "WN", "TkCarrierChange": 0,
               "BulkFare": 0, "Passengers": 10, "MktFare": 250, "MktMilesFlown": 2000,
               "NonStopMiles": 1800, "MktCoupons": 1, "MktGeoType": 2}
        with TemporaryDirectory() as directory:
            root = Path(directory)
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
            writer.writerow({**row, "TkCarrier": "AA"})
            archive = root / "market.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("market.csv", buffer.getvalue())
            source = {"sha256": case.digest(archive)}
            output = case.aggregate(archive, source)
            original_hash = case.digest(output)
            altered = case.pd.read_csv(output)
            altered.loc[0, "fare"] += 1
            altered.to_csv(output, index=False)
            self.assertNotEqual(case.digest(output), original_hash)
            self.assertEqual(len(altered), 2)
            case.aggregate(archive, source)
            self.assertEqual(case.digest(output), original_hash)
            receipt = output.with_suffix(".provenance.json")
            saved = json.loads(receipt.read_text())
            saved["aggregation_contract"]["version"] = 0
            receipt.write_text(json.dumps(saved))
            case.aggregate(archive, source)
            self.assertEqual(json.loads(receipt.read_text())["aggregation_contract"], case.aggregation_contract())
            spec = {"products": str(output), "reference_products": str(output),
                    "sources": [{"path": "original.zip", "sha256": source["sha256"]}],
                    "demand": {"linear": "prices"}, "solve": {"method": "1s"}}
            owner = root / "equity.py"
            owner.write_text("# calculation version one\n")
            owner.with_name("equity_io.py").write_text("# equilibrium version one\n")
            with patch.object(case.equity, "__file__", str(owner)):
                first = case.fit_contract(spec)
                duplicate = root / "same-input-new-location.csv"
                duplicate.write_bytes(output.read_bytes())
                self.assertEqual(case.fit_contract({**spec, "products": str(duplicate)}), first)
                self.assertNotEqual(case.fit_contract({**spec, "solve": {"method": "2s"}}), first)
                self.assertNotEqual(case.fit_contract({**spec, "demand": {"linear": "prices + x"}}), first)
                owner.write_text("# calculation version two\n")
                self.assertNotEqual(case.fit_contract(spec), first)


@unittest.skipIf(equity is None, "install requirements-equity.txt for structural calculations")
class StructuralEquityTests(unittest.TestCase):
    def test_cournot_iv_capacity_and_fcf_connection(self):
        observations = []
        for market in range(12):
            income, cost = np.cos(market), np.sin(market)
            quantity = 10 + cost + .2 * income
            observations.append({"market_ids": market, "quantity": quantity,
                                 "price": 100 + 4*income - 2*quantity,
                                 "income": income, "supply_cost": cost})
        firms = [{"firm_ids": name, "unit_cost": 20, "capacity": 100} for name in ["A", "B"]]
        market = {"market_ids": "annual", "controls": {"income": 0}, "firms": firms}
        spec = {"model": "cournot", "market": "synthetic", "currency": "JPY", "as_of": "2026-10-31",
                "price_unit": 1_000_000, "quantity_unit": "unit", "observations": observations,
                "sources": [{"kind": "synthetic", "description": "P=100+4*income-2*Q; zero demand error"}],
                "identification": {"parameters": [{"name": "inverse demand", "role": "demand",
                    "moments": ["supply_cost"], "variation": "independent cost and income movements",
                    "exclusion": "zero structural demand error", "source": "synthetic equations"}]},
                "inverse_demand": {"controls": ["income"], "instruments": ["supply_cost"]},
                "markets": [market], "counterfactual": {"markets": [{**market, "firms": [
                    {**firms[0], "capacity": 5}, firms[1]]}]}}
        completed = subprocess.run([sys.executable, str(SCRIPT), "fit"], input=json.dumps(spec),
                                   text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        np.testing.assert_allclose([result["coefficients"][k] for k in ["intercept", "quantity", "income"]],
                                   [100, -2, 4], atol=1e-10)
        base = result["baseline"]["market_firms"]
        self.assertAlmostEqual(base[0]["quantity"], 40/3)
        changed = result["counterfactual"]["market_firms"]
        self.assertAlmostEqual(changed[0]["quantity"], 5)
        self.assertAlmostEqual(changed[1]["quantity"], 17.5)
        self.assertAlmostEqual(changed[0]["capacity_shadow_price"], 25_000_000)
        valuation = business()
        valuation["forecasts"] = [{"io": {**result["counterfactual"], "firm_id": "A", "market_ids": ["annual"]},
                                  "ebit": 999, "fixed_cash_cost": 30, "depreciation": 20, "tax_rate": .2,
                                  "capex": 20, "change_working_capital": 0}]
        # Updated IO gross profit replaces stale EBIT: 175 - 30 - 20 gives NOPAT 100.
        self.assertAlmostEqual(equity.value(valuation)["calculation"]["value"], 1000)
        valuation["forecasts"][0].pop("io")
        valuation["forecasts"][0]["io_model"] = {"spec": spec, "outcome": "counterfactual",
                                                 "firm_id": "A", "market_ids": ["annual"]}
        event = {"id": "capacity-release", "announcement_id": "A-official-capacity", "revision": 0,
                 "source_url": "https://example.org/synthetic-capacity", "published_at": "2026-10-31T00:00:00Z",
                 "mechanism": "capacity increase changes both firms' equilibrium quantities",
                 "changes": [{"path": "/forecasts/0/io_model/spec/counterfactual/markets/0/firms/0/capacity", "value": 7}]}
        updated = equity.update({"base": valuation, "events": [event]})
        self.assertAlmostEqual(updated["updated"]["calculation"]["value"], 1448)
        rival = updated["updated"]["calculation"]["forecasts"][0]["io_result"]["counterfactual"]["market_firms"][1]
        self.assertAlmostEqual(rival["quantity"], 16.5)

    def test_conditional_logit_resolves_all_firms_including_reference(self):
        try:
            import pyblp
        except ImportError:
            self.skipTest("install requirements-equity.txt for conditional demand")
        pyblp.options.verbose = False
        products, reference = [], []
        for market in range(12):
            prices = np.array([100, 110, 120, 130]) + market*np.array([.3, .5, .1, .7])
            utility = np.array([0, .2, .5, .8]) - .02*prices
            shares = np.exp(utility) / np.exp(utility).sum()
            rows = [{"market_ids": market, "product_ids": firm, "firm_ids": firm,
                     "prices": prices[i], "shares": shares[i], "market_size": 1000,
                     "reference_price": prices[0], "demand_instruments0": prices[i]-prices[0]}
                    for i, firm in enumerate(["AA", "WN", "DL", "UA"])]
            reference.append(rows[0])
            products.extend({**row, "year": 2026} for row in rows[1:])
        spec = {"model": "conditional_logit", "products": products, "reference_products": reference,
                "demand": {"linear": "0 + C(firm_ids) + I(prices-reference_price)"},
                "currency": "USD", "price_unit": 1, "quantity_unit": "passenger",
                "market": "synthetic conditional airline choice", "as_of": "2026-10-31",
                "identification": "synthetic independent price variation; fixed observed passenger count",
                "sources": [{"kind": "synthetic", "description": "Four-firm logit with alpha=-0.02"}]}
        initial = equity.fit(spec)
        self.assertAlmostEqual(initial["price_coefficient"], -.02, places=8)
        full = initial["baseline"]["products"]
        spec["counterfactual"] = {"costs": [row["unit_cost"] + 10 for row in full]}
        result = equity.fit(spec)
        for base, changed in zip(full, result["counterfactual"]["products"]):
            self.assertAlmostEqual(changed["price"], base["price"]+10, places=7)
            self.assertAlmostEqual(changed["share"], base["share"], places=8)
        self.assertEqual(len(result["counterfactual"]["market_firms"]), 48)
        self.assertLess(max(row["best_response_max_abs_error"] for row in result["counterfactual"]["equilibrium_residuals"]), 1e-8)
        self.assertEqual(initial["cost_support"]["negative_marginal_cost_count"], 0)
        spec["counterfactual"]["costs"] = [-1.] * len(full)
        valuation = business()
        valuation["currency"] = "USD"
        valuation["forecasts"][0].update(fixed_cash_cost=0, io_model={
            "spec": spec, "outcome": "counterfactual", "firm_id": "WN", "market_ids": [0]})
        with self.assertRaisesRegex(ValueError, "selected IO outcome includes negative"):
            equity.value(valuation)
        valuation["forecasts"][0]["io_model"]["negative_cost_interpretation"] = "synthetic subsidy per unit exceeds its production cost"
        self.assertIn("io_result", equity.value(valuation)["calculation"]["forecasts"][0])

    def test_apv_separates_operating_discounting_and_debt_tax_shields(self):
        spec = business()
        spec.update(method="apv", unlevered_cost_of_capital=.1,
                    financing=[{"interest_expense": 10, "tax_rate": .2, "discount_rate": .05}],
                    financing_terminal={"tax_shield": 2, "growth": 0, "discount_rate": .05})
        result = equity.value(spec)
        self.assertAlmostEqual(result["calculation"]["unlevered_operating_value"], 1000)
        self.assertAlmostEqual(result["calculation"]["present_value_financing"], 40)
        self.assertAlmostEqual(result["fair_price"], 111)
        spec["competitive_advantage"] = {"years": 1, "forecast": {**spec["forecasts"][0], "discount_rate": .01}}
        spec["financing"] *= 2
        self.assertAlmostEqual(equity.value(spec)["calculation"]["unlevered_operating_value"], 1000)
        spec.pop("competitive_advantage")
        spec["financing"] = spec["financing"][:1]
        spec["financing_terminal"] = {"value": 0}
        self.assertAlmostEqual(equity.value(spec)["calculation"]["value"], 1000 + 2/1.05)

    def test_dynamic_estimation_joint_responses_and_cashflow_value(self):
        profiles, observations = [], []
        for a, b, count in [(0, 0, 4), (1, 0, 12), (0, 1, 12), (1, 1, 36)]:
            profiles.append({"state": "live", "actions": [a, b], "payoffs": [a*(2-b), b*(2-a)],
                             "payoff_features": {"entry_cost": [-a, -b]}})
            for _ in range(count):
                observations.append({"market_id": "panel", "period": len(observations),
                                     "state": "live", "actions": [a, b], "next_state": "live"})
        game = {"firms": ["A", "B"], "states": ["live"], "profiles": profiles,
                "observations": observations, "discount_factor": .9, "shock_scale": 1,
                "flow_timing": "current", "action_timing": "entry affects this period's cash flow",
                "flow_definition": "unlevered_after_tax_cash_flow_excluding_financial_assets",
                "shock_role": "choice_only", "parameters": [{"name": "entry_cost", "initial": .1, "bounds": [-2, 2]}],
                "currency": "JPY", "amount_unit": 1_000_000, "market": "synthetic", "as_of": "2026-10-31",
                "sources": [{"kind": "synthetic", "description": "Two firms; observed entry share 3/4 each"}],
                "identification": {"parameters": [{"name": "entry_cost", "role": "entry_cost",
                    "moments": ["entry frequencies"], "variation": "observed entry and abstention",
                    "exclusion": "known baseline action payoff, discount and action-shock scale",
                    "source": "synthetic payoff table"}]}}
        result = equity.dynamic(game)
        expected = 1.25 - np.log(3)
        self.assertAlmostEqual(result["estimation"]["parameters"]["entry_cost"], expected, places=5)
        for policy in result["baseline"]["policies"]:
            self.assertAlmostEqual(policy["choice_share"], .75 if policy["action"] else .25, places=5)
        for row in result["baseline"]["state_values"]:
            self.assertAlmostEqual(row["value"], np.log(4)/.1, places=5)
            self.assertAlmostEqual(row["cash_flow_value"], .75*np.log(3)/.1, places=5)
        valuation = business()
        valuation.pop("holding")
        valuation.update(method="dynamic_game", game=game, target_firm="A", initial_state="live")
        self.assertAlmostEqual(equity.value(valuation)["equity_value"], .75*np.log(3)/.1 + 70, places=5)
        news = {"id": "cash-margin", "source_url": "https://example.org/artificial-margin",
                "published_at": "2026-10-31", "mechanism": "A's operating cash flow changes by one",
                "changes": [{"path": "/game/profiles/1/payoffs/0", "value": 3}]}
        updated = equity.update({"base": valuation, "events": [news]})["updated"]
        self.assertAlmostEqual(updated["inputs"]["game"]["parameters"][0]["value"], expected, places=5)
        self.assertIsNone(updated["calculation"]["game"]["estimation"])
        group = {**business(), "method": "sotp", "components": [{"name": "business A", "model": valuation}]}
        group.pop("holding")
        group_news = {**news, "changes": [{"path": "/components/0/model/game/profiles/1/payoffs/0", "value": 3}]}
        group_result = equity.update({"base": group, "events": [group_news]})["updated"]
        self.assertIsNone(group_result["calculation"]["components"][0]["game"]["estimation"])
        self.assertAlmostEqual(group_result["equity_value"], updated["equity_value"], places=6)
        # Raise A's payoff from acting; B's equilibrium action share must respond.
        changed = json.loads(json.dumps(profiles))
        for row in changed:
            row["payoffs"][0] += row["actions"][0]
        game["counterfactual"] = {"profiles": changed}
        cf = equity.dynamic(game)["counterfactual"]["policies"]
        p = {row["firm_ids"]: row["choice_share"] for row in cf if row["action"] == 1}
        self.assertGreater(p["A"], .75)
        self.assertLess(p["B"], .75)
        self.assertAlmostEqual(np.log(p["A"]/(1-p["A"])), 3-p["B"]-expected, places=5)
        self.assertAlmostEqual(np.log(p["B"]/(1-p["B"])), 2-p["A"]-expected, places=5)

    def test_dynamic_cash_flows_follow_joint_state_transitions(self):
        game = {"firms": ["A"], "states": ["low", "high"], "discount_factor": .9, "shock_scale": 1,
                "flow_timing": "current", "action_timing": "one-period deterministic transition",
                "flow_definition": "unlevered_after_tax_cash_flow_excluding_financial_assets",
                "shock_role": "choice_only", "currency": "JPY", "amount_unit": 1,
                "market": "synthetic", "as_of": "2026-10-31",
                "sources": [{"kind": "synthetic", "description": "Alternating cash flows 1 and 2"}],
                "identification": {"parameters": [{"name": "transition", "role": "transition",
                    "moments": ["state transitions"], "variation": "deterministic two-state cycle",
                    "exclusion": "cash flows and transition matrix specified", "source": "synthetic cycle"}]},
                "profiles": [{"state": "low", "actions": ["wait"], "payoffs": [1], "transitions": {"high": 1}},
                             {"state": "high", "actions": ["wait"], "payoffs": [2], "transitions": {"low": 1}}]}
        result = equity.dynamic(game)["baseline"]
        self.assertAlmostEqual(result["state_values"][0]["cash_flow_value"], (1+.9*2)/(1-.9**2))
        self.assertAlmostEqual(result["state_values"][1]["cash_flow_value"], (2+.9*1)/(1-.9**2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
