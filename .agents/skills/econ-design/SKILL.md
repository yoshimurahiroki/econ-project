---
name: econ-design
description: Develop an economics question or model, design identification and inference, or select among research methods and designs.
---

# Research design


<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `design`: Choose a research question, model, identification strategy, study design or policy action. Finish: Return the requested result when its input, content, format and authorized operation requirements are met.
<!-- END GENERATED MODES -->

## Purpose and input

[Task boundaries and completion](../../runtime/CORE.md) and [operation ownership](../../registry/operations.json) govern this specialist. Use [PROSE](../../runtime/PROSE.md) when explaining the result.

Input: Requested economic question, model or empirical design, closest literature and documented source fields.

For an explicit assessment of a specified claim or artifact, econ-review owns the assessment and this skill returns its technical design judgment.

## Procedure

### Identify the requested design work

When this design requires both an analytical result and source findings, or method applicability or selection remains unresolved, use [DECIDE](../../runtime/DECIDE.md) for problem formulation, decision selection and independent source integration.

Select the requested output: a research question, derivation, empirical design or recommendation. For a research question, identify the behavior, incentive, information constraint, allocation or equilibrium it would explain; use econ-literature to compare that contribution with the closest papers. For an economic choice, apply [DECIDE's action-selection procedure](../../runtime/DECIDE.md#select-a-feasible-action), expressing incremental benefits and resource costs for the same population, period and units and including existing uses of the same capacity. An assessment support call returns the requested technical judgment to econ-review.

When conflicting model results motivate a research question, express their choices and outcomes in a common model and vary the condition that can reverse the result. If aligned definitions resolve the difference, narrow the contribution accordingly. If an economic condition explains it, formulate the question around when that condition holds and select settings or measurements that distinguish its regimes.

When proposing a behavioral hypothesis, identify its driver, the quantity to measure independently, and the comparison where competing hypotheses predict different outcomes. Specify how cases differ in that driver while holding established determinants of the choice fixed, and how the measure would explain choices beyond established explanations.

For a design-only request, complete the question, hypotheses, identifying comparison, measurement targets, estimand and adopted design. When the request includes empirical measurement, calculate the comparison on the adopted sample and use its results to retain or revise the hypothesis. A completed design does not itself start measurement or estimation.

### For an empirical specification

Use [design elements](references/designs.md#design-elements) to define the parameter, comparison, assignment, controls and inference units. Translate the intervention into the information, feasible actions or payoffs it changes and the eligibility rule that includes actors. For staged implementation, locate the changed gate and retain eligible actors who do not proceed through it. Use timing gaps between information, contracting and implementation to find a comparison where one choice is fixed while another can respond. When explanations predict different responses, choose the population, timing or participation boundary where their predictions separate, then assess the explanations against that comparison.

When a proposed rule uses observed behavior to set eligibility, scores or prices, identify who can change that behavior after learning the rule. Compare fixed-input predictions with responses to the announced rule, including the cost of changing the input. Use the announcement-to-implementation interval and differences in the gain or cost of qualifying to distinguish anticipation from implementation effects; revise treatment timing, input assumptions or the policy comparison when those responses change the answer.

Use the [design-specific section selector](references/designs.md#select-the-needed-section) to match estimation and inference to the parameter, treatment path, heterogeneity, dependence and assignment units. Interpret each requested diagnostic through its null, precision and sampling design.

For implementation, pass the adopted estimator, sample, timing, weight meaning and inference requirements to [econ-data's engine selection](../econ-data/references/implementation.md#estimator-engine-and-algorithm-selection). A faster representation must preserve that contract; identify a proposed change in the economic specification and its affected comparisons as a design decision governed by [CORE](../../runtime/CORE.md).

### For a theoretical model

Choose the requested object: a payoff comparison, optimal choice, equilibrium, dynamic path or optimized value. Use the matching [model-construction operations](references/designs.md#model-construction). Retain structure whose omission changes that object, including waiting, nonparticipation, switching or actor composition. A baseline representing an existing institution preserves its objectives, rights and priority rules; a change to those features is a separate intervention to evaluate. A payoff comparison requires payoffs; deriving choices additionally requires a behavioral rule.

For interventions, include displacement into feasible alternative places, times or actions. If competitors or trading partners respond, include their outcomes in the aggregation boundary and reassess their eligibility as untreated comparisons. Use [observation mapping and interventions](references/designs.md#connect-observed-choices-and-outcomes-to-the-model-and-interventions) to map observed choices and outcomes to model parameters; use [restrictions and set-valued predictions](references/designs.md#construct-restrictions-and-set-valued-predictions) for deviations, multiple equilibria and compatible counterfactual sets.

### For behavioral responses and group comparisons

Distinguish a behavioral mechanism's total or fixed cost from its cost of an additional unit. Use the actor's decision rule and initial choice to derive the response to a cost change. Establish which choices cross the participation or supply threshold, or which feasible alternative becomes the chosen treatment. Express changes in net gains and changes in actions as separate economic objects.

An individual's monotone comparative static gives the direction of that actor's response. To compare group quantity changes, convert choices crossing the threshold into the comparison's quantity unit and apply population weights. When a change in the number participating can arise from entry or exit, compare those transitions and the quantities each contributes. Establish comparability of initial choice distributions, production opportunities and response margins at the affected thresholds. Choose the observation window from the response's adjustment and duration; a narrow window can precede implementation, while a long average can dilute a short-lived response.

### Establish feasibility

For each proposed design, map required measures and comparisons to documented fields and source records within the task's cost and access limits. Preserve supplied candidate IDs and scope. Use econ-data for field or linkage analysis. Repair input or implementation defects within the authorized design; record missing fields or permissions needed for the next operation and continue independent work.

### Choose among research designs

When asked to select a design, compare feasible candidates on their identified parameter, identifying assumptions, precision and data, implementation and delay costs. Evaluate precision against a stated economic threshold or target contrast, deriving it from the task's objective when available. If that criterion is missing, request it when its value changes the design choice. Use [DECIDE](../../runtime/DECIDE.md#select-a-feasible-action) to rank feasible designs, establish switch conditions and stop information gathering when it cannot change the action; return the selected design or its selecting conditions. Keep adoption decisions and project status in operational records; research artifacts state the economic comparison, assumptions and results.

## Output

The requested question, derivation, recommendation or design assessment, with the economic comparison and conditions that determine it.

