import tempfile
import unittest
from datetime import date
from pathlib import Path

from topic_editorial import (
    balanced_shortlist,
    enhance_prompt,
    load_topics_with_categories,
    performance_adjustment,
    validate_brief,
)


class TopicEditorialTests(unittest.TestCase):
    def test_load_topics_preserves_major_category(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "topics.txt"
            path.write_text(
                "# ═══ المال الشخصي ═══\n"
                "كيف أوفر من راتبي؟ | راتب, ادخار\n"
                "# ═══ التقنية ═══\n"
                "ماذا تغير في الذكاء الاصطناعي؟ | ai, ذكاء\n",
                encoding="utf-8",
            )
            topics = load_topics_with_categories(path)
        self.assertEqual(topics[0]["category"], "المال الشخصي")
        self.assertEqual(topics[1]["category"], "التقنية")
        self.assertEqual(topics[0]["triggers"], ["راتب", "ادخار"])

    def test_balanced_shortlist_does_not_let_file_order_fill_all_slots(self):
        scored = [
            {"topic": f"مال {i}", "score": 5, "category": "المال الشخصي", "reasons": ["من القائمة العامة"]}
            for i in range(10)
        ] + [
            {"topic": "تقنية", "score": 5, "category": "التقنية", "reasons": ["من القائمة العامة"]},
            {"topic": "سيارات", "score": 5, "category": "السيارات والنقل", "reasons": ["من القائمة العامة"]},
            {"topic": "رياضة", "score": 5, "category": "الرياضة", "reasons": ["من القائمة العامة"]},
        ]
        shortlist = balanced_shortlist(scored, limit=8)
        categories = {row["category"] for row in shortlist}
        self.assertTrue({"المال الشخصي", "التقنية", "السيارات والنقل", "الرياضة"} <= categories)

    def test_balanced_shortlist_keeps_strong_current_signals(self):
        scored = [
            {"topic": "خبر نفط", "score": 45, "category": "الاقتصاد", "reasons": ["في أخبار الأمس: نفط"]},
            {"topic": "خبر أوبك", "score": 44, "category": "الاقتصاد", "reasons": ["في أخبار الأمس: أوبك"]},
            {"topic": "تقنية عامة", "score": 5, "category": "التقنية", "reasons": ["من القائمة العامة"]},
        ]
        shortlist = balanced_shortlist(scored, limit=2)
        self.assertEqual([row["topic"] for row in shortlist], ["خبر نفط", "خبر أوبك"])

    def test_performance_adjustment_is_bounded(self):
        performance = {"categories": {"التقنية": 100}, "topics": {"موضوع": 100}}
        self.assertEqual(performance_adjustment("موضوع", "التقنية", performance), 15)

    def test_validate_brief_accepts_complete_snapchat_brief(self):
        brief = {
            "title": "فاتورتك تتغير بهذا السبب",
            "body": "إذا ارتفع استهلاكك بالصيف، يبان الفرق بسرعة. وفق بيانات الجهة الرسمية، التعرفة مرتبطة بشرائح الاستهلاك.",
            "takeaway": "قارن استهلاك هذا الشهر بنفس الشهر من السنة الماضية.",
            "caption": "رقم واحد يستحق تراجعه قبل نهاية الشهر.",
            "sources": ["هيئة تنظيم المياه والكهرباء", "Reuters"],
            "image_queries": ["Saudi electricity meter Riyadh", "Saudi home electricity Riyadh", "Saudi summer home Riyadh"],
            "image_queries_ar": ["كهرباء", "عداد", "الرياض"],
            "image_prompt": "a modern electricity meter on a Saudi home wall in Riyadh",
            "source_url": "https://example.com/source",
        }
        self.assertEqual(validate_brief(brief), [])

    def test_validate_brief_rejects_oversized_fields(self):
        brief = {
            "title": "ط" * 46,
            "body": "ب" * 261,
            "takeaway": "خ" * 111,
            "caption": "ن" * 121,
            "sources": ["واس", "Reuters"],
            "image_queries": ["Saudi Riyadh street", "Saudi Riyadh people", "Saudi Riyadh city"],
            "image_queries_ar": ["الرياض", "ناس", "مدينة"],
            "image_prompt": "a street scene in Riyadh Saudi Arabia",
            "source_url": "https://example.com/source",
        }
        errors = validate_brief(brief)
        self.assertIn("title exceeds 45 characters", errors)
        self.assertIn("body exceeds 260 characters", errors)
        self.assertIn("takeaway exceeds 110 characters", errors)
        self.assertIn("caption exceeds 120 characters", errors)

    def test_enhance_prompt_resolves_voice_conflict_and_adds_ksa_date(self):
        base = (
            "- sources: أسماء المصادر (٢ إلى ٤). إن كان المصدر أجنبياً فاكتبه بالعربية.\n"
            "قواعد اللهجة والمصطلح — اكتب بلسان سعودي رسمي:\n"
            "- قل \"المملكة\" لا \"السعودية\" في كل مرة، و\"المواطنين\" و\"المقيمين\" حين يلزم.\n"
        )
        prompt = enhance_prompt(base, date(2026, 8, 29))
        self.assertNotIn("إن كان المصدر أجنبياً فاكتبه بالعربية", prompt)
        self.assertNotIn("بلسان سعودي رسمي", prompt)
        self.assertNotIn('قل "المملكة" لا "السعودية" في كل مرة', prompt)
        self.assertIn("Reuters", prompt)
        self.assertIn("29 أغسطس 2026", prompt)
        self.assertIn("جمهور سعودي عربي على سناب شات", prompt)


if __name__ == "__main__":
    unittest.main()
