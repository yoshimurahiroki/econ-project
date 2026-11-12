# Compose and deliver a research artifact

Select the sections needed by the requested output under the [shared writing contract](../SKILL.md).

## Generate articles and slides from results

Select `research_result_artifacts` and use [result artifacts](result-artifacts.md) to register named quantities and units from saved estimates, preserve their covariance and inference, and generate the requested article, table, figure and slide sources through the existing research DAG. Materialize the project's adopted artifact specification from its completed results and authored text. Bind the adopted equations and parameters to their actual code, specification and result. A changed producer or result rebuilds its affected consumers while preserving completed generations. Use the same selected quantities when revising article and slide arguments. Select `research_meeting_materials` for [meeting materials](../../../harness/meetings.md) assembled from saved displays and GitHub progress, with editable Markdown, Quarto rendering and independent native Google Slides editions.

For a theory or structural presentation, select the existing `model` or `structural` material template. Keep derivations, proofs and additional results in internal research records. Supply adopted equations and explanations through `project-view.section_content` and select the saved parameter, fit, equilibrium and welfare displays by their result IDs. Their `metadata.report_role` places each display in the corresponding section. CLI and gallery read these templates from the same `tex/slides/meeting_templates.json`; presentation edits reuse the saved scientific result.

## Compose a talk

1. **Output: argument sequence; consumer: slide author.** Connect the audience's question, actors' choices, identifying comparison, evidence and answer. Allocate the requested speaking time to the relations establishing that answer. Give each page one inference and its required premises; define quantities before using them.
2. **Output: page content; consumer: template.** Write a short nominal title naming the economic object and relation. Put the supported proposition in the first sentence, then its equation or saved exhibit and the sentence explaining its implication. Before: “結果を説明する” followed by a table alone. After: “利用支援と契約継続” followed by the saved effect, its group comparison and the allocation implication. A section divider names the next argument; a results page completes an inference.
3. **Output: composed page; consumer: renderer.** Set body, bullets and table text to a 24 pt baseline in screen slides, Beamer and native Slides; CSS 24 pt equals 32 px. Use the existing bundle's `title`, body, `artifacts` and `layout`. Use `stack` for a claim and a wide table; `figure-left` for a figure beside its interpretation; `figures` for comparable panels with common scales. Place population, period and units beside the exhibit. Attach its explanatory body to the same section and set the consumed summary section's `visible` to `false`. Fit dense content by splitting its argument across pages. Before: “Shrink the table to 10 pt.” After: “Keep 24 pt and give each comparison its own page.” Keep derivations and diagnostic commentary at their internal owners.
4. **Output: inspected talk; consumer: audience.** Render through the existing path and inspect every changed page at presentation size. Read the title, claim, exhibit and implication in that order. Check that mathematical symbols, row labels and intervals are legible from the same view. Repair the producing layout or text, then inspect affected outputs against the adopted argument and duration.

The existing [meeting template](../../../tex/slides/meeting_template.qmd) owns screen settings. The [Beamer source](../../../tex/slides/main.tex) and its generated [adapter](../../../tex/slides/pandoc_template.latex) share PDF typography. Adopt the model material's composition within the user's 24 pt baseline. Inspect the actual rendered fonts and page size; a Beamer class option alone does not establish the body size.

| Element | Screen slides | Beamer slides | HTML research document |
|---|---|---|---|
| Page and text block | 1280 × 720, top-aligned, 7% outer margin | 960 × 540 PDF points, top-aligned, 54-point side margins | 44 rem reading column |
| Title and section heading | 40 pt title, 32 pt nominal heading | 40 pt title, 32 pt frame title | 34 px title, 25 px section heading |
| Main text | 24 pt / 32 px, line height 1.45 | 24 pt, 30 pt baseline spacing | 18 px, line height 1.8 |
| Table | 24 pt, aligned numeric columns | 24 pt, 8 pt column padding | 16 px, horizontal rules |
| Supporting quantity definition | 20 pt | 20 pt | 16 px |

Use the selected font family consistently within each medium. A populated template carries the full question-to-answer sequence and original prose, equations and saved exhibits. The [subscription material producer](../../econ-data/examples/subscription/materials.py) supplies a same-result bilingual example; run its [documented commands](../../econ-data/examples/subscription/README.md) to inspect the actual pages.

## Compose a research site

Use the project's existing publication and analysis objects and preserve canonical links. Select the question, result and evidence each page needs, then adapt the complete explanation to the page's reading order.

## Render the requested artifact

Use the existing build path and view the actual resulting page or slide when layout affects delivery. Avoid unrelated rebuilds.

For a new LaTeX paper, start from the supplied [Econometrica template](../../../tex/paper/ecta_template.tex) with its class, configuration and bibliography style. For new slides, use the supplied [Beamer template](../../../tex/slides/main.tex), retaining metropolis, Waseda colors and Harano Aji Japanese fonts. Fill the intended author, title, abstract, keyword and body placeholders from the requested content. The [shared build helper](../../../scripts/build_latex.py) owns LuaLaTeX compatibility, citation processing and preservation of the previous PDF on failure. The [result-artifact renderer](result-artifacts.md) and Quarto consume the same default family through their produced Pandoc adapters. Preserve a user's adopted document format and existing research files when the request concerns only new defaults.

## Execute paragraph and argument contracts

Consult [paragraph guidance](paragraph-workflow.md) when a complex long-form argument needs structure. Perform its argument and paragraph reasoning in the draft and include it in the common integrated review. Use its existing state and source bindings when the requested composition needs persistent dependencies. Complete the same integrated review and actual delivery path.

## Compose for the medium and language

A requested model material supplies the composition pattern. [Profile authoring](profile.md#profile) records its page measurements and argument operations, produces the complete original example and compares the rendered output with the original. Use that adopted pattern in the selected existing template with the current study's specification and saved results.

A local revision or translation uses its selected mode and surrounding premises. A paper section uses the relevant [paper guidance](paper-workflow.md#compose-the-requested-section); a consequential long-form structural choice uses [paragraph guidance](paragraph-workflow.md). Retrieve profile examples only for a remaining language choice.

Select the paper guidance for the actual scientific argument: empirical identification and contrasts, structural estimation/equilibrium/welfare, or theory/proof. Bind numerical text, equations and exhibits through the selected [result contract](result-artifacts.md). Preserve estimated/calibrated/fixed parameter roles and each quantity's population, timing, units, denominator and scenario. Resolve a missing derivation or comparison through econ-design/data within the existing editing authority, then update affected passages and exhibits.

Match content to its purpose: an explanation connects finding and mechanism; a decision report compares feasible actions; a proposal connects the obstacle to deliverables and resources; a progress review states the new result's implication for the adopted decision and next action. Before a meeting or review, state the unresolved decision, current hypothesis and evidence needed to resolve it. Prepare discussion around the actual disputed premise, fact or criterion. Explain the exhibit-to-conclusion inference when the reader needs that step. Requested records retain decisions, basis, responsibility, timing and dependencies in existing project context. The reader's decision determines detail and cadence supplies no additional template.
