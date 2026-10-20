# Native research run

Use `native_run.py` to pin a task, assess immutable candidate snapshots and publish only host-authorized strict results. Draft production is available without publication authority.

## Select the review plan

`strict-reviewed` is the default. It requires independent original-request coverage, quality-a, quality-b and compliance. Both quality workers inspect the complete candidate and all 22 B25–B31/C01–C15 judgments, resolve every occurrence under the pinned 142-rule dictionary and preserve source meaning. They fix their judgments independently before seeing the other return. Compliance checks operations, actual reviews and the exact final version. Missing capability never changes this plan or becomes a passing return.

An explicit `direct` or `focused` bounded plan remains available for drafting and diagnosis; `full` retains its prior three-role record format for diagnosis. None authorizes publication. Bounded plan files retain their exact scope and original request-evidence fields. The strict-reviewed/full plan file contains only `schema_version: 1` and `plan`. Self-checks are labeled as author assessments and cannot satisfy independent approval.

Record consistency, hashes, worker-ID strings and caller-supplied `source_verification` are not authenticated evidence. The common `native_check.assert_release_predicates` requires the complete check, exact request/contract/policy/candidate/artifact/submission bindings, schema-3 bidirectional coverage and the adopted host verification route. Host-authenticated verification independently retrieves actual events; the explicitly authorized Site host-observed route retains direct submissions and coordinator comparison without authenticating worker identity. No CLI argument, JSON field or environment variable installs a verifier. The local connection is unavailable by default; the result remains `blocked-unapproved` with causes and next actions. Never invent a verifier, key, trust setting or worker event to obtain success.

## Begin and fix original-request coverage

```sh
python harness/native_run.py begin --run-dir run-001 \
  --request request.txt --requirements requirements.json --author-id actual-executor-id \
  --operation econ-writing:compose --capabilities capabilities.json
```

The first call writes run schema 2 and generates a fresh canonical UUIDv4 `run_id` and saves the request, contract, selected policy, capabilities, and mode. Identical inputs in two new directories produce different run identities and hashes. Resuming preserves the identity. Schema-1 runs require a new begin and fresh review originals. The existing request, contract, candidate and snapshot hashes bind revisions; no parallel revision counter is used. The contract must use integer `schema_version: 2`. New begins, saved-run reads, resumes, submissions, and finalizations enforce that version. Run `requirements_check.py` for a v1 diagnostic, migrate the contract to v2, then start a new run.

`--operation` names the registered operation. Use repeatable `--condition` values to select active conditions, `--profile` for a registered prose-profile resource ID, and repeatable `--template` values for registered template resource IDs. The runner verifies the mandatory registry and resolver bytes, resolves the dependency closure, and reads only mandatory assets and the selected closure. It saves the selection, active rule IDs, resource sections, asset paths, and hashes. Changing the selection starts a new run.

In strict mode, begin without a coverage return reports `blocked` with `obtain-requirements-coverage`. Give the coverage worker both the original request and the proposed contract before producing the candidate. Match its actual launch and return references, then record its structured return:

```sh
python harness/native_run.py begin --run-dir run-001 --coverage-review coverage.json
```

The coverage envelope retains role, actual worker_id, completed execution_status, return_ref, source_verification, exact return_text and return_sha256. Under direct, review_kind is self-check, worker_id equals author_id and source verification is self-check by that author. Under focused/full/strict-reviewed, review_kind is independent, the worker differs from author_id and launch/return references are distinct actual events. The same assigned worker can later audit request–candidate consistency, with prior request exposure recorded; it cannot be labeled request-unread comprehension. For independent coverage, both event references must differ from every candidate review's launch and return references, including cross-kind comparisons. Submit and finalize reject event-reference reuse between these stages.

Independent `source_verification` has `status: matched-to-runtime`, a `reference`, and `verifier_id`; direct uses status self-check, a reference and the actual author as verifier_id. `return_text` is the worker's exact JSON original, with:

- `schema_version: 3`, `role: requirements-coverage`, `decision: pass` for publication. Schema 2 remains draft diagnosis only.
- `run_id` copied from this run’s begin result.
- `request_sha256`, `contract_sha256`, and `policy_manifest_sha256` copied from the matching begin result.
- Empty `findings`, `unassessed`, and `errors` arrays.
- `coverage_rows`, replacing the two former pass flags. Rows partition the entire original request in source order, including whitespace, with no gap or overlap.

Each coverage row contains exactly `id`, `start`, `end`, `source_quote`, `kind`, and `requirement_ids`. IDs are unique; offsets count decoded Unicode characters with an exclusive end; the quote equals the exact request slice. An `obligation` row links one or more distinct IDs in the frozen contract. The linked contract source spans cover every non-whitespace character of that row. Every contract ID is linked, and at least one exact occurrence of each linked contract source is covered by its obligation rows. This rejects a whole-request row whose only linked requirement quotes an earlier sentence while omitting a later instruction. A `non-obligation` row has no requirement IDs and adds a nonempty `rationale` explaining why the source span is context rather than a requested obligation.

Schema 3 obligation rows additionally contain `classifications` drawn from `output`, `content`, `prohibition`, `action`, `authority` and `completion`. The original return also includes one `independent_extraction` comparison with the source-ledger hash, every contract requirement's class, forward row-to-requirement links, reverse requirement-to-row links, explicit non-obligation decisions and no ambiguities. Reuse the common quoted source ledger rather than copying the request into every comparison. See [requirements check](requirements_check.md) for the exact shape. The local helper checks both directions and original positions but never authenticates the extractor or semantic coverage; the host verifier must observe its independent actor and pre-candidate, original-only inputs.

The wrapper hashes and parses the original return; mirrored fields must match its JSON values and types. Import passing request coverage before the first candidate. When an actual worker changes, append replacement coverage with the current context hash.

`capabilities.json` contains unique disjoint `available` and `unavailable` arrays. Optional assignments contain worker_id, roles, launch_ref and matched-to-runtime source_verification. The selected registry plan determines required capabilities. Draft direct requires no independent-worker capability and has no publication authority. Recorded valid returns fulfill local record checks; authenticated host observations or an explicitly authorized host-observed Site receipt/match adapter are separately required for publication; remaining unavailable/unknown assignments appear in needed_actions.

Control assignments keep `assignment_kind: control-review` (the compatible default) and their registered roles. A support assignment uses `assignment_kind: support`, its actual worker/launch binding, a support role, `assignment_id`, `parent_task_id`, `parent_requirement_ids`, `assigned_result`, `input_versions`, `adopted_choice_ids`, `authority_and_holds` and `required_checks`. Its fixed input versions include request.txt and requirements.json plus consumed original sources. A support original repeats those bindings, worker_id and launch_ref, and returns schema_version 1, a nonempty result and source_refs with exact original path/hash/start/end/text. The hook checks input bindings, original-return identity and required original-source passages; other required checks must have executed successfully. Support completion never counts as independent quality approval or completes the parent's unrelated requirements. Effective parent authority and holds remain enforced by the bound task state.

Recover capacity in the same run:

```sh
python harness/native_run.py begin --run-dir run-001 \
  --capabilities current-capabilities.json --expected-record-sha256 CURRENT_HASH
```

An actual author replacement adds `--author-id ACTUAL_SUCCESSOR` and an author assignment in that capability record. Append-only numbered records bind their predecessor and payload hashes; concurrent writers compare the same context hash and one must reload after a conflict. Fixed request, contract, policy, review plan and mode stay unchanged. Reuse completed work and replace the affected actor's assessments. Return flags continue to record the checker’s actual provenance and release state.

Resource reads use the same run records: `begin --run-dir RUN --resource-reads reads.json --expected-record-sha256 HASH`. The JSON has schema_version: 1 and reads rows with reader_id, resource_id, sha256 and sections. Use the adopted resource hash and selected section IDs, or `["all"]` for a whole resource. The returned resource_reads cache combines matching reader/resource/hash entries. Record completed reading only and reuse it across support entries. Changing read bookkeeping preserves fixed input bindings and completed checks.

## Submit and review a snapshot

```sh
python harness/native_run.py submit --run-dir run-001 \
  --candidate final.txt --artifacts artifacts --events events.json
```

Submit directly runs requirement checks, dictionary scanning, and returned-review checks. It saves the candidate, artifacts, events, text-view mapping, exact review originals, and computed results as one content-addressed submission. The returned `submission_sha256` identifies that complete snapshot; `candidate_file_sha256` identifies only final.txt.

`submit --surface final|progress|status|error` (Python `submit_run(..., surface=...)`) binds the exact outgoing surface to this run. The default is final. Nonfinal snapshots retain their surface and expose the native `surface_check`; parent completion requirements remain pending. Nonfinal review consistency never authorizes final-task publication. `current_status` rechecks saved bytes, adopted policy and any task-state binding, then reuses a check only for identical consumed-input and checker hashes. Read bookkeeping does not change that dependency key. A changed dependency reruns the checker and replaces its disposable current-check cache; finalization always reruns the complete checks and publication predicate.

The shared instruction packet separates fixed original-request/adopted-rule text from current stage, unmet IDs and next actions. Normal status and per-tool reminders retain the canonical short text and direct references. Begin/resume, submit and finalization restore the saved request and actual adopted rule bodies through the same canonical API. `current_status(..., restore_instructions=True)` and `status --restore-instructions` request that same restoration, including during compaction recovery; they do not change the request, judgments or approval state. Restoration metadata carries hashes and ranges rather than another copy of the full bodies.

Original `--sources` snapshots preserve exact raw bytes, including non-UTF8 Stata and Parquet calculation inputs. Register those inputs as `input-file` with id, source_kind, source_path, source_sha256 and size_bytes in the existing evidence_sources ledger. Text evidence and pinned processing code are separately UTF-8 validated when used. The raw input hashes remain part of the fixed run files and sources_sha256; changing an input cannot reuse a calculation or review bound to its prior bytes. File-bound numeric derivations and typed PDF extraction bind raw input-file premises to actual processing; direct source-observation and logical/comparison claims use their extracted original propositions.

To add evidence acquired or computed after begin, pass `--evidence evidence-dir` to submit (Python: `submit_run(..., evidence=...)`). Keep the original request, authority, adopted policy and begin sources unchanged. The directory contains manifest.json with `{schema_version: 1, run_id: <fixed run UUID>, evidence_sources: [...]}` and UTF-8 evidence body files. Their logical source paths are evidence/<relative-path>. Use the provenance and typed derivation schema in [native check](native_check.md). Each added evidence row binds its ID, kind, exact content hash/span, actual tool call/return and input premises. Acquisition uses the selected-document, batched web open/click/reference, Library and PDF extraction adapters described in native check. Retain actual tool names, called source identities and exact return spans; keep discovery snippets and unread/access-page content in the search frontier rather than treating them as claim evidence. The evidence manifest run_id must match the current run, including direct checker invocation. The submission captures this directory together with the candidate and artifacts; finalization rechecks the saved snapshot, not later external files.

Pass the same evidence directory on the report-bearing resubmission. Reviewers inspect the complete original-plus-added evidence set and mirror registered evidence_sources rows. Their sources_sha256 includes the new manifest and body bytes. Changed evidence invalidates reviews bound to the earlier set; retain earlier submissions and obtain affected new returns. Numeric derivation binds premises to the executed command and returned calculation result. Its result_span must identify the complete corresponding quantity; result 3 cannot match a substring of 30, -3, 3.0 or 3e9. Logical and comparison derivations bind premises to a concrete inference or choice comparison without requiring a numeric result.

Give the saved candidate, this run’s `run_id`, and matching hashes to actual reviewers. Every candidate review original must contain the exact `run_id` returned in `checks.bindings`; a transport-only ID does not bind an original. Coverage and candidate originals from another run fail even when every input and candidate hash matches. Their original structured returns follow `native_check.md`. Submit the unchanged candidate and artifacts again with the returned reports:

```sh
python harness/native_run.py submit --run-dir run-001 \
  --candidate final.txt --artifacts artifacts --events events.json \
  --reports reports.json --text-views text-views.json
```

Omit `--text-views` for text-only artifacts. For a rendered artifact, supply `--views INTERNAL_DIR` and map its name to artifact_sha256, view_path, view_sha256 and pages records with positive page numbers and contiguous decoded-character start/end ranges covering the view. View files remain internal and are scanned under views/. Changing either hash or the page mapping changes its required checks. Each revised candidate, event log, or review envelope produces a separate submission; earlier snapshots remain intact. `ready` requires all required capabilities available, the fixed coverage return, and `native_check` status `consistent`. Every selected quality role supplies all 22 individual records, B25–B31 and C01–C15, with candidate hashes, concrete judgment evidence and claim_refs into the shared claim_evidence ledger. Register target ranges and typed source correspondence once in that ledger. Missing materials, missing checks, failed requirements, and unresolved findings return `blocked` and the next actions.

## Finalize the same bytes

```sh
python harness/native_run.py release-check --run-dir run-001 \
  --submission-sha256 SUBMISSION_SHA256
python harness/native_run.py finalize --run-dir run-001 \
  --submission-sha256 SUBMISSION_SHA256 --output completed-001
```

Both commands reread the saved snapshot and rerun its complete checks. The same publication predicate runs before writing, during post-staging revalidation and in trusted Stop's verify-only branch. A changed candidate, source, coverage return, required file, policy or review cannot reuse an old approval. `release-check` is read-only and returns no candidate body or output. Without a configured authenticated or explicitly authorized host-observed adapter, it returns `blocked-unapproved`; changing self-reported booleans cannot elevate it.

Only strict-reviewed, fully checked and authenticated results can become `finalized-approved`. An explicitly authorized Site host-observed adapter instead returns `finalized-host-observed`, `assurance_class=host-observed` and `provenance_authenticated=false`; it requires real direct role submissions and coordinator comparison with actual launches and originals as specified in CONTROL. The existing atomic no-replace writer publishes only the contract's requested artifact paths. Metadata binds the exact request, candidate, policy, complete artifact set, actual review event references, host approval time and release identity. The final response is returned only after publication; the output destination must be new or match its exact recoverable prior finalization. Interrupted publication can resume only after the same publication predicate passes again. Unknown, unavailable, failed or incomplete conditions remain unapproved regardless of retry count.

The read-only Python API is `verify_release(run_dir, submission_sha256)`. Neither it nor `finalize_run` accepts a verifier keyword or an authorization argument. Begin fixes `release_assurance` as host-authenticated (the local default) or the explicitly selected host-observed class. Host code can also fix `release_adapter` with adapter_id, version, connection and output_channel. Metadata records a configured route; it does not install a callback or prove connection. A configured Site route awaiting its server callback reports configured-awaiting-host-verification and directs the caller to that route. A missing local route directs the caller to obtain the missing integration. Neither is promoted by metadata to ready or approved. A different observed assurance class fails the common release predicate. Ordinary Chat text sends remain owned by the host and are not intercepted by this command.

## Site outgoing-surface routing

The Site keeps nonfinal progress/status/error submissions in isolated slots inside the same parent run. `advance_validation(action="submit", arguments={..., "surface":"progress"})` returns a server `surface_id`; it does not replace the parent final-candidate pointer or its review records. The fixed request, contract, adopted policy and pre-candidate coverage remain the parent's. Every slot holds one exact surface candidate and common claim/source ledger, with separate actual A/B and compliance original returns. Reuse the same compliance assignment; completion of its surface-review turn does not complete the parent assignment.

Pass that `surface_id` at the top level of `advance_validation` for `submit` control records and `status`. Register the three role assignments through `host-observed-assignment`; each actual worker directly submits its own `host-observed-review` original; the coordinator supplies the matching actual launch/return observations through `host-observed-match`. Originals bind the nonfinal `surface` and exact candidate hash. Keep both A/B judgments separate until fixed. Final-role records and another surface's records cannot satisfy this slot. Every review assembly selects its immutable submission explicitly, rather than the last mutable input file.

Use `advance_validation(action="release-surface", run_id=..., revision=..., surface_id=..., arguments={"submission_sha256":...})` for the slot's current assembled submission. The separate native surface predicate rechecks all 142 rules, both 22-judgment originals, compliance, source/operation bindings and actual host observations. Only eligible parent completion requirements remain deferred in `parent_unmet`; preserved prohibitions and invalid inputs block release. Success returns the identical body with `surface_release_authorized:true`, `release_authorized:false` and `final_task_release_authorized:false`. It creates no final artifact, URL or finalized parent state. Send only those unchanged bytes. Ordinary Chat transmission is not intercepted.

Parent substantive state changes make old surface slots stale; reading bookkeeping does not. Surface submissions and review turns preserve the parent's final candidate, final receipts and pending requirements. Parent completion/cancellation does not permit a surface operation to restart the task. Without the required actual reviewers or coverage, authored free-text release stays blocked; tool/UI diagnostics describe their returned state and do not constitute approved authored prose.

## Explicit provisional selection

`--mode provisional --provisional-selection selection.json` records an explicit supplied mode choice, with exactly `mode: provisional`, `user_message_ref` and `user_text`. It does not authorize publication or authenticate the user message. Candidate bytes and check failures stay under the run's `submissions/` directory. Submit returns `quarantined-unapproved` or a blocked check; finalize and release-check return `blocked-unapproved`. They never create the requested final output directory, return `final_message`, or supply a public URL. Existing runs cannot change mode; resume missing work in the same unapproved run or begin a strict-reviewed run as required.

## Optional existing task-state binding

Select `--condition requested_local_state_helper_operation` at begin to pin the state helper. A run without this condition cannot add state at submit; begin a new run with the condition. Unused state helper changes do not invalidate a run.

Add `--state-file FILE --state-task TASK_ID --state-root PROJECT_ROOT` to submit to bind an existing task. `--state-root` defaults to the current directory, matching `state.py`.

The read-only adapter records `state.content_hash(state.candidate(task))` as `state_candidate_sha256` and the native file digest as `native_candidate_file_sha256`. Each registered file or message output maps to one exact candidate/artifact path with its registered version and native file hash. File paths must match the registered project-relative paths; message values must match the final candidate text. When one file supplies both final text and an artifact, its file record maps to the artifact namespace and its message record maps to the candidate namespace. Unmatched or object outputs require an explicit supported correspondence before this adapter proceeds.

Finalize rechecks that state candidate, its input/dependency versions, and mapped output bytes. It retains the hash of the exact state-store bytes parsed and every file hash read by the state validator, including transitive dependency and receipt evidence, for the atomic writer’s post-staging check. The adapter never updates task status or imports native reviews as state reviews. Without the adapter, `state_binding` is null.

## Regenerate and verify policy assets

```sh
python harness/policy_assets.py generate --root .
python harness/policy_assets.py verify --root .
```

Run generation after changing shipped rules or checkers. The runtime catalog contains mandatory assets and registered runtime resources; it excludes every `source_distribution_only` maintenance resource.

`verify --root .` checks every body in the runtime catalog and is the package-verification command. Each run transition instead verifies the mandatory assets, resolves the saved operation/profile/template/condition selection, and verifies only that adopted closure. It compares the exact selected manifest to the saved run. A changed selected asset or selection requires a new run, coverage, and candidate returns. Unselected resource bodies are not read during a run; package verification checks them separately. Finalization rechecks selected file hashes and resolves the current selected manifest after staging. Regeneration or edits to unadopted resource bodies preserve the run; changes to adopted bodies require updated adoption and checks.

Exporters pass runtime assets to `build_manifest(assets, paths=layout_paths)` after rewriting bundle paths, then call `verify_manifest(root, manifest)` to verify the complete exported layout. `verify_manifest(root, manifest, operation=..., conditions=..., profile=..., templates=...)` verifies and returns only the selected catalog and its bytes; `select_manifest` accepts that scoped result. Every mandatory asset and every resource in the adopted closure remains pinned.

Exit status is 1 for `blocked`, `blocked-unapproved` and `quarantined-unapproved`; other completed transitions return 0. Atomic snapshot and output writes select the existing OS-specific no-replace primitive; the implementation and test matrix below separates actual Linux execution from macOS/Windows API mocks.

## Fixing sources and handling expression matches

Pass the UTF-8 sources used for quotations and bibliographies through `begin --sources SOURCE_DIR`. Save sources in the run directory's `sources/` before creating the candidate, and fix each file's hash. Use a new run for source additions or replacements when resuming. Keep candidate and attachment directories separate from sources.

Retain every dictionary block match. Existing quality reviewers use `occurrence_judgments` to bind function, meaning, syntax, retained propositions, and source identity to each occurrence and candidate hash. Correct or delete occurrences that perform prohibited functions. Preserve quantities, logical negation, conditions, identifiers, and required original text through non-rhetorical occurrence judgments and source verification. Spelling, finite word lists, and quotation, code, or technical-term labels alone do not clear matches. Read legacy technical_usages/source_reproductions under the strict conditions of their original formats.

Block finalization in both strict and provisional modes when unresolved expression matches remain. Export requires completed expression scanning and zero unresolved matches.

Before each final/progress/status/error send, bind the exact outgoing bytes to the matching surface, perform the complete 142-rule scan and both quality originals' 22 semantic judgments, and inspect surface_check.review_status. `scan-text --require-clean` reports lexical results only; zero hits do not authorize a send. Preserve any located nonrhetorical occurrence with its meaning and original-source identity. Parent completion requirements can remain pending during a consistent progress review; final publication still requires every parent requirement and the common gate. Final delivery uses unchanged finalized bytes. Ordinary Chat transmission remains outside this runner's execution ownership.

## File and inspection budgets

Original data and binary artifacts are pinned by streaming SHA-256 and byte size. Source versions are stored once under their content hash and reused by local runs. Reopening and finalization recheck that content. UTF-8 original quotations use decoded-character coordinates with bounded range reads. Managed text/JSON and each inspected artifact/view body use the 16MiB inspection budget; combined artifact/view text uses 64MiB. These inspection budgets do not cap raw source or binary artifact size.

## Concurrent run operations

Begin/resume, submit and finalize share one OS lock for the canonical run path. A concurrent operation returns an active-operation result and reloads the current context before retrying. Process exit releases that lock. Keep the existing run and its append-only record chain. Finalization rechecks the bound state task, required outputs and actual read dependencies after staging; unrelated task bookkeeping preserves their valid checks.

## Trusted Codex hook association

The plugin's UserPromptSubmit command hook supplies a persistent task context and each turn's membership. Use its directory and `begin --hook-context ABSOLUTE_CONTEXT_PATH`. Status queries and continuation preserve the original request, run, candidate and same compliance worker. Additional user amendments retain exact text and contract-before/after hashes. The hook supplies an effective-request record and a new fixed-run path for an adopted change; copy its exact text rather than reconstructing the request. The old run cannot inherit the changed request's approval. A named partial stop records its target and preserved task; whole-task stop/Interrupt ends automatic reminders. A clearly marked new independent task receives its own context. Version-1 hook bindings remain readable at their original paths.

The compliance worker's exact canonical short packet plus check request ends a `turn-finished`, including before a candidate exists. The same worker resumes for the next relevant event. `assignment-completed` instead requires the same structured compliance original checked for the current candidate, with both quality original hashes. Instruction delivery and its observed receipt never become a semantic judgment or publication approval.

PreToolUse applies hook-side operation/target/authority checks and returns the host's permissionDecision deny shape for a refusal. The hook registers only the input paths it can resolve; shell expressions or modifying targets that remain unresolved cannot supply permission. Its saved preflight binding is not a reusable execution permit. The host does not rerun PreToolUse for write_stdin input or poll, and hook errors/timeouts can continue execution. The local runtime has no execution-owner/session-input adapter, so it cannot guarantee prevention on those paths. Do not describe the local callback tests as live execution enforcement or change host trust/permissions to make them pass.

Hook-bound submissions retain only the current submission pointer. Authenticated successful finalization records its actual publication after writing the requested files. Stop calls the same finalization checks in a read-only verification branch, checks that receipt and latest submission, and compares the actual host message plus finalized output paths and bytes. It refuses stale candidates, altered attachments, missing checks and mismatched host bindings. Saved record consistency does not authenticate the origin of caller-supplied semantic judgments.

Command hooks require a supported local orchestration host and explicit trust in the exact definition. The publication implementation selects Linux renameat2, macOS renamex_np or Windows MoveFileExW. Linux publication is exercised in this environment; macOS/Windows APIs are covered by compatibility mocks, with actual OS/GUI/IDE activation and E2E unmeasured. Cloud orchestration command hooks remain unsupported.

## Reading selection and recovery

The begin manifest fixes the full adopted dependency closure. `select_reading_sections` chooses registered resource/section IDs for entry, contract, compose, review or finalize within that closure. `--resource-reads` records reader_id, resource_id, exact resource sha256 and completed section IDs. Optional partial_sections records section_id/start/end at absolute Unicode-character positions; keep unread ranges for the next read. Same-version readings are reused without changing run ID or policy manifest. Reading metadata records reported reads, not model consumption or adherence.

Finalization first fixes submission, destination and the complete output set/size/hash in the existing finalizations record. After interruption, repeat the same command: identical outputs and adopted dependencies allow missing receipts to be repaired. A modified, missing, extra or foreign output is rejected. Missing required artifacts return requirement_id/path/produce-required-artifact in every mode; add the file and resubmit in the same run.

| Platform | Implementation | API compatibility test | Real host |
| --- | --- | --- | --- |
| Linux | renameat2 no-replace + OS lock | native calls | CLI library/shell tests here; actual Codex hooks activation not measured |
| macOS | renamex_np no-replace + OS lock | mock API branches | not measured |
| Windows | MoveFileExW no-replace + OS lock | mock API branches | not measured |
