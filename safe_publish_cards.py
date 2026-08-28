#!/usr/bin/env python3
"""Safety wrapper for reviewed-card publishing.

Telegram is the private review stage. Snapchat is the public release stage.
A Telegram review sends the selected reviewed deck and caption without calling
Bundle/Snapchat or changing the Snapchat quota.

Before review, the actual rendered cards must contain enough photographic
coverage. If an old baked deck predates the current visual standard, review mode
rebuilds that same story once with the current renderer, verifies the fresh deck,
and only then sends it to Telegram. The rebuild runs with Telegram and Snapchat
credentials removed/disabled so the wrapper remains the sole review sender.

Bundle/Snapchat Public Profile publishing supports one media item per Story
post. Our live tests showed that neither multiple Bundle image posts nor one
video produces the requested six separate photo snaps. Refuse that unsupported
live operation instead of silently publishing the wrong shape.
"""

import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import publish_cards as publisher
from review_visual_gate import require_photo_coverage


PUBLISH_MODE = os.getenv("PUBLISH_MODE", "telegram_review").strip() or "telegram_review"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def guard_bundle_multiframe(provider, frames, dry_run=False):
    frames = list(frames or [])
    if provider == "bundle" and not dry_run and len(frames) > 1:
        raise SystemExit(
            f"Bundle cannot publish {len(frames)} separate Snapchat Story photos "
            "reliably. Live publishing is blocked to prevent another one-item "
            "Story. Use Telegram review for private review, DRY_RUN=1 for log "
            "preview, or a publishing path that can prove separate Story snaps."
        )


def _selected_story():
    selector = publisher.resolve_story_selector(publisher.STAMP)
    stamp, frames = publisher.find_story(selector)
    if not frames:
        raise SystemExit(f"no story cards found in {publisher.CARDS_DIR}/")
    return stamp, frames


def _sidecar_path(stamp):
    return Path(publisher.CARDS_DIR) / f"{stamp}-story.json"


def _story_identity(stamp):
    """Return the canonical story input that originally built a deck."""
    path = _sidecar_path(stamp)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(
            f"cannot rebuild stale deck {stamp}: sidecar is unreadable ({exc})"
        )
    story = str(data.get("story") or "").strip()
    if not story:
        raise SystemExit(
            f"cannot rebuild stale deck {stamp}: sidecar has no canonical story field"
        )
    return story


def _matching_sidecars(story):
    matches = {}
    root = Path(publisher.CARDS_DIR)
    for path in root.glob("*-story.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(data.get("story") or "").strip() != story:
            continue
        matches[path] = (path.stat().st_mtime_ns, path.stat().st_size)
    return matches


def _rebuild_story_for_review(story, stale_stamp):
    """Rebuild one stale story with zero Telegram/Snapchat side effects."""
    before = _matching_sidecars(story)
    env = os.environ.copy()
    env.update({
        "STORY": story,
        "DRY_RUN": "",
        "POST_TO_SNAPCHAT": "0",
        "STORY_ALLOW_REPEAT": "1",
        "STORY_FRAMES": "6",
        "ALLOW_GENERATED": "0",
        "ALLOW_STORY_GENERATION": "0",
    })
    # The subprocess may commit its fresh cards, but it must never send a
    # Telegram preview of its own or gain access to the public publisher.
    for key in (
        "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "BUNDLE_API_KEY",
        "BUNDLE_TEAM_ID", "BUNDLE_BASE",
    ):
        env.pop(key, None)

    print(f"Stale review deck detected — rebuilding current story: {story}")
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
        raise SystemExit(
            f"automatic review rebuild failed for {story!r}; "
            "Telegram and Snapchat were not called"
        )

    after = _matching_sidecars(story)
    changed = [
        path for path, fingerprint in after.items()
        if path not in before or before[path] != fingerprint
    ]
    if not changed:
        raise SystemExit(
            f"automatic review rebuild produced no fresh cards for {story!r}; "
            "Telegram and Snapchat were not called"
        )
    newest = max(changed, key=lambda p: p.stat().st_mtime_ns)
    suffix = "-story.json"
    stamp = newest.name[:-len(suffix)]
    if stamp == stale_stamp and before.get(newest) == after.get(newest):
        raise SystemExit("automatic review rebuild did not replace the stale deck")
    stamp, frames = publisher.find_story(stamp)
    if not frames:
        raise SystemExit("automatic review rebuild sidecar has no valid frame set")
    print(f"Fresh review deck built: {stamp} ({len(frames)} frames)")
    return stamp, frames


def _telegram_review_photo(text, photo_path):
    """Send one Telegram photo and verify Telegram returned a message id."""
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        raise SystemExit("TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must both be set")
    path = Path(photo_path)
    if not path.exists():
        return False

    boundary = "----snapreview" + hashlib.md5(
        f"{text}|{path.name}".encode()
    ).hexdigest()[:12]
    parts = []
    for name, value in (("chat_id", TELEGRAM_CHAT_ID), ("caption", text)):
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="photo"; '
        f'filename="{path.name}"\r\n'
        f"Content-Type: image/png\r\n\r\n".encode()
    )
    body = b"".join(parts) + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        print(f"  ! Telegram sendPhoto {exc.code}: {exc.read().decode()[:250]}")
        return False
    except Exception as exc:
        print(f"  ! Telegram sendPhoto failed: {exc}")
        return False

    message_id = ((data.get("result") or {}).get("message_id")
                  if isinstance(data, dict) else None)
    return bool(isinstance(data, dict) and data.get("ok") is True and message_id)


def _send_review_photos(stamp, caption, frames):
    """Send every review frame as its own Telegram photo and verify each one."""
    total = len(frames)
    confirmed = 0
    for index, frame in enumerate(frames, start=1):
        text = f"👀 مراجعة قبل النشر — {stamp}\n{index}/{total}"
        if index == 1:
            text += f"\n{caption}"
        ok = _telegram_review_photo(text, frame)
        if not ok:
            raise SystemExit(
                f"Telegram confirmed only {confirmed}/{total} review photos; "
                f"frame {index} was not confirmed. Snapchat/Bundle were not called."
            )
        confirmed += 1
        print(f"    telegram review photo {index}/{total}: confirmed")
    return confirmed


def review_on_telegram():
    """Validate, repair if stale, and send the deck privately to Telegram."""
    stamp, frames = _selected_story()
    caption = publisher.load_caption(stamp, len(frames))

    print(f"Telegram review: {len(frames)} frames from {stamp}")
    for path in frames:
        print(f"    {path}")
    print(f"    caption: {caption}")

    try:
        require_photo_coverage(frames, minimum=4)
    except SystemExit:
        # A true dry run may inspect but must never mutate/commit the repo.
        if publisher.DRY_RUN:
            raise
        story = _story_identity(stamp)
        stamp, frames = _rebuild_story_for_review(story, stamp)
        caption = publisher.load_caption(stamp, len(frames))
        # The fresh baked PNGs are the final authority. A rebuild that still
        # misses 4/6 fails closed before any Telegram message is sent.
        require_photo_coverage(frames, minimum=4)

    if publisher.DRY_RUN:
        print("DRY_RUN — visual gate passed; Telegram review not sent; Snapchat untouched")
        return

    confirmed = _send_review_photos(stamp, caption, frames)
    print(
        f"Telegram review confirmed {confirmed}/{len(frames)} separate photos — "
        "Snapchat/Bundle not called; quota unchanged"
    )


def run_mode(mode=None):
    mode = (mode or PUBLISH_MODE).strip().lower()
    if mode == "telegram_review":
        review_on_telegram()
        return
    if mode == "snapchat":
        _stamp, frames = _selected_story()
        guard_bundle_multiframe(publisher.POST_PROVIDER, frames, publisher.DRY_RUN)
        publisher.main()
        return
    raise SystemExit(
        f"unknown publish mode {mode!r}; expected 'telegram_review' or 'snapchat'"
    )


def main():
    run_mode()


if __name__ == "__main__":
    main()
