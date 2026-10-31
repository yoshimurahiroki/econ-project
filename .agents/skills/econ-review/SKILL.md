---
name: econ-review
description: Judge a requested economics claim or artifact by comparing its claims with the cited passages and calculations.
---

# Research review

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

A local review stays with the named passage, result or operation and dependencies needed to assess it. For a whole argument or execution review, first recover the intended choice, central claim and required outcome from the artifact and actual results. Prioritize defects that change that answer, invalidate its identifying comparison or block delivery. Allocate further inspection by the unresolved consequence under [DECIDE](../../runtime/DECIDE.md); routine technical precision does not substitute for resolving a defective central mechanism. Correct the target when correction is requested.

Compare the recovered result with the governing request. Trace the decisive evidence through its needed inference to the claim and the chosen action. Identify a missing causal step, incompatible premise or unstated aggregation where it changes the answer. For a project result, connect completed subtasks to the parent deliverables and inspect the resulting artifacts and actions. Required work remains open until its own completion condition is met; a convincing report or completed component cannot discharge it.

### Locate and repair the cause

For each defect, identify the passage, calculation or operation and explain what it changes in the requested result. For a contested explanation, compare its consequential alternative and contradictory evidence. Use the demonstrated cause to select the repair:

- Source or premise: check the cited material.
- Transformation or calculation: correct the operation and recompute affected results.
- Inference: revise the claim or its conditions to match the result.
- Presentation: revise wording or selection when the underlying result supports the claim.
- Execution: repair the failed operation, resume its affected descendants and inspect the requested output through its existing owner. A revised success statement cannot repair a missing artifact or failed calculation.

Use econ-writing's `revise` mode for revision and its `compose` mode when the requested repair requires reconstruction; integrate the return into the assessment's named target.

Trace the repair through connected claims and artifacts. When slides or a figure-heavy brief are in scope, read the artifact and its designated substantive sources before using the author's explanation of the layout. Recover the question, comparison, result and supporting evidence from the pages themselves. Apply [the medium rules](../econ-writing/SKILL.md#compose-a-talk) and [render checks](../econ-writing/SKILL.md#render-the-requested-artifact) to the affected pages; compare titles, table axes, estimate scales and labels with the original result. Check speaking time or website controls when requested. Stop when the affected claims follow from their sources or calculations under the adopted conditions and the artifact meets the requested format and operation requirements.

### Compare versions or decisions when requested

Retain an accessible original before a requested before-and-after revision; an existing file or conversation suffices. Compare actual versions on the same requested outcome, inputs, authority and available tools. Identify the issue selected, decisive evidence used, method adopted and operation completed, including a justified unchanged choice. Assess the resulting calculation or artifact alongside work and resources used. Judge mathematical validity, feasibility and the requested economic outcome separately. Model self-ratings and instruction compliance alone do not establish improvement. With a single version, assess its claims against sources or calculations.

Apply these comparisons when relevant:

- Estimates across specifications: separate sample, measurement and target-population changes from method changes; use a common-sample or common-measure comparison to isolate the proposed explanation.
- Recipient or action selection: hold budget and constraints fixed; examine errors that cross the selection boundary and their losses. For who gains or loses, inspect group transitions or joint outcomes hidden by averages.
- Subgroup differences: assess their direct contrast.
- Model–decision-maker disagreement: compare the choices with those rationalized by the decision-maker's objectives, private information and unobserved outcomes. Use remaining violations and relevant realized outcomes to locate decisions to change.
- Independent judgment: when facts and criteria stay fixed, a change in user insistence or source identity should preserve the evidence-based choice. When contrary evidence changes a determining premise, assess whether the explanation and action change with it.
- Multi-stage work: compare actual actions and accumulated artifacts at entry, an intermediate decision, finalization and resumption. Check the original purpose, binding conditions, adopted definitions and authorized amendments at each relevant stage. Assess whether new evidence changed the right dependent tasks, preserved reusable results and led to the requested final output. Use the existing task and operation records for the comparison.

Use [oversight notes](references/oversight.md) for requested independent assessment, blinded comparison or a contested execution finding.

### Deliver the assessment

State the conclusion from the comparison. For an economic claim, use its generating comparison or calculation to distinguish an observed association, estimated effect or model implication when that distinction changes the interpretation. For a referee response, answer each comment with the result and supporting passage. Handle execution status, proposed analyses and revision history under [EXECUTION's record and artifact rules](../../runtime/EXECUTION.md), including explicitly requested operational content.

Return demonstrated defects and their needed repairs, plus the corrected target when requested. Continue the next authorized step in the parent task under its existing completion and stopping conditions.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `assess`: Assess the specified claim or artifact and return findings and proposed repairs.
- `assess+repair`: Assess the specified target and repair it within the requested change scope.
<!-- END GENERATED MODES -->
