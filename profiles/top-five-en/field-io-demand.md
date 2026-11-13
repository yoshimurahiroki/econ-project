Identifying Heterogeneity in Demand from Diversion Data
1. Model and Data
Market t contains J products indexed j = 1, …, J and an outside option j = 0. Consumer i in market t chooses the alternative that maximizes
uijt = xjt′βi − αi pjt + ξjt + εijt,   (1)
where xjt are observed characteristics, pjt is the price, ξjt is a product-market quality observed by consumers and firms, and εijt is an independent type 1 extreme value shock. The coefficients (βi, αi) follow a distribution Fθ with αi > 0 and finite mean, indexed by a parameter vector θ. Utility from the outside option equals εi0t. Consumer i chooses product j with probability
sijt = exp(xjt′βi − αi pjt + ξjt) / (1 + Σk exp(xkt′βi − αi pkt + ξkt)),   (2)
and the market share of product j equals sjt = ∫ sijt dFθ(βi, αi).
The analyst observes market shares, prices, characteristics, cost shifters zjt, and diversion data. A stockout of product j in market t removes the product from the choice set for a period, and the diversion ratio Djkt equals the change in the share of product k divided by the share of product j before the stockout. The sample contains 3,800 retail markets in Marden, 11 products per market, and 41,800 stockout episodes.
2. Diversion Under Heterogeneity
PROPOSITION 1: Under equations (1) and (2), the diversion ratio from j to k equals
Djkt = (1/sjt) ∫ sijt sikt / (1 − sijt) dFθ.   (3)
PROOF: When product j leaves the choice set, consumer i chooses product k with probability sikt / (1 − sijt), because the extreme value shocks preserve the relative odds of the remaining alternatives. The change in the choice probability equals sikt / (1 − sijt) − sikt = sijt sikt / (1 − sijt). Integrating over Fθ and dividing by sjt gives equation (3). Q.E.D.
The formula carries the content of the identification argument. Each diversion ratio weights consumers by the product sijt sikt, which rises with the joint attractiveness of products j and k to consumer i. When all consumers share one set of coefficients, equation (3) collapses to skt/(1 − sjt), the proportional diversion of the logit model. Heterogeneity in βi and αi moves the diversion ratio of close substitutes above this benchmark, and the size of the move measures the covariance of consumer valuations of the two products. Each market adds J(J − 1) diversion ratios to the J aggregate shares, so the data deliver 121 moments per market for the parameters of Fθ.
3. Estimator
The estimator combines two sets of moment conditions. The aggregate moments equal E[ξjt(θ0) zjt] = 0, where ξjt(θ) solves sjt = sjt(ξt, θ) in each market. The diversion moments equal E[D̂jkt − Djkt(θ0)] = 0, where D̂jkt is the observed diversion ratio and Djkt(θ) is the model value from equation (3). Stack the moments into gT(θ) and define
θ̂ = argminθ gT(θ)′ WT gT(θ),   (4)
where WT is a positive definite weighting matrix that converges to W.
PROPOSITION 2: Suppose the markets are independent across t, the moment function is continuously differentiable in θ, G = E[∂gT(θ0)/∂θ] has full column rank, and Ω = Var(√T gT(θ0)) is finite. Then θ̂ is consistent, and √T(θ̂ − θ0) converges in distribution to a normal with mean zero and variance (G′WG)−1 G′WΩWG (G′WG)−1.
The proposition applies the standard asymptotic theory of generalized method of moments to the stacked moment vector. The rank condition on G holds when the diversion moments respond to every element of θ, and equation (3) shows the response: each element of θ that governs the variance of βi or αi changes the weights sijt sikt.
4. Estimates
TABLE 5—DEMAND ESTIMATES
| Parameter | Aggregate moments | Aggregate and diversion moments |
| --- | --- | --- |
| Mean price coefficient | 1.12 (0.21) | 2.31 (0.09) |
| Income gradient of the price coefficient (per decile) | −0.03 (0.04) | −0.17 (0.02) |
| Standard deviation of the quality coefficient | 0.48 (0.31) | 0.92 (0.07) |
| Own-price elasticity, first income decile | −1.74 (0.38) | −3.42 (0.11) |
| Own-price elasticity, tenth income decile | −1.51 (0.41) | −1.89 (0.14) |
| Markets | 3,800 | 3,800 |
Source: Marden retail scanner data and stockout records. Standard errors clustered by market are in parentheses.
Table 5 reports the estimates. The aggregate moments return a mean price coefficient of 1.12 (s.e. 0.21) and an income gradient of −0.03 (s.e. 0.04). Adding the diversion moments raises the mean price coefficient to 2.31 (s.e. 0.09) and the income gradient to −0.17 per decile (s.e. 0.02). The own-price elasticity equals −3.42 (s.e. 0.11) in the first income decile and −1.89 (s.e. 0.14) in the tenth decile, a gradient of 0.17 per decile. The diversion moments reduce the standard errors of the elasticities by 71 percent in the first decile and 66 percent in the tenth decile.
