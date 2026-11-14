# Subscription support and contact allocation

Use this fictional example for renewal prediction, heterogeneous support effects and capacity-constrained customer targeting. The [specification](specification.json) fixes customer utility, randomized assignment, contact costs, learning and inference. The [executable example](run.py) uses the existing data and causal runners.

1. **Adopted allocation question.** Compare cancellation prediction with allocating support to maximize quarterly contribution. Read the customer's renewal condition and the firm's margin, contact cost and capacity. The formulation operation binds the selected question to the specification.
2. **Shared customer and renewal tables.** Generate 8,000 customers with pretreatment disengagement and onboarding needs. Normalize each source with DuckDB into keyed Parquet tables, then join one renewal record per customer. Save definitions, source hashes, row IDs and the fixed 4,000/4,000 training and evaluation partition.
3. **Fitted predictions and frozen allocations.** Fit arm-specific random forests on training customers. Cross-fitted training rewards feed official `econml.policy.PolicyTree`; `scipy.optimize.milp` allocates up to 800 support contacts within the 1,600-thousand-JPY budget. Compare its training-predicted contribution with cancellation-risk targeting and the existing service. Save the selected allocation and every customer's action.
4. **Held-out policy values and group effects.** Read `result-index.json` for AIPW quarterly contribution, paired policy contrasts and 95% intervals. Read its prediction section for the control-service Brier loss and calibration bins, and its heterogeneity section for onboarding-need group effects and their direct contrast. The joint covariance preserves shared outcomes across policies. Scientific conditions and assignment corrections remain in the internal result record.

Before: “Rank customers by cancellation probability and report contacts.” After: “Rank feasible allocations by training-fitted net contribution, freeze the selected actions, and evaluate their quarterly contribution on held-out randomized records.”

Run from the repository or extracted plugin runtime:

```sh
python skills/econ-data/examples/subscription/run.py --output /path/to/private/subscription-run
```

The flat-export command is `python subscription-example.py --output /path/to/private/subscription-run`. Each invocation creates a fresh output directory. Restore the selected packages from [the causal requirements](../../scripts/requirements-causal.txt), plus [the shared-table dependencies](../../references/research-data.md#shared-tables-across-sql-python-r-and-julia), in the adopted interpreter.

The [policy contract](../../../econ-design/references/causal-models/policy.md) owns cross-fitting, fixed-cohort evaluation and exact allocation. Official [PolicyTree](https://econml.azurewebsites.net/_autosummary/econml.policy.PolicyTree.html) fits the reward matrix; [SciPy MILP](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html) solves the integer resource assignment; [RandomForestRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html) supplies training-fitted outcome means. The runner retains actual package versions, effective options, folds and original constraint residuals.

`result-index.json` binds the specification, producer, formulation, shared tables, fitted result and frozen allocations. Its `prediction`, `heterogeneity`, `decision_quantities`, `public_claims` and `uncertainty` supply saved quantities to artifact consumers. `internal` retains the full inference contract and simulation primitives. A changed utility, assignment, cost or capacity regenerates the analysis; wording and display changes consume its saved result.

## Materials

[materials.py](materials.py) registers the saved exhibits in the Gallery and creates the `brief` and `results` bundles. Each bundle holds the exhibits, their labels and units, and takes the specification ID as its title. Headings, prose and slide text enter at task time through [econ-writing](../../../econ-writing/SKILL.md) and the [borrowing procedure](../../../../runtime/WRITING.md); slide and document headings are noun phrases.

```sh
python skills/econ-data/examples/subscription/materials.py --root /path/to/project \
  --run /path/to/project/private/subscription-run --output /path/to/project/private/subscription-materials --language ja
python harness/research.py meeting render --root /path/to/project \
  --bundle /path/to/project/private/subscription-materials/results \
  --output /path/to/project/private/subscription-results-pdf --format pdf
```
