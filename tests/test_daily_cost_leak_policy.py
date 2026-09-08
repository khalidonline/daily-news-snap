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

    def test_explicit_story_recovery_can_bootstrap_visual_validation(self):
        story_workflow = Path(".github/workflows/story.yml").read_text(encoding="utf-8")
        receiver = Path(".github/workflows/external-clock-receiver.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("story-recovery", story_workflow)
        self.assertIn("RECOVERY_STORY_B64", story_workflow)
        self.assertIn("STORY_RECOVERY_STORY", story_workflow)
        self.assertIn("github.event.action == 'story-recovery'", story_workflow)
        self.assertIn("github.event.action == 'story-recovery' && 'regenerate_editorial'", story_workflow)
        self.assertIn("github.event.action == 'story-recovery' && github.run_id", story_workflow)
        self.assertIn("MAX_TOKENS: ${{ github.event.action == 'story-recovery' && '32000'", story_workflow)
        self.assertIn('if [ "$bot" = "story" ]', receiver)
        self.assertIn('[[ "$trigger_value" == recovery_story=* ]]', receiver)
        self.assertIn('-f event_type="story-recovery"', receiver)


if __name__ == "__main__":
    unittest.main()
