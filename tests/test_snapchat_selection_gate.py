import unittest

import daily_news_runner


class SnapchatSelectionGateTests(unittest.TestCase):
    def test_rejects_story_with_fewer_than_two_strong_signals(self):
        result = {"stories": [{
            "headline": "خبر صحيح لكنه عادي",
            "snap_score": 8,
            "snap_signals": ["visual_strength"],
        }]}

        filtered = daily_news_runner.enforce_snapchat_selection_gate(result)

        self.assertEqual(filtered["stories"], [])

    def test_rejects_story_below_minimum_snap_score(self):
        result = {"stories": [{
            "headline": "خبر ضعيف",
            "snap_score": 5,
            "snap_signals": ["saudi_relevance", "practical_impact"],
        }]}

        filtered = daily_news_runner.enforce_snapchat_selection_gate(result)

        self.assertEqual(filtered["stories"], [])

    def test_keeps_story_with_score_six_and_two_recognized_signals(self):
        story = {
            "headline": "قرار تمويل سعودي يمس آلاف الأسر",
            "snap_score": 6,
            "snap_signals": ["saudi_relevance", "practical_impact"],
        }

        filtered = daily_news_runner.enforce_snapchat_selection_gate({"stories": [story]})

        self.assertEqual(filtered["stories"], [story])

    def test_missing_or_invalid_evidence_fails_closed(self):
        result = {"stories": [
            {"headline": "بلا تقييم"},
            {
                "headline": "إشارات مكررة",
                "snap_score": 9,
                "snap_signals": ["surprise", "surprise", "unknown"],
            },
            {
                "headline": "درجة خارج النطاق",
                "snap_score": 99,
                "snap_signals": ["surprise", "shareability"],
            },
        ]}

        filtered = daily_news_runner.enforce_snapchat_selection_gate(result)

        self.assertEqual(filtered["stories"], [])


if __name__ == "__main__":
    unittest.main()
