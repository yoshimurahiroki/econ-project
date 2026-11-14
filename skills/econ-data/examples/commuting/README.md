# Commuting support and local labor markets

Use this fictional example for market-level random assignment, shared household and market tables, equilibrium wage incidence, subgroup effects and a monetary policy comparison. The [specification](specification.json) fixes the economy, three subsidy arms, assignment and welfare valuation. The [executable example](run.py) uses the existing formulation, assembly and causal runners.

1. **Output: adopted formulation; consumer: source generation.** Read the specification. Its upstream question selects the subsidy maximizing social surplus over eight weeks. The saved `formulation.json` binds this choice to the specification hash.
2. **Output: shared tables and assignment; consumer: outcome construction.** Generate 4,800 households and 48 markets from the fixed population seed. Construct keyed household and market tables with `research_data.assemble`; `randomizr` assigns 16 markets to each subsidy. Each household keeps its ID through assignment, joins and estimation.
3. **Output: seven saved estimates; consumer: policy selection and writing.** Solve household participation and employer hiring at each subsidy, preserving each market's primitives. Verify profitable-deviation and resource-accounting residuals at `1e-8`. Join observed outcomes to shared tables, retain all assigned households and call `research_causal.py run` for each outcome. Official `estimatr::horvitz_thompson` retains cluster assignment probabilities, standard errors and 95% pointwise intervals for all three pairwise contrasts.
4. **Output: selected subsidy and result bindings; consumer: Gallery, prose and project work.** Read `result-index.json` and its seven referenced result files. The adopted decision selects the highest estimated social surplus. Use their named estimates, units and intervals for artifacts. Keep potential outcomes, equilibrium checks, source paths and the formulation comparison in the internal working record.

Run from the repository or extracted plugin runtime, with the selected Python environment's pandas and the R interpreter on `PATH`:

```sh
python skills/econ-data/examples/commuting/run.py --output /path/to/private/commuting-run
```

The output path names a new generation. The R environment uses `jsonlite` 2.0.0, `randomizr` 2.0.1.9000 at `190d5f24cb6b9782ab781952a80c72c17a4c27d4`, and `estimatr` 2.1.0 at `18209f7bdcbb5fd5b25191e4f500d7a10ea9e86b`, as recorded in [the existing dependency specification](../../scripts/requirements-causal-r.json). The [RCT interface](../../../econ-design/references/causal-models/randomization.md) defines their assignment and inference contracts. The flat export uses `python commuting-example.py --output /path/to/private/commuting-run`.

Each result retains the common sample, actual package versions, native fitted object and producer hashes. Changing an economic primitive, assignment, outcome or valuation creates a new calculation generation. Wording and layout consume the selected saved generation through the existing artifact owners.

## Materials

[materials.py](materials.py) registers the saved exhibits in the Gallery and creates the `brief` and `results` bundles. Each bundle holds the exhibits, their labels and units, and takes the specification ID as its title. Headings, prose and slide text enter at task time through [econ-writing](../../../econ-writing/SKILL.md) and the [borrowing procedure](../../../../runtime/WRITING.md); slide and document headings are noun phrases.

```sh
python skills/econ-data/examples/commuting/materials.py --root /path/to/project \
  --run /path/to/project/private/commuting-run --output /path/to/project/private/commuting-materials --language ja
python harness/research.py meeting render --root /path/to/project \
  --bundle /path/to/project/private/commuting-materials/results \
  --output /path/to/project/private/commuting-results-pdf --format pdf
```
