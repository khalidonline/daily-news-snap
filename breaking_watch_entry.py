#!/usr/bin/env python3
"""Production entrypoint for breaking watch with strict visual publishing."""

import os
import subprocess
import sys

import breaking_watch


def _run_strict_news_bot(extra_env):
    env = os.environ.copy()
    env.update(extra_env)
    # Review phase: breaking cards may be generated and sent to Telegram,
    # but this entrypoint must never allow a direct Snapchat publish.
    env["POST_TO_SNAPCHAT"] = "0"
    return subprocess.call([sys.executable, "breaking_news_runner.py"], env=env)


def _install_quiet_notifications():
    """Silence routine watcher status while preserving real alerts/failures."""
    send = breaking_watch.notify

    def notify(message):
        text = str(message)
        if text.startswith("⚪️"):
            print("routine breaking-watch Telegram notification suppressed")
            return None
        return send(message)

    breaking_watch.notify = notify


breaking_watch._run_news_bot = _run_strict_news_bot


def run():
    """Run the watcher, or safely reproduce an already-confirmed event."""
    confirmed_event = (
        os.getenv("CONFIRMED_BREAKING_EVENT", "").strip()
        or os.getenv("TRIGGER_CONFIRMED_EVENT", "").strip()
    )
    if confirmed_event:
        print("manual confirmed-event reproduction — classifier bypassed, dry run forced")
        return _run_strict_news_bot({
            "PINNED_EVENT": confirmed_event,
            "POST_TO_SNAPCHAT": "0",
            "DRY_RUN": "1",
        })

    _install_quiet_notifications()
    breaking_watch.watch()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
