"""Mechanical and phrase regression tests; no model-response performance is inferred."""
from __future__ import annotations
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ai_tools as ai  # noqa: E402
import style_guard as guard  # noqa: E402

class ConfigurationTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.root = self.folder / 'root'
        self.root.mkdir()
        for relative in ['.agents/skills', 'docs/ai']:
            shutil.copytree(ROOT / relative, self.root / relative)
        (self.root / 'scripts').mkdir()
        for path in (ROOT / 'scripts').glob('*.py'):
            shutil.copy2(path, self.root / 'scripts' / path.name)
        for relative in ['.cursorrules', 'AGENTS.md', 'CLAUDE.md', 'CODEX.md']:
            if (ROOT / relative).is_file():
                shutil.copy2(ROOT / relative, self.root / relative)

    def change(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def test_configuration(self):
        self.assertEqual(ai.check(self.root), [])

    def test_ten_skills(self):
        self.assertEqual(len(ai.names(self.root)), 10)

    def test_duplicate_registry(self):
        self.change('docs/ai/skills.json', json.dumps({'schema': 1, 'skills': [ai.STYLE, ai.STYLE]}))
        self.assertTrue(ai.check(self.root))

    def test_invalid_registry(self):
        self.change('docs/ai/skills.json', json.dumps({'schema': 1, 'skills': ['../x']}))
        self.assertTrue(ai.check(self.root))

    def test_policy_budget(self):
        self.change('.cursorrules', ai.STYLE + 'x' * 3000)
        self.assertTrue(ai.check(self.root))

    def test_project_budget_crlf(self):
        self.change('docs/ai/project_instructions.txt', 'ECON_ASSERTIVE.md\n' + 'a\n' * 3000)
        self.assertTrue(ai.check(self.root))

    def test_skill_budget(self):
        name = '.agents/skills/econ-paper/SKILL.md'
        self.change(name, ai.read(self.root, name) + 'x' * 3000)
        self.assertTrue(ai.check(self.root))

    def test_style_policy_required(self):
        self.change('.cursorrules', '# Policy\n')
        self.assertTrue(ai.check(self.root))

    def test_style_prompt_required(self):
        self.change('docs/ai/project_instructions.txt', '# Project\n')
        self.assertTrue(ai.check(self.root))

    def test_every_task_trigger(self):
        for name in ai.names(self.root):
            if name != ai.STYLE:
                self.assertIn(ai.TRIGGER, ai.read(self.root, f'.agents/skills/{name}/SKILL.md'))

    def test_missing_task_trigger(self):
        name = '.agents/skills/econ-paper/SKILL.md'
        self.change(name, ai.read(self.root, name).replace(ai.TRIGGER, 'Use any style'))
        self.assertTrue(ai.check(self.root))

    def test_postdraft_stage_required(self):
        name = '.agents/skills/econ-assertive/SKILL.md'
        self.change(name, ai.read(self.root, name).replace('Stage 2:', 'Final section:'))
        self.assertTrue(ai.check(self.root))

    def test_metadata_mismatch(self):
        name = '.agents/skills/econ-paper/SKILL.md'
        self.change(name, ai.read(self.root, name).replace('name: econ-paper', 'name: other'))
        self.assertTrue(ai.check(self.root))

    def test_broken_reference(self):
        name = '.agents/skills/econ-paper/SKILL.md'
        self.change(name, ai.read(self.root, name) + '\n[ref](absent.md)\n')
        self.assertTrue(ai.check(self.root))

    def test_path_traversal(self):
        for name in ['../x', '/x', 'a/../b', '.git/config', 'C:\\x', 'a//b']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                ai.safe(self.root, name)

    def test_symlink(self):
        path = self.root / '.agents/skills/econ-paper/SKILL.md'
        path.unlink()
        path.symlink_to(self.root / '.cursorrules')
        self.assertTrue(ai.check(self.root))

    def test_bridge(self):
        path = self.folder / 'bridge'
        m = ai.export(self.root, path, 'bridge')
        self.assertEqual(m['skills'], [ai.STYLE])
        self.assertEqual(ai.verify(path)['verified_files'], 7)
        self.assertIn('python STYLE_GUARD.py', (path / 'ECON_ASSERTIVE.md').read_text())

    def test_standalone(self):
        path = self.folder / 'all'
        m = ai.export(self.root, path, 'standalone')
        self.assertEqual(len(m['skills']), 10)
        self.assertEqual(ai.verify(path)['verified_files'], 20)

    def test_selection_adds_style(self):
        m = ai.export(self.root, self.folder / 'one', 'standalone', ['econ-paper'])
        self.assertEqual(m['skills'], ['econ-paper', ai.STYLE])

    def test_selection_no_duplicate_style(self):
        m = ai.export(self.root, self.folder / 'one', 'standalone', ['econ-paper', ai.STYLE])
        self.assertEqual(m['skills'].count(ai.STYLE), 1)

    def test_invalid_selection(self):
        for selected in [[], ['bad'], [ai.STYLE, ai.STYLE]]:
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                ai.export(self.root, self.folder / 'bad', 'standalone', selected)

    def test_existing_export_preserved(self):
        target = self.folder / 'exists'
        target.mkdir()
        (target / 'user.txt').write_text('keep')
        with self.assertRaises(ValueError):
            ai.export(self.root, target, 'bridge')
        self.assertEqual((target / 'user.txt').read_text(), 'keep')

    def test_export_tamper(self):
        target = self.folder / 'export'
        ai.export(self.root, target, 'bridge')
        (target / 'ECON_ASSERTIVE.md').write_text('changed')
        with self.assertRaises(ValueError):
            ai.verify(target)

    def test_export_extra_file(self):
        target = self.folder / 'export'
        ai.export(self.root, target, 'bridge')
        (target / 'extra.txt').write_text('extra')
        with self.assertRaises(ValueError):
            ai.verify(target)

    def test_export_inside_source_rejected(self):
        with self.assertRaises(ValueError):
            ai.export(self.root, self.root / 'exported', 'bridge')
        self.assertFalse((self.root / 'exported').exists())

    def test_long_skill_name_rejected(self):
        self.change('docs/ai/skills.json', json.dumps({'schema': 1, 'skills': [ai.STYLE, 'a' * 65]}))
        self.assertTrue(ai.check(self.root))

    def test_file_layer_revision(self):
        self.assertIsNone(ai.revision(self.root)['observed_commit'])

    def test_size_basis(self):
        b = ai.budget(self.root)
        self.assertEqual(b['prose_startup_basis']['utf8_bytes'], b['startup_basis']['utf8_bytes'] + b['default_style']['utf8_bytes'])
        self.assertNotIn('tokens', b['policy'])

class PhraseTests(unittest.TestCase):

    def test_japanese_candidates(self):
        for text in ['ただし、注意が必要である。', 'とはいえ、結果は限定的である。', '念のため記す。', 'あくまで一つの結果である。', 'その可能性を否定できない。', 'これだけで有効とまでは言えない。']:
            with self.subTest(text=text):
                self.assertTrue(guard.scan(text))

    def test_english_candidates(self):
        for text in ['However, X.', 'Although useful, X.', 'This may potentially suggest X.', 'It should be noted that X.', 'This does not imply Y.']:
            with self.subTest(text=text):
                self.assertTrue(guard.scan(text))

    def test_direct_measurement(self):
        self.assertEqual(guard.scan('アウトカムは犯罪認知件数である。'), [])

    def test_estimate(self):
        self.assertEqual(guard.scan('The estimated effect is 1.2 percentage points (95% CI: [-0.8, 3.2]).'), [])

    def test_technical_negative(self):
        self.assertEqual(guard.scan('The model has no equilibrium. The null is not rejected at p = 0.21.'), [])

    def test_mathematical_condition(self):
        self.assertEqual(guard.scan('The equilibrium exists if and only if alpha > 0.'), [])

    def test_math_protection(self):
        self.assertEqual(guard.scan('\\[\\text{however}\\] $\\text{ただし}$'), [])

    def test_quote_protection(self):
        self.assertEqual(guard.scan('The source says "however". 原文は「ただし」で始まる。', skip_quotes=True), [])

    def test_blockquote_protection(self):
        self.assertEqual(guard.scan('> However, X.\nThe source reports Y.', skip_quotes=True), [])

    def test_generated_quote_scanned(self):
        self.assertTrue(guard.scan('"However, X."'))

    def test_generated_blockquote_scanned(self):
        self.assertTrue(guard.scan('> However, X.'))

    def test_generated_tex_quote_scanned(self):
        self.assertTrue(guard.scan('\\begin{quote}However, X.\\end{quote}', tex=True))

    def test_verified_tex_quote_protected(self):
        self.assertEqual(guard.scan('\\begin{quote}However, X.\\end{quote}', tex=True, skip_quotes=True), [])

    def test_code_protection(self):
        self.assertEqual(guard.scan('```python\n# however\nprint("ただし")\n```'), [])

    def test_percent_not_comment(self):
        self.assertTrue(guard.scan('The effect is 5%. However, X.'))

    def test_tex_comment(self):
        self.assertEqual(guard.scan('% However, X.\nThe effect is 5\\%.', tex=True), [])

    def test_line_locations(self):
        found = guard.scan('```r\nx <- 1\n```\nHowever, X.\nただし、Y。')
        self.assertEqual([r['line'] for r in found], [4, 5])

    def test_detector_readonly(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'draft.md'
            p.write_text('However, X.\n')
            before = p.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(guard.main([str(p)]), 1)
            self.assertEqual(p.read_bytes(), before)

    def test_clean_scan_still_semantic_review(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'draft.md'
            p.write_text('The estimate is 2.\n')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(guard.main([str(p)]), 0)
            self.assertTrue(json.loads(output.getvalue())['semantic_review_required'])
if __name__ == '__main__':
    unittest.main()
