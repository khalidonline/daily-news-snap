import importlib
import os
import sys
import types
import unittest
from unittest.mock import patch


class BreakingMapFallbackTests(unittest.TestCase):
    def _load(self, event):
        fake_news = types.ModuleType("news_bot")
        fake_news.PINNED_EVENT = event
        fake_news.looks_like_a_graphic = lambda path: True
        sys.modules["news_bot"] = fake_news

        fake_base = types.ModuleType("breaking_news_runner")
        fake_base._BREAKING_VISION_PROMPT = "strict prompt"
        fake_base.run_bot = lambda bot: "ok"
        sys.modules["breaking_news_runner"] = fake_base
        sys.modules.pop("breaking_resilient_runner", None)
        return importlib.import_module("breaking_resilient_runner"), fake_news, fake_base

    def test_severe_saudi_attack_gets_map_fallback_queries(self):
        mod, _, _ = self._load(
            "هجوم على منشآت في أبها وجيزان ونجران أسفر عن إصابة 73 مدنياً"
        )
        queries = mod._fallback_queries(
            "هجوم على منشآت في أبها وجيزان ونجران أسفر عن إصابة 73 مدنياً"
        )
        self.assertIn("Saudi Arabia map", queries)

    def test_routine_saudi_business_news_gets_no_map_fallback(self):
        mod, _, _ = self._load("شركة سعودية تعلن نتائجها الفصلية")
        self.assertEqual(mod._fallback_queries("شركة سعودية تعلن نتائجها الفصلية"), [])

    def test_fallback_reuses_free_commons_without_extra_model_call(self):
        mod, bot, _ = self._load("هجوم على منشآت في جيزان ونجران")
        calls = []

        def commons(queries, out_path, **kwargs):
            calls.append((queries, kwargs, bot.looks_like_a_graphic("x")))
            if len(calls) == 1:
                return None, None
            return "map.png", "Wikimedia Commons"

        bot.fetch_commons_photo = commons
        mod.install_resilient_visual_fallback(bot)
        photo, credit = bot.fetch_commons_photo(["Jizan attack"], "out.png")
        self.assertEqual((photo, credit), ("map.png", "Wikimedia Commons"))
        self.assertEqual(calls[1][0], ["Saudi Arabia map"])
        self.assertFalse(calls[1][2])
        self.assertTrue(bot.looks_like_a_graphic("x"))

    def test_visual_prompt_explicitly_allows_map_for_multicity_saudi_security_event(self):
        mod, _, base = self._load("هجوم على منشآت في جيزان ونجران")
        mod.install_resilient_visual_prompt(base)
        self.assertIn("خريطة السعودية", base._BREAKING_VISION_PROMPT)
        self.assertIn("شعار الجهة الرسمية", base._BREAKING_VISION_PROMPT)


class BreakingTimeGuidanceTests(unittest.TestCase):
    def test_entrypoint_requires_event_time_in_breaking_event(self):
        from pathlib import Path
        text = Path("breaking_watch_entry.py").read_text(encoding="utf-8")
        self.assertIn("وقت الحدث", text)
        self.assertIn("غير محدد", text)
        self.assertIn("WATCH_PROMPT", text)

    def test_entrypoint_launches_resilient_runner(self):
        from pathlib import Path
        text = Path("breaking_watch_entry.py").read_text(encoding="utf-8")
        self.assertIn("breaking_resilient_runner.py", text)


if __name__ == "__main__":
    unittest.main()
