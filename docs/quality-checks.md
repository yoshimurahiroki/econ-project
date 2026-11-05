# Changed-work verification

Use a check when the changed mechanism or an explicit requirement creates an evidence gap and the result decides acceptance or repair. Reuse completed checks for unchanged inputs. Keep explicitly selected independent certification and its existing evidence requirements.

`python harness/local_checks.py check-changed --base <commit>` selects and executes existing commands from changed paths. It includes tracked edits and new files. Python paths select syntax compilation, Ruff and mypy. Owning implementation paths select the retained named tests. Registry inputs select the existing entry generator; registered distribution sources select the existing distribution producer, which already includes entry generation. An unrelated document change selects neither tests nor generation.

Select only the remaining evidence gaps with repeated `--check syntax`, `--check lint`, `--check typecheck`, `--check tests`, `--check registry` or `--check distribution`. Use repeated `--path path` for an explicitly bounded changed scope. `--list` prints the selected commands without executing them. Ordinary invocation executes the commands and propagates the first failing exit status. It writes no audit record or separate test state.

```sh
python harness/local_checks.py check-changed --base HEAD --check syntax
python harness/local_checks.py check-changed --path harness/codex_hooks.py --check tests
python harness/local_checks.py check-changed --base <release-base> --check distribution
```

The retained Python tests cover changed external inputs and permission holds (`harness/test_state.py`), actual hook callbacks and instruction restoration in the same owning test file, failed research replacement (`harness/test_research.py`), and changed numerical identities or units (`harness/test_research_evidence.py`). The private distribution retains `scripts/test_equity_isolation.cjs` for its private boundary. For a changed numerical calculation, compare the named output with an independent calculation or official implementation on the adopted inputs. Inspect the actual generated output when distribution changes.

Manual `make lint FILE=...`, `make format FILE=...`, `make typecheck FILE=...` and `make test TEST=path::Class::method` remain available. The CI workflow runs only through manual dispatch. It accepts a comparison base and a selected check, or an exact existing test node. Push and pull requests start no test suite.

The existing `harness.local_checks` pytest plugin requires passing calls for the selected tests. It rejects skipped collection or phases, deselected tests, empty collection and collected tests without a passing call. Existing failures and exit codes propagate. The selector and `make test` both load that plugin explicitly.
