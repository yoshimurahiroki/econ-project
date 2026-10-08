# Project integration

Repository skills run in the coding environment. Project attachments are snapshots identified in SOURCE.md. A repository task uses the current policy and the files relevant to the request.

## Common core

[econ-project-mini](https://github.com/yoshimurahiroki/econ-project-mini) is the editing source for the common policy, skills, references, host pointers, indexes, Project templates and exporter. The explicit `COMMON_PATHS` allowlist in [sync_common_core.py](../../scripts/sync_common_core.py) defines the same relative paths copied to econ-project and Ruan. Project context, integration prose, source history, study records, environments and execution recipes remain project-owned.

Compare and apply when preparing publication of a common-core change. Use the actual destination HEADs for `--expect-head`; this example uses the refactor's recorded baselines.

```sh
cd /tmp/econ-project-mini-instructions-20261008
python scripts/sync_common_core.py --source . \
  --target /tmp/econ-project-instructions-20261008 \
  --target /tmp/ruan-literature-20261005

python scripts/sync_common_core.py --source . \
  --target /tmp/econ-project-instructions-20261008 \
  --target /tmp/ruan-literature-20261005 --apply \
  --expect-head econ-project=91aad0bb9c15583d8ca2efce9303642043cfc7a5 \
  --expect-head Ruan=af5a07cfcc0ac00a9a0e556520623fc2673f97bf
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
  "source_base_commit": "22f658321ece40b20b54dddb38d18a41027ee3e4",
  "common_content_id": "84cb754dfe67c5823751500f75ffcf3ec149eca6ac6792f5e456b395ca2caab1",
  "source_state": "committed",
  "paths": [
    {
      "path": ".agents/AGENTS.md",
      "git_blob": "a699a9e3b9521f612a0c2bd26261b65c38f6a970",
      "sha256": "e348a9d4f1a32b26c56044a73f729200cadd057e694deffea570ca6dbe9cd5dc"
    },
    {
      "path": ".agents/skills/econ-assertive/SKILL.md",
      "git_blob": "9c1fd38e03d612c5ed49101b58bb9336cbef34e9",
      "sha256": "793e0891cd6b9383f8d168be2b29ce2fec9b0b200561140715948731187dc8b4"
    },
    {
      "path": ".agents/skills/econ-assertive/agents/openai.yaml",
      "git_blob": "4fa559402be06cfc396c30638b154b8b5c5cb321",
      "sha256": "915fa6ed9271039a32cb2814d9907034e8e5bce426e9be12581e6c11d5cc7442"
    },
    {
      "path": ".agents/skills/econ-assertive/references/default-micro.md",
      "git_blob": "13dcd3b2a5f876f1b3e2d1a22a7530189ac41b86",
      "sha256": "87d677fb103977d62f6e5252f3bcd33b69d2174ca0d18d922c677c1217506558"
    },
    {
      "path": ".agents/skills/econ-assertive/references/patterns.md",
      "git_blob": "7a704d5fb70513df03f351aaebd973a1350f0f1b",
      "sha256": "c26ee36e2699c0b434ac1e091d0ce9ee2b9709f357687e044f3d31e0d88ce764"
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
      "git_blob": "e094b8c2d9237ef75423c47f0f217bccd5539ca4",
      "sha256": "5ba21c0e8d58bc39535c1377dbb8e9b997625a106ba91f7e9163648fb291553f"
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
      "git_blob": "8483ff8432534d4aa49239591878e2136ec40914",
      "sha256": "329488be0f7f4652852e091f186d286b5cd97cd6dabdc034ded13062b9b33065"
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
      "git_blob": "ab69f87f7e28804b0411aa7d57ef0ac0716cecff",
      "sha256": "77e6804d5efeb072acd93b1b23cb24f11a52ceeca3f31b42d5c1874aa82f7fe3"
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
