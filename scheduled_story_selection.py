#!/usr/bin/env python3
"""Resolve a dated owner-selected story for the scheduled review run."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KSA = ZoneInfo("Asia/Riyadh")


def _catalog_titles(path: Path) -> set[str]:
    return {
        line.split("|", 1)[0].strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def selected_story_for_run(
    selection_path: Path,
    *,
    now: datetime | None = None,
    catalog: set[str] | None = None,
) -> str:
    try:
        row = json.loads(selection_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""

    story = str(row.get("story", "")).strip()
    selected_date = str(row.get("date", "")).strip()
    today = (now or datetime.now(KSA)).astimezone(KSA).date().isoformat()
    if not story or selected_date != today:
        return ""
    if catalog is not None and story not in catalog:
        return ""
    return story


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--github-env", type=Path, required=True)
    args = parser.parse_args()

    story = selected_story_for_run(
        args.selection,
        catalog=_catalog_titles(args.catalog),
    )
    with args.github_env.open("a", encoding="utf-8") as env_file:
        env_file.write(f"SCHEDULED_STORY={story}\n")
    print(f"scheduled story selection: {story or '(automatic picker)'}")


if __name__ == "__main__":
    main()
