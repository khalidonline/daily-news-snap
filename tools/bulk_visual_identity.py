"""Fail-closed identity resolution for existing local story logos."""

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
import time
from urllib.error import HTTPError
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
_JSON_CACHE = {}
_RETRYABLE_HTTP = frozenset({429, 500, 502, 503, 504})
_WIKIMEDIA_DISAMBIGUATION = "Q4167410"


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


@dataclass(frozen=True)
class LogoResolution:
    """A bounded, machine-readable result from fail-closed discovery."""
    logo: DiscoveredLogo | None
    reason: str
    detail: str = ""


NO_ENTITY_CANDIDATE = "no_entity_candidate"
AMBIGUOUS_ENTITY_CANDIDATES = "ambiguous_entity_candidates"
EXACT_ENTITY_NO_LOGO = "exact_entity_no_logo_property"
MULTIPLE_LOGO_PROPERTIES = "multiple_logo_properties"
LOGO_NO_OFFICIAL_DOMAIN = "logo_without_verified_official_domain"
AMBIGUOUS_OFFICIAL_DOMAINS = "ambiguous_official_domains"
MISSING_CANONICAL_LABEL = "missing_canonical_entity_label"
PERSON_ORG_RELATION_UNRESOLVED = "person_organization_relationship_absent_or_ambiguous"
VERIFIED_IDENTITY = "verified_organization_identity"


def _json_get(url):
    cached = _JSON_CACHE.get(url)
    if cached is not None:
        return cached
    request = Request(url, headers={"User-Agent": "daily-news-snap/1.0 (logo identity resolver)"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
            _JSON_CACHE[url] = payload
            return payload
        except HTTPError as exc:
            if exc.code not in _RETRYABLE_HTTP or attempt == 3:
                raise
            retry_after = (exc.headers or {}).get("Retry-After", "")
            try:
                delay = max(0.0, min(float(retry_after), 30.0))
            except (TypeError, ValueError):
                delay = (2.0, 5.0, 10.0)[attempt]
            time.sleep(delay)
    raise RuntimeError("unreachable retry loop")


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


def _site_domains(entity):
    """Return canonical official-site domains without guessing from a name.

    Wikidata may list regional P856 sites alongside the global site. When one
    or more claims are not scoped by P1001 (applies to jurisdiction), only
    those unscoped claims compete for canonical identity. If every site is
    jurisdiction-scoped, all remain candidates and ambiguity still fails.
    """
    claims = list(entity.get("claims", {}).get("P856", []))
    if not claims:
        return set()
    unscoped = [claim for claim in claims if not claim.get("qualifiers", {}).get("P1001")]
    selected = unscoped or claims
    domains = set()
    for claim in selected:
        site = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not isinstance(site, str) or not site:
            continue
        hostname = (urlparse(site).hostname or "").casefold().rstrip(".")
        if hostname.startswith("www."):
            hostname = hostname[4:]
        if hostname:
            domains.add(hostname)
    return domains


def _logo_from_entity(qid, entity):
    label, aliases = _entity_names(entity)
    logos = _claim_values(entity, "P154")
    domains = _site_domains(entity)
    if not label or len(set(logos)) != 1 or len(domains) != 1:
        return None
    return DiscoveredLogo(
        label, domains.pop(), logos[0],
        f"https://www.wikidata.org/wiki/{qid}", tuple(aliases),
    )


def _entity_logo_resolution(qid, entity):
    """Explain why an exact entity can or cannot supply a verified logo."""
    label, aliases = _entity_names(entity)
    if not label:
        return LogoResolution(None, MISSING_CANONICAL_LABEL, qid)
    logos = set(_claim_values(entity, "P154"))
    if not logos:
        return LogoResolution(None, EXACT_ENTITY_NO_LOGO, qid)
    if len(logos) > 1:
        return LogoResolution(None, MULTIPLE_LOGO_PROPERTIES, qid)
    domains = _site_domains(entity)
    if not domains:
        return LogoResolution(None, LOGO_NO_OFFICIAL_DOMAIN, qid)
    if len(domains) > 1:
        return LogoResolution(None, AMBIGUOUS_OFFICIAL_DOMAINS, qid)
    return LogoResolution(
        DiscoveredLogo(label, next(iter(domains)), next(iter(logos)),
                       f"https://www.wikidata.org/wiki/{qid}", tuple(aliases)),
        VERIFIED_IDENTITY, qid,
    )


def _canonical_entity(qid, json_get):
    """Resolve a Wikidata redirect and reject non-entity disambiguation pages."""
    entities = json_get(WIKIDATA_ENTITY.format(qid=qid)).get("entities", {})
    if len(entities) != 1:
        return None, None
    canonical_qid, entity = next(iter(entities.items()))
    if _WIKIMEDIA_DISAMBIGUATION in _claim_values(entity, "P31"):
        return None, None
    return canonical_qid, entity


def discover_wikidata_logo_for_terms(terms, json_get=_json_get):
    """Find one exact canonical Wikidata identity with logo and official site."""
    wanted = {norm(term) for term in terms if norm(term)}
    qids = set()
    for term in sorted({str(term).strip() for term in terms if str(term).strip()}):
        payload = json_get(WIKIDATA_SEARCH.format(query=quote(term, safe="")))
        for result in payload.get("search", []):
            names = {norm(result.get("label")), *map(norm, result.get("aliases", []))}
            if wanted & names and result.get("id"):
                qids.add(result["id"])

    canonical = {}
    for qid in sorted(qids):
        canonical_qid, entity = _canonical_entity(qid, json_get)
        if not canonical_qid:
            continue
        label, aliases = _entity_names(entity)
        if wanted & {norm(label), *map(norm, aliases)}:
            canonical[canonical_qid] = entity

    # Redirects to the same item are one identity; genuinely distinct exact
    # senses remain ambiguous. Disambiguation pages are navigation, not senses.
    if len(canonical) != 1:
        return None
    qid, entity = next(iter(canonical.items()))
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


def _exact_human_identity(terms, json_get):
    """Return one exact human QID and the declared aliases that name it.

    This is only used when the story line was not explicitly typed with
    ``person:`` metadata. Wikidata P31=Q5 is the structured proof; titles,
    face recognition, capitalization, and name-shape heuristics never count.
    """
    humans = {}
    for term in sorted({str(term).strip() for term in terms if str(term).strip()}):
        qids = _exact_search_qids({term}, json_get)
        canonical_qids = set()
        for qid in qids:
            canonical_qid, entity = _canonical_entity(qid, json_get)
            if not canonical_qid or "Q5" not in _claim_values(entity, "P31"):
                continue
            label, aliases = _entity_names(entity)
            if norm(term) not in {norm(label), *map(norm, aliases)}:
                continue
            canonical_qids.add(canonical_qid)
        if len(canonical_qids) != 1:
            continue
        qid = next(iter(canonical_qids))
        humans.setdefault(qid, set()).add(term)
    if len(humans) != 1:
        return None, set()
    qid, matched_terms = next(iter(humans.items()))
    return qid, matched_terms


def diagnose_verified_logo_identity(story, json_get=_json_get):
    """Resolve an identity and retain a bounded reason when it fails closed."""
    story_key = str(story).strip()
    people = set(sb._STORY_PERSONS.get(story_key) or ())
    declared_terms = set(sb.story_aliases(story)) | people
    direct_matches = {}
    exact_entities = {}
    saw_ambiguous = False
    direct_failures = set()

    # Inspect each explicitly declared term independently. This prevents a
    # biography's person from making its declared company look ambiguous,
    # without ever deriving an organization from prose.
    for term in sorted({str(term).strip() for term in declared_terms if str(term).strip()}):
        canonical = {}
        for qid in sorted(_exact_search_qids({term}, json_get)):
            canonical_qid, entity = _canonical_entity(qid, json_get)
            if not canonical_qid:
                continue
            label, aliases = _entity_names(entity)
            if norm(term) in {norm(label), *map(norm, aliases)}:
                canonical[canonical_qid] = entity
        if len(canonical) > 1:
            saw_ambiguous = True
            continue
        if len(canonical) != 1:
            continue
        qid, entity = next(iter(canonical.items()))
        exact_entities[qid] = entity
        # A person's P154/P856 is not an organization identity. People can
        # reach an organization only through the corroborated relation path.
        if "Q5" in _claim_values(entity, "P31"):
            continue
        resolved = _entity_logo_resolution(qid, entity)
        if resolved.logo:
            logo = resolved.logo
            direct_matches[(logo.domain, logo.commons_filename, logo.source_url)] = logo
        else:
            direct_failures.add(resolved.reason)

    if len(direct_matches) > 1 or saw_ambiguous:
        return LogoResolution(None, AMBIGUOUS_ENTITY_CANDIDATES)
    if len(direct_matches) == 1:
        return LogoResolution(next(iter(direct_matches.values())), VERIFIED_IDENTITY)

    if people:
        person_qids = _exact_search_qids(people, json_get)
        explicit_entities = set(sb.story_aliases(story)) - people
    else:
        detected_qid, detected_terms = _exact_human_identity(declared_terms, json_get)
        person_qids = {detected_qid} if detected_qid else set()
        people = set(detected_terms)
        explicit_entities = set(sb.story_aliases(story)) - people

    approved, _ = sr.approved_runtime_visuals(story)
    approved_names = {path.name for path in approved}
    photo_tags = {
        tag for entry in nb.load_local_images() if entry["path"].name in approved_names
        for tag in entry.get("tags", [])
    }

    if len(person_qids) != 1:
        if person_qids or people:
            return LogoResolution(None, PERSON_ORG_RELATION_UNRESOLVED)
        if len(direct_failures) == 1:
            return LogoResolution(None, next(iter(direct_failures)))
        if len(direct_failures) > 1:
            return LogoResolution(None, AMBIGUOUS_ENTITY_CANDIDATES)
        if exact_entities:
            return LogoResolution(None, EXACT_ENTITY_NO_LOGO)
        return LogoResolution(None, NO_ENTITY_CANDIDATE)
    person_qid = next(iter(person_qids))
    cache = {}

    def full_entity(qid):
        if qid not in cache:
            canonical_qid, entity = _canonical_entity(qid, json_get)
            cache[qid] = entity if canonical_qid else {}
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
        return LogoResolution(None, PERSON_ORG_RELATION_UNRESOLVED)
    org_qid = organizations[0]
    canonical_qid, entity = _canonical_entity(org_qid, json_get)
    if not canonical_qid:
        return LogoResolution(None, PERSON_ORG_RELATION_UNRESOLVED)
    return _entity_logo_resolution(canonical_qid, entity)


def discover_verified_logo_identity(story, json_get=_json_get):
    """Compatibility wrapper returning only a successfully verified logo."""
    return diagnose_verified_logo_identity(story, json_get).logo


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
