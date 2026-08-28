#!/usr/bin/env python3
"""Safety wrapper for reviewed-card publishing.

Telegram is the private review stage. Snapchat is the public release stage.
A Telegram review sends the selected reviewed deck and caption without calling
Bundle/Snapchat or changing the Snapchat quota.

Bundle/Snapchat Public Profile publishing supports one media item per Story
post. Our live tests showed that neither multiple Bundle image posts nor one
video produces the requested six separate photo snaps. Refuse that unsupported
live operation instead of silently publishing the wrong shape.
"""

import os

import publish_cards as publisher


PUBLISH_MODE = os.getenv("PUBLISH_MODE", "telegram_review").strip() or "telegram_review"


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


def _send_review_photos(stamp, caption, frames):
    """Send every review frame as its own Telegram photo and verify each one."""
    total = len(frames)
    confirmed = 0
    for index, frame in enumerate(frames, start=1):
        text = f"👀 مراجعة قبل النشر — {stamp}\n{index}/{total}"
        if index == 1:
            text += f"\n{caption}"
        ok = publisher.notify(text, frame)
        if not ok:
            raise SystemExit(
                f"Telegram confirmed only {confirmed}/{total} review photos; "
                f"frame {index} was not confirmed. Snapchat/Bundle were not called."
            )
        confirmed += 1
        print(f"    telegram review photo {index}/{total}: confirmed")
    return confirmed


def review_on_telegram():
    """Send the reviewed deck privately to Telegram and stop there."""
    stamp, frames = _selected_story()
    caption = publisher.load_caption(stamp, len(frames))

    print(f"Telegram review: {len(frames)} frames from {stamp}")
    for path in frames:
        print(f"    {path}")
    print(f"    caption: {caption}")

    if publisher.DRY_RUN:
        print("DRY_RUN — Telegram review not sent; Snapchat untouched")
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
