import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
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
    def feed(self, xml):
        with patch.object(breaking_watch, "WATCH_FEEDS", ["https://example.com/rss"]), \
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

    def test_default_trigger_set_includes_general_saudi_headlines(self):
        self.assertTrue(
            any("news.google.com/rss?" in url for url in breaking_watch.WATCH_FEEDS),
            breaking_watch.WATCH_FEEDS,
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

    def test_2000_and_later_stays_outside_window_without_stale_fallback_text(self):
        now = datetime(2026, 8, 29, 20, 0, tzinfo=timezone.utc)
        with patch.object(breaking_watch, "ksa_now", return_value=now), \
                patch.object(breaking_watch, "feed_fresh_items") as feed, \
                patch.object(breaking_watch, "notify") as notify:
            breaking_watch._watch()
        feed.assert_not_called()
        message = notify.call_args.args[0]
        self.assertNotIn("احتياطي", message)
        self.assertNotIn("fallback", message.lower())


if __name__ == "__main__":
    unittest.main()
