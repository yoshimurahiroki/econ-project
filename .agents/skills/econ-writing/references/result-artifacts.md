# Generate artifacts from saved research results

The artifact operations extend `.agents/harness/research_evidence.py` and generate a manifest for the existing `.agents/harness/research.py` DAG. The research owner adopts the result sources, displayed quantities, units, words, equations, code spans and substantive judgments. The resulting registry retains each original result in full, including the covariance, inference reference, confidence-set structure and JSON nulls. Each input is identified by its project-relative path and SHA-256.

## Default LaTeX family

New paper and slide exports use the supplied [Econometrica paper](../../../tex/paper/ecta_template.tex) and [metropolis slides](../../../tex/slides/main.tex). Their original author/title/body placeholders remain available for direct editing. Keep the paper's class, configuration and `.agents/tex/paper/ecta-fullname.bst` together. A citing direct document reads its project bibliography at `tex/bibliography.bib`; a missing requested bibliography remains a build error.

The existing artifact helper derives Pandoc adapters from those exact source templates:

```sh
python .agents/harness/research_artifacts.py generate-adapters --root "$PROJECT"
```

The project Quarto defaults and new artifact LaTeX/PDF stages consume those adapters. The shared LuaLaTeX helper handles the journal class's fontspec initialization, citation-aware BibTeX passes, backreferences and previous-PDF restoration on a failed build. Template, package and build-helper versions enter the affected stage inputs, so a layout change rebuilds the corresponding artifacts while preserving matching estimates and their scientific definitions. Keep explicitly adopted document formats with their existing projects.

## Run the reproducible example

Use a project containing the existing harness, causal and market scripts and an analysis Python with their installed dependencies. Pandoc, Quarto, LuaLaTeX and an SVG converter must be available. Source the project's usual environment before these commands; choose an output directory that does not already exist.

```sh
python .agents/harness/research_evidence.py artifacts example \
  --root "$PROJECT" --output "$PROJECT/outputs/artifact-example" \
  --python "$ANALYSIS_PYTHON" --pandoc "$PANDOC" --quarto "$QUARTO"
python .agents/harness/research.py --root "$PROJECT" outputs/artifact-example/manifest.json
```

The example draws a seeded IV sample, executes `.agents/skills/econ-data/scripts/research_causal.py` and `.agents/skills/econ-data/scripts/research_markets.py`, and writes the actual results, source specification, data, article and slide templates, artifact specification and executable DAG manifest. It connects the simulated IV result and the independent uniform-offer, full-recall search model. The search reservation threshold z solves c = (1−z)²/2 for 0 ≤ c ≤ 1/2. Its saved equation residual, code expression, baseline cost and reported threshold are checked together. The DAG returns the current generation path of every artifact; those files are not copied over previous generations.

## Adopt an artifact specification

The `example` writes a complete working JSON specification. Its `sources` list gives each distinct `id`, `result`, `code` and, where applicable, `specification` and `data`, all relative to the project root. A saved producer `spec_sha256`, `data_sha256` or `script_sha256` must match the selected file. When a producer did not record a hash, provide the owner's SHA-256 in `expected_hashes` for each selected code, specification or data input. That adopted hash pins the selected input; it does not assert that an older result recorded its producing code hash. Preserve the actual source result and execution record when establishing that historical correspondence.

The normalizer registers every finite `{value,unit}` in `statistics`, names coefficients, standard errors, saved p values, saved 95% confidence limits and observation counts when available, and retains the complete source result. For a legacy result with coefficients, standard errors and an explicit normal or Student-t reference, it derives missing two-sided Wald p values and 95% limits from that reference and records the calculation and inputs. SciPy is loaded for that derivation. For older coefficient results, supply `coefficient_units` mapping each parameter to its actual unit; no unit is inferred from a label. `quantities` can explicitly select additional finite source-result key paths and their adopted units. Stable keys are `<source-id>.<semantic-key>`.

Each `bindings` entry supplies a registry `key`, exact `unit`, numeric `format`, `display_unit` and human-readable `label`. Supported formats are `f`, `g`, `e`, or a precision such as `.3f`. A template statistic consists of two opening braces, `stat:name`, and two closing braces. The table and figure markers use the same brace pairs around `table` and `figure`. A value and its displayed unit are inserted together; their character spans generate the existing binder's number contract automatically. Repeated occurrences each receive their own binding. `figure` selects binding IDs sharing one unit.

A `models` entry names the `source`, exact article `equation`, exact `code_quote`, source-result `residual_key`, tolerance and supported owner `judgment`. Optional `parameters` name an exact manuscript target and code quote, a specification key and its unit, and a registered result statistic. The generated model and parameter contracts bind the article, code and specification hashes, saved result identity, residual and selected quantity through the existing evidence binder. An owner confirms the substantive equation-to-code correspondence and economic interpretation; exact text matching establishes the selected passages.

For an adopted specification at `analysis/artifacts.json`, materialize and execute it with:

```sh
python .agents/harness/research_evidence.py artifacts materialize \
  --root "$PROJECT" --spec "$PROJECT/analysis/artifacts.json" \
  --output "$PROJECT/analysis/artifact-manifest.json" \
  --python "$ANALYSIS_PYTHON" --pandoc "$PANDOC" --quarto "$QUARTO"
python .agents/harness/research.py --root "$PROJECT" analysis/artifact-manifest.json
```

The generated stages normalize each selected result separately, merge their registry, render the table and SVG, generate article and slide sources, bind the manuscript and model, and export article HTML, LaTeX, PDF, Word and Quarto HTML plus slide PDF and PowerPoint. The article and slide sources are Quarto Markdown. Pandoc and Quarto execute as declared stages, and the Quarto output retains its executable version and hash. The PDF stages use a project-local LuaTeX cache; the runner records the selected environment and Pandoc executable identity.

Result, specification, data, code and template bytes enter the ordinary stage signatures. A changed result rebuilds its registry fragment and descendants; a figure consuming a different source remains reusable. A changed code or specification hash fails its old source binding until the owner adopts the changed input and its corresponding result. Binder verification rechecks the producing references of each selected registry quantity; an unrelated registry record is outside that selection. An older report fails when its selected result or code changes. Run the manifest again after an authorized update; the existing research runner retains prior generations and rebuilds affected stages. Update the article or slide text when a changed result changes the adopted argument.

## Claims, coverage and requested re-review

The same `.agents/harness/research_evidence.py review CONTRACT --root PROJECT --output PACKET` selects registered claims and their original source passages. An anchor may name its evidential `role`, such as population, identification, assumption, result or counterevidence. A claim's `bindings` list refers to the existing `numbers`, `models` or `mappings` IDs; the packet supplies only those selected result values, producing inputs and code spans. `bind` checks their existing units, identities, formatted values, original equations and residuals. Multiple anchors and bindings establish their separate roles; the owner judges the resulting inference.

`claim_coverage` locates citation, quantitative, inference, causal and theoretical sentence candidates within `coverage.spans`, or the manuscript when no scope is selected. It returns exact Unicode character spans, detection signals and uncovered candidates. These heuristics do not establish truth or semantic completeness. Read the whole requested argument and register the material claims they miss. For selected coverage enforcement, set `coverage.claims` to true and retain a supported `coverage.claim_judgment` using the existing reviewer/decision/rationale judgment. A specific nonmaterial candidate can have its exact `target` and reasoned `judgment` in `coverage.claim_accounts`. Existing numerical coverage and source-bound numeric accounts remain in force. This is a manuscript-specific assessment, not a general detection exemption.

A requested review round adds a `review` object to the same contract. Its initial `criteria` are nonempty `{id,text}` rows. The owner's `assessment` has a `reviewer` and `findings`; each finding retains `id`, `claim_id`, `criterion_id`, `decision` (`supported`, `revision-required`, `unresolved` or `removed`), `rationale` and nonempty hash-pinned file `references`, with an optional exact `span`. Revised text has exact manuscript spans in `changes`. The resulting `reviewed` record means that the supplied evidence assessment covers its selected claims; its findings can still require repairs. It grants no certification or release authority.

Re-review points `review.previous` to the saved completed review's `{path,sha256}`. Initial criteria, adopted scientific identities and finding targets remain fixed. A changed criterion is rejected. Omitted initial findings are rejected when supplying the revised assessment. A removed finding requires the actual earlier claim to be absent from the new manuscript. The packet identifies `claims_to_reassess`, `reusable_claims` and removed claim IDs. Reused findings link their historical review through `reused_from`; current source/result context stays beside the current manuscript.

The manuscript's whole-file hash pins the delivered version. Each claim fingerprint instead binds its actual quoted claim, adopted identities, source editions/propositions and original locators, selected quantity and producing code/input identities. It excludes unrelated manuscript text and manuscript character offsets. A peripheral edit preserves those judgments; a changed selected claim, source edition or calculation input reopens its dependents. Register the selected fingerprint, decision and rationale as an existing state object output when continuation needs it, and let each writing or analysis task consume that output ID. Requeue the changed output through the existing state helper; preserve unrelated outputs and completed consumers.

Supply the author letter only through `review.author_response` together with `review.response_after`, a hash-pinned separately saved assessment of the current evidence. The command validates that assessment and its criteria before reading the letter, and returns `response-comparison-required` with unchanged evidence findings. Compare the letter's assertions with those findings. A new determining fact returns to the same evidence and assessment path; a response alone never silently changes the verdict. This selected file dependency controls the packet contents; it does not attest to unseen host inputs or create another reviewer Agent.
