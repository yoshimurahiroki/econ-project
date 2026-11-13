#!/usr/bin/env python3
"""Build bilingual research materials from the saved commuting experiment."""
import argparse
import hashlib
import json
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
    observed = reference(root, path)
    if observed["sha256"] != ref["sha256"]:
        raise ValueError("Saved input changed: " + observed["path"])
    return path


def build(root, run, output, language):
    index = read(run / "result-index.json")
    spec_path = checked_reference(root, index["specification"])
    checked_reference(root, index["producer"])
    checked_reference(root, index["formulation"])
    specification = read(spec_path)
    bundled_spec = Path(__file__).with_name("commuting-specification.json" if FLAT else "specification.json")
    if specification != read(bundled_spec):
        raise ValueError("Select the matching commuting specification and saved generation")
    results = {name: read(checked_reference(root, ref)) for name, ref in index["results"].items()}
    parameters = specification["parameters"]
    changes = {"control": 0.0, **{arm: results["social_surplus"]["coefficients"][arm + "-control"]
                               for arm in ("subsidy20", "subsidy40")}}
    selected = max(changes, key=lambda arm: (changes[arm], -parameters["subsidies"][arm]))
    if selected != index["selected_arm"] or changes != index["estimated_surplus_changes"]:
        raise ValueError("Policy selection differs from its saved scientific result")
    output.relative_to(root)
    output.mkdir(parents=True, exist_ok=False)
    sources = []
    for name, result in results.items():
        provenance = result["provenance"]
        result_ref = reference(root, Path(index["results"][name]["path"]))
        analysis_ref = reference(root, Path(provenance["spec_path"]))
        judgment = {"owner": "commuting example author", "question": specification["question"],
                    "prediction": specification["mechanism"],
                    "comparison": "Prespecified subsidy contrasts on the common household population",
                    "decision_criterion": specification["internal"]["decision"],
                    "conclusion": "Retain the executed assignment contrasts and their pointwise intervals for the adopted policy comparison.",
                    "decision": "retain", "observations": [["coefficients"], ["inference"], ["sample"]]}
        interpretation = design.interpret_result({"specification": analysis_ref, "result": result_ref,
                                                 "judgment": judgment}, root)
        interpretation_path = output / (name + "-interpretation.json")
        save(interpretation_path, interpretation)
        sources.append({"id": name, "result": result_ref["path"], "specification": analysis_ref["path"],
                        "code": reference(root, Path(provenance["producer_path"]))["path"],
                        "data": reference(root, Path(provenance["data_path"]))["path"],
                        "metadata": {"result_interpretation": reference(root, interpretation_path),
                                     "internal": {"case_specification": reference(root, spec_path)}}})
    inputs = {"sources": sources, "bindings": {}}
    save(output / "normalization-input.json", inputs)
    registry = artifacts.normalize(root, inputs)
    registry_path = output / "gallery.json"
    artifacts.save_registry(registry_path, registry)
    definitions = []
    selected_ids = []
    for name in ("employment", "social_surplus"):
        item = next(value for value in registry["items"].values() if value["result_ids"] == [name])
        selected_ids.append(item["id"])
        unit = results[name]["statistics"]["coefficient.subsidy40-control"]["unit"]
        titles = {"employment": ("給付額別の雇用効果", "Employment assignment effects"),
                  "social_surplus": ("給付額別の社会的余剰", "Social-surplus assignment effects")}
        labels = ({"subsidy20-control": "2万円 − 0円", "subsidy40-control": "4万円 − 0円",
                   "subsidy40-subsidy20": "4万円 − 2万円"} if language == "ja" else
                  {"subsidy20-control": "20,000 − 0", "subsidy40-control": "40,000 − 0",
                   "subsidy40-subsidy20": "40,000 − 20,000"})
        captions = {"employment": ("1世帯あたり就業者数・8週間．95%信頼区間．", "Employed workers per household over eight weeks. 95% confidence intervals."),
                    "social_surplus": ("1世帯あたり千円・8週間．95%信頼区間．", "Thousand JPY per household over eight weeks. 95% confidence intervals.")}
        rows = [{**row, "comparison": labels[row["term"]]} for row in item["rows"]]
        # The caption carries the unit, so the numeric columns print their labels alone.
        columns = [{**column, "unit": ""} if column["key"] in ("estimate", "ci_low", "ci_high") else column for column in item["columns"]]
        columns += [{"key": "comparison", "label": "支援額の比較" if language == "ja" else "Subsidy contrast, JPY", "unit": ""}]
        column_labels = {"estimate": "推定値", "ci_low": "95%下限", "ci_high": "95%上限"} if language == "ja" else {"estimate": "Estimate", "ci_low": "95% CI lower", "ci_high": "95% CI upper"}
        definitions.append({"id": item["id"], "rows": rows, "columns": columns,
                            "title": titles[name][language == "en"],
                            "metadata": {"public_claims": [captions[name][language == "en"]], "unit": unit, "internal": {"case_specification": reference(root, spec_path)}},
                            "display": {"plot_type": "table", "column_order": ["comparison", "estimate", "ci_low", "ci_high"],
                                        "column_labels": column_labels, "formats": {key: ".3f" for key in ("estimate", "ci_low", "ci_high")}}})
    save(output / "display-items.json", definitions)
    artifacts.register_gallery(root, registry_path, definitions, formats=())
    entries = artifacts.gallery_items(root, registry_path, item_ids=selected_ids)
    save(output / "selection.json", entries)
    # Bundles carry the saved exhibits; prose is composed at task time from inspected sources.
    for kind in ('brief', 'results'):
        meetings.create_bundle(root, output / kind, entries, title=read(spec_path)["specification_id"], kind=kind,
                               project_view={"language": language})
    save(output / "material-inputs.json", {"result_index": reference(root, run / "result-index.json"),
                                          "producer": reference(root, Path(__file__)), "language": language,
                                          "selected_arm": selected, "analysis_executed": False})
    return {"output": str(output), "bundles": ["brief", "results"], "analysis_executed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--language", choices=("ja", "en"), default="ja")
    args = parser.parse_args()
    print(json.dumps(build(args.root.resolve(strict=True), args.run.resolve(strict=True),
                           args.output.resolve(), args.language), ensure_ascii=False))
