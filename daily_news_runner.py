"""Daily entrypoint that applies the Saudi Snapchat editorial policy.

The legacy ``news_bot`` module continues to own rendering, provider fetchers,
publishing, retry behavior, and posted-story memory. This runner swaps in the
Saudi-audience feed/ranking prompt and, in ``auto`` image mode, compares the
approved provider candidates by visual relevance before returning one to the
legacy renderer.
"""

import os
import shutil
import urllib.parse
from pathlib import Path

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

_IMAGE_MARKERS = (".exempt", ".generated", ".recentkeep")
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
            _STORY_CONTEXTS[key] = dict(story)
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


def validate_ranked_result(result, shortlist):
    """Remove model-ranked stories that violate hard source-item boundaries.

    The model refers to the numbered shortlist with a 1-based integer ``item``.
    Only that exact source item decides eligibility; generated card wording can
    never be used to bypass the deterministic scope rules.
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
        if not hard_scope_eligible(source_item):
            continue
        if not audience_fit_eligible(source_item):
            continue
        kept.append(story)

    validated = dict(result)
    validated["stories"] = kept
    if len(kept) != len(stories):
        print(f"    post-model scope gate: kept {len(kept)}/{len(stories)} ranked stories")
    return validated


def _can_install_auto_image_selector(news_bot_module):
    return all(hasattr(news_bot_module, name) for name in AUTO_IMAGE_REQUIRED_ATTRS)


def make_fetcher(news_bot_module):
    def _fetch():
        return fetch_headlines(
            news_bot_module._http_get,
            news_bot_module._clean,
            news_bot_module._parse_date,
            lookback_hours=news_bot_module.LOOKBACK_HOURS,
        )
    return _fetch


def make_summarizer(news_bot_module):
    original_summarize = news_bot_module.summarize

    def _summarize(items, already_posted=(), pinned=""):
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
        raw = original_summarize(decorated, already_posted, pinned)
        validated = validate_ranked_result(raw, shortlist)
        return remember_story_contexts(validated)

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
        q_en = story.get("image_queries", queries_en) or queries_en
        q_ar = story.get("image_queries_ar", queries_ar) or queries_ar

        neutral = None
        recentkeep = None
        candidates = []

        def prepare(name):
            candidate = _candidate_path(hero, name)
            _clear_candidate(candidate)
            candidates.append(candidate)
            return candidate

        def record_recent(candidate):
            nonlocal recentkeep
            keep = _marker(candidate, ".recentkeep")
            if recentkeep is None and keep.exists():
                recentkeep = keep

        def judge(name, photo, credit, candidate):
            nonlocal neutral
            record_recent(candidate)
            if not photo:
                return None
            verdict = str(news_bot_module.photo_shows(photo, context)).strip().lower()
            print(f"      auto image relevance [{name}]: {verdict}")
            if verdict == "yes":
                return (Path(photo), credit, name)
            if verdict == "neutral":
                proposed = (Path(photo), credit, name)
                if neutral is None or _NEUTRAL_PRIORITY.get(name, 99) < \
                        _NEUTRAL_PRIORITY.get(neutral[2], 99):
                    neutral = proposed
            return None

        selected = None

        candidate = prepare("local")
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

        if selected is None and neutral is not None:
            selected = neutral
            print(f"      auto image: using safe neutral fallback from {selected[2]}")

        if selected is not None:
            selected_path, selected_credit, _ = selected
            result = _promote_candidate(selected_path, hero), selected_credit
            for candidate in candidates:
                _clear_candidate(candidate)
            return result

        # Preserve the legacy exhaustion fallback for a provider that rejected
        # an otherwise usable image only because it appeared on a recent card.
        if recentkeep is not None and not _marker(hero, ".recentkeep").exists():
            shutil.copy2(recentkeep, _marker(hero, ".recentkeep"))
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
    if news_bot_module.IMAGE_SOURCE == "auto":
        install_auto_image_selector(news_bot_module)
    return news_bot_module


def main():
    import news_bot
    configure(news_bot)
    news_bot.main()


if __name__ == "__main__":
    main()
