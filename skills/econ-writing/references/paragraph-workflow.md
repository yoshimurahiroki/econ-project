# Paragraph procedure

For one paragraph, a section or a long argument whose paragraphs depend on each other. The paper's content comes from the worksheet and the [paper procedure](paper-workflow.md); this file governs how each paragraph is built and connected. Text follows [WRITING](../../../runtime/WRITING.md).

## G1. Paragraph sheet

Fill one line per paragraph before writing it:

```
Para <n>:   reader's question → proposition (one) → evidence (saved result, derivation or source passage)
            → link to the next paragraph
```

Rules:

- **One proposition per paragraph.** A paragraph that needs two propositions becomes two paragraphs.
- **Evidence with the claim.** An estimate travels with its estimand, population, units, interval and comparison; a mechanism with the intermediate evidence or derivation; a magnitude with its baseline or allocation consequence; a group difference with its direct contrast; a joint diagnostic with its tested vector and reference distribution; welfare with its allocation, valuation and population weights.
- **Defined before used.** Terms, symbols and samples are defined in or before the paragraph that first uses them.

## G2. Compose

1. Take the paragraph's move from the English exemplar of the same function (`exemplars.py find --lang en --function F`): how it opens, where the evidence sits, how it closes.
2. Japanese paragraphs take their connectives, endings, vocabulary and rhythm from Japanese exemplars (`exemplars.py find --lang ja` and `style`), sentence by sentence.
3. Write the paragraph from its sheet line; every sentence carries part of the proposition, its evidence or the link.

## G3. Integrate

1. Read the section through: each paragraph answers the question raised by the one before.
2. Reconcile actors, population, period, estimand, assumptions and numbers with the parent section and the worksheet.
3. Trace compressed claims in the title, abstract, introduction and conclusion back to the paragraphs that establish them.
4. A changed result or definition reopens the paragraphs that use it; unaffected paragraphs stay.

## G4. Delegated paragraphs

A paragraph written by a worker receives its sheet line, the neighboring paragraphs, the sources and saved results, and the fixed definitions ([TEAM](../../../runtime/TEAM.md)); the parent integrates it under G3.

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
