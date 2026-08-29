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

    def test_concatenated_rss_recovers_first_complete_document(self):
        rss = """<?xml version='1.0' encoding='UTF-8'?>
        <rss><channel><item>
          <title>خبر سفر أول</title>
          <description>الوثيقة الأولى صالحة.</description>
          <link>https://example.com/first</link>
          <pubDate>Sat, 29 Aug 2026 08:00:00 GMT</pubDate>
        </item></channel></rss>
        <?xml version='1.0' encoding='UTF-8'?>
        <rss><channel><item>
          <title>خبر ثانٍ يجب تجاهله</title>
          <pubDate>Sat, 29 Aug 2026 09:00:00 GMT</pubDate>
        </item></channel></rss>""".encode("utf-8")
        items = fetch_headlines(
            lambda _: rss, self.clean, self.parse_date,
            feed_specs=self.SPECS, lookback_hours=48, now=self.NOW,
        )
        self.assertEqual([item["title"] for item in items], ["خبر سفر أول"])

    def test_atom_document_with_trailing_second_document_recovers_first_feed(self):
        atom = """<?xml version='1.0' encoding='UTF-8'?>
        <feed xmlns='http://www.w3.org/2005/Atom'>
          <entry>
            <title>رحلة جديدة إلى الرياض</title>
            <summary>إضافة مسار سفر جديد.</summary>
            <link href='https://example.com/atom-first'/>
            <updated>2026-08-29T08:00:00+00:00</updated>
          </entry>
        </feed>
        <feed xmlns='http://www.w3.org/2005/Atom'></feed>""".encode("utf-8")

        def parse_iso(text):
            return datetime.fromisoformat(text) if text else None

        items = fetch_headlines(
            lambda _: atom, self.clean, parse_iso,
            feed_specs=self.SPECS, lookback_hours=48, now=self.NOW,
        )
        self.assertEqual([item["title"] for item in items], ["رحلة جديدة إلى الرياض"])
        self.assertEqual(items[0]["link"], "https://example.com/atom-first")


if __name__ == "__main__":
    unittest.main()
