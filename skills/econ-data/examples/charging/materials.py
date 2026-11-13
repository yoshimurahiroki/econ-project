#!/usr/bin/env python3
"""Build bilingual charging-market materials from an executed result index."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

FLAT = (Path(__file__).resolve().parent / "RESOURCES.json").is_file()
RUNTIME = Path(__file__).resolve().parent if FLAT else Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RUNTIME if FLAT else RUNTIME / "harness"))
sys.path.insert(0, str(RUNTIME if FLAT else RUNTIME / "skills/econ-design/scripts"))
import research_artifacts as artifacts
import research_design as design
import research_meetings as meetings


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def reference(root, path):
    path = path.resolve(strict=True)
    return {"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def checked_reference(root, ref):
    path = (root / ref["path"]).resolve(strict=True)
    if reference(root, path)["sha256"] != ref["sha256"]:
        raise ValueError("Saved input changed: " + ref["path"])
    return path


def prose(index, spec, language):
    p = spec["parameters"]
    changes = index["decision_quantities"]["changes_from_baseline"]
    coefficient = index["uncertainty"]["coefficients"]["prices"]
    def money(scenario, quantity):
        return f"{changes[scenario][quantity] / 10000:,.1f}".replace("-", "−")
    cost = p["integration_cost_per_potential_occasion"] * index["decision_quantities"]["population"] / 10000
    reduction = p["merged_cost_reduction"] * 100
    estimate, lo, hi = (f"{coefficient[key]:.3f}" for key in ("estimate", "lower", "upper"))
    if language == "ja":
        return {
            "title": "充電サービスの企業結合と余剰の配分",
            "question": "充電事業者の結合は、共同価格設定と調達費用を通じて利用者と企業の余剰を変える。競争当局は、統合費用を含む1週間の総余剰から承認を選ぶ。",
            "model": "利用者は3つの充電サービスまたは外部選択肢を選ぶ。企業は自社サービスの利益を最大にする価格を選ぶ。共同所有により、両サービス間の代替が結合企業の価格設定へ入る。",
            "identification": "調達価格の変動が限界費用と均衡価格を動かす。この変動から、品質と定数項を含むロジット需要式の価格係数を推定する。",
            "data": f"架空経済の{p['markets']}市場に各{p['products_per_market']}サービスを配置する。1市場あたり{p['occasions_per_market']:,}回、計{index['decision_quantities']['population']:,}回の潜在的な10-kWh充電機会を1週間について評価する。",
            "parameters": f"価格係数は100円あたり{estimate}正規化効用単位、95%信頼区間は[{lo}, {hi}]である。価格と品質に対する利用者の選択が、共同価格設定の需要を決める。",
            "counterfactual": f"結合前の費用による共同価格設定の総余剰変化は{money('ownership-only', 'social_welfare')}百万円である。統合では、結合する2サービスの限界費用を{reduction:g}%削減し、{cost:g}百万円の実物資源を使う。",
            "welfare": f"統合の消費者余剰変化は{money('integrated', 'consumer_surplus')}百万円、生産者余剰変化は{money('integrated', 'producer_surplus')}百万円となる。統合費用を含む総余剰変化は{money('integrated', 'social_welfare')}百万円である。",
            "interpretation": "共同価格設定と調達費用の削減が、利用者と企業の間の余剰配分を決める。同じ人口と期間の余剰を合計することで、価格への反応と資源費用が判断基準へ結び付く。",
            "decisions": "総余剰に基づく判断は企業結合の承認を選ぶ。" if index["selected_action"] == "approve" else "総余剰に基づく判断は結合前の所有を選ぶ。",
        }
    return {
        "title": "Charging-Service Mergers and the Allocation of Surplus",
        "question": "A charging-service merger changes consumer and producer surplus through joint pricing and procurement costs. The authority chooses approval by total surplus over one operating week, including the real integration cost.",
        "model": "Drivers choose one of three charging services or the outside option. Firms choose prices to maximize profit on their services. Joint ownership brings substitution between the merging services into the same pricing objective.",
        "identification": "Procurement-price variation moves marginal costs and equilibrium prices. We use this variation to estimate the price coefficient in logit demand with quality and an intercept.",
        "data": f"The fictional economy contains {p['markets']} markets with {p['products_per_market']} services each. We evaluate {p['occasions_per_market']:,} potential 10-kWh charging occasions per market, totaling {index['decision_quantities']['population']:,} over one operating week.",
        "parameters": f"The price coefficient is {estimate} normalized utility units per hundred JPY; its 95% confidence interval is [{lo}, {hi}]. Drivers' responses to prices and quality determine the demand facing joint pricing.",
        "counterfactual": f"Joint pricing at baseline costs changes total surplus by JPY {money('ownership-only', 'social_welfare')} million. The integrated merger reduces the two merging services' marginal costs by {reduction:g}% and uses JPY {cost:g} million in real integration resources.",
        "welfare": f"The integrated merger changes consumer surplus by JPY {money('integrated', 'consumer_surplus')} million and producer surplus by JPY {money('integrated', 'producer_surplus')} million. The total-surplus change, including the integration cost, is JPY {money('integrated', 'social_welfare')} million.",
        "interpretation": "Joint pricing and procurement savings determine the allocation of surplus between drivers and firms. Summing surplus over the same population and period connects price responses and resource costs to the decision criterion.",
        "decisions": "The total-surplus rule selects merger approval." if index["selected_action"] == "approve" else "The total-surplus rule selects baseline ownership.",
    }


def build(root, run, output, language):
    index = read(run / "result-index.json")
    spec_path = checked_reference(root, index["specification"])
    producer = checked_reference(root, index["producer"])
    for ref in (index["formulation"], index["data_record"], *index["results"].values()):
        checked_reference(root, ref)
    spec = read(spec_path)
    bundled = Path(__file__).with_name("charging-specification.json" if FLAT else "specification.json")
    if spec != read(bundled) or index["result_id"] != spec["specification_id"]:
        raise ValueError("Select the matching charging specification and saved generation")
    decision = index["decision_quantities"]
    gain = decision["changes_from_baseline"]["integrated"]["social_welfare"]
    selected = "approve" if gain > 0 else "baseline"
    if selected != index["selected_action"] or gain != index["net_social_surplus_change"]:
        raise ValueError("Decision differs from its saved scientific result")
    for scenario, totals in decision["scenario_totals"].items():
        if not math.isclose(totals["consumer_surplus"] + totals["producer_surplus"], totals["social_welfare"], rel_tol=0, abs_tol=1e-8):
            raise ValueError("Saved surplus accounting differs: " + scenario)
    output.relative_to(root)
    output.mkdir(parents=True, exist_ok=False)
    definition = {key: spec[key] for key in ("question", "population", "period", "unit")}
    definition.update(estimand=spec["economic_model"]["objective"], identification=spec["economic_model"]["identification"],
                      source_specification=reference(root, spec_path))
    definition_path = output / "adopted-definition.json"
    save(definition_path, definition)
    interpretation = design.interpret_result({"specification": reference(root, definition_path),
        "result": reference(root, run / "result-index.json"), "judgment": {
            "owner": "charging example author", "question": spec["question"],
            "prediction": spec["economic_model"]["mechanism_comparison"],
            "comparison": "Common-population surplus under baseline, joint pricing and the integrated merger",
            "decision_criterion": spec["economic_model"]["objective"], "conclusion": "Retain the net surplus comparison and the selected action.",
            "decision": "retain", "observations": [["decision_quantities"], ["uncertainty"], ["selected_action"]]}}, root)
    interpretation_path = output / "interpretation.json"
    save(interpretation_path, interpretation)
    quantities = {}
    for group in ("scenario_totals", "changes_from_baseline"):
        for scenario, values in decision[group].items():
            for name in values:
                quantities[f"{group}.{scenario}.{name}"] = {"key": ["decision_quantities", group, scenario, name], "unit": decision["unit"]}
    for term, values in index["uncertainty"]["coefficients"].items():
        for key in ("estimate", "standard_error", "lower", "upper"):
            quantities[f"demand.{term}.{key}"] = {"key": ["uncertainty", "coefficients", term, key], "unit": values["unit"]}
    inputs = {"sources": [{"id": "charging", "result": reference(root, run / "result-index.json")["path"],
        "code": reference(root, producer)["path"], "specification": reference(root, definition_path)["path"],
        "expected_hashes": {"code": index["producer"]["sha256"], "specification": reference(root, definition_path)["sha256"]},
        "quantities": quantities, "metadata": {"result_interpretation": reference(root, interpretation_path),
            "internal": {"case_specification": reference(root, spec_path), "native_results": index["results"],
                         "inference_scope": spec["internal"]["inference_scope"]}}}], "bindings": {}}
    save(output / "normalization-input.json", inputs)
    registry = artifacts.normalize(root, inputs)
    registry_path = output / "gallery.json"
    artifacts.save_registry(registry_path, registry)
    ja = language == "ja"
    price = index["uncertainty"]["coefficients"]["prices"]
    price_keys = ("estimate", "standard_error", "lower", "upper")
    price_labels = ("推定値", "標準誤差", "95% CI 下限", "95% CI 上限") if ja else ("Estimate", "SE", "95% CI lower", "95% CI upper")
    welfare_keys = ("scenario", "consumer_surplus", "producer_surplus", "social_welfare")
    welfare_labels = ("シナリオ", "消費者余剰", "生産者余剰", "総余剰") if ja else ("Scenario", "Consumer surplus", "Producer surplus", "Total surplus")
    names = {"baseline": ("結合前", "Baseline"), "ownership-only": ("共同価格", "Joint pricing"), "integrated": ("調達統合", "Integration")}
    definitions = [
        {"id": "charging-price", "title": "需要の価格係数" if ja else "Demand price coefficient", "kind": "descriptive", "result_ids": ["charging"],
         "rows": [{key: price[key] for key in price_keys}],
         "columns": [{"key": key, "label": label, "unit": ""} for key, label in zip(price_keys, price_labels)],
         "metadata": {"report_role": "parameters", "unit": price["unit"], "public_claims": ["100円あたりの正規化効用単位" if ja else "Normalized utility units per hundred JPY"],
                      "confidence_level": 0.95, "internal": {"source_keys": {key: quantities['demand.prices.' + key]['key'] for key in price_keys}}},
         "display": {"plot_type": "table", "column_order": list(price_keys), "formats": {key: ".3f" for key in price_keys}}},
        {"id": "charging-welfare", "title": "結合前からの余剰変化" if ja else "Surplus changes from baseline", "kind": "descriptive", "result_ids": ["charging"],
         "rows": [{"scenario": names[scenario][not ja], **{key: value / 10000 for key, value in values.items()}}
                  for scenario, values in decision["changes_from_baseline"].items()],
         "columns": [{"key": key, "label": label, "unit": ""} for key, label in zip(welfare_keys, welfare_labels)],
         "metadata": {"report_role": "welfare", "unit": "million JPY", "public_claims": ["単位：百万円。1週間・潜在的な充電機会10万回。統合費用を含む。" if ja else "Million JPY over one week and 100,000 potential charging occasions, including integration costs."],
                      "internal": {"source_group": ["decision_quantities", "changes_from_baseline"], "display_multiplier": 0.0001}},
         "display": {"plot_type": "table", "column_order": list(welfare_keys), "formats": {key: ".1f" for key in welfare_keys[1:]}}}]
    save(output / "display-items.json", definitions)
    artifacts.register_gallery(root, registry_path, definitions, formats=())
    entries = artifacts.gallery_items(root, registry_path, item_ids=[item["id"] for item in definitions])
    save(output / "selection.json", entries)
    body = prose(index, spec, language)
    titles = {"question": ("企業結合を総余剰で評価する", "Evaluating the merger by total surplus"),
              "model": ("利用者の選択と共同価格設定", "Driver choice and joint pricing"),
              "identification": ("調達価格から需要を推定する", "Estimating demand from procurement prices"),
              "data": ("100市場の充電サービス", "Charging services in 100 markets"),
              "parameters": ("利用者の価格への反応", "Drivers' response to prices"),
              "counterfactual": ("共同価格と調達費用の削減", "Joint pricing and procurement savings"),
              "welfare": ("利用者と企業への余剰配分", "Surplus allocated to drivers and firms"),
              "interpretation": ("価格と資源費用を判断へ結ぶ", "Connecting prices and resource costs to the decision"),
              "decisions": ("総余剰による選択", "The total-surplus choice")}
    for kind in ("brief", "structural"):
        sections = {key: value for key, value in body.items() if key != "title"}
        headings = dict(titles)
        if kind == "brief":
            sections = {"question": body["question"], "data": body["data"],
                        "specification": body["model"] + "\n\n" + body["identification"],
                        "results": body["parameters"] + "\n\n" + body["counterfactual"] + "\n\n" + body["welfare"],
                        "interpretation": body["interpretation"] + "\n\n" + body["decisions"]}
            headings.update(specification=("選択と価格を結ぶ需要", "Demand linking choices and prices"),
                            results=("需要と余剰の推定結果", "Demand and surplus estimates"))
        view = {"language": language, "section_content": sections}
        save(output / (kind + "-view.json"), view)
        bundle = output / kind
        meetings.create_bundle(root, bundle, entries, title=body["title"], kind=kind, project_view=view)
        for section in sections:
            revision = meetings.load_meeting(bundle)[2]
            meetings.edit_section(bundle, section, {"title": headings[section][not ja]}, expected_revision=revision)
    save(output / "material-inputs.json", {"result_index": reference(root, run / "result-index.json"),
        "producer": reference(root, Path(__file__)), "language": language, "analysis_executed": False})
    return {"output": str(output), "bundles": ["brief", "structural"], "analysis_executed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--language", choices=("ja", "en"), default="ja")
    args = parser.parse_args()
    print(json.dumps(build(args.root.resolve(strict=True), args.run.resolve(strict=True), args.output.resolve(), args.language), ensure_ascii=False))
