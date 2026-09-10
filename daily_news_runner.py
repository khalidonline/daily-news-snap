"""Daily entrypoint that applies the Saudi Snapchat editorial policy.

The legacy ``news_bot`` module continues to own rendering, provider fetchers,
publishing, retry behavior, and posted-story memory. This runner swaps in the
Saudi-audience feed/ranking prompt and, in ``auto`` image mode, compares the
approved provider candidates by visual relevance before returning one to the
legacy renderer.
"""

import base64
import hashlib
import io
import json
import os
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

from news_visual_recovery import exact_logo_for_targets, normalize_visual_targets

from PIL import Image

from news_editorial import (
    DEFAULT_LOOKBACK_HOURS,
    SYSTEM_PROMPT,
    audience_fit_eligible,
    balanced_shortlist,
    decorate_model_items,
    fetch_headlines,
    hard_scope_eligible,
    shortlist_lane_counts,
)

LANE_ORDER = (
    "business_tech",
    "saudi_core",
    "sports",
    "entertainment_culture",
    "travel_lifestyle",
)

SUPPORTED_IMAGE_SOURCES = {
    "auto", "article", "spa", "commons", "loc", "openverse", "stock", "none"
}

AUTO_IMAGE_REQUIRED_ATTRS = (
    "fetch_local_photo",
    "fetch_article_photo",
    "fetch_spa_photo",
    "fetch_commons_photo",
    "fetch_loc_photo",
    "fetch_openverse_photo",
    "fetch_photo",
    "photo_shows",
)

_IMAGE_MARKERS = (
    ".exempt", ".generated", ".recentkeep", ".commons-title",
    ".official-subject",
)
_NEUTRAL_PRIORITY = {
    "article": 0,
    "commons": 1,
    "spa": 2,
    "local": 3,
    "openverse": 4,
    "loc": 5,
    "stock": 6,
}
_STORY_CONTEXTS = {}
_LOGOS_DIR = Path("images/logos")
_LOGOS_INDEX = _LOGOS_DIR / "index.json"

_PRODUCT_CLASS_WORDS = {
    "android", "camera", "fold", "foldable", "galaxy", "iphone", "ipad",
    "macbook", "mix", "model", "phone", "pixel", "playstation", "pro",
    "series", "smartphone", "ultra", "watch", "xbox",
}
_NUMBERED_PRODUCT_WORDS = _PRODUCT_CLASS_WORDS | {
    "apple", "google", "honor", "huawei", "meta", "oneplus", "oppo",
    "samsung", "xiaomi",
}
_OPENVERSE_NEUTRAL_DIGITAL_SUBJECTS = {
    "ai", "anthropic", "app", "application", "artificial", "claude",
    "intelligence", "meta", "muse", "openai", "platform", "software",
}

SNAPCHAT_SIGNALS = frozenset({
    "saudi_relevance",
    "surprise",
    "practical_impact",
    "human_interest",
    "shareability",
    "visual_strength",
})
MIN_SNAPCHAT_SCORE = 6
MIN_SNAPCHAT_SIGNALS = 2

# Cross-run mix guard. Sports remains a valid lane, but after one sports card
# the next three selected cards should come from other lanes when at least one
# valid alternative can be illustrated. This prevents famous club/player names
# from dominating repeated review runs without banning genuinely major sports.
SPORTS_BALANCE_WINDOW = 3
_SPORTS_MEMORY_AR_TOKENS = {
    "رونالدو", "ميسي", "نيمار", "ليفربول", "برشلونة",
    "دوري", "بطولة", "مباراة", "مباريات", "كأس", "هداف", "أهداف",
    "لاعب", "مدرب", "خماسية", "يتأهل", "تأهل",
}
_SPORTS_MEMORY_PHRASE_RE = re.compile(
    r"(?:ريال مدريد|مانشستر سيتي|مانشستر يونايتد|باريس سان جيرمان|"
    r"\b(?:ronaldo|messi|neymar|liverpool|real madrid|barcelona|"
    r"manchester (?:city|united)|paris saint-germain|football|soccer|"
    r"league|cup|match|goal|player|coach|transfer|champion)\b)",
    re.IGNORECASE,
)
_SPORTS_MEMORY_HILAL_CONTEXT_TOKENS = {
    "صفقة", "موسم", "نادي", "يسجل", "سجل", "يفوز", "فوز", "يخسر",
    "خسارة", "تعادل", "تعاقد", "انتقال", "لاعب", "مدرب", "دوري",
    "مباراة", "بطولة", "كأس", "هداف", "أهداف", "خماسية",
}

_DEDUPE_TOKEN_RE = re.compile(r"[A-Za-z0-9\u0600-\u06ff]+")
_ARABIC_DIACRITICS_RE = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06edـ]")
_FIRST_CLAIM_RE = re.compile(
    r"(?<![\w])(?:أول|الأول|أولى|الأولى|لأول\s+مرة|first)(?![\w])",
    re.IGNORECASE,
)
_ARABIC_NORMALIZATION = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي",
})
_DEDUPE_STOPWORDS = {
    "الى", "إلى", "على", "عن", "في", "من", "مع", "بعد", "قبل", "بين",
    "هذا", "هذه", "ذلك", "تلك", "الذي", "التي", "حول", "ضمن", "عبر",
    "اليوم", "جديد", "جديدة", "خبر", "اخبار", "أخبار", "السعودية", "المملكة",
    "شركة", "وزارة", "هيئة", "مليون", "مليار", "ريال", "دولار",
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "new", "news", "saudi", "arabia", "company", "million", "billion",
}


def normalize_image_source(value):
    value = (value or "").strip().lower()
    if value == "pexels":
        value = "stock"
    return value if value in SUPPORTED_IMAGE_SOURCES else "auto"


def _query_key(values):
    if isinstance(values, str):
        values = [values]
    return tuple(
        str(value).strip().casefold()
        for value in (values or [])
        if str(value).strip()
    )


def _numbered_product_request(query_text):
    query_tokens = re.findall(r"[A-Za-z0-9]+", str(query_text).casefold())
    return {
        token for index, token in enumerate(query_tokens)
        if token.isdigit() and len(token) <= 3 and any(
            query_tokens[nearby] in _NUMBERED_PRODUCT_WORDS
            for nearby in range(max(0, index - 1), min(len(query_tokens), index + 2))
            if nearby != index
        )
    }


def _commons_misses_numbered_product_model(query_text, commons_title):
    """True when a product photo omits the requested numbered model."""
    requested = _numbered_product_request(query_text)
    if not requested:
        return False
    title_tokens = re.findall(r"[A-Za-z0-9]+", str(commons_title).casefold())
    if not set(title_tokens).intersection(_PRODUCT_CLASS_WORDS):
        # A company headquarters or launch venue can still be relevant context.
        return False
    title_numbers = {token for token in title_tokens if token.isdigit()
                     and len(token) <= 3}
    return not requested.issubset(title_numbers)


def _story_context_key(story):
    return (
        _query_key(story.get("image_queries", [])),
        _query_key(story.get("image_queries_ar", [])),
    )


def _story_context_text(story):
    return "\n".join(
        str(value).strip()
        for value in (
            story.get("headline", ""),
            story.get("summary", ""),
            story.get("takeaway", ""),
        )
        if str(value).strip()
    )


def remember_story_contexts(result):
    """Remember complete ranked stories for the automatic image search."""
    _STORY_CONTEXTS.clear()
    for story in (result or {}).get("stories", []):
        if not isinstance(story, dict):
            continue
        key = _story_context_key(story)
        if not any(key):
            continue
        if _story_context_text(story):
            remembered = dict(story)
            remembered["visual_targets"] = normalize_visual_targets(story)
            _STORY_CONTEXTS[key] = remembered
    return result


def _story_for_queries(queries_en, queries_ar):
    key = (_query_key(queries_en), _query_key(queries_ar))
    return _STORY_CONTEXTS.get(key)


def _context_for_queries(queries_en, queries_ar):
    story = _story_for_queries(queries_en, queries_ar)
    if story:
        return _story_context_text(story)
    key = (_query_key(queries_en), _query_key(queries_ar))
    fallback = list(key[0]) + list(key[1])
    return "\n".join(fallback)


def _model_story_scope_item(story, source_item):
    """Project model-written card text back into the source item's policy lane."""
    candidate = dict(source_item)
    candidate["title"] = str(story.get("headline", "") or "").strip()
    candidate["summary"] = " ".join(
        str(story.get(field, "") or "").strip()
        for field in ("summary", "takeaway")
        if str(story.get(field, "") or "").strip()
    )
    return candidate


def _introduces_unsupported_first_claim(story, source_item):
    """Reject a first-ever claim introduced by the generated headline."""
    headline = str(story.get("headline", "") or "")
    source_title = str(source_item.get("title", "") or "")
    return bool(
        _FIRST_CLAIM_RE.search(headline)
        and not _FIRST_CLAIM_RE.search(source_title)
    )


def validate_ranked_result(result, shortlist):
    """Remove model-ranked stories that violate hard editorial boundaries.

    The model refers to the numbered shortlist with a 1-based integer ``item``.
    Both the exact source item and the model-written card text must independently
    pass the deterministic scope gates. This prevents an ambiguous source item
    from being rewritten into health advice, rumor, politics, or other material
    that the daily brief explicitly excludes.
    """
    if not isinstance(result, dict):
        return result
    stories = result.get("stories")
    if not isinstance(stories, list):
        return result

    kept = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        item_no = story.get("item")
        if isinstance(item_no, bool) or not isinstance(item_no, int):
            continue
        if item_no < 1 or item_no > len(shortlist):
            continue
        source_item = shortlist[item_no - 1]
        if _introduces_unsupported_first_claim(story, source_item):
            continue
        if not hard_scope_eligible(source_item):
            continue
        if not audience_fit_eligible(source_item):
            continue
        card_item = _model_story_scope_item(story, source_item)
        if not hard_scope_eligible(card_item):
            continue
        if not audience_fit_eligible(card_item):
            continue
        kept.append(story)

    validated = dict(result)
    validated["stories"] = kept
    if len(kept) != len(stories):
        print(f"    post-model scope gate: kept {len(kept)}/{len(stories)} ranked stories")
    return validated


def enforce_snapchat_selection_gate(result):
    """Keep only stories with explicit evidence of Snapchat audience value."""
    if not isinstance(result, dict):
        return result
    stories = result.get("stories")
    if not isinstance(stories, list):
        return result

    kept = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        score = story.get("snap_score")
        signals = story.get("snap_signals")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            continue
        if not isinstance(signals, list):
            continue
        recognized = {
            signal for signal in signals
            if isinstance(signal, str) and signal in SNAPCHAT_SIGNALS
        }
        if (
            MIN_SNAPCHAT_SCORE <= score <= 10
            and len(recognized) >= MIN_SNAPCHAT_SIGNALS
        ):
            kept.append(story)

    gated = dict(result)
    gated["stories"] = kept
    if len(kept) != len(stories):
        print(f"    Snapchat selection gate: kept {len(kept)}/{len(stories)} stories")
    return gated


def _story_lane(story, shortlist):
    """Return the deterministic source lane for one ranked model story."""
    if not isinstance(story, dict):
        return ""
    item_no = story.get("item")
    if isinstance(item_no, bool) or not isinstance(item_no, int):
        return ""
    if item_no < 1 or item_no > len(shortlist):
        return ""
    return str(shortlist[item_no - 1].get("lane", "business_tech") or "")


def _legacy_headline_is_sports(headline):
    """Conservative fallback for old posted-state rows that lack a lane.

    New rows persist the exact editorial lane. The text fallback only needs to
    bridge the existing 3-day memory, so use exact Arabic tokens and specific
    sports names/phrases. Avoid generic substrings such as هدف/نهائي because
    they also appear in ordinary business and government headlines.
    """
    text = str(headline or "").strip()
    if not text:
        return False
    if _SPORTS_MEMORY_PHRASE_RE.search(text):
        return True
    normalized = _ARABIC_DIACRITICS_RE.sub("", text).translate(
        _ARABIC_NORMALIZATION
    )
    tokens = set(_DEDUPE_TOKEN_RE.findall(normalized))
    if tokens & _SPORTS_MEMORY_AR_TOKENS:
        return True
    if "الهلال" in tokens and "الاحمر" not in tokens:
        return bool(tokens & _SPORTS_MEMORY_HILAL_CONTEXT_TOKENS)
    return False


def _posted_story_lane(entry):
    if not isinstance(entry, dict):
        return ""
    lane = str(entry.get("lane", "") or "").strip()
    if lane in LANE_ORDER:
        return lane
    if _legacy_headline_is_sports(entry.get("headline", "")):
        return "sports"
    return ""


def _recent_sports_card(posted, window=SPORTS_BALANCE_WINDOW):
    recent = [entry for entry in (posted or []) if isinstance(entry, dict)][-window:]
    return any(_posted_story_lane(entry) == "sports" for entry in recent)


def rebalance_ranked_result(result, shortlist, posted):
    """Keep sports to at most one selected card in a rolling four-card window.

    The model still decides quality within each lane. When a sports card exists
    among the previous three outputs, stable-partition the already validated
    ranking so every valid non-sports alternative is tried for imagery before
    another sports story. If no non-sports alternative can ultimately render,
    sports remains available as the fallback rather than causing a dead run.
    """
    if not isinstance(result, dict):
        return result
    stories = result.get("stories")
    if not isinstance(stories, list):
        return result

    annotated = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        copy = dict(story)
        lane = _story_lane(copy, shortlist)
        if lane:
            copy["_editorial_lane"] = lane
        annotated.append(copy)

    balanced = dict(result)
    balanced["stories"] = annotated
    if not _recent_sports_card(posted):
        return balanced

    non_sports = [s for s in annotated if s.get("_editorial_lane") != "sports"]
    sports = [s for s in annotated if s.get("_editorial_lane") == "sports"]
    if not non_sports or not sports:
        return balanced

    reordered = non_sports + sports
    if reordered != annotated:
        print(
            "    sports balance: a sports card appeared in the previous "
            f"{SPORTS_BALANCE_WINDOW} outputs — trying {len(non_sports)} "
            "non-sports alternative(s) first"
        )
        balanced["stories"] = reordered
    return balanced


def _normalize_source_link(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urllib.parse.urlsplit(raw)
    except ValueError:
        return raw
    if not parts.netloc:
        return raw.rstrip("/")
    host = parts.netloc.casefold()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/")
    tracking_keys = {"ref", "source", "fbclid", "gclid"}
    query_pairs = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(
            parts.query, keep_blank_values=True
        )
        if key.casefold() not in tracking_keys
        and not key.casefold().startswith("utm_")
    ]
    query = urllib.parse.urlencode(query_pairs, doseq=True)
    return urllib.parse.urlunsplit(("https", host, path, query, ""))


def _normalize_dedupe_token(token):
    # Arabic commonly attaches conjunctions/prepositions to the noun.
    # Normalize only the high-confidence forms around the definite article
    # so "للنصر", "والنصر" and "بالنصر" compare as "النصر".
    if len(token) > 5 and token[0] in {"و", "ف"} and token[1:3] == "لل":
        token = token[1:]
    if token.startswith("لل") and len(token) > 4:
        return "ال" + token[2:]
    if len(token) > 4 and token[:3] in {"وال", "فال", "بال", "كال"}:
        return token[1:]
    return token


def _dedupe_tokens(text):
    normalized = _ARABIC_DIACRITICS_RE.sub("", str(text or ""))
    normalized = normalized.translate(_ARABIC_NORMALIZATION).casefold()
    tokens = set()
    for token in _DEDUPE_TOKEN_RE.findall(normalized):
        token = _normalize_dedupe_token(token)
        if len(token) < 3 or token in _DEDUPE_STOPWORDS:
            continue
        tokens.add(token)
    return tokens


def _same_recent_event(candidate_title, remembered_title):
    candidate = _dedupe_tokens(candidate_title)
    remembered = _dedupe_tokens(remembered_title)
    if not candidate or not remembered:
        return False
    shared = candidate & remembered
    if len(shared) < 3:
        return False
    return len(shared) / min(len(candidate), len(remembered)) >= 0.40


def filter_recent_source_duplicates(items, posted):
    """Remove already-covered source stories before they consume model slots.

    New memory entries carry a canonical source URL, which is the strongest
    identity. Older entries have only the AI-written headline, so retain a
    conservative three-token event-overlap fallback to protect existing state
    (including the Ronaldo record story) without blocking unrelated news about
    the same person or company.
    """
    recent = [entry for entry in (posted or []) if isinstance(entry, dict)]
    recent_links = set()
    legacy_headlines = []
    for entry in recent:
        remembered_link = _normalize_source_link(entry.get("source_link"))
        if remembered_link:
            recent_links.add(remembered_link)
        elif str(entry.get("headline", "") or "").strip():
            legacy_headlines.append(entry.get("headline", ""))
    kept = []
    removed = 0
    for item in items:
        link = _normalize_source_link(item.get("link"))
        if link and link in recent_links:
            removed += 1
            continue
        title = str(item.get("title", "") or "").strip()
        if title and any(
            _same_recent_event(title, headline)
            for headline in legacy_headlines
        ):
            removed += 1
            continue
        kept.append(item)
    if removed:
        print(f"    source dedupe: removed {removed} recently covered candidate(s)")
    return kept


def make_source_aware_save_posted(news_bot_module):
    """Preserve legacy state format while adding stable source identity."""
    original_save = news_bot_module.save_posted

    def _save(previous, stories):
        path = Path(original_save(previous, stories))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return path
        if not isinstance(data, list):
            return path

        start = max(0, len(data) - len(stories))
        changed = False
        for entry, story in zip(data[start:], stories):
            if not isinstance(entry, dict) or not isinstance(story, dict):
                continue
            link = _normalize_source_link(story.get("link"))
            if link and entry.get("source_link") != link:
                entry["source_link"] = link
                changed = True
            lane = str(story.get("_editorial_lane", "") or "").strip()
            if lane in LANE_ORDER and entry.get("lane") != lane:
                entry["lane"] = lane
                changed = True
        if changed:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        return path

    return _save


def _can_install_auto_image_selector(news_bot_module):
    return all(hasattr(news_bot_module, name) for name in AUTO_IMAGE_REQUIRED_ATTRS)


def make_fetcher(news_bot_module):
    def _fetch():
        items = fetch_headlines(
            news_bot_module._http_get,
            news_bot_module._clean,
            news_bot_module._parse_date,
            lookback_hours=news_bot_module.LOOKBACK_HOURS,
        )
        load_posted = getattr(news_bot_module, "load_posted", None)
        posted = load_posted() if callable(load_posted) else []
        return filter_recent_source_duplicates(items, posted)
    return _fetch


def cached_news_editorial(bot, generate):
    """Reuse identical feed requests within a scheduled slot, before revalidation.

    Feed content, posted history, policy, model and slot are all part of the
    identity. Pinned events always need fresh verification. Failed or empty
    responses are never retained. Visual checks remain outside this cache.
    """
    def summarize(items, already_posted=(), pinned=""):
        root = os.getenv("NEWS_EDITORIAL_CACHE_DIR", "").strip()
        slot = os.getenv("SCHEDULE_SLOT_ID", "").strip()
        if not root or not slot or pinned:
            return generate(items, already_posted, pinned)
        material = json.dumps({
            "schema": 1, "slot": slot, "items": items,
            "posted": list(already_posted), "prompt": bot.SYSTEM_PROMPT,
            "model": bot.CLAUDE_MODEL, "candidates": bot.CANDIDATES,
        }, ensure_ascii=False, sort_keys=True)
        key = hashlib.sha256(material.encode("utf-8")).hexdigest()
        path = Path(root) / (key + ".json")
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and isinstance(cached.get("stories"), list) and cached["stories"]:
                print("    editorial request cache hit — revalidating saved result")
                return cached
        except (OSError, ValueError, UnicodeError):
            pass
        result = generate(items, already_posted, pinned)
        if isinstance(result, dict) and isinstance(result.get("stories"), list) and result["stories"]:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_suffix(".tmp")
                temp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                temp.replace(path)
            except OSError:
                print("    editorial cache unavailable — continuing with paid result")
        return result
    return summarize


def make_summarizer(news_bot_module):
    original_summarize = news_bot_module.summarize

    def _summarize(items, already_posted=(), pinned=""):
        encoded_recovery = os.getenv("NEWS_RECOVERY_STORY_B64", "").strip()
        if encoded_recovery:
            try:
                story = json.loads(base64.b64decode(encoded_recovery).decode("utf-8"))
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("invalid exact News recovery payload") from exc
            required = ("headline", "summary", "takeaway", "link")
            if not isinstance(story, dict) or any(not story.get(k) for k in required):
                raise ValueError("exact News recovery payload is missing required fields")
            print("    exact News recovery: preserving original story copy")
            return remember_story_contexts({"stories": [story]})

        if pinned:
            # Pinned events keep the original verified-search path. Remembering
            # the returned context is harmless and keeps image behavior coherent
            # if this runner is ever used with a pinned event.
            return remember_story_contexts(
                original_summarize(items, already_posted, pinned)
            )

        shortlist = balanced_shortlist(items, news_bot_module.MAX_HEADLINES_TO_MODEL)
        counts = shortlist_lane_counts(shortlist)
        if shortlist:
            print("    model shortlist: " + ", ".join(
                f"{lane}={counts.get(lane, 0)}" for lane in LANE_ORDER
            ))
        decorated = decorate_model_items(shortlist)
        def generate_validated(feed, posted, event):
            generated = original_summarize(feed, posted, event)
            return enforce_snapchat_selection_gate(
                validate_ranked_result(generated, shortlist)
            )
        raw = cached_news_editorial(news_bot_module, generate_validated)(
            decorated, already_posted, pinned
        )
        validated = validate_ranked_result(raw, shortlist)
        selected = enforce_snapchat_selection_gate(validated)
        load_posted = getattr(news_bot_module, "load_posted", None)
        posted = load_posted() if callable(load_posted) else []
        balanced = rebalance_ranked_result(selected, shortlist, posted)
        return remember_story_contexts(balanced)

    return _summarize


def _marker(path, suffix):
    return Path(str(path) + suffix)


def _clear_candidate(path, *, image=True, preserve_recent=False):
    path = Path(path)
    if image:
        path.unlink(missing_ok=True)
    for suffix in _IMAGE_MARKERS:
        if preserve_recent and suffix == ".recentkeep":
            continue
        _marker(path, suffix).unlink(missing_ok=True)


def _candidate_path(hero, provider):
    hero = Path(hero)
    suffix = hero.suffix or ".jpg"
    return hero.with_name(f"{hero.stem}.auto-{provider}{suffix}")


def _promote_candidate(candidate, hero):
    """Copy one isolated provider candidate and only its own provenance."""
    candidate, hero = Path(candidate), Path(hero)
    _clear_candidate(hero, image=True)
    hero.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate, hero)
    for suffix in _IMAGE_MARKERS:
        src = _marker(candidate, suffix)
        if src.exists():
            shutil.copy2(src, _marker(hero, suffix))
    return str(hero)


def _promote_exact_logo(logo_path, hero, entity):
    """Place an exact logo on a clean image canvas for the card renderer."""
    hero = Path(hero)
    hero.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(logo_path) as source:
        logo = source.convert("RGBA")
        logo.thumbnail((760, 460), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (1280, 960), (245, 242, 236, 255))
        x = (canvas.width - logo.width) // 2
        y = (canvas.height - logo.height) // 2
        canvas.alpha_composite(logo, (x, y))
        canvas.convert("RGB").save(hero, "JPEG", quality=94)
    _marker(hero, ".exempt").write_text(
        f"logo:{entity}", encoding="utf-8"
    )
    return str(hero)


OFFICIAL_VISUAL_HOSTS = {
    "ndmc.gov.sa", "www.ndmc.gov.sa", "sukuk.ndmc.gov.sa",
    "mof.gov.sa", "www.mof.gov.sa",
    "spa.gov.sa", "www.spa.gov.sa",
}
CURATED_RECOVERY_VISUAL_HOSTS = {
    "upload.wikimedia.org", "arabic.arabianbusiness.com",
}


def fetch_verified_official_visual(story, out_path, opener=urllib.request.urlopen):
    """Load an exact recovery visual from a trusted URL or repository asset."""
    official_url = str(story.get("official_image_url") or "").strip()
    recovery_url = str(story.get("recovery_image_url") or "").strip()
    asset_name = str(story.get("recovery_image_b64_path") or "").strip()
    credit = str(story.get("recovery_photo_credit") or "").strip()

    if asset_name:
        asset = Path(asset_name)
        if (
            asset.is_absolute()
            or ".." in asset.parts
            or asset.parts[:2] != ("assets", "recovery")
            or asset.suffix != ".b64"
        ):
            print("  ! exact recovery asset path is not allowlisted")
            return None, None
        if not credit:
            print("  ! curated recovery visual is missing required attribution")
            return None, None
        try:
            data = base64.b64decode(asset.read_text(encoding="ascii"), validate=True)
        except Exception as exc:
            print(f"  ! exact recovery asset could not be decoded: {exc}")
            return None, None
        is_curated = True
        source_label = asset_name
        provenance = f"asset:{asset_name}"
    else:
        url = official_url or recovery_url
        if not url:
            return None, None
        parsed = urllib.parse.urlparse(url)
        is_curated = bool(recovery_url and not official_url)
        allowed_hosts = (
            CURATED_RECOVERY_VISUAL_HOSTS if is_curated else OFFICIAL_VISUAL_HOSTS
        )
        if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
            print("  ! exact recovery visual is not from an allowlisted host")
            return None, None
        if is_curated and not credit:
            print("  ! curated recovery visual is missing required attribution")
            return None, None
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; daily-news-snap/1.0)",
                    "Referer": f"{parsed.scheme}://{parsed.netloc}/",
                },
            )
            with opener(request, timeout=60) as response:
                data = response.read(8_000_001)
        except Exception as exc:
            print(f"  ! official recovery visual download failed: {exc}")
            return None, None
        source_label = parsed.hostname
        provenance = f"url:{url}"

    if len(data) < 5_000 or len(data) > 8_000_000:
        print("  ! official recovery visual has an invalid size")
        return None, None
    target = Path(out_path)
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            rgba = source.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (245, 242, 236, 255))
            background.alpha_composite(rgba)
            background.convert("RGB").save(
                target, format="JPEG", quality=95, optimize=True
            )
    except Exception as exc:
        print(f"  ! official recovery visual is not a valid image: {exc}")
        return None, None
    _marker(target, ".official-subject").write_text(
        provenance, encoding="utf-8"
    )
    kind = "curated" if is_curated else "official"
    print(f"    photo: verified {kind} subject visual from {source_label}")
    return str(target), credit or None


def install_auto_image_selector(news_bot_module):
    """Search all approved providers once, ranking relevance before source.

    Existing provider functions still own licensing, metadata quality, safety,
    Saudi-context and cooldown checks. In auto mode this runner gives each one
    an isolated candidate path, asks the existing vision judge about that
    candidate, and applies the editorial tiering rule:

        direct yes > best safe neutral > no candidate

    A later direct match therefore beats any neutral. If no direct match exists,
    an article-backed neutral outranks a generic local neutral so geographic
    familiarity alone cannot produce a visually unrelated card.
    """
    if getattr(news_bot_module, "_AUTO_IMAGE_SELECTOR_INSTALLED", False):
        return news_bot_module
    if not _can_install_auto_image_selector(news_bot_module):
        return news_bot_module

    originals = {
        "local": news_bot_module.fetch_local_photo,
        "article": news_bot_module.fetch_article_photo,
        "spa": news_bot_module.fetch_spa_photo,
        "commons": news_bot_module.fetch_commons_photo,
        "loc": news_bot_module.fetch_loc_photo,
        "openverse": news_bot_module.fetch_openverse_photo,
        "stock": news_bot_module.fetch_photo,
    }
    state = {"suppress_downstream": False}

    def downstream_pair(original):
        def _wrapped(*args, **kwargs):
            if state["suppress_downstream"]:
                return None, None
            return original(*args, **kwargs)
        return _wrapped

    def downstream_stock(*args, **kwargs):
        if state["suppress_downstream"]:
            return None
        return originals["stock"](*args, **kwargs)

    def local(queries_ar, queries_en, out_path,
              respect_cooldown=True, exclude=()):
        # Every story begins at the legacy local-library entrypoint. Reset the
        # guard here so an unresolved story can still use the old provider loop.
        state["suppress_downstream"] = False
        story = _story_for_queries(queries_en, queries_ar)
        if not story:
            return originals["local"](
                queries_ar, queries_en, out_path,
                respect_cooldown=respect_cooldown, exclude=exclude,
            )

        state["suppress_downstream"] = True
        hero = Path(out_path)
        # Never carry provenance from a previous failed attempt. Keep an
        # existing recentkeep, because legacy main intentionally remembers the
        # first recent candidate across ranked stories.
        _clear_candidate(hero, image=True, preserve_recent=True)

        context = _story_context_text(story) or _context_for_queries(
            queries_en, queries_ar)
        saudi = story.get("scope", "world") == "saudi"
        link = str(story.get("link", "") or "").strip()
        targets = normalize_visual_targets(story)

        def expanded_queries(original, field):
            values = list(original if isinstance(original, (list, tuple)) else [original])
            values.extend(target.get(field, "") for target in targets)
            return list(dict.fromkeys(
                str(value).strip() for value in values if str(value).strip()
            ))

        q_en = expanded_queries(
            story.get("image_queries", queries_en) or queries_en, "name_en"
        )
        q_ar = expanded_queries(
            story.get("image_queries_ar", queries_ar) or queries_ar, "name_ar"
        )

        neutral = None
        recentkeep = None
        candidates = []

        def prepare(name):
            candidate = _candidate_path(hero, name)
            _clear_candidate(candidate)
            candidates.append(candidate)
            return candidate

        def record_recent(candidate, credit):
            nonlocal recentkeep
            keep = _marker(candidate, ".recentkeep")
            if recentkeep is None and keep.exists():
                recentkeep = (keep, credit)

        def judge(name, photo, credit, candidate):
            nonlocal neutral
            record_recent(candidate, credit)
            if not photo:
                return None
            judge_context = context
            if credit:
                judge_context += f"\nPhoto provenance: {credit}"
            verdict = str(news_bot_module.photo_shows(
                photo, judge_context
            )).strip().lower()
            print(f"      auto image relevance [{name}]: {verdict}")
            if name == "commons" and verdict == "yes":
                title_marker = _marker(candidate, ".commons-title")
                try:
                    commons_title = title_marker.read_text(encoding="utf-8")
                except OSError:
                    commons_title = ""
                query_text = " ".join(
                    str(item) for item in
                    (q_en if isinstance(q_en, (list, tuple)) else [q_en])
                )
                if _commons_misses_numbered_product_model(
                        query_text, commons_title):
                    print("      auto image: rejected Commons photo for a "
                          "different numbered product model")
                    return None
            if verdict == "yes":
                return (Path(photo), credit, name)
            if verdict == "neutral" and name == "openverse":
                # Openverse has already required the candidate's own title,
                # tags and attribution to match the search terms, then the
                # vision gate confirmed it was not unrelated.  Keep that
                # metadata-screened photo as a last resort so a run does not
                # die only because the model could not verify exact identity.
                # Numbered products remain affirmative-only: an older model
                # must never illustrate a newly announced one.
                query_text = " ".join(
                    str(item) for item in
                    (q_en if isinstance(q_en, (list, tuple)) else [q_en])
                )
                query_tokens = set(re.findall(
                    r"[A-Za-z0-9]+", query_text.casefold()
                ))
                if (not _numbered_product_request(query_text)
                        and not query_tokens.intersection(_PRODUCT_CLASS_WORDS)
                        and query_tokens.intersection(
                            _OPENVERSE_NEUTRAL_DIGITAL_SUBJECTS
                        )):
                    neutral = (Path(photo), credit, name)
            if (verdict == "neutral" and name == "commons"
                    and not getattr(news_bot_module, "NEWS_REQUIRE_VERIFIED_VISUAL", False)):
                # A neutral verdict alone does not prove topicality. Commons
                # search can return a generic scene whose description happens
                # to contain a query word (for example, a Perth street for an
                # Apple launch). Require the file title to name a meaningful
                # query subject before retaining it as the final fallback.
                title_marker = _marker(candidate, ".commons-title")
                try:
                    commons_title = title_marker.read_text(encoding="utf-8")
                except OSError:
                    commons_title = ""
                query_text = " ".join(
                    str(item) for item in
                    (q_en if isinstance(q_en, (list, tuple)) else [q_en])
                )
                generic = {
                    "file", "photo", "image", "event", "stage", "launch",
                    "september", "building", "lineup", "reveal", "news",
                    # Geography and generic officialdom establish where a
                    # photo was taken, not what it depicts.  Treating Riyadh
                    # as a subject match put the Ministry of Education on a
                    # card about white-land fees.
                    "saudi", "arabia", "arabian", "kingdom", "riyadh",
                    "jeddah", "makkah", "mecca", "madinah", "medina",
                    "dammam", "khobar", "government", "ministry",
                    # Generic finance/place terms do not make a city scene
                    # relevant to a specific sukuk, IPO, bank product, or deal.
                    "financial", "finance", "district", "market", "office",
                    "building", "business", "bank",
                    # Generic retail and geography words can overlap a model
                    # query while depicting the wrong company or place.  A
                    # random high-street shop is not Next, and a wide Gulf
                    # view is not evidence that the image shows Khafji.
                    "store", "shop", "retail", "retailer", "street", "high",
                    "coast", "coastal", "gulf", "eastern", "province",
                    # A commodity or facility type alone does not connect a
                    # generic industrial scene to a live price or supply-risk
                    # story. A specific company, location, vessel, or event
                    # must still match.
                    "oil", "crude", "petroleum", "energy", "refinery",
                    "terminal", "tanker", "tankers", "pipeline",
                    # An empty venue does not depict a named athlete, coach,
                    # club, or transfer merely because the search asked for
                    # a football setting.
                    "sport", "sports", "football", "soccer", "stadium",
                    "arena", "venue", "field", "pitch",
                    # Literal money objects are not sufficient context for a
                    # modern named investment or savings product.
                    "coin", "coins", "currency", "money", "riyal", "riyals",
                }
                title_tokens = {
                    token.casefold() for token in re.findall(
                        r"[A-Za-z0-9]+", commons_title
                    ) if len(token) > 2
                }
                subject_tokens = {
                    token.casefold() for token in re.findall(
                        r"[A-Za-z0-9]+", query_text
                    ) if len(token) > 2 and token.casefold() not in generic
                }
                # A modern capture date in a filename is provenance, not an
                # archival subject. Keep the veto for genuinely historical
                # pre-2000 material such as the 1949 refinery, while allowing
                # named current subjects photographed in the digital era.
                title_years = {
                    year for year in re.findall(
                        r"\b(?:19|20)\d{2}\b", commons_title
                    ) if int(year) < 2000
                }
                context_years = set(re.findall(
                    r"\b(?:19|20)\d{2}\b", context
                ))
                if title_years - context_years:
                    print("      auto image: rejected neutral Commons photo "
                          "with an unmentioned archival year")
                elif title_tokens & subject_tokens:
                    neutral = (Path(photo), credit, name)
                else:
                    print("      auto image: rejected neutral Commons photo "
                          "without a named subject match")
            return None

        selected = None

        candidate = prepare("official")
        photo, credit = fetch_verified_official_visual(story, candidate)
        graphic_check = getattr(news_bot_module, "looks_like_a_graphic", None)
        if photo and graphic_check and graphic_check(photo):
            print("  ! exact recovery visual is a logo or graphic — rejecting")
            Path(photo).unlink(missing_ok=True)
            _marker(photo, ".official-subject").unlink(missing_ok=True)
            photo = None
        if photo:
            selected = (Path(photo), credit, "official")
            print("      auto image relevance [official]: verified direct subject")

        candidate = prepare("local")
        if selected is None:
            photo, credit = originals["local"](
                q_ar, q_en, candidate,
                respect_cooldown=respect_cooldown, exclude=exclude,
            )
            selected = judge("local", photo, credit, candidate)

        if selected is None and link:
            candidate = prepare("article")
            photo, domain = originals["article"](link, candidate)
            if photo and not domain:
                domain = urllib.parse.urlparse(link).netloc.replace("www.", "")
            mapped = getattr(news_bot_module, "DOMAIN_CREDITS", {}).get(domain, domain) \
                if domain else None
            selected = judge("article", photo, mapped, candidate)

        if selected is None and saudi:
            candidate = prepare("spa")
            photo, credit = originals["spa"](q_ar, candidate)
            selected = judge("spa", photo, credit, candidate)

        if selected is None:
            candidate = prepare("commons")
            photo, credit = originals["commons"](
                q_en, candidate, need_saudi=saudi)
            selected = judge("commons", photo, credit, candidate)

        if selected is None:
            candidate = prepare("loc")
            photo, credit = originals["loc"](
                q_en, candidate, need_saudi=saudi)
            selected = judge("loc", photo, credit, candidate)

        if selected is None:
            candidate = prepare("openverse")
            photo, credit = originals["openverse"](
                q_en, candidate, need_saudi=saudi)
            selected = judge("openverse", photo, credit, candidate)

        if selected is None and getattr(news_bot_module, "PEXELS_API_KEY", ""):
            candidate = prepare("stock")
            photo = originals["stock"](q_en, candidate, need_saudi=saudi)
            selected = judge("stock", photo, "Pexels" if photo else None, candidate)

        portrait_fetcher = getattr(
            news_bot_module, "fetch_commons_portrait", None
        )
        if selected is None and portrait_fetcher:
            for index, target in enumerate(targets):
                if target.get("kind") != "person":
                    continue
                name = target.get("name_en") or target.get("name_ar")
                candidate = prepare(f"portrait-{index}")
                photo, credit = portrait_fetcher(name, candidate)
                if photo:
                    selected = (Path(photo), credit, "portrait")
                    print(f"      auto image recovery: exact portrait for {name}")
                    break

        if selected is None:
            logo, entity = exact_logo_for_targets(
                targets, _LOGOS_DIR, _LOGOS_INDEX
            )
            if logo:
                result = _promote_exact_logo(logo, hero, entity)
                for candidate in candidates:
                    _clear_candidate(candidate)
                print(f"      auto image recovery: exact logo for {entity}")
                return result, entity

        if selected is None and neutral is not None:
            selected = neutral
            print(f"      auto image: using metadata-screened {neutral[2]} "
                  "photo as topical fallback")

        if selected is None and recentkeep is not None:
            keep, recent_credit = recentkeep
            _clear_candidate(hero, image=True)
            shutil.copy2(keep, hero)
            for candidate in candidates:
                _clear_candidate(candidate)
            print("      auto image recovery: reusing same-story verified photo")
            return str(hero), recent_credit

        if selected is not None:
            selected_path, selected_credit, _ = selected
            result = _promote_candidate(selected_path, hero), selected_credit
            for candidate in candidates:
                _clear_candidate(candidate)
            return result

        # Preserve the legacy exhaustion fallback for a provider that rejected
        # an otherwise usable image only because it appeared on a recent card.
        if recentkeep is not None and not _marker(hero, ".recentkeep").exists():
            shutil.copy2(recentkeep[0], _marker(hero, ".recentkeep"))
        for candidate in candidates:
            _clear_candidate(candidate)
        return None, None

    news_bot_module.fetch_local_photo = local
    news_bot_module.fetch_article_photo = downstream_pair(originals["article"])
    news_bot_module.fetch_spa_photo = downstream_pair(originals["spa"])
    news_bot_module.fetch_commons_photo = downstream_pair(originals["commons"])
    news_bot_module.fetch_loc_photo = downstream_pair(originals["loc"])
    news_bot_module.fetch_openverse_photo = downstream_pair(originals["openverse"])
    news_bot_module.fetch_photo = downstream_stock
    news_bot_module._AUTO_IMAGE_SELECTOR_INSTALLED = True
    return news_bot_module


def configure(news_bot_module):
    """Apply the editorial and daily-image policy to imported ``news_bot``."""
    news_bot_module.LOOKBACK_HOURS = int(
        os.getenv("LOOKBACK_HOURS", str(DEFAULT_LOOKBACK_HOURS))
    )
    news_bot_module.IMAGE_SOURCE = normalize_image_source(
        os.getenv("IMAGE_SOURCE", "auto")
    )
    news_bot_module.SYSTEM_PROMPT = SYSTEM_PROMPT
    news_bot_module.fetch_headlines = make_fetcher(news_bot_module)
    news_bot_module.summarize = make_summarizer(news_bot_module)
    if hasattr(news_bot_module, "save_posted"):
        news_bot_module.save_posted = make_source_aware_save_posted(news_bot_module)
    if news_bot_module.IMAGE_SOURCE == "auto":
        install_auto_image_selector(news_bot_module)
    return news_bot_module


def main():
    import news_bot
    configure(news_bot)
    news_bot.main()


if __name__ == "__main__":
    main()
