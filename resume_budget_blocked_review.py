#!/usr/bin/env python3
"""Resume only the final reviewer for a budget-blocked shadow package.

This is intentionally narrow: it reuses the exact saved draft, evidence and rendered
frames from a prior run. It performs no editor, timing, research, writer or visual call.
"""
from __future__ import annotations

import argparse
import base64
import copy
import io
import json
import os
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

from PIL import Image

from daily_budget import Ledger, GitHubStore, PRICES, actual_cost, autopilot_daily_limit, prepare
from publishing_v2 import providers
from publishing_v2.bundle_api import GitHubJournal
from publishing_v2.autopilot import policy
from publishing_v2.autopilot.agents import STYLE, PROMPTS, parse_object
from publishing_v2.autopilot.feedback import EDITORIAL_FEEDBACK
from publishing_v2.autopilot.replay import restore_text
from publishing_v2.autopilot.runtime import engine_id, shadow_record

REVIEWER_MAX_TOKENS = 8192
IMAGE_TOKEN_CAP = 4784


def restore_sources(snapshot):
    restored = []
    import hashlib
    for row in snapshot:
        body = restore_text(row)
        expected = row.get("retrieved_text_sha256")
        if not expected or hashlib.sha256(body.encode()).hexdigest() != expected:
            raise ValueError("saved_source_changed")
        restored.append(dict(row, text=body))
    return restored


def review_once(package, original_sources, frames, ledger):
    encoded = json.dumps(dict(copy.deepcopy(package), original_sources=original_sources),
                         ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > 90000 or len(frames) > 8:
        raise ValueError("review_input_too_large")
    content = []
    for path in frames:
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((1080, 1920))
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=85)
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.b64encode(buffer.getvalue()).decode(),
            },
        })
    content.append({"type": "text", "text": encoded})
    payload = {
        "model": "claude-sonnet-5",
        "max_tokens": REVIEWER_MAX_TOKENS,
        "system": STYLE + "\n" + PROMPTS["reviewer"],
        "messages": [{"role": "user", "content": content}],
        "output_config": {"effort": "high"},
    }
    payload, _ = prepare(payload)
    text_payload = copy.deepcopy(payload)
    text_payload["messages"][0]["content"] = [content[-1]]
    _, text_maximum = prepare(text_payload)
    maximum = text_maximum + len(frames) * IMAGE_TOKEN_CAP * PRICES["claude-sonnet-5"][0]
    token = ledger.reserve(maximum, "autopilot:reviewer")
    transport = partial(providers._default_transport, timeout_seconds=180)
    status, body = providers._request(
        transport,
        "POST",
        "https://api.anthropic.com/v1/messages",
        {
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        payload,
    )
    if status != 200:
        raise RuntimeError("agent_http_" + str(status))
    cost = actual_cost("claude-sonnet-5", body)
    ledger.settle(token, cost)
    if cost > maximum:
        raise RuntimeError("reviewer_price_bound_exceeded")
    answer = "".join(block.get("text", "") for block in body.get("content", [])
                     if block.get("type") == "text")
    review = parse_object(answer)
    receipt = {
        "role": "reviewer",
        "model": "claude-sonnet-5",
        "response_id": body.get("id"),
        "usage": body.get("usage", {}),
        "cost_micro_usd": cost,
        "stop_reason": body.get("stop_reason"),
        "content_types": [block.get("type") for block in body.get("content", [])],
        "response_format": "plain",
    }
    return review, receipt, maximum


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-slot", required=True)
    parser.add_argument("--frames-root", type=Path, required=True)
    args = parser.parse_args()

    if os.environ.get("GITHUB_REPOSITORY") != "khalidonline/daily-news-snap":
        raise ValueError("configured_repository_required")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("main_branch_required")

    journal = GitHubJournal(args.source_slot)
    state = journal.read()
    if (state.get("status") != "held" or state.get("reason") != "BudgetBlocked"
            or not isinstance(state.get("draft"), dict)
            or any(r.get("role") == "reviewer" for r in state.get("agent_receipts", []))):
        raise ValueError("source_not_budget_blocked_before_review")
    if state.get("engine") != engine_id():
        raise ValueError("source_engine_changed")

    now = datetime.now(timezone.utc)
    expires = datetime.fromisoformat(state["expires_at"])
    if expires.tzinfo is None or now >= expires:
        raise ValueError("source_expired")

    original_sources = restore_sources(state["sources"])
    policy.validate_attention(state["candidate"], now)
    policy.validate_timing(state["timing"], original_sources, now)
    policy.validate_research(state["research"], original_sources, state["lane"], now)

    draft = copy.deepcopy(state["draft"])
    editorial = [c for c in draft["cards"] if c.get("kind") != "credits"]
    visible = [{k: v for k, v in c.items()
                if k in {"kind", "title", "body", "punch", "claim_ids", "image_query", "image_caption"}}
               for c in editorial]
    policy.validate_draft({"title": draft["title"], "cards": visible}, state["research"])

    package = dict(
        draft,
        sources=copy.deepcopy(state["sources"]),
        research=copy.deepcopy(state["research"]),
        lane=state["lane"],
        editorial_feedback=EDITORIAL_FEEDBACK,
        candidate=copy.deepcopy(state["candidate"]),
        expires_at=state["expires_at"],
        as_of=now.isoformat(),
        repair={"feedback": state.get("feedback", ""), "excluded_image_ids": []},
    )

    frames = sorted(args.frames_root.glob("card-*.jpg"))
    if len(frames) != len(package["cards"]):
        raise ValueError("saved_frame_count_mismatch")
    seal = policy.seal(package, frames)

    token = os.environ.get("DAILY_BUDGET_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    ledger = Ledger(
        GitHubStore(os.environ["GITHUB_REPOSITORY"], token),
        limit_micro_usd=autopilot_daily_limit(now, os.environ.get("AUTOPILOT_DAILY_LIMIT_MICRO_USD", "3000000")),
    )
    review, receipt, reserved = review_once(package, original_sources, frames, ledger)
    review["input_sha256"] = policy.digest(dict(copy.deepcopy(package), original_sources=original_sources))
    policy.validate_review(review, len(frames))
    policy.verify_seal(package, frames, seal, datetime.now(timezone.utc))

    state["agent_receipts"].append(receipt)
    state.update(
        status="shadow_passed",
        reason=None,
        package=package,
        paths=[str(path) for path in frames],
        approval=seal,
        review=review,
        budget_diagnostic=None,
    )
    state.setdefault("audit", []).append({
        "event": "review_resumed_after_budget_block",
        "at": datetime.now(timezone.utc).isoformat(),
        "reserved_micro_usd": reserved,
        "actual_micro_usd": receipt["cost_micro_usd"],
    })
    journal.save(state)

    readiness = GitHubJournal("autopilot-readiness")
    ready = readiness.read()
    ready[state["lane"]] = shadow_record(state, state["engine"], args.source_slot)
    readiness.save(ready)

    out = {
        "status": "shadow_passed",
        "lane": state["lane"],
        "source_slot": args.source_slot,
        "reserved_micro_usd": reserved,
        "actual_micro_usd": receipt["cost_micro_usd"],
        "title": package["title"],
    }
    Path("resume-review-result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
