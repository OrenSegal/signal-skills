import json
import unittest
from pathlib import Path

from _loader import load

rr = load("signal-report", "render_report.py")


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


class MalformedPayload(unittest.TestCase):
    """The payload is written by a model. A wrong shape must come back as a
    PayloadError that names the field, never as a Python traceback."""

    def tier(self, **overrides):
        tier = make_payload()["tiers"][0]
        tier.update(overrides)
        return make_payload(tiers=[tier])

    def assert_payload_error(self, payload, *needles):
        for render in (rr.render, rr.render_text):
            with self.assertRaises(rr.PayloadError) as ctx:
                render(payload)
            for needle in needles:
                self.assertIn(needle, str(ctx.exception))

    def test_payload_that_is_not_an_object(self):
        self.assert_payload_error([make_payload()], "object")

    def test_tiers_that_is_not_a_list(self):
        self.assert_payload_error(make_payload(tiers={"a": 1}), "tiers", "list")

    def test_tier_that_is_not_an_object(self):
        self.assert_payload_error(make_payload(tiers=["Do now"]), "tier 0", "object")

    def test_items_that_is_not_a_list(self):
        self.assert_payload_error(self.tier(items={"claim": "x"}), "tier 0", "items", "list")

    def test_item_that_is_not_an_object(self):
        self.assert_payload_error(self.tier(items=["Users want CSV export"]), "tier 0 item 0", "object")

    def test_rank_that_is_not_a_whole_number(self):
        for bad in ("5", 2.5, None, True):
            self.assert_payload_error(self.tier(rank=bad), "tier 0", "rank")

    def test_of_that_is_not_a_whole_number(self):
        self.assert_payload_error(self.tier(of="5"), "tier 0", "of")

    def test_rank_out_of_range_is_caught_by_validation(self):
        with self.assertRaises(rr.PayloadError):
            rr.validate_payload(self.tier(rank=6, of=5))

    def test_missing_rank_does_not_fail_a_tier_with_many_items(self):
        # The default used to be the item count, so a sixth item in a tier with
        # no rank failed with "rank 6 out of range", which names nothing the
        # author wrote.
        tier = make_payload()["tiers"][0]
        del tier["rank"]
        tier["items"] = tier["items"] * 7
        html = rr.render(make_payload(tiers=[tier]))
        self.assertEqual(html.count('<i class="on"></i>'), 5)

    def test_em_dash_in_a_footer_raises(self):
        self.assert_payload_error(make_payload(footer_left="state \u2014 show.json"), "footer_left")


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



class CommittedExample(unittest.TestCase):
    def test_example_report_matches_renderer(self):
        # The checked-in example must match what the renderer produces today, so it cannot go stale.
        examples = Path(rr.__file__).parent / "examples"
        payload = json.loads((examples / "payload.json").read_text())
        self.assertEqual(rr.render_to(payload, Path("report.html")), (examples / "report.html").read_text())


if __name__ == "__main__":
    unittest.main()
