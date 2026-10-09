# Local IDE configuration

These examples are public definitions. Run `bash scripts/setup_ide_mcp.sh --write` from the workspace to create the local runtime configurations. The generator reads these definitions and the enabled server environment.

Runtime configurations, authentication and generation ownership state remain local and ignored. Existing model, agent, permission, editor and manual MCP settings are retained. Generated JSON server ownership is recorded in `.agents/state/mcp-generated.json`; Codex ownership uses a comment block in its local TOML. Regeneration updates those owned entries. A manual server with the same name takes precedence.

Keep credentials in the established environment or secret store. The examples contain no credentials, private endpoints or host paths.
