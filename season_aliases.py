#!/usr/bin/env python3
"""Resolve a manual Topic Brief season entry to a canonical seasons.txt name."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_AR_DIACRITICS = re.compile(r"[\u064b-\u065f\u0670]")
_NON_WORD = re.compile(r"[^0-9a-z\u0600-\u06ff]+", re.IGNORECASE)

# Cross-language aliases that cannot be inferred from the Arabic canonical name.
# Keep these as search tokens rather than canonical names so seasons.txt remains
# the source of truth for the actual season title.
_CROSS_LANGUAGE_ALIASES = {
    "leap": "ليب",
}


def _normalize(text: str) -> str:
    text = _AR_DIACRITICS.sub("", str(text or "").strip().lower())
    text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"}))
    return " ".join(_NON_WORD.sub(" ", text).split())


def _canonical_names(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    names = []
    for raw in lines:
        line = raw.strip()
        if not line.startswith("##"):
            continue
        name = line[2:].split("|", 1)[0].strip()
        if name:
            names.append(name)
    return names


def resolve_season(value: str, path: Path = Path("seasons.txt")) -> str:
    """Return the matching canonical season name, or the original value."""
    original = str(value or "").strip()
    if not original:
        return ""

    want = _normalize(original)
    names = _canonical_names(path)

    # Existing Arabic/partial-name behavior, but normalized for punctuation and
    # common Arabic letter variants.
    for name in names:
        canonical = _normalize(name)
        if want and (want in canonical or canonical in want):
            return name

    # Translate known cross-language event aliases to a token that can be
    # matched against the canonical Arabic season heading.
    alias_token = None
    for alias, token in _CROSS_LANGUAGE_ALIASES.items():
        if alias in want.split() or want.startswith(alias + " "):
            alias_token = _normalize(token)
            break
    if alias_token:
        for name in names:
            if alias_token in _normalize(name):
                return name

    # Preserve current behavior for genuinely unknown entries: topic_bot will
    # log the available seasons and fall back rather than silently changing it.
    return original


def main(argv: list[str]) -> int:
    value = argv[1] if len(argv) > 1 else ""
    path = Path(argv[2]) if len(argv) > 2 else Path("seasons.txt")
    print(resolve_season(value, path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
