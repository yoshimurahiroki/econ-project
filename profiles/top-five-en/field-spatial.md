Housing Supply and the Geography of Commuting
I. Model
Port Halvard consists of N = 1,214 neighborhoods. A mass L̄ of workers chooses a neighborhood of residence i and a neighborhood of employment j. A worker ω who chooses the pair (i, j) obtains utility
Uij(ω) = zij(ω) Bi wj / (κij Qi1−β),   (1)
where Bi is the residential amenity of neighborhood i, wj is the wage paid in neighborhood j, κij ≥ 1 is the commuting cost between i and j with κii = 1, Qi is the price of floor space in i, and β ∈ (0, 1) is the expenditure share on goods. The shock zij(ω) is drawn independently across workers and pairs from a type 2 extreme value distribution with shape ε > 1, with Pr(zij ≤ x) = exp(−x−ε). Workers choose the pair with the highest utility, so the share of workers who choose (i, j) equals
πij = (Bi wj / (κij Qi1−β))ε / Σr,s (Br ws / (κrs Qr1−β))ε.   (2)
Neighborhood i houses Ri = L̄ Σj πij residents, and neighborhood j employs Lj = L̄ Σi πij workers. Competitive firms in j produce with productivity Aj, and the wage equals
wj = Aj Ljϕ,   (3)
where ϕ is the elasticity of the wage with respect to employment and takes a negative value when decreasing returns to labor exceed agglomeration externalities. Landlords in i supply floor space Hi = H̄i Qiμi, where μi ≥ 0 is the supply elasticity of neighborhood i. Residents spend the share 1 − β of their income on floor space, so the housing market of neighborhood i clears when
Qi H̄i Qiμi = (1 − β) L̄ Σj πij wj.   (4)
An equilibrium consists of shares πij, wages wj, and prices Qi that satisfy equations (2) through (4) and Σi,j πij = 1.
PROPOSITION 1: For any parameters with ε > 1, β ∈ (0, 1), and finite ϕ, an equilibrium exists.
PROOF: Substituting (3) into (2) and (4) writes the equilibrium as a fixed point of a continuous map from the set of share vectors and bounded prices to itself. The housing market clearing condition (4) bounds each price between two positive constants that depend on the maximum and minimum wage bills. The fixed point theorem for continuous maps on compact convex sets delivers an equilibrium. Q.E.D.
II. Counterfactuals in Changes
Let x̂ = x′/x denote the proportional change of a variable x after a change in commuting costs κ̂ij. The changes solve
π̂ij = (ŵj / (κ̂ij Q̂i1−β))ε / Σr,s πrs (ŵs / (κ̂rs Q̂r1−β))ε,   (5)
ŵj = L̂jϕ,   L̂j = Σi πij π̂ij / Σi πij,   (6)
Q̂i1+μi = Σj ωij π̂ij ŵj,   ωij = πij wj / Σk πik wk.   (7)
The system (5) through (7) takes the observed shares πij, the observed wage bills, and the parameters (ε, β, ϕ, μi) as inputs, and the levels of Bi, Aj, and κij drop out. The change in welfare, measured by the expected utility of a worker, equals
Ŵ = (Σr,s πrs (ŵs / (κ̂rs Q̂r1−β))ε)1/ε.   (8)
III. Estimation
We measure the commuting flows πij from the mobile-phone records of 2.8 million workers. A worker's home is the neighborhood with the most nighttime pings, and the workplace is the neighborhood with the most weekday daytime pings. The matrix contains 1,473,796 pairs, and 288,415 pairs carry positive flows. Wages wj come from the Marden Revenue Service payroll files by workplace, and rents Qi come from 612,000 listings of the Halvard Exchange.
We set κij = exp(δ dij), where dij is the road distance in kilometers. Equation (2) implies the gravity equation
log πij = −εδ dij + φi + ψj + eij,   (9)
where φi and ψj are residence and workplace effects and eij is the error term. The Poisson regression estimate of εδ equals 0.0798 (s.e. 0.0021). The response of commuting flows to wage changes after 14 plant openings gives ε = 4.2 (s.e. 0.2), so δ = 0.0190 and commuting costs rise by 1.9 percent per kilometer.
The housing supply elasticities μi come from the 2009 zoning reform, which raised permitted floor-area ratios in 212 neighborhoods. The elasticity equals 0.4 (s.e. 0.1) in the urban core and rises with distance from the center to 2.1 (s.e. 0.3) at the periphery.
IV. The Metro Line
Line 4 of the Port Halvard metro opens in 2024 with 12 stations. The line lowers the commuting cost κij by 8 percent for every pair of neighborhoods that lie within 800 meters of stations, so κ̂ij = 0.92 for these pairs and κ̂ij = 1 for the other pairs. We solve (5) through (7) and compute welfare from (8).
TABLE 7—EFFECTS OF LINE 4
|  | Estimated supply elasticities | Core elasticity doubled |
| --- | --- | --- |
| Change in worker welfare (percent) | 1.3 | 2.2 |
| Change in rents in the 12 station neighborhoods (percent) | 9.4 | 5.1 |
| Share of the gain captured by landowners in the 12 station neighborhoods (percent) | 46 | 22 |
| Change in employment in the core (percent) | 2.8 | 5.6 |
Source: Equilibrium system (5) through (8) evaluated at the estimated parameters. Column 2 doubles the supply elasticity μi in the neighborhoods of the urban core.
Table 7 reports the results. Line 4 raises worker welfare by 1.3 percent. Rents in the 12 station neighborhoods rise by 9.4 percent, and landowners in these neighborhoods capture 46 percent of the gain. Doubling the supply elasticity in the core lowers the rent increase at stations to 5.1 percent, reduces the share captured by landowners to 22 percent, and lifts the welfare gain to 2.2 percent. Employment in the core grows by 2.8 percent under the estimated elasticities and by 5.6 percent when the elasticity doubles.
