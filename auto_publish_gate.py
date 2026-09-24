#!/usr/bin/env python3
"""Fail-closed gate for promoting reviewed shadow packages to Snapchat.

This script makes no network mutations except reading the durable GitHub journals.
It never generates content and never publishes. The workflow may publish only lanes
explicitly returned as publishable here.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from publishing_v2.autopilot.runtime import engine_id, promotable_shadow
from publishing_v2.bundle_api import GitHubJournal


def _norm(value):
    return " ".join(str(value or "").casefold().split())


def _subject_key(state):
    candidate = state.get("package", {}).get("candidate", {})
    resolved = candidate.get("resolved_subjects") or []
    names = [_norm(row.get("name")) for row in resolved if isinstance(row, dict)]
    names = [name for name in names if name]
    if names:
        return tuple(sorted(set(names)))
    editorial = candidate.get("editorial", {})
    query = _norm(editorial.get("research_query"))
    return (query,) if query else ()


def _candidate_id(state):
    return state.get("package", {}).get("candidate", {}).get("id")


def _load_lane(readiness, lane, engine, now):
    row = readiness.get(lane)
    if not isinstance(row, dict):
        return {"action": "blocked", "reason": "readiness_missing", "state": None}
    if row.get("engine") != engine:
        return {"action": "blocked", "reason": "readiness_engine_mismatch", "state": None}
    slot = row.get("slot")
    if not isinstance(slot, str) or not slot:
        return {"action": "blocked", "reason": "readiness_slot_missing", "state": None}
    state = GitHubJournal(slot).read()
    if row.get("status") == "published" and state.get("status") == "published":
        return {"action": "already_published", "reason": None, "state": state}
    if row.get("status") != "shadow_passed":
        return {"action": "blocked", "reason": "shadow_not_passed", "state": state}
    promoted = promotable_shadow(state, engine, lane, now, slot)
    if promoted is None:
        return {"action": "blocked", "reason": "shadow_not_promotable", "state": state}
    return {"action": "publish", "reason": None, "state": state}


def decide(readiness, engine, now):
    daily = _load_lane(readiness, "daily", engine, now)
    local = _load_lane(readiness, "local", engine, now)

    if daily["action"] == "blocked":
        # Daily is the minimum publication contract. Do not publish only Local.
        local = dict(local, action="blocked", reason="daily_not_publishable")
    elif local["action"] == "publish":
        daily_state = daily.get("state") or {}
        local_state = local.get("state") or {}
        same_id = (_candidate_id(daily_state) and
                   _candidate_id(daily_state) == _candidate_id(local_state))
        daily_subject = _subject_key(daily_state)
        local_subject = _subject_key(local_state)
        same_subject = bool(daily_subject and local_subject and
                            set(daily_subject) & set(local_subject))
        if same_id or same_subject:
            local = dict(local, action="blocked", reason="duplicate_with_daily")

    return {
        "engine": engine,
        "daily": {"action": daily["action"], "reason": daily.get("reason")},
        "local": {"action": local["action"], "reason": local.get("reason")},
    }


def main():
    if os.environ.get("GITHUB_REPOSITORY") != "khalidonline/daily-news-snap":
        raise ValueError("configured_repository_required")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("main_branch_required")

    now = datetime.now(timezone.utc)
    engine = engine_id()
    readiness = GitHubJournal("autopilot-readiness").read()
    result = decide(readiness, engine, now)

    out = Path("autopublish-output")
    out.mkdir(parents=True, exist_ok=True)
    (out / "gate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as stream:
            stream.write("daily=" + ("true" if result["daily"]["action"] == "publish" else "false") + "\n")
            stream.write("local=" + ("true" if result["local"]["action"] == "publish" else "false") + "\n")
            stream.write("daily_action=" + result["daily"]["action"] + "\n")
            stream.write("local_action=" + result["local"]["action"] + "\n")
            stream.write("local_reason=" + str(result["local"].get("reason") or "") + "\n")

    print(json.dumps(result, ensure_ascii=False))
    if result["daily"]["action"] == "blocked":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
