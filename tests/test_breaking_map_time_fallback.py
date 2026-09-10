import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path


class BreakingMapFallbackTests(unittest.TestCase):
    def _load(self, event):
        fake_news = types.ModuleType("news_bot")
        fake_news.PINNED_EVENT = event
        fake_news.looks_like_a_graphic = lambda path: True
        fake_news._commons_safe = lambda _page, _info: False
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
            calls.append((
                queries, kwargs, bot.looks_like_a_graphic("x"),
                bot._commons_safe({"title": "File:Saudi Arabia map-ar.png"}, {}),
                bot._commons_safe({"title": "blocked"}, {}),
            ))
            if len(calls) == 1:
                return None, None
            return "map.png", "Wikimedia Commons"

        bot.fetch_commons_photo = commons
        mod.install_resilient_visual_fallback(bot)
        photo, credit = bot.fetch_commons_photo(["Jizan attack"], "out.png")
        self.assertEqual(photo, "map.png")
        self.assertEqual(credit, "خريطة توضيحية / Wikimedia Commons")
        self.assertEqual(calls[1][0], ["Saudi Arabia map"])
        self.assertFalse(calls[1][2])
        self.assertTrue(calls[1][3])
        self.assertFalse(calls[1][4])
        self.assertTrue(bot.looks_like_a_graphic("x"))
        self.assertFalse(bot._commons_safe({"title": "blocked"}, {}))

    def test_rejected_generic_commons_photo_falls_through_to_exact_centcom_seal(self):
        mod, bot, base = self._load("القيادة المركزية الأمريكية تعلن تدمير ناقلات إيرانية")
        calls = []

        def commons(queries, out_path, **kwargs):
            calls.append((queries, kwargs))
            Path(out_path).write_bytes(b"candidate")
            if len(calls) == 1:
                return str(out_path), "generic warship"
            Path(str(out_path) + ".commons-title").write_text(
                "File:Seal of the United States Central Command.png", encoding="utf-8"
            )
            return str(out_path), "Wikimedia Commons"

        base._breaking_photo_acceptable = (
            lambda _bot, photo, _event, _context="":
            Path(str(photo) + ".commons-title").exists()
        )
        base._cleanup_rejected = lambda photo: Path(photo).unlink(missing_ok=True)
        bot.fetch_commons_photo = commons
        mod.install_resilient_visual_fallback(bot)
        photo, credit = bot.fetch_commons_photo(["US Navy warship Persian Gulf"], "out.png")
        self.assertEqual("out.png", photo)
        self.assertEqual("شعار رسمي / Wikimedia Commons", credit)
        self.assertEqual(2, len(calls))
        self.assertEqual(["United States Central Command official seal"], calls[1][0])

    def test_visual_prompt_explicitly_allows_map_for_multicity_saudi_security_event(self):
        mod, _, base = self._load("هجوم على منشآت في جيزان ونجران")
        mod.install_resilient_visual_prompt(base)
        self.assertIn("خريطة السعودية", base._BREAKING_VISION_PROMPT)
        self.assertIn("شعار الجهة الرسمية", base._BREAKING_VISION_PROMPT)

    def test_exact_verified_saudi_map_bypasses_subjective_vision_only_for_severe_event(self):
        mod, bot, base = self._load("هجوم على منشآت في جيزان ونجران")
        base._breaking_photo_acceptable = lambda *_a, **_k: False
        mod.install_exact_map_acceptance(base)
        with tempfile.TemporaryDirectory() as td:
            photo = Path(td) / "map.png"
            photo.write_bytes(b"map")
            Path(str(photo) + ".commons-title").write_text(
                "File:Saudi Arabia map-ar.png", encoding="utf-8"
            )
            self.assertTrue(base._breaking_photo_acceptable(
                bot, photo, "هجوم صاروخي على أبها وجيزان"
            ))
            self.assertFalse(base._breaking_photo_acceptable(
                bot, photo, "شركة سعودية تعلن نتائجها"
            ))


class BreakingTimeGuidanceTests(unittest.TestCase):
    def test_entrypoint_requires_event_time_in_breaking_event(self):
        text = Path("breaking_watch_entry.py").read_text(encoding="utf-8")
        self.assertIn("وقت الحدث", text)
        self.assertIn("YYYY-MM-DD HH:MM", text)
        self.assertIn("تاريخ سعودي سابق", text)
        self.assertIn("WATCH_PROMPT", text)

    def test_entrypoint_launches_resilient_runner(self):
        text = Path("breaking_watch_entry.py").read_text(encoding="utf-8")
        self.assertIn("breaking_resilient_runner.py", text)


if __name__ == "__main__":
    unittest.main()
