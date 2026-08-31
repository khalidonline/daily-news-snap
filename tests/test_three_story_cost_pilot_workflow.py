import unittest
from pathlib import Path


WORKFLOW = Path(".github/workflows/three-story-cost-pilot.yml")


class ThreeStoryCostPilotWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_is_manual_only_and_targets_the_optimization_branch(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("schedule:", self.text)
        self.assertIn("ref: optimize/all-stories-publication-ready", self.text)

    def test_runs_exactly_three_named_stories_sequentially(self):
        self.assertEqual(3, self.text.count('STORY="'))
        self.assertIn("قصة الرياض: من بلدة مسورة إلى عاصمة اقتصادية", self.text)
        self.assertIn("قصة تأسيس مؤسسة النقد ساما", self.text)
        self.assertIn("من هي Madam C. J. Walker؟ أول مليونيرة عصامية في أمريكا", self.text)
        self.assertNotIn("matrix:", self.text)

    def test_uses_guarded_auto_mode_with_publication_disabled(self):
        self.assertIn('STORY_OPERATION_MODE: "auto"', self.text)
        self.assertIn('POST_TO_SNAPCHAT: "0"', self.text)
        self.assertIn('DRY_RUN: "1"', self.text)
        self.assertEqual(3, self.text.count("python guarded_story_publish.py"))

    def test_keeps_frames_and_cost_report_even_after_failure(self):
        self.assertIn("if: always()", self.text)
        self.assertIn("pilot-artifacts/", self.text)
        self.assertIn("story-cost-report.json", self.text)
        self.assertIn("if-no-files-found: warn", self.text)
        self.assertEqual(3, self.text.count("status=$?"))
        self.assertEqual(3, self.text.count('exit "$status"'))
        self.assertEqual(2, self.text.count("find out -mindepth 1 -maxdepth 1 -type f -delete"))


if __name__ == "__main__":
    unittest.main()
