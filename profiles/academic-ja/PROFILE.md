# Japanese economics writing profile

Profile family: academic-ja. Language: Japanese.

## Use

This profile fixes notation, numbers, terms, exhibits, citations and layout for Japanese papers, notes, briefs, meeting materials and slides. Japanese output is native-language working material in Top Five form. Argument structure comes from English exemplars ([WRITING](../../runtime/WRITING.md) section 1); connectives, sentence endings, vocabulary, rhythm and explanation order come from Japanese exemplars ([WRITING](../../runtime/WRITING.md) section 2), and an English draft is never translated. Where an exemplar and this profile differ on wording, the exemplar wins. Length follows the content of the worksheet and the exemplar of the same genre.

## 1. Characters and punctuation

- Papers, notes, briefs and meeting documents use 「，．」; slides use 「、」 and end bullets as the slide exemplars do.
- Latin letters, Arabic numerals, operators, equations and numeric intervals are half-width; Japanese parentheses are full-width.
- No space between Japanese characters; a half-width space between a number and a Latin unit; 年・月・人・件・円・% follow the number directly.
- Digits for quantities, dates, sample sizes and exhibit numbers; grouping commas from 4 digits; the minus sign 「−」 and the range dash 「–」.

## 2. Numbers

- An estimate, its standard error and its interval share one scale and one number of decimals; a table column uses one number of decimals.
- Display precision follows the precision of the estimates; round once from the saved value; p < 0.001 below that value.
- Differences in proportions are in percentage points; the currency, price base year and scale of a monetary result are stated at its first appearance.

## 3. Terms

- One standard term per concept across text, tables, equations and slides; the first occurrence gives 「日本語術語（原語，略語）」, and later occurrences use the abbreviation.
- Technical distinctions are kept: 推定値 (a reported number), 推定結果 (a display of results), 推定量 (an estimator); 処置群 and 対照群; 識別; 厚生.
- Software, package and variable names keep their original spelling; katakana spellings データ, モデル, パラメータ, クラスター.

## 4. Symbols and equations

- Standard symbols unless the model defines others: i for a unit, t for time, β for a coefficient, ε for a disturbance; each symbol is defined where it is introduced.
- Equations are numbered through the document and cited as 式(1); exhibits as 表1 and 図1; sections as 第2節.

## 5. Tables and figures

- Tables: a numbered title, column numbers (1), (2), (3), the coefficient with its parenthesized standard error on the next row, no significance stars; observations, fixed effects, controls and weights below, with X for an included block; portrait, at most 9 columns, horizontal rules only, Panel A and Panel B for subtables.
- Table notes: content, estimator by column, fixed effects, sample, level of clustering, weights, from the saved specification.
- Figures: axis labels with quantity and unit; intervals labelled with the level and method from the saved result; vector PDF; panels labelled a, b, c.

## 6. Citations and references

- 「著者（年）」 as the subject of a sentence and 「（著者 年）」 for attribution, with a half-width space between author and year; two Japanese authors joined by 「・」, three or more by the first author and 「ほか」; the reference list gives every author.
- Entries: articles with author, year, title, journal, volume, issue, pages, DOI; books with author, year, title, publisher; working papers with author, year, title, series, number, institution, URL.

## 7. Layout

- **Papers:** the Econometrica template in `tex/paper` (econsocart, LuaLaTeX, Harano Aji fonts for Japanese); exhibits after the paragraph that first cites them; page numbers centred at the foot.
- **Slides:** 16:9, body 32 pt, headings 36 pt, title 44 pt, with labels, tables and captions at body size (Japanese type is set larger than English because a character carries more content); the metropolis theme and Waseda colours of `tex/slides`; page number at the lower right.
- **Slide content:** a noun-phrase heading, one claim, its exhibit or equation with a one-line reading and the magnitude with its unit; content that does not fit moves to the next slide at the same type size.

## 8. Genres

- Decision proposals and pre-analysis plans: [proposals](../../skills/econ-writing/references/proposals.md).
- Talks and meeting materials: [slides and materials](../../skills/econ-writing/references/artifact-writing.md).
- Papers: [paper workflow](../../skills/econ-writing/references/paper-workflow.md).
- Referee responses: each comment quoted, then the response, then the exact section, page or line of the change.
- Research briefs: the conclusion with its magnitude first, then the evidence, the mechanism and the action.
