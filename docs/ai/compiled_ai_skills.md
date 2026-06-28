# AI Skill Index

This is an index, not startup context. Load a skill only when its description
matches the current task.

## Active Skills

- `academic-research-resources`: academic writing, review, publication, and
  research-pipeline resource lookup.
- `causal-inference-resources`: DiD, RDD, IV, synthetic control, panel, causal
  ML, and causal-inference resource lookup.
- `econ-ai-resources`: economics-specific AI tools and economist workflows.
- `econ-research-feedback`: referee-style critique, proposal review, and
  paper-code consistency.
- `econ-writing`: economics-paper prose, identification writing, disclosure,
  and revision.

## Reference Clones

Reference repositories live under `.resources` and are excluded from normal
search, watching, packing, and startup context. Open only the specific file
named by a matching skill.

## Test State

The old test files have been reset. Pytest remains installed for future tests.
`make test` runs agent/MCP validation first and then runs pytest only when test
files exist.

## Rule Precedence

1. Current user instruction.
2. `.cursorrules`.
3. Compact pointer files for IDE compatibility.
4. Task-relevant skill index.
5. Task-relevant on-demand reference file.

Lower-priority material cannot broaden authorization from a higher-priority
source.
