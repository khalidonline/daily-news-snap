import unittest
from types import SimpleNamespace

import topic_snapchat
from topic_snapchat import research_with_validation


class TopicEditorialRetryTests(unittest.TestCase):
    def test_finance_topic_gets_third_draft_without_weakening_guards(self):
        calls = []
        bot = SimpleNamespace(SYSTEM_PROMPT="base prompt")

        valid = {
            "title": "وش يعني ثبات الفائدة للتمويل؟",
            "body": "أبقى البنك المركزي السعودي معدل إعادة الشراء عند مستواه الحالي. التمويل المتغير يعتمد على المؤشر المرجعي وهامش البنك وموعد إعادة التسعير، لذلك لا يختزل أثره في قرار واحد.",
            "takeaway": "بيئة الفائدة مستقرة حالياً، بينما أثرها على التمويل يختلف حسب العقد والمؤشر المرجعي.",
            "caption": "ثبات الفائدة مهم، لكن تفاصيل التمويل تحدد الأثر الفعلي.",
            "sources": ["Federal Reserve", "البنك المركزي السعودي"],
            "image_queries": ["Saudi Central Bank SAMA Riyadh", "Saudi banking Riyadh", "Saudi interest rates Riyadh"],
            "image_queries_ar": ["البنك المركزي السعودي", "ساما الرياض", "الفائدة السعودية"],
            "image_prompt": "editorial photograph related to Saudi monetary policy and banking",
            "source_url": "https://www.sama.gov.sa/",
        }

        first = dict(valid)
        first["body"] = valid["body"] * 3
        first["sources"] = ["Reuters", "CNBC"]

        second = dict(valid)
        second["caption"] = "الفيدرالي ثابت وساما مثله، وهذا ينعكس على بيئة التمويل."

        drafts = [first, second, valid]

        def original(topic):
            calls.append(bot.SYSTEM_PROMPT)
            return dict(drafts[len(calls) - 1])

        result = research_with_validation(bot, original, "سعر الفائده وساما")

        self.assertEqual(len(calls), 3)
        self.assertEqual(result["title"], valid["title"])
        self.assertEqual(topic_snapchat.validate_brief(result), [])
        self.assertEqual(bot.SYSTEM_PROMPT, "base prompt")


if __name__ == "__main__":
    unittest.main()
