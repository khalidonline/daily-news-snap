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

from PIL import Image, ImageDraw

import news_bot as nb
import story_bot as sb
import story_runtime as sr
import story_visual_state as svs
import story_notification_state as sns
import story_cost_guard as scg


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


def persist_editorial_state(commit_fn=None):
    """Persist spend guard/cache evidence created by the child, even on failure."""
    commit_fn = commit_fn or sb.commit_and_push
    cost_root = Path(os.getenv("STORY_COST_STATE_ROOT", "state"))
    targets = [
        cost_root / "model_usage.jsonl",
        cost_root / "model_call_guard",
        Path(os.getenv("STORY_BRIEF_ROOT", "state/story_briefs")),
    ]
    for target in targets:
        if target.exists():
            commit_fn(target, f"story editorial state: {target.name}")


def persist_visual_revision(
    story,
    *,
    revision_fn=None,
    state_dir_fn=None,
    commit_fn=None,
):
    """Commit the revision-scoped visual state/assets after a successful build."""
    revision_fn = revision_fn or (lambda value: svs._effective_revision(sb, value))
    state_dir_fn = state_dir_fn or svs.visual_revision_dir
    commit_fn = commit_fn or sb.commit_and_push
    revision = revision_fn(story)
    path = Path(state_dir_fn(story, revision))
    if path.exists():
        commit_fn(path, f"story visual state: {revision[:12]}")
    return path


def persist_notification_state(commit_fn=None):
    commit_fn = commit_fn or sb.commit_and_push
    claims = sns.notification_claim_dir()
    ledger = sns.notification_ledger_path()
    if claims.exists():
        commit_fn(claims, "story notification claims")
    if ledger.exists():
        commit_fn(ledger, "story notification ledger")


def notify_final_candidate(
    story,
    frames,
    status,
    revision,
    digest=None,
    *,
    claim_fn=None,
    notify_fn=None,
    complete_fn=None,
    release_fn=None,
    persist_fn=None,
):
    """Send one final READY/REVIEW Telegram album for a unique rendered deck."""
    status = str(status or "").strip().upper()
    if not sns.should_notify(status):
        return False
    frames = list(frames or [])
    digest = digest or sns.deck_hash(frames)
    claim_fn = claim_fn or sns.claim_notification
    notify_fn = notify_fn or sb.notify_album
    complete_fn = complete_fn or sns.complete_notification
    release_fn = release_fn or sns.release_notification
    persist_fn = persist_fn or persist_notification_state

    claim = claim_fn(story, revision, status, digest)
    if claim is None:
        print(f"    Telegram {status} candidate unchanged — duplicate suppressed")
        return False
    try:
        notify_fn(
            f"[{status}] {story}\nFinal publication candidate",
            frames,
            as_documents=True,
        )
    except Exception:
        release_fn(claim)
        raise
    complete_fn(claim, story, revision, status, digest)
    persist_fn()
    print(f"    Telegram final candidate sent: {status}")
    return True


def build_story_without_posting(story):
    """Render one fresh strict-PASS deck without changing posting state."""
    before = _frame_snapshot()
    env = os.environ.copy()
    env.update({
        "STORY": story,
        "DRY_RUN": "1",
        "POST_TO_SNAPCHAT": "0",
        "STORY_SUPPRESS_TELEGRAM": "1",
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
    # The child owns paid-call/cache writes. Persist them before interpreting
    # its exit status so a failed render cannot erase a reservation on the
    # next clean GitHub runner and accidentally buy the same revision again.
    persist_editorial_state()
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
    persist_visual_revision(story)
    return changed


def _logo_panel_color(logo):
    rgba = logo.convert("RGBA")
    pixels = [px for px in rgba.getdata() if px[3] > 32]
    if not pixels:
        return (248, 248, 246, 245)
    avg = sum((0.2126 * r + 0.7152 * g + 0.0722 * b) for r, g, b, _ in pixels) / len(pixels)
    return (24, 56, 97, 245) if avg >= 150 else (248, 248, 246, 245)


def ensure_subject_logo_visible(story, frames, coverage_fn=None):
    """Guarantee a readable approved subject logo on the first Story frame."""
    frames = list(frames or [])
    if not frames:
        return frames
    coverage_fn = coverage_fn or sr.coverage
    _photos, logos, status = coverage_fn(story)
    if status != "PASS" or not logos:
        return frames

    logo_path = Path(logos[0])
    try:
        logo = Image.open(logo_path).convert("RGBA")
        bbox = logo.getbbox()
        if bbox:
            logo = logo.crop(bbox)
        frame_path = Path(frames[0])
        card = Image.open(frame_path).convert("RGBA")
    except Exception as exc:
        print(f"    logo visibility safeguard skipped: {exc}")
        return frames

    panel_w, panel_h = 260, 160
    x0, y0 = 700, 455
    x1, y1 = x0 + panel_w, y0 + panel_h
    overlay = Image.new("RGBA", card.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    panel = _logo_panel_color(logo)
    draw.rounded_rectangle((x0, y0, x1, y1), radius=26, fill=panel)

    max_w, max_h = 210, 110
    scale = min(max_w / max(1, logo.width), max_h / max(1, logo.height))
    size = (max(1, int(logo.width * scale)), max(1, int(logo.height * scale)))
    rendered_logo = logo.resize(size, Image.LANCZOS)
    lx = x0 + (panel_w - rendered_logo.width) // 2
    ly = y0 + (panel_h - rendered_logo.height) // 2
    overlay.alpha_composite(rendered_logo, (lx, ly))
    card = Image.alpha_composite(card, overlay)
    card.convert("RGB").save(frame_path, "PNG")
    print(f"    subject logo visibility safeguard: {logo_path.name} on frame 1")
    return frames


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
    ensure_subject_logo_visible(story, frames)

    revision = svs._effective_revision(sb, story)
    visual_state = svs.load_visual_state(story, revision)
    final_status = (
        "READY"
        if visual_state and not svs.failed_frame_indices(visual_state)
        else "REVIEW"
    )
    scg.record_operation_event(
        story,
        revision,
        "final_state",
        mode=os.getenv("STORY_OPERATION_MODE", "auto"),
        status=final_status,
    )
    persist_editorial_state()
    notify_final_candidate(story, frames, final_status, revision)

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
