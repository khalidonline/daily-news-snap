import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import daily_news_runner


class DailySportsBalanceTests(unittest.TestCase):
    def _summarize(self, posted, stories, shortlist):
        module = SimpleNamespace()
        module.MAX_HEADLINES_TO_MODEL = 60
        module.load_posted = lambda: posted
        module.summarize = lambda items, already_posted=(), pinned="": {
            "caption": "test",
            "stories": [dict(story) for story in stories],
        }

        with patch.object(
            daily_news_runner, "balanced_shortlist", return_value=shortlist
        ), patch.object(
            daily_news_runner, "decorate_model_items", side_effect=lambda items: items
        ), patch.object(
            daily_news_runner, "validate_ranked_result", side_effect=lambda result, items: result
        ), patch.object(
            daily_news_runner, "remember_story_contexts", side_effect=lambda result: result
        ):
            return daily_news_runner.make_summarizer(module)([], [], "")

    def test_recent_sports_pushes_all_sports_behind_non_sports(self):
        posted = [{"headline": "رونالدو يتصدر قائمة هدافي النصر التاريخيين"}]
        shortlist = [
            {"lane": "sports"},
            {"lane": "business_tech"},
            {"lane": "sports"},
            {"lane": "saudi_core"},
        ]
        stories = [
            {"item": 1, "headline": "الهلال يسجل خماسية أمام الخليج"},
            {"item": 2, "headline": "Anthropic تواجه دعوى حقوق نشر"},
            {"item": 3, "headline": "ليفربول يحسم صفقة جديدة"},
            {"item": 4, "headline": "الأسهم السعودية ترتفع للأسبوع الرابع"},
        ]

        result = self._summarize(posted, stories, shortlist)

        self.assertEqual(
            [story["item"] for story in result["stories"]],
            [2, 4, 1, 3],
        )

    def test_saved_lane_marks_recent_sports_even_when_headline_is_ambiguous(self):
        posted = [{"headline": "تطور جديد للنادي", "lane": "sports"}]
        shortlist = [
            {"lane": "sports"},
            {"lane": "business_tech"},
        ]
        stories = [
            {"item": 1, "headline": "خبر رياضي كبير"},
            {"item": 2, "headline": "OpenAI تطلق منتجاً جديداً"},
        ]

        result = self._summarize(posted, stories, shortlist)

        self.assertEqual(result["stories"][0]["item"], 2)

    def test_no_recent_sports_keeps_model_order(self):
        posted = [
            {"headline": "Apple ترفع سعر اشتراك Apple TV"},
            {"headline": "الأسهم السعودية ترتفع للأسبوع الرابع"},
        ]
        shortlist = [
            {"lane": "sports"},
            {"lane": "business_tech"},
        ]
        stories = [
            {"item": 1, "headline": "الهلال يحقق لقباً كبيراً"},
            {"item": 2, "headline": "OpenAI تطلق منتجاً جديداً"},
        ]

        result = self._summarize(posted, stories, shortlist)

        self.assertEqual([story["item"] for story in result["stories"]], [1, 2])

    def test_sports_older_than_last_three_cards_does_not_trigger_guard(self):
        posted = [
            {"headline": "رونالدو يحطم رقماً قياسياً"},
            {"headline": "Apple تغير أسعارها"},
            {"headline": "ساما تصدر قراراً جديداً"},
            {"headline": "OpenAI تطلق ميزة جديدة"},
        ]
        shortlist = [
            {"lane": "sports"},
            {"lane": "business_tech"},
        ]
        stories = [
            {"item": 1, "headline": "الهلال يحقق بطولة كبرى"},
            {"item": 2, "headline": "Anthropic تواجه دعوى جديدة"},
        ]

        result = self._summarize(posted, stories, shortlist)

        self.assertEqual(result["stories"][0]["item"], 1)

    def test_all_sports_remains_available_when_no_non_sports_alternative_exists(self):
        posted = [{"headline": "رونالدو يحطم رقماً قياسياً"}]
        shortlist = [{"lane": "sports"}, {"lane": "sports"}]
        stories = [
            {"item": 1, "headline": "الهلال يحقق بطولة كبرى"},
            {"item": 2, "headline": "المنتخب يتأهل إلى النهائي"},
        ]

        result = self._summarize(posted, stories, shortlist)

        self.assertEqual([story["item"] for story in result["stories"]], [1, 2])

    def test_business_deal_is_not_mistaken_for_sports_memory(self):
        posted = [{"headline": "أرامكو تحسم صفقة استحواذ بـ10 مليارات دولار"}]
        shortlist = [
            {"lane": "sports"},
            {"lane": "saudi_core"},
        ]
        stories = [
            {"item": 1, "headline": "الهلال يحقق بطولة كبرى"},
            {"item": 2, "headline": "ساما تعلن نظاماً جديداً"},
        ]

        result = self._summarize(posted, stories, shortlist)

        self.assertEqual(result["stories"][0]["item"], 1)

    def test_source_aware_save_persists_editorial_lane_for_future_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "posted.json"

            def legacy_save(previous, stories):
                entries = list(previous) + [
                    {"headline": story["headline"], "at": "2026-08-30T07:00:00+00:00"}
                    for story in stories
                ]
                state_path.write_text(
                    json.dumps(entries, ensure_ascii=False), encoding="utf-8"
                )
                return state_path

            module = SimpleNamespace(save_posted=legacy_save)
            save = daily_news_runner.make_source_aware_save_posted(module)
            save([], [{
                "headline": "الهلال يحقق بطولة كبرى",
                "link": "https://example.com/story",
                "_editorial_lane": "sports",
            }])

            saved = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(saved[0].get("lane"), "sports")


if __name__ == "__main__":
    unittest.main()
