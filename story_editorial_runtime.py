"""Cost-controlled editorial research wrapper for Story-to-Snapchat."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from typing import Any

import story_brief_store as sbs
import story_cost_guard as scg
import story_editorial_quality as seq


_CONFIGURED_ATTR = "_story_editorial_runtime_configured"


def _mode() -> str:
    return (os.getenv("STORY_OPERATION_MODE") or "auto").strip() or "auto"


def _active_prompt(sb: Any) -> str:
    provider = getattr(sb, "editorial_prompt_for_revision", None)
    prompt = provider() if callable(provider) else str(getattr(sb, "SYSTEM_PROMPT", "") or "")
    frames = int(getattr(sb, "STORY_FRAMES", 6))
    try:
        return prompt.format(n=frames)
    except (KeyError, IndexError, ValueError):
        return prompt


def revision_for(sb: Any, story: str, mode: str | None = None) -> str:
    selected = (mode or _mode()).strip() or "auto"
    prompt = _active_prompt(sb)
    if selected == scg.OperationMode.REGENERATE_EDITORIAL.value:
        nonce = (os.getenv("STORY_REGENERATION_NONCE") or "").strip()
        if not nonce:
            raise scg.EditorialSpendBlocked(
                "regenerate_editorial requires STORY_REGENERATION_NONCE"
            )
        # Explicit regeneration is a new revision. Reusing the same nonce is
        # intentionally idempotent so a GitHub rerun cannot buy it twice.
        prompt = prompt + "\n[explicit-regeneration:" + hashlib.sha256(
            nonce.encode("utf-8")
        ).hexdigest() + "]"
    return sbs.revision_key(
        story,
        prompt,
        str(getattr(sb, "STORY_MODEL", "")),
        int(getattr(sb, "STORY_FRAMES", 6)),
    )


def _usage(sb: Any) -> dict[str, Any]:
    raw = getattr(sb, "_LAST_EDITORIAL_USAGE", {}) or {}
    return raw if isinstance(raw, dict) else {}


def _record_result(sb: Any, reservation: scg.CallReservation, status: str) -> None:
    usage = _usage(sb)
    scg.record_model_result(
        reservation,
        model=str(getattr(sb, "STORY_MODEL", "")),
        message_id=usage.get("message_id"),
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        status=status,
    )


class _CapturedResponse:
    """Proxy an HTTP 200 response while capturing Anthropic usage metadata."""

    def __init__(self, raw: Any, sb: Any):
        self._raw = raw
        self._reader = raw
        self._sb = sb

    def __enter__(self):
        enter = getattr(self._raw, "__enter__", None)
        self._reader = enter() if callable(enter) else self._raw
        return self

    def __exit__(self, exc_type, exc, tb):
        exit_fn = getattr(self._raw, "__exit__", None)
        if callable(exit_fn):
            return exit_fn(exc_type, exc, tb)
        close = getattr(self._raw, "close", None)
        if callable(close):
            close()
        return False

    def read(self, *args, **kwargs):
        data = self._reader.read(*args, **kwargs)
        try:
            payload = json.loads(data)
            usage = payload.get("usage") or {}
            self._sb._LAST_EDITORIAL_USAGE = {
                "message_id": payload.get("id"),
                "input_tokens": int(usage.get("input_tokens") or 0),
                "output_tokens": int(usage.get("output_tokens") or 0),
            }
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        return data

    def __getattr__(self, name: str):
        return getattr(self._reader, name)


def _research_with_paid_response_ceiling(sb: Any, research_fn: Any, story: str):
    """Allow at most one successful Messages HTTP response per revision.

    Transport/HTTP failures that raise before a response is returned can still
    retry inside the existing Story Bot. Once one HTTP response succeeds,
    however, a pause-turn or truncation continuation would create another
    separately billable Anthropic message and is blocked fail-closed.
    """
    urllib_module = getattr(sb, "urllib", None)
    request_module = getattr(urllib_module, "request", None)
    original_urlopen = getattr(request_module, "urlopen", None)
    if not callable(original_urlopen):
        return research_fn(story)

    successful_responses = 0

    def guarded_urlopen(*args, **kwargs):
        nonlocal successful_responses
        if successful_responses >= 1:
            raise scg.EditorialSpendBlocked(
                "editorial paid-response ceiling reached; explicit regeneration required"
            )
        response = original_urlopen(*args, **kwargs)
        successful_responses += 1
        return _CapturedResponse(response, sb)

    request_module.urlopen = guarded_urlopen
    try:
        return research_fn(story)
    finally:
        request_module.urlopen = original_urlopen


def configure(story_bot_module: Any) -> Any:
    """Wrap the already-focused research function with cache and spend policy."""
    sb = story_bot_module
    if getattr(sb, _CONFIGURED_ATTR, False):
        return sb

    original_research = sb.research
    sb._story_editorial_uncached_research = original_research

    def _controlled_research(story: str):
        selected = _mode()
        revision = revision_for(sb, story, selected)

        # Existing cache entries are authoritative. Malformed/corrupt entries
        # raise BriefCacheError here and never become permission to regenerate.
        cached = sbs.load_locked_brief(story, revision)
        if cached is not None:
            print(f"    EDITORIAL_CACHE_HIT {revision[:12]}")
            scg.record_cache_hit(story, revision)
            return copy.deepcopy(cached["brief"])

        if selected == scg.OperationMode.VISUAL_ONLY.value:
            scg.record_operation_event(
                story, revision, "visual_only_block",
                mode=selected,
                reason="missing EDITORIAL_LOCKED cache",
            )
            raise SystemExit(
                "visual_only requires an EDITORIAL_LOCKED cached brief"
            )

        reservation = scg.reserve_editorial_call(story, revision, selected)
        sb._LAST_EDITORIAL_USAGE = {}
        try:
            brief = _research_with_paid_response_ceiling(sb, original_research, story)
        except BaseException:
            _record_result(sb, reservation, "error")
            raise

        quality = seq.evaluate_brief(
            brief, int(getattr(sb, "STORY_FRAMES", 6))
        )
        if not quality.passed:
            _record_result(sb, reservation, "editorial_review")
            scg.record_operation_event(
                story, revision, "editorial_review",
                reasons=list(quality.reasons),
            )
            raise SystemExit(
                "editorial quality gate failed: " + "; ".join(quality.reasons)
            )

        _record_result(sb, reservation, "success")
        usage = _usage(sb)
        sbs.save_locked_brief(
            story,
            revision,
            {
                "status": "EDITORIAL_LOCKED",
                "brief": copy.deepcopy(brief),
                "model": str(getattr(sb, "STORY_MODEL", "")),
                "message_id": usage.get("message_id"),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "prompt_hash": hashlib.sha256(
                    _active_prompt(sb).encode("utf-8")
                ).hexdigest(),
            },
        )
        print(f"    EDITORIAL_LOCKED {revision[:12]}")
        return copy.deepcopy(brief)

    def controlled_research(story: str):
        marker = "_ACTIVE_EDITORIAL_STORY"
        previous = getattr(sb, marker, None)
        setattr(sb, marker, str(story or "").strip())
        try:
            return _controlled_research(story)
        finally:
            if previous is None:
                try:
                    delattr(sb, marker)
                except AttributeError:
                    pass
            else:
                setattr(sb, marker, previous)

    sb.research = controlled_research
    setattr(sb, _CONFIGURED_ATTR, True)
    return sb
