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

    def test_explicit_upgrade_preserves_settled_and_reserved_charges(self):
        settled = self.ledger.reserve(1_000_000, 'news')
        self.ledger.settle(settled, 200_000)
        self.ledger.reserve(2_000_000, 'story')
        _, original = self.store.read('2026-09-12')
        commissioning = budget.Ledger(self.store, now=lambda: self.now,
                                      limit_micro_usd=10_000_000)
        commissioning.reserve(7_800_000, 'commissioning')
        _, row = self.store.read('2026-09-12')
        self.assertEqual(row['limit_micro_usd'], 10_000_000)
        for ident, entry in original['entries'].items():
            self.assertEqual(row['entries'][ident], entry)
        with self.assertRaises(budget.BudgetBlocked):
            commissioning.reserve(1, 'retry')

    def test_twenty_dollar_upgrade_keeps_unknown_reservations_and_ten_dollar_callers_bounded(self):
        old = budget.Ledger(self.store, now=lambda: self.now, limit_micro_usd=10_000_000)
        settled = old.reserve(4_500_000, 'prior-runs')
        old.settle(settled, 4_475_385)
        old.reserve(115_566, 'unknown-writer')
        before = self.store.read('2026-09-12')[1]
        with self.assertRaises(budget.BudgetBlocked):
            old.reserve(5_409_600, 'visual-review')
        upgraded = budget.Ledger(self.store, now=lambda: self.now, limit_micro_usd=20_000_000)
        review = upgraded.reserve(5_409_600, 'visual-review')
        after = self.store.read('2026-09-12')[1]
        for ident, entry in before['entries'].items():
            self.assertEqual(after['entries'][ident], entry)
        with self.assertRaises(budget.BudgetBlocked):
            old.reserve(1, 'old-run')
        upgraded.settle(review, 200_000)
        upgraded.reserve(15_209_049, 'remaining-headroom')
        with self.assertRaises(budget.BudgetBlocked):
            upgraded.reserve(1, 'over-cap')

    def test_legacy_caller_keeps_lower_ceiling_and_can_settle_upgraded_row(self):
        old = self.ledger.reserve(2_000_000, 'news')
        commissioning = budget.Ledger(self.store, now=lambda: self.now,
                                      limit_micro_usd=10_000_000)
        newer = commissioning.reserve(6_000_000, 'commissioning')
        with self.assertRaises(budget.BudgetBlocked):
            self.ledger.reserve(1, 'legacy')
        self.ledger.settle(old, 500_000)
        self.ledger.settle(newer, 1_000_000)
        self.ledger.reserve(1_500_000, 'legacy')
        with self.assertRaises(budget.BudgetBlocked):
            self.ledger.reserve(1, 'legacy')
        self.assertEqual(self.store.read(old[0])[1]['limit_micro_usd'], 10_000_000)
        commissioning.reserve(7_000_000, 'commissioning')

    def test_configured_ceiling_requires_integer_between_three_and_twenty_dollars(self):
        for limit in [None, True, False, 3_000_000.0, '10000000', -1, 0,
                      2_999_999, 20_000_001]:
            with self.subTest(limit=limit), self.assertRaises(budget.BudgetBlocked):
                budget.Ledger(self.store, limit_micro_usd=limit)
        for limit in [3_000_000, 5_500_000, 10_000_000, 20_000_000]:
            ledger = budget.Ledger(MemoryStore(), limit_micro_usd=limit)
            ledger.reserve(limit, 'commissioning')
            with self.assertRaises(budget.BudgetBlocked):
                ledger.reserve(1, 'retry')

    def test_invalid_shared_ceiling_blocks_upgrade_without_reset(self):
        for limit in [True, 3_000_000.0, '3000000', 2_999_999, 20_000_001]:
            original = {'version': 1, 'day': '2026-09-12',
                        'limit_micro_usd': limit, 'entries': {}}
            self.store.rows['2026-09-12'] = (1, original)
            commissioning = budget.Ledger(self.store, now=lambda: self.now,
                                          limit_micro_usd=10_000_000)
            with self.subTest(limit=limit), self.assertRaises(budget.BudgetBlocked):
                commissioning.reserve(1, 'commissioning')
            self.assertEqual(self.store.read('2026-09-12'), (1, original))

    def test_concurrent_upgrade_and_legacy_reservations_share_ten_dollar_cap(self):
        self.ledger.reserve(2_000_000, 'existing')
        commissioning = budget.Ledger(self.store, now=lambda: self.now,
                                      limit_micro_usd=10_000_000)
        def reserve(index):
            ledger = commissioning if index % 2 else self.ledger
            try:
                ledger.reserve(500_000, 'concurrent')
                return 1
            except budget.BudgetBlocked:
                return 0
        with ThreadPoolExecutor(max_workers=12) as pool:
            accepted = sum(pool.map(reserve, range(64)))
        self.assertEqual(accepted, 16)
        row = self.store.read('2026-09-12')[1]
        self.assertEqual(sum(e['charged_micro_usd'] for e in row['entries'].values()),
                         10_000_000)

    def test_upgrade_conflict_reloads_intervening_charge(self):
        self.ledger.reserve(2_000_000, 'existing')
        commissioning = budget.Ledger(self.store, now=lambda: self.now,
                                      limit_micro_usd=10_000_000)
        write = self.store.write
        raced = False
        def racing_write(day, version, row):
            nonlocal raced
            if not raced:
                raced = True
                self.ledger.reserve(500_000, 'other-run')
            return write(day, version, row)
        with patch.object(self.store, 'write', side_effect=racing_write):
            with self.assertRaises(budget.BudgetBlocked):
                commissioning.reserve(8_000_000, 'commissioning')
        row = self.store.read('2026-09-12')[1]
        self.assertEqual(len(row['entries']), 2)
        self.assertEqual(row['limit_micro_usd'], 3_000_000)
        commissioning.reserve(7_500_000, 'commissioning')
        with self.assertRaises(budget.BudgetBlocked):
            commissioning.reserve(1, 'retry')

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

class WorkflowBudgetTests(unittest.TestCase):
    def test_paid_workflows_cannot_override_guard_python_path(self):
        from pathlib import Path
        for path in Path('.github/workflows').glob('*.yml'):
            text = path.read_text()
            if 'secrets.ANTHROPIC_API_KEY' not in text:
                continue
            if path.name == 'publishing-v2-autopilot.yml':
                # These two audited entry points use Agents + Ledger directly.
                # Any new credential-bearing step must be reviewed explicitly.
                import yaml
                workflow = yaml.safe_load(text)
                allowed = {
                    'python recover_held_local.py',
                    'python -m publishing_v2.autopilot.runtime --mode "$AUTOPILOT_MODE" --lane "$AUTOPILOT_LANE"',
                }
                for job in workflow['jobs'].values():
                    self.assertNotIn('ANTHROPIC_API_KEY', job.get('env', {}))
                    for step in job['steps']:
                        env = step.get('env', {})
                        if 'ANTHROPIC_API_KEY' in env:
                            self.assertIn(step.get('run','').strip(), allowed)
                            self.assertEqual(str(env.get('AUTOPILOT_DAILY_LIMIT_MICRO_USD')), '3000000')
                            self.assertIn('DAILY_BUDGET_GITHUB_TOKEN',env)
            else:
                self.assertIn('Install shared $3 daily budget guard', text, str(path))
            for line in text.splitlines():
                if 'PYTHONPATH=' in line or 'PYTHONPATH:' in line:
                    self.assertIn('daily-budget', line, f'{path}: {line}')


class NativeAgentBudgetTests(unittest.TestCase):
    def test_exhausted_shared_ledger_prevents_provider_connection(self):
        from publishing_v2.autopilot.agents import Agents
        ledger=budget.Ledger(MemoryStore(), limit_micro_usd=3000000)
        ledger.reserve(3000000,'already-used')
        def forbidden_transport(*args,**kwargs):
            raise AssertionError('provider contacted despite exhausted budget')
        agent=Agents(env={'ANTHROPIC_API_KEY':'offline-test'},ledger=ledger,transport=forbidden_transport)
        with self.assertRaises(budget.BudgetBlocked):
            agent.run('text_review',{'cards':[]})
        self.assertEqual(agent.receipts,[])
