import unittest
from pathlib import Path


class ModelUsageWorkflowTests(unittest.TestCase):
    def workflow(self, name):
        return Path(f".github/workflows/{name}.yml").read_text(encoding="utf-8")

    def test_primary_bot_workflows_publish_usage_summaries_and_artifacts(self):
        for name in ("daily", "topic", "breaking"):
            with self.subTest(workflow=name):
                text = self.workflow(name)
                self.assertIn('MODEL_USAGE_PATH: "out/model_usage.jsonl"', text)
                self.assertIn("python model_usage.py summarize", text)
                self.assertIn("out/model_usage.jsonl", text)

    def test_story_workflow_prices_editorial_usage_and_reports_it(self):
        text = self.workflow("story")
        self.assertIn('STORY_MODEL_INPUT_USD_PER_M: "5"', text)
        self.assertIn('STORY_MODEL_OUTPUT_USD_PER_M: "25"', text)
        self.assertIn("python story_cost_report.py --last 1", text)
        self.assertIn("state/model_usage.jsonl", text)

    def test_batch_review_has_a_three_story_hard_maximum(self):
        text = self.workflow("batch-review")
        self.assertIn('BATCH_STORIES: ${{ inputs.batch_stories || \'3\' }}', text)
        self.assertIn('STORY_MAX_PAID_RESPONSES: "3"', text)
        self.assertNotIn('STORY_MAX_PAID_RESPONSES: "4"', text)


if __name__ == "__main__":
    unittest.main()
