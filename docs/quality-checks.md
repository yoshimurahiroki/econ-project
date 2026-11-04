# Changed results and retained checks

Complete one integrated review under CORE. Ordinary work does not automatically run tests, validation matrices or pre-commit processes.

The retained Python tests cover changed external inputs and permission holds (`harness/test_state.py`), failed research replacement (`harness/test_research.py`), and changed numerical identities or units (`harness/test_research_evidence.py`). Run the corresponding named test only when its owning implementation changes. The private distribution also retains its existing `scripts/test_equity_isolation.cjs` for changes to that private boundary.

For a changed numerical calculation, compare its actual named output with an independent calculation or official implementation on the adopted inputs. For a changed distribution, generate it through the existing producer and inspect the actual saved output. Keep the actual arguments, result and relevant versions in the existing work record; add no permanent test framework.

Manual `make lint FILE=...`, `make format FILE=...` and `make typecheck FILE=...` use the existing project environment for a requested code operation. Research Python/R packages, document tools and the ordinary build commands remain available. There is no separate quality environment or automatic test run. `make test TEST=path::Class::method` retains its existing explicit selector. The existing CI workflow runs one selected retained test only through manual workflow dispatch; push and pull requests start no tests.

The explicit `make test` selection is required to execute and pass. Its existing `harness.local_checks` pytest plugin rejects skipped collection, skipped test phases, deselected tests, empty collection and collected tests without a passing call. The command reports the incomplete stage and pytest's skip reasons. Existing pytest failures and nonzero exit codes propagate unchanged; checks run through this entry point cannot succeed from collection alone. The plugin is loaded explicitly by `make test`, with the project root prepended to the existing Python path for console and module invocations, and adds no automatic test run.
