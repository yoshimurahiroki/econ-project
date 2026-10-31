#!/usr/bin/env python3
"""Configuration regeneration preserves user settings and excludes secret values."""
import json
from unittest.mock import patch
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="econ-mcp-test-")
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "runtime").mkdir(parents=True)
        source = Path(__file__).parents[1]
        if (source / "registry").exists():
            shutil.copytree(source / "registry", self.root / "registry")
        else:
            shutil.copyfile(source / "runtime/ROUTES.yaml", self.root / "runtime/ROUTES.yaml")
        shutil.copyfile(source / "scripts/route_registry.py", self.root / "scripts/route_registry.py")
        shutil.copytree(Path(__file__).parents[1] / "docs/ai/config-templates", self.root / "docs/ai/config-templates")
        shutil.copytree(source / "references/repository-policy/.codex/agents", self.root / "references/repository-policy/.codex/agents")
        shutil.copyfile(Path(__file__).with_name("setup_ide_mcp.sh"), self.root / "scripts/setup_ide_mcp.sh")
        (self.root / ".vscode").mkdir()
        (self.root / ".vscode/settings.json").write_text(json.dumps({"model": "user-choice", "mcpServers": {}, "editor.fontSize": 19}))
        (self.root / ".devcontainer").mkdir()
        (self.root / ".devcontainer/devcontainer.json").write_text(json.dumps({"workspaceFolder": "/workspaces/econ-project", "customizations": {"vscode": {"settings": {"editor.fontSize": 19, "mcpServers": {}}}}}))
        (self.root / ".codex").mkdir()
        self.codex = self.root / ".codex/config.toml"
        self.user = 'model = "chosen-model"\napproval_policy = "on-request"\n\n[agents.reviewer]\nmodel = "review-model"\n\n[permissions]\nworkspace_write = true\n\n[mcp_servers.user_owned]\ncommand = "manual-server"\n'
        self.codex.write_text(self.user)
        (self.root / ".cursor").mkdir()
        (self.root / ".cursor/mcp.json").write_text(json.dumps({"privatePreference": "keep", "mcpServers": {}}))
        self.env = {key: value for key, value in os.environ.items() if key not in {"BRAVE_API_KEY", "EXA_API_KEY", "GITHUB_PERSONAL_ACCESS_TOKEN", "DATABASE_URL", "ENABLE_GOOGLE_DRIVE_MCP", "ENABLE_CONTEXT_MCP", "ENABLE_ECONOMICS_CHECKED_MCP", "ECONOMICS_CHECKED_MCP_URL"}}
        self.home = self.root / 'home'
        self.env.update(HOME=str(self.home), CODEX_HOME=str(self.root / 'codex-home'))

    def tearDown(self):
        self.temp.cleanup()

    def checked_command(self, *args):
        return subprocess.run(['bash', str(self.root / 'scripts/setup_ide_mcp.sh'), *args],
                              env=self.env, capture_output=True, text=True)

    def test_checked_disabled_has_no_destination_or_network_request(self):
        import contextlib
        import io
        import sys
        script = (self.root / 'scripts/setup_ide_mcp.sh').read_text()
        body = script.split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
        namespace = {'__name__': 'configuration_fixture'}
        with patch.dict(os.environ, {**self.env, 'PROJECT_ROOT': str(self.root)}, clear=True):
            exec(compile(body, 'configuration_fixture', 'exec'), namespace)
            for values in ({}, {'ECONOMICS_CHECKED_MCP_URL': 'https://checker.example.invalid/mcp'}):
                with patch.dict(os.environ, values), patch.object(sys, 'argv', ['config', '--print']), \
                        patch('socket.socket', side_effect=AssertionError('network request')), \
                        contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(0, namespace['main']())
                    self.assertEqual({}, json.loads(output.getvalue())['mcpServers'])

    def test_checked_endpoint_requires_opt_in_and_is_resolved_by_generator(self):
        self.env['ENABLE_ECONOMICS_CHECKED_MCP'] = '1'
        self.env['ECONOMICS_CHECKED_MCP_URL'] = 'https://checker.example.invalid/mcp'
        result = self.checked_command('--write', '--client', 'codex', '--client', 'cursor')
        self.assertEqual(0, result.returncode, result.stderr)
        server = json.loads((self.root / '.cursor/mcp.json').read_text())['mcpServers']['economics-checked-artifacts']
        self.assertEqual({'type': 'http', 'url': self.env['ECONOMICS_CHECKED_MCP_URL']}, server)
        self.assertIn('url = "https://checker.example.invalid/mcp"', self.codex.read_text())
        self.assertNotIn('${ECONOMICS_CHECKED_MCP_URL}', self.codex.read_text())
        self.env.pop('ENABLE_ECONOMICS_CHECKED_MCP')
        result = self.checked_command('--write', '--client', 'codex', '--client', 'cursor')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn('economics-checked-artifacts', self.codex.read_text())

    def test_checked_bad_endpoints_and_shared_targets_prevent_writes(self):
        self.env['ENABLE_ECONOMICS_CHECKED_MCP'] = '1'
        before = self.codex.read_bytes()
        for endpoint in ('', 'http://checker.example.invalid/mcp',
                         'https://user:secret@checker.example.invalid/mcp',
                         'https://checker.example.invalid/mcp?token=secret',
                         'https://checker.example.invalid/mcp#fragment'):
            with self.subTest(endpoint=endpoint):
                self.env['ECONOMICS_CHECKED_MCP_URL'] = endpoint
                self.assertNotEqual(0, self.checked_command('--write', '--client', 'codex').returncode)
                self.assertEqual(before, self.codex.read_bytes())
        self.env['ECONOMICS_CHECKED_MCP_URL'] = 'https://checker.example.invalid/mcp'
        self.assertNotEqual(0, self.checked_command('--write', '--client', 'vscode').returncode)

    def test_checked_manual_endpoint_is_preserved(self):
        self.env.update(ENABLE_ECONOMICS_CHECKED_MCP='1',
                        ECONOMICS_CHECKED_MCP_URL='https://checker.example.invalid/mcp')
        manual = {'economics-checked-artifacts': {'type': 'http', 'url': 'https://manual.example.invalid/mcp'}}
        path = self.root / '.cursor/mcp.json'
        path.write_text(json.dumps({'mcpServers': manual}))
        self.assertEqual(0, self.checked_command('--write', '--client', 'cursor').returncode)
        self.assertEqual(manual, json.loads(path.read_text())['mcpServers'])

    def test_checked_destinations_are_ignored_and_tracked_destination_is_rejected(self):
        source = Path(__file__).parents[1]
        shutil.copyfile(source / '.gitignore', self.root / '.gitignore')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        for relative in ('.codex/config.toml', '.mcp.json', '.cursor/mcp.json', '.agents/state/mcp-generated.json'):
            self.assertEqual(0, subprocess.run(['git', '-C', str(self.root), 'check-ignore', '--no-index', '-q', relative]).returncode)
        self.env.update(ENABLE_ECONOMICS_CHECKED_MCP='1',
                        ECONOMICS_CHECKED_MCP_URL='https://checker.example.invalid/mcp')
        self.assertEqual(0, self.checked_command('--write', '--client', 'codex').returncode)
        subprocess.run(['git', '-C', str(self.root), 'add', '-f', '.codex/config.toml'], check=True)
        self.assertNotEqual(0, self.checked_command('--write', '--client', 'codex').returncode)

    def run_script(self, flag):
        subprocess.run(["bash", str(self.root / "scripts/setup_ide_mcp.sh"), flag, "--client", "cursor", "--client", "codex", "--client", "vscode", "--client", "devcontainer"], env=self.env,
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def test_preserves_codex_models_roles_permissions_manual_mcp_and_json_fields(self):
        self.env["EXA_API_KEY"] = "fixture-value-must-never-be-saved"
        self.env["DATABASE_URL"] = "postgres://fixture-private"
        self.run_script("--write")
        generated = self.codex.read_text()
        self.assertTrue(generated.startswith(self.user))
        self.assertIn('env_vars = ["EXA_API_KEY"]', generated)
        self.assertIn('[mcp_servers.postgres]', generated)
        self.assertIn("$" + "{DATABASE_URL:?Set DATABASE_URL", generated)
        self.assertEqual(json.loads((self.root / ".cursor/mcp.json").read_text())["privatePreference"], "keep")
        self.assertEqual(json.loads((self.root / ".vscode/settings.json").read_text())["editor.fontSize"], 19)
        self.assertEqual(json.loads((self.root / ".devcontainer/devcontainer.json").read_text())["workspaceFolder"], "/workspaces/econ-project")
        for path in self.root.rglob("*"):
            if path.is_file():
                content = path.read_text()
                self.assertNotIn("fixture-value-must-never-be-saved", content)
                self.assertNotIn("postgres://fixture-private", content)
        self.run_script("--check")
        self.run_script("--write")
        self.assertEqual(generated, self.codex.read_text())
        self.env.pop("EXA_API_KEY")
        self.env.pop("DATABASE_URL")
        self.run_script("--write")
        self.assertNotIn("[mcp_servers.exa]", self.codex.read_text())
        self.assertTrue(self.codex.read_text().startswith(self.user))

    def test_codex_team_roundtrip_preserves_unrelated_configuration(self):
        self.codex.write_text('# personal comment\nmodel = "old" # retain this comment\nmodel_provider = "custom"\napproval_policy = "on-request"\n\n[model_providers.custom]\nbase_url = "https://example.invalid/v1"\n\n[agents]\nmax_concurrent_threads_per_session = 5\n\n[agents.reviewer]\nmodel = "review-model"\n\n[permissions]\nworkspace_write = true\n\n[mcp_servers.user_owned]\ncommand = "manual-server"\n')
        self.env['EXA_API_KEY'] = 'enabled'
        result = self.checked_command('--write', '--client', 'codex', '--codex-team')
        self.assertEqual(0, result.returncode, result.stderr)
        text = self.codex.read_text()
        data = tomllib.loads(text)
        self.assertEqual(data['model'], 'gpt-6.1-sol')
        self.assertEqual(data['model_provider'], 'openai')
        self.assertEqual(data['model_providers']['custom']['base_url'], 'https://example.invalid/v1')
        self.assertEqual(data['model_reasoning_effort'], 'xhigh')
        self.assertEqual(data['forced_login_method'], 'chatgpt')
        self.assertEqual(data['agents']['enabled'], True)
        self.assertEqual(data['agents']['max_concurrent_threads_per_session'], 5)
        self.assertEqual(data['agents']['default_subagent_model'], 'gpt-6.1-sol')
        self.assertEqual(data['agents']['default_subagent_reasoning_effort'], 'xhigh')
        self.assertEqual(data['agents']['reviewer']['model'], 'review-model')
        self.assertEqual(data['permissions']['workspace_write'], True)
        self.assertEqual(data['mcp_servers']['user_owned']['command'], 'manual-server')
        self.assertNotIn('exa', data['mcp_servers'])
        self.assertIn('# personal comment', text)
        self.assertIn('# retain this comment', text)
        for role, model in [('terra', 'gpt-6.1-terra'), ('luna', 'gpt-6-luna'), ('astra', 'gpt-6-astra')]:
            data = tomllib.loads((self.root / '.codex/agents' / (role + '.toml')).read_text())
            self.assertEqual(set(data), {'name', 'description', 'developer_instructions', 'model', 'model_reasoning_effort'})
            self.assertEqual((data['name'], data['model'], data['model_reasoning_effort']), (role, model, 'xhigh'))
        self.assertEqual(0, self.checked_command('--check', '--client', 'codex', '--codex-team').returncode)
        self.assertEqual(0, self.checked_command('--write', '--client', 'codex', '--codex-team').returncode)
        self.assertEqual(text, self.codex.read_text())

    def test_codex_team_rejects_unscoped_and_preserves_edited_role(self):
        for args in (('--codex-team',), ('--codex-team', '--print', '--client', 'codex'),
                     ('--codex-team', '--write', '--client', 'cursor'),
                     ('--codex-team', '--write', '--client', 'codex', '--client', 'cursor')):
            self.assertEqual(2, self.checked_command(*args).returncode)
        role = self.root / '.codex/agents/terra.toml'
        role.parent.mkdir()
        role.write_text('name = "my-custom-role"\n')
        before = self.snapshot()
        result = self.checked_command('--write', '--client', 'codex', '--codex-team')
        self.assertEqual(1, result.returncode)
        self.assertIn('Conflict:', result.stderr)
        self.assertEqual(before, self.snapshot())
        role.unlink()
        result = self.checked_command('--write', '--client', 'codex', '--codex-team')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(3, tomllib.loads(self.codex.read_text())['agents']['max_concurrent_threads_per_session'])
        role.write_text(role.read_text() + '# personal change\n')
        self.codex.write_text(self.codex.read_text().replace('gpt-6.1-sol', 'user-model', 1))
        before = self.snapshot()
        for mode in ('--diff', '--check', '--write'):
            result = self.checked_command(mode, '--client', 'codex', '--codex-team')
            self.assertEqual(1, result.returncode)
            self.assertIn('Conflict:', result.stderr)
            self.assertIn('.codex/agents/terra.toml', result.stderr)
            self.assertEqual(before, self.snapshot())

    def test_user_team_scope_roundtrip_preserves_existing_configuration(self):
        target = Path(self.env['CODEX_HOME'])
        target.mkdir()
        config = target / 'config.toml'
        config.write_text('model = "old"\napproval_policy = "on-request"\n\n[agents]\nmax_threads = 7\n\n[permissions]\nworkspace_write = true\n\n[mcp_servers.manual]\ncommand = "manual"\n')
        project_before = self.codex.read_bytes()
        args = ('--codex-team', '--client', 'codex', '--scope', 'user')
        preview = self.checked_command(*args)
        self.assertEqual(0, preview.returncode, preview.stderr)
        self.assertIn('codex-home/config.toml', preview.stdout)
        self.assertNotIn('gpt-6.1-sol', config.read_text())
        self.assertEqual(1, self.checked_command(*args, '--check').returncode)
        result = self.checked_command(*args, '--write')
        self.assertEqual(0, result.returncode, result.stderr)
        data = tomllib.loads(config.read_text())
        self.assertEqual((data['model'], data['model_provider'], data['model_reasoning_effort'], data['forced_login_method']),
                         ('gpt-6.1-sol', 'openai', 'xhigh', 'chatgpt'))
        self.assertEqual(data['agents']['max_threads'], 7)
        self.assertNotIn('max_concurrent_threads_per_session', data['agents'])
        self.assertEqual(data['permissions']['workspace_write'], True)
        self.assertEqual(data['mcp_servers']['manual']['command'], 'manual')
        for role in ('terra', 'luna', 'astra'):
            self.assertEqual(tomllib.loads((target / 'agents' / f'{role}.toml').read_text())['name'], role)
        state = json.loads((target / '.agents/state/mcp-generated.json').read_text())
        self.assertIn('agents/terra.toml', state)
        self.assertEqual(self.codex.read_bytes(), project_before)
        self.assertEqual(0, self.checked_command(*args, '--check').returncode)
        self.assertEqual(0, self.checked_command(*args, '--write').returncode)

    def test_user_team_scope_default_home_and_conflict_preserves_all_targets(self):
        self.env.pop('CODEX_HOME')
        target = self.home / '.codex'
        args = ('--codex-team', '--client', 'codex', '--scope', 'user')
        self.assertEqual(0, self.checked_command(*args, '--write').returncode)
        role = target / 'agents/terra.toml'
        role.write_text(role.read_text() + '# personal change\n')
        config = target / 'config.toml'
        config.write_text(config.read_text().replace('gpt-6.1-sol', 'personal-model', 1))
        before = {path: path.read_bytes() for path in target.rglob('*') if path.is_file()}
        for mode in ('--diff', '--check', '--write'):
            result = self.checked_command(*args, mode)
            self.assertEqual(1, result.returncode)
            self.assertIn('Conflict:', result.stderr)
            self.assertEqual(before, {path: path.read_bytes() for path in target.rglob('*') if path.is_file()})

    def test_user_team_scope_preexisting_role_is_not_adopted(self):
        target = Path(self.env['CODEX_HOME'])
        (target / 'agents').mkdir(parents=True)
        config = target / 'config.toml'
        config.write_text('model = "personal-model"\n')
        role = target / 'agents/terra.toml'
        role.write_text('name = "custom"\n')
        before = {path: path.read_bytes() for path in target.rglob('*') if path.is_file()}
        result = self.checked_command('--codex-team', '--client', 'codex', '--scope', 'user', '--write')
        self.assertEqual(1, result.returncode)
        self.assertIn('Conflict:', result.stderr)
        self.assertEqual(before, {path: path.read_bytes() for path in target.rglob('*') if path.is_file()})

    def test_user_team_scope_reuses_ownership_from_another_project(self):
        args = ('--codex-team', '--client', 'codex', '--scope', 'user')
        result = self.checked_command(*args, '--write')
        self.assertEqual(0, result.returncode, result.stderr)
        other = self.root / 'other-project'
        for directory in ('scripts', 'registry', 'docs/ai/config-templates', 'references/repository-policy/.codex/agents'):
            shutil.copytree(self.root / directory, other / directory)
        source = other / 'references/repository-policy/.codex/agents/luna.toml'
        source.write_text(source.read_text() + '# updated template\n')
        result = subprocess.run(['bash', str(other / 'scripts/setup_ide_mcp.sh'), *args, '--write'],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        installed = Path(self.env['CODEX_HOME']) / 'agents/luna.toml'
        self.assertEqual(source.read_bytes(), installed.read_bytes())
        state = json.loads((Path(self.env['CODEX_HOME']) / '.agents/state/mcp-generated.json').read_text())
        self.assertEqual(state['agents/luna.toml']['owned']['content'], source.read_text())

    def test_user_team_scope_rejects_invalid_combinations_and_symlink(self):
        for args in (('--scope', 'user'), ('--scope', 'user', '--client', 'codex'),
                     ('--scope', 'user', '--codex-team', '--client', 'cursor'),
                     ('--scope', 'user', '--codex-team', '--client', 'codex', '--print')):
            self.assertEqual(2, self.checked_command(*args).returncode)
        target = Path(self.env['CODEX_HOME'])
        elsewhere = self.root / 'elsewhere'
        elsewhere.mkdir()
        target.symlink_to(elsewhere, target_is_directory=True)
        result = self.checked_command('--scope', 'user', '--codex-team', '--client', 'codex', '--write')
        self.assertEqual(1, result.returncode)
        self.assertIn('Symlink configuration path refused', result.stderr)
        self.assertEqual([], list(elsewhere.iterdir()))

    def test_codex_team_does_not_reconcile_mcp_or_validate_integrations(self):
        self.env['BRAVE_API_KEY'] = 'enabled'
        result = self.checked_command('--write', '--client', 'codex')
        self.assertEqual(0, result.returncode, result.stderr)
        original = self.codex.read_text()
        original_mcp = original[original.index('[mcp_servers.user_owned]'):]
        state_path = self.root / '.agents/state/mcp-generated.json'
        original_ownership = json.loads(state_path.read_text())['.codex/config.toml']
        self.env.pop('BRAVE_API_KEY')
        self.env.update(EXA_API_KEY='dummy', ENABLE_GOOGLE_DRIVE_MCP='1',
                        ENABLE_ECONOMICS_CHECKED_MCP='1', ECONOMICS_CHECKED_MCP_URL='invalid')
        result = self.checked_command('--write', '--client', 'codex', '--codex-team')
        self.assertEqual(0, result.returncode, result.stderr)
        text = self.codex.read_text()
        self.assertIn(original_mcp, text)
        data = tomllib.loads(text)['mcp_servers']
        self.assertEqual(set(data), {'user_owned', 'brave-search'})
        self.assertEqual(original_ownership, json.loads(state_path.read_text())['.codex/config.toml'])
        self.assertEqual(0, self.checked_command('--check', '--client', 'codex', '--codex-team').returncode)
        self.env.pop('ENABLE_GOOGLE_DRIVE_MCP')
        self.env.pop('ENABLE_ECONOMICS_CHECKED_MCP')
        result = self.checked_command('--write', '--client', 'codex')
        self.assertEqual(0, result.returncode, result.stderr)
        data = tomllib.loads(self.codex.read_text())['mcp_servers']
        self.assertEqual(set(data), {'user_owned', 'exa'})

    def test_manual_mcp_servers_survive_and_same_name_has_one_codex_table(self):
        manual = {"manual-server": {"command": "user-tool"}, "exa": {"command": "user-exa"}}
        (self.root / ".cursor/mcp.json").write_text(json.dumps({"mcpServers": manual}))
        self.codex.write_text(self.user + '\n[mcp_servers.exa]\ncommand = "user-exa"\n')
        self.env["EXA_API_KEY"] = "fixture-value-must-never-be-saved"
        self.env["BRAVE_API_KEY"] = "fixture-other-value"
        self.run_script("--write")
        actual = json.loads((self.root / ".cursor/mcp.json").read_text())["mcpServers"]
        self.assertEqual(actual["manual-server"], manual["manual-server"])
        self.assertEqual(actual["exa"], manual["exa"])
        self.assertIn("brave-search", actual)
        self.assertEqual(self.codex.read_text().count("[mcp_servers.exa]"), 1)
        self.assertIn('command = "user-exa"', self.codex.read_text())
        self.env.pop("BRAVE_API_KEY")
        self.env.pop("EXA_API_KEY")
        self.run_script("--write")
        actual = json.loads((self.root / ".cursor/mcp.json").read_text())["mcpServers"]
        self.assertEqual(actual, manual)
        self.run_script("--check")
        state = json.loads((self.root / ".agents/state/mcp-generated.json").read_text())
        self.assertEqual(state[".cursor/mcp.json"]["owned"], {})


    def test_preserves_unverifiable_legacy_toml_and_manual_top_level_settings(self):
        self.codex.write_text('# Generated by scripts/setup_ide_mcp.sh.\nmodel = "chosen-model"\n\n[mcp_servers.exa]\ncommand = "old-command"\n\n[agents.reviewer]\nmodel = "review-model"\n')
        self.run_script("--write")
        generated = self.codex.read_text()
        self.assertIn('model = "chosen-model"', generated)
        self.assertIn('[agents.reviewer]\nmodel = "review-model"', generated)
        self.assertIn("old-command", generated)
        self.run_script("--check")

    def invoke(self, *args):
        return subprocess.run(["bash", str(self.root / "scripts/setup_ide_mcp.sh"), *args], env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_e5_json_toml_and_devcontainer_edits_release_ownership(self):
        self.env["EXA_API_KEY"] = "enabled"
        self.run_script("--write")
        cursor = self.root / ".cursor/mcp.json"
        data = json.loads(cursor.read_text())
        data["mcpServers"]["exa"]["command"] = "user-edited-command"
        cursor.write_text(json.dumps(data))
        self.codex.write_text(self.codex.read_text().replace('"npx"', '"user-edited-command"'))
        dev = self.root / ".devcontainer/devcontainer.json"
        data = json.loads(dev.read_text())
        data["customizations"]["vscode"]["settings"]["mcpServers"]["exa"]["command"] = "user-edited-command"
        dev.write_text(json.dumps(data))
        self.run_script("--write")
        self.env.pop("EXA_API_KEY")
        self.run_script("--write")
        self.assertIn("user-edited-command", cursor.read_text())
        self.assertIn("user-edited-command", self.codex.read_text())
        self.assertIn("user-edited-command", dev.read_text())
        state = json.loads((self.root / ".agents/state/mcp-generated.json").read_text())
        for key in (".cursor/mcp.json", ".codex/config.toml", ".devcontainer/devcontainer.json#vscode"):
            self.assertNotIn("exa", state[key]["owned"])
            self.assertIn("exa", state[key]["released"])
        self.run_script("--check")

    def test_e6_unknown_conflicting_and_unscoped_write_options_never_write(self):
        before = self.snapshot()
        for args in (("--unknown-option", "--print"), ("--write",), ("--write", "--check"), ("--client", "bad", "--write")):
            self.assertEqual(self.invoke(*args).returncode, 2, args)
            self.assertEqual(before, self.snapshot())

    def test_default_and_selected_diff_are_read_only(self):
        self.env["EXA_API_KEY"] = "enabled"
        before = self.snapshot()
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(self.invoke("--client", "cursor").returncode, 0)
        self.assertEqual(self.invoke("--check", "--client", "cursor").returncode, 1)
        self.assertEqual(before, self.snapshot())

    def test_selected_client_only(self):
        self.env["EXA_API_KEY"] = "enabled"
        codex = self.codex.read_bytes()
        self.assertEqual(self.invoke("--write", "--client", "cursor").returncode, 0)
        self.assertEqual(codex, self.codex.read_bytes())
        self.assertFalse((self.root / ".windsurf").exists())

    def test_missing_or_invalid_last_selected_input_prevents_all_writes(self):
        self.env["EXA_API_KEY"] = "enabled"
        dev = self.root / ".devcontainer/devcontainer.json"
        dev.unlink()
        for invalid in (None, "{broken"):
            if invalid is not None:
                dev.write_text(invalid)
            before = self.snapshot()
            result = self.invoke("--write", "--client", "cursor", "--client", "devcontainer")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, self.snapshot())

    def test_deleted_generated_entry_is_not_recreated(self):
        self.env["EXA_API_KEY"] = "enabled"
        self.run_script("--write")
        cursor = self.root / ".cursor/mcp.json"
        cursor.write_text('{"mcpServers": {}}')
        self.run_script("--write")
        self.run_script("--write")
        self.assertEqual(json.loads(cursor.read_text())["mcpServers"], {})

    def test_apply_recovers_and_preserves_concurrent_edit(self):
        # Load the exact embedded implementation; mock writes only in the fixture.
        script = (self.root / "scripts/setup_ide_mcp.sh").read_text()
        code = script.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        namespace = {"__name__": "fixture"}
        with patch.dict(os.environ, {"PROJECT_ROOT": str(self.root)}):
            exec(compile(code, "setup_ide_mcp.sh", "exec"), namespace)
        a, b = self.root / "a.json", self.root / "b.json"
        a.write_bytes(b"before-a")
        b.write_bytes(b"before-b")
        plan = {a: (b"before-a", b"after-a"), b: (b"before-b", b"after-b")}
        original = namespace["replace"]
        for concurrent in (False, True):
            a.write_bytes(b"before-a")
            def failing(path, content):
                if path == b:
                    if concurrent:
                        a.write_bytes(b"user-edit")
                    raise OSError("fixture write failure")
                original(path, content)
            namespace["replace"] = failing
            with self.assertRaises(OSError):
                namespace["apply"](plan)
            self.assertEqual(a.read_bytes(), b"user-edit" if concurrent else b"before-a")
            self.assertEqual(b.read_bytes(), b"before-b")
        namespace["replace"] = original
        with self.assertRaises(RuntimeError):
            namespace["apply"](plan)
        self.assertEqual(a.read_bytes(), b"user-edit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
