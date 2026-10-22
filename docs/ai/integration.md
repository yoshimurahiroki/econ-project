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
  "source_base_commit": "4cd364b570b5a364581beee009df409d344f78a8",
  "source_state": "working",
  "common_content_id": "841e89a8a9d60271c59196aaae720047b97ce080628d1afbcb90fcfa1f41bf99",
  "target_repository": "github.com/yoshimurahiroki/econ-project",
  "paths": [
    {
      "path": ".agents/AGENTS.md",
      "state": "present",
      "sha256": "f21deab27df67a078feb01a9635feaa4298792f8bb904d8adee7917e747cc05e",
      "git_blob": "8401c4f203472f1a4f4d5d42db72d19c2399104e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/argument.py",
      "state": "present",
      "sha256": "fbf3b34c3febd21208526e44b6494ea543b10e3d011c2e05950192226a655909",
      "git_blob": "1829e3fee0a056fbf1fd95ee08017b112e0195bf",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/argument.schema.json",
      "state": "present",
      "sha256": "3bde57438e6fe255e7cd3a525bfe0b9b4ade8f4c2eae2a41fe1850bf41e7a013",
      "git_blob": "4397bb0feed6a22c198025f3789fad2f77b44503",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/codex_hooks.py",
      "state": "present",
      "sha256": "af49379b64dbb776ab5e8c5b8ae12f8f51dbb2c774e26a19a57f644cfb8ea320",
      "git_blob": "899761c5cbc028c091a5bf7ad07ccf37ee0dd967",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/local_checks.md",
      "state": "present",
      "sha256": "0e293b8818d8011b5f7622ecd5a675b4ed5754045363f5e1ac1a9e9b93a2ca09",
      "git_blob": "a70526122cf5003e85a5bed6527f7358fc13535c",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/local_checks.py",
      "state": "present",
      "sha256": "3d5734bbfa4862fd25ee2f6233b3fdebc98ee7d9d2d981da5eff9ea4efde0385",
      "git_blob": "85782f05746141be8aa3bc97c1dfed2f7123a3a1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/native_check.md",
      "state": "present",
      "sha256": "43d02628e72ebac05e3ce321b761640338a32814611a773dd648c493f04057a6",
      "git_blob": "1b3e08c5b3567e469f0985205fbd4495959a16f2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/native_check.py",
      "state": "present",
      "sha256": "efadb90fd74173bbe85452c18e7527dbe845dfeaa3b32c551860d0af039a5099",
      "git_blob": "015aa93da026a9c1ad8b1276f2eacdfb4016038c",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/native_run.md",
      "state": "present",
      "sha256": "7c0983b51eb0c39c46d276f1d81651886ea57f89100961c7ad2b91763b0f23d7",
      "git_blob": "1ca623c7d5b8128cebaf2b37cc5567afb58392ef",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/native_run.py",
      "state": "present",
      "sha256": "c7174f6b33260a22438fbb6dc7c2f7c278de0b9175611c522ba14782914bac35",
      "git_blob": "611dd24e23637a021d21551883ca84df00d9db0d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/paragraph.py",
      "state": "present",
      "sha256": "9aaefb9fbfa4904f1682ad64a10689fc28deeb15de26a1baa9e6b748dd7a3764",
      "git_blob": "0bf963a49903f192b1a5e86c86e232083be1ca33",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/paragraph.schema.json",
      "state": "present",
      "sha256": "1bc8fd4382a7861bf0c8905b5c5b7b39ececcf25083cafba0fe81e9d83936df0",
      "git_blob": "1765fb6ee780b4f3e9be04a3479aab3d92c82b75",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/policy_assets.py",
      "state": "present",
      "sha256": "775de776170dbdacef9834d18252917a1019389ab4e9c4a3f9be5e8d2b48f4e8",
      "git_blob": "12b8c6280107278e86dbf31bbe4eae632b6d766f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/publication.md",
      "state": "present",
      "sha256": "61c475a55fdd46c07d642a1b433efb3b49a1e90d8c5a7e1604cd6bff9dc97432",
      "git_blob": "080cebc7d7cddee1379e1e295111c3997d8a6443",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/requirements_check.md",
      "state": "present",
      "sha256": "4275b227742dee85a9c1bda1c070e3d37041c8789a111568e27be7def5fb7cb4",
      "git_blob": "c48d312d04fba435bedc2ea2cab308323675b5c9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/requirements_check.py",
      "state": "present",
      "sha256": "3586e6170d23c77080647f88cd6c09026e11c45835b2e92e318ac91683bf8747",
      "git_blob": "e29565611e61184c4bf5895da6ce1d6aa635a2f2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/state.md",
      "state": "present",
      "sha256": "aab9dc34e04fa2872eb4040f387d127a8c6e39d20f0ce64b3d98164caad484e2",
      "git_blob": "a5592c8d5915cbb32092a2540e27a0ac8d38b285",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/harness/state.py",
      "state": "present",
      "sha256": "187ed869eb7e5642bf94662772e269e7dd4fd970505f31a8e2e140acabc6286c",
      "git_blob": "77b450bed31bdba0b78f340ae0a422e181b28408",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
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
      "path": ".agents/profiles/default-micro/PROFILE.md",
      "state": "present",
      "sha256": "6b4e475fb3786c6006b26893824a05f9c40aeccb174ba1ec811face85b8c22b0",
      "git_blob": "809aceb9f90152bb37f6e813db612cc559bbd062",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/profiles/default-micro/extended-introduction-en.md",
      "state": "present",
      "sha256": "0b1d9f9511b5d32cc935c4d7c75b24bf01f94ef48f1ec7b330218d508e810b34",
      "git_blob": "834688a8d352f80a6ac4cc0b96fbe4f831dfad74",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/profiles/default-micro/extended-introduction-ja.md",
      "state": "present",
      "sha256": "cb49bab9fbb949538056f82e7560d715a3a6c648f663ea14af2b77e833bec03b",
      "git_blob": "84c9e720bfec8a585613ed516f91047c9c5f78bb",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/profiles/default-micro/short-examples-en.md",
      "state": "present",
      "sha256": "e395b60c46f6ba98e614bdab1b118ead92e7ca05560641d43ba5b75a8c83a08b",
      "git_blob": "9fafab070f78b4299f8c8611f4c3083e6514497e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/profiles/default-micro/short-examples-ja.md",
      "state": "present",
      "sha256": "4147294992356f95fb21d7484164ff56cf9adae9919d1fd1e989eb911ae05fa2",
      "git_blob": "1953cb16b796b7001b9be33f7c3804fc3fc87a56",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/quality/policy_manifest.json",
      "state": "present",
      "sha256": "92e183215ac57f91a5ea2470d848511fde416d1e0a999ec9d3f2279178f18154",
      "git_blob": "c5e6890caa6a1b363dddc8eb13f88ed0c9e186ce",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/quality/prose_rules.json",
      "state": "present",
      "sha256": "b8a4858b2cb185abec04f3d26772ce3c13c21e12beaaadb3700cd3112becfda5",
      "git_blob": "80f833b3633013a5cc6604659af408bae98b5dc3",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/quality/prose_rules.md",
      "state": "present",
      "sha256": "d918a5b89a251dae228bb61daf380751982a3b109aafdb1e9a8b38e19ee6e377",
      "git_blob": "293976240d723a66e4fdb09ed692a07f26dc87f1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/registry/operations.json",
      "state": "present",
      "sha256": "9b7ad8a88703e0fa4ec9a48394f4555f26da8d9664969ac95848e5f8762c622e",
      "git_blob": "cb0b26142a96f74d0bdfec0989bd8b4e72b06622",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/registry/placements.json",
      "state": "present",
      "sha256": "f83f807390a24d4a9f7dfd9c47ced33754078912ef4fccc6ca33e38771b55153",
      "git_blob": "cdcb7a2ad80bfd9ae89f31a3e89f195258e1f8cc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/registry/resources.json",
      "state": "present",
      "sha256": "e65f10bc11dadedd8e77ad983c84f93f08cf470375eae2f522dac01347fe1bfc",
      "git_blob": "b038326f82ffc8d266626bbd607dab77316f9e2b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/runtime/CONTROL.md",
      "state": "present",
      "sha256": "62126a9a74a00dda2484e8eafbda862b72899f3903ad25624c65ee97d09ef224",
      "git_blob": "8814dab2f31a5361e0e28f6e119235f4eef654b5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/runtime/CORE.md",
      "state": "present",
      "sha256": "6d62304fb1d76dbd3f8ae1c12fa2b215ac9ba74db929fca45105814788f66f81",
      "git_blob": "445a3b7d498857972917bdc070ab164920b5cec8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/runtime/DECIDE.md",
      "state": "present",
      "sha256": "3c89d70facdd919f9c5c72e721c5d574834a129ac286fc4d694c524fbc280354",
      "git_blob": "4631ce06121b68b78909e3592cfefb1d66037eba",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/runtime/EXECUTION.md",
      "state": "present",
      "sha256": "1a4748600b22a61c7039a8bae0e593b03fbad8c8198701cb2e02ecbb717a9a13",
      "git_blob": "9d30016adf0a4ea748febe1005f2e7025ad6cd16",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/runtime/PROSE.md",
      "state": "present",
      "sha256": "ef72a27ea308ae66fe8ead523e9f49b0527c98018e32d6334ffe3ed2867cb514",
      "git_blob": "028dadab39a6130d0ba809321dd3347b2f421838",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/runtime/TEAM.md",
      "state": "present",
      "sha256": "36ab34202dbf77f30a290f4235882631b26663b873a5021b0a6382b7fc7755f1",
      "git_blob": "b524a07306b30d3cc29a7b92ec3bb4f91fe4f8f0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/scripts/route_registry.py",
      "state": "present",
      "sha256": "a392856fd2d92c939242442a429798ad1633594c538caa671798c94e9b115603",
      "git_blob": "39ead8d39be1836646cb9640114029313e041079",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
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
      "sha256": "138871678b341e3c214574acedbb62f759230b81f275342b3267ae30dad63fea",
      "git_blob": "0df61199e8326298ab425f9c51e218cd53ee791a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/skills/econ-data/references/implementation.md",
      "state": "present",
      "sha256": "949f19c182e486e514fbaad78606d00c9925dbcaca131a5192d2d5cdd54e6d5a",
      "git_blob": "7c3016625eda1dc9b41604bf11adfefe11302e30",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/skills/econ-data/references/reproducible-workflow.md",
      "state": "present",
      "sha256": "a4e944cdf1f38c6bcc22825c5822839d865b1b45346a34bb39d28b70eef05279",
      "git_blob": "4ec66c1039257d3acd892fce7a3cf14e56c47712",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/skills/econ-design/SKILL.md",
      "state": "present",
      "sha256": "930eb1587ab0a3d8153707f7e6606ef9a96c7a943b95532d5b00583283391ec9",
      "git_blob": "922fed1e8accc5d6b22848c532b1fdcdb92b90f0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/skills/econ-design/references/designs.md",
      "state": "present",
      "sha256": "22c1fd49b8b0bf2fb20b81aaa1292c95dcbc15b4f3936969fa70ac92bcfacc11",
      "git_blob": "67036d975b7ba00cbc208e34a15dc768034abd44",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
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
      "sha256": "9331bfcf15401f9ca59795945c39a1767ac2a36f30b937464111728ea2e26475",
      "git_blob": "ac89b61a693fb8006dd3cedcd3f294a6e9456a4a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
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
      "sha256": "e39a1d23c5f15d82e8ba8abdced95cf3c8dd9d48aec587a137bd2ade1ed35110",
      "git_blob": "58bce1f7a7f2e92e3d9dfe1265be9e6da4c35053",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/skills/econ-review/references/oversight.md",
      "state": "present",
      "sha256": "f8f55602e313f8bebd51cdf78a80b2e458fc90c55cf304f8f9953b03c36a169e",
      "git_blob": "750c97d55a9b8edb09edfe768d571be76b4b4f7a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
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
      "sha256": "be2a14dc436c466ac06776e33856f4d58449dbc5399a000c774ad8d1e77085e3",
      "git_blob": "6fdfcbb1e83e17698561ab7923655da20e82e8ec",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/skills/econ-writing/agents/openai.yaml",
      "state": "present",
      "sha256": "0b240d8469d087232c9aaa617e3cf6e4db6d20b6a72c1df961175c3be557d01c",
      "git_blob": "655b9d6ad34ec5c7e4c9c545aa5389c6f7ec5ab9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/skills/econ-writing/references/paper-workflow.md",
      "state": "present",
      "sha256": "8643ea052054c2e6afad273020087e648e52c3cbab020e1e9907cfc578a5ec21",
      "git_blob": "445df5c46807b461f36d42168e0bb813b2f412f5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/skills/econ-writing/references/paragraph-workflow.md",
      "state": "present",
      "sha256": "3f431fc0bf0c444c6d5e0ce267a5a04884eda7e8915f8d6081f25f8d1e80a1c2",
      "git_blob": "ea6e7042528743f1bbee2880ceecb72e4d33aa75",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": ".agents/skills/economics-checked-instructions/SKILL.md",
      "state": "present",
      "sha256": "75d29b2cd750a4d22d75942b21d11edb487590fc5fffa9330b83e9ef24c85fa8",
      "git_blob": "e7b2861cbbd4e565a6d7a69992fe61990ed770fb",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
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
      "path": "ECON_INDEX.md",
      "state": "present",
      "sha256": "478ee028681b282e8564c2e106c3d257967085d71c7b70100072834364334887",
      "git_blob": "03f8e8b49a605798d9e0f7fee9a383a27d8e1a1b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "OPTIONAL_INPUTS.md",
      "state": "present",
      "sha256": "34e0ce93c1c2dd094ba8d05615e65146e27e768794adebe43a5b62f216e15ce8",
      "git_blob": "822694879670f31550d4f2513f7ac26e96b43dcc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "PROJECT_INSTRUCTIONS.txt",
      "state": "present",
      "sha256": "36ef14b0e0106b4945b7bf4af5c52115deb7e90349196e33bd99cf03e3b95616",
      "git_blob": "ec30b864c0b88492e7469262f25d50615cb44291",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
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
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "docs/ai/config-templates/README.md",
      "state": "present",
      "sha256": "79d77ee0cffd70c04ef4884485ed124a21d83aba0786a7054c132d75950dfa87",
      "git_blob": "97ec119bcae6bac54dc9b0f39a8208709100a410",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "docs/ai/config-templates/claude-mcp.example.json",
      "state": "present",
      "sha256": "7e098a33b20cda19ae9067ffc8252f2637bf0314963893df85110fe3120fee63",
      "git_blob": "e29ee95ea2e7cdc213561f0a75252c43d28d51de",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "docs/ai/config-templates/codex.example.toml",
      "state": "present",
      "sha256": "c57023f63a938b1d62c9c66f5d6f6c0dbb001e496aa9813bbf3d6a5980e38b05",
      "git_blob": "be298aabfb36b8954160f39686750a294dad8527",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "docs/ai/config-templates/mcp.example.json",
      "state": "present",
      "sha256": "d8e397af03b5b032f21d0aa967086f0c78b33c87b76f2e9898ae0a144df7de02",
      "git_blob": "da39e4ffafe816be90259a3f68b763a3f71b93ed",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "docs/ai/plugin-integration.md",
      "state": "present",
      "sha256": "28ab3ae51de52e2ea6ef463a9329f9b8a908ca845dfce7d917e7c3012a452609",
      "git_blob": "8d37f2d10408ebc21e815b1ca8e80ca07a27e9e6",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
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
      "sha256": "7a7a6b5a3741d093acf6d80a8e17190557112d0a1cb22f4949b88f0f19ae7f35",
      "git_blob": "760a8006bf6e7183fd5bfee9de9f475d0551ac93",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "docs/ai/resources.md",
      "state": "present",
      "sha256": "50e49433980afbfa083917ba020e70f0274300aeb5bc753a807f2624fda77118",
      "git_blob": "b0a1ddae6e948e1648b369ab688030338c577fbb",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/argument.py",
      "state": "present",
      "sha256": "fbf3b34c3febd21208526e44b6494ea543b10e3d011c2e05950192226a655909",
      "git_blob": "1829e3fee0a056fbf1fd95ee08017b112e0195bf",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/argument.schema.json",
      "state": "present",
      "sha256": "3bde57438e6fe255e7cd3a525bfe0b9b4ade8f4c2eae2a41fe1850bf41e7a013",
      "git_blob": "4397bb0feed6a22c198025f3789fad2f77b44503",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/codex_hooks.py",
      "state": "present",
      "sha256": "af49379b64dbb776ab5e8c5b8ae12f8f51dbb2c774e26a19a57f644cfb8ea320",
      "git_blob": "899761c5cbc028c091a5bf7ad07ccf37ee0dd967",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/local_checks.md",
      "state": "present",
      "sha256": "c9df41b68d1aeeefe2ed6a0c2fa5fdd6ec44da1348303e63f78f284dc1501984",
      "git_blob": "5d3e954c637ea95cd38cd47cb615708b02807d5a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/local_checks.py",
      "state": "present",
      "sha256": "3d5734bbfa4862fd25ee2f6233b3fdebc98ee7d9d2d981da5eff9ea4efde0385",
      "git_blob": "85782f05746141be8aa3bc97c1dfed2f7123a3a1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/native_check.md",
      "state": "present",
      "sha256": "eacc3099f79b450310dbcf11e87ca747218097f80d3e1fc08caa1095ffe131ec",
      "git_blob": "41982d375eef8611c0e61f3b7caf7e59901a7412",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/native_check.py",
      "state": "present",
      "sha256": "efadb90fd74173bbe85452c18e7527dbe845dfeaa3b32c551860d0af039a5099",
      "git_blob": "015aa93da026a9c1ad8b1276f2eacdfb4016038c",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/native_run.md",
      "state": "present",
      "sha256": "6065017432682e614fd8e384ce513170222838ca9eed9a79a9ca43b27a4ec5bf",
      "git_blob": "405e1340864933c1e98dc8b24de1d7400b47822c",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/native_run.py",
      "state": "present",
      "sha256": "c7174f6b33260a22438fbb6dc7c2f7c278de0b9175611c522ba14782914bac35",
      "git_blob": "611dd24e23637a021d21551883ca84df00d9db0d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/paragraph.py",
      "state": "present",
      "sha256": "9aaefb9fbfa4904f1682ad64a10689fc28deeb15de26a1baa9e6b748dd7a3764",
      "git_blob": "0bf963a49903f192b1a5e86c86e232083be1ca33",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/paragraph.schema.json",
      "state": "present",
      "sha256": "1bc8fd4382a7861bf0c8905b5c5b7b39ececcf25083cafba0fe81e9d83936df0",
      "git_blob": "1765fb6ee780b4f3e9be04a3479aab3d92c82b75",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/policy_assets.py",
      "state": "present",
      "sha256": "775de776170dbdacef9834d18252917a1019389ab4e9c4a3f9be5e8d2b48f4e8",
      "git_blob": "12b8c6280107278e86dbf31bbe4eae632b6d766f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/publication.md",
      "state": "present",
      "sha256": "61c475a55fdd46c07d642a1b433efb3b49a1e90d8c5a7e1604cd6bff9dc97432",
      "git_blob": "080cebc7d7cddee1379e1e295111c3997d8a6443",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/requirements_check.md",
      "state": "present",
      "sha256": "73edc472d8c66deb1195d6300b9ee172da0690f743602ef2cc862e143c0a2961",
      "git_blob": "33b40573042e0393440803cb31f7f76e8faaddb2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/requirements_check.py",
      "state": "present",
      "sha256": "3586e6170d23c77080647f88cd6c09026e11c45835b2e92e318ac91683bf8747",
      "git_blob": "e29565611e61184c4bf5895da6ce1d6aa635a2f2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/state.md",
      "state": "present",
      "sha256": "d267567f881731aa82226b7d6995da0570eb6b08f3ee585b6ce7339129fc5e25",
      "git_blob": "2e32586b8cea19bedc32933585e854557d8e15ca",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/state.py",
      "state": "present",
      "sha256": "187ed869eb7e5642bf94662772e269e7dd4fd970505f31a8e2e140acabc6286c",
      "git_blob": "77b450bed31bdba0b78f340ae0a422e181b28408",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/test_argument.py",
      "state": "present",
      "sha256": "7420df6fa26d35053705b125f983729dbb65d4a7b83215b91a8e6dc3a9dcdf69",
      "git_blob": "6dab28f613f2e0a492048e7bfa23294b66f30ce7",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/test_argument_regressions.py",
      "state": "present",
      "sha256": "1c60176c741a5f4ef5fb8b71d95d27fe369fb9f5e02713fd26c0108f38b87494",
      "git_blob": "d65bcef97ed3f1ea415134d65b6877e78e5bf4d5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/test_paragraph.py",
      "state": "present",
      "sha256": "ac8d59c80402903e982cdef2eb829a2f1a4211a16167fa13a956a66446be7a24",
      "git_blob": "5df8feb0e1bc2e41b7f054fafabe074a76d15362",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/test_paragraph_regressions.py",
      "state": "present",
      "sha256": "5ade200d1f981478571d52c8342a0b751b9a849dbaa0c94fb73bf5cf341b9b3a",
      "git_blob": "cca894667cbc3a898abdb64583dbb0d9f5433982",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/test_state.py",
      "state": "present",
      "sha256": "b0ff4178de611822856fad1dbebd2899d41fdab88a0c499d78edbdd6d9d381be",
      "git_blob": "e396315580b1b34e303ccb88e8942729fc8d8a8d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "harness/test_writing_integration.py",
      "state": "present",
      "sha256": "036f861d403aeecea968576cd38584a2ce9cf9ea69d96307375fedd98fb31a61",
      "git_blob": "d51d181e823b454b74a86ba2c20edc781578c1a3",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "profiles/default-micro/PROFILE.md",
      "state": "present",
      "sha256": "6b4e475fb3786c6006b26893824a05f9c40aeccb174ba1ec811face85b8c22b0",
      "git_blob": "809aceb9f90152bb37f6e813db612cc559bbd062",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "profiles/default-micro/extended-introduction-en.md",
      "state": "present",
      "sha256": "0b1d9f9511b5d32cc935c4d7c75b24bf01f94ef48f1ec7b330218d508e810b34",
      "git_blob": "834688a8d352f80a6ac4cc0b96fbe4f831dfad74",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "profiles/default-micro/extended-introduction-ja.md",
      "state": "present",
      "sha256": "cb49bab9fbb949538056f82e7560d715a3a6c648f663ea14af2b77e833bec03b",
      "git_blob": "84c9e720bfec8a585613ed516f91047c9c5f78bb",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "profiles/default-micro/short-examples-en.md",
      "state": "present",
      "sha256": "e395b60c46f6ba98e614bdab1b118ead92e7ca05560641d43ba5b75a8c83a08b",
      "git_blob": "9fafab070f78b4299f8c8611f4c3083e6514497e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "profiles/default-micro/short-examples-ja.md",
      "state": "present",
      "sha256": "4147294992356f95fb21d7484164ff56cf9adae9919d1fd1e989eb911ae05fa2",
      "git_blob": "1953cb16b796b7001b9be33f7c3804fc3fc87a56",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "quality/policy_manifest.json",
      "state": "present",
      "sha256": "399c8f7b0e3ef8c3161b4c64afef121675c864363ed898795e9674c186adf950",
      "git_blob": "084ec39e0d95b29e01a8d14c3375bfd653892fe9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "quality/prose_rules.json",
      "state": "present",
      "sha256": "b8a4858b2cb185abec04f3d26772ce3c13c21e12beaaadb3700cd3112becfda5",
      "git_blob": "80f833b3633013a5cc6604659af408bae98b5dc3",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "quality/prose_rules.md",
      "state": "present",
      "sha256": "c793dca71f7dba85c3d04faecc0b4ab25c5aa305a698a3274fe2169f0b8f7826",
      "git_blob": "4dfc2afe09560fd06219f0feaebbafcb2baa5d31",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "references/repository-policy/.agents/AGENTS.md",
      "state": "present",
      "sha256": "cafc59de32d85efa1b2dd219936e00920bd17fb439cdd7a9b93401e1478f6267",
      "git_blob": "0e328520b47fa076db49ecbf69b487c8e059f6d2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "references/repository-policy/.antigravityrules",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "references/repository-policy/.claude/AGENTS.md",
      "state": "present",
      "sha256": "cafc59de32d85efa1b2dd219936e00920bd17fb439cdd7a9b93401e1478f6267",
      "git_blob": "0e328520b47fa076db49ecbf69b487c8e059f6d2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "references/repository-policy/.clinerules",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "references/repository-policy/.cursor/rules/01_project_policy.mdc",
      "state": "present",
      "sha256": "6d8d91e33b2190b2da8edba15dd46350ebc3a394334ea7e2f57c4c141fb06ec2",
      "git_blob": "1f2bf852b6ba2c45f2edd1b5f8ac737be77aa6c0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "references/repository-policy/.cursorrules",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "references/repository-policy/.gemini/GEMINI.md",
      "state": "present",
      "sha256": "cafc59de32d85efa1b2dd219936e00920bd17fb439cdd7a9b93401e1478f6267",
      "git_blob": "0e328520b47fa076db49ecbf69b487c8e059f6d2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "references/repository-policy/.github/copilot-instructions.md",
      "state": "present",
      "sha256": "cafc59de32d85efa1b2dd219936e00920bd17fb439cdd7a9b93401e1478f6267",
      "git_blob": "0e328520b47fa076db49ecbf69b487c8e059f6d2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "references/repository-policy/.windsurfrules",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "references/repository-policy/AGENTS.md",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "references/repository-policy/CLAUDE.md",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "references/repository-policy/CODEX.md",
      "state": "present",
      "sha256": "cdba8d7384055991db4fcf03ae4808090fa3d483322d7b471e448752c6def107",
      "git_blob": "81ed24cb0684e0cfdf31cec462a455f22f861772",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "registry/operations.json",
      "state": "present",
      "sha256": "9b7ad8a88703e0fa4ec9a48394f4555f26da8d9664969ac95848e5f8762c622e",
      "git_blob": "cb0b26142a96f74d0bdfec0989bd8b4e72b06622",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "registry/placements.json",
      "state": "present",
      "sha256": "f83f807390a24d4a9f7dfd9c47ced33754078912ef4fccc6ca33e38771b55153",
      "git_blob": "cdcb7a2ad80bfd9ae89f31a3e89f195258e1f8cc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "registry/resources.json",
      "state": "present",
      "sha256": "e65f10bc11dadedd8e77ad983c84f93f08cf470375eae2f522dac01347fe1bfc",
      "git_blob": "b038326f82ffc8d266626bbd607dab77316f9e2b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "runtime/CONTROL.md",
      "state": "present",
      "sha256": "5c9a1e1edb9b9c069334fcf5d771bad28fb21d298adf909c7ad8ebd22f421c1a",
      "git_blob": "3a275f2ad3a81222a5fa08368226d6e3ca08be04",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "runtime/CORE.md",
      "state": "present",
      "sha256": "83bf3e68e669401f2c9ae8f76efca7e7a17a074a7250d197559ce61857e5d2a4",
      "git_blob": "d80900bcd95f7f180dd8a253ea41072db33c2204",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "runtime/DECIDE.md",
      "state": "present",
      "sha256": "3c89d70facdd919f9c5c72e721c5d574834a129ac286fc4d694c524fbc280354",
      "git_blob": "4631ce06121b68b78909e3592cfefb1d66037eba",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "runtime/EXECUTION.md",
      "state": "present",
      "sha256": "4157cad813f4d4c9b2bc0423181a9d93218a13b2fc678957f3827c2baa8fd73d",
      "git_blob": "53bb56ab297f940e0bc19fd7644b669b9eccce22",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "runtime/PROSE.md",
      "state": "present",
      "sha256": "0096cf536702b001e0eb479185360822c98adfcd4b7feb45ff58be10d492c358",
      "git_blob": "196f10ccc7143869f75464a3c311c4ba927c4317",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "runtime/TEAM.md",
      "state": "present",
      "sha256": "36ab34202dbf77f30a290f4235882631b26663b873a5021b0a6382b7fc7755f1",
      "git_blob": "b524a07306b30d3cc29a7b92ec3bb4f91fe4f8f0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/__init__.py",
      "state": "present",
      "sha256": "483ac5ccf6287140cba89cb9ea470f9bcce24b3e2efdaaa1de3e1251438034c3",
      "git_blob": "1fc5a64100ae58e3ad92d02cc9ce7b4126f041ea",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/check_instruction_links.py",
      "state": "present",
      "sha256": "11caf4e468e6959c978b67c066b07f3a261e3fe71f4d5b634038aef156092fe7",
      "git_blob": "351d248153744ebc165306de628da2f1f91dc4a9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/export_project.py",
      "state": "present",
      "sha256": "0ee6af56bf2f75610e258292edf170c7bc85df4e44087eb75c15e3a060ef7c3f",
      "git_blob": "5a5b0982cbd46938d2f7862c2a37e1d7908b104f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/pack_context.sh",
      "state": "present",
      "sha256": "683360d226686020e02f939e1bfa6baf0cdaaabfcfe5981e7135dfe49b1386b9",
      "git_blob": "5f14fe582e9f4ee842a24d07ae2f7a16d8d777d1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/route_registry.py",
      "state": "present",
      "sha256": "a392856fd2d92c939242442a429798ad1633594c538caa671798c94e9b115603",
      "git_blob": "39ead8d39be1836646cb9640114029313e041079",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/setup_extensions.sh",
      "state": "present",
      "sha256": "917c8bee2c31f08c9c2c86f60e1eaf4b5c685bd582afcce33fc0378996ed3cb1",
      "git_blob": "f2aad4d755d38bdcf02c7010a99e1925c9951175",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/setup_ide_mcp.sh",
      "state": "present",
      "sha256": "b35800f79f1dc5e95d8d875d668aa5dc27738f929764c14072dccd0e34af3fc9",
      "git_blob": "1b5abda4c59df9e91973c9e83f73469903bb59be",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/sync_common_core.py",
      "state": "present",
      "sha256": "ce79903cc76d6ff4545e340f9a09e0c165fd6b3e6bc9753b734560037b771411",
      "git_blob": "61c654f174246b9dd333117b96a16e934183ebad",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/test_configuration_tools.py",
      "state": "present",
      "sha256": "bbff9ec63935445c1d74800a89b6510ace71af8d1c48a0db7772306d4b30e9c4",
      "git_blob": "af3ccf0b42fea3213d6c028068a4cdf8fa30e90f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/test_export_project.py",
      "state": "present",
      "sha256": "ed9f50483832920d56a1723b6268405f9909dce08b286168f15c3f83c4e66f5a",
      "git_blob": "a98adb00f459a9ce432170653c687152052d908f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/test_instruction_links.py",
      "state": "present",
      "sha256": "d1587c35b9e929a2b09fd62d4264a4e8a9ca153b4c6cdd56746a337bb5307e68",
      "git_blob": "fa5b2317222fd5b09478b1f1323f394b2cba1e24",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/test_setup_ide_mcp.py",
      "state": "present",
      "sha256": "1a96b0a96ae68206b3c3072a87471f2d08aa592822d32d30856f9c4e4d5bf3cb",
      "git_blob": "2b0222ecbcfb61a3d94ce9c05fec3522540ccce7",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "scripts/test_sync_common_core.py",
      "state": "present",
      "sha256": "47c76029474c503a4812415e1279aa4f3222a71ba161596f7e68405c7475ca24",
      "git_blob": "2555fbc44b566b3b9b8df00a0c4519163652f187",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/econ-data/SKILL.md",
      "state": "present",
      "sha256": "dd72e481256ff37dd79640a03f2a6f0570002caf63bc33e7acea429f09a30652",
      "git_blob": "562404fcf14bd600aae0c136e35346dc875a0433",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/econ-data/references/implementation.md",
      "state": "present",
      "sha256": "61e9a53d5206eff0cd7207e7f18887403e04ca28b7fd2f348bd6a1fd2d98a966",
      "git_blob": "02caa6031f2c94c6f0759dffdf4e288f9bf535d9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/econ-data/references/reproducible-workflow.md",
      "state": "present",
      "sha256": "a97f56f433f5dd817dfb6a3861860634c34d72d1f6ce125ee56424ccee7d8cf1",
      "git_blob": "404a6df27b74c3feee1645429dbf3f8765d38dcc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/econ-design/SKILL.md",
      "state": "present",
      "sha256": "61537e19fc2d4329ed029962979e46db2838c2197624513f11bba1006c21bc10",
      "git_blob": "392b95e7d735403bff78b1ffe55a2f2f4bf5449c",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/econ-design/references/designs.md",
      "state": "present",
      "sha256": "cc98ea05b73f992d9fde15fc809b658cf7d4e49aee131ac180f4de00d3981284",
      "git_blob": "502456dd376c965bf512de4e987c503962c0c7fc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/econ-literature/SKILL.md",
      "state": "present",
      "sha256": "74c9e09aedc34b617ea5b64ad25e25147795507df865d6a0151de4aa1691f6fd",
      "git_blob": "7b11083302871898e79ab6b6a41c5599fb991b4f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/econ-review/SKILL.md",
      "state": "present",
      "sha256": "acbf33b8181d037b9b91d60a37a2f014bfc5eaea4a9ddc2652d40d0f9ddf2279",
      "git_blob": "389dbeb5a51006213ed5962db69d87a4ffc251ac",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/econ-review/references/oversight.md",
      "state": "present",
      "sha256": "f8f55602e313f8bebd51cdf78a80b2e458fc90c55cf304f8f9953b03c36a169e",
      "git_blob": "750c97d55a9b8edb09edfe768d571be76b4b4f7a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/econ-writing/SKILL.md",
      "state": "present",
      "sha256": "3d57189d41b90a671a69e776883250372ffe0a63cfa78a4f565355a7ef8670f8",
      "git_blob": "b744b6b8491b9a254b5f6611007687c7ef123fbe",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/econ-writing/agents/openai.yaml",
      "state": "present",
      "sha256": "0b240d8469d087232c9aaa617e3cf6e4db6d20b6a72c1df961175c3be557d01c",
      "git_blob": "655b9d6ad34ec5c7e4c9c545aa5389c6f7ec5ab9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/econ-writing/references/paper-workflow.md",
      "state": "present",
      "sha256": "8643ea052054c2e6afad273020087e648e52c3cbab020e1e9907cfc578a5ec21",
      "git_blob": "445df5c46807b461f36d42168e0bb813b2f412f5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/econ-writing/references/paragraph-workflow.md",
      "state": "present",
      "sha256": "ad65727cb5e368f7dc5cda6aa0e8de7769089cccbc7712c45c75dda937dcbb67",
      "git_blob": "dd8f97eccb7c66b1a1afe10a5eb662b434423687",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
    },
    {
      "path": "skills/economics-checked-instructions/SKILL.md",
      "state": "present",
      "sha256": "75d29b2cd750a4d22d75942b21d11edb487590fc5fffa9330b83e9ef24c85fa8",
      "git_blob": "e7b2861cbbd4e565a6d7a69992fe61990ed770fb",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "4cd364b570b5a364581beee009df409d344f78a8"
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
