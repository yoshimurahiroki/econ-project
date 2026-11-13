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


def prose(index, spec, language):
    rows = {row["scenario"]: row for row in index["decision_quantities"]["rows"]}
    combined, transport = rows["transport-and-floor"], rows["transport"]
    money = lambda row, key: f"{row[key] / 1000:,.1f}".replace("-", "−")
    names = {"baseline": ("基準の配分", "the baseline allocation"),
             "transport": ("交通整備", "transport investment"),
             "transport-and-floor": ("交通整備と床供給拡張の組合せ", "combined transport investment and floor expansion")}
    if language == "ja":
        return {
            "title": "通勤アクセスと床供給の政策評価",
            "question": "都市当局は交通整備に床供給の拡張を組み合わせるべきか．交通整備は通勤時間を短縮し，労働者の居住地と勤務地の選択を変える．労働者が郊外へ移ると郊外の賃料が上がり，床供給が制約されていれば便益の一部は所有者に帰着する．本稿では，定量的空間均衡モデルを用いて，交通整備単独と床供給拡張との組合せの年間純便益を比較する．",
            "model": "労働者は，賃金，賃料，通勤時間，居住環境に基づいて居住地と勤務地の組を選ぶ．企業は労働と事業用床を投入して財を生産する．各地区の床市場では，住宅用と事業用の床需要の合計が床供給に等しい．居住と雇用の密度は，それぞれ居住環境と生産性に集積効果として作用する．",
            "identification": "弾力性と通勤費用の係数は既存研究の値を採用する．その下で，地区別の居住者数，就業者数，賃料を均衡条件に代入し，観察されない賃金，生産性，居住環境，床供給を基準均衡として復元する．",
            "data": "分析には，架空都市の3地区に暮らす労働者12,000人のデータを用いる．地区別に居住者数と事業所の就業者数を集計した．地区の賃料は，年間の賃料収入総額を賃貸床面積で割って求めている．居住地と勤務地の9つの組について移動時間を対応させた．",
            "parameters": "基準均衡の平均年賃金は400万円である．交通整備は中心部と郊外の間の移動時間を40分から20分に短縮する．組合せ政策では，これに加えて郊外の床供給を20%拡張する．いずれの政策も同じ基準均衡から反実仮想の均衡を計算する．",
            "counterfactual": f"交通整備の年間費用は{money(transport, 'policy_resource_cost')}百万円である．組合せ政策は{combined['additional_floor_m2']:,.0f}平方メートルの床を追加し，年間費用は{money(combined, 'policy_resource_cost')}百万円となる．年間の資源予算は{spec['policy_budget_thousand_jpy'] / 1000:,.0f}百万円である．",
            "welfare": f"組合せ政策による労働者の便益は，所得換算で{money(combined, 'worker_income_equivalent')}百万円である．所有者の賃料収入は{money(combined, 'owner_income_change_gross')}百万円増加し，政策費用を負担した後の所得変化は{money(combined, 'owner_income_change_net')}百万円となる．両者を合計した年間純便益は{money(combined, 'net_income_equivalent')}百万円である．",
            "interpretation": f"平均通勤時間は，基準均衡の{rows['baseline']['mean_commute_minutes']:.1f}分から組合せ政策では{combined['mean_commute_minutes']:.1f}分となる．政策の便益は，この立地の再配分を織り込んで評価される．",
            "decisions": f"年間純便益の基準による選択は{names[index['selected_action']][0]}である．年間純便益は交通整備単独で{money(transport, 'net_income_equivalent')}百万円，床供給拡張との組合せで{money(combined, 'net_income_equivalent')}百万円となる．",
        }
    return {
        "title": "Commuting Access, Floor Supply, and Policy Gains",
        "question": "Transport investment changes residence-workplace choices and distributes gains through wages and rents. The authority selects a policy by adding the worker income equivalent to the change in owners' net income.",
        "model": "Workers choose where to live and work using wages, rents, travel times and amenities. Firms produce the traded good with labor and commercial floor space. Residential and commercial demand exhaust district floor supply. Residential and employment density affect amenities and productivity.",
        "identification": "At the adopted elasticities and commuting-cost coefficient, district residents, jobs and rents recover baseline wages, productivity, amenities and floor supply.",
        "data": "The fictional city contains 12,000 workers in three districts. We aggregate residents and jobs from disjoint subdistrict and workplace records. Annual lease revenue divided by leased floor area gives district rent. Nine directed residence-workplace travel pairs complete the shared tables.",
        "parameters": "The baseline mean annual wage is JPY 4 million. Transport investment reduces center–outer travel time from 40 to 20 minutes. The combined policy also expands outer-district floor supply by 20%. Both policies carry forward the same baseline equilibrium.",
        "counterfactual": f"Transport service costs JPY {money(transport, 'policy_resource_cost')} million annually. The combined policy adds {combined['additional_floor_m2']:,.0f} square meters of floor services and costs JPY {money(combined, 'policy_resource_cost')} million annually. The annual resource budget is JPY {spec['policy_budget_thousand_jpy'] / 1000:,.0f} million.",
        "welfare": f"The combined policy gives workers JPY {money(combined, 'worker_income_equivalent')} million of income equivalent. Owners' rental receipts rise by JPY {money(combined, 'owner_income_change_gross')} million, and their income after the policy charge changes by JPY {money(combined, 'owner_income_change_net')} million. The annual net gain is JPY {money(combined, 'net_income_equivalent')} million.",
        "interpretation": f"The composition of residences and workplaces determines mean commuting time. Its baseline value is {rows['baseline']['mean_commute_minutes']:.1f} minutes; the combined policy gives {combined['mean_commute_minutes']:.1f} minutes. Valuing workers' utility changes at baseline prices and adding owners' net income changes connects the allocation to the policy objective.",
        "decisions": f"The annual net income-equivalent criterion selects {names[index['selected_action']][1]}. Transport investment yields JPY {money(transport, 'net_income_equivalent')} million of net gains; adding floor supply yields JPY {money(combined, 'net_income_equivalent')} million.",
    }


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
    body = prose(index, spec, language)
    titles = {"question": ("交通整備と床供給の政策評価", "Evaluating transport and floor supply citywide"),
              "model": ("居住地・勤務地選択と床市場", "Residence, workplace and floor use"),
              "identification": ("基準均衡の復元", "Recovering equilibrium from district populations and prices"),
              "data": ("3地区の人口・賃料・移動時間", "Connecting population, prices and travel across three districts"),
              "parameters": ("基準均衡と政策の設定", "Computing policies from the baseline equilibrium"),
              "counterfactual": ("政策の年間費用と純便益", "Costs of transport investment and floor supply"),
              "welfare": ("労働者と所有者への便益の帰着", "Allocating gains to workers and owners"),
              "interpretation": ("立地の再配分と平均通勤時間", "Connecting location choices to policy gains"),
              "decisions": ("採用する政策", "Selecting policy by annual net gains")}
    for kind in ("brief", "structural"):
        sections = {key: value for key, value in body.items() if key != "title"}
        headings = dict(titles)
        if kind == "brief":
            sections = {"question": body["question"], "data": body["data"],
                        "specification": body["model"] + "\n\n" + body["identification"],
                        "results": body["parameters"] + "\n\n" + body["counterfactual"] + "\n\n" + body["welfare"],
                        "interpretation": body["interpretation"] + "\n\n" + body["decisions"]}
            headings.update(specification=("空間均衡モデル", "Equilibrium linking locations and floor markets"),
                            results=("政策費用と便益の配分", "Policy costs and the allocation of gains"))
        if kind == "structural":
            sections = {key: meetings.sentence_bullets(value) for key, value in sections.items()}
        view = {"language": language, "section_content": sections}
        save(output / (kind + "-view.json"), view)
        bundle = output / kind
        meetings.create_bundle(root, bundle, entries, title=body["title"], kind=kind, project_view=view)
        for section in sections:
            revision = meetings.load_meeting(bundle)[2]
            meetings.edit_section(bundle, section, {"title": headings[section][not ja]}, expected_revision=revision)
        if kind == "structural":
            # Each exhibit page carries the claim it supports.
            for source, exhibit, layout in (("counterfactual", "result-1", "stack"), ("welfare", "result-2", "figure-left")):
                meetings.fold_into_exhibit(bundle, source, exhibit, layout=layout)
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
