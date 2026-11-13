# Subscription Support and Quarterly Contribution

## Abstract

Subscription firms allocate support among customers whose renewal decisions respond to the service they receive. We study this allocation in a fictional economy of 8,000 customers, using randomized support to learn and evaluate a policy with an 800-contact capacity. A renewed contract contributes JPY 20,000 and a contact costs JPY 2,000. We estimate action-specific renewal probabilities on 4,000 training customers, use these records to select a feasible allocation, and evaluate its quarterly contribution on a separate cohort of 4,000 customers. The selected policy raises contribution by JPY 896 per evaluation customer relative to the existing service; the 95% confidence interval is [675, 1,117]. Its gain over cancellation-risk targeting with the same contact capacity is JPY 787, with a 95% interval of [506, 1,069]. Customers reporting onboarding needs have a renewal response 28.14 percentage points above that of the other recorded group, with a 95% interval of [22.94, 33.34]. This response gradient links information about customers' needs to the return on scarce support capacity.

## Introduction

Subscription firms choose which customers receive help using their services. A support contact reduces the effort of learning the service and raises the benefit of continued use. Customers respond by revising their renewal decisions, and the firm earns a contribution from the contracts they renew. When the firm has a fixed number of contacts available, the return to support depends on the customers receiving those contacts. The relevant economic question is how to allocate this capacity to maximize the contribution from the entire customer cohort.

The allocation combines a customer choice with a resource decision. Customers compare the utility of continued service with the value of their outside option. The firm chooses whom to contact using information available before renewal. A customer's response to contact changes the probability that the firm receives the contract margin, while every contact incurs a cost. Together, the response, margin and cost determine the incremental contribution of support. Capacity then makes the ranking of these increments consequential: assigning a contact to one customer uses a slot that the firm could assign to another.

We examine this choice in a fictional economy with 8,000 subscribers. The firm observes a continuous measure of prior disengagement and an indicator of reported onboarding needs. Disengagement lowers the utility of renewing, and support raises that utility by an amount related to the recorded need. A renewed contract contributes JPY 20,000 during the quarter. The firm pays JPY 2,000 for a contact and can allocate 800 contacts among the 4,000 customers in the evaluation cohort. These primitives give the allocation problem a common monetary objective and a defined scale of operation.

Randomized support supplies the evidence used to construct the allocation. Each customer receives support with probability one-half before the renewal outcome is observed. We use 4,000 customers to estimate renewal under each action and to learn a policy tree. The tree assigns an incremental contribution to each evaluation customer from their prior information. An integer allocation then selects contacts within the firm's capacity and JPY 1.6 million budget. Training-fitted contribution ranks this allocation alongside the existing service and a policy that contacts customers with the lowest predicted renewal probability under that service.

The remaining 4,000 customers provide the evaluation of these fixed allocations. For each candidate, we estimate the contribution that the firm receives after paying for the assigned contacts. Evaluation uses the same customers, contract margin and quarterly outcome across candidates. Their paired contribution differences therefore measure the return to changing the allocation over a common cohort. The comparison with the existing service measures the value of deploying the selected support program. The comparison with risk targeting measures the value of changing recipients while holding the number and cost of contacts fixed.

The selected allocation raises quarterly contribution by JPY 896 per evaluation customer, with a 95% confidence interval of [675, 1,117]. It contacts 800 customers at a total cost of JPY 1.6 million. Cancellation-risk targeting uses the same resources and raises contribution by JPY 109 per evaluation customer, with a 95% interval of [−134, 351]. The selected allocation's paired gain over risk targeting is JPY 787, with a 95% interval of [506, 1,069]. The monetary comparison thus gives a direct value to the information used in assigning the available contacts.

Customers' responses explain the return to this assignment. Among customers reporting onboarding needs, support raises renewal by 30.09 percentage points, with a 95% confidence interval of [26.59, 33.58]. The estimated effect for the group with need indicator zero is 1.95 percentage points, with a 95% interval of [−1.90, 5.80]. Their direct contrast is 28.14 percentage points, with a 95% interval of [22.94, 33.34]. Because a renewal generates the same contract margin across customers, this response gradient also orders the corresponding group-level increments in contribution before the contact cost.

The study connects three economic objects within one allocation problem. The renewal model explains how support changes a customer's choice. Random assignment measures that response and supplies action-specific rewards for policy learning. The resource-constrained allocation converts those rewards into a feasible operating decision, which the evaluation values in money. This sequence makes the information needed for the decision explicit: the firm uses prior customer characteristics to predict the contribution induced by support and deploys its capacity where the predicted increment is greatest.

The analysis also gives a common interpretation to the prediction and policy results. Renewal predictions describe the outcome under an assigned service and enter the evaluation of every candidate. The support response connects the two actions, and the contact cost converts that response into an incremental payoff. The policy comparison aggregates these payoffs over the same customer cohort. Following these connections from customer choice to total contribution explains why the evaluation includes both group effects and complete allocation values, and why the selected action is determined before reading the evaluation outcomes.

The operating scale supplies a further economic interpretation of the gain. Eight hundred contacts cover 20% of the evaluation cohort and cost JPY 400 per cohort member. The learned allocation raises the estimated cohort renewal rate from 51.21% to 57.69%. The paired increase is 6.48 percentage points, with a 95% interval of [5.37, 7.58]. At the JPY 20,000 contract margin, the additional renewals generate the gross return from which the JPY 400 cost is deducted. The resulting JPY 896 net gain connects the estimated behavioral change to the firm's quarterly accounts.

This accounting also clarifies the value of assigning a fixed resource. The learned policy's estimated total gain is JPY 3.583 million for the evaluation cohort, with a 95% interval of [2.699, 4.467] million. Its gain over risk targeting is JPY 3.149 million, with a 95% interval of [2.022, 4.275] million. Both policies use the same support budget. Their comparison therefore values the allocation of an existing operating capacity, while the baseline comparison values the decision to deploy that capacity for support. Each margin has an observed policy counterpart and an estimated monetary return.

## Customer choice and support allocation

### Renewal incentives

A customer receives utility from continued access to the service and incurs the effort required to use it. Prior disengagement summarizes a reduction in the value of continued access. Onboarding support reduces the effort of using the service, with a larger benefit for customers who have reported needing help. The customer compares the resulting utility with the outside option and renews when continued service has the higher value. This comparison supplies the behavioral link from contact to the firm's renewal revenue.

Let $r_i$ denote prior disengagement and let $z_i$ be the indicator of reported onboarding need. The service choice is $a_i\in\{0,1\}$, with one denoting support. The utility difference between renewal and the outside option in the fictional economy is

$$u_i(a_i)=2-4r_i+a_i(0.2+1.6z_i)-\varepsilon_i.$$

The customer renews when this difference is positive. Disengagement ranges from zero to one, and the customer-specific utility shock has the standard logistic distribution. These primitives imply the conditional renewal probability

$$q_i(a)=\Lambda\{2-4r_i+a(0.2+1.6z_i)\},\qquad
\Lambda(v)=\frac{\exp(v)}{1+\exp(v)}.$$

The response to support is $\tau_i=q_i(1)-q_i(0)$. This response is a probability change, so multiplying it by 100 gives its magnitude in percentage points. The utility increment is 0.2 for customers with need indicator zero and 1.8 for customers with need indicator one. The same increment produces a renewal response that also depends on the customer's initial position along the logistic curve. Prior disengagement and reported need therefore enter the allocation through their joint effect on the probability of a renewed contract.

The curvature of the renewal probability explains this joint dependence. Writing the initial utility index as $v$ and the support increment as $d$, the response is $\Lambda(v+d)-\Lambda(v)$. Its slope with respect to the initial index is $\Lambda'(v+d)-\Lambda'(v)$. The response reaches its maximum at $v=-d/2$, where the support interval is centered on the steepest part of the logistic curve. In economic terms, support produces its largest renewal response for customers whose service choice is most responsive over the utility change delivered by the contact.

Reported need changes both the size of that utility change and the location of the largest response. It raises the value of receiving help, while disengagement determines the customer's starting utility. The two observed characteristics thus describe a response surface over which the firm can allocate support. The empirical procedure learns this surface from randomized records. The resulting action-specific predictions supply the expected contract returns used in the allocation problem.

At the response maximum, the two utility indices are $-d/2$ and $d/2$. The resulting probability change is $\Lambda(d/2)-\Lambda(-d/2)=\tanh(d/4)$. For the need-zero utility increment of 0.2, the maximum is 5.00 percentage points at disengagement 0.525. For the need-one increment of 1.8, the maximum is 42.19 percentage points at disengagement 0.725. These are implications of the specified customer-choice model. They show how the intensity of the benefit from support changes the behavioral return that a contact can generate.

The locations of these maxima also describe which customers a response-based rule values. A customer's prior disengagement moves the starting utility continuously. Support then shifts that utility by the increment associated with recorded need. Near the response maximum, this shift traverses a large change in the probability of choosing renewal. Toward the ends of the disengagement range, the same utility increment traverses a flatter portion of the probability curve. This curvature gives the joint customer information an explicit role in predicting the return from a contact.

### The return to a contact

The firm receives JPY 20,000 from each renewed contract after the service costs included in the contract margin. A contact costs JPY 2,000. Let $N=4,000$ denote the evaluation cohort and measure contribution in thousand JPY. Expected quarterly contribution under the contact vector $a$ is

$$\Pi(a)=\sum_{i=1}^{N}\left[20q_i(0)+a_i(20\tau_i-2)\right].$$

The first term is the contribution from renewal under the existing service. The second term is the increment induced by the assigned contacts. Its customer-specific component, $g_i=20\tau_i-2$, combines the additional contract return with the cost of delivering support. A contact has a positive expected increment when the renewal response exceeds 0.10, or 10 percentage points. This threshold follows directly from the ratio of the contact cost to the contract margin.

The threshold puts the behavioral response on a monetary scale. A larger renewal response increases the expected number of retained contracts, and the margin converts those contracts into contribution. The contact cost is paid when support is delivered. Each assigned customer therefore contributes an expected increment defined before the renewal outcome is realized. Summing those increments over recipients gives the expected contribution gain from the entire support program.

Capacity introduces a second comparison. A positive increment makes a contact valuable on its own, and the available slots determine which valuable contacts the firm can deliver. With a capacity of 800 and a contact budget of 1,600 thousand JPY, the feasible allocation solves

$$\max_{a_i\in\{0,1\}}\sum_{i=1}^{N}a_i g_i
\quad\text{subject to}\quad
\sum_i a_i\leq800,\qquad 2\sum_i a_i\leq1,600.$$

Equal contact costs make these two limits describe the same maximum operating scale. The firm orders positive increments and assigns the available slots to the largest ones. The comparison across customers gives each slot an opportunity cost: using it for a lower increment gives up the contribution generated by a higher-ranked feasible contact. The allocation responds to that opportunity cost by concentrating support where its predicted contribution is greatest.

This ordering follows from a direct comparison of feasible assignments. Consider two customers, one contacted and one assigned the existing service. Moving the contact to the customer with the higher increment changes expected contribution by the difference in their increments and keeps total spending fixed. Repeating this comparison places the available contacts at the top of the increment ranking. The exchange argument explains why the firm's objective and equal contact costs lead to a ranked allocation.

Write the ordered positive increments as $g_{(1)}\geq g_{(2)}\geq\cdots$. For capacity $K$, the support gain is the sum of the first $K$ increments up to the available positive-return customers. An additional slot has the value of the next increment in this order. The firm's own allocation thus defines the marginal value of capacity through the return on the next customer it can serve. The evaluated 800-contact policy provides the complete operating decision at the adopted capacity; the ranking explains the resource tradeoff within that decision.

The cost-to-margin ratio and the capacity ranking perform successive parts of the choice. The ratio of 2 to 20 gives the 10-percentage-point renewal response at which a contact covers its cost. The ranking then compares the profitable contacts with one another. In the specified model, the largest need-one response gives an incremental contribution of JPY 6,438 for a contact. This amount follows from the 42.19-percentage-point response, the JPY 20,000 contract margin and the JPY 2,000 contact cost. The model therefore gives both the participation threshold for support and the payoff comparison allocating scarce slots.

### From estimated responses to feasible policies

The implemented allocation uses rewards learned from the training records. A policy tree partitions customers by their pretreatment characteristics and assigns an action-specific reward to each leaf. The predicted increment associated with a customer is the difference between the two rewards in the customer's leaf. The resource allocation applies the contact and budget constraints to these fitted increments. This construction carries the customer's observed information through a common prediction rule into a contact decision.

We compare this learned allocation with two operating choices. The existing service supplies the baseline contribution for the cohort. Cancellation-risk targeting contacts the 800 customers with the lowest training-fitted renewal probability under that service, using customer identity to order ties. The learned allocation uses the tree's incremental rewards and the same resource limits. The candidates therefore attach concrete service choices to the observed customer information, and each produces a complete vector of actions over the evaluation cohort.

Training-fitted net contribution selects among these vectors. The criterion averages the fitted contribution under each customer's assigned action, including the contact cost. It evaluates all candidates on the evaluation cohort's pretreatment characteristics. The chosen vector is then held fixed for the outcome comparison. The decision consequently connects the trained response model, the actual customers available for contact and the firm's stated quarterly objective.

## Experimental design

### Population, timing and observed outcomes

The fictional economy contains 8,000 customers observed for one renewal quarter. Each record contains the customer identity, prior disengagement, reported onboarding need, assigned support and observed renewal. Pretreatment characteristics are recorded before the support assignment. The customer receives the assigned service and then chooses whether to renew. This timing gives the firm the same information at policy assignment that appears in the training and evaluation records.

Support is assigned independently to each customer with probability one-half. Customer identity fixes a partition into 4,000 training customers and 4,000 evaluation customers. The training records supply the outcome predictions and policy rewards. The evaluation cohort supplies the observed outcomes used to value the resulting allocations. Every candidate policy assigns an action to each member of this same evaluation cohort, so its reported contribution uses a common denominator of 4,000 customers.

Customer records are organized into shared customer and renewal tables. The customer table gives one row per identity and its pretreatment characteristics. The renewal table attaches the assigned action and quarterly outcome to that identity. Joining these records produces one observation per customer's renewal decision. This observation is the unit used in the outcome models, the evaluation scores and the subsequent aggregation into policy values.

The outcome is an indicator equal to one for a renewed contract. Multiplying it by 20 gives the contract contribution in thousand JPY. Subtracting two for an assigned contact gives net contribution under the service choice. The same conversion appears in the learning rewards and in the final policy evaluation. As a result, the allocation rule is trained on the economic return that the policy comparison subsequently measures.

### Outcome predictions and learned rewards

We fit a separate renewal model for each support action using the training customers. The predictors are prior disengagement and reported onboarding need. Each random forest contains 200 trees, uses a minimum leaf size of 40 and has maximum depth six. These models describe how renewal varies over the observed characteristics within each action. Their fitted probabilities provide the two expected outcomes needed to evaluate a prospective contact.

Policy learning uses four folds of the training sample. For each fold, the outcome models are fitted using the other training observations, and the fitted models predict both actions for customers in the held-out fold. The predicted probabilities are combined with the customer's assigned action and observed outcome to form action-specific rewards. Repeating this operation across the four folds supplies a reward pair for every training customer. The policy tree then uses these pairs and the pretreatment characteristics to learn how the value of support varies across customers.

To state the reward construction, let $A_i$ denote randomized support and let $Y_i$ denote observed renewal. Write $\widehat m_a(X_i)$ for the fitted renewal probability under action $a$, with $X_i=(r_i,z_i)$. The augmented renewal score for action $a$ is

$$\widehat\psi_i(a)=\widehat m_a(X_i)
+\frac{\mathbf{1}\{A_i=a\}}{0.5}
\{Y_i-\widehat m_a(X_i)\}.$$

The monetary reward for that action is $20\widehat\psi_i(a)-2a$. The fitted mean supplies a prediction for each customer, and the randomized observed outcome supplies its assignment-weighted correction. In the training folds, these rewards give the policy tree a common contribution measure for comparing actions across customer characteristics. The tree has maximum depth two and a minimum leaf size of 100, so the learned partition links a small sequence of customer characteristics to the two action rewards.

After learning, the tree maps each evaluation customer's pretreatment information into fitted leaf rewards. Their difference supplies the incremental contribution used by the integer allocation. The solver assigns contacts within the 800-person capacity and JPY 1.6 million budget. The resulting vector identifies both the customers receiving support and the total resources required to implement it. This completed allocation is the learned-policy candidate in the subsequent comparison.

Cancellation-risk targeting uses the outcome model for the existing service to order the same evaluation customers. It contacts the 800 lowest predicted renewal probabilities. The baseline assigns the existing service to every customer. Training-fitted outcome means then give each complete allocation its predicted net contribution. The highest value selects the operating policy; exact ties use contact count and the adopted candidate order. This selection takes the observed customer cohort and the trained response models as inputs.

### Policy values and paired comparisons

We evaluate a fixed allocation $a^{(k)}$ using the outcome models fitted on all training customers. Its estimated quarterly contribution per evaluation customer is

$$\widehat W_k=\frac{1}{N}\sum_{i=1}^{N}
\left[20\widehat\psi_i\{a_i^{(k)}\}-2a_i^{(k)}\right],\qquad N=4,000.$$

The score selects the fitted outcome and randomized correction for the action prescribed by the policy. The cost term charges the policy for every assigned contact. Averaging over all evaluation customers puts the contract returns and contact spending on the same population basis. The primary comparison uses the per-customer contribution difference between two policies. Multiplying this difference by the cohort size gives their quarterly total gain. For a support program relative to the existing service, dividing that gain by the program's contact count gives its gain per contact.

Two contrasts answer the allocation question. The learned policy's value relative to the baseline measures the gain from adopting the support program. Its value relative to risk targeting measures the gain from changing recipients at the same operating scale. Both contrasts use the customers' contributions to the paired policy values. Their saved joint covariance supplies the standard errors and 95% confidence intervals reported in the results.

The group analysis uses the two reported-need categories fixed before policy evaluation. Within each category, we average the augmented renewal-score difference between support and the existing service. The result is a renewal effect for that recorded population. We also evaluate the direct difference between the two group effects and retain its 95% interval. This comparison gives the response gradient its own estimated magnitude, which the economic model then translates into the value of allocating contacts.

The score construction carries the assigned support probability into each outcome comparison. With assignment probability one-half, a customer's observed residual under an action receives weight two in that action's score. The fitted outcome remains the starting value for every customer. Averaging the resulting scores over the prescribed actions produces the policy renewal rate. Contract contribution and contact spending are then applied to that rate and the fixed contact vector, respectively. This order preserves the relationship between the behavioral estimand and the firm's payoff.

For joint inference, define $e_{ik}$ as customer $i$'s normalized monetary residual correction for candidate $k$:

$$e_{ik}=\frac{20}{N}\frac{\mathbf{1}\{A_i=a_i^{(k)}\}}{0.5}
\{Y_i-\widehat m_{a_i^{(k)}}(X_i)\}.$$

The saved covariance matrix is $\widehat C=\sum_i e_i e_i'$, where $e_i$ contains that customer's correction for all three policies. The standard error for a paired contrast $k-j$ is $\sqrt{\widehat C_{kk}+\widehat C_{jj}-2\widehat C_{kj}}$. This calculation uses the common evaluation records directly. It is the source of the numerical intervals attached to the policy comparisons in the results.

The monetary and renewal comparisons have an exact accounting relation. Let $c_k$ denote contact spending per evaluation customer under policy $k$, in thousand JPY. Its estimated renewal rate is $(\widehat W_k+c_k)/20$. For a comparison with the baseline, the renewal change is therefore the net-contribution change plus contact spending, divided by the contract margin. A comparison between the two 800-contact policies uses equal spending. These linear transformations also carry the saved interval endpoints into renewal units, keeping the policy and behavioral results tied to the same estimated contrast.

Prediction is evaluated on the 1,933 evaluation customers assigned the existing service. For these customers, the Brier loss averages the squared difference between the predicted renewal probability and observed renewal. The calibration exhibit groups predictions into intervals of width 0.2 and compares each group's mean prediction with its observed renewal rate. The plot therefore evaluates the probability forecast that enters risk targeting and the baseline outcome component of the policy scores.

These calculations use the same renewal outcome to inform the firm's decision. Training predictions and rewards determine the feasible contact allocations. Evaluation records supply the group effects describing the response gradient and the policy values measuring the contribution of each fixed allocation. The shared quarterly outcome and monetary conversion connect the behavioral interpretation to the firm's payoff comparison.

## Results

### Selection from training-fitted contribution

Training-fitted quarterly contribution is JPY 9.978 thousand per evaluation customer for the existing service, JPY 10.528 thousand for risk targeting and JPY 10.780 thousand for the learned allocation. This ordering selects the learned policy. The criterion uses the action-specific predictions from the training records and the evaluation customers' pretreatment information. It therefore chooses a complete, feasible contact vector using the information available when the firm assigns support.

The training criterion and the evaluated outcome describe successive stages of the decision. The criterion supplies the firm's choice among candidates. Evaluation then measures the contribution of the fixed choice on the randomized customer records. The selected allocation uses all 800 contact slots and the associated JPY 1.6 million budget. This operating scale is the same as that of risk targeting, making the comparison between them a valuation of the recipients selected by their respective rules.

The following results explain that valuation through the customers' renewal responses. We first examine the response gradient across recorded needs, then evaluate the contribution of the complete allocations. Renewal rates and contact spending translate that contribution back into the behavior and resources generating it. Finally, the calibration evidence describes the probability predictions used in the candidate construction and evaluation.

### Renewal responses and recorded needs

Customers reporting onboarding needs have an estimated support effect of 30.09 percentage points, with a 95% confidence interval of [26.59, 33.58]. This group contains 1,990 evaluation customers. For the 2,010 customers with need indicator zero, the estimated effect is 1.95 percentage points, with a 95% interval of [−1.90, 5.80]. The estimates measure changes in the probability of renewing during the same quarter under the two assigned services.

The direct difference between the group effects is 28.14 percentage points, with a 95% interval of [22.94, 33.34]. This gradient gives reported need an economic role in support allocation. A contact raises the utility of continued use by more for customers who reported needing help. The resulting renewal response increases the expected return on their contracts. Because contract margins and contact costs are common across customers, the response enters the contribution ranking through a common monetary conversion.

The group estimates can be read against the 10-percentage-point response needed to cover a contact's cost. The estimated effect for the need-one group is 30.09 percentage points, and its 95% interval runs from 26.59 to 33.58. For the need-zero group, the estimate is 1.95 percentage points and the interval runs from −1.90 to 5.80. These magnitudes place the group's renewal response beside the firm's cost-to-margin ratio, making the economic comparison visible in the units of the behavioral outcome.

The learned policy uses prior disengagement together with the need indicator to assign rewards. Disengagement locates the customer's initial propensity to renew, and need changes the utility gain from support. Their joint role follows from the renewal model: the same contact increment is applied at different starting positions on the choice-probability curve. The tree captures this relationship through its fitted partition, and the allocation uses the resulting rewards to choose recipients within the available capacity.

### The value of the learned allocation

The selected policy contacts 800 customers and incurs JPY 1.6 million in support costs. Its estimated quarterly contribution is JPY 11.137 thousand per evaluation customer. The existing service yields JPY 10.242 thousand over the same customer cohort. The paired difference is JPY 896, with a 95% confidence interval of [675, 1,117]. This difference values the program after paying for all contacts assigned by the policy.

The estimated renewal rate under the learned allocation is 57.69%, compared with 51.21% under the existing service. The paired increase is 6.48 percentage points, with a 95% confidence interval of [5.37, 7.58]. The contact program covers 20% of the cohort and costs JPY 400 per cohort member. Multiplying the estimated renewal increase by the JPY 20,000 contract margin and subtracting this cost gives the JPY 896 net gain. The behavioral and monetary results thus satisfy the same quarterly accounting equation.

At the cohort scale, the learned policy generates an estimated net gain of JPY 3.583 million, with a 95% interval of [2.699, 4.467] million. Dividing this gain by the 800 allocated contacts gives JPY 4,478 per contact, with a 95% interval of [3,373, 5,584]. The first quantity values implementation over the full customer base; the second expresses the program's gain per unit of the resource it uses. Both are linear transformations of the saved policy contrast and retain its contact costs.

The positive net gain corresponds to renewal revenue exceeding the expenditure on the selected contacts. The model identifies the source of this return as the change in customers' service utility. The estimated group response supplies evidence on where that change produces additional renewals, and the learned rule uses the available customer information to assign contact rewards. The evaluated contribution then measures the return to implementing the resulting contact list at the adopted scale.

### The return to changing recipients

Cancellation-risk targeting also contacts 800 customers at a cost of JPY 1.6 million. Its estimated quarterly contribution is JPY 10.350 thousand per evaluation customer. Relative to the existing service, the paired gain is JPY 109, with a 95% confidence interval of [−134, 351]. This policy gives the available contacts to customers with the lowest fitted renewal probability under the existing service.

The learned policy exceeds risk targeting by JPY 787 per evaluation customer. The paired 95% confidence interval is [506, 1,069]. Since the two policies pay for the same number of contacts, their spending terms cancel in this contrast. The contribution difference therefore follows from the renewal outcomes generated by changing the recipients. This comparison assigns an economic value to using the learned action rewards in the contact decision.

The renewal model explains the selection margin. Prior disengagement moves the customer's initial utility, and reported need changes the utility increment from support. An increment produces its largest probability response around the portion of the choice curve traversed by the intervention. A policy that uses both action rewards can place contacts where this response yields the greatest predicted contribution. The evaluated difference with risk targeting measures the outcome of applying that criterion to the fixed customer cohort.

All three policy values are estimated from the same evaluation records. Their joint covariance retains the shared contribution of each customer's randomized outcome. The reported interval for the learned-policy advantage comes from that paired contrast. It describes the quantity that determines the comparison between the two complete allocations: their difference in net contribution per member of the same cohort during the same quarter.

The renewal comparison gives the same advantage in behavioral units. Risk targeting yields an estimated cohort renewal rate of 53.75%. The learned allocation raises that rate by 3.94 percentage points, with a 95% interval of [2.53, 5.34]. Multiplying the paired rate difference by the contract margin gives the JPY 787 contribution advantage because the policies incur equal support expenditure. Thus, the operating-budget comparison and the renewal comparison identify the same return from changing recipients.

Across the 4,000-customer cohort, the learned allocation's gain over risk targeting is JPY 3.149 million, with a 95% interval of [2.022, 4.275] million. Relative to the common 800-contact resource, the advantage is JPY 3,936 per contact slot, with a 95% interval of [2,528, 5,343]. A slot here denotes a unit of operating capacity used by each policy. Its reported value is the difference between the programs' gains per unit of that common capacity, which makes the comparison applicable to the firm's choice of allocation rule.

Risk targeting's own increase in renewal over the existing service is 2.54 percentage points, with a 95% interval of [1.33, 3.76]. This increase generates the gross contract return from which its JPY 400 per-customer contact spending is deducted. The resulting net gain is the reported JPY 109. The learned allocation produces a larger renewal increase with the same spending, so its net advantage follows from the allocation of support across the response surface described by disengagement and reported need.

### Renewal prediction and the allocation decision

The fitted probability of renewal under the existing service has a Brier loss of 0.196 on the 1,933 evaluation customers receiving that service. The calibration exhibit pairs the mean forecast and observed renewal rate within fixed probability intervals of width 0.2. Each displayed point refers to the customers whose fitted probabilities fall in that interval. The exhibit places the prediction on the same zero-to-one probability scale as the outcome mean.

The first probability interval contains 337 customers. Their mean predicted renewal probability is 0.148 and their observed renewal rate is 0.220. The next interval contains 412 customers, with mean prediction 0.277 and observed rate 0.303. These two points describe the lower end of the fitted renewal ranking used in risk targeting. Their customer counts give the scale of the populations underlying the plotted averages.

The middle interval contains 424 customers, with mean prediction 0.520 and observed renewal 0.488. The two upper intervals contain 416 and 344 customers. Their respective prediction–outcome pairs are 0.707–0.733 and 0.857–0.840. Moving through these intervals follows the same pretreatment prediction from low to high expected renewal, while the observed rates describe the outcomes of the customers receiving the existing service. The figure therefore places the ranking's actual populations beside the probability forecasts.

The squared probability loss summarizes these forecasts over individual customers. Each customer contributes the squared gap between their forecast and binary renewal outcome, and the 1,933 observations receive equal weight. The calibration points aggregate those same customers by their forecast interval. Reading the score and plot together supplies both an overall numerical measure and the probability-level comparisons relevant to the ordering used for targeting.

These predictions enter both risk targeting and the policy evaluation. Risk targeting orders customers by the fitted probability. The augmented policy score uses the fitted outcome for each prescribed action together with the randomized correction. Thus, the prediction exercise describes a component used in constructing and evaluating the allocations. The final decision follows from the complete candidate values, which combine renewal under the prescribed action with the cost of delivering it.

The resulting evidence has a common economic interpretation. The group contrast measures where support generates a larger renewal response. The policy comparison values the contacts assigned using learned rewards. The risk-targeting comparison holds operating scale fixed and measures the return to changing recipients. Taken together, these results trace the contribution gain to the allocation of support across customers whose renewal choices respond differently to the service they receive.

## Conclusion

The firm's quarterly contribution criterion selects the learned support allocation. It assigns 800 contacts within a JPY 1.6 million budget and raises estimated contribution by JPY 896 per evaluation customer relative to the existing service, with a 95% confidence interval of [675, 1,117]. Against cancellation-risk targeting at the same operating scale, its gain is JPY 787, with a 95% interval of [506, 1,069]. These comparisons value the adopted contact decision over the same 4,000 customers and quarter.

The economic mechanism runs through the customer's renewal response. Support raises the utility of continued use, and recorded onboarding need changes the size of that utility gain. The resulting response determines the additional contract return produced by a contact. Combining this return with the contact cost gives the incremental contribution that the firm can earn from serving each customer. Capacity makes the ranking of those increments determine the feasible allocation.

Randomized customer records connect this mechanism to the operating decision. Training observations supply action-specific predictions and rewards, the resource allocation converts them into a contact list, and the evaluation cohort supplies the paired contribution comparisons. The same contract margin and contact cost carry the analysis from renewal probabilities to monetary values. This connection gives the firm a complete basis for assigning its support capacity: the expected contribution induced by each contact and the return from the feasible allocation as a whole.

At the program scale, the selected allocation generates a net gain of JPY 3.583 million, with a 95% confidence interval of [2.699, 4.467] million. The gain includes the JPY 1.6 million spent on support. Its behavioral counterpart is a 6.48-percentage-point increase in the cohort's renewal rate, with a 95% interval of [5.37, 7.58]. The common accounting identity connects this rate change to the contribution available for the firm's quarterly decision.

The comparison with risk targeting values the use of information within the same operating budget. The learned rule uses action-specific rewards to assign contacts, and its evaluated advantage is JPY 3.149 million for the cohort, with a 95% interval of [2.022, 4.275] million. In the specified economy, recorded customer needs and prior disengagement describe how support changes renewal. Valuing that response at the contract margin gives a resource-allocation criterion that is expressed in the firm's objective and evaluated on its intended customers.
