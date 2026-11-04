"""Selected sources stay bound to publisher evidence, not feed ranking."""
import hashlib
from datetime import datetime, timezone
from html import escape
from unittest.mock import patch

import pytest

from publishing_v2.autopilot.sources import Sources, SourceRedirect

URL = 'https://www.alyaum.com/articles/selected-falcon'
TITLE = 'Selected falcon auction'
DATE = '2026-11-04T03:33:00+00:00'
FEED = 'https://www.alyaum.com/rssFeed/1005'
NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
BODY = 'The original publisher reports a falcon auction with verified details. ' * 15


def brief():
    ident = hashlib.sha256(URL.encode()).hexdigest()[:16]
    return {'version': 1, 'lane': 'daily', 'candidate_id': ident,
            'choice': {'id': ident, 'source_title': TITLE},
            'source': {'url': URL, 'title': TITLE, 'published_at': DATE, 'feed_url': FEED}}


def item(url=URL, title=TITLE, date='Wed, 04 Nov 2026 03:33:00 GMT'):
    return ('<item><link>' + escape(url) + '</link><title>' + escape(title)
            + '</title><pubDate>' + escape(date) + '</pubDate><description>'
            + escape(BODY) + '</description><enclosure type="image/jpeg" '
            'url="https://www.alyaum.com/falcon.jpg"/></item>')


def feed(items):
    return ('<rss><channel>' + ''.join(items) + '</channel></rss>').encode()


def test_selection_beyond_discovery_rank_preserves_evidence_and_images():
    provider = Sources()
    raw = feed([item(url=URL + str(n), title='Other story') for n in range(30)] + [item()])
    with patch('publishing_v2.autopilot.sources.fetch', return_value=raw) as fetch:
        chosen = provider.resolve_selection(brief(), 'daily', NOW)
    assert chosen['url'] == URL and chosen['title'] == TITLE
    assert chosen['published_at'] == DATE
    key = (chosen['id'], URL, DATE)
    assert provider.publisher_articles[key]['text'] == BODY.strip()
    assert provider.feed_images[key] == ['https://www.alyaum.com/falcon.jpg']
    fetch.assert_called_once_with(FEED)


@pytest.mark.parametrize('field,value', [
    ('url', 'http://www.alyaum.com/a'), ('url', 'https://www.alyaum.com.evil.test/a'),
    ('url', 'https://user:pass@www.alyaum.com/a'), ('url', 'https://www.alyaum.com:444/a'),
    ('url', 'https://www.alyaum.com/a#fragment'), ('url', 'https://en.wikipedia.org/wiki/Falcon'),
    ('feed_url', 'https://www.alyaum.com/arbitrary-feed'),
    ('title', 'Unapproved replacement'), ('published_at', 'not-a-date'),
    ('published_at', '2026-11-04T03:33:00'),
])
def test_invalid_metadata_never_retrieves(field, value):
    selected = brief(); selected['source'][field] = value
    with patch('publishing_v2.autopilot.sources.fetch', side_effect=AssertionError('unexpected retrieval')):
        with pytest.raises(ValueError):
            Sources().resolve_selection(selected, 'daily', NOW)


@pytest.mark.parametrize('change', ['candidate_id', 'choice_id', 'lane'])
def test_identity_or_lane_drift_fails_before_retrieval(change):
    selected = brief()
    if change == 'choice_id': selected['choice']['id'] = 'incorrect'
    else: selected[change] = 'incorrect'
    with patch('publishing_v2.autopilot.sources.fetch', side_effect=AssertionError('unexpected retrieval')):
        with pytest.raises(ValueError): Sources().resolve_selection(selected, 'daily', NOW)


@pytest.mark.parametrize('row', [item(title='Replacement title'),
    item(date='Wed, 04 Nov 2026 04:33:00 GMT'), item(date='not-a-date'), item(url=URL + '-other')])
def test_fresh_publisher_metadata_must_match_original(row):
    with patch('publishing_v2.autopilot.sources.fetch', return_value=feed([row])):
        with pytest.raises(ValueError): Sources().resolve_selection(brief(), 'daily', NOW)


@pytest.mark.parametrize('now', [datetime(2026, 11, 6, tzinfo=timezone.utc),
                                datetime(2026, 11, 4, 1, tzinfo=timezone.utc)])
def test_stale_or_future_selection_is_not_refreshed(now):
    with patch('publishing_v2.autopilot.sources.fetch', return_value=feed([item()])):
        with pytest.raises(ValueError): Sources().resolve_selection(brief(), 'daily', now)


def test_lookup_is_bounded_and_does_not_fall_back_to_other_story():
    rows = [item(url=URL + str(n)) for n in range(250)] + [item()]
    with patch('publishing_v2.autopilot.sources.fetch', return_value=feed(rows)) as fetch:
        with pytest.raises(ValueError): Sources().resolve_selection(brief(), 'daily', NOW)
    fetch.assert_called_once_with(FEED)


def test_unrelated_malformed_item_does_not_hide_selection():
    with patch('publishing_v2.autopilot.sources.fetch', return_value=feed([item(url='bad', date='bad'), item()])):
        assert Sources().resolve_selection(brief(), 'daily', NOW)['title'] == TITLE


def test_legacy_brief_keeps_existing_pool_behavior():
    selected = brief(); del selected['source']
    assert Sources().resolve_selection(selected, 'daily', NOW) is None


def test_selected_lookup_keeps_redirect_guard():
    with pytest.raises(ValueError, match='source_url_not_allowed'):
        SourceRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.test/article')
