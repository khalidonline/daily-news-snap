#!/usr/bin/env python3
"""Run a Story delivery attempt until Telegram confirms it or the budget ends."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable


def run_until_delivered(
    run_once: Callable[[], int], *, max_attempts: int = 3
) -> int:
    """Return success immediately; otherwise exhaust a small, bounded budget."""
    attempts = max(1, int(max_attempts))
    last_result = 1
    for attempt in range(1, attempts + 1):
        print(f"STORY_DELIVERY_ATTEMPT {attempt}/{attempts}", flush=True)
        last_result = int(run_once())
        if last_result == 0:
            print(f"STORY_DELIVERY_CONFIRMED on attempt {attempt}", flush=True)
            return 0
        print(f"STORY_DELIVERY_RETRY_REQUIRED after attempt {attempt}", flush=True)
        # A scheduled owner choice that proves unusable must not strand the
        # daily slot. Its failure is persisted by the renderer, then the next
        # attempt may select another prevalidated Story.
        if os.getenv("STORY_SELECTION_MODE", "").strip() == "scheduled":
            os.environ["STORY"] = ""
    return last_result


def _run_guarded_story() -> int:
    completed = subprocess.run(
        [sys.executable, "guarded_story_publish.py"],
        check=False,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)
    combined = stdout + "\n" + stderr
    if (
        completed.returncode == 0
        and "duplicate suppressed" in combined
        and "Telegram final candidate sent" not in combined
    ):
        print(
            "STORY_DELIVERY_UNCONFIRMED: duplicate suppression is not a "
            "Telegram delivery",
            flush=True,
        )
        return 1
    return completed.returncode


def main() -> int:
    attempts = int(os.getenv("STORY_DELIVERY_MAX_ATTEMPTS", "3") or "3")
    return run_until_delivered(_run_guarded_story, max_attempts=attempts)


if __name__ == "__main__":
    raise SystemExit(main())
