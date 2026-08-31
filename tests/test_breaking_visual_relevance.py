import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import news_bot


class BreakingVisualRelevanceTests(unittest.TestCase):
    def story(self):
        return {
            "headline": "فيدان: تحالف مكة الدفاعي بدأ ببنية أمنية جديدة",
            "summary": "إعلان تركي عن بدء تشكيل الهيكل الأساسي لاتفاق دفاعي بين السعودية وتركيا وباكستان.",
            "takeaway": "تطور مباشر في اتفاق دفاعي يهم القارئ السعودي.",
        }

    def test_generic_riyadh_library_photo_cannot_qualify_for_breaking(self):
        helper = getattr(news_bot, "_breaking_photo_acceptable", None)
        self.assertIsNotNone(helper)
        with patch.object(news_bot, "PINNED_EVENT", "وزير خارجية تركيا يعلن بدء تشكيل الهيكل الأساسي لاتفاق مكة الدفاعي"), \
                patch.object(news_bot, "photo_shows", return_value="neutral") as judge:
            accepted = helper("old-riyadh-souq.jpg", self.story())
        self.assertFalse(accepted)
        context = judge.call_args.args[1]
        self.assertIn("تركيا", context)
        self.assertIn("باكستان", context)

    def test_breaking_visual_requires_explicit_yes(self):
        helper = getattr(news_bot, "_breaking_photo_acceptable", None)
        self.assertIsNotNone(helper)
        with patch.object(news_bot, "PINNED_EVENT", "حدث عاجل سعودي"):
            for verdict in ("neutral", "no"):
                with self.subTest(verdict=verdict), \
                        patch.object(news_bot, "photo_shows", return_value=verdict):
                    self.assertFalse(helper("candidate.jpg", self.story()))
            with patch.object(news_bot, "photo_shows", return_value="yes"):
                self.assertTrue(helper("candidate.jpg", self.story()))

    def test_non_breaking_visual_path_stays_unchanged(self):
        helper = getattr(news_bot, "_breaking_photo_acceptable", None)
        self.assertIsNotNone(helper)
        with patch.object(news_bot, "PINNED_EVENT", ""), \
                patch.object(news_bot, "photo_shows") as judge:
            self.assertTrue(helper("candidate.jpg", self.story()))
        judge.assert_not_called()

    def test_strict_vision_gate_fails_closed_when_api_is_unavailable(self):
        self.assertIn("fail_open", inspect.signature(news_bot.photo_shows).parameters)
        with tempfile.TemporaryDirectory() as td:
            photo = Path(td) / "candidate.jpg"
            Image.new("RGB", (20, 20), "white").save(photo)
            with patch.object(news_bot, "VISION_GATE", True), \
                    patch.object(news_bot, "ANTHROPIC_API_KEY", "test-key"), \
                    patch.object(news_bot.urllib.request, "urlopen", side_effect=OSError("vision unavailable")):
                verdict = news_bot.photo_shows(photo, "breaking context", fail_open=False)
        self.assertEqual(verdict, "no")

    def test_breaking_no_photo_aborts_with_dedicated_exit_code(self):
        helper = getattr(news_bot, "_handle_no_usable_photo", None)
        self.assertIsNotNone(helper)
        with patch.object(news_bot, "PINNED_EVENT", "حدث عاجل سعودي"), \
                patch.object(news_bot, "notify") as notify:
            with self.assertRaises(SystemExit) as raised:
                helper([self.story()])
        self.assertEqual(raised.exception.code, news_bot.BREAKING_VISUAL_EXIT)
        self.assertIn("صورة", notify.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
