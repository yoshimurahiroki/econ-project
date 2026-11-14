## RCT design, assignment and diagnosis

Use to design, assign, analyze and diagnose randomized experiments: blocks and clusters, assignment probabilities, randomization inference, power and attrition.

Select `design="rct"` or `"rct_design"`, or `design="auto"` with `conditions.assignment_mechanism="randomized"`, and target `itt`, `ate` or `power`. Choose the outcome population and measurement period, assignment unit, intervention and interference mapping before allocation. Cluster assignment implements a joint intervention on the cluster; `interference="within_cluster"` defines its cluster-level assignment contrast. Cross-cluster or individual network exposure effects use the existing network-exposure owner. Receipt LATE selects the IV owner with assignment as the instrument and the adopted relevance, exclusion and monotonicity conditions.

The existing command `python skills/econ-data/scripts/research_causal.py run SPEC.json --output RESULT.json` accepts `method="rct_design"` and `inference={"type":"official"}`. Its R calculation lives in the sibling `research_rct.R` and inherits the project's R startup profile, working directory and library paths. The common specification supplies data, unique row ID, outcome, population, period, outcome unit and estimand. `regressors` names numeric pretreatment covariates; `endogenous` and `instruments` are empty. An assignment roster has one row per outcome unit and no existing treatment column. `analyze` requires complete numeric outcomes and the observed assignment labels.

Required options are `operation` (`assign`, `analyze` or `diagnose`), `treatment`, integer `seed` and `experimental_design`. For example:

```json
{
  "operation": "assign",
  "treatment": "assignment",
  "seed": 912,
  "weights": "population_weight",
  "experimental_design": {
    "conditions": ["control", "treatment"],
    "blocks": "stratum",
    "clusters": "village",
    "block_m_each": {"north": [4, 2], "south": [2, 4]},
    "interference": "within_cluster"
  }
}
```

Omit `clusters` for individual assignment and `blocks` for an unblocked design. Every cluster belongs to one block. `conditions` gives the adopted arm order, with the first arm as reference. Choose one allocation field: `m_each` or `prob_each`, or a block-label map `block_m_each` or `block_prob_each`. Counts refer to assignment units, so cluster counts replace row counts in cluster designs. Their vector order follows `conditions`; omitted allocation uses the official equal-probability complete design. Two-arm probability allocation uses randomizr's complete-randomization rounding distribution. Complete multiple-arm and factorial designs require fixed integer arm counts in each block, supplied directly or through matching probabilities. This matches the official multi-arm joint-inclusion calculation. Every unit has positive probability in every arm. IDs and group labels retain their original text, including leading zeros.

For a two-level factorial, replace `conditions` with `factorial`, for example `{"offer":["no","yes"],"reminder":["no","yes"]}`. The full Cartesian cells become named conditions such as `offer=yes|reminder=no`. Each allocation vector follows the saved `factorial_cells` order. Default factorial contrasts multiply the selected factors' low/high signs and divide by `2^(K-1)`, where K is the factor count. In a 2-by-2 design this gives main effects averaged equally over the other factor and an interaction equal to half the difference-in-differences. `contrasts=[{"name":"...","weights":{"cell label":number,...}}]` supplies another finite zero-sum contrast over every cell.

### Covariate-balanced assignment

Set `experimental_design.ra_type="balanced"` to call native `randomizr::balanced_ra` through `declare_ra` and `conduct_ra`. `formula="~ age + score"` adds native cube-on-X balancing and also selects this design. Its one-sided formula uses the numeric pretreatment columns declared in `regressors`. The formula's intercept supplies the count constraint. `prob` is a shared two-arm treatment probability, `prob_unit` names a column of unit-specific treatment probabilities, and `prob_unit_each` names one probability column per condition in the saved condition order. Choose one of these or the existing `prob_each`; omitted probabilities use native equal allocation. Fixed count and block-count fields belong to the complete-design path.

The formula path has two arms and supports clusters; the native API excludes simultaneous blocks and a `prob_unit_each` matrix. With clusters, the native balancing covariates are unweighted within-cluster means and each cluster receives one assignment. Probabilities are constant within each cluster. Without a formula, balanced allocation supports blocks, clusters, multiple arms and the existing factorial condition map, including unit-specific probability matrices. The native function holds allocation counts against their probability totals and the formula targets `X'Z` near `X'pi`; its landing step determines attained covariate balance. The runner retains that native assignment without rejection sampling or replacing it with a fixed-count declaration.

`balanced_ra_probabilities` supplies exact first-order condition probabilities in the same row order as the declaration. The saved assignment includes every probability, assignment-unit ID, formula matrix and formula-column order. Analysis with `assignment_result` restores those identities and requires the same balancing matrix. Target-population weights govern the outcome estimand; they do not change the native cluster-mean balancing rule.

Balanced analysis uses official `estimatr::horvitz_thompson` point estimates with `se_type="none"` and the actual two-condition probability matrix in the native outcome/arm row order. A general zero-sum factorial or multi-arm contrast is the specified linear combination of these native pair estimates over the same population denominator. Balancing regressors retain their allocation role; this HT calculation applies no regression adjustment. The native HT call requires observed outcomes in each compared arm. `ri.method="monte_carlo"` is required for balanced `analyze` and `diagnose`. The main p values test the declared sharp null using the actual assignment mechanism. Average-effect standard errors and confidence intervals are absent because this native path exports no cube-design joint probabilities.

### Assignment probabilities and the estimator

For complete allocation, the default pairwise estimator is `estimatr::horvitz_thompson`, with `condition_prs` set to the complete `ra_declaration` and explicit `condition1`/`condition2`. For positive fixed population weights w, its target and estimate are

\[
\tau_{ba}=\frac{\sum_i w_i\{Y_i(b)-Y_i(a)\}}{\sum_i w_i},\qquad
\widehat\tau_{ba}=\frac{1}{\sum_i w_i}\sum_i w_iY_i
\left\{\frac{1[Z_i=b]}{\pi_i(b)}-\frac{1[Z_i=a]}{\pi_i(a)}\right\}.
\]

The official call uses transformed outcome `N*w*y/sum(w)`. It retains all N rows for a multi-arm contrast. The declaration provides the marginal and joint inclusion probabilities for its `youngs` variance calculation, including block allocation and joint cluster assignment. The result saves official standard errors and normal pointwise intervals. A multi-contrast HT result retains each native variance and interval; `inference.covariance_available` records availability of the joint contrast covariance.

`estimator="difference_in_means"` selects the official unweighted two-arm individual/block complete-design calculation. `estimator="lm_robust"` selects a regression containing each block-by-condition cell and its interactions with pretreatment covariates centered at that block's weighted population mean. Each block's contribution uses its target population weight share. Full rank and observed support in every required cell determine estimability. A reversible coefficient-basis change makes each requested standardized contrast an actual `lm_robust` coefficient, preserving the official HC2 or cluster CR2 covariance, contrast-specific degrees of freedom and t interval. General factorial contrasts and covariate adjustment select this regression. The saved native fits retain coefficients, covariance and interval endpoints.

The assign result contains the realized labels, row and assignment-unit IDs, block/cluster correspondence, every marginal assignment probability, the probability of each observed assignment, population weights and L'Ecuyer-CMRG state before and after allocation. Set `assignment_result` to that result's relative path during analysis. The runner checks identical design, seed, IDs, row order, group correspondence, probabilities and labels before fitting. `receipt` names an observed receipt column for the saved assignment-by-receipt table; the analyzed contrast remains assignment ITT.

### Randomization inference

Add `ri={"method":"exact","seed":205,"maximum_permutations":10000}` or `ri={"method":"monte_carlo","seed":205,"draws":1999}`. Optional `null_effects` names a constant effect for every arm, with zero for the reference arm. The sharp null is `Y_i(a)=Y_i(reference)+null_effects[a]` for every unit and arm, with observation status fixed across assignments. The statistic is the absolute contrast estimate centered on that null contrast, using the same estimator and population weights.

Exact inference uses `obtain_permutation_matrix` and `obtain_permutation_probabilities`; the probabilities sum to one and recover the declaration's marginal probabilities. The p value sums those actual assignment probabilities over statistics at least as extreme as observed. Monte Carlo inference draws independently with `conduct_ra(declaration)` and uses `(1+exceedances)/(1+draws)`. The result retains the sharp null, seed, draw count, sampling method and statistic draws, plus enumeration probabilities for an exact test. These p values test the saved sharp null; a complete-design official interval describes the saved average-effect contrast. Balanced designs use Monte Carlo draws of the entire declared assignment vector: assignment units within that vector follow the joint cube allocation, and each `conduct_ra` draw is independent. `obtain_permutation_probabilities.ra_balanced` does not enumerate the native assignment support.

### Power, MDE, adherence and attrition

Set `operation="diagnose"` and provide `simulation`:

```json
{
  "effect_grid": [0, 0.5, 1, 1.5, 2, 2.5],
  "arm_effects": {"control": 0, "treatment": 1},
  "outcome_sd": 1,
  "icc": 0.2,
  "adherence": {"control": 1, "treatment": 0.7},
  "attrition": 0.15,
  "replications": 300,
  "seed": 1631,
  "target_power": 0.8,
  "test": "wald"
}
```

The roster supplies N, cluster sizes, cluster count, blocks, covariates and population weights. Each replication draws a Gaussian cluster shock with variance `outcome_sd^2*icc`, an independent individual shock with variance `outcome_sd^2*(1-icc)`, and independent unit-by-arm Bernoulli receipt with the declared adherence probabilities. Its potential outcome adds `effect*arm_effects[arm]*receipt` to the baseline and shocks. Optional `covariate_coefficients` and `block_effects` map every named covariate or block to its baseline coefficient. `outcome_sd` defines the residual baseline scale; arm effects and receipt also determine treated-outcome variance. Positive ICC requires a declared cluster column.

MCAR retention is drawn before assignment with probability `1-attrition` and is fixed across potential outcomes. The simulation inquiry is the population-weighted finite-population assignment ITT among retained outcome units, with denominator equal to their weight total. The original roster and randomization declaration remain intact; official estimation retains the original row-to-probability correspondence after missing outcomes are removed. The result saves retained counts, weight totals, effective assignment-unit counts, actual receipt rates and each draw's true estimand. The unconditional expected contrast at effect scale e is `e*sum(contrast*arm_effects*adherence)`. LATE uses the IV owner.

The executable design combines official `declare_model`, `declare_inquiry`, `declare_assignment`, `declare_measurement` and `declare_estimator` steps and calls `diagnose_design` for every effect-grid value. Every simulation uses the same declaration and estimator as analysis. `test="wald"` uses the official p value; `test="randomization"` uses the declared RI test and stores each replication's RI seed. Balanced diagnosis selects the randomization test, retains power, bias and RMSE, and records `coverage_available=false` with null coverage because its point-estimation path produces no average-effect interval. `confidence_level` determines both the official interval level and rejection threshold. Common random draws across the grid preserve the same model and assignment realizations. All requested replications must return their estimates; a failed draw stops completion.

Saved diagnosis rows contain power, bias, RMSE, coverage, Monte Carlo standard errors and retained-population summaries. MDE is the smallest supplied grid value whose rejection frequency reaches `target_power`. Its row gives the effect scale, expected assignment ITT, mean simulated finite-population ITT, attained power and preceding grid value. `attained=false` means no supplied grid value reaches the target. This criterion and the complete effect grid remain attached to the result. The existing `research.py power` interface retains its pooled two-arm t-test, noncentral-t power and continuous MDE inversion.

### Saved results and official sources

`adopted.experimental_design` and `display.metadata.experimental_design` carry allocation, conditions, factorial cells, contrasts, estimator, inference, weight normalization, seeds and diagnosis definitions. Observation arrays and simulation draws remain in `diagnostics`. The native serialized result retains the randomization declaration, original data and fitted objects. The common `display`/`displays` and named statistics feed the existing gallery and Writing path; input, producer and R-companion hashes identify their calculation.

The executed interfaces use [randomizr `190d5f2`, `R/declare_ra.R`](https://github.com/DeclareDesign/randomizr/blob/190d5f24cb6b9782ab781952a80c72c17a4c27d4/R/declare_ra.R), its [exact assignment probabilities](https://github.com/DeclareDesign/randomizr/blob/190d5f24cb6b9782ab781952a80c72c17a4c27d4/R/obtain_permutation_probabilities.R), [estimatr `18209f7`, `horvitz_thompson`](https://github.com/DeclareDesign/estimatr/blob/18209f7bdcbb5fd5b25191e4f500d7a10ea9e86b/R/horvitz_thompson.R), [`lm_robust`](https://github.com/DeclareDesign/estimatr/blob/18209f7bdcbb5fd5b25191e4f500d7a10ea9e86b/R/lm_robust.R), [`difference_in_means`](https://github.com/DeclareDesign/estimatr/blob/18209f7bdcbb5fd5b25191e4f500d7a10ea9e86b/R/difference_in_means.R), and [DeclareDesign `faa5b93`, `diagnose_design`](https://github.com/DeclareDesign/DeclareDesign/blob/faa5b939a150205128f329dd4f8f7530e891b6d4/R/diagnose_design.R). The declaration-based HT path requires estimatr 2.1.0 or later. Native [balanced allocation and probabilities](https://github.com/DeclareDesign/randomizr/blob/190d5f24cb6b9782ab781952a80c72c17a4c27d4/R/balanced_ra.R) use the already pinned randomizr revision. The inspected estimatr declaration resolver routes balanced declarations through its complete-design variance branch; the balanced binding therefore uses native point estimation and actual-design Monte Carlo inference. `experimental_design` records the assignment function, probability function, full-vector draw unit and covariance availability. DeclareDesign receives the adopted alpha explicitly for its power diagnosand.

