# Local IDE configuration

## Native Sol, Terra, Luna and Astra

The public Codex template selects the native OpenAI provider, ChatGPT login and primary `gpt-6.1-sol` with `xhigh`. The three standalone child templates select Terra for bounded implementation, Luna for routine batches and Astra for the consequential exceptionally hard core remaining after Sol's substantive failed attempts. [TEAM](../../../runtime/TEAM.md#native-model-roles) owns their assignments and Sol's final authority.

Preview, apply and check the team configuration from this repository:

```sh
bash scripts/setup_ide_mcp.sh --codex-team --client codex
bash scripts/setup_ide_mcp.sh --codex-team --client codex --write
bash scripts/setup_ide_mcp.sh --codex-team --client codex --check
```

This explicit option sets `.codex/config.toml`'s model, effort, native provider and login fields and the supported `[agents]` defaults, then installs `.codex/agents/{terra,luna,astra}.toml`. An existing concurrency setting, including the legacy `max_threads` alias, is retained; the template supplies three child slots when neither setting is present. The existing atomic plan and generated-content ownership protect unrelated configuration and edited role files. Team setup preserves existing MCP declarations and their ownership; ordinary MCP generation uses the commands in the next section. A custom role conflict prevents application and identifies its path. The native role files inherit the parent's permissions, provider and MCP configuration.

Export the registered native configuration together with the requested operation:

```sh
python scripts/export_project.py --task econ-data \
  --condition requested_distribution_configuration_or_installation \
  --format flat --output /tmp/native-team-flat-new
python scripts/export_project.py --task econ-data \
  --condition requested_distribution_configuration_or_installation \
  --format deployed --output /tmp/native-team-deployed-new
```

The flat package contains `CODEX_AGENT_terra.toml`, `CODEX_AGENT_luna.toml`, `CODEX_AGENT_astra.toml` and `CONFIG_codex.example.toml`. The deployed package places the child definitions in `.codex/agents/` and keeps the primary template at `docs/ai/config-templates/codex.example.toml`. Their TOML bytes and source/output hashes are preserved. Apply the primary template through the configuration workflow above. A bounded operation export carries TEAM's role authority; select the configuration condition when the package must also contain the configuration files.

An installed source tree supplies the three complete registries under `.agents/registry/` and every selected deployment path. From that tree, add `--layout installed` to either export command. A bounded deployed operation package supplies its selected resources; installation of the complete registry-backed source remains the existing deployment workflow.

Codex CLI and its IDE extension read user configuration and user agents from `CODEX_HOME` when set, otherwise from `~/.codex`. Trusted project configuration layers the repository's `.codex/config.toml` and `.codex/agents/` over that user setup. Preview, apply and check a user-wide installation with the same conflict and concurrent-edit protections:

```sh
bash scripts/setup_ide_mcp.sh --codex-team --client codex --scope user
bash scripts/setup_ide_mcp.sh --codex-team --client codex --scope user --write
bash scripts/setup_ide_mcp.sh --codex-team --client codex --scope user --check
```

`--scope project` is the default. User scope requires `--codex-team --client codex`; it writes the selected Codex home's `config.toml`, `agents/` and `.agents/state/mcp-generated.json` ownership metadata. Each scope keeps its own role ownership history. Existing edited or user-owned role files are preserved and reported as conflicts before any write.

Native configuration follows the installed client's schema and actual model catalog. Run `codex --version` and `codex login status`; the selected authentication result is `Logged in using ChatGPT`. Start the primary with `codex --model gpt-6.1-sol -c model_reasoning_effort='"xhigh"'` when applying the same choices to one session. The [official agent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents) and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) define native loading and supported fields.

ChatGPT Work uses its hosted child-launch schema. Supply the explicit model and `xhigh` through that schema; use a fresh-context launch when the host requires it for model overrides, and provide the original fixed contract and applicable rule references. Work's composer selects its primary session model. For a fixed primary with supported child overrides, launch a Sol manager and keep the primary on transport and authorized publication. Local TOML configures local Codex clients. Ordinary ChatGPT Chat uses its own model choices and accounting. The API is a separately billed route; this workflow executes through native Work or ChatGPT-authenticated Codex.

Report requested model and effort separately from the host's observed fields. A host that returns only the child identity establishes the accepted launch and its identity. Native `account/usage/read` groups thread model, effort and returned token or credit observations; `account/rateLimits/read` supplies the separate allowance state. Use those actual fields when the installed host exposes them, and retain absent values through TEAM's accounting contract.

## Preview and selected application

Python 3.11+ is required. Run `bash scripts/setup_ide_mcp.sh` for a read-only structural diff. It previews registered clients, omitting an absent devcontainer. Values are not printed in diffs. Select narrower targets with repeated `--client`, for example:

```sh
bash scripts/setup_ide_mcp.sh --client cursor --client codex
bash scripts/setup_ide_mcp.sh --write --client cursor --client codex
bash scripts/setup_ide_mcp.sh --check --client cursor --client codex
```

`--write` always requires explicit client selection. `--check` returns 1 for differences, 0 for a match. `--print` prints generated MCP JSON without applying it. Modes are mutually exclusive; unknown arguments return 2 before writes. The client names and paths come from `registry/placements.json`, through the shared registry loader's `placements.configuration.configuration_clients`. Paths resolve against this project root, regardless of the caller's working directory. A selected devcontainer must already exist and contain a customization's `settings.mcpServers` object. All selected targets, enabled integrations, and ownership state are parsed before application.

## Ownership, recovery, and credentials

The generator preserves existing model, agent, permission, editor, and manual MCP settings. `.agents/state/mcp-generated.json` records the previous generated server values for JSON and TOML. An unchanged generated entry can be updated or removed. A changed or deleted entry is preserved and released from generated ownership; a deleted entry is not recreated on subsequent runs. Existing manual entries with matching names win. Older name-only state or TOML generation comments do not establish content ownership, so unverifiable legacy entries are preserved. No automatic destructive legacy migration is performed.

Before application, the helper rechecks every selected file and ownership state, then rechecks each file immediately before replacing it. On a caught write failure, it restores earlier files only when their current bytes still match this invocation's write. Concurrent edits observed during recheck or recovery are preserved and reported. Replacement is atomic per file; this is not a filesystem-wide transaction or a process-crash recovery journal. An unrelated writer in the final check-to-replace interval cannot be excluded without a shared locking protocol.

Runtime configuration and ownership state stay local and ignored. Generated credentials remain environment or secret-store references. Optional integrations are enabled by `BRAVE_API_KEY`, `EXA_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `DATABASE_URL`, `ENABLE_GOOGLE_DRIVE_MCP=1`, or `ENABLE_CONTEXT_MCP=1`. Google Drive requires the existing `secrets/credentials.json`; context integrations require both local executables. Secret values are never copied from the environment into generated files. Do not place private endpoints or secrets in public examples.

Economics Checked Artifacts has no default server. Enable it only with both `ENABLE_ECONOMICS_CHECKED_MCP=1` and `ECONOMICS_CHECKED_MCP_URL`, selecting Git-ignored local clients. See [private endpoint setup](../plugin-integration.md#checked-artifacts-connection). The generator performs no authentication or data submission.

## Extensions and scoped context

`bash scripts/setup_extensions.sh --client code` previews extensions. Add `--write` to install for that selected CLI. Supported clients are `code`, `cursor`, `code-insiders`, `agy-ide`, and `antigravity-ide`. The helper reads this project's devcontainer, skips installed IDs, aggregates failed IDs, and returns nonzero if a required listing, parse, or installation fails. It does not silently fall back to a different installed IDE.

`bash scripts/pack_context.sh --output /tmp/fresh-context.txt runtime/CORE.md skills/econ-data/SKILL.md` packs only explicitly selected local paths. The output must be fresh and outside the project. No external collector, package runner, or network call is used. Secret directories, environment files, local IDE configuration directories, state stores, credential/key files, and binary databases are excluded; direct selection of excluded paths fails. Broad explicitly selected directories still require the caller to know their contents: filename exclusions cannot detect arbitrary secrets embedded in ordinary source documents. Select the smallest relevant paths.
