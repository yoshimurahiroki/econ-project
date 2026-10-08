# Project integration

Repository skills run in the coding environment. Project attachments are snapshots identified in SOURCE.md. A repository task uses the current policy and the files relevant to the request.

## Common core

[econ-project-mini](https://github.com/yoshimurahiroki/econ-project-mini) is the editing source for the common policy, skills, references, host pointers, indexes, Project templates and exporter. The explicit `COMMON_PATHS` allowlist in [sync_common_core.py](../../scripts/sync_common_core.py) defines the same relative paths copied to econ-project and Ruan. Project context, integration prose, source history, study records, environments and execution recipes remain project-owned.

Compare and apply when preparing publication of a common-core change. Read the current destination HEADs for `--expect-head` immediately before applying.

```sh
cd /tmp/econ-project-mini-instructions-20261008
python scripts/sync_common_core.py --source . \
  --target /tmp/econ-project-instructions-20261008 \
  --target /tmp/ruan-literature-20261005

python scripts/sync_common_core.py --source . \
  --target /tmp/econ-project-instructions-20261008 \
  --target /tmp/ruan-literature-20261005 --apply \
  --expect-head econ-project="$(git -C /tmp/econ-project-instructions-20261008 rev-parse HEAD)" \
  --expect-head Ruan="$(git -C /tmp/ruan-literature-20261005 rev-parse HEAD)"
```

Comparison is read-only. The script records copied source bytes in the destinations' managed common-core receipt; the receipt is the only synchronized part of this document. Exit codes are 0 for equality or successful application, 1 for comparison differences and 2 for a refused or invalid operation. Ordinary task startup and environment setup run neither synchronization nor export.

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

<!-- common-core-receipt:v1 -->
```json
{
  "source_repository": "yoshimurahiroki/econ-project-mini",
  "source_base_commit": "bfd700a2e5f2acfdf26d22fc1e88b89da9923091",
  "common_content_id": "481391cc435653a80f24ce0ee0e3ea7fd03c37d701e59b3cf92d831c058bcf80",
  "source_state": "committed",
  "paths": [
    {
      "path": ".agents/AGENTS.md",
      "git_blob": "a699a9e3b9521f612a0c2bd26261b65c38f6a970",
      "sha256": "e348a9d4f1a32b26c56044a73f729200cadd057e694deffea570ca6dbe9cd5dc"
    },
    {
      "path": ".agents/skills/econ-assertive/SKILL.md",
      "git_blob": "fe9ee15ad7eee8a9eea6774bfbd409f8c9bdeeb9",
      "sha256": "ce4a8b304dc62ad9416ec0e79735b0501c2b3b517d296777c6fa5cbe178ec589"
    },
    {
      "path": ".agents/skills/econ-assertive/agents/openai.yaml",
      "git_blob": "dee094ccea339ad98679240513fca09c75056bab",
      "sha256": "d4733c0ce7c612b920d155207500ef8d9f2097bac1b308cf2d919422cc106e67"
    },
    {
      "path": ".agents/skills/econ-assertive/references/default-micro.md",
      "git_blob": "84208cd9491ff63940b3c01eee81a8c3d54e4491",
      "sha256": "63d338b8fd4108bddfd3a5c5625ea899f979162862abd8a4ae1605bcb407a996"
    },
    {
      "path": ".agents/skills/econ-assertive/references/patterns.md",
      "git_blob": "89a3d5d7ce31839b5307d716b8dccce34d558293",
      "sha256": "7829a155ca59ba93f8b2870f0dcd007c1b15b8e000a5c9d8404e1d526e170057"
    },
    {
      "path": ".agents/skills/econ-data/SKILL.md",
      "git_blob": "0d2a0c1bb220da577900854e18748dca9fffbee0",
      "sha256": "cccf3bb83ad5d90e4a48e5e53b6a0bc864a4f50f09b1ffa8330028c316048480"
    },
    {
      "path": ".agents/skills/econ-data/references/implementation.md",
      "git_blob": "9bddc44671d7cca14ba5d12c6b2c8a087579d621",
      "sha256": "f474c414ca2a0f7f69ece93b29609e50397364b95ed2fb14dfb5b81533f3c9c2"
    },
    {
      "path": ".agents/skills/econ-data/references/reproducible-workflow.md",
      "git_blob": "d5562fbbf0d565633de2d506f4bfc463dcb313b8",
      "sha256": "d7fd53bdbd66ec77a1ec03df3dc23285e1a58d66994852891b42b47fb804ae22"
    },
    {
      "path": ".agents/skills/econ-design/SKILL.md",
      "git_blob": "91c0d1316a0bb3a5fd96f7f3b04f92ebbff33eaf",
      "sha256": "c20d87e0d13ff828a12b7bbd7322d9247adc8533528679de654a118bbafea87a"
    },
    {
      "path": ".agents/skills/econ-design/references/designs.md",
      "git_blob": "b19a7fd3f510b8ea15fba9647b859d21c9a86fe0",
      "sha256": "b2df29345e6ea0bc1b3e27bd0483685eab1e140afe923827224738e7fb3cc1dd"
    },
    {
      "path": ".agents/skills/econ-edit/SKILL.md",
      "git_blob": "f5389269edf446eece7a4ae2f9389fd9e92a2a6d",
      "sha256": "37ddcd11de4a1efc51e94d404909e79085e2c8b2cc61c5ffcb633eba099dcd79"
    },
    {
      "path": ".agents/skills/econ-handoff/SKILL.md",
      "git_blob": "b0119f04e0ea7720eaffe98aa8a037da30c7937d",
      "sha256": "d35a7f72f4896e3280d82583d2c69a149cf552b9ff95b7226177d76891f90e36"
    },
    {
      "path": ".agents/skills/econ-handoff/references/handoff.md",
      "git_blob": "88de79983187c941e4fab55dbcc1d1e161ef72e9",
      "sha256": "a2cb46b36ad4bb4ce90d06559d8f4055817789ae8a44cfdc23460cc4672a0d1b"
    },
    {
      "path": ".agents/skills/econ-literature/SKILL.md",
      "git_blob": "63ad745f54692f9aa3a8d8469600d506641c2e82",
      "sha256": "fca1edd3c4fad4f545bf0a6dccfa225c1a1498c80e810fe058d08fffc4513d83"
    },
    {
      "path": ".agents/skills/econ-paper/SKILL.md",
      "git_blob": "5332ba07b3ed577ac4557ceef7792f1b2d6827b4",
      "sha256": "6e0424c6be0fad37fb1de013b6b2f152417ab6048749a48373259678653a58b9"
    },
    {
      "path": ".agents/skills/econ-review/SKILL.md",
      "git_blob": "e1c1552c71e9a27b6dbc362b0ddb58dfbdd92cda",
      "sha256": "4fbcfb15213248393969e6ae0b8bed9940d8fd340dd7ed14a5d44e37f13d613c"
    },
    {
      "path": ".agents/skills/econ-style/SKILL.md",
      "git_blob": "6ff3592294e7b1fe6629863beabfa21464edf235",
      "sha256": "fc7d72d2080cbf1aeb6fa03a20c2b5d4909f9d41f3756d1f79b8f192a7916d5f"
    },
    {
      "path": ".agents/skills/econ-workflow/SKILL.md",
      "git_blob": "4feca538f97c123f727f3d58a4723e35506d2eab",
      "sha256": "cbdf017692f8346961b69dfe726f80d4e094c24566a3342094eb60e612bf0d12"
    },
    {
      "path": ".agents/skills/econ-workflow/references/descriptive-model.md",
      "git_blob": "119fbe91deae9fc9084b3b4e9a8ff8d0ab1db1a8",
      "sha256": "6b3eccdf5907af6a7c86221d14516aff4d81c4a54ed1466c24f6e5c68dc42d12"
    },
    {
      "path": ".agents/skills/econ-writing/SKILL.md",
      "git_blob": "21c4824a8762545a595cb32b5604f4bc88f4f2ed",
      "sha256": "6dae6b9a9a1b6fbba77b9d07aa301a0f6376fe5356aabba1e3988fbf31c5e807"
    },
    {
      "path": ".claude/AGENTS.md",
      "git_blob": "a699a9e3b9521f612a0c2bd26261b65c38f6a970",
      "sha256": "e348a9d4f1a32b26c56044a73f729200cadd057e694deffea570ca6dbe9cd5dc"
    },
    {
      "path": ".cursor/rules/01_project_policy.mdc",
      "git_blob": "cbc8df4bedae7b9b0a2871bea951f6a60be18d23",
      "sha256": "adf647e1c9af5396fb121b2d6ac8ffec650833da6deae33d96c2d25cbb465510"
    },
    {
      "path": ".cursorrules",
      "git_blob": "0da9da26e8b1ebb339f6ab6b776004c26c8b4c77",
      "sha256": "e71c708ec426e6a9b23c333f06f00e4d1564d579100161415595bbe3fd0d93f6"
    },
    {
      "path": ".gemini/GEMINI.md",
      "git_blob": "9396740efa914c5e999800240480e35ba6181b94",
      "sha256": "9e475650f183f0b043de0d05c6e0677f491d54f9fcc8f1a2a3b8d3b9dad60d55"
    },
    {
      "path": ".github/copilot-instructions.md",
      "git_blob": "2c6d60bcd43d4df21d8da6317bfec0faca5258a8",
      "sha256": "b772e08542240ea8098a8ec663105acd3171d0e9a4a5b72b8f735ec58af901c1"
    },
    {
      "path": "AGENTS.md",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b"
    },
    {
      "path": "CLAUDE.md",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b"
    },
    {
      "path": "CODEX.md",
      "git_blob": "d283e0711272480eae374ee496b78e543136214b",
      "sha256": "49b1e11198dd8151d890eeff1e12bb97b8dde8ea7a492e1ec1b043ad9a22987b"
    },
    {
      "path": "docs/ai/compiled_ai_skills.md",
      "git_blob": "14f199bd7cef96c4707f826fafccb5bc5923577b",
      "sha256": "e4552b5603641ab14f9a61fe8c2d8ec6af33988d76673aad977cc6e2ea924366"
    },
    {
      "path": "docs/ai/project_bridge.txt",
      "git_blob": "4e1a6b417812b4bdb2bde417c00b380d398f95b5",
      "sha256": "fe4c2abcd08c5675579b86eecaeaf5760646f10bf8b09e4f66f13979896be76e"
    },
    {
      "path": "docs/ai/project_instructions.txt",
      "git_blob": "092068c0a841a84a3e94c4bca6ca2fb182fee38c",
      "sha256": "e0bc6975bcc071778cc6edae3afc27c41595c557644558c1e2567caacc84e253"
    },
    {
      "path": "scripts/export_project.py",
      "git_blob": "7435dfb4af79129767ffba285991dae5b5315d0d",
      "sha256": "b0b3e947e5e546cb462b4e4e7b21a57468c0d8d67da92b86e7f7b9ba4bbc3e9a"
    },
    {
      "path": "scripts/pack_context.sh",
      "git_blob": "7174135411df6697c22589b25f0fdb9f50784e7a",
      "sha256": "f74a948b3fc7e3e43d4c68b89f2010cc54190d36d1a95c79abadad349ebb7155"
    },
    {
      "path": "scripts/sync_common_core.py",
      "git_blob": "0b4fda904409a276bc281c82b442cb5815237296",
      "sha256": "89291f98981b681bffecb45618f04226594f1b5014100b3d14ce59d5ffbda267"
    }
  ]
}
```
<!-- /common-core-receipt:v1 -->
