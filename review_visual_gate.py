#!/usr/bin/env python3
"""Fail closed when a rendered story deck is visually under-covered.

The source-level Story runtime requires four reviewed photos plus a verified
logo, but old decks in cards/ can pre-date that gate. This module checks the
actual rendered PNGs before they are sent for review so a stale deck whose
photo zone is mostly typography cannot masquerade as visually ready.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image


# The story template reserves roughly this upper-middle region for the visual.
# Normalized coordinates keep the check stable across 1080x1920 source cards
# and resized screenshots. On the reported Bogle deck the real portrait is
# ~7 bits of entropy while the number/text treatments are ~0.9-1.35 bits.
VISUAL_BOX = (0.08, 0.22, 0.92, 0.55)
PHOTO_ENTROPY_MIN = 4.0


def _entropy(gray: Image.Image) -> float:
    histogram = gray.histogram()
    total = sum(histogram)
    if total <= 0:
        return 0.0
    result = 0.0
    for count in histogram:
        if not count:
            continue
        p = count / total
        result -= p * math.log2(p)
    return result


def photographic_entropy(path) -> float:
    """Return grayscale entropy for the rendered card's visual zone."""
    image = Image.open(path).convert("L")
    width, height = image.size
    left, top, right, bottom = VISUAL_BOX
    crop = image.crop((
        int(width * left),
        int(height * top),
        int(width * right),
        int(height * bottom),
    ))
    return _entropy(crop)


def is_photographic_frame(path) -> bool:
    try:
        return photographic_entropy(path) >= PHOTO_ENTROPY_MIN
    except Exception as exc:
        print(f"    visual gate: {Path(path).name} unreadable ({exc})")
        return False


def require_photo_coverage(frames, minimum=4) -> int:
    """Require at least ``minimum`` rendered frames with a photographic zone.

    This is deliberately independent of metadata/sidecars. It protects review
    and publication from stale cards already baked before the current runtime
    relevance gate existed.
    """
    paths = list(frames or [])
    scores = []
    for index, path in enumerate(paths, start=1):
        try:
            score = photographic_entropy(path)
        except Exception as exc:
            score = 0.0
            print(f"    visual gate frame {index}: unreadable ({exc})")
        photo = score >= PHOTO_ENTROPY_MIN
        scores.append((score, photo))
        print(
            f"    visual gate frame {index}/{len(paths)}: "
            f"entropy={score:.2f} -> {'PHOTO' if photo else 'NON-PHOTO'}"
        )

    count = sum(1 for _, photo in scores if photo)
    if count < int(minimum):
        raise SystemExit(
            f"review blocked: only {count}/{len(paths)} photographic frames; "
            f"minimum is {minimum}. This rendered deck is stale or visually "
            "incomplete and will not be sent to Telegram or Snapchat."
        )
    print(f"    visual gate PASS: {count}/{len(paths)} photographic frames")
    return count
