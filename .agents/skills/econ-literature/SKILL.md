---
name: econ-literature
description: Find literature, assess novelty, check citations against the cited text or institutional dates against the applicable rule, and update a requested research source index. Connect structural IO identification and estimation papers to their executable implementations.
---

# Economic literature

## Purpose and input

[Task boundaries and completion](../../runtime/CORE.md) and [operation selection](../../../ECON_INDEX.md) govern this specialist. Use [PROSE](../../runtime/PROSE.md) when explaining the result.

Input: Specified materials, existing source records and requested search or source-check scope.

Before source selection or comparison, apply [CORE task entry](../../runtime/CORE.md#task-entry). Read the applicable source-discovery, institutional or method reference and its required dependencies in full; retrieve knowledge IDs and their true prerequisites only when the source question needs them. A search result, summary, heading or knowledge lookup does not replace the original passage, its source version or this specialist's comparison.

## Procedure

When the pending operation needs a library definition, derivation, model condition or worked example, activate [econ-knowledge](../econ-knowledge/SKILL.md) and select the needed IDs and required prerequisites. Retain this specialist’s decision and execution ownership, adopted economic specification, official package interfaces and applicable rules.


### Find the work that answers the comparison

Use [Investigate source claims](../../runtime/DECIDE.md#investigate-source-claims) for literature, institutional, technical and other source questions. Return findings and exact passages to the result owner when the assignment is resolved. For the relation between analytical and source work, use [DECIDE](../../runtime/DECIDE.md).

Start with supplied materials and existing source records, then search the personal collection or literature index by the question's mechanism or parameter. Select the next paper for the unresolved premise or competing prediction it can resolve. Include evidence that could overturn the leading explanation; a null result, group contrast or timing pattern can distinguish mechanisms that the main average effect does not. Read the model, design and result passages establishing that comparison, with the relevant population and conditions. Use econ-writing:explain for a requested paper explanation.

Determine what evidence the unresolved proposition needs: a definition, a documented event, a mechanism, a quantitative contrast or a population frequency. Select sources and the form of the returned result accordingly. A detailed case can establish that a process occurred; estimating its prevalence requires a relevant sampling frame and denominator. Use an output outline to expose missing support before widening the search. As evidence arrives, revise the affected proposition and the next retrieval or analysis in the existing context, then return its consequence to the result owner.

For an economic method, follow the requested decision quantity through the source's equation, identified population or response margin, empirical implementation and reported result. Read the replication call when its transformation, weighting, sample or post-estimation defaults determine that mapping. Distinguish evidence identifying the historical effect from evidence supporting the new policy's response. Select the source comparison that resolves this difference before collecting additional applications of the same estimator; return the supported mapping and the affected design or calculation to its owner.

For novelty, identify the closest existing answer, the central question it leaves unresolved and how the proposed study resolves that question. Compare mechanism, estimand, measurement and identifying variation through the prediction, choice, welfare-relevant magnitude or economic knowledge they change. Apply the same criterion to a new dataset, population or setting. Return the supported contribution comparison. For a request covering every item in a collection, reconcile reviewed items with that collection and retain queries, versions and reviewed records in the existing index. Preserve an existing discovery, counterexample and unseen-evaluation split; retrieve only the assigned partition for the current purpose.

### Establish the supporting passages and versions

For executable public discovery, use the [source connector](scripts/research_sources.py). `literature` searches Crossref and retains DOI, author, title, year, references and the exact response. `work` resolves an exact DOI; `references` extracts its backward references with their complete original fields and origins. Repeated queries through `literature-multi` merge normalized DOI or exact title/year identities and retain every query, rank and response status. `indicators` searches the official World Bank indicator definitions; `series` acquires the selected country-year observations with their definition, original pages, hashes and missing values. `fetch` acquires an explicitly selected original and can use the existing document parser. Retain the query and returned source record with the research inputs. Follow the selected DOI or publication link into the original passage before using its mechanism or finding. Match a statistical series by definition, unit, geography, period and release before adopting it. Use the host's connected holdings, search and document tools for complementary sources under the same evidence rules.

For research discovery, compare candidate questions in the existing adopted specification: the closest paper's actual answer; the mechanism or parameter the candidate adds; the prediction separating it from that answer; and the observable variation and accessible data that implement the comparison. Trace reference lists and forward citations from the closest answer, and revise the candidate when a found paper already answers its determining question. Return the selected question and its executable source/data operation to econ-design; retain rejected candidates and the determining evidence in the existing task result. A replication carries the original question and its reproduced result as its contribution.

For structural estimation or IO, connect the requested parameter and counterfactual to the original model, identification and estimator passages, then to the matching author code or specialist engine. Read the parameter's normalization, observed variation or moments, information/timing, equilibrium concept and policy-invariance argument. Match a BLP demand/supply implementation to its share inversion and GMM moments; NFXP to the solved dynamic likelihood; CCP to its inversion and first-stage conditions; MPEC to the original equilibrium constraints; and dynamic-game simulation estimators to policies, transitions and feasible deviations. Recover the published and replication versions separately when their algorithms differ. Give econ-design the identification passage and econ-data the exact equation, function, version, sample and numerical convention needed to execute it. Store this correspondence in the existing source record or adopted specification.

For a proposed numerical acceleration, inspect the mathematical approximation, training/simulation design, parameter region, exact reference solver and reported comparison's full computing boundary. Locate public code and its executed examples. Connect reported speed and accuracy to that model, hardware, precision and quantity, then return the implementation choice it resolves. Record the inspected commit, license and implementation path in the existing development/source record before importing a reusable technique.

For a citation check, compare the claim with its supporting passage in the requested version and resolve that version's DOI, citation key or stable ID. Distinguish the author's assertion, observed or estimated result, identifying assumptions and the implication derived for this task. Resolve conflicting claims at the comparison that separates them under [DECIDE's source rules](../../runtime/DECIDE.md#investigate-source-claims). For institutional timing, distinguish announcement, effective and implementation dates and use the date corresponding to the event claimed.

For an interview design or supplied interview material, identify which actor had direct knowledge of the relevant choice, information and period. Ask for concrete episodes, available alternatives, constraints and the sequence of actions before testing the proposed explanation. Probe cases in which the predicted result did not occur and corroborate consequential factual claims with records or other relevant observations. Separate the participant's experience, recollection, interpretation and incentives; agreement with a leading question supplies no causal identification. Keep contacts and interview execution within the task's explicit authority.

Render citations in the artifact's requested format. Keep reading editions, claim locators and new-calculation inputs in the existing source record. Preserve the bibliography and research PDFs. Store derived notes separately from holdings metadata. Use native connectors for live private records.

### Complete a requested AI-method assessment

For a requested AI-method adoption, use [task resources](../../../docs/ai/resources.md) to locate the relevant primary source and implementation. Inspect their operation permissions and dependencies. Return the source findings to econ-review for a requested assessment or to the existing result owner for authorized adoption work under [EXECUTION](../../runtime/EXECUTION.md).

### Deliver the literature's economic relevance

Deliver the requested source answer or contribution comparison in original prose, citing the supporting source versions and passage locations. When a required passage cannot be read, identify it and the access needed for the next authorized action in task communication. Keep search progress and adoption status in operational records.

## Source and data discovery

Select `research_source_discovery` and read [source discovery](references/source-discovery.md) for bounded citation-graph traversal, multi-query retrieval, hash-verified PDF/HTML/text passages, lexical ranking, selected attributed propositions and model/identification/result comparisons linked to research decisions. Preserve each paper's stable identity and the original location and version behind each proposition. Bibliography updates retain adopted knowledge; a source or interpretation change identifies the affected uses for the existing design, calculation, writing or review owner. Matching original hashes reuse saved page text.

The same corpus accepts local CSL-JSON exports and existing PDF/text/Markdown holdings. Keep bibliography-only entries visible as missing-body records and retain their adoption, exclusion or pending judgment with its reason. Search the local corpus first and use the existing source connector for its determining gaps. Keep retrieved/extracted text distinct from explicitly inspected ranges and the researcher's expressly supplied reading declaration, all bound to the actual edition. Pass selected propositions through the same reader to design and evidence review; project papers and notes remain outside the generic plugin.

Select `research_data_discovery` for [official data acquisition, dataset-use passages and structured tables](../econ-data/references/research-data.md). Select `research_adaptive_experiments` for [proposals from collected source propositions](../econ-design/references/adaptive-research.md). Acquire the original passage and dataset documentation, express the economic proposition, and pass the recorded source, observation unit, measures, period and join keys to the design owner.

For a delegated investigation, return the supported comparison and its original source versions, passage locations, populations and conditions, with the unresolved source question and next authorized retrieval when needed. Pass the source-to-equation or implementation mapping to the responsible design or data owner without adopting its decision. After interruption, handoff or loss of context, restore the original request, authority, source coverage, adopted comparison, completed reads and mandatory rule bodies that are unread, changed or no longer available in the active context through [TEAM's resumption contract](../../runtime/TEAM.md#resumption); reuse same-version reads and valid results. Continue the authorized investigation toward the requested source coverage, preserving any missing passage and its actual access dependency.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `investigate`: Find and select source information that resolves a research question or citation task.
<!-- END GENERATED MODES -->
