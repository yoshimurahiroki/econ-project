# Descriptive quantities and inference

Use for descriptive statistics: choosing the population, unit, weights and summary from the question, and reporting denominators.

## Choose descriptive statistics from the question

- Start with the population and period the question concerns, the unit receiving equal or weighted representation, and the quantity to summarize.
- Reuse adopted definitions; resolve a missing choice when it changes the economic object.
- Save the selected summaries with their sample definition, units, grouping keys and denominators for downstream tables and plots.

- **What is observed?** On the eligible population, count usable observations, observed zeros, missing values and suppressed values separately; retain censoring information where present. Zero is a subset of observed values, not a separate exclusion. Save variable-specific usable counts for available-case summaries and display them where differences in support affect the comparison. Do not discard an observed outcome merely because an unrelated regressor is missing. For a model-sample description, use the actual fitted sample, including estimator omissions. A shared denominator must be deliberate rather than the accidental result of a library dropping rows.
- **Whose typical experience?** A record-level mean in a panel weights entities with more usable periods more heavily. For the average entity's period-average outcome, first form each entity's average over the defined period support, then average entities with the adopted entity weights. For the average period's population outcome, aggregate within period first. State how incomplete period coverage enters; neither equal entity weights nor an unbalanced record mean repairs missing periods. Report the number of records, entities and periods wherever each matters.
- **How much, how often, or how large on average?** Use a sum for the amount across included units, retaining coverage so an observed subtotal is not described as a complete population total. Use total events divided by corresponding total exposure for an exposure rate, with the eligible numerator and denominator formed on the same support. Use an arithmetic mean for an equally represented analysis unit, or `sum(w*y) / sum(w)` on the same usable value–weight pairs for the adopted weighted mean. Establish whether weights represent frequency, population expansion, exposure or another adopted role; a normalized weighted mean is not an expanded population total. Account for missing or unusable weights and require a defined, nonzero denominator.
- **Where is the distribution concentrated?** Use a median or selected quantiles for a typical rank or tail question; use a mean when the question concerns expected amounts or additive totals. Select spread or tail summaries when those features matter rather than assuming the mean describes them. Record quantile probabilities, interpolation or order-statistic convention, and any weighting convention; match these across engines. A median of subgroup medians is not generally the pooled median. Do not silently drop genuine extremes or replace a mean with a median to make the result look stable.
- **Which group supplies the denominator?** For within-group rates or shares, divide by that group's eligible exposure or count; for a group's share of the population total, divide by the corresponding across-group total. Identify missing group labels and groups with no usable values. A zero count of observed events with positive exposure can give a zero rate; an empty group or zero exposure cannot. Keep counts, denominators and group definitions alongside comparisons so composition changes remain visible.
- **Which measure of dispersion?** Standard deviation uses variation among the defined units, the chosen variance divisor and the weight convention. Calculate each requested statistic using its adopted sampling, clustering or survey design. A descriptive-dispersion request uses the selected descriptive measure.
- **Conditional on what?** Label a summary among participants, employed people, positive outcomes or another selected group with that condition. To describe the whole target population, use its unconditional observations or combine conditional quantities with the relevant group shares under the adopted definition. An adjusted model prediction at fixed covariates differs from a prediction averaged over a stated covariate distribution; neither is automatically the raw observed mean. Keep the conditioning set or averaging population with the saved result.
- The existing `research_data.py describe SPEC --root PROJECT --output GENERATION --rscript Rscript` operation computes Table 1 through `modelsummary::datasummary`.
- It saves the full selected sample and each declared group with mean, SD, median, requested quantiles, minimum, maximum and usable source-record N. Set `observation_unit` and an `entity` identity column for record and entity counts.
- The saved sample flow retains both counts at each selection step.
- An adopted period column produces the same summaries by period in `display.by_year` and the existing trend blocks.
- Available-case and fitted-sample definitions retain their variable-specific row IDs in the private sample record.
- The result metadata carries population, sample, group levels, period/time definition, outcome units, denominator, weight meaning, variance convention and quantile convention.

- Request a balance comparison explicitly, for example `"balance": {"control": "0", "treated": "1", "inference": {"method": "welch", "confidence_level": 0.95}, "smd": {"denominator": "pooled_sd"}, "plot_smd": true}`.
- The contrast is treated minus control.
- The runner saves both group means and counts, the official estimate, standard error, statistic, degrees of freedom, p-value and interval endpoints.
- `mean_difference` retains the unadjusted group-mean difference; `difference` retains the official estimator's contrast.
- `estimatr` accepts the adopted `clusters` and `blocks` column names and retains the official design name; a blocked estimator follows its design-defined aggregation.
- `welch` calls `stats::t.test`.
- A descriptive contrast with `inference.method: "none"` saves the means and SMD without inferential cells.
- SMD is the unadjusted mean difference divided by `sqrt((treated_variance + control_variance) / 2)` for `pooled_sd`, or by the control SD for `control_sd`.
- A zero or missing scale produces a null SMD.
- `plot_smd: true` adds a saved `display.smd` block.
- Legacy specifications without `balance` retain their existing `display.balance` identity as a group-summary block with `difference_in_means: false`.

- Weight types select eligible inference.
- Frequency weights are nonnegative integer multiplicities; Welch inference explicitly expands those multiplicities before the official call and records both source-record N and frequency N. Probability weights preserve their original scale, use ML weighted dispersion for descriptive SD and the scale-invariant weighted ECDF `i/n` quantile convention; inference uses `survey::svydesign` and `survey::svyglm` with the adopted `ids`, optional `strata`/`fpc` column lists and explicit `nest` boolean.
- `ids: []` declares independent sampling.
- Construct the survey design from all positive-weight input records, then select the adopted sample, period, groups and variable support as a survey domain.
- The full input design retains excluded-domain PSU and stratum contributions.
- Analytic or reliability weights use `normalization: "sum_to_n"` for descriptive dispersion and `analytic_wls` only when the adopted error model assigns inverse-variance meaning to those weights; the official `stats::lm`, `summary` and `confint` methods supply inference.
- Population-expansion summaries alone do not assign a sampling design and use `method: "none"`.
- The runner rejects an incompatible weight/inference pair.
- Weighted moments and quantiles retain the declared `Hmisc` conventions through `datasummary`; a custom `datasummary_balance(fn=...)` does not establish weighted summaries.

- These numerical operations run only under the explicit `describe` execution.
- The existing result JSON stores full-precision Table 1, balance, sample flow, by-period summaries and requested distribution/ SMD display rows.
- Registration and display consume those saved rows; they do not load source data, rerun an estimator, infer p-values or reconstruct intervals.
- A scientific definition change creates a newly executed result under the existing result-identity contract.

### Example: choose available cases and the represented unit

- Fictional operation trace: five eligible shop–month records cover shops A–D in a two-month window.
- A has observed sales `0` and `18`; B has one observed value `6`; C has one missing value; D has one suppressed value.
- Sales use the same toy currency and price base.
- A's second record has a missing regressor; the other four records have that regressor observed.
- Unrecorded shop–months are outside this supplied coverage, not observed zeros.
- The stipulated descriptive question uses available observed sales; the stipulated model uses complete cases on sales and the regressor.

- The eligible records number `5`: sales are observed on `3`, missing on `1` and suppressed on `1`; the observed-zero count is `1` within the `3`.
- The observed subtotal is `0 + 18 + 6 = 24`, and the record-weighted mean is `24 / 3 = 8`.
- Sorted observed values are `0, 6, 18`, so the middle-observation median is `6`.
- For an equally weighted average of the two shops' available-period means, A contributes `(0 + 18) / 2 = 9` and B contributes `6 / 1 = 6`, giving `(9 + 6) / 2 = 7.5`; this is not a balanced two-month population mean.
- The model sample retains A's first record and B's record, so its descriptive mean is `(0 + 6) / 2 = 3`.
- These results answer different questions; none turns the observed subtotal into sales for all four shops.
