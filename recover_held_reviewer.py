#!/usr/bin/env python3
"""Resume only a budget-blocked final reviewer on a saved shadow slot."""
from __future__ import annotations

import base64, copy, hashlib, io, json, os, re
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from PIL import Image

from daily_budget import GitHubStore, Ledger, PRICES, actual_cost, autopilot_daily_limit, prepare
from publishing_v2 import providers
from publishing_v2.autopilot import policy
from publishing_v2.autopilot.agents import PROMPTS, STYLE, parse_object
from publishing_v2.autopilot.feedback import EDITORIAL_FEEDBACK
from publishing_v2.autopilot.replay import restore_text
from publishing_v2.autopilot.runtime import Renderer, shadow_record
from publishing_v2.bundle_api import GitHubJournal

SLOT_RE = re.compile(r"autopilot-\d{4}-\d{2}-\d{2}-(daily|local)-shadow-[a-f0-9]{16}")
REVIEWER_MAX_TOKENS = 4096

def restore_sources(rows):
    """Prefer a byte-identical refetch; otherwise use the immutable saved excerpt.

    Evidence snapshots were persisted only after quote-in-source validation during
    the original research pass. A publisher page can change later; that must not
    force new Research or silently substitute new text during final review.
    """
    restored = []
    for row in rows:
        expected = row.get("retrieved_text_sha256")
        saved = row.get("text")
        if not expected or not isinstance(saved, str) or not saved.strip():
            raise ValueError("saved_source_provenance_missing")
        try:
            body = restore_text(row)
        except Exception:
            body = None
        if isinstance(body, str) and hashlib.sha256(body.encode()).hexdigest() == expected:
            restored.append(dict(row, text=body, recovery_source_mode="refetched_exact"))
        else:
            restored.append(dict(row, text=saved, recovery_source_mode="saved_evidence_snapshot"))
    return restored

def attach_saved_timing_evidence(sources, timing):
    ident = timing.get("event_source_id")
    quote = timing.get("event_quote")
    if not isinstance(ident, str) or not isinstance(quote, str) or len(quote) < 8:
        raise ValueError("saved_timing_evidence_missing")
    found = False
    for source in sources:
        if source.get("id") == ident:
            found = True
            if quote not in source.get("text", ""):
                source["text"] = source.get("text", "") + "\n" + quote
                source["recovery_timing_mode"] = "saved_exact_timing_quote"
            break
    if not found:
        raise ValueError("saved_timing_source_missing")
    return sources

def rebuild_package(state, now):
    draft = copy.deepcopy(state["draft"])
    package = dict(
        draft,
        sources=copy.deepcopy(state["sources"]),
        research=copy.deepcopy(state["research"]),
        lane=state["lane"],
        editorial_feedback=copy.deepcopy(EDITORIAL_FEEDBACK),
        candidate=copy.deepcopy(state["candidate"]),
        expires_at=state["expires_at"],
        as_of=now.isoformat(),
        repair={"feedback": state.get("feedback", ""), "excluded_image_ids": []},
    )
    visible = []
    for card in package["cards"]:
        if card.get("kind") == "credits":
            continue
        visible.append({k: copy.deepcopy(v) for k, v in card.items()
                        if k in {"kind","title","body","punch","claim_ids","image_query","image_caption"}})
    policy.validate_draft({"title": package["title"], "cards": visible}, state["research"])
    return package

def review_once(review_input, images, *, env, ledger):
    model = env.get("AUTOPILOT_REVIEWER_MODEL", "claude-sonnet-5")
    if model != "claude-sonnet-5":
        raise ValueError("recovery_requires_benchmarked_sonnet_reviewer")
    credential = env.get("ANTHROPIC_API_KEY", "").strip()
    if not credential:
        raise ValueError("missing_agent_credential")

    encoded = json.dumps(review_input, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > 90000 or len(images) > 8:
        raise ValueError("agent_input_too_large")

    content = []
    for path in images:
        with Image.open(Path(path)) as image:
            image = image.convert("RGB")
            image.thumbnail((1080, 1920))
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=85)
        content.append({"type":"image","source":{"type":"base64","media_type":"image/jpeg",
                        "data":base64.b64encode(buffer.getvalue()).decode()}})
    content.append({"type":"text","text":encoded})

    payload = {
        "model": model,
        "max_tokens": REVIEWER_MAX_TOKENS,
        "system": STYLE + "\n" + PROMPTS["reviewer"] + "\nFor recovery, some original sources may be immutable saved evidence excerpts from the exact earlier retrieval. Treat any context absent from those excerpts as unknown and reject claims that require missing context; never fill gaps from memory.",
        "messages": [{"role":"user","content":content}],
        "output_config": {"effort":"high"},
    }
    payload, _ = prepare(payload)
    text_payload = copy.deepcopy(payload)
    text_payload["messages"][0]["content"] = [content[-1]]
    _, text_maximum = prepare(text_payload)
    maximum = text_maximum + len(images) * 8192 * PRICES[model][0]

    token = ledger.reserve(maximum, "autopilot:reviewer")
    transport = partial(providers._default_transport, timeout_seconds=180)
    status, body = providers._request(
        transport, "POST", "https://api.anthropic.com/v1/messages",
        {"x-api-key":credential,"anthropic-version":"2023-06-01","Content-Type":"application/json"},
        payload)
    if status != 200:
        raise RuntimeError("agent_http_" + str(status))
    cost = actual_cost(model, body)
    ledger.settle(token, cost)
    if cost > maximum:
        raise RuntimeError("agent_price_bound_exceeded")

    receipt = {
        "role":"reviewer","model":model,"response_id":body.get("id"),
        "usage":body.get("usage"),"cost_micro_usd":cost,"stop_reason":body.get("stop_reason"),
        "content_types":[p.get("type") for p in body.get("content",[]) if isinstance(p,dict)],
        "recovery_max_tokens":REVIEWER_MAX_TOKENS,
        "recovery_reservation_micro_usd":maximum,
    }
    if not receipt["response_id"]:
        raise ValueError("missing_agent_receipt")
    raw = providers._parse_anthropic(body)
    receipt["response_format"] = "fenced_json" if raw.strip().startswith(chr(96) * 3) else "plain"
    return parse_object(raw), receipt

def main():
    slot = os.environ.get("RECOVERY_SLOT", "").strip()
    if not SLOT_RE.fullmatch(slot):
        raise ValueError("invalid_recovery_slot")
    if os.environ.get("GITHUB_REPOSITORY") != "khalidonline/daily-news-snap":
        raise ValueError("configured_repository_required")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("main_branch_required")

    journal = GitHubJournal(slot)
    state = journal.read()
    diagnostic = state.get("budget_diagnostic") or {}
    if (state.get("status") != "held" or state.get("reason") != "BudgetBlocked"
            or diagnostic.get("role") != "reviewer" or not state.get("draft")
            or state.get("review")
            or any(r.get("role") == "reviewer" for r in state.get("agent_receipts", []))):
        raise ValueError("slot_not_unstarted_budget_blocked_review")

    now = datetime.now(timezone.utc)
    sources = attach_saved_timing_evidence(restore_sources(state["sources"]), state["timing"])
    policy.validate_attention(state["candidate"], now)
    policy.validate_timing(state["timing"], sources, now)
    policy.validate_research(state["research"], sources, state["lane"], now)

    package = rebuild_package(state, now)
    output = Path("review-recovery-output")
    paths = Renderer(None, None)(package, output)
    if len(paths) != len(package["cards"]):
        raise ValueError("missing_rendered_cards")
    seal = policy.seal(package, paths)

    review_input = dict(copy.deepcopy(package), original_sources=sources)
    token = os.environ.get("DAILY_BUDGET_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    ledger = Ledger(GitHubStore(os.environ["GITHUB_REPOSITORY"], token),
                    limit_micro_usd=autopilot_daily_limit(
                        now, os.environ.get("AUTOPILOT_DAILY_LIMIT_MICRO_USD", "3000000")))
    review, receipt = review_once(review_input, paths, env=os.environ, ledger=ledger)
    review["input_sha256"] = policy.digest(review_input)
    policy.validate_review(review, len(paths))
    policy.verify_seal(package, paths, seal, now)

    state.update(package=package, review=review, approval=seal,
                 paths=[str(p) for p in paths], status="shadow_passed", reason=None)
    state.pop("budget_diagnostic", None)
    state.setdefault("agent_receipts", []).append(receipt)
    state.setdefault("audit", []).append({
        "event":"review_budget_recovered","at":now.isoformat(),
        "reservation_micro_usd":receipt["recovery_reservation_micro_usd"],
        "cost_micro_usd":receipt["cost_micro_usd"]})
    state["audit"].append({"event":"shadow_complete","at":now.isoformat()})
    journal.save(state)

    readiness = GitHubJournal("autopilot-readiness")
    ready = readiness.read()
    ready[state["lane"]] = shadow_record(state, state["engine"], slot)
    readiness.save(ready)

    output.mkdir(parents=True, exist_ok=True)
    result = {"slot":slot,"lane":state["lane"],"status":state["status"],"engine":state["engine"],
              "reviewer_cost_micro_usd":receipt["cost_micro_usd"],
              "reservation_micro_usd":receipt["recovery_reservation_micro_usd"]}
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
