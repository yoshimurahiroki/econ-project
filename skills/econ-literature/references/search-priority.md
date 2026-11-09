# Select literature by fit, venue and execution date

## Establish the comparison

Recover the requested population, intervention, outcome, mechanism, estimand and research design. A request for directly matching studies retains only studies whose inspected body establishes that match. Search the existing source corpus first and carry its stable study identities into additional discovery. A requested additional search acquires new sources, queries, years or citation links.

Use the single journal and working-paper classification owned by the literature source implementation. `research_sources.py search-plan --field FIELD --output DIR` returns the selected field, aliases, explicit leading-journal boundary and execution-date windows; repeat `--field` for a cross-field question. Apply the user-adopted venue order, with [Economists Japan](https://sites.google.com/site/economistsjapan/journals) and [RePEc](https://ideas.repec.org/top/top.journals.all.html) as source references. Keep a ranking source's date with its provenance. Update a changed journal name, official destination or field classification when the current search encounters it.

## Compute the search periods

Record the search's actual current date and let its calendar year be Y. Compute the following periods at execution:

| Priority | Publication or release years |
| --- | --- |
| R0 | Y−2 through Y |
| R1 | Y−5 through Y−3 |
| R2 | Y−9 through Y−6 |
| R3 | Y−10 and earlier |

Start with R0 at the five leading economics journals and the selected fields' leading journals, alongside new W1 and relevant W2 papers. Expand through R1 and R2. Retrieve foundational theory, identification and estimation papers through R3 and the selected studies' citations. The current date determines these periods on every execution. A year change requires no revision of the rules or ranking data.

## Rank the matching studies

Verify direct subject fit first. Within directly matching candidates, use this order: published or forthcoming papers in the five leading economics journals; published or forthcoming papers in the field's leading journals; recent, directly matching W1 papers; major field journals and relevant W2 papers; other matching journals and working papers. Within a venue tier, prioritize substantive fit and the study's relevant method specialization, then execution-year recency and the adopted venue order. Citation counts and search rank provide discovery leads.

W1 comprises NBER, CEPR and Becker Friedman Institute. W2 comprises IZA, IFS, World Bank Policy Research Working Papers, IMF Working Papers, and relevant official central-bank, university and research-institute series. Use SSRN and arXiv to discover and obtain manuscripts. Confirm a working paper's actual content, author expertise, identification, revisions and acceptance/publication record before its final placement.

For a cross-field question, search each field's leading journals in parallel. Use that field's journal standing and the common research-question match when comparing the returned studies. Apply the shared priority to selection, paper introductions, prior-research comparisons, design choices and writing.

## Reconcile the study and its editions

Keep working-paper first release and revisions, acceptance and forthcoming status, online-first date, issue publication year, and the latest manuscript revision as distinct source fields. Match explicitly linked DOI and working-paper identifiers, authors and titles through the existing source record. Confirm title variants and editions from their original records. One study occupies one selection position; retain its edition history and links.

Use the latest formal publication information and available manuscript. Keep the first-release date and the date used for the current selection with their source. A publication-status change updates that study and the existing claims or uses affected by its changed edition. Reuse unchanged source bytes and completed calculations.

## Search crime, policing and criminal justice

Begin with the current [Jennifer Doleac Crime papers spreadsheet](https://docs.google.com/spreadsheets/d/1zyRB708QpsxG_8vNCRl7gv5FyrPE81w3mF_kMVJlHbY/edit) metadata and tab inventory. Select Accepted, the latest existing annual tab, the preceding two existing annual tabs, and older years needed by the question. Obtain each actual sheet ID from that inventory. Read Overview for coverage. Record the source's returned modification date and coverage date with their original fields; obtain later research from official journals and working-paper series.

Read the current [Doleac Resources page](https://jenniferdoleac.com/resources/), its Economics of crime research material and the thematic Literature reviews relevant to the question. Follow the currently published links. Use the adopted C0, C1 and C2 orders and the relevant adjacent-field and theme priorities. Criminal-justice questions search the leading C2 venues alongside C0 and C1. The latest annual tab and current journal/WP records supply new years through the same procedure.

## Read and hand forward the selected evidence

Read the selected study's abstract and the original model, identification, estimator and result passages through [paper reading](paper-reading.md). Follow determining tables, notes, proofs and appendices. Retain exact edition, source/page hashes and inspected locators in the existing source record. Preserve Crossref retrieval, OpenAlex forward/backward discovery and BM25 search of stored materials through their existing owners.

For each introduced study, carry title and authors, journal or WP series, publication status, first release and formal publication year, field priority, population/intervention/outcome, identification and estimator, main finding, concrete task match, and DOI or direct original URL. Present studies in the selected priority order. Pass these same fields and supporting passages to econ-design, econ-review and econ-writing; each owner uses the source for its requested result.
