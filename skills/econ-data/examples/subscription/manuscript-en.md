# Subscription Support and Quarterly Contribution

## Abstract

This paper studies how a subscription firm should allocate a fixed number of support contacts among customers whose renewal decisions respond to the service they receive. We focus on a fictional economy of 8,000 customers in which a renewed contract contributes JPY 20,000 and a contact costs JPY 2,000. Using randomized support for 4,000 training customers, we learn a policy that assigns 800 contacts, and we evaluate it on a separate cohort of 4,000 customers. The learned allocation raises quarterly contribution by JPY 896 per evaluation customer relative to the existing service (95% CI [675, 1,117]) and by JPY 787 relative to cancellation-risk targeting with the same capacity (95% CI [506, 1,069]). The renewal response of customers reporting onboarding needs exceeds that of other customers by 28.14 percentage points (95% CI [22.94, 33.34]), and this gradient accounts for the return to scarce support capacity.

## Introduction

Subscription firms decide which customers receive help with their services. A support contact lowers the effort of using the service, customers revise their renewal decisions, and the firm earns a contract margin on each renewal. With a fixed number of contacts, the return to support depends on who receives them. This paper asks how a firm should allocate its support capacity to maximize the quarterly contribution of its whole customer cohort, and how much the answer is worth.

The answer requires two quantities: the renewal response to a contact for each customer and the value of an allocation that ranks customers by that response. The response converts into money at the contract margin, and capacity turns the comparison of responses into a ranking problem: a slot given to one customer is a slot withheld from another. Cancellation-risk targeting ranks customers by their predicted renewal under the existing service. The contribution of a contact equals the contract margin times the change in renewal that the contact produces, less its cost.

We study this allocation in a fictional economy of 8,000 subscribers. The firm observes each customer's prior disengagement and an indicator of reported onboarding need before it assigns support. Support is randomized with probability one-half, and customer identity fixes a training cohort and an evaluation cohort of 4,000 customers each. A renewed contract contributes JPY 20,000 in the quarter, a contact costs JPY 2,000, and the firm can deliver 800 contacts within a JPY 1.6 million budget.

We use the training cohort to estimate renewal under each action and to learn a policy tree from augmented contribution scores. An integer program assigns the 800 contacts to the largest fitted increments. Training-fitted contribution then selects among three complete allocations: the existing service, cancellation-risk targeting with the same 800 contacts, and the learned allocation. The selected allocation is frozen before any evaluation outcome is read.

The learned allocation raises quarterly contribution by JPY 896 per evaluation customer relative to the existing service, with a 95% confidence interval of [675, 1,117]. Cancellation-risk targeting raises contribution by JPY 109 (95% CI [−134, 351]) with the same resources, and the learned allocation exceeds it by JPY 787 (95% CI [506, 1,069]). Over the cohort, the learned allocation generates JPY 3.583 million in net contribution, or JPY 4,478 per contact.

The customers' renewal responses explain these gains. Support raises renewal by 30.09 percentage points (95% CI [26.59, 33.58]) among customers reporting onboarding needs and by 1.95 percentage points (95% CI [−1.90, 5.80]) among the other customers. A contact covers its cost when it raises renewal by 10 percentage points, the ratio of the contact cost to the contract margin. The difference of 28.14 percentage points (95% CI [22.94, 33.34]) places the profitable contacts among customers with recorded needs, and the learned allocation finds them.

Section 2 presents the customer's renewal choice and the firm's allocation problem. Section 3 describes the experimental design and the estimators. Section 4 reports the results. Section 5 concludes.

## Customer choice and support allocation

### Renewal incentives

A customer receives utility from continued access to the service and incurs the effort of using it. Prior disengagement lowers the value of access, and onboarding support lowers the effort, with a larger benefit for customers who report needing help. The customer renews when continued service is worth more than the outside option.

Let $r_i\in[0,1]$ denote prior disengagement, $z_i$ the indicator of reported onboarding need and $a_i\in\{0,1\}$ the service choice, with one denoting support. The utility difference between renewal and the outside option is

$$u_i(a_i)=2-4r_i+a_i(0.2+1.6z_i)-\varepsilon_i,$$

where $\varepsilon_i$ has the standard logistic distribution. The renewal probability is

$$q_i(a)=\Lambda\{2-4r_i+a(0.2+1.6z_i)\},\qquad
\Lambda(v)=\frac{\exp(v)}{1+\exp(v)},$$

and the response to support is $\tau_i=q_i(1)-q_i(0)$. Support raises the utility index by 0.2 for customers with $z_i=0$ and by 1.8 for customers with $z_i=1$.

The same utility increment produces different renewal responses along the logistic curve. With initial index $v$ and increment $d$, the response $\Lambda(v+d)-\Lambda(v)$ reaches its maximum at $v=-d/2$, where it equals $\tanh(d/4)$. The maximum is 5.00 percentage points at disengagement 0.525 for customers with $z_i=0$ and 42.19 percentage points at disengagement 0.725 for customers with $z_i=1$. Reported need sets the size of the utility gain, and disengagement sets the customer's position on the curve, so the two characteristics jointly determine the return to a contact.

### The return to a contact

Measure contribution in thousand JPY and let $N=4,000$ denote the evaluation cohort. Expected quarterly contribution under the contact vector $a$ is

$$\Pi(a)=\sum_{i=1}^{N}\left[20q_i(0)+a_i(20\tau_i-2)\right].$$

The first term is contribution under the existing service, and the second is the increment from the assigned contacts. A contact to customer $i$ has expected increment $g_i=20\tau_i-2$, which is positive when the renewal response exceeds 10 percentage points. In the specified model, the largest response among customers with recorded needs gives an increment of JPY 6,438.

With 800 contacts and a budget of 1,600 thousand JPY, the firm solves

$$\max_{a_i\in\{0,1\}}\sum_{i=1}^{N}a_i g_i
\quad\text{subject to}\quad
\sum_i a_i\leq800,\qquad 2\sum_i a_i\leq1,600.$$

Equal contact costs make the two constraints coincide. Moving a contact from a lower to a higher increment raises contribution at unchanged spending, so the optimal allocation assigns the 800 slots to the largest positive increments $g_{(1)}\geq g_{(2)}\geq\cdots$, and the value of an additional slot is the next increment in this order.

### From estimated responses to feasible policies

The implemented allocation replaces $g_i$ with increments learned from the training cohort. A policy tree partitions customers by their pretreatment characteristics and assigns an action-specific reward to each leaf; a customer's fitted increment is the difference between the two rewards in the customer's leaf. We compare the learned allocation with two operating choices: the existing service for every customer, and cancellation-risk targeting, which contacts the 800 customers with the lowest training-fitted renewal probability under the existing service and orders ties by customer identity. Training-fitted net contribution on the evaluation cohort's pretreatment characteristics selects among the three complete action vectors, and the selected vector is held fixed for evaluation.

## Experimental design

### Population, timing and observed outcomes

The economy contains 8,000 customers observed for one renewal quarter. Each record contains the customer identity, prior disengagement, reported onboarding need, assigned support and observed renewal. Pretreatment characteristics are recorded before assignment, so the firm assigns support with the information that appears in the training and evaluation records.

Support is assigned independently with probability one-half. Customer identity fixes 4,000 training customers, who supply the outcome predictions and policy rewards, and 4,000 evaluation customers, whose outcomes value each fixed allocation. A customer table holds one row per identity and its pretreatment characteristics; a renewal table attaches the assigned action and quarterly outcome. Their join yields one observation per renewal decision. The outcome equals one for a renewed contract; it contributes 20 thousand JPY, and an assigned contact costs 2 thousand JPY in both the learning rewards and the evaluation.

### Outcome predictions and learned rewards

We fit a separate random forest for renewal under each action on the training customers, with prior disengagement and reported need as predictors, 200 trees, a minimum leaf size of 40 and maximum depth six. Let $A_i$ denote randomized support, $Y_i$ observed renewal, $X_i=(r_i,z_i)$, and $\widehat m_a(X_i)$ the fitted renewal probability under action $a$. The augmented renewal score for action $a$ is

$$\widehat\psi_i(a)=\widehat m_a(X_i)
+\frac{\mathbf{1}\{A_i=a\}}{0.5}
\{Y_i-\widehat m_a(X_i)\},$$

and the monetary reward is $20\widehat\psi_i(a)-2a$. Policy learning uses four folds of the training cohort: the outcome models are fitted on three folds and score the fourth, which yields a cross-fitted reward pair for every training customer. The policy tree has maximum depth two and a minimum leaf size of 100.

The fitted tree maps each evaluation customer's pretreatment characteristics into leaf rewards, and their difference is the increment passed to the integer program. The program assigns contacts within the 800-person capacity and the JPY 1.6 million budget. Exact ties in training-fitted contribution are broken by contact count and then by the adopted candidate order.

### Policy values and paired comparisons

We evaluate a fixed allocation $a^{(k)}$ with outcome models fitted on all training customers. Its estimated quarterly contribution per evaluation customer is

$$\widehat W_k=\frac{1}{N}\sum_{i=1}^{N}
\left[20\widehat\psi_i\{a_i^{(k)}\}-2a_i^{(k)}\right],\qquad N=4,000.$$

The contrast with the existing service values the support program, and the contrast with risk targeting values the change of recipients at a common operating scale. Multiplying a per-customer contrast by $N$ gives the cohort gain, and dividing the program's cohort gain by its contact count gives the gain per contact.

Let $e_{ik}$ denote customer $i$'s normalized residual correction for candidate $k$,

$$e_{ik}=\frac{20}{N}\frac{\mathbf{1}\{A_i=a_i^{(k)}\}}{0.5}
\{Y_i-\widehat m_{a_i^{(k)}}(X_i)\}.$$

The covariance matrix of the three policy values is $\widehat C=\sum_i e_i e_i'$, and the standard error of the contrast $k-j$ is $\sqrt{\widehat C_{kk}+\widehat C_{jj}-2\widehat C_{kj}}$. With contact spending $c_k$ per customer, the renewal rate under policy $k$ is $(\widehat W_k+c_k)/20$, so each monetary contrast and its interval endpoints map linearly into renewal units.

The group analysis averages the augmented score difference between support and the existing service within each reported-need category and reports the difference between the two group effects with its 95% interval. Prediction is evaluated on the 1,933 evaluation customers assigned the existing service, by the Brier loss and by a calibration exhibit that groups predictions into intervals of width 0.2.

## Results

### Selection from training-fitted contribution

Training-fitted quarterly contribution is JPY 9.978 thousand per evaluation customer for the existing service, JPY 10.528 thousand for risk targeting and JPY 10.780 thousand for the learned allocation. The criterion selects the learned allocation, which uses all 800 contacts and the JPY 1.6 million budget, the same operating scale as risk targeting.

### Renewal responses and recorded needs

The table of group effects reports the renewal response by recorded need. Among the 1,990 evaluation customers reporting onboarding needs, support raises the probability of renewal within the quarter by 30.09 percentage points, with a 95% confidence interval of [26.59, 33.58]. Among the 2,010 other customers, the effect is 1.95 percentage points, with a 95% interval of [−1.90, 5.80]. The difference between the two group effects is 28.14 percentage points, with a 95% interval of [22.94, 33.34].

The break-even response of 10 percentage points lies below the entire interval for customers with recorded needs and above the entire interval for the other customers. A contact to a customer with recorded needs covers its cost, and a contact to another customer falls short of it. The learned allocation uses prior disengagement together with the need indicator, because disengagement locates the customer on the renewal curve that the support increment traverses.

### The value of the learned allocation

The learned allocation contacts 800 customers at a cost of JPY 1.6 million. Its estimated quarterly contribution is JPY 11.137 thousand per evaluation customer, against JPY 10.242 thousand under the existing service, a difference of JPY 896 with a 95% confidence interval of [675, 1,117].

The estimated renewal rate rises from 51.21% under the existing service to 57.69% under the learned allocation, an increase of 6.48 percentage points with a 95% interval of [5.37, 7.58]. At the JPY 20,000 margin, this increase less the JPY 400 contact spending per cohort member gives the JPY 896 net gain. Over the cohort, the net gain is JPY 3.583 million, with a 95% interval of [2.699, 4.467] million, or JPY 4,478 per contact, with a 95% interval of [3,373, 5,584].

### The return to changing recipients

Cancellation-risk targeting also contacts 800 customers at a cost of JPY 1.6 million. Its estimated quarterly contribution is JPY 10.350 thousand per evaluation customer, a gain of JPY 109 over the existing service with a 95% confidence interval of [−134, 351]. Its renewal rate of 53.75% exceeds that of the existing service by 2.54 percentage points, with a 95% interval of [1.33, 3.76].

The table of allocation contrasts reports the three paired comparisons. The learned allocation exceeds risk targeting by JPY 787 per evaluation customer, with a paired 95% confidence interval of [506, 1,069]. Because both policies pay for 800 contacts, the difference arises entirely from the renewals produced by the choice of recipients: the learned allocation raises the renewal rate by 3.94 percentage points over risk targeting, with a 95% interval of [2.53, 5.34]. Over the cohort, the advantage is JPY 3.149 million, with a 95% interval of [2.022, 4.275] million, or JPY 3,936 per contact slot, with a 95% interval of [2,528, 5,343].

Risk targeting ranks customers by their renewal probability under the existing service. The contribution of a contact depends on the change in that probability, which is largest for customers with recorded needs near the steep part of the renewal curve. The learned rewards rank customers by that change.

### Renewal prediction and the allocation decision

The fitted renewal probability under the existing service has a Brier loss of 0.196 on the 1,933 evaluation customers who received that service. The calibration figure plots the mean prediction against the observed renewal rate in five intervals of width 0.2. In these intervals, the mean prediction and the observed renewal rate are 0.148 and 0.220 for 337 customers, 0.277 and 0.303 for 412 customers, 0.520 and 0.488 for 424 customers, 0.707 and 0.733 for 416 customers, and 0.857 and 0.840 for 344 customers.

These predictions order customers for risk targeting and supply the baseline outcome in every policy score. Mean predictions rise from 0.148 to 0.857 across the five intervals and observed renewal rises from 0.220 to 0.840, so the forecast orders customers by their risk of cancellation. The JPY 787 gap between the learned allocation and risk targeting is the value of ranking customers by their response to support.

## Conclusion

A subscription firm with 800 support contacts raises its quarterly contribution by JPY 896 per customer, with a 95% confidence interval of [675, 1,117], when it assigns the contacts by the learned response to support. The same contacts assigned by cancellation risk earn JPY 787 less per customer, with a 95% interval of [506, 1,069]. Over a cohort of 4,000 customers, the learned allocation adds JPY 3.583 million to contribution after JPY 1.6 million in contact costs.

The gain runs through the customers' renewal choices. Support raises renewal by 30.09 percentage points among customers who report onboarding needs and by 1.95 percentage points among other customers, against a break-even response of 10 percentage points. Randomized assignment measures this gradient, and the contract margin and contact cost convert it into the value of each slot. The firm's allocation decision therefore depends on information about how customers respond to support, and the value of that information is JPY 3.149 million per quarter at the adopted operating scale.
