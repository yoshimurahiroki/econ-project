"""Regression fixtures for source/deployed instruction reference validation."""
import json
from pathlib import Path
import tempfile
import unittest

from check_instruction_links import check


class InstructionLinksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.put('registry/resources.json', json.dumps({'resources': {
            'core': {'source_path': 'runtime/CORE.md'}}}))
        self.put('registry/placements.json', json.dumps({'resources': {
            'core': {'deployment_path': '.agents/runtime/CORE.md'}}}))
        for path in ('runtime/CORE.md', '.agents/runtime/CORE.md'):
            self.put(path, '# Core\n\n[entry](#core)\n')
        for path in ('PROJECT_INSTRUCTIONS.txt', 'ECON_INDEX.md', 'OPTIONAL_INPUTS.md'):
            self.put(path, '')

    def put(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_source_bundle_reference_is_not_optionalized(self):
        self.put('runtime/CORE.md', '[missing](references/bundle/runtime/TEAM.md)')
        self.assertEqual(1, len(check(self.root, 'source')))
        self.assertEqual([], check(self.root, 'deployed'))

    def test_existing_file_with_missing_anchor_is_rejected(self):
        self.put('.agents/runtime/CORE.md', '# Core\n\n[entry](#absent)\n')
        self.assertEqual([], check(self.root, 'source'))
        self.assertIn('missing anchor', check(self.root, 'deployed')[0])

    def test_snapshot_reference_follows_installed_location(self):
        self.put('PROJECT_INSTRUCTIONS.txt', 'SOURCE.md identifies this snapshot.')
        self.assertEqual(1, len(check(self.root, 'deployed')))
        self.put('docs/source.md', '# Source\n')
        self.put('PROJECT_INSTRUCTIONS.txt', '[Source snapshot](docs/source.md) identifies this snapshot.')
        self.assertEqual([], check(self.root, 'deployed'))


if __name__ == '__main__':
    unittest.main()
