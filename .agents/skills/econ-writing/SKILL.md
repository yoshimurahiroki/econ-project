---
name: econ-writing
description: Use for economics-paper writing, empirical identification prose, AEA-style replication/disclosure checks, theory-to-text alignment, and paper revision. Loads local writing references only when needed.
origin: econ-project
---

# Econ Writing

Lightweight index for economics writing and revision.

## Use For

- Economics manuscripts, slides, abstracts, introductions, and referee responses.
- Empirical identification prose and theory-to-text alignment.
- AEA-style replication, disclosure, and data/code availability language.

## Reference loading

Do not read the whole repository. Open exactly one starting file:

- Task resource index: `docs/ai/resources.md`
- Local condensed project reference: `docs/ai/econ_writing_reference.md`

## Writing Lenses

- Identification: assumptions, timing, exclusion restrictions, threats.
- Estimation: standard errors, clustering, sample construction, robustness.
- Theory-to-code alignment: formulas, code, tables, and narrative match.
- Disclosure: AI use, replication package, data/code availability.
- Writing: economics style, contribution, mechanism, and limitations.

## Boundaries

- Use `econ-research-feedback` for adversarial or referee-style critique.
- Use `causal-inference-resources` before writing if the identification design is
  still unsettled.
- Do not invent citations or claims. Verify citations before final prose.

Mark uncertain claims with `TODO_HUMAN` or `\unproven{}`.
