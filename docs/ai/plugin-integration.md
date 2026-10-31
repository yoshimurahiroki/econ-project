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
2. Copy the selected distribution's tracked source into a temporary staging directory, preserving registered source files such as `references/repository-policy/.agents/AGENTS.md`. Exclude the root repository's `.git`, generated `.agents` deployment, caches, local credentials, source documents and valuation histories. Public archives come from the public source, never from a private tree with files removed afterward. Run `python scripts/export_project.py --generate-entries` from that staging directory to regenerate all five skill entries, package-local bundles and manifests. Include the generated bundles in the plugin release archive; keep them out of the canonical repository.
3. Verify the selected writing modes, reference resolution and generated exports through the existing commands. Remove superseded root `REFERENCE.md` copies and retired skill files from the update archive and the account release's explicit deletion list.
4. Update the existing plugin with its observed release ID. Preserve its identity, ownership, audience, prompts and connections.
5. Read the saved skill entries, active rule bodies and inventory back from the new release.

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
