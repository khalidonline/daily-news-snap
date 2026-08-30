"""Versioned, fail-closed persistence for approved story editorial briefs."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


BRIEF_SCHEMA_VERSION = "story-brief-v1"
BRIEF_ROOT = Path(os.getenv("STORY_BRIEF_ROOT", "state/story_briefs"))


class BriefCacheError(RuntimeError):
    """Raised when an existing cache entry is unsafe to reuse."""


def _brief_root() -> Path:
    # Resolve at call time so tests and isolated runs can redirect state safely.
    return Path(os.getenv("STORY_BRIEF_ROOT", str(BRIEF_ROOT)))


def _normalize_story(story: str) -> str:
    return " ".join(str(story or "").split())


def _story_id(story: str) -> str:
    return hashlib.sha256(_normalize_story(story).encode("utf-8")).hexdigest()[:16]


def _safe_revision(revision: str) -> str:
    value = str(revision or "").strip()
    if not value or not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError("revision must contain only letters, digits, dot, underscore, or hyphen")
    return value


def revision_key(story: str, prompt: str, model: str, frame_count: int) -> str:
    material = json.dumps(
        {
            "schema": BRIEF_SCHEMA_VERSION,
            "story": _normalize_story(story),
            "prompt": str(prompt or ""),
            "model": str(model or ""),
            "frame_count": int(frame_count),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def brief_path(story: str, revision: str) -> Path:
    return _brief_root() / _story_id(story) / f"{_safe_revision(revision)}.json"


def save_locked_brief(story: str, revision: str, payload: dict[str, Any]) -> Path:
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    if payload.get("status") != "EDITORIAL_LOCKED":
        raise ValueError("only EDITORIAL_LOCKED briefs may be cached")

    revision = _safe_revision(revision)
    dest = brief_path(story, revision)
    dest.parent.mkdir(parents=True, exist_ok=True)
    stored = {
        "schema": BRIEF_SCHEMA_VERSION,
        "revision": revision,
        **payload,
    }
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(
        json.dumps(stored, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(dest)
    return dest


def load_locked_brief(story: str, revision: str) -> dict[str, Any] | None:
    revision = _safe_revision(revision)
    path = brief_path(story, revision)
    if not path.exists():
        return None

    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BriefCacheError(f"malformed story brief cache: {path}") from exc

    if not isinstance(stored, dict):
        raise BriefCacheError("story brief cache must contain a JSON object")
    if stored.get("schema") != BRIEF_SCHEMA_VERSION:
        raise BriefCacheError("story brief cache schema mismatch")
    if stored.get("revision") != revision:
        raise BriefCacheError("story brief cache revision mismatch")
    if stored.get("status") != "EDITORIAL_LOCKED":
        raise BriefCacheError("story brief cache is not EDITORIAL_LOCKED")
    if "brief" not in stored or not isinstance(stored.get("brief"), dict):
        raise BriefCacheError("story brief cache is missing a valid brief object")

    return {key: value for key, value in stored.items() if key not in {"schema", "revision"}}
