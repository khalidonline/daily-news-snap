#!/usr/bin/env python3
"""Shared relevance policy for Story Bot runtime and audits.

For a personal Snapchat story, the useful question is simple: do we have enough
reviewed, relevant visuals to tell the story? A logo is optional, and a curated
historical document/currency scan is a valid visual when it was selected from
the reviewed local library for that story.
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
    """Return the story-specific review verdict, or ``""`` when unreviewed."""
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
    """Whether this local visual may count and be served for ``story``.

    DIRECT and STRONG_CONTEXT count. Explicit weak/wrong verdicts do not.
    Unreviewed materialized ``rt-*`` files fail closed; manually curated files
    remain trusted unless explicitly vetoed.
    """
    name = Path(filename).name
    verdict = verdict_for(name, story, ledger_path)
    if verdict in COUNTABLE:
        return True
    if verdict in REJECTED:
        return False
    return not name.startswith("rt-")


def _selected_local_source(selected_path: str | Path) -> str:
    """Return the source filename recorded by fetch_local_photo, if any."""
    marker = Path(str(selected_path) + ".exempt")
    try:
        value = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not value.startswith("local:"):
        return ""
    return Path(value.split(":", 1)[1].strip()).name


def trusted_selected_local_visual(
    selected_path: str | Path,
    story: str,
    ledger_path: str | Path = DEFAULT_LEDGER,
) -> bool:
    """Trust a keyword-selected, reviewed local visual for a Story frame.

    The local selector has already matched the frame's image keywords. If the
    source is curated/countable for this story, do not make a second generic
    "is this a photograph?" model veto it merely because it is a banknote,
    document, receipt, advertisement or archive scan. Explicit weak/wrong
    verdicts still fail closed.
    """
    source = _selected_local_source(selected_path)
    if not source:
        return False
    return asset_countable(source, story, ledger_path)


def runtime_status(photo_count: int, logo_count: int = 0) -> str:
    """Six-card personal Story gate: five reviewed visuals; logo optional."""
    need_visuals = max(0, 5 - int(photo_count))
    if need_visuals == 0:
        return "PASS"
    return f"NEEDS {need_visuals} MORE VISUAL{'S' if need_visuals != 1 else ''}"


def runtime_pass(photo_count: int, logo_count: int = 0) -> bool:
    return runtime_status(photo_count, logo_count) == "PASS"
