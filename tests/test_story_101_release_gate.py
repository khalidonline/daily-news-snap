import unittest

import ready_story_publish as rsp
import story_bot as sb


class Story101ReleaseGateTests(unittest.TestCase):
    def test_review_deck_is_never_publishable(self):
        with self.assertRaises(SystemExit):
            rsp.require_ready_for_publication("REVIEW", "قصة تأسيس مؤسسة النقد ساما")

    def test_ready_deck_is_publishable(self):
        rsp.require_ready_for_publication("READY", "story")

    def test_typographic_frames_still_count_as_missing_visuals(self):
        frames = [
            {"text": "1952"},
            {"text": "1953"},
            {"text": "1954"},
            {"text": "1955"},
            {"text": "photo"},
            {"text": "photo"},
        ]
        photos = [None, None, None, None, "5.jpg", "6.jpg"]
        self.assertEqual(sb._missing_visual_indices(frames, photos), [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
