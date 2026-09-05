import unittest
from pathlib import Path

import yaml


PAID_WORKFLOWS = ("daily.yml", "topic.yml", "story.yml", "breaking.yml")
CLOCK_DISPATCHES = {
    "news": "news-schedule",
    "topic": "topic-schedule",
    "story": "story-schedule",
    "breaking": "breaking-recovery",
}


class PaidWorkflowPolicyTests(unittest.TestCase):
    def load_workflow(self, filename):
        path = Path(".github/workflows") / filename
        return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    def test_paid_workflows_cannot_run_from_repository_pushes(self):
        for filename in PAID_WORKFLOWS:
            with self.subTest(workflow=filename):
                triggers = self.load_workflow(filename)["on"]
                self.assertNotIn("push", triggers)

    def test_paid_workflows_keep_scheduled_and_manual_entry_points(self):
        for filename in PAID_WORKFLOWS:
            with self.subTest(workflow=filename):
                triggers = self.load_workflow(filename)["on"]
                self.assertIn("schedule", triggers)
                self.assertIn("workflow_dispatch", triggers)

    def test_news_recovery_is_an_explicit_input_not_a_commit_side_effect(self):
        triggers = self.load_workflow("daily.yml")["on"]
        inputs = triggers["workflow_dispatch"]["inputs"]
        dispatch_types = triggers["repository_dispatch"]["types"]
        self.assertIn("recovery_story", inputs)
        self.assertIn("news-recovery", dispatch_types)

    def test_breaking_recovery_uses_repository_dispatch(self):
        triggers = self.load_workflow("breaking.yml")["on"]
        self.assertIn("breaking-recovery", triggers["repository_dispatch"]["types"])

    def test_external_clock_receiver_is_path_scoped(self):
        receiver = self.load_workflow("external-clock-receiver.yml")
        triggers = receiver["on"]["push"]
        self.assertEqual(triggers["branches"], ["main"])
        self.assertEqual(
            set(triggers["paths"]),
            {f"scheduler/triggers/{bot}.txt" for bot in CLOCK_DISPATCHES},
        )

    def test_external_clock_receiver_dispatches_each_bot_without_model_calls(self):
        receiver_path = Path(".github/workflows/external-clock-receiver.yml")
        text = receiver_path.read_text(encoding="utf-8")
        for bot, event_type in CLOCK_DISPATCHES.items():
            with self.subTest(bot=bot):
                self.assertIn(f"{bot}:{event_type}", text)
        self.assertNotIn("ANTHROPIC_API_KEY", text)
        self.assertNotIn("python daily_news", text)
        self.assertNotIn("python story", text)
        self.assertNotIn("python topic", text)
        self.assertNotIn("python breaking", text)


if __name__ == "__main__":
    unittest.main()
