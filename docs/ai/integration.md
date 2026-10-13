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

## Standalone Project

```sh
python scripts/export_project.py --profile standalone --output /tmp/econ-all-new
python scripts/export_project.py --profile standalone --skills econ-paper econ-design \
  --output /tmp/econ-subset-new
```

Paste PROJECT_INSTRUCTIONS.txt into the field and attach the other exported files. Standalone without `--task` or `--skills` retains all 11 skill bodies and their references. `--skills` selects an available subset. A study entry point is included when declared by the project block.

## Task snapshots

For bounded writing or translation, use the ordinary writing snapshot. For a complete research paper, whole-paper argument plan or substantive whole-paper composition from research materials, explicitly select econ-paper support:

```sh
python scripts/export_project.py --profile standalone --task econ-writing \
  --output /tmp/bounded-writing-new
python scripts/export_project.py --profile standalone --task econ-writing \
  --support econ-paper --output /tmp/whole-paper-writing-new
```

Both recipes retain the project's selected writing profile. Select support for a bounded task only when its own source-understanding dependency warrants it. These commands document package selection; they do not automatically route requests or change a live Project's settings.

```sh
python scripts/export_project.py --profile standalone --task econ-paper \
  --references .agents/skills/econ-workflow/references/descriptive-model.md \
  --output /tmp/econ-paper-new
python scripts/export_project.py --profile standalone --task econ-edit \
  --style-profile default-micro --output /tmp/econ-edit-new
```

`--task` selects the deliverable's method role; `--support` names a dependency method and `--references` names an exact repository-relative reference file. Both options are repeatable and require `--task`. `--task` and `--skills` are exclusive.

Task snapshots include econ-workflow as entry, econ-assertive as prose owner, the requested specialist as executor, explicit references and applicable writing-profile resources. Read entry once; support and reference reads continue the same task. ECON_INDEX.md is the active selection; NATIVE_METHOD_INDEX.md preserves the repository ownership map. Inclusion makes a resource available; the current task determines whether it is read. ECON_INDEX.md lists the selected roles and files. Project additions come from the `export-project:v1` block in [repo_context.md](repo_context.md).

Use a fresh output directory outside the repository. The exporter enforces the 8,000-character instruction-field limit. Included links use exported filenames; omitted repository files use their recorded immutable revision. SOURCE.md records source versions, original and generated hashes and snapshot identity, including working-file content. Regenerate the selected snapshot when its source instructions change.

## Custom exemplars

[econ-assertive](../../.agents/skills/econ-assertive/SKILL.md) selects source examples for writing. The `writing_profile` value in [project context](repo_context.md) records the persistent choice. `--style-profile` selects a snapshot's task profile without changing that value. Writing or wording tasks include the selected profile; default-micro remains available as a source of examples.

To create or revise a profile, request econ-style with the source papers, language and target section. Name a destination to save it; a repository-save request without a path uses docs/ai/custom-style.md. Creation and saving preserve the persistent choice. Change the project-context value only for an explicit request to adopt or switch the profile.

## Handoff

A requested handoff uses the existing task record for the revision, evidence, authorized work, results and next action relevant to the transfer. Keep private data and credentials in their existing storage.

## Coordinated research execution

Read econ-workflow once for every new economics task, then use the requested specialist as executor. Support calls and reference reads continue the current task without repeating entry. Econ-workflow coordinates interdependent research work and owns its integrated result; bounded tasks remain bounded. Read team-execution for concurrent write ownership, state resumption or requested usage accounting. Econ-review assesses the requested claim or artifact; its oversight notes support an independent assessment or a contested execution finding. Independent review uses a different worker or session.

Existing research task records remain the canonical assignment and scientific-decision source. If no operational store exists, the portable stdlib helper at `.agents/skills/econ-workflow/scripts/team_state.py` saves task state in the already ignored `.agents/state/` directory. Its `--help` lists creation, transitions, usage import and active inspection. It neither launches inference nor modifies platform permissions. Keep the store and Codex JSONL transcripts local. Record output and passed-verification evidence before completion, and inspect saved input/output hashes before resumption.

Codex execution uses the user's verified installed CLI and normal ChatGPT login. Confirm version, authentication and available tools at setup; keep user model and permission settings. Native delegation and existing execution records precede external orchestrator adoption. Free package licensing does not establish free inference. The templates do not enable local LLMs, paid API fallback or credit purchases.

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
