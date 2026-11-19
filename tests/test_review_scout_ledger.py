import argparse
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from _loader import load

ledger = load("review-scout", "ledger.py")


class IsolatedState(unittest.TestCase):
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

    def write_app(self, slug, data):
        ledger.save_json(ledger.app_path(slug), data)


class Slugify(unittest.TestCase):
    def test_lowercases_and_dashes(self):
        self.assertEqual(ledger.slugify("My Cool App!"), "my-cool-app")

    def test_empty_falls_back_to_app(self):
        self.assertEqual(ledger.slugify("***"), "app")


class RecordAndKnownIssues(IsolatedState):
    def test_record_then_known_issues(self):
        self.run_cmd(
            ledger.cmd_record,
            app="My App",
            batch="ios-2026-01-01",
            source="ios-app-store",
            date_range="2026-01-01..2026-01-15",
            findings_path="",
            regressions_json=json.dumps(["crash on checkout, fixed v2.4, recurring v2.6"]),
        )
        out = json.loads(self.run_cmd(ledger.cmd_known_issues, app="My App"))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["batch"], "ios-2026-01-01")
        self.assertIn("crash on checkout", out[0]["note"])

    def test_known_issues_across_all_apps_when_app_omitted(self):
        self.write_app("app-a", {"app": "App A", "batches": {"b1": {"regressions": ["issue one here"]}}})
        self.write_app("app-b", {"app": "App B", "batches": {"b1": {"regressions": ["issue two here"]}}})
        out = json.loads(self.run_cmd(ledger.cmd_known_issues, app=None))
        self.assertEqual(len(out), 2)


class RecordedFindings(IsolatedState):
    """SKILL.md has each extractor return findings, and ideation reads
    review-scout through `known-issues`. Until findings were recorded, the
    ledger kept only regression notes: a bug seen in one version left nothing
    for a later batch (or for ideation) to compare against."""

    FINDINGS = [
        {"claim": "checkout button crashes on submit", "tag": "bug", "version": "2.3", "count": 15},
        {"claim": "wants dark mode", "tag": "feature-request", "version": "2.3", "count": 4},
        {"claim": "loves the offline sync", "tag": "praise", "version": "2.3", "count": 9},
    ]

    def record(self, batch, findings, regressions=()):
        return self.run_cmd(
            ledger.cmd_record, app="My App", batch=batch, source="ios-app-store", date_range="", findings_path="",
            findings_json=json.dumps(findings), regressions_json=json.dumps(list(regressions)))

    def test_record_stores_findings(self):
        out = self.record("v2.3", self.FINDINGS)
        self.assertIn("3 findings", out)
        self.assertEqual(ledger.load_app("my-app")["batches"]["v2.3"]["findings"], self.FINDINGS)

    def test_known_issues_lists_findings_and_regressions(self):
        self.record("v2.3", self.FINDINGS, regressions=["login loop, fixed v2.1, back in v2.3"])
        out = json.loads(self.run_cmd(ledger.cmd_known_issues, app="My App"))
        self.assertEqual([i["kind"] for i in out], ["finding", "finding", "finding", "regression"])
        bug = out[0]
        self.assertEqual((bug["note"], bug["tag"], bug["version"], bug["count"], bug["batch"]),
                         ("checkout button crashes on submit", "bug", "2.3", 15, "v2.3"))

    def test_dedup_finds_a_bug_that_returns_in_a_later_batch(self):
        self.record("v2.3", self.FINDINGS)
        self.record("v2.6", [{"claim": "checkout button crashes when submitting", "tag": "bug", "version": "2.6"},
                             {"claim": "loves the offline sync feature", "tag": "praise", "version": "2.6"}])
        out = json.loads(self.run_cmd(ledger.cmd_dedup, threshold=0.5))
        self.assertEqual([(p["a"]["batch"], p["b"]["batch"]) for p in out], [("v2.3", "v2.6")])
        self.assertIn("checkout", out[0]["shared_terms"])

    def test_plain_string_findings_are_accepted(self):
        self.record("v1", ["app freezes on launch"])
        out = json.loads(self.run_cmd(ledger.cmd_known_issues, app="My App"))
        self.assertEqual(out[0]["note"], "app freezes on launch")

    def test_main_accepts_findings_json(self):
        with mock.patch.object(ledger, "migrate_legacy", lambda: None), \
                mock.patch("sys.argv", ["ledger.py", "record", "--app", "My App", "--batch", "v1",
                                        "--findings-json", json.dumps(self.FINDINGS)]), \
                redirect_stdout(io.StringIO()):
            ledger.main()
        self.assertEqual(len(ledger.load_app("my-app")["batches"]["v1"]["findings"]), 3)


class Dedup(IsolatedState):
    def test_cross_batch_overlap_detected_same_batch_excluded(self):
        self.write_app("app-a", {
            "app": "App A",
            "batches": {
                "v2.3": {"regressions": ["checkout button crashes on submit"]},
                "v2.6": {"regressions": ["checkout button crashes when submitting"]},
            },
        })
        out = json.loads(self.run_cmd(ledger.cmd_dedup, threshold=0.5))
        self.assertTrue(len(out) >= 1)
        for pair in out:
            self.assertNotEqual(pair["a"]["batch"], pair["b"]["batch"])

    def test_output_independent_of_filesystem_order(self):
        # glob() order is filesystem-dependent (sorted-looking on APFS,
        # not on ext4). Force both orders and require the same output, so
        # dedup pair orientation and known-issues order can't flip.
        self.write_app("app-a", {
            "app": "App A",
            "batches": {"v2.3": {"regressions": ["checkout button crashes on submit"]}},
        })
        self.write_app("app-b", {
            "app": "App B",
            "batches": {"v2.6": {"regressions": ["checkout button crashes when submitting"]}},
        })
        real_glob = Path.glob
        dedups, issues = [], []
        for reverse in (False, True):
            def ordered_glob(path, pattern, _reverse=reverse):
                return iter(sorted(real_glob(path, pattern), reverse=_reverse))
            with mock.patch.object(Path, "glob", ordered_glob):
                dedups.append(json.loads(self.run_cmd(ledger.cmd_dedup, threshold=0.5)))
                issues.append(json.loads(self.run_cmd(ledger.cmd_known_issues, app=None)))
        self.assertEqual(dedups[0], dedups[1])
        self.assertEqual([(p["a"]["app"], p["b"]["app"]) for p in dedups[1]],
                         [("App A", "App B")])
        self.assertEqual(issues[0], issues[1])
        self.assertEqual([i["app"] for i in issues[1]], ["App A", "App B"])

    def test_same_batch_label_across_apps_not_excluded(self):
        # Batch labels are per-app ("v2.0" in App A has nothing to do with
        # "v2.0" in App B), so only a pair from the same app AND the same
        # batch is skipped.
        self.write_app("app-a", {
            "app": "App A",
            "batches": {"v2.0": {"regressions": [
                "checkout button crashes on submit",
                "checkout button crashes on submit again",
            ]}},
        })
        self.write_app("app-b", {
            "app": "App B",
            "batches": {"v2.0": {"regressions": ["checkout button crashes when submitting"]}},
        })
        out = json.loads(self.run_cmd(ledger.cmd_dedup, threshold=0.5))
        pairs = {(p["a"]["app"], p["a"]["batch"], p["b"]["app"], p["b"]["batch"]) for p in out}
        self.assertIn(("App A", "v2.0", "App B", "v2.0"), pairs)
        for p in out:
            self.assertFalse(p["a"]["app"] == p["b"]["app"] and p["a"]["batch"] == p["b"]["batch"])

    def test_below_threshold_excluded(self):
        self.write_app("app-a", {
            "app": "App A",
            "batches": {
                "v1": {"regressions": ["battery drains overnight badly"]},
                "v2": {"regressions": ["login screen freezes randomly"]},
            },
        })
        out = json.loads(self.run_cmd(ledger.cmd_dedup, threshold=0.5))
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
