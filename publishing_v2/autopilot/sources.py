"""Bounded read-only discovery and source retrieval; no model-supplied hosts."""
import hashlib
import json
import re
import unicodedata
import time
from datetime import timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from html import escape, unescape
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree

from publishing_v2.public_images import (search_commons, search_commons_category, search_nasa, download_image,
                                        ImageSourceError, commons_files, commons_subcategories)
from publishing_v2.flickr_images import search_flickr
from publishing_v2.met_images import search_met, OBJECTS
from .credits import attribution_eligible
from publishing_v2.official_images import owner_editorial_use, PROFILES
from publishing_v2.primary_images import ImageMemory, page_images, official_site_images, owner_primary_use, OWNER_DECISION
from publishing_v2.publication import image_publication_eligible
from .feedback import rejected_trigger
from .eligibility import routine_trigger_rejection

FEEDS = ('https://feeds.bbci.co.uk/news/rss.xml',
         'https://feeds.bbci.co.uk/news/technology/rss.xml',
         'https://feeds.bbci.co.uk/sport/rss.xml',
         'https://www.alyaum.com/rssFeed/1005', 'https://aawsat.com/feed')
HOSTS = {'feeds.bbci.co.uk', 'www.bbc.com', 'www.bbc.co.uk', 'bbc.com', 'bbc.co.uk',
         'www.alyaum.com', 'aawsat.com', 'www.aawsat.com', 'en.wikipedia.org', 'ar.wikipedia.org', 'www.wikidata.org'}
OFFICIAL_HOSTS = {'www.spa.gov.sa', 'spa.gov.sa', 'saudipedia.com', 'www.mofa.gov.sa'}
HOSTS |= OFFICIAL_HOSTS
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


def feed_images(item):
    """Photo URLs an RSS item carries itself: enclosure, Media RSS, inline img."""
    media = '{http://search.yahoo.com/mrss/}'
    urls = []
    for tag in ('enclosure', media + 'content', media + 'thumbnail'):
        for node in item.iter(tag):
            kind = node.get('type', '') or node.get('medium', '')
            if tag == 'enclosure' and kind and not kind.startswith('image'):
                continue
            urls.append(node.get('url', ''))
    for field in ('description', '{http://purl.org/rss/1.0/modules/content/}encoded'):
        urls += re.findall(r'<img[^>]+src=["\']([^"\']+)', item.findtext(field, '') or '')
    return [u for u in dict.fromkeys(urls) if u.startswith('https://')][:4]


# Owner 2026-09-26: "be smart, widen the search with several keywords" (SAR had
# trains, stations and a logo on Commons, but a search for its English name
# found almost nothing usable). Widening keys off the Wikidata entity the
# research already resolved, so every extra query still names THIS subject:
# its other names, its Arabic label, its recorded photo and logo, its Commons
# category, and "name + thing" queries from what kind of entity it is.
TYPE_NOUNS = (
    (r'rail|train', ('train', 'station', 'locomotive')),
    (r'airline|airport|aircraft', ('aircraft', 'airport')),
    (r'football|sports club|team', ('stadium', 'team')),
    (r'bank|compan|enterprise|business|corporation|conglomerate', ('headquarters', 'building')),
    (r'city|town|village|capital|region|province', ('skyline', 'street')),
    (r'museum|palace|mosque|building|tower|stadium', ('building', 'interior')),
    (r'university|school|college', ('campus', 'building')),
    (r'port|harbou?r', ('port', 'ship')),
    (r'car|automobile|vehicle', ('car',)),
)


def entity_profile(entity):
    """Names, files and categories a Wikidata entity records for itself."""
    empty = {'names': [], 'files': [], 'categories': [], 'queries': []}
    if not isinstance(entity, str) or not re.fullmatch(r'Q[1-9][0-9]*', entity):
        return empty
    data = wiki_json('https://www.wikidata.org/w/api.php?' + urlencode({
        'action': 'wbgetentities', 'format': 'json', 'ids': entity,
        'props': 'claims|labels|aliases', 'languages': 'en|ar'}))
    item = data.get('entities', {}).get(entity, {})
    claims = item.get('claims', {})
    def values(prop):
        out = []
        for claim in claims.get(prop, []):
            value = claim.get('mainsnak', {}).get('datavalue', {}).get('value')
            if claim.get('rank') != 'deprecated' and value is not None:
                out.append(value)
        return out
    names = [item.get('labels', {}).get(lang, {}).get('value', '') for lang in ('en', 'ar')]
    names += [a.get('value', '') for lang, n in (('en', 4), ('ar', 2))
              for a in item.get('aliases', {}).get(lang, [])[:n]]
    # A bare acronym (SAR, STC) names half the world: Hong Kong SAR, search and rescue.
    names = [n.strip() for n in dict.fromkeys(names) if isinstance(n, str)
             and 4 <= len(n.strip()) <= 80 and not re.fullmatch(r'[A-Z0-9&.\- ]{2,6}', n.strip())]
    kinds = [v.get('id') for v in values('P31') if isinstance(v, dict)][:3]
    kind_words = ''
    if kinds:
        try:
            labels = wiki_json('https://www.wikidata.org/w/api.php?' + urlencode({
                'action': 'wbgetentities', 'format': 'json', 'ids': '|'.join(kinds),
                'props': 'labels', 'languages': 'en'}))
            kind_words = ' '.join(e.get('labels', {}).get('en', {}).get('value', '')
                                  for e in labels.get('entities', {}).values()).casefold()
        except (ValueError, OSError):
            pass
    nouns = next((n for pattern, n in TYPE_NOUNS if re.search(pattern, kind_words)), ())
    english = next((n for n in names if re.search(r'[A-Za-z]', n)), None)
    return {'names': names[:6],
            'files': [v for v in values('P18')[:2] + values('P154')[:1] if isinstance(v, str)],
            'categories': [v for v in values('P373')[:1] if isinstance(v, str)],
            'queries': [english + ' ' + noun for noun in nouns] if english else []}


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


# Alyaum served its RSS feed but answered 403 to the article page itself on
# 2026-09-26 (camels and SAR), so the article photo never reached the photo
# search and SAR died for want of two images. Article pages retry once as a
# browser, the way news_bot has always fetched publishers.
BROWSER_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')


def fetch(url, user_agent='DailyNewsSnap/2.0 (editorial research)'):
    request = Request(safe_url(url), headers={'User-Agent': user_agent})
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


def wiki_json(url):
    """Two bounded read attempts; permanent denial never triggers a retry."""
    for attempt in range(2):
        try:
            result = json.loads(fetch(url))
        except HTTPError as error:
            if attempt or error.code not in {502, 503, 504}:
                raise
        except (URLError, TimeoutError):
            if attempt:
                raise
        else:
            if not isinstance(result, dict):
                raise ValueError('encyclopedia_invalid_response')
            if not result.get('error'):
                return result
            code = str(result['error'].get('code', 'unknown'))
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,50}', code):
                code = 'unknown'
            if attempt or code not in {'maxlag', 'readonly'}:
                raise ValueError('encyclopedia_api_error:' + code)
        time.sleep(1)


# Owner 2026-09-26: the first 10,000 characters are the lead and early history,
# the least surprising part of an article; legacy, business and trivia sit later.
WIKI_TEXT_LIMIT = 24000


def wiki(query, *, language="en", exact_only=False):
    # Query text cannot select arbitrary URLs or redirect retrieval elsewhere.
    query = str(query)[:180]
    if language not in {'en', 'ar'}:
        raise ValueError('unsupported_source_language')
    site = 'https://' + language + '.wikipedia.org/'
    prefix = 'wiki-' if language == 'en' else 'wiki-ar-'
    base = site + 'w/api.php?'
    direct = wiki_json(base + urlencode({'action': 'query', 'format': 'json',
        'titles': query, 'redirects': 1, 'prop': 'extracts|pageprops|extlinks', 'ellimit': 50,
        'explaintext': 1}))
    pages = list(direct.get('query', {}).get('pages', {}).values())
    if len(pages) == 1:
        page = pages[0]
        if (page.get('pageid', -1) > 0 and page.get('extract')
                and 'disambiguation' not in page.get('pageprops', {})):
            return [{'id': prefix + str(page['pageid']),
                'url': site + '?curid=' + str(page['pageid']),
                'text': str(page['extract'])[:WIKI_TEXT_LIMIT], 'title': page['title'],
                'reference_urls': [link.get('*', '') for link in page.get('extlinks', [])],
                'verified_aliases': [query], 'website_entity': page.get('pageprops', {}).get('wikibase_item'), 'source_type': 'encyclopedia'}]
    if exact_only:
        return []
    # Title-constrained recovery prevents a common surname from crowding out
    # the same-named object; resolution still requires source-backed context.
    disambiguation = any('disambiguation' in p.get('pageprops', {}) for p in pages)
    search_query = 'intitle:' + query if disambiguation else query
    search_limit = 5 if disambiguation else 2
    search = wiki_json(base + urlencode({'action': 'query', 'format': 'json',
                        'list': 'search', 'srsearch': search_query, 'srlimit': search_limit}))
    ids = [str(p['pageid']) for p in search.get('query', {}).get('search', [])[:search_limit]]
    if not ids: return []
    # Multiple extracts require exintro; direct exact titles get full history.
    result = wiki_json(base + urlencode({'action': 'query', 'format': 'json',
        'pageids': '|'.join(ids), 'prop': 'extracts|pageprops|extlinks', 'ellimit': 50, 'explaintext': 1,
        'exintro': 1, 'exlimit': len(ids)}))
    return [{'id': prefix + str(page['pageid']), 'url': site + '?curid=' + str(page['pageid']),
             'text': str(page.get('extract', ''))[:WIKI_TEXT_LIMIT], 'title': page.get('title'),
             'reference_urls': [link.get('*', '') for link in page.get('extlinks', [])],
             'source_type': 'encyclopedia', 'website_entity': page.get('pageprops', {}).get('wikibase_item')}
            for page in result.get('query', {}).get('pages', {}).values() if page.get('extract') and 'disambiguation' not in page.get('pageprops', {})]


def official_references(rows):
    """Fetch at most two unique official links actually returned by Wikipedia.

    Domain provenance is not endorsement of every statement. The researcher
    still has to reconcile dates and distinguish decree from effective date.
    """
    result, seen = [], set()
    for row in rows:
        for url in row.get('reference_urls', []):
            try:
                safe_url(url)
                if urlsplit(url).hostname not in OFFICIAL_HOSTS or url in seen:
                    continue
            except (ValueError, TypeError):
                continue
            if len(seen) >= 2:
                return result
            seen.add(url)
            try:
                body = plain(fetch(url).decode('utf-8', errors='replace'))[:4000]
            except (OSError, ValueError):
                continue
            if len(body) >= 12:
                result.append({'id': 'official-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                               'url': url, 'text': body, 'source_type': 'official_reference'})
    return result


def native_subject_name(mention):
    """Use a single quoted name from an already source-validated mention."""
    quoted = re.findall(r'«([^«»]+)»|“([^“”]+)”|"([^"\n]+)"', mention)
    if len(quoted) == 1:
        name = next(part for part in quoted[0] if part).strip()
        if name:
            return name
    return mention.strip()


def reusable_image(row):
    # Metadata from the source adapter, never a model-provided rights assertion.
    return owner_editorial_use(row) or owner_primary_use(row) or attribution_eligible(row) or (row.get('license') in {'Public domain', 'CC0', 'CC0 1.0'}
            and not row.get('restrictions')
            and str(row.get('attribution_required', '')).lower() in {'', 'false', 'no'})


def subject_metadata_matches(subject, row):
    """Cheap subject feasibility only; never a substitute for pixel review."""
    def words(value):
        plain = ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                        if not unicodedata.combining(c))
        return re.findall(r'[^\W_]+', plain, re.UNICODE)
    required = set(words(subject)) - {'the', 'of', 'and'}
    metadata = words(str(row.get('title', '')) + ' ' + str(row.get('description', '')) + ' ' + str(row.get('collection_subject', '')))
    # A passing mention elsewhere in a long caption cannot join unrelated
    # title words into an apparent subject match. Allow short name modifiers.
    window = len(required) + 2
    return bool(required) and any(required.issubset(metadata[i:i + window])
                                  for i in range(len(metadata)))



def resolve_subject(query, rows, *, context=""):
    """Resolve only a unique retrieved title matching the query's main phrase."""
    def normalize(value):
        value = ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                        if not unicodedata.combining(c))
        return re.findall(r'[^\W_]+', value, re.UNICODE)
    wanted = normalize(query)
    matches = {}
    contextual = {}
    stop_words = set(normalize('the of and in for a an في من إلى على عن هو هي أن إن مع أو هذا هذه ذلك التي الذي أول كل وقد كما خلال بعد قبل'))
    context_words = set(normalize(context)) - set(wanted) - stop_words
    for row in rows:
        title = row.get('title')
        if row.get('source_type') != 'encyclopedia' or not title or not row.get('text'):
            continue
        words = normalize(title)
        # Never turn a short ambiguous query into an unrelated longer entity.
        if (any(normalize(alias) == wanted for alias in row.get('verified_aliases', []))
                or words == wanted or (len(words) >= 2 and wanted[:len(words)] == words
                                and len(words) / max(1, len(wanted)) >= 0.6)):
            matches[title] = {'name': title, 'source_id': row['id']}
        # Disambiguate only the SAME base name, using retrieved context.
        # Never shorten arbitrary titles (Michelin Guide != Michelin), nor
        # replace an abstract phrase with a loosely related concrete object.
        parenthetical = re.fullmatch(r'(.+?) \([^()]+\)', title)
        if (parenthetical and normalize(parenthetical[1]) == wanted
                and len(context_words & set(normalize(row['text'][:1200]))) >= 2):
            contextual[title] = {'name': title, 'source_id': row['id']}
    if matches:
        return next(iter(matches.values())) if len(matches) == 1 else None
    return next(iter(contextual.values())) if len(contextual) == 1 else None


class Sources:
    def __init__(self, *, recovery=False, publication_only=False, image_memory=None):
        self.recovery = recovery
        self.publication_only = publication_only
        self.recovery_cache = {}
        self.image_diagnostics = []
        self.image_memory = image_memory or ImageMemory()
        self.article_html = {}
        self.primary_pools = {}
        self.primary_context = {}
        self.subject_entities = {}
        self.image_bytes = {}
        self.publisher_articles = {}
        self.feed_images = {}
        self.entity_profiles = {}
        self.attention_cache = {}
        self.official_image_cache = {}
        self.image_cache = {}
        self.image_search_cache = {}
        self.discovery_rejections = []

    def discover(self, lane, now):
        if lane not in {'daily', 'local'}:
            raise ValueError('invalid_lane')
        # Both lanes need a real attention moment. LOCAL_TOPICS only helps image
        # search; a date-based rotation is not evidence that people care today.
        results, seen = [], set()
        self.discovery_rejections = []
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
                    reason = routine_trigger_rejection(candidate)
                    if reason:
                        self.discovery_rejections.append({'candidate_id': candidate['id'],
                            'source_title': candidate['title'], 'reason': reason})
                        continue
                    body = plain(item.findtext('{http://purl.org/rss/1.0/modules/content/}encoded', '')
                                 or item.findtext('description', ''))
                    publisher = {'id': 'article', 'url': link, 'text': body,
                                 'source_type': 'publisher_feed', 'feed_url': url,
                                 'published_at': published.isoformat()}
                    if attention_source(publisher, candidate):
                        self.publisher_articles[(candidate['id'], link, candidate['published_at'])] = publisher
                    images = feed_images(item)
                    if images:
                        self.feed_images[(candidate['id'], link, candidate['published_at'])] = images
                    results.append(candidate)
                    accepted += 1
                    # Reserve room for later Saudi feeds in the bounded pool.
                    if accepted >= 12:
                        break
            except Exception:
                continue
        return results[:60]

    def attention(self, candidate):
        """Retrieve the trigger once, before encyclopedia or image searches."""
        key = (candidate.get("id"), candidate.get("url"), candidate.get("published_at"))
        if key in self.attention_cache:
            return [dict(row) for row in self.attention_cache[key]]
        rows = []
        if candidate.get('url'):
            try:
                try:
                    raw = fetch(candidate['url'])
                except HTTPError as error:
                    if error.code != 403:
                        raise
                    raw = fetch(candidate['url'], user_agent=BROWSER_UA)
                html = raw.decode('utf-8', errors='replace')
                self.article_html[candidate['url']] = html
                body = plain(html)
                if len(body) > 200:
                    rows.append({'id': 'article', 'url': candidate['url'], 'text': body,
                                 'source_type': 'news_article'})
            except Exception as error:
                print(json.dumps({'stage': 'article_retrieval_failed', 'url': candidate['url'],
                                  'error': type(error).__name__, 'http_status': getattr(error, 'code', None)}), flush=True)
        if candidate.get('url') not in self.article_html:
            # The feed item's own photo is the article's photo: hand it to the
            # same article-image path (publisher allowlist, owner editorial use).
            images = self.feed_images.get((candidate.get('id'), candidate.get('url'),
                                           candidate.get('published_at')), [])
            if images:
                self.article_html[candidate['url']] = ''.join(
                    '<meta property="og:image" content="%s">' % escape(url, quote=True) for url in images)
        if not rows:
            publisher = self.publisher_articles.get((candidate.get('id'), candidate.get('url'),
                                                     candidate.get('published_at')))
            if publisher and attention_source(publisher, candidate):
                rows.append(dict(publisher))
        self.attention_cache[key] = [dict(row) for row in rows]
        return rows

    def research(self, candidate):
        rows = self.attention(candidate)
        editorial = candidate['editorial']
        subjects = editorial.get('subjects')
        if subjects is not None and (not isinstance(subjects, list) or not 1 <= len(subjects) <= 2
                or any(not isinstance(name, str) or not name.strip() or len(name) > 130 for name in subjects)
                or len({name.casefold().strip() for name in subjects}) != len(subjects)):
            raise ValueError('invalid_editorial_subjects')
        candidate.pop('resolved_subjects', None)
        candidate.pop('resolved_subject', None)
        resolved_subjects = []
        candidate['subject_resolution'] = []
        for query in subjects or [editorial['research_query']]:
            retrieval_error = None
            try:
                evidence = wiki(query)
            except Exception as error:
                evidence = []
                retrieval_error = {'error_type': type(error).__name__,
                                   'http_status': getattr(error, 'code', None)}
            resolved = resolve_subject(query, evidence, context=editorial['research_query'])
            resolution_query = query
            if not resolved and editorial.get('subject_evidence'):
                # A native name must be grounded in this source, never invented
                # from an English spelling or borrowed from another candidate.
                try:
                    from .policy import validate_editor_binding
                    validate_editor_binding(candidate)
                    native = next(r['mention'] for r in editorial['subject_evidence'] if r['subject'] == query)
                    # Strip only presentation quotes after validating the original
                    # mention. Resolve ambiguous native names against this news
                    # source, with the same bounded, exact-base-name guards.
                    native = native_subject_name(native)
                    if re.search(r'[\u0600-\u06ff]', native):
                        native_rows = wiki(native, language='ar')
                        native_context = ' '.join(str(candidate.get(k, '')) for k in ('title', 'summary'))
                        native_resolved = resolve_subject(native, native_rows, context=native_context)
                        if native_resolved:
                            evidence, resolved, resolution_query = native_rows, native_resolved, native
                except (ValueError, KeyError, TypeError, StopIteration, OSError):
                    pass
            rows.extend(row for row in evidence if row['id'] not in {r['id'] for r in rows})
            candidate['subject_resolution'].append({'query': query,
                'context': editorial['research_query'], 'resolution_query': resolution_query,
                'retrieved_titles': [r.get('title') for r in evidence],
                'status': 'resolved' if resolved else 'retrieval_failed' if retrieval_error else 'needs_concrete_subject',
                **(retrieval_error or {})})
            if resolved:
                self.subject_entities[resolved['name']] = next((r.get('website_entity') for r in evidence if r['id'] == resolved['source_id']), None)
                resolved_subjects.append(resolved)
            elif subjects is not None:
                raise ValueError('unresolved_editorial_subject')
        rows.extend(official_references(rows))
        rows = [{k: v for k, v in row.items() if k != 'reference_urls'} for row in rows]
        if not rows:
            raise ValueError('no_retrieved_evidence')
        if resolved_subjects:
            candidate['resolved_subject'] = resolved_subjects[0]
            candidate['resolved_subjects'] = resolved_subjects
        return rows

    def prime_images(self, candidate, subject):
        """Reuse the original article; use the exact entity's official website next."""
        if not candidate.get('url') and subject not in self.subject_entities:
            return
        if subject in self.primary_pools and self.primary_context.get(subject) == candidate.get('url'):
            return
        self.primary_context[subject] = candidate.get('url')
        self.recovery_cache.pop((subject, subject), None)
        rows = page_images(self.article_html.get(candidate.get('url'), ''),
                           candidate.get('url', ''), subject, kind='article')
        entity = self.subject_entities.get(subject)
        known_official = any(subject.casefold().strip() in p['aliases'] for p in PROFILES)
        if not known_official and isinstance(entity, str) and re.fullmatch(r'Q[1-9][0-9]*', entity):
            try:
                data = wiki_json('https://www.wikidata.org/w/api.php?' + urlencode({
                    'action':'wbgetclaims','format':'json','entity':entity,'property':'P856'}))
                sites = [r.get('mainsnak', {}).get('datavalue', {}).get('value')
                         for r in data.get('claims', {}).get('P856', []) if r.get('rank') != 'deprecated']
                site = next((u.replace('http://','https://',1) for u in sites
                             if isinstance(u,str) and u.startswith(('https://','http://'))), None)
                if site:
                    rows += official_site_images(site, entity, subject)
            except (ValueError, OSError):
                self.image_diagnostics.append({'stage':'official_site','subject':subject,'status':'unavailable'})
        self.primary_pools[subject] = rows

    def record_visual_feedback(self, candidate, package, review):
        subject = candidate.get('resolved_subject', {}).get('name')
        if not subject:
            return
        for card, check in zip(package.get('cards', []), review.get('card_checks', [])):
            if card.get('kind') != 'credits' and check.get('relevant') is False and card.get('image'):
                self.image_memory.record(subject, card['image'], False)
        self.image_memory.save()

    def official_images(self, subject):
        from publishing_v2.official_images import search_official, PROFILES, official_source_asset, OWNER_USE_DECISION, varied_official_images
        key = subject.casefold().strip()
        profile = next((p for p in PROFILES if key in p['aliases']), None)
        key = profile['newsroom'] if profile else key
        if key not in self.official_image_cache:
            try:
                self.official_image_cache[key] = search_official(subject)
            except (ValueError, OSError, RuntimeError, ImageSourceError) as error:
                self.image_diagnostics.append({'stage': 'official_media', 'subject': subject,
                                               'error': type(error).__name__})
                self.official_image_cache[key] = []
        rows = [dict(row) for row in self.official_image_cache[key]]
        for row in rows:
            if official_source_asset(row):
                row.update(owner_use_decision=OWNER_USE_DECISION,
                           rights_status='owner_accepted_editorial_use', collection_subject=subject)
        return varied_official_images(rows)

    def entity_profile(self, subject):
        entity = self.subject_entities.get(subject)
        if entity not in self.entity_profiles:
            try:
                self.entity_profiles[entity] = entity_profile(entity)
            except (ValueError, OSError, AttributeError, TypeError):
                self.entity_profiles[entity] = entity_profile(None)
        return self.entity_profiles[entity]

    def subject_images(self, query, subject):
        return self.recover_images(query, subject) if self.recovery else self.images(query, subject=subject)

    def recover_images(self, query, subject):
        """Fresh source queries; bounded time/requests; cache metadata, never photos."""
        key = (query, subject)
        if key in self.recovery_cache:
            return self.recovery_cache[key]
        if not isinstance(query, str) or not query.strip() or not isinstance(subject, str) or not subject.strip():
            return []
        deadline = time.monotonic() + 90
        found, identities, hashes, origins = [], set(), set(), set()
        attempts = 0
        profile = self.entity_profile(subject)
        names = [n for n in profile['names'] if n.casefold() != subject.casefold()]
        def entity_rows(rows):
            # Bound to the subject by the entity's own claim or category, not by
            # caption words; the paid pixel check still judges every photo.
            for row in rows:
                row['collection_subject'] = subject
            return rows
        def category_rows(category):
            rows = search_commons_category(category, limit=5)
            for sub in (commons_subcategories(category) if len(rows) < 2 else []):
                rows += search_commons_category(sub, limit=5)
            return entity_rows(rows)
        stages = [('primary_media', lambda: self.primary_pools.get(subject, [])),
                  ('official_media', lambda: self.official_images(subject)),
                  *[('entity_media', lambda: entity_rows(commons_files(profile['files'])))][:bool(profile['files'])],
                  *[('entity_category', lambda c=c: category_rows(c)) for c in profile['categories']],
                  ('commons', lambda: search_commons(query, limit=5)),
                  *[('commons_alias', lambda n=n: search_commons(n, limit=5)) for n in names[:4]],
                  *[('commons_typed', lambda q=q: search_commons(q, limit=5)) for q in profile['queries']],
                  ('commons_collection', lambda: search_commons_category(subject, limit=5)),
                  ('flickr_cc0' if self.publication_only else 'flickr',
                   lambda: search_flickr(subject, limit=5, deadline=deadline,
                          publication_only=self.publication_only,
                          accept_metadata=lambda row: subject_metadata_matches(subject, row))),
                  *([('flickr_attribution',
                   lambda: search_flickr(subject, limit=5, deadline=deadline,
                          publication_only=False,
                          accept_metadata=lambda row: subject_metadata_matches(subject, row)))] if self.publication_only else []),
                  ('met_open_access', lambda: search_met(subject, limit=3, deadline=deadline)),
                  ('commons_page_2', lambda: search_commons(query, limit=5, offset=5)),
                  ('commons_page_3', lambda: search_commons(query, limit=5, offset=10))]
        # Route specialized subjects before general stock catalogs. Primary and
        # entity-bound stages always lead; learned successes rank only the open
        # catalogs behind them.
        head = sum(1 for name, _ in stages if name in {'primary_media', 'official_media', 'entity_media', 'entity_category'})
        if re.search(r'equinox|solstice|space|planet|astronom|اعتدال|فلك', subject, re.I):
            stages.insert(head, ('nasa', lambda: search_nasa(query, limit=5)))
        if OBJECTS.search(subject):
            met = next(pair for pair in stages if pair[0]=='met_open_access')
            stages.remove(met); stages.insert(head, met)
        preferred = self.image_memory.preferred(subject)
        stages = stages[:head] + sorted(stages[head:], key=lambda pair: pair[0].split('_')[0] not in preferred)
        for provider, search in stages:
            if provider not in {'primary_media','official_media'} and len(found) >= 2:
                break
            if len(found) >= 5 or attempts >= 10 or time.monotonic() >= deadline:
                break
            event = {'stage':'image_recovery', 'query':query, 'subject':subject, 'provider':provider,
                     'returned':0, 'accepted':0, 'rejections':{}}
            def reject(reason):
                event['rejections'][reason] = event['rejections'].get(reason, 0) + 1
            try:
                rows = search()
                event['returned'] = len(rows)
                for original in rows:
                    if len(found) >= 5 or attempts >= 10 or time.monotonic() >= deadline:
                        break
                    row = dict(original)
                    if provider == 'nasa':
                        row.update(original_url=row.get('download_url'),owner_use_decision=OWNER_DECISION,
                                   rights_status='owner_accepted_editorial_use')
                    identity = (row.get('provider'), row.get('asset_id'))
                    if identity in identities: continue
                    identities.add(identity)
                    if self.image_memory.rejected(subject, row):
                        reject('previously_rejected_for_subject'); continue
                    if not reusable_image(row):
                        reject('rights'); continue
                    # Review-only images must not consume the public pool or
                    # its download budget before the renderer filters them.
                    if self.publication_only and not image_publication_eligible(row):
                        reject('public_attribution_required'); continue
                    if not subject_metadata_matches(subject, row):
                        if not any(subject_metadata_matches(name, row) for name in names):
                            reject('subject'); continue
                        # Another name of the same entity: keep the row findable
                        # by the subject filters downstream (screen, plan_visuals).
                        row['collection_subject'] = subject
                    dimensions = (row.get('original_width'), row.get('original_height'))
                    if all(type(v) is int and v > 0 for v in dimensions) and (min(dimensions) < 600 or max(dimensions) < 1000):
                        reject('original_too_small'); continue
                    origin = re.search(r'flickr.com/photos/[^/\s]+/([0-9]+)',
                        ' '.join(str(row.get(k, '')) for k in ('source_url', 'credit_line', 'rights_links')))
                    met_origin = re.search(r'https://(?:www\.)?metmuseum\.org/art/collection/(?:search/)?([0-9]+)(?=[/?#\s\"\']|$)',
                        ' '.join(str(row.get(k, '')) for k in ('source_url', 'credit_line', 'rights_links')))
                    # A Commons thumbnail and the museum original remain one
                    # object even when resizing changes the bytes.
                    origin_key = ('met:' + met_origin[1] if met_origin else
                                  'flickr:' + origin[1] if origin else str(row['asset_id']))
                    if origin_key in origins:
                        reject('duplicate_origin'); continue
                    attempts += 1
                    try:
                        raw = download_image(row)
                    except Exception as error:
                        reject('download:' + str(error)[:100]); continue
                    sha = hashlib.sha256(raw).hexdigest()
                    self.image_bytes[row['asset_id']] = raw
                    if sha in hashes:
                        reject('duplicate_bytes'); continue
                    # Copied metadata is retained in the remote package journal;
                    # original image bytes are discarded after this check.
                    row.update(sha256=sha, origin_key=origin_key,
                               image_role=row.get('image_role', 'subject illustration; event date requires review'))
                    found.append(row); hashes.add(sha); origins.add(origin_key)
                    event['accepted'] += 1
            except Exception as error:
                event['error'] = type(error).__name__ + ':' + str(error)[:120]
            self.image_diagnostics.append(event)
            print(json.dumps(event), flush=True)
        self.recovery_cache[key] = found
        return found

    def images(self, query, *, subject=None):
        query = ' '.join(str(query).split())[:130]
        if not query:
            return []
        cache_key = (query, subject) if subject else query
        if cache_key in self.image_cache:
            return self.image_cache[cache_key]
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
                      and (not self.publication_only or image_publication_eligible(r))
                      and (not subject or subject_metadata_matches(subject, r))
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
                    self.image_cache[cache_key] = collected[:5]
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
            self.image_cache[cache_key] = collected[:5]
            return collected[:5]
        self.image_cache[cache_key] = []
        print(json.dumps({'stage': 'image_search', 'query': query, 'usable': 0, 'errors': errors}), flush=True)
        return []
