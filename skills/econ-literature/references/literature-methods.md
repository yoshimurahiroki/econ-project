# Literature methods

Select the section that resolves the requested comparison. Read its full body and required dependencies; retain the source version and exact passage in the existing record.

## Economic methods and replication

For an economic method, follow the requested decision quantity through the source's equation, identified population or response margin, empirical implementation and reported result. Read the replication call when its transformation, weighting, sample or post-estimation defaults determine that mapping. Distinguish evidence identifying the historical effect from evidence supporting the new policy's response. Select the source comparison that resolves this difference before collecting additional applications of the same estimator; return the supported mapping and the affected design or calculation to its owner.

## Novelty and coverage

For novelty, identify the closest existing answer, the central question it leaves unresolved and how the proposed study resolves that question. Compare mechanism, estimand, measurement and identifying variation through the prediction, choice, welfare-relevant magnitude or economic knowledge they change. Apply the same criterion to a new dataset, population or setting. Return the supported contribution comparison. For a request covering every item in a collection, reconcile reviewed items with that collection and retain queries, versions and reviewed records in the existing index. Preserve an existing discovery, counterexample and unseen-evaluation split; retrieve only the assigned partition for the current purpose.

## Public source acquisition

For executable public discovery, use the [source connector](../scripts/research_sources.py). `literature` searches Crossref and retains DOI, author, title, year, references and the exact response. `work` resolves an exact DOI; `references` extracts its backward references with their complete original fields and origins. Repeated queries through `literature-multi` merge normalized DOI or exact title/year identities and retain every query, rank and response status. `indicators` searches the official World Bank indicator definitions; `series` acquires the selected country-year observations with their definition, original pages, hashes and missing values. `fetch` acquires an explicitly selected original and can use the existing document parser. Retain the query and returned source record with the research inputs. Follow the selected DOI or publication link into the original passage before using its mechanism or finding. Match a statistical series by definition, unit, geography, period and release before adopting it. Use the host's connected holdings, search and document tools for complementary sources under the same evidence rules.

## Research discovery

For research discovery, compare candidate questions in the existing adopted specification: the closest paper's actual answer; the mechanism or parameter the candidate adds; the prediction separating it from that answer; and the observable variation and accessible data that implement the comparison. Trace reference lists and forward citations from the closest answer, and revise the candidate when a found paper already answers its determining question. Return the selected question and its executable source/data operation to econ-design; retain rejected candidates and the determining evidence in the existing task result. A replication carries the original question and its reproduced result as its contribution.

## Structural methods

For structural estimation or IO, connect the requested parameter and counterfactual to the original model, identification and estimator passages, then to the matching author code or specialist engine. Read the parameter's normalization, observed variation or moments, information/timing, equilibrium concept and policy-invariance argument. Match a BLP demand/supply implementation to its share inversion and GMM moments; NFXP to the solved dynamic likelihood; CCP to its inversion and first-stage conditions; MPEC to the original equilibrium constraints; and dynamic-game simulation estimators to policies, transitions and feasible deviations. Recover the published and replication versions separately when their algorithms differ. Give econ-design the identification passage and econ-data the exact equation, function, version, sample and numerical convention needed to execute it. Store this correspondence in the existing source record or adopted specification.

## Numerical implementation

For a proposed numerical acceleration, inspect the mathematical approximation, training/simulation design, parameter region, exact reference solver and reported comparison's full computing boundary. Locate public code and its executed examples. Connect reported speed and accuracy to that model, hardware, precision and quantity, then return the implementation choice it resolves. Record the inspected commit, license and implementation path in the existing development/source record before importing a reusable technique.

## Citation and institutional checks

For a citation check, compare the claim with its supporting passage in the requested version and resolve that version's DOI, citation key or stable ID. Record the author's assertion, observed or estimated result, identifying assumptions and the implication derived for this task in the internal evidence. Resolve conflicting claims at the comparison that separates them under [the economist's procedure's source rules](../../../runtime/ECONOMIST.md). For institutional timing, distinguish announcement, effective and implementation dates and use the date corresponding to the event claimed.

## Interview evidence

For an interview design or supplied interview material, identify which actor had direct knowledge of the relevant choice, information and period. Ask for concrete episodes, available alternatives, constraints and the sequence of actions before testing the proposed explanation. Probe cases in which the predicted result did not occur and corroborate consequential factual claims with records or other relevant observations. Separate the participant's experience, recollection, interpretation and incentives; agreement with a leading question supplies no causal identification. Keep contacts and interview execution within the task's explicit authority.

## AI-method assessment

For a requested AI-method adoption, use [task resources](../../../docs/ai/resources.md) to locate the relevant primary source and implementation. Inspect their operation permissions and dependencies. Return the source findings to econ-review for a requested assessment or to the existing result owner for authorized adoption work under [EXECUTION](../../../runtime/ECONOMIST.md#5-execution).

## Procedure

### Find the work that answers the comparison

Apply [the economist's procedure's source procedure](../../../runtime/ECONOMIST.md). Select papers by the unresolved mechanism, parameter or competing prediction they can establish. Treat a definition, a documented event, a causal contrast and a population frequency as four claim types; a case establishes occurrence, and prevalence rests on its sampling frame and denominator. Use econ-writing:explain for a paper explanation.

### Establish the supporting passages and versions

Read the actual edition's determining model, design, result and contrary passages. For an assigned paper, activate `paper_reading` and its empirical, theory or structural [reading procedure](paper-reading.md). Preserve bibliography and PDFs, keep derived notes separate and render citations in the requested format.

### Deliver the literature's economic relevance

Return the source answer or contribution comparison with original passage locations and versions. Identify any determining unread passage and the next accessible route in task communication.

## Source and data discovery

Activate `research_source_discovery` for the [existing corpus](source-discovery.md): citation traversal, multi-query retrieval, verified original passages and selected attributed propositions. Search local CSL-JSON/PDF/text holdings first. Keep bibliography-only entries visibly body-missing, extracted text distinct from inspected ranges, and each supplied reading declaration bound to its edition. Match hashes to reuse page text; keep project holdings outside the plugin.

Use `research_data_discovery` for [dataset documentation and tables](../../econ-data/references/research-data.md), and `research_adaptive_experiments` for [source-grounded proposals](../../econ-design/references/adaptive-research.md). Pass source identity, observation unit, measures, period and join keys to the design/data owner. A changed source or interpretation updates affected uses through their existing owners.

