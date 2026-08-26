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


if __name__ == '__main__':
    unittest.main()
