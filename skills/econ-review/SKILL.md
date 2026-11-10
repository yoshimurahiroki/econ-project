---
name: econ-review
description: Judge a requested economics claim or artifact by comparing its claims with the cited passages and calculations, including structural identification, equation-to-code correspondence, numerical equilibrium, counterfactuals and welfare.
---

# Research review

## Purpose and input

Assess the named claim or artifact within its requested scope, using its intended reader, cited sources and saved calculations. `assess` returns findings; `assess+repair` also repairs the target within granted authority. Editorial assessment activates its writing/profile conditions; reconstruction uses writing's compose procedure.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `assess`: Assess the specified claim or artifact and return findings and proposed repairs.
- `assess+repair`: Assess the specified target and repair it within the requested change scope.
<!-- END GENERATED MODES -->

## Select the operation

Use the registered operations; the [econ-review procedure](references/review.md) owns the selected specialist steps.

## Output

Return the [requested assessment](references/review.md#deliver-the-assessment).
