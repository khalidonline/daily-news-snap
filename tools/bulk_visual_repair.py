#!/usr/bin/env python3
"""Resumable, fail-closed production orchestrator for strict visual repair."""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile
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
from tools.bulk_visual_validate import validate_candidate


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
            except Exception as exc:
                attempt_fn({"story": original.story, "kind": "photo", "source": "orchestrator",
                        "result": "SOURCE_UNAVAILABLE",
                        "reason": f"{exc.__class__.__name__}: {exc}"})
                # Capture any runtime-visible progress made before the source
                # failed, rather than discarding resumable work.
                current = refresh_fn(current.story)
        refreshed[original.story] = current
        reduction = max(0, _gap(original) - _gap(current))
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


def _download(candidate, destination):
    request = Request(candidate.direct_url, headers={"User-Agent": "daily-news-snap/1.0 (visual repair)"})
    with urlopen(request, timeout=60) as response:
        Path(destination).write_bytes(response.read())


def catalogue_photo_paths():
    """Return every runtime-relevant local photo for global deduplication."""
    names = {name for row in build_board() for name in row.photos}
    return [Path("images") / name for name in sorted(names)]


def refresh_runtime_row(story):
    """Reload story identity metadata before authoritative post-write coverage."""
    sb.load_stories()
    return build_board([story])[0]


def _strict_relevance(story, candidate, path):
    """Ask the configured vision reviewer; missing/error/invalid output rejects."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is required for candidate approval")
    with Image.open(path) as image:
        image = image.convert("RGB"); image.thumbnail((1000, 1000))
        import io
        buffer = io.BytesIO(); image.save(buffer, "JPEG", quality=85)
    prompt = (
        "Return JSON only with verdict, reason, source_metadata_sufficient. Verdict must be "
        "DIRECT, STRONG_CONTEXT, WEAK_GENERIC, or WRONG_ENTITY. Judge this image for the exact "
        f"story {story!r}. Source title={candidate.title!r}; description={candidate.description!r}; "
        f"depicts={candidate.depicts!r}; beat={candidate.beat_key!r}. Never infer a person's identity "
        "from their face; source metadata is the identity proof."
    )
    payload = {"model": os.environ.get("VISION_MODEL", "claude-sonnet-4-20250514"), "max_tokens": 300,
               "messages": [{"role": "user", "content": [
                   {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                               "data": base64.b64encode(buffer.getvalue()).decode()}},
                   {"type": "text", "text": prompt}]}]}
    request = Request("https://api.anthropic.com/v1/messages", data=json.dumps(payload).encode(),
                      headers={"content-type": "application/json", "x-api-key": key,
                               "anthropic-version": "2023-06-01"})
    with urlopen(request, timeout=75) as response:
        body = json.load(response)
    text = "".join(item.get("text", "") for item in body.get("content", [])
                   if item.get("type") == "text").strip()
    return json.loads(text)


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
    for beat in plan_story_beats(story):
        if accepted >= deficit:
            break
        adapters = [("commons", discover_commons), ("loc", discover_loc),
                    ("openverse", discover_openverse)]
        domain = sb.story_logo_domain(story)
        if domain:
            adapters.append(("first-party", lambda planned, limit:
                             discover_first_party(planned, domain, limit)))
        for source, adapter in adapters:
            if accepted >= deficit:
                break
            try:
                candidates = adapter(beat, max_candidates_per_beat)
            except Exception as exc:
                attempt_fn({"story": story, "kind": "photo", "beat": beat.key, "source": source,
                            "result": "SOURCE_UNAVAILABLE", "reason": f"{exc.__class__.__name__}: {exc}"})
                continue
            for candidate in candidates:
                if accepted >= deficit:
                    break
                result = validate_candidate(story, candidate, existing, OUT_DIR / "tmp",
                                            _strict_relevance, _download)
                record = {"story": story, "kind": "photo", "beat": beat.key, "source": source,
                          "source_page": candidate.source_page, "candidate": candidate.title,
                          "result": "ACCEPTED" if result.accepted else result.reason.split(":", 1)[0],
                          "reason": f"{result.verdict}; {result.reason}".strip("; ")}
                if record["result"] not in ALLOWED_FAILURES | {"ACCEPTED"}:
                    record["result"] = "VALIDATION_ERROR"
                attempt_fn(record)
                if not result.accepted:
                    continue
                destination = register_photo(story, candidate, result)
                result.temp_path.unlink(missing_ok=True)
                existing.append(destination); accepted += 1
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
    result = process_rows(
        backlog, args.batch_stories, repair_logo,
        lambda story, deficit: repair_photos(story, deficit, args.max_candidates_per_beat),
        refresh_runtime_row, append_attempt,
    )
    final = build_board(stories); write_board(final, OUT_DIR); _write_unresolved(final)
    # Only the complete catalogue may return completion, never a selected story.
    if len(final) == 123 and all(row.status == "PASS" for row in final):
        return 0
    return 3 if result.exit_code == 3 else (10 if result.progress else 2)


if __name__ == "__main__":
    raise SystemExit(main())
