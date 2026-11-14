# Paper procedure

From a filled worksheet and saved results to a paper, a section or a revision. Work through the steps in order; each ends with a block in section 7 of the worksheet `work/<topic>.md`. Text follows [WRITING](../../../runtime/WRITING.md): structure from English originals (`exemplars.py outline`), Japanese expression from Japanese exemplars (`exemplars.py find` and `style`), direct claims and numerical uncertainty.

Three rules hold throughout:

1. **The worksheet is the content.** Every paragraph carries the question, the model and its predictions, the comparison, an estimate or a decision from the worksheet. Content missing from the worksheet goes back to the step that produces it.
2. **One central object.** The same question, estimand, population and units appear in the title, abstract, introduction, body and conclusion.
3. **Numbers from saved results.** Every number comes from a saved result through the [result artifacts](result-artifacts.md) producers, with its unit, population and period.

## W1. Argument sheet

Fill before writing any prose:

```
Question:                 actors, choice, change, outcome (worksheet 2)
Answer:                   the main result with its magnitude, units, population (worksheet 6)
Why it matters:           the stake with its size (worksheet 1)
How we know:              variation or model operation that produces the answer (worksheet 4)
Mechanism:                the incentive or constraint that explains it, and the competing mechanism it rejects
Closest existing answer:  author (year): their result and its conditions (econ-literature)
Contribution:             what this paper establishes that the closest answer leaves open: a new quantity,
                          comparison, mechanism, population or derived implication
Decision implication:     the action it selects and its switching condition
Research type:            causal / theory / structural / descriptive / historical / macro / mixed
```

The research type fixes the chain the paper must make visible:

| Type | Chain |
| --- | --- |
| Causal | variation and its conditions → estimand, population and behavioral margin → estimated response → economic magnitude |
| Theory | conditions → proposition → decisive proof or optimization step → incentives, best responses, equilibrium implication |
| Structural | variation and restrictions → primitives → optimized behavior and baseline equilibrium → changed equilibrium → welfare |
| Descriptive or measurement | records, construction, sample, aggregation → measured object → comparable quantities with denominators |
| Historical | documents, authorship and purpose → institutional sequence → comparison they establish |
| Macro | shock or policy, initial and terminal conditions, horizon → transition and equilibrium → aggregate or distributional path → welfare |
| Mixed | for each component: the observation that disciplines a parameter → its equilibrium response → its valuation |

## W2. Section plan

Read the structure of two strong papers of the same type:

```sh
python3 skills/econ-writing/scripts/exemplars.py outline --lang en --function introduction --query "<topic words>"
python3 skills/econ-writing/scripts/exemplars.py outline --lang en --function results --query "<topic words>"
```

Fill one line per section and per paragraph:

```
Section:      <name>: the reader's question it answers; its exhibits
  Para <n>:   <move from the exemplar outline> → <worksheet item it carries>
```

Ordering rules: institutions before the comparisons that use them; variable construction before the results that depend on it; dependent results in the order of inference; parallel results by their weight in the answer; symbols defined at or before first use.

## W3. Compose section by section

Write each section from its plan lines and the checklist below; then read it against the plan.

**Title.** The central economic object and the relationship the paper establishes; setting, population or design only when the claim needs them.

**Abstract.** Question → identifying variation or model operation → main magnitude with object, unit, comparison and horizon → second result only when it changes the reading of the first → economic meaning. Meet the word limit by dropping detail, never the determining premise.

**Introduction.**
1. Opening: the economic fact, institutional choice or problem behind the question, with its source and size.
2. The question and the answer in the first page.
3. Why the answer is credible: the variation, measurement or model discipline.
4. Findings in sequence, each with its mechanism and magnitude.
5. Contribution against the closest studies on the axis that matters (object, variation, population, margin, restriction, implication), each citation tied to the finding its passage establishes.
6. Roadmap only when the paper's order is unusual.

**Literature review or survey.** Organize studies by the question and the object compared, explain how their findings relate through their populations and designs, and end with the synthesis the paper uses.

**Institutional background and data.** The rule, timing, eligibility, information or incentive that changes choices or creates the comparison; who assigns, delivers and receives. Then source records, observation unit, measurement, sample, geography and period; the denominator of each rate; descriptive exhibits that show the population and the variation.

**Identification and empirical method.** Write what a reader with core PhD training cannot supply: the setting's source of variation, the comparison, and the case-specific reason it identifies the estimand or could fail here; the textbook conditions of a standard design are omitted (WRITING rule 3). Define the estimand in its population before the estimator. Write the estimating equation, sample, weights and fixed effects, and show which coefficient or aggregation gives the estimand. Keep observation, assignment, analysis and inference units distinct. By design:

| Design | What the section establishes |
| --- | --- |
| RCT or encouragement | assigned offer, assignment unit, eligibility; delivered treatment; assignment effect as primary; receipt effect through the first stage; inference matching the randomization |
| DiD and event study | intervention, comparison group, why the comparison group's path stands in for the treated group's in this setting; group-time effects, anticipation, reference period, weights by horizon; leads with their joint test; the population each aggregate describes |
| IV | instrument's institutional source, the choice it moves, first stage and reduced form, complier population; strength diagnostics with their null |
| RD | running variable, cutoff, rule, local population; fuzzy jumps; density and covariate continuity; bandwidth, polynomial, kernel and inference |
| Synthetic control | treated units, donor pool, fitting period, weights, pre-period fit in outcome units, placebo inference |
| Shift-share | shares and their reference period, shocks, exposure; identifying variation and exposure-robust inference |
| Bunching | choice, incentive change, threshold; excess mass and the counterfactual density; the elasticity under the optimization model |
| Orthogonal scores, heterogeneity | target, score, cross-fitting; heterogeneity through direct group contrasts or calibration tests; policy value on held-out data |

**Theory, model and proof.** Actors, objectives, feasible choices, information, timing; the equilibrium concept. Each proposition: its economic content, formal statement with domain and quantifiers, and the decisive step with the assumption it uses, explained as the payoff, deviation or market response that makes it hold. Comparative statics through every affected choice, price and quantity, with changes in binding constraints. Welfare: objective, population, weights, transfers, costs and horizon, with the reference level named before the change.

**Structural estimation and counterfactuals.** Why the question needs the model's choice and interaction structure; each parameter with the variation, moment or likelihood that informs it; estimated, calibrated and fixed quantities with sources; fit in the data's units. The chain: primitives θ → equilibrium F(y; θ, z) = 0 → observation equation → estimate θ̂ → counterfactual y(θ̂, z′) → welfare from the same θ̂ and each scenario's equilibrium. Elasticities, markups and costs through the demand derivatives, ownership and conduct.

**Results.** One subsection per question the results answer. Each result: the estimate, its interval, the comparison that produces it, and a benchmark (baseline mean, denominator, population, period). Transformations stated with their formula: percent of baseline, percentage points, 100[exp(βΔx) − 1]. Tables explained by the contrast in their columns; figures by the objects compared, axes, reference and pattern. Mechanisms only with the intermediate evidence or derivation that supports them; subgroup claims through direct contrasts.

**Discussion and conclusion.** The implication for theory, behavior, allocation or policy, with costs, feasible actions and population; then the answer and its meaning. No repeated coefficients, second literature review or research plans.

**Appendix.** Proofs, measurement details, extra exhibits and computational definitions, each linked to its use in the main text, with the same symbols and labels.

## W4. Exhibits

For each table and figure, fill:

```
Exhibit <n>:   question it answers; saved result IDs; units, population, period; the sentence that reads it
```

Choose the display by the question: distribution → histogram or empirical distribution with declared height; group differences → dots or bars from zero with within-group rates; estimates → points with intervals around a marked reference; change over time → actual date spacing and marked base period; joint variation → scatter or binned scatter at a stated unit. Common bins and shared axes for comparable panels; shapes or line styles readable in grayscale. Tables follow the AEA rules in the profile. Render and read every exhibit at its final size.

## W5. Integrate and revise

1. Read the whole paper as one argument: each paragraph's proposition and its role in the answer.
2. Trace the answer from the results to the discussion and back to title, abstract, introduction and conclusion; they state the same object and numbers.
3. Check coverage both ways: every worksheet item the answer needs appears in the text, and every claim in the text has its worksheet item or saved result.
4. A changed estimate, source or definition reopens every passage and exhibit that uses it.
5. Japanese text: compare each sentence with its exemplar passages under WRITING section 2.

## W6. Submission and referee response

- **Submission:** apply the journal's current instructions on length, anonymity, abstract, references, exhibits and supplements; keep the document class; build and read the output.
- **Referee comments:** read all comments together; locate each comment's question and premise in the manuscript, equations, exhibits and results; repair shared premises once, at their source; update dependent passages, then abstract, introduction and conclusion. The response states for each comment the answer, the change made, the evidence or reasoning, and the exact location ([claim coverage and re-review](result-artifacts.md#claims-coverage-and-requested-re-review)).

## W7. Render and report

Build with the templates (`make build-paper`, `make qmd-pdf QMD=...`), read the rendered pages, repair at the producer, and record the output path in worksheet section 7. Long manuscripts with versioned paragraph dependencies use the [paragraph procedure](paragraph-workflow.md).
