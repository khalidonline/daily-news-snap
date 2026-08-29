import unittest

import story_bot as sb


RIYADH_STORY = "قصة الرياض: من بلدة مسورة إلى عاصمة اقتصادية"


class StorySubjectFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Populate aliases exactly as production does from stories.txt.
        sb.load_stories()

    def test_riyadh_contract_locks_declared_subject(self):
        contract = sb.story_focus_contract(RIYADH_STORY)
        self.assertIn("Riyadh", contract)
        self.assertIn("الرياض", contract)
        self.assertIn("السفارات", contract)
        self.assertIn("ليست كافية", contract)

    def test_city_prompt_uses_city_arc_instead_of_person_arc(self):
        self.assertIn("إذا كان بطل القصة مدينة أو مكاناً", sb.SYSTEM_PROMPT)
        self.assertIn("لا تُدخل شخصاً كبطل في اللقطة الثانية", sb.SYSTEM_PROMPT)
        self.assertIn("التوسع المادي", sb.SYSTEM_PROMPT)

    def test_frame_visual_context_binds_story_and_specific_frame(self):
        frame = {
            "heading": "خرجت من السور",
            "text": "مع التوسع العمراني، امتدت الرياض خارج حدودها القديمة.",
        }
        context = sb.frame_visual_context(RIYADH_STORY, frame)
        self.assertIn("Riyadh", context)
        self.assertIn("الرياض", context)
        self.assertIn("خرجت من السور", context)
        self.assertIn("امتدت الرياض خارج حدودها القديمة", context)
        self.assertIn("هذه اللقطة تحديداً", context)

    def test_story_photo_gate_requires_confirmed_relevance(self):
        self.assertTrue(sb.story_photo_verdict_ok("yes"))
        self.assertFalse(sb.story_photo_verdict_ok("neutral"))
        self.assertFalse(sb.story_photo_verdict_ok("no"))
        self.assertFalse(sb.story_photo_verdict_ok(""))


if __name__ == "__main__":
    unittest.main()
