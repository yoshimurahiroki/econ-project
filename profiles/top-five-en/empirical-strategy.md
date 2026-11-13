IV. Empirical Strategy
A. Older Workers: A Discontinuity at the Cutoff
We estimate the effect of the reform on workers at ages 60 to 62 by comparing workers born on either side of the cutoff c = January 1, 1958. Let bi denote the birth date of worker i in months relative to c, and let Di = 1[bi ≥ 0] denote assignment to the eligibility age of 63. The reduced-form regression equals
Yi = α + τ Di + β1 bi + β2 Di bi + εi,   (4)
estimated on workers with |bi| ≤ h, where Yi is an outcome of worker i averaged over ages 60 to 62, τ is the effect of the reform at the cutoff, and εi is the error term. We use a local linear specification with a triangular kernel and a bandwidth of h = 18 months, the value that minimizes the mean squared error of the estimate of τ for the first-stage outcome. We cluster standard errors by birth month.
The fuzzy design scales τ by the first stage. Let Ci equal one if worker i claims a pension by age 61. The first-stage regression replaces Yi in (4) with Ci, and the ratio of the reduced form to the first stage gives the effect of delayed claiming. We report both objects.
The design identifies τ under continuity of the conditional mean of every outcome at the cutoff. Three results verify the condition. The density of birth dates is smooth at the cutoff (p = 0.71). Predetermined characteristics measured at age 58 balance at the cutoff, with a joint p-value of 0.58 across 11 variables. Placebo cutoffs at 17 other birth dates produce estimates that center on zero, with a mean of 0.2 percentage points and a standard deviation of 0.6.
B. Firms: An Exposure Design
The reform retains workers in each firm in proportion to the share of its employees who belong to the affected cohorts. For firm j, define exposure Ej as the share of the firm's employees in 2010 who were born in the 24 months after the cutoff, and define Postt = 1[t ≥ 2018]. The number of retained workers per 100 employees, Rjt, solves the first-stage equation
Rjt = π (Ej × Postt) + Xjt′γ + μj + ηt + vjt,   (5)
and hires of age group a per 100 employees follow the outcome equation
Hjta = ψa Rjt + Xjt′δa + μj + ηt + ejta,   (6)
where μj are firm fixed effects, ηt are year fixed effects, and Xjt contains sector-by-year effects and log firm size. The coefficient ψa measures the change in hires of group a per retained older worker, and −ψ<30 equals the displacement ratio of Section III.
Exposure Ej is measured in 2010, one year before the Act passes, and fixes the cohort composition of each firm before any response. The exclusion restriction requires that exposure affects hiring through retention. We evaluate the restriction with the event-study regression
Hjt = Σk ≠ 2017 θk (Ej × 1[t = k]) + Xjt′δ + μj + ηt + ejt,   (7)
where the coefficients θk for k ≤ 2016 equal zero under the restriction and the coefficients for k ≥ 2018 trace the dynamic effect of exposure on hiring.
C. Inference and Estimand
We cluster standard errors at the firm level in equations (5) through (7) and report the first-stage F-statistic for the instrument. The instrument varies continuously, so the instrumental variables estimand is a weighted average of marginal effects of retention on hiring across the exposure distribution, with the largest weights on firms near the median exposure of 0.061. We report the effect per retained worker, which equals the ratio of the reduced-form coefficient to the first-stage coefficient.
