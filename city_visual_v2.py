"""Run-93 fix: deterministic visual selection for city stories.

This module replaces only the city selection integration.  It reuses the
reviewed metadata/prompt helpers from ``city_visual_fallback`` but takes full
control before generic Story Bot can classify one supporting entity as a
company and turn the whole city deck into a logo-led story.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Iterable

import city_visual_fallback as legacy
import story_focus


CITY_PROMPT = legacy.CITY_PROMPT
CITY_FALLBACK_MARKER = "[[CITY_FALLBACK_SCENE_ONLY]]\n"
_CONFIGURED_ATTR = "_city_visual_v2_configured"

# Re-export the stable helpers already covered by the earlier city tests.
reviewed_city_exact_match = legacy.reviewed_city_exact_match
exact_city_keywords = legacy.exact_city_keywords
city_fallback_queries = legacy.city_fallback_queries
city_candidate_metadata_ok = legacy.city_candidate_metadata_ok


def is_city_fallback_context(context: str) -> bool:
    return str(context or "").startswith(CITY_FALLBACK_MARKER)


def city_fallback_visual_context(story: str, aliases: Iterable[str]) -> str:
    return CITY_FALLBACK_MARKER + legacy.city_fallback_visual_context(story, aliases)


def _is_city_deck(brief: dict) -> bool:
    frames = list((brief or {}).get("frames") or [])
    return any(str(frame.get("subject_kind", "")).strip() == "place_city"
               for frame in frames)


def normalize_city_deck_for_visuals(brief: dict) -> dict:
    """A city remains the visual subject even if one frame mentions a company."""
    out = deepcopy(brief) if isinstance(brief, dict) else brief
    if not isinstance(out, dict) or not _is_city_deck(out):
        return out
    for frame in out.get("frames") or []:
        frame["subject_kind"] = "place_city"
    return out


def reviewed_city_exact_rows(frame: dict, index_path,
                             aliases: Iterable[str] = ()) -> list[dict]:
    """Return reviewed rows that match the frame beat, independent of fuzzy score."""
    rows = []
    for row in legacy._read_visual_index(index_path):
        if reviewed_city_exact_match(
            Path(row["filename"]), frame, index_path, aliases=aliases
        ):
            rows.append(row)
    return rows


_GENERIC_SCENE_TERMS = (
    "skyline", "أفق", "street", "شارع", "road", "طريق",
    "landmark", "معلم", "airport", "مطار", "departures", "المغادرون",
    "stadium", "ملعب", "park", "حديقة", "boulevard", "بوليفارد",
    "district", "حي", "tower", "برج", "downtown", "public space",
    "مساحة عامة",
)


def reviewed_city_fallback_rows(index_path,
                                aliases: Iterable[str] = ()) -> list[dict]:
    """Prefer obvious city scenes; a bare city tag is not enough for fallback."""
    out = []
    for row in legacy._read_visual_index(index_path):
        metadata = " ".join(
            [row.get("filename", ""), row.get("tags", ""), row.get("credit", "")]
        )
        if not story_focus.catalog_tags_match_aliases([metadata], aliases):
            continue
        if not city_candidate_metadata_ok(metadata, aliases):
            continue
        text = metadata.casefold()
        if not any(term.casefold() in text for term in _GENERIC_SCENE_TERMS):
            continue
        out.append(row)
    return out


def _row_terms(row: dict) -> list[str]:
    tags = [part.strip() for part in str(row.get("tags", "")).split(",")
            if part.strip()]
    return list(dict.fromkeys(tags))[:8]


def configure(story_bot_module):
    """Install a city-only selector after ``story_focus.configure``."""
    sb = story_bot_module
    if getattr(sb, _CONFIGURED_ATTR, False):
        return sb

    base_find_photo = sb.find_photo
    base_find_all_photos = sb.find_all_photos
    base_research = sb.research
    active = {
        "story": "",
        "frames": [],
        "aliases": [],
        "attempted": set(),
        "photo_count": 0,
    }

    def index_path():
        try:
            import news_bot as nb
            return nb.IMAGES_INDEX
        except Exception:
            return None

    def fresh(photo, seen):
        if not photo:
            return False
        try:
            digest = sb._photo_digest(photo)
            return not any(sb.same_picture(digest, prior) for prior in seen)
        except Exception:
            return True

    def reserved_for_other_frames(frame):
        path = index_path()
        if not path:
            return set()
        reserved = set()
        for other in active["frames"]:
            if other is frame:
                continue
            for row in reviewed_city_exact_rows(other, path, active["aliases"]):
                reserved.add(Path(row["filename"]).name)
        return reserved

    def fetch_reviewed_row(row, out_path, seen, tried):
        source = Path(row["filename"]).name
        terms = _row_terms(row)
        if not terms:
            return None
        candidate, _credit = sb.fetch_local_photo(
            [], terms, out_path,
            exclude=list(dict.fromkeys(list(tried) + [
                Path(r["filename"]).name
                for r in legacy._read_visual_index(index_path())
                if Path(r["filename"]).name != source
            ])),
            respect_cooldown=False,
        )
        if not candidate or legacy._source_name(candidate) != source:
            return None
        if not fresh(candidate, seen):
            return None
        return candidate

    def exact_local(frame, out_path, seen, lib_exclude=()):
        path = index_path()
        if not path:
            return None
        excluded = {Path(str(v)).name for v in (lib_exclude or [])}
        for row in reviewed_city_exact_rows(frame, path, active["aliases"]):
            source = Path(row["filename"]).name
            if source in excluded:
                continue
            candidate = fetch_reviewed_row(row, out_path, seen, excluded)
            if candidate:
                print(
                    f"      city exact local v2: {source} "
                    "(reviewed row selected directly; cooldown ignored)"
                )
                return candidate
        return None

    def generic_local(frame, out_path, seen, lib_exclude=()):
        path = index_path()
        if not path:
            return None
        excluded = {Path(str(v)).name for v in (lib_exclude or [])}
        excluded |= reserved_for_other_frames(frame)
        for row in reviewed_city_fallback_rows(path, active["aliases"]):
            source = Path(row["filename"]).name
            if source in excluded:
                continue
            candidate = fetch_reviewed_row(row, out_path, seen, excluded)
            if candidate:
                print(
                    f"      city fallback local v2: {source} "
                    "(reviewed city scene; cooldown ignored)"
                )
                return candidate
        return None

    def web_fallback(out_path, seen):
        if active["photo_count"] >= 4:
            return None
        queries = city_fallback_queries(active["aliases"])
        if not queries:
            return None
        local_names = [
            Path(row["filename"]).name
            for row in legacy._read_visual_index(index_path())
        ]
        spec = {
            "image_keywords": queries[:4],
            "image_keywords_ar": queries[4:6],
            "lib_exclude": local_names,
        }
        # The frame-specific story_focus gate is intentionally bypassed only
        # for this explicit CITY_FALLBACK marker.  Raw vision still checks that
        # the image is genuinely of the declared city and not another city.
        try:
            import news_bot as nb
            strict_gate = sb.photo_shows
            sb.photo_shows = nb.photo_shows
            try:
                return base_find_photo(
                    spec, out_path, seen,
                    city_fallback_visual_context(active["story"], active["aliases"]),
                    allow_neutral=True,
                )
            finally:
                sb.photo_shows = strict_gate
        except Exception:
            return None

    def focused_find_photo(spec, out_path, seen=(), context="",
                           allow_neutral=True, bank=None):
        frame = legacy._frame_from_context(active["frames"], context)
        if not active["story"] or frame is None:
            return base_find_photo(
                spec, out_path, seen, context,
                allow_neutral=allow_neutral, bank=bank,
            )

        key = id(frame)
        if key in active["attempted"]:
            return None
        active["attempted"].add(key)

        excludes = (spec or {}).get("lib_exclude") or []
        photo = exact_local(frame, out_path, seen, excludes)
        if photo is None:
            photo = generic_local(frame, out_path, seen, excludes)
        if photo is None:
            photo = web_fallback(out_path, seen)
        if photo is not None:
            active["photo_count"] += 1
        return photo

    def focused_research(story):
        previous = sb.SYSTEM_PROMPT
        sb.SYSTEM_PROMPT = previous + CITY_PROMPT
        try:
            return base_research(story)
        finally:
            sb.SYSTEM_PROMPT = previous

    def focused_find_all_photos(brief):
        if not _is_city_deck(brief):
            return base_find_all_photos(brief)

        previous = dict(active)
        frames = list((brief or {}).get("frames") or [])
        old_kinds = [frame.get("subject_kind") for frame in frames]
        active["story"] = str((brief or {}).get("story", "") or "").strip()
        active["frames"] = frames
        active["aliases"] = legacy._unique(sb.story_aliases(active["story"]))
        active["attempted"] = set()
        active["photo_count"] = 0

        # Critical #93 fix: one supporting company/product frame must never
        # make Story Bot classify the entire Riyadh deck as a company story.
        for frame in frames:
            frame["subject_kind"] = "place_city"
        try:
            return base_find_all_photos(brief)
        finally:
            for frame, old_kind in zip(frames, old_kinds):
                frame["subject_kind"] = old_kind
            active.clear()
            active.update(previous)

    sb.find_photo = focused_find_photo
    sb.research = focused_research
    sb.find_all_photos = focused_find_all_photos
    setattr(sb, _CONFIGURED_ATTR, True)
    return sb
