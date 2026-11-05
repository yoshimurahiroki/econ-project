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


def template_path(root, name):
    root = Path(root)
    candidates = [root / "tex/slides" / name, root / ".agents/tex/slides" / name,
                  Path(__file__).resolve().parent.parent / "tex/slides" / name,
                  Path(__file__).resolve().parent / name]
    if name == "pandoc_template.latex":
        candidates.append(Path(__file__).resolve().parent / "slides_pandoc_template.latex")
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
        lines.append("- " + label + ("（" + "、".join(str(x) for x in details if x) + "）" if any(details) else ""))
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
        "previous": summary_lines(prior_bodies.get("decisions") or prior.get("decisions", [])),
        "previous-todos": prior_bodies.get("next") or task_lines(prior.get("next_actions", [])),
        "completed": task_lines(completed),
        "active": task_lines(view.get("active", view.get("in_progress", []))),
        "findings": summary_lines(view.get("findings", [])),
        "interpretation": summary_lines(view.get("interpretations", [])),
        "discussion": summary_lines(view.get("open_decisions", [])),
        "decisions": summary_lines(view.get("adopted_decisions", [])),
        "next": task_lines(view.get("next", view.get("next_actions", []))),
        "question": str(view.get("research_question", view.get("central_question", ""))),
        "plan": summary_lines(view.get("plan", [])),
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".meeting-", dir=output.parent) as temporary:
        stage = Path(temporary) / "bundle"
        (stage / "assets").mkdir(parents=True)
        artifacts = {}
        for index, entry in enumerate(entries):
            identity = str(entry["id"])
            if identity in artifacts:
                raise ValueError("Duplicate selected artifact: " + identity)
            exported = {key: copy.deepcopy(entry[key]) for key in
                        ("id", "title", "kind", "metadata", "provenance", "rows", "columns",
                         "interpretation", "status", "links", "display", "result_ids") if key in entry}
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
        result_position = next((i for i, row in enumerate(sections) if row["id"] == "results"), len(sections))
        if result_position < len(sections):
            sections.pop(result_position)
        for index, entry in enumerate(entries):
            sid = "result-" + str(index + 1)
            sections.insert(result_position + index, {"id": sid, "title": entry.get("title", entry["id"]),
                            "visible": True, "layout": "stack", "artifacts": [entry["id"]],
                            "caption": "", "speaker_notes": ""})
            bodies[sid] = entry.get("interpretation", "")
        for section in sections:
            section.setdefault("visible", bool(bodies.get(section["id"])) or bool(section.get("artifacts")))
            section.setdefault("layout", "stack")
            section.setdefault("artifacts", [])
            section.setdefault("caption", "")
            section.setdefault("speaker_notes", "")
        meeting = {"schema": "ers-meeting-v1", "title": title, "date": date, "kind": kind,
                   "issue_url": issue_url, "github_source": github_source, "cloud_export": False,
                   "previous": {"title": prior.get("title", ""), "issue_url": prior.get("issue_url", "")},
                   "sections": sections, "artifacts": artifacts, "decisions": [],
                   "next_actions": copy.deepcopy(view.get("next", view.get("next_actions", []))),
                   "task_snapshot": copy.deepcopy(view.get("tasks", [])),
                   "task_source": copy.deepcopy(view.get("github", {})),
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
        bodies[section_id] = body
        write_text(Path(bundle) / "content.md", content_text(meeting["sections"], bodies))
    write_json(Path(bundle) / "meeting.json", meeting)
    return {"source_revision": load_meeting(bundle)[2], "analysis_executed": False}


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
        bodies[add["id"]] = add.get("body", "")
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
        write_text(Path(bundle) / "content.md", existing_text.rstrip() + "\n\n<!-- section:"
                   + add["id"] + " -->\n\n" + bodies[add["id"]] + "\n")
    write_json(Path(bundle) / "meeting.json", meeting)
    return {"source_revision": load_meeting(bundle)[2], "analysis_executed": False}


def artifact_notes(entry, *, output_format="html"):
    metadata = entry.get("metadata", {})
    labels = {"sample": "標本", "observation_unit": "観測単位", "comparison": "比較", "period": "期間",
              "unit": "単位", "estimand": "推定対象", "estimator": "推定方法", "clustering": "クラスタ",
              "confidence_level": "信頼区間", "n": "N", "source": "出所",
              "measurement_units": "単位", "inference": "推論", "data_source": "データ出所"}
    if output_format == "pdf":
        labels.update({"population": "母集団", "variables": "変数"})
    parts = []
    for key, label in labels.items():
        value = metadata.get(key)
        if value is not None and value != "":
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            parts.append(label + ": " + str(value))
    if entry.get("result_ids"):
        parts.append("結果ID: " + ", ".join(entry["result_ids"]))
    if output_format == "pdf":
        for result_id in entry.get("result_ids", []):
            definition = metadata.get("result_definitions", {}).get(result_id, {})
            for key, label in labels.items():
                value = definition.get(key)
                if value is not None and value != "" and value != metadata.get(key):
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False)
                    parts.append(result_id + " " + label + ": " + str(value))
            producer = metadata.get("producers", {}).get(result_id, {})
            identity = producer.get("identity") or {}
            origin = dict(identity)
            if producer.get("run_id"):
                origin["run_id"] = producer["run_id"]
            if origin:
                parts.append(result_id + " 生成元: " + json.dumps(origin, ensure_ascii=False))
    return "。".join(parts)


def table_markdown(entry):
    rows = entry.get("rows", [])
    definitions = entry.get("columns") or ([{"key": key, "label": key} for key in rows[0]] if rows else [])
    columns = [item["key"] for item in definitions]
    if not columns:
        return ""
    display = entry.get("display", {})
    def cell(value, key=None):
        if type(value) in (int, float) and key in display.get("formats", {}):
            value = format(value, display["formats"][key])
        return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")
    labels = {item["key"]: display.get("column_labels", {}).get(item["key"], item.get("label", item["key"])) +
              (" (" + item["unit"] + ")" if item.get("unit") else "") for item in definitions}
    lines = ["| " + " | ".join(cell(labels.get(key, key)) for key in columns) + " |",
             "| " + " | ".join("---" for _ in columns) + " |"]
    lines.extend("| " + " | ".join(cell(row.get(key, ""), key) for key in columns) + " |" for row in rows)
    return "\n".join(lines)


def exhibit_markdown(entry, *, output_format="html", layout="stack"):
    files = entry.get("files", {})
    image = next((value for suffix in (".png", ".jpg", ".jpeg", ".svg")
                  for value in files.values() if Path(value).suffix.lower() == suffix), None)
    table = entry.get("display", {}).get("plot_type", "table" if entry.get("kind") in
        {"table", "descriptive", "descriptive_table", "sample_composition"} else "figure") == "table"
    if table and entry.get("rows"):
        content = table_markdown(entry)
    elif image:
        content = "![" + entry.get("title", "").replace("]", "\\]") + "](" + image + "){fig-alt=" + json.dumps(entry.get("title", ""), ensure_ascii=False) + "}"
    else:
        content = table_markdown(entry)
    notes = artifact_notes(entry, output_format=output_format)
    if output_format == "pdf":
        note = "```{=latex}\n\\begingroup\\scriptsize\\raggedright\n```\n\n" + notes + "\n\n```{=latex}\n\\par\\endgroup\n```" if notes else ""
        if image and not table:
            # Reserve room for the saved definitions and preserve the display's
            # aspect ratio while bounding both dimensions within its column.
            height = "70%" if layout == "stack" else "40%"
            content = content[:-1] + " width=100% height=" + height + "}"
            content = "```{=latex}\n\\begingroup\\setkeys{Gin}{keepaspectratio}\n```\n\n" + content + "\n\n```{=latex}\n\\endgroup\n```"
            if note and layout == "stack":
                return ":::: {.columns}\n::: {.column width=\"68%\"}\n" + content + "\n:::\n::: {.column width=\"32%\"}\n" + note + "\n:::\n::::"
        return "\n\n".join(part for part in (content, note) if part)
    return content + ("\n\n::: {.exhibit-note}\n" + notes + "\n:::" if notes else "")


def document_source(root, meeting, bodies, *, output_format="html"):
    template = template_path(root, "meeting_template.qmd")
    if template is None:
        raise ValueError("Missing tex/slides/meeting_template.qmd")
    slides = []
    for section in meeting["sections"]:
        if not section.get("visible", True):
            continue
        body = bodies[section["id"]]
        if "{{<" in body:
            raise ValueError("Meeting Markdown uses saved bundle assets; expand Quarto shortcodes before export")
        layout = section.get("layout", "stack")
        selected = [exhibit_markdown(meeting["artifacts"][key], output_format=output_format, layout=layout)
                    for key in section.get("artifacts", [])]
        exhibits = "\n\n".join(selected)
        if layout in {"figure-left", "figure-right"} and exhibits:
            first, second = (exhibits, body) if layout == "figure-left" else (body, exhibits)
            content = ":::: {.columns}\n::: {.column width=\"52%\"}\n" + first + "\n:::\n::: {.column width=\"48%\"}\n" + second + "\n:::\n::::"
        elif layout == "figures" and selected:
            width = str(100 / len(selected)) + "%"
            content = body + "\n\n:::: {.columns}\n" + "\n".join(
                "::: {.column width=\"" + width + "\"}\n" + exhibit + "\n:::" for exhibit in selected) + "\n::::"
        else:
            content = "\n\n".join(part for part in (body, exhibits) if part)
        if section.get("caption"):
            if output_format == "pdf":
                content += "\n\n```{=latex}\n\\begingroup\\scriptsize\\raggedright\n```\n\n" + section["caption"] + "\n\n```{=latex}\n\\par\\endgroup\n```"
            else:
                content += "\n\n::: {.exhibit-note}\n" + section["caption"] + "\n:::"
        if section.get("speaker_notes"):
            content += "\n\n::: {.notes}\n" + section["speaker_notes"] + "\n:::"
        slides.append("## " + section["title"].replace("\n", " ") + " {#" + section["id"] + "}\n\n" + content)
    substitutions = {"title": json.dumps(meeting["title"], ensure_ascii=False),
                     "date": json.dumps(meeting.get("date", ""), ensure_ascii=False),
                     "body": "\n\n".join(slides)}
    return re.sub(r"\{\{(title|date|body)\}\}", lambda match: substitutions[match.group(1)], template.read_text(encoding="utf-8"))


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
            table = entry.get("display", {}).get("plot_type", "table" if entry.get("kind") in
                {"table", "descriptive", "descriptive_table", "sample_composition"} else "figure") == "table"
            if table or not picture:
                output.append(table_markdown(entry))
            else:
                url = asset_base_url.rstrip("/") + "/" + quote(picture, safe="/") if asset_base_url else picture
                output.append("![" + entry.get("title", key).replace("]", "\\]") + "](" + url + ")")
            output.append(artifact_notes(entry))
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
    source = document_source(root, meeting, bodies, output_format=output_format)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ers-meeting-render-", dir=output.parent) as temporary:
        stage = Path(temporary)
        (stage / "index.qmd").write_text(source, encoding="utf-8")
        # An isolated document root prevents repository render hooks and engines
        # from participating in a saved-exhibit render.
        (stage / "_quarto.yml").write_text("project:\n  type: default\nexecute:\n  enabled: false\n  freeze: true\n", encoding="utf-8")
        consumed = set()
        for section in meeting["sections"]:
            if not section.get("visible", True):
                continue
            for key in section.get("artifacts", []):
                for relative in meeting["artifacts"][key].get("files", {}).values():
                    if relative in consumed:
                        continue
                    source_asset = bundled_path(bundle, relative)
                    target = stage / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source_asset, target)
                    consumed.add(relative)
        target_format = {"html": "revealjs", "pdf": "beamer", "markdown": "gfm"}[output_format]
        command = [quarto, "render", "index.qmd", "--to", target_format, "--no-execute"]
        if output_format == "pdf":
            adapter = template_path(root, "pandoc_template.latex")
            if adapter is None:
                raise ValueError("Missing existing Beamer/Pandoc template")
            command += ["--template", str(adapter), "--pdf-engine", "lualatex"]
        subprocess.run(command, cwd=stage, capture_output=True, text=True, check=True)
        extension = {"html": "html", "pdf": "pdf", "markdown": "md"}[output_format]
        completed = stage / ("index." + extension)
        if not completed.is_file():
            raise ValueError("Document renderer did not return its declared output")
        published = stage / "completed"
        published.mkdir()
        shutil.copyfile(completed, published / completed.name)
        shutil.copyfile(stage / "index.qmd", published / "index.qmd")
        (published / "preview.md").write_text(preview_markdown(bundle), encoding="utf-8")
        if (stage / "assets").exists():
            shutil.copytree(stage / "assets", published / "assets")
        record = {"source_revision": revision, "format": output_format, "command": command,
                  "artifact": completed.name, "artifact_sha256": hashlib.sha256(completed.read_bytes()).hexdigest(),
                  "consumed_assets": sorted(consumed), "analysis_executed": False,
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
    box(cover, "cover_title", meeting["title"], 40, 120, 640, 110, 34,
        {"red": 146 / 255, "green": 46 / 255, "blue": 65 / 255})
    box(cover, "cover_date", meeting.get("date", ""), 40, 260, 640, 35, 18)
    notes[cover] = "\n".join(value for value in [meeting.get("issue_url", ""), meeting.get("github_source", ""),
                                                "Source revision: " + revision] if value)
    for index, section in enumerate(row for row in meeting["sections"] if row.get("visible", True)):
        page = prefix + "slide_" + str(index)
        requests.append({"createSlide": {"objectId": page, "slideLayoutReference": {"predefinedLayout": "BLANK"}}})
        title_height = text_height(section["title"], 664, 28)
        box(page, "title_" + str(index), section["title"], 28, 18, 664, title_height, 28,
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
        caption = section.get("caption", "")
        caption_height = text_height(caption, 650, 10)
        exhibit_bottom = 390 - caption_height
        if entries and layout in {"figure-left", "figure-right"}:
            body_x, image_x = (388, 30) if layout == "figure-left" else (30, 350)
            body_width, image_width = 302, 340
            body_height = exhibit_bottom - content_y
            image_y, image_height = content_y, body_height
        else:
            body_x, image_x = 30, 30
            body_width, image_width = 650, 650
            body_height = text_height(body, body_width, 18) if entries else exhibit_bottom - content_y
            image_y = content_y + body_height + (8 if body else 0)
            image_height = exhibit_bottom - image_y
        if entries and image_height < 80:
            raise ValueError("Section text fills its exhibit area; shorten the body or select a side layout: " + section["id"])
        body_id = box(page, "body_" + str(index), body, body_x, content_y, body_width, body_height, 18)
        for text_range in bullet_ranges:
            requests.append({"createParagraphBullets": {"objectId": body_id, "textRange": text_range, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
        for number, entry in enumerate(entries):
            tile_width = image_width / max(1, len(entries))
            tile_x = image_x + number * tile_width
            files = entry.get("files", {})
            paths = files.values() if isinstance(files, dict) else files
            picture = next((value for value in paths if Path(value).suffix.lower() in {".png", ".jpg", ".jpeg"}), None)
            plot_type = entry.get("display", {}).get("plot_type")
            saved_table = plot_type == "table" if plot_type else entry.get("kind") == "table"
            if entry.get("rows") and (saved_table or not picture):
                rows = entry["rows"]
                definitions = entry.get("columns") or [{"key": key, "label": key} for key in rows[0]]
                columns = [column["key"] for column in definitions]
                identity = prefix + "table_" + str(index) + "_" + str(number)
                requests.append({"createTable": {"objectId": identity, "rows": len(rows) + 1, "columns": len(columns), "elementProperties": {
                    "pageObjectId": page, "size": {"width": {"magnitude": tile_width - 12, "unit": "PT"}, "height": {"magnitude": image_height, "unit": "PT"}},
                    "transform": {"scaleX": 1, "scaleY": 1, "translateX": tile_x, "translateY": image_y, "unit": "PT"}}}})
                requests.append({"updateTableCellProperties": {"objectId": identity,
                    "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": 1, "columnSpan": len(columns)},
                    "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": {"rgbColor": {"red": 0.91, "green": 0.94, "blue": 0.97}}}}},
                    "fields": "tableCellBackgroundFill"}})
                labels = [column.get("label", column["key"]) + ("\n" + column["unit"] if column.get("unit") else "") for column in definitions]
                values = [labels] + [[row.get(key, "") for key in columns] for row in rows]
                formats = entry.get("display", {}).get("formats", {})
                for row_index, values_row in enumerate(values):
                    for column_index, value in enumerate(values_row):
                        location = {"rowIndex": row_index, "columnIndex": column_index}
                        if row_index and isinstance(value, (int, float)) and columns[column_index] in formats:
                            value = format(value, formats[columns[column_index]])
                        cell = "—" if value is None else str(value)
                        if cell:
                            requests.append({"insertText": {"objectId": identity, "cellLocation": location, "text": cell}})
                        requests.append({"updateTextStyle": {"objectId": identity, "cellLocation": location, "textRange": {"type": "ALL"},
                            "style": {"fontFamily": "Noto Sans JP", "fontSize": {"magnitude": 14 if row_index == 0 else 16, "unit": "PT"}, "bold": row_index == 0}, "fields": "fontFamily,fontSize,bold"}})
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
        box(page, "caption_" + str(index), caption, 30, exhibit_bottom, 650, caption_height, 10)
        note_parts = [section.get("speaker_notes", "")]
        for entry in entries:
            note_parts.extend([entry["title"], artifact_notes(entry), *entry.get("display", {}).get("notes", [])])
            note_parts.append(json.dumps(entry.get("metadata", {}), ensure_ascii=False, indent=2))
        notes[page] = "\n\n".join(part for part in note_parts if part)
    return {"title": meeting["title"] + (" — " + meeting["date"] if meeting.get("date") else ""),
            "mime_type": "application/vnd.google-apps.presentation", "source_revision": revision,
            "requests": requests, "speaker_notes": notes, "images": images,
            "issue_url": meeting.get("issue_url", ""), "new_independent_edition": True}


def affected_bundles(root, changed):
    root = Path(root)
    common = {"harness/research_meetings.py", "tex/slides/meeting_template.qmd", ".github/workflows/meetings.yml"}
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
    create.add_argument("--kind", default="meeting", choices=("meeting", "progress", "proposal", "results"))
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
