---
name: econ-handoff
description: Transfer a task between Chat, Work and repository agents using revision and execution records.
---

# Research handoff

Read the canonical task and source through the available connector or checkout. Identify the current repository, branch, revision and authorized stage. Attached Project exports are snapshots; compare their SOURCE revision with the current repository before using them for implementation. Use the version specified by the task.

Reuse the existing task record. Carry the object, deliverable, base commit, stable source IDs and paths, adopted and open decisions, authorized edits, environment, generating commands, observed results, output locations and next action. Use [the handoff fields](references/handoff.md) for the information needed to resume.

Git stores code, configuration, specifications and reviewable outputs. Approved research storage holds raw data, private papers and credentials. Carry locators instead of copying private records; preserve sharing settings.

Repository edits, Project attachments and deployed outputs are separate writes. State which were actually changed. Regenerate the relevant snapshot after changing its source instructions. The repository's `docs/ai/integration.md` describes the existing export entry point.
