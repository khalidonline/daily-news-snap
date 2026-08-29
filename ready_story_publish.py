#!/usr/bin/env python3
"""Strict-ready Story Bot publishing pipeline.

The visual runtime gate remains authoritative. This module maintains a visible
READY list and publishes a six-card Snapchat story as six separate Story posts,
which matches Snapchat's single-media-per-post constraint.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import news_bot as nb
import story_bot as sb
import story_runtime as sr


READY_FILE = Path(os.getenv("READY_STORIES_FILE", "state/ready_to_post.json"))


def collect_ready_stories(stories=None, coverage_fn=None):
    """Return only stories that pass the strict runtime visual gate."""
    stories = list(sb.load_stories() if stories is None else stories)
    coverage_fn = coverage_fn or sr.coverage
    ready = []
    for story in stories:
        photos, logos, status = coverage_fn(story)
        if status == "PASS" and len(photos) >= 4 and len(logos) >= 1:
            ready.append(story)
    return ready


def write_ready_file(path=READY_FILE):
    """Persist the current strict-PASS pool for operations and review."""
    ready = collect_ready_stories()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ready_count": len(ready),
        "total_stories": len(sb.load_stories()),
        "stories": ready,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"READY_FOR_SNAP={len(ready)}/{payload['total_stories']}")
    return path, ready


def publish_frames_sequentially(
    caption,
    frames,
    *,
    post_fn=None,
    post_ok_fn=None,
):
    """Publish each rendered card as its own Snapchat Story item."""
    frames = list(frames or [])
    if not frames:
        raise SystemExit("no story frames to publish")
    post_fn = post_fn or nb.post_story
    post_ok_fn = post_ok_fn or nb.post_ok

    confirmed = 0
    for index, frame in enumerate(frames, start=1):
        response = post_fn(caption, [], frame)
        print(f"    Snapchat frame {index}/{len(frames)}: {response}")
        if not post_ok_fn(response):
            raise SystemExit(
                f"Snapchat confirmed only {confirmed}/{len(frames)} frames; "
                f"frame {index} failed. Story is not marked complete."
            )
        confirmed += 1
    return confirmed


def _frame_snapshot():
    result = {}
    for path in nb.OUT_DIR.glob("*-story-*.png"):
        try:
            result[path] = (path.stat().st_mtime_ns, path.stat().st_size)
        except OSError:
            pass
    return result


def build_story_without_posting(story):
    """Render one fresh strict-PASS deck without changing posting state."""
    before = _frame_snapshot()
    env = os.environ.copy()
    env.update({
        "STORY": story,
        "DRY_RUN": "1",
        "POST_TO_SNAPCHAT": "0",
        "STORY_ALLOW_REPEAT": "1",
        "ALLOW_GENERATED": "0",
        "ALLOW_STORY_GENERATION": "0",
    })
    result = subprocess.run(
        [sys.executable, "story_runtime.py"],
        env=env,
        text=True,
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.rstrip())
        raise SystemExit(f"story build failed for {story!r}; nothing posted")

    after = _frame_snapshot()
    changed = [
        path for path, fingerprint in after.items()
        if path not in before or before[path] != fingerprint
    ]
    changed.sort(key=lambda path: path.stat().st_mtime_ns)
    expected = int(os.getenv("STORY_FRAMES", "6") or "6")
    if len(changed) != expected:
        raise SystemExit(
            f"expected {expected} fresh story frames, got {len(changed)}; nothing posted"
        )
    return changed


def _mark_story_complete(story):
    slug = re.sub(r"[^\w]+", "-", story, flags=re.UNICODE)[:40].strip("-")
    sb.commit_and_push(sb.save_used(sb.load_used(), story), f"story: {slug}")
    sb.bump_mix(sb.story_pool(story))
    sb.commit_and_push(nb.quota_bump(), f"quota story: {slug}")


def _resolve_story():
    if sb.STORY:
        story = sb.resolve_story_input(sb.STORY)
        photos, logos, status = sr.coverage(story)
        if status != "PASS" or len(photos) < 4 or not logos:
            raise SystemExit(
                f"requested story is not READY_FOR_SNAP: {status}: {story}"
            )
        return story
    return sr.choose_runtime_story()


def main():
    refresh_only = "--refresh-only" in sys.argv
    ready_path, ready = write_ready_file()
    if refresh_only:
        return
    if not ready:
        raise SystemExit("READY_FOR_SNAP is empty")

    story = _resolve_story()
    if not story:
        raise SystemExit("no fresh READY_FOR_SNAP story available")
    print(f"Selected READY_FOR_SNAP story: {story}")

    frames = build_story_without_posting(story)
    if nb.DRY_RUN or not nb.POST_ENABLED:
        print(f"DRY/HYBRID — rendered {len(frames)} frames; Snapchat untouched")
        return

    if not nb.quota_ok():
        raise SystemExit("monthly Snapchat post quota reached")

    confirmed = publish_frames_sequentially(story, frames)
    if confirmed != len(frames):
        raise SystemExit("not all Snapchat Story frames were confirmed")

    _mark_story_complete(story)
    print(f"SNAPCHAT STORY COMPLETE: {story} ({confirmed}/{len(frames)} frames)")


if __name__ == "__main__":
    main()
