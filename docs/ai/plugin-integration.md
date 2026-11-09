# Economics Research Skills integration

## Source and distribution

[econ-project-mini](https://github.com/yoshimurahiroki/econ-project-mini) owns the shared instructions and implementation. Its canonical files are `runtime/`, `skills/`, `registry/`, `quality/`, `profiles/`, `harness/` and the registered maintenance scripts. `registry/resources.json` declares ownership; `registry/placements.json` declares repository and Project output paths.

The common source is synchronized to explicitly selected public or private destinations. Public manifests contain the skills without account-specific apps, MCP endpoints or credentials. A private distribution owns its account release, authenticated app bindings and service source; these are outside the common resource registry. Repository `.agents/` files, IDE entrances, Project exports and the shared plugin runtime use the same canonical instructions. The synchronization receipt in `docs/ai/common-core.json` binds each synchronized destination to its source commit and managed file hashes.

## Writing and execution

`econ-writing` owns `compose`, `revise`, `explain`, `translate`, `convert`, `guidance` and explicitly requested `profile` work. Japanese clarity and concision requests reach `econ-writing` directly. The historical `explain-before-shorten` selector resolves to `econ-writing:revise`; the independent skill is retired.

Each operation reads CORE, PROSE and the complete selected mode and dependency text. CORE owns substantive reasoning, authorized execution, one integrated review and checks of affected behavior. PROSE owns direct argument, natural Japanese and English, and removal of defensive rhetoric. The writing skill completes the explanation before shortening it. The data skill owns minimal implementation and verification of the behavior changed by code.

The existing native harness supplies independent review, paragraph and argument state, source bindings and certified publication when that workflow is explicitly selected. Its recorded reviewer identities and release predicates stay within that selected workflow. Ordinary operations complete through CORE and their own result contracts.

## Synchronize repositories

Use [the integration commands](integration.md#common-core) to compare the selected source and destinations, inspect ownership conflicts and pin current HEADs. Synchronize committed source or bind a completed working source to the comparison's `common_content_id` with `--expect-source-content`. Synchronize the registered canonical source. Retire development artifacts and tracked generated deployments through explicit deletions; preserve project-owned research data and local state. Transfer retired paths with `--move` or `--delete`, retain project-owned paths, and stage the explicit changed files. Regenerate each destination’s policy manifest from its adopted canonical files.

Read each destination's current project instructions before changing its integration. Its installed-plugin arrangement, project specification, research code, data, results and site retain their project ownership.

## Publish the plugin

Use the existing exporter and account-update workflow:

1. Save the shared source and synchronize the registered files. Keep mini's lightweight template and full's scientific dependencies, Pixi/rv locks and environment configuration under their own owners. Update the existing public plugin manifests and policy version together.
2. Run `python scripts/export_project.py --generate-entries` to update canonical entries and their policy manifest once. Then run `python scripts/export_project.py --format plugin --output /tmp/ers-release-new`. The output places one complete canonical runtime tree at `skills/project-work/references/shared/`. The seven top-level Skill entrances retain their names, descriptions and existing `defaultPrompt` values and direct readers to the same plugin's `project-work` package. Read each selected owner's complete `references/shared/skills/<owner>/instructions.md` and the required rule bodies through that package. The exporter updates shared links, resource paths and policy bindings; only the public entrances retain the discoverable `SKILL.md` filename. For implementation or calculation, acquire `project-work/bundle` once for the selected release and use its `references/shared` directory as the runtime root. The top-level `hooks/check.py` delegates to `skills/project-work/references/shared/hooks/check.py`.
3. The exporter places the knowledge runtime collection once at `skills/project-work/references/shared/skills/econ-knowledge/references/`. Its existing retrieval program uses that directory directly. Catalogs and authored chapters remain in the repository; the plugin contains the saved manifest, runtime marker, domain indexes, semantic views and unit bodies. Rebuild the knowledge source only after changing its authored content.
4. Inspect the actual generated package. The package excludes development environments, repository-only maintenance tools, local state and generated per-Skill bundles. Registry references to source-only maintenance remain optional inputs. Keep required third-party notices and package requirements.
5. For the existing account plugin, retrieve its exact current release, manifests and App binding. Overlay its identity, complete prompt values, presentation, ownership and connection configuration on the generated candidate; change the version and authorized files. Keep public repository manifests free of account-specific bindings.
6. Submit the candidate through the existing update operation with that `expected_release_id`. List superseded files from the current inventory in explicit `delete_paths`, including the seven former `skills/project-work/references/shared/skills/<owner>/SKILL.md` bodies, old `skills/*/references/bundle/` copies and former plugin-root common resources now held in the shared tree. Omitted files otherwise remain in the account release.
7. Read back the updated Skill entrances, affected shared resources and inventory. Match the returned release and confirm the requested deletions and preserved connections.

`--format flat` and `--format deployed` continue to select the requested operation and its activated rule bodies. Keep generated packages outside canonical Git tracking. Generation derives its outputs from current canonical source and publishes the policy manifest last. After interruption, rerun generation from that source; no separate persistent generation journal is maintained.

### Reuse an exact release baseline

For an incremental account update, retain the complete candidate archive and file hashes from its immutable source commit. Match the target's current plugin and release IDs to a previously read and verified inventory and content baseline. Compare every candidate path and hash with that exact baseline. A transport archive contains all changed and new files, including changed manifests; explicit deletion paths identify retired files present in the current inventory. The account update overlays uploaded files and preserves omitted files under its declared interface. Submit with the matched `expected_release_id`; a release conflict requires retrieving and reconciling the changed source before retrying.

After saving, match the returned release and resulting inventory to the candidate and confirm every requested deletion. Read back the changed entry points, their affected rule or implementation bodies, and the provider-generated compatibility manifest. Reuse the exporter's completed reference and rule-body resolution for unchanged dependencies. Compare the effective App bindings and prompts with the retrieved baseline. Keep the candidate, baseline identity and actual update return in the existing publication record.

The `project-work` package exposes the single shared tree through its Skill reader and bundle. Read `references/shared/runtime/CORE.md`, `references/shared/runtime/PROSE.md`, `references/shared/registry/operations.json` and the selected specialist's complete body and activated dependencies from that package. The selected specialist and mode retain ownership within `references/shared/skills/<owner>/`. The policy manifest binds paths relative to this shared runtime root. Subsequent releases start from the canonical GitHub source and preserve the account-owned metadata through the same overlay.

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
