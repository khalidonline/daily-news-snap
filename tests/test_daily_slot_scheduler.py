import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import daily_slot_scheduler as scheduler


KSA = ZoneInfo("Asia/Riyadh")


class DailySlotSchedulerTests(unittest.TestCase):
    def test_recovers_most_recent_due_slot_within_window(self):
        now = datetime(2026, 9, 1, 9, 27, tzinfo=KSA)
        self.assertEqual(
            scheduler.due_slot_id(now, completed=set()),
            "2026-09-01T09:10+03:00",
        )

    def test_completed_slot_is_not_selected_twice(self):
        now = datetime(2026, 9, 1, 9, 40, tzinfo=KSA)
        completed = {"2026-09-01T09:10+03:00"}
        self.assertIsNone(scheduler.due_slot_id(now, completed=completed))

    def test_same_day_slot_older_than_recovery_window_is_not_resurrected(self):
        now = datetime(2026, 9, 1, 10, 45, tzinfo=KSA)
        self.assertIsNone(scheduler.due_slot_id(now, completed=set()))

    def test_does_not_resurrect_obsolete_overnight_slot(self):
        now = datetime(2026, 9, 2, 2, 43, tzinfo=KSA)
        self.assertIsNone(scheduler.due_slot_id(now, completed=set()))

    def test_next_slot_becomes_due_even_if_previous_slot_was_missed(self):
        now = datetime(2026, 9, 1, 11, 18, tzinfo=KSA)
        self.assertEqual(
            scheduler.due_slot_id(now, completed=set()),
            "2026-09-01T11:10+03:00",
        )

    def test_state_round_trip_marks_completed_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daily_slot_state.json"
            scheduler.mark_complete(path, "2026-09-01T09:10+03:00")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("2026-09-01T09:10+03:00", data["completed_slots"])


if __name__ == "__main__":
    unittest.main()
