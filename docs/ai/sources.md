# Source review and design decisions

Review date: 2026-09-27. This record identifies the source material read and the local adaptations made from it.

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

Direct drafting is followed by one meaning-based necessity review using the current claim and source evidence.

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
| https://github.com/rhstanton/project_template | Traceable data, code and publication exhibits; selectable languages | Keep a minimal claim-to-code map and the repository's chosen languages. |
| https://github.com/maxwell2732/codex-stata-for-economists/blob/main/README.en.md | Numerical claims tied to logs and output tables | Carry run evidence with each reportable result. |
| https://github.com/pedrohcgs/claude-code-my-workflow | Replication checks, claim provenance and handoffs | Use targeted checks and existing task records; retain the single-agent default. |
| https://github.com/tsdfs930514/econ-research-workflow | Lifecycle skills and cross-validation | Keep task routing; additional execution follows a concrete research need. |
| https://developers.openai.com/blog/skills-agents-sdk | Short repository policy, task metadata, selected bodies and deterministic scripts | Keep one policy, bounded discovery and no default external-repository loading. |
| https://learn.chatgpt.com/docs/agent-configuration/agents-md | Repository-level instruction discovery | Retain compact host pointers to the existing policy owner. |


## Semantic content selection (2026-10-06)

The current user instruction establishes semantic admission and affirmative direct prose. The local adaptation uses one writing pass in econ-assertive: select the requested answer and its supporting claims, delete rejected propositions completely, and reconstruct the paragraph from admitted content. Methods retain the evidence required by their requested research object.

| Actual skill and inspected revision | Sections read | Local adaptation |
| --- | --- | --- |
| [Kiterlin/anti-defensive-writing](https://github.com/Kiterlin/anti-defensive-writing/blob/c7edf8fc91ae9c4f7e58345bd12934bb4cf41c46/skill/anti-defensive-writing/SKILL.md), commit c7edf8fc91ae9c4f7e58345bd12934bb4cf41c46 | Core Rule; Preserve Necessary Precision; Rewrite Procedure; Writing Principles; Examples; Final Pass; Additional Rules | Claim-first organization, full deletion and paragraph reconstruction; the user admission rule decides retained content before wording. |
| [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu/blob/986da6ffc89316a90e509d007c1efe1fc59057e6/SKILL.md), commit 986da6ffc89316a90e509d007c1efe1fc59057e6 | §1 meaning, register, paragraph relations, subject/object alignment, literal verbs and information; §2-3 execution/output | Preserve the admitted claim's factual function, numerical strength, attribution and causal status; align subjects and predicates in the requested register. |
| [makotofalcon/humanizer-ja](https://github.com/makotofalcon/humanizer-ja/blob/4cc01cdd5aff4102888e9396c3ba16da99828f78/SKILL.md), commit 4cc01cdd5aff4102888e9396c3ba16da99828f78 | §§11, 11b, 12, 14, 15, 16 and 22-25; process and output sections | Delete inflated significance, appended evaluation, decorative contrasts and stock framing; retain stable economic terms. |

These are original local rules and examples adapted from the identified operations. The inspected repositories license their files under MIT: [Kiterlin, copyright 2026](https://github.com/Kiterlin/anti-defensive-writing/blob/c7edf8fc91ae9c4f7e58345bd12934bb4cf41c46/LICENSE), [nanaism, copyright 2026](https://github.com/nanaism/yomiyasu/blob/986da6ffc89316a90e509d007c1efe1fc59057e6/LICENSE), and [humanizer-ja, copyright 2025](https://github.com/makotofalcon/humanizer-ja/blob/4cc01cdd5aff4102888e9396c3ba16da99828f78/LICENSE).

Earlier wording references recorded in patterns.md on 2026-10-01 remain attributable to [blader/humanizer](https://github.com/blader/humanizer/blob/main/SKILL.md), [softaworks/writing-clearly-and-concisely](https://github.com/softaworks/agent-toolkit/blob/main/skills/writing-clearly-and-concisely/SKILL.md), [Keizai Seminar's introduction article](https://note.com/keisemi/n/n6442eac8af25), and [Cochrane's Writing Tips](https://www.fma.org/assets/docs/membercontent/writing_cochrane.pdf). Their recorded operations concern paragraph development, literal subjects and direct contributions. The default-micro corpus, its inspected-version records and its source locators remain in their existing reference.

## Semantic admission and expression (2026-10-06 refinement)

The user requires categorical deletion of hedging, concession, qualifying commentary, ornament and their substitutes. Each retained proposition binds to the requested answer or a specific admitted claim. The adaptation deletes rejected meanings at sentence, clause, modifier and implied-premise level, then composes the answer from admitted claims. Existing source/version records and one internal writing pass supply provenance and review.

| Current source and inspected revision | Read material | Local operation |
| --- | --- | --- |
| [Kiterlin/anti-defensive-writing](https://github.com/Kiterlin/anti-defensive-writing/blob/c7edf8fc91ae9c4f7e58345bd12934bb4cf41c46/skill/anti-defensive-writing/SKILL.md), c7edf8fc91ae9c4f7e58345bd12934bb4cf41c46 | Core and additional rules, rewrite procedure, patterns, examples and English/Chinese sections | Organize around the claim and rebuild paragraphs. Apply semantic admission to positive scope conversions, limitation allowances, hedges and reviewer framing. |
| [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu/blob/986da6ffc89316a90e509d007c1efe1fc59057e6/SKILL.md), 986da6ffc89316a90e509d007c1efe1fc59057e6 | §1 and its subsections, §2 procedure, §3 output | Preserve admitted factual relations and align actor, object and predicate. Apply deletion to evaluations, metaphorical implications and corrective contrasts. |
| [makotofalcon/humanizer-ja](https://github.com/makotofalcon/humanizer-ja/blob/4cc01cdd5aff4102888e9396c3ba16da99828f78/SKILL.md), 4cc01cdd5aff4102888e9396c3ba16da99828f78 | Principles, human voice, patterns 1–25 and 11b, process and output | Delete appended significance, vague authority, promotion and stock conclusions. Use the admission rule for residual hedges, personal voice and digressions. |
| [Silas1929/econ-writing](https://github.com/Silas1929/econ-writing/blob/ba636f282fc80b12dbed623752b76c1513cd73ea/SKILL.md), ba636f282fc80b12dbed623752b76c1513cd73ea | Complete SKILL: core principles, quick reference, four modes and general guidelines | State results first with plain verbs. Apply categorical deletion to hedge allowances, one-off usage, alternate contrast forms and routine conclusion caveats. |

These compact rules and examples are original adaptations. The existing econ-assertive owner handles content and wording; related methods preserve admitted economic claims, evidence and logical polarity.
