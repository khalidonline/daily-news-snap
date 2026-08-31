import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image


class BreakingVisualRelevanceTests(unittest.TestCase):
    def runner(self):
        path = Path("breaking_news_runner.py")
        self.assertTrue(path.exists(), "breaking-news visual gate runner is missing")
        import breaking_news_runner
        return breaking_news_runner

    def fake_bot(self, *, verdict_photo="candidate.jpg"):
        notices = []

        def local(_queries_ar, _queries_en, out_path, **_kwargs):
            Path(out_path).write_bytes(b"candidate")
            return str(out_path), "local credit"

        return SimpleNamespace(
            PINNED_EVENT=(
                "وزير خارجية تركيا يعلن بدء تشكيل الهيكل الأساسي "
                "لاتفاق مكة الدفاعي بين السعودية وتركيا وباكستان"
            ),
            POST_ENABLED=True,
            ANTHROPIC_API_KEY="test-key",
            VISION_GATE=True,
            VISION_MODEL="test-model",
            OUT_DIR=Path("out"),
            fetch_local_photo=local,
            notify=lambda text, *args, **kwargs: notices.append(text),
            ksa_stamp=lambda: "2026-08-31-9pm",
            post_story=lambda *args, **kwargs: {"status": "SCHEDULED"},
            main=lambda: None,
            _notices=notices,
        )

    def test_generic_riyadh_library_photo_cannot_qualify_for_breaking(self):
        runner = self.runner()
        bot = self.fake_bot()
        event = bot.PINNED_EVENT
        with patch.object(runner, "_strict_vision_verdict", return_value="neutral") as judge:
            accepted = runner._breaking_photo_acceptable(
                bot, "old-riyadh-souq.jpg", event
            )
        self.assertFalse(accepted)
        context = judge.call_args.args[2]
        self.assertIn("تركيا", context)
        self.assertIn("باكستان", context)

    def test_breaking_visual_requires_explicit_yes(self):
        runner = self.runner()
        bot = self.fake_bot()
        for verdict in ("neutral", "no"):
            with self.subTest(verdict=verdict), \
                    patch.object(runner, "_strict_vision_verdict", return_value=verdict):
                self.assertFalse(
                    runner._breaking_photo_acceptable(bot, "candidate.jpg", bot.PINNED_EVENT)
                )
        with patch.object(runner, "_strict_vision_verdict", return_value="yes"):
            self.assertTrue(
                runner._breaking_photo_acceptable(bot, "candidate.jpg", bot.PINNED_EVENT)
            )

    def test_strict_vision_gate_fails_closed_when_api_is_unavailable(self):
        runner = self.runner()
        bot = self.fake_bot()
        with tempfile.TemporaryDirectory() as td:
            photo = Path(td) / "candidate.jpg"
            Image.new("RGB", (20, 20), "white").save(photo)
            with patch.object(
                runner.urllib.request, "urlopen", side_effect=OSError("vision unavailable")
            ):
                verdict = runner._strict_vision_verdict(
                    bot, photo, "حدث عاجل سعودي"
                )
        self.assertEqual(verdict, "no")

    def test_rejected_local_candidate_is_removed_from_breaking_pipeline(self):
        runner = self.runner()
        bot = self.fake_bot()
        with tempfile.TemporaryDirectory() as td, \
                patch.object(runner, "_strict_vision_verdict", return_value="neutral"):
            hero = Path(td) / "hero.jpg"
            state = runner.install_strict_visual_gate(bot)
            photo, credit = bot.fetch_local_photo(["الرياض"], ["saudi"], hero)
        self.assertIsNone(photo)
        self.assertIsNone(credit)
        self.assertFalse(state["accepted_photo"])

    def test_breaking_no_photo_aborts_with_dedicated_exit_code(self):
        runner = self.runner()
        bot = self.fake_bot()
        with patch.object(runner, "_strict_vision_verdict", return_value="neutral"):
            with self.assertRaises(SystemExit) as raised:
                runner.run_bot(bot)
        self.assertEqual(raised.exception.code, runner.BREAKING_VISUAL_EXIT)
        self.assertTrue(bot._notices)
        self.assertIn("صورة", bot._notices[-1])


if __name__ == "__main__":
    unittest.main()
