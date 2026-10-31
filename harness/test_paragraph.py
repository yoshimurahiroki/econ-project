#!/usr/bin/env python3
"""Paragraph-contract integration tests using a recorded test host adapter."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('paragraph_under_test', Path(__file__).with_name('paragraph.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def span(text, quote=None):
    quote = text if quote is None else quote
    index = text.index(quote)
    return {'start': index, 'end': index + len(quote), 'quote': quote}


def rules():
    return {'policy_id': 'test-policy', 'texts': {key: (ROOT / path).read_text() for key, path in {
        'CORE': 'runtime/CORE.md', 'PROSE': 'runtime/PROSE.md', 'econ-writing': 'skills/econ-writing/SKILL.md',
        'prose-guide': 'quality/prose_rules.md'}.items()},
        'dictionary': json.loads((ROOT / 'quality/prose_rules.json').read_text()),
        'profile': {'id': 'default-micro', 'text': (ROOT / 'profiles/default-micro/PROFILE.md').read_text()}}


def argument_fixture(blueprint, sources):
    paragraphs = blueprint['paragraphs']
    multiple = len(paragraphs) > 1
    scope = {'population': 'fictional regions', 'period': 'fixture period', 'unit': 'prescriptions',
             'denominator': 'region', 'comparison': 'common regional comparison', 'conditions': ['fictional fixture'],
             'definitions': blueprint['definitions']}
    nodes = []
    for index, paragraph in enumerate(paragraphs, 1):
        sid = paragraph['source_ids'][0]
        ref = {'source_id': sid, 'source_sha256': sources[sid]['sha256'], **span(sources[sid]['text'])}
        nodes.append({'node_id': 'n' + str(index), 'parent_id': 'n0' if multiple else None, 'child_ids': [],
                      'claim': paragraph['central_proposition'],
                      'question': 'What does this regional comparison establish?' if multiple else blueprint['central_question'],
                      'next_questions': [], 'logical_role': 'observation', 'inference_form': 'atomic',
                      'abstraction_level': 1 if multiple else 0, 'scope': copy.deepcopy(scope), 'source_refs': [ref],
                      'section_id': paragraph['section_id'], 'paragraph_ids': [paragraph['paragraph_id']],
                      'reasoning': paragraph['central_proposition'],
                      'order': {'basis': 'structure', 'position': index, 'rationale': 'Present the regional comparison in its adopted order.'}})
    groups = []
    if multiple:
        root_claim = 'The regional counts establish the policy comparison using a common aggregation.'
        child_ids = [row['node_id'] for row in nodes]
        nodes.insert(0, {'node_id': 'n0', 'parent_id': None, 'child_ids': child_ids, 'claim': root_claim,
                        'question': blueprint['central_question'],
                        'next_questions': [{'question': 'What does each region contribute to the comparison?', 'answered_by': child_ids}],
                        'logical_role': 'conclusion', 'inference_form': 'inductive', 'abstraction_level': 0,
                        'scope': copy.deepcopy(scope), 'source_refs': [], 'section_id': 'introduction', 'paragraph_ids': [],
                        'reasoning': 'Combine the regional observations on their common aggregation.',
                        'integration': {'member_ids': child_ids, 'conclusion': root_claim,
                                        'common_property': 'Regional prescription counts', 'meaning': 'The regional observations jointly define the comparison.'},
                        'order': {'basis': 'structure', 'position': 0, 'rationale': 'State the integrated comparison.'}})
        groups = [{'group_id': 'regional-observations', 'parent_id': 'n0', 'member_ids': child_ids,
                   'classification_basis': 'Regional prescription observations', 'logical_role': 'observation',
                   'inference_form': 'inductive', 'order': {'basis': 'structure', 'ordered_ids': child_ids,
                                                          'rationale': 'Present each region within the common comparison.'}}]
        blueprint['central_answer'] = root_claim
    graph = {'schema_version': 1, 'version': blueprint['version'], 'central_question': blueprint['central_question'],
             'central_answer': blueprint['central_answer'], 'root_ids': ['n0' if multiple else 'n1'],
             'nodes': nodes, 'groups': groups, 'dependencies': [], 'source_ids': list(sources),
             'source_manifest': {sid: source['sha256'] for sid, source in sources.items()}}
    return graph


def fixture(language='ja', count=2, dependencies=False):
    if language == 'ja':
        texts = ['対象地域の処方件数は10件増えた。費用の低下が処方を増やした。',
                 '比較地域の処方件数は2件増えた。両地域の差は8件だった。',
                 '研究者は処方件数を地域ごとに集計した。地域別の集計で比較を統一した。']
    else:
        texts = ['Prescriptions in the treatment area increased by 10. Lower costs increased prescribing.',
                 'Prescriptions in the comparison area increased by 2. The difference between areas was 8.',
                 'Researchers counted prescriptions within each area. The common aggregation aligned the comparison.']
    texts = texts[:count]
    sources = {f's{i+1}': {'text': text, 'origin_id': f'fictional-test-source-{i+1}', 'sha256': p.sha(text)} for i, text in enumerate(texts)}
    blueprint = {'schema_version': 1, 'version': '1', 'purpose': 'Explain the fictional research result', 'reader': 'research reader',
                 'central_question': 'How did the policy change prescribing?', 'central_answer': texts[0],
                 'contribution': 'Separate the treatment comparison.', 'completion_conditions': ['Explain every paragraph contract'],
                 'sections': [{'section_id': 'introduction', 'role': 'answer the research question', 'claim': texts[0]}],
                 'paragraphs': [{'paragraph_id': f'p{i+1}', 'section_id': 'introduction', 'central_proposition': text,
                                 'role': 'present the result' if i == 0 else 'explain the comparison',
                                 'depends_on': [f'p{i}'] if dependencies and i else [], 'source_ids': [f's{i+1}'],
                                 'scope': 'The fictional research comparison'} for i, text in enumerate(texts)],
                 'definitions': {'prescriptions': 'counted prescriptions'}, 'quantities': [],
                 'conditions': ['Fictional fixture'], 'writing_rules': ['one purpose per paragraph'],
                 'prohibited_rules': [p.PRIMARY_RULE, p.JAPANESE_RULE]}
    blueprint['argument_structure'] = argument_fixture(blueprint, sources)
    specifications = []
    for i, text in enumerate(texts):
        pid, sid, claim_id = f'p{i+1}', f's{i+1}', f'n{i+1}'
        specifications.append({
            'paragraph_id': pid, 'section_id': 'introduction', 'blueprint_version': '1',
            'role': {'purpose': 'Explain the assigned result', 'contribution_to_global_argument': 'Establish the research comparison'},
            'central_proposition': {'claim': text, 'logical_status': 'source-observation'},
            'required_content': [{'proposition_id': claim_id, 'exact_content': text, 'source_id': sid,
                                  'source_location': span(text), 'evidence_type': 'source-observation',
                                  'required_reasoning': text}],
            'logical_structure': {'opening': text, 'development': text, 'mechanism': text, 'implication': text},
            'relationships': {'preceding_paragraph': f'p{i}' if i else None,
                              'following_paragraph': f'p{i+2}' if i + 1 < count else None,
                              'inherited_information': [], 'information_to_pass_forward': [text]},
            'terminology': {'adopted_definitions': blueprint['definitions'], 'fixed_quantities': [], 'required_terms': []},
            'scope': {'included': [text], 'excluded': ['unrelated research'], 'content_change_authority': 'assigned paragraph'},
            'writing': {'language': language, 'profile': 'default-micro', 'paragraph_rules': ['one purpose'],
                        'prohibited_functions': [p.PRIMARY_RULE, p.JAPANESE_RULE],
                        'instruction_packet': p.PRIMARY_RULE + '\n' + p.JAPANESE_RULE, 'source_references': [sid]},
            'completion': {'mandatory_claims': [claim_id], 'evidence_correspondence': 'every claim',
                           'logical_coherence': 'all sentences', 'prose_compliance': '142 rules', 'local_review': 'required'},
            **p._argument_io().paragraph_argument(blueprint['argument_structure'], f'n{i+1}'),
        })
    return blueprint, specifications, sources


class RecordedTestHost:
    """A unit-test transport; its events are explicitly test observations."""

    def __init__(self, kind='independent-subagent'):
        self.kind, self.events, self.tasks, self.counter = kind, {}, [], 0
        self.override = None
        self.integration_fail = False
        self.integration_edit = None
        self.fail_pid = None
        self.blueprint = None
        self.specifications = None
        self.argument_fail = False
        self._lock = threading.Lock()
        self.returns = {}

    def observe(self, event_id):
        return copy.deepcopy(self.events[event_id])

    def recover(self, task):
        returned = self.returns[task['input_sha256']]
        if returned.get('status') == 'failed':
            return copy.deepcopy(returned)
        return {'event_id': returned['event_id'], 'status': 'completed', 'returned': copy.deepcopy(returned)}

    def __call__(self, task):
        with self._lock:
            self.counter += 1
            sequence = self.counter
            self.tasks.append(copy.deepcopy(task))
        op, payload = task['operation'], task['payload']
        pid = payload.get('paragraph_id') or payload.get('specification', {}).get('paragraph_id')
        if op in ('argument.review', 'argument.compare'):
            graph = payload['graph']
            source_ref = next(ref for node in graph['nodes'] for ref in node['source_refs'])
            failed = self.argument_fail and op == 'argument.compare'
            value = {'checks': [{'check_id': key, 'verdict': 'fail' if failed and key == 'reverse_alignment' else 'pass',
                     'assessment': 'The fixture graph and cited original establish the named relation.',
                     'node_ids': [node['node_id'] for node in graph['nodes']], 'source_refs': [source_ref]}
                     for key in payload['required_checks']],
                     'findings': [{'finding_id': 'test-outline-mismatch', 'check_id': 'reverse_alignment',
                                  'node_ids': [graph['nodes'][0]['node_id']], 'cause_level': 'global',
                                  'message': 'The extracted argument differs from the designed claim.',
                                  'repair': 'Revise the affected claim and repeat the comparison.'}] if failed else []}
        elif op == 'argument.reverse':
            paragraphs = payload['manuscript']
            sections = list(dict.fromkeys(row['section_id'] for row in paragraphs))
            value = {'paragraphs': [{'paragraph_id': row['paragraph_id'], 'section_id': row['section_id'],
                       'central_claim': row['text'], 'role': 'State the regional observation.', 'text_spans': [span(row['text'])]}
                      for row in paragraphs],
                     'sections': [{'section_id': sid, 'claim': 'The regional observations establish the comparison.',
                                  'paragraph_ids': [row['paragraph_id'] for row in paragraphs if row['section_id'] == sid]} for sid in sections],
                     'central_question': 'How did the policy change prescribing?',
                     'central_answer': 'The regional observations establish the policy comparison.'}
        elif op == 'writing:architect':
            value = {'blueprint': self.blueprint}
        elif op == 'writing:specify':
            value = {'specifications': self.specifications}
        elif op == 'writing:paragraph':
            if pid == self.fail_pid:
                event_id = f'test-failed-{sequence}'
                self.events[event_id] = {'test_fixture': True, 'status': 'failed',
                                         'input_sha256': task['input_sha256']}
                self.returns[task['input_sha256']] = {'event_id': event_id, 'status': 'failed'}
                raise RuntimeError('test writer failure')
            value = {'paragraph_id': pid, 'text': payload['specification']['central_proposition']['claim'],
                     'binding': payload['binding'], 'read_instruction_sha256': p.content_hash(task['instruction_context'])}
        elif op == 'writing:paragraph-review':
            text, spec, sources = payload['text'], payload['specification'], payload['sources']
            hits = payload['lexical_hits']
            value = {'paragraph_id': pid, 'text_sha256': p.sha(text), 'spec_sha256': p.content_hash(spec),
                     'binding': payload['binding'], 'checks': [{'check_id': key, 'verdict': 'fail' if hits and key == 'prose-compliance' else 'pass',
                         'assessment': 'The inspected text corresponds to the named paragraph requirement.', 'spans': [span(text)]} for key in p.LOCAL_CHECKS],
                     'claim_evidence': [{'proposition_id': row['proposition_id'], 'assessment': 'The text states this source proposition.',
                          'source_id': row['source_id'], 'source_sha256': sources[row['source_id']]['sha256'],
                          'target': span(text), 'source': row['source_location']} for row in spec['required_content']],
                     'reasoning': [{'proposition_id': row['proposition_id'], 'assessment': 'The assigned reasoning appears in the paragraph.',
                                   'required_reasoning': row['required_reasoning'], 'target': span(text)} for row in spec['required_content']],
                     'quantity_evidence': [],
                     'occurrence_judgments': [{'rule_id': row['rule_id'], 'start': row['start'], 'end': row['end'],
                         'function': 'prohibited expression', 'meaning': row['matched_text'], 'syntax': 'clause',
                         'proposition': spec['central_proposition']['claim'], 'verdict': 'violation', 'text_sha256': p.sha(text)} for row in hits],
                     'findings': [{'check_id': 'prose-compliance', 'span': span(text), 'problem': 'The paragraph contains a prohibited expression.',
                                  'repair': 'Remove the prohibited expression.'}] if hits else []}
            for match in p.QUANTITY.finditer(text):
                sid = next((sid for sid, s in sources.items() if any(m.group() == match.group() for m in p.QUANTITY.finditer(s['text']))), None)
                if sid:
                    source_match = next(m for m in p.QUANTITY.finditer(sources[sid]['text']) if m.group() == match.group())
                    value['quantity_evidence'].append({'target': {'start': match.start(), 'end': match.end(), 'quote': match.group()},
                         'source_id': sid, 'source_sha256': sources[sid]['sha256'], 'assessment': 'Same adopted number.',
                         'source': {'start': source_match.start(), 'end': source_match.end(), 'quote': source_match.group()}})
        elif op in ('writing:section-integrate', 'writing:manuscript-integrate'):
            paragraphs = copy.deepcopy(payload['paragraphs'])
            if self.integration_edit:
                key, replacement = self.integration_edit
                paragraphs[key] = replacement
                self.integration_edit = None
            text = '\n\n'.join(paragraphs.values())
            value = {'paragraph_hashes': payload['paragraph_hashes'], 'paragraphs': paragraphs, 'text': text,
                     'checks': [{'check_id': key, 'verdict': 'fail' if self.integration_fail and key == 'logical-order' else 'pass',
                                 'assessment': 'The complete text is compared with its assigned argument.', 'spans': [span(text)]}
                                for key in payload['required_checks']],
                     'findings': [{'check_id': 'logical-order', 'problem': 'The second paragraph contradicts the first.'}] if self.integration_fail else []}
            if op == 'writing:manuscript-integrate':
                value['outline_comparison'] = [{'paragraph_id': key, 'assessment': 'The extracted proposition matches its design role.',
                    'spec_sha256': p.content_hash(payload['specifications'][key]), 'outline_sha256': p.content_hash(payload['reverse_outline']),
                    'verdict': 'pass'} for key in paragraphs]
        else:
            raise AssertionError(op)
        if self.override:
            value = self.override(task, value)
        role = op.split(':')[-1]
        worker_id = 'test-' + role + '-' + str(pid or 'document') if self.kind == 'independent-subagent' else 'test-author'
        event_id, launch_ref, turn_ref = f'test-return-{sequence}', f'test-launch-{sequence}', f'test-turn-{sequence}'
        original = json.dumps(value, ensure_ascii=False)
        event = {'test_fixture': True, 'worker_id': worker_id, 'input_sha256': task['input_sha256'],
                 'return_sha256': p.sha(original), 'status': 'completed', 'execution_kind': self.kind}
        result = {'worker_id': worker_id, 'event_id': event_id, 'input_sha256': task['input_sha256'], 'return_text': original}
        if self.kind == 'independent-subagent':
            result['launch_ref'] = event['launch_ref'] = launch_ref
            self.events[launch_ref] = {'test_fixture': True, 'worker_id': worker_id, 'input_sha256': task['input_sha256'],
                                       'status': 'running', 'execution_kind': self.kind}
        else:
            result['turn_ref'] = event['turn_ref'] = turn_ref
        self.events[event_id] = event
        self.returns[task['input_sha256']] = copy.deepcopy(result)
        return result


class ParagraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = rules()

    def run_fixture(self, language='ja', count=2, dependencies=False, operation='compose', editable_ids=None, kind='independent-subagent'):
        bp, specs, sources = fixture(language, count, dependencies)
        original = {s['paragraph_id']: s['central_proposition']['claim'] for s in specs} if operation in ('revise', 'translate', 'convert') else None
        run = p.ParagraphRun.create(run_id='test-run', request='Write the fictional research introduction.', authority='Write assigned paragraphs.',
                    author_id='test-author', operation='econ-writing:' + operation, blueprint=bp, specifications=specs,
                    sources=sources, rules=self.rules, execution_kind=kind, original_paragraphs=original, editable_ids=editable_ids)
        return run, RecordedTestHost(kind)

    def finish(self, run, host):
        run.write(host, host.observe, max_workers=3)
        for pid in run.state['paragraphs']:
            self.assertTrue(run.review(pid, host, host.observe)['result']['passed'])
        for section in run.state['blueprint']['sections']:
            self.assertEqual(run.integrate_section(section['section_id'], host, host.observe)['status'], 'integrated')
        self.assertEqual(run.integrate_manuscript(host, host.observe)['status'], 'integrated')
        packet = run.packet()
        self.assertTrue(p.validate_packet(packet, run.state['manuscript']['text'])['valid'])
        return packet

    def test_japanese_multiparagraph_introduction(self):
        run, host = self.run_fixture()
        packet = self.finish(run, host)
        self.assertEqual(len(packet['paragraphs']), 2)
        self.assertFalse(packet['release_authorized'])

    def test_english_multiparagraph_introduction(self):
        self.finish(*self.run_fixture('en'))

    def test_single_paragraph_contract(self):
        self.finish(*self.run_fixture(count=1))

    def test_blueprint_and_specification_generation_calls_host(self):
        bp, specs, sources = fixture()
        host = RecordedTestHost(); host.blueprint, host.specifications = bp, specs
        brief = {'original_request': 'Write the fictional result.', 'authority': 'Write', 'purpose': 'Explain', 'reader': 'Researchers'}
        output = p.generate_blueprint(brief, sources, self.rules, host, host.observe)
        designed = p.generate_specifications(output['blueprint'], sources, self.rules, host, host.observe,
                                             request=brief['original_request'], authority='Write')
        self.assertEqual(designed['specifications'], specs)
        self.assertEqual(host.tasks[0]['operation'], 'writing:architect')

    def test_results_quantities_and_table(self):
        run, host = self.run_fixture('en', count=1)
        row = run.state['paragraphs']['p1']
        table = 'Prescriptions increased by 10.\n\n| Outcome | Change |\n| --- | --- |\n| Prescriptions | 10 |'
        run.state['sources']['s1']['text'] = table
        run.state['sources']['s1']['sha256'] = p.sha(table)
        row['spec']['required_content'][0]['source_location'] = span(table)
        run.state['blueprint']['argument_structure'] = argument_fixture(run.state['blueprint'], run.state['sources'])
        run.state['blueprint'] = p.seal_blueprint(run.state['blueprint'], run.state['sources'])
        row['spec'].update(p._argument_io().paragraph_argument(run.state['blueprint']['argument_structure'], 'n1'))
        row['spec_sha256'] = p.content_hash(row['spec'])
        host.override = lambda task, value: ({**value, 'text': table} if task['operation'] == 'writing:paragraph' else value)
        self.finish(run, host)

    def test_revision_preserves_other_paragraph_bytes(self):
        run, host = self.run_fixture(operation='revise', editable_ids=['p2'])
        before = run.state['paragraphs']['p1']['text']
        self.finish(run, host)
        writer_ids = [task['payload']['specification']['paragraph_id'] for task in host.tasks if task['operation'] == 'writing:paragraph']
        self.assertEqual(writer_ids, ['p2'])
        self.assertEqual(run.state['paragraphs']['p1']['text'], before)

    def test_local_pass_global_failure_blocks_packet(self):
        run, host = self.run_fixture()
        run.write(host, host.observe, max_workers=2)
        for pid in run.state['paragraphs']:
            self.assertTrue(run.review(pid, host, host.observe)['result']['passed'])
        host.integration_fail = True
        result = run.integrate_section('introduction', host, host.observe)
        self.assertEqual(result['status'], 'failed')
        with self.assertRaises(p.ParagraphError):
            run.packet()

    def test_missing_claim_correspondence_is_rejected(self):
        run, host = self.run_fixture(count=1)
        run.write(host, host.observe)
        host.override = lambda task, value: {**value, 'claim_evidence': []}
        result = run.review('p1', host, host.observe)
        self.assertFalse(result['result']['passed'])
        self.assertIn('mandatory claim', result['result']['structural_errors'][0])

    def test_duplicate_proposition_ownership_rejected(self):
        bp, specs, sources = fixture()
        specs[1]['required_content'][0]['proposition_id'] = 'n1'
        specs[1]['completion']['mandatory_claims'] = ['n1']
        with self.assertRaisesRegex(p.ParagraphError, 'multiple paragraph owners|proposition order differs'):
            p.ParagraphRun.create(run_id='test', request='Write', authority='Write', author_id='a', operation='econ-writing:compose',
                                   blueprint=bp, specifications=specs, sources=sources, rules=self.rules)

    def test_numeric_source_mismatch_rejected(self):
        run, host = self.run_fixture('en', count=1)
        host.override = lambda task, value: {**value, 'text': value['text'].replace('10', '11')} if task['operation'] == 'writing:paragraph' else value
        run.write(host, host.observe)
        result = run.review('p1', host, host.observe)
        self.assertFalse(result['result']['passed'])
        self.assertIn('quantity', result['result']['structural_errors'][0])

    def test_prohibited_expression_records_failure_and_repair(self):
        run, host = self.run_fixture('en', count=1)
        host.override = lambda task, value: {**value, 'text': 'However, ' + value['text']} if task['operation'] == 'writing:paragraph' else value
        run.write(host, host.observe)
        result = run.review('p1', host, host.observe)
        self.assertFalse(result['result']['passed'])
        self.assertGreater(result['result']['lexical_hits'], 0)
        host.override = None
        self.assertTrue(run.repair('p1', host, host.observe)['result']['passed'])
        self.assertEqual(run.state['paragraphs']['p1']['repair_count'], 1)

    def test_specification_change_reopens_only_affected_reviews(self):
        run, host = self.run_fixture(count=3, dependencies=False)
        self.finish(run, host)
        old_p3 = copy.deepcopy(run.state['paragraphs']['p3']['review'])
        spec = copy.deepcopy(run.state['paragraphs']['p1']['spec'])
        spec['role']['purpose'] += ' with the adopted comparison'
        self.assertEqual(run.update_specification(spec), ['p1'])
        self.assertEqual(run.state['paragraphs']['p3']['review'], old_p3)
        self.assertIsNone(run.state['manuscript'])

    def test_source_change_invalidates_dependents(self):
        run, host = self.run_fixture(dependencies=True)
        self.finish(run, host)
        sources = copy.deepcopy(run.state['sources'])
        sources['s1']['text'] += ' 追加記録。'; sources['s1']['sha256'] = p.sha(sources['s1']['text'])
        self.assertEqual(run.update_sources(sources), ['p1', 'p2'])
        self.assertIsNone(run.state['paragraphs']['p2']['review'])

    def test_interruption_resume_reuses_current_drafts(self):
        run, host = self.run_fixture()
        run.write(host, host.observe)
        run.review('p1', host, host.observe)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            run.save(path)
            resumed = p.ParagraphRun.load(path)
            self.assertEqual(resumed.state['paragraphs']['p1']['review'], run.state['paragraphs']['p1']['review'])
            self.assertEqual(resumed.tasks(), [])
            self.assertEqual(resumed.state['events'][-1]['kind'], 'resumed')

    def test_chat_sequential_path_has_no_independent_writer_claim(self):
        run, host = self.run_fixture(kind='single-agent-sequential')
        self.finish(run, host)
        for row in run.state['paragraphs'].values():
            self.assertEqual(row['writer']['execution_kind'], 'single-agent-sequential')
            self.assertNotIn('launch_ref', row['writer'])
            self.assertIn('turn_ref', row['writer'])

    def test_independent_final_review_remains_required(self):
        run, host = self.run_fixture()
        packet = self.finish(run, host)
        result = p.validate_packet(packet, run.state['manuscript']['text'])
        self.assertEqual(result['required_final_roles'], ['quality-a', 'quality-b', 'compliance'])
        self.assertEqual(len(result['required_final_prose_checks']), 22)
        self.assertFalse(result['release_authorized'])

    def test_actual_launch_actor_and_return_bytes_are_checked(self):
        run, host = self.run_fixture(count=1)
        run.review_argument(host, host.observe)
        task = run.tasks()[0]; run.assign(task)
        returned = host(task)
        host.events[returned['launch_ref']]['worker_id'] = 'different-worker'
        with self.assertRaisesRegex(p.ParagraphError, 'launch actor'):
            run.accept_draft('p1', returned, host.observe)

    def test_stale_return_is_rejected(self):
        run, host = self.run_fixture(count=1)
        run.review_argument(host, host.observe)
        task = run.tasks()[0]; run.assign(task); returned = host(task)
        run.state['sources']['s1']['sha256'] = '0' * 64
        with self.assertRaisesRegex(p.ParagraphError, 'dependencies changed'):
            run.accept_draft('p1', returned, host.observe)

    def test_parallel_and_dependent_writer_layers(self):
        run, host = self.run_fixture(dependencies=True)
        run.write(host, host.observe, max_workers=3)
        writer_tasks = [task for task in host.tasks if task['operation'] == 'writing:paragraph']
        self.assertEqual([task['payload']['specification']['paragraph_id'] for task in writer_tasks], ['p1', 'p2'])
        self.assertEqual(writer_tasks[1]['payload']['binding']['dependencies']['p1'], run.state['paragraphs']['p1']['text_sha256'])

    def test_cycle_is_rejected_before_writing(self):
        bp, _, _ = fixture(dependencies=True)
        bp['paragraphs'][0]['depends_on'] = ['p2']
        with self.assertRaisesRegex(p.ParagraphError, 'cycle'):
            p.seal_blueprint(bp)

    def test_integrator_change_requires_local_recheck(self):
        run, host = self.run_fixture()
        run.write(host, host.observe)
        for pid in run.state['paragraphs']:
            run.review(pid, host, host.observe)
        host.integration_edit = ('p1', run.state['paragraphs']['p1']['text'] + ' 集計は地域単位である。')
        result = run.integrate_section('introduction', host, host.observe)
        self.assertEqual(result['status'], 'recheck-required')
        self.assertEqual(run.state['paragraphs']['p1']['status'], 'drafted')
        with self.assertRaises(p.ParagraphError):
            run.packet()

    def test_reverse_outline_receives_manuscript_before_blueprint(self):
        run, host = self.run_fixture()
        self.finish(run, host)
        task = next(t for t in host.tasks if t['operation'] == 'argument.reverse')
        self.assertNotIn('blueprint', task['payload'])
        self.assertNotIn('specifications', task['payload'])
        self.assertNotIn('graph', task['payload'])

    def test_all_five_registered_operations(self):
        for mode in ('compose', 'revise', 'translate', 'explain', 'convert'):
            with self.subTest(mode=mode):
                self.finish(*self.run_fixture(count=1, operation=mode))

    def test_tampered_integration_original_is_rejected(self):
        run, host = self.run_fixture(count=1)
        packet = self.finish(run, host)
        original = json.loads(packet['manuscript']['execution']['return_text'])
        original['checks'][0]['verdict'] = 'fail'
        raw = json.dumps(original, ensure_ascii=False)
        packet['manuscript']['execution']['return_text'] = raw
        packet['manuscript']['execution']['return_sha256'] = p.sha(raw)
        packet['packet_sha256'] = p.content_hash({k: v for k, v in packet.items() if k != 'packet_sha256'})
        self.assertFalse(p.validate_packet(packet, run.state['manuscript']['text'])['valid'])

    def test_rule_update_invalidates_every_review(self):
        run, host = self.run_fixture()
        self.finish(run, host)
        updated = copy.deepcopy(self.rules); updated['policy_id'] = 'test-policy-2'
        self.assertEqual(run.update_rules(updated), ['p1', 'p2'])
        self.assertTrue(all(row['review'] is None for row in run.state['paragraphs'].values()))

    def test_writer_failure_preserves_completed_siblings(self):
        run, host = self.run_fixture()
        host.fail_pid = 'p2'
        with self.assertRaisesRegex(p.ParagraphError, 'writer failed'):
            run.write(host, host.observe, max_workers=2)
        self.assertEqual(run.state['paragraphs']['p1']['status'], 'drafted')
        self.assertEqual(run.state['paragraphs']['p2']['status'], 'assigned')
        self.assertIsNotNone(run.state['paragraphs']['p2']['assignment'])
        host.fail_pid = None
        self.assertEqual(run.write(host, host.observe), ['p2'])

    def test_boolean_review_cannot_replace_evidence(self):
        run, host = self.run_fixture(count=1)
        run.write(host, host.observe)
        host.override = lambda task, value: {'passed': True, 'binding': task['payload']['binding']}
        result = run.review('p1', host, host.observe)
        self.assertFalse(result['result']['passed'])

    def test_blueprint_requires_full_argument_graph(self):
        blueprint, _, sources = fixture()
        blueprint['argument_structure'] = {'question': blueprint['central_question']}
        with self.assertRaisesRegex(p.ParagraphError, 'argument is invalid'):
            p.seal_blueprint(blueprint, sources)

    def test_single_paragraph_uses_one_atomic_root(self):
        run, _ = self.run_fixture(count=1)
        graph = run.state['blueprint']['argument_structure']
        self.assertEqual(len(graph['nodes']), 1)
        self.assertEqual(graph['nodes'][0]['inference_form'], 'atomic')
        self.assertEqual(run.state['paragraphs']['p1']['spec']['proposition_order'], ['n1'])

    def test_specification_argument_fields_must_match_graph(self):
        blueprint, specifications, sources = fixture()
        specifications[0]['local_question'] = 'A different local question'
        with self.assertRaisesRegex(p.ParagraphError, 'argument fields differ'):
            p.validate_specification(specifications[0], blueprint, sources)

    def test_graph_source_change_blocks_assignment_until_adoption(self):
        run, host = self.run_fixture(count=1)
        sources = copy.deepcopy(run.state['sources'])
        sources['s1']['text'] += ' A further source sentence.'
        sources['s1']['sha256'] = p.sha(sources['s1']['text'])
        run.update_sources(sources)
        with self.assertRaisesRegex(p.ParagraphError, 'argument semantic review failed'):
            run.write(host, host.observe)

    def test_argument_comparison_failure_blocks_manuscript(self):
        run, host = self.run_fixture(count=1)
        run.write(host, host.observe)
        run.review('p1', host, host.observe)
        run.integrate_section('introduction', host, host.observe)
        host.argument_fail = True
        result = run.integrate_manuscript(host, host.observe)
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['argument_comparison']['valid'])
        with self.assertRaisesRegex(p.ParagraphError, 'global integration missing'):
            run.packet()

    def test_packet_rechecks_actual_host_event_identity(self):
        run, host = self.run_fixture(count=1)
        packet = self.finish(run, host)
        self.assertTrue(p.validate_packet(packet, run.state['manuscript']['text'], observe=host.observe)['valid'])
        writer = packet['paragraphs']['p1']['writer']
        host.events[writer['event_id']]['worker_id'] = 'different-live-worker'
        result = p.validate_packet(packet, run.state['manuscript']['text'], observe=host.observe)
        self.assertFalse(result['valid'])
        self.assertIn('actor or assignment', result['issues'][0])

    def test_packet_rejects_writer_return_tampering(self):
        run, host = self.run_fixture(count=1)
        packet = self.finish(run, host)
        writer = packet['paragraphs']['p1']['writer']
        original = json.loads(writer['return_text'])
        original['text'] = 'Different returned bytes.'
        writer['return_text'] = json.dumps(original)
        writer['return_sha256'] = p.sha(writer['return_text'])
        packet['packet_sha256'] = p.content_hash({k: v for k, v in packet.items() if k != 'packet_sha256'})
        self.assertFalse(p.validate_packet(packet, run.state['manuscript']['text'])['valid'])

    def test_argument_update_preserves_existing_text(self):
        run, host = self.run_fixture(count=1)
        self.finish(run, host)
        original_text = run.state['paragraphs']['p1']['text']
        blueprint = copy.deepcopy(run.state['blueprint'])
        blueprint['version'] = blueprint['argument_structure']['version'] = '2'
        blueprint['argument_structure']['nodes'][0]['reasoning'] += ' The adopted unit is the region.'
        specification = copy.deepcopy(run.state['paragraphs']['p1']['spec'])
        specification['blueprint_version'] = '2'
        specification.update(p._argument_io().paragraph_argument(blueprint['argument_structure'], 'n1'))
        self.assertEqual(run.update_blueprint(blueprint, [specification]), ['p1'])
        self.assertEqual(run.state['paragraphs']['p1']['text'], original_text)
        self.assertIsNone(run.state['paragraphs']['p1']['review'])
        self.assertIsNone(run.state['argument_review'])

    def test_compact_packet_preserves_exact_host_originals(self):
        run, host = self.run_fixture(count=1)
        full = self.finish(run, host)
        compact = p.compact_packet(full)
        self.assertEqual(p.unpack_packet(compact), full)
        self.assertLess(len(p.canonical(compact)), len(p.canonical(full)))
        checked = p.validate_packet(compact, run.state['manuscript']['text'], observe=host.observe)
        self.assertTrue(checked['valid'], checked['issues'])
        self.assertEqual(compact['rules'], full['rules'])

    def test_compact_packet_rejects_modified_original_blob(self):
        run, host = self.run_fixture(count=1)
        compact = p.compact_packet(self.finish(run, host))
        blob = next(iter(compact['execution_blobs'].values()))
        blob['uncompressed_bytes'] += 1
        compact['packet_sha256'] = p.content_hash({k: v for k, v in compact.items() if k != 'packet_sha256'})
        checked = p.validate_packet(compact, run.state['manuscript']['text'])
        self.assertFalse(checked['valid'])

    def test_assignment_recovery_uses_original_without_regeneration(self):
        run, host = self.run_fixture(count=1)
        run.review_argument(host, host.observe)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'paragraph-state.json'
            run.save(path)
            task = run.tasks()[0]
            run.assign(task)
            host(task)
            resumed = p.ParagraphRun.load(path)
            calls = len(host.tasks)
            self.assertEqual(resumed.recover_assignments(host, host.observe)['recovered'], ['p1'])
            self.assertEqual(len(host.tasks), calls)
            self.assertEqual(resumed.state['paragraphs']['p1']['status'], 'drafted')

    def test_full_execution_resumes_completed_work(self):
        run, host = self.run_fixture(count=1)
        result = p.execute_operation(run, 'full', host, host.observe)
        self.assertEqual(result['status'], 'integrated')
        calls = len(host.tasks)
        self.assertEqual(p.execute_operation(run, 'full', host, host.observe)['status'], 'integrated')
        self.assertEqual(len(host.tasks), calls)

    def test_updated_specification_cannot_duplicate_another_owner(self):
        run, _ = self.run_fixture()
        spec = copy.deepcopy(run.state['paragraphs']['p2']['spec'])
        spec['required_content'][0]['proposition_id'] = 'n1'
        spec['completion']['mandatory_claims'] = ['n1']
        with self.assertRaisesRegex(p.ParagraphError, 'multiple paragraph owners|proposition order differs'):
            run.update_specification(spec)


if __name__ == '__main__':
    unittest.main()
