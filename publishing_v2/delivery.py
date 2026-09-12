"""Durable, local reference implementation of frame delivery."""

from __future__ import annotations

import fcntl
import hashlib
import os
import sqlite3
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

_RIYADH = ZoneInfo("Asia/Riyadh")


class DeliveryError(RuntimeError):
    pass


class TemporaryDeliveryError(DeliveryError):
    """The provider definitely did not accept the frame."""


class AmbiguousDeliveryError(DeliveryError):
    """The provider may have accepted the frame."""


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def theme_expiry(activated_at: datetime) -> datetime:
    _aware(activated_at, "activated_at")
    local_date = activated_at.astimezone(_RIYADH).date() + timedelta(days=2)
    return datetime.combine(local_date, time.min, tzinfo=_RIYADH)


def theme_active(activated_at: datetime, now: datetime) -> bool:
    _aware(activated_at, "activated_at")
    _aware(now, "now")
    return activated_at <= now < theme_expiry(activated_at)


def _instant(value: datetime) -> str:
    _aware(value, "expires_at")
    return value.astimezone(timezone.utc).isoformat()


class DeliveryStore:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_dir = self.path.parent / f"{self.path.name}.locks"
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS delivery_posts (
                    post_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    format TEXT NOT NULL,
                    outcome TEXT
                );
                CREATE TABLE IF NOT EXISTS delivery_frames (
                    post_id TEXT NOT NULL,
                    frame_index INTEGER NOT NULL,
                    path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('pending','sending','delivered','unknown')),
                    receipt TEXT,
                    PRIMARY KEY(post_id, frame_index),
                    FOREIGN KEY(post_id) REFERENCES delivery_posts(post_id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _post_lock(self, post_id: str):
        lock_name = hashlib.sha256(post_id.encode("utf-8")).hexdigest() + ".lock"
        descriptor = os.open(self.lock_dir / lock_name, os.O_CREAT | os.O_RDWR, 0o600)
        acquired = False
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                pass
            yield acquired
        finally:
            if acquired:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def prepare(self, post_id: str, event_id: str, expires_at: datetime, frames: Iterable[str | os.PathLike[str]], *, format: str) -> dict[str, Any]:
        frame_paths = [str(Path(path).resolve()) for path in frames]
        normalized_format = format.lower()
        required = 6 if normalized_format == "story" else 1 if normalized_format in {"info", "topic"} else None
        if required is None:
            raise ValueError("format must be info, topic, or story")
        if len(frame_paths) != required:
            raise ValueError(f"{normalized_format} requires exactly {required} frame(s)")
        digests = []
        try:
            for path in frame_paths:
                digests.append(hashlib.sha256(Path(path).read_bytes()).hexdigest())
        except OSError as exc:
            raise DeliveryError("A prepared frame is not readable.") from exc
        expiry = _instant(expires_at)

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT event_id, expires_at, format FROM delivery_posts WHERE post_id = ?", (post_id,)).fetchone()
            if existing:
                rows = connection.execute("SELECT path, sha256 FROM delivery_frames WHERE post_id = ? ORDER BY frame_index", (post_id,)).fetchall()
                stored = [(row["path"], row["sha256"]) for row in rows]
                requested = list(zip(frame_paths, digests))
                if (existing["event_id"], existing["expires_at"], existing["format"], stored) != (event_id, expiry, normalized_format, requested):
                    raise DeliveryError("Prepared delivery payload is immutable.")
            else:
                connection.execute(
                    "INSERT INTO delivery_posts(post_id, event_id, expires_at, format) VALUES (?, ?, ?, ?)",
                    (post_id, event_id, expiry, normalized_format),
                )
                connection.executemany(
                    "INSERT INTO delivery_frames(post_id, frame_index, path, sha256, state) VALUES (?, ?, ?, ?, 'pending')",
                    [(post_id, index, path, digest) for index, (path, digest) in enumerate(zip(frame_paths, digests))],
                )
        return self.status(post_id)

    def status(self, post_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            post = connection.execute("SELECT * FROM delivery_posts WHERE post_id = ?", (post_id,)).fetchone()
            if post is None:
                raise DeliveryError("Delivery is not prepared.")
            rows = connection.execute("SELECT * FROM delivery_frames WHERE post_id = ? ORDER BY frame_index", (post_id,)).fetchall()
        frames = [
            {"frame_index": row["frame_index"], "path": row["path"], "sha256": row["sha256"], "state": row["state"], "receipt": row["receipt"]}
            for row in rows
        ]
        states = {frame["state"] for frame in frames}
        status = post["outcome"]
        expected_count = 6 if post["format"] == "story" else 1
        complete = len(frames) == expected_count and all(
            frame["state"] == "delivered" and bool(frame["receipt"])
            for frame in frames
        )
        if status == "delivered":
            status = "delivered" if complete else "unknown"
        elif status is None:
            missing_receipt = any(frame["state"] == "delivered" and not frame["receipt"] for frame in frames)
            malformed_count = len(frames) != expected_count
            status = "unknown" if "unknown" in states or missing_receipt or malformed_count else "sending" if "sending" in states else "pending" if "pending" in states else "delivered"
        return {
            "post_id": post["post_id"],
            "event_id": post["event_id"],
            "expires_at": post["expires_at"],
            "format": post["format"],
            "status": status,
            "frames": frames,
        }

    def _set_outcome(self, post_id: str, outcome: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("UPDATE delivery_posts SET outcome = ? WHERE post_id = ?", (outcome, post_id))
        return self.status(post_id)

    def deliver(self, post_id: str, sender: Callable[[str, str], str], now: datetime | Callable[[], datetime]) -> dict[str, Any]:
        with self._post_lock(post_id) as acquired:
            if not acquired:
                return self.status(post_id)
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                post = connection.execute("SELECT * FROM delivery_posts WHERE post_id = ?", (post_id,)).fetchone()
                if post is None:
                    raise DeliveryError("Delivery is not prepared.")
                connection.execute("UPDATE delivery_frames SET state = 'unknown' WHERE post_id = ? AND state = 'sending'", (post_id,))
            current = self.status(post_id)
            if current["status"] in {"unknown", "delivered", "expired", "artifact_changed"}:
                return current

            # Validate the complete immutable deck before any external side effect.
            for frame in current["frames"]:
                try:
                    digest = hashlib.sha256(Path(frame["path"]).read_bytes()).hexdigest()
                except OSError:
                    return self._set_outcome(post_id, "artifact_changed")
                if digest != frame["sha256"]:
                    return self._set_outcome(post_id, "artifact_changed")

            expiry = datetime.fromisoformat(current["expires_at"])
            started = monotonic() if not callable(now) else None
            for frame in current["frames"]:
                if frame["state"] == "delivered":
                    continue
                try:
                    digest = hashlib.sha256(Path(frame["path"]).read_bytes()).hexdigest()
                except OSError:
                    return self._set_outcome(post_id, "artifact_changed")
                if digest != frame["sha256"]:
                    return self._set_outcome(post_id, "artifact_changed")
                moment = now() if callable(now) else now + timedelta(seconds=monotonic() - started)
                _aware(moment, "now")
                if moment >= expiry:
                    return self._set_outcome(post_id, "expired")
                with self._connect() as connection:
                    updated = connection.execute(
                        "UPDATE delivery_frames SET state = 'sending' WHERE post_id = ? AND frame_index = ? AND state = 'pending'",
                        (post_id, frame["frame_index"]),
                    )
                    if updated.rowcount != 1:
                        raise DeliveryError("Frame state changed before sending.")
                key = f"{post_id}:{frame['frame_index']}:{frame['sha256']}"
                try:
                    receipt = sender(frame["path"], key)
                    if not isinstance(receipt, str) or not receipt.strip():
                        raise AmbiguousDeliveryError("Provider returned no receipt.")
                except TemporaryDeliveryError:
                    with self._connect() as connection:
                        connection.execute("UPDATE delivery_frames SET state = 'pending' WHERE post_id = ? AND frame_index = ?", (post_id, frame["frame_index"]))
                    return self.status(post_id)
                except Exception:
                    with self._connect() as connection:
                        connection.execute("UPDATE delivery_frames SET state = 'unknown' WHERE post_id = ? AND frame_index = ?", (post_id, frame["frame_index"]))
                    return self.status(post_id)
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE delivery_frames SET state = 'delivered', receipt = ? WHERE post_id = ? AND frame_index = ?",
                        (receipt, post_id, frame["frame_index"]),
                    )
            return self._set_outcome(post_id, "delivered")

    def resolve_unknown(self, post_id: str, frame_index: int, receipt: str | None = None, definitely_not_sent: bool = False) -> dict[str, Any]:
        has_receipt = isinstance(receipt, str) and bool(receipt.strip())
        if has_receipt == (definitely_not_sent is True):
            raise ValueError("Provide exactly one of a receipt or definite proof the frame was not sent.")
        with self._post_lock(post_id) as acquired:
            if not acquired:
                raise DeliveryError("Delivery is active.")
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT state FROM delivery_frames WHERE post_id = ? AND frame_index = ?", (post_id, frame_index)
                ).fetchone()
                if row is None:
                    raise DeliveryError("Delivery frame does not exist.")
                if row["state"] != "unknown":
                    raise DeliveryError("Only an unknown frame can be resolved.")
                state = "delivered" if has_receipt else "pending"
                connection.execute(
                    "UPDATE delivery_frames SET state = ?, receipt = ? WHERE post_id = ? AND frame_index = ?",
                    (state, receipt if has_receipt else None, post_id, frame_index),
                )
                connection.execute("UPDATE delivery_posts SET outcome = NULL WHERE post_id = ?", (post_id,))
        return self.status(post_id)
