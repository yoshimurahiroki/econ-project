---
name: econ-knowledge
description: Retrieve local economics knowledge and host-provided domain sources with their required prerequisites. Retain external source bodies and versions in existing task outputs and connect them to research decisions and arguments.
---

# Economics knowledge

The knowledge library supplies the definitions, equations, model conditions and worked examples that step 3 of the [economist's procedure](../../runtime/ECONOMIST.md) needs. Retrieve them before writing a model or a condition.

```sh
python3 skills/econ-knowledge/scripts/knowledge.py domains
python3 skills/econ-knowledge/scripts/knowledge.py search --query "需要独占 最低賃金" --limit 6
python3 skills/econ-knowledge/scripts/knowledge.py plan UNIT-ID --read
```

Record the unit IDs in the worksheet. Search, classification and model contracts are described in [retrieval](references/retrieval.md#domains-and-search).

<!-- BEGIN GENERATED MODES -->
## Registered operations

- `lookup`: Retrieve the economics definitions, derivations, model conditions or worked examples needed by the current specialist.
<!-- END GENERATED MODES -->
