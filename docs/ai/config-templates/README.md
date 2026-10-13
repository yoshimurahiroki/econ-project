# Local IDE configuration

## Authorized generation

These files define public configuration examples. The authorized setup command `bash scripts/setup_ide_mcp.sh --write` creates local runtime configurations from these definitions and the enabled server environment.

## Local ownership and regeneration

Keep runtime configurations, authentication and generation ownership state local and ignored. Preserve existing model, agent, permission, editor and manual MCP settings. The generator records JSON server ownership in `.agents/state/mcp-generated.json` and Codex ownership in a comment block in the local TOML. Regeneration updates those owned entries. A manual server with the same name takes precedence.

## Private configuration

Keep credentials in the established environment or secret store. Do not add credentials, private endpoints or host paths to public examples.
