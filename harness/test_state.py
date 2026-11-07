"""Bounded, offline state-contract regressions using disposable local fixtures."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('team_state', Path(__file__).with_name('state.py'))
h = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h)

class TeamStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ['input', 'artifact']:
            (self.root / name).write_text(name)
        self.cli('init')

    def cli(self, *args):
        with patch('sys.argv', ['team_state', '--root', str(self.root), *args]), contextlib.redirect_stdout(io.StringIO()) as out:
            h.main()
        return json.loads(out.getvalue())

    def state(self):
        return json.loads((self.root / '.agents/state/team.json').read_text())

    def release(self, task, *args):
        """Supply explicit synthetic user evidence in this offline fixture."""
        hold = args[args.index('--hold-id') + 1]
        evidence = self.root / ('release-' + hold.replace(':', '-') + '.json')
        evidence.write_text(json.dumps({
            'source': 'user', 'message_id': 'fixture-release-' + hold,
            'text': 'Release the named hold for this test fixture.',
            'source_task_id': task, 'hold_id': hold,
        }))
        return self.cli('release-hold', task, *args, '--user-release', evidence.name)

    def task(self, key='T'):
        return self.state()['tasks'][key]

    def add(self, *args, name='T', kind='create'):
        if '--required-output' not in args and '--required-action' not in args:
            target = 'message:1' if kind == 'answer' else ('input' if kind == 'modify' else 'artifact')
            requirement = {'role': 'final', 'kind': 'message' if kind == 'answer' else 'file', 'target': target}
            args = (*args, '--required-output', json.dumps(requirement))
        self.cli('add', name, '--owner', 'writer', '--operation-kind', kind, '--next', 'Produce result', *args)

    def test_permission_hold_needs_recorded_release(self):
        self.add(kind='answer'); self.cli('start', 'T')
        self.cli('transition', 'T', 'blocked', '--reason', 'permission', '--hold-id', 'approval', '--next', 'Await approval')
        with self.assertRaises(ValueError): self.cli('resume', 'T')
        with self.assertRaises(ValueError): self.cli('requeue', 'T')
        with self.assertRaisesRegex(ValueError, 'requires --user-release'):
            self.cli('release-hold', 'T', '--hold-id', 'approval',
                     '--authority', 'user-message:approved', '--next', 'Continue')
        self.release( 'T', '--hold-id', 'approval', '--authority', 'user-message:approved', '--next', 'Continue approved work')
        self.cli('resume', 'T')
        self.assertEqual('user-message:approved', self.task()['hold_releases'][-1]['authority'])
        self.assertEqual('fixture-release-approval', self.task()['hold_releases'][-1]['message']['message_id'])

if __name__ == '__main__':
    unittest.main()
