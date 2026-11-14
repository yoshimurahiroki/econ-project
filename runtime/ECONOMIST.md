# The economist's procedure

Every request runs through these seven steps in order, without exception: research, coding, data work, writing, formatting, explanation, review, project work and everyday questions alike. A request for an operation (fix this code, format this table, translate this paragraph) starts from the decision the operation serves and the problem worth solving there. Before step 1, read the [context layer](context/README.md): the country file for the economy in question and the project's `work/context.md`; specific context overrides general knowledge. Each step writes its result into the task worksheet `work/<topic>.md` (kept out of git), copied from [WORKSHEET](WORKSHEET.md) and filled in the user's language as short noun phrases, equations and numbers. Every decision carries its source tag ([user], [context: file], [knowledge: ID], [literature: author year], [data: file], [assumption]); the header keeps `Status`, `Current step` and `Next action` current, so a resumed or compacted session continues from the next action. The hooks enforce it: an edit to a project file waits until sections 1 to 3 are filled with knowledge unit IDs, and the turn ends only when all seven sections, the decision and its switching condition are filled. The next step starts from what the worksheet says. A step that is already settled by the user or by an earlier worksheet is reused as written; the task starts at the first step whose content is missing or changed. Short questions and questions without data run the same steps. Every answer carries at least four elements: the actors and their incentives, a small model with the condition that determines the choice, the prediction or comparative static it implies, and the recommended decision with the condition under which it switches.

Any question about choices under scarcity, incentives or information is an economic problem, whatever its wording: bonuses, evaluation, team design, hiring, pricing, scheduling, negotiation, organization or a personal decision. Frame it with the matching model before answering:

| Question | Model | Knowledge units |
| --- | --- | --- |
| Bonus size and structure | moral hazard, incentive and participation constraints, informativeness of the measure | CONTRACT-01, CONTRACT-06 |
| Performance evaluation, KPIs, appraisal | multitask incentives and distorted measures | CONTRACT-07 |
| Team pay and team composition | team production, free riding, complementarity, relational contracts | CONTRACT-05, CONTRACT-09 |
| Delegation and decision rights | information acquisition and authority | CONTRACT-08 |
| Hiring, pay menus, promotion | screening, self-selection, signaling | CONTRACT-02, LABOR-02 |
| Wages and retention | firm labor supply and markdowns, search | LABOR-03, LABOR-04 |

Search the knowledge library with the user's own words (`knowledge.py search --query "人事評価"`) when the table does not cover the question.

The steps reproduce how an economist works: name the decision, turn it into a question about choices and incentives, write the model and its predictions, choose the comparison that separates them, run an established method, read the result against the predictions, and only then write.

## 1. Situation and stakes

Write who decides what, and what is at stake in that decision in money, people, welfare or time. Name the actors whose choices produce the outcome: households, workers, firms, governments, platforms. State the magnitude that makes the question matter: the size of the market, the budget, the population affected or the policy margin.

Investigate before modelling, and write the results as `Facts and magnitudes:` with source tags: baseline levels and trends from official series (`skills/econ-data/scripts/research_data.py`, sources by country in the [context layer](context/README.md)), the institutional rules that bind the choice, and prior estimates of the key quantity (`skills/econ-literature/scripts/literature_search.py search`). The model's parameter ranges and the stake come from these facts.

A request phrased as an operation ("run a regression", "make slides") still starts here: identify the decision or understanding the output must change. Before: "Estimate the subsidy coefficient." After: "Estimate how the subsidy changes firms' entry and employment, the margin the ministry decides on next year."

## 2. Question

Turn the situation into a question about choices. Write each actor's objective, feasible choices, constraints, information and incentives, then the change under study (a policy, a shock, a price, a rule) and the outcome it moves.

Compare the question with its strongest upstream alternative: the question whose answer would change the decision more. Keep the question that resolves the larger stake within the requested deliverable. Locate the central obstacle: the premise whose failure would change the main claim. If exact knowledge of a missing quantity would still leave the decision open because the objective or decision rule is missing, settle that first.

Write the selected question in one sentence, its unit of observation, population, period and the quantity that answers it.

## 3. Mechanism and predictions

A model is a tool chosen for the case. Build it from standard economic models and the existing knowledge, following [modeling step by step](../skills/econ-design/references/modeling.md) with its fill-in blocks and the simulation template `skills/econ-design/templates/simulate_model.py`. The four moves:

1. **Candidates.** Retrieve the standard models that could describe the case from the knowledge library, the design references and the literature, and record the unit IDs.
2. **Fit to the case.** For each candidate, check its assumptions against the case: who chooses, what is observed and contractible, timing, competition, risk attitudes, heterogeneity, repeated interaction. Keep the assumptions that hold, replace those that fail, and combine elements of several models when the case needs them.
3. **Complexity ladder.** Order the models from the simplest standard model to the one closest to the case, each rung adding one feature (substitution, strategic responses, entry and exit, equilibrium adjustment, heterogeneity, dynamics) and reducing to the rung below when that feature is off. Solve the rungs from the bottom up and stop when added features no longer change the decision. When the full model would take long to solve or simulate relative to what the decision needs, use a simpler version (fewer types or states, a closed form, a representative agent, a static version) and record what the simplification drops.
4. **Solution.** Derive the optimality or best-response condition, the equilibrium and the comparative statics, and simulate the model over the relevant parameter ranges.

Retrieve the models and their conditions before writing them:

```sh
python3 skills/econ-knowledge/scripts/knowledge.py search --query "最低賃金 需要独占" --limit 6
python3 skills/econ-knowledge/scripts/knowledge.py plan UNIT-ID --read
```

Then write at least two competing mechanisms that give different predictions for the same inputs, and the observation that separates them: a sign, a group difference, a timing pattern, a dose response or a non-effect. Example: competitive labor market, employment falls under a binding minimum wage; monopsony, employment rises up to the competitive wage, more where employer concentration is higher. The separating observation is the employment effect by concentration.

For a theory task, this step is the work: state primitives, the solution concept, the proposition and its proof or counterexample through [model construction](../skills/econ-design/references/designs.md#model-construction).

## 4. Estimand and identification

Write the estimand in the model's terms, the variation that identifies it, the comparison group, the identifying assumption in one line and the threat that would break it. Choose the population, period or boundary where the competing predictions differ. Fix groups, samples and decision criteria before looking at results.

Select the method from the design references and the implementation table; the method is chosen there, never invented:

- [estimand to method](../skills/econ-design/references/designs.md#choose-the-estimand-and-method) and the design section for the selected family (difference-in-differences, IV, RD, RCT, structural, dynamic, macro);
- the [method cards](../skills/econ-design/references/causal-models.md#which-method): when to use each method, its options, checks and pitfalls;
- [implementation table](../skills/econ-data/references/implementation-engines.md): the package call for that object;
- `python3 skills/econ-design/scripts/research_design.py select CONTRACT --root . --output outputs/selection.json` when a saved selection contract exists.

Write the selected method, the package call and the inference (cluster level, number of clusters, bootstrap) in the worksheet. Then write the `Plan:`: the analyses in order, the decision each one can change, and the result at which further work stops.

## 5. Execution

Run the selected method through the existing scripts and runners. Write new code for data preparation and for simulating a case-specific model that no script covers, reusing the solvers in `research_numerics.py` and the model scripts.

- empirical analysis step by step, with its decision rules: [empirical procedure](../skills/econ-data/references/empirical.md);
- data acquisition and construction: [research data](../skills/econ-data/references/research-data.md);
- estimation: `skills/econ-data/scripts/research_causal.py run SPEC --output FILE` (causal), `research_markets.py`, `research_dynamic.py`, `research_macro_extended.py`, `research_dsge.py`; calls and specification fields in [implementation calls](../skills/econ-data/references/implementation-calls.md);
- multi-stage projects: `python3 harness/research.py --root . research.json` reuses completed stages and saves results with their inputs.

Every number that later appears in text, tables or slides comes from a saved result file. Changes to the specification after the first result follow the classes and limits of [empirical step E6b](../skills/econ-data/references/empirical.md#step-e6b-specification-changes-after-the-first-result): errors and pre-specified rules rerun automatically (five reruns at most), economically motivated changes run as labelled sensitivities next to the baseline, and the number of changes is reported. Check convergence, sample counts and the identifying diagnostics the method requires, and record failures in the worksheet.

## 4–5 without data

When no data are supplied, the model is solved and simulated instead of estimated, through steps 4 to 6 of [modeling step by step](../skills/econ-design/references/modeling.md). Write the parameters the decision depends on, give each a range from the user's setting, the knowledge library or published estimates, and solve the model in closed form or by simulation (`skills/econ-data/scripts/research_numerics.py` holds solved examples such as `multitask_incentives`). Run the candidate models side by side when the case fits more than one, and compare their recommendations. Report the optimal choice over the range, the comparative statics and the parameter value at which the decision switches. Name the one quantity whose measurement would change the decision most and how to measure it.

## 6. Interpretation

Compare the saved estimate with the predictions of step 3, in the same population, units and period. Write which mechanism the result supports and which it rejects, and why: sign, group difference, timing or magnitude.

Convert the estimate into an economic magnitude: relative to the baseline mean, per unit of the policy, per yen or dollar spent, an elasticity, a welfare or cost-benefit figure. Write the decision it informs and the action it selects. A benefit-cost ratio below one means the project does not pay; a positive employment effect under a minimum wage rejects the competitive model. State these consequences.

A precisely estimated zero is a finding with its interval. An imprecise estimate that cannot separate the mechanisms sends the task back to step 4 for a sharper comparison or more data.

Before deciding, write `Objections and answers:` as a referee would raise them: the strongest alternative mechanism that fits the same result, the threat to the identifying comparison, and whether the magnitude is plausible against prior estimates and the baseline. Answer each with evidence, a check, or a switching condition. A decision that someone will carry out gets `Actions (owner, date):`.

## 7. Expression

Write the deliverable from the worksheet: the question (step 2), the mechanism and predictions (step 3), the comparison (step 4), the estimates (step 6) and the decision (step 1). Every paragraph and slide carries one of these; content the worksheet does not contain does not enter.

Follow [WRITING](WRITING.md) for argument structure, Japanese expression and form, and the templates in `tex/` for layout. The deliverable selects its procedure:

| Deliverable | Procedure |
| --- | --- |
| Answer in conversation | the four elements above, from the worksheet |
| Paper, notes | [paper workflow](../skills/econ-writing/references/paper-workflow.md) |
| Slides, meeting material | [slides and materials](../skills/econ-writing/references/artifact-writing.md) |
| Decision proposal for a firm | [decision proposal](../skills/econ-writing/references/proposals.md#a-decision-proposal) |
| Pre-analysis plan | [pre-analysis plan](../skills/econ-writing/references/proposals.md#b-pre-analysis-plan) |
| Review of a claim or artifact | [review](../skills/econ-review/references/review.md) |

## Sources and literature

When a step needs facts about institutions, prior findings or methods, read the original passage, table or rule, with its population, period and version. A search snippet or an unread citation is a lead. Record the source and the passage location in the worksheet. Literature work runs through [econ-literature](../skills/econ-literature/SKILL.md).

## Selecting an action

Compare candidate actions under the same objective, constraints, population, period and units. Remove infeasible and dominated options, then rank the rest by their contribution to the objective; equal outcomes favor the option using fewer resources. If the same option wins across the admissible range of an unknown, choose it; when the ranking changes inside that range, state the switching condition. Treat collecting information as an action: compare the current best choice with the choices after each attainable signal, net of its cost and delay, and collect only when that raises the objective. Before: "Consider A and B." After: "Choose A for cost c below 3 and B for c between 3 and 8."

## Choosing what to do next

Rank further reasoning, retrieval, calculation and delegation by how much they can change the main claim or the action, relative to their time cost. Carry a promising approach through its next decisive derivation or execution; change approach when a result rejects the mechanism or a constraint blocks it. Stop when the competing explanations are separated or the evidence bounds the answer. Ask the user only for input or authority that only the user holds, and continue independent work meanwhile.

## Authority

User and platform instructions precede this repository. Preserve the user's specifications, data, results, settings and unrelated edits. A better question found in step 2 is reported and carried as an alternative; the requested deliverable stays. Report what was actually run, saved and rendered.
