#!/usr/bin/env python3
"""Provider-neutral per-run model usage ledger and safety counters."""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class ModelBudgetExceeded(RuntimeError):
    """Raised before a request that would exceed a paid-response ceiling."""


_ANTHROPIC_PRICES = {
    "claude-opus-5": {
        "input": 5.0,
        "output": 25.0,
        "cache_write": 6.25,
        "cache_read": 0.5,
    },
    "claude-sonnet-5": {
        "input": 2.0,
        "output": 10.0,
        "cache_write": 2.5,
        "cache_read": 0.2,
    },
    "claude-haiku-4-5-20251001": {
        "input": 1.0,
        "output": 5.0,
        "cache_write": 1.25,
        "cache_read": 0.1,
    },
}
_WEB_SEARCH_USD = 0.01
_successful_responses: dict[str, int] = defaultdict(int)
_estimated_run_cost = 0.0


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _usage_path(path: Path | str | None = None) -> Path:
    return Path(path or os.getenv("MODEL_USAGE_PATH", "out/model_usage.jsonl"))


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _search_requests(usage: dict[str, Any]) -> int:
    server = usage.get("server_tool_use") or {}
    if not isinstance(server, dict):
        return 0
    return _integer(server.get("web_search_requests"))


def estimate_anthropic_cost(model: str, usage: dict[str, Any]) -> float | None:
    """Estimate first-party Claude list cost from a Messages usage object."""
    prices = _ANTHROPIC_PRICES.get(str(model or "").strip())
    if prices is None:
        return None
    total = (
        _integer(usage.get("input_tokens")) * prices["input"]
        + _integer(usage.get("output_tokens")) * prices["output"]
        + _integer(usage.get("cache_creation_input_tokens"))
        * prices["cache_write"]
        + _integer(usage.get("cache_read_input_tokens")) * prices["cache_read"]
    ) / 1_000_000
    total += _search_requests(usage) * _WEB_SEARCH_USD
    return round(total, 6)


def _append(row: dict[str, Any], path: Path | str | None = None) -> None:
    target = _usage_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def record_anthropic_response(
    *,
    bot: str,
    purpose: str,
    model: str,
    response: dict[str, Any],
    path: Path | str | None = None,
) -> dict[str, Any]:
    usage = response.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    row = {
        "timestamp": _utcnow(),
        "provider": "anthropic",
        "bot": str(bot),
        "purpose": str(purpose),
        "model": str(model),
        "message_id": response.get("id"),
        "input_tokens": _integer(usage.get("input_tokens")),
        "output_tokens": _integer(usage.get("output_tokens")),
        "cache_creation_input_tokens": _integer(
            usage.get("cache_creation_input_tokens")
        ),
        "cache_read_input_tokens": _integer(usage.get("cache_read_input_tokens")),
        "web_search_requests": _search_requests(usage),
        "estimated_usd": estimate_anthropic_cost(model, usage),
        "run_id": os.getenv("GITHUB_RUN_ID") or None,
        "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT") or None,
    }
    _append(row, path)
    global _estimated_run_cost
    if row["estimated_usd"] is not None:
        _estimated_run_cost += float(row["estimated_usd"])
    return row


def record_external_call(
    *,
    provider: str,
    bot: str,
    purpose: str,
    model: str,
    estimated_usd: float | None = None,
    path: Path | str | None = None,
) -> dict[str, Any]:
    row = {
        "timestamp": _utcnow(),
        "provider": str(provider),
        "bot": str(bot),
        "purpose": str(purpose),
        "model": str(model),
        "estimated_usd": (
            round(float(estimated_usd), 6) if estimated_usd is not None else None
        ),
        "run_id": os.getenv("GITHUB_RUN_ID") or None,
        "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT") or None,
    }
    _append(row, path)
    global _estimated_run_cost
    if row["estimated_usd"] is not None:
        _estimated_run_cost += float(row["estimated_usd"])
    return row


def require_response_capacity(bucket: str, limit: int) -> None:
    limit = int(limit)
    if limit < 1 or _successful_responses[str(bucket)] >= limit:
        raise ModelBudgetExceeded(
            f"paid-response ceiling reached for {bucket}: "
            f"{_successful_responses[str(bucket)]}/{limit}"
        )


def note_successful_response(bucket: str) -> None:
    _successful_responses[str(bucket)] += 1


def require_run_cost_capacity(limit_usd: float) -> None:
    limit = float(limit_usd)
    observed_cost = _estimated_run_cost
    run_id = os.getenv("GITHUB_RUN_ID")
    if run_id:
        persisted_cost = sum(
            float(row.get("estimated_usd") or 0)
            for row in read_rows(_usage_path())
            if row.get("run_id") == run_id
        )
        # Current-process calls exist in both counters; a previous subprocess's
        # calls exist only in the ledger. max() avoids double-counting either.
        observed_cost = max(observed_cost, persisted_cost)
    if limit <= 0 or observed_cost >= limit:
        raise ModelBudgetExceeded(
            f"run cost ceiling reached: ${observed_cost:.4f}/${limit:.4f}"
        )


def reset_run_state() -> None:
    global _estimated_run_cost
    _successful_responses.clear()
    _estimated_run_cost = 0.0


def read_rows(path: Path | str) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    rows = []
    for line in target.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    result = {
        "calls": 0,
        "estimated_usd": 0.0,
        "unpriced_calls": 0,
        "by_bot": {},
        "by_route": {},
    }
    for row in rows:
        bot = str(row.get("bot") or "unknown")
        purpose = str(row.get("purpose") or "unknown")
        summary = result["by_bot"].setdefault(
            bot, {"calls": 0, "estimated_usd": 0.0, "unpriced_calls": 0}
        )
        route = result["by_route"].setdefault(
            f"{bot}/{purpose}",
            {"calls": 0, "estimated_usd": 0.0, "unpriced_calls": 0},
        )
        result["calls"] += 1
        summary["calls"] += 1
        route["calls"] += 1
        cost = row.get("estimated_usd")
        if cost is None:
            result["unpriced_calls"] += 1
            summary["unpriced_calls"] += 1
            route["unpriced_calls"] += 1
        else:
            result["estimated_usd"] += float(cost)
            summary["estimated_usd"] += float(cost)
            route["estimated_usd"] += float(cost)
    result["estimated_usd"] = round(result["estimated_usd"], 6)
    for summary in result["by_bot"].values():
        summary["estimated_usd"] = round(summary["estimated_usd"], 6)
    for summary in result["by_route"].values():
        summary["estimated_usd"] = round(summary["estimated_usd"], 6)
    return result


def _print_markdown(summary: dict[str, Any]) -> None:
    print("## Model usage")
    print()
    print(
        f"Calls: **{summary['calls']}** · Estimated: "
        f"**${summary['estimated_usd']:.4f}** · "
        f"Unpriced: **{summary['unpriced_calls']}**"
    )
    print()
    print("| Bot / purpose | Calls | Estimated USD | Unpriced |")
    print("|---|---:|---:|---:|")
    for route, values in sorted(summary["by_route"].items()):
        print(
            f"| {route} | {values['calls']} | ${values['estimated_usd']:.4f} | "
            f"{values['unpriced_calls']} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    summary = sub.add_parser("summarize")
    summary.add_argument("--path", type=Path, default=_usage_path())
    args = parser.parse_args()
    if args.command == "summarize":
        _print_markdown(summarize_rows(read_rows(args.path)))


if __name__ == "__main__":
    main()
