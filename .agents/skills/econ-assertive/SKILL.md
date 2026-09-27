---
name: econ-assertive
description: Default economics prose with direct drafting and a mandatory post-draft detect, assess, delete and revise pass.
---

# Direct research prose

Apply both stages to papers, explanations, notes, slides, captions and research responses. EDIT reruns them. Research checklists are not output inventories.

## Stage 1: draft directly

Select the answer, its evidence and required logical steps before writing. Default rhetorical hedges, concessions and scope disclaimers: zero. Use concrete subjects, direct verbs and one main claim per sentence. Keep one topic per paragraph. Let facts and estimates state the conclusion.

Delete textbook cautions, generic measurement warnings, hypothetical objections and repeated population boundaries. A true caution earns no space merely by being true. Do not recycle deleted content as a positive scope sentence, parenthesis, footnote, appendix or closing reminder. Preserve scientific meaning, numbers, signs, equations and attribution; a wording change adds no evidence or causal force.

## Stage 2: mandatory post-draft audit

Before delivery, scan the entire new draft, including headings, bullets, captions and notes. Detect both listed phrases and semantic paraphrases: concession frames, modal stacks, defensive qualifications, negative self-limitation and disguised scope disclaimers.

For each candidate, determine its function and the effect of deletion. Retain content only if the user requests that exact issue OR all three tests hold: name a specific claim or action in this answer that would be wrong; cite case-specific evidence of the error; supply the shortest factual repair. Generic appeals to accuracy, uncertainty, identification or transparency fail this test.

Assign one action: DELETE the nonessential proposition; REWRITE essential content as a direct factual statement; KEEP an indispensable technical expression or exact quotation. Keep a compact internal record of span, necessity evidence and action. Create an audit file only when requested.

Apply the actions. Recheck changed passages and affected claim/citation links. Confirm that deleted cautions have not resurfaced elsewhere. A phrase-clean draft still receives the semantic necessity check. For a requested audit-only task, report the findings without changing the source.

## Execution cost

Run `python scripts/style_guard.py PATH` on generated prose files to locate phrase candidates. The script is a detector, not a necessity judge. Reuse source evidence. Resolve one material evidence gap with targeted retrieval. Reuse the loaded skill. Recheck only changed passages after the first complete scan; avoid repeated whole-paper research or agent loops.

Return the requested artifact, without the internal audit or a style-compliance report. See [patterns](references/patterns.md). Quoted prose is scanned by default; `--skip-quotes` applies to source-verified quotations. Do not hide new prose in code or math.
