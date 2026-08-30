"""Final Story candidate notification dedupe with concurrency-safe claims."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


NOTIFIABLE_STATUSES = frozenset({"READY", "REVIEW"})


def notification_ledger_path() -> Path:
    return Path(os.getenv("STORY_NOTIFICATION_LEDGER", "state/story_notifications.jsonl"))


def notification_claim_dir() -> Path:
    ledger = notification_ledger_path()
    return ledger.parent / "story_notification_claims"


def should_notify(status: str) -> bool:
    return str(status or "").strip().upper() in NOTIFIABLE_STATUSES


def deck_hash(frames: Iterable[object]) -> str:
    digest = hashlib.sha256()
    for index, raw in enumerate(frames, start=1):
        path = Path(str(raw))
        digest.update(f"{index}:".encode("utf-8"))
        if not path.exists() or not path.is_file():
            digest.update(b"<missing>")
            digest.update(str(path).encode("utf-8"))
            continue
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _notification_key(story: str, revision: str, status: str, digest: str) -> str:
    material = json.dumps(
        {
            "story": " ".join(str(story or "").split()),
            "revision": str(revision or ""),
            "status": str(status or "").strip().upper(),
            "deck_hash": str(digest or ""),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def claim_notification(
    story: str, revision: str, status: str, digest: str
) -> Path | None:
    normalized_status = str(status or "").strip().upper()
    if not should_notify(normalized_status):
        return None
    key = _notification_key(story, revision, normalized_status, digest)
    claims = notification_claim_dir()
    claims.mkdir(parents=True, exist_ok=True)
    marker = claims / f"{key}.claim"
    try:
        with marker.open("x", encoding="utf-8") as handle:
            json.dump(
                {
                    "story": story,
                    "revision": revision,
                    "status": normalized_status,
                    "deck_hash": digest,
                    "claimed_at": datetime.now(timezone.utc).isoformat(),
                },
                handle,
                ensure_ascii=False,
                sort_keys=True,
            )
            handle.write("\n")
    except FileExistsError:
        return None
    return marker


def release_notification(claim: Path | None) -> None:
    if claim is not None:
        Path(claim).unlink(missing_ok=True)


def complete_notification(
    claim: Path,
    story: str,
    revision: str,
    status: str,
    digest: str,
) -> Path:
    claim = Path(claim)
    if not claim.exists():
        raise RuntimeError("notification claim disappeared before completion")
    ledger = notification_ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "telegram_sent",
        "story": story,
        "revision": revision,
        "status": str(status or "").strip().upper(),
        "deck_hash": digest,
        "run_id": os.getenv("GITHUB_RUN_ID") or None,
        "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT") or None,
    }
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    # Marker intentionally remains as the concurrency-safe durable dedupe key.
    return ledger
