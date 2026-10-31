#!/usr/bin/env python3
"""Cross-module writing gates; fixture host records are not model-run evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


n = load('writing_native_test', 'harness/native_check.py')
f = load('writing_fixture_test', 'harness/test_paragraph.py')
s = load('writing_state_test', 'harness/state.py')
p = f.p


class WritingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f.ParagraphTests.setUpClass()
        case = f.ParagraphTests()
        cls.writing_run, host = case.run_fixture()
        cls.packet = case.finish(cls.writing_run, host)

    def check(self, packet=True, *, operation='econ-writing:compose', candidate=None,
              sources=None, expected_rules=None, extra_views=None, artifacts=None):
        value = copy.deepcopy(self.packet) if packet is True else packet
        request = self.writing_run.state['request'].encode()
        candidate = (self.writing_run.state['manuscript']['text'] if candidate is None else candidate).encode()
        contract = n.gate.canonical({'schema_version': 2, 'request_sha256': n.gate.sha(request),
            'requirements': [{'id': 'result', 'kind': 'content', 'source_text': request.decode(),
                'target': 'message://final', 'evaluator': {'type': 'contains_literal', 'value': '処方'},
                'evidence_refs': [], 'status': 'pending'}]})
        views = dict(extra_views or {})
        if value is not None:
            views[p.PACKET_PATH] = n.gate.canonical(value)
        return n.check_native('candidate.md', candidate, request, contract, artifacts or {}, b'[]',
            n.gate.canonical(self.writing_run.state['rules']['dictionary']), 'test-author',
            n.gate.sha(request), n.gate.sha(contract), n.gate.sha(candidate),
            sources=sources if sources is not None else {k: row['text'].encode() for k, row in self.writing_run.state['sources'].items()},
            view_files=views, operation=operation,
            expected_writing_rules=expected_rules or self.writing_run.state['rules'])

    def reasons(self, result):
        return ' '.join(row.get('message', '') for row in result['failed_checks'])

    def test_each_writing_mode_requires_packet(self):
        for operation in p.OPERATIONS:
            with self.subTest(operation=operation):
                self.assertIn('mandatory paragraph execution packet missing', self.reasons(self.check(None, operation=operation)))

    def test_packet_is_prerequisite_and_keeps_independent_final_gate(self):
        result = self.check()
        self.assertIn('paragraph-execution', result['executed_checks'], self.reasons(result))
        self.assertFalse(result['release_authorized'])
        self.assertEqual({r['check'] for r in result['missing_checks']} & {'quality-a','quality-b','compliance'},
                         {'quality-a','quality-b','compliance'})
        self.assertEqual(result['prose_scan']['dictionary_rule_count'], 142)
        self.assertEqual(len(n.PROSE_CHECK_IDS), 22)

    def test_internal_packet_does_not_enter_reader_prose(self):
        result = self.check()
        self.assertNotIn('views/' + p.PACKET_PATH, result['prose_scan']['paths'])
        self.assertIn('candidate/candidate.md', result['prose_scan']['paths'])
        self.assertEqual(result['bindings']['paragraph_packet_sha256'], n.gate.sha(n.gate.canonical(self.packet)))

    def test_candidate_edit_invalidates_integration(self):
        result = self.check(candidate=self.writing_run.state['manuscript']['text'] + '変更。')
        self.assertIn('candidate target differs', self.reasons(result))

    def test_source_edit_invalidates_packet(self):
        sources = {k: v['text'].encode() for k, v in self.writing_run.state['sources'].items()}
        sources['s1'] += b' changed'
        self.assertIn('immutable source bytes', self.reasons(self.check(sources=sources)))

    def test_adopted_rule_change_invalidates_packet(self):
        rules = copy.deepcopy(self.writing_run.state['rules'])
        rules['texts']['CORE'] += '\nChanged rule.'
        self.assertIn('adopted policy and profile', self.reasons(self.check(expected_rules=rules)))

    def test_wrong_writing_operation_rejected(self):
        self.assertIn('adopted route', self.reasons(self.check(operation='econ-writing:translate')))

    def test_unknown_private_view_is_rejected(self):
        self.assertIn('unreferenced internal text view', self.reasons(self.check(extra_views={'other.json': b'{}'})))

    def test_packet_cannot_be_attached_to_nonwriting_operation(self):
        self.assertIn('adopted final writing operation', self.reasons(self.check(operation='econ-data:execute')))

    def test_delivered_artifact_is_still_scanned(self):
        result = self.check(artifacts={'extra.md': b'uncertainty'})
        self.assertTrue(any(row['check'] == 'B25' for row in result['failed_checks']))
        self.assertIn('artifacts/extra.md', result['prose_scan']['paths'])

    def test_saved_writing_state_invalidates_task_evidence_on_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.writing_run.save(root / 'paragraphs.json')
            task = {'status': 'running', 'check_receipts': {'old': {}}, 'verification': {},
                    'history': [], 'next': 'Integrate'}
            ref = s.bind_paragraph_state(root, task, 'paragraphs.json')
            self.assertEqual(ref['blueprint_sha256'], self.writing_run.state['blueprint']['sha256'])
            self.assertFalse(task['check_receipts'])
            self.assertEqual(s.context_changes(root, task), [])
            with (root / 'paragraphs.json').open('a') as output:
                output.write('\n')
            self.assertIn('writing_state:paragraphs.json', s.context_changes(root, task))

    def test_both_fixed_literals_are_restored_once(self):
        restored = n.expression_policy.primary_instruction(p.PRIMARY_RULE + p.JAPANESE_RULE + ' Continue.')
        self.assertEqual(restored.count(p.PRIMARY_RULE), 1)
        self.assertEqual(restored.count(p.JAPANESE_RULE), 1)

    def test_operation_registry_scopes_execution_closure_to_formal_review(self):
        resolver = load('writing_integration_routes', 'scripts/route_registry.py')
        routes = resolver.load_routes(ROOT)
        for operation in p.OPERATIONS:
            ordinary = resolver.resolve_operation(routes, operation)
            self.assertNotIn('paragraph-engine', ordinary['resource_sections'])
            formal = resolver.resolve_operation(routes, operation, conditions=['formal_review_requested'])
            self.assertTrue({'native-check', 'paragraph-engine', 'argument-engine'} <= formal['resource_sections'].keys())
        self.assertIn('paragraph-engine.all', routes['rules']['native-check.all']['requires'])

    def test_github_action_checks_exact_call_target_and_guard(self):
        args = {'repository_full_name': 'owner/repo', 'branch_name': 'main', 'sha': 'a' * 40,
                'expected_sha': 'b' * 40, 'force': False}
        returned = {'content': [{'type': 'text', 'text': 'Action completed.'}],
                    'structuredContent': {'success': True}, 'isError': False}
        event = {'event_id': 'fixture-event', 'operation': 'github.update_ref',
                 'target': 'owner/repo:refs/heads/main', 'status': 'success'}
        def report(call):
            call_text, return_text = json.dumps(call), json.dumps(returned)
            return {'action_results_verified': [{**event, 'tool_name': 'mcp__codex_apps__github_update_ref',
                'tool_call_ref': 'fixture-call', 'tool_return_ref': 'fixture-return',
                'call_args_text': call_text, 'call_args_sha256': n.gate.sha(call_text.encode()),
                'return_text': return_text, 'return_sha256': n.gate.sha(return_text.encode()),
                'source_verification': {'status': 'matched-to-runtime', 'reference': 'offline-fixture', 'verifier_id': 'fixture'}}]}
        self.assertEqual(n._operation_results(report(args), [event]), {'fixture-event'})
        for change in ({'branch_name': 'other'}, {'force': True}, {'expected_sha': ''}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                n._operation_results(report({**args, **change}), [event])

    def test_connector_error_or_conflicting_copy_is_rejected(self):
        args = {'sha': 'a' * 40}
        for result in ({'success': False}, {'isError': True, 'structuredContent': {'success': True}},
                       {'structuredContent': {'success': True}, 'content': [{'type': 'text', 'text': '{"success":false}'}]}):
            with self.subTest(result=result), self.assertRaises(ValueError):
                n._connector_operation(result, args, 'github.update_ref', 'owner/repo:refs/heads/main', 'github-ref')

    def test_plugin_action_requires_changed_matching_release(self):
        args = {'plugin_id': 'plugins_fixture', 'expected_release_id': 'release-old'}
        leaf = {'status': 'updated', 'plugin_id': 'plugins_fixture', 'release_id': 'release-new',
                'latest_release_id': 'release-new', 'version': '0.4.0', 'plugin_url': 'https://chatgpt.com/plugin/fixture'}
        self.assertEqual(n._connector_operation({'result': leaf}, args, 'plugin_creator.update_plugin',
                         'plugins_fixture', 'plugin-update')['release_id'], 'release-new')
        for change in ({'plugin_id': 'plugins_other'}, {'release_id': 'release-old', 'latest_release_id': 'release-old'},
                       {'status': 'created'}, {'error': 'denied'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                n._connector_operation({**leaf, **change}, args, 'plugin_creator.update_plugin', 'plugins_fixture', 'plugin-update')


if __name__ == '__main__':
    unittest.main()
