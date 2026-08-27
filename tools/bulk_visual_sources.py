"""Strict, metadata-only discovery of story-aware photo candidates.

Discovery is deliberately separate from approval.  These adapters only expose
traceable candidates; validation and the runtime relevance ledger decide what
may count.
"""

from dataclasses import dataclass
from collections import OrderedDict
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

import news_bot as nb
import story_bot as sb


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
LOC_API = "https://www.loc.gov/photos/"
OPENVERSE_API = "https://api.openverse.org/v1/images/"
_GENERIC = {"business", "office", "city", "meeting", "street"}
# One larger response lets irrelevant search hits fall through without turning
# discovery into unbounded pagination.  This is a per-query ceiling, even when
# callers accidentally request a larger candidate limit.
_MAX_SOURCE_RESULTS_PER_QUERY = 48
_DISCOVERY_WINDOW_MULTIPLIER = 4


@dataclass(frozen=True)
class StoryBeat:
    key: str
    queries: tuple[str, ...]
    required_identity: tuple[str, ...]


@dataclass(frozen=True)
class SourceCandidate:
    source: str
    source_id: str
    source_page: str
    direct_url: str
    title: str
    description: str
    creator: str
    license: str
    license_url: str
    width: int
    height: int
    beat_key: str
    matched_on: str
    required_identity: tuple[str, ...]
    depicts: tuple[str, ...] = ()


_JSON_CACHE = OrderedDict()
_TRANSIENT_HTTP = frozenset({429, 500, 502, 503, 504})
_OPENVERSE_DISABLED_UNTIL = 0.0


def _retry_delay(exc, attempt):
    retry_after = getattr(exc, "headers", {}).get("Retry-After") if getattr(exc, "headers", None) else None
    try:
        return min(2.0, max(0.0, float(retry_after)))
    except (TypeError, ValueError):
        return 0.25 * (2 ** attempt)


def _json_get(url, *, attempts=2, sleep=time.sleep):
    """Fetch source JSON once per URL, with only bounded transient retries."""
    if url in _JSON_CACHE:
        _JSON_CACHE.move_to_end(url)
        return _JSON_CACHE[url]
    req = Request(url, headers={"User-Agent": "daily-news-snap/1.0 (visual source discovery; contact: repository maintainers)",
                                "Accept": "application/json"})
    for attempt in range(attempts):
        try:
            with urlopen(req, timeout=15) as response:
                payload = json.load(response)
            _JSON_CACHE[url] = payload
            if len(_JSON_CACHE) > 256:
                _JSON_CACHE.popitem(last=False)
            return payload
        except HTTPError as exc:
            if exc.code not in _TRANSIENT_HTTP or attempt + 1 >= attempts:
                raise
            sleep(_retry_delay(exc, attempt))
        except (TimeoutError, URLError):
            if attempt + 1 >= attempts:
                raise
            sleep(0.25 * (2 ** attempt))


def _html_get(url):
    req = Request(url, headers={"User-Agent": "daily-news-snap/1.0 (first-party discovery)"})
    with urlopen(req, timeout=30) as response:
        return response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")


def _clean(value):
    if isinstance(value, list):
        value = " ".join(map(str, value))
    return unescape(re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def _values(value):
    return value if isinstance(value, (list, tuple)) else ((value,) if value else ())


def _blocked(*values):
    text = " ".join(_clean(value) for value in values)
    return any(pattern.search(text) for pattern in
               (nb._BLOCKED_RE, nb._BLOCKED_AR_RE, nb._ARTWORK_RE, nb._ARTWORK_AR_RE))


def _identities(story):
    sb.load_stories()
    aliases = [str(x).strip() for x in sb.story_aliases(story) if str(x).strip()]
    persons = [str(x).strip() for x in sb._STORY_PERSONS.get(str(story).strip(), ()) if str(x).strip()]
    if not aliases and not persons:
        # Standalone test/manual stories still need an exact, non-generic anchor.
        prefix = str(story).split(":", 1)[0]
        aliases = re.findall(r"[A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+)+", prefix)
    # Both lists are curated declarations.  Keep their spelling and ordering;
    # never replace aliases with identities mined from the story prose.
    return tuple(dict.fromkeys((*persons, *aliases)))


def plan_story_beats(story):
    """Create four deterministic, identity-anchored editorial searches."""
    identities = _identities(story)
    if not identities:
        return []  # fail closed rather than emit generic searches
    exact = str(story).strip()
    is_person = bool(sb._STORY_PERSONS.get(exact)) or (
        not sb.story_logo_domain(exact) and
        any(len(identity.split()) >= 2 for identity in identities) and
        bool(re.search(r"[A-Z][a-z]+\s+[A-Z][a-z]+", exact))
    )
    if is_person:
        keys_terms = (("person", "photograph"), ("early_work", "early career"),
                      ("product_or_company", "work company product"), ("legacy", "legacy"))
    elif sb.story_logo_domain(exact):
        keys_terms = (("origin", "founding origin"), ("early_operation", "early operation"),
                      ("turning_point", "milestone"), ("modern_result", "modern headquarters product"))
    else:
        keys_terms = (("origin_or_early", "history early"), ("subject_detail", "detail"),
                      ("turning_point", "milestone"), ("modern_or_legacy", "modern legacy"))
    aliases = identities[:3]
    beats = []
    for key, terms in keys_terms:
        queries = tuple(f"{identity} {terms}" for identity in aliases
                        if identity.casefold() not in _GENERIC)
        if queries:
            beats.append(StoryBeat(key, queries, identities))
    return beats


def _metadata(meta, key):
    item = meta.get(key, {})
    return _clean(item.get("value", "") if isinstance(item, dict) else item)


def _identity_bearing(beat, title, description, depicts=()):
    """Apply validation's exact metadata identity gate during discovery."""
    # Import locally so source adapters and validation retain their separate
    # responsibilities without maintaining two subtly different matchers.
    from tools.bulk_visual_validate import identity_proven
    probe = SourceCandidate("", "", "", "", title, description, "", "", "",
                            0, 0, beat.key, "", beat.required_identity,
                            tuple(_clean(value) for value in depicts if value))
    return identity_proven(probe)


def _source_window(limit):
    return min(_MAX_SOURCE_RESULTS_PER_QUERY,
               max(0, int(limit)) * _DISCOVERY_WINDOW_MULTIPLIER)


def _report_discovery_skips(telemetry_fn, source, query, skipped, examined):
    if telemetry_fn is not None and skipped:
        telemetry_fn({"kind": "photo", "source": source, "query": query[:240],
                      "result": "DISCOVERY_IDENTITY_SKIPPED",
                      "skipped_count": skipped, "examined_count": examined})


def discover_commons(beat, limit=12, json_get=_json_get, *, excluded_source_ids=(),
                     telemetry_fn=None):
    found = []
    excluded = set(excluded_source_ids)
    for query in beat.queries:
        params = {"action": "query", "format": "json", "generator": "search",
                  "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6,
                  "gsrlimit": _source_window(limit), "prop": "imageinfo", "iiprop": "url|size|extmetadata",
                  # Ask MediaWiki for its documented raster derivative instead
                  # of repeatedly materialising potentially huge originals.
                  "iiurlwidth": 1600}
        payload = json_get(f"{COMMONS_API}?{urlencode(params)}")
        skipped = examined = 0
        for page in list(payload.get("query", {}).get("pages", {}).values())[:_MAX_SOURCE_RESULTS_PER_QUERY]:
            examined += 1
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            title = _clean(page.get("title"))
            desc = _clean(" ".join(filter(None, (_metadata(meta, "ImageDescription"),
                                                   _metadata(meta, "ObjectName"),
                                                   _metadata(meta, "ImageDescriptionValue")))))
            source_id = f"commons:{page.get('pageid')}"
            direct = info.get("thumburl") or info.get("url")
            depicts = tuple(filter(None, (_metadata(meta, "DepictedPeople"), _metadata(meta, "Categories"))))
            if not _identity_bearing(beat, title, desc, depicts):
                skipped += 1
                continue
            if (page.get("pageid") is None or source_id in excluded or
                    any(candidate.source_id == source_id for candidate in found) or
                    not info.get("descriptionurl") or not direct or _blocked(title, desc)):
                continue
            found.append(SourceCandidate("commons", source_id,
                info.get("descriptionurl", ""), direct, title, desc,
                _metadata(meta, "Artist"), _metadata(meta, "LicenseShortName"),
                _metadata(meta, "LicenseUrl"), int(info.get("width") or 0), int(info.get("height") or 0),
                beat.key, query, beat.required_identity, depicts))
            if len(found) >= limit:
                _report_discovery_skips(telemetry_fn, "commons", query, skipped, examined)
                return found
        _report_discovery_skips(telemetry_fn, "commons", query, skipped, examined)
    return found


def discover_loc(beat, limit=12, json_get=_json_get, *, excluded_source_ids=(),
                 telemetry_fn=None):
    found = []
    excluded = set(excluded_source_ids)
    for query in beat.queries:
        payload = json_get(f"{LOC_API}?{urlencode({'fo': 'json', 'q': query, 'c': _source_window(limit)})}")
        skipped = examined = 0
        for item in payload.get("results", [])[:_MAX_SOURCE_RESULTS_PER_QUERY]:
            examined += 1
            title = _clean(item.get("title"))
            desc = _clean(" ".join(str(value or "") for value in
                                    (item.get("description"), item.get("notes"))))
            source_page = str(item.get("id") or "")
            images = item.get("image_url") or []
            direct = images[-1] if isinstance(images, list) and images else ""
            depicts = tuple(_clean(value) for field in
                ("subject", "partof", "location", "names") for value in _values(item.get(field)))
            if not _identity_bearing(beat, title, desc, depicts):
                skipped += 1
                continue
            if not source_page or not direct or _blocked(title, desc, item.get("format")):
                continue
            resource = (item.get("resources") or [{}])[0]
            ident = source_page.rstrip("/").rsplit("/", 1)[-1]
            source_id = f"loc:{ident}"
            if source_id in excluded or any(item.source_id == source_id for item in found):
                continue
            found.append(SourceCandidate("loc", source_id, source_page, direct,
                title, desc, _clean(item.get("contributor")), _clean(item.get("rights")), "",
                int(resource.get("width") or 0), int(resource.get("height") or 0), beat.key, query,
                beat.required_identity, depicts))
            if len(found) >= limit:
                _report_discovery_skips(telemetry_fn, "loc", query, skipped, examined)
                return found
        _report_discovery_skips(telemetry_fn, "loc", query, skipped, examined)
    return found


def discover_openverse(beat, limit=12, json_get=_json_get, *, excluded_source_ids=(),
                       telemetry_fn=None):
    global _OPENVERSE_DISABLED_UNTIL
    if json_get is _json_get and time.monotonic() < _OPENVERSE_DISABLED_UNTIL:
        return []
    found = []
    excluded = set(excluded_source_ids)
    for query in beat.queries:
        try:
            payload = json_get(f"{OPENVERSE_API}?{urlencode({'q': query, 'page_size': _source_window(limit)})}")
        except (HTTPError, URLError, TimeoutError):
            if json_get is _json_get:
                _OPENVERSE_DISABLED_UNTIL = time.monotonic() + 60
            raise
        skipped = examined = 0
        for item in payload.get("results", [])[:_MAX_SOURCE_RESULTS_PER_QUERY]:
            examined += 1
            title, desc = _clean(item.get("title")), _clean(item.get("description"))
            depicts = tuple(tag.get("name", "") for tag in item.get("tags", []) if isinstance(tag, dict))
            if not _identity_bearing(beat, title, desc, depicts):
                skipped += 1
                continue
            if (not item.get("id") or not item.get("url") or
                    not item.get("foreign_landing_url") or
                    _blocked(title, desc, item.get("tags"))):
                continue
            source_id = f"openverse:{item.get('id')}"
            if source_id in excluded or any(candidate.source_id == source_id for candidate in found):
                continue
            found.append(SourceCandidate("openverse", source_id,
                item["foreign_landing_url"], item["url"], title, desc, _clean(item.get("creator")),
                _clean(item.get("license")), str(item.get("license_url") or ""),
                int(item.get("width") or 0), int(item.get("height") or 0), beat.key, query,
                beat.required_identity, depicts))
            if len(found) >= limit:
                _report_discovery_skips(telemetry_fn, "openverse", query, skipped, examined)
                return found
        _report_discovery_skips(telemetry_fn, "openverse", query, skipped, examined)
    return found


class _Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images, self.links, self.title, self._title = [], [], "", False
        self._link_href, self._link_text = "", []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title": self._title = True
        if tag == "img" and attrs.get("src"): self.images.append((attrs["src"], attrs.get("alt", "")))
        if tag == "a" and attrs.get("href"):
            self._link_href, self._link_text = attrs["href"], []
        if tag == "meta" and attrs.get("property", "").casefold() in {"og:image", "twitter:image"} and attrs.get("content"):
            self.images.append((attrs["content"], attrs.get("content", "")))
    def handle_endtag(self, tag):
        if tag == "title": self._title = False
        if tag == "a" and self._link_href:
            self.links.append((self._link_href, _clean(" ".join(self._link_text))))
            self._link_href, self._link_text = "", []
    def handle_data(self, data):
        if self._title: self.title += data
        if self._link_href: self._link_text.append(data)


def discover_first_party(beat, domain, limit=12, *, page_url=None, html_get=_html_get,
                         excluded_source_ids=(), telemetry_fn=None):
    """Discover images referenced by a verified official page, never a naked CDN."""
    domain = (domain or "").casefold().strip().strip(".")
    page_url = page_url or f"https://{domain}/"
    host = (urlparse(page_url).hostname or "").casefold().rstrip(".")
    if not domain or not (host == domain or host.endswith("." + domain)):
        return []
    excluded = set(excluded_source_ids)
    found = []
    pages, queued = [page_url], {page_url}
    for current_page in pages:
        try:
            parser = _Images(); parser.feed(html_get(current_page))
        except (OSError, UnicodeError, ValueError):
            continue
        # Follow a small, deterministic set of official links whose URL carries
        # the requested identity/beat terms. This makes later beats explore
        # actual story pages rather than returning the homepage hero repeatedly.
        terms = _relevance_tokens((*beat.required_identity, *beat.queries, beat.key))
        for raw_link, anchor in parser.links:
            link = urljoin(current_page, raw_link)
            parsed_link = urlparse(link)
            link_host = (parsed_link.hostname or "").casefold()
            # Deliberately exclude the hostname: on nvidia.com it would make
            # the NVIDIA identity token match unrelated links such as /privacy.
            link_terms = _relevance_tokens((parsed_link.path, parsed_link.query, anchor))
            if (link_host == domain or link_host.endswith("." + domain)) and terms & link_terms:
                link = urlunparse(urlparse(link)._replace(fragment=""))
                if link not in queued and len(pages) < 5:
                    queued.add(link); pages.append(link)
        for raw, alt in parser.images:
            direct = urljoin(current_page, raw)
            if urlparse(direct).scheme not in {"http", "https"} or _blocked(direct, parser.title, alt):
                continue
            canonical_direct = urlunparse(urlparse(direct)._replace(fragment=""))
            identity = hashlib.sha256(canonical_direct.encode("utf-8")).hexdigest()[:20]
            source_id = f"first-party:{domain}:{identity}"
            if source_id in excluded or any(item.source_id == source_id for item in found):
                continue
            description = _clean(alt) or "Image referenced by verified official page"
            found.append(SourceCandidate("first-party", source_id, current_page,
                direct, _clean(parser.title), description, domain, "", "", 0, 0,
                beat.key, beat.queries[0] if beat.queries else "", beat.required_identity,
                (_clean(alt),) if _clean(alt) else ()))
            if len(found) >= limit: return found
    return found


def _fold_token(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")


def _relevance_tokens(values):
    tokens = set()
    for value in values:
        for token in _fold_token(value).split("-"):
            if len(token) < 3:
                continue
            # A small normalization makes query "product" match an official
            # /products/... path without introducing fuzzy identity matching.
            tokens.add(token[:-1] if token.endswith("s") and len(token) > 4 else token)
    return tokens
