import unittest
from pathlib import Path

import yaml


PAID_WORKFLOWS = ("daily.yml", "topic.yml", "story.yml", "breaking.yml")


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


if __name__ == "__main__":
    unittest.main()
