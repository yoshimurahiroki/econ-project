# State, consumed dependencies and resumption

Use only when durable state, saved-result reuse or resumption is needed. Inherit [CORE](../runtime/CORE.md) and the [completion contract](../runtime/EXECUTION.md#checks-and-completion). Ordinary answers need no local store.

## State and version contract

Represent this task record in an existing store or conversation when tracking or resumption needs it. The local helper described below implements the file-backed form; ordinary answers need no state file.

- task_id, parent_id, owner: identify the task, parent dependency and one result owner.
- operation_kind: answer, modify, create or external.
- status: queued, running, blocked, completed or failed. This remains the scheduling state; completed never means published.
- stages: read-time completed, self_checked and reviewed assessments on show and inspect, derived from current task data and check receipts.
- blocked_reason: dependency, user_hold, interrupted or permission; present only while blocked.
- read_dependencies: protected inputs and versions that the operation may not change.
- consumed_inputs: the exact direct input versions consumed by each operation.
- after: preceding task IDs controlling start order only; never implicitly consume all their outputs.
- consumes: explicit producer_id, output_id, kind, content_version and definition_versions records; include publication_group_id only for outputs required to be published together.
- required_outputs: requested role, kind (file, message or object) and exact target for each deliverable.
- required_actions: target kind, target identifier and operation for each requested action.
- contract_revisions: retained initial and subsequent requirement snapshots, hashes and source evidence. A new contract does not erase the old one.
- outputs: registered role, file/message/object identifier, resulting content version, adopted definition_versions, local producer_id and any required publication_group_id.
- action_results: returned results of performed actions, with target identities, assessed versions and result records.
- write_scope: authorized relative file targets, when applicable; external_targets holds exact external object identifiers separately.
- required_checks: identifiers of the task's applicable checks; empty when none apply.
- check_receipts: check operation, target input/output versions, result and evidence class. Self-checks are separate from candidate-bound worker-result evidence.
- authority, holds, next_action: current scope, preserved stops and the next authorized operation while unfinished.

Use the existing runner's dependency graph as canonical. Record only actually consumed artifacts and meaning-determining definitions such as sample, measurement and estimand. A changed consumed definition invalidates its users even when numerical bytes match. An unused parent output change preserves the child and its matching check receipts. A required publication group binds outputs that must be current together. A skill-index or style-rule version alone is not a numerical dependency; connect recomputation to the inputs, code, definitions and environment actually used.

Use content hashes to identify file contents; keep path and content identity distinct. Message and object values use SHA-256 of UTF-8 json.dumps(value, sort_keys=True, ensure_ascii=False), with Python's default separators, both at registration and on reads. A stored value/hash mismatch invalidates completion, checks, review and consuming dependencies. Git identifiers may supplement content identity when available; their absence does not make an input unusable.

For an in-place modification, retain the pre-change version as consumed input and the post-change version as output. Do not require the current output bytes to equal the pre-change bytes. Protected read dependencies must remain preserved. A change to a protected input is a conflict to resolve within authority.

## Governing context

The existing task record can retain `task_context` with exactly `request_refs`, `goal_and_constraints`, `active_instruction_refs` and `adopted_decisions`. Register it with `add --task-context FILE`. Request references use source_id, version and content_sha256; instruction references use rule_id, version, section and content_sha256. Each may include a root-relative path whose bytes must match the hash. Versions are nonempty strings or nonnegative integers. Each adopted decision has decision_id, version, choice, reason and switch_condition. goal_and_constraints is the existing substantive brief as text. Reference the pinned common contract among the request records when it governs required outputs/actions; derive the existing required_outputs/required_actions declarations from that contract. The local state record does not authenticate user authority.

`context_id` binds this content, authority, holds, declared requirements/scope and the recorded content hash. Candidates and check receipts share it. It excludes Git display revisions, time, progress status and next-action display text. `outputs`, `consumes` and `next` remain the sole completed-result and continuation records. No duplicate completed_refs or next-action ledger is created.

A child's file scope and external targets must fit every ancestor's assigned bounds. Omitted authority and task context inherit from the parent; an explicit child declaration still retains the ancestor constraints. `effective_constraints_sha256`, `effective_holds` and `inherited_authority` are derived from the setting tasks and bind the child's candidate and check context. Check them again at start/resume and before accepting current results. A changed applicable parent hold or governing context blocks an active/completed child, invalidates its assessments, and preserves its output bytes. An unused parent output or an unrelated scoped hold does not invalidate the child. Parent context changes propagate to children that inherited that context; explicit child context remains subject to the current ancestor context.

Resume compares record bytes, retained context and current referenced content. A changed context or record blocks resume and old assessments; outputs remain saved. Stop the active task, reconcile an authorized context change with `set-context ID --task-context FILE`, or use requeue to refresh a changed substantive record. Recheck affected judgments against preserved outputs. A prose-rule/context update alone does not remove numerical results or alter consumed numerical definitions. Numerical recomputation follows the existing input/definition dependency rules. Current context can be supplied to start/resume with --task-context; a different governing version must first be registered. Permission/user holds still require the existing explicit release-hold operation.

Older receipts lacking context_id cannot establish a current context-bound check; retain their outputs and obtain only the missing assessment.

## Resumption and migration

Restore saved artifacts and compare their versions and governing definitions. Recover the last consumed input and output identities before deciding which work remains. Preserve original records and outputs. Read [State migration](../docs/ai/integration.md#state-migration) only for a requested migration.

For a formerly completed task with no recoverable assessment target versions, preserve its outputs and perform only missing required checks against identified current versions. Do not rerun the original calculation merely because its old record lacks receipt metadata. Respect holds and use [TEAM](../runtime/TEAM.md#resumption) for active assignments and continuation context.

## Local state helper

harness/state.py manages task records in the selected root. The active runtime executes worker and tool actions; state commands register their returned results. [Native run](native_run.py) finalizes candidate files into a local output directory. Use an explicit --root or the current working directory. Git is optional. Keep its local store and transcripts out of shared artifacts.

For an authorized store operation, read the helper's --help for the command. Its schema-v5 interface records these distinctions:

- add accepts --operation-kind answer|modify|create|external and one or more --required-output JSON records with role/kind/target or --required-action records with target_kind/target_id/operation. Declare requirements from the request before producing results. --record is optional. Repeated --input values identify direct consumed sources; --after records start order only. Repeated --consumes JSON records bind specific upstream outputs using producer_id, output_id, kind, content_version and definition_versions, plus publication_group_id when joint publication is required; --read-dependency identifies protected sources. --required-check defaults to empty. Carry authority and identified holds; use --external-target for opaque external IDs independently of relative file scope.
- output records a file path by default. --role associates it with the declared requirement; an omitted role is inferred only from an exact unambiguous kind and target. --kind message|object with --value records the named result and content identity. Use --definition-versions JSON for meaning-determining definitions, --publication-group-id for a required joint group, and --producer-id for a local producer label (default: task). Use repeated --dependency JSON pairs [producer_id, output_id] to narrow the consumed edges of this result, or --no-dependencies for a result independent of task consumes; omission binds all task consumes. Supplementary progress outputs do not satisfy another role or kind.
- action records an already performed operation using --target-kind, --target-id, --operation, --result and --evidence. The coordinator matches the recorded evidence to the actual tool return, operation and target. File targets retain their actual content hash, or their missing state for a deletion. Object targets require a registered object output or --target-version from the returned result or readback. Freshness refers to the latest registered result; obtain remote updates through the authorized service and register their versions. Match the declared action target and operation and retain its input/output and result-record versions.
- verify without --worker-result records a self-check using --check, --result and --reviewer; --evidence is optional for a self-check. A name and passing verdict cannot establish independent review. --worker-result FILE imports the structured returned record described below and derives the verdict from its decision. An optional --result must agree. --independent-review tasks require this evidence and its recorded runtime-source match for every required check. All receipts bind current input/output versions; --input and --output can narrow self-check targets so unrelated results retain their receipts. Worker results also bind the complete candidate and become stale when it changes.
- transition completed applies to a running task whose required outputs, actions, versions, dependencies and checks match and whose holds are resolved. The legacy evaluating and interrupted names map to running and blocked.
- resume retains saved outputs and attempt history. requeue --output ID or --producer ID selects the affected branch for recomputation after changed dependencies, preserving unaffected outputs and receipts. Repeated --consumes records replace its upstream input contract and narrow legacy compatibility groups; --no-consumes explicitly clears that contract. A completed task accepts requeue only with an explicit output, producer or consumes selection. For a blocked or failed task without output or producer selectors, requeue removes results stale by bytes or dependencies and preserves current results. A changed check log can be resolved by resume and the affected check without recomputing outputs.
- release-hold requires --hold-id, --authority, --user-release FILE and --next. The saved user instruction has source `user`, nonempty message_id/text and the matching source_task_id/hold_id. Release a hold only on its setting task; a child cannot release an inherited hold. Retain other holds and the original general authority. The coordinator compares the retained instruction with the actual user message; local JSON does not authenticate it. A permission/user-hold transition must identify its hold. Optional repeated --hold-operation and --hold-target values on add/transition narrow its application; targets use `file:relative/path` or `object:exact-id`. Omitted selectors preserve a task-wide hold. After the setting task releases an applicable hold, resume the same child and obtain only its invalidated checks.
- set-contract appends a requirement revision for a queued, blocked or failed task and associates preserved exact results with their declared roles. Additive requirements need no user-change record. Removing or replacing any existing output, action or external target requires --user-change FILE with the exact user instruction and old/new contract hashes. An omitted old requirement is a removal, not implicit permission to drop it. The helper retains the prior snapshot and supplied evidence; it cannot decide whether the quotation really authorized the change.

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

The coordinator compares worker references with actual runtime launch and return events. State candidate(task) digests and native-check file-byte digests identify different objects; retain both and their mapping. Tests exercise synthetic saved records.

Use explicit capacity, depth or attempt limits only when the user or runtime supplies them. For a requested legacy-store conversion, use [State migration](../docs/ai/integration.md#state-migration).

## Local assessment stages

The verify command compares saved task records, candidate versions and check receipts. Use [CONTROL](../runtime/CONTROL.md) for candidate review and native finalization. show (one task or the entire store) and inspect expose these assessments:

- completed: the completion contract, results, dependencies and checks are current and holds are resolved. Scheduling and upstream consumption use the status and dependency rules above.
- self_checked: current caller-recorded checks cover every output and required check. Receipts with unchecked worker-source references remain in this class.
- reviewed: distinct passing worker-result records have recorded runtime-source matches and bind the complete current candidate. They cover every output and required check. review_source is worker-result-evidence, and missing_independent_checks lists required checks without current matched worker evidence. An empty evidence set does not establish review.

Changes to candidate bytes, definitions, requirements, source dependencies or saved check evidence invalidate the affected assessment. Holds also apply. Older receipts without candidate binding retain ordinary completion and reuse behavior but do not establish self_checked or reviewed.

Schema-v5 migration preserves tasks, outputs, contracts, dependencies, check receipts, action results and holds. It discards retired publication records and saved stage flags from the task and its history. Read-only commands derive the migrated view; the next state-writing command persists it. Prior publication records do not establish worker review.

Publication completion is recorded by native_run's finalized local output, separately from task scheduling and review. The state helper neither publishes files nor stores a publication identifier. Native review records state which checks passed and which runtime-source comparisons were recorded.

## State writer ownership

State updates hold a nonblocking exclusive OS flock on one persistent .lock file from read through atomic save. The descriptor remains open for the update and is closed afterward; process termination releases ownership automatically. Keep the lock file in place so every writer uses the same inode. A competing live writer returns the state path and a retry instruction. Resume from the last complete JSON after the writer exits; never delete and recreate the lock file to bypass a live writer. Save through a newly and exclusively created private temporary file, flush its bytes, then replace the store and flush its directory. Existing temporary-name symlinks and hard links are never opened. The explicit root write scope `.` contains repository-relative descendants and overlaps every descendant write scope.

## Scoped check coverage and requested deletion

Required checks may be ID strings (each applies to every requested target) or {id, targets: [...]} records. Keep scoped receipts per check and target; each required pair needs a current passing receipt. A later current failed verdict shadows an earlier pass for that pair. Changes invalidate only affected target receipts and their actual dependencies. All requested targets must be covered before completion.

For a requested delete/remove/unlink action on a consumed input, bind its input_version to the pinned pre-deletion file hash, actual operation and target, successful evidence and observed absence. This tombstone permits only that requested deletion through input validation. Recreating it or changing another consumed input invalidates affected work; explicit read dependencies remain fixed.
