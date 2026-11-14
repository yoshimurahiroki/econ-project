# State, consumed dependencies and resumption

Use this interface for durable state, saved-result reuse or resumption under [ECONOMIST](../runtime/ECONOMIST.md). [TEAM](../runtime/TEAM.md#resumption) owns recovery of the governing task, and [EXECUTION](../runtime/ECONOMIST.md#5-execution) owns operation completion.

## State and version contract

1. **Session -> ordinary work.** The native hook initializes private `session.json` and its writer lock. It retains the original request, verbatim later messages, kernel delivery identities, child assignments/returns and once-per-turn review markers. Large child bodies use immutable source references. An independent task archives the preceding scope and starts its own holds/children; Continue retains the adopted request. Explicit durable adoption carries that scope into the task context. Startup validates existing session and durable stores. A startup failure blocks that prompt and reports the repair; retry follows the repaired input.
2. **Kernel -> executor.** Session start, a fresh child context and context recovery deliver the complete the economist's procedure and WRITING. Later prompts reuse the intact same-version kernel. Read a saved packet with its exact returned command; delivery metadata identifies source bytes.
3. **Contract -> durable owner.** Pass the current `session.json` as `bind-operation --hook-context` with the complete requested outputs/actions and `--operation-kind`. The return supplies `context_path` for subsequent bindings. Validation precedes task publication. Existing durable contexts retain authority, holds and completion requirements. Valid legacy ordinary pointers are cleared while their saved directories remain available; existing child handoffs retain their owner through integration.

Use detailed task state for durable continuation, saved-result reuse or an explicit request. Tasks bind one owner, requested outputs/actions, write scope, protected inputs, authority/holds and the next action. Scheduling states are queued, running, blocked, completed and failed; completion does not mean publication.

`state.py` uses one parsed subcommand classification for execution and hooks. Store mutations, `prepare-context`, `project-update`, `inspect --invalidate` and `project-view --save` require authorization; ordinary reads remain direct. Ordinary state writes require their exact command and store/saved-view file targets within scope. For explicitly bound durable tasks, retain the actual request and selected output/action contract, target the existing store/task, and match changes or hold releases to saved user messages. Automatic session startup creates no task contract. This bookkeeping grants no artifact or external-action authority. Interactive input additionally binds the initiating command, live session and exact `stdin://SESSION/SHA256` input. Delegation uses the exact call target `agent-call://SHA256`, hashing canonical JSON `{tool_name,tool_input}`; its required action uses the tool's operation name. When a durable task contract is explicitly in use, a child write uses a unique descendant task whose `owner` is the actual host agent ID, with its own authority, running state and bounded contract.

Use the existing runner's dependency graph. `after` orders starts; `consumes` binds actual producer/output versions and scientific `definition_versions`. A changed consumed sample, measurement or estimand invalidates its users even if numerical bytes match; unrelated outputs and style-only changes do not trigger recomputation. `publication_group_id` binds outputs required to be current together.

The helper verifies file/value content identities and rejects changes during reads or stored hash mismatches. Paths identify locations separately from content. For in-place edits, retain the old version as input and new version as output; preserve protected inputs. Keep requirement/context revisions and actual action/check evidence in the same record. TEAM owns assignments and requested usage accounting.

## Governing context

Register `task_context` with `add --task-context FILE`: `request_refs`, `goal_and_constraints`, `active_instruction_refs`, `adopted_decisions`. References bind source/rule identity, version and `content_sha256`, optionally a hash-matching relative path. Decisions bind ID, version, choice, reason and switch condition; `change_authority` is fixed unless the task delegates revision. Derive required outputs/actions from the governing request. Ordinary hypotheses/results use `outputs`; continuation uses `next`.

`context_id` binds governing content, authority, holds and requirements, excluding progress, time and display-only changes. Child scope/authority must fit every ancestor. Changed governing context/holds invalidate affected child assessments while preserving output bytes; unrelated outputs/holds do not. The helper verifies these bindings at start/resume and result acceptance.

After context loss, restore original applicable bodies and settled choices through TEAM. Reconcile an authorized change with `set-context ID --task-context FILE`; changed referenced/record bytes require reconciliation or requeue. Use the existing explicit release-hold operation for a user/permission hold. Context changes alone do not remove scientific results or alter numerical dependencies.

`set-context` retains revisions. Removing/replacing governing instructions, fixed decisions or the objective requires the already-given instruction in `--user-change FILE`, with previous/replacement context hashes. This records authority and does not require asking again. A path-only change preserving source/version/content grants no new authority.

To revise a delegated choice within its existing switch condition, supply `--decision-update JSON` with `decision_id`, `reason` and existing result-path `evidence`. Read the evidence and establish the economic switching condition; the helper verifies bytes, not that judgment. Deletion, a changed switch condition or fixed-to-delegated conversion requires the bound user instruction. Preserve prior analysis versions.

## Retain and retrieve adopted definitions

Each adopted decision may carry `references` in the same `{kind,id,path,version,relation,basis}` format as an argument node. Use the source catalog or retained knowledge output for the inspected original and its locator/version; use `json` with `keys` for the selected definition in the canonical research specification or `data-record.json`. Keep the adopted meaning, unit, observation unit, timing, transformation and join keys at that scientific owner. The decision records the choice, reason, switching condition and existing change authority. Saving those references uses `set-context` and its existing revision rules.

Use `python harness/state.py context --help` for the command and options.

The command searches the selected task and its governing ancestors, reads only the selected source/definition references and returns their current identities, values and impact actions. `--history` returns the existing context revisions. `--reference JSON` resolves a proposed owner reference and returns `current_version` before it is adopted; copy that identity into the reference's `version`. Retrieval does not change the store or run an analysis. Resume through the existing context and source checks, retaining the original instruction bodies.

To link a decision to an argument or another adopted decision, use `kind:"decision"`, `path:TASK_ID`, `id:DECISION_ID` and the returned content `version`. This resolves the actual `task_context.adopted_decisions` record. A changed supporting source requests review of that decision; the existing argument relations propagate the affected action. A changed adopted scientific definition follows its declared execution or generation dependencies. A source review or presentation edit retains matching numerical results. Versioned original knowledge and interpretation remain at their separate existing owners.

Older receipts lacking context_id cannot establish a current context-bound check; retain their outputs and obtain only the missing assessment.

The existing hook restoration includes the bound task and ancestor governing contexts, their adopted decisions, original request/specification and instruction bodies, required outputs/actions, saved result references and next operation. It restores task and ancestor object/message values with their locators, versions and current/stale status; identical values are included once. These saved hypotheses and results are evidence, and the original instruction and decision authority still govern their use. Source bodies are checked against their recorded hashes and included once per identical content. For structural research, bind the canonical model specification as a request/source reference and carry its revision through the consuming estimates and counterfactuals. Ordinary progress and reusable numerical experience stay in existing outputs and continuation records; they preserve the binding source and its change authority.

For a task that actually needs a durable completion contract, bind its original outputs/actions and authority through the registered hook context. Ordinary file modifications and external actions do not require a state contract merely because the hook started. An already bound durable task retains its contract at its state owner. Use the registry reader for ordinary operation selection. An existing durable context uses `bind-operation --operation OPERATION` to select rules while retaining its contract. For an explicitly selected file contract:

```sh
python harness/codex_hooks.py --root /absolute/project bind-operation \
  --hook-context /absolute/plugin-data/economics/SESSION_SHA256/session.json \
  --operation econ-data:execute --condition data_code_change --operation-kind modify \
  --authority 'Original user request' \
  --required-output '{"role":"implementation","kind":"file","target":"analysis.py"}' \
  --required-action '{"operation":"update","target_kind":"file","target_id":"analysis.py"}'
```

Repeat `--condition` for each activated condition and supply `--profile` when selected. Declare every original deliverable with repeated `--required-output` and `--required-action`, using the state helper's role/kind/target and target_kind/target_id/operation records. File outputs need their producing actions and actual retained user authority; the final response is added as a message requirement. Exact object and interactive-input authority uses repeated `--external-target`. The existing context owns this minimal completion contract without creating a state store. Rebinding retains obligations; removal uses the existing user-change contract. Matching preflight and current output bytes support completion evidence; callbacks without a matching preflight are recorded as such without claiming authorization.

The economist's procedure owns the lead's comparison of the full original request with registered outputs/actions. Native Stop reports incomplete contract results and current files without blocking for those checks. It requests one semantic revision of the final response and created or materially edited user-facing local artifacts per turn, including generated files. The continued host assigns one actual native subagent when available, waits for its return and integrates its changes; otherwise the host performs the pass itself and reports the actual result. Stop permits the next completion even if a check fails. This request is not evidence that a subagent ran or an artifact was actually reviewed. Host authority, scope and approval controls remain in effect. Historical 0.89.2 confirmation messages remain inert context.

For resolved file effects, record the affected required file versions before the authorized producing call and compare content after its callback. Opaque command returns establish the exact command status; generated scientific files retain the existing result owner's version and execution binding. A pre-existing unchanged file supplies no new production evidence. Preserve valid prior outputs across unrelated no-op commands; deliberate reuse follows the existing saved-result/state owner. Interactive polling retains the initiating call's baseline only while its session is live. At completion, re-read every required file and match its current hash; a deleted, replaced or changed file invalidates the saved result. Production evidence and current file identity are checked separately.

1. **Stage -> reader.** Use `bind-operation --stage STAGE` for a bound task's pending operation. Retain its operation, conditions, profile and scientific contract. Its callback delivers the complete selected stage and prerequisites; later-stage bodies remain deferred. Ordinary tasks use `route_registry.py read`.
2. **Recovery -> executor.** After compaction or child launch, restore applicable originals and the selected TEAM recovery rules. Stage-only refresh retains unchanged request/project/result sources. A changed operation, method or source clears the old stage unless a new stage is supplied. Source identities preserve authority; The economist's procedure owns complete reading.

The explicit command records the operation, conditions, profile and a fingerprint of the exact selected source/rule closure. the economist's procedure and the selected Skill own input and completion rules. Repeating the same binding preserves its bytes. Removing a declared output, action or external target requires the existing `--user-change` evidence; additive requirements preserve the earlier contract revision. A source, request or selection change follows the task's existing authority and explicit rebinding. A later durable state binding must retain the declared requirements and authority. Tasks using the state helper retain their full request and applicable instruction references through `task_context`. In ChatGPT Cloud, use the available state, file and native-agent paths to restore those sources after context loss. Local hook installation configures the clients that load it.

PreToolUse classifies current native and connector tools and preserves the host's actual authority. Explicitly bound state or completion contracts retain their target, scope and hold checks. Ordinary operations need no additional state-registration approval. PostToolUse retains the actual callbacks and affected output versions needed by a selected completion contract. Stop compares that contract with its saved results; ordinary work follows the economist's procedure's integrated review and actual operation return. Failed or missing work remains incomplete, and child returns must reach the parent. Instruction changes are detected at their mutation or binding boundary. Compact/resume restores the complete original request, adopted specifications and applicable rule bodies. Explicitly selected independent certification retains its existing state-owner requirements.

The existing reinjection record retains the manifest, operation/source closure and current reading stage selected under [the economist's procedure's task entry](../runtime/ECONOMIST.md). Entry, changed binding/stage, compaction recovery and delegation deliver applicable text through their callbacks. Stage-only refresh retains unchanged request, project sources and saved values; actual context loss restores them. An ordinary continuation reuses unchanged bodies in the active context and retains the exact request/amendment locations; changed bound sources deliver their new bodies. Scoped AGENTS.md refresh checks current bytes and emits changed bodies; actual context restoration emits the complete applicable stage bodies. Default contexts use the same stage selection. Each callback shares its loaded modules and starts with a fresh snapshot. Unchanged operational records retain their bytes. Delivery and source hashes preserve identity; The economist's procedure owns complete reading.

`PostCompact` records pending restoration in the existing reinjection record using the host's stop/message contract. There is no PreCompact registration. `SessionStart(source=compact)` delivers the full restoration and clears the pending state. Keep exact host event/trigger identities and the actual spill-file locator. Read the complete original request and required rule bodies from their saved sources before dependent work; a callback, saved snapshot or reading receipt supplies no omitted text.

Compaction pending state is associated with the root or actual child `agent_id`. A continuing `PreToolUse` or `Stop` returns the governing text; Stop also requests one prose revision per turn. A root SessionStart consumes its own pending state. Child restoration retains the exact observed successful native spawn call and return in the existing child record, with its source hash, original assignment and parent context. The returned `agent_id` identifies the runtime child when present; otherwise `task_name` supplies its canonical identity. The complete launch and return retain both fields with the assignment. Each level uses its direct parent and the same ancestor authority and context.

1. **Check -> next action.** Existing observable authority/completion checks share two advisory notices per host turn. The separate Stop marker requests one independent final review. Reading and equivalent evidence follow the existing task contract; hooks retain no text-exposure checklist.
2. **Packet -> reader.** Measure the entire serialized response against the declared byte budget. Oversized responses retain one immutable UTF-8 packet and return an exact `read-packet` command. One call returns up to 16,000 characters; a non-null `next_offset` continues with the same SHA-256, and character pages preserve a long single-line assignment. Stop retains its required action first.
3. **Propositions -> delivery.** WRITING routes public claims, internal items and numerical uncertainty to their existing owners. The final-form card and exact WRITING finish read accompany the once-per-turn review. Write-target AGENTS bodies follow their actual subtree and changed-source boundaries.

Recover a missing child assignment from its original parent source. Register that exact text in the already authorized task's `request_refs`, using source ID `child-assignment:AGENT` and its content hash, then bind it through the existing context:

```sh
python harness/codex_hooks.py --root /absolute/project bind-child-assignment \
  --hook-context /absolute/plugin-data/economics/TASK/context.json \
  --agent-id AGENT --source-id child-assignment:AGENT --source-sha256 SHA256
```

The binder requires the observed child and matching existing bound-state source. Missing assignments are reported without blocking writes or completion. The next boundary emits the recovered assignment and applicable rules. Restored sources retain their actual authority, holds and versions, and callback provenance remains recorded as observed evidence.

## Project work

Use the existing task store and [argument engine](argument.py) sources for requested persistent project work. `project-work:contribute` and `project-work:manage` select the user's role; ordinary one-step work continues through its existing specialist.



The definition has `schema_version:1`, `argument:{path,sources_path}`, `resources`, `work`, `data_date_hour`, `time_unit:"hours"`, `origin`, `target_finish_hour`, `approved_finish_hour` and `decision_rights`. A project without a GitHub binding also supplies `priority`, naming each work task once. Optional `budget` and resource/fixed costs use a declared `currency`. `origin` is an ISO timestamp with timezone or an explicit `relative:LABEL`. Each resource maps its ID to `capacity_units` and `hourly_cost`. Each work row supplies an existing descendant `task_id`, determining `node_ids`, positive `duration_hours` and required resource units; optional `release_hour`, `fixed_cost` and `effect` preserve their declared meanings. Additional project-owned definition and work fields remain intact. The argument and source catalog own the adopted question, answer, model and evidence. The task store owns executable operations, worker roles, execution dependencies, produced versions and completion receipts. A GitHub binding assigns human tasks, assignees, progress, priority, due dates and issue dependencies to GitHub Issues/Projects.

Binding stores exact definition, argument and source paths and hashes. Repeating it preserves its bytes. Keep preceding sources at immutable versioned paths. A changed bind requires `--user-change` with the actual source, message ID/text, `previous_project_sha256` and `replacement_project_sha256`, computed with the existing `content_hash` on the old and new binding objects. Stop an active task before changing its adopted binding. A revised completed parent is blocked for its affected reassessment with its outputs preserved. The project binding affects its owner's context; selective consumption and `project-impact` retain reuse of unaffected child results. Source and amendment-evidence drift feed the existing resumption and ancestor constraints.

`project-history CASE` returns the existing numbered revisions, bindings, amendment source and dates. `project-diff CASE --from-revision 1 --to-revision 2` compares the saved definition, argument and source catalog. To assess an edit before adoption, save its changed sources at new paths and run `project-diff CASE --definition plan-v2.json` or `project-impact CASE --definition plan-v2.json`. Both return the proposed binding, structured changes and affected/reusable task/output identities with their Issue links. A work-duration or resource change requests schedule reassessment. A changed argument premise follows the existing scientific impact traversal. Adopt the proposed version with `project-bind` and its actual amendment evidence.

The views derive the current summary, argument story and workplan from this same binding and state. Contributor views select the named owner's work; manager views include the case's decision rights and shared resources. Work rows connect their actual argument propositions, input/consumed-output versions, required outputs/actions, current output identities and next action. Their priority rank and schedule come from the same forecast. `next_tasks` identifies work whose dependencies, release and resource slot permit continuation at the data date; completed work is reused. It grants no execution permission.

`forecast` computes a feasible schedule under the selected priority, precedence, release, data-date and resource constraints. It reports the precedence-only critical path, resource waits, resource units, remaining/total planned direct cost, budget and approved/target/forecast/actual times, including target and approved-date delay hours. Running work retains its resource slot ahead of unstarted work in `execution_order`; a new proposed priority queues behind it. An unresolved predecessor is blocked. Shared projects require matching origins, data dates, currencies and common capacities. Repeat `--project CASE` for the portfolio in forecast, summary or workplan. Repeat `--priority TASK` for every selected task to compare a candidate global order; `--capacity '{"RESOURCE":2}'` compares proposed capacities. Proposals use the same scheduler without changing sources, saved priorities, authority or actual capacity. Deadline losses and the opportunity cost of displaced work belong in the economist's procedure's economic comparison, where elapsed time and money stay separate quantities.

Use existing object outputs for actual project observations. Supported roles are `project_judgment`, `project_acceptance`, `project_handover`, `project_outcome` and `project_actual`. The value records `actor`, `date`, `status`, nonempty `evidence:[{path,sha256}]` and `target`. An artifact target is `{task_id,output_id,content_version}`; an argument target is `{node_id,argument_sha256}`, using `argument.argument_sha256`. Current sources and artifact versions determine which observations enter the views. Actual acceptance/handover must name the actor in `decision_rights.acceptance` or `.handover`. Preserve the actual evidence's provenance.

The same object-output interface records `project_finding` with status `observed`, `project_interpretation` with status `recorded` or `proposed`, and `project_open_decision` with status `open` or `resolved`. Each adds a nonempty `text`; an open-decision record also supplies its `decision_id`. Declare the role and object ID through the task's existing required output, then register or edit it with `output TASK ID --kind object --value JSON`. Summary returns these current records as `findings`, `interpretations` and `open_decisions`. It reads `adopted_decisions` from the existing governing `task_context`; use `set-context` with its existing amendment/delegated-decision evidence to edit an adopted choice. A decision present in that adopted context leaves the open list. Output content versions and context revisions retain their existing ownership.

Judgment status is `supported`, `refuted` or `proposed`; acceptance is `accepted`, `rejected` or `proposed`; handover is `handed_over`, `rejected` or `proposed`. An outcome records `observed_value`, `unit`, `target_value`, `comparator` and `observed` or `proposed` status. Actual work timing records `start_hour`, `finish_hour` and `actual` or `proposed` status against its task output. A completed task retains its scheduling meaning. Assess the target outcome and actual acceptance from their respective evidence, then perform the required next work.

For an economic allocation decision, extend that existing judgment's value with `allocation:{project_bindings,priority,rationale}` and an optional nonempty `switching_condition`. `project_bindings` maps every selected project ID to `content_hash(binding)` from `project-bind`; `priority` names all selected work tasks exactly once. Record the same objective's outcome comparison, information value, costs, displacement and assumptions in the rationale and its existing evidence. Count an information-induced improvement once. Use existing consumed-output dependencies for determining results and retain the current argument target. Numerical inputs need their actual source; a supported ordering or switching condition can select the action without invented numbers.

Only a current `supported` judgment from the actor in `decision_rights.allocation` changes the default forecast. For shared projects, matching judgments must establish the allocation rights of every affected project; a common authorized actor can cover its projects in one record. Only a supported judgment adopts an order. Conflicting supported allocations require the authorized decision; replace the existing judgment output through its normal versioned path. Changed plan bindings or determining evidence require reassessment. With declared allocation rights and no current adopted judgment, the view returns `decision-required` and no next tasks. Legacy plans without allocation rights retain their explicit baseline priority. Ordinary recorded authority covers recorded decisions; external mutations and user-fixed specifications and commitments keep their own authority.

`project-impact` joins argument change propagation with task and consumed-output dependencies, returning affected and reusable task/output identities. Use `--node CLAIM` for a changed proposition, `--resource ID` for changed capacity, `--task ID` for a work-timing change, or `--deadline` for changed dates; at least one is required. Repeat `--project CASE` to include sharing portfolios. `schedule_task_ids` includes competing resource users and dependent work, while `affected_outputs` identifies scientific results whose actual argument/output dependencies changed. Valid scientific outputs stay valid under capacity or deadline changes alone. Apply an authorized change through the existing context, requeue, input, output and research commands, compare the revised forecast and update the existing judgment when its decision changes. The impact query keeps the state unchanged. Root and child hook restoration include the complete current definition, argument and source catalog from the existing project binding, once per content hash. Their emission retains the full-reading obligation.

Argument nodes and adopted decisions share `references:[{kind,id,path,version,relation,basis}]` to join existing owners at read time. `knowledge` selects a local knowledge ID and its true prerequisite bodies through Reader; externally acquired knowledge uses the existing task `output` reference returned by `knowledge.py acquire`. `literature` selects an original corpus proposition and verifies its original locators; `claim` selects the existing evidence contract's current claim fingerprint. `file` binds bytes, `json` adds the nonempty `keys` path for a selected value, and `output` uses the producer task ID as `path` and its output ID as `id`. `decision` selects an adopted decision from that task. A selected artifact-registry value also binds its actual producer references, even when a recomputation returns the same value. Versions are the returned content identities. File paths are project-relative. Knowledge `path:"@package"` reads the executing package's own collection. The other owners remain at their registered code paths.

`project-impact CASE --references` compares those identities. Reference relations `supports`, `refutes`, `assumes`, `prerequisite_to_understand` and `requires_to_apply` request review; `execution_input` requests recalculation; `generated_from` requests regeneration; `adopted_specification` requests authority. `related`, `alternative` and `alternative_under` remain reference-only. Optional `when:{decision_id:[accepted_choice]}` uses the current adopted decisions in governing context. Missing conditions or inputs require a decision/input, and a mismatched condition is inapplicable. Existing argument dependencies can add `effect:review|recalculate|regenerate|authority|reference` and the same `when`. Their direction remains prerequisite to consumer. The existing impact traversal propagates these effects; review and missing authority stay review and missing authority. It returns `node_actions`, `unresolved_conditions` and task `actions`, alongside existing affected/reusable identities. For an actual known node change, repeat `--change NODE=ACTION`.

Summary, story, workplan and forecast expose these selected dependencies as `reference_impact` and hold work requiring authority. Analyze joins the same impact into affected task findings; Converge consumes that analysis. Completion checks the same selected references for the task and its bound project, rejecting unresolved changes without adding a review plan. A related-reference or bibliographic metadata update supplies no numerical dependency. A changed result follows its actual output consumers; `after` remains start order. A work row can declare the adopted `effect` for a consumed result. A consumer with a typed argument edge or work effect follows it; the owner decides whether any other consumer is an estimate or an exhibit. Read the classified action and its current reference before choosing review, requeue or artifact generation. A reference query reads; edits to an adopted model, project binding, task, output or permission go through their owners. Reuse valid estimates during a source review. Adopt an authorized changed specification through the existing versioned project/context binding, then requeue only the affected outputs and record the actual new results. The existing full project restoration retains these references, the original request, fixed decisions and preceding source versions.

Read the [interface](state.md#interface-project-work) for the exact input forms.

## GitHub Issues and Projects

Add the GitHub identifiers to the existing definition. A Project is selected by its GraphQL node ID; an Issues-only project supplies linked work Issue numbers. Several executable tasks can link to one Issue. Human tasks in the selected repository's Project also enter the summary before they acquire an execution task.



`repository` is required. `project_id`, `issue_template`, `fields` and `status_groups` are optional. A Project can also use `project:{"owner":"OWNER","number":1,"owner_type":"organization"}`; `owner_type` defaults to `user`. The reader resolves this selector to the current GraphQL node ID. When both selectors are supplied, they must identify the same Project. Field mappings default to the names shown. Artifact IDs link the existing result/gallery/document registry; saved results, figures and documents retain their original owners. `links` in the derived task includes the bound plan, linked artifact IDs, current execution outputs and Issue URL.

`project-view` reads Issues and both directions of their native dependencies through GitHub REST. It reads Project fields and items through GraphQL, including all returned pages, field types, single-select options and current/completed iterations. The external executable is GitHub CLI with `gh api --paginate --slurp`; it uses the current user's existing authentication. Issue reads require repository Issues read access; Project reads require `read:project` or the corresponding GitHub App permission. See [GitHub's Projects API](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects), [Issue dependencies REST API](https://docs.github.com/en/rest/issues/issue-dependencies) and [gh api](https://cli.github.com/manual/gh_api). `project-view` performs reads. `project-update` is the explicit write command described below; browser and connector writes use their authorized operation.

For an Issues-only workflow, use an Issue form with headings `Priority`, `Due date`, `Classification`, `Progress` and `Related research`. The corresponding Japanese headings are `優先順位`, `期限`, `分類`, `進捗` and `関連研究`. Current Project field values take precedence over these Issue-body values. Title, URL, assignees, open/closed state and native issue dependencies come from the Issue API. Editing the Issue body or Project field in GitHub changes the next view. An absent due date remains JSON `null`.

An optional `github.fields.publication_stage` maps the adopted Project field, for example `"publication_stage":"Publication stage"`. Issues-only workflows use `### Publication stage` or `### 投稿段階`. The derived task retains the actual value, including stage `0`, and meeting materials place it beside ownership and due date. Existing configurations retain their current field mappings. GitHub status and native dependencies determine execution buckets and scheduling; the publication value describes the manuscript's publication process.

Use these standard options from [Lebo2016, pp.260–262](https://doi.org/10.1017/S1049096516000160) when setting up the selected Project field. Preserve the project's adopted labels and current value.

| Stage | Publication milestone |
| --- | --- |
| 7 | Research idea and agreed scope |
| 6 | Paper outline and acquired inputs |
| 5 | Complete manuscript with results |
| 4 | Presented manuscript and feedback |
| 3 | Journal review |
| 2 | Requested revision |
| 1 | Review of revised manuscript |
| 0 | Acceptance |

Refresh `project-view --save` after a GitHub stage change and pass that saved view to meeting creation. `project-bind`, `project-diff` and `project-history` retain changes to the adopted field mapping through the existing definition revisions; actual GitHub values retain their acquired snapshot identities. Source or specification changes use `project-impact` for scientific consumers. Compare resource competition and execution order through the existing `forecast` and adopted project judgment.

The view returns native browser management links, the template-specific new-Issue link, Project field IDs/options, REST endpoint and GraphQL endpoint. Open an Issue to change its assignees, form text or dependencies; use the Project URL to edit its fields. GitHub documents [Issue-template URL parameters](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue#creating-an-issue-from-a-url-query). The template remains in the repository's existing Issue-template directory.



`--github` accepts a current read snapshot from an authorized connector. Repeat it for a portfolio. A connector's nested `structuredContent` and JSON-string `content` envelopes are unwrapped before the existing snapshot validation. The contained snapshot identifies its actual source and acquisition time, matches the bound repository/Project, and contains complete Issue/dependency lists. Native reads construct the same shape:



For a Project, replace `null` with `{id,url,title,fields,items}`. `fields` contains its GraphQL field records, including single-select options. Each item has `{id,issue_number,fields:{FIELD_NAME:VALUE}}`. Issue dependency arrays contain their native REST Issue objects with `html_url` and `state`. The importer retains the supplied acquisition time and reports the snapshot hash; an API failure returns an error.

Summary exposes `tasks` once per Issue and `work` once per executable task. Every GitHub task has `title`, `url`, `assignees`, `due_date`, `priority`, `classification`, `progress`, `dependencies` and `links`. A closed Issue or completed Project status enters `completed`; a blocking open dependency or blocked Project/Progress value enters `blocked`; an active Project status or `Progress: In progress` enters `active`; remaining open work enters `next`. Completed rows are ordered by their closing/update time. `--owner` selects the GitHub login. Project priority options and item order supply the execution forecast's derived order; Issues-only `P0`, `P1`, `P2` values use their numeric order. `--priority` produces an explicit comparison. Legacy local priorities are retained in their source bytes. GitHub-bound views use the current GitHub ordering.

`work.execution` exposes local worker state and executable dependencies. `current_completion` and `next_tasks` retain the existing scientific result/receipt and executable DAG predicates. The GitHub Issue's completion and the scientific execution result each retain their respective meanings. `project-impact` returns only the affected scientific results and the corresponding Issue links; resource or deadline changes return schedule Issue links separately.

`--save` writes the derived JSON atomically, without changing the task store. It can replace an existing `artifact_kind:"project-view"` output and preserves canonical plan, source and state paths. The saved view carries source/acquisition identities, the plan binding, current findings, interpretations and decisions. Meeting generation reads this file plus the selected saved result/gallery IDs. Requested meeting destinations are Markdown, Quarto HTML, Beamer PDF and native Google Slides. Refresh the view to incorporate subsequent GitHub edits; make human-task edits at GitHub.

Read the [interface](state.md#interface-github-issues-and-projects) for the exact input forms.

## Explicit GitHub updates

`project-update` edits a linked work Issue or an Issue in the bound Project. Its exact Issue URL must already be declared in the task's `external_targets`. A Project field edit also requires that Project's exact browser URL in the same existing contract. Current contract/context sources, task/ancestor holds and external-target ownership apply. The command uses the existing task lock and leaves the task store and adopted research sources intact.



Issue changes support `title`, `body`, `state`, `state_reason`, `assignees`, `labels` and `milestone`. A milestone is its positive number or `null`; assignees and labels are lists of names. `state_reason` accompanies a state change and uses `completed`, `not_planned`, `reopened` or `null`. `fields` uses existing Project field names: single-select values use a name or ID; iterations use an existing title or ID, including completed iterations; dates use `YYYY-MM-DD`; numbers use finite JSON numbers; text uses strings. `null` clears a supported Project field. Built-in Issue fields use the Issue keys. `blocked_by` replaces the Issue's blocking dependencies with canonical Issue URLs; an empty list removes them.

The command validates all supplied values before writing, compares `--expected-updated-at` with the current Issue when supplied, and executes native [Issue PATCH](https://docs.github.com/en/rest/issues/issues#update-an-issue), [typed Project item edits](https://cli.github.com/manual/gh_project_item-edit), and dependency additions/removals in sequence. The return contains actual operation responses and readback of the changed values. A failed later operation returns `completed_responses` and its error so continuation uses the completed writes. Required execution evidence uses the existing returned-action record. Issue writes require Issues write access; Project edits require `project` scope or the corresponding GitHub App permission.

The explicit update, typed field editing, connector-envelope handling and owner/number selector were adapted from [PR #9, commit 8e5cfd4](https://github.com/yoshimurahiroki/econ-project-mini/commit/8e5cfd4b04fcf9a15faa525cadcacc40c719a4d3) into this project's existing schema and authority paths.

Read the [interface](state.md#interface-explicit-github-updates) for the exact input forms.

## Resumption and migration

Use [TEAM's resumption contract](../runtime/TEAM.md#resumption) with the saved consumed-input, output and governing-definition identities above. Read [State migration](../docs/ai/integration.md#state-migration) only for a requested migration. Read the [compatibility interfaces](#compatibility-interfaces) for retained legacy forms.

For a formerly completed task with no recoverable assessment target versions, preserve its outputs and reconcile the actual requested result and its source versions. Carry any explicitly selected certification through its existing evidence owner. Respect holds and use [TEAM](../runtime/TEAM.md#resumption) for active assignments and continuation context.

## Local state helper

harness/state.py manages task records in the selected root. The active runtime executes worker and tool actions; state commands register their returned results. The selected host or existing producer writes the requested output at its authorized destination. Use an explicit --root or the current working directory. Git is optional. Keep its local store and transcripts out of shared artifacts.

For an authorized store operation, read the helper's --help for the command. Its schema-v5 interface records these distinctions:

- `add` declares the request's requirements before producing results. Operation kinds are `answer|modify|create|external`. Required outputs bind `{role,kind,target}`; actions bind `{target_kind,target_id,operation}`. Keep direct inputs, start-order predecessors, protected sources, authority and holds distinct. Consumes bind `{producer_id,output_id,kind,content_version,definition_versions}` and any required `publication_group_id`. Opaque external IDs are separate from relative file scope. The record is optional; required checks default to empty.
- `output` defaults to a file. Bind its role, or infer it only from one exact kind/target match. `message|object` outputs retain their named value and content identity. Preserve `definition_versions`, a required `publication_group_id` and the local `producer_id` (default: the current task). Dependency pairs `[producer_id,output_id]` narrow consumed edges; explicit `--no-dependencies` clears them, while omission binds all task consumes. Supplementary progress cannot satisfy another role or kind.
- action records an already performed operation using --target-kind, --target-id, --operation, --result and --evidence. A passing object action imports the native returned-tool record from that evidence file and derives its outcome through the existing native adapters. File targets retain their actual content hash, or their missing state for a deletion. Object targets require a registered object output or --target-version from the returned result or readback. Returned GitHub commit and plugin release identifiers must match an explicit target version. Freshness refers to the latest registered result; obtain remote updates through the authorized service and register their versions. Match the declared action target and operation and retain its input/output and result-record versions.
- `verify` imports actual `execution-result` evidence or an explicitly requested `worker-result`; an optional result must agree. Independent review requires the structured worker record and runtime-source match for each selected certification. Receipts bind current input/output versions; input/output selectors can narrow execution-evidence targets. Worker evidence binds the complete candidate and becomes stale when it changes. Match mapped scientific commands to their actual native returns. Transitions and check replacements update the record without duplicate history snapshots; saved history remains readable.
- `transition completed` requires a running task whose required outputs, actions, versions, dependencies and checks match and whose holds are resolved.
- resume retains saved outputs and existing attempt records. requeue --output ID or --producer ID selects the affected branch for recomputation after changed dependencies, preserving unaffected outputs and receipts. Repeated --consumes records replace its upstream input contract and narrow legacy compatibility groups; --no-consumes explicitly clears that contract. A completed task accepts requeue only with an explicit output, producer or consumes selection. For a blocked or failed task without output or producer selectors, requeue removes results stale by bytes or dependencies and preserves current results. A changed selected execution record can be reconciled through resume while reusing matching numerical outputs.
- release-hold requires --hold-id, --authority, --user-release FILE and --next. The saved user instruction has source `user`, nonempty message_id/text and the matching source_task_id/hold_id. Release a hold only on its setting task; a child cannot release an inherited hold. Retain other holds and the original general authority. The coordinator compares the retained instruction with the actual user message; local JSON does not authenticate it. A permission/user-hold transition must identify its hold. Optional repeated --hold-operation and --hold-target values on add/transition narrow its application; targets use `file:relative/path` or `object:exact-id`. Omitted selectors preserve a task-wide hold. After the setting task releases an applicable hold, resume the same child and obtain only its invalidated checks.
- set-contract appends a requirement revision for a queued, blocked or failed task and associates preserved exact results with their declared roles. Additive requirements need no user-change record. Removing or replacing any existing output, action or external target requires --user-change FILE with the exact user instruction and old/new contract hashes. An omitted old requirement is a removal, not implicit permission to drop it. The helper retains the prior snapshot and supplied evidence; it cannot decide whether the quotation really authorized the change.

### Returned action evidence

For a passing object action, save one existing native `action_results_verified` record as the evidence JSON object. Include `event_id`, `operation`, `target`, `status: "success"`, `tool_name`, distinct `tool_call_ref` and `tool_return_ref`, exact `call_args_text` and `return_text`, their UTF-8 SHA-256 values in `call_args_sha256` and `return_sha256`, and the existing `source_verification` runtime-match record. Match the saved bytes and references to the host's actual call and return. The [native operation parser](native_check.py) supplies the registered tool/operation pairing, exact target, error handling and command continuations. The state receipt stores its normalized `operation_outcome` in the existing action record.

GitHub object creation uses `github.create_blob`, `github.create_tree` or `github.create_commit` with target `owner/repository:git/blobs`, `:git/trees` or `:git/commits`. GitHub content writes use `github.create_file`, `github.update_file` or `github.delete_file` with target `owner/repository:contents/PATH`, adding `?ref=BRANCH` for an explicit branch. Each operation retains its actual returned SHA. Use `github.update_ref` with `mcp__codex_apps__github_update_ref` and target `owner/repository:refs/heads/branch`; use `plugin_creator.update_plugin` with its same-named MCP tool and the existing plugin ID. Command actions use `execute_command` and the exact initiating command string. Register the command's actual `write_stdin` continuations until the terminal result. Nonempty input also requires the exact external target `stdin://SESSION/SHA256`, with SHA256 of the UTF-8 chars; polling uses empty input. If the live session identity requires additional authority, block the task, add the exact target through `set-contract`, then resume the same task and process. Re-register its retained returns under the current contract rather than rerunning completed work. A terminal session cannot accept further input or polling. A nonzero exit, returned error, mismatched target, conflicting result branch or running session prevents a passing receipt. Keep a failed operation's return with `--result failed`, repair its cause and register the completed replacement. Existing stored receipts retain their recorded versions; new passing object receipts use the returned-tool contract.

### User-directed contract changes

The user-change JSON object contains source equal to user, a nonempty message_id, the verbatim user text in text, previous_contract_sha256 and replacement_contract_sha256. Both hashes use the JSON encoding above over an object with required_outputs, required_actions and external_targets. show exposes the current contract_revisions snapshot and hash. Array order is retained. Retain the actual user message in the task conversation and compare the saved quotation, identity and scope change with it before importing; hashes bind versions, not authority. A fabricated user label is not authorization.

Revisions retain their complete snapshots and the change file hash. Missing or changed saved change evidence invalidates the contract's current completion assessment. Pre-existing stores without revision history retain their legacy semantics; their first set-contract change records the previous snapshot before appending the new one. Already existing requirements are never inferred from preserved outputs.

### Worker-result evidence

The JSON passed to --worker-result preserves the original return and its runtime references:

- The envelope contains role equal to --check, worker_id equal to --reviewer, distinct launch_ref and return_ref, execution_status equal to completed, return_text, return_sha256, and source_verification. The worker differs from the task owner.
- return_text is the exact original structured JSON object, with schema_version equal to 1, role, candidate_sha256, decision, findings, unassessed, errors and checks. return_sha256 is SHA-256 of its raw UTF-8 text.
- candidate_sha256 uses the JSON encoding above over candidate(task), including task identity, owner, versions, required outputs/actions/checks.
- decision is pass or fail. findings, unassessed and errors are arrays. A pass requires empty arrays, checks[role] equal to passed, and every reported check equal to passed. Preserve resolved finding history in a separate original-object field.
- source_verification has status matched-to-runtime or not-verified. A matched record includes verifier_id and reference identifying the coordinator's actual runtime comparison.

The importer derives the verdict, arrays, checks and candidate reference from return_text and stores that object as worker_result.normalized_return in the receipt. Compatibility copies of substantive fields in the envelope are optional and must match the original JSON exactly, including types. The original evidence file and return_text remain intact. A fail in the original and pass in an envelope or --result is rejected. Missing original fields, duplicate JSON keys, nonfinite values and unstructured legacy returns require a corrected structured return before review registration.

The helper re-parses the saved original on reads and compares it with the normalized receipt, file hash, current candidate and task checks. Changes invalidate the current receipt. Terminal state, role, worker identity and distinct launch/return references are checked across required roles. Source status not-verified remains self-reported and cannot satisfy --independent-review.

The coordinator compares worker references with actual runtime launch and return events. State candidate(task) digests and native-check file-byte digests identify different objects; retain both and their mapping.

Use explicit capacity, depth or attempt limits only when the user or runtime supplies them. For a requested legacy-store conversion, use [State migration](../docs/ai/integration.md#state-migration).

## Find saved work

Use `state.py find QUERY` when the task ID or saved result is unknown. It reads the existing local store and returns candidate IDs, recorded status, owner, immediate parent, matching JSON pointers and short excerpts. Whitespace-separated terms use case-insensitive literal matching; all terms must occur somewhere in the same task. Japanese terms remain searchable without translation. Search covers recorded context, output and evidence references, action results, checks and retained history. File bodies and external services are not searched. A former failed check can match a task whose later check passed; read the pointed original before deciding what that failure means.

Narrow candidates with exact `--parent`, `--owner` or `--status`; parent selects immediate children, and status selects the recorded scheduling state. Pages are ordered by task ID. `--limit` controls the number of candidates (default 5); `--offset` selects the next page. Pass the returned `store_sha256` with `--snapshot` when continuing a page sequence so a changed store causes a fresh search. Each candidate includes at most three matching excerpts, the full match count and the number omitted. These are navigation excerpts; the original source bodies remain intact.

Select a candidate with `state.py show ID`, follow its request, instruction, adopted-decision, result and evidence references, and restore the complete applicable source bodies. The returned pointers address the helper's existing normalized task record; request/rule/decision references retain their original identities, content versions and paths in that record. Use existing show/resume/version checks to compare the current request, inputs, targets, definitions and holds before reusing the result or continuing an operation. A search hit and its recorded status do not certify completion, freshness, permission or applicability. The locator command does not acquire the writer lock, save migrations, replace instructions or create another memory store.

## Local assessment stages

The verify command compares saved task records, candidate versions and check receipts. Use the economist's procedure for the integrated review and EXECUTION for actual destination completion. show (one task or the entire store) and inspect expose completion. An explicitly selected independent certification also exposes its returned evidence:

- completed: the completion contract, results, dependencies and checks are current and holds are resolved. Scheduling and upstream consumption use the status and dependency rules above.
- reviewed: distinct passing worker-result records have recorded runtime-source matches and bind the complete current candidate. They cover every output and required check. review_source is worker-result-evidence, and missing_independent_checks lists required checks without current matched worker evidence. An empty evidence set does not establish review.

Changes to candidate bytes, definitions, requirements, source dependencies or saved check evidence invalidate the affected assessment. Holds also apply. Older receipts without candidate binding retain ordinary completion and reuse behavior but do not establish independent review.

Schema-v5 migration preserves tasks, outputs, contracts, dependencies, check receipts, action results and holds. It discards retired publication records and saved stage flags from the task and its history. Read-only commands derive the migrated view; the next state-writing command persists it. Prior publication records do not establish worker review.

Publication completion follows the actual returned operation and current destination version. The state helper retains the corresponding action result and current artifact dependencies.

## State writer ownership

State updates hold a nonblocking exclusive OS flock on one persistent .lock file from read through atomic save. The descriptor remains open for the update and is closed afterward; process termination releases ownership automatically. Keep the lock file in place so every writer uses the same inode. A competing live writer returns the state path and a retry instruction. Resume from the last complete JSON after the writer exits; never delete and recreate the lock file to bypass a live writer. Save through a newly and exclusively created private temporary file, flush its bytes, then replace the store and flush its directory. Existing temporary-name symlinks and hard links are never opened. The explicit root write scope `.` contains repository-relative descendants and overlaps every descendant write scope.

## Scoped check coverage and requested deletion

Required checks may be ID strings (each applies to every requested target) or {id, targets: [...]} records. Keep scoped receipts per check and target; each required pair needs a current passing receipt. A later current failed verdict shadows an earlier pass for that pair. Changes invalidate only affected target receipts and their actual dependencies. All requested targets must be covered before completion.

For a requested delete/remove/unlink action on a consumed input, bind its input_version to the pinned pre-deletion file hash, actual operation and target, successful evidence and observed absence. This tombstone permits only that requested deletion through input validation. Recreating it or changing another consumed input invalidates affected work; explicit read dependencies remain fixed.

## Adopted specification boundary

Bind an adopted [request contract](requirements_check.md) and its original request when adding a task with `--requirements REQUIREMENTS --request REQUEST`, or use `bind-specification` on an existing queued, blocked or failed task. The state keeps the exact file paths and SHA-256 values in `specification` and its revision history. Replacing an adopted binding uses existing `--user-change` evidence with `previous_specification_sha256` and `replacement_specification_sha256`.

The boundary validates source spans, fixed requirements, declared paths and prohibited operations. Completion follows the requested outputs, actual action returns, dependencies, current versions and selected certification. The economist's procedure owns the integrated review. The state does not execute development checks, rescan the implementation for an audit or create repair tasks automatically. Existing saved check runs remain readable as historical execution evidence.

## Observed execution usage

`state.py usage` deduplicates cumulative observations.

Import actual app-server notifications or typed usage events through the existing usage command:



The app-server adapter consumes `thread/tokenUsage/updated` with `params.threadId`, `turnId` and `tokenUsage.total`; it retains `last` alongside the cumulative observation. A typed event has `type:"usage.observed"`, `source_id`, `session_id`, optional `turn_id`, stable `event_id`, and `counters` using `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, `reasoning_output_tokens`. Retain `metadata.requested` and `metadata.observed` model, effort and agent fields separately. Optional `resources` records event-scoped tool calls, retries, auxiliary calls, failure loops, human corrections and duration; declare `resource_scope:"event"` for attributable subtotals.

Sequence zero identifies the captured cumulative epoch start. Preserve its epoch through continuation and start a new epoch for a reset. Stable event identities deduplicate imports across tasks; conflicting identities, source overlap, missing delta event IDs, an unknown cumulative baseline or a decreasing counter prevent totals for that affected group. Input includes cached input; output includes reasoning output. Unknown counters remain `null`, reported zero remains zero, and cached/reasoning details stay within their enclosing totals. Reported resource subtotals retain their observed coverage. Session completion, current runtime model and subscription allowance consumption follow the actual host returns.

An epoch label records a counter reset; stable producer identity persists across labels. Importing the same stable event or exact legacy source observation under another epoch is rejected. Existing overlapping records remain intact and expose the overlap with affected totals set to `null`. Distinct stable event IDs and distinct recorded reset evidence retain their separate observations. Codex 0.159.2's `turn.completed.usage` emits the latest thread total and uses default zeros when its upstream usage notification is absent; the legacy importer retains cumulative semantics and its existing zero-counter checks. Retain `tokenUsage.last` with `total` when the app-server supplies both.

Use actual model-usage returns for token and cache comparisons. Tool-output byte counts, approximate display-token estimates and wrapper execution time describe their own operations. Keep the standard host compaction settings until a comparable completed-task measurement establishes lower actual total tokens and elapsed time with instruction adherence, correctness and completion preserved.

`--counter-mode observation --source-format usage-event` records typed operational events with token counters absent. Existing imported observations retain command phases, actual terminal outcomes and source hashes in the `usage` field. These observations preserve output/check versions, remain outside numerical token aggregation and carry their source-verification status. Full instructions are restored from the governing task and applicable source bodies when required; metadata-only usage changes preserve an already delivered same-version packet. Inspect actual callback, delivery and source-reading evidence when assessing a host.

Read the [interface](state.md#interface-observed-execution-usage) for the exact input forms.

## Read retained research logs

For an unresolved implementation location, use `rg` at the existing owner. The registered [context packer](../scripts/pack_context.sh) also accepts `--map --query EXACT_IDENTIFIER --root PROJECT_ROOT --limit 80` with relevant paths when definition, import or caller locations resolve the pending lookup. Retrieve the selected source before editing.

Read a saved research execution through the existing helper:



Page with `--offset` and use `--view log` for the saved bounded diagnostic. The research execution output retains its byte count and truncation status. Displayed credential-bearing lines are redacted while the diagnostic stays in its authorized private record.

Read the [interface](state.md#interface-read-retained-research-logs) for the exact input forms.

## Paragraph state binding

Bind a saved ParagraphRun with `state.py bind-writing TASK --paragraph-state RELATIVE_PATH`. The binding records its bytes, request, blueprint, rule and paragraph versions; changed state invalidates completion evidence. Use [paragraph.py](paragraph.py) to preserve unaffected text and requeue changed source or specification consumers. Resume with the full current instruction packet. The state binding records execution; it does not replace native final review.

## Compatibility interfaces

existing explicit `--operation-kind answer` contracts remain supported.

The legacy evaluating and interrupted names map to running and blocked.

an untyped legacy graph retains its existing impact API.

## Interface: Project work

```sh
python harness/state.py --root PROJECT project-bind CASE --definition plan-v1.json
python harness/state.py --root PROJECT project-view CASE --role contribute --owner PERSON --view summary
python harness/state.py --root PROJECT project-view CASE --role manage --view story
python harness/state.py --root PROJECT project-view CASE --role manage --view workplan
python harness/state.py --root PROJECT project-view CASE --role manage --view forecast --project OTHER_CASE
python harness/state.py --root PROJECT project-impact CASE --node CLAIM_ID
```

## Interface: GitHub Issues and Projects

```json
{
  "github": {
    "repository": "OWNER/REPO",
    "project_id": "PVT_PROJECT_NODE_ID",
    "issue_template": "research-task.yml",
    "fields": {"status":"Status", "priority":"Priority", "due_date":"Due date", "classification":"Classification", "progress":"Progress"},
    "status_groups": {"completed":["Done"], "active":["In Progress"], "next":["Todo"], "blocked":["Blocked"]}
  },
  "work": [{"task_id":"ESTIMATE", "node_ids":["CLAIM"], "duration_hours":2, "resources":{},
            "issue_number":12, "artifact_ids":{"results":["RESULT_ID"], "figures":["FIGURE_ID"], "documents":["DOCUMENT_ID"]}}]
}
```

```sh
python harness/state.py --root PROJECT project-view CASE --role manage --view summary --save project-summary.json
python harness/state.py --root PROJECT project-view CASE --role contribute --owner GITHUB_LOGIN --view workplan
python harness/state.py --root PROJECT project-view CASE --role manage --view summary --github github-read.json --save project-summary.json
```

```json
{
  "schema_version":1,
  "repository":"OWNER/REPO",
  "fetched_at":"2026-11-05T12:00:00Z",
  "source":"connector tool and returned read identity",
  "issues":[{"number":12,"title":"Inspect saved result","html_url":"https://github.com/OWNER/REPO/issues/12",
             "state":"open","assignees":[{"login":"PERSON"}],"body":"### Priority\n\nP1\n\n### Progress\n\nIn progress",
             "updated_at":"2026-11-05T12:00:00Z","closed_at":null,"blocked_by":[],"blocking":[]}],
  "project":null
}
```

## Interface: Explicit GitHub updates

```sh
python harness/state.py --root PROJECT project-update CASE \
  --issue-url https://github.com/OWNER/REPO/issues/12 \
  --expected-updated-at 2026-11-05T12:00:00Z \
  --changes '{"assignees":["PERSON"],"fields":{"Status":"In Progress","Due date":"2026-11-20","Iteration":"Iteration 2"}}'
```

## Interface: Observed execution usage

```sh
python harness/state.py --root . usage TASK --jsonl observed.jsonl \
  --source-format codex-app-server --counter-mode cumulative --epoch EPOCH --sequence 0
python harness/state.py --root . usage TASK --jsonl observed.jsonl \
  --source-format usage-event --counter-mode delta --epoch EPOCH --sequence 0
python harness/state.py --root . summary
```

## Interface: Read retained research logs

```sh
python harness/codex_hooks.py --root . focus-research TASK --limit 100
```

## Project allocation interface

Use existing `project-view --view forecast` for feasibility and `project_judgment` for the adopted comparison, sources, order and authority. On determining changes, use `project-impact` to update affected decisions and consumers.
