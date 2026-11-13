#!/usr/bin/env python3
"""Edit and render portable meeting sources from explicitly selected saved results.

The render and Google Slides paths use only this module, the meeting bundle and
the document renderer. They never import the analysis runner or open raw data.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import quote, urlsplit


SECTION = re.compile(r"^<!-- section:([A-Za-z][A-Za-z0-9_-]*) -->\s*$", re.MULTILINE)
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
LAYOUTS = {"stack", "figure-left", "figure-right", "figures"}
TABLE_KINDS = {"table", "table1", "regression", "regression_table", "descriptive",
               "descriptive_table", "sample_composition", "balance", "sample-flow"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_text(path, text):
    """Publish one edited source or completed document with an atomic rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(text)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def bundled_path(bundle, relative):
    path = Path(relative)
    root = Path(bundle).resolve()
    if path.is_absolute() or ".." in path.parts or path.parts[:1] != ("assets",):
        raise ValueError("Meeting assets must be stored inside assets/: " + str(relative))
    target = root / path
    if not target.resolve().is_relative_to(root) or target.is_symlink():
        raise ValueError("Meeting asset escapes its bundle: " + str(relative))
    return target


def load_meeting(bundle):
    bundle = Path(bundle)
    specification = (bundle / "meeting.json").read_bytes()
    manuscript = (bundle / "content.md").read_bytes()
    meeting = json.loads(specification)
    if meeting.get("schema") != "ers-meeting-v1":
        raise ValueError("Expected an ers-meeting-v1 source")
    if meeting.get("document_type", "slides") not in {"slides", "article"}:
        raise ValueError("document_type must be slides or article")
    export_formats(meeting)
    sections = meeting.get("sections", [])
    identities = [row["id"] for row in sections]
    if len(set(identities)) != len(identities) or any(not NAME.fullmatch(key) for key in identities):
        raise ValueError("Section IDs must be distinct simple names")
    bodies = split_content(manuscript.decode("utf-8"))
    for section in sections:
        if section.get("layout", "stack") not in LAYOUTS:
            raise ValueError("Unknown section layout: " + str(section.get("layout")))
        if section["id"] not in bodies:
            raise ValueError("Missing content section: " + section["id"])
        for artifact_id in section.get("artifacts", []):
            if artifact_id not in meeting.get("artifacts", {}):
                raise ValueError("Unknown selected artifact: " + artifact_id)
    revision = hashlib.sha256(specification + b"\0" + manuscript).hexdigest()
    return meeting, bodies, revision


def export_formats(meeting):
    formats = meeting.get("cloud_formats", ["html"])
    if (not isinstance(formats, list) or not formats or
            any(value not in ("html", "pdf", "markdown") for value in formats) or
            len(set(formats)) != len(formats)):
        raise ValueError("cloud_formats must select distinct html, pdf or markdown outputs")
    return formats


def split_content(markdown):
    matches = list(SECTION.finditer(markdown))
    bodies = {}
    for index, match in enumerate(matches):
        key = match.group(1)
        if key in bodies:
            raise ValueError("Duplicate Markdown section: " + key)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        bodies[key] = markdown[match.end():end].strip()
    return bodies


def content_text(sections, bodies):
    return "\n\n".join("<!-- section:" + row["id"] + " -->\n\n" + bodies.get(row["id"], "")
                        for row in sections) + "\n"


def replace_section_body(markdown, section_id, body):
    """Replace one section, retaining the other sections and removed drafts."""
    if not isinstance(body, str) or SECTION.search(body):
        raise ValueError("Section prose must be text without structural section markers")
    matches = list(SECTION.finditer(markdown))
    for index, match in enumerate(matches):
        if match.group(1) == section_id:
            end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
            return markdown[:match.end()] + body.rstrip() + "\n\n" + markdown[end:]
    separator = "" if not markdown or markdown.endswith("\n\n") else "\n\n"
    return markdown + separator + "<!-- section:" + section_id + " -->\n\n" + body.rstrip() + "\n"


def template_path(root, name, family="slides"):
    root = Path(root)
    candidates = [root / "tex" / family / name, root / ".agents/tex" / family / name,
                  Path(__file__).resolve().parent.parent / "tex" / family / name,
                  Path(__file__).resolve().parent / name]
    if name == "pandoc_template.latex":
        candidates.append(Path(__file__).resolve().parent / (family + "_pandoc_template.latex"))
    return next((path for path in candidates if path.is_file()), None)


def task_lines(tasks):
    lines = []
    for task in tasks:
        title = task.get("title") or task.get("name") or task.get("id", "")
        url = task.get("url") or task.get("html_url") or task.get("issue_url")
        label = "[" + title + "](" + url + ")" if url else title
        owners = task.get("assignees", task.get("owner", []))
        if isinstance(owners, str):
            owners = [owners]
        owners = [item.get("login", "") if isinstance(item, dict) else str(item) for item in owners]
        details = [", ".join(owners), task.get("due_date") or task.get("due") or ""]
        stage = task.get("publication_stage")
        if stage is not None and stage != "":
            details.append("投稿段階: " + str(stage))
        lines.append("- " + label + (" — " + " / ".join(str(x) for x in details if x) if any(details) else ""))
    return "\n".join(lines)


def summary_lines(values):
    if isinstance(values, str):
        return values
    if isinstance(values, dict):
        values = [values]
    lines = []
    for item in values or []:
        if isinstance(item, str):
            text = item
        else:
            value = item.get("value", item)
            text = str(value.get("text") or value.get("choice") or value.get("title") or value.get("summary") or "")
            if value.get("reason"):
                text += " — " + str(value["reason"])
        if text:
            lines.append("- " + text)
    return "\n".join(lines)


def create_bundle(root, output, entries, *, title, kind="meeting", project_view=None,
                  previous=None, date="", issue_url="", github_source=""):
    """Copy an explicit exhibit selection into an independently editable edition."""
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Choose a new meeting directory; previous editions are retained")
    templates = template_path(root, "meeting_templates.json")
    if templates is None:
        raise ValueError("Missing tex/slides/meeting_templates.json")
    formats = read_json(templates)
    if kind not in formats:
        raise ValueError("Unknown meeting template: " + kind)
    view = project_view or {}
    prior, prior_bodies, _ = load_meeting(previous) if previous else ({}, {}, "")
    prior_tasks = {row.get("url", row.get("id")): row for row in prior.get("task_snapshot", [])}
    completed = [row for row in view.get("completed", [])
                 if prior_tasks.get(row.get("url", row.get("id")), {}).get("state") != "closed"]
    sections = copy.deepcopy(formats[kind]["sections"])
    bodies = {section["id"]: "" for section in sections}
    bodies.update({
        "previous": summary_lines(prior_bodies.get("decisions", "")),
        "previous-todos": prior_bodies.get("next") or task_lines(prior.get("next_actions", [])),
        "completed": task_lines(completed),
        "active": task_lines(view.get("active", view.get("in_progress", []))),
        "next": task_lines(view.get("next", view.get("next_actions", []))),
        "question": str(view.get("research_question", view.get("central_question", ""))),
        "plan": summary_lines(view.get("plan", [])),
        "data": summary_lines(view.get("data_description", [])),
        "specification": summary_lines(view.get("specification_description", [])),
        "results": summary_lines(view.get("results_summary", [])),
    })
    section_content = view.get("section_content", {})
    if (not isinstance(section_content, dict) or
            any(not isinstance(value, str) for value in section_content.values())):
        raise ValueError("section_content must map template section IDs to adopted Markdown text")
    if set(section_content) - {section["id"] for section in sections}:
        raise ValueError("section_content contains a section outside the selected template")
    bodies.update(section_content)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".meeting-", dir=output.parent) as temporary:
        stage = Path(temporary) / "bundle"
        (stage / "assets").mkdir(parents=True)
        artifacts = {}
        for index, entry in enumerate(entries):
            artifact_public_text(entry)
            identity = str(entry["id"])
            if identity in artifacts:
                raise ValueError("Duplicate selected artifact: " + identity)
            exported = {key: copy.deepcopy(entry[key]) for key in
                        ("id", "title", "kind", "plot_type", "metadata", "provenance", "rows", "columns",
                         "interpretation", "findings", "issues", "adoption_decision", "status", "links",
                         "display", "result_ids", "source_reference", "presentation", "public_text", "row_indices") if key in entry}
            if "columns" in exported:
                exported["columns"] = [{"key": column, "label": column} if isinstance(column, str) else column
                                       for column in exported["columns"]]
            exported["files"] = {}
            for file_index, relative in enumerate(entry.get("files", [])):
                role = str(file_index + 1)
                source = (root / relative).resolve()
                if not source.is_relative_to(root) or not source.is_file():
                    raise ValueError("Selected exhibit is outside the project or absent: " + str(relative))
                if source.suffix.lower() not in {".svg", ".png", ".jpg", ".jpeg", ".pdf", ".md", ".html"}:
                    continue
                name = "assets/exhibit-" + str(index + 1) + "-" + re.sub(r"[^A-Za-z0-9_-]", "_", role) + source.suffix
                raw = source.read_bytes()
                (stage / name).write_bytes(raw)
                exported["files"][role] = name
                exported.setdefault("content_versions", {})[role] = hashlib.sha256(raw).hexdigest()
            artifacts[identity] = exported
        slots = {section["artifact_role"]: section["id"] for section in sections if "artifact_role" in section}
        default_slot = "exhibits" if any(row["id"] == "exhibits" for row in sections) else "results"
        placements = {}
        for index, entry in enumerate(entries):
            metadata = entry.get("metadata", {})
            role = metadata.get("report_role")
            if role is None:
                if entry.get("kind") in {"descriptive", "sample_composition", "group_comparison"}:
                    role = "descriptive"
                elif entry.get("kind") == "event_study":
                    role = "event_study"
                elif entry.get("kind") in {"robustness", "alternative_specification"}:
                    role = "additional"
                else:
                    role = "main"
            placements.setdefault(slots.get(role, default_slot), []).append((index, entry))
        arranged = []
        for section in sections:
            selected = placements.pop(section["id"], [])
            # Retain authored summary text before its exhibits.
            if not selected or bodies.get(section["id"]):
                arranged.append(section)
            for index, entry in selected:
                sid = "result-" + str(index + 1)
                arranged.append({"id": sid, "title": entry.get("title", entry["id"]),
                                 "visible": True, "layout": "stack", "artifacts": [entry["id"]],
                                 "caption": "", "speaker_notes": "", "source_section": section["id"]})
                bodies[sid] = ""
        if placements:
            raise ValueError("Template needs an exhibit section for selected saved results")
        sections = arranged
        for section in sections:
            section.setdefault("visible", bool(bodies.get(section["id"])) or bool(section.get("artifacts")))
            section.setdefault("layout", "stack")
            section.setdefault("artifacts", [])
            section.setdefault("caption", "")
            section.setdefault("speaker_notes", "")
        meeting = {"schema": "ers-meeting-v1", "title": title, "date": date, "kind": kind,
                   "abstract": str(view.get("abstract", "")),
                   "language": view.get("language", "ja"),
                   "document_type": formats[kind].get("document_type", "slides"),
                   "issue_url": issue_url, "github_source": github_source, "cloud_export": False,
                   "cloud_formats": ["html", "pdf"],
                   "previous": {"title": prior.get("title", ""), "issue_url": prior.get("issue_url", "")},
                   "sections": sections, "artifacts": artifacts,
                   "decisions": copy.deepcopy(view.get("adopted_decisions", [])),
                   "next_actions": copy.deepcopy(view.get("next", view.get("next_actions", []))),
                   "task_snapshot": copy.deepcopy(view.get("tasks", [])),
                   "task_source": copy.deepcopy(view.get("github", {})),
                   "internal": {field: copy.deepcopy(view[field]) for field in
                                ("findings", "interpretations", "open_decisions") if field in view},
                   "editions": []}
        write_json(stage / "meeting.json", meeting)
        write_text(stage / "content.md", content_text(sections, bodies))
        os.replace(stage, output)
    return {"bundle": str(output), "sections": len(sections), "artifacts": len(entries),
            "source_revision": load_meeting(output)[2]}


def edit_section(bundle, section_id, changes, *, expected_revision, body=None):
    meeting, bodies, revision = load_meeting(bundle)
    if revision != expected_revision:
        raise ValueError("Meeting sources changed; reload the current edition before saving")
    permitted = {"title", "visible", "layout", "artifacts", "caption", "speaker_notes"}
    if set(changes) - permitted:
        raise ValueError("Section edit contains a non-display field")
    section = next((row for row in meeting["sections"] if row["id"] == section_id), None)
    if section is None:
        raise ValueError("Unknown section: " + section_id)
    section.update(changes)
    if section.get("layout", "stack") not in LAYOUTS:
        raise ValueError("Unknown section layout")
    if any(identity not in meeting["artifacts"] for identity in section.get("artifacts", [])):
        raise ValueError("Section references an exhibit outside this saved bundle")
    if body is not None:
        content_path = Path(bundle) / "content.md"
        markdown = content_path.read_text(encoding="utf-8")
        write_text(content_path, replace_section_body(markdown, section_id, body))
    write_json(Path(bundle) / "meeting.json", meeting)
    return {"source_revision": load_meeting(bundle)[2], "analysis_executed": False}


def fold_into_exhibit(bundle, source_id, exhibit_id, *, layout="stack"):
    """Move a prose section onto the exhibit it explains and hide the prose-only page.

    The exhibit page takes the prose section's heading and body, so the claim and
    its table or figure share one page.
    """
    meeting, bodies, revision = load_meeting(bundle)
    source = next((row for row in meeting["sections"] if row["id"] == source_id), None)
    if source is None:
        raise ValueError("Unknown section: " + source_id)
    edit_section(bundle, exhibit_id, {"title": source["title"], "layout": layout},
                 body=bodies.get(source_id, ""), expected_revision=revision)
    edit_section(bundle, source_id, {"visible": False}, expected_revision=load_meeting(bundle)[2])


def change_sections(bundle, *, expected_revision, order=None, add=None, remove=None):
    meeting, bodies, revision = load_meeting(bundle)
    if revision != expected_revision:
        raise ValueError("Meeting sources changed; reload before saving")
    sections = meeting["sections"]
    if add:
        if not NAME.fullmatch(add["id"]) or any(row["id"] == add["id"] for row in sections):
            raise ValueError("New section needs a distinct simple ID")
        sections.append({"id": add["id"], "title": add.get("title", ""), "visible": True,
                         "layout": "stack", "artifacts": [], "caption": "", "speaker_notes": ""})
        bodies[add["id"]] = add.get("body", bodies.get(add["id"], ""))
    if remove:
        if not any(row["id"] == remove for row in sections):
            raise ValueError("Unknown removed section: " + remove)
        sections[:] = [row for row in sections if row["id"] != remove]
        bodies.pop(remove, None)
    if order is not None:
        by_id = {row["id"]: row for row in sections}
        if len(order) != len(by_id) or set(order) != set(by_id):
            raise ValueError("Order must contain every section ID exactly once")
        sections[:] = [by_id[key] for key in order]
    # Removed sections retain their draft text; reordering changes only the
    # structure. Adding text first keeps the current structure readable.
    if add:
        existing_text = (Path(bundle) / "content.md").read_text(encoding="utf-8")
        write_text(Path(bundle) / "content.md",
                   replace_section_body(existing_text, add["id"], bodies[add["id"]]))
    write_json(Path(bundle) / "meeting.json", meeting)
    return {"source_revision": load_meeting(bundle)[2], "analysis_executed": False}


def artifact_public_text(entry):
    """Consume the Gallery's explicit public projection; retain metadata in the bundle."""
    parts = entry.get("public_text", [])
    if not isinstance(parts, list) or any(not isinstance(text, str) or not text.strip() for text in parts):
        raise ValueError("public_text must contain the selected Gallery's public propositions")
    return "\n\n".join(parts)


def is_table(entry):
    plot_type = entry.get("display", {}).get("plot_type", entry.get("plot_type"))
    return plot_type == "table" if plot_type else entry.get("kind") in TABLE_KINDS


def table_cells(entry):
    """Use the selected saved table presentation in document and native Slides exports."""
    presentation = entry.get("presentation")
    if presentation:
        headers = []
        for row in presentation["headers"]:
            headers.append([value for cell in row for value in
                            [cell["text"], *([""] * (cell.get("colspan", 1) - 1))]])
        width = len(headers[-1]) if headers else 0
        rows = []
        for row in [*presentation["body"], *presentation.get("footer", [])]:
            values = [row.get("label", ""), *row.get("cells", [])]
            if row.get("kind") == "panel":
                values.extend([""] * (width - len(values)))
            if len(values) != width:
                raise ValueError("Saved table presentation width differs from its header")
            rows.append(values)
        return headers, rows
    rows = entry.get("rows", [])
    definitions = entry.get("columns") or ([{"key": key, "label": key} for key in rows[0]] if rows else [])
    columns = [item["key"] for item in definitions]
    if not columns:
        return [], []
    display = entry.get("display", {})
    def cell(value, key=None):
        if type(value) in (int, float) and key in display.get("formats", {}):
            value = format(value, display["formats"][key])
        return str(value if value is not None else "—")
    labels = {item["key"]: display.get("column_labels", {}).get(item["key"], item.get("label", item["key"])) +
              (" (" + item["unit"] + ")" if item.get("unit") else "") for item in definitions}
    labels.update(display.get("labels", {}))
    return [[cell(labels.get(key, key)) for key in columns]], [[cell(row.get(key, ""), key) for key in columns] for row in rows]


def table_markdown(entry):
    headers, rows = table_cells(entry)
    if not headers:
        return ""
    def line(values):
        return "| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in values) + " |"
    return "\n".join([line(headers[0]), line(["---", *(["---:"] * (len(headers[0]) - 1))]),
                      *(line(row) for row in [*headers[1:], *rows])])


def exhibit_markdown(entry, output_format="html", *, slides=False, caption=""):
    files = entry.get("files", {})
    extensions = (".pdf", ".png", ".jpg", ".jpeg", ".svg") if output_format == "pdf" else (".png", ".jpg", ".jpeg", ".svg")
    image = next((value for extension in extensions for value in files.values() if Path(value).suffix.lower() == extension), None)
    notes = artifact_public_text(entry)
    if output_format == "pdf" and caption:
        notes = (notes.rstrip("。") + "。" if notes else "") + caption
    if is_table(entry) and entry.get("rows"):
        content = table_markdown(entry)
        if output_format == "pdf" and notes:
            return content + "\n\n: " + notes
    elif image:
        caption = entry.get("title", "")
        if output_format == "pdf" and notes:
            caption += ". " + notes
        size = (" height=3in" if len(caption) > 500 else " height=4.25in") if output_format == "pdf" and slides else ""
        content = "![" + caption.replace("[", "\\[").replace("]", "\\]") + "](" + image + "){fig-alt=" + json.dumps(entry.get("title", ""), ensure_ascii=False) + size + "}"
        if output_format == "pdf":
            return content
    else:
        content = table_markdown(entry)
    return content + ("\n\n" + notes if notes else "")


def document_source(root, meeting, bodies, output_format="html"):
    template = template_path(root, "meeting_template.qmd")
    if template is None:
        raise ValueError("Missing tex/slides/meeting_template.qmd")
    slides = []
    article = meeting.get("document_type") == "article"
    for section in meeting["sections"]:
        if not section.get("visible", True):
            continue
        body = bodies[section["id"]]
        for text in (body, section.get("caption", ""), section.get("speaker_notes", "")):
            if "{{<" in text or re.search(r"!\s*\[", text):
                raise ValueError("Select saved figures through section.artifacts; body text cannot include files or Quarto shortcodes")
        selected = section.get("artifacts", [])
        exhibit_parts = [exhibit_markdown(meeting["artifacts"][key], output_format, slides=not article,
                         caption=section.get("caption", "") if index == len(selected) - 1 else "")
                         for index, key in enumerate(selected)]
        exhibits = "\n\n".join(exhibit_parts)
        layout = section.get("layout", "stack")
        if layout in {"figure-left", "figure-right"} and exhibits:
            first, second = (exhibits, body) if layout == "figure-left" else (body, exhibits)
            content = ":::: {.columns}\n::: {.column width=\"52%\"}\n" + first + "\n:::\n::: {.column width=\"48%\"}\n" + second + "\n:::\n::::"
        elif layout == "figures" and exhibit_parts:
            width = str(100 / len(exhibit_parts))
            columns = "\n\n".join('::: {.column width="' + width + '%"}\n' + part + "\n:::" for part in exhibit_parts)
            content = (body + "\n\n" if body else "") + ":::: {.columns}\n" + columns + "\n::::"
        else:
            content = "\n\n".join(part for part in (body, exhibits) if part)
        if section.get("caption") and not (output_format == "pdf" and exhibit_parts):
            content += "\n\n::: {.exhibit-note}\n" + section["caption"] + "\n:::"
        if section.get("speaker_notes") and not article:
            content += "\n\n::: {.notes}\n" + section["speaker_notes"] + "\n:::"
        heading = "# " if article else "## "
        section_text = heading + section["title"].replace("\n", " ") + " {#" + section["id"] + "}\n\n" + content
        if article and output_format == "pdf" and len(selected) == 1:
            entry = meeting["artifacts"][selected[0]]
            headers, rows = table_cells(entry)
            if is_table(entry) and headers:
                # Keep a short table, its heading and definition together. Larger
                # tables retain longtable's ordinary page continuation.
                cell_width = max(12, 85 // len(headers[0]))
                lines = sum(max((len(str(cell)) + cell_width - 1) // cell_width for cell in row)
                            for row in [*headers, *rows])
                lines += (len(artifact_public_text(entry)) + len(body) + 84) // 85
                if lines <= 28:
                    section_text = "```{=latex}\n\\begin{minipage}{\\linewidth}\n```\n\n" + section_text + "\n\n```{=latex}\n\\end{minipage}\n```"
        slides.append(section_text)
    substitutions = {"title": json.dumps(meeting["title"], ensure_ascii=False),
                     "abstract": json.dumps(meeting.get("abstract", ""), ensure_ascii=False),
                     "date": json.dumps(meeting.get("date", ""), ensure_ascii=False),
                     "language": json.dumps(meeting.get("language", "ja"), ensure_ascii=False),
                     "body": "\n\n".join(slides)}
    return re.sub(r"\{\{(title|abstract|date|language|body)\}\}", lambda match: substitutions[match.group(1)], template.read_text(encoding="utf-8"))


def preview_markdown(bundle, *, asset_base_url=""):
    """Render the complete visible deck as a GitHub/browser Markdown preview."""
    meeting, bodies, revision = load_meeting(bundle)
    output = ["# " + meeting["title"], meeting.get("date", "")]
    for section in meeting["sections"]:
        if not section.get("visible", True):
            continue
        output.extend(["## " + section["title"], bodies[section["id"]]])
        for key in section.get("artifacts", []):
            entry = meeting["artifacts"][key]
            picture = next((path for path in entry.get("files", {}).values()
                            if Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".svg"}), None)
            if is_table(entry) or not picture:
                output.append(table_markdown(entry))
            else:
                url = asset_base_url.rstrip("/") + "/" + quote(picture, safe="/") if asset_base_url else picture
                output.append("![" + entry.get("title", key).replace("]", "\\]") + "](" + url + ")")
            output.append(artifact_public_text(entry))
        output.append(section.get("caption", ""))
    if meeting.get("issue_url"):
        output.append("[関連 Issue](" + meeting["issue_url"] + ")")
    output.append("資料の版: `" + revision[:12] + "`")
    return "\n\n".join(str(part) for part in output if part) + "\n"


def render_bundle(root, bundle, output, *, quarto="quarto", output_format="html"):
    root, bundle, output = Path(root).resolve(), Path(bundle).resolve(), Path(output).resolve()
    meeting, bodies, revision = load_meeting(bundle)
    if output.exists():
        raise ValueError("Choose a new render directory; completed editions are retained")
    source = document_source(root, meeting, bodies, output_format)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ers-meeting-render-", dir=output.parent) as temporary:
        stage = Path(temporary)
        if meeting.get("document_type") == "article" and output_format == "pdf":
            # econsocart defines none of the caption names Babel's language setup reads; luatexja-fontspec
            # sets the Japanese text, so the PDF article omits the Babel language.
            source = re.sub(r"^lang:.*\n", "", source, count=1, flags=re.MULTILINE)
            if str(meeting.get("language", "ja")).startswith("ja") and source.startswith("---\n"):
                source = "---\njapanese: true\n" + source[4:]
        (stage / "index.qmd").write_text(source, encoding="utf-8")
        # An isolated document root prevents repository render hooks and engines
        # from participating in a saved-exhibit render.
        (stage / "_quarto.yml").write_text("project:\n  type: default\nengine: markdown\nexecute:\n  enabled: false\n  freeze: true\n", encoding="utf-8")
        consumed = set()
        asset_versions = {}
        for section in meeting["sections"]:
            if not section.get("visible", True):
                continue
            for key in section.get("artifacts", []):
                entry = meeting["artifacts"][key]
                for role, relative in entry.get("files", {}).items():
                    if relative in consumed or "(" + relative + ")" not in source:
                        continue
                    source_asset = bundled_path(bundle, relative)
                    asset_version = hashlib.sha256(source_asset.read_bytes()).hexdigest()
                    expected = entry.get("content_versions", {}).get(role)
                    if expected and expected != asset_version:
                        raise ValueError("Saved exhibit changed; select its current display version: " + relative)
                    target = stage / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source_asset, target)
                    consumed.add(relative)
                    asset_versions[relative] = asset_version
        article = meeting.get("document_type") == "article"
        target_format = {"html": "html" if article else "revealjs", "pdf": "pdf" if article else "beamer", "markdown": "gfm"}[output_format]
        command = [quarto, "render", "index.qmd", "--to", target_format, "--no-execute"]
        templates = [template_path(root, "meeting_template.qmd")]
        if output_format == "html" and not article:
            # Quarto's legacy Reveal template registers the MathJax 2 plugin
            # while supplying its MathJax 3 loader. Keep the installed template
            # and its partials, selecting Reveal's official MathJax 3 interface.
            resource_root = Path(subprocess.run([quarto, "--paths"], check=True,
                                 capture_output=True, text=True).stdout.splitlines()[-1])
            reveal_template = resource_root / "formats/revealjs/pandoc/template.html"
            reveal_source = reveal_template.read_text(encoding="utf-8")
            if re.search(r"\bRevealMath\s*,", reveal_source):
                reveal_source = re.sub(r"\n        math: \{.*?\n        \},",
                    "\n        mathjax3: {\n          mathjax: '$mathjaxurl$',\n        },",
                    reveal_source, flags=re.DOTALL)
                reveal_source = re.sub(r"\bRevealMath\s*,", "RevealMath.MathJax3,", reveal_source)
                adapter = stage / "revealjs-mathjax3.html"
                adapter.write_text(reveal_source, encoding="utf-8")
                templates.append(reveal_template)
                for name in ("title-slide.html", "toc-slide.html"):
                    partial = reveal_template.with_name(name)
                    shutil.copyfile(partial, stage / name)
                    templates.append(partial)
                command += ["--template", str(adapter)]
        if output_format == "pdf":
            family = "paper" if article else "slides"
            adapter = template_path(root, "pandoc_template.latex", family)
            if adapter is None:
                raise ValueError("Missing existing " + family + "/pandoc_template.latex")
            command += ["--template", str(adapter), "--pdf-engine", "lualatex"]
            templates.append(adapter)
            if article:
                for name in ("econsocart.cls", "econsocart.cfg", "ecta-fullname.bst"):
                    source_style = template_path(root, name, "paper")
                    if source_style is None:
                        raise ValueError("Missing existing Econometrica style: " + name)
                    shutil.copyfile(source_style, stage / name)
                    templates.append(source_style)
        rendered = subprocess.run(command, cwd=stage, capture_output=True, text=True)
        if rendered.returncode:
            log = stage / "index.log"
            detail = "\n" + "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]) if log.is_file() else ""
            raise RuntimeError("Quarto render failed:\n" + rendered.stdout + rendered.stderr + detail)
        extension = {"html": "html", "pdf": "pdf", "markdown": "md"}[output_format]
        completed = stage / ("index." + extension)
        if not completed.is_file():
            raise ValueError("Document renderer did not return its declared output")
        published = stage / "completed"
        published.mkdir()
        shutil.copyfile(completed, published / completed.name)
        latex_files = {}
        if output_format == "pdf":
            latex_names = ["index.tex"] + (["econsocart.cls", "econsocart.cfg", "ecta-fullname.bst"] if article else [])
            for name in latex_names:
                source_file = stage / name
                latex_files[name] = hashlib.sha256(source_file.read_bytes()).hexdigest()
        if output_format == "markdown" and (stage / "assets").exists():
            shutil.copytree(stage / "assets", published / "assets")
        record = {"source_revision": revision, "format": output_format, "command": command,
                  "artifact": completed.name, "artifact_sha256": hashlib.sha256(completed.read_bytes()).hexdigest(),
                  "consumed_assets": sorted(consumed), "asset_versions": asset_versions,
                  "latex_files": latex_files,
                  "template_versions": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in templates},
                  "analysis_executed": False,
                  "renderer": subprocess.run([quarto, "--version"], check=True, capture_output=True, text=True).stdout.strip()}
        write_json(published / "render.json", record)
        os.replace(published, output)
    return record


def register_edition(bundle, url, *, kind, expected_revision, source_revision=None):
    meeting, _, revision = load_meeting(bundle)
    if revision != expected_revision:
        raise ValueError("Meeting sources changed; reload before linking an edition")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Edition needs its returned HTTPS URL")
    if any(row["url"] == url for row in meeting.get("editions", [])):
        return {"url": url, "status": "already-linked"}
    meeting.setdefault("editions", []).append({"kind": kind, "url": url, "source_revision": source_revision or revision})
    write_json(Path(bundle) / "meeting.json", meeting)
    return {"url": url, "source_revision": load_meeting(bundle)[2]}


def native_slides_requests(bundle, *, asset_base_url=None):
    """Return native Google Slides operations for a newly created independent deck."""
    import math
    import unicodedata

    meeting, bodies, revision = load_meeting(bundle)
    requests, notes, images = [], {}, []
    prefix = "ers_" + revision[:12] + "_"
    body_size = 28

    def text_height(text, width, size):
        if not text:
            return 0
        lines = 0
        for line in text.splitlines():
            units = sum(1 if unicodedata.east_asian_width(char) in {"W", "F"} else 0.55 for char in line)
            lines += max(1, math.ceil(units * size / (width - 16)))
        return lines * size * 1.25 + 10

    def box(page, name, text, x, y, width, height, size, color=None):
        if not text:
            return None
        identity = prefix + name
        requests.append({"createShape": {"objectId": identity, "shapeType": "TEXT_BOX", "elementProperties": {
            "pageObjectId": page, "size": {"width": {"magnitude": width, "unit": "PT"}, "height": {"magnitude": height, "unit": "PT"}},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "PT"}}}})
        if text:
            requests.append({"insertText": {"objectId": identity, "text": text}})
            style = {"fontFamily": "Noto Sans JP", "fontSize": {"magnitude": size, "unit": "PT"}}
            if color:
                style["foregroundColor"] = {"opaqueColor": {"rgbColor": color}}
            requests.append({"updateTextStyle": {"objectId": identity, "textRange": {"type": "ALL"}, "style": style, "fields": ",".join(style)}})
            requests.append({"updateParagraphStyle": {"objectId": identity, "textRange": {"type": "ALL"},
                "style": {"lineSpacing": 110, "spaceAbove": {"magnitude": 0, "unit": "PT"}, "spaceBelow": {"magnitude": 5, "unit": "PT"}},
                "fields": "lineSpacing,spaceAbove,spaceBelow"}})
        return identity
    cover = prefix + "cover"
    requests.append({"createSlide": {"objectId": cover, "slideLayoutReference": {"predefinedLayout": "BLANK"}}})
    box(cover, "cover_title", meeting["title"], 40, 120, 640, 110, 40,
        {"red": 146 / 255, "green": 46 / 255, "blue": 65 / 255})
    box(cover, "cover_date", meeting.get("date", ""), 40, 260, 640, 45, body_size)
    notes[cover] = ""
    for index, section in enumerate(row for row in meeting["sections"] if row.get("visible", True)):
        page = prefix + "slide_" + str(index)
        requests.append({"createSlide": {"objectId": page, "slideLayoutReference": {"predefinedLayout": "BLANK"}}})
        title_height = text_height(section["title"], 664, 32)
        box(page, "title_" + str(index), section["title"], 28, 18, 664, title_height, 32,
            {"red": 146 / 255, "green": 46 / 255, "blue": 65 / 255})
        entries = [meeting["artifacts"][key] for key in section.get("artifacts", [])]
        lines, bullet_ranges, position = [], [], 0
        for line in bodies[section["id"]].splitlines():
            bullet = bool(re.match(r"^[-*] ", line))
            line = re.sub(r"^[-*] ", "", line)
            line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
            line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
            length = len(line.encode("utf-16-le")) // 2
            if bullet and line.strip():
                bullet_ranges.append({"type": "FIXED_RANGE", "startIndex": position, "endIndex": position + length})
            lines.append(line)
            position += length + 1
        body = "\n".join(lines)
        layout = section.get("layout", "stack")
        content_y = 18 + title_height + 10
        caption = "\n\n".join(part for part in [*(artifact_public_text(entry) for entry in entries),
                                               section.get("caption", "")] if part)
        caption_height = text_height(caption, 650, body_size)
        exhibit_bottom = 390 - caption_height
        if entries and layout in {"figure-left", "figure-right"}:
            body_x, image_x = (388, 30) if layout == "figure-left" else (30, 350)
            body_width, image_width = 302, 340
            body_height = exhibit_bottom - content_y
            image_y, image_height = content_y, body_height
        else:
            body_x, image_x = 30, 30
            body_width, image_width = 650, 650
            body_height = text_height(body, body_width, body_size) if entries else exhibit_bottom - content_y
            image_y = content_y + body_height + (8 if body else 0)
            image_height = exhibit_bottom - image_y
        if entries and image_height < 80:
            raise ValueError("Section text fills its exhibit area; shorten the body or select a side layout: " + section["id"])
        if text_height(body, body_width, body_size) > body_height:
            raise ValueError("Section text fills its slide at 28 pt; split the section: " + section["id"])
        if caption_height > 390 - content_y:
            raise ValueError("Section caption fills its slide at 28 pt; split the section: " + section["id"])
        body_id = box(page, "body_" + str(index), body, body_x, content_y, body_width, body_height, body_size)
        for text_range in bullet_ranges:
            requests.append({"createParagraphBullets": {"objectId": body_id, "textRange": text_range, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
        for number, entry in enumerate(entries):
            tile_width = image_width / max(1, len(entries))
            tile_x = image_x + number * tile_width
            files = entry.get("files", {})
            paths = files.values() if isinstance(files, dict) else files
            picture = next((value for value in paths if Path(value).suffix.lower() in {".png", ".jpg", ".jpeg"}), None)
            if entry.get("rows") and (is_table(entry) or not picture):
                headers, rows = table_cells(entry)
                column_count = len(headers[-1])
                values = [*headers, *rows]
                cell_width = (tile_width - 12) / column_count
                if cell_width <= 16:
                    raise ValueError("Section table columns are too narrow at 28 pt; split the table: " + section["id"])
                required_row_height = max(text_height("—" if value is None else str(value), cell_width, body_size)
                                          for values_row in values for value in values_row)
                if required_row_height * len(values) > image_height:
                    raise ValueError("Section table fills its slide at 28 pt; split the table or its section: " + section["id"])
                identity = prefix + "table_" + str(index) + "_" + str(number)
                requests.append({"createTable": {"objectId": identity, "rows": len(values), "columns": column_count, "elementProperties": {
                    "pageObjectId": page, "size": {"width": {"magnitude": tile_width - 12, "unit": "PT"}, "height": {"magnitude": image_height, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": tile_x, "translateY": image_y, "unit": "PT"}}}})
                requests.append({"updateTableCellProperties": {"objectId": identity,
                    "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": len(headers), "columnSpan": column_count},
                    "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": {"rgbColor": {"red": 0.91, "green": 0.94, "blue": 0.97}}}}},
                    "fields": "tableCellBackgroundFill"}})
                for row_index, values_row in enumerate(values):
                    for column_index, value in enumerate(values_row):
                        location = {"rowIndex": row_index, "columnIndex": column_index}
                        cell = "—" if value is None else str(value)
                        if not cell:
                            continue
                        requests.append({"insertText": {"objectId": identity, "cellLocation": location, "text": cell}})
                        requests.append({"updateTextStyle": {"objectId": identity, "cellLocation": location, "textRange": {"type": "ALL"},
                            "style": {"fontFamily": "Noto Sans JP", "fontSize": {"magnitude": body_size, "unit": "PT"}, "bold": row_index < len(headers)}, "fields": "fontFamily,fontSize,bold"}})
            elif picture:
                local = str(bundled_path(bundle, picture))
                url = asset_base_url.rstrip("/") + "/" + quote(picture, safe="/") if asset_base_url else local
                identity = prefix + "image_" + str(index) + "_" + str(number)
                # Slides fits the image inside this frame while preserving its intrinsic aspect ratio.
                requests.append({"createImage": {"objectId": identity, "url": url, "elementProperties": {
                    "pageObjectId": page, "size": {"width": {"magnitude": tile_width - 12, "unit": "PT"}, "height": {"magnitude": image_height, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": tile_x, "translateY": image_y, "unit": "PT"}}}})
                if not asset_base_url:
                    images.append({"object_id": identity, "path": local})
            else:
                raise ValueError("Native Slides requires a saved PNG/JPEG or saved table rows: " + entry["id"])
        box(page, "caption_" + str(index), caption, 30, exhibit_bottom, 650, caption_height, body_size)
        notes[page] = section.get("speaker_notes", "")
    return {"title": meeting["title"] + (" — " + meeting["date"] if meeting.get("date") else ""),
            "mime_type": "application/vnd.google-apps.presentation", "source_revision": revision,
            "requests": requests, "speaker_notes": notes, "images": images,
            "issue_url": meeting.get("issue_url", ""), "new_independent_edition": True}


def affected_bundles(root, changed):
    root = Path(root)
    common = {"harness/research_meetings.py", "tex/slides/meeting_template.qmd",
              "tex/slides/pandoc_template.latex", "tex/paper/pandoc_template.latex",
              "tex/paper/econsocart.cls", "tex/paper/econsocart.cfg", "tex/paper/ecta-fullname.bst",
              ".github/workflows/meetings.yml"}
    if common.intersection(changed):
        return sorted(str(path.parent.relative_to(root)) for path in (root / "meetings").glob("*/meeting.json"))
    names = {"/".join(Path(path).parts[:2]) for path in changed
             if len(Path(path).parts) >= 3 and Path(path).parts[0] == "meetings"}
    return sorted(name for name in names if (root / name / "meeting.json").is_file())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--root", type=Path, default=Path.cwd())
    create.add_argument("--selection", type=Path, required=True, help="Explicit saved gallery selection JSON")
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--kind", default="meeting", help="Template key from tex/slides/meeting_templates.json")
    create.add_argument("--project-view", type=Path)
    create.add_argument("--previous", type=Path)
    create.add_argument("--date", default="")
    create.add_argument("--issue-url", default="")
    create.add_argument("--github-source", default="")
    render = commands.add_parser("render")
    render.add_argument("--root", type=Path, default=Path.cwd())
    render.add_argument("--bundle", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    render.add_argument("--quarto", default="quarto")
    render.add_argument("--format", choices=("html", "pdf", "markdown"), default="html")
    native = commands.add_parser("google-slides")
    native.add_argument("--bundle", type=Path, required=True)
    native.add_argument("--output", type=Path, required=True)
    native.add_argument("--asset-base-url")
    edit = commands.add_parser("edit")
    edit.add_argument("--bundle", type=Path, required=True)
    edit.add_argument("--section", required=True)
    edit.add_argument("--patch", type=Path, required=True)
    edit.add_argument("--expected-revision", required=True)
    edit.add_argument("--body-file", type=Path)
    link = commands.add_parser("link-edition")
    link.add_argument("--bundle", type=Path, required=True)
    link.add_argument("--url", required=True)
    link.add_argument("--kind", default="google-slides")
    link.add_argument("--expected-revision", required=True)
    link.add_argument("--source-revision")
    affected = commands.add_parser("affected")
    affected.add_argument("--root", type=Path, default=Path.cwd())
    affected.add_argument("--changed", type=Path, required=True)
    preview = commands.add_parser("preview")
    preview.add_argument("--bundle", type=Path, required=True)
    preview.add_argument("--output", type=Path, required=True)
    preview.add_argument("--asset-base-url", default="")
    args = parser.parse_args(argv)
    if args.command in {"google-slides", "preview"}:
        bundle, output = args.bundle.resolve(), args.output.resolve()
        sources = {(bundle / name).resolve() for name in ("meeting.json", "content.md")}
        if output in sources or output.is_relative_to((bundle / "assets").resolve()):
            raise ValueError("A meeting export cannot replace its editable sources or saved exhibits")
    if args.command == "create":
        entries = read_json(args.selection)
        entries = entries["items"] if isinstance(entries, dict) else entries
        result = create_bundle(args.root, args.output, entries, title=args.title, kind=args.kind,
                               project_view=read_json(args.project_view) if args.project_view else None,
                               previous=args.previous, date=args.date, issue_url=args.issue_url,
                               github_source=args.github_source)
    elif args.command == "render":
        result = render_bundle(args.root, args.bundle, args.output, quarto=args.quarto, output_format=args.format)
    elif args.command == "google-slides":
        result = native_slides_requests(args.bundle, asset_base_url=args.asset_base_url)
        write_json(args.output, result)
        result = {"output": str(args.output), "slides": len(result["speaker_notes"]), "source_revision": result["source_revision"]}
    elif args.command == "edit":
        result = edit_section(args.bundle, args.section, read_json(args.patch), expected_revision=args.expected_revision,
                              body=args.body_file.read_text(encoding="utf-8") if args.body_file else None)
    elif args.command == "link-edition":
        result = register_edition(args.bundle, args.url, kind=args.kind, expected_revision=args.expected_revision, source_revision=args.source_revision)
    elif args.command == "preview":
        write_text(args.output, preview_markdown(args.bundle, asset_base_url=args.asset_base_url))
        result = {"output": str(args.output)}
    else:
        result = affected_bundles(args.root, args.changed.read_text(encoding="utf-8").splitlines())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
