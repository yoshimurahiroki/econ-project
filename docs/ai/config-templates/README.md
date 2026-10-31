# Local IDE configuration

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
