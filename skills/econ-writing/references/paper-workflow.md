# From research records to a paper

Use this workflow for a new complete paper, a paper-wide argument plan or reconstruction from research records. For a specialist section or support to a supplied manuscript's revision, use the section-composition instructions below. Inherit [CORE](../../../runtime/CORE.md), [PROSE](../../../runtime/PROSE.md) and [econ-writing's common process](../SKILL.md#compose-for-the-medium-and-language). Complete the explanation before compression and perform the integrated editorial review on the requested result. Read the paper, section, exhibit or integration instructions needed for that result.

## Establish the argument from the research

Read the canonical research record and main exhibits. Identify the economic question, the knowledge or choice changed by its answer, and the main result: a magnitude for a quantitative finding, or the proposition and determining conditions for a theoretical finding. Trace each central claim to its supporting passage or calculation. Attribute source-reported findings and describe an executed calculation by its actual operation and output.

Compare the central finding with the closest existing explanation or result. Identify the measurement, variation or theoretical step that makes the contribution possible. Use econ-literature for an unresolved comparison with prior research and econ-design for an unresolved implication. State the paper's contribution through that specific difference and the result supporting it, rather than a general claim of importance. Carry the answer into the headline claim and body argument.

Compose passages whose sources and results are available. When a derivation or computation determines a requested result, resolve that dependency within the user's authority and record the operation in the existing work record. Carry forward sections whose inputs are unchanged.

## Design the paper's argument

Assign each section a claim or explanation needed for the central argument. Explain institutional rules before a comparison that depends on them and measurement before a design that depends on the measured object.

Use the Introduction to explain the question, decisive comparison, answer and contribution. Develop the supporting derivations, observations and estimated comparisons in the body. Place sample construction, specification details and diagnostics with the claims they establish. Include literature comparisons where they explain the added knowledge. Remove repeated explanations when integrating sections.

When the research distinguishes competing explanations, identify the comparison that separates their predictions. Explain what each comparison establishes and how they jointly answer the question. Use econ-design when the mechanisms still imply the same observed result. Select an exhibit that makes an empirical comparison recoverable through its groups, period, units, denominator and direct contrast. Use econ-data for a required calculation and return the result to the passage it supports.

## Compose the requested section

An Abstract compresses the question, decisive comparison, principal answer and economic meaning. Write it from the completed argument and findings. An Introduction explains why the question arises, how the comparison answers it and how the findings change existing knowledge.

For a specialist section, read the corresponding research source sections for the requested paper's institutional rules, data, methods and results. Record their edition and section in the existing source record when needed to locate the claims or continue the task. Resolve remaining wording or organization choices through [the profile-selection rule](../../../runtime/PROSE.md#select-the-profile).

An institutional section explains rules that change actors' decisions or generate the comparison. A data section connects the economic object to records, units and construction. An identification section defines the treatment, comparison and estimand, then explains the conditions and implementation that identify the effect. A results section states the answer and magnitude and explains its mechanism or economic meaning through the reported comparisons.

For theory, connect the defined object and assumptions to the proposition through the decisive derivation; explain which structural change alters the result. For a model-based counterfactual, connect the observations informing the model to the assumptions and behavioral responses generating the counterfactual. Use econ-design and [the model-to-observation mapping](../../econ-design/references/designs.md#connect-observed-choices-and-outcomes-to-the-model-and-interventions) for unresolved steps. Place supporting derivations and computations with the claims they establish.

## Choose and explain descriptive exhibits

Start with the economic question and the comparison the reader needs to see. Select the few exhibits that answer it from the adopted research results. Use [econ-data](../../econ-data/SKILL.md#produce-the-result-by-dependency) for sample construction, weights, denominators, bin summaries and other descriptive calculations. Own the visual encoding, caption and explanation here. Reuse the [result lifecycle](../../econ-data/references/reproducible-workflow.md#carry-analysis-results-into-tables-figures-and-prose) and existing figure producer: a label or layout revision redraws saved quantities; a changed sample, denominator or statistic returns to its calculation.

Choose a display the available data can support. A histogram needs observations or saved bin boundaries and counts; an exact ECDF needs values and their frequencies. Bin counts support cumulative shares at their known boundaries, not an invented within-bin distribution. A scatterplot needs paired quantities at its stated unit; paired group means can show a between-group relationship. Marginal means alone cannot recover a distribution or an individual-level association. Use a supported display that answers the question; obtain additional inputs only when the requested comparison requires them.

- **Where is the distribution concentrated, and how do its tails differ?** Use a histogram for mass across intervals or an empirical cumulative distribution for shares below thresholds without a bin choice. Compare histograms using common bin edges and axis scales. Counts answer how many observations or how much weighted population lies in each bin; within-group proportions answer what fraction does. Density is proportion divided by bin width, so area, rather than height, represents mass when widths differ. Label which quantity is shown. For unequal group populations, use comparable within-group shares or densities when the question concerns distributional shape; preserve counts when population size is the question.
- **Which groups have higher levels or shares?** Use aligned dots or bars with a meaningful group order and a shared scale. Bars start at zero because their lengths encode magnitudes. A dot plot can use a tighter, clearly labeled range when small differences matter. State whether a level is a mean, median or total and whose denominator defines a share. A larger total can reflect a larger population; use a rate or per-unit quantity only when that answers the economic question. Stacking suits parts of a common whole; aligned marks make individual group comparisons easier.
- **Which alternatives differ on common attributes?** Put the alternatives in rows and the common evaluation attributes in columns. Match each column's unit, period, population and reference definition across rows; convert from available source quantities only when the conversion is defined and authorized. Show an intended difference in the relevant header or cell. Keep a conclusion or interpretation outside the rows of comparable objects, and compare it with the displayed values.
- **How do estimates compare with a reference?** Align comparable series on a common scale and identify the reference group or value beside the exhibit. Match each point to its saved estimate and each requested range to its defined type and endpoints. Give different outcomes or units their own panels and labels. Match any numerical or conclusive title to those results. Use the saved contrast to report a difference between groups and route a requested calculation to econ-data.
- **How does a quantity evolve over time?** Use lines for ordered repeated measurements and points when observations are isolated. Keep actual time spacing, common units and comparable period definitions. Show missing periods as gaps rather than zeros or uninterrupted lines; label any adopted interpolation. Distinguish a changing population's series from a fixed-sample series. If an index is useful, identify its base period and level, and obtain that calculation from econ-data.
- **How do two measured quantities vary together?** Use a scatterplot, labeling the observation unit and both axes. Reduce overlap with smaller, transparent marks; use an explicitly defined binned or density display when overlap still hides the relationship. Route the aggregation to econ-data and explain what each bin represents. Label a fitted descriptive relationship and its sample if included; a causal interpretation requires an identifying design. Describe a plot of group means as a between-group relationship; individual-level relationships require individual-level quantities.

For each comparison, carry forward the adopted population, eligibility and missingness rules, period, observation unit, weights and quantity units. Use the same definitions across panels where the contrast requires them, and explain intended differences. A common-sample comparison is a substantive choice when it changes the target population; do not silently replace each group's eligible observations with complete cases. Distinguish unweighted observation counts from weighted population totals and identify the weights' meaning in the caption when used.

Choose a scale that lets the reader recover the comparison. Ordinary logarithmic axes require positive values: keep zeros and negative values visible on a suitable scale or in a separately explained view. Do not drop them or add a constant merely to make a log plot work. Displaying a saved level on a log axis changes its visual position; calculating a statistic of log-transformed observations belongs to econ-data under the adopted definition. Use comparable scales across comparison panels, or make an intentionally different scale conspicuous. Draw the quantities requested from the saved result and define any dispersion or range marks through their actual construction and endpoints.

Use short labels naming the economic objects, include units and readable ticks, and distinguish series without relying on color alone. Use the caption to supply definitions needed to interpret the marks that the title, axes and legend do not establish. Include a population, period, unit, denominator, bin boundary, weight or range definition when its omission changes the comparison the reader recovers. Keep other construction details in the existing methods or source record unless the request requires them in the caption. State the main comparison with its determining quantities when the title and labels do not convey it; omit repetition that adds no implication. For a caption requested on its own, apply this selection to the information available with that caption. Explain the economic meaning in the surrounding prose. Set sizes for the final page or slide and, when rendering is authorized, inspect that output at its intended viewing size for legible labels, clipping and distinguishable marks.

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

## Revise the integrated manuscript

Read the paper as one argument. Recover each paragraph's actual contribution to that argument as a reverse outline, using it to locate missing links, misplaced explanations and duplicated work. Supply missing links from cited passages or calculations, delete digressions, and move explanations to the claims they establish. Match the Introduction's promised answer and contribution to what the body actually establishes; revise unsupported promises instead of writing toward an imagined result. Reconcile claims with exhibits and make terms and referents consistent. Apply PROSE across the integrated manuscript for repeated rhetorical patterns, local revision, language-specific diagnosis and meaning checks. Use [writing:revise](../SKILL.md#revise) for scoped revision and econ-review for a requested independent assessment. Return from a local edit to the remaining requested manuscript work.

## Execute the paragraph architecture

Use [paragraph and argument guidance](paragraph-workflow.md) to resolve the actual dependencies of a long manuscript. In an Introduction, connect the shared situation and explanation problem to the question, answer and body claims. In each section, make its parent proposition follow from the concrete paragraph claims. Perform this reasoning in the draft and include the result in the integrated manuscript review. Preserve the adopted research choices and economic content when revising, translating or converting.

An explicitly selected formal paragraph certification or applicable platform contract activates the existing source-bound hierarchy, paragraph specifications, host assignments and independent final review under CONTROL. Complete those requirements within that selected workflow.
