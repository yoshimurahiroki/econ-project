import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paragraph
import research_evidence as evidence
import research_artifacts as artifacts
import research_meetings as meetings


def selection(text, quote):
    start = text.index(quote)
    return {'start': start, 'end': start + len(quote), 'quote': quote}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paper = 'In 1990 the estimate was 1.25 hours. Euler: c = beta * future.'
        self.source = 'The 1990 sample covers households.'
        self.code = 'residual = c - beta * future\n'
        self.write('spec.json', json.dumps({'beta': 0.96}))
        spec_hash = self.ref('spec.json')['sha256']
        self.result = {'sample': 'households', 'scenario': 'baseline', 'model': 'Euler', 'specification': spec_hash,
                       'stats': {'estimate': {'value': 1.249, 'unit': 'hours'},
                                 'beta': {'value': 0.96, 'unit': 'dimensionless'}}, 'residual': 1e-10}
        self.write('paper.txt', self.paper)
        self.write('source.txt', self.source)
        self.write('code.py', self.code)
        self.write('result.json', json.dumps(self.result))
        self.identities = {'sample': 'households', 'scenario': 'baseline', 'model': 'Euler', 'specification': spec_hash}
        keys = {name: [name] for name in self.identities}
        judgment = {'reviewer': 'native-owner', 'decision': 'supported', 'rationale': 'Compared the exact passages.'}
        self.contract = {
            'manuscript': self.ref('paper.txt'), 'adopted': self.identities,
            'sources': {'original': {**self.ref('source.txt'), 'metadata': {'identities': {'sample': 'households'}}}},
            'claims': [{'id': 'sample', 'target': selection(self.paper, 'In 1990'),
                        'sources': [{'id': 'original', 'span': selection(self.source, '1990 sample covers households')}],
                        'judgment': judgment}],
            'numbers': [{'id': 'estimate', 'target': selection(self.paper, '1.25'),
                         'unit_target': selection(self.paper, 'hours'), 'unit_display': 'hours',
                         'result': {**self.ref('result.json'), 'key': ['stats', 'estimate'],
                                    'unit': 'hours', 'format': '.2f', 'identity_keys': keys}}],
            'models': [{'id': 'euler', 'equation': selection(self.paper, 'c = beta * future'),
                        'code': {**self.ref('code.py'), 'span': selection(self.code, self.code.strip())},
                        'result': {**self.ref('result.json'), 'residual_key': ['residual'],
                                   'tolerance': 1e-8, 'identity_keys': keys}, 'judgment': judgment}],
            'coverage': {'spans': [selection(self.paper, self.paper)],
                         'accounted': [{'target': selection(self.paper, '1990'), 'claim': 'sample', 'kind': 'source'}]}}

    def write(self, name, data):
        (self.root / name).write_text(data, encoding='utf-8')

    def ref(self, name):
        return {'path': name, 'sha256': paragraph.sha((self.root / name).read_bytes())}

    def result_change(self, mutate):
        result = copy.deepcopy(self.result)
        mutate(result)
        self.write('result.json', json.dumps(result))
        for key in ('numbers', 'models'):
            self.contract[key][0]['result'].update(self.ref('result.json'))


    def test_changed_number_sample_scenario_and_unit(self):
        for field, value, message in [('value', 1.4, 'formatted statistic'), ('unit', 'days', 'unit differs')]:
            with self.subTest(field=field):
                self.result_change(lambda r: r['stats']['estimate'].__setitem__(field, value))
                with self.assertRaisesRegex(ValueError, message):
                    evidence.bind(self.contract, self.root)
        for field in ('sample', 'scenario', 'model', 'specification'):
            with self.subTest(field=field):
                self.result_change(lambda r: r.__setitem__(field, 'different'))
                with self.assertRaisesRegex(ValueError, 'identity differs'):
                    evidence.bind(self.contract, self.root)
        self.result_change(lambda r: r['stats']['estimate'].__setitem__('value', float('nan')))
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            evidence.bind(self.contract, self.root)
        self.result_change(lambda r: r['stats'].pop('estimate'))
        with self.assertRaisesRegex(ValueError, 'missing JSON key'):
            evidence.bind(self.contract, self.root)

    def test_registration_preserves_saved_inference_without_derivation(self):
        saved = {'method': 'official-example', 'coefficients': {'effect': 0.0, 'omitted': None},
                 'standard_errors': {'effect': 0.25, 'omitted': None},
                 'statistics': {'coefficient.effect': {'value': 0.0, 'unit': 'hours'}},
                 'provenance': {'producer_sha256': self.ref('code.py')['sha256']},
                 'covariance': [[0.0625, None], [None, None]],
                 'inference': {'reference_distribution': 'normal'}}
        self.write('saved.json', json.dumps(saved))
        spec = {'sources': [{'id': 'fit', 'result': 'saved.json', 'code': 'code.py'}], 'bindings': {}}
        registry = artifacts.normalize(self.root, spec)
        self.assertEqual(set(registry['statistics']), {'fit.coefficient.effect', 'fit.standard_error.effect'})
        self.assertEqual(registry['records']['fit']['source_result'], saved)
        saved['inference'].update(confidence_level=0.90, confidence_intervals={'effect': [-0.41, 0.41]},
                                  p_values={'effect': 1.0, 'omitted': None})
        self.write('saved.json', json.dumps(saved))
        registry = artifacts.normalize(self.root, spec)
        self.assertEqual(registry['statistics']['fit.confidence_lower.effect']['value'], -0.41)
        self.assertNotIn('fit.confidence_95_lower.effect', registry['statistics'])
        self.assertEqual(registry['items']['fit-coefficients']['metadata']['confidence_level'], 0.90)

        model = {'model_contract': 'MC-choice', 'knowledge_ids': ['CHOICE-01'],
                 'equations': {'choice': 'a = max(0, b / c)'},
                 'notation': {'a': 'hours of chosen activity'},
                 'parameter_roles': {'c': {'role': 'calibrated', 'unit': 'currency per hour squared'}},
                 'assumptions': ['c > 0'], 'normalization': 'outside-option utility is zero',
                 'equilibrium_selection': 'unique maximizer', 'horizon': 'one period'}
        saved['adopted'] = {**model, 'sample_ids': ['individual-1']}
        saved['effective_options'] = {'raw_records': [{'private_row': index} for index in range(50)]}
        saved['run_id'] = 'saved-fit-run'
        spec['sources'][0]['metadata'] = {'welfare_definition': 'net benefit in currency per person'}
        self.write('saved.json', json.dumps(saved))
        registry = artifacts.normalize(self.root, spec)
        self.write('gallery.json', json.dumps(registry))
        (self.root / 'saved.json').unlink()
        (self.root / 'code.py').unlink()
        selected = artifacts.gallery_items(self.root, 'gallery.json', item_ids=['fit-coefficients'])[0]
        definitions = selected['metadata']['result_definitions']['fit']
        self.assertEqual({key: definitions[key] for key in model}, model)
        self.assertEqual(definitions['welfare_definition'], 'net benefit in currency per person')
        self.assertNotIn('sample_ids', definitions)
        self.assertEqual(registry['records']['fit']['source_result'], saved)
        self.assertEqual(selected['source_reference']['keys'], ['items', 'fit-coefficients'])
        context = artifacts.composition_context(self.root, 'gallery.json', result_ids=['fit'],
                                               item_ids=['fit-coefficients'])
        result = context['sources']['result:fit']['research_result']
        self.assertEqual(result['statistics']['fit.coefficient.effect'], {'value': 0.0, 'unit': 'hours'})
        self.assertEqual(result['quantity_origins']['fit.coefficient.effect']['source_key'], ['coefficients', 'effect'])
        self.assertEqual({key: result['definitions'][key] for key in model}, model)
        self.assertEqual(result['producer']['run_id'], 'saved-fit-run')
        self.assertEqual(result['producer']['references'], registry['records']['fit']['references'])
        self.assertNotIn('raw_records', json.dumps(context))
        self.assertNotIn('source_result', json.dumps(context))
        display = context['sources']['display:fit-coefficients']['display_item']
        self.assertEqual(display['rows'], selected['rows'])
        self.assertEqual(display['row_indices'], selected['row_indices'])
        self.assertEqual(display['source_reference'], selected['source_reference'])
        self.assertEqual(json.loads(context['sources']['result:fit']['text']), result)

    def test_saved_specialist_blocks_keep_interval_family_and_cell_coordinates(self):
        source = {'display': {'kind': 'iv_confidence_set', 'rows': [
            {'term': 'effect', 'lower': None, 'upper': 0.25, 'lower_unbounded': True, 'upper_unbounded': False},
            {'term': 'effect', 'lower': 2.0, 'upper': None, 'lower_unbounded': False, 'upper_unbounded': True},
            {'term': 'price', 'lower': 0.1, 'upper': 0.9, 'lower_unbounded': False, 'upper_unbounded': False}],
            'metadata': {'effective_options': {'args': {'weights': [11, 17], 'vcov': 'HC1'},
                                               'columns': {'weights': 'sampling_weight'}}}},
            'displays': {'simultaneous': {'kind': 'event-study', 'rows': [
                {'event_time': 0, 'estimate': 1.0, 'ci_low': -0.7, 'ci_high': 2.7}],
                'metadata': {'interval_type': 'simultaneous', 'confidence_level': 0.9}},
                'rdd_summary': {'kind': 'rdd', 'rows': [{'term': 'treatment_effect', 'estimate': 1.4}]},
                'rdd_coordinates': {'kind': 'rdd', 'rows': [
                    {'x': -0.1, 'estimate': 0.4, 'component': 'bin', 'side': 'left'},
                    {'x': 0.1, 'estimate': 1.8, 'component': 'bin', 'side': 'right'}]},
                'outcomes': {'kind': 'structural', 'columns': [
                    {'key': key, 'label': label, 'unit': ''} for key, label in
                    [('scenario', 'Scenario'), ('quantity', 'Outcome'), ('value', 'Saved value'), ('unit', 'Unit')]],
                    'rows': [{'scenario': scenario, 'quantity': quantity, 'value': value, 'unit': unit}
                             for scenario, quantity, value, unit in
                             [('baseline', 'price', 2.0, 'currency'), ('merger', 'price', 2.4, 'currency'),
                              ('baseline', 'share', 0.2, 'share'), ('merger', 'share', 0.15, 'share')]],
                    'metadata': {'report_role': 'counterfactual'},
                    'display': {'plot_type': 'bar', 'x': 'scenario', 'y': 'value', 'facet': 'quantity', 'legend': False}}},
            'diagnostics': {'group_time': {'cells': [
                {'group': 2021, 'time': 2022, 'event_time': 1, 'estimate': 1.4, 'se': 0.2,
                 'ci_low': 0.9, 'ci_high': 1.9, 'role': 'att', 'sample_ids': ['private-row']} ]}}}
        items = artifacts.prepare_gallery_items({'records': {'saved': {'source_result': source}}, 'statistics': {}})
        self.assertEqual(items['saved-iv_confidence_set']['display']['plot_type'], 'iv_confidence_set')
        confidence = artifacts.gallery_plot(items['saved-iv_confidence_set'])
        self.assertEqual([tick.get_text() for tick in confidence.axes[0].get_yticklabels()], ['effect', 'price'])
        options = items['saved-iv_confidence_set']['metadata']['effective_options']
        self.assertEqual(options, {'args': {'vcov': 'HC1'}, 'columns': {'weights': 'sampling_weight'}})
        self.assertEqual(source['display']['metadata']['effective_options']['args']['weights'], [11, 17])
        self.assertEqual(items['saved-displays-simultaneous']['metadata']['interval_type'], 'simultaneous')
        self.assertEqual(items['saved-displays-simultaneous']['rows'][0]['ci_low'], -0.7)
        self.assertEqual(items['saved-displays-rdd_summary']['display']['plot_type'], 'table')
        self.assertEqual(items['saved-displays-rdd_coordinates']['display']['x'], 'x')
        self.assertEqual(items['saved-displays-rdd_coordinates']['display']['plot_type'], 'rdd')
        outcomes = items['saved-displays-outcomes']
        self.assertEqual(outcomes['columns'], source['displays']['outcomes']['columns'])
        self.assertEqual(outcomes['display']['facet'], 'quantity')
        self.assertEqual([row['value'] for row in outcomes['rows']], [2.0, 2.4, 0.2, 0.15])
        figure = artifacts.gallery_plot(outcomes)
        self.assertEqual([axis.get_ylabel() for axis in figure.axes], ['Saved value (currency)', 'Saved value (share)'])
        self.assertNotIn('result_id', source['displays']['outcomes']['rows'][0])
        cell = items['saved-group_time']['rows'][0]
        self.assertEqual((cell['cohort'], cell['time'], cell['estimate'], cell['ci_high']), (2021, 2022, 1.4, 1.9))
        self.assertNotIn('sample_ids', cell)
        self.assertIsNone(items['saved-group_time']['metadata']['interval_type'])
        self.assertEqual(items['saved-group_time-cohort-event']['metadata']['display_source']['key'], ['diagnostics', 'group_time'])

    def test_comparison_retains_definitions_within_one_display(self):
        definitions = {'estimand': 'ATT(g,t)', 'population': 'eligible people', 'sample': 'sample-v1',
                       'period': [2020, 2022], 'weights': None, 'base_period': 'universal'}
        registry = {'schema': 'research-artifact-registry-v1', 'statistics': {}, 'records': {
            'a': {'source_result': dict(definitions, cohort=2021)},
            'b': {'source_result': dict(definitions, cohort=2022)}}}
        registry['items'] = artifacts.prepare_gallery_items(registry, [{
            'id': 'effects', 'title': 'Saved effects', 'kind': 'coefficient', 'result_ids': ['a', 'b'],
            'columns': [{'key': 'estimate', 'label': 'Effect', 'unit': 'hours'}],
            'rows': [{'result_id': 'a', 'estimate': 1.0}, {'result_id': 'b', 'estimate': 2.0}],
            'display': {'plot_type': 'table'}}])
        self.write('gallery.json', json.dumps(registry))
        compared = artifacts.gallery_compare(self.root, 'gallery.json', ['effects'])
        self.assertEqual(compared['result_definition_differences']['cohort'], {'effects/a': 2021, 'effects/b': 2022})
        self.assertEqual(compared['comparison_contract']['status'], 'different_definitions')
        self.assertEqual(compared['comparison_contract']['unrecorded_fields'], {})
        self.assertFalse(compared['comparison_contract']['analysis_executed'])
        self.assertEqual(compared['items'][0]['source_reference']['keys'], ['items', 'effects'])
        registry['items']['effects']['display']['row_order'] = [1, 0]
        for row in registry['items']['effects']['rows']:
            row['unit'] = 'hours'
        self.write('gallery.json', json.dumps(registry))
        context = artifacts.composition_context(self.root, 'gallery.json', result_ids=['b', 'a'], item_ids=['effects'])
        self.assertEqual(list(context['sources']), ['result:b', 'result:a', 'display:effects'])
        display = context['sources']['display:effects']['display_item']
        self.assertEqual(display['row_indices'], [1, 0])
        self.assertEqual([row['estimate'] for row in display['rows']], [2.0, 1.0])
        context = artifacts.composition_context(self.root, 'gallery.json', result_ids=['a'], item_ids=['effects'])
        display = context['sources']['display:effects']['display_item']
        self.assertEqual(display['result_ids'], ['a'])
        self.assertEqual(display['row_indices'], [0])
        self.assertEqual(display['rows'], [{'estimate': 1.0, 'result_id': 'a', 'unit': 'hours'}])
        self.assertEqual(list(display['metadata']['result_definitions']), ['a'])
        registry['items']['effects']['metadata']['producers']['a']['run_id'] = 'another-run'
        self.write('different.json', json.dumps(registry))
        with self.assertRaisesRegex(ValueError, 'producer differ'):
            artifacts.composition_context(self.root, 'gallery.json', result_ids=['a'], item_ids=['effects'],
                                          gallery_path='different.json')

    def test_selected_theory_displays_preserve_regions_paths_and_point_labels(self):
        columns = [{'key': key, 'label': key, 'unit': ''}
                   for key in ('x', 'y', 'lower', 'upper', 'component', 'series', 'time', 'label')]
        rows = [{'x': q, 'y': 12-q, 'lower': 2+q, 'upper': 12-q,
                 'component': 'region', 'series': 'Surplus'} for q in (0, 5)]
        rows += [{'x': 5, 'y': 7, 'component': 'equilibrium', 'series': 'Equilibrium', 'label': 'E'}]
        rows += [{'x': x, 'y': y, 'time': time, 'component': 'path', 'series': 'Adjustment'}
                 for time, x, y in [(0, 8, 4), (1, 6.8, 5), (2, 5.82, 4.8), (3, 5.528, 4.23)]]
        registry = {'schema': 'research-artifact-registry-v1', 'statistics': {},
                    'records': {'theory': {'source_result': {}}}}
        registry['items'] = artifacts.prepare_gallery_items(registry, [{
            'id': 'theory', 'title': 'Saved model relationships', 'kind': 'structural',
            'result_ids': ['theory'], 'columns': columns, 'rows': rows,
            'display': {'plot_type': 'structural', 'x': 'x', 'y': 'y', 'series': 'series',
                        'lower': 'lower', 'upper': 'upper', 'path_order': 'time', 'point_label': 'label'}}])
        original = copy.deepcopy(registry['items']['theory'])
        # Selection must not compose presentations for the rest of a saved catalogue.
        registry['items']['unselected'] = {'id': 'unselected'}
        self.write('gallery.json', json.dumps(registry))
        selected = artifacts.gallery_items(self.root, 'gallery.json', item_ids=['theory'])
        self.assertEqual([item['id'] for item in selected], ['theory'])
        figure = artifacts.gallery_plot(selected[0])
        axis = figure.axes[0]
        path = next(line for line in axis.lines if line.get_label().startswith('Adjustment'))
        self.assertEqual(list(path.get_xdata()), [8, 6.8, 5.82, 5.528])
        self.assertEqual(list(path.get_ydata()), [4, 5, 4.8, 4.23])
        polygon = axis.collections[0].get_paths()[0].vertices
        self.assertEqual(set(map(tuple, polygon)), {(0, 2), (0, 12), (5, 7)})
        self.assertIn('E', [text.get_text() for text in axis.texts])
        self.assertEqual(registry['items']['theory'], original)
        invalid = copy.deepcopy(selected[0])
        invalid['rows'][0]['lower'] = 13
        with self.assertRaisesRegex(ValueError, 'region boundaries'):
            artifacts.gallery_plot(invalid)

    def test_result_materials_place_saved_exhibits_and_keep_summary(self):
        root = Path(__file__).resolve().parent.parent
        entries = [{'id': key, 'title': key, 'kind': kind, 'result_ids': [key], 'files': [],
                    'metadata': {}, 'rows': [], 'columns': [], 'interpretation': 'Saved interpretation'}
                   for key, kind in [('main', 'coefficient'), ('sample', 'descriptive'), ('event', 'event_study')]]
        entries[0]['findings'] = 'Saved finding'
        output = self.root / 'materials'
        meetings.create_bundle(root, output, entries, title='Results', kind='results',
                               project_view={'research_question': 'Effect on hours?', 'results_summary': 'Saved main result'})
        meeting, bodies, _ = meetings.load_meeting(output)
        ids = [row['id'] for row in meeting['sections']]
        self.assertLess(ids.index('result-2'), ids.index('results'))
        self.assertLess(ids.index('results'), ids.index('result-1'))
        self.assertLess(ids.index('result-1'), ids.index('result-3'))
        self.assertEqual(bodies['results'], 'Saved main result')
        self.assertEqual(bodies['findings'], 'main: Saved finding')
        self.assertEqual(meeting['artifacts']['main']['rows'], entries[0]['rows'])
        structural = [{'id': key, 'title': key, 'kind': 'table', 'result_ids': ['fitted-model'],
                       'files': [], 'metadata': {'report_role': role, 'model_contract': 'MC-pyblp-bertrand'},
                       'rows': [{'value': value, 'result_id': 'fitted-model'}],
                       'columns': [{'key': 'value', 'label': 'Saved value', 'unit': 'currency'}]}
                      for key, role, value in [('prices', 'counterfactual', 2.4),
                                               ('moments', 'model_fit', 0.01), ('parameters', 'parameters', -1.1)]]
        model_text = r'Consumers choose one product. $u_{ij}=x_j\beta-\alpha p_j+\epsilon_{ij}$.'
        output = self.root / 'structural'
        meetings.create_bundle(root, output, structural, title='Structural model', kind='structural',
                               project_view={'section_content': {'model': model_text,
                                             'identification': 'Excluded cost shifts identify the price response.'}})
        meeting, bodies, _ = meetings.load_meeting(output)
        self.assertEqual(bodies['model'], model_text)
        positions = [section['source_section'] for section in meeting['sections'] if section.get('artifacts')]
        self.assertEqual(positions, ['parameters', 'model-fit', 'counterfactual'])
        self.assertEqual(meeting['artifacts']['prices']['rows'], structural[0]['rows'])
        self.assertIn(model_text, meetings.document_source(root, meeting, bodies))
        self.assertIn('MC-pyblp-bertrand', meetings.artifact_notes(meeting['artifacts']['prices']))
        with self.assertRaisesRegex(ValueError, 'outside the selected template'):
            meetings.create_bundle(root, self.root / 'invalid-materials', [], title='Invalid', kind='model',
                                   project_view={'section_content': {'unselected-section': 'Text'}})

    def test_saved_regression_presentation_survives_edit_and_native_export(self):
        definitions = {'estimand': 'linear projection', 'population': 'synthetic example',
                       'sample': 'saved-sample', 'period': '2024', 'weights': None, 'n': 40}
        registry = {'schema': 'research-artifact-registry-v1', 'statistics': {}, 'records': {
            'fit': {'source_result': definitions, 'references': {'data': {'path': 'unavailable-raw.csv'}}}}}
        rows = [{'result_id': 'fit', 'outcome': outcome, 'term': 'treatment', 'estimate': estimate,
                 'se': 0.25, 'ci_low': estimate - 0.4, 'ci_high': estimate + 0.4, 'p_value': p}
                for outcome, estimate, p in [('hours', 0.0, 1.0), ('earnings', 2.0, 0.003)]]
        registry['items'] = artifacts.prepare_gallery_items(registry, [{
            'id': 'regression', 'title': 'Saved models', 'kind': 'table', 'result_ids': ['fit'],
            'columns': [{'key': key, 'label': key, 'unit': ''} for key in rows[0] if key != 'result_id'],
            'rows': rows, 'metadata': {'table_type': 'regression'},
            'display': {'plot_type': 'table', 'outcome_column': 'outcome', 'show_ci': True,
                        'term_labels': {'treatment': 'Treatment'}, 'statistic_rows': [{'field': 'n', 'label': 'N'}]}}])
        self.write('gallery.json', json.dumps(registry))
        revision = artifacts.state.content_hash(registry['items']['regression'])
        artifacts.edit_gallery_item(self.root, 'gallery.json', 'regression',
                                    {'display': {'title': 'Main results'}}, expected_revision=revision)
        saved = json.loads((self.root / 'gallery.json').read_text())
        self.assertEqual(saved['items']['regression']['rows'], rows)
        entries = artifacts.gallery_items(self.root, 'gallery.json')
        self.assertEqual(entries[0]['presentation']['body'][0]['cells'], ['0.000', '2.000'])
        self.assertEqual(entries[0]['presentation']['body'][1]['cells'], ['(0.250)', '(0.250)'])
        template_root = Path(__file__).resolve().parent.parent / 'tex' / 'slides'
        target = self.root / 'tex' / 'slides'
        target.mkdir(parents=True)
        (target / 'meeting_templates.json').write_bytes((template_root / 'meeting_templates.json').read_bytes())
        bundle = self.root / 'meeting'
        meetings.create_bundle(self.root, bundle, entries, title='Results', kind='results')
        native = meetings.native_slides_requests(bundle)
        cells = [request['insertText']['text'] for request in native['requests']
                 if 'insertText' in request and 'cellLocation' in request['insertText']]
        self.assertIn('0.000', cells)
        self.assertIn('(0.250)', cells)
        self.assertIn('[1.600, 2.400]', cells)
        self.assertEqual(native['images'], [])
        self.assertTrue(native['new_independent_edition'])

    def test_regression_comparison_preserves_model_formats_and_saved_values(self):
        registry = {'schema': 'research-artifact-registry-v1', 'statistics': {}, 'records': {}}
        items = []
        for result_id, se, low, high, p, digits, formats in [
            ('a', 'standard_error', 'lower', 'upper', 'pvalue', 1,
             {'estimate': '.1f', 'standard_error': '.2f', 'lower': '.2f',
              'pvalue': '.2e', 'degrees_of_freedom': '.2f'}),
            ('b', 'std.error', 'conf.low', 'conf.high', 'p.value', 5,
             {'estimate': '.5f', 'std.error': '.4f', 'conf.low': '.4f',
              'p.value': '.5f', 'degrees_of_freedom': '.4f'}),
        ]:
            registry['records'][result_id] = {'source_result': {'n': 40}}
            zero = 0.0 if result_id == 'a' else None
            rows = [{'result_id': result_id, 'term': 'x', 'estimate': 1.234567,
                     se: .123456, low: 1.0, high: 1.5, p: .00012345,
                     'degrees_of_freedom': 17.12345},
                    {'result_id': result_id, 'term': 'zero', 'estimate': zero,
                     se: zero, low: zero, high: zero, p: zero,
                     'degrees_of_freedom': 17.12345}]
            items.append({'id': result_id, 'title': result_id, 'kind': 'table',
                          'result_ids': [result_id], 'rows': rows,
                          'columns': [{'key': key, 'label': key, 'unit': ''}
                                      for key in rows[0] if key != 'result_id'],
                          'metadata': {'table_type': 'regression'},
                          'display': {'digits': digits, 'formats': formats,
                                      'show_ci': True, 'show_p': True, 'show_stars': True}})
        registry['items'] = artifacts.prepare_gallery_items(registry, items)
        self.write('gallery.json', json.dumps(registry))
        original = (self.root / 'gallery.json').read_bytes()
        expected = {
            'a': ['1.2***', '(0.12)', '[1.00, 1.5]', '1.23e-04',
                  '0.0***', '(0.00)', '[0.00, 0.0]', '0.00e+00'],
            'b': ['1.23457***', '(0.1235)', '[1.0000, 1.50000]', '0.00012', '', '', '', ''],
        }
        for order in [('a', 'b'), ('b', 'a')]:
            comparison = artifacts.gallery_compare(self.root, 'gallery.json', list(order))
            table = comparison['regression_table']
            for index, result_id in enumerate(order):
                self.assertEqual([row['cells'][index] for row in table['presentation']['body']],
                                 expected[result_id])
                df = next(row for row in table['presentation']['footer'] if row['label'] == '自由度')
                self.assertEqual(df['cells'][index], '17.12' if result_id == 'a' else '17.1234')
                n = next(row for row in table['presentation']['footer'] if row['label'] == '観測数')
                self.assertEqual(n['cells'][index], '40')
            values = {row['quantity']: row for row in table['rows']}
            for quantity, value in [('x / 推定値', 1.234567), ('x / 標準誤差', .123456),
                                    ('x / 区間下端', 1.0), ('x / 区間上端', 1.5),
                                    ('x / p 値', .00012345)]:
                self.assertEqual([values[quantity][result_id] for result_id in order], [value, value])
            self.assertEqual(values['zero / 推定値']['a'], 0.0)
            self.assertIsNone(values['zero / 推定値']['b'])
            self.assertFalse(comparison['comparison_contract']['analysis_executed'])
        self.assertEqual((self.root / 'gallery.json').read_bytes(), original)

        for item in items:
            model_key = item['id'] + '_model'
            outcome_key = item['id'] + '_outcome'
            item['display'].update(model_column=model_key, outcome_column=outcome_key)
            item['columns'].extend({'key': key, 'label': key, 'unit': ''}
                                   for key in (model_key, outcome_key))
            models = [('main', 'hours')] if item['id'] == 'a' else [('first', 'hours'), ('second', 'earnings')]
            item['rows'] = [{**row, model_key: model, outcome_key: outcome}
                            for model, outcome in models for row in item['rows']]
        registry['items'] = artifacts.prepare_gallery_items(registry, items)
        self.write('multiple.json', json.dumps(registry))
        for order, columns, outcomes in [
            (['a', 'b'], ['main', 'first', 'second'], ['hours', 'hours', 'earnings']),
            (['b', 'a'], ['first', 'second', 'main'], ['hours', 'earnings', 'hours']),
        ]:
            table = artifacts.gallery_compare(self.root, 'multiple.json', order)['regression_table']
            self.assertEqual([column['key'] for column in table['columns'][1:]], columns)
            self.assertEqual([cell['text'] for cell in table['presentation']['headers'][0][1:]
                              for _ in range(cell['colspan'])], outcomes)
            for index, model in enumerate(columns):
                self.assertEqual([row['cells'][index] for row in table['presentation']['body']],
                                 expected['a' if model == 'main' else 'b'])

    def test_artifact_definitions_preserve_saved_text_and_numeric_spans(self):
        comparison = '地区Aと地区B、2024–2025年。文字列 {{stat:effect}} を保持。'
        equation = r'c_t + k_{t+1} = (1-\tau_t)k_t^\alpha + (1-\delta)k_t'
        saved = {'statistics': {'effect': {'value': 1.249, 'unit': 'hours'}},
                 'adopted': {'comparison': comparison, 'equations': {'resource': equation}},
                 'provenance': {'producer_sha256': self.ref('code.py')['sha256']}}
        self.write('saved.json', json.dumps(saved, ensure_ascii=False))
        source_bytes = (self.root / 'saved.json').read_bytes()
        templates = {
            'article': '{{definition:comparison}}\n{{stat:effect}}\n{{definition:equation}}\n{{stat:effect}}',
            'slides': '{{definition:equation}}\n{{stat:effect}}\n{{definition:comparison}}\n{{stat:effect}}'}
        for name, text in templates.items():
            self.write(name + '.qmd', text)
        spec = {'pipeline': 'saved-definitions',
                'sources': [{'id': 'fit', 'result': 'saved.json', 'code': 'code.py'}],
                'bindings': {'effect': {'key': 'fit.effect', 'unit': 'hours', 'format': '.2f',
                                        'display_unit': '時間', 'label': 'Effect'}},
                'definitions': {
                    'comparison': {'key': ['items', 'fit-statistics', 'metadata',
                                           'result_definitions', 'fit', 'comparison']},
                    'equation': {'key': ['records', 'fit', 'source_result', 'adopted',
                                        'equations', 'resource']}},
                'article_template': 'article.qmd', 'slides_template': 'slides.qmd', 'figure': ['effect']}
        self.write('artifacts.json', json.dumps(spec))
        common = ['--root', str(self.root), '--spec', str(self.root / 'artifacts.json')]
        registry_path = self.root / 'registry.json'
        self.assertEqual(artifacts.main(['normalize', *common, '--output', str(registry_path)]), 0)
        registry_bytes = registry_path.read_bytes()
        for name in templates:
            manuscript = self.root / (name + '-rendered.qmd')
            trace = self.root / (name + '-trace.json')
            self.assertEqual(artifacts.main([
                'render', *common, '--registry', str(registry_path),
                '--template', str(self.root / (name + '.qmd')),
                '--output', str(manuscript), '--trace', str(trace)]), 0)
            text = manuscript.read_text(encoding='utf-8')
            self.assertIn(comparison, text)
            self.assertIn(equation, text)
            self.assertEqual(text.count('1.25 時間'), 2)
            self.assertEqual(text.count('{{stat:effect}}'), 1)
            captures = artifacts.load(trace)
            self.assertEqual(len(captures), 2)
            for capture in captures:
                for key in ('target', 'unit_target'):
                    span = capture[key]
                    self.assertEqual(text[span['start']:span['end']], span['quote'])
            contract = artifacts.make_contract(self.root, spec, registry_path, manuscript, captures)
            self.assertEqual(evidence.bind(contract, self.root)['status'], 'verified')
        self.assertEqual(registry_path.read_bytes(), registry_bytes)
        self.assertEqual((self.root / 'saved.json').read_bytes(), source_bytes)

        invalid = copy.deepcopy(spec)
        invalid['definitions'].pop('comparison')
        with self.assertRaisesRegex(ValueError, 'unknown definition binding'):
            artifacts.validate_spec(self.root, invalid)
        registry = artifacts.load(registry_path)
        for value in (' ', {'period': '2024'}, 2024):
            registry['records']['fit']['source_result']['adopted']['equations']['resource'] = value
            with self.assertRaisesRegex(ValueError, 'saved nonempty text'):
                artifacts.render(self.root, spec, registry, 'article.qmd', None, None)


    def test_saved_results_reach_design_draft_and_completed_body(self):
        from unittest.mock import patch
        import argument

        saved = {'statistics': {'effect': {'value': 1.249, 'unit': 'hours'}},
                 'adopted': {'comparison': '地区Aと地区B'},
                 'provenance': {'producer_sha256': self.ref('code.py')['sha256']}}
        self.write('saved.json', json.dumps(saved, ensure_ascii=False))
        registry = artifacts.normalize(self.root, {'sources': [
            {'id': 'fit', 'result': 'saved.json', 'code': 'code.py'}], 'bindings': {}})
        self.write('registry.json', json.dumps(registry, ensure_ascii=False))
        brief = {'original_request': '保存された地区間比較を文章にする。', 'authority': '保存値と比較を保持する。',
                 'purpose': '地区間比較を伝える。', 'reader': '経済学博士課程のコア科目を履修した読者',
                 'language': 'ja', 'research_results': {'root': str(self.root), 'registry_path': 'registry.json',
                     'result_ids': ['fit'], 'item_ids': ['fit-statistics']}}
        repo = Path(__file__).resolve().parent.parent
        rules = {'policy_id': 'fixture', 'texts': {key: 'Synthetic callback fixture.' for key in
                 ('CORE', 'PROSE', 'econ-writing', 'prose-guide')}, 'profile': 'fixture',
                 'dictionary': json.loads((repo / 'quality/prose_rules.json').read_text())}
        sources = paragraph.normalize_sources({}, research_results=brief['research_results'])
        source = sources['result:fit']
        ref = {'source_id': 'result:fit', 'source_sha256': source['sha256'],
               **selection(source['text'], source['text'])}
        claim = '地区Aと地区Bの労働時間差は1.249時間である。'
        graph = {'schema_version': 1, 'version': '1', 'central_question': '地区間の労働時間差はいくらか。',
                 'central_answer': claim, 'root_ids': ['effect'], 'groups': [], 'dependencies': [],
                 'source_ids': list(sources), 'source_manifest': {sid: row['sha256'] for sid, row in sources.items()},
                 'nodes': [{'node_id': 'effect', 'parent_id': None, 'child_ids': [], 'claim': claim,
                            'question': '地区間の労働時間差はいくらか。', 'next_questions': [],
                            'logical_role': 'result', 'inference_form': 'atomic', 'abstraction_level': 0,
                            'scope': {}, 'source_refs': [ref], 'section_id': 'results', 'paragraph_ids': ['p'],
                            'reasoning': '保存された比較と単位を使う。',
                            'order': {'basis': 'inference', 'position': 0, 'rationale': '比較から結果を述べる。'}}]}
        blueprint = {'schema_version': 1, 'version': '1', 'purpose': brief['purpose'], 'reader': brief['reader'],
                     'central_question': graph['central_question'], 'central_answer': claim, 'contribution': claim,
                     'completion_conditions': ['保存数量を伝える。'], 'argument_structure': graph,
                     'sections': [{'section_id': 'results', 'role': 'result', 'claim': claim}],
                     'paragraphs': [{'paragraph_id': 'p', 'section_id': 'results', 'central_proposition': claim,
                                     'role': 'result', 'depends_on': [], 'source_ids': list(sources), 'scope': {}}],
                     'definitions': saved['adopted'], 'quantities': saved['statistics'], 'conditions': [],
                     'writing_rules': [], 'prohibited_rules': []}
        spec = {'paragraph_id': 'p', 'section_id': 'results', 'blueprint_version': '1',
                'role': {'purpose': brief['purpose'], 'contribution_to_global_argument': claim},
                'central_proposition': {'claim': claim, 'logical_status': 'saved result'},
                'required_content': [{'proposition_id': 'effect', 'exact_content': claim, 'source_id': 'result:fit',
                                      'source_location': selection(source['text'], source['text']),
                                      'evidence_type': 'saved result', 'required_reasoning': '保存された比較と単位を使う。'}],
                'logical_structure': dict.fromkeys(('opening', 'development', 'mechanism', 'implication'), claim),
                'relationships': {'preceding_paragraph': None, 'inherited_information': [],
                                  'following_paragraph': None, 'information_to_pass_forward': claim},
                'terminology': {'adopted_definitions': saved['adopted'], 'fixed_quantities': saved['statistics'],
                                'required_terms': []},
                'scope': {'included': claim, 'excluded': [], 'content_change_authority': brief['authority']},
                'writing': {'language': 'ja', 'profile': 'fixture', 'paragraph_rules': [], 'prohibited_functions': [],
                            'instruction_packet': paragraph.PRIMARY_RULE + paragraph.JAPANESE_RULE,
                            'source_references': list(sources)},
                'completion': {'mandatory_claims': ['effect'], 'evidence_correspondence': True,
                               'logical_coherence': True, 'prose_compliance': True, 'local_review': True},
                **argument.paragraph_argument(graph, 'effect')}
        events, seen = {}, []
        def host(task):
            payload = task['payload']
            seen.append(task)
            self.assertEqual(payload['sources']['result:fit']['research_result']['statistics']['fit.effect'],
                             {'value': 1.249, 'unit': 'hours'})
            self.assertEqual(payload['sources']['display:fit-statistics']['display_item']['rows'],
                             registry['items']['fit-statistics']['rows'])
            if task['operation'] == 'writing:architect':
                result = {'blueprint': blueprint}
            elif task['operation'] == 'writing:specify':
                result = {'specifications': [spec]}
            elif task['operation'] == 'argument.review':
                result = {'checks': [{'check_id': key, 'verdict': 'pass', 'assessment': 'Synthetic saved result correspondence.',
                                      'node_ids': ['effect'], 'source_refs': [ref]}
                                     for key in argument.SEMANTIC_CHECKS], 'findings': []}
            elif task['operation'] == 'writing:paragraph':
                quantity = payload['sources']['result:fit']['research_result']['statistics']['fit.effect']['value']
                result = {'paragraph_id': 'p', 'text': f'地区Aと地区Bの労働時間差は{quantity}時間である。',
                          'binding': payload['binding']}
            else:
                self.assertEqual(task['operation'], 'writing:paragraph-review')
                span = selection(claim, claim)
                result = {'paragraph_id': 'p', 'text_sha256': paragraph.sha(claim), 'spec_sha256': paragraph.content_hash(spec),
                          'binding': payload['binding'], 'findings': [], 'occurrence_judgments': [],
                          'checks': [{'check_id': key, 'verdict': 'pass', 'assessment': 'Synthetic saved result correspondence.',
                                      'spans': [span]} for key in paragraph.LOCAL_CHECKS],
                          'claim_evidence': [{'proposition_id': 'effect', 'assessment': 'Exact saved comparison.',
                              'source_id': 'result:fit', 'source_sha256': source['sha256'], 'target': span,
                              'source': selection(source['text'], source['text'])}],
                          'reasoning': [{'proposition_id': 'effect', 'assessment': 'Exact saved comparison.',
                              'required_reasoning': spec['required_content'][0]['required_reasoning'], 'target': span}],
                          'quantity_evidence': [{'source_id': 'result:fit', 'source_sha256': source['sha256'],
                              'assessment': 'Exact saved quantity.', 'target': selection(claim, '1.249'),
                              'source': selection(source['text'], '1.249')}]}
            original = json.dumps(result, ensure_ascii=False)
            event_id = 'fixture-' + str(len(events))
            returned = {'worker_id': 'fixture', 'event_id': event_id, 'input_sha256': task['input_sha256'],
                        'return_text': original, 'execution_kind': 'single-agent-sequential', 'turn_ref': event_id}
            events[event_id] = {**returned, 'return_sha256': paragraph.sha(original), 'status': 'completed'}
            return returned

        for name, value in [('brief', brief), ('sources', {}), ('rules', rules)]:
            self.write(name + '.json', json.dumps(value, ensure_ascii=False))
        with patch.object(paragraph, 'load_host_adapter', return_value=(host, events.__getitem__)):
            self.assertEqual(paragraph.main(['design', '--brief', str(self.root / 'brief.json'), '--sources', str(self.root / 'sources.json'),
                '--rules', str(self.root / 'rules.json'), '--host', str(self.root / 'host.py'), '--author-id', 'fixture',
                '--execution-kind', 'single-agent-sequential', '--output', str(self.root / 'design.json')]), 0)
        designed = json.loads((self.root / 'design.json').read_text())
        self.assertEqual(designed['sources'], sources)
        for mode in ('compose', 'revise'):
            run = paragraph.ParagraphRun.create(run_id=mode, request=brief['original_request'], authority=brief['authority'],
                author_id='fixture', operation='econ-writing:' + mode, rules=rules, execution_kind='single-agent-sequential',
                original_paragraphs={'p': '著者が書いた元の段落。'} if mode == 'revise' else None, **designed)
            self.assertTrue(run.review_argument(host, events.__getitem__)['valid'])
            self.assertEqual(run.write(host, events.__getitem__), ['p'])
            if mode == 'revise':
                self.assertEqual(seen[-1]['payload']['original_text'], '著者が書いた元の段落。')
            self.assertTrue(run.review('p', host, events.__getitem__)['result']['passed'])
            run.save(self.root / 'paragraph-state.json')
            loaded = paragraph.ParagraphRun.load(self.root / 'paragraph-state.json', resume=False)
            context = loaded.composition_context(['p'])
            self.assertEqual(context['paragraphs']['p']['text'], claim)
            self.assertEqual(context['sources'], sources)
            reused = paragraph.generate_blueprint(brief, sources, rules, host, events.__getitem__, completed_run=loaded,
                paragraph_ids=['p'], execution_kind='single-agent-sequential', author_id='fixture')
            paragraph.generate_specifications(reused['blueprint'], reused['sources'], rules, host, events.__getitem__,
                request=brief['original_request'], authority=brief['authority'], brief=brief, completed_run=loaded,
                paragraph_ids=['p'], execution_kind='single-agent-sequential', author_id='fixture')
            self.assertEqual(seen[-2]['payload']['completed_body'], context)
            self.assertEqual(seen[-1]['payload']['completed_body'], context)


class EvidenceReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, value):
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        (self.root / name).write_text(raw, encoding='utf-8')
        return {'path': name, 'sha256': paragraph.sha((self.root / name).read_bytes())}

    def revision(self, language='en'):
        if language == 'ja':
            original = '割当て効果は8パーセントポイントである。'
            revised = ('アウトカムは世帯による8週間以内の申請完了である。割当てとクラスタリングの単位は自治体である。'
                       '割当て効果は8パーセントポイントである。')
            comment = 'アウトカムの定義と推論の単位を示してください。'
            rationale = ('第3節に、世帯による8週間以内の申請完了をアウトカムとして記載しました。'
                         '割当てとクラスタリングの単位を自治体と明記しました。割当て効果は8パーセントポイントです。')
            unit = 'パーセントポイント'
        else:
            original = 'The assignment effect is 8 percentage points.'
            revised = ('The outcome is household application completion within eight weeks. '
                       'Assignment and clustering are at the municipality level. '
                       'The assignment effect is 8 percentage points.')
            comment = 'Define the outcome and identify the inference unit.'
            rationale = ('Section 3 now defines the outcome as household application completion within eight weeks. '
                         'It states the municipality-level assignment and clustering. '
                         'The assignment effect remains 8 percentage points.')
            unit = 'percentage points'
        fixed = r' \(Y_{im}=\alpha+\tau D_m+u_{im}\) \citep{trial-protocol}.'
        original += fixed
        revised += fixed
        original_ref = self.write('original.md', original)
        revised_ref = self.write('revised.md', revised)
        source_ref = self.write('protocol.txt', revised)
        comment_ref = {**self.write('referee.txt', comment), 'span': selection(comment, comment)}
        result_ref = self.write('saved-result.json', {'sample': 'households', 'statistics': {
            'assignment_effect': {'value': 8, 'unit': 'percentage_points'}}})
        judgment = {'reviewer': 'owner', 'decision': 'supported', 'rationale': rationale}
        contract = {'manuscript': original_ref, 'adopted': {'sample': 'households'},
                    'sources': {'protocol': {**source_ref, 'metadata': {'identities': {'sample': 'households'}}}},
                    'claims': [{'id': 'effect', 'target': selection(original, original), 'judgment': judgment,
                                'sources': [{'id': 'protocol', 'span': selection(revised, revised)}],
                                'bindings': ['effect-number']}],
                    'numbers': [{'id': 'effect-number', 'target': selection(original, '8'),
                                 'unit_target': selection(original, unit), 'unit_display': unit,
                                 'result': {**result_ref, 'key': ['statistics', 'assignment_effect'],
                                            'identity_keys': {'sample': ['sample']},
                                            'unit': 'percentage_points', 'format': '.0f'}}],
                    'review': {'criteria': [{'id': 'definition', 'text': comment}],
                               'assessment': {'reviewer': 'owner', 'findings': [
                                   {'id': 'definition-1', 'claim_id': 'effect', 'criterion_id': 'definition',
                                    'decision': 'revision-required', 'rationale': comment, 'comment': comment_ref,
                                    'references': [{**source_ref, 'span': selection(revised, revised)}, result_ref]}]}}}
        initial = evidence.review(contract, self.root)
        previous_ref = self.write('initial-review.json', initial)
        contract['manuscript'] = revised_ref
        contract['claims'][0]['target'] = selection(revised, revised)
        start = revised.index('8' + ('パーセントポイント' if language == 'ja' else ' percentage points'))
        contract['numbers'][0]['target'] = {'start': start, 'end': start + 1, 'quote': '8'}
        contract['numbers'][0]['unit_target'] = selection(revised, unit)
        contract['review']['previous'] = previous_ref
        finding = contract['review']['assessment']['findings'][0]
        finding.update(decision='supported', rationale=rationale, changes=[selection(revised, revised)])
        contract['review']['response_draft'] = {'language': language, 'finding_ids': ['definition-1']}
        return contract, original, revised, rationale

    def test_current_revision_generates_bilingual_response_through_cli(self):
        from unittest.mock import patch
        for language in ('ja', 'en'):
            with self.subTest(language=language):
                contract, original, revised, rationale = self.revision(language)
                evidence.bind(contract, self.root)
                before = {name: (self.root / name).read_bytes() for name in ('original.md', 'initial-review.json')}
                self.write('contract.json', contract)
                self.assertEqual(evidence.main(['review', 'contract.json', '--root', str(self.root),
                                                '--output', 'current-review.json']), 0)
                result = json.loads((self.root / 'current-review.json').read_text(encoding='utf-8'))
                draft = result['response_draft']
                entry = draft['entries'][0]
                self.assertEqual(entry['origin']['target']['quote'], original)
                self.assertEqual(entry['passages'][0]['quote'], revised)
                self.assertEqual(entry['changes'], contract['review']['assessment']['findings'][0]['changes'])
                self.assertEqual(entry['rationale'], rationale)
                self.assertIn(rationale, draft['text'])
                self.assertIn(revised, draft['text'])
                self.assertIn('**回答**' if language == 'ja' else '**Response**', draft['text'])
                self.assertEqual(entry['bindings']['effect-number']['selected_result'],
                                 {'value': 8, 'unit': 'percentage_points'})
                self.assertEqual(draft['evidence_sha256'], result['evidence_sha256'])
                comparison = copy.deepcopy(contract)
                comparison['review'].pop('assessment')
                comparison['review'].pop('response_draft')
                comparison['review']['response_after'] = {
                    'path': 'current-review.json',
                    'sha256': paragraph.sha((self.root / 'current-review.json').read_bytes())}
                comparison['review']['author_response'] = self.write('response.md', draft['text'])
                compared = evidence.review(comparison, self.root)
                self.assertEqual(compared['status'], 'response-comparison-required')
                self.assertEqual(compared['review']['findings'], result['review']['findings'])
                self.assertEqual({name: (self.root / name).read_bytes() for name in before}, before)
                rules_root = Path(__file__).resolve().parents[1]
                self.write('rules.json', {
                    'policy_id': 'current-writing',
                    'texts': {key: (rules_root / path).read_text(encoding='utf-8') for key, path in {
                        'CORE': 'runtime/CORE.md', 'PROSE': 'runtime/PROSE.md',
                        'econ-writing': 'skills/econ-writing/SKILL.md',
                        'prose-guide': 'skills/econ-writing/references/paper-workflow.md'}.items()},
                    'dictionary': json.loads((rules_root / 'quality/prose_rules.json').read_text(encoding='utf-8')),
                    'profile': (rules_root / 'profiles/default-micro/PROFILE.md').read_text(encoding='utf-8')})
                self.write('host.py', '# Selected host adapter; transport is supplied by the test.\n')
                events = {}
                response = (rationale + (' 第3節の式は同じ割当て効果を表しています。' if language == 'ja'
                                         else ' The equation in Section 3 defines this assignment effect.'))
                def host(task):
                    self.assertEqual(task['operation'], 'econ-writing:compose')
                    entry = task['payload']['entries'][0]
                    self.assertEqual(entry['origin']['target']['quote'], original)
                    self.assertEqual(entry['passages'][0]['quote'], revised)
                    self.assertEqual(entry['bindings']['effect-number']['selected_result']['value'], 8)
                    returned = {'responses': {'definition-1': response}}
                    original_return = json.dumps(returned, ensure_ascii=False)
                    event = {'worker_id': 'writer', 'input_sha256': task['input_sha256'],
                             'return_sha256': paragraph.sha(original_return), 'status': 'completed',
                             'execution_kind': 'single-agent-sequential', 'turn_ref': 'response-turn'}
                    events['response-event'] = event
                    return {'worker_id': 'writer', 'event_id': 'response-event',
                            'input_sha256': task['input_sha256'], 'return_text': original_return,
                            'turn_ref': event['turn_ref']}
                with patch.object(paragraph, 'load_host_adapter', return_value=(host, events.__getitem__)):
                    self.assertEqual(evidence.main([
                        'review', 'contract.json', '--root', str(self.root), '--output', 'written-review.json',
                        '--host', 'host.py', '--rules', 'rules.json', '--request', 'Write the referee response.',
                        '--response-output', 'written-response.md']), 0)
                written = json.loads((self.root / 'written-review.json').read_text(encoding='utf-8'))['response_draft']
                self.assertEqual(written['entries'][0]['response'], response)
                self.assertEqual(written['entries'][0]['rationale'], rationale)
                self.assertEqual(written['execution']['input']['operation'], 'econ-writing:compose')
                self.assertEqual((self.root / 'written-response.md').read_text(encoding='utf-8'), written['text'])
                self.assertEqual(written['output'], {'path': 'written-response.md',
                                                    'sha256': paragraph.sha(written['text'])})
                self.assertEqual({name: (self.root / name).read_bytes() for name in before}, before)

    def test_response_uses_preserved_original_current_changes_and_evidence(self):
        contract, original, revised, _ = self.revision()
        finding = contract['review']['assessment']['findings'][0]
        finding['changes'] = []
        with self.assertRaisesRegex(ValueError, 'changed claim requires'):
            evidence.review(contract, self.root)
        finding['changes'] = [selection(revised, revised)]
        self.write('original.md', original + ' altered')
        with self.assertRaisesRegex(ValueError, 'original manuscript hash differs'):
            evidence.review(contract, self.root)
        self.write('original.md', original)
        self.write('protocol.txt', revised + ' altered')
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            evidence.review(contract, self.root)

    def test_reused_finding_relocates_passage_after_peripheral_edit(self):
        contract, _, revised, rationale = self.revision()
        claim = 'The assignment effect is 8 percentage points.'
        contract['claims'][0]['target'] = selection(revised, claim)
        previous = evidence.review(contract, self.root)
        previous_ref = self.write('current-review.json', previous)
        moved = '# Paper\n\n' + revised
        contract['manuscript'] = self.write('moved.md', moved)
        contract['claims'][0]['target'] = selection(moved, claim)
        contract['numbers'][0]['target'] = selection(moved, '8')
        contract['numbers'][0]['unit_target'] = selection(moved, 'percentage points')
        contract['review'].pop('assessment')
        contract['review']['previous'] = previous_ref
        result = evidence.review(contract, self.root)
        self.assertEqual(result['changes']['reusable_claims'], ['effect'])
        entry = result['response_draft']['entries'][0]
        self.assertEqual(entry['passages'], [selection(moved, revised)])
        self.assertEqual(entry['rationale'], rationale)
        self.assertEqual(entry['origin']['manuscript']['path'], 'original.md')

    def test_cli_preserves_review_manuscript_and_evidence_inputs(self):
        import contextlib
        import io
        contract, _, _, _ = self.revision()
        self.write('contract.json', contract)
        for target in ('original.md', 'initial-review.json', 'protocol.txt', 'referee.txt'):
            with self.subTest(target=target):
                before = (self.root / target).read_bytes()
                error = io.StringIO()
                with contextlib.redirect_stderr(error):
                    status = evidence.main(['review', 'contract.json', '--root', str(self.root), '--output', target])
                self.assertEqual(status, 1)
                self.assertIn('output cannot overwrite', error.getvalue())
                self.assertEqual((self.root / target).read_bytes(), before)
        before = (self.root / 'original.md').read_bytes()
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            status = evidence.main(['review', 'contract.json', '--root', str(self.root),
                                    '--output', 'current-review.json', '--response-output', 'original.md'])
        self.assertEqual(status, 1)
        self.assertIn('response output cannot overwrite', error.getvalue())
        self.assertEqual((self.root / 'original.md').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
