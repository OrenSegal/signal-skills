import unittest
from pathlib import Path

from _loader import load

rr = load("signal-scout", "render_report.py")


def make_payload(**overrides):
    payload = {
        "title": "Test Report",
        "eyebrow": "3 shows, since 2026-01-01",
        "headline": "Ship the export flow",
        "query": "What should we build next?",
        "tiers": [
            {
                "label": "Ship before the deadline",
                "name": "Do now",
                "rank": 4,
                "of": 5,
                "color": "sig",
                "items": [
                    {
                        "claim": "Users want CSV export",
                        "tag": "confirmed twice",
                        "tag_class": "sig",
                        "reasoning": "Came up in 2 episodes independently",
                        "source": "ep12, 2026-02-01",
                    }
                ],
            }
        ],
        "footer_left": "manifest.json",
        "footer_right": "state/show.json",
    }
    payload.update(overrides)
    return payload


class SlugifyKey(unittest.TestCase):
    def test_lowercases_and_dashes(self):
        self.assertEqual(rr.slugify_key("Do Now!!", "x"), "do-now")

    def test_empty_falls_back(self):
        self.assertEqual(rr.slugify_key("???", "fallback"), "fallback")


class EmDashCheck(unittest.TestCase):
    def test_raises_on_em_dash(self):
        with self.assertRaises(rr.PayloadError):
            rr.check_no_em_dash("this has an em dash — right there", "field")

    def test_allows_plain_text(self):
        rr.check_no_em_dash("this is fine - a hyphen", "field")


class RenderBars(unittest.TestCase):
    def test_filled_and_empty_counts(self):
        html = rr.render_bars(3, 5, "sig")
        self.assertEqual(html.count('class="on"'), 3)
        self.assertEqual(html.count("<i></i>"), 2)

    def test_out_of_range_raises(self):
        with self.assertRaises(rr.PayloadError):
            rr.render_bars(6, 5, "sig")
        with self.assertRaises(rr.PayloadError):
            rr.render_bars(0, 5, "sig")


class ValidatePayload(unittest.TestCase):
    def test_valid_payload_passes(self):
        rr.validate_payload(make_payload())

    def test_missing_top_level_field_raises(self):
        payload = make_payload()
        del payload["headline"]
        with self.assertRaises(rr.PayloadError):
            rr.validate_payload(payload)

    def test_zero_tiers_raises(self):
        with self.assertRaises(rr.PayloadError):
            rr.validate_payload(make_payload(tiers=[]))

    def test_tier_with_zero_items_raises(self):
        payload = make_payload()
        payload["tiers"][0]["items"] = []
        with self.assertRaises(rr.PayloadError):
            rr.validate_payload(payload)

    def test_invalid_tier_color_raises(self):
        payload = make_payload()
        payload["tiers"][0]["color"] = "purple"
        with self.assertRaises(rr.PayloadError):
            rr.validate_payload(payload)

    def test_item_missing_field_raises(self):
        payload = make_payload()
        del payload["tiers"][0]["items"][0]["reasoning"]
        with self.assertRaises(rr.PayloadError):
            rr.validate_payload(payload)

    def test_invalid_tag_class_raises(self):
        payload = make_payload()
        payload["tiers"][0]["items"][0]["tag_class"] = "purple"
        with self.assertRaises(rr.PayloadError):
            rr.validate_payload(payload)

    def test_em_dash_in_headline_raises(self):
        payload = make_payload(headline="Ship it — now")
        with self.assertRaises(rr.PayloadError):
            rr.validate_payload(payload)


class Render(unittest.TestCase):
    def test_render_escapes_html_and_includes_content(self):
        payload = make_payload()
        payload["tiers"][0]["items"][0]["claim"] = "<script>alert(1)</script>"
        out = rr.render(payload)
        self.assertNotIn("<script>alert(1)</script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("Ship the export flow", out)
        self.assertIn("Test Report", out)

    def test_render_to_dispatches_on_extension(self):
        payload = make_payload()
        html_out = rr.render_to(payload, Path("out.html"))
        md_out = rr.render_to(payload, Path("out.md"))
        self.assertIn("<div class=\"wrap\">", html_out)
        self.assertNotIn("<div", md_out)


class RenderText(unittest.TestCase):
    def test_contains_headline_and_claim(self):
        text = rr.render_text(make_payload())
        self.assertIn("# Ship the export flow", text)
        self.assertIn("Users want CSV export", text)
        self.assertIn("Source: ep12, 2026-02-01", text)

    def test_footer_omitted_when_empty(self):
        payload = make_payload(footer_left="", footer_right="")
        text = rr.render_text(payload)
        self.assertNotIn("---", text)


if __name__ == "__main__":
    unittest.main()
