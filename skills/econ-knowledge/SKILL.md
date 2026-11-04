---
name: econ-knowledge
description: Retrieve a specified economics theory, model, identification argument, numerical method or worked example by knowledge ID and its required prerequisites. Use as a conditional reference for the existing research specialist.
---

# Economics knowledge

## Ownership and input

[CORE](../../runtime/CORE.md), [PROSE](../../runtime/PROSE.md) and the [operation registry](../../registry/operations.json) govern this reference. The specialist handling the user's design, data, literature, writing or review keeps responsibility for the result. The lead adopts economic choices through [TEAM](../../runtime/TEAM.md). Activate this reference when the pending operation requires a definition, derivation, method condition or calculation from the knowledge library.

Identify the question, economic object, requested operation and adopted assumptions before searching. Preserve settled estimands, populations, units, timing, equilibrium selection and inference. Use the retrieved equations and conditions to resolve that pending operation, then continue through its existing specialist and official package implementation.

Read the full activated mandatory rules and complete [PROSE normative text](../../runtime/PROSE.md) before judging the retrieved material or composing its return. Apply selective retrieval to economics knowledge and its true prerequisites while retaining that complete normative scope. The [detailed dictionary](../../quality/prose_rules.json) supplies concrete lexical detections for the same integrated review. Reuse available same-version bodies and restore them after context loss through the governing task.

## Select and read knowledge

The [retrieval program](scripts/knowledge.py) provides `domains`, bounded `search`, and `read` commands. Select the relevant domain from `domains`, compare the candidate's use, inputs and outputs with the request, and read the selected IDs. `search --domain DOMAIN --query TEXT --limit 8` returns at most eight ranked candidates in that domain. Omitting `--domain` searches the available domain indexes under one shared limit. Use that cross-domain search when the question spans mechanisms or the relevant field is itself being selected; refine the question's economic objects through the returned domain and unit descriptions. A merger question can require demand, ownership, equilibrium, consumer welfare and business valuation. Search those objects together or through the corresponding focused queries, then select the complete chain the requested result uses. Exact IDs take priority, followed by matches in the indexed title, domain, topic, purpose, inputs and outputs through normalized words, bilingual aliases and Japanese character fragments. The lead makes the economic selection from the candidates' meanings and the adopted assumptions.

Search weights words by their specificity across the selected indexes, normalizes English plurals, and counts each matched concept once. Inspect `matched_concepts` and their definition owners to distinguish meanings of a shared term. `concepts --query TEXT` accepts a full question and returns the matching labels with each distinct concept. Compare the definition and economic object before selecting a meaning.

Run `read ID...` to retrieve those IDs and their topologically ordered required prerequisites. Related and alternative IDs support selection and enter the read only when the operation needs them. Verify each returned body's definition, assumptions and implementation conditions against the requested use. Additional technical dependencies discovered during the work trigger the corresponding additional ID read.

For a version 2 collection, use `concepts --query TEXT` to inspect bilingual names, aliases, broader and narrower concepts, definitions and JEL mappings. Use `relations ID...` to inspect typed incoming and outgoing relations; `--type TYPE` restricts the relation and repeated `--context KEY=VALUE` supplies an adopted applicability selector. Use `plan ID...` with the same optional context to identify understanding prerequisites, applicable implementation dependencies, unresolved conditions and model contracts. A selector reports whether the supplied value matches a registered condition; establish the condition from the actual model and evidence before relying on it. Use related and alternative relations to compare candidates under their stated target, identifying observations and conditions.

`plan` identifies required IDs; `read` retrieves the requested IDs and their understanding prerequisites. Read any additional applicable IDs returned by the plan. A selected snapshot permits bodies within its declared closure; obtain an expanded snapshot through the existing exporter when the needed body lies outside it. Use the graph and contract views to locate the complete bodies, interfaces and conditions that support the specialist's economic judgment.

Contract implementation descriptors identify the existing econ-data owner and, when registered, its resource ID. An `execution_binding` identifies a registered engine or pinned external module; an `executable_example_provenance` identifies source-only example code. A `canonical_source` path, source URL and SHA-256 address the exact source provenance. Source-only examples are retrieved through that source URL; registered execution bindings resolve through the econ-data resource closure. Current calculations retain their actual inputs, outputs and verification in the producing research record. Execute the adopted calculation through the registered econ-data resource and its documented dependencies; preserve the fitted specification, returned result and requested verification.

Use a method comparison on its stated economic problem, population and quantity. Check the competing methods' identifying observations, maintained restrictions, inference and computational requirements before selecting one. The body's investigation path identifies the unresolved object, specialist search terms, original material or official interface needed, the observation that changes the adopted method, and the resulting calculation. Pass that concrete source question to econ-literature under DECIDE; econ-design adopts the resulting model or estimand and econ-data executes its selected engine. Preserve the existing result owner and resume its requested outcome after the lookup.

The source and deployed script resolve their own reference directory. A flat snapshot uses `--base knowledge/references` before the subcommand. A snapshot selected with the existing exporter's `--knowledge-id ID` contains that selection and its prerequisite closure; use a matching expanded snapshot when the operation requires another ID.

Source editing uses the authored catalog and chapters with the generated indexes, bodies and manifest. A runtime export contains the canonical manifest, the applicable small domain indexes and complete selected ID bodies, plus `runtime.json` bound to that checked source generation. The existing producer verifies the full authored generation before creating this projection. Runtime reads verify the marker, index and unit hashes and the declared selection; source reads continue to verify the authored catalog and chapters. Preserve this explicit layout identity when transferring a collection.

For a host that reads files directly, use the knowledge Skill's own package and its linked retrieval program. In an installed plugin, the small listing is `references/bundle/skills/econ-knowledge/references/domains.json`. Read its selected domain index, then the chosen ID files under the same reference directory's `units/`. The domain record supplies each ID's prerequisites and exact location. Restore only that prerequisite closure. Keep the version manifest and runtime marker available to establish the checked source and file identities; their full text need not enter the model's working context. The root-shaped compatibility CLI accepts the same collection through its existing explicit `--base skills/econ-knowledge/references/bundle/skills/econ-knowledge/references` argument before the subcommand. The linked package program supplies the default runtime path.

## Versioned reuse and continuation

`read ID... --task TASK --root PROJECT` uses the [existing task state](../../harness/state.md) and its packaged state helper. It requires a running task and saves knowledge bodies as existing object outputs named `knowledge:ID`, with body, catalog, manifest and retrieval-specification versions. A matching saved body is checked and omitted from the repeated result; the return identifies its saved output. A changed version supplies the current body. Reuse a body already available at that version. When compression has removed its content from the working context, restore the saved object or read the ID without `--task` to obtain the full body.

Restore the original request, adopted choices and every applicable mandatory rule through the existing governing context before continuing. Preserve valid calculations and results. A missing file, stale generation, invalid prerequisite or cyclic dependency requires repair through its canonical owner before the affected use.

## Canonical content and distribution

The authored catalog and chapter files are the content source. The retrieval program's `build` command generates ID bodies, domain indexes and the version manifest in one path; `build --check` rejects stale derived files. Edit the chapter and its per-ID metadata, regenerate, and propagate the changed versions through the existing export and synchronization owners. Generated unit bodies project relative file links to canonical source URLs; authored chapters keep their local source links and execution retains its registered owner.

The knowledge collection is packaged once under this reference Skill. The other five skills refer to this owner and retain their execution instructions and package interfaces. Knowledge content supplies economics; the runtime supplies authority, state, verification and completion.

## Return

Return the selected IDs, the prerequisite closure, exact body and index versions, the equations or conditions used, and their consequence for the pending operation. Include the method-selection reason, the determining source question and update condition when the operation uses those judgments. Bind resulting calculations and prose to the existing task or research artifact when that work uses persistent evidence. Complete the specialist's requested result under CORE.

<!-- BEGIN GENERATED MODES -->
## Registered operations

Generated from registry/operations.json; the request determines the actual target and authority.

- `lookup`: Retrieve the economics definitions, derivations, model conditions or worked examples needed by the current specialist.
<!-- END GENERATED MODES -->
