import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from daily_budget import BudgetBlocked, Ledger
from publishing_v2.autopilot.agents import Agents
from publishing_v2.autopilot import report


class Store:
    row = None
    def read(self, day): return 'v1', copy.deepcopy(self.row)
    def write(self, day, version, row): self.row = copy.deepcopy(row); return True


class BudgetPolicyTests(unittest.TestCase):
    def test_opus_visual_review_fits_cap_with_conservative_reservation(self):
        store = Store()
        ledger = Ledger(store, now=lambda: datetime(2026, 9, 20, tzinfo=timezone.utc))
        def transport(method, url, headers, payload):
            reserved = sum(e['charged_micro_usd'] for e in store.row['entries'].values())
            self.assertGreater(reserved, 8 * 4784 * 5 + 16384 * 25)
            self.assertLess(reserved, 3_000_000)
            self.assertEqual(len(payload['messages'][0]['content']), 9)
            self.assertEqual(payload['output_config']['effort'], 'high')
            return {'status_code': 200, 'body': {'id': 'r', 'stop_reason': 'end_turn',
                'usage': {'input_tokens': 45000, 'output_tokens': 1000},
                'content': [{'type': 'text', 'text': '{}'}]}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'frame.jpg'
            Image.new('RGB', (1080, 1920)).save(path)
            agent = Agents(env={'ANTHROPIC_API_KEY': 'test', 'AUTOPILOT_REVIEWER_MODEL': 'claude-opus-5'}, ledger=ledger, transport=transport)
            agent.run('reviewer', {'evidence': 'x' * 80000}, images=[path] * 8)
        self.assertTrue(all(e['status'] == 'settled' for e in store.row['entries'].values()))

    def test_review_still_blocked_by_previous_spend_and_unknown_reservations(self):
        store = Store()
        ledger = Ledger(store, now=lambda: datetime(2026, 9, 20, tzinfo=timezone.utc))
        ledger.reserve(2_900_000, 'earlier-attempt')
        def forbidden(*args): self.fail('Paid call escaped daily cap')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'frame.jpg'; Image.new('RGB', (1080, 1920)).save(path)
            agent = Agents(env={'ANTHROPIC_API_KEY': 'test', 'AUTOPILOT_REVIEWER_MODEL': 'claude-opus-5'}, ledger=ledger, transport=forbidden)
            with self.assertRaises(BudgetBlocked): agent.run('reviewer', {}, images=[path])
        self.assertEqual(len(store.row['entries']), 1)

    def test_budget_hold_report_requests_approval_without_automatic_increase(self):
        summary = {'mode': 'shadow', 'results': [{'lane': 'daily', 'status': 'held',
            'cost_micro_usd': 1200000, 'reason': 'BudgetBlocked',
            'budget_diagnostic': {'code': 'insufficient_remaining', 'limit_micro_usd': 5000000}}]}
        sent = []
        def request(url, headers, method, data):
            sent.append(json.loads(data)['text'])
            return {'ok': True, 'result': {'message_id': 1, 'chat': {'id': 123}}}
        with patch.dict('os.environ', {'TELEGRAM_TOKEN': 'test', 'TELEGRAM_CHAT_ID': '123', 'GITHUB_RUN_ID': '42'}), patch.object(report.Path, 'exists', return_value=True), patch.object(report.Path, 'read_text', return_value=json.dumps(summary)), patch.object(report, 'GitHubJournal') as journal, patch.object(report, 'request', side_effect=request):
            journal.return_value.read.return_value = {}
            self.assertEqual(report.main(), 0)
        self.assertIn('$5 shared budget', sent[0])
        self.assertNotIn('$3/day', sent[0])
        self.assertIn('approval', sent[0])
        self.assertIn('BudgetBlocked', sent[0])
