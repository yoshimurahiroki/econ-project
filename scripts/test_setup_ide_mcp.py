#!/usr/bin/env python3
"""Configuration regeneration preserves user settings and excludes secret values."""
import json
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
        subprocess.run(["bash", str(self.root / "scripts/setup_ide_mcp.sh"), flag], env=self.env,
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
        self.assertEqual(state[".cursor/mcp.json"], [])


    def test_migrates_legacy_generated_toml_without_losing_manual_top_level_settings(self):
        self.codex.write_text('# Generated by scripts/setup_ide_mcp.sh.\nmodel = "chosen-model"\n\n[mcp_servers.exa]\ncommand = "old-command"\n\n[agents.reviewer]\nmodel = "review-model"\n')
        self.run_script("--write")
        generated = self.codex.read_text()
        self.assertIn('model = "chosen-model"', generated)
        self.assertIn('[agents.reviewer]\nmodel = "review-model"', generated)
        self.assertNotIn("old-command", generated)
        self.run_script("--check")


if __name__ == "__main__":
    unittest.main(verbosity=2)
