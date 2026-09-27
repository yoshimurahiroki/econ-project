---
name: econ-data
description: Acquire, validate and link data; implement research code and reproduce analysis results.
---

Use `econ-assertive` by default for generated prose: direct drafting, then mandatory post-draft detection, necessity assessment and revision.

# Data and reproducibility

Read inputs, provider documentation, code and environment. Map economic objects to records, fields and transformations. Record source version, retrieval, unit, population, period, geography and units. Distinguish observation frequency from release frequency. Verify actual fee, registration, application, review and use terms when access matters.

Check key definitions, uniqueness, join cardinality, crosswalk timing and match counts with denominators. Choose the join from the intended population. Keep zero, suppression, censoring, missingness and ineligibility as distinct recording states. Check sample selection, coverage changes, treatment timing and comparison support.

Use the established language and dependency conventions. Keep analysis choices separate from infrastructure. Use project-relative paths and authorized environment variables. Protect raw files and credentials. Keep one canonical QMD or established entry point. Extract reused computation into scripts. Set seeds; generate numerical prose, tables and figures from analysis objects.

Use official documentation for current package behavior. Manage R through rv and Python through Pixi. Use existing licensed Stata or configured Julia when requested. Record versions and commands. Read [implementation checks](references/implementation.md) for acquisition, prediction, simulation or replication.

Use [reproducible execution](references/reproducible-workflow.md) for pipelines, replication and cache invalidation. Test required columns, dates, units, keys, merge expansion, finite values and economic invariants from the actual input contract. Test affected code and a small numerical example before expensive execution. Reconcile sample, treatment, weights and inference with the design. Separate inspection, execution, numerical agreement and deployment through their observed records. Deliver the requested code, data, result or feasibility assessment with definitions and run evidence.
