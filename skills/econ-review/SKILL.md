---
name: econ-review
description: Judge a requested economics claim or artifact by comparing its claims with the cited passages and calculations, including structural identification, equation-to-code correspondence, numerical equilibrium, counterfactuals and welfare.
---

# Research review

1. Recover the named claim or artifact, the scope, the reader, the cited sources and the saved calculations. `assess` returns findings; `assess+repair` repairs within the requested scope.
2. Review against the [economist's procedure](../../runtime/ECONOMIST.md): is the question consequential, do the predictions separate the mechanisms, does the comparison identify the estimand, do the numbers match the saved results, does the interpretation follow from the estimates.
3. Review the text against [WRITING](../../runtime/WRITING.md), and the procedure in [review](references/review.md).

<!-- BEGIN GENERATED MODES -->
## Registered operations

- `assess`: Assess the specified claim or artifact and return findings and proposed repairs.
- `assess+repair`: Assess the specified target and repair it within the requested change scope.
<!-- END GENERATED MODES -->
