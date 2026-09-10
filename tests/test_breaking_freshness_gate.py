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

import breaking_freshness
import breaking_watch
import breaking_watch_entry

KSA = timezone(timedelta(hours=3))


class BreakingFreshnessGateTests(unittest.TestCase):
    def test_classifier_guidance_requires_full_event_date(self):
        original = breaking_watch.WATCH_PROMPT
        try:
            breaking_watch_entry._install_breaking_time_guidance()
            self.assertIn("YYYY-MM-DD HH:MM", breaking_watch.WATCH_PROMPT)
            self.assertIn("خبر وقع في تاريخ سعودي سابق", breaking_watch.WATCH_PROMPT)
        finally:
            breaking_watch.WATCH_PROMPT = original

    def test_yesterday_event_is_never_breaking_today(self):
        now = datetime(2026, 9, 10, 9, 0, tzinfo=KSA)
        self.assertFalse(breaking_freshness.is_same_ksa_day(
            "2026-09-09T21:00:00+03:00", now
        ))

    def test_today_event_can_pass_freshness_gate(self):
        now = datetime(2026, 9, 10, 9, 0, tzinfo=KSA)
        self.assertTrue(breaking_freshness.is_same_ksa_day(
            "2026-09-10T08:20:00+03:00", now
        ))

    def test_event_text_stamp_is_understood(self):
        now = datetime(2026, 9, 10, 9, 0, tzinfo=KSA)
        event = "حدث كبير — وقت الحدث: 2026-09-10 08:20 بتوقيت السعودية"
        self.assertTrue(breaking_freshness.is_same_ksa_day(event, now))

    def test_unknown_event_time_fails_closed(self):
        now = datetime(2026, 9, 10, 9, 0, tzinfo=KSA)
        self.assertFalse(breaking_freshness.is_same_ksa_day("حدث بلا وقت", now))

    @patch.object(breaking_watch_entry, "_run_strict_news_bot")
    @patch.object(breaking_watch_entry.breaking_watch, "load_state", return_value={})
    @patch.object(
        breaking_watch_entry.breaking_watch,
        "ksa_now",
        return_value=datetime(2026, 9, 10, 9, 0, tzinfo=KSA),
    )
    def test_confirmed_recovery_from_yesterday_is_refused(
        self, _now, _state, runner
    ):
        with patch.dict("os.environ", {
            "CONFIRMED_BREAKING_EVENT": "حدث مؤكد قديم",
            "CONFIRMED_BREAKING_OCCURRED_AT": "2026-09-09T21:00:00+03:00",
        }, clear=False):
            rc = breaking_watch_entry.run()
        self.assertEqual(rc, 0)
        runner.assert_not_called()

    @patch.object(breaking_watch_entry.subprocess, "call", return_value=0)
    @patch.object(
        breaking_watch_entry.breaking_watch,
        "ksa_now",
        return_value=datetime(2026, 9, 10, 9, 0, tzinfo=KSA),
    )
    def test_strict_runner_refuses_yesterday_before_subprocess(self, _now, call):
        rc = breaking_watch_entry._run_strict_news_bot({
            "PINNED_EVENT": "حدث قديم",
            "PINNED_EVENT_OCCURRED_AT": "2026-09-09T23:50:00+03:00",
        })
        self.assertEqual(rc, 0)
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
