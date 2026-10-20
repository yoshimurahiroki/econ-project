# Registered requirements: contracts v1 and v2

This local stdlib-only checker evaluates registered requirements against exact final-message bytes, artifact bytes, final action records, and structured original review returns. Use Python 3.9+. It makes no network requests.

## Register and freeze the requirements

Save the exact UTF-8 user request as `request.txt`. Each requirement has a unique `id`, a `kind`, and a nonempty `source_text` quotation that occurs exactly in the request. Compare the original request with the complete requirement list before producing the candidate. Register each requested output, action, content condition, prohibition, and evidence condition.

For inherited instructions, v2 additionally accepts the paired `sources` and `request_source_id` fields. Each source has exactly `source_id`, `version` (a nonempty string or nonnegative integer), `content_sha256` and exact UTF-8 `content`. The current-request source must reproduce request.txt bytes. Each requirement then requires its own `source_id`; all quoted spans use that source's Unicode coordinates. Missing, duplicate, stale or mismatched IDs/hashes fail validation. The existing single-request form remains the implicit default source and keeps its original span shape. Sources are pinned inside requirements.json, so begin, resumed transitions and candidate/review contract hashes retain them. Preserve prior sources and prohibitions when a later request says to continue; only an actual user change updates that contract. The existing request-coverage return partitions every registered source, with source_id on each row. Semantic obligation coverage is the reviewer's judgment, not a conclusion inferred from a matching quote.

An operation prohibition uses kind `prohibition`, exact `target`, evaluator `{"type":"forbidden_operation","operation":"..."}`, evidence_refs and pending status. It compares every recorded action's operation/target, including a failed attempt; matching events fail. A logged prohibited attempt may identify its prohibition requirement_id. Existing action records and their actual tool-return verification remain required. No matching event describes only the supplied log, not an authenticated history or preventive permission control. Use forbidden_literal for forbidden output text; the two predicates are separate.

Native quality evidence may cite a registered source at `request-source://SOURCE_ID`, with the exact content hash, character span and quote. This namespace is derived from the pinned contract and admits request-instruction, user-supplied-value or user-supplied-assumption evidence. Original external inputs and generated text retain their separate admission rules.

Each requirement accepts an optional `source_span: {"start": 0, "end": 36}`. Offsets count Unicode characters in the decoded original request, starting at zero, with an exclusive `end`. The selected substring must equal `source_text` exactly. UTF-8 byte offsets, UTF-16 code units, normalized text, and offsets into a reconstructed request fail this comparison. When `source_span` is absent, the checker derives every exact occurrence, including overlapping occurrences. Repeated quotations retain every occurrence; an explicit span selects one. Freeze and check results expose these exact positions in `source_spans`, keyed by requirement ID. Condition evaluations and checked entries also carry their positions. Derivation leaves the contract bytes and hash unchanged.

The contract has exactly three top-level fields:

```json
{
  "schema_version": 2,
  "request_sha256": "<SHA-256 of exact request.txt bytes>",
  "requirements": [
    {
      "id": "report",
      "kind": "artifact",
      "source_text": "Write report.md with three sections.",
      "path": "report.md",
      "file_type": "text",
      "nonempty": true
    },
    {
      "id": "three-sections",
      "kind": "content",
      "source_text": "Write report.md with three sections.",
      "target": "artifact://report.md",
      "evaluator": {"type": "exact_sections", "level": 1, "count": 3},
      "evidence_refs": [],
      "status": "pending"
    }
  ]
}
```

`schema_version: 1` supports the existing artifact/action format for standalone diagnosis. Version 2 retains both formats and adds `content`, `prohibition`, and `evidence`. Requirements must be a nonempty array. IDs, artifact paths, and required operation/target pairs must be unique. Conditions with identical kind, resolved target, evaluator, and evidence references are duplicates. Distinct checks may address the same target. Definitions with unknown fields, unresolved quotations, mismatched source spans, or unsafe relative paths fail validation.

Freeze before candidate generation:

```sh
python .agents/harness/requirements_check.py freeze-requirements \
  --requirements requirements.json --request request.txt
```

Retain the returned `contract_sha256` outside the candidate. Checking requires that retained hash. A contract change needs an explicit requirement-change decision and a newly retained version.

## Artifact and action predicates

An artifact requirement names `path` and `file_type`. `nonempty` defaults to true; UTF-8 text and JSON containing only whitespace count as empty. Optional `reject_placeholders` is an array of literal strings matched case-insensitively in text/JSON.

Supported artifact types:

- `text`: UTF-8 decoding.
- `json`: JSON parsing, including duplicate-key rejection.
- `pdf`: `%PDF-` signature and `%%EOF` trailer.
- `zip`: ZIP member CRC inspection.
- `docx`, `pptx`, `xlsx`: ZIP inspection plus the corresponding document and content-type entries.
- `binary`: bytes.

ZIP inspection admits at most 10,000 members and 64 MiB of declared expanded data.

Action requirements retain this format:

```json
{
  "id": "send",
  "kind": "action",
  "source_text": "Email the report to alice@example.com.",
  "operation": "send_email",
  "target": "alice@example.com"
}
```

Each action requires exactly one final record in `events.json`:

```json
[{"event_id":"event-1","requirement_id":"send","operation":"send_email","target":"alice@example.com","status":"success"}]
```

Operation and target must match exactly; only `success` fulfills the action. Missing/duplicate IDs, unknown requirement IDs, multiple final records, wrong operations/targets, and unsuccessful statuses fail. Preserve intermediate/retry history separately. Supply the final-record array through `--events`; keep intermediate and retry history in the existing operational record. Supply `[]` when the contract has no actions.

## Content, prohibition, and evidence predicates

Every v2 condition requires these fields, plus optional `source_span`:

- `id`, `kind`, `source_text`.
- `target`: `message://final` for the final response, or `artifact://path` for an exact artifact-relative path. Existing bare artifact paths retain their artifact meaning.
- `evaluator`: one supported object below.
- `evidence_refs`: an array of file/ID references.
- `status`: `pending` in the frozen contract. The execution report derives the result.

`message://final` consumes the separately supplied final-message bytes. An artifact named `final` or `final.txt` remains an artifact. Artifact-map keys are relative paths, never target URIs. A missing message input fails every condition registered against `message://final`.

Target syntax is case-sensitive and exact. Artifact targets reject absolute paths, empty/dot/parent components, trailing or repeated slashes, backslashes, colons, control characters, percent encodings, queries, and fragments. The checker performs no URL decoding, Unicode normalization, case folding, or path normalization. Artifact and evidence file paths also reject colons and control characters. `message://final/`, `message://final?x`, and `artifact://../file` fail validation.

For a final-message requirement, register the predicate directly:

```json
{
  "id": "answer-heading",
  "kind": "content",
  "source_text": "Include a heading titled Results.",
  "target": "message://final",
  "evaluator": {"type": "contains_literal", "value": "# Results"},
  "evidence_refs": [],
  "status": "pending"
}
```

Supported evaluators:

- Content: `{"type":"exact_sections","level":1,"count":3}` counts Markdown ATX headings at precisely level 1. Levels 1–6 and nonnegative integer counts are accepted. Headings inside backtick/tilde fenced code are excluded. A heading has at most three leading spaces, the registered number of `#` characters, then whitespace or end-of-line. Setext headings, HTML headings, and subordinate heading levels are outside this registered syntax.
- Content: `{"type":"json_field","pointer":"/results/0/estimate"}` requires the RFC 6901 pointer to resolve in parsed JSON. Object keys use `~0` for `~` and `~1` for `/`. Array indexes use canonical nonnegative decimals. Null, false, zero, and empty containers count as existing fields. The empty pointer selects the entire JSON value.
- Content: `{"type":"contains_literal","value":"paper-1"}` requires a case-sensitive exact substring in the UTF-8 target.
- Prohibition: `{"type":"forbidden_literal","value":"banned phrase"}` requires that case-sensitive exact substring to be absent.
- Evidence: `{"type":"evidence_refs"}` resolves every registered evidence file and ID. The registered message or artifact target must also exist. Citation spelling in the target uses a separate `contains_literal` condition; citation-to-claim meaning uses `structured_review`.
- Any new kind: `{"type":"structured_review","role":"quality-b","check_id":"sign-preserved"}` resolves the named check in a structured original review return. Supported roles are `quality-a`, `quality-b`, and `compliance`.

Use `structured_review` for causal claims, domain judgments, and other conditions needing an actual review. Register the specific `check_id` before producing the candidate. Evaluators are fixed built-ins; code, expressions, and arbitrary evaluator names are rejected.

### Evidence files and IDs

A file reference is `{"path":"source.txt"}`. An ID reference is `{"path":"references.json","id":"paper-1"}`. Referenced files must exist and contain non-whitespace bytes. ID lookup uses this JSON structure:

```json
{"records":[{"id":"paper-1","title":"Source title"}]}
```

All records must have unique, nonempty string IDs, and the registered ID must be present. Repeated file/ID references fail validation. An `evidence` condition requires at least one reference. Content and prohibition conditions may use an empty array.

The returned evidence entries include the exact file SHA-256. For citation requirements, pair ID resolution with `contains_literal` for a registered citation spelling, or use a structured review to check the citation's relation to the claim.

### Structured review returns

Supply reviews as an array of records, using `--reviews reviews.json` or the Python `reviews` argument. Each required role resolves to exactly one record. The record supplies:

- `role`, actual `worker_id` and `return_ref`. Independent additionally requires its distinct actual `launch_ref`.
- `execution_status: "completed"` and the frozen `review_kind` (default independent). Explicit self-check is only quality-a with the selected compatible plan, actual author ID, no worker launch and source verification `{status: self-check, reference: ..., verifier_id: AUTHOR_ID}`.
- `return_text`: the original JSON object serialized as text, plus its exact `return_sha256`.
- Independent `source_verification`: `{"status":"matched-to-runtime","reference":"<original runtime reference>","verifier_id":"<verifier>"}`.

The original JSON object supplies quality schema_version 2 or 3 (compliance schema_version 1), the same `role`, `decision: "pass"`, empty `findings`, `unassessed`, and `errors` arrays, and a `checks` object with the registered check set to `"passed"`. Every other reported check must also be passed. It must bind `request_sha256`, `contract_sha256`, and `artifacts_sha256` to the evaluated inputs. The artifacts hash covers the canonical sorted array of `{"path":...,"sha256":...}` entries for the complete supplied snapshot.

A review for `message://final` additionally binds `candidate_sha256` to the exact final-message bytes. Changing line endings, whitespace, or any other message byte invalidates that review. Artifact-target reviews bind their bytes through the complete artifact manifest. The contract hash binds each check ID to its registered target and evaluator.

Any mirrored outer fields must match the original JSON values exactly. A supplied `normalized_return` must equal the parsed original. An outer `decision: "pass"` cannot override an original failure. Plain text such as `OK` is not a structured review.

Missing returns, unfinished reviews, missing source references, and unassessed checks produce an evaluation status of `pending` and an overall `fail`. Failures, stale bindings, contradictory fields, and missing evidence also block overall pass. Passing evaluations retain the actual worker, return reference, return digest, and `authenticated: false`; verify those references against the host's actual launch and return records.

The native checker forwards only role records that passed its original-return, identity, binding, and provenance checks.

## Run the check

```sh
python .agents/harness/requirements_check.py check-requirements \
  --requirements requirements.json --request request.txt \
  --artifacts candidate --events events.json \
  --expected-contract-sha256 THE_RETAINED_HASH \
  --final-message final.txt \
  --reviews reviews.json
```

Omit `--reviews` for contracts evaluated entirely by deterministic checks. Supply `--final-message` whenever a condition targets `message://final`. This file is read separately from the artifact map, preserving every byte. Place metadata and final-message files outside the artifact directory. When reviews are supplied, the adapter collects the complete artifact directory for snapshot binding; otherwise it collects all registered artifact, artifact-target, and evidence paths. Symlink components, paths outside the artifact root, and non-regular files are rejected. The separate message file also rejects symlink components and non-regular files.

Exit 0 means every registered requirement passed. Exit 1 means a requirement is pending, failed, or invalid. JSON output includes `unmet`, `checked`, `source_spans`, and v2 `evaluations`. Each condition evaluation has `pass`, `pending`, or `fail`, the registered `target`, its resolved `target_uri`, the evaluator, and exact source positions. Once the target resolves, its SHA-256 remains in the evaluation even when the predicate fails. `pending` never becomes pass without a completed passing review.

## Python integration

```python
from requirements_check import validate_requirements

report = validate_requirements(
    contract,
    request_bytes,
    artifacts,               # dict[str, bytes], exact safe relative paths
    final_events,
    reviews=usable_reviews,  # list of structured original review records
    contract_sha256=retained_contract_sha256,
    candidate_bytes=final_message_bytes,  # exact UTF-8 bytes; separate from artifacts
)
if report["status"] != "pass":
    display_unmet(report["unmet"])
```

The optional `contract_sha256` binds reviews to the exact serialized contract. Supply the independently retained digest when using a contract file. If omitted, the pure function hashes canonical JSON: sorted keys, compact separators, UTF-8, and unescaped Unicode. The filesystem adapter supplies the exact file digest automatically.

`check_requirements(requirements_path, artifacts_dir, events_path, request_path, expected_contract_sha256, reviews_path=None, final_message_path=None)` retains its existing required arguments and review-path position. `validate_requirements` appends the optional `candidate_bytes` argument after `contract_sha256`. Existing v1 standalone calls retain their signatures and artifact/action predicates.

The filesystem adapter resolves `local-checks` through the adopted policy manifest and its registered layout. Source, deployed and flat packages use the same resolution; the loaded checker and policy module must belong to that manifest. Runtime execution uses the registered-requirement check above.

For structured_review, review_kind defaults to independent. Explicit self-check is valid only for quality-a under the fixed author identity and a compatible direct plan. Native callers pass the fixed review plan and actual author_id to the requirement checker; independent returns retain actual launch/return, source verification and author separation.

## Bidirectional pre-candidate coverage

Native publication uses coverage original schema 3 and the common `validate_request_coverage` check. Keep the original full Unicode-span/quote/hash partition once in `coverage_rows`. The independent extraction binds that source ledger by hash, classifies every requirement as output/content/prohibition/action/authority/completion, and records complete request-to-contract and contract-to-request links, all non-obligation decisions and unresolved ambiguities. It accepts no candidate text. A missing, reclassified or added obligation, omitted reverse link, ambiguous quote position or unsettled non-obligation fails this structural check. Schema 2 remains draft diagnosis only. Structural consistency never authenticates the host original or the independent, candidate-unseen extraction; strict release separately requires those actual host observations.
