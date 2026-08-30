#!/usr/bin/env python3
"""Local-only Story cost/operation report. No network or model calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def _rows(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    result = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            result.append(row)
    return result


def _ordered(rows: Iterable[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: str(row.get("timestamp") or ""))


def _limit_stories(rows: list[dict], last: int | None) -> list[dict]:
    if not last or last < 1:
        return rows
    newest: dict[str, str] = {}
    for row in rows:
        story = str(row.get("story") or "").strip()
        if story:
            newest[story] = max(newest.get(story, ""), str(row.get("timestamp") or ""))
    keep = {
        story for story, _stamp in
        sorted(newest.items(), key=lambda item: item[1], reverse=True)[:last]
    }
    return [row for row in rows if not row.get("story") or str(row.get("story")) in keep]


def summarize(
    usage_path: Path = Path("state/model_usage.jsonl"),
    notification_path: Path = Path("state/story_notifications.jsonl"),
    *,
    last: int | None = None,
) -> dict:
    usage = _ordered(_rows(Path(usage_path)))
    notifications = _ordered(_rows(Path(notification_path)))
    combined = _limit_stories(usage + notifications, last)
    allowed = {str(row.get("story")) for row in combined if row.get("story")}
    usage = [row for row in usage if not allowed or str(row.get("story")) in allowed]
    notifications = [row for row in notifications if not allowed or str(row.get("story")) in allowed]

    stories = {str(row.get("story")) for row in usage + notifications if row.get("story")}
    paid = [row for row in usage if row.get("event") == "model_result"]
    cache_hits = sum(row.get("event") == "cache_hit" for row in usage)
    visual_only = sum(str(row.get("mode") or "") == "visual_only" for row in usage)
    blocks = sum(row.get("event") == "call_block" for row in usage)

    prices = [row.get("estimated_usd") for row in paid]
    if paid and any(value is None for value in prices):
        estimated: float | str = "unpriced"
    else:
        estimated = round(sum(float(value or 0) for value in prices), 6)

    latest_state: dict[tuple[str, str], tuple[str, str]] = {}
    for row in usage:
        if row.get("event") != "final_state":
            continue
        key = (str(row.get("story") or ""), str(row.get("revision") or ""))
        latest_state[key] = (str(row.get("timestamp") or ""), str(row.get("status") or "").upper())

    statuses = [status for _stamp, status in latest_state.values()]
    return {
        "stories": len(stories),
        "paid_editorial_calls": len(paid),
        "cache_hits": int(cache_hits),
        "visual_only_runs": int(visual_only),
        "estimated_usd": estimated,
        "second_call_blocks": int(blocks),
        "ready": sum(status == "READY" for status in statuses),
        "review": sum(status == "REVIEW" for status in statuses),
        "blocked": sum(status == "BLOCKED" for status in statuses),
    }


def _print(report: dict) -> None:
    for key in (
        "stories", "paid_editorial_calls", "cache_hits", "visual_only_runs",
        "estimated_usd", "second_call_blocks", "ready", "review", "blocked",
    ):
        print(f"{key}: {report[key]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--last", type=int, default=None, help="limit to most recent unique stories")
    parser.add_argument("--usage", type=Path, default=Path("state/model_usage.jsonl"))
    parser.add_argument("--notifications", type=Path, default=Path("state/story_notifications.jsonl"))
    args = parser.parse_args()
    _print(summarize(args.usage, args.notifications, last=args.last))


if __name__ == "__main__":
    main()
