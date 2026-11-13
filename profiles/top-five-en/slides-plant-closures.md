Sample: Seminar Slides — Plant Closures and the Local Labor Market

A fictional study. The country, data, authors and cited works are invented. Each `##` heading is one slide.

# Plant Closures and the Local Labor Market

## Motivation

- Velmora spent €4.8 billion on plant-entry subsidies, 1995–2015
- The evaluation rule assumes a local multiplier of 1.5 jobs per plant job
- 214 large plants closed in the same period

## Question

How many local jobs does a commuting zone lose for each job lost at a closing plant?

- Counterfactual: commuting-zone employment without the closure
- Parameter: the local employment multiplier on the way out

## This paper

- Closures of plants with 500+ employees, timed by multinational headquarters
- Universe of employer-employee records linked to firm-to-firm transactions
- Stacked difference-in-differences around each closure

## Preview of findings

- Commuting zone loses 1.6 jobs per plant job lost (s.e. 0.21)
- Suppliers account for 68% of the additional loss
- Displaced workers: −9.2 pp employment after ten years
- Nondisplaced workers recover within four years

## Data

- Closure announcements: 214 plants, 1995–2015
- Employer-employee records: all private employment, 1990–2020
- Firm-to-firm transactions: all incorporated firms, 1993–2020
- Unit: commuting zone × year; 118 commuting zones

## Model

$$
E_{ct} = \alpha_{ec} + \delta_{et} + \beta\,(\text{Post}_{et} \times L_{e}) + \varepsilon_{ect}
$$

- $E_{ct}$: employment in commuting zone $c$, year $t$
- $L_e$: jobs lost at the closing plant in event $e$
- $\alpha_{ec}$, $\delta_{et}$: event × zone and event × year fixed effects
- Identification: $\mathrm{E}(\varepsilon_{ect} \mid \text{Post}_{et} \times L_e, \alpha_{ec}, \delta_{et}) = 0$
  - Closure timing set by headquarters outside Velmora

## Bottom-line quantity

- $\beta$: jobs lost in the zone per job lost at the plant
- Compared with 1.5 in the subsidy evaluation rule

## Pre-trends

- Treated and matched zones follow the same employment path for five years before the announcement

## Commuting-zone employment

| Jobs per plant job lost | Estimate | s.e. |
|:--|--:|--:|
| Commuting zone | −1.62 | 0.21 |
| Commuting zone, matched controls | −1.58 | 0.19 |
| Local suppliers | −0.41 | 0.07 |

## Workers

- Displaced workers: −9.2 pp employment ten years after the closure
- Nondisplaced workers in the zone: back to the pre-announcement employment rate within four years

## Bottom line

- Local multiplier of 1.6 on the way out, close to the 1.5 assumed on the way in
- The supply chain carries 68% of the additional loss
- The long-run cost of a closure falls on the workers it displaces
