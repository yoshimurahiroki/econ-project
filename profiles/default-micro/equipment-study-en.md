# Equipment Renewal and the Value of Adoption

Profile: `default-micro`. Research form: dynamic discrete choice and investment. Functions: abstract, introduction, data, model, estimation, counterfactuals and conclusion. Reader: economics researcher. Language: English.

## Input card

Use the independently authored [equipment specification](../../skills/econ-data/examples/equipment/specification.json), ID `equipment-renewal-v1`, and its [executable example](../../skills/econ-data/examples/equipment/run.py). The fictional panel follows 480 firms, each with one machine, for 32 quarters. The saved `result-index.json` owns cost estimates, replacement probabilities, net present gains and their joint covariance. Monetary gains use thousand JPY per machine at adoption and the same initial population, with 80 machines in each wear state. The common technology maximizes the population's mean net present gain.

1. **Output: opening paragraph; consumer: model exposition.** Connect the recurring choice to the investment that changes its future payoffs. Before: “We estimate a model of replacement.” After: “A renewal technology reduces the cost of future replacements. Its investment value combines those savings with firms' subsequent maintenance and replacement choices.”
2. **Output: decision paragraph; consumer: conclusion.** Put adoption costs and discounted gains on the same monetary basis, then state the selected technology with its saved interval. Before: “Advanced technology increases replacement.” After: “Advanced technology yields a net present gain of JPY 213.434 thousand per machine; the 95% confidence interval is [205.718, 221.150].”

## Abstract

A renewal technology changes the cost of future equipment replacement and the timing of maintenance decisions. We evaluate technology adoption in a fictional panel of 480 firms observed for 32 quarters. A dynamic choice model connects wear, maintenance costs and replacement costs to firms' quarterly actions. Advanced technology generates an expected discounted operating-value gain of JPY 513.434 thousand per machine. Its adoption cost is JPY 300 thousand, giving a net present gain of JPY 213.434 thousand and a 95% confidence interval of [205.718, 221.150]. The mean net present gain criterion selects advanced technology for the initial machine population.

## Introduction

Replacing a worn machine restores its operating state and requires an immediate expenditure. Continuing to use it carries maintenance costs into subsequent quarters. A technology that reduces replacement costs changes both sides of this recurring choice: the cost of replacing today and the value of operating a machine that can be replaced later. Those adjustments determine how much a firm gains from paying to adopt the technology.

We compare three permanent renewal technologies for the same initial population of 480 machines. The standard and advanced technologies cost JPY 120 thousand and JPY 300 thousand per machine to adopt and reduce each subsequent replacement cost by JPY 40 thousand and JPY 80 thousand. Each firm has an adoption budget of JPY 350 thousand. We select the common technology by its mean discounted operating-value gain after the adoption cost.

Quarterly maintenance and replacement choices provide the link between the investment and its value. We estimate the costs governing those choices, solve the resulting operating problem under each technology, and compare the gains at the same initial wear states. This sequence carries the observed replacement behavior into the investment decision.

## Data and model

The panel contains 15,360 firm-quarter observations. Each record supplies the machine's wear state, the firm's action and the next state. Wear takes six values, from 0 to 5. Maintenance advances wear by one state up to 5; replacement returns the machine to state 0. Each initial state contains 80 machines.

At wear state $s$, maintenance has payoff $-cs$ and replacement has payoff $-R+d_k$, where $d_k$ is the replacement-cost reduction under technology $k$. One payoff unit equals JPY 100 thousand. Firms observe their action-specific payoff shocks and choose the action maximizing current payoff plus discounted continuation value. With quarterly discount factor $\beta=0.95$, the value before observing these shocks satisfies

$$
V_k(s)=\log\left[\exp\{-cs+\beta V_k(\min(s+1,5))\}+\exp\{-R+d_k+\beta V_k(0)\}\right].
$$

Higher wear raises the maintenance cost relative to replacement. The variation in quarterly actions across wear states identifies the two cost parameters in the adopted model. We estimate them from the common panel and carry the fitted costs into each technology's value function.

## Estimates and investment comparison

The estimated maintenance-cost coefficient is 0.3448 payoff units per wear state, with standard error 0.0098. The estimated replacement cost is 2.7919 payoff units, with standard error 0.0564. Firm-level clustering carries the dependence among each firm's quarterly choices into inference. Under the baseline technology, the fitted replacement probability rises from 0.1049 at state 0 to 0.6653 at state 5; the corresponding standard errors are 0.0036 and 0.0094.

For each technology, we average its value-function gain over the initial machine population, convert the gain to money and subtract the adoption cost. Standard technology generates JPY 244.719 thousand in discounted operating value and costs JPY 120 thousand to adopt. Its net present gain is JPY 124.719 thousand per machine, with a 95% confidence interval of [121.234, 128.204]. Advanced technology generates JPY 513.434 thousand in operating value and costs JPY 300 thousand to adopt. Its net present gain is JPY 213.434 thousand, with a 95% confidence interval of [205.718, 221.150].

The advanced technology's net gain exceeds the standard technology's by JPY 88.715 thousand per machine; the 95% confidence interval is [84.434, 92.996]. This comparison uses the joint covariance of the gains, which share the same estimated costs. Recurring savings and the resulting changes in maintenance and replacement choices determine the return to the larger initial investment.

## Conclusion

The mean net present gain criterion selects advanced technology for the initial population. Its adoption cost of JPY 300 thousand per machine and net gain of JPY 213.434 thousand establish the investment comparison. Connecting observed quarterly choices to continuation values turns replacement behavior into a decision about permanent technology adoption.
