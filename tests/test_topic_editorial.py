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

    def _complete_brief(self):
        return {
            "title": "فاتورتك تتغير بهذا السبب",
            "body": "إذا ارتفع استهلاكك بالصيف، يبان الفرق بسرعة. وفق بيانات الجهة الرسمية، التعرفة مرتبطة بشرائح الاستهلاك.",
            "takeaway": "شرائح الاستهلاك هي العامل الذي يفسر تغير الفاتورة مع ارتفاع الاستخدام.",
            "caption": "رقم واحد يوضح لماذا تختلف الفاتورة بين شهر وآخر.",
            "sources": ["هيئة تنظيم المياه والكهرباء", "Reuters"],
            "image_queries": ["Saudi electricity meter Riyadh", "Saudi home electricity Riyadh", "Saudi summer home Riyadh"],
            "image_queries_ar": ["كهرباء", "عداد", "الرياض"],
            "image_prompt": "a modern electricity meter on a Saudi home wall in Riyadh",
            "source_url": "https://example.com/source",
        }

    def test_validate_brief_accepts_complete_snapchat_brief(self):
        self.assertEqual(validate_brief(self._complete_brief()), [])

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

    def test_validate_brief_blocks_run_71_style_foreign_policy_overclaim(self):
        brief = self._complete_brief()
        brief.update({
            "title": "قسطك مرتبط بقرار في واشنطن مو الرياض",
            "body": "إذا عندك قرض بفائدة متغيرة، قرار الفيدرالي يوصلك خلال أيام.",
            "takeaway": "أثر القرار الخارجي يمر عبر السياسة النقدية المحلية وشروط التمويل.",
        })
        errors = validate_brief(brief)
        self.assertTrue(any("indirect financial relationship" in error for error in errors), errors)

    def test_validate_brief_blocks_personalized_foreign_rate_hook(self):
        brief = self._complete_brief()
        brief.update({
            "title": "الفيدرالي ثبّت الفائدة... وقسطك؟",
            "body": "قرار أمريكا الأخير يخصك إذا كان تمويلك متغيراً، لكن الأثر الفعلي يعتمد على المؤشر والعقد.",
            "takeaway": "تكلفة التمويل المتغير تعتمد على المؤشر المرجعي وهامش البنك وموعد إعادة التسعير.",
            "caption": "ثبات الفائدة جزء من السياق النقدي، وليس العامل الوحيد في تكلفة التمويل.",
            "sources": ["Federal Reserve", "البنك المركزي السعودي"],
        })
        errors = validate_brief(brief)
        self.assertTrue(any("personalize a foreign central-bank decision" in error for error in errors), errors)

    def test_validate_brief_blocks_run_72_repo_only_claim(self):
        brief = self._complete_brief()
        brief.update({
            "title": "الفيدرالي ثبّت الفائدة",
            "body": "إذا عندك تمويل بفائدة متغيرة، قرار الفيدرالي يهمك لأن الريال مربوط بالدولار.",
            "takeaway": "التمويل المتغير يتحرك فقط لو غيّر ساما سعر الريبو فعلياً.",
            "caption": "وش يعني ثبات الفائدة للتمويل المتغير؟",
            "sources": ["Federal Reserve", "البنك المركزي السعودي"],
        })
        errors = validate_brief(brief)
        self.assertTrue(any("policy rate is not the only driver" in error for error in errors), errors)

    def test_validate_brief_blocks_institution_following_language(self):
        brief = self._complete_brief()
        brief.update({
            "title": "الفيدرالي ثبّت الفائدة وساما لحقه",
            "body": "الريال مربوط بالدولار، لكن كل جهة لها قرارها وسياقها المحلي.",
            "takeaway": "إعادة تسعير التمويل المتغير تعتمد على المؤشر المرجعي وشروط العقد.",
            "caption": "وش يعني ثبات الفائدة للتمويل المتغير؟",
            "sources": ["Federal Reserve", "البنك المركزي السعودي"],
        })
        errors = validate_brief(brief)
        self.assertTrue(any("state each institution's decision separately" in error for error in errors), errors)

    def test_validate_brief_requires_primary_sources_for_fed_sama_topic(self):
        brief = self._complete_brief()
        brief.update({
            "title": "وش يعني قرار الفيدرالي للتمويل المتغير؟",
            "body": "الريال مربوط بالدولار، لذلك قرار الفيدرالي يؤثر على اتجاه الفائدة في السعودية، لكن الأثر الفعلي يعتمد على المؤشر والعقد.",
            "takeaway": "التمويل المتغير يعتمد على المؤشر وهامش البنك وموعد إعادة التسعير.",
            "caption": "الفائدة الأمريكية جزء من الصورة، وليست العامل الوحيد في تكلفة التمويل.",
            "sources": ["أرقام", "اليوم السابع", "الإمارات اليوم"],
        })
        errors = validate_brief(brief)
        self.assertTrue(any("Federal Reserve and SAMA primary sources" in error for error in errors), errors)

    def test_validate_brief_accepts_clear_conditional_finance_explanation(self):
        brief = self._complete_brief()
        brief.update({
            "title": "وش يعني ثبات الفائدة للتمويل المتغير؟",
            "body": "ارتباط الريال بالدولار يجعل الفائدة المحلية تتأثر بالسياسة الأمريكية. وإذا كان التمويل متغيراً، يعتمد الأثر الفعلي على عقده وتسعير البنك.",
            "takeaway": "في التمويل المتغير، الأثر الفعلي يعتمد على الفائدة المحلية وشروط العقد.",
            "caption": "القرار الأمريكي مهم للسياق النقدي، لكنه لا يحدد القسط وحده.",
            "sources": ["Federal Reserve", "البنك المركزي السعودي"],
        })
        self.assertEqual(validate_brief(brief), [])

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

    def test_enhance_prompt_keeps_finance_hooks_informative_not_geographic_or_advisory(self):
        prompt = enhance_prompt("", date(2026, 8, 29))
        self.assertIn("العلاقة المباشرة وغير المباشرة", prompt)
        self.assertIn("وش يعني ثبات الفائدة للتمويل المتغير؟", prompt)
        self.assertIn("المؤشر المرجعي", prompt)
        self.assertIn("ليس دورك أن تعلّم", prompt)
        self.assertIn("من دون توجيه القارئ", prompt)
        self.assertIn("لا تجعل قراراً أجنبياً يبدو كأنه موجه شخصياً للقارئ", prompt)

    def test_enhance_prompt_teaches_saibor_margin_and_separate_institutions(self):
        prompt = enhance_prompt("", date(2026, 8, 29))
        self.assertIn("سايبور", prompt)
        self.assertIn("هامش البنك", prompt)
        self.assertIn("موعد إعادة التسعير", prompt)
        self.assertIn("اعرض قرار كل جهة على حدة", prompt)
        self.assertIn("وش يعني ثبات الفائدة للتمويل المتغير؟", prompt)
        self.assertIn("المصدرين الأوليين", prompt)
        self.assertIn("صورة تحريرية عالية الجودة", prompt)
        self.assertIn("حقل takeaway ليس نصيحة", prompt)
        self.assertNotIn("وساما تبعه", prompt)


if __name__ == "__main__":
    unittest.main()
