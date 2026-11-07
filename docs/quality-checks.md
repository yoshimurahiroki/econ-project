# Verify the changed result

Use CORE’s three conditions to choose a consequential check. Inspect the changed operation’s actual output and reuse an established result for unchanged inputs. Run the owning command directly.

The retained tests address permission holds (`harness/test_state.py`) and failed result replacement, no-arbitrage price bounds and equation-defined equilibria (`harness/test_research.py`). Their assertions concern authorization, preservation of saved data and independent numerical identities. Select a named method only when its mechanism changed and direct execution has not established it. They use Python’s standard-library `unittest`.

```sh
python -m unittest harness.test_state.TeamStateTests.test_permission_hold_needs_recorded_release
python -m unittest harness.test_research.ResearchPipelineTest.test_failed_replacement_preserves_previous_and_blocks_descendant
```

Numerical changes use the adopted inputs and the official implementation or the defining equations. Compare the estimate and its requested inference, units and sample. Writing uses the adopted evidence and one integrated substantive review.

Distribution changes use the existing producer, `python scripts/export_project.py --generate-entries`, and the actual Git or plugin update. Inspect the affected generated entry and returned destination. Keep explicitly selected independent certification and its source evidence.

Formatting tools remain available for an explicitly named file. Test suites, static checks and distribution builds have no automatic trigger from ordinary edits or GitHub pushes.
