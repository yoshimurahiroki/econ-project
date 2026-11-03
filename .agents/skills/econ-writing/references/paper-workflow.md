# From research records to a paper

Use this workflow for a new complete paper, a paper-wide argument plan or reconstruction from research records. For a specialist section or support to a supplied manuscript's revision, use the section-composition instructions below. Inherit [CORE](../../../runtime/CORE.md), [PROSE](../../../runtime/PROSE.md) and [econ-writing's common process](../SKILL.md#compose-for-the-medium-and-language). Complete the explanation before compression and perform the integrated editorial review on the requested result. Read the paper, section, exhibit or integration instructions needed for that result.

## Establish the argument from the research

Read the canonical research record and main exhibits. Identify the economic question, the knowledge or choice changed by its answer, and the main result: a magnitude for a quantitative finding, or the proposition and determining conditions for a theoretical finding. Trace each central claim to its supporting passage or calculation. Attribute source-reported findings and describe an executed calculation by its actual operation and output.

Compare the central finding with the closest existing explanation or result. Identify the measurement, variation or theoretical step that makes the contribution possible. Use econ-literature for an unresolved comparison with prior research and econ-design for an unresolved implication. State the paper's contribution through that specific difference and the result supporting it, rather than a general claim of importance. Carry the answer into the headline claim and body argument.

Build candidate explanations from the relationships among the actual results. Compare the predictions each explanation makes for the available groups, margins and periods. A recurring pattern can identify the next mechanism to investigate; adopt the mechanism through its derivation or identifying comparison. Let a contradictory result change the parent claim and the dependent passages. Preserve the original research objective and settled specification while completing the analysis needed to resolve the consequential difference.

Compose passages whose sources and results are available. When a derivation or computation determines a requested result, resolve that dependency within the user's authority and record the operation in the existing work record. Carry forward sections whose inputs are unchanged.

## Design the paper's argument

Assign each section a claim or explanation needed for the central argument. Explain institutional rules before a comparison that depends on them and measurement before a design that depends on the measured object.

Make the parent claim explicit enough to determine what its support must establish. A mechanism section needs the choice margin and the response it predicts; an identification section needs the comparison and assumptions recovering the defined estimand. Preserve the same population, policy contrast, outcome scale and horizon across each inferential step, or explain the model or calculation that connects different objects. Order parallel findings by their contribution to the answer and dependent findings by the inference that uses them.

Use the Introduction to explain the question, decisive comparison, answer and contribution. Develop the supporting derivations, observations and estimated comparisons in the body. Place sample construction, specification details and diagnostics with the claims they establish. Include literature comparisons where they explain the added knowledge. Remove repeated explanations when integrating sections.

When the research distinguishes competing explanations, identify the comparison that separates their predictions. Explain what each comparison establishes and how they jointly answer the question. Use econ-design when the mechanisms still imply the same observed result. Select an exhibit that makes an empirical comparison recoverable through its groups, period, units, denominator and direct contrast. Use econ-data for a required calculation and return the result to the passage it supports.

## Compose the requested section

An Abstract compresses the question, decisive comparison, principal answer and economic meaning. Write it from the completed argument and findings. Select a result because it establishes the contribution, rather than because it is the largest or most statistically significant coefficient. An Introduction explains the gap between the existing explanation and the observed or theoretical problem, how the comparison answers it and how the findings change economic knowledge. Preserve a consequential non-effect, heterogeneity or counterfactual when it changes the mechanism or policy ranking; put technical detail with the claim whose validity needs it.

For a specialist section, read the corresponding research source sections for the requested paper's institutional rules, data, methods and results. Record their edition and section in the existing source record when needed to locate the claims or continue the task. Resolve remaining wording or organization choices through [the profile-selection rule](../../../runtime/PROSE.md#select-the-profile).

An institutional section explains rules that change actors' decisions or generate the comparison. A data section connects the economic object to records, units and construction. An identification section defines the treatment, comparison and estimand, then explains the conditions and implementation that identify the effect. A results section states the answer and magnitude and explains its mechanism or economic meaning through the reported comparisons.

For theory, connect the defined object and assumptions to the proposition through the decisive derivation; explain which structural change alters the result. For a model-based counterfactual, connect the observations informing the model to the assumptions and behavioral responses generating the counterfactual. Use econ-design and [the model-to-observation mapping](../../econ-design/references/designs.md#connect-observed-choices-and-outcomes-to-the-model-and-interventions) for unresolved steps. Place supporting derivations and computations with the claims they establish.

## Choose and explain descriptive exhibits

Define the comparison the reader must recover, then select its already calculated quantities through [the result lifecycle](../../econ-data/references/reproducible-workflow.md#carry-analysis-results-into-tables-figures-and-prose). Bind each displayed object to its saved value, unit and population. A change in measurement, sample, weights or aggregation belongs to [the data owner](../../econ-data/SKILL.md#produce-the-result-by-dependency); a change in labels or page arrangement redraws the same quantities.

Choose the representation from the observation structure and question:

| Question | Required observations | Representation and defining quantity |
| --- | --- | --- |
| How is a population distributed? | Individual values, frequencies or saved interval counts | Histogram height is count, proportion or density as declared. Density equals proportion divided by interval width, so its area represents population share. An empirical cumulative curve sums observed frequencies at their values; interval counts determine cumulative shares at interval boundaries. |
| Which groups differ? | Comparable group statistics with explicit denominators | Aligned dots or bars on a common axis. A bar's length measures its value from zero; a dot's position can use a labeled restricted range. Use within-group rates when comparing prevalence and totals when comparing aggregate quantities. |
| Which option performs better on several attributes? | Each option's values under common attribute definitions | Options occupy rows and attributes occupy columns. Give each column its unit, period and aggregation, then derive the decision from those values in the surrounding argument. |
| How do estimates compare? | Named estimates and the requested interval endpoints or reference | Show comparable estimates on the same scale, identify the reference and state the range's construction. Use the saved direct contrast for a requested difference. |
| How does the outcome change with time? | Repeated observations with actual dates and common units | Place points at their actual time spacing and connect the ordered series. Preserve observed gaps. Name an index's base period and value. |
| How do two quantities vary together? | Paired observations at the declared unit | A scatterplot locates each pair. Group averages describe between-group pairs; original individual pairs support individual relationships. Compute bins or densities upstream when overlap requires aggregation. |

Carry the adopted eligibility, missingness, period, observation unit and weight definitions into the display. Define a share by its numerator and denominator. Keep a sample change explicit in the analysis specification. Compare distributions with common bins and group proportions when population size differs; preserve counts when size answers the question. Stacked marks describe parts of a stated whole; aligned marks expose individual differences.

Select scales from the values and inferential comparison. A logarithmic axis represents positive levels; an analysis containing zeros or negative values uses a display defined for those observations. Calculating a transformed outcome or adding a constant changes its upstream definition. Use shared axes across comparable panels and label an adopted different scale at its panel. Explain a fitted descriptive relationship through its actual sample and equation, and explain a causal relation through its adopted identification.

Write object names and units beside the relevant marks. Use distinguishable shapes or line styles as well as color, readable ticks and enough space for the decisive contrast. A caption supplies the population, period, denominator, weights, boundaries and interval definition needed to read the exhibit. Develop the economic implication in the text from the displayed comparison. Inspect the rendered page or slide at its intended size and repair clipping, illegible symbols, ambiguous series and labels that no longer match the producing values.

### Example: draw an already calculated group share

Fictional question: what share of eligible households participated in each district in 2024? The selected saved result contains North `40.0` percent (40 of 100 eligible households) and South `60.0` percent (30 of 50). These are unweighted, exhaustive district records with no missing eligibility or participation status; the percentage calculation belongs upstream. The drawing reads those saved percentages rather than recomputing them. Language: Python with Matplotlib.

```python
import matplotlib.pyplot as plt

# Tiny stand-in for the selected, already aggregated result.
districts = ["North", "South"]
participation_pct = [40.0, 60.0]

fig, ax = plt.subplots(figsize=(5.0, 3.2), layout="constrained")
bars = ax.bar(districts, participation_pct, color="#336699", width=0.6)
ax.bar_label(bars, fmt="%.0f%%", padding=3, fontsize=11)
ax.set_ylabel("Eligible households participating (%)", fontsize=11)
ax.set_ylim(0, 100)
ax.set_yticks([0, 20, 40, 60, 80, 100])
ax.tick_params(labelsize=11)
ax.set_title("Participation by district, 2024", fontsize=12)
```

Expected: two bars starting at zero, North at `40` labeled `40%` and South at `60` labeled `60%`, on a shared 0–100 percent axis. Suggested caption: “Share of eligible households participating in 2024. Denominators are 100 households in North and 50 in South; records are unweighted and complete. Source: fictional district records.” South's 30 participants form 60% of its 50 eligible households; North's 40 participants form 40% of its 100. The existing output producer supplies the export path, format and manuscript caption.

## Connect the prose

Apply [relation-based sentence connections](../../../runtime/PROSE.md#connect-the-explanation) to connect the paper's argument. When the study establishes the mechanism, explain how an institutional rule changes costs, how costs change choices and how the empirical comparison measures that margin.

Connect sections through what the preceding result establishes and what the next comparison must resolve. For example, a treatment effect on purchases raises a different question from an effect on total consumption: the mechanism linking them requires evidence on substitution or a specified behavioral model. Supply that dependency from the study's actual design and results before carrying the claim into the Abstract or policy recommendation.

## Revise the integrated manuscript

Read the paper as one argument. Recover each paragraph's actual contribution to that argument as a reverse outline, using it to locate missing links, misplaced explanations and duplicated work. Supply missing links from cited passages or calculations, delete digressions, and move explanations to the claims they establish. Match the Introduction's promised answer and contribution to what the body actually establishes; revise unsupported promises instead of writing toward an imagined result. Reconcile claims with exhibits and make terms and referents consistent. Apply PROSE across the integrated manuscript for repeated rhetorical patterns, local revision, language-specific diagnosis and meaning checks. Use [writing:revise](../SKILL.md#revise) for scoped revision and econ-review for a requested independent assessment. Return from a local edit to the remaining requested manuscript work.

For a requested submission or revision response, use the actual journal instructions and editor/referee comments. Link each substantive comment to its disputed claim, original passage or calculation, adopted response and changed manuscript location. Explain a supported disagreement and retain the evidence; revise a supported defect through its existing design/data owner and update the affected exhibits and text. Keep unchanged results when their consumed inputs and definitions remain valid. Produce the requested response letter and submission files, inspect their rendered content and preserve submission authority. Use the existing task/source/result objects for this correspondence. A requested grant, preregistration or data-management artifact consumes the same adopted design, resources, access/retention constraints and reproducibility plan; its audience and destination determine the completed document.

## Execute the paragraph architecture

Use [paragraph and argument guidance](paragraph-workflow.md) to resolve the actual dependencies of a long manuscript. In an Introduction, connect the shared situation and explanation problem to the question, answer and body claims. In each section, make its parent proposition follow from the concrete paragraph claims. Perform this reasoning in the draft and include the result in the integrated manuscript review. Preserve the adopted research choices and economic content when revising, translating or converting.

Use the existing source-bound hierarchy and paragraph state when the requested paper needs resumable dependencies. Complete the integrated review under CORE and deliver the actual requested artifact.
