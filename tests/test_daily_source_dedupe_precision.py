import unittest

import daily_news_runner


class DailySourceDedupePrecisionTests(unittest.TestCase):
    def test_url_normalization_drops_tracking_but_keeps_article_identity_query(self):
        first = daily_news_runner._normalize_source_link(
            "http://www.example.com/story?id=1&utm_source=telegram&ref=rss"
        )
        second = daily_news_runner._normalize_source_link(
            "https://example.com/story?id=2&utm_medium=social"
        )
        self.assertEqual(first, "https://example.com/story?id=1")
        self.assertEqual(second, "https://example.com/story?id=2")
        self.assertNotEqual(first, second)

    def test_fuzzy_headline_fallback_applies_only_to_legacy_memory_without_source_link(self):
        posted = [{
            "headline": "رونالدو يحطم رقم السهلاوي ويتصدر هدافي النصر",
            "at": "2026-08-29T15:00:00+00:00",
            "source_link": "https://example.com/ronaldo-goals-record",
        }]
        different_story = {
            "title": "رونالدو يحطم رقم الحضور ويتصدر مبيعات قمصان النصر",
            "link": "https://example.com/ronaldo-shirt-sales",
            "source": "example",
        }
        self.assertEqual(
            daily_news_runner.filter_recent_source_duplicates(
                [different_story], posted
            ),
            [different_story],
        )


if __name__ == "__main__":
    unittest.main()
