# Transport, housing and location choice

Use this fictional example for SQL measurement, residential and workplace choice, spatial equilibrium and a policy decision. The [specification](specification.json) fixes the population, economic equations, source quantities and annual costs consumed by the [executable example](run.py).

1. **Output: adopted policy question; consumer: data construction.** Read the specification's comparison of the outer district's rent change with the net policy gain across all districts. Workers choose residences and workplaces; firms hire labor and rent commercial space; floor owners receive rents and finance the policy. The formulation operation binds the adopted question to the specification hash.
2. **Output: shared district and travel tables; consumer: baseline inversion.** Generate the declared subdistrict counts, workplace counts, leases, land and travel records. DuckDB sums counts, divides total lease revenue by leased area, and converts land and travel units. The existing assembly owner joins district tables one to one and records keys, definitions, source hashes and SQL. The complete directed travel table supplies the residence-workplace matrix in the declared district order.
3. **Output: baseline and policy equilibria; consumer: economic interpretation.** Execute `MC-qse-commuting` through the existing macro runner. The calibrated choice model recovers wages, amenities, productivity and floor supply from the baseline observations. Reuse the saved baseline for the transport policy and the combined transport-and-floor policy. SciPy solves location choices, labor markets, firm conditions and floor clearing at the adopted tolerance.
4. **Output: annual net policy comparison; consumer: prose, Gallery and project decisions.** Read `result-index.json` and its bound results. The index converts the runner's monetary quantities into thousand JPY per year and saves worker income equivalents, gross owner income changes, policy costs and net owner income changes. It selects the feasible policy with the largest net income-equivalent gain. Read named decision quantities when composing the policy comparison. Retain the calibration, numerical diagnostics and complete source records in the internal working record.

Run from the repository or extracted plugin runtime:

```sh
python skills/econ-data/examples/housing/run.py --output /path/to/private/housing-run
```

The flat-export command is `python housing-example.py --output /path/to/private/housing-run`. Each invocation creates a new generation. Restore pandas from the existing [research requirements](../../scripts/requirements-research.txt), NumPy and SciPy from the [macro requirements](../../scripts/requirements-macro.txt), and the selected SQL dependencies through `python -m pip install pyarrow==26.0.1 duckdb==2.0.0` in that environment. The [shared-table contract](../../references/research-data.md#shared-tables-across-sql-python-r-and-julia) and [spatial model contract](../../../econ-design/references/macro-models/spatial.md#closed-city-commuting-and-floor-space-equilibrium) define the input and output interfaces.

The annual budget is 1.5 billion JPY. A lump-sum charge on floor owners funds the transport service and the additional floor-space service. Owner consumption plus policy resource use equals gross rental receipts. The decision adds the worker income equivalent to the owner income change after that charge. All scenarios retain the same 12,000 workers, baseline monetary normalization and one-year horizon.

Official interfaces: [DuckDB Python SQL](https://duckdb.org/docs/stable/clients/python/reference) and [SciPy least squares](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.optimize.least_squares.html). The existing macro runner owns the equilibrium equations and their saved residuals. Changes to source quantities, calibration or policy inputs create a new calculation generation; wording and layout consume its saved quantities.

The complete [English profile](../../../../profiles/default-micro/housing-study-en.md) and [Japanese profile](../../../../profiles/default-micro/housing-study-ja.md) carry the same measurement, equilibrium and annual policy comparison from Abstract through Conclusion.

Build the existing brief and structural material bundles from that saved generation with the [material producer](materials.py). Set `--root` to the common project directory containing the runtime and saved results. Select `--language ja` or `--language en`; each invocation creates a new output directory.

```sh
python skills/econ-data/examples/housing/materials.py --root /path/to/project --run /path/to/project/housing-run --output /path/to/project/housing-materials-ja --language ja
```

The flat command uses `python housing-materials.py` with the same arguments. The producer binds the saved result, registers annual costs, worker and owner gains and mean commuting times, and creates Gallery exhibits and both material bundles. Use the existing [meeting renderer](../../../../harness/meetings.md#edit-prose-and-structure) to generate each bundle's HTML and PDF. Wording and layout consume the saved calculation; a revised scientific input returns to the example runner.
