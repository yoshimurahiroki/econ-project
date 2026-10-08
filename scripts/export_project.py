#!/usr/bin/env python3
"""Export selected research instructions into a fresh Project attachment folder."""

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ".agents/skills/econ-assertive/references/default-micro.md"
WORKFLOW_REFERENCE = ".agents/skills/econ-workflow/references/descriptive-model.md"
PROJECT_MARKER = "<!-- export-project:v1 -->"
RECEIPT_MARKER = "<!-- common-core-receipt:v1 -->"
GENERATED = {"ECON_INDEX.md", "SOURCE.md"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def marked_json(text, marker):
    occurrences = list(re.finditer(re.escape(marker), text))
    if not occurrences:
        return None, None
    if len(occurrences) != 1:
        raise ValueError(f"Duplicate configuration block: {marker}")
    start = occurrences[0].end()
    match = re.match(
        r"\s*(?P<fence>`{3,}|~{3,})json[ \t]*\n(?P<body>[\s\S]*?)\n(?P=fence)[ \t]*(?=\n|$)",
        text[start:],
    )
    if not match:
        raise ValueError(f"Expected a fenced JSON block after {marker}")
    try:
        value = json.loads(match.group("body"), object_pairs_hook=unique_object)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON after {marker}: {error.msg}") from error
    return value, (start + match.start("body"), start + match.end("body"))


def flat_filename(name):
    return (
        isinstance(name, str)
        and bool(name.strip())
        and name not in {".", ".."}
        and not any(char in name for char in "/\\:\r\n\0")
    )


def inline_code_mask(text):
    """Mark matched backtick spans without changing their bytes or offsets."""
    mask = bytearray(len(text))
    position = 0
    while position < len(text):
        if text[position] != "`" or (position and text[position - 1] == "\\"):
            position += 1
            continue
        end = position
        while end < len(text) and text[end] == "`":
            end += 1
        length = end - position
        closing = end
        while closing < len(text):
            candidate = text.find("`", closing)
            if candidate < 0:
                break
            stop = candidate
            while stop < len(text) and text[stop] == "`":
                stop += 1
            if stop - candidate == length:
                mask[position:stop] = b"\x01" * (stop - position)
                position = stop
                break
            closing = stop
        else:
            candidate = -1
        if candidate < 0 or closing >= len(text):
            position = end
    return mask


def destination_span(text, start):
    """Read an angle-bracket or balanced bare Markdown destination."""
    if start >= len(text):
        return None
    if text[start] == "<":
        end = start + 1
        while end < len(text):
            if text[end] == "\\":
                end += 2
            elif text[end] == ">":
                return start + 1, end, end + 1
            elif text[end] == "\n":
                return None
            else:
                end += 1
        return None
    end, depth = start, 0
    while end < len(text):
        char = text[end]
        if char == "\\":
            end += 2
            continue
        if char.isspace() and depth == 0:
            break
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                break
            depth -= 1
        end += 1
    if depth or end == start:
        return None
    return start, end, end


def rewrite_fragment(text, rewrite):
    mask = inline_code_mask(text)
    changes = []
    title_close = re.compile(
        r'''\s*(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\((?:[^)\\]|\\.)*\))?\s*\)'''
    )
    for match in re.finditer(r"(?<!\\)\]\([ \t\n]*", text):
        if mask[match.start()]:
            continue
        span = destination_span(text, match.end())
        if span is None:
            continue
        start, end, after = span
        closing = title_close.match(text, after)
        if closing is None or any(mask[match.start():closing.end()]):
            continue
        changes.append((start, end, rewrite(text[start:end])))
    for match in re.finditer(r"^ {0,3}\[(?!\^)[^\]\n]+\]:[ \t]*", text, re.MULTILINE):
        if mask[match.start()]:
            continue
        span = destination_span(text, match.end())
        if span:
            start, end, _ = span
            if not any(mask[start:end]):
                changes.append((start, end, rewrite(text[start:end])))
    for start, end, replacement in sorted(set(changes), reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def rewrite_markdown(text, rewrite):
    """Rewrite prose destinations, preserving fenced and inline code."""
    output, pending = [], []
    fence = None
    indented_code = False
    blank_before = True
    for line in text.splitlines(keepends=True):
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\n"))
        indented = line.startswith(("    ", "\t"))
        if not fence and (indented_code or blank_before) and (indented or not line.strip()):
            output.append(rewrite_fragment("".join(pending), rewrite))
            pending = []
            output.append(line)
            indented_code = indented or indented_code
            blank_before = not line.strip()
            continue
        indented_code = False
        if fence:
            output.append(line)
            if re.match(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*$", line.rstrip("\n")):
                fence = None
        elif opening:
            output.append(rewrite_fragment("".join(pending), rewrite))
            pending = []
            fence = opening.group(1)
            output.append(line)
        else:
            pending.append(line)
        blank_before = not line.strip()
    output.append(rewrite_fragment("".join(pending), rewrite))
    return "".join(output)


class Snapshot:
    def __init__(self, root):
        self.root = root.resolve()
        self.cache = {}
        self.mapping = {}
        self.aliases = {name.casefold(): None for name in GENERATED}
        self.omitted = {}
        self.base_commit = self.git("rev-parse", "HEAD").decode().strip() or None
        object_format = self.git("rev-parse", "--show-object-format").decode().strip()
        self.object_format = object_format if object_format in {"sha1", "sha256"} else "sha1"
        origin = self.git("config", "--get", "remote.origin.url").decode().strip()
        remote = re.fullmatch(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([^/]+/[^/?#]+?)(?:\.git)?/?", origin)
        self.repository = remote.group(1) if remote else None

    def git(self, *args):
        process = subprocess.run(
            ["git", "-C", str(self.root), *args], capture_output=True, check=False,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        return process.stdout if process.returncode == 0 else b""

    def committed(self, path):
        if self.base_commit is None or not path.is_relative_to(self.root):
            return None, None
        relative = path.relative_to(self.root).as_posix()
        locator = f"{self.base_commit}:{relative}"
        blob = self.git("rev-parse", "--verify", locator).decode().strip()
        if not blob:
            return None, None
        process = subprocess.run(
            ["git", "-C", str(self.root), "cat-file", "blob", locator],
            capture_output=True, check=False, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        return (blob, process.stdout) if process.returncode == 0 else (None, None)

    def input(self, path):
        path = path.resolve()
        if path not in self.cache:
            if not path.is_file():
                raise ValueError(f"Missing source file: {path}")
            raw = path.read_bytes()
            logical = path.relative_to(self.root).as_posix() if path.is_relative_to(self.root) else "external-profile:" + path.name
            base_blob, _ = self.committed(path)
            current_blob = hashlib.new(self.object_format, b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            self.cache[path] = {
                "path": logical, "base_git_blob": base_blob,
                "current_git_blob": current_blob, "sha256": sha256(raw), "raw": raw,
            }
            if not path.is_relative_to(self.root):
                self.cache[path]["actual_path"] = str(path)
        return self.cache[path]

    def text(self, path):
        return self.input(path)["raw"].decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")

    def inside(self, value):
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise ValueError(f"Expected a repository-relative path: {value}")
        path = (self.root / value).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"Path escapes repository: {value}")
        return path

    def add(self, path, output):
        path = path.resolve()
        if not flat_filename(output):
            raise ValueError(f"Expected a flat output filename: {output}")
        alias = output.casefold()
        if path in self.mapping:
            if self.mapping[path] != output:
                raise ValueError(f"Source has two output aliases: {path}")
            return
        if alias in self.aliases:
            raise ValueError(f"Output alias collision: {output}")
        self.text(path)
        self.mapping[path] = output
        self.aliases[alias] = path

    def omitted_locator(self, path, suffix=""):
        path = path.resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"Unresolved external resource: {path}")
        relative = path.relative_to(self.root).as_posix()
        if not self.repository or not self.base_commit:
            raise ValueError(f"Repository/commit required for omitted resource: {relative}")
        if path.is_dir():
            tree = self.git("rev-parse", "--verify", f"{self.base_commit}:{relative}").decode().strip()
            if not tree or self.git("cat-file", "-t", tree).strip() != b"tree":
                raise ValueError(f"Directory has no recorded revision: {relative}")
            blob, kind = tree, "tree"
        elif path.is_file():
            blob, committed = self.committed(path)
            current = self.input(path)["raw"]
            if committed is None or current != committed:
                raise ValueError(f"Omitted file differs from base commit; include it: {relative}")
            kind = "blob"
        else:
            raise ValueError(f"Unresolved repository resource: {relative}")
        locator = f"https://github.com/{self.repository}/{kind}/{self.base_commit}/{quote(relative, safe='/')}"
        self.omitted[relative] = {"path": relative, "committed_git_blob": blob, "locator": locator}
        return locator + suffix

    def destination(self, source, value):
        decoded = re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])", r"\1", value)
        parts = urlsplit(decoded)
        if not parts.path:
            return value
        suffix = ("?" + parts.query if parts.query else "") + ("#" + parts.fragment if parts.fragment else "")
        if parts.scheme or decoded.startswith("//"):
            pieces = unquote(parts.path).lstrip("/").split("/", 4)
            own = (
                parts.netloc.lower() == "github.com" and self.repository
                and len(pieces) == 5 and "/".join(pieces[:2]).casefold() == self.repository.casefold()
                and pieces[2] in {"blob", "tree"} and pieces[3] in {"main", "HEAD"}
            )
            if not own:
                return value
            linked = self.inside(pieces[4])
        else:
            clean = unquote(parts.path)
            linked = ((self.root / clean.lstrip("/")) if clean.startswith("/") else source.parent / clean).resolve()
            if not linked.exists() and not clean.startswith("/") and "/" not in clean and clean.casefold() in self.aliases:
                alias_source = self.aliases[clean.casefold()]
                filename = self.mapping[alias_source] if alias_source is not None else next(
                    name for name in GENERATED if name.casefold() == clean.casefold()
                )
                return quote(filename, safe='/._-') + suffix
        if linked in self.mapping:
            return quote(self.mapping[linked], safe='/._-') + suffix
        return self.omitted_locator(linked, suffix)


def project_config(snapshot, context_text, available):
    supplied, span = marked_json(context_text, PROJECT_MARKER)
    config = {"version": 1, "writing_profile": "default-micro", "bridge_skills": [], "files": []}
    if span is None:
        legacy = snapshot.root / "docs/research/master-project-addendum.txt"
        if legacy.is_file():
            config["files"] = [{"path": "docs/research/master-project-addendum.txt", "output": "STUDY_ENTRY_POINT.txt"}]
    else:
        if not isinstance(supplied, dict) or set(supplied) - set(config):
            raise ValueError("Invalid export-project:v1 keys")
        if type(supplied.get("version")) is not int or supplied["version"] != 1:
            raise ValueError("export-project:v1 requires version 1")
        config.update(supplied)
    preference = config["writing_profile"]
    if not isinstance(preference, str) or not preference:
        raise ValueError("writing_profile must be default-micro or a repository-relative path")
    if preference != "default-micro":
        snapshot.text(snapshot.inside(preference))
    bridges = config["bridge_skills"]
    if not isinstance(bridges, list) or any(not isinstance(name, str) or name not in available for name in bridges):
        raise ValueError("bridge_skills must name installed methods")
    if len(bridges) != len(set(bridges)):
        raise ValueError("Duplicate bridge_skills entry")
    files = config["files"]
    if not isinstance(files, list):
        raise TypeError("Project files must be a list")
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "output"}:
            raise ValueError("Each project file requires exactly path/output")
        snapshot.text(snapshot.inside(item["path"]))
        if not flat_filename(item["output"]):
            raise ValueError(f"Invalid project output filename: {item['output']}")
    return config, span


def reference_alias(path, root, profile):
    relative = path.relative_to(root).as_posix()
    if profile == "bridge" and relative == WORKFLOW_REFERENCE:
        return "RESEARCH_WORKFLOW.md"
    pieces = path.relative_to(root).parts
    prefix = pieces[2].upper().replace("-", "_")
    reference = "__".join(pieces[4:])
    stem = str(Path(reference).with_suffix("")).upper().replace("-", "_")
    return f"{prefix}__{stem}{path.suffix}"


def export(
    target: Path, profile: str, skills: list[str] | None = None, *,
    task: str | None = None,
    support: tuple[str, ...] = (),
    references: tuple[str, ...] = (),
    style_profile: str | None = None,
) -> int:
    root = ROOT.resolve()
    requested_target = Path(target)
    target = requested_target.resolve()
    if requested_target.exists() or requested_target.is_symlink() or target.exists() or target.is_relative_to(root):
        raise ValueError("Choose a fresh output directory outside the repository")
    if profile not in {"bridge", "standalone"}:
        raise ValueError("Select bridge or standalone")
    if task is not None and skills is not None:
        raise ValueError("Use either --task or --skills")
    if profile == "bridge" and skills is not None:
        raise ValueError("Use --skills with the standalone profile")
    if task is None and (support or references):
        raise ValueError("--support and --references require --task")
    available = {path.parent.name: path.resolve() for path in (root / ".agents/skills").glob("*/SKILL.md")}
    if "econ-assertive" not in available:
        raise ValueError("Missing installed econ-assertive")
    if any(not path.is_relative_to(root) for path in available.values()):
        raise ValueError("Installed skill source escapes repository")
    methods = set(available) - {"econ-assertive"}
    supports = sorted(set(support))
    if task is not None and task not in methods:
        raise ValueError(f"Select an installed primary method: {task}")
    if any(name not in methods or name == task for name in supports):
        raise ValueError("Support must be an installed method distinct from primary/assertive")
    if skills is not None and (not skills or any(name not in available for name in skills)):
        raise ValueError("Select installed skills with --skills")
    snapshot = Snapshot(root)
    context_path = root / "docs/ai/repo_context.md"
    context_text = snapshot.text(context_path)
    config, config_span = project_config(snapshot, context_text, available)
    if task is not None:
        selected = {task, "econ-assertive", *supports}
    elif profile == "bridge":
        selected = {"econ-assertive", "econ-style", *config["bridge_skills"]}
    else:
        selected = set(skills if skills is not None else available)
        selected.add("econ-assertive")
    if any(name not in available for name in selected):
        raise ValueError("Select installed skills")
    selected = sorted(selected)
    core = {
        ".cursorrules": "REPO_POLICY.md",
        "docs/ai/project_instructions.txt": "PROJECT_INSTRUCTIONS.txt",
        "docs/ai/repo_context.md": "REPO_CONTEXT.md",
        "docs/ai/sources.md": "METHOD_SOURCES.md",
    }
    if profile == "bridge":
        core["docs/ai/project_bridge.txt"] = "BRIDGE_INSTRUCTIONS.txt"
    for source, filename in core.items():
        snapshot.add(root / source, filename)
    for name in selected:
        snapshot.add(available[name], name.upper().replace("-", "_") + ".md")
    ref_paths = set()
    if task is None:
        for name in selected:
            ref_paths.update(path.resolve() for path in (available[name].parent / "references").glob("*.md"))
        if profile == "bridge":
            ref_paths.add((root / WORKFLOW_REFERENCE).resolve())
    for value in references:
        path = snapshot.inside(value)
        pieces = path.relative_to(root).parts
        if len(pieces) < 5 or pieces[:2] != (".agents", "skills") or pieces[2] not in available or pieces[3] != "references":
            raise ValueError(f"Select a repository skill reference: {value}")
        ref_paths.add(path)
    for path in sorted(ref_paths):
        if not path.is_relative_to(root):
            raise ValueError(f"Reference escapes repository: {path}")
        snapshot.add(path, reference_alias(path, root, profile))
    for item in config["files"]:
        snapshot.add(snapshot.inside(item["path"]), item["output"])
    general = task is None and (profile == "bridge" or skills is None)
    needs_profile = general or bool(set(selected) & {"econ-writing", "econ-edit"}) or style_profile is not None
    resolved_profile = None
    profile_path = None
    if needs_profile:
        choice = style_profile if style_profile is not None else config["writing_profile"]
        if not isinstance(choice, str) or not choice:
            raise ValueError("Expected a style-profile name or path")
        if choice == "default-micro":
            profile_path = (root / DEFAULT_PROFILE).resolve()
            resolved_profile = "default-micro"
        elif style_profile is not None and Path(choice).is_absolute():
            profile_path = Path(choice).resolve()
            resolved_profile = snapshot.input(profile_path)["path"]
        else:
            profile_path = snapshot.inside(choice)
            resolved_profile = profile_path.relative_to(root).as_posix()
        default_path = (root / DEFAULT_PROFILE).resolve()
        snapshot.add(default_path, "ECON_ASSERTIVE__DEFAULT_MICRO.md")
        if profile_path != default_path:
            snapshot.add(profile_path, "CUSTOM_STYLE.md")
    # Identity includes the implementation and the receipt source even though
    # these inputs are not instruction attachments.
    snapshot.input(root / "scripts/export_project.py")
    receipt = None
    integration = root / "docs/ai/integration.md"
    if integration.is_file():
        receipt, _ = marked_json(snapshot.text(integration), RECEIPT_MARKER)
    if config_span and config["writing_profile"] != "default-micro":
        exported_config = dict(config)
        preference_path = snapshot.inside(config["writing_profile"])
        exported_config["writing_profile"] = (
            snapshot.mapping[preference_path] if preference_path in snapshot.mapping
            else snapshot.omitted_locator(preference_path)
        )
        start, end = config_span
        context_text = context_text[:start] + json.dumps(exported_config, ensure_ascii=False, sort_keys=True, indent=2) + context_text[end:]
    method_provider = (
        "ECON_STYLE" if task == "econ-style"
        else "native ECON methods" if profile == "standalone"
        else "supplied R00/R01–R08 methods"
    )
    study_line = (
        "Use [STUDY_ENTRY_POINT.txt](STUDY_ENTRY_POINT.txt) for requested study implementation."
        if "study_entry_point.txt" in snapshot.aliases else ""
    )
    contents = {}
    for source, filename in sorted(snapshot.mapping.items(), key=lambda item: item[1]):
        text = context_text if source == context_path.resolve() else snapshot.text(source)
        if filename in {"PROJECT_INSTRUCTIONS.txt", "BRIDGE_INSTRUCTIONS.txt"}:
            text = text.replace("{{METHOD_PROVIDER}}", method_provider).replace("{{STUDY_ENTRY_POINT_LINE}}", study_line)
            if filename == "BRIDGE_INSTRUCTIONS.txt" and task == "econ-style":
                text = text.replace(
                    "Use supplied R00_ROUTER.md to select one existing R01-R08 method for the requested deliverable.",
                    "Use ECON_STYLE.md as the primary for this requested profile operation.",
                )
            if re.search(r"\{\{[^{}]+\}\}", text):
                raise ValueError(f"Unresolved instruction template placeholder: {filename}")
        text = rewrite_markdown(text, lambda link, source=source: snapshot.destination(source, link))
        if filename.endswith("INSTRUCTIONS.txt") and len(text.replace("\r\n", "\n").replace("\n", "\r\n")) > 8000:
            raise ValueError(f"Project instructions exceed 8,000 characters: {filename}")
        contents[filename] = text
    # An omitted installed method is a retrievable committed resource. Its
    # current bytes must match that resource just like an omitted linked file.
    for name, path in sorted(available.items()):
        if path not in snapshot.mapping:
            snapshot.omitted_locator(path)
    lines = [
        "# Research task index", "", f"Mode: {profile}.",
        f"Task semantic selector: {task or 'select the method for the current request'}.",
        f"Active method provider: {method_provider}.", "",
    ]
    if profile == "bridge" and task != "econ-style":
        lines.extend([
            "Supplied R00_ROUTER.md resolves the task role to one existing R01–R08 primary. Read the original module to establish its filename.",
            "An explicit native-provider request activates the included native fallback for the whole deliverable.", "",
        ])
    if profile_path is not None:
        alias = snapshot.mapping[profile_path]
        label = "Task profile override" if style_profile is not None else "Available writing profile" if general else "Selected writing profile"
        lines.append(f"{label}: [{resolved_profile}]({alias}).")
        if style_profile is not None:
            lines.append("Use this explicit task profile for the requested writing or wording operation; it overrides the persistent project preference.")
        if profile_path != (root / DEFAULT_PROFILE).resolve():
            lines.append("Use [default-micro](ECON_ASSERTIVE__DEFAULT_MICRO.md) for a required function absent from the selected profile.")
        lines.append("")
    if task == "econ-style":
        lines.extend(["The profile operation uses the requested source passages. A saved project profile is a writing preference rather than an automatically selected source corpus.", ""])
    for name in selected:
        text = snapshot.text(available[name])
        description = re.search(r"^description:[ \t]*(.+)$", text, re.MULTILINE)
        if description is None:
            raise ValueError(f"Missing skill description: {name}")
        if name == "econ-assertive":
            role = "finalizer"
        elif name in supports:
            role = "support"
        elif task == name:
            role = "native fallback" if profile == "bridge" and task != "econ-style" else "primary"
        else:
            role = "available native fallback" if profile == "bridge" and name not in {"econ-style"} else "available method"
        lines.append(f"- [{name}]({snapshot.mapping[available[name]]}) — {role}: {description.group(1).strip()}")
    if ref_paths:
        lines.extend(["", "Included task/reference resources:"])
        for path in sorted(ref_paths):
            lines.append(f"- [{path.relative_to(root).as_posix()}]({snapshot.mapping[path]})")
    lines.extend(["", "Read support and reference sections for the dependency identified by the primary method. METHOD_SOURCES.md records source history.", ""])
    contents["ECON_INDEX.md"] = "\n".join(lines)
    selection = {
        "profile": profile, "task": task,
        "skills": sorted(set(skills)) if skills is not None else None,
        "supports": supports,
        "references": sorted(path.relative_to(root).as_posix() for path in ref_paths),
        "requested_style_profile": style_profile,
        "resolved_style_profile": resolved_profile,
        "profile_output": snapshot.mapping[profile_path] if profile_path is not None else None,
    }
    inputs = []
    for value in snapshot.cache.values():
        inputs.append({key: item for key, item in value.items() if key != "raw"})
    inputs.sort(key=lambda item: item["path"])
    source_mapping = sorted(
        [[snapshot.input(source)["path"], filename] for source, filename in snapshot.mapping.items()],
        key=lambda item: item[0],
    )
    repository = {
        "full_name": snapshot.repository,
        "url": f"https://github.com/{snapshot.repository}" if snapshot.repository else None,
    }
    identity = {
        "repository": repository, "base_commit": snapshot.base_commit,
        "selection": selection, "mapping": source_mapping,
        "inputs": [[item["path"], item["sha256"]] for item in inputs],
    }
    source_for_output = {filename: snapshot.input(source)["path"] for source, filename in snapshot.mapping.items()}
    files = [
        {"source": source_for_output.get(filename, "generated:" + filename),
         "output": filename, "sha256": sha256(text.encode("utf-8"))}
        for filename, text in sorted(contents.items())
    ]
    manifest = {
        "schema_version": 1,
        "repository": repository,
        "base_commit": snapshot.base_commit,
        "snapshot_id": sha256(canonical(identity).encode("utf-8")),
        "selection": selection,
        "project_config": {
            "path": "docs/ai/repo_context.md", "parsed": config,
            "sha256": snapshot.input(context_path)["sha256"],
        },
        "common_core": {"owner": "yoshimurahiroki/econ-project-mini", "receipt": receipt},
        "inputs": inputs,
        "files": files,
        "omitted": [snapshot.omitted[path] for path in sorted(snapshot.omitted)],
        "external_provider": (
            {"resolver": "R00_ROUTER.md", "methods": "existing R01–R08 attachments",
             "input_identity": "Supplied original attachments are outside this export's input hashes."}
            if profile == "bridge" and task != "econ-style" else None
        ),
    }
    contents["SOURCE.md"] = "# Export source\n\n```json\n" + json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n```\n"
    # Every input, alias, omitted locator, placeholder and field length has
    # passed validation before the first output filesystem mutation.
    target.mkdir(parents=True)
    for filename, text in sorted(contents.items()):
        with (target / filename).open("w", encoding="utf-8", newline="\n") as output:
            output.write(text)
    return len(contents)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["bridge", "standalone"], default="standalone")
    parser.add_argument("--output", type=Path, required=True)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--skills", nargs="+")
    selection.add_argument("--task")
    parser.add_argument("--support", action="append", default=[])
    parser.add_argument("--references", action="append", default=[])
    parser.add_argument("--style-profile")
    args = parser.parse_args()
    try:
        count = export(
            args.output, args.profile, args.skills, task=args.task,
            support=tuple(args.support), references=tuple(args.references),
            style_profile=args.style_profile,
        )
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        parser.exit(2, f"Export: {error}\n")
    print(f"Exported {count} files to {args.output}")


if __name__ == "__main__":
    main()
