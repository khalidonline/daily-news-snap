"""Build the authoritative runtime coverage board for bulk visual repair."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import story_bot as sb
import story_runtime as sr


@dataclass(frozen=True)
class CoverageRow:
    """One story's visual state, as reported by the production runtime gate."""

    story: str
    photos: tuple[str, ...]
    logos: tuple[str, ...]
    need_photos: int
    need_logo: bool
    status: str


def build_board(stories: Iterable[str] | None = None) -> list[CoverageRow]:
    """Return coverage rows without reproducing any runtime gate logic."""

    story_list = list(stories if stories is not None else sb.load_stories())
    rows = []
    for story in story_list:
        photos, logos, status = sr.coverage(story)
        rows.append(CoverageRow(
            story=story,
            photos=tuple(Path(path).name for path in photos),
            logos=tuple(Path(path).name for path in logos),
            need_photos=max(0, 4 - len(photos)),
            need_logo=not bool(logos),
            status=status,
        ))
    return rows


def repair_backlog(rows: Iterable[CoverageRow]) -> list[CoverageRow]:
    """Order failing rows by the smallest total visual deficit first."""

    failing = (row for row in rows if row.status != "PASS")
    return sorted(failing, key=lambda row: (
        row.need_photos + int(row.need_logo),
        row.need_photos,
        int(row.need_logo),
        row.story.casefold(),
    ))


def row_for_story(rows: Iterable[CoverageRow], story: str) -> CoverageRow:
    """Return the exact story row, raising ``StopIteration`` if absent."""

    return next(row for row in rows if row.story == story)


def write_board(
    rows: Sequence[CoverageRow],
    out_dir: str | Path = "out/bulk-visual-repair",
) -> Path:
    """Write the board as machine-readable JSON and spreadsheet-friendly CSV."""

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "board.json"
    json_path.write_text(
        json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with (out / "board.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        fields = [
            "story", "photo_count", "logo_count", "need_photos", "need_logo",
            "status", "photos", "logos",
        ]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "story": row.story,
                "photo_count": len(row.photos),
                "logo_count": len(row.logos),
                "need_photos": row.need_photos,
                "need_logo": int(row.need_logo),
                "status": row.status,
                "photos": "; ".join(row.photos),
                "logos": "; ".join(row.logos),
            })
    return json_path
