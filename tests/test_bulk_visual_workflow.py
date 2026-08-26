import unittest
from pathlib import Path


class BulkVisualWorkflowTests(unittest.TestCase):
    def test_pull_requests_cannot_receive_repair_secret_or_write_permission(self):
        text = Path('.github/workflows/bulk-visual-repair.yml').read_text(encoding='utf-8')
        self.assertIn('permissions:\n  contents: read', text)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", text)
        self.assertIn('permissions:\n      contents: write', text)
        repair = text.split('  repair:', 1)[1]
        self.assertNotIn("github.event_name == 'pull_request'", repair)
        self.assertIn('ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}', repair)

    def test_pull_request_job_runs_tests_without_secret(self):
        text = Path('.github/workflows/bulk-visual-repair.yml').read_text(encoding='utf-8')
        tests = text.split('  tests:', 1)[1].split('  repair:', 1)[0]
        self.assertIn("if: github.event_name == 'pull_request'", tests)
        self.assertNotIn('secrets.', tests)
        self.assertNotIn('git push', tests)

    def test_repair_job_has_thirty_minute_hard_timeout(self):
        text = Path('.github/workflows/bulk-visual-repair.yml').read_text(encoding='utf-8')
        self.assertIn('timeout-minutes: 30', text)

    def test_repair_jobs_are_serialized_without_cancelling_active_run(self):
        text = Path('.github/workflows/bulk-visual-repair.yml').read_text(encoding='utf-8')
        repair = text.split('  repair:', 1)[1]
        self.assertIn('concurrency:', repair)
        self.assertIn('cancel-in-progress: false', repair)

    def test_workflow_calls_bounded_controller_once_and_has_no_full_backlog_probe_loop(self):
        text = Path('.github/workflows/bulk-visual-repair.yml').read_text(encoding='utf-8')
        self.assertEqual(text.count('python tools/bulk_visual_run.py'), 1)
        self.assertNotIn('for story in "${later_stories[@]}"', text)
        self.assertNotIn('for batch in $(seq', text)

    def test_workflow_maps_two_ten_and_zero_to_success_but_three_to_failure(self):
        text = Path('.github/workflows/bulk-visual-repair.yml').read_text(encoding='utf-8')
        self.assertIn('if [ "$rc" -eq 3 ]; then exit 3; fi', text)
        self.assertIn('if [ "$rc" -eq 0 ] || [ "$rc" -eq 2 ] || [ "$rc" -eq 10 ]; then exit 0; fi', text)

    def test_workflow_clamps_dispatch_story_count_to_twelve(self):
        text = Path('.github/workflows/bulk-visual-repair.yml').read_text(encoding='utf-8')
        self.assertIn('MAX_STORIES=12', text)
        self.assertIn('BATCH_STORIES', text)

    def test_summary_reports_bounded_controller_outcome(self):
        text = Path('.github/workflows/bulk-visual-repair.yml').read_text(encoding='utf-8')
        self.assertIn('run-summary.json', text)
        self.assertIn('Bounded run outcome:', text)


if __name__ == '__main__':
    unittest.main()
