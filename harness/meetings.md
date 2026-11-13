# Edit research meeting materials from saved results

Select research artifacts in the local marimo interface and build materials from the previous decisions, tasks and GitHub progress. A material bundle consists of `meeting.json`, `content.md` and the selected `assets/`. Supported outputs are HTML slides, Markdown, PDF through the existing Beamer templates, and native Google Slides.

1. **Selected result → bundle.** Register the [public claims and numerical uncertainty](../skills/econ-writing/references/result-artifacts.md#save-displays-at-analysis-or-registration) at Gallery, then select its resolved `public_text` and saved rows. Keep conditions, diagnostics and producer identities in the bundle's metadata and internal record. Public claims state quantities and actual outcomes under [PROSE Common output](../runtime/PROSE.md#common-output); conditions, failures and sample accounting stay in that metadata.
2. **Adopted argument → document.** Supply section prose through `section_content` or `content.md` using the source-first borrowing procedure below and the saved result. Retain restrictions internally with their scientific owner; the section states quantities, mechanisms and outcomes under PROSE Common output.
3. **Rendered material → user.** Read the generated body, labels, captions and speaker text through PROSE's finish step. Repair the producing field, regenerate and inspect the selected formats.

Saved-result mechanical fields: estimate `2 pp`; SE `0.5 pp`.

Apply [PROSE Common output](../runtime/PROSE.md#common-output) to every material and existing draft.

Apply this procedure also to short text, single-word edits, translation, formatting, labels, automated summaries, headings, captions, speaker notes, figures, tables, layouts and template defaults, including carried-forward or user-authored drafts. A template, automatic output or saved content is not itself an exemption: search and read corresponding actual sources and adjust its producing fields as needed. Record source-to-output locations and adjustments in the existing material or work record, then compare every element of the finished material with its source. If a corresponding passage or visual is missing, resume searching and reading; do not fill gaps with free paraphrase, invented examples, or independently composed arguments or designs.

## Create a bundle

```sh
python harness/state.py --root "$PROJECT" project-view CASE --role manage --view summary \
  --github github-snapshot.json --save meeting-summary.json
python harness/research.py gallery select --root "$PROJECT" \
  --registry analysis/gallery.json sample-table main-event-study \
  --output selected-results.json
python harness/research.py meeting create --root "$PROJECT" \
  --selection selected-results.json --project-view meeting-summary.json \
  --previous meetings/previous --output meetings/current \
  --title "研究ミーティング" --kind meeting --date 2026-11-05 \
  --issue-url https://github.com/OWNER/REPO/issues/123
```

Omit `--previous` for the first meeting. Choose `--kind` from the templates below and use a new destination directory. The CLI and marimo read the same `tex/slides/meeting_templates.json`.

| `--kind` | Content | HTML / PDF |
| --- | --- | --- |
| `brief` | Research question, data and sample, analysis specification, saved results, interpretation, next work | Document / Econometrica |
| `progress` | Previous decisions, completed outputs, current work, results, next work | Slides / Beamer |
| `proposal` | Research question and estimand, adopted plan, descriptive statistics, design consultation, decision | Slides / Beamer |
| `results` | Research question, design, sample, Table 1, main results, event study, additional results, interpretation, current decision, next work | Slides / Beamer |
| `meeting` | Previous decisions and tasks, current work, results, interpretation and decisions, next tasks | Slides / Beamer |
| `model` | Actors, choices, objectives and constraints, information and timing, notation, optimization, equilibrium, propositions and derivations, comparative statics, numerical solution, counterfactuals and welfare | Slides / Beamer |
| `structural` | Model, observed variation and identification, data, likelihood or moments, solution method, structural parameters, fit, counterfactuals, welfare, sensitivity | Slides / Beamer |
| `appendix` | Notation, model, derivations and proofs, identification, data construction, estimation and inference, numerical computation, additional results | Document / Econometrica |
| `manuscript` | Data, empirical specification, results, exhibits, interpretation | Document / Econometrica |

Keep templates in the existing `tex/slides/meeting_templates.json`. Initialize manuscript Data, Specification and Results sections from `data_description`, `specification_description` and `results_summary` in `project-view`, applying the source-first procedure to these inputs and any automatic summaries. Edit the prose in `content.md` by that procedure. Exhibits retain the selected result IDs and saved values.

Set `project-view.language` to the document's language tag, such as `ja` or `en`. The bundle retains it as `meeting.json.language`; rendering uses that value for generated table names and other localized labels. Existing bundles use `ja`.

Set `project-view.abstract` to the completed article abstract. The bundle preserves it in `meeting.json.abstract`, and the article renderer places it before the chapters. Add complete chapters through the existing section operations and order them with the saved exhibits. The [subscription producer](../skills/econ-data/examples/subscription/materials.py) consumes its registered bilingual profile as a complete manuscript.

For theory and structural materials, supply section IDs and adopted Markdown prose in the same `project-view` object's `section_content`. Send equations and explanations to sections in the selected template, such as `model`, `information`, `optimality`, `equilibrium`, `propositions`, `identification` and `numerical`. Borrow and imitate corresponding source text, making only the necessary adjustments to the adopted model contract's actors, constraints, information and equilibrium conditions. State the identified parameters and observed variation, optimality conditions and numerical methods, and the primitives held fixed in each counterfactual. Put notation and definitions in `notation`; put propositions and proofs in `propositions` or the appendix's `derivation`. Supplied prose takes precedence over automatic summaries. Section IDs must belong to the selected template.

```json
{
  "research_question": "<research_question>",
  "section_content": {
    "model": "<model>",
    "identification": "<identification>",
    "numerical": "<numerical>"
  }
}
```

These mechanical placeholders identify input fields for `--kind structural`; apply the source-first procedure above to their content. Actual materials specify the adopted demand equation, instruments, cost structure, equilibrium selection and executed results. `section_content` supplies document content; analysis specifications and saved results remain at their scientific owners.

The template's `artifact_role` determines where descriptive statistics, main results, event studies and additional results appear. Set the selected result's `metadata.report_role` to `descriptive`, `main`, `event_study` or `additional` when its role is explicit. Otherwise placement follows the saved exhibit type. Keep the main-result summary before its exhibits. The bundle retains findings, interpretations, issues and adopted judgments internally; the author selects the supported public argument into `section_content`.

Structural materials also place saved `report_role` values `parameters`, `model_fit`, `counterfactual` and `welfare`; theory materials place `notation`, `mechanism` and `comparative_statics`. An exhibit without a dedicated section uses the selected template's existing exhibit section. Display structural parameters with their estimated, calibrated or fixed status and units; fit with observed and model moments; and counterfactuals with scenario-specific prices, quantities, profits and welfare. Use separate gallery panels for quantities with different units. Carry each exhibit's `model_contract`, `scenario`, `parameter_definition`, parameter treatment, state-value definition, terminal condition, and stock/flow timing into the materials.

Standard regression tables inherit the `presentation` assembled by Gallery from saved values. Markdown and native Google Slides tables use the same column groups, coefficient rows, labeled numerical standard-error rows and model information. Their public text comes from the selected result's resolved projection. Retain original numeric rows, internal notes and result IDs in the bundle.

`project-view` reads GitHub Issues / Projects registered through the existing `project-bind`. `--github` accepts a connector-acquired snapshot. The bundle's `task_snapshot` records the meeting's state; edit current ownership, deadlines, priorities and progress in GitHub. Keep research specifications and scientific results in the existing ERS canonical sources.

Map the optional [publication stage](state.md#github-issues-and-projects) at `github.fields.publication_stage`. Task lines carry its current value beside the Issue link, assignees and due date; the bundle retains the same value in `task_snapshot` and `next_actions`. Refresh the saved project view and create the next meeting edition after a stage change. Existing saved scientific exhibits supply the new edition's results.

Carry forward authored decisions and tasks from the previous bundle's `content.md`; `next_actions` supplies saved task inputs. Select tasks completed since the previous meeting. Each exhibit retains its result ID, sample, observation unit, comparison, period, units, estimate, standard-error and interval definitions, and producing source. Route findings and adopted judgments through the public argument step before writing their sections. Edit prose separately from numeric values.

## Edit prose and structure

Text after `<!-- section:ID -->` in `content.md` supplies the section body. `sections` in `meeting.json` controls order, headings, visibility, layout, exhibit IDs, captions and speaker notes.

| Target | Field to edit |
| --- | --- |
| Prose | Corresponding section in `content.md` |
| Slide order | Order of the `sections` array |
| Heading and visibility | `title`, `visible` |
| Exhibit selection and order | ID array in `artifacts` |
| Layout | `layout`: `stack`, `figure-left`, `figure-right`, `figures` |
| Caption and speaker notes | `caption`, `speaker_notes` |
| Add or remove a section | Add the same ID to both files, or remove it from the structure |

The local marimo interface edits these fields through forms. Its explicit save button checks the existing saved revision's hash before writing. Change scientific definitions through the existing specification-update and result-registration paths. Presentation edits consume saved results without invoking estimation.

Producers place each exhibit on the page of the claim it supports with `fold_into_exhibit(bundle, source_id, exhibit_id, layout=...)`, which moves the prose section's heading and body onto the exhibit section and hides the prose-only page. Slide headings are noun phrases.

Editing one section preserves the other section bodies and draft text retained after a section is removed. Re-adding a removed section ID restores its retained draft unless the addition supplies replacement prose. Structural `<!-- section:ID -->` markers belong to the section structure and cannot appear inside a section's body.

```sh
python harness/research.py meeting render --root "$PROJECT" \
  --bundle meetings/current --output outputs/current-html --format html
```

`--format markdown` produces Markdown; `--format pdf` produces LuaLaTeX output. Documents use the existing `tex/paper/pandoc_template.latex` and Econometrica class and settings. Slides use the existing `tex/slides/pandoc_template.latex`, metropolis, Waseda colors and Japanese fonts. HTML and PDF destinations contain the completed files and `render.json`. Markdown output also includes images referenced by its text. Keep editable prose, structure and exhibits in the source bundle; regenerate intermediate Quarto, TeX and style files during rendering. `render.json` records each consumed LaTeX file's hash in `latex_files`. Prefer saved PDF, PNG and JPEG assets for PDF output; use `rsvg-convert` for figures available only as SVG.

Gallery's `public_text` supplies supported claims and numerical uncertainty to HTML, Markdown, PDF and native Slides. Existing diagnostic/annotation fields, complete inference definitions and producer hashes remain in bundle metadata. Public claims state actual outcomes and select population, period, units and comparison into the claim when they define its quantity; conditions, failures and sample accounting stay in bundle metadata. Preserve adopted exhibit cells and user-authored content while applying the source-first procedure to its expression and presentation; inspect it through PROSE before delivery. Place a section's `caption` after its last exhibit; speaker text uses the explicit `speaker_notes` field. Slides use 28 pt body, bullet and table text, with 32 pt headings and 28 pt supporting definitions. CSS renders 28 pt as 37.33 px; Beamer uses a 960 × 540-point page and explicit 28 pt body fonts; Japanese glyphs run at `luatexja-preset` scale 1, so Japanese text also renders at 28 pt. Split dense arguments across pages and inspect figure labels at their placed size. Keep a short document table's heading, rows and caption on one page. Break long table identifiers at underscores. The Pandoc adapter carries Quarto's `include-in-header` through the same path, including Japanese document PDF settings.

Quarto renders prose and saved exhibits in an isolated working directory with `engine: markdown` and `--no-execute`. Select exhibits through `sections[].artifacts`; use the body for prose, equations, lists and links. Check saved exhibit hashes and write the completed version to a new output directory. `render.json` retains the input revision, consumed exhibit and template hashes, executed command, Quarto version and output hashes.

## Edit in the GitHub browser

1. Save only materials selected for publication in the repository's `meetings/NAME/` directory and set their `meeting.json` field `cloud_export` to `true`. Its initial value is `false`. Set `cloud_formats` to the selected formats, such as `["html", "pdf"]`; new materials select HTML and PDF. Keep raw data and microdata outside the material bundle.
2. Use the pencil button on `content.md` in GitHub to edit prose. Edit `meeting.json` for order, visibility and layout. GitHub's web editor (`.` key) can save several files in one commit.
3. Open the `Render selected meeting materials` Actions run. Saving the manuscript in the browser renders each format in `cloud_formats`. `Run workflow` with `format: configured` uses that selection; `html`, `pdf` and `markdown` select the named format. Summary shows the completed prose, tables and figures; the `meeting-...` artifact contains the completed materials. HTML produces a self-contained `index.html`. Existing materials without `cloud_formats` use HTML.
4. Save subsequent edits through the same browser operation. Only jobs for changed materials rerun. Renderer or shared-template changes refresh the affected materials' presentation.

The Actions selection job reads the material settings and selects bundles with `cloud_export: true`. Rendering jobs retrieve their selected directories and presentation templates. For PDF, Quarto Actions prepares TinyTeX and installs metropolis, Japanese fonts and exhibit packages. Link the material directory, Actions run and Google Slides edition in the Issue's Related research field.

## Create an independent Google Slides edition

```sh
python harness/research.py meeting google-slides \
  --bundle meetings/current --output outputs/current-google-slides.json
```

The packet contains Google Slides API `createSlide` requests and native text, table and image requests. Create a new presentation (`application/vnd.google-apps.presentation`) through connected Google Drive / Slides and pass `requests` to `batchUpdate`. Supply local PNG/JPEG files from `images` through the connected tool's image-upload arguments. For published images, `--asset-base-url` can specify the bundle's HTTPS URL.

After creation, retrieve `slides[].slideProperties.notesPage.notesProperties.speakerNotesObjectId` and use `insertText` to place the packet's `speaker_notes` in the corresponding notes shapes. Use the user's Drive `ChatGPT` folder as the destination. Edit prose, order and exhibit layout in the Google Slides GUI using the same source-first procedure and record and compare every element.

```sh
python harness/research.py meeting link-edition --bundle meetings/current \
  --url https://docs.google.com/presentation/d/PRESENTATION_ID/edit \
  --expected-revision CURRENT_SOURCE_SHA256 --kind google-slides
```

Append the returned editing URL and source revision to `editions`. Regeneration creates a new presentation and preserves the edited presentation at its existing ID. Retain the GitHub manuscript and Google Slides edition as independently editable versions.

After producing the packet, execute presentation creation, `batchUpdate`, speaker-note insertion and returned editing-URL registration through connected tools. The packet supplies their input; `editions` identifies actually created materials. `--source-revision` can specify the source version recorded in the packet. Pass the current bundle revision at registration as `--expected-revision`.

## Dependencies and saved content

The existing research DAG owns analysis and data updates. The gallery owns exhibit presentation updates. This renderer owns meeting prose and structure updates. Save the producing sources for raw data, estimates and presentation summaries during analysis. Ordinary viewing and material editing read the selected saved results. Build a reproduction package through the existing `research.py` path when creation, update or reproduction of the corresponding artifact is selected.

## Official specifications and templates

- [Quarto execution options](https://quarto.org/docs/computations/execution-options.html): document rendering with `engine: markdown`.
- [Quarto Beamer](https://quarto.org/docs/presentations/beamer.html): heading-based slide breaks, exhibit columns and PDF presentation settings.
- [Quarto journal templates](https://quarto.org/docs/journals/templates.html): existing Pandoc templates and LaTeX output.
- [Econometrica's official LaTeX distribution guide](https://www.e-publications.org/ecta/support/) and [source repository](https://github.com/vtex-soft/texsupport.econometricsociety-ecta): sources for this project's class, settings and manuscript templates.
- [Quarto Actions](https://github.com/quarto-dev/quarto-actions): Quarto and TinyTeX configuration on GitHub.
- [Quarto figure sizing](https://quarto.org/docs/authoring/figures.html#figure-sizing): figure height in PDF slides.
- [EconAgentSkills standard tables](https://github.com/JonasWeinert/EconAgentSkills/blob/c1b8b1ef7ab59e6858fe3599a39d4732e5a76142/_skills/writing/latex-tables/examples/table_main_template.tex): coefficient and parenthesized standard-error rows and specification rows.
- [econ-research-os notation table](https://github.com/RyanPiao/econ-research-os/blob/0b206cd043f77d787932dcb149106bb648106033/skills/econ-write/templates/notation-table.md) and [Quarto chapter structure](https://github.com/RyanPiao/econ-research-os/blob/0b206cd043f77d787932dcb149106bb648106033/skills/econ-write/templates/chapter-template.qmd): connections between notation, equations, implementation and examples. ERS connects them through its existing material structure.
