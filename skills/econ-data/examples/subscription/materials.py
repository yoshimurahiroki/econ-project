#!/usr/bin/env python3
"""Build bilingual subscription-policy materials from saved evaluation results."""
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
    bundled = Path(__file__).with_name("subscription-specification.json" if FLAT else "specification.json")
    if spec != read(bundled) or index["result_id"] != spec["specification_id"]:
        raise ValueError("Select the matching subscription specification and saved generation")
    rows = index["decision_quantities"]["rows"]
    selected = max(enumerate(rows), key=lambda pair: (pair[1]["training_fitted_net_contribution"], -pair[1]["contacts"], -pair[0]))[1]
    if selected["scenario"] != index["selected_action"]:
        raise ValueError("Selected allocation differs from the saved training-predicted criterion")
    count = spec["simulation"]["customers"] - spec["simulation"]["training_customers"]
    for row in rows:
        value = spec["simulation"]["renewal_contribution"] * row["renewal_rate"] - row["total_contact_cost"] / count
        if not math.isclose(value, row["net_contribution"], rel_tol=0, abs_tol=1e-8):
            raise ValueError("Saved contribution accounting differs: " + row["scenario"])
    output.relative_to(root)
    output.mkdir(parents=True, exist_ok=False)
    definition = {key: spec[key] for key in ("question", "period", "unit")}
    definition.update(population=index["decision_quantities"]["population"], estimand=spec["inference"]["target"],
                      identification=spec["economic_model"]["identification"], source_specification=reference(root, spec_path))
    definition_path = output / "adopted-definition.json"
    save(definition_path, definition)
    interpretation = design.interpret_result({"specification": reference(root, definition_path),
        "result": reference(root, run / "result-index.json"), "judgment": {
            "owner": "subscription example author", "question": spec["question"], "prediction": spec["economic_model"]["mechanism"],
            "comparison": "Training-fixed contact allocations on the same held-out customer cohort",
            "decision_criterion": spec["learning"]["selection"],
            "conclusion": "Retain the policy values, paired intervals, pretreatment group effects and selected allocation.",
            "decision": "retain", "observations": [["decision_quantities"], ["uncertainty"], ["heterogeneity"], ["selected_action"]]}}, root)
    interpretation_path = output / "interpretation.json"
    save(interpretation_path, interpretation)
    quantities = {"prediction.brier_loss": {"key": ["prediction", "brier_loss"], "unit": "squared probability"},
                  "prediction.observed_customers": {"key": ["prediction", "observed_customers"], "unit": "customers"}}
    groups = index["heterogeneity"]["rows"]
    collections = [(["decision_quantities", "rows"], index["decision_quantities"]["field_units"]),
        (["prediction", "calibration"], index["prediction"]["calibration_field_units"]),
        (["heterogeneity", "rows"], {key: "customers" if key == "customers" else "percentage points of quarterly renewal"
                                    for key in groups[0] if key != "support_need"}),
        (["uncertainty", "pairwise_contrasts"], {key: spec["unit"] for key in ("net_gain_difference", "std_error", "ci_lower", "ci_upper")})]
    for path, units in collections:
        for position, row in enumerate(index[path[0]][path[1]]):
            for key, unit in units.items():
                quantities[".".join((path[0], str(position), key))] = {"key": path + [position, key], "unit": unit}
    for key in index["heterogeneity"]["need_group_difference"]:
        quantities["group_difference." + key] = {"key": ["heterogeneity", "need_group_difference", key], "unit": "percentage points of quarterly renewal"}
    inputs = {"sources": [{"id": "subscription", "result": reference(root, run / "result-index.json")["path"],
        "code": reference(root, producer)["path"], "specification": reference(root, definition_path)["path"],
        "expected_hashes": {"code": index["producer"]["sha256"], "specification": reference(root, definition_path)["sha256"]},
        "quantities": quantities, "metadata": {"result_interpretation": reference(root, interpretation_path),
            "internal": {"case_specification": reference(root, spec_path), "native_results": index["results"],
                         "inference": spec["inference"]}}}], "bindings": {}}
    save(output / "normalization-input.json", inputs)
    registry_path = output / "gallery.json"
    artifacts.save_registry(registry_path, artifacts.normalize(root, inputs))
    ja = language == "ja"
    contrasts = index["uncertainty"]["pairwise_contrasts"]
    contrast_names = [("解約予測 − 現行", "Risk − existing"), ("学習配分 − 現行", "Learned − existing"),
                      ("学習配分 − 解約予測", "Learned − risk")]
    effect_keys = ["group", "customers", "renewal_effect", "ci_lower", "ci_upper"]
    effect_labels = ["事前の申告指標", "顧客数", "継続効果", "95%下限", "95%上限"] if ja else ["Prior need indicator", "Customers", "Renewal effect", "95% lower", "95% upper"]
    gain_keys = ["comparison", "net_gain_difference", "ci_lower", "ci_upper"]
    gain_labels = ["配分の比較", "利益増加", "95%下限", "95%上限"] if ja else ["Allocation contrast", "Contribution gain", "95% lower", "95% upper"]
    definitions = [
        {"id": "subscription-group-effects", "title": "利用支援の必要性と契約継続の効果" if ja else "Onboarding needs and renewal effects",
         "kind": "descriptive", "result_ids": ["subscription"],
         "rows": [{"group": str(row["support_need"]), **{key: row[key] for key in effect_keys[1:]}} for row in groups],
         "columns": [{"key": key, "label": label, "unit": ""} for key, label in zip(effect_keys, effect_labels)],
         "metadata": {"report_role": "descriptive", "unit": "percentage points of quarterly renewal",
             "public_claims": ["評価対象4,000人．契約継続率の変化・ポイント．95%信頼区間．" if ja else "4,000 evaluation customers. Renewal effects in percentage points. 95% confidence intervals."],
             "internal": {"inference": spec["inference"], "source_key": "heterogeneity.rows"}},
         "display": {"plot_type": "table", "column_order": effect_keys,
             "formats": {key: ".0f" if key == "customers" else ".2f" for key in effect_keys[1:]}}},
        {"id": "subscription-policy-gains", "title": "支援配分による利益の増加" if ja else "Contribution gains from support allocation",
         "kind": "descriptive", "result_ids": ["subscription"],
         "rows": [{"comparison": contrast_names[j][not ja], **{key: row[key] for key in gain_keys[1:]}} for j, row in enumerate(contrasts)],
         "columns": [{"key": key, "label": label, "unit": ""} for key, label in zip(gain_keys, gain_labels)],
         "metadata": {"report_role": "main", "unit": spec["unit"],
             "public_claims": ["評価対象の顧客1人あたり・四半期・千円．95%信頼区間．" if ja else "Thousand JPY per evaluation customer per quarter. 95% confidence intervals."],
             "internal": {"inference": spec["inference"], "source_key": "uncertainty.pairwise_contrasts"}},
         "display": {"plot_type": "table", "column_order": gain_keys, "formats": {key: ".3f" for key in gain_keys[1:]}}},
        {"id": "subscription-calibration", "title": "契約継続の予測と観測" if ja else "Predicted and observed renewal",
         "kind": "descriptive", "result_ids": ["subscription"],
         "rows": [{"predicted": row["predicted_renewal"], "observed": row["observed_renewal"]} for row in index["prediction"]["calibration"]],
         "columns": [{"key": key, "label": label, "unit": "probability"} for key, label in zip(["predicted", "observed"],
             ["平均予測値", "契約継続率"] if ja else ["Mean prediction", "Observed renewal"])],
         "metadata": {"report_role": "additional", "unit": "probability",
             "public_claims": [f"通常サービス{index['prediction']['observed_customers']:,}人・確率0.2幅" if ja else
                 f"Control: {index['prediction']['observed_customers']:,}; bin width: 0.2"],
             "internal": {"bin_closure": index["prediction"]["calibration_bin_closure"], "source_key": "prediction.calibration"},
             "reference_lines": [{"axis": "identity"}]},
         "display": {"plot_type": "scatter", "x": "predicted", "y": "observed", "style": "presentation", "title": "",
             "x_limits": [0, 1], "y_limits": [0, 1],
             "x_label": "平均予測確率" if ja else "Mean prediction",
             "y_label": "契約継続率" if ja else "Renewal rate", "width": 760, "height": 640,
             "font_size": 32, "legend": False, "colors": {"": "#922E41"}}}]
    paper_calibration = {**definitions[2], "id": "subscription-calibration-paper",
                         "display": {**definitions[2]["display"], "style": "paper", "font_size": 14}}
    save(output / "display-items.json", [*definitions, paper_calibration])
    artifacts.register_gallery(root, registry_path, [*definitions, paper_calibration], formats=("png", "pdf"))
    entries = artifacts.gallery_items(root, registry_path, item_ids=[item["id"] for item in definitions])
    for entry in entries:
        entry["title"] = next(item["title"] for item in definitions if item["id"] == entry["id"])
        if entry["id"] == "subscription-calibration":
            # The saved figure already prints its population and bin definition.
            entry["public_text"] = []
    save(output / "selection.json", entries)
    # Bundles carry the saved exhibits; prose is composed at task time from inspected sources.
    for kind in ("brief", "results"):
        meetings.create_bundle(root, output / kind, entries[:2] if kind == "brief" else entries,
                               title=spec["specification_id"], kind=kind, project_view={"language": language})
    save(output / "material-inputs.json", {"result_index": reference(root, run / "result-index.json"),
        "producer": reference(root, Path(__file__)), "language": language, "analysis_executed": False})
    return {"output": str(output), "bundles": ["brief", "results"], "analysis_executed": False}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--language", choices=("ja", "en"), default="ja")
    args = parser.parse_args()
    print(json.dumps(build(args.root.resolve(strict=True), args.run.resolve(strict=True), args.output.resolve(), args.language), ensure_ascii=False))
