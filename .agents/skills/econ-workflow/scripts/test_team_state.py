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

    def test_empty_scope_can_be_saved_but_start_preserves_queued_state(self):
        self.run_cli('add', 'unassigned', '--owner', 'worker', '--record', 'request.md', '--input', 'request.md', '--next', 'Await an output assignment')
        path = self.root / '.agents/state/team.json'
        before = path.read_bytes()
        self.run_cli('start', 'unassigned', fail=True)
        self.assertEqual(path.read_bytes(), before)
        task = self.run_cli('show')['tasks']['unassigned']
        self.assertEqual(task['status'], 'queued')
        self.assertEqual(task['attempts'], 0)
        self.assertEqual(task['scope'], [])

    def test_scoped_assignment_registers_output_beside_saved_empty_scope(self):
        self.run_cli('add', 'unassigned', '--owner', 'worker', '--record', 'request.md', '--next', 'Await an output assignment')
        self.add('owned')
        self.run_cli('start', 'owned')
        output = self.root / 'outputs/owned/result.md'
        output.parent.mkdir(parents=True)
        output.write_text('Saved descriptive quantity: 10.\n')
        self.run_cli('output', 'owned', 'outputs/owned/result.md')
        tasks = self.run_cli('show')['tasks']
        self.assertEqual(list(tasks['owned']['outputs']), ['outputs/owned/result.md'])
        self.assertEqual(tasks['unassigned']['status'], 'queued')
        self.assertEqual(tasks['unassigned']['attempts'], 0)

    def test_show_selected_task_preserves_full_view_and_store_bytes(self):
        self.add('a')
        self.add('b')
        path = self.root / '.agents/state/team.json'
        before = path.read_bytes()
        full = self.run_cli('show')
        self.assertEqual(self.run_cli('show', 'a'), full['tasks']['a'])
        self.assertEqual(self.run_cli('show'), full)
        self.assertEqual(path.read_bytes(), before)

    def test_show_unknown_task_refuses_without_writing(self):
        self.add('a')
        path = self.root / '.agents/state/team.json'
        before = path.read_bytes()
        self.run_cli('show', 'unknown-task', fail=True)
        self.assertEqual(path.read_bytes(), before)

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
        self.run_cli('usage', 'a', '--jsonl', str(events), '--epoch', 'rollout-1', '--sequence', '0', '--elapsed-seconds', '3.5')
        totals = self.run_cli('summary')['totals']
        self.assertEqual(totals['total_tokens'], 120)
        self.assertEqual(totals['elapsed_seconds'], 3.5)
        before = (self.root / '.agents/state/team.json').read_bytes()
        self.run_cli('usage', 'a', '--jsonl', str(events), '--epoch', 'rollout-1', '--sequence', '0', '--elapsed-seconds', '3.5')
        self.assertEqual((self.root / '.agents/state/team.json').read_bytes(), before)
        self.assertEqual(self.run_cli('summary')['totals']['total_tokens'], 120)

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

    def usage_file(self, name, session, counters):
        path = self.root / (name + '.jsonl')
        rows = [{'type': 'thread.started', 'thread_id': session}]
        for amount in counters:
            rows.append({'type': 'turn.completed', 'usage': {
                'input_tokens': amount, 'cached_input_tokens': amount // 2,
                'cache_write_input_tokens': 0, 'output_tokens': amount // 10,
                'reasoning_output_tokens': amount // 20}})
        path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
        return str(path)

    def test_cumulative_turns_and_resume_count_thread_once(self):
        self.add()
        original = self.usage_file('original', 's1', [100, 150])
        resumed = self.usage_file('resumed', 's1', [200])
        self.run_cli('usage', 'a', '--jsonl', original, '--epoch', 'e1', '--sequence', '0')
        self.run_cli('usage', 'a', '--jsonl', resumed, '--epoch', 'e1', '--sequence', '1')
        result = self.run_cli('summary')
        self.assertEqual(result['totals']['input_tokens'], 200)
        self.assertEqual(result['totals']['total_tokens'], 220)
        self.assertEqual([row['increment_since_previous_observation']['input_tokens'] for row in result['intervals']], [100, 50, 50])

    def test_reverse_import_uses_declared_order_not_import_order(self):
        self.add()
        earlier = self.usage_file('earlier', 's1', [100])
        later = self.usage_file('later', 's1', [180])
        self.run_cli('usage', 'a', '--jsonl', later, '--epoch', 'e1', '--sequence', '1')
        self.assertIsNone(self.run_cli('summary')['totals']['total_tokens'])
        self.run_cli('usage', 'a', '--jsonl', earlier, '--epoch', 'e1', '--sequence', '0')
        self.assertEqual(self.run_cli('summary')['totals']['total_tokens'], 198)

    def test_distinct_threads_add_without_cache_reasoning_double_count(self):
        self.add()
        for sid, amount in [('s1', 100), ('s2', 200)]:
            path = self.usage_file(sid, sid, [amount])
            self.run_cli('usage', 'a', '--jsonl', path, '--epoch', 'e1', '--sequence', '0')
        total = self.run_cli('summary')['totals']
        self.assertEqual(total['input_tokens'], 300)
        self.assertEqual(total['cached_input_tokens'], 150)
        self.assertEqual(total['reasoning_output_tokens'], 15)
        self.assertEqual(total['total_tokens'], 330)

    def test_counter_reset_in_one_epoch_is_unknown_not_new_zero(self):
        self.add()
        first = self.usage_file('first', 's1', [100])
        reset = self.usage_file('reset', 's1', [20])
        self.run_cli('usage', 'a', '--jsonl', first, '--epoch', 'e1', '--sequence', '0')
        self.run_cli('usage', 'a', '--jsonl', reset, '--epoch', 'e1', '--sequence', '1')
        result = self.run_cli('summary')
        self.assertIsNone(result['totals']['total_tokens'])
        self.assertIn('counter-decreased-within-declared-epoch', [x['kind'] for x in result['problems']])

    def test_explicit_new_epoch_makes_confirmed_reset_additive(self):
        self.add()
        for epoch, amount in [('e1', 100), ('e2', 20)]:
            path = self.usage_file(epoch, 's1', [amount])
            self.run_cli('usage', 'a', '--jsonl', path, '--epoch', epoch, '--sequence', '0')
        self.assertEqual(self.run_cli('summary')['totals']['total_tokens'], 132)

    def test_unknown_epoch_or_order_retains_raw_and_reports_null(self):
        self.add()
        raw = self.usage_file('raw', 's1', [100])
        self.run_cli('usage', 'a', '--jsonl', raw)
        state = self.run_cli('show')
        self.assertEqual(state['tasks']['a']['usage'][0]['observations'][0]['counter']['input_tokens'], 100)
        self.assertIsNone(self.run_cli('summary')['totals']['total_tokens'])

    def test_zero_or_default_counter_keeps_raw_zero_and_normalizes_unknown(self):
        self.add()
        raw = self.usage_file('zero', 's1', [0])
        self.run_cli('usage', 'a', '--jsonl', raw, '--epoch', 'e1', '--sequence', '0')
        state = self.run_cli('show')
        self.assertEqual(state['tasks']['a']['usage'][0]['observations'][0]['counter']['input_tokens'], 0)
        report = self.run_cli('summary')
        self.assertIsNone(report['totals']['total_tokens'])
        self.assertIsNone(report['intervals'][0]['increment_since_previous_observation']['input_tokens'])

    def test_later_nonzero_counter_recovers_total_but_not_unknown_interval(self):
        self.add()
        for sequence, amount in [(0, 0), (1, 100), (2, 120)]:
            raw = self.usage_file('value-' + str(sequence), 's1', [amount])
            self.run_cli('usage', 'a', '--jsonl', raw, '--epoch', 'e1', '--sequence', str(sequence))
        report = self.run_cli('summary')
        self.assertEqual(report['totals']['total_tokens'], 132)
        self.assertEqual([row['increment_since_previous_observation']['input_tokens'] for row in report['intervals']], [None, None, 20])
        self.assertEqual(report['totals']['cache_write_input_tokens'], 0)

if __name__ == '__main__':
    unittest.main()
