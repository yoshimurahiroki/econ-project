## Multi-arm policy learning and evaluation

Use to learn and evaluate a treatment-assignment rule: policy value on an independent holdout, budgets and capacities.

- Select `design="policy_learning"` and `target.kind="policy_value"`; the same target with `design="auto"` and randomized or selection-on-observables assignment reaches this owner.
- A policy value is the expected potential outcome under the declared action rule on its evaluation population.
- The mean of a fitted CATE surface retains its separate effect target.
- The original `options={"treatment":"d","propensity":"p","partition":"split","seed":512}` remains the binary DRPolicyTree/IPW route with its original defaults and output.

- The extension requires `options.treatment`, `partition`, `seed` and `policy`.
- Optional `options.weights` names positive pretreatment target-population weights.
- Use `inference={"type":"policy","confidence_level":0.95}` and add `cluster` for one independent cluster partition.
- Selection binds the adopted weights, confidence level and cluster column.
- All declared input columns are complete and finite.
- The data owner constructs the adopted sample before learning.
- `regressors` names pretreatment covariates for both nuisance models and tree splits.

```json
{
  "arms": ["control", "offer1", "offer2"],
  "baseline": "control",
  "value_method": "aipw",
  "propensity": {"source": "known", "columns": ["p0", "p1", "p2"]},
  "evaluation_target": "population",
  "n_folds": 3,
  "learners": {"ml_g": {"type": "random_forest_regressor", "params": {"n_estimators": 100, "min_samples_leaf": 5}}},
  "tree": {"max_depth": 2, "min_samples_leaf": 10, "honest": false},
  "objective": "net_benefit",
  "costs": {"amounts": [0, 1, 1.8], "unit": "currency units", "benefit_per_outcome": 2}
}
```
- Required policy fields are `arms`, `baseline`, `value_method`, `propensity` and `evaluation_target`.
- Arms are ordered, distinct string labels, and every arm occurs in training.
- Treatment labels are read as strings.
- Known propensity columns follow arm order, lie strictly in `(0,1)` and sum to one for every row.
- `propensity={"source":"estimated"}` instead fits a declared `ml_m` probability classifier.
- The shared DoubleML learner constructor accepts its existing learner names and native `params`; policy `ml_g` is a regressor.
- Defaults are a 100-tree random forest with minimum leaf size 5 and, for estimated propensities, logistic regression with `max_iter=1000`.
- No probability clipping, trimming or fallback occurs.

- Each training scoring fold receives predictions from its other training folds.
- Stratified folds keep the entire declared cluster together.
- Every nuisance fitting fold contains all arms.
- Held-out nuisance predictions come from models fitted to all training rows.
- Training and evaluation IDs, and cluster labels when supplied, are disjoint.
- Evaluation treatment and outcome never fit a nuisance model, tune the tree or choose an action.
- Saved fold IDs and prediction matrices record this separation.

- Arm rewards are `Gamma_ia = mu_a(X_i) + 1{A_i=a}(Y_i-mu_a(X_i))/p_a(X_i)`.
- Official `econml.policy.PolicyTree` fits the cross-fitted reward matrix with the training target weights.
- `objective="outcome"` maximizes outcome rewards.
- `objective="net_benefit"` uses `benefit_per_outcome * Gamma_ia - cost_a`; the multiplier has cost units per outcome unit.
- Costs are fixed nonnegative amounts per action, in arm order.
- Omitted costs are zero, with multiplier one in outcome units.
- Native greedy welfare splits learn the tree; depth and minimum leaf size specify its complexity.
- `min_samples_split`, `min_balancedness_tol` and `honest` are also supported.
- Selected honesty uses the native row split within training; independent evaluation supplies value inference.

### Independent holdout population value

- `evaluation_target="population"` evaluates a training-fixed tree on an independently sampled population.
- `value_method="aipw"` uses the arm score above; `"ipw"` sets the evaluation outcome-model term to zero and requires known probabilities.
- Policy value averages `Gamma_i,pi(X_i)`, baseline value averages `Gamma_i,baseline`, and gain averages their paired difference.
- Any declared arm can be the baseline.
- Each constant-arm policy value is also retained.
- Consistency, no interference, conditional exchangeability and overlap identify these values.
- Known randomization probabilities supply the assignment model.
- Estimated-propensity AIPW requires one consistent nuisance model for value consistency and the adopted nuisance product-rate conditions for inference.
- Estimated-propensity IPW would add first-order training-estimation variation; this holdout-score covariance route therefore selects AIPW for estimated probabilities.

- Weights normalize by their evaluation sum: `V_hat=sum_i w_i score_i / sum_i w_i`.
- For independent unweighted observations, actual `statspai.policy_learning.ope.doubly_robust` or `ips` returns value, SE and normal-reference endpoints using supplied training-fitted nuisance arrays and no weight cap.
- Paired gains and weighted/clustered means use native `statsmodels.WLS` with an intercept.
- HC1 multiplies centered weighted-score cross-products by `n/(n-1)`.
- Cluster covariance first sums contributions within each cluster, multiplies by `G/(G-1)`, and uses a Student t reference with `G-1` degrees of freedom.
- The joint covariance retains the policy/baseline dependence.
- Weights describe represented people; counts retain observed persons.

### Exact batch budget and capacity

- `constraints` accepts total `budget`, `max_treated` or `max_treated_fraction`, and an `arm_capacities` integer array in arm order.
- A fraction means `floor(fraction * evaluation_rows)`.
- Treatment capacity counts actions different from the baseline.
- Budget sums arm costs over evaluation persons; target weights never multiply physical counts or spending.
- Set `evaluation_target="fixed_batch"` and known propensity fields `mechanism="independent_multinomial"`, `assignment_unit="individual"` or `"cluster"`.
- Cluster assignment requires one realized arm and the same probability vector within each declared cluster.
- Complete randomization with fixed arm counts has a different dependence law and is rejected by this contract.

- Official `scipy.optimize.milp` chooses one action per person to maximize the weighted predicted tree reward, subject to the budget, capacity and integer constraints.
- Its inputs contain predictions, weights, costs and resource limits.
- Evaluation outcomes and realized treatment are absent.
- Results retain the objective, optimality gap, original constraint residuals, tree actions and final allocated actions.
- This is a batch allocation using the tree's reward predictions; the constrained actions need not themselves form a tree rule.

- The target is the weighted potential-outcome mean for this fixed evaluation cohort, conditional on covariates, training fit and allocated actions.
- Its normal reference is asymptotic over independent assignment units with no dominating contribution.
- Let `u_g` sum normalized target weights times the observed IPW residual correction for each value contrast within assignment unit `g`.
- The implemented covariance bound is `sum_g u_g u_g'`, without centering or a finite-sample multiplier.
- Conditional assignment variance is `sum_g {E[u_g u_g']-E[u_g]E[u_g]'}`; the omitted matrices are positive semidefinite.
- This is an implemented conservative second-moment derivation.
- It differs from the OPE package's centered population-score covariance.
- Normal critical values give pointwise intervals.
- Costs and assignment rates are fixed conditional quantities with zero assignment variance.
- Gains and net benefits use the same joint correction vectors.
- The raw corrections and covariance target are saved.

### Saved policy result and official comparison

- `adopted.policy` and `display.metadata.policy` preserve arms, baseline, nuisance models, training/evaluation roles, tree, objective, costs and constraints.
- `adopted.weights` defines the target and normalization.
- Main rows contain values, baseline, gain, costs, net benefits, net gain, constant-arm values and weighted assignment rates, each with its own unit, SE and interval.
- `displays.policy_assignments` contains IDs, chosen and tree-recommended actions, leaf IDs, weights, costs and training-model predictions of outcomes, effects against baseline, benefits and net benefits.
- `displays.policy_groups` contains native tree predictions by leaf and arm, including the baseline effect contrast.
- These predictions retain their model role alongside the held-out value estimates.
- Diagnostics save split/leaf arrays, folds, DR rewards, nuisance means, propensities, evaluation scores/corrections, action counts and total spending.
- The existing gallery reads these displays without fitting again.

- The official implementations divide these calculations differently.
- `policytree::policy_tree` exhaustively searches shallow multi-arm trees from an arm reward matrix; `double_robust_scores` builds rewards from binary/multi-arm GRF means and propensities.
- GRF supplies honest forest effects, nuisance predictions, sampling weights and clusters.
- EconML's DRPolicyTree constructs cross-fitted arm rewards and fits its policy-tree final model; its direct PolicyTree API accepts the externally constructed known/estimated-propensity rewards and cost adjustments used here.
- DoubleML's IRM policy entry fits binary weighted classification from its ATE score.
- StatsPAI targeting ranks binary CATE predictions under a count/fraction limit; its expected gain is a sum of predictions.
- StatsPAI OPE evaluates declared actions with observed rewards and supplied nuisance arrays.

Sources: policytree 1.2.5 [tree search](https://github.com/grf-labs/policytree/blob/b543f0fa35dcb4cbe97e28d102b20523e2fcedaf/r-package/policytree/R/policy_tree.R), [multi-arm scores](https://github.com/grf-labs/policytree/blob/b543f0fa35dcb4cbe97e28d102b20523e2fcedaf/r-package/policytree/R/multi_arm_causal_forest-scores.R) and [binary scores](https://github.com/grf-labs/policytree/blob/b543f0fa35dcb4cbe97e28d102b20523e2fcedaf/r-package/policytree/R/causal_forest-scores.R); GRF 2.6.1 [causal forest](https://github.com/grf-labs/grf/blob/5bee99b51471f76cb2d63acbc8a9b0ffec408ba0/r-package/grf/R/causal_forest.R) and [multi-arm forest](https://github.com/grf-labs/grf/blob/5bee99b51471f76cb2d63acbc8a9b0ffec408ba0/r-package/grf/R/multi_arm_causal_forest.R); EconML 0.17.0 [DRPolicyTree](https://github.com/py-why/EconML/blob/f0fc2e7d39d20e1a9d9201233fb7945e88cab0cc/econml/policy/_drlearner.py) and [PolicyTree](https://github.com/py-why/EconML/blob/f0fc2e7d39d20e1a9d9201233fb7945e88cab0cc/econml/policy/_forest/_tree.py); StatsPAI 1.43.1 [targeting](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/policy_learning/targeting.py) and [OPE](https://github.com/brycewang-stanford/StatsPAI/blob/ddb3b45f2d3fc649ea794aa15f8989bb10f8e543/src/statspai/policy_learning/ope.py); DoubleML 0.11.4 [IRM score and policy entry](https://github.com/DoubleML/doubleml-for-py/blob/96e32c9517812a8b8875dd74956704d7998f6510/doubleml/irm/irm.py) and [binary policy classification](https://github.com/DoubleML/doubleml-for-py/blob/96e32c9517812a8b8875dd74956704d7998f6510/doubleml/utils/policytree.py).
