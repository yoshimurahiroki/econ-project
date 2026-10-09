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

## Information design and writing quality (2026-10-08)

The source passages below informed the existing skills and profiles. Shared information selection, clarity and continuity belong to econ-assertive; composition to econ-writing; meaning-preserving revision to econ-edit; source-based profile learning to econ-style. The adaptations use original wording and preserve scientific definitions, comparisons, quantities and conditions.

| Source and inspected version | Sections read and retained operation |
| --- | --- |
| [Silas1929/econ-writing](https://github.com/Silas1929/econ-writing/tree/ba636f282fc80b12dbed623752b76c1513cd73ea), `ba636f282fc80b12dbed623752b76c1513cd73ea` | `references/paragraph-composition.md` §§1–4, 6, 8–11; `references/sentence-structure.md` §§2, 6–9, 11–17: develop paragraph claims, unpack noun chains, identify referents and repair information order. |
| [lishn6/economics-writing-style](https://github.com/lishn6/awesome-ai-econ-research-writing/blob/639285453d451d765da66cfae559bc3e5e24d137/skills/economics-writing-style/SKILL.md), `639285453d451d765da66cfae559bc3e5e24d137` | Information Density, Logic and Paragraphs, Revision Discipline: select important economic content and make successive sentences explain it. |
| [lishn6/paper-style-learner](https://github.com/lishn6/awesome-ai-econ-research-writing/blob/639285453d451d765da66cfae559bc3e5e24d137/skills/paper-style-learner/SKILL.md), same revision | Style Extraction Priorities, Non-Negotiables and profile schema §§2–4, 7: learn reader functions, evidence order and technical-detail placement. |
| [dariia-m/academic_writing](https://github.com/dariia-m/my_claude_skills/blob/8a32ebf8e0ae5a7930621ea561055875d75533cb/academic_writing/SKILL.md), `8a32ebf8e0ae5a7930621ea561055875d75533cb` | §§0.1, 1, 3, 4.1, 8.2, 9–11, 15: link claims to evidence, economic explanation, notation and interpretation. |
| [dariia-m/econ_intro_writing](https://github.com/dariia-m/my_claude_skills/blob/8a32ebf8e0ae5a7930621ea561055875d75533cb/econ_intro_writing/SKILL.md), same revision | Core Structure, Empirical Approach, Detailed Results, Value-Added: introduce the question, comparison and knowledge gained in the reader's understanding order. |
| [Ecow0ker/econ-humanizer-skills](https://github.com/Ecow0ker/econ-humanizer-skills/tree/6821b3182c3492fd0ccdc6438b33b96d59b58355), `6821b3182c3492fd0ccdc6438b33b96d59b58355` | humanizer-principles and econ-style-en: remove mechanical lists, symmetrical syntax and empty endings; keep names for the same object stable. |
| [hanlulong/econ-write](https://github.com/hanlulong/econ-writing-skill/blob/f2bf7a22c5e3b37921a5e6c73bd1fb380a5e00e8/.agents/skills/econ-write/SKILL.md), `f2bf7a22c5e3b37921a5e6c73bd1fb380a5e00e8` | Reader First, Triangular/Newspaper Style, Idiomatic Natural Phrasing, Paragraphs: track known and new concepts and expose actor–action relations. |
| [Cochrane, Writing Tips for PhD Students](https://www.johnhcochrane.com/s/phd_paper_writing.pdf), 2005-06-08 | pp.2–4 Organization and pp.5–9 Writing: put central content first and manage what the reader knows. |
| [Head, The Introduction Formula](https://blogs.ubc.ca/khead/research/research-advice/formula), read 2026-10-08 | Parts 1–5: concrete question, economic importance and relevant prior knowledge. |
| [Evans, introduction guidance](https://www.cgdev.org/blog/how-write-introduction-your-development-economics-paper), 2020-02-10 | Research Question, Empirical Approach, Detailed Results, Value Added: explain comparison, quantities and additional economic knowledge. |
| [Bellemare, Middle Bits Formula](https://marcfbellemare.com/wordpress/12797), 2018-01 | Framework, Data and Descriptive Statistics: connect predictions, comparisons and observation units in dependency order. |

Hedge allowances, concessions, cautious alternatives, generic limitations and defensive disclaimers are excluded. Fixed word counts, sentence counts, contribution counts, forced paragraph sequences and deliberate roughness are also excluded. Profiles transfer argument and information placement to target evidence.

Validation used the existing skill-creator frontmatter check for four revised skills and independent edits of Ruan introduction, institutions and design passages. Citation commands, the specification equation, quantities and scientific conditions were retained. The observed institutional paragraph mixing led to revised population/identifier and supply-stage transfer directions in the Ruan profile. Verification rewrites remain outside the research originals.

The existing default-micro corpus was retained. Re-read the published [Egger et al. PDF](https://drive.google.com/file/d/13KC9FwbvqbouTDmEykLmLlEWgOe6hP9f/view), pp.2604–2606, for the question-to-variation-to-observation chain and the expenditure-based multiplier; and [Gershenson et al. PDF](https://drive.google.com/file/d/17GNBlDGzF9WKB0fFvN7kpXTDI6ZOrZUH/view), pp.315–316 and Table 2, for estimate, uncertainty and baseline relations. The existing source versions and reading map remain in default-micro.

## Generative writing refinement (2026-10-09)

Ordinary native econ-writing requests generated a Japanese Ruan mechanism explanation, a Japanese Introduction and an English Identification section from the canonical research records. Each run recorded the actual method, profile, read sections and content hashes. Independent review separated sentence/paragraph compliance, readability, source fidelity and conditional reasoning. Generated drafts remained outside the research originals.

The failures led to revisions at their existing owners: econ-assertive reconstructs the completed draft, separates independent definitions and operations, and retains the same scientific conditions in summaries; econ-writing selects the requested argument and carries a decision condition from incentives to actions and group quantities; econ-style makes profile examples enact their transfer directions. Default-micro explains the relation from a descriptive pattern to a research judgment and groups outcome estimates by an explicit economic relation. Result transfer preserves the distinct study, baseline, treatment and outcome windows, and separates non-detection, approximate equality and exact zero. Ruan's profile defines legal terms at first use, preserves identifier units and publication coverage, and separates quantity construction from attribute linkage.

Re-read [Silas paragraph and sentence references](https://github.com/Silas1929/econ-writing/tree/ba636f282fc80b12dbed623752b76c1513cd73ea), paragraph §§1–2, 4, 6, 8 and sentence §§2, 6–9, 11–14; [lishn6 paper-style-learner](https://github.com/lishn6/awesome-ai-econ-research-writing/blob/639285453d451d765da66cfae559bc3e5e24d137/skills/paper-style-learner/SKILL.md), extraction priorities and evidence discipline; [Cochrane](https://www.johnhcochrane.com/s/phd_paper_writing.pdf), pp.3, 5–10; and [Kiterlin's existing adaptation source](https://github.com/Kiterlin/anti-defensive-writing/blob/c7edf8fc91ae9c4f7e58345bd12934bb4cf41c46/skill/anti-defensive-writing/SKILL.md), Rewrite Procedure and Final Pass. Retain reconstruction, explicit relations and evidence-matched claim strength. Exclude hedge allowances, defensive reformulations, stock caveats and fixed length/structure quotas.

The supplied Galasso and Luo (2026) theory section, pp.485–486, supplies the payoff-to-choice relation. Alpert et al. (2022), pp.1154–1155, separates its principal comparison, alternative comparison and inference. Gruber et al. (2025), p.270, links each population/source construction to its economic role. Their existing profile source records retain the inspected PDF versions.

The final three Ruan tasks passed every required prose and scientific-meaning criterion. Results generation from [Bessone et al. (2021)](https://economics.mit.edu/sites/default/files/2022-09/economic-sleep-qje.pdf), Table IV and pp.1926, 1929–1930, exposed source-transfer errors in non-detection, approximate equality, treatment duration and outcome grouping; fresh generation after the Results refinement passed. An independent task from [Kline, Rose and Walters (2022)](https://ekrose.github.io/files/randres.pdf), Tables II and IV, also passed, including average effects, between-firm dispersion, units, denominators and uncertainty. No generated verification draft was hand-edited. The Results-only refinement was outside the three Ruan tasks' recorded reading/selection, whose unchanged instruction coverage retained its passing evidence.

The existing frontmatter validator passed for econ-assertive, econ-writing and econ-style. Shared bytes matched the 34-path contract; scientific records, paper/code/data and persistent profile selections stayed in their owners. Committed source identity belongs to the existing integration receipts and exported SOURCE.md records.

## Coordinated research and verified execution (read 2026-10-09)

The team extension addresses missing execution state, completion evidence, independent oversight and resumption. It preserves the eleven specialist methods and their existing writing corpus. All new instructions and the stdlib helper are original local implementation; no external runtime or source code is vendored.

| Primary source and inspected version | Read location | Local adoption and verification |
| --- | --- | --- |
| [OpenAI Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), current page read 2026-10-09 | Custom-agent inheritance, global limits and separate review examples | Native delegation with explicit assignment and separate review identity; preserve the user's model, roles and permissions. Actual host CLI reports 0.160.1, ChatGPT login, stable multi_agent and goals features. Container CLI is absent; it is not claimed as installed. |
| [Non-interactive Codex](https://learn.chatgpt.com/docs/non-interactive-mode), current page | JSONL events and usage, output schema, saved-auth reuse and exact session resume | Capture account-authenticated CLI outputs locally, preserve session cumulative counters and derive verified epoch deltas, save IDs and resume current evidence. No auth files or token values are read. Existing account auth is retained; no API fallback is configured. |
| [ChatGPT plan access](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan), current page | Connect your account, allowance and usage distinction | Existing ChatGPT allowance is the inference path. Credits, new plans and local models are not enabled. |
| [Codex changelog](https://learn.chatgpt.com/docs/changelog), window 2026-09-09 through 2026-10-09 | October 1 0.160.0, October 5 0.160.1, October 7 0.161.0 and October 8 0.162.0 entries | Distinguish installed 0.160.1 from newer release documentation; 0.160.1 preserves Windows remote MCP environment. Use installed help and demonstrated tools, not inferred newer keys. No upgrade is required for this implementation. |
| [Rethinking skills and prompts](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra), published 2026-09-11 | Better skills, up-to-date AGENTS and decision boundaries | Keep routing concise, ordinary specialist tasks direct, and team/oversight detail conditional. Do not import a fixed itinerary or repeat the current project command. |
| [Agent Skills specification](https://agentskills.io/specification), current page | SKILL frontmatter, references, scripts and progressive disclosure | Two role-specific references and one dependency-free local helper; validate link/export integrity and behavior. |
| [Agent improvement loop](https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop), published 2026-05-12 | Overview, harness contract, configuration checks and diagnosis handoff | Connect raw run evidence and independent feedback to implementation causes. Exclude its API-key-dependent live SDK/Promptfoo/HALO execution, model defaults and fixed report headings. |
| [Reward Hacking Challenges Oversight of Autonomous Research Agents](https://arxiv.org/html/2609.28614v1), v1 submitted 2026-09-23, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Sections 3.1 and 8: execution audit, independent evidence and evaluation control | Fix comparison criteria before implementation; retain raw execution and use separate workers. Do not transfer performance percentages as claims about this research team. |

OpenAI documentation is referenced for behavior; no documentation or cookbook code is copied. Repository code licensing is unchanged. The arXiv source is paraphrased with attribution.

### Free-tool selection

| Candidate and inspected version | Function and current change record | Decision |
| --- | --- | --- |
| [Cezar](https://github.com/open-mercato/cezar/tree/1a34fe0fc262c1ea7d3a22f953bb19ac82c3acbf), package 0.14.0, [MIT](https://github.com/open-mercato/cezar/blob/1a34fe0fc262c1ea7d3a22f953bb19ac82c3acbf/LICENSE) | README: file-based state and Codex login. [Codex runner](https://github.com/open-mercato/cezar/blob/1a34fe0fc262c1ea7d3a22f953bb19ac82c3acbf/packages/cezar/src/core/codex-app-server-runner.ts) lines 47–59, 415–420 and usage event handling: account auth or API auth, autonomous default permissions, ignored allowedTools. October 8 commits add graph execution (9230faac), branding (3b0d2d1f) and repair assertions (1a34fe0f). GitHub commits API queried with since=2026-09-09. | Not installed. Native delegation/resume plus the existing task record and local helper satisfy this assignment. A second runtime would duplicate state and require reconciling its default approval/sandbox behavior. Package licensing does not establish free model inference. |
| [ccusage](https://github.com/ccusage/ccusage/tree/ee04dbf1ae9ad2b447dc94473d2e6bda47613171), [MIT](https://github.com/ccusage/ccusage/blob/ee04dbf1ae9ad2b447dc94473d2e6bda47613171/apps/ccusage/LICENSE) | README Supported Sources, JSON/offline/no-cost reporting. The root LICENSE points to apps/ccusage/LICENSE; that actual file was read. October 9 updates models.dev (ee04dbf1, 2dca8650) and LiteLLM (43f5d48e) pricing snapshots; commits API queried with since=2026-09-09. | Not installed. This run receives direct Codex JSONL usage, so a separate report parser adds no missing function. API-equivalent price estimates are not invoices. Consider later for a local cross-session view. |
| [SQLite/FTS5](https://sqlite.org/fts5.html), container SQLite 3.37.2; [public domain](https://sqlite.org/copyright.html) | Read FTS5 overview, table creation and external-content synchronization; [release history](https://sqlite.org/changes.html) checked for 2026-09-09–2026-10-09 and lists no release in that interval. An in-memory FTS5 table was created successfully in the existing Python runtime. | No second DB or index is created. Exact IDs and text search cover the present task store and source collection. Retain the existing runtime; adopt indexing only after measured search/state scale requires it. |

LangGraph, Pydantic AI, Promptfoo, Langfuse, Phoenix and OPA remain uninstalled candidates. No demonstrated missing execution function requires them. Their installation cost alone would not verify a free inference path.


### Common synchronization and environment sources (common-core reader, 2026-10-09)

| Primary source and edition | Inspected passage | Adoption and confirmation |
| --- | --- | --- |
| [Git configuration](https://git-scm.com/docs/git-config), documentation 2.56.0 updated 2026-09-28; container Git 2.34.1 | core.fileMode, displayed lines 1748–1755 | Preserve executable-mode ownership and refuse incompatible target filesystems. Do not change a user's core.fileMode setting to bypass a synchronization refusal. New Python-invoked helper files use mode 644. |
| [Docker build context](https://docs.docker.com/build/concepts/context/), fetched 2026-10-09; page publication/update date not displayed | .dockerignore, displayed lines 341–413 | Exclude local operational state, auth caches, secrets and environment files from the build context. Existing mounted data and cache structures remain intact. |
| [Docker build secrets](https://docs.docker.com/build/building/secrets/), fetched 2026-10-09; page publication/update date not displayed | Displayed lines 30–33 | Keep build secrets out of Docker ARG and ENV. No secret mechanism is changed or credential extracted. |
| [VS Code sharing Git credentials](https://code.visualstudio.com/remote/advancedcontainers/sharing-git-credentials), fetched 2026-10-09 | Host .gitconfig and credential-helper behavior, displayed lines 23–32 | Remove personal Git-author Docker defaults and use the user's existing Git settings and official credential-helper path. Container username remains separate from commit-author identity. |

The common-core worker inspected these primary passages and implemented the corresponding sync/Docker changes. These are original repository explanations; no documentation paragraphs or source code are copied, and no repository license is newly selected.


### Native CLI cumulative usage semantics (2026-10-09)

Read OpenAI Codex [JSONL event processor](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/exec/src/event_processor_with_jsonl_output.rs) at the installed `rust-v0.160.1` tag: `usage_from_last_total`, lines 118–128, and `ThreadTokenUsageUpdated`/`TurnCompleted`, lines 509–534. Completed-turn output copies the thread's cumulative total, including cached-input and reasoning-output counters. Read [token-usage replay](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/app-server/src/request_processors/token_usage_replay.rs) for resumed-history reconstruction. Lines 119-121 also default to all zero when usage information is absent, so an unverified all-zero observation is retained raw and normalized as unknown. The same-ID native resume increased the original counters and confirmed this behavior. The original run and correction raw records are retained; increments are differences within the verified epoch.

Adoption: the local helper binds raw counter observations to session, explicit epoch, chronological sequence and hash. It computes additive totals across distinct sessions/epochs and cumulative deltas within one epoch, regardless of import order. Unknown/reset semantics remain null. The original implementation is referenced under its [Apache-2.0 license](https://github.com/openai/codex/blob/rust-v0.160.1/LICENSE); no source code is copied and this repository's license remains unchanged.

### Setup failure and Git trust preservation (2026-10-09)

Read [Git configuration](https://git-scm.com/docs/git-config), documentation 2.56.0 updated 2026-09-28, `safe.directory` and `--add` (displayed lines 4572–4578). Container Git 2.34.1 supports the inspected commands. The workspace trust entry is added only when absent; existing entries and commit-author settings remain intact. Isolated-home fixtures execute setup twice and check byte-identical second-run configuration. Dependency-installation and required-kernel failures stop setup. Kernel registration follows the requested R dependency transaction. These local explanations and implementations do not copy documentation or change licensing.

### Locked R dependency toolchain (2026-10-09)

The locked R Polars 1.12.0.9000 [git revision 2457d793](https://github.com/pola-rs/r-polars/tree/2457d79339979d7ae6f41d85b832b2e59e6e43e7) uses Rust Polars 0.54.4 and ethnum 1.5.2. Read its DESCRIPTION, Cargo.toml and Cargo.lock; the Polars minimum Rust version is 1.95. Read [Rust issue 157363](https://github.com/rust-lang/rust/issues/157363) and [ethnum 1.5.3 release](https://github.com/nlordell/ethnum-rs/releases/tag/v1.5.3) for the TryFromIntError layout change after 1.96. Actual compilation with Rust 1.99.0 stopped at E0512. Docker and Make default to [Rust 1.96.1](https://blog.rust-lang.org/2026/06/30/Rust-1.96.1/) to retain the existing dependency APIs and the 1.96 maintenance fixes. [Rustup overrides](https://rust-lang.github.io/rustup/overrides.html) and [environment variables](https://rust-lang.github.io/rustup/environment-variables.html) define the explicit toolchain and automatic-installation controls; user overrides remain effective.

The current-month review separately checked [Rust 1.99.0, October 1](https://blog.rust-lang.org/2026/10/01/Rust-1.99.0/) and [R Polars 1.16.0, September 13](https://github.com/pola-rs/r-polars/releases/tag/v1.16.0). The newer R Polars release carries API migration changes, so this repair preserves rproject.toml, rv.lock, pyproject.toml and pixi.lock. Rust and ethnum are MIT OR Apache-2.0; R Polars and Rust Polars are MIT. Source license files were read; no external code is copied and the repository license is unchanged. Mini and individual projects keep their own lightweight dependency environments.

## Shared prose instruction sources (2026-10-09)

The shared writing guidance's inspected primary sources and adaptations are recorded in [econ-project-mini's source history](https://github.com/yoshimurahiroki/econ-project-mini/blob/19f8e11312a8d3400984c41b0a35a926f31b3e8a/docs/ai/sources.md). 

## Research judgment and harness simplification — sources read 2026-10-09

The revision concentrates on useful outcomes, consequential dependencies and reader needs. Detailed source methods were not imported as a new workflow. Current, minimal and revised instructions were compared through fresh same-input outputs and independent qualitative reading; this source record does not establish model performance.

| Primary source | Passage read and use |
| --- | --- |
| Richard Rumelt, [Good Strategy/Bad Strategy](https://www.richardrumelt.com/good-strategy-bad-strategy) and [The Crux](https://www.richardrumelt.com/the-crux) | Author book overviews and key messages; focus changes on the important tractable obstacle. Whole books were not read. |
| Barbara Minto, [Course](https://www.barbaraminto.com/course) | Course topics and work-sample application; integrate findings into an answer to the reader's question. |
| David Maister, [The Consultant's Role](https://davidmaister.com/articles/2/4/), 2004 | Opening, trusted-advisor discussion and Focus on the Other Person; select advice for the recipient's situation. |
| McKinsey, [Consulting roles](https://www.mckinsey.com/careers/our-roles/consulting-roles) | Client service and Associate/Engagement Manager descriptions; outcome responsibility, without replicating positions as agents. |
| Bain, [Results Delivery](https://www.bain.com/contentassets/8180a9e22db04502a49a92986c714055/bain_brief_results_delivery.pdf) | Printed pp.1–4; distinguish installed arrangements from useful delivered outcomes. |
| Nancy Duarte, [Visual storytelling](https://www.duarte.com/training/visual-storytelling-training/) | Failure discussion and teaching sequence; select and integrate content for the audience. |
| UK Cabinet Office, [The Consultancy Playbook](https://www.gov.uk/government/publications/the-consultancy-playbook), v1.1, September 2022 | Printed p.10 and pp.20–23; reuse existing knowledge, address a specific capability gap and compare outcomes without prescribing every input. |

Author and corporate sources were paraphrased without importing text, branded templates, numerical performance claims or a reuse license. The UK PDF states Crown copyright and OGL v3.0 except third-party material. Repository licensing is unchanged. The September 11 Astra and October 2 GPT-6 source records above were reused.

## Argument prediction and bounded harness adaptation — sources read 2026-10-10

The private comparison predicts content roles from a title/abstract and preceding discussion before opening the target text. It treats a coherent alternative architecture as valid and excludes unknowable original-only facts. This is an inference-time evaluation of instructions; model weights were not updated.

| Source and inspected edition | Reading and use |
| --- | --- |
| Xu et al., [Unfolding Scientific Papers into Multi-Turn Generation Trajectories for Continued Pre-Training](https://arxiv.org/abs/2608.25826), v2, 2026-09-07 | Abstract, §§3.2–3.4, §5 and Appendix A. Reconstructed writing trajectories motivate checking argument roles, but are not observed author deliberation. Its CPT/SFT results concern weight training and do not establish local harness gains. CC BY 4.0. |
| Xu, [Self-Evolving Harness on Multiple Tasks with the Agent as Its Own Optimizer](https://arxiv.org/abs/2609.38372), v1, 2026-09-29 | §§1.2–1.3, 3.1–3.3, 4.1, 5.1, 5.7 and 6. Its frozen-model experiment reports gains and side-effect regressions; engineering runnability alone does not validate an update. CC BY 4.0. |
| Ke et al., [EvoHarnessBench](https://arxiv.org/abs/2609.04280), v3, 2026-09-26 | §§3.3–3.4, 4.1–4.3 and Appendices J.2/K. Retention, adaptation and cost are distinct. Routing/coverage proxies do not establish completed-task quality, and richer capability pools have mixed effects. CC BY-SA 4.0. |
| Garrette, Phelps and Sibony, [Cracked It!](https://link.springer.com/book/10.1007/978-3-319-89375-4), first edition, 2018 | Publisher overview and author opening: distinguish the problem from premature solution advocacy. No book framework or text was imported. |
| Roger Martin, [The Opposable Mind and integrative thinking](https://rogerlmartin.com/thought-pillars/integrative-thinking), 2007 | Author overview: consider tensions between plausible interpretations. No fixed integrative-thinking procedure was imported. |
| Wesley Pasfield, [Build an Agent Improvement Loop with Traces, Evals, and Codex](https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop), 2026-05-12 | Reverified official introduction, feedback/evaluation and handoff discussion. Its synthetic demonstration is not evidence of this project's improvement. Paid API notebook calls and its runtime were not adopted. |

Existing Rumelt, Minto, Maister, Duarte, consultancy, Cochrane, Bellemare, Mahoney, Astra and Sadallah readings were reused. New paper-role comparisons used Heath, Hidrobo and Roy, [JDE 143:102410](https://doi.org/10.1016/j.jdeveco.2019.102410), and a separately reserved Finkelstein–Hendren study, [JEP 34(4):146–167](https://doi.org/10.1257/jep.34.4.146). Source text and evaluation records remain outside the distributed harness. These are original attributed summaries; no paper text, training corpus, branded procedure, weights or software was vendored, and repository licensing is unchanged.
