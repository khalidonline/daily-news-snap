import unittest
from pathlib import Path


WORKFLOW = Path('.github/workflows/story.yml')


class StoryOperationModeWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding='utf-8')

    def test_workflow_exposes_explicit_operation_modes(self):
        self.assertIn('operation_mode:', self.text)
        self.assertIn('default: auto', self.text)
        self.assertIn('- auto', self.text)
        self.assertIn('- visual_only', self.text)
        self.assertIn('- regenerate_editorial', self.text)

    def test_runtime_receives_mode_and_explicit_regeneration_nonce(self):
        self.assertIn('STORY_OPERATION_MODE:', self.text)
        self.assertIn("inputs.operation_mode || 'auto'", self.text)
        self.assertIn('STORY_REGENERATION_NONCE:', self.text)
        self.assertIn("inputs.operation_mode == 'regenerate_editorial'", self.text)
        self.assertIn('github.run_id', self.text)

    def test_workflow_exposes_targeted_visual_repair_frames(self):
        self.assertIn('repair_frames:', self.text)
        self.assertIn('STORY_REPAIR_FRAMES:', self.text)
        self.assertIn("inputs.repair_frames || ''", self.text)

    def test_rerun_attempt_never_implies_regeneration(self):
        self.assertNotIn('github.run_attempt > 1', self.text)
        self.assertNotIn('github.run_attempt != 1', self.text)
        self.assertNotIn('STORY_OPERATION_MODE: "regenerate_editorial"', self.text)

    def test_snapchat_publish_expression_is_preserved(self):
        expected = "POST_TO_SNAPCHAT: ${{ (github.event_name == 'schedule' || (github.event_name == 'workflow_dispatch' && inputs.post)) && '1' || '0' }}"
        self.assertIn(expected, self.text)


if __name__ == '__main__':
    unittest.main()
