import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from publishing_v2.autopilot import policy
from publishing_v2.autopilot.sources import Sources, FEEDS
from test_v2_autopilot import research, evidence
import test_v2_autopilot as fixtures

NOW = datetime(2026, 9, 17, 9, tzinfo=timezone.utc)


def feed(items):
    return ('<rss><channel>' + ''.join(
        f'<item><title>{title}</title><link>{url}</link><pubDate>{stamp}</pubDate></item>'
        for title, url, stamp in items) + '</channel></rss>').encode()


class AttentionTests(unittest.TestCase):
    def test_local_has_no_evergreen_fallback_when_feeds_fail(self):
        with patch('publishing_v2.autopilot.sources.fetch', side_effect=OSError):
            self.assertEqual(Sources().discover('local', NOW), [])

    def test_local_discovery_uses_actual_dated_reporting(self):
        raw = feed([('Jeddah festival opens', 'https://www.alyaum.com/articles/123/festival',
                     'Thu, 17 Sep 2026 08:00:00 GMT')])
        with patch('publishing_v2.autopilot.sources.fetch', return_value=raw):
            rows = Sources().discover('local', NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['url'], 'https://www.alyaum.com/articles/123/festival')
        self.assertIn('published_at', rows[0])

    def test_rejected_trigger_is_excluded_even_with_new_query_string(self):
        raw = feed([('Ostrich return', 'https://www.alyaum.com/articles/6683301/new-slug?utm=x',
                     'Thu, 17 Sep 2026 08:00:00 GMT')])
        with patch('publishing_v2.autopilot.sources.fetch', return_value=raw):
            self.assertEqual(Sources().discover('daily', NOW), [])

    def test_all_feeds_have_space_in_bounded_candidate_pool(self):
        replies = [feed([(str(i), f'https://www.bbc.com/news/{n}-{i}',
                         'Thu, 17 Sep 2026 08:00:00 GMT') for i in range(25)])
                   for n in range(len(FEEDS))]
        with patch('publishing_v2.autopilot.sources.fetch', side_effect=replies):
            rows = Sources().discover('daily', NOW)
        self.assertLessEqual(len(rows), 60)
        self.assertTrue(any('/4-' in r['url'] for r in rows))

    def test_missing_and_old_local_attention_dates_are_rejected(self):
        for date in [None, '2026-09-01']:
            data = research(); data['event_date'] = date
            with self.subTest(date=date), self.assertRaises(ValueError):
                policy.validate_research(data, evidence(), 'local', NOW)

    def test_local_reporting_time_is_grounded_like_daily(self):
        data = research(); data['event_date'] = None
        sources = [dict(evidence()[0], source_type='news_article')]
        result = policy.reporting_time(data, sources,
            {'url': sources[0]['url'], 'published_at': NOW.isoformat()}, 'local')
        self.assertEqual(result.get('timing_basis'), 'report_date')

    def test_reviewer_must_explicitly_pass_attention_and_feedback(self):
        checks = {k: True for k in policy.REVIEW_CHECKS
                  if k not in {'current_attention', 'feedback_respected'}}
        with self.assertRaises(ValueError):
            policy.validate_review({'checks': checks, 'reason': 'checked',
                'card_checks': [{'readable': True, 'relevant': True}]}, 1)


class AttentionPipelineTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    render = fixtures.PipelineTests.render
    publish = fixtures.PipelineTests.publish
    pipeline = fixtures.PipelineTests.pipeline

    def test_new_trigger_for_same_subject_is_not_permanently_banned(self):
        candidate = {'id': 'new', 'title': 'Ostrich',
                     'url': 'https://www.alyaum.com/articles/999/new-development',
                     'published_at': NOW.isoformat()}
        policy.validate_attention(candidate, NOW)

    def test_missing_original_news_article_never_reaches_writer(self):
        pipeline = self.pipeline()
        pipeline.sources.research = lambda candidate: [dict(evidence()[0], source_type='encyclopedia')]
        result = pipeline.run('local', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertNotIn('writer', self.agent.calls)

    def test_rejected_trigger_is_blocked_even_if_editor_selects_it(self):
        pipeline = self.pipeline()
        pipeline.sources.discover = lambda lane, now: [
            {'id': 'a', 'url': 'https://www.alyaum.com/articles/6683301/changed',
             'published_at': NOW.isoformat(), 'title': 'rejected'}]
        result = pipeline.run('daily', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertNotIn('researcher', self.agent.calls)

    def test_undated_candidate_cannot_reach_paid_research(self):
        pipeline = self.pipeline()
        pipeline.sources.discover = lambda lane, now: [{'id': 'a', 'title': 'timeless'}]
        result = pipeline.run('local', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertNotIn('researcher', self.agent.calls)

    def test_editor_and_reviewer_receive_owner_feedback(self):
        original = self.agent.run
        seen = []
        def run(role, data, images=()):
            if role in {'editor', 'reviewer'}:
                self.assertTrue(data.get('editorial_feedback'))
                seen.append(role)
            return original(role, data, images)
        self.agent.run = run
        self.assertEqual(self.pipeline().run('local', 'shadow')['status'], 'shadow_passed')
        self.assertEqual(seen, ['editor', 'reviewer'])
