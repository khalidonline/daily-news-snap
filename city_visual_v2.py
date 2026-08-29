"""Deterministic visual selection for city stories.

The city path deliberately uses a whole-deck two-pass policy:
1. plan distinct reviewed local photos that exactly support visible beats;
2. only if fewer than four exact photos exist, use broad city-scene fallbacks.

This keeps generic Story Bot company/logo behavior out of city stories and
prevents a fallback photo from stealing a slot that a later frame can match
exactly.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Iterable
import re

import city_visual_fallback as legacy
import story_focus


CITY_PROMPT = legacy.CITY_PROMPT
CITY_FALLBACK_MARKER = "[[CITY_FALLBACK_SCENE_ONLY]]\n"
_CONFIGURED_ATTR = "_city_visual_v2_configured"

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


def _years(text: str) -> set[str]:
    return set(re.findall(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)", str(text or "")))


def _norm_phrase(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+|[ء-ي]+", str(text or "").casefold()))


def _specific_phrase_match(targets: list[str], metadata_parts: list[str]) -> int:
    """Score real scene/entity phrase overlap, not bare city/generic words."""
    best = 0
    generic = {
        "riyadh", "الرياض", "city", "مدينة", "construction", "building",
        "بناء", "البناء", "عمران", "old", "قديم", "القديمة", "photo", "صورة",
    }
    for position, target in enumerate(targets):
        t = _norm_phrase(target)
        if not t:
            continue
        t_tokens = set(t.split()) - generic
        for part in metadata_parts:
            m = _norm_phrase(part)
            if not m:
                continue
            m_tokens = set(m.split()) - generic
            shared = t_tokens & m_tokens
            if (t in m or m in t) and len(min(t, m, key=len)) >= 5:
                score = 45 - min(position, 10)
                best = max(best, score)
            elif len(shared) >= 2:
                best = max(best, 26 - min(position, 10))
            elif shared and any(len(tok) >= 6 for tok in shared):
                best = max(best, 14 - min(position, 10))
    return best


def _row_exact_score(row: dict, frame: dict, aliases: Iterable[str]) -> int:
    source = Path(row.get("filename", "")).name
    tags = [p.strip() for p in str(row.get("tags", "")).split(",") if p.strip()]
    credit = str(row.get("credit", "") or "")
    metadata_parts = [source] + tags + ([credit] if credit else [])
    metadata = " ".join(metadata_parts)

    if not story_focus.catalog_tags_match_aliases([metadata], aliases):
        return -1
    if not city_candidate_metadata_ok(metadata, aliases):
        return -1

    targets = exact_city_keywords(frame, aliases)
    if not targets:
        return -1
    target_text = " ".join(targets)
    target_cf = target_text.casefold()
    metadata_cf = metadata.casefold()

    target_years = _years(target_text)
    meta_years = _years(metadata)
    phrase_score = _specific_phrase_match(targets, metadata_parts)

    if target_years and meta_years and not (target_years & meta_years):
        if phrase_score < 25:
            return -1

    score = phrase_score
    if target_years & meta_years:
        score += 100

    if not target_years and (
        "1970s" in target_cf or "السبعينات" in target_cf
    ) and any(year.startswith("197") for year in meta_years):
        score += 70

    if (("old riyadh" in target_cf and "old riyadh" in metadata_cf)
            or ("الرياض القديمة" in target_text and "الرياض القديمة" in metadata)):
        score += 90

    target_clues = legacy._visual_clues(targets, aliases)
    meta_clues = legacy._visual_clues([metadata], aliases)
    score += min(30, 6 * len(target_clues & meta_clues))

    for i, target in enumerate(targets):
        years = _years(target)
        if years and years & meta_years:
            score += max(0, 12 - i)
            break

    return score if score > 0 else -1


def reviewed_city_exact_match(photo, frame: dict, index_path,
                              aliases: Iterable[str] = ()) -> bool:
    source = legacy._source_name(photo)
    row = next(
        (r for r in legacy._read_visual_index(index_path)
         if Path(r.get("filename", "")).name == source),
        None,
    )
    return bool(row and _row_exact_score(row, frame, aliases) > 0)


def reviewed_city_exact_rows(frame: dict, index_path,
                             aliases: Iterable[str] = ()) -> list[dict]:
    """Reviewed candidates sorted by exact visual relevance to one frame."""
    scored = []
    for order, row in enumerate(legacy._read_visual_index(index_path)):
        score = _row_exact_score(row, frame, aliases)
        if score > 0:
            scored.append((score, -order, row))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row for _score, _order, row in scored]


_GENERIC_SCENE_TERMS = (
    "skyline", "أفق", "street", "شارع", "road", "طريق",
    "landmark", "معلم", "airport", "مطار", "departures", "المغادرون",
    "stadium", "ملعب", "park", "حديقة", "boulevard", "بوليفارد",
    "district", "حي", "tower", "برج", "downtown", "public space",
    "مساحة عامة",
)


def city_frame_allows_generic_fallback(frame: dict,
                                       aliases: Iterable[str] = ()) -> bool:
    """Return True only when the frame itself asks for a generic city scene."""
    targets = list((frame or {}).get("image_keywords") or [])
    targets += list((frame or {}).get("image_keywords_ar") or [])
    alias_tokens = set()
    for alias in aliases or ():
        alias_tokens.update(_norm_phrase(alias).split())
    generic_tokens = {"city", "مدينة"}
    for term in _GENERIC_SCENE_TERMS:
        generic_tokens.update(_norm_phrase(term).split())

    saw_generic = False
    for target in targets:
        tokens = set(_norm_phrase(target).split()) - alias_tokens
        if not tokens:
            continue
        if not tokens <= generic_tokens:
            return False
        saw_generic = True
    return saw_generic


def city_spa_metadata_ok(item: dict, aliases: Iterable[str] = ()) -> bool:
    """Reject an SPA result whose own title/tags explicitly name another city."""
    title = str((item or {}).get("title") or "")
    tags = " ".join(
        str(tag.get("name") or "")
        for tag in ((item or {}).get("tags") or [])
        if isinstance(tag, dict)
    )
    metadata = " ".join(part for part in (title, tags) if part).strip()
    return bool(metadata) and city_candidate_metadata_ok(metadata, aliases)


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


def plan_reviewed_exact_assignments(frames: Iterable[dict], index_path,
                                    aliases: Iterable[str] = ()) -> dict[int, dict]:
    """Assign distinct reviewed exact photos across the whole deck first."""
    assignments: dict[int, dict] = {}
    used: set[str] = set()
    for idx, frame in enumerate(frames or []):
        for row in reviewed_city_exact_rows(frame, index_path, aliases):
            source = Path(row.get("filename", "")).name
            if source in used:
                continue
            assignments[idx] = row
            used.add(source)
            break
    return assignments


def apply_riyadh_closing(brief: dict) -> dict:
    """Lock the owner-approved Riyadh closing card and its skyline target."""
    if not isinstance(brief, dict):
        return brief
    story = str(brief.get("story", "") or "")
    if "الرياض" not in story or "عاصمة اقتصادية" not in story:
        return brief
    frames = list(brief.get("frames") or [])
    if not frames:
        return brief
    last = frames[-1]
    last.update({
        "heading": "من بلدة مسوّرة إلى مدينة بهذا الحجم",
        "text": (
            "في 2024 سجّلت الرياض 225 مليار ريال في مبيعات نقاط البيع. "
            "رقم يعكس حجم السوق والحركة الاقتصادية في مدينة كانت قبل نحو "
            "قرن محصورة داخل سور من الطين."
        ),
        "punch": "هذا هو حجم التحول الذي عاشته الرياض.",
        "subject_kind": "place_city",
        "image_keywords": ["Riyadh skyline", "King Abdullah Financial District Riyadh"],
        "image_keywords_ar": ["أفق الرياض", "الرياض"],
    })
    return brief


def _row_terms(row: dict) -> list[str]:
    tags = [part.strip() for part in str(row.get("tags", "")).split(",")
            if part.strip()]
    return list(dict.fromkeys(tags))[:8]


def configure(story_bot_module):
    """Install the whole-deck city selector after ``story_focus.configure``."""
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
        "frame_index": {},
        "exact_assignments": {},
        "fallback_needed": False,
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

    def fetch_reviewed_row(row, out_path, seen, tried=()):
        source = Path(row["filename"]).name
        terms = _row_terms(row)
        if not terms:
            return None
        all_rows = legacy._read_visual_index(index_path())
        excluded = list(dict.fromkeys(
            list(tried or [])
            + [Path(r["filename"]).name for r in all_rows
               if Path(r["filename"]).name != source]
        ))
        candidate, _credit = sb.fetch_local_photo(
            [], terms, out_path,
            exclude=excluded,
            respect_cooldown=False,
        )
        if not candidate or legacy._source_name(candidate) != source:
            return None
        if not fresh(candidate, seen):
            return None
        return candidate

    def generic_local(out_path, seen, lib_exclude=()):
        path = index_path()
        if not path:
            return None
        assigned = {
            Path(row["filename"]).name
            for row in active["exact_assignments"].values()
        }
        excluded = {Path(str(v)).name for v in (lib_exclude or [])} | assigned
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

    def targeted_web(frame, spec, out_path, seen, context, bank=None):
        if active["photo_count"] >= 4:
            return None
        local_names = [
            Path(row["filename"]).name
            for row in legacy._read_visual_index(index_path())
        ]
        targeted = deepcopy(spec or {})
        targeted["image_keywords"] = list(frame.get("image_keywords") or [])
        targeted["image_keywords_ar"] = list(frame.get("image_keywords_ar") or [])
        targeted["lib_exclude"] = list(dict.fromkeys(
            list(targeted.get("lib_exclude") or []) + local_names
        ))
        if not targeted["image_keywords"] and not targeted["image_keywords_ar"]:
            return None

        # SPA's scorer may find the requested city only in tags while the title
        # explicitly names a different city. During a strict city-beat search,
        # veto that metadata contradiction before the item can be downloaded or
        # consume the fourth-photo slot.
        spa_globals = getattr(sb.fetch_spa_photo, "__globals__", {})
        original_spa_score = spa_globals.get("_spa_score")
        if original_spa_score:
            def strict_spa_score(item, terms):
                if not city_spa_metadata_ok(item, active["aliases"]):
                    return -10_000
                return original_spa_score(item, terms)
            spa_globals["_spa_score"] = strict_spa_score
        try:
            return base_find_photo(
                targeted, out_path, seen, context,
                allow_neutral=False, bank=bank,
            )
        except Exception:
            return None
        finally:
            if original_spa_score:
                spa_globals["_spa_score"] = original_spa_score

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

    def frame_index_from_context(context: str):
        frame = legacy._frame_from_context(active["frames"], context)
        if frame is None:
            return None
        return active["frame_index"].get(id(frame))

    def focused_find_photo(spec, out_path, seen=(), context="",
                           allow_neutral=True, bank=None):
        idx = frame_index_from_context(context)
        if not active["story"] or idx is None:
            return base_find_photo(
                spec, out_path, seen, context,
                allow_neutral=allow_neutral, bank=bank,
            )

        if idx in active["attempted"]:
            return None
        active["attempted"].add(idx)

        assigned = active["exact_assignments"].get(idx)
        if assigned is not None:
            photo = fetch_reviewed_row(
                assigned, out_path, seen, (spec or {}).get("lib_exclude") or []
            )
            if photo:
                source = Path(assigned["filename"]).name
                active["photo_count"] += 1
                print(
                    f"      city exact local v2: {source} "
                    "(whole-deck reviewed assignment; cooldown ignored)"
                )
                return photo
            return None

        if not active["fallback_needed"] or active["photo_count"] >= 4:
            return None

        frame = active["frames"][idx]
        if not city_frame_allows_generic_fallback(frame, active["aliases"]):
            photo = targeted_web(frame, spec, out_path, seen, context, bank=bank)
            if photo is not None:
                active["photo_count"] += 1
            return photo

        photo = generic_local(
            out_path, seen, (spec or {}).get("lib_exclude") or []
        )
        if photo is None:
            photo = web_fallback(out_path, seen)
        if photo is not None:
            active["photo_count"] += 1
        return photo

    def focused_research(story):
        previous = sb.SYSTEM_PROMPT
        sb.SYSTEM_PROMPT = previous + CITY_PROMPT
        try:
            brief = base_research(story)
        finally:
            sb.SYSTEM_PROMPT = previous
        return apply_riyadh_closing(brief)

    def focused_find_all_photos(brief):
        if not _is_city_deck(brief):
            return base_find_all_photos(brief)

        apply_riyadh_closing(brief)
        previous = dict(active)
        actual_frames = list((brief or {}).get("frames") or [])
        source_frames = deepcopy(actual_frames)
        aliases = legacy._unique(sb.story_aliases(str(brief.get("story", "") or "")))
        path = index_path()
        assignments = plan_reviewed_exact_assignments(source_frames, path, aliases)
        required = min(4, len(actual_frames))

        active["story"] = str((brief or {}).get("story", "") or "").strip()
        active["frames"] = source_frames
        active["aliases"] = aliases
        active["frame_index"] = {id(frame): i for i, frame in enumerate(source_frames)}
        active["exact_assignments"] = assignments
        active["fallback_needed"] = len(assignments) < required
        active["attempted"] = set()
        active["photo_count"] = 0

        print(
            f"    city visual plan: {len(assignments)} exact reviewed frame(s); "
            + ("generic fallback enabled" if active["fallback_needed"]
               else "four-photo target met — generic fallback disabled")
        )

        old_kinds = [frame.get("subject_kind") for frame in actual_frames]
        old_brief_keywords = brief.get("image_keywords", None)
        old_brief_queries_ar = brief.get("image_queries_ar", None)
        first_two_keywords = [
            actual_frames[i].get("image_keywords", None)
            for i in range(min(2, len(actual_frames)))
        ]
        for frame in actual_frames:
            frame["subject_kind"] = "place_city"
        brief["image_keywords"] = []
        brief["image_queries_ar"] = []
        for i in range(min(2, len(actual_frames))):
            actual_frames[i]["image_keywords"] = []

        try:
            return base_find_all_photos(brief)
        finally:
            for frame, old_kind in zip(actual_frames, old_kinds):
                frame["subject_kind"] = old_kind
            if old_brief_keywords is None:
                brief.pop("image_keywords", None)
            else:
                brief["image_keywords"] = old_brief_keywords
            if old_brief_queries_ar is None:
                brief.pop("image_queries_ar", None)
            else:
                brief["image_queries_ar"] = old_brief_queries_ar
            for i, old in enumerate(first_two_keywords):
                if old is None:
                    actual_frames[i].pop("image_keywords", None)
                else:
                    actual_frames[i]["image_keywords"] = old
            active.clear()
            active.update(previous)

    sb.find_photo = focused_find_photo
    sb.research = focused_research
    sb.find_all_photos = focused_find_all_photos
    setattr(sb, _CONFIGURED_ATTR, True)
    return sb
