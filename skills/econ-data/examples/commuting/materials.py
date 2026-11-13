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
            "question": "通勤支援の給付額をいくらに設定すべきか．給付は通勤費用を引き下げて家計の就業を促し，労働供給の増加を通じて賃金と企業の採用を動かす．給付支出には資金調達の費用がかかる．本稿では，賃金調整と財政費用を含めた8週間の社会的余剰を基準に，0円，2万円，4万円の3つの給付額を比較する．",
            "data": f"分析には，架空経済の{markets}市場に各{per_market}世帯を配置したデータを用いる．給付額は市場単位で無作為に割り当てた．同じ{markets * per_market:,}世帯について，就業，賃金，家計余剰，企業利益，財政支出を観測している．",
            "specification": "家計は，賃金と給付から通勤費用を引いた額を家事生産の価値と比較して就業を選ぶ．企業は，労働の限界生産物と賃金が等しくなるように採用数を決める．各市場の賃金は，この労働供給と労働需要が一致する水準で決まる．市場単位の無作為割当により，給付額ごとの世帯平均の効果を識別する．",
            "results": f"分析の結果明らかになったのは，4万円の給付が就業を大きく高めることだ．就業確率の上昇は{employment}ポイント(95%信頼区間[{lower}, {upper}])である．労働供給の増加は賃金調整を通じて企業の採用増加につながる．",
            "interpretation": f"社会的余剰は，家計余剰と企業利益に就業1人あたり{external / 10:g}万円の社会的便益を加え，給付支出とその{burden:g}倍の資金調達費用を差し引いて計算する．4万円給付の余剰効果は1世帯あたり{surplus}千円(95%信頼区間[{slo}, {shi}])となる．推定余剰が最も大きい給付額は{selected_yen:,.0f}円である．",
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
    body = prose(results, parameters, selected, language)
    view = {"language": language, "section_content": {key: value for key, value in body.items() if key != "title"}}
    save(output / "project-view.json", view)
    titles = {"question": ("通勤支援の給付額の選択", "Choosing the subsidy by social surplus"),
              "data": ("48市場・4,800世帯の無作為割当", "A policy comparison across 48 markets"),
              "specification": ("家計の就業選択と企業の採用", "Linking participation to hiring"),
              "results": ("4万円給付の雇用効果", "Employment gains from support"),
              "interpretation": ("社会的余剰による給付額の比較", "Choosing support from benefits and fiscal costs")}
    for kind in ("brief", "results"):
        bundle = output / kind
        kind_view = view if kind == "brief" else {**view, "section_content": {key: meetings.sentence_bullets(value)
                                                                            for key, value in view["section_content"].items()}}
        meetings.create_bundle(root, bundle, entries, title=body["title"], kind=kind, project_view=kind_view)
        for section, heading in titles.items():
            revision = meetings.load_meeting(bundle)[2]
            meetings.edit_section(bundle, section, {"title": heading[language == "en"]}, expected_revision=revision)
        if kind == "results":
            # Each table page carries the claim it supports.
            for source, exhibit in (("results", "result-1"), ("interpretation", "result-2")):
                meetings.fold_into_exhibit(bundle, source, exhibit)
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
