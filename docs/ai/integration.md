# Project integration

`econ-project-mini` owns shared research instructions, tools and the authored economics library. Read this document for requested distribution, synchronization, configuration, installation or state migration. The active runtime and selected specialist own ordinary research.

## Current research and reading path

1. Establish the current request, adopted specification, authority and complete mandatory instructions through CORE.
2. Resolve the final operation, specialist and mode through the operation registry; activate conditions from the actual requested object.
3. Read the specialist method and its required dependency closure. Reuse complete same-version bodies already available in context.
4. When the pending operation needs economics knowledge, search the conditional knowledge reference, select applicable IDs by their inputs, outputs and conditions, and read their true prerequisites.
5. Execute the calculation or change through the established owner and official package interface.
6. Review the integrated result and verify the changed behavior through its actual entry point.
7. Save the requested result and producing evidence in its existing destination; reuse matching completed work after restoring the governing context.

Sol owns economic choices, decomposition, integration and the final result. Terra implements adopted bounded specifications; Luna performs settled retrieval and extraction; Astra receives the consequential core after Sol's actual attempts and cause-specific repairs leave it unresolved. TEAM owns the model and host contracts. The five specialist owners and seven writing modes retain their specialist methods and actual completion contracts.

CORE owns the common entry and the complete PROSE normative-reading obligation; the detailed dictionary supplies concrete lexical detections for the same integrated review. Specialist entries retain their method, source and execution requirements. The policy assembler validates each selected resource once per invocation, reuses those exact bytes across selected sections and delivers every required body. The existing state, source, research, publication owners retain authority, version, evidence and completion behavior.

On hosts delivering the registered callbacks, ordinary task completion uses the declared outputs/actions in the existing operation context or bound task state, actual returned outcomes and current artifact versions. Simple responses need no state store. Parent completion waits for child returns; compact/resume retains the original sources and saved-result references. Interactive input requires the exact live session/input and initiating-command authority. Callback records retain actual outcomes within the current execution permission.

## Economics knowledge source and retrieval

The authored catalog and chapters are the content source. Schema2 keeps bilingual concepts, selected JEL tags, conditional typed relations and model contracts in that catalog; compatibility prerequisite/related/alternative arrays are generated from its relation records. `skills/econ-knowledge/scripts/knowledge.py build` generates per-ID bodies, domain indexes, checked semantic views and the hash manifest; `build --check` rejects stale generations. Declared counts are checked against actual content, so a valid collection can grow without changing fixed-size code assertions. Edit the canonical source, regenerate once, then synchronize and export through the commands below.

Small bilingual domain indexes nominate candidates across economics fields. Exact IDs, normalized English words, Japanese fragments and explicit aliases support bounded search. The specialist selects the full economic chain from meanings and adopted assumptions. `read` returns a topologically ordered prerequisite closure; related and alternative methods enter only when the operation requires them. Source and projected runtime collections retain explicit layout, manifest, body and selection identities. The knowledge owner packages its runtime collection once; the five specialists keep their own methods and execution resources.

Use `concepts --query TEXT` for bilingual names and taxonomy, `relations ID...` for typed conditions, and `plan ID... --context KEY=VALUE` for the adopted application. Sol establishes the selector facts, identifies the required IDs, and reads their full bodies. Registered econ-data engines retain execution ownership; source implementations carry canonical URLs and SHA-256 provenance. A matching task-cached body retains its body, catalog, manifest and retrieval-specification identities. Changed bytes require a new read. Restore complete saved content after context loss. The manifest and runtime marker establish file identity without adding their full administrative text to the model's working context. Local structured retrieval has no paid service or model-weight requirement.

## Supplied document defaults

New LaTeX papers use the supplied Econometrica template and its original class, configuration and full-name bibliography style. New slides use the supplied Beamer/metropolis layout, Waseda colors and Harano Aji Japanese setup. Preserve the five supplied files' exact bytes, comments, intended placeholders and license notices. The artifact helper produces Pandoc adapters for Quarto and result-bound LaTeX/PDF generation from these templates.

The shared build helper preloads fontspec for the journal class, processes bibliographies when the auxiliary closure requests citations and restores the preceding PDF on failure. Make and the LaTeX Workshop recipe use that helper; shared editor defaults disable magic-comment compiler selection. Raw registered assets preserve their bytes through source, portable and Skill-bundle generation. Existing research contents, scientific results, bibliographies and private settings keep their ownership.

## Common core

`econ-project-mini` owns the shared source. Public and private destinations consume the registered common files and retain their own manifests, connections and project data. Account-specific plugin releases and authenticated services belong to the selected private destination. The existing synchronizer stores its machine receipt in `docs/ai/common-core.json`, separately from these operating instructions. It records source and destination identities, the current synchronization source commit and exact managed hashes and modes.

The resource source paths in [resource registry](../../registry/resources.json) define default shared instructions and tools. Entries marked sync=false remain project-owned. The synchronizer copies the same source-relative paths between repositories; it does not install deployment mappings. Each user chooses the source, destinations and paths. Origins are identified by their complete host/owner/repository path. Repositories with separate histories and different owners are supported.

`quality/policy_manifest.json` is generated for its target repository and has `sync=false`. Synchronization validates the resulting resource and operation catalog in memory; the destination's exporter then regenerates the manifest from its actual project context, integration guide and common files. For an earlier receipt that owns this path, release that ownership with `--release quality/policy_manifest.json` while retaining the local file and index. Complete target generation before using its runtime policy. Explicit path selection retains the synchronizer's ownership checks, including protection of previously released paths.

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

Use `--migrate-receipt` to migrate a v1 receipt whose recorded source commit, blob, hash and mode can be verified. Source switching requires a separate reviewed ownership decision. Each v2 receipt records the source identity, input commit, selected hashes and modes, adoption state and destination identity. The same guarded apply migrates an older embedded receipt into the machine JSON and removes only its block from this guide. Deleted paths and redundant per-path commit history are omitted after their authorized deletion; current fingerprints retain the ownership baseline. It contains no host paths or credential-bearing URLs. Project context, integration prose, research records and environment dependencies remain project-owned.

Use `--release PATH` to relinquish receipt ownership while retaining the local file and index. Released paths cannot be copied or deleted by subsequent synchronization. The explicit --release-local-configs option releases the declared LOCAL_CONFIG_PATHS; combine it with explicit --path entries when also copying common files. Remove public tracking separately with `git rm --cached -- PATH`; keep the runtime file locally and distribute its public example definition. The [configuration examples](config-templates/README.md) are managed common files; runtime MCP configurations and their generation state are local.

Deletions require `--delete PATH` with that source path absent. Moves require `--move OLD=NEW` with source OLD absent and NEW present. Existing destination paths still require their recorded baseline or a matching ownership claim. These operations stay within the explicitly selected paths.

The script checks all destinations before writing. It compares shared source inputs, repository identity and indexes at the start and final publication boundaries; immediately before each write it compares that target's content, index, repository identity and configuration. Previously written targets are checked at the final boundary. Writes use optimistic per-file atomic replacement, not a filesystem-wide transaction. It writes receipts after content, verifies the result and rolls back only its own unchanged writes on failure while retaining concurrent user changes. Exit codes are 0 for equality or successful application, 1 for comparison differences and 2 for a refused or incomplete operation.

Git `core.filemode=false` supports content updates and replay at the existing tracked mode. A mode transition requires `core.filemode=true` in a filesystem that tracks execute bits. The synchronizer refuses that transition and leaves index metadata unchanged.

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

Use the actual selected generation and synchronization results to establish package and destination behavior. Preserve ownership, current source/index versions and rollback at the existing producers; do not maintain a separate distribution test suite.

### Native configuration dependency and continuation

`core.task-entry` requires `team.native-model-roles`, so the ordinary operation retains Sol's authority and the bounded child contracts. The existing `requested_distribution_configuration_or_installation` condition additionally selects the three `policy-codex-agent-*.all` rules and `config-template-codex-example-toml.all`. Their registered source files are public templates; deployment maps child files to `.codex/agents/` and retains the primary template in the configuration documentation. The [configuration commands](config-templates/README.md#native-sol-terra-luna-and-astra) produce flat aliases or deployed paths through this same closure.

Each native role declaration selects its own model and reasoning effort through its registered configuration file. Child execution inherits the parent permission boundary, provider, authentication and MCP configuration. Preserve those inherited bounds when applying a role override. The exporter preserves executable and data-resource bytes; each `SOURCE.md` records the source and exported SHA-256, logical resource and physical output path. The decision contract always applies; configuration files are selected for an authorized installation.

The installed-layout continuation consumes the same deployed resource mappings and complete registry versions. It regenerates only the requested exports, compares native TOML metadata and bytes with the selected source, and retains the completed first exports. The primary template's provider/login settings, the three requested child models and `xhigh`, and Sol's fixed research authority carry through both layouts.

A repository can retain canonical source and a deployed `.agents` tree together. The source policy uses `quality/policy_manifest.json`; the deployed policy uses its registered `.agents/quality/policy_manifest.json` with repository-root deployment paths. Discovery matches the actual policy module against the installed placement before treating the nested registry as a source root. Each layout binds its own resources and policy manifest; a changed resource invalidates the corresponding manifest. Deployment adoption preserves canonical root documents and binds the actual adopted bytes through the deployed manifest and source snapshot.

## Distribution contract

Read this section only for requested export, installation, synchronization or configuration work. The [operation registry](../../registry/operations.json) defines modes and conditional rule selection, the [resource registry](../../registry/resources.json) defines logical resource IDs and rule dependencies, and the [placement registry](../../registry/placements.json) defines physical locations and export aliases. Use the registered resource IDs and the selected layout when exporting or synchronizing. Read the relevant command section and its supported options. Compare common inputs at batch boundaries and each destination immediately before writing; do not reread every unchanged input for each target.

For an export, select CORE, the final operation and its activated support/resources. Include only sections needed by those operations. Short prose does not activate whole-paper instructions. Resolve every active mandatory reference inside a standalone package. An omitted optional capability becomes an additional input if later needed; do not turn it into an automatic remote-repository fetch. Resolve resource paths through the declared placement and export aliases. Check required files, references, unique output names and requested size limits before producing the complete package in a new destination.

The configuration interface defaults to a diff, changes only explicitly selected clients or adopted project targets, and rejects unknown arguments or incompatible modes before writing. Read every selected destination and required input, then assemble all intended changes. Include devcontainer only when selected. Resolve relative paths from the command's declared project root.

For each generated setting, compare the previous generated content, current content and proposed content. Update a setting only while its current value matches the previous generated value. Preserve manual changes and mark the item manually owned. Recheck content immediately before applying and preserve detected concurrent changes. The helper uses per-file atomic replacement with optimistic rereads. Coordinate other writers across the final read-to-replace interval. For a caught multi-file write failure, roll back only content still matching this operation's writes. A process crash requires inspection of the actual destinations before resumption. Legacy name-only ownership records do not establish content ownership; preserve those entries until their ownership is resolved.

Reference secrets through existing environment or approved storage rather than embedding them. Required configuration or installation failures must propagate as failures with the affected targets. Preserve successful work, diagnose failed items and retry only the affected operation. Report the returned statuses; an instruction to perform an operation is not a successful operation result.


## State migration

Use explicit capacity, depth or attempt limits only when the user or runtime supplies them. Migration preserves saved outputs, bound check receipts, usage, holds and limit provenance. A legacy task lacking declared deliverables retains an unresolved completion contract; recover the request and use set-contract rather than infer requirements from whatever output exists. Previously completed tasks with an unresolved contract become blocked while their results remain saved. Legacy permission/user-hold reasons without an identifier receive an identified legacy hold. Perform missing required operations against preserved current results; migration does not rerun calculations.


An old evaluating state maps to running; interrupted maps to blocked with blocked_reason=interrupted. Schema-v4 migration preserves outputs, check receipts, authority, holds, attempt counts and usage. Where recorded consumed inputs identify one parent output unambiguously, migrate to that explicit consumes edge. Otherwise retain the legacy dependency set as a compatibility group until the next relevant operation establishes its input contract; never erase it or guess a narrower dependency. Migration alone does not invalidate numerical results or rerun completed stages.
