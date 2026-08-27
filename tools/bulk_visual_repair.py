#!/usr/bin/env python3
"""Resumable, fail-closed production orchestrator for strict visual repair."""

from __future__ import annotations

import argparse
import base64
from collections import OrderedDict
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

import story_bot as sb

from tools.bulk_visual_board import build_board, repair_backlog, write_board
from tools.bulk_visual_identity import (
    discover_verified_logo_identity, download_commons_logo,
    resolve_existing_logo_identity,
)
from tools.bulk_visual_register import register_logo, register_photo
from tools.bulk_visual_sources import (
    discover_commons, discover_first_party, discover_loc, discover_openverse,
    plan_story_beats,
)
from tools.bulk_visual_validate import (
    ReviewerConfigurationError, VisualDuplicateIndex, identity_proven, validate_candidate,
)


OUT_DIR = Path("out/bulk-visual-repair")
ALLOWED_FAILURES = frozenset({
    "SOURCE_UNAVAILABLE", "NO_SAFE_CANDIDATE", "IDENTITY_UNPROVEN",
    "DUPLICATE_ONLY", "LOGO_IDENTITY_MISSING", "VALIDATION_ERROR",
    "EXTERNAL_API_ERROR",
})


@dataclass(frozen=True)
class BatchResult:
    progress: int
    processed: int
    exit_code: int


def _gap(row):
    return row.need_photos + int(row.need_logo)


def process_rows(rows, batch_stories, repair_logo_fn, repair_photos_fn,
                 refresh_fn, attempt_fn):
    """Process a bounded set while treating refreshed runtime coverage as truth."""
    selected = [row for row in rows if row.status != "PASS"][:max(0, batch_stories)]
    progress = processed = 0
    invariant = False
    refreshed = {row.story: row for row in rows}
    for original in selected:
        story_started = time.monotonic()
        processed += 1
        current = original
        claimed = 0
        if current.need_logo:
            try:
                writes = int(repair_logo_fn(current.story) or 0)
                claimed += writes
                current = refresh_fn(current.story)
            except Exception as exc:
                attempt_fn({"story": original.story, "kind": "logo", "source": "orchestrator",
                            "result": "SOURCE_UNAVAILABLE",
                            "reason": f"{exc.__class__.__name__}: {exc}"})
        # A logo-source outage must not prevent independent photo sources from
        # repairing the same story (and vice versa).
        if current.need_photos:
            try:
                writes = int(repair_photos_fn(current.story, current.need_photos) or 0)
                claimed += writes
                current = refresh_fn(current.story)
            except ReviewerConfigurationError:
                raise
            except Exception as exc:
                attempt_fn({"story": original.story, "kind": "photo", "source": "orchestrator",
                        "result": "SOURCE_UNAVAILABLE",
                        "reason": f"{exc.__class__.__name__}: {exc}"})
                # Capture any runtime-visible progress made before the source
                # failed, rather than discarding resumable work.
                current = refresh_fn(current.story)
        refreshed[original.story] = current
        reduction = max(0, _gap(original) - _gap(current))
        attempt_fn({"story": original.story, "kind": "runtime-coverage", "source": "runtime",
                    "result": "ACCEPTED" if reduction else "NO_SAFE_CANDIDATE",
                    "reason": ("story_runtime.coverage() reduced the deficit" if reduction else
                               "story_runtime.coverage() reported no deficit reduction"),
                    "before_gap": _gap(original), "after_gap": _gap(current),
                    "claimed_writes": claimed, "elapsed_seconds": time.monotonic() - story_started})
        # Registration functions report writes for observability only. Runtime
        # coverage is both the progress counter and the invariant authority:
        # over-claiming (including two writes that close one slot) is just as
        # unsafe as a wholly invisible registration.
        progress += reduction
        if claimed != reduction:
            invariant = True
            attempt_fn({"story": original.story, "kind": "invariant", "source": "runtime",
                        "result": "VALIDATION_ERROR",
                        "reason": (f"claimed {claimed} registration(s), but refreshed "
                                   f"story_runtime.coverage() reduced the deficit by {reduction}")})
    if invariant:
        return BatchResult(progress, processed, 3)
    remaining = any(row.status != "PASS" for row in refreshed.values())
    return BatchResult(progress, processed, 10 if progress and remaining else (2 if remaining else 0))


def append_attempt(record, path=OUT_DIR / "attempts.jsonl"):
    record = dict(record)
    result = record.get("result")
    if result != "ACCEPTED" and result not in ALLOWED_FAILURES:
        raise ValueError(f"invalid attempt result: {result}")
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


_DOWNLOAD_CACHE = OrderedDict()
_TRANSIENT_HTTP = frozenset({429, 500, 502, 503, 504})
_REVIEWER_CONFIGURATION_FAILURE = None
_REVIEW_VERDICTS = ("DIRECT", "STRONG_CONTEXT", "WEAK_GENERIC", "WRONG_ENTITY")
_REVIEW_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(_REVIEW_VERDICTS)},
        "reason": {"type": "string"},
        "source_metadata_sufficient": {"type": "boolean"},
    },
    "required": ["verdict", "reason", "source_metadata_sufficient"],
    "additionalProperties": False,
}
_MAX_RESPONSE_BYTES = 1024 * 1024


def _download(candidate, destination, *, sleep=time.sleep):
    """Materialize once per stable source, retrying only bounded transient failures."""
    if candidate.source_id in _DOWNLOAD_CACHE:
        _DOWNLOAD_CACHE.move_to_end(candidate.source_id)
        Path(destination).write_bytes(_DOWNLOAD_CACHE[candidate.source_id]); return
    request = Request(candidate.direct_url, headers={
        "User-Agent": "daily-news-snap/1.0 (visual repair; contact: repository maintainers)",
        "Accept": "image/avif,image/webp,image/jpeg,image/png,*/*;q=0.5",
    })
    for attempt in range(3 if candidate.source == "commons" else 2):
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read()
            _DOWNLOAD_CACHE[candidate.source_id] = content
            if len(_DOWNLOAD_CACHE) > 16:
                _DOWNLOAD_CACHE.popitem(last=False)
            Path(destination).write_bytes(content)
            return
        except HTTPError as exc:
            if exc.code not in _TRANSIENT_HTTP or attempt + 1 >= (3 if candidate.source == "commons" else 2):
                raise
            header = exc.headers.get("Retry-After") if exc.headers else None
            try: delay = min(2.0, max(0.0, float(header)))
            except (TypeError, ValueError): delay = 0.25 * (2 ** attempt)
            sleep(delay)
        except (TimeoutError, URLError):
            if attempt + 1 >= (3 if candidate.source == "commons" else 2): raise
            sleep(0.25 * (2 ** attempt))


def catalogue_photo_paths():
    """Return every runtime-relevant local photo for global deduplication."""
    names = {name for row in build_board() for name in row.photos}
    return [Path("images") / name for name in sorted(names)]


def refresh_runtime_row(story):
    """Reload story identity metadata before authoritative post-write coverage."""
    sb.load_stories()
    return build_board([story])[0]


def _safe_api_error(exc, api_key):
    """Return bounded Anthropic error details without reflecting credentials."""
    error_type, message = "", ""
    try:
        raw = exc.read(64 * 1024)
        body = json.loads(raw.decode("utf-8", errors="replace"))
        error = body.get("error", {}) if isinstance(body, dict) else {}
        if isinstance(error, dict):
            error_type = str(error.get("type", ""))
            message = str(error.get("message", ""))
    except (AttributeError, OSError, TypeError, ValueError):
        pass
    finally:
        try:
            exc.close()
        except (AttributeError, OSError):
            pass
    # API responses should never contain the credential, but redact it (and
    # truncate remote text) rather than trusting that invariant in telemetry.
    if api_key:
        error_type = error_type.replace(api_key, "[REDACTED]")
        message = message.replace(api_key, "[REDACTED]")
    return error_type[:120], message[:500]


def _review_failure_telemetry(story, model, exc, api_key, retryable, attempt):
    error_type, message = _safe_api_error(exc, api_key)
    folded = f"{error_type} {message}".casefold()
    if exc.code == 401:
        category = "authentication"
    elif exc.code == 403:
        category = "permission"
    elif exc.code == 429:
        category = "rate_limit"
    elif 500 <= exc.code <= 599:
        category = "anthropic_service"
    elif (error_type.casefold() == "not_found_error" and "model" in message.casefold()) or (
            "model" in folded and
            any(word in folded for word in ("invalid", "not found", "unavailable"))):
        category = "invalid_model"
    else:
        category = "malformed_request_or_client_error"
    return {
        "story": story, "kind": "vision-review", "source": "anthropic",
        "result": "EXTERNAL_API_ERROR", "reason": "Anthropic reviewer HTTP failure",
        "http_status": exc.code, "api_error_type": error_type,
        "api_error_message": message, "model": model,
        "failure_category": category, "retryable": retryable, "attempt": attempt,
    }


def _parse_failure_telemetry(story, model, category, exc, *, output=b""):
    """Describe parsing failures without retaining reviewer text or other secrets."""
    bounded = output[:_MAX_RESPONSE_BYTES]
    return {
        "story": story, "kind": "vision-review", "source": "anthropic",
        "result": "EXTERNAL_API_ERROR", "reason": "Anthropic reviewer response parse failure",
        "model": model, "failure_category": category,
        "error_type": exc.__class__.__name__, "response_bytes": len(output),
        "response_truncated": len(output) > len(bounded),
        "response_sha256": hashlib.sha256(bounded).hexdigest(),
    }


def _parse_reviewer_output(body):
    """Strictly decode the single structured-output text block and its schema."""
    if not isinstance(body, dict) or not isinstance(body.get("content"), list):
        raise ValueError("unexpected Anthropic response envelope")
    blocks = body["content"]
    if len(blocks) != 1 or not isinstance(blocks[0], dict) or blocks[0].get("type") != "text" \
            or not isinstance(blocks[0].get("text"), str):
        raise ValueError("unexpected Anthropic response content")
    result = json.loads(blocks[0]["text"])
    required = {"verdict", "reason", "source_metadata_sufficient"}
    if not isinstance(result, dict) or set(result) != required:
        raise ValueError("reviewer output does not match required fields")
    if result["verdict"] not in _REVIEW_VERDICTS or not isinstance(result["reason"], str) \
            or type(result["source_metadata_sufficient"]) is not bool:
        raise ValueError("reviewer output does not match schema")
    return result


def _strict_relevance(story, candidate, path, *, telemetry_fn=append_attempt,
                      sleep=time.sleep, max_attempts=3):
    """Ask the configured vision reviewer; missing/error/invalid output rejects."""
    global _REVIEWER_CONFIGURATION_FAILURE
    if _REVIEWER_CONFIGURATION_FAILURE is not None:
        raise ReviewerConfigurationError(_REVIEWER_CONFIGURATION_FAILURE)
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is required for candidate approval")
    with Image.open(path) as image:
        image = image.convert("RGB"); image.thumbnail((1000, 1000))
        import io
        buffer = io.BytesIO(); image.save(buffer, "JPEG", quality=85)
    prompt = (
        "Judge this image for the exact "
        f"story {story!r}. Source title={candidate.title!r}; description={candidate.description!r}; "
        f"depicts={candidate.depicts!r}; beat={candidate.beat_key!r}. Never infer a person's identity "
        "from their face; source metadata is the identity proof."
    )
    model = os.environ.get("VISION_MODEL", "claude-sonnet-4-6")
    payload = {"model": model, "max_tokens": 300,
               "output_config": {"format": {"type": "json_schema",
                                             "schema": _REVIEW_OUTPUT_SCHEMA}},
               "messages": [{"role": "user", "content": [
                   {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                               "data": base64.b64encode(buffer.getvalue()).decode()}},
                   {"type": "text", "text": prompt}]}]}
    request = Request("https://api.anthropic.com/v1/messages", data=json.dumps(payload).encode(),
                      headers={"content-type": "application/json", "x-api-key": key,
                               "anthropic-version": "2023-06-01"})
    attempts = max(1, max_attempts)
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=75) as response:
                raw_body = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw_body) > _MAX_RESPONSE_BYTES:
                raise ValueError("Anthropic response envelope exceeds size limit")
            try:
                body = json.loads(raw_body)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                telemetry_fn(_parse_failure_telemetry(
                    story, model, "invalid_response_envelope_json", exc, output=raw_body))
                raise
            break
        except HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            # Read the response exactly once before a possible retry. This also
            # preserves the useful API error details that HTTPError otherwise hides.
            failure = _review_failure_telemetry(story, model, exc, key, retryable, attempt)
            telemetry_fn(failure)
            if failure["failure_category"] == "invalid_model":
                _REVIEWER_CONFIGURATION_FAILURE = (
                    f"invalid vision reviewer model {model}: {failure['api_error_message']}"
                )
                raise ReviewerConfigurationError(_REVIEWER_CONFIGURATION_FAILURE) from exc
            if not retryable or attempt == attempts:
                raise
            header = exc.headers.get("Retry-After") if exc.headers else None
            try:
                delay = min(4.0, max(0.0, float(header)))
            except (TypeError, ValueError):
                delay = 0.5 * (2 ** (attempt - 1))
            sleep(delay)
    try:
        return _parse_reviewer_output(body)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        text = (body.get("content", [{}])[0].get("text", "")
                if isinstance(body, dict) and isinstance(body.get("content"), list)
                and body["content"] and isinstance(body["content"][0], dict) else "")
        category = ("invalid_reviewer_output_json" if isinstance(exc, json.JSONDecodeError)
                    else "invalid_reviewer_output_schema")
        telemetry_fn(_parse_failure_telemetry(
            story, model, category, exc, output=text.encode("utf-8", errors="replace")))
        raise


def repair_logo(story, attempt_fn=append_attempt):
    local = resolve_existing_logo_identity(story)
    if local and local.domain:
        files = sorted(Path("images/logos").glob(f"{local.slug}-*.png"))
        if files:
            register_logo(files[0], story, local.domain, local.aliases)
            attempt_fn({"story": story, "kind": "logo", "source": "local-index",
                        "candidate": files[0].name, "result": "ACCEPTED", "reason": local.reason})
            return 1
    discovered = discover_verified_logo_identity(story)
    if not discovered:
        attempt_fn({"story": story, "kind": "logo", "source": "wikidata",
                    "result": "LOGO_IDENTITY_MISSING", "reason": "no unique verified identity"})
        return 0
    with tempfile.TemporaryDirectory() as td:
        logo = download_commons_logo(discovered.commons_filename, discovered.entity_label,
                                     Path(td) / "logo.png")
        if not logo:
            attempt_fn({"story": story, "kind": "logo", "source": "commons",
                        "source_page": discovered.source_url, "result": "VALIDATION_ERROR",
                        "reason": "logo download/decode/render validation failed"})
            return 0
        register_logo(logo, story, discovered.domain,
                      (discovered.entity_label, *discovered.aliases))
    attempt_fn({"story": story, "kind": "logo", "source": "wikidata/commons",
                "source_page": discovered.source_url, "candidate": discovered.commons_filename,
                "result": "ACCEPTED", "reason": "exact Wikidata identity with P154 and P856"})
    return 1


def repair_photos(story, deficit, max_candidates_per_beat=12, attempt_fn=append_attempt):
    accepted = 0
    # A photo relevant to another story still cannot be imported as a second
    # catalogue asset. Newly accepted paths are appended below during the run.
    existing = catalogue_photo_paths()
    duplicate_index = VisualDuplicateIndex.from_paths(existing)
    seen_source_ids = set()
    for beat in plan_story_beats(story):
        if accepted >= deficit:
            break
        adapters = [("commons", discover_commons), ("loc", discover_loc),
                    ("openverse", discover_openverse)]
        domain = sb.story_logo_domain(story)
        if domain:
            adapters.append(("first-party", lambda planned, limit, **kwargs:
                             discover_first_party(planned, domain, limit, **kwargs)))
        for source, adapter in adapters:
            if accepted >= deficit:
                break
            try:
                discovery_started = time.monotonic()
                candidates = adapter(beat, max_candidates_per_beat,
                                     excluded_source_ids=seen_source_ids)
                discovery_seconds = time.monotonic() - discovery_started
            except ReviewerConfigurationError:
                raise
            except Exception as exc:
                discovery_seconds = time.monotonic() - discovery_started
                attempt_fn({"story": story, "kind": "photo", "beat": beat.key, "source": source,
                            "result": "SOURCE_UNAVAILABLE", "reason": f"{exc.__class__.__name__}: {exc}",
                            "discovery_seconds": discovery_seconds, "candidate_count": 0})
                continue
            if not candidates:
                attempt_fn({"story": story, "kind": "photo", "beat": beat.key,
                            "source": source, "result": "NO_SAFE_CANDIDATE",
                            "reason": "discovery returned no candidates",
                            "discovery_seconds": discovery_seconds,
                            "candidate_count": 0})
            for candidate in candidates:
                if accepted >= deficit:
                    break
                if candidate.source_id in seen_source_ids:
                    attempt_fn({"story": story, "kind": "photo", "beat": beat.key,
                                "source": source, "source_page": candidate.source_page,
                                "candidate": candidate.title, "result": "DUPLICATE_ONLY",
                                "reason": "candidate source_id already evaluated",
                                "discovery_seconds": discovery_seconds,
                                "validation_seconds": 0.0})
                    continue
                seen_source_ids.add(candidate.source_id)
                validation_started = time.monotonic()
                # Keep this explicit preflight observable. validate_candidate
                # repeats the gate so direct callers remain fail closed.
                if not identity_proven(candidate):
                    validation_seconds = time.monotonic() - validation_started
                    attempt_fn({"story": story, "kind": "photo", "beat": beat.key,
                                "source": source, "source_page": candidate.source_page,
                                "candidate": candidate.title, "result": "IDENTITY_UNPROVEN",
                                "reason": "required identity absent from source metadata; fetch skipped",
                                "discovery_seconds": discovery_seconds,
                                "validation_seconds": validation_seconds,
                                "fetch_skipped": True})
                    continue
                measured = {"fetch": 0.0, "model_review": 0.0}
                def measured_download(item, path):
                    phase_started = time.monotonic()
                    try:
                        return _download(item, path)
                    finally:
                        measured["fetch"] += time.monotonic() - phase_started
                def measured_review(item_story, item, path):
                    phase_started = time.monotonic()
                    try:
                        return _strict_relevance(item_story, item, path)
                    finally:
                        measured["model_review"] += time.monotonic() - phase_started
                result = validate_candidate(story, candidate, existing, OUT_DIR / "tmp",
                                            measured_review, measured_download, duplicate_index)
                validation_seconds = time.monotonic() - validation_started
                measured.update(result.phase_seconds)
                record = {"story": story, "kind": "photo", "beat": beat.key, "source": source,
                          "source_page": candidate.source_page, "candidate": candidate.title,
                          "result": "ACCEPTED" if result.accepted else result.reason.split(":", 1)[0],
                          "reason": f"{result.verdict}; {result.reason}".strip("; "),
                          "discovery_seconds": discovery_seconds,
                          "validation_seconds": validation_seconds,
                          "phase_seconds": measured}
                if record["result"] not in ALLOWED_FAILURES | {"ACCEPTED"}:
                    record["result"] = "VALIDATION_ERROR"
                attempt_fn(record)
                if not result.accepted:
                    continue
                destination = register_photo(story, candidate, result)
                result.temp_path.unlink(missing_ok=True)
                existing.append(destination); accepted += 1
                duplicate_index.add(result.sha256, result.dhash)
                refreshed = build_board([story])[0]
                if len(refreshed.photos) < len(existing):
                    raise RuntimeError("registered photo absent from runtime coverage")
    if not accepted:
        attempt_fn({"story": story, "kind": "photo", "source": "all",
                    "result": "NO_SAFE_CANDIDATE", "reason": "source tiers exhausted"})
    return accepted


def _write_unresolved(rows, path=OUT_DIR / "unresolved.json"):
    unresolved = [asdict(row) for row in rows if row.status != "PASS"]
    Path(path).write_text(json.dumps(unresolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-stories", type=int, default=15)
    parser.add_argument("--max-candidates-per-beat", type=int, default=12)
    parser.add_argument("--board-only", action="store_true")
    parser.add_argument("--story")
    args = parser.parse_args(argv)
    stories = [args.story] if args.story else None
    rows = build_board(stories); write_board(rows, OUT_DIR); _write_unresolved(rows)
    if args.board_only:
        return 0 if len(rows) == 123 and all(row.status == "PASS" for row in rows) else 2
    backlog = repair_backlog(rows)
    try:
        result = process_rows(
            backlog, args.batch_stories, repair_logo,
            lambda story, deficit: repair_photos(story, deficit, args.max_candidates_per_beat),
            refresh_runtime_row, append_attempt,
        )
    except ReviewerConfigurationError as exc:
        append_attempt({"story": args.story or "batch", "kind": "invariant",
                        "source": "anthropic", "result": "VALIDATION_ERROR",
                        "reason": str(exc)})
        return 3
    final = build_board(stories); write_board(final, OUT_DIR); _write_unresolved(final)
    # Only the complete catalogue may return completion, never a selected story.
    if len(final) == 123 and all(row.status == "PASS" for row in final):
        return 0
    return 3 if result.exit_code == 3 else (10 if result.progress else 2)


if __name__ == "__main__":
    raise SystemExit(main())
