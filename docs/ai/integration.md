# Project integration

Repository skills run in the coding environment. Project attachments are snapshots identified in SOURCE.md. A repository task uses the current policy and the files relevant to the request.

## Existing R00-R08 Project

```sh
python scripts/export_project.py --profile bridge --output /tmp/econ-bridge
```

Keep the existing R00-R08 method attachments. For a complete instruction-field replacement, paste PROJECT_INSTRUCTIONS.txt. To update a separately maintained field, replace its bridge with BRIDGE_INSTRUCTIONS.txt. Attach the exported policy, context and prose files. ECON_INDEX.md lists their roles; method steps and the research framework apply to the requested object.

## Standalone Project

```sh
python scripts/export_project.py --profile standalone --output /tmp/econ-project
```

Paste PROJECT_INSTRUCTIONS.txt into the field and attach the other files. Select methods with `--skills econ-paper econ-design econ-writing econ-edit`. Both profiles include the repository policy, context, source records, econ-assertive, its default exemplars and econ-style. A study entry point is included when the repository supplies master-project-addendum.txt.

Use a fresh output directory outside the repository. The exporter enforces the 8,000-character instruction-field limit. Included references use exported filenames; references to other repository files use the recorded GitHub revision. Regenerate the selected snapshot when its source instructions change.

## Custom exemplars

For writing or wording edits, consult the profile selected by the policy. To create a profile, request econ-style with the source papers, language and target section.

Name a destination to save the profile; a repository-save request without a path uses docs/ai/custom-style.md. Select a saved profile by path and attach or retrieve it for a Project task. Set a persistent project choice explicitly. "Use the default" restores default-micro.

## Handoff

A requested handoff uses the existing task record for the revision, evidence, authorized work, results and next action relevant to the transfer. Keep private data and credentials in their existing storage.
