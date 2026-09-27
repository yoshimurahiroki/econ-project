# econ-project

General economics research with Python, R, Quarto and LaTeX. Open the repository in the Dev Container. Full and mini retain their separate package environments.

## Working rules

`.cursorrules` owns common policy. [Research skills](docs/ai/compiled_ai_skills.md) supply task methods. Use direct code, concise prose and plain templates. Reuse existing results and add only what the current task needs.

Mechanical checks are off by default. A concrete risk in a changed result justifies the smallest relevant execution. Writing includes one meaning-based post-draft review. Routine scanners, configuration suites and passing-check reports are removed.

## Dependencies

```sh
make sync
make r-install
pixi add PACKAGE
rv add PACKAGE
```

Run research code with the existing Pixi/R environment. Full keeps its broad research stack; mini adds analysis packages as needed.

## Documents and explicit operations

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
