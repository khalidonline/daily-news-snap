from pathlib import Path
import unittest


WORKFLOW = Path('.github/workflows/repair-all-story-visuals.yml')


class RepairAllStoryVisualsWorkflowTests(unittest.TestCase):
    def test_board_count_capture_suppresses_build_board_stdout(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('redirect_stdout', text)
        self.assertIn('io.StringIO()', text)
        self.assertIn("print(sum(r.status == 'PASS' for r in rows), len(rows))", text)


if __name__ == '__main__':
    unittest.main()
