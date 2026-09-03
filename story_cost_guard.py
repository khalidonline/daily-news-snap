"""Hard editorial-model call guard and append-only usage ledger."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


MAX_EDITORIAL_CALLS_PER_REVISION = int(os.getenv("MAX_EDITORIAL_CALLS_PER_REVISION", "1") or "1")


class OperationMode(str, Enum):
    AUTO = "auto"
    VISUAL_ONLY = "visual_only"
    REGENERATE_EDITORIAL = "regenerate_editorial"


class EditorialSpendBlocked(RuntimeError):
    """Raised when policy forbids another paid editorial call."""


class AuxModelSpendBlocked(RuntimeError):
    """Raised before an auxiliary model call exceeds its run ceiling."""


_AUX_PRICES = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
}
_aux_paid_responses = 0


@dataclass(frozen=True)
class CallReservation:
    story: str
    revision: str
    guard_revision: str
    mode: str
    reserved_at: str
    run_id: str | None
    run_attempt: str | None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_root() -> Path:
    return Path(os.getenv("STORY_COST_STATE_ROOT", "state"))


def usage_ledger_path() -> Path:
    return _state_root() / "model_usage.jsonl"


def _guard_dir() -> Path:
    return _state_root() / "model_call_guard"


def _guard_path(guard_revision: str) -> Path:
    safe = hashlib.sha256(guard_revision.encode("utf-8")).hexdigest()
    return _guard_dir() / f"{safe}.json"


def _append_row(row: dict[str, Any]) -> None:
    path = usage_ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _run_identity(run_id: str | None = None, run_attempt: str | None = None) -> tuple[str | None, str | None]:
    return (
        str(run_id) if run_id is not None else (os.getenv("GITHUB_RUN_ID") or None),
        str(run_attempt) if run_attempt is not None else (os.getenv("GITHUB_RUN_ATTEMPT") or None),
    )


def _coerce_mode(mode: str | OperationMode) -> str:
    value = mode.value if isinstance(mode, OperationMode) else str(mode or "auto")
    if value not in {item.value for item in OperationMode}:
        raise ValueError(f"unknown STORY_OPERATION_MODE: {value}")
    return value


def _guard_revision(revision: str, mode: str) -> str:
    if mode != OperationMode.REGENERATE_EDITORIAL.value:
        return revision
    nonce = (os.getenv("STORY_REGENERATION_NONCE") or "").strip()
    if not nonce:
        raise EditorialSpendBlocked("regenerate_editorial requires STORY_REGENERATION_NONCE")
    nonce_digest = hashlib.sha256(nonce.encode("utf-8")).hexdigest()[:16]
    return f"{revision}--regen--{nonce_digest}"


def reserve_editorial_call(story: str, revision: str, mode: str | OperationMode) -> CallReservation:
    selected = _coerce_mode(mode)
    if selected == OperationMode.VISUAL_ONLY.value:
        raise EditorialSpendBlocked("visual_only forbids editorial model calls")
    if MAX_EDITORIAL_CALLS_PER_REVISION < 1:
        raise EditorialSpendBlocked("editorial model calls disabled by MAX_EDITORIAL_CALLS_PER_REVISION")

    guard_revision = _guard_revision(str(revision), selected)
    marker = _guard_path(guard_revision)
    marker.parent.mkdir(parents=True, exist_ok=True)
    run_id, run_attempt = _run_identity()
    reserved_at = _utcnow()
    payload = {
        "story": story,
        "revision": revision,
        "guard_revision": guard_revision,
        "mode": selected,
        "reserved_at": reserved_at,
        "run_id": run_id,
        "run_attempt": run_attempt,
    }
    try:
        with marker.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        _append_row({
            "timestamp": _utcnow(),
            "event": "call_block",
            "story": story,
            "revision": revision,
            "guard_revision": guard_revision,
            "mode": selected,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "reason": "editorial call already reserved for revision",
        })
        raise EditorialSpendBlocked("editorial call already reserved for revision") from exc

    return CallReservation(
        story=story,
        revision=str(revision),
        guard_revision=guard_revision,
        mode=selected,
        reserved_at=reserved_at,
        run_id=run_id,
        run_attempt=run_attempt,
    )


def _estimated_usd(
    input_tokens: int | None,
    output_tokens: int | None,
    web_search_requests: int | None = 0,
) -> float | None:
    input_price = os.getenv("STORY_MODEL_INPUT_USD_PER_M")
    output_price = os.getenv("STORY_MODEL_OUTPUT_USD_PER_M")
    if input_price in (None, "") or output_price in (None, ""):
        return None
    try:
        in_rate = float(input_price)
        out_rate = float(output_price)
        in_tokens = int(input_tokens or 0)
        out_tokens = int(output_tokens or 0)
    except (TypeError, ValueError):
        return None
    return round(
        (in_tokens / 1_000_000) * in_rate
        + (out_tokens / 1_000_000) * out_rate
        + int(web_search_requests or 0) * 0.01,
        6,
    )


def record_model_result(
    reservation: CallReservation,
    *,
    model: str,
    message_id: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    status: str,
    web_search_requests: int | None = 0,
) -> None:
    _append_row({
        "timestamp": _utcnow(),
        "event": "model_result",
        "purpose": "forced_regeneration" if reservation.mode == OperationMode.REGENERATE_EDITORIAL.value else "editorial_generation",
        "story": reservation.story,
        "revision": reservation.revision,
        "guard_revision": reservation.guard_revision,
        "mode": reservation.mode,
        "model": model,
        "message_id": message_id,
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "web_search_requests": int(web_search_requests or 0),
        "estimated_usd": _estimated_usd(
            input_tokens, output_tokens, web_search_requests
        ),
        "status": status,
        "cache_hit": False,
        "run_id": reservation.run_id,
        "run_attempt": reservation.run_attempt,
    })


def require_aux_model_capacity() -> None:
    limit = int(os.getenv("STORY_AUX_MAX_PAID_RESPONSES", "50") or "50")
    if limit < 1 or _aux_paid_responses >= limit:
        raise AuxModelSpendBlocked(
            f"auxiliary paid-response ceiling reached: {_aux_paid_responses}/{limit}"
        )


def _aux_estimated_usd(model: str, usage: dict[str, Any]) -> float | None:
    rates = _AUX_PRICES.get(str(model or ""))
    if rates is None:
        return None
    server = usage.get("server_tool_use") or {}
    searches = int(server.get("web_search_requests") or 0) \
        if isinstance(server, dict) else 0
    return round(
        int(usage.get("input_tokens") or 0) * rates[0] / 1_000_000
        + int(usage.get("output_tokens") or 0) * rates[1] / 1_000_000
        + searches * 0.01,
        6,
    )


def record_aux_model_result(
    *, purpose: str, model: str, response: dict[str, Any]
) -> dict[str, Any]:
    usage = response.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    server = usage.get("server_tool_use") or {}
    searches = int(server.get("web_search_requests") or 0) \
        if isinstance(server, dict) else 0
    run_id, run_attempt = _run_identity()
    row = {
        "timestamp": _utcnow(),
        "event": "aux_model_result",
        "provider": "anthropic",
        "purpose": str(purpose),
        "story": os.getenv("STORY_USAGE_CONTEXT", "").strip(),
        "model": str(model),
        "message_id": response.get("id"),
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "web_search_requests": searches,
        "estimated_usd": _aux_estimated_usd(model, usage),
        "run_id": run_id,
        "run_attempt": run_attempt,
    }
    _append_row(row)
    global _aux_paid_responses
    _aux_paid_responses += 1
    return row


def reset_aux_run_state() -> None:
    global _aux_paid_responses
    _aux_paid_responses = 0


def record_cache_hit(
    story: str,
    revision: str,
    run_id: str | None = None,
    run_attempt: str | None = None,
) -> None:
    resolved_run_id, resolved_attempt = _run_identity(run_id, run_attempt)
    _append_row({
        "timestamp": _utcnow(),
        "event": "cache_hit",
        "story": story,
        "revision": revision,
        "mode": _coerce_mode(os.getenv("STORY_OPERATION_MODE", "auto")),
        "cache_hit": True,
        "run_id": resolved_run_id,
        "run_attempt": resolved_attempt,
    })


def record_operation_event(story: str, revision: str, event: str, **extra: Any) -> None:
    run_id, run_attempt = _run_identity()
    row = {
        "timestamp": _utcnow(),
        "event": event,
        "story": story,
        "revision": revision,
        "run_id": run_id,
        "run_attempt": run_attempt,
    }
    row.update(extra)
    _append_row(row)
