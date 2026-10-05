# Project integration

Repository skills run in the coding environment. Project attachments are explicit snapshots with a revision in SOURCE.md. Connectors or checkouts provide current files; read the current policy and research record before repository changes.

## Existing R00-R08 Project

```sh
python scripts/export_project.py --profile bridge --output /tmp/econ-bridge
```

Keep existing R00-R08 method attachments. Replace the prose attachment with ECON_ASSERTIVE.md and its exported references, including ECON_ASSERTIVE__DEFAULT_MICRO.md. Attach ECON_STYLE.md and the other exported files for profile creation, repository execution and the descriptive/model framework.

For a complete instruction-field replacement, paste docs/ai/project_instructions.txt. For a separately maintained field, replace its old bridge with BRIDGE_INSTRUCTIONS.txt. Use one route and attach the corresponding policy and method files.

## Standalone Project

```sh
python scripts/export_project.py --output /tmp/econ-project
```

Paste PROJECT_INSTRUCTIONS.txt into the field and attach the remaining files. To select methods, add `--skills econ-paper econ-design econ-writing econ-edit`. Both profiles include econ-assertive, its default exemplars and econ-style. ECON_INDEX.md lists the selected standalone methods.

Use a fresh output directory outside the repository. The exporter writes the selected snapshot and checks the instruction-field limit during export. Regenerate it when the selected instructions change. Repository publication does not replace Project attachments automatically.

## Custom exemplars

econ-assertive owns default and custom profile selection. To create and apply a task profile, ask: "Use econ-style to create custom exemplars from these papers for the results section, then use them for this draft."

Name a destination to save it; a repository-save request without a path uses docs/ai/custom-style.md. Select a saved profile by path and attach or retrieve it for a Project task. Set a persistent project choice explicitly. "Use the default" restores default-micro.

## Handoff

Use the existing task record for the revision, source IDs, adopted/open decisions, authorized edits, commands, results, output locations and next action. Keep private data and credentials in approved storage. State repository, Project and deployment writes separately.
