# Task

## Goal

State the objective.

## Target Files

List files that may be modified.

## Reference Files

List the smallest useful context set. Prefer five files or fewer.

## Execution Contract

- Cloud IDE agents may implement directly when requested.
- Do not route work to local LLM or local agent runtimes.
- Do not mutate Git or DVC state unless the user explicitly asks.

## Acceptance Criteria

- Observable outcome.

## Verification

- `make test`
- `make check`

If no pytest files exist yet, `make test` should still pass via configuration
smoke validation.
