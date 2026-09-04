import json
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scheduled_story_selection import selected_story_for_run


class ScheduledStorySelectionTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.temp_dir = tempfile.TemporaryDirectory()
        self.selection = Path(self.temp_dir.name) / "story_selection.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_returns_selected_story_on_matching_ksa_date(self):
        self.selection.write_text(
            json.dumps(
                {
                    "date": "2026-09-05",
                    "story": "من هم أول الموظفين السعوديين في أرامكو؟",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        now = datetime(2026, 9, 5, 14, 0, tzinfo=ZoneInfo("Asia/Riyadh"))

        self.assertEqual(
            selected_story_for_run(self.selection, now=now),
            "من هم أول الموظفين السعوديين في أرامكو؟",
        )

    def test_ignores_selection_outside_its_ksa_date(self):
        self.selection.write_text(
            json.dumps({"date": "2026-09-05", "story": "chosen"}),
            encoding="utf-8",
        )

        now = datetime(2026, 9, 6, 0, 1, tzinfo=ZoneInfo("Asia/Riyadh"))

        self.assertEqual(selected_story_for_run(self.selection, now=now), "")

    def test_rejects_story_missing_from_catalog(self):
        self.selection.write_text(
            json.dumps({"date": "2026-09-05", "story": "not in catalog"}),
            encoding="utf-8",
        )

        now = datetime(2026, 9, 5, 14, 0, tzinfo=ZoneInfo("Asia/Riyadh"))

        self.assertEqual(
            selected_story_for_run(
                self.selection,
                now=now,
                catalog={"another story"},
            ),
            "",
        )
