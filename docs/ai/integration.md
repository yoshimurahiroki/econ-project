# Project integration

Use the repository skills in a coding environment. Use an explicit export for Chat or Work Project attachments. Native connectors provide live files; attached copies retain the version recorded in SOURCE.md. Read the current repository policy before edits. Use the tools actually available for each task.

## Existing R00-R08 Project

```sh
python scripts/export_project.py --profile bridge --output /tmp/econ-bridge
```

Replace the previous repository bridge with BRIDGE_INSTRUCTIONS.txt in the Project instructions and attach the remaining exported files. Keep the combined instructions within 8,000 characters. R00-R08 retain research-method ownership; the bridge supplies simple execution, direct writing and the descriptive-model framework.

## Standalone Project

```sh
python scripts/export_project.py --output /tmp/econ-project
```

Paste PROJECT_INSTRUCTIONS.txt into the instruction field and attach the remaining files. To export selected methods, add `--skills econ-paper econ-design econ-writing`. Direct-writing instructions are included automatically.

Use a fresh output directory outside the repository. The exporter reads the selected files and writes the snapshot once. It checks the instruction-field length when exporting that field. No preflight suite, token report, generated scanner or post-export hash sweep runs. Regenerate a snapshot when its selected instructions change.

## Daily work

Read one method and the prose skill. Reuse unchanged evidence and outputs. Write concise code and plain documents. Review the completed wording once within drafting. Mechanical checks require a concrete consequential risk; use the smallest operation that resolves it. Research-code tests, lint and formatting are opt-in and path-scoped. Setup performs no AI-rule tests. Keep essential scientific evidence with the result rather than a second validation report.

## Handoff

Carry the task, source revision, relevant paths, decisions, authorized edits and actual output locations in the existing task record. Keep credentials, raw data and private papers in their approved storage. Repository changes and Project settings are separate writes.

## Product references

- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- https://help.openai.com/en/articles/10169521-projects-in-chatgpt
- https://agentskills.io/specification
