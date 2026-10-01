# Project integration

Use repository skills in the coding environment and explicit exports for Project attachments. Native connectors provide live files; attached copies retain the revision recorded in SOURCE.md. Read current repository policy before edits.

## Existing R00-R08 Project

```sh
python scripts/export_project.py --profile bridge --output /tmp/econ-bridge
```

Keep the existing R00-R08 method attachments. Replace the old prose attachment with ECON_ASSERTIVE.md and its exported references. Attach the remaining bridge files for repository execution and the descriptive-model framework.

For a complete instruction-field replacement, paste docs/ai/project_instructions.txt. It contains the Economics Research - Simple rules and the prose routing. For a separately maintained instruction field, replace its old bridge with BRIDGE_INSTRUCTIONS.txt. Use one of these instruction-field routes; do not append the bridge to the complete replacement. Keep the field within 8,000 characters.

R00-R08 own research methods. ECON_ASSERTIVE.md owns Japanese and English wording. Run its review once within the task. A request for natural prose does not activate a second research module or a second humanizer. Existing method checklists do not add generic cautions, limitation sections or compliance reports.

## Standalone Project

```sh
python scripts/export_project.py --output /tmp/econ-project
```

Paste PROJECT_INSTRUCTIONS.txt into the instruction field and attach the remaining files. For selected methods, add `--skills econ-paper econ-design econ-writing econ-edit`. Direct-writing instructions and their references are included automatically.

Use a fresh output directory outside the repository. The exporter reads the selected files and writes the snapshot once. It checks instruction-field length during export. No preflight suite, token report, scanner or post-export hash sweep runs. Regenerate the selected snapshot when its instructions change.

## Daily work

Read one method and reuse the prose rules. Write direct economic claims; delete nonessential qualifications and empty framing. Keep evidence, technical terms and numerical content with the relevant claim. Reuse unchanged evidence and outputs. Mechanical checks require a concrete consequential risk; use the smallest resolving operation. Research-code tests, lint and formatting are opt-in and path-scoped. Setup performs no AI-rule tests.

## Handoff

Carry the task, source revision, relevant paths, decisions, authorized edits and actual output locations in the existing task record. Keep credentials, raw data and private papers in approved storage. Repository changes and Project settings are separate writes.

## Product references

- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/10169521-projects-in-chatgpt
- https://agentskills.io/specification
