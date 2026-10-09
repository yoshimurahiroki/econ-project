"""Disposable repositories verify task completion, resumption and resource evidence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('team_state.py')

class TaskStateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / 'request.md').write_text('Compare the saved quantity; no new estimation.\n')
        subprocess.run(['git', '-C', str(self.root), 'add', 'request.md'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], check=True)
        self.run_cli('init', '--max-active', '2', '--max-attempts', '2')

    def tearDown(self):
        self.directory.cleanup()

    def run_cli(self, *args, fail=False):
        result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2 if fail else 0, result.stderr)
        return result.stderr if fail else json.loads(result.stdout)

    def add(self, key='a', *extra):
        self.run_cli('add', key, '--owner', key, '--record', 'request.md', '--input', 'request.md', '--scope', 'outputs/' + key, '--next', 'Generate the saved comparison', *extra)

    def complete(self, key='a', reviewer='independent-session'):
        self.run_cli('start', key)
        output = self.root / 'outputs' / key / 'result.md'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('Saved quantity: 10; denominator: original sample.\n')
        self.run_cli('output', key, output.relative_to(self.root).as_posix())
        self.run_cli('transition', key, 'evaluating')
        (self.root / ('review-' + key + '.md')).write_text('Read result and source. Quantities and status agree.\n')
        self.run_cli('verify', key, '--evidence', 'review-' + key + '.md', '--result', 'passed', '--reviewer', reviewer)
        self.run_cli('transition', key, 'completed')

    def test_completion_requires_artifact_and_verification(self):
        self.add()
        self.run_cli('start', 'a')
        self.run_cli('transition', 'a', 'evaluating')
        self.run_cli('transition', 'a', 'completed', fail=True)

    def test_success_records_current_evidence(self):
        self.add('a', '--independent-review')
        self.complete()
        self.assertEqual(self.run_cli('show')['tasks']['a']['status'], 'completed')
        self.assertEqual(self.run_cli('inspect')['findings'], [])

    def test_self_review_cannot_satisfy_independent_assignment(self):
        self.add('a', '--independent-review')
        self.run_cli('start', 'a')
        self.run_cli('transition', 'a', 'evaluating')
        (self.root / 'review.md').write_text('Self check')
        self.run_cli('verify', 'a', '--evidence', 'review.md', '--result', 'passed', '--reviewer', 'a', fail=True)

    def test_changed_input_invalidates_only_its_dependencies(self):
        self.add()
        self.complete()
        (self.root / 'other.md').write_text('Other independent input')
        self.run_cli('add', 'other', '--owner', 'other', '--record', 'other.md', '--scope', 'outputs/other', '--next', 'Read')
        self.complete('other')
        self.add('child', '--after', 'a')
        self.complete('child')
        (self.root / 'request.md').write_text('Changed definition')
        view = self.run_cli('inspect', '--invalidate')
        self.assertEqual(view['affected_tasks'], ['a', 'child'])
        tasks = self.run_cli('show')['tasks']
        self.assertEqual(tasks['a']['status'], 'interrupted')
        self.assertEqual(tasks['child']['status'], 'interrupted')
        self.assertEqual(tasks['other']['status'], 'completed')
        self.run_cli('requeue', 'a')
        self.run_cli('start', 'a')
        self.assertEqual(self.run_cli('show')['tasks']['a']['attempts'], 2)

    def test_output_change_invalidates_completion(self):
        self.add()
        self.complete()
        (self.root / 'outputs/a/result.md').write_text('Changed result')
        self.assertEqual(self.run_cli('inspect')['affected_tasks'], ['a'])

    def test_missing_upstream_verification_refuses_child_start_without_inspect(self):
        self.add()
        self.complete()
        self.add('child', '--after', 'a')
        (self.root / 'review-a.md').unlink()
        self.run_cli('start', 'child', fail=True)

    def test_upstream_proof_change_refuses_inflight_child_completion(self):
        self.add()
        self.complete()
        self.add('child', '--after', 'a')
        self.run_cli('start', 'child')
        output = self.root / 'outputs/child/result.md'
        output.parent.mkdir(parents=True)
        output.write_text('Child result')
        self.run_cli('output', 'child', 'outputs/child/result.md')
        self.run_cli('transition', 'child', 'evaluating')
        (self.root / 'review-child.md').write_text('Reviewed child')
        self.run_cli('verify', 'child', '--evidence', 'review-child.md', '--result', 'passed', '--reviewer', 'separate')
        (self.root / 'review-a.md').write_text('Changed proof')
        self.run_cli('transition', 'child', 'completed', fail=True)

    def test_scope_overlap_and_outside_output_refused(self):
        self.add()
        self.run_cli('add', 'b', '--owner', 'b', '--record', 'request.md', '--scope', 'outputs/a/nested', '--next', 'Read')
        self.run_cli('start', 'a')
        self.run_cli('start', 'b', fail=True)
        self.run_cli('output', 'a', 'request.md', fail=True)

    def test_missing_dependency_and_attempt_limit(self):
        self.add()
        self.add('b', '--after', 'a')
        self.run_cli('start', 'b', fail=True)
        for unused in range(2):
            self.run_cli('start', 'a')
            self.run_cli('transition', 'a', 'interrupted', '--next', 'Check source')
            self.run_cli('requeue', 'a')
        self.run_cli('start', 'a', fail=True)

    def test_traversal_symlink_and_nonlocal_store_refused(self):
        self.run_cli('add', 'escape', '--owner', 'x', '--record', '../request.md', '--next', 'Read', fail=True)
        self.run_cli('--store', 'public.json', 'show', fail=True)
        try:
            (self.root / 'linked.md').symlink_to(self.root / 'request.md')
        except OSError:
            return
        self.run_cli('add', 'linked', '--owner', 'x', '--record', 'linked.md', '--next', 'Read', fail=True)

    def test_usage_deduplicates_and_preserves_inclusion(self):
        self.add()
        events = self.root / 'usage.jsonl'
        events.write_text(json.dumps({'type': 'thread.started', 'thread_id': 'fixture-thread'}) + '\n' + json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 100, 'cached_input_tokens': 80, 'output_tokens': 20, 'reasoning_output_tokens': 10}}) + '\n')
        self.run_cli('usage', 'a', '--jsonl', str(events), '--elapsed-seconds', '3.5')
        totals = self.run_cli('summary')['totals']
        self.assertEqual(totals['total_tokens'], 120)
        self.assertEqual(totals['elapsed_seconds'], 3.5)
        self.run_cli('usage', 'a', '--jsonl', str(events), fail=True)

    def test_unknown_usage_is_not_zero(self):
        self.add()
        events = self.root / 'usage.jsonl'
        events.write_text(json.dumps({'type': 'turn.failed'}) + '\n')
        self.run_cli('usage', 'a', '--jsonl', str(events))
        self.assertIsNone(self.run_cli('summary')['totals']['total_tokens'])

    def test_append_only_record_does_not_invalidate_scientific_outputs(self):
        (self.root / 'ledger.md').write_text('Task a requested comparison\n')
        (self.root / 'data-definition.md').write_text('Fixed population and denominator\n')
        self.run_cli('add', 'a', '--owner', 'a', '--record', 'ledger.md', '--input', 'data-definition.md', '--scope', 'outputs/a', '--next', 'Compare')
        self.complete()
        self.run_cli('add', 'child', '--owner', 'child', '--record', 'ledger.md', '--after', 'a', '--scope', 'outputs/child', '--next', 'Communicate')
        self.complete('child')
        saved = self.run_cli('show')['tasks']['a']['record_version']['sha256']
        with (self.root / 'ledger.md').open('a') as stream:
            stream.write('Task b progress and quantities checked\n')
        self.assertEqual(self.run_cli('inspect')['affected_tasks'], [])
        self.assertEqual(self.run_cli('show')['tasks']['a']['record_version']['sha256'], saved)
        self.assertEqual(self.run_cli('show')['tasks']['child']['status'], 'completed')
        (self.root / 'data-definition.md').write_text('Changed scientific denominator\n')
        self.assertEqual(self.run_cli('inspect', '--invalidate')['affected_tasks'], ['a', 'child'])

    def test_record_explicitly_named_as_input_remains_dependency(self):
        self.add()
        self.complete()
        self.add('child', '--after', 'a')
        self.complete('child')
        with (self.root / 'request.md').open('a') as stream:
            stream.write('Changed adopted definition\n')
        self.assertEqual(self.run_cli('inspect', '--invalidate')['affected_tasks'], ['a', 'child'])

    def test_legacy_dependencies_need_explicit_requeue_without_silent_migration(self):
        self.add()
        self.run_cli('start', 'a')
        self.run_cli('transition', 'a', 'interrupted', '--next', 'Adopt explicit input list')
        path = self.root / '.agents/state/team.json'
        state = json.loads(path.read_text())
        task = state['tasks']['a']
        task.pop('input_contract')
        task.pop('input_paths')
        task.pop('record_version')
        path.write_text(json.dumps(state))
        before = path.read_bytes()
        self.run_cli('inspect')
        self.assertEqual(path.read_bytes(), before)
        self.run_cli('requeue', 'a', fail=True)
        self.assertEqual(path.read_bytes(), before)
        self.run_cli('requeue', 'a', '--input', 'request.md')
        self.assertEqual(self.run_cli('show')['tasks']['a']['input_paths'], ['request.md'])
        (self.root / 'request.md').write_text('Changed explicit record input\n')
        self.assertEqual(self.run_cli('inspect')['affected_tasks'], ['a'])

if __name__ == '__main__':
    unittest.main()
