# Executing an adopted research pipeline

`research.py` executes an adopted local DAG and records each attempt in the existing `.agents/harness/state.py` store. The host selects the research question, scientific methods, acquisition and analysis commands, definitions and inputs through the five specialists. A stage runs after its declared consumed outputs complete; a failed stage blocks its descendants and independent branches continue.

A saved stage is reusable when its adopted specification, declared source and helper bytes, exact environment, executable and consumed result versions match a completed state record. The renderer resolves each numerical token to a named result key, checks its saved unit and applies its declared format. The same state record links the displayed quantity to the actual producing execution.

```sh
python .agents/harness/research.py --root /path/to/project --store .agents/state/team.json --parent TASK_ID research.json
```

The root is the project owning the source files. The manifest and the store are root-relative. The store defaults to `.agents/state/team.json` and is initialized if absent. `--parent` attaches attempts to an existing state task, inheriting its full governing context, scoped holds and authority; its write scope must include `.agents/research/PIPELINE`. An existing parent must already be in the selected store. Release overlapping active writer scopes through the existing state transition before starting child attempts. A single runner lock coordinates research runners in the root, and the existing state helper coordinates individual store updates. Commands execute with the host process's operating-system access and must stay within their authorized scope and declared generation outputs.

A manifest is a JSON object with a `pipeline` ID and `stages` array. Stage IDs and output names use letters, digits, underscores or hyphens. Each stage has `inputs` (root-relative files), `depends` (producer stage to list of output names), `outputs` (name to path relative to its generation), and exactly one of `argv`, `render` or `select`. Input and output paths stay within the project through regular files. Inputs include the actual data, adopted specifications, source scripts, called helpers, seeds, package/environment locks and other files that affect the calculation. Stage changes and tracked input bytes invalidate the stage; selected upstream output identities and definitions invalidate its consumers. The declared environment is exact: `env` supplies literal name/value pairs and `inherit_env` names existing variables to copy and track. Supply executable search `PATH` when the command needs it. The selected invocation path, resolved executable bytes, actual argv, selected environment and runner bytes are recorded. Declare every consumed helper, external-source snapshot and relevant environment specification. Keep credentials in the host's approved storage outside tracked environment values. The specialist owner establishes scientific validity through the adopted model and producing calculation.

For an argv stage, arguments are passed directly to `subprocess.run`, without a shell. `{root}` expands to the project root, `{out:NAME}` to the named file in the new generation and `{dep:STAGE:NAME}` to a declared completed dependency's file. The command runs in its fresh generation directory, with declared environment variables only. Outputs must be regular files present on successful exit; a producer should validate its own schemas, convergence and numerical requirements before exiting successfully. Subprocess stdout, stderr and exit status are recorded in the attempt. Files of an unsuccessful attempt are not selected for descendants.

```json
{
  "pipeline": "hours",
  "stages": [
    {
      "id": "estimate",
      "inputs": ["data/people.csv", "spec/sample.json", "code/fit.py", "environment.lock"],
      "depends": {},
      "outputs": {"result": "result.json"},
      "argv": ["/usr/bin/python3", "{root}/code/fit.py", "{root}/data/people.csv", "{root}/spec/sample.json", "{out:result}"]
    },
    {
      "id": "paper",
      "inputs": ["paper/template.txt"],
      "depends": {"estimate": ["result"]},
      "outputs": {"text": "paper.txt"},
      "render": {
        "template": "paper/template.txt", "output": "text",
        "statistics": {
          "training": {"stage": "estimate", "output": "result", "key": ["statistics", "training"], "unit": "hours_per_week", "format": ".2f"}
        }
      }
    }
  ]
}
```

A rendered template contains two opening braces, `stat:training`, and two closing braces. The selected JSON key must resolve to an object such as `{"value": 1.25, "unit": "hours_per_week"}`; its finite numeric value, exact unit and format produce the inserted bytes. Key paths are arrays of JSON object keys. Supported formats are `f`, `g`, `e` and their precision forms such as `.2f`. The bindings must exactly match the template placeholders. The template is a tracked input and the source result a declared dependency. Additional tables and figures can be argv stages that consume the same result; their scientific and content checks belong in their generating commands.

Every successful stage publishes an immutable generation by completing its state task after all declared files exist. The JSON response returns each selected generation's root-relative file paths and `executed`, `reused`, `recovered`, `skipped`, `failed` or `blocked` status. Exit codes are 0 for a completed DAG, 1 when a stage failed or was blocked, and 2 for invalid input or a runner/state error. New attempts use separate generation paths. Previous complete files remain available after a failed replacement, but the failed branch is not passed to current descendants. State completion, input hashes, consumed versions, definitions and output bytes are checked before reuse. Modifying a saved result or rendered artifact invalidates its reuse. Original context and input versions remain in state task records; retain the project specification and source files under their own version control as well.

## Acquire the selected literature and data

Use the [source connector](../skills/econ-literature/scripts/research_sources.py) to inspect public bibliographic metadata, indicator definitions and observed series. Each result retains its query, exact response bytes, retrieval identity and SHA-256. An explicitly selected original can be fetched and parsed through the existing equity document reader. Read the original argument establishing a paper's result before adopting that result in the research design.

```sh
python .agents/skills/econ-literature/scripts/research_sources.py literature --query "production adjustment mechanism" --output outputs/literature
python .agents/skills/econ-literature/scripts/research_sources.py indicators --query "GDP per capita current US" --output outputs/indicators
python .agents/skills/econ-literature/scripts/research_sources.py series --indicator NY.GDP.PCAP.CD --countries JPN USA --start 2020 --end 2024 --output outputs/gdp
```

Select a dataset by its observation unit, variables, measurement, period, identifying variation, keys and actual access path. The World Bank connector retains source definitions and distinguishes observed numbers, null values and absent requested keys. The host uses its other connected statistical and document tools under econ-data's acquisition contract. Freeze an adopted source snapshot for reproduction; an authorized refresh produces a new tracked input version.

## Estimate a linear specification

The [estimator](../skills/econ-data/scripts/research.py) executes OLS with `statsmodels.OLS` and 2SLS with `linearmodels.iv.IV2SLS`. Use a Python 3.12 scientific environment with the [pinned research requirements](../skills/econ-data/scripts/requirements-research.txt); the [existing equity requirements](../skills/econ-data/scripts/requirements-equity.txt) supply PyBLP and document extraction for the structural and source workflows. Select an existing matching environment or create a fresh task-owned environment:

```sh
python3.12 -m venv outputs/research-env
outputs/research-env/bin/python -m pip install -r .agents/skills/econ-data/scripts/requirements-research.txt -r .agents/skills/econ-data/scripts/requirements-equity.txt
```

Use that interpreter for numerical commands and the case's `--python` argument; the runner can use the host's standard-library interpreter. Each CSV row has a unique recorded ID. The JSON specification names `data`, `id`, `outcome`, `population`, `period`, `unit`, `sources`, `method`, `exog`, and, for IV, `endog` and `instruments`. `sample_columns` defines additional complete-case columns for a stipulated common sample; `filters` supplies explicit column/operator/value restrictions. `question` and `identification` retain the adopted economic target and conditions. Additional sample fields retain nonempty categorical labels and finite numeric observations; model columns follow the adopted numeric design. The interface rejects unsupported fields and options before producing an estimate and publishes a complete JSON result by atomic replacement.

```json
{
  "data": "people.csv", "id": "person_id", "outcome": "productivity_points",
  "population": "synthetic training participants", "period": "simulated period 1",
  "unit": "productivity points per training hour", "sources": [{"path": "source-record.json"}],
  "method": "iv2sls", "exog": ["baseline_productivity"], "endog": ["training_hours"],
  "instruments": ["randomized_training_offer"], "covariance": {"type": "HC1"}
}
```

`covariance: {"type": "HC1"}` selects heteroskedastic robust finite-sample adjustment. `{"type": "CR1", "cluster": "site_id"}` selects the official one-way cluster adjustment using the fitted rows' site labels. Outputs preserve full named covariance, coefficients, standard errors, actual fitted and excluded IDs, cluster assignments, source/specification hashes and engine versions. They retain each engine's actual inferential reference: OLS CR1 uses Student t with G−1 degrees of freedom; debiased IV uses Student t with n−k. The IV result keeps the package's first-stage diagnostic distribution and a separately computed conditional Wald F with its actual covariance and degrees of freedom. Use these named quantities and references in downstream interpretation and rendering.

```sh
outputs/research-env/bin/python .agents/skills/econ-data/scripts/research.py estimate analysis.json -o result.json
```

## Run the independent Python and R case

The [case producer](../skills/econ-data/scripts/research_case.py) creates an original seeded data-generating process, raw observations, a base-R preprocessing script and the adopted OLS/IV specifications. Its nine stages connect R processing and summary, Python estimates, a named-statistic summary, table, SVG, QMD and standalone HTML. The saved source record defines the generated outcome, treatment, instrument, disturbances and true coefficient. These observations and results describe the specified simulation.

```sh
outputs/research-env/bin/python .agents/skills/econ-data/scripts/research_case.py prepare --root /path/to/project --python /path/to/analysis/python --rscript /path/to/Rscript --case-id independent019
python /path/to/project/.agents/state/independent019/code/runner.py --root /path/to/project .agents/state/independent019/manifest.json
```

Use a new `--case-id` for each prepared case. Existing directories are preserved. `--parent TASK_ID` on the runner inherits the task's governing context, authority, holds and scope. Optional repeated `--source-record-dir` arguments copy explicitly selected source records after hash verification. The producer works from canonical, deployed and flat layouts. Each command stage declares the actual Python or R runtime, selected package versions and relevant environment inputs. An identical second invocation reuses all nine stages. A figure-label revision redraws the figure and assembled HTML while retaining matching fits.

## Run an independently specified structural example

The [structural producer](../skills/econ-data/scripts/research_structural_case.py) generates six synthetic product markets from its stated utility and cost equations, estimates demand through the existing `equity.fit` PyBLP interface and re-solves an ownership intervention. It saves its original generated observations, model and source specification, package/engine hashes, estimated parameters, changed prices, shares, profits, consumer values and original equilibrium residuals. The synthetic finite-state example uses the existing `equity.dynamic` NFXP and MPEC owners and re-solves the changed payoff policy.

```sh
outputs/research-env/bin/python .agents/skills/econ-data/scripts/research_structural_case.py --output outputs/structural-new
```

Supply a fresh output directory under an existing parent. The producer uses the existing complete-generation publisher and emits named statistics with units for subsequent tables, figures and prose. Restore the [equity requirements](../skills/econ-data/scripts/requirements-equity.txt) alongside the [research requirements](../skills/econ-data/scripts/requirements-research.txt) in the selected Python 3.12 environment. The current generating run saves its inputs, results and replay bindings in the requested output directory.

## Choose and execute the next research operation

Sol formulates candidate questions from the requested economic object and the closest inspected answers. For each candidate, state the mechanism, estimand, identifying variation, measurement and population; identify the prediction or knowledge added by its comparison with the closest answer. Retrieve a consequential contrary finding and the actual data documentation when they determine that comparison. Keep these judgments and the candidate ordering in the adopted specification under the existing governing task.

The [design assessment](../skills/econ-design/scripts/research_design.py) checks that specification against retained source bytes and actual CSV records. Its `sources` map binds IDs to `{path,sha256}`; source references use `{source_id,start,end,quote}` with character offsets into the exact UTF-8 text. Its `datasets` map declares the CSV path/hash, observation `unit`, `population`, documented `period:{start,end}`, documentation spans, `grain` keys and `definition_versions`. A candidate declares all five economic dimensions, source evidence, `closest_answers` with the same dimensions, and the owner's contribution judgment: `classification` is `replication` or `changed_contribution`, with `owner`, `rationale`, `changed_dimensions` and supporting evidence. The owner cites each closest answer in that judgment.

Each candidate's `requirements` declares the fields, unit, population, period and actual identifying variation its design uses. Optional missingness fractions, observed year coverage, sample filters, observation-status fields and linkage requirements check the corresponding rows and keys. Numeric variation counts numeric values. A candidate's `next_operation:{argv,cwd}` records the authorized executable action. `selection:{rule:"owner_order",order:[...]}` lists every candidate once; the result selects the first feasible one and retains every candidate's findings, definition versions, source hashes and selecting evidence.

```sh
python .agents/skills/econ-design/scripts/research_design.py assess design.json --root /path/to/project --output outputs/design.json
```

Use this result as a consumed output of the next source, estimation or experiment stage. Sol reads its economic comparison and executes the selected action through the current host. After each returned source or calculation, Sol tests the determining prediction, adopts the next action and continues through design, data, writing and review to the original requested artifacts. A changed premise updates its dependent operations in the same task; matching completed branches remain reusable. Native search and worker tools provide the model's reasoning and delegation. The local executables provide reproducible source, calculation, comparison and persistence operations under that adopted reasoning.

Bibliographic discovery supports exact DOI lookup with `work --doi DOI`, one-hop backward records with `references --doi DOI`, and union search with repeated `literature-multi --query QUERY`. All take `--output DIR`. Reference rows retain the original work, rank, reference key, DOI and complete original reference fields, including unresolved text. Union rows retain each query, its status, rank and exact response origin; normalized DOI identifies duplicates, and an exact title/year identity handles rows without DOI. A failed query publishes its attributable partial record and returns a failing status. Follow selected references and forward citations through the current source tools until their original passages resolve the research comparison.

## Compare specifications on a frozen protocol

Define the scientific target, population, units, identifying restrictions, sample and inference before opening trial results. A predictive comparison fixes training, validation and holdout roles; a causal or structural comparison fixes the adopted parameter and its relevant diagnostic or model criterion. Put that comparison in a tracked protocol. Every compared result carries exactly the protocol's `identity` fields (`estimand`, `evaluator`, `sample`, `partition`); its `protocol` object matches the adopted `evaluation_protocol`. Bind data partitions, code, seeds and evaluator versions to their actual hashes. A target change creates its own adopted comparison.

The manifest's optional `grids` array expands declared alternatives. Each grid specifies `prefix`, `parameters` (arrays of distinct strings) and a normal stage `template`. Optional `order` names every parameter once; positive `budget` bounds the expanded alternatives and nonnegative integer `seed` fixes the declared randomization. Expansion follows the declared Cartesian order and budget. `{param:NAME}` and `{grid:seed}` insert the selected literal values. The expanded stages retain the same input, output, dependency and authority rules as ordinary stages.

A selection stage declares `select:{protocol:"protocol.json",candidates:{"candidate-id":{stage:"trial-id",output:"result"}}}` and one output. The protocol is a declared input; candidates are declared dependencies. Its `metrics` array names JSON `key` paths, `direction:"min"|"max"` and optional feasibility `min`/`max`. Metrics rank feasible candidates lexicographically; `tie_break` names every candidate in the adopted order. `on_failure:"block"|"exclude"` determines how an actual failed trial affects selection. The protocol also declares its `seed`, `budget`, `holdout` paths and exact `evaluation_protocol`. Trial ancestry and literal arguments are checked against the declared holdout paths. The selector saves all observed metrics and failures with the selected ID.

An action stage can declare `when:{stage:"choose",output:"selection",equals:"candidate-id"}` and consume that selection. The runner executes the selected branch and reports other branches as `skipped`. Put winner-only holdout evaluation and artifact generation on that branch. The native owner can use the returned comparison to adopt a subsequent experiment in the existing manifest and governing context.

For fixed-split prediction, `research.py evaluate SPEC -o RESULT` calls scikit-learn OLS or Ridge. The specification names distinct `train_data` and `evaluation_data`, unique `id`, `outcome`, `features`, `candidate:{method:"ols"}` or `{method:"ridge",alpha:1}`, partition, protocol and scientific identity. Preprocessing fits on the training records; the result retains training/evaluation IDs, predictions, MSE, model parameters, source hashes and package versions. Use the same fixed input and protocol for every trial, and retain the selected result and winner-only holdout output in the existing result record.

An argv stage can declare `checks:[{type:"json",output:"result",fields:[{key:["metrics","loss"],type:"number",min:0}]}]`. Declared types and exact values/ranges check the producing file before completion. Preserve the actual command exit, current log and checked output together.

## Recover interrupted attempts

The runner saves the command's actual terminal return and output hashes before publication. On restart, a complete matching receipt and matching inputs allow that same attempt to complete without repeating its command. A prepared generation whose source, output or context changed fails that reuse check. An active command with no observed terminal return remains blocked for reconciliation through its actual process and target; retain its logs and determine whether its child still runs before any retry.

For an observed failed attempt, repair the determining cause and retain the actual reconciliation evidence. Select one explicit retry with:

```sh
python .agents/harness/research.py --root /path/to/project --parent TASK_ID --retry-failed STAGE_ID --retry-reason "corrected producing input" --retry-evidence retry-evidence.json research.json
```

The evidence file is hashed and retained with the new attempt. Existing failed logs and immutable successful generations survive. Resume at the affected stage and rebuild its descendants while reusing matching independent results. Existing process-interruption coverage checks both a killed runner after its child's terminal return and a killed runner with a killed unfinished child, including lock release, zero remaining active writers and actual generation counts.

## Retain and reuse an observed procedure

The [experience helper](experience.py) stores reusable procedures as completed output objects in the same state store. A captured procedure consumes a current completed result and its successful actual execution record. Its seven typed conditions bind `model`, `engine`, `schema`, `method`, `failure_mechanism`, `package_versions` and `specification_sha256` to named producer-output keys. The specification hash must identify an actual tracked producer input or consumed output. Capturing retains its original task, inputs, authority, execution and source versions.

```sh
python .agents/harness/experience.py --root /path/to/project capture --task-id PROCEDURE --parent TASK --spec capture.json
python .agents/harness/experience.py --root /path/to/project find --conditions conditions.json
python .agents/harness/experience.py --root /path/to/project prepare --target TASK --procedure PROCEDURE --task-id PROPOSAL --conditions conditions.json
```

Capture configuration names `producer_id`, `output_id`, `execution_output_id` (default `research:execution`) and `conditions:{NAME:{output_id:"RESULT",path:["identity","NAME"]}}`. `permitted_switches` binds permitted revisions to the producing evidence. The optional stage field `learn:{spec:"learn.json"}` performs this capture after a successful stage. Its stage-specific metadata uses `output:"result"` and `conditions:{NAME:{output:"result",path:["identity","NAME"]}}`; these logical names resolve to the completed producer's actual immutable file IDs. Learning metadata has its own capture-task input and identity. Changing its wording or path recaptures the procedure while reusing the unchanged numerical producer. A requested capture failure blocks its dependent postcondition while preserving the completed calculation.

`find` returns only current matching procedures. `prepare` binds the selected procedure and its producing evidence to the target task's current context, scope and holds as an adoption proposal. The owner then applies the current specification and executes the proposed operation. Native-operation capture uses actual host command arguments and returns, semantic target checks, source-preservation evidence and the resulting artifact/readback. Explicit `--allow-rebind` discovery and `prepare --bindings TARGET_INPUT.json` can transfer an owner-authorized stage/release or specification revision declared by the original permitted-switch evidence; the current target tracks those bindings and specification. The resulting proposal retains `result_reuse:false`. The observed packaging example learns stage/working-directory equality and preservation checks from actual exit-zero calls and their different targets.

For an observed project command or environment repair, select `operational_procedure_reuse` and capture `execution_kind:"task_check"`. Its `producer_id`, `output_id` and `check_id` identify the completed result and its current verified [run-check](state.md#analyze-and-converge). The six operational condition references are `project`, `runtime`, `schema`, `failure_mechanism`, `package_versions` and `specification_sha256`; each resolves through `{output_id, path}` to that checked output. `steps` references the owner's proposed instruction list in the same output. The specification hash identifies a tracked producing input or consumed output.

Optional `failure_run_id` selects an earlier actual run of the same adopted check command. Its `failure_observation` references `{run_id, reason, observed_output}` in the checked output; the observed text must occur in that earlier run's retained stdout or stderr. A zero exit retains its actual status when the observation identifies a wrong target or another unmet output condition. Capture preserves both original runs and their versions. `find` rechecks the successful producer and receipt. `prepare` requires the current target to track or consume the exact operational identity and specification, then binds the proposed procedure to its current authority and holds. Observations, proposed steps and adopted governing rules retain their existing separate authority.

### Select a version-bound operational fact

For recurring test-launch failures, the same [experience helper](experience.py) can assess explicitly supplied private Codex logs. Its deterministic adapter recognizes the bare `pytest -q` or `unittest -q` command missing with exit 127 and the corresponding successful `python -m` command, with actual pass counts. Exact pre/post environment, package and input checksum observations bind the pair. Keep the source logs, conditions and code inputs in the target task's current consumed/read inputs. Source paths and their content hashes identify the received evidence; `provided-host-log` retains `host_authenticated:false`.

```sh
python .agents/harness/experience.py --root . assess-host-logs --target TASK \
  --conditions .agents/state/TASK/identity.json --family unittest \
  --log .agents/state/TASK/session-a.jsonl --log .agents/state/TASK/session-b.jsonl \
  --log .agents/state/TASK/session-c.jsonl --code code/test_module.py
```

Conditions use the operational identity above, including the actual Python/package versions and specification hash. Each received log must contain its actual session header, project working directory, turn/policy context and matched tool calls with terminal returns. Running processes and unsupported return encodings require reconciliation. Three distinct source sessions establish the initial eligibility threshold; four or more known opportunities require at least forty percent contribution. A contradictory successful bare command invalidates the fact. Input, specification, environment and authority versions govern subsequent application. `operational-candidates` displays candidates from the existing saved procedure records, including their typed failed-execution or unmet-semantic-output cause. An exit-zero call with a wrong target retains exit zero.

`assess-host-logs --record` explicitly registers its sanitized assessment through the same task store. Automatic feedback uses the existing [task controls](state.md#optional-execution-controls-and-observed-usage). Its private plan contains `conditions`, `logs`, `code`, `family` and optional `current_log` paths. Configure that plan through `optimization ... --experience-plan`; the saved plan hash and current target inputs are checked before a matching pending command. The existing PreToolUse caller appends the selected fact after the mandatory reminder. A received current-session developer message containing the exact version-marked fact supplies repeat-delivery evidence. Constructed callback output retains prepared status until that evidence exists. Task controls, selected scientific specification and current permissions govern the subsequent operation.

## Bind claims equations and saved results

The [evidence binder](research_evidence.py) checks an explicitly selected manuscript against source, result and producer identities:

```sh
python .agents/harness/research_evidence.py bind evidence.json --root /path/to/project --output outputs/bound.json
```

The contract names `manuscript:{path,sha256}`, `adopted` scalar identities and optional `sources` with exact file hashes and metadata. `claims` bind an exact target span to source IDs/spans and a native `judgment:{reviewer,decision:"supported",rationale}`. `numbers` bind target and displayed-unit spans to a result path/hash, semantic key, unit, format and all adopted `identity_keys`. `models` bind an equation span, exact code span/hash, original residual key and adopted tolerance to the same model/specification identities and native judgment. A changed source, code, value, unit, identity or excessive residual fails the binding and preserves the prior complete output.

Optional `mappings` bind individual symbols and parameters. Each names `kind:"symbol"|"parameter"`, `status:"derived"|"fixed"|"calibrated"|"estimated"`, manuscript `target`, exact `code` span, result identities and native judgment. Its `origin` names either a source ID/span or a specification path/hash/key/value/unit. Fixed and calibrated parameters bind the actual adopted specification; estimated parameters bind a named `{value,unit}` result quantity. `coverage` selects manuscript spans for numeric-token accounting; displayed statistics and explicit source/assumption/citation claims account for those tokens. The native owner establishes the claim's meaning and economic inference using the bound passages and calculations.

## Estimate orthogonal scores

The estimation interface supports `method:"dml_plr"` through DoubleMLPLR and `method:"dml_did"` through the pinned DoubleML two-period panel interface. Define treatment, covariates, outcome or pre/post outcomes, actual individual IDs, sample, population, period, units, sources and the adopted identification. The partial linear target uses the declared conditional exogeneity and partially linear model. The DID target uses its experimental or observational score and adopted parallel-trends comparison. Bind each adopted target to its own model, identification, sample and result identity.

`dml` declares integer `folds`, `seed` and `score`; PLR selects `"partialling out"`. DID selects `"experimental"` or `"observational"` and boolean `normalize`; observational DID also declares `clipping_threshold`. `learners` declares linear or positive-alpha Ridge outcome models and PLR treatment models; observational DID declares a logistic propensity model with `C` and `max_iter`. The saved result retains actual folds, fitted/excluded IDs, score, clipping, parameters, confidence intervals and package/specification versions. Scientific adoption follows the corresponding design and engine-selection rules.

## Solve the adopted finite horizon model

The [macro interface](../skills/econ-data/scripts/research_macro.py) solves a deterministic finite-period representative-household growth model. The household chooses positive capital and consumption to maximize the sum of discounted log consumption. Output equals productivity times capital to `alpha`; resources include depreciated capital and output after its tax. Tax receipts are government absorption. The specification fixes `alpha`, `beta`, `delta`, initial and terminal capital, baseline/scenario `productivity` and `output_tax` arrays, population, period, units, sources and `tolerance`.

```sh
outputs/research-env/bin/python .agents/skills/econ-data/scripts/research_macro.py solve macro.json -o macro-result.json
```

The implementation supplies analytic objective gradients and resource Jacobians to SciPy SLSQP, checks them against finite differences and evaluates the original Euler and resource residuals at both returned paths. It publishes the actual capital, output, consumption, welfare and scenario difference with engine/specification identities after the declared residual tolerance passes. For another adopted heterogeneous-agent or aggregate-equilibrium model, select its matching package, information/timing, market closure and original residuals through the existing structural design and numerical owners.

## Capture the selected Python and R environment

An argv stage can declare `runtime` with `language:"python"|"r"`, `probe_argv`, `version`, `packages` and `files`. The literal `probe_argv` is the leading interpreter/options prefix of the stage's actual argv. `version` enforces the selected runtime version when supplied. `packages` maps installed package names to exact required versions or `null` to record their actual versions. Every `files` entry is a declared stage input, such as a pinned requirements file or the project's existing Pixi/rv lock.

Before reuse and after execution, the runner records the actual runtime version, interpreter/wrapper identities, selected installed dependency closure and library locations, tracked environment-file hashes and selected environment. Python package discovery uses the chosen interpreter's `packaging` interface; the [research requirements](../skills/econ-data/scripts/requirements-research.txt) declare its pinned version for the worked case. R uses its base package-discovery interfaces. Install the dependencies selected for the actual project in its adopted environment; the mini template retains its lightweight infrastructure definition. The full project retains its existing fixed dependency and lock definitions.

```json
{"runtime":{"language":"python","probe_argv":["/path/to/python"],"version":"3.12.16","packages":{"numpy":"2.3.5"},"files":["requirements.txt"]}}
```

A missing required package or mismatched version stops the affected operation before its calculation. A changed observed package closure invalidates the consuming stage even when the interpreter binary and input data are unchanged. The saved execution retains that identity beside the actual result.

For a consequential selected interface, add `apis` to a Python or R runtime, including an R companion:

```json
{"apis":[{"package":"numpy","symbol":"numpy.linalg.solve","positional":2,"keywords":[]}]}
```

Each API's package has an explicit version in that runtime's `packages`. Python resolves the distribution-owned callable and binds the proposed positional count and keyword names to its actual signature; it records that signature, installed documentation hash and available source identity. R resolves the package export, checks its formals and records the version-matched installed help identity. An unavailable symbol, signature or adopted call stops the affected stage. The runtime identity includes these observations, so a changed API or documentation version invalidates its consumers. Explicitly acquired official reference files use the existing tracked `runtime.files` inputs.

## Select a named execution profile

A manifest may define `profiles:{"development":{stages:["prepare","fit"],overrides:{"fit":{argv:[...]}}},"formal":{stages:[...]}}`. Stage selections name the expanded stage IDs and include every required predecessor. Overrides explicitly replace selected stage fields while retaining their IDs. Choose the profile with `--profile NAME`; an unprofiled invocation preserves the original manifest behavior. The profile definition and selected name enter the execution signature, so development and formal results have distinct reuse identities. Keep any changed scientific sample or numerical specification explicit in that profile and its generated result.

## Detect changed results behind manual prose

For a text stage whose interpretation has been reviewed against a saved summary, declare `reviewed_results:{"summary":{"result":"SHA256"}}`. Each name refers to a declared consumed output. The runner compares its actual current bytes with that reviewed hash before reusing or producing the dependent artifact. A changed result blocks the affected text while preserving its preceding complete generation. The owner inspects the changed comparison, revises the passage where its conclusion changes and updates the reviewed binding. Select the stable result summary carrying the interpretation's quantities and definitions; display-only work can reuse its matching binding. This uses the existing task, output and dependency records.

## Package and reproduce a completed research result

The [reproduction producer](reproduction.py) assembles an explicitly selected current execution into a fresh package. The build consumes the existing state store and its exact completed tasks; it preserves the source project and performs no scientific rerun. Its config names `manifest`, optional `profile`, `tasks` mapping stage IDs to completed task IDs, `outputs` mapping selected output names to comparisons, `allow_inputs`, `allow_env` and `interpreters`. `allow_inputs` lists the exact data, code and environment paths approved for inclusion; `allow_env` names the disclosed selected environment values. Missing required inputs stop the build with their acquisition or inclusion requirement. Existing target directories are preserved.

A comparison is `{method:"sha256"}` or `{method:"numeric-json",path:["estimate"],unit_path:["unit"],rtol:1e-8,atol:1e-10}`. Numeric comparisons verify the actual value and its exact unit. Optional `helpers` maps `research.py`, `.agents/harness/state.py` and `.agents/harness/local_checks.py` to the project's existing matching helper copies; the default paths are under `harness/`. The selected manifest, observed runtime, producing argv/environment, source hashes, original context hashes and saved comparison outputs form the release provenance. Private task-store bodies and unselected source files stay in their existing storage.

```sh
python .agents/harness/reproduction.py build --root /path/to/project --config reproduction.json /path/to/reproduction-new
python /path/to/reproduction-new/project/harness/reproduction.py verify /path/to/reproduction-new
python /path/to/reproduction-new/project/harness/reproduction.py reproduce /path/to/reproduction-new
```

The builder checks current inputs, consumed versions, executable and runtime identities before copying and at the publication boundary. Its atomic new directory includes an exact finite file inventory and the existing runner/helper closure. `verify` compares that inventory with the actual package. `reproduce` uses the copied runner in a fresh temporary project and compares the declared outputs with their saved originals. The package remains unchanged after replay. Explicit interpreter mappings select recipient paths while retaining the recorded runtime and package requirements. The current package path accepts completed stage closures; learning-capture and failed-candidate task closures identify their unsupported helper/receipt requirement before publication.

The independent Python/R case uses this same runner and reproduction builder for its generated data, estimates, summary, table, SVG, QMD and HTML outputs. Python/R notebooks and Quarto/LaTeX render commands can occupy the same argv stages with their real scripts, package/lock inputs and output definitions.

## Select the specialized model

Use the existing `econ-design` and `econ-data` operations with the condition matching the scientific contract. Each command stage declares the source, specification, model helpers, selected requirement files and consumed outputs.

| Condition | Specification and execution reference |
| --- | --- |
| `method_extended_causal` | [Causal models](../skills/econ-design/references/causal-models.md): official Python/R estimators, sample IDs, named inference and reported-parameter covariance. |
| `method_extended_markets` | [Market models](../skills/econ-design/references/market-models.md): joint PyBLP estimation, market interventions, auction-record estimation, search, bargaining, platforms and matching. |
| `method_extended_dynamic` | [Dynamic models](../skills/econ-design/references/dynamic-models.md): observed panels, official pinned Rust criterion, CCP, simulation moments, sequential estimators, continuous-time and capacity estimation, hidden types and dynamic adoption. |
| `method_extended_macro` | [General equilibrium](../skills/econ-design/references/macro-models.md) and [stochastic equilibrium](../skills/econ-design/references/dsge-models.md): observed productivity, household/firm clearing, lifecycle choices, Sequence-Space Jacobians and shocks. |
| `method_agent_simulation` | [Agent models](../skills/econ-design/references/agent-models.md): explicit behavior, transaction conservation, learning, policy experiments and next candidates. |
| `method_extended_numerics` | [Numerical methods](../skills/econ-design/references/numerical-models.md): moment rank, derivatives, sparse Python/Julia solves, JAX devices, original-equation surrogate verification and Monte Carlo. |

Select the pinned requirements of the chosen family and Python 3.12. The extended causal environment uses pandas 3; the other families retain their declared pandas version. The [causal R requirements](../skills/econ-data/scripts/requirements-causal-r.json) specify R and its selected packages. A Python command that calls R or Julia declares `runtime.companions`; the [compound-runtime contract](../skills/econ-design/references/adaptive-research.md#julia-runtime-identity) records executable, package and native-library identities in the stage signature. A GPU request executes on an observed compatible device and records its returned execution status.

## Discover sources and continue an adopted experiment

Select `research_source_discovery` for [citations, original passages and reusable corpora](../skills/econ-literature/references/source-discovery.md). Select `research_data_discovery` for [official data, original tables, declared joins and panel/geographic construction](../skills/econ-data/references/research-data.md). Their hashes and economic dimensions enter the existing design assessment.

Select `research_adaptive_experiments` for [proposals and result-dependent search](../skills/econ-design/references/adaptive-research.md). Sol adopts the target, population, scientific evaluation, permitted axes and observation partitions. Completed training/validation results determine the next bounded candidates through the same DAG. The selector's exact winning parameters reach the final held-out evaluation. The existing state retains that single final evaluation, earlier attempts and source-backed adoption.

## Generate articles slides and a reproduction package

Select `research_result_artifacts` for [automatic registration and article/slide production](../skills/econ-writing/references/result-artifacts.md). The portable example supplies seeded scientific inputs and an executable manifest. Registration retains the complete fitted result and names quantities, units, covariance, inferential reference, sample counts and intervals. The same bindings generate tables, SVG, Quarto, HTML, LaTeX, PDF, Word and PowerPoint. Converters consume the checked model contract; changed model, code or result bytes invalidate dependent exports.

The existing reproduction producer packages completed selection branches, excluded failed candidates, procedure-capture stages and shared declared helpers. `environment PACKAGE --workers N` reports runtime closure and CPU/memory/device bounds. `restore PACKAGE --output NEW_ENV --python PYTHON3.12` creates an independent Python environment from exact pins and commit-pinned sources. `reproduce PACKAGE --python NEW_ENV/bin/python --output NEW_PROJECT` retains a fresh replay and compares its selected outputs with saved quantities and units. R and Julia use the declared project environments and compound identities. Preserve the existing Pixi, R and Julia manifests and locks with the selected inputs.

## Native lifecycle and child returns

The registered native hook commands preserve the original task, current governing rules, permissions, scoped operations and actual tool/child returns. Codex uses its own command-trust controls. The eight registrations cover session start, prompt submission, tool pre/post callbacks, child start/stop, stop and interruption. Context packets use the host-supported context events. Stop, child-stop and interruption retain their supported decisions and records.

A successful `SubagentStop` retains the exact child return and scope-check status, then queues its parent handoff in the same task directory. The next eligible parent `PostToolUse` emits the full restoration packet and pending statuses once. A child tool callback preserves the pending parent handoff. Failed formal checks retain their blocking decision; ordinary child completion retains its assigned scope for the parent's integration. The current host's callback result and command-trust state determine activation. TEAM retains model-role ownership, delegation and resumption.
