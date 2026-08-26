#!/usr/bin/env python3
"""Shared relevance policy for Story Bot runtime and audits.

A local file is necessary but not sufficient. Materialized ``rt-*`` assets
must be explicitly reviewed for the specific story before they count. Existing
manually curated assets remain trusted by default unless the ledger explicitly
rejects them.
"""

from __future__ import annotations

import json
from pathlib import Path

DIRECT = "DIRECT"
STRONG_CONTEXT = "STRONG_CONTEXT"
WEAK_GENERIC = "WEAK_GENERIC"
WRONG_ENTITY = "WRONG_ENTITY"
COUNTABLE = {DIRECT, STRONG_CONTEXT}
REJECTED = {WEAK_GENERIC, WRONG_ENTITY}

DEFAULT_LEDGER = Path("images/relevance.json")


def _load(path: str | Path = DEFAULT_LEDGER) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"assets": {}}
    if not isinstance(data, dict):
        return {"assets": {}}
    assets = data.get("assets")
    if not isinstance(assets, dict):
        data["assets"] = {}
    return data


def verdict_for(filename: str, story: str, ledger_path: str | Path = DEFAULT_LEDGER) -> str:
    """Return the story-specific review verdict, or ``""`` when unreviewed.

    Ledger keys are normally exact story lines. A shorter explicit selector
    such as ``Jack Bogle`` is also allowed and matches only when that selector
    is contained in the story line. This keeps the ledger stable if editorial
    punctuation in a title changes without making verdicts global.
    """
    row = _load(ledger_path).get("assets", {}).get(Path(filename).name, {})
    stories = row.get("stories", {}) if isinstance(row, dict) else {}
    if not isinstance(stories, dict):
        return ""
    story_text = str(story).strip()
    exact = stories.get(story_text)
    if exact:
        return str(exact).strip().upper()
    folded = story_text.casefold()
    matches = [(len(str(selector)), verdict)
               for selector, verdict in stories.items()
               if selector != "*" and str(selector).strip().casefold() in folded]
    if matches:
        return str(max(matches, key=lambda item: item[0])[1]).strip().upper()
    return str(stories.get("*", "")).strip().upper()


def asset_countable(filename: str, story: str,
                    ledger_path: str | Path = DEFAULT_LEDGER) -> bool:
    """Whether this local photo may count and be served for ``story``.

    Policy:
    * ``DIRECT`` and ``STRONG_CONTEXT`` count.
    * ``WEAK_GENERIC`` and ``WRONG_ENTITY`` never count.
    * unreviewed ``rt-*`` files fail closed.
    * legacy/manual non-``rt-*`` files remain trusted unless explicitly vetoed.
    """
    name = Path(filename).name
    verdict = verdict_for(name, story, ledger_path)
    if verdict in COUNTABLE:
        return True
    if verdict in REJECTED:
        return False
    return not name.startswith("rt-")


def runtime_status(photo_count: int, logo_count: int) -> str:
    """Canonical 4 relevant photos + 1 logo classification."""
    need_photos = max(0, 4 - int(photo_count))
    has_logo = int(logo_count) > 0
    if need_photos == 0 and has_logo:
        return "PASS"
    if need_photos and not has_logo:
        return f"NEEDS {need_photos} MORE PHOTO{'S' if need_photos != 1 else ''} + LOGO"
    if need_photos:
        return f"NEEDS {need_photos} MORE PHOTO{'S' if need_photos != 1 else ''}"
    return "NEEDS LOGO"


def runtime_pass(photo_count: int, logo_count: int) -> bool:
    return runtime_status(photo_count, logo_count) == "PASS"
