#!/usr/bin/env python3
"""Build bilingual housing-policy materials from an executed result index."""
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
    bundled = Path(__file__).with_name("housing-specification.json" if FLAT else "specification.json")
    if spec != read(bundled) or index["result_id"] != spec["specification_id"]:
        raise ValueError("Select the matching housing specification and saved generation")
    rows = index["decision_quantities"]["rows"]
    selected = max((row for row in rows if row["feasible"]), key=lambda row: row["net_income_equivalent"])
    if selected["scenario"] != index["selected_action"]:
        raise ValueError("Decision differs from its saved scientific result")
    for row in rows:
        if not math.isclose(row["worker_income_equivalent"] + row["owner_income_change_net"], row["net_income_equivalent"], rel_tol=0, abs_tol=1e-8):
            raise ValueError("Saved income-equivalent accounting differs: " + row["scenario"])
    output.relative_to(root)
    output.mkdir(parents=True, exist_ok=False)
    definition = {key: spec[key] for key in ("question", "population", "period", "unit")}
    definition.update(estimand=spec["economic_model"]["objective"], identification=spec["economic_model"]["identification"],
                      source_specification=reference(root, spec_path))
    definition_path = output / "adopted-definition.json"
    save(definition_path, definition)
    interpretation = design.interpret_result({"specification": reference(root, definition_path),
        "result": reference(root, run / "result-index.json"), "judgment": {
            "owner": "housing example author", "question": spec["question"],
            "prediction": spec["economic_model"]["mechanism_comparison"],
            "comparison": "Same-population annual income equivalents under baseline, transport and transport with floor expansion",
            "decision_criterion": spec["economic_model"]["objective"], "conclusion": "Retain the annual net gain comparison and selected policy.",
            "decision": "retain", "observations": [["decision_quantities"], ["uncertainty"], ["selected_action"]]}}, root)
    interpretation_path = output / "interpretation.json"
    save(interpretation_path, interpretation)
    quantities = {}
    for position, row in enumerate(rows):
        for key, value in row.items():
            if type(value) in (int, float):
                unit = {"mean_commute_minutes": "minutes", "additional_floor_m2": "square meters"}.get(key, spec["unit"])
                quantities[row["scenario"] + "." + key] = {"key": ["decision_quantities", "rows", position, key], "unit": unit}
    inputs = {"sources": [{"id": "housing", "result": reference(root, run / "result-index.json")["path"],
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
    names = {"baseline": ("基準", "Baseline"), "transport": ("交通整備", "Transport"),
             "transport-and-floor": ("交通＋床供給", "Transport + floor")}
    series = {"worker_income_equivalent": ("労働者", "Workers"),
              "owner_income_change_net": ("所有者\n純所得", "Owners,\nnet"),
              "net_income_equivalent": ("純便益", "Net gain")}
    welfare_rows = [{"scenario": names[row["scenario"]][not ja], "group": label[not ja], "value": row[key] / 1000}
                    for row in rows if row["scenario"] != "baseline" for key, label in series.items()]
    money_keys = ("scenario", "policy_resource_cost", "net_income_equivalent")
    money_labels = ("政策", "年間費用", "年間純便益") if ja else ("Policy", "Annual cost", "Annual net gain")
    definitions = [
        {"id": "housing-budget", "title": "年間費用と純便益" if ja else "Annual costs and net gains", "kind": "descriptive", "result_ids": ["housing"],
         "rows": [{"scenario": names[row["scenario"]][not ja], **{key: row[key] / 1000 for key in money_keys[1:]}} for row in rows],
         "columns": [{"key": key, "label": label, "unit": ""} for key, label in zip(money_keys, money_labels)],
         "metadata": {"report_role": "counterfactual", "unit": "million JPY per year",
             "public_claims": ["単位：百万円／年．労働者12,000人と床所有者．" if ja else "Million JPY per year for 12,000 workers and floor owners."],
             "internal": {"source_keys": list(money_keys[1:]), "display_multiplier": .001}},
         "display": {"plot_type": "table", "column_order": list(money_keys), "formats": {key: ".1f" for key in money_keys[1:]}}},
        {"id": "housing-welfare", "title": "労働者と所有者への便益配分" if ja else "Gains allocated to workers and owners", "kind": "descriptive", "result_ids": ["housing"],
         "rows": welfare_rows, "columns": [{"key": key, "label": label, "unit": ""} for key, label in
             zip(("scenario", "group", "value"), ("政策", "主体・合計", "年間所得換算便益") if ja else ("Policy", "Group or total", "Annual income equivalent"))],
         "metadata": {"report_role": "welfare", "unit": "million JPY per year", "reference_lines": [{"axis": "y", "value": 0}],
             "public_claims": [],
             "internal": {"source_keys": list(series), "display_multiplier": .001}},
         "display": {"plot_type": "bar", "x": "scenario", "y": "value", "series": "group", "style": "presentation", "title": "",
             "x_label": "政策" if ja else "Policy", "y_label": "百万円／年" if ja else "Million JPY/year", "width": 1100, "height": 620, "font_size": 34,
             "legend_location": "above", "formats": {"value": ".3f"}}},
        {"id": "housing-commute", "title": "立地選択後の平均通勤時間" if ja else "Mean commuting time after location choice", "kind": "descriptive", "result_ids": ["housing"],
         "rows": [{"scenario": names[row["scenario"]][not ja], "minutes": row["mean_commute_minutes"]} for row in rows],
         "columns": [{"key": "scenario", "label": "政策" if ja else "Policy", "unit": ""},
                     {"key": "minutes", "label": "平均通勤時間" if ja else "Mean commuting time", "unit": "分" if ja else "minutes"}],
         "metadata": {"report_role": "counterfactual", "public_claims": ["同じ12,000人の居住地・勤務地選択で重み付けした平均．" if ja else "Mean weighted by the residence-workplace choices of the same 12,000 workers."],
             "internal": {"source_key": "mean_commute_minutes"}},
         "display": {"plot_type": "table", "column_order": ["scenario", "minutes"], "formats": {"minutes": ".1f"}}}]
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
