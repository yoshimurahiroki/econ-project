"""Contract tests using fictional research records and an explicit host test double.

FixtureHost checks callback transport only. Its synthetic events do not establish
actual worker execution, independent review or publication authorization.
"""

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from harness import argument as arg


def sources():
    return arg.source_catalog({
        's1': {'text': 'In period T, outcome A rises by 10 units for group X.', 'origin_id': 'observation-a'},
        's2': {'text': 'In period T, outcome B rises by 20 units for group X.', 'origin_id': 'observation-b'},
    })


def reference(sid='s1'):
    row = sources()[sid]
    return {'source_id': sid, 'source_sha256': row['sha256'], 'start': 0,
            'end': len(row['text']), 'quote': row['text']}


def graph():
    scope = {'population': 'group X', 'period': 'T', 'unit': 'units',
             'denominator': 'group X', 'comparison': 'baseline',
             'conditions': ['fixed measurement'], 'definitions': {'outcome': 'count'}}
    def node(nid, claim, paragraph, sid, position):
        return {'node_id': nid, 'parent_id': 'root', 'child_ids': [], 'claim': claim,
                'question': 'What happens to outcome ' + nid.upper() + '?',
                'next_questions': [], 'logical_role': 'result', 'inference_form': 'atomic',
                'abstraction_level': 1, 'scope': deepcopy(scope),
                'source_refs': [reference(sid)], 'section_id': 'results',
                'paragraph_ids': [paragraph], 'reasoning': '',
                'order': {'basis': 'structure', 'position': position, 'rationale': 'Present A before B.'},
                'proposition': {'subject': 'group X', 'predicate': 'records a rise',
                                'object': 'outcome ' + nid.upper(), 'new_information': claim}}
    a = node('a', 'Outcome A rises by 10 units.', 'pa', 's1', 1)
    b = node('b', 'Outcome B rises by 20 units.', 'pb', 's2', 2)
    answer = 'Both measured outcomes rise for group X in period T.'
    root = {'node_id': 'root', 'parent_id': None, 'child_ids': ['a', 'b'],
            'claim': answer, 'question': 'Which outcomes rise for group X in period T?',
            'next_questions': [{'question': 'Which measurements establish the joint rise?', 'answered_by': ['a', 'b']}],
            'logical_role': 'synthesis', 'inference_form': 'inductive', 'abstraction_level': 0,
            'scope': deepcopy(scope), 'source_refs': [], 'section_id': 'results', 'paragraph_ids': [],
            'reasoning': 'The positive changes for A and B establish a rise in both measured outcomes.',
            'order': {'basis': 'structure', 'position': 0, 'rationale': 'State the joint result before its two measurements.'},
            'integration': {'member_ids': ['a', 'b'], 'common_property': 'positive change',
                            'meaning': 'Both measured outcomes increase in the same population and period.', 'conclusion': answer}}
    return {'schema_version': 1, 'version': '1', 'central_question': root['question'],
            'central_answer': answer, 'root_ids': ['root'], 'nodes': [root, a, b],
            'groups': [{'group_id': 'outcomes', 'parent_id': 'root', 'member_ids': ['a', 'b'],
                        'classification_basis': 'Changes in the two measured outcomes.', 'logical_role': 'result',
                        'inference_form': 'inductive', 'expected_member_ids': ['a', 'b'],
                        'reader_question': 'Which measurements establish the joint rise?',
                        'order': {'basis': 'structure', 'ordered_ids': ['a', 'b'], 'rationale': 'Present A before B.'}}],
            'dependencies': [], 'source_ids': ['s1', 's2'],
            'source_manifest': {k: v['sha256'] for k, v in sources().items()}}


def brief():
    return {'purpose': 'Explain the fictional results', 'reader': 'Research reader',
            'original_request': 'Explain the two recorded changes.', 'authority': 'Use the supplied fictional sources.'}


def selection(g=None):
    g = g or graph()
    return {'central_question': g['central_question'], 'central_answer': g['central_answer'],
            'selected_source_ids': ['s1', 's2'],
            'selection_reasons': {'s1': 'Measures outcome A.', 's2': 'Measures outcome B.'}}


def semantic_checks(g, verdict='pass', findings=None):
    failed = {row['check_id'] for row in findings or []}
    return [{'check_id': key, 'verdict': 'fail' if key in failed else verdict,
             'assessment': 'Inspected the declared propositions against the two fictional records.',
             'node_ids': [n['node_id'] for n in g['nodes']], 'source_refs': [reference('s1'), reference('s2')]}
            for key in arg.SEMANTIC_CHECKS]


def finding(check='parent_support', node_ids=None, fid='f1'):
    return {'finding_id': fid, 'check_id': check, 'node_ids': node_ids or ['root'],
            'message': 'The upper claim exceeds the two supplied measurements.',
            'repair': 'State the joint rise in the two measured outcomes.', 'cause_level': 'inference'}


class FixtureHost:
    """Synthetic host transport for unit tests; never used as release evidence."""
    def __init__(self, outputs, *, kind='single-agent-sequential', worker='fixture-worker'):
        self.outputs = deepcopy(outputs)
        self.kind, self.worker = kind, worker
        self.calls, self.events = [], {}

    def __call__(self, task):
        self.calls.append(deepcopy(task))
        operation = task['operation'].split('.')[-1]
        output = self.outputs[operation]
        if isinstance(output, list):
            output = output.pop(0)
        event_id = 'fixture-event-' + str(len(self.calls))
        original = json.dumps(output, ensure_ascii=False)
        row = {'worker_id': self.worker, 'event_id': event_id, 'input_sha256': task['input_sha256'],
               'return_text': original, 'execution_kind': self.kind}
        ref = 'launch_ref' if self.kind == 'independent-subagent' else 'turn_ref'
        row[ref] = 'fixture-' + ref + '-' + str(len(self.calls))
        self.events[event_id] = {'worker_id': self.worker, 'input_sha256': task['input_sha256'],
                                 'return_sha256': arg.sha256(original), 'status': 'completed',
                                 'execution_kind': self.kind, ref: row[ref]}
        if ref == 'launch_ref':
            self.events[row[ref]] = {'worker_id': self.worker, 'input_sha256': task['input_sha256'],
                                     'status': 'completed', 'execution_kind': self.kind}
        return row

    def observe(self, event_id):
        return deepcopy(self.events.get(event_id))


def review_host(g, findings=None):
    findings = findings or []
    result = {'checks': semantic_checks(g, findings=findings), 'findings': findings}
    return FixtureHost({'review': result, 'compare': result})


def manuscript():
    return [{'paragraph_id': 'pa', 'section_id': 'results', 'text': 'Outcome A rises by 10 units.'},
            {'paragraph_id': 'pb', 'section_id': 'results', 'text': 'Outcome B rises by 20 units.'}]


def outline_output():
    parts = manuscript()
    return {'paragraphs': [{'paragraph_id': p['paragraph_id'], 'section_id': p['section_id'],
                             'central_claim': p['text'], 'role': 'result',
                             'text_spans': [{'start': 0, 'end': len(p['text']), 'quote': p['text']}]}
                            for p in parts],
            'sections': [{'section_id': 'results', 'claim': graph()['central_answer'], 'paragraph_ids': ['pa', 'pb']}],
            'central_question': graph()['central_question'], 'central_answer': graph()['central_answer']}


def problem():
    return {'system': 'Fictional service', 'initial_state': 'Uniform waiting time', 'change': 'Service rule changed',
            'current_result': {'object': 'waiting time', 'period': 'T', 'measure': 10, 'criterion': 'minutes'},
            'target_result': {'object': 'waiting time', 'period': 'T', 'measure': 5, 'criterion': 'minutes'},
            'gap': {'value': 5, 'unit': 'minutes'}, 'previous_actions': [], 'question': 'Why did waiting time change?',
            'question_type': 'mechanism',
            'relationships': [{'relation_id': 'r1', 'from': 'service capacity', 'to': 'waiting time', 'relation': 'capacity changes delay'}],
            'mechanisms': [
                {'mechanism_id': 'm1', 'claim': 'Added capacity reduces the queue.', 'object': 'waiting time',
                 'conditions': ['same demand'], 'predictions': ['fewer queued users']},
                {'mechanism_id': 'm2', 'claim': 'Routing changes recorded delay.', 'object': 'waiting time',
                 'conditions': ['same demand'], 'predictions': ['unchanged queued users']}],
            'comparisons': [{'mechanism_ids': ['m1', 'm2'], 'contrast': 'Queue length response',
                             'design': 'Compare counts before and after the rule.', 'evidence_ids': ['s1'],
                             'predictions': {'m1': 'queue falls', 'm2': 'queue stays'}}],
            'verification_plan': [{'test_id': 'queue', 'question': 'Does capacity change the queue?',
                                   'relation_ids': ['r1'], 'mechanism_ids': ['m1', 'm2'], 'evidence_ids': ['s1'],
                                   'comparison': 'Before versus after.', 'acceptance_condition': 'Queue counts follow the measured change.'}]}


class ArgumentRequirementTests(unittest.TestCase):
    def assert_issue(self, g, check, catalog=None):
        result = arg.validate_argument(g, catalog or sources())
        self.assertFalse(result['valid'])
        self.assertIn(check, {row['check_id'] for row in result['issues']})

    def test_01_top_down_builds_source_bound_hierarchy(self):
        host = FixtureHost({'select': selection(), 'decompose': {'graph': graph()}})
        result = arg.generate_argument(brief(), sources(), host)
        self.assertTrue(arg.validate_argument(result, sources())['valid'])
        self.assertEqual([x['operation'] for x in host.calls], ['argument.select', 'argument.decompose'])
        self.assertTrue(all(arg.PRIMARY_RULE in x['instruction_context']['text'] and arg.JAPANESE_RULE in x['instruction_context']['text'] for x in host.calls))

    def test_02_bottom_up_separates_classification_and_derivation(self):
        g = graph()
        atomic = deepcopy(g['nodes'][1:])
        for row in atomic:
            row['parent_id'] = None
        host = FixtureHost({'select': selection(), 'extract': {'propositions': atomic},
                            'classify': {'groups': g['groups']}, 'derive': {'node': g['nodes'][0]}})
        result = arg.generate_argument(brief(), sources(), host, direction='bottom-up')
        self.assertTrue(arg.validate_argument(result, sources())['valid'])
        self.assertEqual([x['operation'] for x in host.calls], ['argument.select', 'argument.extract', 'argument.classify', 'argument.derive'])

    def test_03_parent_restatement_is_detected(self):
        g = graph(); g['nodes'][1]['claim'] = g['central_answer']
        self.assert_issue(g, 'restatement')

    def test_04_unsupported_parent_fails_semantic_review(self):
        g = graph(); findings = [finding()]
        result = arg.review_argument(g, sources(), review_host(g, findings))
        self.assertFalse(result['valid']); self.assertFalse(result['release_authorized'])

    def test_05_hierarchy_and_dependency_cycles_are_detected(self):
        g = graph(); g['nodes'][1]['child_ids'] = ['root']
        self.assert_issue(g, 'hierarchy_cycle')
        g = graph(); g['dependencies'] = [{'from': 'a', 'to': 'b', 'relation': 'prerequisite'}, {'from': 'b', 'to': 'a', 'relation': 'prerequisite'}]
        self.assert_issue(g, 'dependency_cycle')

    def test_06_homogeneous_siblings_pass(self):
        self.assertTrue(arg.validate_argument(graph(), sources())['valid'])

    def test_07_mixed_roles_and_abstraction_are_detected(self):
        g = graph(); g['nodes'][2]['logical_role'] = 'cause'
        self.assert_issue(g, 'mixed_roles')
        g = graph(); g['nodes'][2]['abstraction_level'] = 2
        self.assert_issue(g, 'abstraction')

    def test_08_group_overlap_and_missing_components_are_detected(self):
        g = graph(); g['groups'][0]['member_ids'] = ['a', 'a', 'b']
        self.assert_issue(g, 'group_overlap')
        g = graph(); g['groups'][0]['member_ids'] = ['a']
        self.assert_issue(g, 'group_coverage')

    def test_09_empty_summary_repair_is_attributed(self):
        g = graph(); g['nodes'][0]['claim'] = g['central_answer'] = '主な要因は三つある'
        g['nodes'][0]['integration']['conclusion'] = g['central_answer']
        self.assert_issue(g, 'empty_summary')
        fixed = graph(); fixed['version'] = '2'
        host = FixtureHost({'repair': {'graph': fixed, 'changes': [{'node_id': 'root', 'finding_id': 'f1', 'reason': 'Replace the item count with the observed joint outcome.'}]}})
        result = arg.repair_argument(g, [finding()], sources(), host)
        self.assertEqual(result['graph']['central_answer'], fixed['central_answer'])
        self.assertIn('pa', result['affected_paragraph_ids'])

    def test_10_action_group_uses_joint_outcome(self):
        g = graph()
        for row in g['nodes'][1:]: row['logical_role'] = 'action'
        g['groups'][0]['logical_role'] = 'action'
        g['nodes'][0]['integration']['meaning'] = 'The two actions produce aligned measurement records.'
        result = arg.review_argument(g, sources(), review_host(g))
        self.assertTrue(result['valid'])
        task = arg.make_task('derive', {'group': g['groups'][0]})
        self.assertIn('directly achieved joint outcome', task['instruction_context']['operation_instruction'])

    def test_11_deduction_preserves_conditions_and_premises(self):
        g = graph(); root = g['nodes'][0]
        root['inference_form'] = g['groups'][0]['inference_form'] = 'deductive'
        root['inference'] = {'premise_ids': ['a', 'b'], 'conclusion_id': 'root', 'conditions': ['fixed measurement'],
                             'steps': [{'step_id': 'joint', 'premise_ids': ['a', 'b'], 'claim': root['claim'], 'relation': 'conjunction of the two measured changes'}]}
        self.assertTrue(arg.validate_argument(g, sources())['valid'])
        root['inference']['conditions'] = []
        self.assert_issue(g, 'deduction_conditions')

    def test_12_induction_requires_common_property_and_supported_meaning(self):
        g = graph(); g['nodes'][0]['integration']['meaning'] = ''
        self.assert_issue(g, 'induction')

    def test_13_missing_intermediate_premise_is_detected(self):
        g = graph(); root = g['nodes'][0]
        root['inference_form'] = g['groups'][0]['inference_form'] = 'deductive'
        root['inference'] = {'premise_ids': ['a', 'b'], 'conclusion_id': 'root', 'conditions': ['fixed measurement'],
                             'steps': [{'step_id': 'joint', 'premise_ids': ['absent'], 'claim': root['claim'], 'relation': 'implication'}]}
        self.assert_issue(g, 'missing_intermediate')

    def test_14_causal_claim_requires_admitted_identification_evidence(self):
        g = graph(); g['nodes'][1]['relationship_type'] = 'causal'
        self.assert_issue(g, 'causal_status')

    def test_15_introduction_connects_situation_problem_question_answer(self):
        g = graph(); intro = {'shared_situation': 'Two outcomes are measured.', 'complication': 'Their response must be explained.',
                              'question': g['central_question'], 'answer': g['central_answer'], 'body_node_ids': ['a', 'b']}
        result = arg.build_introduction(intro['shared_situation'], intro['complication'], g, sources(), FixtureHost({'introduction': {'introduction': intro}}))
        self.assertEqual(result['introduction'], intro)

    def test_16_question_and_answer_match_root(self):
        g = graph(); g['central_answer'] = 'A different claim.'
        self.assert_issue(g, 'central_answer')

    def test_17_reader_questions_cover_every_child(self):
        g = graph(); g['nodes'][0]['next_questions'][0]['answered_by'] = ['a']
        self.assert_issue(g, 'reader_questions')

    def test_18_selection_requires_reason_for_each_retained_source(self):
        chosen = selection(); chosen['selection_reasons'].pop('s2')
        with self.assertRaises(arg.ArgumentError):
            arg.generate_argument(brief(), sources(), FixtureHost({'select': chosen}))

    def test_19_problem_has_current_target_gap_and_system(self):
        self.assertEqual(arg.validate_problem(problem()), [])
        value = problem(); value.pop('gap')
        self.assertIn('Problem definition lacks gap', arg.validate_problem(value))

    def test_20_competing_mechanisms_require_different_predictions(self):
        value = problem(); value['comparisons'][0]['predictions']['m2'] = 'queue falls'
        self.assertIn('Competing mechanisms require a comparison of their differing predictions', arg.validate_problem(value))

    def test_21_problem_derives_tests_from_named_structure(self):
        value = problem()
        result = arg.analyze_problem(value, sources(), FixtureHost({'problem': {'problem': value}}))
        self.assertEqual(result['problem']['verification_plan'][0]['relation_ids'], ['r1'])
        value['verification_plan'][0]['relation_ids'] = ['absent']
        self.assertTrue(arg.validate_problem(value))

    def test_22_integrated_paragraphs_match_argument(self):
        g = graph(); outline = arg.reverse_outline(manuscript(), FixtureHost({'reverse': outline_output()}))
        result = arg.compare_outline(g, outline, sources(), review_host(g))
        self.assertTrue(result['valid']); self.assertTrue(result['paragraph_coverage'])

    def test_23_cross_paragraph_duplicate_or_missing_explanation_fails(self):
        g = graph(); g['nodes'][2]['claim'] = g['nodes'][1]['claim']
        self.assert_issue(g, 'duplicate_claim')
        g = graph(); result = arg.review_argument(g, sources(), review_host(g, [finding('inference_completeness')]))
        self.assertFalse(result['valid'])

    def test_24_reverse_outline_is_bound_to_completed_text(self):
        output = outline_output(); output['paragraphs'][0]['text_spans'][0]['quote'] = 'Invented quote.'
        with self.assertRaises(arg.ArgumentError):
            arg.reverse_outline(manuscript(), FixtureHost({'reverse': output}))

    def test_25_bidirectional_comparison_reports_manuscript_mismatch(self):
        g = graph(); outline = arg.reverse_outline(manuscript(), FixtureHost({'reverse': outline_output()}))
        result = arg.compare_outline(g, outline, sources(), review_host(g, [finding('reverse_alignment', ['a'])]))
        self.assertFalse(result['valid']); self.assertEqual(result['findings'][0]['node_ids'], ['a'])

    def test_26_changed_claim_invalidates_dependents(self):
        g = graph(); g['dependencies'] = [{'from': 'a', 'to': 'b', 'relation': 'uses the first measurement'}]
        affected = arg.affected_nodes(g, ['a'])
        self.assertEqual(affected['affected_node_ids'], ['a', 'b', 'root'])
        self.assertEqual(affected['affected_paragraph_ids'], ['pa', 'pb'])


class ArgumentRegressionTests(unittest.TestCase):
    def test_bottom_up_reduces_two_frontiers(self):
        g = graph(); catalog = sources()
        catalog.update(arg.source_catalog({
            's3': {'text': 'In period T, outcome C rises by 30 units for group X.'},
            's4': {'text': 'In period T, outcome D rises by 40 units for group X.'}}))
        leaves = deepcopy(g['nodes'][1:])
        for nid, sid, amount in [('c', 's3', 30), ('d', 's4', 40)]:
            row = deepcopy(leaves[0])
            row.update(node_id=nid, paragraph_ids=['p' + nid], claim='Outcome ' + nid.upper() + ' rises by ' + str(amount) + ' units.')
            row['order']['position'] = 3 if nid == 'c' else 4
            row['source_refs'] = [{'source_id': sid, 'source_sha256': catalog[sid]['sha256'],
                                   'start': 0, 'end': len(catalog[sid]['text']), 'quote': catalog[sid]['text']}]
            leaves.append(row)
        for row in leaves:
            row['parent_id'] = None
        parents, groups = [], []
        for nid, members, position in [('ab', ['a', 'b'], 1), ('cd', ['c', 'd'], 2), ('all', ['ab', 'cd'], 0)]:
            row = deepcopy(g['nodes'][0]); row.update(node_id=nid, child_ids=members)
            row['claim'] = 'The measured outcomes in group ' + nid.upper() + ' rise.'
            row['question'] = 'What happens to the measured outcomes in group ' + nid.upper() + '?'
            row['next_questions'][0]['answered_by'] = members
            row['integration'].update(member_ids=members, conclusion=row['claim'])
            row['order']['position'] = position
            parent_group = deepcopy(g['groups'][0]); parent_group.update(group_id=nid, parent_id=nid, member_ids=members,
                                                                         expected_member_ids=members)
            parent_group['order']['ordered_ids'] = members
            if nid == 'all':
                parent_group['logical_role'] = 'synthesis'
            parents.append(row); groups.append(parent_group)
        chosen = {'central_question': parents[-1]['question'], 'central_answer': parents[-1]['claim'],
                  'selected_source_ids': list(catalog), 'selection_reasons': {sid: 'Reports the selected measured outcome.' for sid in catalog}}
        host = FixtureHost({'select': chosen, 'extract': {'propositions': leaves},
                            'classify': [{'groups': groups[:2]}, {'groups': groups[2:]}],
                            'derive': [{'node': row} for row in parents]})
        result = arg.generate_argument(brief(), catalog, host, direction='bottom-up')
        self.assertEqual(len(result['nodes']), 7)
        self.assertEqual(max(n['abstraction_level'] for n in result['nodes']), 2)
        self.assertEqual(sum(t['operation'] == 'argument.classify' for t in host.calls), 2)

    def test_each_semantic_check_covers_its_required_nodes(self):
        g = graph(); checks = semantic_checks(g)
        next(c for c in checks if c['check_id'] == 'source_correspondence')['node_ids'] = ['a']
        with self.assertRaisesRegex(arg.ArgumentError, 'omits required propositions: source_correspondence'):
            arg.review_argument(g, sources(), FixtureHost({'review': {'checks': checks, 'findings': []}}))

    def test_review_task_exposes_complete_per_check_scope(self):
        g = graph(); host = review_host(g)
        arg.review_argument(g, sources(), host)
        required = host.calls[0]['payload']['required_node_ids']
        self.assertEqual(required['source_correspondence'], ['a', 'b', 'root'])
        self.assertEqual(required['parent_support'], ['root'])

    def test_quantity_cannot_use_source_outside_adopted_manifest(self):
        g = graph(); catalog = sources()
        catalog['extra'] = deepcopy(catalog['s1'])
        ref = reference(); ref['source_id'] = 'extra'
        g['nodes'][1]['quantities'] = [{'value': 10, 'unit': 'units', 'period': 'T',
                                       'denominator': 'group X', 'comparison': 'baseline', 'source_ref': ref}]
        result = arg.validate_argument(g, catalog)
        self.assertIn('quantity', {x['check_id'] for x in result['issues']})

    def test_positive_quantity_cannot_match_negative_source_value(self):
        g = graph(); catalog = sources()
        catalog['s1']['text'] = catalog['s1']['text'].replace('10', '-10')
        catalog['s1']['sha256'] = arg.sha256(catalog['s1']['text'])
        ref = {'source_id': 's1', 'source_sha256': catalog['s1']['sha256'], 'start': 0,
               'end': len(catalog['s1']['text']), 'quote': catalog['s1']['text']}
        g['source_manifest']['s1'] = catalog['s1']['sha256']
        g['nodes'][1]['source_refs'] = [ref]
        g['nodes'][1]['quantities'] = [{'value': 10, 'unit': 'units', 'period': 'T',
                                       'denominator': 'group X', 'comparison': 'baseline', 'source_ref': ref}]
        self.assertIn('quantity', {x['check_id'] for x in arg.validate_argument(g, catalog)['issues']})

    def test_causal_basis_requires_admitted_source(self):
        g = graph(); catalog = sources(); catalog['extra'] = deepcopy(catalog['s1'])
        ref = reference(); ref['source_id'] = 'extra'
        g['nodes'][1].update(relationship_type='causal', causal_basis=[ref])
        self.assertIn('causal_status', {x['check_id'] for x in arg.validate_argument(g, catalog)['issues']})

    def test_group_sequence_matches_hierarchy_and_node_positions(self):
        g = graph(); g['nodes'][0]['child_ids'] = ['b', 'a']
        self.assertIn('group_order', {x['check_id'] for x in arg.validate_argument(g, sources())['issues']})
        g = graph(); g['nodes'][2]['order']['position'] = 1
        self.assertIn('group_order', {x['check_id'] for x in arg.validate_argument(g, sources())['issues']})

    def test_inference_step_ids_are_distinct_and_use_every_premise(self):
        g = graph(); root = g['nodes'][0]
        root['inference_form'] = g['groups'][0]['inference_form'] = 'deductive'
        root['inference'] = {'premise_ids': ['a', 'b'], 'conclusion_id': 'root', 'conditions': ['fixed measurement'],
                             'steps': [{'step_id': 'a', 'premise_ids': ['a'], 'claim': root['claim'], 'relation': 'implication'}]}
        messages = [x['message'] for x in arg.validate_argument(g, sources())['issues']]
        self.assertIn('Inference step ID repeats a premise or earlier step', messages)
        self.assertIn('Deduction leaves an adopted premise unused', messages)

    def test_reverse_outline_rejects_duplicate_sections(self):
        value = outline_output(); value['sections'] *= 2
        with self.assertRaisesRegex(arg.ArgumentError, 'every section'):
            arg.reverse_outline(manuscript(), FixtureHost({'reverse': value}))

    def test_reverse_outline_rejects_repeated_paragraph_members(self):
        value = outline_output(); value['sections'][0]['paragraph_ids'] = ['pa', 'pa', 'pb']
        with self.assertRaisesRegex(arg.ArgumentError, 'complete paragraph set'):
            arg.reverse_outline(manuscript(), FixtureHost({'reverse': value}))

    def test_reverse_outline_rejects_empty_manuscript_before_callback(self):
        host = FixtureHost({})
        with self.assertRaises(arg.ArgumentError):
            arg.reverse_outline('   ', host)
        self.assertEqual(host.calls, [])

    def test_atomic_paragraph_retains_its_own_proposition(self):
        self.assertEqual(arg.paragraph_argument(graph(), 'a')['proposition_order'], ['a'])

    def test_dependency_consumer_invalidates_its_supporting_subtree(self):
        g = graph(); root, a, b = g['nodes']
        c = deepcopy(b); c.update(node_id='c', parent_id='b', child_ids=[], paragraph_ids=['pc'])
        b['child_ids'] = ['c']; g['nodes'].append(c)
        g['dependencies'] = [{'from': 'a', 'to': 'b', 'relation': 'supports the consumer conclusion'}]
        result = arg.affected_nodes(g, ['a'])
        self.assertEqual(result['affected_node_ids'], ['a', 'b', 'c', 'root'])
        self.assertEqual(result['affected_paragraph_ids'], ['pa', 'pb', 'pc'])

    def test_compare_requires_current_structural_validity(self):
        g = graph(); g['nodes'][2]['logical_role'] = 'cause'
        outline = arg.reverse_outline(manuscript(), FixtureHost({'reverse': outline_output()}))
        result = arg.compare_outline(g, outline, sources(), review_host(g))
        self.assertFalse(result['valid']); self.assertFalse(result['structural']['valid'])

    def test_metric_rates_retain_numerator_and_denominator(self):
        g = graph(); findings = [finding('reader_questions')]
        review = arg.review_argument(g, sources(), review_host(g, findings))
        result = arg.metrics(g, review, repair_count=1)
        self.assertEqual(result['reader_question_alignment'], 0.0)
        self.assertEqual(result['coverage_counts']['reader_questions'], {'passed': 0, 'required': 1})
        self.assertEqual(result['grouping_fit'], 1.0)

    def test_comparison_requires_identical_research_inputs(self):
        g = graph(); values = arg.metrics(g, arg.review_argument(g, sources(), review_host(g)))
        inputs = {'material_sha256': 'materials', 'question': g['central_question'],
                  'results_sha256': 'results', 'conditions_sha256': 'writing conditions'}
        compared = arg.compare_metrics(values, values, inputs, deepcopy(inputs))
        self.assertEqual(compared['measures']['grouping_fit']['change'], 0.0)
        changed = deepcopy(inputs); changed['results_sha256'] = 'other results'
        with self.assertRaises(arg.ArgumentError):
            arg.compare_metrics(values, values, inputs, changed)


if __name__ == '__main__':
    unittest.main()
