import unittest
from pathlib import Path

import yaml


class ModelUsageWorkflowTests(unittest.TestCase):
    def workflow(self, name):
        return Path(f".github/workflows/{name}.yml").read_text(encoding="utf-8")

    def run_env(self, name, command):
        parsed = yaml.load(self.workflow(name), Loader=yaml.BaseLoader)
        jobs = parsed["jobs"].values()
        return next(
            step["env"]
            for job in jobs
            for step in job["steps"]
            if step.get("run") == command
        )

    def test_primary_bot_workflows_publish_usage_summaries_and_artifacts(self):
        for name in ("daily", "topic", "breaking"):
            with self.subTest(workflow=name):
                text = self.workflow(name)
                self.assertIn('MODEL_USAGE_PATH: "out/model_usage.jsonl"', text)
                self.assertIn("python model_usage.py summarize", text)
                self.assertIn("out/model_usage.jsonl", text)

    def test_story_workflow_prices_editorial_usage_and_reports_it(self):
        text = self.workflow("story")
        env = self.run_env("story", "python guarded_story_publish.py")
        self.assertEqual(env["STORY_MODEL"], "claude-sonnet-5")
        self.assertEqual(env["STORY_MODEL_INPUT_USD_PER_M"], "2")
        self.assertEqual(env["STORY_MODEL_OUTPUT_USD_PER_M"], "10")
        self.assertEqual(env["MODEL_MAX_USD_PER_RUN"], "1.00")
        self.assertEqual(env["STORY_MAX_PAID_RESPONSES"], "1")
        self.assertEqual(env["STORY_AUX_MAX_PAID_RESPONSES"], "24")
        self.assertIn("python story_cost_report.py --last 1", text)
        self.assertIn("state/model_usage.jsonl", text)

    def test_batch_review_has_a_three_story_hard_maximum(self):
        env = self.run_env("batch-review", "python batch_review.py")
        self.assertEqual(env["BATCH_STORIES"], "${{ inputs.batch_stories || '3' }}")
        self.assertEqual(env["STORY_MODEL"], "claude-sonnet-5")
        self.assertEqual(env["MODEL_MAX_USD_PER_RUN"], "2")
        self.assertEqual(env["STORY_MAX_PAID_RESPONSES"], "3")
        self.assertEqual(env["VISION_MAX_PAID_RESPONSES"], "24")

    def test_normal_workflows_have_tight_per_run_cost_guards(self):
        expected = {
            "daily": ("python daily_news_fresh_runner.py", "0.50", "2", "20"),
            "topic": ("python topic_snapchat.py", "1.50", "2", "20"),
            "breaking": ("python breaking_watch_entry.py", "0.60", "2", "12"),
        }
        for name, (command, dollars, editorial_calls, vision_calls) in expected.items():
            with self.subTest(workflow=name):
                env = self.run_env(name, command)
                self.assertEqual(env["MODEL_MAX_USD_PER_RUN"], dollars)
                editorial_key = "TOPIC_MAX_PAID_RESPONSES" if name == "topic" else "NEWS_MAX_PAID_RESPONSES"
                self.assertEqual(env[editorial_key], editorial_calls)
                self.assertEqual(env["VISION_MAX_PAID_RESPONSES"], vision_calls)

    def test_routine_selection_and_breaking_classification_use_haiku(self):
        topic = self.run_env("topic", "python topic_snapchat.py")
        breaking = self.run_env("breaking", "python breaking_watch_entry.py")
        self.assertEqual(topic["SELECT_MODEL"], "claude-haiku-4-5-20251001")
        self.assertEqual(
            breaking["WATCH_MODEL"],
            "${{ vars.WATCH_MODEL || 'claude-haiku-4-5-20251001' }}",
        )

    def test_final_arabic_editorial_defaults_to_sonnet(self):
        daily = self.run_env("daily", "python daily_news_fresh_runner.py")
        topic = self.run_env("topic", "python topic_snapchat.py")
        self.assertEqual(daily["CLAUDE_MODEL"], "${{ vars.NEWS_MODEL || 'claude-sonnet-5' }}")
        self.assertEqual(topic["CLAUDE_MODEL"], "${{ vars.TOPIC_MODEL || 'claude-sonnet-5' }}")


if __name__ == "__main__":
    unittest.main()
