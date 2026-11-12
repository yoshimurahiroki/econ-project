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


def prose(index, spec, language):
    rows = {row["scenario"]: row for row in index["decision_quantities"]["rows"]}
    advanced, standard = rows["advanced"], rows["standard"]
    c, replacement = index["parameters"]["rows"]
    contrast = next(row for row in index["uncertainty"]["pairwise_contrasts"]
                    if row["scenario"] == "advanced" and row["comparator"] == "standard")
    s = spec["simulation"]
    money = lambda row, key: f"{row[key]:,.3f}"
    interval = lambda row: f"[{row['ci_lower']:,.3f}, {row['ci_upper']:,.3f}]"
    names = {"baseline": ("基準技術", "baseline technology"), "standard": ("標準技術", "standard technology"),
             "advanced": ("高度技術", "advanced technology")}
    if language == "ja":
        return {
            "title": "設備更新と技術導入の投資価値",
            "question": "更新技術の導入は、将来の設備交換費用と維持・交換の時期を変える。初期の設備集団について操業価値の増分を金額へ換算し、導入費用を差し引いた平均純現在価値から共通技術を選ぶ。",
            "model": f"企業は毎四半期に設備の維持か交換を選ぶ。維持の費用は摩耗とともに増加し、交換すると摩耗は状態0へ戻る。企業は当期の利得と継続価値を合計して行動を決める。四半期の割引因子は{s['discount_factor']:.2f}、利得1単位は{s['money_scale_thousand_jpy']:.0f}千円である。",
            "identification": "維持の費用は摩耗状態に応じて変化し、交換には共通の費用がかかる。採用したモデルでは、摩耗状態ごとの行動の変動が維持費用の係数と交換費用を識別する。",
            "data": f"架空の{s['firms']:,}社が各1台の設備を操業する。{s['quarters']}四半期のパネルは{s['firms'] * s['quarters']:,}件の企業・四半期観測を持つ。企業表と選択表を結合し、摩耗状態、行動、次の状態を同じ観測単位で使う。初期の各摩耗状態には{s['firms'] // s['states']}台を配置する。",
            "specification": "各四半期に選ばれた行動の確率を使って費用を最尤推定する。企業単位のクラスタリングを用い、同じ企業の四半期行動の依存を推論へ反映する。",
            "numerical": "ベルマン方程式から各状態の継続価値と行動確率を計算する。各技術の交換費用で価値関数を解き、同じ初期状態で価値の増分を平均する。価値関数のパラメータ微分と費用推定値の共分散から、投資価値の標準誤差を求める。",
            "parameters": f"維持費用の係数は摩耗1段階あたり{c['estimate']:.4f}利得単位、標準誤差は{c['std_error']:.4f}となる。交換費用は{replacement['estimate']:.4f}利得単位、標準誤差は{replacement['std_error']:.4f}である。",
            "counterfactual": "交換費用を引き下げると、当期の交換利得と、将来の交換機会を持つ設備の継続価値が変わる。各技術の摩耗状態別の交換確率が、その行動調整を表す。",
            "welfare": f"高度技術の期待操業価値の現在価値増分は、設備1台あたり{money(advanced, 'operating_value_gain')}千円となる。導入費用{advanced['adoption_cost']:,.0f}千円を差し引いた純現在価値は{money(advanced, 'net_present_gain')}千円、95%信頼区間は{interval(advanced)}千円である。",
            "interpretation": f"高度技術の純現在価値は、標準技術を1台あたり{money(contrast, 'net_gain_difference')}千円上回る。差の95%信頼区間は{interval(contrast)}千円となる。同じ推定費用から得られる両技術の価値の共分散を、この比較へ反映する。",
            "decisions": f"平均純現在価値に基づき、{names[index['selected_action']][0]}を選ぶ。標準技術の純現在価値は{money(standard, 'net_present_gain')}千円、高度技術では{money(advanced, 'net_present_gain')}千円となる。1台あたりの導入予算は{spec['adoption_budget_thousand_jpy']:,.0f}千円である。",
        }
    return {
        "title": "Equipment Renewal and the Value of Adoption",
        "question": "A renewal technology changes future replacement costs and the timing of maintenance decisions. We select a common technology by its mean discounted operating-value gain after adoption costs over the initial machine population.",
        "model": f"Each quarter, a firm maintains or replaces its machine. Maintenance costs rise with wear; replacement restores state 0. The firm combines current payoff with continuation value when choosing its action. The quarterly discount factor is {s['discount_factor']:.2f}, and one payoff unit equals JPY {s['money_scale_thousand_jpy']:.0f} thousand.",
        "identification": "Wear changes maintenance costs while replacement has a common cost. Variation in quarterly actions across wear states identifies the maintenance-cost coefficient and replacement cost in the adopted model.",
        "data": f"The fictional panel follows {s['firms']:,} firms, each with one machine, for {s['quarters']} quarters. Its {s['firms'] * s['quarters']:,} firm-quarter observations join firm and choice tables and retain wear, action and next state. Each initial wear state contains {s['firms'] // s['states']} machines.",
        "specification": "The probabilities of observed quarterly actions supply the likelihood for cost estimation. Firm-level clustering carries dependence among a firm's quarterly choices into inference.",
        "numerical": "The Bellman equation supplies state values and action probabilities. We solve each technology at its replacement cost and average value gains over the same initial states. Value-function derivatives and the estimated cost covariance give standard errors for investment values.",
        "parameters": f"The estimated maintenance-cost coefficient is {c['estimate']:.4f} payoff units per wear state, with SE {c['std_error']:.4f}. The estimated replacement cost is {replacement['estimate']:.4f} payoff units, with SE {replacement['std_error']:.4f}.",
        "counterfactual": "A lower replacement cost changes the payoff from replacing today and the continuation value of a machine with future replacement opportunities. State-specific replacement probabilities trace this behavioral adjustment across technologies.",
        "welfare": f"Advanced technology yields an expected discounted operating-value gain of JPY {money(advanced, 'operating_value_gain')} thousand per machine. Subtracting its JPY {advanced['adoption_cost']:,.0f} thousand adoption cost gives a net present gain of JPY {money(advanced, 'net_present_gain')} thousand; the 95% confidence interval is {interval(advanced)}.",
        "interpretation": f"The advanced technology's net gain exceeds the standard technology's by JPY {money(contrast, 'net_gain_difference')} thousand per machine; the 95% confidence interval is {interval(contrast)}. The comparison uses the joint covariance of gains sharing the same estimated costs.",
        "decisions": f"The mean net present gain criterion selects {names[index['selected_action']][1]}. Standard technology yields JPY {money(standard, 'net_present_gain')} thousand per machine; advanced technology yields JPY {money(advanced, 'net_present_gain')} thousand. The adoption budget is JPY {spec['adoption_budget_thousand_jpy']:,.0f} thousand per machine.",
    }


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
             "public_claims": ["利得1単位＝100千円。維持費用係数は摩耗1段階あたり。" if ja else "One payoff unit = JPY 100 thousand. Maintenance coefficient per wear state."],
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
             "public_claims": ["設備1台あたり千円。初期集団の平均。95%信頼区間。" if ja else "Thousand JPY per machine at adoption. Initial-population means. 95% confidence intervals."],
             "internal": {"source_keys": list(gain_keys[1:]), "inference": spec["estimation"]["inference"], "accounting": spec["internal"]["accounting"]}},
         "display": {"plot_type": "table", "column_order": list(gain_keys), "formats": {key: ".3f" for key in gain_keys[1:]}}}]
    save(output / "display-items.json", definitions)
    artifacts.register_gallery(root, registry_path, definitions, formats=("png", "pdf"))
    entries = artifacts.gallery_items(root, registry_path, item_ids=[item["id"] for item in definitions])
    exhibit_titles = {item["id"]: item["title"] for item in definitions}
    for entry in entries:
        entry["title"] = exhibit_titles[entry["id"]]
    save(output / "selection.json", entries)
    body = prose(index, spec, language)
    titles = {"question": ("将来の交換機会から導入価値を測る", "Valuing adoption through future replacement choices"),
              "model": ("維持・交換と継続価値", "Maintenance, replacement and continuation value"),
              "identification": ("摩耗状態と行動から費用を識別する", "Identifying costs from wear and actions"),
              "data": ("480社の四半期行動を結ぶ", "Connecting quarterly actions across 480 firms"),
              "specification": ("行動確率から費用を推定する", "Estimating costs from action probabilities"),
              "numerical": ("価値関数を投資価値へつなぐ", "Connecting value functions to investment gains"),
              "parameters": ("維持と交換の費用推定値", "Estimated maintenance and replacement costs"),
              "counterfactual": ("技術が交換行動を変える", "Technology changes replacement behavior"),
              "welfare": ("導入費用を含む投資価値", "Investment value after adoption costs"),
              "interpretation": ("追加投資の純現在価値", "Net present gain from the additional investment"),
              "decisions": ("平均純現在価値から技術を選ぶ", "Selecting technology by mean net present gain")}
    for kind in ("brief", "structural"):
        sections = {key: value for key, value in body.items() if key != "title"}
        headings = dict(titles)
        if kind == "brief":
            sections = {"question": body["question"], "data": body["data"],
                        "specification": "\n\n".join(body[key] for key in ("model", "identification", "specification")),
                        "results": "\n\n".join(body[key] for key in ("parameters", "welfare")),
                        "interpretation": body["interpretation"] + "\n\n" + body["decisions"]}
            headings.update(results=("費用推定値と技術の投資価値", "Estimated costs and technology investment values"))
        view = {"language": language, "section_content": sections}
        save(output / (kind + "-view.json"), view)
        bundle = output / kind
        meetings.create_bundle(root, bundle, entries, title=body["title"], kind=kind, project_view=view)
        for section in sections:
            meetings.edit_section(bundle, section, {"title": headings[section][not ja]}, expected_revision=meetings.load_meeting(bundle)[2])
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
