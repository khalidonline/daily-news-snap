import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.bulk_visual_board import (
    build_board,
    repair_backlog,
    row_for_story,
    write_board,
)


class BulkVisualBoardTests(unittest.TestCase):
    @patch("tools.bulk_visual_board.sr.coverage")
    def test_board_uses_runtime_coverage(self, coverage):
        coverage.side_effect = [
            (["a", "b", "c", "d"], ["logo"], "PASS"),
            (["a", "b", "c"], [], "NEEDS 1 MORE PHOTO + LOGO"),
        ]
        rows = build_board(["Story A", "Story B"])
        self.assertEqual(rows[0].status, "PASS")
        self.assertEqual(rows[0].need_photos, 0)
        self.assertFalse(rows[0].need_logo)
        self.assertEqual(rows[1].need_photos, 1)
        self.assertTrue(rows[1].need_logo)

    @patch("tools.bulk_visual_board.sr.coverage")
    def test_backlog_orders_smallest_gap_first(self, coverage):
        coverage.side_effect = [
            (["a", "b", "c", "d"], [], "NEEDS LOGO"),
            (["a", "b", "c"], ["logo"], "NEEDS 1 MORE PHOTO"),
            (["a"], [], "NEEDS 3 MORE PHOTOS + LOGO"),
        ]
        rows = build_board(["Logo", "One", "Large"])
        self.assertEqual(
            [row.story for row in repair_backlog(rows)],
            ["Logo", "One", "Large"],
        )

    @patch("tools.bulk_visual_board.sr.coverage")
    def test_write_board_serializes_json_and_csv(self, coverage):
        coverage.return_value = ([Path("images/a.jpg")], [], "NEEDS 3 MORE PHOTOS + LOGO")
        rows = build_board(["Story"])
        self.assertEqual(row_for_story(rows, "Story"), rows[0])
        with tempfile.TemporaryDirectory() as tmp:
            path = write_board(rows, tmp)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload[0]["photos"], ["a.jpg"])
            self.assertTrue((Path(tmp) / "board.csv").exists())


if __name__ == "__main__":
    unittest.main()
