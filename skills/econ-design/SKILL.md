---
name: econ-design
description: Develop an economics question or model, design identification and inference, or select among research methods and designs, including structural IO, dynamic choice, equilibrium counterfactuals and welfare.
---

# Economic design

## Purpose and input

[Task boundaries and completion](../../runtime/CORE.md) and [operation selection](../../docs/ai/compiled_ai_skills.md) govern this specialist. Use [PROSE](../../runtime/PROSE.md) when explaining the result.

Input: Requested economic question, model or empirical design and supplied premises. Use relevant literature when contribution or source investigation is in scope, and documented source fields when empirical measurement or data feasibility is in scope.

For an explicit assessment of a specified claim or artifact, econ-review owns the assessment and this skill returns its technical design judgment.

For a design-only request, complete the requested economic object and the assumptions and operations needed to establish it. An empirical design specifies its question, identifying comparison, measurement targets, estimand and inference; a theoretical design specifies primitives, feasible choices, solution concept and the proposition or comparative static sought. Include testable hypotheses when they are part of the requested design. When the request includes empirical measurement, calculate the comparison on the adopted sample and use its results to retain or revise the hypothesis. A completed design does not itself start measurement or estimation.

## Select the operation

Start with the [operation index](../../docs/ai/compiled_ai_skills.md), select `design`, and identify the requested economic object from the supplied question and adopted specification. Use this table to choose the applicable workflow and method sections. Read each selected body and its required premises completely before deriving or adopting the result. An index locates the source; the source establishes its conditions and reasoning. Reuse complete same-version reads and matching adopted results.

| Requested object or decision | Complete workflow | Activation |
| --- | --- | --- |
| Research question, hypothesis, diagnostic comparison or design-only scope | [Identify the design work](references/workflow.md#identify-the-requested-design-work) | `design_question_formation` |
| Empirical specification, measurement or identification | [Empirical specification](references/workflow.md#for-an-empirical-specification) | `design_empirical_specification` |
| Payoff comparison, choice, equilibrium, path or value | [Theoretical model](references/workflow.md#for-a-theoretical-model) | `design_theoretical_model` |
| Behavioral response or comparison of group quantities | [Responses and groups](references/workflow.md#for-behavioral-responses-and-group-comparisons) | `design_behavioral_response` |
| Data or computational feasibility, preregistration or research cycle | [Feasibility](references/workflow.md#establish-feasibility) | `design_feasibility` |
| Selection among feasible research designs | [Design comparison](references/workflow.md#choose-among-research-designs) | `design_choice` |
| An executable causal, structural, dynamic or equilibrium method | [Method selector](references/workflow.md#specialized-executable-designs) | The selected `method_*` condition |

Use [econ-knowledge](../econ-knowledge/SKILL.md) for the selected definitions, model equations and necessary prerequisites. Connect the chosen model and identifying conditions to the method section, then to [econ-data](../econ-data/SKILL.md) when execution is requested. Preserve the adopted scientific specification through that handoff. Select the whole workflow only when all of its branches are required.

## Output

The requested question, derivation, recommendation or design assessment, with the economic comparison and conditions that determine it.

For a delegated design, return the economic object, population, timing, assumptions, identifying comparison or equilibrium, determining evidence and next operation. Match each calculation and source to the adopted estimand, model and units. Follow [TEAM](../../runtime/TEAM.md) for return and resumption.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `design`: Choose a research question, model, identification strategy, study design or policy action.
<!-- END GENERATED MODES -->
