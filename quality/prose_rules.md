# Lexical detection and integrated review

[CORE](../runtime/CORE.md), [PROSE](../runtime/PROSE.md) and [EXECUTION](../runtime/EXECUTION.md) own the single integrated review of the requested result, its truth conditions, argument, expression and completed operations.

The [dictionary](prose_rules.json) groups concrete Japanese and English phrasing by rhetorical function. The existing scanner preserves source coordinates across Unicode, markup and whitespace views. Matches locate passages for the same integrated review; a match is not a semantic verdict. Assess negation, scientific uncertainty, mathematical bounds, model conditions and source attribution through their actual propositions under PROSE.

PROSE permits statistical uncertainty only as numerical measures or numerical interval/set notation with the labels, confidence levels and units needed to read them. Retain valid standard errors, confidence or credible intervals and p values. Qualitative uncertainty, hedging and significance stars remain outside that reporting form; a lexical match alone does not invalidate a numerical report.

Use `local_checks.py scan-text` to locate lexical candidates. Its default diagnostics return positions and counts without reproducing candidate text. The supported Stop hook requires a post-draft semantic review of every part of the final response, tied to its exact text. Review authored artifacts and the entire proposition as well; a lexical scan does not certify semantic compliance. Complete the reasoning or operation that produces the corrected artifact, then inspect the affected result.
