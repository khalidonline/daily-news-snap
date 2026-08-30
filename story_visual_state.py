"""Revision-scoped Story visual state and failed-frame-only repair helpers."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable, Iterable

import story_editorial_runtime as ser


VISUAL_STATE_SCHEMA = "story-visual-v1"
_CONFIGURED_ATTR = "_story_visual_state_configured"
_FRAME_NO_RE = re.compile(r"story-frame-(\d+)")
_SIDECARS = (".exempt", ".generated")


def _root() -> Path:
    return Path(os.getenv("STORY_VISUAL_STATE_ROOT", "state/story_visuals"))


def _story_id(story: str) -> str:
    normalized = " ".join(str(story or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def visual_revision_dir(story: str, revision: str) -> Path:
    return _root() / _story_id(story) / str(revision)


def visual_state_path(story: str, revision: str) -> Path:
    return visual_revision_dir(story, revision) / "state.json"


def asset_dir(story: str, revision: str) -> Path:
    return visual_revision_dir(story, revision) / "assets"


def load_visual_state(story: str, revision: str) -> dict[str, Any]:
    path = visual_state_path(story, revision)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"malformed visual state: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("visual state must be an object")
    if payload.get("schema") not in (None, VISUAL_STATE_SCHEMA):
        raise RuntimeError("visual state schema mismatch")
    return {key: value for key, value in payload.items() if key != "schema"}


def save_visual_state(story: str, revision: str, state: dict[str, Any]) -> Path:
    dest = visual_state_path(story, revision)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    stored = {"schema": VISUAL_STATE_SCHEMA, **copy.deepcopy(state)}
    tmp.write_text(
        json.dumps(stored, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(dest)
    return dest


def failed_frame_indices(state: dict[str, Any]) -> tuple[int, ...]:
    frames = (state or {}).get("frames") or {}
    failed: list[int] = []
    for key, row in frames.items():
        try:
            frame_no = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(row, dict) or row.get("status") != "PASS":
            failed.append(frame_no)
    return tuple(sorted(failed))


def requested_repair_frame_indices(raw: str | None = None) -> tuple[int, ...]:
    """Parse human-requested visual repair slots from STORY_REPAIR_FRAMES."""
    if raw is None:
        raw = os.getenv("STORY_REPAIR_FRAMES", "")
    raw = str(raw or "").strip()
    if not raw:
        return ()
    frames: set[int] = set()
    for token in re.split(r"[,\s]+", raw):
        if not token:
            continue
        try:
            frame_no = int(token)
        except ValueError as exc:
            raise ValueError(
                f"invalid STORY_REPAIR_FRAMES token {token!r}; "
                "use comma-separated frame numbers"
            ) from exc
        if frame_no < 1:
            raise ValueError("STORY_REPAIR_FRAMES values must be >= 1")
        frames.add(frame_no)
    return tuple(sorted(frames))


def preserve_approved_frames(
    previous: dict[str, Any], incoming_frames: Iterable[dict], failed: Iterable[int]
) -> list[dict]:
    failed_set = {int(i) for i in failed}
    old_frames = (previous or {}).get("frames") or {}
    result: list[dict] = []
    for index, incoming in enumerate(incoming_frames, start=1):
        current = copy.deepcopy(incoming)
        old = old_frames.get(str(index)) or {}
        if index not in failed_set and old.get("status") == "PASS":
            payload = old.get("frame_payload")
            if isinstance(payload, dict):
                current = copy.deepcopy(payload)
            else:
                for key in ("heading", "text", "punch", "subject_kind",
                            "image_keywords", "image_keywords_ar"):
                    if key in old:
                        current[key] = copy.deepcopy(old[key])
        result.append(current)
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_sidecars(source: Path, dest: Path) -> None:
    for suffix in _SIDECARS:
        src = Path(str(source) + suffix)
        dst = Path(str(dest) + suffix)
        if src.exists():
            shutil.copy2(src, dst)
        else:
            dst.unlink(missing_ok=True)


def _asset_destination(story: str, revision: str, frame_no: int, source: Path) -> Path:
    suffix = source.suffix if source.suffix else ".jpg"
    return asset_dir(story, revision) / f"frame-{frame_no:02d}{suffix.lower()}"


def capture_visual_state(
    story: str,
    revision: str,
    brief: dict[str, Any],
    photos: Iterable[object],
) -> dict[str, Any]:
    frames = list((brief or {}).get("frames") or [])
    photos_list = list(photos or [])
    rows: dict[str, dict[str, Any]] = {}
    assets = asset_dir(story, revision)
    assets.mkdir(parents=True, exist_ok=True)

    for index, frame in enumerate(frames, start=1):
        photo = photos_list[index - 1] if index - 1 < len(photos_list) else None
        row: dict[str, Any] = {
            "status": "FAIL",
            "image_source": None,
            "asset_hash": None,
            "qa_reasons": ["no approved visual selected"],
            "frame_payload": copy.deepcopy(frame),
        }
        if photo:
            src = Path(str(photo))
            if src.exists() and src.is_file():
                dest = _asset_destination(story, revision, index, src)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if src.resolve() != dest.resolve():
                    shutil.copy2(src, dest)
                    _copy_sidecars(src, dest)
                row.update({
                    "status": "PASS",
                    "image_source": str(dest),
                    "asset_hash": _sha256(dest),
                    "qa_reasons": [],
                })
        rows[str(index)] = row

    state = {
        "status": "VISUAL_ASSEMBLY" if any(
            row["status"] != "PASS" for row in rows.values()
        ) else "VISUAL_READY",
        "story": story,
        "revision": revision,
        "frames": rows,
    }
    save_visual_state(story, revision, state)
    return state


def repair_visual_slots(
    previous: dict[str, Any],
    out_paths: Iterable[Path],
    search: Callable[[int, Path], object],
) -> list[str]:
    rows = (previous or {}).get("frames") or {}
    outputs: list[str] = []
    for frame_no, raw_out in enumerate(out_paths, start=1):
        out = Path(raw_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        row = rows.get(str(frame_no)) or {}
        source = Path(str(row.get("image_source") or ""))
        if row.get("status") == "PASS" and source.exists():
            shutil.copy2(source, out)
            _copy_sidecars(source, out)
            outputs.append(str(out))
            continue
        found = search(frame_no, out)
        if found:
            outputs.append(str(found))
    return outputs


def _frame_no_from_path(path: object) -> int | None:
    match = _FRAME_NO_RE.search(Path(str(path)).name)
    return int(match.group(1)) if match else None


def _effective_revision(sb: Any, story: str) -> str:
    mode = (os.getenv("STORY_OPERATION_MODE") or "auto").strip() or "auto"
    # visual_only consumes the same locked editorial revision created by auto.
    revision_mode = "auto" if mode == "visual_only" else mode
    return ser.revision_for(sb, story, revision_mode)


def _valid_reuse_map(
    state: dict[str, Any], excluded: Iterable[int] = ()
) -> dict[int, Path]:
    excluded_set = {int(i) for i in excluded}
    result: dict[int, Path] = {}
    for key, row in ((state or {}).get("frames") or {}).items():
        if not isinstance(row, dict) or row.get("status") != "PASS":
            continue
        try:
            frame_no = int(key)
        except (TypeError, ValueError):
            continue
        if frame_no in excluded_set:
            continue
        source = Path(str(row.get("image_source") or ""))
        if source.exists() and source.is_file():
            result[frame_no] = source
    return result


def _previous_rejected_digests(
    sb: Any, previous: dict[str, Any], requested: Iterable[int]
) -> dict[int, object]:
    result: dict[int, object] = {}
    if not hasattr(sb, "_photo_digest"):
        return result
    rows = (previous or {}).get("frames") or {}
    for frame_no in requested:
        row = rows.get(str(frame_no)) or {}
        source = Path(str(row.get("image_source") or ""))
        if row.get("status") != "PASS" or not source.exists():
            continue
        try:
            result[int(frame_no)] = sb._photo_digest(source)
        except Exception:
            continue
    return result


def _seen_with_rejected(sb: Any, seen: Iterable[object], rejected: object):
    values = list(seen or ())
    if rejected is None:
        return tuple(values)
    duplicate = False
    for prior in values:
        try:
            if sb.same_picture(rejected, prior):
                duplicate = True
                break
        except Exception:
            if rejected == prior:
                duplicate = True
                break
    if not duplicate:
        values.append(rejected)
    return tuple(values)


def _reject_unchanged_requested_photos(
    sb: Any,
    photos: Iterable[object],
    rejected_digests: dict[int, object],
) -> list[object]:
    result = list(photos or [])
    if not rejected_digests or not hasattr(sb, "_photo_digest"):
        return result
    for frame_no, rejected in rejected_digests.items():
        index = frame_no - 1
        if index < 0 or index >= len(result) or not result[index]:
            continue
        try:
            digest = sb._photo_digest(result[index])
            unchanged = sb.same_picture(digest, rejected)
        except Exception:
            unchanged = False
        if unchanged:
            print(
                f"    frame {frame_no}: targeted repair rejected unchanged prior visual"
            )
            result[index] = None
    return result


def configure(story_bot_module: Any) -> Any:
    """Wrap the final visual selector so visual_only repairs only requested slots."""
    sb = story_bot_module
    if getattr(sb, _CONFIGURED_ATTR, False):
        return sb

    original_find_all = sb.find_all_photos

    def visual_state_find_all(brief: dict[str, Any]):
        story = str((brief or {}).get("story", "") or "").strip()
        if not story:
            return original_find_all(brief)
        revision = _effective_revision(sb, story)
        mode = (os.getenv("STORY_OPERATION_MODE") or "auto").strip() or "auto"
        previous = load_visual_state(story, revision)
        requested = requested_repair_frame_indices() if mode == "visual_only" else ()
        frame_count = len(list((brief or {}).get("frames") or []))
        invalid = [frame_no for frame_no in requested if frame_no > frame_count]
        if invalid:
            raise ValueError(
                "STORY_REPAIR_FRAMES outside this deck: "
                + ", ".join(str(i) for i in invalid)
            )
        failed = failed_frame_indices(previous) if mode == "visual_only" else ()
        repair_slots = tuple(sorted(set(failed) | set(requested)))
        reuse = (
            _valid_reuse_map(previous, repair_slots)
            if mode == "visual_only" else {}
        )
        rejected_digests = (
            _previous_rejected_digests(sb, previous, requested)
            if mode == "visual_only" else {}
        )

        if mode == "visual_only" and previous:
            brief["frames"] = preserve_approved_frames(
                previous, list(brief.get("frames") or []), repair_slots
            )
            print(
                "    visual_only repair slots: "
                + (", ".join(str(i) for i in repair_slots) if repair_slots else "none")
            )
            if requested:
                print(
                    "    human-requested visual repair slots: "
                    + ", ".join(str(i) for i in requested)
                )

        originals: dict[str, Any] = {}

        def stage(frame_no: int | None, out_path: object):
            if frame_no is None or frame_no not in reuse:
                return None
            source = reuse[frame_no]
            dest = Path(str(out_path))
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            _copy_sidecars(source, dest)
            print(f"    frame {frame_no}: reused approved visual state")
            return str(dest)

        if reuse or rejected_digests:
            if hasattr(sb, "find_photo"):
                originals["find_photo"] = sb.find_photo

                def reuse_find_photo(
                    spec, out_path, seen=(), context="", allow_neutral=True, bank=None
                ):
                    frame_no = _frame_no_from_path(out_path)
                    staged = stage(frame_no, out_path)
                    if staged:
                        return staged
                    repair_seen = seen
                    if frame_no in rejected_digests:
                        repair_seen = _seen_with_rejected(
                            sb, seen, rejected_digests[frame_no]
                        )
                    return originals["find_photo"](
                        spec, out_path, repair_seen, context,
                        allow_neutral=allow_neutral, bank=bank,
                    )

                sb.find_photo = reuse_find_photo

            if hasattr(sb, "_person_frame_photo"):
                originals["_person_frame_photo"] = sb._person_frame_photo

                def reuse_person(frame, slot, used):
                    frame_no = _frame_no_from_path(slot)
                    staged = stage(frame_no, slot)
                    if staged:
                        return staged
                    repair_used = used
                    if frame_no in rejected_digests:
                        repair_used = _seen_with_rejected(
                            sb, used, rejected_digests[frame_no]
                        )
                    return originals["_person_frame_photo"](
                        frame, slot, repair_used
                    )

                sb._person_frame_photo = reuse_person

            if hasattr(sb, "_curated_logo"):
                originals["_curated_logo"] = sb._curated_logo

                def reuse_logo(frame_no, total, inner_brief, frame, allow_hero=False):
                    slot = sb.OUT_DIR / f"story-frame-{frame_no}.jpg"
                    staged = stage(frame_no, slot)
                    return staged or originals["_curated_logo"](
                        frame_no, total, inner_brief, frame, allow_hero=allow_hero
                    )

                sb._curated_logo = reuse_logo

            if hasattr(sb, "_curated_flag"):
                originals["_curated_flag"] = sb._curated_flag

                def reuse_flag(frame_no, frame):
                    slot = sb.OUT_DIR / f"story-frame-{frame_no}.jpg"
                    staged = stage(frame_no, slot)
                    return staged or originals["_curated_flag"](frame_no, frame)

                sb._curated_flag = reuse_flag

            if hasattr(sb, "_generated_frame"):
                originals["_generated_frame"] = sb._generated_frame

                def reuse_generated(frame, slot):
                    staged = stage(_frame_no_from_path(slot), slot)
                    return staged or originals["_generated_frame"](frame, slot)

                sb._generated_frame = reuse_generated

        try:
            photos = original_find_all(brief)
        finally:
            for name, original in originals.items():
                setattr(sb, name, original)

        if photos is not None:
            photos = _reject_unchanged_requested_photos(
                sb, photos, rejected_digests
            )
            capture_visual_state(story, revision, brief, photos)
        return photos

    sb.find_all_photos = visual_state_find_all
    setattr(sb, _CONFIGURED_ATTR, True)
    return sb
