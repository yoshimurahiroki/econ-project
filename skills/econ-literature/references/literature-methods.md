# Literature procedure

Literature work serves a step of the [economist's procedure](../../../runtime/ECONOMIST.md): the closest existing answer for the question (step 2), the models and prior estimates for the mechanism (step 3), the designs and calls for the method (step 4), or a citation and an institutional fact. Work through the steps in order and fill each block in the worksheet; a claim enters the worksheet only with the passage that supports it.

Three rules hold throughout:

1. **Passages, not snippets.** A finding counts once its passage, table or equation has been read in the actual edition. A search result, abstract or unread citation is a lead.
2. **Claim type decides the evidence.** A definition needs the defining text; an event needs a dated record; a causal effect needs the identifying comparison; a frequency needs the sampling frame and denominator.
3. **Independent evidence.** Copies, syndication, shared datasets and circular citations count once.

## L1. Source question

Fill:

```
Step served:          question / mechanism / method / citation / institution / data
Claim to establish:   <one sentence>
Claim type:           definition / event / causal effect / frequency / proposition / implementation
What would settle it: the passage, table, equation, code or record
```

## L2. Search

Search in this order and record each query and its result count:

1. The user's holdings and connected libraries (local PDFs, CSL-JSON, Google Drive).
2. Journals in the order of [search priority](search-priority.md), within the execution-year window it sets.
3. Crossref through the source connector:

```sh
python3 skills/econ-literature/scripts/research_sources.py literature --query "minimum wage monopsony" --limit 20 --output work/sources
python3 skills/econ-literature/scripts/research_sources.py references --doi 10.xxxx/xxxxx --output work/sources
python3 skills/econ-literature/scripts/research_sources.py literature-multi --query "..." --query "..." --output work/sources
```

4. Backward references and forward citations of the closest paper, and the authors' related work.

```
Queries and results:   <query: n results>
Candidates:            <author year, venue, why it may settle the claim>
```

Stop searching when the claim is settled by read passages or when further leads repeat the same evidence; an empty search shows only that the query found nothing.

## L3. Read

Read each selected source through the [paper-reading sheet](paper-reading.md) and the method checklist: [empirical](read-empirical.md), [theory](read-theory.md) or [structural](read-structural.md). Fill one block per source:

```
Source:        author (year), title, venue, edition / version, DOI
Passage:       section, page, equation / table / figure
Finding:       quantity with population, period, units, estimator and interval; or proposition with its domain
Relevance:     which claim of L1 it settles, and how
```

## L4. Judge

Fill:

```
Claim settled?          yes / partly / no
Supporting sources:     <list>
Conflicting sources:    <list>, resolved at <the passage, measurement or model difference that separates them>
Remaining gap:          <the unread passage or missing evidence and how to reach it>
```

Rules:

- Resolve conflicts at the determining passage, measurement or model implication; a majority of papers settles nothing.
- An organization's statement establishes what it said; its effects and quality need the underlying observations.
- Institutional dates: announcement, effective and implementation dates are different events; use the date of the event claimed.

## L5. Purpose-specific rules

**Novelty.** Write the closest existing answer, the question it leaves open and how the proposed study answers it: a new mechanism, estimand, measurement, variation, population or decision margin, each judged by the prediction or magnitude it changes. When a found paper already answers the question, narrow or replace the question in step D2 of the [design procedure](../../econ-design/references/workflow.md).

**Prior estimates for a model.** Record the parameter, its estimate and interval, population, period and identifying variation; these give the parameter ranges for simulation.

**Methods and replication.** Follow the decision quantity through the paper's equation, identified population, implementation and reported result; read the replication code when its sample, weights or defaults determine the number. Evidence on a historical effect and evidence on the response to a new policy are recorded separately.

**Structural methods.** Read the parameter's normalization, the variation or moments that identify it, timing and information, the equilibrium concept and the argument for policy invariance; match the estimator to its implementation: BLP to share inversion and GMM moments, NFXP to the solved likelihood, CCP to its inversion and first stage, MPEC to the equilibrium constraints. Record function, version and inputs for econ-data.

**Numerical acceleration.** Read the approximation, training design, parameter region, the exact reference solver and the full computing boundary of the reported comparison; record the code commit and license.

**Citations.** Compare the claim with the supporting passage in the cited version and record the version identifier.

**Interviews.** Ask the actor with direct knowledge for concrete episodes, alternatives, constraints and sequences before testing an explanation; probe cases where the prediction failed; corroborate factual claims with records.

**Data discovery.** Match a statistical series by definition, unit, geography, period and release (`research_sources.py indicators`, `series`) and pass source, observation unit, measures, period and keys to the [data procedure](../../econ-data/references/workflow.md). Corpus traversal and verified passages use the [source discovery](source-discovery.md) tools.

## L6. Hand-off

Copy the settled claims with their passages into the worksheet section they serve (2, 3 or 4) and name the remaining gap. Originals, extracted text and reading notes stay in the user's private records.
