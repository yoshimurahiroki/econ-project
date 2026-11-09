---
name: econ-knowledge
description: Retrieve local economics knowledge and host-provided domain sources with their required prerequisites. Retain external source bodies and versions in existing task outputs and connect them to research decisions and arguments.
---

# Economics knowledge

## Ownership and input

[CORE](../../runtime/CORE.md), [PROSE](../../runtime/PROSE.md) and the [operation registry](../../registry/operations.json) govern this reference. The specialist handling the user's design, data, literature, writing or review keeps responsibility for the result. The lead adopts economic choices through [TEAM](../../runtime/TEAM.md). Activate this reference when the pending operation requires a definition, derivation, method condition or calculation from the knowledge library.

Identify the question, economic object, requested operation and adopted assumptions before searching. Preserve settled estimands, populations, units, timing, equilibrium selection and inference. Use the retrieved equations and conditions to resolve that pending operation, then continue through its existing specialist and official package implementation.

## Select the needed procedure

Start with the small domain index or an established knowledge ID. Select the procedure below from the pending operation, then read its complete body and required dependencies. An index or plan locates the text used for economic judgment; read the selected units and their necessary prerequisites before applying them. Reuse complete same-version bodies already in context.

| Pending operation | Complete procedure | Registered condition |
| --- | --- | --- |
| Locate a field, concept or candidate ID | [Domains and search](references/retrieval.md#domains-and-search) | `knowledge_search` |
| Interpret JEL or STW mappings and distinct concept meanings | [Concepts and classifications](references/retrieval.md#concepts-and-classifications) | `knowledge_classification` |
| Read selected IDs, prerequisite closure or conditional application dependencies | [Read selected units](references/retrieval.md#read-selected-units) | Required for this Skill |
| Select a model contract and connect its equations to the existing implementation | [Model contracts and execution](references/retrieval.md#model-contracts-and-execution) | `knowledge_model_contract` |
| Discover, retain or consume host-provided domain sources | [External domain sources](references/retrieval.md#external-domain-sources) | `knowledge_external_source` |
| Reuse or restore task-bound knowledge bodies | [Versioned reuse and continuation](references/retrieval.md#versioned-reuse-and-continuation) | `knowledge_task_reuse` |
| Edit source knowledge or export its saved generation | [Canonical content and distribution](references/retrieval.md#canonical-content-and-distribution) | `knowledge_content_update` |

The [retrieval program](scripts/knowledge.py) resolves the same collection in a repository and its packaged runtime. Direct readers use `references/domains.json`, the selected domain index and `references/units/ID.md`; the domain index records each ID's required prerequisites. Task-bound operations use the existing state owner and activate `requested_local_state_helper_operation`. Read only the selected branch of these procedures and the full knowledge bodies it requires. Preserve the specialist's adopted scientific specification and completion authority.

## Return

Return the selected IDs, the prerequisite closure, exact body and index versions, the equations or conditions used, and their consequence for the pending operation. Include the method-selection reason, the determining source question and update condition when the operation uses those judgments. Bind resulting calculations and prose to the existing task or research artifact when that work uses persistent evidence. Complete the specialist's requested result under CORE.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `lookup`: Retrieve the economics definitions, derivations, model conditions or worked examples needed by the current specialist.
<!-- END GENERATED MODES -->
