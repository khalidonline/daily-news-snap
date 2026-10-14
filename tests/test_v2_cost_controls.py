"""Offline regressions for the owner's 27 September production ceilings."""
import copy
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from daily_budget import BudgetBlocked, Ledger
from test_daily_budget import MemoryStore
import test_v2_autopilot as fixtures
from test_v2_autopilot import FakeAgent, NOW, research
from publishing_v2.autopilot.agents import Agents


class PackageBudgetTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()

    def ledger(self, stage, package='one'):
        ledger = Ledger(self.store, now=lambda: datetime(2026, 9, 27, 16, tzinfo=timezone.utc))
        ledger.context = {'package_id': package, 'stage': stage}
        return ledger

    def test_research_and_repairs_share_cap_across_restart(self):
        ledger = self.ledger('researcher')
        token = ledger.reserve(600_000, 'autopilot:researcher')
        ledger.settle(token, 500_000)
        self.ledger('writer').reserve(250_000, 'autopilot:writer')
        with self.assertRaises(BudgetBlocked):
            self.ledger('card_repair').reserve(1, 'autopilot:card_repair')
        self.ledger('writer', 'two').reserve(1, 'autopilot:writer')

    def test_visual_and_final_review_share_separate_cap(self):
        self.ledger('writer').reserve(750_000, 'autopilot:writer')
        self.ledger('image_check').reserve(100_000, 'autopilot:image_check')
        self.ledger('text_review').reserve(100_000, 'autopilot:text_review')
        self.ledger('reviewer').reserve(300_000, 'autopilot:reviewer')
        with self.assertRaises(BudgetBlocked):
            self.ledger('visual').reserve(1, 'autopilot:visual')

    def test_concurrent_reservations_cannot_both_fit(self):
        def reserve(_):
            try:
                self.ledger('writer').reserve(400_000, 'autopilot:writer')
                return True
            except BudgetBlocked:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(reserve, range(2))), [False, True])

    def test_selection_unknown_stage_and_missing_identity_cannot_reserve(self):
        for stage in ('editor', 'timing', 'pitch_judge', 'hooks', 'hook_judge', 'unknown'):
            with self.subTest(stage=stage), self.assertRaises(BudgetBlocked):
                self.ledger(stage).reserve(1, 'autopilot:' + stage)
        for package in ('', 'selection:daily'):
            with self.subTest(package=package), self.assertRaises(BudgetBlocked):
                self.ledger('writer', package).reserve(1, 'autopilot:writer')

    def test_stage_cannot_be_mislabelled_to_borrow_other_allowance(self):
        with self.assertRaises(BudgetBlocked):
            self.ledger('writer').reserve(1, 'autopilot:reviewer')

    def test_daily_cap_still_includes_other_bots(self):
        ledger = self.ledger('writer')
        ledger.reserve(2_900_000, 'other-project-stage')
        with self.assertRaises(BudgetBlocked):
            ledger.reserve(100_001, 'autopilot:writer')

    def test_paid_selection_never_contacts_provider(self):
        calls = []
        def transport(*args):
            calls.append(args)
            raise AssertionError('provider must not be called')
        agent = Agents(env={'ANTHROPIC_API_KEY': 'offline'}, ledger=self.ledger('editor'), transport=transport)
        for role in ('editor', 'timing', 'pitch_judge', 'hooks', 'hook_judge'):
            with self.subTest(role=role), self.assertRaises(BudgetBlocked):
                agent.run(role, {'sources': []})
        self.assertEqual(calls, [])


class FreeSelectionTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    render = fixtures.PipelineTests.render
    publish = fixtures.PipelineTests.publish
    pipeline = fixtures.PipelineTests.pipeline
    # Reuse only the fixture, not its legacy selection expectations.
    def make_pipeline(self):
        pipeline = self.pipeline()
        self.agent.requires_free_selection = True
        candidate = pipeline.sources.discover('daily', NOW)[0]
        choice = FakeAgent().run('editor', {'candidates': pipeline.sources.discover('daily', NOW)})['candidates'][0]
        pipeline.free_selection = {
            'version': 1, 'lane': 'daily', 'candidate_id': 'a', 'choice': choice,
            'timing': dict(research(), eligible=True, timing_basis='event', reason='Current event'),
            'story': [{'source_id': 's1', 'quote': q, 'point': p} for q, p in [
                ('A useful historical fact.', 'البداية'),
                ('The event began on 17 September 2026.', 'التغيير'),
                ('17 September 2026.', 'النتيجة')]],
            'image_plan': [{'asset_id': str(i), 'purpose': 'صورة تطابق المرحلة'} for i in range(3)],
        }
        def screen(candidate):
            candidate['visual_feasibility'] = [{'asset_id': str(i)} for i in range(3)]
            return True
        def render(package, output):
            return self.render(package, output)
        render.screen_visuals = screen
        pipeline.render = render
        return pipeline

    def test_missing_free_brief_stops_without_paid_selection(self):
        pipeline = self.make_pipeline()
        pipeline.free_selection = None
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertEqual(self.agent.calls, [])

    def test_good_brief_skips_all_paid_selection_and_timing_roles(self):
        pipeline = self.make_pipeline()
        pipeline.hooks = True
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'shadow_passed', result.get('reason'))
        self.assertNotIn('editor', self.agent.calls)
        self.assertNotIn('timing', self.agent.calls)
        self.assertNotIn('hooks', self.agent.calls)
        self.assertEqual(self.agent.calls.count('researcher'), 1)

    def test_free_assessment_and_card_plan_reach_actual_writer(self):
        pipeline = self.make_pipeline()
        original = self.agent.run
        payloads = []
        def run(role, data, images=()):
            if role == 'writer': payloads.append(copy.deepcopy(data))
            return original(role, data, images)
        self.agent.run = run
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertEqual(result['selection_assessment']['status'], 'evidence_passed')
        self.assertEqual(payloads[0]['candidate']['card_image_plan'], pipeline.free_selection['image_plan'])

    def test_missing_images_stops_before_first_paid_request(self):
        pipeline = self.make_pipeline()
        pipeline.render.screen_visuals = lambda c: False
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertEqual(self.agent.calls, [])

    def test_invented_story_or_image_or_old_timing_stops_before_spend(self):
        for mutation in ('story', 'image', 'date'):
            self.store.data = {}; self.agent.calls = []
            pipeline = self.make_pipeline()
            if mutation == 'story': pipeline.free_selection['story'][0]['quote'] = 'Not in the source'
            if mutation == 'image': pipeline.free_selection['image_plan'][0]['asset_id'] = 'missing'
            if mutation == 'date': pipeline.free_selection['timing']['event_date'] = '2025-01-01'
            result = pipeline.run('daily', 'shadow')
            self.assertEqual(result['status'], 'held', mutation)
            self.assertEqual(self.agent.calls, [], mutation)

    def test_failed_selected_candidate_does_not_start_second_package(self):
        pipeline = self.make_pipeline()
        original = self.agent.run
        def run(role, data, images=()):
            if role == 'researcher':
                self.agent.calls.append(role)
                raise ValueError('unsupported_story')
            return original(role, data, images)
        self.agent.run = run
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertEqual(self.agent.calls, ['researcher'])
        self.assertEqual(result['candidate_id'], 'a')



class RuntimeLaneTests(unittest.TestCase):
    def test_metadata_without_downloaded_pixels_is_not_feasibility(self):
        from publishing_v2.autopilot.runtime import Renderer
        class Sources:
            image_bytes = {}
            def subject_images(self, subject, query):
                return [{'asset_id': key, 'title': 'Jeddah', 'license': 'CC0'} for key in ('a', 'b')]
        candidate = {'resolved_subjects': [{'name': 'Jeddah'}]}
        self.assertFalse(Renderer(None, Sources()).screen_visuals(candidate))

    def test_both_modes_reject_dual_production_before_any_credentials(self):
        from unittest.mock import patch
        from publishing_v2.autopilot.runtime import main
        for mode in ('shadow', 'live'):
            with patch('sys.argv', ['runtime', '--mode', mode, '--lane', 'both']):
                with self.assertRaisesRegex(ValueError, 'produce_one_lane_per_run'):
                    main()
