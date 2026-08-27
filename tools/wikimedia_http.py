"""Shared, policy-compliant Wikimedia request and rate-limit state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import os
from pathlib import Path
import tempfile
import time


WIKIMEDIA_USER_AGENT = (
    "daily-news-snap-visual-repair-bot/1.0 "
    "(https://github.com/khalidonline/daily-news-snap)"
)
SMALL_RETRY_ALLOWANCE_SECONDS = 3.0
MAX_COOLDOWN_SECONDS = 30.0
# The persisted block can be longer than this telemetry ceiling.  This file is
# deliberately runtime output: it is shared by the controller's sequential
# story children, but is neither catalogue nor committed cursor state.
COOLDOWN_STATE_PATH = Path(os.environ.get(
    "WIKIMEDIA_COOLDOWN_STATE",
    "out/bulk-visual-repair/wikimedia-cooldown.json",
))
_MALFORMED_STATE_BLOCK_SECONDS = MAX_COOLDOWN_SECONDS
_LOCAL_BLOCKED_UNTIL = 0.0


def wikimedia_headers(*, accept=None):
    headers = {"User-Agent": WIKIMEDIA_USER_AGENT}
    if accept:
        headers["Accept"] = accept
    return headers


def parse_retry_after(value, *, now=None):
    """Parse Retry-After delta-seconds or HTTP-date; return a nonnegative delay."""
    if value is None:
        return None
    try:
        delay = float(str(value).strip())
        return max(0.0, delay) if math.isfinite(delay) else None
    except (TypeError, ValueError):
        pass
    try:
        requested = parsedate_to_datetime(str(value).strip())
        if requested.tzinfo is None:
            requested = requested.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        return max(0.0, (requested - current).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


@dataclass
class SourceRateLimited(Exception):
    source: str
    phase: str
    http_status: int = 429
    retry_after_seconds: float = 0.0
    retry_occurred: bool = False
    source_cooldown_activated: bool = True
    source_cooldown_active: bool = True

    def __str__(self):
        return (f"{self.source} {self.phase} rate limited (HTTP {self.http_status}; "
                f"bounded retry-after {self.retry_after_seconds:.3g}s)")

    def telemetry(self):
        return {
            "result": "SOURCE_RATE_LIMITED", "source": self.source,
            "phase": self.phase, "http_status": self.http_status,
            "retry_after_seconds": round(max(0.0, self.retry_after_seconds), 3),
            "retry_occurred": self.retry_occurred,
            "source_cooldown_activated": self.source_cooldown_activated,
            "source_cooldown_active": self.source_cooldown_active,
        }


def _atomic_write_blocked_until(blocked_until, path=None):
    """Best-effort atomic state write; an I/O fault must not crash a story."""
    path = Path(path or COOLDOWN_STATE_PATH)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump({"blocked_until": blocked_until}, handle)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    except (OSError, TypeError, ValueError):
        pass
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _remove_expired_state(path=None):
    try:
        Path(path or COOLDOWN_STATE_PATH).unlink(missing_ok=True)
    except OSError:
        pass


def _persisted_blocked_until(now, path=None):
    """Read shared epoch state, conservatively blocking malformed state."""
    path = Path(path or COOLDOWN_STATE_PATH)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        blocked_until = float(payload["blocked_until"])
        if not math.isfinite(blocked_until):
            raise ValueError("non-finite blocked_until")
    except FileNotFoundError:
        return 0.0
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        # A truncated atomic-state file must not accidentally reopen Commons.
        # Leave it malformed: every separately initialized story child will
        # independently fail closed until an operator removes the bad state.
        return now + _MALFORMED_STATE_BLOCK_SECONDS
    if blocked_until <= now:
        _remove_expired_state(path)
        return 0.0
    return blocked_until


def cooldown_remaining(*, now=None, path=None):
    current = time.time() if now is None else now
    blocked_until = max(_LOCAL_BLOCKED_UNTIL,
                        _persisted_blocked_until(current, path))
    return max(0.0, blocked_until - current)


def require_available(phase, *, now=None, path=None):
    remaining = cooldown_remaining(now=now, path=path)
    if remaining:
        raise SourceRateLimited(
            "commons", phase,
            retry_after_seconds=min(remaining, MAX_COOLDOWN_SECONDS),
            source_cooldown_activated=False,
        )


def terminal_rate_limit(phase, requested_delay, *, retry_occurred=False,
                        now=None, path=None):
    """Persist the full requested block while keeping telemetry bounded."""
    global _LOCAL_BLOCKED_UNTIL
    current = time.time() if now is None else now
    delay = 1.0 if requested_delay is None else max(0.0, requested_delay)
    # Even a zero/malformed Retry-After on a terminal response gets a brief
    # cooldown so the next candidate cannot immediately recreate the storm.
    requested_blocked_until = current + max(1.0, delay)
    existing = max(_LOCAL_BLOCKED_UNTIL,
                   _persisted_blocked_until(current, path))
    blocked_until = max(existing, requested_blocked_until)
    activated = blocked_until > existing
    _LOCAL_BLOCKED_UNTIL = blocked_until
    _atomic_write_blocked_until(blocked_until, path)
    remaining = blocked_until - current
    return SourceRateLimited(
        "commons", phase,
        retry_after_seconds=min(remaining, MAX_COOLDOWN_SECONDS),
        retry_occurred=retry_occurred,
        source_cooldown_activated=activated,
    )


def reset_cooldown(*, path=None):
    """Test helper; production state otherwise expires and removes itself."""
    global _LOCAL_BLOCKED_UNTIL
    _LOCAL_BLOCKED_UNTIL = 0.0
    _remove_expired_state(path)
