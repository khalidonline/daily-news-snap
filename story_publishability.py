#!/usr/bin/env python3
"""Fail-closed Story publishability based on persisted frame-level evidence.

Automatic daily Story selection must not infer readiness from raw inventory.
Only a deck that has completed the current frame-relevance policy may enter the
publish pool. Old evidence from before the frame-level relevance hardening is
stale by design and requires an explicit dry validation to become current.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PUBLISHABILITY_POLICY = "frame-relevance-v2"
DEFAULT_VISUAL_ROOT = Path("state/story_visuals")


def _story_id(story: str) -> str:
    normalized = " ".join(str(story or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def publishability_from_visual_state(
    story: str,
    state: dict[str, Any] | None,
    *,
    frame_count: int = 6,
    require_assets: bool = False,
) -> dict[str, Any]:
    """Judge whether persisted renderer evidence is safe for auto-selection."""
    state = state or {}
    result = {
        "story": story,
        "policy": PUBLISHABILITY_POLICY,
        "status": "BLOCKED_NO_FRAME_EVIDENCE",
        "publishable": False,
        "usable_frames": 0,
        "missing_frames": list(range(1, int(frame_count) + 1)),
        "opening_ok": False,
        "closing_ok": False,
    }
    if not state:
        return result

    if str(state.get("story") or "").strip() != str(story or "").strip():
        result["status"] = "BLOCKED_STALE_EVIDENCE"
        return result
    if state.get("publishability_policy") != PUBLISHABILITY_POLICY:
        result["status"] = "BLOCKED_STALE_EVIDENCE"
        return result

    rows = state.get("frames") or {}
    if not isinstance(rows, dict):
        return result

    approved: list[int] = []
    missing: list[int] = []
    for frame_no in range(1, int(frame_count) + 1):
        row = rows.get(str(frame_no)) or {}
        passed = isinstance(row, dict) and row.get("status") == "PASS"
        if passed and require_assets:
            source = Path(str(row.get("image_source") or ""))
            passed = source.exists() and source.is_file()
        (approved if passed else missing).append(frame_no)

    opening_ok = 1 in approved
    closing_ok = int(frame_count) in approved
    publishable = opening_ok and closing_ok and len(missing) <= 1
    result.update({
        "status": "READY_FOR_PUBLISH" if publishable else "BLOCKED_FRAME_COVERAGE",
        "publishable": publishable,
        "usable_frames": len(approved),
        "approved_frames": approved,
        "missing_frames": missing,
        "opening_ok": opening_ok,
        "closing_ok": closing_ok,
    })
    return result


def _load_state_path(
    path: Path,
    load_fn: Callable[[Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if load_fn is not None:
        try:
            payload = load_fn(path)
        except (OSError, ValueError, TypeError):
            return {}
        return payload if isinstance(payload, dict) else {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {key: value for key, value in payload.items() if key != "schema"}


def latest_visual_state(
    story: str,
    *,
    root: str | Path = DEFAULT_VISUAL_ROOT,
    load_fn: Callable[[Path], dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return the newest meaningful persisted visual evidence for a story.

    Git checkouts commonly give many files the same filesystem mtime, so mtime
    is only a final fallback. Current-policy states rank ahead of legacy states,
    and among current states the persisted evaluation timestamp is authoritative.
    """
    root = Path(root)
    parent = root / _story_id(story)
    candidates: list[tuple[tuple[Any, ...], str, dict[str, Any]]] = []
    if parent.exists():
        for path in parent.glob("*/state.json"):
            state = _load_state_path(path, load_fn=load_fn)
            if not state:
                continue
            try:
                mtime = path.stat().st_mtime_ns
            except OSError:
                mtime = 0
            current_policy = int(
                state.get("publishability_policy") == PUBLISHABILITY_POLICY
            )
            evaluated_at = str(state.get("publishability_evaluated_at") or "")
            revision = path.parent.name
            rank = (current_policy, evaluated_at, mtime, revision)
            candidates.append((rank, revision, state))
    if not candidates:
        return "", {}
    _rank, revision, state = max(candidates, key=lambda item: item[0])
    return revision, state


def evaluate_story(
    story: str,
    *,
    root: str | Path = DEFAULT_VISUAL_ROOT,
    require_assets: bool = True,
) -> dict[str, Any]:
    revision, state = latest_visual_state(story, root=root)
    result = publishability_from_visual_state(
        story,
        state,
        require_assets=require_assets,
    )
    result["revision"] = revision
    return result


def mark_visual_state_current(
    story: str,
    revision: str,
    state: dict[str, Any],
    *,
    final_status: str,
    save_fn: Callable[[str, str, dict[str, Any]], Any],
) -> dict[str, Any]:
    """Stamp evidence only after the current renderer has reached final QA."""
    updated = dict(state or {})
    updated["story"] = story
    updated["revision"] = revision
    updated["publishability_policy"] = PUBLISHABILITY_POLICY
    updated["final_release_status"] = str(final_status or "").strip().upper()
    updated["publishability_evaluated_at"] = datetime.now(timezone.utc).isoformat()
    save_fn(story, revision, updated)
    return updated
