# Charging-service demand and merger welfare

Use this fictional example for demand IV, market-level inference, joint pricing, procurement efficiencies and a monetary merger decision. The [specification](specification.json) defines the same drivers, services and market population throughout the [executable example](run.py).

1. **Output: adopted question; consumer: data construction.** Read the specification and its comparison of the price question with the total-surplus decision. The formulation operation binds that choice to the specification hash. Drivers choose a charging service or the outside option; firms choose prices; the authority compares the two feasible ownership arrangements.
2. **Output: shared tables and analysis input; consumer: estimation.** Generate 100 markets and 300 service products from the specified primitives. PyBLP solves the original Bertrand prices. The existing assembly owner builds keyed product and market tables, attaches market population with a many-to-one join, and retains the 300 product-market IDs in the analysis sample. Its dictionary and data record carry units, source versions and construction dependencies.
3. **Output: fitted demand and two counterfactual results; consumer: economic interpretation.** Execute the existing market runner on the shared analysis table. Procurement-price variation identifies the price coefficient; quality and an intercept complete the demand equation. Official two-step GMM retains market-clustered inference. Reuse the saved native fit for ownership-only and integrated-merger scenarios. The latter reduces the merged services' marginal costs by 20%.
4. **Output: monetary comparison and selected action; consumer: prose, Gallery and project decisions.** Read `result-index.json` and its three referenced results. Its `decision_quantities` saves consumer, producer and total surplus on the fixed population, with the real integration cost deducted once from integrated-merger producer and total surplus. Use these named levels and changes for the specified total-surplus decision. Keep original-equation checks, assumptions and diagnostic records in the internal working record. Pass saved point estimates and the demand coefficients' 95% pointwise intervals with their units to the requested artifact.

Run from the repository or extracted plugin runtime using the selected Python environment:

```sh
python skills/econ-data/examples/charging/run.py --output /path/to/private/charging-run
```

The output names a new generation. The flat export command is `python charging-example.py --output /path/to/private/charging-run`. Use PyBLP 1.3.0 and its existing [market dependencies](../../scripts/requirements-markets.txt). [The market contract](../../../econ-design/references/market-models.md#differentiated-demand-and-supply) connects the equations, data, official calls and saved results. The official [Simulation](https://pyblp.readthedocs.io/en/stable/_api/pyblp.Simulation.html) generates the fictional economy; [Problem.solve](https://pyblp.readthedocs.io/en/stable/_api/pyblp.Problem.solve.html) estimates its demand.

The result index retains full-precision source bindings, original logit-share and pricing residuals, monetary accounting, native inference and the applied objective. A changed primitive, sample, model or intervention creates a new calculation generation. Changes to prose or layout consume the selected saved generation through the existing artifact owners.

## Compose from the saved comparison

1. **Output: selected passage; consumer: draft.** Read the complete [English study](../../../../profiles/default-micro/charging-study-en.md) or [Japanese study](../../../../profiles/default-micro/charging-study-ja.md). Carry the sequence from drivers' choices through joint pricing and procurement to the total-surplus decision into the current argument.
2. **Output: bound displays and materials; consumer: renderer.** Execute [materials.py](materials.py) on the saved generation. It binds the index, source specification, native result references and adopted interpretation through the existing artifact owners. The Gallery retains full-precision quantities; the welfare display converts hundred JPY to million JPY. The brief and structural presentation use the same two exhibits and numerical prose.

```sh
python skills/econ-data/examples/charging/materials.py --root /path/to/project \
  --run /path/to/project/private/charging-run --output /path/to/project/private/charging-materials --language ja
```

Use a project root containing the selected runtime and result paths. The flat command uses `charging-materials.py`; `--language en` selects English. Each execution creates a new material directory with `brief` and `structural` bundles.

3. **Output: inspected pages; consumer: reader.** Render each bundle through `python harness/research.py meeting render --root /path/to/project --bundle /path/to/project/private/charging-materials/structural --output /path/to/project/private/charging-slides-html --format html`. Select `pdf` with a new output directory for PDF. In a flat export, use `research.py`. Read the actual pages under PROSE and retain their input hashes and inspection evidence in the private working record.
