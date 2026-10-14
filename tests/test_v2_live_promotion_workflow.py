"""Execute the free workflow router, including malformed dispatch input."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


class LivePromotionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load(Path('.github/workflows/publishing-v2-autopilot.yml').read_text())
        step = next(s for s in self.workflow['jobs']['packages']['steps'] if s.get('id') == 'route')
        self.script = step['run'].split("python - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]

    def route(self, **env):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'route'
            result = subprocess.run(['python', '-c', self.script],
                env={**os.environ, 'GITHUB_OUTPUT': str(output), 'INPUT_MODE': '',
                     'INPUT_LANE': '', 'HEAD_COMMIT_MESSAGE': '', **env},
                capture_output=True, text=True)
            return result, output.read_text() if output.exists() else ''

    def test_push_defaults_to_single_shadow_even_if_dispatch_inputs_are_present(self):
        result, output = self.route(GITHUB_EVENT_NAME='push', INPUT_MODE='live', INPUT_LANE='local')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, 'mode=shadow\nlane=daily\n')

    def test_explicit_promotion_message_publishes_only_daily(self):
        result, output = self.route(GITHUB_EVENT_NAME='push', HEAD_COMMIT_MESSAGE='automation: promote daily autopilot live')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, 'mode=live\nlane=daily\n')

    def test_dispatch_can_choose_local_but_cannot_choose_both(self):
        result, output = self.route(GITHUB_EVENT_NAME='workflow_dispatch', INPUT_MODE='shadow', INPUT_LANE='local')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, 'mode=shadow\nlane=local\n')
        result, output = self.route(GITHUB_EVENT_NAME='workflow_dispatch', INPUT_MODE='shadow', INPUT_LANE='both')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output, '')
