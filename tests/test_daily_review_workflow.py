import unittest
from pathlib import Path


class DailyReviewWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

    def test_keeps_github_heartbeat_only_as_temporary_fallback(self):
        self.assertIn('- cron: "10,25,40,55 4-20 * * *"', self.workflow)
        self.assertIn("Temporary fallback only", self.workflow)
        self.assertIn("repository_dispatch:", self.workflow)
        self.assertIn("types: [news-schedule]", self.workflow)

    def test_shared_gate_controls_paid_work(self):
        self.assertIn("python3 shared_schedule_gate.py due", self.workflow)
        self.assertIn("--bot news", self.workflow)
        self.assertIn("github.event.client_payload.slot", self.workflow)
        self.assertIn("SCHEDULE_SLOT_ID", self.workflow)
        self.assertIn("if: ${{ env.RUN_SCHEDULED_BOT != '0' }}", self.workflow)

    def test_successful_slot_marks_durable_state(self):
        verify_index = self.workflow.index("Verify News card was produced")
        mark_index = self.workflow.index("Mark News slot complete")
        self.assertLess(verify_index, mark_index)
        self.assertIn("test -n \"$(find out -maxdepth 1 -name \'*.png\' -print -quit)\"", self.workflow)
        self.assertIn("python3 shared_schedule_gate.py mark", self.workflow)
        self.assertIn("daily_slot_state.json", self.workflow)
        self.assertIn("git pull --rebase origin main", self.workflow)
        self.assertIn("git push origin HEAD:main", self.workflow)

    def test_heartbeat_never_cancels_live_delivery(self):
        self.assertIn("cancel-in-progress: false", self.workflow)

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
        self.assertNotIn("repository_dispatch", post_line)
        self.assertNotIn("schedule", post_line)

    def test_scheduled_review_mode_keeps_telegram_and_dedupe(self):
        self.assertIn("TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}", self.workflow)
        self.assertIn("TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}", self.workflow)
        self.assertIn("DRY_RUN: ${{ inputs.dry_run && '1' || '' }}", self.workflow)
        self.assertIn('REMEMBER_DAYS: "3"', self.workflow)
        self.assertIn('LOOKBACK_HOURS: "48"', self.workflow)
        self.assertIn("run: python daily_news_fresh_runner.py", self.workflow)

    def test_manual_post_remains_explicit_opt_in(self):
        self.assertIn("post:", self.workflow)
        self.assertIn("default: false", self.workflow)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.post", self.workflow)


if __name__ == "__main__":
    unittest.main()
