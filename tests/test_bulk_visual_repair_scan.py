import unittest

from tools.bulk_visual_board import CoverageRow
from tools.bulk_visual_repair import process_backlog_until_progress


def row(story, need_photos=0, need_logo=True, status="NEEDS"):
    return CoverageRow(story, tuple(), tuple(), need_photos, need_logo, status)


class BulkVisualRepairScanTests(unittest.TestCase):
    def test_zero_progress_chunk_does_not_starve_later_repairable_story(self):
        rows = [row("Blocked A"), row("Blocked B"), row("Repairable")]
        calls = []

        def repair_logo(story):
            calls.append(story)
            return 1 if story == "Repairable" else 0

        def refresh(story):
            if story == "Repairable":
                return row(story, need_logo=False, status="PASS")
            return row(story)

        result = process_backlog_until_progress(
            rows,
            batch_stories=2,
            repair_logo_fn=repair_logo,
            repair_photos_fn=lambda story, deficit: 0,
            refresh_fn=refresh,
            attempt_fn=lambda record: None,
        )

        self.assertEqual(calls, ["Blocked A", "Blocked B", "Repairable"])
        self.assertEqual(result.progress, 1)
        self.assertEqual(result.processed, 3)
        self.assertEqual(result.exit_code, 10)

    def test_zero_progress_requires_full_unresolved_pass(self):
        rows = [row("Blocked A"), row("Blocked B"), row("Blocked C")]
        calls = []
        result = process_backlog_until_progress(
            rows,
            batch_stories=2,
            repair_logo_fn=lambda story: calls.append(story) or 0,
            repair_photos_fn=lambda story, deficit: 0,
            refresh_fn=lambda story: row(story),
            attempt_fn=lambda record: None,
        )

        self.assertEqual(calls, ["Blocked A", "Blocked B", "Blocked C"])
        self.assertEqual(result.progress, 0)
        self.assertEqual(result.processed, 3)
        self.assertEqual(result.exit_code, 2)


if __name__ == "__main__":
    unittest.main()
