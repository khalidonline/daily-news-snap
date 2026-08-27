import unittest
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from tools.bulk_visual_sources import (
    SourceDiscoveryBudget,
    SourceDiscoveryBudgetExceeded,
    StoryBeat,
    _json_get,
    discover_commons,
    discover_first_party,
    discover_loc,
    discover_openverse,
    plan_story_beats,
)
from tools.wikimedia_http import (
    SourceRateLimited, WIKIMEDIA_USER_AGENT, parse_retry_after, reset_cooldown,
)


class StoryBeatPlannerTests(unittest.TestCase):
    def setUp(self):
        reset_cooldown()

    def tearDown(self):
        reset_cooldown()

    def test_retry_after_supports_delta_seconds_and_http_date(self):
        now = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(parse_retry_after("10", now=now), 10)
        self.assertEqual(parse_retry_after("Thu, 27 Aug 2026 12:00:10 GMT", now=now), 10)

    @patch("tools.bulk_visual_sources.urlopen")
    def test_commons_discovery_uses_policy_compliant_identity(self, open_url):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = __import__("io").BytesIO(b'{"query": {}}')
        open_url.return_value = response
        _json_get("https://commons.wikimedia.org/w/api.php?test=ua")
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), WIKIMEDIA_USER_AGENT)
        self.assertIn("https://github.com/khalidonline/daily-news-snap", WIKIMEDIA_USER_AGENT)
        self.assertNotIn("Mozilla", WIKIMEDIA_USER_AGENT)

    @patch("tools.bulk_visual_sources.urlopen")
    def test_commons_retry_after_ten_enters_cooldown_without_sleep_or_retry(self, open_url):
        open_url.side_effect = HTTPError("https://commons.wikimedia.org/w/api.php", 429,
                                         "rate", {"Retry-After": "10"}, None)
        sleeps = []
        with self.assertRaises(SourceRateLimited) as caught:
            _json_get("https://commons.wikimedia.org/w/api.php?test=long", sleep=sleeps.append)
        self.assertEqual(open_url.call_count, 1)
        self.assertEqual(sleeps, [])
        self.assertEqual(caught.exception.retry_after_seconds, 10)
        self.assertFalse(caught.exception.retry_occurred)

    @patch("tools.bulk_visual_sources.urlopen")
    def test_cooldown_prevents_additional_commons_requests(self, open_url):
        open_url.side_effect = HTTPError("https://commons.wikimedia.org/w/api.php", 429,
                                         "rate", {"Retry-After": "60"}, None)
        with self.assertRaises(SourceRateLimited):
            _json_get("https://commons.wikimedia.org/w/api.php?test=storm-one", sleep=lambda _: None)
        with self.assertRaises(SourceRateLimited) as caught:
            _json_get("https://commons.wikimedia.org/w/api.php?test=storm-two", sleep=lambda _: None)
        self.assertEqual(open_url.call_count, 1)
        self.assertFalse(caught.exception.source_cooldown_activated)
        self.assertTrue(caught.exception.source_cooldown_active)
        self.assertLessEqual(caught.exception.retry_after_seconds, 30)

    @patch("tools.bulk_visual_sources.urlopen")
    def test_commons_cooldown_does_not_affect_non_commons_json(self, open_url):
        from io import BytesIO
        from tools.wikimedia_http import terminal_rate_limit
        terminal_rate_limit("discovery", 60)
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = BytesIO(b'{"ok": true}')
        open_url.return_value = response
        self.assertEqual(_json_get("https://api.test/not-commons"), {"ok": True})
        self.assertEqual(open_url.call_count, 1)

    @patch("tools.bulk_visual_sources.urlopen")
    def test_json_get_bounds_transient_retries(self, open_url):
        # A dead external API receives one retry, not one long retry loop per
        # candidate. Use unique URLs to avoid the successful-response cache.
        open_url.side_effect = HTTPError("https://api.test/transient", 503, "down", {}, None)
        with self.assertRaises(HTTPError):
            _json_get("https://api.test/transient", attempts=2, sleep=lambda _: None)
        self.assertEqual(open_url.call_count, 2)

    def test_person_story_starts_with_exact_person_identity(self):
        beats = plan_story_beats("Jack Bogle: أنشأ صندوق المؤشرات ورفض أن يصبح ملياردير")
        self.assertEqual(beats[0].key, "person")
        self.assertEqual(beats[0].required_identity, ("Jack Bogle",))

    def test_company_story_has_four_distinct_beats(self):
        beats = plan_story_beats("قصة NVIDIA: من رقائق الألعاب إلى أغلى شركة في العالم")
        self.assertEqual([b.key for b in beats[:4]],
                         ["origin", "early_operation", "turning_point", "modern_result"])

    def test_queries_are_identity_anchored(self):
        for beat in plan_story_beats("قصة NVIDIA: من رقائق الألعاب إلى أغلى شركة في العالم"):
            self.assertTrue(beat.required_identity)
            self.assertTrue(all(any(identity in query for identity in beat.required_identity)
                                for query in beat.queries))

    def test_punctuation_heavy_identity_remains_the_query_anchor(self):
        beats = plan_story_beats("قصة CP/M: النظام الذي كاد يسبق Microsoft ثم اختفى")
        self.assertTrue(beats)
        self.assertIn("CP/M", beats[0].required_identity)
        self.assertTrue(all(any(query.startswith(identity + " ")
                                for identity in beat.required_identity)
                            for beat in beats for query in beat.queries))
        self.assertTrue(all(any(query.startswith("CP/M ") for query in beat.queries)
                            for beat in beats))

    @staticmethod
    def openverse_item(number, title, *, description="", tags=()):
        return {"id": str(number), "title": title, "description": description,
                "url": f"https://img.test/{number}.jpg",
                "foreign_landing_url": f"https://source.test/{number}",
                "tags": [{"name": tag} for tag in tags]}

    def test_unrelated_hits_do_not_consume_candidate_budget(self):
        beat = StoryBeat("origin", ("CP/M history",), ("CP/M",))
        items = [self.openverse_item(i, "Van Gogh artwork") for i in range(5)]
        items += [self.openverse_item(5, "CP/M computer"),
                  self.openverse_item(6, "CP/M terminal")]
        telemetry = []
        found = discover_openverse(beat, limit=2,
                                   json_get=lambda _: {"results": items},
                                   telemetry_fn=telemetry.append)
        self.assertEqual([item.title for item in found],
                         ["CP/M computer", "CP/M terminal"])
        self.assertEqual(telemetry[0]["result"], "DISCOVERY_IDENTITY_SKIPPED")
        self.assertEqual(telemetry[0]["skipped_count"], 5)

    def test_person_results_require_declared_exact_identity_in_metadata(self):
        beat = StoryBeat("person", ("Jerry Lawson photograph",),
                         ("Jerry Lawson", "Gerald Lawson"))
        wrong = self.openverse_item(1, "Lawson archive", description="Jerry McDonald records")
        right = self.openverse_item(2, "Engineering pioneers", tags=("Jerry Lawson",))
        found = discover_openverse(beat, limit=1,
                                   json_get=lambda _: {"results": [wrong, right]})
        self.assertEqual([item.source_id for item in found], ["openverse:2"])

    def test_mcdonald_brothers_sawmill_conflict_skips_before_review(self):
        beat = StoryBeat("person", ("McDonald brothers photograph",),
                         ("McDonald brothers",), "person", ("restaurant", "Ray Kroc"))
        telemetry = []
        found = discover_openverse(
            beat, json_get=lambda _: {"results": [
                self.openverse_item(1, "McDonald Brothers' Sawmill")
            ]}, telemetry_fn=telemetry.append)
        self.assertEqual(found, [])
        self.assertEqual(telemetry[0]["result"], "DISCOVERY_ENTITY_CONFLICT_SKIPPED")
        self.assertIn("sawmill", telemetry[0]["reason"])

    def test_mcdonald_restaurant_context_and_ambiguous_metadata_remain_eligible(self):
        beat = StoryBeat("person", ("McDonald brothers photograph",),
                         ("McDonald brothers",), "person", ("restaurant", "Ray Kroc"))
        items = [self.openverse_item(1, "McDonald brothers at their restaurant",
                                     tags=("Ray Kroc",)),
                 self.openverse_item(2, "McDonald brothers archive")]
        found = discover_openverse(beat, limit=2,
                                   json_get=lambda _: {"results": items})
        self.assertEqual([item.source_id for item in found],
                         ["openverse:1", "openverse:2"])

    def test_same_name_person_explicitly_classified_as_company_is_skipped(self):
        beat = StoryBeat("person", ("Jerry Lawson photograph",),
                         ("Jerry Lawson",), "person")
        telemetry = []
        found = discover_openverse(
            beat, json_get=lambda _: {"results": [
                self.openverse_item(1, "Jerry Lawson Company headquarters")
            ]}, telemetry_fn=telemetry.append)
        self.assertEqual(found, [])
        self.assertEqual(telemetry[0]["result"], "DISCOVERY_ENTITY_CONFLICT_SKIPPED")

    def test_source_budget_bounds_requests_and_retries(self):
        now = [0.0]
        budget = SourceDiscoveryBudget("openverse", seconds=18, max_requests=2,
                                       clock=lambda: now[0])
        self.assertEqual(budget.begin_request(), 9)
        now[0] = 9
        self.assertEqual(budget.begin_request(), 9)
        with self.assertRaises(SourceDiscoveryBudgetExceeded):
            budget.begin_request()
        self.assertEqual(budget.request_count, 2)
        self.assertTrue(budget.disabled)

    @patch("tools.bulk_visual_sources.urlopen")
    def test_loc_and_openverse_http_timeouts_are_short_and_retries_bounded(self, open_url):
        open_url.side_effect = URLError("timed out")
        for source, url in (("loc", "https://www.loc.gov/photos/?budget-test=loc"),
                            ("openverse", "https://api.openverse.org/v1/images/?budget-test=ov")):
            budget = SourceDiscoveryBudget(source)
            with self.assertRaises(URLError):
                _json_get(url, budget=budget, sleep=lambda _: None)
            self.assertEqual(budget.request_count, 2)
            self.assertEqual(budget.retry_count, 1)
        self.assertEqual(open_url.call_count, 4)
        self.assertTrue(all(call.kwargs["timeout"] <= 9 for call in open_url.call_args_list))

    def test_openverse_anonymous_pagination_is_bounded_and_finds_later_identity(self):
        beat = StoryBeat("person", ("Jerry Lawson photograph",), ("Jerry Lawson",))
        requested, telemetry = [], []

        def response(url):
            params = parse_qs(urlparse(url).query)
            requested.append(params)
            page = int(params.get("page", ["1"])[0])
            start = (page - 1) * 20
            if page < 3:
                return {"page_count": 3,
                        "results": [self.openverse_item(start + i, "unrelated archive")
                                    for i in range(20)]}
            return {"page_count": 3,
                    "results": [self.openverse_item(start + i, "unrelated archive")
                                for i in range(7)] +
                               [self.openverse_item(47, "Jerry Lawson portrait")] +
                               [self.openverse_item(48 + i, "unrelated archive")
                                for i in range(12)]}

        found = discover_openverse(beat, limit=12, json_get=response,
                                   telemetry_fn=telemetry.append)
        self.assertEqual([item.source_id for item in found], ["openverse:47"])
        self.assertEqual([params["page_size"] for params in requested],
                         [["20"], ["20"], ["8"]])
        self.assertEqual([params["page"] for params in requested],
                         [["1"], ["2"], ["3"]])
        self.assertEqual(telemetry[0]["examined_count"], 48)
        self.assertEqual(telemetry[0]["skipped_count"], 47)

    def test_openverse_respects_reported_page_count(self):
        beat = StoryBeat("person", ("Jerry Lawson photograph",), ("Jerry Lawson",))
        requested = []

        def response(url):
            requested.append(url)
            return {"page_count": 1,
                    "results": [self.openverse_item(i, "unrelated archive")
                                for i in range(20)]}

        self.assertEqual(discover_openverse(beat, limit=12, json_get=response), [])
        self.assertEqual(len(requested), 1)

    def test_commons_filters_artwork_and_preserves_license(self):
        beat = StoryBeat("person", ("Jack Bogle",), ("Jack Bogle", "John C. Bogle"))
        def fake_json_get(url):
            return {"query": {"pages": {
                "1": {"pageid": 1, "title": "File:John C Bogle 2007.jpg", "imageinfo": [{
                    "url": "https://upload.wikimedia.org/bogle.jpg", "descriptionurl": "https://commons.wikimedia.org/wiki/File:John_C_Bogle_2007.jpg",
                    "width": 594, "height": 792, "extmetadata": {"ImageDescription": {"value": "John C. Bogle in 2007"}, "Artist": {"value": "Bill Cramer"}, "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]},
                "2": {"pageid": 2, "title": "File:Jack Bogle illustration.svg", "imageinfo": [{
                    "url": "https://upload.wikimedia.org/bogle-art.svg", "descriptionurl": "https://commons.wikimedia.org/wiki/File:Jack_Bogle_illustration.svg",
                    "width": 800, "height": 800, "extmetadata": {"ImageDescription": {"value": "Illustration of Jack Bogle"}, "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]},
            }}}
        found = discover_commons(beat, json_get=fake_json_get)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].source_id, "commons:1")
        self.assertEqual(found[0].license, "CC BY-SA 4.0")
        self.assertIn("John C. Bogle", found[0].description)

    def test_commons_uses_raster_thumbnail_and_skips_already_seen_ids(self):
        beat = StoryBeat("modern", ("Emirates aircraft", "Emirates A380"), ("Emirates",))
        urls = []
        def response(url):
            urls.append(url)
            return {"query": {"pages": {"7": {"pageid": 7, "title": "File:Emirates A380.jpg",
                "imageinfo": [{"url": "https://upload.wikimedia.org/original.jpg",
                    "thumburl": "https://upload.wikimedia.org/thumb/1600px-plane.jpg",
                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Emirates_A380.jpg",
                    "width": 4000, "height": 3000,
                    "extmetadata": {"ImageDescription": {"value": "Emirates A380 aircraft"}}}]}}}}
        found = discover_commons(beat, json_get=response, excluded_source_ids={"commons:7"})
        self.assertEqual(found, [])
        self.assertEqual(len(urls), 2)  # continue to the next query looking for diversity
        found = discover_commons(StoryBeat("modern", ("Emirates aircraft",), ("Emirates",)),
                                 json_get=response)
        self.assertIn("iiurlwidth=1600", urls[-1])
        self.assertEqual(found[0].direct_url,
                         "https://upload.wikimedia.org/thumb/1600px-plane.jpg")

    def test_structured_adapters_reject_missing_stable_identity_or_page(self):
        beat = StoryBeat("person", ("Jack Bogle",), ("Jack Bogle",))
        commons_base = {"title": "File:Jack Bogle.jpg", "imageinfo": [{
            "url": "https://upload.wikimedia.org/bogle.jpg", "width": 800,
            "height": 800, "extmetadata": {"ImageDescription": {"value": "Jack Bogle"}},
        }]}
        self.assertEqual(discover_commons(beat, json_get=lambda _: {
            "query": {"pages": {"x": commons_base}}}), [])
        with_id = dict(commons_base, pageid=3)
        self.assertEqual(discover_commons(beat, json_get=lambda _: {
            "query": {"pages": {"x": with_id}}}), [])

        self.assertEqual(discover_loc(beat, json_get=lambda _: {"results": [{
            "title": "Jack Bogle", "description": ["Jack Bogle"],
            "image_url": ["https://tile.loc.gov/x.jpg"],
        }]}), [])
        self.assertEqual(discover_openverse(beat, json_get=lambda _: {"results": [{
            "title": "Jack Bogle", "url": "https://img.test/a.jpg",
            "foreign_landing_url": "https://source.test/a",
        }]}), [])

    def test_loc_and_openverse_keep_provenance(self):
        beat = StoryBeat("origin", ("NVIDIA origin",), ("NVIDIA",))
        loc = discover_loc(beat, json_get=lambda url: {"results": [{"id": "https://www.loc.gov/item/1/", "title": "NVIDIA headquarters", "description": ["NVIDIA building"], "image_url": ["https://tile.loc.gov/x.jpg"], "resources": [{"width": 900, "height": 700}]}]})
        self.assertEqual(loc[0].source_id, "loc:1")
        ov = discover_openverse(beat, json_get=lambda url: {"results": [{"id": "abc", "title": "NVIDIA headquarters", "url": "https://img.test/a.jpg", "foreign_landing_url": "https://source.test/a", "creator": "A", "license": "by", "license_url": "https://creativecommons.org/licenses/by/4.0/", "width": 900, "height": 700}]})
        self.assertEqual(ov[0].source_page, "https://source.test/a")
        self.assertEqual(ov[0].license, "by")

    def test_first_party_rejects_unverified_page_and_accepts_referenced_cdn(self):
        beat = StoryBeat("modern_result", ("NVIDIA modern",), ("NVIDIA",))
        self.assertEqual(discover_first_party(beat, "nvidia.com", page_url="https://evil.test/news", html_get=lambda _: '<img src="https://cdn.test/a.jpg">'), [])
        found = discover_first_party(beat, "nvidia.com", page_url="https://www.nvidia.com/news", html_get=lambda _: '<meta property="og:image" content="https://cdn.nvidia.test/a.jpg"><title>NVIDIA News</title>')
        self.assertEqual(found[0].source_page, "https://www.nvidia.com/news")
        self.assertEqual(found[0].license, "")

    def test_first_party_source_id_is_stable_across_page_image_order(self):
        beat = StoryBeat("modern_result", ("NVIDIA modern",), ("NVIDIA",))
        first = discover_first_party(
            beat, "nvidia.com", page_url="https://www.nvidia.com/news",
            html_get=lambda _: '<title>NVIDIA News</title><img src="/a.jpg"><img src="/b.jpg">')
        second = discover_first_party(
            beat, "nvidia.com", page_url="https://www.nvidia.com/news",
            html_get=lambda _: '<title>NVIDIA News</title><img src="/b.jpg"><img src="/a.jpg">')
        ids_by_url = {item.direct_url: item.source_id for item in first}
        self.assertEqual(ids_by_url,
                         {item.direct_url: item.source_id for item in second})

    def test_first_party_follows_identity_links_and_returns_distinct_assets(self):
        beat = StoryBeat("modern_result", ("NVIDIA modern product",), ("NVIDIA",))
        pages = {
            "https://nvidia.com/": ('<title>NVIDIA</title><img src="/hero.jpg" alt="NVIDIA campus">'
                                    '<a href="/privacy">Privacy</a>'
                                    '<a href="/nvidia-news">News</a>'
                                    '<a href="/products/gpu">GPU products</a>'),
            "https://nvidia.com/nvidia-news": ('<title>NVIDIA News</title>'
                    '<img src="/hero.jpg" alt="NVIDIA campus"><img src="/gpu.jpg" alt="NVIDIA GPU">'),
            "https://nvidia.com/products/gpu": ('<title>NVIDIA GPU products</title>'
                    '<img src="/product.jpg" alt="NVIDIA GPU product">'),
        }
        requested = []
        def get_page(url):
            requested.append(url)
            return pages[url]
        found = discover_first_party(beat, "nvidia.com", html_get=get_page)
        self.assertNotIn("https://nvidia.com/privacy", requested)
        self.assertIn("https://nvidia.com/nvidia-news", requested)
        self.assertIn("https://nvidia.com/products/gpu", requested)
        self.assertEqual([item.direct_url for item in found],
                         ["https://nvidia.com/hero.jpg", "https://nvidia.com/gpu.jpg",
                          "https://nvidia.com/product.jpg"])
        self.assertIn("NVIDIA GPU", found[1].depicts)
        excluded = discover_first_party(beat, "nvidia.com", html_get=lambda url: pages[url],
                                        excluded_source_ids={found[0].source_id})
        self.assertEqual([item.direct_url for item in excluded],
                         ["https://nvidia.com/gpu.jpg", "https://nvidia.com/product.jpg"])


if __name__ == "__main__":
    unittest.main()
