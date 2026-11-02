import contextlib
import http.server
import io
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
from collections import Counter
from unittest import mock

from _loader import load

resolve = load("podcast", "resolve.py")
real_get = resolve.get
real_connect = socket.socket.connect


def _connect_local(sock, port):
    """Stands in for the network: any connection lands on the local fixture."""
    return real_connect(sock, ("127.0.0.1", port))

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


class FetchGuard(unittest.TestCase):
    """The feed URL comes from the user or iTunes and transcript URLs come from
    the feed, so a hostile feed must not be able to read local files or
    internal addresses into --download. "Never contacted" reads the hit counter."""

    def setUp(self):
        self.hits = Counter()
        hits = self.hits

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hits[self.path] += 1
                if self.path.startswith("/redirect-to/"):
                    self.send_response(302)
                    self.send_header("Location", self.path[len("/redirect-to/"):].replace("|", "://", 1))
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"INTERNAL-SECRET")

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def fake_dns(self, name, ip):
        real = socket.getaddrinfo

        def resolver(host, port, *args, **kwargs):
            if host == name:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
            return real(host, port, *args, **kwargs)

        return mock.patch.object(socket, "getaddrinfo", resolver)

    def test_non_http_schemes_are_refused(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            f.write(b"local file contents")
            f.flush()
            for url in ("file://" + f.name, "ftp://example.com/x", "data:text/plain,hello"):
                with self.subTest(url=url), self.assertRaises(resolve.BlockedURL):
                    resolve.get(url)

    def test_local_address_spellings_are_never_contacted(self):
        for host in ("127.0.0.1", "localhost", "2130706433", "0x7f000001", "0177.0.0.1", "127.1",
                     "[::1]", "[::ffff:127.0.0.1]", "[64:ff9b::7f00:1]", "①②⑦.⓪.⓪.①", "169.254.169.254"):
            with self.subTest(host=host), self.assertRaises(resolve.BlockedURL):
                resolve.get(f"http://{host}:{self.port}/")
        self.assertEqual(sum(self.hits.values()), 0)

    def test_hostname_resolving_to_a_private_address_is_never_contacted(self):
        with self.fake_dns("evil.test", "127.0.0.1"), self.assertRaises(resolve.BlockedURL):
            resolve.get(f"http://evil.test:{self.port}/")
        self.assertEqual(sum(self.hits.values()), 0)

    def test_redirect_to_a_local_target_is_not_followed(self):
        # The first hop is a public name in DNS terms; the fixture stands behind it.
        real_check = resolve.is_blocked_ip
        with self.fake_dns("public.test", "93.184.215.14"), \
                mock.patch.object(resolve, "is_blocked_ip", lambda ip: str(ip) != "93.184.215.14" and real_check(ip)), \
                mock.patch.object(socket.socket, "connect", lambda s, a: _connect_local(s, self.port)):
            with self.assertRaises(resolve.BlockedURL):
                resolve.get(f"http://public.test:{self.port}/redirect-to/http|127.0.0.1:{self.port}/secret")
            # urllib refuses this one itself; either way no file comes back.
            with self.assertRaises((resolve.BlockedURL, urllib.error.HTTPError)):
                resolve.get(f"http://public.test:{self.port}/redirect-to/file|/etc/hosts")
        self.assertEqual(self.hits["/secret"], 0)

    def test_hostile_transcript_url_writes_nothing_to_download(self):
        feed = SAMPLE_RSS.replace("https://example.com/ep1.vtt", "file:///etc/hosts").encode("utf-8")
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(resolve, "resolve_source", return_value=("https://feed.example/rss", None, None, "x")), \
                mock.patch.object(resolve, "get", side_effect=lambda url, timeout=60: feed if "feed.example" in url else real_get(url)), \
                mock.patch.object(sys, "argv", ["resolve.py", "https://feed.example/rss", "--download", tmp]), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            resolve.main()
            manifest = json.load(open(os.path.join(tmp, "manifest.json")))
        self.assertEqual(manifest, [])
        self.assertIn("FAIL", out.getvalue())

    def test_public_address_passes_the_check(self):
        with self.fake_dns("public.test", "93.184.215.14"):
            resolve.check_url("https://public.test/feed.xml")
        with self.fake_dns("fed1.ca", "93.184.215.14"):  # hex-looking name, not a numeric spelling
            resolve.check_url("https://fed1.ca/feed.xml")


if __name__ == "__main__":
    unittest.main()
