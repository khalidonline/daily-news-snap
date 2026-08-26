#!/usr/bin/env python3
"""Build a review artifact for the runtime-relevance repair pass.

Outputs:
  out/runtime-review/status.csv
  out/runtime-review/materialized.csv
  out/runtime-review/contact-XX.jpg

The report deliberately imports the production runtime matcher so the review
queue is based on exactly what Story Bot can resolve, not on a parallel audit.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import news_bot as nb
import story_bot as sb
import story_runtime as sr
from runtime_relevance import verdict_for
from tools.bulk_visual_board import build_board

OUT = Path("out/runtime-review")


def _font(size=22):
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _story_matches(entry, stories):
    return [story for story in stories if sr._matches_story(entry, story)]


def write_status(stories):
    rows = [{
        "story": row.story,
        "photo_count": len(row.photos),
        "logo_count": len(row.logos),
        "status": row.status,
        "photos": "; ".join(row.photos),
        "logos": "; ".join(row.logos),
    } for row in build_board(stories)]
    with (OUT / "status.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    return rows


def write_materialized(stories):
    rows = []
    for entry in nb.load_local_images():
        path = entry["path"]
        if not path.name.startswith("rt-"):
            continue
        matches = _story_matches(entry, stories)
        if not matches:
            rows.append({
                "file": path.name,
                "credit": entry.get("credit", ""),
                "tags": ", ".join(entry.get("tags", [])),
                "story": "",
                "verdict": "",
            })
            continue
        for story in matches:
            rows.append({
                "file": path.name,
                "credit": entry.get("credit", ""),
                "tags": ", ".join(entry.get("tags", [])),
                "story": story,
                "verdict": verdict_for(path.name, story),
            })
    with (OUT / "materialized.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        fields = ["file", "credit", "tags", "story", "verdict"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return rows


def build_contact_sheets(materialized_rows):
    # One tile per unique file. The CSV carries every story association.
    files = []
    seen = set()
    for row in materialized_rows:
        name = row["file"]
        if name and name not in seen:
            seen.add(name)
            files.append(name)

    cols, rows_per_sheet = 4, 3
    per_sheet = cols * rows_per_sheet
    tile_w, tile_h = 520, 430
    label_h = 76
    thumb_h = tile_h - label_h
    font = _font(21)
    small = _font(16)

    for sheet_no in range(math.ceil(len(files) / per_sheet)):
        chunk = files[sheet_no * per_sheet:(sheet_no + 1) * per_sheet]
        canvas = Image.new("RGB", (cols * tile_w, rows_per_sheet * tile_h), "white")
        draw = ImageDraw.Draw(canvas)
        for idx, name in enumerate(chunk):
            col = idx % cols
            row = idx // cols
            x, y = col * tile_w, row * tile_h
            p = nb.IMAGES_DIR / name
            try:
                img = Image.open(p).convert("RGB")
                fitted = ImageOps.contain(img, (tile_w - 20, thumb_h - 20), Image.LANCZOS)
                px = x + (tile_w - fitted.width) // 2
                py = y + 10 + (thumb_h - 20 - fitted.height) // 2
                canvas.paste(fitted, (px, py))
            except Exception as exc:
                draw.rectangle((x + 10, y + 10, x + tile_w - 10, y + thumb_h - 10), outline="black")
                draw.text((x + 20, y + 30), f"UNREADABLE: {exc.__class__.__name__}", fill="black", font=font)

            assoc = [r for r in materialized_rows if r["file"] == name]
            verdicts = sorted({r["verdict"] or "UNREVIEWED" for r in assoc})
            draw.rectangle((x, y + thumb_h, x + tile_w, y + tile_h), fill=(245, 245, 245))
            draw.text((x + 12, y + thumb_h + 8), name[:46], fill="black", font=font)
            draw.text((x + 12, y + thumb_h + 40), "/".join(verdicts)[:55], fill="black", font=small)
            draw.rectangle((x, y, x + tile_w - 1, y + tile_h - 1), outline=(180, 180, 180))

        canvas.save(OUT / f"contact-{sheet_no + 1:02d}.jpg", "JPEG", quality=88)


def write_summary(status_rows, materialized_rows):
    tallies = {}
    for row in status_rows:
        tallies[row["status"]] = tallies.get(row["status"], 0) + 1
    unique_rt = len({r["file"] for r in materialized_rows})
    reviewed = len({(r["file"], r["story"]) for r in materialized_rows if r["verdict"]})
    total_assoc = len([r for r in materialized_rows if r["story"]])
    lines = [
        f"Stories: {len(status_rows)}",
        f"Unique materialized rt-* files: {unique_rt}",
        f"Materialized story associations: {total_assoc}",
        f"Reviewed associations: {reviewed}",
        "Status board:",
    ]
    for key in sorted(tallies):
        lines.append(f"  {key}: {tallies[key]}")
    (OUT / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stories = sb.load_stories()
    status_rows = write_status(stories)
    materialized_rows = write_materialized(stories)
    build_contact_sheets(materialized_rows)
    write_summary(status_rows, materialized_rows)


if __name__ == "__main__":
    main()
