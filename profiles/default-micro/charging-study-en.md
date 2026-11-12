# Charging-Service Mergers and the Allocation of Surplus

Profile: `default-micro`. Research form: structural demand, equilibrium and welfare. Functions: abstract, introduction, model, identification, results and conclusion. Reader: economics researcher. Language: English.

## Input card

Use the independently authored [charging specification](../../skills/econ-data/examples/charging/specification.json), ID `charging-merger-v1`, and its [executable example](../../skills/econ-data/examples/charging/run.py). The fictional economy has 100 markets, three services per market and 100,000 potential 10-kWh charging occasions over one operating week. The saved `result-index.json` supplies `decision_quantities` and `uncertainty`. Monetary passages convert hundred JPY to million JPY by dividing by 10,000. Producer and total surplus include the real integration cost. Each 95% interval describes its named demand coefficient.

Composition operation: open with joint pricing and procurement, connect drivers' choices to the welfare comparison, then use the ownership and cost scenarios to explain the merger decision. Apply this progression and sentence rhythm to the current study's own model and results.

## Abstract

A charging-service merger changes the prices drivers face and the resources used to provide charging. We estimate demand in a fictional economy with 100 markets and compare joint pricing with a merger that reduces the merging services' marginal costs by 20%. Joint pricing at baseline costs changes total surplus by JPY −1.093 million over one operating week. Adding procurement savings and the real integration cost gives a net surplus gain of JPY 0.697 million. Consumer surplus changes by JPY −2.458 million and producer surplus by JPY 3.155 million. The total-surplus rule selects merger approval.

## Introduction

Combining two charging providers puts their prices under joint control. The merged firm receives the profit from drivers who switch between its services. Procurement savings also change the cost of supplying those drivers. These changes link the merger decision to participation, substitution and the resources used in charging.

We study this decision in a fictional economy with three services in each of 100 markets. Drivers choose a service or the outside option, and firms choose prices. The authority evaluates consumer and producer surplus for the same 100,000 potential charging occasions over one week. We compare baseline ownership, joint pricing at baseline costs, and the integrated merger with procurement savings. This sequence connects each change in ownership and costs to its contribution to welfare.

## Model and identification

A driver receives utility from service quality and a product-specific demand component and pays the service's price. Logit demand maps those utilities into service shares and outside participation. Each firm chooses prices to maximize profit on its products. Joint ownership makes substitution between the two merged services enter the same profit objective.

Procurement-price variation moves marginal costs and equilibrium prices. We use that variation to estimate the price coefficient from 300 product-market observations, together with service quality and an intercept. The estimated price coefficient is −0.824 normalized utility units per hundred JPY; its 95% confidence interval is [−1.005, −0.643]. The estimated quality coefficient is 0.615 normalized utility units per quality-index unit; its 95% confidence interval is [0.513, 0.717].

The fitted demand system and baseline pricing conditions recover marginal costs. We then solve joint prices at those costs and at costs reduced by 20% for the two merged services. The integrated merger uses JPY 0.200 million in real integration resources. All three scenarios use the same drivers, service qualities, outside option and operating week.

## Results and welfare

Joint pricing at baseline marginal costs changes consumer surplus by JPY −3.454 million and producer surplus by JPY 2.361 million. The resulting total-surplus change is JPY −1.093 million. The ownership change alters the merged firm's pricing incentives through substitution between its services.

Procurement savings raise the integrated merger's total surplus to JPY 38.775 million, including the integration cost. Baseline total surplus is JPY 38.078 million. The net gain is JPY 0.697 million over the common week and population. Consumer surplus changes by JPY −2.458 million and producer surplus by JPY 3.155 million. The surplus accounting links these distributional effects to the authority's objective.

## Conclusion

The total-surplus rule selects approval of the integrated merger. Joint pricing and procurement savings determine the allocation of surplus between drivers and firms. Evaluating both responses on the same population, together with the real integration cost, gives the monetary comparison supporting the decision.
