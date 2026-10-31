#!/usr/bin/env python3
"""Bounded package-only fixtures; never invokes models or research programs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('export_project', Path(__file__).with_name('export_project.py'))
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'source'
        self.root.mkdir()
        self.resources = {
            'core': {'source_path': 'runtime/CORE.md', 'deployment_path': '.agents/runtime/CORE.md', 'export_alias': 'CORE.md'},
            'writing': {'source_path': 'skills/econ-writing/SKILL.md', 'deployment_path': '.agents/skills/econ-writing/SKILL.md', 'export_alias': 'WRITING.md'},
            'paper': {'source_path': 'skills/econ-writing/references/paper.md', 'deployment_path': '.agents/skills/econ-writing/references/paper.md', 'export_alias': 'PAPER.md'},
            'policy': {'source_path': 'references/repository-policy/.cursorrules', 'deployment_path': '.cursorrules', 'export_alias': 'POLICY.md'},
        }
        self.routes = {'schema_version': 1, 'resources': self.resources, 'operations': [
            {'skill_id': 'econ-writing', 'operation': 'write', 'mode': 'compose', 'default': True, 'required_resources': ['core', 'writing', 'policy'], 'conditional_resources': [{'resource_id': 'paper', 'when': 'whole-paper', 'whole_resource': True}]},
            {'skill_id': 'econ-writing', 'operation': 'revise', 'mode': 'revise', 'required_resources': ['core', 'writing', 'policy'], 'conditional_resources': []},
        ], 'aliases': {'econ-edit': {'skill_id': 'econ-writing', 'mode': 'revise'}}}
        self.put('runtime/CORE.md', '# Core\n')
        self.put('skills/econ-writing/SKILL.md', '# Writing\n[core](../../runtime/CORE.md)\n[whole paper](references/paper.md)\n')
        self.put('skills/econ-writing/references/paper.md', '# Paper\n')
        self.put('references/repository-policy/.cursorrules', '# Policy\n')
        self.save()
        self.patch = patch.object(exporter, 'ROOT', self.root)
        self.patch.start()
    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()
    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    def save(self):
        self.put('runtime/ROUTES.yaml', json.dumps(self.routes))
    def run_export(self, **kwargs):
        target = self.base / 'out'
        exporter.export(target, task='econ-writing', **kwargs)
        return target
    def manifest(self, out):
        return json.loads((out / 'SOURCE.md').read_text().split('```json\n')[1].split('\n```')[0])
    def test_source_zip_needs_no_git_or_installed_tree(self):
        out = self.run_export()
        self.assertTrue((out / 'POLICY.md').is_file())
        self.assertNotIn('PAPER.md', [p.name for p in out.iterdir()])
        self.assertIn('(CORE.md)', (out / 'WRITING.md').read_text())
        self.assertIn('(OPTIONAL_INPUTS.md#paper)', (out / 'WRITING.md').read_text())
    def test_explicit_condition_includes_reference(self):
        out = self.run_export(conditions=['whole-paper'])
        self.assertTrue((out / 'PAPER.md').is_file())
        self.assertIn('(PAPER.md)', (out / 'WRITING.md').read_text())
    def test_legacy_alias_resolves_mode(self):
        out = self.base / 'out'
        exporter.export(out, task='econ-edit')
        self.assertEqual(self.manifest(out)['operations'][0]['mode'], 'revise')
    def test_installed_layout_uses_deployment_mapping(self):
        for res in self.resources.values():
            self.put(res['deployment_path'], (self.root / res['source_path']).read_text())
        self.put('.agents/runtime/ROUTES.yaml', json.dumps(self.routes))
        out = self.run_export(layout='installed')
        self.assertEqual(self.manifest(out)['layout'], 'installed')
    def test_missing_required_resource_leaves_no_output(self):
        (self.root / 'runtime/CORE.md').unlink()
        with self.assertRaises(OSError): self.run_export()
        self.assertFalse((self.base / 'out').exists())
    def test_unknown_local_reference_leaves_no_output(self):
        self.put('runtime/CORE.md', '[must read](missing.md)')
        with self.assertRaisesRegex(ValueError, 'Unregistered'): self.run_export()
        self.assertFalse((self.base / 'out').exists())
    def test_alias_collision_rejected(self):
        self.resources['paper']['export_alias'] = 'core.MD'
        self.save()
        with self.assertRaises(ValueError): self.run_export()
    def test_traversal_rejected(self):
        self.resources['core']['source_path'] = '../escape.md'
        self.save()
        with self.assertRaises(ValueError): self.run_export()
    def test_symlink_source_rejected(self):
        path = self.root / 'runtime/CORE.md'
        path.unlink()
        path.symlink_to(self.root / 'references/repository-policy/.cursorrules')
        with self.assertRaises(ValueError): self.run_export()
    def test_content_identity_changes_with_source(self):
        out = self.run_export()
        first = self.manifest(out)
        self.put('runtime/CORE.md', '# Changed\n')
        second = self.base / 'second'
        exporter.export(second, task='econ-writing')
        self.assertNotEqual(first['snapshot_id'], self.manifest(second)['snapshot_id'])
        for record in first['files']:
            self.assertEqual(len(record['source_sha256']), 64)
            self.assertEqual(len(record['export_sha256']), 64)
    def test_code_path_rewrite_preserves_receipt_metadata(self):
        from sync_common_core import read_receipt, RECEIPT_START, RECEIPT_END, LEGACY_START, LEGACY_END
        source = self.resources['writing']['source_path']
        relocated = str(Path(source).with_name('REFERENCE.md'))
        digest = exporter.sha256((self.root / source).read_bytes())
        metadata = {'source_repository': 'github.com/example/source',
                    'paths': [{'path': source, 'source_path': source,
                               'source_sha256': digest, 'target_sha256': digest}],
                    'note': '同期時点の記録'}
        before = '使用例: `' + source + '`\n\n'
        after = '\n\n```sh\ncat ' + source + '\n```\n'
        for version, start, end in ((1, LEGACY_START, LEGACY_END), (2, RECEIPT_START, RECEIPT_END)):
            with self.subTest(version=version):
                block = start + '\n```json\n' + json.dumps(metadata, ensure_ascii=False, indent=3) + '\n```\n' + end
                result = exporter.rewrite_code_paths(before + block + after, {source: relocated})
                expected = before.replace(source, relocated) + block + after.replace(source, relocated)
                self.assertEqual(result.encode('utf-8'), expected.encode('utf-8'))
                self.assertEqual(read_receipt(result.encode('utf-8'))[:2], (version, metadata))
    def test_unknown_condition_rejected(self):
        with self.assertRaises(ValueError): self.run_export(conditions=['typo'])
    def test_existing_output_preserved(self):
        out = self.base / 'out'
        out.mkdir()
        (out / 'user.txt').write_text('keep')
        with self.assertRaises(ValueError): self.run_export()
        self.assertEqual((out / 'user.txt').read_text(), 'keep')
    def test_required_dependency_closure(self):
        self.resources['core']['required_resources'] = ['paper']
        self.save()
        self.assertTrue((self.run_export() / 'PAPER.md').is_file())
    def test_custom_profile_and_project_addition(self):
        self.put('docs/ai/custom.md', '# Custom\n')
        self.put('docs/project.txt', 'Project input\n')
        config = {'version': 1, 'writing_profile': 'docs/ai/custom.md', 'files': [{'path': 'docs/project.txt', 'output': 'STUDY.txt'}]}
        self.put('docs/ai/repo_context.md', '<!-- export-project:v1 -->\n~~~json\n' + json.dumps(config) + '\n~~~\n')
        out = self.run_export()
        self.assertTrue((out / 'CUSTOM_STYLE.md').is_file())
        self.assertTrue((out / 'STUDY.txt').is_file())
    def test_runtime_handoff_alias_preserves_existing_owner(self):
        self.routes['aliases']['econ-handoff'] = {'runtime_action': 'handoff', 'required_resources': ['core'], 'resolve_owner_by': 'existing_result_owner'}
        self.save()
        out = self.base / 'handoff'
        exporter.export(out, task='econ-handoff')
        self.assertEqual(self.manifest(out)['operations'][0]['skill_id'], 'runtime')
        self.assertFalse((out / 'WRITING.md').exists())
    def test_global_condition_adds_only_selected_resource(self):
        self.routes['placements'] = {'common_resources': ['policy'], 'conditional_resources': [{'resource_id': 'paper', 'when': 'figure_needed'}]}
        self.save()
        self.assertTrue((self.run_export(conditions=['figure_needed']) / 'PAPER.md').exists())
    def test_unknown_mode_fails_before_output(self):
        with self.assertRaises(ValueError): self.run_export(mode='unknown')
        self.assertFalse((self.base / 'out').exists())
    def test_installed_source_policy_relative_link(self):
        self.put('references/repository-policy/.cursorrules', '[core](../../runtime/CORE.md)')
        for res in self.resources.values():
            self.put(res['deployment_path'], (self.root / res['source_path']).read_text())
        self.put('.agents/runtime/ROUTES.yaml', json.dumps(self.routes))
        out = self.run_export(layout='installed')
        self.assertIn('(CORE.md)', (out / 'POLICY.md').read_text())
    def test_all_packaged_local_links_resolve(self):
        out = self.run_export()
        from urllib.parse import urlsplit
        def check(link):
            parts = urlsplit(link)
            if not parts.scheme and parts.path:
                self.assertTrue((out / parts.path).is_file(), link)
            return link
        for path in out.glob('*.md'):
            exporter.rewrite_markdown(path.read_text(), check)
    def test_instruction_character_limit(self):
        self.resources['instructions'] = {'source_path': 'docs/ai/project_instructions.txt', 'deployment_path': 'docs/ai/project_instructions.txt', 'export_alias': 'PROJECT_INSTRUCTIONS.txt'}
        self.routes['operations'][0]['required_resources'].append('instructions')
        self.put('docs/ai/project_instructions.txt', 'a' * 8001)
        self.save()
        with self.assertRaisesRegex(ValueError, '8,000'): self.run_export()
        self.assertFalse((self.base / 'out').exists())

    def test_empty_sections_add_no_body(self):
        self.routes['conditions'] = {'empty': {'paper': {'sections': []}}}
        self.save()
        self.assertFalse((self.run_export(conditions=['empty']) / 'PAPER.md').exists())

    def test_sections_descendants_dependency_and_dedup(self):
        self.put('skills/econ-writing/references/paper.md', '# Paper\n## Pick\nchosen\n### Child\nchild body\n## Dependency\nneeded\n## Omitted\nnot selected\n')
        self.routes['conditions'] = {'scoped': {'paper': {'sections': ['Pick', 'Child', 'Pick']}}}
        self.resources['paper']['section_dependencies'] = {'Pick': {'paper': {'sections': ['Dependency']}}}
        self.save()
        text = (self.run_export(conditions=['scoped']) / 'PAPER.md').read_text()
        self.assertEqual(text.count('### Child'), 1)
        self.assertIn('needed', text)
        self.assertNotIn('not selected', text)

    def test_missing_section_identifies_resource_and_section(self):
        self.routes['conditions'] = {'bad': {'paper': {'sections': ['Absent']}}}
        self.save()
        with self.assertRaisesRegex(ValueError, 'paper / Absent'):
            self.run_export(conditions=['bad'])
        self.assertFalse((self.base / 'out').exists())

    def test_alias_input_and_handoff_section_preserved(self):
        self.routes['aliases']['EDIT'] = {'skill_id': 'econ-writing', 'mode': 'revise', 'default_input': 'immediately_preceding_answer'}
        self.routes['aliases']['econ-handoff'] = {'runtime_action': 'handoff', 'required_resources': ['core'], 'section': 'Handoff', 'resolve_owner_by': 'existing_result_owner'}
        edit = exporter.resolve_operation(self.routes, 'EDIT')
        self.assertEqual(edit['default_input'], 'immediately_preceding_answer')
        self.assertEqual(edit['requested_selector'], 'EDIT')
        handoff = exporter.resolve_operation(self.routes, 'econ-handoff')
        self.assertEqual(handoff['requested_section'], 'Handoff')

    def test_profile_precedence_and_default_exclusion(self):
        self.resources['default-micro'] = {'source_path': 'profiles/default.md', 'deployment_path': '.agents/profiles/default.md', 'export_alias': 'DEFAULT.md'}
        self.put('profiles/default.md', '# Default\n')
        self.put('profiles/user.md', '# User profile\n')
        self.routes['operations'][0]['required_resources'].append('default-micro')
        self.save()
        resolved = exporter.resolve_operation(self.routes, 'econ-writing', user_profile='profiles/user.md', project_profile='profiles/project.md')
        self.assertEqual(resolved['selected_profile'], 'profiles/user.md')
        self.assertNotIn('default-micro', resolved['resource_sections'])
        out = self.run_export(style_profile='profiles/user.md')
        self.assertFalse((out / 'DEFAULT.md').exists())
        self.assertTrue((out / 'CUSTOM_STYLE.md').exists())

    def test_deployed_links_and_generated_entrances(self):
        self.routes['placements'] = {'policy_pointers': [{'source_path': 'references/repository-policy/.cursorrules', 'deployment_path': '.cursor/rules/task.mdc'}]}
        self.save()
        out = self.run_export(output_format='deployed')
        self.assertTrue((out / '.agents/runtime/CORE.md').is_file())
        entry = out / '.cursor/rules/task.mdc'
        self.assertIn('../../.agents/runtime/CORE.md', entry.read_text())
        from urllib.parse import urlsplit
        for path in out.rglob('*'):
            if not path.is_file() or path.name == 'SOURCE.md':
                continue
            def check(link):
                parts = urlsplit(link)
                if not parts.scheme and parts.path:
                    self.assertTrue((path.parent / parts.path).is_file(), (path, link))
                return link
            exporter.rewrite_markdown(path.read_text(), check)

    def test_declared_anchor_dependency_is_retained(self):
        self.put('skills/econ-writing/references/paper.md', '# Paper\n## Pick\n[needed](#dependency)\n## Dependency\nkept\n## Other\nomitted\n')
        self.resources['paper']['section_dependencies'] = {'Pick': {'paper': {'sections': ['Dependency']}}}
        self.routes['conditions'] = {'scoped': {'paper': {'sections': ['Pick']}}}
        self.save()
        text = (self.run_export(conditions=['scoped']) / 'PAPER.md').read_text()
        self.assertIn('## Dependency', text)
        self.assertNotIn('## Other', text)

    def test_conflicting_duplicate_condition_rejected(self):
        self.routes['conditions'] = {'whole-paper': {'paper': {'sections': ['Other']}}}
        self.save()
        with self.assertRaisesRegex(ValueError, 'Conflicting condition'):
            self.run_export()

    def test_fenced_headings_are_not_sections(self):
        self.put('skills/econ-writing/references/paper.md', '## Pick\n```python\n# Pretend\n## Fake\n```\n### Child\nkept\n## Other\nomitted\n')
        self.routes['conditions'] = {'scoped': {'paper': {'sections': ['Pick', 'Child']}}}
        self.save()
        text = (self.run_export(conditions=['scoped']) / 'PAPER.md').read_text()
        self.assertEqual(text.count('### Child'), 1)
        self.assertIn('## Fake', text)
        self.assertNotIn('## Other', text)

    def test_deployed_custom_profile_and_root_policy(self):
        self.resources['repository-policy'] = self.resources.pop('policy')
        for op in self.routes['operations']:
            op['required_resources'] = ['core', 'writing', 'repository-policy']
        self.resources['default-micro'] = {'source_path': 'profiles/default.md', 'deployment_path': '.agents/profiles/default.md', 'export_alias': 'DEFAULT.md'}
        self.put('profiles/default.md', '# Default\n')
        self.put('profiles/custom.md', '# Custom\n')
        self.save()
        out = self.run_export(output_format='deployed', style_profile='profiles/custom.md')
        self.assertTrue((out / 'CUSTOM_STYLE.md').exists())
        self.assertFalse((out / '.agents/profiles/default.md').exists())
        self.assertIn('(.agents/runtime/CORE.md)', (out / '.cursorrules').read_text())
        self.assertNotIn('configuration_clients', (out / 'ECON_INDEX.md').read_text())

    def test_generated_operation_instructions_keep_alias_metadata(self):
        self.routes['aliases']['EDIT'] = {'skill_id': 'econ-writing', 'mode': 'revise', 'default_input': 'immediately_preceding_answer'}
        self.save()
        out = self.base / 'edit'
        exporter.export(out, task='EDIT')
        self.assertIn('immediately_preceding_answer', (out / 'ECON_INDEX.md').read_text())
        self.routes['aliases']['econ-handoff'] = {'runtime_action': 'handoff', 'required_resources': ['core'], 'section': 'Handoff'}
        self.save()
        handoff = self.base / 'handoff'
        exporter.export(handoff, task='econ-handoff')
        self.assertIn('Requested section: Handoff', (handoff / 'ECON_INDEX.md').read_text())

    def test_conditional_section_links_do_not_expand_active_resource(self):
        self.put('skills/econ-writing/references/paper.md', '## Pick\n[only if needed](#other)\n## Other\nunrequested body\n')
        self.routes['conditions'] = {'scoped': {'paper': {'sections': ['Pick']}}, 'empty': {'paper': {'sections': []}}}
        self.save()
        out = self.run_export(conditions=['scoped', 'empty'])
        text = (out / 'PAPER.md').read_text()
        self.assertNotIn('unrequested body', text)
        self.assertIn('OPTIONAL_INPUTS.md#paper--other', text)

    def test_deployed_scoped_skill_keeps_yaml_metadata(self):
        self.put('skills/econ-writing/SKILL.md', '---\nname: econ-writing\ndescription: Write prose.\n---\n# Writing\n## Revise\nselected\n## Compose\nnot selected\n')
        self.routes['operations'][0]['resource_sections'] = {'writing': {'sections': ['Revise']}}
        self.save()
        out = self.run_export(output_format='deployed')
        text = (out / '.agents/skills/econ-writing/SKILL.md').read_text()
        self.assertTrue(text.startswith('---\nname: econ-writing'))
        self.assertIn('## Revise', text)
        self.assertNotIn('## Compose', text)

    def test_maintenance_tool_snapshot_refused_before_publication(self):
        self.resources['maintenance'] = {'source_path': 'scripts/setup.sh', 'deployment_path': 'scripts/setup.sh', 'export_alias': 'SETUP.sh', 'snapshot': 'source_distribution_only'}
        self.put('scripts/setup.sh', '#!/bin/sh\n')
        self.save()
        for output_format in ['flat', 'deployed']:
            with self.assertRaisesRegex(ValueError, 'complete source distribution'):
                self.run_export(references=['maintenance'], output_format=output_format)
            self.assertFalse((self.base / 'out').exists())


class RealRegistryTests(unittest.TestCase):
    """Regression tests against the shipped definitions, never synthetic substitutes."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = Path(__file__).resolve().parents[1]
        self.routes = exporter.load_routes(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def output(self, name, **kwargs):
        out = self.base / name
        exporter.export(out, **kwargs)
        return out

    def manifest(self, out):
        return json.loads((out / 'SOURCE.md').read_text().split('```json\n')[1].split('\n```')[0])

    def test_thirteen_operations_five_owners_both_formats(self):
        self.assertEqual(len(self.routes['operations']), 13)
        self.assertEqual(len({op['owner_skill'] for op in self.routes['operations']}), 5)
        for fmt in ('flat', 'deployed'):
            for i, op in enumerate(self.routes['operations']):
                with self.subTest(operation=op['id'], format=fmt):
                    out = self.output(fmt + str(i), task=op['id'], output_format=fmt)
                    manifest = self.manifest(out)
                    self.assertEqual(manifest['operations'][0]['canonical_operation'], op['id'])
                    self.assertTrue(manifest['operations'][0]['active_rules'])
                    selected = {row['logical_id'] for row in manifest['files']}
                    self.assertTrue({'core', 'control', 'prose'} <= selected)
                    self.assertFalse(selected & {'native-run', 'native-check', 'paragraph-engine', 'argument-engine'})
                    if fmt == 'deployed':
                        for pointer in self.routes['placements']['policy_pointers']:
                            self.assertTrue((out / pointer['deployment_path']).is_file())

    def test_revise_required_language_rule_never_optional(self):
        for fmt in ('flat', 'deployed'):
            out = self.output(fmt, task='econ-writing:revise', output_format=fmt)
            res = self.routes['resources']['prose']
            path = res['export_alias' if fmt == 'flat' else 'deployment_path']
            self.assertIn('## Revise for the requested language', (out / path).read_text())
            self.assertNotIn('prose--revise-for-the-requested-language', (out / 'OPTIONAL_INPUTS.md').read_text())
            self.assertFalse(any(r['logical_id'] in ('execution', 'state-contract', 'publication', 'integration') for r in self.manifest(out)['files']))

    def test_whole_paper_argument_and_structure_required(self):
        for fmt in ('flat', 'deployed'):
            out = self.output(fmt, task='econ-writing:compose', conditions=['whole_paper_abstract_introduction_or_section_architecture'], output_format=fmt)
            res = self.routes['resources']['paper-workflow']
            text = (out / res['export_alias' if fmt == 'flat' else 'deployment_path']).read_text()
            self.assertIn('## Establish the argument from the research', text)
            self.assertIn("## Design the paper's argument", text)
            self.assertNotIn('paper-workflow--establish-the-argument-from-the-research', (out / 'OPTIONAL_INPUTS.md').read_text())

    def test_selected_model_method_contains_body(self):
        out = self.output('model', task='econ-design', conditions=['economic_method_needed', 'method_model_construction'])
        text = (out / self.routes['resources']['design-methods']['export_alias']).read_text()
        self.assertIn('## Model construction', text)
        self.assertIn('### Ordered choices and constructive representations', text)
        self.assertNotIn('## Regression discontinuity', text)

    def test_conditions_add_real_body_without_duplicate_empty_conditions(self):
        for old in ('formulation_choice_or_dependency_order_unresolved', 'delegation_resume_or_handoff_active', 'selected_profile_is_default_micro'):
            self.assertNotIn(old, self.routes['conditions'])
        for cid in ('formulation_or_choice_unresolved', 'delegation_active', 'resumption_active', 'handoff_active'):
            op = exporter.resolve_operation(self.routes, 'econ-data', conditions=[cid])
            self.assertTrue(set(op['resource_sections']) - {'core', 'econ-data'})
        for cid, selection in self.routes['conditions'].items():
            self.assertTrue(selection, cid)
        formal = exporter.resolve_operation(self.routes, 'econ-writing:revise', conditions=['formal_review_requested'])
        self.assertTrue({'native-run', 'native-check', 'prose-check-rules'} <= formal['resource_sections'].keys())
        for fmt in ('flat', 'deployed'):
            out = self.output('resume-' + fmt, task='econ-data', conditions=['resumption_active'], output_format=fmt)
            resource = self.routes['resources']['state-contract']
            text = (out / resource['export_alias' if fmt == 'flat' else 'deployment_path']).read_text()
            self.assertIn('## Governing context', text)
            self.assertIn('context_revisions', text)
            self.assertIn('previous_context_sha256', text)

    def test_one_japanese_example_no_other_function_or_language(self):
        out = self.output('ja', task='econ-writing:revise', conditions=['example_ja_revision_translation'])
        text = (out / self.routes['resources']['examples-ja']['export_alias']).read_text()
        self.assertIn('default-micro.ja.translation', text)
        self.assertIn('## 改稿と翻訳', text)
        self.assertNotIn('## 結論と比較', text)
        self.assertNotIn('## Abstract', text)
        ids = {r['logical_id'] for r in self.manifest(out)['files']}
        self.assertNotIn('examples-en', ids)
        self.assertNotIn('extended-ja', ids)

    def test_aliases_keep_owner_input_and_handoff_contract(self):
        for alias, canonical in [('econ-paper', 'econ-writing:explain'), ('econ-style', 'econ-writing:profile'), ('econ-edit', 'econ-writing:revise'), ('econ-assertive', 'econ-writing:guidance'), ('explain-before-shorten', 'econ-writing:revise')]:
            self.assertEqual(exporter.resolve_operation(self.routes, alias)['canonical_operation'], canonical)
        self.assertEqual(exporter.resolve_operation(self.routes, 'EDIT')['default_input'], 'immediately_preceding_answer')
        handoff = exporter.resolve_operation(self.routes, 'econ-handoff')
        self.assertEqual(handoff['requested_section'], 'Handoff')
        self.assertEqual(handoff['resolve_owner_by'], 'existing_result_owner')
        repair = exporter.resolve_operation(self.routes, 'econ-review', 'assess+repair')
        self.assertEqual(repair['canonical_operation'], 'econ-review:assess+repair')

    def copied_source(self):
        import shutil
        copied = self.base / 'source'
        shutil.copytree(self.root, copied, ignore=shutil.ignore_patterns('__pycache__', '.git'))
        return copied

    def distribution_source(self):
        import runpy
        import shutil
        root = self.copied_source()
        shutil.rmtree(root / '.agents', ignore_errors=True)
        version = runpy.run_path(str(root / 'harness/policy_assets.py'))['POLICY_ID'].removeprefix('economics-native-')
        for name in ('plugin.json', '.codex-plugin/plugin.json'):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'version': version}))
        self.assertFalse((root / 'skills/econ-literature/references').exists())
        return root

    def test_distribution_creates_missing_bundle_parents(self):
        import subprocess
        import sys
        root = self.distribution_source()
        run = subprocess.run([sys.executable, '-B', 'scripts/export_project.py', '--generate-entries'],
                             cwd=root, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        for owner in {op['owner_skill'] for op in self.routes['operations']}:
            self.assertTrue((root / 'skills' / owner / 'references/bundle/quality/policy_manifest.json').is_file())

    def test_distribution_retains_concurrent_input_when_creating_parent(self):
        root = self.distribution_source()
        original = Path.mkdir
        concurrent = root / 'concurrent.txt'
        def mkdir(path, *args, **kwargs):
            original(path, *args, **kwargs)
            if path == root / 'skills/econ-literature/references':
                concurrent.write_text('concurrent input\n')
        with patch.object(Path, 'mkdir', mkdir):
            with self.assertRaisesRegex(ValueError, 'Distribution inputs changed: concurrent.txt'):
                exporter.generate_distribution(root)
        self.assertEqual(concurrent.read_text(), 'concurrent input\n')
        self.assertFalse((root / 'skills/econ-literature/references/bundle').exists())

    def test_missing_required_body_fails_with_rule_and_operation_before_publish(self):
        root = self.copied_source()
        path = root / 'runtime/PROSE.md'
        path.write_text(path.read_text().replace('## Revise for the requested language', '## Removed meaning rule'))
        with patch.object(exporter, 'ROOT', root):
            for fmt in ('flat', 'deployed'):
                with self.assertRaisesRegex(ValueError, 'Missing required rule prose.revise-for-the-requested-language; required section Revise for the requested language; operation econ-writing:revise'):
                    self.output(fmt, task='econ-writing:revise', output_format=fmt)
                self.assertFalse((self.base / fmt).exists())

    def test_missing_required_rule_definition_fails_before_publish(self):
        root = self.copied_source()
        path = root / 'registry/resources.json'
        data = json.loads(path.read_text())
        del data['rules']['prose.revise-for-the-requested-language']
        path.write_text(json.dumps(data))
        with patch.object(exporter, 'ROOT', root):
            with self.assertRaisesRegex(ValueError, 'Missing required rule prose.revise-for-the-requested-language'):
                self.output('missing', task='econ-writing:revise')
        self.assertFalse((self.base / 'missing').exists())

    def test_stable_rule_id_survives_heading_rename(self):
        root = self.copied_source()
        path = root / 'runtime/PROSE.md'
        path.write_text(path.read_text().replace('## Revise for the requested language', '## Preserve source propositions'))
        registry = root / 'registry/resources.json'
        data = json.loads(registry.read_text())
        data['sections']['prose']['revise-for-the-requested-language']['heading'] = 'Preserve source propositions'
        registry.write_text(json.dumps(data))
        # A moved public heading must also update its source links; the stable rule ID does not change.
        for path in root.rglob('*.md'):
            path.write_text(path.read_text().replace('#revise-for-the-requested-language', '#preserve-source-propositions'))
        with patch.object(exporter, 'ROOT', root):
            out = self.output('renamed', task='econ-writing:revise')
        self.assertIn('## Preserve source propositions', (out / 'PROSE.md').read_text())
        self.assertIn('prose.revise-for-the-requested-language', self.manifest(out)['operations'][0]['active_rules'])

    def test_generated_entries_are_repeatable_and_registry_owned(self):
        from route_registry import generate_entries
        root = self.copied_source()
        generate_entries(root)
        self.assertIn('runtime/CORE.md', (root / 'docs/ai/project_instructions.txt').read_text())
        self.assertIn('CORE, PROSE', (root / 'skills/econ-writing/agents/openai.yaml').read_text())
        self.assertEqual((root / 'runtime/CONTROL.md').read_text().count('## Registered review plans'), 1)
        for name in ('CORE', 'PROSE', 'TEAM', 'EXECUTION'):
            self.assertNotIn('BEGIN GENERATED REVIEW PLANS', (root / 'runtime' / (name + '.md')).read_text())
        files = [root / 'docs/ai/compiled_ai_skills.md'] + list((root / 'references/repository-policy').rglob('*')) + list((root / 'skills').glob('*/SKILL.md'))
        before = {str(p): p.read_bytes() for p in files if p.is_file()}
        generate_entries(root)
        self.assertEqual(before, {p: Path(p).read_bytes() for p in before})
        self.assertEqual(len(self.routes['placements']['policy_pointers']), 12)
        self.assertEqual((root / 'skills/econ-writing/SKILL.md').read_text().count('<!-- BEGIN GENERATED MODES -->'), 1)
        self.assertEqual((root / 'skills/econ-writing/SKILL.md').read_text().count('## Registered operations'), 1)

    def test_new_registry_installed_layout(self):
        root = self.base / 'installed'
        root.mkdir()
        for resource in self.routes['resources'].values():
            source = self.root / resource['source_path']
            if source.is_file():
                target = root / resource['deployment_path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        with patch.object(exporter, 'ROOT', root):
            out = self.output('installed-out', task='econ-writing:revise', layout='installed', output_format='deployed')
        self.assertIn('## Revise for the requested language', (out / '.agents/runtime/PROSE.md').read_text())

    def test_explicit_state_helper_remains_self_contained_in_both_formats(self):
        import hashlib
        import subprocess
        import sys
        for fmt in ('flat', 'deployed'):
            out = self.output(fmt, task='econ-data', conditions=['requested_local_state_helper_operation'], output_format=fmt)
            res = self.routes['resources']['team-state-helper']
            helper = out / res['export_alias' if fmt == 'flat' else 'deployment_path']
            run = subprocess.run([sys.executable, '-B', str(helper), '--help'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            ids = {r['logical_id'] for r in self.manifest(out)['files']}
            self.assertIn('state-contract', ids)
            self.assertIn('team', ids)
            self.assertNotIn('state-tests', ids)
            project = self.base / (fmt + '-project')
            project.mkdir()
            def command(*args):
                result = subprocess.run([sys.executable, '-B', str(helper), '--root', str(project), *args],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            command('init')
            command('add', 'publish', '--owner', 'fixture', '--operation-kind', 'external',
                    '--external-target', 'fixture:result', '--next', 'Record the returned publication',
                    '--required-action', json.dumps({'target_kind': 'object', 'target_id': 'fixture:result', 'operation': 'publish'}))
            command('start', 'publish')
            call_text = json.dumps({'target': 'fixture:result'})
            return_text = json.dumps({'status': 'success', 'target': 'fixture:result'})
            (project / 'returned.json').write_text(json.dumps({
                'event_id': 'fixture-event', 'operation': 'publish', 'target': 'fixture:result', 'status': 'success',
                'tool_name': 'publish', 'tool_call_ref': 'fixture-call', 'tool_return_ref': 'fixture-return',
                'call_args_text': call_text, 'call_args_sha256': hashlib.sha256(call_text.encode()).hexdigest(),
                'return_text': return_text, 'return_sha256': hashlib.sha256(return_text.encode()).hexdigest(),
                'source_verification': {'status': 'matched-to-runtime', 'reference': 'offline-export-fixture', 'verifier_id': 'fixture'},
            }))
            command('action', 'publish', '--target-kind', 'object', '--target-id', 'fixture:result',
                    '--target-version', 'fixture-version', '--operation', 'publish', '--result', 'passed',
                    '--evidence', 'returned.json')
            command('transition', 'publish', 'completed')

    def test_source_distribution_keeps_tools_and_state_tests(self):
        paths = {r['source_path'] for r in self.routes['resources'].values()}
        for path in ('harness/state.py', 'harness/test_state.py', 'scripts/test_export_project.py', 'scripts/test_configuration_tools.py', 'scripts/__init__.py', 'registry/operations.json', 'registry/resources.json', 'registry/placements.json'):
            self.assertIn(path, paths)
            self.assertTrue((self.root / path).is_file())
        for fmt in ('flat', 'deployed'):
            with self.assertRaisesRegex(ValueError, 'complete source distribution'):
                self.output(fmt, task='econ-data', references=['tool-export-project-py'], output_format=fmt)
            self.assertFalse((self.base / fmt).exists())


if __name__ == '__main__': unittest.main(verbosity=2)
