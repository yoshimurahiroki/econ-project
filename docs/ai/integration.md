# Project integration

Use repository skills in the coding environment and explicit exports for Project attachments. Native connectors provide live files; attached copies retain the revision recorded in SOURCE.md. Read current repository policy before edits.

## Existing R00-R08 Project

```sh
python scripts/export_project.py --profile bridge --output /tmp/econ-bridge
```

Keep existing R00-R08 method attachments. Replace the prose attachment with ECON_ASSERTIVE.md and its exported references, including ECON_ASSERTIVE__DEFAULT_MICRO.md. Attach ECON_STYLE.md for explicit custom-profile requests and the remaining bridge files for execution and the descriptive-model framework.

For a complete instruction-field replacement, paste docs/ai/project_instructions.txt. For a separately maintained field, replace its old bridge with BRIDGE_INSTRUCTIONS.txt. Use one route; do not append the bridge to the complete replacement. Keep the field within 8,000 characters.

R00-R08 own research methods. ECON_ASSERTIVE.md owns Japanese and English wording. Apply it once within the task. A request for natural prose does not add another research module or humanizer. Method checklists do not add generic cautions, limitation sections or compliance reports.

## Standalone Project

```sh
python scripts/export_project.py --output /tmp/econ-project
```

Paste PROJECT_INSTRUCTIONS.txt into the instruction field and attach the remaining files. For selected methods, add `--skills econ-paper econ-design econ-writing econ-edit`. The prose rules, default exemplars and custom-profile creation skill are included automatically in both export profiles and selected-method exports.

Use a fresh output directory outside the repository. The exporter reads selected files and writes the snapshot once. It checks instruction-field length during export. No preflight suite, token report, scanner or post-export hash sweep runs. Regenerate the selected snapshot when its instructions change.

## Default and custom exemplars

Every research-prose task uses default-micro unless the user explicitly selects custom exemplars. Reuse loaded text. Providing a paper for analysis does not select its style. A custom file's presence does not activate it. No profile is created during ordinary writing.

To create and apply a task-specific profile: "Use econ-style to create custom exemplars from these papers for the results section, then use them for this draft." To save it, name the destination; a repository-save request without a path uses docs/ai/custom-style.md. To use a saved profile, select its path explicitly. A persistent project choice requires an explicit instruction. "Use the default" restores default-micro.

For a custom profile used in Chat, attach or retrieve the selected file. The default examples remain available for sections that profile does not cover. Profiles transfer syntax, paragraph development and register; task evidence supplies all findings and citations. The zero default for hedges, concessions, qualifications, rhetorical contrasts and emphasis governs every profile.

## Daily work

Read one method, the prose rules and the selected exemplars; reuse loaded material. Write direct economic claims; delete nonessential qualifications and empty framing. Keep evidence, terms and numbers with their claim. Reuse unchanged results. Mechanical checks require a concrete consequential risk; use the smallest resolving operation. Research-code tests, lint and formatting are opt-in and path-scoped. Setup performs no AI-rule tests.

## Handoff

Carry the task, source revision, relevant paths, decisions, authorized edits and actual output locations in the existing task record. Keep credentials, raw data and private papers in approved storage. Repository changes and Project settings are separate writes.

## Product references

- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/10169521-projects-in-chatgpt
- https://agentskills.io/specification
