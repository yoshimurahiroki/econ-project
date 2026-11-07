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


if __name__ == '__main__':
    unittest.main()
