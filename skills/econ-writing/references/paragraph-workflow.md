# Paragraph and argument execution

## Required writing path

Use [econ-writing's common process](../SKILL.md#compose-for-the-medium-and-language) to complete the requested argument and its integrated editorial review. The sections below describe the existing composition dependencies. These are reasoning and integration performed in the draft; they create no extra agents, passes, records or gates. Use the parts that resolve the actual dependencies of a long argument.

## A. Global Argument Architect

Identify the reader's question, the central answer, its premises and evidence. Work through the dependency from each supporting claim to the answer and select the order in which a reader can follow it. Build that explanation before shortening the draft.

Derive each parent proposition from the concrete relation among its supporting claims. Start from the actual findings when the parent is unclear, compare their common objects and conditions, and locate the additional premise or discriminating observation needed for the inference. Send that precise dependency to its existing research or analysis owner within the task's authority. Integrate the returned result into the argument and retain unaffected work.

Select each admitted source once with a substantive reason. For bottom-up reasoning, extract source-bound atomic claims, partition each frontier under a common classification, and derive a parent for each group until the central answer is established. Keep the original question and answer, source IDs and hashes fixed. Problem comparisons and their verification tasks cite the admitted evidence.

Identify what makes each supporting result usable by the next claim. Measurement defines the compared object; an identifying condition maps variation to the estimand; an optimality or equilibrium relation determines a model response; an aggregation rule maps individual responses into a total. Recover the particular relation from the adopted source. Use it to decide the order and content of the paragraphs carrying that inference.

## B. Paragraph Specification Designer

Give each necessary paragraph one central proposition and the reader question it answers. Decide which evidence or mechanism establishes that proposition and how it connects to the surrounding paragraphs. Allocate space by the work each step performs. Express these choices in the ordinary draft; use the existing paragraph specifications when resumable composition requires them.

For a result-based passage, connect the economic object and its population to the named estimand, proposition or counterfactual; recover the identifying variation, equation and determining conditions; interpret the direction and magnitude against the adopted comparison; and establish the claim used by the next paragraph. Keep units, denominators, periods and scenario definitions with their quantities. Select the equation, direct contrast or aggregation that makes the proposed inference valid before choosing which saved values to include. A mechanism uses the study's intermediate evidence or model derivation; an economic magnitude uses its baseline, scale or allocation consequence.

Select the supporting inputs for that inference through the same source/result bindings. A paragraph using a joint diagnostic needs its tested vector, covariance-based statistic and reference distribution; a paragraph comparing groups needs the direct contrast and its saved inference; a welfare paragraph needs the allocation, valuation and population weights used in its total. Read those selected objects through the relevant [paper guidance](paper-workflow.md#identification-and-empirical-method) and [model argument](paper-workflow.md#theory-model-and-proof). State the resulting economic proposition in the paragraph and carry its defining relation into any abstract or conclusion that uses it.

Begin where the reader's established premises end. Turn those relations into the sentences needed to establish the paragraph's proposition, selecting their order and length from its inferential task. Combine sentences establishing one relation and give a distinct proposition its own paragraph. Retain the actor and economic object through the transition so a change of population, time or choice margin is explicit. Reuse these choices in the existing paragraph specification when versioned composition is requested.

Carry the applicable purpose, scope, source identity, adopted definitions and settled decisions into any delegated passage through the existing TEAM handoff. State the unresolved relation the writer must establish and the neighboring claim that will use it. Preserve the authoritative instructions in their existing owners and read them at execution; a paragraph assignment supplies the specific work to perform.

## C. Paragraph Writers

Write the completed paragraph that establishes its assigned claim and connects with neighboring paragraphs. Develop the evidence-to-claim inference in the actual wording, using the selected source passages, saved quantities and adopted equations. For Japanese, reconstruct the complete explanation aloud in natural wording before compression. Preserve source-supported actors, operations, quantities and relations while applying PROSE's language rules.

## D. Local Quality Control

Resolve the local claim, source correspondence, mechanism and wording during composition, then include that text in the single review under [Global Integration](#f-global-integration). CORE governs any additional automated check.

## E. Section Integration

Arrange the paragraphs so their concrete claims establish the section's proposition. Connect the steps, place definitions before use and preserve citations. Remove repeated or empty paragraphs and restore a missing premise from the source or completed analysis.

Integrate returned passages by matching their actors, population, period, estimand, assumptions and result status to the parent argument. A change in one of these objects requires its explicit analytical connection. Resolve the difference through the responsible analysis and update affected passages. Make the combined inference using the actual returned evidence; a completed paragraph establishes only the claim supported within it. Select the returned proposition, evidence and determining conditions for the parent draft. Remove effort-based self-justification, self-evaluations and defensive content under PROSE before adapting the passage's wording. Retain the actual operation results in their existing operational destination.

## F. Global Integration

Complete [PROSE's passage review](../../../runtime/PROSE.md#finish-the-passage) on the finished long argument, covering the answer, evidence, logical order, paragraph connections and expression. Reconcile the title, abstract, introduction, exhibits and conclusion with the body. Trace compressed claims through their establishing paragraphs; retain the relation each conclusion needs. Repair discovered defects and reread the affected passages and connections within that review.

## State, changes and resumption

Use the existing project record when interrupted work needs a durable handoff. Preserve source identity, settled choices, completed work and the next dependency. The existing paragraph state retains requested source and dependency bindings; ordinary writing creates no parallel ledger.

An argument repair retains the fixed request, authority, purpose, reader, admitted sources and completion conditions. Attribute each changed node to its actual finding, preserve nodes outside the affected dependencies, save the revised version and invalidate the affected reviews.

Resume from the original request, applicable rule bodies and current canonical sources, using the existing EXECUTION state to recover completed outputs and pending dependencies. Restore the binding scope and adopted definitions before integrating a new passage. Keep source-linked quantities and conditions in the draft as it is condensed; reload their authoritative records when a compressed handoff omits them.

## Verification and comparison

Apply [CORE's completion rule](../../../runtime/CORE.md#completion-and-reporting) to additional checks. Source correspondence and PROSE judgment belong to the integrated review above, including paraphrases and rhetorical function.

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

`evidence_paths` maps a selected result ID to a nonempty list of distinct key paths relative to that record's `source_result`; each path is a nonempty list of nonempty strings. Each selected value is returned in `research_result.evidence` with its `keys`, original structured `value` and `source_reference`. That reference contains the registry `path`, `keys:["records", RESULT_ID, "source_result", ...]` and the selected value's `content_version`. The example passes the saved joint test and the event-minus-one p value with their original shapes. The writer recovers their tested contrasts and interval family from the adopted design and selected source definitions, then explains their relation in the manuscript. Select additional saved paths when that explanation requires their contents.

Pass the design output's `blueprint`, `specifications`, `sources` and `design_records` into the existing `ParagraphRun.create` input. The writer develops the evidence-to-claim explanation above; completed paragraphs retain these same sources for later section design and reuse. An initial sources file can contain `{}` when the brief supplies the selected results.

To design a requested section from completed body paragraphs, use the existing `design` entry with the saved run and explicit paragraph IDs:

```bash
python harness/paragraph.py design \
  --brief writing-brief.json --sources sources.json --rules writing-rules.json \
  --host host-adapter.py --author-id author --execution-kind single-agent-sequential \
  --reuse-state writing/paragraph-state.json \
  --reuse-paragraph results-main --reuse-paragraph mechanism \
  --output section-design.json
```

Use the actual paths and paragraph IDs from the project. The current brief retains the request, authority, reader, language, research type and section function. Both architecture and specification callbacks receive that brief and `completed_body`: the selected paragraphs' original text and specifications, supporting argument nodes, prerequisite relations, adopted exhibits, exact source spans, saved-result references and current version bindings. The canonical central question, answer and contribution stay fixed in the returned design. Use the paper guidance's research-type and section operations to express them in the requested language.

Selection expands through the argument's supporting claims and incoming prerequisites and through each paragraph's `depends_on`. Reuse binds every selected paragraph and prerequisite to its current text, specification, sources, rules and dependencies. The ordinary path reads completed text through those bindings. The explicitly selected independent path also retains its completed independent review. A changed binding identifies the paragraph whose producing work must finish. Unrelated paragraphs stay outside `completed_body`. The design operation reads the saved run without a resume event and writes its new design to the specified output.

For an existing Python caller, use `ParagraphRun.load(path, resume=False).composition_context(paragraph_ids)` to read the same selected context. Pass the loaded run and `paragraph_ids` to `generate_blueprint` and `generate_specifications`; pass the current `brief` to the specification call. These operations consume the existing state and actual saved evidence.
