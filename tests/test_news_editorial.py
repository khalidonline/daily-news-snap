import unittest
from datetime import datetime, timedelta, timezone

from news_editorial import (
    DEFAULT_LOOKBACK_HOURS,
    FEED_SPECS,
    LANE_TARGETS,
    SYSTEM_PROMPT,
    audience_fit_eligible,
    balanced_shortlist,
    decorate_model_items,
    fetch_headlines,
    format_age_label,
    freshness_eligible,
    publication_age_hours,
    shortlist_lane_counts,
)


class NewsEditorialTests(unittest.TestCase):
    FIXED_NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)

    def make_item(self, lane, n, source=None, title=None, age_hours=3, summary=None):
        item = {
            "lane": lane,
            "source": source or f"source-{lane}",
            "title": title or f"{lane} story {n}",
            "summary": summary or f"meaningful development {n}",
            "link": f"https://example.com/{lane}/{n}",
        }
        if age_hours is not None:
            item["published_at"] = (self.FIXED_NOW - timedelta(hours=age_hours)).isoformat()
        return item

    def test_lane_targets_cover_sixty_model_slots(self):
        self.assertEqual(LANE_TARGETS, {
            "business_tech": 20,
            "saudi_core": 16,
            "sports": 8,
            "entertainment_culture": 8,
            "travel_lifestyle": 8,
        })
        self.assertEqual(sum(LANE_TARGETS.values()), 60)

    def test_default_lookback_is_48_hours(self):
        self.assertEqual(DEFAULT_LOOKBACK_HOURS, 48)

    def test_feed_registry_contains_each_required_lane_and_unique_urls(self):
        lanes = {feed["lane"] for feed in FEED_SPECS}
        self.assertTrue(set(LANE_TARGETS).issubset(lanes))
        urls = [feed["url"] for feed in FEED_SPECS]
        self.assertEqual(len(urls), len(set(urls)))

    def test_dedicated_saudi_interest_sources_are_present(self):
        urls = {feed["url"] for feed in FEED_SPECS}
        for url in (
            "https://www.alyaum.com/rssFeed/1009",
            "https://www.alwatan.com.sa/rssFeed/3",
            "https://aawsat.com/feed/sport",
            "https://aawsat.com/feed/culture",
            "https://aawsat.com/feed/travel",
            "https://www.alyaum.com/rssFeed/1007/105",
        ):
            self.assertIn(url, urls)

    def test_hyperlocal_municipal_project_is_filtered(self):
        self.assertFalse(audience_fit_eligible({
            "lane": "saudi_core",
            "title": "بلدية محافظة صغيرة تدشن ممشى جديداً في أحد الأحياء",
            "summary": "المشروع يتضمن تشجيراً وإنارة ومقاعد لخدمة الحي.",
        }))

    def test_major_airport_story_is_not_filtered_as_local(self):
        self.assertTrue(audience_fit_eligible({
            "lane": "saudi_core",
            "title": "مطار الملك سلمان يعلن مرحلة جديدة تستوعب ملايين المسافرين",
            "summary": "التطوير يرتبط بحركة السفر والطيران على مستوى المملكة.",
        }))

    def test_routine_cooperation_pr_is_filtered(self):
        self.assertFalse(audience_fit_eligible({
            "lane": "saudi_core",
            "title": "جهتان تبحثان أوجه التعاون وتوقعان مذكرة تفاهم",
            "summary": "ناقش الاجتماع فرص التعاون المستقبلية بين الطرفين.",
        }))

    def test_routine_sports_fixture_is_filtered(self):
        self.assertFalse(audience_fit_eligible({
            "lane": "sports",
            "title": "موعد مباراة الهلال القادمة والقنوات الناقلة",
            "summary": "المباراة تقام مساء الجمعة.",
        }))

    def test_familiar_consumer_technology_story_survives_gate(self):
        self.assertTrue(audience_fit_eligible({
            "lane": "business_tech",
            "title": "Apple ترفع سعر iPhone في السعودية",
            "summary": "السعر الجديد أعلى بـ200 ريال عند الإطلاق.",
        }))

    def test_balanced_shortlist_represents_all_populated_lanes(self):
        items = []
        for lane in LANE_TARGETS:
            items.extend(self.make_item(lane, i) for i in range(20))
        shortlist = balanced_shortlist(items, 60, now=self.FIXED_NOW)
        counts = shortlist_lane_counts(shortlist)
        self.assertEqual(len(shortlist), 60)
        self.assertEqual(counts, LANE_TARGETS)

    def test_unused_lane_capacity_flows_to_other_qualified_lanes(self):
        items = [self.make_item("business_tech", i) for i in range(80)]
        items += [self.make_item("saudi_core", i) for i in range(4)]
        counts = shortlist_lane_counts(balanced_shortlist(items, 60, now=self.FIXED_NOW))
        self.assertEqual(counts["saudi_core"], 4)
        self.assertEqual(counts["business_tech"], 56)

    def test_hyperlocal_items_do_not_fill_saudi_core_target(self):
        weak = [self.make_item(
            "saudi_core", i, source="local",
            title=f"بلدية محافظة تدشن ممشى جديداً في حي {i}",
            summary="تشجير وإنارة لخدمة الحي.") for i in range(20)]
        strong = [self.make_item("business_tech", i) for i in range(60)]
        counts = shortlist_lane_counts(balanced_shortlist(weak + strong, 60, now=self.FIXED_NOW))
        self.assertEqual(counts.get("saudi_core", 0), 0)
        self.assertEqual(counts["business_tech"], 60)

    def test_one_source_cannot_monopolize_lane_before_peer_gets_turn(self):
        items = [self.make_item("sports", i, source="sports-a") for i in range(20)]
        items += [self.make_item("sports", 100 + i, source="sports-b") for i in range(4)]
        items += [self.make_item("business_tech", i, source="tech") for i in range(52)]
        shortlist = balanced_shortlist(items, 60, now=self.FIXED_NOW)
        first_sports = [x["source"] for x in shortlist if x["lane"] == "sports"][:4]
        self.assertIn("sports-a", first_sports)
        self.assertIn("sports-b", first_sports)

    def test_duplicate_title_from_general_and_section_feed_appears_once(self):
        duplicate = "الهلال يعلن صفقة كبرى للموسم الجديد"
        items = [
            self.make_item("saudi_core", 1, source="general", title=duplicate),
            self.make_item("sports", 2, source="sports", title=duplicate),
            self.make_item("business_tech", 3, source="tech"),
        ]
        titles = [x["title"] for x in balanced_shortlist(items, 60, now=self.FIXED_NOW)]
        self.assertEqual(titles.count(duplicate), 1)

    def test_prompt_targets_saudi_snapchat_adults_25_to_50(self):
        for token in ("25", "50", "سناب شات", "جمهور سعودي"):
            self.assertIn(token, SYSTEM_PROMPT)

    def test_prompt_allows_major_sports_entertainment_and_travel(self):
        for token in ("الرياضة", "الترفيه", "السفر", "الهلال", "موسم الرياض"):
            self.assertIn(token, SYSTEM_PROMPT)

    def test_prompt_rejects_hyperlocal_routine_gossip_and_youth_only_content(self):
        for token in ("المشروع", "محلياً ضيقاً", "الشائعات", "نتائج المباريات الروتينية", "ثرثرة المشاهير", "الترندات الشبابية"):
            self.assertIn(token, SYSTEM_PROMPT)
        self.assertNotIn("الرياضة والمشاهير والفن", SYSTEM_PROMPT)

    def test_prompt_contains_freshness_policy(self):
        for token in ("48", "0–12", "24–48", "الأحدث", "خبر كبير عمره 30–48"):
            self.assertIn(token, SYSTEM_PROMPT)

    def test_prompt_preserves_existing_accuracy_and_image_safety_rules(self):
        for token in (
            "قواعد المقارنة بين رقمين",
            "ربع واحد لا يصنع اتجاهاً",
            "كل ريال تدفعه",
            "image_queries_ar",
            "أشخاص بوجوه واضحة",
            "لا تذكر أي معلومة غير موجودة",
            "Maraya، Aramco، NEOM",
        ):
            self.assertIn(token, SYSTEM_PROMPT)

    def test_age_helpers(self):
        item = self.make_item("business_tech", 1, age_hours=4.9)
        self.assertAlmostEqual(publication_age_hours(item, self.FIXED_NOW), 4.9, places=5)
        self.assertEqual(format_age_label(item, self.FIXED_NOW), "4h")
        older = self.make_item("business_tech", 2, age_hours=31.2)
        self.assertEqual(format_age_label(older, self.FIXED_NOW), "31h")

    def test_unknown_age_item_is_not_eligible_for_normal_daily_shortlist(self):
        item = self.make_item("business_tech", 99)
        item.pop("published_at")
        self.assertFalse(freshness_eligible(item, now=self.FIXED_NOW))

    def test_47_hour_item_eligible_and_49_hour_item_excluded(self):
        self.assertTrue(freshness_eligible(self.make_item("business_tech", 1, age_hours=47), now=self.FIXED_NOW))
        self.assertFalse(freshness_eligible(self.make_item("business_tech", 2, age_hours=49), now=self.FIXED_NOW))

    def test_newer_item_leads_within_same_source_when_otherwise_equal(self):
        old = self.make_item("business_tech", 1, source="same", age_hours=30)
        new = self.make_item("business_tech", 2, source="same", age_hours=4)
        shortlist = balanced_shortlist([old, new], 60, now=self.FIXED_NOW)
        self.assertEqual(shortlist[0]["title"], new["title"])

    def test_strong_30h_item_survives_when_new_weak_pr_is_filtered(self):
        old = self.make_item("saudi_core", 1, age_hours=30,
                             title="ساما تخفض تكلفة تمويل منتج واسع الانتشار",
                             summary="القرار يغير تكلفة التمويل على العملاء.")
        weak = self.make_item("saudi_core", 2, age_hours=2,
                              title="جهتان تبحثان أوجه التعاون وتوقعان مذكرة تفاهم",
                              summary="ناقش الاجتماع فرص التعاون المستقبلية.")
        shortlist = balanced_shortlist([weak, old], 60, now=self.FIXED_NOW)
        self.assertEqual([x["title"] for x in shortlist], [old["title"]])

    def test_decorated_model_items_include_age_and_lane_without_changing_source(self):
        item = self.make_item("sports", 1, source="الشرق الأوسط", age_hours=31)
        decorated = decorate_model_items([item], now=self.FIXED_NOW)[0]
        self.assertIn("[lane=sports]", decorated["summary"])
        self.assertIn("[age=31h]", decorated["summary"])
        self.assertEqual(decorated["source"], item["source"])
        self.assertEqual(decorated["title"], item["title"])

    def test_fetch_headlines_carries_lane_dedupes_and_retains_utc_date(self):
        rss = """<?xml version='1.0'?>
        <rss><channel><item>
          <title>خبر سعودي مهم</title>
          <description>تغيير واسع يمس المستخدمين</description>
          <link>https://example.com/story</link>
          <pubDate>Fri, 28 Aug 2026 12:00:00 GMT</pubDate>
        </item></channel></rss>""".encode("utf-8")
        specs = (
            {"source": "general", "url": "https://example.com/general", "lane": "saudi_core"},
            {"source": "section", "url": "https://example.com/section", "lane": "sports"},
        )
        responses = iter([rss, rss])
        def http_get(_): return next(responses)
        def clean(text): return (text or "").strip()
        from email.utils import parsedate_to_datetime
        def parse_date(text): return parsedate_to_datetime(text) if text else None
        items = fetch_headlines(http_get, clean, parse_date, feed_specs=specs,
                                lookback_hours=48, now=self.FIXED_NOW)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["lane"], "saudi_core")
        self.assertEqual(items[0]["published_at"], "2026-08-28T12:00:00+00:00")

    def test_fetch_headlines_excludes_items_older_than_48_hours(self):
        old = """<rss><channel><item><title>قديم</title><description>x</description>
        <pubDate>Wed, 26 Aug 2026 11:00:00 GMT</pubDate></item></channel></rss>""".encode("utf-8")
        from email.utils import parsedate_to_datetime
        items = fetch_headlines(lambda _: old, lambda x: (x or "").strip(),
                                lambda x: parsedate_to_datetime(x) if x else None,
                                feed_specs=({"source":"s","url":"u","lane":"saudi_core"},),
                                lookback_hours=48, now=self.FIXED_NOW)
        self.assertEqual(items, [])


class DailyNewsRunnerTests(unittest.TestCase):
    def test_configure_applies_48h_prompt_and_balanced_summarizer(self):
        import os
        from types import SimpleNamespace
        from unittest.mock import patch
        import daily_news_runner

        captured = {}

        def original_summarize(items, already_posted=(), pinned=""):
            captured["items"] = items
            captured["already_posted"] = already_posted
            captured["pinned"] = pinned
            return {"stories": []}

        fake = SimpleNamespace(
            LOOKBACK_HOURS=30,
            SYSTEM_PROMPT="old",
            MAX_HEADLINES_TO_MODEL=60,
            summarize=original_summarize,
            _http_get=lambda _: b"<rss><channel></channel></rss>",
            _clean=lambda x: x or "",
            _parse_date=lambda x: None,
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOOKBACK_HOURS", None)
            daily_news_runner.configure(fake)

        self.assertEqual(fake.LOOKBACK_HOURS, 48)
        self.assertIn("25 و50", fake.SYSTEM_PROMPT)

        now = datetime.now(timezone.utc)
        items = []
        for lane in LANE_TARGETS:
            for i in range(20):
                item = {
                    "lane": lane,
                    "source": f"src-{lane}",
                    "title": f"{lane}-{i}",
                    "summary": "meaningful",
                    "link": f"https://e/{lane}/{i}",
                    "published_at": (now - timedelta(hours=3)).isoformat(),
                }
                items.append(item)
        fake.summarize(items, ("old story",), "")
        self.assertEqual(len(captured["items"]), 60)
        counts = shortlist_lane_counts(captured["items"])
        self.assertEqual(counts, LANE_TARGETS)
        self.assertTrue(all("[lane=" in x["summary"] for x in captured["items"]))
        self.assertTrue(all("[age=3h]" in x["summary"] or "[age=2h]" in x["summary"] for x in captured["items"]))
        self.assertEqual(captured["already_posted"], ("old story",))

    def test_pinned_event_bypasses_lane_balancing(self):
        from types import SimpleNamespace
        import daily_news_runner

        captured = {}
        def original(items, already_posted=(), pinned=""):
            captured.update(items=items, pinned=pinned)
            return {"stories": []}
        fake = SimpleNamespace(MAX_HEADLINES_TO_MODEL=60, summarize=original)
        wrapped = daily_news_runner.make_summarizer(fake)
        raw = [{"title": "x"}]
        wrapped(raw, (), "حدث عاجل")
        self.assertIs(captured["items"], raw)
        self.assertEqual(captured["pinned"], "حدث عاجل")


if __name__ == "__main__":
    unittest.main()
