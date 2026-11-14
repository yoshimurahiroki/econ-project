# Knowledge retrieval procedures

Select the procedure for the pending lookup; The economist's procedure owns complete reading and reuse.

## Domains and search

Use the [retrieval program](../scripts/knowledge.py): `domains`, `search --domain DOMAIN --query TEXT --limit 8`, then `read ID...`. Use known IDs directly. Omit `--domain` for cross-field questions or when a restricted search finds no applicable candidate; inspect the returned purpose, definition and economic object before declaring a gap. Repeat `--query` for independent questions sharing the same scope.

Search ranks IDs, classifications and normalized bilingual concepts against indexed purposes, inputs and outputs. Inspect `matched_concepts` and definition owners for ambiguous terms. The lead selects the economic meaning and applicable conditions from the bodies.

## Concepts and classifications

`concepts --query TEXT` returns bilingual labels, aliases, definitions and mappings. Queries also accept JEL codes/groups; inspect `matched_jel_codes` alongside substantive coverage. STW mappings distinguish `exactMatch`, `closeMatch`, `broadMatch`, `narrowMatch` and `relatedMatch`; keep distinct meanings under their local definition IDs.

Mappings attribute ZBW's [STW](https://www.zbw.eu/stw/version/latest/download/about.en.html), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), with recorded source versions. Local Japanese labels and judgments are authored here. The [STW–JEL crosswalk](https://www.zbw.eu/stw/version/latest/mapping/jel/about.en.html) is [CC0](https://creativecommons.org/publicdomain/zero/1.0/) and targets edition `20210225`; current codes/labels come from the [AEA tree](https://www.aeaweb.org/econlit/classificationTree.xml). Classification locates a field; preserve the local definition when external labels combine distinct objects.

## Read selected units

`read ID... --limit 16000` returns complete selected units and topologically ordered prerequisites in bounded pages. Follow `next_offset` with the same IDs/limit and `--offset VALUE --expected-sha256 HASH`. Offsets count Unicode characters; a changed stream requires a new read. Without `--limit`, the program returns the full structured interface. Task-bound pages use `--restore` to preserve cache state.

`relations ID... [--type TYPE]` shows typed links. `plan ID... --context KEY=VALUE` resolves understanding prerequisites, applicable implementation dependencies and assumption-definition bodies; supply only conditions established by the adopted problem. Inspect unresolved and inapplicable relations. Alternatives and related IDs enter the read only when needed by the operation.

For small closures use `plan ... --read`; for larger ones pass `required_ids` to bounded `read`. Cycles or unavailable required bodies return `read_blocked` without bodies: repair the graph or expand the snapshot before use. A selected export permits only its declared closure. Flat snapshots use `--base knowledge/references` before the subcommand. Direct readers use the collection's `domains.json`, selected domain index, `selection.json` when present, and `units/ID.md`; retain manifest/runtime identity. Native plugin and extracted runtime collections live at `knowledge/references`; source and deployed repositories retain the canonical Skill collection. Cloud readers without an executor use the installed entrance's pinned Git references, including applicable semantic relations and model contracts, and fetch each selected body and its true prerequisites at that same revision.

## Model contracts and execution

`method --method METHOD --design DESIGN --stage STAGE` retrieves defining knowledge at contract stage and adds execution or interpretation knowledge at compose/review. The design and causal selectors call it automatically. `--implementation` must match an implementation-bound contract; otherwise automatic selection uses common design knowledge. `--model` identifies a structural model: its matching contract is required, and a missing/mismatched contract returns `source_required` without generic bodies. `--contract` fixes a contract explicitly. A shared prerequisite does not select unrelated contracts.

`--context KEY=VALUE` supplies established applicability conditions. Additional `--knowledge-id ID`, or selector `knowledge_ids`, adds local/task-external knowledge with prerequisites without replacing curated requirements. An unknown method needs a saved applicable source before adoption.

`plan MC-ID` follows the contract's units, equations and applicable dependencies. Read complete defining and equation bodies; compare actors, timing, feasible choices, target and identifying observations before adopting the model. Conditional application links may identify an additional unit; include that ID when the actual calculation requires it.

Contract availability distinguishes `theory_reference`, `numerical_example`, `internal_runner`, `internal_function` and `external_official_api`. These describe interfaces, while actual execution establishes installation, convergence and results. `selection_binding` connects `model_contract_id` in `research_causal.py select` to the registered model/implementation. The selector validates its target, conditions, algorithm and implementation and preserves proposed specification changes for adoption. Unbound theory/callable contracts return `implementation_required`; they execute nothing.

An empty `implementation` list supplies a mathematical contract for econ-data to derive or calculate. Registered bindings use their declared engines/dependencies; source-only examples use their canonical source URL and hash. Retain inputs, specification and actual outputs through the existing research result. Select or compare methods under the economist's procedure; pass a determining source gap to econ-literature and resume its consumer afterward.

## External domain sources

Discover the source using the host's actual skill/knowledge catalog. Read the chosen resource and its required prerequisites through all returned pages. Use its exact locator and source version.

`acquire --task TASK --root PROJECT --source FILE` retains the body in existing task outputs. The source JSON supplies `provider`, `knowledge_id`, `version`, `title`, `domain`, nonempty `applicability`, `body`, `locator`, and `retrieval` with actual tool/arguments. A complete single-page `skills.read` return may be `retrieval.result`; for multiple pages join their original bodies and retain cursor arguments. Optional `prerequisites`, `model_contract_ids`, `inputs` and `outputs` connect the source to its use.

Identical acquisition reuses the immutable output. Bind its returned current `reference` and immutable `saved_reference`, including required prerequisites, to the adopted decision/argument. A source update changes its consumers through existing reference impact; it grants no scientific authority. Full external bodies stay in task outputs outside the plugin.

Use `search --task TASK --root PROJECT --query TEXT` for local/acquired metadata and `plan ID... --task TASK --root PROJECT --read` for their bodies. An unreadable prerequisite must be acquired first. `read ... --as-sources` returns exact bodies/versions in the argument source-catalog format; reuse existing matching sources.

## Versioned reuse and continuation

Task-bound retrieval activates `requested_local_state_helper_operation` and uses the existing [state owner](../../../harness/state.md); ordinary lookup needs no store. `read ID... --task TASK --root PROJECT` caches local bodies as `knowledge:ID` in a running task. Matching body/catalog/manifest/retrieval versions reuse them; changed versions return current bodies. `--restore` reads originals without writes and works after completion. `--as-sources` also preserves state.

At stage changes, reuse full matching text in context and refresh only changed dependencies. After context loss, recover applicable instructions and adopted choices through TEAM, then restore the needed bodies. Repair stale generations or prerequisite cycles before dependent use.

## Canonical content and distribution

The authored catalog and chapters are the content source. After changing their metadata/body, run `build` once, then distribute that saved generation through the existing exporter/synchronizer. Generated units project links to canonical source URLs. Runtime exports retain the manifest, selected indexes and full prerequisite bodies plus `runtime.json`; selected snapshots declare their closure in `selection.json`. The existing reader verifies those versions and boundaries.

Package the collection once outside Skill directories at runtime-root `knowledge/references`; econ-knowledge owns retrieval and other Skills retain specialist execution. Its files remain in the complete execution bundle.
