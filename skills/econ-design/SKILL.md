---
name: econ-design
description: Develop an economics question or model, design identification and inference, or select among research methods and designs, including structural IO, dynamic choice, equilibrium counterfactuals and welfare.
---

# Economic design

This skill carries steps 1 to 4 of the [economist's procedure](../../runtime/ECONOMIST.md).

1. **Question.** Write the situation, the actors' objectives, choices, constraints and information, and the selected question into the worksheet (steps 1 and 2).
2. **Mechanism.** Build the model step by step through [modeling](references/modeling.md) (fill-in blocks, simulation template), with [model construction](references/designs.md#model-construction) for proofs and the knowledge library; write the competing mechanisms and the observation that separates them (step 3).
3. **Design.** Choose the estimand and identifying comparison through [estimand to method](references/designs.md#choose-the-estimand-and-method) and the section for the selected family: [causal](references/causal-models.md), [market](references/market-models.md), [dynamic](references/dynamic-models.md), [macro](references/macro-models.md), [DSGE](references/dsge-models.md), [numerical](references/numerical-models.md), [agent](references/agent-models.md), [adaptive experiments](references/adaptive-research.md). Read only the selected section.
4. **Method.** Pick the package call from the [implementation table](../econ-data/references/implementation-engines.md); with a saved selection contract run `python3 skills/econ-design/scripts/research_design.py select CONTRACT --root . --output outputs/selection.json`. Write the method and inference into the worksheet and hand the design to econ-data.

The full design procedure for each kind of work is in the [design workflow](references/workflow.md).

<!-- BEGIN GENERATED MODES -->
## Registered operations

- `design`: Choose a research question, model, identification strategy, study design or policy action.
<!-- END GENERATED MODES -->
