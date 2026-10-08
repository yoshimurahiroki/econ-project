#!/usr/bin/env python3
"""Compare or synchronize the explicit mini-owned instruction paths."""

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

COMMON_PATHS = (
    "AGENTS.md",
    "CLAUDE.md",
    "CODEX.md",
    ".cursorrules",
    ".agents/AGENTS.md",
    ".claude/AGENTS.md",
    ".cursor/rules/01_project_policy.mdc",
    ".github/copilot-instructions.md",
    ".gemini/GEMINI.md",
    ".agents/skills/econ-assertive/SKILL.md",
    ".agents/skills/econ-assertive/agents/openai.yaml",
    ".agents/skills/econ-assertive/references/default-micro.md",
    ".agents/skills/econ-assertive/references/patterns.md",
    ".agents/skills/econ-data/SKILL.md",
    ".agents/skills/econ-data/references/implementation.md",
    ".agents/skills/econ-data/references/reproducible-workflow.md",
    ".agents/skills/econ-design/SKILL.md",
    ".agents/skills/econ-design/references/designs.md",
    ".agents/skills/econ-edit/SKILL.md",
    ".agents/skills/econ-handoff/SKILL.md",
    ".agents/skills/econ-handoff/references/handoff.md",
    ".agents/skills/econ-literature/SKILL.md",
    ".agents/skills/econ-paper/SKILL.md",
    ".agents/skills/econ-review/SKILL.md",
    ".agents/skills/econ-style/SKILL.md",
    ".agents/skills/econ-workflow/SKILL.md",
    ".agents/skills/econ-workflow/references/descriptive-model.md",
    ".agents/skills/econ-writing/SKILL.md",
    "docs/ai/compiled_ai_skills.md",
    "docs/ai/project_instructions.txt",
    "docs/ai/project_bridge.txt",
    "scripts/export_project.py",
    "scripts/pack_context.sh",
    "scripts/sync_common_core.py",
)
RECEIPT_START = "<!-- common-core-receipt:v1 -->"
RECEIPT_END = "<!-- /common-core-receipt:v1 -->"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def git(root, *args, required=True):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if required and result.returncode:
        raise ValueError(f"{root}: {result.stderr.decode('utf-8', errors='replace').strip()}")
    return result.stdout if result.returncode == 0 else None


def repository(root):
    root = root.resolve(strict=True)
    top = Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if root != top:
        raise ValueError(f"Use the repository root: {root}")
    origin = git(root, "remote", "get-url", "origin").decode().strip()
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([^/]+/[^/]+?)(?:\.git)?/?", origin)
    if not match:
        raise ValueError(f"Unsupported GitHub origin: {root}")
    return root, match[1], git(root, "rev-parse", "HEAD").decode().strip()


def safe_file(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError(f"Refuse symlink or escaping path: {path}")
    # A parent symlink could redirect a later write even when it currently stays inside root.
    if any(parent.is_symlink() for parent in path.parents if parent != root and parent.is_relative_to(root)):
        raise ValueError(f"Refuse symlink parent: {path}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Expected a file: {path}")
    return path


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def head_file(root, head, relative):
    entry = git(root, "ls-tree", head, "--", relative).decode().strip()
    if not entry:
        return None, None
    metadata, _ = entry.split("\t", 1)
    mode, kind, oid = metadata.split()
    if kind != "blob" or mode not in {"100644", "100755"}:
        raise ValueError(f"Unsupported Git entry: {root / relative}")
    return oid, mode


def file_mode(path, root=None, head=None, relative=None):
    # Some established checkouts ignore filesystem executable bits. Use their
    # tracked Git mode, which is also what a commit will record.
    if root is not None and git(root, "config", "--get", "core.filemode", required=False) == b"false\n":
        _, tracked_mode = head_file(root, head, relative)
        if tracked_mode is not None:
            return tracked_mode
    return "100755" if path.stat().st_mode & 0o111 else "100644"


def receipt_bytes(original, receipt):
    text = original.decode("utf-8")
    block = RECEIPT_START + "\n```json\n" + json.dumps(receipt, ensure_ascii=False, indent=2) + "\n```\n" + RECEIPT_END
    if text.count(RECEIPT_START) != text.count(RECEIPT_END) or text.count(RECEIPT_START) > 1:
        raise ValueError("Malformed common-core receipt in integration.md")
    if RECEIPT_START in text:
        start, end = text.index(RECEIPT_START), text.index(RECEIPT_END)
        if end < start:
            raise ValueError("Malformed common-core receipt in integration.md")
        text = text[:start] + block + text[end + len(RECEIPT_END):]
    else:
        separator = "" if not text or text.endswith("\n\n") else "\n" if text.endswith("\n") else "\n\n"
        text = text + separator + block + "\n"
    return text.encode("utf-8")


def synchronize(source, targets, *, apply=False, expected=None):
    source, source_name, source_head = repository(source)
    if source_name != "yoshimurahiroki/econ-project-mini":
        raise ValueError("Source must be yoshimurahiroki/econ-project-mini")
    destinations = [repository(target) for target in targets]
    roots = [source, *(item[0] for item in destinations)]
    if len(set(roots)) != len(roots):
        raise ValueError("Source and destination roots must be distinct")
    names = [item[1].split("/")[-1] for item in destinations]
    if len(set(names)) != len(names):
        raise ValueError("Specify each destination repository once")
    expected = expected or {}
    if set(expected) - set(names):
        raise ValueError("Expected HEAD supplied for an unselected destination")
    for root, name, head in destinations:
        if name not in {"yoshimurahiroki/econ-project", "yoshimurahiroki/Ruan"}:
            raise ValueError(f"Unsupported destination: {name}")
        short = name.split("/")[-1]
        if apply and expected.get(short) != head:
            raise ValueError(f"Expected HEAD mismatch or absent: {short}; actual {head}")

    inputs = {}
    source_committed = True
    for relative in sorted(COMMON_PATHS):
        path = safe_file(source, relative)
        data = path.read_bytes()
        oid, mode = blob(data), file_mode(path, source, source_head, relative)
        base_oid, base_mode = head_file(source, source_head, relative)
        source_committed &= (oid, mode) == (base_oid, base_mode)
        inputs[relative] = (data, oid, mode, hashlib.sha256(data).hexdigest())
    content_id = hashlib.sha256(canonical([[p, inputs[p][3]] for p in sorted(inputs)])).hexdigest()
    receipt = {
        "source_repository": source_name,
        "source_base_commit": source_head,
        "common_content_id": content_id,
        "source_state": "committed" if source_committed else "working",
        "paths": [{"path": p, "git_blob": inputs[p][1], "sha256": inputs[p][3]} for p in sorted(inputs)],
    }
    report = {"source_repository": source_name, "source_head": source_head, "common_content_id": content_id, "targets": []}
    writes = []
    different = False
    for root, name, head in destinations:
        rows = []
        for relative, (data, oid, mode, sha256) in inputs.items():
            path = safe_file(root, relative)
            current = path.read_bytes() if path.exists() else None
            current_oid = blob(current) if current is not None else None
            current_mode = file_mode(path, root, head, relative) if current is not None else None
            base_oid, base_mode = head_file(root, head, relative)
            matches = (current_oid, current_mode) == (oid, mode)
            # Content already matches the intended source may have its executable bit repaired.
            if apply and not matches and (current_oid, current_mode) != (base_oid, base_mode) and current_oid != oid:
                raise ValueError(f"Conflicting targeted edit: {path}")
            different |= not matches
            rows.append({"path": relative, "source_git_blob": oid, "destination_git_blob": current_oid,
                         "destination_head_blob": base_oid, "source_sha256": sha256,
                         "source_mode": mode, "destination_mode": current_mode, "different": not matches})
            if not matches:
                writes.append((path, current, data, mode))
        integration = safe_file(root, "docs/ai/integration.md")
        original = integration.read_bytes()
        updated = receipt_bytes(original, receipt)
        if updated != original:
            writes.append((integration, original, updated, file_mode(integration)))
        report["targets"].append({"repository": name, "root": str(root), "head": head, "files": rows})
    if apply:
        # All destinations have been checked before the first copy.
        for path, before, _, _ in writes:
            current = path.read_bytes() if path.exists() else None
            if current != before:
                raise ValueError(f"Changed during preflight: {path}")
        for path, _, data, mode in writes:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o755 if mode == "100755" else 0o644)
    report["applied"] = apply
    report["different"] = different
    return report, 0 if apply or not different else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect-head", nargs="+", action="extend", default=[])
    args = parser.parse_args()
    try:
        expected = {}
        for item in args.expect_head:
            name, separator, value = item.partition("=")
            if not separator or name in expected or not re.fullmatch(r"[0-9a-f]{40}", value):
                raise ValueError(f"Invalid or repeated expected HEAD: {item}")
            expected[name] = value
        report, status = synchronize(args.source, args.target, apply=args.apply, expected=expected)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Sync: {error}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(status)


if __name__ == "__main__":
    main()
