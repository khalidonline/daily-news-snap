import unittest
from unittest.mock import patch
from publishing_v2.autopilot import policy
from publishing_v2.autopilot.sources import Sources
import test_v2_autopilot as fixtures


def timing(date='2026-09-17'):
    return {'eligible': True, 'event_date': date, 'event_source_id': 's1',
            'event_quote': 'The event began on 17 September 2026.',
            'timing_basis': 'event', 'reason': 'Current documented development'}


class TimingPreflightTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    pipeline = fixtures.PipelineTests.pipeline
    render = fixtures.PipelineTests.render
    publish = fixtures.PipelineTests.publish

    def test_old_event_is_rejected_before_history_images_or_full_research(self):
        pipeline = self.pipeline()
        seen = []
        pipeline.sources.attention = lambda candidate: fixtures.evidence()
        pipeline.sources.research = lambda candidate: seen.append('history')
        def render(*args):
            seen.append('render')
        render.plan_visuals = lambda candidate: seen.append('images')
        pipeline.render = render
        original = self.agent.run
        def run(role, data, images=()):
            if role == 'timing':
                seen.append('timing')
                return timing('2026-09-01')
            return original(role, data, images)
        self.agent.run = run
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertEqual(seen, ['timing', 'timing'])
        self.assertNotIn('researcher', self.agent.calls)
        self.assertNotIn('writer', self.agent.calls)
        self.assertTrue(any(e.get('reason') == 'event_outside_window' for e in result['audit']))

    def test_uncertain_or_unsupported_timing_cannot_pass(self):
        for changes in ({'eligible': False}, {'event_date': None},
                        {'event_quote': 'Invented current event description'},
                        {'event_source_id': 'unknown'}, {'timing_basis': 'guess'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                policy.validate_timing(dict(timing(), **changes), fixtures.evidence(), fixtures.NOW)

    def test_attention_retrieval_does_not_fetch_history_and_is_reused(self):
        source = Sources()
        candidate = dict(fixtures.FakeSources().discover('daily', fixtures.NOW)[0],
                         editorial={'research_query': 'Jeddah'})
        article = ('A current report about Jeddah. ' * 15).encode()
        with patch('publishing_v2.autopilot.sources.fetch', return_value=article) as fetch, \
             patch('publishing_v2.autopilot.sources.wiki', return_value=[]) as wiki:
            self.assertTrue(source.attention(candidate))
            wiki.assert_not_called()
            source.research(candidate)
            self.assertEqual(fetch.call_count, 1)

    def test_current_trigger_passes_before_history_images_and_research(self):
        pipeline = self.pipeline()
        seen = []
        original = self.agent.run
        def run(role, data, images=()):
            seen.append(role)
            return original(role, data, images)
        self.agent.run = run
        pipeline.sources.research = lambda candidate: (seen.append('history') or fixtures.evidence())
        def render(package, output):
            return self.render(package, output)
        render.plan_visuals = lambda candidate: (seen.append('images') or [{'asset_id': str(i)} for i in range(3)])
        pipeline.render = render
        self.assertEqual(pipeline.run('daily', 'shadow')['status'], 'shadow_passed')
        self.assertLess(seen.index('timing'), seen.index('history'))
        self.assertLess(seen.index('timing'), seen.index('images'))
        self.assertLess(seen.index('timing'), seen.index('researcher'))

    def test_timing_request_has_small_budgeted_output(self):
        import json
        from test_v2_autopilot_recovery import FormatRecoveryTests
        decision = {k: v for k, v in timing().items() if k not in {'event_quote', 'event_source_id'}}
        decision['event_passage_id'] = 's1:p0'
        agent, ledger, calls = FormatRecoveryTests().agent([json.dumps(decision)])
        result = agent.run('timing', {'sources': fixtures.evidence()})
        self.assertEqual(result['event_quote'], fixtures.evidence()[0]['text'])
        self.assertEqual(result['event_date'], timing()['event_date'])
        self.assertEqual(calls[0]['model'], 'claude-sonnet-5')
        self.assertEqual(calls[0]['max_tokens'], 2048)
        self.assertEqual(len(ledger.reserved), 1)
        self.assertEqual(len(ledger.settled), 1)
