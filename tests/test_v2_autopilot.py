import copy
import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from publishing_v2.autopilot import policy
from publishing_v2.autopilot.pipeline import Pipeline


NOW = datetime(2026, 9, 17, 9, tzinfo=timezone.utc)


class MemoryStore:
    def __init__(self): self.data = {}
    def read(self): return copy.deepcopy(self.data)
    def save(self, data): self.data = copy.deepcopy(data)


def evidence():
    return [{'id': 's1', 'url': 'https://www.bbc.com/news/a',
             'source_type': 'news_article', 'text': 'The event began on 17 September 2026. A useful historical fact.'}]


def research():
    return {'event_date': '2026-09-17', 'event_quote': '17 September 2026',
            'event_source_id': 's1', 'sensitive': False,
            'claims': [{'id': 'c1', 'source_id': 's1', 'quote': 'A useful historical fact.',
                        'fact': 'حقيقة مفيدة'}]}


def draft():
    return {'title': 'قصة قريبة من الناس', 'cards': [
        {'kind': kind, 'title': 'حكاية المكان', 'body': 'معلومة واضحة وقريبة من الناس',
         'punch': '', 'claim_ids': ['c1'], 'image_query': 'Jeddah'}
        for kind in ['info', 'story', 'story']]}


class FakeAgent:
    def __init__(self, reject=0): self.reject, self.calls = reject, []
    def run(self, role, data, images=()):
        self.calls.append(role)
        if role == 'editor':
            return {'candidates': [{'id': 'a', 'why_saudi': 'قريب من الناس',
                                    'angle': 'قصة جدة', 'why_now': 'اليوم', 'share_reason': 'معلومة جديدة',
                                    'research_query': 'Jeddah', 'subjects': ['Jeddah'],
                                    'source_title': next(c['title'] for c in data['candidates'] if c['id'] == 'a'),
                                    'subject_evidence': [{'subject':'Jeddah','mention':'جدة',
                                        'quote':'بدأ مهرجان جدة اليوم في المنطقة التاريخية'}]},
                                   {'id': 'b', 'why_saudi': 'قريب من الناس',
                                    'angle': 'قصة جدة', 'why_now': 'اليوم', 'share_reason': 'معلومة جديدة',
                                    'research_query': 'Jeddah', 'subjects': ['Jeddah'],
                                    'source_title': next(c['title'] for c in data['candidates'] if c['id'] == 'b'),
                                    'subject_evidence': [{'subject':'Jeddah','mention':'جدة',
                                        'quote':'بدأ مهرجان جدة اليوم في المنطقة التاريخية'}]}]}
        if role == 'timing':
            return dict(research(), eligible=True, timing_basis='event', reason='Current event')
        if role == 'researcher': return research()
        if role == 'text_review':
            from publishing_v2.editorial_production import TEXT_CHECKS
            return {'checks':dict.fromkeys(TEXT_CHECKS,True),'repair_indices':[],'reason':'Source text verified'}
        if role == 'card_repair':
            return {'patches':[{'index':i,'card':copy.deepcopy(data['draft']['cards'][i])} for i in data['repair_indices']]}
        if role == 'writer': return draft()
        if role == 'reviewer':
            passed = self.reject <= 0
            self.reject -= 1
            return {'checks': {key: passed for key in policy.REVIEW_CHECKS},
                    'reason': 'Checked against evidence and images',
                    'repair_indices': [] if passed else list(range(len(data['cards']))),
                    'card_checks': [{'readable': passed, 'relevant': passed} for _ in images]}
        raise AssertionError(role)


class FakeSources:
    def discover(self, lane, now): return [{'id': x, 'title': x, 'summary': 'بدأ مهرجان جدة اليوم في المنطقة التاريخية', 'url': 'https://www.bbc.com/news/a', 'published_at': now.isoformat()} for x in ['a', 'b']]
    def attention(self, candidate): return evidence()
    def research(self, candidate): return evidence()


class PipelineTests(unittest.TestCase):
    def test_image_rejection_is_handed_to_the_next_render(self):
        self.agent.reject = 1
        seen = []
        def render(package, output):
            seen.append(copy.deepcopy(package))
            for i, card in enumerate(package['cards']):
                card['image'] = {'asset_id': str(i)}
            return self.render(package, output)
        pipeline = self.pipeline()
        pipeline.render = render
        self.assertEqual(pipeline.run('daily', 'shadow')['status'], 'shadow_passed')
        self.assertEqual(seen[1]['repair']['excluded_image_ids'], ['0', '1', '2'])
        self.assertIn('Checked against evidence', seen[1]['repair']['feedback'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store, self.agent, self.sent = MemoryStore(), FakeAgent(), []
        self.renders = 0

    def render(self, package, output):
        self.renders += 1
        output.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, card in enumerate(package['cards']):
            path = output / f'{i}.jpg'
            path.write_bytes(f'pixels {i}'.encode())
            paths.append(path)
        return paths

    def publish(self, package, paths):
        self.sent.append(package)
        return {'status': 'POSTED', 'post_ids': ['one', 'two', 'three']}

    def pipeline(self, **kwargs):
        return Pipeline(agent=self.agent, sources=FakeSources(), render=self.render,
                        store=self.store, publish=kwargs.get('publish', self.publish),
                        output=Path(self.temp.name), now=lambda: NOW)

    def test_four_rejected_candidates_are_bounded_and_audited(self):
        class MoreCandidates(FakeAgent):
            def run(self, role, data, images=()):
                result = super().run(role, data, images)
                if role == 'editor':
                    result['candidates'] = [dict(result['candidates'][0], id=ident, source_title=ident) for ident in 'abcd']
                if role == 'researcher': result['sensitive'] = True
                return result
        pipeline = self.pipeline()
        pipeline.agent = MoreCandidates()
        pipeline.sources.discover = lambda lane, now: [{'id': ident, 'title': ident, 'summary': 'بدأ مهرجان جدة اليوم في المنطقة التاريخية', 'url': 'https://www.bbc.com/news/a', 'published_at': now.isoformat()} for ident in 'abcd']
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertEqual(pipeline.agent.calls.count('researcher'), 4)
        self.assertEqual(sum(e['event'] == 'candidate_rejected' for e in result['audit']), 4)

    def recovery_pipeline(self, *, succeed=None, repeat=False, block=False):
        pipeline = self.pipeline()
        rows = [dict(FakeSources().discover('daily', NOW)[0], id=x, title=x) for x in 'abcdefghij']
        pipeline.sources.discover = lambda lane, now: rows
        base = FakeAgent().run('editor', {'candidates': FakeSources().discover('daily', NOW)})['candidates'][0]
        pools, researched = [], []
        original = self.agent.run
        def run(role, data, images=()):
            if role == 'editor':
                pools.append([c['id'] for c in data['candidates']])
                if block and len(pools) == 2:
                    from daily_budget import BudgetBlocked
                    raise BudgetBlocked('daily_cap')
                selected = rows[:4] if repeat else data['candidates'][:4]
                return {'candidates': [dict(base, id=c['id'], source_title=c['title']) for c in selected]}
            return original(role, data, images)
        self.agent.run = run
        def retrieve(candidate):
            researched.append(candidate['id'])
            if candidate['id'] != succeed:
                raise ValueError('unresolved_editorial_subject')
            return evidence()
        pipeline.sources.research = retrieve
        return pipeline, pools, researched

    def test_second_editor_round_uses_remaining_candidates_and_can_finish(self):
        pipeline, pools, researched = self.recovery_pipeline(succeed='e')
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertEqual(pools, [list('abcdefghij'), list('efghij')])
        self.assertEqual(researched, list('abcde'))
        self.assertEqual(self.sent, [])

    def test_first_round_success_does_not_select_again(self):
        pipeline, pools, researched = self.recovery_pipeline(succeed='a')
        self.assertEqual(pipeline.run('daily', 'shadow')['status'], 'shadow_passed')
        self.assertEqual(len(pools), 1)

    def test_sibling_lane_candidate_is_filtered_before_editor_and_research(self):
        pipeline = self.pipeline()
        pipeline.excluded_candidate_ids = {'a'}
        seen_pools, researched = [], []
        original = self.agent.run
        def run(role, data, images=()):
            if role == 'editor':
                seen_pools.append([c['id'] for c in data['candidates']])
                choice = data['candidates'][0]
                return {'candidates': [{
                    'id': choice['id'], 'why_saudi': 'قريب من الناس',
                    'angle': 'قصة جدة', 'why_now': 'اليوم',
                    'share_reason': 'معلومة جديدة', 'research_query': 'Jeddah',
                    'subjects': ['Jeddah'], 'source_title': choice['title'],
                    'subject_evidence': [{'subject':'Jeddah','mention':'جدة',
                        'quote':'بدأ مهرجان جدة اليوم في المنطقة التاريخية'}],
                }]}
            if role == 'researcher':
                researched.append(data['candidate']['id'])
            return original(role, data, images)
        self.agent.run = run
        result = pipeline.run('local', 'shadow')
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertEqual(seen_pools, [['b']])
        self.assertEqual(researched, ['b'])
        filtered = [row for row in result['eligibility_rejections']
                    if row['candidate_id'] == 'a']
        self.assertEqual(filtered[0]['reason'], 'selected_in_sibling_lane')

    def test_selection_recovery_stops_after_three_rounds(self):
        pipeline, pools, researched = self.recovery_pipeline()
        self.assertEqual(pipeline.run('daily', 'shadow')['status'], 'held')
        self.assertEqual(len(pools), 3)
        self.assertEqual(researched, list('abcdefghij'))

    def test_repeated_candidate_in_second_round_is_not_retried(self):
        pipeline, pools, researched = self.recovery_pipeline(repeat=True)
        self.assertEqual(pipeline.run('daily', 'shadow')['status'], 'held')
        self.assertEqual(len(pools), 2)
        self.assertEqual(researched, list('abcd'))

    def test_second_round_budget_block_stops_recovery(self):
        pipeline, pools, researched = self.recovery_pipeline(block=True)
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertEqual(result['reason'], 'BudgetBlocked')
        self.assertEqual(len(pools), 2)
        self.assertEqual(researched, list('abcd'))

    def test_single_video_receipt_covers_all_reviewed_frames(self):
        pipeline=self.pipeline(publish=lambda package,paths:{'status':'POSTED','post_ids':['video-post']})
        def render(package,output):
            package['delivery']={'kind':'video'}
            return self.render(package,output)
        pipeline.render=render
        result=pipeline.run('daily','live',rollout_verified=True)
        self.assertEqual(result['status'],'published')
        self.assertEqual(len(result['paths']),3)
        self.assertEqual(result['receipt']['post_ids'],['video-post'])

    def test_shadow_finishes_with_independent_review_without_publishing(self):
        result = self.pipeline().run('daily', 'shadow')
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertEqual(self.sent, [])
        self.assertIn('reviewer', self.agent.calls)
        self.assertEqual(len(result['approval']['media_sha256']), 3)

    def test_rejected_package_is_repaired_and_reviewed_again(self):
        self.agent.reject = 1
        result = self.pipeline().run('local', 'shadow')
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertEqual(self.agent.calls.count('reviewer'), 2)
        self.assertEqual(self.renders, 2)

    def test_rejections_are_bounded_and_never_publish(self):
        self.agent.reject = 99
        result = self.pipeline().run('daily', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertEqual(self.agent.calls.count('reviewer'), 8)
        self.assertEqual(self.sent, [])

    def test_two_review_rejections_can_be_repaired_without_new_candidate(self):
        self.agent.reject = 2
        result = self.pipeline().run('local', 'shadow')
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertEqual(self.agent.calls.count('reviewer'), 3)
        self.assertEqual(self.agent.calls.count('researcher'), 1)
        self.assertEqual(self.sent, [])

    def test_slot_rerun_does_not_pay_for_generation_again(self):
        first = self.pipeline().run('daily', 'shadow')
        count = len(self.agent.calls)
        self.assertEqual(self.pipeline().run('daily', 'shadow'), first)
        self.assertEqual(len(self.agent.calls), count)

    def test_live_requires_verified_rollout(self):
        with self.assertRaisesRegex(ValueError, 'rollout'):
            self.pipeline().run('daily', 'live')
        self.assertEqual(self.agent.calls, [])

    def test_publish_failure_never_regenerates_slot(self):
        def fail(package, paths): raise RuntimeError('ambiguous create')
        pipe = self.pipeline(publish=fail)
        result = pipe.run('daily', 'live', rollout_verified=True)
        self.assertEqual(result['status'], 'delivery_pending')
        count = len(self.agent.calls)
        result = pipe.run('daily', 'live', rollout_verified=True)
        self.assertEqual(result['status'], 'delivery_pending')
        self.assertEqual(len(self.agent.calls), count)

    def test_successful_delivery_clears_stale_error_reason(self):
        calls = 0
        def flaky_then_success(package, paths):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError('temporary delivery issue')
            return {'status': 'POSTED', 'post_ids': ['one', 'two', 'three']}
        pipe = self.pipeline(publish=flaky_then_success)
        first = pipe.run('daily', 'live', rollout_verified=True)
        self.assertEqual(first['status'], 'delivery_pending')
        self.assertEqual(first['reason'], 'RuntimeError')
        second = pipe.run('daily', 'live', rollout_verified=True)
        self.assertEqual(second['status'], 'published')
        self.assertIsNone(second['reason'])

    def test_journal_failure_after_publish_never_reenters_generation(self):
        original = self.store.save
        def flaky(state):
            if state['audit'][-1]['event'] in {'delivery_verified', 'delivery_unresolved'}:
                raise OSError('journal unavailable')
            original(state)
        self.store.save = flaky
        with self.assertRaises(Exception):
            self.pipeline().run('daily', 'live', rollout_verified=True)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.agent.calls.count('writer'), 1)

    def test_receipts_are_durable_before_publication(self):
        self.agent.receipts = [{'role': 'reviewer', 'response_id': 'independent-response'}]
        def publish(package, paths):
            self.assertEqual(self.store.read()['agent_receipts'], self.agent.receipts)
            return {'status': 'POSTED', 'post_ids': ['a', 'b', 'c']}
        self.assertEqual(self.pipeline(publish=publish).run('daily', 'live', rollout_verified=True)['status'], 'published')

    def test_reviewer_gets_full_source_context_not_only_selected_quotes(self):
        original = self.agent.run
        def run(role, data, images=()):
            if role == 'reviewer':
                self.assertEqual(data['original_sources'], evidence())
            return original(role, data, images)
        self.agent.run = run
        self.assertEqual(self.pipeline().run('local', 'shadow')['status'], 'shadow_passed')

    def test_research_rejection_records_specific_validation_reason(self):
        original = self.agent.run
        def run(role, data, images=()):
            value = original(role, data, images)
            if role == 'researcher': value['claims'] = []
            return value
        self.agent.run = run
        result = self.pipeline().run('local', 'shadow')
        events = [e for e in result['audit'] if e['event'] == 'candidate_rejected']
        self.assertEqual(events[0]['reason'], 'invalid_claims')


class PolicyTests(unittest.TestCase):
    def test_story_context_fits_bounded_expanded_body(self):
        data = draft()
        data['cards'][1]['body'] = 'ب' * 320
        policy.validate_draft(data, research())
        data['cards'][1]['body'] += 'ب'
        with self.assertRaises(ValueError):
            policy.validate_draft(data, research())

    def test_unsupported_numeric_claim_is_pruned_without_weakening_validator(self):
        data = research()
        data['claims'] = [
            {'id': ident, 'source_id': 's1', 'quote': 'A useful historical fact.',
             'fact': 'حقيقة مفيدة'}
            for ident in ('c1', 'c2', 'c3')
        ] + [
            {'id': 'bad', 'source_id': 's1', 'quote': 'A useful historical fact.',
             'fact': 'حقيقة في 2026'}
        ]
        cleaned, dropped = policy.prune_unsupported_number_claims(data, evidence())
        self.assertEqual(dropped, ['bad'])
        self.assertEqual([claim['id'] for claim in cleaned['claims']], ['c1', 'c2', 'c3'])
        policy.validate_research(cleaned, evidence(), 'daily', NOW)
        with self.assertRaisesRegex(ValueError, 'unsupported_claim_number'):
            policy.validate_research(data, evidence(), 'daily', NOW)

    def test_numeric_prune_fails_closed_when_too_little_story_evidence_remains(self):
        data = research()
        data['claims'] = [
            {'id': 'c1', 'source_id': 's1', 'quote': 'A useful historical fact.',
             'fact': 'حقيقة مفيدة'},
            {'id': 'bad', 'source_id': 's1', 'quote': 'A useful historical fact.',
             'fact': 'حقيقة في 2026'},
        ]
        with self.assertRaisesRegex(ValueError, 'insufficient_supported_claims_after_prune'):
            policy.prune_unsupported_number_claims(data, evidence())

    def test_language_and_story_failures_each_block_approval(self):
        for key in ('saudi_language', 'story_coherent'):
            checks = dict.fromkeys(policy.REVIEW_CHECKS, True)
            checks[key] = False
            review = {'checks': checks, 'reason': 'Needs editorial repair',
                      'card_checks': [{'readable': True, 'relevant': True}] * 3}
            with self.assertRaisesRegex(ValueError, 'editorial_review_rejected'):
                policy.validate_review(review, 3)

    def test_writer_cannot_supply_image_rights_or_extra_authority_fields(self):
        data = draft(); data['cards'][0]['image'] = {'license': 'CC0', 'download_url': 'invented'}
        with self.assertRaises(ValueError): policy.validate_draft(data, research())
    def test_fabricated_quote_is_rejected(self):
        data = research(); data['claims'][0]['quote'] = 'Invented supporting evidence'
        with self.assertRaises(ValueError): policy.validate_research(data, evidence(), 'daily', NOW)

    def test_old_event_cannot_be_refreshed_by_current_article(self):
        data = research(); data['event_date'] = '2026-09-14'
        with self.assertRaises(ValueError): policy.validate_research(data, evidence(), 'daily', NOW)

    def test_string_true_and_missing_card_reviews_do_not_approve(self):
        checks = {key: True for key in policy.REVIEW_CHECKS}
        checks['factual'] = 'true'
        with self.assertRaises(ValueError): policy.validate_review({'checks': checks}, 3)

    def test_writer_cannot_reference_unknown_claim(self):
        data = draft(); data['cards'][0]['claim_ids'] = ['invented']
        with self.assertRaises(ValueError): policy.validate_draft(data, research())

    def test_approval_detects_changed_image_or_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'a.jpg'; path.write_bytes(b'original')
            package = {'title': 'approved', 'expires_at': '2026-09-18T21:00:00+00:00'}
            approval = policy.seal(package, [path])
            policy.verify_seal(package, [path], approval, NOW)
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError): policy.verify_seal(package, [path], approval, NOW)


if __name__ == '__main__': unittest.main()

