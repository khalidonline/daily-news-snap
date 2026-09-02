#!/usr/bin/env python3
"""Shared KSA slot gate for News, Topic, and Story workflows.

External schedulers may provide an explicit ISO slot. GitHub cron may call the
same gate without one as a temporary fallback. A durable per-bot ledger keeps
both trigger paths idempotent.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KSA = ZoneInfo("Asia/Riyadh")
RECOVERY_WINDOW_MINUTES = 90

BOT_SLOTS = {
    "news": tuple((hour, 10) for hour in (7, 9, 11, 13, 15, 17, 19, 21, 23)),
    "topic": ((9, 0),),
    "story": ((14, 0),),
}


def slot_id(slot: datetime) -> str:
    return slot.isoformat(timespec="minutes")


def slots_for_day(bot: str, now: datetime) -> list[datetime]:
    if bot not in BOT_SLOTS:
        raise ValueError(f"unknown bot: {bot}")
    local = now.astimezone(KSA)
    return [
        local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        for hour, minute in BOT_SLOTS[bot]
    ]


def _parse_requested_slot(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(KSA).replace(second=0, microsecond=0)


def _is_valid_bot_slot(bot: str, slot: datetime) -> bool:
    return (slot.hour, slot.minute) in BOT_SLOTS.get(bot, ())


def resolve_slot(
    *,
    bot: str,
    now: datetime,
    completed: set[str],
    requested_slot: str = "",
) -> str | None:
    local_now = now.astimezone(KSA)

    if requested_slot:
        requested = _parse_requested_slot(requested_slot)
        if requested is None or not _is_valid_bot_slot(bot, requested):
            return None
        identifier = slot_id(requested)
        if identifier in completed:
            return None
        return identifier

    due = [slot for slot in slots_for_day(bot, local_now) if slot <= local_now]
    if not due:
        return None
    latest = due[-1]
    if local_now - latest > timedelta(minutes=RECOVERY_WINDOW_MINUTES):
        return None
    identifier = slot_id(latest)
    if identifier in completed:
        return None
    return identifier


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"completed_slots": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"completed_slots": []}
    completed = data.get("completed_slots", [])
    if not isinstance(completed, list):
        completed = []
    return {"completed_slots": [str(item) for item in completed if item]}


def completed_slots(path: Path) -> set[str]:
    return set(load_state(path)["completed_slots"])


def mark_complete(path: Path, identifier: str) -> None:
    state = load_state(path)
    completed = list(dict.fromkeys(state["completed_slots"] + [identifier]))
    completed = sorted(completed)[-126:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"completed_slots": completed}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def append_env(path: str | None, key: str, value: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def command_due(args: argparse.Namespace) -> int:
    requested = (args.requested_slot or "").strip()
    # A human workflow_dispatch without a scheduled_slot is an explicit manual run.
    if args.event_name == "workflow_dispatch" and not requested:
        append_env(args.github_env, "RUN_SCHEDULED_BOT", "1")
        append_env(args.github_env, "SCHEDULE_SLOT_ID", "")
        print("manual dispatch — shared schedule gate bypassed")
        return 0

    identifier = resolve_slot(
        bot=args.bot,
        now=datetime.now(KSA),
        completed=completed_slots(args.state),
        requested_slot=requested,
    )
    if identifier:
        append_env(args.github_env, "RUN_SCHEDULED_BOT", "1")
        append_env(args.github_env, "SCHEDULE_SLOT_ID", identifier)
        print(f"{args.bot} slot due: {identifier}")
    else:
        append_env(args.github_env, "RUN_SCHEDULED_BOT", "0")
        append_env(args.github_env, "SCHEDULE_SLOT_ID", "")
        print(f"no uncompleted {args.bot} slot due")
    return 0


def command_mark(args: argparse.Namespace) -> int:
    identifier = (args.slot or "").strip()
    if not identifier:
        raise SystemExit("--slot is required")
    mark_complete(args.state, identifier)
    print(f"marked slot complete: {identifier}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    due = sub.add_parser("due")
    due.add_argument("--bot", choices=sorted(BOT_SLOTS), required=True)
    due.add_argument("--event-name", default=os.getenv("GITHUB_EVENT_NAME", "schedule"))
    due.add_argument("--requested-slot", default="")
    due.add_argument("--github-env", default=os.getenv("GITHUB_ENV"))
    due.add_argument("--state", type=Path, required=True)
    due.set_defaults(func=command_due)

    mark = sub.add_parser("mark")
    mark.add_argument("--slot", default=os.getenv("SCHEDULE_SLOT_ID", ""))
    mark.add_argument("--state", type=Path, required=True)
    mark.set_defaults(func=command_mark)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
