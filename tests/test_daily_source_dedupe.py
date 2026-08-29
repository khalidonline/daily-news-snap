import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import daily_news_runner


class DailySourceDedupeTests(unittest.TestCase):
    def _filter(self, items, posted):
        fn = getattr(
            daily_news_runner,
            "filter_recent_source_duplicates",
            lambda current, recent: list(current),
        )
        return fn(items, posted)

    def test_same_source_link_is_removed_before_model_even_if_headline_changes(self):
        posted = [{
            "headline": "صياغة قديمة مختلفة تماماً",
            "at": "2026-08-29T14:00:00+00:00",
            "source_link": "https://www.alyaum.com/articles/123?utm_source=telegram",
        }]
        items = [{
            "title": "عنوان جديد لنفس الخبر",
            "link": "https://alyaum.com/articles/123",
            "source": "اليوم",
        }]
        self.assertEqual(self._filter(items, posted), [])

    def test_legacy_rewritten_ronaldo_headline_blocks_same_underlying_event(self):
        posted = [{
            "headline": "رونالدو يكتب التاريخ ويتفوق على السهلاوي مع النصر",
            "at": "2026-08-29T14:59:35+00:00",
        }]
        items = [{
            "title": "رونالدو يحطم رقم السهلاوي ويتصدر هدافي النصر",
            "link": "https://www.alyaum.com/articles/ronaldo-record",
            "source": "اليوم",
        }]
        self.assertEqual(self._filter(items, posted), [])

    def test_different_ronaldo_story_is_not_blocked_by_name_alone(self):
        posted = [{
            "headline": "رونالدو يكتب التاريخ ويتفوق على السهلاوي مع النصر",
            "at": "2026-08-29T14:59:35+00:00",
        }]
        item = {
            "title": "رونالدو يفتتح أكاديمية كرة قدم جديدة في الرياض",
            "link": "https://example.com/ronaldo-academy",
            "source": "example",
        }
        self.assertEqual(self._filter([item], posted), [item])

    def test_make_fetcher_applies_recent_source_dedupe_before_returning_items(self):
        posted = [{
            "headline": "رونالدو يكتب التاريخ ويتفوق على السهلاوي مع النصر",
            "at": "2026-08-29T14:59:35+00:00",
        }]
        items = [{
            "title": "رونالدو يحطم رقم السهلاوي ويتصدر هدافي النصر",
            "link": "https://www.alyaum.com/articles/ronaldo-record",
            "source": "اليوم",
            "lane": "sports",
        }]
        fake = SimpleNamespace(
            _http_get=lambda url: b"",
            _clean=lambda value: value,
            _parse_date=lambda value: None,
            LOOKBACK_HOURS=48,
            load_posted=lambda: posted,
        )
        with patch.object(daily_news_runner, "fetch_headlines", return_value=items):
            self.assertEqual(daily_news_runner.make_fetcher(fake)(), [])

    def test_source_aware_save_preserves_legacy_fields_and_adds_source_link(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = Path(td) / "posted.json"

            def legacy_save(previous, stories):
                entries = previous + [
                    {"headline": story["headline"], "at": "2026-08-29T15:00:00+00:00"}
                    for story in stories
                ]
                state_file.write_text(
                    json.dumps(entries, ensure_ascii=False, indent=1),
                    encoding="utf-8",
                )
                return state_file

            fake = SimpleNamespace(save_posted=legacy_save)
            factory = getattr(
                daily_news_runner,
                "make_source_aware_save_posted",
                lambda module: module.save_posted,
            )
            save = factory(fake)
            path = save([], [{
                "headline": "رونالدو يكتب التاريخ ويتفوق على السهلاوي مع النصر",
                "link": "https://www.alyaum.com/articles/ronaldo-record?ref=rss",
            }])
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(data[0]["headline"], "رونالدو يكتب التاريخ ويتفوق على السهلاوي مع النصر")
            self.assertEqual(data[0]["at"], "2026-08-29T15:00:00+00:00")
            self.assertEqual(
                data[0].get("source_link"),
                "https://alyaum.com/articles/ronaldo-record",
            )


if __name__ == "__main__":
    unittest.main()
