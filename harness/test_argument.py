"""Offline argument-contract regressions. FixtureHost is a synthetic test double."""
import contextlib
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location('argument_engine', Path(__file__).with_name('argument.py'))
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


class FixtureHost:
    """Exercise callback binding without claiming an actual agent execution."""
    def __init__(self, outputs, kind='independent-subagent'):
        self.outputs, self.kind = outputs, kind
        self.tasks, self.events = [], {}

    def __call__(self, task):
        self.tasks.append(deepcopy(task))
        operation = task['operation'].split('.')[-1]
        output = self.outputs[operation]
        if callable(output):
            output = output(deepcopy(task['payload']))
        text = json.dumps(output, ensure_ascii=False)
        count = len(self.tasks)
        worker = 'fixture-worker-' + operation
        event = 'fixture-return-' + str(count)
        ref_key = 'launch_ref' if self.kind == 'independent-subagent' else 'turn_ref'
        ref = 'fixture-' + ref_key + '-' + str(count)
        result = {'worker_id': worker, 'event_id': event, 'input_sha256': task['input_sha256'],
                  'return_text': text, 'execution_kind': self.kind, ref_key: ref}
        self.events[event] = {'worker_id': worker, 'input_sha256': task['input_sha256'],
            'return_sha256': a.sha256(text), 'status': 'completed', 'execution_kind': self.kind, ref_key: ref}
        self.events[ref] = {'worker_id': worker, 'input_sha256': task['input_sha256'],
                            'status': 'completed', 'execution_kind': self.kind}
        return result

    def observe(self, event_id):
        return deepcopy(self.events.get(event_id))


def sources():
    return a.source_catalog({
        's1': {'text': '2024年のA地域では取り締まり変更後の違反率が30から20へ下がった。', 'origin_id': 'A-observations', 'location': 'table A'},
        's2': {'text': '2024年のB地域では取り締まり変更後の違反率が40から25へ下がった。', 'origin_id': 'B-observations', 'location': 'table B'},
    })


def ref(sid, catalog=None):
    catalog = catalog or sources()
    row = catalog[sid]
    return {'source_id': sid, 'source_sha256': row['sha256'], 'start': 0,
            'end': len(row['text']), 'quote': row['text']}


def graph_fixture():
    catalog = sources()
    scope = {'population': '二地域の記録', 'period': '2024', 'unit': 'percent',
             'denominator': 'observed events', 'comparison': 'before-after', 'conditions': [], 'definitions': {}}
    def node(nid, parent, claim, question, position, sid=None):
        return {'node_id': nid, 'parent_id': parent, 'child_ids': [], 'claim': claim,
                'question': question, 'next_questions': [], 'logical_role': 'observed-result',
                'inference_form': 'atomic', 'abstraction_level': 1 if parent else 0,
                'scope': deepcopy(scope), 'source_refs': [ref(sid, catalog)] if sid else [],
                'section_id': 'results', 'paragraph_ids': ['p' + str(position)], 'reasoning': '',
                'order': {'basis': 'structure', 'position': position, 'rationale': '対象地域の定義順に記述する。'},
                'proposition': {'subject': nid, 'predicate': '低下した', 'object': '違反率', 'new_information': claim}}
    root = node('root', None, '両地域で違反率が低下した。', '二つの地域の違反率はどう変化したか。', 0)
    root.update(child_ids=['a', 'b'], inference_form='inductive', logical_role='integrated-result',
        reasoning='A地域とB地域の双方で変更後の違反率が変更前を下回るため、二地域に共通する低下を示す。',
        next_questions=[{'question': '地域別の違反率はどう変化したか。', 'answered_by': ['a', 'b']}],
        integration={'member_ids': ['a', 'b'], 'common_property': '同一年の変更前後で違反率が低下した。',
                     'meaning': '低下は二つの地域に共通する。', 'conclusion': '両地域で違反率が低下した。'})
    leaves = [node('a', 'root', catalog['s1']['text'], 'A地域の違反率はどう変化したか。', 1, 's1'),
              node('b', 'root', catalog['s2']['text'], 'B地域の違反率はどう変化したか。', 2, 's2')]
    group = {'group_id': 'g1', 'parent_id': 'root', 'member_ids': ['a', 'b'],
             'classification_basis': '同一年の地域別の違反率の変化', 'logical_role': 'observed-result',
             'inference_form': 'inductive', 'reader_question': '地域ごとにどう変化したか。',
             'order': {'basis': 'structure', 'ordered_ids': ['a', 'b'], 'rationale': 'A地域、B地域の順に比較する。'}}
    return {'schema_version': 1, 'version': '1', 'central_question': root['question'],
            'central_answer': root['claim'], 'root_ids': ['root'], 'nodes': [root, *leaves],
            'groups': [group], 'dependencies': [], 'source_ids': list(catalog),
            'source_manifest': {sid: row['sha256'] for sid, row in catalog.items()}}


def brief_fixture():
    return {'purpose': '地域別結果を説明する。', 'reader': '研究論文の読者',
            'original_request': '与えられた二地域の違反率の変化を記述してください。',
            'authority': {'content_change': 'adopted-materials-only'},
            'completion_conditions': ['二地域の変化と共通結果を示す。']}


def selection_fixture(graph=None, ids=None):
    graph = graph or graph_fixture()
    ids = ids or graph['source_ids']
    return {'central_question': graph['central_question'], 'central_answer': graph['central_answer'],
            'selected_source_ids': ids, 'selection_reasons': {sid: '地域別結果が中心的な回答を支える。' for sid in ids}}


def review_fixture(graph=None, failures=None):
    graph = graph or graph_fixture()
    failures = failures or {}
    checks, findings = [], []
    for check in a.SEMANTIC_CHECKS:
        checks.append({'check_id': check, 'verdict': 'fail' if check in failures else 'pass',
            'assessment': '二地域の原文、親命題と地域別命題、対応する問い、定義、順序を照合した。',
            'node_ids': [n['node_id'] for n in graph['nodes']], 'source_refs': [ref('s1'), ref('s2')]})
        if check in failures:
            findings.append({'finding_id': 'f-' + check, 'check_id': check, 'node_ids': failures[check],
                'cause_level': 'inference', 'message': 'この親命題は指定された地域別結果と一致しない。',
                'repair': '地域別結果が共同で示す命題へ書き換える。'})
    return {'checks': checks, 'findings': findings}


def manuscript_fixture(graph=None):
    graph = graph or graph_fixture()
    return [{'paragraph_id': n['paragraph_ids'][0], 'section_id': n['section_id'], 'text': n['claim']}
            for n in graph['nodes']]


def reverse_fixture(manuscript=None, graph=None):
    graph = graph or graph_fixture()
    manuscript = manuscript or manuscript_fixture(graph)
    return {'central_question': graph['central_question'], 'central_answer': graph['central_answer'],
            'paragraphs': [{'paragraph_id': p['paragraph_id'], 'section_id': p['section_id'],
                'central_claim': p['text'], 'role': 'result',
                'text_spans': [{'start': 0, 'end': len(p['text']), 'quote': p['text']}]} for p in manuscript],
            'sections': [{'section_id': 'results', 'claim': graph['central_answer'],
                          'paragraph_ids': [p['paragraph_id'] for p in manuscript]}]}


def problem_fixture():
    return {'system': '二地域の違反行動', 'initial_state': '変更前の取り締まり',
        'change': '取り締まり手続の変更',
        'current_result': {'object': '二地域', 'period': '2024', 'measure': '違反率', 'criterion': '変更前後の差'},
        'target_result': {'object': '二地域', 'period': '2024', 'measure': '違反率', 'criterion': '地域共通の低下'},
        'gap': '地域共通の低下がどの機序に対応するか。', 'previous_actions': [],
        'question': '違反率の低下は監視頻度と罰金のどちらの変更に対応するか。', 'question_type': 'mechanism',
        'relationships': [{'relation_id': 'r1', 'from': '監視頻度', 'to': '違反行動', 'relation': '発見される確率を変える。'},
                          {'relation_id': 'r2', 'from': '罰金', 'to': '違反行動', 'relation': '発見後の支払額を変える。'}],
        'mechanisms': [{'mechanism_id': 'm1', 'claim': '監視頻度の変更が行動を変える。', 'object': '二地域',
                        'conditions': ['同一年', '共通の違反定義'], 'predictions': {'監視頻度のみ変更': '低下'}},
                       {'mechanism_id': 'm2', 'claim': '罰金額の変更が行動を変える。', 'object': '二地域',
                        'conditions': ['同一年', '共通の違反定義'], 'predictions': {'監視頻度のみ変更': '変化なし'}}],
        'comparisons': [{'mechanism_ids': ['m1', 'm2'], 'contrast': '罰金固定で監視頻度のみ変えた群を比較する。',
                         'design': '監視変更群と非変更群の変更前後を比較する。', 'evidence_ids': ['s1', 's2'],
                         'predictions': {'m1': '低下', 'm2': '変化なし'}}],
        'verification_plan': [{'test_id': 'v1', 'question': '監視頻度のみの変化に違反率は対応するか。',
            'relation_ids': ['r1'], 'mechanism_ids': ['m1', 'm2'], 'evidence_ids': ['s1', 's2'],
            'comparison': '罰金額を固定して監視変更の有無を比較する。', 'acceptance_condition': '群間差を原資料の定義と一致させる。'}]}


class ArgumentCases(unittest.TestCase):
    def setUp(self):
        self.graph, self.sources = graph_fixture(), sources()

    def codes(self, graph=None):
        return {r['check_id'] for r in a.validate_argument(graph or self.graph, self.sources)['issues']}

    def generate(self, graph=None):
        graph = graph or self.graph
        host = FixtureHost({'select': selection_fixture(graph), 'decompose': {'graph': graph}})
        return a.generate_argument(brief_fixture(), self.sources, host), host

    def test_case_01_constructs_multilevel_top_down_argument(self):
        old_root = self.graph['nodes'][0]
        upper = deepcopy(old_root)
        upper.update(node_id='overall', child_ids=['root'], claim='二地域の比較は低下の共通性を示す。',
            question='地域比較からどの共通結果が得られるか。', paragraph_ids=['p3'],
            next_questions=[{'question': old_root['question'], 'answered_by': ['root']}])
        upper['integration'].update(member_ids=['root'], conclusion=upper['claim'])
        old_root['parent_id'] = 'overall'
        for node in self.graph['nodes']:
            node['abstraction_level'] += 1
        self.graph['nodes'].append(upper)
        self.graph.update(root_ids=['overall'], central_question=upper['question'], central_answer=upper['claim'])
        group = deepcopy(self.graph['groups'][0])
        group.update(group_id='g2', parent_id='overall', member_ids=['root'], logical_role='integrated-result')
        group['order']['ordered_ids'] = ['root']
        self.graph['groups'].append(group)
        result, host = self.generate()
        self.assertEqual(2, max(n['abstraction_level'] for n in result['nodes']))
        self.assertEqual(['argument.select', 'argument.decompose'], [t['operation'] for t in host.tasks])
        self.assertEqual(a.argument_sha256(result), result['argument_sha256'])

    def test_case_02_bottom_up_derives_concrete_parent(self):
        host = FixtureHost({'select': selection_fixture(), 'extract': {'propositions': self.graph['nodes'][1:]},
            'classify': {'groups': self.graph['groups']}, 'derive': {'node': self.graph['nodes'][0]}})
        result = a.generate_argument(brief_fixture(), self.sources, host, direction='bottom-up')
        self.assertEqual(self.graph['central_answer'], result['central_answer'])
        self.assertEqual(['select', 'extract', 'classify', 'derive'], [t['operation'].split('.')[-1] for t in host.tasks])
        self.assertEqual(4, len(result['generation_records']))

    def test_case_03_restatement_of_parent_is_detected(self):
        self.graph['nodes'][1]['claim'] = self.graph['nodes'][0]['claim']
        self.assertIn('restatement', self.codes())

    def test_case_04_unsupported_parent_requires_semantic_review(self):
        root = self.graph['nodes'][0]
        root['claim'] = self.graph['central_answer'] = root['integration']['conclusion'] = '両地域で取り締まり変更が違反率を下げた。'
        self.assertTrue(a.validate_argument(self.graph, self.sources)['valid'])
        host = FixtureHost({'review': review_fixture(self.graph, {'parent_support': ['root']})})
        review = a.review_argument(self.graph, self.sources, host)
        self.assertFalse(review['valid'])
        self.assertFalse(review['release_authorized'])
        self.assertEqual('f-parent_support', review['findings'][0]['finding_id'])

    def test_case_05_reference_dependency_cycle_is_detected(self):
        self.graph['dependencies'] = [{'from': 'a', 'to': 'b', 'relation': 'definition'},
                                      {'from': 'b', 'to': 'a', 'relation': 'definition'}]
        self.assertIn('dependency_cycle', self.codes())
        self.assertNotIn('hierarchy_cycle', self.codes())

    def test_case_06_classification_and_derivation_are_separate_calls(self):
        def derive(payload):
            self.assertEqual(['a', 'b'], payload['group']['member_ids'])
            self.assertEqual('同一年の地域別の違反率の変化', payload['group']['classification_basis'])
            return {'node': self.graph['nodes'][0]}
        host = FixtureHost({'select': selection_fixture(), 'extract': {'propositions': self.graph['nodes'][1:]},
                           'classify': {'groups': self.graph['groups']}, 'derive': derive})
        result = a.generate_argument(brief_fixture(), self.sources, host, direction='bottom-up')
        self.assertTrue(a.validate_argument(result, self.sources)['valid'])
        self.assertNotIn('node', host.tasks[2]['payload'])

    def test_case_07_mixed_roles_and_levels_are_detected(self):
        self.graph['nodes'][2].update(logical_role='cause', abstraction_level=3)
        self.assertTrue({'mixed_roles', 'abstraction'} <= self.codes())

    def test_case_08_overlap_and_omitted_components_are_detected(self):
        for members, expected in [(['a', 'a', 'b'], 'group_overlap'), (['a'], 'group_coverage')]:
            with self.subTest(members=members):
                graph = deepcopy(self.graph)
                graph['groups'][0]['member_ids'] = members
                self.assertIn(expected, self.codes(graph))

    def test_case_09_empty_summary_is_repaired_to_concrete_proposition(self):
        original = deepcopy(self.graph)
        self.graph['central_answer'] = self.graph['nodes'][0]['claim'] = '主な要因は二つある。'
        self.graph['nodes'][0]['integration']['conclusion'] = self.graph['central_answer']
        self.assertIn('empty_summary', self.codes())
        original['version'] = '2'
        finding = {'finding_id': 'f-empty', 'node_ids': ['root'], 'repair': '二地域の共通結果を命題化する。'}
        host = FixtureHost({'repair': {'graph': original, 'changes': [
            {'node_id': 'root', 'finding_id': 'f-empty', 'reason': '地域別結果の共通する低下を示した。'}]}})
        result = a.repair_argument(self.graph, [finding], self.sources, host)
        self.assertEqual('両地域で違反率が低下した。', result['graph']['central_answer'])
        self.assertEqual(['a', 'b', 'root'], result['affected_node_ids'])

    def test_case_10_action_group_derives_joint_achieved_result(self):
        for node, claim in zip(self.graph['nodes'][1:], ['データの識別子を統一する。', '重複する観測を一件へ統合する。']):
            node.update(claim=claim, logical_role='action')
        root = self.graph['nodes'][0]
        root['claim'] = self.graph['central_answer'] = '各観測が一意の識別子で一件ずつ表される。'
        root['integration'].update(conclusion=root['claim'], common_property='観測の識別と一意性を整える。', meaning=root['claim'])
        self.graph['groups'][0]['logical_role'] = 'action'
        self.graph['dependencies'] = [{'from': 'a', 'to': 'b', 'relation': '識別子統一後に重複を判定する。'}]
        self.graph['groups'][0]['order']['basis'] = 'dependency'
        host = FixtureHost({'select': selection_fixture(self.graph), 'extract': {'propositions': self.graph['nodes'][1:]},
            'classify': {'groups': self.graph['groups']}, 'derive': {'node': root}})
        brief = brief_fixture()
        brief['dependencies'] = self.graph['dependencies']
        result = a.generate_argument(brief, self.sources, host, direction='bottom-up')
        self.assertEqual(root['claim'], result['central_answer'])

    def deduction(self):
        root = self.graph['nodes'][0]
        root['inference_form'] = self.graph['groups'][0]['inference_form'] = 'deductive'
        root.pop('integration')
        root['inference'] = {'premise_ids': ['a', 'b'], 'conditions': [], 'conclusion_id': 'root',
            'steps': [{'step_id': 'step1', 'premise_ids': ['a', 'b'], 'claim': root['claim'],
                       'relation': '二地域が対象全集合であり、それぞれの観測が低下を示す。'}]}
        return root

    def test_case_11_deductive_premises_and_conclusion_are_bound(self):
        root = self.deduction()
        self.assertTrue(a.validate_argument(self.graph, self.sources)['valid'])
        root['inference']['steps'][-1]['claim'] = '別の結論'
        self.assertIn('deduction', self.codes())

    def test_case_12_inductive_common_property_is_required(self):
        self.graph['nodes'][0]['integration']['common_property'] = ''
        self.assertIn('induction', self.codes())

    def test_case_13_missing_intermediate_proposition_is_detected(self):
        root = self.deduction()
        root['inference']['steps'][0]['premise_ids'] = ['missing-step']
        self.assertIn('missing_intermediate', self.codes())

    def test_case_14_causal_rewrite_requires_a_causal_basis(self):
        self.graph['nodes'][1]['relationship_type'] = 'causal'
        self.assertIn('causal_status', self.codes())

    def test_case_15_introduction_connects_situation_problem_question(self):
        introduction = {'shared_situation': '二地域が違反率を記録する。', 'complication': '取り締まり手続が変わった。',
            'question': self.graph['central_question'], 'answer': self.graph['central_answer'], 'body_node_ids': ['a', 'b']}
        host = FixtureHost({'introduction': {'introduction': introduction}})
        result = a.build_introduction(introduction['shared_situation'], introduction['complication'], self.graph, self.sources, host)
        self.assertEqual(self.graph['central_question'], result['introduction']['question'])
        self.assertEqual('argument.introduction', result['record']['task']['operation'])

    def test_case_16_central_question_and_answer_match_root(self):
        self.graph['central_question'] = '別の問い'
        self.assertIn('central_answer', self.codes())

    def test_case_17_reader_questions_cover_required_explanations(self):
        self.graph['nodes'][0]['next_questions'][0]['answered_by'] = ['a']
        self.assertIn('reader_questions', self.codes())

    def test_case_18_purpose_selects_needed_sources(self):
        self.sources['s3'] = {'text': '別年の人口統計', 'sha256': a.sha256('別年の人口統計'), 'origin_id': 'population', 'location': 'other'}
        result, host = self.generate()
        self.assertEqual({'s1', 's2'}, set(result['source_ids']))
        self.assertEqual({'s1', 's2'}, set(host.tasks[1]['payload']['sources']))
        self.assertEqual({'s1', 's2'}, set(result['selection']['selection_reasons']))

    def test_case_19_problem_states_target_gap_and_object(self):
        problem = problem_fixture()
        host = FixtureHost({'problem': {'problem': problem}})
        result = a.analyze_problem({'system': problem['system']}, self.sources, host)
        self.assertEqual(problem, result['problem'])
        broken = deepcopy(problem)
        broken['target_result'].pop('measure')
        self.assertTrue(a.validate_problem(broken))

    def test_case_20_competing_mechanisms_have_discriminating_comparison(self):
        problem = problem_fixture()
        self.assertEqual([], a.validate_problem(problem))
        problem['comparisons'][0]['predictions']['m2'] = '低下'
        self.assertIn('Competing mechanisms require a comparison of their differing predictions', a.validate_problem(problem))

    def test_case_21_verification_tasks_follow_problem_relationships(self):
        problem = problem_fixture()
        host = FixtureHost({'problem': {'problem': problem}})
        result = a.analyze_problem({'system': problem['system']}, self.sources, host)
        self.assertEqual(['r1'], result['problem']['verification_plan'][0]['relation_ids'])
        problem['verification_plan'][0]['relation_ids'] = ['unregistered']
        self.assertTrue(a.validate_problem(problem))

    def test_case_22_integrated_paragraphs_receive_global_comparison(self):
        host = FixtureHost({'reverse': reverse_fixture(), 'compare': review_fixture()})
        outline = a.reverse_outline(manuscript_fixture(), host)
        compared = a.compare_outline(self.graph, outline, self.sources, host)
        self.assertTrue(compared['valid'])
        self.assertTrue(compared['paragraph_coverage'])
        self.assertFalse(compared['release_authorized'])

    def test_case_23_global_review_detects_cross_paragraph_defects(self):
        failures = {'grouping': ['a', 'b'], 'information_density': ['a', 'b'], 'inference_completeness': ['root']}
        host = FixtureHost({'review': review_fixture(self.graph, failures)})
        result = a.review_argument(self.graph, self.sources, host, manuscript=manuscript_fixture())
        self.assertEqual(set(failures), {f['check_id'] for f in result['findings']})
        self.assertFalse(result['semantic_pass'])

    def test_case_24_reverse_reconstructs_from_text_alone(self):
        host = FixtureHost({'reverse': reverse_fixture()})
        outline = a.reverse_outline(manuscript_fixture(), host)
        self.assertEqual({'manuscript'}, set(host.tasks[0]['payload']))
        self.assertEqual(self.graph['central_answer'], outline['central_answer'])
        self.assertEqual(a.sha256(manuscript_fixture()), outline['manuscript_sha256'])
        self.assertEqual(3, len(outline['paragraphs']))

    def test_case_25_mismatch_repair_preserves_unaffected_propositions(self):
        revised = deepcopy(self.graph)
        revised['version'] = '2'
        revised['nodes'][1]['reasoning'] = 'A地域の変更前後を原文の順に照合する。'
        finding = {'finding_id': 'f-text', 'node_ids': ['a'], 'repair': 'A地域の説明を補う。'}
        host = FixtureHost({'repair': {'graph': revised, 'changes': [
            {'node_id': 'a', 'finding_id': 'f-text', 'reason': '原文との対応を明示した。'}]}})
        result = a.repair_argument(self.graph, [finding], self.sources, host)
        self.assertEqual(self.graph['nodes'][2], result['graph']['nodes'][2])
        self.assertEqual(['a', 'root'], result['affected_node_ids'])
        self.assertNotEqual(a.argument_sha256(self.graph), result['graph']['argument_sha256'])

    def test_case_26_changed_nodes_invalidate_dependent_paragraphs_and_checks(self):
        self.graph['reviews'] = [{'review_id': 'old-review'}]
        self.graph['dependencies'] = [{'from': 'a', 'to': 'b', 'relation': '比較対象の定義を共有する。'}]
        revised = deepcopy(self.graph)
        revised['version'] = '2'
        revised['nodes'][1]['reasoning'] = 'A地域の比較基準を固定した。'
        finding = {'finding_id': 'f-scope', 'node_ids': ['a'], 'repair': '比較基準を明示する。'}
        host = FixtureHost({'repair': {'graph': revised, 'changes': [
            {'node_id': 'a', 'finding_id': 'f-scope', 'reason': '参照される定義を明示した。'}]}})
        result = a.repair_argument(self.graph, [finding], self.sources, host)
        self.assertEqual(['a', 'b', 'root'], result['affected_node_ids'])
        self.assertEqual(['p0', 'p1', 'p2'], result['affected_paragraph_ids'])
        self.assertEqual([{'review_id': 'old-review'}], result['invalidated_reviews'])
        self.assertNotIn('reviews', result['graph'])

    def test_structural_success_does_not_authorize_release(self):
        checked = a.validate_argument(self.graph, self.sources)
        self.assertTrue(checked['valid'])
        self.assertTrue(checked['semantic_review_required'])
        self.assertFalse(checked['release_authorized'])

    def test_paragraph_spec_has_exact_seven_argument_fields(self):
        fields = a.paragraph_argument(self.graph, 'root')
        self.assertEqual({'argument_node_id', 'parent_proposition', 'local_question', 'supporting_propositions',
                          'inference_form', 'proposition_order', 'logical_completion'}, set(fields))
        self.assertEqual(['a', 'b'], fields['proposition_order'])
        atomic = a.paragraph_argument(self.graph, 'a')
        self.assertEqual(['a'], atomic['proposition_order'])
        self.assertEqual('root', atomic['parent_proposition']['node_id'])

    def test_source_span_and_manifest_modification_are_rejected(self):
        self.graph['nodes'][1]['source_refs'][0]['quote'] = '改変した引用'
        self.graph['source_manifest']['s2'] = '0' * 64
        self.assertTrue({'source_correspondence', 'source_version'} <= self.codes())

    def test_unselected_source_cannot_supply_a_proposition(self):
        self.graph['source_ids'] = ['s1']
        self.graph['source_manifest'].pop('s2')
        self.assertIn('source_correspondence', self.codes())

    def test_shared_origin_cannot_be_counted_as_independent_evidence(self):
        self.sources['s2']['origin_id'] = self.sources['s1']['origin_id']
        self.graph['groups'][0]['evidence_relation'] = 'independent'
        self.assertIn('double_counting', self.codes())

    def test_measurement_and_quantity_must_match_source_and_scope(self):
        self.graph['nodes'][1]['quantities'] = [{'value': 20, 'unit': 'percent', 'period': '2024',
            'denominator': 'observed events', 'comparison': 'before-after', 'source_ref': ref('s1')}]
        self.assertEqual(set(), self.codes())
        self.graph['nodes'][1]['quantities'][0].update(value=200, period='2023')
        self.assertTrue({'quantity', 'quantity_scope'} <= self.codes())

    def test_scope_change_requires_explicit_aggregation(self):
        self.graph['nodes'][1]['scope']['population'] = 'A地域'
        self.assertIn('scope', self.codes())
        self.graph['nodes'][0]['scope_aggregation'] = [{'field': 'population', 'parent_value': '二地域の記録',
            'child_values': ['A地域'], 'reasoning': '対象二地域のうちA地域を分解する。'}]
        self.assertNotIn('scope', self.codes())

    def test_deduction_retains_all_application_conditions(self):
        root = self.deduction()
        for node in self.graph['nodes']:
            node['scope']['conditions'] = ['対象集合が二地域で尽くされる。']
        self.assertIn('deduction_conditions', self.codes())
        root['inference']['conditions'] = root['scope']['conditions']
        self.assertNotIn('deduction_conditions', self.codes())

    def test_hash_change_invalidates_old_argument(self):
        self.graph['argument_sha256'] = a.argument_sha256(self.graph)
        self.graph['nodes'][1]['reasoning'] = '追加の説明'
        self.assertIn('argument_version', self.codes())

    def test_missing_actual_event_observation_is_rejected(self):
        task = a.make_task('review', {})
        host = FixtureHost({'review': review_fixture()})
        result = host(task)
        with self.assertRaises(a.ArgumentError):
            a.accept_host_return(task, result, lambda event: None)

    def test_observed_original_return_hash_must_match(self):
        task = a.make_task('review', {})
        host = FixtureHost({'review': review_fixture()})
        result = host(task)
        result['return_text'] += ' '
        with self.assertRaises(a.ArgumentError):
            a.accept_host_return(task, result, host.observe)

    def test_changed_assignment_and_launch_are_rejected(self):
        task = a.make_task('review', {})
        host = FixtureHost({'review': review_fixture()})
        result = host(task)
        changed = deepcopy(task)
        changed['payload']['added'] = True
        with self.assertRaises(a.ArgumentError):
            a.accept_host_return(changed, result, host.observe)
        host.events[result['launch_ref']]['worker_id'] = 'different-worker'
        with self.assertRaises(a.ArgumentError):
            a.accept_host_return(task, result, host.observe)

    def test_sequential_execution_retains_actual_turn_reference(self):
        host = FixtureHost({'review': review_fixture()}, kind='single-agent-sequential')
        review = a.review_argument(self.graph, self.sources, host)
        self.assertEqual('single-agent-sequential', review['record']['execution_kind'])
        self.assertTrue(review['record']['turn_ref'].startswith('fixture-'))
        self.assertIsNone(review['record']['launch_observation'])

    def test_self_reported_pass_does_not_replace_review(self):
        host = FixtureHost({'review': {'passed': True}})
        with self.assertRaises(a.ArgumentError):
            a.review_argument(self.graph, self.sources, host)

    def test_evidence_checks_require_original_source_ranges(self):
        output = review_fixture()
        output['checks'][0]['source_refs'] = []
        host = FixtureHost({'review': output})
        with self.assertRaises(a.ArgumentError):
            a.review_argument(self.graph, self.sources, host)

    def test_reverse_outline_rejects_fabricated_text_span(self):
        output = reverse_fixture()
        output['paragraphs'][0]['text_spans'][0]['quote'] = '本文にない命題'
        with self.assertRaises(a.ArgumentError):
            a.reverse_outline(manuscript_fixture(), FixtureHost({'reverse': output}))

    def test_outline_edit_invalidates_bidirectional_comparison(self):
        host = FixtureHost({'reverse': reverse_fixture(), 'compare': review_fixture()})
        outline = a.reverse_outline(manuscript_fixture(), host)
        outline['central_answer'] = '別の結論'
        with self.assertRaises(a.ArgumentError):
            a.compare_outline(self.graph, outline, self.sources, host)

    def test_unmapped_and_missing_paragraphs_fail_comparison(self):
        manuscript = manuscript_fixture()[1:]
        host = FixtureHost({'reverse': reverse_fixture(manuscript), 'compare': review_fixture()})
        outline = a.reverse_outline(manuscript, host)
        compared = a.compare_outline(self.graph, outline, self.sources, host)
        self.assertFalse(compared['valid'])
        self.assertEqual(['p0'], host.tasks[-1]['payload']['missing_paragraphs'])

    def test_repair_cannot_change_preserved_sibling(self):
        revised = deepcopy(self.graph)
        revised['version'] = '2'
        revised['nodes'][2]['reasoning'] = '無関係な変更'
        finding = {'finding_id': 'f-a', 'node_ids': ['a'], 'repair': 'A地域を修正する。'}
        host = FixtureHost({'repair': {'graph': revised, 'changes': [{'node_id': 'b', 'finding_id': 'f-a', 'reason': '変更'}]}})
        with self.assertRaises(a.ArgumentError):
            a.repair_argument(self.graph, [finding], self.sources, host)

    def test_repair_attribution_requires_the_actual_finding(self):
        revised = deepcopy(self.graph)
        revised['version'] = '2'
        revised['nodes'][1]['reasoning'] = '変更'
        finding = {'finding_id': 'f-a', 'node_ids': ['a'], 'repair': 'A地域を修正する。'}
        host = FixtureHost({'repair': {'graph': revised, 'changes': [{'node_id': 'a', 'finding_id': 'other', 'reason': '変更'}]}})
        with self.assertRaises(a.ArgumentError):
            a.repair_argument(self.graph, [finding], self.sources, host)

    def test_metrics_compare_identical_material_question_results_conditions(self):
        host = FixtureHost({'review': review_fixture()})
        review = a.review_argument(self.graph, self.sources, host)
        before = a.metrics(self.graph, review, repair_count=2)
        after = a.metrics(self.graph, review, repair_count=1)
        inputs = {'material_sha256': a.sha256(self.sources), 'question': self.graph['central_question'],
                  'results_sha256': a.sha256('adopted results'), 'conditions_sha256': a.sha256(brief_fixture())}
        compared = a.compare_metrics(before, after, inputs, inputs)
        self.assertEqual(-1, compared['measures']['repair_count']['change'])
        changed = {**inputs, 'question': '別の問い'}
        with self.assertRaises(a.ArgumentError):
            a.compare_metrics(before, after, inputs, changed)

    def test_malformed_fields_return_structural_findings(self):
        cases = [({}, 'source_ids'), ({'nodes': [{}]}, 'nodes'),
                 ({'root_ids': [{}]}, 'root_ids'), ({'groups': [None]}, 'groups'),
                 ({'dependencies': [{'from': []}]}, 'dependencies')]
        for patch, label in cases:
            with self.subTest(label=label):
                graph = {} if not patch else {**deepcopy(self.graph), **patch}
                self.assertFalse(a.validate_argument(graph, self.sources)['valid'])
        for key, value in [('scope', None), ('child_ids', [{}]), ('claim', []), ('parent_id', {})]:
            with self.subTest(field=key):
                graph = deepcopy(self.graph)
                graph['nodes'][1][key] = value
                self.assertFalse(a.validate_argument(graph, self.sources)['valid'])

    def test_primary_rule_is_present_in_each_operation_packet(self):
        for operation in a.OPERATIONS:
            task = a.make_task(operation, {}, {'text': '保持する原依頼'})
            self.assertIn(a.PRIMARY_RULE, task['instruction_context']['text'])
            self.assertIn(a.JAPANESE_RULE, task['instruction_context']['short_text'])
            self.assertIn('保持する原依頼', task['instruction_context']['text'])

    def test_single_paragraph_atomic_argument_uses_same_contract(self):
        leaf = deepcopy(self.graph['nodes'][1])
        leaf.update(parent_id=None, abstraction_level=0)
        self.graph.update(nodes=[leaf], groups=[], root_ids=['a'], central_question=leaf['question'], central_answer=leaf['claim'])
        self.assertTrue(a.validate_argument(self.graph, self.sources)['valid'])
        self.assertEqual(['a'], a.paragraph_argument(self.graph, 'a')['proposition_order'])

    def test_cli_check_returns_current_structural_result(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'graph.json').write_text(json.dumps(self.graph))
            (base / 'sources.json').write_text(json.dumps(self.sources))
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = a.main(['check', '--graph', str(base / 'graph.json'), '--sources', str(base / 'sources.json')])
            self.assertEqual(0, code)
            self.assertTrue(json.loads(output.getvalue())['semantic_review_required'])

    def test_schema_defines_hierarchy_and_dependencies_separately(self):
        schema = json.loads(Path(__file__).with_name('argument.schema.json').read_text())
        self.assertEqual('https://json-schema.org/draft/2020-12/schema', schema['$schema'])
        self.assertTrue({'nodes', 'groups', 'dependencies'} <= set(schema['required']))
        self.assertEqual(set(a.NODE_FIELDS), set(schema['$defs']['node']['required']))


if __name__ == '__main__':
    unittest.main()
