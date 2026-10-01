---
name: econ-style
description: Create or update custom economics style exemplars from user-selected papers on explicit request. Ordinary drafting uses the installed default empirical-micro exemplars.
---

# Custom economics exemplars

Run only when the user asks to create, update or learn custom style exemplars. Ordinary writing uses [econ-assertive](../econ-assertive/SKILL.md) and its [default-micro profile](../econ-assertive/references/default-micro.md). A paper supplied for explanation or literature research does not activate style learning.

## Create

Use the user's papers, language, target section and requested scope. Retrieve exact source files through the appropriate Project-file tool or connector. Read the relevant complete sections and the passages supporting each selected writing move. Inspect page images when parsed text is garbled. When the user asks you to choose references, use a small set of relevant empirical-micro papers from the available collection and primary sources. Do not create a profile from abstracts or imagined passages.

Extract paragraph functions, order of claims and evidence, syntax, literal verbs, authorial voice, literature positioning and result reporting. Select the moves that fit the requested section. Resolve differing source styles by that section's purpose and the user's stated preference. The profile inherits econ-assertive: hedges, concessions, qualifications, rhetorical contrasts and emphasis remain zero by default. Exclude source rhetoric that conflicts with those rules.

Produce one Markdown profile with its name, language and scope; exact source/version/URL/page records; a few source-based paragraph adaptations; and short transfer directions. Provide English and Japanese adaptations when requested, otherwise use the requested language. Label adaptations as adaptations. Use source facts only inside the source-study examples. In target-text examples use supplied target evidence or explicit placeholders. Keep quotation within permitted source limits and do not copy distinctive prose. Do not add scores, a separate diagnosis, an audit report, an installer or a second editing pass.

Return the requested profile. Save it to the user's specified path when asked; for a requested repository save without a path, use `docs/ai/custom-style.md` after reading any existing file. Update the same profile for a revision. Preserve the installed default. Do not commit original PDFs or private source passages to a public repository.

## Select and apply

The current task's explicit profile selection has priority over an explicitly set persistent project choice; otherwise use default-micro. The existence of a custom file does not activate it. Creating a profile alone does not change the persistent choice. A request to create and use a profile applies it to that task. A task-scoped selection expires with the task. "Use the default" selects default-micro immediately.

Read the selected profile once and reuse it. For a section the custom profile does not cover, use the corresponding default example. Read an explicitly selected file before applying it; retrieve a missing file or ask for that file instead of silently claiming to use it. A language or section adaptation keeps the user's requested genre and structure.

Apply syntax, paragraph development and register to the target evidence. Keep target numbers, comparisons, notation, citations and authorship. Do not import a source study's findings, institutional details or assumptions into the target study. Return only the requested profile or revised text. The selected research module keeps ownership of substance.

## Adaptation source

The source-to-profile workflow draws on `lishn6/awesome-ai-econ-research-writing`, `skills/paper-style-learner/SKILL.md`, blob `5b3bce7949e0f9847c17c3ad18274abcbe0f0650`, read 2026-10-01: https://github.com/lishn6/awesome-ai-econ-research-writing/blob/main/skills/paper-style-learner/SKILL.md

This local implementation uses explicit opt-in creation, a persistent default, source-based examples and one writing pass. It omits the upstream mandatory report structure and learning of hedging or caveat patterns.
