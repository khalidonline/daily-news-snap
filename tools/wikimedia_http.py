"""Shared, policy-compliant Wikimedia request and rate-limit state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
import time


WIKIMEDIA_USER_AGENT = (
    "daily-news-snap-visual-repair-bot/1.0 "
    "(https://github.com/khalidonline/daily-news-snap)"
)
SMALL_RETRY_ALLOWANCE_SECONDS = 3.0
MAX_COOLDOWN_SECONDS = 30.0
_COOLDOWN_UNTIL = 0.0


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
        }


def cooldown_remaining(*, monotonic=time.monotonic):
    return max(0.0, _COOLDOWN_UNTIL - monotonic())


def require_available(phase, *, monotonic=time.monotonic):
    remaining = cooldown_remaining(monotonic=monotonic)
    if remaining:
        raise SourceRateLimited("commons", phase, retry_after_seconds=remaining)


def terminal_rate_limit(phase, requested_delay, *, retry_occurred=False,
                        monotonic=time.monotonic):
    """Activate a bounded process-wide Commons cooldown and return telemetry error."""
    global _COOLDOWN_UNTIL
    delay = 1.0 if requested_delay is None else max(0.0, requested_delay)
    # Even a zero/malformed Retry-After on a terminal response gets a brief
    # cooldown so the next candidate cannot immediately recreate the storm.
    bounded = min(max(1.0, delay), MAX_COOLDOWN_SECONDS)
    _COOLDOWN_UNTIL = max(_COOLDOWN_UNTIL, monotonic() + bounded)
    return SourceRateLimited("commons", phase, retry_after_seconds=bounded,
                             retry_occurred=retry_occurred)


def reset_cooldown():
    """Test/run boundary helper; production cooldown otherwise expires naturally."""
    global _COOLDOWN_UNTIL
    _COOLDOWN_UNTIL = 0.0
