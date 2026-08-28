#!/usr/bin/env python3
"""Safety wrapper for reviewed-card publishing.

Telegram is the private review stage. Snapchat is the public release stage.
A Telegram review sends the selected reviewed deck and caption without calling
Bundle/Snapchat or changing the Snapchat quota.

Before review, the actual rendered cards must contain enough photographic
coverage. This protects against stale decks built before the runtime visual
coverage gate existed.

Bundle/Snapchat Public Profile publishing supports one media item per Story
post. Our live tests showed that neither multiple Bundle image posts nor one
video produces the requested six separate photo snaps. Refuse that unsupported
live operation instead of silently publishing the wrong shape.
"""

import hashlib
import json
import os
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
    """Validate and send the reviewed deck privately to Telegram only."""
    stamp, frames = _selected_story()
    caption = publisher.load_caption(stamp, len(frames))

    print(f"Telegram review: {len(frames)} frames from {stamp}")
    for path in frames:
        print(f"    {path}")
    print(f"    caption: {caption}")

    # Validate the actual baked PNGs, not just source inventory. Old decks can
    # pre-date story_runtime's 4-photo + logo gate and must fail closed here.
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
