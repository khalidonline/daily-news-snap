import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape

from publishing_v2.autopilot import policy
from publishing_v2.autopilot.sources import Sources, FEEDS
from test_v2_autopilot_attention import NOW
import test_v2_autopilot as fixtures

URL = 'https://www.alyaum.com/articles/123/schools'
BODY = ('Schools begin National Day activities on Sunday with classroom programmes and documented local history. ' * 9)

def rss(body=BODY, url=URL):
    return ('<rss><channel><item><title>School activities</title><link>' + escape(url)
            + '</link><pubDate>Thu, 17 Sep 2026 08:00:00 GMT</pubDate><description>'
            + escape(body) + '</description></item></channel></rss>').encode()

class PublisherFeedTests(unittest.TestCase):
    def discover(self, body=BODY):
        source = Sources()
        with patch('publishing_v2.autopilot.sources.fetch',
                   side_effect=lambda url: rss(body) if url == FEEDS[3] else b'<rss/>'):
            candidate = source.discover('local', NOW)[0]
        candidate['editorial'] = {'research_query': 'Saudi National Day'}
        return source, candidate

    def test_substantive_publisher_text_recovers_failed_article_with_provenance(self):
        source, candidate = self.discover()
        with patch('publishing_v2.autopilot.sources.fetch', side_effect=OSError), \
             patch('publishing_v2.autopilot.sources.wiki', return_value=[]):
            row = source.research(candidate)[0]
        self.assertEqual(row['source_type'], 'publisher_feed')
        self.assertEqual(row['feed_url'], FEEDS[3])
        self.assertEqual(row['url'], URL)
        self.assertEqual(row['text'], BODY.strip())

    def test_short_summary_is_not_promoted_to_article_evidence(self):
        source, candidate = self.discover('A headline-sized summary without the actual article text.')
        with patch('publishing_v2.autopilot.sources.fetch', side_effect=OSError), \
             patch('publishing_v2.autopilot.sources.wiki', return_value=[]), \
             self.assertRaises(ValueError):
            source.research(candidate)

    def test_changed_candidate_cannot_reuse_cached_evidence(self):
        for key, value in [('url', URL + '-other'), ('published_at', NOW.isoformat()), ('id', 'other')]:
            source, candidate = self.discover()
            candidate[key] = value
            with self.subTest(key=key), patch('publishing_v2.autopilot.sources.fetch', side_effect=OSError), \
                 patch('publishing_v2.autopilot.sources.wiki', return_value=[]), self.assertRaises(ValueError):
                source.research(candidate)

    def test_foreign_publisher_feed_cannot_supply_another_publishers_evidence(self):
        source = Sources()
        with patch('publishing_v2.autopilot.sources.fetch',
                   side_effect=lambda url: rss() if url == FEEDS[0] else b'<rss/>'):
            candidate = source.discover('local', NOW)[0]
        candidate['editorial'] = {'research_query': 'Schools'}
        with patch('publishing_v2.autopilot.sources.fetch', side_effect=OSError), \
             patch('publishing_v2.autopilot.sources.wiki', return_value=[]), self.assertRaises(ValueError):
            source.research(candidate)

    def test_available_article_is_preferred(self):
        source, candidate = self.discover()
        with patch('publishing_v2.autopilot.sources.fetch', return_value=BODY.encode()), \
             patch('publishing_v2.autopilot.sources.wiki', return_value=[]):
            row = source.research(candidate)[0]
        self.assertEqual(row['source_type'], 'news_article')

class FeedPipelineTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    render = fixtures.PipelineTests.render
    publish = fixtures.PipelineTests.publish
    pipeline = fixtures.PipelineTests.pipeline

    def test_publisher_evidence_still_requires_full_review_and_preserves_provenance(self):
        pipeline = self.pipeline()
        row = dict(fixtures.evidence()[0], source_type='publisher_feed', feed_url=FEEDS[0],
                   published_at=NOW.isoformat(), text=fixtures.evidence()[0]['text'] + ' ' + BODY)
        pipeline.sources.research = lambda candidate: [row]
        result = pipeline.run('local', 'shadow')
        self.assertEqual(result['status'], 'shadow_passed')
        self.assertIn('reviewer', self.agent.calls)
        self.assertEqual(result['sources'][0]['feed_url'], FEEDS[0])
        self.assertEqual(result['sources'][0]['source_type'], 'publisher_feed')
        data = fixtures.research(); data['event_date'] = None
        self.assertEqual(policy.reporting_time(data, [row],
            {'url': row['url'], 'published_at': NOW.isoformat()}, 'local')['timing_basis'], 'report_date')

    def test_untrusted_feed_cannot_reach_paid_research(self):
        pipeline = self.pipeline()
        pipeline.sources.research = lambda candidate: [dict(fixtures.evidence()[0],
            source_type='publisher_feed', feed_url='https://untrusted.example/rss',
            published_at=NOW.isoformat(), text=BODY)]
        result = pipeline.run('local', 'shadow')
        self.assertEqual(result['status'], 'held')
        self.assertNotIn('researcher', self.agent.calls)
