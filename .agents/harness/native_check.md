# Native candidate consistency checks

`native_check.py check-native` is one read-only entry for an existing Python execution tool. It calls the shipped `requirements_check.validate_requirements` and `local_checks.scan` implementations, then compares the selected registered plan’s original role records with the same candidate and inputs. Python 3.10+ is required. The checker reads local inputs and makes no network requests. The host launches the independent reviewers required by focused/full, while direct retains author self-checks; the coordinator supplies their original returns and delivers the finalized runner snapshot.

## Prepare and inspect

1. Before producing the candidate, retain the exact UTF-8 request and the explicit requirement contract. Use [freeze-requirements](requirements_check.md) to validate the contract and retain its printed SHA-256 independently. Also retain SHA-256 of the request bytes. Do not replace either pin with a freshly calculated value merely to pass a changed input. A legitimate user change needs its own preserved request/contract version and change evidence.
2. Save the complete final user-facing text, including headings, quotations and completion statements, as `answer.md`. Retain its exact byte hash. Keep every deliverable in a dedicated `candidate/` directory, and keep contracts, dictionaries, operation records and role reports outside that directory. The final answer file may be inside or outside the directory; if it is also a deliverable, both labelled surfaces are scanned.
3. Supply the final action-event array described in [the requirement guide](requirements_check.md). Artifact-only tasks use `[]`. Missing events, failed actions and wrong operations/targets remain unmet. Match each success event with the performing tool’s actual return.
4. Run the checker, initially without `--reports` if reviews are still pending:

```sh
python .agents/harness/native_check.py check-native \
  --candidate answer.md --request request.txt --requirements requirements.json \
  --expected-request-sha256 RETAINED_REQUEST_SHA256 \
  --expected-contract-sha256 PRE_CANDIDATE_CONTRACT_SHA256 \
  --expected-candidate-sha256 EXACT_CANDIDATE_SHA256 \
  --artifacts candidate --events events.json \
  --dictionary .agents/quality/prose_rules.json --author-id ACTUAL_EXECUTOR_ID \
  --review-plan SELECTED_PLAN
```

Replace SELECTED_PLAN with the pinned direct, focused or full registry plan; native_run supplies it for its own checks. Use actual 64-character lowercase SHA-256 values. `--author-id` identifies the actual execution worker, not a newly invented name. The initial run still checks requirements and scans prose, returns computed bindings and findings, and reports the missing role returns as `incomplete`. Do not describe it as approved. Malformed inputs or changed pins produce `fail`.

All files in the artifact directory are included in the snapshot, including extra deliverables not declared in the contract. Symlinks, nonregular files and unreadable artifact subtrees are rejected. Traversal errors cannot silently reduce the inspected snapshot. Managed text/JSON inputs and each inspected text artifact or internal view have a 16 MiB budget; inspected artifact/view text has a 64 MiB total budget. Artifact and original-source snapshots each permit 10,000 files. Original sources and binary artifacts are fixed by streamed size/SHA-256 rather than a universal 16 MiB file limit or 64 MiB raw-source total. Textual evidence uses bounded UTF-8 ranges, and format-specific inspection limits still apply. The pure integration function applies the same relevant count/text budgets; its caller owns safe acquisition of input bytes or fixed file versions. Input snapshot or scanner errors remain failures and list checks not completed.

## Returned role records

After the selected checks finish, preserve each exact original structured JSON return in `return_text` and its raw UTF-8 hash in `return_sha256`. The original object is the source of every verdict, finding, check and candidate binding:

```json
{
  "schema_version": 3,
  "role": "quality-a",
  "decision": "pass",
  "candidate_sha256": "COPY_FROM_CHECKER_BINDINGS",
  "request_sha256": "COPY_FROM_CHECKER_BINDINGS",
  "contract_sha256": "COPY_FROM_CHECKER_BINDINGS",
  "events_sha256": "COPY_FROM_CHECKER_BINDINGS",
  "dictionary_sha256": "COPY_FROM_CHECKER_BINDINGS",
  "artifacts_sha256": "COPY_FROM_CHECKER_BINDINGS",
  "text_views_sha256": "COPY_FROM_CHECKER_BINDINGS",
  "sources_sha256": "COPY_FROM_CHECKER_BINDINGS",
  "findings": [],
  "unassessed": [],
  "errors": [],
  "checks": {
    "requirements": "passed",
    "whole-candidate": "passed",
    "prose": "passed",
    "meaning": "passed"
  },
  "evidence_sources": [],
  "claim_evidence": [],
  "claim_ledger_sha256": "HASH_OF_CANONICAL_CLAIM_AND_EVIDENCE_LEDGER",
  "review_scope": ["candidate/answer.md"],
  "assessment": "Concrete comparison of the full text, claims and original sources",
  "prose_verdicts": {},
  "occurrence_judgments": []
}
```

New quality original returns use schema version 3. Version 2 remains readable under its original strict validation and is normalized to a common review view; original bytes/hash remain unchanged. Compliance originals and the reports envelope remain version 1. Populate the typed claim ledger, complete review_scope and all 22 prose_verdicts before returning a completed review. The empty verdict map above leaves all 22 checks unmet.

Place each exact return in a record containing these transport fields:

- `role`: the same role as the original object.
- `worker_id`: the actual assigned identity; `review_kind`: the registered plan’s `independent` or `self-check` value.
- Independent returns retain distinct actual `launch_ref`/`return_ref` and `execution_status: completed`. Direct uses the author ID without an independent launch and mirrors worker_id/review_kind in its original body.
- `return_text` and `return_sha256`: the original JSON text and its raw UTF-8 SHA-256.
- Independent `source_verification` records use status `matched-to-runtime`, the actual comparison reference and verifier_id; use `not-verified` until compared. Direct uses status `self-check` and the actual author as verifier_id. These labels never authenticate a source by themselves.

The containing `reports.json` object has `schema_version: 1`, `reports: [...]` and `unresolved_flags: []`. Include only the selected plan’s roles from registry/operations.json: direct uses author quality-a self-checks; focused uses one independent quality-a; full uses independent quality-a, quality-b and compliance. Full worker IDs differ from the executor and each other, with distinct launch and return references. Request coverage remains the separate pre-candidate return required by that plan.

The importer parses the original and returns it under `reviews[role].normalized_return`. Compatibility copies of verdicts, arrays, checks, bindings or other substantive fields in the envelope must exactly match the original JSON values, including their types. Copies may be omitted. A missing original field cannot be supplied by an envelope copy. A fail in the original and pass in the envelope produces `fail`. Duplicate JSON keys, nonfinite values and malformed structured objects are rejected. Legacy unstructured text is classified `unstructured` and leaves the role unmet; retain it and obtain a structured return for the current candidate.

`findings`, `unassessed`, `errors`, and top-level `unresolved_flags` contain outstanding issues. Preserve repaired finding history in a separate original-object field. Pending or failed returns, stale bindings and outstanding issues leave the corresponding requirement unmet.

All roles require the eight bindings printed by the checker. `artifacts_sha256` is SHA-256 of the UTF-8 canonical JSON array of `{path, sha256}` objects, sorted by path. `text_views_sha256` hashes the canonical mapping, or `{}`. `sources_sha256` hashes the canonical array of `{path, sha256}` objects for the separate original-source snapshot sorted by path, including `[]` when no sources exist. Canonical JSON is `json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')`. Request/contract/candidate/events/dictionary hashes use exact raw bytes, not canonicalized JSON. Hashes identify the exact input bytes; retain runtime event references for timing and authority.

Each selected role's `checks` must explicitly record `passed` for the registry plan’s required checks. Additional reported checks cannot contain a failed, pending or unperformed value:

- quality-a: `requirements`, `whole-candidate`, `prose`, `meaning`; focused also requires request-coverage/instructions, and direct requires its registered coverage, meaning-preservation, instruction/provenance/final-candidate self-checks.
- quality-b under full: `request-coverage`, `whole-candidate`, `meaning-preservation`. Extract required deliverables, actions and conditions directly from the original request and compare them with the contract, rather than merely accepting the declared rows.
- compliance under full: `instructions`, `operation-provenance`, `review-provenance`, `final-candidate`. Compare actual tool returns with all declared successful action events.

### Individual full-candidate prose records

Every selected quality role returns all 22 verdict IDs: B25–B31 and C01–C15. The catalog is fixed independently of dictionary metadata. Each role records candidate_sha256 once, claim_ledger_sha256 once, review_scope containing every complete final text/attachment/view path exactly once, and a concrete assessment of the whole text against the proposition ledger and original sources. The general checks object and zero lexical matches cannot replace these judgments.

`claim_ledger_sha256 = sha256(canonical({"claim_evidence": [...], "evidence_sources": [...]}))`. The surrounding request/artifact/view/source bindings continue to fix all input bytes. Use `native_check.quality_review_record(candidate_sha256, claims, evidence, text_paths, assessment, verdicts, occurrence_judgments=())` to generate these common v3 fields; it does not generate substantive judgments, identity transport, role checks or approval.

```json
{
  "schema_version": 3,
  "candidate_sha256": "EXACT_CANDIDATE_BYTES_SHA256",
  "claim_ledger_sha256": "HASH_FROM_claim_ledger_sha256_HELPER",
  "review_scope": ["candidate/answer.txt", "artifacts/answer.txt"],
  "assessment": "Concrete bidirectional comparison of the complete texts, required propositions and original evidence; includes information structure and omitted propositions.",
  "prose_verdicts": {
    "B25": "absent", "B26": "absent", "B27": "absent", "B28": "absent",
    "B29": "absent", "B30": "absent", "B31": "absent",
    "C01": "absent", "C02": "absent", "C03": "absent", "C04": "absent",
    "C05": "absent", "C06": "absent", "C07": "absent", "C08": "absent",
    "C09": "absent", "C10": "absent", "C11": "absent", "C12": "absent",
    "C13": "absent", "C14": "absent", "C15": "absent"
  }
}
```

Supply the existing evidence_sources and claim_evidence arrays with inspected exact bytes. Each claim has exactly id, target, claim_kind and basis_refs; derived-result also has derivation. Targets have {path, sha256, start, end, quote}, unique IDs and non-overlapping exact ranges. Record propositions, including numerical/conclusive headings, and their original evidence. Navigation headings, connectives and list markers are information structure assessed in the full text; do not invent evidentiary claims for them. The checker rejects uncovered numeric content (ordered-list marker digits are structural), while the selected reviewer judges whether conclusions or other propositions were omitted. Semantic completeness and entailment are not proven from assessment prose.

Each prose_verdicts value is absent, violation or unassessed. Missing IDs leave the review incomplete; unknown IDs and invalid values fail. Violation/unassessed requires a concrete corresponding entry in findings/unassessed with check_id, target {path, sha256, start, end, quote}, assessment and claim_refs. References identify affected ledger claims only, not the whole ledger repeated 22 times. A finding concerning information structure may have empty claim_refs. Outstanding findings, errors, unassessed points and violations continue to block completion. Candidate/ledger/scope changes require a current return.

Version 2 remains readable for migration and draft checks; strict-reviewed publication and outgoing-surface consistency require current schema 3 originals so downgrading cannot omit typed meaning/source identity. Version 2 keeps its original prose_checks array with exactly {check_id, verdict, candidate_sha256, evidence, claim_refs} for all 22 IDs, and every record must reference every claim exactly once. Its ledger still covers all non-whitespace target text. The reader validates those original constraints before deriving reviews[role].prose_review with one shared candidate, ledger hash, scope, verdict map and retained legacy assessments. Do not silently relabel unchecked v2 data as v3. Generation uses v3; read conversion never rewrites an original return or its transport hash.

- Each ordinary `evidence_sources` entry has exactly `{id, source_path, source_sha256, source_kind, start, end, quote}`. The quote must be nonempty and exactly match the supplied source range. Only `request`, registered contract text at `request-source://SOURCE_ID`, paths from the separately pinned original-source snapshot, and registered evidence/<relative-path> bodies in the current submission evidence snapshot are eligible. Each source ID must be referenced by a claim, occurrence source_refs, a literal reproduction, or legacy definition_refs; missing or duplicate IDs fail.
- Within `request` or a pinned contract request-source, classify the exact source span as `request-instruction`, `user-supplied-value`, or `user-supplied-assumption`; do not classify the entire request automatically as an instruction. In pinned original sources the allowed kinds are `source-proposition`, `calculation-result`, and `adopted-premise`. They retain exact byte bindings; every calculation-result also requires provenance binding premises, the actual command and returned result. Added evidence rows and their provenance must exactly match the submitted evidence manifest.
- Binary calculation inputs use `source_kind: input-file` with exactly `{id, source_kind, source_path, source_sha256, size_bytes}`. The original-source snapshot stores their raw bytes; size_bytes is the nonnegative byte count and source_sha256 hashes those bytes without UTF-8 decoding. They have no quote or character range. Only numeric derived-result input_refs and basis_refs may include this kind, through a `mode: file` input binding to the calculation-result. It cannot directly support source-observation, logical/comparison derivation, a quoted passage or a term definition. Textual evidence and processing code still require valid UTF-8 and exact source spans.
- `operation-result` sources instead have exactly `{id, source_kind, event_id}`. Their event must have a successful operation result already validated against the original call and return. An event label or a reviewer's statement of success does not substitute for the actual validated result.
- `basis_refs` is a nonempty array of unique existing source IDs. Required source kinds are fixed: `request-adherence` requires `request-instruction`; `user-supplied-value` requires the matching user-supplied value span; `source-observation` requires `source-proposition` or `calculation-result`; `assumption` requires `user-supplied-assumption` or `adopted-premise`; `derived-result` requires premises (`user-supplied-assumption`, `adopted-premise`, `source-proposition`, or `user-supplied-value`) plus the typed derivation described below; `operation-complete` requires `operation-result`. Unrelated source kinds cannot be mixed in to satisfy the dependency. Thus an observed 80-yen price with only a request instruction fails; a translation of a user-provided 80-yen price uses its exact request value span.
- Offsets count original decoded UTF-8 characters, not bytes or normalized scanner coordinates. All hashes use exact raw bytes. Quotations and target spans are verified before references are used. These pointers do not by themselves exempt dictionary matches.

For a numeric derived-result, use `derivation: {kind: numeric, expression: <exact executed command>, input_refs: [<premise IDs>], result_ref: <calculation-result ID>, result_span: {start, end}}`. result_span uses absolute character offsets in the claim target text; its exact slice must equal the calculation evidence quote after stripping outer whitespace. The span must cover a whole numeric token in the full candidate, not just within the claim: a result of 3 cannot prove 30, -3, 3.0, 3e9 or 3,000. Unicode minus signs and exponent signs belong to the quantity. Dot decimals and complete comma-separated three-digit groups are recognized without converting the spelling or value. Shared source-coordinate display views also reject quantities split across adjacent claims or Markdown decoration/link labels, such as 3**0**. Original stdout selections and evidence quote boundaries cannot cut through a quantity either; diagnostics identify original return, evidence quote or candidate result_span. Original bytes, labels, newlines and offsets remain unchanged. A calculation yielding 3 cannot prove a claim stating 80. Its basis_refs contain exactly those inputs and the result. The result provenance binds those inputs to that actual command and its validated return chain; the result-bearing return need not be the successful terminal return. For logical deduction or a choice comparison, use `{kind: logical|comparison, expression: <specific inference or candidate comparison>, input_refs: [<premise IDs>]}`; basis_refs contain exactly the premises. The quality reviewers verify the premises and inference, without demanding an irrelevant numeric calculation. Generated explanations, circular references and calculations with different inputs fail.

Additional evidence uses the existing evidence_sources ledger, not a new review role. Submit an evidence directory containing manifest.json with schema_version 1, the fixed run_id and evidence_sources, plus UTF-8 result bodies. Each added row has the ordinary fields and `provenance: {tool_result: <actual operation-result record>, input_bindings: [{source_id, pointer, start, end}], result: {pointer, start, end}}`. Pointers are JSON pointers into parsed call_args_text and return_text, respectively; selected values must be strings. Input spans equal exact premise quotes, and the result span equals the entire stored evidence body. Calculations require successful execute_command with nonempty input bindings. For command results, prefer `result: {tool_return_ref, pointer: /output, start, end}`. The reference selects the initial return or any continuation from that same fully validated command chain. The legacy result without tool_return_ref selects the terminal return. For multiple pieces, use `result: {fragments: [{tool_return_ref, pointer: /output, start, end}, ...]}`; concatenate exactly in listed order, without inserted separators. References must appear in chain order and cover one continuous range of the reconstructed, fully validated same-session stdout. Within a return each fragment begins exactly where the prior fragment ends; across returns, preserve the prior suffix, subsequent prefix and all intervening output. Missing newlines or any other skipped text are rejected. Quantity boundaries are checked after reconstruction, so returns ending with 1 and starting with 4 may form the intact quantity 14, but neither digit can be selected alone. Their exact concatenation equals the entire evidence body. A prior result is accepted even when the terminal output is empty. Completion still requires same-session continuations and a successful terminal exit code; an intermediate error, unrelated return or running final session fails.

Input bindings retain the existing direct-argument form, optionally with `mode: argument`. For file inputs use `{mode: file, source_id, workdir, path, sha256, processing, reference}`. workdir must be an absolute normalized path equal to the explicit exec_command workdir; path is the resolved absolute normalized input path, and sha256 is the hash of the full pinned input bytes, not merely its quoted range. Register input, code and configuration bytes in the existing evidence_sources and original-source snapshot (or supported acquired evidence snapshot), not a separate ledger. processing is a nonempty ordered array of `{source_id, path, sha256, reference: {start, end}}` links. Its first reference selects the invoked code path in the exact command; each later reference selects the configuration path in the preceding pinned code/configuration body. The binding's final reference selects the input path in the last processing body. Resolve every selected path against the fixed workdir and match the recorded absolute path and full source digest. For example, `python /work/calc.py` → pinned calc.py containing `open("values.json")` → pinned /work/values.json with `[1, 2]` does not require copying `[1, 2]` into command arguments. A comment containing the values is not a substitute for this file chain. Multiple inputs may reuse pinned processing dependencies; numeric derivation input_refs still list only premise inputs, while processing sources are retained as transitive dependencies. The final link accepts input-file, validates its pinned byte size and digest, and stops without decoding it. Processing links never accept input-file and remain UTF-8 text. Numeric input_refs must equal the result’s premise dependencies, and basis_refs must equal input_refs plus result_ref. Code/config/input changes invalidate old version bindings. Paths with dynamic construction need an inspectable supported reference chain, not invented string spans. Existing quality reviewers verify actual code invocation, file resolution (including symlinks), configuration use and that the processing consumed these input bytes; this checker validates retained references and versions, not execution truth.

Acquired source-proposition/adopted-premise evidence uses a fixed read adapter and exact runtime-matched call/return hashes:

- mcp__codex_apps__google_drive_get_document uses read_document/success, target equal to the raw document ID from document_id/document_url, and a result pointer ending /textRun/content under the matching returned documentId.
- web__run uses read_url/success with the original open/click call and return. Select one returned document body with result pointer, raw character start/end and its returned source_id. Supported batches bind the selected document to its actual call item and header metadata. Reference-ID and click retrievals retain the validated antecedent call/return chain establishing that reference; a bare reference label cannot substitute for it. Single absolute-URL legacy reads remain supported when unambiguous. Search snippets and discovery metadata are not document bodies. Fetch failures, selected-branch errors, mismatched identities and out-of-body spans fail.
- mcp__codex_apps__search_service_web_run uses the same web adapter while preserving its actual tool name and complete CallToolResult. Select the actual text block, for example /content/N/text, with the same document/call and original-body bindings. Never rewrite the tool name or manufacture an envelope.
- mcp__codex_apps__library_read uses read_document/success and the actual read array. Select /structuredContent/results/I/content/J with returned source_id and file_id and the supplied version_id when present. Bind the selected result’s read_index/identity to its call item; an unrelated sibling failure does not become a failure of a valid selected document. Root or selected-document failures and identity/version mismatches remain rejected.



The selected span equals the stored evidence body. input_bindings may be empty for acquisition. Existing quality reviewers confirm that the passage is the actual document body, inspect partial access and conversion quality, and assess its support for the claim. The checker binds tool, target and exact bytes; article headers and a matching string do not establish source authority. Arbitrary generators or shell echoes cannot be relabeled as source reads. The evidence manifest run_id must equal the supplied canonical run_id, including direct checker calls; an absent or different run ID fails. Mirror registered evidence rows exactly in each quality report. The manifest and bodies join sources_sha256, so changed evidence requires affected reviews even when candidate bytes are unchanged.

The selected quality roles inspect the complete candidate and attachments against all 22 criteria. Full retains two independent quality findings before comparison; focused uses its independent reviewer, and direct records the author’s self-check. Runtime identity and release authorization are not established by this structural check; authentication and release flags retain their existing false values.

For every final action event, the full plan’s original structured compliance return must include one `action_results_verified` entry. Direct/focused eligibility excludes action events; do not invent a compliance role for those plans. An artifact-only task may omit this list or supply `[]`. Example:

```json
{
  "action_results_verified": [
    {
      "event_id": "actual-final-event-id",
      "operation": "send_email",
      "target": "alice@example.com",
      "status": "success",
      "tool_name": "send_email",
      "call_args_text": "{\"target\":\"alice@example.com\"}",
      "call_args_sha256": "SHA256_OF_EXACT_CALL_ARGUMENT_TEXT_UTF8_BYTES",
      "tool_call_ref": "actual-tool-call-reference",
      "tool_return_ref": "actual-tool-return-reference",
      "return_text": "{\"status\":\"success\",\"operation\":\"send_email\",\"target\":\"alice@example.com\"}",
      "return_sha256": "SHA256_OF_EXACT_RETURN_TEXT_UTF8_BYTES",
      "source_verification": {
        "status": "matched-to-runtime",
        "reference": "actual-operation-comparison-reference",
        "verifier_id": "actual-observer-id"
      }
    }
  ]
}
```

The event ID, operation, target and status must match the final event array. Each action has an original returned result; duplicate or unknown event IDs fail. Tool call and return references must differ. The checker validates each event against its supplied original return; the coordinator compares that return with the runtime event.

The fixed `_OPERATION_ADAPTERS` table selects a parser by the exact `(tool_name, operation)` pair, never by a reviewer-selected parser. Registered saved-result schemas are `(send_email, send_email)` and `(publish, publish)` for JSON results, and `(execute_command, execute_command)` or `(exec_command, execute_command)` for command completion, with `(write_stdin, execute_command)` for linked continuations. Real file-save bindings are `(mcp__codex_apps__library_create_library_file, save_file)`, `(mcp__codex_apps__library_replace_library_file, save_file)` and `(mcp__codex_apps__library_finalize_uploads, save_file)`. Each registered parser binds the named call schema to its saved return. Add a fixed parser entry when adding another tool, and retain its actual tool name.

Each record includes the actual tool name, exact original `call_args_text` and its `call_args_sha256`, as well as the original return text and digest. Both texts parse as strict JSON objects (duplicate keys and nonfinite values fail). Call arguments derive the target from `target` or `to` for send_email, `target` or `document_id` for publish, and `cmd` for command completion. Multiple aliases must agree exactly. The operation is bound by the registered pair; a supplied operation argument must agree. The derived call target must match the final event. The coordinator compares this caller-supplied evidence with the actual call and return; matching bytes do not authenticate their origin.

JSON returns require explicit `status: "success"` and returned target metadata (`target` or `target_id`, directly or inside `metadata`) matching the call. Pure status objects cannot establish completion. All `result`, `structuredContent` and JSON-text `content` branches are recursively inspected to eight wrapper levels, with every terminal branch independently satisfying its adapter. A non-success status, non-false `isError`, nonempty error/errors, inconsistent target/operation, unknown result field or uninterpreted container rejects the record. Metadata is restricted to operation, target, target_id and id string fields. Empty/non-text content, prose-only returns, unknown outcome containers and unsupported provider formats remain unmet, even beside a success flag.

Command completion requires a terminal integer `exit_code: 0`, bound to the exact `cmd` argument. Boolean false is not an exit code. Nonzero exit, pending/running status, a non-null session ID or a nested error remains unmet; a continuing session is classified as `running`, exposed in the operation-result diagnostics, and is not a completed action. Command completion proves only execution completion, never publication or sending. Public/send completion must use the corresponding registered operation and returned target metadata. No new external connection, runtime identity authentication or release authority is introduced.

For an asynchronous command, retain the initial exec_command record and append a `continuations` array. Each continuation repeats the same event_id, operation and original command target; it contains the actual write_stdin tool_name, unique call/return references, exact call_args_text/return_text and both SHA-256 digests, plus source_verification. Every call must poll the initial integer session_id with empty or omitted chars. Intermediate returns remain running; only a matching terminal exit_code 0 with no live session completes that original command. Reject another session, target, operation, nested error or a continuation after termination.

File-save adapters accept one file per action, not arbitrary provider formats or multi-file batches. create_library_file binds the absolute local path in file (or a single-element files array); its return must identify library_file_id. finalize_uploads binds one item with purpose=create_library_file, store_in_library=true, upload_session_id, file_id, file_name and exactly one workspace_path or upload_url. Its target is workspace_path for local uploads or file_name for the signed-URL route. The supported returned Library identity and documented metadata are parsed through the registered adapter, including a one-result envelope. The returned library_file_id is retained in the operation outcome; finalize_uploads also requires the returned file_id to equal its input file_id, including nested-result agreement. Native create and replace returns use status succeeded and operation create_library_file or replace_library_file; the fixed adapter maps these actual returned operations to the recorded save_file operation. It accepts the documented Library identity, path/file_name, current_version_number, nullable restored_from_version_number, xattrs name/value entries, directory_id, mime_type, library_artifact_type, file_size_bytes and boolean external_connectors_accessed. The outer text content Action completed. is accepted only alongside the structuredContent result; errors and contradictory JSON branches remain rejected. Replacement call arguments include file and library_file_id, with optional expected_current_version, directory_id and version_reason. The target remains the source path, the returned library_file_id must equal the call, and a supplied expected_current_version requires returned current_version_number equal to that version plus one. A saved file does not establish publication or delivery.

Under full, after its two quality reports are locked, the original structured compliance return supplies `quality_reports_sha256`, an object mapping `quality-a` and `quality-b` to SHA-256 of their complete supplied canonical envelope objects, including original text and transport metadata. Hash the supplied records, not the derived normalized output. Changing either report invalidates that final observation.

The coordinator must compare launch references, actual worker IDs, role assignments, original return text, check coverage, candidate bindings and actual operation results against the runtime's real outputs. Use `source_verification.status: "not-verified"` when that comparison has not occurred; such a record remains incomplete.

Add `--reports reports.json` to the same command for the final consistency run. A missing/unreadable reports file remains a missing check; other available inspections still run. Never manufacture returned report text, call references, source comparisons or worker identities to fill this envelope.

## Prohibition and technical use

Every lexical hit remains blocked until repaired or resolved by the selected quality reviewers. The base dictionary action is block; scan also returns resolution: occurrence-review-required. Native review changes that field to occurrence-reviewed only for the exact matches resolved by all selected quality roles. All 142 IDs/patterns and raw/display/whitespace constituent mappings remain in effect. A source quotation, code block or technical label alone never resolves a hit. Retired source_exemptions, compound_dispositions, dispositions and literal_dispositions remain rejected when nonempty.

Schema 3 uses occurrence_judgments. Each item has exactly:

`{rule_id, path, start, end, input_sha256, text, text_start, text_end, character_spans, verdict, prohibited_function, function, sense, syntax_role, target_proposition, assessment, claim_refs, source_refs, source_identity, meaning}`.

rule_id/path/start/end anchor an actual hit. input_sha256 fixes that file. text is normalized source-view spelling; text_start/text_end and character_spans identify its actual constituent characters in raw-source coordinates. It must contain the anchor hit and match a real occurrence; a raw interval cannot substitute for constituent mapping. A judgment is shared only across rules matching the same contributing characters, never across every hit inside a quoted/code/paragraph envelope. Other occurrences retain their own judgments.

verdict is absent, violation or unassessed; prohibited_function is an actual boolean. Only absent plus prohibited_function:false can resolve a hit. function, sense, syntax_role, target_proposition and assessment are concrete nonempty judgments of the actual occurrence and surrounding proposition. Code, quotation, profession, necessity and good intent are not substantive judgments. A quotation selected as self-defense or a reservation remains prohibited. The existing 22 full-text judgments independently cover the explanation, quotation selection and actions, including execution deferral even without a lexical hit.

meaning has exactly {proposition_id, actor, predicate, object, relation_type, modality, polarity, quantifiers, conditions, quantities_and_units, source_relation}. actor/predicate/object/relation_type are concrete nonempty strings. proposition_id identifies one of claim_refs (or source_refs when no claim is referenced). modality is permission, obligation, ability, feasibility, actuality, epistemic-uncertainty or none; polarity is positive, negative or not-applicable. quantifiers and conditions are arrays of nonempty strings; quantities_and_units contains {quantity, unit} strings, retaining the original scale and units. source_relation is quotation, bibliography, identifier, paraphrase or generated-proposition. A/B canonical agreement includes all these fields, including causal/correlational relations, relative/absolute changes and necessary/sufficient conditions; free explanatory wording is retained independently. A semantic-structure disagreement remains unresolved. The checker establishes recorded agreement.

claim_refs identifies unique existing claims containing this occurrence. source_refs identifies unique existing source ledger rows. At least one of these arrays is nonempty. The same ledger validates evidence kinds and retained original bytes. There is no new word whitelist. Registered technical_candidates are definition hints; technical terms, Japanese lexical compounds, calendar words, logical syntax and original identifiers use the same occurrence review.

source_identity is mandatory when meaning.source_relation is quotation, bibliography or identifier, or a registered source_reproductions range contains this occurrence. Omission cannot disable literal checking. A non-null value has exactly {kind, source_id, target_start, target_end}, with kind quotation, bibliography or identifier. source_id must be in source_refs. Its validated source quote must exactly equal the entire raw target range, enclosing this occurrence. A modified quotation fails this identity check. Exact copying cannot clear prohibited_function:true, violation or unassessed.

Full requires both independent quality originals to agree on the structured occurrence, exact target/claim correspondence and canonical original-source identity. Independent explanatory prose may differ; proposition_id binds the shared claim or source ledger and all typed meaning fields must agree. Focused uses its selected independent role; direct uses the labeled author self-check. The checker verifies structure, binding and recorded agreement.

Version 2 technical_usages is read with its original exact fields and eligibility constraints: registered/unregistered technical definitions and different Japanese whole words require the former definition/source/quantity-boundary checks. It is converted into reviews[role].occurrence_review as located sense/syntax/function records while retaining legacy definition metadata. Version 2 source_reproductions is still checked for exact source equality and converted as unassessed literal identity, never an invented function approval. Its original return bytes/hash remain unchanged. New v3 returns use occurrence_judgments and do not carry technical_usages. source_reproductions may still register additional literal quotations; source_identity integrates the literal correspondence for an occurrence. Both paths use the same source ledger and literal equality checks.

## Output and final checks

The JSON result includes `bindings`, `artifacts`, the requirement check, actual scan hits and unresolved hits, `reviews`, `executed_checks`, `failed_checks`, `missing_checks`, and `unresolved`.

- `fail`: invalid inputs, stale bindings, a failed requirement/review, or an invalid record. Exit 1.
- `incomplete`: required returns/checks, source comparisons, text views or finding resolutions are missing. Exit 1.
- `consistent`: all specified checks and supplied return records agree; `recorded_checks_complete: true`. Exit 0.

`executed_checks` lists this program's completed mechanical inspections. `consistent` sets `recorded_checks_complete: true`; `full_pass`, `release_authorized`, and `provenance.authenticated` remain false. Return provenance is `self-reported` or `caller-reported-runtime-match`. The coordinator compares actual launch, return and operation events before final delivery.

Contract-v2 requirements receive the exact final text as `candidate_bytes`. A `message://final` condition evaluates that text; `artifact://<path>` evaluates the matching attachment. Semantic requirements receive the normalized role records after role validation, including every selected quality role’s 22 individual assessments. The required role and named check must have a current passing return. Unassessed conditions remain unmet.

Re-read the exact final text and files before delivery. Changes to a candidate, attachment, contract, event, dictionary, source snapshot, text-view mapping or quality return require affected checks and current candidate-bound reports. When independent approval is a required output condition, obtain the missing return before delivering that candidate.

## Run-level verification

`native_run` passes a unique UUIDv4 `run_id` to `check_native(..., run_id=...)`. Include the same `run_id` in the original quality A, quality B, and instruction-compliance reviews. The checker verifies the run ID together with the existing hashes of the original request, contract, candidate, attachments, and operation records. A missing ID or an ID from another run is a mismatch. Standalone record diagnostics use the existing byte comparisons.

## Selected review plan

`.agents/registry/operations.json` is the source of review roles, capabilities, check names and eligible operations. The runner pins this definition; the checker compares any supplied definition against the registered one. Full and focused use their registered roles with the same claim ledger, prohibition checks, source dependencies and exact-snapshot finalization.

## Verbatim correspondence and derived operation state

Each quality original registers every verbatim source quotation and bibliography excerpt in `source_reproductions`: kind (quotation or bibliography), target_path, target_start, target_end and source_id referring to its typed evidence_sources. The exact target characters must equal that registered source quotation; hashes and source spans are verified by the ledger. A literal reproduction alone never resolves a hit; the schema 3 occurrence judgment additionally assesses function, sense, syntax and proposition. Changed wording is recorded as paraphrase, not verbatim reproduction.

Computed operation results appear in `operation_results`. Supported command sessions and pending results have status running; terminal exit-code-zero commands have success. A running result never proves operation-complete or satisfies a success event. The tool/operation adapter is selected from the fixed saved-result schema table, not from a reviewer-chosen parser.

## Artifact text classification

Use each validated artifact requirement's declared file_type before a filename suffix: text and json are scanned directly as UTF-8, including extensionless and custom-extension paths. Declared binary formats require extracted text and render correspondence even when their path ends in .txt. Undeclared attachments use the existing suffix fallback. Invalid declared types, malformed JSON and binary controls in text remain failures.

## Selected acquisition and internal views

Preserve the entire original tool call and return and their exact hashes. A web result selector chooses pointer/start/end and source_id inside one returned document body. Each selected Source header must match its own open or click item. Reused ref_id values require antecedents containing their actual producing calls and returns; click also binds its link ID. A Library selector uses /structuredContent/results/i/content/j (or that block's /text), source_id, immutable file_id and the returned version_id when specified. The selected document must match its request index and called ID. Failed selected transport/document records remain unmet; an unrelated failed sibling does not replace the selected success.

PDF acquisition uses a source-proposition provenance with extraction: {kind: pdf-text, input_source_id: ID, first_page: N, last_page: M}. Retain one input-file binding in file mode, its original PDF hash and absolute resolved path, exact workdir and command-path reference, and processing: []. The actual successful execute_command call uses pdftotext with the fixed input and stdout output. Bind -f/-l to the declared page interval; first_page: 1 and last_page: null records all pages. The parser accepts option order changes, an absolute pdftotext path, layout/raw/page-break flags and an explicit UTF-8 encoding. Bind its complete returned page text through result /output. The command, page interval, fixed PDF and returned body must agree. Other processing uses the existing pinned-code chain and explicit input bindings.

Text views are separate view_files inputs. Each artifact mapping binds artifact_sha256, view_path, view_sha256 and pages [{page,start,end}]; pages increase and character ranges partition the full view. A view cannot serve as an original source or become an extra delivery file. Scan view text under views/ and bind it to the selected quality judgments. Finalization publishes the contract's artifact set and retains all internal checking records in the run.

## Authenticated publication boundary

`assert_release_predicates` is the common strict-reviewed publication predicate. Existing requirement, operation, policy, exact-candidate, artifact, 142-occurrence and all 22-per-quality-role checks must pass before the separate trusted host provenance boundary. Record consistency is not release authorization. The installed host adapter is unavailable in this implementation; normal finalize and verify calls therefore retain blocked-unapproved. Callers cannot supply authorization through JSON, CLI, environment or a verifier keyword. Synthetic verifier injection belongs only to audit copies and does not establish a production host connection or semantic approval.

## Outgoing surfaces

`check-native --surface final|progress|status|error` fixes that surface and the exact candidate hash. Nonfinal surfaces require the same strict-reviewed A/B whole-text judgments, 142-rule scan and exact evidence/return bindings. The surface_check result separates scan_complete, lexical_hits, both 22-verdict maps, review_status, unresolved and release_authorized. Zero hits alone cannot produce consistent meaning review. Parent completion requirements remain in parent_unmet; an unfinished final artifact/action/content is deferred only for reviewing the progress/status/error text, never for final release. Preserved prohibitions and invalid inputs remain blocking. Native consistency retains release_authorized:false; it does not intercept ordinary Chat sends or authenticate caller-supplied records. Final publication still applies the complete fixed parent contract and adopted host gate.

The quantity omission guard uses structure_regions without altering the full-source scan. prose_scan.navigation_targets retains each link destination/reference identifier with its exact raw string, path, source coordinates and input_sha256; changing a destination changes both this identity record and candidate hash. Link destinations and reference identifiers retain exact raw strings/hash and source coordinates, while numbers in visible link labels or code still require proposition coverage. TextInspection shares identical views and occurrence searches within one check across the scan and both quality records; changed text or transformer creates a different key, and no reviewer judgment is inferred from this cache.
