# Economics Research Skills integration

## Source and distribution

[econ-project-mini](https://github.com/yoshimurahiroki/econ-project-mini) owns the shared instructions and implementation. Its canonical files are `runtime/`, `skills/`, `registry/`, `quality/`, `profiles/`, `harness/` and the registered maintenance scripts. `registry/resources.json` declares ownership; `registry/placements.json` declares repository and Project output paths. `plugin.json` is the single manifest source; `--generate-entries` writes `.codex-plugin/plugin.json` from it.

The common source is synchronized to explicitly selected public or private destinations. Public manifests contain the skills without account-specific apps, MCP endpoints or credentials. A private distribution owns its account release, authenticated app bindings and service source; these are outside the common resource registry. Repository `.agents/` files, IDE entrances, Project exports and the plugin runtime use the same canonical instructions. Plugin knowledge files live at root `knowledge/references` and in the execution bundle, outside Skill-local file inventories. Native lookup retains the same CLI; cloud lookup without an executor uses the entrance's fixed source revision and the same prerequisite graph. The synchronization receipt in `docs/ai/common-core.json` binds each synchronized destination to its source commit and managed file hashes.

## Writing and execution

The resolver reads schema-3 operations/resources and schema-2 placements; it also reads existing schema-2 snapshots. CORE and the owning Skills govern inputs and completion. Every current-stage read restores the kernel and its prerequisites; explicit complete-body reuse suppresses retained text. Whole-resource selections retain section dependency edges. Condition applicability and purpose metadata use the same resolver in readers, hooks and exporters. Bound method conditions return knowledge read commands at contract. Bootstrap verification loads the resolver and catalogs. State, paragraph/argument execution and lexical checking enter through their resource dependencies. Modifications and external actions retain exact authority, output versions and actual returns. Resumption restores TEAM recovery rules.

`econ-writing` owns `compose`, `revise`, `explain`, `translate`, `convert`, `guidance` and explicitly requested `profile` work. Japanese clarity and concision requests reach `econ-writing` directly and use the [shared Japanese drafting and revision rules](../../runtime/PROSE.md#revise-for-the-requested-language). The historical `explain-before-shorten` selector resolves to `econ-writing:revise`; the independent skill is retired.

Borrowing and imitating inspected sources for every writing element is owned by [PROSE Common output](../../runtime/PROSE.md#common-output).

Adopted fictional profile bodies remain intact and are never real source evidence. Profile selection does not replace real source correspondence for any prose or visual element. Preserve the supplied templates' exact bytes while grounding the resulting visual treatment in inspected real sources and making only necessary adjustments consistent with the specified medium and template requirements.

[CORE](../../runtime/CORE.md) owns entry, authority and completion; [PROSE](../../runtime/PROSE.md) owns expression, and specialist Skills own their procedures. [TEAM](../../runtime/TEAM.md#review-findings-and-independence) owns explicitly selected independent review. The [state interface](../../harness/state.md) retains source bindings and paragraph/argument state when the selected workflow needs them. The separately selected Checked Artifacts service owns its validation and publication operations.

## Synchronize repositories

Use [the integration commands](integration.md#common-core) to compare the selected source and destinations, inspect ownership conflicts and pin current HEADs. Synchronize committed source or bind a completed working source to the comparison's `common_content_id` with `--expect-source-content`. Synchronize the registered canonical source. Retire development artifacts and tracked generated deployments through explicit deletions; preserve project-owned research data and local state. Transfer retired paths with `--move` or `--delete`, retain project-owned paths, and stage the explicit changed files. Before committing or pushing, inspect the exact candidate tree, including tracked generated files: distribute canonical rules, technical examples, code, templates and public citations; keep consulted originals, excerpts, reading logs and acquisition records in the private working record outside both repositories. Regenerate each destination’s policy manifest from its adopted canonical files.

Read each destination's current project instructions before changing its integration. Its installed-plugin arrangement, project specification, research code, data, results and site retain their project ownership.

## Publish the plugin

Use the existing exporter and account-update workflow:

1. Save the shared source and synchronize the registered files. Keep mini's lightweight template and full's scientific dependencies, Pixi/rv locks and environment configuration under their own owners. Update the existing public plugin manifests and policy version together.
2. Run `python scripts/export_project.py --generate-entries`, then `python scripts/export_project.py --check`, then `python scripts/export_project.py --format plugin --output /tmp/ers-release-new` from the source Git repository. The check computes entries and their policy manifest in memory, reports differing paths with exit code 1, and validates all nine declared hook budgets. Export consumes the checked source. Its origin and committed saved knowledge generation pin executor-free source references. The native plugin keeps the canonical runtime at its root, including the hook. Each of the seven entrances reads its own `instructions.md` and specialist references. Common prose is exposed through `project-work/references/shared/`; executable modules and machine-readable assets remain at the native root and in the existing `runtime.zip`.
3. For cloud execution, acquire `project-work/bundle`, extract the Skill, then use `python -m zipfile -e references/runtime.zip RUNTIME` and execute from `RUNTIME`. The archive contains the exact native-runtime bytes and paths; native hooks require no extraction. Knowledge lives at runtime-root `knowledge/references`, outside Skill directories. Without an executor, follow the entrance's pinned domain index, exact units and applicable semantic prerequisites at that revision. Catalogs/chapters remain source-only; saved manifests, indexes, semantic views and complete unit bodies are preserved. Rebuild knowledge only after authored-content changes.
4. Inspect the actual generated package and the entries and content of `skills/project-work/references/runtime.zip` against the private source holdings. Pass canonical resources and public citations to the account update; retain consulted originals, excerpts, reading logs and acquisition records in the private working record. The package excludes development environments, repository-only maintenance tools, local state and separate per-Skill execution bundles. Registry references to source-only maintenance remain optional inputs. Keep required third-party notices and package requirements.
5. For the existing account plugin, retrieve its exact current release, manifests and App binding. Overlay its identity, complete prompt values, presentation, ownership and connection configuration on the generated candidate; change the version and authorized files. Keep public repository manifests free of account-specific bindings.
6. Submit the candidate through the existing update operation with that `expected_release_id`. Delete only superseded paths present in the current inventory through explicit `delete_paths`. For a layout migration, remove only superseded exposed paths after their complete current replacements and execution archive are verified. Omitted files otherwise remain in the account release.
7. Read back the updated Skill entrances, owner-scoped resources, common views and full inventory; obtain the actual Skill bundle to verify its binary runtime archive. Match the returned release and confirm the requested deletions and preserved connections.

`--format flat` and `--format deployed` continue to select the requested operation and its activated rule bodies. Keep generated packages outside canonical Git tracking. Generation derives its outputs from current canonical source and publishes the policy manifest last. After interruption, rerun generation from that source; no separate persistent generation journal is maintained.

### Reuse an exact release baseline

For an incremental account update, retain the complete candidate archive and file hashes from its immutable source commit. Match the target's current plugin and release IDs to a previously read and verified inventory and content baseline. Compare every candidate path and hash with that exact baseline. A transport archive contains all changed and new files, including changed manifests; explicit deletion paths identify retired files present in the current inventory. The account update overlays uploaded files and preserves omitted files under its declared interface. Submit with the matched `expected_release_id`; a release conflict requires retrieving and reconciling the changed source before retrying.

After saving, match the returned release and resulting inventory to the candidate and confirm every requested deletion. Read back the changed entry points, their affected rule or implementation bodies, and the provider-generated compatibility manifest. Reuse the exporter's completed reference and rule-body resolution for unchanged dependencies. Compare the effective App bindings and prompts with the retrieved baseline. Keep the candidate, baseline identity and actual update return in the existing publication record.

Read common bodies directly through project-work without opening its main entry for a file catalog. Read a specialist body through its own package and known resource path. The runtime manifest binds the native root and its identical archive. A host may append a Skill file inventory to its main entry; count that actual response separately from authored text and avoid catalog reads for known resources. Subsequent releases use the canonical source and the same account-metadata overlay.

## Data and authentication ownership

Public calculations read public sources or the current operator's explicitly configured credentials. EDINET and e-Stat use `EDINET_API_KEY` and `ESTAT_APP_ID`; absence is an error with registration instructions. There is no owner-key or hosted-service fallback. Save inputs, raw documents and valuation histories outside tracked source paths.

A private browser integration authenticates the caller before invoking MCP tools. API credentials, raw-object access, valuation lookup, parent references and history queries all use that authenticated identity. A global encryption key protects storage; it is not an API credential shared among callers. Bind encrypted credentials to both user and provider, and never return their values in status, URLs or logs. Keep the private app manifest, hosting configuration, service bindings and persistent data in the private distribution. Common-source synchronization must not change them.

Public archives contain the canonical public source and selected generated dependencies. Private account updates retain the retrieved App bindings, prompts and configuration. Historical public commits and their source archives remain accessible after an ordinary cleanup commit; removing those objects requires a separately authorized history rewrite and, where applicable, host cache removal.

## Checked Artifacts connection

Economics Checked Artifacts remains a separately selected integration. Its instruction package and the research plugin retain their existing identities. The existing configuration generator uses an explicitly selected endpoint and clients:

```sh
ENABLE_ECONOMICS_CHECKED_MCP=1 \
ECONOMICS_CHECKED_MCP_URL='<your HTTPS MCP endpoint>' \
bash scripts/setup_ide_mcp.sh --client codex --client claude

ENABLE_ECONOMICS_CHECKED_MCP=1 \
ECONOMICS_CHECKED_MCP_URL='<your HTTPS MCP endpoint>' \
bash scripts/setup_ide_mcp.sh --write --client codex --client claude
```

Keep personal endpoints and credentials in the existing local configuration and credential storage. Preserve manually owned settings during regeneration. Authentication and research-data submission follow the user's authorization and the receiving service's controls. The selected certified workflow uses its existing policy, guidance, validation and publication operations.
