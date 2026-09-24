import unittest
from pathlib import Path


class ExternalAutopilotTriggerTests(unittest.TestCase):
    def test_autopilot_uses_external_push_trigger_not_github_schedule(self):
        text = Path(".github/workflows/publishing-v2-autopilot.yml").read_text(encoding="utf-8")
        self.assertIn("push:\n    branches: [main]\n    paths:\n      - 'autopilot-trigger.txt'", text)
        self.assertNotIn("\n  schedule:\n", text)
        self.assertIn("workflow_dispatch:", text)


if __name__ == "__main__":
    unittest.main()
