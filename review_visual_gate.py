#!/usr/bin/env python3
"""Rendered-story verification and deterministic visual placement."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageOps


# The story template reserves roughly this upper-middle region for the visual.
VISUAL_BOX = (0.08, 0.22, 0.92, 0.55)
PHOTO_ENTROPY_MIN = 4.0
CARD_BG = (238, 232, 227)


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


def _pixel_box(image: Image.Image):
    width, height = image.size
    left, top, right, bottom = VISUAL_BOX
    return (
        int(width * left),
        int(height * top),
        int(width * right),
        int(height * bottom),
    )


def photographic_entropy(path) -> float:
    """Return grayscale entropy for the rendered card's visual zone."""
    image = Image.open(path).convert("L")
    crop = image.crop(_pixel_box(image))
    return _entropy(crop)


def is_photographic_frame(path) -> bool:
    try:
        return photographic_entropy(path) >= PHOTO_ENTROPY_MIN
    except Exception as exc:
        print(f"    visual gate: {Path(path).name} unreadable ({exc})")
        return False


def apply_requested_photos(frames, photo_paths, requested=4) -> int:
    """Make the rendered deck contain exactly ``requested`` photo cards.

    The source photos are already story-approved by ``story_runtime``. The
    first requested card visual zones receive distinct approved photographs.
    Any photographic zone after that is neutralized so the four-photo review
    standard is deterministic before logo/portrait fallback is applied.
    """
    paths = [Path(p) for p in (frames or [])]
    photos = [Path(p) for p in (photo_paths or [])]
    requested = int(requested)
    if requested < 1 or requested > len(paths):
        raise SystemExit(
            f"number of pictures must be between 1 and {len(paths)}"
        )
    if len(photos) < requested:
        raise SystemExit(
            f"story has only {len(photos)} approved distinct photos; "
            f"requested {requested}. Nothing was sent to Telegram."
        )

    for index, card_path in enumerate(paths):
        card = Image.open(card_path).convert("RGB")
        box = _pixel_box(card)
        width = box[2] - box[0]
        height = box[3] - box[1]
        if index < requested:
            source = Image.open(photos[index]).convert("RGB")
            fitted = ImageOps.fit(
                source,
                (width, height),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            card.paste(fitted, (box[0], box[1]))
            print(
                f"    requested picture {index + 1}/{requested}: "
                f"{photos[index].name} -> {card_path.name}"
            )
        elif is_photographic_frame(card_path):
            blank = Image.new("RGB", (width, height), CARD_BG)
            card.paste(blank, (box[0], box[1]))
        card.save(card_path, "PNG")

    return require_photo_coverage(paths, minimum=requested)


def apply_fallback_visuals(frames, visual_paths, start_index=4) -> int:
    """Fill remaining card visual zones with one repeatable approved visual.

    ``visual_paths`` should be ordered by preference. The first approved logo
    is normally supplied; if a story has no logo, callers may supply an
    approved portrait/photo instead. Reusing the same logo or portrait on
    multiple cards is intentional.
    """
    paths = [Path(p) for p in (frames or [])]
    visuals = [Path(p) for p in (visual_paths or []) if Path(p).exists()]
    start_index = int(start_index)
    if not visuals or start_index >= len(paths):
        return 0

    source_path = visuals[0]
    source = Image.open(source_path).convert("RGB")
    filled = 0
    for index in range(max(0, start_index), len(paths)):
        card_path = paths[index]
        card = Image.open(card_path).convert("RGB")
        box = _pixel_box(card)
        width = box[2] - box[0]
        height = box[3] - box[1]

        blank = Image.new("RGB", (width, height), CARD_BG)
        fitted = ImageOps.contain(
            source,
            (int(width * 0.82), int(height * 0.82)),
            method=Image.Resampling.LANCZOS,
        )
        x = (width - fitted.width) // 2
        y = (height - fitted.height) // 2
        blank.paste(fitted, (x, y))
        card.paste(blank, (box[0], box[1]))
        card.save(card_path, "PNG")
        filled += 1
        print(
            f"    fallback visual {index + 1}/{len(paths)}: "
            f"{source_path.name} -> {card_path.name}"
        )
    return filled


def require_photo_coverage(frames, minimum=4) -> int:
    """Require at least ``minimum`` rendered frames with a photographic zone."""
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
            f"minimum is {minimum}. This rendered deck is visually incomplete "
            "and will not be sent to Telegram or Snapchat."
        )
    print(f"    visual gate PASS: {count}/{len(paths)} photographic frames")
    return count
