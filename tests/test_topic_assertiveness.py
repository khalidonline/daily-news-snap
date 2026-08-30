import unittest

from topic_editorial import enhance_prompt, validate_brief


class TopicAssertivenessTests(unittest.TestCase):
    def _brief(self):
        return {
            "title": "أسعار الأراضي ارتفعت أسرع من الشقق",
            "body": "ارتفعت أسعار الأراضي السكنية أسرع من الشقق خلال الفترة نفسها وفق البيانات الرسمية.",
            "takeaway": "البيانات تظهر تفاوتاً في وتيرة ارتفاع مكونات السوق السكنية.",
            "caption": "فارق واضح في وتيرة ارتفاع الأراضي والشقق.",
            "sources": ["الهيئة العامة للإحصاء", "جريدة الرياض"],
            "image_queries": ["Riyadh residential land", "Riyadh housing development", "Riyadh residential plots"],
            "image_queries_ar": ["أراضي الرياض", "سكن الرياض", "مخططات الرياض"],
            "image_prompt": "residential land plots in Riyadh",
            "source_url": "https://example.com/source",
        }

    def test_blocks_riyadh_not_a_coincidence_claim(self):
        brief = self._brief()
        brief["body"] = "أسعار الأراضي ارتفعت أكثر من الشقق. واضحة مو صدفة، والمحرك الأكبر هو الأرض."
        brief["takeaway"] = "الأرض لا الشقة هي ما يرفع فاتورة السكن في الرياض هذه الفترة."
        errors = validate_brief(brief)
        self.assertTrue(any("assertiveness exceeds the evidence" in error for error in errors), errors)

    def test_blocks_definitive_causal_shortcuts_across_topics(self):
        for phrase in (
            "هذا هو السبب الحقيقي وراء الارتفاع.",
            "بلا شك هذا العامل هو ما يرفع الأسعار.",
            "واضح أن هذا هو المحرك الأكبر للسوق.",
        ):
            with self.subTest(phrase=phrase):
                brief = self._brief()
                brief["takeaway"] = phrase
                errors = validate_brief(brief)
                self.assertTrue(any("assertiveness exceeds the evidence" in error for error in errors), errors)

    def test_accepts_calibrated_interpretation(self):
        brief = self._brief()
        brief["takeaway"] = "ارتفاع الأراضي بوتيرة أسرع يجعل تكلفة الأرض عاملاً مهماً ضمن تكلفة السكن."
        self.assertFalse(any("assertiveness exceeds the evidence" in error for error in validate_brief(brief)))

    def test_prompt_requires_evidence_calibration_globally(self):
        prompt = enhance_prompt("")
        self.assertIn("لا تجعل قوة العبارة أعلى من قوة الدليل", prompt)
        self.assertIn("«واضحة مو صدفة»", prompt)
        self.assertIn("«تشير البيانات إلى»", prompt)
        self.assertIn("«أحد العوامل»", prompt)


if __name__ == "__main__":
    unittest.main()
