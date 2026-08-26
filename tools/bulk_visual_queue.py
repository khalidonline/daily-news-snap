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
    return (
        row.need_photos + int(row.need_logo),
        row.need_photos,
        int(row.need_logo),
        row.story.casefold(),
    )


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
    classes: dict[str, list[CoverageRow]] = {}
    for name in QUEUE_CLASSES:
        members = sorted(
            (
                row
                for row in all_rows
                if row.status != "PASS" and queue_class(row) == name
            ),
            key=_sort_key,
        )
        classes[name] = _rotate(members, cursor.get(name))
    return (classes["photo-needed"] + classes["logo-only"])[:limit]


def advance_cursor(
    cursor: Mapping[str, str | None],
    row: CoverageRow,
) -> dict[str, str | None]:
    """Return cursor state advanced through ``row`` within its queue class."""

    updated = {name: cursor.get(name) for name in QUEUE_CLASSES}
    updated[queue_class(row)] = row.story
    return updated
