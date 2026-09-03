#!/usr/bin/env python3
"""Hard post-render release gate for Story delivery.

Automatic Story selection is fail-closed: raw image inventory is never enough
for the daily publish pool. A story must have persisted frame-level relevance
evidence and must pass the global Story quality policy before it can be frozen
as a human-ready candidate.
"""

from __future__ import annotations

import json
import os
import sys

import ready_story_publish as rsp
import story_publishability as sp
import story_quality_gate as sqg


def _personal_collect_ready_stories(stories=None, coverage_fn=None):
    """Return the globally publishable pool based on current frame evidence."""
    stories = list(rsp.sb.load_stories() if stories is None else stories)
    if coverage_fn is not None:
        ready = []
        for story in stories:
            photos, _logos, status = coverage_fn(story)
            if status == "PASS" and len(photos) >= 4:
                ready.append(story)
        return ready

    ready = []
    for story in stories:
        result = sp.evaluate_story(story)
        if result["publishable"]:
            ready.append(story)
    return ready


def _auto_story_has_visual_buffer(story):
    """Automatic selection uses persisted frame evidence, never inventory count."""
    result = sp.evaluate_story(story)
    print(
        "    auto publishability: "
        f"{result['status']} "
        f"({result['usable_frames']}/6 usable frame visual(s); "
        f"opening={'yes' if result['opening_ok'] else 'no'}; "
        f"closing={'yes' if result['closing_ok'] else 'no'}; "
        f"policy={sp.PUBLISHABILITY_POLICY})"
    )
    return bool(result["publishable"])


def _personal_resolve_story():
    # Explicit/manual Story runs remain the bootstrap/review path: they may
    # attempt an inventory-PASS story so it can earn current-policy evidence.
    if rsp.sb.STORY:
        story = rsp.sb.resolve_story_input(rsp.sb.STORY)
        photos, _logos, status = rsp.sr.coverage(story)
        if status != "PASS" or len(photos) < 4:
            raise SystemExit(
                f"requested story is not READY_FOR_RENDER: {status}: {story}"
            )
        return story
    return rsp.sr.choose_runtime_story()


rsp.collect_ready_stories = _personal_collect_ready_stories
rsp._resolve_story = _personal_resolve_story
rsp.sr._eligible_story = _auto_story_has_visual_buffer


def require_ready_for_publication(status: str, story: str) -> None:
    normalized = str(status or "").strip().upper()
    if normalized != "READY":
        raise SystemExit(
            f"POST_RENDER_RELEASE_BLOCKED: {story}: final status {normalized or 'UNKNOWN'}; "
            "Snapchat untouched"
        )


def visual_accounting(visual_state: dict, frame_count: int = 6) -> dict:
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
    """Judge the actual deck, not an inventory quota."""
    report = report or {}
    frame_count = int(report.get("frame_count", 0) or 0)
    approved_frames = {
        int(frame_no) for frame_no in (report.get("approved_visual_frames") or [])
    }
    missing = int(report.get("missing_visual_count", frame_count) or 0)
    if frame_count <= 0:
        return False
    if 1 not in approved_frames or frame_count not in approved_frames:
        return False
    return missing <= 1


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


def _frame_payloads(visual_state: dict, frame_count: int = 6) -> list[dict]:
    rows = (visual_state or {}).get("frames") or {}
    return [
        dict((rows.get(str(frame_no)) or {}).get("frame_payload") or {})
        for frame_no in range(1, int(frame_count) + 1)
    ]


def apply_quality_gate(
    story: str,
    revision: str,
    visual_state: dict,
    *,
    technical_status: str,
    save_fn=None,
):
    """Persist global quality evidence and return the human-review release state.

    A quality PASS may preserve technical READY, but it can never promote an
    already technical REVIEW candidate. This function is deterministic and has
    no publishing or model side effects.
    """
    save_fn = save_fn or rsp.svs.save_visual_state
    updated = dict(visual_state or {})
    rows = updated.get("frames") or {}
    frame_count = max(6, len(rows)) if rows else 6
    payloads = _frame_payloads(updated, frame_count=frame_count)
    quality = sqg.evaluate_story_quality(story, payloads, updated)

    updated["story_quality_policy"] = sqg.QUALITY_POLICY
    updated["story_quality_status"] = quality["status"]
    updated["story_quality_dimensions"] = quality.get("dimensions") or {}
    updated["story_quality_findings"] = quality.get("findings") or []
    updated["story_quality_frame_evidence"] = quality.get("frame_evidence") or []
    updated["story_quality_repair"] = quality.get("repair") or {}
    save_fn(story, revision, updated)

    technical = str(technical_status or "").strip().upper()
    final_status = (
        "READY"
        if technical == "READY" and sqg.release_ready(quality)
        else "REVIEW"
    )
    return final_status, quality, updated


def _persist_current_publishability(story: str, revision: str, visual_state: dict,
                                    final_status: str) -> dict:
    """Stamp and persist evidence only after current post-render QA completes."""
    updated = sp.mark_visual_state_current(
        story,
        revision,
        visual_state,
        final_status=final_status,
        save_fn=rsp.svs.save_visual_state,
    )
    rsp.persist_visual_revision(story)
    result = sp.publishability_from_visual_state(story, updated, require_assets=True)
    print(
        "PUBLISHABILITY_EVIDENCE: "
        f"{result['status']} {result['usable_frames']}/6 "
        f"policy={sp.PUBLISHABILITY_POLICY}"
    )
    return result


def main() -> None:
    refresh_only = "--refresh-only" in sys.argv
    _ready_path, ready = rsp.write_ready_file()
    if refresh_only:
        return
    if not ready and not rsp.sb.STORY:
        raise SystemExit("READY_FOR_PUBLISH is empty")

    story = rsp._resolve_story()
    if not story:
        raise SystemExit("no fresh READY_FOR_PUBLISH story available")
    print(f"Selected {'MANUAL_VALIDATION' if rsp.sb.STORY else 'READY_FOR_PUBLISH'} story: {story}")

    frames = rsp.build_story_without_posting(story)

    revision, _visual_path = rsp.resolve_visual_revision(story)
    visual_state = rsp.svs.load_visual_state(story, revision)
    visual_report = print_visual_accounting(visual_state, frame_count=len(frames))
    technical_status = (
        "READY" if visual_state and visual_report_is_ready(visual_report) else "REVIEW"
    )
    final_status, quality_report, visual_state = apply_quality_gate(
        story,
        revision,
        visual_state,
        technical_status=technical_status,
    )
    blocked_frames = (quality_report.get("repair") or {}).get("frames") or []
    print(
        "STORY_QUALITY_GATE: "
        f"{quality_report['status']} "
        f"policy={sqg.QUALITY_POLICY} "
        f"frames={blocked_frames}"
    )
    if blocked_frames:
        print(
            "STORY_QUALITY_REPAIR: "
            + json.dumps(
                quality_report.get("repair") or {},
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    publishability = _persist_current_publishability(
        story, revision, visual_state, final_status
    )

    rsp.scg.record_operation_event(
        story,
        revision,
        "final_state",
        mode=os.getenv("STORY_OPERATION_MODE", "auto"),
        status=final_status,
    )
    rsp.persist_editorial_state()
    manifest_path = rsp.write_review_manifest(
        story, revision, final_status, frames
    )
    human_approved = (os.getenv("STORY_HUMAN_APPROVED") or "").strip() == "1"
    if rsp.review_delivery_allowed(status=final_status, approved=human_approved):
        rsp.notify_final_candidate(story, frames, final_status, revision)
    else:
        print(
            f"REVIEW_GATE: {final_status} deck frozen for human review; "
            f"Telegram untouched; artifact={manifest_path}"
        )
        if not human_approved:
            print("REVIEW_REQUIRED — no Telegram or Snapchat delivery before approval")
            return

    if rsp.nb.DRY_RUN or not rsp.nb.POST_ENABLED:
        print(
            f"DRY/HYBRID — rendered {len(frames)} frames; Snapchat untouched; "
            f"publishability={publishability['status']}"
        )
        return

    require_ready_for_publication(final_status, story)
    if not publishability["publishable"]:
        raise SystemExit(
            f"POST_RENDER_RELEASE_BLOCKED: {story}: "
            f"{publishability['status']}; Snapchat untouched"
        )

    if not rsp.nb.quota_ok():
        raise SystemExit("monthly Snapchat post quota reached")

    confirmed = rsp.publish_frames_sequentially(story, frames)
    if confirmed != len(frames):
        raise SystemExit("not all Snapchat Story frames were confirmed")

    rsp._mark_story_complete(story)
    print(f"SNAPCHAT STORY COMPLETE: {story} ({confirmed}/{len(frames)} frames)")


if __name__ == "__main__":
    main()
