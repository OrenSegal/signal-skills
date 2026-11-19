"""scoreboard_report.py end to end, against a scratch ledger."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _loader import REPO_ROOT

PODCAST = REPO_ROOT / "plugins" / "podcast"


class ScoreboardReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = {**os.environ, "SIGNAL_SKILLS_HOME": str(self.home / "data")}

    def run_script(self, script, *args):
        return subprocess.run([sys.executable, str(PODCAST / script), *args],
                              capture_output=True, text=True, env=self.env)

    def record(self, show, episode, predictions):
        result = self.run_script("ledger.py", "record", "--show", show, "--episode", episode,
                                 "--predictions-json", json.dumps(predictions))
        self.assertEqual(result.returncode, 0, result.stderr)

    def confirm(self, show, episode, text, status="confirmed"):
        result = self.run_script("ledger.py", "check-prediction", "--show", show, "--episode", episode,
                                 "--text", text, "--status", status)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_renders_html_and_markdown(self):
        self.record("Show One", "ep1", ["prices fall by half", "agents replace forms"])
        self.confirm("Show One", "ep1", "prices")
        self.confirm("Show One", "ep1", "agents", status="failed")
        html, md = self.home / "board.html", self.home / "board.md"
        result = self.run_script("scoreboard_report.py", str(html), str(md))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Show One: 1/2 calls confirmed", md.read_text())
        self.assertIn("50%", html.read_text())

    def test_em_dash_in_a_show_name_or_prediction_does_not_block_the_report(self):
        # Show names and quoted predictions are data from the ledger, not copy the
        # agent wrote. The renderer's em-dash rule must not make them unpublishable.
        self.record("The Daily — Tech", "ep1", ["GPT prices will fall by half — soon"])
        self.confirm("The Daily — Tech", "ep1", "GPT")
        out = self.home / "board.md"
        result = self.run_script("scoreboard_report.py", str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        text = out.read_text()
        self.assertNotIn("—", text)
        self.assertIn("The Daily, Tech: 1/1 calls confirmed", text)
        self.assertIn("GPT prices will fall by half, soon", text)

    def test_nothing_recorded_exits_with_a_message(self):
        result = self.run_script("scoreboard_report.py", str(self.home / "board.html"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("nothing to grade", result.stderr)


if __name__ == "__main__":
    unittest.main()
