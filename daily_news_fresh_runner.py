"""Daily news entrypoint with strict cross-story visual freshness.

The legacy photo layer keeps a `.recentkeep` escape hatch so older bots can
reuse a recent image when every fresh source is exhausted. That behavior is
wrong for the scheduled News card: a recent image rejected for one ranked
story must never become another story's final fallback.
"""

from pathlib import Path

import daily_news_runner


def install_recent_photo_fail_closed(news_bot_module):
    """Prevent scheduled News from recycling a recently used photo."""
    original_local = news_bot_module.fetch_local_photo

    def fresh_local(*args, **kwargs):
        result = original_local(*args, **kwargs)
        out_path = kwargs.get("out_path")
        if out_path is None and len(args) >= 3:
            out_path = args[2]
        photo = result[0] if isinstance(result, tuple) and result else result
        if not photo and out_path:
            Path(str(out_path) + ".recentkeep").unlink(missing_ok=True)
        return result

    def no_recent_fallback(out_path):
        Path(str(out_path) + ".recentkeep").unlink(missing_ok=True)
        print("  ! fresh visual exhausted — refusing recent-photo fallback")
        return None

    news_bot_module.fetch_local_photo = fresh_local
    news_bot_module.recent_fallback = no_recent_fallback
    return news_bot_module


def install_news_notification_labels(news_bot_module):
    """Keep News alerts distinct from the separate Story bot."""
    original_notify = news_bot_module.notify

    def news_notify(text, *args, **kwargs):
        text = str(text).replace(
            "stories had a usable photo", "news items had a usable photo"
        ).replace(
            "model returned no stories", "model returned no news items"
        )
        return original_notify(text, *args, **kwargs)

    news_bot_module.notify = news_notify
    return news_bot_module


def main():
    import news_bot

    daily_news_runner.configure(news_bot)
    install_recent_photo_fail_closed(news_bot)
    install_news_notification_labels(news_bot)
    news_bot.main()


if __name__ == "__main__":
    main()
