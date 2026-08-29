"""Install the shared atmospheric photo-quality rule on news_bot.

All photo-driven bots reuse news_bot's fetchers. Installing once here makes
both downloaded candidates and curated local-library candidates reject strong
dust/sand haze while preserving the existing source/relevance behavior.
"""

from __future__ import annotations

from pathlib import Path
import re

import photo_quality


_INSTALLED = "_global_photo_quality_installed"
_HISTORICAL_TERMS = (
    "historical", "archive", "archival", "old ", "vintage",
    "تاريخ", "أرشيف", "قديم", "القديمة", "القديم",
)


def _index_row(source: str, index_path):
    try:
        lines = Path(index_path).read_text(encoding="utf-8").splitlines()
    except (OSError, TypeError):
        return ""
    source = Path(str(source or "")).name
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if Path(line.split("|", 1)[0].strip()).name == source:
            return line
    return ""


def is_historical_archive_source(source: str, index_path) -> bool:
    """Preserve intentionally warm/sepia archival material.

    Atmospheric orange cast is an editorial defect on contemporary city
    photography, but it can be the medium itself on a historical archive.
    Reviewed catalogue metadata is authoritative for that distinction.
    """
    row = _index_row(source, index_path)
    text = f"{source} {row}".casefold()
    if any(term.casefold() in text for term in _HISTORICAL_TERMS):
        return True
    years = [int(y) for y in re.findall(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)", text)]
    return bool(years and min(years) < 2000)


def reviewed_local_is_acceptable(source: str, index_path, images_dir=None,
                                 candidate_path=None) -> bool:
    """Apply modern atmosphere quality while exempting reviewed archives."""
    if is_historical_archive_source(source, index_path):
        return True

    path = Path(candidate_path) if candidate_path else None
    if path is None or not path.exists():
        if images_dir is None:
            try:
                import news_bot as nb
                images_dir = nb.IMAGES_DIR
            except Exception:
                images_dir = None
        if images_dir is not None:
            path = Path(images_dir) / Path(str(source)).name
    if path is None or not path.exists():
        # Selection/fetching will handle a missing file; quality should not
        # invent a rejection without pixels.
        return True
    return not photo_quality.has_poor_atmospheric_visibility(path)


def install(nb):
    if getattr(nb, _INSTALLED, False):
        return nb

    original_graphic = nb.looks_like_a_graphic
    original_local = nb.fetch_local_photo

    def quality_graphic(path):
        if original_graphic(path):
            return True
        if photo_quality.has_poor_atmospheric_visibility(path):
            print("  ! poor atmospheric visibility (dust/sand haze) — rejecting")
            return True
        return False

    def quality_local(queries_ar, queries_en, out_path,
                      respect_cooldown=True, exclude=()):
        excluded = list(exclude or ())
        while True:
            photo, credit = original_local(
                queries_ar, queries_en, out_path,
                respect_cooldown=respect_cooldown,
                exclude=excluded,
            )
            if not photo:
                return None, None

            source = ""
            marker = Path(str(out_path) + ".exempt")
            try:
                value = marker.read_text(encoding="utf-8").strip()
                if value.startswith("local:"):
                    source = Path(value.split(":", 1)[1]).name
            except OSError:
                pass

            if source and reviewed_local_is_acceptable(
                source, nb.IMAGES_INDEX, nb.IMAGES_DIR, candidate_path=photo
            ):
                return photo, credit
            if not source and not photo_quality.has_poor_atmospheric_visibility(photo):
                return photo, credit

            marker.unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)
            if not source or source in excluded:
                print("    local library: dusty/hazy candidate rejected")
                return None, None
            excluded.append(source)
            print(f"    local library: {source} rejected — poor atmospheric visibility")

    nb.looks_like_a_graphic = quality_graphic
    nb.fetch_local_photo = quality_local
    setattr(nb, _INSTALLED, True)
    return nb
