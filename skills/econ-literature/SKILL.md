---
name: econ-literature
description: Find literature, assess novelty, check citations against the cited text or institutional dates against the applicable rule, and update a requested research source index. Connect structural IO identification and estimation papers to their executable implementations.
---

# Economic literature

## Purpose and input

[Task boundaries and completion](../../runtime/CORE.md) and [operation selection](../../docs/ai/compiled_ai_skills.md) govern this specialist. Use [PROSE](../../runtime/PROSE.md) when explaining the result.

Input: Specified materials, existing source records and requested search or source-check scope.

## Procedure

### Find the work that answers the comparison

Use [Investigate source claims](../../runtime/DECIDE.md#investigate-source-claims) for literature, institutional, technical and other source questions. Return findings and exact passages to the result owner when the assignment is resolved. For the relation between analytical and source work, use [DECIDE](../../runtime/DECIDE.md).

Start with supplied materials and existing source records, then search the personal collection or literature index by the question's mechanism or parameter. Select the next paper for the unresolved premise or competing prediction it can resolve. Include evidence that could overturn the leading explanation; a null result, group contrast or timing pattern can distinguish mechanisms that the main average effect does not. Read the model, design and result passages establishing that comparison, with the relevant population and conditions. Use econ-writing:explain for a requested paper explanation.

Determine what evidence the unresolved proposition needs: a definition, a documented event, a mechanism, a quantitative contrast or a population frequency. Select sources and the form of the returned result accordingly. A detailed case can establish that a process occurred; estimating its prevalence requires a relevant sampling frame and denominator. Use an output outline to expose missing support before widening the search. As evidence arrives, revise the affected proposition and the next retrieval or analysis in the existing context, then return its consequence to the result owner.

### Establish the supporting passages and versions

Use the actual edition and exact body passages for each claim. Read only the source records, pages, equations and tables that establish the selected comparison, then follow their determining dependencies. For a paper, activate `paper_reading` and use [the paper-reading procedure](references/paper-reading.md).

Render citations in the artifact's requested format. Keep reading editions, claim locators and new-calculation inputs in the existing source record. Preserve the bibliography and research PDFs. Store derived notes separately from holdings metadata. Use native connectors for live private records.

### Deliver the literature's economic relevance

Deliver the requested source answer or contribution comparison in original prose, citing the supporting source versions and passage locations. When a required passage cannot be read, identify it and the access needed for the next authorized action in task communication. Keep search progress and adoption status in operational records.

## Select the source operation

Read the complete selected section and activate its condition. The same literature operation retains ownership throughout.

| Requested operation | Condition and reference |
| --- | --- |
| Find or rank papers; compare prior research | `research_literature_search`: [search priority](references/search-priority.md), then [public acquisition](references/literature-methods.md#public-source-acquisition) |
| Establish novelty or a candidate research question | `literature_novelty`: [novelty and coverage](references/literature-methods.md#novelty-and-coverage) and [research discovery](references/literature-methods.md#research-discovery) |
| Select a method or read a replication | `literature_method`: [methods and replication](references/literature-methods.md#economic-methods-and-replication); add `literature_structural` for [structural methods](references/literature-methods.md#structural-methods) |
| Compare numerical implementations | `literature_numerical`: [numerical implementation](references/literature-methods.md#numerical-implementation) |
| Check a citation or institutional date | `literature_citation`: [citation and institutional checks](references/literature-methods.md#citation-and-institutional-checks) |
| Design or interpret interviews | `literature_interview`: [interview evidence](references/literature-methods.md#interview-evidence) |
| Assess an AI research method | `literature_ai_method`: [AI-method assessment](references/literature-methods.md#ai-method-assessment) |

The registry maps these conditions to their owning sections. Retrieve a field's journal ordering through the existing source command; the single ranking data file remains machine input.

## Source and data discovery

Select `research_source_discovery` and read [source discovery](references/source-discovery.md) for bounded citation-graph traversal, multi-query retrieval, hash-verified PDF/HTML/text passages, lexical ranking, selected attributed propositions and model/identification/result comparisons linked to research decisions. Preserve each paper's stable identity and the original location and version behind each proposition. Bibliography updates retain adopted knowledge; a source or interpretation change identifies the affected uses for the existing design, calculation, writing or review owner. Matching original hashes reuse saved page text.

The same corpus accepts local CSL-JSON exports and existing PDF/text/Markdown holdings. Keep bibliography-only entries visible as missing-body records and retain their adoption, exclusion or pending judgment with its reason. Search the local corpus first and use the existing source connector for its determining gaps. Keep retrieved/extracted text distinct from explicitly inspected ranges and the researcher's expressly supplied reading declaration, all bound to the actual edition. Pass selected propositions through the same reader to design and evidence review; project papers and notes remain outside the generic plugin.

Select `research_data_discovery` for [official data acquisition, dataset-use passages and structured tables](../econ-data/references/research-data.md). Select `research_adaptive_experiments` for [proposals from collected source propositions](../econ-design/references/adaptive-research.md). Acquire the original passage and dataset documentation, express the economic proposition, and pass the recorded source, observation unit, measures, period and join keys to the design owner.

For a delegated investigation, return the supported comparison, original source versions, passage locations, populations and conditions, and the next required retrieval. Pass the source-to-equation or implementation mapping to its design or data owner. Follow [TEAM](../../runtime/TEAM.md) for return and resumption.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `investigate`: Find and select source information that resolves a research question or citation task.
<!-- END GENERATED MODES -->
