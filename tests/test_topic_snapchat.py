import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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

    def test_install_uses_full_cooldown_and_snapchat_brand(self):
        bot = SimpleNamespace(
            COOLDOWN_DAYS=21,
            HARD_COOLDOWN_DAYS=5,
            KICKER="ملخص تنفيذي",
            SYSTEM_PROMPT="قواعد اللهجة والمصطلح — اكتب بلسان سعودي رسمي:\n",
            SELECT_PROMPT="اختر الموضوع",
            research=lambda topic: {},
            TOPICS_FILE=Path("topics.txt"),
            choose_topic=lambda exclude=(): "قديم",
        )
        with patch.dict("os.environ", {}, clear=False):
            install(bot)
        self.assertEqual(bot.HARD_COOLDOWN_DAYS, 21)
        self.assertEqual(bot.KICKER, "معلومة تهمك")
        self.assertNotIn("بلسان سعودي رسمي", bot.SYSTEM_PROMPT)
        self.assertIn("سناب شات", bot.SELECT_PROMPT)


if __name__ == "__main__":
    unittest.main()
