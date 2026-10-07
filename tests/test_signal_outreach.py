"""Tests for signal-outreach's report generator, plus a full-report smoke
test against the example outreach package.

Ported from the first-to-first-sale repo (tests/test_generate_outreach.py),
where signal-outreach was first published.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _loader import REPO_ROOT, load

go = load("signal-outreach", "scripts/generate_outreach.py")

SCRIPT = REPO_ROOT / "plugins" / "signal-outreach" / "scripts" / "generate_outreach.py"
EXAMPLES = REPO_ROOT / "plugins" / "signal-outreach" / "examples"
EXAMPLE = EXAMPLES / "outreach-package.json"


class HelperTests(unittest.TestCase):
    def test_esc_escapes_html(self):
        self.assertEqual(
            go.esc("<script>alert(1)</script>"),
            "&lt;script&gt;alert(1)&lt;/script&gt;",
        )

    def test_esc_handles_none(self):
        self.assertEqual(go.esc(None), "")

    def test_clamp_bounds_to_range(self):
        self.assertEqual(go.clamp(150), 100)
        self.assertEqual(go.clamp(-10), 0)
        self.assertEqual(go.clamp(42), 42)

    def test_clamp_handles_non_numeric(self):
        self.assertEqual(go.clamp("not a number"), 0)

    def test_items_wraps_scalar_in_list(self):
        self.assertEqual(go.items("x"), ["x"])
        self.assertEqual(go.items(None), [])
        self.assertEqual(go.items([1, 2]), [1, 2])

    def test_dicts_filters_non_dict_entries(self):
        self.assertEqual(
            go.dicts([{"a": 1}, "skip", {"b": 2}, None]), [{"a": 1}, {"b": 2}]
        )


class ReportTests(unittest.TestCase):
    def test_build_html_smoke(self):
        data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        output = go.build_html(data)
        self.assertIn("<html", output.lower())
        self.assertGreater(len(output), 500)

    def test_cli_runs_against_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "report.html"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(EXAMPLE), str(out_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertGreater(out_path.stat().st_size, 0)
            # The checked-in rendered example must match what the script
            # produces today, so the example cannot silently go stale.
            self.assertEqual(
                out_path.read_text(encoding="utf-8"),
                (EXAMPLES / "outreach-report.html").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
