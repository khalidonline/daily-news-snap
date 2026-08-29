import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import patch


# breaking_watch imports only these names from news_bot at module import time.
# Stub them so this reliability suite stays focused and dependency-free.
_fake_news_bot = types.ModuleType("news_bot")
_fake_news_bot.ANTHROPIC_API_KEY = "test-key"
_fake_news_bot.DRY_RUN = True
_fake_news_bot.commit_and_push = lambda *args, **kwargs: None
_fake_news_bot.ksa_stamp = lambda: "test-stamp"
_fake_news_bot.notify = lambda *args, **kwargs: None
sys.modules.setdefault("news_bot", _fake_news_bot)

import breaking_watch


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class BreakingWatchFeedTests(unittest.TestCase):
    def feed(self, xml, spec=None):
        feeds = [spec or "https://example.com/rss"]
        with patch.object(breaking_watch, "WATCH_FEEDS", feeds), \
                patch.object(
                    breaking_watch.urllib.request,
                    "urlopen",
                    return_value=FakeResponse(xml.encode("utf-8")),
                ):
            return breaking_watch.feed_fresh_items()

    def test_plain_rss_title_is_seen_as_fresh(self):
        rss = """<rss><channel><item>
          <title>قرار سعودي جديد يغيّر رسوماً ابتداء من الغد</title>
        </item></channel></rss>"""
        fresh, feeds_ok = self.feed(rss)
        self.assertTrue(feeds_ok)
        self.assertEqual(
            fresh,
            ["قرار سعودي جديد يغيّر رسوماً ابتداء من الغد"],
        )

    def test_atom_title_still_works(self):
        atom = """<feed xmlns='http://www.w3.org/2005/Atom'><entry>
          <title>تعليق تداول سهم سعودي بقرار رسمي</title>
        </entry></feed>"""
        fresh, feeds_ok = self.feed(atom)
        self.assertTrue(feeds_ok)
        self.assertEqual(fresh, ["تعليق تداول سهم سعودي بقرار رسمي"])

    def test_two_hour_old_item_survives_schedule_jitter_window(self):
        published = datetime.now(timezone.utc) - timedelta(hours=2)
        rss = f"""<rss><channel><item>
          <title>تعطل واسع يؤثر على رحلات مطار سعودي</title>
          <pubDate>{format_datetime(published, usegmt=True)}</pubDate>
        </item></channel></rss>"""
        fresh, feeds_ok = self.feed(rss)
        self.assertTrue(feeds_ok)
        self.assertEqual(fresh, ["تعطل واسع يؤثر على رحلات مطار سعودي"])

    def test_reachable_feed_with_entries_but_no_parseable_titles_fails_open(self):
        rss = """<rss><channel><item>
          <description>Entry exists, but its title cannot be parsed.</description>
        </item></channel></rss>"""
        fresh, feeds_ok = self.feed(rss)
        self.assertEqual(fresh, [])
        self.assertFalse(feeds_ok)

    def test_default_trigger_set_includes_requested_regional_and_global_sources(self):
        blob = "\n".join(str(spec).lower() for spec in breaking_watch.WATCH_FEEDS)
        for domain in (
            "alarabiya.net",
            "aljazeera.net",
            "asharq.com",
            "argaam.com",
            "cnbcarabia.com",
            "cnn.com",
            "bbc.com",
            "reuters.com",
            "apnews.com",
        ):
            self.assertIn(domain, blob)

    def test_irrelevant_global_headline_is_filtered_before_classifier(self):
        rss = """<rss><channel><item>
          <title>US baseball team wins championship after extra innings</title>
        </item></channel></rss>"""
        fresh, feeds_ok = self.feed(
            rss,
            {"name": "CNN", "url": "https://example.com/cnn", "tier": "global"},
        )
        self.assertTrue(feeds_ok)
        self.assertEqual(fresh, [])

    def test_saudi_global_headline_survives_relevance_filter(self):
        rss = """<rss><channel><item>
          <title>Saudi Arabia announces new aviation rules affecting Riyadh flights</title>
        </item></channel></rss>"""
        fresh, feeds_ok = self.feed(
            rss,
            {"name": "BBC", "url": "https://example.com/bbc", "tier": "global"},
        )
        self.assertTrue(feeds_ok)
        self.assertEqual(
            fresh,
            ["Saudi Arabia announces new aviation rules affecting Riyadh flights"],
        )

    def test_irrelevant_regional_headline_is_filtered_before_classifier(self):
        rss = """<rss><channel><item>
          <title>فريق أمريكي يفوز ببطولة محلية في مباراة مثيرة</title>
        </item></channel></rss>"""
        fresh, feeds_ok = self.feed(
            rss,
            {"name": "Al Jazeera", "url": "https://example.com/aj", "tier": "regional"},
        )
        self.assertTrue(feeds_ok)
        self.assertEqual(fresh, [])

    def test_gulf_regional_headline_survives_relevance_filter(self):
        rss = """<rss><channel><item>
          <title>الإمارات تعلن قراراً جديداً يؤثر على رحلات الطيران في الخليج</title>
        </item></channel></rss>"""
        fresh, feeds_ok = self.feed(
            rss,
            {"name": "Al Arabiya", "url": "https://example.com/aa", "tier": "regional"},
        )
        self.assertTrue(feeds_ok)
        self.assertEqual(
            fresh,
            ["الإمارات تعلن قراراً جديداً يؤثر على رحلات الطيران في الخليج"],
        )

    def test_duplicate_headline_across_feeds_is_returned_once(self):
        rss = """<rss><channel><item>
          <title>أوبك تعلن قراراً جديداً بشأن إنتاج النفط</title>
        </item></channel></rss>""".encode("utf-8")
        feeds = [
            {"name": "Al Arabiya", "url": "https://example.com/a", "tier": "regional"},
            {"name": "Reuters", "url": "https://example.com/b", "tier": "global"},
        ]
        with patch.object(breaking_watch, "WATCH_FEEDS", feeds), \
                patch.object(
                    breaking_watch.urllib.request,
                    "urlopen",
                    side_effect=[FakeResponse(rss), FakeResponse(rss)],
                ):
            fresh, feeds_ok = breaking_watch.feed_fresh_items()
        self.assertTrue(feeds_ok)
        self.assertEqual(fresh, ["أوبك تعلن قراراً جديداً بشأن إنتاج النفط"])

    def test_optional_global_outage_does_not_force_paid_fail_open(self):
        published = datetime.now(timezone.utc) - timedelta(hours=4)
        old_rss = f"""<rss><channel><item>
          <title>قرار سعودي قديم خارج نافذة العاجل</title>
          <pubDate>{format_datetime(published, usegmt=True)}</pubDate>
        </item></channel></rss>""".encode("utf-8")
        feeds = [
            {"name": "Saudi core", "url": "https://example.com/core", "tier": "core"},
            {"name": "CNN", "url": "https://example.com/cnn", "tier": "global"},
        ]
        with patch.object(breaking_watch, "WATCH_FEEDS", feeds), \
                patch.object(
                    breaking_watch.urllib.request,
                    "urlopen",
                    side_effect=[FakeResponse(old_rss), OSError("optional feed down")],
                ):
            fresh, feeds_ok = breaking_watch.feed_fresh_items()
        self.assertEqual(fresh, [])
        self.assertTrue(feeds_ok)

    def test_feed_identified_candidate_uses_one_verification_search(self):
        self.assertEqual(breaking_watch._classifier_search_budget(["headline"]), 1)
        self.assertEqual(
            breaking_watch._classifier_search_budget(None),
            breaking_watch.WATCH_MAX_SEARCHES,
        )


class BreakingWatchWindowTests(unittest.TestCase):
    def test_delayed_1930_schedule_is_still_checked_at_1940(self):
        now = datetime(2026, 8, 29, 19, 40, tzinfo=timezone.utc)
        with patch.object(breaking_watch, "ksa_now", return_value=now), \
                patch.object(breaking_watch, "load_state", return_value={}), \
                patch.object(
                    breaking_watch, "feed_fresh_items", return_value=([], True)
                ) as feed, \
                patch.object(breaking_watch, "notify"):
            breaking_watch._watch()
        feed.assert_called_once_with()

    def test_2259_is_still_inside_extended_window(self):
        now = datetime(2026, 8, 29, 22, 59, tzinfo=timezone.utc)
        with patch.object(breaking_watch, "ksa_now", return_value=now), \
                patch.object(breaking_watch, "load_state", return_value={}), \
                patch.object(
                    breaking_watch, "feed_fresh_items", return_value=([], True)
                ) as feed, \
                patch.object(breaking_watch, "notify"):
            breaking_watch._watch()
        feed.assert_called_once_with()

    def test_2300_and_later_stays_outside_window(self):
        now = datetime(2026, 8, 29, 23, 0, tzinfo=timezone.utc)
        with patch.object(breaking_watch, "ksa_now", return_value=now), \
                patch.object(breaking_watch, "feed_fresh_items") as feed, \
                patch.object(breaking_watch, "notify") as notify:
            breaking_watch._watch()
        feed.assert_not_called()
        message = notify.call_args.args[0]
        self.assertIn("23:00", message)
        self.assertNotIn("احتياطي", message)
        self.assertNotIn("fallback", message.lower())

    def test_workflow_schedules_through_2230_ksa(self):
        workflow = Path(".github/workflows/breaking.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "*/30 5-19 * * *"', workflow)


if __name__ == "__main__":
    unittest.main()
