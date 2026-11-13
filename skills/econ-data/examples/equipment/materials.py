#!/usr/bin/env python3
"""Build bilingual equipment-investment materials from saved scientific results."""
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
    for ref in (index["formulation"], *index["data_records"].values(), *index["results"].values()):
        checked_reference(root, ref)
    spec = read(spec_path)
    bundled = Path(__file__).with_name("equipment-specification.json" if FLAT else "specification.json")
    if spec != read(bundled) or index["result_id"] != spec["specification_id"]:
        raise ValueError("Select the matching equipment specification and saved generation")
    rows = index["decision_quantities"]["rows"]
    selected = max((row for row in rows if row["feasible"]), key=lambda row: row["net_present_gain"])
    if selected["scenario"] != index["selected_action"]:
        raise ValueError("Decision differs from its saved scientific result")
    for row in rows:
        if not math.isclose(row["operating_value_gain"] - row["adoption_cost"], row["net_present_gain"], rel_tol=0, abs_tol=1e-8):
            raise ValueError("Saved present-value accounting differs: " + row["scenario"])
    output.relative_to(root)
    output.mkdir(parents=True, exist_ok=False)
    definition = {key: spec[key] for key in ("question", "population", "period", "unit")}
    definition.update(estimand=spec["economic_model"]["objective"], identification=spec["economic_model"]["identification"],
                      source_specification=reference(root, spec_path))
    definition_path = output / "adopted-definition.json"
    save(definition_path, definition)
    interpretation = design.interpret_result({"specification": reference(root, definition_path),
        "result": reference(root, run / "result-index.json"), "judgment": {
            "owner": "equipment example author", "question": spec["question"],
            "prediction": spec["economic_model"]["mechanism"],
            "comparison": "Mean discounted operating-value gains net of adoption costs for the same initial machines",
            "decision_criterion": spec["economic_model"]["objective"], "conclusion": "Retain the net present gains, pairwise intervals and selected technology.",
            "decision": "retain", "observations": [["decision_quantities"], ["uncertainty"], ["selected_action"]]}}, root)
    interpretation_path = output / "interpretation.json"
    save(interpretation_path, interpretation)
    quantities = {}
    collections = ((["parameters", "rows"], "parameter"), (["replacement_probabilities", "rows"], "scenario"),
                   (["decision_quantities", "rows"], "scenario"), (["uncertainty", "pairwise_contrasts"], "scenario"))
    for path, identity in collections:
        source_rows = index[path[0]][path[1]]
        for position, row in enumerate(source_rows):
            for key, value in row.items():
                if type(value) not in (int, float) or key == "state":
                    continue
                unit = spec["unit"]
                if path[0] == "parameters":
                    unit = "payoff units per wear state" if row[identity] == "maintenance_cost" else "payoff units"
                elif path[0] == "replacement_probabilities" or key == "initial_replacement_probability":
                    unit = "probability per quarter"
                name = ".".join((path[0], str(position), key))
                quantities[name] = {"key": path + [position, key], "unit": unit}
    inputs = {"sources": [{"id": "equipment", "result": reference(root, run / "result-index.json")["path"],
        "code": reference(root, producer)["path"], "specification": reference(root, definition_path)["path"],
        "expected_hashes": {"code": index["producer"]["sha256"], "specification": reference(root, definition_path)["sha256"]},
        "quantities": quantities, "metadata": {"result_interpretation": reference(root, interpretation_path),
            "internal": {"case_specification": reference(root, spec_path), "native_results": index["results"],
                         "inference_scope": spec["internal"]["inference_scope"]}}}], "bindings": {}}
    save(output / "normalization-input.json", inputs)
    registry_path = output / "gallery.json"
    artifacts.save_registry(registry_path, artifacts.normalize(root, inputs))
    ja = language == "ja"
    names = {"baseline": ("基準", "Baseline"), "standard": ("標準", "Standard"), "advanced": ("高度", "Advanced")}
    parameters = {"maintenance_cost": ("維持費用係数", "Maintenance coefficient"), "replacement_cost": ("交換費用", "Replacement cost")}
    param_labels = ("推定パラメータ", "推定値", "標準誤差") if ja else ("Estimated parameter", "Estimate", "SE")
    gain_keys = ("scenario", "adoption_cost", "net_present_gain", "ci_lower", "ci_upper")
    gain_labels = ("技術", "導入費用", "純現在価値", "95%下限", "95%上限") if ja else ("Technology", "Adoption cost", "Net gain", "95% lower", "95% upper")
    definitions = [
        {"id": "equipment-costs", "title": "維持と交換の推定費用" if ja else "Estimated maintenance and replacement costs", "kind": "descriptive", "result_ids": ["equipment"],
         "rows": [{"parameter": parameters[row["parameter"]][not ja], "estimate": row["estimate"], "std_error": row["std_error"]} for row in index["parameters"]["rows"]],
         "columns": [{"key": key, "label": label, "unit": ""} for key, label in zip(("parameter", "estimate", "std_error"), param_labels)],
         "metadata": {"report_role": "parameters", "model_contract": spec["model_contract_id"],
             "public_claims": ["利得1単位＝100千円．維持費用係数は摩耗1段階あたり．" if ja else "One payoff unit = JPY 100 thousand. Maintenance coefficient per wear state."],
             "internal": {"parameter_treatment": "estimated", "inference": spec["estimation"]["inference"]}},
         "display": {"plot_type": "table", "column_order": ["parameter", "estimate", "std_error"], "formats": {"estimate": ".4f", "std_error": ".4f"}}},
        {"id": "equipment-replacement", "title": "摩耗状態ごとの交換確率" if ja else "Replacement probabilities across wear states", "kind": "descriptive", "result_ids": ["equipment"],
         "rows": [{**row, "scenario": names[row["scenario"]][not ja]} for row in index["replacement_probabilities"]["rows"]],
         "columns": [{"key": key, "label": label, "unit": ""} for key, label in zip(("state", "probability", "std_error", "scenario"),
             ("摩耗状態", "交換確率", "標準誤差", "技術") if ja else ("Wear state", "Replacement probability", "SE", "Technology"))],
         "metadata": {"report_role": "counterfactual", "unit": "probability per quarter", "model_contract": spec["model_contract_id"], "public_claims": [],
             "internal": {"state_value_definition": "Infinite quarterly horizon before the action shocks", "source_key": "replacement_probabilities"}},
         "display": {"plot_type": "line", "x": "state", "y": "probability", "series": "scenario", "style": "presentation", "title": "",
             "x_label": "摩耗状態" if ja else "Wear state", "y_label": "四半期の\n交換確率" if ja else "Replacement\nprobability\nper quarter",
             "width": 1200, "height": 620, "font_size": 34, "legend_location": "above"}},
        {"id": "equipment-investment", "title": "導入費用と純現在価値" if ja else "Adoption costs and net present gains", "kind": "descriptive", "result_ids": ["equipment"],
         "rows": [{"scenario": names[row["scenario"]][not ja], **{key: row[key] for key in gain_keys[1:]}} for row in rows],
         "columns": [{"key": key, "label": label, "unit": ""} for key, label in zip(gain_keys, gain_labels)],
         "metadata": {"report_role": "welfare", "unit": spec["unit"], "model_contract": spec["model_contract_id"],
             "public_claims": ["設備1台あたり千円．初期集団の平均．95%信頼区間．" if ja else "Thousand JPY per machine at adoption. Initial-population means. 95% confidence intervals."],
             "internal": {"source_keys": list(gain_keys[1:]), "inference": spec["estimation"]["inference"], "accounting": spec["internal"]["accounting"]}},
         "display": {"plot_type": "table", "column_order": list(gain_keys), "formats": {key: ".1f" for key in gain_keys[1:]}}}]
    save(output / "display-items.json", definitions)
    artifacts.register_gallery(root, registry_path, definitions, formats=("png", "pdf"))
    entries = artifacts.gallery_items(root, registry_path, item_ids=[item["id"] for item in definitions])
    exhibit_titles = {item["id"]: item["title"] for item in definitions}
    for entry in entries:
        entry["title"] = exhibit_titles[entry["id"]]
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
