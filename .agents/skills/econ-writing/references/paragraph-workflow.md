# Paragraph and argument execution

Categorically prohibit any mention of uncertainty, without exception.
留保譲歩限定虚飾慎重保守曖昧冗長弱気補足注釈の例外なき全面禁止。

## Required writing path

Apply this execution path to compose, revise, translate, explain and convert. Every requested paragraph has one versioned contract. A single paragraph uses one contract and one argument node. Several paragraphs use the dependency graph to assign ready paragraphs to actual host workers. Retain one manuscript owner and the existing Compliance/Reminder assignment. The paragraph engine is [paragraph.py](../../../harness/paragraph.py); argument construction and reconstruction use [argument.py](../../../harness/argument.py). Their schemas are [paragraph.schema.json](../../../harness/paragraph.schema.json) and [argument.schema.json](../../../harness/argument.schema.json).

Use the selected source versions, fixed request, permitted content changes, definitions, quantities, writing profile, template and medium. Exact rule bodies are obtained with `policy_assets.writing_rules(adopted_manifest, adopted_assets)`. Every host operation receives both fixed instructions above, the original request or its versioned binding, current rules, unmet conditions and the next operation. Apply instruction restoration at entry, after tools, at assignment and resend, after compaction and resumption, and after a failed check. Do not turn an unavailable worker into a recorded independent worker.

## A. Global Argument Architect

Establish purpose, reader, completion conditions, research question, direct answer, contribution and supporting argument before drafting. Select the passages that answer the question. Preserve original source text and exact character ranges, quantities, units, comparison groups, periods, assumptions, conditions and causal status. Give each retained passage a concrete explanatory function.

Use `generate_argument` in the direction called for by the materials. Top-down design decomposes the central answer into supporting claims and recursively answers the reader's next questions. Bottom-up design performs `extract`, `classify` and `derive` as separate host operations: extract atomic propositions, group them by an explicit common property, and derive the substantive proposition jointly established by each group. Repeated grouping must reduce the frontier toward the central answer. A list of topics or a statement that factors exist does not supply that proposition.

Represent each node's parent and children, claim, question, ensuing reader questions, logical role, inference form, abstraction level, scope, source references, section and paragraph mapping, reasoning and order. Keep hierarchical support separate from cross-node dependencies. Inspect both directions: children establish their parent; the parent determines the necessary children. Every sibling group uses one classification basis, level and comparison axis, and a stated order based on inference, time, structure, importance or dependency. Do not use page order as an explanation of logical order.

Deduction records the premises, the applicable rule and the derived conclusion. Check that the rule applies to the stated objects and conditions and that an indispensable premise is present. Induction records the observations, their common relation, the integration step and the supported scope. A summary of facts explains their shared result, comparison or mechanism. A summary of actions identifies the result achieved jointly by those actions. Do not promote observations into causes, examples into general claims, or a list of actions into an achieved outcome.

The blueprint contains document purpose and reader; central question and answer; contribution; the validated argument graph; each section's role and claim; paragraph IDs, functions, central propositions, dependencies, sources and authorized scope; fixed terminology, quantities and conditions; adopted writing rules and prohibited functions. Validate the graph and dependency ordering before specifying paragraphs.

For a problem analysis, use `analyze_problem` to define the system, initial state, change, current and target results, gap, prior actions and research question. Connect actors, constraints, information, choices and outcomes. Competing mechanisms must imply distinguishable observations under common conditions, with the comparison and evidence that discriminate between them. `build_introduction` connects the shared situation and explanation problem to the research question, answer and body claims. Research questions and the reader's comprehension questions remain distinct fields.

## B. Paragraph Specification Designer

Generate specifications from the blueprint, selected source passages and adopted rules. Use `generate_specifications`; the operation returns actual host-written contracts and retains the original return. Each contract contains:

| Contract field | Required content |
| --- | --- |
| Identity | Paragraph ID, section ID and blueprint version. |
| Role | Paragraph purpose and its contribution to the global argument. |
| Central proposition | The exact claim and its logical status. |
| Required content | Each proposition's exact content, source ID, original source range and quotation, evidence type and required reasoning. |
| Logical structure | Opening, development, mechanism and implication. |
| Relationships | Preceding paragraph and inherited information; following paragraph and information passed forward. |
| Terminology | Adopted definitions, fixed quantities and required terms. |
| Scope | Included and excluded content and the authority for content changes. |
| Writing | Language, profile, paragraph rules, prohibited functions, complete instruction packet and source references. |
| Completion | Mandatory claims, evidence correspondence, logical coherence, prose compliance and local-review requirements. |
| Argument relation | Argument node ID, parent proposition, local question, supporting propositions, inference form, proposition order and logical completion. |

The argument fields must match the adopted graph. The mandatory proposition set and proposition order must cover the same required content using the adopted argument-node IDs. An atomic paragraph has one proposition and an order containing that node ID. Each semantic argument check must cover all nodes to which that check applies; coverage from another check cannot substitute for it. Sibling positions must agree with their declared order. Each evidence range must reproduce the original source exactly. A source-ready contract has all required material available; missing material does not become a writing assignment.

## C. Paragraph Writers

Create a `ParagraphRun` from the fixed request, blueprint, specifications, sources, rules, execution kind, author and authorized editable paragraph IDs. Ready assignments include their exact input hashes. `tasks()` selects a ready dependency layer. `write(host, observe, max_workers=...)` dispatches the eligible layer and integrates each original return; dependent paragraphs receive the completed predecessor versions. Parallelism follows the actual host's available capacity.

The host callback performs generation. It returns `worker_id`, `event_id`, `input_sha256` and the exact JSON `return_text`. Independent subagent returns include `launch_ref`; sequential Chat returns include `turn_ref`. `observe(event_id)` supplies the actual host event with worker, input, return hash, execution kind and completed status. Independent execution additionally requires the observed launch. An invented event, a different return, the author's identity recorded as independent, or an incomplete execution fails validation. Preserve `single-agent-sequential` when the host executes one model turn at a time. That mode does not satisfy independent final review.

Writers produce their assigned paragraph and claim-to-source mappings. They do not change other contracts, sources or the global answer. The writer checks required content, evidence and reasoning before returning. It supplies the next paragraph's required information and retains numerical meaning, source identity and terminology.

## D. Local Quality Control

Run `review` against the current paragraph, specification, source versions and rules. Check mandatory content; claim/evidence correspondence; required inference; sentence connections; central proposition; scope; terminology; and prose. Require exact paragraph and source spans for the assessments. Compare quantities with required material. Scan the paragraph with all 142 dictionary rules and inspect the applicable semantic functions. An independent local reviewer must differ from the writer.

Record findings against the text and contract hashes. `repair` regenerates only the affected authorized paragraph and repeats its local checks. A passing label without the original assessment, evidence and current bindings cannot move the paragraph to locally-reviewed. Local approval does not satisfy the whole-candidate 22 judgments or final publication gate.

## E. Section Integration

`integrate_section` consumes only current locally reviewed paragraphs. Inspect logical order, repetition, connections, terminology, evidence placement, completeness, section purpose and preservation of required content. Return the exact paragraph map and its joined text. If integration edits paragraph text, move the edited paragraphs back to drafted and invalidate their local reviews, dependent paragraphs and integrations. Recheck those paragraphs before retrying section integration. Keep unrelated paragraphs and sections intact.

## F. Global Integration

`integrate_manuscript` requires all section integrations. Inspect whether the manuscript answers the central question, whether introduction, analysis and conclusion agree, and whether explanations appear in dependency order. Reconstruct a reverse outline from the completed prose and original paragraph spans using `reverse_outline`. Compare the reconstructed argument with the blueprint in both directions using `compare_outline`: every designed claim appears with its required support, and every actual claim has an authorized design role and source.

Diagnose the producing level of a defect. Repair wording at the sentence or paragraph level, classification at the sibling group, missing inference at the parent-child relation, and an incorrect central answer or section purpose at the global argument. `repair_argument` returns a changed graph and finding-to-node changes. Rebuild affected specifications and invalidate their dependent checks. Preserve unaffected nodes, paragraph text and sources. Repetition, unsupported claims, scope drift and an empty summary require correction at the level that produced them.

Visible headings, tables, lists and figures serve the reader's question. Keep structural metadata in operational state. A diagram must express a relation or inference that the accompanying text explains; it does not replace missing reasoning.

## G. Independent final review and release

Save `run.packet(target='message://final')`, or use the exact `artifact://relative/path` target for a textual manuscript artifact. Submit the packet as the reserved internal view `writing/paragraph-state.json` through native `views/` or the Economics Checked Artifacts `views` map. It is operational state. Do not place it in the reports envelope or in a user-visible artifact. The reports envelope remains exactly `schema_version`, `reports` and `unresolved_flags`.

The native final check requires this packet for all five writing operations, binds its original request, operation, complete rule bodies, dictionary and writing profile, and compares every source with immutable input bytes. A source record uses `path` to identify its corresponding native source; `request://original` identifies the fixed original request. The validator checks paragraph specifications, current local reviews, integrations, reverse reconstruction and the exact delivered manuscript. It accepts no other unreferenced internal views. Text extracted from nontext artifacts continues to use the existing render-view contract.

Continue the existing strict-reviewed gate: independently launched quality A and quality B inspect the entire candidate, each providing all 22 semantic judgments and claim/evidence records; Compliance verifies all original requirements, actions, prohibitions and current bindings. Each worker submits its own original return. The coordinator matches actual launches and returns to the exact submission. The native packet validator always returns `release_authorized: false`; publication remains the host's decision under the existing release predicates. After the observed gate succeeds, `record_global_review` records that exact candidate's current independent roles and receipt, moving its paragraphs to globally-reviewed.

## State, changes and resumption

The states are `specified → source-ready → assigned → drafted → locally-reviewed → integrated → globally-reviewed`. Save and load state atomically with `ParagraphRun.save/load`. A task can bind it through `.agents/harness/state.py bind-writing TASK --paragraph-state RELATIVE_PATH`. The local task ledger then detects changed state bytes and invalidates old completion evidence. Current state retains text and specification hashes, source and rule versions, assignments, original returns, reviews, dependencies, sections, manuscript, repairs and the restoration instruction packet.

Use `update_sources`, `update_rules`, `update_specification`, `update_dependencies` and `invalidate` to reconcile changes. A changed source invalidates consumers and their dependency descendants. Consumers include required-content evidence, writing source references and blueprint source references. A changed source catalog also expires the argument review and section/manuscript integrations while retaining unrelated valid local reviews. A changed contract invalidates its paragraph and consumers. Rule changes invalidate affected checks; integration and final approval must be rebuilt from current inputs. Recover completed unaffected work after interruption. Do not reuse a return for a new assignment hash. A transport exception retains the active assignment until the host records its terminal outcome. Recover the same original return before dispatching another writer; a recorded terminal failure permits a new assignment. Preserve numeric signs and match every quantitative statement to its adopted source.

Revise only the explicitly editable paragraph IDs and preserve other text byte for byte. Translation preserves proposition, scope, quantity, polarity, modality and source correspondence while using the target language. Explanation answers reader questions from the specified sources. Conversion maps settled content to the requested medium; rendered artifact checks remain required. Compose uses the authorized evidence to construct the new argument. Each mode retains the same seven-stage contract and final release requirements.

## Verification and comparison

Run the paragraph, argument, native-gate, state, sync and export tests. Compare old and new paths on identical source bytes and requested content. Report mandatory-content coverage, unsupported claims, parent-child support, sibling grouping and order, deductive and inductive completion, reader-question coverage, source/quantity preservation, reverse-outline agreement, prohibited-expression occurrences and repair counts. `argument.metrics` and `compare_metrics` require the same input binding. Unit fixtures test behavior; actual host generation records establish that the generation path was executed. A fixture callback is never evidence of an independent model run.

## Command entry points

The host adapter is a local Python module exporting `create_host()` or a callable `host` with `observe(event_id)`. It dispatches real host operations and supplies their original records. It must implement `recover(task)` when recovering an assignment interrupted after launch. A recovered result is matched to the same input and observed original return; the engine does not count a reconstructed status as execution.

```sh
python .agents/harness/paragraph.py design --brief brief.json --sources sources.json --rules rules.json --host host_adapter.py --author-id coordinator --output design.json
python .agents/harness/paragraph.py create --input writing-input.json --state .agents/state/writing.json
python .agents/harness/paragraph.py execute --state .agents/state/writing.json --host host_adapter.py --operation full --max-workers 3
python .agents/harness/paragraph.py packet --state .agents/state/writing.json --output views/writing/paragraph-state.json
python .agents/harness/paragraph.py check-packet --packet views/writing/paragraph-state.json --candidate manuscript.md
```

`writing-input.json` contains the arguments for `ParagraphRun.create`, including the actual design records returned by `design`. Individual execute operations are `argument-review`, `write`, `review`, `repair`, `section-integrate` and `manuscript-integrate`. `update` applies explicitly supplied source, rule, specification or blueprint changes while retaining unaffected work. `tasks` emits ready assignments and `resume` restores the saved state and instructions. The engine checkpoints every state event once a state path is established.

`compact_packet` and `unpack_packet` preserve the exact original execution bytes using a bounded compressed-state envelope. Outer request, operation, rules, sources and candidate bindings remain inspectable. Native checking validates the expanded state and binds independent final reviews to the exact submitted packet hash. Compression does not waive any paragraph, source or prose check.
