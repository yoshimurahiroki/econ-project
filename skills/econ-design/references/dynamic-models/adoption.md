## Dynamic durable adoption and share inversion

- A fresh cohort in observed price state `z` chooses a single durable product or waits; adoption ends the modeled choice problem and waiters expect price state `z'` with known probability `Q_zz'`.
- Each consumer has a permanent observed-in-distribution price taste `η_k` with known weight `w_k`.
- Conditional utility of adoption is `δ_z+η_k p_z`, and waiting gives zero current flow.
- With unit-scale extreme-value choice shocks and normalized adoption terminal value zero,

`V_k(z)=log[exp(δ_z+η_k p_z)+exp(β Σ_z' Q_zz' V_k(z'))]`,

`P_k(adopt|z)=logistic[δ_z+η_k p_z-β Σ_z' Q_zz' V_k(z')]`,

`S_z=Σ_k w_k P_k(adopt|z)`.

- The implementation passes the consumer Bellman residual to official SciPy `root(method="hybr")` from zero values and requires its maximum absolute residual below `1e-12`.
- It then solves `S_z(δ)=observed share_z` jointly for mean utilities in all states.
- For the observed cross sections, each state draws a new cohort from the declared type distribution; the shares are conditional on initial nonownership.
- The estimated mean utilities are projected onto an intercept and current price.
- State prices are exogenous in this model; known `Q`, discount factor, type distribution and utility scale are imposed, while price-state variation identifies the intercept and mean price slope.
- The code records observed counts, model-predicted shares, inverted mean utilities, regression residuals, rank and both Bellman and share-inversion residuals.
- A price change recomputes values and shares from the same fitted intercept and slope, including the type-specific price effects; the value comparison is expected utility of an initially nonowning consumer at the first price state.
- Monetary surplus would additionally require a common marginal utility of income, which is not imposed here.
- This dynamic durable model has one inside product and an outside wait action.
