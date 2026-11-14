# Writing

Writing is step 7 of the [economist's procedure](ECONOMIST.md). The worksheet supplies the content; this file governs structure, expression and form. Structure and argument are shared across languages and come from English research papers and talks. Japanese vocabulary, connectives, sentence endings and rhythm come from Japanese originals. Layout comes from the templates in `tex/` and the [profiles](../profiles/).

## The exemplar library

Each user keeps their own exemplar library outside the repository: Top Five papers and slides for structure, Japanese lecture notes, textbooks, lecture slides and discussion papers for Japanese expression. Register files or folders once:

```sh
python3 skills/econ-writing/scripts/exemplars.py add ~/papers ~/lectures
python3 skills/econ-writing/scripts/exemplars.py list
```

The library is a local SQLite file (`$ERS_EXEMPLARS`, or the user data directory). Texts and passages stay on the user's machine and never enter a commit. If no library exists, ask the user once to register their files and continue with the profiles in the meantime.

## 1. Borrow the argument from English originals

Before drafting a section, read how a strong paper moves through the same function:

```sh
python3 skills/econ-writing/scripts/exemplars.py outline --lang en --function introduction --query "minimum wage"
python3 skills/econ-writing/scripts/exemplars.py find --lang en --function results --query "event study" --limit 2
```

`outline` prints the first sentence of every paragraph of one section: the sequence of moves. Map each worksheet item onto those moves (motivating fact, question, approach, main result with magnitude, mechanism, contribution) and follow the same order and paragraph functions. Functions: introduction, background, data, model, method, results, mechanism, robustness, conclusion. Slides follow the sequence of a research talk; read one with `find --lang en --kind slide`.

## 2. Borrow the Japanese expression from Japanese originals

Japanese text is composed from Japanese exemplars. It is never a translation of an English draft. The argument from step 1 is fixed; the words, connectives, endings and rhythm are taken from the Japanese passages.

```sh
python3 skills/econ-writing/scripts/exemplars.py find --lang ja --kind prose --query "需要 均衡" --limit 3
python3 skills/econ-writing/scripts/exemplars.py style --lang ja --kind prose
```

Use `--kind slide` for slides. `style` lists the openings and connectives, the sentence endings and the sentence-length quartiles of the matching passages. Then write each sentence under these rules:

1. **Connectives and openings** are taken from the retrieved passages or the `style` list (そこで, ここで, つまり, このような場合, なお, しかし, したがって and the like). A sentence opens with one of them, or with its subject.
2. **Endings** are taken from the `style` list (である, となる, と呼ぶ, ている and the like). Consecutive sentences vary their endings as the passages do.
3. **Rhythm** follows the quartiles: most sentences fall between the first and third quartile, with short sentences mixed in at the observed share.
4. **Vocabulary** follows the passages: their technical terms, verbs and the way they introduce symbols (ここで，λは…を表す). A term the passages lack takes its standard Japanese textbook form.
5. **Explanation order** follows the passages: a statement, then its reason or condition, then the consequence (このような場合は…となる). Each paragraph moves in the order of the English argument from step 1.

After drafting, compare every sentence with the passages: each has a counterpart for its opening, its ending and its length. Rewrite sentences without one. Papers and notes use 「，．」; slides use 「、」 and full sentences or noun phrases as the slide exemplars do.

## 3. Expression rules

These apply to every language and format, including tables, labels and captions.

1. **Direct claims.** State definitions, model primitives, mechanisms, estimates with population, period and units, decisions and actions in direct sentences.
2. **Numerical uncertainty only.** Uncertainty appears as standard errors, confidence intervals or p values with their levels and units. Significance stars are replaced by these numbers.
3. **Conditions stay in the worksheet.** Assumptions, diagnostics, sample restrictions, failures and caveats stay in the worksheet and the result metadata. A condition that is itself the answer or a model primitive (an identification strategy, a theorem's hypotheses, an equilibrium condition) enters the text as a proposition.
4. **No defensive or ornamental language.** Hedges, disclaimers, reservations, concessions, limitations, ornament, exaggeration and abstract value judgments are removed, in any language. So are negation contrasts ("not A but B", "A rather than B", "A and B must be distinguished"): state A, or B, directly.
5. **Exact quantities.** Name each quantity with its population and estimand ("the average effect on compliers"). Every number comes from a saved result.

## 4. Form

- **English papers and slides:** [top-five-en profile](../profiles/top-five-en/PROFILE.md).
- **Japanese working drafts, notes and slides:** [academic-ja profile](../profiles/academic-ja/PROFILE.md). Japanese output is native-language working material in Top Five form.
- **Templates:**
  - paper: `tex/paper/ecta_template.tex` (econsocart);
  - Beamer: `tex/slides/main.tex`, with the Japanese sizes switched on by `japanese: true` or `\ersjapanesetrue` (32, 36 and 44 pt; English 28, 32 and 40 pt);
  - Quarto: `tex/*/quarto_template.qmd`;
  - building: `make build-paper`, `make build-slides`, `make qmd-pdf QMD=...`.
- **Slides:** noun-phrase headings, one claim per slide, a figure or table with a one-line reading, the magnitude with its unit.
- **Tables and figures:** generated from saved results through the [result artifacts](../skills/econ-writing/references/result-artifacts.md) producers.

## 5. Finish

Read the rendered output: text, tables, captions, labels and slides. Check each claim against the worksheet and the saved results, each Japanese sentence against its exemplars, and the rules in section 3. Repair the producer when a generated element is wrong, regenerate and read the output again. Report the saved and rendered paths.
