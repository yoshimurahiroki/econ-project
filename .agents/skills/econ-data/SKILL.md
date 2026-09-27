---
name: econ-data
description: Acquire and link data, implement concise research code and reproduce requested results.
---

Use `econ-assertive` for prose. Apply the repository simplicity and minimum-verification rules to every generated artifact.

# Data and code

Read the relevant input, documentation and entry point. Map the economic object to records, fields and transformations. Preserve source version, unit, population, period and units needed for interpretation. Verify access terms when access is part of the task. Choose joins from the intended population; preserve the meanings of zero, suppression, censoring and missingness.

Use direct code in the existing language and environment. Keep one canonical QMD or analysis entry point. Extract a helper only for actual reuse or substantial complexity. Avoid generic frameworks, wrapper-only functions, speculative options, duplicate analysis paths and validation layers. Use project-relative paths, explicit seeds and analysis objects for numerical prose and exhibits. Protect raw inputs and credentials. Manage Python with Pixi and R with rv; preserve the full/mini distinction.

Inspection and existing results come first. Run the smallest changed analysis unit only when a consequential uncertainty remains. Check a key, merge, sample, weight, formula or estimator setting when that operation can silently change the requested result. Place the check once at the relevant boundary. Rely on existing library errors for conditions they already enforce. Skip separate parse/import/smoke checks after a relevant successful execution.

Add a persistent test only for a demonstrated bug or consequential reusable calculation with a plausible regression. One-off scripts, straightforward calls and static settings need no test suite. No routine synthetic fixtures, benchmark runs, coverage targets, repeated data scans or whole-pipeline reruns. Stop when the changed result is established.

Read [implementation notes](references/implementation.md) or [reproducible execution](references/reproducible-workflow.md) for the requested dependency. Deliver the requested code, data or result with the definitions and execution evidence needed to use it.
