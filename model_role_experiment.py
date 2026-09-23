#!/usr/bin/env python3
"""Manual blind writer benchmark on frozen real project cases.

Production routing, readiness, Telegram and Snapchat are untouched. The same
frozen facts and writer prompt are sent to every candidate.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from daily_budget import GitHubStore, Ledger
from publishing_v2.autopilot.agents import PROMPTS, STYLE, parse_object

CANDIDATES = (
    {"id": "baseline-opus", "provider": "anthropic", "model": "claude-opus-5",
     "input_price": 5.0, "output_price": 25.0, "credential": "ANTHROPIC_API_KEY"},
    {"id": "candidate-sonnet", "provider": "anthropic", "model": "claude-sonnet-5",
     "input_price": 2.0, "output_price": 10.0, "credential": "ANTHROPIC_API_KEY"},
    {"id": "candidate-sol", "provider": "openai", "model": "gpt-5.6-sol",
     "input_price": 4.0, "output_price": 20.0, "credential": "OPENAI_API_KEY"},
)
LABELS = ("A", "B", "C")
MAX_CASES = 2
MAX_OUTPUT_TOKENS = 4096
MAX_EXPERIMENT_COST_USD = 0.75
TIMEOUT_SECONDS = 180


class ExperimentError(RuntimeError):
    pass


def _safe_http_error(status: int, raw: bytes) -> str:
    detail = f"provider_http_{status}"
    try:
        body = json.loads(raw)
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            safe = error.get("code") or error.get("type")
            if isinstance(safe, str) and safe and all(ch.isalnum() or ch in "._-" for ch in safe[:80]):
                detail += "_" + safe[:80]
    except Exception:
        pass
    return detail


def _request(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        raw = exc.read(64 * 1024)
        raise ExperimentError(_safe_http_error(exc.code, raw)) from None
    except Exception as exc:
        raise ExperimentError(type(exc).__name__) from None
    if len(raw) > 2 * 1024 * 1024:
        raise ExperimentError("provider_response_too_large")
    try:
        body = json.loads(raw)
    except Exception:
        raise ExperimentError("provider_json_invalid") from None
    if not isinstance(body, dict):
        raise ExperimentError("provider_json_object_required")
    return body


def _anthropic(candidate: dict[str, Any], prompt: str, key: str):
    body = _request(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01",
         "Content-Type": "application/json"},
        {"model": candidate["model"], "max_tokens": MAX_OUTPUT_TOKENS,
         "output_config": {"effort": "medium"},
         "messages": [{"role": "user", "content": prompt}]},
    )
    if body.get("stop_reason") != "end_turn":
        stop = body.get("stop_reason")
        safe = stop if isinstance(stop, str) and stop else "unknown"
        raise ExperimentError("anthropic_stop_" + safe[:80])
    if not isinstance(body.get("content"), list):
        raise ExperimentError("anthropic_content_invalid")
    text = "".join(
        row.get("text", "")
        for row in body["content"]
        if isinstance(row, dict) and row.get("type") == "text"
    ).strip()
    usage = body.get("usage") or {}
    tokens = (usage.get("input_tokens"), usage.get("output_tokens"))
    if not text or not all(type(v) is int and v >= 0 for v in tokens):
        raise ExperimentError("anthropic_response_invalid")
    return text, {"input_tokens": tokens[0], "output_tokens": tokens[1]}, str(body.get("id") or "")


def _openai(candidate: dict[str, Any], prompt: str, key: str):
    body = _request(
        "https://api.openai.com/v1/responses",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {"model": candidate["model"], "input": prompt,
         "reasoning": {"effort": "medium"},
         "max_output_tokens": MAX_OUTPUT_TOKENS},
    )
    if body.get("status") != "completed":
        status = body.get("status")
        details = body.get("incomplete_details") if isinstance(body.get("incomplete_details"), dict) else {}
        reason = details.get("reason")
        safe = reason if isinstance(reason, str) and reason else (status if isinstance(status, str) else "unknown")
        raise ExperimentError("openai_incomplete_" + safe[:80])
    if not isinstance(body.get("output"), list):
        raise ExperimentError("openai_output_invalid")
    texts = []
    for item in body["output"]:
        if not isinstance(item, dict) or item.get("type") == "reasoning":
            continue
        if item.get("type") != "message" or not isinstance(item.get("content"), list):
            continue
        for part in item["content"]:
            if isinstance(part, dict) and part.get("type") == "output_text":
                texts.append(part.get("text", ""))
    text = "".join(texts).strip()
    usage = body.get("usage") or {}
    tokens = (usage.get("input_tokens"), usage.get("output_tokens"))
    if not text or not all(type(v) is int and v >= 0 for v in tokens):
        raise ExperimentError("openai_response_invalid")
    return text, {"input_tokens": tokens[0], "output_tokens": tokens[1]}, str(body.get("id") or "")


def maximum_call_cost(candidate: dict[str, Any], prompt: str) -> float:
    # UTF-8 bytes are a conservative upper bound on text token count.
    input_tokens = len(prompt.encode("utf-8"))
    return (
        input_tokens * candidate["input_price"]
        + MAX_OUTPUT_TOKENS * candidate["output_price"]
    ) / 1_000_000


def call_candidate(candidate: dict[str, Any], prompt: str, env: dict[str, str]) -> dict[str, Any]:
    key = env.get(candidate["credential"], "").strip()
    if not key:
        return {"status": "missing_credentials"}
    started = time.monotonic()
    try:
        if candidate["provider"] == "anthropic":
            text, usage, response_id = _anthropic(candidate, prompt, key)
        elif candidate["provider"] == "openai":
            text, usage, response_id = _openai(candidate, prompt, key)
        else:
            raise ExperimentError("unsupported_provider")
        cost = (
            usage["input_tokens"] * candidate["input_price"]
            + usage["output_tokens"] * candidate["output_price"]
        ) / 1_000_000
        return {
            "status": "completed", "text": text, "usage": usage,
            "response_id": response_id,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "cost_usd": round(cost, 6),
        }
    except Exception as exc:
        return {
            "status": "failed", "error": str(exc)[:160],
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }


def case_input(case: dict[str, Any]) -> dict[str, Any]:
    claims = [
        {"id": fact["id"], "fact": fact["text"]}
        for source in case.get("sources", [])
        for fact in source.get("facts", [])
    ]
    return {
        "candidate": {
            "title": case["trigger"],
            "why_now": case["trigger"],
            "angle": case.get("objectives", {}).get("story", ""),
        },
        "research": {"sensitive": False, "claims": claims},
        "visual_options": [],
        "feedback": (
            "Frozen benchmark only. Follow these objectives exactly: "
            + json.dumps(case.get("objectives", {}), ensure_ascii=False)
            + ". Cautions: "
            + json.dumps(case.get("cautions", []), ensure_ascii=False)
        ),
    }


def prompt_for(case: dict[str, Any]) -> str:
    return (
        STYLE + "\n\nROLE TASK:\n" + PROMPTS["writer"]
        + "\n\nFROZEN INPUT JSON:\n"
        + json.dumps(case_input(case), ensure_ascii=False, sort_keys=True)
    )


def validate_output(text: str, case: dict[str, Any]) -> dict[str, Any]:
    try:
        obj = parse_object(text)
    except Exception as exc:
        return {"passed": False, "reason": type(exc).__name__}
    cards = obj.get("cards")
    if not isinstance(obj.get("title"), str) or not isinstance(cards, list) or not 3 <= len(cards) <= 4:
        return {"passed": False, "reason": "shape"}
    allowed = {
        fact["id"] for source in case.get("sources", [])
        for fact in source.get("facts", [])
    }
    if cards[0].get("kind") != "info" or sum(c.get("kind") == "info" for c in cards) != 1:
        return {"passed": False, "reason": "info_shape"}
    for card in cards:
        if card.get("kind") not in {"info", "story"}:
            return {"passed": False, "reason": "card_kind"}
        if not all(isinstance(card.get(k), str) and card[k].strip()
                   for k in ("title", "body", "punch", "image_query")):
            return {"passed": False, "reason": "missing_text"}
        ids = card.get("claim_ids")
        if not isinstance(ids, list) or not ids or any(cid not in allowed for cid in ids):
            return {"passed": False, "reason": "claim_ids"}
        if len(card["title"]) > 85 or len(card["body"]) > 320 or len(card["punch"]) > 100:
            return {"passed": False, "reason": "length"}
    return {"passed": True, "reason": "ok"}


def blind_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Blind writer benchmark", "",
        "راجع الصياغة بدون النظر إلى مفتاح النماذج. ركّز على: سعودية اللغة، "
        "قوة المعلومة، ترابط القصة، الالتزام بالحقائق، وقابلية المشاركة.", "",
    ]
    for case in result["cases"]:
        lines += [f"## Case: {case['id']}", f"Trigger: {case['trigger']}", ""]
        for output in case["outputs"]:
            lines.append(f"### Option {output['label']}")
            if output["status"] != "completed":
                lines += [f"_Unavailable: {output['status']}_", ""]
                continue
            lines += [
                f"Validation: {'PASS' if output['validation']['passed'] else 'FAIL'}",
                "", "~~~json", output["text"].strip(), "~~~", "",
            ]
    return "\n".join(lines).rstrip() + "\n"


def reserve_shared_budget(env: dict[str, str]):
    repository = env.get("GITHUB_REPOSITORY", "").strip()
    token = (env.get("DAILY_BUDGET_GITHUB_TOKEN", "") or env.get("GITHUB_TOKEN", "")).strip()
    if not repository or not token:
        if env.get("GITHUB_ACTIONS") == "true":
            raise ExperimentError("shared_budget_credentials_required")
        return None, None
    ledger = Ledger(GitHubStore(repository, token))
    reservation = ledger.reserve(
        int(MAX_EXPERIMENT_COST_USD * 1_000_000),
        "manual:model-role-experiment",
    )
    return ledger, reservation


def run(cases_path: Path, output_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])[:MAX_CASES]
    if len(cases) != MAX_CASES:
        raise ValueError("benchmark_requires_selected_cases")
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger, budget_token = reserve_shared_budget(env)
    result = {
        "schema_version": 1,
        "purpose": "manual_blind_writer_model_benchmark",
        "production_changed": False,
        "published": False,
        "candidates": [
            {"label": label, **{k: c[k] for k in
             ("id", "provider", "model", "input_price", "output_price")}}
            for label, c in zip(LABELS, CANDIDATES)
        ],
        "cases": [],
    }
    total_cost = 0.0
    reserved_maximum = 0.0
    for case in cases:
        prompt = prompt_for(case)
        row = {"id": case["id"], "trigger": case["trigger"], "outputs": []}
        for label, candidate in zip(LABELS, CANDIDATES):
            maximum = maximum_call_cost(candidate, prompt)
            if reserved_maximum + maximum > MAX_EXPERIMENT_COST_USD:
                generated = {"status": "cost_cap_reached"}
            else:
                reserved_maximum += maximum
                generated = call_candidate(candidate, prompt, env)
            output = {"label": label, **generated}
            if generated["status"] == "completed":
                output["validation"] = validate_output(generated["text"], case)
                total_cost += generated["cost_usd"]
            row["outputs"].append(output)
        result["cases"].append(row)
    result["total_cost_usd"] = round(total_cost, 6)
    result["reserved_maximum_usd"] = round(reserved_maximum, 6)
    if result["total_cost_usd"] > MAX_EXPERIMENT_COST_USD:
        raise ExperimentError("experiment_cost_cap_exceeded")
    (output_dir / "model-experiment-key.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "model-experiment-blind.md").write_text(
        blind_markdown(result), encoding="utf-8")
    summary = {
        "completed_calls": sum(o["status"] == "completed" for c in result["cases"] for o in c["outputs"]),
        "missing_credentials": sum(o["status"] == "missing_credentials" for c in result["cases"] for o in c["outputs"]),
        "failed_calls": sum(o["status"] == "failed" for c in result["cases"] for o in c["outputs"]),
        "total_cost_usd": result["total_cost_usd"],
        "cost_cap_usd": MAX_EXPERIMENT_COST_USD,
        "reserved_maximum_usd": result["reserved_maximum_usd"],
        "note": "No Telegram/Snapchat publication and no production routing changes.",
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if ledger is not None and budget_token is not None:
        ledger.settle(budget_token, int(round(result["total_cost_usd"] * 1_000_000)))
    print(json.dumps(summary))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=Path("evaluation/event_packages.json"))
    parser.add_argument("--output", type=Path, default=Path("model-experiment-output"))
    args = parser.parse_args()
    run(args.cases, args.output, dict(os.environ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
