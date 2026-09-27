# Reproducible execution

Use the existing runner and analysis entry point. Recompute only the outputs affected by changed data, code or parameters. Reuse unchanged results from their recorded source version; avoid routine checksum sweeps and cache frameworks.

Keep reportable numbers connected to the generating command, sample, specification and source object in the existing analysis. Preserve dependency versions and seeds. Add an execution record only when it is needed to reproduce or transfer the requested result.

Use existing output or one representative execution to settle a concrete risk. Add a separate fixture, benchmark or cross-language comparison only when that risk requires it. Skip repeated tests of built-in or library behavior. Full clean execution belongs to an explicit reproduction/release request or a result that requires the complete pipeline.

A replication compares the requested results against their source with a meaningful tolerance. Routine code work stops after the changed behavior is established. Keep essential scientific evidence; omit passing-check logs, scorecards and duplicate reports.
