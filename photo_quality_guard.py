"""Install the shared atmospheric photo-quality rule on news_bot.

All photo-driven bots reuse news_bot's fetchers. Installing once here makes
both downloaded candidates and curated local-library candidates reject strong
dust/sand haze while preserving the existing source/relevance behavior.
"""

from __future__ import annotations

from pathlib import Path

import photo_quality


_INSTALLED = "_global_photo_quality_installed"


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
            if not photo_quality.has_poor_atmospheric_visibility(photo):
                return photo, credit

            source = ""
            marker = Path(str(out_path) + ".exempt")
            try:
                value = marker.read_text(encoding="utf-8").strip()
                if value.startswith("local:"):
                    source = Path(value.split(":", 1)[1]).name
            except OSError:
                pass
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
