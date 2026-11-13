# Subscription support and contact allocation

Use this fictional example for renewal prediction, heterogeneous support effects and capacity-constrained customer targeting. The [specification](specification.json) fixes customer utility, randomized assignment, contact costs, learning and inference. The [executable example](run.py) uses the existing data and causal runners.

1. **Output: adopted allocation question; consumer: data construction.** Compare cancellation prediction with allocating support to maximize quarterly contribution. Read the customer's renewal condition and the firm's margin, contact cost and capacity. The formulation operation binds the selected question to the specification.
2. **Output: shared customer and renewal tables; consumer: learning.** Generate 8,000 customers with pretreatment disengagement and onboarding needs. Normalize each source with DuckDB into keyed Parquet tables, then join one renewal record per customer. Save definitions, source hashes, row IDs and the fixed 4,000/4,000 training and evaluation partition.
3. **Output: fitted predictions and frozen allocations; consumer: evaluation.** Fit arm-specific random forests on training customers. Cross-fitted training rewards feed official `econml.policy.PolicyTree`; `scipy.optimize.milp` allocates up to 800 support contacts within the 1,600-thousand-JPY budget. Compare its training-predicted contribution with cancellation-risk targeting and the existing service. Save the selected allocation and every customer's action.
4. **Output: held-out policy values and group effects; consumer: prose, exhibits and decisions.** Read `result-index.json` for AIPW quarterly contribution, paired policy contrasts and 95% intervals. Read its prediction section for the control-service Brier loss and calibration bins, and its heterogeneity section for onboarding-need group effects and their direct contrast. The joint covariance preserves shared outcomes across policies. Scientific conditions and assignment corrections remain in the internal result record.

Before: “Rank customers by cancellation probability and report contacts.” After: “Rank feasible allocations by training-fitted net contribution, freeze the selected actions, and evaluate their quarterly contribution on held-out randomized records.”

Run from the repository or extracted plugin runtime:

```sh
python skills/econ-data/examples/subscription/run.py --output /path/to/private/subscription-run
```

The flat-export command is `python subscription-example.py --output /path/to/private/subscription-run`. Each invocation creates a fresh output directory. Restore the selected packages from [the causal requirements](../../scripts/requirements-causal.txt), plus [the shared-table dependencies](../../references/research-data.md#shared-tables-across-sql-python-r-and-julia), in the adopted interpreter.

The [policy contract](../../../econ-design/references/causal-models/policy.md) owns cross-fitting, fixed-cohort evaluation and exact allocation. Official [PolicyTree](https://econml.azurewebsites.net/_autosummary/econml.policy.PolicyTree.html) fits the reward matrix; [SciPy MILP](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html) solves the integer resource assignment; [RandomForestRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html) supplies training-fitted outcome means. The runner retains actual package versions, effective options, folds and original constraint residuals.

`result-index.json` binds the specification, producer, formulation, shared tables, fitted result and frozen allocations. Its `prediction`, `heterogeneity`, `decision_quantities`, `public_claims` and `uncertainty` supply saved quantities to artifact consumers. `internal` retains the full inference contract and simulation primitives. A changed utility, assignment, cost or capacity regenerates the analysis; wording and display changes consume its saved result.

## Write and render the allocation comparison

1. **Output: original study prose; consumer: composition.** Select an [English writing profile](../../../../profiles/top-five-en/PROFILE.md) for the current section or select a [Japanese writing profile](../../../../profiles/academic-ja/PROFILE.md). Connect the customer's renewal choice to randomized support effects, then to the firm's contribution and contact capacity. The [English example manuscript](manuscript-en.md) supplies the computational fixture for this example's renderer.
2. **Output: saved-result displays and material bundles; consumer: rendering.** Run [materials.py](materials.py) against the completed generation. It binds the result, specification and producer, registers named quantities and creates group-effect, allocation-gain and prediction-calibration exhibits. The `brief` and `results` templates consume the same saved result. The `manuscript` bundle consumes the example manuscript's abstract and five complete chapters and records its source binding.
3. **Output: inspected document and presentation; consumer: researcher.** Render each selected bundle through the existing meeting command. Inspect chapter connections, labels, units, intervals, figure placement and page density. Slide body and table text use the shared 28 pt baseline. Presentation edits consume saved values.

```sh
python skills/econ-data/examples/subscription/materials.py \
  --root /path/to/project --run /path/to/project/subscription-run \
  --output /path/to/project/subscription-ja --language ja
python harness/research.py meeting render --root /path/to/project \
  --bundle /path/to/project/subscription-ja/brief \
  --output /path/to/project/subscription-ja/brief-html --format html
python harness/research.py meeting render --root /path/to/project \
  --bundle /path/to/project/subscription-ja/results \
  --output /path/to/project/subscription-ja/results-pdf --format pdf
python harness/research.py meeting render --root /path/to/project \
  --bundle /path/to/project/subscription-ja/manuscript \
  --output /path/to/project/subscription-ja/manuscript-pdf --format pdf
```

Use `--language en` and fresh destinations for English materials. The flat-export producer is `subscription-materials.py` and the renderer is `research.py`. Select an interpreter with the [artifact dependencies](../../../econ-writing/references/result-artifacts.md). The declared root contains the saved generation, its specification and producer, and the output destination.
