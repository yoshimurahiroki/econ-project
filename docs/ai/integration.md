# Project integration

Use repository skills in the coding environment and SOURCE.md to identify Project attachment snapshots. Read this document only for explicitly requested distribution, synchronization, configuration, installation or state migration. Ordinary research uses the runtime and the selected specialist.

## Common core

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

Use `--release PATH` to relinquish receipt ownership while retaining the local file and index. Released paths cannot be copied or deleted by subsequent synchronization. The explicit --release-local-configs option releases the nine LOCAL_CONFIG_PATHS; combine it with explicit --path entries when also copying common files. Remove public tracking separately with `git rm --cached -- PATH`; keep the runtime file locally and distribute its public example definition. The [configuration examples](config-templates/README.md) are managed common files; runtime MCP configurations and their generation state are local.

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

Run the affected package-only checks with python scripts/test_export_project.py. Synchronization fixtures run with python scripts/test_sync_common_core.py and retain the ownership, dirty-source, staged-index, rollback and execute-mode safeguards above.

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
  "source_base_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809",
  "source_state": "committed",
  "common_content_id": "8132d96789e173479c9bf422aa2dd81fbf0ab5ad59842b6b2cfb5898ea5fde9a",
  "target_repository": "github.com/yoshimurahiroki/econ-project",
  "paths": [
    {
      "path": ".agents/AGENTS.md",
      "state": "present",
      "sha256": "e348a9d4f1a32b26c56044a73f729200cadd057e694deffea570ca6dbe9cd5dc",
      "git_blob": "a699a9e3b9521f612a0c2bd26261b65c38f6a970",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-assertive/SKILL.md",
      "state": "present",
      "sha256": "d830160a0aa3bf38b22fb233a8fb2efd5ad2c6f82daf654ec813c5515299b314",
      "git_blob": "1b7a60f463660af7c6cab37967a19b186b981221",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-assertive/agents/openai.yaml",
      "state": "present",
      "sha256": "459377a9ab082284cb5e37d6e6e0d9120ecbde7970b29ed3da0884d79f189e85",
      "git_blob": "41813f2b92e08828d01a2c3c0604b0f8c60ad6ac",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-assertive/references/default-micro.md",
      "state": "present",
      "sha256": "cddf3f84ebe3bf2e2bd1a4dad33b0ee78b8c92b6e68d017ac6eea4a928a9a6fa",
      "git_blob": "f2eef4930b44c37b9e66aca309e0a138b8350d78",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-assertive/references/patterns.md",
      "state": "present",
      "sha256": "4793b1c76c86e43af204cd53ebb649bdf8fad1b0d509d19077651bc05d01a6b8",
      "git_blob": "037cc297c3f30ec794b5933817a54e1300e20ad3",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-data/SKILL.md",
      "state": "present",
      "sha256": "f28e8bb396738b74a8c1da553669b0af62c99ce0c14b546da69a9ae4aaa5c784",
      "git_blob": "646b18931f1ab7476204f4135f82e5c42e853955",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-data/references/implementation.md",
      "state": "present",
      "sha256": "2b664b5b8617829cd0c3e1257a40838eb4d944bc6d4f0804de8af6d405cedad9",
      "git_blob": "b7778008dac7699622cf108b4e56c2bf70df0083",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-data/references/reproducible-workflow.md",
      "state": "present",
      "sha256": "48aeef636228691b2083d16742b1d92666258ace6d211f48e17d3504f58a38f3",
      "git_blob": "e8ca43387f406ca55cc76485f4389854fa7f083a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-design/SKILL.md",
      "state": "present",
      "sha256": "f561697a74856398299a5f0383e180182a3341a896543bcb548d824522bc1160",
      "git_blob": "a7c47a912be39df8b72bc2f156d7e9e95d8d788f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-design/references/designs.md",
      "state": "present",
      "sha256": "0c5b85b79259aa9f9ca7259c5b8768faba7b94a4520f6f3410bbf654893d8de8",
      "git_blob": "fbe5f2461ef695ea738a3fff3e7e3d2dde2c14fd",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-edit/SKILL.md",
      "state": "present",
      "sha256": "d750d366d652110ba3c31107a082331417c0cfe9ffdf809ce78700905ed86803",
      "git_blob": "499529b73bac66ee82ef7a1d8d5b179f69e7a03b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-handoff/SKILL.md",
      "state": "present",
      "sha256": "e8d028b9d2a054b79053cbc94a20f0623db2926270698d739d2d899618fc372f",
      "git_blob": "c914f299058c36123d98bfa84977a3c8fe6972c6",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-handoff/references/handoff.md",
      "state": "present",
      "sha256": "40d49124207279ef205f752f9b24f1a6875786b8874460840f1c15c25d0063d2",
      "git_blob": "5cc09975b0d3ca1dbad15dad86d558bb40343a60",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-literature/SKILL.md",
      "state": "present",
      "sha256": "626d9503de3620d67c08e6f381a04b272ac6368df74b3ee6a202bee877bd8f55",
      "git_blob": "a0e8ed76bd71b3727f4bdca1e9752b5f08fe8480",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-paper/SKILL.md",
      "state": "present",
      "sha256": "453da712a2dd914d5d759e406b4ccecc1b1ea5c8da105a910ad02a6c4992c7cd",
      "git_blob": "c79541db73fab8d32799332e7b7e304149744f5a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-review/SKILL.md",
      "state": "present",
      "sha256": "ed33315829bec3ae18cfa35ef26cbc4465f501a505a444d436371f744ea52892",
      "git_blob": "ca79fb5838a8ffa53d91d004ce98570684ac6c1a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-review/references/oversight.md",
      "state": "present",
      "sha256": "e642a4ca86a314130fc3046257694d999d0d81da5d14a93e0b17193275022eb9",
      "git_blob": "614b8572a1d31850a67e36565fe54eba5b905e32",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-style/SKILL.md",
      "state": "present",
      "sha256": "796599d67a0d80b8494f484022bcb2e02e6f35743a929911f6c5f9c512326a3d",
      "git_blob": "7e60182e5724477d1d8ae691d4937deaa965f7a5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-workflow/SKILL.md",
      "state": "present",
      "sha256": "154cb6768d9229cd47dd1cc13dc123d2e0be48b75eeb12e13431a3e0b9ffc19e",
      "git_blob": "20ee352e9739b62cdbde78b0051c784b86508c20",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-workflow/references/descriptive-model.md",
      "state": "present",
      "sha256": "b0eedf820554ae13e8b2a44fcfc16015b03d99d5f049651918548b06b3d05a29",
      "git_blob": "9ead28626fb16ba5cf84e35fc3332da3cff0b989",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-workflow/references/team-execution.md",
      "state": "present",
      "sha256": "a02e97052df4fb1bc9101de333068d5b44fdeffece06ccc75d5ab78bfede1ece",
      "git_blob": "177986fce60503d23d125c581fd1ed6efabbe96a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-workflow/scripts/team_state.py",
      "state": "present",
      "sha256": "540ad668fbaad0a79316d453a57ce9b0be041f6fdc856b82f99082c43bac6486",
      "git_blob": "1d5a1ab021b6909fcbf65546d51d10ae3d21f56d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-workflow/scripts/test_team_state.py",
      "state": "present",
      "sha256": "74cf7a91731e9f64092716f344ef96053511866a8847b605b973a00cd9f807e0",
      "git_blob": "95ca51375385099802d5b40b9ecba01db78b1472",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-writing/SKILL.md",
      "state": "present",
      "sha256": "7f5a8582f4ff7babd823ba5a98d75e2afdc2b584093869dab6385d0cb54e3677",
      "git_blob": "bd46b6bd31a0da8ca87644234c1edc02e6642f48",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".agents/skills/econ-writing/references/paper-workflow.md",
      "state": "present",
      "sha256": "4de0f32642782cb7180b7da3740c012d8d72371254d5f8f44df6a0838e744fe4",
      "git_blob": "837a30532920182e4159c676ebb3e6356004202f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".claude/AGENTS.md",
      "state": "present",
      "sha256": "e348a9d4f1a32b26c56044a73f729200cadd057e694deffea570ca6dbe9cd5dc",
      "git_blob": "a699a9e3b9521f612a0c2bd26261b65c38f6a970",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".cursor/rules/01_project_policy.mdc",
      "state": "present",
      "sha256": "adf647e1c9af5396fb121b2d6ac8ffec650833da6deae33d96c2d25cbb465510",
      "git_blob": "cbc8df4bedae7b9b0a2871bea951f6a60be18d23",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".cursorrules",
      "state": "present",
      "sha256": "d323042867bd3abaf3a12a6ea672b8fe4449756eac17ac3087ec79edab0039a6",
      "git_blob": "750bd4e507b04067a2479b3b276514c0d039ef5c",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".gemini/GEMINI.md",
      "state": "present",
      "sha256": "9e475650f183f0b043de0d05c6e0677f491d54f9fcc8f1a2a3b8d3b9dad60d55",
      "git_blob": "9396740efa914c5e999800240480e35ba6181b94",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": ".github/copilot-instructions.md",
      "state": "present",
      "sha256": "b772e08542240ea8098a8ec663105acd3171d0e9a4a5b72b8f735ec58af901c1",
      "git_blob": "2c6d60bcd43d4df21d8da6317bfec0faca5258a8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "AGENTS.md",
      "state": "present",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "CLAUDE.md",
      "state": "present",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "CODEX.md",
      "state": "present",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "THIRD_PARTY_NOTICES.md",
      "state": "present",
      "sha256": "9f558903e68380889c7fe67fd0c39850d11b41f66b7f89b5d7b5cd844e97d7ca",
      "git_blob": "8bf3668c5ae6356e8e1332efded152f2a407e744",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "docs/ai/compiled_ai_skills.md",
      "state": "present",
      "sha256": "7a4ec07308dfaacf135d7f7cb36c9061cfeef3bc04605ca3a2383dc2e3ba953c",
      "git_blob": "d1e7681bd40c6babee85f92253a96e452fc9bf2a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "docs/ai/config-templates/README.md",
      "state": "present",
      "sha256": "346cb67de8f53e1a182c8cde81c9e178e848448664d21abeb520af0b9224c6c1",
      "git_blob": "3a1fab0e93823aed50e9085c84810e0bff1c09fb",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "docs/ai/config-templates/claude-mcp.example.json",
      "state": "present",
      "sha256": "7e098a33b20cda19ae9067ffc8252f2637bf0314963893df85110fe3120fee63",
      "git_blob": "e29ee95ea2e7cdc213561f0a75252c43d28d51de",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "docs/ai/config-templates/codex.example.toml",
      "state": "present",
      "sha256": "c57023f63a938b1d62c9c66f5d6f6c0dbb001e496aa9813bbf3d6a5980e38b05",
      "git_blob": "be298aabfb36b8954160f39686750a294dad8527",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "docs/ai/config-templates/mcp.example.json",
      "state": "present",
      "sha256": "d8e397af03b5b032f21d0aa967086f0c78b33c87b76f2e9898ae0a144df7de02",
      "git_blob": "da39e4ffafe816be90259a3f68b763a3f71b93ed",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
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
      "sha256": "8886a72ac7d13e4bcd813b8dce28df202e0985763ce67f563727b468f22a17fb",
      "git_blob": "056fe341c358840e1813acd16508578ecbde2dbc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "docs/ai/resources.md",
      "state": "present",
      "sha256": "d6e285c9b81e5ad353004efa867417618fe5bf6830acf8b9c629162b6e5af1cb",
      "git_blob": "2d3bf06f3c7e63e4669bee6a5df395980cd35d19",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "scripts/export_project.py",
      "state": "present",
      "sha256": "005dac5b1c5dd831773d912fdd10202c0475197cd86c09d4f620154f6b4b2377",
      "git_blob": "58d83dac7f368d12499a06a720f17c8ea82e9ce9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "scripts/pack_context.sh",
      "state": "present",
      "sha256": "f74a948b3fc7e3e43d4c68b89f2010cc54190d36d1a95c79abadad349ebb7155",
      "git_blob": "7174135411df6697c22589b25f0fdb9f50784e7a",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "scripts/setup_ide_mcp.sh",
      "state": "present",
      "sha256": "69240f5c7ef14618fff70f072ffbab635496d303d542122e12f476939bf8a0b0",
      "git_blob": "db03ad944ff24607af333e421c6a80c280932440",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "scripts/sync_common_core.py",
      "state": "present",
      "sha256": "29ef4ef561e31b8ec755fe7a3768b65a155be101f78d7b1e5ae34a1789c76dcc",
      "git_blob": "859ca38082f08003b49683305525481c58c11ffb",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "scripts/test_setup_ide_mcp.py",
      "state": "present",
      "sha256": "33d977ad402871445215d55330817cc63718a9ca164dbe463df5786784eab7dc",
      "git_blob": "0ded4f6348a1264581bb68ccbf4d897033cfbdc7",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
    },
    {
      "path": "scripts/test_sync_common_core.py",
      "state": "present",
      "sha256": "2d0a694d4d20f8979150f988e5f9a471de1c7f4813e2f93806a46dfc5e9e9179",
      "git_blob": "c795517bd8c3a9dc46e189311bc5835fb8cfbda5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "6116d1cc244269568b0aa3f1568a05f5cdd25809"
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
