import unittest
import os
from unittest.mock import patch

import guarded_story_publish as gsp


class StoryAutoVisualBufferTests(unittest.TestCase):
    def test_auto_selection_requires_six_approved_visuals(self):
        with patch.object(gsp.rsp.sr, "coverage", return_value=([1, 2, 3, 4], [], "PASS")):
            self.assertFalse(gsp._auto_story_has_visual_buffer("SABIC"))
        with patch.object(gsp.rsp.sr, "coverage", return_value=([1, 2, 3, 4, 5, 6], [], "PASS")):
            self.assertTrue(gsp._auto_story_has_visual_buffer("robust story"))

    def test_scheduled_selection_blocks_unvalidated_story_before_render(self):
        with patch.dict(os.environ, {"STORY_SELECTION_MODE": "scheduled"}), \
             patch.object(gsp.rsp.sb, "STORY", "Alibaba"), \
             patch.object(gsp.rsp.sb, "resolve_story_input", return_value="Alibaba"), \
             patch.object(gsp.sp, "evaluate_story", return_value={
                 "publishable": False,
                 "status": "BLOCKED_FRAME_COVERAGE",
                 "usable_frames": 4,
                 "opening_ok": True,
                 "closing_ok": False,
             }), \
             patch.object(gsp.rsp.sr, "coverage") as coverage:
            with self.assertRaisesRegex(SystemExit, "not prevalidated"):
                gsp._personal_resolve_story()
        coverage.assert_not_called()

    def test_automatic_selection_never_bootstraps_raw_inventory(self):
        with patch.dict(os.environ, {"STORY_SELECTION_MODE": "scheduled"}), \
             patch.object(gsp.rsp.sb, "STORY", ""), \
             patch.object(gsp.rsp.sr, "choose_runtime_story", return_value=""), \
             patch.object(gsp.rsp.sb, "load_stories") as load_stories:
            self.assertEqual(gsp._personal_resolve_story(), "")
        load_stories.assert_not_called()


if __name__ == "__main__":
    unittest.main()
