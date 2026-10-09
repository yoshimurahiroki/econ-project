#!/usr/bin/env python3
"""Compare or synchronize an explicit set of common files between Git repositories."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from urllib.parse import urlsplit
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
    "scripts/test_sync_common_core.py",
    "scripts/setup_ide_mcp.sh",
    "scripts/test_setup_ide_mcp.py",
    "docs/ai/config-templates/mcp.example.json",
    "docs/ai/config-templates/claude-mcp.example.json",
    "docs/ai/config-templates/codex.example.toml",
    "docs/ai/config-templates/README.md",
    ".agents/skills/econ-workflow/references/team-execution.md",
    ".agents/skills/econ-workflow/scripts/team_state.py",
    ".agents/skills/econ-workflow/scripts/test_team_state.py",
    ".agents/skills/econ-review/references/oversight.md",
)

LOCAL_CONFIG_PATHS = (
    ".agents/mcp.json",
    ".claude/mcp-configs/mcp-servers.json",
    ".codex/config.toml",
    ".cursor/mcp.json",
    ".gemini/mcp-configs/mcp-servers.json",
    ".gemini/mcp.json",
    ".mcp.json",
    ".windsurf/mcp.json",
    "mcp.json",
)
RECEIPT_PATH = "docs/ai/integration.md"
RECEIPT_START = "<!-- common-core-receipt:v2 -->"
RECEIPT_END = "<!-- /common-core-receipt:v2 -->"
LEGACY_START = "<!-- common-core-receipt:v1 -->"
LEGACY_END = "<!-- /common-core-receipt:v1 -->"
FENCE = chr(96) * 3


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def git(root, *args, required=True):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if required and result.returncode:
        raise ValueError(f"Git operation failed: {args[0]}")
    return result.stdout if result.returncode == 0 else None


def identity(origin):
    """Public, credential-free host/owner/repository identity."""
    match = re.fullmatch(r"(?:[^/@:]+@)?([^/:]+):([^?#]+)", origin)
    if match and "://" not in origin:
        host, path = match.groups()
    else:
        parsed = urlsplit(origin)
        if parsed.scheme not in {"https", "http", "ssh", "git"} or not parsed.hostname:
            raise ValueError("Repository origin must identify a remote host and repository")
        if parsed.password or parsed.query or parsed.fragment or (parsed.scheme in {"http", "https"} and parsed.username):
            raise ValueError("Credential-bearing or parameterized origins are not accepted")
        host = parsed.hostname + (f":{parsed.port}" if parsed.port else "")
        path = parsed.path.lstrip("/")
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if len(path.split("/")) < 2 or any(part in {"", ".", ".."} for part in path.split("/")):
        raise ValueError("Origin must contain its complete owner and repository path")
    return host.lower() + "/" + path


def repository(root):
    root = Path(root).resolve(strict=True)
    top = Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if root != top:
        raise ValueError("Use the actual Git repository root")
    origin = git(root, "remote", "get-url", "origin").decode().strip()
    return root, identity(origin), git(root, "rev-parse", "HEAD").decode().strip()


def checked_path(relative):
    path = Path(relative)
    if not relative or any(ord(c) < 32 for c in relative) or path.is_absolute() or "\\" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise ValueError(f"Invalid managed relative path: {relative}")
    if ".git" in path.parts or relative == RECEIPT_PATH:
        raise ValueError(f"Reserved managed path: {relative}")
    return relative


def safe_file(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError(f"Refuse symlink or escaping path: {relative}")
    if any(parent.is_symlink() for parent in path.parents if parent != root and parent.is_relative_to(root)):
        raise ValueError(f"Refuse symlink parent: {relative}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Expected a regular file: {relative}")
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
        raise ValueError(f"Unsupported Git entry: {relative}")
    return oid, mode



def index_file(root, relative):
    entries = []
    for line in git(root, "ls-files", "--stage", "--", relative).decode().splitlines():
        metadata, _ = line.split("\t", 1)
        mode, oid, stage = metadata.split()
        entries.append((oid, mode, stage))
    return tuple(entries)


def index_matches_head(root, head, relative, entries):
    oid, mode = head_file(root, head, relative)
    expected = ((oid, mode, "0"),) if oid is not None else ()
    return entries == expected

def file_mode(path, root=None, head=None, relative=None):
    if root is not None and git(root, "config", "--get", "core.filemode", required=False) == b"false\n":
        _, tracked_mode = head_file(root, head, relative)
        if tracked_mode is not None:
            return tracked_mode
    return "100755" if path.stat().st_mode & 0o111 else "100644"


def snapshot(root, head, relative, modes=False):
    path = safe_file(root, relative)
    if not path.exists():
        return {"data": None, "sha256": None, "mode": None, "git_blob": None, "filesystem_mode": None}
    data = path.read_bytes()
    mode = file_mode(path, root, head, relative) if modes is False else ((modes or {}).get(relative) or ("100755" if path.stat().st_mode & 0o111 else "100644"))
    return {"data": data, "sha256": hashlib.sha256(data).hexdigest(),
            "mode": mode, "git_blob": blob(data),
            "filesystem_mode": "100755" if path.stat().st_mode & 0o111 else "100644"}


def signature(state):
    return state["sha256"], state["mode"]


def fingerprint(state):
    return "absent" if state["data"] is None else f'{state["sha256"]}:{state["mode"]}'


def read_receipt(original):
    text = original.decode("utf-8")
    found = []
    for version, start, end in ((2, RECEIPT_START, RECEIPT_END), (1, LEGACY_START, LEGACY_END)):
        if text.count(start) != text.count(end) or text.count(start) > 1:
            raise ValueError("Malformed common-core receipt")
        if start in text:
            a, b = text.index(start), text.index(end)
            if b < a:
                raise ValueError("Malformed common-core receipt")
            body = text[a + len(start):b].strip()
            if not body.startswith(FENCE + "json\n") or not body.endswith("\n" + FENCE):
                raise ValueError("Malformed receipt JSON block")
            receipt = json.loads(body[len(FENCE + "json\n"):-len("\n" + FENCE)])
            found.append((version, receipt, a, b + len(end)))
    if len(found) > 1:
        raise ValueError("Multiple common-core receipts")
    return found[0] if found else (None, {}, None, None)


def receipt_bytes(original, receipt):
    _, _, start, end = read_receipt(original)
    text = original.decode("utf-8")
    block = RECEIPT_START + "\n" + FENCE + "json\n" + json.dumps(receipt, ensure_ascii=False, indent=2) + "\n" + FENCE + "\n" + RECEIPT_END
    if start is not None:
        text = text[:start] + block + text[end:]
    else:
        separator = "" if not text or text.endswith("\n\n") else "\n" if text.endswith("\n") else "\n\n"
        text += separator + block + "\n"
    return text.encode("utf-8")


def baseline(receipt, version, source, source_name, target_name, migrate, released=()):
    if not version:
        return {}
    old_source = receipt.get("source_repository", "")
    if version == 1:
        if not migrate:
            raise ValueError("Legacy receipt requires --migrate-receipt after checking its recorded source")
        if "/" in old_source and not old_source.startswith(("https:", "ssh:")) and old_source.count("/") == 1:
            old_source = "github.com/" + old_source
    if old_source != source_name:
        raise ValueError("Receipt belongs to another source repository")
    if version == 2 and receipt.get("target_repository") != target_name:
        raise ValueError("Receipt belongs to another target repository")
    rows = {}
    for row in receipt.get("paths", []):
        path = checked_path(row["path"])
        if path in released:
            continue
        if path in rows:
            raise ValueError(f"Repeated receipt path: {path}")
        row = dict(row)
        if version == 1:
            oid, mode = head_file(source, receipt["source_base_commit"], path)
            data = git(source, "show", f'{receipt["source_base_commit"]}:{path}')
            if oid != row.get("git_blob") or hashlib.sha256(data).hexdigest() != row.get("sha256"):
                raise ValueError(f"Legacy receipt cannot establish committed baseline: {path}; use an explicit --claim")
            row["mode"] = mode
            row["state"] = "present"
        if row.get("state") == "deleted":
            row["sha256"], row["mode"] = None, None
        elif not re.fullmatch(r"[0-9a-f]{64}", row.get("sha256", "")) or row.get("mode") not in {"100644", "100755"}:
            raise ValueError(f"Invalid receipt baseline: {path}")
        rows[path] = row
    return rows


def _atomic_write(path, data, mode):
    if data is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".common-sync-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(temporary, 0o755 if mode == "100755" else 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def synchronize(source, targets, *, apply=False, expected=None, expected_source=None,
                expected_content=None, paths=None, deletes=(), releases=(), claims=None, migrate=False):
    source, source_name, source_head = repository(source)
    destinations = [repository(target) for target in targets]
    roots = [source, *(item[0] for item in destinations)]
    if len(set(roots)) != len(roots):
        raise ValueError("Source and destination roots must be distinct")
    names = [item[1] for item in destinations]
    if len(set(names)) != len(names):
        raise ValueError("Specify each complete destination identity once")
    expected, claims = expected or {}, claims or {}
    if set(expected) - set(names):
        raise ValueError("Expected HEAD supplied for an unselected destination")
    selected = {checked_path(p) for p in (COMMON_PATHS if paths is None and not deletes and not releases else (paths or []))}
    released = {checked_path(p) for p in releases}
    deleted = {checked_path(p) for p in deletes}
    if not selected and not deleted and not released:
        raise ValueError("Select at least one managed file")
    if (selected | deleted) & released:
        raise ValueError("A released path cannot also be copied or deleted")
    if selected & deleted:
        raise ValueError("A path cannot be both copied and deleted")
    managed = selected | deleted
    if any(name not in names or path not in managed for name, path in claims):
        raise ValueError("Claim supplied outside the selected destinations or paths")
    if apply and expected_source != source_head:
        raise ValueError(f"Expected source HEAD mismatch or absent: {source_name}; actual {source_head}")
    for _, name, head in destinations:
        if apply and expected.get(name) != head:
            raise ValueError(f"Expected target HEAD mismatch or absent: {name}; actual {head}")

    mode_configs, mode_context = {}, {}
    for root, _, head in [(source, source_name, source_head), *destinations]:
        config = git(root, "config", "--get", "core.filemode", required=False)
        mode_configs[root] = config
        modes = {}
        if config == b"false\n":
            for entry in git(root, "ls-tree", "-r", "-z", head, "--", *sorted(managed | {RECEIPT_PATH})).split(b"\0"):
                if entry:
                    metadata, relative = entry.decode().split("\t", 1)
                    modes[relative] = metadata.split()[0]
        mode_context[root] = modes
    def snap(root, head, relative):
        return snapshot(root, head, relative, modes=mode_context[root])

    inputs = {}
    committed = True
    for relative in sorted(selected):
        state = snap(source, source_head, relative)
        if state["data"] is None:
            raise ValueError(f"Source file absent: {relative}; deletion requires --delete")
        committed &= (state["git_blob"], state["mode"]) == head_file(source, source_head, relative)
        inputs[relative] = state
    for relative in deleted:
        committed &= head_file(source, source_head, relative) == (None, None)
        if snap(source, source_head, relative)["data"] is not None:
            raise ValueError(f"Deletion source must be absent: {relative}")
        inputs[relative] = {"data": None, "sha256": None, "git_blob": None, "mode": None}
    content_id = hashlib.sha256(canonical([[p, inputs[p]["sha256"], inputs[p]["mode"]] for p in sorted(inputs)] + [[p, "released", None] for p in sorted(released)])).hexdigest()
    if expected_content is not None and expected_content != content_id:
        raise ValueError("Expected source content does not match selected inputs")
    if apply and not committed and expected_content != content_id:
        raise ValueError("Working source requires --expect-source-content from the reviewed comparison")
    report = {"source_repository": source_name, "source_head": source_head,
              "source_state": "committed" if committed else "working",
              "common_content_id": content_id, "managed_paths": sorted(managed), "released_paths": sorted(released), "targets": []}
    observations, indexes, writes, receipts, conflicts = [], [], [], [], []
    different = False
    for root, name, head in destinations:
        integration = snap(root, head, RECEIPT_PATH)
        original = integration["data"] or b""
        version, old_receipt, _, _ = read_receipt(original)
        all_released = released | set(old_receipt.get("released_paths", []))
        if managed & all_released:
            raise ValueError("Previously released local paths cannot be synchronized")
        old_rows = baseline(old_receipt, version, source, source_name, name, migrate, all_released)
        receipt_index = index_file(root, RECEIPT_PATH)
        indexes.append((root, RECEIPT_PATH, receipt_index))
        if not index_matches_head(root, head, RECEIPT_PATH, receipt_index):
            conflicts.append(f"{name}:{RECEIPT_PATH}: staged receipt changes are protected")
        rows, new_rows = [], dict(old_rows)
        for relative, desired in sorted(inputs.items()):
            current = snap(root, head, relative)
            observations.append((root, head, relative, current))
            staged = index_file(root, relative)
            indexes.append((root, relative, staged))
            previous = old_rows.get(relative)
            matches = signature(current) == signature(desired)
            repair_execute = desired["mode"] == current["mode"] == "100755" and current.get("filesystem_mode") != "100755"
            matches = matches and not repair_execute
            own = previous is not None and signature(current) == (previous["sha256"], previous["mode"])
            claimed = claims.get((name, relative)) == fingerprint(current)
            conflict = None
            if not own and not claimed and (previous is not None or current["data"] is not None):
                conflict = "target changed since receipt" if previous else "existing file requires explicit ownership claim"
            if (name, relative) in claims and not claimed:
                conflict = "claim fingerprint does not match target"
            if not index_matches_head(root, head, relative, staged):
                conflict = "staged target changes are protected"
            if desired["mode"] is not None and desired["mode"] != (current["mode"] or "100644") and mode_configs[root] == b"false\n":
                conflict = "executable mode change requires Git core.filemode=true; synchronization does not stage index changes"
            if conflict:
                conflicts.append(f"{name}:{relative}: {conflict}")
            different |= not matches
            rows.append({"path": relative, "source_sha256": desired["sha256"],
                         "source_mode": desired["mode"], "destination_fingerprint": fingerprint(current),
                         "repair_execute_bit": repair_execute,
                         "previous_sha256": previous["sha256"] if previous else None,
                         "destination_index": staged,
                         "different": not matches, "conflict": conflict})
            if not matches and not conflict:
                writes.append((root, head, relative, current, desired))
            new_rows[relative] = {"path": relative, "state": "deleted" if desired["data"] is None else "present",
                                  "sha256": desired["sha256"], "git_blob": desired["git_blob"],
                                  "mode": desired["mode"], "source_repository": source_name,
                                  "source_commit": source_head}
        receipt = {"schema_version": 2, "source_repository": source_name,
                   "source_base_commit": source_head, "source_state": report["source_state"],
                   "common_content_id": content_id, "target_repository": name,
                   "paths": [new_rows[p] for p in sorted(new_rows)], "released_paths": sorted(all_released)}
        updated = receipt_bytes(original, receipt)
        observations.append((root, head, RECEIPT_PATH, integration))
        if updated != original:
            different = True
            desired = {"data": updated, "sha256": hashlib.sha256(updated).hexdigest(),
                       "git_blob": blob(updated), "mode": integration["mode"] or "100644"}
            receipts.append((root, head, RECEIPT_PATH, integration, desired))
        report["targets"].append({"repository": name, "head": head, "files": rows})
    report["conflicts"] = conflicts
    report["applied"], report["different"] = False, different
    if apply:
        if conflicts:
            raise ValueError("Conflicts:\n" + "\n".join(conflicts))

        def verify_inputs():
            if repository(source) != (source, source_name, source_head):
                raise ValueError("Source repository changed during synchronization")
            for p, before in inputs.items():
                if signature(snap(source, source_head, p)) != signature(before):
                    raise ValueError(f"Source changed during synchronization: {p}")
            by_root = {}
            for root, relative, before_index in indexes:
                by_root.setdefault(root, {})[relative] = before_index
            for root, previous_index in by_root.items():
                current_index = {p: [] for p in previous_index}
                for entry in git(root, "ls-files", "--stage", "-z", "--", *previous_index).split(b"\0"):
                    if entry:
                        metadata, relative = entry.decode().split("\t", 1)
                        mode, oid, stage = metadata.split()
                        current_index[relative].append((oid, mode, stage))
                for relative, before_index in previous_index.items():
                    if tuple(current_index[relative]) != before_index:
                        raise ValueError(f"Target index changed during synchronization: {relative}")
            for root, before_config in mode_configs.items():
                if git(root, "config", "--get", "core.filemode", required=False) != before_config:
                    raise ValueError("Git mode configuration changed during synchronization")
            for root, name, head in destinations:
                if repository(root) != (root, name, head):
                    raise ValueError(f"Target repository changed during synchronization: {name}")

        verify_inputs()
        for root, head, relative, before in observations:
            if signature(snap(root, head, relative)) != signature(before):
                raise ValueError(f"Changed during preflight: {relative}")
        completed = []
        try:
            for root, head, relative, before, desired in [*writes, *receipts]:
                verify_inputs()
                for old_root, old_head, old_relative, _, done in completed:
                    if signature(snap(old_root, old_head, old_relative)) != signature(done):
                        raise ValueError(f"Applied file changed concurrently: {old_relative}")
                if signature(snap(root, head, relative)) != signature(before):
                    raise ValueError(f"Target changed during synchronization: {relative}")
                _atomic_write(safe_file(root, relative), desired["data"], desired["mode"])
                completed.append((root, head, relative, before, desired))
            verify_inputs()
            adopted = {(root, relative): desired for root, _, relative, _, desired in completed}
            for root, head, relative, before in observations:
                final = adopted.get((root, relative), before)
                if signature(snap(root, head, relative)) != signature(final):
                    raise ValueError(f"Final content verification failed: {relative}")
        except (OSError, ValueError) as error:
            unresolved = []
            for root, head, relative, before, desired in reversed(completed):
                try:
                    expected_name = next(name for destination, name, _ in destinations if destination == root)
                    prior_index = next(state for index_root, index_path, state in indexes if index_root == root and index_path == relative)
                    if repository(root) != (root, expected_name, head) or index_file(root, relative) != prior_index:
                        unresolved.append(relative)
                        continue
                    if signature(snap(root, head, relative)) == signature(desired):
                        _atomic_write(safe_file(root, relative), before["data"], before["mode"])
                    else:
                        unresolved.append(relative)
                except (OSError, ValueError):
                    unresolved.append(relative)
            detail = f"; concurrent files retained: {', '.join(unresolved)}" if unresolved else "; task writes rolled back"
            raise ValueError(f"Incomplete synchronization: {error}{detail}") from error
        report["applied"] = True
    return report, 0 if apply or not different else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, action="append", required=True)
    parser.add_argument("--path", action="append", help="Explicit copied relative path; default: COMMON_PATHS")
    parser.add_argument("--delete", action="append", default=[], help="Explicit removed relative path, absent from source")
    parser.add_argument("--release", action="append", default=[], help="Release receipt ownership without touching local files or index")
    parser.add_argument("--release-local-configs", action="store_true", help="Release the nine LOCAL_CONFIG_PATHS; retain every local runtime file")
    parser.add_argument("--move", action="append", default=[], help="OLD=NEW; source NEW exists and OLD is absent")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect-source-head")
    parser.add_argument("--expect-source-content")
    parser.add_argument("--expect-head", nargs="+", action="extend", default=[])
    parser.add_argument("--claim", action="append", default=[], help="HOST/OWNER/REPO:PATH=SHA256:MODE or =absent")
    parser.add_argument("--migrate-receipt", action="store_true", help="Verify and migrate the recorded v1 baseline")
    args = parser.parse_args()
    try:
        expected, claims = {}, {}
        for item in args.expect_head:
            name, separator, value = item.partition("=")
            if not separator or name in expected or not re.fullmatch(r"[0-9a-f]{40,64}", value):
                raise ValueError("Invalid or repeated expected target HEAD")
            expected[name] = value
        for item in args.claim:
            location, separator, value = item.partition("=")
            name, colon, path = location.rpartition(":")
            if not separator or not colon or (name, path) in claims or not re.fullmatch(r"(?:[0-9a-f]{64}:100(?:644|755)|absent)", value):
                raise ValueError("Invalid or repeated ownership claim")
            claims[(name, checked_path(path))] = value
        releases = [*args.release, *(LOCAL_CONFIG_PATHS if args.release_local_configs else ())]
        copied = list(args.path) if args.path is not None else ([] if args.move or args.delete or releases else None)
        deleted = list(args.delete)
        for item in args.move:
            old, separator, new = item.partition("=")
            if not separator:
                raise ValueError("Move must be OLD=NEW")
            deleted.append(old)
            copied.append(new)
        report, status = synchronize(
            args.source, args.target, apply=args.apply, expected=expected,
            expected_source=args.expect_source_head, expected_content=args.expect_source_content,
            paths=copied, deletes=deleted, releases=releases, claims=claims, migrate=args.migrate_receipt,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Sync: {error}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(status)


if __name__ == "__main__":
    main()
