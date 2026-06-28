# econ-project

Economics research workspace for Python, R, LaTeX, Quarto, and cloud IDE
agents. The project is designed to be ready when the Dev Container starts while
keeping AI context small.

## Environment

Open the repository in the Dev Container. The container provides:

- Python through `pixi`
- R packages through `rv`
- LaTeX and Quarto tooling
- Jupyter kernel registration
- Compact AI rules and MCP configuration for supported IDEs

The default container does not install local LLM runtimes or broad agent
orchestration systems.

## Dependencies

The environment is synchronized automatically on container creation. Manual
commands:

```bash
make sync
make r-install
```

Use `pixi run` for Python commands:

```bash
pixi run python scripts/sync_rules.py
```

## AI Surface

`.cursorrules` is the single authoritative policy. Other IDE files are compact
pointers or generated MCP configs.

Project skills live in `.agents/skills` and are lightweight indexes only. Heavy
reference repositories live under `.resources` and are read only when a matching
task requires them.

Current skill indexes:

- `academic-research-resources`
- `causal-inference-resources`
- `econ-ai-resources`
- `econ-research-feedback`
- `econ-writing`

On-demand reference clones:

- `.resources/econ-ai/AI-research-feedback`
- `.resources/econ-ai/awesome-ai-for-economists`
- `.resources/econ-ai/awesome-causal-inference`
- `.resources/econ-ai/awesome-econ-ai-stuff`
- `.resources/econ-ai/econ-writing-skill`
- `.resources/research-ai/ECC`
- `.resources/research-ai/academic-research-skills`

## Commands

```bash
make test      # agent/MCP/rule smoke validation
               # plus pytest when tests exist
make check     # ruff, format check, mypy, and tests/smoke validation
make format    # ruff format and autofix
make r-install # sync R dependencies with rv
```

LaTeX and Quarto:

```bash
make build-paper
make build-slides
make quarto-html
make quarto-pdf
```

## Cleanup

Generated caches and reports are not source:

- `.agent_state`
- `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
- `__pycache__`
- `.coverage`
- TeX and Quarto build artifacts

Use:

```bash
make clean
```
