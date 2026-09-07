import unittest
from pathlib import Path


class DailyCostLeakPolicyTests(unittest.TestCase):
    def test_news_bounds_vision_spend_and_still_renders_without_a_photo(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")
        self.assertIn('REQUIRE_PHOTO: "0"', workflow)
        self.assertIn('VISION_MAX_PAID_RESPONSES: "12"', workflow)
        self.assertNotIn('VISION_MAX_PAID_RESPONSES: "35"', workflow)

    def test_scheduled_story_is_identified_as_cost_safe_automatic_work(self):
        workflow = Path(".github/workflows/story.yml").read_text(encoding="utf-8")
        self.assertIn("STORY_SELECTION_MODE:", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)


if __name__ == "__main__":
    unittest.main()
