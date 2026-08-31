import unittest
from pathlib import Path


WORKFLOW = Path(".github/workflows/three-story-cost-pilot.yml")


class ThreeStoryCostPilotSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_is_manual_visual_only_and_cannot_publish(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("schedule:", self.text)
        self.assertIn('STORY_OPERATION_MODE: "visual_only"', self.text)
        self.assertIn('POST_TO_SNAPCHAT: "0"', self.text)
        self.assertIn('DRY_RUN: "1"', self.text)

    def test_uses_current_repair_branch_and_can_persist_guarded_state(self):
        self.assertIn("contents: write", self.text)
        self.assertIn("ref: repair/all-story-visuals-2026-08-29", self.text)
        self.assertNotIn("ref: optimize/all-stories-publication-ready", self.text)

    def test_repairs_only_riyadh_and_sama(self):
        self.assertEqual(2, self.text.count('STORY="'))
        self.assertIn("قصة الرياض: من بلدة مسورة إلى عاصمة اقتصادية", self.text)
        self.assertIn("قصة تأسيس مؤسسة النقد ساما", self.text)
        self.assertNotIn("Madam C. J. Walker", self.text)

    def test_cost_report_is_scoped_to_this_run(self):
        self.assertIn('STORY_COST_STATE_ROOT: "pilot-cost-state"', self.text)
        self.assertIn('usage_path=Path("pilot-cost-state/model_usage.jsonl")', self.text)

    def test_story_failures_make_the_job_fail_after_artifact_upload(self):
        self.assertIn("id: riyadh", self.text)
        self.assertIn("id: sama", self.text)
        self.assertIn("steps.riyadh.outcome", self.text)
        self.assertIn("steps.sama.outcome", self.text)
        upload = self.text.index("uses: actions/upload-artifact@v4")
        verdict = self.text.index("name: Enforce pilot result")
        self.assertLess(upload, verdict)


if __name__ == "__main__":
    unittest.main()
