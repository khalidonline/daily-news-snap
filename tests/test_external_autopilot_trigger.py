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
        # Verify the actual provider payload and shared reservation, not an
        # obsolete source-code literal. HTTP is the only replaced boundary.
        from unittest.mock import patch
        import recover_held_reviewer as recovery
        from daily_budget import Ledger, BudgetBlocked
        from tests.test_daily_budget import MemoryStore
        store = MemoryStore()
        ledger = Ledger(store)
        ledger.context = {'package_id': 'offline-review', 'stage': 'reviewer'}
        calls = []
        def response(transport, method, url, headers, payload):
            calls.append(payload)
            entries = [e for _, row in store.rows.values() for e in row['entries'].values()]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]['status'], 'reserved')
            self.assertGreaterEqual(entries[0]['charged_micro_usd'], 48000)
            self.assertEqual(payload['max_tokens'], 4800)
            return 200, {'id': 'offline', 'stop_reason': 'end_turn',
                         'usage': {'input_tokens': 1, 'output_tokens': 1},
                         'content': [{'type': 'text', 'text': '{}'}]}
        with patch.object(recovery.providers, '_request', side_effect=response):
            result, receipt = recovery.review_once({}, [], env={'ANTHROPIC_API_KEY': 'offline'}, ledger=ledger)
        self.assertEqual(result, {})
        self.assertEqual(len(calls), 1)
        self.assertEqual(receipt['recovery_max_tokens'], 4800)
        # An exhausted real ledger must stop before the transport boundary.
        blocked = Ledger(MemoryStore())
        blocked.reserve(3000000, 'offline-used')
        blocked.context = ledger.context
        with patch.object(recovery.providers, '_request', side_effect=AssertionError('provider contacted')):
            with self.assertRaises(BudgetBlocked):
                recovery.review_once({}, [], env={'ANTHROPIC_API_KEY': 'offline'}, ledger=blocked)
        self.assertIn('slot_not_unstarted_budget_blocked_review', script)
        self.assertIn('review-recovery-trigger.txt', workflow)
        self.assertNotIn('BUNDLE_API_KEY', workflow)
        self.assertNotIn('POST_TO_SNAPCHAT', workflow)


if __name__ == '__main__':
    unittest.main()
