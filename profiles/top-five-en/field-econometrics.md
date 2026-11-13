Inference with Staggered Adoption under Cluster Dependence
I. Setup
The panel contains units i = 1, …, N observed in periods t = 1, …, T. Each unit belongs to one of C clusters, and c(i) denotes the cluster of unit i. Unit i adopts the policy in period Gi and stays treated afterward, so the treatment indicator equals Dit = 1[t ≥ Gi]. The outcome equals Yit = Yit(0) + Dit τit, where Yit(0) is the untreated outcome and τit is the treatment effect of unit i in period t. The estimand at horizon h ≥ 0 equals
τh = E[τit | t − Gi = h].   (1)
ASSUMPTION 1 (Untreated outcomes): Yit(0) = αi + λt + εit with E[εit | Gi] = 0.
ASSUMPTION 2 (Clusters): Clusters are independent and identically distributed, the dependence of εit within a cluster is unrestricted, and C → ∞.
ASSUMPTION 3 (Moments): E[εit4] and E[τit4] are finite, and the number of treated units at each horizon grows in proportion to N.
II. The Two-Way Fixed-Effects Estimator
The two-way fixed-effects regression of Yit on Dit, unit effects, and period effects returns a weighted average of the treatment effects τit of treated cells. The weights sum to one, and they turn negative for treated cells in early-adopting units observed in late periods, because the regression uses these cells as controls for later adopters. In the panel of 3,100 firms, 23 percent of the treated cells receive negative weights. The estimator converges to a quantity that lies outside the range of the treatment effects when the effects grow with exposure time.
III. The Imputation Estimator
The imputation estimator proceeds in three steps. Step 1 estimates α̂i and λ̂t by least squares on the untreated cells, those with Dit = 0. Step 2 imputes the untreated outcome of every treated cell as Ŷit(0) = α̂i + λ̂t and computes τ̂it = Yit − Ŷit(0). Step 3 averages over the treated cells at horizon h:
τ̂h = (1/nh) Σi,t: t−Gi=h τ̂it,   (2)
where nh counts the treated cells at horizon h. Each treated cell enters (2) with a nonnegative weight by construction, because Step 3 averages the imputed effects with equal weights.
The variance estimator sums the estimation error within clusters. Let ψ̂i denote the influence term of unit i, which combines the deviation τ̂it − τ̂h of the unit's treated cells with the weighted imputation error that the unit's untreated cells and the untreated cells of other units contribute to Step 1. Then
V̂h = (1/nh2) Σc=1C (Σi: c(i)=c ψ̂i)2.   (3)
PROPOSITION 1: Under Assumptions 1 through 3, τ̂h is consistent for τh, and (τ̂h − τh) / V̂h1/2 converges in distribution to a standard normal as C → ∞.
PROOF: Substituting Yit = αi + λt + εit + τit for treated cells gives τ̂h − τh = (1/nh) Σ (τit − τh) + (1/nh) Σ (εit − (α̂i − αi) − (λ̂t − λt)). The least squares errors α̂i − αi and λ̂t − λt are linear in the errors εit of the untreated cells, so the right side equals a sum over clusters of terms that depend on the data of one cluster each. These terms are independent across clusters with mean zero and finite variance by Assumptions 2 and 3. The Lindeberg central limit theorem delivers the normal limit, and the law of large numbers applied to the squared cluster sums shows that V̂h converges to the limiting variance. Q.E.D.
The proposition allows arbitrary dependence of errors within a cluster and arbitrary dynamics of the treatment effects. The variance estimator (3) accounts for the dependence between the treated cells of a cluster and the untreated cells that determine their imputed outcomes, and this dependence is the source of the undercoverage of conventional standard errors.
IV. Simulations
We calibrate 14 data-generating processes to the panels of 14 benchmark applications, preserving the number of clusters, the adoption dates, and the within-cluster correlation of residuals. Each process runs 5,000 replications with a treatment effect that grows by 20 percent of the outcome standard deviation per period of exposure.
TABLE 6—COVERAGE OF 95 PERCENT CONFIDENCE INTERVALS
| Estimator and standard error | Coverage (percent) | Median interval length |
| --- | --- | --- |
| Two-way fixed effects, conventional standard error | 61.4 | 0.19 |
| Two-way fixed effects, cluster-robust standard error | 71.3 | 0.34 |
| Imputation estimator, conventional standard error | 83.7 | 0.28 |
| Imputation estimator, cluster-robust standard error (3) | 94.8 | 0.46 |
Source: 5,000 replications in each of 14 calibrated data-generating processes. Coverage is the share of replications in which the interval contains the true effect at horizon 3.
Table 6 reports the results. Two-way fixed effects with cluster-robust standard errors cover the true effect in 71.3 percent of replications. The imputation estimator with the variance estimator (3) covers the true effect in 94.8 percent of replications, with a median interval length of 0.46 in units of the outcome standard deviation. The gain in coverage of 23.5 percentage points over the two-way fixed-effects interval costs an increase in length of 0.12.
