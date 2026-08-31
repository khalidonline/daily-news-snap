import os
import tempfile
import unittest

import story_bot as sb
import story_editorial_runtime as ser
import story_editorial_quality as seq
import story_runtime


class StoryFrameAwareRepairTests(unittest.TestCase):
    def test_company_frame_queries_keep_subject_and_frame_terms(self):
        spec = sb.company_frame_spec(
            {
                "image_keywords": ["SAMA"],
                "image_keywords_ar": ["ساما"],
            },
            {
                "image_keywords": ["Saudi silver riyal coin"],
                "image_keywords_ar": ["الريال السعودي الفضي"],
            },
        )

        self.assertEqual(
            ["Saudi silver riyal coin", "SAMA"], spec["image_keywords"]
        )
        self.assertEqual(
            ["الريال السعودي الفضي", "ساما"], spec["image_keywords_ar"]
        )

    def test_sama_modern_headquarters_is_in_explicit_story_pool(self):
        self.assertIn(
            "rt-sama-1.jpg",
            story_runtime._STORY_EXTRA_VISUALS["قصة تأسيس مؤسسة النقد ساما"],
        )

    def test_riyadh_current_revision_reuses_an_approved_locked_brief(self):
        story = "قصة الرياض: من بلدة مسورة إلى عاصمة اقتصادية"
        saved_mode = os.environ.get("STORY_OPERATION_MODE")
        saved_cost_root = os.environ.get("STORY_COST_STATE_ROOT")
        try:
            with tempfile.TemporaryDirectory() as td:
                os.environ["STORY_OPERATION_MODE"] = "visual_only"
                os.environ["STORY_COST_STATE_ROOT"] = td
                brief = story_runtime.sb.research(story)
        finally:
            if saved_mode is None:
                os.environ.pop("STORY_OPERATION_MODE", None)
            else:
                os.environ["STORY_OPERATION_MODE"] = saved_mode
            if saved_cost_root is None:
                os.environ.pop("STORY_COST_STATE_ROOT", None)
            else:
                os.environ["STORY_COST_STATE_ROOT"] = saved_cost_root

        quality = seq.evaluate_brief(brief, 6)
        self.assertTrue(quality.passed, quality.reasons)


if __name__ == "__main__":
    unittest.main()
