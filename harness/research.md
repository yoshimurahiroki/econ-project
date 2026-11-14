# Executing an adopted research pipeline

[ECONOMIST](../runtime/ECONOMIST.md) owns authority, preserved scientific inputs and completion; [EXECUTION](../runtime/ECONOMIST.md#5-execution) owns operation and failure handling. 

## Run an adopted pipeline

`research.py` executes an adopted local DAG and records each attempt in the existing `state.py` store. The host selects the research question, scientific methods, acquisition and analysis commands, definitions and inputs through the seven Skills. A stage runs after its declared consumed outputs complete; a failed stage blocks its descendants and independent branches continue.

A saved stage is reusable when its adopted specification, declared source and helper bytes, exact environment, executable and consumed result versions match a completed state record. The renderer resolves each numerical token to a named result key, checks its saved unit and applies its declared format. The same state record links the displayed quantity to the actual producing execution.

Use `python harness/research.py --help` for the command and options.

The root is the project owning the source files. The manifest and the store are root-relative. The store defaults to `.agents/state/team.json` and is initialized if absent. `--parent` attaches attempts to an existing state task, inheriting its full governing context, scoped holds and authority; its write scope must include `.agents/research/PIPELINE`. An existing parent must already be in the selected store. Release overlapping active writer scopes through the existing state transition before starting child attempts. A single runner lock coordinates research runners in the root, and the existing state helper coordinates individual store updates. Commands execute with the host process's operating-system access and must stay within their authorized scope and declared generation outputs.

A manifest is a JSON object with a `pipeline` ID and `stages` array. Stage IDs and output names use letters, digits, underscores or hyphens. Each stage has `inputs` (root-relative files), `depends` (producer stage to list of output names), `outputs` (name to path relative to its generation), and exactly one of `argv`, `render`, `select` or `adaptive`. Input and output paths stay within the project through regular files. Inputs include the actual data, adopted specifications, source scripts, called helpers, seeds, package/environment locks and other files that affect the calculation. Stage changes and tracked input bytes invalidate the stage; selected upstream output identities and definitions invalidate its consumers. The declared environment is exact: `env` supplies literal name/value pairs and `inherit_env` names existing variables to copy and track. Supply executable search `PATH` when the command needs it. The selected invocation path, resolved executable bytes, actual argv, environment-value hashes and runner bytes are recorded. Declare every consumed helper, external-source snapshot and relevant environment specification. Keep credentials in the host's approved storage and pass them only through `inherit_env`; inherited values enter the child process while signatures retain their hashes. Keep secrets out of literal `env`, argv and program output, which remain saved. The specialist owner establishes scientific validity through the adopted model and producing calculation.

For an argv stage, arguments are passed directly to the child process. `{root}` expands to the project root, `{out:NAME}` to the named file in the new generation and `{dep:STAGE:NAME}` to a declared completed dependency's file. The command runs in its fresh generation directory, with declared environment variables only. Outputs must be regular files present on successful exit; a producer validates its own schemas, convergence and numerical requirements before exiting successfully. The runner drains stdout and stderr concurrently and retains their combined final 64 KiB in the existing `research:execution.log`, with total `output_bytes`, `log_truncated` and the actual exit status. It creates no separate log file. Files of an unsuccessful attempt are not selected for descendants.

For the existing research analysis entry points, the runner also tracks files read through the command's specification: analysis and partition data, the construction record and its canonical table, SQL sources and lookup tables, model source, saved fits or solutions, and declared evaluation references. These files enter the ordinary input snapshot and output definitions. Name the specification through `{root}`, a dependency placeholder or an absolute path. Generated specifications resolve after their producing stage completes. Analysis references resolve relative to the specification; `research_data.py` references follow its explicit `--root`. Keep those paths inside the project. Other commands declare their consumed files in `inputs`. The same resolved input set determines reuse, holdout separation and reproduction packaging.

Discovery identifies the invoked script at its source, deployed or flat package path, including the flat `research_estimator.py` alias and unchanged script copies. `runtime.probe_argv` identifies the script position for a wrapped Python command; a direct Python/PyPy invocation uses its interpreter options. User programs with the same filename retain their own declared input contract.

For `equity.py`, pass `--root {root}` and use project-relative `products`, `agents`, `reference_products` and `observations` files. The same rule covers nested IO models used by cash-flow valuation, reverse valuation and news updates. The runner tracks their CSV or JSON inputs and the calculation resolves them against the declared project root. Absolute paths retain their existing meaning; omitting `--root` retains the standalone command's working-directory resolution. Inline records remain part of the specification. A `-` specification argument denotes standard input and adds no file; its input source belongs in the stage's explicit `inputs`.



A rendered template contains two opening braces, `stat:training`, and two closing braces. The selected JSON key must resolve to an object such as `{"value": 1.25, "unit": "hours_per_week"}`; its finite numeric value, exact unit and format produce the inserted bytes. Key paths are arrays of JSON object keys. Supported formats are `f`, `g`, `e` and their precision forms such as `.2f`. The bindings must exactly match the template placeholders. The template is a tracked input and the source result a declared dependency. Additional tables and figures can be argv stages that consume the same result; their scientific and content checks belong in their generating commands.

The same renderer carries saved economic definitions into section templates. Add `definitions` to `render`. A definition placeholder contains two opening braces, `definition:NAME`, and two closing braces; names such as `comparison`, `period` and `equilibrium` select the corresponding bindings. Each binding has `stage`, `output` and a `key` array selecting a nonempty string from a declared saved-result dependency. For example, `"comparison":{"stage":"saved","output":"result","key":["metadata","comparison"]}` inserts that result's exact comparison. Equations, notation definitions, identifying conditions, parameter roles and welfare definitions use their own selected text keys. Select the saved language edition appropriate to the manuscript. The renderer preserves the text literally and uses the numeric bindings for quantities.

Keep each section's source template and consumed result outputs explicit. Title, Abstract, Introduction, Results and Conclusion can bind the same headline statistic and defining comparison through their own stages. A changed section template rebuilds that section and its assembled consumers while preserving matching saved-result stages and other sections. A changed scientific result rebuilds its declared consumers. Register saved results through the artifact normalizer before writing; render operations consume those completed outputs and perform no estimation.

Every successful stage publishes an immutable generation by completing its state task after all declared files exist. The JSON response returns each selected generation's root-relative file paths and `executed`, `reused`, `recovered`, `skipped`, `failed` or `blocked` status. Exit codes are 0 for a completed DAG, 1 when a stage failed or was blocked, and 2 for invalid input or a runner/state error. New attempts use separate generation paths. Previous complete files remain available after a failed replacement, but the failed branch is not passed to current descendants. State completion, input hashes, consumed versions, definitions and output bytes are checked before reuse. Modifying a saved result or rendered artifact invalidates its reuse. Original context and input versions remain in state task records; retain the project specification and source files under their own version control as well.

Read the [interface](research.md#interface-run-an-adopted-pipeline) for the exact input forms.

## Acquire the selected literature and data

Use the [source connector](../skills/econ-literature/scripts/research_sources.py) to inspect public bibliographic metadata, indicator definitions and observed series. Each result retains its query, exact response bytes, retrieval identity and SHA-256. An explicitly selected original can be fetched and parsed through the existing equity document reader. Read the original argument establishing a paper's result before adopting that result in the research design.



Select a dataset by its observation unit, variables, measurement, period, identifying variation, keys and actual access path. The World Bank connector retains source definitions and distinguishes observed numbers, null values and absent requested keys. The host uses its other connected statistical and document tools under econ-data's acquisition contract. Freeze an adopted source snapshot for reproduction; an authorized refresh produces a new tracked input version.

Read the [interface](research.md#interface-acquire-the-selected-literature-and-data) for the exact input forms.

## Estimate a linear specification

The [estimator](../skills/econ-data/scripts/research.py) executes OLS with `statsmodels.OLS` and 2SLS with `linearmodels.iv.IV2SLS`. Use a Python 3.12 scientific environment with the [pinned research requirements](../skills/econ-data/scripts/requirements-research.txt); the [existing equity requirements](../skills/econ-data/scripts/requirements-equity.txt) supply PyBLP and document extraction for the structural and source workflows. Select an existing matching environment or create a fresh task-owned environment:



Use that interpreter for numerical commands and the case's `--python` argument; the runner can use the host's standard-library interpreter. Each row in the selected CSV, Parquet or Arrow IPC table has a unique recorded ID. The JSON specification names `data`, `id`, `outcome`, `population`, `period`, `unit`, `sources`, `method`, `exog`, and, for IV, `endog` and `instruments`. A shared sample uses its hashed `data_record`, which carries the adopted sample and variable definitions into the result. `sample_columns` defines additional complete-case columns for a stipulated common sample; `filters` supplies explicit column/operator/value restrictions. `question` and `identification` retain the adopted economic target and conditions. Additional sample fields retain nonempty categorical labels and finite numeric observations; model columns follow the adopted numeric design. The interface rejects unsupported fields and options before producing an estimate and publishes a complete JSON result by atomic replacement.



`covariance: {"type": "HC1"}` selects heteroskedastic robust finite-sample adjustment. `{"type": "CR1", "cluster": "site_id"}` selects the official one-way cluster adjustment using the fitted rows' site labels. Outputs preserve full named covariance, coefficients, standard errors, actual fitted and excluded IDs, cluster assignments, source/specification hashes and engine versions. They retain each engine's actual inferential reference: OLS CR1 uses Student t with G−1 degrees of freedom; debiased IV uses Student t with n−k. The IV result keeps the package's first-stage diagnostic distribution and a separately computed conditional Wald F with its actual covariance and degrees of freedom. Use these named quantities and references in downstream interpretation and rendering.

Read the [interface](research.md#interface-estimate-a-linear-specification) for the exact input forms.

## Choose and execute the next research operation

Use [the economist's procedure](../runtime/ECONOMIST.md) to select the determining research operation and [econ-design](../skills/econ-design/SKILL.md) to establish its scientific specification. The assessment below consumes that adopted comparison and candidate ordering.

The [design assessment](../skills/econ-design/scripts/research_design.py) checks that specification against retained source bytes and actual CSV records. Its `sources` map binds IDs to `{path,sha256}`; source references use `{source_id,start,end,quote}` with character offsets into the exact UTF-8 text. Its `datasets` map declares the CSV path/hash, observation `unit`, `population`, documented `period:{start,end}`, documentation spans, `grain` keys and `definition_versions`. A candidate declares all five economic dimensions, source evidence, `closest_answers` with the same dimensions, and the owner's contribution judgment: `classification` is `replication` or `changed_contribution`, with `owner`, `rationale`, `changed_dimensions` and supporting evidence. The owner cites each closest answer in that judgment.

Each candidate's `requirements` declares the fields, unit, population, period and actual identifying variation its design uses. Optional missingness fractions, observed year coverage, sample filters, observation-status fields and linkage requirements check the corresponding rows and keys. Numeric variation counts numeric values. A candidate's `next_operation:{argv,cwd}` records the authorized executable action. `selection:{rule:"owner_order",order:[...]}` lists every candidate once; the result selects the first feasible one and retains every candidate's findings, definition versions, source hashes and selecting evidence.



Use this result as a consumed output of the selected source, estimation or experiment stage. [the economist's procedure](../runtime/ECONOMIST.md) owns interpretation and continuation; native search and worker tools supply retrieval and delegation, and the local executables supply the declared calculations and persistence.

Bibliographic discovery supports exact DOI lookup with `work --doi DOI`, one-hop backward records with `references --doi DOI`, and union search with repeated `literature-multi --query QUERY`. All take `--output DIR`. Reference rows retain the original work, rank, reference key, DOI and complete original reference fields, including unresolved text. Union rows retain each query, its status, rank and exact response origin; normalized DOI identifies duplicates, and an exact title/year identity handles rows without DOI. A failed query publishes its attributable partial record and returns a failing status. Follow selected references and forward citations through the current source tools until their original passages resolve the research comparison.

Read the [interface](research.md#interface-choose-and-execute-the-next-research-operation) for the exact input forms.

## Compare specifications on a frozen protocol

Define the scientific target, population, units, identifying restrictions, sample and inference before opening trial results. A predictive comparison fixes training, validation and holdout roles; a causal or structural comparison fixes the adopted parameter and its relevant diagnostic or model criterion. Put that comparison in a tracked protocol. Every compared result carries exactly the protocol's `identity` fields (`estimand`, `evaluator`, `sample`, `partition`); its `protocol` object matches the adopted `evaluation_protocol`. Bind data partitions, code, seeds and evaluator versions to their actual hashes. A target change creates its own adopted comparison.

The manifest's optional `grids` array expands declared alternatives. Each grid specifies `prefix`, `parameters` (arrays of distinct strings) and a normal stage `template`. Optional `order` names every parameter once; positive `budget` bounds the expanded alternatives and nonnegative integer `seed` fixes the declared randomization. Expansion follows the declared Cartesian order and budget. `{param:NAME}` and `{grid:seed}` insert the selected literal values. The expanded stages retain the same input, output, dependency and authority rules as ordinary stages.

A selection stage declares `select:{protocol:"protocol.json",candidates:{"candidate-id":{stage:"trial-id",output:"result"}}}` and one output. The protocol is a declared input; candidates are declared dependencies. Its `metrics` array names JSON `key` paths, `direction:"min"|"max"` and optional feasibility `min`/`max`. Metrics rank feasible candidates lexicographically; `tie_break` names every candidate in the adopted order. `on_failure:"block"|"exclude"` determines how an actual failed trial affects selection. The protocol also declares its `seed`, `budget`, `holdout` paths and exact `evaluation_protocol`. Trial ancestry and literal arguments are checked against the declared holdout paths. The selector saves all observed metrics and failures with the selected ID.

An action stage can declare `when:{stage:"choose",output:"selection",equals:"candidate-id"}` and consume that selection. The runner executes the selected branch and reports other branches as `skipped`. Put winner-only holdout evaluation and artifact generation on that branch. The native owner can use the returned comparison to adopt a subsequent experiment in the existing manifest and governing context.

For fixed-split prediction, `research.py evaluate SPEC -o RESULT` calls scikit-learn OLS or Ridge. The specification names distinct `train_data` and `evaluation_data`, unique `id`, `outcome`, `features`, `candidate:{method:"ols"}` or `{method:"ridge",alpha:1}`, partition, protocol and scientific identity. Preprocessing fits on the training records; the result retains training/evaluation IDs, predictions, MSE, model parameters, source hashes and package versions. Use the same fixed input and protocol for every trial, and retain the selected result and winner-only holdout output in the existing result record.

An argv stage can declare `checks:[{type:"json",output:"result",fields:[{key:["metrics","loss"],type:"number",min:0}]}]`. Declared types and exact values/ranges check the producing file before completion. Preserve the actual command exit, current log and checked output together.

## Recover interrupted attempts

The runner saves the launched process identity, actual terminal return and output hashes in the existing attempt before publication. On restart, a complete matching receipt and matching inputs allow that same attempt to complete without repeating its command. This recovery includes a prepared final held-out evaluation; a new evaluation after an observed terminal return requires a fresh holdout. A prepared generation whose source, output or context changed fails that reuse check. An active command with no observed terminal return remains blocked for reconciliation through its actual process and target; use its saved process identity and bounded diagnostic to establish whether the child still runs before retrying.

SIGINT and SIGTERM stop the active child process group and prevent later stages from starting. An interrupted command records its signal and actual return, removes its incomplete generation, and starts a fresh attempt on the next invocation. A saved prepared generation remains available for publication recovery. Signal exits use `128 + signal` (130 for SIGINT and 143 for SIGTERM). A terminal calculation failure retains the explicit retry procedure below.

For an observed failed attempt, repair the determining cause and retain the actual reconciliation evidence. Select one explicit retry with:



The evidence file is hashed and retained with the new attempt. Existing failed logs and immutable successful generations survive. Resume at the affected stage and rebuild its descendants while reusing matching independent results.

Read the [interface](research.md#interface-recover-interrupted-attempts) for the exact input forms.

## Retain and reuse an observed procedure

The [experience helper](experience.py) stores reusable procedures as completed output objects in the same state store. A captured procedure consumes a current completed result and its successful actual execution record. Its seven typed conditions bind `model`, `engine`, `schema`, `method`, `failure_mechanism`, `package_versions` and `specification_sha256` to named producer-output keys. The specification hash must identify an actual tracked producer input or consumed output. Capturing retains its original task, inputs, authority, execution and source versions.



Capture configuration names `producer_id`, `output_id`, `execution_output_id` (default `research:execution`) and `conditions:{NAME:{output_id:"RESULT",path:["identity","NAME"]}}`. `permitted_switches` binds permitted revisions to the producing evidence. The optional stage field `learn:{spec:"learn.json"}` performs this capture after a successful stage. Its stage-specific metadata uses `output:"result"` and `conditions:{NAME:{output:"result",path:["identity","NAME"]}}`; these logical names resolve to the completed producer's actual immutable file IDs. Learning metadata has its own capture-task input and identity. Changing its wording or path recaptures the procedure while reusing the unchanged numerical producer. A requested capture failure blocks its dependent postcondition while preserving the completed calculation.

`find` returns only current matching procedures. `prepare` binds the selected procedure and its producing evidence to the target task's current context, scope and holds as an adoption proposal. The owner then applies the current specification and executes the proposed operation. Native-operation capture uses the actual host command arguments and terminal return, with `native_evidence.expected_workdir` and `native_evidence.algorithm` referencing the producing task’s explicit working directory and adopted procedure steps. The existing native operation adapter validates the call, returned result, source references and continuation sessions. Earlier package, preservation, restoration and readback references remain readable as supporting evidence; a working-directory repair additionally binds its prior command to the same command in the other directory. Supporting summaries retain their source status and supply no independent proof of an external action. Explicit `--allow-rebind` discovery and `prepare --bindings TARGET_INPUT.json` can transfer an owner-authorized stage/release or specification revision declared by the original permitted-switch evidence; the current target tracks those bindings and specification. The resulting proposal retains `result_reuse:false`.

For an observed project command or environment repair, reuse its actual saved execution and applicable inputs. Existing `execution_kind:"task_check"` records can still supply their retained producer, command return, condition references and prior failure observation. This compatibility path reads saved evidence; no check runner is available. New research procedures consume the requested stage's `research:execution` output and adopted specification. `find` and `prepare` retain the target's current authority, scope and holds.

Read the [interface](research.md#interface-retain-and-reuse-an-observed-procedure) for the exact input forms.

## Bind claims equations and saved results

The [evidence binder](research_evidence.py) checks an explicitly selected manuscript against source, result and producer identities:



The contract names `manuscript:{path,sha256}`, `adopted` scalar identities and optional `sources` with exact file hashes and metadata. `claims` bind an exact target span to source IDs/spans and a native `judgment:{reviewer,decision:"supported",rationale}`. `numbers` bind target and displayed-unit spans to a result path/hash, semantic key, unit, format and all adopted `identity_keys`. `models` bind an equation span, exact code span/hash, original residual key and adopted tolerance to the same model/specification identities and native judgment. A changed source, code, value, unit, identity or excessive residual fails the binding and preserves the prior complete output.

Optional `mappings` bind individual symbols and parameters. Each names `kind:"symbol"|"parameter"`, `status:"derived"|"fixed"|"calibrated"|"estimated"`, manuscript `target`, exact `code` span, result identities and native judgment. Its `origin` names either a source ID/span or a specification path/hash/key/value/unit. Fixed and calibrated parameters bind the actual adopted specification; estimated parameters bind a named `{value,unit}` result quantity. `coverage` selects manuscript spans for numeric-token accounting; displayed statistics and explicit source/assumption/citation claims account for those tokens. The native owner establishes the claim's meaning and economic inference using the bound passages and calculations.

Read the [interface](research.md#interface-bind-claims-equations-and-saved-results) for the exact input forms.

## Estimate orthogonal scores

The estimation interface supports `method:"dml_plr"` through DoubleMLPLR and `method:"dml_did"` through the pinned DoubleML two-period panel interface. Define treatment, covariates, outcome or pre/post outcomes, actual individual IDs, sample, population, period, units, sources and the adopted identification. The partial linear target uses the declared conditional exogeneity and partially linear model. The DID target uses its experimental or observational score and adopted parallel-trends comparison. Bind each adopted target to its own model, identification, sample and result identity.

`dml` declares integer `folds`, `seed` and `score`; PLR selects `"partialling out"`. DID selects `"experimental"` or `"observational"` and boolean `normalize`; observational DID also declares `clipping_threshold`. `learners` declares linear or positive-alpha Ridge outcome models and PLR treatment models; observational DID declares a logistic propensity model with `C` and `max_iter`. The saved result retains actual folds, fitted/excluded IDs, score, clipping, parameters, confidence intervals and package/specification versions. Scientific adoption follows the corresponding design and engine-selection rules.

## Solve the adopted finite horizon model

The [macro interface](../skills/econ-data/scripts/research_macro.py) solves a deterministic finite-period representative-household growth model. The household chooses positive capital and consumption to maximize the sum of discounted log consumption. Output equals productivity times capital to `alpha`; resources include depreciated capital and output after its tax. Tax receipts are government absorption. The specification fixes `alpha`, `beta`, `delta`, initial and terminal capital, baseline/scenario `productivity` and `output_tax` arrays, population, period, units, sources and `tolerance`.



The implementation supplies analytic objective gradients and resource Jacobians to SciPy SLSQP, checks them against finite differences and evaluates the original Euler and resource residuals at both returned paths. It publishes the actual capital, output, consumption, welfare and scenario difference with engine/specification identities after the declared residual tolerance passes. For another adopted heterogeneous-agent or aggregate-equilibrium model, select its matching package, information/timing, market closure and original residuals through the existing structural design and numerical owners.

<a id="capture-the-selected-python-and-r-environment"></a>

Read the [interface](research.md#interface-solve-the-adopted-finite-horizon-model) for the exact input forms.

## Capture the selected Python, R or Julia environment

An argv stage can declare `runtime` with `language:"python"|"r"|"julia"`, `probe_argv`, `version`, `packages` and `files`. The literal `probe_argv` is the leading interpreter/options prefix of the stage's actual argv. `version` enforces the selected runtime version when supplied. `packages` maps installed package names to exact required versions or `null` to record their actual versions. Every `files` entry is a declared stage input, such as a pinned requirements file or the project's existing Pixi/rv lock. A Python stage that invokes R or Julia declares that interpreter in `runtime.companions`, including its actual environment and selected package closure.

For the causal runner and descriptive summaries, the selected R companion supplies the actual interpreter and options through `ERS_R_ARGV`. The causal runner's Julia estimator uses `ERS_JULIA_ARGV`. Each language has one selected companion. The runner binds these JSON prefixes to the environment used by runtime capture and reproduction, and the calculation executes the selected prefix, including its project and startup options. An explicit `--rscript` or estimator `julia` executable must match that companion. Standalone descriptive summaries retain `Rscript --vanilla`; standalone Julia fits retain `julia --startup-file=no`. A declared companion supplies its complete options.

Completed dependency placeholders resolve before specification discovery and runtime capture. An upstream-generated Python script therefore supplies the same script path and import directory to the runtime probe and the actual command. Before replay generates that script, the reproduction environment command reports its pending dependency and retains the recorded runtime requirements. Replay resolves the dependency through the normal runner and compares the resulting installed package versions with the saved runtime.

Use the stage's `executables` list for external commands invoked by its wrapper, such as Pandoc, Quarto and LuaLaTeX. Entries are distinct executable paths or names resolved through the declared `PATH`. Their invocation paths, resolved files and byte hashes enter the stage identity and reproduction provenance, including stages without a language runtime. Changes invalidate reuse, and a change during execution prevents publication.

Use `runtime.requirements` to name the existing selected family's requirement files, also listed in that stage's `inputs`. Python files contain exact `name==version` pins or `name @ git+https://repository@FULL_COMMIT_SHA`; R uses the existing JSON with `r_version` and `packages`. The runner derives its package pins and tracked hashes from those sources. Conflicting explicit `packages` values or conflicting requirement files stop before calculation. A Python Git requirement also checks the installed distribution's direct-source URL and full commit. R source references retain their existing acquisition role; the runtime checks the installed R/package versions. `runtime.files` tracks Pixi/rv locks without treating the lock contents as the selected runtime's installed versions.

For the research entry points, the runner selects table-reader packages from the actual input references and the specification's output format. Parquet and Arrow IPC select Python `pyarrow`, R `arrow`, and Julia `Parquet2` or `Arrow` according to the format. Julia table reading also selects `Tables`, `DataFrames` and, for CSV, `CSV`. An `assemble` specification using `sql` selects Python `duckdb` and `pyarrow`. Explicit package versions remain authoritative; otherwise the runtime records the installed versions. Generated dependency specifications use the same selection before execution. The stage signature and reproduction package retain these dependencies and their saved exact pins together with declared requirement files.



Restore the selected family into its own Python 3.12 environment. For example, run `python3.12 -m venv .venv/ers-causal`, then `.venv/ers-causal/bin/python -m pip install -r skills/econ-data/scripts/requirements-causal.txt`. In `econ-project`, the existing Pixi Python can create this environment. Point both `argv` and `runtime.probe_argv` to its absolute interpreter. Select the R companion and its `R_LIBS_USER` from the adopted rv project. The research and market families pin pandas 2.2.3; the causal family pins pandas 3.1.0. Use separate environments for those families. Exact versions stay in their existing requirement owners.

Before reuse and after execution, the runner records the actual runtime version, interpreter/wrapper identities, selected installed dependency closure and library locations, tracked environment-file hashes and selected environment. Initial probes use an empty temporary directory inside the project so wrappers can find its environment manifest through their parent-directory search. Python discovery follows the selected distributions' requirements, including `packaging`, and fingerprints their installed source and editable modules. R follows the selected packages' DESCRIPTION dependencies. Julia fingerprints selected package source, extensions, project files and loaded libraries. File identities include size, nanosecond modification/change times and inode/device; unchanged identities reuse the in-process content hash. Directory membership and file identities are checked before reusing a package digest. The runner keeps no persistent environment cache. Install the dependencies selected for the actual project in its adopted environment; the mini template retains its lightweight infrastructure definition. The full project retains its existing fixed dependency and lock definitions.

For Julia, bind the project's existing `Project.toml` and `Manifest.toml` through `runtime.files` and stage inputs, and include the chosen `--project` option in `probe_argv`. The existing probe records package UUIDs, versions, sources, dependency closure, loaded libraries, active project and depots. Set `JULIA_PROJECT`, `JULIA_DEPOT_PATH` and `JULIA_LOAD_PATH` in the stage environment when the project uses them. Use Julia for a required specialist implementation or an observed performance improvement on the adopted calculation. A SQL query executed through Python uses that interpreter's `duckdb` package and the same tracked source files.



A missing required package or mismatched version stops the affected operation before its calculation. A changed observed package closure invalidates the consuming stage even when the interpreter binary and input data are unchanged. The saved execution retains that identity beside the actual result.

For a consequential selected interface, add `apis` to a Python or R runtime, including an R companion:



Each API's package has an explicit version in that runtime's `packages`. Python resolves the distribution-owned callable and binds the proposed positional count and keyword names to its actual signature; it records that signature, installed documentation hash and available source identity. R resolves the package export, checks its formals and records the version-matched installed help identity. An unavailable symbol, signature or adopted call stops the affected stage. The runtime identity includes these observations, so a changed API or documentation version invalidates its consumers. Explicitly acquired official reference files use the existing tracked `runtime.files` inputs.

Python API symbols can traverse classes after the importable module, including `pyblp.Problem.solve` and `doubleml.DoubleMLPLR.fit`. The declared positional count includes the receiver for an unbound instance method. Pins derived from `requirements` supply the same explicit version contract. Method selection returns the official entry; this probe checks the callable in the interpreter that will execute that entry.

Read the [interface](research.md#interface-capture-the-selected-python-r-or-julia-environment) for the exact input forms.

## Select a named execution profile

A manifest may define `profiles:{"development":{stages:["prepare","fit"],overrides:{"fit":{argv:[...]}}},"formal":{stages:[...]}}`. Stage selections name the expanded stage IDs and include every required predecessor. Overrides explicitly replace selected stage fields while retaining their IDs. Choose the profile with `--profile NAME`; an unprofiled invocation preserves the original manifest behavior. The profile definition and selected name enter the execution signature, so development and formal results have distinct reuse identities. Keep any changed scientific sample or numerical specification explicit in that profile and its generated result.

## Detect changed results behind manual prose

For a text stage whose interpretation has been reviewed against a saved summary, declare `reviewed_results:{"summary":{"result":"SHA256"}}`. Each name refers to a declared consumed output. The runner compares its actual current bytes with that reviewed hash before reusing or producing the dependent artifact. A changed result blocks the affected text while preserving its preceding complete generation. The owner inspects the changed comparison, revises the passage where its conclusion changes and updates the reviewed binding. Select the stable result summary carrying the interpretation's quantities and definitions; display-only work can reuse its matching binding. This uses the existing task, output and dependency records.

## Package and reproduce a completed research result

The [reproduction producer](reproduction.py) assembles an explicitly selected current execution into a fresh package. The build consumes the existing state store and its exact completed tasks; it preserves the source project and performs no scientific rerun. Its config names `manifest`, optional `profile`, `tasks` mapping stage IDs to completed task IDs, `outputs` mapping selected output names to comparisons, `allow_inputs`, `allow_env` and `interpreters`. `allow_inputs` lists the exact data, code and environment paths approved for inclusion; `allow_env` names the disclosed selected environment values. Missing required inputs stop the build with their acquisition or inclusion requirement. Existing target directories are preserved.

Every package includes a top-level `README.md` derived from the same execution records. Optional `documentation` in that existing build config supplies `title`, `overview`, `data_availability`, `rights`, `code_license`, `data_sources`, `hardware`, `runtime`, `randomness`, `exhibits` and `references`. Use the adopted project metadata for these fields. A `data_sources` row names `name`, `source`, `version`, `access`, `license`, `observation_unit`, `period`, `variables`, `sample`, `weights`, `citation` and `files` as applicable. Inclusion comes from the actual approved copy map; naming a file in documentation never copies it. An `exhibits` row binds `label`, `stage` and `output` to an included saved result and carries its existing `result_id`, `specification`, `sample` and `status`. Keep adopted, superseded and alternative result identities explicit.

Set `documentation.formats` to `["md","pdf"]` to produce `README.pdf` with Pandoc and XeLaTeX; `documentation.font` selects an installed font, including a Japanese font. The [AEA February 2026 policy](https://www.aeaweb.org/journals/data/data-code-policy) requires a top-level PDF README with access and redistribution statements, computing requirements, execution instructions and program-to-exhibit correspondence. The [SSDE template](https://social-science-data-editors.github.io/template_README/template-README.html) supplies the section structure. [TIER 4.0](https://www.projecttier.org/tier-protocol/protocol-4-0/) supplies the input/analysis/output and master-script correspondence. [showyourwork](https://show-your.work/en/latest/latex/) supplies the explicit figure-to-producing-script pattern. ERS retains its existing DAG, completed generations and selective rendering path. Package construction and README rendering perform no deposit or research estimation.

A comparison is `{method:"sha256"}` or `{method:"numeric-json",path:["estimate"],unit_path:["unit"],rtol:1e-8,atol:1e-10}`. Numeric comparisons verify the actual value and its exact unit. Optional `helpers` maps `research.py`, `state.py` and `local_checks.py` to the project's existing matching helper copies; the default paths are under `harness/`. The selected manifest, observed runtime, producing argv/environment, source hashes, original context hashes and saved comparison outputs form the release provenance. Private task-store bodies and unselected source files stay in their existing storage.



The builder checks current inputs, consumed versions, executable and runtime identities before copying and at the publication boundary. Its atomic new directory includes an exact finite file inventory and the existing runner/helper closure. `verify` compares that inventory with the actual package. `reproduce` uses the copied runner in a fresh temporary project and compares the declared outputs with their saved originals. The package remains unchanged after replay. Python interpreter mappings and `--python` replace the interpreter within the saved command prefix, retaining its wrapper, interpreter options, script arguments and environment. The original invocation stays in provenance. The package includes completed stage closures, procedure captures and explicitly excluded failed candidates, including commands that returned zero and failed their output conditions. Replay preserves each candidate's failed status and actual exit code.

Keep packaged source references relative to their specification or explicit project root. Use `{root}` for project paths in stage arguments and `equity.py --root {root}` for project-relative equity CSV references. Package construction preserves input bytes; an adopted absolute-path specification retains that absolute destination after copying. Before packaging such a stage for another machine, update its path references through the existing specification owner and save the corresponding execution. This changes file locations while preserving the adopted model, observations and numerical options.

The independent Python/R case uses this same runner and reproduction builder for its generated data, estimates, summary, table, SVG, QMD and HTML outputs. Python/R notebooks and Quarto/LaTeX render commands can occupy the same argv stages with their real scripts, package/lock inputs and output definitions.

Read the [interface](research.md#interface-package-and-reproduce-a-completed-research-result) for the exact input forms.

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

Select `research_adaptive_experiments` for [proposals and result-dependent search](../skills/econ-design/references/adaptive-research.md). The lead adopts the target, population, scientific evaluation, permitted axes and observation partitions. Completed training/validation results determine the next bounded candidates through the same DAG. The selector's exact winning parameters reach the final held-out evaluation. The existing state retains that single final evaluation, earlier attempts and source-backed adoption.

## Generate articles slides and a reproduction package

Select `research_result_artifacts` for [automatic registration and article/slide production](../skills/econ-writing/references/result-artifacts.md). Registration retains the complete fitted result and names quantities, units, covariance, inferential reference, sample counts and intervals. The same bindings generate tables, SVG, Quarto, HTML, LaTeX and PDF. Converters consume the checked model contract; changed model, code or result bytes invalidate dependent exports. The saved-result gallery and [meeting materials](meetings.md) reuse registered display rows and figures without loading raw data or invoking an estimator.

`environment PACKAGE --workers N` reports runtime closure and CPU/memory/device bounds. `restore PACKAGE --output NEW_ENV --python PYTHON3.12` creates an independent Python environment from the same exact pins and commit-pinned sources used by runtime capture. Its installation plan reads the packaged runtime records and declared requirement files regardless of their names. After installation, it compares the selected runtime and companion closures with those records. A failed or interrupted restoration removes its incomplete new environment. `reproduce PACKAGE --python NEW_ENV/bin/python --output NEW_PROJECT` retains a fresh replay and compares its selected outputs with saved quantities and units. R and Julia use the declared project environments and compound identities. Preserve the existing Pixi, R and Julia manifests and locks with the selected inputs.

## Native lifecycle and child returns

The [state manual's hook contract](state.md#governing-context) defines task binding, callback evidence and compaction recovery. The registered events in `hooks/hooks.json` cover session start, prompt submission, tool pre/post callbacks, child start/stop, stop, interruption and post-compaction. Host permission and command-trust controls remain authoritative; callback records retain the task's declared targets, holds and completion evidence.

`SubagentStop` retains the exact observed child return as its assigned contribution and queues a parent handoff. The next eligible parent `PostToolUse` presents pending return identities once; a child callback preserves that queue. Governing-text restoration follows the state manual's entry, binding and recovery boundaries. [TEAM](../runtime/TEAM.md#return-and-integration) owns parent integration and [ECONOMIST](../runtime/ECONOMIST.md) owns final completion.

## Formulation interface

`research_design.py formulate CONTRACT --root PROJECT --output OUTPUT` saves `judgment.formulation`. Assessments use `candidates[].judgment.formulation`; matching saved records use `adopted_design`. Selection accepts `research_decisions.formulation={path,sha256}` and optional `candidate_id` for an assessment record. The producer validates these bindings.

## Interpretation interface

`research_design.py interpret CONTRACT --root PROJECT --output OUTPUT` binds exact `{path,sha256}` specification/result references. The saved outcome is `retain|repair|authority_required`; resumed selection uses `research_decisions.interpretation={path,sha256}`.

## Interface: Run an adopted pipeline

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

## Interface: Acquire the selected literature and data

```sh
python skills/econ-literature/scripts/research_sources.py literature --query "production adjustment mechanism" --output outputs/literature
python skills/econ-literature/scripts/research_sources.py indicators --query "GDP per capita current US" --output outputs/indicators
python skills/econ-literature/scripts/research_sources.py series --indicator NY.GDP.PCAP.CD --countries JPN USA --start 2020 --end 2024 --output outputs/gdp
```

## Interface: Estimate a linear specification

```sh
python3.12 -m venv outputs/research-env
outputs/research-env/bin/python -m pip install -r skills/econ-data/scripts/requirements-research.txt -r skills/econ-data/scripts/requirements-equity.txt
```

```json
{
  "data": "people.csv", "id": "person_id", "outcome": "productivity_points",
  "population": "synthetic training participants", "period": "simulated period 1",
  "unit": "productivity points per training hour", "sources": [{"path": "source-record.json"}],
  "method": "iv2sls", "exog": ["baseline_productivity"], "endog": ["training_hours"],
  "instruments": ["randomized_training_offer"], "covariance": {"type": "HC1"}
}
```

```sh
outputs/research-env/bin/python skills/econ-data/scripts/research.py estimate analysis.json -o result.json
```

## Interface: Choose and execute the next research operation

```sh
python skills/econ-design/scripts/research_design.py assess design.json --root /path/to/project --output outputs/design.json
```

## Interface: Recover interrupted attempts

```sh
python harness/research.py --root /path/to/project --parent TASK_ID --retry-failed STAGE_ID --retry-reason "corrected producing input" --retry-evidence retry-evidence.json research.json
```

## Interface: Retain and reuse an observed procedure

```sh
python harness/experience.py --root /path/to/project capture --task-id PROCEDURE --parent TASK --spec capture.json
python harness/experience.py --root /path/to/project find --conditions conditions.json
python harness/experience.py --root /path/to/project prepare --target TASK --procedure PROCEDURE --task-id PROPOSAL --conditions conditions.json
```

## Interface: Bind claims equations and saved results

```sh
python harness/research_evidence.py bind evidence.json --root /path/to/project --output outputs/bound.json
```

## Interface: Solve the adopted finite horizon model

```sh
outputs/research-env/bin/python skills/econ-data/scripts/research_macro.py solve macro.json -o macro-result.json
```

## Interface: Capture the selected Python, R or Julia environment

```json
{"runtime":{"language":"python","probe_argv":["/path/to/ers-causal/bin/python"],"requirements":["skills/econ-data/scripts/requirements-causal.txt"]}}
```

```json
{"runtime":{"language":"python","probe_argv":["/path/to/python"],"version":"3.12.16","packages":{"numpy":"2.3.5"},"files":["requirements.txt"]}}
```

```json
{"apis":[{"package":"numpy","symbol":"numpy.linalg.solve","positional":2,"keywords":[]}]}
```

## Interface: Package and reproduce a completed research result

```sh
python harness/reproduction.py build --root /path/to/project --config reproduction.json /path/to/reproduction-new
python /path/to/reproduction-new/project/harness/reproduction.py verify /path/to/reproduction-new
python /path/to/reproduction-new/project/harness/reproduction.py reproduce /path/to/reproduction-new
```
