import unittest
from unittest.mock import patch

import guarded_story_publish as gsp


class StoryAutoVisualBufferTests(unittest.TestCase):
    def test_auto_selection_requires_six_approved_visuals(self):
        with patch.object(gsp.rsp.sr, "coverage", return_value=([1, 2, 3, 4], [], "PASS")):
            self.assertFalse(gsp._auto_story_has_visual_buffer("SABIC"))
        with patch.object(gsp.rsp.sr, "coverage", return_value=([1, 2, 3, 4, 5, 6], [], "PASS")):
            self.assertTrue(gsp._auto_story_has_visual_buffer("robust story"))


if __name__ == "__main__":
    unittest.main()
