# JA/EN prose checker dictionary v1.8

## Purpose and scope

Treat 「わけではありません」「区別が必要です」「実施されていません」 and semantic variants as rewrite triggers in existing ja-068, en-068, B28 and C04. Reconstruct the complete claim and paragraph around the actual definition, actor, operation or measured comparison. Preserve source truth conditions and values; state a zero only when the actual record establishes it.

The 142 existing JA/EN patterns and all 22 semantic criteria govern ordinary composition and the mandatory integrated editorial review in [PROSE](../runtime/PROSE.md#finish-the-passage). Judge the claim, paragraph and argument by their meaning, including paraphrases absent from the dictionary. Eliminate defensive reservations, artificial contrasts, filler and evasive language by rebuilding the substantive explanation. Complete the explanation before shortening it.

An explicitly selected exhaustive review activates the existing full scan and required records. Ordinary writing applies the same substantive criteria within its integrated editorial review.

## Function and occurrence identity

When the user requests lexical review, each match identifies a location to examine. The verdict follows the expression's actual function in its proposition and paragraph. Preserve quantities, comparisons, source attribution and truth conditions when rewriting. A zero match count establishes only the scan result; the integrated meaning and style review remains mandatory.

## Occurrence records and legacy formats

Only formal reviews that actually use the legacy checker produce its expected occurrence records. Keep the candidate and source bytes consistent within that workflow.

## Machine detection and whole-text review

Use the existing [prose dictionary](prose_rules.json) and `.agents/harness/local_checks.py scan-text` for an explicitly selected scan or a concrete consequential defect that satisfies CORE's verification rule. Perform the one integrated editorial review on the actual final text, repair the defects found and reread their affected passages. Fixed sentence lengths, uniform paragraph templates and automated scores supply no substitute for this review.

<a id="共通台帳と全文審査"></a>

## Shared ledger and whole-text review

An explicitly selected certified full-text review uses the existing 22 judgments and source correspondence with its required records. Ordinary writing completes these substantive judgments in the integrated editorial review.

## Categories and counts

The dictionary contains 142 lexical patterns, 71 Japanese and 71 English, and 22 semantic criteria. Keep the original enumerated patterns in the JSON as the sole machine-readable source.

### A: Index of 24 categories

The `source_categories` objects in the dictionary provide the authoritative categories.

### B: Seven semantic judgments

B25–B31 address hedging, conditions, vague quantities, negation and contrast, exceptions, inference and domain-specific caution.

### C: Fifteen functions covering unmatched paraphrases

C01–C15 cover defensive reservation, concession, disclaimers, empty contrasts, filler, evasive reasoning and similar functions. Apply these meaning judgments during ordinary writing, including unlisted paraphrases. The selected formal workflow records the judgments in the existing fields.
