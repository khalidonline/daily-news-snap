import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from daily_news_runner import _story_for_queries, remember_story_contexts
from topic_snapchat import install, prepare_shortlist, research_with_validation


class TopicSnapchatRuntimeTests(unittest.TestCase):
    def test_prepare_shortlist_uses_bounded_performance_and_categories(self):
        with tempfile.TemporaryDirectory() as td:
            topics_path = Path(td) / "topics.txt"
            topics_path.write_text(
                "# ═══ المال الشخصي ═══\nمال 1\nمال 2\n"
                "# ═══ التقنية ═══\nتقنية\n",
                encoding="utf-8",
            )
            bot = SimpleNamespace(TOPICS_FILE=topics_path)
            scored = [
                {"topic": "مال 1", "score": 5, "reasons": ["من القائمة العامة"]},
                {"topic": "مال 2", "score": 5, "reasons": ["من القائمة العامة"]},
                {"topic": "تقنية", "score": 5, "reasons": ["من القائمة العامة"]},
            ]
            shortlist = prepare_shortlist(bot, scored, {"categories": {"التقنية": 4}}, limit=3)
        self.assertEqual(shortlist[0]["topic"], "تقنية")
        self.assertEqual({row["category"] for row in shortlist}, {"المال الشخصي", "التقنية"})

    def test_research_validation_retries_once(self):
        calls = []
        bot = SimpleNamespace(SYSTEM_PROMPT="base prompt")

        def original(topic):
            calls.append((topic, bot.SYSTEM_PROMPT))
            if len(calls) == 1:
                return {"title": "عنوان فقط"}
            return {
                "title": "عنوان صالح",
                "body": "متن صالح",
                "takeaway": "خلاصة صالحة",
                "caption": "تعليق صالح",
                "sources": ["واس", "Reuters"],
                "image_queries": ["Saudi Riyadh street", "Saudi Riyadh people", "Saudi Riyadh city"],
                "image_queries_ar": ["الرياض", "ناس", "مدينة"],
                "image_prompt": "a street scene in Riyadh Saudi Arabia",
                "source_url": "https://example.com/source",
            }

        brief = research_with_validation(bot, original, "موضوع")
        self.assertEqual(brief["title"], "عنوان صالح")
        self.assertEqual(len(calls), 2)
        self.assertIn("فشلت في بوابة الجودة", calls[1][1])
        self.assertEqual(bot.SYSTEM_PROMPT, "base prompt")

    def test_research_validation_blocks_after_second_invalid_result(self):
        bot = SimpleNamespace(SYSTEM_PROMPT="base prompt")
        with self.assertRaisesRegex(SystemExit, "failed editorial validation"):
            research_with_validation(bot, lambda topic: {"title": "ناقص"}, "موضوع")

    def test_research_remembers_full_topic_context_for_image_relevance(self):
        remember_story_contexts({"stories": []})
        brief = {
            "title": "العنوان الذي سيراه المتابع",
            "body": "المعلومة الأساسية التي يجب أن تعكسها الصورة",
            "takeaway": "الخلاصة العملية",
            "caption": "تعليق",
            "sources": ["واس", "Reuters"],
            "image_queries": ["Saudi Riyadh school", "Saudi students Riyadh", "Saudi classroom"],
            "image_queries_ar": ["الرياض", "طلاب", "مدارس"],
            "image_prompt": "Saudi students in a Riyadh classroom",
            "source_url": "https://example.com/source",
        }
        bot = SimpleNamespace(SYSTEM_PROMPT="base prompt")
        result = research_with_validation(bot, lambda topic: dict(brief), "موضوع")
        story = _story_for_queries(result["image_queries"], result["image_queries_ar"])
        self.assertIsNotNone(story)
        self.assertEqual(story["headline"], brief["title"])
        self.assertEqual(story["summary"], brief["body"])
        self.assertEqual(story["takeaway"], brief["takeaway"])
        self.assertEqual(story["link"], brief["source_url"])
        remember_story_contexts({"stories": []})

    def test_install_uses_full_cooldown_snapchat_brand_shared_model_and_auto_images(self):
        rendered_credits = []

        def renderer(brief, out_path, photo_path=None, photo_credit=None):
            rendered_credits.append(photo_credit)
            return out_path

        def pair(*args, **kwargs):
            return None, None

        def stock(*args, **kwargs):
            return None

        bot = SimpleNamespace(
            COOLDOWN_DAYS=21,
            HARD_COOLDOWN_DAYS=5,
            KICKER="ملخص تنفيذي",
            CLAUDE_MODEL="claude-sonnet-5",
            TOPIC_MODEL="claude-opus-5",
            IMAGE_SOURCE="spa",
            SYSTEM_PROMPT="قواعد اللهجة والمصطلح — اكتب بلسان سعودي رسمي:\n",
            SELECT_PROMPT="اختر الموضوع",
            research=lambda topic: {},
            TOPICS_FILE=Path("topics.txt"),
            choose_topic=lambda exclude=(): "قديم",
            render_story=renderer,
            render_topic=renderer,
            fetch_local_photo=pair,
            fetch_article_photo=pair,
            fetch_spa_photo=pair,
            fetch_commons_photo=pair,
            fetch_loc_photo=pair,
            fetch_openverse_photo=pair,
            fetch_photo=stock,
            photo_shows=lambda photo, context: "no",
            _AUTO_IMAGE_SELECTOR_INSTALLED=False,
        )
        with patch.dict("os.environ", {}, clear=False):
            install(bot)
        self.assertEqual(bot.HARD_COOLDOWN_DAYS, 21)
        self.assertEqual(bot.KICKER, "معلومة تهمك")
        self.assertEqual(bot.TOPIC_MODEL, bot.CLAUDE_MODEL)
        self.assertEqual(bot.IMAGE_SOURCE, "auto")
        self.assertTrue(bot._AUTO_IMAGE_SELECTOR_INSTALLED)
        self.assertNotIn("بلسان سعودي رسمي", bot.SYSTEM_PROMPT)
        self.assertIn("سناب شات", bot.SELECT_PROMPT)

        bot.render_story({}, Path("card.png"), Path("hero.jpg"), "Pexels")
        bot.render_topic({}, Path("card.png"), Path("hero.jpg"), "SPA")
        self.assertEqual(rendered_credits, [None, None])

    def test_topic_workflow_has_no_image_source_choice_and_forces_auto(self):
        workflow = Path(".github/workflows/topic.yml").read_text(encoding="utf-8")
        self.assertNotIn("image_source:", workflow)
        self.assertNotIn("inputs.image_source", workflow)
        self.assertIn('IMAGE_SOURCE: "auto"', workflow)


if __name__ == "__main__":
    unittest.main()
