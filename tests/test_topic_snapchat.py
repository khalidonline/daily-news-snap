import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import topic_snapchat
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
            "takeaway": "الخلاصة الخبرية",
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

    def test_run_74_teacher_like_action_line_is_publish_blocking(self):
        brief = {
            "title": "وش يعني ثبات الفائدة للتمويل المتغير؟",
            "body": "الفائدة المرجعية والتمويل المتغير لا يتحركان دائماً بالطريقة نفسها؛ العقد يحدد المؤشر والهامش وموعد إعادة التسعير.",
            "takeaway": "راجع مؤشر تمويلك المتغير في العقد، ولا تفترض ارتباطه المباشر بقرار واحد.",
            "caption": "ثبات الفائدة لا يعني أن كل تمويل متغير سيبقى كما هو.",
            "sources": ["Federal Reserve", "البنك المركزي السعودي"],
            "image_queries": ["Saudi Central Bank headquarters Riyadh", "Saudi banking finance Riyadh", "Saudi mortgage banking Riyadh"],
            "image_queries_ar": ["البنك المركزي السعودي", "تمويل بنكي", "تمويل عقاري"],
            "image_prompt": "high-quality editorial photograph about Saudi banking and variable-rate financing",
            "source_url": "https://www.sama.gov.sa/",
        }
        errors = topic_snapchat.validate_brief(brief)
        self.assertTrue(any("instructional or advisory" in error for error in errors), errors)

    def test_run_74_institution_comparison_is_publish_blocking(self):
        brief = {
            "title": "الفائدة الأمريكية ثابتة",
            "body": "التمويل المتغير يعتمد على المؤشر المرجعي وهامش البنك وموعد إعادة التسعير.",
            "takeaway": "تكلفة التمويل تتأثر بعدة عوامل، وليس بقرار واحد فقط.",
            "caption": "الفيدرالي ثابت وساما مثله، لكن تفاصيل العقد هي التي تحدد إعادة التسعير.",
            "sources": ["Federal Reserve", "البنك المركزي السعودي"],
            "image_queries": ["Saudi Central Bank headquarters Riyadh", "Saudi banking finance Riyadh", "Saudi mortgage banking Riyadh"],
            "image_queries_ar": ["البنك المركزي السعودي", "تمويل بنكي", "تمويل عقاري"],
            "image_prompt": "high-quality editorial photograph about Saudi banking and variable-rate financing",
            "source_url": "https://www.sama.gov.sa/",
        }
        errors = topic_snapchat.validate_brief(brief)
        self.assertTrue(any("state each institution's decision separately" in error for error in errors), errors)

    def test_credit_policy_rejects_attribution_required_open_images(self):
        policy = getattr(topic_snapchat, "_credit_requires_visible", None)
        self.assertIsNotNone(policy)
        self.assertTrue(policy("openverse", "Alice / CC BY 4.0"))
        self.assertTrue(policy("commons", "Alice / Wikimedia Commons"))
        self.assertFalse(policy("openverse", "Openverse / CC CC0 1.0"))
        self.assertFalse(policy("openverse", "Public Domain / PDM"))
        self.assertFalse(policy("loc", "Library of Congress"))
        self.assertFalse(policy("stock", "Pexels"))

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
            photo_shows=lambda photo, context: "neutral",
            recent_fallback=lambda path: "old-unrelated-photo.jpg",
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

        # Topic Brief is stricter than Daily News: neutral imagery and unrelated
        # recent-photo reuse are not valid fallbacks. A generated topic-specific
        # image can run after the real-photo search is exhausted.
        self.assertEqual(bot.photo_shows(Path("candidate.jpg"), "topic"), "no")
        self.assertIsNone(bot.recent_fallback(Path("hero.jpg")))

        # The bot surfaces what matters; it does not tell the follower what to do.
        self.assertIn("ليس دورك أن تعلّم", bot.SYSTEM_PROMPT)
        self.assertIn("takeaway", bot.SYSTEM_PROMPT)
        self.assertIn("صورة تحريرية عالية الجودة", bot.SYSTEM_PROMPT)
        self.assertNotIn("يمكن للمتابع استخدامه", bot.SELECT_PROMPT)

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
