#!/usr/bin/env python3
"""Build bilingual subscription-policy materials from saved evaluation results."""
import argparse
import hashlib
import json
import math
import re
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
    s = spec["simulation"]
    groups = index["heterogeneity"]["rows"]
    difference = index["heterogeneity"]["need_group_difference"]
    contrast = {(row["scenario"], row["comparator"]): row for row in index["uncertainty"]["pairwise_contrasts"]}
    gain, advantage = contrast["policy", "baseline"], contrast["policy", "risk"]
    selected = {"baseline": ("現在のサービス", "the existing service"), "risk": ("解約予測に基づく配分", "risk targeting"),
                "policy": ("決定木を使った配分", "the learned policy allocation")}[index["selected_action"]][language == "en"]
    interval = lambda row, scale=1: f"[{row['ci_lower'] * scale:,.2f}, {row['ci_upper'] * scale:,.2f}]"
    if language == "ja":
        return {
            "title": "継続契約と利用支援の配分",
            "question": "企業は、契約継続から得る四半期の利益を最大にする利用支援の配分を選ぶ。支援は利用方法を習得する負担を減らし、顧客が契約を更新する便益を高める。対応人数の上限が、支援先を選ぶ基準に入る。",
            "data": f"架空経済の{s['customers']:,}人に支援を無作為に割り当てる。{s['training_customers']:,}人を学習用、残る{s['customers'] - s['training_customers']:,}人を評価用に固定する。事前の利用離れを表す指標、利用支援の必要性、支援の割当、四半期の契約更新を同じ顧客IDで結ぶ。",
            "specification": f"各顧客への支援確率は{s['assignment_probability']:.1f}である。学習用標本から支援行動別の継続を予測し、決定木で配分候補を作る。企業は継続契約1件から{s['renewal_contribution']:g}千円を得て、支援1件に{s['contact_cost']:g}千円を支払う。対応能力{s['maximum_contacts']:,}人、予算{s['contact_budget']:,.0f}千円の範囲で、予測利益が最大の配分を選ぶ。",
            "table1": f"利用支援の必要性を事前に申告した群の推定継続効果は{groups[1]['renewal_effect']:.2f}ポイント、95%信頼区間は{interval(groups[1])}ポイントである。申告指標0の群との効果差は{difference['estimate']:.2f}ポイント、95%区間は{interval(difference)}ポイントとなる。",
            "results": f"学習した配分は{s['maximum_contacts']:,}人を支援する。現在のサービスに対する利益増加は評価対象の顧客1人あたり{gain['net_gain_difference'] * 1000:,.0f}円、95%信頼区間は[{gain['ci_lower'] * 1000:,.0f}, {gain['ci_upper'] * 1000:,.0f}]円となる。支援による契約継続の増加を対応費用と合わせて評価する。",
            "additional": f"継続予測は評価用標本の通常サービスを受けた{index['prediction']['observed_customers']:,}人で評価する。二乗誤差は{index['prediction']['brier_loss']:.3f}である。図は予測確率の区間ごとに、平均予測値と実際の契約継続率を示す。",
            "interpretation": f"同じ対応人数を使う解約予測に基づく配分に対し、学習した配分の利益は顧客1人あたり{advantage['net_gain_difference'] * 1000:,.0f}円高い。差の95%信頼区間は[{advantage['ci_lower'] * 1000:,.0f}, {advantage['ci_upper'] * 1000:,.0f}]円となる。顧客の反応を同じ利益単位で比較することが、対応能力1枠の価値を定める。",
            "decisions": f"学習用標本の予測利益に基づき、{selected}を採用する。継続契約の利益、顧客の反応、対応費用を同じ評価対象について結び付ける。"}
    return {
        "title": "Subscription Support and Quarterly Contribution",
        "question": "A subscription firm chooses support allocations to maximize quarterly contribution. Support reduces the effort of learning the service and raises the customer's return to renewal. Contact capacity enters the choice of which customers receive support.",
        "data": f"The fictional economy randomly assigns support across {s['customers']:,} customers. We fix {s['training_customers']:,} customers for training and {s['customers'] - s['training_customers']:,} for evaluation. Customer IDs connect prior disengagement, reported onboarding needs, support assignment and quarterly renewal.",
        "specification": f"Each customer receives support with probability {s['assignment_probability']:.1f}. Training records supply action-specific renewal predictions and policy-tree allocations. A renewed contract contributes JPY {s['renewal_contribution']:g} thousand and a contact costs JPY {s['contact_cost']:g} thousand. Predicted contribution selects an allocation within {s['maximum_contacts']:,} contacts and a JPY {s['contact_budget']:,.0f} thousand budget.",
        "table1": f"Support raises renewal by an estimated {groups[1]['renewal_effect']:.2f} percentage points among customers reporting onboarding needs; the 95% interval is {interval(groups[1])}. The direct contrast with need indicator 0 is {difference['estimate']:.2f} percentage points, with a 95% interval of {interval(difference)}.",
        "results": f"The learned allocation contacts {s['maximum_contacts']:,} customers. Its contribution gain over the existing service is JPY {gain['net_gain_difference'] * 1000:,.0f} per evaluation customer; the 95% confidence interval is [{gain['ci_lower'] * 1000:,.0f}, {gain['ci_upper'] * 1000:,.0f}]. The evaluation combines the renewal response with contact costs.",
        "additional": f"We evaluate control-service renewal predictions on {index['prediction']['observed_customers']:,} evaluation customers receiving that service. The Brier loss is {index['prediction']['brier_loss']:.3f}. The figure plots mean predictions against observed renewal rates within fixed probability bins.",
        "interpretation": f"Using the same contact capacity, the learned allocation earns JPY {advantage['net_gain_difference'] * 1000:,.0f} more per evaluation customer than risk targeting; the 95% interval is [{advantage['ci_lower'] * 1000:,.0f}, {advantage['ci_upper'] * 1000:,.0f}]. A common contribution measure connects customer response to the value of a contact slot.",
        "decisions": f"Training-predicted contribution selects {selected}. The decision combines customer response, the margin on a renewed contract and contact costs over the same evaluation cohort."}


def slide_prose(index, spec, language):
    """Connect the firm's choice, experimental evidence and saved allocation."""
    s = spec["simulation"]
    contrast = {(row["scenario"], row["comparator"]): row for row in index["uncertainty"]["pairwise_contrasts"]}
    gain = contrast["policy", "baseline"]
    difference = index["heterogeneity"]["need_group_difference"]
    equation = (r"$$\max_{a_i\in\{0,1\}}\sum_i a_i\widehat g_i,\qquad "
                + rf"\sum_i a_i\leq {s['maximum_contacts']},\quad "
                + rf"{s['contact_cost']:g}\sum_i a_i\leq {s['contact_budget']:g}.$$" )
    if language == "ja":
        return {
            "question": "利用支援は、サービスを使い続ける顧客の便益を高める。\n\n"
                + f"- 企業の目的：四半期の契約利益の最大化。\n- 選択：評価対象{s['customers'] - s['training_customers']:,}人への支援配分。\n"
                + f"- 対応能力：{s['maximum_contacts']:,}人、支援1件の費用{s['contact_cost'] * 1000:,.0f}円。",
            "data": f"架空経済で支援を確率{s['assignment_probability']:.1f}で無作為に割り当て、同じ四半期の契約更新を観測する。\n\n"
                + f"- 学習用{s['training_customers']:,}人：行動別の継続予測と配分規則の推定。\n"
                + f"- 評価用{s['customers'] - s['training_customers']:,}人：固定した配分の利益と配分間の差の推定。\n"
                + "- 事前情報：利用離れの指標、利用支援の必要性。",
            "specification": "学習した決定木が与える支援の増分利益を $\\widehat g_i$ 千円とする。\n\n"
                + equation + "\n\n契約継続の増分に契約利益を掛け、対応費用を差し引く。対応枠は、この予測増分利益に沿って配分する。",
            "table1": f"申告指標1の群の支援効果は、指標0の群を{difference['estimate']:.2f}ポイント上回る。\n\n"
                + f"差の95%信頼区間：[{difference['ci_lower']:.2f}, {difference['ci_upper']:.2f}]ポイント。事前の必要性が支援の増分価値を捉える。",
            "results": f"学習配分による四半期の利益増加は、評価対象の顧客1人あたり{gain['net_gain_difference'] * 1000:,.0f}円。\n\n"
                + "共通の対応能力と費用のもとで、支援への反応が配分の利益を決める。",
            "additional": f"通常サービスを受けた{index['prediction']['observed_customers']:,}人で継続予測を評価する。\n\n"
                + f"二乗誤差：{index['prediction']['brier_loss']:.3f}。\n\n予測確率の区間ごとに、予測平均と実際の継続率を対応させる。",
            "interpretation": prose(index, spec, language)["interpretation"],
            "decisions": "予測利益が最大の学習配分を採用する。\n\n"
                + f"- 実行規模：{s['maximum_contacts']:,}人、対応費用{s['contact_budget'] / 10:,.0f}万円。\n"
                + f"- 評価した利益増加：顧客1人・四半期あたり{gain['net_gain_difference'] * 1000:,.0f}円。\n"
                + "- 配分の根拠：支援によって増える契約継続の価値。",
        }
    return {
        "question": "Support raises the customer's return to continued use.\n\n"
            + "- Objective: maximize quarterly contract contribution.\n"
            + f"- Choice: allocate support across {s['customers'] - s['training_customers']:,} evaluation customers.\n"
            + f"- Capacity: {s['maximum_contacts']:,} contacts at JPY {s['contact_cost'] * 1000:,.0f} each.",
        "data": f"In the fictional economy, support is randomly assigned with probability {s['assignment_probability']:.1f}; renewal is observed over the same quarter.\n\n"
            + f"- Training: {s['training_customers']:,} customers for action-specific predictions and allocation rules.\n"
            + f"- Evaluation: {s['customers'] - s['training_customers']:,} customers for fixed-policy values and paired contrasts.\n"
            + "- Prior information: disengagement and reported onboarding needs.",
        "specification": "The learned policy tree assigns contact $i$ an incremental contribution of $\\widehat g_i$ thousand JPY.\n\n"
            + equation + "\n\nA contact's value combines the renewal response, the contract margin and contact cost. Predicted incremental contribution determines the allocation.",
        "table1": f"The support effect is {difference['estimate']:.2f} pp higher for need indicator 1 than 0. "
            + f"The 95% interval for this contrast is [{difference['ci_lower']:.2f}, {difference['ci_upper']:.2f}] pp.",
        "results": f"Learned allocation: JPY {gain['net_gain_difference'] * 1000:,.0f} additional contribution per evaluation customer per quarter.",
        "additional": f"Evaluate renewal predictions on {index['prediction']['observed_customers']:,} customers receiving the existing service.\n\n"
            + f"Brier loss: {index['prediction']['brier_loss']:.3f}.\n\nCompare mean predictions with observed renewal rates within fixed probability bins.",
        "interpretation": prose(index, spec, language)["interpretation"],
        "decisions": "Adopt the learned allocation selected by training-predicted contribution.\n\n"
            + f"- Scale: {s['maximum_contacts']:,} contacts; cost JPY {s['contact_budget'] / 1000:g} million.\n"
            + f"- Gain: JPY {gain['net_gain_difference'] * 1000:,.0f} per customer per quarter.\n"
            + "- Criterion: contribution induced by support.",
    }


def manuscript(root, output, entries, language, prose_sections=None, chapter_titles=None):
    """Render the English fixture or Japanese prose from saved results."""
    if language == "en":
        source = (RUNTIME / "SUBSCRIPTION_MANUSCRIPT_EN.md" if FLAT else
                  Path(__file__).resolve().parent / "manuscript-en.md")
    else:
        if prose_sections is None or chapter_titles is None:
            raise ValueError("Japanese manuscript rendering requires the saved-result prose and chapter titles")
        source = output / "manuscript-ja.md"
        chapters = [
            (chapter_titles["question"][0], prose_sections["question"]),
            (chapter_titles["specification"][0], prose_sections["specification"]),
            (chapter_titles["data"][0], prose_sections["data"]),
            (chapter_titles["results"][0], "### 学習した配分の利益\n\n"
             + prose_sections["table1"] + "\n\n" + prose_sections["results"]
             + "\n\n### 継続予測と配分判断\n\n" + prose_sections["additional"]
             + "\n\n" + prose_sections["interpretation"]),
            (chapter_titles["decisions"][0], prose_sections["decisions"]),
        ]
        text = "# " + prose_sections["title"] + "\n\n## 要旨\n\n"
        text += prose_sections["question"] + "\n\n" + prose_sections["results"] + "\n\n"
        text += "\n\n".join("## " + title + "\n\n" + body for title, body in chapters) + "\n"
        source.write_text(text, encoding="utf-8")
    text = source.read_text(encoding="utf-8")
    abstract_heading = "要旨" if language == "ja" else "Abstract"
    public = text.partition("## " + abstract_heading + "\n")[2]
    parts = re.split(r"^## (.+)\n", public, flags=re.MULTILINE)
    if len(parts) != 11:
        raise ValueError("The example manuscript must contain its abstract and five complete paper sections")
    bundle = output / "manuscript"
    meetings.create_bundle(root, bundle, entries, title=text.splitlines()[0].removeprefix("# "),
                           kind="manuscript", project_view={"language": language, "abstract": parts[0].strip()})
    names = ["introduction", "model", "design", "results", "conclusion"]
    for i, name in enumerate(names):
        body = re.sub(r"^### ", "## ", parts[2 + 2 * i].strip(), flags=re.MULTILINE)
        if name == "results":
            anchors = (["学習した配分の利益", "継続予測と配分判断"] if language == "ja" else
                       ["The value of the learned allocation", "Renewal prediction and the allocation decision"])
            for entry, anchor in zip(entries[:2], anchors):
                marker = "## " + anchor
                if body.count(marker) != 1:
                    raise ValueError("The complete Results chapter must retain its exhibit anchor: " + anchor)
                table = meetings.table_markdown(entry) + "\n\n: " + meetings.artifact_public_text(entry)
                body = body.replace(marker, table + "\n\n" + marker, 1)
        meetings.change_sections(bundle, expected_revision=meetings.load_meeting(bundle)[2],
            add={"id": "paper-" + name, "title": parts[1 + 2 * i].strip(), "body": body})
    meetings.edit_section(bundle, "paper-results", {"artifacts": [entries[2]["id"]]},
                          expected_revision=meetings.load_meeting(bundle)[2])
    for number in range(1, len(entries) + 1):
        meetings.edit_section(bundle, "result-" + str(number), {"visible": False},
                              expected_revision=meetings.load_meeting(bundle)[2])
    current = meetings.load_meeting(bundle)[0]
    order = ["paper-introduction", "paper-model", "paper-design", "paper-results", "paper-conclusion"]
    order.extend(section["id"] for section in current["sections"] if section["id"] not in order)
    meetings.change_sections(bundle, expected_revision=meetings.load_meeting(bundle)[2], order=order)
    return reference(root, source)


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
             "public_claims": ["評価対象4,000人。契約継続率の変化・ポイント。95%信頼区間。" if ja else "4,000 evaluation customers. Renewal effects in percentage points. 95% confidence intervals."],
             "internal": {"inference": spec["inference"], "source_key": "heterogeneity.rows"}},
         "display": {"plot_type": "table", "column_order": effect_keys,
             "formats": {key: ".0f" if key == "customers" else ".2f" for key in effect_keys[1:]}}},
        {"id": "subscription-policy-gains", "title": "支援配分による利益の増加" if ja else "Contribution gains from support allocation",
         "kind": "descriptive", "result_ids": ["subscription"],
         "rows": [{"comparison": contrast_names[j][not ja], **{key: row[key] for key in gain_keys[1:]}} for j, row in enumerate(contrasts)],
         "columns": [{"key": key, "label": label, "unit": ""} for key, label in zip(gain_keys, gain_labels)],
         "metadata": {"report_role": "main", "unit": spec["unit"],
             "public_claims": ["評価対象の顧客1人あたり・四半期・千円。95%信頼区間。" if ja else "Thousand JPY per evaluation customer per quarter. 95% confidence intervals."],
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
             "internal": {"bin_closure": index["prediction"]["calibration_bin_closure"], "source_key": "prediction.calibration"}},
         "display": {"plot_type": "line", "x": "predicted", "y": "observed", "style": "presentation", "title": "",
             "x_label": "平均予測確率" if ja else "Mean prediction",
             "y_label": "契約継続率" if ja else "Renewal rate", "width": 720, "height": 600,
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
    body = prose(index, spec, language)
    titles = {"question": ("利用支援と企業の配分問題", "Support and the firm's allocation problem"),
        "data": ("支援の無作為割当と契約更新", "Randomized support and contract renewal"),
        "specification": ("顧客の反応と支援の増分利益", "Customer response and incremental contribution"),
        "table1": ("事前の必要性と支援への反応", "Prior need and response to support"),
        "results": ("800人への支援配分が生む利益", "Contribution from 800 support contacts"),
        "additional": ("契約継続の予測と観測", "Predicted and observed renewal"),
        "interpretation": ("対応能力1枠の価値", "The value of a contact slot"),
        "decisions": ("支援配分の選択と実行規模", "Selected allocation and implementation")}
    for kind in ("brief", "results"):
        sections = slide_prose(index, spec, language)
        if kind == "brief":
            sections = {key: body[key] for key in ("question", "data", "specification", "table1", "results")}
            sections["interpretation"] = body["interpretation"] + "\n\n" + body["decisions"]
        view = {"language": language, "section_content": sections}
        save(output / (kind + "-view.json"), view)
        bundle = output / kind
        meetings.create_bundle(root, bundle, entries[:2] if kind == "brief" else entries,
                               title=body["title"], kind=kind, project_view=view)
        for section in sections:
            meetings.edit_section(bundle, section, {"title": titles[section][not ja]}, expected_revision=meetings.load_meeting(bundle)[2])
        # Each displayed comparison carries its own economic interpretation.
        for source, exhibit in (("table1", "result-1"), ("results", "result-2"), ("additional", "result-3")):
            if source in sections:
                meetings.edit_section(bundle, exhibit,
                    {"title": titles[source][not ja], "layout": "figure-left" if source == "additional" else "stack"},
                    body=sections[source], expected_revision=meetings.load_meeting(bundle)[2])
                meetings.edit_section(bundle, source, {"visible": False}, expected_revision=meetings.load_meeting(bundle)[2])
        if kind == "results":
            meetings.edit_section(bundle, "interpretation", {"visible": False}, expected_revision=meetings.load_meeting(bundle)[2])
    paper_entry = artifacts.gallery_items(root, registry_path, item_ids=[paper_calibration["id"]])[0]
    paper_entry["title"] = paper_calibration["title"]
    paper_entry["public_text"] = []
    source = manuscript(root, output, [*entries[:2], paper_entry], language,
                        prose_sections=body, chapter_titles=titles)
    save(output / "material-inputs.json", {"result_index": reference(root, run / "result-index.json"), "manuscript_source": source,
        "producer": reference(root, Path(__file__)), "language": language, "analysis_executed": False})
    return {"output": str(output), "bundles": ["brief", "results", "manuscript"], "analysis_executed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--language", choices=("ja", "en"), default="ja")
    args = parser.parse_args()
    print(json.dumps(build(args.root.resolve(strict=True), args.run.resolve(strict=True), args.output.resolve(), args.language), ensure_ascii=False))
