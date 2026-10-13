---
name: econ-data
description: Map or link research data, change research code or data, and reproduce requested numerical results through existing execution paths.
---

# Data and code

## Purpose and input

For a new economics task, complete the brief [workflow entry](../econ-workflow/SKILL.md#task-entry) once, then continue here. Support calls within an existing task do not restart entry.

Map or link research data, change research code or data, and reproduce requested numerical results through existing execution paths.

Input: Requested data operation, canonical specification, input documentation and saved results.

Apply [the common prose rule](../econ-assertive/SKILL.md#common-prose-rule) to every output from this task.

## Procedure

Read the applicable operation-specific reference before performing that operation.

### Map the object to the existing execution path

Implement the requested acquisition, transformation, calculation or reproduction through the existing entry point. Read that entry point's specification, input documentation and saved results. Map the requested economic object to records, fields, keys and transformations. Preserve the source version, population, period, observation unit, quantity unit and denominator. Choose joins that produce the intended population. Preserve the distinctions among observed zero, suppression, censoring and missingness.

### If the request is a data design

For a data design, inspect the source fields that define the proposed measures. Map sample eligibility, measurement support, scale, case mix, behavior and heterogeneity to their roles in the design. Define each requested metric's population, numerator, denominator, timing, aggregation and missingness. Construct pre-treatment groups from pre-treatment information and fix their membership across the comparison period.

### Reuse or recompute by dependency

Trace each requested result through its source, derived data, analysis object and exhibit. Reuse saved objects whose inputs and definitions match the calculation. Record input, definition and transformation versions in existing metadata. Recompute calculations that depend on a changed mapping or population. Generate wording, layout and language revisions from saved quantities and preserve their numerical provenance.

### Preserve scientific choices and execution safeguards

Keep the user's sample rules and classifications in the canonical specification. Keep unresolved user choices and project-management records outside research artifacts. Do not resolve the researcher's scientific choices without authorization. Set explicit seeds for stochastic computation.

### Verify affected operations

Verify keys, joins, samples, weights and formulas affected by the work through the existing checks and boundary assertions for those operations.

### Output and explanation

Use econ-paper or econ-writing to explain what the data measure and how they answer the economic question. Keep the technical verification record separate from that exposition.

### Read the operation-specific procedure

Read [implementation notes](references/implementation.md) or [reproducible execution](references/reproducible-workflow.md) for the operation being performed.
