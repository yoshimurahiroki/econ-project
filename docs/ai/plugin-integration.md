# Economics plugin integration

This repository installs the repository-layout derivative of Economics Research
Skills 0.3.34 and Economics Checked Artifacts instructions 1.0.1. Research files,
adopted project context and local authentication remain project-owned.

## Distribution identity

| Package | Archive SHA-256 |
| --- | --- |
| Economics Research Skills 0.3.34 | `ea1049b4264654f38915a271690e361da07bcde0cfd0ba9a53c6319dfd4de570` |
| Checked Artifacts instructions 1.0.1 | `bdcc03d8974d373fb965c2658a59ccc245c9b8445553bc0507f3cb2c8fb51e3a` |

The Research Skills archive declares version 0.3.34 in both plugin manifests.
Its original exporter rejects the archive with
`Root plugin, Codex plugin and policy versions must match`: the root policy
module is a wrapper without a top-level `POLICY_ID`, and its pinned bundled
implementation declares `economics-native-0.3.32`. Root skill wrappers also omit
the registered workflow sections, which are present in bundled `REFERENCE.md`.

The repository derivative restores those complete registered bodies to canonical
`skills/*/SKILL.md`, retains the primary expression rule from each 0.3.34 wrapper,
and resolves their skill references to repository `SKILL.md` paths. It expands
the pinned policy implementation, retains the wrapper's canonical short-command
insertion, and declares `economics-native-0.3.34`. The original implementation
SHA-256 is `7eaea334b144dc8c774d4d5156909deb8982ac433adfb8e79a458d754d524d14`.
The existing exporter regenerates entries, bundles and manifests; version and
required-body checks remain active. Repository IDE configuration registrations
and quality-check instructions are retained.

## Checked Artifacts connection

The public configuration has no default endpoint. With no opt-in, the generator
adds no Economics Checked MCP server and performs no network request. The
instruction package is separate from a hosted backend; installing it does not
install a server or grant remote approval.

Choose the receiving service, the permitted submission data and the target
client before enabling the connector. Supply the endpoint only in your local
shell, together with explicit opt-in. The generator resolves that value into the
client configuration; clients do not need environment-variable interpolation:

```sh
ENABLE_ECONOMICS_CHECKED_MCP=1 \
ECONOMICS_CHECKED_MCP_URL='<your HTTPS MCP endpoint>' \
bash scripts/setup_ide_mcp.sh --client codex --client claude

ENABLE_ECONOMICS_CHECKED_MCP=1 \
ECONOMICS_CHECKED_MCP_URL='<your HTTPS MCP endpoint>' \
bash scripts/setup_ide_mcp.sh --write --client codex --client claude
```

Endpoint URLs containing credentials, query strings or fragments are rejected.
Personal endpoints may only be written to untracked, Git-ignored local client
configurations, such as `.codex/config.toml` or `.mcp.json`. The shared VS Code
settings and devcontainer targets are rejected for this connector. Keep OAuth
credentials in the client's local credential storage. Authorize authentication
and each research-data submission separately; configuration generation sends no
data and grants no authentication, trust or publication approval.

Existing manual settings retain ownership under the generator's three-way
comparison. A managed connector is removed when regenerating without opt-in;
a manually owned connector remains under its user's control. Remove or disable
that manual connector locally when withdrawing permission to connect.

Use the Checked instruction skill with the connected server's `get_policy`,
`get_guidance`, `open_instruction_panel`, `advance_validation`,
`validate_and_publish` and `get_artifact` tools. Preserve exact candidate hashes,
actual independent reviews and the server's release conditions. Installing these
files does not constitute checker approval or enable automatic host interception.

## Repository maintenance

Canonical source files remain under `skills`, `runtime`, `harness`, `quality`,
`registry` and `profiles`. Use `scripts/sync_common_core.py` to compare and apply
explicit common paths with pinned source and destination HEADs. Use
`scripts/export_project.py --format deployed --output <fresh-directory>` for
deployment generation. Include registered reference resources needed by the
installed workflows. Preserve project-specific client instructions when applying
generated pointers. Keep `docs/ai/repo_context.md` and its adopted writing profile.

Source and deployed policy manifests bind their actual layout and bytes.
After an authorized change to a registered asset, regenerate the corresponding
manifest and verify it with `harness/policy_assets.py`. Run affected export,
synchronization and configuration tests and the repository quality checks before
publishing changes.
