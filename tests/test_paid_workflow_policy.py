import unittest
from pathlib import Path


class PaidWorkflowPolicyTests(unittest.TestCase):
    def test_breaking_workflow_is_removed(self):
        self.assertFalse(Path(".github/workflows/breaking.yml").exists())

    def test_breaking_test_workflow_is_removed(self):
        self.assertFalse(Path(".github/workflows/breaking-watch-tests.yml").exists())

    def test_retired_external_clock_remains_inactive(self):
        self.assertFalse(Path(".github/workflows/external-clock-receiver.yml").exists())


if __name__ == "__main__":
    unittest.main()
