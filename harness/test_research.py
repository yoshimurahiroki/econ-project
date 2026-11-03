"""Exercise the research CLI using a small calculation and its consumers."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(__file__).with_name('research.py').resolve()


class ResearchPipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'data.txt').write_text('4')
        (self.root / 'spec.txt').write_text('3')
        (self.root / 'labels.txt').write_text('Result: {{stat:estimate}} units\n')
        (self.root / 'estimate.py').write_text("""import json, pathlib, sys
x = int(pathlib.Path(sys.argv[1]).read_text())
y = int(pathlib.Path(sys.argv[2]).read_text())
pathlib.Path(sys.argv[3]).write_text(json.dumps({'estimate': {'value': x * y, 'unit': 'units'}}))
""")
        self.spec = {'pipeline': 'demo', 'stages': [
            {'id': 'estimate', 'inputs': ['data.txt', 'spec.txt', 'estimate.py'], 'depends': {},
             'outputs': {'result': 'result.json'}, 'argv': [sys.executable, '{root}/estimate.py', '{root}/data.txt', '{root}/spec.txt', '{out:result}']},
            {'id': 'paper', 'inputs': ['labels.txt'], 'depends': {'estimate': ['result']}, 'outputs': {'text': 'paper.txt'},
             'render': {'template': 'labels.txt', 'output': 'text', 'statistics': {'estimate': {'stage': 'estimate', 'output': 'result', 'key': ['estimate'], 'unit': 'units', 'format': '.2f'}}}},
            {'id': 'independent', 'inputs': ['data.txt'], 'depends': {}, 'outputs': {'copy': 'copy.txt'},
             'argv': [sys.executable, '-c', 'import pathlib,sys; pathlib.Path(sys.argv[2]).write_text(pathlib.Path(sys.argv[1]).read_text())', '{root}/data.txt', '{out:copy}']},
        ]}
        self.write_spec()

    def tearDown(self):
        self.tmp.cleanup()

    def write_spec(self):
        (self.root / 'manifest.json').write_text(json.dumps(self.spec))

    def cli(self, code=0, profile=None):
        args = [sys.executable, str(RUNNER), '--root', str(self.root)]
        if profile is not None:
            args += ['--profile', profile]
        p = subprocess.run(args + ['manifest.json'], text=True, capture_output=True)
        self.assertEqual(p.returncode, code, p.stderr + p.stdout)
        return json.loads(p.stdout) if p.stdout else p.stderr


    def test_failed_replacement_preserves_previous_and_blocks_descendant(self):
        first = self.cli()
        prior = self.root / first['estimate']['outputs']['result']
        old = prior.read_bytes()
        (self.root / 'estimate.py').write_text('raise SystemExit(7)\n')
        failed = self.cli(1)
        self.assertEqual(failed['estimate']['status'], 'failed')
        self.assertEqual(failed['paper']['status'], 'blocked')
        self.assertEqual(failed['independent']['status'], 'reused')
        self.assertEqual(prior.read_bytes(), old)
        tasks = json.loads((self.root / '.agents/state/team.json').read_text())['tasks']
        self.assertEqual(tasks[failed['estimate']['task']]['status'], 'failed')
        self.assertEqual(tasks[failed['estimate']['task']]['outputs']['research:execution']['value']['returncode'], 7)


if __name__ == '__main__':
    unittest.main()
