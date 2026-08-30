import unittest

import guarded_story_publish as gsp


class StoryVisualAccountingTests(unittest.TestCase):
    def test_failed_visual_state_counts_typographic_cards_as_missing(self):
        state = {
            "frames": {
                "1": {"status": "FAIL"},
                "2": {"status": "FAIL"},
                "3": {"status": "FAIL"},
                "4": {"status": "FAIL"},
                "5": {"status": "PASS"},
                "6": {"status": "FAIL"},
            }
        }

        report = gsp.visual_accounting(state, frame_count=6)

        self.assertEqual(report["approved_visual_frames"], [5])
        self.assertEqual(report["missing_visual_frames"], [1, 2, 3, 4, 6])
        self.assertEqual(report["approved_visual_count"], 1)
        self.assertEqual(report["missing_visual_count"], 5)

    def test_missing_state_counts_every_frame_as_missing(self):
        report = gsp.visual_accounting({}, frame_count=6)

        self.assertEqual(report["approved_visual_frames"], [])
        self.assertEqual(report["missing_visual_frames"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(report["missing_visual_count"], 6)


if __name__ == "__main__":
    unittest.main()
