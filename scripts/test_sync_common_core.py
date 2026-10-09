#!/usr/bin/env python3
"""Real temporary-Git regression cases for explicit common-core ownership."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("sync", Path(__file__).with_name("sync_common_core.py"))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SynchronizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="econ-common-test-")
        self.root = Path(self.temp.name)
        self.source = self.repo("source", "alice/shared")
        self.one = self.repo("one", "bob/same")
        self.two = self.repo("two", "carol/same")
        self.put(self.source, "rules.md", "original\n", commit=True)

    def tearDown(self):
        self.temp.cleanup()

    def command(self, root, *args):
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL).decode().strip()

    def repo(self, folder, name):
        root = self.root / folder
        root.mkdir()
        self.command(root, "init", "-q")
        self.command(root, "config", "user.name", "Test")
        self.command(root, "config", "user.email", "test@example.invalid")
        self.command(root, "config", "core.filemode", "true")
        self.command(root, "remote", "add", "origin", "https://github.com/" + name + ".git")
        self.command(root, "commit", "-qm", "independent start", "--allow-empty")
        return root

    def put(self, root, path, text, commit=False, executable=False):
        destination = root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text)
        destination.chmod(0o755 if executable else 0o644)
        if commit:
            self.command(root, "add", path)
            self.command(root, "commit", "-qm", "change " + path)

    def apply(self, targets=None, **kwargs):
        targets = targets or [self.one]
        paths = kwargs.pop("paths", ["rules.md"])
        preview, _ = sync.synchronize(self.source, targets, paths=paths,
                                      deletes=kwargs.get("deletes", ()), releases=kwargs.get("releases", ()), claims=kwargs.get("claims"),
                                      migrate=kwargs.get("migrate", False))
        expected = {sync.repository(root)[1]: self.command(root, "rev-parse", "HEAD") for root in targets}
        return sync.synchronize(self.source, targets, apply=True, paths=paths, expected=expected,
                                expected_source=self.command(self.source, "rev-parse", "HEAD"),
                                expected_content=preview["common_content_id"], **kwargs)

    def test_arbitrary_owner_same_name_multiple_independent_histories(self):
        self.apply([self.one, self.two])
        self.assertEqual((self.one / "rules.md").read_text(), "original\n")
        self.assertEqual((self.two / "rules.md").read_text(), "original\n")
        self.assertNotEqual(self.command(self.source, "rev-parse", "HEAD"), self.command(self.one, "rev-parse", "HEAD"))

    def test_default_comparison_never_writes(self):
        report, status = sync.synchronize(self.source, [self.one], paths=["rules.md"])
        self.assertEqual(status, 1)
        self.assertFalse(report["applied"])
        self.assertFalse((self.one / "rules.md").exists())

    def test_first_existing_file_requires_matching_explicit_claim(self):
        self.put(self.one, "rules.md", "user\n", commit=True)
        with self.assertRaisesRegex(ValueError, "ownership claim"):
            self.apply()
        claim = {("github.com/bob/same", "rules.md"): sync.fingerprint(sync.snapshot(self.one, self.command(self.one, "rev-parse", "HEAD"), "rules.md"))}
        self.apply(claims=claim)
        self.assertEqual((self.one / "rules.md").read_text(), "original\n")

    def test_committed_custom_change_is_preserved(self):
        self.apply()
        self.put(self.one, "rules.md", "custom committed\n", commit=True)
        self.put(self.source, "rules.md", "source next\n", commit=True)
        with self.assertRaisesRegex(ValueError, "changed since receipt"):
            self.apply()
        self.assertEqual((self.one / "rules.md").read_text(), "custom committed\n")

    def test_uncommitted_custom_change_is_preserved(self):
        self.apply()
        self.put(self.one, "rules.md", "custom dirty\n")
        with self.assertRaisesRegex(ValueError, "changed since receipt"):
            self.apply()
        self.assertEqual((self.one / "rules.md").read_text(), "custom dirty\n")

    def test_uncommitted_deletion_is_preserved(self):
        self.apply()
        (self.one / "rules.md").unlink()
        with self.assertRaisesRegex(ValueError, "changed since receipt"):
            self.apply()
        self.assertFalse((self.one / "rules.md").exists())

    def test_expected_source_and_target_head_required(self):
        source_head = self.command(self.source, "rev-parse", "HEAD")
        target_head = self.command(self.one, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "source HEAD"):
            sync.synchronize(self.source, [self.one], apply=True, paths=["rules.md"])
        with self.assertRaisesRegex(ValueError, "target HEAD"):
            sync.synchronize(self.source, [self.one], apply=True, paths=["rules.md"], expected_source=source_head,
                             expected={"github.com/bob/same": "0" * 40})
        with self.assertRaisesRegex(ValueError, "unselected"):
            sync.synchronize(self.source, [self.one], paths=["rules.md"], expected={"same": target_head})

    def test_dirty_source_needs_reviewed_content_hash(self):
        self.put(self.source, "rules.md", "source working\n")
        with self.assertRaisesRegex(ValueError, "source requires"):
            sync.synchronize(self.source, [self.one], apply=True, paths=["rules.md"],
                             expected_source=self.command(self.source, "rev-parse", "HEAD"),
                             expected={"github.com/bob/same": self.command(self.one, "rev-parse", "HEAD")})
        self.apply()
        self.assertEqual((self.one / "rules.md").read_text(), "source working\n")

    def test_symlinks_and_traversal_are_refused(self):
        (self.one / "rules.md").symlink_to(self.source / "rules.md")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.apply()
        (self.one / "rules.md").unlink()
        self.put(self.source, "inside/rules.md", "nested\n", commit=True)
        (self.one / "inside").symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            sync.synchronize(self.source, [self.one], paths=["inside/rules.md"])
        with self.assertRaisesRegex(ValueError, "Invalid"):
            sync.synchronize(self.source, [self.one], paths=["../escape"])

    def test_rerun_preserves_receipt_and_executable_mode(self):
        self.put(self.source, "rules.md", "executable\n", commit=True, executable=True)
        self.apply()
        receipt = (self.one / sync.RECEIPT_PATH).read_bytes()
        report, status = self.apply()
        self.assertEqual(status, 0)
        self.assertFalse(report["different"])
        self.assertEqual(receipt, (self.one / sync.RECEIPT_PATH).read_bytes())
        self.assertTrue((self.one / "rules.md").stat().st_mode & 0o111)

    def test_explicit_delete_and_move_preserve_unrelated_file(self):
        self.apply()
        (self.source / "rules.md").unlink()
        self.put(self.source, "renamed.md", "new position\n")
        self.command(self.source, "add", "-A")
        self.command(self.source, "commit", "-qm", "move")
        self.put(self.one, "unrelated.md", "private choice\n")
        self.apply(paths=["renamed.md"], deletes=["rules.md"])
        self.assertFalse((self.one / "rules.md").exists())
        self.assertEqual((self.one / "renamed.md").read_text(), "new position\n")
        self.assertEqual((self.one / "unrelated.md").read_text(), "private choice\n")

    def test_mid_apply_change_rolls_back_and_never_commits_receipt(self):
        self.put(self.source, "z.md", "second\n", commit=True)
        original = sync._atomic_write
        calls = []
        def changed(path, data, mode):
            original(path, data, mode)
            calls.append(path)
            if len(calls) == 1:
                self.put(self.one, "z.md", "concurrent user change\n")
        with patch.object(sync, "_atomic_write", changed):
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                self.apply(paths=["rules.md", "z.md"])
        self.assertFalse((self.one / "rules.md").exists())
        self.assertEqual((self.one / "z.md").read_text(), "concurrent user change\n")
        self.assertFalse((self.one / sync.RECEIPT_PATH).exists())

    def test_conflict_in_second_destination_leaves_first_untouched(self):
        self.put(self.two, "rules.md", "existing\n", commit=True)
        with self.assertRaisesRegex(ValueError, "ownership claim"):
            self.apply([self.one, self.two])
        self.assertFalse((self.one / "rules.md").exists())

    def test_receipt_is_credential_and_host_path_free(self):
        self.apply()
        text = (self.one / sync.RECEIPT_PATH).read_text()
        self.assertNotIn(str(self.root), text)
        self.assertNotIn("https://", text)
        self.assertIn("github.com/alice/shared", text)
        self.assertIn("github.com/bob/same", text)
        with self.assertRaisesRegex(ValueError, "Credential"):
            sync.identity("https://token@example.org/team/repo.git")
        self.assertEqual(sync.identity("git@example.org:other/project.git"), "example.org/other/project")

    def test_staged_only_change_is_protected(self):
        self.apply()
        self.command(self.one, "add", "-A")
        self.command(self.one, "commit", "-qm", "adopt")
        self.put(self.one, "rules.md", "staged user choice\n")
        self.command(self.one, "add", "rules.md")
        self.put(self.one, "rules.md", "original\n")
        staged = self.command(self.one, "show", ":rules.md")
        with self.assertRaisesRegex(ValueError, "staged target"):
            self.apply()
        self.assertEqual(staged, self.command(self.one, "show", ":rules.md"))
        self.assertEqual((self.one / "rules.md").read_text(), "original\n")

    def test_filemode_false_content_replay_and_mode_transition_refusal(self):
        self.command(self.one, "config", "core.filemode", "false")
        self.apply()
        self.command(self.one, "add", "-A")
        self.command(self.one, "commit", "-qm", "first")
        self.put(self.source, "rules.md", "new content\n", commit=True)
        self.apply()
        report, _ = self.apply()
        self.assertFalse(report["different"])
        self.put(self.source, "rules.md", "executable\n", commit=True, executable=True)
        with self.assertRaisesRegex(ValueError, "core.filemode=true"):
            self.apply()
        self.assertEqual((self.one / "rules.md").read_text(), "new content\n")

    def test_mid_apply_index_change_preserves_user_index(self):
        self.put(self.source, "z.md", "second\n", commit=True)
        original = sync._atomic_write
        calls = []
        def changed(path, data, mode):
            original(path, data, mode)
            calls.append(path)
            if len(calls) == 1:
                self.put(self.one, "z.md", "new staged user choice\n")
                self.command(self.one, "add", "z.md")
        with patch.object(sync, "_atomic_write", changed):
            with self.assertRaisesRegex(ValueError, "index changed"):
                self.apply(paths=["rules.md", "z.md"])
        self.assertEqual(self.command(self.one, "show", ":z.md"), "new staged user choice")
        self.assertFalse((self.one / "rules.md").exists())

    def test_mid_apply_user_commit_retains_adopted_content(self):
        self.put(self.source, "z.md", "second\n", commit=True)
        original = sync._atomic_write
        calls = []
        def committed(path, data, mode):
            original(path, data, mode)
            calls.append(path)
            if len(calls) == 1:
                self.command(self.one, "add", "rules.md")
                self.command(self.one, "commit", "-qm", "user adopts copied content")
        with patch.object(sync, "_atomic_write", committed):
            with self.assertRaisesRegex(ValueError, "concurrent files retained"):
                self.apply(paths=["rules.md", "z.md"])
        self.assertEqual((self.one / "rules.md").read_text(), "original\n")
        self.assertEqual(self.command(self.one, "show", "HEAD:rules.md"), "original")
        self.assertFalse((self.one / sync.RECEIPT_PATH).exists())

    def test_filemode_false_replay_repairs_existing_tracked_execute_bit(self):
        self.put(self.source, "rules.md", "original\n", commit=True, executable=True)
        self.put(self.one, "rules.md", "original\n", commit=True, executable=True)
        self.command(self.one, "config", "core.filemode", "false")
        claims = {("github.com/bob/same", "rules.md"): sync.fingerprint(sync.snapshot(self.one, self.command(self.one, "rev-parse", "HEAD"), "rules.md"))}
        self.apply(claims=claims)
        (self.one / "rules.md").chmod(0o644)
        self.apply()
        self.assertTrue((self.one / "rules.md").stat().st_mode & 0o111)
        report, _ = self.apply()
        self.assertFalse(report["different"])

    def test_release_keeps_local_runtime_and_index_and_prevents_readoption(self):
        self.put(self.source, "local.json", "public initial definition\n", commit=True)
        self.apply(paths=["rules.md", "local.json"])
        self.command(self.one, "add", "-A")
        self.command(self.one, "commit", "-qm", "initial adopted definition")
        self.put(self.one, "local.json", "private manual setting\n")
        self.command(self.one, "add", "local.json")
        staged = self.command(self.one, "show", ":local.json")
        self.apply(paths=[], releases=["local.json"])
        self.assertEqual((self.one / "local.json").read_text(), "private manual setting\n")
        self.assertEqual(self.command(self.one, "show", ":local.json"), staged)
        receipt = sync.read_receipt((self.one / sync.RECEIPT_PATH).read_bytes())[1]
        self.assertIn("local.json", receipt["released_paths"])
        self.assertNotIn("local.json", [row["path"] for row in receipt["paths"]])
        self.put(self.source, "rules.md", "next shared rule\n", commit=True)
        self.apply()
        self.assertEqual((self.one / "local.json").read_text(), "private manual setting\n")
        with self.assertRaisesRegex(ValueError, "Previously released"):
            self.apply(paths=["local.json"])

    def test_legacy_receipt_migration_checks_historical_blob_and_mode(self):
        state = sync.snapshot(self.source, self.command(self.source, "rev-parse", "HEAD"), "rules.md")
        legacy = {"source_repository": "alice/shared", "source_base_commit": self.command(self.source, "rev-parse", "HEAD"),
                  "paths": [{"path": "rules.md", "git_blob": state["git_blob"], "sha256": state["sha256"]}]}
        data = sync.receipt_bytes(b"# Project\n", legacy).replace(sync.RECEIPT_START.encode(), sync.LEGACY_START.encode()).replace(sync.RECEIPT_END.encode(), sync.LEGACY_END.encode())
        self.put(self.one, "rules.md", "original\n")
        (self.one / "docs/ai").mkdir(parents=True)
        (self.one / sync.RECEIPT_PATH).write_bytes(data)
        with self.assertRaisesRegex(ValueError, "migrate-receipt"):
            self.apply()
        self.put(self.source, "rules.md", "next source\n", commit=True)
        self.apply(migrate=True)
        self.assertIn(sync.RECEIPT_START, (self.one / sync.RECEIPT_PATH).read_text())
        self.assertEqual((self.one / "rules.md").read_text(), "next source\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
