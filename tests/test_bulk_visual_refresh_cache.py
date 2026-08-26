import unittest
from unittest.mock import patch

import tools.bulk_visual_repair as repair
from tools.bulk_visual_board import CoverageRow


class BulkVisualRefreshCacheTests(unittest.TestCase):
    @patch("tools.bulk_visual_repair.build_board")
    @patch("tools.bulk_visual_repair.sb.load_stories")
    def test_post_write_refresh_reloads_story_metadata_before_coverage(self, load_stories, build_board):
        expected = CoverageRow("Story X", tuple(), ("example.com-current.png",), 0, False, "PASS")
        build_board.return_value = [expected]

        actual = repair.refresh_runtime_row("Story X")

        load_stories.assert_called_once_with()
        build_board.assert_called_once_with(["Story X"])
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
