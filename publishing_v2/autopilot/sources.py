"""Bounded read-only discovery and source retrieval; no model-supplied hosts."""
import hashlib
import json
import re
from datetime import timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from xml.etree import ElementTree

from publishing_v2.public_images import search_commons
from .credits import attribution_eligible
from .feedback import rejected_trigger

FEEDS = ('https://feeds.bbci.co.uk/news/rss.xml',
         'https://feeds.bbci.co.uk/news/technology/rss.xml',
         'https://feeds.bbci.co.uk/sport/rss.xml',
         'https://www.alyaum.com/rssFeed/1005', 'https://aawsat.com/feed')
HOSTS = {'feeds.bbci.co.uk', 'www.bbc.com', 'www.bbc.co.uk', 'bbc.com', 'bbc.co.uk',
         'www.alyaum.com', 'aawsat.com', 'www.aawsat.com', 'en.wikipedia.org', 'ar.wikipedia.org'}
LOCAL_TOPICS = ('Abha', 'Asir', 'Khamis Mushait', 'Saudi coffee', 'Jeddah', 'Taif rose', 'Bisht', 'Al-Qatt Al-Asiri',
                'Al-Ahsa Oasis', 'Saudi Arabian cuisine', 'Diriyah', 'Date palm', 'Souq')


FEED_PUBLISHERS = {feed: ({'www.alyaum.com'} if 'alyaum.com' in feed else
                         {'aawsat.com', 'www.aawsat.com'} if 'aawsat.com' in feed else
                         {'bbc.com', 'www.bbc.com', 'bbc.co.uk', 'www.bbc.co.uk'})
                   for feed in FEEDS}


def attention_source(source, candidate):
    if source.get('url') != candidate.get('url'):
        return False
    if source.get('source_type') == 'news_article':
        return True
    if source.get('source_type') != 'publisher_feed':
        return False
    body = source.get('text', '')
    return (urlsplit(source.get('url', '')).hostname in FEED_PUBLISHERS.get(source.get('feed_url'), set())
            and source.get('published_at') == candidate.get('published_at')
            and isinstance(body, str) and len(body) >= 500 and len(body.split()) >= 80)


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


class SourceRedirect(HTTPRedirectHandler):
    """Article canonicalization may redirect, but every hop stays allowlisted."""
    def __init__(self):
        self.hops = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        self.hops += 1
        if self.hops > 3:
            raise ValueError('source_redirect_limit')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    request = Request(safe_url(url), headers={'User-Agent': 'DailyNewsSnap/2.0 (editorial research)'})
    with build_opener(SourceRedirect()).open(request, timeout=15) as response:
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
    parser = ArticleText(); parser.feed(unescape(raw))
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
    return attribution_eligible(row) or (row.get('license') in {'Public domain', 'CC0', 'CC0 1.0'}
            and not row.get('restrictions')
            and str(row.get('attribution_required', '')).lower() in {'', 'false', 'no'})


class Sources:
    def __init__(self):
        self.publisher_articles = {}
        self.image_cache = {}
        self.image_search_cache = {}

    def discover(self, lane, now):
        if lane not in {'daily', 'local'}:
            raise ValueError('invalid_lane')
        # Both lanes need a real attention moment. LOCAL_TOPICS only helps image
        # search; a date-based rotation is not evidence that people care today.
        results, seen = [], set()
        for url in FEEDS:
            try:
                root = ElementTree.fromstring(fetch(url))
                accepted = 0
                for item in list(root.iter('item'))[:25]:
                    link = item.findtext('link', '')
                    if link in seen: continue
                    safe_url(link)
                    published = parsedate_to_datetime(item.findtext('pubDate', ''))
                    if published.tzinfo is None or not now - timedelta(days=1) <= published <= now:
                        continue
                    seen.add(link)
                    candidate = {'id': hashlib.sha256(link.encode()).hexdigest()[:16],
                        'title': plain(item.findtext('title', ''))[:250], 'url': link,
                        'summary': plain(item.findtext('description', ''))[:1000],
                        'published_at': published.isoformat()}
                    if rejected_trigger(candidate):
                        continue
                    body = plain(item.findtext('{http://purl.org/rss/1.0/modules/content/}encoded', '')
                                 or item.findtext('description', ''))
                    publisher = {'id': 'article', 'url': link, 'text': body,
                                 'source_type': 'publisher_feed', 'feed_url': url,
                                 'published_at': published.isoformat()}
                    if attention_source(publisher, candidate):
                        self.publisher_articles[(candidate['id'], link, candidate['published_at'])] = publisher
                    results.append(candidate)
                    accepted += 1
                    # Reserve room for later Saudi feeds in the bounded pool.
                    if accepted >= 12:
                        break
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
            except Exception as error:
                print(json.dumps({'stage': 'article_retrieval_failed', 'url': candidate['url'],
                                  'error': type(error).__name__, 'http_status': getattr(error, 'code', None)}), flush=True)
        if not rows:
            publisher = self.publisher_articles.get((candidate.get('id'), candidate.get('url'),
                                                     candidate.get('published_at')))
            if publisher and attention_source(publisher, candidate):
                rows.append(dict(publisher))
        try:
            rows.extend(wiki(candidate['editorial']['research_query']))
        except Exception:
            pass
        if not rows:
            raise ValueError('no_retrieved_evidence')
        return rows

    def images(self, query):
        query = ' '.join(str(query).split())[:130]
        if not query:
            return []
        if query in self.image_cache:
            return self.image_cache[query]
        # Commons ANDs all words. Recover the named subject from descriptive
        # briefs before spending the request budget on lower-ranked results.
        subjects = [query]
        for topic in sorted(LOCAL_TOPICS, key=len, reverse=True):
            if re.search(r'(?<!\w)' + re.escape(topic) + r'(?!\w)', query, re.I):
                subjects.append(topic)
                break
        words = query.split()
        if len(words) > 2:
            subjects.extend([' '.join(words[:3]), ' '.join(words[:2])])
        subjects = list(dict.fromkeys(subjects))[:3]
        searches = [search for subject in subjects for search in
                    (subject, subject + ' haswbstatement:P275=Q6938433')]
        # Q20007257 is CC BY 4.0; metadata still governs eligibility.
        searches.append(subjects[-1] + ' haswbstatement:P275=Q20007257')
        errors, deeper, collected = [], [], []
        seen = set()

        def lookup(search, offset=0):
            key = (search, offset)
            if key not in self.image_search_cache:
                self.image_search_cache[key] = search_commons(search, limit=5, offset=offset)
            rows = self.image_search_cache[key]
            usable = [r for r in rows if reusable_image(r)
                      and not (r.get('width') and r.get('height')
                               and (min(r['width'], r['height']) < 600
                                    or max(r['width'], r['height']) < 1000))]
            for row in usable:
                identity = (row.get('provider', 'commons'), row.get('asset_id') or row.get('download_url')
                            or json.dumps(row, sort_keys=True))
                if identity not in seen:
                    seen.add(identity)
                    collected.append(row)
            return rows, usable

        # Up to seven first-page requests, then five additional pages, never
        # broadening rights. Search operators only narrow discovery; source
        # metadata independently decides eligibility on every returned row.
        for search in searches:
            try:
                rows, usable = lookup(search)
                if len(collected) >= 5:
                    self.image_cache[query] = collected[:5]
                    return collected[:5]
                # The adapter drops unsupported formats, so fewer than five
                # returned images does not mean the API page was exhausted.
                if rows:
                    deeper.append(search)
            except Exception as error:
                errors.append(type(error).__name__)
                if len(errors) >= 2:
                    break
        attempts = 0
        if len(errors) < 2:
            for offset in (5, 10, 15, 20):
                if len(collected) >= 5:
                    break
                for search in list(deeper):
                    if attempts >= 5 or len(errors) >= 2:
                        break
                    attempts += 1
                    try:
                        rows, usable = lookup(search, offset)
                        if len(collected) >= 5:
                            break
                        if not rows:
                            deeper.remove(search)
                    except Exception as error:
                        errors.append(type(error).__name__)
        if collected:
            self.image_cache[query] = collected[:5]
            return collected[:5]
        self.image_cache[query] = []
        print(json.dumps({'stage': 'image_search', 'query': query, 'usable': 0, 'errors': errors}), flush=True)
        return []
