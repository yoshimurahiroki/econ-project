---
name: econ-review
description: Judge a requested economics claim or artifact by comparing its claims with the cited passages and calculations, including structural identification, equation-to-code correspondence, numerical equilibrium, counterfactuals and welfare.
---

# Research review

## Purpose and input

When the pending operation needs a library definition, derivation, model condition or worked example, activate [econ-knowledge](../econ-knowledge/SKILL.md) and select the needed IDs and required prerequisites. Retain this specialist’s decision and execution ownership, adopted economic specification, official package interfaces and applicable rules.


[Task boundaries and completion](../../runtime/CORE.md) and [operation selection](../../../ECON_INDEX.md) govern this specialist. Use [PROSE](../../runtime/PROSE.md) when explaining the result.

Input: Named claim or artifact, requested review scope, intended reader and cited sources or saved calculations.

Before evaluating that target, read the full activated CORE, PROSE and specialist rule bodies. Apply the complete PROSE normative text to the whole argument; the [detailed dictionary](../../quality/prose_rules.json) supplies concrete lexical detections for the same integrated review. Reuse a same-version full read while its content is available; restore the original request, exact target, adopted specifications and full applicable bodies after context loss. Select `review_editorial_requested` for the common writing process and profile used by an editorial assessment. Select the existing paper-architecture condition when the requested section structure needs it. Authorized prose revision uses `review_prose_repair_requested`; reconstruction uses `review_prose_reconstruction_requested` and writing's compose procedure. The assessment remains with this specialist; the selected writing operation supplies its scoped return.

Recover the actual question, claim, target and fixed conditions from the original request and artifact; do not attribute an unexpressed position. Judge agreement and correction by the same evidence and reasoning regardless of insistence, authority or earlier answers, and update affected conclusions when decisive new evidence changes a premise. Identify a supported criticism through its evidence and an error through its cause and repair. Exclude invented objections, counterexamples that violate fixed conditions and unnecessary concerns. Under PROSE, remove decision-irrelevant defensive separation at paragraph level and state any determining comparison through its concrete content.

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

For a generated research paper, trace each decisive numerical sentence, table cell and plotted point to its named statistic, unit, fitted sample, adopted definition and successful producing run. Use the [existing research execution record](../../harness/research.md) to resolve its selected generation and consumed versions. Reproduce the requested calculation before comparing its result with the manuscript; compare rounded display values using their declared format and compare underlying estimates at the calculation's numerical tolerance. Assess the economic claim through its source passage and identifying or equilibrium argument in this same review. Repair a changed numerical producer and rebuild its affected exhibits and prose; retain unaffected calculations and completed checks.

For a selected literature-backed manuscript, `.agents/harness/research_evidence.py review CONTRACT --root PROJECT --output PACKET` reads the hash-pinned `corpus` reference and the claim's `literature` proposition IDs/hashes. It returns the actual target claims, original passages and deduplicated page context without supplying prior support judgments. Read the relevant original argument and its qualifiers, compare the target's meaning with the source's meaning, and state the inference that connects them. The binder's adopted judgment records that comparison in `claim_meaning`, `source_meaning` and `inference`; text/hash matching alone cannot supply it. For a contested finding, the result owner adjudicates the demonstrated source or calculation against the manuscript and repairs the supported defect. Preserve a correct claim when the proposed finding lacks that support.

Use the same packet's claim candidates to find omitted material claims, then judge the whole requested argument beyond those lexical signals. Bind each source's evidential role and the selected statistic, equation or code through the [existing evidence contract](../econ-writing/references/result-artifacts.md#claims-coverage-and-requested-re-review). For requested re-review, retain the initial criteria and finding IDs, inspect the actual revised evidence first, and save that assessment before opening the author response through `response_after`. Reuse unchanged claim judgments by their actual dependencies. A reply or a repaired sentence alone cannot establish a repaired analysis. The existing state consumes selected claim outputs and requeues their affected writing or analysis consumers.

When exact correspondence is requested, execute the [evidence binder](../../harness/research_evidence.py) with the adopted manuscript, source, model and specification identities. Inspect its claim/source spans, statistic/unit bindings, equation/code/residual checks and symbol/parameter construction mappings. Preserve the native semantic judgment establishing each inference. For a specification search, compare candidates under the frozen estimand, sample, inference and evaluator; inspect the selected validation result, winner-only holdout operation and retained unsuccessful trials. Use the actual observed comparison to judge the claim and repair its affected producer or passage.

For a structural result, follow its [adopted model](../econ-design/references/designs.md#structural-estimation-and-counterfactuals) into the actual parameter order, normalized payoffs, information/timing, transitions, moments or likelihood and solver calls. Evaluate each estimated parameter's identifying variation and the maintained exclusion or selection rule. Inspect the original Bellman, pricing, feasibility or deviation residuals at the returned solution and the requested derivative or simulation comparison through [numerical methods](../econ-data/references/implementation.md#numerical-methods). Trace each intervention into the changed choice sets, ownership, costs, transitions and all affected actors' best responses. Match prices, shares, profits and consumer values to the same scenario and equilibrium, then assess welfare aggregation, transfer accounting, units, horizon and group weights. A requested numerical repair retains the adopted economic specification and rebuilds the affected results at their producing owner.

For each defect, identify the passage, calculation or operation and explain what it changes in the requested result. For a contested explanation, compare its consequential alternative and contradictory evidence. Use the demonstrated cause to select the repair:

- Source or premise: check the cited material.
- Transformation or calculation: correct the operation and recompute affected results.
- Inference: revise the claim or its conditions to match the result.
- Presentation: recover each passage's role in the reader's inference or action. Remove decision-irrelevant defensive content at its selection step; reconstruct necessary content around its actual proposition, evidence and determining quantities under PROSE. Preserve source truth conditions, numerical boundaries and explicit content requirements. Fix the whole unsupported parent claim or missing inference before polishing its sentences.
- Execution: repair the failed operation, resume its affected descendants and inspect the requested output through its existing owner. A revised success statement cannot repair a missing artifact or failed calculation.

Use econ-writing's `revise` mode for revision and its `compose` mode when the requested repair requires reconstruction; integrate the return into the assessment's named target.

For a revision or translation assessment, align the original and revised propositions through their actors, economic objects, quantities, conditions and source attachments. Check which group, period and comparison each unchanged number describes. For a model passage, match each verbal claim to the equation's domain, quantifiers, inequality and equilibrium response. Judge the target-language argument through these relations and preserve the author's adopted terms, notation and effective phrasing. Repair a changed meaning at the passage that introduced it, then reconcile its dependent restatements.

For each referee comment, recover the question, factual premise and requested change. Locate the relevant claim and its supporting manuscript passage, appendix, equation, exhibit or source before judging the premise. Resolve each substantive point through that evidence. A correct existing result retains its supporting derivation; a demonstrated defect receives the repair that changes the affected claim. Carry these decisions through the existing finding and manuscript correspondence. Apply the task's authority to the actual repair, including an already authorized analytical change.

Keep the target's permission and version binding with each support assignment. A finding-only request returns the supported defect and repair; an authorized repair request continues through the corrected producer and affected consumers to the actual inspected target. Preserve completed evidence and original returns across interruption and restore the unresolved defect and next authorized operation through the existing task state.

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

State the conclusion from the comparison. For an economic claim, use its generating comparison or calculation to distinguish an observed association, estimated effect or model implication when that distinction changes the interpretation. Compose a referee response from the inspected revision: answer the substantive point, give its evidence and identify the changed section, equation, table or figure. Explain a retained result through its adopted assumptions and supporting comparison. Match every claimed change to the actual revised text and reconcile the affected Abstract, Introduction, Results and Conclusion through their existing dependencies. Handle execution status, proposed analyses and revision history under [EXECUTION's record and artifact rules](../../runtime/EXECUTION.md), including explicitly requested operational content.

Return demonstrated defects and their needed repairs, plus the corrected target when requested. Use the affected object, consequence and completed repair to explain an execution defect. Complete authorized recovery and inspect its output before reporting success. Keep the requested artifact's substantive answer separate from work-status details through its existing owner. Continue the next authorized step in the parent task under its existing completion and stopping conditions.

## Evaluate specialized calculations and artifacts

Select the registered scientific condition for the requested [causal](../econ-design/references/causal-models.md), [market](../econ-design/references/market-models.md), [dynamic](../econ-design/references/dynamic-models.md), [macro](../econ-design/references/macro-models.md), [stochastic](../econ-design/references/dsge-models.md), [agent](../econ-design/references/agent-models.md) or [numerical](../econ-design/references/numerical-models.md) model. Match its identifying inputs and original equilibrium equations with the saved sample, estimator, covariance, converged policies and fitted counterfactual. Apply the requested comparison to the actual target and model.

Use `research_adaptive_experiments` to examine the fixed target, population, partition IDs, score history, generated candidates and selected final evaluation. Use `research_result_artifacts` to examine the automatic statistic registry and [article/slide bindings](../econ-writing/references/result-artifacts.md), including changed-result and changed-code detection. CORE governs the integrated review and the requested completion path.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `assess`: Assess the specified claim or artifact and return findings and proposed repairs.
- `assess+repair`: Assess the specified target and repair it within the requested change scope.
<!-- END GENERATED MODES -->
