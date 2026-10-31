"""Run scoped helpers against temporary projects and a fake IDE CLI only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ScopedToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='econ-config-fixture-')
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'
        (self.root / 'scripts').mkdir(parents=True)
        for name in ('pack_context.sh', 'setup_extensions.sh'):
            shutil.copyfile(Path(__file__).with_name(name), self.root / 'scripts' / name)
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        self.log = self.base / 'calls'
        mock = self.bin / 'code'
        mock.write_text('''#!/bin/bash
printf '%s\\n' "$*" >> "$CALL_LOG"
case "$1" in
--list-extensions) echo 'already.installed'; exit "${LIST_FAIL:-0}";;
--install-extension) [[ "$2" != "fail.extension" ]];;
*) exit 88;;
esac
''')
        mock.chmod(0o755)
        # If packing attempts an external collection, fail and record it.
        for name in ('npx', 'repomix'):
            mock = self.bin / name
            mock.write_text('#!/bin/bash\necho external >> "$CALL_LOG"\nexit 89\n')
            mock.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'], CALL_LOG=str(self.log))

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, name, *args):
        return subprocess.run(['bash', str(self.root / 'scripts' / name), *map(str, args)], cwd=self.base,
                              env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def devcontainer(self):
        (self.root / '.devcontainer').mkdir()
        (self.root / '.devcontainer/devcontainer.json').write_text(json.dumps({'customizations': {'vscode': {'extensions': ['already.installed', 'fail.extension', 'good.extension']}}}))

    def test_extension_default_does_not_install_and_unknown_options_fail(self):
        self.devcontainer()
        result = self.run_tool('setup_extensions.sh', '--client', 'code')
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())
        self.assertEqual(self.run_tool('setup_extensions.sh', '--write', '--client', 'code', '--unknown').returncode, 2)
        self.assertFalse(self.log.exists())

    def test_extension_failures_return_nonzero_and_installed_ids_are_skipped(self):
        self.devcontainer()
        result = self.run_tool('setup_extensions.sh', '--client', 'code', '--write')
        self.assertEqual(result.returncode, 1)
        calls = self.log.read_text()
        self.assertNotIn('--install-extension already.installed', calls)
        self.assertIn('--install-extension good.extension', calls)
        self.assertIn(b'fail.extension', result.stderr)

    def test_extension_list_failure_stops_before_installs(self):
        self.env['LIST_FAIL'] = '9'
        result = self.run_tool('setup_extensions.sh', '--client', 'code', '--write')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('--install-extension', self.log.read_text())

    def test_extension_malformed_required_input_has_no_cli_calls(self):
        self.devcontainer()
        (self.root / '.devcontainer/devcontainer.json').write_text('{broken')
        self.assertNotEqual(self.run_tool('setup_extensions.sh', '--client', 'code', '--write').returncode, 0)
        self.assertFalse(self.log.exists())

    def test_pack_requires_scope_and_keeps_exclusions_out(self):
        out = self.base / 'context.txt'
        self.assertNotEqual(self.run_tool('pack_context.sh', '--output', out).returncode, 0)
        self.assertFalse(out.exists())
        (self.root / 'public.md').write_text('public text')
        for relative in ('secrets/credentials.json', '.agents/state/session.json', '.codex/config.toml', '.env', 'mcp.json'):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('PRIVATE_SENTINEL')
        result = self.run_tool('pack_context.sh', '--output', out, '.')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('public text', out.read_text())
        self.assertNotIn('PRIVATE_SENTINEL', out.read_text())
        self.assertFalse(self.log.exists())
        self.assertNotEqual(self.run_tool('pack_context.sh', '--output', out, 'public.md').returncode, 0)

    def test_pack_selected_paths_only_and_denies_escapes_and_secret_alias(self):
        (self.root / 'public.md').write_text('selected')
        (self.root / 'other.md').write_text('unselected')
        out = self.base / 'context.txt'
        self.assertEqual(self.run_tool('pack_context.sh', '--output', out, 'public.md').returncode, 0)
        self.assertNotIn('unselected', out.read_text())
        (self.root / 'secrets').mkdir()
        (self.root / 'secrets/private.txt').write_text('private')
        (self.root / 'alias').symlink_to(self.root / 'secrets', target_is_directory=True)
        for scope in ('../context.txt', 'alias/private.txt', 'secrets', 'missing'):
            self.assertNotEqual(self.run_tool('pack_context.sh', '--output', self.base / 'new.txt', scope).returncode, 0)
            self.assertFalse((self.base / 'new.txt').exists())
        self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
