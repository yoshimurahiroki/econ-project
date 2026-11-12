# Economics operation index

Generated from registry/operations.json. Support continues the adopted task.

## Read the pending operation

1. **Selected operation → reader.** Read CORE and PROSE Common output, then select the final operation below. Find conditions with `python scripts/route_registry.py index --operation OPERATION --family FAMILY` or `--query TEXT`.
2. **Complete bodies → execution.** Run `python scripts/route_registry.py read OPERATION --stage STAGE --condition CONDITION --format compact`. Stages: entry classifies; contract adopts question/method/inputs; compose executes/writes; review interprets/repairs; finalize saves/delivers. Direct `read RULE_ID` returns that rule and prerequisites.
3. **Retained bodies → next stage.** Follow every `next_offset` under the same `content_sha256` and seen arguments. `bodies` identifies complete bodies and `reused` names omissions. Pass `--seen BODY_SHA256` only for complete matching bodies still in intact context. After compaction, handoff or model change read originals without seen arguments.
4. **Runtime root → reader.** Deployed trees run `python .agents/scripts/route_registry.py --layout installed read OPERATION --stage STAGE --format compact`; expand incomplete snapshots from canonical source. Skill-scoped hosts read specialist `instructions.md` and common `project-work/references/shared/` bodies, acquiring the matching runtime bundle once for execution.

- [econ-design / design](../../skills/econ-design/SKILL.md): Choose a research question, model, identification strategy, study design or policy action.
- [econ-data / execute](../../skills/econ-data/SKILL.md): Acquire, transform, join, calculate, estimate or change research data and code.
- [econ-data / equity](../../skills/econ-data/SKILL.md): Evaluate Japanese, US and overseas equities from public filings, IR and market observations; estimate competition, compute sustainable cash flows, reverse valuation, after-tax investment decisions and news-driven changes.
- [econ-literature / investigate](../../skills/econ-literature/SKILL.md): Find and select source information that resolves a research question or citation task.
- [econ-writing / compose](../../skills/econ-writing/SKILL.md): Compose academic prose and research materials from the adopted sources.
- [econ-writing / revise](../../skills/econ-writing/SKILL.md): Revise supplied prose, including natural Japanese, spoken explanations and requests such as 自然な日本語に, 何を言いたいの, 直訳っぽい, 口頭で説明して and わかりやすく短く.
- [econ-writing / translate](../../skills/econ-writing/SKILL.md): Translate supplied prose into natural Japanese or English with source attribution under PROSE.
- [econ-writing / convert](../../skills/econ-writing/SKILL.md): Convert adopted content into a paper, slides, research site or requested format.
- [econ-writing / guidance](../../skills/econ-writing/SKILL.md): Explain a concrete writing decision and show the needed revision.
- [econ-writing / explain](../../skills/econ-writing/SKILL.md): Explain a paper, theory, institution, method or result through its question, mechanism, evidence and answer.
- [econ-writing / profile](../../skills/econ-writing/SKILL.md): Create or revise a reusable writing profile only when explicitly requested.
- [econ-review / assess](../../skills/econ-review/SKILL.md): Assess the specified claim or artifact and return findings and proposed repairs.
- [econ-review / assess+repair](../../skills/econ-review/SKILL.md): Assess the specified target and repair it within the requested change scope.
- [econ-knowledge / lookup](../../skills/econ-knowledge/SKILL.md): Retrieve the economics definitions, derivations, model conditions or worked examples needed by the current specialist.
- [project-work / contribute](../../skills/project-work/SKILL.md): Complete an assigned project contribution from its adopted economic model through research, calculations, consultation drafts and actual artifacts.
- [project-work / manage](../../skills/project-work/SKILL.md): Manage a project or shared portfolio through its economic decision, evidence, work, resources, authorized changes, outcomes and handover.
- [project-work / clarify](../../skills/project-work/SKILL.md): Clarify requested task requirements, scope or work approaches; compare consequential alternatives and complete the adopted brief or specification.
- [project-work / prompt](../../skills/project-work/SKILL.md): Create, rewrite or improve a ready-to-execute prompt from the user request or supplied draft; do not substitute prompt drafting for an ordinary execution request.

Compatibility names:

| Name | Destination | Selection |
| --- | --- | --- |
| econ-workflow | boundary | required_rules=core.all; resolve_owner_by=requested_final_operation |
| econ-assertive | econ-writing:guidance |  |
| econ-edit | econ-writing:revise |  |
| EDIT | econ-writing:revise | default_input=immediately_preceding_answer |
| econ-handoff | handoff | requested_section=Handoff; required_rules=core.all, team.resumption; resolve_owner_by=existing_result_owner |
| econ-style | econ-writing:profile |  |
| explain-before-shorten | econ-writing:revise |  |

## Select the next reference

Choose the operation above, then the applicable field or method below. Read the selected body and its prerequisite rules completely. An index supplies locations; the linked body supplies the method.

- [design-methods](../../skills/econ-design/references/designs.md)
- [data-implementation](../../skills/econ-data/references/implementation.md)
- [models-causal](../../skills/econ-design/references/causal-models.md)
- [models-markets](../../skills/econ-design/references/market-models.md)
- [models-dynamic](../../skills/econ-design/references/dynamic-models.md)
- [models-macro-extended](../../skills/econ-design/references/macro-models.md)
- [models-dsge](../../skills/econ-design/references/dsge-models.md)
- [models-numerics](../../skills/econ-design/references/numerical-models.md)
- [econ-knowledge](../../skills/econ-knowledge/SKILL.md)
- [research-execution](../../harness/research.md)
- [result-artifacts](../../skills/econ-writing/references/result-artifacts.md)

For local or extracted runtimes, go directly to a known `read OPERATION --condition CONDITION`. `index --operation OPERATION` lists its conditions and bodies; `index --resource RESOURCE_ID` lists a method hierarchy and prerequisites. Read pages through `next_offset` until null. `read RULE_ID` returns that rule with its prerequisites. Reuse complete same-version reads.

