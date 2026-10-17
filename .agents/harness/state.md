# State, consumed dependencies and resumption

Use only when durable state, saved-result reuse or resumption is needed. Inherit [CORE](../runtime/CORE.md) and the [completion contract](../runtime/EXECUTION.md#checks-and-completion). Ordinary answers need no local store.

## State and version contract

Represent this task record in an existing store or conversation when tracking or resumption needs it. The local helper described below implements the file-backed form; ordinary answers need no state file.

- task_id, parent_id, owner: identify the task, parent dependency and one result owner.
- operation_kind: answer, modify, create or external.
- status: queued, running, blocked, completed or failed.
- blocked_reason: dependency, user_hold, interrupted or permission; present only while blocked.
- read_dependencies: protected inputs and versions that the operation may not change.
- consumed_inputs: the exact direct input versions consumed by each operation.
- after: preceding task IDs controlling start order only; never implicitly consume all their outputs.
- consumes: explicit producer_id, output_id, kind, content_version and definition_versions records; include publication_group_id only for outputs required to be published together.
- required_outputs: requested role, kind (file, message or object) and exact target for each deliverable.
- required_actions: target kind, target identifier and operation for each requested action.
- outputs: registered role, file/message/object identifier, resulting content version, adopted definition_versions, local producer_id and any required publication_group_id.
- action_results: returned results of performed actions, with target identities, assessed versions and result records.
- write_scope: authorized relative file targets, when applicable; external_targets holds exact external object identifiers separately.
- required_checks: identifiers of the task's applicable checks; empty when none apply.
- check_receipts: check operation, target input versions, target output versions and returned result.
- authority, holds, next_action: current scope, preserved stops and the next authorized operation while unfinished.

Use the existing runner's dependency graph as canonical. Record only actually consumed artifacts and meaning-determining definitions such as sample, measurement and estimand. A changed consumed definition invalidates its users even when numerical bytes match. An unused parent output change preserves the child and its matching check receipts. A required publication group binds outputs that must be current together. A skill-index or style-rule version alone is not a numerical dependency; connect recomputation to the inputs, code, definitions and environment actually used.

Use content hashes to identify file contents; keep path and content identity distinct. Use stable message or object identifiers and a version or content identity sufficient to distinguish revisions. Git identifiers may supplement content identity when available; their absence does not make an input unusable.

For an in-place modification, retain the pre-change version as consumed input and the post-change version as output. Do not require the current output bytes to equal the pre-change bytes. Protected read dependencies must remain preserved. A change to a protected input is a conflict to resolve within authority.

## Resumption and migration

Restore saved artifacts and compare their versions and governing definitions. Recover the last consumed input and output identities before deciding which work remains. Preserve original records and outputs. Read [State migration](../../docs/ai/integration.md#state-migration) only for a requested migration.

For a formerly completed task with no recoverable assessment target versions, preserve its outputs and perform only missing required checks against identified current versions. Do not rerun the original calculation merely because its old record lacks receipt metadata. Respect holds and use [TEAM](../runtime/TEAM.md#resumption) for active assignments and continuation context.

## Local state helper

The local helper is harness/state.py. It manages records in the selected root and does not launch workers, execute their actions or grant permissions. Use an explicit --root or the current working directory. Git is optional. Keep its local store, transcripts and authenticated settings out of shared artifacts.

For an authorized store operation, read the helper's --help for the command. Its schema-v4 interface records these distinctions:

- add accepts --operation-kind answer|modify|create|external and one or more --required-output JSON records with role/kind/target or --required-action records with target_kind/target_id/operation. Declare requirements from the request before producing results. --record is optional. Repeated --input values identify direct consumed sources; --after records start order only. Repeated --consumes JSON records bind specific upstream outputs using producer_id, output_id, kind, content_version and definition_versions, plus publication_group_id when joint publication is required; --read-dependency identifies protected sources. --required-check defaults to empty. Carry authority and identified holds; use --external-target for opaque external IDs independently of relative file scope.
- output records a file path by default. --role associates it with the declared requirement; an omitted role is inferred only from an exact unambiguous kind and target. --kind message|object with --value records the named result and content identity. Use --definition-versions JSON for meaning-determining definitions, --publication-group-id for a required joint group, and --producer-id for a local producer label (default: task). Use repeated --dependency JSON pairs [producer_id, output_id] to narrow the consumed edges of this result, or --no-dependencies for a result independent of task consumes; omission binds all task consumes. Supplementary progress outputs do not satisfy another role or kind.
- action records an already performed operation using --target-kind, --target-id, --operation, --result and --evidence. It records the returned result; it does not perform an external action. File targets retain their actual content hash, or their missing state for a deletion. Object targets require a registered object output or --target-version from the returned result or readback. Freshness refers to the latest registered result; obtain remote updates through the authorized service and register their versions. Match the declared action target and operation and retain its input/output and result-record versions.
- verify records --check, --result and --reviewer. --evidence is optional. A receipt binds current input and output versions; --input and --output can select the actual targets so unrelated outputs keep their valid receipts.
- transition completed applies to a running task whose required outputs, actions, versions, dependencies and checks match and whose holds are resolved. The legacy evaluating and interrupted names map to running and blocked.
- resume retains saved outputs and attempt history. requeue --output ID or --producer ID selects the affected branch for recomputation after changed dependencies, preserving unaffected outputs and receipts. Repeated --consumes records replace its upstream input contract and narrow legacy compatibility groups; --no-consumes explicitly clears that contract. A completed task accepts requeue only with an explicit output, producer or consumes selection. For a blocked or failed task without output or producer selectors, requeue removes results stale by bytes or dependencies and preserves current results. A changed check log can be resolved by resume and the affected check without recomputing outputs.
- release-hold requires --hold-id, --authority and --next, removes only that identified hold and retains all other holds. A permission/user-hold transition must identify its hold. The governing instruction supplies release authority; a stored reference records that instruction.
- set-contract supplies explicit required outputs/actions for a queued, blocked or failed task, associates preserved exact results with their declared roles and keeps unrelated requirements unresolved.

Use explicit capacity, depth or attempt limits only when the user or runtime supplies them. For a requested legacy-store conversion, use [State migration](../../docs/ai/integration.md#state-migration).
