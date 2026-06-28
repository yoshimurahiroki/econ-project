# Econ Writing Reference

This document serves as a supplementary reference for AI agents assisting with economics papers. It synthesizes rules from `econ-writing-skill` and provides specific guidance on empirical identification strategies and LaTeX formatting.

## 1. Identification Strategies

When writing empirical papers, adapt the introduction and presentation according to the identification strategy:

- **Randomized Controlled Trials (RCTs)**: Clearly specify the randomization unit, timing, and compliance.
- **Difference-in-Differences (DiD)**: Emphasize the parallel trends assumption. If using staggered adoption, explicitly mention the modern estimators used (e.g., Callaway-Sant'Anna, Sun-Abraham) to account for heterogeneous treatment effects.
- **Instrumental Variables (IV)**: Devote significant space to defending the exclusion restriction and the relevance of the instrument. Explain the "first stage" clearly in the introduction.
- **Regression Discontinuity Design (RDD)**: Focus on the running variable and the assumption of no manipulation around the threshold. Present density tests and robustness to bandwidth choices.
- **Synthetic Control**: Explain the donor pool selection and placebo tests for inference.
- **Structural Estimation**: Start with the data patterns, introduce the model that explains them, and clearly map the parameters to the moments in the data.

## 2. LaTeX Best Practices

- **Tables**: Use the `booktabs` package (`\toprule`, `\midrule`, `\bottomrule`) for professional tables. Avoid vertical lines.
- **Notes**: Use `threeparttable` or the `\notes` command to ensure table notes are exactly the width of the table.
- **Math**: Use `amsmath` and `amssymb`. Define custom operators for `\E` (Expectation), `\Var` (Variance), and `\Cov` (Covariance).
- **Citations**: Use `natbib` (`\citet{}` for text citations, `\citep{}` for parenthetical citations).
- **Cross-referencing**: Use the `cleveref` package (`\cref{}`) to automatically format "Table 1" or "Section 2" consistently.

## 3. AEA Replication Standards

When preparing a replication package:
- Ensure the `README.md` strictly follows the AEA Data Editor template.
- All datasets must have proper Data Citations in the bibliography.
- The directory structure must clearly separate `data/`, `scripts/`, and `output/`.
- AI use (e.g., using LLMs for coding or editing) must be explicitly disclosed in the manuscript's acknowledgments per AEA and Econometric Society policies.
