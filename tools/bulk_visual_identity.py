"""Fail-closed identity resolution for existing local story logos."""

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from PIL import Image

import image_precheck as ipc
import news_bot as nb
import story_bot as sb
import story_runtime as sr


LOGO_DIR = Path("images/logos")
LOGO_INDEX = LOGO_DIR / "index.json"
WIKIDATA_SEARCH = "https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&limit=8&search={query}"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql?format=json&query={query}"
COMMONS_IMAGEINFO = "https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=url&iiurlwidth=1024&titles=File:{filename}"


@dataclass(frozen=True)
class LogoIdentity:
    slug: str
    domain: str
    aliases: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class DiscoveredLogo:
    entity_label: str
    domain: str
    commons_filename: str
    source_url: str
    aliases: tuple[str, ...]


def _json_get(url):
    request = Request(url, headers={"User-Agent": "daily-news-snap/1.0 (logo identity resolver)"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def _bytes_get(url):
    request = Request(url, headers={"User-Agent": "daily-news-snap/1.0 (logo downloader)"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def norm(value):
    """Normalize an identity for exact (never substring) comparison."""
    return ipc.normalize(str(value or ""))


def choose_unique_logo_slug(names, index):
    """Return the sole index slug with an exact identity match, if any."""
    wanted = {norm(name) for name in names if norm(name)}
    matches = []
    for slug, aliases in index.items():
        haystack = {norm(slug), *(norm(alias) for alias in aliases)}
        if wanted & haystack:
            matches.append(slug)
    return matches[0] if len(set(matches)) == 1 else None


def story_identity_terms(story):
    """Collect only identities explicitly associated with the story/assets."""
    terms = set(sb.story_aliases(story))
    terms.update(sb._STORY_PERSONS.get(str(story).strip()) or [])
    approved, _ = sr.approved_runtime_visuals(story)
    approved_names = {path.name for path in approved}
    for entry in nb.load_local_images():
        if entry["path"].name in approved_names:
            terms.update(entry.get("tags", []))
    return {term for term in terms if str(term).strip()}


def resolve_existing_logo_identity(story, index_path=LOGO_INDEX):
    """Resolve a declared or uniquely indexed identity with a local logo.

    Missing/malformed indexes, ambiguous aliases, and absent local files all
    return ``None``. No domain is ever inferred from a partial or loose term.
    """
    domain = sb.story_logo_domain(story)
    if domain and (LOGO_DIR / f"{domain}-current.png").exists():
        return LogoIdentity(
            domain,
            domain,
            (domain,),
            "declared-domain-local-file",
        )

    try:
        index = json.loads(Path(index_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(index, dict):
        return None

    slug = choose_unique_logo_slug(story_identity_terms(story), index)
    if not slug or not list(LOGO_DIR.glob(f"{slug}-*.png")):
        return None
    aliases = index.get(slug, [])
    if not isinstance(aliases, list):
        return None
    return LogoIdentity(
        slug,
        slug if "." in slug else "",
        tuple(aliases),
        "unique-local-logo-alias",
    )


def _claim_values(entity, prop):
    values = []
    for claim in entity.get("claims", {}).get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict):
            value = value.get("id")
        if isinstance(value, str) and value:
            values.append(value)
    return values


def _entity_names(entity):
    label = entity.get("labels", {}).get("en", {}).get("value", "")
    aliases = tuple(
        item.get("value", "") for item in entity.get("aliases", {}).get("en", [])
        if item.get("value")
    )
    return label, aliases


def _logo_from_entity(qid, entity):
    label, aliases = _entity_names(entity)
    logos = _claim_values(entity, "P154")
    sites = _claim_values(entity, "P856")
    if not label or len(set(logos)) != 1 or not sites:
        return None
    domains = set()
    for site in sites:
        hostname = (urlparse(site).hostname or "").casefold().rstrip(".")
        if hostname.startswith("www."):
            hostname = hostname[4:]
        if hostname:
            domains.add(hostname)
    if len(domains) != 1:
        return None
    return DiscoveredLogo(
        label, domains.pop(), logos[0],
        f"https://www.wikidata.org/wiki/{qid}", tuple(aliases),
    )


def discover_wikidata_logo_for_terms(terms, json_get=_json_get):
    """Find one exact Wikidata identity carrying both a logo and official site."""
    wanted = {norm(term) for term in terms if norm(term)}
    qids = set()
    for term in sorted({str(term).strip() for term in terms if str(term).strip()}):
        payload = json_get(WIKIDATA_SEARCH.format(query=quote(term, safe="")))
        for result in payload.get("search", []):
            names = {norm(result.get("label")), *map(norm, result.get("aliases", []))}
            if wanted & names and result.get("id"):
                qids.add(result["id"])
    # Multiple exact senses are ambiguous even if only one happens to have a logo.
    if len(qids) != 1:
        return None
    qid = next(iter(qids))
    entity = json_get(WIKIDATA_ENTITY.format(qid=qid)).get("entities", {}).get(qid, {})
    label, aliases = _entity_names(entity)
    if not wanted & {norm(label), *map(norm, aliases)}:
        return None
    return _logo_from_entity(qid, entity)


def corroborated_org_qids(person_qid, explicit_entity_terms, approved_photo_tags,
                           entity_get, sparql_get):
    """Return relation-linked organizations also named by explicit story evidence."""
    person = entity_get(person_qid)
    candidates = set(person.get("P108", []))
    candidates.update(sparql_get("P112", person_qid))
    candidates.update(sparql_get("P169", person_qid))
    wanted = {norm(value) for value in (*explicit_entity_terms, *approved_photo_tags) if norm(value)}
    kept = []
    for qid in sorted(candidates):
        entity = entity_get(qid)
        names = {norm(entity.get("label")), *map(norm, entity.get("aliases", []))}
        if wanted & names:
            kept.append(qid)
    return kept


def discover_verified_logo_identity(story, json_get=_json_get):
    """Resolve a direct entity or one uniquely corroborated person relation."""
    key = str(story).strip()
    people = set(sb._STORY_PERSONS.get(key) or ())
    # Direct identity discovery is restricted to declared story metadata.
    # Approved-photo tags are contextual corroboration, not logo identities.
    declared_terms = set(sb.story_aliases(story)) | people
    direct = discover_wikidata_logo_for_terms(declared_terms, json_get)
    if direct:
        return direct

    explicit_entities = set(sb.story_aliases(story)) - people
    approved, _ = sr.approved_runtime_visuals(story)
    approved_names = {path.name for path in approved}
    photo_tags = {
        tag for entry in nb.load_local_images() if entry["path"].name in approved_names
        for tag in entry.get("tags", [])
    }

    person_qids = _exact_search_qids(people, json_get)
    if len(person_qids) != 1:
        return None
    person_qid = next(iter(person_qids))
    cache = {}

    def full_entity(qid):
        if qid not in cache:
            cache[qid] = json_get(WIKIDATA_ENTITY.format(qid=qid)).get("entities", {}).get(qid, {})
        return cache[qid]

    def simple_entity(qid):
        entity = full_entity(qid)
        label, aliases = _entity_names(entity)
        return {"label": label, "aliases": list(aliases), "P108": _claim_values(entity, "P108")}

    def relation_qids(prop, qid):
        query = f"SELECT ?org WHERE {{ ?org wdt:{prop} wd:{qid}. }}"
        payload = json_get(WIKIDATA_SPARQL.format(query=quote(query, safe="")))
        return [
            row.get("org", {}).get("value", "").rsplit("/", 1)[-1]
            for row in payload.get("results", {}).get("bindings", [])
            if row.get("org", {}).get("value")
        ]

    organizations = corroborated_org_qids(
        person_qid, explicit_entities, photo_tags, simple_entity, relation_qids,
    )
    if len(organizations) != 1:
        return None
    return _logo_from_entity(organizations[0], full_entity(organizations[0]))


def _exact_search_qids(terms, json_get):
    wanted = {norm(term) for term in terms if norm(term)}
    qids = set()
    for term in sorted({str(term).strip() for term in terms if str(term).strip()}):
        payload = json_get(WIKIDATA_SEARCH.format(query=quote(term, safe="")))
        for result in payload.get("search", []):
            names = {norm(result.get("label")), *map(norm, result.get("aliases", []))}
            if wanted & names and result.get("id"):
                qids.add(result["id"])
    return qids


def download_commons_logo(filename, entity_label, destination,
                          json_get=_json_get, bytes_get=_bytes_get):
    """Download a Commons P154 as a guarded PNG, preferring raster thumbnails."""
    info_url = COMMONS_IMAGEINFO.format(filename=quote(filename, safe=""))
    pages = json_get(info_url).get("query", {}).get("pages", {})
    infos = [info for page in pages.values() for info in page.get("imageinfo", [])]
    if len(infos) != 1:
        return None
    source_url = infos[0].get("thumburl") or infos[0].get("url")
    if not source_url:
        return None
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".png", delete=False) as temp:
            temp_name = Path(temp.name)
            temp.write(bytes_get(source_url))
        # Decode completely, then normalize all formats to a local raster PNG.
        with Image.open(temp_name) as image:
            image.load()
            image.convert("RGBA").save(temp_name, format="PNG")
        reason = ipc.guard_render(ipc.Candidate(path=str(temp_name), caption=entity_label, slot="logo"))
        if reason:
            return None
        temp_name.replace(destination)
        temp_name = None
        return destination
    except (OSError, ValueError):
        return None
    finally:
        if temp_name is not None:
            temp_name.unlink(missing_ok=True)
