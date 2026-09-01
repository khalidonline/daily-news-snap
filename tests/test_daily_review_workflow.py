import unittest
from pathlib import Path


class DailyReviewWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

    def test_runs_every_two_hours_from_710am_through_1110pm_ksa(self):
        self.assertIn('- cron: "10 4-20/2 * * *"', self.workflow)
        self.assertNotIn('- cron: "0 4-20/2 * * *"', self.workflow)

    def test_stale_scheduled_runs_are_skipped_before_paid_work(self):
        self.assertIn('name: Guard scheduled freshness', self.workflow)
        self.assertIn('RUN_DAILY=0', self.workflow)
        self.assertIn('RUN_DAILY=1', self.workflow)
        self.assertIn('github.event_name == \'workflow_dispatch\'', self.workflow)
        self.assertIn('if: ${{ env.RUN_DAILY != \'0\' }}', self.workflow)
        self.assertIn('MAX_SCHEDULE_DELAY_MINUTES: "45"', self.workflow)

    def test_scheduled_runs_never_post_to_snapchat(self):
        expected = (
            "POST_TO_SNAPCHAT: ${{ (github.event_name == 'workflow_dispatch' && inputs.post) "
            "&& '1' || '0' }}"
        )
        self.assertIn(expected, self.workflow)
        post_line = next(
            line for line in self.workflow.splitlines()
            if line.strip().startswith("POST_TO_SNAPCHAT:")
        )
        self.assertNotIn("schedule", post_line)

    def test_scheduled_review_mode_keeps_telegram_and_dedupe(self):
        self.assertIn("TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}", self.workflow)
        self.assertIn("TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}", self.workflow)
        self.assertIn("DRY_RUN: ${{ inputs.dry_run && '1' || '' }}", self.workflow)
        self.assertIn('REMEMBER_DAYS: "3"', self.workflow)
        self.assertIn('LOOKBACK_HOURS: "48"', self.workflow)
        self.assertIn("run: python daily_news_runner.py", self.workflow)

    def test_manual_post_remains_explicit_opt_in(self):
        self.assertIn("post:", self.workflow)
        self.assertIn("default: false", self.workflow)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.post", self.workflow)


if __name__ == "__main__":
    unittest.main()
