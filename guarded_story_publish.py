#!/usr/bin/env python3
"""Hard post-render release gate for Story-to-Snapchat.

The inventory gate decides which stories are worth attempting. This entrypoint
adds the authoritative final gate: only a rendered deck whose persisted visual
state is READY may cross the Snapchat publishing boundary. REVIEW decks remain
available for Telegram/manual review but are never auto-published.
"""

from __future__ import annotations

import os
import sys

import ready_story_publish as rsp


def require_ready_for_publication(status: str, story: str) -> None:
    """Fail closed unless the post-render deck is explicitly READY."""
    normalized = str(status or "").strip().upper()
    if normalized != "READY":
        raise SystemExit(
            f"POST_RENDER_RELEASE_BLOCKED: {story}: final status {normalized or 'UNKNOWN'}; "
            "Snapchat untouched"
        )


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
    failed = rsp.svs.failed_frame_indices(visual_state) if visual_state else ()
    final_status = "READY" if visual_state and not failed else "REVIEW"

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

    # This is the boundary Story #101 was missing. REVIEW is useful for human
    # inspection, but it is never a publishable state.
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
