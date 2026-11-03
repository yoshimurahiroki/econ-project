import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paragraph
import research_evidence as evidence


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


if __name__ == '__main__':
    unittest.main()
