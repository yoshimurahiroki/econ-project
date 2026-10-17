#!/usr/bin/env python3
"""Configuration regeneration preserves user settings and excludes secret values."""
import json
from unittest.mock import patch
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
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
        self.env = {key: value for key, value in os.environ.items() if key not in {"BRAVE_API_KEY", "EXA_API_KEY", "GITHUB_PERSONAL_ACCESS_TOKEN", "DATABASE_URL", "ENABLE_GOOGLE_DRIVE_MCP", "ENABLE_CONTEXT_MCP"}}

    def tearDown(self):
        self.temp.cleanup()

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
