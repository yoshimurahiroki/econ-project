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


def prose(results, parameters, selected, language):
    contrast = "subsidy40-control"
    def number(outcome, kind="coefficient", scale=1):
        return f"{results[outcome]['statistics'][kind + '.' + contrast]['value'] * scale:.2f}"
    employment = number("employment", scale=100)
    lower = number("employment", "confidence_lower", 100)
    upper = number("employment", "confidence_upper", 100)
    surplus = number("social_surplus")
    slo, shi = number("social_surplus", "confidence_lower"), number("social_surplus", "confidence_upper")
    selected_yen = parameters["subsidies"][selected] * 1000
    markets, per_market = parameters["markets"], parameters["households_per_market"]
    external, burden = parameters["external_benefit_per_job"], parameters["fiscal_excess_burden"]
    if language == "ja":
        return {
            "title": "通勤支援と雇用の配分",
            "question": "通勤支援の給付額は、家計の就業と企業の採用を通じて政策の便益と費用を変える。本研究は、賃金調整と財政費用を含めた8週間の社会的余剰から給付額を選ぶ。",
            "data": f"架空経済の{markets}市場に各{per_market}世帯を配置し、同じ{markets * per_market:,}世帯の雇用、家計余剰、企業利益、財政支出を評価する。市場ごとに0円、2万円、4万円の支援を割り当てる。",
            "specification": "家計は賃金と給付から通勤費用を引いた額を家事生産の価値と比較して就業を選ぶ。企業は限界生産物と賃金を比較して採用数を決める。市場単位の無作為割当から、各給付額の世帯平均の効果を推定する。",
            "results": f"4万円支援の雇用効果は{employment}ポイント、95%信頼区間は[{lower}, {upper}]ポイントである。家計の労働供給の拡大と賃金調整が、企業の採用増加を支える。",
            "interpretation": f"家計余剰と企業利益に就業1人あたり{external / 10:g}万円の社会的便益を加え、給付支出とその{burden:g}倍の資金調達費用を差し引く。4万円支援の余剰効果は1世帯あたり{surplus}千円、95%信頼区間は[{slo}, {shi}]千円である。推定余剰の順位は{selected_yen:,.0f}円支援を選ぶ。",
        }
    return {
        "title": "Commuting Support and the Allocation of Employment",
        "question": "Commuting subsidies change the benefits and costs of employment policy through household participation and firms' hiring. We choose the subsidy by social surplus over eight weeks, incorporating wage adjustment and fiscal costs.",
        "data": f"The fictional economy contains {markets} markets with {per_market} households each. We measure employment, household surplus, firm profit and fiscal spending for the same {markets * per_market:,} households. Markets receive subsidies of JPY 0, 20,000 or 40,000.",
        "specification": "Households compare wages plus the subsidy, net of commuting costs, with home production. Firms compare wages with the marginal product of labor. Random assignment at the market level identifies the average assignment effects across households.",
        "results": f"The JPY 40,000 subsidy raises employment by {employment} percentage points; the 95% confidence interval is [{lower}, {upper}] percentage points. The expansion of labor supply and wage adjustment support firms' increased hiring.",
        "interpretation": f"The policy objective adds household surplus, firm profit and an external benefit of JPY {external:g} thousand per job, then subtracts subsidy spending and its {burden:g}-times financing burden. The JPY 40,000 subsidy has a surplus effect of JPY {surplus} thousand per household; the 95% confidence interval is [{slo}, {shi}] thousand. Ranking estimated surplus selects JPY {selected_yen:,.0f}.",
    }


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
        titles = {"employment": ("雇用の割当効果", "Employment assignment effects"),
                  "social_surplus": ("社会的余剰の割当効果", "Social-surplus assignment effects")}
        labels = ({"subsidy20-control": "2万円 − 0円", "subsidy40-control": "4万円 − 0円",
                   "subsidy40-subsidy20": "4万円 − 2万円"} if language == "ja" else
                  {"subsidy20-control": "20,000 − 0", "subsidy40-control": "40,000 − 0",
                   "subsidy40-subsidy20": "40,000 − 20,000"})
        captions = {"employment": ("1世帯あたり就業者数・8週間。95%信頼区間。", "Employed workers per household over eight weeks. 95% confidence intervals."),
                    "social_surplus": ("1世帯あたり千円・8週間。95%信頼区間。", "Thousand JPY per household over eight weeks. 95% confidence intervals.")}
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
    body = prose(results, parameters, selected, language)
    view = {"language": language, "section_content": {key: value for key, value in body.items() if key != "title"}}
    save(output / "project-view.json", view)
    titles = {"question": ("給付額を社会的余剰で選ぶ", "Choosing the subsidy by social surplus"),
              "data": ("48市場・4,800世帯の政策比較", "A policy comparison across 48 markets"),
              "specification": ("家計の就業と企業の採用を結ぶ", "Linking participation to hiring"),
              "results": ("支援による雇用の増加", "Employment gains from support"),
              "interpretation": ("便益と財政費用から給付額を選ぶ", "Choosing support from benefits and fiscal costs")}
    for kind in ("brief", "results"):
        bundle = output / kind
        meetings.create_bundle(root, bundle, entries, title=body["title"], kind=kind, project_view=view)
        for section, heading in titles.items():
            revision = meetings.load_meeting(bundle)[2]
            meetings.edit_section(bundle, section, {"title": heading[language == "en"]}, expected_revision=revision)
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
