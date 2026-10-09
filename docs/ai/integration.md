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

A broad research assignment uses econ-workflow as coordinator and the existing specialist for each deliverable. Read its team-execution reference only for delegation, operational state, tool selection or team evaluation. Econ-review's oversight reference provides separate Inspector, Adjudicator, scientific-referee and editorial entry points. Use actual independent workers for independent review.

Existing research task records remain the canonical assignment and scientific-decision source. If no operational store exists, the portable stdlib helper at `.agents/skills/econ-workflow/scripts/team_state.py` saves task state in the already ignored `.agents/state/` directory. Its `--help` lists creation, transitions, usage import and active inspection. It neither launches inference nor modifies platform permissions. Keep the store and Codex JSONL transcripts local. Record output and passed-verification evidence before completion, and inspect saved input/output hashes before resumption.

Codex execution uses the user's verified installed CLI and normal ChatGPT login. Confirm version, authentication and available tools at setup; keep user model and permission settings. Native delegation and existing execution records precede external orchestrator adoption. Free package licensing does not establish free inference. The templates do not enable local LLMs, paid API fallback or credit purchases.

<!-- common-core-receipt:v2 -->
```json
{
  "schema_version": 2,
  "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
  "source_base_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94",
  "source_state": "committed",
  "common_content_id": "ab5793d39bbaaebda6d1076953deb890c1231f1ac00a68bfb2530ef7476700e0",
  "target_repository": "github.com/yoshimurahiroki/econ-project",
  "paths": [
    {
      "path": ".agents/AGENTS.md",
      "state": "present",
      "sha256": "e348a9d4f1a32b26c56044a73f729200cadd057e694deffea570ca6dbe9cd5dc",
      "git_blob": "a699a9e3b9521f612a0c2bd26261b65c38f6a970",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-assertive/SKILL.md",
      "state": "present",
      "sha256": "e2995238410a44e96ed5c7fe0e00afcbd29f24358a7a98218e9da3d026c6fc0e",
      "git_blob": "0e344c8b6cd7ac47cabbce9d7322b5e9756eff08",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": ".agents/skills/econ-assertive/agents/openai.yaml",
      "state": "present",
      "sha256": "d4733c0ce7c612b920d155207500ef8d9f2097bac1b308cf2d919422cc106e67",
      "git_blob": "dee094ccea339ad98679240513fca09c75056bab",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-assertive/references/default-micro.md",
      "state": "present",
      "sha256": "207f6a70f2b5cf138f34ad1e6dc6f82d0b81a023ffd08aae5ed6fc9d61c71ac6",
      "git_blob": "cf1f588c5f701d2da3bbbf2bf58976811011087b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": ".agents/skills/econ-assertive/references/patterns.md",
      "state": "present",
      "sha256": "47a03ed30cb0ed7644ed308d30f8488fd3099d99112f26ee1f7a95fb3b327b3b",
      "git_blob": "17cf13913dcd13e19ed900023f32042bb95785ed",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": ".agents/skills/econ-data/SKILL.md",
      "state": "present",
      "sha256": "cccf3bb83ad5d90e4a48e5e53b6a0bc864a4f50f09b1ffa8330028c316048480",
      "git_blob": "0d2a0c1bb220da577900854e18748dca9fffbee0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-data/references/implementation.md",
      "state": "present",
      "sha256": "40f8779e0a4b317c165a9eaff6b812b048b8a8b77a01fedc2d63714734af3af7",
      "git_blob": "fc8754dde914621e093c73b241206aa7ead85f61",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-data/references/reproducible-workflow.md",
      "state": "present",
      "sha256": "d7fd53bdbd66ec77a1ec03df3dc23285e1a58d66994852891b42b47fb804ae22",
      "git_blob": "d5562fbbf0d565633de2d506f4bfc463dcb313b8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-design/SKILL.md",
      "state": "present",
      "sha256": "66489bc920d5edb7e121d205f20762f71dbac1a42a094b06ee11a94697aba7fd",
      "git_blob": "7a493c404c3ad6a6825358a95967ee6cd5694702",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": ".agents/skills/econ-design/references/designs.md",
      "state": "present",
      "sha256": "b2df29345e6ea0bc1b3e27bd0483685eab1e140afe923827224738e7fb3cc1dd",
      "git_blob": "b19a7fd3f510b8ea15fba9647b859d21c9a86fe0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-edit/SKILL.md",
      "state": "present",
      "sha256": "5b246b8b19d12e15dbaa453be55cecf024ff5660692e882ffcad183e6397d0bd",
      "git_blob": "80a1211e0cccb1cdf2b3cfbc18ce40473d493010",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": ".agents/skills/econ-handoff/SKILL.md",
      "state": "present",
      "sha256": "67d218bb78d06c45676904d532559df97a7ed97c0ece9315a45b325bac2722cf",
      "git_blob": "2309285f27927e16c5115f89cc013e3305b99f4a",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-handoff/references/handoff.md",
      "state": "present",
      "sha256": "a2cb46b36ad4bb4ce90d06559d8f4055817789ae8a44cfdc23460cc4672a0d1b",
      "git_blob": "88de79983187c941e4fab55dbcc1d1e161ef72e9",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-literature/SKILL.md",
      "state": "present",
      "sha256": "a4476a85ab7fa3838377bccabaafd80ceb9418239f2cf6227c097bb4c6a86dbf",
      "git_blob": "bfffdf25ff77851c45c58327d9b7ae8775df4d58",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-paper/SKILL.md",
      "state": "present",
      "sha256": "8e0d2b59200604ae404bc114f2befff25f3b50edccb4ebd1a6472388e554ae9c",
      "git_blob": "48a061d75f183b7c49c31982acee1f74d907ad35",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": ".agents/skills/econ-review/SKILL.md",
      "state": "present",
      "sha256": "6d2dacc1ac8145fa26fe7b59a787db352b5a96aeb8d8261859c3ca8e798590e8",
      "git_blob": "bbf790d8b0ff9103468345716490a655f7aac4ba",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": ".agents/skills/econ-review/references/oversight.md",
      "state": "present",
      "sha256": "7e24a77f084c47b8bc846686ff46e77ca69dd7c58b80d5e406807844c3adb108",
      "git_blob": "00aa90bef647029d8d13d3ec27a8561aa8f2cfcd",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": ".agents/skills/econ-style/SKILL.md",
      "state": "present",
      "sha256": "c598d8712a48cadac38e0c1fc3dc2c449f2677b05e4ccc81e557a3a524c01b0a",
      "git_blob": "e1c1c66e49d3f38884126b5034efe75035ae0edc",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": ".agents/skills/econ-workflow/SKILL.md",
      "state": "present",
      "sha256": "466735f73bfda925ef541dc394731f2f60920e842a0ee4bb659b0dfeba605ade",
      "git_blob": "4f8d7d0f6a18d3e2d831bc35f3dc931da81b27d0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-workflow/references/descriptive-model.md",
      "state": "present",
      "sha256": "5fba016ce5396f7ca4c90f9678491aaa0f3a8a2a0846f195297c73fb3a5ece0d",
      "git_blob": "58bdf968ca3f374a59f11d3aa47c0a5dbb05548f",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-workflow/references/team-execution.md",
      "state": "present",
      "sha256": "9a4045b3d07c8f3aa31da08c6ca687e346e73501dc17bc9b84d729ccbccea67e",
      "git_blob": "bcb8b35f5e8cf7a53309cb0321ee0a8be54529d0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-workflow/scripts/team_state.py",
      "state": "present",
      "sha256": "9721cd0e6e7e145ba8ec83af0b7dacdbc3896d0ea034ff24c65d2a8b4bc0a19e",
      "git_blob": "33a3607581c44ffb2d3f413388d8151066ba573e",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-workflow/scripts/test_team_state.py",
      "state": "present",
      "sha256": "64c3666b4a875e293099e2e40669483ac8c2646413f65c7a0e2a7c31860a820d",
      "git_blob": "63e590ee4cc45fc74833a1e90bb214c9a9e32583",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".agents/skills/econ-writing/SKILL.md",
      "state": "present",
      "sha256": "6e245cb34488f015e3d119008bd4d40758206a693428eaa6939a296dc4f122b5",
      "git_blob": "eb11cc7baa2603e29c454277677fe76e040f3c0b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": ".claude/AGENTS.md",
      "state": "present",
      "sha256": "e348a9d4f1a32b26c56044a73f729200cadd057e694deffea570ca6dbe9cd5dc",
      "git_blob": "a699a9e3b9521f612a0c2bd26261b65c38f6a970",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".cursor/rules/01_project_policy.mdc",
      "state": "present",
      "sha256": "adf647e1c9af5396fb121b2d6ac8ffec650833da6deae33d96c2d25cbb465510",
      "git_blob": "cbc8df4bedae7b9b0a2871bea951f6a60be18d23",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".cursorrules",
      "state": "present",
      "sha256": "ad3aded720c77cc153acb273e7f9f6ff78ed3a3e74a37076d860acab627711e6",
      "git_blob": "6d53e383357a0e6ab14c3d63d98611caeaf37fc0",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": ".gemini/GEMINI.md",
      "state": "present",
      "sha256": "9e475650f183f0b043de0d05c6e0677f491d54f9fcc8f1a2a3b8d3b9dad60d55",
      "git_blob": "9396740efa914c5e999800240480e35ba6181b94",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": ".github/copilot-instructions.md",
      "state": "present",
      "sha256": "b772e08542240ea8098a8ec663105acd3171d0e9a4a5b72b8f735ec58af901c1",
      "git_blob": "2c6d60bcd43d4df21d8da6317bfec0faca5258a8",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "AGENTS.md",
      "state": "present",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "CLAUDE.md",
      "state": "present",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "CODEX.md",
      "state": "present",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "docs/ai/compiled_ai_skills.md",
      "state": "present",
      "sha256": "45e88d63ef5ace2f6c532ecd969ed510072fbc20b9e354c9da75b0d26c07b4b6",
      "git_blob": "c63b5bb1b8b8595e220773761fcfe6d974bf6ca5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": "docs/ai/config-templates/README.md",
      "state": "present",
      "sha256": "1adf3d97d7b4a926d0d253987e1d4c706bb50b6c0c9263eb685c0c566948b8be",
      "git_blob": "24040bc1ed19e9919b9e88e93a4989e4072c8df3",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "docs/ai/config-templates/claude-mcp.example.json",
      "state": "present",
      "sha256": "7e098a33b20cda19ae9067ffc8252f2637bf0314963893df85110fe3120fee63",
      "git_blob": "e29ee95ea2e7cdc213561f0a75252c43d28d51de",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "docs/ai/config-templates/codex.example.toml",
      "state": "present",
      "sha256": "c57023f63a938b1d62c9c66f5d6f6c0dbb001e496aa9813bbf3d6a5980e38b05",
      "git_blob": "be298aabfb36b8954160f39686750a294dad8527",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "docs/ai/config-templates/mcp.example.json",
      "state": "present",
      "sha256": "d8e397af03b5b032f21d0aa967086f0c78b33c87b76f2e9898ae0a144df7de02",
      "git_blob": "da39e4ffafe816be90259a3f68b763a3f71b93ed",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "docs/ai/project_bridge.txt",
      "state": "present",
      "sha256": "beea22932a7ee0cd39a5de9ead42a5abc14aada6d6e580301c76b3d55965e54e",
      "git_blob": "aecb0b1191730ce4da09a3e7ce7015f17071bf3b",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": "docs/ai/project_instructions.txt",
      "state": "present",
      "sha256": "e0bc6975bcc071778cc6edae3afc27c41595c557644558c1e2567caacc84e253",
      "git_blob": "092068c0a841a84a3e94c4bca6ca2fb182fee38c",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "scripts/export_project.py",
      "state": "present",
      "sha256": "70022ff50b27d360951ffbd307b62ad91ce8ccd9318d85bfa488abd9322996ec",
      "git_blob": "37addfa2b2425a46b0602c9c18d84c71ce5f3267",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "f6037b2455ad26d3b979a88e0de9f9dd4a9bdc94"
    },
    {
      "path": "scripts/pack_context.sh",
      "state": "present",
      "sha256": "f74a948b3fc7e3e43d4c68b89f2010cc54190d36d1a95c79abadad349ebb7155",
      "git_blob": "7174135411df6697c22589b25f0fdb9f50784e7a",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "scripts/setup_ide_mcp.sh",
      "state": "present",
      "sha256": "69240f5c7ef14618fff70f072ffbab635496d303d542122e12f476939bf8a0b0",
      "git_blob": "db03ad944ff24607af333e421c6a80c280932440",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "scripts/sync_common_core.py",
      "state": "present",
      "sha256": "02e7f4dc0fdea8147295a7d05fb6e90d11caf7d20ecf0e38c3bc245fc30c73fc",
      "git_blob": "8a08ced8cd8e680d164db310aebaeda16a540f1a",
      "mode": "100755",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "scripts/test_setup_ide_mcp.py",
      "state": "present",
      "sha256": "33d977ad402871445215d55330817cc63718a9ca164dbe463df5786784eab7dc",
      "git_blob": "0ded4f6348a1264581bb68ccbf4d897033cfbdc7",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
    },
    {
      "path": "scripts/test_sync_common_core.py",
      "state": "present",
      "sha256": "2d0a694d4d20f8979150f988e5f9a471de1c7f4813e2f93806a46dfc5e9e9179",
      "git_blob": "c795517bd8c3a9dc46e189311bc5835fb8cfbda5",
      "mode": "100644",
      "source_repository": "github.com/yoshimurahiroki/econ-project-mini",
      "source_commit": "94a0776459f170c3baf0f5fb8a27bf58c54f652c"
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
