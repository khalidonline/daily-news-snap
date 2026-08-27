import json
import tempfile
import unittest
from pathlib import Path

from tools.bulk_visual_board import CoverageRow
from tools.bulk_visual_queue import (
    advance_cursor, build_run_queue, load_cursor, queue_class, save_cursor,
)


def row(story, need_photos, need_logo, status="NEEDS"):
    return CoverageRow(story, tuple(), tuple(), need_photos, need_logo, status)


class BulkVisualQueueTests(unittest.TestCase):
    def test_near_pass_priority_bands(self):
        rows = [
            row("Logo A", 0, True),
            row("Photo B", 2, False),
            row("Mixed C", 1, True),
        ]
        queue = build_run_queue(rows, {"photo-needed": None, "logo-only": None}, 12)
        self.assertEqual([item.story for item in queue], ["Logo A", "Mixed C", "Photo B"])
        self.assertEqual(queue_class(queue[0]), "logo-only")

    def test_cursor_rotates_past_previous_hard_prefix(self):
        rows = [row("A", 1, False), row("B", 1, False), row("C", 1, False)]
        queue = build_run_queue(rows, {"photo-needed": "B", "logo-only": None}, 3)
        self.assertEqual([item.story for item in queue], ["C", "A", "B"])

    def test_missing_cursor_story_starts_from_deterministic_head(self):
        rows = [row("B", 1, False), row("A", 1, False)]
        queue = build_run_queue(rows, {"photo-needed": "Gone", "logo-only": None}, 2)
        self.assertEqual([item.story for item in queue], ["A", "B"])

    def test_limit_is_hard(self):
        rows = [row(f"Story {n:02d}", 1, False) for n in range(20)]
        self.assertEqual(len(build_run_queue(rows, {"photo-needed": None, "logo-only": None}, 12)), 12)

    def test_cursor_round_trip_and_advance(self):
        cursor = {"photo-needed": None, "logo-only": None}
        cursor = advance_cursor(cursor, row("Hard Photo", 1, False))
        cursor = advance_cursor(cursor, row("Hard Logo", 0, True))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cursor.json"
            save_cursor(cursor, path)
            self.assertEqual(load_cursor(path), {
                "photo-needed": "Hard Photo",
                "logo-only": "Hard Logo",
            })
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], 1)
