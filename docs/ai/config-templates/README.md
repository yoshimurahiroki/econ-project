# Local IDE configuration

## Native Codex hooks

Preview, write and check the existing lifecycle handlers at project scope:

```sh
bash scripts/setup_ide_mcp.sh --codex-hooks --client codex
bash scripts/setup_ide_mcp.sh --codex-hooks --client codex --write
bash scripts/setup_ide_mcp.sh --codex-hooks --client codex --check
```

Add `--scope user` to use `CODEX_HOME`, or `~/.codex` when unset. Both scopes preserve unrelated configuration and use the existing atomic plan and ownership record. The command refuses conflicting edited handlers or inline hooks at the same configuration layer. Review and trust the resulting hooks through the native Codex controls; installation does not grant trust. The existing plugin uses its packaged hook definition independently. Work cloud and Chat use their supported Skill and context paths; a local configuration does not turn on unsupported hooks.

Callbacks restore the original request, applicable instructions and their versions at supported boundaries. When a host presents an oversized packet as a preview with a saved-file locator, open the locator and read all applicable bodies; the preview and a recorded hash do not prove those reads occurred. Continue to use the native sandbox, approval controls and destination owner for operation authority. A callback or local check is not formal independent review or authenticated publication.

The registered compaction handlers follow the published CLI contract: `PostCompact` marks pending restoration, and `SessionStart(source=compact)` supplies complete governing text to the continuation. Bind the selected operation through the [existing context command](../../../harness/state.md#governing-context). The host's PostCompact output controls stopping and messages; model-context restoration uses SessionStart. Review changed hook definitions through the client's native trust controls. Cloud sessions use their exposed context/state mechanisms and retain the same full-reading requirement.

Keep standard automatic compaction and stable instruction/tool ordering. The inspected OpenAI remote V2 path uses its standard compaction trigger; `compact_prompt` is consumed by the local summarization path. This template preserves the standard compaction prompt and threshold. Compare host-provided `total` and `body_after_prefix` settings through an actual supported setting and completed-task usage measurement; preserve model, reasoning effort, permissions and all binding text.

The existing guarded GitHub branch-update and plugin-update connectors use their registered call schemas and exact object targets. An ordinary task must bind the corresponding required action, external target, authority and applicable holds in its existing state. A formal task retains its current output-owner release check. Unknown connector calls and opaque wrapper code remain unresolved; the native execution and destination owners retain their own authorization checks.

<a id="native-sol-terra-luna-and-astra"></a>

## Native roles and model selection

[TEAM](../../../runtime/TEAM.md#native-model-roles) owns lead, implementer, retriever and specialist authority, delegation, direct-parent returns and the specialist's actual-attempt escalation condition. These roles are independent of model and provider. Their four native templates refer to the same complete governing bodies; host adapters do not redefine those contracts. Defaults inherit the host's available model and effort. Explicitly edit a role's native model setting to select another supported model; the generator preserves user-edited files and reports a conflict instead of replacing that choice.

Preview, apply and check the existing native configuration workflow:

```sh
bash scripts/setup_ide_mcp.sh --agent-team --client codex
bash scripts/setup_ide_mcp.sh --agent-team --client codex --write
bash scripts/setup_ide_mcp.sh --agent-team --client codex --check
```

`--codex-team` remains a compatibility spelling. Ordinary team setup preserves primary model, provider, login, effort and explicit subagent defaults. It installs `.codex/agents/{lead,implementer,retriever,specialist}.toml` with no model or effort override, and retains the legacy Terra/Luna/Astra native files as explicit OpenAI model presets. Their old names map to TEAM's implementer/retriever/specialist roles without additional authority. The existing Codex example retains the OpenAI primary and subagent settings for explicit `--openai-preset` use:

```sh
bash scripts/setup_ide_mcp.sh --agent-team --client codex --openai-preset --write
```

That selected preset uses the existing native OpenAI model choices and `xhigh`. Project setup preserves the project provider assignment because the inspected Codex client reads `model_provider` at user scope; user-scope preset setup includes that provider. A conflicting user-owned preset value refuses the whole application before writes; use ordinary inherited setup to retain that configuration. Generic setup never starts login or API operations. Codex applies a role's model after a per-call model argument; use a generic inherited role or its explicit native override when choosing a different provider/model, rather than a conflicting model-fixed legacy role.

The root agent settings enable native delegation, bound V1 depth to two edges and share three child slots across the whole session. Existing tighter depth and concurrency settings remain tighter; larger settings are reduced to these adopted bounds. The legacy `max_threads` spelling is retained. At upstream revision `3a2788e6fc897fc4dd40185225167af9a9f13754`, V1 enforces `agents.max_depth`; V2 ignores it. Both share the session registry across descendants. V2 translates `agents.max_concurrent_threads_per_session = 3` to an internal root-inclusive budget of four; its dedicated `features.multi_agent_v2.max_concurrent_threads_per_session` has separate precedence. When present, the generator reduces a larger dedicated root-inclusive budget to four and preserves tighter values; unsupported edited TOML layouts are refused before writes. Keep existing host constraints and TEAM's whole-hierarchy budget, including a bridge worker, instead of assigning a new three-slot pool to each parent. Native role projection does not apply role-local provider, depth or concurrency fields.

Codex CLI and IDE use `CODEX_HOME`, otherwise `~/.codex`, for user configuration. Trusted project configuration layers the repository's settings over that setup. The existing generator supports user installation through `--scope user`; its generated-content ownership, conflict checks, atomic writes and rollback apply at the selected scope. Existing MCP declarations and unrelated model/permission settings retain their ownership.

Claude Code, OpenCode and Gemini CLI native adapters use the same four generic source templates through the existing generator:

```sh
bash scripts/setup_ide_mcp.sh --agent-team --client claude --write
bash scripts/setup_ide_mcp.sh --agent-team --client opencode --write
bash scripts/setup_ide_mcp.sh --agent-team --client gemini --write
```

Claude files are `.claude/agents/*.md` with native `name`, `description` and `model: inherit`; tool settings are omitted to retain host tools. OpenCode files are `.opencode/agents/*.md` with `mode: subagent`, native descriptions and no model override. Use each host's supported per-role model field for an explicit selection. These operations generate native adapters only, leaving MCP configurations unchanged. Gemini files are `.gemini/agents/*.md` with native names and descriptions and no model or tool override. Its documented recursion protection prevents subagents from invoking other subagents, so they return that dependency to the parent lead for reassignment. Use the same fallback on any host that cannot nest its children. Other hosts retain TEAM and their actual documented delegation/model controls; no independent runtime is installed.

Select `native_agent_configuration_requested` when configuring native agent roles or exporting their templates:

```sh
python scripts/export_project.py --task econ-data \
  --condition native_agent_configuration_requested \
  --format flat --output /tmp/native-team-flat-new
python scripts/export_project.py --task econ-data \
  --condition native_agent_configuration_requested \
  --format deployed --output /tmp/native-team-deployed-new
```

Flat output carries `CODEX_AGENT_{lead,implementer,retriever,specialist,terra,luna,astra}.toml` and `CONFIG_codex.example.toml`. Deployed output maps those native templates to `.codex/agents/`. The complete source distribution supplies the configuration generator; `--layout installed` consumes the same registered deployment mappings. Every child inherits its parent's permissions, provider and source access; an explicit role choice never expands that authority.

ChatGPT Work uses its exposed native schema: fresh `fork_turns="none"` with the necessary brief, and omitted model/effort fields for inheritance or supported explicit overrides when selected. The inspected CLI V1 spells fresh context `fork_context=false`; CLI V2 uses `fork_turns="none"`. Local TOML does not configure Work. A fixed primary can retain one lead bridge for substantive work while it handles transport; count that bridge among the shared worker slots.

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

`bash scripts/setup_extensions.sh --client code` previews extensions. Add `--write` to install for that selected CLI. Supported clients are `code`, `cursor`, `code-insiders`, `agy-ide`, and `antigravity-ide`. The helper reads the canonical `.vscode/extensions.json`; `bash scripts/setup_extensions.sh --sync` generates the two hosts' devcontainer extension lists. Installation skips installed IDs, aggregates failed IDs, and returns nonzero if a required listing, parse, or installation fails. It does not silently fall back to a different installed IDE.

`bash scripts/pack_context.sh --output /tmp/fresh-context.txt runtime/CORE.md skills/econ-data/SKILL.md` packs only explicitly selected local paths. The output must be fresh and outside the project. No external collector, package runner, or network call is used. Secret directories, environment files, local IDE configuration directories, state stores, credential/key files, and binary databases are excluded; direct selection of excluded paths fails. Broad explicitly selected directories still require the caller to know their contents: filename exclusions cannot detect arbitrary secrets embedded in ordinary source documents. Select the smallest relevant paths.
