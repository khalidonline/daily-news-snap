import unittest

import story_bot as sb


class StoryVisualAccountingTests(unittest.TestCase):
    def test_typographic_frames_still_count_as_missing_real_visuals(self):
        frames = [
            {"heading": "1952", "text": "بدأت القصة"},
            {"heading": "1953", "text": "تغير الاسم"},
            {"heading": "1954", "text": "صدر النقد"},
            {"heading": "1955", "text": "مرحلة جديدة"},
            {"heading": "صورة", "text": "لها صورة"},
            {"heading": "صورة", "text": "لها صورة"},
        ]
        photos = [None, None, None, None, "5.jpg", "6.jpg"]

        self.assertEqual(sb._missing_visual_indices(frames, photos), [1, 2, 3, 4])

    def test_visual_accounting_distinguishes_real_visuals_from_typography(self):
        frames = [{"heading": str(i), "text": str(i)} for i in range(1, 7)]
        photos = [None, "2.jpg", None, "4.jpg", "5.jpg", None]

        report = sb._visual_accounting(frames, photos)

        self.assertEqual(report["real_visual_frames"], [2, 4, 5])
        self.assertEqual(report["missing_visual_frames"], [1, 3, 6])
        self.assertEqual(report["real_visual_count"], 3)
        self.assertEqual(report["missing_visual_count"], 3)


if __name__ == "__main__":
    unittest.main()
