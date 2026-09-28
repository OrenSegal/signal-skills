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
