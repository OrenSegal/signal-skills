import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from _loader import load

resolve = load("review-scout", "resolve.py")


class Detect(unittest.TestCase):
    def _in_tmp(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, dict):
                path.write_text(json.dumps(content))
            else:
                path.write_text(content)
        return root

    def test_flutter_detected_as_mobile(self):
        root = self._in_tmp({"pubspec.yaml": "name: foo"})
        result = resolve.detect(root)
        self.assertEqual(result["kind"], "mobile-app")

    def test_android_dir_detected_as_mobile(self):
        root = self._in_tmp({"android/build.gradle": ""})
        result = resolve.detect(root)
        self.assertEqual(result["kind"], "mobile-app")

    def test_react_native_package_json_detected_as_mobile(self):
        root = self._in_tmp({"package.json": {"dependencies": {"react-native": "0.74.0"}}})
        result = resolve.detect(root)
        self.assertEqual(result["kind"], "mobile-app")

    def test_manifest_v3_detected_as_extension(self):
        root = self._in_tmp({"manifest.json": {"manifest_version": 3}})
        result = resolve.detect(root)
        self.assertEqual(result["kind"], "browser-extension")

    def test_plain_package_json_detected_as_web_saas(self):
        root = self._in_tmp({"package.json": {"dependencies": {"express": "4.0.0"}}})
        result = resolve.detect(root)
        self.assertEqual(result["kind"], "web-saas")

    def test_nothing_detected_as_unknown(self):
        root = self._in_tmp({})
        result = resolve.detect(root)
        self.assertEqual(result["kind"], "unknown")

    def test_malformed_manifest_json_does_not_crash(self):
        root = self._in_tmp({"manifest.json": "not valid json{{"})
        result = resolve.detect(root)
        self.assertEqual(result["kind"], "unknown")


SAMPLE_FEED = {
    "feed": {
        "entry": [
            {
                "id": {"label": "123"},
                "im:rating": {"label": "5"},
                "title": {"label": "Great app"},
                "content": {"label": "Works perfectly"},
                "author": {"name": {"label": "alice"}},
                "updated": {"label": "2026-01-05T00:00:00-07:00"},
                "im:version": {"label": "2.4"},
            },
            {
                "id": {"label": "124"},
                "im:rating": {"label": "1"},
                "title": {"label": "Crashes"},
                "content": {"label": "Crashes on launch"},
                "author": {"name": {"label": "bob"}},
                "updated": {"label": "2026-01-04T00:00:00-07:00"},
                "im:version": {"label": "2.3"},
            },
        ]
    }
}


class FetchIos(unittest.TestCase):
    def test_parses_reviews_and_writes_manifest(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out_dir = Path(tmp.name)

        class FakeResponse:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def read(self_inner):
                return json.dumps(SAMPLE_FEED).encode("utf-8")

        call_count = {"n": 0}

        def fake_urlopen(url, timeout=15):
            call_count["n"] += 1
            if call_count["n"] > 1:
                # second page: empty feed, stop pagination
                return type("R", (), {
                    "__enter__": lambda s: s,
                    "__exit__": lambda s, *a: False,
                    "read": lambda s: json.dumps({"feed": {}}).encode("utf-8"),
                })()
            return FakeResponse()

        with patch.object(resolve.urllib.request, "urlopen", side_effect=fake_urlopen):
            resolve.fetch_ios("999", "us", 5, out_dir)

        manifest = json.loads((out_dir / "ios-999-manifest.json").read_text())
        self.assertEqual(manifest["count"], 2)
        self.assertEqual(manifest["source"], "ios-app-store")

        txt = (out_dir / "ios-999.txt").read_text()
        self.assertIn("Great app", txt)
        self.assertIn("Crashes on launch", txt)

    def test_first_page_failure_exits_nonzero_and_writes_nothing(self):
        # A wrong id, no network or a blocked host used to end in an empty
        # reviews file, a count-0 manifest and exit 0: "no reviews" and "could
        # not fetch" looked the same to the caller.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out_dir = Path(tmp.name) / "tx"
        with patch.object(resolve.urllib.request, "urlopen", side_effect=OSError("network down")), \
                redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                resolve.fetch_ios("999", "us", 5, out_dir)
        self.assertIn("network down", str(ctx.exception))
        self.assertEqual(list(out_dir.glob("*")) if out_dir.exists() else [], [])

    def test_app_with_no_reviews_still_writes_a_count_zero_manifest(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        empty = type("R", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: False,
                               "read": lambda s: json.dumps({"feed": {}}).encode("utf-8")})
        with patch.object(resolve.urllib.request, "urlopen", side_effect=lambda url, timeout=15: empty()), \
                redirect_stdout(io.StringIO()):
            resolve.fetch_ios("999", "us", 5, Path(tmp.name))
        self.assertEqual(json.loads((Path(tmp.name) / "ios-999-manifest.json").read_text())["count"], 0)

    def test_app_id_and_country_are_validated_before_any_fetch(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with patch.object(resolve.urllib.request, "urlopen", side_effect=AssertionError("fetched")):
            for app_id, country in (("../../evil", "us"), ("com.example.app", "us"), ("999", "../x"), ("", "us")):
                with self.assertRaises(SystemExit, msg=(app_id, country)):
                    resolve.fetch_ios(app_id, country, 1, Path(tmp.name))

    def test_app_id_copied_from_a_store_url_is_accepted(self):
        self.assertEqual(resolve.ios_app_id("id284882215"), "284882215")
        self.assertEqual(resolve.ios_app_id(" 284882215 "), "284882215")


class AndroidPackage(unittest.TestCase):
    def test_package_name_cannot_escape_the_download_folder(self):
        self.assertEqual(resolve.android_package("com.example.app_2"), "com.example.app_2")
        for bad in ("../../evil", "com/example", "", "com.example app"):
            with self.assertRaises(SystemExit, msg=bad):
                resolve.android_package(bad)


if __name__ == "__main__":
    unittest.main()
