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

Keep the original R00-R08 attachments unchanged. For a complete instruction-field replacement, paste PROJECT_INSTRUCTIONS.txt. To update a separately maintained field, replace its bridge block with BRIDGE_INSTRUCTIONS.txt and remove conflicting inherited common-policy and writing instructions. Attach the exported files. ECON_INDEX.md gives native econ-paper, econ-writing, econ-edit and econ-style priority for paper explanation, writing, wording revision and profile work. Scientific research uses the original R02-R05 or R07 under the supplied R00 router. References to R01, R06 and R08 resolve to the corresponding native methods. An explicit native-provider request uses the exported native fallback for a research deliverable.

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

`--task` selects the deliverable's method role; `--support` names a dependency method and `--references` names an exact repository-relative reference file. Both options are repeatable and require `--task`. `--task` and `--skills` are exclusive. Bridge task snapshots use the selected native primary for paper explanation, writing, wording revision or profile work. A bridge workflow snapshot uses native econ-workflow as coordinator, with a separate supplied R00 primary for each substantive research deliverable. Other research snapshots retain the supplied R02-R05/R07 provider and include the selected native research body as its available fallback.

Task snapshots include the selected bodies, explicit references and applicable writing-profile resources. Inclusion makes a resource available; the current task determines whether it is read. ECON_INDEX.md lists the selected roles and files. Project additions come from the `export-project:v1` block in [repo_context.md](repo_context.md).

Use a fresh output directory outside the repository. The exporter enforces the 8,000-character instruction-field limit. Included links use exported filenames; omitted repository files use their recorded immutable revision. SOURCE.md records source versions, original and generated hashes and snapshot identity, including working-file content. Regenerate the selected snapshot when its source instructions change.

## Custom exemplars

[econ-assertive](../../.agents/skills/econ-assertive/SKILL.md) selects source examples for writing. The `writing_profile` value in [project context](repo_context.md) records the persistent choice. `--style-profile` selects a snapshot's task profile without changing that value. Writing or wording tasks include the selected profile; default-micro remains available as a source of examples.

To create or revise a profile, request econ-style with the source papers, language and target section. Name a destination to save it; a repository-save request without a path uses docs/ai/custom-style.md. Creation and saving preserve the persistent choice. Change the project-context value only for an explicit request to adopt or switch the profile.

## Handoff

A requested handoff uses the existing task record for the revision, evidence, authorized work, results and next action relevant to the transfer. Keep private data and credentials in their existing storage.

## Coordinated research execution

Econ-workflow coordinates interdependent research work and owns its integrated result. Bounded tasks use their relevant specialist directly. Read team-execution for concurrent write ownership, state resumption or requested usage accounting. Econ-review assesses the requested claim or artifact; its oversight notes support an independent assessment or a contested execution finding. Independent review uses a different worker or session.

Existing research task records remain the canonical assignment and scientific-decision source. If no operational store exists, the portable stdlib helper at `.agents/skills/econ-workflow/scripts/team_state.py` saves task state in the already ignored `.agents/state/` directory. Its `--help` lists creation, transitions, usage import and active inspection. It neither launches inference nor modifies platform permissions. Keep the store and Codex JSONL transcripts local. Record output and passed-verification evidence before completion, and inspect saved input/output hashes before resumption.

Codex execution uses the user's verified installed CLI and normal ChatGPT login. Confirm version, authentication and available tools at setup; keep user model and permission settings. Native delegation and existing execution records precede external orchestrator adoption. Free package licensing does not establish free inference. The templates do not enable local LLMs, paid API fallback or credit purchases.

<!-- common-core-receipt:v2 -->
```json
{
  "schema_version": 2,
  "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
  "source_base_commit": "7902d4225363d753fc501a7ba716945c26a152c6",
  "source_state": "committed",
  "common_content_id": "2b93039700a7985e4fffbeece4729554474eac6d36675f1339a3ae5a8213614a",
  "target_repository": "github.com/yoshimurahiroki/econ-project",
  "paths": [
    {
      "path": ".agents/AGENTS.md",
      "state": "present",
      "sha256": "e348a9d4f1a32b26c56044a73f729200cadd057e694deffea570ca6dbe9cd5dc",
      "git_blob": "a699a9e3b9521f612a0c2bd26261b65c38f6a970",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-assertive/SKILL.md",
      "state": "present",
      "sha256": "ff105321c8770db0f6448de91b0d1c0c5bd281d3fac8a04d161e6cfbb1cde54a",
      "git_blob": "8b348725a665c7d0bc0d29a9b733c1aec489b9a7",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-assertive/agents/openai.yaml",
      "state": "present",
      "sha256": "d4733c0ce7c612b920d155207500ef8d9f2097bac1b308cf2d919422cc106e67",
      "git_blob": "dee094ccea339ad98679240513fca09c75056bab",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-assertive/references/default-micro.md",
      "state": "present",
      "sha256": "670a7d067c99dd7c82b4c9fe5f6b09dcecee35d7d308dc4a534365aad1945e38",
      "git_blob": "284ec46b74154685cd00fbad5006bd20df76ebc1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-assertive/references/patterns.md",
      "state": "present",
      "sha256": "97eff0a7ba981766ff190b5c593593a518de15d99879b5de6a442f0788fb4933",
      "git_blob": "3142c9e1ee7fcc14f8f038ad3121f1aaeab3ea1a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-data/SKILL.md",
      "state": "present",
      "sha256": "68454e943de1a5eefff51f88690cec196d7611d372cc6e36bfdc518a9aa77c37",
      "git_blob": "031f74f64e90e95a3ec3aa772baa100458984433",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-data/references/implementation.md",
      "state": "present",
      "sha256": "40f8779e0a4b317c165a9eaff6b812b048b8a8b77a01fedc2d63714734af3af7",
      "git_blob": "fc8754dde914621e093c73b241206aa7ead85f61",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-data/references/reproducible-workflow.md",
      "state": "present",
      "sha256": "d7fd53bdbd66ec77a1ec03df3dc23285e1a58d66994852891b42b47fb804ae22",
      "git_blob": "d5562fbbf0d565633de2d506f4bfc463dcb313b8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-design/SKILL.md",
      "state": "present",
      "sha256": "6f01b4d6d4c9b5d47d5b50f451e53b12a40f7d0e2e5054b874589d2494579e75",
      "git_blob": "b1fe188971bff1fd967ea72e3e4e8e0ea600bc2e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-design/references/designs.md",
      "state": "present",
      "sha256": "8d02e140c377d41530998003b3f573525a75a1fefb0bb3cb4433a946acd80a60",
      "git_blob": "7f526e342d079bdfdd6bcff5da40c554c43d84bc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-edit/SKILL.md",
      "state": "present",
      "sha256": "cb8510e03ee23a7ba69fe20b3afea1b911308b64db04ee69e3a4e3e81853e702",
      "git_blob": "87b79dafab99102532efe872e5314ea7c04ee656",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-handoff/SKILL.md",
      "state": "present",
      "sha256": "dff27f196bf3ec4c872d1c972cda0f905bf82c4b33861ea34d67eea04d28af8c",
      "git_blob": "956366395daa04091809d73d48b9b80ad9f2a7fc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-handoff/references/handoff.md",
      "state": "present",
      "sha256": "2b853325770da0c9838cc44388faee09eb5aa99eb782cc70ebb2ba7be98b37d5",
      "git_blob": "cfe7d4ac3949acaa5e3a27b0f20258e4dd189238",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-literature/SKILL.md",
      "state": "present",
      "sha256": "c7cf23ebf3f5ed6c1f0f013992c05eaf4b7092a6ac9c5413cedf390b2c7c9130",
      "git_blob": "46ba6e382f91e47cbbc9fc879b82a717f2952152",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-paper/SKILL.md",
      "state": "present",
      "sha256": "9b33302d96216369fb66421364bf893249ab2d75b2172cacb495e6dcd52cf130",
      "git_blob": "107e064023caf0ed65631c6b553f9320b3ddc68f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-review/SKILL.md",
      "state": "present",
      "sha256": "f7c472bee6c35fcb5e757e500dfa9721233c66f87e78c25f7152f64478f93d67",
      "git_blob": "f1c93878775ff7354eb47ff5f10290e4f3af4472",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-review/references/oversight.md",
      "state": "present",
      "sha256": "647b797da3348ad21e1c2fcab083742125d25a89225b1e43f28be04c1697d6e4",
      "git_blob": "f020082ff9dc14a6168877a5f431b8826c1a40a1",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-style/SKILL.md",
      "state": "present",
      "sha256": "988135a3e708eadaeb46f8aa2bb5681e49b0eb0af022a132fa09e3a569642e6a",
      "git_blob": "0107b99ec431369cceff1c74326264bc49c52102",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-workflow/SKILL.md",
      "state": "present",
      "sha256": "86a5effe8ac7b95a2e96882699882c206d039e642f4f6567f50fbf0e932297ae",
      "git_blob": "d2cc695c09010a2f1f6b47330e1773c8ff211df5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-workflow/references/descriptive-model.md",
      "state": "present",
      "sha256": "6b3eccdf5907af6a7c86221d14516aff4d81c4a54ed1466c24f6e5c68dc42d12",
      "git_blob": "119fbe91deae9fc9084b3b4e9a8ff8d0ab1db1a8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-workflow/references/team-execution.md",
      "state": "present",
      "sha256": "ec8622bff2ac49d07982f19af4cde204d5fc7f486640151a2ebf463f38c5fbe1",
      "git_blob": "1678fa6cf496830e26bf8c78d0b0252d3d0f6b6d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-workflow/scripts/team_state.py",
      "state": "present",
      "sha256": "9721cd0e6e7e145ba8ec83af0b7dacdbc3896d0ea034ff24c65d2a8b4bc0a19e",
      "git_blob": "33a3607581c44ffb2d3f413388d8151066ba573e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-workflow/scripts/test_team_state.py",
      "state": "present",
      "sha256": "64c3666b4a875e293099e2e40669483ac8c2646413f65c7a0e2a7c31860a820d",
      "git_blob": "63e590ee4cc45fc74833a1e90bb214c9a9e32583",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".agents/skills/econ-writing/SKILL.md",
      "state": "present",
      "sha256": "c50cbd130d3a021e799e8c4f5077471913ec6ee700601924c5b2c082f0fede3d",
      "git_blob": "7f08f8e0d0083ff6733506f261430d8b81f55ada",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".claude/AGENTS.md",
      "state": "present",
      "sha256": "e348a9d4f1a32b26c56044a73f729200cadd057e694deffea570ca6dbe9cd5dc",
      "git_blob": "a699a9e3b9521f612a0c2bd26261b65c38f6a970",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".cursor/rules/01_project_policy.mdc",
      "state": "present",
      "sha256": "adf647e1c9af5396fb121b2d6ac8ffec650833da6deae33d96c2d25cbb465510",
      "git_blob": "cbc8df4bedae7b9b0a2871bea951f6a60be18d23",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".cursorrules",
      "state": "present",
      "sha256": "8cf44156d854d96ca1908c25d7f91d2ad0f95fc9b0bb3ed8ab0139c0035c7d60",
      "git_blob": "6de0bb55fe95b2eed54a0548464cc485d001c3e6",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".gemini/GEMINI.md",
      "state": "present",
      "sha256": "9e475650f183f0b043de0d05c6e0677f491d54f9fcc8f1a2a3b8d3b9dad60d55",
      "git_blob": "9396740efa914c5e999800240480e35ba6181b94",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": ".github/copilot-instructions.md",
      "state": "present",
      "sha256": "b772e08542240ea8098a8ec663105acd3171d0e9a4a5b72b8f735ec58af901c1",
      "git_blob": "2c6d60bcd43d4df21d8da6317bfec0faca5258a8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "AGENTS.md",
      "state": "present",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "CLAUDE.md",
      "state": "present",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "CODEX.md",
      "state": "present",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "docs/ai/compiled_ai_skills.md",
      "state": "present",
      "sha256": "48d316d1ac94a59a143b0ae464d6b251fb7b441b7cbcf38eabaabb915bbe09b2",
      "git_blob": "54e255126fcf7dd80f48dbd026df190c0ecde726",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "docs/ai/config-templates/README.md",
      "state": "present",
      "sha256": "1adf3d97d7b4a926d0d253987e1d4c706bb50b6c0c9263eb685c0c566948b8be",
      "git_blob": "24040bc1ed19e9919b9e88e93a4989e4072c8df3",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "docs/ai/config-templates/claude-mcp.example.json",
      "state": "present",
      "sha256": "7e098a33b20cda19ae9067ffc8252f2637bf0314963893df85110fe3120fee63",
      "git_blob": "e29ee95ea2e7cdc213561f0a75252c43d28d51de",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "docs/ai/config-templates/codex.example.toml",
      "state": "present",
      "sha256": "c57023f63a938b1d62c9c66f5d6f6c0dbb001e496aa9813bbf3d6a5980e38b05",
      "git_blob": "be298aabfb36b8954160f39686750a294dad8527",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "docs/ai/config-templates/mcp.example.json",
      "state": "present",
      "sha256": "d8e397af03b5b032f21d0aa967086f0c78b33c87b76f2e9898ae0a144df7de02",
      "git_blob": "da39e4ffafe816be90259a3f68b763a3f71b93ed",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "docs/ai/project_bridge.txt",
      "state": "present",
      "sha256": "44879162073a056098b78804a2134fbe96988dad6cf5da581ea51f513935737c",
      "git_blob": "cda4001d8e532b244ac29c01f72a333072b9376d",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "docs/ai/project_instructions.txt",
      "state": "present",
      "sha256": "135753dc1a1f5f6074570b79eb7092cf61fabacd59bddb04c03f249a3721e37e",
      "git_blob": "a38f911b50d0d6efe5de27d2034d6361afbd8ccd",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "scripts/export_project.py",
      "state": "present",
      "sha256": "39e1ebe14e23e1639216fd5ea5f126c216b7b01ae65d76ffd27f39c9ea59c794",
      "git_blob": "b472beabfa96db25073484aa5317c4dcefc2b380",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "scripts/pack_context.sh",
      "state": "present",
      "sha256": "f74a948b3fc7e3e43d4c68b89f2010cc54190d36d1a95c79abadad349ebb7155",
      "git_blob": "7174135411df6697c22589b25f0fdb9f50784e7a",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "scripts/setup_ide_mcp.sh",
      "state": "present",
      "sha256": "69240f5c7ef14618fff70f072ffbab635496d303d542122e12f476939bf8a0b0",
      "git_blob": "db03ad944ff24607af333e421c6a80c280932440",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "scripts/sync_common_core.py",
      "state": "present",
      "sha256": "02e7f4dc0fdea8147295a7d05fb6e90d11caf7d20ecf0e38c3bc245fc30c73fc",
      "git_blob": "8a08ced8cd8e680d164db310aebaeda16a540f1a",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "scripts/test_setup_ide_mcp.py",
      "state": "present",
      "sha256": "33d977ad402871445215d55330817cc63718a9ca164dbe463df5786784eab7dc",
      "git_blob": "0ded4f6348a1264581bb68ccbf4d897033cfbdc7",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
    },
    {
      "path": "scripts/test_sync_common_core.py",
      "state": "present",
      "sha256": "2d0a694d4d20f8979150f988e5f9a471de1c7f4813e2f93806a46dfc5e9e9179",
      "git_blob": "c795517bd8c3a9dc46e189311bc5835fb8cfbda5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "7902d4225363d753fc501a7ba716945c26a152c6"
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
