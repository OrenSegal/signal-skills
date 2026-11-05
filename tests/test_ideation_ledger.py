import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _loader import load

ledger = load("ideation", "ledger.py")


class IdeationLedger(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self._orig = ledger.IDEAS_PATH
        ledger.IDEAS_PATH = Path(tmp.name) / "state" / "ideas.json"
        self.addCleanup(setattr, ledger, "IDEAS_PATH", self._orig)

    def run_cmd(self, func, **kw):
        out = io.StringIO()
        with redirect_stdout(out):
            func(argparse.Namespace(**kw))
        return out.getvalue()

    def propose(self, title):
        return self.run_cmd(ledger.cmd_propose, title=title, citations_json='["ep1"]', note="")

    def test_same_title_is_not_proposed_twice(self):
        self.assertIn("proposed", self.propose("Offline Mode"))
        self.assertIn("already proposed", self.propose("offline  mode!"))
        self.assertEqual(len(ledger.load_ideas()["ideas"]), 1)

    def test_status_filter_and_update(self):
        self.propose("Offline Mode")
        self.propose("Dark Theme")
        self.run_cmd(ledger.cmd_set_status, title="Dark Theme", status="shipped")
        listed = json.loads(self.run_cmd(ledger.cmd_list, status="proposed"))
        self.assertEqual([i["slug"] for i in listed], ["offline-mode"])

    def test_invalid_status_and_unknown_idea_exit_1(self):
        self.propose("Offline Mode")
        for title, status in (("Offline Mode", "done"), ("Nope", "shipped")):
            with self.assertRaises(SystemExit) as cm:
                ledger.cmd_set_status(argparse.Namespace(title=title, status=status))
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
