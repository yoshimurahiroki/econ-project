# Expression review pointer

1. **Source first → located passage → composer.** [PROSE Common output](../runtime/PROSE.md#common-output) owns the source-borrowing procedure for every element of English and Japanese prose, papers, materials, slides and Beamer. The [recurring-pattern table](prose_rules.json) maps locators to its steps; `python harness/local_checks.py scan-text --input FILE --dictionary quality/prose_rules.json` returns source positions.
2. **Revised artifact → final review.** Apply the complete [finish procedure](../runtime/PROSE.md#finish-the-passage) to meaning and rhetorical function, including passages beyond the listed locators. A locator or a record supplements reading the source.
