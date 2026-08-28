#!/usr/bin/env python3
"""Private Telegram review and guarded Snapchat publishing.

The manual Telegram workflow is intentionally simple: build one fresh story,
place the requested number of approved photographs into its six cards, verify
the rendered result, then send the six cards to Telegram. Snapchat/Bundle are
not called by this review path.
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
from review_visual_gate import apply_requested_photos, require_photo_coverage


PUBLISH_MODE = os.getenv("PUBLISH_MODE", "telegram_review").strip() or "telegram_review"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
REVIEW_STORY = os.getenv("STORY", "").strip()
try:
    PHOTO_COUNT = int(os.getenv("PHOTO_COUNT", "4").strip() or "4")
except ValueError:
    PHOTO_COUNT = 4


def guard_bundle_multiframe(provider, frames, dry_run=False):
    frames = list(frames or [])
    if provider == "bundle" and not dry_run and len(frames) > 1:
        raise SystemExit(
            f"Bundle cannot publish {len(frames)} separate Snapchat Story photos "
            "reliably. Live publishing is blocked to prevent another one-item "
            "Story. Use Telegram review for private review."
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
    path = _sidecar_path(stamp)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"cannot read story sidecar {stamp}: {exc}")
    story = str(data.get("story") or "").strip()
    if not story:
        raise SystemExit(f"story sidecar {stamp} has no canonical story field")
    return story


def _all_sidecars():
    result = {}
    for path in Path(publisher.CARDS_DIR).glob("*-story.json"):
        try:
            result[path] = (path.stat().st_mtime_ns, path.stat().st_size)
        except OSError:
            pass
    return result


def _matching_sidecars(story):
    matches = {}
    for path in Path(publisher.CARDS_DIR).glob("*-story.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(data.get("story") or "").strip() != story:
            continue
        matches[path] = (path.stat().st_mtime_ns, path.stat().st_size)
    return matches


def _run_story_builder(story):
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
    # The build process creates files only. The wrapper is the sole Telegram
    # sender and no public publisher credentials are available to the builder.
    for key in (
        "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "BUNDLE_API_KEY",
        "BUNDLE_TEAM_ID", "BUNDLE_BASE",
    ):
        env.pop(key, None)

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
            f"story build failed for {story!r}; nothing was sent to Telegram"
        )


def _build_fresh_review_story(story):
    """Build exactly one fresh six-card deck for this review run."""
    before = _all_sidecars()
    print(f"Building fresh Telegram review story: {story}")
    _run_story_builder(story)
    after = _all_sidecars()
    changed = [
        path for path, fingerprint in after.items()
        if path not in before or before[path] != fingerprint
    ]
    if not changed:
        raise SystemExit(
            f"story build produced no fresh deck for {story!r}; "
            "nothing was sent to Telegram"
        )
    newest = max(changed, key=lambda p: p.stat().st_mtime_ns)
    stamp = newest.name[:-len("-story.json")]
    stamp, frames = publisher.find_story(stamp)
    if len(frames) != 6:
        raise SystemExit(
            f"fresh story must contain 6 cards; got {len(frames)} for {stamp}"
        )
    print(f"Fresh deck ready: {stamp} ({len(frames)} cards)")
    return stamp, frames


def _rebuild_story_for_review(story, stale_stamp):
    """Legacy compatibility wrapper used by older tests/callers."""
    return _build_fresh_review_story(story)


def approved_runtime_visuals(story):
    """Lazy import keeps publishing tests isolated from the story engine."""
    from story_runtime import approved_runtime_visuals as _approved
    return _approved(story)


def _telegram_review_photo(text, photo_path):
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
    total = len(frames)
    confirmed = 0
    for index, frame in enumerate(frames, start=1):
        text = f"👀 مراجعة قبل النشر — {stamp}\n{index}/{total}"
        if index == 1:
            text += f"\n{caption}"
        if not _telegram_review_photo(text, frame):
            raise SystemExit(
                f"Telegram confirmed only {confirmed}/{total} review photos; "
                f"frame {index} was not confirmed. Snapchat/Bundle were not called."
            )
        confirmed += 1
        print(f"    telegram review photo {index}/{total}: confirmed")
    return confirmed


def review_story_on_telegram(story, picture_count):
    """Build one fresh story and send one verified review deck to Telegram."""
    story = str(story or "").strip()
    try:
        picture_count = int(picture_count)
    except (TypeError, ValueError):
        raise SystemExit("number of pictures must be 1, 2, 3, or 4")
    if not story:
        raise SystemExit("Story is required")
    if picture_count not in (1, 2, 3, 4):
        raise SystemExit("number of pictures must be 1, 2, 3, or 4")

    stamp, frames = _build_fresh_review_story(story)
    canonical_story = _story_identity(stamp)
    photos, _logos = approved_runtime_visuals(canonical_story)
    if len(photos) < picture_count:
        raise SystemExit(
            f"{canonical_story} has only {len(photos)} approved distinct photos; "
            f"requested {picture_count}. Nothing was sent to Telegram."
        )

    # This is the deterministic contract: the requested number is applied to
    # the actual cards, then independently verified before Telegram sees them.
    apply_requested_photos(frames, photos, requested=picture_count)
    require_photo_coverage(frames, minimum=picture_count)
    caption = publisher.load_caption(stamp, len(frames))

    confirmed = _send_review_photos(stamp, caption, frames)
    print(
        f"Telegram review complete: {confirmed}/6 cards sent; "
        f"requested pictures={picture_count}; Snapchat/Bundle not called"
    )
    return stamp, frames


def review_on_telegram():
    """Legacy built-deck review retained for callers that do not pass STORY."""
    stamp, frames = _selected_story()
    caption = publisher.load_caption(stamp, len(frames))
    print(f"Telegram review: {len(frames)} frames from {stamp}")
    for path in frames:
        print(f"    {path}")
    print(f"    caption: {caption}")
    try:
        require_photo_coverage(frames, minimum=4)
    except SystemExit:
        if publisher.DRY_RUN:
            raise
        story = _story_identity(stamp)
        stamp, frames = _rebuild_story_for_review(story, stamp)
        caption = publisher.load_caption(stamp, len(frames))
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
        if REVIEW_STORY:
            review_story_on_telegram(REVIEW_STORY, PHOTO_COUNT)
        else:
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
