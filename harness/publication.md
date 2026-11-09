# Publish requested outputs and changes

Use this contract for requested file moves, complete multi-file outputs, staging, commits and external publication. [CORE](../runtime/CORE.md) owns authority, preserved inputs, integrated review and completion. [EXECUTION](../runtime/EXECUTION.md) owns ordinary file and computation operations. Existing authorization persists through the work.

Complete the authorized destination through its actual returned operation. Preserve unrelated edits, user settings, original inputs, concurrent writers and destination ownership. A completed component leaves the parent's remaining outputs active.

## Complete-generation boundary

Write each output completely before exposing it. Replace a single file atomically from a temporary file on the destination filesystem. For a linked output set, use the project's existing generation and manifest: finish its required files, then atomically publish the pointer. Each reader resolves one generation and uses that generation throughout its operation.

Keep the preceding complete result available until replacement succeeds. A failed preparation leaves it selected under its original identity. Fixed-path consumers use the existing runner's barrier across replacement and recovery. Resume them after one complete set is available. Give concurrent writers separate destinations or one designated owner.

A requested rollback selects an earlier generation only when its inputs and definitions still satisfy the intended use and a later publisher has not superseded the target. Retain generations needed by active readers. Retirement follows the user's authorized scope.

## Working files, Git and delivery

Inspect current index and working-tree changes before editing or staging. Identify each path's producer, consumers and owner. Update references with a relocation or deletion. Stage only the authorized complete files or reviewed hunks, preserving unrelated staged and unstaged work.

An ordinary commit includes the current index. A path-limited `git commit --only` includes the named files' complete working-tree contents. Choose it only when those entire changes belong to the requested commit and no concurrent writer or merge owns them. Resolve overlapping changes through their owner before selecting hunks. Use the returned commit and patch to establish the saved scope; keep the existing index for other work.

For a cross-filesystem move, copy into a separate destination-side staging area. Match the stable source's required contents and metadata, publish the complete copy, and update consumers. Remove the original only within the authorized move while it still matches that copy. If another writer changes either side, preserve those changes and reconcile the affected target. A caught failure rolls back only this operation's unchanged writes. Reconcile the actual destination before retrying an interrupted operation.

Derive the delivery layout from the requested recipient, executable entry points and required licenses. Include producing inputs or lawful acquisition instructions, environment, commands and output mapping. Preserve adopted scientific results, project settings and deliberately versioned generated assets. Keep private data and credentials in their existing authorized storage. Inspect ignored files needed by the package. Third-party distribution notices retain their required scope.

Check package-relative references through the actual exporter, synchronize the selected common paths while preserving project-owned settings, and save through the existing Git or plugin operation. Keep repository, parent commit, branch, plugin identity and expected release bound to that write. Distinguish local implementation, saved Git commits, synchronization and published releases through their returned results.
