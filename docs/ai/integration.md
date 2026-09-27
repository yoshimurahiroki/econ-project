# Chat, Work and repository integration

## Shared content and actual capabilities

Code, configuration and templates remain in Git. Approved research storage retains papers and data. Existing task records carry decisions and evidence paths. Full and mini retain their separate dependency manifests, locks, containers and templates.

Chat and Work started inside a Project can use its context. Codex has a separate view and history. Use the actual connector, filesystem and execution permissions exposed in the session. Record tool results for reads, executions and deployed writes. [O1]

## Existing r31 Project

Append the exported BRIDGE_INSTRUCTIONS.txt to the existing Project instructions and attach the other bridge files. For the supplied r31 text, the separately delivered replacement prompt is another installation option. Retain R00-R08 and existing templates. ECON_ASSERTIVE.md owns direct drafting and post-draft detection, necessity decisions, deletion and revision. R00-R08 retain substantive methods. RESEARCH_WORKFLOW.md adds the supplied Mahoney framework. STYLE_GUARD.py locates phrase candidates.

```sh
python scripts/ai_tools.py export --profile bridge --output /tmp/econ-bridge
python scripts/ai_tools.py verify --path /tmp/econ-bridge
```

Measure a separately customized prompt after adding BRIDGE_INSTRUCTIONS.txt. The configuration checker enforces the 8,000-character ceiling for the standalone prompt; measure each combined custom prompt before saving.

## Standalone Project

```sh
python scripts/ai_tools.py export --output /tmp/econ-context
```

Paste PROJECT_INSTRUCTIONS.txt into Project instructions and attach the remaining files. The index selects one task skill plus the default prose skill. A --skills selection always includes econ-assertive. References are read for concrete dependencies.

Choose a new destination outside the repository. Exports are explicit snapshots with source hashes and observed revision metadata when a checkout exists. Regenerate after changes. Project attachments and native skill installation are separate mechanisms. [O2][O3]

## Repository discovery

Codex reads `.agents/skills` and discovers names, descriptions and paths before loading selected skill bodies. The repository policy and every task skill explicitly invoke econ-assertive. Its optional openai.yaml enables implicit invocation. Other hosts can use the compact index when their discovery path differs. [O3][O4]

Standalone skills and plugin-bundled skills have different product surfaces. Use the installation interface actually available. This package supplies repository files and Project snapshots; it performs no account-setting changes. Existing GitHub, Drive, academic-search and artifact tools retain their permissions. [O3]

## Writing checks and cost

```sh
python scripts/sync_rules.py
make -f scripts/ai.mk ai-check
python scripts/style_guard.py path/to/draft.md
python scripts/ai_tools.py budget
```

In an exported Project directory, run `python STYLE_GUARD.py PATH`. The detector is read-only and returns candidate phrases and locations. Exit 0 means zero phrase candidates; exit 1 means candidates need a decision; exit 2 is an input error. Quoted generated prose is included. Use --skip-quotes only for source-verified quotations. A full semantic scan follows even with zero phrase candidates. Judge each candidate with ECON_ASSERTIVE.md; delete nonessential propositions and rewrite essential content. Recheck edited passages and claim/citation links. Keep necessity decisions internal unless an audit is requested.

Reuse source readings and analysis outputs with unchanged inputs. Use deterministic scripts for counts, hashes, arithmetic and phrase matching. Do not restart literature searches or estimation for a wording edit. A changed data version, code path, parameter or environment invalidates dependent outputs. Run the complete requested pipeline for a release. The legacy setup_ai_skills.sh entry point validates bundled methods instead of fetching seven repositories. External collections remain task-specific references.

The budget measures UTF-8 bytes and characters. Its prose-startup basis includes the default style body, in addition to policy and discovery metadata. Task bodies, references, platform prompts and tool schemas are separate. An optional --encoding argument uses an installed tiktoken and available encoding data. These measurements are not end-to-end billing or model-adherence estimates.

## Primary sources

Accessed 2026-09-27.

- [O1] https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
- [O2] https://help.openai.com/en/articles/10169521-projects-in-chatgpt
- [O3] https://learn.chatgpt.com/docs/build-skills
- [O4] https://agentskills.io/specification

## Runtime and maintenance

Run `make -f scripts/ai.mk ai-check` with Python 3.12 or newer for configuration-only validation. It uses the standard library and small fixtures. Existing Make/Pixi/rv commands remain the owners of analysis execution. Existing environments, locks, containers, templates and MCP permissions are retained.

The path-filtered GitHub workflow repeats configuration checks and size reporting. The external source survey stays in sources.md and is read only for maintenance or a concrete discovery task. The script budget includes the mandatory prose skill; it does not equate file-size reduction with measured billing reduction.
