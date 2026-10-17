---
name: econ-review
description: Judge a requested economics claim or artifact by comparing its claims with the cited passages and calculations.
---

# Review and interpretation


<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `assess`: Assess the specified claim or artifact and return findings and proposed repairs. Finish: Return the requested result when its input, content, format and authorized operation requirements are met.
- `assess+repair`: Assess the specified target and repair it within the requested change scope. Finish: Return findings and the repaired authorized target; report any determining unresolved dependency.
<!-- END GENERATED MODES -->

## Purpose and input

[Task boundaries and completion](../../runtime/CORE.md) and [operation ownership](../../registry/operations.json) govern this specialist. Use [PROSE](../../runtime/PROSE.md) when explaining the result.

Input: Named claim or artifact, requested review scope, intended reader and cited sources or saved calculations.

## Procedure

### Choose the review target

Review the named object within the requested scope:

- Editorial review: assess information selection, argument and expression for the intended reader under [PROSE](../../runtime/PROSE.md), selecting a profile example only when it resolves a wording or structure decision. Use econ-writing's section rules for section structure; a local assessment needs only the relevant passage and rule.
- Claims and derivations: compare the conclusion and claim-bearing appendices with cited passages, equations or generating calculations. Read econ-design or econ-data when the assessment requires its technical method.
- Code or pipeline: trace the changed calculation to its adopted definitions and affected consumers. Use [changed-calculation comparisons](../econ-data/references/implementation.md#compare-changed-calculations) for samples, estimates and inference, [numerical dependencies](../econ-data/references/reproducible-workflow.md) for saved analysis results, and [EXECUTION](../../runtime/EXECUTION.md) for completion and output ownership within the requested scope.
- Conduct: compare actual operations and returned results with the request and granted authority.
- Operational plan: apply the [decision-selection rules](../../runtime/DECIDE.md); assess whether actions, handoffs and checks advance the requested outcome. Preserve user-required frequencies.

A local review stays with the named passage, result or operation and dependencies needed to assess it. Correct the target when correction is requested.

### Locate and repair the cause

For each defect, identify the passage, calculation or operation and explain what it changes in the requested result. Use the demonstrated cause to select the repair:

- Source or premise: check the cited material or obtain the missing fact.
- Transformation or calculation: correct the operation and recompute affected results.
- Inference: revise the claim or its conditions to match the result.
- Presentation: revise wording or selection when the underlying result supports the claim.

Use econ-writing's `revise` mode for meaning-preserving revision and its `compose` mode when the requested repair requires reconstruction; integrate the return into the assessment's named target.

Trace the repair through connected claims and artifacts, preserving unaffected sources and results. Inspect rendered output when presentation is in scope; check speaking time or website controls when the request includes them. Stop when the affected claims follow from their sources or calculations under the adopted conditions and the artifact meets the requested format and operation requirements.

### Compare versions or decisions when requested

Retain an accessible original before a requested before-and-after revision; an existing file or conversation suffices. Compare the actual versions on the same requested outcome and inputs. Identify the choice the changed method or instruction induced, including a justified unchanged choice, and assess the result alongside the work and resources used. Judge mathematical validity, feasibility and the requested economic outcome separately. With a single version, assess its claims against sources or calculations.

Apply these comparisons when relevant:

- Estimates across specifications: separate sample, measurement and target-population changes from method changes; use a common-sample or common-measure comparison to isolate the proposed explanation.
- Recipient or action selection: hold budget and constraints fixed; examine errors that cross the selection boundary and their losses. For who gains or loses, inspect group transitions or joint outcomes hidden by averages.
- Subgroup differences: assess their direct contrast.
- Model–decision-maker disagreement: compare the choices with those rationalized by the decision-maker's objectives, private information and unobserved outcomes. Use remaining violations and relevant realized outcomes to locate decisions to change.

Use [oversight notes](references/oversight.md) for requested independent assessment, blinded comparison or a contested execution finding.

### Deliver the assessment

State the conclusion from the comparison. For an economic claim, use its generating comparison or calculation to distinguish an observed association, estimated effect or model implication when that distinction changes the interpretation. For a referee response, answer each comment with the result and supporting passage. Handle execution status, proposed analyses and revision history under [EXECUTION's record and artifact rules](../../runtime/EXECUTION.md), including explicitly requested operational content.

Return demonstrated defects and their needed repairs, plus the corrected target when requested. Continue the next authorized step in the parent task under its existing completion and stopping conditions.
