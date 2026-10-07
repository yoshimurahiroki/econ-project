#!/usr/bin/env python3
"""Export selected research instructions into a fresh Project attachment folder."""

import argparse
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PROSE = ["econ-assertive", "econ-style"]


def export(target: Path, profile: str, skills: list[str] | None = None) -> int:
    target = target.resolve()
    if target.exists() or target.is_relative_to(ROOT):
        raise ValueError("Choose a fresh output directory outside the repository")
    available = {p.parent.name: p for p in (ROOT / ".agents/skills").glob("*/SKILL.md")}
    selected = PROSE if profile == "bridge" else list(dict.fromkeys((skills or sorted(available)) + PROSE))
    if profile == "bridge" and skills:
        raise ValueError("Use --skills with the standalone profile")
    if any(name not in available for name in selected):
        raise ValueError("Select an installed skill")
    mapping = {
        ROOT / ".cursorrules": "REPO_POLICY.md",
        ROOT / "docs/ai/project_instructions.txt": "PROJECT_INSTRUCTIONS.txt",
        ROOT / "docs/ai/repo_context.md": "REPO_CONTEXT.md",
        ROOT / "docs/ai/sources.md": "METHOD_SOURCES.md",
    }
    study_entry = ROOT / "docs/research/master-project-addendum.txt"
    if study_entry.exists():
        mapping[study_entry] = "STUDY_ENTRY_POINT.txt"
    if profile == "bridge":
        mapping.update({
            ROOT / "docs/ai/project_bridge.txt": "BRIDGE_INSTRUCTIONS.txt",
            ROOT / ".agents/skills/econ-workflow/references/descriptive-model.md": "RESEARCH_WORKFLOW.md",
        })
    for name in selected:
        prefix = name.upper().replace("-", "_")
        mapping[available[name]] = f"{prefix}.md"
        for ref in sorted((available[name].parent / "references").glob("*.md")):
            mapping[ref] = f"{prefix}__{ref.stem.upper().replace('-', '_')}.md"
    revision = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    origin = subprocess.run(["git", "-C", str(ROOT), "config", "--get", "remote.origin.url"], capture_output=True, text=True, check=False)
    remote = re.search(r"github\.com[:/]([^/]+/[^/?#]+?)(?:\.git)?$", origin.stdout.strip())
    source_url = f"https://github.com/{remote.group(1)}/blob/{revision.stdout.strip()}/" if remote and revision.returncode == 0 else None
    contents = {}
    for source, filename in mapping.items():
        text = source.read_text(encoding="utf-8")
        def rewrite(match):
            link = match.group(1)
            parts = urlsplit(link)
            if parts.scheme or link.startswith("//") or not parts.path:
                return match.group(0)
            linked = (ROOT / unquote(parts.path).lstrip("/") if parts.path.startswith("/") else source.parent / unquote(parts.path)).resolve()
            fragment = "#" + parts.fragment if parts.fragment else ""
            if linked in mapping:
                return f"]({mapping[linked]}{fragment})"
            if source_url and linked.is_relative_to(ROOT) and linked.is_file():
                return f"]({source_url}{quote(linked.relative_to(ROOT).as_posix())}{fragment})"
            return match.group(0)
        text = re.sub(r"\]\(([^)]+)\)", rewrite, text)
        if filename.endswith("INSTRUCTIONS.txt") and len(text.replace("\n", "\r\n")) > 8000:
            raise ValueError("Project instructions exceed 8,000 characters")
        contents[filename] = text
    lines = ["# Research task index", "", "Match the current request to the relevant method. Its steps and references apply to that request. REPO_POLICY.md owns content scope and execution; ECON_ASSERTIVE.md owns the final deletion and expression pass. Consult style profiles for writing or wording edits. ECON_STYLE.md creates profiles on request.", ""]
    for name in selected:
        text = contents[mapping[available[name]]]
        description = next(line.removeprefix("description: ") for line in text.splitlines() if line.startswith("description: "))
        lines.append(f"- [{name}]({mapping[available[name]]}): {description}")
    contents["ECON_INDEX.md"] = "\n".join(lines) + "\n"
    contents["SOURCE.md"] = "# Export source\n\n" + (
        f"Base commit: `{revision.stdout.strip()}`. Export includes the current working files.\n"
        if revision.returncode == 0 else "Source: the instruction files supplied to this export.\n"
    )
    target.mkdir(parents=True)
    for filename, text in contents.items():
        (target / filename).write_text(text, encoding="utf-8")
    return len(contents)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["bridge", "standalone"], default="standalone")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skills", nargs="+")
    args = parser.parse_args()
    try:
        count = export(args.output, args.profile, args.skills)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Export: {error}\n")
    print(f"Exported {count} files to {args.output}")


if __name__ == "__main__":
    main()
