# Project integration

Use repository skills in the coding environment and SOURCE.md to identify Project attachment snapshots. Read this document only for explicitly requested distribution, synchronization, configuration, installation or state migration. Ordinary research uses the runtime and the selected specialist.

## Common core

`econ-project-mini` owns the shared source. Public and private destinations consume the registered common files and retain their own manifests, connections and project data. Account-specific plugin releases and authenticated services belong to the selected private destination. Destination receipts record the source direction and exact adopted commit for synchronized common files.

The resource source paths in [resource registry](../../registry/resources.json) define default shared instructions and tools. Entries marked sync=false remain project-owned. The synchronizer copies the same source-relative paths between repositories; it does not install deployment mappings. Each user chooses the source, destinations and paths. Origins are identified by their complete host/owner/repository path. Repositories with separate histories and different owners are supported.

Compare before applying. Supply the reviewed source HEAD and every destination HEAD. A working source also requires the comparison's `common_content_id` through `--expect-source-content`. Commit and push are separate operations.

```sh
SOURCE=/path/to/shared-template
TARGET=/path/to/research-repository

python scripts/sync_common_core.py --source "$SOURCE" --target "$TARGET"

python scripts/sync_common_core.py --source "$SOURCE" --target "$TARGET" --apply \
  --expect-source-head "$(git -C "$SOURCE" rev-parse HEAD)" \
  --expect-head github.com/example/research-repository="$(git -C "$TARGET" rev-parse HEAD)"
```

The default is a read-only comparison of the route-derived common paths. Repeat `--target` for multiple destinations or `--path` for an explicit subset. The source and destination roots must be distinct and match their Git origins and pinned HEADs. Ordinary startup, research work and environment setup do not synchronize.

A first synchronization adopts absent files. Existing files require an explicit `--claim 'HOST/OWNER/REPO:PATH=SHA256:MODE'` using the destination fingerprint reported by comparison. This claim establishes ownership of that particular path at that particular version. The three-way comparison then checks the previous receipt, current destination and new source. Uncommitted, staged and committed custom changes are protected. Resolve only the reported paths and claim their reviewed current fingerprints when choosing to replace them. Synchronization never stages files or clears the index.

Use `--migrate-receipt` to migrate a v1 receipt whose recorded source commit, blob, hash and mode can be verified. Source switching requires a separate reviewed ownership decision. Each v2 receipt records the source identity, input commit, selected hashes and modes, adoption state and destination identity. It contains no host paths or credential-bearing URLs. Project context, integration prose, research records and environment dependencies remain project-owned.

Use `--release PATH` to relinquish receipt ownership while retaining the local file and index. Released paths cannot be copied or deleted by subsequent synchronization. The explicit --release-local-configs option releases the declared LOCAL_CONFIG_PATHS; combine it with explicit --path entries when also copying common files. Remove public tracking separately with `git rm --cached -- PATH`; keep the runtime file locally and distribute its public example definition. The [configuration examples](config-templates/README.md) are managed common files; runtime MCP configurations and their generation state are local.

Deletions require `--delete PATH` with that source path absent. Moves require `--move OLD=NEW` with source OLD absent and NEW present. Existing destination paths still require their recorded baseline or a matching ownership claim. These operations stay within the explicitly selected paths.

The script checks all destinations before writing. It compares shared source inputs, repository identity and indexes at the start and final publication boundaries; immediately before each write it compares that target's content, index, repository identity and configuration. Previously written targets are checked at the final boundary. Writes use optimistic per-file atomic replacement, not a filesystem-wide transaction. It writes receipts after content, verifies the result and rolls back only its own unchanged writes on failure while retaining concurrent user changes. Exit codes are 0 for equality or successful application, 1 for comparison differences and 2 for a refused or incomplete operation.

Git `core.filemode=false` supports content updates and replay at the existing tracked mode. A mode transition requires `core.filemode=true` in a filesystem that tracks execute bits. The synchronizer refuses that transition and leaves index metadata unchanged. Run the temporary-repository checks with `python scripts/test_sync_common_core.py`.

## Standalone Project snapshots

Run from the extracted source tree; no Git repository, origin, commit, installed skills, network or model execution is needed.

```sh
python scripts/export_project.py --task econ-writing --mode compose --output /tmp/bounded-writing-new
python scripts/export_project.py --task econ-writing --mode compose \
  --condition whole_paper_abstract_introduction_or_section_architecture \
  --support econ-writing:explain --output /tmp/paper-writing-new
python scripts/export_project.py --task econ-edit --output /tmp/revision-new
python scripts/export_project.py --task econ-writing --mode translate \
  --condition example_ja_revision_translation --output /tmp/translation-new
```

`--task` accepts a specialist, operation ID, or compatibility alias. `--mode` selects a specialist mode; the default is declared in registry/operations.json. `econ-assertive` maps to writing/guidance and `econ-edit` or EDIT to writing/revise. `econ-workflow` exports the runtime boundary and asks the current task to resolve its specialist owner; `econ-handoff` exports the handoff resources for the existing result owner. Neither creates another specialist.

Without `--task` or `--skills`, the snapshot includes all five specialist bodies and their required resources. `--skills` selects specialist bodies and all their modes. Conditional resources remain inactive unless selected. `--support SKILL[:MODE]`, `--condition CONDITION` and `--references RESOURCE_ID` are repeatable. Reference selection also accepts an exact source/deployment path registered in registry/resources.json. Conditions are exact registry identifiers; misspellings fail. The operation registry defines conditions and required rule IDs; the resource registry maps each rule to its section and mandatory dependencies, and maps example IDs to language and function. Resolve their closure once per content version before rendering. Empty section selections add no body; they cannot supply a required rule. Requested headings include descendants and declared section dependencies. Missing required rules identify the rule and originating operation.

Ordinary writing includes CORE, the required PROSE sections, the chosen writing mode and exactly one selected writing profile. Profile priority is explicit `--style-profile`, adopted project preference, then default-micro. Examples are selected by language/function need. Whole-paper workflows are conditional and absent from a bounded writing snapshot. ECON_INDEX.md is generated from the selected operations; an unselected specialist index is not duplicated in the package.

Paste PROJECT_INSTRUCTIONS.txt into the Project instruction field and attach the exported files. Use a fresh directory outside the source tree. The exporter validates required files, registered links, aliases, placeholders and the 8,000-character instruction-field limit before publishing the package. Selected references resolve to flat exported aliases. Only inactive optional capabilities and examples may resolve to OPTIONAL_INPUTS.md. Activated mandatory references must resolve inside the package; a missing required rule reports its rule ID and originating operation and prevents publication. Unknown local references fail; no external-repository fallback is generated.

SOURCE.md records the logical resource ID, source path, source SHA-256, exported SHA-256, selected operations, conditions, registry hash and a content-based snapshot ID. Working source bytes are supported. Regenerate when the needed input versions change. These commands create local instruction packages; they do not update a live Project or plugin.

## Layout and generated index

The canonical source layout is skills/, runtime/, harness/, registry/, profiles/ and references/repository-policy/. The deployment paths in registry/placements.json map these to .agents/skills/, .agents/runtime/, .agents/harness/, .agents/registry/, .agents/profiles/ and repository-root policy pointers. Generate a fresh deployment package with the command below. Each selected resource is written at its declared deployment path, relative links are calculated from its destination, and client entrances are generated for that package. This creates a new package; applying it to an existing project is a separate requested operation. Export an already installed tree with --layout installed; this reads the three registries under .agents/registry/ and each declared deployment path. The exporter never guesses the layout.

```sh
python scripts/export_project.py --task econ-writing --mode revise --format deployed --output /tmp/revision-deployed-new
```

Maintenance scripts and their fixtures run from the complete source distribution. They are optional inputs in operation snapshots; explicitly selecting them fails before publishing either format, because their source-layout configuration and imports are not a standalone runtime package. The requested local team-state helper is supported separately with its declared runtime dependencies.

Both `--format flat` (the default) and `--format deployed` consume the same resolved operation and section selection. Installed input requires all three complete registries under `.agents/registry/`; an operation snapshot is not a replacement for that source registry.

Generate the repository operation index from the same registry:

```sh
python scripts/export_project.py --generate-index docs/ai/compiled_ai_skills.md
```

## Project additions and profiles

The export-project:v1 JSON block in repo_context.md supports version, writing_profile and files. Each file entry contains a repository-relative path and unique flat output filename. The persistent writing_profile can be default-micro or a repository-relative custom profile. --style-profile overrides it for this snapshot only; an absolute custom profile path is also supported. Custom inputs are hashed in SOURCE.md. Existing configuration is not rewritten.

Use econ-writing:profile (or its econ-style compatibility alias) to create or revise a profile. Creating or saving a profile does not adopt it. Switch the persistent preference only when the user requests adoption.

## Execution and handoff

Select files_calculation_external_or_resume for ordinary execution, resumption_active for saved-state reuse, delegation_active for a worker assignment, and publication_requested for an authorized publication or move. Use econ-handoff for the Handoff section and existing result owner. Select other sections only when their pending operation needs them. Existing project records remain canonical. Local state is optional; select requested_local_state_helper_operation to package its implementation when needed. An exported state.py requires --root for the actual project root. No helper starts a model or research program.

Select affected export and synchronization cases from `scripts/test_export_project.py` and `scripts/test_sync_common_core.py` using CORE. Actual generation and synchronization establish the selected package and destination behavior; reuse those results. The existing fixtures cover ownership, dirty-source, staged-index, rollback and execute-mode behavior.

## 0.12.0 changes and measured evaluation

Version 0.12.0 selects execution structure at the actual dependency. Settled input/output contracts use the existing procedure; prerequisites remain sequential; independent reads and isolated writes can run concurrently; specialist delegation accounts for briefing, coordination and integration. Shared-resource ownership includes session keys, browser tabs, transactions and remote targets. Returns retain their assignment/tool-call and input-version identity. The existing five specialist owners, operation registry, instruction authority and outcome completion rules remain in force.

Code work follows the real entry point to the owning definition, complete current body, relevant callers and working implementation. An available language server resolves ambiguous symbols or cross-file changes; known local changes use the existing patch path. General code exploration is owned by EXECUTION and referenced by econ-data. Repeated failures are compared by effective input, code, environment and returned error. Complete operation output is retained before a shortened display is used, and required original text is restored from its source.

The existing state helper now supports `find QUERY`, with exact parent/owner/recorded-status filters and snapshot-bound pagination. Candidates point to the original request, rules, adopted decisions, results and recorded failures. Selected `show` and existing resume/version checks establish applicability. Search is read-only and adds no database, transcript collector, embedding service or memory authority. TEAM and the existing helper/resumption routes load this capability through the resource registry.

The baseline is mini `bc96f1890dc06864091985129ed28f8eccba5506` and full `2cceb24a351b526a86fabe6f47d25aa8cb94a58c`, version 0.11.0. Same-input measurements used actual existing entry points:

| Operation and retained result | Before | After |
| --- | --- | --- |
| Locate the specified parent's saved PPML case in a 50-task synthetic store, then restore its full task record | Whole-store `show`: 565,059 UTF-8 bytes, one CLI invocation | `find` plus selected `show`: 11,927 bytes, two invocations; complete selected record, outputs and governing context identical |
| Locate the same parent's historical packaging failure and restore its full record | 565,059 bytes | 23,483 bytes; original history and references retained; store bytes unchanged |
| Generate the full distribution from identical 0.11 inputs | 60.695 seconds elapsed; 60.639 process CPU seconds | 6.499 seconds elapsed; 6.458 process CPU seconds |
| Interruption and resumption through the existing 33-call lifecycle | Original context restored; four lossy context updates and premature completion rejected | Same results; one analysis computation, no unnecessary child reassessment, identical analysis and recommendation hashes |

The distribution optimization validates each unchanged resource body, locator and selected scope once within its immutable verification invocation. Every operation retains its required-rule and selection coverage; each later snapshot rereads its bytes. Publication ownership, input-change detection, rollback, links, syntax and control-character checks remain active. Across the paired 550-file generated trees, 537 files were byte-identical; the other 13 were the two changed implementation modules, their bundled copies and corresponding integrity manifests. All generated rule bodies were identical. An initial separate timing pair was 60.152 versus 6.241 seconds. These are local generator measurements, not hosted-CI or model-token measurements.

Existing state tests exercised retained authority, holds, dependency versions and completion, with three added search cases. The existing exporter suite passed 52 cases, including shared-resource section validation, later-snapshot changes, malformed control text and omitted selections. The changed local-helper export is exercised in flat and deployed layouts using the actual `find` command and its packaged body. The 33-call lifecycle checked initial, intermediate, post-compaction-proposal, resumed and final records. No unseen-paper content or result was used for development or evaluation.

Two independent fresh agents also executed the same code, source-inspection and data-analysis assignment using their respective rule versions. The calibrated two-product logit project initially mixed counterfactual prices with stored baseline shares. Both agents read the installed PyBLP 1.3.0 implementation, repaired the owning profit function, invalidated its affected cache and saved the required JSON and Japanese decision memo. Both obtained baseline profit 1.1978837249168965, common-owner profit 1.3748225281836233 and net gain 0.07693880326672672 at transaction cost 0.1, selecting merger. An authorized continuation changed only transaction cost to 0.2: both retained the identical saved model result and run counter at two, regenerated the artifacts, obtained net gain -0.02306119673327328 and selected separate ownership. Original model parameters, population, objective and unused method were preserved. This case establishes completed repair, correct package use and continuation in both versions; it does not establish a general model-quality improvement rate.

Twenty OSS implementations and the 21 design-pattern applicability discussions were compared with these existing owners; detailed public provenance is retained in the root notices. The release adds no external runtime dependency, model service, permanent agent, hook, state store or standalone evaluation framework. Existing environment locks, separate quality environment, CI selection and official synchronization/publication paths are reused.

## 0.11.0 changes and measured evaluation

Version 0.11.0 connects issue priority to the downstream work invalidated by a wrong premise. The existing decision, design, execution and delegation owners identify the determining population, mechanism, model or interface; obtain the discriminating observation or smallest real calculation; and carry the result into dependent work. Unaffected completed work remains reusable. Required instructions, deliverables and verification retain their authority and coverage. No separate agent, state system, checker, estimator, wrapper or runtime dependency was added.

The comparison baseline is mini `3975116892cc443a71f7bc4c3244f52e294da45b` and full `43c8a466300df1e0519881aaec0afcf91f8d0f49`, both version 0.10.0. The following comparisons used the same inputs and actual entry points before and after the change.

| Observed operation | 0.10.0 | 0.11.0 |
| --- | --- | --- |
| New data pipeline or code-change export | Omitted the existing execution entry/dependency and output/failure bodies | Includes both bodies in flat and deployed exports |
| Compound mini CI change | Four pytest processes for four affected suites | One pytest process retains those suites and includes the existing configuration suite |
| Corresponding full CI selection | Selected a mini-only test absent from the full repository; exit 1 | Selects the full repository's existing suites; exit 0 |
| Two routine `make sync` calls | Ten privileged filesystem calls and two installer calls | Zero privileged calls and the same two installer calls |
| Kernel registration in a relocated checkout | Failed at a fixed `/workspaces` path | Resolves the project from the script and reaches Python/R registration |

The CI and environment comparisons executed their real shell entry points with controlled external executables that recorded operations and injected failures. Installer failure, missing R kernel and pytest exit 19 remain failures. Container-volume ownership is established in the existing initialization script; routine synchronization runs as the current user. Existing lockfiles, dependency declarations, cache volumes, pre-commit controls and instruction entrances are retained. The measurements establish operation selection and failure propagation; container builds, dependency downloads and hosted-CI elapsed time were outside this comparison.

The prose integration changes content selection before word editing: retain the proposition, evidence, causal relationship, quantity and action needed for the reader's judgment, and remove content serving rhetorical self-protection. Eight existing semantic criteria had described the defect in imperative form, including instructions to add concessions or replace a concrete request with generalities. They now direct the removal or reconstruction of that defect. The 142 lexical records, all 22 semantic IDs and names, required actions, instruction precedence and prohibition on rhetorical exceptions are unchanged. Existing writing modes and integrated review own this work.

Direct specialist-package calculations exercised consequential method choices using declared synthetic models:

| Decision quantity | Incompatible calculation | Matching calculation and result |
| --- | --- | --- |
| Two-product merger, homogeneous logit, marginal costs 1, transaction cost 0.1 | Fixed-demand price approximation: incremental profit −0.4397878760; pricing-equation residual 0.2290854151 | PyBLP 1.3.0 equilibrium: incremental profit +0.0769388033; residual zero at returned precision |
| Profit at the new equilibrium | New prices with default baseline shares: 1.7791524025 | Explicit new prices and recomputed shares: 1.3748225282 |
| Expanding participation beyond the instrument's observed margin | Treat historical LATE 1 on (0.2, 0.4] as the new-margin effect | Two compatible response curves imply net policy values +0.2 and −1 on (0.4, 0.8]; the determining unknown is the new margin's mean effect, with boundary 0.5 |
| Finite tax change 10 to 30, demand 100 minus tax and external damage 15 per unit | Extend the initial welfare derivative across the full change: +100 | Integrate the derivative along the path: −100, comprising external benefit 300 and extra deadweight loss 400; tax transfers cancel |

The merger uses two separate firms at baseline, one owner in the counterfactual and market size one. These comparisons establish calculation behavior under the stated models. They do not estimate an empirical market effect or a model-level behavioral improvement rate. Design and data instructions now trace the economic quantity through identifying support, package arguments, returned arrays and the action threshold before extending dependent analysis.

Separate fresh agents used the same synthetic board-decision task and saved their initial and updated Japanese memos. Both versions selected B at total incremental profits A = 12 and B = 21 million yen, retained the 120-million-yen capital budget and rejected the infeasible joint project. Both calculated the switching boundary at an existing-product contribution of −32 million yen. When the authorized input changed from −41 to −27, both updated the saved memo to select A at profit 26 versus 21, with an 80-million-yen initial investment and the responsible manager's next procurement-specification action. Existing population, horizon and cost definitions remained intact. This comparison confirms the observed decisions and completed artifacts in both versions; no general behavior-improvement rate is inferred.

The two corpus indexes assigned a consulted paper to different partitions. The new rule and example additions depending on that paper were withdrawn. Existing adopted analysis instructions remain intact. No unseen-paper evaluation was run or used for this release.

The existing state mechanism was also exercised on the same 33-call sequence in both versions. Both rejected all four proposed omissions of the original request, active instructions, adopted decisions and objective; rejected parent completion without the final requested file; resumed with original context; and completed both artifacts. Initial, middle, post-compaction-proposal, resumed and final observations retained parent and child context. Each version computed the analysis once and required zero unnecessary child reassessments. The analysis and recommendation hashes match the 0.10.0 comparison below. This run confirms preservation of the existing resumption behavior.

Nine existing configuration cases passed with three added regression methods covering the changed entry points. Two existing exporter methods exercised the two changed conditions in both formats and all thirteen operations across five owners. Two existing equity cases executed demand recovery/ownership equilibrium and the steady-value/share-unit/holding-return bridge. Validation reuses these results and the actual generated packages. Public operational instructions contain generalized original procedures; development provenance remains in the root notices file.

## 0.10.0 changes and measured evaluation

Version 0.10.0 connects evidence-derived parent claims, reader-dependent content selection, project decomposition, delegated results and resumption through the existing owners. The common writing path now distinguishes the premises needed for an inference, derives an informative parent proposition from its supporting relationships, and returns a missing comparison to its analysis owner. Proposals, research explanations, progress reviews, discussions and oral explanations select information by the recipient's actual judgment. Multi-stage work connects the current answer, supporting propositions, producing operations and accumulated outputs. Fixed requirements retain their original authority; delegated analytical choices can change on evidence within their adopted switching condition.

The state helper now keeps governing context revisions beside its existing requirement history. Removing or replacing the original request, active rules, fixed decisions or governing objective needs the already-given user instruction bound to the old and new context. A delegated decision uses a new version and saved evidence for the unchanged switching condition. This is retained declaration and content identity, not signed authentication or automatic semantic validation. Progress updates, identical rebinding and additive references remain usable. No separate framework, management ledger, production agent or runtime dependency was added.

The comparison baseline is `f35e8d13d6f9fe523539c51636572a46deb89752` (0.9.0). The same real CLI sequence registered the original sources, calculated a child result, bound the parent's consumed output, interrupted the task, proposed four lossy context updates, resumed and completed both requested files.

| Observation | 0.9.0 | 0.10.0 |
| --- | --- | --- |
| Updates deleting the request, active rules, adopted decisions or objective | Accepted 4/4 | Rejected 4/4 |
| Resume with original context after those proposals | Exit 2 | Exit 0 |
| Parent and child context after proposals and at resume | Replaced | Original retained |
| Unnecessary re-completion of the child after restoration | 1 | 0 |
| Parent completion without its final requested file | Rejected | Rejected |
| Actual analysis computations | 1 | 1 |
| Final analysis and recommendation | Both completed | Both completed; identical output hashes |

The changed implementation retained the original context at initial, middle, post-proposal, resumed and final observations. Analysis SHA-256 was `aece227ae60b5e60f83abc86871cf7305a462ee78f966af4ea9641781792a817`; recommendation SHA-256 was `ead8d573fe1ed141d14404420cf3e7a5a40a0801189ede8fee415a64c9cdfdba` in both versions. The sequence used 34 versus 33 CLI calls and took 2.203 versus 2.101 seconds in one local run. These timings are descriptive, not evidence of a general speed improvement. The sequence reproduces a compaction-boundary failure; it is not an hours-long model-success benchmark.

A second actual distribution comparison found that the old `resumption_active` export omitted the already existing Governing context section. Registering that section and its dependencies now includes its original-source restoration and revision instructions in both flat and deployed exports. The standalone flat export still contains ten files. Delegation also selects the existing Return and integration body. This repairs access to the rules rather than adding another rule owner.

Separate fresh agents executed the same synthetic business-analysis task with the old and new implementations. Initial evidence left onboarding channel shifts unknown; both computed the action-switch boundary at 90 customers without inventing a measurement. Reconciled evidence then supplied 105 shifts. Both selected discount: 60 genuinely new customers and net contribution 40 thousand yen, against repair's 55 customers and 10 thousand yen. Both retained the 1,000-person denominator, one-year horizon, 120-thousand-yen budget and all four alternatives, with the 180-thousand-yen combined option infeasible. Fresh workers then resumed from a secondary handoff favoring the wrong gross-uptake comparison. Both recovered the original contract and saved evidence, retained discount, and delivered executable scripts, CSVs and Japanese memos (260 and 313 characters). Final CSVs and memos matched each implementation's completed phase-two outputs byte-for-byte. The changed implementation retained its initial context and its evidence-bound delegated-decision revision in the existing state helper. This development task demonstrates preserved decisions and usable artifacts in both versions; it does not establish a general model-quality improvement. Restart used fresh workers, not an observed host compaction.

The existing state suite passed all 60 tests, including three added regressions for consequential context loss, authority/evidence-bound revisions and intact resumption. Three selected exporter tests and the existing equity suite ran 19 cases: 15 passed and four optional-dependency equity cases were skipped. Source and deployed instruction links have zero failures. No unseen paper-corpus contents or evaluation results were used to create the rules; the existing discovery/counterexample/unseen separation is preserved.

## 0.9.0 changes and measured evaluation

Version 0.9.0 connects the central economic issue and obstacle to the next comparison, calculation or execution step through the existing runtime and specialist owners. Source assessment distinguishes an organization's claim from its underlying observations, and method selection preserves the adopted estimand and requires a matching specialist implementation. Completion uses returned execution status and the requested output. Existing writing, valuation, export and synchronization responsibilities remain in place.

The comparison baseline is `426c54731a017aaedb7b5cbf5d008431b2b7f55c`. The old and new state mechanisms received the same six inputs. The old mechanism accepted all six: a success string without completion evidence, exit status 1, a running operation, `isError`, a result for another target, and a successful exit status 0. The new mechanism rejected the first five and accepted the successful exit status 0. This comparison establishes the changed acceptance behavior of the state mechanism.

Separate fresh agents applied the old and new rules to the same four development tasks:

| Task | Observed outcome in both versions | Additional observed difference |
| --- | --- | --- |
| Policy choice | Reject the intervention with aggregate net benefit of minus JPY 550,000. | None in the selected action. |
| Price competition | Choose the dominant price of 10, yielding profit of 200. | None in the selected action. |
| Estimator and package choice | Preserve the adopted fixed-effects OLS specification for the count outcome and reject an unsupported DRDID argument. | The old answer leaned toward custom implementation for the auxiliary estimate; the new answer prioritized a specialist implementation matching the doubly robust score and inference. |
| Independent product judgment | Choose B; retain B under pressure without new evidence; switch to A when new measurements change the comparison. | None in the selected actions. |

Both versions answered all four development tasks correctly. The observed package-selection difference concerns the proposed next implementation step; it does not establish that the auxiliary estimator was executed. These single-run tasks do not measure a general improvement in model ability. The existing 100-paper corpus's unseen partition was not used. Two existing stock-valuation tests also passed.

A separate numerical execution directly used the installed scikit-learn 1.8.0 `PoissonRegressor(alpha=0, solver='newton-cholesky', tol=1e-12)` and `LinearRegression`, adding no dependency. The eight-observation nonnegative count sample retained both zeros and had group means of 1.5 and 3. PPML returned a group coefficient of `0.6931471805599455` (absolute difference from log 2: `2.22e-16`), a mean ratio of `2.0000000000000004` and a score residual of `4.44e-16` after five iterations. OLS returned the level difference of 1.5. The fits took 0.134 seconds in total, and the saved sample, fitted values and result were reread. This run verifies point estimates; it did not perform fixed-effects absorption, cluster-robust inference or causal identification.

## Distribution and settings contract

Read this section only for requested export, installation, synchronization or configuration work. The [operation registry](../../registry/operations.json) defines modes and conditional rule selection, the [resource registry](../../registry/resources.json) defines logical resource IDs and rule dependencies, and the [placement registry](../../registry/placements.json) defines physical locations and export aliases. Use the registered resource IDs and the selected layout when exporting or synchronizing. Read the relevant command section and its supported options. Compare common inputs at batch boundaries and each destination immediately before writing; do not reread every unchanged input for each target.

For an export, select CORE, the final operation and its activated support/resources. Include only sections needed by those operations. Short prose does not activate whole-paper instructions. Resolve every active mandatory reference inside a standalone package. An omitted optional capability becomes an additional input if later needed; do not turn it into an automatic remote-repository fetch. Resolve resource paths through the declared placement and export aliases. Check required files, references, unique output names and requested size limits before producing the complete package in a new destination.

The configuration interface defaults to a diff, changes only explicitly selected clients or adopted project targets, and rejects unknown arguments or incompatible modes before writing. Read every selected destination and required input, then assemble all intended changes. Include devcontainer only when selected. Resolve relative paths from the command's declared project root.

For each generated setting, compare the previous generated content, current content and proposed content. Update a setting only while its current value matches the previous generated value. Preserve manual changes and mark the item manually owned. Recheck content immediately before applying and preserve detected concurrent changes. The helper uses per-file atomic replacement with optimistic rereads. Coordinate other writers across the final read-to-replace interval. For a caught multi-file write failure, roll back only content still matching this operation's writes. A process crash requires inspection of the actual destinations before resumption. Legacy name-only ownership records do not establish content ownership; preserve those entries until their ownership is resolved.

Reference secrets through existing environment or approved storage rather than embedding them. Required configuration or installation failures must propagate as failures with the affected targets. Preserve successful work, diagnose failed items and retry only the affected operation. Report the returned statuses; an instruction to perform an operation is not a successful operation result.


## State migration

Use explicit capacity, depth or attempt limits only when the user or runtime supplies them. Migration preserves saved outputs, bound check receipts, usage, holds and limit provenance. A legacy task lacking declared deliverables retains an unresolved completion contract; recover the request and use set-contract rather than infer requirements from whatever output exists. Previously completed tasks with an unresolved contract become blocked while their results remain saved. Legacy permission/user-hold reasons without an identifier receive an identified legacy hold. Perform missing required operations against preserved current results; migration does not rerun calculations.


An old evaluating state maps to running; interrupted maps to blocked with blocked_reason=interrupted. Schema-v4 migration preserves outputs, check receipts, authority, holds, attempt counts and usage. Where recorded consumed inputs identify one parent output unambiguously, migrate to that explicit consumes edge. Otherwise retain the legacy dependency set as a compatibility group until the next relevant operation establishes its input contract; never erase it or guess a narrower dependency. Migration alone does not invalidate numerical results or rerun completed stages.

<!-- common-core-receipt:v2 -->
```json
{
  "schema_version": 2,
  "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
  "source_base_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675",
  "source_state": "committed",
  "common_content_id": "3bad28d5be1a2ad4fcd8f3eb18a6823d40bae0317d79036b8f2a3c84630e1596",
  "target_repository": "github.com/yoshimurahiroki/econ-project",
  "paths": [
    {
      "path": ".agents/AGENTS.md",
      "state": "present",
      "sha256": "b77c32844cf532a12f44e2ce59fb40224f8507877bfc703b8b5df9862abd341f",
      "git_blob": "60285886b26c2f19a65dd579e977614a442a1dc0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/argument.py",
      "state": "present",
      "sha256": "fbf3b34c3febd21208526e44b6494ea543b10e3d011c2e05950192226a655909",
      "git_blob": "1829e3fee0a056fbf1fd95ee08017b112e0195bf",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/argument.schema.json",
      "state": "present",
      "sha256": "3bde57438e6fe255e7cd3a525bfe0b9b4ade8f4c2eae2a41fe1850bf41e7a013",
      "git_blob": "4397bb0feed6a22c198025f3789fad2f77b44503",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/codex_hooks.py",
      "state": "present",
      "sha256": "af49379b64dbb776ab5e8c5b8ae12f8f51dbb2c774e26a19a57f644cfb8ea320",
      "git_blob": "899761c5cbc028c091a5bf7ad07ccf37ee0dd967",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/local_checks.md",
      "state": "present",
      "sha256": "603abd9deed49956c29f6e5ef3f1ab66fcd6497ca5ba77ececb773cab81f3d6b",
      "git_blob": "eaa513b2816c2d906b4fb2edfd64fbfd4fb99f07",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/local_checks.py",
      "state": "present",
      "sha256": "27545f9a3d73839ea162e7eef474bdd206037469baed560cd6daa745d2075194",
      "git_blob": "d9878828561f770ebec1ecf24076884e7337652d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/native_check.md",
      "state": "present",
      "sha256": "0e1e220a0d84bc9130c24302d9a09bdcca11e2c4d49927b88cbfa9a7516ca069",
      "git_blob": "ba4278b1d8fefbc4c4f9bc32393d66eaff8e4b20",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/native_check.py",
      "state": "present",
      "sha256": "efadb90fd74173bbe85452c18e7527dbe845dfeaa3b32c551860d0af039a5099",
      "git_blob": "015aa93da026a9c1ad8b1276f2eacdfb4016038c",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/native_run.md",
      "state": "present",
      "sha256": "901399703c82a0dbc606c8277fa337d46ff47b2ed6e7b0076c4a09184e2bb83b",
      "git_blob": "6574ba806e2bbbdec6d62f4db021d4e0d59f2a28",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/native_run.py",
      "state": "present",
      "sha256": "5a626d88017a0a155fc88b165bd54c7d8530960f6aa1ab427e4bbcca64dc18e9",
      "git_blob": "175fd933a3d387becb69e104f4167878d018dae0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/paragraph.py",
      "state": "present",
      "sha256": "9aaefb9fbfa4904f1682ad64a10689fc28deeb15de26a1baa9e6b748dd7a3764",
      "git_blob": "0bf963a49903f192b1a5e86c86e232083be1ca33",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/paragraph.schema.json",
      "state": "present",
      "sha256": "1bc8fd4382a7861bf0c8905b5c5b7b39ececcf25083cafba0fe81e9d83936df0",
      "git_blob": "1765fb6ee780b4f3e9be04a3479aab3d92c82b75",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/policy_assets.py",
      "state": "present",
      "sha256": "a9cc4bd338a770b13c1800ed0cd50a487f1121ff2233f4ce94c31c85c2dde3c5",
      "git_blob": "9514dac3a89279d079ffa27e4f24a03b6877f857",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/publication.md",
      "state": "present",
      "sha256": "179d3510f823308e1d4d0d7afdbbc698de4dac6f8a8d5490c580bf8dacd1b9ad",
      "git_blob": "d31793e539faf12ae5f148b6002073751b753f5f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/requirements_check.md",
      "state": "present",
      "sha256": "4275b227742dee85a9c1bda1c070e3d37041c8789a111568e27be7def5fb7cb4",
      "git_blob": "c48d312d04fba435bedc2ea2cab308323675b5c9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/requirements_check.py",
      "state": "present",
      "sha256": "3586e6170d23c77080647f88cd6c09026e11c45835b2e92e318ac91683bf8747",
      "git_blob": "e29565611e61184c4bf5895da6ce1d6aa635a2f2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/state.md",
      "state": "present",
      "sha256": "d2682811664eafd4f26308f0650662960ec561ce00617a8bc83d75f16e29700f",
      "git_blob": "85459c159d87b3ae05cbf95858f2a039a594ab95",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/state.py",
      "state": "present",
      "sha256": "ad37cdfcff61f78d05bcb5b11ffba9dc53142304056d47be28a63feceed9efa3",
      "git_blob": "3a114c4cd602c08052d2bdffc1adcd4a0619e11d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/harness/test_state.py",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": ".agents/profiles/default-micro/PROFILE.md",
      "state": "present",
      "sha256": "4f2dcd24e60ca79ea7d7753aacabc1b541782ec30cf4f6afbaa149f51c8dba9a",
      "git_blob": "349dbbd4c0c63a6e99cc4beb7b9c100317f8e402",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/profiles/default-micro/extended-introduction-en.md",
      "state": "present",
      "sha256": "0b1d9f9511b5d32cc935c4d7c75b24bf01f94ef48f1ec7b330218d508e810b34",
      "git_blob": "834688a8d352f80a6ac4cc0b96fbe4f831dfad74",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/profiles/default-micro/extended-introduction-ja.md",
      "state": "present",
      "sha256": "cb49bab9fbb949538056f82e7560d715a3a6c648f663ea14af2b77e833bec03b",
      "git_blob": "84c9e720bfec8a585613ed516f91047c9c5f78bb",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/profiles/default-micro/short-examples-en.md",
      "state": "present",
      "sha256": "e395b60c46f6ba98e614bdab1b118ead92e7ca05560641d43ba5b75a8c83a08b",
      "git_blob": "9fafab070f78b4299f8c8611f4c3083e6514497e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/profiles/default-micro/short-examples-ja.md",
      "state": "present",
      "sha256": "4147294992356f95fb21d7484164ff56cf9adae9919d1fd1e989eb911ae05fa2",
      "git_blob": "1953cb16b796b7001b9be33f7c3804fc3fc87a56",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/quality/policy_manifest.json",
      "state": "present",
      "sha256": "e760c590fc0b81b789ff7918863fac5ff2a6de0881ff4ff72405dba04971e765",
      "git_blob": "1dea7669adeb9db63f78524beee0102c732be2c4",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/quality/prose_rules.json",
      "state": "present",
      "sha256": "2c06436dbd009176a34a039566d28e01ae2de4aa989517e17faed51648b5e976",
      "git_blob": "cca7852d21bdb64ec911db5e5b106962eb3a48a6",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/quality/prose_rules.md",
      "state": "present",
      "sha256": "d670453bf00c8348254048619bdb686127f87cc2a6f5e87eab6a538dce5b109f",
      "git_blob": "5bb1831db0292e17f7d6322b018a15e86c0f912f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/registry/operations.json",
      "state": "present",
      "sha256": "397729c65e0785a47e1ca2816cba98462dac42fe67edbfb01dbe55b51cbf3303",
      "git_blob": "9c39c1aef4d994125c89ac26374fe631d3a48924",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/registry/placements.json",
      "state": "present",
      "sha256": "5048f354f65d521af13b1f0cbab438f2e75a9e2fe9560c7f40ffd14169aad8fb",
      "git_blob": "4255d00970003a2271c7d9e00dd4c92913c067b1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/registry/resources.json",
      "state": "present",
      "sha256": "6fe25c3f6bcbbe2ed2bc2ba5449c4926334c89c50055592c98fc38321ed965aa",
      "git_blob": "0450fa060908aff356bdcdc01c8415ece15098a8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/runtime/CONTROL.md",
      "state": "present",
      "sha256": "12876572098fa24bcbc59b20bdfada46032cca1a591ed4009143fdc3ace9c914",
      "git_blob": "a030b8bd8cafedf48f197bdf08cd3e5a961154b8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/runtime/CORE.md",
      "state": "present",
      "sha256": "3d4b7fb302e4e9f6cbdb7b3cd1c136eb47aeaa2e65eba06611427931cd1b8eed",
      "git_blob": "be776d659d37adf09a0625673ead69699b13d85e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/runtime/DECIDE.md",
      "state": "present",
      "sha256": "a3a356a0526a5a15d7af0fc98df7ffaf11dde6bd1bb80783a54bd4b5fcfaedd1",
      "git_blob": "f477318bb1eb933bdf37d052dca200932bc952f9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/runtime/EXECUTION.md",
      "state": "present",
      "sha256": "2217bd88ce704af81a0607b79cc2f1585b7ba3c0fea3a2cbd0358574bf856b02",
      "git_blob": "a1ee28202a60039337ca2f56f2245718e1726082",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/runtime/PROSE.md",
      "state": "present",
      "sha256": "75b00f636021fe247eafd8757de565269dcd0fe5bf27774546b1dabc73144ccf",
      "git_blob": "f1b8fc0aed2a09af4a38156967e84ed03b37fb59",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/runtime/TEAM.md",
      "state": "present",
      "sha256": "c223ceb5335605e57980c95549e2225f17966b5c06bb58f5894de6aec4a191c4",
      "git_blob": "759e87ec9695bed8f991b88904e5e8c13fcef317",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/scripts/route_registry.py",
      "state": "present",
      "sha256": "ded7428176104de0c6699effbe52d112c3fea2622a8db94146b88bf8e584b851",
      "git_blob": "275ebcb8627def49d2871ca21607eab1c7423a3f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-assertive/SKILL.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-assertive/agents/openai.yaml",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-assertive/references/default-micro.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-assertive/references/patterns.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-data/SKILL.md",
      "state": "present",
      "sha256": "5c958cf2db7db75548feac1fab928697974ce12b31591821f0d6da8825266f55",
      "git_blob": "f5679aa42bbfcba6b196030bbe1f2403bee83109",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-data/references/equity-case-results.json",
      "state": "present",
      "sha256": "62b1020b7bb0a1d43d9379dfd2bfcd724498d51aa64cb629d3a47182d8ab53a1",
      "git_blob": "65a01990e86791bf438c4a4004ad11f3c7707e14",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-data/references/equity-models.md",
      "state": "present",
      "sha256": "ad421aae45765b1d5ab19928ad59cc1fe69085a3a94548f6ce4dd54827f6421d",
      "git_blob": "3cf2de32d0d41114c7e2bc2e9afdd22f0df48971",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-data/references/equity.md",
      "state": "present",
      "sha256": "b819613bf397adb5df04d58644b3c87a6285faccb16507e9c4c90e369cb8e741",
      "git_blob": "b6075835e6eee963c6de0a0d27d7fd9024938b44",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-data/references/implementation.md",
      "state": "present",
      "sha256": "32780684281587ef5a4a70354ff8f9419c71b58d706df28f73eea3ce6d2bcff6",
      "git_blob": "170e6c43f91d481937c41a0803daf6009f80b170",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-data/references/reproducible-workflow.md",
      "state": "present",
      "sha256": "df32a3213d9a247cd12a7f69b8cf132f0c9203556c80245a3227bd7b453d7e95",
      "git_blob": "477c31ee83d48fb942846cfcfec5dd09736ebe60",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-data/scripts/equity.py",
      "state": "present",
      "sha256": "bbad37392cc248f4a886b5a5ec62b430b7db16194893c3c21cae03f2b649a357",
      "git_blob": "df6f809760b0209e3c7a03c0592be0ba609ba32e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-data/scripts/equity_airline_case.py",
      "state": "present",
      "sha256": "86ae7c9184ceb418d388b876d1f0d691d3dd2c56db0ef24a8a5c2f24962b6d37",
      "git_blob": "a3b77b4f6ce369c889858e02175db23d3171cf19",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-data/scripts/equity_company_case.py",
      "state": "present",
      "sha256": "4438db3ebe34a80111296032ab5ef0ccc743759d2acaa4e850943971b9f7dea4",
      "git_blob": "ee7acfdd92fc3e39d6ae98d682efd16eeb8e1ba4",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-data/scripts/equity_io.py",
      "state": "present",
      "sha256": "2cecd52b064c7c087bcc0c5fb9367f34dbaaafe81878425cc21779677714453b",
      "git_blob": "23b2159052f8e7655035a5af92a34ecede713d0f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-data/scripts/equity_sources.py",
      "state": "present",
      "sha256": "c9a19d58db9ce4d91401d153d5427b90ed10ad5ce0b0161c60d699f545cf9376",
      "git_blob": "43290d859ede730bac639dae89dce24799064e8e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-data/scripts/requirements-equity.txt",
      "state": "present",
      "sha256": "5f7ec2a7f299c62968db977bba260c91cf9e0bad20ed855e5d429ee4814bf627",
      "git_blob": "c2d6b5d234c8e846449217df41bae0b9353c2ea5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-design/SKILL.md",
      "state": "present",
      "sha256": "1f551acace7ee0465088a1c4d165ae0ebe378c755d3123a4408f74ae8cb2a4a0",
      "git_blob": "9da70c152ed73f2ea7e8c4f9c0129572bc638559",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-design/references/designs.md",
      "state": "present",
      "sha256": "e663eaf0fcbb76563584d8da4b2923e3ab994bf960d82a876b775a6929940911",
      "git_blob": "edef7f438c871553aa88be140869b1a57528c21e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-edit/SKILL.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-handoff/SKILL.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-handoff/references/handoff.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-literature/SKILL.md",
      "state": "present",
      "sha256": "0731eac6b0eeea9257a865b4de562b0cc307c0d46c2315b55073219dcbde8149",
      "git_blob": "e32707c79bae522d0d89555e84749067b3c2e9bd",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-paper/SKILL.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-review/SKILL.md",
      "state": "present",
      "sha256": "135eeb6202776212af47201c9131ed05d680b14c2018abb5b9cb863addca7cc4",
      "git_blob": "2b7a2055152610e41e19e3fc6c78da24b8e83994",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-review/references/oversight.md",
      "state": "present",
      "sha256": "808f85d34009f54760e801e76f16449d04f02efe16e7cccb5b8a13a4d8c7e2b0",
      "git_blob": "614e1b6e653d1debc94a230d2f567ffe7260e60f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-style/SKILL.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-workflow/SKILL.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-workflow/references/descriptive-model.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-workflow/references/team-execution.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-workflow/scripts/team_state.py",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-workflow/scripts/test_team_state.py",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "b0ec2ae8723d872f0d502a07c9d264c836c7c02a"
    },
    {
      "path": ".agents/skills/econ-writing/SKILL.md",
      "state": "present",
      "sha256": "34831fd2c93a844619889b0a18d3053f12a6967c27cb4a82dc1295dfbc6c42da",
      "git_blob": "02eb76eca25c0aef577345fa78b62417301894fc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-writing/agents/openai.yaml",
      "state": "present",
      "sha256": "dadd933a3fd861e194ac4df3dff3b8912874b72ffad11768719b8776f4a123a6",
      "git_blob": "d3214f8ae4e43308c30f96f8577c1696f43a068c",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-writing/references/paper-workflow.md",
      "state": "present",
      "sha256": "737f7bf096eaf1e780a8b8215ba4cbf24d013d5e6b01484cdcb8f21c996cebfd",
      "git_blob": "9aaae68a5e325df34aa0917ee358567308c7ae3d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/econ-writing/references/paragraph-workflow.md",
      "state": "present",
      "sha256": "3c9d2f5f55e8c736ec33da83eadf88505d16cc68b3ea219d7a7d075d8e4e1433",
      "git_blob": "afa820c2d02db03832d1db6268935ffd594190e6",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/economics-checked-instructions/SKILL.md",
      "state": "present",
      "sha256": "1ce58690297b9a393cdb37c5b82858d7a92a49e61abf01a4e00434e5b44a670d",
      "git_blob": "d9ada92182e0b0a08d333f0f54ae35dc38e2917f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": ".agents/skills/explain-before-shorten/SKILL.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": ".antigravityrules",
      "state": "present",
      "sha256": "fa365dbe72fded587175a9ef85d322a8735335c6f82467caa3de5c180d3dab89",
      "git_blob": "326ecadfaa660ff940e1ef3fe4db83733ed3db18",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": ".claude/AGENTS.md",
      "state": "present",
      "sha256": "5c0fec1706f7be5aebaa626285f92eb38f315828bebfac7246dc3d8a5f85d6a4",
      "git_blob": "aa9e020d3378864015084cd2c90c2eff41a16e1f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": ".clinerules",
      "state": "present",
      "sha256": "fa365dbe72fded587175a9ef85d322a8735335c6f82467caa3de5c180d3dab89",
      "git_blob": "326ecadfaa660ff940e1ef3fe4db83733ed3db18",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": ".cursor/rules/01_project_policy.mdc",
      "state": "present",
      "sha256": "df36821ad2582cfcf411c4f54fef7a976086ac7787d3277a3b6adbd5f742155a",
      "git_blob": "60e2ceb36ae546786126798170c97e48b9a9c7f1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": ".cursorrules",
      "state": "present",
      "sha256": "fa365dbe72fded587175a9ef85d322a8735335c6f82467caa3de5c180d3dab89",
      "git_blob": "326ecadfaa660ff940e1ef3fe4db83733ed3db18",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": ".gemini/GEMINI.md",
      "state": "present",
      "sha256": "5c0fec1706f7be5aebaa626285f92eb38f315828bebfac7246dc3d8a5f85d6a4",
      "git_blob": "aa9e020d3378864015084cd2c90c2eff41a16e1f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": ".github/copilot-instructions.md",
      "state": "present",
      "sha256": "5c0fec1706f7be5aebaa626285f92eb38f315828bebfac7246dc3d8a5f85d6a4",
      "git_blob": "aa9e020d3378864015084cd2c90c2eff41a16e1f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": ".windsurfrules",
      "state": "present",
      "sha256": "fa365dbe72fded587175a9ef85d322a8735335c6f82467caa3de5c180d3dab89",
      "git_blob": "326ecadfaa660ff940e1ef3fe4db83733ed3db18",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": "AGENTS.md",
      "state": "present",
      "sha256": "3996b26a2f42294c5fdf46f96010132dc12916bea694ebcc7d6615fd1bb53585",
      "git_blob": "6a9cead3204d6dcabf1ca0a629f99707d9015257",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": "CLAUDE.md",
      "state": "present",
      "sha256": "fa365dbe72fded587175a9ef85d322a8735335c6f82467caa3de5c180d3dab89",
      "git_blob": "326ecadfaa660ff940e1ef3fe4db83733ed3db18",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": "CODEX.md",
      "state": "present",
      "sha256": "fa365dbe72fded587175a9ef85d322a8735335c6f82467caa3de5c180d3dab89",
      "git_blob": "326ecadfaa660ff940e1ef3fe4db83733ed3db18",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": "ECON_INDEX.md",
      "state": "present",
      "sha256": "a9b049648e59a8820fa0d1abb57dfb75fb3afa8354dcebca6c232b02f767dec9",
      "git_blob": "58f6472c6b6c29ba94948f014adaa441b3f8bac9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": "OPTIONAL_INPUTS.md",
      "state": "present",
      "sha256": "05beda72fa1a29cc076f3a28f990698b5cee794138c121a329e856a4a07b582b",
      "git_blob": "49216868e2c06fec50052a9086de3678d3651758",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": "PROJECT_INSTRUCTIONS.txt",
      "state": "present",
      "sha256": "8b41128278556f3072d5714143a5029363541a33e3e6485cfbbf7147b5f6191b",
      "git_blob": "e58b754ebf14c9df87b4ab165afa5540a499a14d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": "THIRD_PARTY_NOTICES.md",
      "state": "present",
      "sha256": "ff8d9b56579c8e46d36aa1fc503e08a13b346d627a11863330d6565b3c4f8b14",
      "git_blob": "78c9d5b1ec677c166c30a5c71f310efff43d8b63",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    },
    {
      "path": "docs/ai/compiled_ai_skills.md",
      "state": "present",
      "sha256": "31ab66bb1af928ebbc0bd0befe3a646c229382c15223dced5955479a0ecc0afb",
      "git_blob": "39aba34611f4f34b2ab016c21b62e2c592595c17",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "docs/ai/config-templates/README.md",
      "state": "present",
      "sha256": "79d77ee0cffd70c04ef4884485ed124a21d83aba0786a7054c132d75950dfa87",
      "git_blob": "97ec119bcae6bac54dc9b0f39a8208709100a410",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "docs/ai/config-templates/claude-mcp.example.json",
      "state": "present",
      "sha256": "7e098a33b20cda19ae9067ffc8252f2637bf0314963893df85110fe3120fee63",
      "git_blob": "e29ee95ea2e7cdc213561f0a75252c43d28d51de",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "docs/ai/config-templates/codex.example.toml",
      "state": "present",
      "sha256": "c57023f63a938b1d62c9c66f5d6f6c0dbb001e496aa9813bbf3d6a5980e38b05",
      "git_blob": "be298aabfb36b8954160f39686750a294dad8527",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "docs/ai/config-templates/mcp.example.json",
      "state": "present",
      "sha256": "d8e397af03b5b032f21d0aa967086f0c78b33c87b76f2e9898ae0a144df7de02",
      "git_blob": "da39e4ffafe816be90259a3f68b763a3f71b93ed",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "docs/ai/plugin-integration.md",
      "state": "present",
      "sha256": "194b8d2b5d093a914b2483f44cc65ae2ebca5deb365fa87e04074c5b1c4a961c",
      "git_blob": "48de612d69a557dd975531e64366acca8020e24d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "docs/ai/project_bridge.txt",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "fd9af45e1aa67a2ec9d01757a2a358abdf98c0f4"
    },
    {
      "path": "docs/ai/project_instructions.txt",
      "state": "present",
      "sha256": "006c11beaea72cdc43e3805cb39d5cc83b9fe4e9021b6d2cc495207c1bd43336",
      "git_blob": "21fb364c65f735029a0a273a558e1cfd07570336",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "docs/ai/resources.md",
      "state": "present",
      "sha256": "c7b1f6ef433d17846072877b691bbb7aa8db7ca7f672884116213cf944573609",
      "git_blob": "0922a0b1884c6e994ec24be8a8d4a1b0a25f048e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/argument.py",
      "state": "present",
      "sha256": "fbf3b34c3febd21208526e44b6494ea543b10e3d011c2e05950192226a655909",
      "git_blob": "1829e3fee0a056fbf1fd95ee08017b112e0195bf",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/argument.schema.json",
      "state": "present",
      "sha256": "3bde57438e6fe255e7cd3a525bfe0b9b4ade8f4c2eae2a41fe1850bf41e7a013",
      "git_blob": "4397bb0feed6a22c198025f3789fad2f77b44503",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/codex_hooks.py",
      "state": "present",
      "sha256": "af49379b64dbb776ab5e8c5b8ae12f8f51dbb2c774e26a19a57f644cfb8ea320",
      "git_blob": "899761c5cbc028c091a5bf7ad07ccf37ee0dd967",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/local_checks.md",
      "state": "present",
      "sha256": "c9df41b68d1aeeefe2ed6a0c2fa5fdd6ec44da1348303e63f78f284dc1501984",
      "git_blob": "5d3e954c637ea95cd38cd47cb615708b02807d5a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/local_checks.py",
      "state": "present",
      "sha256": "27545f9a3d73839ea162e7eef474bdd206037469baed560cd6daa745d2075194",
      "git_blob": "d9878828561f770ebec1ecf24076884e7337652d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/native_check.md",
      "state": "present",
      "sha256": "eacc3099f79b450310dbcf11e87ca747218097f80d3e1fc08caa1095ffe131ec",
      "git_blob": "41982d375eef8611c0e61f3b7caf7e59901a7412",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/native_check.py",
      "state": "present",
      "sha256": "efadb90fd74173bbe85452c18e7527dbe845dfeaa3b32c551860d0af039a5099",
      "git_blob": "015aa93da026a9c1ad8b1276f2eacdfb4016038c",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/native_run.md",
      "state": "present",
      "sha256": "3ea1caa868d186fcc2b8a91a3d1f9a719b0ea89b6c6abdd90b9295a04556a14e",
      "git_blob": "5d536a372702c4712a24772a11ea0250c27b55f2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/native_run.py",
      "state": "present",
      "sha256": "5a626d88017a0a155fc88b165bd54c7d8530960f6aa1ab427e4bbcca64dc18e9",
      "git_blob": "175fd933a3d387becb69e104f4167878d018dae0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/paragraph.py",
      "state": "present",
      "sha256": "9aaefb9fbfa4904f1682ad64a10689fc28deeb15de26a1baa9e6b748dd7a3764",
      "git_blob": "0bf963a49903f192b1a5e86c86e232083be1ca33",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/paragraph.schema.json",
      "state": "present",
      "sha256": "1bc8fd4382a7861bf0c8905b5c5b7b39ececcf25083cafba0fe81e9d83936df0",
      "git_blob": "1765fb6ee780b4f3e9be04a3479aab3d92c82b75",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/policy_assets.py",
      "state": "present",
      "sha256": "a9cc4bd338a770b13c1800ed0cd50a487f1121ff2233f4ce94c31c85c2dde3c5",
      "git_blob": "9514dac3a89279d079ffa27e4f24a03b6877f857",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/publication.md",
      "state": "present",
      "sha256": "179d3510f823308e1d4d0d7afdbbc698de4dac6f8a8d5490c580bf8dacd1b9ad",
      "git_blob": "d31793e539faf12ae5f148b6002073751b753f5f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/requirements_check.md",
      "state": "present",
      "sha256": "73edc472d8c66deb1195d6300b9ee172da0690f743602ef2cc862e143c0a2961",
      "git_blob": "33b40573042e0393440803cb31f7f76e8faaddb2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/requirements_check.py",
      "state": "present",
      "sha256": "3586e6170d23c77080647f88cd6c09026e11c45835b2e92e318ac91683bf8747",
      "git_blob": "e29565611e61184c4bf5895da6ce1d6aa635a2f2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/state.md",
      "state": "present",
      "sha256": "a0beb2926ac0b6a21eb8eaf34ef2a7db012fae7d4749399e565f6ffc50c761d2",
      "git_blob": "b894508bdbcb942baf26b36801f863cd72127152",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/state.py",
      "state": "present",
      "sha256": "ad37cdfcff61f78d05bcb5b11ffba9dc53142304056d47be28a63feceed9efa3",
      "git_blob": "3a114c4cd602c08052d2bdffc1adcd4a0619e11d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/test_argument.py",
      "state": "present",
      "sha256": "7420df6fa26d35053705b125f983729dbb65d4a7b83215b91a8e6dc3a9dcdf69",
      "git_blob": "6dab28f613f2e0a492048e7bfa23294b66f30ce7",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/test_argument_regressions.py",
      "state": "present",
      "sha256": "1c60176c741a5f4ef5fb8b71d95d27fe369fb9f5e02713fd26c0108f38b87494",
      "git_blob": "d65bcef97ed3f1ea415134d65b6877e78e5bf4d5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/test_paragraph.py",
      "state": "present",
      "sha256": "ac8d59c80402903e982cdef2eb829a2f1a4211a16167fa13a956a66446be7a24",
      "git_blob": "5df8feb0e1bc2e41b7f054fafabe074a76d15362",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/test_paragraph_regressions.py",
      "state": "present",
      "sha256": "5ade200d1f981478571d52c8342a0b751b9a849dbaa0c94fb73bf5cf341b9b3a",
      "git_blob": "cca894667cbc3a898abdb64583dbb0d9f5433982",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/test_state.py",
      "state": "present",
      "sha256": "ea12840bedda1c772f9c1b6e42b44e691a5fa03150fe89478efc570c1573b664",
      "git_blob": "053f8f4375d9cce98948159bf475d837d82a1c62",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "harness/test_writing_integration.py",
      "state": "present",
      "sha256": "6e85956258fc3602115f3c887cb5c1df4c28097ad6cc8cec76114fbec9fc4ac6",
      "git_blob": "e592ebc2e5f621b9752fadc12b63a0464184e8cd",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "profiles/default-micro/PROFILE.md",
      "state": "present",
      "sha256": "4f2dcd24e60ca79ea7d7753aacabc1b541782ec30cf4f6afbaa149f51c8dba9a",
      "git_blob": "349dbbd4c0c63a6e99cc4beb7b9c100317f8e402",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "profiles/default-micro/extended-introduction-en.md",
      "state": "present",
      "sha256": "0b1d9f9511b5d32cc935c4d7c75b24bf01f94ef48f1ec7b330218d508e810b34",
      "git_blob": "834688a8d352f80a6ac4cc0b96fbe4f831dfad74",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "profiles/default-micro/extended-introduction-ja.md",
      "state": "present",
      "sha256": "cb49bab9fbb949538056f82e7560d715a3a6c648f663ea14af2b77e833bec03b",
      "git_blob": "84c9e720bfec8a585613ed516f91047c9c5f78bb",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "profiles/default-micro/short-examples-en.md",
      "state": "present",
      "sha256": "e395b60c46f6ba98e614bdab1b118ead92e7ca05560641d43ba5b75a8c83a08b",
      "git_blob": "9fafab070f78b4299f8c8611f4c3083e6514497e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "profiles/default-micro/short-examples-ja.md",
      "state": "present",
      "sha256": "4147294992356f95fb21d7484164ff56cf9adae9919d1fd1e989eb911ae05fa2",
      "git_blob": "1953cb16b796b7001b9be33f7c3804fc3fc87a56",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "quality/policy_manifest.json",
      "state": "present",
      "sha256": "a47d8ccd9e824b4acdc8d2dbf3ba83a5e8c736e74e1e1acb2a48800ea2275be3",
      "git_blob": "a722a1d07ef22f385041a5f6643f68894d824b6f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "quality/prose_rules.json",
      "state": "present",
      "sha256": "2c06436dbd009176a34a039566d28e01ae2de4aa989517e17faed51648b5e976",
      "git_blob": "cca7852d21bdb64ec911db5e5b106962eb3a48a6",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "quality/prose_rules.md",
      "state": "present",
      "sha256": "54fdf8a593eecfaa89f4e21dd92b460a3ff4edf61012fa8a7175b31ce2bdd78f",
      "git_blob": "4ed2886075d52e2e2e7e22f9ed313d934412e71d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "references/repository-policy/.agents/AGENTS.md",
      "state": "present",
      "sha256": "fb2ca850320584c3f1fff26993690ddcea651ab8d115c869b3b6718cdc127456",
      "git_blob": "d2dea0549d19641aebd5a1d5b76bd41644875c21",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "references/repository-policy/.antigravityrules",
      "state": "present",
      "sha256": "ef1eedb37cf47b56277e2e192b44e83d67c162adf88e2a0f6e027b892aeb3c7b",
      "git_blob": "1fd4bb7151310df632693e71c341dcab4b1d4f19",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "references/repository-policy/.claude/AGENTS.md",
      "state": "present",
      "sha256": "fb2ca850320584c3f1fff26993690ddcea651ab8d115c869b3b6718cdc127456",
      "git_blob": "d2dea0549d19641aebd5a1d5b76bd41644875c21",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "references/repository-policy/.clinerules",
      "state": "present",
      "sha256": "ef1eedb37cf47b56277e2e192b44e83d67c162adf88e2a0f6e027b892aeb3c7b",
      "git_blob": "1fd4bb7151310df632693e71c341dcab4b1d4f19",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "references/repository-policy/.cursor/rules/01_project_policy.mdc",
      "state": "present",
      "sha256": "f4275ca6376aa993e43bdb895a8c291bef7cf5c5c1590365b3487ccaa1a4e6c8",
      "git_blob": "6ce4b680f3f1c8f18c7b0acc853538c3a71b8e24",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "references/repository-policy/.cursorrules",
      "state": "present",
      "sha256": "ef1eedb37cf47b56277e2e192b44e83d67c162adf88e2a0f6e027b892aeb3c7b",
      "git_blob": "1fd4bb7151310df632693e71c341dcab4b1d4f19",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "references/repository-policy/.gemini/GEMINI.md",
      "state": "present",
      "sha256": "fb2ca850320584c3f1fff26993690ddcea651ab8d115c869b3b6718cdc127456",
      "git_blob": "d2dea0549d19641aebd5a1d5b76bd41644875c21",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "references/repository-policy/.github/copilot-instructions.md",
      "state": "present",
      "sha256": "fb2ca850320584c3f1fff26993690ddcea651ab8d115c869b3b6718cdc127456",
      "git_blob": "d2dea0549d19641aebd5a1d5b76bd41644875c21",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "references/repository-policy/.windsurfrules",
      "state": "present",
      "sha256": "ef1eedb37cf47b56277e2e192b44e83d67c162adf88e2a0f6e027b892aeb3c7b",
      "git_blob": "1fd4bb7151310df632693e71c341dcab4b1d4f19",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "references/repository-policy/AGENTS.md",
      "state": "present",
      "sha256": "ef1eedb37cf47b56277e2e192b44e83d67c162adf88e2a0f6e027b892aeb3c7b",
      "git_blob": "1fd4bb7151310df632693e71c341dcab4b1d4f19",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "references/repository-policy/CLAUDE.md",
      "state": "present",
      "sha256": "ef1eedb37cf47b56277e2e192b44e83d67c162adf88e2a0f6e027b892aeb3c7b",
      "git_blob": "1fd4bb7151310df632693e71c341dcab4b1d4f19",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "references/repository-policy/CODEX.md",
      "state": "present",
      "sha256": "ef1eedb37cf47b56277e2e192b44e83d67c162adf88e2a0f6e027b892aeb3c7b",
      "git_blob": "1fd4bb7151310df632693e71c341dcab4b1d4f19",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "registry/operations.json",
      "state": "present",
      "sha256": "397729c65e0785a47e1ca2816cba98462dac42fe67edbfb01dbe55b51cbf3303",
      "git_blob": "9c39c1aef4d994125c89ac26374fe631d3a48924",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "registry/placements.json",
      "state": "present",
      "sha256": "5048f354f65d521af13b1f0cbab438f2e75a9e2fe9560c7f40ffd14169aad8fb",
      "git_blob": "4255d00970003a2271c7d9e00dd4c92913c067b1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "registry/resources.json",
      "state": "present",
      "sha256": "6fe25c3f6bcbbe2ed2bc2ba5449c4926334c89c50055592c98fc38321ed965aa",
      "git_blob": "0450fa060908aff356bdcdc01c8415ece15098a8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "runtime/CONTROL.md",
      "state": "present",
      "sha256": "12876572098fa24bcbc59b20bdfada46032cca1a591ed4009143fdc3ace9c914",
      "git_blob": "a030b8bd8cafedf48f197bdf08cd3e5a961154b8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "runtime/CORE.md",
      "state": "present",
      "sha256": "3d4b7fb302e4e9f6cbdb7b3cd1c136eb47aeaa2e65eba06611427931cd1b8eed",
      "git_blob": "be776d659d37adf09a0625673ead69699b13d85e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "runtime/DECIDE.md",
      "state": "present",
      "sha256": "a3a356a0526a5a15d7af0fc98df7ffaf11dde6bd1bb80783a54bd4b5fcfaedd1",
      "git_blob": "f477318bb1eb933bdf37d052dca200932bc952f9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "runtime/EXECUTION.md",
      "state": "present",
      "sha256": "17720b98af6eacc44318eaa37f727d850425babfdab62a8c7a0f57cd2d304787",
      "git_blob": "237f68b8a137faab2d760a67838f4dc7077ef336",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "runtime/PROSE.md",
      "state": "present",
      "sha256": "75b00f636021fe247eafd8757de565269dcd0fe5bf27774546b1dabc73144ccf",
      "git_blob": "f1b8fc0aed2a09af4a38156967e84ed03b37fb59",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "runtime/TEAM.md",
      "state": "present",
      "sha256": "c223ceb5335605e57980c95549e2225f17966b5c06bb58f5894de6aec4a191c4",
      "git_blob": "759e87ec9695bed8f991b88904e5e8c13fcef317",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/__init__.py",
      "state": "present",
      "sha256": "483ac5ccf6287140cba89cb9ea470f9bcce24b3e2efdaaa1de3e1251438034c3",
      "git_blob": "1fc5a64100ae58e3ad92d02cc9ce7b4126f041ea",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/check_instruction_links.py",
      "state": "present",
      "sha256": "11caf4e468e6959c978b67c066b07f3a261e3fe71f4d5b634038aef156092fe7",
      "git_blob": "351d248153744ebc165306de628da2f1f91dc4a9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/export_project.py",
      "state": "present",
      "sha256": "2f746472084912df8e87634fb391b680e97e57199dcd6f1cdbd44e5945aa68c6",
      "git_blob": "3aa7fc7e0da28bf4d4a1c3a26ff40436fac497f8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/pack_context.sh",
      "state": "present",
      "sha256": "683360d226686020e02f939e1bfa6baf0cdaaabfcfe5981e7135dfe49b1386b9",
      "git_blob": "5f14fe582e9f4ee842a24d07ae2f7a16d8d777d1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/route_registry.py",
      "state": "present",
      "sha256": "ded7428176104de0c6699effbe52d112c3fea2622a8db94146b88bf8e584b851",
      "git_blob": "275ebcb8627def49d2871ca21607eab1c7423a3f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/setup_extensions.sh",
      "state": "present",
      "sha256": "917c8bee2c31f08c9c2c86f60e1eaf4b5c685bd582afcce33fc0378996ed3cb1",
      "git_blob": "f2aad4d755d38bdcf02c7010a99e1925c9951175",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/setup_ide_mcp.sh",
      "state": "present",
      "sha256": "b35800f79f1dc5e95d8d875d668aa5dc27738f929764c14072dccd0e34af3fc9",
      "git_blob": "1b5abda4c59df9e91973c9e83f73469903bb59be",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/sync_common_core.py",
      "state": "present",
      "sha256": "35ac76cf449aaeb26f8a07fd0c74eb7a30958d1625860a591d03d4f94ad510df",
      "git_blob": "0eef84d0ffc7f840a75ca74f9e586ed77683ed05",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/test_configuration_tools.py",
      "state": "present",
      "sha256": "467a63f779e2096214e545726c8691ca88e03cefcce56096b8c6cffd1a6bbde5",
      "git_blob": "d5246f7781bbc7e17b1a8b185d2e418a33f5fce4",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/test_equity.py",
      "state": "present",
      "sha256": "332e1f8cc9305b1e7d63c2914d9e6da8017dd0de3c7b7843a346fc1b81a2f588",
      "git_blob": "aa258adcac24fe8635c111ec1378d1c40b8d8cee",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/test_export_project.py",
      "state": "present",
      "sha256": "a27393dad3ab56b9854226d012093e8648bfaf42742d3e45d75a1f12a3e296df",
      "git_blob": "e7c6093885440a9aa1ca7858be1aa825428077d3",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/test_instruction_links.py",
      "state": "present",
      "sha256": "d1587c35b9e929a2b09fd62d4264a4e8a9ca153b4c6cdd56746a337bb5307e68",
      "git_blob": "fa5b2317222fd5b09478b1f1323f394b2cba1e24",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/test_setup_ide_mcp.py",
      "state": "present",
      "sha256": "1a96b0a96ae68206b3c3072a87471f2d08aa592822d32d30856f9c4e4d5bf3cb",
      "git_blob": "2b0222ecbcfb61a3d94ce9c05fec3522540ccce7",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "scripts/test_sync_common_core.py",
      "state": "present",
      "sha256": "47c76029474c503a4812415e1279aa4f3222a71ba161596f7e68405c7475ca24",
      "git_blob": "2555fbc44b566b3b9b8df00a0c4519163652f187",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-data/SKILL.md",
      "state": "present",
      "sha256": "5c958cf2db7db75548feac1fab928697974ce12b31591821f0d6da8825266f55",
      "git_blob": "f5679aa42bbfcba6b196030bbe1f2403bee83109",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-data/references/equity-case-results.json",
      "state": "present",
      "sha256": "62b1020b7bb0a1d43d9379dfd2bfcd724498d51aa64cb629d3a47182d8ab53a1",
      "git_blob": "65a01990e86791bf438c4a4004ad11f3c7707e14",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-data/references/equity-models.md",
      "state": "present",
      "sha256": "ad421aae45765b1d5ab19928ad59cc1fe69085a3a94548f6ce4dd54827f6421d",
      "git_blob": "3cf2de32d0d41114c7e2bc2e9afdd22f0df48971",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-data/references/equity.md",
      "state": "present",
      "sha256": "368c6ce84357fddb5a962642a3b14fe72c58f73c8fddb33e1115f697911bcd28",
      "git_blob": "ef8792d249c74ddc521ecf9af1081d96789eb253",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-data/references/implementation.md",
      "state": "present",
      "sha256": "73595de7f39dd84f975b5d878beac2194368175ae73e1c3ef6319d4d43ae8b52",
      "git_blob": "a5610d4e4fd720cb6a01f95a6b2efe9f24abdd57",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-data/references/reproducible-workflow.md",
      "state": "present",
      "sha256": "64da57d762e1f97661f7ba749a9106fd0f9a7569f252589e97f785bb012208e5",
      "git_blob": "004ee60bf45b2e56310ecb465eb8679bfebfac99",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-data/scripts/equity.py",
      "state": "present",
      "sha256": "bbad37392cc248f4a886b5a5ec62b430b7db16194893c3c21cae03f2b649a357",
      "git_blob": "df6f809760b0209e3c7a03c0592be0ba609ba32e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-data/scripts/equity_airline_case.py",
      "state": "present",
      "sha256": "86ae7c9184ceb418d388b876d1f0d691d3dd2c56db0ef24a8a5c2f24962b6d37",
      "git_blob": "a3b77b4f6ce369c889858e02175db23d3171cf19",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-data/scripts/equity_company_case.py",
      "state": "present",
      "sha256": "4438db3ebe34a80111296032ab5ef0ccc743759d2acaa4e850943971b9f7dea4",
      "git_blob": "ee7acfdd92fc3e39d6ae98d682efd16eeb8e1ba4",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-data/scripts/equity_io.py",
      "state": "present",
      "sha256": "2cecd52b064c7c087bcc0c5fb9367f34dbaaafe81878425cc21779677714453b",
      "git_blob": "23b2159052f8e7655035a5af92a34ecede713d0f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-data/scripts/equity_sources.py",
      "state": "present",
      "sha256": "c9a19d58db9ce4d91401d153d5427b90ed10ad5ce0b0161c60d699f545cf9376",
      "git_blob": "43290d859ede730bac639dae89dce24799064e8e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-data/scripts/requirements-equity.txt",
      "state": "present",
      "sha256": "5f7ec2a7f299c62968db977bba260c91cf9e0bad20ed855e5d429ee4814bf627",
      "git_blob": "c2d6b5d234c8e846449217df41bae0b9353c2ea5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-design/SKILL.md",
      "state": "present",
      "sha256": "1f551acace7ee0465088a1c4d165ae0ebe378c755d3123a4408f74ae8cb2a4a0",
      "git_blob": "9da70c152ed73f2ea7e8c4f9c0129572bc638559",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-design/references/designs.md",
      "state": "present",
      "sha256": "fde5c26e3d1b53fc59f43955fb71a0682d85c34733ad69af397490fb9d595a86",
      "git_blob": "a4db99db04f7e2f74a5468e69cb386a8aa89ae08",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-literature/SKILL.md",
      "state": "present",
      "sha256": "b48e5e966871e299dfabff4b132ea1732a7ab4960c816b86dc4aa741d883bb05",
      "git_blob": "19ab5000eb9ad190a3853d64ae7e84d6177a1484",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-review/SKILL.md",
      "state": "present",
      "sha256": "135eeb6202776212af47201c9131ed05d680b14c2018abb5b9cb863addca7cc4",
      "git_blob": "2b7a2055152610e41e19e3fc6c78da24b8e83994",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-review/references/oversight.md",
      "state": "present",
      "sha256": "808f85d34009f54760e801e76f16449d04f02efe16e7cccb5b8a13a4d8c7e2b0",
      "git_blob": "614e1b6e653d1debc94a230d2f567ffe7260e60f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-writing/SKILL.md",
      "state": "present",
      "sha256": "2caaf2701352e1352a15b605be70dc8c05bebfdced821ee67467b76b9f89225a",
      "git_blob": "ec299397f4bfcbbc739b3ea3b863078cf507e701",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-writing/agents/openai.yaml",
      "state": "present",
      "sha256": "dadd933a3fd861e194ac4df3dff3b8912874b72ffad11768719b8776f4a123a6",
      "git_blob": "d3214f8ae4e43308c30f96f8577c1696f43a068c",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-writing/references/paper-workflow.md",
      "state": "present",
      "sha256": "737f7bf096eaf1e780a8b8215ba4cbf24d013d5e6b01484cdcb8f21c996cebfd",
      "git_blob": "9aaae68a5e325df34aa0917ee358567308c7ae3d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/econ-writing/references/paragraph-workflow.md",
      "state": "present",
      "sha256": "3c9d2f5f55e8c736ec33da83eadf88505d16cc68b3ea219d7a7d075d8e4e1433",
      "git_blob": "afa820c2d02db03832d1db6268935ffd594190e6",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/economics-checked-instructions/SKILL.md",
      "state": "present",
      "sha256": "1ce58690297b9a393cdb37c5b82858d7a92a49e61abf01a4e00434e5b44a670d",
      "git_blob": "d9ada92182e0b0a08d333f0f54ae35dc38e2917f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "becfd22d5dd15fd6e4b0a273a945a7db3989c675"
    },
    {
      "path": "skills/explain-before-shorten/SKILL.md",
      "state": "deleted",
      "sha256": null,
      "git_blob": null,
      "mode": null,
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6390c6c6b7bc976905d0414055b65f97d0ada291"
    }
  ],
  "released_paths": [
    ".agents/mcp.json",
    ".claude/mcp-configs/mcp-servers.json",
    ".codex/config.toml",
    ".cursor/mcp.json",
    ".gemini/mcp-configs/mcp-servers.json",
    ".gemini/mcp.json",
    ".mcp.json",
    ".windsurf/mcp.json",
    "mcp.json"
  ]
}
```
<!-- /common-core-receipt:v2 -->
