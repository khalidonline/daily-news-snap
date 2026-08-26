"""Strict, metadata-only discovery of story-aware photo candidates.

Discovery is deliberately separate from approval.  These adapters only expose
traceable candidates; validation and the runtime relevance ledger decide what
may count.
"""

from dataclasses import dataclass
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

import news_bot as nb
import story_bot as sb


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
LOC_API = "https://www.loc.gov/photos/"
OPENVERSE_API = "https://api.openverse.org/v1/images/"
_GENERIC = {"business", "office", "city", "meeting", "street"}


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


def _json_get(url):
    req = Request(url, headers={"User-Agent": "daily-news-snap/1.0 (visual source discovery)"})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def _html_get(url):
    req = Request(url, headers={"User-Agent": "daily-news-snap/1.0 (first-party discovery)"})
    with urlopen(req, timeout=30) as response:
        return response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")


def _clean(value):
    if isinstance(value, list):
        value = " ".join(map(str, value))
    return unescape(re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


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
    return tuple(dict.fromkeys(persons or aliases))


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


def discover_commons(beat, limit=12, json_get=_json_get):
    found = []
    for query in beat.queries:
        params = {"action": "query", "format": "json", "generator": "search",
                  "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6,
                  "gsrlimit": limit, "prop": "imageinfo", "iiprop": "url|size|extmetadata"}
        payload = json_get(f"{COMMONS_API}?{urlencode(params)}")
        for page in payload.get("query", {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            title, desc = _clean(page.get("title")), _metadata(meta, "ImageDescription")
            if (page.get("pageid") is None or not info.get("descriptionurl") or
                    not info.get("url") or _blocked(title, desc)):
                continue
            depicts = tuple(filter(None, (_metadata(meta, "DepictedPeople"), _metadata(meta, "Categories"))))
            found.append(SourceCandidate("commons", f"commons:{page.get('pageid')}",
                info.get("descriptionurl", ""), info["url"], title, desc,
                _metadata(meta, "Artist"), _metadata(meta, "LicenseShortName"),
                _metadata(meta, "LicenseUrl"), int(info.get("width") or 0), int(info.get("height") or 0),
                beat.key, query, beat.required_identity, depicts))
            if len(found) >= limit:
                return found
    return found


def discover_loc(beat, limit=12, json_get=_json_get):
    found = []
    for query in beat.queries:
        payload = json_get(f"{LOC_API}?{urlencode({'fo': 'json', 'q': query, 'c': limit})}")
        for item in payload.get("results", []):
            title, desc = _clean(item.get("title")), _clean(item.get("description"))
            source_page = str(item.get("id") or "")
            images = item.get("image_url") or []
            direct = images[-1] if isinstance(images, list) and images else ""
            if not source_page or not direct or _blocked(title, desc, item.get("format")):
                continue
            resource = (item.get("resources") or [{}])[0]
            ident = source_page.rstrip("/").rsplit("/", 1)[-1]
            found.append(SourceCandidate("loc", f"loc:{ident}", source_page, direct,
                title, desc, _clean(item.get("contributor")), _clean(item.get("rights")), "",
                int(resource.get("width") or 0), int(resource.get("height") or 0), beat.key, query,
                beat.required_identity, tuple(item.get("partof") or ())))
            if len(found) >= limit:
                return found
    return found


def discover_openverse(beat, limit=12, json_get=_json_get):
    found = []
    for query in beat.queries:
        payload = json_get(f"{OPENVERSE_API}?{urlencode({'q': query, 'page_size': limit})}")
        for item in payload.get("results", []):
            title, desc = _clean(item.get("title")), _clean(item.get("description"))
            if (not item.get("id") or not item.get("url") or
                    not item.get("foreign_landing_url") or
                    _blocked(title, desc, item.get("tags"))):
                continue
            found.append(SourceCandidate("openverse", f"openverse:{item.get('id')}",
                item["foreign_landing_url"], item["url"], title, desc, _clean(item.get("creator")),
                _clean(item.get("license")), str(item.get("license_url") or ""),
                int(item.get("width") or 0), int(item.get("height") or 0), beat.key, query,
                beat.required_identity, tuple(tag.get("name", "") for tag in item.get("tags", []) if isinstance(tag, dict))))
            if len(found) >= limit:
                return found
    return found


class _Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls, self.title, self._title = [], "", False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title": self._title = True
        if tag == "img" and attrs.get("src"): self.urls.append(attrs["src"])
        if tag == "meta" and attrs.get("property", "").casefold() in {"og:image", "twitter:image"} and attrs.get("content"):
            self.urls.append(attrs["content"])
    def handle_endtag(self, tag):
        if tag == "title": self._title = False
    def handle_data(self, data):
        if self._title: self.title += data


def discover_first_party(beat, domain, limit=12, *, page_url=None, html_get=_html_get):
    """Discover images referenced by a verified official page, never a naked CDN."""
    domain = (domain or "").casefold().strip().strip(".")
    page_url = page_url or f"https://{domain}/"
    host = (urlparse(page_url).hostname or "").casefold().rstrip(".")
    if not domain or not (host == domain or host.endswith("." + domain)):
        return []
    try:
        parser = _Images(); parser.feed(html_get(page_url))
    except (OSError, UnicodeError, ValueError):
        return []
    found = []
    for raw in dict.fromkeys(parser.urls):
        direct = urljoin(page_url, raw)
        if urlparse(direct).scheme not in {"http", "https"} or _blocked(direct, parser.title):
            continue
        canonical_page = urlunparse(urlparse(page_url)._replace(fragment=""))
        canonical_direct = urlunparse(urlparse(direct)._replace(fragment=""))
        identity = hashlib.sha256(
            f"{canonical_page}\n{canonical_direct}".encode("utf-8")
        ).hexdigest()[:20]
        found.append(SourceCandidate("first-party", f"first-party:{domain}:{identity}", page_url,
            direct, _clean(parser.title), "Image referenced by verified official page", domain, "", "",
            0, 0, beat.key, beat.queries[0] if beat.queries else "", beat.required_identity, ()))
        if len(found) >= limit: break
    return found
