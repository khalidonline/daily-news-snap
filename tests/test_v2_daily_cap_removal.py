"""Offline coverage of the owner's 2026-11-04 aggregate-cap removal."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch
import daily_budget as budget
from tests.test_daily_budget import MemoryStore

class DailyCapRemovalTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.now = lambda: datetime(2026, 11, 4, 12, tzinfo=timezone.utc)

    def test_production_factories_have_no_daily_ceiling(self):
        with patch.object(budget, 'GitHubStore', return_value=self.store):
            self.assertIsNone(budget.shared_ledger().limit_micro_usd)
        for requested in (3000000, '8000000', 20000000):
            self.assertIsNone(budget.autopilot_daily_limit(self.now(), requested))

    def test_uncapped_upgrade_preserves_history_and_settlement(self):
        old = budget.Ledger(self.store, now=self.now)
        existing = old.reserve(3000000, 'news')
        before = self.store.read(existing[0])[1]['entries']
        ledger = budget.Ledger(self.store, now=self.now, limit_micro_usd=None)
        token = ledger.reserve(25000000, 'news')
        row = self.store.read(token[0])[1]
        self.assertIsNone(row['limit_micro_usd'])
        for key, entry in before.items():
            self.assertEqual(row['entries'][key], entry)
        ledger.settle(token, 21000000)
        old.settle(existing, 1000000)
        self.assertIsNone(self.store.read(token[0])[1]['limit_micro_usd'])
        with self.assertRaises(budget.BudgetBlocked):
            old.reserve(1, 'news')

    def test_uncapped_still_enforces_package_and_input_controls(self):
        ledger = budget.Ledger(self.store, now=self.now, limit_micro_usd=None)
        for amount in (0, -1, True, 1.5):
            with self.assertRaises(budget.BudgetBlocked):
                ledger.reserve(amount, 'news')
        ledger.context = {'package_id': 'one', 'stage': 'writer'}
        ledger.reserve(750000, 'autopilot:writer')
        with self.assertRaises(budget.BudgetBlocked):
            ledger.reserve(1, 'autopilot:writer')
        with self.assertRaises(budget.BudgetBlocked):
            ledger.reserve(1, 'autopilot:editor')

    def test_uncapped_still_rejects_corrupt_state(self):
        self.store.rows['2026-11-04'] = (1, {'version': 1, 'day': '2026-11-04',
            'limit_micro_usd': 'unlimited', 'entries': {}})
        ledger = budget.Ledger(self.store, now=self.now, limit_micro_usd=None)
        with self.assertRaises(budget.BudgetBlocked):
            ledger.reserve(1, 'news')

    def test_uncapped_concurrent_reservations_keep_every_entry(self):
        ledger = budget.Ledger(self.store, now=self.now, limit_micro_usd=None)
        with ThreadPoolExecutor(max_workers=8) as pool:
            tokens = list(pool.map(lambda _: ledger.reserve(1000000, 'news'), range(32)))
        row = self.store.read(tokens[0][0])[1]
        self.assertEqual(len(row['entries']), 32)
        self.assertEqual(sum(e['charged_micro_usd'] for e in row['entries'].values()), 32000000)

    def test_removal_starts_at_saudi_midnight(self):
        self.assertEqual(budget.autopilot_daily_limit(
            datetime(2026, 11, 3, 20, 59, tzinfo=timezone.utc)), 3000000)
        self.assertIsNone(budget.autopilot_daily_limit(
            datetime(2026, 11, 3, 21, 0, tzinfo=timezone.utc)))
