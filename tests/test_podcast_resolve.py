import json
import unittest

from _loader import load

resolve = load("podcast", "resolve.py")

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Test Show</title>
    <item>
      <title>Episode One</title>
      <pubDate>Mon, 05 Jan 2026 00:00:00 GMT</pubDate>
      <podcast:transcript url="https://example.com/ep1.vtt" type="text/vtt" />
    </item>
    <item>
      <title>Episode Two</title>
      <pubDate>Mon, 12 Jan 2026 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


class ParseFeed(unittest.TestCase):
    def test_parses_title_date_transcript(self):
        eps = resolve.parse_feed(SAMPLE_RSS.encode("utf-8"), limit=10)
        self.assertEqual(len(eps), 2)
        self.assertEqual(eps[0]["title"], "Episode One")
        self.assertEqual(eps[0]["transcript"], "https://example.com/ep1.vtt")
        self.assertIsNone(eps[1]["transcript"])

    def test_respects_limit(self):
        eps = resolve.parse_feed(SAMPLE_RSS.encode("utf-8"), limit=1)
        self.assertEqual(len(eps), 1)


class FlattenTranscript(unittest.TestCase):
    def test_strips_vtt_timestamps_and_headers(self):
        vtt = (
            "WEBVTT\n\n"
            "1\n00:00:00.000 --> 00:00:02.000\nHello there\n\n"
            "2\n00:00:02.000 --> 00:00:04.000\nHow are you\n"
        )
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".vtt", mode="w", delete=False) as f:
            f.write(vtt)
            path = f.name
        try:
            out = resolve.flatten_transcript_file(path)
        finally:
            import os
            os.remove(path)
        self.assertNotIn("-->", out)
        self.assertNotIn("WEBVTT", out)
        self.assertIn("Hello there", out)
        self.assertIn("How are you", out)

    def test_dedups_repeated_lines(self):
        vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nSame line\n\n00:00:01.000 --> 00:00:02.000\nSame line\n"
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".vtt", mode="w", delete=False) as f:
            f.write(vtt)
            path = f.name
        try:
            out = resolve.flatten_transcript_file(path)
        finally:
            os.remove(path)
        self.assertEqual(out.count("Same line"), 1)


class YtDate(unittest.TestCase):
    def test_formats_yyyymmdd(self):
        self.assertEqual(resolve._yt_date("20260115"), "2026-01-15")

    def test_none_or_malformed_returns_empty(self):
        self.assertEqual(resolve._yt_date(None), "")
        self.assertEqual(resolve._yt_date("2026"), "")


class IsYoutube(unittest.TestCase):
    def test_detects_youtube_urls(self):
        self.assertTrue(resolve.is_youtube("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(resolve.is_youtube("https://youtu.be/abc"))

    def test_rejects_non_youtube(self):
        self.assertFalse(resolve.is_youtube("https://podcasts.apple.com/us/podcast/x/id123"))


if __name__ == "__main__":
    unittest.main()
