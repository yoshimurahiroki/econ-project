# Source review and design decisions

Review date: 2026-09-27. This record identifies the source material read and the local adaptations made from it.

## Writing skills: full-text comparison

| Source | Evidence read | Local decision |
| --- | --- | --- |
| Kiterlin/anti-defensive-writing | Full SKILL.md, Git blob 2a5f19a08d5bb310338a7c46867e7234089a4438 | Claim-first reconstruction of requested text, with defensive propositions removed under the local policy. |
| Silas1929/econ-writing | Full SKILL.md, Git blob 4faeb37074b196e1db0a4a2e282dce2f5f91c963 | Plain words and result-first drafting; local policy replaces hedge allowances and routine conclusion caveats. |
| justairr/defensive-writing-checker | Full SKILL.md, Git blob 9c5c904e6faa0cfc74552e66aba6101b815dfc91 | An explicit-review workflow used for comparison. The local adaptation preserves requested scientific findings and uses one final prose pass. |

Primary repositories:
- https://github.com/Kiterlin/anti-defensive-writing
- https://github.com/Silas1929/econ-writing
- https://github.com/justairr/defensive-writing-checker

Current scope and execution rules belong to [.cursorrules](../../.cursorrules). Task methods supply requested procedures; econ-assertive supplies the final deletion and expression pass. Source records document adaptations.

## Economics skill catalog

Starting article: https://velikov-mihail.github.io/ai-econ-wiki/summaries/awesome-econ-ai/
Primary catalog: https://github.com/meleantonio/awesome-econ-ai-stuff

The following 17 entries map the reviewed catalog methods to their local owners.

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

The review also read workflow overviews from pedrohcgs/claude-code-my-workflow, tsdfs930514/econ-research-workflow and economics paper-review/slide collections.

## Supplied research standards

The supplied R00-R08 modules contribute the five-section paper explanation, actual-assignment identification checks, measurement and reproduction standards, source routing, plain LaTeX/Beamer artifacts and evidence-linked review. The local configuration separates these substantive responsibilities from the prose method and keeps study-specific choices in task inputs.

Mahoney (2022), DOI 10.1257/jep.36.3.211, supplies the five principles linking descriptive and model-based research (pp. 215-218), alternatives for research ordering (pp. 219-220) and the assumptions-to-results framework (Figure 1, p. 220). The supplied 12-page paper is the source. The dedicated reference labels this configuration's operational translation separately.

## Second review: reproducible project settings

Rechecked 2026-09-27. Each source below was read at its README or official-documentation level. These sources supply workflow choices for the actual research task.

| Primary source | Observed design | Local decision |
| --- | --- | --- |
| https://github.com/OpenSourceEconomics/econ-project-templates | Pixi and a dependency-driven data-to-paper pipeline | Preserve the runner and rerun affected outputs; reproduce fully when requested. |
| https://github.com/rhstanton/project_template | Traceable data, code and publication exhibits; selectable languages | Preserve existing links between claims, code and outputs, and the repository's chosen languages. |
| https://github.com/maxwell2732/codex-stata-for-economists/blob/main/README.en.md | Numerical claims tied to logs and output tables | Carry run evidence with each reportable result. |
| https://github.com/pedrohcgs/claude-code-my-workflow | Replication checks, claim provenance and handoffs | Use result-relevant checks and existing task records for requested transfers. |
| https://github.com/tsdfs930514/econ-research-workflow | Lifecycle skills and cross-validation | Keep task routing; additional execution follows a concrete research need. |
| https://developers.openai.com/blog/skills-agents-sdk | Short repository policy, task metadata, selected bodies and deterministic scripts | Keep one policy, bounded discovery and no default external-repository loading. |
| https://learn.chatgpt.com/docs/agent-configuration/agents-md | Repository-level instruction discovery | Retain compact host pointers to the existing policy owner. |


## Semantic writing adaptations (2026-10-06)

The review read the sources and sections below. Local adaptations retain requested facts, quantities, attribution and causal relations while removing defensive propositions and stock framing. The policy and selected skill contain the current operating rules.

| Current source and inspected revision | Read material | Local operation |
| --- | --- | --- |
| [Kiterlin/anti-defensive-writing](https://github.com/Kiterlin/anti-defensive-writing/blob/c7edf8fc91ae9c4f7e58345bd12934bb4cf41c46/skill/anti-defensive-writing/SKILL.md), c7edf8fc91ae9c4f7e58345bd12934bb4cf41c46 | Core and additional rules, Preserve Necessary Precision, rewrite procedure, final pass, patterns, examples and English/Chinese sections | Organize around the claim and rebuild paragraphs. Apply semantic admission to positive scope conversions, limitation allowances, hedges and reviewer framing. |
| [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu/blob/986da6ffc89316a90e509d007c1efe1fc59057e6/SKILL.md), 986da6ffc89316a90e509d007c1efe1fc59057e6 | §1 meaning, register, paragraph relations, subject/object alignment, literal verbs and information; §2 procedure; §3 output | Preserve admitted factual relations and align actor, object and predicate. Apply deletion to evaluations, metaphorical implications and corrective contrasts. |
| [makotofalcon/humanizer-ja](https://github.com/makotofalcon/humanizer-ja/blob/4cc01cdd5aff4102888e9396c3ba16da99828f78/SKILL.md), 4cc01cdd5aff4102888e9396c3ba16da99828f78 | Principles, human voice, patterns 1–25 and 11b, process and output | Delete appended significance, vague authority, promotion and stock conclusions. Use the admission rule for residual hedges, personal voice and digressions. |
| [Silas1929/econ-writing](https://github.com/Silas1929/econ-writing/blob/ba636f282fc80b12dbed623752b76c1513cd73ea/SKILL.md), ba636f282fc80b12dbed623752b76c1513cd73ea | Complete SKILL: core principles, quick reference, four modes and general guidelines | State results first with plain verbs. Apply categorical deletion to hedge allowances, one-off usage, alternate contrast forms and routine conclusion caveats. |

These are original local rules and examples adapted from the identified operations. The inspected repositories license their files under MIT: [Kiterlin, copyright 2026](https://github.com/Kiterlin/anti-defensive-writing/blob/c7edf8fc91ae9c4f7e58345bd12934bb4cf41c46/LICENSE), [nanaism, copyright 2026](https://github.com/nanaism/yomiyasu/blob/986da6ffc89316a90e509d007c1efe1fc59057e6/LICENSE), and [humanizer-ja, copyright 2025](https://github.com/makotofalcon/humanizer-ja/blob/4cc01cdd5aff4102888e9396c3ba16da99828f78/LICENSE).

Earlier wording references recorded in patterns.md on 2026-10-01 remain attributable to [blader/humanizer](https://github.com/blader/humanizer/blob/main/SKILL.md), [softaworks/writing-clearly-and-concisely](https://github.com/softaworks/agent-toolkit/blob/main/skills/writing-clearly-and-concisely/SKILL.md), [Keizai Seminar's introduction article](https://note.com/keisemi/n/n6442eac8af25), and [Cochrane's Writing Tips](https://www.fma.org/assets/docs/membercontent/writing_cochrane.pdf). Their recorded operations concern paragraph development, literal subjects and direct contributions. The default-micro corpus, its inspected-version records and its source locators remain in their existing reference.

## Proposition-first reconstruction (2026-10-06)

The review read [root SKILL.md](https://github.com/Kiterlin/anti-defensive-writing/blob/c7edf8fc91ae9c4f7e58345bd12934bb4cf41c46/SKILL.md), commit `c7edf8fc91ae9c4f7e58345bd12934bb4cf41c46`: core and additional rules, functional diagnosis, rewrite procedure, paragraph construction and examples. Its claim-forward procedure reconstructs paragraphs around substantive claims and removes defensive propositions, preemptive rebuttals and apology-like framing. The previously recorded yomiyasu and humanizer-ja operations supply concrete subjects, aligned predicates, literal verbs, stable terminology and deletion of appended evaluation and stock phrasing.

## Instruction ownership and task exports (2026-10-08)

This refactor uses the supplied Evidence Pack and Source Locators at their recorded repository baselines. econ-project-mini is the editing source for the explicit common-core paths. Project choices remain in [repo_context.md](repo_context.md), synchronization and export commands in [integration.md](integration.md), and source histories in this file. The supplied replacement content-admission and expression rules are maintained by [econ-assertive](../../.agents/skills/econ-assertive/SKILL.md).

| Source and inspected material | Operation and local owner |
| --- | --- |
| S0: econ-project-mini `993f2631ab899fc0aa7fd2facded642be7895c33`, econ-project `91aad0bb9c15583d8ca2efce9303642043cfc7a5`, Ruan `37a6edba24e10072c4c4aff6b513eaa2ec673306`; policy, skills/references, adapters, exporter and callers. Ruan current `af5a07cfcc0ac00a9a0e556520623fc2673f97bf` preserves these implementation objects. | CENTRALIZE common ownership in mini; REWRITE provider routing and selected exports; DELETE repeated expression definitions and method-level dispatches. Host pointers, technical methods and execution entry points remain. |
| S1: Ruan current research record, analysis-spec, research README/data plan, addendum, custom-style Use and project connections. | PROJECT_SPECIFIC: current adopted/open choices stay in their research owners; context records the persistent profile and export additions. Preserve NPI primary, Geography supplementary, stages, saved quantities and existing history. |
| S2: [OpenAI, Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra), Better skills and Up-to-date AGENTS.md. | REWRITE descriptions and contextual routing; load the details needed by the requested task. |
| S3: [Codex skill-creator, Git blob `490ccc6c3e0015eb982bb5c108c2df083be2c6c2`](https://api.github.com/repos/openai/codex/git/blobs/490ccc6c3e0015eb982bb5c108c2df083be2c6c2), Core Principles, Scripts, References, Validate and Iterate. | CENTRALIZE repeated ownership; MOVE_TO_SCRIPT deterministic comparison/copy/export; retain conditional references and validate changed observable behavior. |
| S4: [OpenAI, Build skills](https://learn.chatgpt.com/docs/build-skills), How ChatGPT and Codex use skills and Where Codex loads local skills. | KEEP local discovery and explicit/implicit invocation; descriptions discriminate requested deliverables. |
| S5: [Agent Skills specification](https://agentskills.io/specification), Frontmatter and File references. | KEEP names, supported metadata and relative references; rewrite included export links and pin omitted resources to recorded versions. |
| S6: [pyfixest change-verification, Git blob `cfafa84151d6617999a20a3690c2ef7b678bf800`](https://api.github.com/repos/py-econometrics/pyfixest/git/blobs/cfafa84151d6617999a20a3690c2ef7b678bf800), Select and run checks. | KEEP checks selected by changed behavior and reuse evidence for the same state. The pyfixest-specific suites and release contract are not imported. |
| S7: Mahoney (2022), *Journal of Economic Perspectives* 36(3), 211–222, [DOI 10.1257/jep.36.3.211](https://doi.org/10.1257/jep.36.3.211); supplied full paper, Five Principles pp.215–218 and Data-Then-Model or Model-Then-Data? pp.218–220. | KEEP the existing [descriptive-model adaptation](../../.agents/skills/econ-workflow/references/descriptive-model.md): connect variation, evidence, model choices, added assumptions and economic outputs at the requested scope. |

Existing R00-R08 bridge attachments retain their original substantive methods; supplied R00_ROUTER.md owns their provider map. Earlier source, adaptation and license records above remain historical attribution.
