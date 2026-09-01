#!/usr/bin/env python3
"""Shared relevance policy for Story Bot runtime and audits.

For a personal Snapchat story, the useful question is simple: do we have enough
reviewed, relevant source material to attempt the story? The rendered six-card
deck is authoritative for publication quality. A logo is optional, and a
curated historical document/currency scan is a valid visual when it was
selected from the reviewed local library for that story.

Authentic visual policy: Story cards must prefer real, documentary source
material. Synthetic/generated assets never count toward runtime readiness. A
reviewed STRONG_CONTEXT asset may be used even when its literal tags do not
repeat the story subject, which allows real products, meals, employees,
operations, locations and other context to broaden a deck safely.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DIRECT = "DIRECT"
STRONG_CONTEXT = "STRONG_CONTEXT"
WEAK_GENERIC = "WEAK_GENERIC"
WRONG_ENTITY = "WRONG_ENTITY"
COUNTABLE = {DIRECT, STRONG_CONTEXT}
REJECTED = {WEAK_GENERIC, WRONG_ENTITY}

DEFAULT_LEDGER = Path("images/relevance.json")

_GENERATED_NAME_PATTERNS = (
    re.compile(r"(^|[-_])ai[-_]generated([-_.]|$)", re.I),
    re.compile(r"(^|[-_])generated([-_.]|$)", re.I),
    re.compile(r"(^|[-_])synthetic([-_.]|$)", re.I),
)
_GENERATED_SOURCE_TYPES = {
    "ai",
    "ai_generated",
    "generated",
    "synthetic",
    "image_generation",
}
_SANITY_REJECT = {"FAIL", "REJECT", "INVALID", "BAD"}


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


def _asset_row(filename: str, ledger_path: str | Path = DEFAULT_LEDGER) -> dict:
    row = _load(ledger_path).get("assets", {}).get(Path(filename).name, {})
    return row if isinstance(row, dict) else {}


def verdict_for(filename: str, story: str, ledger_path: str | Path = DEFAULT_LEDGER) -> str:
    """Return the story-specific review verdict, or ``""`` when unreviewed."""
    row = _asset_row(filename, ledger_path)
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


def generated_asset(filename: str, ledger_path: str | Path = DEFAULT_LEDGER) -> bool:
    """Return True when filename or provenance marks an asset as synthetic."""
    name = Path(filename).name
    if any(pattern.search(name) for pattern in _GENERATED_NAME_PATTERNS):
        return True
    row = _asset_row(name, ledger_path)
    source_type = str(
        row.get("source_type") or row.get("provenance") or row.get("origin") or ""
    ).strip().casefold()
    if source_type in _GENERATED_SOURCE_TYPES:
        return True
    source_url = str(row.get("source_url") or "").strip().casefold()
    return source_url.startswith(("generated:", "ai:", "synthetic:"))


def visual_sanity_ok(filename: str, ledger_path: str | Path = DEFAULT_LEDGER) -> bool:
    """Fail closed when human/automated review explicitly flags a broken visual."""
    row = _asset_row(filename, ledger_path)
    sanity = str(row.get("visual_sanity") or "").strip().upper()
    orientation = str(row.get("orientation") or "").strip().upper()
    if sanity in _SANITY_REJECT:
        return False
    if orientation in {"INVALID", "UPSIDE_DOWN", "UPSIDE-DOWN", "ROTATED_BAD"}:
        return False
    return True


def explicitly_relevant(filename: str, story: str,
                        ledger_path: str | Path = DEFAULT_LEDGER) -> bool:
    """True for reviewed DIRECT/STRONG_CONTEXT authentic assets for this story."""
    if generated_asset(filename, ledger_path) or not visual_sanity_ok(filename, ledger_path):
        return False
    return verdict_for(filename, story, ledger_path) in COUNTABLE


def asset_countable(filename: str, story: str,
                    ledger_path: str | Path = DEFAULT_LEDGER) -> bool:
    """Whether this local visual may count and be served for ``story``.

    DIRECT and STRONG_CONTEXT count. Explicit weak/wrong verdicts do not.
    Unreviewed materialized ``rt-*`` files fail closed; manually curated files
    remain trusted unless explicitly vetoed. Synthetic/generated assets and
    explicit visual-sanity failures are always rejected.
    """
    name = Path(filename).name
    if generated_asset(name, ledger_path) or not visual_sanity_ok(name, ledger_path):
        return False
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
    document, receipt, advertisement or archive scan. Explicit weak/wrong,
    generated and visual-sanity-failed assets still fail closed.
    """
    source = _selected_local_source(selected_path)
    if not source:
        return False
    return asset_countable(source, story, ledger_path)


def runtime_status(photo_count: int, logo_count: int = 0) -> str:
    """Source-material gate only; final rendered-frame quality is authoritative.

    Four reviewed visuals are enough to attempt a six-card personal story. This
    is deliberately not a publication quota or target: the renderer should use
    every strong relevant visual it can find, including a fifth or sixth one.
    """
    need_visuals = max(0, 4 - int(photo_count))
    if need_visuals == 0:
        return "PASS"
    return f"NEEDS {need_visuals} MORE VISUAL{'S' if need_visuals != 1 else ''}"


def runtime_pass(photo_count: int, logo_count: int = 0) -> bool:
    return runtime_status(photo_count, logo_count) == "PASS"
