# 2026-09-27 run: an approved Al-Buraikan package died because one story card
# had no distinct photo; two candidates were logged as timing format faults.
import copy
import tempfile
import unittest
from pathlib import Path

from daily_budget import BudgetBlocked
from publishing_v2.autopilot import policy
from publishing_v2.autopilot.evidence import hydrate_timing
from publishing_v2.autopilot.pipeline import Pipeline
from publishing_v2.autopilot.runtime import LaneLedger, DAILY_LANE_SHARE
from test_v2_autopilot import NOW, FakeAgent, FakeSources, MemoryStore, draft


def four_cards():
    base = draft()
    base['cards'].append(copy.deepcopy(base['cards'][1]))
    for i, card in enumerate(base['cards']):
        card['title'] = f'بطاقة {i}'
    return base


class ShortfallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def run_with(self, missing):
        rendered = []
        def render(package, output):
            cards = [c for c in package['cards'] if c.get('kind') != 'credits']
            if len(cards) == 4 and missing:
                raise policy.VisualShortfall(missing, 'no distinct photo')
            rendered.append([c['title'] for c in cards])
            output.mkdir(parents=True, exist_ok=True)
            paths = []
            for i, _ in enumerate(package['cards']):
                path = output / f'{i}.jpg'; path.write_bytes(f'px {i}'.encode()); paths.append(path)
            return paths
        class Writer(FakeAgent):
            def run(self, role, data, images=()):
                if role == 'writer':
                    self.calls.append(role); return four_cards()
                return super().run(role, data, images)
        agent = Writer()
        pipeline = Pipeline(agent=agent, sources=FakeSources(), render=render, store=MemoryStore(),
                            publish=lambda p, paths: None, output=Path(self.temp.name), now=lambda: NOW)
        return pipeline.run('daily', 'shadow'), agent, rendered

    def test_photo_less_story_card_is_dropped_and_text_reapproved(self):
        result, agent, rendered = self.run_with([2])
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertEqual(rendered, [['بطاقة 0', 'بطاقة 1', 'بطاقة 3']])
        self.assertEqual(agent.calls.count('writer'), 1)
        self.assertEqual(agent.calls.count('text_review'), 2)   # the shortened text is judged again
        self.assertIn('visual_shortened', [e['event'] for e in result['audit']])

    def test_info_card_or_too_few_cards_still_rejects(self):
        for missing in ([0], [1, 2]):
            result, agent, _ = self.run_with(missing)
            self.assertEqual(result['status'], 'held', missing)
            reasons = [e.get('reason', '') for e in result['audit'] if e['event'] == 'candidate_rejected']
            self.assertTrue(reasons[0].startswith('insufficient_distinct_story_photos'), reasons)


class TimingFormatTests(unittest.TestCase):
    def test_refusal_without_basis_is_a_refusal(self):
        result = hydrate_timing({'eligible': False}, [])
        self.assertIs(result['eligible'], False)
        with self.assertRaisesRegex(ValueError, 'ineligible_or_uncertain_event_time'):
            policy.validate_timing(result, [], NOW)

    def test_eligible_without_date_is_a_format_fault(self):
        with self.assertRaisesRegex(ValueError, 'unexpected_timing_fields'):
            hydrate_timing({'eligible': True, 'timing_basis': 'event', 'reason': 'x'}, [])


class Ledger:
    limit_micro_usd = 3_000_000
    def __init__(self): self.reserved, self.settled = [], []
    def reserve(self, amount, bot):
        self.reserved.append(amount); return ('day', len(self.reserved))
    def settle(self, token, actual): self.settled.append(actual)


class LaneLedgerTests(unittest.TestCase):
    def test_daily_share_caps_reservations_and_credits_back_settlements(self):
        inner = Ledger()
        lane = LaneLedger(inner, inner.limit_micro_usd * DAILY_LANE_SHARE)
        token = lane.reserve(1_500_000, 'autopilot:researcher')
        lane.settle(token, 200_000)                  # unused reservation returns to the lane
        self.assertEqual(lane.used, 200_000)
        lane.reserve(1_500_000, 'autopilot:writer')
        with self.assertRaises(BudgetBlocked) as caught:
            lane.reserve(200_000, 'autopilot:reviewer')
        self.assertEqual(caught.exception.diagnostic['code'], 'lane_share_exhausted')
        self.assertEqual(len(inner.reserved), 2)     # the shared ledger never saw the blocked request

    def test_context_and_limit_pass_through(self):
        inner = Ledger()
        lane = LaneLedger(inner, 100)
        lane.context = {'stage': 'writer'}
        self.assertEqual(inner.context, {'stage': 'writer'})
        self.assertEqual(lane.context, {'stage': 'writer'})
        self.assertEqual(lane.limit_micro_usd, 3_000_000)


if __name__ == '__main__':
    unittest.main()
