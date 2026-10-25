"""Behavioral tests. Every fixture lives in a newly created temporary project."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("knowledge_write.py").resolve()
spec = importlib.util.spec_from_file_location("knowledge_write", SCRIPT)
kw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kw)
NOTE = "Research_Knowledge/topics/shared.md"


class PublicationTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ.get("KNOWLEDGE_TEST_TMP", str(Path.cwd() / ".knowledge-write-tests"))).resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="knowledge-coordination-test-", dir=scratch)
        self.root = Path(self.temp.name).resolve()
        (self.root / "Research_Knowledge").mkdir()
        self.c = kw.Coordinator(self.root, timeout=2)
        self.write(NOTE, "原始证据\n")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def draft(self, run, name, text):
        path = self.c.folder(run) / "draft" / name
        path.write_text(text, encoding="utf-8")

    def run_for(self, paths, owner="test"):
        run = self.c.begin(owner)["run"]
        self.c.checkout(run, paths)
        return run

    def test_stale_same_file_preserves_first_writer_and_both_drafts(self):
        a, b = self.run_for([NOTE], "writer-a"), self.run_for([NOTE], "writer-b")
        self.draft(a, NOTE, "时间序列补充\n")
        self.draft(b, NOTE, "LASSO补充\n")
        self.c.commit(a)
        with self.assertRaises(kw.WriteError) as caught:
            self.c.commit(b)
        self.assertEqual(caught.exception.code, 3)
        self.assertEqual((self.root / NOTE).read_text(encoding="utf-8"), "时间序列补充\n")
        self.assertEqual((self.c.folder(b) / "draft" / NOTE).read_text(encoding="utf-8"), "LASSO补充\n")
        self.assertEqual((self.c.folder(b) / "base" / NOTE).read_text(encoding="utf-8"), "原始证据\n")
        self.assertEqual((self.c.folder(b) / "conflict" / NOTE).read_text(encoding="utf-8"), "时间序列补充\n")

    def test_simultaneous_creation_of_same_note_is_a_conflict(self):
        name = "Research_Knowledge/papers/new.md"
        a, b = self.run_for([name]), self.run_for([name])
        self.draft(a, name, "第一份新笔记\n")
        self.draft(b, name, "另一份新笔记\n")
        self.c.commit(a)
        with self.assertRaises(kw.WriteError):
            self.c.commit(b)
        self.assertEqual((self.root / name).read_text(encoding="utf-8"), "第一份新笔记\n")

    def test_disjoint_files_can_both_publish(self):
        other = "Research_Knowledge/papers/other.md"
        a, b = self.run_for([NOTE]), self.run_for([other])
        self.draft(a, NOTE, "changed\n")
        self.draft(b, other, "new\n")
        self.c.commit(a)
        self.c.commit(b)
        self.assertEqual((self.root / other).read_text(), "new\n")

    def test_batch_conflict_publishes_no_other_file(self):
        index = "Research_Knowledge/INDEX.md"
        self.write(index, "index before\n")
        run = self.run_for([NOTE, index])
        self.draft(run, NOTE, "my note\n")
        self.draft(run, index, "my index\n")
        self.write(index, "another writer index\n")
        with self.assertRaises(kw.WriteError):
            self.c.commit(run)
        self.assertEqual((self.root / NOTE).read_text(encoding="utf-8"), "原始证据\n")
        self.assertEqual((self.root / index).read_text(), "another writer index\n")

    def test_gitignore_participates_in_same_conflict_check(self):
        self.write(".gitignore", "/*\n")
        run = self.run_for([NOTE, ".gitignore"])
        self.draft(run, NOTE, "changed\n")
        self.draft(run, ".gitignore", "/*\n!/new-note\n")
        self.write(".gitignore", "/*\n!/other-note\n")
        with self.assertRaises(kw.WriteError):
            self.c.commit(run)
        self.assertEqual((self.root / NOTE).read_text(encoding="utf-8"), "原始证据\n")

    def test_repeat_checkout_does_not_destroy_a_draft(self):
        run = self.run_for([NOTE])
        self.draft(run, NOTE, "valuable draft\n")
        with self.assertRaises(kw.WriteError):
            self.c.checkout(run, [NOTE])
        self.assertEqual((self.c.folder(run) / "draft" / NOTE).read_text(), "valuable draft\n")

    def test_recommit_is_idempotent_and_backup_is_retained(self):
        run = self.run_for([NOTE])
        self.draft(run, NOTE, "new\n")
        self.assertEqual(self.c.commit(run)["status"], "committed")
        self.write(NOTE, "later\n")
        self.assertEqual(self.c.commit(run)["status"], "already_committed")
        self.assertEqual((self.root / NOTE).read_text(), "later\n")
        self.assertEqual((self.c.folder(run) / "base" / NOTE).read_text(encoding="utf-8"), "原始证据\n")

    def test_paths_outside_notes_are_rejected(self):
        for name in ("../outside.md", "Research_Knowledge/../INDEX.md", "C:/outside.md",
                     "Research/data.csv", "Research_Knowledge/_work/cache.md",
                     "Research_Knowledge/reproductions/a/local/data.txt", "Research_Knowledge/topics/note.md "):
            with self.subTest(name=name), self.assertRaises(kw.WriteError):
                self.c.target(name)

    def test_case_aliases_are_rejected_before_any_checkout(self):
        run = self.c.begin("aliases")["run"]
        with self.assertRaises(kw.WriteError):
            self.c.checkout(run, [NOTE, "Research_Knowledge/topics/Shared.md"])
        self.assertEqual(self.c.load(run)["entries"], [])

    def test_real_two_process_same_file_race_has_one_winner(self):
        a, b = self.run_for([NOTE]), self.run_for([NOTE])
        self.draft(a, NOTE, "A\n")
        self.draft(b, NOTE, "B\n")
        processes = [subprocess.Popen([sys.executable, str(SCRIPT), "--root", str(self.root), "commit", "--run", run],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8") for run in (a, b)]
        outputs = [p.communicate(timeout=15) for p in processes]
        self.assertEqual(sorted(p.returncode for p in processes), [0, 3], outputs)
        self.assertIn((self.root / NOTE).read_text(), ("A\n", "B\n"))
        states = sorted(self.c.load(run)["state"] for run in (a, b))
        self.assertEqual(states, ["committed", "conflict"])

    def test_lock_timeout_and_release_after_process_termination(self):
        ready = self.root / "lock-ready"
        code = ("import importlib.util,time;from pathlib import Path;"
                f"s=importlib.util.spec_from_file_location('kw',{str(SCRIPT)!r});"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                f"c=m.Coordinator({str(self.root)!r});\n"
                f"with c.lock():\n Path({str(ready)!r}).write_text('ready');time.sleep(30)\n")
        p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 8
            while not ready.exists() and time.monotonic() < deadline and p.poll() is None:
                time.sleep(0.05)
            self.assertTrue(ready.exists())
            with self.assertRaises(kw.WriteError) as caught:
                kw.Coordinator(self.root, timeout=0.05).begin("blocked")
            self.assertEqual(caught.exception.code, 4)
        finally:
            p.terminate()
            p.communicate(timeout=5)
        self.assertEqual(self.c.begin("after terminated writer")["status"], "open")

    def make_interrupted_run(self):
        other = "Research_Knowledge/topics/new.md"
        run = self.run_for([NOTE, other])
        self.draft(run, NOTE, "first published\n")
        self.draft(run, other, "second not yet published\n")
        code = ("import importlib.util,os;"
                f"s=importlib.util.spec_from_file_location('kw',{str(SCRIPT)!r});"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);real=m.atomic_write;\n"
                "def interrupted(path,data):\n real(path,data)\n"
                f" if str(path)=={str(self.root / NOTE)!r}:os._exit(72)\n"
                "m.atomic_write=interrupted\n"
                f"m.Coordinator({str(self.root)!r}).commit({run!r})\n")
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=10)
        self.assertEqual(p.returncode, 72, p.stderr)
        return run, other

    def test_interrupted_batch_blocks_writers_until_recovered(self):
        run, other = self.make_interrupted_run()
        self.assertEqual(self.c.load(run)["state"], "applying")
        with self.assertRaises(kw.WriteError) as caught:
            self.c.begin("later writer")
        self.assertEqual(caught.exception.code, 5)
        self.assertEqual(self.c.recover(run)["status"], "rolled_back")
        self.assertEqual((self.root / NOTE).read_text(encoding="utf-8"), "原始证据\n")
        self.assertFalse((self.root / other).exists())
        self.assertTrue((self.c.folder(run) / "draft" / other).exists())
        self.assertEqual(self.c.begin("can continue")["status"], "open")

    def test_recovery_preserves_external_changes(self):
        run, other = self.make_interrupted_run()
        self.write(NOTE, "external edit after crash\n")
        with self.assertRaises(kw.WriteError) as caught:
            self.c.recover(run)
        self.assertEqual(caught.exception.result["status"], "recovery_conflict")
        self.assertEqual((self.root / NOTE).read_text(), "external edit after crash\n")
        self.assertFalse((self.root / other).exists())

    def test_io_error_rolls_back_batch(self):
        other = "Research_Knowledge/topics/second.md"
        self.write(other, "before\n")
        run = self.run_for([NOTE, other])
        self.draft(run, NOTE, "first\n")
        self.draft(run, other, "second\n")
        real = kw.atomic_write
        failed = False

        def fail_once(path, data):
            nonlocal failed
            if path == self.root / other and not failed:
                failed = True
                raise OSError("simulated disk error")
            real(path, data)

        with patch.object(kw, "atomic_write", fail_once), self.assertRaises(OSError):
            self.c.commit(run)
        self.assertEqual(self.c.load(run)["state"], "rolled_back")
        self.assertEqual((self.root / NOTE).read_text(encoding="utf-8"), "原始证据\n")
        self.assertEqual((self.root / other).read_text(), "before\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
