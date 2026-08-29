"""Shared editorial photo-quality checks.

The goal is intentionally narrow: reject the strongly orange/sand-cast,
low-visibility city photographs that make a clear-day story look dusty or
unappealing. Mild warm desert light is allowed, and monochrome archival
photography is explicitly preserved.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def has_poor_atmospheric_visibility(path) -> bool:
    """Return True for a pervasive dust/sand atmospheric cast.

    This is a conservative pixel heuristic, not a weather classifier. It only
    fires when a large majority of the image has the characteristic warm
    red>green>blue channel separation seen in heavy dust/haze. Normal golden
    light can contain warm areas without dominating the full frame, while
    black-and-white archival photos have almost no channel separation.
    """
    try:
        img = Image.open(Path(path)).convert("RGB")
        img.thumbnail((160, 160))
    except Exception:
        return False

    pixels = list(img.getdata())
    if not pixels:
        return False

    total = len(pixels)
    mean_r = sum(p[0] for p in pixels) / total
    mean_g = sum(p[1] for p in pixels) / total
    mean_b = sum(p[2] for p in pixels) / total

    # Monochrome/near-monochrome images are often legitimate archive photos.
    if max(mean_r, mean_g, mean_b) - min(mean_r, mean_g, mean_b) < 16:
        return False

    warm = sum(
        1 for r, g, b in pixels
        if r >= g + 15 and g >= b + 10 and r - b >= 45
    ) / total

    # Strong widespread sand/dust cast. Thresholds are deliberately high so
    # ordinary sunset/golden-hour photography is not rejected merely for
    # containing warm light.
    return (
        warm >= 0.62
        and mean_r - mean_b >= 50
        and mean_g - mean_b >= 18
    )
