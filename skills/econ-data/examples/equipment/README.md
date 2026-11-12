# Equipment renewal and technology choice

Use this fictional example for dynamic choice estimation, Bellman derivatives, firm-level inference and investment decisions. The [specification](specification.json) fixes the economic question, simulation, inference and technology costs. The [executable example](run.py) passes their outputs through the existing data and dynamic runners.

1. **Output: adopted investment question; consumer: data construction.** Compare replacement timing with technology choice over the firm's discounted operating horizon. Read the specification's actors, information, incentives, constraints and identifying state variation. The formulation operation binds the selected question to the specification hash.
2. **Output: shared firm and choice tables; consumer: estimation.** Generate 480 firms observed for 32 quarters. DuckDB normalizes source fields and quarter indices into keyed Parquet tables. Assembly joins each choice to its firm, preserves the 15,360 row identities and records definitions, source hashes, keys, clustering and the fitted sample.
3. **Output: fitted costs and covariance; consumer: technology calculation.** Execute `MC-replacement-ddc` through `research_dynamic.py run`. Its pinned official ruspy criterion estimates maintenance and replacement costs. Three starting values use the same sample and objective. Differentiate the original Bellman equation, sum action scores within firms and combine their outer products with conditional expected information. Save the cost covariance and numerical diagnostics.
4. **Output: net present gains and selected technology; consumer: prose, exhibits and project decisions.** Re-solve each technology at the fitted costs. Average its inclusive-value change over the same initial-state population, convert to thousand JPY per machine and subtract its adoption cost once. Read `result-index.json` for the feasible choice, 95% intervals and pairwise contrasts using the full gain covariance. Retain identifying conditions, inference scope and finite-horizon diagnostics in the internal working record.

Run from the repository or extracted plugin runtime:

```sh
python skills/econ-data/examples/equipment/run.py --output /path/to/private/equipment-run
```

The flat-export command is `python equipment-example.py --output /path/to/private/equipment-run`. Each invocation creates a fresh output directory. Restore the selected interpreter from [the dynamic requirements](../../scripts/requirements-dynamic.txt) and [the shared-table dependencies](../../references/research-data.md#shared-tables-across-sql-python-r-and-julia).

The official [ruspy criterion factory](https://github.com/OpenSourceEconomics/ruspy/blob/414e9f98e3b1cf19544b1ca3b1e544ac5751c1e9/ruspy/estimation/criterion_function.py) returns likelihood and transition functions. The existing runner maps its replacement timing to the adopted reset-to-zero model and checks both likelihoods on the same observations. NumPy solves the implicit-derivative systems and constructs the firm-cluster covariance; SciPy supplies the Bellman solver and normal quantile. The saved result records the actual package versions, producer hashes and inference inputs.

`result-index.json` links the formulation, shared tables, official fit and technology solutions. Its `parameters`, `replacement_probabilities`, `decision_quantities` and `uncertainty` supply named quantities to consumers; `internal` retains the scientific and execution record. A changed cost, sample or technology regenerates these calculations. A display change reads the selected saved result.

## Write and render the investment comparison

1. **Output: original study prose; consumer: composition.** Read the complete [English profile](../../../../profiles/default-micro/equipment-study-en.md) or [Japanese profile](../../../../profiles/default-micro/equipment-study-ja.md). Carry the recurring replacement choice into permanent adoption through costs, continuation values and the saved net-gain comparison.
2. **Output: saved-result displays and material bundles; consumer: rendering.** Run [materials.py](materials.py) against the completed generation. It binds the result, specification and producer, retains inference internally, and creates cost estimates, replacement probabilities and net-present-gain displays through Gallery. The existing `brief` and `structural` templates consume the same result IDs.
3. **Output: inspected document and presentation; consumer: researcher.** Render each selected bundle through the existing meeting command. Inspect the prose, labels, units, intervals and page layout; presentation edits consume the saved numerical results.

```sh
python skills/econ-data/examples/equipment/materials.py \
  --root /path/to/project --run /path/to/project/equipment-run \
  --output /path/to/project/equipment-ja --language ja
python harness/research.py meeting render --root /path/to/project \
  --bundle /path/to/project/equipment-ja/brief \
  --output /path/to/project/equipment-ja/brief-html --format html
python harness/research.py meeting render --root /path/to/project \
  --bundle /path/to/project/equipment-ja/structural \
  --output /path/to/project/equipment-ja/structural-pdf --format pdf
```

Use `--language en` and fresh destinations for English materials. In the flat export, the producer is `equipment-materials.py` and the renderer is `research.py`. Select an interpreter with the [artifact-rendering dependencies](../../../econ-writing/references/result-artifacts.md). The declared root contains the saved generation, its specification and producer, and the output destination.
