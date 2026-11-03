# Economics Research Skills integration

## Source and distribution

[econ-project-mini](https://github.com/yoshimurahiroki/econ-project-mini) owns the shared instructions and implementation. Its canonical files are `runtime/`, `skills/`, `registry/`, `quality/`, `profiles/`, `harness/` and the registered maintenance scripts. `registry/resources.json` declares ownership; `registry/placements.json` declares repository and Project output paths.

The common source is synchronized to explicitly selected public or private destinations. Public manifests contain the skills without account-specific apps, MCP endpoints or credentials. A private distribution owns its account release, authenticated app bindings and service source; these are outside the common resource registry. Repository `.agents/` files, IDE entrances, Project exports and skill-local plugin bundles are generated from the same canonical instructions. The synchronization receipt in `docs/ai/integration.md` binds each synchronized destination to its source commit and managed file hashes.

## Writing and execution

`econ-writing` owns `compose`, `revise`, `explain`, `translate`, `convert`, `guidance` and explicitly requested `profile` work. Japanese clarity and concision requests reach `econ-writing` directly. The historical `explain-before-shorten` selector resolves to `econ-writing:revise`; the independent skill is retired.

Each operation reads CORE, PROSE and the complete selected mode and dependency text. CORE owns substantive reasoning, authorized execution, one integrated review and checks of affected behavior. PROSE owns direct argument, natural Japanese and English, and removal of defensive rhetoric. The writing skill completes the explanation before shortening it. The data skill owns minimal implementation and verification of the behavior changed by code.

The existing native harness supplies independent review, paragraph and argument state, source bindings and certified publication when that workflow is explicitly selected. Its recorded reviewer identities and release predicates stay within that selected workflow. Ordinary operations complete through CORE and their own result contracts.

## Synchronize repositories

Use [the integration commands](integration.md#common-core) to compare the selected source and destinations, inspect ownership conflicts and pin current HEADs. Commit source changes before synchronization. Transfer retired paths with `--move` or `--delete`, retain project-owned paths, and stage the explicit changed files.

Read each destination's current project instructions before changing its integration. Its installed-plugin arrangement, project specification, research code, data, results and site retain their project ownership.

## Publish the plugin

Use the existing generation and account-update workflow:

1. Synchronize the common source and update both existing plugin manifests and `harness/policy_assets.py` to the release version. Keep public manifests free of app and MCP declarations. Preserve the authorized bindings in a private destination's own manifests.
2. Copy the selected distribution's tracked source into a temporary staging directory, preserving registered source files such as `references/repository-policy/.agents/AGENTS.md`. Exclude the root repository's `.git`, generated `.agents` deployment, caches, local credentials, source documents and valuation histories. Public archives come from the public source, never from a private tree with files removed afterward. Run `python scripts/export_project.py --generate-entries` from that staging directory to regenerate the five specialist entries, the conditional econ-knowledge entry, the project-work entry, and their package-local bundles and manifests. Include the generated bundles in the plugin release archive; keep them out of the canonical repository.
The authored knowledge catalog and chapters generate unit bodies, domain indexes and listing, checked bilingual lexicon, typed relation adjacency, model-contract views and version manifest through `knowledge.py build`; check them with `build --check`. The existing exporter's `knowledge_assets(..., source_assets=True)` identifies the complete canonical source path set from the actual generation. After validating it, the same producer emits a runtime projection with the checked semantic views, applicable indexes and unit bodies, plus an explicit `runtime.json` bound to the source manifest. Selected exports retain their declared understanding-prerequisite closure. Contract source URLs and hashes identify scientific provenance; runtime execution binds to the existing econ-data resource owner. After generating and checking staging bundles, exclude the exact canonical data path set from the active plugin root and retain the runtime collection inside the econ-knowledge reference bundle. The five specialist and project-work bundles retain their instruction and execution dependencies. Local research records, credentials, caches and historical distribution archives are not plugin inputs. Reconcile prior generated deployment inventories through the existing producer and preserve local state and unowned paths.

Use the knowledge Skill's linked bundled program as the installed entry. Verify the root-shaped compatibility program with its existing explicit `--base skills/econ-knowledge/references/bundle/skills/econ-knowledge/references` argument against that same collection. Source and deployed defaults retain their own collection paths. Keep source catalog/chapter validation and runtime projection validation distinct through their explicit generated layout, preserving both stale-file checks and the existing state cache.

3. Verify the selected writing modes, reference resolution and generated exports through the existing commands. Remove superseded root `REFERENCE.md` copies and retired skill files from the update archive and the account release's explicit deletion list.
4. Update the existing plugin with its observed release ID. Preserve its identity, ownership, audience, prompts and connections.
5. Read the saved skill entries, active rule bodies and inventory back from the new release.

### Reuse an exact release baseline

For an incremental account update, retain the complete candidate archive and file hashes from its immutable source commit. Match the target's current plugin and release IDs to a previously read and verified inventory and content baseline. Compare every candidate path and hash with that exact baseline. A transport archive contains all changed and new files, including changed manifests; explicit deletion paths identify retired files present in the current inventory. The account update overlays uploaded files and preserves omitted files under its declared interface. Submit with the matched `expected_release_id`; a release conflict requires retrieving and reconciling the changed source before retrying.

After saving, enumerate the complete resulting inventory and match its release ID and path set to the candidate. Read back and compare every uploaded file, active changed entry and provider-generated compatibility manifest. Reuse an omitted file's earlier content proof only when its candidate hash is byte-identical to the verified baseline and the accepted update was guarded by that baseline's release ID. Combine those retained proofs with the new readbacks to check the complete effective package. Compare the effective App bindings, prompts and other preserved metadata as well. Keep the full candidate, transport archive, baseline identity, exact update return and resulting comparisons in the existing publication record.

Each public skill in the release carries the package-local dependencies required by its operations. The exporter generates these copies from the canonical source and resolves their links inside that skill package. Their source bodies and logical rule IDs remain shared. Subsequent synchronization uses the canonical repository, before staging and bundle generation.

## Data and authentication ownership

Public calculations read public sources or the current operator's explicitly configured credentials. EDINET and e-Stat use `EDINET_API_KEY` and `ESTAT_APP_ID`; absence is an error with registration instructions. There is no owner-key or hosted-service fallback. Save inputs, raw documents and valuation histories outside tracked source paths.

A private browser integration authenticates the caller before invoking MCP tools. API credentials, raw-object access, valuation lookup, parent references and history queries all use that authenticated identity. A global encryption key protects storage; it is not an API credential shared among callers. Bind encrypted credentials to both user and provider, and never return their values in status, URLs or logs. Keep the private app manifest, hosting configuration, service bindings and persistent data in the private distribution. Common-source synchronization must not change them.

Before publishing, inspect both source and generated archives for personal document links, account app identifiers, private endpoints and saved data. Verify the public entry with credentials absent and the private entry with the existing account's credentials and saved records. Historical public commits and their source archives remain accessible after an ordinary cleanup commit; removing those objects requires a separately authorized history rewrite and, where applicable, host cache removal.

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
