# Source review and design decisions

Review date: 2026-09-27. This record distinguishes source procedures from this configuration's own implementation. The local skills are newly written; no upstream installer, agent loop, MCP server or implementation is activated.

## Writing skills: full-text comparison

| Source | Evidence read | Local decision |
| --- | --- | --- |
| Kiterlin/anti-defensive-writing | Full SKILL.md, Git blob 2a5f19a08d5bb310338a7c46867e7234089a4438 | Use detection, function classification and rewriting. Replace the broad limitation allowance and automatic conversion to positive scope with the user's strict necessity gate. |
| Silas1929/econ-writing | Full SKILL.md, Git blob 4faeb37074b196e1db0a4a2e282dce2f5f91c963 | Use plain words and proactive drafting plus review. Replace one-hedge-per-claim and routine conclusion caveats with the zero-default policy. |
| justairr/defensive-writing-checker | Full SKILL.md, Git blob 9c5c904e6faa0cfc74552e66aba6101b815dfc91 | Compare its explicit-review workflow. The local skill runs by default and retains scientific findings independently of whether they favor the argument. Selective reporting rules are not imported. |

Primary repositories:
- https://github.com/Kiterlin/anti-defensive-writing
- https://github.com/Silas1929/econ-writing
- https://github.com/justairr/defensive-writing-checker

The new two-stage gate is an implementation of the current user's instructions. The detector supplies candidates. Necessity judgment uses the current claim and source evidence. Post-draft review is mandatory even after a phrase-clean scan. The audit record is internal by default.

## Economics skill catalog

Starting article: https://velikov-mihail.github.io/ai-econ-wiki/summaries/awesome-econ-ai/
Primary catalog: https://github.com/meleantonio/awesome-econ-ai-stuff

The following 17 entries are the task coverage map used in this request. It is a routing/adoption comparison, not an execution benchmark of upstream sample code.

| Catalog entry | Local owner |
| --- | --- |
| [research-ideation](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/ideation/research-ideation/SKILL.md) | econ-design |
| [lit-review-assistant](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/literature/lit-review-assistant/SKILL.md) | econ-literature |
| [latex-econ-model](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/theory/latex-econ-model/SKILL.md) | econ-design, econ-writing |
| [general-equilibrium-model-builder](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/theory/general-equilibrium-model-builder/SKILL.md) | econ-design |
| [stata-data-cleaning](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/data/stata-data-cleaning/SKILL.md) | econ-data |
| [api-data-fetcher](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/data/api-data-fetcher/SKILL.md) | econ-data |
| [r-econometrics](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/analysis/r-econometrics/SKILL.md) | econ-design, econ-data |
| [python-panel-data](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/analysis/python-panel-data/SKILL.md) | econ-design, econ-data |
| [stata-regression](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/analysis/stata-regression/SKILL.md) | econ-data |
| [academic-paper-writer](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/writing/academic-paper-writer/SKILL.md) | econ-writing |
| [latex-tables](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/writing/latex-tables/SKILL.md) | econ-writing |
| [beamer-presentation](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/communication/beamer-presentation/SKILL.md) | econ-writing |
| [econ-visualization](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/communication/econ-visualization/SKILL.md) | econ-writing |
| [sdd](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/engineering/sdd/SKILL.md) | econ-workflow |
| [techdebt](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/engineering/techdebt/SKILL.md) | econ-data |
| [commit-push-pr](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/engineering/commit-push-pr/SKILL.md) | repository policy |
| [code-simplifier](https://github.com/meleantonio/awesome-econ-ai-stuff/blob/main/_skills/engineering/code-simplifier/SKILL.md) | econ-data |

## Existing repository references

The prior repository configuration listed seven optional collections: hanlulong/econ-writing-skill, claesbackman/AI-research-feedback, matteocourthoud/awesome-causal-inference, meleantonio/awesome-econ-ai-stuff, hanlulong/awesome-ai-for-economists, Imbad0202/academic-research-skills and affaan-m/ECC. Their installed local pointer skills were inspected during this request. The final configuration uses self-contained task methods and retrieves external references for a specific dependency.

Additional comparison in the request covered repository workflow overviews including pedrohcgs/claude-code-my-workflow, tsdfs930514/econ-research-workflow and economics paper-review/slide collections. These overviews are discovery material, not empirical evidence of performance.

## Supplied research standards

The supplied R00-R08 modules contribute the five-section paper explanation, actual-assignment identification checks, measurement and reproduction standards, source routing, plain LaTeX/Beamer artifacts and evidence-linked review. The new configuration keeps these substantive responsibilities separate from the default prose gate. General repository files contain no private collection IDs, study-specific treatments, research-candidate verdicts or dataset choices.

Mahoney (2022), DOI 10.1257/jep.36.3.211, supplies the five principles linking descriptive and model-based research (pp. 215-218), alternatives for research ordering (pp. 219-220) and the assumptions-to-results framework (Figure 1, p. 220). The supplied 12-page paper is the source. The dedicated reference labels this configuration's operational translation separately.

## Product and performance evidence

Official integration sources are recorded in integration.md. Names and descriptions support task-triggered loading; skill bodies and references are read for the task. Configuration tests check structure, budgets, default wiring, exports, phrase detection and safe application. No live model-response adherence or billing reduction is estimated.

The base policies were read from mini commit 24383fdfd4fe63c0a2f711f1e31fbdcffd6cec8f and full commit 69460c417f7cfd065fb5b26810867e617171ab6b. GitHub reports 7,347 and 4,313 UTF-8 bytes for those policies. The budget command measures the final files and separately includes the default prose skill.

## Second review: reproducible project settings

Rechecked 2026-09-27. Each source below was read at its README or official-documentation level. The adopted procedures are locally implemented and tested; external runtimes are not installed.

| Primary source | Observed design | Local decision |
| --- | --- | --- |
| https://github.com/OpenSourceEconomics/econ-project-templates | Pixi and a dependency-driven data-to-paper pipeline | Preserve the existing runner and use input-dependent reruns; keep full release reproduction. |
| https://github.com/rhstanton/project_template | Traceable data, code and publication exhibits; selectable languages | Keep a minimal claim-to-code map and the repository's chosen languages. |
| https://github.com/maxwell2732/codex-stata-for-economists/blob/main/README.en.md | Numerical claims tied to logs and output tables | Carry run evidence with each reportable result. |
| https://github.com/pedrohcgs/claude-code-my-workflow | Replication checks, claim provenance and handoffs | Use targeted checks and existing task records; retain the single-agent default. |
| https://github.com/tsdfs930514/econ-research-workflow | Lifecycle skills and cross-validation | Keep task routing and cheap fixtures; cross-language replication follows a specific need. |
| https://developers.openai.com/blog/skills-agents-sdk | Short repository policy, task metadata, selected bodies and deterministic scripts | Keep one policy, bounded discovery and no default external-repository loading. |
| https://learn.chatgpt.com/docs/agent-configuration/agents-md | Repository-level instruction discovery | Retain compact host pointers to the existing policy owner. |

This revision also tests quoted generated prose, oversized skill names, source-contained export destinations and small configuration-only test fixtures. The GitHub workflow executes the standard-library checks on relevant configuration changes. File sizes measure context inputs; task accuracy and billed tokens require observed task runs.
