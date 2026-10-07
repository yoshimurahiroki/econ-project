---
name: econ-handoff
description: Transfer requested research work between Chat, Work and repository agents with the information needed to resume.
---

# Research handoff

Use the canonical task and specified source version. For current repository implementation, identify the authorized branch and revision. Project exports contain snapshots; use their SOURCE revision to identify the supplied version.

Reuse the existing task record. Carry the information needed to resume through [handoff fields](references/handoff.md). Keep decisions in the canonical research record and scientific provenance in generating metadata. Carry locators for private assets in approved storage.

State the actual repository, attachment or deployment changes relevant to the transfer. For a requested Project export, use the existing exporter described in docs/ai/integration.md.
