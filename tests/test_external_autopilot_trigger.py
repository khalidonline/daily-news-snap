import unittest
from pathlib import Path


class ExternalAutopilotTriggerTests(unittest.TestCase):
    def test_autopilot_uses_external_push_trigger_not_github_schedule(self):
        text = Path('.github/workflows/publishing-v2-autopilot.yml').read_text(encoding='utf-8')
        self.assertIn("push:\n    branches: [main]\n    paths:\n      - 'autopilot-trigger.txt'", text)
        self.assertNotIn('\n  schedule:\n', text)
        self.assertIn('workflow_dispatch:', text)
        self.assertIn("AUTOPILOT_MODE: ${{ inputs.mode || 'shadow' }}", text)
        self.assertIn("AUTOPILOT_REQUESTED_MODE: ${{ inputs.mode || 'shadow' }}", text)

    def test_reviewer_recovery_is_bounded_and_cannot_publish(self):
        script = Path('recover_held_reviewer.py').read_text(encoding='utf-8')
        workflow = Path('.github/workflows/recover-held-reviewer.yml').read_text(encoding='utf-8')
        self.assertIn('REVIEWER_MAX_TOKENS = 4096', script)
        self.assertIn('slot_not_unstarted_budget_blocked_review', script)
        self.assertIn('review-recovery-trigger.txt', workflow)
        self.assertNotIn('BUNDLE_API_KEY', workflow)
        self.assertNotIn('POST_TO_SNAPCHAT', workflow)


if __name__ == '__main__':
    unittest.main()
