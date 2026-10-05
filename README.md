# econ-project

General economics research with Python, R, Quarto and LaTeX. Open the repository in the Dev Container. Full and mini retain their separate package environments.

## Working rules

`.cursorrules` owns common policy. [Research skills](docs/ai/compiled_ai_skills.md) supply task methods. Use direct code, concise prose and plain templates. Reuse existing results and add only what the current task needs.

Mechanical checks are off by default. A concrete risk in a changed result justifies the smallest relevant execution. Writing includes one meaning-based post-draft review. Routine scanners, configuration suites and passing-check reports are removed.

## Dev Container storage

New projects use `econ_data_${devcontainerId}` for `/workspaces/econ-project/data` and `econ_pixi_env_${devcontainerId}` for `/workspaces/econ-project/.pixi`. The [Dev Container identifier](https://github.com/devcontainers/spec/blob/main/docs/specs/devcontainer-id-variable.md) separates project instances on the same Docker host and remains stable across container rebuilds. The download cache `econ_pixi_cache` remains shared.

Before recreating an existing container, inspect its current mounts with `docker inspect CONTAINER --format '{{json .Mounts}}'`. To continue using the previous volumes, set the two `source=` values in `.devcontainer/devcontainer.json` to their current names. For the original defaults, retain:

```json
"type=volume,source=econ_data,target=/workspaces/econ-project/data",
"type=volume,source=econ_pixi_env,target=/workspaces/econ-project/.pixi"
```

Keep the cache mount as configured, then recreate the container. This setting reuses the volumes at their existing locations; it performs no data migration or deletion.

## Dependencies

```sh
make sync
make r-install
pixi add PACKAGE
rv add PACKAGE
```

Run research code with the existing Pixi/R environment. Full keeps its broad research stack; mini adds analysis packages as needed.

## Documents and explicit operations

| Entry point | Main output |
| --- | --- |
| `make build-paper [PAPER=path.tex]` | PDF beside the LaTeX source; default `tex/paper/ecta_template.pdf` |
| `make build-slides [SLIDES=path.tex]` | PDF beside the LaTeX source; default `tex/slides/main.pdf` |
| `make quarto-html QMD=path.qmd` | HTML for the named QMD; the whole project when omitted |
| `make quarto-pdf QMD=path.qmd` | PDF for the named QMD; the whole project when omitted |
| `make quarto-reveal QMD=path.qmd` | Reveal.js slides for the named QMD; the whole project when omitted |

Quarto output locations follow the document or project configuration. The default LaTeX templates use `tex/bibliography.bib`; provide the study bibliography before building them. LaTeX stops on a compilation error. Bibliography processing runs when the generated `.aux` names bibliography data and propagates its failures.

```sh
make build-paper
make build-slides
make test TEST=tests/example.py::test_result
make lint FILE=scripts/example.py
make format FILE=scripts/example.py
```

Tests, lint and formatting run only for the explicitly named target. Commit hooks retain only private-key detection. Editor test discovery, routine lint and automatic formatting are disabled.

## Chat and Work

[Project integration](docs/ai/integration.md) describes the existing-Project bridge and standalone export.

```sh
python scripts/export_project.py --profile bridge --output /tmp/econ-bridge
```

Code and templates stay in Git. Raw data, papers and credentials retain their existing storage and access rules. Source assets and unrelated work are preserved.
