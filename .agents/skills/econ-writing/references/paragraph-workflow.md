# Paragraph and argument execution

## Required writing path

Use [econ-writing's common process](../SKILL.md#compose-for-the-medium-and-language) to complete the requested argument and its integrated editorial review. The sections below describe the existing composition dependencies. These are reasoning and integration performed in the draft; they create no extra agents, passes, records or gates. Use the parts that resolve the actual dependencies of a long argument.

## A. Global Argument Architect

Identify the reader's question, the central answer, its premises and evidence. Work through the dependency from each supporting claim to the answer and select the order in which a reader can follow it. Build that explanation before shortening the draft.

Derive each parent proposition from the concrete relation among its supporting claims. Start from the actual findings when the parent is unclear, compare their common objects and conditions, and locate the additional premise or discriminating observation needed for the inference. Send that precise dependency to its existing research or analysis owner within the task's authority. Integrate the returned result into the argument and retain unaffected work.

Identify what makes each supporting result usable by the next claim. Measurement defines the compared object; an identifying condition maps variation to the estimand; an optimality or equilibrium relation determines a model response; an aggregation rule maps individual responses into a total. Recover the particular relation from the adopted source. Use it to decide the order and content of the paragraphs carrying that inference.

## B. Paragraph Specification Designer

Give each necessary paragraph one central proposition and the reader question it answers. Decide which evidence or mechanism establishes that proposition and how it connects to the surrounding paragraphs. Allocate space by the work each step performs. Express these choices in the ordinary draft; use the existing paragraph specifications when resumable composition requires them.

Begin where the reader's established premises end. Supply the new observation, definition or derivation, explain its bearing on the proposition, and carry the resulting fact into the next dependent paragraph. Choose the sentence order from that inferential task. Combine sentences establishing one relation and give a distinct proposition its own paragraph. Retain the actor and economic object through the transition so a change of population, time or choice margin is explicit.

Carry the applicable purpose, scope, source identity, adopted definitions and settled decisions into any delegated passage through the existing TEAM handoff. State the unresolved relation the writer must establish and the neighboring claim that will use it. Preserve the authoritative instructions in their existing owners and read them at execution; a paragraph assignment supplies the specific work to perform.

## C. Paragraph Writers

Write a coherent paragraph that establishes its assigned claim and connects with neighboring paragraphs. For Japanese, reconstruct the complete explanation aloud in natural wording before compression. Preserve source-supported actors, operations, quantities and relations while applying PROSE's language rules.

## D. Local Quality Control

Resolve the local claim, source correspondence and wording as part of composition. The completed text's integrated review includes each paragraph's meaning, mechanism and expression. A separate automated check follows CORE's three-condition rule.

## E. Section Integration

Arrange the paragraphs so their concrete claims establish the section's proposition. Connect the steps, place definitions before use and preserve citations. Remove repeated or empty paragraphs and restore a missing premise from the source or completed analysis.

Integrate returned passages by matching their actors, population, period, estimand, assumptions and result status to the parent argument. A change in one of these objects requires its explicit analytical connection. Resolve the difference through the responsible analysis and update affected passages. Make the combined inference using the actual returned evidence; a completed paragraph establishes only the claim supported within it. Select the returned proposition, evidence and determining conditions for the parent draft. Remove effort-based self-justification, self-evaluations and defensive content under PROSE before adapting the passage's wording. Retain the actual operation results in their existing operational destination.

## F. Global Integration

Perform the one substantive integrated editorial review on the finished long argument. Assess the central answer, source support, logical order, section and paragraph connections, prohibited rhetoric and natural language together. Reconcile the title, abstract, introduction, exhibits and conclusion with the body. Trace each compressed claim through the paragraph that establishes its necessary relation, preserving that relation in the finished wording. Repair each defect found and reread the affected passages with their connections until complete.

## State, changes and resumption

Use the existing project record when interrupted work needs a durable handoff. Preserve source identity, settled choices, completed work and the next dependency. The existing paragraph state retains requested source and dependency bindings; ordinary writing creates no parallel ledger.

Resume from the original request, applicable rule bodies and current canonical sources, using the existing EXECUTION state to recover completed outputs and pending dependencies. Restore the binding scope and adopted definitions before integrating a new passage. Keep source-linked quantities and conditions in the draft as it is condensed; reload their authoritative records when a compressed handoff omits them.

## Verification and comparison

Use the smallest existing check that can change a material acceptance decision under CORE. Match final claims, quantities and comparisons to their actual source during the integrated review. Assess the entire argument under PROSE, including paraphrases and rhetorical function, within the same integrated review.

## Command entry points

Use `.agents/harness/paragraph.py` and `.agents/harness/argument.py` for requested versioned composition and argument operations. Actual final artifacts and authorized destination returns establish delivery.

To design a requested section from completed body paragraphs, use the existing `design` entry with the saved run and explicit paragraph IDs:

```bash
python .agents/harness/paragraph.py design \
  --brief writing-brief.json --sources sources.json --rules writing-rules.json \
  --host host-adapter.py --author-id author --execution-kind single-agent-sequential \
  --reuse-state writing/paragraph-state.json \
  --reuse-paragraph results-main --reuse-paragraph mechanism \
  --output section-design.json
```

Use the actual paths and paragraph IDs from the project. The current brief retains the request, authority, reader, language, research type and section function. Both architecture and specification callbacks receive that brief and `completed_body`: the selected paragraphs' original text and specifications, supporting argument nodes, prerequisite relations, adopted exhibits, exact source spans, saved-result references and current version bindings. The canonical central question, answer and contribution stay fixed in the returned design. Use the paper guidance's research-type and section operations to express them in the requested language.

Selection expands through the argument's supporting claims and incoming prerequisites and through each paragraph's `depends_on`. Reuse requires every selected paragraph and prerequisite to have its existing completed review bound to the current text, specification, sources, rules and dependencies. A changed binding identifies the paragraph whose producing work must finish. Unrelated paragraphs stay outside `completed_body`. The design operation reads the saved run without a resume event and writes its new design to the specified output.

For an existing Python caller, use `ParagraphRun.load(path, resume=False).composition_context(paragraph_ids)` to read the same selected context. Pass the loaded run and `paragraph_ids` to `generate_blueprint` and `generate_specifications`; pass the current `brief` to the specification call. These operations consume the existing state and actual saved evidence.
