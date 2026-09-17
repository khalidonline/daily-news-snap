"""Bounded read-only discovery and source retrieval; no model-supplied hosts."""
import hashlib
import json
from datetime import timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, build_opener
from xml.etree import ElementTree

from publishing_v2.public_images import NoRedirect, search_commons

FEEDS = ('https://feeds.bbci.co.uk/news/rss.xml',
         'https://feeds.bbci.co.uk/news/technology/rss.xml',
         'https://feeds.bbci.co.uk/sport/rss.xml',
         'https://www.alyaum.com/rssFeed/1005', 'https://aawsat.com/feed')
HOSTS = {'feeds.bbci.co.uk', 'www.bbc.com', 'www.bbc.co.uk', 'bbc.com', 'bbc.co.uk',
         'www.alyaum.com', 'aawsat.com', 'www.aawsat.com', 'en.wikipedia.org', 'ar.wikipedia.org'}
LOCAL_TOPICS = ('Saudi coffee', 'Jeddah', 'Taif rose', 'Bisht', 'Al-Qatt Al-Asiri',
                'Al-Ahsa Oasis', 'Saudi Arabian cuisine', 'Diriyah', 'Date palm', 'Souq')


def safe_url(url):
    try:
        part = urlsplit(url)
        okay = part.scheme == 'https' and part.hostname in HOSTS and not part.username and not part.password
        okay = okay and part.port in (None, 443) and not part.fragment
    except (TypeError, ValueError):
        okay = False
    if not okay:
        raise ValueError('source_url_not_allowed')
    return url


def fetch(url):
    request = Request(safe_url(url), headers={'User-Agent': 'DailyNewsSnap/2.0 (editorial research)'})
    with build_opener(NoRedirect()).open(request, timeout=15) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('source_too_large')
    return raw


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript'}: self.skip += 1
    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript'}: self.skip = max(0, self.skip - 1)
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def plain(raw):
    parser = ArticleText(); parser.feed(raw)
    return ' '.join(' '.join(parser.parts).split())[:16000]


def wiki(query):
    # Query text cannot select arbitrary URLs or redirect retrieval elsewhere.
    query = str(query)[:180]
    base = 'https://en.wikipedia.org/w/api.php?'
    search = json.loads(fetch(base + urlencode({'action': 'query', 'format': 'json',
                        'list': 'search', 'srsearch': query, 'srlimit': 2})))
    ids = [str(p['pageid']) for p in search.get('query', {}).get('search', [])[:2]]
    if not ids: return []
    result = json.loads(fetch(base + urlencode({'action': 'query', 'format': 'json',
        'pageids': '|'.join(ids), 'prop': 'extracts', 'explaintext': 1, 'exchars': 10000})))
    return [{'id': 'wiki-' + str(page['pageid']), 'url': 'https://en.wikipedia.org/?curid=' + str(page['pageid']),
             'text': str(page.get('extract', ''))[:10000], 'title': page.get('title'),
             'source_type': 'encyclopedia'}
            for page in result.get('query', {}).get('pages', {}).values() if page.get('extract')]


def reusable_image(row):
    # Metadata from the source adapter, never a model-provided rights assertion.
    return (row.get('license') in {'Public domain', 'CC0', 'CC0 1.0'}
            and not row.get('restrictions')
            and str(row.get('attribution_required', '')).lower() in {'', 'false', 'no'})


class Sources:
    def discover(self, lane, now):
        if lane == 'local':
            start = now.date().toordinal() % len(LOCAL_TOPICS)
            return [{'id': 'local-' + hashlib.sha256(topic.encode()).hexdigest()[:12],
                     'title': topic, 'local': True}
                    for topic in (LOCAL_TOPICS[(start + i) % len(LOCAL_TOPICS)] for i in range(5))]
        results, seen = [], set()
        for url in FEEDS:
            try:
                root = ElementTree.fromstring(fetch(url))
                for item in list(root.iter('item'))[:25]:
                    link = item.findtext('link', '')
                    if link in seen: continue
                    safe_url(link)
                    published = parsedate_to_datetime(item.findtext('pubDate', ''))
                    if published.tzinfo is None or not now - timedelta(days=1) <= published <= now:
                        continue
                    seen.add(link)
                    results.append({'id': hashlib.sha256(link.encode()).hexdigest()[:16],
                        'title': plain(item.findtext('title', ''))[:250], 'url': link,
                        'summary': plain(item.findtext('description', ''))[:1000],
                        'published_at': published.isoformat()})
            except Exception:
                continue
        return results[:60]

    def research(self, candidate):
        rows = []
        if candidate.get('url'):
            try:
                body = plain(fetch(candidate['url']).decode('utf-8', errors='replace'))
                if len(body) > 200:
                    rows.append({'id': 'article', 'url': candidate['url'], 'text': body,
                                 'source_type': 'news_article'})
            except Exception:
                pass
        try:
            rows.extend(wiki(candidate['editorial']['research_query']))
        except Exception:
            pass
        if not rows:
            raise ValueError('no_retrieved_evidence')
        return rows

    def images(self, query):
        return [row for row in search_commons(query, limit=5) if reusable_image(row)]
