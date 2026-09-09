import tempfile
import unittest
import json
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

    def test_exact_named_location_can_pass_without_depicting_event_moment(self):
        runner = self.runner()
        prompt = runner._BREAKING_VISION_PROMPT
        self.assertIn("المكان المحدد نفسه", prompt)
        self.assertIn("لا يشترط أن تُظهر لحظة الحدث", prompt)
        self.assertIn("صورة أرشيفية", prompt)

    def test_verified_asset_provenance_reaches_visual_gate(self):
        runner = self.runner()
        bot = self.fake_bot()
        with tempfile.TemporaryDirectory() as td:
            photo = Path(td) / "candidate.jpg"
            photo.write_bytes(b"candidate")
            Path(str(photo) + ".exempt").write_text(
                "local:kharg-island-oil-terminal-nasa.jpg\\n"
                "tags: Kharg Island oil terminal Iran, tanker docks, oil tanks\\n"
                "credit: NASA / Public domain — Wikimedia Commons",
                encoding="utf-8",
            )
            with patch.object(
                runner, "_strict_vision_verdict", return_value="yes"
            ) as judge:
                accepted = runner._breaking_photo_acceptable(
                    bot, photo, "انفجارات قرب جزيرة خرج"
                )
        self.assertTrue(accepted)
        context = judge.call_args.args[2]
        self.assertIn("kharg-island-oil-terminal-nasa.jpg", context)
        self.assertIn("tanker docks", context)
        self.assertIn("NASA", context)

    def test_local_asset_marker_carries_curated_provenance(self):
        import news_bot
        with tempfile.TemporaryDirectory() as td:
            asset = Path(td) / "kharg-island-oil-terminal-nasa.jpg"
            asset.write_bytes(b"candidate")
            hero = Path(td) / "hero.jpg"
            entry = {
                "path": asset,
                "tags": ["Kharg Island oil terminal Iran", "tanker docks"],
                "credit": "NASA / Public domain — Wikimedia Commons",
            }
            with patch.object(news_bot, "load_local_images", return_value=[entry]), \
                    patch.object(news_bot, "MIN_PHOTO_SCORE", 10):
                photo, credit = news_bot.fetch_local_photo(
                    [], ["Kharg Island oil terminal Iran"], hero,
                    respect_cooldown=False,
                )
            marker = Path(str(hero) + ".exempt").read_text(encoding="utf-8")
        self.assertEqual(photo, str(hero))
        self.assertEqual(credit, entry["credit"])
        self.assertIn("Kharg Island oil terminal Iran", marker)
        self.assertIn("tanker docks", marker)
        self.assertIn("NASA", marker)

    def test_verified_commons_context_reaches_visual_gate(self):
        runner = self.runner()
        bot = self.fake_bot()
        with tempfile.TemporaryDirectory() as td:
            photo = Path(td) / "candidate.jpg"
            photo.write_bytes(b"candidate")
            Path(str(photo) + ".commons-context").write_text(
                "File:ISS005-E-11900 lrg.jpg\\n"
                "Kharg Island oil terminal; tanker docks, tanks and infrastructure\\n"
                "NASA Johnson Space Center / Public domain",
                encoding="utf-8",
            )
            with patch.object(
                runner, "_strict_vision_verdict", return_value="yes"
            ) as judge:
                accepted = runner._breaking_photo_acceptable(
                    bot, photo, "انفجارات قرب جزيرة خرج"
                )
        self.assertTrue(accepted)
        context = judge.call_args.args[2]
        self.assertIn("ISS005-E-11900", context)
        self.assertIn("tanker docks", context)
        self.assertIn("NASA", context)

    def test_curated_commons_kharg_terminal_is_registered(self):
        import news_bot
        resolver = getattr(news_bot, "_curated_commons_file_titles", lambda _q: [])
        self.assertIn(
            "File:ISS005-E-11900 lrg.jpg",
            resolver(["Kharg Island oil terminal Iran"]),
        )

    def test_curated_commons_saudi_map_is_registered(self):
        import news_bot
        resolver = getattr(news_bot, "_curated_commons_file_titles", lambda _q: [])
        self.assertIn(
            "File:Saudi Arabia map-ar.png",
            resolver(["Saudi Arabia map"]),
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

    def test_visual_verdict_cache_avoids_second_paid_call(self):
        runner = self.runner()
        bot = self.fake_bot()
        with tempfile.TemporaryDirectory() as td:
            photo = Path(td) / "candidate.jpg"
            Image.new("RGB", (20, 20), "white").save(photo)
            response = {"content": [{"type": "text", "text": "نعم — مرتبطة"}], "usage": {}}
            body = json.dumps(response).encode()
            class FakeResponse:
                def __enter__(self): return self
                def __exit__(self, *_args): return False
                def read(self): return body
            with patch.object(runner, "CACHE_FILE", Path(td) / "cache.json"), \
                    patch.object(runner.urllib.request, "urlopen", return_value=FakeResponse()) as api, \
                    patch.object(runner.model_meter, "require_response_capacity"), \
                    patch.object(runner.model_meter, "require_run_cost_capacity"), \
                    patch.object(runner.model_meter, "note_successful_response"), \
                    patch.object(runner.model_meter, "record_anthropic_response"):
                first = runner._strict_vision_verdict(bot, photo, bot.PINNED_EVENT)
                second = runner._strict_vision_verdict(bot, photo, bot.PINNED_EVENT)
        self.assertEqual(("yes", "yes"), (first, second))
        self.assertEqual(1, api.call_count)

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
        self.assertEqual([], bot._notices)


    def test_recoverable_visual_no_card_notice_stays_internal(self):
        runner = self.runner()
        bot = self.fake_bot()
        runner.install_recovery_notification_filter(bot)
        bot.notify(
            "⚠️ slot — no card: visual recovery infrastructure failed for: event"
        )
        self.assertEqual([], bot._notices)
        bot.notify("[DRY RUN] would have posted: delivered", "card.png")
        self.assertEqual(["[DRY RUN] would have posted: delivered"], bot._notices)

    def test_review_mode_no_photo_also_aborts_instead_of_false_success(self):
        runner = self.runner()
        bot = self.fake_bot()
        bot.DRY_RUN = True
        bot.POST_ENABLED = False
        with patch.object(runner, "_strict_vision_verdict", return_value="neutral"):
            with self.assertRaises(SystemExit) as raised:
                runner.run_bot(bot)
        self.assertEqual(runner.BREAKING_VISUAL_EXIT, raised.exception.code)


class BreakingEditorialCacheTests(unittest.TestCase):
    def test_event_time_is_forced_into_cached_story_summary(self):
        import breaking_news_runner as runner
        cached = {
            "stories": [{
                "headline": "هجوم حوثي جنوب السعودية",
                "summary": "أصيب 73 مدنياً",
                "takeaway": "رُفعت حالة التأهب",
            }]
        }
        bot = SimpleNamespace(summarize=lambda *_a, **_k: cached)
        runner.install_visible_event_time(
            bot,
            "هجوم مؤكد — وقت الحدث: غير محدد (8 سبتمبر 2026)",
        )
        result = bot.summarize([])
        self.assertIn(
            "وقت الحدث: غير محدد (8 سبتمبر 2026)",
            result["stories"][0]["summary"],
        )

    def test_existing_event_time_is_not_duplicated(self):
        import breaking_news_runner as runner
        cached = {"stories": [{"summary": "وقت الحدث: 18:30 بتوقيت السعودية"}]}
        bot = SimpleNamespace(summarize=lambda *_a, **_k: cached)
        runner.install_visible_event_time(
            bot, "حدث مؤكد — وقت الحدث: 18:30 بتوقيت السعودية"
        )
        result = bot.summarize([])
        self.assertEqual(
            1, result["stories"][0]["summary"].count("وقت الحدث:")
        )

    def test_visual_repair_reuses_editorial_without_calling_model(self):
        import breaking_news_runner as runner
        event = "قرار سعودي عاجل مؤكد الآن"
        cached = {"caption": "خبر", "stories": [{"headline": "عنوان"}]}
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td) / "cache.json"
            cache.write_text(json.dumps({"editorial": {runner._event_fingerprint(event): {"result": cached}}}, ensure_ascii=False), encoding="utf-8")
            calls = []
            bot = SimpleNamespace(summarize=lambda *_a, **_k: calls.append(1))
            with patch.object(runner, "CACHE_FILE", cache):
                runner.install_editorial_cache(bot, event, "repair_visual")
                result = bot.summarize([], pinned=event)
        self.assertEqual(cached, result)
        self.assertEqual([], calls)

    def test_visual_repair_without_cache_fails_before_model_call(self):
        import breaking_news_runner as runner
        calls = []
        bot = SimpleNamespace(summarize=lambda *_a, **_k: calls.append(1))
        with tempfile.TemporaryDirectory() as td, patch.object(runner, "CACHE_FILE", Path(td) / "missing.json"):
            runner.install_editorial_cache(bot, "حدث جديد", "repair_visual")
            with self.assertRaises(SystemExit):
                bot.summarize([], pinned="حدث جديد")
        self.assertEqual([], calls)

    def test_regenerate_editorial_refreshes_cached_result_once(self):
        import breaking_news_runner as runner
        result = {"caption": "جديد", "stories": [{"headline": "عنوان جديد"}]}
        calls = []
        bot = SimpleNamespace(summarize=lambda *_a, **_k: calls.append(1) or result, commit_and_push=lambda *_a, **_k: None)
        with tempfile.TemporaryDirectory() as td, patch.object(runner, "CACHE_FILE", Path(td) / "cache.json"):
            runner.install_editorial_cache(bot, "حدث مؤكد", "regenerate_editorial")
            actual = bot.summarize([], pinned="حدث مؤكد")
        self.assertEqual(result, actual)
        self.assertEqual([1], calls)


if __name__ == "__main__":
    unittest.main()
