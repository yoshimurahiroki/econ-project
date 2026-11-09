# Compose and deliver a research artifact

Select the sections needed by the requested output under the [shared writing contract](../SKILL.md).

## Generate articles and slides from results

Select `research_result_artifacts` and use [result artifacts](result-artifacts.md) to register named quantities and units from saved estimates, preserve their covariance and inference, and generate the requested article, table, figure and slide sources through the existing research DAG. Materialize the project's adopted artifact specification from its completed results and authored text. Bind the adopted equations and parameters to their actual code, specification and result. A changed producer or result rebuilds its affected consumers while preserving completed generations. Use the same selected quantities when revising article and slide arguments. Select `research_meeting_materials` for [meeting materials](../../../harness/meetings.md) assembled from saved displays and GitHub progress, with editable Markdown, Quarto rendering and independent native Google Slides editions.

For a theory or structural presentation, select the existing `model` or `structural` material template; use `appendix` for derivations, proofs and additional results. Supply adopted equations and explanations through `project-view.section_content` and select the saved parameter, fit, equilibrium and welfare displays by their result IDs. Their `metadata.report_role` places each display in the corresponding section. CLI and gallery read these templates from the same `tex/slides/meeting_templates.json`; presentation edits reuse the saved scientific result.

## Compose a talk

Build the talk around the audience's question, the economic comparison that answers it and the action or understanding that follows. Develop the complete explanation first. Arrange its necessary premises and results in the order a listener can use them, allocating the requested speaking time to the relations that determine the answer.

For each screen, state the proposition the audience should recover and choose the saved result, equation or diagram that establishes it. Define actors and quantities before using them in a mechanism. On an exhibit, identify the objects compared, their units and the contrast carrying the conclusion. Explain that contrast aloud before advancing to its implication. Put the intermediate derivation and requested oral wording in speaker notes or supporting material.

Compose the actual page from those elements. Give the decisive comparison sufficient space, place its defining labels beside the marks and size the text for the display. Use [the existing render path](#render-the-requested-artifact) to inspect every changed page at presentation size. Repair clipping, unreadable symbols, mismatched values and ordering that interrupts the listener's inference, then complete the integrated review against the adopted argument and requested duration.

## Compose a research site

Use the project's existing publication and analysis objects and preserve canonical links. Select the question, result and evidence each page needs, then adapt the complete explanation to the page's reading order.

## Render the requested artifact

Use the existing build path and view the actual resulting page or slide when layout affects delivery. Avoid unrelated rebuilds.

For a new LaTeX paper, start from the supplied [Econometrica template](../../../tex/paper/ecta_template.tex) with its class, configuration and bibliography style. For new slides, use the supplied [Beamer template](../../../tex/slides/main.tex), retaining metropolis, Waseda colors and Harano Aji Japanese fonts. Fill the intended author, title, abstract, keyword and body placeholders from the requested content. The [shared build helper](../../../scripts/build_latex.py) owns LuaLaTeX compatibility, citation processing and preservation of the previous PDF on failure. The [result-artifact renderer](result-artifacts.md) and Quarto consume the same default family through their produced Pandoc adapters. Preserve a user's adopted document format and existing research files when the request concerns only new defaults.

## Execute paragraph and argument contracts

Consult [paragraph guidance](paragraph-workflow.md) when a complex long-form argument needs structure. Perform its argument and paragraph reasoning in the draft and include it in the common integrated review. Use its existing state and source bindings when the requested composition needs persistent dependencies. Complete the same integrated review and actual delivery path.
