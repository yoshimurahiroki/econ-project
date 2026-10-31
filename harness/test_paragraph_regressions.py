"""Paragraph workflow regressions using explicitly synthetic host event doubles.

FixtureHost exercises the callback protocol and state transitions.  Its records
are unit-test inputs; they do not establish an independent model execution.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('paragraph_test_engine', ROOT / 'harness/paragraph.py')
paragraph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(paragraph)


def span(text, quote=None):
    quote = text if quote is None else quote
    start = text.index(quote)
    return {'start': start, 'end': start + len(quote), 'quote': quote}


def fixture(language='en', operation='econ-writing:compose', *, dependencies=False,
            execution_kind='independent-subagent', editable_ids=None):
    """Create fixed fictional source material and complete paragraph contracts."""
    texts = (['標本には処置地域が40地域ある。', '標本には比較地域が60地域ある。']
             if language == 'ja' else
             ['The sample contains 40 treated sites.', 'The sample contains 60 comparison sites.'])
    sources = paragraph.normalize_sources({
        's1': {'text': texts[0], 'origin_id': 'fixture-treated', 'path': 'source-one.txt'},
        's2': {'text': texts[1], 'origin_id': 'fixture-comparison', 'path': 'source-two.txt'},
        'context': {'text': 'Each site is one administrative unit.', 'origin_id': 'fixture-definitions', 'path': 'context.txt'},
    })
    rules = {
        'policy_id': 'unit-fixture',
        'texts': {key: (ROOT / path).read_text(encoding='utf-8') for key, path in {
            'CORE': 'runtime/CORE.md', 'PROSE': 'runtime/PROSE.md',
            'econ-writing': 'skills/econ-writing/SKILL.md', 'prose-guide': 'quality/prose_rules.md',
        }.items()},
        'dictionary': json.loads((ROOT / 'quality/prose_rules.json').read_text(encoding='utf-8')),
        'profile': {'name': 'fixture', 'language': language},
    }
    question = 'Which sites form the fictional sample?'
    answer = 'The fictional sample includes treated and comparison sites.'
    scope = {'population': 'fictional sample', 'period': 'fixture period', 'unit': 'site',
             'denominator': 'included sites', 'comparison': 'treatment status',
             'conditions': [], 'definitions': {'site': 'administrative unit'}}
    refs = {sid: {'source_id': sid, 'source_sha256': sources[sid]['sha256'], **span(sources[sid]['text'])}
            for sid in ('s1', 's2')}
    nodes = []
    for index, (nid, pid, sid) in enumerate((('a', 'pa', 's1'), ('b', 'pb', 's2')), start=1):
        nodes.append({'node_id': nid, 'parent_id': 'root', 'child_ids': [],
                      'claim': sources[sid]['text'], 'question': 'Which ' + nid + ' sites are included?',
                      'next_questions': [], 'logical_role': 'sample_component', 'inference_form': 'atomic',
                      'abstraction_level': 1, 'scope': copy.deepcopy(scope), 'source_refs': [refs[sid]],
                      'section_id': 'introduction', 'paragraph_ids': [pid],
                      'reasoning': 'The source reports the count for this sample component.',
                      'order': {'basis': 'structure', 'position': index, 'rationale': 'Declare treated sites before the comparison.'}})
    root = {'node_id': 'root', 'parent_id': None, 'child_ids': ['a', 'b'], 'claim': answer,
            'question': question, 'next_questions': [{'question': 'Which components form the sample?', 'answered_by': ['a', 'b']}],
            'logical_role': 'sample_composition', 'inference_form': 'inductive', 'abstraction_level': 0,
            'scope': copy.deepcopy(scope), 'source_refs': [], 'section_id': 'introduction', 'paragraph_ids': [],
            'reasoning': 'The two source counts identify the treatment groups that compose the sample.',
            'order': {'basis': 'structure', 'position': 0, 'rationale': 'State the composition before describing each component.'},
            'integration': {'member_ids': ['a', 'b'], 'common_property': 'membership in the fictional sample',
                            'meaning': 'Both treatment groups have included sites.', 'conclusion': answer}}
    graph = {'schema_version': 1, 'version': 'fixture-1', 'central_question': question, 'central_answer': answer,
             'root_ids': ['root'], 'nodes': [root] + nodes,
             'groups': [{'group_id': 'components', 'parent_id': 'root', 'member_ids': ['a', 'b'],
                         'expected_member_ids': ['a', 'b'], 'classification_basis': 'treatment status',
                         'logical_role': 'sample_component', 'inference_form': 'inductive',
                         'order': {'basis': 'structure', 'ordered_ids': ['a', 'b'], 'rationale': 'Describe treated sites, then comparison sites.'}}],
             'dependencies': [], 'source_ids': ['s1', 's2'],
             'source_manifest': {sid: sources[sid]['sha256'] for sid in ('s1', 's2')}}
    blueprint = paragraph.seal_blueprint({
        'schema_version': 1, 'version': 'fixture-1', 'purpose': 'Describe the fictional study sample.',
        'reader': 'Researcher', 'central_question': question, 'central_answer': answer,
        'contribution': 'State the counts used by the comparison.', 'completion_conditions': ['Both counts have exact sources.'],
        'argument_structure': graph, 'sections': [{'section_id': 'introduction', 'role': 'Define the study sample.', 'claim': answer}],
        'paragraphs': [{'paragraph_id': n['paragraph_ids'][0], 'section_id': 'introduction',
                        'central_proposition': n['claim'], 'role': 'Describe one sample component.',
                        'depends_on': ['pa'] if dependencies and n['node_id'] == 'b' else [],
                        'source_ids': [n['source_refs'][0]['source_id']], 'scope': copy.deepcopy(scope)} for n in nodes],
        'definitions': scope['definitions'], 'quantities': ['40', '60'], 'conditions': [],
        'writing_rules': ['One sample component per paragraph.'],
        'prohibited_rules': [paragraph.PRIMARY_RULE, paragraph.JAPANESE_RULE],
    }, sources)
    specs = []
    argument = paragraph._argument_io()
    for index, n in enumerate(nodes):
        pid, sid = n['paragraph_ids'][0], n['source_refs'][0]['source_id']
        spec = {'paragraph_id': pid, 'section_id': 'introduction', 'blueprint_version': blueprint['version'],
                'role': {'purpose': 'Describe this sample component.', 'contribution_to_global_argument': 'Identify one of the study groups.'},
                'central_proposition': {'claim': n['claim'], 'logical_status': 'source-observation'},
                'required_content': [{'proposition_id': n['node_id'], 'exact_content': n['claim'], 'source_id': sid,
                                      'source_location': span(sources[sid]['text']), 'evidence_type': 'source-observation',
                                      'required_reasoning': n['reasoning']}],
                'logical_structure': {'opening': n['claim'], 'development': n['reasoning'], 'mechanism': '', 'implication': ''},
                'relationships': {'preceding_paragraph': None if index == 0 else 'pa', 'inherited_information': 'Definition of the sample.',
                                  'following_paragraph': 'pb' if index == 0 else None, 'information_to_pass_forward': 'The included site count.'},
                'terminology': {'adopted_definitions': scope['definitions'], 'fixed_quantities': [str(40 if index == 0 else 60)], 'required_terms': []},
                'scope': {'included': [n['claim']], 'excluded': ['Other research findings.'], 'content_change_authority': 'Retain the fictional source counts.'},
                'writing': {'language': language, 'profile': rules['profile'], 'paragraph_rules': ['One central claim.'],
                            'prohibited_functions': ['Unsupported additions.'],
                            'instruction_packet': paragraph.instruction_packet('Describe the supplied fictional sample.', rules),
                            'source_references': [sid]},
                'completion': {'mandatory_claims': [n['node_id']], 'evidence_correspondence': 'Exact source span.',
                               'logical_coherence': 'Name the sample component and its count.', 'prose_compliance': 'Apply all current rules.',
                               'local_review': 'Pass the complete local review.'},
                **argument.paragraph_argument(graph, n['node_id'])}
        specs.append(spec)
    originals = dict(zip(('pa', 'pb'), texts)) if operation in ('econ-writing:revise', 'econ-writing:translate', 'econ-writing:convert') else {}
    kwargs = {'run_id': 'unit-fixture', 'request': 'Describe the supplied fictional sample.', 'authority': 'Use fictional source records.',
              'author_id': 'fixture-author', 'operation': operation, 'blueprint': blueprint, 'specifications': specs,
              'sources': sources, 'rules': rules, 'execution_kind': execution_kind,
              'original_paragraphs': originals, 'editable_ids': editable_ids}
    return kwargs


class FixtureHost:
    """Deterministic protocol test double; never used as model-run evidence."""

    def __init__(self, inputs, *, fail_global=False, drafts=None):
        self.inputs = inputs
        self.events = {}
        self.calls = []
        self.sequence = 0
        self.lock = threading.Lock()
        self.fail_global = fail_global
        self.drafts = drafts or {}
        self.interrupt_once = None
        self.pending = {}
        self.completed = {}

    def observe(self, event_id):
        return copy.deepcopy(self.events.get(event_id))

    def recover(self, task):
        key = task['input_sha256']
        if key in self.completed:
            returned = self.completed[key]
            return {'event_id': returned['event_id'], 'status': 'completed', 'returned': returned}
        return {'event_id': self.pending[key], 'status': 'running'}

    def __call__(self, task):
        with self.lock:
            self.sequence += 1
            n = self.sequence
            self.calls.append(copy.deepcopy(task))
        operation, payload = task['operation'], task['payload']
        kind = self.inputs['execution_kind']
        worker = 'fixture-' + operation + '-' + str(n) if kind == 'independent-subagent' else 'fixture-author'
        event_id, ref = 'fixture-return-' + str(n), 'fixture-start-' + str(n)
        ref_key = 'launch_ref' if kind == 'independent-subagent' else 'turn_ref'
        event = {'worker_id': worker, 'input_sha256': task['input_sha256'], 'execution_kind': kind, 'status': 'running', ref_key: ref}
        self.events[ref] = copy.deepcopy(event)
        if self.interrupt_once == operation:
            self.interrupt_once = None
            self.events[event_id] = copy.deepcopy(event)
            self.pending[task['input_sha256']] = event_id
            self.pending['task'] = copy.deepcopy(task)
            raise ConnectionError('fixture transport interrupted after launch')
        result = self.output(task)
        raw = json.dumps(result, ensure_ascii=False, sort_keys=True)
        event.update(status='completed', return_sha256=paragraph.sha(raw))
        self.events[event_id] = event
        returned = {'worker_id': worker, 'event_id': event_id, 'input_sha256': task['input_sha256'],
                    'return_text': raw, 'execution_kind': kind, ref_key: ref}
        self.completed[task['input_sha256']] = returned
        return returned

    def complete_interrupted(self):
        task = self.pending['task']
        key = task['input_sha256']
        event_id = self.pending[key]
        event = self.events[event_id]
        raw = json.dumps(self.output(task), ensure_ascii=False, sort_keys=True)
        event.update(status='completed', return_sha256=paragraph.sha(raw))
        ref_key = 'launch_ref' if event['execution_kind'] == 'independent-subagent' else 'turn_ref'
        returned = {'worker_id': event['worker_id'], 'event_id': event_id, 'input_sha256': key,
                    'return_text': raw, 'execution_kind': event['execution_kind'], ref_key: event[ref_key]}
        self.completed[key] = returned
        return returned

    def output(self, task):
        operation, payload = task['operation'], task['payload']
        if operation == 'writing:architect':
            return {'blueprint': copy.deepcopy(self.inputs['blueprint'])}
        if operation == 'writing:specify':
            return {'specifications': copy.deepcopy(self.inputs['specifications'])}
        if operation in ('argument.review', 'argument.compare'):
            refs = [copy.deepcopy(n['source_refs'][0]) for n in payload['graph']['nodes'] if n['source_refs']]
            failing = operation == 'argument.compare' and self.fail_global
            checks = [{'check_id': cid, 'verdict': 'fail' if failing and cid == 'reverse_alignment' else 'pass',
                       'assessment': 'Fixture assessment covers the declared proposition set.',
                       'node_ids': payload['required_node_ids'][cid], 'source_refs': refs} for cid in payload['required_checks']]
            findings = ([{'finding_id': 'fixture-global-conflict', 'check_id': 'reverse_alignment', 'node_ids': ['a', 'b'],
                          'cause_level': 'global', 'message': 'Fixture manuscript contradicts its adopted comparison.',
                          'repair': 'Regenerate the conflicting paragraph from the adopted comparison.'}] if failing else [])
            return {'checks': checks, 'findings': findings}
        if operation == 'argument.reverse':
            paragraphs = payload['manuscript']
            return {'paragraphs': [{'paragraph_id': p['paragraph_id'], 'central_claim': p['text'],
                                    'role': 'Describe one sample component.', 'section_id': p['section_id'],
                                    'text_spans': [span(p['text'])]} for p in paragraphs],
                    'sections': [{'section_id': 'introduction', 'claim': self.inputs['blueprint']['central_answer'],
                                  'paragraph_ids': [p['paragraph_id'] for p in paragraphs]}],
                    'central_question': self.inputs['blueprint']['central_question'],
                    'central_answer': self.inputs['blueprint']['central_answer']}
        if operation == 'writing:paragraph':
            spec = payload['specification']
            pid = spec['paragraph_id']
            return {'paragraph_id': pid, 'text': self.drafts.get(pid, spec['central_proposition']['claim']),
                    'binding': payload['binding'], 'read_instruction_sha256': paragraph.content_hash(task['instruction_context'])}
        if operation == 'writing:paragraph-review':
            return local_review(payload)
        if operation in ('writing:section-integrate', 'writing:manuscript-integrate'):
            text = '\n\n'.join(payload['paragraphs'].values())
            result = {'paragraphs': payload['paragraphs'], 'paragraph_hashes': payload['paragraph_hashes'], 'text': text,
                      'checks': [{'check_id': cid, 'verdict': 'pass', 'assessment': 'Fixture integration preserves the exact paragraph map.',
                                  'spans': [span(text)]} for cid in payload['required_checks']], 'findings': []}
            if operation == 'writing:manuscript-integrate':
                result['outline_comparison'] = [{'paragraph_id': pid, 'assessment': 'Fixture paragraph matches its declared role.',
                                                 'spec_sha256': paragraph.content_hash(spec),
                                                 'outline_sha256': paragraph.content_hash(payload['reverse_outline']), 'verdict': 'pass'}
                                                for pid, spec in payload['specifications'].items()]
            return result
        raise AssertionError('Unexpected fixture operation: ' + operation)


def local_review(payload):
    text, spec, sources = payload['text'], payload['specification'], payload['sources']
    claims, reasoning, missing = [], [], []
    for required in spec['required_content']:
        pid, sid = required['proposition_id'], required['source_id']
        if required['exact_content'] not in text:
            missing.append(pid)
            continue
        target = span(text, required['exact_content'])
        claims.append({'proposition_id': pid, 'assessment': 'The fictional source passage is reproduced.',
                       'source_id': sid, 'source_sha256': sources[sid]['sha256'], 'target': target,
                       'source': required['source_location']})
        reasoning.append({'proposition_id': pid, 'assessment': 'The count identifies the sample component.',
                          'required_reasoning': required['required_reasoning'], 'target': target})
    quantities = []
    for match in paragraph.QUANTITY.finditer(text):
        quote = match.group()
        admitted = {r['source_id'] for r in spec['required_content']} | set(spec['writing']['source_references'])
        source_id = next((sid for sid in admitted if quote in sources[sid]['text']), spec['required_content'][0]['source_id'])
        original = sources[source_id]['text']
        original_match = next(paragraph.QUANTITY.finditer(original))
        source_span = span(original, quote) if quote in original else span(original, original_match.group())
        quantities.append({'source_id': source_id, 'source_sha256': sources[source_id]['sha256'],
                           'assessment': 'The displayed count matches the fixed source.',
                           'target': {'start': match.start(), 'end': match.end(), 'quote': quote}, 'source': source_span})
    hits = payload['lexical_hits']
    findings = []
    if missing:
        findings.append({'check_id': 'mandatory-content', 'problem': 'A mandatory fixture claim is absent.',
                         'repair': 'Restore the specified claim.', 'span': span(text)})
    if hits:
        findings.append({'check_id': 'prose-compliance', 'problem': 'The fixture includes a prohibited expression.',
                         'repair': 'Remove the expression.', 'span': span(text)})
    failed = {f['check_id'] for f in findings}
    return {'paragraph_id': spec['paragraph_id'], 'text_sha256': paragraph.sha(text), 'spec_sha256': paragraph.content_hash(spec),
            'binding': payload['binding'],
            'checks': [{'check_id': cid, 'verdict': 'fail' if cid in failed else 'pass',
                        'assessment': 'Fixture local comparison for ' + cid + '.', 'spans': [span(text)]} for cid in paragraph.LOCAL_CHECKS],
            'claim_evidence': claims, 'reasoning': reasoning, 'quantity_evidence': quantities,
            'occurrence_judgments': [{'rule_id': hit['rule_id'], 'start': hit['start'], 'end': hit['end'],
                                     'function': 'Fixture prohibited qualification.', 'meaning': 'Additional unsupported framing.',
                                     'syntax': 'Sentence modifier.', 'proposition': spec['central_proposition']['claim'],
                                     'verdict': 'violation', 'text_sha256': paragraph.sha(text)} for hit in hits],
            'findings': findings, 'missing_claims': missing, 'missing_reasoning': missing}


class ParagraphWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.inputs = fixture()

    def complete(self, inputs=None, **host_options):
        inputs = inputs or self.inputs
        run = paragraph.ParagraphRun.create(**inputs)
        host = FixtureHost(inputs, **host_options)
        result = paragraph.execute_operation(run, 'full', host, host.observe, max_workers=2)
        return run, host, result

    def test_japanese_multi_paragraph_introduction(self):
        run, host, result = self.complete(fixture('ja'))
        self.assertEqual(result['status'], 'integrated')
        checked = paragraph.validate_packet(run.packet(), result['text'], observe=host.observe)
        self.assertTrue(checked['valid'], checked['issues'])

    def test_english_multi_paragraph_introduction(self):
        run, host, result = self.complete()
        self.assertEqual(result['status'], 'integrated')
        checked = paragraph.validate_packet(run.packet(), result['text'], observe=host.observe)
        self.assertTrue(checked['valid'], checked['issues'])

    def test_results_numbers_and_table_preserve_source_correspondence(self):
        table = '\n| Group | Sites |\n| --- | --- |\n| Treated | 40 |'
        run, host, result = self.complete(drafts={'pa': self.inputs['sources']['s1']['text'] + table})
        self.assertIn('| Treated | 40 |', result['text'])
        review = json.loads(run.state['paragraphs']['pa']['review']['record']['return_text'])
        self.assertEqual([q['target']['quote'] for q in review['quantity_evidence']], ['40', '40'])
        modified = copy.deepcopy(review)
        modified['quantity_evidence'][0]['source']['quote'] = '60'
        with self.assertRaises(paragraph.ParagraphError):
            paragraph.validate_local_review(modified, run.state['paragraphs']['pa']['spec'],
                                            run.state['paragraphs']['pa']['text'], run.state['sources'], [])

    def test_signed_estimate_and_results_table_have_exact_numeric_evidence(self):
        claim = 'The estimated effect is -0.25 points.'
        sources = paragraph.normalize_sources({'estimate': {'text': claim}})
        spec = copy.deepcopy(self.inputs['specifications'][0])
        spec['central_proposition']['claim'] = claim
        required = spec['required_content'][0]
        required.update(exact_content=claim, source_id='estimate', source_location=span(claim),
                        required_reasoning='The signed coefficient reports the treatment comparison in points.')
        spec['writing']['source_references'] = ['estimate']
        spec['terminology']['fixed_quantities'] = ['-0.25']
        text = claim + '\n| Estimand | Estimate |\n| --- | --- |\n| Treatment effect | -0.25 |'
        payload = {'text': text, 'specification': spec, 'sources': sources, 'binding': {'fixture': 'estimate'}, 'lexical_hits': []}
        review = local_review(payload)
        checked = paragraph.validate_local_review(review, spec, text, sources, [])
        self.assertTrue(checked['passed'])
        self.assertEqual([q['target']['quote'] for q in review['quantity_evidence']], ['-0.25', '-0.25'])

    def test_scoped_revision_retains_other_paragraph_bytes(self):
        inputs = fixture(operation='econ-writing:revise', editable_ids=['pa'])
        run, host, result = self.complete(inputs)
        self.assertEqual(result['status'], 'integrated')
        self.assertEqual(run.state['paragraphs']['pb']['text'], inputs['original_paragraphs']['pb'])
        written = [t['payload']['specification']['paragraph_id'] for t in host.calls if t['operation'] == 'writing:paragraph']
        self.assertEqual(written, ['pa'])

    def test_cross_paragraph_conflict_blocks_manuscript(self):
        run, host, result = self.complete(fail_global=True)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['findings'][0]['check_id'], 'reverse_alignment')
        self.assertIsNone(run.state['manuscript'])

    def test_missing_mandatory_claim_fails_local_review(self):
        run, host, result = self.complete(drafts={'pa': 'The source describes the study sample.'})
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(run.state['paragraphs']['pa']['review']['result']['passed'])

    def test_duplicate_proposition_ownership_is_rejected(self):
        inputs = copy.deepcopy(self.inputs)
        inputs['specifications'][1]['required_content'][0]['proposition_id'] = 'a'
        inputs['specifications'][1]['completion']['mandatory_claims'] = ['a']
        with self.assertRaises(paragraph.ParagraphError):
            paragraph.ParagraphRun.create(**inputs)

    def test_prohibited_expression_is_reported_and_repaired(self):
        inputs = self.inputs
        run = paragraph.ParagraphRun.create(**inputs)
        host = FixtureHost(inputs, drafts={'pa': inputs['sources']['s1']['text'] + ' It is worth noting that this is important.'})
        result = paragraph.execute_operation(run, 'full', host, host.observe)
        self.assertEqual(result['status'], 'failed')
        self.assertGreater(run.state['paragraphs']['pa']['review']['result']['lexical_hits'], 0)
        host.drafts.clear()
        repaired = run.repair('pa', host, host.observe)
        self.assertTrue(repaired['result']['passed'])
        self.assertEqual(run.state['paragraphs']['pa']['repair_count'], 1)

    def test_source_reference_update_invalidates_its_consumers(self):
        inputs = copy.deepcopy(self.inputs)
        inputs['specifications'][0]['writing']['source_references'].append('context')
        run, host, result = self.complete(inputs)
        unaffected = copy.deepcopy(run.state['paragraphs']['pb']['review'])
        updated = copy.deepcopy(run.state['sources'])
        updated['context']['text'] += ' Definitions are versioned.'
        updated['context'].pop('sha256')
        self.assertEqual(run.update_sources(updated), ['pa'])
        self.assertIsNone(run.state['paragraphs']['pa']['review'])
        self.assertEqual(run.state['paragraphs']['pb']['review'], unaffected)
        self.assertFalse(run.state['sections'])
        self.assertIsNone(run.state['manuscript'])

    def test_blueprint_source_update_invalidates_its_consumers(self):
        inputs = copy.deepcopy(self.inputs)
        inputs['blueprint']['paragraphs'][0]['source_ids'].append('context')
        run, host, result = self.complete(inputs)
        updated = copy.deepcopy(run.state['sources'])
        updated['context']['text'] += ' Context changes.'
        updated['context'].pop('sha256')
        self.assertEqual(run.update_sources(updated), ['pa'])

    def test_unchanged_sources_reuse_completed_records(self):
        run, host, result = self.complete()
        before = copy.deepcopy(run.state['sections'])
        self.assertEqual(run.update_sources(copy.deepcopy(run.state['sources'])), [])
        self.assertEqual(run.state['sections'], before)

    def test_resume_reuses_current_completed_reviews(self):
        run, host, result = self.complete()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.json'
            run.save(path)
            restored = paragraph.ParagraphRun.load(path)
            count = len(host.calls)
            after = paragraph.execute_operation(restored, 'full', host, host.observe)
            self.assertEqual(after['text'], result['text'])
            self.assertEqual(len(host.calls), count)

    def test_chat_sequential_execution_is_labeled_and_serial(self):
        run, host, result = self.complete(fixture(execution_kind='single-agent-sequential'))
        self.assertEqual(result['status'], 'integrated')
        for row in run.state['paragraphs'].values():
            self.assertEqual(row['writer']['execution_kind'], 'single-agent-sequential')
            self.assertNotIn('launch_ref', row['writer'])
        self.assertFalse(run.packet()['release_authorized'])

    def test_local_pass_keeps_independent_release_unfulfilled(self):
        run, host, result = self.complete()
        checked = paragraph.validate_packet(run.packet(), result['text'], observe=host.observe)
        self.assertFalse(checked['release_authorized'])
        self.assertEqual(checked['required_final_roles'], ['quality-a', 'quality-b', 'compliance'])
        self.assertEqual(len(checked['required_final_prose_checks']), 22)

    def test_missing_native_independent_role_is_rejected(self):
        run, host, result = self.complete()
        receipt = {'event_id': 'fixture-native', 'candidate_sha256': result['sha256'], 'return_sha256': 'fixture-hash'}
        event = {**receipt, 'status': 'completed', 'review_plan': 'strict-reviewed', 'roles': ['quality-a'], 'decision': 'passed'}
        with self.assertRaises(paragraph.ParagraphError):
            run.record_global_review(receipt, lambda _: event)

    def test_all_five_modes_execute_the_same_contract_path(self):
        for mode in paragraph.OPERATIONS:
            with self.subTest(mode=mode):
                run, host, result = self.complete(fixture(operation=mode))
                self.assertEqual(result['status'], 'integrated')
                checked = paragraph.validate_packet(run.packet(), result['text'], observe=host.observe)
                self.assertTrue(checked['valid'], checked['issues'])

    def test_single_paragraph_uses_one_complete_contract(self):
        inputs = copy.deepcopy(self.inputs)
        graph = inputs['blueprint']['argument_structure']
        node = copy.deepcopy(graph['nodes'][1])
        node.update(parent_id=None, abstraction_level=0)
        graph.update(root_ids=['a'], nodes=[node], groups=[], source_ids=['s1'],
                     source_manifest={'s1': inputs['sources']['s1']['sha256']},
                     central_question=node['question'], central_answer=node['claim'])
        blueprint = inputs['blueprint']
        blueprint.update(central_question=node['question'], central_answer=node['claim'],
                         paragraphs=blueprint['paragraphs'][:1])
        blueprint['sections'][0]['claim'] = node['claim']
        spec = inputs['specifications'][0]
        spec.update(paragraph._argument_io().paragraph_argument(graph, 'a'))
        spec['relationships']['following_paragraph'] = None
        inputs['specifications'] = [spec]
        run, host, result = self.complete(inputs)
        self.assertEqual(len(run.state['paragraphs']), 1)
        checked = paragraph.validate_packet(run.packet(), result['text'], observe=host.observe)
        self.assertTrue(checked['valid'], checked['issues'])

    def test_architect_and_designer_returns_are_observed(self):
        inputs = self.inputs
        host = FixtureHost(inputs)
        brief = {'original_request': inputs['request'], 'authority': inputs['authority'],
                 'purpose': inputs['blueprint']['purpose'], 'reader': inputs['blueprint']['reader']}
        design = paragraph.generate_blueprint(brief, inputs['sources'], inputs['rules'], host, host.observe, author_id=inputs['author_id'])
        contracts = paragraph.generate_specifications(design['blueprint'], inputs['sources'], inputs['rules'], host, host.observe,
                                                       request=inputs['request'], authority=inputs['authority'], author_id=inputs['author_id'])
        self.assertEqual([s['paragraph_id'] for s in contracts['specifications']], ['pa', 'pb'])
        self.assertEqual(design['execution']['host_observation']['status'], 'completed')

    def test_revised_predecessor_is_completed_before_consumer_assignment(self):
        inputs = fixture(operation='econ-writing:revise', dependencies=True)
        run = paragraph.ParagraphRun.create(**inputs)
        self.assertEqual([t['payload']['specification']['paragraph_id'] for t in run.tasks()], ['pa'])
        host = FixtureHost(inputs)
        run.write(host, host.observe, max_workers=2)
        written = [t['payload']['specification']['paragraph_id'] for t in host.calls if t['operation'] == 'writing:paragraph']
        self.assertEqual(written, ['pa', 'pb'])

    def test_transport_interruption_retains_assignment_and_recovers_original(self):
        inputs = fixture(dependencies=True)
        run = paragraph.ParagraphRun.create(**inputs)
        host = FixtureHost(inputs)
        host.interrupt_once = 'writing:paragraph'
        with self.assertRaises(paragraph.ParagraphError):
            run.write(host, host.observe)
        self.assertEqual(run.state['paragraphs']['pa']['status'], 'assigned')
        assignment = copy.deepcopy(run.state['paragraphs']['pa']['assignment'])
        self.assertEqual(run.recover_assignments(host, host.observe)['running'], ['pa'])
        host.complete_interrupted()
        self.assertEqual(run.recover_assignments(host, host.observe)['recovered'], ['pa'])
        self.assertEqual(run.state['paragraphs']['pa']['writer']['input_sha256'], assignment['input_sha256'])
        run.write(host, host.observe)
        calls = [t for t in host.calls if t['operation'] == 'writing:paragraph' and t['payload']['specification']['paragraph_id'] == 'pa']
        self.assertEqual(len(calls), 1)

    def test_japanese_quantity_requires_explicit_evidence(self):
        inputs = fixture('ja')
        run, host, result = self.complete(inputs)
        review = json.loads(run.state['paragraphs']['pa']['review']['record']['return_text'])
        self.assertEqual([q['target']['quote'] for q in review['quantity_evidence']], ['40'])
        review['quantity_evidence'] = []
        with self.assertRaises(paragraph.ParagraphError):
            paragraph.validate_local_review(review, run.state['paragraphs']['pa']['spec'], run.state['paragraphs']['pa']['text'], run.state['sources'], [])

    def test_dependency_update_alias_preserves_existing_entry(self):
        run = paragraph.ParagraphRun.create(**self.inputs)
        with patch.object(run, 'change_dependencies', return_value=['pa', 'pb']) as update:
            self.assertEqual(run.update_dependencies('pb', ['pa']), ['pa', 'pb'])
            update.assert_called_once_with('pb', ['pa'])

    def test_changed_specification_invalidates_dependency_descendants(self):
        inputs = fixture(dependencies=True)
        run, host, result = self.complete(inputs)
        spec = copy.deepcopy(run.state['paragraphs']['pa']['spec'])
        spec['role']['purpose'] = 'Define the treated component before its comparison.'
        self.assertEqual(run.update_specification(spec), ['pa', 'pb'])
        self.assertIsNone(run.state['paragraphs']['pb']['review'])

    def test_state_and_packet_hash_tampering_is_rejected(self):
        run, host, result = self.complete()
        packet = run.packet()
        packet['paragraphs']['pa']['text'] = 'Changed text.'
        self.assertFalse(paragraph.validate_packet(packet, result['text'])['valid'])

    def test_compacted_packet_restores_exact_original_execution_records(self):
        run, host, result = self.complete()
        packet = run.packet(compact=False)
        compact = paragraph.compact_packet(packet)
        self.assertEqual(paragraph.unpack_packet(compact), packet)
        checked = paragraph.validate_packet(compact, result['text'], observe=host.observe)
        self.assertTrue(checked['valid'], checked['issues'])


if __name__ == '__main__':
    unittest.main()
