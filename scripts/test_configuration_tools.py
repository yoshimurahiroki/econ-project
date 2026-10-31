"""Run scoped helpers against temporary projects and a fake IDE CLI only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE_ROOT = Path(__file__).resolve().parents[1]


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
        for name in ('MAKEFLAGS', 'MFLAGS', 'MAKELEVEL', 'MAKEOVERRIDES'):
            self.env.pop(name, None)

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

    def test_sync_runs_as_the_current_user_and_preserves_installer_failure(self):
        shutil.copyfile(SOURCE_ROOT / 'Makefile', self.root / 'Makefile')
        pixi = self.bin / 'pixi'
        pixi.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\nexit "${INSTALL_EXIT:-0}"\n')
        pixi.chmod(0o755)
        sudo = self.bin / 'sudo'
        sudo.write_text('#!/bin/sh\necho unexpected-sudo >> "$CALL_LOG"\nexit 87\n')
        sudo.chmod(0o755)
        for _ in range(2):
            result = subprocess.run(['make', '-s', 'sync'], cwd=self.root, env=self.env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / '.pixi').is_dir())
        self.assertEqual(self.log.read_text().splitlines(), ['install', 'install'])
        self.env['INSTALL_EXIT'] = '7'
        result = subprocess.run(['make', '-s', 'sync'], cwd=self.root, env=self.env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

    def test_kernel_registration_resolves_its_project_and_reports_r_failure(self):
        container = self.root / '.devcontainer'
        container.mkdir()
        script = container / 'register-kernels.sh'
        shutil.copyfile(SOURCE_ROOT / '.devcontainer/register-kernels.sh', script)
        runtime = self.root / '.pixi/envs/default/bin'
        runtime.mkdir(parents=True)
        for name in ('python', 'Rscript', 'jupyter'):
            executable = runtime / name
            executable.write_text(
                '#!/bin/sh\nprintf "%s %s\\n" "${0##*/}" "$*" >> "$CALL_LOG"\n'
                'if [ "${0##*/}" = Rscript ]; then exit "${R_EXIT:-0}"; fi\n'
            )
            executable.chmod(0o755)
        result = subprocess.run(['bash', str(script)], cwd=self.base, env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.log.read_text().splitlines()
        self.assertEqual(len(calls), 3)
        self.assertIn('python -m ipykernel install', calls[0])
        self.assertIn('IRkernel::installspec', calls[-1])
        self.env['R_EXIT'] = '9'
        result = subprocess.run(['bash', str(script)], cwd=self.base, env=self.env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

    def test_ci_selects_existing_affected_suites_once_and_returns_failure(self):
        import yaml

        workflow = yaml.safe_load((SOURCE_ROOT / '.github/workflows/quality.yml').read_text())
        script = next(step['run'] for step in workflow['jobs']['changed-code']['steps']
                      if step.get('name') == 'Check changed files and affected small tests')
        shutil.copyfile(SOURCE_ROOT / 'Makefile', self.root / 'Makefile')
        for path in (SOURCE_ROOT / 'scripts').glob('*'):
            if path.is_file():
                shutil.copyfile(path, self.root / 'scripts' / path.name)
        for args in (['init', '-q'], ['add', '.']):
            subprocess.run(['git', *args], cwd=self.root, env=self.env, check=True)

        def commit():
            subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                            'commit', '-qm', 'fixture'], cwd=self.root, env=self.env, check=True)
            return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.root,
                                           env=self.env, text=True).strip()

        self.env['PR_BASE'] = commit()
        for name in ('Makefile', 'scripts/setup_ide_mcp.sh', 'scripts/sync_common_core.py'):
            with (self.root / name).open('a') as output:
                output.write('\n# fixture change\n')
        subprocess.run(['git', 'add', '.'], cwd=self.root, env=self.env, check=True)
        commit()
        pixi = self.bin / 'pixi'
        pixi.write_text(
            f'#!{sys.executable}\n'
            'import json, os, pathlib, sys\n'
            'args = sys.argv[1:]\n'
            'with open(os.environ["CALL_LOG"], "a") as output:\n'
            '    output.write(json.dumps(args) + "\\n")\n'
            'if "pytest" in args:\n'
            '    for target in args[args.index("pytest") + 1:]:\n'
            '        if target.startswith("scripts/") and not pathlib.Path(target.split("::")[0]).is_file():\n'
            '            sys.exit("CI selected missing test: " + target)\n'
            '    sys.exit(int(os.environ.get("TEST_EXIT", "0")))\n'
        )
        pixi.chmod(0o755)
        result = subprocess.run(['bash', '-eu', '-o', 'pipefail', '-c', script],
                                cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        tests = [call for call in calls if 'pytest' in call]
        self.assertEqual(len(tests), 1)
        quality = ('scripts/test_quality_make.py' if (SOURCE_ROOT / 'scripts/test_quality_make.py').is_file()
                   else 'scripts/test_quality_commands.py')
        for target in (quality, 'scripts/test_setup_ide_mcp.py', 'scripts/test_sync_common_core.py',
                       'scripts/test_configuration_tools.py'):
            self.assertEqual(tests[0].count(target), 1)
        if (SOURCE_ROOT / 'scripts/test_build_latex.py').is_file():
            self.assertEqual(tests[0].count('scripts/test_build_latex.py::BuildTests'), 1)
        self.env['TEST_EXIT'] = '19'
        result = subprocess.run(['bash', '-eu', '-o', 'pipefail', '-c', script],
                                cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 19)


if __name__ == '__main__':
    unittest.main(verbosity=2)
