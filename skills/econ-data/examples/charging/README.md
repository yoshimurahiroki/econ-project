# Charging-service demand and merger welfare

Use this fictional example for demand IV, market-level inference, joint pricing, procurement efficiencies and a monetary merger decision. The [specification](specification.json) defines the same drivers, services and market population throughout the [executable example](run.py).

1. **Adopted question.** Read the specification and its comparison of the price question with the total-surplus decision. The formulation operation binds that choice to the specification hash. Drivers choose a charging service or the outside option; firms choose prices; the authority compares the two feasible ownership arrangements.
2. **Shared tables and analysis input.** Generate 100 markets and 300 service products from the specified primitives. PyBLP solves the original Bertrand prices. The existing assembly owner builds keyed product and market tables, attaches market population with a many-to-one join, and retains the 300 product-market IDs in the analysis sample. Its dictionary and data record carry units, source versions and construction dependencies.
3. **Fitted demand and two counterfactual results.** Execute the existing market runner on the shared analysis table. Procurement-price variation identifies the price coefficient; quality and an intercept complete the demand equation. Official two-step GMM retains market-clustered inference. Reuse the saved native fit for ownership-only and integrated-merger scenarios. The latter reduces the merged services' marginal costs by 20%.
4. **Monetary comparison and selected action.** Read `result-index.json` and its three referenced results. Its `decision_quantities` saves consumer, producer and total surplus on the fixed population, with the real integration cost deducted once from integrated-merger producer and total surplus. Use these named levels and changes for the specified total-surplus decision. Keep original-equation checks, assumptions and diagnostic records in the internal working record. Pass saved point estimates and the demand coefficients' 95% pointwise intervals with their units to the requested artifact.

Run from the repository or extracted plugin runtime using the selected Python environment:

```sh
python skills/econ-data/examples/charging/run.py --output /path/to/private/charging-run
```

The output names a new generation. The flat export command is `python charging-example.py --output /path/to/private/charging-run`. Use PyBLP 1.3.0 and its existing [market dependencies](../../scripts/requirements-markets.txt). [The market contract](../../../econ-design/references/market-models.md#differentiated-demand-and-supply) connects the equations, data, official calls and saved results. The official [Simulation](https://pyblp.readthedocs.io/en/stable/_api/pyblp.Simulation.html) generates the fictional economy; [Problem.solve](https://pyblp.readthedocs.io/en/stable/_api/pyblp.Problem.solve.html) estimates its demand.

The result index retains full-precision source bindings, original logit-share and pricing residuals, monetary accounting, native inference and the applied objective. A changed primitive, sample, model or intervention creates a new calculation generation. Changes to prose or layout consume the selected saved generation through the existing artifact owners.

## Materials

[materials.py](materials.py) registers the saved exhibits in the Gallery and creates the `brief` and `structural` bundles. Each bundle holds the exhibits, their labels and units, and takes the specification ID as its title. Headings, prose and slide text enter at task time through [econ-writing](../../../econ-writing/SKILL.md) and the [borrowing procedure](../../../../runtime/WRITING.md); slide and document headings are noun phrases.

```sh
python skills/econ-data/examples/charging/materials.py --root /path/to/project \
  --run /path/to/project/private/charging-run --output /path/to/project/private/charging-materials --language ja
python harness/research.py meeting render --root /path/to/project \
  --bundle /path/to/project/private/charging-materials/structural \
  --output /path/to/project/private/charging-structural-pdf --format pdf
```
