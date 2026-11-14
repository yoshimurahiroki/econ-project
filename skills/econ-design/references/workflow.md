# Design procedure

Steps 2 to 4 of the [economist's procedure](../../../runtime/ECONOMIST.md) in detail: from a request to an adopted question, model and design. Work through the steps in order. Each step ends with a block copied into the worksheet `work/<topic>.md` and filled; a step whose block is empty is not done, and the hooks hold edits and the end of the turn until sections 1 to 3 and then all sections are filled.

Three rules hold throughout:

1. **Write before choosing.** Every choice (question, model, design, method) is written in the worksheet with its reason before the next step uses it.
2. **Compare, then adopt.** Every adopted item names the alternative it beat and the observation or calculation that decided.
3. **Decision rules decide.** When a table in this file or in [designs](designs.md) covers the case, its first matching row decides; deviations are written with their reason.

## D1. Kind of design work

Pick the first row that matches the request.

| Request | Output of this procedure | Steps |
| --- | --- | --- |
| A research question or project idea | adopted question with contribution | D2, D3, D4, D7 |
| A model, a derivation or a proof | model, solution and proposition | D2, D3 ([modeling](modeling.md)) |
| An empirical design for a given question | estimand, comparison, method, inference | D2, D4, D5, D6, D7 |
| A choice among designs or methods | ranked designs with the switching condition | D2, D5, D8 |
| A policy or business recommendation | model, simulation and decision rule | D2, D3, [modeling](modeling.md) steps 4 to 6 |
| Preregistration, grant or data plan | design with confirmatory and exploratory branches | D2 to D7 |

```
Kind of work:   <row>
Deliverable:    <file or answer>
```

## D2. Question

Fill:

```
Decision and decision maker:        who acts on the answer, and what they choose
Behavior or mechanism explained:    the choice, incentive, information problem or equilibrium at the core
Question (one sentence):            how does <change> affect <choice/outcome> of <actors>, <population>, <period>
Closest existing answer:            paper or result, and what it leaves open (econ-literature)
What this question adds:            new variation, new mechanism, new population, new decision margin
Upstream alternative:               the question whose answer would move the decision more; why this one is kept
Central obstacle:                   the premise whose failure would overturn the answer
```

Rules:

- A question that names only a statistical operation ("regress y on x") is restated as a change in choices or outcomes. Before: "Estimate the subsidy coefficient." After: "Estimate how the subsidy changes firms' entry and employment under next year's policy contrast."
- When the closest existing answer already settles the question for this population and margin, narrow the question to the margin it leaves open or report the existing answer.
- When exact knowledge of a missing number would still leave the decision open because the objective is undefined, settle the objective first.

## D3. Model and predictions

Run [modeling step by step](modeling.md): candidates from the knowledge library, the fit table, the complexity ladder, the solved model. Then fill:

```
Adopted model (rung):                <model>, knowledge units <IDs>
Prediction of interest:              sign or size of the effect, comparative static
Competing model and its prediction:  <model>: <prediction>
Separating observation:              sign, group difference, timing, dose response or non-effect that differs
```

Rules:

- **Two predictions at least.** A design with one prediction cannot fail; add the strongest competing mechanism.
- **Conflicting model predictions:** put the choices and outcomes of both models into one common model and vary the condition that reverses the result; the separating observation is that condition.
- **Behavioral hypothesis:** name the driver, an independent measure of it, and the comparison where standard and behavioral predictions differ.
- **Diagnosis of a problem:** derive the margin linking obstacle, intervention and resulting choice, including displaced activity and responses of existing participants; a local target can improve while total value falls.

## D4. Comparison that separates the predictions

Fill:

```
Population, period or boundary where predictions differ:
Treated and comparison units:
Assignment of the variation:         random / rule / timing / threshold / instrument / none
Groups, sample and criteria fixed before seeing results:  yes, written in the worksheet
```

Rules:

- **Policy expansion:** compare the actors moved by the new policy with those moved by the identifying variation; a mismatch is a different estimand and is written as such.
- **Finite or phased interventions:** the response over the whole path is the object; one-period contrasts are rungs.
- **Eligibility:** define who is eligible and what changes for them (information, actions, payoffs), keeping eligible nonparticipants in the population.
- **Timing gaps:** when one choice is fixed and another responds, the estimand names which.
- **Announced rules:** when an eligibility or score rule is announced, include anticipation and manipulation of the score in the comparison.

## D5. Estimand and method

Follow the estimand-to-method sequence in this order and fill each line:

```
Requested use of the estimate:        the decision of D2 and its threshold
Population and contrast:
Observation unit and assignment unit:
Outcome and scale:                    levels, logs, rates, shares, counts
Identifying variation:
Inference:                            cluster level, number of clusters, small-sample rule
Method:                               the first matching row of empirical.md step E4
Package call:                         from the implementation table
```

Use [designs: estimand and method](designs.md#choose-the-estimand-and-method), the family section of [designs](designs.md) (difference-in-differences, RD, IV, shift-share, synthetic control, structural, networks) and the [implementation table](../../econ-data/references/implementation-engines.md). A saved selection contract runs through `python3 skills/econ-design/scripts/research_design.py select CONTRACT --root . --output outputs/selection.json`. A structural model uses the matching file: [market](market-models.md), [dynamic](dynamic-models.md), [macro](macro-models.md), [DSGE](dsge-models.md), [numerical](numerical-models.md), [agent-based](agent-models.md).

## D6. Variables

For each variable, one line:

```
<name>: role (outcome / treatment / instrument / running variable / control / weight / cluster), definition,
        unit, timing relative to treatment, source field, construction
```

Rules:

- Controls are measured before treatment; a post-treatment variable enters only as an outcome or a mediator.
- Weights state whose average they produce.
- When predictive learners choose nuisance controls, the identifying adjustment set stays in the model.
- The construction record travels with the data into estimates and writing (`research_design.py variables`).

## D7. Feasibility

Fill:

```
Data source and documentation read:   <source>, <fields>, <grain>, <period>, <keys>
Variation present in the data:        number of treated units, timing, support near the threshold, first stage
Expected precision:                   minimum detectable effect against the decision threshold of D5
Access and permissions:
Confirmatory and exploratory branches (for preregistration):
```

Rules:

- Inspect the real documentation or a data sample before adopting a design; a design without its variation in the data returns to D4.
- When the minimum detectable effect exceeds the decision threshold, report this and return to D4 or D5 for a sharper comparison or more data.

## D8. Choice among designs

When several designs remain, fill one row each:

```
Design   Estimand   Identifying assumption   Precision vs threshold   Data and delay cost   Decision it supports
```

Rule: rank by whether the design can change the decision of D2 (precision against the threshold), then by cost and delay; the same winner across the admissible range is adopted, otherwise write the switching condition. Novelty of a method and the length of a menu carry no weight.

## Hand-off

Copy into the worksheet sections 2 to 4: the question (D2), the model and predictions (D3), the comparison, estimand, method and inference (D4 to D6), and pass the design to [econ-data](../../econ-data/SKILL.md) for execution through the [empirical procedure](../../econ-data/references/empirical.md).
