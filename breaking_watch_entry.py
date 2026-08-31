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


if __name__ == "__main__":
    breaking_watch.watch()
