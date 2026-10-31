import unittest
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import yaml


class ExternalAutopilotTriggerTests(unittest.TestCase):
    def test_autopilot_uses_external_push_trigger_not_github_schedule(self):
        text = Path('.github/workflows/publishing-v2-autopilot.yml').read_text(encoding='utf-8')
        self.assertIn("push:\n    branches: [main]\n    paths:\n      - 'autopilot-trigger.txt'", text)
        self.assertNotIn('\n  schedule:\n', text)
        self.assertIn('workflow_dispatch:', text)
        steps = yaml.safe_load(text)['jobs']['packages']['steps']
        route = next(step for step in steps if step.get('id') == 'route')
        runner = next(step for step in steps if step.get('name') == 'Run coordinated editorial agents')
        report = next(step for step in steps if step.get('name') == 'Send publication outcome')
        self.assertEqual(report['env']['AUTOPILOT_REQUESTED_MODE'], '${{ steps.route.outputs.mode }}')
        self.assertEqual(runner['env']['AUTOPILOT_MODE'], '${{ steps.route.outputs.mode }}')
        self.assertEqual(runner['env']['AUTOPILOT_LANE'], '${{ steps.route.outputs.lane }}')
        lines = route['run'].strip().splitlines()
        self.assertEqual(lines[0], "python - <<'PY'")
        self.assertEqual(lines[-1], 'PY')
        script = '\n'.join(lines[1:-1])
        cases = [
            ({'GITHUB_EVENT_NAME': 'push', 'INPUT_MODE': 'live', 'INPUT_LANE': 'local'},
             {'mode': 'shadow', 'lane': 'daily'}),
            ({'GITHUB_EVENT_NAME': 'workflow_dispatch'}, {'mode': 'shadow', 'lane': 'daily'}),
            ({'GITHUB_EVENT_NAME': 'workflow_dispatch', 'INPUT_MODE': 'shadow', 'INPUT_LANE': 'local'},
             {'mode': 'shadow', 'lane': 'local'}),
            ({'GITHUB_EVENT_NAME': 'workflow_dispatch', 'INPUT_MODE': 'invalid'}, None),
            ({'GITHUB_EVENT_NAME': 'workflow_dispatch', 'INPUT_LANE': 'both'}, None),
        ]
        for env, expected in cases:
            with self.subTest(env=env), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / 'outputs'
                result = subprocess.run([sys.executable, '-c', script],
                    env={**env, 'GITHUB_OUTPUT': str(output)}, capture_output=True, text=True)
                if expected is None:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('single_lane_required', result.stderr)
                    self.assertFalse(output.exists())
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), expected)
                    self.assertEqual(output.read_text(),
                        f"mode={expected['mode']}\nlane={expected['lane']}\n")

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
