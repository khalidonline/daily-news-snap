import unittest
import tempfile
from unittest.mock import patch
from publishing_v2.autopilot.sources import Sources
from publishing_v2.autopilot.pipeline import Pipeline
from test_v2_autopilot import MemoryStore, FakeSources, NOW
from daily_budget import Ledger, BudgetBlocked
from test_v2_autopilot_adapters import Store
from publishing_v2.autopilot.runtime import Renderer


class TrialDiagnosticsTests(unittest.TestCase):
    def test_reservation_reports_real_cap_request_and_balance(self):
        ledger = Ledger(Store(), limit_micro_usd=5_000_000)
        ledger.reserve(3_200_000, 'prior')
        with self.assertRaises(BudgetBlocked) as caught:
            ledger.reserve(2_000_000, 'next')
        self.assertEqual(caught.exception.diagnostic, {
            'code': 'insufficient_remaining', 'limit_micro_usd': 5_000_000,
            'requested_micro_usd': 2_000_000, 'charged_micro_usd': 3_200_000})

    def test_preflight_excludes_unrelated_name_matches(self):
        class Sources:
            def images(self, query):
                return [dict(asset_id=str(i), title=title, license='CC0',
                             width=1600, height=1200) for i, title in enumerate([
                    'File:Diego Simeone portrait.jpg', 'File:Simone Italian painting.jpg',
                    'File:Simeone restaurant.jpg', 'File:Diego Simeone training.jpg'])]
        rows = Renderer(object(), Sources()).plan_visuals({
            'id': 's', 'editorial': {'research_query': 'Diego Simeone'}})
        self.assertEqual([r['asset_id'] for r in rows], ['0', '3'])

    def test_preflight_handles_accents_in_names(self):
        class Sources:
            def images(self, query):
                return [dict(asset_id='1', title='File:José Mourinho.jpg', license='CC0',
                             width=1600, height=1200)]
        rows = Renderer(object(), Sources()).plan_visuals({
            'id': 'm', 'editorial': {'research_query': 'Jose Mourinho'}})
        self.assertEqual(len(rows), 1)

    def test_specific_search_does_not_poison_subject_cache(self):
        def search(query, **kwargs):
            return [dict(asset_id=query + str(i), title=query, license='CC0',
                         width=1600, height=1200) for i in range(5)]
        with patch('publishing_v2.autopilot.sources.search_commons', side_effect=search) as api:
            source = Sources()
            source.images('Jose Mourinho portrait')
            self.assertNotIn('Jose Mourinho', source.image_cache)
            source.images('Jose Mourinho')
            self.assertIn('Jose Mourinho', [c.args[0] for c in api.call_args_list])

    def test_pipeline_persists_safe_diagnostic_not_exception_text(self):
        class Agent:
            def run(self, *args, **kwargs):
                raise BudgetBlocked('secret provider response', code='request_exceeds_ceiling',
                                    limit=5_000_000, requested=6_000_000)
        with tempfile.TemporaryDirectory() as folder:
            result = Pipeline(agent=Agent(), sources=FakeSources(), render=None,
                              store=MemoryStore(), publish=None, output=folder,
                              now=lambda: NOW).run('daily', 'shadow')
        self.assertEqual(result['reason'], 'BudgetBlocked')
        self.assertEqual(result['budget_diagnostic']['limit_micro_usd'], 5_000_000)
        self.assertNotIn('secret', str(result))
