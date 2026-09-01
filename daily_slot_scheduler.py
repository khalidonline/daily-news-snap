#!/usr/bin/env python3
"""Self-healing scheduler for Daily News Telegram review slots.

The GitHub workflow wakes frequently. This module decides whether the most
recent intended KSA slot is due, using a durable repo ledger to prevent a slot
from being delivered twice. It never backfills an older slot once a newer slot
has become due, and it will not resurrect a slot more than 90 minutes late.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KSA = ZoneInfo("Asia/Riyadh")
SLOT_HOURS = (7, 9, 11, 13, 15, 17, 19, 21, 23)
SLOT_MINUTE = 10
RECOVERY_WINDOW_MINUTES = 90
DEFAULT_STATE_PATH = Path("daily_slot_state.json")


def slot_id(slot: datetime) -> str:
    return slot.isoformat(timespec="minutes")


def slots_for_day(now: datetime) -> list[datetime]:
    local = now.astimezone(KSA)
    return [
        local.replace(hour=hour, minute=SLOT_MINUTE, second=0, microsecond=0)
        for hour in SLOT_HOURS
    ]


def due_slot_id(now: datetime, completed: set[str]) -> str | None:
    """Return the latest recoverable slot for *today*, or None.

    Only the most recent intended slot is considered. This deliberately avoids
    a burst of old cards after an outage: once 11:10 is due, a missed 09:10 is
    no longer backfilled. A slot may be recovered for up to 90 minutes.
    """
    local = now.astimezone(KSA)
    due = [slot for slot in slots_for_day(local) if slot <= local]
    if not due:
        return None

    latest = due[-1]
    delay = local - latest
    if delay > timedelta(minutes=RECOVERY_WINDOW_MINUTES):
        return None

    identifier = slot_id(latest)
    if identifier in completed:
        return None
    return identifier


def load_state(path: Path = DEFAULT_STATE_PATH) -> dict:
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


def completed_slots(path: Path = DEFAULT_STATE_PATH) -> set[str]:
    return set(load_state(path)["completed_slots"])


def mark_complete(path: Path, identifier: str) -> None:
    state = load_state(path)
    completed = list(dict.fromkeys(state["completed_slots"] + [identifier]))

    # Keep the ledger small. Slot IDs are ISO strings, so lexical ordering is
    # chronological for this fixed timezone/format.
    completed = sorted(completed)[-126:]  # 14 days × 9 slots/day
    path.write_text(
        json.dumps({"completed_slots": completed}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def append_env(path: str | None, key: str, value: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def command_due(args: argparse.Namespace) -> int:
    if args.event_name == "workflow_dispatch":
        append_env(args.github_env, "RUN_DAILY", "1")
        append_env(args.github_env, "DAILY_SLOT_ID", "")
        print("manual dispatch — scheduler slot gate bypassed")
        return 0

    now = datetime.now(KSA)
    identifier = due_slot_id(now, completed_slots(args.state))
    if identifier:
        append_env(args.github_env, "RUN_DAILY", "1")
        append_env(args.github_env, "DAILY_SLOT_ID", identifier)
        print(f"daily slot due: {identifier}")
    else:
        append_env(args.github_env, "RUN_DAILY", "0")
        append_env(args.github_env, "DAILY_SLOT_ID", "")
        print("no recoverable uncompleted daily slot due")
    return 0


def command_mark(args: argparse.Namespace) -> int:
    identifier = (args.slot or "").strip()
    if not identifier:
        raise SystemExit("--slot is required")
    mark_complete(args.state, identifier)
    print(f"marked daily slot complete: {identifier}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    due = sub.add_parser("due")
    due.add_argument("--event-name", default=os.getenv("GITHUB_EVENT_NAME", "schedule"))
    due.add_argument("--github-env", default=os.getenv("GITHUB_ENV"))
    due.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    due.set_defaults(func=command_due)

    mark = sub.add_parser("mark")
    mark.add_argument("--slot", default=os.getenv("DAILY_SLOT_ID", ""))
    mark.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    mark.set_defaults(func=command_mark)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
