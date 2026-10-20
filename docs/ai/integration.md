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
  "source_base_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038",
  "source_state": "working",
  "common_content_id": "0b522f70819197f86768a11dcc01331c267bb24617e4d176dd9a4b9207d169fd",
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
      "path": ".agents/harness/test_state.py",
      "state": "present",
      "sha256": "b0ff4178de611822856fad1dbebd2899d41fdab88a0c499d78edbdd6d9d381be",
      "git_blob": "e396315580b1b34e303ccb88e8942729fc8d8a8d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
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
      "sha256": "3f5dc9d5167ada28729c6c8d87a4a4a985dca396ecfd35a4d4d414319ab691b2",
      "git_blob": "537a090fc5ee12e84194d65bdd330c49b17bda86",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "docs/ai/config-templates/README.md",
      "state": "present",
      "sha256": "79d77ee0cffd70c04ef4884485ed124a21d83aba0786a7054c132d75950dfa87",
      "git_blob": "97ec119bcae6bac54dc9b0f39a8208709100a410",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "docs/ai/config-templates/claude-mcp.example.json",
      "state": "present",
      "sha256": "7e098a33b20cda19ae9067ffc8252f2637bf0314963893df85110fe3120fee63",
      "git_blob": "e29ee95ea2e7cdc213561f0a75252c43d28d51de",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "docs/ai/config-templates/codex.example.toml",
      "state": "present",
      "sha256": "c57023f63a938b1d62c9c66f5d6f6c0dbb001e496aa9813bbf3d6a5980e38b05",
      "git_blob": "be298aabfb36b8954160f39686750a294dad8527",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "docs/ai/config-templates/mcp.example.json",
      "state": "present",
      "sha256": "d8e397af03b5b032f21d0aa967086f0c78b33c87b76f2e9898ae0a144df7de02",
      "git_blob": "da39e4ffafe816be90259a3f68b763a3f71b93ed",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "docs/ai/plugin-integration.md",
      "state": "present",
      "sha256": "7a19677f863fc010e706ff7d503ba9190c5289c66e88b79b88ad3a308deb0509",
      "git_blob": "c3ad94c9985c01bc65b745cdba30b64366afb240",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
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
      "sha256": "d7ef5e069d999ac2d9f5aeff634f0e2f74155665d9348699f3f45b687fe4d400",
      "git_blob": "4fa8a9d1016b72dbdfe09a352416f342935d6c96",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "docs/ai/resources.md",
      "state": "present",
      "sha256": "d511eccc4a4d279121cc0abf1803cd6346c670b1c4b313c126328065a8d8f4ea",
      "git_blob": "ff3b64efb0ff35fd36653ea6b08b15ef9266c77d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/codex_hooks.py",
      "state": "present",
      "sha256": "af49379b64dbb776ab5e8c5b8ae12f8f51dbb2c774e26a19a57f644cfb8ea320",
      "git_blob": "899761c5cbc028c091a5bf7ad07ccf37ee0dd967",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/local_checks.md",
      "state": "present",
      "sha256": "c9df41b68d1aeeefe2ed6a0c2fa5fdd6ec44da1348303e63f78f284dc1501984",
      "git_blob": "5d3e954c637ea95cd38cd47cb615708b02807d5a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/local_checks.py",
      "state": "present",
      "sha256": "3d5734bbfa4862fd25ee2f6233b3fdebc98ee7d9d2d981da5eff9ea4efde0385",
      "git_blob": "85782f05746141be8aa3bc97c1dfed2f7123a3a1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/native_check.md",
      "state": "present",
      "sha256": "eacc3099f79b450310dbcf11e87ca747218097f80d3e1fc08caa1095ffe131ec",
      "git_blob": "41982d375eef8611c0e61f3b7caf7e59901a7412",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/native_check.py",
      "state": "present",
      "sha256": "5ce9eacdf010ae8dc62d597e1e5efd840e97d6c5e9fdaeebdafae08cfec79491",
      "git_blob": "b09603cf69bcfa7e7856c49fbcf680859f17cdfe",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/native_run.md",
      "state": "present",
      "sha256": "05248f166790b02fd4c8f6032fe94741517853019caed057d976a7e950d5afc1",
      "git_blob": "f74d068bf6370f405c98e5044561ba97c422bb1a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/native_run.py",
      "state": "present",
      "sha256": "3c2cbe04ba81d5ea0eb3431f543cfed70bc88898c30d6c6e654724008e6a551b",
      "git_blob": "bbdbc403c9f278d18c7cb086a67005f4e99b24ee",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/policy_assets.py",
      "state": "present",
      "sha256": "a341b5aca1b42798ceb14980e3c843919d9c0c7c7eb8ceeef81a1ccfca827db2",
      "git_blob": "bfa2b034dbaeae7aa0e4229a70fd1eb182427360",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/publication.md",
      "state": "present",
      "sha256": "61c475a55fdd46c07d642a1b433efb3b49a1e90d8c5a7e1604cd6bff9dc97432",
      "git_blob": "080cebc7d7cddee1379e1e295111c3997d8a6443",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/requirements_check.md",
      "state": "present",
      "sha256": "73edc472d8c66deb1195d6300b9ee172da0690f743602ef2cc862e143c0a2961",
      "git_blob": "33b40573042e0393440803cb31f7f76e8faaddb2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/requirements_check.py",
      "state": "present",
      "sha256": "3586e6170d23c77080647f88cd6c09026e11c45835b2e92e318ac91683bf8747",
      "git_blob": "e29565611e61184c4bf5895da6ce1d6aa635a2f2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/state.md",
      "state": "present",
      "sha256": "480efef8a4b4a3e78e4d36eabb7111df2c714a71032039d54154761a2ddfd4ec",
      "git_blob": "2c621a5e3e0e263a64c7f890187a41d42ffaf7d7",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/state.py",
      "state": "present",
      "sha256": "4dfb583cb10fd257bab2904973047fbd005bc65f5ee0f62740a04fdb687eb3aa",
      "git_blob": "beca5948bd9cb3a46d8246d4e67d82ceb0d9f77d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "harness/test_state.py",
      "state": "present",
      "sha256": "b0ff4178de611822856fad1dbebd2899d41fdab88a0c499d78edbdd6d9d381be",
      "git_blob": "e396315580b1b34e303ccb88e8942729fc8d8a8d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "profiles/default-micro/PROFILE.md",
      "state": "present",
      "sha256": "6b4e475fb3786c6006b26893824a05f9c40aeccb174ba1ec811face85b8c22b0",
      "git_blob": "809aceb9f90152bb37f6e813db612cc559bbd062",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "profiles/default-micro/extended-introduction-en.md",
      "state": "present",
      "sha256": "0b1d9f9511b5d32cc935c4d7c75b24bf01f94ef48f1ec7b330218d508e810b34",
      "git_blob": "834688a8d352f80a6ac4cc0b96fbe4f831dfad74",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "profiles/default-micro/extended-introduction-ja.md",
      "state": "present",
      "sha256": "cb49bab9fbb949538056f82e7560d715a3a6c648f663ea14af2b77e833bec03b",
      "git_blob": "84c9e720bfec8a585613ed516f91047c9c5f78bb",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "profiles/default-micro/short-examples-en.md",
      "state": "present",
      "sha256": "e395b60c46f6ba98e614bdab1b118ead92e7ca05560641d43ba5b75a8c83a08b",
      "git_blob": "9fafab070f78b4299f8c8611f4c3083e6514497e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "profiles/default-micro/short-examples-ja.md",
      "state": "present",
      "sha256": "4147294992356f95fb21d7484164ff56cf9adae9919d1fd1e989eb911ae05fa2",
      "git_blob": "1953cb16b796b7001b9be33f7c3804fc3fc87a56",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "quality/policy_manifest.json",
      "state": "present",
      "sha256": "f69b0b46c35138cbd4daff385169b73b1be9362700bffab5ab38734ad1e3ebd3",
      "git_blob": "fbe7958263627b0660b31074ff8a9bef094cd15e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "quality/prose_rules.json",
      "state": "present",
      "sha256": "bf529599a9f8c7912488760bf1752bdd172388f4e5304aad8daeac2c1f003373",
      "git_blob": "62da99449fe21c785149b4a94c44ddb436f9d3b7",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "quality/prose_rules.md",
      "state": "present",
      "sha256": "9a16afdf6d7a0f82d3ead92eb802f7868f9c05ac32794158564a7bff0a350c1f",
      "git_blob": "12d9e249e475f6afb8b4dc895d854908dbc289f8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "references/repository-policy/.agents/AGENTS.md",
      "state": "present",
      "sha256": "cafc59de32d85efa1b2dd219936e00920bd17fb439cdd7a9b93401e1478f6267",
      "git_blob": "0e328520b47fa076db49ecbf69b487c8e059f6d2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "references/repository-policy/.antigravityrules",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "references/repository-policy/.claude/AGENTS.md",
      "state": "present",
      "sha256": "cafc59de32d85efa1b2dd219936e00920bd17fb439cdd7a9b93401e1478f6267",
      "git_blob": "0e328520b47fa076db49ecbf69b487c8e059f6d2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "references/repository-policy/.clinerules",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "references/repository-policy/.cursor/rules/01_project_policy.mdc",
      "state": "present",
      "sha256": "6d8d91e33b2190b2da8edba15dd46350ebc3a394334ea7e2f57c4c141fb06ec2",
      "git_blob": "1f2bf852b6ba2c45f2edd1b5f8ac737be77aa6c0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "references/repository-policy/.cursorrules",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "references/repository-policy/.gemini/GEMINI.md",
      "state": "present",
      "sha256": "cafc59de32d85efa1b2dd219936e00920bd17fb439cdd7a9b93401e1478f6267",
      "git_blob": "0e328520b47fa076db49ecbf69b487c8e059f6d2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "references/repository-policy/.github/copilot-instructions.md",
      "state": "present",
      "sha256": "cafc59de32d85efa1b2dd219936e00920bd17fb439cdd7a9b93401e1478f6267",
      "git_blob": "0e328520b47fa076db49ecbf69b487c8e059f6d2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "references/repository-policy/.windsurfrules",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "references/repository-policy/AGENTS.md",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "references/repository-policy/CLAUDE.md",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "references/repository-policy/CODEX.md",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "registry/operations.json",
      "state": "present",
      "sha256": "5c4bb361a805821c9d5d745150b78aa844a44facf4b6ccdba1c5f32f2c10af04",
      "git_blob": "da76c300dde4e16b449769da93796dad4a7fab46",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "registry/placements.json",
      "state": "present",
      "sha256": "526ece1f2ae7b56aea02784e4d3e2361d88bd3db8d2883a1752e2d0b560746d6",
      "git_blob": "6d39734235e63261ed565c71f874c03063dd784a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "registry/resources.json",
      "state": "present",
      "sha256": "e51b1c439144766e121bf4b655ee3003855e617f656cb0a9ea7ae5a6d1fbcdc8",
      "git_blob": "db72d89444ef4ee2e03bd014a9e2947288ccf6de",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "runtime/CONTROL.md",
      "state": "present",
      "sha256": "a1e360017638782c7963ebc5f1961d9daa250be5fcbc6b46e46b5ce8c8f053b9",
      "git_blob": "fdea383cca76294544e97da50c4f20aa494bb47b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "runtime/CORE.md",
      "state": "present",
      "sha256": "078adfa83d04a78529a37749cdafaf30e57e94547665510c9b6ac26ffd850c8b",
      "git_blob": "32444f1413ca6b2feb26901df76b4cc0b03388b9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "runtime/DECIDE.md",
      "state": "present",
      "sha256": "3c89d70facdd919f9c5c72e721c5d574834a129ac286fc4d694c524fbc280354",
      "git_blob": "4631ce06121b68b78909e3592cfefb1d66037eba",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "runtime/EXECUTION.md",
      "state": "present",
      "sha256": "e2cf8193da5815d71e6f82cc316ed32ecccc02a4507d12e00016d6a54aac1197",
      "git_blob": "439fe9dc59bd5e2dcf5ebd157dd9fe81e37664ed",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "runtime/PROSE.md",
      "state": "present",
      "sha256": "dfa5038ce9ee7862f7e1ade4d0cbd7a3585615edb698178c3c88578009fbcb83",
      "git_blob": "d3cedc4a413b538e7c41eb276b80095931a0f12a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "runtime/TEAM.md",
      "state": "present",
      "sha256": "9a17e8ff584f1c77945e3624480b371aff60c331bbcb2c8b30ce625deecbf6be",
      "git_blob": "9f0822c51385b4d52d445c85ceba0134340cdb4d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/__init__.py",
      "state": "present",
      "sha256": "483ac5ccf6287140cba89cb9ea470f9bcce24b3e2efdaaa1de3e1251438034c3",
      "git_blob": "1fc5a64100ae58e3ad92d02cc9ce7b4126f041ea",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/check_instruction_links.py",
      "state": "present",
      "sha256": "11caf4e468e6959c978b67c066b07f3a261e3fe71f4d5b634038aef156092fe7",
      "git_blob": "351d248153744ebc165306de628da2f1f91dc4a9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/export_project.py",
      "state": "present",
      "sha256": "1913a1dd4e23dfd509e10568dfbe3c6c4e836dbb6ea42c42c1f5ce8c99ddd4de",
      "git_blob": "57fc3a7c7d3028ded59d58856dc1d9a463eacbb1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/pack_context.sh",
      "state": "present",
      "sha256": "729f22f4d8753a7ce50c1e81e1a7acff6e5ad1c28004f95185f3e0051b781ad9",
      "git_blob": "d1bb8f99c8daf9472272d0dcb90a6216afd21378",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/route_registry.py",
      "state": "present",
      "sha256": "7fcda5e4ff400a4db2d2f4327d7cabf78e3118d15ebdfc5156fc102640923b10",
      "git_blob": "7e8329214c63a77d752fc4eca2cf01c07573f332",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/setup_extensions.sh",
      "state": "present",
      "sha256": "917c8bee2c31f08c9c2c86f60e1eaf4b5c685bd582afcce33fc0378996ed3cb1",
      "git_blob": "f2aad4d755d38bdcf02c7010a99e1925c9951175",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/setup_ide_mcp.sh",
      "state": "present",
      "sha256": "b35800f79f1dc5e95d8d875d668aa5dc27738f929764c14072dccd0e34af3fc9",
      "git_blob": "1b5abda4c59df9e91973c9e83f73469903bb59be",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/sync_common_core.py",
      "state": "present",
      "sha256": "ce79903cc76d6ff4545e340f9a09e0c165fd6b3e6bc9753b734560037b771411",
      "git_blob": "61c654f174246b9dd333117b96a16e934183ebad",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/test_configuration_tools.py",
      "state": "present",
      "sha256": "bbff9ec63935445c1d74800a89b6510ace71af8d1c48a0db7772306d4b30e9c4",
      "git_blob": "af3ccf0b42fea3213d6c028068a4cdf8fa30e90f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/test_export_project.py",
      "state": "present",
      "sha256": "ed9f50483832920d56a1723b6268405f9909dce08b286168f15c3f83c4e66f5a",
      "git_blob": "a98adb00f459a9ce432170653c687152052d908f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/test_instruction_links.py",
      "state": "present",
      "sha256": "d1587c35b9e929a2b09fd62d4264a4e8a9ca153b4c6cdd56746a337bb5307e68",
      "git_blob": "fa5b2317222fd5b09478b1f1323f394b2cba1e24",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/test_setup_ide_mcp.py",
      "state": "present",
      "sha256": "1a96b0a96ae68206b3c3072a87471f2d08aa592822d32d30856f9c4e4d5bf3cb",
      "git_blob": "2b0222ecbcfb61a3d94ce9c05fec3522540ccce7",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "scripts/test_sync_common_core.py",
      "state": "present",
      "sha256": "47c76029474c503a4812415e1279aa4f3222a71ba161596f7e68405c7475ca24",
      "git_blob": "2555fbc44b566b3b9b8df00a0c4519163652f187",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "skills/econ-data/SKILL.md",
      "state": "present",
      "sha256": "ea6c4198064e09041dce5a4c89549d3f711eea51ed918f3eff12b07bc868fced",
      "git_blob": "c6c5851943d157c9f4b58a62b56b24db596fb837",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "skills/econ-data/references/implementation.md",
      "state": "present",
      "sha256": "61e9a53d5206eff0cd7207e7f18887403e04ca28b7fd2f348bd6a1fd2d98a966",
      "git_blob": "02caa6031f2c94c6f0759dffdf4e288f9bf535d9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "skills/econ-data/references/reproducible-workflow.md",
      "state": "present",
      "sha256": "a97f56f433f5dd817dfb6a3861860634c34d72d1f6ce125ee56424ccee7d8cf1",
      "git_blob": "404a6df27b74c3feee1645429dbf3f8765d38dcc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "skills/econ-design/SKILL.md",
      "state": "present",
      "sha256": "5bc44a280fedfc48fc7db194d06d907968deb09001f8da8925448db8ff8a0057",
      "git_blob": "5a490db17e158eea05d76036ec83774458a4de45",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "skills/econ-design/references/designs.md",
      "state": "present",
      "sha256": "cc98ea05b73f992d9fde15fc809b658cf7d4e49aee131ac180f4de00d3981284",
      "git_blob": "502456dd376c965bf512de4e987c503962c0c7fc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "skills/econ-literature/SKILL.md",
      "state": "present",
      "sha256": "164910ca504d0f828c2f2f123428aae42081866955f66b7a625bc35492960fd4",
      "git_blob": "9bc411a70513e584706362bfdbd297ae9dc3f683",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "skills/econ-review/SKILL.md",
      "state": "present",
      "sha256": "0b91f2725b0455d0d910143b368653cbff31aa4168804a9ec1a365259d34893d",
      "git_blob": "048da2eafdd12e91d934c99ad280eee0528ff778",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "skills/econ-review/references/oversight.md",
      "state": "present",
      "sha256": "f8f55602e313f8bebd51cdf78a80b2e458fc90c55cf304f8f9953b03c36a169e",
      "git_blob": "750c97d55a9b8edb09edfe768d571be76b4b4f7a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "skills/econ-writing/SKILL.md",
      "state": "present",
      "sha256": "d4e69c1aed637e72d521a9cff9b60849265f8b0f62dfa6d7084f6623e30c449a",
      "git_blob": "13a66e7823ad7a410ddf456f81731e97a308655b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "skills/econ-writing/agents/openai.yaml",
      "state": "present",
      "sha256": "909db8360fa94ffebd95e74be67902b8afb5bb15a438318c52ba386a0f4ec600",
      "git_blob": "7df861dfe015b40a4931492e323eb042d4994d25",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "skills/econ-writing/references/paper-workflow.md",
      "state": "present",
      "sha256": "6ca33453716ef90a15b7326aeec09b6a9af35045b5ec874fd98421aa15f34aec",
      "git_blob": "efa49d3f8240c6a9148e030a953dffe4d20fa51a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
    },
    {
      "path": "skills/economics-checked-instructions/SKILL.md",
      "state": "present",
      "sha256": "c7d7abbdb431642582a797d261ab3c8c7de54cc59c890c5e78a98564fbd6f8b7",
      "git_blob": "27954ea2e3e7a62d596615d92cd7c102be865b47",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "72f2c0891b5a9452f53c83bdea2681bb317f0038"
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
