import argparse
import datetime
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from _loader import REPO_ROOT, load

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

    def test_output_independent_of_filesystem_order(self):
        # glob() order is filesystem-dependent (sorted-looking on APFS,
        # hash/creation order on ext4). Force both orders and require the
        # same output, so pair orientation can't flip between machines.
        self.write_show("show-a", {
            "show": "Show A",
            "episodes": {"ep1": {"predictions": [
                {"text": "pricing will drop significantly next quarter", "status": "open", "made_at": "2026-01-01"},
            ]}},
        })
        self.write_show("show-b", {
            "show": "Show B",
            "episodes": {"ep1": {"predictions": [
                {"text": "pricing will drop significantly soon", "status": "open", "made_at": "2026-01-01"},
            ]}},
        })
        real_glob = Path.glob
        outputs = []
        for reverse in (False, True):
            def ordered_glob(path, pattern, _reverse=reverse):
                return iter(sorted(real_glob(path, pattern), reverse=_reverse))
            with mock.patch.object(Path, "glob", ordered_glob):
                outputs.append(json.loads(self.run_cmd(ledger.cmd_dedup, threshold=0.5)))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual([(p["a"]["show"], p["b"]["show"]) for p in outputs[1]],
                         [("Show A", "Show B")])

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


class StateLocationTest(unittest.TestCase):
    """State must not live in the install folder, and state written there by
    an earlier version must be carried over once."""

    def test_state_is_outside_the_install_folder(self):
        for plugin in ("podcast", "review-scout", "ideation"):
            mod = load(plugin, "ledger.py")
            self.assertNotIn(mod.ROOT, mod.CONFIG_PATH.parents, plugin)
            self.assertEqual(mod.CONFIG_PATH.parent.name, plugin)

    def test_legacy_state_is_copied_once_and_left_in_place(self):
        for plugin in ("podcast", "review-scout", "ideation"):
            mod = load(plugin, "ledger.py")
            with tempfile.TemporaryDirectory() as tmp:
                old, new = Path(tmp) / "old", Path(tmp) / "data" / plugin
                (old / "state").mkdir(parents=True)
                (old / "state" / "a.json").write_text('{"k": 1}')
                (old / "config.json").write_text('{"pref": "x"}')
                self.assertEqual(mod.migrate_legacy(new, [Path(tmp) / "missing", old]), old)
                self.assertEqual(json.loads((new / "state" / "a.json").read_text()), {"k": 1})
                self.assertEqual(json.loads((new / "config.json").read_text()), {"pref": "x"})
                self.assertTrue((old / "state" / "a.json").exists())
                (new / "config.json").write_text('{"pref": "changed"}')
                self.assertIsNone(mod.migrate_legacy(new, [old]))
                self.assertEqual(json.loads((new / "config.json").read_text()), {"pref": "changed"})

    def test_nothing_is_created_when_there_is_no_legacy_state(self):
        mod = load("podcast", "ledger.py")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(mod.migrate_legacy(Path(tmp) / "data", [Path(tmp) / "none"]))
            self.assertFalse((Path(tmp) / "data").exists())

    def test_no_command_in_a_skill_file_names_a_fixed_install_path(self):
        for path in sorted((REPO_ROOT / "plugins").glob("*/*.md")):
            self.assertNotIn("~/.claude/skills", path.read_text(encoding="utf-8"), path)


if __name__ == "__main__":
    unittest.main()


class EpisodeDates(IsolatedState):
    """resolve.py used to hand back RSS dates ("Mon, 03 Nov 2025"), and the
    ledger stored whatever it was given. `query --since` and the newest-first
    sort compare dates as strings, so they need ISO dates on both sides."""

    def record(self, episode, date):
        self.run_cmd(ledger.cmd_record, show="Show", episode=episode, date=date, findings_path="",
                     findings_json=json.dumps([{"claim": episode, "tag": "measured", "topic": "pricing"}]),
                     predictions_json="[]")

    def query(self, since=None):
        return json.loads(self.run_cmd(ledger.cmd_query, show=None, topic=None, tag=None, since=since))

    def test_iso_date_normalizes_rss_and_iso_forms(self):
        for raw in ("Mon, 03 Nov 2025", "Mon, 03 Nov 2025 09:30:00 GMT", "3 Nov 2025", "2025-11-03",
                    "2025-11-03T09:30:00Z"):
            self.assertEqual(ledger.iso_date(raw), "2025-11-03", raw)

    def test_iso_date_leaves_unparseable_text_alone(self):
        self.assertEqual(ledger.iso_date("sometime last fall"), "sometime last fall")
        self.assertEqual(ledger.iso_date(""), "")

    def test_record_stores_an_rss_date_as_iso(self):
        self.record("old", "Mon, 03 Nov 2025")
        self.assertEqual(ledger.load_show("show")["episodes"]["old"]["date"], "2025-11-03")

    def test_since_excludes_an_older_episode_recorded_with_an_rss_date(self):
        self.record("old", "Mon, 03 Nov 2025")
        self.record("new", "Fri, 10 Jul 2026")
        self.assertEqual([f["episode"] for f in self.query(since="2026-01-01")], ["new"])

    def test_since_and_sort_work_on_rss_dates_already_in_a_state_file(self):
        self.write_show("show", {"show": "Show", "episodes": {
            "old": {"date": "Mon, 03 Nov 2025", "findings": [{"claim": "old", "tag": "measured", "topic": "x"}]},
            "new": {"date": "Fri, 10 Jul 2026", "findings": [{"claim": "new", "tag": "measured", "topic": "x"}]},
        }})
        self.assertEqual([f["episode"] for f in self.query()], ["new", "old"])
        self.assertEqual([f["date"] for f in self.query(since="2026-01-01")], ["2026-07-10"])


class ReRecord(IsolatedState):
    """Recording an episode a second time (a re-mine, or a retry after a
    failed run) must not throw away what was already graded."""

    def record(self, predictions):
        self.run_cmd(ledger.cmd_record, show="Show", episode="ep1", date="2026-01-05", findings_path="",
                     findings_json="[]", predictions_json=json.dumps(predictions))

    def test_resolved_prediction_keeps_its_status_and_evidence(self):
        self.record(["prices fall by half", {"text": "agents replace forms", "speaker": "Guest"}])
        self.run_cmd(ledger.cmd_check_prediction, show="Show", episode="ep1", text="prices",
                     status="confirmed", source_url="https://example.com/evidence")
        ledger.load_show("show")  # sanity: file is readable
        self.record(["Prices fall by half ", {"text": "agents replace forms", "speaker": "Guest"}, "a new call"])
        preds = {p["text"].strip().lower(): p for p in ledger.load_show("show")["episodes"]["ep1"]["predictions"]}
        kept = preds["prices fall by half"]
        self.assertEqual((kept["status"], kept["source_url"]), ("confirmed", "https://example.com/evidence"))
        self.assertIsNotNone(kept["checked_at"])
        self.assertEqual(preds["agents replace forms"]["status"], "open")
        self.assertEqual(preds["a new call"]["status"], "open")

    def test_made_at_survives_a_re_record(self):
        self.write_show("show", {"show": "Show", "episodes": {"ep1": {"date": "2026-01-05", "predictions": [
            {"text": "prices fall by half", "speaker": None, "status": "open", "made_at": "2026-01-06",
             "checked_at": None, "source_url": None}]}}})
        self.record(["prices fall by half"])
        self.assertEqual(ledger.load_show("show")["episodes"]["ep1"]["predictions"][0]["made_at"], "2026-01-06")


class AtomicSave(IsolatedState):
    def test_a_failed_write_leaves_the_previous_file_intact(self):
        path = ledger.show_path("show")
        ledger.save_json(path, {"show": "Show", "episodes": {"ep1": {}}})
        with self.assertRaises(TypeError):
            ledger.save_json(path, {"show": "Show", "episodes": {"ep1": {}, "ep2": object()}})
        self.assertEqual(ledger.load_json(path, None), {"show": "Show", "episodes": {"ep1": {}}})
        self.assertEqual([p.name for p in path.parent.iterdir()], ["show.json"])


class Boundaries(IsolatedState):
    """Pin the edges: a prediction exactly --min-weeks old is gradeable, one
    exactly --weeks old is not yet stale, and a dedup score equal to the
    threshold counts."""

    def write_pred(self, weeks_old):
        made_at = (datetime.date.today() - datetime.timedelta(weeks=weeks_old)).isoformat()
        self.write_show("show-a", {"show": "Show A", "episodes": {"ep1": {"predictions": [
            {"text": "edge prediction", "status": "open", "made_at": made_at, "checked_at": None}]}}})

    def test_prediction_exactly_min_weeks_old_is_a_grade_candidate(self):
        self.write_pred(2)
        out = json.loads(self.run_cmd(ledger.cmd_grade_candidates, min_weeks=2, limit=10))
        self.assertEqual([p["text"] for p in out], ["edge prediction"])

    def test_prediction_exactly_weeks_old_is_not_stale_yet(self):
        self.write_pred(8)
        self.assertEqual(json.loads(self.run_cmd(ledger.cmd_stale_sweep, weeks=8, show=None, dry_run=True)), [])

    def test_dedup_score_equal_to_the_threshold_is_reported(self):
        # 2 of 4 keywords shared: score exactly 0.5
        self.write_show("show-a", {"show": "Show A", "episodes": {"e": {"predictions": [
            {"text": "pricing agents alpha beta", "status": "open", "made_at": "2026-01-01"}]}}})
        self.write_show("show-b", {"show": "Show B", "episodes": {"e": {"predictions": [
            {"text": "pricing agents gamma delta", "status": "open", "made_at": "2026-01-01"}]}}})
        out = json.loads(self.run_cmd(ledger.cmd_dedup, threshold=0.5))
        self.assertEqual([p["score"] for p in out], [0.5])
