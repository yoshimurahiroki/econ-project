# English economics paper profiles

Profile family: top-five-en. Language: English.

## Principles

Apply [PROSE Common output](../../runtime/PROSE.md#common-output) to every element selected from this profile.

Select and read the complete sample matching the current passage’s function and research field. Ground adopted expressions and visual elements in the original sources. The 25 paper body files contain the user-adopted English samples; the seminar-slide profile presents the empirical study as a talk in the order motivation, question, this paper, preview of findings, setting, data, strategy, results, mechanism and bottom line. Preserve their text, equations, headings and table contents. Profile selection and usage instructions belong in this index and the routing registry.

## Select a profile

Each row is a separate selectable writing profile. The registered profile ID is `top-five-en-` followed by the filename stem; the example ID uses `top-five-en.` followed by the same stem. Read the complete selected body through the existing profile or example reader.

```sh
python scripts/route_registry.py read econ-writing:compose --user-profile top-five-en-introduction-empirical --stage compose
python scripts/route_registry.py read top-five-en-field-spatial.all
```

| Function | Field | Profile body |
|---|---|---|
| abstract | labor and public economics | [abstract-labor-public](abstract-labor-public.md) |
| abstract | microeconomic theory | [abstract-micro-theory](abstract-micro-theory.md) |
| abstract | industrial organization and identification | [abstract-io-identification](abstract-io-identification.md) |
| abstract | urban and spatial economics | [abstract-spatial](abstract-spatial.md) |
| abstract | econometrics | [abstract-econometrics](abstract-econometrics.md) |
| abstract | field experiments and development | [abstract-field-experiment](abstract-field-experiment.md) |
| abstract | macro and finance | [abstract-macro-finance](abstract-macro-finance.md) |
| introduction | applied microeconomics | [introduction-empirical](introduction-empirical.md) |
| introduction | microeconomic theory | [introduction-theory](introduction-theory.md) |
| institutional setting | applied microeconomics | [empirical-institution](empirical-institution.md) |
| data | applied microeconomics | [empirical-data](empirical-data.md) |
| conceptual framework | applied microeconomics | [empirical-framework](empirical-framework.md) |
| empirical strategy | applied microeconomics | [empirical-strategy](empirical-strategy.md) |
| results: older workers | applied microeconomics | [empirical-older-workers](empirical-older-workers.md) |
| results: firms and younger workers | applied microeconomics | [empirical-firms-younger-workers](empirical-firms-younger-workers.md) |
| mechanisms and heterogeneity | applied microeconomics | [empirical-mechanisms](empirical-mechanisms.md) |
| conclusion | applied microeconomics | [empirical-conclusion](empirical-conclusion.md) |
| field sections | microeconomic theory | [field-micro-theory](field-micro-theory.md) |
| field sections | industrial organization | [field-io-demand](field-io-demand.md) |
| field sections | econometrics | [field-econometrics](field-econometrics.md) |
| field sections | spatial economics | [field-spatial](field-spatial.md) |
| field sections | macro and finance | [field-macro-finance](field-macro-finance.md) |
| field sections | field experiments | [field-experiment](field-experiment.md) |
| field sections | computational methods | [field-computation](field-computation.md) |
| field sections | economic history | [field-history](field-history.md) |
| seminar slides | applied microeconomics | [slides-seminar](slides-seminar.md) |

## Read connected sections

For the empirical study, read the labor/public abstract, empirical introduction, and empirical sections in this order: institution, data, framework, strategy, older workers, firms and younger workers, mechanisms, conclusion.

For microeconomic theory, read the theory abstract, theory introduction, and microeconomic-theory field profile. For the remaining fields, select the corresponding abstract and field profile where available.
