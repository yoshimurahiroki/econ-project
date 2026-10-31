"""Bounded, offline state-contract regressions using disposable local fixtures."""
import contextlib
import importlib.util
import io
import json
import os
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
        for name in ['record', 'input', 'check', 'artifact', 'extra']:
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

    def consume(self, producer, output, kind='file', **kwargs):
        row = {'producer_id': producer, 'output_id': output, 'kind': kind, 'content_version': 'pending', 'definition_versions': {}, **kwargs}
        current = h.dependency_value(self.state()['tasks'], row)
        row['content_version'] = current['content_version']
        row['definition_versions'] = current['definition_versions']
        return json.dumps(row)

    def prepared(self, *args, name='T'):
        args = list(args)
        checks = ['--required-check', json.dumps({'id': 'check', 'targets': ['artifact']})]
        if 'other' in args:
            at = args.index('other')
            args[at] = json.dumps({'id': 'other', 'targets': ['extra']})
            args += ['--required-output', json.dumps({'role': 'final', 'kind': 'file', 'target': 'artifact'}),
                     '--required-output', json.dumps({'role': 'extra', 'kind': 'file', 'target': 'extra'})]
        self.add('--scope', 'artifact', '--scope', 'extra', '--input', 'input', *checks, *args, name=name)
        self.cli('start', name)
        self.cli('output', name, 'artifact')

    def verify(self, *args, name='T', check='check'):
        self.cli('verify', name, '--check', check, '--result', 'passed', '--reviewer', 'reviewer', *args)

    def completed(self, name='T'):
        self.cli('transition', name, 'completed')

    def action_evidence(self, target='obj:1', operation='publish', tool='publish',
                        arguments=None, returned=None):
        """Synthetic native tool record for offline state-boundary fixtures."""
        call_text = json.dumps(arguments if arguments is not None else {'target': target})
        return_text = json.dumps(returned if returned is not None else {'status': 'success', 'target': target})
        record = {
            'event_id': 'fixture-action', 'operation': operation, 'target': target, 'status': 'success',
            'tool_name': tool, 'tool_call_ref': 'fixture-call', 'tool_return_ref': 'fixture-return',
            'call_args_text': call_text, 'call_args_sha256': h.gate.sha(call_text.encode()),
            'return_text': return_text, 'return_sha256': h.gate.sha(return_text.encode()),
            'source_verification': {'status': 'matched-to-runtime', 'reference': 'offline-fixture',
                                    'verifier_id': 'fixture-owner'},
        }
        (self.root / 'check').write_text(json.dumps(record))

    def rejects_completion(self, name='T'):
        with self.assertRaises(ValueError):
            self.completed(name)

    def test_answer_without_scope_record_or_check_file(self):
        self.add(kind='answer')
        self.cli('start', 'T')
        self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'The answer')
        self.completed()
        self.assertTrue(h.completion_current(self.root, self.state()['tasks'], 'T'))
        self.assertEqual([], self.task()['required_checks'])

    def task_context(self, name='context.json', *, delegated=False):
        (self.root / 'request.txt').write_text('Deliver the policy decision and preserve the adopted outcome units.')
        (self.root / 'rules.md').write_text('Retain the full request and use the saved analysis.')
        value = {'request_refs': [{'source_id': 'user-request', 'version': 1,
                                  'content_sha256': h.digest(self.root / 'request.txt'), 'path': 'request.txt'}],
                 'goal_and_constraints': 'Choose the profitable policy; retain all regions and monetary units.',
                 'active_instruction_refs': [{'rule_id': 'core', 'version': 1, 'section': 'all',
                                              'content_sha256': h.digest(self.root / 'rules.md'), 'path': 'rules.md'}],
                 'adopted_decisions': [{'decision_id': 'method', 'version': 1, 'choice': 'level contrast',
                                       'reason': 'Requested units', 'switch_condition': 'New evidence changes the comparison',
                                       'change_authority': 'delegated' if delegated else 'fixed'}]}
        (self.root / name).write_text(json.dumps(value))
        return value

    def test_compacted_context_cannot_drop_binding_requirements(self):
        original = self.task_context()
        self.add('--task-context', 'context.json', '--scope', 'artifact', kind='answer', name='P')
        self.add('--parent', 'P', '--scope', 'artifact', name='C')
        self.cli('start', 'C'); self.cli('output', 'C', 'artifact'); self.completed('C')
        self.cli('start', 'P')
        self.cli('transition', 'P', 'blocked', '--next', 'Read saved context and integrate child result')
        artifact_version = self.task('C')['outputs']['artifact']['version']
        for field, replacement in [('request_refs', []), ('active_instruction_refs', []),
                                   ('adopted_decisions', []), ('goal_and_constraints', 'Report a result')]:
            with self.subTest(field=field):
                compacted = {**original, field: replacement}
                (self.root / 'compacted.json').write_text(json.dumps(compacted))
                with self.assertRaisesRegex(ValueError, 'binding context'):
                    self.cli('set-context', 'P', '--task-context', 'compacted.json')
                self.assertEqual(original, self.task('P')['task_context'])
                self.assertEqual(original, self.task('C')['task_context'])
        self.assertEqual(artifact_version, self.task('C')['outputs']['artifact']['version'])
        self.assertTrue(h.completion_current(self.root, self.state()['tasks'], 'C'))
        self.cli('resume', 'P', '--task-context', 'context.json')
        self.cli('output', 'P', 'message:1', '--kind', 'message', '--value', 'Decision from the completed child result')
        self.completed('P')

    def test_context_changes_bind_authority_and_delegated_decision_evidence(self):
        previous = self.task_context(delegated=True)
        self.add('--task-context', 'context.json', kind='answer')
        replacement = json.loads(json.dumps(previous)); replacement['adopted_decisions'][0].update(version=2, choice='alternative level contrast')
        (self.root / 'replacement.json').write_text(json.dumps(replacement))
        (self.root / 'analysis.json').write_text('{"net_benefit":55}')
        with self.assertRaisesRegex(ValueError, 'decision-update'):
            self.cli('set-context', 'T', '--task-context', 'replacement.json')
        self.cli('set-context', 'T', '--task-context', 'replacement.json', '--decision-update',
                 json.dumps({'decision_id': 'method', 'reason': 'The saved comparison crosses the adopted decision boundary', 'evidence': ['analysis.json']}))
        self.assertEqual('delegated-decision', self.task()['context_revisions'][-1]['source']['kind'])
        # A delegated choice cannot rewrite the criterion or the user's instruction.
        changed = json.loads(json.dumps(replacement)); changed['goal_and_constraints'] = 'New user objective with the same monetary units.'
        (self.root / 'changed.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, 'binding context'):
            self.cli('set-context', 'T', '--task-context', 'changed.json')
        (self.root / 'user-change.json').write_text(json.dumps({'source': 'user', 'message_id': 'fixture-user-change',
            'text': 'Adopt the new objective while preserving monetary units.',
            'previous_context_sha256': h.content_hash(replacement), 'replacement_context_sha256': h.content_hash(changed)}))
        self.cli('set-context', 'T', '--task-context', 'changed.json', '--user-change', 'user-change.json')
        self.cli('start', 'T'); self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'Completed decision'); self.completed()
        (self.root / 'analysis.json').write_text('{"net_benefit":-55}')
        self.assertFalse(h.completion_current(self.root, self.state()['tasks'], 'T'))

    def test_context_rebinding_and_additions_preserve_previous_instructions(self):
        previous = self.task_context()
        self.add('--task-context', 'context.json', kind='answer')
        self.cli('start', 'T'); self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'Saved result')
        self.cli('transition', 'T', 'blocked', '--next', 'Resume the same result')
        before = self.task()['outputs']
        (self.root / 'same.json').write_text(json.dumps(previous, indent=2))
        self.cli('set-context', 'T', '--task-context', 'same.json')
        self.assertEqual(before, self.task()['outputs'])
        self.assertEqual(1, len(self.task()['context_revisions']))
        extra = json.loads(json.dumps(previous)); extra['adopted_decisions'].append(
            {'decision_id': 'report', 'version': 1, 'choice': 'Report the total', 'reason': 'Decision scope', 'switch_condition': 'User changes the target'})
        (self.root / 'extra-context.json').write_text(json.dumps(extra))
        self.cli('set-context', 'T', '--task-context', 'extra-context.json')
        self.assertEqual(previous, self.task()['context_revisions'][0]['context'])
        self.cli('resume', 'T', '--task-context', 'extra-context.json'); self.completed()
        saved = self.state(); saved['tasks']['T']['context_revisions'][0]['context']['goal_and_constraints'] = 'A forged shorter instruction'
        (self.root / '.agents/state/team.json').write_text(json.dumps(saved))
        self.assertFalse(h.completion_current(self.root, saved['tasks'], 'T'))

    def test_same_path_modify_preserves_before_and_after(self):
        self.add('--scope', 'input', '--input', 'input', '--required-check', 'check', kind='modify')
        before = self.task()['consumed_inputs']['input']
        self.cli('start', 'T')
        (self.root / 'input').write_text('after')
        self.cli('output', 'T', 'input')
        self.verify()
        self.completed()
        self.assertEqual(before, self.task()['consumed_inputs']['input'])
        self.assertNotEqual(before, self.task()['outputs']['input']['version'])

    def test_external_input_change_rejects_pass_and_completion(self):
        self.prepared()
        self.verify()
        (self.root / 'input').write_text('changed')
        self.rejects_completion()
        with self.assertRaises(ValueError):
            self.verify()
        self.assertEqual(['T'], self.cli('inspect')['affected_tasks'])

    def test_replacement_requires_current_check(self):
        self.prepared()
        self.verify()
        (self.root / 'artifact').write_text('replacement')
        self.cli('output', 'T', 'artifact')
        self.assertEqual({}, self.task()['check_receipts'])
        self.rejects_completion()
        self.verify()
        self.completed()

    def test_only_affected_output_receipts_invalidated(self):
        self.prepared('--required-check', 'other')
        self.cli('output', 'T', 'extra')
        self.verify('--output', 'artifact')
        self.verify('--output', 'extra', check='other')
        (self.root / 'artifact').write_text('new')
        self.cli('output', 'T', 'artifact')
        self.assertEqual(['other'], list(self.task()['check_receipts']))
        self.verify('--output', 'artifact')
        self.completed()

    def test_legacy_completed_preserves_output_and_only_rechecks(self):
        self.prepared()
        state = self.state()
        t = state['tasks']['T']
        t['outputs'] = {k: v['version'] for k,v in t['outputs'].items()}
        t['status'] = 'completed'
        t['verification'] = {'result': 'passed', 'evidence': h.snapshot(self.root, ['check'])}
        state['version'] = 1
        t.pop('contract_revisions', None)
        t.pop('check_targets', None)
        state['limits']['max_attempts'] = 3
        (self.root / '.agents/state/team.json').write_text(json.dumps(state))
        old_version = h.digest(self.root / 'artifact')
        self.cli('set-contract', 'T', '--required-output', json.dumps({'role':'final','kind':'file','target':'artifact'}))
        self.cli('resume', 'T')
        self.assertEqual(1, self.task()['attempts'])
        self.rejects_completion()
        self.verify(check='legacy-verification')
        self.completed()
        self.assertEqual(old_version, self.task()['outputs']['artifact']['version'])

    def test_check_log_format_change_only_needs_recheck(self):
        self.prepared()
        self.verify('--evidence', 'check')
        self.completed()
        (self.root / 'check').write_text('same check in a new display format')
        self.cli('inspect', '--invalidate')
        self.cli('resume', 'T')
        self.assertEqual(1, self.task()['attempts'])
        self.verify('--evidence', 'check')
        self.completed()

    def test_no_default_retry_limit(self):
        self.add(kind='answer')
        for i in range(5):
            self.cli('start', 'T')
            self.cli('transition', 'T', 'failed', '--next', 'Retry requested operation')
            self.cli('requeue', 'T')
        self.assertEqual(5, self.task()['attempts'])

    def test_unchanged_registration_preserves_receipt(self):
        self.prepared(); self.verify()
        receipt = self.task()['check_receipts']
        self.cli('output', 'T', 'artifact')
        self.assertEqual(receipt, self.task()['check_receipts'])
        self.completed()

    def test_output_addition_invalidates_whole_result_check(self):
        self.prepared(); self.verify()
        self.cli('output', 'T', 'extra')
        self.rejects_completion()

    def test_in_place_does_not_exempt_explicit_read_dependency(self):
        self.add('--scope', 'input', '--input', 'input', '--read-dependency', 'input', kind='modify')
        self.cli('start', 'T')
        (self.root / 'input').write_text('change')
        self.cli('output', 'T', 'input')
        self.rejects_completion()

    def test_unregistered_modified_input_rejected(self):
        self.add('--scope', 'input', '--input', 'input', kind='modify')
        self.cli('start', 'T')
        (self.root / 'input').write_text('change')
        self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'done')
        self.rejects_completion()

    def test_object_output_hash_is_canonical(self):
        self.add('--required-output', json.dumps({'role':'final','kind':'object','target':'object:1'}), kind='answer'); self.cli('start', 'T')
        self.cli('output', 'T', 'object:1', '--kind', 'object', '--value', '{"b":2,"a":1}')
        version = self.task()['outputs']['object:1']['version']
        self.cli('output', 'T', 'object:1', '--kind', 'object', '--value', '{"a":1,"b":2}')
        self.assertEqual(version, self.task()['outputs']['object:1']['version'])
        self.completed()

    def test_write_scope_and_lock_guards(self):
        self.prepared()
        with self.assertRaises(ValueError): self.cli('output', 'T', 'input')
        lock = self.root / '.agents/state/team.lock'
        with h.locked(self.root / '.agents/state/team.json'):
            with self.assertRaises(ValueError): self.verify()
        self.assertTrue(lock.exists())

    def test_overlap_rejected(self):
        self.prepared()
        self.add('--scope', 'artifact', name='P')
        with self.assertRaises(ValueError): self.cli('start', 'P')

    def test_independent_review(self):
        self.prepared('--independent-review')
        with self.assertRaises(ValueError):
            self.cli('verify', 'T', '--check', 'check', '--result', 'passed', '--reviewer', 'writer')

    def test_requeue_explicit_no_inputs_releases_old_inputs(self):
        self.prepared()
        self.cli('transition', 'T', 'failed', '--next', 'Revise assignment')
        self.cli('requeue', 'T', '--no-inputs')
        (self.root / 'input').unlink()
        self.cli('start', 'T')
        self.assertEqual({}, self.task()['consumed_inputs'])

    def test_upstream_replacement_invalidates_dependents(self):
        self.prepared(name='P'); self.verify(name='P'); self.completed('P')
        self.add('--after', 'P', '--consumes', self.consume('P', 'artifact'), name='T', kind='answer')
        self.cli('start', 'T'); self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'done'); self.completed()
        (self.root / 'artifact').write_text('new upstream')
        self.assertFalse(h.completion_current(self.root, self.state()['tasks'], 'T'))
        self.assertEqual(['P', 'T'], self.cli('inspect', '--invalidate')['affected_tasks'])

    def test_record_provenance_not_computation_input(self):
        self.prepared('--record', 'record'); self.verify()
        (self.root / 'record').write_text('changed display')
        self.rejects_completion()
        (self.root / 'record').write_text('record')
        self.completed()

    def test_non_git_explicit_root_and_cwd_default(self):
        self.assertIsNone(h.revision(self.root))
        with patch('sys.argv', ['team_state', 'show']), patch.object(Path, 'cwd', return_value=self.root), contextlib.redirect_stdout(io.StringIO()) as out:
            h.main()
        self.assertEqual(5, json.loads(out.getvalue())['version'])

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

    def test_recomputed_upstream_current_bytes_still_invalidate_old_consumer(self):
        self.prepared(name='P'); self.verify(name='P'); self.completed('P')
        self.add('--after', 'P', '--consumes', self.consume('P', 'artifact'), kind='answer')
        self.cli('start', 'T'); self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'done'); self.completed()
        (self.root / 'artifact').write_text('changed upstream')
        self.cli('inspect', '--invalidate')
        self.cli('requeue', 'P'); self.cli('start', 'P'); self.cli('output', 'P', 'artifact'); self.verify(name='P'); self.completed('P')
        self.assertTrue(h.completion_current(self.root, self.state()['tasks'], 'P'))
        with self.assertRaises(ValueError): self.cli('resume', 'T')
        self.assertIn('T', self.cli('inspect')['affected_tasks'])

    def test_limit_provenance_preserves_legacy_configuration(self):
        self.assertEqual({'max_active': None, 'max_depth': None, 'max_attempts': None}, self.state()['limits'])
        self.add(kind='answer')
        state = self.state(); state['version'] = 1
        state['limits'] = {'max_active': 7, 'max_depth': 4, 'max_attempts': 9}
        (self.root / '.agents/state/team.json').write_text(json.dumps(state))
        self.cli('start', 'T')
        self.assertEqual(9, self.state()['limits']['max_attempts'])
        self.assertEqual('legacy_unspecified', self.state()['limit_sources']['max_attempts'])

    def test_explicit_attempt_budget_rejects_only_that_start(self):
        state = self.state(); state['limits']['max_attempts'] = 1
        (self.root / '.agents/state/team.json').write_text(json.dumps(state))
        self.add(kind='answer'); self.cli('start', 'T')
        self.cli('transition', 'T', 'failed', '--next', 'Retry after budget review')
        self.cli('requeue', 'T')
        with self.assertRaises(ValueError): self.cli('start', 'T')
        self.add(kind='answer', name='P'); self.cli('start', 'P')
        self.assertEqual('running', self.task('P')['status'])

    def test_failed_required_check_rejects_completion(self):
        self.prepared()
        self.cli('verify', 'T', '--check', 'check', '--result', 'failed', '--reviewer', 'reviewer')
        self.rejects_completion()

    def test_unregistered_output_mutation_rejects_completion(self):
        self.prepared(); self.verify()
        (self.root / 'artifact').write_text('unregistered replacement')
        self.rejects_completion()
        self.assertEqual(['check'], h.missing_checks(self.root, self.task()))

    def test_legacy_interrupted_and_evaluating_mapping(self):
        for old, new in [('interrupted', 'blocked'), ('evaluating', 'running')]:
            state = self.state()
            task = {'owner':'writer','record':'record','parent':None,'scope':[], 'inputs':{}, 'outputs':{},
                    'status':old,'next':'Continue','verification':None,'after':[], 'usage':[], 'attempts':1,
                    'human_corrections':0, 'updated':h.now(), 'history':[]}
            state['version'] = 1; state['tasks'] = {'T': task}
            h.migrate(state)
            self.assertEqual(new, state['tasks']['T']['status'])
            if old == 'interrupted': self.assertEqual('interrupted', state['tasks']['T']['blocked_reason'])

    def test_usage_cumulative_epochs_and_dedup_preserved(self):
        self.add(kind='answer')
        path = self.root / 'events.jsonl'
        for sequence, tokens in [(0, 10), (1, 30)]:
            rows = [{'type':'thread.started','thread_id':'S'}, {'type':'turn.completed','usage':{'input_tokens':tokens,'cached_input_tokens':0,'output_tokens':tokens//2}}]
            path.write_text('\n'.join(map(json.dumps, rows)))
            args = ('usage', 'T', '--jsonl', str(path), '--epoch', 'E', '--sequence', str(sequence))
            self.cli(*args); self.cli(*args)
        summary = self.cli('summary')
        self.assertEqual(2, summary['runs'])
        self.assertEqual(30, summary['totals']['input_tokens'])
        self.assertEqual(15, summary['totals']['output_tokens'])
        self.assertEqual(20, summary['intervals'][1]['increment_since_previous_observation']['input_tokens'])


    def test_progress_cannot_replace_required_file(self):
        self.add('--scope', 'artifact')
        self.cli('start', 'T')
        self.cli('output', 'T', 'progress', '--kind', 'message', '--value', 'Saved plan')
        self.rejects_completion()
        with self.assertRaises(ValueError):
            self.cli('output', 'T', 'artifact', '--kind', 'message', '--role', 'final', '--value', 'done')
        self.cli('output', 'T', 'artifact', '--role', 'final')
        self.completed()

    def test_all_requested_outputs_must_match_target_and_kind(self):
        self.add('--scope', 'artifact', '--scope', 'extra', '--required-output', json.dumps({'role':'file','kind':'file','target':'artifact'}),
                 '--required-output', json.dumps({'role':'reply','kind':'message','target':'final-response'}))
        self.cli('start', 'T'); self.cli('output', 'T', 'extra')
        self.cli('output', 'T', 'artifact'); self.rejects_completion()
        self.cli('output', 'T', 'final-response', '--kind', 'message', '--value', '')
        self.rejects_completion()
        self.cli('output', 'T', 'final-response', '--kind', 'message', '--value', 'Requested final response')
        self.completed()

    def test_release_only_named_hold_preserves_others(self):
        self.add('--hold', 'one', '--hold', 'two', kind='answer')
        self.cli('transition', 'T', 'blocked', '--next', 'Await authorization')
        with self.assertRaises(ValueError):
            self.release( 'T', '--hold-id', 'unknown', '--authority', 'user:yes', '--next', 'Continue')
        self.release( 'T', '--hold-id', 'one', '--authority', 'user:yes', '--next', 'Await two')
        self.assertEqual(['two'], self.task()['holds'])
        with self.assertRaises(ValueError): self.cli('resume', 'T')
        self.release( 'T', '--hold-id', 'two', '--authority', 'user:yes2', '--next', 'Continue')
        self.cli('resume', 'T')
        self.assertEqual(['one','two'], [r['hold_id'] for r in self.task()['hold_releases']])

    def test_external_action_requires_exact_object_id_and_current_receipt(self):
        target = 'https://service.invalid/objects/../opaque-id'
        requirement = {'target_kind':'object','target_id':target,'operation':'publish'}
        self.add('--external-target', target, '--required-action', json.dumps(requirement), kind='external')
        self.cli('start', 'T'); self.rejects_completion()
        args = ('action', 'T', '--target-kind', 'object', '--target-version', 'remote-v1', '--operation', 'publish', '--result', 'passed', '--evidence', 'check')
        with self.assertRaises(ValueError): self.cli(*args, '--target-id', 'opaque-id')
        self.action_evidence(target)
        self.cli(*args, '--target-id', target)
        self.completed()
        self.assertTrue(h.completion_current(self.root, self.state()['tasks'], 'T'))
        (self.root / 'check').write_text('changed receipt')
        self.assertFalse(h.completion_current(self.root, self.state()['tasks'], 'T'))
        self.assertEqual(['T'], self.cli('inspect')['affected_tasks'])

    def test_action_and_output_both_required(self):
        self.add('--scope','artifact', '--external-target','obj:1',
                 '--required-output', json.dumps({'role':'final','kind':'file','target':'artifact'}),
                 '--required-action', json.dumps({'target_kind':'object','target_id':'obj:1','operation':'publish'}))
        self.cli('start','T'); self.cli('output','T','artifact'); self.rejects_completion()
        args = ('action','T','--target-kind','object','--target-version','remote-v1','--target-id','obj:1','--operation','publish','--evidence','check')
        self.cli(*args,'--result','failed'); self.rejects_completion()
        self.action_evidence()
        self.cli(*args,'--result','passed'); self.completed()

    def test_external_completion_uses_returned_outcome(self):
        target = 'python analysis.py'
        operation = 'execute_command'
        self.add('--external-target', target, '--required-action', json.dumps({
            'target_kind': 'object', 'target_id': target, 'operation': operation}), kind='external')
        self.cli('start', 'T')
        action = ('action', 'T', '--target-kind', 'object', '--target-id', target,
                  '--target-version', 'run-1', '--operation', operation,
                  '--result', 'passed', '--evidence', 'check')
        with self.assertRaises(ValueError):
            self.cli(*action)  # An arbitrary existing log and caller verdict.
        for returned in ({'exit_code': 1, 'output': 'calculation failed'},
                         {'exit_code': None, 'session_id': 41, 'output': ''},
                         {'exit_code': 0, 'isError': True},
                         {'exit_code': 0, 'target': 'different calculation'}):
            with self.subTest(returned=returned):
                self.action_evidence(target, operation, 'exec_command', {'cmd': target}, returned)
                with self.assertRaises(ValueError):
                    self.cli(*action)
                self.assertEqual([], self.task()['action_results'])
                self.rejects_completion()
        self.action_evidence(target, operation, 'exec_command', {'cmd': target}, {'exit_code': 0, 'output': '42'})
        self.cli(*action)
        self.completed()
        self.assertEqual('success', self.task()['action_results'][0]['operation_outcome']['status'])

    def test_distribution_actions_bind_returned_version(self):
        cases = [
            ('repo/fixture:refs/heads/main', 'github.update_ref', 'mcp__codex_apps__github_update_ref',
             {'repository_full_name': 'repo/fixture', 'branch_name': 'main', 'sha': 'b' * 40,
              'expected_sha': 'a' * 40}, {'success': True}, 'b' * 40, 'commit_sha'),
            ('plugins_fixture', 'plugin_creator.update_plugin', 'mcp__codex_apps__plugin_creator_update_plugin',
             {'plugin_id': 'plugins_fixture', 'archive': '/tmp/fixture.zip', 'expected_release_id': 'old'},
             {'status': 'updated', 'plugin_id': 'plugins_fixture', 'release_id': 'new',
              'latest_release_id': 'new', 'plugin_url': 'https://service.invalid/plugin', 'version': '1.1.0'},
             'new', 'release_id'),
        ]
        for number, (target, operation, tool, arguments, returned, version, field) in enumerate(cases):
            with self.subTest(operation=operation):
                name = f'D{number}'
                self.add('--external-target', target, '--required-action', json.dumps({
                    'target_kind': 'object', 'target_id': target, 'operation': operation}), kind='external', name=name)
                self.cli('start', name)
                self.action_evidence(target, operation, tool, arguments, returned)
                action = ('action', name, '--target-kind', 'object', '--target-id', target,
                          '--operation', operation, '--result', 'passed', '--evidence', 'check')
                with self.assertRaisesRegex(ValueError, 'version differs'):
                    self.cli(*action, '--target-version', 'invented-version')
                self.cli(*action, '--target-version', version)
                self.completed(name)
                self.assertEqual(version, self.task(name)['action_results'][0]['operation_outcome'][field])

    def test_v2_migration_preserves_results_limits_holds_requires_contract(self):
        self.prepared(); self.verify(); self.completed()
        state = self.state(); task = state['tasks']['T']
        task['holds'] = ['hold-a', 'hold-b']; state['version'] = 2
        task.pop('contract_revisions', None)
        task.pop('check_targets', None)
        for key in ['completion_contract','required_outputs','required_actions','action_results','external_targets']:
            task.pop(key)
        before = json.loads(json.dumps(task))
        (self.root / '.agents/state/team.json').write_text(json.dumps(state))
        shown = self.cli('show','T')
        self.assertEqual(before['outputs'], shown['outputs'])
        # Reconstructed legacy contracts have a different context binding.
        # Preserve the outputs and obtain fresh checks after fixing that contract.
        self.assertEqual({}, shown['check_receipts'])
        self.assertEqual(before['holds'], shown['holds'])
        self.assertEqual('blocked', shown['status'])
        self.assertIsNone(shown['completion_contract'])
        self.assertEqual(['explicit-completion-contract-required'], h.missing_deliverables(self.root, shown))
        self.cli('set-contract','T','--required-output',json.dumps({'role':'final','kind':'file','target':'artifact'}))
        self.assertEqual(state['limits'], self.state()['limits'])
        self.assertEqual(state['limit_sources'], self.state()['limit_sources'])
        for hold in ['hold-a','hold-b']:
            self.release('T','--hold-id',hold,'--authority','user:approved','--next','Continue')
        self.cli('resume','T'); self.verify(); self.completed()
        self.assertTrue(h.completion_current(self.root, self.state()['tasks'], 'T'))

    def test_add_requires_explicit_deliverable_contract(self):
        with self.assertRaises(ValueError):
            self.cli('add','T','--owner','writer','--next','Work','--scope','artifact')


    def test_action_only_upstream_replacement_invalidates_consumer(self):
        self.add('--external-target','obj:1', '--required-check','check',
                 '--required-action', json.dumps({'target_kind':'object','target_id':'obj:1','operation':'publish'}), kind='external', name='P')
        action = ('action','P','--target-kind','object','--target-version','remote-v1','--target-id','obj:1','--operation','publish','--evidence','check','--result','passed')
        self.action_evidence()
        self.cli('start','P'); self.cli(*action); self.verify(name='P'); self.completed('P')
        self.add('--after','P','--consumes',self.consume('P','obj:1', 'object'),kind='answer'); self.cli('start','T')
        self.cli('output','T','message:1','--kind','message','--value','Final answer'); self.completed()
        self.action_evidence(returned={'status': 'success', 'target': 'obj:1', 'message': 'new external receipt'})
        self.cli('inspect','--invalidate'); self.cli('requeue','P'); self.cli('start','P')
        self.cli(*action); self.verify(name='P'); self.completed('P')
        with self.assertRaises(ValueError): self.cli('resume','T')
        self.assertIn('T',self.cli('inspect')['affected_tasks'])

    def test_migrated_permission_reason_gets_addressable_hold(self):
        self.add(kind='answer')
        state = self.state(); state['version'] = 2
        state['tasks']['T'].update(status='blocked', blocked_reason='permission', holds=[])
        (self.root / '.agents/state/team.json').write_text(json.dumps(state))
        self.assertEqual(['legacy:permission'],self.cli('show','T')['holds'])
        with self.assertRaises(ValueError): self.cli('resume','T')
        self.release('T','--hold-id','legacy:permission','--authority','user:yes','--next','Continue')
        self.cli('resume','T'); self.rejects_completion()

    def test_external_file_scope_does_not_authorize_object_target(self):
        self.add('--scope','artifact', '--required-action', json.dumps({'target_kind':'object','target_id':'artifact','operation':'update'}), kind='external')
        with self.assertRaises(ValueError): self.cli('start','T')


    def test_action_only_file_receipt_tracks_actual_target_bytes(self):
        self.add('--scope','artifact','--required-action',json.dumps({'target_kind':'file','target_id':'artifact','operation':'render'}))
        self.cli('start','T')
        self.cli('action','T','--target-kind','file','--target-id','artifact','--operation','render','--result','passed','--evidence','check')
        self.assertEqual({},self.task()['outputs'])
        self.completed()
        (self.root / 'artifact').write_text('changed target without output registration')
        self.assertFalse(h.completion_current(self.root,self.state()['tasks'],'T'))
        self.assertEqual(['T'], self.cli('inspect')['affected_tasks'])

    def test_deletion_action_receipt_tracks_tombstone(self):
        self.add('--scope','artifact','--required-action',json.dumps({'target_kind':'file','target_id':'artifact','operation':'delete'}))
        self.cli('start','T'); (self.root / 'artifact').unlink()
        self.cli('action','T','--target-kind','file','--target-id','artifact','--operation','delete','--result','passed','--evidence','check')
        self.completed(); self.assertIsNone(self.task()['action_results'][0]['target_version'])
        (self.root / 'artifact').write_text('restored')
        self.assertFalse(h.completion_current(self.root,self.state()['tasks'],'T'))

    def test_object_action_requires_version_and_tracks_registered_replacements(self):
        self.add('--external-target','obj:1','--required-action',json.dumps({'target_kind':'object','target_id':'obj:1','operation':'publish'}),kind='external')
        self.cli('start','T')
        args=('action','T','--target-kind','object','--target-id','obj:1','--operation','publish','--result','passed','--evidence','check')
        with self.assertRaises(ValueError): self.cli(*args)
        self.action_evidence()
        self.cli('output','T','obj:1','--kind','object','--value','{"version":1}')
        self.cli(*args)
        self.cli('output','T','obj:1','--kind','object','--value','{"version":2}')
        self.rejects_completion()
        self.cli(*args); self.completed()

    def test_unrelated_output_change_preserves_action_receipt(self):
        self.add('--scope','artifact','--scope','extra','--required-action',json.dumps({'target_kind':'file','target_id':'artifact','operation':'render'}))
        self.cli('start','T'); self.cli('output','T','artifact'); self.cli('output','T','extra')
        self.cli('action','T','--target-kind','file','--target-id','artifact','--operation','render','--result','passed','--evidence','check')
        (self.root / 'extra').write_text('new unrelated output'); self.cli('output','T','extra')
        self.completed()

    def parent_pair(self, group=None):
        self.prepared('--required-check', 'other', name='P')
        options = ('--publication-group-id', group) if group else ()
        self.cli('output', 'P', 'artifact', *options)
        self.cli('output', 'P', 'extra', *options)
        self.verify('--output', 'artifact', name='P')
        self.verify('--output', 'extra', name='P', check='other')
        self.completed('P')

    def child_answer(self, **kwargs):
        self.add('--after', 'P', '--consumes', self.consume('P', 'artifact', **kwargs), kind='answer')
        self.cli('start', 'T')
        self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'answer')
        self.completed()

    def test_unused_parent_output_preserves_consumer_and_check(self):
        self.parent_pair()
        self.add('--after', 'P', '--consumes', self.consume('P', 'artifact'), '--required-check', 'check', kind='answer')
        self.cli('start', 'T'); self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'answer')
        self.verify('--output', 'message:1'); self.completed()
        before = self.task()
        (self.root / 'extra').write_text('unrelated new display')
        self.assertEqual(['P'], self.cli('inspect', '--invalidate')['affected_tasks'])
        self.cli('requeue', 'P', '--output', 'extra')
        self.assertIn('artifact', self.task('P')['outputs'])
        self.assertIn('check', self.task('P')['check_receipts'])
        self.cli('start', 'P'); self.cli('output', 'P', 'extra'); self.verify('--output', 'extra', name='P', check='other'); self.completed('P')
        self.assertTrue(h.completion_current(self.root, self.state()['tasks'], 'T'))
        self.assertEqual(before, self.task())

    def test_after_is_order_only_even_if_producer_changes(self):
        self.parent_pair()
        self.add('--after', 'P', kind='answer'); self.cli('start', 'T')
        self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'ordered'); self.completed()
        (self.root / 'artifact').write_text('changed')
        self.assertEqual(['P'], self.cli('inspect', '--invalidate')['affected_tasks'])
        self.assertTrue(h.completion_current(self.root, self.state()['tasks'], 'T'))

    def test_ordering_requires_completion_before_start(self):
        self.add('--scope', 'artifact', name='P')
        self.add('--after', 'P', kind='answer')
        with self.assertRaises(ValueError): self.cli('start', 'T')

    def test_definition_change_invalidates_only_consuming_output(self):
        self.parent_pair()
        self.add('--consumes', self.consume('P', 'artifact'), '--consumes', self.consume('P', 'extra'),
                 '--required-check', json.dumps({'id': 'check', 'targets': ['message:1']}),
                 '--required-check', json.dumps({'id': 'other', 'targets': ['message:2']}),
                 '--required-output', json.dumps({'role': 'final', 'kind': 'message', 'target': 'message:1'}),
                 '--required-output', json.dumps({'role': 'extra', 'kind': 'message', 'target': 'message:2'}), kind='answer')
        self.cli('start', 'T')
        self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'a', '--dependency', ' ["P", "artifact"] ', '--producer-id', 'analysis')
        self.cli('output', 'T', 'message:2', '--kind', 'message', '--value', 'b', '--dependency', '["P","extra"]', '--producer-id', 'display')
        self.verify('--output', 'message:1'); self.verify('--output', 'message:2', check='other'); self.completed()
        survivor = self.task()['check_receipts']['other']
        self.cli('inspect', '--invalidate')
        # A semantic update without changing any artifact bytes.
        self.cli('requeue', 'P', '--output', 'artifact')
        self.cli('start', 'P'); self.cli('output', 'P', 'artifact', '--definition-versions', '{"sample":"v2"}')
        self.verify('--output', 'artifact', name='P'); self.completed('P')
        self.assertEqual(['T'], self.cli('inspect', '--invalidate')['affected_tasks'])
        self.cli('requeue', 'T')
        self.assertEqual(['message:2'], list(self.task()['outputs']))
        self.assertEqual({'other': survivor}, self.task()['check_receipts'])
        self.cli('start', 'T'); self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'a2', '--dependency', '["P","artifact"]')
        self.verify('--output', 'message:1'); self.completed()

    def test_selective_requeue_by_producer_keeps_unrelated_results(self):
        self.prepared('--required-check', 'other')
        self.cli('output', 'T', 'artifact', '--producer-id', 'numbers')
        self.cli('output', 'T', 'extra', '--producer-id', 'display')
        self.verify('--output', 'artifact'); self.verify('--output', 'extra', check='other')
        self.cli('transition', 'T', 'failed', '--next', 'Refresh display')
        self.cli('requeue', 'T', '--producer', 'display')
        self.assertEqual(['artifact'], list(self.task()['outputs']))
        self.assertEqual(['check'], list(self.task()['check_receipts']))

    def test_joint_publication_group_invalidates_member_consumer(self):
        self.parent_pair(group='joint')
        self.child_answer(publication_group_id='joint')
        (self.root / 'extra').write_text('changed joint member')
        self.assertEqual(['P', 'T'], self.cli('inspect', '--invalidate')['affected_tasks'])

    def test_git_executable_missing_allows_answer_registration(self):
        with patch.object(h.subprocess, 'check_output', side_effect=FileNotFoundError('git')):
            self.add(kind='answer')
        self.assertIsNone(self.task()['revision'])

    def legacy_v3_store(self, with_input):
        self.parent_pair()
        options = ('--input', 'artifact') if with_input else ()
        self.add('--after', 'P', '--required-check', 'check', *options, kind='answer')
        self.cli('start', 'T'); self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'answer')
        self.verify(); self.completed()
        state = self.state(); state['version'] = 3
        for task in state['tasks'].values():
            task.pop('consumes'); task.pop('compatibility_dependencies')
            task.pop('contract_revisions', None)
            task.pop('check_targets', None)
            for row in task['outputs'].values():
                for key in ('dependency_ids', 'definition_versions', 'producer_id'):
                    row.pop(key, None)
        task = state['tasks']['T']
        task['dependency_versions'] = {'P': h.versions(state['tasks']['P'])}
        task['check_receipts']['check']['versions']['dependencies'] = task['dependency_versions']
        task['verification']['versions']['dependencies'] = task['dependency_versions']
        task['authority'] = 'user:authorized'; task['attempts'] = 7; task['human_corrections'] = 3
        (self.root / '.agents/state/team.json').write_text(json.dumps(state))
        return state

    def test_v3_unique_input_migration_retains_results_and_counts(self):
        old = self.legacy_v3_store(True)
        migrated = self.cli('show')
        task = migrated['tasks']['T']
        self.assertEqual(5, migrated['version'])
        self.assertEqual(['artifact'], [r['output_id'] for r in task['consumes']])
        self.assertEqual([], task['compatibility_dependencies'])
        for key in ('outputs', 'authority', 'holds', 'attempts', 'usage', 'human_corrections', 'status'):
            self.assertEqual(old['tasks']['T'][key], task[key])
        # This legacy fixture changes authority and check-target context after
        # the saved receipts. Migration cannot authorize those stale checks.
        self.assertFalse(h.completion_current(self.root, migrated['tasks'], 'T'))
        (self.root / 'extra').write_text('unused')
        self.assertFalse(h.completion_current(self.root, migrated['tasks'], 'T'))

    def test_v3_unknown_dependency_keeps_compatibility_group_until_recontract(self):
        self.legacy_v3_store(False)
        migrated = self.cli('show')
        self.assertEqual(['P'], migrated['tasks']['T']['compatibility_dependencies'])
        self.assertFalse(h.completion_current(self.root, migrated['tasks'], 'T'))
        self.cli('requeue', 'T', '--consumes', self.consume('P', 'artifact'))
        self.assertEqual([], self.task()['compatibility_dependencies'])

    def test_explicit_message_and_object_consumption(self):
        for kind, value in [('message', 'text'), ('object', '{"n":1}')]:
            key = 'P' + kind
            self.add('--required-output', json.dumps({'role':'final', 'kind':kind, 'target':'logical'}), name=key, kind='answer')
            self.cli('start', key); self.cli('output', key, 'logical', '--kind', kind, '--value', value); self.completed(key)
            child = 'C' + kind
            self.add('--consumes', self.consume(key, 'logical', kind), name=child, kind='answer')
            self.cli('start', child); self.cli('output', child, 'message:1', '--kind', 'message', '--value', 'used'); self.completed(child)
            self.assertTrue(h.completion_current(self.root, self.state()['tasks'], child))


    def test_transitive_invalidation_follows_only_consumed_branch(self):
        self.parent_pair()
        self.add('--consumes', self.consume('P', 'artifact'), '--consumes', self.consume('P', 'extra'), kind='answer')
        self.cli('start', 'T')
        self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'a', '--dependency', '["P","artifact"]')
        self.cli('output', 'T', 'message:2', '--kind', 'message', '--value', 'b', '--dependency', '["P","extra"]')
        self.completed()
        for suffix, output in [('A', 'message:1'), ('B', 'message:2')]:
            key = 'C' + suffix
            self.add('--consumes', self.consume('T', output, 'message'), name=key, kind='answer')
            self.cli('start', key); self.cli('output', key, 'message:1', '--kind', 'message', '--value', suffix); self.completed(key)
        (self.root / 'artifact').write_text('changed')
        self.assertEqual(['CA', 'P', 'T'], self.cli('inspect', '--invalidate')['affected_tasks'])
        self.assertTrue(h.completion_current(self.root, self.state()['tasks'], 'CB'))

    def test_action_consumer_rejects_changed_producer_input(self):
        self.add('--input', 'input', '--external-target', 'obj:1',
                 '--required-action', json.dumps({'target_kind':'object','target_id':'obj:1','operation':'publish'}), kind='external', name='P')
        self.action_evidence()
        self.cli('start', 'P'); self.cli('action', 'P', '--target-kind', 'object', '--target-id', 'obj:1', '--target-version', 'v1', '--operation', 'publish', '--result', 'passed', '--evidence', 'check'); self.completed('P')
        self.add('--consumes', self.consume('P', 'obj:1', 'object'), kind='answer')
        self.cli('start', 'T'); self.cli('output', 'T', 'message:1', '--kind', 'message', '--value', 'used'); self.completed()
        (self.root / 'input').write_text('changed source')
        self.assertEqual(['P', 'T'], self.cli('inspect')['affected_tasks'])

    def test_malformed_consumes_and_cycles_rejected_without_mutation(self):
        self.parent_pair()
        with self.assertRaises(ValueError): self.add('--consumes', '{"producer_id":"P"}', kind='answer')
        self.child_answer()
        before = self.state()
        with self.assertRaises(ValueError): self.cli('requeue', 'P', '--consumes', self.consume('T', 'message:1', 'message'))
        self.assertEqual(before, self.state())


if __name__ == '__main__': unittest.main()
