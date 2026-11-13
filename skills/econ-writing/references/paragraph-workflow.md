# Paragraph and argument composition

## Construct the argument

Do not invent prose or arguments. For every request, including a short passage, one-word edit, translation, formatting or an existing draft, first search and read the relevant original sections and their surroundings, pages, slides and exhibits in sources suited to the task: papers and slides from the five leading journals from 2020 onward, major economics handbooks, review articles and guides, economics textbooks, and economics course materials (lecture notes, class slides and handouts). No output needs every source category. For Japanese, find and borrow the corresponding Japanese original; do not create a literal translation of English prose. When a matching passage is missing, search and read further rather than inventing or freely paraphrasing.

Apply [PROSE Common output](../../../runtime/PROSE.md#common-output) to every element.

Identify the reader's question, central answer and supporting premises/evidence from the request and sources. Keep the question, answer and admitted source identities/hashes fixed; problem comparisons and verification tasks cite that evidence. Establish dependencies through the existing owner and use source-bound claims and actual evidence. Preserve the relations needed to make results usable, including measurement, identification, optimality or equilibrium, and aggregation; borrow their ordering and expression from applicable read sources.

## Compose the paragraph

Borrow the paragraph's proposition, sequence, connections and expression from applicable read source passages, with only the necessary adjustments above. Bind each target proposition to its evidence and neighboring claims; preserve actors, economic objects, populations, units, denominators, periods, scenarios and result status. Connect a result's estimand, proposition or counterfactual, variation, equation, conditions, direction and magnitude to the adopted comparison and next claim as supported by the evidence. Establish mechanisms through intermediate evidence or derivation, and economic magnitude through its baseline, scale or allocation consequence.

Use the selected source/result bindings for this inference. Joint diagnostics require the tested vector, covariance-based statistic and reference distribution; group comparisons their direct contrast and inference; welfare its allocation, valuation and population weights. Retrieve those objects through [empirical guidance](paper-workflow.md#identification-and-empirical-method) and [model guidance](paper-workflow.md#theory-model-and-proof). Carry their defining relation into abstracts and conclusions using corresponding read source passages.

Apply [PROSE's language rules](../../../runtime/PROSE.md#revise-for-the-requested-language) to Japanese sentence connections and compression by borrowing from corresponding Japanese originals. Record the source and adjustment for each choice in the existing work record; persist paragraph specifications for requested versioned composition. A delegated paragraph receives its exact inference, neighboring consumer, scope, sources and fixed definitions under TEAM, including the original passages and correspondence needed to imitate them.

## Integrate the argument

Borrow the section's arrangement and transitions from read source passages and adjust only as necessary for the target. Define before use, preserve citations and repair missing premises from their source or completed analysis. Reconcile actors, population, period, estimand, assumptions and result status with the parent. Resolve differences through the analysis owner, retaining unaffected results. Integrate actual evidence; a completed child paragraph establishes only its supported claim. Keep operation returns in their operational destination and apply PROSE and the source correspondences to the integrated wording.

CORE's single review covers answer, evidence, order, paragraph connections and expression. Reconcile title, abstract, introduction, exhibits and conclusion with the body, tracing compressed claims to their establishing paragraphs. Compare every output element with its read original and the recorded adjustments. Repair demonstrated defects by returning to sources and reread affected connections. This reasoning creates no extra agents, passes, records or gates.

## State, changes and resumption

Use existing paragraph/argument state and materials or work records for source correspondence and dependencies. Preserve the request, authority, purpose, reader, admitted sources, definitions and completion conditions; attribute changes to actual findings, retain unaffected nodes and invalidate affected reviews. TEAM restores original applicable bodies and settled decisions before resumed integration. Reload source-bound quantities, conditions and original passages omitted by a compressed handoff; use the existing record rather than a parallel ledger.

## Command entry points

Use `harness/paragraph.py` and `harness/argument.py` for requested versioned composition and argument operations. Actual final artifacts and authorized destination returns establish delivery.

The default `single-agent-sequential` path writes source-bound paragraphs and completes one manuscript integration with the substantive review. Its integrator returns the finished paragraphs, joined text, input paragraph hashes and remaining concrete findings. Authorized wording repairs can be returned in that same operation. Source, specification, rule and dependency changes reopen the affected text through the existing state. Local review, argument review and section integration remain explicitly selectable operations. Select `independent-subagent` for the existing independent review path; its observed worker identities and certification requirements remain attached to that selection.

To begin from saved results, add `research_results` to the existing writing brief:

```json
"research_results": {
  "root": "/absolute/project/root",
  "registry_path": "analysis/saved-results.json",
  "result_ids": ["specialist-did-r01"],
  "evidence_paths": {
    "specialist-did-r01": [
      ["diagnostics", "pretreatment_test"],
      ["inference", "p_values", "event_m1"]
    ]
  }
}
```

The existing `design` command resolves this selection through `research_artifacts.composition_context(root, registry_path, result_ids=..., item_ids=..., gallery_path=..., evidence_paths=...)`. Add `gallery_path` and `item_ids` when the paragraph uses saved displays. Its architecture and specification callbacks receive named quantities, units, adopted definitions, producing references, selected evidence and display rows. The returned `sources` contain `result:<ID>` and selected `display:<ID>` entries with exact text hashes, structured content and original quantity keys or row indices.

`evidence_paths` maps a selected result ID to a nonempty list of distinct key paths relative to that record's `source_result`; each path is a nonempty list of nonempty strings. Each selected value is returned in `research_result.evidence` with its `keys`, original structured `value` and `source_reference`. That reference contains the registry `path`, `keys:["records", RESULT_ID, "source_result", ...]` and the selected value's `content_version`. The example passes the saved joint test and the event-minus-one p value with their original shapes. The writer recovers their tested contrasts and interval family from the adopted design and selected source definitions, then borrows a corresponding read source passage to explain their relation in the manuscript with necessary adjustments. Select additional saved paths when that explanation requires their contents.

Pass the design output's `blueprint`, `specifications`, `sources` and `design_records` into the existing `ParagraphRun.create` input. The writer borrows the evidence-to-claim explanation from corresponding read source passages and adjusts it only as necessary; completed paragraphs retain these same sources for later section design and reuse. An initial sources file can contain `{}` when the brief supplies the selected results.

To design a requested section from completed body paragraphs, use the existing `design` entry with the saved run and explicit paragraph IDs:

```bash
python harness/paragraph.py design \
  --brief writing-brief.json --sources sources.json --rules writing-rules.json \
  --host host-adapter.py --author-id author --execution-kind single-agent-sequential \
  --reuse-state writing/paragraph-state.json \
  --reuse-paragraph results-main --reuse-paragraph mechanism \
  --output section-design.json
```

Use the actual paths and paragraph IDs from the project. The current brief retains the request, authority, reader, language, research type and section function. Both architecture and specification callbacks receive that brief and `completed_body`: the selected paragraphs' original text and specifications, supporting argument nodes, prerequisite relations, adopted exhibits, exact source spans, saved-result references and current version bindings. The canonical central question, answer and contribution stay fixed in the returned design. Use the paper guidance's research-type and section operations and corresponding read originals to express them in the requested language; use Japanese originals for Japanese.

Selection expands through the argument's supporting claims and incoming prerequisites and through each paragraph's `depends_on`. Reuse binds every selected paragraph and prerequisite to its current text, specification, sources, rules and dependencies. The ordinary path reads completed text through those bindings. The explicitly selected independent path also retains its completed independent review. A changed binding identifies the paragraph whose producing work must finish. Unrelated paragraphs stay outside `completed_body`. The design operation reads the saved run without a resume event and writes its new design to the specified output.

For an existing Python caller, use `ParagraphRun.load(path, resume=False).composition_context(paragraph_ids)` to read the same selected context. Pass the loaded run and `paragraph_ids` to `generate_blueprint` and `generate_specifications`; pass the current `brief` to the specification call. These operations consume the existing state and actual saved evidence.
