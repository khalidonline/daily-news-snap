"""Build a bounded, resumable queue for bulk visual repair."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

from tools.bulk_visual_board import CoverageRow

CURSOR_PATH = Path("state/bulk_visual_repair_cursor.json")
QUEUE_CLASSES = ("photo-needed", "logo-only")


def queue_class(row: CoverageRow) -> str:
    """Return the repair queue class for an unresolved coverage row."""

    return "photo-needed" if row.need_photos else "logo-only"


def _sort_key(row: CoverageRow) -> tuple[int, int, int, str]:
    # Explicit near-PASS bands: logo-only, one photo, one photo plus logo,
    # then all larger deficits. Alphabetical ordering makes each band stable.
    if row.need_photos == 0 and row.need_logo: priority = 0
    elif row.need_photos == 1 and not row.need_logo: priority = 1
    elif row.need_photos == 1 and row.need_logo: priority = 2
    else: priority = 3
    return (priority, row.need_photos + int(row.need_logo),
            int(row.need_logo), row.story.casefold())


def _rotate(rows: list[CoverageRow], after_story: str | None) -> list[CoverageRow]:
    if not rows or not after_story:
        return rows
    for index, row in enumerate(rows):
        if row.story == after_story:
            return rows[index + 1:] + rows[:index + 1]
    return rows


def load_cursor(path: str | Path = CURSOR_PATH) -> dict[str, str | None]:
    """Load cursor positions, falling back safely when state is unavailable."""

    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        payload = {}
    return {name: payload.get(name) for name in QUEUE_CLASSES}


def save_cursor(
    cursor: Mapping[str, str | None],
    path: str | Path = CURSOR_PATH,
) -> Path:
    """Persist the cursor with a versioned on-disk representation."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, **{name: cursor.get(name) for name in QUEUE_CLASSES}}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def build_run_queue(
    rows: Iterable[CoverageRow],
    cursor: Mapping[str, str | None],
    limit: int = 12,
) -> list[CoverageRow]:
    """Order unresolved rows by class and rotate each class past its cursor."""

    limit = max(0, int(limit))
    all_rows = tuple(rows)
    members = sorted((row for row in all_rows if row.status != "PASS"), key=_sort_key)
    # Retain class cursors, but rotate only within equal-priority bands so a
    # hard alphabetical prefix cannot starve peers without defeating proximity.
    ordered = []
    for priority in range(4):
        band = [r for r in members if _sort_key(r)[0] == priority]
        marker = next((cursor.get(queue_class(r)) for r in band
                       if cursor.get(queue_class(r)) in {x.story for x in band}), None)
        ordered.extend(_rotate(band, marker))
    return ordered[:limit]


def advance_cursor(
    cursor: Mapping[str, str | None],
    row: CoverageRow,
) -> dict[str, str | None]:
    """Return cursor state advanced through ``row`` within its queue class."""

    updated = {name: cursor.get(name) for name in QUEUE_CLASSES}
    updated[queue_class(row)] = row.story
    return updated
