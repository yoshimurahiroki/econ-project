# Building and simulating a model, step by step

Use this for step 3 of the [economist's procedure](../../../runtime/ECONOMIST.md) and for every question without data. Each step ends with a filled block in the worksheet `work/<topic>.md`; the next step starts only when the block is filled. The worked case throughout is "how strongly should a bonus depend on a KPI?".

## Step 1. Decision and actors

Fill:

```
Decision maker / decision:   firm / bonus rate b on the KPI (b = 0 is flat pay)
Actors and objectives:       firm: value of output minus pay; worker: pay minus effort cost, risk averse
Choices:                     firm: b and fixed pay a; worker: effort on each task
Information and timing:      firm sets (a, b); worker sees it, chooses effort; KPI realized with noise; pay made
Stake:                       pay bill and output of N workers; measurement cost K per worker
```

## Step 2. Candidate models

Search the knowledge library with the case's words and with the economic terms; read the two or three best units completely.

```sh
python3 skills/econ-knowledge/scripts/knowledge.py search --query "ボーナス 業績評価" --limit 6
python3 skills/econ-knowledge/scripts/knowledge.py plan CONTRACT-07 --read
```

Fill one row per candidate:

```
Model             Units         Key assumptions                         Prediction for the decision
single-task LEN   CONTRACT-01   one task, KPI = effort + noise, CARA     b* = 1/(1 + r c σ²): noisier KPI, weaker bonus
multitask         CONTRACT-07   KPI misses part of the valued work       b* = (f·g)/(|g|² + r c σ²): misaligned KPI, weaker bonus
relational        CONTRACT-05   repeated play, subjective evaluation     bonus capped by the value of the relationship
```

## Step 3. Fit to the case and order the ladder

For each assumption of each candidate, write whether it holds in this case and what replaces it when it fails.

```
Assumption                     Holds?   Evidence from the case             Replacement
worker risk averse             yes      fixed-salary norm                   –
KPI captures all valued work   no       sales KPI ignores after-sales care   multitask model (g2 < f2)
one-shot contract              partly   long tenure                         relational cap on the bonus
```

Then order the models into a complexity ladder. Rung 0 is the simplest standard model of the decision. Each higher rung adds one feature from the table, ordered by how much that feature can move the decision, and reduces exactly to the rung below when the feature is switched off (a parameter set to zero or infinity).

```
Rung   Model            Adds                                 Off switch
0      single task      –                                    –
1      multitask        second valued task, partial KPI       f2 = g2 = 0
2      relational cap   credible bonus limit                  cap = ∞
```

## Step 4. Write the model

Write primitives, timing, payoffs and the solution concept as equations, then derive by hand the conditions the code will compute:

1. Agent's best response from its first-order condition, with the corner cases (zero effort, participation).
2. Principal's problem with the incentive and participation constraints substituted in.
3. Equilibrium or optimum, and the comparative statics with their signs.
4. The decision rule: the action as a function of parameters and the switching condition.

Worked case: e_i = b g_i / c; surplus(b) = f·e − c|e|²/2 − r b² σ²/2; b* = (f·g)/(|g|² + r c σ²); pay the KPI bonus iff (f·g)² / (2c(|g|² + r c σ²)) > K.

## Step 5. Code and simulation

Copy the template and replace its four blocks; keep the structure.

```sh
cp skills/econ-design/templates/simulate_model.py work/<topic>_model.py
python3 work/<topic>_model.py work/<topic>_model.json
```

1. **Parameters:** each parameter with its range and the source of the range, as a dictionary of lists, and the off switch of each feature.
2. **Ladder:** one function per rung, simplest first, written exactly as in step 4: the optimum in closed form or by a numerical solver (`scipy.optimize`, the solvers in `skills/econ-data/scripts/research_numerics.py`).
3. **Checks:** each optimum against a grid search or the first-order residual of the same surplus, and each rung with its feature off against the rung below. A failed check sends the work back to step 4.
4. **Decision:** the action per parameter point and the gain that decides it.

The run climbs the ladder from rung 0 and records, for each rung, the share of decisions that change from the rung below. It stops once two consecutive rungs leave the decision unchanged or the time budget (about a minute per rung) is spent. Rungs are solved once and their results kept; a new feature adds a rung on top. Rungs that are independent of each other and cheap can run in parallel processes; a rung that is too slow is simplified before it enters the ladder: coarser grid, fewer varied parameters, fewer types or states, a closed form or a static version.

## Step 6. Read the results

Fill:

```
Recommendation:        KPI bonus in 94% of the parameter range, b between 0.20 and 0.60 at the top rung
Decisive feature:      the multitask rung changes 6% of decisions; the relational cap lowers b but changes none
Comparative statics:   b falls with KPI noise σ² and risk aversion r; falls as the KPI misses valued work (g2 < f2)
Switching condition:   flat pay when the measurement cost K exceeds (f·g)² / (2c(|g|² + r c σ²))
Model disagreement:    single-task and multitask agree when g2 = f2; multitask recommends a weaker bonus otherwise
Measure first:         g2, how much of the valued work the KPI captures; it moves b* the most
```

The answer to the user states the recommendation, the reason in terms of incentives, the switching condition and the quantity to measure, under [WRITING](../../../runtime/WRITING.md).
