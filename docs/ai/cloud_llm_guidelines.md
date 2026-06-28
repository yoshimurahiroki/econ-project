# Cloud LLM Guidelines

Cloud IDE agents may implement repository work directly when the user requests
maintenance or code changes.

## Operating Rules

1. Read `.cursorrules` first.
2. Use narrow context and targeted search.
3. Load specialized skills only when their descriptions match the task.
4. Do not invoke local LLMs or local agent runtimes.
5. Verify with `make test` and `make check` before reporting completion.
   `make test` always validates agent/MCP rules and runs pytest when tests
   exist.

## Active Surface

- `.cursorrules`: authoritative policy.
- Pointer files: `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `.antigravityrules`,
  `.clinerules`, `.windsurfrules`, `.gemini/GEMINI.md`, and Copilot
  instructions.
- `.agents/skills`: lightweight skill indexes.
- `.resources`: on-demand reference clones, excluded from active context.

## Boundaries

- Do not create commits, branches, pull requests, or DVC mutations unless the
  user explicitly asks for that operation.
- Do not import external hooks, agents, MCP servers, or worktree automation
  into the active project surface.
