import hashlib
import json
from datetime import datetime
from unittest.mock import patch

import pytest
from publishing_v2.autopilot import sources as m

URL='https://www.alyaum.com/articles/6689569/%D8%B5%D9%82%D8%B1'
DATE='2026-11-04T03:33:00+03:00'
NOW=datetime.fromisoformat('2026-11-04T14:00:00+00:00')
TITLE='صقر'

def brief():
    ident=hashlib.sha256(URL.encode()).hexdigest()[:16]
    return {'version':1,'lane':'daily','candidate_id':ident,'choice':{'id':ident,'source_title':TITLE},
            'source':{'url':URL,'title':TITLE,'published_at':DATE,'feed_url':'https://www.alyaum.com/rssFeed/1005'}}

def page(**changes):
    data={'@type':'NewsArticle','headline':TITLE,'datePublished':DATE,'mainEntityOfPage':{'@id':'6689569'}}
    data.update(changes)
    return ('<link rel="canonical" href="'+URL+'"><meta property="og:url" content="'+URL+'">'
            '<meta property="og:title" content="'+TITLE+'"><script type="application/ld+json">'+json.dumps(data)+
            '</script><article>'+('خبر عن الصقر ' * 100)+'</article>').encode()

def resolve(html):
    s=m.Sources()
    with patch.object(m,'fetch',side_effect=[b'<rss><channel/></rss>',html]) as read:
        c=s.resolve_selection(brief(),'daily',NOW)
        assert read.call_count==2
        assert s.attention(c)[0]['source_type']=='news_article'
        assert read.call_count==2
    return s,c

def test_absent_feed_exact_article_metadata_and_cached_body():
    s,c=resolve(page())
    assert c['url']==URL and c['published_at']==DATE
    assert c['id']==brief()['candidate_id']
    assert URL in s.article_html
    assert not s.publisher_articles

@pytest.mark.parametrize('changes',[
    {'headline':'different'}, {'datePublished':'2026-11-04T03:34:00+03:00'},
    {'datePublished':None,'dateModified':DATE},{'datePublished':'2026-11-04T03:33:00'},
    {'datePublished':'2026-11-05T03:33:00+03:00'},{'datePublished':'2026-11-02T03:33:00+03:00'},
    {'mainEntityOfPage':{'@id':'different'}},
])
def test_mismatched_authoritative_metadata_holds(changes):
    with pytest.raises(ValueError):resolve(page(**changes))

@pytest.mark.parametrize('suffix',[
    '<script type="application/ld+json">{broken</script>',
    '<script type="application/ld+json">'+json.dumps({'@type':'NewsArticle','headline':'other'})+'</script>',
    '<meta property="og:title" content="other">',
    '<link rel="canonical" href="https://www.alyaum.com/articles/other">',
])
def test_conflicting_or_malformed_metadata_holds(suffix):
    with pytest.raises(ValueError):resolve(page()+suffix.encode())

def test_canonical_identity_is_required():
    with pytest.raises(ValueError):resolve(page().replace(b'rel="canonical"',b'rel="other"'))

def test_unicode_percent_encoding_equivalence():
    resolve(page().replace(URL.encode(),URL.replace('%D8%B5%D9%82%D8%B1','صقر').encode()))

def test_feed_fetch_failure_does_not_attempt_article():
    with patch.object(m,'fetch',side_effect=OSError('offline')) as read:
        with pytest.raises(ValueError):m.Sources().resolve_selection(brief(),'daily',NOW)
        assert read.call_count==1

@pytest.mark.parametrize('target',[
    'https://www.bbc.com/articles/6689569',
    'https://www.alyaum.com/articles/6689570/other',
    URL+'?redirected=yes', URL.replace('/articles/', '/articles%2F'),
])
def test_pinned_redirect_rejects_other_host_or_identity(target):
    from urllib.request import Request
    redirect=m.SourceRedirect(URL)
    with pytest.raises(ValueError):
        redirect.redirect_request(Request(URL),None,302,'Found',{},target)


def test_present_feed_keeps_original_route_without_article_fetch():
    from email.utils import format_datetime
    from html import escape
    source=brief()['source']
    rss=('<rss><channel><item><link>'+escape(URL)+'</link><title>'+TITLE+'</title><pubDate>'+
         format_datetime(datetime.fromisoformat(DATE))+'</pubDate><description>Original feed</description>'+
         '</item></channel></rss>').encode()
    with patch.object(m,'fetch',return_value=rss) as read:
        s=m.Sources();c=s.resolve_selection(brief(),'daily',NOW)
        assert c['summary']=='Original feed'
        assert not s.article_html
        assert read.call_count==1

@pytest.mark.parametrize('html',[
    page().replace(b'"headline":', b'"headline":"other", "headline":'),
    page()+b'<meta property="article:published_time" content="2026-11-04T04:33:00+03:00">',
    page().replace(b'</script>',b''),
    page().replace(b'property="og:url"',b'property="other"'),
    page().replace(b'%D8%B5%D9%82%D8%B1',b'%2Fother'),
])
def test_incomplete_or_contradictory_publisher_metadata_holds(html):
    with pytest.raises(ValueError,match='selected_source_article_metadata_unverified'):
        resolve(html)


def test_summary_uses_verified_article_description_not_navigation():
    from publishing_v2.autopilot.feedback import MUSIC_ARTIST_TERMS, rejected_trigger
    description='بيع صقرين في المزاد الوطني'
    html=('<nav>'+MUSIC_ARTIST_TERMS[0]+'</nav>').encode()+page(description=description)
    _,candidate=resolve(html)
    assert candidate['summary']==description
    assert not rejected_trigger(candidate)


def test_summary_preserves_actual_article_rejection_terms():
    from publishing_v2.autopilot.feedback import MUSIC_ARTIST_TERMS, rejected_trigger
    _,candidate=resolve(page(description=MUSIC_ARTIST_TERMS[0]))
    assert rejected_trigger(candidate)


def test_summary_without_article_description_stays_empty_not_navigation():
    _,candidate=resolve(page())
    assert candidate['summary']==''

@pytest.mark.parametrize('field', ['description','articleBody'])
def test_article_specific_summary_fields(field):
    _,candidate=resolve(page(**{field:'Article-specific falcon summary'}))
    assert candidate['summary']=='Article-specific falcon summary'


def test_open_graph_description_fallback():
    _,candidate=resolve(page()+b'<meta property="og:description" content="Publisher article summary">')
    assert candidate['summary']=='Publisher article summary'


def test_conflicting_open_graph_descriptions_hold():
    with pytest.raises(ValueError,match='selected_source_article_metadata_unverified'):
        resolve(page()+b'<meta property="og:description" content="one"><meta property="og:description" content="two">')


def test_all_verified_article_metadata_preserves_subject_quote_not_navigation():
    from publishing_v2.autopilot.feedback import rejected_trigger
    from html import escape
    short='بيع صقرين بـ388 ألف ريال في الليلة 17'
    lead='شهدت الليلة 17 بيع صقرين من نوع شاهين فرخ بمبلغ إجمالي بلغ 388 ألف ريال'
    html=(page(description=short)+('<meta property="og:description" content="'+escape(lead)+'">'
                                  '<nav>موسيقى</nav>').encode())
    _,candidate=resolve(html)
    assert short in candidate['summary']
    assert 'بيع صقرين من نوع شاهين فرخ' in candidate['summary']
    assert not rejected_trigger(candidate)


def test_secondary_verified_description_rejection_terms_remain_visible():
    from publishing_v2.autopilot.feedback import MUSIC_ARTIST_TERMS,rejected_trigger
    _,candidate=resolve(page(description='Falcon article')+
                        ('<meta property="og:description" content="'+MUSIC_ARTIST_TERMS[0]+'">').encode())
    assert rejected_trigger(candidate)
