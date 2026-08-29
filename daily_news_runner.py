"""Daily entrypoint that applies the Saudi Snapchat editorial policy.

The legacy ``news_bot`` module continues to own rendering, provider fetchers,
publishing, retry behavior, and posted-story memory. This runner swaps in the
Saudi-audience feed/ranking prompt and, in ``auto`` image mode, adds a visual
relevance gate between provider fetchers and the legacy first-success selector.
"""

import os

from news_editorial import (
    DEFAULT_LOOKBACK_HOURS,
    SYSTEM_PROMPT,
    balanced_shortlist,
    decorate_model_items,
    fetch_headlines,
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
    """Remember card text so image fetch wrappers can judge the real story."""
    _STORY_CONTEXTS.clear()
    for story in (result or {}).get("stories", []):
        key = _story_context_key(story)
        if not any(key):
            continue
        context = _story_context_text(story)
        if context:
            _STORY_CONTEXTS[key] = context
    return result


def _context_for_queries(queries_en, queries_ar):
    key = (_query_key(queries_en), _query_key(queries_ar))
    context = _STORY_CONTEXTS.get(key)
    if context:
        return context
    fallback = list(key[0]) + list(key[1])
    return "\n".join(fallback)


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
        return remember_story_contexts(
            original_summarize(decorated, already_posted, pinned)
        )

    return _summarize


def install_auto_image_selector(news_bot_module):
    """Accept provider candidates only when they directly depict the story.

    The legacy ``news_bot.main`` already tries local/article/SPA/Commons/LoC/
    Openverse/Pexels sequentially. Its only flaw for ``auto`` is that it stops
    at the first provider that returns a technically usable file. Wrapping the
    provider functions lets all of their existing licence, metadata, safety,
    quality, Saudi-context and cooldown rules run unchanged; a returned file is
    then passed through the existing vision judge. ``neutral`` and ``no`` are
    withheld, so the legacy loop naturally continues to later providers.
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
    state = {"context": ""}

    def accepts(photo):
        if not photo:
            return False
        context = state["context"]
        verdict = str(news_bot_module.photo_shows(photo, context)).strip().lower()
        print(f"      auto image relevance: {verdict}")
        return verdict == "yes"

    def local(queries_ar, queries_en, out_path,
              respect_cooldown=True, exclude=()):
        state["context"] = _context_for_queries(queries_en, queries_ar)
        photo, credit = originals["local"](
            queries_ar, queries_en, out_path,
            respect_cooldown=respect_cooldown, exclude=exclude,
        )
        return (photo, credit) if accepts(photo) else (None, None)

    def article(url, out_path):
        photo, domain = originals["article"](url, out_path)
        return (photo, domain) if accepts(photo) else (None, None)

    def spa(queries_ar, out_path):
        photo, credit = originals["spa"](queries_ar, out_path)
        return (photo, credit) if accepts(photo) else (None, None)

    def commons(queries, out_path, need_saudi=None, min_hits=None,
                subject_mode=False):
        photo, credit = originals["commons"](
            queries, out_path, need_saudi=need_saudi, min_hits=min_hits,
            subject_mode=subject_mode,
        )
        return (photo, credit) if accepts(photo) else (None, None)

    def loc(queries, out_path, need_saudi=None, min_hits=None,
            subject_mode=False):
        photo, credit = originals["loc"](
            queries, out_path, need_saudi=need_saudi, min_hits=min_hits,
            subject_mode=subject_mode,
        )
        return (photo, credit) if accepts(photo) else (None, None)

    def openverse(queries, out_path, need_saudi=None, min_hits=None,
                  subject_mode=False):
        photo, credit = originals["openverse"](
            queries, out_path, need_saudi=need_saudi, min_hits=min_hits,
            subject_mode=subject_mode,
        )
        return (photo, credit) if accepts(photo) else (None, None)

    def stock(queries, out_path, need_saudi=None):
        photo = originals["stock"](queries, out_path, need_saudi=need_saudi)
        return photo if accepts(photo) else None

    news_bot_module.fetch_local_photo = local
    news_bot_module.fetch_article_photo = article
    news_bot_module.fetch_spa_photo = spa
    news_bot_module.fetch_commons_photo = commons
    news_bot_module.fetch_loc_photo = loc
    news_bot_module.fetch_openverse_photo = openverse
    news_bot_module.fetch_photo = stock
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
