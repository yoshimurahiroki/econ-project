---
name: econ-data
description: Acquire and link data, implement concise research code and reproduce requested results.
---

# Data and code

Read the current specification, input documentation and entry point. Map the economic object to records, fields, keys and transformations. Preserve source version, population, period, observation unit, quantity unit and denominator. Verify access terms when access is part of the task. Choose joins from the intended population; retain the meanings of observed zero, suppression, censoring and missingness.

Trace source -> derived data -> analysis object -> exhibit through the existing pipeline. Separate costly acquisition and transformation from calculation and presentation where results can be reused. Record the material input, definition and transformation versions in existing metadata. Reuse a saved object for matching recorded inputs. An object with unrecorded provenance has an unverified input version. A changed mapping or population can affect downstream years through a shared universe. Rerun those affected stages. Wording, layout and language changes use saved quantities and preserve their numerical provenance.

Keep sample rules and classifications in the canonical specification. Preserve unresolved choices.

Use direct code in the existing language, environment and entry point. Extract helpers for actual reuse or substantial complexity. Keep source paths and output roles clear. Use explicit seeds when computation is stochastic. Generate numerical prose and exhibits from analysis objects.

Inspect a key, merge, sample, weight or formula when the changed operation can silently alter the requested result. Place a necessary assertion once at that boundary and rely on library errors for conditions they enforce. Establish changed behavior through the smallest representative calculation; repository policy governs further verification.

Read [implementation notes](references/implementation.md) or [reproducible execution](references/reproducible-workflow.md) for the relevant dependency. Deliver the requested code, data or result with the definitions and actual execution evidence needed to use it.
