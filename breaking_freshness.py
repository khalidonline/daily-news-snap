"""Deterministic freshness gate for Breaking delivery.

A Breaking card may only represent an event that occurred on the current KSA
calendar date. Article publication/republication time is not event time.
"""

import re
from datetime import datetime, timedelta, timezone

KSA = timezone(timedelta(hours=3))

_EVENT_STAMP_RE = re.compile(
    r"وقت الحدث\s*:\s*(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2})(?::\d{2})?)?"
)


def parse_occurred_at(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KSA)
        return dt.astimezone(KSA)
    except ValueError:
        pass

    match = _EVENT_STAMP_RE.search(text)
    if not match:
        return None
    clock = match.group(2) or "00:00"
    return datetime.fromisoformat(
        f"{match.group(1)}T{clock}:00+03:00"
    ).astimezone(KSA)


def is_same_ksa_day(event_or_time, now):
    occurred = parse_occurred_at(event_or_time)
    if occurred is None:
        return False
    if now.tzinfo is None:
        now = now.replace(tzinfo=KSA)
    now = now.astimezone(KSA)
    return occurred.date() == now.date()
