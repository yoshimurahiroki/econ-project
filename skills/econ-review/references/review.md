# Review procedure

Review asks one question: does the artifact's answer follow from its question, model, comparison and numbers? Work through the steps in order and fill each block in the worksheet. Every finding names the exact place, the evidence that shows the defect, its consequence for the answer, and the repair.

## R1. Target

```
Artifact and version:     <file, section, slide, commit>
Central claim:            <the answer the artifact gives>
Decision it informs:      <who acts on it>
Scope:                    whole artifact / named passage / code path / referee comments
Mode:                     findings only / findings and repair
```

## R2. Rebuild the economist's chain

Fill the seven-step chain of the [economist's procedure](../../../runtime/ECONOMIST.md) from the artifact itself, before judging it:

```
Question (actors, choices, change, outcome):
Model and predictions (with the competing prediction):
Comparison / estimand / identifying assumption:
Method and inference:
Results (numbers with population, units, table):
Interpretation and decision:
```

A link the artifact does not supply is already a finding.

## R3. Checks by kind of claim

Run every check that applies and record its result as pass or as a finding.

**Question and model**
- The question names actors, choices and a change; it beats its upstream alternative.
- The model's assumptions fit the case; at least two mechanisms with different predictions are compared.

**Empirical claims**
- Reconstruct the population contrast, weights and identifying restriction from the text and code.
- Coefficients and subgroup contrasts match their covariance and reference distribution; subgroup differences are estimated directly.
- Clustering at the assignment level; few clusters handled by the wild cluster bootstrap; staggered adoption estimated with a heterogeneity-robust estimator (the decision rules of the [empirical procedure](../../econ-data/references/empirical.md)).
- Each diagnostic is read against its own null.

**Structural and numerical claims**
- Parameter roles, normalizations, timing, transitions and moments match the [adopted model](../../econ-design/references/designs.md#structural-estimation-and-counterfactuals).
- Residuals of the original Bellman, pricing, feasibility or deviation conditions at the returned solution are within tolerance.
- Counterfactuals carry the change through all affected best responses; prices, shares, profits and consumer values come from the same scenario.

**Theory**
- Domain and quantifiers are complete; the determining proof step holds; a proposed counterexample satisfies every hypothesis.

**Numbers in text and exhibits**
- Trace each decisive number to its saved result, sample, unit and definition; compare with the display rounding.
- `python3 harness/research_evidence.py review CONTRACT --root PROJECT --output PACKET` returns the cited source passages for literature-backed claims; read them and judge the claim against them.

**Code and pipelines**
- Follow the definitions from producer to every consumer; check keys, joins, sample, weights and formula ([implementation rules](../../econ-data/references/implementation.md)).

**Writing, slides and figures**
- Apply [WRITING](../../../runtime/WRITING.md); for slides and figures, check scales, axes, labels and speaking time against the [rendering procedure](../../econ-writing/references/artifact-writing.md), before reading the author's explanation of the layout.

## R4. Findings

One block per finding, ranked by consequence for the central claim:

```
Finding <n>:     <place>
Evidence:        <passage, number, residual or counterexample>
Consequence:     changes the answer / weakens the comparison / presentation only
Cause:           source / transformation / inference / presentation / execution
Repair:          <exact change, and where it is made>
```

Rules:

- A defect is repaired where it is produced: a source at the cited material, a transformation at its operation, an inference at the argument, a calculation at its producer (then every exhibit and sentence that uses it is rebuilt).
- A contested finding is settled against the cited passage or the producing calculation; a correct claim stays.
- Referee comments: locate the substantive question of each comment in the manuscript, keep a correct result with its derivation, repair a demonstrated defect, and answer with the exact revised locations ([claim coverage and re-review](../../econ-writing/references/result-artifacts.md#claims-coverage-and-requested-re-review)).

## R5. Versions and decisions

When comparing versions or proposed changes, hold inputs, authority and criteria fixed; separate changes in sample, measurement or target from changes in method; compare subgroup differences directly. Fixed evidence keeps the judgment fixed whatever the insistence; new determining evidence changes it.

## R6. Delivery

Findings only: report the ranked findings with their repairs. Findings and repair: revise the producer and the affected abstract, introduction, results and conclusion, render the target, read it, and report the revised locations. Independent or blinded assessment follows the [oversight notes](oversight.md).
