# Local checks and snapshots

`local_checks.py` supplies UTF-8 text scanning, JSON loading, exact hashes, safe relative paths and atomic storage to the existing task and research owners.

## Text scanning

```sh
python harness/local_checks.py scan-text --input answer.md --dictionary quality/prose_rules.json
```

The scanner uses NFKC/casefold, original source, rendered-label and whitespace views. Markdown labels use the canonical parser in `scripts/route_registry.py`, or its sibling in a flat export. It retains raw source-character intervals across Markdown, HTML entities and TeX argument projection. English lexical boundaries preserve complete words next to other writing systems. Every match has its input hash, rule ID, contributing character spans and source coordinates. [PROSE's review contract](../runtime/PROSE.md#finish-the-passage) owns activation, meaning and rhetorical judgment for these locations and unmatched wording.

## Input and storage

Reject duplicate JSON keys, nonfinite JSON, nonregular files, symlinks and unsafe output paths. `release(artifacts, output, input_hashes=None)` writes the supplied fixed bytes into a same-parent temporary generation, verifies them, rechecks selected input hashes and publishes without replacing an existing destination. Failure retains the earlier destination. This is file storage, not publication authorization.

## Outgoing text and lexical/use judgments

`scan-text` reports positions and counts, omitting candidate wording and examples. Exit zero means scanning completed. `--require-clean` returns exit one when matches remain. `semantic_review: not-performed` describes the scanner itself. [CORE](../runtime/CORE.md#completion-and-reporting) owns the integrated review and completion.
