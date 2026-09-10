import copy
import io
import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.request import Request

try:
    import daily_budget as budget
except ImportError:
    budget = None


class MemoryStore:
    def __init__(self):
        self.rows = {}
        self.lock = threading.Lock()

    def read(self, day):
        with self.lock:
            version, row = self.rows.get(day, (0, None))
            return version, copy.deepcopy(row)

    def write(self, day, version, row):
        with self.lock:
            if self.rows.get(day, (0, None))[0] != version:
                return False
            self.rows[day] = (version + 1, copy.deepcopy(row))
            return True


class DailyBudgetTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(budget, 'shared daily budget is missing')
        self.store = MemoryStore()
        self.now = datetime(2026, 9, 12, 10, tzinfo=timezone.utc)
        self.ledger = budget.Ledger(self.store, now=lambda: self.now)

    def test_all_bots_share_three_dollars(self):
        for bot in ['news', 'topic', 'story']:
            self.ledger.reserve(1_000_000, bot)
        with self.assertRaises(budget.BudgetBlocked):
            self.ledger.reserve(1, 'breaking')

    def test_concurrent_reservations_never_exceed_limit(self):
        def reserve(_):
            try:
                self.ledger.reserve(100_000, 'news')
                return 1
            except budget.BudgetBlocked:
                return 0
        with ThreadPoolExecutor(max_workers=12) as pool:
            accepted = sum(pool.map(reserve, range(60)))
        self.assertEqual(accepted, 30)

    def test_settlement_releases_only_unused_reservation(self):
        token = self.ledger.reserve(2_500_000, 'story')
        self.ledger.settle(token, 100_000)
        self.ledger.reserve(2_900_000, 'news')
        with self.assertRaises(budget.BudgetBlocked):
            self.ledger.reserve(1, 'topic')

    def test_unknown_failure_keeps_reservation_across_new_run(self):
        self.ledger.reserve(3_000_000, 'news')
        retry = budget.Ledger(self.store, now=lambda: self.now)
        with self.assertRaises(budget.BudgetBlocked):
            retry.reserve(1, 'news')

    def test_midnight_is_saudi_time_and_late_settlement_uses_original_day(self):
        self.now = datetime(2026, 9, 12, 20, 59, tzinfo=timezone.utc)
        old = self.ledger.reserve(3_000_000, 'story')
        self.now = datetime(2026, 9, 12, 21, 0, tzinfo=timezone.utc)
        self.ledger.reserve(3_000_000, 'news')
        self.ledger.settle(old, 1)
        with self.assertRaises(budget.BudgetBlocked):
            self.ledger.reserve(1, 'topic')

    def test_corrupt_ledger_is_not_treated_as_zero(self):
        self.store.rows['2026-09-12'] = (1, {'oops': True})
        with self.assertRaises(budget.BudgetBlocked):
            self.ledger.reserve(1, 'news')

    def test_reservation_cannot_be_negative_zero_or_over_limit(self):
        for amount in [-1, 0, 3_000_001]:
            with self.assertRaises(budget.BudgetBlocked):
                self.ledger.reserve(amount, 'news')

    def test_repeated_settlement_cannot_refund_twice(self):
        token = self.ledger.reserve(1_000_000, 'news')
        self.ledger.settle(token, 100_000)
        self.ledger.settle(token, 100_000)
        self.ledger.reserve(2_900_000, 'story')
        with self.assertRaises(budget.BudgetBlocked):
            self.ledger.reserve(1, 'topic')

    def test_unknown_models_and_paid_image_generation_are_blocked(self):
        with self.assertRaises(budget.BudgetBlocked):
            budget.prepare({'model': 'unknown', 'max_tokens': 100, 'messages': []})
        with patch.object(budget, '_transport') as transport:
            with self.assertRaises(budget.BudgetBlocked):
                budget.urlopen(Request('https://fal.run/model', data=b'{}'))
            transport.assert_not_called()

    def test_searches_have_finite_bound_and_output_is_reserved(self):
        payload, upper = budget.prepare({
            'model': 'claude-sonnet-5', 'max_tokens': 16000,
            'messages': [{'role': 'user', 'content': 'research'}],
            'tools': [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 6}],
        })
        self.assertEqual(payload['tools'][0]['max_uses'], 1)
        self.assertGreater(upper, 2_320_000)
        self.assertLess(upper, 3_000_000)

    def test_free_requests_do_not_need_ledger(self):
        with patch.object(budget, '_transport', return_value='free') as transport:
            self.assertEqual(budget.urlopen('https://example.com/photo.jpg'), 'free')
            transport.assert_called_once()

    def test_no_provider_request_when_daily_balance_insufficient(self):
        self.ledger.reserve(3_000_000, 'news')
        request = Request('https://api.anthropic.com/v1/messages', data=json.dumps({
            'model': 'claude-sonnet-5', 'max_tokens': 100, 'messages': []}).encode())
        with patch.object(budget, 'shared_ledger', return_value=self.ledger), patch.object(budget, '_transport') as transport:
            with self.assertRaises(budget.BudgetBlocked):
                budget.urlopen(request)
            transport.assert_not_called()

    def test_response_is_preserved_and_actual_usage_settles_reservation(self):
        body = json.dumps({'id': 'm1', 'usage': {'input_tokens': 100, 'output_tokens': 10}, 'content': []}).encode()
        request = Request('https://api.anthropic.com/v1/messages', data=json.dumps({
            'model': 'claude-sonnet-5', 'max_tokens': 100, 'messages': []}).encode())
        with patch.object(budget, 'shared_ledger', return_value=self.ledger), patch.object(budget, '_transport', return_value=io.BytesIO(body)):
            with budget.urlopen(request) as response:
                self.assertEqual(response.read(), body)
        self.ledger.reserve(2_999_700, 'story')

    def test_timeout_is_not_refunded(self):
        request = Request('https://api.anthropic.com/v1/messages', data=json.dumps({
            'model': 'claude-sonnet-5', 'max_tokens': 100, 'messages': []}).encode())
        with patch.object(budget, 'shared_ledger', return_value=self.ledger), patch.object(budget, '_transport', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                budget.urlopen(request)
        with self.assertRaises(budget.BudgetBlocked):
            self.ledger.reserve(3_000_000, 'story')

    def test_missing_credentials_blocks_paid_call(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(budget.BudgetBlocked):
                budget.shared_ledger()


if __name__ == '__main__':
    unittest.main()

class GitHubStoreTests(unittest.TestCase):
    def test_atomic_update_includes_original_sha_and_shared_branch(self):
        store = budget.GitHubStore('owner/repo', 'test-token')
        with patch.object(store, 'request', return_value={}) as api:
            self.assertTrue(store.write('2026-09-12', 'old-sha', {'version': 1}))
        payload = api.call_args.args[2]
        self.assertEqual(payload['sha'], 'old-sha')
        self.assertEqual(payload['branch'], 'cost-ledger')

    def test_conflict_reloads_instead_of_authorizing_spend(self):
        import urllib.error
        store = budget.GitHubStore('owner/repo', 'test-token')
        with patch.object(store, 'request', side_effect=urllib.error.HTTPError('url', 409, 'conflict', {}, None)):
            self.assertFalse(store.write('2026-09-12', 'old-sha', {}))

    def test_write_timeout_fails_closed(self):
        store = budget.GitHubStore('owner/repo', 'test-token')
        with patch.object(store, 'request', side_effect=TimeoutError):
            with self.assertRaises(budget.BudgetBlocked):
                store.write('2026-09-12', 'old-sha', {})

    def test_dynamic_filtering_is_converted_to_bounded_direct_search(self):
        payload, _ = budget.prepare({'model': 'claude-sonnet-5', 'max_tokens': 16000,
            'messages': [], 'tools': [{'type': 'web_search_20260318', 'name': 'web_search',
            'max_uses': 6, 'response_inclusion': 'excluded'}]})
        self.assertEqual(payload['tools'][0], {'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 1})

    def test_subprocess_installs_guard_and_blocks_unpriced_paid_request(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as target:
            budget.install_runtime(target)
            result = subprocess.run(['python', '-c',
                "import urllib.request; urllib.request.urlopen(urllib.request.Request('https://fal.run/x', data=b'{}'))"],
                env={**os.environ, 'PYTHONPATH': target}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unpriced paid provider blocked', result.stderr)
