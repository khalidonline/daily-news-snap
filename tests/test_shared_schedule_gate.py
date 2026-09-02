import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import shared_schedule_gate as gate


KSA = ZoneInfo("Asia/Riyadh")


class SharedScheduleGateTests(unittest.TestCase):
    def test_external_slot_is_accepted_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            requested = "2026-09-02T09:10+03:00"
            self.assertEqual(
                gate.resolve_slot(
                    bot="news",
                    now=datetime(2026, 9, 2, 9, 12, tzinfo=KSA),
                    completed=set(),
                    requested_slot=requested,
                ),
                requested,
            )
            gate.mark_complete(state, requested)
            self.assertIsNone(
                gate.resolve_slot(
                    bot="news",
                    now=datetime(2026, 9, 2, 9, 20, tzinfo=KSA),
                    completed=gate.completed_slots(state),
                    requested_slot=requested,
                )
            )

    def test_news_fallback_resolves_latest_slot(self):
        self.assertEqual(
            gate.resolve_slot(
                bot="news",
                now=datetime(2026, 9, 2, 11, 25, tzinfo=KSA),
                completed=set(),
            ),
            "2026-09-02T11:10+03:00",
        )

    def test_topic_fallback_resolves_daily_0900_slot(self):
        self.assertEqual(
            gate.resolve_slot(
                bot="topic",
                now=datetime(2026, 9, 2, 9, 20, tzinfo=KSA),
                completed=set(),
            ),
            "2026-09-02T09:00+03:00",
        )

    def test_story_fallback_resolves_daily_1400_slot(self):
        self.assertEqual(
            gate.resolve_slot(
                bot="story",
                now=datetime(2026, 9, 2, 14, 20, tzinfo=KSA),
                completed=set(),
            ),
            "2026-09-02T14:00+03:00",
        )

    def test_external_slot_for_wrong_bot_time_is_rejected(self):
        self.assertIsNone(
            gate.resolve_slot(
                bot="topic",
                now=datetime(2026, 9, 2, 9, 20, tzinfo=KSA),
                completed=set(),
                requested_slot="2026-09-02T11:10+03:00",
            )
        )

    def test_state_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            gate.mark_complete(state, "2026-09-02T14:00+03:00")
            data = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(data["completed_slots"], ["2026-09-02T14:00+03:00"])


if __name__ == "__main__":
    unittest.main()
