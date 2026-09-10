import tempfile
import unittest
from pathlib import Path
from unittest import mock

import story_bot as sb


class ExplicitStoryRecoveryCooldownTests(unittest.TestCase):
    def test_explicit_story_reuses_reviewed_local_assets(self):
        calls = []

        def local(_ar, _en, _out, respect_cooldown=True, exclude=()):
            calls.append(respect_cooldown)
            return None, None

        original_story = sb.STORY
        sb.STORY = "كيف بنت TSMC احتكاراً على رقائق العالم"
        try:
            with tempfile.TemporaryDirectory() as td, \
                    mock.patch.object(sb, "fetch_local_photo", side_effect=local), \
                    mock.patch.object(sb, "fetch_commons_photo", return_value=(None, None)), \
                    mock.patch.object(sb, "fetch_loc_photo", return_value=(None, None)), \
                    mock.patch.object(sb, "fetch_openverse_photo", return_value=(None, None)):
                sb.find_photo(
                    {"image_keywords": ["TSMC"], "image_keywords_ar": []},
                    Path(td) / "frame.jpg",
                    context="",
                )
        finally:
            sb.STORY = original_story

        self.assertTrue(calls)
        self.assertTrue(all(value is False for value in calls))


    def test_text_overflow_blocks_render(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(RuntimeError):
                sb.render_frame(
                    Path(td) / "overflow.png",
                    "ملخص تنفيذي - قصة",
                    "6 / 6",
                    "عنوان طويل للاختبار",
                    60,
                    sub=("نص طويل جداً " * 180),
                    photo=None,
                    punch=("خلاصة طويلة " * 30),
                    footer="المصدر: اختبار",
                )


if __name__ == "__main__":
    unittest.main()
