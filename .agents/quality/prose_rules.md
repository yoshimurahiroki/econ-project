# JA/EN prose checker dictionary v1.7

## Purpose and scope

Apply the primary expression rule defined in `.agents/harness/policy_assets.py` before every rule below. No lower-priority occurrence, technical-use, quotation or source-identity judgment may weaken it. Delete every disclaimer without exception. Retain 142 rules (71 JA and 71 EN) and the 22 judgments in B25–B31/C01–C15. Remove disclaimers, reservations, concessions, qualifications, embellishment, cautionary or conservative stances, rhetorical framing through supplements or annotations, hedging, weak wording, and self-defense from generated content, expression, choices, and actions. Apply this to body text, headings, figures and tables, footnotes, translations, explanations, links, progress and status reports, quotation selection and explanation, and delegated returns.

## Function and occurrence identity

A machine match identifies an occurrence for review; it does not by itself establish a prohibited function. Retain all matches, including overlapping IDs and positions. The existing quality reviewer establishes sense, syntactic role, target proposition, and surrounding function. Revise occurrences that perform prohibited functions, then recheck surrounding sentences and the completed artifact. Fail unmatched paraphrases that retain prohibited functions.

Do not conclude a judgment from a quotation, code, or technical-term label alone. Return for revision any selection of quotations as substitutes for self-defense or reservations. Where original text is needed, fix its source, version, scope, and verbatim identity, and distinguish quotation from generated explanation. Write generated explanations as direct propositions. Do not register modified quotations as original-source quotations.

## Occurrence records and legacy formats

New quality returns use schema 3 occurrence_judgments. Bind occurrence text, sense and syntax, function and presence of prohibited functions, target proposition, substantive assessment, related claims and sources, and required source identity to the candidate hash and actual constituent characters. Apply the same mechanism to original titles, proper names, dates, logical conditions, ordering relations, technical terms, and distinct words; do not add word-specific allowlists.

An occurrence claiming source identity must have an exact match between the fixed source quote and the candidate's target span. Sense and syntax review and verbatim source comparison are separate checks. Neither permits prohibited functions. Machine checks verify structure, spans, hashes, original returns, and agreement among selected quality reviewers. direct uses author self-review, focused uses the selected independent reviewer, and full uses substantive judgments from both quality reviewers.

Validate legacy schema 2 technical_usages and source_reproductions under their original strict conditions, then convert them into read views for shared and occurrence review. Do not change original return text or hashes. A legacy quotation record alone does not clear a prohibited match. Do not include legacy technical_usages alongside the new format. Follow [native check](../harness/native_check.md#prohibition-and-technical-use) for API and migration conditions.

## Machine detection and whole-text review

Keep the base action of all 142 rules as block; scan returns resolution: occurrence-review-required. Do not pass unreviewed matches. Preserve all constituent characters and coordinates in raw-source, display-approximation, and whitespace-normalized views. Do not clear a combined span containing unrelated HTML attributes, comments, or adjacent occurrences. technical_terms is an index for definition references, not automatic clearance. Obtain new occurrence judgments whenever the candidate hash changes.

For `python3 .agents/harness/local_checks.py scan-text --input FILE --dictionary .agents/quality/prose_rules.json`, status: scanned records that scanning occurred, not that the prose passed. Build an inspection view with NFKC/casefold without overwriting the original text. Compare internal extraction views with final renderings for rendered artifacts. Consult matched rules and necessary definitions; rereading the entire dictionary every time is not required. Conduct the 22 whole-text functional checks even when there are no dictionary matches.

<a id="共通台帳と全文審査"></a>

## Shared ledger and whole-text review

Schema 3 records the whole-text target path, candidate hash, claim ledger hash, and substantive assessment once, and returns verdicts for all 22 IDs. Do not repeat every claim ID under every check. Register propositions in the evidence ledger; review navigation headings, connective text, symbols, and similar elements as information structure in whole-text review. Register headings containing quantities or conclusions as propositions. Check for unregistered propositions through machine checks for missing numerical content and the reviewer's whole-text comparison.

Bind findings and unevaluated items to existing check IDs, candidates, locations, target propositions, and sources. Do not treat generic declarations of checking as execution evidence or record internal thought processes. Fix the actual bytes of outbound progress, status, and error messages as separate surfaces within the same parent run, distinct from its final candidate. Scan all 142 rules. Both existing quality reviewers refer to the same text and shared proposition/source ledger and each records the 22 whole-text judgments and occurrence judgments in their original returns. Do not overwrite the parent's final candidate, review records, or unfinished requirements, duplicate ledgers per reviewer, or create separate tasks. Sending a surface requires comparison with its actual reviewer returns and execution evidence; this is distinct from release approval for the final artifact. Map execution status to actual tool returns.

## Categories and counts

Version 1.7 has 142 rules (71 JA and 71 EN), all with base action block. Preserve rule IDs and counts. Each rule detects an expression family with shared syntax and inflections, not just individual examples. Extend families only within the same prohibited function. The 142 rules are a detection index for locating matches, not a requirement for 142 separate semantic judgments. Retain the seven B25–B31 checks and fifteen C01–C15 checks as semantic and functional audits independent of dictionary detection. Include quotations and bibliography in every check.

### A: Index of 24 categories

The following maps categories to rule IDs; it does not authorize retention based on necessity or context.

- A01 Unnecessary prefaces and emphasis on the obvious: ja-041, en-041.
- A02 Self-reference and declarations of speaking stance: ja-042, en-042.
- A03 Self-defense and preemptive justification: ja-043, en-043.
- A04 Ritual concessions and unnecessary adversatives: ja-044, en-044.
- A05 Vague warnings and cautionary stances: ja-045, en-045.
- A06 Disclaimers, avoidance of responsibility, and generic qualifications: ja-046, en-046.
- A07 Unsupported hedging and weak assertions: ja-047, en-047.
- A08 Indirect assertions and unnecessary speculation: ja-048, en-048.
- A09 Embellishment and excessive valuation: ja-049, en-049.
- A10 Unnecessary negative contrasts and artificial emphasis: ja-050, en-050.
- A11 Low-content buffers and filler: ja-051, en-051.
- A12 Reader instructions, reminders, and persuasive prefaces: ja-052, en-052.
- A13 Excessive agreement, praise, and ingratiation: ja-053, en-053.
- A14 Excessive empathy and emotional buffering: ja-054, en-054.
- A15 Self-justification and evasive explanations of failure: ja-055, en-055.
- A16 Unnecessary apologies and ritual refusals: ja-056, en-056.
- A17 Answer deferral, unnecessary clarification, and execution avoidance: ja-057, en-057.
- A18 Empty generalizations and explanations lacking specifics: ja-058, en-058.
- A19 False neutrality and purposeless presentation of both sides: ja-059, en-059.
- A20 Answer avoidance through abstraction: ja-060, en-060.
- A21 Redundant summaries and closings: ja-061, en-061.
- A22 Unsupported self-evaluation and exaggerated results: ja-062, en-062.
- A23 Unnecessary additional suggestions and conversation extension: ja-063, en-063.
- A24 Excessive metaphors, promotional language, and theatrical wording: ja-064, en-064.

### B: Seven semantic judgments

- B25 Uncertainty: Reject every mention of uncertainty on every surface, including indirect formulations, quotations, bibliography, technical terminology, forecasts and probability statements. No context or source-identity exception applies. The primary expression rule governs this check before all occurrence and technical-use judgments.
- B26 Conditions and scope: Prohibit reservations, qualifications, and buffers justified by conditions or scope. State the target set and applicable conditions directly. Inspect the entire text, including quotations and bibliography. Do not retain prohibited functions. Review sense, syntax, target proposition, and the role of the wording.
- B27 Approximation and quantity: Prohibit vague wording justified by approximation or quantity. State rounding rules, bounds, and comparison criteria directly. Inspect the entire text, including quotations and bibliography. Do not retain prohibited functions. Review sense, syntax, target proposition, and the role of the wording.
- B28 Negation and contrast: Prohibit concessions, reservations, and ornamentation justified by negation or contrast. State truth conditions, competing hypotheses, and choices directly. Inspect the entire text, including quotations and bibliography. Do not retain prohibited functions. Review sense, syntax, target proposition, and the role of the wording.
- B29 Exceptions and exclusions: Prohibit reservations justified by exceptions or exclusions. Define the target set and necessary and sufficient conditions directly. Inspect the entire text, including quotations and bibliography. Do not retain prohibited functions. Review sense, syntax, target proposition, and the role of the wording.
- B30 Inference and attribution: Prohibit indirect and weak wording justified by inference or attribution. State the reporting party, assumptions, and inferential relationships directly. Inspect the entire text, including quotations and bibliography. Do not retain prohibited functions. Review sense, syntax, target proposition, and the role of the wording.
- B31 Domain-based qualification: Reject domain-based disclaimers, cautionary stances and qualifications. Apply the primary expression rule first. Technical terminology, confidence intervals, estimation errors, source quotations and specialized context create no exception. Review the entire candidate, including quotations and bibliography, and retain only content that satisfies the governing rules.

### C: Fifteen functions covering unmatched paraphrases

Each quality reviewer in the selected plan returns judgments, locations, evidence, and source correspondence for every check across the entire text. Leave no prohibited functions in quotations or bibliography. Classify rhetorical framing through supplements or annotations under the existing check for its function: C01 for reservations or qualifications, C03 for disclaimers, C06 for self-defense, C14 for indirection, and so on. Moving wording into footnotes or postscripts, or recognizing technical usage or a distinct word, does not clear a judgment. Retain the 22 checks and existing review stages.

- C01 Rhetorical reservations: Wrap a claim in reservations, qualifications, or a cautionary stance. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action. Do not move reservations or qualifications into supplements, annotations, postscripts, or parentheses.
- C02 Ritual concessions: Add concession structures or a concessive stance. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action.
- C03 Preemptive disclaimers: Add framing that disclaims or avoids responsibility. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action.
- C04 Unnecessary negative contrasts: Compare the propositions in the sentence and the overall request. Remove negative contrasts that add ornamentation or emphasis. Do not retain prohibited functions.
- C05 Empty warnings: State a cautionary stance instead of concrete subjects or actions. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action.
- C06 Self-defense: Defend the respondent’s good intentions, intent, effort, or legitimacy. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action.
- C07 Issue avoidance: Replace a concrete request with generalities, methodology, or problem statements. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action. For decision requests, connect the requested choice, adopted objective and binding constraints, comparison criteria, selected result, and next execution step to the original request. For prose revision, address the target proposition and defects in expression.
- C08 Unsupported presentation of both sides: Obscure the answer by presenting both sides without a judgment. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action. For decision requests, connect the requested choice, adopted objective and binding constraints, comparison criteria, selected result, and next execution step to the original request. For prose revision, address the target proposition and defects in expression.
- C09 Vague degree expressions: Wrap quantities or comparisons in vague degree expressions. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action.
- C10 Unsupported self-evaluation: Wrap execution results in self-evaluation or exaggeration. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action.
- C11 Unnecessary conversation extension: Append unrequested conversation extensions to a completed answer. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action.
- C12 Supplements, annotations, and redundant self-contained explanations: Append explanations outside the claim as supplements, annotations, or postscripts. Delete sentences that do not contribute to the judgment. Remove repeated definitions, background, and premises. Do not use quotations, bibliography, technical terminology, or necessity as reasons for retention.
- C13 Meaningless emphasis: Wrap a claim in embellishment or theatrical emphasis. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action.
- C14 Indirect assertions: Wrap a claim in indirect assertions or weak wording. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action.
- C15 Unrequested safety explanations: Emphasize a safe, cautious, or conservative stance instead of concrete hazards and required actions. Do not justify a prohibited function through context, a specialized domain, good intentions, or necessity. Judge the actual function of the sense, syntax, proposition, and action.
