"""Exercise the research CLI using a small calculation and its consumers."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(__file__).with_name('research.py').resolve()


class ResearchPipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'data.txt').write_text('4')
        (self.root / 'spec.txt').write_text('3')
        (self.root / 'labels.txt').write_text('Result: {{stat:estimate}} units\n')
        (self.root / 'estimate.py').write_text("""import json, pathlib, sys
x = int(pathlib.Path(sys.argv[1]).read_text())
y = int(pathlib.Path(sys.argv[2]).read_text())
pathlib.Path(sys.argv[3]).write_text(json.dumps({'estimate': {'value': x * y, 'unit': 'units'}}))
""")
        self.spec = {'pipeline': 'demo', 'stages': [
            {'id': 'estimate', 'inputs': ['data.txt', 'spec.txt', 'estimate.py'], 'depends': {},
             'outputs': {'result': 'result.json'}, 'argv': [sys.executable, '{root}/estimate.py', '{root}/data.txt', '{root}/spec.txt', '{out:result}']},
            {'id': 'paper', 'inputs': ['labels.txt'], 'depends': {'estimate': ['result']}, 'outputs': {'text': 'paper.txt'},
             'render': {'template': 'labels.txt', 'output': 'text', 'statistics': {'estimate': {'stage': 'estimate', 'output': 'result', 'key': ['estimate'], 'unit': 'units', 'format': '.2f'}}}},
            {'id': 'independent', 'inputs': ['data.txt'], 'depends': {}, 'outputs': {'copy': 'copy.txt'},
             'argv': [sys.executable, '-c', 'import pathlib,sys; pathlib.Path(sys.argv[2]).write_text(pathlib.Path(sys.argv[1]).read_text())', '{root}/data.txt', '{out:copy}']},
        ]}
        self.write_spec()

    def tearDown(self):
        self.tmp.cleanup()

    def write_spec(self):
        (self.root / 'manifest.json').write_text(json.dumps(self.spec))

    def cli(self, code=0, profile=None):
        args = [sys.executable, str(RUNNER), '--root', str(self.root)]
        if profile is not None:
            args += ['--profile', profile]
        p = subprocess.run(args + ['manifest.json'], text=True, capture_output=True)
        self.assertEqual(p.returncode, code, p.stderr + p.stdout)
        return json.loads(p.stdout) if p.stdout else p.stderr


    def test_failed_replacement_preserves_previous_and_blocks_descendant(self):
        first = self.cli()
        prior = self.root / first['estimate']['outputs']['result']
        old = prior.read_bytes()
        (self.root / 'estimate.py').write_text('raise SystemExit(7)\n')
        failed = self.cli(1)
        self.assertEqual(failed['estimate']['status'], 'failed')
        self.assertEqual(failed['paper']['status'], 'blocked')
        self.assertEqual(failed['independent']['status'], 'reused')
        self.assertEqual(prior.read_bytes(), old)
        tasks = json.loads((self.root / '.agents/state/team.json').read_text())['tasks']
        self.assertEqual(tasks[failed['estimate']['task']]['status'], 'failed')
        self.assertEqual(tasks[failed['estimate']['task']]['outputs']['research:execution']['value']['returncode'], 7)



    def test_state_price_contract_selects_and_saves_price_set(self):
        project = RUNNER.parent.parent
        selector = project / 'skills/econ-data/scripts/research_causal.py'
        payoffs = [[1, 0], [1, 1], [1, 2]]
        prices = [1, 1]
        request = {'question': 'Which claim prices admit no arbitrage with the traded assets?',
            'estimand': 'The no-arbitrage price set and its lower and upper hedges.',
            'identification': 'Hold every possible state, traded payoff and observed asset price fixed.',
            'design': 'structural', 'outcome_scale': 'currency', 'data_structure': 'finite_model',
            'treatment_pattern': 'none', 'dependence': 'deterministic',
            'model_contract_id': 'MC-state-price-bounds', 'target': {'kind': 'price_bounds'},
            'conditions': {'free_trading': True, 'all_states_possible': True},
            'adopted_specification': {'model': 'state_price_bounds',
                'inputs': {'payoffs': payoffs, 'prices': prices}, 'unit': 'USD'}}
        request_path = self.root / 'selection.json'
        selected_path = self.root / 'selected.json'
        spec_path = self.root / 'model.json'
        result_path = self.root / 'result.json'
        # q=(t,1-2t,t), 0<t<1/2: the middle-state claim has price (0,1).
        # The claim (1,2,3) equals one unit of each traded asset and costs 2.
        for claim, lower, upper, price_set in [([0, 1, 0], 0, 1, 'open_interval'),
                                              ([1, 2, 3], 2, 2, 'singleton')]:
            with self.subTest(price_set=price_set):
                request['adopted_specification']['inputs']['claim'] = claim
                request_path.write_text(json.dumps(request))
                selected_run = subprocess.run([sys.executable, str(selector), 'select', str(request_path),
                    '--output', str(selected_path)], cwd=project, text=True, capture_output=True)
                self.assertEqual(selected_run.returncode, 0, selected_run.stderr)
                selected = json.loads(selected_path.read_text())
                self.assertEqual(selected['status'], 'selected')
                self.assertFalse(selected['executed'])
                self.assertEqual(selected['method'], 'state_price_bounds')
                execution = selected['method_selection']['official_implementation']['execution_specification']
                self.assertEqual(execution['status'], 'specified')
                self.assertFalse(execution['adoption_required'])
                self.assertEqual(execution['specification'], request['adopted_specification'])
                spec_path.write_text(json.dumps(execution['specification']))
                argv = [sys.executable if i == 0 else str(spec_path) if arg == 'SPEC.json'
                        else str(result_path) if arg == 'RESULT.json' else arg
                        for i, arg in enumerate(execution['command'])]
                completed = subprocess.run(argv, cwd=project, text=True, capture_output=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                saved = json.loads(result_path.read_text())
                self.assertEqual(saved['model_contract'], 'MC-state-price-bounds')
                self.assertEqual(saved['knowledge_ids'], ['ASSET-01'])
                self.assertEqual(saved['specification'], execution['specification'])
                self.assertEqual(saved['effective_inputs']['tolerance'], 1e-9)
                result = saved['fullresults']
                self.assertEqual(result['price_set'], price_set)
                for name, expected in [('lower_bound', lower), ('upper_bound', upper)]:
                    self.assertAlmostEqual(result[name], expected, places=10)
                    self.assertAlmostEqual(saved['statistics'][name]['value'], expected, places=10)
                    self.assertEqual(saved['statistics'][name]['unit'], 'USD today')
                q = result['positive_state_prices']
                self.assertGreater(min(q), 0)
                for j, price in enumerate(prices):
                    self.assertAlmostEqual(sum(row[j]*state_price for row, state_price in zip(payoffs, q)), price, places=10)
                for name, bound, direction in [('subhedge', lower, 1), ('superhedge', upper, -1)]:
                    hedge = result[name]
                    self.assertAlmostEqual(sum(p*h for p, h in zip(prices, hedge)), bound, places=10)
                    for row, payoff in zip(payoffs, claim):
                        self.assertLessEqual(direction*(sum(x*h for x, h in zip(row, hedge))-payoff), 1e-10)
                if price_set == 'singleton':
                    for holding in result['replicating_portfolio']:
                        self.assertAlmostEqual(holding, 1, places=10)
                else:
                    self.assertIsNone(result['replicating_portfolio'])

    def test_numerical_contracts_select_and_execute(self):
        project = RUNNER.parent.parent
        selector = project / 'skills/econ-data/scripts/research_causal.py'
        cases = [
            ('MC-finite-correlated-equilibrium', 'correlated_equilibrium', 'equilibrium',
             {'payoffs': [[[1, -1], [-1, 1]], [[-1, 1], [1, -1]]]}),
            ('MC-finite-tu-shapley-core', 'tu_shapley_core', 'allocation',
             {'values': [0, 1, 2, 5, 0, 3, 4, 8]}),
            ('MC-interbank-clearing', 'interbank_clearing', 'equilibrium',
             {'liabilities': [[0, 6], [3, 0]], 'outside_liabilities': [4, 3], 'external_assets': [1, 2]}),
            ('MC-multitask-incentives', 'multitask_incentives', 'policy_value',
             {'b': 1, 'm': 2, 'rho': .25, 'a': .5, 'vq': 2, 'vqly': 3}),
        ]
        results = {}
        for contract, model, target, inputs in cases:
            with self.subTest(model=model):
                request = {'question': 'Calculate the supplied finite model.',
                    'estimand': 'The equation-defined allocation and payoffs.',
                    'identification': 'Hold the supplied primitives fixed.',
                    'design': 'structural', 'outcome_scale': 'payoff', 'data_structure': 'finite_model',
                    'treatment_pattern': 'none', 'dependence': 'deterministic',
                    'model_contract_id': contract, 'target': {'kind': target},
                    'adopted_specification': {'model': model, 'inputs': inputs, 'unit': 'payoff units'}}
                request_path = self.root / (model+'-selection.json')
                selected_path = self.root / (model+'-selected.json')
                request_path.write_text(json.dumps(request))
                selected_run = subprocess.run([sys.executable, str(selector), 'select', str(request_path),
                    '--output', str(selected_path)], cwd=project, text=True, capture_output=True)
                self.assertEqual(selected_run.returncode, 0, selected_run.stderr)
                selected = json.loads(selected_path.read_text())
                self.assertEqual(selected['status'], 'selected')
                self.assertFalse(selected['executed'])
                self.assertEqual(selected['method'], model)
                implementation = selected['method_selection']['official_implementation']
                execution = implementation['execution_specification']
                self.assertEqual(execution['status'], 'specified')
                self.assertEqual(execution['specification'], request['adopted_specification'])
                self.assertFalse(execution['adoption_required'])
                spec_path = self.root / (model+'-spec.json')
                result_path = self.root / (model+'-result.json')
                spec_path.write_text(json.dumps(execution['specification']))
                argv = [sys.executable if i == 0 else str(spec_path) if arg == 'SPEC.json'
                        else str(result_path) if arg == 'RESULT.json' else arg
                        for i, arg in enumerate(execution['command'])]
                completed = subprocess.run(argv, cwd=project, text=True, capture_output=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                saved = json.loads(result_path.read_text())
                self.assertEqual(saved['model_contract'], contract)
                self.assertEqual(saved['specification'], execution['specification'])
                self.assertEqual(saved['unit'], 'payoff units')
                results[model] = saved['fullresults']

        # Matching pennies has four equally likely recommendations and zero gains from deviation.
        ce = results['correlated_equilibrium']
        for row in ce['probabilities']:
            for probability in row:
                self.assertAlmostEqual(probability, .25, places=10)
        self.assertEqual(ce['payoffs'], [0., 0.])
        self.assertLessEqual(ce['mass_error'], 1e-10)
        self.assertTrue(all(abs(row['slack']) <= 1e-10 for row in ce['obedience']))
        # The six player orders yield these marginal-contribution averages.
        shapley = results['tu_shapley_core']
        self.assertEqual(shapley['allocation'], ['8/3', '11/3', '5/3'])
        self.assertEqual(shapley['efficiency_residual'], '0')
        self.assertTrue(shapley['in_core'])
        # p1=1+p2/2 and p2=2+3*p1/5; both payments are below nominal debt.
        clearing = results['interbank_clearing']
        for actual, expected in zip(clearing['payments'], (20/7, 26/7)):
            self.assertAlmostEqual(actual, expected, places=9)
        self.assertLessEqual(clearing['fixed_point_residual'], 1e-11)
        self.assertAlmostEqual(sum(clearing['outside_payments'])+sum(clearing['equity']), 3, places=9)
        # x+y/4=1 and y+x/4=2 define the interior effort choice.
        effort = results['multitask_incentives']
        for name, expected in [('x', 8/15), ('y', 28/15), ('principal_payoff', 169/30), ('agent_payoff', 79/30)]:
            self.assertAlmostEqual(effort[name], expected, places=10)
        self.assertLessEqual(effort['kkt_residual'], 1e-10)

        # A partial adopted input remains a specification request and executes no model.
        del request['adopted_specification']['inputs']['m']
        request_path.write_text(json.dumps(request))
        partial = subprocess.run([sys.executable, str(selector), 'select', str(request_path),
            '--output', str(selected_path)], cwd=project, text=True, capture_output=True)
        self.assertEqual(partial.returncode, 0, partial.stderr)
        execution = json.loads(selected_path.read_text())['method_selection']['official_implementation']['execution_specification']
        self.assertEqual(execution['status'], 'inputs_required')
        self.assertEqual(execution['missing_fields'], ['inputs.m'])


if __name__ == '__main__':
    unittest.main()
