import argparse
import datetime
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _loader import load

ledger = load("podcast", "ledger.py")


class IsolatedState(unittest.TestCase):
    """Point the module's STATE_DIR/CONFIG_PATH at a scratch dir per test,
    since these are read at module scope and every cmd_* function uses them
    as globals."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self._orig_state_dir = ledger.STATE_DIR
        self._orig_config_path = ledger.CONFIG_PATH
        ledger.STATE_DIR = root / "state"
        ledger.CONFIG_PATH = root / "config.json"
        ledger.STATE_DIR.mkdir(parents=True)

    def tearDown(self):
        ledger.STATE_DIR = self._orig_state_dir
        ledger.CONFIG_PATH = self._orig_config_path

    def run_cmd(self, func, **kwargs):
        buf = io.StringIO()
        with redirect_stdout(buf):
            func(argparse.Namespace(**kwargs))
        return buf.getvalue()

    def write_show(self, slug, data):
        ledger.save_json(ledger.show_path(slug), data)


class Slugify(unittest.TestCase):
    def test_lowercases_and_dashes_punctuation(self):
        self.assertEqual(ledger.slugify("The Vergecast!"), "the-vergecast")

    def test_collapses_multiple_separators(self):
        self.assertEqual(ledger.slugify("A -- B__C"), "a-b-c")

    def test_empty_falls_back_to_show(self):
        self.assertEqual(ledger.slugify("   "), "show")


class Keywords(unittest.TestCase):
    def test_drops_stopwords_and_short_words(self):
        kw = ledger._keywords("This is the best pricing model for AI tools")
        self.assertIn("pricing", kw)
        self.assertIn("model", kw)
        self.assertIn("tools", kw)
        self.assertNotIn("this", kw)
        self.assertNotIn("for", kw)
        self.assertNotIn("ai", kw)  # length <= 3 dropped


class RecordAndMined(IsolatedState):
    def test_record_then_mined_lists_episode(self):
        self.run_cmd(
            ledger.cmd_record,
            show="The Vergecast",
            episode="ep1",
            date="2026-01-01",
            findings_path="",
            findings_json=json.dumps([{"claim": "x", "tag": "measured", "topic": "pricing"}]),
            predictions_json=json.dumps(["GPT-5 ships in June"]),
        )
        out = self.run_cmd(ledger.cmd_mined, show="The Vergecast")
        self.assertEqual(json.loads(out), ["ep1"])

    def test_record_prediction_defaults(self):
        self.run_cmd(
            ledger.cmd_record,
            show="Show A",
            episode="ep1",
            date="",
            findings_path="",
            findings_json="[]",
            predictions_json=json.dumps([{"text": "X happens", "speaker": "Guest"}]),
        )
        show = ledger.load_show("show-a")
        pred = show["episodes"]["ep1"]["predictions"][0]
        self.assertEqual(pred["text"], "X happens")
        self.assertEqual(pred["speaker"], "Guest")
        self.assertEqual(pred["status"], "open")


class Query(IsolatedState):
    def setUp(self):
        super().setUp()
        self.write_show("show-a", {
            "show": "Show A",
            "episodes": {
                "ep1": {"date": "2026-01-01", "findings": [
                    {"claim": "price up", "tag": "measured", "topic": "pricing"},
                    {"claim": "rumor", "tag": "speculative", "topic": "hardware"},
                ]},
                "ep2": {"date": "2026-02-01", "findings": [
                    {"claim": "old news", "tag": "measured", "topic": "pricing"},
                ]},
            },
        })

    def test_filters_by_topic(self):
        out = json.loads(self.run_cmd(ledger.cmd_query, show=None, topic="pricing", tag=None, since=None))
        self.assertEqual(len(out), 2)
        self.assertTrue(all(f["topic"] == "pricing" for f in out))

    def test_filters_by_tag(self):
        out = json.loads(self.run_cmd(ledger.cmd_query, show=None, topic=None, tag="speculative", since=None))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["claim"], "rumor")

    def test_filters_by_since(self):
        out = json.loads(self.run_cmd(ledger.cmd_query, show=None, topic=None, tag=None, since="2026-02-01"))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["claim"], "old news")

    def test_sorted_newest_first(self):
        out = json.loads(self.run_cmd(ledger.cmd_query, show=None, topic="pricing", tag=None, since=None))
        self.assertEqual([f["date"] for f in out], ["2026-02-01", "2026-01-01"])


class Scoreboard(IsolatedState):
    def setUp(self):
        super().setUp()
        self.write_show("show-a", {
            "show": "Show A",
            "episodes": {
                "ep1": {"predictions": [
                    {"status": "confirmed", "speaker": "Alice"},
                    {"status": "failed", "speaker": "Alice"},
                    {"status": "confirmed", "speaker": "Bob"},
                    {"status": "open", "speaker": "Bob"},
                ]},
            },
        })

    def test_hit_rate_by_show(self):
        out = json.loads(self.run_cmd(ledger.cmd_scoreboard, by_guest=False))
        row = next(r for r in out if r["show"] == "Show A")
        self.assertEqual(row["confirmed"], 2)
        self.assertEqual(row["failed"], 1)
        self.assertEqual(row["hit_rate"], round(2 / 3, 2))

    def test_hit_rate_by_guest(self):
        out = json.loads(self.run_cmd(ledger.cmd_scoreboard, by_guest=True))
        alice = next(r for r in out if r["by_guest"] == "Alice")
        bob = next(r for r in out if r["by_guest"] == "Bob")
        self.assertEqual(alice["hit_rate"], 0.5)  # 1 confirmed, 1 failed
        self.assertEqual(bob["hit_rate"], 1.0)  # 1 confirmed, 0 failed, 1 open (untested)


class ScoreboardUntested(IsolatedState):
    def test_no_tested_predictions_gives_none_rate(self):
        self.write_show("show-b", {
            "show": "Show B",
            "episodes": {"ep1": {"predictions": [{"status": "open", "speaker": None}]}},
        })
        out = json.loads(self.run_cmd(ledger.cmd_scoreboard, by_guest=False))
        row = next(r for r in out if r["show"] == "Show B")
        self.assertIsNone(row["hit_rate"])


class StaleSweep(IsolatedState):
    def setUp(self):
        super().setUp()
        old_date = (datetime.date.today() - datetime.timedelta(weeks=10)).isoformat()
        recent_date = datetime.date.today().isoformat()
        self.write_show("show-a", {
            "show": "Show A",
            "episodes": {
                "ep1": {"predictions": [
                    {"text": "old open pred", "status": "open", "made_at": old_date, "checked_at": None},
                    {"text": "recent pred", "status": "open", "made_at": recent_date, "checked_at": None},
                ]},
            },
        })

    def test_dry_run_does_not_write(self):
        out = json.loads(self.run_cmd(ledger.cmd_stale_sweep, weeks=8, show=None, dry_run=True))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "old open pred")
        show = ledger.load_show("show-a")
        self.assertEqual(show["episodes"]["ep1"]["predictions"][0]["status"], "open")

    def test_non_dry_run_flags_stale(self):
        self.run_cmd(ledger.cmd_stale_sweep, weeks=8, show=None, dry_run=False)
        show = ledger.load_show("show-a")
        preds = {p["text"]: p["status"] for p in show["episodes"]["ep1"]["predictions"]}
        self.assertEqual(preds["old open pred"], "stale")
        self.assertEqual(preds["recent pred"], "open")


class GradeCandidates(IsolatedState):
    def test_excludes_too_recent_and_sorts_oldest_first(self):
        d1 = (datetime.date.today() - datetime.timedelta(weeks=6)).isoformat()
        d2 = (datetime.date.today() - datetime.timedelta(weeks=3)).isoformat()
        d3 = datetime.date.today().isoformat()
        self.write_show("show-a", {
            "show": "Show A",
            "episodes": {
                "ep1": {"predictions": [
                    {"text": "oldest", "status": "open", "made_at": d1},
                    {"text": "middling", "status": "open", "made_at": d2},
                    {"text": "too fresh", "status": "open", "made_at": d3},
                ]},
            },
        })
        out = json.loads(self.run_cmd(ledger.cmd_grade_candidates, min_weeks=2, limit=10))
        self.assertEqual([p["text"] for p in out], ["oldest", "middling"])


class Dedup(IsolatedState):
    def test_cross_show_overlap_detected_same_show_excluded(self):
        self.write_show("show-a", {
            "show": "Show A",
            "episodes": {"ep1": {"predictions": [
                {"text": "pricing will drop significantly next quarter", "status": "open", "made_at": "2026-01-01"},
                {"text": "pricing will drop significantly next quarter too", "status": "open", "made_at": "2026-01-02"},
            ]}},
        })
        self.write_show("show-b", {
            "show": "Show B",
            "episodes": {"ep1": {"predictions": [
                {"text": "pricing will drop significantly soon", "status": "open", "made_at": "2026-01-01"},
            ]}},
        })
        out = json.loads(self.run_cmd(ledger.cmd_dedup, threshold=0.5))
        shows_in_pairs = {(p["a"]["show"], p["b"]["show"]) for p in out}
        self.assertIn(("Show A", "Show B"), shows_in_pairs)
        for p in out:
            self.assertNotEqual(p["a"]["show"], p["b"]["show"])

    def test_no_overlap_below_threshold(self):
        self.write_show("show-a", {
            "show": "Show A",
            "episodes": {"ep1": {"predictions": [{"text": "completely unrelated claim about weather", "status": "open", "made_at": "2026-01-01"}]}},
        })
        self.write_show("show-b", {
            "show": "Show B",
            "episodes": {"ep1": {"predictions": [{"text": "totally different topic regarding sports", "status": "open", "made_at": "2026-01-01"}]}},
        })
        out = json.loads(self.run_cmd(ledger.cmd_dedup, threshold=0.5))
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
