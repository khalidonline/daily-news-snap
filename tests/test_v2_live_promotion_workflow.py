import unittest
from pathlib import Path


class LivePromotionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = Path('.github/workflows/publishing-v2-autopilot.yml').read_text(encoding='utf-8')

    def test_push_defaults_to_shadow_and_requires_explicit_promotion_message_for_live(self):
        self.assertIn('message.startswith("automation: promote daily autopilot live")', self.text)
        self.assertIn('mode = "live"', self.text)
        self.assertIn('mode = (os.environ.get("INPUT_MODE") or "shadow")', self.text)

    def test_duplicate_lane_candidate_promotes_daily_only(self):
        self.assertIn('if daily_id and daily_id == local_id:', self.text)
        self.assertIn('lane = "daily"', self.text)

    def test_runtime_uses_resolved_mode_and_lane(self):
        self.assertIn("AUTOPILOT_MODE: ${{ steps.route.outputs.mode }}", self.text)
        self.assertIn("AUTOPILOT_LANE: ${{ steps.route.outputs.lane }}", self.text)
        self.assertIn("POST_TO_SNAPCHAT: ${{ steps.route.outputs.mode == 'live' && '1' || '0' }}", self.text)
        self.assertIn("DRY_RUN: ${{ steps.route.outputs.mode == 'live' && '0' || '1' }}", self.text)


if __name__ == '__main__':
    unittest.main()
