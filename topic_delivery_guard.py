#!/usr/bin/env python3
"""Confirmed-delivery ledger for Topic Telegram review runs.

The Topic selection history is written before Telegram transport completes, so
it cannot be used as proof that a review card reached Telegram. This module
keeps a separate ledger that is written only after the workflow has observed
`telegram: sent`. Exact retained-brief recoveries consult that ledger before
bypassing the normal schedule gate.
"""

import argparse
import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_COOLDOWN_DAYS = 21


def _load(path):
    path = Path(path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def recovery_topic(payload_b64):
    if not payload_b64:
        return ""
    try:
        payload = json.loads(base64.b64decode(payload_b64).decode("utf-8"))
    except Exception:
        return ""
    return str(payload.get("topic") or "").strip()


def delivered_recently(topic, state_path, days=DEFAULT_COOLDOWN_DAYS, now=None):
    topic = str(topic or "").strip()
    if not topic:
        return False
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    for entry in _load(state_path):
        if str(entry.get("topic") or "").strip() != topic:
            continue
        raw = str(entry.get("at") or "")
        try:
            at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if at >= cutoff:
            return True
    return False


def _append_env(path, key, value):
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def check_recovery(payload_b64, state_path, github_env, days=DEFAULT_COOLDOWN_DAYS):
    topic = recovery_topic(payload_b64)
    duplicate = delivered_recently(topic, state_path, days=days)
    _append_env(github_env, "RECOVERY_ALREADY_DELIVERED", "1" if duplicate else "0")
    if duplicate:
        _append_env(github_env, "RUN_SCHEDULED_BOT", "0")
        print(f"exact Topic recovery suppressed — Telegram already confirmed: {topic}")
    else:
        print("exact Topic recovery has no confirmed-delivery duplicate")
    return duplicate


def record_latest(topics_used_path, state_path, now=None):
    used = _load(topics_used_path)
    if not used:
        raise SystemExit("cannot record Topic delivery: topics_used is empty")
    topic = str(used[-1].get("topic") or "").strip()
    if not topic:
        raise SystemExit("cannot record Topic delivery: latest topic is blank")

    now = now or datetime.now(timezone.utc)
    state_path = Path(state_path)
    entries = _load(state_path)
    # Keep one recent confirmation per exact Topic. A later confirmed delivery
    # refreshes the timestamp rather than growing duplicate ledger rows.
    entries = [e for e in entries if str(e.get("topic") or "").strip() != topic]
    entries.append({"topic": topic, "at": now.isoformat()})
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    print(f"recorded confirmed Topic Telegram delivery: {topic}")
    return topic


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check")
    check.add_argument("--payload-b64", required=True)
    check.add_argument("--state", required=True)
    check.add_argument("--github-env", required=True)
    check.add_argument("--days", type=int, default=DEFAULT_COOLDOWN_DAYS)

    record = sub.add_parser("record")
    record.add_argument("--topics-used", required=True)
    record.add_argument("--state", required=True)

    args = parser.parse_args()
    if args.command == "check":
        check_recovery(args.payload_b64, args.state, args.github_env, args.days)
    else:
        record_latest(args.topics_used, args.state)


if __name__ == "__main__":
    main()
