# Registered requirements: contracts v1 and v2

This local stdlib-only checker evaluates registered requirements against exact final-message bytes, artifact bytes and final action records. Use Python 3.9+. It makes no network requests.

## Register and freeze the requirements

Save the exact UTF-8 user request as `request.txt`. Each requirement has a unique `id`, a `kind`, and a nonempty `source_text` quotation that occurs exactly in the request. Compare the original request with the complete requirement list before producing the candidate. Register each requested output, action, content condition, prohibition, and evidence condition.

For inherited instructions, v2 additionally accepts the paired `sources` and `request_source_id` fields. Each source has exactly `source_id`, `version` (a nonempty string or nonnegative integer), `content_sha256` and exact UTF-8 `content`. The current-request source must reproduce request.txt bytes. Each requirement then requires its own `source_id`; all quoted spans use that source's Unicode coordinates. Missing, duplicate, stale or mismatched IDs/hashes fail validation. The existing single-request form remains the implicit default source and keeps its original span shape. Sources are pinned inside requirements.json so subsequent transitions retain them. Preserve prior sources and prohibitions when a later request says to continue; only an actual user change updates that contract. Exact quote matching does not establish semantic completeness of the registered requirements.

An operation prohibition uses kind `prohibition`, exact `target`, evaluator `{"type":"forbidden_operation","operation":"..."}`, evidence_refs and pending status. It compares every recorded action's operation/target, including a failed attempt; matching events fail. A logged prohibited attempt may identify its prohibition requirement_id. Existing action records and their actual tool-return verification remain required. No matching event describes only the supplied log, not an authenticated history or preventive permission control. Use forbidden_literal for forbidden output text; the two predicates are separate.

Each requirement accepts an optional `source_span: {"start": 0, "end": 36}`. Offsets count Unicode characters in the decoded original request, starting at zero, with an exclusive `end`. The selected substring must equal `source_text` exactly. UTF-8 byte offsets, UTF-16 code units, normalized text, and offsets into a reconstructed request fail this comparison. When `source_span` is absent, the checker derives every exact occurrence, including overlapping occurrences. Repeated quotations retain every occurrence; an explicit span selects one. Freeze and check results expose these exact positions in `source_spans`, keyed by requirement ID. Condition evaluations and checked entries also carry their positions. Derivation leaves the contract bytes and hash unchanged.

The basic contract has three top-level fields. Version 2 also accepts the paired source fields above and the optional traceability array below.

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
python harness/requirements_check.py freeze-requirements \
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
- Evidence: `{"type":"evidence_refs"}` resolves every registered evidence file and ID. The registered message or artifact target must also exist. Citation spelling in the target uses a separate `contains_literal` condition.

Evaluators are fixed built-ins; code, expressions, and arbitrary evaluator names are rejected. A semantic or domain judgment requires actual assessment outside these deterministic predicates.

### Evidence files and IDs

A file reference is `{"path":"source.txt"}`. An ID reference is `{"path":"references.json","id":"paper-1"}`. Referenced files must exist and contain non-whitespace bytes. ID lookup uses this JSON structure:

```json
{"records":[{"id":"paper-1","title":"Source title"}]}
```

All records must have unique, nonempty string IDs, and the registered ID must be present. Repeated file/ID references fail validation. An `evidence` condition requires at least one reference. Content and prohibition conditions may use an empty array.

The returned evidence entries include the exact file SHA-256. For citation requirements, pair ID resolution with `contains_literal` for a registered citation spelling. Assess the citation's relation to the claim separately.

## Run the check

```sh
python harness/requirements_check.py check-requirements \
  --requirements requirements.json --request request.txt \
  --artifacts candidate --events events.json \
  --expected-contract-sha256 THE_RETAINED_HASH \
  --final-message final.txt
```

Supply `--final-message` whenever a condition targets `message://final`. This file is read separately from the artifact map, preserving every byte. Place metadata and final-message files outside the artifact directory. The adapter collects all registered artifact, artifact-target, and evidence paths. Symlink components, paths outside the artifact root, and non-regular files are rejected. The separate message file also rejects symlink components and non-regular files.

Exit 0 means every registered requirement passed. Exit 1 means a requirement failed or is invalid. JSON output includes `unmet`, `checked`, `source_spans`, and v2 `evaluations`. Each condition evaluation has `pass` or `fail`, the registered `target`, its resolved `target_uri`, the evaluator, and exact source positions. Once the target resolves, its SHA-256 remains in the evaluation even when the predicate fails.

## Python integration

```python
from requirements_check import validate_requirements

report = validate_requirements(
    contract,
    request_bytes,
    artifacts,               # dict[str, bytes], exact safe relative paths
    final_events,
    contract_sha256=retained_contract_sha256,
    candidate_bytes=final_message_bytes,  # exact UTF-8 bytes; separate from artifacts
)
if report["status"] != "pass":
    display_unmet(report["unmet"])
```

The optional `contract_sha256` must be a lowercase SHA-256 digest. Supply the independently retained digest when using a contract file. If omitted, the pure function hashes canonical JSON: sorted keys, compact separators, UTF-8, and unescaped Unicode. The filesystem adapter supplies the exact file digest automatically.

`check_requirements(requirements_path, artifacts_dir, events_path, request_path, expected_contract_sha256, final_message_path=None)` validates the pinned contract file and collects the registered files. `validate_requirements` accepts optional `contract_sha256` and `candidate_bytes` arguments. Version 1 artifact and action predicates remain available.

The filesystem adapter resolves `local-checks` through the adopted policy manifest and its registered layout. Source, deployed and flat packages use the same resolution; the loaded checker and policy module must belong to that manifest. Runtime execution uses the registered-requirement check above.

## Analyze an adopted implementation specification

Select this contract when the task calls for specification analysis or implementation reconciliation. Add `traceability` to the existing version-2 requirement object, with one row for every requirement ID:

```json
"traceability": [{
  "requirement_id": "report",
  "task_ids": ["report-task"],
  "code_paths": ["analysis.py"],
  "check_ids": ["report-calculation"],
  "check_commands": {"report-calculation": "python tests/test_report.py"},
  "decision_refs": [{"decision_id": "outcome", "version": 1, "choice": "weekly hours"}],
  "depends_on": [],
  "constraints": {"report.outcome_unit": "hours per week"}
}]
```

`task_ids` identify the existing task records; `check_ids` identify their declared checks. `check_commands` pins each executable check's exact producing command; omitted check IDs have no pinned command in this mapping. `code_paths` identify the implementation files and may be empty for a delivery operation. `decision_refs` pin adopted decision IDs, versions and choices. `depends_on` names prerequisite requirement IDs. Every list contains distinct values. `constraints` maps a fully qualified property name to its adopted finite JSON scalar value. Use the same property key wherever specifications constrain the same object.

`analyze_requirements(contract, request_bytes, *, tasks=None, context=None, code_files=None)` checks requirement coverage, reference shape, prerequisite cycles, conflicting property values, required text containing forbidden text, and required operations matching prohibitions. Supplied task records additionally establish task/check existence; a supplied governing context establishes decision correspondence; supplied code bytes establish implementation presence and hashes. The result contains `status`, `findings`, `mappings` and `code_hashes`. Each finding identifies its requirement and affected check, task, decision or path. The state adapter supplies all these current inputs through [Analyze and Converge](state.md#analyze-and-converge).

Read the actual requirement and implementation when judging semantic correspondence. Encode a computable acceptance condition with the existing predicates, and record a substantive judgment through the applicable project process. Preserve the original requirement, source span and amendment authority when repairing its implementation.
