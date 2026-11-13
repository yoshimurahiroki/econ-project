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
    price_labels = ("推定値", "標準誤差", "95%下限", "95%上限") if ja else ("Estimate", "SE", "95% CI lower", "95% CI upper")
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
         "metadata": {"report_role": "welfare", "unit": "million JPY", "public_claims": ["単位：百万円．1週間・潜在的な充電機会10万回．統合費用を含む．" if ja else "Million JPY over one week and 100,000 potential charging occasions, including integration costs."],
                      "internal": {"source_group": ["decision_quantities", "changes_from_baseline"], "display_multiplier": 0.0001}},
         "display": {"plot_type": "table", "column_order": list(welfare_keys), "formats": {key: ".1f" for key in welfare_keys[1:]}}}]
    save(output / "display-items.json", definitions)
    artifacts.register_gallery(root, registry_path, definitions, formats=())
    entries = artifacts.gallery_items(root, registry_path, item_ids=[item["id"] for item in definitions])
    save(output / "selection.json", entries)
    # Bundles carry the saved exhibits; prose is composed at task time from inspected sources.
    for kind in ('brief', 'structural'):
        meetings.create_bundle(root, output / kind, entries, title=spec["specification_id"], kind=kind,
                               project_view={"language": language})
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
