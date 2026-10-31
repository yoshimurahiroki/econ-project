---
name: econ-literature
description: Find literature, assess novelty, check citations against the cited text or institutional dates against the applicable rule, and update a requested research source index.
---

# Economic literature

## Purpose and input

[Task boundaries and completion](../../runtime/CORE.md) and [operation ownership](../../registry/operations.json) govern this specialist. Use [PROSE](../../runtime/PROSE.md) when explaining the result.

Input: Specified materials, existing source records and requested search or source-check scope.

## Procedure

### Find the work that answers the comparison

Use [Investigate source claims](../../runtime/DECIDE.md#investigate-source-claims) for literature, institutional, technical and other source questions. Return findings and exact passages to the result owner when the assignment is resolved. For the relation between analytical and source work, use [DECIDE](../../runtime/DECIDE.md).

Start with supplied materials and existing source records, then search the personal collection or literature index by the question's mechanism or parameter. Select the next paper for the unresolved premise or competing prediction it can resolve. Include evidence that could overturn the leading explanation; a null result, group contrast or timing pattern can distinguish mechanisms that the main average effect does not. Read the model, design and result passages establishing that comparison, with the relevant population and conditions. Use econ-writing:explain for a requested paper explanation.

For novelty, identify the closest existing answer, the central question it leaves unresolved and how the proposed study resolves that question. Compare mechanism, estimand, measurement and identifying variation through the prediction, choice, welfare-relevant magnitude or economic knowledge they change. Apply the same criterion to a new dataset, population or setting. Return the supported contribution comparison. For a request covering every item in a collection, reconcile reviewed items with that collection and retain queries, versions and reviewed records in the existing index. Preserve an existing discovery, counterexample and unseen-evaluation split; retrieve only the assigned partition for the current purpose.

### Establish the supporting passages and versions

For a citation check, compare the claim with its supporting passage in the requested version and resolve that version's DOI, citation key or stable ID. Distinguish the author's assertion, observed or estimated result, identifying assumptions and the implication derived for this task. Resolve conflicting claims at the comparison that separates them under [DECIDE's source rules](../../runtime/DECIDE.md#investigate-source-claims). For institutional timing, distinguish announcement, effective and implementation dates and use the date corresponding to the event claimed.

Render citations in the artifact's requested format. Keep reading editions, claim locators and new-calculation inputs in the existing source record. Preserve the bibliography and research PDFs. Store derived notes separately from holdings metadata. Use native connectors for live private records.

### Complete a requested AI-method assessment

For a requested AI-method adoption, use [task resources](../../docs/ai/resources.md) to locate the relevant primary source and implementation. Inspect their operation permissions and dependencies. Return the source findings to econ-review for a requested assessment or to the existing result owner for authorized adoption work under [EXECUTION](../../runtime/EXECUTION.md).

### Deliver the literature's economic relevance

Deliver the requested source answer or contribution comparison in original prose, citing the supporting source versions and passage locations. When a required passage cannot be read, identify it and the access needed for the next authorized action in task communication. Keep search progress and adoption status in operational records.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `investigate`: Find and select source information that resolves a research question or citation task.
<!-- END GENERATED MODES -->
