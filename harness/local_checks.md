# Local checks and snapshots

`local_checks.py` supplies UTF-8 text scanning, JSON loading, exact hashes, safe relative paths and atomic storage to the existing task and research owners.

## Text scanning

```sh
python harness/local_checks.py scan-text --input answer.md --dictionary quality/prose_rules.json
```

The scanner uses NFKC/casefold, original source, rendered-label and whitespace views. It retains raw source-character intervals across Markdown, HTML entities and TeX argument projection. English lexical boundaries preserve complete words next to other writing systems. Every match has its input hash, rule ID, contributing character spans and source coordinates. These identify a passage; CORE and PROSE own its meaning and rhetorical function.

The compact dictionary groups concrete phrasing. General negation, bounds, model conditions and source attribution keep their actual content. Definitions and unmatched paraphrases are judged in the same integrated review. No technical-term approval index, individual occurrence record or separate meaning checklist is required.

## Input and storage

Reject duplicate JSON keys, nonfinite JSON, nonregular files, symlinks and unsafe output paths. `release(artifacts, output, input_hashes=None)` writes the supplied fixed bytes into a same-parent temporary generation, verifies them, rechecks selected input hashes and publishes without replacing an existing destination. Failure retains the earlier destination. This is file storage, not publication authorization.

## Outgoing text and lexical/use judgments

`scan-text` reports positions and counts, omitting candidate wording and examples. Exit zero means scanning completed. `--require-clean` returns exit one when matches remain. `semantic_review: not-performed` describes the scanner itself. The task owner completes one integrated review of the result and requested operations through CORE, PROSE and EXECUTION. Actual output versions and returned actions establish completion.
