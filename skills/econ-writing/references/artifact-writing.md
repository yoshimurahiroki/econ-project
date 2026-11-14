# Slides, materials and rendering

Talks, meeting materials, research sites and the rendering of every artifact. The content comes from the worksheet and saved results; text follows [WRITING](../../../runtime/WRITING.md). Work through the steps in order and record the output paths in section 7 of the worksheet.

## S1. Talk plan

Read the sequence of a strong talk of the same type:

```sh
python3 skills/econ-writing/scripts/exemplars.py find --lang en --kind slide --query "<topic words>" --limit 3
```

Talks not yet in the library come from the user's Drive, authors' homepages, NBER Summer Institute and Methods Lectures, conference programs and course pages. Fill one line per slide:

```
Slide <n> (<minutes>):  noun-phrase title → one claim → exhibit or equation (saved result ID) → worksheet item
```

The default sequence follows the worksheet: question and stake, answer, mechanism with competing predictions, setting and data, identifying comparison, main result, magnitude and decision, mechanism evidence, conclusion; appendix slides for derivations, extra estimates and definitions. A talk exemplar of the same type takes precedence over this default. Allocate minutes to the slides that carry the answer; quantities are defined before they are used.

## S2. Compose slides

1. **Titles** are noun phrases. **Each slide carries one claim**, with its figure or table and a one-line reading of it, and the magnitude with its unit.
2. **Japanese slides** take their heading grammar, bullet endings, punctuation and layout from Japanese slide exemplars (`find --lang ja --kind slide`, `style --lang ja --kind slide`), at 32 pt body text with lines of up to 24 characters.
3. **Every exhibit slide carries its reading.** A figure or table without a one-line reading is unfinished: register the claim in the display's `metadata.public_claims` or write the section caption before rendering.
4. **Layouts** in meeting bundles: `stack` for a claim with a wide table; `figure-left` for a figure beside its interpretation; `figures` for comparable panels on common scales. Population, period and units sit beside the exhibit. Dense content is split across slides at the same type size.
5. **Theory and structural talks** use the `model` or `structural` material template (`tex/slides/meeting_templates.json`); saved parameter, fit, equilibrium and welfare displays are placed by their result IDs.

## S3. Type sizes and templates

| Element | Screen slides (Quarto) | Beamer | HTML document |
|---|---|---|---|
| Page | 1280 × 720, top-aligned, 7% margin | 960 × 540 pt, top-aligned, 54 pt side margins | 44 rem column |
| Title / heading | English 40 / 32 pt; Japanese 44 / 36 pt | English 40 / 32 pt; Japanese 44 / 36 pt | 34 px / 25 px |
| Body, bullets, tables, captions | English 28 pt (37.33 px); Japanese 32 pt; line height 1.45 | English 28 pt; Japanese 32 pt (`japanese: true` or `\ersjapanesetrue`) | 18 px, line height 1.8 |

Templates: paper `tex/paper/ecta_template.tex` (econsocart; Top Five section order, each slot naming the function of a paragraph), Beamer `tex/slides/main.tex` (metropolis, Waseda colors, Harano Aji fonts; the sequence above), Quarto `tex/paper/quarto_template.qmd` and `tex/slides/quarto_template.qmd`, meeting `tex/slides/meeting_template.qmd`. Replace every slot with content from the worksheet in the wording of the exemplar and delete unused sections and frames; a rendered page that still shows ⟨…⟩ or [fill: …] is unfinished. `scripts/build_latex.py` handles LuaLaTeX, citations and keeps the previous PDF when a build fails.

## S4. Results-based materials

Register named quantities and units from saved estimates and generate tables, figures, articles and slides through the [result artifacts](result-artifacts.md) producers and the research DAG; article and slides read the same quantities. Meeting materials come from saved displays and progress records ([meetings](../../../harness/meetings.md)), with editable Markdown, Quarto rendering and native Google Slides editions.

## S5. Other documents

Decision proposals and pre-analysis plans follow [proposals](proposals.md). Research sites, progress reviews and meeting records take their structure from exemplars of the same purpose and their content from the worksheet and project records: decisions, basis, responsibility, timing and dependencies.

## S6. Render and read

Build through the existing path (`make build-slides`, `make slides-pdf QMD=...`, `make build-paper`, `harness/research.py meeting render`) and read every changed page at its presentation size:

```
Page <n>:   title and claim match the plan; numbers match the saved result; symbols, labels and intervals legible;
            rendered body size (pdffonts or measurement) as in S3
```

Repair at the producer (text, layout or result), rebuild, and read the affected pages again. Check the total against the speaking time.
