# lineareg — Econometric Estimators with Bootstrap Inference

This repository hosts the Python package `lineareg`, providing a suite of econometric estimators designed for performance, flexibility, and robust inference. It features OLS, IV/GMM, GLS, Quantile Regression, and various panel and spatial models, all equipped with modern bootstrap methods for standard error estimation.

The library is built around a high-performance linear algebra core that leverages `numpy.einsum` and supports sparse matrices, making it suitable for high-dimensional problems.

## Features

- **Estimators**: OLS, IV (2SLS), GMM (One-step, Two-step), GLS, Quantile Regression, Spatial SAR (2SLS).
- **Panel Models**: Advanced estimators for modern causal inference, including Event Study (Sun & Abraham, Callaway & Sant'Anna), Synthetic Control, and Synthetic DID.
- **High-Dimensional Fixed Effects**: Efficiently absorb multiple fixed effects using alternating projections (within-transformations) without creating dummy variables.
- **Robust Bootstrap SEs**: A comprehensive suite of bootstrap schemes:
    - Wild (Rademacher, Mammen, Webb)
    - Cluster Wild (multi-way, with WCR/WCU recentering)
    - Dependent Wild Bootstrap (DWB) for time-series
    - Spatial Dependent Wild Bootstrap (SDWB) for spatial data
- **Formula Interface**: A user-friendly formula system inspired by Stata and R, supporting terms like `FE(firm)`, time lags `L(var, p)`, and spatial lags `SL(y)`.
- **Performance**: A sparse-aware linear algebra backend that avoids explicit matrix inversion, optimized for speed and memory efficiency.

## Installation

For a reproducible environment, using the provided devcontainer is recommended (requires VS Code and Docker).

Alternatively, you can install the dependencies listed in `libs/lineareg/pyproject.toml` in your local Python environment. The package source code is located in the `libs/lineareg` directory.

## Quick Start

Here is a quick demonstration of how to use `lineareg` with a few key estimators.

```python
import numpy as np
import pandas as pd
from lineareg import OLS, IV2SLS
from lineareg.estimators import EventStudyCS
from lineareg.output import model_summary_table

# --- Generate Sample Data ---
N, T = 100, 10
df = pd.DataFrame({
    'y': np.random.randn(N * T),
    'x1': np.random.randn(N * T),
    'x2': np.random.randn(N * T),
    'id': np.repeat(np.arange(N), T),
    'time': np.tile(np.arange(T), N),
    'cluster_id': np.repeat(np.arange(N // 5), T * 5),
})
# Generate an instrument for x1
df['z1'] = df['x1'] + np.random.randn(len(df)) * 0.2
# Generate a treatment cohort for event study
df['cohort'] = df.groupby('id')['time'].transform(
    lambda x: np.random.choice(range(5, 8)) if np.random.rand() > 0.5 else -1
)

# --- 1. OLS with Fixed Effects and Cluster Bootstrap ---
# Model: y ~ x1 + FE(id)
ols = OLS()
res_ols = ols.fit(
    formula='y ~ x1 + FE(id)',
    data=df,
    bootstrap={
        'scheme': 'webb',
        'n_boot': 499,
        'clusters': [df['cluster_id']],
    }
)

# --- 2. IV/2SLS with Two-Way Clustering ---
# Model: y ~ x1 (endog) | z1 (instr) + x2 (exog)
iv = IV2SLS()
res_iv = iv.fit(
    formula='y ~ x1 + x2 | z1 + x2',
    data=df,
    bootstrap={
        'scheme': 'mammen',
        'n_boot': 499,
        'clusters': [df['id'], df['time']],
    }
)

# --- 3. Event Study (Sun & Abraham, 2021) ---
# Model: y ~ event_time | FE(id) + FE(time)
event_study = EventStudyCS()
res_es = event_study.fit(
    data=df,
    y_var='y',
    unit_var='id',
    time_var='time',
    cohort_var='cohort',
    # Control variables can be added via `covariates_formula`
    bootstrap={
        'scheme': 'webb',
        'n_boot': 499,
        'clusters': [df['cluster_id']],
    }
)

# --- 4. Display Results in a Summary Table ---
table = model_summary_table(
    [res_ols, res_iv],
    model_names=['OLS+FE', 'IV-2SLS']
)
print(table)

# Event study results can be plotted
res_es.plot()
```

## Estimator Guides

### OLS with Fixed Effects and Bootstrap
- **Formula**: `y ~ x1 + x2 + FE(firm) + FE(year)`. Fixed effects are absorbed via alternating projections (an iterative demeaning process).
- **Bootstrap SEs**: Supports wild (Mammen/Webb), cluster wild (multi-way WCR/WCU), DWB (time), and SDWB (spatial) schemes. Leverage corrections (HC2/HC3) are based on the QR decomposition of the design matrix.
- **Few Clusters**: For a small number of clusters, the Webb six-point distribution (`scheme='webb'`) is recommended for better finite-sample properties.

### IV / 2SLS
- **Formula**: `y ~ x1_endog + x2_exog | z1_instr + z2_instr + x2_exog`. Note that exogenous regressors must be included on both sides of the `|`.
- **Diagnostics**: Weak identification diagnostics (Kleibergen-Paap rk, Cragg-Donald min eigenvalue, Stock-Wright score statistic) are reported in `result.stats`.
- **Bootstrap SEs**: The same schemes as OLS are available. Leverage is calculated based on the IV projection space.

### GMM (One-step / Two-step)
- **One-step GMM**: Uses a user-provided weighting matrix `W` or defaults to `W = I`.
- **Two-step GMM**: Constructs an efficient weighting matrix from the residuals of a first-step estimation.
- **Bootstrap**: The option `refit_weight_in_boot=True` re-estimates the optimal weighting matrix within each bootstrap replication to account for its sampling variation.

```python
from lineareg.estimators import OneStepGMM, TwoStepGMM

# One-step GMM with identity weight
gmm1 = OneStepGMM()
res1 = gmm1.fit(formula='y ~ x1 | z1', data=df, bootstrap={'n_boot': 399})

# Efficient Two-step GMM
gmm2 = TwoStepGMM()
res2 = gmm2.fit(formula='y ~ x1 | z1', data=df, bootstrap={'n_boot': 399})
```

### GLS / Feasible GLS
- **Whitening**: Transforms the data via `(X_tilde, y_tilde) = (C @ X, C @ y)`, where `C.T @ C = Σ**(-1)`. OLS is then performed on the transformed data.
- **Bootstrap**: The option `refit_sigma_in_boot=True` implements a feasible GLS-style bootstrap. Within each replication, it reconstructs `y*` in the original scale, re-estimates `Σ*` from OLS residuals, and whitens the data again before estimation.

### Quantile Regression (WGB)
- Implements the Wild Gradient Bootstrap (Feng, He & Hu, 2011) for inference.
- The quantile of interest is specified as a constructor argument: `QuantileRegression(quantile=0.5)`.

### Spatial SAR (Kelejian–Prucha 2SLS)
- **Formula**: When a spatial weight matrix `W` is provided via the `W_spatial` argument, spatial lag (`SL`) and spatial Durbin (`WX`) terms can be included in the formula.
- **Endogeneity**: The spatial lag of the dependent variable, `SL(y)`, is automatically treated as endogenous. Instruments are formed from spatial lags of the exogenous regressors (e.g., `WX`, `W**2 X`), with collinear instruments automatically removed.

## Bootstrap Schemes and Options

- **`scheme`**: `'mammen'` (two-point), `'webb'` (six-point, recommended for few clusters), `'rademacher'` (two-point), `'dwb'` (for time dependence), `'sdwb'` (for spatial dependence).
- **Clustering**: Pass a single series or a list of series to the `clusters=` argument for one-way or multi-way clustering.
- **Multi-way Options**: `multiway_mode` (`'wcr'`/`'wcu'`) controls re-centering, and `multiway_combine` (`'product'`/`'sum'`) controls how perturbations are combined across clustering dimensions.
- **Leverage Correction**: Apply HC2/HC3 style corrections via `leverage_correction='hc2'` or `'hc3'`.

## Monte Carlo & Demo

- **Demo**: Run `python -m lineareg.demo` to execute all estimators on synthetic data and generate a summary table.
- **Monte Carlo**: The `lineareg.sim.montecarlo` module provides a small suite for validation and performance testing.

## References

- Correia, S. (2017). "Linear Models with High-Dimensional Fixed Effects: An Efficient and Feasible Estimator."
- Davidson, R., & Flachaire, E. (2008). "The Wild Bootstrap, Tamed at Last." *Journal of Econometrics*.
- Feng, X., He, X., & Hu, J. (2011). "Wild Gradient Bootstrap for Quantile Regression."
- Guimarães, P., & Portugal, P. (2010). "A Simple Feasible Procedure to Fit Models with High-Dimensional Fixed Effects." *The Stata Journal*.
- MacKinnon, J. G., & Webb, M. D. (2017). "The Wild Cluster Bootstrap for Few (Treated) Clusters."
- Mammen, E. (1993). "Bootstrap and Wild Bootstrap for High Dimensional Linear Models." *The Annals of Statistics*.
- Shao, J. (2010). "The Dependent Wild Bootstrap." *Journal of the American Statistical Association*.
- Sun, L., & Abraham, S. (2021). "Estimating Dynamic Treatment Effects in Event Studies with Staggered Adoption." *Journal of Econometrics*.
- Webb, M. D. (2014). "Reworking Wild Bootstrap Based Inference for Clustered Errors."
