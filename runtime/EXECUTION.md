# Execute on identified inputs and outputs

Use for ordinary file work, calculations and external actions. Select [state and resumption](../harness/state.md) only when persistent records or saved-result reuse are needed, and [publication](../harness/publication.md) for a requested move, joint publication or Git operation. Inherit [CORE](CORE.md)'s authority, input scope and completion conditions. Derive execution authority from the current task and apply it to each operation and target.

## Select the operation and working area

Classify the operation as answer, modify, create or external. Assign write scope only to operations that change something. Return a read-only answer as a conversation result. Use the established project entry point and permitted environment. Inspect the existing task-owned paths and preserve source inputs, adopted definitions, unrelated work and concurrent changes.

Keep scratch output separate from final destinations. Where a complete file or output generation must replace an earlier result, finish the new generation in the authorized staging area, perform applicable format and content operations there, then publish the complete generation. A failure leaves the previous complete output available. Use the matching examples for [complete file replacement](#example-replace-one-output-after-a-complete-write) or [multi-file publication](../harness/publication.md#example-publish-one-complete-generation).

Git staging, commits, remote writes, installation and configuration changes require the task's corresponding authority. Scope authorized changes to task-owned paths and read back a remote result when that action is required. Stage task-owned changes and keep secrets in their authorized credential storage.

## Checks and completion

Choose required operations from explicit task conditions, the changed objects under [Compare changed outputs](#compare-changed-outputs), and the requested output format. Express each over named inputs with a comparison or acceptance condition. Runtime checks inspect the current request, candidate, prose and returned operations. Ordinary research answers use their candidate-bound checks.

Use [native_run.py](../harness/native_run.md) `begin` before candidate production. Select the registered operation, activated conditions, profile and templates, then fix the request, contract v2, adopted policy dependency closure, capability record and strict/provisional mode. The required roles, capabilities and checks come from the selected `review_plans` definition in registry/operations.json; strict submission and finalization require each selected capability to be `available`. Import the original-request coverage return required by the selected plan (author self-check under direct, actual independent reviewer under focused/full), then `submit` the complete response, artifacts, actual action records and structured original reviews. The runner executes mechanical checks and identifies missing returns. Obtain those returns through actual host tools, repair findings and resubmit. `finalize` takes the returned submission hash and writes the checked snapshot to a new output directory. Retain commands, reports and the mapping between the snapshot and any state-helper candidate record. Apply CONTROL's fixed-mode and actual-event checks. The runner reads and writes local files using existing authorized Python execution; reviewer launches use the host's existing worker tools.

Associate each result with the exact inputs and output versions it assessed. Match each completion receipt to the current target bytes. Invalidate only checks whose relevant inputs or target output versions changed; retain receipts whose targets still match. A change to the display of an operational log does not change a calculation input.

Completion requires a result matching every required output's role, kind and target, a returned result for each required action's exact target and operation, and current-version results for every required content, prohibition, evidence and review condition. Match action records to the performing tool's actual return. Register the entire response, including headings, captions and completion/status prose. Store runner inputs and snapshots in its task-owned run directory; keep operational records separate from requested deliverables. For an action-only task, use an empty artifact directory and save the actual final response as the runner candidate. Register response content, prohibitions and evidence against `message://final`; register file conditions against `artifact://path`. The message bytes are a separate input from the artifact snapshot. Bind message review conditions to `candidate_sha256` and the request, contract and artifact digests.

On failure, identify the cause and affected descendants, repair within authority, then repeat the affected operation. Reuse saved results with matching inputs, definitions and completed prerequisites. After a figure-label change, reuse matching estimates and rebuild rendering; an estimator-input change invalidates the corresponding estimates and dependent tables, figures and prose.

## Compare changed outputs

Select the comparison from the object changed. For a formula, sample, weight, encoding, resampling scheme or estimator change, compare affected quantities with a direct calculation, a derived small case or the specified implementation. Match sample identifiers, keys and term names. Derive numerical tolerances from calculation or simulation error.

For a library or calculation-engine change, hold the sample and definitions fixed and compare named estimates and the inference quantities the task requires. For a join, inspect key multiplicity and unmatched identifiers. For a comment, name, reference or display change, inspect the affected references and consumers. For a requested format conversion, establish that the output opens or renders in that format. For PDFs, slides and figures, bind the extracted-text view to the final artifact version and retain page, slide or figure locations. Compare it with the actual rendering, including headings, footnotes and embedded labels; inspect text omitted or misread by extraction directly and record every uninspected region. Complete rendered-content coverage by inspecting the final rendering and recording each text-view match.

When rules, routes, distribution formats or state interfaces change, run the affected path through the actual registry and instruction bodies. Compare inclusion of activated required rules as well as link existence; change consumed and unused dependencies separately. For ordinary writing or explanation, use the native candidate checks and role returns in CONTROL.

For a changed public entry point, use the original input through that entry and confirm that the intended operation ran and produced the requested content and artifacts attributable to that execution. Exit zero, a successful import or accepted arguments alone do not establish completion. Reuse the corresponding same-input regression; this does not add a standing end-to-end run to ordinary answers.

Repair a mismatch at the operation producing the affected value and regenerate its descendants. Reuse completed comparisons with unchanged inputs. Finish when the changed results satisfy their corresponding conditions.

## Project-file ownership

Inspect the task root and affected dependencies. Check applicable ancestor instructions at their specific paths without traversing unrelated sibling directories. Before editing, creating, renaming or moving a file, identify its canonical owner and consumers; identify the producing command for generated artifacts. Update an existing producer for an existing generated result. Add a file when the output or dependency has a distinct role. Update imports, paths, entry points and consumers together for an authorized move. Preserve source inputs and place transformations in derived-data locations. Give intentional alternatives separate destinations.

## Entry point and dependencies

Use the existing runner and its documented execution root. Keep machine-specific external locations in existing configuration and resolve shared-input links to the intended fixed revision. Transfers include that revision or authorized access instructions. Use one canonical producer per output with explicit prerequisites. Keep alternatives in separate destinations and direct consumers to the intended result.

Use a simple local runner when the chain fits the rerun budget. Use the existing dependency system when selective rebuilding, persistent reuse or ordered parallel prerequisites are needed. Resolve source research through the host's existing search and connector tools; keep harness execution and saved state local.

Keep required language, runtime and package versions in the existing environment specification, including dynamically selected packages and external executables missed by automatic discovery. Reuse suitable installed dependencies. For an authorized clean reproduction or transferable package, restore the recorded environment within any code hold and start without undeclared interactive-session objects or packages. Report the missing dependency and needed authorization when restoration is outside scope.

## Complete outputs and failure propagation

Write an output completely before exposing it to downstream stages. Where interrupted writes can be mistaken for reusable results, write to a temporary destination, establish that all required records and fields were written and replace the final artifact. Preserve the prior valid result under its existing run identity until its replacement is ready. Give parallel writers separate destinations or one designated producer. For an active multi-file publication, apply the [complete-generation boundary](../harness/publication.md#complete-generation-boundary).

Check required child exit statuses and retain attributable logs. Stop affected dependents on failure. Require a successful generating-stage return for each output in the current run. Match the expected output identifiers and input/specification versions to the completed run before using them.

When an operation's outcome is unknown, reconcile the same target and actual returns under [retry and capacity](TEAM.md#retry-and-capacity) before treating it as failed or repeating a change. For a confirmed stage failure, identify its last completed prerequisites in the existing dependency record. After repairing the operation within authority, restart at the failed stage only if those prerequisites are complete and still match the inputs, definitions, code and settings now required. A repair to an upstream transformation instead restarts at that transformation and invalidates affected descendants. Treat the failed attempt's partial files as unpublished; resume inside the stage only when its existing checkpoint records a complete restart boundary and matching dependencies. Otherwise rerun that stage into a fresh destination. Retain the failed attempt's attributable log when a rerun would overwrite it, and release downstream stages only after the replacement succeeds. Unaffected completed branches remain reusable.

### Example: replace one output after a complete write

**Use when:** an authorized transformation overwrites one derived CSV, with one designated writer and no concurrent modification of its destination. The output directory already exists; `records` is the existing iterable of person records whose fields satisfy the input contract with numeric weekly minutes. The source data and the previous output must survive a failed transformation or write.

```python
import csv
import os
import tempfile
from pathlib import Path

destination = Path("derived/weekly_hours.csv")
temporary = None
try:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", delete=False,
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp"
    ) as stream:
        temporary = Path(stream.name)
        writer = csv.writer(stream)
        writer.writerow(["person_id", "weekly_hours"])
        for row in records:
            writer.writerow([row["person_id"], row["weekly_minutes"] / 60])
    os.replace(temporary, destination)
    temporary = None
finally:
    if temporary is not None:
        temporary.unlink(missing_ok=True)
```

**Expected result:** the stream is closed before replacement. A conversion, iteration, or write/close failure leaves the existing output bytes unchanged. A successful replacement publishes the completed CSV. Cleanup targets only this invocation's temporary file. After abrupt process termination, inspect and remove the abandoned invocation temporary file.

**Decision criterion:** keep the temporary file in the destination directory for same-filesystem replacement. Publish one completed file under the stated writer coordination. Apply the project's persistence protocol for crash/power-loss durability. File permissions come from the temporary file. Use an existing project publication helper when destination metadata must be preserved or writers coordinated.


## Record and artifact boundaries

Keep project progress, adoption status, unresolved user choices and continuation history in the existing operational record. Keep adopted research definitions in their canonical specification and numerical provenance with the generating result. A requested plan or transfer is an operational deliverable. Include operational status inside research prose only when the user requests it; otherwise the research artifact presents its economic argument, quantities and conditions.

Operational updates lead with the useful result and the next authorized action. Store continuation state, versions and permissions in their existing records, while selecting the user-facing detail by the decision or action it enables. A record-format change alone does not invalidate the research content or numerical result.

## Final delivery authority

Apply [CONTROL](CONTROL.md) to the exact final snapshot and its requirements-to-results map. Record actual tool/task outcomes and candidate-bound original review results. Strict mode requires contract v2, available required capabilities, passing request coverage, matching adopted dependencies and completed candidate-bound checks. Every quality role selected by the pinned plan supplies the 22 B25–B31/C01–C15 records specified in CONTROL: one author for direct work, one independent reviewer for focused work and two independent reviewers for full review. Explicitly selected provisional mode retains the candidate snapshot in the isolated run workspace and reports its quarantined status and missing checks through the applicable outgoing-surface procedure; it does not deliver the candidate body or requested final artifacts. Deliver the finalized snapshot unchanged; regenerate or edit only through a new submission and affected checks. The coordinator performs the Chat send and any separately authorized external action.

Apply the common prose gate and exact outgoing-text scan in [CONTROL](CONTROL.md#finalization-and-delivery). Retain its 22 judgments and original-source comparison under the selected plan. Publish requested artifacts only; keep operational records and text views in the run.

<!-- BEGIN GENERATED REVIEW PLANS -->
Read the [registered review plans](CONTROL.md#registered-review-plans) once; apply the selected plan to this document’s operations.
<!-- END GENERATED REVIEW PLANS -->
