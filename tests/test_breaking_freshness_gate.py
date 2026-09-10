import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

fake = types.ModuleType("news_bot")
fake.ANTHROPIC_API_KEY = "test-key"
fake.DRY_RUN = True
fake.commit_and_push = lambda *a, **k: None
fake.ksa_stamp = lambda: "test-stamp"
fake.notify = lambda *a, **k: None
sys.modules.setdefault("news_bot", fake)

import breaking_watch
import breaking_watch_entry

KSA = timezone(timedelta(hours=3))


class BreakingFreshnessGateTests(unittest.TestCase):
    def test_classifier_schema_requires_occurred_at(self):
        self.assertIn("occurred_at", breaking_watch.CLASSIFIER_OUTPUT_SCHEMA["required"])

    def test_yesterday_event_is_never_breaking_today(self):
        now = datetime(2026, 9, 10, 9, 0, tzinfo=KSA)
        verdict = {
            "breaking": True,
            "event": "حدث كبير",
            "occurred_at": "2026-09-09T21:00:00+03:00",
            "sources": ["Reuters", "official"],
            "official_source": True,
            "reason": "confirmed",
        }
        self.assertFalse(breaking_watch._breaking_event_is_today(verdict, now))

    def test_today_event_can_pass_freshness_gate(self):
        now = datetime(2026, 9, 10, 9, 0, tzinfo=KSA)
        verdict = {
            "breaking": True,
            "event": "حدث كبير",
            "occurred_at": "2026-09-10T08:20:00+03:00",
        }
        self.assertTrue(breaking_watch._breaking_event_is_today(verdict, now))

    def test_unknown_event_time_fails_closed(self):
        now = datetime(2026, 9, 10, 9, 0, tzinfo=KSA)
        self.assertFalse(breaking_watch._breaking_event_is_today(
            {"breaking": True, "event": "حدث", "occurred_at": ""}, now
        ))

    @patch.object(breaking_watch_entry, "_run_strict_news_bot")
    @patch.object(breaking_watch_entry.breaking_watch, "load_state", return_value={})
    @patch.object(
        breaking_watch_entry.breaking_watch,
        "ksa_now",
        return_value=datetime(2026, 9, 10, 9, 0, tzinfo=KSA),
    )
    def test_confirmed_recovery_without_same_day_occurred_at_is_refused(
        self, _now, _state, runner
    ):
        with patch.dict("os.environ", {
            "CONFIRMED_BREAKING_EVENT": "حدث مؤكد قديم",
            "CONFIRMED_BREAKING_OCCURRED_AT": "2026-09-09T21:00:00+03:00",
        }, clear=False):
            rc = breaking_watch_entry.run()
        self.assertEqual(rc, 0)
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
