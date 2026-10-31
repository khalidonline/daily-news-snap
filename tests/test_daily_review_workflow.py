import unittest
import os
from pathlib import Path
import subprocess
import sys


class DailyReviewWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.news_runner = Path("daily_news_fresh_runner.py").read_text(encoding="utf-8")
        cls.breaking_runner = Path("breaking_news_runner.py").read_text(encoding="utf-8")

    def test_news_runner_defaults_to_standard_light_card_without_workflow_theme(self):
        env = os.environ.copy()
        env.pop("THEME", None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import daily_news_fresh_runner; "
                    "news_bot = daily_news_fresh_runner.load_news_bot(); "
                    "print(news_bot.THEME); "
                    "print(news_bot.BG_TOP)"
                ),
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stdout.splitlines(), ["light", "(238, 232, 227)"])

    def test_importing_news_runner_does_not_mutate_theme_environment(self):
        env = os.environ.copy()
        env.pop("THEME", None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import daily_news_fresh_runner, os; print('THEME' in os.environ)",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), "False")

    def test_news_runner_respects_explicit_theme_override(self):
        env = os.environ.copy()
        env["THEME"] = "dark"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import daily_news_fresh_runner; "
                    "news_bot = daily_news_fresh_runner.load_news_bot(); "
                    "print(news_bot.THEME); "
                    "print(news_bot.BG_TOP)"
                ),
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stdout.splitlines(), ["dark", "(14, 17, 26)"])

    def test_no_photo_notification_calls_news_items_not_stories(self):
        self.assertIn("install_news_notification_labels", self.news_runner)
        self.assertIn('"news items had a usable photo"', self.news_runner)
        self.assertIn('"model returned no news items"', self.news_runner)
        self.assertIn("install_news_notification_labels(news_bot)", self.news_runner)

    def test_financial_news_explains_what_the_news_means(self):
        required = "في الأخبار المالية، اجعل takeaway يشرح ببساطة ماذا يعني الخبر"
        for runner in (self.news_runner, self.breaking_runner):
            self.assertIn(required, runner)
            self.assertIn("صكوك", runner)
            self.assertIn("اكتتاب", runner)
            self.assertIn("تمويل", runner)
        self.assertIn("install_financial_takeaway_guidance(news_bot)", self.news_runner)
        self.assertIn("install_financial_takeaway_guidance(bot)", self.breaking_runner)

    def test_retired_daily_workflow_remains_inactive(self):
        self.assertFalse(Path(".github/workflows/daily.yml").exists())


if __name__ == "__main__":
    unittest.main()
