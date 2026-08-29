import unittest
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from news_editorial import fetch_headlines


class NewsFeedIngestionTests(unittest.TestCase):
    NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    SPECS = ({"source": "test", "url": "https://example.com/rss", "lane": "travel_lifestyle"},)

    @staticmethod
    def clean(text):
        return (text or "").strip()

    @staticmethod
    def parse_date(text):
        return parsedate_to_datetime(text) if text else None

    def test_bare_ampersand_feed_is_recovered_conservatively(self):
        rss = """<?xml version='1.0' encoding='UTF-8'?>
        <rss><channel><item>
          <title>وجهة سفر سعودية جديدة</title>
          <description>رياض & سفر لعطلة نهاية الأسبوع</description>
          <link>https://example.com/story</link>
          <pubDate>Sat, 29 Aug 2026 08:00:00 GMT</pubDate>
        </item></channel></rss>""".encode("utf-8")
        items = fetch_headlines(
            lambda _: rss, self.clean, self.parse_date,
            feed_specs=self.SPECS, lookback_hours=48, now=self.NOW,
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "وجهة سفر سعودية جديدة")
        self.assertIn("رياض & سفر", items[0]["summary"])

    def test_undated_item_never_enters_normal_daily_pool(self):
        rss = """<rss><channel><item>
          <title>خبر بلا تاريخ</title>
          <description>لا يمكن إثبات أنه ضمن نافذة 48 ساعة.</description>
          <link>https://example.com/undated</link>
        </item></channel></rss>""".encode("utf-8")
        items = fetch_headlines(
            lambda _: rss, self.clean, self.parse_date,
            feed_specs=self.SPECS, lookback_hours=48, now=self.NOW,
        )
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
