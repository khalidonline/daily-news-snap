#!/usr/bin/env python3
"""Build the persisted publication-ready story pool.

Visual source coverage is a repair/input gate. A story belongs in the live
READY_TO_POST pool only after it also has locked editorial content and a
committed six-frame rendered visual state.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import story_bot as sb
import story_brief_store as sbs
import story_runtime as sr
import story_visual_state as svs


READY_FILE = Path(os.getenv("READY_STORIES_FILE", "state/ready_to_post.json"))
EXPECTED_FRAMES = int(os.getenv("STORY_FRAMES", "6") or "6")


def _story_id(story: str) -> str:
    normalized = " ".join(str(story or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _read_json_object(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def has_locked_editorial(story: str, *, brief_root: Path | None = None) -> bool:
    root = Path(brief_root or os.getenv("STORY_BRIEF_ROOT", "state/story_briefs"))
    story_dir = root / _story_id(story)
    if not story_dir.exists():
        return False
    for path in sorted(story_dir.glob("*.json")):
        payload = _read_json_object(path)
        if (
            payload.get("schema") == sbs.BRIEF_SCHEMA_VERSION
            and payload.get("revision") == path.stem
            and payload.get("status") == "EDITORIAL_LOCKED"
            and isinstance(payload.get("brief"), dict)
        ):
            return True
    return False


def has_complete_rendered_state(
    story: str,
    *,
    visual_root: Path | None = None,
    expected_frames: int = EXPECTED_FRAMES,
) -> bool:
    root = Path(visual_root or os.getenv("STORY_VISUAL_STATE_ROOT", "state/story_visuals"))
    story_dir = root / _story_id(story)
    if not story_dir.exists():
        return False
    expected = int(expected_frames)
    for state_path in sorted(story_dir.glob("*/state.json")):
        state = _read_json_object(state_path)
        frames = state.get("frames") or {}
        if state.get("schema") != svs.VISUAL_STATE_SCHEMA:
            continue
        if state.get("story") != story or state.get("status") != "VISUAL_READY":
            continue
        if state.get("revision") != state_path.parent.name:
            continue
        if not isinstance(frames, dict) or len(frames) != expected:
            continue
        if all(
            isinstance(frames.get(str(frame_no)), dict)
            and frames[str(frame_no)].get("status") == "PASS"
            for frame_no in range(1, expected + 1)
        ):
            return True
    return False


def publication_evidence_ready(
    story: str,
    *,
    locked_fn=None,
    rendered_fn=None,
) -> bool:
    locked_fn = locked_fn or has_locked_editorial
    rendered_fn = rendered_fn or has_complete_rendered_state
    return bool(locked_fn(story) and rendered_fn(story))


def collect_publication_ready_stories(
    stories=None,
    *,
    coverage_fn=None,
    evidence_fn=None,
):
    stories = list(sb.load_stories() if stories is None else stories)
    coverage_fn = coverage_fn or sr.coverage
    evidence_fn = evidence_fn or publication_evidence_ready
    ready = []
    for story in stories:
        photos, logos, status = coverage_fn(story)
        if (
            status == "PASS"
            and len(photos) >= 4
            and len(logos) >= 1
            and evidence_fn(story)
        ):
            ready.append(story)
    return ready


def write_ready_file(path: Path = READY_FILE):
    ready = collect_publication_ready_stories()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ready_count": len(ready),
        "total_stories": len(sb.load_stories()),
        "basis": "visual PASS + EDITORIAL_LOCKED + committed six-frame VISUAL_READY",
        "stories": ready,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"READY_TO_POST={len(ready)}/{payload['total_stories']}")
    for story in ready:
        print(f"READY_TO_POST_STORY {story}")
    return path, ready


def main() -> None:
    write_ready_file()


if __name__ == "__main__":
    main()
