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

import city_visual_v2 as v2
import city_visual_fallback as legacy
import story_focus


# Public surface retained for the runtime/tests.
CITY_PROMPT = v2.CITY_PROMPT
CITY_FALLBACK_MARKER = v2.CITY_FALLBACK_MARKER
exact_city_keywords = v2.exact_city_keywords
city_fallback_queries = v2.city_fallback_queries
city_candidate_metadata_ok = v2.city_candidate_metadata_ok
is_city_fallback_context = v2.is_city_fallback_context
city_fallback_visual_context = v2.city_fallback_visual_context
normalize_city_deck_for_visuals = v2.normalize_city_deck_for_visuals
reviewed_city_fallback_rows = v2.reviewed_city_fallback_rows
apply_riyadh_closing = v2.apply_riyadh_closing


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+|[ء-ي]+", str(text or "").casefold()))


def _years(text: str) -> set[str]:
    return set(re.findall(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)", str(text or "")))


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


def _meaningful_overlap(targets: list[str], metadata: str,
                        aliases: Iterable[str]) -> int:
    generic = _generic_tokens(aliases)
    meta = _tokens(metadata) - generic
    best = 0
    for target in targets:
        target_tokens = _tokens(target) - generic
        shared = target_tokens & meta
        # Two independent scene/project words are strong: Dammam + railway,
        # سكة + حديد, metro + station, etc.
        if len(shared) >= 2:
            best = max(best, 40 + 5 * min(3, len(shared)))
        # One distinctive long token can still be exact: skyline, departures,
        # boulevard, المصمك, المغادرون...
        elif shared and max(len(token) for token in shared) >= 6:
            best = max(best, 24)
    return best


def _row_exact_score(row: dict, frame: dict, aliases: Iterable[str]) -> int:
    source = Path(row.get("filename", "")).name
    tags = str(row.get("tags", "") or "")
    credit = str(row.get("credit", "") or "")
    metadata = " ".join([source, tags, credit])

    # Exact rows still must belong to the declared story subject. The broad
    # fallback's "other named city" veto is intentionally NOT applied here:
    # a real named project can legitimately connect two cities, such as the
    # Riyadh-Dammam railway. Unrelated Jeddah material cannot become exact
    # because it earns no meaningful scene/project overlap below.
    if not story_focus.catalog_tags_match_aliases([metadata], aliases):
        return -1

    targets = exact_city_keywords(frame, aliases)
    if not targets:
        return -1
    target_text = " ".join(targets)
    target_cf = _norm(target_text)
    metadata_cf = _norm(metadata)

    # Old Riyadh is an explicit historical scene anchor. It is intentionally
    # special-cased because removing the city alias leaves only the generic
    # word "old", which should not match unrelated modern Riyadh assets.
    old_anchor = (
        ("old riyadh" in target_cf and "old riyadh" in metadata_cf)
        or ("الرياض القديمة" in target_text and "الرياض القديمة" in metadata)
    )

    target_years = _years(target_text)
    meta_years = _years(metadata)
    overlap = _meaningful_overlap(targets, metadata, aliases)

    # An explicit wrong year is a hard contradiction unless the row and frame
    # share a named multi-word project (e.g. Riyadh-Dammam railway 1947→1951).
    if target_years and meta_years and not (target_years & meta_years):
        if overlap < 40:
            return -1

    score = overlap
    if old_anchor:
        score += 100
    if target_years & meta_years:
        score += 120

    # Decade wording may match a reviewed year inside that decade.
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
            assignments[idx] = row
            used.add(source)
            break
    return assignments


def configure(story_bot_module):
    """Use v2 runtime flow with this module's corrected exact scorer."""
    v2.reviewed_city_exact_match = reviewed_city_exact_match
    v2.reviewed_city_exact_rows = reviewed_city_exact_rows
    v2.plan_reviewed_exact_assignments = plan_reviewed_exact_assignments
    return v2.configure(story_bot_module)
