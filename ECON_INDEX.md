# Selected task operations

Read the included common rules once. Support inherits this task and returns to its owner. Run documentation command examples from this snapshot root.

- econ-design / design: design
- econ-data / execute: execute
- econ-literature / investigate: investigate
- econ-writing / compose: compose
- econ-writing / revise: revise
- econ-writing / translate: translate
- econ-writing / convert: convert
- econ-writing / guidance: guidance
- econ-writing / explain: explain
- econ-writing / profile: profile
- econ-review / assess: assess
- econ-review / assess+repair: assess+repair

Included resources:

- [checked-artifacts-instructions](.agents/skills/economics-checked-instructions/SKILL.md)
- [codex-hooks](.agents/harness/codex_hooks.py)
- [control](.agents/runtime/CONTROL.md)
- [core](.agents/runtime/CORE.md)
- [data-implementation](.agents/skills/econ-data/references/implementation.md)
- [data-results](.agents/skills/econ-data/references/reproducible-workflow.md)
- [default-micro](.agents/profiles/default-micro/PROFILE.md)
- [design-methods](.agents/skills/econ-design/references/designs.md)
- [econ-data](.agents/skills/econ-data/SKILL.md)
- [econ-design](.agents/skills/econ-design/SKILL.md)
- [econ-literature](.agents/skills/econ-literature/SKILL.md)
- [econ-review](.agents/skills/econ-review/SKILL.md)
- [econ-writing](.agents/skills/econ-writing/SKILL.md)
- [examples-en](.agents/profiles/default-micro/short-examples-en.md)
- [examples-ja](.agents/profiles/default-micro/short-examples-ja.md)
- [execution](.agents/runtime/EXECUTION.md)
- [extended-en](.agents/profiles/default-micro/extended-introduction-en.md)
- [extended-ja](.agents/profiles/default-micro/extended-introduction-ja.md)
- [local-checks](.agents/harness/local_checks.py)
- [local-checks-guide](.agents/harness/local_checks.md)
- [native-check](.agents/harness/native_check.py)
- [native-check-guide](.agents/harness/native_check.md)
- [native-run](.agents/harness/native_run.py)
- [native-run-guide](.agents/harness/native_run.md)
- [paper-workflow](.agents/skills/econ-writing/references/paper-workflow.md)
- [policy-assets](.agents/harness/policy_assets.py)
- [policy-manifest](.agents/quality/policy_manifest.json)
- [prose](.agents/runtime/PROSE.md)
- [prose-check-guide](.agents/quality/prose_rules.md)
- [prose-check-rules](.agents/quality/prose_rules.json)
- [publication](.agents/harness/publication.md)
- [registry-operations](.agents/registry/operations.json)
- [registry-placements](.agents/registry/placements.json)
- [registry-resources](.agents/registry/resources.json)
- [requirements-check](.agents/harness/requirements_check.py)
- [requirements-check-guide](.agents/harness/requirements_check.md)
- [research](.agents/runtime/DECIDE.md)
- [review-methods](.agents/skills/econ-review/references/oversight.md)
- [state-contract](.agents/harness/state.md)
- [team](.agents/runtime/TEAM.md)
- [team-state-helper](.agents/harness/state.py)
- [tool-route-registry-py](.agents/scripts/route_registry.py)
- [writing-ui](.agents/skills/econ-writing/agents/openai.yaml)

Optional resources are requested only when their function becomes necessary. See [optional inputs](OPTIONAL_INPUTS.md).

Operation contract:

- Selector: econ-design:design; owner: econ-design; canonical operation: econ-design:design.
- Inputs: Use the requested target and authorized inputs; inherit settled scope, definitions, permissions and holds.
- Result: {"kind":"as_requested","meaning":"Choose a research question, model, identification strategy, study design or policy action.","role":"requested_result","target":"from_request"}
- Finish: Return the requested result when its input, content, format and authorized operation requirements are met. Apply the selected review-plan completion and exact-candidate release conditions in CONTROL.
- Selector: econ-data:execute; owner: econ-data; canonical operation: econ-data:execute.
- Inputs: Use the requested target and authorized inputs; inherit settled scope, definitions, permissions and holds.
- Result: {"kind":"as_requested","meaning":"Acquire, transform, join, calculate, estimate or change research data and code.","role":"requested_result","target":"from_request"}
- Finish: Return the requested result when its input, content, format and authorized operation requirements are met. Apply the selected review-plan completion and exact-candidate release conditions in CONTROL.
- Selector: econ-literature:investigate; owner: econ-literature; canonical operation: econ-literature:investigate.
- Inputs: Use the requested target and authorized inputs; inherit settled scope, definitions, permissions and holds.
- Result: {"kind":"as_requested","meaning":"Find and select source information that resolves a research question or citation task.","role":"requested_result","target":"from_request"}
- Finish: Return the requested result when its input, content, format and authorized operation requirements are met. Apply the selected review-plan completion and exact-candidate release conditions in CONTROL.
- Selector: econ-writing:compose; owner: econ-writing; canonical operation: econ-writing:compose.
- Inputs: Use the requested target and authorized inputs; inherit settled scope, definitions, permissions and holds.
- Result: {"kind":"as_requested","meaning":"Compose the requested prose from authorized materials.","role":"requested_result","target":"from_request"}
- Finish: Return the requested result when its input, content, format and authorized operation requirements are met. Apply the selected review-plan completion and exact-candidate release conditions in CONTROL.
- Selector: econ-writing:revise; owner: econ-writing; canonical operation: econ-writing:revise.
- Inputs: Use the requested target and authorized inputs; inherit settled scope, definitions, permissions and holds.
- Result: {"kind":"as_requested","meaning":"Revise supplied prose within the authorized content-change scope.","role":"requested_result","target":"from_request"}
- Finish: Return the requested result when its input, content, format and authorized operation requirements are met. Apply the selected review-plan completion and exact-candidate release conditions in CONTROL.
- Selector: econ-writing:translate; owner: econ-writing; canonical operation: econ-writing:translate.
- Inputs: Use the requested target and authorized inputs; inherit settled scope, definitions, permissions and holds.
- Result: {"kind":"as_requested","meaning":"Translate the requested passage into the target language.","role":"requested_result","target":"from_request"}
- Finish: Return the requested result when its input, content, format and authorized operation requirements are met. Apply the selected review-plan completion and exact-candidate release conditions in CONTROL.
- Selector: econ-writing:convert; owner: econ-writing; canonical operation: econ-writing:convert.
- Inputs: Use the requested target and authorized inputs; inherit settled scope, definitions, permissions and holds.
- Result: {"kind":"as_requested","meaning":"Convert settled content into the requested medium and format.","role":"requested_result","target":"from_request"}
- Finish: Return the requested result when its input, content, format and authorized operation requirements are met. Apply the selected review-plan completion and exact-candidate release conditions in CONTROL.
- Selector: econ-writing:guidance; owner: econ-writing; canonical operation: econ-writing:guidance.
- Inputs: Use the requested target and authorized inputs; inherit settled scope, definitions, permissions and holds.
- Result: {"kind":"as_requested","meaning":"Answer questions about prose principles and examples.","role":"requested_result","target":"from_request"}
- Finish: Return the requested result when its input, content, format and authorized operation requirements are met. Apply the selected review-plan completion and exact-candidate release conditions in CONTROL.
- Selector: econ-writing:explain; owner: econ-writing; canonical operation: econ-writing:explain.
- Inputs: Use the requested target and authorized inputs; inherit settled scope, definitions, permissions and holds.
- Result: {"kind":"as_requested","meaning":"Explain a specified source's economic claims, theory, methods or results.","role":"requested_result","target":"from_request"}
- Finish: Return the requested result when its input, content, format and authorized operation requirements are met. Apply the selected review-plan completion and exact-candidate release conditions in CONTROL.
- Selector: econ-writing:profile; owner: econ-writing; canonical operation: econ-writing:profile.
- Inputs: Use the requested target and authorized inputs; inherit settled scope, definitions, permissions and holds.
- Result: {"kind":"as_requested","meaning":"Create or revise a reusable prose profile and functional fictional examples.","role":"requested_result","target":"from_request"}
- Finish: Return the requested result when its input, content, format and authorized operation requirements are met. Apply the selected review-plan completion and exact-candidate release conditions in CONTROL.
- Selector: econ-review:assess; owner: econ-review; canonical operation: econ-review:assess.
- Inputs: Use the requested target and authorized inputs; inherit settled scope, definitions, permissions and holds.
- Result: {"kind":"as_requested","meaning":"Assess the specified claim or artifact and return findings and proposed repairs.","role":"requested_result","target":"from_request"}
- Finish: Return the requested result when its input, content, format and authorized operation requirements are met. Apply the selected review-plan completion and exact-candidate release conditions in CONTROL.
- Selector: econ-review:assess+repair; owner: econ-review; canonical operation: econ-review:assess+repair.
- Inputs: Use the requested target and authorized inputs; inherit settled scope, definitions, permissions and holds.
- Result: {"kind":"as_requested","meaning":"Assess a specified claim or artifact and return requested findings or scoped corrections.","role":"requested_result","target":"from_request"}
- Finish: Return findings and the repaired authorized target; report any determining unresolved dependency. Apply the selected review-plan completion and exact-candidate release conditions in CONTROL.
