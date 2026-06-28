#!/usr/bin/env python3
"""Validate the minimal cloud-agent surface for econ-project."""

import os
import re
import subprocess
from pathlib import Path

POINTER_CONTENT = (
    "# econ-project AI rules\n\n"
    "Read and follow `.cursorrules`; it is the single authoritative policy.\n"
    "Do not duplicate or extend its rules in this file.\n"
)

POINTER_TARGETS = (
    "AGENTS.md",
    "CLAUDE.md",
    "CODEX.md",
    ".antigravityrules",
    ".clinerules",
    ".windsurfrules",
    ".agents/AGENTS.md",
    ".claude/AGENTS.md",
)

COPILOT_CONTENT = (
    "# GitHub Copilot instructions\n\n"
    "Read and follow [`.cursorrules`](../.cursorrules). "
    "It is the authoritative policy.\n"
)

CURSOR_RULE_CONTENT = (
    "---\n"
    "description: econ-project policy pointer\n"
    "globs: *\n"
    "---\n\n"
    "Read and follow `.cursorrules`; it is the single authoritative policy.\n"
    "Do not duplicate or extend its rules in Cursor rules.\n"
)

ALLOWED_SKILLS = {
    "academic-research-resources",
    "causal-inference-resources",
    "econ-ai-resources",
    "econ-research-feedback",
    "econ-writing",
}

def configured_reference_paths() -> tuple[str, ...]:
    value = os.environ.get("AI_REFERENCE_REPOSITORIES", "")
    enabled = any(os.environ.get(key, "").strip().lower() in {"1", "true", "yes", "on"}
                  for key in ("ECC_REQUIRE_AI_REFERENCES", "ECC_FETCH_AI_REFERENCES"))
    if enabled and not value:
        raise ValueError("Set explicit AI_REFERENCE_REPOSITORIES triples before enabling references")
    paths = []
    for number, line in enumerate(value.split("\n"), 1):
        line = line.strip(" \t")
        if not line:
            continue
        fields = re.split(r"[ \t]+", line)
        if (len(fields) != 3 or fields[0] not in {"econ", "research"}
                or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", fields[1]) is None
                or re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", fields[2]) is None):
            raise ValueError(f"Invalid reference triple on line {number}")
        group, repository, name = fields
        root = "econ-ai" if group == "econ" else "research-ai"
        paths.append(f".resources/{root}/{name}")
    return tuple(paths)


REQUIRED_FILES = (
    ".cursorrules",
    ".agents/skills/academic-research-resources/SKILL.md",
    ".agents/skills/causal-inference-resources/SKILL.md",
    ".agents/skills/econ-ai-resources/SKILL.md",
    ".agents/skills/econ-research-feedback/SKILL.md",
    ".agents/skills/econ-writing/SKILL.md",

) + configured_reference_paths()


def validate_content(path: Path, content: str) -> list[str]:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return []
    return [f"{path}: content differs from the compact pointer"]


def validate_project_policy(base_path: Path) -> list[str]:
    violations: list[str] = []

    for relative_path in POINTER_TARGETS:
        path = base_path / relative_path
        if path.is_symlink():
            violations.append(f"{relative_path}: must be a regular compact pointer file")
            continue
        violations.extend(validate_content(path, POINTER_CONTENT))

    violations.extend(
        validate_content(
            base_path / ".github" / "copilot-instructions.md",
            COPILOT_CONTENT,
        )
    )
    violations.extend(
        validate_content(
            base_path / ".cursor" / "rules" / "01_project_policy.mdc",
            CURSOR_RULE_CONTENT,
        )
    )
    return violations


def validate_required_surface(base_path: Path) -> list[str]:
    violations = [
        f"{relative_path}: required file or on-demand reference is missing"
        for relative_path in REQUIRED_FILES
        if not (base_path / relative_path).exists()
    ]

    skills_path = base_path / ".agents" / "skills"
    actual_skills = {path.name for path in skills_path.iterdir() if path.is_dir()}
    extra_skills = sorted(actual_skills - ALLOWED_SKILLS)
    if extra_skills:
        violations.append(f".agents/skills: unexpected always-available skills {extra_skills}")

    return violations


def validate_mcp(base_path: Path) -> list[str]:
    result = subprocess.run(
        ["bash", "scripts/setup_ide_mcp.sh", "--check"],
        cwd=base_path,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        if result.stdout.strip():
            print(result.stdout.strip())
        return []

    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    return [f"MCP configuration check failed:\n{output.strip()}"]


def main() -> None:
    base_path = Path(__file__).resolve().parents[1]

    violations = []
    violations.extend(validate_project_policy(base_path))
    violations.extend(validate_required_surface(base_path))
    violations.extend(validate_mcp(base_path))

    if violations:
        print("AI surface validation failed:")
        for violation in violations:
            print(f"- {violation}")
        raise SystemExit(1)

    print("AI surface validation passed.")


if __name__ == "__main__":
    main()
