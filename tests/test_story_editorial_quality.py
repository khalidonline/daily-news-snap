import unittest

import story_editorial_quality as seq


def good_brief():
    return {
        "frames": [
            {
                "heading": f"مشهد {i}",
                "text": f"نص واضح ومختلف للقطة رقم {i} يشرح تطور القصة بشكل مباشر.",
                "punch": f"خلاصة واضحة {i}",
                "subject_kind": "company",
                "image_keywords": [f"subject {i}"],
                "image_keywords_ar": [f"موضوع {i}"],
            }
            for i in range(1, 7)
        ],
        "sources": ["https://example.com/source"],
    }


class EditorialQualityTests(unittest.TestCase):
    def test_publication_shaped_brief_passes(self):
        result = seq.evaluate_brief(good_brief(), 6)
        self.assertTrue(result.passed)
        self.assertEqual("EDITORIAL_LOCKED", result.status)

    def test_valid_json_with_duplicate_frames_does_not_lock(self):
        brief = good_brief()
        brief["frames"][4]["heading"] = brief["frames"][3]["heading"]
        brief["frames"][4]["text"] = brief["frames"][3]["text"]
        result = seq.evaluate_brief(brief, 6)
        self.assertFalse(result.passed)
        self.assertEqual("EDITORIAL_REVIEW", result.status)

    def test_missing_sources_fails(self):
        brief = good_brief()
        brief["sources"] = []
        self.assertFalse(seq.evaluate_brief(brief, 6).passed)

    def test_wrong_frame_count_fails(self):
        brief = good_brief()
        brief["frames"].pop()
        self.assertFalse(seq.evaluate_brief(brief, 6).passed)

    def test_empty_required_field_fails(self):
        brief = good_brief()
        brief["frames"][2]["punch"] = ""
        self.assertFalse(seq.evaluate_brief(brief, 6).passed)

    def test_model_boilerplate_or_raw_json_fails(self):
        brief = good_brief()
        brief["frames"][1]["text"] = "As an AI language model, here is the answer: {\"frame\": 2}"
        self.assertFalse(seq.evaluate_brief(brief, 6).passed)

    def test_closing_question_is_not_a_payoff(self):
        brief = good_brief()
        brief["frames"][-1]["punch"] = "فماذا سيحدث بعد ذلك؟"
        self.assertFalse(seq.evaluate_brief(brief, 6).passed)

    def test_unsupported_comparative_phrase_routes_to_review(self):
        brief = good_brief()
        brief["frames"][2]["text"] += " وهي تتفوق على الجميع بلا مصدر محدد."
        self.assertFalse(seq.evaluate_brief(brief, 6).passed)


if __name__ == "__main__":
    unittest.main()
