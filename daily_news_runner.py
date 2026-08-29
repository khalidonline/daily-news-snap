"""Daily entrypoint that applies the Saudi Snapchat editorial policy.

The legacy ``news_bot`` module continues to own rendering, image selection,
publishing, retry behavior, and posted-story memory. This runner only swaps in
lane-tagged feed fetching, shortlist preparation, and the approved system prompt
before calling ``news_bot.main()``.
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
            # Pinned breaking events use the original verified-search path; only
            # the system prompt is updated. Lane/freshness balancing applies to
            # normal feed candidates, not to a single pinned event.
            return original_summarize(items, already_posted, pinned)

        shortlist = balanced_shortlist(items, news_bot_module.MAX_HEADLINES_TO_MODEL)
        counts = shortlist_lane_counts(shortlist)
        if shortlist:
            print("    model shortlist: " + ", ".join(
                f"{lane}={counts.get(lane, 0)}" for lane in LANE_ORDER
            ))
        decorated = decorate_model_items(shortlist)
        return original_summarize(decorated, already_posted, pinned)

    return _summarize


def configure(news_bot_module):
    """Apply the editorial policy to an imported ``news_bot`` module."""
    news_bot_module.LOOKBACK_HOURS = int(
        os.getenv("LOOKBACK_HOURS", str(DEFAULT_LOOKBACK_HOURS))
    )
    news_bot_module.SYSTEM_PROMPT = SYSTEM_PROMPT
    news_bot_module.fetch_headlines = make_fetcher(news_bot_module)
    news_bot_module.summarize = make_summarizer(news_bot_module)
    return news_bot_module


def main():
    import news_bot
    configure(news_bot)
    news_bot.main()


if __name__ == "__main__":
    main()
