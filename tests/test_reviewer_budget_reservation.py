import unittest
from pathlib import Path


class ReviewerBudgetReservationTests(unittest.TestCase):
    def test_reviewer_output_ceiling_is_bounded(self):
        text = Path("publishing_v2/autopilot/agents.py").read_text(encoding="utf-8")
        self.assertIn("max_tokens': 8192 if role == 'reviewer'", text)

    def test_visual_reservation_uses_documented_image_token_bound(self):
        text = Path("publishing_v2/autopilot/agents.py").read_text(encoding="utf-8")
        self.assertIn("len(images) * 4784 * PRICES[model][0]", text)
        self.assertNotIn("len(images) * 8192 * PRICES[model][0]", text)


if __name__ == "__main__":
    unittest.main()
