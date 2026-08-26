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

    def test_zero_progress_scans_later_unresolved_stories_before_failing(self):
        text = Path('.github/workflows/bulk-visual-repair.yml').read_text(encoding='utf-8')
        repair = text.split('  repair:', 1)[1]
        self.assertIn('if [ "$rc" -eq 2 ]; then', repair)
        self.assertIn('repair_backlog(build_board())', repair)
        self.assertIn('--story "$story"', repair)
        self.assertIn('scan_rc=10', repair)
        self.assertIn('if [ "$scan_rc" -eq 10 ]; then rc=10; fi', repair)
        self.assertIn('if [ "$scan_rc" -eq 3 ]; then exit 3; fi', repair)


if __name__ == '__main__':
    unittest.main()
