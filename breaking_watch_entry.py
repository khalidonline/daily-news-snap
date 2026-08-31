#!/usr/bin/env python3
"""Production entrypoint for breaking watch with strict visual publishing."""

import os
import subprocess
import sys

import breaking_watch


def _run_strict_news_bot(extra_env):
    env = os.environ.copy()
    env.update(extra_env)
    return subprocess.call([sys.executable, "breaking_news_runner.py"], env=env)


breaking_watch._run_news_bot = _run_strict_news_bot


def run():
    """Run the watcher, or safely reproduce an already-confirmed event."""
    confirmed_event = os.getenv("CONFIRMED_BREAKING_EVENT", "").strip()
    if confirmed_event:
        print("manual confirmed-event reproduction — classifier bypassed, dry run forced")
        return _run_strict_news_bot({
            "PINNED_EVENT": confirmed_event,
            "POST_TO_SNAPCHAT": "1",
            "DRY_RUN": "1",
        })

    breaking_watch.watch()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
