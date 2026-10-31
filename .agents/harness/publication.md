# Publish requested outputs and changes

Use only for requested file moves, joint output publication, staging or commits. Inherit [CORE](../runtime/CORE.md) authority and the ordinary [execution contract](../runtime/EXECUTION.md). Examples establish no additional authority.

Complete authorized file delivery and Git changes through the existing destination after CORE's integrated review and the verification required by the changed behavior. Preserve concurrent edits and check the actual returned write or publication result.

An explicitly requested certified publication uses `native_check.assert_release_predicates` with the strict-reviewed plan, original-request coverage, the pinned policy, the 142-rule dictionary, both independent workers' 22 full-text judgments and compliance on the exact candidate. The existing host verification binds the request and actual worker and operation events. `native_run` applies this predicate at release-check, publication and verification; its draft plans retain their diagnostic purpose.

## Complete-generation boundary

Write an output completely before exposing it to downstream stages. Where interrupted writes can be mistaken for reusable results, write to a temporary destination, establish that all required records and fields were written and replace the final artifact. For a multi-file result, use the project's publication boundary: write a separate generation and publish its manifest or pointer only after all required files succeed. A consumer must resolve that generation once and read all its files from it; replacing files one by one behind an old completion marker can expose mixed versions. If consumers require fixed paths, stop their reads during replacement and resume only after the complete set satisfies its output contracts; use the existing runner's stage barrier when it provides that guarantee. A failed replacement leaves those reads blocked until the complete old set is restored or the new set succeeds. Preserve the prior valid result until its replacement is ready, but do not label it as the new run's output. Give parallel writers separate destinations or one designated producer.

## Working files, Git and delivery

Keep source snapshots, derived data, analysis code and manuscript outputs distinguishable in the existing layout. Add an intermediate stage when it has a reusable or inspectable transformation role. Keep raw inputs unchanged and preserve their acquisition records; keep credentials and restricted data outside shared repositories and delivery packages. A reusable software interface may need packaging, while a research working directory may need only a documented root and runner.

Before changing tracked files, inspect current changes and ownership. Stage only the intended paths or hunks; preserve unrelated and concurrent edits. Remove or relocate a file only after checking its producer, consumers and recovery path within the authorized scope. For renames, update dependent paths and entry points together.

When an authorized relocation crosses filesystems, treat it as copy, verify, publish, then remove the source if removal is authorized. Copy to a separate destination-side staging path; verify the expected file set and content against a stable source, plus permissions or metadata required by its consumers. File counts or byte sizes alone do not establish content equality. If the source changes during copying, establish a stable snapshot or repeat the affected copy before publication. Publish the verified copy using the destination filesystem's supported replacement operation, then update consumers and verify their new paths. Remove the original only while writers are coordinated and its contents still match the verified copy; otherwise retain it and reconcile the newer changes. Until those steps succeed, keep the source and prior destination recoverable. On failure before publication, consumers stay on the source; after publication, restore their prior paths and destination only if those versions remain valid and no intervening writer's changes would be lost. Otherwise preserve both versions and resolve the conflict within authority. A completed copy alone is not a completed move.

When a commit is requested and unrelated changes are already staged, separate commit scope from staging scope. An ordinary commit includes the whole index; a path-limited commit instead takes the named paths' working-tree contents, which can include unrelated unstaged hunks. Use the latter only when the entire named-file changes belong in the requested commit, with no concurrent writer or unresolved merge. Where changes overlap within a file, agree how to isolate the intended patch before committing; do not quietly include or unstage someone else's work. Verify the resulting commit and preservation of the original unrelated staged and unstaged changes.

Follow the project's versioning policy: exclude secrets and bulky rebuildable intermediates, while retaining deliberate reference results or release exhibits when review or delivery requires them. Generated does not automatically mean untracked. Check ignored files explicitly when preparing a requested package so required data, metadata or artifacts are not silently omitted.

Derive a delivery layout from recipient requirements, licenses and executable entry points rather than reorganizing the working project to match an entire template. Include the needed inputs or lawful acquisition instructions, environment, execution root, commands and output mapping. Check package-relative paths and required dependencies for the requested delivery; exclude private operational state and secrets.


### Example: stage a correction and move a clean file

**Use when:** the authorized task corrects a sample expression in `src/select_sample.R` and moves `docs/variables.txt` to `docs/data_dictionary.txt`. The sample correction has already been made and is unstaged alongside an unrelated hunk in that file. An unrelated change to `notes/review.md` is already staged, and another unrelated edit is unstaged. No commit is requested.

First inspect both the index and working tree:

```sh
git status --short
git diff --cached
git diff
```

Proceed only after identifying the original staged patch and confirming that the move source has no staged or unstaged edits, the destination is absent, and no merge conflict is present. Check the file's producer, consumers, and recovery path before moving it. This example stipulates a tracked, hand-maintained dictionary with no path-dependent consumers; if references or entry points use its old path, include their authorized updates in the same reviewed change. If a move would involve someone else's partially staged file, pause to agree how that file should be handled.

```sh
git mv -- docs/variables.txt docs/data_dictionary.txt
git add -p -- src/select_sample.R
```

At the patch prompt, accept only the authorized sample-expression hunk and reject the unrelated hunk. Split a combined hunk if possible; if the changes cannot be separated confidently, stop rather than stage the whole file.

```sh
git diff --cached
git diff
git status --short
```

**Expected result:** the index contains the original staged change to `notes/review.md`, the requested rename, and the selected sample correction. The unrelated unstaged edits remain unstaged and unchanged. The final full diffs must match the initial diffs except for the authorized move and movement of the selected hunk into the index. A rename may be displayed as a deletion/addition depending on diff settings; the content must still match.

**Decision criterion:** stage by named path and reviewed hunk, and compare against the initial index rather than assuming the index belongs to this task. Do not use a blanket add, reset, clean, deletion, or commit to finish this operation. Existing staged work remains staged; a later commit needs an agreed scope because an ordinary commit would include that work too.


### Example: publish one complete generation

**Use when:** a requested result consists of `estimates.csv` and `sample_counts.csv`, and the existing project manifest names immutable generation directories. One designated publisher controls the manifest; consumers already read it once per job. This trace uses that arrangement rather than introducing a new publication system.

**Operation trace:**

1. The current manifest selects generation A. Begin the replacement in a separate generation B directory; leave A and the current manifest unchanged.
2. Write B's estimates, then B's sample counts. If the second write fails, B remains unpublished. Existing readers continue using A; dependents requesting the replacement remain blocked. Repair and rerun the failed stage as described above, without mixing A's counts with B's estimates.
3. Once B's required files are complete and their shared input/specification provenance and stage-specific contracts match, write a complete candidate manifest selecting B. Replace the current manifest through the project's same-filesystem publication operation.
4. A reader that already resolved A finishes with A. A reader resolving the new manifest reads both files from B. Keep A available for active readers and any authorized rollback; retiring it is a separate scoped operation.

**Expected result:** publication changes the selected generation from A to B in one step. A failed preparation never makes B current. If B later proves invalid, repoint to A only when A is still valid for the intended use and the manifest has not been superseded by another publisher; describe it as a rollback, not successful completion of B. If A does not satisfy the requested dependencies, block that result until a corrected generation is ready.


### Example: commit requested files with unrelated work staged

**Use when:** the user requests a commit containing the complete corrections to `src/labels.R` and `docs/figure_labels.md`. An unrelated change to `notes/review.md` is already staged. These are existing tracked files on an ordinary branch, with no merge in progress or concurrent writer. Every change in the two requested files belongs to this task.

**Operation trace:**

1. Inspect `git status --short`, `git diff --cached`, and `git diff`; retain the initial staged and unstaged diffs for comparison. Inspect `git diff HEAD -- src/labels.R docs/figure_labels.md` to review the complete working-tree changes the path-limited commit would include.
2. With that exact scope confirmed, use `git commit --only -m "Correct figure labels" -- src/labels.R docs/figure_labels.md`. This commits the named files' working-tree contents while leaving the unrelated staged file out of the commit.
3. Inspect the resulting commit's paths and patch, then the staged and unstaged diffs. The commit contains only the two requested corrections; `notes/review.md` retains its original staged change, and other working-tree edits remain unchanged. If the commit fails, inspect the reported cause and current index before retrying rather than assuming success or restaging everything.

**Decision criterion:** this path-limited method does not isolate hunks. If `src/labels.R` also has an unrelated working-tree hunk, do not execute step 2: ask how the overlapping work should be isolated. Selecting one hunk into the normal index would not make `commit --only` use just that hunk. Preserve the original staged state while resolving that scope question.
