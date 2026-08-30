"""Narrow exact-match scoring for the city visual selector.

This module keeps the v2 two-pass runtime but replaces its exact-row scorer.
Bare city/generic words cannot make a reviewed asset an exact match; a row
needs a visible scene/project clue, an exact requested year, or the explicit
old-Riyadh historical anchor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable
import re
import shutil
import urllib.parse
import urllib.request

from PIL import Image

import city_visual_v2 as v2
import city_visual_fallback as legacy
import photo_quality
import photo_quality_guard
import story_focus


CITY_PROMPT = v2.CITY_PROMPT
CITY_FALLBACK_MARKER = v2.CITY_FALLBACK_MARKER
exact_city_keywords = v2.exact_city_keywords
city_fallback_queries = v2.city_fallback_queries
city_candidate_metadata_ok = v2.city_candidate_metadata_ok
is_city_fallback_context = v2.is_city_fallback_context
city_fallback_visual_context = v2.city_fallback_visual_context
city_frame_allows_generic_fallback = v2.city_frame_allows_generic_fallback
targeted_city_keywords = v2.targeted_city_keywords
city_target_metadata_ok = v2.city_target_metadata_ok
city_spa_metadata_ok = v2.city_spa_metadata_ok
normalize_city_deck_for_visuals = v2.normalize_city_deck_for_visuals
reviewed_city_fallback_rows = v2.reviewed_city_fallback_rows
apply_riyadh_closing = v2.apply_riyadh_closing

_KNOWN_HISTORICAL_ERA_MISMATCHES = {"old-riyadh-souq.jpg"}

_PINNED_RIYADH_MURABBA = {
    "filename": "Murabba Palace.jpg",
    "commons_file": "Murabba Palace.jpg",
    "credit": "saudipics / Wikimedia Commons / CC BY-SA 4.0",
}
_PINNED_RIYADH_METRO = {
    "filename": "KAFD Station - Riyadh Metro.jpg",
    "commons_file": "KAFD Station - Riyadh Metro.jpg",
    "credit": "Ali Lajami / Wikimedia Commons / CC BY 2.0",
}
_PINNED_RIYADH_METRO_ALTERNATE = {
    "filename": "KAFD Metro Station Riyadh Saudi Arabia 019.jpg",
    "commons_file": "KAFD Metro Station Riyadh Saudi Arabia 019.jpg",
    "credit": "Kolaiel / Wikimedia Commons / CC0 1.0",
}
_PINNED_RIYADH_GROWTH = {
    "filename": "Riyadh aerial helicam 2013.jpg",
    "commons_file": "Riyadh aerial helicam 2013.jpg",
    "credit": "Ville Hyvönen / Wikimedia Commons / CC BY-SA 2.0",
}
_PINNED_RIYADH_SKYLINE = {
    "filename": "Riyadh Skyline.jpg",
    "commons_file": "Riyadh Skyline.jpg",
    "credit": "B.alotaby / Wikimedia Commons / CC BY-SA 4.0",
}


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+|[ء-ي]+", str(text or "").casefold()))


def _years(text: str) -> set[str]:
    return set(
        re.findall(
            r"(?<![0-9a-z])((?:18|19|20)\d{2})(?![0-9a-z])",
            str(text or "").casefold(),
        )
    )


def _tokens(text: str) -> set[str]:
    return set(_norm(text).split())


def _generic_tokens(aliases: Iterable[str]) -> set[str]:
    generic = {
        "city", "مدينة", "photo", "صورة", "riyadh", "الرياض",
        "construction", "building", "buildings", "بناء", "البناء", "عمران",
        "old", "قديم", "القديمة",
    }
    for alias in aliases or ():
        generic |= _tokens(alias)
    return generic


def city_frame_deserves_targeted_search_after_minimum(
    frame: dict, aliases: Iterable[str] = ()
) -> bool:
    targets = list((frame or {}).get("image_keywords") or [])
    targets += list((frame or {}).get("image_keywords_ar") or [])
    text = _norm(" ".join(str(term) for term in targets if term))
    if not text:
        return False
    phrases = (
        "metro", "مترو",
        "skyline", "أفق",
        "kafd", "king abdullah financial district",
        "مركز الملك عبدالله المالي",
    )
    return any(_norm(phrase) in text for phrase in phrases)


def pinned_riyadh_visuals(frame: dict) -> list[dict]:
    """Return ordered deterministic Commons candidates for key Riyadh beats."""
    if not isinstance(frame, dict):
        return []
    targets = list(frame.get("image_keywords") or [])
    targets += list(frame.get("image_keywords_ar") or [])
    target_text = _norm(" ".join(str(term) for term in targets if term))
    body = str(frame.get("text", "") or "")
    heading = str(frame.get("heading", "") or "")
    raw = " ".join([target_text, body, heading])
    whole = _norm(raw)
    is_riyadh = "riyadh" in whole or "الرياض" in raw

    if is_riyadh and (
        "قصر المربع" in body
        or "قصر المربع" in heading
        or "murabba palace" in whole
        or "al murabba" in whole
    ):
        return [dict(_PINNED_RIYADH_MURABBA)]

    if is_riyadh and ("metro" in whole or "مترو" in raw):
        return [
            dict(_PINNED_RIYADH_METRO),
            dict(_PINNED_RIYADH_METRO_ALTERNATE),
        ]

    approved_close = (
        "225" in body and "نقاط البيع" in body
    ) or "من بلدة مسو رة إلى مدينة بهذا الحجم" in _norm(heading)
    if approved_close and is_riyadh:
        return [
            dict(_PINNED_RIYADH_SKYLINE),
            dict(_PINNED_RIYADH_GROWTH),
        ]

    growth_markers = (
        "تعداد السعودية",
        "سبعة ملايين",
        "7 ملايين",
        "هذا الحجم",
        "حجم لم تعرفه",
        "عدد سكانها",
    )
    if is_riyadh and any(marker in body or marker in heading for marker in growth_markers):
        return [dict(_PINNED_RIYADH_GROWTH)]
    return []


def pinned_riyadh_visual(frame: dict):
    """Backward-compatible first-choice Riyadh pin."""
    candidates = pinned_riyadh_visuals(frame)
    return candidates[0] if candidates else None


def _meaningful_overlap(targets: list[str], metadata: str,
                        aliases: Iterable[str]) -> int:
    generic = _generic_tokens(aliases)
    meta = _tokens(metadata) - generic
    best = 0
    for target in targets:
        target_tokens = _tokens(target) - generic
        shared = target_tokens & meta
        if len(shared) >= 2:
            best = max(best, 40 + 5 * min(3, len(shared)))
        elif shared and max(len(token) for token in shared) >= 6:
            best = max(best, 24)
    return best


def _row_exact_score(row: dict, frame: dict, aliases: Iterable[str]) -> int:
    source = Path(row.get("filename", "")).name
    tags = str(row.get("tags", "") or "")
    credit = str(row.get("credit", "") or "")
    metadata = " ".join([source, tags, credit])

    if not story_focus.catalog_tags_match_aliases([metadata], aliases):
        return -1

    targets = exact_city_keywords(frame, aliases)
    if not targets:
        return -1
    target_text = " ".join(targets)
    target_cf = _norm(target_text)
    metadata_cf = _norm(metadata)

    target_years = _years(target_text)
    historical_request = bool(target_years) or "old riyadh" in target_cf or "الرياض القديمة" in target_text
    if source in _KNOWN_HISTORICAL_ERA_MISMATCHES and historical_request:
        return -1

    old_anchor = (
        ("old riyadh" in target_cf and "old riyadh" in metadata_cf)
        or ("الرياض القديمة" in target_text and "الرياض القديمة" in metadata)
    )

    meta_years = _years(metadata)
    overlap = _meaningful_overlap(targets, metadata, aliases)

    if target_years and meta_years and not (target_years & meta_years):
        if overlap < 40:
            return -1

    score = overlap
    if old_anchor:
        score += 100
    if target_years & meta_years:
        score += 120

    if not target_years and (
        "1970s" in target_cf or "السبعينات" in target_text
    ) and any(year.startswith("197") for year in meta_years):
        score += 80

    return score if score > 0 else -1


def reviewed_city_exact_match(photo, frame: dict, index_path,
                              aliases: Iterable[str] = ()) -> bool:
    source = legacy._source_name(photo)
    row = next(
        (item for item in legacy._read_visual_index(index_path)
         if Path(item.get("filename", "")).name == source),
        None,
    )
    return bool(row and _row_exact_score(row, frame, aliases) > 0)


def reviewed_city_exact_rows(frame: dict, index_path,
                             aliases: Iterable[str] = ()) -> list[dict]:
    scored = []
    for order, row in enumerate(legacy._read_visual_index(index_path)):
        score = _row_exact_score(row, frame, aliases)
        if score > 0:
            scored.append((score, -order, row))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row for _score, _order, row in scored]


def plan_reviewed_exact_assignments(frames: Iterable[dict], index_path,
                                    aliases: Iterable[str] = ()) -> dict[int, dict]:
    assignments: dict[int, dict] = {}
    used: set[str] = set()
    for idx, frame in enumerate(frames or []):
        for row in reviewed_city_exact_rows(frame, index_path, aliases):
            source = Path(row.get("filename", "")).name
            if source in used:
                continue
            if not photo_quality_guard.reviewed_local_is_acceptable(
                source, index_path
            ):
                print(
                    f"      city exact plan: {source} excluded before counting "
                    "— poor atmospheric visibility"
                )
                continue
            assignments[idx] = row
            used.add(source)
            break
    return assignments


def _download_pinned_visual(asset: dict, out_path, sb, seen=()):
    if not asset:
        return None
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".pinned.tmp")
    tmp.unlink(missing_ok=True)
    filename = str(asset["commons_file"])
    url = (
        "https://commons.wikimedia.org/wiki/Special:Redirect/file/"
        + urllib.parse.quote(filename, safe="")
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ExecutiveSummaryStoryBot/1.0 (visual editorial review)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response, tmp.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        with Image.open(tmp) as image:
            image.verify()
        if photo_quality.has_poor_atmospheric_visibility(tmp):
            print(f"      pinned Riyadh visual rejected by quality: {asset['filename']}")
            tmp.unlink(missing_ok=True)
            return None
        try:
            digest = sb._photo_digest(tmp)
            if any(sb.same_picture(digest, prior) for prior in seen):
                print(f"      pinned Riyadh visual skipped as previously rejected: {asset['filename']}")
                tmp.unlink(missing_ok=True)
                return None
        except Exception:
            pass
        tmp.replace(out)
        print(f"      pinned Riyadh visual: {asset['filename']} — {asset['credit']}")
        return str(out)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        print(f"      pinned Riyadh visual unavailable: {asset['filename']} ({exc})")
        return None


def configure(story_bot_module):
    """Use v2 flow, with deterministic final Riyadh visuals."""
    pre_city_find_photo = story_bot_module.find_photo

    v2.reviewed_city_exact_match = reviewed_city_exact_match
    v2.reviewed_city_exact_rows = reviewed_city_exact_rows
    v2.plan_reviewed_exact_assignments = plan_reviewed_exact_assignments
    sb = v2.configure(story_bot_module)
    city_find_photo = sb.find_photo

    def find_photo_with_high_value_late_exact(
        spec, out_path, seen=(), context="", allow_neutral=True, bank=None
    ):
        frame = spec if isinstance(spec, dict) else {}
        if str(frame.get("subject_kind", "")).strip() == "place_city":
            pinned = pinned_riyadh_visuals(frame)
            if pinned:
                # Fail closed. A pinned Riyadh beat may become text-only if all
                # exact files are unavailable, but it may never drift to another
                # city or an unrelated local photo. Human repair can reject the
                # first pin through ``seen`` and advance to the next exact pin.
                for candidate in pinned:
                    photo = _download_pinned_visual(candidate, out_path, sb, seen)
                    if photo is not None:
                        return photo
                return None

        photo = city_find_photo(
            spec, out_path, seen, context,
            allow_neutral=allow_neutral, bank=bank,
        )
        if photo is not None:
            return photo

        if str(frame.get("subject_kind", "")).strip() != "place_city":
            return None
        aliases = legacy._unique(
            alias for alias in ("Riyadh", "الرياض")
            if alias and alias.casefold() in (
                " ".join(
                    [str(context or "")]
                    + [str(x) for x in frame.get("image_keywords", [])]
                    + [str(x) for x in frame.get("image_keywords_ar", [])]
                ).casefold()
            )
        )
        if not city_frame_deserves_targeted_search_after_minimum(frame, aliases):
            return None

        targets = _norm(" ".join(
            [str(x) for x in frame.get("image_keywords", [])]
            + [str(x) for x in frame.get("image_keywords_ar", [])]
        ))
        if "skyline" in targets or "أفق" in targets:
            return None

        print("      city high-value exact search: continuing after four-photo minimum")
        return pre_city_find_photo(
            frame, out_path, seen, context,
            allow_neutral=False, bank=bank,
        )

    sb.find_photo = find_photo_with_high_value_late_exact
    return sb
