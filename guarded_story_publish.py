#!/usr/bin/env python3
"""Hard post-render release gate for Story-to-Snapchat.

This is a personal Snapchat story, not a corporate asset pipeline. The inventory
gate asks only whether enough reviewed relevant visuals exist to attempt the
story; logos are optional. The rendered deck is authoritative and may contain
at most one genuinely text-only card.
"""

from __future__ import annotations

import os
import sys

import ready_story_publish as rsp


def _personal_collect_ready_stories(stories=None, coverage_fn=None):
    stories = list(rsp.sb.load_stories() if stories is None else stories)
    coverage_fn = coverage_fn or rsp.sr.coverage
    ready = []
    for story in stories:
        photos, _logos, status = coverage_fn(story)
        if status == "PASS" and len(photos) >= 4:
            ready.append(story)
    return ready


def _personal_resolve_story():
    if rsp.sb.STORY:
        story = rsp.sb.resolve_story_input(rsp.sb.STORY)
        photos, _logos, status = rsp.sr.coverage(story)
        if status != "PASS" or len(photos) < 4:
            raise SystemExit(
                f"requested story is not READY_FOR_SNAP: {status}: {story}"
            )
        return story
    return rsp.sr.choose_runtime_story()


# Keep the legacy publisher helpers, but replace its corporate-style inventory
# assumptions for this guarded Story entrypoint only.
rsp.collect_ready_stories = _personal_collect_ready_stories
rsp._resolve_story = _personal_resolve_story


def require_ready_for_publication(status: str, story: str) -> None:
    """Fail closed unless the post-render deck is explicitly READY."""
    normalized = str(status or "").strip().upper()
    if normalized != "READY":
        raise SystemExit(
            f"POST_RENDER_RELEASE_BLOCKED: {story}: final status {normalized or 'UNKNOWN'}; "
            "Snapchat untouched"
        )


def visual_accounting(visual_state: dict, frame_count: int = 6) -> dict:
    """Report approved visual slots from persisted post-render state."""
    rows = (visual_state or {}).get("frames") or {}
    approved = []
    missing = []
    for frame_no in range(1, int(frame_count) + 1):
        row = rows.get(str(frame_no)) or {}
        if isinstance(row, dict) and row.get("status") == "PASS":
            approved.append(frame_no)
        else:
            missing.append(frame_no)
    return {
        "approved_visual_frames": approved,
        "missing_visual_frames": missing,
        "approved_visual_count": len(approved),
        "missing_visual_count": len(missing),
        "frame_count": int(frame_count),
    }


def visual_report_is_ready(report: dict) -> bool:
    """A personal Story needs strong visual coverage, not six corporate assets."""
    frame_count = int((report or {}).get("frame_count", 0) or 0)
    approved = int((report or {}).get("approved_visual_count", 0) or 0)
    missing = int((report or {}).get("missing_visual_count", frame_count) or 0)
    required = min(4, frame_count)
    return frame_count > 0 and approved >= required and missing <= 1


def print_visual_accounting(visual_state: dict, frame_count: int = 6) -> dict:
    report = visual_accounting(visual_state, frame_count=frame_count)
    print(
        "POST_RENDER_VISUAL_ACCOUNTING: "
        f"approved={report['approved_visual_count']}/{report['frame_count']} "
        f"frames={report['approved_visual_frames']}; "
        f"missing={report['missing_visual_count']}/{report['frame_count']} "
        f"frames={report['missing_visual_frames']}"
    )
    return report


def main() -> None:
    refresh_only = "--refresh-only" in sys.argv
    _ready_path, ready = rsp.write_ready_file()
    if refresh_only:
        return
    if not ready:
        raise SystemExit("READY_FOR_SNAP is empty")

    story = rsp._resolve_story()
    if not story:
        raise SystemExit("no fresh READY_FOR_SNAP story available")
    print(f"Selected READY_FOR_SNAP story: {story}")

    frames = rsp.build_story_without_posting(story)

    revision, _visual_path = rsp.resolve_visual_revision(story)
    visual_state = rsp.svs.load_visual_state(story, revision)
    report = print_visual_accounting(visual_state, frame_count=len(frames))
    final_status = "READY" if visual_state and visual_report_is_ready(report) else "REVIEW"

    rsp.scg.record_operation_event(
        story,
        revision,
        "final_state",
        mode=os.getenv("STORY_OPERATION_MODE", "auto"),
        status=final_status,
    )
    rsp.persist_editorial_state()
    rsp.notify_final_candidate(story, frames, final_status, revision)

    if rsp.nb.DRY_RUN or not rsp.nb.POST_ENABLED:
        print(f"DRY/HYBRID — rendered {len(frames)} frames; Snapchat untouched")
        return

    require_ready_for_publication(final_status, story)

    if not rsp.nb.quota_ok():
        raise SystemExit("monthly Snapchat post quota reached")

    confirmed = rsp.publish_frames_sequentially(story, frames)
    if confirmed != len(frames):
        raise SystemExit("not all Snapchat Story frames were confirmed")

    rsp._mark_story_complete(story)
    print(f"SNAPCHAT STORY COMPLETE: {story} ({confirmed}/{len(frames)} frames)")


if __name__ == "__main__":
    main()
