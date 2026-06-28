# AI Research Assistant Guide

This project uses a compact cloud-agent setup. `.cursorrules` is the
authoritative policy; this file only records research-specific guidance.

## Research Priorities

- Preserve reproducibility with stable paths, explicit configuration, and
  recorded verification commands.
- Treat economic assumptions as first-class objects: identifying assumptions,
  timing, exclusion restrictions, equilibrium restrictions, and data filters.
- Mark uncertain mathematics or claims with `\unproven{}` or `TODO_HUMAN`.
- Verify citation claims against the cited source before relying on them.
- Keep formulas, estimation code, tables, and prose aligned.

## Context Discipline

- Load only files needed for the current question.
- Use `.agents/skills/*/SKILL.md` as lightweight routing indexes.
- Read `.resources` clones only after a matching skill points to a specific
  file.
- Do not load whole reference repositories, `docs/ai`, or README files at
  startup.

## Verification

- Agent configuration and tests: `make test`, then `make check`.
  The current repository test suite has been reset; pytest remains available
  and runs automatically when test files are added.
- Python execution: `pixi run python ...`.
- Manuscripts and slides: compile or render the actual artifact.
- Expensive analyses: run a small deterministic sample first.
- Data pipelines: use named columns, `left_join`, and economic invariant
  assertions such as nonnegative prices or feasible shares.

## Git and DVC

Read-only inspection is allowed. Mutating Git, remote Git, collaboration, and
DVC state-changing operations require an explicit user request. Never manually
edit `.dvc` metadata.
