# Project integration

Repository skills run in the coding environment. Project attachments are snapshots identified in SOURCE.md. A repository task uses the current policy and the files relevant to the request.

## Common core

The explicit managed paths in [sync_common_core.py](../../scripts/sync_common_core.py) define the shared instructions and tools. Each user chooses the source, destinations and paths. Origins are identified by their complete host/owner/repository path. Repositories with separate histories and different owners are supported.

Compare before applying. Supply the reviewed source HEAD and every destination HEAD. A working source also requires the comparison's `common_content_id` through `--expect-source-content`. Commit and push are separate operations.

```sh
SOURCE=/path/to/shared-template
TARGET=/path/to/research-repository

python scripts/sync_common_core.py --source "$SOURCE" --target "$TARGET"

python scripts/sync_common_core.py --source "$SOURCE" --target "$TARGET" --apply \
  --expect-source-head "$(git -C "$SOURCE" rev-parse HEAD)" \
  --expect-head github.com/example/research-repository="$(git -C "$TARGET" rev-parse HEAD)"
```

The default is a read-only comparison of `COMMON_PATHS`. Repeat `--target` for multiple destinations or `--path` for an explicit subset. The source and destination roots must be distinct and match their Git origins and pinned HEADs. Ordinary startup, research work and environment setup do not synchronize.

A first synchronization adopts absent files. Existing files require an explicit `--claim 'HOST/OWNER/REPO:PATH=SHA256:MODE'` using the destination fingerprint reported by comparison. This claim establishes ownership of that particular path at that particular version. The three-way comparison then checks the previous receipt, current destination and new source. Uncommitted, staged and committed custom changes are protected. Resolve only the reported paths and claim their reviewed current fingerprints when choosing to replace them. Synchronization never stages files or clears the index.

Use `--migrate-receipt` to migrate a v1 receipt whose recorded source commit, blob, hash and mode can be verified. Source switching requires a separate reviewed ownership decision. Each v2 receipt records the source identity, input commit, selected hashes and modes, adoption state and destination identity. It contains no host paths or credential-bearing URLs. Project context, integration prose, source history, research records and environment dependencies remain project-owned.

Use `--release PATH` to relinquish receipt ownership while retaining the local file and index. Released paths cannot be copied or deleted by subsequent synchronization. The explicit --release-local-configs option releases the nine LOCAL_CONFIG_PATHS; combine it with explicit --path entries when also copying common files. Remove public tracking separately with `git rm --cached -- PATH`; keep the runtime file locally and distribute its public example definition. The [configuration examples](config-templates/README.md) are managed common files; runtime MCP configurations and their generation state are local.

Deletions require `--delete PATH` with that source path absent. Moves require `--move OLD=NEW` with source OLD absent and NEW present. Existing destination paths still require their recorded baseline or a matching ownership claim. These operations stay within the explicitly selected paths.

The script checks all destinations before writing. It detects changes to source inputs, destination files, HEADs, origins and indexes during application. It writes receipts after content, verifies the result and rolls back its own writes on failure while retaining concurrent user changes. Exit codes are 0 for equality or successful application, 1 for comparison differences and 2 for a refused or incomplete operation.

Git `core.filemode=false` supports content updates and replay at the existing tracked mode. A mode transition requires `core.filemode=true` in a filesystem that tracks execute bits. The synchronizer refuses that transition instead of silently staging index metadata. Run the temporary-repository checks with `python scripts/test_sync_common_core.py`.

For these upstream templates, maintainers edit common functionality in econ-project-mini and explicitly synchronize tested changes to econ-project and selected research projects. This maintenance arrangement adds no default destination or owner restriction to a user's copy.

## Existing R00-R08 Project

```sh
python scripts/export_project.py --profile bridge --output /tmp/econ-bridge-new
```

Keep the unchanged existing R00-R08 method attachments. For a complete instruction-field replacement, paste PROJECT_INSTRUCTIONS.txt. To update a separately maintained field, replace its bridge block with BRIDGE_INSTRUCTIONS.txt and remove conflicting inherited common-policy, profile and final-dispatch text. Attach the exported files. ECON_INDEX.md records their roles; supplied R00_ROUTER.md resolves the existing research method for the requested deliverable. An explicit native-provider request uses the exported native fallback for that deliverable.

## Standalone Project

```sh
python scripts/export_project.py --profile standalone --output /tmp/econ-all-new
python scripts/export_project.py --profile standalone --skills econ-paper econ-design \
  --output /tmp/econ-subset-new
```

Paste PROJECT_INSTRUCTIONS.txt into the field and attach the other exported files. Standalone without `--task` or `--skills` retains all 11 skill bodies and their references. `--skills` selects an available subset. A study entry point is included when declared by the project block.

## Task snapshots

```sh
python scripts/export_project.py --profile standalone --task econ-paper \
  --references .agents/skills/econ-workflow/references/descriptive-model.md \
  --output /tmp/econ-paper-new
python scripts/export_project.py --profile standalone --task econ-edit \
  --style-profile default-micro --output /tmp/econ-edit-new
```

`--task` selects the deliverable's method role; `--support` names a dependency method and `--references` names an exact repository-relative reference file. Both options are repeatable and require `--task`. `--task` and `--skills` are exclusive. Bridge task snapshots keep the supplied R00-R08 provider and include the selected native body as its available fallback. A requested profile operation selects econ-style.

Task snapshots include the selected bodies, explicit references and applicable writing-profile resources. Inclusion makes a resource available; the current task determines whether it is read. ECON_INDEX.md lists the selected roles and files. Project additions come from the `export-project:v1` block in [repo_context.md](repo_context.md).

Use a fresh output directory outside the repository. The exporter enforces the 8,000-character instruction-field limit. Included links use exported filenames; omitted repository files use their recorded immutable revision. SOURCE.md records source versions, original and generated hashes and snapshot identity, including working-file content. Regenerate the selected snapshot when its source instructions change.

## Custom exemplars

[econ-assertive](../../.agents/skills/econ-assertive/SKILL.md) owns writing-profile selection. The `writing_profile` value in [project context](repo_context.md) records the persistent choice. `--style-profile` selects a snapshot's task profile without changing that value. Writing or wording tasks include the selected profile and default-micro for a needed function absent from it.

To create or revise a profile, request econ-style with the source papers, language and target section. Name a destination to save it; a repository-save request without a path uses docs/ai/custom-style.md. Creation and saving preserve the persistent choice. Change the project-context value only for an explicit request to adopt or switch the profile.

## Handoff

A requested handoff uses the existing task record for the revision, evidence, authorized work, results and next action relevant to the transfer. Keep private data and credentials in their existing storage.

<!-- common-core-receipt:v2 -->
```json
{
  "schema_version": 2,
  "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
  "source_base_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5",
  "source_state": "committed",
  "common_content_id": "5ede446f3a05b576b1e3cae34de16d4c3903ebdce7d49bb2ebc8b215a10883a1",
  "target_repository": "github.com/yoshimurahiroki/econ-project",
  "paths": [
    {
      "path": ".agents/AGENTS.md",
      "state": "present",
      "sha256": "e348a9d4f1a32b26c56044a73f729200cadd057e694deffea570ca6dbe9cd5dc",
      "git_blob": "a699a9e3b9521f612a0c2bd26261b65c38f6a970",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-assertive/SKILL.md",
      "state": "present",
      "sha256": "4ca18449da85108f82388f4321370f2904a3b01d53915009545c7e435e9dc5ba",
      "git_blob": "e1ac06d9ff28ae447d6cba648f57f5c922af3aa1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-assertive/agents/openai.yaml",
      "state": "present",
      "sha256": "d4733c0ce7c612b920d155207500ef8d9f2097bac1b308cf2d919422cc106e67",
      "git_blob": "dee094ccea339ad98679240513fca09c75056bab",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-assertive/references/default-micro.md",
      "state": "present",
      "sha256": "63d338b8fd4108bddfd3a5c5625ea899f979162862abd8a4ae1605bcb407a996",
      "git_blob": "84208cd9491ff63940b3c01eee81a8c3d54e4491",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-assertive/references/patterns.md",
      "state": "present",
      "sha256": "7829a155ca59ba93f8b2870f0dcd007c1b15b8e000a5c9d8404e1d526e170057",
      "git_blob": "89a3d5d7ce31839b5307d716b8dccce34d558293",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-data/SKILL.md",
      "state": "present",
      "sha256": "cccf3bb83ad5d90e4a48e5e53b6a0bc864a4f50f09b1ffa8330028c316048480",
      "git_blob": "0d2a0c1bb220da577900854e18748dca9fffbee0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-data/references/implementation.md",
      "state": "present",
      "sha256": "f474c414ca2a0f7f69ece93b29609e50397364b95ed2fb14dfb5b81533f3c9c2",
      "git_blob": "9bddc44671d7cca14ba5d12c6b2c8a087579d621",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-data/references/reproducible-workflow.md",
      "state": "present",
      "sha256": "d7fd53bdbd66ec77a1ec03df3dc23285e1a58d66994852891b42b47fb804ae22",
      "git_blob": "d5562fbbf0d565633de2d506f4bfc463dcb313b8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-design/SKILL.md",
      "state": "present",
      "sha256": "6bbb9fc4eaabf947d047d627ca310ba3901e02b52a4280509b411e8159b3b63f",
      "git_blob": "0c55e6388b4eee28c573d299d9ee8ee33d306b4f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-design/references/designs.md",
      "state": "present",
      "sha256": "b2df29345e6ea0bc1b3e27bd0483685eab1e140afe923827224738e7fb3cc1dd",
      "git_blob": "b19a7fd3f510b8ea15fba9647b859d21c9a86fe0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-edit/SKILL.md",
      "state": "present",
      "sha256": "a28f49742b609f1f78468d863b1eb3cc1e439caf4cdeb1dd2027adf4eaaf873f",
      "git_blob": "6ab02a0ddeb06fb6e68e2351eb62bb8c95932676",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-handoff/SKILL.md",
      "state": "present",
      "sha256": "67d218bb78d06c45676904d532559df97a7ed97c0ece9315a45b325bac2722cf",
      "git_blob": "2309285f27927e16c5115f89cc013e3305b99f4a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-handoff/references/handoff.md",
      "state": "present",
      "sha256": "a2cb46b36ad4bb4ce90d06559d8f4055817789ae8a44cfdc23460cc4672a0d1b",
      "git_blob": "88de79983187c941e4fab55dbcc1d1e161ef72e9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-literature/SKILL.md",
      "state": "present",
      "sha256": "35eec693992b49bdb5580c6541894d6f5c104a5833aede0b56352e568c00f776",
      "git_blob": "5f5bec251ad998872cf4e5ba95b0d90cd3456bc8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-paper/SKILL.md",
      "state": "present",
      "sha256": "baafc8a120acac17eeb65462991a6f9f8eba12b195e0c4ee11553f16dade0887",
      "git_blob": "8e0f828583fea376c864499325696c020e8a28a2",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-review/SKILL.md",
      "state": "present",
      "sha256": "c251b7891b0c0a48ec852839cc2f9946ba9267413fe23e437c5059360abab486",
      "git_blob": "0d9fecb3540bd98abb79c72afcd59cff17bafde6",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-review/references/oversight.md",
      "state": "present",
      "sha256": "81f9a2b0d43247e215f614e4629c54db9618861ce450698f969e6eb7e390e74f",
      "git_blob": "f5736f5cfb7835ef958e5392f0e040ccf980d0be",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-style/SKILL.md",
      "state": "present",
      "sha256": "461d1b4b940d35d97b0d590ba960aec36cade89e206657fb50a2e8baa8995147",
      "git_blob": "0a8b6d2f1b7cad21a0efabe19622993d375e8e27",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-workflow/SKILL.md",
      "state": "present",
      "sha256": "20fe89b13ad46e7334f516e9fe5628ce0f89b4de8ba497cd85e81d15c4762645",
      "git_blob": "e2d7607e7795fd31e66c70382bfa6ff5dc5e67ea",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-workflow/references/descriptive-model.md",
      "state": "present",
      "sha256": "6b3eccdf5907af6a7c86221d14516aff4d81c4a54ed1466c24f6e5c68dc42d12",
      "git_blob": "119fbe91deae9fc9084b3b4e9a8ff8d0ab1db1a8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-workflow/references/team-execution.md",
      "state": "present",
      "sha256": "3f8dd0f11661b15be933ea218df283959231f0b8ede6fc9ea49bdae9c46d2805",
      "git_blob": "f48518a586f1d2ab209c612be4de1c6d052dcce4",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-workflow/scripts/team_state.py",
      "state": "present",
      "sha256": "4ae96ed80e0737386d5b81348e3a58d63e619cf41a1eead2f42703451f40693f",
      "git_blob": "d9f7d31e90f135ecc928762d8cec5ad990a5c4ec",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-workflow/scripts/test_team_state.py",
      "state": "present",
      "sha256": "c8416f85fb06eaf8834e7e45708d207f9a1b402a3edc3f1fe0a04a5d30b1b8a4",
      "git_blob": "c863b8bebaf0c704ac8d18d84a56f298aff8ccdc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".agents/skills/econ-writing/SKILL.md",
      "state": "present",
      "sha256": "a60beb8a08b6674e3bc6a493c43a5d35e1885059493e1851b7ef22ce4f341e97",
      "git_blob": "b933866b20238fc9fc79a1efba80cea53ca0ffef",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".claude/AGENTS.md",
      "state": "present",
      "sha256": "e348a9d4f1a32b26c56044a73f729200cadd057e694deffea570ca6dbe9cd5dc",
      "git_blob": "a699a9e3b9521f612a0c2bd26261b65c38f6a970",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".cursor/rules/01_project_policy.mdc",
      "state": "present",
      "sha256": "adf647e1c9af5396fb121b2d6ac8ffec650833da6deae33d96c2d25cbb465510",
      "git_blob": "cbc8df4bedae7b9b0a2871bea951f6a60be18d23",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".cursorrules",
      "state": "present",
      "sha256": "ccc798e821ce9988d686b5f8e7f80d4e57513d5bbe8ec3fdd603231de658ff5b",
      "git_blob": "3e26f346af323cfe6dbff601568a3840645656d3",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".gemini/GEMINI.md",
      "state": "present",
      "sha256": "9e475650f183f0b043de0d05c6e0677f491d54f9fcc8f1a2a3b8d3b9dad60d55",
      "git_blob": "9396740efa914c5e999800240480e35ba6181b94",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": ".github/copilot-instructions.md",
      "state": "present",
      "sha256": "b772e08542240ea8098a8ec663105acd3171d0e9a4a5b72b8f735ec58af901c1",
      "git_blob": "2c6d60bcd43d4df21d8da6317bfec0faca5258a8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "AGENTS.md",
      "state": "present",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "CLAUDE.md",
      "state": "present",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "CODEX.md",
      "state": "present",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "docs/ai/compiled_ai_skills.md",
      "state": "present",
      "sha256": "b03d31fa10e3043638e145a78947c71d94c9b2694ea9fc46e97a95ae4d49a89a",
      "git_blob": "6edc0c5e53ba8b5485eac71af3c6bec5bc336cc5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "docs/ai/config-templates/README.md",
      "state": "present",
      "sha256": "1adf3d97d7b4a926d0d253987e1d4c706bb50b6c0c9263eb685c0c566948b8be",
      "git_blob": "24040bc1ed19e9919b9e88e93a4989e4072c8df3",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "docs/ai/config-templates/claude-mcp.example.json",
      "state": "present",
      "sha256": "7e098a33b20cda19ae9067ffc8252f2637bf0314963893df85110fe3120fee63",
      "git_blob": "e29ee95ea2e7cdc213561f0a75252c43d28d51de",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "docs/ai/config-templates/codex.example.toml",
      "state": "present",
      "sha256": "c57023f63a938b1d62c9c66f5d6f6c0dbb001e496aa9813bbf3d6a5980e38b05",
      "git_blob": "be298aabfb36b8954160f39686750a294dad8527",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "docs/ai/config-templates/mcp.example.json",
      "state": "present",
      "sha256": "d8e397af03b5b032f21d0aa967086f0c78b33c87b76f2e9898ae0a144df7de02",
      "git_blob": "da39e4ffafe816be90259a3f68b763a3f71b93ed",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "docs/ai/project_bridge.txt",
      "state": "present",
      "sha256": "fe4c2abcd08c5675579b86eecaeaf5760646f10bf8b09e4f66f13979896be76e",
      "git_blob": "4e1a6b417812b4bdb2bde417c00b380d398f95b5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "docs/ai/project_instructions.txt",
      "state": "present",
      "sha256": "e0bc6975bcc071778cc6edae3afc27c41595c557644558c1e2567caacc84e253",
      "git_blob": "092068c0a841a84a3e94c4bca6ca2fb182fee38c",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "scripts/export_project.py",
      "state": "present",
      "sha256": "b0b3e947e5e546cb462b4e4e7b21a57468c0d8d67da92b86e7f7b9ba4bbc3e9a",
      "git_blob": "7435dfb4af79129767ffba285991dae5b5315d0d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "scripts/pack_context.sh",
      "state": "present",
      "sha256": "f74a948b3fc7e3e43d4c68b89f2010cc54190d36d1a95c79abadad349ebb7155",
      "git_blob": "7174135411df6697c22589b25f0fdb9f50784e7a",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "scripts/setup_ide_mcp.sh",
      "state": "present",
      "sha256": "69240f5c7ef14618fff70f072ffbab635496d303d542122e12f476939bf8a0b0",
      "git_blob": "db03ad944ff24607af333e421c6a80c280932440",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "scripts/sync_common_core.py",
      "state": "present",
      "sha256": "02e7f4dc0fdea8147295a7d05fb6e90d11caf7d20ecf0e38c3bc245fc30c73fc",
      "git_blob": "8a08ced8cd8e680d164db310aebaeda16a540f1a",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "scripts/test_setup_ide_mcp.py",
      "state": "present",
      "sha256": "33d977ad402871445215d55330817cc63718a9ca164dbe463df5786784eab7dc",
      "git_blob": "0ded4f6348a1264581bb68ccbf4d897033cfbdc7",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
    },
    {
      "path": "scripts/test_sync_common_core.py",
      "state": "present",
      "sha256": "2d0a694d4d20f8979150f988e5f9a471de1c7f4813e2f93806a46dfc5e9e9179",
      "git_blob": "c795517bd8c3a9dc46e189311bc5835fb8cfbda5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "a22adffdbfcbcdf088199ac8294ff418543ab0a5"
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
